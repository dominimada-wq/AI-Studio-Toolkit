"""
Mission 179: type of the four top-level collections of project.json.

WorkspaceStorage.load() reads project.json. Its four top-level
collections (images, models, workflows, characters) are held to one
rule when the file is read:

* the key is absent, or its value is null: accepted, and still means
  "empty collection";
* the value is a list: accepted, and the elements of the list are not
  examined by the storage (their treatment by the Domain is unchanged);
* any other value that is present is refused with the storage's own
  error, whatever the value: {}, "", 0, 0.0 and false are refused like
  their non-empty or non-zero variants, because the test is on the type
  and never on truthiness.

When several collections are faulty only the first one, in the fixed
order images, models, workflows, characters, is reported, whatever the
order of the keys in the file. The message is
"<file> has a '<key>' value that is not a list", with exactly one error
log record and no chained cause. load() never writes, repairs, renames
or creates anything.

Out of scope, and not refused by any test here: the nested collections
of a character (datasets, loras, prompts, trainings), the entries of a
list, settings, name, version and every other key (including the keys
that older files may still carry). RecursionError, the other ValueError
cases and a file modified while it is read are not covered either. The
frequency and the origin of badly typed values are not established.

Every test below is one of two kinds:

* "Unchanged": behaviour that is the same before and after this mission
  (the accepted forms: absent key, null, empty list, valid list, list
  with badly typed elements; the root error for a root that is not an
  object; the fields listed as out of scope, which are not refused);
* "Refused": behaviour introduced by this mission (a present value that
  is not a list, in the storage and through WorkspaceManager.open()).

The kind is stated in the class names: ...AcceptedCollectionsTest and
...RootAndScopeTest hold the unchanged tests, ...RefusedCollectionsTest
the new ones.

All files are real temporary files. No Qt, no network, no process.
"""

import hashlib
import itertools
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.core.event_bus import EventBus
from src.infrastructure.storage.workspace_storage import (
    WorkspaceStorage,
    WorkspaceStorageError,
)
from src.managers.workspace_manager import (
    WORKSPACE_OPENED,
    WorkspaceManager,
    WorkspaceManagerError,
)

# The four collections, in the order in which the storage reports them.
KEYS = ("images", "models", "workflows", "characters")

# Labels of the accepted forms. "absent" is the key left out of the file.
ACCEPTED_FORMS = (
    "absent",
    "null",
    "empty list",
    "valid list",
    "list with badly typed elements",
)

# A valid list for each collection.
VALID_LISTS = {
    "images": ["legacy.png", {"image_id": "i1", "file_path": "b.png"}],
    "models": [{"model_id": "m1", "name": "M", "file_path": ""}],
    "workflows": [{"workflow_id": "w1", "name": "W", "file_path": ""}],
    "characters": [{"character_id": "c1", "name": "Aria"}],
}

# The same collections with badly typed elements around one valid entry.
BADLY_TYPED_LISTS = {
    "images": ["legacy.png", 42, None, ["x"], {"file_path": ""}, {"image_id": "i2", "file_path": "c.png"}],
    "models": [42, "x", None, [], {"model_id": "m2", "name": "M2", "file_path": ""}],
    "workflows": [42, "x", None, [], {"workflow_id": "w2", "name": "W2", "file_path": ""}],
    "characters": [42, "x", None, [], {"character_id": "c2", "name": "Bea"}],
}

# What WorkspaceManager.open() must hold after an accepted form: for the
# images, the file paths in order (a legacy string becomes an image of
# the same path); for the others, (identifier, name) pairs.
EXPECTED_AFTER_OPEN = {
    "images": {
        "valid list": ["legacy.png", "b.png"],
        "list with badly typed elements": ["legacy.png", "c.png"],
    },
    "models": {
        "valid list": [("m1", "M")],
        "list with badly typed elements": [("m2", "M2")],
    },
    "workflows": {
        "valid list": [("w1", "W")],
        "list with badly typed elements": [("w2", "W2")],
    },
    "characters": {
        "valid list": [("c1", "Aria")],
        "list with badly typed elements": [("c2", "Bea")],
    },
}

