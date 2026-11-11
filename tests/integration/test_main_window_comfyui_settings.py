"""
Narrow coverage for Mission 018 — MainWindow reads ComfyUI's base_url/
checkpoint_name exclusively from ApplicationSettings (the sole source
of truth as of this mission), never from a fallback constant of its
own (none exists anymore in main_window.py). Real MainWindow instances
are constructed, with ApplicationSettingsStorage.default_directory()
redirected to a temporary directory so the real %LOCALAPPDATA% is
never touched — same lesson as test_application_settings_roundtrip.py.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.engines.comfyui_engine import ComfyUIEngine, ComfyUIEngineError
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)
from src.ui.main_window import COMFYUI_GENERATION_TIMEOUT, MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowComfyUISettingsTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_main_window_uses_default_comfyui_settings_when_none_configured(self):
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        # No fallback constant left in MainWindow — this is
        # ApplicationSettings' own literal default (see
        # test_application_settings_domain_object_roundtrip_and_defaults),
        # read straight through.
        self.assertEqual(window.comfyui_engine._base_url, "http://127.0.0.1:8000")
        self.assertEqual(
            window.generation_manager._checkpoint_name,
            "v1-5-pruned-emaonly-fp16.safetensors",
        )
        # Mission 059: same "sole source of truth, no fallback constant"
        # contract as checkpoint_name above — "" honestly means "no
        # LoRA configured".
        self.assertEqual(window.generation_manager._lora_name, "")
        self.assertEqual(window.generation_manager._lora_strength, 1.0)

    def test_main_window_uses_configured_comfyui_url_and_checkpoint_from_application_settings(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {
                "comfyui_url": "http://192.168.1.50:8188",
                "comfyui_checkpoint_name": "sdxl_base.safetensors",
                "comfyui_lora_name": "style.safetensors",
                "comfyui_lora_strength": 0.7,
            },
        )

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=configured_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.comfyui_engine._base_url, "http://192.168.1.50:8188")
        self.assertEqual(
            window.generation_manager._checkpoint_name, "sdxl_base.safetensors"
        )
        self.assertEqual(window.generation_manager._lora_name, "style.safetensors")
        self.assertEqual(window.generation_manager._lora_strength, 0.7)


class _FakeResponse:
    """Minimal stand-in for the object urllib.request.urlopen() returns."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class _FakeClock:
    """
    Deterministic replacement for the `time` module as used by
    ComfyUIEngine.wait_for_result(): sleeping advances the clock instantly,
    so a generation lasting minutes is simulated without any real wait.
    """

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


# Longer than the former 120 s default, shorter than the new 600 s timeout.
SIMULATED_GENERATION_SECONDS = 150.0
_PROMPT_ID = "prompt-1"


def _history_entry_with_image():
    return {
        _PROMPT_ID: {
            "status": {"status_str": "success", "completed": True, "messages": []},
            "outputs": {
                "9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
            },
        }
    }


class _SimulatedComfyUIServer:
    """
    A fake ComfyUI that only answers GET /history/<id> — never a submission.
    Its history stays empty until `completes_after` simulated seconds have
    elapsed (None: never completes). Any other request fails the test, which
    also proves that nothing is ever submitted again while waiting.
    """

    def __init__(self, clock, completes_after):
        self._clock = clock
        self._completes_after = completes_after
        self.requests = []
        self.timeouts = []

    def urlopen(self, request, timeout=None):
        self.requests.append((request.get_method(), request.full_url))
        self.timeouts.append(timeout)
        if request.get_method() != "GET" or f"/history/{_PROMPT_ID}" not in request.full_url:
            raise AssertionError(f"unexpected request: {request.get_method()} {request.full_url}")
        if self._completes_after is not None and self._clock.now >= self._completes_after:
            return _FakeResponse(json.dumps(_history_entry_with_image()).encode("utf-8"))
        return _FakeResponse(b"{}")


class MainWindowComfyUIGenerationTimeoutTest(unittest.TestCase):
    """
    The ComfyUI engine of the Inference page uses COMFYUI_GENERATION_TIMEOUT.
    The durations are simulated (fake clock, fake server): no real generation
    and no real wait. What this does NOT cover: the real ComfyUI, real
    network timeouts of the operating system, and the Qt worker thread.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def _build_window(self):
        with patch.object(
            ApplicationSettingsStorage,
            "default_directory",
            return_value=Path(self.tmp_dir) / "NoSettingsFile",
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        return window

    def _wait_with(self, engine, completes_after):
        clock = _FakeClock()
        server = _SimulatedComfyUIServer(clock, completes_after)
        with patch("src.engines.comfyui_engine.time", clock), patch(
            "urllib.request.urlopen", side_effect=server.urlopen
        ):
            try:
                result = engine.wait_for_result(_PROMPT_ID)
                error = None
            except ComfyUIEngineError as caught:
                result = None
                error = caught
        return clock, server, result, error

    def test_main_window_comfyui_engine_uses_the_generation_timeout(self):
        window = self._build_window()

        self.assertEqual(COMFYUI_GENERATION_TIMEOUT, 600.0)
        self.assertEqual(window.comfyui_engine._timeout, COMFYUI_GENERATION_TIMEOUT)

    def test_a_generation_longer_than_the_former_120_seconds_succeeds(self):
        window = self._build_window()

        clock, server, result, error = self._wait_with(
            window.comfyui_engine, SIMULATED_GENERATION_SECONDS
        )

        self.assertIsNone(error)
        self.assertIn("9", result)
        # The simulated generation really lasted longer than 120 s...
        self.assertGreaterEqual(clock.now, SIMULATED_GENERATION_SECONDS)
        # ...and every HTTP request of this engine shares the same timeout.
        self.assertEqual(set(server.timeouts), {COMFYUI_GENERATION_TIMEOUT})

    def test_the_former_120_second_timeout_expires_on_the_same_generation(self):
        # Regression guard: documents the failure this timeout fixes.
        clock, _server, result, error = self._wait_with(
            ComfyUIEngine(timeout=120.0), SIMULATED_GENERATION_SECONDS
        )

        self.assertIsNone(result)
        self.assertIsInstance(error, ComfyUIEngineError)
        self.assertIn(f"Timed out waiting for ComfyUI result for prompt {_PROMPT_ID}", str(error))
        self.assertLess(clock.now, SIMULATED_GENERATION_SECONDS)

    def test_expiry_reports_the_timeout_message_and_never_submits_again(self):
        window = self._build_window()

        clock, server, result, error = self._wait_with(window.comfyui_engine, None)

        self.assertIsNone(result)
        self.assertIsInstance(error, ComfyUIEngineError)
        self.assertIn(f"Timed out waiting for ComfyUI result for prompt {_PROMPT_ID}", str(error))
        self.assertGreaterEqual(clock.now, COMFYUI_GENERATION_TIMEOUT)
        # Only history polling happened: no submission, hence no duplicate job.
        self.assertTrue(server.requests)
        self.assertTrue(all(method == "GET" for method, _url in server.requests))


if __name__ == "__main__":
    unittest.main()
