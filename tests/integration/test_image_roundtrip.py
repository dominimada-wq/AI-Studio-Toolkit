"""
Integration coverage for Mission 011's Image domain object: its own
to_dict()/from_dict() round-trip, the legacy list[str] -> list[Image]
migration (Image.list_from_data()) applied by both Workspace and
Dataset, and the ownership model D invariant — Workspace.images and
Dataset.images are two independent pools, never sharing identity or
cross-referencing each other, even when they contain the same
file_path. Also confirms Character.images was fully removed (dead
field, no consumer — see Mission 011 architectural audit).
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.core.event_bus import EventBus
from src.domain.character import Character
from src.domain.dataset import Dataset
from src.domain.image import Image
from src.domain.workspace import Workspace
from src.managers.character_manager import CharacterManager
from src.managers.dataset_manager import DatasetManager
from src.managers.workspace_manager import WorkspaceManager


class ImageRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ImageProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        return event_bus, workspace_manager, character_manager, dataset_manager

    def test_image_domain_object_roundtrip_and_defaults(self):

        # Default values.
        image = Image()
        self.assertEqual(image.image_id, "")
        self.assertEqual(image.file_path, "")
        self.assertEqual(image.to_dict(), {"image_id": "", "file_path": ""})

        # Round-trip without loss of information.
        original = Image(image_id="abc-123", file_path="C:/images/ref.png")
        restored = Image.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        # Missing key -> default, consistent with every other Domain object.
        self.assertEqual(Image.from_dict({}), Image())
        self.assertEqual(Image.from_dict({"file_path": "only_path.png"}).image_id, "")
        self.assertEqual(Image.from_dict({"image_id": "only_id"}).file_path, "")

    def test_list_from_data_migrates_legacy_and_filters_invalid(self):

        entries = [
            "legacy_a.png",                              # legacy str -> new Image, new id
            {"image_id": "kept-id", "file_path": "b.png"},  # already migrated -> id preserved
            "legacy_a.png",                              # duplicate path -> its own Image, its own id
            None,                                         # invalid -> filtered
            42,                                           # invalid -> filtered
            ["nested"],                                   # invalid -> filtered
        ]

        images = Image.list_from_data(entries)

        # Only the 3 valid entries (2 legacy str + 1 dict) survive.
        self.assertEqual(len(images), 3)
        self.assertEqual([img.file_path for img in images], ["legacy_a.png", "b.png", "legacy_a.png"])

        # Legacy entries get a freshly generated, non-empty id each.
        self.assertTrue(images[0].image_id)
        self.assertTrue(images[2].image_id)
        # The duplicate path produces two distinct Image instances with
        # distinct ids — no merge, no data loss.
        self.assertNotEqual(images[0].image_id, images[2].image_id)

        # The already-migrated dict entry keeps its own id verbatim.
        self.assertEqual(images[1].image_id, "kept-id")

        # Absent/None input degrades to an empty list, same principle as
        # every other nested-list field in this codebase.
        self.assertEqual(Image.list_from_data(None), [])
        self.assertEqual(Image.list_from_data([]), [])

    def test_list_from_data_filters_dicts_without_usable_file_path(self):

        entries = [
            "a.png",                                       # valid legacy str -> kept
            {},                                             # no file_path -> filtered
            {"image_id": "abc"},                            # no file_path -> filtered
            {"file_path": ""},                               # empty file_path -> filtered
            {"file_path": None},                             # non-str file_path -> filtered
            {"file_path": 42},                               # non-str file_path -> filtered
            {"image_id": "valid-id", "file_path": "b.png"},  # valid dict -> kept
            None,                                            # wrong type -> filtered
            42,                                              # wrong type -> filtered
            ["c.png"],                                       # wrong type -> filtered
        ]

        # No exception raised while processing this mixed, partly
        # malformed collection.
        images = Image.list_from_data(entries)

        # Only the 2 genuinely valid entries survive — neighbours of
        # invalid entries are preserved, nothing is dropped by mistake.
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0].file_path, "a.png")
        self.assertTrue(images[0].image_id)
        self.assertEqual(images[1], Image(image_id="valid-id", file_path="b.png"))

        # An incomplete dict must never silently produce an empty-string
        # Image — this is exactly the case Mission 011's review flagged.
        self.assertNotIn(Image(image_id="", file_path=""), images)
        self.assertNotIn(Image(image_id="abc", file_path=""), images)

    def test_workspace_migrates_legacy_images_without_loss(self):

        workspace = Workspace.from_dict({
            "images": ["a.png", "b.png", "a.png", None, 42],
        })

        self.assertEqual(len(workspace.images), 3)
        self.assertEqual(
            [image.file_path for image in workspace.images],
            ["a.png", "b.png", "a.png"],
        )
        ids = [image.image_id for image in workspace.images]
        self.assertTrue(all(ids))
        self.assertEqual(len(set(ids)), 3, "each legacy entry must get its own distinct id")

    def test_dataset_migrates_legacy_images_without_loss(self):

        dataset = Dataset.from_dict({
            "dataset_id": "d1",
            "name": "Portraits",
            "images": ["x.png", "y.png", "x.png"],
        })

        self.assertEqual(len(dataset.images), 3)
        self.assertEqual(
            [image.file_path for image in dataset.images],
            ["x.png", "y.png", "x.png"],
        )
        ids = [image.image_id for image in dataset.images]
        self.assertTrue(all(ids))
        self.assertEqual(len(set(ids)), 3)

    def test_workspace_and_dataset_roundtrip_preserves_image_id_new_format(self):

        original_workspace = Workspace(
            name="P",
            images=[Image(image_id="w1", file_path="a.png"), Image(image_id="w2", file_path="b.png")],
        )
        restored_workspace = Workspace.from_dict(original_workspace.to_dict())
        self.assertEqual(
            [(i.image_id, i.file_path) for i in restored_workspace.images],
            [("w1", "a.png"), ("w2", "b.png")],
        )

        original_dataset = Dataset(
            dataset_id="d1",
            name="Portraits",
            images=[Image(image_id="i1", file_path="c.png")],
        )
        restored_dataset = Dataset.from_dict(original_dataset.to_dict())
        self.assertEqual(
            [(i.image_id, i.file_path) for i in restored_dataset.images],
            [("i1", "c.png")],
        )

    def test_manager_add_images_ids_stable_across_save_and_reopen(self):

        _, workspace_manager, _character_manager, _dataset_manager = self._wire()
        workspace_manager.create(self.folder)

        workspace_manager.add_images(["ref1.png", "ref2.png"])
        original_ids = [image.image_id for image in workspace_manager.current_workspace.images]
        self.assertTrue(all(original_ids))

        workspace_manager.close()

        _, workspace_manager_2, _character_manager_2, _dataset_manager_2 = self._wire()
        workspace_manager_2.open(self.folder)

        reopened_ids = [image.image_id for image in workspace_manager_2.current_workspace.images]
        self.assertEqual(reopened_ids, original_ids)

    def test_dataset_manager_add_images_dedups_prospectively_by_file_path(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        added1 = dataset_manager.add_images(["a.png", "b.png"])
        self.assertEqual(added1, 2)

        added2 = dataset_manager.add_images(["a.png", "c.png"])
        self.assertEqual(added2, 1)

        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            ["a.png", "b.png", "c.png"],
        )

    def test_workspace_and_dataset_pools_are_independent(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        # The exact same file_path imported into both pools.
        workspace_manager.add_images(["shared.png"])
        dataset_manager.add_images(["shared.png"])

        workspace_image = workspace_manager.current_workspace.images[0]
        dataset_image = dataset_manager.active_dataset.images[0]

        self.assertEqual(workspace_image.file_path, dataset_image.file_path)
        # Two independent instances, two independent ids — no shared
        # registry, no cross-pool reference (ownership model D).
        self.assertIsNot(workspace_image, dataset_image)
        self.assertNotEqual(workspace_image.image_id, dataset_image.image_id)

        # Deleting/clearing one pool must never affect the other.
        workspace_manager.current_workspace.images.clear()
        self.assertEqual(len(dataset_manager.active_dataset.images), 1)

    def test_character_images_field_was_removed(self):

        character = Character(character_id="c1", name="Aria")
        self.assertFalse(hasattr(character, "images"))
        self.assertNotIn("images", character.to_dict())

        # Legacy project.json entries carrying a "images" key under a
        # Character are silently ignored on load, same defensive
        # principle applied to every other unknown/removed key.
        restored = Character.from_dict({
            "character_id": "c1",
            "name": "Aria",
            "images": ["stale.png"],
        })
        self.assertFalse(hasattr(restored, "images"))


if __name__ == "__main__":
    unittest.main()
