"""
Real-widget coverage for the "Ordre d'ajout (derniers ajouts d'abord)" sort
criterion of ImagesPage (Workspace.images) and DatasetsPage (the active
Dataset's own images).

The criterion is a Presentation-layer ordering only: it shows the recorded
list REVERSED (a batch [x, y, z] is shown z, y, x). It is neither a creation
date nor a guaranteed history -- the recorded list is whatever the Domain
and project.json hold, in the order the Managers appended to it. Nothing
here asserts anything about the order in which a file dialog or
QListWidget.selectedItems() hands paths over: every test that needs a batch
supplies the exact list of paths itself.

Both pages are covered by ONE set of cases (_AddedOrderCases), run by a
concrete TestCase per page, so their behaviours cannot silently diverge;
GalleryCriterionParityTest additionally compares the two combos directly.

Real temporary files, a real offscreen QApplication, the real Managers and
EventBus; no engine, no network, no test double of the code under test (only
the file dialog / message boxes of the import flows are patched, exactly as
the existing page tests do).
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog

from src.core.event_bus import EventBus
from src.managers.character_manager import (
    CharacterManager,
    CHARACTER_CREATED,
    CHARACTER_SELECTED,
    CHARACTER_DELETED,
)
from src.managers.dataset_manager import (
    DatasetManager,
    DATASET_CREATED,
    DATASET_SELECTED,
    DATASET_DELETED,
)
from src.managers.workspace_lifecycle import create_workspace_with_default_character
from src.managers.workspace_manager import (
    WorkspaceManager,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
    WORKSPACE_RENAMED,
)
from src.ui.pages.datasets_page import DatasetsPage
from src.ui.pages.images_page import ImagesPage
from tests.integration._qt_dialog_safety_net import start_dialog_guard, stop_dialog_guard

_app = QApplication.instance() or QApplication([])

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED, WORKSPACE_RENAMED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
DATASET_EVENTS = (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED)

NAME_LABEL = "Nom (A → Z)"
DATE_LABEL = "Date du fichier (plus récent d'abord)"
ADDED_LABEL = "Ordre d'ajout (derniers ajouts d'abord)"
ADDED_TOOLTIP = (
    "Affiche les images dans l'ordre inverse de la liste enregistrée, "
    "sans utiliser la date des fichiers."
)
EXPECTED_CRITERIA = [(NAME_LABEL, "name"), (DATE_LABEL, "date"), (ADDED_LABEL, "added")]

# File names with no relation to the order in which they are added
# (hexadecimal, like the names of accepted generated images).
UUID_LIKE_NAMES = (
    "f3e1c7a09b2d4e5f8a6b1c3d5e7f9a0b.png",
    "a1b2c3d4e5f60718293a4b5c6d7e8f90.png",
    "c9d0e1f2a3b4c5d6e7f8091a2b3c4d5e.png",
)


def _make_png(path: str, width: int = 4, height: int = 4) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill()
    assert pixmap.save(path, "PNG")


def _combo_entries(page):
    combo = page.sort_combo
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


class _AddedOrderCases:
    """
    The cases shared by both pages. A concrete subclass is also a TestCase
    and provides the page-specific hooks (see ImagesPageAddedOrderTest and
    DatasetsPageAddedOrderTest). Every case that depends on the new
    criterion starts with _require_added() / _use("added"): the failure of
    that first assertion is the whole outcome on a code base that does not
    have the criterion.
    """

    # --- page-independent helpers -------------------------------------

    def _base_setup(self, project_name):
        # The guard turns an unexpected real QMessageBox into a clean
        # failure instead of a wait for a human click.
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.sources_dir = Path(self.tmp_dir) / "sources"
        self.sources_dir.mkdir()
        self.folder = Path(self.tmp_dir) / project_name

    def _require_added(self):
        self.assertGreaterEqual(
            self.page.sort_combo.findData("added"), 0,
            "criterion 'added' is absent from the sort combo",
        )

    def _use(self, criterion):
        index = self.page.sort_combo.findData(criterion)
        self.assertGreaterEqual(index, 0, f"criterion {criterion!r} is absent from the sort combo")
        self.page.sort_combo.setCurrentIndex(index)

    def source(self, name):
        path = str(self.sources_dir / name)
        _make_png(path)
        return path

    def shown_paths(self):
        return [self.view.item(i).data(Qt.UserRole) for i in range(self.view.count())]

    def shown_names(self):
        return [self.view.item(i).text() for i in range(self.view.count())]

    def recorded_paths(self):
        return [image.file_path for image in self.pool()]

    def recorded_names(self):
        return [Path(path).name for path in self.recorded_paths()]

    def add_one(self, name):
        result = self.add([self.source(name)])
        self.assertEqual(result.added, 1)
        return self.recorded_paths()[-1]

    def select_items(self, *paths, current=None):
        # The current item first (setCurrentItem() replaces the selection),
        # the others afterwards: independent of the display order.
        if current is not None:
            for i in range(self.view.count()):
                if self.view.item(i).data(Qt.UserRole) == current:
                    self.view.setCurrentItem(self.view.item(i))
        for i in range(self.view.count()):
            item = self.view.item(i)
            if item.data(Qt.UserRole) in paths:
                item.setSelected(True)

    def selected_paths(self):
        return {item.data(Qt.UserRole) for item in self.view.selectedItems()}

    def current_path(self):
        item = self.view.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def project_json(self):
        return json.loads((self.folder / "project.json").read_text(encoding="utf-8"))

    @staticmethod
    def entry_path(entry):
        return entry["file_path"] if isinstance(entry, dict) else entry

    # --- cases ---------------------------------------------------------

    def test_default_criterion_is_the_third_item_and_is_selected(self):
        self._require_added()
        self.assertEqual(_combo_entries(self.page), EXPECTED_CRITERIA)
        self.assertEqual(self.page.sort_combo.currentIndex(), 2)
        self.assertEqual(self.page.sort_combo.currentData(), "added")

    def test_the_new_criterion_has_the_agreed_tooltip(self):
        self._require_added()
        index = self.page.sort_combo.findData("added")
        self.assertEqual(self.page.sort_combo.itemData(index, Qt.ToolTipRole), ADDED_TOOLTIP)

    def test_uuid_like_names_unrelated_to_the_recorded_order(self):
        self._require_added()
        for name in UUID_LIKE_NAMES:
            self.add_one(name)

        self.assertEqual(self.recorded_names(), list(UUID_LIKE_NAMES))
        self.assertEqual(self.shown_names(), list(reversed(UUID_LIKE_NAMES)))
        self.assertNotEqual(self.shown_names(), sorted(UUID_LIKE_NAMES))
        self._use("name")
        self.assertEqual(self.shown_names(), sorted(UUID_LIKE_NAMES))
        self.assertEqual(self.recorded_names(), list(UUID_LIKE_NAMES))

    def test_file_dates_differing_from_the_recorded_order(self):
        self._require_added()
        first = self.add_one("first.png")
        second = self.add_one("second.png")
        third = self.add_one("third.png")
        # The first recorded file is the most recent one on disk.
        os.utime(first, (3000, 3000))
        os.utime(second, (2000, 2000))
        os.utime(third, (1000, 1000))

        self._use("added")
        self.assertEqual(self.shown_paths(), [third, second, first])
        self._use("date")
        self.assertEqual(self.shown_paths(), [first, second, third])
        self._use("added")
        self.assertEqual(self.shown_paths(), [third, second, first])

    def test_multiple_add_shows_the_reverse_of_the_recorded_list(self):
        self._require_added()
        self.add_one("old.png")
        batch = [self.source("m_batch.png"), self.source("b_batch.png"), self.source("z_batch.png")]

        result = self.add(batch)

        self.assertEqual(result.added, 3)
        self.assertEqual(self.recorded_names(), ["old.png", "m_batch.png", "b_batch.png", "z_batch.png"])
        self.assertEqual(self.shown_names(), ["z_batch.png", "b_batch.png", "m_batch.png", "old.png"])

    def test_batch_with_duplicate_and_failed_entries_keeps_the_order_of_the_others(self):
        self._require_added()
        self.add_one("x.png")
        p1 = self.source("p1.png")
        p2 = self.source("p2.png")
        missing = str(self.sources_dir / "does_not_exist.png")

        result = self.add([p1, p1, missing, p2])

        self.assertEqual(result.added, 2)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(self.recorded_names(), ["x.png", "p1.png", "p2.png"])
        self.assertEqual(self.shown_names(), ["p2.png", "p1.png", "x.png"])

    def test_page_import_flow_keeps_the_provided_order(self):
        self._require_added()
        files = [self.source("c.png"), self.source("a.png"), self.source("b.png")]

        self.import_via_page(files)

        self.assertEqual(self.recorded_names(), ["c.png", "a.png", "b.png"])
        self.assertEqual(self.shown_names(), ["b.png", "a.png", "c.png"])

    def test_an_already_present_image_keeps_its_position(self):
        self._require_added()
        first = self.add_one("first.png")
        self.add_one("second.png")
        self.add_one("third.png")

        result = self.add([first])

        self.assertEqual(result.added, 0)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(self.recorded_names(), ["first.png", "second.png", "third.png"])
        self.assertEqual(self.shown_names(), ["third.png", "second.png", "first.png"])

    def test_removed_then_added_again_comes_first(self):
        self._require_added()
        self.add_one("a.png")
        second = self.add_one("b.png")
        self.add_one("c.png")

        self.remove([second])
        self.assertEqual(self.shown_names(), ["c.png", "a.png"])

        result = self.add([second])

        self.assertEqual(result.added, 1)
        self.assertEqual(self.recorded_names(), ["a.png", "c.png", "b.png"])
        self.assertEqual(self.shown_names(), ["b.png", "c.png", "a.png"])

    def test_removal_keeps_the_relative_order_of_the_others(self):
        self._require_added()
        for name in ("a.png", "b.png", "c.png", "d.png"):
            self.add_one(name)
        third = self.recorded_paths()[2]

        self.remove([third])

        self.assertEqual(self.recorded_names(), ["a.png", "b.png", "d.png"])
        self.assertEqual(self.shown_names(), ["d.png", "b.png", "a.png"])

    def test_switching_criteria_and_back_never_changes_the_recorded_list(self):
        self._require_added()
        names = ("pear.png", "Apple.png", "mango.png")
        paths = [self.add_one(name) for name in names]
        for path, stamp in zip(paths, (2000, 3000, 1000)):
            os.utime(path, (stamp, stamp))
        recorded_before = list(self.recorded_paths())
        ids_before = [image.image_id for image in self.pool()]

        sequence = []
        for criterion in ("name", "date", "added", "name", "added", "date", "added"):
            self._use(criterion)
            sequence.append((criterion, self.shown_names()))

        expected = {
            "name": ["Apple.png", "mango.png", "pear.png"],
            "date": ["Apple.png", "pear.png", "mango.png"],
            "added": ["mango.png", "Apple.png", "pear.png"],
        }
        for criterion, shown in sequence:
            self.assertEqual(shown, expected[criterion], criterion)
        self.assertEqual(self.recorded_paths(), recorded_before)
        self.assertEqual([image.image_id for image in self.pool()], ids_before)

    def test_unrelated_refresh_keeps_criterion_and_order(self):
        self._require_added()
        for name in ("a.png", "b.png", "c.png"):
            self.add_one(name)
        before = self.shown_paths()

        self.workspace_manager.save()
        self.assertEqual(self.page.sort_combo.currentData(), "added")
        self.assertEqual(self.shown_paths(), before)

        self.refresh_directly()
        self.assertEqual(self.page.sort_combo.currentData(), "added")
        self.assertEqual(self.shown_paths(), before)

    def test_project_rename_keeps_the_order(self):
        self._require_added()
        for name in ("a.png", "b.png", "c.png"):
            self.add_one(name)

        self.assertTrue(self.workspace_manager.rename("RenamedProject"))
        self.folder = Path(self.tmp_dir) / "RenamedProject"

        self.assertEqual(self.page.sort_combo.currentData(), "added")
        self.assertEqual(self.recorded_names(), ["a.png", "b.png", "c.png"])
        self.assertEqual(self.shown_names(), ["c.png", "b.png", "a.png"])
        for path in self.shown_paths():
            self.assertTrue(Path(path).exists(), path)

    def test_reload_keeps_the_recorded_order_and_a_new_page_starts_on_added(self):
        self._require_added()
        for name in ("pear.png", "Apple.png", "mango.png"):
            self.add_one(name)
        self._use("name")
        self.workspace_manager.save()
        persisted_before = [Path(self.entry_path(entry)).name for entry in self.persisted_pool()]
        self.assertEqual(persisted_before, ["pear.png", "Apple.png", "mango.png"])

        self.reload()

        # A new page instance: no preference is persisted, so it starts on
        # the default criterion again.
        self.assertEqual(self.page.sort_combo.currentData(), "added")
        self.assertEqual(self.recorded_names(), ["pear.png", "Apple.png", "mango.png"])
        self.assertEqual(self.shown_names(), ["mango.png", "Apple.png", "pear.png"])
        self.assertEqual(
            [Path(self.entry_path(entry)).name for entry in self.persisted_pool()],
            persisted_before,
        )

    def test_legacy_string_entries_follow_the_stored_order(self):
        self._require_added()
        paths = [self.add_one(name) for name in ("one.png", "two.png", "three.png")]
        self.workspace_manager.save()
        self.rewrite_pool_as_strings(paths)

        self.reload()

        self.assertEqual(self.recorded_paths(), paths)
        self.assertEqual(self.shown_paths(), list(reversed(paths)))

    def test_selection_and_current_item_survive_addition_and_criterion_change(self):
        self._require_added()
        a = self.add_one("a.png")
        self.add_one("b.png")
        c = self.add_one("c.png")
        self.select_items(a, c, current=c)
        self.assertEqual(self.selected_paths(), {a, c})
        self.assertEqual(self.current_path(), c)

        d = self.add_one("d.png")

        self.assertEqual(self.selected_paths(), {a, c})
        self.assertNotIn(d, self.selected_paths())
        self.assertEqual(self.current_path(), c)
        self._use("name")
        self.assertEqual(self.selected_paths(), {a, c})
        self.assertEqual(self.current_path(), c)
        self._use("added")
        self.assertEqual(self.selected_paths(), {a, c})
        self.assertEqual(self.current_path(), c)
        self.assertEqual(self.shown_paths()[0], d)

    def test_criterion_change_alone_never_writes_or_publishes(self):
        self._require_added()
        for name in ("a.png", "b.png", "c.png"):
            self.add_one(name)
        pool_before = self.pool()
        snapshot_before = [(image.image_id, image.file_path) for image in pool_before]
        project = self.folder / "project.json"
        bytes_before = project.read_bytes()
        mtime_before = project.stat().st_mtime_ns
        published = []

        def recorder(event_name):
            def record(payload=None):
                published.append(event_name)
            return record

        for event_name in WORKSPACE_EVENTS:
            self.event_bus.subscribe(event_name, recorder(event_name))

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            for criterion in ("name", "date", "added", "date", "name", "added"):
                self._use(criterion)
            save_spy.assert_not_called()

        self.assertEqual(published, [])
        self.assertIs(self.pool(), pool_before)
        self.assertEqual([(image.image_id, image.file_path) for image in self.pool()], snapshot_before)
        self.assertEqual(project.read_bytes(), bytes_before)
        self.assertEqual(project.stat().st_mtime_ns, mtime_before)

    def test_empty_and_single_item_galleries(self):
        self._require_added()
        for criterion in ("name", "date", "added"):
            self._use(criterion)
            self.assertEqual(self.view.count(), 0, criterion)

        only = self.add_one("only.png")

        for criterion in ("name", "date", "added"):
            self._use(criterion)
            self.assertEqual(self.shown_paths(), [only], criterion)

    def test_items_keep_text_tooltip_and_identity_under_every_criterion(self):
        self._require_added()
        paths = [self.add_one(name) for name in ("b.png", "a.png", "c.png")]

        for criterion in ("name", "date", "added"):
            self._use(criterion)
            self.assertEqual(sorted(self.shown_paths()), sorted(paths), criterion)
            for i in range(self.view.count()):
                item = self.view.item(i)
                self.assertEqual(item.text(), Path(item.data(Qt.UserRole)).name, criterion)
                self.assertEqual(item.toolTip(), item.data(Qt.UserRole), criterion)

    def test_name_and_date_criteria_are_unchanged(self):
        # Does not depend on the new criterion: the two existing ones keep
        # their documented behaviour (case-insensitive name, most recent
        # modification time first).
        banana = self.add_one("Banana.png")
        apple = self.add_one("apple.png")
        cherry = self.add_one("Cherry.png")
        for path, stamp in ((banana, 3000), (apple, 1000), (cherry, 2000)):
            os.utime(path, (stamp, stamp))

        self._use("name")
        self.assertEqual(self.shown_names(), ["apple.png", "Banana.png", "Cherry.png"])
        self._use("date")
        self.assertEqual(self.shown_names(), ["Banana.png", "Cherry.png", "apple.png"])


class ImagesPageAddedOrderTest(_AddedOrderCases, unittest.TestCase):

    def setUp(self):
        self._base_setup("ImagesAddedOrderProject")
        self._build_stack()
        self.workspace_manager.create(self.folder)

    def _build_stack(self):
        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.page = ImagesPage(self.workspace_manager)
        for event_name in WORKSPACE_EVENTS:
            self.event_bus.subscribe(event_name, self.page.update_images)

    # --- hooks ---------------------------------------------------------

    @property
    def view(self):
        return self.page.list_widget

    def pool(self):
        return self.workspace_manager.current_workspace.images

    def add(self, paths):
        return self.workspace_manager.add_images(paths)

    def remove(self, paths):
        return self.workspace_manager.remove_images(paths)

    def persisted_pool(self):
        return self.project_json()["images"]

    def rewrite_pool_as_strings(self, paths):
        data = self.project_json()
        data["images"] = list(paths)
        (self.folder / "project.json").write_text(json.dumps(data), encoding="utf-8")

    def reload(self):
        self.workspace_manager.close()
        self._build_stack()
        self.workspace_manager.open(self.folder)

    def refresh_directly(self):
        self.page.update_images(self.workspace_manager.current_workspace.to_dict())

    def import_via_page(self, files):
        with patch("src.ui.pages.images_page.QFileDialog.getOpenFileNames", return_value=(files, "")), \
                patch("src.ui.pages.images_page.QMessageBox.information"):
            self.page.import_images()


class DatasetsPageAddedOrderTest(_AddedOrderCases, unittest.TestCase):

    def setUp(self):
        self._base_setup("DatasetsAddedOrderProject")
        self._build_stack()
        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(self.dataset.dataset_id)
        self.dataset_id = self.dataset.dataset_id

    def _build_stack(self):
        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.page = DatasetsPage(self.dataset_manager, self.workspace_manager)
        for event_name in WORKSPACE_EVENTS + CHARACTER_EVENTS + DATASET_EVENTS:
            self.event_bus.subscribe(event_name, self.page.update_datasets)

    # --- hooks ---------------------------------------------------------

    @property
    def view(self):
        return self.page.images_list

    def pool(self):
        return self.dataset_manager.active_dataset.images

    def add(self, paths):
        return self.dataset_manager.add_images(paths)

    def remove(self, paths):
        return self.dataset_manager.remove_images(paths)

    def _persisted_dataset(self, data):
        for character in data["characters"]:
            for dataset in character["datasets"]:
                if dataset["dataset_id"] == self.dataset_id:
                    return dataset
        self.fail("the dataset is not in project.json")

    def persisted_pool(self):
        return self._persisted_dataset(self.project_json())["images"]

    def rewrite_pool_as_strings(self, paths):
        data = self.project_json()
        self._persisted_dataset(data)["images"] = list(paths)
        (self.folder / "project.json").write_text(json.dumps(data), encoding="utf-8")

    def reload(self):
        self.workspace_manager.close()
        self._build_stack()
        self.workspace_manager.open(self.folder)
        self.dataset_manager.select(self.dataset_id)

    def refresh_directly(self):
        self.page.update_datasets()

    def import_via_page(self, files):
        with patch("src.ui.pages.datasets_page.QFileDialog.getOpenFileNames", return_value=(files, "")), \
                patch("src.ui.pages.datasets_page.QMessageBox.information"):
            self.page.import_images()

    # --- cases specific to the Dataset pool ----------------------------

    def test_add_from_gallery_uses_the_dataset_own_order_not_the_gallery_order(self):
        self._require_added()
        gallery = []
        for name in ("g1.png", "g2.png", "g3.png"):
            self.workspace_manager.add_images([self.source(name)])
            gallery.append(self.workspace_manager.current_workspace.images[-1].file_path)

        with patch("src.ui.pages.datasets_page.SelectImagesDialog") as dialog_cls, \
                patch("src.ui.pages.datasets_page.QMessageBox"):
            dialog_cls.return_value.exec.return_value = QDialog.Accepted
            dialog_cls.return_value.selected_paths.return_value = [gallery[2], gallery[0]]
            self.page.add_images_from_gallery()

        # Known limit (not changed by this criterion): the picker lists the
        # gallery in the Domain order, oldest first.
        self.assertEqual(dialog_cls.call_args[0][0], gallery)
        self.assertEqual(self.recorded_paths(), [gallery[2], gallery[0]])
        self.assertEqual(self.shown_paths(), [gallery[0], gallery[2]])

    def test_each_dataset_has_its_own_order_and_the_criterion_is_kept_when_switching(self):
        self._require_added()
        for name in ("a1.png", "a2.png"):
            self.add_one(name)
        other = self.dataset_manager.create("Landscapes")
        self.dataset_manager.select(other.dataset_id)
        for name in ("b1.png", "b2.png", "b3.png"):
            self.add_one(name)
        self.assertEqual(self.shown_names(), ["b3.png", "b2.png", "b1.png"])

        self.dataset_manager.select(self.dataset_id)

        self.assertEqual(self.page.sort_combo.currentData(), "added")
        self.assertEqual(self.shown_names(), ["a2.png", "a1.png"])

    def test_captions_follow_their_images_after_reordering(self):
        self._require_added()
        first = self.add_one("x.png")
        self.add_one("y.png")
        first_id = self.pool()[0].image_id

        self.dataset_manager.set_caption(first_id, "a caption")

        texts_by_id = {
            self.view.item(i).data(Qt.UserRole + 1): self.view.item(i).text()
            for i in range(self.view.count())
        }
        self.assertEqual(self.shown_paths()[-1], first)
        self.assertTrue(texts_by_id[first_id].endswith("[caption]"), texts_by_id[first_id])
        other_texts = [text for image_id, text in texts_by_id.items() if image_id != first_id]
        self.assertEqual(other_texts, ["y.png"])


class GalleryCriterionParityTest(unittest.TestCase):
    """The two pages must offer exactly the same criteria, default and order."""

    def setUp(self):
        self.dialog_guard = start_dialog_guard()
        self.addCleanup(stop_dialog_guard, self.dialog_guard)
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "ParityProject"
        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.images_page = ImagesPage(self.workspace_manager)
        self.datasets_page = DatasetsPage(self.dataset_manager, self.workspace_manager)
        for event_name in WORKSPACE_EVENTS:
            self.event_bus.subscribe(event_name, self.images_page.update_images)
        for event_name in WORKSPACE_EVENTS + CHARACTER_EVENTS + DATASET_EVENTS:
            self.event_bus.subscribe(event_name, self.datasets_page.update_datasets)

    def test_both_pages_expose_the_same_criteria_tooltips_and_default(self):
        for page in (self.images_page, self.datasets_page):
            self.assertGreaterEqual(
                page.sort_combo.findData("added"), 0,
                "criterion 'added' is absent from the sort combo",
            )
        self.assertEqual(_combo_entries(self.images_page), EXPECTED_CRITERIA)
        self.assertEqual(_combo_entries(self.datasets_page), EXPECTED_CRITERIA)
        for page in (self.images_page, self.datasets_page):
            self.assertEqual(page.sort_combo.currentData(), "added")
            self.assertEqual(page.sort_combo.itemData(2, Qt.ToolTipRole), ADDED_TOOLTIP)

    def test_both_pages_show_the_same_relative_order_for_the_same_additions(self):
        self.assertGreaterEqual(
            self.images_page.sort_combo.findData("added"), 0,
            "criterion 'added' is absent from the sort combo",
        )
        create_workspace_with_default_character(self.workspace_manager, self.character_manager, self.folder)
        dataset = self.dataset_manager.create("Portraits")
        self.dataset_manager.select(dataset.dataset_id)
        sources = []
        for name in ("m.png", "c.png", "t.png"):
            path = str(Path(self.tmp_dir) / name)
            _make_png(path)
            sources.append(path)
        self.workspace_manager.add_images(sources)
        gallery = [image.file_path for image in self.workspace_manager.current_workspace.images]
        self.dataset_manager.add_images(gallery)

        images_shown = [
            self.images_page.list_widget.item(i).text()
            for i in range(self.images_page.list_widget.count())
        ]
        datasets_shown = [
            self.datasets_page.images_list.item(i).text()
            for i in range(self.datasets_page.images_list.count())
        ]

        self.assertEqual(images_shown, ["t.png", "c.png", "m.png"])
        self.assertEqual(datasets_shown, images_shown)


if __name__ == "__main__":
    unittest.main()
