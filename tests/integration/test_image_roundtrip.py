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
from src.domain.generation_metadata import GenerationMetadata, GenerationReference
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
        self.assertIsNone(image.generation_metadata)
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

        # Mission 028: add_images() physically copies each source, so
        # real external files are required here.
        ref1 = Path(self.tmp_dir) / "ref1.png"
        ref2 = Path(self.tmp_dir) / "ref2.png"
        ref1.write_bytes(b"fake-png-1")
        ref2.write_bytes(b"fake-png-2")

        workspace_manager.add_images([str(ref1), str(ref2)])
        original_ids = [image.image_id for image in workspace_manager.current_workspace.images]
        self.assertTrue(all(original_ids))
        self.assertEqual(len(original_ids), 2)

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

        a = Path(self.tmp_dir) / "a.png"
        b = Path(self.tmp_dir) / "b.png"
        c = Path(self.tmp_dir) / "c.png"
        a.write_bytes(b"fake-a")
        b.write_bytes(b"fake-b")
        c.write_bytes(b"fake-c")

        result1 = dataset_manager.add_images([str(a), str(b)])
        self.assertEqual(result1.added, 2)

        # Re-selecting the exact same external source a second time is
        # not deduplicated by content (Mission 028: no hash-based
        # dedup) — it produces its own internal copy, collision-safe
        # since "a.png" is already taken in the destination folder.
        result2 = dataset_manager.add_images([str(a), str(c)])
        self.assertEqual(result2.added, 2)

        dataset_id = dataset_manager.active_dataset.dataset_id
        destination = self.folder / "datasets" / dataset_id
        self.assertEqual(
            [image.file_path for image in dataset_manager.active_dataset.images],
            [
                str(destination / "a.png"),
                str(destination / "b.png"),
                str(destination / "a_1.png"),
                str(destination / "c.png"),
            ],
        )

        # Re-selecting an already-internal copy (not an external
        # source anymore) is recognized as a genuine duplicate.
        already_internal = dataset_manager.active_dataset.images[0].file_path
        result3 = dataset_manager.add_images([already_internal])
        self.assertEqual(result3.added, 0)
        self.assertEqual(result3.skipped, [already_internal])
        self.assertEqual(len(dataset_manager.active_dataset.images), 4)

    def test_workspace_and_dataset_pools_are_independent(self):

        _, workspace_manager, character_manager, dataset_manager = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        dataset_manager.select(dataset.dataset_id)

        # The exact same external source imported into both pools —
        # Mission 028: each pool gets its own physical copy, under its
        # own destination folder, so the resulting file_path values
        # are no longer expected to be equal (only their basenames
        # are, since neither copy triggers a collision in its own
        # destination folder).
        shared_source = Path(self.tmp_dir) / "shared.png"
        shared_source.write_bytes(b"fake-shared")

        workspace_manager.add_images([str(shared_source)])
        dataset_manager.add_images([str(shared_source)])

        workspace_image = workspace_manager.current_workspace.images[0]
        dataset_image = dataset_manager.active_dataset.images[0]

        self.assertEqual(
            Path(workspace_image.file_path).name, Path(dataset_image.file_path).name
        )
        self.assertNotEqual(workspace_image.file_path, dataset_image.file_path)
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


