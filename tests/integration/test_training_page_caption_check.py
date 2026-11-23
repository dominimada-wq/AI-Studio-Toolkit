"""
"Vérifier les légendes" on the Training page and its result dialog: real
EventBus, Managers and widgets; the counting itself is replaced by a fake (the
real helper is never launched here). Covered: the interface stays responsive
while the analysis runs, a result is bound to its session and analyzed texts and
is dropped or labelled obsolete when they change, a partial failure never gives
a reassuring balance, the export, and the strictly read-only behaviour. Temporary
isolated projects, fictitious data only.
"""

import csv
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from src.core.event_bus import EventBus
from src.engines import caption_length_check as clc
from src.infrastructure.storage.caption_report_storage import CaptionReportStorageError
from src.infrastructure.storage.workspace_storage import WorkspaceStorage
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.managers.character_manager import (
    CHARACTER_CREATED,
    CHARACTER_DELETED,
    CHARACTER_SELECTED,
    CharacterManager,
)
from src.managers.dataset_manager import DatasetManager
from src.managers.training_manager import (
    TRAINING_CREATED,
    TRAINING_DELETED,
    TRAINING_SELECTED,
    TrainingManager,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.managers.workspace_manager import (
    WORKSPACE_CLOSED,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_RENAMED,
    WORKSPACE_SAVED,
    WorkspaceManager,
)
from src.ui.dialogs import caption_check_dialog as dialog_module
from src.ui.dialogs.caption_check_dialog import CaptionCheckDialog, source_text, summary_text
from src.ui.pages.training_page import TrainingPage

_app = QApplication.instance() or QApplication([])

TRIGGER = "Kaëlya woman"


def tokenizer_info(name):
    return clc.TokenizerInfo(
        name=name, repo_id="stabilityai/stable-diffusion-xl-base-1.0", subfolder=name,
        revision="462165984030d82259a11f4367a4eed129e94a7b", tokenizer_class="CLIPTokenizer",
        model_max_length=77, special_tokens_per_sequence=2, content_limit=75,
    )


def make_report(training_id, training_name, architecture, items, statuses, dataset_id="", onetrainer_path="",
                helper_messages=None):
    results = []
    for item, status in zip(items, statuses):
        count = clc.TokenizerItemCount(content_tokens=80 if status == clc.STATUS_TOO_LONG else 5,
                                       special_tokens=2, over_line_count=1 if status == clc.STATUS_TOO_LONG else 0,
                                       truncated_line_index=0 if status == clc.STATUS_TOO_LONG else None,
                                       truncated_text="la fin" if status == clc.STATUS_TOO_LONG else None)
        results.append(clc.CaptionItemResult(
            image_id=item["image_id"], file_name=item["file_name"], text=item["text"], origin=item["origin"],
            line_count=1, status=status, reason="tokenizer failed" if status == clc.STATUS_UNVERIFIABLE else "",
            counts=[count, count], concept_image_file_name=item["concept_image_file_name"],
            concept_caption_file_name=item["concept_caption_file_name"],
            usable_text=clc.has_usable_text(item["text"]),
        ))
    return clc.CaptionLengthReport(
        training_id=training_id, training_name=training_name, architecture=architecture,
        fingerprint=clc.fingerprint_caption_inputs(training_id, architecture, items, dataset_id, onetrainer_path),
        tokenizers=[tokenizer_info("tokenizer"), tokenizer_info("tokenizer_2")], items=results,
        helper_messages=list(helper_messages or []),
    )


class CaptionCheckPageTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.folder = self.tmp / "CaptionPageProject"

        self.unexpected_dialogs = []
        self.warnings = []
        self.infos = []
        self.criticals = []
        patches = [
            patch.object(QMessageBox, "warning", side_effect=lambda *a, **k: self.warnings.append(a)),
            patch.object(QMessageBox, "information", side_effect=lambda *a, **k: self.infos.append(a)),
            patch.object(QMessageBox, "critical", side_effect=lambda *a, **k: self.criticals.append(a)),
            patch.object(QMessageBox, "exec", new=lambda box, *a, **k: self.unexpected_dialogs.append(box)),
        ]
        for started in patches:
            started.start()
            self.addCleanup(started.stop)

        self.shown = []
        exec_patch = patch.object(
            CaptionCheckDialog, "exec", new=lambda dialog: self.shown.append(dialog) or 0
        )
        exec_patch.start()
        self.addCleanup(exec_patch.stop)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        self.training_manager = TrainingManager(self.character_manager, self.workspace_manager, event_bus=self.event_bus)
        self.settings_manager = ApplicationSettingsManager(storage_directory=self.tmp / "app_settings")
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        self.page = TrainingPage(
            self.training_manager, self.dataset_manager, self.workspace_manager,
            self.settings_manager, lora_library_manager,
        )
        self.addCleanup(self._delete_page)
        for event_name in (WORKSPACE_SAVED, WORKSPACE_RENAMED, CHARACTER_CREATED,
                           TRAINING_CREATED, TRAINING_SELECTED, TRAINING_DELETED):
            self.event_bus.subscribe(event_name, self.page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED, CHARACTER_SELECTED, CHARACTER_DELETED):
            self.event_bus.subscribe(event_name, self.page.reset_for_context_change)

        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)
        imports = self.tmp / "Imports"
        imports.mkdir()
        for name in ("a.png", "b.png"):
            (imports / name).write_bytes(b"fake-image-bytes")
        self.dataset_manager.add_images([str(imports / "a.png"), str(imports / "b.png")])
        self.images = {Path(image.file_path).name: image for image in self.dataset.images}
        self.dataset_manager.set_caption(self.images["a.png"].image_id, "Légende A, « élégante »\nligne 2")
        self.training_a = self.training_manager.create("Session A", self.dataset.dataset_id)
        self.training_b = self.training_manager.create("Session B", self.dataset.dataset_id)
        self.training_manager.select(self.training_a.training_id)
        self.training_manager.update(architecture="SDXL", trigger_word=TRIGGER)

        self.gate = None
        self.fake_calls = []
        self.fake_statuses = None
        self.fake_error = None

    def tearDown(self):
        self.assertEqual(self.unexpected_dialogs, [], "an unexpected dialog was opened")

    def _delete_page(self):
        try:
            self.page.deleteLater()
        except RuntimeError:
            pass   # a test already destroyed it

    # --- helpers ---------------------------------------------------------------------------------------------------

    def fake_check(self, **kwargs):
        self.fake_calls.append(kwargs)
        if self.gate is not None:
            self.gate.wait(10)
        if self.fake_error is not None:
            raise self.fake_error
        statuses = self.fake_statuses or [clc.STATUS_OK] * len(kwargs["items"])
        return make_report(kwargs["training_id"], kwargs["training_name"], kwargs["architecture"],
                           kwargs["items"], statuses, kwargs["dataset_id"], kwargs["onetrainer_path"])

    def start_check(self):
        with patch("src.ui.caption_check_worker.check_caption_lengths", side_effect=self.fake_check):
            self.page.check_captions()
        return self.page._caption_check_worker

    def wait_for_completion(self, timeout=8.0):
        deadline = time.time() + timeout
        while self.page._caption_check_worker is not None and time.time() < deadline:
            QTest.qWait(10)
        self.assertIsNone(self.page._caption_check_worker, "the analysis never finished")

    def run_check_to_completion(self):
        self.start_check()
        self.wait_for_completion()

    def project_bytes(self):
        return (self.folder / "project.json").read_bytes()

    # --- the button --------------------------------------------------------------------------------------------------

    def test_the_button_needs_a_selected_training_and_is_idle_by_default(self):
        self.assertEqual(self.page.check_captions_button.text(), "Vérifier les légendes")
        self.assertTrue(self.page.check_captions_button.isEnabled())      # a training is selected
        self.assertEqual(self.page.caption_check_label.text(), "")

        self.workspace_manager.close()                                    # nothing selected any more

        self.assertFalse(self.page.check_captions_button.isEnabled())
        self.assertEqual(self.page.check_captions_button.text(), "Vérifier les légendes")

    # --- responsiveness ----------------------------------------------------------------------------------------------

    def test_the_interface_stays_responsive_while_the_analysis_runs(self):
        self.gate = threading.Event()
        started = time.time()

        worker = self.start_check()

        self.assertLess(time.time() - started, 2.0)          # returned at once: not blocked on the analysis
        self.assertIsNotNone(worker)
        self.assertFalse(self.page.check_captions_button.isEnabled())
        self.assertIn("en cours", self.page.check_captions_button.text())
        self.assertIn("en cours", self.page.caption_check_label.text())
        QApplication.processEvents()                          # the event loop keeps running
        self.page.check_captions()                            # a second request is ignored
        self.gate.set()
        self.wait_for_completion()
        self.assertEqual(len(self.fake_calls), 1)
        self.assertTrue(self.page.check_captions_button.isEnabled())
        self.assertEqual(self.page.check_captions_button.text(), "Vérifier les légendes")

    def test_the_worker_receives_the_exact_texts_of_the_selected_session(self):
        self.run_check_to_completion()

        call = self.fake_calls[0]
        self.assertEqual(call["training_id"], self.training_a.training_id)
        self.assertEqual(call["architecture"], "SDXL")
        by_file = {item["file_name"]: item for item in call["items"]}
        self.assertEqual(by_file["a.png"]["text"], "Légende A, « élégante »\nligne 2")
        self.assertEqual((by_file["b.png"]["text"], by_file["b.png"]["origin"]), (TRIGGER, "trigger_word"))

    # --- the result ---------------------------------------------------------------------------------------------------

    def test_a_result_opens_the_dialog_and_the_page_describes_it_as_current(self):
        self.fake_statuses = [clc.STATUS_OK, clc.STATUS_TOO_LONG]

        self.run_check_to_completion()

        self.assertEqual(len(self.shown), 1)
        self.assertEqual(self.shown[0].report.training_id, self.training_a.training_id)
        label = self.page.caption_check_label.text()
        self.assertIn("Dernière vérification", label)
        self.assertIn("1 conforme(s) (longueur), 1 trop longue(s), 0 non vérifiable(s)", label)
        self.assertNotIn("obsolète", label)
        self.assertNotIn("aucune longueur excessive", label)

    def test_only_a_complete_all_conform_check_reassures(self):
        self.fake_statuses = [clc.STATUS_OK, clc.STATUS_OK]
        self.run_check_to_completion()
        self.assertIn("aucune longueur excessive", self.page.caption_check_label.text())
        self.assertIn("Aucune légende ne dépasse la limite", self.shown[-1].summary_label.text())

    def test_a_partial_failure_never_gives_a_reassuring_balance(self):
        self.fake_statuses = [clc.STATUS_OK, clc.STATUS_UNVERIFIABLE]

        self.run_check_to_completion()

        label = self.page.caption_check_label.text()
        self.assertIn("1 non vérifiable(s)", label)
        self.assertIn("bilan incomplet", label)
        summary = self.shown[0].summary_label.text()
        self.assertIn("Bilan INCOMPLET", summary)
        self.assertNotIn("Aucune légende ne dépasse la limite", summary)

    def test_an_unexpected_worker_failure_becomes_an_unverifiable_report(self):
        self.fake_error = RuntimeError("boom")

        self.run_check_to_completion()

        report = self.shown[0].report
        self.assertEqual({r.status for r in report.items}, {clc.STATUS_UNVERIFIABLE})
        self.assertIn("unexpected failure", report.reason)
        self.assertIn("Bilan INCOMPLET", self.shown[0].summary_label.text())

    def test_nothing_is_written_to_the_project_during_the_whole_flow(self):
        before = self.project_bytes()
        saves = []
        real_save = WorkspaceStorage.save

        def counting_save(root, data):
            saves.append(root)
            return real_save(root, data)

        with patch.object(WorkspaceStorage, "save", new=staticmethod(counting_save)):
            self.run_check_to_completion()

        self.assertEqual(saves, [])
        self.assertEqual(self.project_bytes(), before)

    # --- session and texts binding -------------------------------------------------------------------------------------

    def test_a_result_is_dropped_when_the_selected_session_changes_during_the_analysis(self):
        self.gate = threading.Event()
        worker = self.start_check()

        self.training_manager.select(self.training_b.training_id)

        # Abandoned at once: the worker is cancelled (its helper process would be killed) and the button is free.
        self.assertTrue(worker.cancelled)
        self.assertIsNone(self.page._caption_check_worker)
        self.assertIn("abandonnée", self.page.caption_check_label.text())
        self.gate.set()
        worker.join(5)
        QTest.qWait(50)
        self.assertEqual(self.shown, [])
        self.assertIsNone(self.page._last_caption_check)
        self.assertIn("abandonnée", self.page.caption_check_label.text())

    def test_a_result_is_dropped_when_a_caption_changes_during_the_analysis(self):
        self.gate = threading.Event()
        worker = self.start_check()

        self.dataset_manager.set_caption(self.images["b.png"].image_id, "modifiée pendant l'analyse")
        self.gate.set()
        worker.join(5)
        QTest.qWait(50)

        self.assertTrue(worker.cancelled)
        self.assertEqual(self.shown, [])
        self.assertIn("abandonnée", self.page.caption_check_label.text())

    def test_a_displayed_result_becomes_obsolete_when_a_caption_changes_afterwards(self):
        self.run_check_to_completion()
        dialog = self.shown[0]
        self.assertTrue(dialog.export_button.isEnabled())

        self.dataset_manager.set_caption(self.images["b.png"].image_id, "changée après l'analyse")
        self.page._refresh_caption_check_controls()

        self.assertIn("obsolète", self.page.caption_check_label.text())
        self.assertFalse(dialog.refresh_currentness())
        self.assertFalse(dialog.export_button.isEnabled())
        self.assertIn("n'est plus actuel", dialog.stale_label.text())

    def test_a_displayed_result_becomes_obsolete_when_another_session_is_selected(self):
        self.run_check_to_completion()

        self.training_manager.select(self.training_b.training_id)

        self.assertIn("obsolète", self.page.caption_check_label.text())

    def test_a_context_change_discards_the_result(self):
        self.run_check_to_completion()

        self.workspace_manager.close()

        self.assertIsNone(self.page._last_caption_check)
        self.assertEqual(self.page.caption_check_label.text(), "")

    # --- what makes a displayed result obsolete (and its export impossible as "current") -------------------------------

    def assert_obsolete_after(self, change):
        self.run_check_to_completion()
        dialog = self.shown[0]
        self.assertTrue(dialog.export_button.isEnabled())
        self.assertNotIn("obsolète", self.page.caption_check_label.text())

        change()
        self.page._refresh_caption_check_controls()

        self.assertIn("obsolète", self.page.caption_check_label.text())
        self.assertFalse(dialog.refresh_currentness())
        self.assertFalse(dialog.export_button.isEnabled())
        with patch.object(QFileDialog, "getSaveFileName") as chooser:
            dialog.export_csv()
        chooser.assert_not_called()

    def test_a_trigger_word_change_makes_the_result_obsolete_when_a_text_comes_from_it(self):
        # b.png has no entry: its text is the trigger word.
        self.assert_obsolete_after(lambda: self.training_manager.update(trigger_word="un autre mot"))

    def test_an_architecture_change_makes_the_result_obsolete(self):
        self.assert_obsolete_after(lambda: self.training_manager.update(architecture="SD15"))

    def test_a_dataset_content_change_makes_the_result_obsolete(self):
        def add_an_image():
            extra = self.tmp / "Imports" / "c.png"
            extra.write_bytes(b"fake-image-bytes")
            self.dataset_manager.select(self.dataset.dataset_id)
            self.dataset_manager.add_images([str(extra)])

        self.assert_obsolete_after(add_an_image)

    def test_pointing_the_training_to_another_dataset_makes_the_result_obsolete(self):
        def repoint():
            other = self.dataset_manager.create("Autres")
            self.training_manager._find(self.training_a.training_id).dataset_id = other.dataset_id

        self.assert_obsolete_after(repoint)

    def test_a_change_of_the_onetrainer_installation_makes_the_result_obsolete(self):
        self.assert_obsolete_after(lambda: setattr(self.settings_manager.settings, "onetrainer_path", "J:/ailleurs"))

    # --- context safety: no result applied to the wrong context, no destroyed object touched ---------------------------

    def test_closing_the_project_while_the_analysis_runs_stops_it_and_applies_nothing(self):
        self.gate = threading.Event()
        worker = self.start_check()

        self.workspace_manager.close()

        self.assertTrue(worker.cancelled)
        self.assertIsNone(self.page._caption_check_worker)
        self.gate.set()
        worker.join(5)
        QTest.qWait(50)
        self.assertEqual(self.shown, [])
        self.assertIsNone(self.page._last_caption_check)
        self.assertEqual(self.page.caption_check_label.text(), "")

    def test_destroying_the_page_while_the_analysis_runs_cancels_it_without_any_error(self):
        self.gate = threading.Event()
        worker = self.start_check()
        thread_errors = []

        with patch.object(threading, "excepthook", side_effect=lambda args: thread_errors.append(args)):
            self.page.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            QApplication.processEvents()
            self.assertTrue(worker.cancelled)           # the destruction stopped the analysis
            self.gate.set()
            worker.join(5)
            QTest.qWait(50)

        self.assertEqual(thread_errors, [])
        self.assertEqual(self.shown, [])

    def test_the_late_result_of_an_abandoned_analysis_is_ignored(self):
        self.gate = threading.Event()
        first = self.start_check()
        old_serial = first.serial
        old_report = make_report(self.training_a.training_id, "Session A", "SDXL", [], [])
        self.page._abandon_caption_check("")
        second = self.start_check()
        self.assertIsNotNone(second)

        self.page._on_caption_check_finished(old_serial, old_report)   # a result that arrives late

        self.assertEqual(self.shown, [])
        self.assertIs(self.page._caption_check_worker, second)          # the new analysis is untouched
        self.assertIsNone(self.page._last_caption_check)
        self.gate.set()
        self.wait_for_completion()
        self.assertEqual(len(self.shown), 1)
        self.assertEqual(self.shown[0].report.training_id, self.training_a.training_id)

    # --- impossible checks, with the real engine (nothing is launched) -------------------------------------------------

    def test_a_non_sdxl_session_gives_an_unverifiable_report_without_any_helper(self):
        self.training_manager.update(architecture="SD15")

        self.page.check_captions()
        self.wait_for_completion()

        report = self.shown[0].report
        self.assertEqual({r.status for r in report.items}, {clc.STATUS_UNVERIFIABLE})
        self.assertIn("not supported", report.reason)
        summary = self.shown[0].summary_label.text()
        self.assertIn("Bilan INCOMPLET", summary)
        self.assertNotIn("Aucune légende ne dépasse la limite", summary)

    def test_an_unconfigured_onetrainer_gives_an_unverifiable_report(self):
        self.assertEqual(self.settings_manager.settings.onetrainer_path, "")

        self.page.check_captions()
        self.wait_for_completion()

        report = self.shown[0].report
        self.assertEqual({r.status for r in report.items}, {clc.STATUS_UNVERIFIABLE})
        self.assertIn("OneTrainer is not usable", report.reason)

    def test_an_unresolvable_dataset_warns_and_starts_nothing(self):
        self.training_manager._find(self.training_a.training_id).dataset_id = "gone"

        self.page.check_captions()

        self.assertEqual(len(self.warnings), 1)
        self.assertIsNone(self.page._caption_check_worker)
        self.assertEqual(self.shown, [])


class CaptionCheckDialogTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.infos = []
        self.criticals = []
        for started in (
            patch.object(QMessageBox, "information", side_effect=lambda *a, **k: self.infos.append(a)),
            patch.object(QMessageBox, "critical", side_effect=lambda *a, **k: self.criticals.append(a)),
        ):
            started.start()
            self.addCleanup(started.stop)
        self.items = [
            {"image_id": "i1", "file_name": "a.png", "concept_image_file_name": "a.png",
             "concept_caption_file_name": "a.txt",
             "text": 'Kaëlya "woman", crème\nligne 2 « x »', "origin": "entry"},
            {"image_id": "i2", "file_name": "b.png", "concept_image_file_name": "b.png",
             "concept_caption_file_name": "b.txt", "text": "", "origin": "entry"},
            {"image_id": "i3", "file_name": "c.png", "concept_image_file_name": "c.png",
             "concept_caption_file_name": "c.txt", "text": TRIGGER,
             "origin": "trigger_word"},
        ]

    def report(self, statuses):
        return make_report("t1", "Session 1", "SDXL", self.items, statuses)

    def test_summary_separates_the_three_statuses_and_only_complete_conform_reassures(self):
        conform = summary_text(self.report([clc.STATUS_OK] * 3))
        self.assertIn("Conformes (longueur) : 3 — Trop longues : 0 — Non vérifiables : 0", conform)
        self.assertIn("Aucune légende ne dépasse la limite de 75 jetons de contenu par ligne", conform)
        self.assertIn("seulement : aucune longueur excessive", conform)

        mixed = summary_text(self.report([clc.STATUS_OK, clc.STATUS_TOO_LONG, clc.STATUS_UNVERIFIABLE]))
        self.assertIn("Conformes (longueur) : 1 — Trop longues : 1 — Non vérifiables : 1", mixed)
        self.assertIn("seront tronquées", mixed)
        self.assertIn("Bilan INCOMPLET", mixed)
        self.assertNotIn("Aucune légende ne dépasse la limite", mixed)

        too_long_only = summary_text(self.report([clc.STATUS_OK, clc.STATUS_TOO_LONG, clc.STATUS_OK]))
        self.assertNotIn("INCOMPLET", too_long_only)
        self.assertNotIn("Aucune légende ne dépasse la limite", too_long_only)

    def test_an_empty_dataset_is_not_reassuring(self):
        empty = clc.CaptionLengthReport("t1", "Session 1", "SDXL", "fp", [], [])

        text = summary_text(empty)

        self.assertIn("rien à vérifier", text)
        self.assertNotIn("Aucune légende ne dépasse la limite", text)

    def test_the_source_of_the_tokenizers_and_the_limit_are_shown(self):
        text = source_text(self.report([clc.STATUS_OK] * 3))

        self.assertIn("stabilityai/stable-diffusion-xl-base-1.0@462165984030/tokenizer", text)
        self.assertIn("75 jetons de contenu", text)
        self.assertIn("77 positions moins 2 jetons spéciaux", text)
        self.assertEqual(source_text(clc.CaptionLengthReport("t", "n", "SDXL", "fp", [], [])), "Tokenizers : non disponibles.")

    def test_empty_texts_are_flagged_and_never_replaced_by_the_trigger_word(self):
        self.items[1]["text"] = " \n "
        report = self.report([clc.STATUS_OK] * 3)

        summary = summary_text(report)
        dialog = CaptionCheckDialog(report)
        self.addCleanup(dialog.deleteLater)

        self.assertIn("1 légende(s) sans aucun texte exploitable", summary)
        self.assertIn("le mot déclencheur ne les remplace pas", summary)
        self.assertEqual(dialog.table.item(1, 1).text(), "Conforme (longueur) — texte vide")
        self.assertEqual(dialog.table.item(0, 1).text(), "Conforme (longueur)")

    def test_the_helper_messages_are_shown_when_there_are_some_and_hidden_otherwise(self):
        with_messages = make_report("t1", "Session 1", "SDXL", self.items, [clc.STATUS_OK] * 3,
                                    helper_messages=["Some real warning", "Another one"])
        dialog = CaptionCheckDialog(with_messages)
        self.addCleanup(dialog.deleteLater)
        quiet = CaptionCheckDialog(self.report([clc.STATUS_OK] * 3))
        self.addCleanup(quiet.deleteLater)

        self.assertTrue(dialog.messages_label.isVisibleTo(dialog))
        self.assertIn("Some real warning", dialog.messages_label.text())
        self.assertIn("Another one", dialog.messages_label.text())
        self.assertFalse(quiet.messages_label.isVisibleTo(quiet))

    def test_the_line_number_and_the_counts_of_each_tokenizer_are_shown_for_a_multi_line_caption(self):
        count_1 = clc.TokenizerItemCount(content_tokens=80, special_tokens=2, longest_line_index=1, over_line_count=1,
                                         truncated_line_index=1, truncated_text="la fin")
        count_2 = clc.TokenizerItemCount(content_tokens=78, special_tokens=2, longest_line_index=1, over_line_count=1,
                                         truncated_line_index=1, truncated_text="la fin")
        report = clc.CaptionLengthReport(
            "t1", "Session 1", "SDXL", "fp", [tokenizer_info("tokenizer"), tokenizer_info("tokenizer_2")],
            [clc.CaptionItemResult("i1", "a.png", "x\ny", "entry", 2, clc.STATUS_TOO_LONG, "", [count_1, count_2])],
        )
        dialog = CaptionCheckDialog(report)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.table.item(0, 3).text(), "80 (ligne 2)")
        self.assertEqual(dialog.table.item(0, 4).text(), "78 (ligne 2)")
        self.assertEqual(dialog.table.item(0, 6).text(), "2")
        self.assertEqual(dialog.table.item(0, 7).text(), "la fin")

    def test_the_dialog_states_that_the_truncated_part_is_reconstructed_by_decoding(self):
        dialog = CaptionCheckDialog(self.report([clc.STATUS_OK, clc.STATUS_TOO_LONG, clc.STATUS_OK]))
        self.addCleanup(dialog.deleteLater)

        self.assertIn("reconstruite par décodage des jetons", dialog.method_label.text())
        self.assertEqual(dialog.table.rowCount(), 3)
        self.assertEqual(dialog.table.item(1, 6).text(), "1")          # number of the truncated line
        self.assertEqual(dialog.table.item(1, 7).text(), "la fin")
        self.assertEqual(dialog.table.item(1, 1).text(), "Trop longue")
        self.assertIn("Mot déclencheur", dialog.table.item(2, 2).text())

    def test_export_writes_every_image_with_exact_text_origin_counts_limits_and_status(self):
        report = self.report([clc.STATUS_OK, clc.STATUS_TOO_LONG, clc.STATUS_UNVERIFIABLE])
        dialog = CaptionCheckDialog(report)
        self.addCleanup(dialog.deleteLater)
        target = self.tmp / "legendes.csv"

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "")):
            dialog.export_csv()

        with open(target, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(tuple(rows[0].keys()), clc.REPORT_COLUMNS)
        self.assertEqual([r["image_id"] for r in rows], ["i1", "i2", "i3"])
        self.assertEqual([r["file_name"] for r in rows], ["a.png", "b.png", "c.png"])
        self.assertEqual([r["concept_image_file_name"] for r in rows], ["a.png", "b.png", "c.png"])
        self.assertEqual([r["concept_caption_file_name"] for r in rows], ["a.txt", "b.txt", "c.txt"])
        self.assertNotIn("concept_file_name", rows[0])
        self.assertEqual(rows[0]["analyzed_text"], 'Kaëlya "woman", crème\nligne 2 « x »')   # exact text kept
        self.assertEqual(rows[1]["analyzed_text"], "")
        self.assertEqual([r["text_origin"] for r in rows], ["entry", "entry", "trigger_word"])
        self.assertEqual([r["status"] for r in rows], ["ok", "too_long", "unverifiable"])
        self.assertEqual(rows[1]["tokenizer_1_content_tokens"], "80")
        self.assertEqual(rows[1]["tokenizer_2_content_tokens"], "80")
        self.assertEqual((rows[0]["content_limit"], rows[0]["max_length"]), ("75", "77"))
        self.assertEqual(rows[2]["status_reason"], "tokenizer failed")
        self.assertEqual(len(self.infos), 1)

    def test_a_cancelled_file_dialog_writes_nothing(self):
        dialog = CaptionCheckDialog(self.report([clc.STATUS_OK] * 3))
        self.addCleanup(dialog.deleteLater)

        with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
            dialog.export_csv()

        self.assertEqual(list(self.tmp.iterdir()), [])
        self.assertEqual(self.infos, [])

    def test_a_write_failure_is_reported_and_not_announced_as_done(self):
        dialog = CaptionCheckDialog(self.report([clc.STATUS_OK] * 3))
        self.addCleanup(dialog.deleteLater)

        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(self.tmp / "x.csv"), "")), \
                patch.object(dialog_module.CaptionReportStorage, "write",
                             side_effect=CaptionReportStorageError("disk full")):
            dialog.export_csv()

        self.assertEqual(len(self.criticals), 1)
        self.assertEqual(self.infos, [])

    def test_a_stale_result_cannot_be_exported(self):
        current = {"value": True}
        dialog = CaptionCheckDialog(self.report([clc.STATUS_OK] * 3), is_current=lambda: current["value"])
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.export_button.isEnabled())

        current["value"] = False
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(self.tmp / "x.csv"), "")) as chooser:
            dialog.export_csv()

        chooser.assert_not_called()
        self.assertFalse(dialog.export_button.isEnabled())
        self.assertNotEqual(dialog.stale_label.text(), "")
        self.assertEqual(list(self.tmp.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
