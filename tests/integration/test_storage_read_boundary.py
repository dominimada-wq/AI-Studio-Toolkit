"""
Mission 178: read boundary of the three file storages.

WorkspaceStorage (project.json), ApplicationSettingsStorage and
LoRALibraryStorage all read one JSON file. For the categories covered
here (invalid JSON, a root that is not a JSON object, bytes that are not
valid UTF-8, an OSError raised while reading or by Path.exists()), a
file that is present but unusable must come out of load() as the
storage's own dedicated error, never as a raw exception of those
categories and never as None, which only ever means "the file does not
exist". load() must never write, repair, rename or create anything.

Out of scope, and not covered by any test here: RecursionError (very
deeply nested JSON), the other ValueError cases (for example the
integer digit limit of the json module), and badly typed inner
structures (collections of project.json, entries of a collection).

Every test below is one of two kinds:

* "Invariants": behaviour that was already true before this mission and
  must stay true (absent file, valid UTF-8 object with accents, invalid
  JSON, a UTF-8 BOM still refused as invalid JSON, a read OSError, the
  non-object roots of the two machine-local storages).
* "NewContract": behaviour introduced by this mission (a non-object root
  of project.json, bytes that are not valid UTF-8, an OSError raised by
  Path.exists()).

For the storage test classes the kind is stated in the class name
(...InvariantsTest, ...RootInvariantsTest, ...NewContractTest). The
manager test classes do not all follow that convention:
WorkspaceManagerOpenFailureTest mixes invariants (absent project file,
invalid JSON, a failed open with no workspace open, a successful open)
and new-contract tests (non-object roots, undecodable bytes), and
MachineLocalManagerUndecodableFileTest holds new-contract tests only.

All files are real temporary files. Two OSError cases use a double
(a PermissionError raised by open() or by Path.exists()): a double
shows how the storage reacts to that exception, not that Windows
raises it for a real access refusal. No Qt, no network, no process.
"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.event_bus import EventBus
from src.infrastructure.storage.application_settings_storage import (
    ApplicationSettingsStorage,
    ApplicationSettingsStorageError,
)
from src.infrastructure.storage.lora_library_storage import (
    LoRALibraryStorage,
    LoRALibraryStorageError,
)
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.managers.lora_library_manager import LoRALibraryManager
from src.managers.workspace_manager import (
    WORKSPACE_OPENED,
    WorkspaceManager,
    WorkspaceManagerError,
)

UTF8_BOM = b"\xef\xbb\xbf"

# JSON values that are valid JSON but not an object.
NON_OBJECT_ROOTS = {
    "list": b"[1, 2, 3]",
    "string": b'"just text"',
    "integer": b"42",
    "float": b"1.5",
    "true": b"true",
    "null": b"null",
}

# Byte strings that are not valid UTF-8 text. The first two are UTF-16 LE
# content (b"\xff\xfe" is the UTF-16 LE signature): they are rejected
# because they do not conform to the UTF-8 encoding the storages expect,
# not because a BOM is missing.
UNDECODABLE_BYTES = {
    "utf-16-le signature alone": b"\xff\xfe",
    "utf-16-le encoded object": b"\xff\xfe{\x00}\x00",
    "invalid continuation byte": b"{\xc3(}",
    "latin-1 accented letter": b'{"name": "\xe9"}',
    "truncated multi-byte sequence": b'{"name": "\xe2\x82"}',
}


def _tree(root):
    """Every path under root with the sha256 of each file's bytes."""
    snapshot = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
    return snapshot