class GenerationMetadataRoundTripTest(unittest.TestCase):
    """
    Mission 123: GenerationMetadata/GenerationReference round-trip,
    Image.generation_metadata's sentinel (None), and the defensive
    deserialization contract for a hand-edited or legacy project.json.
    """

    def test_generation_reference_roundtrip_and_defaults(self):

        reference = GenerationReference()
        self.assertEqual(reference.path, "")
        self.assertEqual(reference.role, "")
        self.assertEqual(reference.to_dict(), {"path": "", "role": ""})

        original = GenerationReference(path="C:/refs/pose.png", role="pose_composition")
        restored = GenerationReference.from_dict(original.to_dict())
        self.assertEqual(original, restored)

    def test_generation_metadata_roundtrip_and_defaults(self):

        metadata = GenerationMetadata()
        self.assertEqual(metadata.engine, "")
        self.assertEqual(metadata.seed, -1)
        self.assertEqual(metadata.checkpoint_name, None)
        self.assertEqual(metadata.lora_strength, None)
        self.assertEqual(metadata.references, [])

        original = GenerationMetadata(
            engine="comfyui",
            prompt="a portrait",
            negative_prompt="blurry",
            seed=42,
            width=512,
            height=768,
            steps=20,
            cfg=7.5,
            sampler_name="euler",
            scheduler="normal",
            checkpoint_name="v1-5-pruned-emaonly-fp16.safetensors",
            lora_name="my_lora.safetensors",
            lora_strength=0.8,
            references=[GenerationReference(path="ref.png", role="pose_composition")],
            reference_strength=0.75,
        )
        restored = GenerationMetadata.from_dict(original.to_dict())
        self.assertEqual(original, restored)

    def test_image_with_generation_metadata_roundtrip(self):

        metadata = GenerationMetadata(engine="forge", prompt="a cat", seed=7)
        original = Image(image_id="i1", file_path="cat.png", generation_metadata=metadata)

        data = original.to_dict()
        self.assertIn("generation_metadata", data)

        restored = Image.from_dict(data)
        self.assertEqual(original, restored)
        self.assertEqual(restored.generation_metadata.prompt, "a cat")
        self.assertEqual(restored.generation_metadata.seed, 7)

    def test_image_from_dict_defensive_generation_metadata(self):

        # Absent key -> None, no error (legacy project.json).
        self.assertIsNone(Image.from_dict({"image_id": "i1", "file_path": "a.png"}).generation_metadata)

        # Wrong type -> None, never an exception.
        for bad_value in (None, "not-a-dict", 42, ["nested"]):
            restored = Image.from_dict({
                "image_id": "i1",
                "file_path": "a.png",
                "generation_metadata": bad_value,
            })
            self.assertIsNone(restored.generation_metadata)

        # references absent/non-list -> empty list, never an exception.
        for bad_references in (None, "not-a-list", {"a": 1}, 42):
            restored = Image.from_dict({
                "image_id": "i1",
                "file_path": "a.png",
                "generation_metadata": {"engine": "comfyui", "references": bad_references},
            })
            self.assertEqual(restored.generation_metadata.references, [])

        # A non-dict entry inside references is silently filtered out,
        # same defensive convention as Image.list_from_data().
        restored = Image.from_dict({
            "image_id": "i1",
            "file_path": "a.png",
            "generation_metadata": {
                "engine": "comfyui",
                "references": [
                    {"path": "a.png", "role": "pose_composition"},
                    None,
                    42,
                    "not-a-dict",
                ],
            },
        })
        self.assertEqual(len(restored.generation_metadata.references), 1)
        self.assertEqual(restored.generation_metadata.references[0].path, "a.png")

        # Optional fields (checkpoint_name/lora_strength) stay correctly
        # optional -- absent or explicit null both resolve to None, never
        # an invented default.
        restored = Image.from_dict({
            "image_id": "i1",
            "file_path": "a.png",
            "generation_metadata": {"engine": "comfyui", "checkpoint_name": None, "lora_strength": None},
        })
        self.assertIsNone(restored.generation_metadata.checkpoint_name)
        self.assertIsNone(restored.generation_metadata.lora_strength)

    def test_generation_metadata_no_shared_mutable_state_between_instances(self):

        # field(default_factory=list) must never let two default
        # instances share the same underlying list.
        first = GenerationMetadata()
        second = GenerationMetadata()
        first.references.append(GenerationReference(path="a.png", role="pose_composition"))
        self.assertEqual(first.references, [GenerationReference(path="a.png", role="pose_composition")])
        self.assertEqual(second.references, [])

        # from_dict() builds fresh GenerationReference instances, never
        # reusing the raw dicts from the loaded data.
        data = {
            "engine": "comfyui",
            "references": [{"path": "a.png", "role": "pose_composition"}],
        }
        loaded_a = GenerationMetadata.from_dict(data)
        loaded_b = GenerationMetadata.from_dict(data)
        self.assertIsNot(loaded_a.references, loaded_b.references)
        self.assertIsNot(loaded_a.references[0], loaded_b.references[0])
        loaded_a.references[0].path = "mutated.png"
        self.assertEqual(loaded_b.references[0].path, "a.png")


if __name__ == "__main__":
    unittest.main()
