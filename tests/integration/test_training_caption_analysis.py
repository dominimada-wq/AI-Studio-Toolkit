"""
TrainingManager.caption_analysis_inputs(): the read-only view of the caption
texts a training would use. The decisive property is that it can never diverge
from what _materialize_concept() really writes: both go through the single
resolve_concept_caption() rule (explicit entry — even an empty one — versus an
absent entry that falls back to the trigger word). Real EventBus and Managers,
temporary isolated projects, fictitious data only.
"""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.event_bus import EventBus
from src.domain.dataset import DatasetEntryMetadata
from src.engines.caption_length_check import caption_lines, fingerprint_caption_inputs
from src.infrastructure.storage.workspace_storage import WorkspaceStorage
from src.managers.character_manager import CharacterManager
from src.managers.dataset_manager import DatasetManager
from src.managers.training_manager import (
    CAPTION_ORIGIN_ENTRY,
    CAPTION_ORIGIN_TRIGGER_WORD,
    TrainingManager,
    resolve_concept_caption,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.managers.workspace_manager import WorkspaceManager

TRIGGER = "Kaëlya woman"


class ResolveConceptCaptionRuleTest(unittest.TestCase):

    def test_an_absent_entry_falls_back_to_the_trigger_word(self):
        self.assertEqual(resolve_concept_caption(None, TRIGGER), (TRIGGER, CAPTION_ORIGIN_TRIGGER_WORD))

    def test_an_entry_is_used_as_is(self):
        self.assertEqual(
            resolve_concept_caption(DatasetEntryMetadata(caption="une légende"), TRIGGER),
            ("une légende", CAPTION_ORIGIN_ENTRY),
        )

    def test_an_explicitly_empty_entry_is_never_replaced_by_the_trigger_word(self):
        self.assertEqual(
            resolve_concept_caption(DatasetEntryMetadata(caption=""), TRIGGER), ("", CAPTION_ORIGIN_ENTRY)
        )


class CaptionAnalysisInputsTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.folder = self.tmp / "CaptionProject"
        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        self.training_manager = TrainingManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)

        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)
        imports = self.tmp / "Imports"
        imports.mkdir()
        for name in ("a.png", "b.png", "c.png", "a.jpg"):
            (imports / name).write_bytes(b"fake-image-bytes")
        # a.png and a.jpg share a stem: the concept folder names them a.png / a_1.jpg.
        self.dataset_manager.add_images([str(imports / name) for name in ("a.png", "b.png", "c.png", "a.jpg")])
        self.by_name = {Path(image.file_path).name: image for image in self.dataset.images}
        self.dataset_manager.set_caption(self.by_name["a.png"].image_id, "Légende A, « élégante »")
        self.dataset_manager.set_caption(self.by_name["b.png"].image_id, "")                 # explicitly empty
        self.dataset_manager.set_caption(self.by_name["a.jpg"].image_id, "Première ligne\n\n  Deuxième ligne  ")
        # c.png: no entry at all.

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(trigger_word=TRIGGER)

    def inputs(self):
        return self.training_manager.caption_analysis_inputs(self.training.training_id)

    def tree_state(self):
        return {
            str(path.relative_to(self.folder)): (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(self.folder.rglob("*")) if path.is_file()
        }

    # --- content ---------------------------------------------------------------------------------------------

    def test_one_item_per_image_in_dataset_order_with_exact_text_and_origin(self):
        inputs = self.inputs()

        self.assertEqual(inputs["training_id"], self.training.training_id)
        self.assertEqual(inputs["training_name"], "Session 1")
        self.assertEqual(inputs["dataset_id"], self.dataset.dataset_id)
        self.assertEqual(inputs["architecture"], self.training.architecture)
        self.assertEqual([i["image_id"] for i in inputs["items"]], [img.image_id for img in self.dataset.images])
        by_file = {i["file_name"]: i for i in inputs["items"]}
        self.assertEqual((by_file["a.png"]["text"], by_file["a.png"]["origin"]), ("Légende A, « élégante »", "entry"))
        self.assertEqual((by_file["b.png"]["text"], by_file["b.png"]["origin"]), ("", "entry"))
        self.assertEqual((by_file["c.png"]["text"], by_file["c.png"]["origin"]), (TRIGGER, "trigger_word"))
        self.assertEqual(by_file["a.jpg"]["text"], "Première ligne\n\n  Deuxième ligne  ")

    def test_the_concept_names_of_the_image_and_of_its_caption_file_are_given_separately(self):
        items = self.inputs()["items"]

        images = {i["file_name"]: i["concept_image_file_name"] for i in items}
        captions = {i["file_name"]: i["concept_caption_file_name"] for i in items}

        # a.png and a.jpg share a stem: the second image is renamed a_1.jpg and so is its caption file.
        self.assertEqual(images, {"a.png": "a.png", "b.png": "b.png", "c.png": "c.png", "a.jpg": "a_1.jpg"})
        self.assertEqual(captions, {"a.png": "a.txt", "b.png": "b.txt", "c.png": "c.txt", "a.jpg": "a_1.txt"})
        self.assertNotIn("concept_file_name", items[0])

    def test_an_empty_entry_and_an_absent_entry_are_told_apart(self):
        by_file = {i["file_name"]: i for i in self.inputs()["items"]}

        self.assertEqual(by_file["b.png"]["origin"], CAPTION_ORIGIN_ENTRY)
        self.assertEqual(by_file["c.png"]["origin"], CAPTION_ORIGIN_TRIGGER_WORD)
        self.assertNotEqual(by_file["b.png"]["text"], by_file["c.png"]["text"])

    # --- no divergence from what is really written ---------------------------------------------------------------

    def test_the_analyzed_texts_are_exactly_the_sidecars_materialize_concept_writes(self):
        inputs = self.inputs()
        dataset = self.character_manager.principal_character.datasets[0]

        concept = self.training_manager._materialize_concept(self.training_manager._find(self.training.training_id), dataset)

        for item in inputs["items"]:
            with self.subTest(file=item["file_name"]):
                sidecar = Path(concept) / item["concept_caption_file_name"]
                self.assertTrue((Path(concept) / item["concept_image_file_name"]).is_file())
                self.assertTrue(sidecar.is_file())
                self.assertEqual(sidecar.read_text(encoding="utf-8"), item["text"])
        # Every caption file really written is one that was announced, and the other way round.
        self.assertEqual(
            sorted(p.name for p in Path(concept).glob("*.txt")),
            sorted(i["concept_caption_file_name"] for i in inputs["items"]),
        )

    def test_the_reading_rule_matches_how_onetrainer_reads_the_written_sidecars(self):
        inputs = self.inputs()
        dataset = self.character_manager.principal_character.datasets[0]
        concept = self.training_manager._materialize_concept(self.training_manager._find(self.training.training_id), dataset)

        for item in inputs["items"]:
            with self.subTest(file=item["file_name"]):
                sidecar = Path(concept) / item["concept_caption_file_name"]
                # mgds LoadMultipleTexts: stripped lines, empty ones dropped, [""] when nothing is left.
                with open(sidecar, encoding="utf-8") as handle:
                    seen = [line.strip() for line in handle]
                seen = [line for line in seen if line != ""] or [""]
                self.assertEqual(caption_lines(item["text"]), seen)

    # --- strictly read-only ------------------------------------------------------------------------------------

    def test_reading_writes_nothing_publishes_nothing_and_creates_no_file(self):
        before = self.tree_state()
        saves = []
        published = []
        real_save = WorkspaceStorage.save

        def counting_save(root, data):
            saves.append(root)
            return real_save(root, data)

        with patch.object(WorkspaceStorage, "save", new=staticmethod(counting_save)), \
                patch.object(self.event_bus, "publish", side_effect=lambda *a, **k: published.append(a)):
            self.inputs()
            self.inputs()

        self.assertEqual(saves, [])
        self.assertEqual(published, [])
        self.assertEqual(self.tree_state(), before)
        self.assertFalse((self.folder / "training" / self.training.training_id / "concept").exists())

    # --- unresolved contexts -------------------------------------------------------------------------------------

    def test_an_unknown_training_gives_none(self):
        self.assertIsNone(self.training_manager.caption_analysis_inputs("unknown"))

    def test_a_dataset_that_no_longer_resolves_gives_none(self):
        self.training_manager._find(self.training.training_id).dataset_id = "gone"

        self.assertIsNone(self.inputs())

    def test_without_an_open_workspace_gives_none(self):
        self.workspace_manager.close()

        self.assertIsNone(self.inputs())

    # --- later changes are visible --------------------------------------------------------------------------------

    def test_a_later_caption_or_trigger_change_is_reflected_and_changes_the_fingerprint(self):
        def fingerprint():
            inputs = self.inputs()
            return fingerprint_caption_inputs(inputs["training_id"], inputs["architecture"], inputs["items"])

        first = fingerprint()
        self.assertEqual(first, fingerprint())

        self.dataset_manager.set_caption(self.by_name["c.png"].image_id, "enfin une légende")
        second = fingerprint()
        self.assertNotEqual(first, second)
        self.assertEqual({i["file_name"]: i["origin"] for i in self.inputs()["items"]}["c.png"], "entry")

        self.training_manager.update(trigger_word="autre mot")
        self.assertEqual(fingerprint(), second)            # c.png now has an entry: the trigger no longer matters

        self.dataset_manager.set_caption(self.by_name["b.png"].image_id, "x")
        self.assertNotEqual(fingerprint(), second)


if __name__ == "__main__":
    unittest.main()
