"""
Narrow coverage for Mission 108 — MainWindow reads Forge's own base_url
exclusively from ApplicationSettings.forge_url, same "sole source of
truth, no fallback constant, read once at startup" contract already
established for ComfyUI (Mission 018) and OneTrainer/Ollama. Real
MainWindow instances are constructed, with
ApplicationSettingsStorage.default_directory() redirected to a
temporary directory so the real %LOCALAPPDATA% is never touched — same
convention as test_main_window_comfyui_settings.py.
"""

import base64
import json
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.engines.forge_engine import ForgeEngine, ForgeEngineError
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)
from src.ui.main_window import FORGE_GENERATION_TIMEOUT, MainWindow

_app = QApplication.instance() or QApplication([])


class MainWindowForgeSettingsTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_main_window_uses_default_forge_url_when_none_configured(self):
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        # ApplicationSettings' own literal default (see
        # test_application_settings_domain_object_roundtrip_and_defaults),
        # read straight through — no fallback constant in MainWindow.
        self.assertEqual(window.forge_engine._base_url, "http://127.0.0.1:7860")

    def test_main_window_uses_configured_forge_url_from_application_settings(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {"forge_url": "http://192.168.1.50:7860"},
        )

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=configured_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertEqual(window.forge_engine._base_url, "http://192.168.1.50:7860")

    def test_main_window_injects_both_engines_into_inference_page(self):
        # Mission 108 section 3.2: two explicit dependencies, the exact
        # same instances MainWindow itself holds — never a second
        # construction, never a dict/registry.
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile2"

        with patch.object(
            ApplicationSettingsStorage, "default_directory", return_value=empty_dir
        ):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertIs(window.inference_page._comfyui_engine, window.comfyui_engine)
        self.assertIs(window.inference_page._forge_engine, window.forge_engine)


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


# Longer than the former 120 s default, shorter than the new 600 s timeout.
SIMULATED_GENERATION_SECONDS = 150.0


class _SimulatedForgeServer:
    """
    A fake Forge whose single blocking generation request takes
    SIMULATED_GENERATION_SECONDS: like a real socket, the request fails with
    a TimeoutError when the client timeout is shorter than that, and
    succeeds otherwise. Nothing is slept: the duration is only compared
    with the timeout the client passed.
    """

    def __init__(self):
        self.requests = []
        self.timeouts = []

    def urlopen(self, request, timeout=None):
        self.requests.append((request.get_method(), request.full_url))
        self.timeouts.append(timeout)
        if timeout is None or timeout < SIMULATED_GENERATION_SECONDS:
            raise TimeoutError("timed out")
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"simulated").decode("ascii")
        return _FakeResponse(json.dumps({"images": [png]}).encode("utf-8"))


class MainWindowForgeGenerationTimeoutTest(unittest.TestCase):
    """
    The Forge engine of the Inference page uses FORGE_GENERATION_TIMEOUT,
    and a timeout is reported as a timeout, not as an unreachable server.
    The durations are simulated (fake server, no real wait): this does NOT
    cover the real Forge, real operating-system timeouts, or the Qt worker
    thread and the dialog that displays the message.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.output_dir = Path(self.tmp_dir) / "out"
        self.output_dir.mkdir()

    def _build_window(self):
        with patch.object(
            ApplicationSettingsStorage,
            "default_directory",
            return_value=Path(self.tmp_dir) / "NoSettingsFile",
        ):
            window = MainWindow()
        self.addCleanup(window.close)
        return window

    def test_main_window_forge_engine_uses_the_generation_timeout(self):
        window = self._build_window()

        self.assertEqual(FORGE_GENERATION_TIMEOUT, 600.0)
        self.assertEqual(window.forge_engine._timeout, FORGE_GENERATION_TIMEOUT)

    def test_a_generation_longer_than_the_former_120_seconds_succeeds(self):
        window = self._build_window()
        server = _SimulatedForgeServer()

        with patch("urllib.request.urlopen", side_effect=server.urlopen):
            image_path = window.forge_engine.generate_image("a fox", str(self.output_dir))

        self.assertTrue(Path(image_path).is_file())
        # One single request, made with the new timeout.
        self.assertEqual(server.timeouts, [FORGE_GENERATION_TIMEOUT])
        self.assertEqual(len(server.requests), 1)

    def test_the_former_120_second_timeout_expires_on_the_same_generation(self):
        # Regression guard: documents the failure this timeout fixes.
        server = _SimulatedForgeServer()

        with patch("urllib.request.urlopen", side_effect=server.urlopen):
            with self.assertRaises(ForgeEngineError) as context:
                ForgeEngine(timeout=120.0).generate_image("a fox", str(self.output_dir))

        self.assertIn("did not respond within 120 s", str(context.exception))
        self.assertEqual(len(server.requests), 1)

    def test_expiry_reports_a_timeout_and_never_claims_more_than_it_knows(self):
        window = self._build_window()

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")) as mock_urlopen:
            with self.assertRaises(ForgeEngineError) as context:
                window.forge_engine.generate_image("a fox", str(self.output_dir))

        message = str(context.exception)
        self.assertIn("did not respond within 600 s", message)
        self.assertIn("/sdapi/v1/txt2img", message)
        self.assertIn("timed out", message)
        self.assertIn("unknown", message)
        # No claim that the server is unreachable or that anything stopped.
        self.assertNotIn("unreachable", message)
        self.assertNotIn("stopped", message)
        # And no automatic second attempt: no duplicate generation.
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_a_timeout_wrapped_in_url_error_while_connecting_is_also_a_timeout(self):
        window = self._build_window()

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError(TimeoutError("timed out")),
        ):
            with self.assertRaises(ForgeEngineError) as context:
                window.forge_engine.generate_image("a fox", str(self.output_dir))

        self.assertIn("did not respond within 600 s", str(context.exception))
        self.assertNotIn("unreachable", str(context.exception))

    def test_a_refused_connection_is_still_reported_as_unreachable(self):
        window = self._build_window()

        for failure in (
            urllib.error.URLError(ConnectionRefusedError(10061, "refused")),
            urllib.error.URLError("Connection refused"),
            ConnectionResetError(10054, "reset"),
        ):
            with self.subTest(failure=repr(failure)):
                with patch("urllib.request.urlopen", side_effect=failure):
                    with self.assertRaises(ForgeEngineError) as context:
                        window.forge_engine.generate_image("a fox", str(self.output_dir))

                message = str(context.exception)
                self.assertIn("Forge server unreachable at http://127.0.0.1:7860", message)
                self.assertNotIn("did not respond", message)


if __name__ == "__main__":
    unittest.main()