# Present values that are not lists. The first five are false in the
# sense of Python truthiness (and null-like or empty): they are refused
# all the same.
REFUSED_VALUES = {
    "empty object": {},
    "object with a string value": {"k": "v"},
    "object of objects keyed by identifier": {"id": {"name": "x"}},
    "empty string": "",
    "non-empty string": "abc",
    "zero": 0,
    "one": 1,
    "minus one": -1,
    "zero float": 0.0,
    "float": 1.5,
    "false": False,
    "true": True,
}

# One representative of each class of refused value, for the manager
# test that runs without any open workspace.
REPRESENTATIVE_REFUSED = ("empty object", "object with a string value", "one")

# Two different faulty values, given to the earlier and the later key of
# a pair.
PAIR_FAULTY_VALUES = ("abc", 1)

# Fields that the storage does not examine: it must return the object.
OUT_OF_SCOPE_PAYLOADS = {
    "settings is a string": {"settings": "x"},
    "name is an integer": {"name": 5},
    "version is a list": {"version": ["0.4"]},
    "nested datasets of a character is a string": {
        "characters": [{"character_id": "c1", "name": "A", "datasets": "abc"}]
    },
    "nested loras of a character is an integer": {
        "characters": [{"character_id": "c1", "name": "A", "loras": 42}]
    },
    "keys that older files may carry, with any type": {
        "datasets": "junk", "loras": 5, "training": {"stale": 1}
    },
    "entries of a list are not examined": {"characters": ["x", 1, None]},
}

# Roots that are not objects. Even when an element looks like a project,
# the root error is the one reported.
NON_OBJECT_ROOTS = {
    "list holding a project": b'[{"images": "abc"}]',
    "null": b"null",
}

BASE_OBJECT = {"name": "Projet Élodie – 日本語", "version": "0.4"}
LOGGER_NAME = WorkspaceStorage.__module__


def _tree(root):
    """Every path under root with the sha256 of each file's bytes."""
    snapshot = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
    return snapshot


