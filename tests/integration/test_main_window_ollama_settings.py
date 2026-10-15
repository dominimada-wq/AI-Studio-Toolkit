"""
Narrow coverage for Mission 031's pre-implementation verification 1 —
MainWindow reads Ollama's base_url/model_name exclusively from
ApplicationSettings, once at construction, exactly the same no-hot-reload
contract already established for ComfyUI (Mission 018,
test_main_window_comfyui_settings.py). Real MainWindow instances are
constructed, with ApplicationSettingsStorage.default_directory()
redirected to a temporary directory so the real %LOCALAPPDATA% is never
touched.

Mission 177 adds assertions on the timeout of the assistant's engine and
rebuilds the fixture of the WHOLE module (the three historical tests keep
their assertions). The description below states what the fixture is meant
to guarantee.

Isolation. setUp points LOCALAPPDATA, USERPROFILE and HOME at a private
temporary tree, redirects ApplicationSettingsStorage.default_directory()
for the whole life of the test (the LoRA library storage resolves through
the same method), and requires, before any window is built, that the
settings and LoRA-library locations resolve under that tree. Tripwires on
socket.socket.connect, socket.socket.connect_ex and urllib.request.urlopen,
and recorders for QMessageBox, are active from before the construction until
the windows have been checked as destroyed. Each call to a tripwire is
recorded (the label of the intercepted function only: no address, no data)
BEFORE the AssertionError is raised, so an attempt whose exception is
swallowed by the code under test is still counted. The records are kept until
after the destruction and checked by a cleanup registered before any window
is built, which therefore also runs when the test or the construction fails;
the count is part of the DISPOSAL balance. These tripwires cover only those
three Python-level entry points: they do not show that the construction of
MainWindow makes no other network or native (Qt) activity.

Disposal. The disposal cleanup is registered before any window is built, so
it also runs when MainWindow() raises. It closes the returned window when
there is one (the close must be accepted and must open no dialog), requests
the deferred deletion of every top-level widget created since setUp,
delivers the deferred-delete events and requires that none of these widgets
is still valid. All of this runs before the private tree is removed (cleanups
run in reverse order of registration), and that removal does not ignore
errors, so an incomplete cleanup is reported as a failure. A window whose
construction failed is handled on a best-effort basis: it is looked for among
the new top-level widgets and its destruction is checked; nothing here
claims that a failed construction left no window or resource behind.
"""

import os
import shutil
import socket
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from shiboken6 import isValid

from src.domain.application_settings import ApplicationSettings
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
)
from src.infrastructure.storage.lora_library_storage import LoRALibraryStorage
from src.ui import main_window as main_window_module
from src.ui.main_window import MainWindow
from src.ui.pages.settings_page import OLLAMA_DISCOVERY_TIMEOUT

_app = QApplication.instance() or QApplication([])

# One entry (a dict) per test: test id, a window was returned, close accepted, dialogs opened by the close,
# new top-level widgets, number of widgets still valid, number of connection attempts intercepted. Created at the
# start of the disposal (so it exists even if the disposal fails) and completed by the cleanups; a value still None
# when printed was never established. Printed by tearDownModule().
_DISPOSAL_LOG = []


class MainWindowOllamaSettingsTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        # No ignore_errors: an incomplete removal must fail visibly. Registered first, so it runs last.
        self.addCleanup(shutil.rmtree, self.tmp_dir)
        root = Path(self.tmp_dir)

        env_patcher = patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": str(root / "localappdata"),
                "USERPROFILE": str(root / "home"),
                "HOME": str(root / "home"),
            },
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        (root / "localappdata").mkdir()
        (root / "home").mkdir()

        # Redirection of the settings storage, maintained until the disposal cleanup has run. The directory is
        # chosen per test through _build_window() (it must exist before the window is built).
        self._settings_dir = root / "DefaultSettings"
        directory_patcher = patch.object(
            ApplicationSettingsStorage, "default_directory", side_effect=lambda: self._settings_dir
        )
        directory_patcher.start()
        self.addCleanup(directory_patcher.stop)

        for label, location in (
            ("application settings", ApplicationSettingsStorage.default_directory()),
            ("LoRA library registry", LoRALibraryStorage.default_directory()),
            ("default LoRA library path", ApplicationSettings().lora_library_path),
            ("home", Path.home()),
        ):
            self.assertTrue(
                os.path.normcase(str(location)).startswith(os.path.normcase(str(root))),
                f"isolation failed: {label} resolves outside the private tree: {location}",
            )

        self.dialogs = []
        for name, result in (
            ("information", QMessageBox.Ok),
            ("warning", QMessageBox.Ok),
            ("critical", QMessageBox.Ok),
            ("question", QMessageBox.No),
        ):
            patcher = patch.object(QMessageBox, name, side_effect=self._recorder(name, result))
            patcher.start()
            self.addCleanup(patcher.stop)

        def _fake_exec(box, *args, **kwargs):
            self.dialogs.append(("exec", [box.text()]))
            return QMessageBox.Cancel

        exec_patcher = patch.object(QMessageBox, "exec", _fake_exec)
        exec_patcher.start()
        self.addCleanup(exec_patcher.stop)

        self.connection_attempts = []
        for target, attribute, label in (
            (socket.socket, "connect", "socket.connect"),
            (socket.socket, "connect_ex", "socket.connect_ex"),
            (urllib.request, "urlopen", "urllib.request.urlopen"),
        ):
            tripwire = patch.object(target, attribute, side_effect=self._tripwire(label))
            tripwire.start()
            self.addCleanup(tripwire.stop)

        # Registered after the tripwires and before any window is built, hence run after the disposal below and
        # before the tripwires are removed: it runs even when the test or the construction fails.
        self._disposal_entry = None
        self.addCleanup(self._verify_no_connection_attempt)

        # Registered last, hence run first, and before any window is built: it also covers a construction that fails.
        self.window = None
        self._widgets_before = list(QApplication.topLevelWidgets())
        self.addCleanup(self._dispose_windows)

    def _tripwire(self, label):
        def _raise(*args, **kwargs):
            # Recorded first, so that an exception swallowed by the code under test is still counted. The label of
            # the intercepted function only: neither the address nor any data is kept.
            self.connection_attempts.append(label)
            raise AssertionError("a real connection is forbidden in this test")

        return _raise

    def _verify_no_connection_attempt(self):
        attempts = list(self.connection_attempts)
        if self._disposal_entry is not None:
            self._disposal_entry["attempts"] = len(attempts)
        self.assertEqual(attempts, [], "the code under test reached a connection tripwire")

    def _recorder(self, name, result):
        def _fake(*args, **kwargs):
            self.dialogs.append((name, [a for a in args if isinstance(a, str)]))
            return result

        return _fake

    def _build_window(self, settings_dir):
        """
        Builds a real MainWindow whose settings directory is `settings_dir` (it must lie under the private tree).
        The engines are only constructed; the tripwires set up in setUp are meant to make any real connection
        attempt during the test fail it.
        """
        self.assertTrue(
            os.path.normcase(str(settings_dir)).startswith(os.path.normcase(self.tmp_dir)),
            f"the settings directory is outside the private tree: {settings_dir}",
        )
        self._settings_dir = settings_dir
        self.window = MainWindow()
        return self.window

    def _dispose_windows(self):
        window = self.window
        new_widgets = [
            widget for widget in QApplication.topLevelWidgets()
            if not any(widget is old for old in self._widgets_before)
        ]
        closed = None
        remaining = []
        dialogs_before = len(self.dialogs)
        dialogs_opened = 0
        entry = {
            "test": self.id(), "window": window is not None, "closed": None, "dialogs": 0,
            "widgets": len(new_widgets), "remaining": None, "attempts": None,
        }
        self._disposal_entry = entry
        _DISPOSAL_LOG.append(entry)
        try:
            if window is not None and isValid(window):
                closed = window.close()
        finally:
            dialogs_opened = len(self.dialogs) - dialogs_before
            for widget in new_widgets:
                if isValid(widget):
                    widget.deleteLater()
            # Deferred deletions are only delivered from an event loop; deliver them explicitly.
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            _app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            remaining = [widget for widget in new_widgets if isValid(widget)]
            entry["closed"] = closed
            entry["dialogs"] = dialogs_opened
            entry["remaining"] = len(remaining)

        if window is not None:
            self.assertTrue(closed, "MainWindow.close() was refused by a production close guard")
            self.assertEqual(dialogs_opened, 0, "a close guard opened a dialog")
        self.assertEqual(remaining, [], "top-level widgets are still valid after deleteLater()")

    def test_main_window_uses_default_ollama_settings_when_none_configured(self):
        empty_dir = Path(self.tmp_dir) / "NoSettingsFile"

        window = self._build_window(empty_dir)

        # ApplicationSettings' own literal default (Mission 030), read
        # straight through — no fallback constant in main_window.py.
        self.assertEqual(window.ollama_engine._base_url, "http://127.0.0.1:11434")
        self.assertEqual(window.prompt_assistant_manager._model_name, "")

    def test_main_window_uses_configured_ollama_url_and_model_from_application_settings(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {
                "ollama_url": "http://192.168.1.50:11434",
                "ollama_model_name": "llama3.2:3b",
            },
        )

        window = self._build_window(configured_dir)

        self.assertEqual(window.ollama_engine._base_url, "http://192.168.1.50:11434")
        self.assertEqual(window.prompt_assistant_manager._model_name, "llama3.2:3b")

    def test_settings_change_after_construction_does_not_affect_the_already_built_engine(self):
        """
        Confirms the deliberate no-hot-reload contract explicitly
        (mirrors SettingsPage's own application_hint label): saving a
        new ollama_url via ApplicationSettingsManager after MainWindow
        was constructed must never retroactively change
        window.ollama_engine/window.prompt_assistant_manager — a
        restart is required, exactly like ComfyUI.
        """
        configured_dir = Path(self.tmp_dir) / "RuntimeChangeSettings"

        window = self._build_window(configured_dir)
        window.application_settings_manager.update(
            ollama_url="http://10.0.0.9:11434", ollama_model_name="mistral:latest"
        )

        self.assertEqual(window.ollama_engine._base_url, "http://127.0.0.1:11434")
        self.assertEqual(window.prompt_assistant_manager._model_name, "")

    # ------------------------------------------------------------------ prompt assistant timeout (M177)
    # The three tests above keep their assertions. The two groups below are kept apart by nature of result: the
    # invariants are expected to hold on the previous production too; the other tests assert the new contract and
    # are expected to fail on the previous production by construction (the constant did not exist and the engine
    # used the 30 s default).

    def test_the_assistant_engine_is_the_backend_of_the_prompt_assistant_manager(self):
        window = self._build_window(Path(self.tmp_dir) / "NoSettingsFile")

        self.assertIs(window.prompt_assistant_manager._ai_backend, window.ollama_engine)

    def test_the_discovery_timeout_of_the_settings_page_is_unchanged(self):
        self.assertEqual(OLLAMA_DISCOVERY_TIMEOUT, 5.0)

    def test_the_generation_timeout_is_a_distinct_120_second_policy_value(self):
        value = getattr(main_window_module, "OLLAMA_GENERATION_TIMEOUT", None)

        self.assertIsNotNone(value, "main_window.OLLAMA_GENERATION_TIMEOUT does not exist")
        self.assertEqual(value, 120.0)
        self.assertNotEqual(value, OLLAMA_DISCOVERY_TIMEOUT)

    def test_the_assistant_engine_is_built_with_the_generation_timeout_by_default(self):
        window = self._build_window(Path(self.tmp_dir) / "NoSettingsFile")

        self.assertEqual(window.ollama_engine._timeout, 120.0)

    def test_the_assistant_engine_timeout_does_not_depend_on_the_configured_url_and_model(self):
        configured_dir = Path(self.tmp_dir) / "ConfiguredSettings"
        ApplicationSettingsStorage.save(
            configured_dir,
            {
                "ollama_url": "http://192.168.1.50:11434",
                "ollama_model_name": "llama3.2:3b",
            },
        )

        window = self._build_window(configured_dir)

        self.assertEqual(window.ollama_engine._base_url, "http://192.168.1.50:11434")
        self.assertEqual(window.ollama_engine._timeout, 120.0)

    def test_a_settings_change_after_construction_does_not_alter_the_assistant_engine_timeout(self):
        window = self._build_window(Path(self.tmp_dir) / "RuntimeChangeSettings")

        window.application_settings_manager.update(
            ollama_url="http://10.0.0.9:11434", ollama_model_name="mistral:latest"
        )

        self.assertEqual(window.ollama_engine._base_url, "http://127.0.0.1:11434")
        self.assertEqual(window.ollama_engine._timeout, 120.0)

    @patch("src.ui.pages.settings_page.OllamaEngine")
    def test_model_discovery_still_builds_its_own_short_timeout_engine_beside_the_assistant_one(
        self, mock_engine_class
    ):
        mock_engine_class.return_value.list_models.return_value = []
        window = self._build_window(Path(self.tmp_dir) / "NoSettingsFile")

        window.settings_page.refresh_ollama_models()

        self.assertEqual(mock_engine_class.call_args.kwargs["timeout"], OLLAMA_DISCOVERY_TIMEOUT)
        self.assertEqual(window.ollama_engine._timeout, 120.0)


def tearDownModule():
    for entry in _DISPOSAL_LOG:
        sys.stderr.write(
            f"DISPOSAL {entry['test'].rsplit('.', 1)[-1]}: window_returned={entry['window']} closed={entry['closed']} "
            f"dialogs_during_close={entry['dialogs']} new_top_level_widgets={entry['widgets']} "
            f"still_valid={entry['remaining']} connection_attempts={entry['attempts']}\n"
        )
    sys.stderr.write(f"DISPOSAL SUMMARY: {len(_DISPOSAL_LOG)} disposals\n")


if __name__ == "__main__":
    unittest.main()