def _utf8(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class _StorageCase:
    """
    Shared helpers. Not a TestCase on its own: each concrete class below
    mixes it with unittest.TestCase and names its storage.
    """

    STORAGE = None
    ERROR = None
    FILE_NAME = None
    VALID_OBJECT = None

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.directory = self.root / "data"
        self.directory.mkdir()
        self.file = self.directory / self.FILE_NAME

    def _load(self):
        return self.STORAGE.load(self.directory)

    def _logger_name(self):
        return self.STORAGE.__module__

    def _assert_refused(self, payload, expected_message_end, expected_cause=None):
        """
        Writes payload as the storage file, then checks: the dedicated
        error, exactly one error log record, the message, the chained
        cause, and that the directory is byte-for-byte what it was
        (same files, same bytes, nothing created).
        """
        self.file.write_bytes(payload)
        before = _tree(self.directory)

        with self.assertLogs(self._logger_name(), level="ERROR") as logs:
            with self.assertRaises(self.ERROR) as raised:
                self._load()

        self.assertEqual(len(logs.records), 1)
        message = str(raised.exception)
        self.assertTrue(message.startswith(str(self.file)) or message.startswith("Could not read"), message)
        self.assertTrue(message.endswith(expected_message_end), message)
        if expected_cause is None:
            self.assertIsNone(raised.exception.__cause__)
        else:
            self.assertIsInstance(raised.exception.__cause__, expected_cause)
        self.assertEqual(_tree(self.directory), before)
        return raised.exception


# ----------------------------------------------------------------------
# Invariants: true before this mission, must stay true
# ----------------------------------------------------------------------
class _InvariantsMixin(_StorageCase):

    def test_absent_file_returns_none_and_creates_nothing(self):
        before = _tree(self.directory)

        self.assertIsNone(self._load())

        self.assertEqual(before, {})
        self.assertEqual(_tree(self.directory), before)

    def test_absent_directory_returns_none_and_is_not_created(self):
        missing = self.root / "never_created"

        self.assertIsNone(self.STORAGE.load(missing))

        self.assertFalse(missing.exists())

    def test_valid_utf8_object_with_accents_is_loaded_and_left_untouched(self):
        self.file.write_bytes(_utf8(self.VALID_OBJECT))
        before = _tree(self.directory)

        loaded = self._load()

        self.assertEqual(loaded, self.VALID_OBJECT)
        self.assertEqual(_tree(self.directory), before)

    def test_empty_object_is_a_valid_object(self):
        self.file.write_bytes(b"{}")

        self.assertEqual(self._load(), {})

    def test_invalid_json_is_refused_with_the_dedicated_error(self):
        self._assert_refused(b"{not valid json at all", "is not valid JSON", json.JSONDecodeError)

    def test_utf8_bom_before_a_valid_object_is_still_refused_as_invalid_json(self):
        # The BOM refusal comes from the json module itself and keeps the
        # generic "not valid JSON" error: no BOM-specific mechanism.
        self._assert_refused(UTF8_BOM + _utf8(self.VALID_OBJECT), "is not valid JSON", json.JSONDecodeError)

    def test_read_oserror_is_converted_with_the_chained_cause(self):
        # Double: open() raises PermissionError. It shows the conversion,
        # not that Windows raises this exception for a real refusal.
        self.file.write_bytes(_utf8(self.VALID_OBJECT))
        before = _tree(self.directory)
        module = sys.modules[self.STORAGE.__module__]

        with patch.object(module, "open", create=True, side_effect=PermissionError(13, "denied")):
            with self.assertLogs(self._logger_name(), level="ERROR") as logs:
                with self.assertRaises(self.ERROR) as raised:
                    self._load()

        self.assertEqual(len(logs.records), 1)
        self.assertEqual(str(raised.exception), f"Could not read {self.file}")
        self.assertIsInstance(raised.exception.__cause__, PermissionError)
        self.assertEqual(_tree(self.directory), before)


class WorkspaceStorageInvariantsTest(_InvariantsMixin, unittest.TestCase):
    STORAGE = WorkspaceStorage
    ERROR = WorkspaceStorageError
    FILE_NAME = WorkspaceStorage.WORKSPACE_FILE
    VALID_OBJECT = {"name": "Projet Élodie – 日本語", "version": "1"}


class ApplicationSettingsStorageInvariantsTest(_InvariantsMixin, unittest.TestCase):
    STORAGE = ApplicationSettingsStorage
    ERROR = ApplicationSettingsStorageError
    FILE_NAME = ApplicationSettingsStorage.FILE_NAME
    VALID_OBJECT = {"python_path": "C:/Programmes/Élodie – 日本語"}


class LoRALibraryStorageInvariantsTest(_InvariantsMixin, unittest.TestCase):
    STORAGE = LoRALibraryStorage
    ERROR = LoRALibraryStorageError
    FILE_NAME = LoRALibraryStorage.FILE_NAME
    VALID_OBJECT = {"loras": [], "note": "Élodie – 日本語"}


class _MachineLocalRootInvariantsMixin(_StorageCase):
    """Non-object roots of the two machine-local storages (already refused before this mission)."""

    def test_non_object_roots_are_refused_without_touching_the_file(self):
        for label, payload in NON_OBJECT_ROOTS.items():
            with self.subTest(root=label):
                self._assert_refused(payload, "does not contain a JSON object")


class ApplicationSettingsRootInvariantsTest(_MachineLocalRootInvariantsMixin, unittest.TestCase):
    STORAGE = ApplicationSettingsStorage
    ERROR = ApplicationSettingsStorageError
    FILE_NAME = ApplicationSettingsStorage.FILE_NAME


class LoRALibraryRootInvariantsTest(_MachineLocalRootInvariantsMixin, unittest.TestCase):
    STORAGE = LoRALibraryStorage
    ERROR = LoRALibraryStorageError
    FILE_NAME = LoRALibraryStorage.FILE_NAME


# ----------------------------------------------------------------------
# New contract
# ----------------------------------------------------------------------
class _NewContractMixin(_StorageCase):

    def test_bytes_that_are_not_valid_utf8_are_refused_with_the_dedicated_error(self):
        for label, payload in UNDECODABLE_BYTES.items():
            with self.subTest(bytes=label):
                self._assert_refused(payload, "is not valid UTF-8 text", UnicodeDecodeError)

    def test_exists_oserror_is_converted_with_the_chained_cause(self):
        # Double: Path.exists() raises PermissionError, as pathlib does
        # for an OSError it does not treat as "not found". It shows the
        # conversion, not that Windows raises it for a real refusal.
        self.file.write_bytes(_utf8(self.VALID_OBJECT))
        before = _tree(self.directory)

        with patch.object(Path, "exists", side_effect=PermissionError(13, "denied")):
            with self.assertLogs(self._logger_name(), level="ERROR") as logs:
                with self.assertRaises(self.ERROR) as raised:
                    self._load()

        self.assertEqual(len(logs.records), 1)
        self.assertEqual(str(raised.exception), f"Could not read {self.file}")
        self.assertIsInstance(raised.exception.__cause__, PermissionError)
        self.assertEqual(_tree(self.directory), before)


class WorkspaceStorageNewContractTest(_NewContractMixin, unittest.TestCase):
    STORAGE = WorkspaceStorage
    ERROR = WorkspaceStorageError
    FILE_NAME = WorkspaceStorage.WORKSPACE_FILE
    VALID_OBJECT = {"name": "Projet Élodie – 日本語", "version": "1"}

    def test_a_non_object_root_is_refused_and_null_is_not_taken_for_an_absent_file(self):
        roots = dict(NON_OBJECT_ROOTS, **{"false": b"false"})
        for label, payload in roots.items():
            with self.subTest(root=label):
                self._assert_refused(payload, "does not contain a JSON object")


class ApplicationSettingsStorageNewContractTest(_NewContractMixin, unittest.TestCase):
    STORAGE = ApplicationSettingsStorage
    ERROR = ApplicationSettingsStorageError
    FILE_NAME = ApplicationSettingsStorage.FILE_NAME
    VALID_OBJECT = {"python_path": "C:/Programmes/Élodie – 日本語"}


class LoRALibraryStorageNewContractTest(_NewContractMixin, unittest.TestCase):
    STORAGE = LoRALibraryStorage
    ERROR = LoRALibraryStorageError
    FILE_NAME = LoRALibraryStorage.FILE_NAME
    VALID_OBJECT = {"loras": [], "note": "Élodie – 日本語"}


# ----------------------------------------------------------------------
# Manager level: WorkspaceManager.open() and the two machine-local managers
# ----------------------------------------------------------------------
class WorkspaceManagerOpenFailureTest(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.bus = EventBus()
        self.opened_events = []
        self.bus.subscribe(WORKSPACE_OPENED, self.opened_events.append)
        self.manager = WorkspaceManager(event_bus=self.bus)

    def _open_a_valid_workspace(self):
        folder = self.root / "good"
        self.manager.create(folder)
        self.opened_events.clear()
        return folder, self.manager.current_workspace

    def _bad_folder(self, payload=None):
        folder = self.root / "bad"
        folder.mkdir(exist_ok=True)
        if payload is not None:
            (folder / WorkspaceStorage.WORKSPACE_FILE).write_bytes(payload)
        return folder

    def _assert_failed_open_changes_nothing(self, folder, previous):
        before = _tree(folder)

        with self.assertRaises(WorkspaceManagerError):
            self.manager.open(folder)

        self.assertIs(self.manager.current_workspace, previous)
        self.assertEqual(self.opened_events, [])
        self.assertEqual(_tree(folder), before)

    def test_absent_project_file_returns_none_and_keeps_the_open_workspace(self):
        _, previous = self._open_a_valid_workspace()
        folder = self._bad_folder()

        self.assertIsNone(self.manager.open(folder))

        self.assertIs(self.manager.current_workspace, previous)
        self.assertEqual(self.opened_events, [])
        self.assertEqual(_tree(folder), {})

    def test_invalid_json_raises_the_manager_error_and_keeps_the_open_workspace(self):
        _, previous = self._open_a_valid_workspace()
        folder = self._bad_folder(b"{not valid json at all")

        self._assert_failed_open_changes_nothing(folder, previous)

    def test_a_failed_open_with_no_workspace_open_leaves_none(self):
        folder = self._bad_folder(b"{not valid json at all")

        self._assert_failed_open_changes_nothing(folder, None)

    def test_a_successful_open_still_publishes_workspace_opened(self):
        folder, _ = self._open_a_valid_workspace()

        opened = self.manager.open(folder)

        self.assertIsNotNone(opened)
        self.assertEqual(len(self.opened_events), 1)

    def test_non_object_roots_raise_the_manager_error_and_change_nothing(self):
        _, previous = self._open_a_valid_workspace()
        for label, payload in dict(NON_OBJECT_ROOTS, **{"false": b"false"}).items():
            with self.subTest(root=label):
                folder = self._bad_folder(payload)
                self._assert_failed_open_changes_nothing(folder, previous)

    def test_undecodable_bytes_raise_the_manager_error_and_change_nothing(self):
        _, previous = self._open_a_valid_workspace()
        for label, payload in UNDECODABLE_BYTES.items():
            with self.subTest(bytes=label):
                folder = self._bad_folder(payload)
                self._assert_failed_open_changes_nothing(folder, previous)


class MachineLocalManagerUndecodableFileTest(unittest.TestCase):
    """The managers load their file while being constructed: they must fail, and write nothing."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _assert_construction_refused(self, file_name, build, error):
        for label, payload in UNDECODABLE_BYTES.items():
            with self.subTest(bytes=label):
                directory = self.root / label.replace(" ", "_")
                directory.mkdir()
                (directory / file_name).write_bytes(payload)
                before = _tree(directory)

                with self.assertRaises(error):
                    build(directory)

                self.assertEqual(_tree(directory), before)

    def test_application_settings_manager_refuses_an_undecodable_file(self):
        self._assert_construction_refused(
            ApplicationSettingsStorage.FILE_NAME,
            lambda directory: ApplicationSettingsManager(storage_directory=directory),
            ApplicationSettingsStorageError,
        )

    def test_lora_library_manager_refuses_an_undecodable_file(self):
        self._assert_construction_refused(
            LoRALibraryStorage.FILE_NAME,
            lambda directory: LoRALibraryManager(storage_directory=directory),
            LoRALibraryStorageError,
        )


if __name__ == "__main__":
    unittest.main()