def _encode(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def _object_with(*pairs):
    """BASE_OBJECT plus the given (key, value) pairs, in the given order."""
    obj = dict(BASE_OBJECT)
    for key, value in pairs:
        obj[key] = value
    return obj


def _accepted_value(key, form):
    """The value of the key for an accepted form; None for 'null'. Not used for 'absent'."""
    if form == "null":
        return None
    if form == "empty list":
        return []
    if form == "valid list":
        return VALID_LISTS[key]
    if form == "list with badly typed elements":
        return BADLY_TYPED_LISTS[key]
    raise AssertionError(form)


def _accepted_object(key, form):
    if form == "absent":
        return _object_with()
    return _object_with((key, _accepted_value(key, form)))


class _FolderCase(unittest.TestCase):
    """Shared helpers. This class holds no test method of its own."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self._counter = 0

    def _new_path(self, prefix):
        """A path under the temporary root that does not exist yet."""
        self._counter += 1
        return self.root / f"{prefix}{self._counter}"

    def _folder(self, payload=None):
        folder = self._new_path("case")
        folder.mkdir()
        if payload is not None:
            (folder / WorkspaceStorage.WORKSPACE_FILE).write_bytes(payload)
        return folder

    @staticmethod
    def _file(folder):
        return folder / WorkspaceStorage.WORKSPACE_FILE

    @staticmethod
    def _expected_message(folder, key):
        return f"{folder / WorkspaceStorage.WORKSPACE_FILE} has a '{key}' value that is not a list"


# ----------------------------------------------------------------------
# Storage level, accepted: behaviour that does not change
# ----------------------------------------------------------------------
class WorkspaceStorageAcceptedCollectionsTest(_FolderCase):

    def test_accepted_forms_are_returned_unchanged_and_nothing_is_written(self):
        for key in KEYS:
            for form in ACCEPTED_FORMS:
                with self.subTest(key=key, form=form):
                    obj = _accepted_object(key, form)
                    folder = self._folder(_encode(obj))
                    before = _tree(folder)

                    with self.assertNoLogs(LOGGER_NAME, level="ERROR"):
                        loaded = WorkspaceStorage.load(folder)

                    # The object read is returned as it is, element for
                    # element, including the elements of a list that the
                    # Domain would later filter.
                    self.assertEqual(loaded, obj)
                    if form == "absent":
                        self.assertNotIn(key, loaded)
                    elif form == "null":
                        self.assertIsNone(loaded[key])
                    else:
                        self.assertEqual(loaded[key], _accepted_value(key, form))
                    self.assertEqual(_tree(folder), before)


# ----------------------------------------------------------------------
# Storage level, out of scope: roots and fields that are not refused
# ----------------------------------------------------------------------
class WorkspaceStorageRootAndScopeTest(_FolderCase):

    def test_a_non_object_root_still_reports_the_root_error(self):
        for label, payload in NON_OBJECT_ROOTS.items():
            with self.subTest(root=label):
                folder = self._folder(payload)
                before = _tree(folder)

                with self.assertLogs(LOGGER_NAME, level="ERROR") as logs:
                    with self.assertRaises(WorkspaceStorageError) as raised:
                        WorkspaceStorage.load(folder)

                self.assertEqual(len(logs.records), 1)
                self.assertEqual(
                    str(raised.exception),
                    f"{self._file(folder)} does not contain a JSON object",
                )
                self.assertEqual(_tree(folder), before)

    def test_fields_out_of_scope_are_not_refused(self):
        for label, extra in OUT_OF_SCOPE_PAYLOADS.items():
            with self.subTest(field=label):
                obj = dict(BASE_OBJECT)
                obj.update(extra)
                folder = self._folder(_encode(obj))
                before = _tree(folder)

                with self.assertNoLogs(LOGGER_NAME, level="ERROR"):
                    loaded = WorkspaceStorage.load(folder)

                self.assertEqual(loaded, obj)
                self.assertEqual(_tree(folder), before)


# ----------------------------------------------------------------------
# Storage level, refused: new contract
# ----------------------------------------------------------------------
class WorkspaceStorageRefusedCollectionsTest(_FolderCase):

    def test_present_non_list_values_are_refused_with_the_dedicated_error(self):
        for key in KEYS:
            for label, value in REFUSED_VALUES.items():
                with self.subTest(key=key, value=label):
                    folder = self._folder(_encode(_object_with((key, value))))
                    before = _tree(folder)

                    with self.assertLogs(LOGGER_NAME, level="ERROR") as logs:
                        with self.assertRaises(WorkspaceStorageError) as raised:
                            WorkspaceStorage.load(folder)

                    self.assertEqual(len(logs.records), 1)
                    self.assertIn(repr(key), logs.records[0].getMessage())
                    self.assertEqual(
                        str(raised.exception), self._expected_message(folder, key)
                    )
                    self.assertIsNone(raised.exception.__cause__)
                    self.assertEqual(_tree(folder), before)

    def test_only_the_first_faulty_collection_in_the_fixed_order_is_reported(self):
        earlier_value, later_value = PAIR_FAULTY_VALUES

        for earlier, later in itertools.combinations(KEYS, 2):
            for file_order in ("fixed order", "reverse order"):
                with self.subTest(earlier=earlier, later=later, file_order=file_order):
                    pairs = [(earlier, earlier_value), (later, later_value)]
                    if file_order == "reverse order":
                        pairs.reverse()
                    payload = _encode(_object_with(*pairs))

                    # The file really lists the keys in the order claimed.
                    text = payload.decode("utf-8")
                    first_in_file = pairs[0][0]
                    second_in_file = pairs[1][0]
                    self.assertLess(
                        text.index(f'"{first_in_file}"'), text.index(f'"{second_in_file}"')
                    )

                    folder = self._folder(payload)
                    before = _tree(folder)

                    with self.assertLogs(LOGGER_NAME, level="ERROR") as logs:
                        with self.assertRaises(WorkspaceStorageError) as raised:
                            WorkspaceStorage.load(folder)

                    self.assertEqual(len(logs.records), 1)
                    self.assertEqual(
                        str(raised.exception), self._expected_message(folder, earlier)
                    )
                    self.assertEqual(_tree(folder), before)

        with self.subTest(case="all four faulty, written in reverse order"):
            pairs = [(key, PAIR_FAULTY_VALUES[0]) for key in reversed(KEYS)]
            payload = _encode(_object_with(*pairs))
            text = payload.decode("utf-8")
            self.assertLess(text.index('"characters"'), text.index('"images"'))
            folder = self._folder(payload)

            with self.assertLogs(LOGGER_NAME, level="ERROR") as logs:
                with self.assertRaises(WorkspaceStorageError) as raised:
                    WorkspaceStorage.load(folder)

            self.assertEqual(len(logs.records), 1)
            self.assertEqual(str(raised.exception), self._expected_message(folder, "images"))


# ----------------------------------------------------------------------
# Manager level
# ----------------------------------------------------------------------
class _ManagerCase(_FolderCase):

    def _manager(self):
        bus = EventBus()
        events = []
        bus.subscribe(WORKSPACE_OPENED, events.append)
        return WorkspaceManager(event_bus=bus), events


class WorkspaceManagerAcceptedCollectionsTest(_ManagerCase):

    def test_accepted_forms_open_the_workspace_and_keep_the_expected_elements(self):
        for key in KEYS:
            for form in ACCEPTED_FORMS:
                with self.subTest(key=key, form=form):
                    folder = self._folder(_encode(_accepted_object(key, form)))
                    before = _tree(folder)
                    manager, events = self._manager()

                    with self.assertNoLogs(LOGGER_NAME, level="ERROR"):
                        workspace = manager.open(folder)

                    self.assertIsNotNone(workspace)
                    self.assertIs(manager.current_workspace, workspace)
                    self.assertEqual(len(events), 1)
                    self.assertEqual(_tree(folder), before)

                    for other in KEYS:
                        held = self._summary(workspace, other)
                        if other == key and form in EXPECTED_AFTER_OPEN[key]:
                            self.assertEqual(held, EXPECTED_AFTER_OPEN[key][form])
                        else:
                            self.assertEqual(held, [])

                    if key == "images" and form in EXPECTED_AFTER_OPEN[key]:
                        ids = [image.image_id for image in workspace.images]
                        self.assertTrue(all(ids))
                        self.assertEqual(len(set(ids)), len(ids))
                        if form == "valid list":
                            # A legacy string gets a new identifier; an
                            # entry that has one keeps it.
                            self.assertEqual(ids[1], "i1")
                        else:
                            self.assertEqual(ids[1], "i2")

    @staticmethod
    def _summary(workspace, key):
        if key == "images":
            return [image.file_path for image in workspace.images]
        if key == "models":
            return [(model.model_id, model.name) for model in workspace.models]
        if key == "workflows":
            return [(workflow.workflow_id, workflow.name) for workflow in workspace.workflows]
        return [(c.character_id, c.name) for c in workspace.characters]


class WorkspaceManagerRefusedCollectionsTest(_ManagerCase):

    def _assert_refused_open(self, manager, events, previous, key, value):
        folder = self._folder(_encode(_object_with((key, value))))
        before = _tree(folder)
        previous_content = previous.to_dict() if previous is not None else None

        with self.assertLogs(LOGGER_NAME, level="ERROR") as logs:
            with self.assertRaises(WorkspaceManagerError) as raised:
                manager.open(folder)

        self.assertEqual(len(logs.records), 1)
        self.assertEqual(str(raised.exception), self._expected_message(folder, key))
        self.assertIs(manager.current_workspace, previous)
        if previous is not None:
            self.assertEqual(previous.to_dict(), previous_content)
        self.assertEqual(events, [])
        self.assertEqual(_tree(folder), before)

    def test_a_refused_open_changes_nothing_and_keeps_the_open_workspace(self):
        for key in KEYS:
            for label, value in REFUSED_VALUES.items():
                with self.subTest(key=key, value=label):
                    manager, events = self._manager()
                    previous = manager.create(self._new_path("open"))
                    events.clear()

                    self._assert_refused_open(manager, events, previous, key, value)

    def test_a_refused_open_with_no_workspace_open_leaves_none(self):
        for key in KEYS:
            for label in REPRESENTATIVE_REFUSED:
                with self.subTest(key=key, value=label):
                    manager, events = self._manager()

                    self._assert_refused_open(manager, events, None, key, REFUSED_VALUES[label])


if __name__ == "__main__":
    unittest.main()
