"""
Integration coverage for the Training lifecycle, exercising
TrainingManager, Character.trainings, its referential integrity with
Dataset, Workspace persistence, EventBus and the real
DashboardPage/CharactersPage/ImagesPage/TrainingPage widgets together
— the same wiring MainWindow uses. Also covers the Training domain
object's own to_dict()/from_dict() round-trip and default-value
behavior directly, since Training is a new entity introduced this
mission.
"""

import inspect
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QMessageBox,
    QListWidget,
    QPushButton,
    QScrollArea,
)

from src.core.event_bus import EventBus
from src.domain.dataset import DatasetEntryMetadata
from src.domain.image import Image
from src.domain.onetrainer_optimizer_settings import OneTrainerOptimizerSettings
from src.domain.onetrainer_settings import OneTrainerSettings
from src.domain.training import Training
from src.domain.training_job import TrainingJob
from src.domain.character import Character
from src.engines.onetrainer_config import OneTrainerConfigError
from src.infrastructure.storage.workspace_storage import WorkspaceStorage, WorkspaceStorageError
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.utils.base_model_source import InvalidBaseModelSourceError, validate_base_model_source
from src.managers.workspace_manager import (
    WorkspaceManager,
    WorkspaceManagerError,
    WORKSPACE_CREATED,
    WORKSPACE_OPENED,
    WORKSPACE_SAVED,
    WORKSPACE_CLOSED,
)
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
from src.managers.training_manager import (
    TrainingManager,
    TrainingPreparationError,
    TrainingJobError,
    TRAINING_ARCHITECTURE_SD15,
    TRAINING_ARCHITECTURE_SDXL,
    TRAINING_ARCHITECTURE_FLUX,
    TRAINING_CREATED,
    TRAINING_SELECTED,
    TRAINING_DELETED,
    TRAINING_JOB_CREATED,
    TRAINING_JOB_STATE_CHANGED,
    TRAINING_JOB_STATE_STARTING,
    TRAINING_JOB_STATE_RUNNING,
    TRAINING_JOB_STATE_SUCCEEDED,
    TRAINING_JOB_STATE_FAILED,
    TRAINING_JOB_STATE_CANCELLED,
    TRAINING_JOB_STATE_UNKNOWN,
)
from src.managers.lora_library_manager import (
    LoRALibraryManager,
    LoRALibraryError,
    LORA_LIBRARY_IMPORTED,
)
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.characters_page import CharactersPage
from src.ui.pages.images_page import ImagesPage
from src.ui.pages.inference_page import InferencePage
from src.ui.pages.training_page import TrainingPage, _STOP_TRAINING_STOP_AFTER

WORKSPACE_EVENTS = (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_SAVED, WORKSPACE_CLOSED)
CHARACTER_EVENTS = (CHARACTER_CREATED, CHARACTER_SELECTED, CHARACTER_DELETED)
DATASET_EVENTS = (DATASET_CREATED, DATASET_SELECTED, DATASET_DELETED)
TRAINING_EVENTS = (TRAINING_CREATED, TRAINING_SELECTED, TRAINING_DELETED)

_app = QApplication.instance() or QApplication([])


class TrainingRoundTripTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)

        dashboard = DashboardPage()
        characters_page = CharactersPage(character_manager, workspace_manager)
        images = ImagesPage(workspace_manager)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        for event_name in WORKSPACE_EVENTS:
            event_bus.subscribe(event_name, dashboard.update_project)
            event_bus.subscribe(event_name, images.update_images)
            event_bus.subscribe(event_name, characters_page.update_characters)

        for event_name in CHARACTER_EVENTS:
            event_bus.subscribe(event_name, characters_page.update_characters)

        # Mission 105: mirrors main_window.py's split exactly —
        # WORKSPACE_SAVED/CHARACTER_CREATED are non-destructive refreshes
        # (update_trainings()); WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are genuine context resets
        # (reset_for_context_change()), handled exclusively there.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in (CHARACTER_CREATED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)

        # Deliberately NOT subscribing training_page to DATASET_* events —
        # the dataset picker is re-read on demand via
        # dataset_manager.list_datasets(), never cached (Commit 5's design).
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return (
            event_bus, workspace_manager, character_manager, dataset_manager, training_manager,
            dashboard, characters_page, images, training_page,
        )

    def test_training_domain_object_roundtrip_and_defaults(self):

        # Default values.
        training = Training()
        self.assertEqual(training.training_id, "")
        self.assertEqual(training.name, "")
        self.assertEqual(training.dataset_id, "")
        self.assertEqual(
            training.to_dict(),
            {
                "training_id": "", "name": "", "dataset_id": "",
                "base_model_source": "", "architecture": "", "resolution": 0,
                "epochs": 100, "learning_rate": 0.0003, "lora_rank": 16,
                "lora_alpha": 1.0, "batch_size": 0, "gradient_accumulation_steps": 0,
                "trigger_word": "",
                "onetrainer_settings": {
                    "learning_rate_scheduler": "",
                    "train_dtype": "",
                    "gradient_checkpointing_mode": "",
                    "unet_weight_dtype": "",
                    "transformer_weight_dtype": "",
                    "text_encoder_weight_dtype": "",
                    "text_encoder_2_weight_dtype": "",
                    "vae_weight_dtype": "",
                    "text_encoder_train": None,
                    "text_encoder_2_train": None,
                    "text_encoder_stop_training_mode": "",
                    "text_encoder_stop_training_after": None,
                    "text_encoder_2_stop_training_mode": "",
                    "text_encoder_2_stop_training_after": None,
                    "lora_layer_filter": "",
                    "timestep_distribution": "",
                    "dynamic_timestep_shifting": None,
                    "timestep_shift": None,
                    "optimizer_settings": {"optimizer": "", "extra_overrides": {}},
                    "extra_overrides": {},
                },
                "jobs": [],
            },
        )

        # Round-trip without loss of information.
        original = Training(training_id="abc", name="Session 1", dataset_id="ds-1")
        restored = Training.from_dict(original.to_dict())
        self.assertEqual(original, restored)

        # Missing key -> default, consistent with every other Domain object.
        self.assertEqual(Training.from_dict({}), Training())
        self.assertEqual(Training.from_dict({"name": "Only Name"}).dataset_id, "")

        # Mission 120: a project.json written before this mission never
        # has "batch_size"/"gradient_accumulation_steps"/
        # "onetrainer_settings" at all — must load with this mission's
        # own sentinel defaults, never an error, never a migration.
        pre_m120 = {
            "training_id": "T1", "name": "Legacy Session", "dataset_id": "D1",
            "base_model_source": "/models/v1-5-pruned.safetensors",
            "architecture": "SD15", "resolution": 512, "epochs": 50,
            "learning_rate": 0.0002, "lora_rank": 8, "lora_alpha": 2.0,
            "trigger_word": "ohwx",
        }
        legacy_training = Training.from_dict(pre_m120)
        self.assertEqual(legacy_training.batch_size, 0)
        self.assertEqual(legacy_training.gradient_accumulation_steps, 0)
        self.assertEqual(legacy_training.onetrainer_settings, OneTrainerSettings())
        # Every pre-existing field is still loaded correctly alongside
        # the new sentinel defaults.
        self.assertEqual(legacy_training.architecture, "SD15")
        self.assertEqual(legacy_training.trigger_word, "ohwx")

        # Mission 120: round-trip of the new fields, including a
        # non-empty OneTrainerSettings (structured field + extra_overrides).
        configured = Training(
            training_id="T2",
            name="Configured Session",
            dataset_id="D2",
            batch_size=4,
            gradient_accumulation_steps=2,
            onetrainer_settings=OneTrainerSettings(
                learning_rate_scheduler="COSINE",
                extra_overrides={"loss_weight_fn": "MIN_SNR_GAMMA"},
            ),
        )
        restored_configured = Training.from_dict(configured.to_dict())
        self.assertEqual(configured, restored_configured)
        self.assertEqual(restored_configured.batch_size, 4)
        self.assertEqual(restored_configured.gradient_accumulation_steps, 2)
        self.assertEqual(
            restored_configured.onetrainer_settings.learning_rate_scheduler, "COSINE"
        )
        self.assertEqual(
            restored_configured.onetrainer_settings.extra_overrides,
            {"loss_weight_fn": "MIN_SNR_GAMMA"},
        )

        # Mission 120: a hand-edited project.json where "onetrainer_settings"
        # is present but malformed (not a dict) falls back to a fresh
        # default, same isinstance(x, dict) guard already used for every
        # other nested Domain object.
        self.assertEqual(
            Training.from_dict({"onetrainer_settings": "not-a-dict"}).onetrainer_settings,
            OneTrainerSettings(),
        )

        # Mission 121: a project.json written before this mission (or by
        # M120) never has the 6 new dtype keys inside onetrainer_settings
        # at all — must load with "" sentinels everywhere, never an
        # error, never a migration.
        pre_m121 = {
            "training_id": "T3", "name": "Pre-M121 Session", "dataset_id": "D3",
            "onetrainer_settings": {"learning_rate_scheduler": "COSINE", "extra_overrides": {}},
        }
        legacy_onetrainer_training = Training.from_dict(pre_m121)
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.learning_rate_scheduler, "COSINE")
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.train_dtype, "")
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.unet_weight_dtype, "")
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.transformer_weight_dtype, "")
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.text_encoder_weight_dtype, "")
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.text_encoder_2_weight_dtype, "")
        self.assertEqual(legacy_onetrainer_training.onetrainer_settings.vae_weight_dtype, "")

        # Mission 121: full round-trip of every new field, including a
        # FLUX-shaped configuration (transformer, not unet).
        dtype_configured = Training(
            training_id="T4",
            name="Dtype Configured Session",
            dataset_id="D4",
            onetrainer_settings=OneTrainerSettings(
                train_dtype="BFLOAT_16",
                transformer_weight_dtype="BFLOAT_16",
                text_encoder_weight_dtype="FLOAT_16",
                text_encoder_2_weight_dtype="FLOAT_16",
                vae_weight_dtype="FLOAT_32",
            ),
        )
        restored_dtype_configured = Training.from_dict(dtype_configured.to_dict())
        self.assertEqual(dtype_configured, restored_dtype_configured)
        self.assertEqual(restored_dtype_configured.onetrainer_settings.train_dtype, "BFLOAT_16")
        self.assertEqual(
            restored_dtype_configured.onetrainer_settings.transformer_weight_dtype, "BFLOAT_16"
        )
        self.assertEqual(restored_dtype_configured.onetrainer_settings.unet_weight_dtype, "")
        self.assertEqual(
            restored_dtype_configured.onetrainer_settings.text_encoder_weight_dtype, "FLOAT_16"
        )
        self.assertEqual(
            restored_dtype_configured.onetrainer_settings.text_encoder_2_weight_dtype, "FLOAT_16"
        )
        self.assertEqual(restored_dtype_configured.onetrainer_settings.vae_weight_dtype, "FLOAT_32")

        # Mission 122: a project.json written before this mission never
        # has "optimizer_settings" at all — must load with a fresh
        # OneTrainerOptimizerSettings() (sentinel "" discriminant, empty
        # extra_overrides), never an error, never a migration.
        pre_m122 = {
            "training_id": "T5", "name": "Pre-M122 Session", "dataset_id": "D5",
            "onetrainer_settings": {"learning_rate_scheduler": "COSINE", "extra_overrides": {}},
        }
        legacy_optimizer_training = Training.from_dict(pre_m122)
        self.assertEqual(
            legacy_optimizer_training.onetrainer_settings.optimizer_settings,
            OneTrainerOptimizerSettings(),
        )
        self.assertEqual(legacy_optimizer_training.onetrainer_settings.learning_rate_scheduler, "COSINE")

        # Mission 122: a hand-edited project.json where "optimizer_settings"
        # is present but malformed (not a dict) falls back to a fresh
        # default — same isinstance(x, dict) guard as every other nested
        # Domain object.
        self.assertEqual(
            OneTrainerSettings.from_dict(
                {"optimizer_settings": "not-a-dict"}
            ).optimizer_settings,
            OneTrainerOptimizerSettings(),
        )

        # Mission 122: full round-trip of the new nested field, including
        # a non-empty OneTrainerOptimizerSettings (discriminant + its own
        # scoped extra_overrides).
        optimizer_configured = Training(
            training_id="T6",
            name="Optimizer Configured Session",
            dataset_id="D6",
            onetrainer_settings=OneTrainerSettings(
                optimizer_settings=OneTrainerOptimizerSettings(
                    optimizer="ADAMW",
                    extra_overrides={"weight_decay": 0.01},
                ),
            ),
        )
        restored_optimizer_configured = Training.from_dict(optimizer_configured.to_dict())
        self.assertEqual(optimizer_configured, restored_optimizer_configured)
        self.assertEqual(
            restored_optimizer_configured.onetrainer_settings.optimizer_settings.optimizer,
            "ADAMW",
        )
        self.assertEqual(
            restored_optimizer_configured.onetrainer_settings.optimizer_settings.extra_overrides,
            {"weight_decay": 0.01},
        )
        # The two extra_overrides dicts (global vs optimizer-scoped) are
        # genuinely distinct objects, never conflated by round-tripping.
        self.assertEqual(restored_optimizer_configured.onetrainer_settings.extra_overrides, {})

        # Mission 126 (B): a project.json written before this mission
        # never has the 3 new flow-matching keys at all — must load with
        # ""/None/None sentinels, never an error, never a migration.
        pre_m126 = {
            "training_id": "T7", "name": "Pre-M126 Session", "dataset_id": "D7",
            "onetrainer_settings": {"learning_rate_scheduler": "COSINE", "extra_overrides": {}},
        }
        legacy_flow_matching_training = Training.from_dict(pre_m126)
        self.assertEqual(
            legacy_flow_matching_training.onetrainer_settings.timestep_distribution, ""
        )
        self.assertIsNone(
            legacy_flow_matching_training.onetrainer_settings.dynamic_timestep_shifting
        )
        self.assertIsNone(legacy_flow_matching_training.onetrainer_settings.timestep_shift)
        self.assertEqual(
            legacy_flow_matching_training.onetrainer_settings.learning_rate_scheduler, "COSINE"
        )

        # Mission 126 (C): full round-trip of every new field, including
        # 1.0 explicit for timestep_shift — a real, distinct value from
        # the None sentinel, never conflated by a naive truthiness check
        # anywhere along to_dict()/from_dict().
        flow_matching_configured = Training(
            training_id="T8",
            name="Flow-Matching Configured Session",
            dataset_id="D8",
            architecture=TRAINING_ARCHITECTURE_FLUX,
            onetrainer_settings=OneTrainerSettings(
                timestep_distribution="LOGIT_NORMAL",
                dynamic_timestep_shifting=True,
                timestep_shift=1.0,
            ),
        )
        restored_flow_matching_configured = Training.from_dict(flow_matching_configured.to_dict())
        self.assertEqual(flow_matching_configured, restored_flow_matching_configured)
        self.assertEqual(
            restored_flow_matching_configured.onetrainer_settings.timestep_distribution,
            "LOGIT_NORMAL",
        )
        self.assertIs(
            restored_flow_matching_configured.onetrainer_settings.dynamic_timestep_shifting, True
        )
        self.assertEqual(
            restored_flow_matching_configured.onetrainer_settings.timestep_shift, 1.0
        )
        self.assertIsNotNone(
            restored_flow_matching_configured.onetrainer_settings.timestep_shift
        )

        # Mission 126: a hand-edited project.json carrying a malformed,
        # truthy-but-wrong-typed value (e.g. a string) for either
        # Optional field must degrade to the safe sentinel, never pass
        # through as-is — same explicit-type-guard discipline already
        # established for text_encoder_train/text_encoder_2_train.
        malformed_flow_matching = OneTrainerSettings.from_dict(
            {"dynamic_timestep_shifting": "true", "timestep_shift": "1.0"}
        )
        self.assertIsNone(malformed_flow_matching.dynamic_timestep_shifting)
        self.assertIsNone(malformed_flow_matching.timestep_shift)

        # Mission 127 (B): a project.json written before this mission
        # never has "gradient_checkpointing_mode" at all — must load with
        # the "" sentinel, never an error, never a migration.
        pre_m127 = {
            "training_id": "T9", "name": "Pre-M127 Session", "dataset_id": "D9",
            "onetrainer_settings": {"learning_rate_scheduler": "COSINE", "extra_overrides": {}},
        }
        legacy_gradient_checkpointing_training = Training.from_dict(pre_m127)
        self.assertEqual(
            legacy_gradient_checkpointing_training.onetrainer_settings.gradient_checkpointing_mode,
            "",
        )
        self.assertEqual(
            legacy_gradient_checkpointing_training.onetrainer_settings.learning_rate_scheduler,
            "COSINE",
        )

        # Mission 127 (C): full round-trip of "", "OFF", "ON" and
        # "CPU_OFFLOADED" — each preserved exactly, never coerced into
        # another value along to_dict()/from_dict().
        for value in ("", "OFF", "ON", "CPU_OFFLOADED"):
            with self.subTest(gradient_checkpointing_mode=value):
                gradient_checkpointing_configured = Training(
                    training_id="T10",
                    name="Gradient Checkpointing Configured Session",
                    dataset_id="D10",
                    onetrainer_settings=OneTrainerSettings(
                        gradient_checkpointing_mode=value,
                    ),
                )
                restored_gradient_checkpointing = Training.from_dict(
                    gradient_checkpointing_configured.to_dict()
                )
                self.assertEqual(gradient_checkpointing_configured, restored_gradient_checkpointing)
                self.assertEqual(
                    restored_gradient_checkpointing.onetrainer_settings.gradient_checkpointing_mode,
                    value,
                )

        # A real bool must never be accepted as timestep_shift (bool is
        # technically an int subclass in Python) — this is the exact
        # `isinstance(x, (int, float)) and not isinstance(x, bool)` guard
        # OneTrainerSettings.from_dict() applies.
        self.assertIsNone(
            OneTrainerSettings.from_dict({"timestep_shift": True}).timestep_shift
        )

        # Character.trainings: key absent / [] / None -> [], same
        # defensive-compatibility principle as datasets/loras/prompts.
        self.assertEqual(Character.from_dict({}).trainings, [])
        self.assertEqual(Character.from_dict({"trainings": []}).trainings, [])
        self.assertEqual(Character.from_dict({"trainings": None}).trainings, [])

        # Mixed list[dict|str|None|int] -> only dict entries survive.
        mixed = Character.from_dict({
            "trainings": [
                {"training_id": "T1", "name": "Training 1", "dataset_id": "D1"},
                "invalid",
                None,
                42,
                {"training_id": "T2", "name": "Training 2"},
            ]
        })
        self.assertEqual(len(mixed.trainings), 2)
        self.assertTrue(all(isinstance(t, Training) for t in mixed.trainings))
        self.assertEqual(mixed.trainings[0].training_id, "T1")
        self.assertEqual(mixed.trainings[0].dataset_id, "D1")
        self.assertEqual(mixed.trainings[1].training_id, "T2")
        self.assertEqual(mixed.trainings[1].dataset_id, "")

    def test_full_create_select_save_close_reopen_cycle(self):

        (event_bus, workspace_manager, character_manager, dataset_manager, training_manager,
         dashboard, characters_page, images, training_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)

        dataset = dataset_manager.create("Portraits")

        # Mission 043: trainingCard mirrors datasetsCard/lorasCard — no
        # Training session yet, so it must read "0" before create().
        self.assertEqual(dashboard.trainingCard.value.text(), "0")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertEqual(training_page.training_list.count(), 1)
        self.assertIn("Portraits", training_page.dataset_label.text())
        self.assertEqual(dashboard.trainingCard.value.text(), "1")

        workspace_manager.close()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_page.training_list.count(), 0)
        self.assertEqual(dashboard.trainingCard.value.text(), "0")

        # Reopen with a second _wire() call — fresh instances, simulating
        # a real application restart rather than reusing in-memory state.
        (event_bus_2, workspace_manager_2, character_manager_2, dataset_manager_2, training_manager_2,
         dashboard_2, characters_page_2, images_2, training_page_2) = self._wire()

        workspace_manager_2.open(self.folder)

        # Mission 043: WORKSPACE_OPENED already carries the reopened
        # workspace's characters/trainings — the restored count is
        # observable immediately, independent of any character/training
        # selection performed below.
        self.assertEqual(dashboard_2.trainingCard.value.text(), "1")

        # Runtime-only per Mission 002-008 decisions: neither
        # active_character_id nor active_training_id survive a restart.
        # Checked BEFORE selecting anything below.
        self.assertIsNone(character_manager_2.active_character_id)
        self.assertIsNone(training_manager_2.active_training_id)

        # Mission 026: the reopened workspace also holds its auto-created
        # principal Character — retrieve "Aria" explicitly by name (the
        # Character these Trainings actually belong to), not by list index.
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(training_manager_2.trainings), 1)
        restored_training = training_manager_2.trainings[0]
        self.assertEqual(restored_training.name, "Session 1")
        self.assertEqual(restored_training.dataset_id, dataset.dataset_id)

    def test_dashboard_training_card_default_value_without_any_workspace(self):
        # Mission 043: a freshly constructed DashboardPage, before any
        # Workspace ever existed, must read "0" — never the "Idle" it
        # displayed before this mission.
        dashboard = DashboardPage()

        self.assertEqual(dashboard.trainingCard.value.text(), "0")

    def test_dashboard_training_card_reflects_multiple_sessions_and_deletion(self):

        (_, workspace_manager, character_manager, dataset_manager, training_manager,
         dashboard, _characters_page, _images, _training_page) = self._wire()

        workspace_manager.create(self.folder)
        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")

        first = training_manager.create("Session 1", dataset.dataset_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "1")

        second = training_manager.create("Session 2", dataset.dataset_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "2")

        training_manager.delete(first.training_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "1")

        training_manager.delete(second.training_id)
        self.assertEqual(dashboard.trainingCard.value.text(), "0")

    def test_create_rejects_empty_or_unknown_dataset_id(self):

        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset_manager.create("Portraits")  # exists but irrelevant to the ids under test

        events_seen = []
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        for invalid_id in ("", "does-not-exist"):
            trainings_before = [t.to_dict() for t in character.trainings]
            active_before = training_manager.active_training_id
            with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
                result = training_manager.create("Session", invalid_id)
                self.assertIsNone(result)
                save_spy.assert_not_called()
            self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)
            self.assertEqual(training_manager.active_training_id, active_before)
            self.assertEqual(events_seen, [])

    def test_create_rejects_dataset_id_from_another_character(self):

        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        aria_dataset = dataset_manager.create("AriaDS")

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)

        events_seen = []
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: events_seen.append(name))

        trainings_before = [t.to_dict() for t in kai.trainings]
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = training_manager.create("Session", aria_dataset.dataset_id)
            self.assertIsNone(result)
            save_spy.assert_not_called()

        self.assertEqual([t.to_dict() for t in kai.trainings], trainings_before)
        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(events_seen, [])

    def test_training_manager_context_reset_on_character_and_workspace_change(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertEqual(training_manager.active_training_id, training.training_id)

        # Switching the active character must reset active_training_id —
        # the new character's training list is unrelated.
        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        self.assertIsNone(training_manager.active_training_id)

        # Re-select Aria and her training, then confirm a workspace close
        # also resets it.
        character_manager.select(aria.character_id)
        training_manager.select(training.training_id)
        self.assertIsNotNone(training_manager.active_training_id)

        workspace_manager.close()
        self.assertIsNone(training_manager.active_training_id)

    def test_delete_active_training_resets_selection_and_persists(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        keep = training_manager.create("Keep", dataset.dataset_id)
        drop = training_manager.create("Drop", dataset.dataset_id)
        training_manager.select(drop.training_id)

        result = training_manager.delete(drop.training_id)
        self.assertTrue(result)
        self.assertIsNone(training_manager.active_training_id)
        self.assertIsNone(training_manager.active_training)
        self.assertEqual([t.name for t in training_manager.trainings], ["Keep"])

        # Non-active deletion preserves the current selection.
        other = training_manager.create("Other", dataset.dataset_id)
        training_manager.select(keep.training_id)
        result = training_manager.delete(other.training_id)
        self.assertTrue(result)
        self.assertEqual(training_manager.active_training_id, keep.training_id)

        # Invalid id: no effect at all.
        trainings_before = [t.to_dict() for t in character.trainings]
        result = training_manager.delete("does-not-exist")
        self.assertFalse(result)
        self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)
        self.assertEqual(training_manager.active_training_id, keep.training_id)

        # Persists: reopening shows only the surviving training.
        _, workspace_manager_2, character_manager_2, dataset_manager_2, training_manager_2 = self._wire()[:5]
        workspace_manager_2.open(self.folder)
        # Mission 026: retrieve "Aria" explicitly by name rather than by
        # list index (the reopened workspace also holds its auto-created
        # principal Character).
        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        self.assertEqual([t.name for t in training_manager_2.trainings], ["Keep"])

    def test_dataset_deletion_blocked_while_referenced_then_unblocks(self):

        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)

        # 1-2. Dataset D created, two Trainings T1/T2 reference it.
        dataset = dataset_manager.create("Portraits")
        t1 = training_manager.create("T1", dataset.dataset_id)
        t2 = training_manager.create("T2", dataset.dataset_id)

        dataset_events_seen = []
        for event_name in DATASET_EVENTS:
            event_bus.subscribe(event_name, lambda payload, name=event_name: dataset_events_seen.append(name))

        # 3-5. delete(D) -> False, no save/event, T1/T2 unchanged.
        datasets_before = [d.to_dict() for d in character.datasets]
        trainings_before = [t.to_dict() for t in character.trainings]
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = dataset_manager.delete(dataset.dataset_id)
            self.assertFalse(result.deleted)
            save_spy.assert_not_called()
        self.assertEqual(dataset_events_seen, [])
        self.assertEqual([d.to_dict() for d in character.datasets], datasets_before)
        self.assertEqual([t.to_dict() for t in character.trainings], trainings_before)

        # 6. delete T1 -> D still blocked (T2 remains), no cascade on D.
        training_manager.delete(t1.training_id)
        self.assertFalse(dataset_manager.delete(dataset.dataset_id).deleted)
        self.assertEqual([d.to_dict() for d in character.datasets], datasets_before)

        # 7-8. delete T2 -> D becomes deletable, deletion succeeds.
        training_manager.delete(t2.training_id)
        dataset_events_seen.clear()
        with patch.object(WorkspaceManager, "save", wraps=workspace_manager.save) as save_spy:
            result = dataset_manager.delete(dataset.dataset_id)
            self.assertTrue(result.deleted)
            save_spy.assert_called_once()
        self.assertEqual(dataset_events_seen, [DATASET_DELETED])
        self.assertNotIn(dataset.dataset_id, [d.dataset_id for d in character.datasets])

        # 9. No cascade ever occurred: character.trainings was only ever
        # mutated by the explicit training_manager.delete() calls above,
        # never as a side-effect of the two blocked delete(D) attempts.

    def test_training_operations_do_not_mutate_other_character_collections(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager = self._wire()[:5]
        workspace_manager.create(self.folder)

        aria = character_manager.create("Aria")
        character_manager.select(aria.character_id)
        dataset = dataset_manager.create("Portraits")

        kai = character_manager.create("Kai")
        character_manager.select(kai.character_id)
        kai_dataset = dataset_manager.create("KaiDS")
        training_manager.create("KaiTraining", kai_dataset.dataset_id)

        character_manager.select(aria.character_id)

        datasets_before = [d.to_dict() for d in aria.datasets]
        loras_before = [l.to_dict() for l in aria.loras]
        prompts_before = [p.to_dict() for p in aria.prompts]
        kai_trainings_before = [t.to_dict() for t in kai.trainings]

        training = training_manager.create("Session", dataset.dataset_id)
        training_manager.select(training.training_id)
        training_manager.delete(training.training_id)

        # The referenced Dataset itself (including its images list) must
        # be untouched — proves no indirect mutation through the
        # dataset_id relationship.
        self.assertEqual([d.to_dict() for d in aria.datasets], datasets_before)
        self.assertEqual([l.to_dict() for l in aria.loras], loras_before)
        self.assertEqual([p.to_dict() for p in aria.prompts], prompts_before)
        self.assertEqual([t.to_dict() for t in kai.trainings], kai_trainings_before)

    def test_training_page_rebuilds_on_relevant_events(self):

        (_, workspace_manager, character_manager, dataset_manager, training_manager,
         _dashboard, _characters_page, _images, training_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        self.assertEqual(training_page.training_list.count(), 1)

        training_manager.select(training.training_id)
        self.assertIn("Portraits", training_page.dataset_label.text())

        # Historical Training whose Dataset no longer exists displays
        # cleanly, without raising.
        training.dataset_id = "ghost-id"
        training_page.update_trainings()
        self.assertIn("introuvable", training_page.dataset_label.text())
        self.assertIn("ghost-id", training_page.dataset_label.text())

        workspace_manager.close()
        self.assertEqual(training_page.training_list.count(), 0)
        self.assertEqual(training_page.dataset_label.text(), "")

    def test_no_duplicate_subscriptions_between_wire_calls(self):

        wired_1 = self._wire()
        wired_2 = self._wire()

        for obj_1, obj_2 in zip(wired_1, wired_2):
            self.assertIsNot(obj_1, obj_2)

        event_bus_1, event_bus_2 = wired_1[0], wired_2[0]

        # 4 subscribers registered directly by _wire() (dashboard, images,
        # characters_page, training_page) + CharacterManager's two own
        # internal subscriptions (active_character_id reset, and
        # Mission 026's principal-Character auto-creation) + DatasetManager's
        # own internal reset subscription + TrainingManager's own internal
        # reset subscription = 8, on EACH bus independently.
        self.assertEqual(len(event_bus_1._subscribers[WORKSPACE_CREATED]), 8)
        self.assertEqual(len(event_bus_2._subscribers[WORKSPACE_CREATED]), 8)
        self.assertTrue(
            set(event_bus_1._subscribers[WORKSPACE_CREATED]).isdisjoint(
                event_bus_2._subscribers[WORKSPACE_CREATED]
            )
        )

    def test_dashboard_and_images_unaffected_by_training_events(self):

        (_, workspace_manager, character_manager, dataset_manager, training_manager,
         dashboard, _characters_page, images, _training_page) = self._wire()

        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        before_dashboard = dashboard.projectCard.value.text()
        before_images_count = images.list_widget.count()

        training_manager.create("Session 1", dataset.dataset_id)

        self.assertEqual(dashboard.projectCard.value.text(), before_dashboard)
        self.assertEqual(images.list_widget.count(), before_images_count)


class TrainingCreationWithoutManualCharacterSelectionTest(unittest.TestCase):
    """
    Mission 029 regression: same defect as LoRAManager/PromptManager
    (see test_lora_roundtrip.py/test_prompt_roundtrip.py's equivalent
    classes), reproduced for TrainingManager. Also proves that
    create()'s dataset-ownership check (character.datasets, see
    TrainingManager.create()) still correctly restricts against the
    principal Character's own datasets once `character` is resolved
    through principal_character instead of active_character.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        return workspace_manager, character_manager, dataset_manager, training_manager

    def test_training_lifecycle_survives_reopen_without_manual_character_selection(self):

        # 1. Create a fresh Workspace, a Dataset, and a Training
        # referencing it, then close.
        (workspace_manager, character_manager,
         dataset_manager, training_manager) = self._wire()
        workspace_manager.create(self.folder)
        principal = character_manager.principal_character

        dataset = dataset_manager.create("Base")
        self.assertIsNotNone(dataset)

        existing = training_manager.create("Run 1", dataset.dataset_id)
        self.assertIsNotNone(existing)

        workspace_manager.close()

        # 2. Reopen — exactly the sequence that leaves active_character_id
        # at None (WORKSPACE_OPENED resets it, and nothing re-selects it,
        # since CharactersPage no longer calls select() at all).
        (workspace_manager, character_manager,
         dataset_manager, training_manager) = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        self.assertIsNotNone(character_manager.principal_character)
        self.assertEqual(
            character_manager.principal_character.character_id,
            principal.character_id,
        )

        # 3. The Training created before the reopen must still be visible.
        trainings = training_manager.trainings
        self.assertEqual(len(trainings), 1)
        self.assertEqual(trainings[0].name, "Run 1")

        # 4. A second Training referencing the same principal Character's
        # own Dataset must succeed — proves the dataset-ownership check
        # inside create() still resolves against the right Character,
        # not merely that create() returns non-None.
        [dataset_again] = dataset_manager.datasets
        second = training_manager.create("Run 2", dataset_again.dataset_id)
        self.assertIsNotNone(second)
        self.assertIn(second, character_manager.principal_character.trainings)
        self.assertEqual(len(training_manager.trainings), 2)

        # 5. Deleting must succeed too.
        self.assertTrue(training_manager.delete(existing.training_id))
        self.assertEqual(len(training_manager.trainings), 1)

        # 6. Persistence: close and reopen again, confirm only the
        # surviving Training remains.
        workspace_manager.close()
        (workspace_manager, character_manager,
         dataset_manager, training_manager) = self._wire()
        workspace_manager.open(self.folder)

        self.assertIsNone(character_manager.active_character_id)
        final = training_manager.trainings
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0].name, "Run 2")

    def _wire_page_with_fake_dataset(self, workspace_manager, character_manager):
        # TrainingPage.create_training() only reaches the "Aucun
        # personnage" branch under test once a non-empty dataset list
        # has already been displayed — dataset_manager is mocked here
        # to force that, independently of whatever principal_character
        # actually resolves to (see Mission 036 specification, section
        # 3: this branch is a defensive/consistency fix, not a normally
        # reachable path — TrainingManager.create() checks
        # principal_character before dataset ownership, so the fake
        # dataset_id below is never actually consulted in these tests).
        training_manager = TrainingManager(character_manager, workspace_manager)
        dataset_manager = MagicMock()
        dataset_manager.list_datasets.return_value = [
            {"name": "Base", "dataset_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        ]
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )
        return training_page

    def test_create_training_without_open_workspace_shows_no_project_warning(self):
        # Mission 036 introduced this "Aucun projet ouvert" message, then
        # reached only via TrainingManager.create() returning None (the
        # "Aucun dataset disponible" guard, fired earlier in the method,
        # was masking it whenever list_datasets() was mocked non-empty
        # as done here). Mission 037 moved the workspace_manager.opened
        # check to the very top of create_training(), so this same
        # scenario is now intercepted before list_datasets() is ever
        # consulted and before either QInputDialog is ever shown —
        # asserted explicitly below.
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        training_page = self._wire_page_with_fake_dataset(workspace_manager, character_manager)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=("Base [aaaaaaaa]", True),
        ) as mock_get_item, patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Run 1", True),
        ) as mock_get_text, patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_called_once_with(
                training_page,
                "Aucun projet ouvert",
                "Ouvrez ou créez un projet avant de créer une session d'entraînement."
            )
            # Mission 037: the new top-of-method guard must prevent any
            # dataset lookup or dialog from firing in this case.
            training_page.dataset_manager.list_datasets.assert_not_called()
            mock_get_item.assert_not_called()
            mock_get_text.assert_not_called()

    def test_create_training_with_open_workspace_and_no_character_shows_personnage_warning(self):
        # Sibling of the test above: same None from TrainingManager.
        # create(), but here the Workspace is open with zero Character.
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        workspace_manager.create(self.folder)
        principal = character_manager.characters[0]
        character_manager.delete(principal.character_id)
        training_page = self._wire_page_with_fake_dataset(workspace_manager, character_manager)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=("Base [aaaaaaaa]", True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Run 1", True),
        ), patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_called_once_with(
                training_page,
                "Aucun personnage",
                "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer une session d'entraînement."
            )

    def test_create_training_with_open_workspace_and_no_dataset_shows_dataset_warning(self):
        # Mission 037: Workspace open, zero Dataset — the pre-existing
        # "Aucun dataset disponible" guard (unrelated to Mission 037,
        # unchanged) must still fire exactly as before, now reached only
        # once the new workspace_manager.opened guard above it has
        # passed. Real WorkspaceManager/DatasetManager here (no mock),
        # unlike the two tests above.
        workspace_manager, character_manager, dataset_manager, training_manager = self._wire()
        workspace_manager.create(self.folder)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        with patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_called_once_with(
                training_page,
                "Aucun dataset disponible",
                "Créez un dataset avant de créer une session d'entraînement."
            )

        self.assertEqual(training_manager.trainings, [])

    def test_create_training_with_open_workspace_and_dataset_succeeds(self):
        # Mission 037: golden path — Workspace open with a Dataset
        # available must remain entirely unaffected by the new guard.
        workspace_manager, character_manager, dataset_manager, training_manager = self._wire()
        workspace_manager.create(self.folder)
        dataset = dataset_manager.create("Base")
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        label = f"Base [{dataset.dataset_id[:8]}]"

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Run 1", True),
        ), patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning:
            training_page.create_training()
            mock_warning.assert_not_called()

        self.assertEqual(len(training_manager.trainings), 1)
        self.assertEqual(training_manager.trainings[0].name, "Run 1")
        self.assertEqual(training_manager.trainings[0].dataset_id, dataset.dataset_id)


class TrainingManagerRenameTest(unittest.TestCase):
    """
    Mission 054: TrainingManager.update_name() — mirrors
    PromptManager.update_name()'s exact idempotent contract (Mission
    053), extended to Training. No training engine, no execution state
    introduced or implied.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)

    def test_update_name_renames_the_active_training(self):
        result = self.training_manager.update_name("Session 1 Renamed")

        self.assertTrue(result)
        self.assertEqual(self.training_manager.active_training.name, "Session 1 Renamed")

    def test_update_name_is_idempotent(self):
        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update_name("Session 1")
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update_name("Session 1 Renamed")
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_name_without_active_training_returns_false(self):
        self.training_manager.active_training_id = None

        result = self.training_manager.update_name("Anything")

        self.assertFalse(result)

    def test_update_name_preserves_training_id_and_dataset_id(self):
        original_training_id = self.training.training_id
        original_dataset_id = self.training.dataset_id

        self.training_manager.update_name("Session 1 Renamed")

        self.assertEqual(self.training_manager.active_training.training_id, original_training_id)
        self.assertEqual(self.training_manager.active_training.dataset_id, original_dataset_id)

    def test_update_name_empty_string_is_legitimate(self):
        result = self.training_manager.update_name("")

        self.assertTrue(result)
        self.assertEqual(self.training_manager.active_training.name, "")

    def test_rename_persists_after_close_reopen(self):
        self.training_manager.update_name("Session 1 Renamed")

        self.workspace_manager.close()

        event_bus_2 = EventBus()
        workspace_manager_2 = WorkspaceManager(event_bus=event_bus_2)
        character_manager_2 = CharacterManager(workspace_manager_2, event_bus=event_bus_2)
        training_manager_2 = TrainingManager(character_manager_2, workspace_manager_2, event_bus=event_bus_2)
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)

        self.assertEqual(len(training_manager_2.trainings), 1)
        restored = training_manager_2.trainings[0]
        self.assertEqual(restored.training_id, self.training.training_id)
        self.assertEqual(restored.name, "Session 1 Renamed")
        self.assertEqual(restored.dataset_id, self.dataset.dataset_id)


class TrainingManagerCreateRollbackTest(unittest.TestCase):
    """
    Mission 072: TrainingManager.create() rolls back the in-memory
    append (the same Training instance just constructed) if save()
    fails — mirrors DatasetManager.create()'s rollback contract.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.existing_training = self.training_manager.create("Session 1", self.dataset.dataset_id)

    def test_create_succeeds_normally_when_save_works(self):
        training = self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertIsNotNone(training)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.existing_training.training_id, training.training_id],
        )

    def test_create_save_failure_removes_the_phantom_training(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.existing_training.training_id],
        )

    def test_create_save_failure_publishes_no_success_event(self):
        received = []
        self.event_bus.subscribe(TRAINING_CREATED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertEqual(received, [])

    def test_create_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        training = self.training_manager.create("Session 2", self.dataset.dataset_id)

        self.assertIsNotNone(training)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.existing_training.training_id, training.training_id],
        )

        with open(self.folder / "project.json", encoding="utf-8") as f:
            on_disk = json.load(f)
        aria = next(c for c in on_disk["characters"] if c["name"] == "Aria")
        self.assertEqual(
            sorted(t["training_id"] for t in aria["trainings"]),
            sorted([self.existing_training.training_id, training.training_id]),
        )

    def test_create_save_failure_does_not_affect_a_preexisting_unrelated_training(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create("Session 2", self.dataset.dataset_id)

        trainings = self.training_manager.trainings
        self.assertEqual(len(trainings), 1)
        self.assertIs(trainings[0], self.existing_training)


class TrainingManagerTriggerWordDefaultPrefillTest(unittest.TestCase):
    """
    Mission 111: Training.trigger_word defaults from the principal
    Character's own trigger_token at TrainingManager.create() time only
    -- a plain initial value, never a lasting link. See MISSION_111.md
    for the full 10-point behavior contract.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        self.character = self.character_manager.principal_character
        self.dataset = self.dataset_manager.create("Portraits")

    def test_new_training_is_prefilled_from_a_non_blank_character_trigger_token(self):
        self.character_manager.update(self.character.character_id, trigger_token="dmlrwoman")

        training = self.training_manager.create("Session 1", self.dataset.dataset_id)

        self.assertEqual(training.trigger_word, "dmlrwoman")

    def test_new_training_stays_blank_when_the_character_has_no_trigger_token(self):
        training = self.training_manager.create("Session 1", self.dataset.dataset_id)

        self.assertEqual(training.trigger_word, "")

    def test_reloading_an_existing_training_with_a_trigger_word_never_changes_it(self):
        self.character_manager.update(self.character.character_id, trigger_token="dmlrwoman")
        training = self.training_manager.create("Session 1", self.dataset.dataset_id)

        # "Reloading" = re-reading the persisted Domain state -- never
        # calling create() again, exactly what TrainingPage.update_trainings()/
        # _load_training_parameters() do (training_page.py:548-663), which
        # this mission leaves entirely untouched.
        self.training_manager.select(training.training_id)
        reloaded = self.training_manager.active_training

        self.assertEqual(reloaded.trigger_word, "dmlrwoman")

    def test_reloading_an_existing_training_with_a_blank_trigger_word_never_prefills_it_late(self):
        training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        # The Character only gains a trigger_token *after* this Training
        # already exists -- reloading it must never retroactively pick it
        # up (rule 8 of MISSION_111.md).
        self.character_manager.update(self.character.character_id, trigger_token="dmlrwoman")

        self.training_manager.select(training.training_id)
        reloaded = self.training_manager.active_training

        self.assertEqual(reloaded.trigger_word, "")

    def test_manually_set_trigger_word_is_never_overwritten_by_the_character(self):
        training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(training.training_id)
        self.training_manager.update(trigger_word="manual-trigger")

        self.character_manager.update(self.character.character_id, trigger_token="dmlrwoman")

        self.assertEqual(self.training_manager.active_training.trigger_word, "manual-trigger")

    def test_changing_the_character_trigger_token_later_never_touches_an_existing_training(self):
        self.character_manager.update(self.character.character_id, trigger_token="dmlrwoman")
        training = self.training_manager.create("Session 1", self.dataset.dataset_id)

        self.character_manager.update(self.character.character_id, trigger_token="different-trigger")

        self.training_manager.select(training.training_id)
        self.assertEqual(self.training_manager.active_training.trigger_word, "dmlrwoman")


class TrainingPageCreatePersistenceFailureTest(unittest.TestCase):
    """
    Mission 072: TrainingPage.create_training() catches
    WorkspaceManagerError around training_manager.create() and shows
    QMessageBox.critical().
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        self.lora_library_manager = MagicMock()
        self.lora_library_manager.get.return_value = None
        self.training_page = TrainingPage(
            self.training_manager, self.dataset_manager, self.workspace_manager,
            self.application_settings_manager, self.lora_library_manager,
        )
        for event_name in TRAINING_EVENTS:
            self.event_bus.subscribe(event_name, self.training_page.update_trainings)

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)
        self.dataset = self.dataset_manager.create("Portraits")
        self.label = f"Portraits [{self.dataset.dataset_id[:8]}]"

    def test_create_failure_shows_error_and_training_list_stays_empty(self):
        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            self.training_page.create_training()

        self.assertTrue(mock_critical.called)
        self.assertEqual(self.training_manager.trainings, [])
        self.assertEqual(self.training_page.training_list.count(), 0)

    def test_create_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical"):
            self.training_page.create_training()

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_create_failure_actually_creates(self):
        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ), patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical"):
            self.training_page.create_training()

        with patch(
            "src.ui.pages.training_page.QInputDialog.getItem",
            return_value=(self.label, True),
        ), patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Session 1", True),
        ):
            self.training_page.create_training()

        self.assertEqual(len(self.training_manager.trainings), 1)
        self.assertEqual(self.training_page.training_list.count(), 1)


class TrainingManagerRenameRollbackTest(unittest.TestCase):
    """
    Mission 070: TrainingManager.update_name() rolls back Training.name
    to its previous value if save() fails — a single-scalar Domain-only
    mutation, no filesystem involved, so a local rollback is sufficient.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)

    def test_update_name_succeeds_normally_when_save_works(self):
        result = self.training_manager.update_name("Session 1 Renamed")

        self.assertTrue(result)
        self.assertEqual(self.training.name, "Session 1 Renamed")

    def test_update_name_save_failure_restores_previous_name_on_same_object(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        self.assertEqual(self.training.name, "Session 1")
        self.assertIs(self.training_manager.active_training, self.training)

    def test_update_name_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_update_name_save_failure_never_touches_dataset_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        self.assertEqual(self.training.dataset_id, self.dataset.dataset_id)

    def test_retry_of_the_same_previously_rejected_name_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_name("Session 1 Renamed")

        result = self.training_manager.update_name("Session 1 Renamed")

        self.assertTrue(result)
        self.assertEqual(self.training.name, "Session 1 Renamed")


class TrainingPageSortTest(unittest.TestCase):
    """
    Mission 051: TrainingPage.training_list is now sorted by name,
    case-insensitive, always active — same pattern as Mission 048.
    Character.trainings (Domain) must never be reordered.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingSortProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        # Mission 105: mirrors main_window.py's split exactly —
        # WORKSPACE_SAVED/CHARACTER_CREATED are non-destructive refreshes
        # (update_trainings()); WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are genuine context resets
        # (reset_for_context_change()), handled exclusively there.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in (CHARACTER_CREATED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _setup_character_and_dataset(self, character_manager, dataset_manager):
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        return character, dataset

    def test_display_order_is_alphabetical_case_insensitive(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        for name in ("Zebra", "mango", "Apple", "banana", "Cherry"):
            training_manager.create(name, dataset.dataset_id)

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "banana", "Cherry", "mango", "Zebra"])

    def test_domain_collection_keeps_insertion_order(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        for name in ("Zebra", "mango", "Apple"):
            training_manager.create(name, dataset.dataset_id)

        self.assertEqual(
            [t.name for t in character.trainings],
            ["Zebra", "mango", "Apple"],
        )

    def test_sort_is_stable_for_identical_names(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        first = training_manager.create("Same", dataset.dataset_id)
        second = training_manager.create("Same", dataset.dataset_id)

        displayed_ids = [
            training_page.training_list.item(i).data(Qt.UserRole)
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed_ids, [first.training_id, second.training_id])

    def test_selection_targets_correct_training_despite_display_reorder(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character, portraits = self._setup_character_and_dataset(character_manager, dataset_manager)
        landscapes = dataset_manager.create("Landscapes")

        zebra = training_manager.create("Zebra", portraits.dataset_id)
        apple = training_manager.create("Apple", landscapes.dataset_id)

        training_manager.select(apple.training_id)

        # "Apple" now displays at position 0, ahead of "Zebra" — confirm
        # the correct training's dataset is reflected, not positional.
        self.assertEqual(training_page.training_list.item(0).text(), "Apple")
        self.assertIn("Landscapes", training_page.dataset_label.text())

        training_manager.select(zebra.training_id)
        self.assertIn("Portraits", training_page.dataset_label.text())

    def test_refresh_after_second_creation_resorts_entire_list(self):

        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training_manager.create("Mango", dataset.dataset_id)
        training_manager.create("Zebra", dataset.dataset_id)
        training_manager.create("Apple", dataset.dataset_id)

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Apple", "Mango", "Zebra"])


class TrainingPageRenameTest(unittest.TestCase):
    """
    Mission 054: TrainingPage.name_edit — real-widget rename, mirroring
    PromptsPageRenameTest (Mission 053). training_list is sorted
    (Mission 051), so a rename must resort the list while keeping the
    selection on the renamed entity by training_id, never by position.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingRenameProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        # Mission 105: mirrors main_window.py's split exactly —
        # WORKSPACE_SAVED/CHARACTER_CREATED are non-destructive refreshes
        # (update_trainings()); WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are genuine context resets
        # (reset_for_context_change()), handled exclusively there.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in (CHARACTER_CREATED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _setup_character_and_dataset(self, character_manager, dataset_manager):
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        return character, dataset

    def test_rename_via_widget_updates_manager_and_display(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertEqual(training_page.name_edit.text(), "Session 1")

        training_page.name_edit.setText("Session 1 Renamed")
        training_page.name_edit.editingFinished.emit()

        self.assertEqual(training_manager.active_training.name, "Session 1 Renamed")
        self.assertEqual(training_manager.active_training.training_id, training.training_id)
        self.assertEqual(training_manager.active_training.dataset_id, dataset.dataset_id)

    def test_rename_with_no_active_training_is_a_no_op(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        self._setup_character_and_dataset(character_manager, dataset_manager)

        training_page.name_edit.setText("Anything")
        training_page.name_edit.editingFinished.emit()

        self.assertIsNone(training_manager.active_training_id)

    def test_rename_moving_entity_to_front_keeps_correct_selection(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        apple = training_manager.create("Apple", dataset.dataset_id)
        zebra = training_manager.create("Zebra", dataset.dataset_id)
        training_manager.select(zebra.training_id)

        training_page.name_edit.setText("Aardvark")
        training_page.name_edit.editingFinished.emit()

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Aardvark", "Apple"])
        self.assertEqual(training_manager.active_training_id, zebra.training_id)
        self.assertEqual(training_page.training_list.currentItem().data(Qt.UserRole), zebra.training_id)

    def test_rename_moving_entity_to_back_keeps_correct_selection(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        apple = training_manager.create("Apple", dataset.dataset_id)
        zebra = training_manager.create("Zebra", dataset.dataset_id)
        training_manager.select(apple.training_id)

        training_page.name_edit.setText("Zzz")
        training_page.name_edit.editingFinished.emit()

        displayed = [
            training_page.training_list.item(i).text()
            for i in range(training_page.training_list.count())
        ]
        self.assertEqual(displayed, ["Zebra", "Zzz"])
        self.assertEqual(training_manager.active_training_id, apple.training_id)
        self.assertEqual(training_page.training_list.currentItem().data(Qt.UserRole), apple.training_id)

    def test_rename_persists_after_close_reopen_via_ui(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        training_page.name_edit.setText("Session 1 Renamed")
        training_page.name_edit.editingFinished.emit()

        workspace_manager.close()

        (_, workspace_manager_2, character_manager_2, dataset_manager_2,
         training_manager_2, training_page_2) = self._wire()
        workspace_manager_2.open(self.folder)

        restored_character = next(
            c for c in character_manager_2.characters if c.name == "Aria"
        )
        character_manager_2.select(restored_character.character_id)
        training_manager_2.select(training.training_id)

        restored = training_manager_2.active_training
        self.assertEqual(restored.name, "Session 1 Renamed")
        self.assertEqual(restored.training_id, training.training_id)
        self.assertEqual(restored.dataset_id, dataset.dataset_id)

    def test_rename_save_failure_shows_error_and_restores_widget_to_previous_name(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        training_page.name_edit.setText("Session 1 Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical") as critical_mock:
            training_page.name_edit.editingFinished.emit()

        self.assertTrue(critical_mock.called)
        self.assertEqual(training.name, "Session 1")
        self.assertEqual(training_page.name_edit.text(), "Session 1")
        self.assertEqual(training_page.training_list.currentItem().text(), "Session 1")

    def test_retry_after_rename_save_failure_actually_renames(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        _, dataset = self._setup_character_and_dataset(character_manager, dataset_manager)

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        training_page.name_edit.setText("Session 1 Renamed")
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical"):
            training_page.name_edit.editingFinished.emit()

        training_page.name_edit.setText("Session 1 Renamed")
        training_page.name_edit.editingFinished.emit()

        self.assertEqual(training.name, "Session 1 Renamed")
        self.assertEqual(training_page.training_list.currentItem().text(), "Session 1 Renamed")


class TrainingManagerDeleteRollbackTest(unittest.TestCase):
    """
    Mission 068: TrainingManager.delete() rolls back the in-memory
    removal (and active_training_id) if save() fails — Domain-only
    mutation, so the rollback is a simple local re-insertion at the
    original index, never a full Workspace snapshot. dataset_id is
    never touched by delete() at all, so no separate rollback for it is
    needed.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")

        self.training_a = self.training_manager.create("Alpha", self.dataset.dataset_id)
        self.training_b = self.training_manager.create("Beta", self.dataset.dataset_id)
        self.training_c = self.training_manager.create("Gamma", self.dataset.dataset_id)
        self.training_manager.select(self.training_b.training_id)

    def test_delete_succeeds_normally_when_save_works(self):
        result = self.training_manager.delete(self.training_b.training_id)

        self.assertTrue(result)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.training_a.training_id, self.training_c.training_id],
        )
        self.assertIsNone(self.training_manager.active_training_id)

    def test_delete_save_failure_restores_object_at_original_index(self):
        received = []
        self.event_bus.subscribe(TRAINING_DELETED, lambda payload: received.append(payload))

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        trainings = self.training_manager.trainings
        self.assertEqual(
            [t.training_id for t in trainings],
            [self.training_a.training_id, self.training_b.training_id, self.training_c.training_id],
        )
        self.assertIs(trainings[1], self.training_b)
        self.assertEqual(self.training_b.dataset_id, self.dataset.dataset_id)
        self.assertEqual(received, [])

    def test_delete_save_failure_restores_active_training_id(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        self.assertEqual(self.training_manager.active_training_id, self.training_b.training_id)

    def test_delete_save_failure_never_touches_an_unrelated_active_id(self):
        self.training_manager.select(self.training_a.training_id)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        self.assertEqual(self.training_manager.active_training_id, self.training_a.training_id)

    def test_delete_save_failure_leaves_project_json_unchanged(self):
        with open(self.folder / "project.json", encoding="utf-8") as f:
            before = json.load(f)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        with open(self.folder / "project.json", encoding="utf-8") as f:
            after = json.load(f)
        self.assertEqual(before, after)

    def test_retry_after_save_failure_is_a_genuine_new_attempt(self):
        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.delete(self.training_b.training_id)

        result = self.training_manager.delete(self.training_b.training_id)

        self.assertTrue(result)
        self.assertEqual(
            [t.training_id for t in self.training_manager.trainings],
            [self.training_a.training_id, self.training_c.training_id],
        )


class TrainingPageDeleteConfirmationTest(unittest.TestCase):
    """
    Mission 062: TrainingPage.delete_training() now confirms before
    deleting, mirroring ImagesPage.delete_selected_images()'s
    established QMessageBox pattern (Mission 046) — Cancel is the safe
    default.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingDeleteProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        # Mission 105: mirrors main_window.py's split exactly —
        # WORKSPACE_SAVED/CHARACTER_CREATED are non-destructive refreshes
        # (update_trainings()); WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are genuine context resets
        # (reset_for_context_change()), handled exclusively there.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in (CHARACTER_CREATED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _confirm_delete(self, accept: bool):
        patcher = patch("src.ui.pages.training_page.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)

        accept_sentinel = object()
        cancel_sentinel = object()
        box_instance = mock_cls.return_value
        box_instance.addButton.side_effect = [accept_sentinel, cancel_sentinel]
        box_instance.clickedButton.return_value = (
            accept_sentinel if accept else cancel_sentinel
        )

        return mock_cls

    def test_delete_with_no_selection_is_a_no_op(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)

        mock_cls = self._confirm_delete(accept=True)

        training_page.delete_training()

        mock_cls.assert_not_called()

    def test_delete_confirmed_removes_training(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self._confirm_delete(accept=True)

        training_page.delete_training()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_manager.trainings, [])

    def test_delete_cancelled_calls_neither_manager_nor_mutates_state(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self._confirm_delete(accept=False)

        with patch.object(training_manager, "delete") as delete_mock:
            training_page.delete_training()
            delete_mock.assert_not_called()

        self.assertEqual(training_manager.active_training_id, training.training_id)
        self.assertEqual(len(training_manager.trainings), 1)

    def test_delete_confirmed_save_failure_shows_error_and_keeps_the_training(self):
        """
        Mission 068: TrainingManager.delete() rolls back the Domain
        removal (and active_training_id) before re-raising on a save()
        failure — the Page must intercept WorkspaceManagerError, inform
        the user, and never present the deletion as successful.
        """
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        mock_cls = self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            training_page.delete_training()

        mock_cls.critical.assert_called_once()
        self.assertEqual(training_manager.active_training_id, training.training_id)
        self.assertEqual(len(training_manager.trainings), 1)
        self.assertIs(training_manager.trainings[0], training)

    def test_retry_after_save_failure_actually_deletes(self):
        _, workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self._confirm_delete(accept=True)

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            training_page.delete_training()

        self._confirm_delete(accept=True)
        training_page.delete_training()

        self.assertIsNone(training_manager.active_training_id)
        self.assertEqual(training_manager.trainings, [])


class TrainingPageDeleteButtonStateTest(unittest.TestCase):
    """
    Mission 063: "Supprimer" must always reflect whether there is
    currently a valid selection to act on, mirroring ImagesPage's
    established delete_button.setEnabled() pattern (Mission 046) —
    never a silent no-op behind an always-clickable button.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingButtonStateProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        # Mission 105: mirrors main_window.py's split exactly —
        # WORKSPACE_SAVED/CHARACTER_CREATED are non-destructive refreshes
        # (update_trainings()); WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are genuine context resets
        # (reset_for_context_change()), handled exclusively there.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in (CHARACTER_CREATED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def test_disabled_before_any_workspace(self):
        _, _, _, _, training_page = self._wire()
        self.assertFalse(training_page.delete_button.isEnabled())

    def test_disabled_with_no_selection_then_enabled_on_select(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")

        self.assertFalse(training_page.delete_button.isEnabled())

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)

        self.assertTrue(training_page.delete_button.isEnabled())

    def test_deselecting_disables_delete_button(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        training_page.training_list.setCurrentItem(None)

        self.assertFalse(training_page.delete_button.isEnabled())

    def test_delete_button_stays_consistent_after_list_rebuild(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training_a = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training_a.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        # TRAINING_CREATED triggers update_trainings() -> a full list
        # rebuild, while the active selection itself is untouched.
        training_manager.create("Session 2", dataset.dataset_id)

        self.assertTrue(training_page.delete_button.isEnabled())
        self.assertEqual(
            training_page.training_list.currentItem().data(Qt.UserRole), training_a.training_id
        )

    def test_disabled_after_workspace_closed(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        workspace_manager.close()

        self.assertFalse(training_page.delete_button.isEnabled())

    def test_disabled_after_deleting_the_selected_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        self.assertTrue(training_page.delete_button.isEnabled())

        # TRAINING_DELETED triggers update_trainings() -> the button
        # must be recomputed from the resulting (now empty) selection.
        training_manager.delete(training.training_id)

        self.assertFalse(training_page.delete_button.isEnabled())


class TrainingPageOnetrainerParametersTest(unittest.TestCase):
    """
    Mission 097: TrainingPage's new generic-hyperparameter widgets, the
    "Enregistrer les paramètres d'entraînement" button
    (TrainingManager.update()), and the "Préparer la configuration
    OneTrainer" button (TrainingManager.prepare_onetrainer_config()) —
    real widgets throughout, QMessageBox/QFileDialog mocked (this
    mission never shows a real modal during automated tests, same
    discipline as every other page in this codebase).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingParamsProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        # Mission 105: mirrors main_window.py's split exactly —
        # WORKSPACE_SAVED/CHARACTER_CREATED are non-destructive refreshes
        # (update_trainings()); WORKSPACE_CREATED/OPENED/CLOSED and
        # CHARACTER_SELECTED/DELETED are genuine context resets
        # (reset_for_context_change()), handled exclusively there.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in (CHARACTER_CREATED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _create_selected_training(self, workspace_manager, character_manager, dataset_manager, training_manager):
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        return dataset, training

    def test_new_buttons_disabled_with_no_selection(self):
        _, _, _, _, training_page = self._wire()

        self.assertFalse(training_page.save_parameters_button.isEnabled())
        self.assertFalse(training_page.prepare_config_button.isEnabled())

    def test_new_buttons_enabled_once_a_training_is_selected(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        self.assertTrue(training_page.save_parameters_button.isEnabled())
        self.assertTrue(training_page.prepare_config_button.isEnabled())

    def test_architecture_change_suggests_the_matching_resolution(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertEqual(training_page.resolution_spinbox.value(), 512)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.resolution_spinbox.value(), 1024)

    def test_reloading_a_saved_training_never_re_triggers_the_resolution_suggestion(self):
        # Mission 097: update_trainings() must blockSignals() on
        # architecture_combo while restoring a training's own saved
        # values — otherwise a stored, deliberately non-default
        # resolution would be silently overwritten by the suggestion.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(architecture=TRAINING_ARCHITECTURE_SDXL, resolution=900)

        training_page.update_trainings()

        self.assertEqual(training_page.architecture_combo.currentText(), TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.resolution_spinbox.value(), 900)

    def test_save_button_persists_every_field_via_training_manager_update(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )

        training_page.base_model_edit.setText("models/base.safetensors")
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.resolution_spinbox.setValue(1024)
        training_page.epochs_spinbox.setValue(30)
        training_page.learning_rate_spinbox.setValue(0.0007)
        training_page.lora_rank_spinbox.setValue(8)
        training_page.lora_alpha_spinbox.setValue(4.0)
        training_page.trigger_word_edit.setText("ohwx")
        training_page.batch_size_spinbox.setValue(4)
        training_page.gradient_accumulation_steps_spinbox.setValue(2)
        training_page.learning_rate_scheduler_combo.setCurrentIndex(
            training_page.learning_rate_scheduler_combo.findData("COSINE")
        )
        training_page.train_dtype_combo.setCurrentIndex(
            training_page.train_dtype_combo.findData("FLOAT_16")
        )
        training_page.main_model_weight_dtype_combo.setCurrentIndex(
            training_page.main_model_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.text_encoder_weight_dtype_combo.setCurrentIndex(
            training_page.text_encoder_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.text_encoder_2_weight_dtype_combo.setCurrentIndex(
            training_page.text_encoder_2_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.vae_weight_dtype_combo.setCurrentIndex(
            training_page.vae_weight_dtype_combo.findData("FLOAT_32")
        )
        training_page.optimizer_combo.setCurrentIndex(
            training_page.optimizer_combo.findData("ADAMW")
        )

        training_page.save_training_parameters()

        self.assertEqual(training.base_model_source, "models/base.safetensors")
        self.assertEqual(training.architecture, TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training.resolution, 1024)
        self.assertEqual(training.epochs, 30)
        self.assertEqual(training.learning_rate, 0.0007)
        self.assertEqual(training.lora_rank, 8)
        self.assertEqual(training.lora_alpha, 4.0)
        self.assertEqual(training.trigger_word, "ohwx")
        self.assertEqual(training.batch_size, 4)
        self.assertEqual(training.gradient_accumulation_steps, 2)
        self.assertEqual(training.onetrainer_settings.learning_rate_scheduler, "COSINE")
        self.assertEqual(training.onetrainer_settings.train_dtype, "FLOAT_16")
        # Mission 121: architecture is SDXL at Save time, so the shared
        # "Main model" combo is bound to unet_weight_dtype, never
        # transformer_weight_dtype.
        self.assertEqual(training.onetrainer_settings.unet_weight_dtype, "FLOAT_16")
        self.assertEqual(training.onetrainer_settings.transformer_weight_dtype, "")
        self.assertEqual(training.onetrainer_settings.text_encoder_weight_dtype, "FLOAT_16")
        self.assertEqual(training.onetrainer_settings.text_encoder_2_weight_dtype, "FLOAT_16")
        self.assertEqual(training.onetrainer_settings.vae_weight_dtype, "FLOAT_32")
        self.assertEqual(training.onetrainer_settings.optimizer_settings.optimizer, "ADAMW")

    def test_new_fields_default_to_not_configured_and_round_trip_through_reload(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        # Mission 120: a freshly created Training shows the "not
        # configured" sentinel in each new widget — never a value that
        # would actually change the built OneTrainer config.
        self.assertEqual(training_page.batch_size_spinbox.value(), 0)
        self.assertEqual(training_page.gradient_accumulation_steps_spinbox.value(), 0)
        self.assertEqual(training_page.learning_rate_scheduler_combo.currentData(), "")

        training_page.batch_size_spinbox.setValue(4)
        training_page.gradient_accumulation_steps_spinbox.setValue(2)
        training_page.learning_rate_scheduler_combo.setCurrentIndex(
            training_page.learning_rate_scheduler_combo.findData("COSINE")
        )
        training_page.save_training_parameters()

        # Force a full reload of the persisted Domain state into the
        # widgets — same mechanism already exercised by
        # test_reloading_a_saved_training_never_re_triggers_the_
        # resolution_suggestion() above (save clears _dirty, and
        # _loaded_training_id is unchanged, so update_trainings() takes
        # its non-destructive-refresh-that-still-reloads path).
        training_page.update_trainings()

        self.assertEqual(training_page.batch_size_spinbox.value(), 4)
        self.assertEqual(training_page.gradient_accumulation_steps_spinbox.value(), 2)
        self.assertEqual(training_page.learning_rate_scheduler_combo.currentData(), "COSINE")

    # --- Mission 121: Advanced settings / Precision-Memory --------------

    def test_dtype_fields_default_to_not_configured_and_round_trip_through_reload(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        self.assertEqual(training_page.train_dtype_combo.currentData(), "")
        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "")
        self.assertEqual(training_page.text_encoder_weight_dtype_combo.currentData(), "")
        self.assertEqual(training_page.text_encoder_2_weight_dtype_combo.currentData(), "")
        self.assertEqual(training_page.vae_weight_dtype_combo.currentData(), "")

        training_page.train_dtype_combo.setCurrentIndex(
            training_page.train_dtype_combo.findData("FLOAT_16")
        )
        training_page.main_model_weight_dtype_combo.setCurrentIndex(
            training_page.main_model_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.text_encoder_weight_dtype_combo.setCurrentIndex(
            training_page.text_encoder_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.text_encoder_2_weight_dtype_combo.setCurrentIndex(
            training_page.text_encoder_2_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.vae_weight_dtype_combo.setCurrentIndex(
            training_page.vae_weight_dtype_combo.findData("FLOAT_32")
        )
        training_page.save_training_parameters()

        training_page.update_trainings()

        self.assertEqual(training_page.train_dtype_combo.currentData(), "FLOAT_16")
        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "FLOAT_16")
        self.assertEqual(training_page.text_encoder_weight_dtype_combo.currentData(), "FLOAT_16")
        self.assertEqual(training_page.text_encoder_2_weight_dtype_combo.currentData(), "FLOAT_16")
        self.assertEqual(training_page.vae_weight_dtype_combo.currentData(), "FLOAT_32")

    # --- Mission 122: Advanced settings / Optimizer ----------------------

    def test_optimizer_field_defaults_to_not_configured_and_round_trips_through_reload(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        self.assertEqual(training_page.optimizer_combo.currentData(), "")

        training_page.optimizer_combo.setCurrentIndex(
            training_page.optimizer_combo.findData("SGD")
        )
        training_page.save_training_parameters()

        training_page.update_trainings()

        self.assertEqual(training_page.optimizer_combo.currentData(), "SGD")

    def test_optimizer_combo_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.optimizer_combo.setCurrentIndex(
            training_page.optimizer_combo.findData("ADAM")
        )

        self.assertTrue(training_page._dirty)

    def test_advanced_settings_container_starts_folded(self):
        # Mission 121: this Page is never shown on screen in these
        # tests, so QWidget.isVisible() (actual on-screen visibility)
        # would report False for every widget regardless of its own
        # explicit setVisible() state — isHidden() reflects this
        # specific widget's own explicit hidden flag instead, which is
        # what setVisible(False)/setVisible(True) actually control here.
        _, _, _, _, training_page = self._wire()

        self.assertTrue(training_page.advanced_settings_container.isHidden())
        self.assertFalse(training_page.advanced_settings_toggle.isChecked())

    def test_toggling_advanced_settings_never_marks_dirty_or_changes_values(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        self.assertFalse(training_page._dirty)

        training_page.advanced_settings_toggle.setChecked(True)
        self.assertFalse(training_page.advanced_settings_container.isHidden())
        self.assertFalse(training_page._dirty)
        self.assertEqual(training_page.train_dtype_combo.currentData(), "")
        # Mission 122: the Optimizer sub-section shares the same
        # container/toggle — folding/unfolding must never touch it
        # either.
        self.assertEqual(training_page.optimizer_combo.currentData(), "")

        training_page.advanced_settings_toggle.setChecked(False)
        self.assertTrue(training_page.advanced_settings_container.isHidden())
        self.assertFalse(training_page._dirty)

    def test_gradient_accumulation_and_scheduler_are_reclassified_into_advanced(self):
        # Mission 125 section 6: both fields were moved from the always-
        # visible Basic form into the Advanced container — a real usage
        # (technical/memory, never surfaced by any of OneTrainer's own 3
        # official LoRA presets), not a cosmetic label change. Asserting
        # ancestry proves the widgets were actually re-parented under
        # advanced_settings_form, not merely visually grouped.
        _, _, _, _, training_page = self._wire()

        self.assertTrue(
            training_page.advanced_settings_container.isAncestorOf(
                training_page.gradient_accumulation_steps_spinbox
            )
        )
        self.assertTrue(
            training_page.advanced_settings_container.isAncestorOf(
                training_page.learning_rate_scheduler_combo
            )
        )
        self.assertFalse(
            training_page.advanced_settings_container.isAncestorOf(
                training_page.batch_size_spinbox
            )
        )

    def test_reclassified_fields_keep_their_value_across_a_fold_unfold_cycle(self):
        # Mission 125 section 7/13: folding Advanced must never lose a
        # value already entered for a field moved into it — the widget is
        # only hidden (QWidget.setVisible), never destroyed or reset.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.advanced_settings_toggle.setChecked(True)
        training_page.gradient_accumulation_steps_spinbox.setValue(4)
        training_page.learning_rate_scheduler_combo.setCurrentIndex(
            training_page.learning_rate_scheduler_combo.findData("COSINE")
        )

        training_page.advanced_settings_toggle.setChecked(False)
        self.assertEqual(training_page.gradient_accumulation_steps_spinbox.value(), 4)
        self.assertEqual(training_page.learning_rate_scheduler_combo.currentData(), "COSINE")

        training_page.advanced_settings_toggle.setChecked(True)
        self.assertEqual(training_page.gradient_accumulation_steps_spinbox.value(), 4)
        self.assertEqual(training_page.learning_rate_scheduler_combo.currentData(), "COSINE")

    def test_text_encoder_2_hidden_for_sd15_visible_for_sdxl_and_flux(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertTrue(training_page.text_encoder_2_weight_dtype_combo.isHidden())

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertFalse(training_page.text_encoder_2_weight_dtype_combo.isHidden())

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertFalse(training_page.text_encoder_2_weight_dtype_combo.isHidden())

    def test_main_model_label_reflects_unet_or_transformer(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertEqual(training_page.main_model_weight_dtype_label.text(), "UNet weight dtype :")

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.main_model_weight_dtype_label.text(), "UNet weight dtype :")

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertEqual(
            training_page.main_model_weight_dtype_label.text(), "Transformer weight dtype :"
        )

    def test_switching_sd15_to_sdxl_never_resets_unet_weight_dtype(self):
        # Mission 121 section 7: unet_weight_dtype stays valid across
        # SD1.5 <-> SDXL — a value configured on one must survive the
        # switch to the other, unlike a genuine incompatibility.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        training_page.main_model_weight_dtype_combo.setCurrentIndex(
            training_page.main_model_weight_dtype_combo.findData("FLOAT_16")
        )

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "FLOAT_16")

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "FLOAT_16")

    def test_switching_sdxl_to_flux_resets_unet_weight_dtype_and_never_resurfaces(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.main_model_weight_dtype_combo.setCurrentIndex(
            training_page.main_model_weight_dtype_combo.findData("FLOAT_16")
        )

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)

        # Now representing transformer_weight_dtype — never the old
        # unet_weight_dtype value, which must be reset, not carried over.
        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "")
        self.assertEqual(training_page._unet_weight_dtype_draft, "")

        # Switching back to SDXL must not silently resurface the old
        # FLOAT_16 unet value either — it was genuinely discarded.
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "")

    def test_switching_flux_to_sd15_still_resets_transformer_weight_dtype(self):
        # Mission 129 section 14: unet_weight_dtype/transformer_weight_
        # dtype are strictly out of scope — their own mutually-exclusive
        # _draft mechanism keeps resetting exactly as before this
        # mission, unaffected by the text_encoder_2 change below (split
        # from this test's pre-M129 combined form, which asserted both
        # in one place).
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.main_model_weight_dtype_combo.setCurrentIndex(
            training_page.main_model_weight_dtype_combo.findData("BFLOAT_16")
        )

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        self.assertEqual(training_page.main_model_weight_dtype_combo.currentData(), "")
        self.assertEqual(training_page._transformer_weight_dtype_draft, "")

    def test_switching_flux_to_sd15_hides_but_never_resets_text_encoder_2_weight_dtype(self):
        # Mission 129 section 7/17 item A: text_encoder_2_weight_dtype now
        # follows the same never-reset contract as text_encoder_2_stop_
        # training (M128) — hidden, but the Domain-backed value survives
        # a temporary architecture switch unchanged.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.text_encoder_2_weight_dtype_combo.setCurrentIndex(
            training_page.text_encoder_2_weight_dtype_combo.findData("FLOAT_16")
        )

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        self.assertEqual(training_page.text_encoder_2_weight_dtype_combo.currentData(), "FLOAT_16")
        self.assertTrue(training_page.text_encoder_2_weight_dtype_combo.isHidden())

        # Switching back to FLUX must reveal the exact same value —
        # never resurrected from a draft, because it was never reset.
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertEqual(training_page.text_encoder_2_weight_dtype_combo.currentData(), "FLOAT_16")
        self.assertFalse(training_page.text_encoder_2_weight_dtype_combo.isHidden())

    def test_architecture_change_marks_dirty_even_when_no_dtype_field_is_configured(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)

        self.assertTrue(training_page._dirty)

    def test_reload_hiding_persisted_incompatible_fields_never_marks_dirty(self):
        # Mission 129 section 11/17 item I: reloading a Training whose
        # Domain already holds SDXL-only values while its architecture is
        # SD1.5 (hide-only gating, reset_incompatible=False) must never
        # mark the form dirty by itself — only a genuine user-driven
        # change does (see the test above).
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15)
        training.onetrainer_settings.text_encoder_2_weight_dtype = "FLOAT_16"
        training.onetrainer_settings.text_encoder_2_train = True

        training_page.update_trainings()

        self.assertTrue(training_page.text_encoder_2_weight_dtype_combo.isHidden())
        self.assertFalse(training_page._dirty)

    def test_prepare_config_surfaces_an_incompatible_dtype_field_as_a_critical_error(self):
        # Mission 121 section 3.3: even though the UI's own reset logic
        # prevents this through normal interactive use, the Domain/
        # translation-level validation in build_training_config() is
        # exercised end-to-end here by forcing an incompatible in-memory
        # combination directly (simulating a hand-edited project.json)
        # and confirming prepare_onetrainer_config() surfaces it as a
        # normal, explicit error dialog — never a silent success.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        # Bypasses the UI entirely — direct Domain mutation, exactly
        # like a hand-edited project.json would produce.
        training.onetrainer_settings.transformer_weight_dtype = "FLOAT_16"

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.prepare_onetrainer_config()
            mock_critical.assert_called_once()

    def test_save_button_failure_shows_error_and_restores_widgets(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.trigger_word_edit.setText("ohwx")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")), \
                patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.save_training_parameters()
            mock_critical.assert_called_once()

        # update_trainings() (called on failure) redraws from the
        # rolled-back Domain state — never the invalid attempted value.
        self.assertEqual(training_page.trigger_word_edit.text(), "")

    def test_browse_base_model_source_sets_the_selected_path(self):
        _, _, _, _, training_page = self._wire()

        with patch(
            "src.ui.pages.training_page.QFileDialog.getOpenFileName",
            return_value=("models/chosen.safetensors", ""),
        ):
            training_page.browse_base_model_source()

        self.assertEqual(training_page.base_model_edit.text(), "models/chosen.safetensors")

    def test_browse_base_model_source_cancelled_leaves_the_field_untouched(self):
        _, _, _, _, training_page = self._wire()
        training_page.base_model_edit.setText("/already/set.safetensors")

        with patch(
            "src.ui.pages.training_page.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            training_page.browse_base_model_source()

        self.assertEqual(training_page.base_model_edit.text(), "/already/set.safetensors")

    def test_prepare_config_success_shows_the_three_paths_and_starts_no_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )

        with patch("src.ui.pages.training_page.QMessageBox.information") as mock_information:
            training_page.prepare_onetrainer_config()
            mock_information.assert_called_once()
            shown_text = mock_information.call_args.args[2]
            self.assertIn("training", shown_text.lower())
            self.assertIn("Aucun entraînement n'a été lancé", shown_text)

    def test_prepare_config_failure_shows_a_critical_message(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        # No images in the dataset -> TrainingPreparationError.

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.prepare_onetrainer_config()
            mock_critical.assert_called_once()

    def test_prepare_config_with_no_selection_is_a_no_op(self):
        _, _, _, _, training_page = self._wire()

        with patch("src.ui.pages.training_page.QMessageBox.information") as mock_information, \
                patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.prepare_onetrainer_config()
            mock_information.assert_not_called()
            mock_critical.assert_not_called()

    # --- Mission 124: Text Encoder train / Layer Filter -----------------

    def test_text_encoder_train_fields_default_to_not_configured(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        self.assertIsNone(training_page.text_encoder_train_combo.currentData())
        self.assertIsNone(training_page.text_encoder_2_train_combo.currentData())
        self.assertEqual(training_page.lora_layer_filter_combo.currentData(), "")

    def test_text_encoder_train_fields_round_trip_through_reload(self):
        # J: the three real UI states (Non configuré/Entraîné/Gelé) and
        # Layer Filter, saved and reloaded exactly like every other
        # Advanced settings field on this page.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        training_page.text_encoder_train_combo.setCurrentIndex(
            training_page.text_encoder_train_combo.findData(True)
        )
        training_page.text_encoder_2_train_combo.setCurrentIndex(
            training_page.text_encoder_2_train_combo.findData(False)
        )
        training_page.lora_layer_filter_combo.setCurrentIndex(
            training_page.lora_layer_filter_combo.findData("ATTN_MLP")
        )
        training_page.save_training_parameters()

        training_page.update_trainings()

        self.assertEqual(training_page.text_encoder_train_combo.currentData(), True)
        self.assertEqual(training_page.text_encoder_2_train_combo.currentData(), False)
        self.assertEqual(training_page.lora_layer_filter_combo.currentData(), "ATTN_MLP")

    def test_text_encoder_train_combo_can_be_reset_back_to_not_configured(self):
        # L (UI side): explicitly setting the combo back to "Non
        # configuré" and saving must actually persist None, never be
        # silently ignored as "nothing to save" — this is exactly the
        # _UNSET-vs-None distinction TrainingManagerUpdateTest also
        # locks in at the Manager level below.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.text_encoder_train_combo.setCurrentIndex(
            training_page.text_encoder_train_combo.findData(True)
        )
        training_page.save_training_parameters()
        self.assertIs(training.onetrainer_settings.text_encoder_train, True)

        training_page.text_encoder_train_combo.setCurrentIndex(0)  # "Non configuré"
        training_page.save_training_parameters()

        self.assertIsNone(training.onetrainer_settings.text_encoder_train)

    def test_text_encoder_train_combo_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.text_encoder_train_combo.setCurrentIndex(
            training_page.text_encoder_train_combo.findData(True)
        )

        self.assertTrue(training_page._dirty)

    def test_lora_layer_filter_combo_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.lora_layer_filter_combo.setCurrentIndex(
            training_page.lora_layer_filter_combo.findData("ATTN_MLP")
        )

        self.assertTrue(training_page._dirty)

    def test_switching_to_sd15_hides_but_never_resets_text_encoder_2_train(self):
        # Mission 129 section 7/17 item B: text_encoder_2_train now
        # follows the same never-reset contract as text_encoder_2_stop_
        # training (M128) and text_encoder_2_weight_dtype above — hidden,
        # but the Domain-backed value survives a temporary architecture
        # switch unchanged. Uses False specifically (not just True) to
        # prove an explicitly-configured False is never lost either.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.text_encoder_2_train_combo.setCurrentIndex(
            training_page.text_encoder_2_train_combo.findData(False)
        )

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        self.assertIs(training_page.text_encoder_2_train_combo.currentData(), False)
        self.assertTrue(training_page.text_encoder_2_train_combo.isHidden())
        self.assertTrue(training_page.text_encoder_2_train_label.isHidden())

        # Switching back to SDXL must reveal the exact same value.
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertIs(training_page.text_encoder_2_train_combo.currentData(), False)
        self.assertFalse(training_page.text_encoder_2_train_combo.isHidden())

    def test_switching_to_sdxl_reveals_text_encoder_2_train(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        self.assertFalse(training_page.text_encoder_2_train_combo.isHidden())
        self.assertFalse(training_page.text_encoder_2_train_label.isHidden())

    def test_prepare_config_succeeds_with_an_incompatible_train_field_persisted(self):
        # Mission 129 section 7/10: text_encoder_2_train persisted on a
        # Training now on SD1.5 (simulating a temporary architecture
        # switch, or a hand-edited project.json) must no longer surface
        # as a critical error — it succeeds, silently omitting the field
        # (see test_text_encoder_2_train_persisted_but_omitted_from_
        # sd15_config in TrainingManagerPrepareOnetrainerConfigTest for
        # the JSON-level proof).
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        training.onetrainer_settings.text_encoder_2_train = False

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical, \
                patch("src.ui.pages.training_page.QMessageBox.information") as mock_information:
            training_page.prepare_onetrainer_config()
            mock_critical.assert_not_called()
            mock_information.assert_called_once()

    # --- Mission 126: NFLOAT_4 / Flow-matching (FLUX) --------------------

    def test_nfloat_4_available_in_every_existing_dtype_combo(self):
        # J: the shared dtype vocabulary gained NFLOAT_4 with no new
        # per-architecture/per-component restriction — confirmed
        # directly against every dtype combo this page exposes.
        _, _, _, _, training_page = self._wire()

        for combo in (
            training_page.train_dtype_combo,
            training_page.main_model_weight_dtype_combo,
            training_page.text_encoder_weight_dtype_combo,
            training_page.text_encoder_2_weight_dtype_combo,
            training_page.vae_weight_dtype_combo,
        ):
            with self.subTest(combo=combo):
                self.assertNotEqual(combo.findData("NFLOAT_4"), -1)

    def test_existing_dtype_choices_unaffected_by_nfloat_4_addition(self):
        # Non-regression: the 4 pre-existing dtype values are all still
        # present after adding NFLOAT_4.
        _, _, _, _, training_page = self._wire()
        for value in ("FLOAT_16", "FLOAT_32", "BFLOAT_16", "TFLOAT_32"):
            with self.subTest(value=value):
                self.assertNotEqual(training_page.train_dtype_combo.findData(value), -1)

    def test_flow_matching_fields_default_to_not_configured(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        self.assertEqual(training_page.timestep_distribution_combo.currentData(), "")
        self.assertIsNone(training_page.dynamic_timestep_shifting_combo.currentData())
        self.assertFalse(training_page.timestep_shift_checkbox.isChecked())
        self.assertFalse(training_page.timestep_shift_spinbox.isEnabled())

    def test_flow_matching_fields_round_trip_through_reload(self):
        # C: timestep_distribution/dynamic_timestep_shifting/
        # timestep_shift saved and reloaded exactly like every other
        # Advanced settings field on this page — including 1.0 explicit
        # for timestep_shift, distinct from "not configured".
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)

        training_page.timestep_distribution_combo.setCurrentIndex(
            training_page.timestep_distribution_combo.findData("LOGIT_NORMAL")
        )
        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page.timestep_shift_spinbox.setValue(1.0)
        training_page.save_training_parameters()

        training_page.update_trainings()

        self.assertEqual(training_page.timestep_distribution_combo.currentData(), "LOGIT_NORMAL")
        self.assertIs(training_page.dynamic_timestep_shifting_combo.currentData(), True)
        self.assertTrue(training_page.timestep_shift_checkbox.isChecked())
        self.assertEqual(training_page.timestep_shift_spinbox.value(), 1.0)

    def test_timestep_shift_checkbox_off_persists_none_even_with_a_leftover_spinbox_value(self):
        # F: unchecked always means None, even if a numeric value
        # remains displayed in the (disabled) spinbox — the checkbox
        # alone is the source of truth for "configured or not".
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.timestep_shift_spinbox.setValue(2.5)
        # Checkbox left unchecked (default) despite a non-default
        # spinbox value.

        training_page.save_training_parameters()

        self.assertIsNone(training.onetrainer_settings.timestep_shift)

    def test_timestep_shift_other_float_round_trips(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page.timestep_shift_spinbox.setValue(1.15)

        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.timestep_shift, 1.15)

    def test_timestep_distribution_combo_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.timestep_distribution_combo.setCurrentIndex(
            training_page.timestep_distribution_combo.findData("LOGIT_NORMAL")
        )

        self.assertTrue(training_page._dirty)

    def test_dynamic_timestep_shifting_combo_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )

        self.assertTrue(training_page._dirty)

    def test_timestep_shift_checkbox_marks_dirty_on_toggle(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.timestep_shift_checkbox.setChecked(True)

        self.assertTrue(training_page._dirty)

    def test_timestep_shift_spinbox_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page._dirty = False

        training_page.timestep_shift_spinbox.setValue(2.0)

        self.assertTrue(training_page._dirty)

    # --- Mission 126 section 8: dynamic/static interaction --------------

    def test_dynamic_timestep_shifting_true_disables_static_controls_without_clearing_value(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page.timestep_shift_spinbox.setValue(1.5)
        self.assertTrue(training_page.timestep_shift_checkbox.isEnabled())
        self.assertTrue(training_page.timestep_shift_spinbox.isEnabled())

        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )

        # Disabled visually, but neither unchecked nor cleared.
        self.assertFalse(training_page.timestep_shift_checkbox.isEnabled())
        self.assertFalse(training_page.timestep_shift_spinbox.isEnabled())
        self.assertTrue(training_page.timestep_shift_checkbox.isChecked())
        self.assertEqual(training_page.timestep_shift_spinbox.value(), 1.5)

        # Repassing to Désactivé re-enables the controls and the
        # previous value is still there, immediately usable again.
        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(False)
        )
        self.assertTrue(training_page.timestep_shift_checkbox.isEnabled())
        self.assertTrue(training_page.timestep_shift_spinbox.isEnabled())
        self.assertTrue(training_page.timestep_shift_checkbox.isChecked())
        self.assertEqual(training_page.timestep_shift_spinbox.value(), 1.5)

    def test_dynamic_true_and_configured_static_shift_both_saved_independently(self):
        # G: OneTrainer ignores timestep_shift at runtime when
        # dynamic_timestep_shifting=True, but Toolkit must still persist
        # both Domain values — never suppress one because of the other.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page.timestep_shift_spinbox.setValue(1.5)
        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )

        training_page.save_training_parameters()

        self.assertIs(training.onetrainer_settings.dynamic_timestep_shifting, True)
        self.assertEqual(training.onetrainer_settings.timestep_shift, 1.5)

    def test_setting_dynamic_timestep_shifting_alone_never_marks_dirty_beyond_its_own_change(self):
        # Mission 126 section 8: the visual-only disabling performed by
        # _apply_dynamic_timestep_shifting_ui_state() (setEnabled() only,
        # never setChecked()/setValue()) must never be mistaken for a
        # second, independent dirty-marking edit — the single dirty mark
        # observed here comes from the combo's own genuine value change,
        # already covered by test_dynamic_timestep_shifting_combo_marks_
        # dirty_on_change above; this test instead confirms no exception
        # or unexpected side effect fires when toggling dynamic on an
        # unconfigured (unchecked) timestep_shift.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)

        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )

        self.assertFalse(training_page.timestep_shift_checkbox.isEnabled())
        self.assertFalse(training_page.timestep_shift_checkbox.isChecked())
        self.assertFalse(training_page.timestep_shift_spinbox.isEnabled())

    # --- Mission 126 section 9: architecture visibility/switching -------

    def test_flow_matching_section_hidden_for_sd15_and_sdxl_visible_for_flux(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertTrue(training_page.timestep_distribution_combo.isHidden())
        self.assertTrue(training_page.dynamic_timestep_shifting_combo.isHidden())
        self.assertTrue(training_page.timestep_shift_checkbox.isHidden())
        self.assertTrue(training_page.timestep_shift_spinbox.isHidden())

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertTrue(training_page.timestep_distribution_combo.isHidden())

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertFalse(training_page.timestep_distribution_combo.isHidden())
        self.assertFalse(training_page.dynamic_timestep_shifting_combo.isHidden())
        self.assertFalse(training_page.timestep_shift_checkbox.isHidden())
        self.assertFalse(training_page.timestep_shift_spinbox.isHidden())

    def test_switching_to_sd15_hides_but_never_resets_flow_matching_fields(self):
        # Mission 129 section 7/17 item C: the three flow-matching fields
        # now follow the same never-reset contract as text_encoder_2_
        # stop_training (M128) and text_encoder_2_weight_dtype/_train
        # above — hidden, but the Domain-backed values survive a
        # temporary architecture switch away from FLUX unchanged.
        # dynamic_timestep_shifting uses True here (see item M below for
        # the explicit-False proof, which must also survive FLUX itself).
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.timestep_distribution_combo.setCurrentIndex(
            training_page.timestep_distribution_combo.findData("LOGIT_NORMAL")
        )
        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page.timestep_shift_spinbox.setValue(1.0)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        self.assertEqual(training_page.timestep_distribution_combo.currentData(), "LOGIT_NORMAL")
        self.assertIs(training_page.dynamic_timestep_shifting_combo.currentData(), True)
        self.assertTrue(training_page.timestep_shift_checkbox.isChecked())
        self.assertEqual(training_page.timestep_shift_spinbox.value(), 1.0)
        self.assertTrue(training_page.timestep_distribution_combo.isHidden())

        # Switching back to FLUX must reveal the exact same values —
        # never resurrected from a draft, because they were never reset.
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertEqual(training_page.timestep_distribution_combo.currentData(), "LOGIT_NORMAL")
        self.assertIs(training_page.dynamic_timestep_shifting_combo.currentData(), True)
        self.assertTrue(training_page.timestep_shift_checkbox.isChecked())
        self.assertFalse(training_page.timestep_distribution_combo.isHidden())

    def test_switching_to_sd15_and_back_preserves_an_explicit_dynamic_timestep_shifting_false(self):
        # Mission 129 section 6/17 item M: False is a real, explicit
        # configuration — never lost by a truthy check anywhere in the
        # persistence path, on FLUX (its only compatible architecture)
        # just as much as on SD15/SDXL.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(False)
        )

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertIs(training_page.dynamic_timestep_shifting_combo.currentData(), False)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertIs(training_page.dynamic_timestep_shifting_combo.currentData(), False)

    def test_switching_to_flux_reveals_flow_matching_fields(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)

        self.assertFalse(training_page.timestep_distribution_combo.isHidden())
        self.assertFalse(training_page.timestep_distribution_label.isHidden())

    def test_architecture_change_marks_dirty_even_for_flow_matching_reset(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page._dirty = False

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        self.assertTrue(training_page._dirty)

    def test_reload_of_a_stale_flux_configuration_on_sd15_preserves_domain_without_resetting(self):
        # Mission 129: a mere programmatic reload (reset_incompatible=
        # False) of a Training whose Domain already holds FLUX-only
        # values under a different current architecture (simulating a
        # hand-edited project.json) must never silently wipe them —
        # same guarantee as a genuine user-driven switch since this
        # mission (test_switching_to_sd15_hides_but_never_resets_flow_
        # matching_fields above), covering the reset_incompatible=False
        # code path specifically, which that other test does not
        # exercise.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15)
        training.onetrainer_settings.timestep_distribution = "LOGIT_NORMAL"
        training.onetrainer_settings.dynamic_timestep_shifting = True
        training.onetrainer_settings.timestep_shift = 1.0

        training_page.update_trainings()

        self.assertEqual(training.onetrainer_settings.timestep_distribution, "LOGIT_NORMAL")
        self.assertIs(training.onetrainer_settings.dynamic_timestep_shifting, True)
        self.assertEqual(training.onetrainer_settings.timestep_shift, 1.0)
        # Widgets reflect the stale-but-real Domain value even though
        # hidden for SD1.5 — never forced back to "" by the reload path.
        self.assertEqual(training_page.timestep_distribution_combo.currentData(), "LOGIT_NORMAL")
        self.assertTrue(training_page.timestep_distribution_combo.isHidden())

    def test_prepare_config_succeeds_with_an_incompatible_flow_matching_field_persisted(self):
        # Mission 129 section 7/10: the architecture gate that used to
        # live in build_training_config() as a raise (see
        # test_onetrainer_config.py) is now a silent-omission gate — a
        # flow-matching value persisted on a Training now on SD1.5 (a
        # temporary architecture switch, or a hand-edited project.json)
        # must no longer surface as a critical error.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        training.onetrainer_settings.timestep_distribution = "LOGIT_NORMAL"

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical, \
                patch("src.ui.pages.training_page.QMessageBox.information") as mock_information:
            training_page.prepare_onetrainer_config()
            mock_critical.assert_not_called()
            mock_information.assert_called_once()

    # --- Mission 128: Text Encoder training duration ---------------------

    def test_stop_training_defaults_to_not_configured(self):
        _, _, _, _, training_page = self._wire()
        self.assertEqual(training_page.text_encoder_stop_training_mode_combo.currentData(), "")
        self.assertEqual(
            training_page.text_encoder_2_stop_training_mode_combo.currentData(), ""
        )

    def test_stop_training_fields_round_trip_through_reload(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        for mode_data, unit_data, value in (
            ("NEVER", None, None),
            ("EPOCH", "EPOCH", 10),
            ("STEP", "STEP", 500),
        ):
            with self.subTest(mode=mode_data):
                training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
                    training_page.text_encoder_stop_training_mode_combo.findData(
                        mode_data if unit_data is None else _STOP_TRAINING_STOP_AFTER
                    )
                )
                if unit_data is not None:
                    training_page.text_encoder_stop_training_unit_combo.setCurrentIndex(
                        training_page.text_encoder_stop_training_unit_combo.findData(unit_data)
                    )
                    training_page.text_encoder_stop_training_value_spinbox.setValue(value)
                training_page.save_training_parameters()

                training_page.update_trainings()

                self.assertEqual(
                    training_page.text_encoder_stop_training_mode_combo.currentData(),
                    mode_data if unit_data is None else _STOP_TRAINING_STOP_AFTER,
                )
                if unit_data is not None:
                    self.assertEqual(
                        training_page.text_encoder_stop_training_unit_combo.currentData(),
                        unit_data,
                    )
                    self.assertEqual(
                        training_page.text_encoder_stop_training_value_spinbox.value(), value
                    )

    # Closure-audit correction: _load_stop_training_widgets() must never
    # leave a stale numeric residue from a previously loaded Training on
    # screen for a Training whose own real after is None — purely visual
    # (never written to the Domain either way), but the displayed state
    # must fully reflect the Training actually loaded.

    def test_loading_a_never_configured_training_resets_the_stale_value_spinbox(self):
        # A.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training_a = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(
            architecture=TRAINING_ARCHITECTURE_SDXL,
            text_encoder_stop_training_mode="EPOCH",
            text_encoder_stop_training_after=7,
        )
        training_page.update_trainings()
        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 7)

        training_b = training_manager.create("Session 2", dataset.dataset_id)
        training_manager.select(training_b.training_id)
        training_manager.update(
            architecture=TRAINING_ARCHITECTURE_SDXL, text_encoder_stop_training_mode="NEVER"
        )

        training_page.update_trainings()

        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 1)
        self.assertEqual(training_page.text_encoder_stop_training_mode_combo.currentData(), "NEVER")
        self.assertEqual(training_b.onetrainer_settings.text_encoder_stop_training_mode, "NEVER")
        self.assertIsNone(training_b.onetrainer_settings.text_encoder_stop_training_after)
        self.assertFalse(training_page._dirty)

    def test_loading_a_not_configured_training_resets_the_stale_value_spinbox(self):
        # B.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training_a = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(
            architecture=TRAINING_ARCHITECTURE_SDXL,
            text_encoder_stop_training_mode="STEP",
            text_encoder_stop_training_after=10,
        )
        training_page.update_trainings()
        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 10)

        training_b = training_manager.create("Session 2", dataset.dataset_id)
        training_manager.select(training_b.training_id)
        training_manager.update(architecture=TRAINING_ARCHITECTURE_SDXL)

        training_page.update_trainings()

        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 1)
        self.assertEqual(training_page.text_encoder_stop_training_mode_combo.currentData(), "")
        self.assertEqual(training_b.onetrainer_settings.text_encoder_stop_training_mode, "")
        self.assertIsNone(training_b.onetrainer_settings.text_encoder_stop_training_after)
        self.assertFalse(training_page._dirty)

    def test_epoch_to_never_then_stop_after_never_resurrects_the_old_value(self):
        # C.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_stop_training_value_spinbox.setValue(7)
        training_page.save_training_parameters()

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData("NEVER")
        )
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_mode, "NEVER")
        self.assertIsNone(training.onetrainer_settings.text_encoder_stop_training_after)

        # A genuine reload (never a live in-session mode toggle) is the
        # only path guaranteed to fully resync the widgets from the
        # freshly-saved Domain — exercised explicitly here.
        training_page.update_trainings()
        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 1)

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )

        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 1)
        self.assertNotEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 7)

    def test_step_to_not_configured_then_stop_after_never_resurrects_the_old_value(self):
        # D.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_stop_training_unit_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_unit_combo.findData("STEP")
        )
        training_page.text_encoder_stop_training_value_spinbox.setValue(10)
        training_page.save_training_parameters()

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData("")
        )
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_mode, "")
        self.assertIsNone(training.onetrainer_settings.text_encoder_stop_training_after)

        training_page.update_trainings()
        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 1)

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )

        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 1)
        self.assertNotEqual(training_page.text_encoder_stop_training_value_spinbox.value(), 10)

    def test_stop_training_value_and_unit_enabled_only_in_stop_after_mode(self):
        _, _, _, _, training_page = self._wire()

        self.assertFalse(training_page.text_encoder_stop_training_value_spinbox.isEnabled())
        self.assertFalse(training_page.text_encoder_stop_training_unit_combo.isEnabled())

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )

        self.assertTrue(training_page.text_encoder_stop_training_value_spinbox.isEnabled())
        self.assertTrue(training_page.text_encoder_stop_training_unit_combo.isEnabled())

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData("NEVER")
        )

        self.assertFalse(training_page.text_encoder_stop_training_value_spinbox.isEnabled())
        self.assertFalse(training_page.text_encoder_stop_training_unit_combo.isEnabled())

    def test_stop_training_value_spinbox_minimum_is_one(self):
        # D (contrat 4): the UI never lets the user reach 0+EPOCH/0+STEP,
        # even though the engine itself accepts it — a real, deliberate
        # UI-level restriction, never a claim that 0 is invalid engine
        # -side.
        _, _, _, _, training_page = self._wire()
        self.assertEqual(training_page.text_encoder_stop_training_value_spinbox.minimum(), 1)
        self.assertEqual(training_page.text_encoder_2_stop_training_value_spinbox.minimum(), 1)

    # F/G: switching away from "Arrêter après" always resets after=None
    # on save, regardless of whatever number the spinbox still displays.

    def test_switching_from_stop_after_to_never_resets_after_to_none_on_save(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_stop_training_value_spinbox.setValue(30)
        training_page.save_training_parameters()
        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_after, 30)

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData("NEVER")
        )
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_mode, "NEVER")
        self.assertIsNone(training.onetrainer_settings.text_encoder_stop_training_after)

    def test_switching_from_stop_after_to_not_configured_resets_after_to_none_on_save(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_stop_training_value_spinbox.setValue(30)
        training_page.save_training_parameters()

        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData("")
        )
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_mode, "")
        self.assertIsNone(training.onetrainer_settings.text_encoder_stop_training_after)

    def test_loading_a_configured_stop_training_never_marks_dirty(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(
            text_encoder_stop_training_mode="EPOCH", text_encoder_stop_training_after=10
        )

        training_page.update_trainings()

        self.assertFalse(training_page._dirty)

    # H (contrat 11): train=False never resets an already-configured
    # duration — persisted, translated, and shown in the UI regardless.

    def test_train_false_does_not_reset_configured_stop_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.text_encoder_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_stop_training_value_spinbox.setValue(5)
        training_page.text_encoder_train_combo.setCurrentIndex(
            training_page.text_encoder_train_combo.findData(False)
        )
        training_page.save_training_parameters()

        self.assertIs(training.onetrainer_settings.text_encoder_train, False)
        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_mode, "EPOCH")
        self.assertEqual(training.onetrainer_settings.text_encoder_stop_training_after, 5)

    # --- Mission 128 section 10: TE2 persistence across architecture ----
    # switching (deliberately different from text_encoder_2_train's own
    # historical reset-on-incompatible-architecture behavior).

    def test_switching_to_sd15_hides_but_never_resets_text_encoder_2_stop_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.text_encoder_2_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_2_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_2_stop_training_unit_combo.setCurrentIndex(
            training_page.text_encoder_2_stop_training_unit_combo.findData("EPOCH")
        )
        training_page.text_encoder_2_stop_training_value_spinbox.setValue(5)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        # Hidden, per the same architecture-driven visibility rule as
        # text_encoder_2_train — but, unlike it, never reset.
        self.assertTrue(training_page.text_encoder_2_stop_training_mode_combo.isHidden())
        self.assertEqual(
            training_page.text_encoder_2_stop_training_mode_combo.currentData(),
            _STOP_TRAINING_STOP_AFTER,
        )
        self.assertEqual(
            training_page.text_encoder_2_stop_training_unit_combo.currentData(), "EPOCH"
        )
        self.assertEqual(
            training_page.text_encoder_2_stop_training_value_spinbox.value(), 5
        )

    def test_switching_to_sdxl_reveals_text_encoder_2_stop_training(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        self.assertFalse(training_page.text_encoder_2_stop_training_mode_combo.isHidden())
        self.assertFalse(training_page.text_encoder_2_stop_training_label.isHidden())

    def test_text_encoder_2_stop_training_persists_domain_and_json_across_temporary_sd15_switch(self):
        # I: the full round-trip contract from this mission's own closing
        # audit — SDXL configure -> switch SD1.5 (Domain persists, UI
        # hidden, JSON omits TE2) -> switch back SDXL (Domain/UI/JSON all
        # restored exactly).
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.base_model_edit.setText("models/sd_xl_base_1.0.safetensors")
        training_page.text_encoder_2_stop_training_mode_combo.setCurrentIndex(
            training_page.text_encoder_2_stop_training_mode_combo.findData(
                _STOP_TRAINING_STOP_AFTER
            )
        )
        training_page.text_encoder_2_stop_training_unit_combo.setCurrentIndex(
            training_page.text_encoder_2_stop_training_unit_combo.findData("EPOCH")
        )
        training_page.text_encoder_2_stop_training_value_spinbox.setValue(5)
        training_page.save_training_parameters()

        # --- switch to SD1.5 ---
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.text_encoder_2_stop_training_mode, "EPOCH")
        self.assertEqual(training.onetrainer_settings.text_encoder_2_stop_training_after, 5)
        self.assertTrue(training_page.text_encoder_2_stop_training_mode_combo.isHidden())

        result = training_manager.prepare_onetrainer_config(training.training_id)
        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("text_encoder_2", written)

        # --- switch back to SDXL ---
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)

        self.assertFalse(training_page.text_encoder_2_stop_training_mode_combo.isHidden())
        self.assertEqual(
            training_page.text_encoder_2_stop_training_mode_combo.currentData(),
            _STOP_TRAINING_STOP_AFTER,
        )
        self.assertEqual(
            training_page.text_encoder_2_stop_training_unit_combo.currentData(), "EPOCH"
        )
        self.assertEqual(training_page.text_encoder_2_stop_training_value_spinbox.value(), 5)

        training_page.save_training_parameters()
        result = training_manager.prepare_onetrainer_config(training.training_id)
        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(
            written["text_encoder_2"],
            {"stop_training_after": 5, "stop_training_after_unit": "EPOCH"},
        )

    def test_text_encoder_2_dtype_and_train_survive_save_reload_and_architecture_return(self):
        # Mission 129 section 8/17 item D: the persistence must not
        # depend on widgets staying alive in the same TrainingPage
        # instance — Save while SD1.5 is selected, a full reload
        # (update_trainings(), simulating closing/reopening the project),
        # then switching back to SDXL, must all still restore the exact
        # same values from the serialized Domain alone.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        training_page.base_model_edit.setText("models/sd_xl_base_1.0.safetensors")
        training_page.text_encoder_2_weight_dtype_combo.setCurrentIndex(
            training_page.text_encoder_2_weight_dtype_combo.findData("FLOAT_16")
        )
        training_page.text_encoder_2_train_combo.setCurrentIndex(
            training_page.text_encoder_2_train_combo.findData(True)
        )
        training_page.save_training_parameters()

        # --- switch to SD1.5, Save while incompatible ---
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.text_encoder_2_weight_dtype, "FLOAT_16")
        self.assertIs(training.onetrainer_settings.text_encoder_2_train, True)

        # --- simulate closing/reopening the project: full reload ---
        training_page.update_trainings()

        self.assertEqual(training.onetrainer_settings.text_encoder_2_weight_dtype, "FLOAT_16")
        self.assertIs(training.onetrainer_settings.text_encoder_2_train, True)
        self.assertTrue(training_page.text_encoder_2_weight_dtype_combo.isHidden())

        # --- switch back to SDXL: UI must reveal the reloaded values ---
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(training_page.text_encoder_2_weight_dtype_combo.currentData(), "FLOAT_16")
        self.assertIs(training_page.text_encoder_2_train_combo.currentData(), True)

        training_page.save_training_parameters()
        result = training_manager.prepare_onetrainer_config(training.training_id)
        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(written["text_encoder_2"], {"weight_dtype": "FLOAT_16", "train": True})

    def test_flow_matching_fields_survive_save_reload_and_architecture_return(self):
        # Mission 129 section 8/17 item D, flow-matching variant.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        dataset, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        image_path = Path(self.tmp_dir) / "a.png"
        image_path.write_bytes(b"fake")
        dataset.images = [Image(image_id="i1", file_path=str(image_path))]

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        training_page.base_model_edit.setText("black-forest-labs/FLUX.1-dev")
        training_page.timestep_distribution_combo.setCurrentIndex(
            training_page.timestep_distribution_combo.findData("LOGIT_NORMAL")
        )
        training_page.dynamic_timestep_shifting_combo.setCurrentIndex(
            training_page.dynamic_timestep_shifting_combo.findData(True)
        )
        training_page.timestep_shift_checkbox.setChecked(True)
        training_page.timestep_shift_spinbox.setValue(1.0)
        training_page.save_training_parameters()

        # --- switch to SD1.5, Save while incompatible ---
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.timestep_distribution, "LOGIT_NORMAL")
        self.assertIs(training.onetrainer_settings.dynamic_timestep_shifting, True)
        self.assertEqual(training.onetrainer_settings.timestep_shift, 1.0)

        # --- simulate closing/reopening the project: full reload ---
        training_page.update_trainings()

        self.assertEqual(training.onetrainer_settings.timestep_distribution, "LOGIT_NORMAL")
        self.assertIs(training.onetrainer_settings.dynamic_timestep_shifting, True)
        self.assertEqual(training.onetrainer_settings.timestep_shift, 1.0)
        self.assertTrue(training_page.timestep_distribution_combo.isHidden())

        # --- switch back to FLUX: UI must reveal the reloaded values ---
        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertEqual(training_page.timestep_distribution_combo.currentData(), "LOGIT_NORMAL")
        self.assertIs(training_page.dynamic_timestep_shifting_combo.currentData(), True)
        self.assertTrue(training_page.timestep_shift_checkbox.isChecked())

        training_page.save_training_parameters()
        result = training_manager.prepare_onetrainer_config(training.training_id)
        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(written["timestep_distribution"], "LOGIT_NORMAL")
        self.assertIs(written["dynamic_timestep_shifting"], True)
        self.assertEqual(written["timestep_shift"], 1.0)


class TrainingPageScrollableContentTest(unittest.TestCase):
    """
    Post-M121 correctif (hors périmètre M121 lui-même) : l'ajout de la
    section "Advanced settings" a fait dépasser la hauteur totale de
    TrainingPage au-delà d'une fenêtre normale, rendant le bas de la page
    (dont la zone "Résultats des entraînements" et les deux boutons
    d'action sous elle) physiquement inatteignable sans mécanisme de
    défilement — observé réellement par l'architecte (capture d'écran).
    Même symptôme, même solution robuste que le mini-correctif déjà
    appliqué à SettingsPage (hors périmètre Mission 115) — voir
    SettingsPageScrollableContentTest dans test_settings_page.py, dont
    ces tests reprennent le même pattern, étendu ici par une preuve
    réelle de dépassement de viewport (fenêtre réduite) puisque ce
    correctif a spécifiquement été demandé pour prouver un scénario de
    hauteur insuffisante, pas seulement la présence du mécanisme.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "TrainingScrollProject"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )
        return workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _create_selected_training(
        self, workspace_manager, character_manager, dataset_manager, training_manager
    ):
        workspace_manager.create(self.folder)
        character = character_manager.create("Aria")
        character_manager.select(character.character_id)
        dataset = dataset_manager.create("Portraits")
        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        return dataset, training

    def test_page_content_is_wrapped_in_a_resizable_scroll_area(self):
        _, _, _, _, training_page = self._wire()

        scroll_areas = training_page.findChildren(QScrollArea)
        self.assertEqual(len(scroll_areas), 1)
        self.assertTrue(scroll_areas[0].widgetResizable())

    def test_jobs_list_and_last_buttons_are_reachable_inside_the_scroll_area(self):
        _, _, _, _, training_page = self._wire()

        scroll_area = training_page.findChildren(QScrollArea)[0]
        scrolled_widget = scroll_area.widget()
        self.assertIsNotNone(scrolled_widget)
        # Reachability must come from the scrolled content, not from
        # TrainingPage's own top-level (fixed, non-scrolling) layout —
        # otherwise these widgets would still be clipped exactly like the
        # architect's real screenshot showed for the "Résultats des
        # entraînements" zone and everything under it.
        self.assertIn(training_page.jobs_list, scrolled_widget.findChildren(QListWidget))
        self.assertIn(training_page.import_lora_button, scrolled_widget.findChildren(QPushButton))
        self.assertIn(
            training_page.use_lora_in_inference_button, scrolled_widget.findChildren(QPushButton)
        )
        # Mission 122: the new Optimizer combo, added inside the same
        # Advanced settings container, must also be reachable from the
        # scrolled content — the post-M121 scroll fix must not need any
        # change for this mission's own additional widget.
        self.assertIn(training_page.optimizer_combo, scrolled_widget.findChildren(QComboBox))

    def test_content_overflows_a_reduced_window_and_bottom_is_reachable_via_scroll(self):
        _, _, _, _, training_page = self._wire()

        # A deliberately short window, well below TrainingPage's own real
        # content height even with Advanced settings folded — reproduces
        # the architect's real report (le bas de la page sort de l'écran).
        training_page.resize(800, 200)
        training_page.show()
        QApplication.processEvents()

        try:
            scroll_area = training_page.findChildren(QScrollArea)[0]
            content_widget = scroll_area.widget()

            self.assertGreater(content_widget.height(), scroll_area.viewport().height())

            scrollbar = scroll_area.verticalScrollBar()
            self.assertGreater(scrollbar.maximum(), 0)

            # The bottom of the content must be genuinely reachable by
            # scrolling all the way down, not merely theoretically present
            # in a taller-than-viewport widget.
            scrollbar.setValue(scrollbar.maximum())
            self.assertEqual(scrollbar.value(), scrollbar.maximum())
        finally:
            training_page.close()

    def test_opening_advanced_settings_increases_required_height_closing_recomputes_it(self):
        _, _, _, _, training_page = self._wire()

        training_page.resize(800, 900)
        training_page.show()
        QApplication.processEvents()

        try:
            content_widget = training_page.findChildren(QScrollArea)[0].widget()

            folded_height = content_widget.sizeHint().height()

            training_page.advanced_settings_toggle.setChecked(True)
            QApplication.processEvents()
            expanded_height = content_widget.sizeHint().height()

            self.assertGreater(expanded_height, folded_height)

            training_page.advanced_settings_toggle.setChecked(False)
            QApplication.processEvents()
            refolded_height = content_widget.sizeHint().height()

            self.assertEqual(refolded_height, folded_height)
        finally:
            training_page.close()

    def test_toggling_advanced_settings_inside_a_short_window_never_marks_dirty(self):
        # Regression guard: the scroll-area wrapping must never disturb
        # the pre-existing no-dirty-state-from-folding contract (Mission
        # 121 section 7), including under the exact short-window
        # condition that motivated this correctif.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = (
            self._wire()
        )
        self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )

        training_page.resize(800, 200)
        training_page.show()
        QApplication.processEvents()

        try:
            self.assertFalse(training_page._dirty)
            training_page.advanced_settings_toggle.setChecked(True)
            QApplication.processEvents()
            self.assertFalse(training_page._dirty)
            training_page.advanced_settings_toggle.setChecked(False)
            QApplication.processEvents()
            self.assertFalse(training_page._dirty)
        finally:
            training_page.close()

    # --- Mission 127: Gradient checkpointing -----------------------------

    def test_gradient_checkpointing_defaults_to_not_configured(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        self.assertEqual(training_page.gradient_checkpointing_combo.currentData(), "")

    def test_gradient_checkpointing_combo_marks_dirty_on_change(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page._dirty = False

        training_page.gradient_checkpointing_combo.setCurrentIndex(
            training_page.gradient_checkpointing_combo.findData("ON")
        )

        self.assertTrue(training_page._dirty)

    def test_gradient_checkpointing_four_states_round_trip_through_reload(self):
        # L/N: the 4 states (Non configuré/OFF/ON/CPU_OFFLOADED), each
        # saved and restored correctly across a save -> reload cycle.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        for value in ("OFF", "ON", "CPU_OFFLOADED", ""):
            with self.subTest(value=value):
                training_page.gradient_checkpointing_combo.setCurrentIndex(
                    training_page.gradient_checkpointing_combo.findData(value)
                )
                training_page.save_training_parameters()

                training_page.update_trainings()

                self.assertEqual(training_page.gradient_checkpointing_combo.currentData(), value)

    def test_gradient_checkpointing_visible_and_unchanged_across_every_architecture(self):
        # O: generic to every architecture — never hidden, never reset,
        # unlike the FLUX-only Flow-matching combos of Mission 126.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._create_selected_training(workspace_manager, character_manager, dataset_manager, training_manager)

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        training_page.gradient_checkpointing_combo.setCurrentIndex(
            training_page.gradient_checkpointing_combo.findData("CPU_OFFLOADED")
        )
        self.assertFalse(training_page.gradient_checkpointing_combo.isHidden())

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL)
        self.assertFalse(training_page.gradient_checkpointing_combo.isHidden())
        self.assertEqual(training_page.gradient_checkpointing_combo.currentData(), "CPU_OFFLOADED")

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_FLUX)
        self.assertFalse(training_page.gradient_checkpointing_combo.isHidden())
        self.assertEqual(training_page.gradient_checkpointing_combo.currentData(), "CPU_OFFLOADED")

        training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SD15)
        self.assertFalse(training_page.gradient_checkpointing_combo.isHidden())
        self.assertEqual(training_page.gradient_checkpointing_combo.currentData(), "CPU_OFFLOADED")

    def test_gradient_checkpointing_cohabits_with_train_dtype_and_dtype_fields(self):
        # Q: UI-level cohabitation check — saving gradient_checkpointing
        # alongside train_dtype/component dtypes must never overwrite,
        # or be overwritten by, any of them.
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        _, training = self._create_selected_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.train_dtype_combo.setCurrentIndex(
            training_page.train_dtype_combo.findData("FLOAT_16")
        )
        training_page.gradient_checkpointing_combo.setCurrentIndex(
            training_page.gradient_checkpointing_combo.findData("ON")
        )
        training_page.main_model_weight_dtype_combo.setCurrentIndex(
            training_page.main_model_weight_dtype_combo.findData("FLOAT_16")
        )

        training_page.save_training_parameters()

        self.assertEqual(training.onetrainer_settings.train_dtype, "FLOAT_16")
        self.assertEqual(training.onetrainer_settings.gradient_checkpointing_mode, "ON")
        self.assertEqual(training.onetrainer_settings.unet_weight_dtype, "FLOAT_16")


class TrainingManagerUpdateTest(unittest.TestCase):
    """
    Mission 097: TrainingManager.update() — same combined-multi-field,
    strictly idempotent, rollback-on-save-failure contract as
    LoRAManager.update() (Mission 073), adapted to act on
    self.active_training (this Manager's own existing convention,
    established by update_name()).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)

    def test_update_sets_every_field(self):
        result = self.training_manager.update(
            base_model_source="models/base.safetensors",
            architecture=TRAINING_ARCHITECTURE_SDXL,
            resolution=1024,
            epochs=50,
            learning_rate=0.0005,
            lora_rank=32,
            lora_alpha=2.0,
            trigger_word="ohwx",
            batch_size=4,
            gradient_accumulation_steps=2,
            learning_rate_scheduler="COSINE",
            train_dtype="FLOAT_16",
            gradient_checkpointing_mode="ON",
            unet_weight_dtype="FLOAT_16",
            transformer_weight_dtype="BFLOAT_16",
            text_encoder_weight_dtype="FLOAT_16",
            text_encoder_2_weight_dtype="FLOAT_16",
            vae_weight_dtype="FLOAT_32",
            optimizer="ADAMW",
            text_encoder_train=False,
            text_encoder_2_train=True,
            text_encoder_stop_training_mode="EPOCH",
            text_encoder_stop_training_after=10,
            text_encoder_2_stop_training_mode="NEVER",
            lora_layer_filter="ATTN_MLP",
        )

        self.assertTrue(result)
        self.assertEqual(self.training.base_model_source, "models/base.safetensors")
        self.assertEqual(self.training.architecture, TRAINING_ARCHITECTURE_SDXL)
        self.assertEqual(self.training.resolution, 1024)
        self.assertEqual(self.training.epochs, 50)
        self.assertEqual(self.training.learning_rate, 0.0005)
        self.assertEqual(self.training.lora_rank, 32)
        self.assertEqual(self.training.lora_alpha, 2.0)
        self.assertEqual(self.training.trigger_word, "ohwx")
        self.assertEqual(self.training.batch_size, 4)
        self.assertEqual(self.training.gradient_accumulation_steps, 2)
        self.assertEqual(self.training.onetrainer_settings.learning_rate_scheduler, "COSINE")
        self.assertEqual(self.training.onetrainer_settings.train_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")
        self.assertEqual(self.training.onetrainer_settings.unet_weight_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.transformer_weight_dtype, "BFLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.text_encoder_weight_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.text_encoder_2_weight_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.vae_weight_dtype, "FLOAT_32")
        self.assertEqual(self.training.onetrainer_settings.optimizer_settings.optimizer, "ADAMW")
        self.assertIs(self.training.onetrainer_settings.text_encoder_train, False)
        self.assertIs(self.training.onetrainer_settings.text_encoder_2_train, True)
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_stop_training_mode, "EPOCH"
        )
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 10)
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_2_stop_training_mode, "NEVER"
        )
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_2_stop_training_after)
        self.assertEqual(self.training.onetrainer_settings.lora_layer_filter, "ATTN_MLP")

    # --- Mission 124: _UNSET sentinel (L) --------------------------------

    def test_omitting_text_encoder_train_leaves_it_untouched(self):
        self.training_manager.update(text_encoder_train=True)
        self.assertIs(self.training.onetrainer_settings.text_encoder_train, True)

        # A later call that never mentions text_encoder_train at all
        # must leave it exactly as it was — the _UNSET default, never
        # confused with the real value None.
        result = self.training_manager.update(epochs=42)
        self.assertTrue(result)
        self.assertIs(self.training.onetrainer_settings.text_encoder_train, True)

    def test_explicit_none_resets_text_encoder_train_to_not_configured(self):
        self.training_manager.update(text_encoder_train=True)
        self.assertIs(self.training.onetrainer_settings.text_encoder_train, True)

        # Explicitly passing None must be treated as a real, deliberate
        # value ("reset to not configured") — never silently
        # interpreted as "argument not provided to this call".
        result = self.training_manager.update(text_encoder_train=None)

        self.assertTrue(result)
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_train)

    def test_explicit_none_resets_text_encoder_2_train_to_not_configured(self):
        self.training_manager.update(text_encoder_2_train=False)
        self.assertIs(self.training.onetrainer_settings.text_encoder_2_train, False)

        result = self.training_manager.update(text_encoder_2_train=None)

        self.assertTrue(result)
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_2_train)

    def test_resetting_to_none_is_idempotent(self):
        # Already None -> explicitly passing None again changes nothing,
        # same idempotence contract as every other field on this method.
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_train)

        result = self.training_manager.update(text_encoder_train=None)

        self.assertFalse(result)

    def test_lora_layer_filter_reset_to_empty_string_is_a_real_explicit_value(self):
        # lora_layer_filter has no _UNSET-style ambiguity (its own "not
        # configured" sentinel, "", is already distinct from None) —
        # confirmed explicitly here for symmetry with the two tests above.
        self.training_manager.update(lora_layer_filter="ATTN_MLP")
        self.assertEqual(self.training.onetrainer_settings.lora_layer_filter, "ATTN_MLP")

        result = self.training_manager.update(lora_layer_filter="")

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.lora_layer_filter, "")

    def test_update_batch_size_and_scheduler_alone_does_not_disturb_extra_overrides(self):
        # Mission 120: learning_rate_scheduler is rolled back/updated on
        # the *same* nested OneTrainerSettings instance, never by
        # replacing it wholesale — an unrelated extra_overrides already
        # present must survive untouched.
        self.training.onetrainer_settings.extra_overrides = {"loss_weight_fn": "MIN_SNR_GAMMA"}

        result = self.training_manager.update(learning_rate_scheduler="LINEAR")

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.learning_rate_scheduler, "LINEAR")
        self.assertEqual(
            self.training.onetrainer_settings.extra_overrides,
            {"loss_weight_fn": "MIN_SNR_GAMMA"},
        )

    def test_update_dtype_fields_alone_does_not_disturb_extra_overrides_or_scheduler(self):
        # Mission 121: same nested-object mutation contract as
        # learning_rate_scheduler — updating only the new dtype fields
        # must never disturb an unrelated extra_overrides or an
        # already-configured scheduler on the same OneTrainerSettings.
        self.training.onetrainer_settings.extra_overrides = {"loss_weight_fn": "MIN_SNR_GAMMA"}
        self.training_manager.update(learning_rate_scheduler="COSINE")

        result = self.training_manager.update(
            train_dtype="FLOAT_16", unet_weight_dtype="FLOAT_16", vae_weight_dtype="FLOAT_32"
        )

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.train_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.unet_weight_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.vae_weight_dtype, "FLOAT_32")
        self.assertEqual(self.training.onetrainer_settings.learning_rate_scheduler, "COSINE")
        self.assertEqual(
            self.training.onetrainer_settings.extra_overrides,
            {"loss_weight_fn": "MIN_SNR_GAMMA"},
        )

    def test_update_optimizer_alone_does_not_disturb_extra_overrides_or_dtype_fields(self):
        # Mission 122: optimizer is mutated in place on
        # onetrainer_settings.optimizer_settings, never by replacing that
        # nested object wholesale — its own extra_overrides (not yet
        # UI-editable, but settable directly on the Domain object) and
        # an unrelated dtype field must survive untouched.
        self.training.onetrainer_settings.extra_overrides = {"loss_weight_fn": "MIN_SNR_GAMMA"}
        self.training.onetrainer_settings.optimizer_settings.extra_overrides = {
            "weight_decay": 0.01
        }
        self.training_manager.update(train_dtype="FLOAT_16")

        result = self.training_manager.update(optimizer="SGD")

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.optimizer_settings.optimizer, "SGD")
        self.assertEqual(
            self.training.onetrainer_settings.optimizer_settings.extra_overrides,
            {"weight_decay": 0.01},
        )
        self.assertEqual(self.training.onetrainer_settings.train_dtype, "FLOAT_16")
        self.assertEqual(
            self.training.onetrainer_settings.extra_overrides,
            {"loss_weight_fn": "MIN_SNR_GAMMA"},
        )

    def test_update_is_idempotent_for_the_new_mission_122_field(self):
        self.training_manager.update(optimizer="ADAMW")

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update(optimizer="ADAMW")
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update(resolution=768)
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_is_idempotent(self):
        self.training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15, resolution=512)

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update(architecture=TRAINING_ARCHITECTURE_SD15, resolution=512)
            self.assertFalse(result)
            save_spy.assert_not_called()

    def test_update_is_idempotent_for_the_new_mission_120_fields(self):
        self.training_manager.update(
            batch_size=4, gradient_accumulation_steps=2, learning_rate_scheduler="COSINE"
        )

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update(
                batch_size=4, gradient_accumulation_steps=2, learning_rate_scheduler="COSINE"
            )
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update(resolution=768)
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_is_idempotent_for_the_new_mission_121_fields(self):
        self.training_manager.update(
            train_dtype="FLOAT_16", unet_weight_dtype="FLOAT_16", vae_weight_dtype="FLOAT_32"
        )

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update(
                train_dtype="FLOAT_16", unet_weight_dtype="FLOAT_16", vae_weight_dtype="FLOAT_32"
            )
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update(resolution=768)
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_leaves_untouched_fields_alone(self):
        self.training_manager.update(trigger_word="ohwx")

        self.training_manager.update(epochs=10)

        self.assertEqual(self.training.trigger_word, "ohwx")

    def test_update_without_active_training_returns_false(self):
        self.training_manager.active_training_id = None

        result = self.training_manager.update(trigger_word="anything")

        self.assertFalse(result)

    def test_update_save_failure_restores_every_field_on_the_same_object(self):
        self.training_manager.update(
            architecture=TRAINING_ARCHITECTURE_SD15, resolution=512, trigger_word="x",
            batch_size=1, gradient_accumulation_steps=1, learning_rate_scheduler="CONSTANT",
            train_dtype="FLOAT_16", unet_weight_dtype="FLOAT_16",
            text_encoder_weight_dtype="FLOAT_16", vae_weight_dtype="FLOAT_32",
            optimizer="ADAMW",
        )

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update(
                    architecture=TRAINING_ARCHITECTURE_SDXL, resolution=1024, trigger_word="y",
                    batch_size=8, gradient_accumulation_steps=4, learning_rate_scheduler="COSINE",
                    train_dtype="BFLOAT_16", unet_weight_dtype="BFLOAT_16",
                    text_encoder_weight_dtype="BFLOAT_16", vae_weight_dtype="FLOAT_16",
                    optimizer="SGD",
                )

        self.assertEqual(self.training.architecture, TRAINING_ARCHITECTURE_SD15)
        self.assertEqual(self.training.resolution, 512)
        self.assertEqual(self.training.trigger_word, "x")
        self.assertEqual(self.training.batch_size, 1)
        self.assertEqual(self.training.gradient_accumulation_steps, 1)
        self.assertEqual(self.training.onetrainer_settings.learning_rate_scheduler, "CONSTANT")
        self.assertEqual(self.training.onetrainer_settings.train_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.unet_weight_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.text_encoder_weight_dtype, "FLOAT_16")
        self.assertEqual(self.training.onetrainer_settings.vae_weight_dtype, "FLOAT_32")
        self.assertEqual(self.training.onetrainer_settings.optimizer_settings.optimizer, "ADAMW")
        self.assertIs(self.training_manager.active_training, self.training)

    # --- Mission 126: timestep_distribution / dynamic_timestep_shifting /
    # timestep_shift (_UNSET sentinel, D) --------------------------------

    def test_update_sets_flow_matching_fields(self):
        result = self.training_manager.update(
            architecture=TRAINING_ARCHITECTURE_FLUX,
            timestep_distribution="LOGIT_NORMAL",
            dynamic_timestep_shifting=True,
            timestep_shift=1.5,
        )

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.timestep_distribution, "LOGIT_NORMAL")
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, True)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.5)

    def test_omitting_dynamic_timestep_shifting_leaves_it_untouched(self):
        self.training_manager.update(dynamic_timestep_shifting=True)
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, True)

        # A later call that never mentions dynamic_timestep_shifting at
        # all must leave it exactly as it was — the _UNSET default,
        # never confused with the real value None.
        result = self.training_manager.update(epochs=42)
        self.assertTrue(result)
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, True)

    def test_explicit_none_resets_dynamic_timestep_shifting_to_not_configured(self):
        self.training_manager.update(dynamic_timestep_shifting=True)
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, True)

        # Explicitly passing None must be treated as a real, deliberate
        # value ("reset to not configured") — never silently interpreted
        # as "argument not provided to this call".
        result = self.training_manager.update(dynamic_timestep_shifting=None)

        self.assertTrue(result)
        self.assertIsNone(self.training.onetrainer_settings.dynamic_timestep_shifting)

    def test_resetting_dynamic_timestep_shifting_to_none_is_idempotent(self):
        self.assertIsNone(self.training.onetrainer_settings.dynamic_timestep_shifting)

        result = self.training_manager.update(dynamic_timestep_shifting=None)

        self.assertFalse(result)

    def test_omitting_timestep_shift_leaves_it_untouched(self):
        self.training_manager.update(timestep_shift=1.0)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.0)

        result = self.training_manager.update(epochs=42)
        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.0)

    def test_explicit_none_resets_timestep_shift_to_not_configured(self):
        self.training_manager.update(timestep_shift=1.0)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.0)

        result = self.training_manager.update(timestep_shift=None)

        self.assertTrue(result)
        self.assertIsNone(self.training.onetrainer_settings.timestep_shift)

    def test_resetting_timestep_shift_to_none_is_idempotent(self):
        self.assertIsNone(self.training.onetrainer_settings.timestep_shift)

        result = self.training_manager.update(timestep_shift=None)

        self.assertFalse(result)

    def test_timestep_shift_one_point_zero_explicit_is_distinct_from_unset(self):
        # F: 1.0 explicit must be genuinely persisted, never conflated
        # with "not configured" — the _UNSET-vs-None distinction at this
        # layer, mirroring the ""-vs-real-value distinction elsewhere.
        result = self.training_manager.update(timestep_shift=1.0)

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.0)
        self.assertIsNotNone(self.training.onetrainer_settings.timestep_shift)

    def test_timestep_distribution_reset_to_empty_string_is_a_real_explicit_value(self):
        # timestep_distribution has no _UNSET-style ambiguity (its own
        # "not configured" sentinel, "", is already distinct from None)
        # — same symmetry already confirmed for lora_layer_filter above.
        self.training_manager.update(timestep_distribution="LOGIT_NORMAL")
        self.assertEqual(self.training.onetrainer_settings.timestep_distribution, "LOGIT_NORMAL")

        result = self.training_manager.update(timestep_distribution="")

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.timestep_distribution, "")

    # G: dynamic_timestep_shifting and timestep_shift are independent —
    # configuring/resetting one on the Manager never mutates or clears
    # the other, even though OneTrainer itself ignores timestep_shift at
    # runtime when dynamic_timestep_shifting=True.

    def test_dynamic_timestep_shifting_and_timestep_shift_are_independent(self):
        self.training_manager.update(dynamic_timestep_shifting=True, timestep_shift=1.5)

        result = self.training_manager.update(dynamic_timestep_shifting=False)

        self.assertTrue(result)
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, False)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.5)

    def test_update_flow_matching_fields_alone_does_not_disturb_extra_overrides(self):
        self.training.onetrainer_settings.extra_overrides = {"loss_weight_fn": "MIN_SNR_GAMMA"}

        result = self.training_manager.update(
            timestep_distribution="UNIFORM", dynamic_timestep_shifting=False, timestep_shift=1.0,
        )

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.timestep_distribution, "UNIFORM")
        self.assertEqual(
            self.training.onetrainer_settings.extra_overrides,
            {"loss_weight_fn": "MIN_SNR_GAMMA"},
        )

    def test_update_is_idempotent_for_the_new_mission_126_fields(self):
        self.training_manager.update(
            timestep_distribution="LOGIT_NORMAL",
            dynamic_timestep_shifting=True,
            timestep_shift=1.0,
        )

        with patch.object(self.workspace_manager, "save", wraps=self.workspace_manager.save) as save_spy:
            result = self.training_manager.update(
                timestep_distribution="LOGIT_NORMAL",
                dynamic_timestep_shifting=True,
                timestep_shift=1.0,
            )
            self.assertFalse(result)
            save_spy.assert_not_called()

            result = self.training_manager.update(resolution=768)
            self.assertTrue(result)
            save_spy.assert_called_once()

    def test_update_save_failure_restores_flow_matching_fields_on_the_same_object(self):
        self.training_manager.update(
            timestep_distribution="UNIFORM", dynamic_timestep_shifting=False, timestep_shift=1.0,
        )

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update(
                    timestep_distribution="LOGIT_NORMAL",
                    dynamic_timestep_shifting=True,
                    timestep_shift=1.5,
                )

        self.assertEqual(self.training.onetrainer_settings.timestep_distribution, "UNIFORM")
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, False)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.0)

    # --- Mission 127: gradient_checkpointing_mode (D) --------------------
    # Same "" sentinel contract as timestep_distribution/train_dtype
    # above — None means "leave untouched", no _UNSET needed (its own
    # "not configured" sentinel is already "", never None).

    def test_update_sets_gradient_checkpointing_mode(self):
        result = self.training_manager.update(gradient_checkpointing_mode="CPU_OFFLOADED")

        self.assertTrue(result)
        self.assertEqual(
            self.training.onetrainer_settings.gradient_checkpointing_mode, "CPU_OFFLOADED"
        )

    def test_omitting_gradient_checkpointing_mode_leaves_it_untouched(self):
        self.training_manager.update(gradient_checkpointing_mode="ON")
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")

        # update(... gradient_checkpointing_mode=None) — argument not
        # provided to this call — must conserve the existing value.
        result = self.training_manager.update(epochs=42)
        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")

    def test_explicit_empty_string_resets_gradient_checkpointing_mode(self):
        self.training_manager.update(gradient_checkpointing_mode="ON")
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")

        # update(... gradient_checkpointing_mode="") — explicit reset to
        # "not configured" — must be treated as a real, deliberate value,
        # never confused with "argument not provided" (that is None).
        result = self.training_manager.update(gradient_checkpointing_mode="")

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "")

    def test_gradient_checkpointing_mode_none_vs_empty_string_distinction(self):
        # Exact contract required by MISSION_127.md section 1.B, reproduced
        # literally: starting from "ON", None conserves it, "" resets it.
        self.training_manager.update(gradient_checkpointing_mode="ON")
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")

        result_none = self.training_manager.update(gradient_checkpointing_mode=None)
        self.assertFalse(result_none)
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")

        result_empty = self.training_manager.update(gradient_checkpointing_mode="")
        self.assertTrue(result_empty)
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "")

    def test_resetting_gradient_checkpointing_mode_to_empty_string_is_idempotent(self):
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "")

        result = self.training_manager.update(gradient_checkpointing_mode="")

        self.assertFalse(result)

    def test_update_gradient_checkpointing_mode_alone_does_not_disturb_extra_overrides(self):
        self.training.onetrainer_settings.extra_overrides = {"loss_weight_fn": "MIN_SNR_GAMMA"}

        result = self.training_manager.update(gradient_checkpointing_mode="OFF")

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "OFF")
        self.assertEqual(
            self.training.onetrainer_settings.extra_overrides,
            {"loss_weight_fn": "MIN_SNR_GAMMA"},
        )

    def test_update_save_failure_restores_gradient_checkpointing_mode_on_the_same_object(self):
        self.training_manager.update(gradient_checkpointing_mode="ON")

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update(gradient_checkpointing_mode="CPU_OFFLOADED")

        self.assertEqual(self.training.onetrainer_settings.gradient_checkpointing_mode, "ON")

    # --- Mission 128: text_encoder_stop_training_mode/_after -------------

    def test_update_sets_text_encoder_stop_training_mode(self):
        result = self.training_manager.update(text_encoder_stop_training_mode="NEVER")
        self.assertTrue(result)
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_stop_training_mode, "NEVER"
        )

    def test_omitting_text_encoder_stop_training_mode_leaves_it_untouched(self):
        self.training_manager.update(text_encoder_stop_training_mode="NEVER")
        result = self.training_manager.update(epochs=42)
        self.assertTrue(result)
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_stop_training_mode, "NEVER"
        )

    def test_explicit_empty_string_resets_text_encoder_stop_training_mode(self):
        self.training_manager.update(text_encoder_stop_training_mode="NEVER")
        result = self.training_manager.update(text_encoder_stop_training_mode="")
        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_mode, "")

    # C. update() without the after argument conserves the current value.

    def test_omitting_text_encoder_stop_training_after_leaves_it_untouched(self):
        self.training_manager.update(text_encoder_stop_training_after=10)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 10)

        result = self.training_manager.update(epochs=42)

        self.assertTrue(result)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 10)

    # D. update(after=None) explicitly resets it to None.

    def test_explicit_none_resets_text_encoder_stop_training_after(self):
        self.training_manager.update(text_encoder_stop_training_after=10)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 10)

        result = self.training_manager.update(text_encoder_stop_training_after=None)

        self.assertTrue(result)
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_stop_training_after)

    def test_text_encoder_stop_training_after_none_vs_unfollowed_distinction(self):
        # Literal reproduction of the exact contract from MISSION_128.md
        # section 2/5: from after=10, an omitted argument conserves 10,
        # an explicit None resets to None, and a new int reassigns.
        self.training_manager.update(text_encoder_stop_training_after=10)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 10)

        self.training_manager.update(epochs=1)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 10)

        self.training_manager.update(text_encoder_stop_training_after=None)
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_stop_training_after)

        self.training_manager.update(text_encoder_stop_training_after=5)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 5)

    def test_resetting_text_encoder_stop_training_after_to_none_is_idempotent(self):
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_stop_training_after)

        result = self.training_manager.update(text_encoder_stop_training_after=None)

        self.assertFalse(result)

    def test_explicit_none_resets_text_encoder_2_stop_training_after(self):
        self.training_manager.update(text_encoder_2_stop_training_after=3)
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_2_stop_training_after, 3
        )

        result = self.training_manager.update(text_encoder_2_stop_training_after=None)

        self.assertTrue(result)
        self.assertIsNone(self.training.onetrainer_settings.text_encoder_2_stop_training_after)

    def test_update_stop_training_fields_alone_does_not_disturb_extra_overrides(self):
        self.training.onetrainer_settings.extra_overrides = {"custom_key": "custom_value"}

        self.training_manager.update(
            text_encoder_stop_training_mode="EPOCH", text_encoder_stop_training_after=10
        )

        self.assertEqual(
            self.training.onetrainer_settings.extra_overrides, {"custom_key": "custom_value"}
        )

    # E. rollback restores mode + after together, on the same object.

    def test_update_save_failure_restores_text_encoder_stop_training_fields_on_the_same_object(self):
        self.training_manager.update(
            text_encoder_stop_training_mode="EPOCH", text_encoder_stop_training_after=7
        )

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update(
                    text_encoder_stop_training_mode="NEVER",
                    text_encoder_stop_training_after=None,
                )

        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_stop_training_mode, "EPOCH"
        )
        self.assertEqual(self.training.onetrainer_settings.text_encoder_stop_training_after, 7)

    def test_update_save_failure_restores_text_encoder_2_stop_training_fields_on_the_same_object(self):
        self.training_manager.update(
            text_encoder_2_stop_training_mode="STEP", text_encoder_2_stop_training_after=50
        )

        with patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update(text_encoder_2_stop_training_mode="")

        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_2_stop_training_mode, "STEP"
        )
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_2_stop_training_after, 50
        )


class ValidateBaseModelSourceTest(unittest.TestCase):
    """
    Mission 106: direct, Qt-free tests of src.utils.base_model_source.
    validate_base_model_source() — no Manager, no Page, no Domain
    involved. Covers exactly the forms audited before this mission's
    contract (MISSION_106.md section 1/3.2): empty/whitespace-only and
    an absolute Windows path (backslash, forward-slash, and UNC — all
    three confirmed equally "absolute" by os.path.isabs() on this
    machine) that does not exist are rejected; an existing file, an
    existing directory (simulating a Diffusers folder), a relative
    string, and a Hugging Face identifier are all accepted without any
    filesystem existence check and without any network access.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_empty_string_is_rejected(self):
        with self.assertRaises(InvalidBaseModelSourceError):
            validate_base_model_source("")

    def test_whitespace_only_is_rejected(self):
        with self.assertRaises(InvalidBaseModelSourceError):
            validate_base_model_source("   ")

    def test_missing_windows_backslash_absolute_path_is_rejected(self):
        missing = str(Path(self.tmp_dir) / "missing.safetensors")
        self.assertTrue(os.path.isabs(missing))
        with self.assertRaises(InvalidBaseModelSourceError):
            validate_base_model_source(missing)

    def test_missing_windows_forward_slash_absolute_path_is_rejected(self):
        missing = str(Path(self.tmp_dir) / "missing.safetensors").replace("\\", "/")
        self.assertTrue(os.path.isabs(missing))
        with self.assertRaises(InvalidBaseModelSourceError):
            validate_base_model_source(missing)

    def test_missing_unc_absolute_path_is_rejected(self):
        missing = r"\\nonexistent-server-xyz-12345\share\missing.safetensors"
        self.assertTrue(os.path.isabs(missing))
        with self.assertRaises(InvalidBaseModelSourceError):
            validate_base_model_source(missing)

    def test_existing_absolute_file_is_accepted(self):
        checkpoint = Path(self.tmp_dir) / "checkpoint.safetensors"
        checkpoint.write_bytes(b"fake-checkpoint-bytes")

        validate_base_model_source(str(checkpoint))  # must not raise

    def test_existing_absolute_directory_is_accepted(self):
        # Simulates a local Diffusers folder — never rejected, even
        # though it is not a single file.
        diffusers_folder = Path(self.tmp_dir) / "diffusers_model"
        diffusers_folder.mkdir()

        validate_base_model_source(str(diffusers_folder))  # must not raise

    def test_relative_string_is_never_rejected_regardless_of_existence(self):
        validate_base_model_source("models/model.safetensors")  # must not raise
        validate_base_model_source("model.safetensors")  # must not raise

    def test_huggingface_identifier_is_accepted_without_any_network_access(self):
        # OneTrainer's own real default (TrainConfig.py) — confirmed by
        # this mission's audit, never a marginal case.
        validate_base_model_source("stable-diffusion-v1-5/stable-diffusion-v1-5")  # must not raise


class TrainingManagerPrepareOnetrainerConfigTest(unittest.TestCase):
    """
    Mission 097: TrainingManager.prepare_onetrainer_config() — real
    filesystem materialization (never mocked for the nominal cases) and
    real config-file generation. Never starts OneTrainer, never imports
    OneTrainer's own code — see MISSION_097.md section 7/8.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        character = self.character_manager.create("Aria")
        self.character_manager.select(character.character_id)

        self.dataset = self.dataset_manager.create("Portraits")
        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
            trigger_word="ohwx",
        )

    def _add_real_image(self, subdir_name, filename, content=b"fake-png-bytes"):
        source_dir = Path(self.tmp_dir) / subdir_name
        source_dir.mkdir(parents=True, exist_ok=True)
        path = source_dir / filename
        path.write_bytes(content)
        return Image(image_id=str(path), file_path=str(path))

    def test_materializes_real_images_with_matching_caption_sidecars(self):
        self.dataset.images = [
            self._add_real_image("SourceA", "portrait1.png", b"AAA"),
            self._add_real_image("SourceB", "portrait2.png", b"BBB"),
        ]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        produced = sorted(p.name for p in concept_folder.iterdir())
        self.assertEqual(produced, ["portrait1.png", "portrait1.txt", "portrait2.png", "portrait2.txt"])
        self.assertEqual((concept_folder / "portrait1.png").read_bytes(), b"AAA")
        self.assertEqual((concept_folder / "portrait1.txt").read_text(encoding="utf-8"), "ohwx")
        self.assertEqual((concept_folder / "portrait2.txt").read_text(encoding="utf-8"), "ohwx")

    def test_text_encoder_train_and_layer_filter_forwarded_to_written_config(self):
        # Mission 124: end-to-end through the real Manager -> real
        # written config.json, complementing the pure build_training_
        # config() unit tests in test_onetrainer_config.py.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training_manager.update(
            text_encoder_train=False, lora_layer_filter="ATTN_MLP",
        )

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(written["text_encoder"], {"train": False})
        self.assertEqual(written["layer_filter"], "attentions")
        self.assertIs(written["layer_filter_regex"], False)

    def test_pre_m124_project_json_prepares_a_config_identical_to_before_this_mission(self):
        # B: a Training loaded from a project.json written before this
        # mission (no text_encoder_train/text_encoder_2_train/
        # lora_layer_filter keys at all) must produce a config file
        # byte-for-byte identical to what this exact Training would have
        # produced before Mission 124 — the 3 new keys are entirely
        # absent from both the source data and the resulting config.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        pre_m124_settings_dict = self.training.onetrainer_settings.to_dict()
        del pre_m124_settings_dict["text_encoder_train"]
        del pre_m124_settings_dict["text_encoder_2_train"]
        del pre_m124_settings_dict["lora_layer_filter"]
        self.training.onetrainer_settings = OneTrainerSettings.from_dict(pre_m124_settings_dict)

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("text_encoder", written)
        self.assertNotIn("layer_filter", written)
        self.assertNotIn("layer_filter_regex", written)

    def test_gradient_checkpointing_mode_forwarded_to_written_config(self):
        # Mission 127 (E): end-to-end through the real Manager -> real
        # written config.json, complementing the pure build_training_
        # config() unit tests in test_onetrainer_config.py.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training_manager.update(gradient_checkpointing_mode="CPU_OFFLOADED")

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(written["gradient_checkpointing"], "CPU_OFFLOADED")

    def test_pre_m127_project_json_prepares_a_config_identical_to_before_this_mission(self):
        # P: a Training loaded from a project.json written before this
        # mission (no gradient_checkpointing_mode key at all) must
        # produce a config file byte-for-byte identical to what this
        # exact Training would have produced before Mission 127 — the
        # new key is entirely absent from both the source data and the
        # resulting config.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        pre_m127_settings_dict = self.training.onetrainer_settings.to_dict()
        del pre_m127_settings_dict["gradient_checkpointing_mode"]
        self.training.onetrainer_settings = OneTrainerSettings.from_dict(pre_m127_settings_dict)

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("gradient_checkpointing", written)

    def test_text_encoder_stop_training_forwarded_to_written_config(self):
        # Mission 128 (L): end-to-end through the real Manager -> real
        # written config.json, complementing the pure build_training_
        # config() unit tests in test_onetrainer_config.py.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training_manager.update(
            text_encoder_stop_training_mode="EPOCH", text_encoder_stop_training_after=10
        )

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(
            written["text_encoder"],
            {"stop_training_after": 10, "stop_training_after_unit": "EPOCH"},
        )

    def test_pre_m128_project_json_prepares_a_config_identical_to_before_this_mission(self):
        # L: a Training loaded from a project.json written before this
        # mission (no text_encoder_stop_training_mode/_after/
        # text_encoder_2_ counterparts keys at all) must produce a config
        # file byte-for-byte identical to what this exact Training would
        # have produced before Mission 128 — the 4 new keys are entirely
        # absent from both the source data and the resulting config.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        pre_m128_settings_dict = self.training.onetrainer_settings.to_dict()
        del pre_m128_settings_dict["text_encoder_stop_training_mode"]
        del pre_m128_settings_dict["text_encoder_stop_training_after"]
        del pre_m128_settings_dict["text_encoder_2_stop_training_mode"]
        del pre_m128_settings_dict["text_encoder_2_stop_training_after"]
        self.training.onetrainer_settings = OneTrainerSettings.from_dict(pre_m128_settings_dict)

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("text_encoder", written)

    def test_text_encoder_2_stop_training_persisted_but_omitted_from_sd15_config(self):
        # Mission 128 section 10/H/I: a Text Encoder 2 duration configured
        # while on SDXL/FLUX must survive being carried over onto a
        # Training whose architecture is currently SD1.5 (this Manager
        # never resets it — only the UI's own architecture-switch
        # handling ever would, and it deliberately does not for these two
        # fields, see training_page.py). Preparing a real SD1.5 config
        # from that exact Domain state must succeed with no TE2 stop key
        # at all, never raise.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training.onetrainer_settings.text_encoder_2_stop_training_mode = "EPOCH"
        self.training.onetrainer_settings.text_encoder_2_stop_training_after = 5
        # self.training.architecture is already SD15 (see setUp()).

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("text_encoder_2", written)
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_2_stop_training_mode, "EPOCH"
        )
        self.assertEqual(
            self.training.onetrainer_settings.text_encoder_2_stop_training_after, 5
        )

    def test_text_encoder_2_weight_dtype_persisted_but_omitted_from_sd15_config(self):
        # Mission 129 section 7/9/17 item E: same guarantee as the
        # stop-training test above, extended to text_encoder_2_
        # weight_dtype — the Manager never gated this on architecture to
        # begin with (see test_onetrainer_config.py's own translator
        # coverage); this proves the real end-to-end JSON output.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training.onetrainer_settings.text_encoder_2_weight_dtype = "FLOAT_16"

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("text_encoder_2", written)
        self.assertEqual(self.training.onetrainer_settings.text_encoder_2_weight_dtype, "FLOAT_16")

    def test_text_encoder_2_train_persisted_but_omitted_from_sd15_config(self):
        # Mission 129 section 7/9/17 item E — False specifically, to
        # prove it is never mistaken for "not configured" anywhere in
        # the real end-to-end path (Domain -> Manager -> translator).
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training.onetrainer_settings.text_encoder_2_train = False

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("text_encoder_2", written)
        self.assertIs(self.training.onetrainer_settings.text_encoder_2_train, False)

    def test_flow_matching_fields_persisted_but_omitted_from_sd15_config(self):
        # Mission 129 section 7/9/17 item F: all three flow-matching
        # fields configured while on SD1.5 (simulating a temporary
        # architecture switch away from FLUX, or a hand-edited
        # project.json) must be entirely absent from the JSON, never
        # raise, Domain left untouched.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training.onetrainer_settings.timestep_distribution = "LOGIT_NORMAL"
        self.training.onetrainer_settings.dynamic_timestep_shifting = True
        self.training.onetrainer_settings.timestep_shift = 1.0

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertNotIn("timestep_distribution", written)
        self.assertNotIn("dynamic_timestep_shifting", written)
        self.assertNotIn("timestep_shift", written)
        self.assertEqual(self.training.onetrainer_settings.timestep_distribution, "LOGIT_NORMAL")
        self.assertIs(self.training.onetrainer_settings.dynamic_timestep_shifting, True)
        self.assertEqual(self.training.onetrainer_settings.timestep_shift, 1.0)

    def test_text_encoder_2_and_flow_matching_json_restored_on_return_to_compatible_architecture(self):
        # Mission 129 section 17 item G: the same Domain state that was
        # just proven to omit these keys under SD1.5 (tests above) must
        # produce them again, unchanged, once the architecture switches
        # back to a compatible one — proving the omission is purely a
        # function of the current architecture, never a one-way mutation.
        self.dataset.images = [self._add_real_image("Source", "portrait.png")]
        self.training.onetrainer_settings.text_encoder_2_weight_dtype = "FLOAT_16"
        self.training.onetrainer_settings.text_encoder_2_train = True
        self.training.onetrainer_settings.timestep_distribution = "LOGIT_NORMAL"
        self.training.onetrainer_settings.dynamic_timestep_shifting = True
        self.training.onetrainer_settings.timestep_shift = 1.0
        self.training_manager.update(
            base_model_source="black-forest-labs/FLUX.1-dev",
            architecture=TRAINING_ARCHITECTURE_FLUX,
        )

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        written = json.loads(Path(result.config_path).read_text(encoding="utf-8"))
        self.assertEqual(
            written["text_encoder_2"], {"weight_dtype": "FLOAT_16", "train": True}
        )
        self.assertEqual(written["timestep_distribution"], "LOGIT_NORMAL")
        self.assertIs(written["dynamic_timestep_shifting"], True)
        self.assertEqual(written["timestep_shift"], 1.0)

    def test_explicit_caption_overrides_trigger_word(self):
        # Mission 098: dataset.entries takes priority over
        # training.trigger_word whenever an entry exists for that image.
        image = self._add_real_image("Source", "portrait.png")
        self.dataset.images = [image]
        self.dataset.entries[image.image_id] = DatasetEntryMetadata(caption="a red car")

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        self.assertEqual((concept_folder / "portrait.txt").read_text(encoding="utf-8"), "a red car")

    def test_explicitly_empty_caption_is_never_replaced_by_trigger_word(self):
        # Mission 098: the exact bug this mission corrects — an explicit
        # empty caption must produce an empty .txt, never "ohwx".
        image = self._add_real_image("Source", "portrait.png")
        self.dataset.images = [image]
        self.dataset.entries[image.image_id] = DatasetEntryMetadata(caption="")

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        self.assertTrue((concept_folder / "portrait.txt").exists())
        self.assertEqual((concept_folder / "portrait.txt").read_text(encoding="utf-8"), "")

    def test_mixed_captions_within_the_same_dataset(self):
        # One image with an explicit caption, one with an explicitly
        # empty caption, one with no entry at all (falls back to
        # trigger_word) — all three coexist correctly in one concept.
        with_caption = self._add_real_image("Source", "with_caption.png")
        empty_caption = self._add_real_image("Source", "empty_caption.png")
        no_entry = self._add_real_image("Source", "no_entry.png")
        self.dataset.images = [with_caption, empty_caption, no_entry]
        self.dataset.entries[with_caption.image_id] = DatasetEntryMetadata(caption="a red car")
        self.dataset.entries[empty_caption.image_id] = DatasetEntryMetadata(caption="")

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        self.assertEqual(
            (concept_folder / "with_caption.txt").read_text(encoding="utf-8"), "a red car"
        )
        self.assertEqual((concept_folder / "empty_caption.txt").read_text(encoding="utf-8"), "")
        self.assertEqual((concept_folder / "no_entry.txt").read_text(encoding="utf-8"), "ohwx")

    def test_deterministic_paths_derived_from_workspace_and_training_id(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        expected_root = self.folder / "training" / self.training.training_id
        self.assertEqual(Path(result.concept_path), expected_root / "concept")
        self.assertEqual(Path(result.config_path), expected_root / "onetrainer_config.json")
        self.assertEqual(Path(result.output_path), expected_root / "output" / "lora.safetensors")

    def test_no_absolute_path_is_ever_persisted_on_training_itself(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]

        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        for value in vars(self.training).values():
            if isinstance(value, str):
                self.assertNotIn(str(self.folder), value)

    def test_collision_free_naming_for_two_sources_sharing_a_basename(self):
        # Mission 097 section 5/6: two distinct source images both
        # named "001.png" from different folders must never overwrite
        # each other in the materialized concept — reusing
        # WorkspaceStorage.resolve_collision_free_name() directly.
        self.dataset.images = [
            self._add_real_image("SourceA", "001.png", b"FROM_A"),
            self._add_real_image("SourceB", "001.png", b"FROM_B"),
        ]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        produced = sorted(p.name for p in concept_folder.glob("*.png"))
        self.assertEqual(produced, ["001.png", "001_1.png"])
        contents = {(concept_folder / name).read_bytes() for name in produced}
        self.assertEqual(contents, {b"FROM_A", b"FROM_B"})
        # Every image has its own caption sidecar, collision-free too.
        self.assertTrue((concept_folder / "001.txt").exists())
        self.assertTrue((concept_folder / "001_1.txt").exists())

    def test_source_dataset_images_are_never_modified(self):
        image = self._add_real_image("Source", "a.png", b"ORIGINAL")
        self.dataset.images = [image]

        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.assertEqual(Path(image.file_path).read_bytes(), b"ORIGINAL")
        # Only the materialized copy carries a caption — never the source.
        self.assertFalse(Path(image.file_path).with_suffix(".txt").exists())

    def test_rerunning_rebuilds_the_concept_from_the_current_dataset_state(self):
        # Mission 097 section 6: reproducible/cleanable — a stale prior
        # materialization must never linger once the Dataset changes.
        first_image = self._add_real_image("Source", "first.png")
        self.dataset.images = [first_image]
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        second_image = self._add_real_image("Source", "second.png")
        self.dataset.images = [second_image]
        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        concept_folder = Path(result.concept_path)
        produced = sorted(p.name for p in concept_folder.glob("*.png"))
        self.assertEqual(produced, ["second.png"])

    def test_config_file_reflects_the_real_materialized_concept_and_training_fields(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]

        result = self.training_manager.prepare_onetrainer_config(self.training.training_id)

        with open(result.config_path, encoding="utf-8") as f:
            config = json.load(f)

        self.assertEqual(config["training_method"], "LORA")
        self.assertEqual(config["model_type"], "STABLE_DIFFUSION_15")
        self.assertEqual(config["base_model_name"], "models/v1-5-pruned.safetensors")
        self.assertEqual(config["resolution"], "512")
        self.assertEqual(config["output_model_destination"], result.output_path)
        self.assertEqual(config["concepts"], [{"name": "Session 1", "path": result.concept_path}])

    def test_unknown_training_id_raises_explicitly(self):
        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config("does-not-exist")

    def test_dataset_with_no_images_raises_explicitly(self):
        self.dataset.images = []

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_dataset_no_longer_existing_raises_explicitly(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.character_manager.principal_character.datasets.remove(self.dataset)

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_invalid_architecture_raises_the_adapter_error(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.training.architecture = "POKEMON"

        with self.assertRaises(OneTrainerConfigError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    # --- Mission 106: base_model_source validated first, before any
    # Dataset materialization or config write ------------------------

    def _expected_paths(self):
        expected_root = self.folder / "training" / self.training.training_id
        return expected_root / "concept", expected_root / "onetrainer_config.json"

    def test_empty_base_model_source_raises_before_materializing_dataset(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.training.base_model_source = ""
        concept_folder, config_path = self._expected_paths()

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.assertFalse(concept_folder.exists())
        self.assertFalse(config_path.exists())

    def test_whitespace_only_base_model_source_raises_before_materializing_dataset(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.training.base_model_source = "   "
        concept_folder, config_path = self._expected_paths()

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.assertFalse(concept_folder.exists())
        self.assertFalse(config_path.exists())

    def test_missing_absolute_base_model_source_raises_before_materializing_dataset(self):
        self.dataset.images = [self._add_real_image("Source", "a.png")]
        self.training.base_model_source = str(Path(self.tmp_dir) / "does_not_exist.safetensors")
        concept_folder, config_path = self._expected_paths()

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.assertFalse(concept_folder.exists())
        self.assertFalse(config_path.exists())

    def test_invalid_base_model_source_raises_even_with_no_dataset_at_all(self):
        # Mission 106: the check runs before Character/Dataset
        # resolution — an unknown/absent Dataset must never mask an
        # already-certain base_model_source failure with a different,
        # unrelated exception.
        self.character_manager.principal_character.datasets.remove(self.dataset)
        self.training.base_model_source = ""

        with self.assertRaises(TrainingPreparationError):
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_invalid_base_model_source_message_is_actionable(self):
        self.training.base_model_source = ""

        with self.assertRaises(TrainingPreparationError) as ctx:
            self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.assertIn("modèle de base", str(ctx.exception))

    def test_never_imports_onetrainer_itself(self):
        # Mission 097 section 7/8: this Manager must never depend on
        # OneTrainer actually being installed — it only ever produces a
        # plain JSON file.
        source = Path(inspect.getfile(TrainingManager)).read_text(encoding="utf-8").lower()
        self.assertNotIn("import onetrainer", source)
        self.assertNotIn("trainer.start", source)
        self.assertNotIn("trainer.train", source)
        self.assertNotIn("subprocess", source)


class TrainingJobDomainRoundTripTest(unittest.TestCase):
    """
    Mission 100: TrainingJob Domain object — defaults, to_dict()/
    from_dict() round-trip, and Training.jobs' defensive-compatibility
    filtering (same isinstance(x, dict) discipline as
    Character.datasets/loras/prompts/trainings).
    """

    def test_defaults_and_exact_shape(self):
        job = TrainingJob()
        self.assertEqual(job.job_id, "")
        self.assertEqual(job.state, "")
        self.assertEqual(
            job.to_dict(),
            {
                "job_id": "", "state": "", "config_snapshot_path": "",
                "expected_output_path": "", "final_output_path": "",
                "created_at": 0.0, "ended_at": 0.0, "error_message": "",
                "imported_lora_id": "",
            },
        )

    def test_roundtrip_without_loss_of_information(self):
        original = TrainingJob(
            job_id="job-1",
            state=TRAINING_JOB_STATE_SUCCEEDED,
            config_snapshot_path="/ws/training/t1/jobs/job-1/onetrainer_config.json",
            expected_output_path="/ws/training/t1/jobs/job-1/output/lora.safetensors",
            final_output_path="/ws/training/t1/jobs/job-1/output/lora.safetensors",
            created_at=1000.0,
            ended_at=1500.0,
            error_message="",
            imported_lora_id="lora-9",
        )
        restored = TrainingJob.from_dict(original.to_dict())
        self.assertEqual(original, restored)

    def test_missing_key_falls_back_to_default(self):
        self.assertEqual(TrainingJob.from_dict({}), TrainingJob())
        self.assertEqual(TrainingJob.from_dict({"job_id": "only-id"}).state, "")

    def test_training_jobs_defensive_filtering(self):
        self.assertEqual(Training.from_dict({}).jobs, [])
        self.assertEqual(Training.from_dict({"jobs": []}).jobs, [])
        self.assertEqual(Training.from_dict({"jobs": None}).jobs, [])

        mixed = Training.from_dict({
            "jobs": [
                {"job_id": "J1", "state": TRAINING_JOB_STATE_RUNNING},
                "invalid",
                None,
                42,
                {"job_id": "J2"},
            ]
        })
        self.assertEqual(len(mixed.jobs), 2)
        self.assertTrue(all(isinstance(j, TrainingJob) for j in mixed.jobs))
        self.assertEqual(mixed.jobs[0].job_id, "J1")
        self.assertEqual(mixed.jobs[0].state, TRAINING_JOB_STATE_RUNNING)
        self.assertEqual(mixed.jobs[1].job_id, "J2")
        self.assertEqual(mixed.jobs[1].state, "")


class TrainingManagerCreateJobTest(unittest.TestCase):
    """
    Mission 100 section 5.1 (Option B): TrainingManager.create_job() —
    real filesystem setup (never mocked for the nominal cases), Job
    isolation, and config-snapshot immutability against a later Prepare.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        # Mission 026: WorkspaceManager.create() already auto-creates the
        # Workspace's principal Character — used directly here (not a
        # second explicitly-created/selected Character) so that
        # CharacterManager.principal_character's "first Character in the
        # Workspace" fallback (exercised by TrainingManagerRecoverStale-
        # JobsTest's close/reopen scenario, before any select() call
        # exists to resolve on the reopened instance) matches this
        # test's own single-Character setup, exactly like the real
        # application's single-principal-Character-per-Workspace shape.
        character = self.character_manager.principal_character

        self.dataset = self.dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
            trigger_word="ohwx",
        )

    def test_raises_for_unknown_training(self):
        with self.assertRaises(TrainingJobError):
            self.training_manager.create_job("does-not-exist")

    def test_raises_when_never_prepared(self):
        with self.assertRaises(TrainingJobError):
            self.training_manager.create_job(self.training.training_id)

    def test_creates_job_with_starting_state_and_deterministic_paths(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        job = self.training_manager.create_job(self.training.training_id)

        self.assertEqual(job.state, TRAINING_JOB_STATE_STARTING)
        self.assertTrue(job.job_id)
        self.assertGreater(job.created_at, 0.0)
        self.assertEqual(job.ended_at, 0.0)

        job_folder = self.folder / "training" / self.training.training_id / "jobs" / job.job_id
        self.assertEqual(Path(job.config_snapshot_path), job_folder / "onetrainer_config.json")
        self.assertEqual(
            Path(job.expected_output_path), job_folder / "output" / "lora.safetensors"
        )
        self.assertTrue(Path(job.config_snapshot_path).is_file())
        self.assertIn(job, self.training.jobs)

    def test_command_pipe_precreated(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        job = self.training_manager.create_job(self.training.training_id)

        paths = self.training_manager.job_paths(self.training.training_id, job.job_id)
        self.assertTrue(
            Path(paths.command_pipe_path).is_file(),
            "command.pipe must be pre-created before the OneTrainer process ever starts "
            "(MISSION_100.md section 3.4 empirical result)",
        )
        # Mission 100 (revised contract, section 7): no callback.pipe is
        # ever created or consumed — TrainingJobPaths has no such field.
        self.assertNotIn("callback", paths._fields)

    def test_config_snapshot_overrides_output_workspace_cache_debug(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        job = self.training_manager.create_job(self.training.training_id)
        paths = self.training_manager.job_paths(self.training.training_id, job.job_id)

        with open(job.config_snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)

        self.assertEqual(snapshot["output_model_destination"], paths.expected_output_path)
        self.assertEqual(snapshot["workspace_dir"], paths.workspace_dir)
        self.assertEqual(snapshot["cache_dir"], paths.cache_dir)
        self.assertEqual(snapshot["debug_dir"], paths.debug_dir)
        # None of these Job-owned paths point under the OneTrainer
        # installation itself — they are all Workspace-relative.
        for value in (
            paths.expected_output_path, paths.workspace_dir,
            paths.cache_dir, paths.debug_dir,
        ):
            self.assertIn(str(self.folder), value)

    def test_two_successive_jobs_are_fully_isolated(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        job_a = self.training_manager.create_job(self.training.training_id)
        job_b = self.training_manager.create_job(self.training.training_id)

        self.assertNotEqual(job_a.job_id, job_b.job_id)
        self.assertNotEqual(job_a.config_snapshot_path, job_b.config_snapshot_path)
        self.assertNotEqual(job_a.expected_output_path, job_b.expected_output_path)
        self.assertEqual(len(self.training.jobs), 2)

    def test_later_prepare_never_mutates_an_earlier_jobs_snapshot(self):
        # Mission 100 section 5.1: a Prepare after Start must never
        # retroactively change the configuration a Job already captured.
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        job = self.training_manager.create_job(self.training.training_id)

        before = Path(job.config_snapshot_path).read_text(encoding="utf-8")

        # Change a parameter and re-Prepare — rewrites the Training-level
        # onetrainer_config.json, must never touch the Job's own copy.
        self.training_manager.update(resolution=1024, architecture=TRAINING_ARCHITECTURE_SDXL)
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        after = Path(job.config_snapshot_path).read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_later_prepare_with_new_dtype_fields_never_mutates_an_earlier_jobs_snapshot(self):
        # Mission 121: same immutability contract as the Mission 120
        # fields above, exercised with the 6 new dtype fields instead —
        # a Prepare that newly configures them after a Job already
        # exists must never retroactively alter that Job's own snapshot.
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        job = self.training_manager.create_job(self.training.training_id)

        before = Path(job.config_snapshot_path).read_text(encoding="utf-8")
        self.assertNotIn("train_dtype", before)
        self.assertNotIn('"unet"', before)

        self.training_manager.update(
            train_dtype="FLOAT_16", unet_weight_dtype="FLOAT_16", vae_weight_dtype="FLOAT_32",
        )
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        after = Path(job.config_snapshot_path).read_text(encoding="utf-8")
        self.assertEqual(before, after)

        # The Training-level (not yet Job-snapshotted) configuration
        # does reflect the new fields — proving the assertion above is
        # a real non-mutation, not merely an absence of any write at all.
        training_level_config = json.loads(
            (self.folder / "training" / self.training.training_id / "onetrainer_config.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(training_level_config["train_dtype"], "FLOAT_16")
        self.assertEqual(training_level_config["unet"], {"weight_dtype": "FLOAT_16"})

    def test_later_prepare_with_new_optimizer_field_never_mutates_an_earlier_jobs_snapshot(self):
        # Mission 122: same immutability contract as Mission 120/121
        # above, exercised with the new optimizer field — a Prepare that
        # newly configures it after a Job already exists must never
        # retroactively alter that Job's own snapshot.
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        job = self.training_manager.create_job(self.training.training_id)

        before = Path(job.config_snapshot_path).read_text(encoding="utf-8")
        self.assertNotIn('"optimizer"', before)

        self.training_manager.update(optimizer="SGD")
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        after = Path(job.config_snapshot_path).read_text(encoding="utf-8")
        self.assertEqual(before, after)

        training_level_config = json.loads(
            (self.folder / "training" / self.training.training_id / "onetrainer_config.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(training_level_config["optimizer"], {"optimizer": "SGD"})

    def test_create_job_publishes_training_job_created(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        events_seen = []
        self.event_bus.subscribe(TRAINING_JOB_CREATED, lambda payload: events_seen.append(payload))

        job = self.training_manager.create_job(self.training.training_id)

        self.assertEqual(len(events_seen), 1)
        self.assertEqual(events_seen[0]["job_id"], job.job_id)
        self.assertEqual(events_seen[0]["state"], TRAINING_JOB_STATE_STARTING)

    def test_create_job_rolled_back_on_save_failure(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        with patch.object(
            self.workspace_manager, "save", side_effect=WorkspaceManagerError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.create_job(self.training.training_id)

        self.assertEqual(self.training.jobs, [])

    def test_job_persists_across_close_and_reopen(self):
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        job = self.training_manager.create_job(self.training.training_id)

        self.workspace_manager.close()

        event_bus_2 = EventBus()
        workspace_manager_2 = WorkspaceManager(event_bus=event_bus_2)
        character_manager_2 = CharacterManager(workspace_manager_2, event_bus=event_bus_2)
        training_manager_2 = TrainingManager(
            character_manager_2, workspace_manager_2, event_bus=event_bus_2
        )

        # No select() needed — this Workspace has a single (principal)
        # Character, exactly like the real application; recovery
        # (_recover_stale_jobs) runs synchronously inside open()'s own
        # WORKSPACE_OPENED publish, before this line even executes.
        workspace_manager_2.open(self.folder)

        restored_training = training_manager_2.trainings[0]
        # Mission 100 section 12: a Job left "starting" at close time has
        # no QProcess supervision once reopened — WORKSPACE_OPENED
        # recovers it to "unknown" automatically (see
        # TrainingManagerRecoverStaleJobsTest below for the dedicated
        # coverage of this mechanism itself).
        self.assertEqual(len(restored_training.jobs), 1)
        self.assertEqual(restored_training.jobs[0].job_id, job.job_id)
        self.assertEqual(restored_training.jobs[0].state, TRAINING_JOB_STATE_UNKNOWN)


class TrainingManagerUpdateJobStateTest(unittest.TestCase):
    """
    Mission 100: TrainingManager.update_job_state() — idempotence,
    rollback on save() failure, ended_at stamping, and event publication.
    Same discipline as every other update_*() in this Manager.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        self.job = self.training_manager.create_job(self.training.training_id)

    def test_unknown_job_id_returns_false(self):
        self.assertFalse(self.training_manager.update_job_state("does-not-exist", TRAINING_JOB_STATE_RUNNING))

    def test_transition_to_running_is_not_terminal(self):
        result = self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_RUNNING)
        self.assertTrue(result)
        self.assertEqual(self.job.state, TRAINING_JOB_STATE_RUNNING)
        self.assertEqual(self.job.ended_at, 0.0)

    def test_identical_state_is_idempotent(self):
        self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_RUNNING)
        with patch.object(self.workspace_manager, "save") as mock_save:
            result = self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_RUNNING)
        self.assertFalse(result)
        mock_save.assert_not_called()

    def test_terminal_state_stamps_ended_at_once(self):
        self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_RUNNING)
        self.training_manager.update_job_state(
            self.job.job_id, TRAINING_JOB_STATE_SUCCEEDED,
            final_output_path=self.job.expected_output_path,
        )
        first_ended_at = self.job.ended_at
        self.assertGreater(first_ended_at, 0.0)
        self.assertEqual(self.job.final_output_path, self.job.expected_output_path)

        # A further update to the same terminal state never re-stamps
        # ended_at, and is itself a no-op (same state, same fields).
        result = self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_SUCCEEDED)
        self.assertFalse(result)
        self.assertEqual(self.job.ended_at, first_ended_at)

    def test_failed_state_records_error_message(self):
        self.training_manager.update_job_state(
            self.job.job_id, TRAINING_JOB_STATE_FAILED,
            error_message="native crash: 0xC0000374",
        )
        self.assertEqual(self.job.state, TRAINING_JOB_STATE_FAILED)
        self.assertEqual(self.job.error_message, "native crash: 0xC0000374")
        self.assertGreater(self.job.ended_at, 0.0)

    def test_rolled_back_on_save_failure(self):
        self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_RUNNING)
        with patch.object(
            self.workspace_manager, "save", side_effect=WorkspaceManagerError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_CANCELLED)
        self.assertEqual(self.job.state, TRAINING_JOB_STATE_RUNNING)
        self.assertEqual(self.job.ended_at, 0.0)

    def test_publishes_training_job_state_changed(self):
        events_seen = []
        self.event_bus.subscribe(TRAINING_JOB_STATE_CHANGED, lambda payload: events_seen.append(payload))

        self.training_manager.update_job_state(self.job.job_id, TRAINING_JOB_STATE_RUNNING)

        self.assertEqual(len(events_seen), 1)
        self.assertEqual(events_seen[0]["job_id"], self.job.job_id)
        self.assertEqual(events_seen[0]["state"], TRAINING_JOB_STATE_RUNNING)


class TrainingManagerHasActiveJobTest(unittest.TestCase):
    """
    Mission 100 section 11: has_active_job() — the exact predicate the
    close guard depends on.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

    def test_false_without_any_job(self):
        self.assertFalse(self.training_manager.has_active_job())

    def test_true_while_starting_or_running(self):
        job = self.training_manager.create_job(self.training.training_id)
        self.assertTrue(self.training_manager.has_active_job())

        self.training_manager.update_job_state(job.job_id, TRAINING_JOB_STATE_RUNNING)
        self.assertTrue(self.training_manager.has_active_job())

    def test_false_once_terminal(self):
        job = self.training_manager.create_job(self.training.training_id)
        self.training_manager.update_job_state(job.job_id, TRAINING_JOB_STATE_RUNNING)
        self.training_manager.update_job_state(job.job_id, TRAINING_JOB_STATE_CANCELLED)
        self.assertFalse(self.training_manager.has_active_job())


class TrainingManagerRecoverStaleJobsTest(unittest.TestCase):
    """
    Mission 100 section 12: a TrainingJob left "starting"/"running" when
    a Workspace is opened has lost all QProcess supervision — it must be
    recovered to TRAINING_JOB_STATE_UNKNOWN, never guessed as
    succeeded/failed/cancelled. A Job already in a terminal state must
    never be touched.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire_minimal(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager

    def test_starting_and_running_jobs_recovered_to_unknown_on_reopen(self):
        event_bus, workspace_manager, character_manager, dataset_manager, training_manager = (
            self._wire_minimal()
        )
        workspace_manager.create(self.folder)
        # Mission 026: the auto-created principal Character, used
        # directly (see TrainingManagerCreateJobTest.setUp's own
        # comment for why this matters specifically for a close/reopen
        # scenario like this one — recovery runs before any select()
        # call could resolve a second, explicitly-created Character).
        dataset = dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        training_manager.prepare_onetrainer_config(training.training_id)

        starting_job = training_manager.create_job(training.training_id)
        running_job = training_manager.create_job(training.training_id)
        training_manager.update_job_state(running_job.job_id, TRAINING_JOB_STATE_RUNNING)
        succeeded_job = training_manager.create_job(training.training_id)
        training_manager.update_job_state(succeeded_job.job_id, TRAINING_JOB_STATE_RUNNING)
        training_manager.update_job_state(
            succeeded_job.job_id, TRAINING_JOB_STATE_SUCCEEDED,
            final_output_path=succeeded_job.expected_output_path,
        )

        workspace_manager.close()

        _, workspace_manager_2, character_manager_2, _, training_manager_2 = self._wire_minimal()
        workspace_manager_2.open(self.folder)

        restored_training = training_manager_2.trainings[0]

        by_id = {job.job_id: job for job in restored_training.jobs}
        self.assertEqual(by_id[starting_job.job_id].state, TRAINING_JOB_STATE_UNKNOWN)
        self.assertEqual(by_id[running_job.job_id].state, TRAINING_JOB_STATE_UNKNOWN)
        # A Job already terminal before the close must never be touched.
        self.assertEqual(by_id[succeeded_job.job_id].state, TRAINING_JOB_STATE_SUCCEEDED)
        self.assertEqual(
            by_id[succeeded_job.job_id].final_output_path, succeeded_job.expected_output_path
        )


class TrainingManagerImportJobToLibraryTest(unittest.TestCase):
    """
    Mission 103: TrainingManager.set_job_imported_lora_id() — the sole
    persisted link between a succeeded TrainingJob and the Central LoRA
    Library entry it was imported into. Same idempotence/rollback
    discipline as update_job_state() (Mission 100), but a strictly
    separate concern (Library linkage, never execution state) and
    strictly no event (MISSION_103.md section 3.4 — no consumer needs
    one; TrainingPage refreshes itself directly after its own call).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )

        self.workspace_manager.create(self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        self.training_manager.prepare_onetrainer_config(self.training.training_id)
        self.job = self.training_manager.create_job(self.training.training_id)
        self.training_manager.update_job_state(
            self.job.job_id, TRAINING_JOB_STATE_SUCCEEDED,
            final_output_path=self.job.expected_output_path,
        )

    def test_unknown_job_id_returns_false(self):
        self.assertFalse(
            self.training_manager.set_job_imported_lora_id("does-not-exist", "lora-1")
        )

    def test_persists_the_link(self):
        result = self.training_manager.set_job_imported_lora_id(self.job.job_id, "lora-1")
        self.assertTrue(result)
        self.assertEqual(self.job.imported_lora_id, "lora-1")

    def test_identical_value_is_idempotent(self):
        self.training_manager.set_job_imported_lora_id(self.job.job_id, "lora-1")
        with patch.object(self.workspace_manager, "save") as mock_save:
            result = self.training_manager.set_job_imported_lora_id(self.job.job_id, "lora-1")
        self.assertFalse(result)
        mock_save.assert_not_called()

    def test_rolled_back_on_save_failure(self):
        with patch.object(
            self.workspace_manager, "save", side_effect=WorkspaceManagerError("disk full")
        ):
            with self.assertRaises(WorkspaceManagerError):
                self.training_manager.set_job_imported_lora_id(self.job.job_id, "lora-1")
        self.assertEqual(self.job.imported_lora_id, "")

    def test_never_touches_state_or_final_output_path(self):
        self.training_manager.set_job_imported_lora_id(self.job.job_id, "lora-1")
        self.assertEqual(self.job.state, TRAINING_JOB_STATE_SUCCEEDED)
        self.assertEqual(self.job.final_output_path, self.job.expected_output_path)

    def test_survives_close_and_reopen(self):
        self.training_manager.set_job_imported_lora_id(self.job.job_id, "lora-1")
        self.workspace_manager.close()

        event_bus_2 = EventBus()
        workspace_manager_2 = WorkspaceManager(event_bus=event_bus_2)
        character_manager_2 = CharacterManager(workspace_manager_2, event_bus=event_bus_2)
        training_manager_2 = TrainingManager(
            character_manager_2, workspace_manager_2, event_bus=event_bus_2
        )
        workspace_manager_2.open(self.folder)

        reloaded_training = training_manager_2.trainings[0]
        reloaded_job = next(j for j in reloaded_training.jobs if j.job_id == self.job.job_id)
        self.assertEqual(reloaded_job.imported_lora_id, "lora-1")


class TrainingPageJobImportTest(unittest.TestCase):
    """
    Mission 103: the Jobs list + import action of TrainingPage, driven
    against a real TrainingManager and a real LoRALibraryManager (never
    mocked for the behavior under test) — mirrors the real user
    workflow: TrainingJob succeeded -> UI action -> real Central LoRA
    Library entry -> Job marked imported -> available in Inference.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.library_root.mkdir(parents=True, exist_ok=True)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "lora_library_registry",
            event_bus=self.event_bus,
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        self.application_settings_manager.update(lora_library_path=str(self.library_root))

        self.workspace_manager.create(self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.page = TrainingPage(
            self.training_manager, self.dataset_manager, self.workspace_manager,
            self.application_settings_manager, self.lora_library_manager,
        )
        for event_name in TRAINING_EVENTS:
            self.event_bus.subscribe(event_name, self.page.update_trainings)
        self.page.update_trainings()

    def _create_succeeded_job(self, filename="lora.safetensors", content=b"fake-lora-bytes"):
        job = self.training_manager.create_job(self.training.training_id)
        output_path = Path(job.expected_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        self.training_manager.update_job_state(
            job.job_id, TRAINING_JOB_STATE_SUCCEEDED, final_output_path=str(output_path)
        )
        return job

    def _select_job_row(self, job_id):
        for i in range(self.page.jobs_list.count()):
            item = self.page.jobs_list.item(i)
            if item.data(Qt.UserRole) == job_id:
                self.page.jobs_list.setCurrentItem(item)
                return
        self.fail(f"No jobs_list row found for job_id={job_id!r}")

    def test_multiple_persisted_jobs_are_all_listed(self):
        job_a = self._create_succeeded_job()
        job_b = self._create_succeeded_job()
        self.page.update_trainings()

        listed_ids = {
            self.page.jobs_list.item(i).data(Qt.UserRole)
            for i in range(self.page.jobs_list.count())
        }
        self.assertEqual(listed_ids, {job_a.job_id, job_b.job_id})

    def test_succeeded_job_with_valid_output_is_importable(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self.assertTrue(self.page.import_lora_button.isEnabled())

    def test_failed_cancelled_unknown_jobs_are_never_importable(self):
        for state in (
            TRAINING_JOB_STATE_FAILED, TRAINING_JOB_STATE_CANCELLED, TRAINING_JOB_STATE_UNKNOWN
        ):
            job = self.training_manager.create_job(self.training.training_id)
            self.training_manager.update_job_state(job.job_id, state)
            self.page.update_trainings()
            self._select_job_row(job.job_id)
            self.assertFalse(
                self.page.import_lora_button.isEnabled(),
                f"state={state!r} must never allow import",
            )

    def test_missing_output_file_blocks_import(self):
        job = self._create_succeeded_job()
        Path(job.final_output_path).unlink()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self.assertFalse(self.page.import_lora_button.isEnabled())
        self.assertIn("introuvable", self.page.jobs_list.currentItem().text())

    def test_import_creates_real_library_entry_and_persists_imported_lora_id(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information") as mock_information:
            self.page.import_selected_job_to_library()

        mock_information.assert_called_once()

        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 1)
        self.assertEqual(loras[0].name, "Imported LoRA")
        self.assertTrue(Path(loras[0].files[0]).is_file())

        reloaded_job = next(
            j for j in self.training_manager.active_training.jobs if j.job_id == job.job_id
        )
        self.assertEqual(reloaded_job.imported_lora_id, loras[0].lora_id)

    def test_import_carries_the_training_trigger_word_into_the_library_entry(self):
        self.training_manager.update(trigger_word="dmlrwoman")
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        loras = self.lora_library_manager.list_loras()
        self.assertEqual(loras[0].trigger_word, "dmlrwoman")

    def test_import_with_blank_training_trigger_word_produces_a_blank_library_entry(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        loras = self.lora_library_manager.list_loras()
        self.assertEqual(loras[0].trigger_word, "")

    def test_a_prefilled_trigger_word_flows_to_the_library_entry_exactly_like_a_manual_one(self):
        # Mission 111 non-regression: a trigger_word prefilled from
        # Character.trigger_token at creation time (never set through
        # training_manager.update(), unlike the two tests above) must
        # reach LoRALibraryManager.import_lora() exactly like a manually
        # typed one -- it is the same Training.trigger_word field, read
        # by the same TrainingPage.import_selected_job_to_library() call
        # (training_page.py:1283) that Mission 110 already covers.
        character = self.character_manager.principal_character
        self.character_manager.update(character.character_id, trigger_token="dmlrwoman")

        second_dataset = self.dataset_manager.create("Portraits 2")
        second_source_dir = Path(self.tmp_dir) / "Source2"
        second_source_dir.mkdir(parents=True, exist_ok=True)
        second_image_path = second_source_dir / "b.png"
        second_image_path.write_bytes(b"fake-png-bytes")
        second_dataset.images = [Image(image_id=str(second_image_path), file_path=str(second_image_path))]

        training = self.training_manager.create("Session 2", second_dataset.dataset_id)
        self.training_manager.select(training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        self.training_manager.prepare_onetrainer_config(training.training_id)
        self.page.update_trainings()

        job = self.training_manager.create_job(training.training_id)
        output_path = Path(job.expected_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-lora-bytes")
        self.training_manager.update_job_state(
            job.job_id, TRAINING_JOB_STATE_SUCCEEDED, final_output_path=str(output_path)
        )
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA 2", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        loras = self.lora_library_manager.list_loras()
        imported = next(lora for lora in loras if lora.name == "Imported LoRA 2")
        self.assertEqual(imported.trigger_word, "dmlrwoman")

    def test_double_import_is_prevented_while_library_entry_exists(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        self._select_job_row(job.job_id)
        self.assertFalse(self.page.import_lora_button.isEnabled())
        self.assertIn("importé", self.page.jobs_list.currentItem().text())
        self.assertEqual(len(self.lora_library_manager.list_loras()), 1)

    def test_deleted_library_entry_shows_reimport_state_and_allows_reimport(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        lora_id = self.lora_library_manager.list_loras()[0].lora_id
        self.lora_library_manager.delete(lora_id, str(self.library_root))

        self.page.update_trainings()
        self._select_job_row(job.job_id)

        self.assertTrue(self.page.import_lora_button.isEnabled())
        self.assertIn("supprimé", self.page.jobs_list.currentItem().text())

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Reimported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 1)
        self.assertEqual(loras[0].name, "Reimported LoRA")

    def test_import_lora_failure_leaves_job_unchanged(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch.object(
            self.lora_library_manager, "import_lora",
            side_effect=LoRALibraryError("disk full"),
        ), patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            self.page.import_selected_job_to_library()

        mock_critical.assert_called_once()
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        reloaded_job = next(
            j for j in self.training_manager.active_training.jobs if j.job_id == job.job_id
        )
        self.assertEqual(reloaded_job.imported_lora_id, "")

    def _assert_blank_library_path_blocks_import(self, blank_value):
        # Mission 104: the library is still empty at this point, so
        # ApplicationSettingsManager's own lock (Mission 087) never
        # fires -- only resolve_lora_library_root() must stop this.
        self.application_settings_manager.update(lora_library_path=blank_value)
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        received = []
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, lambda data: received.append(data))
        cwd_before = set(os.listdir(os.getcwd()))

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch.object(
            self.lora_library_manager, "import_lora"
        ) as import_mock, patch(
            "src.ui.pages.training_page.QMessageBox.critical"
        ) as critical_mock, patch(
            "src.ui.pages.training_page.QMessageBox.information"
        ) as information_mock:
            self.page.import_selected_job_to_library()

        import_mock.assert_not_called()
        self.assertEqual(received, [])
        information_mock.assert_not_called()
        critical_mock.assert_called_once()
        self.assertIn("pas configurée", critical_mock.call_args[0][2])
        self.assertEqual(self.lora_library_manager.list_loras(), [])
        reloaded_job = next(
            j for j in self.training_manager.active_training.jobs if j.job_id == job.job_id
        )
        self.assertEqual(reloaded_job.imported_lora_id, "")
        self.assertEqual(set(os.listdir(os.getcwd())), cwd_before)

    def test_empty_library_path_blocks_import(self):
        self._assert_blank_library_path_blocks_import("")

    def test_blank_library_path_blocks_import(self):
        self._assert_blank_library_path_blocks_import("   ")

    def test_imported_lora_id_persistence_failure_warns_without_false_success(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch.object(
            self.workspace_manager, "save", side_effect=WorkspaceManagerError("disk full")
        ), patch("src.ui.pages.training_page.QMessageBox.warning") as mock_warning, patch(
            "src.ui.pages.training_page.QMessageBox.information"
        ) as mock_information:
            self.page.import_selected_job_to_library()

        # Section 3.5: the Library entry is real and kept — never a
        # false "clean success" message, never a compensating deletion.
        mock_information.assert_not_called()
        mock_warning.assert_called_once()
        loras = self.lora_library_manager.list_loras()
        self.assertEqual(len(loras), 1)

        reloaded_job = next(
            j for j in self.training_manager.active_training.jobs if j.job_id == job.job_id
        )
        self.assertEqual(reloaded_job.imported_lora_id, "")

        # The Job reappears as importable — a retry creates a second,
        # distinct entry (no automatic dedup), exactly as the warning
        # message told the user it would.
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self.assertTrue(self.page.import_lora_button.isEnabled())

    def test_non_succeeded_job_selection_never_enables_import(self):
        job = self.training_manager.create_job(self.training.training_id)
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self.assertFalse(self.page.import_lora_button.isEnabled())

    def test_imported_lora_immediately_available_in_inference_selector(self):
        """
        Mission 103 section 3.7 / MISSION_102.md: no new Inference code
        — LORA_LIBRARY_IMPORTED, already published by import_lora() and
        already consumed by InferencePage.refresh_lora_selector since
        Mission 102, must be enough on its own.
        """
        inference_page = InferencePage(
            MagicMock(), self.workspace_manager, MagicMock(), MagicMock(),
            MagicMock(), self.lora_library_manager, self.application_settings_manager,
            MagicMock(), MagicMock(),
        )
        self.event_bus.subscribe(LORA_LIBRARY_IMPORTED, inference_page.refresh_lora_selector)

        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        lora_id = self.lora_library_manager.list_loras()[0].lora_id
        combo_ids = {
            inference_page.lora_combo.itemData(i)
            for i in range(inference_page.lora_combo.count())
        }
        self.assertIn(lora_id, combo_ids)
        inference_page.shutdown()

    def test_job_selection_and_import_never_mark_parameters_dirty(self):
        """
        Mission 105: TrainingPage's own parameter dirty-state tracking
        must stay entirely independent of Job list activity — the M103
        import workflow must never require (or silently trigger) a
        Save/Discard/Cancel confirmation on the Training's own
        parameters.
        """
        self.assertFalse(self.page._dirty)

        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        self.assertFalse(self.page._dirty)

        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=("Imported LoRA", True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

        self.assertFalse(self.page._dirty)

    def test_job_lifecycle_callbacks_never_mark_parameters_dirty(self):
        """
        Mission 105: _on_job_started()/_on_job_finished() (Mission 100's
        own real execution callbacks) must never touch the parameter
        dirty-state guard — they only ever call _refresh_job_controls(),
        never update_trainings().
        """
        job = self._create_succeeded_job()
        self.page.update_trainings()

        self.page._active_job_id = job.job_id
        self.page._on_job_started()
        self.assertFalse(self.page._dirty)

        with patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page._on_job_finished(
                TRAINING_JOB_STATE_SUCCEEDED, "", job.expected_output_path
            )
        self.assertFalse(self.page._dirty)


class TrainingPageUseLoraInInferenceTest(unittest.TestCase):
    """
    Mission 109: the "Utiliser dans Inference" action — available only
    for a Job whose imported_lora_id still resolves to a real Central
    LoRA Library entry, recomputed fresh on every relevant refresh
    (never a value cached at import time). Same real-manager idiom as
    TrainingPageJobImportTest above, isolated tmp_dir storage
    throughout (no real user storage touched).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"
        self.library_root = Path(self.tmp_dir) / "Library"
        self.library_root.mkdir(parents=True, exist_ok=True)

        self.event_bus = EventBus()
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus)
        self.character_manager = CharacterManager(self.workspace_manager, event_bus=self.event_bus)
        self.dataset_manager = DatasetManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.training_manager = TrainingManager(
            self.character_manager, self.workspace_manager, event_bus=self.event_bus
        )
        self.lora_library_manager = LoRALibraryManager(
            storage_directory=Path(self.tmp_dir) / "lora_library_registry",
            event_bus=self.event_bus,
        )
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        self.application_settings_manager.update(lora_library_path=str(self.library_root))

        self.workspace_manager.create(self.folder)
        self.dataset = self.dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        self.dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        self.training = self.training_manager.create("Session 1", self.dataset.dataset_id)
        self.training_manager.select(self.training.training_id)
        self.training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        self.training_manager.prepare_onetrainer_config(self.training.training_id)

        self.page = TrainingPage(
            self.training_manager, self.dataset_manager, self.workspace_manager,
            self.application_settings_manager, self.lora_library_manager,
        )
        for event_name in TRAINING_EVENTS:
            self.event_bus.subscribe(event_name, self.page.update_trainings)
        self.page.update_trainings()

    def _create_succeeded_job(self, filename="lora.safetensors", content=b"fake-lora-bytes"):
        job = self.training_manager.create_job(self.training.training_id)
        output_path = Path(job.expected_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        self.training_manager.update_job_state(
            job.job_id, TRAINING_JOB_STATE_SUCCEEDED, final_output_path=str(output_path)
        )
        return job

    def _select_job_row(self, job_id):
        for i in range(self.page.jobs_list.count()):
            item = self.page.jobs_list.item(i)
            if item.data(Qt.UserRole) == job_id:
                self.page.jobs_list.setCurrentItem(item)
                return
        self.fail(f"No jobs_list row found for job_id={job_id!r}")

    def _import_selected_job(self, name="Imported LoRA"):
        with patch(
            "src.ui.pages.training_page.QInputDialog.getText",
            return_value=(name, True),
        ), patch("src.ui.pages.training_page.QMessageBox.information"):
            self.page.import_selected_job_to_library()

    def test_button_disabled_without_any_job_selected(self):
        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())

    def test_button_disabled_for_a_non_imported_job(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())

    def test_button_enabled_once_the_job_is_imported(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self._import_selected_job()

        self._select_job_row(job.job_id)
        self.assertTrue(self.page.use_lora_in_inference_button.isEnabled())

    def test_button_disabled_again_once_the_imported_lora_is_deleted(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self._import_selected_job()

        lora_id = self.lora_library_manager.list_loras()[0].lora_id
        self.lora_library_manager.delete(lora_id, str(self.library_root))

        self.page.update_trainings()
        self._select_job_row(job.job_id)

        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())

    def test_button_re_enabled_after_a_successful_reimport(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self._import_selected_job()

        lora_id = self.lora_library_manager.list_loras()[0].lora_id
        self.lora_library_manager.delete(lora_id, str(self.library_root))
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self.assertFalse(self.page.use_lora_in_inference_button.isEnabled())

        self._import_selected_job("Reimported LoRA")
        self._select_job_row(job.job_id)
        self.assertTrue(self.page.use_lora_in_inference_button.isEnabled())

    def test_clicking_the_button_emits_the_exact_imported_lora_id(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self._import_selected_job()

        lora_id = self.lora_library_manager.list_loras()[0].lora_id
        self._select_job_row(job.job_id)

        received = []
        self.page.use_lora_in_inference_requested.connect(received.append)
        self.page.use_lora_in_inference_button.click()

        self.assertEqual(received, [lora_id])

    def test_clicking_the_button_with_no_usable_job_emits_nothing(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)

        received = []
        self.page.use_lora_in_inference_requested.connect(received.append)
        self.page.use_selected_lora_in_inference()

        self.assertEqual(received, [])

    def test_import_and_use_in_inference_never_mark_parameters_dirty(self):
        job = self._create_succeeded_job()
        self.page.update_trainings()
        self._select_job_row(job.job_id)
        self._import_selected_job()
        self._select_job_row(job.job_id)

        self.page.use_selected_lora_in_inference()

        self.assertFalse(self.page._dirty)


class TrainingPageDirtyStateTest(unittest.TestCase):
    """
    Mission 105: TrainingPage.update_trainings() used to unconditionally
    overwrite the 8 parameter widgets (base_model_source/architecture/
    resolution/epochs/learning_rate/lora_rank/lora_alpha/trigger_word)
    on every WORKSPACE_SAVED/CREATED/OPENED/CLOSED and CHARACTER_CREATED/
    SELECTED/DELETED/TRAINING_* event — an unsaved draft was silently
    destroyed by any unrelated mutation elsewhere in the app, exactly
    the bug class already fixed for PromptsPage (Mission 038) and
    CharactersPage/LoRAPage/SettingsPage (Mission 078). A single
    _dirty flag + _loaded_training_id comparison now preserves a
    genuine draft across a non-destructive refresh, discards it on a
    real Training switch or Workspace/Character context change.

    Also covers the distinct Start/Prepare invariant: Start always
    (re)prepares the OneTrainer configuration from the Training's
    current, just-saved state before creating a Job — never trusting a
    stale onetrainer_config.json left over from an earlier Prepare (see
    TrainingPageStartPrepareTest below for the dedicated coverage of
    this contract, pre-M124 correction).
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )

        # Mission 105: same split as the real main_window.py wiring.
        for event_name in (WORKSPACE_SAVED,):
            event_bus.subscribe(event_name, training_page.update_trainings)
        for event_name in (WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        event_bus.subscribe(CHARACTER_CREATED, training_page.update_trainings)
        for event_name in (CHARACTER_SELECTED, CHARACTER_DELETED):
            event_bus.subscribe(event_name, training_page.reset_for_context_change)
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)

        return event_bus, workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _prepare(self):
        (event_bus, workspace_manager, character_manager, dataset_manager,
         training_manager, training_page) = self._wire()
        workspace_manager.create(self.folder)
        character_manager.create("Aria")

        dataset = dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        training_manager.prepare_onetrainer_config(training.training_id)
        training_page.update_trainings()

        return event_bus, workspace_manager, character_manager, training_manager, training_page, training, dataset

    # --- 1. each parameter widget type marks the form dirty -----------

    def test_each_parameter_widget_type_marks_dirty(self):
        _, _, _, _, training_page, _, _ = self._prepare()

        mutations = (
            lambda: training_page.base_model_edit.setText("models/new.safetensors"),
            lambda: training_page.architecture_combo.setCurrentText(TRAINING_ARCHITECTURE_SDXL),
            # 896, not 1024: on_architecture_changed()'s own resolution
            # suggestion for SDXL (just exercised above) already sets
            # resolution_spinbox to 1024 — QSpinBox.setValue() never
            # emits valueChanged for an unchanged value, so re-asserting
            # 1024 here would be a false negative, not a real mutation.
            lambda: training_page.resolution_spinbox.setValue(896),
            lambda: training_page.epochs_spinbox.setValue(50),
            lambda: training_page.learning_rate_spinbox.setValue(0.001),
            lambda: training_page.lora_rank_spinbox.setValue(32),
            lambda: training_page.lora_alpha_spinbox.setValue(2.0),
            lambda: training_page.trigger_word_edit.setText("newtrigger"),
            # Mission 120: same contract for the 3 new widgets.
            lambda: training_page.batch_size_spinbox.setValue(4),
            lambda: training_page.gradient_accumulation_steps_spinbox.setValue(2),
            lambda: training_page.learning_rate_scheduler_combo.setCurrentIndex(
                training_page.learning_rate_scheduler_combo.findData("COSINE")
            ),
            # Mission 121: same contract for the 5 new Precision/Memory
            # widgets.
            lambda: training_page.train_dtype_combo.setCurrentIndex(
                training_page.train_dtype_combo.findData("FLOAT_16")
            ),
            lambda: training_page.main_model_weight_dtype_combo.setCurrentIndex(
                training_page.main_model_weight_dtype_combo.findData("FLOAT_16")
            ),
            lambda: training_page.text_encoder_weight_dtype_combo.setCurrentIndex(
                training_page.text_encoder_weight_dtype_combo.findData("FLOAT_16")
            ),
            lambda: training_page.text_encoder_2_weight_dtype_combo.setCurrentIndex(
                training_page.text_encoder_2_weight_dtype_combo.findData("FLOAT_16")
            ),
            lambda: training_page.vae_weight_dtype_combo.setCurrentIndex(
                training_page.vae_weight_dtype_combo.findData("FLOAT_32")
            ),
        )
        for mutate in mutations:
            training_page._dirty = False
            mutate()
            self.assertTrue(training_page._dirty, f"{mutate} did not mark the form dirty")

    # --- 2. programmatic load / non-destructive refresh ----------------

    def test_dirty_draft_preserved_across_unrelated_character_created(self):
        """
        Mission 105's core non-regression test — mirrors
        LoRAPageDirtyStateTest's exact scenario: an unrelated mutation
        elsewhere (creating a second Character, routed to
        update_trainings() via CHARACTER_CREATED, never a context reset)
        must never wipe an unsaved parameter draft.
        """
        _, _, character_manager, _, training_page, _, _ = self._prepare()

        training_page.base_model_edit.setText("DRAFT NOT SAVED YET")
        self.assertTrue(training_page._dirty)

        character_manager.create("SecondCharacter")

        self.assertEqual(training_page.base_model_edit.text(), "DRAFT NOT SAVED YET")
        self.assertTrue(training_page._dirty)

    def test_reload_of_same_training_never_marks_dirty(self):
        _, _, _, _, training_page, _, _ = self._prepare()

        self.assertFalse(training_page._dirty)
        training_page.update_trainings()
        self.assertFalse(training_page._dirty)

    # --- 3. Save --------------------------------------------------------

    def test_successful_save_clears_dirty_and_persists(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()

        training_page.base_model_edit.setText("models/new-checkpoint.safetensors")
        training_page.save_training_parameters()

        self.assertFalse(training_page._dirty)
        self.assertEqual(training.base_model_source, "models/new-checkpoint.safetensors")

    def test_failed_save_resyncs_parameters_and_keeps_dirty(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()

        training_page.base_model_edit.setText("models/unsaved.safetensors")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.save_training_parameters()

        mock_critical.assert_called_once()
        self.assertEqual(
            training_page.base_model_edit.text(), "models/v1-5-pruned.safetensors"
        )

    # --- 4. selection switch: Save / Discard / Cancel -------------------

    def _create_second_training(self, training_manager, dataset):
        return training_manager.create("Session 2", dataset.dataset_id)

    def test_switch_selection_cancel_restores_previous_selection_and_keeps_dirty(self):
        _, _, _, training_manager, training_page, training, dataset = self._prepare()
        second = self._create_second_training(training_manager, dataset)
        training_page.update_trainings()

        training_page.base_model_edit.setText("DRAFT")
        self.assertTrue(training_page._dirty)

        second_item = next(
            training_page.training_list.item(i)
            for i in range(training_page.training_list.count())
            if training_page.training_list.item(i).data(Qt.UserRole) == second.training_id
        )

        with patch.object(
            training_page, "_confirm_discard_training_before_switch",
            return_value=QMessageBox.Cancel,
        ):
            training_page.training_list.setCurrentItem(second_item)

        self.assertEqual(training_manager.active_training_id, training.training_id)
        self.assertEqual(training_page.base_model_edit.text(), "DRAFT")
        self.assertTrue(training_page._dirty)
        self.assertEqual(training_page.training_list.currentItem().data(Qt.UserRole), training.training_id)

    def test_switch_selection_discard_loses_draft_and_switches(self):
        _, _, _, training_manager, training_page, training, dataset = self._prepare()
        second = self._create_second_training(training_manager, dataset)
        training_page.update_trainings()

        training_page.base_model_edit.setText("DRAFT")

        second_item = next(
            training_page.training_list.item(i)
            for i in range(training_page.training_list.count())
            if training_page.training_list.item(i).data(Qt.UserRole) == second.training_id
        )

        with patch.object(
            training_page, "_confirm_discard_training_before_switch",
            return_value=QMessageBox.Discard,
        ):
            training_page.training_list.setCurrentItem(second_item)

        self.assertEqual(training_manager.active_training_id, second.training_id)
        self.assertFalse(training_page._dirty)
        self.assertEqual(training_page.base_model_edit.text(), "")

    def test_switch_selection_save_persists_then_switches(self):
        _, _, _, training_manager, training_page, training, dataset = self._prepare()
        second = self._create_second_training(training_manager, dataset)
        training_page.update_trainings()

        training_page.base_model_edit.setText("models/saved-before-switch.safetensors")

        second_item = next(
            training_page.training_list.item(i)
            for i in range(training_page.training_list.count())
            if training_page.training_list.item(i).data(Qt.UserRole) == second.training_id
        )

        with patch.object(
            training_page, "_confirm_discard_training_before_switch",
            return_value=QMessageBox.Save,
        ):
            training_page.training_list.setCurrentItem(second_item)

        self.assertEqual(training_manager.active_training_id, second.training_id)
        self.assertFalse(training_page._dirty)
        self.assertEqual(training.base_model_source, "models/saved-before-switch.safetensors")

    # --- 5. deletion ------------------------------------------------------

    def _confirm_delete(self, accept: bool):
        # Mission 105: same interception technique already established
        # by TrainingPageDeleteConfirmationTest._confirm_delete() —
        # distinct sentinels per addButton() call, never a shared object,
        # so clickedButton() unambiguously identifies which button "was
        # clicked" without depending on call order elsewhere.
        patcher = patch("src.ui.pages.training_page.QMessageBox")
        mock_cls = patcher.start()
        self.addCleanup(patcher.stop)

        accept_sentinel = object()
        cancel_sentinel = object()
        box_instance = mock_cls.return_value
        box_instance.addButton.side_effect = [accept_sentinel, cancel_sentinel]
        box_instance.clickedButton.return_value = (
            accept_sentinel if accept else cancel_sentinel
        )

        return mock_cls

    def test_delete_active_training_without_dirty_shows_plain_confirmation(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()

        mock_cls = self._confirm_delete(accept=False)
        training_page.delete_training()

        message_text = mock_cls.return_value.setText.call_args[0][0]
        self.assertNotIn("non enregistrés", message_text)

    def test_delete_active_dirty_training_enriches_confirmation_text(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("DRAFT")

        mock_cls = self._confirm_delete(accept=False)
        training_page.delete_training()

        message_text = mock_cls.return_value.setText.call_args[0][0]
        self.assertIn("non enregistrés", message_text)

    # --- 6. Character/Workspace context reset ------------------------------

    def test_character_selected_resets_dirty_draft_without_dialog(self):
        _, _, character_manager, _, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("DRAFT")
        self.assertTrue(training_page._dirty)

        second_character = character_manager.create("SecondCharacter")
        with patch("src.ui.pages.training_page.QMessageBox") as mock_cls:
            character_manager.select(second_character.character_id)

        mock_cls.assert_not_called()
        self.assertFalse(training_page._dirty)
        self.assertEqual(training_page.base_model_edit.text(), "")
        self.assertEqual(training_page.training_list.count(), 0)

    def test_workspace_closed_resets_dirty_draft_without_dialog(self):
        _, workspace_manager, _, _, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("DRAFT")
        self.assertTrue(training_page._dirty)

        with patch("src.ui.pages.training_page.QMessageBox") as mock_cls:
            workspace_manager.close()

        mock_cls.assert_not_called()
        self.assertFalse(training_page._dirty)
        self.assertEqual(training_page.base_model_edit.text(), "")

    # --- 7. confirm_context_change() (MainWindow guard) ---------------------

    def test_confirm_context_change_clean_returns_true_without_dialog(self):
        _, _, _, _, training_page, _, _ = self._prepare()

        with patch("src.ui.pages.training_page.QMessageBox") as mock_cls:
            result = training_page.confirm_context_change()

        mock_cls.assert_not_called()
        self.assertTrue(result)

    def test_confirm_context_change_cancel_returns_false_and_keeps_draft(self):
        _, _, _, _, training_page, _, _ = self._prepare()
        training_page.base_model_edit.setText("DRAFT")

        with patch.object(
            training_page, "_confirm_discard_training_before_switch",
            return_value=QMessageBox.Cancel,
        ):
            result = training_page.confirm_context_change()

        self.assertFalse(result)
        self.assertTrue(training_page._dirty)
        self.assertEqual(training_page.base_model_edit.text(), "DRAFT")

    def test_confirm_context_change_save_persists_and_returns_true(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("models/saved-on-close.safetensors")

        with patch.object(
            training_page, "_confirm_discard_training_before_switch",
            return_value=QMessageBox.Save,
        ):
            result = training_page.confirm_context_change()

        self.assertTrue(result)
        self.assertFalse(training_page._dirty)
        self.assertEqual(training.base_model_source, "models/saved-on-close.safetensors")

    # --- 8. Prepare / Start invariant ---------------------------------------

    def test_prepare_dirty_saves_then_prepares(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("models/dirty-before-prepare.safetensors")

        with patch("src.ui.pages.training_page.QMessageBox.information"):
            training_page.prepare_onetrainer_config()

        self.assertFalse(training_page._dirty)
        self.assertEqual(training.base_model_source, "models/dirty-before-prepare.safetensors")

        # Mission 105: prepare_onetrainer_config() is idempotent by
        # design (Mission 097) — calling it again purely to obtain its
        # public config_path return value re-confirms the same file
        # training_page.prepare_onetrainer_config() just wrote above.
        result = training_manager.prepare_onetrainer_config(training.training_id)
        config = json.loads(Path(result.config_path).read_text())
        self.assertEqual(config["base_model_name"], "models/dirty-before-prepare.safetensors")

    def test_prepare_failed_save_never_calls_manager_prepare(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("DRAFT")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.training_page.QMessageBox.critical"), patch.object(
            training_manager, "prepare_onetrainer_config"
        ) as mock_prepare:
            training_page.prepare_onetrainer_config()

        mock_prepare.assert_not_called()
        # Mission 105: save_training_parameters()'s own established
        # (Mission 097) failure contract resyncs the fields to the
        # rolled-back Domain state and clears _dirty — the same
        # "discard and resync" contract LoRAPage.save_metadata() already
        # uses. prepare_onetrainer_config() must detect the failure via
        # save_training_parameters()'s return value, never by
        # re-inspecting _dirty afterward — this is what mock_prepare.
        # assert_not_called() above actually proves.
        self.assertFalse(training_page._dirty)
        self.assertEqual(training_page.base_model_edit.text(), "models/v1-5-pruned.safetensors")

    def test_start_clean_and_already_prepared_still_calls_prepare(self):
        """
        Pre-M124 correction (CAS D): even when the form is clean and an
        earlier Prepare already wrote a valid onetrainer_config.json,
        Start still calls prepare_onetrainer_config() unconditionally —
        no longer skipped based on a session-local staleness flag. The
        extra call is safe (idempotent, filesystem-only) and never
        blocks job creation/run.
        """
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        self.assertFalse(training_page._dirty)

        with patch.object(
            training_manager, "prepare_onetrainer_config",
            wraps=training_manager.prepare_onetrainer_config,
        ) as mock_prepare, patch(
            "src.ui.pages.training_page.TrainingJobRunner"
        ) as mock_runner_cls:
            training_page.start_training()

        mock_prepare.assert_called_once()
        mock_runner_cls.return_value.start.assert_called_once()
        self.assertEqual(len(training.jobs), 1)

    def test_start_dirty_saves_prepares_and_creates_job_with_new_values(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()

        training_page.base_model_edit.setText("models/new-checkpoint.safetensors")
        self.assertTrue(training_page._dirty)

        with patch("src.ui.pages.training_page.TrainingJobRunner") as mock_runner_cls:
            training_page.start_training()

        self.assertFalse(training_page._dirty)
        self.assertEqual(training.base_model_source, "models/new-checkpoint.safetensors")
        mock_runner_cls.return_value.start.assert_called_once()

        self.assertEqual(len(training.jobs), 1)
        job = training.jobs[0]
        job_paths = training_manager.job_paths(training.training_id, job.job_id)
        snapshot = json.loads(Path(job_paths.config_snapshot_path).read_text())
        self.assertEqual(snapshot["base_model_name"], "models/new-checkpoint.safetensors")

    def test_start_dirty_save_failure_creates_no_job(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        training_page.base_model_edit.setText("DRAFT")

        with patch.object(
            WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full")
        ), patch("src.ui.pages.training_page.QMessageBox.critical"), patch.object(
            training_manager, "create_job"
        ) as mock_create_job, patch(
            "src.ui.pages.training_page.TrainingJobRunner"
        ) as mock_runner_cls:
            training_page.start_training()

        mock_create_job.assert_not_called()
        mock_runner_cls.return_value.start.assert_not_called()
        # Mission 105: same "discard and resync" contract as
        # test_prepare_failed_save_never_calls_manager_prepare above —
        # start_training() must detect the save failure via
        # save_training_parameters()'s return value, never by
        # re-inspecting _dirty, which is already False again here.
        self.assertFalse(training_page._dirty)
        self.assertEqual(training_page.base_model_edit.text(), "models/v1-5-pruned.safetensors")

    def test_start_prepare_failure_creates_no_job(self):
        """
        Pre-M124 correction (CAS E): Prepare is now attempted
        unconditionally on every Start, including for an already-clean,
        already-prepared Training — so a Prepare failure must be caught
        here too, before create_job() is ever reached, exactly as it
        already was for a dirty/stale form.
        """
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        self.assertFalse(training_page._dirty)

        with patch.object(
            training_manager, "prepare_onetrainer_config",
            side_effect=TrainingPreparationError("boom"),
        ), patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical, patch.object(
            training_manager, "create_job"
        ) as mock_create_job, patch(
            "src.ui.pages.training_page.TrainingJobRunner"
        ) as mock_runner_cls:
            training_page.start_training()

        mock_critical.assert_called_once()
        mock_create_job.assert_not_called()
        mock_runner_cls.return_value.start.assert_not_called()

    # --- Mission 106: real (unmocked) base_model_source validation,
    # exercised through the real M105 dirty -> save -> auto-Prepare
    # flow -- never a simulated TrainingPreparationError side_effect
    # like the tests above, to prove the real validation itself
    # integrates correctly with Save/_dirty. ----------------------------

    def test_start_dirty_with_invalid_base_model_source_saves_then_stops_before_job(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()
        config_path = self.folder / "training" / training.training_id / "onetrainer_config.json"
        config_before = config_path.read_text(encoding="utf-8")

        training_page.base_model_edit.setText("")
        self.assertTrue(training_page._dirty)

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical, patch(
            "src.ui.pages.training_page.TrainingJobRunner"
        ) as mock_runner_cls:
            training_page.start_training()

        # The dirty edit was genuinely saved for real before validation
        # ran -- Save and validation are not the same step.
        self.assertEqual(training.base_model_source, "")
        self.assertFalse(training_page._dirty)

        mock_critical.assert_called_once()
        self.assertEqual(len(training.jobs), 0)
        mock_runner_cls.return_value.start.assert_not_called()
        # The config file written by _prepare()'s own earlier, valid
        # call is never overwritten by the failed attempt.
        self.assertEqual(config_path.read_text(encoding="utf-8"), config_before)

    def test_prepare_with_invalid_base_model_source_shows_actionable_error(self):
        _, _, _, training_manager, training_page, training, _ = self._prepare()

        training_page.base_model_edit.setText("   ")
        self.assertTrue(training_page._dirty)

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical:
            training_page.prepare_onetrainer_config()

        self.assertEqual(training.base_model_source, "   ")
        self.assertFalse(training_page._dirty)
        mock_critical.assert_called_once()
        shown_text = mock_critical.call_args.args[2]
        self.assertIn("modèle de base", shown_text)


class TrainingPageStartPrepareTest(unittest.TestCase):
    """
    Pre-M124 correction — dedicated coverage for
    `TrainingPage.start_training()`'s new, unconditional contract:

        Save (if dirty) -> Prepare (always) -> Create Job -> Run

    `_config_stale` used to gate the Prepare step: a purely
    session-local, per-page-instance flag reset by any reload of the
    parameter widgets (switching Training and back, or an application
    restart) — with no relation to whether onetrainer_config.json on
    disk still matched this Training's real, persisted state. A
    Training never explicitly Prepared, or one whose file had gone
    stale across such a reload, could reach create_job() with either no
    file at all (a raw, English TrainingJobError) or a stale one
    (silently starting a real job with outdated parameters). Start now
    always (re)prepares from the Training's current Domain state
    first — see TrainingPageDirtyStateTest above for the complementary
    "clean and already prepared" (CAS D) and "Prepare failure" (CAS E)
    coverage, which did not need this dedicated fixture.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.folder = Path(self.tmp_dir) / "Project"

    def _wire(self):
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        character_manager = CharacterManager(workspace_manager, event_bus=event_bus)
        dataset_manager = DatasetManager(character_manager, workspace_manager, event_bus=event_bus)
        training_manager = TrainingManager(character_manager, workspace_manager, event_bus=event_bus)
        application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "app_settings"
        )
        lora_library_manager = MagicMock()
        lora_library_manager.get.return_value = None
        training_page = TrainingPage(
            training_manager, dataset_manager, workspace_manager, application_settings_manager,
            lora_library_manager,
        )
        for event_name in TRAINING_EVENTS:
            event_bus.subscribe(event_name, training_page.update_trainings)
        return workspace_manager, character_manager, dataset_manager, training_manager, training_page

    def _make_training(self, workspace_manager, character_manager, dataset_manager, training_manager):
        workspace_manager.create(self.folder)
        character_manager.create("Aria")

        dataset = dataset_manager.create("Portraits")
        source_dir = Path(self.tmp_dir) / "Source"
        source_dir.mkdir(parents=True, exist_ok=True)
        image_path = source_dir / "a.png"
        image_path.write_bytes(b"fake-png-bytes")
        dataset.images = [Image(image_id=str(image_path), file_path=str(image_path))]

        training = training_manager.create("Session 1", dataset.dataset_id)
        training_manager.select(training.training_id)
        training_manager.update(
            base_model_source="models/v1-5-pruned.safetensors",
            architecture=TRAINING_ARCHITECTURE_SD15,
            resolution=512,
        )
        return training

    def _config_path(self, training):
        return self.folder / "training" / training.training_id / "onetrainer_config.json"

    # --- CAS A: a Training never Prepared at all -----------------------

    def test_start_never_prepared_training_prepares_automatically(self):
        """
        A fresh Training, defaults accepted, no field ever edited (so
        _dirty stays False the whole time), Start clicked directly —
        never Prepared before. Must succeed: Prepare runs automatically,
        the old "has not been prepared yet — call
        prepare_onetrainer_config()" TrainingJobError must never surface.
        """
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        training = self._make_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.update_trainings()

        self.assertFalse(self._config_path(training).is_file())
        self.assertFalse(training_page._dirty)

        with patch("src.ui.pages.training_page.QMessageBox.critical") as mock_critical, \
                patch("src.ui.pages.training_page.TrainingJobRunner") as mock_runner_cls:
            training_page.start_training()

        mock_critical.assert_not_called()
        self.assertTrue(self._config_path(training).is_file())
        mock_runner_cls.return_value.start.assert_called_once()
        self.assertEqual(len(training.jobs), 1)

    # --- CAS B: a previously-Prepared config that has since gone stale -

    def test_start_after_edit_and_navigation_away_and_back_uses_current_value_not_stale_file(self):
        """
        Training A Prepared once with epochs=X, then epochs changed to Y
        and saved (but Prepare not clicked again), then the page
        navigates to another Training and back — reproducing exactly
        the sequence that used to reset the now-removed _config_stale
        flag to False for A, even though A's own onetrainer_config.json
        on disk still held X. Start on A must still re-Prepare and the
        Job actually created must reflect Y, never the stale X.
        """
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        training_a = self._make_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_manager.update(epochs=10)
        training_page.update_trainings()
        training_manager.prepare_onetrainer_config(training_a.training_id)

        config_before = json.loads(self._config_path(training_a).read_text(encoding="utf-8"))
        self.assertEqual(config_before["epochs"], 10)

        # A second Training to navigate away to and back from.
        dataset_b = dataset_manager.create("Other Dataset")
        training_b = training_manager.create("Session 2", dataset_b.dataset_id)

        training_manager.select(training_a.training_id)
        training_page.update_trainings()
        training_page.epochs_spinbox.setValue(40)
        training_page.save_training_parameters()
        self.assertEqual(training_a.epochs, 40)

        # Navigate away and back — this used to wipe the now-removed
        # _config_stale flag for training_a, defeating the safety net.
        training_manager.select(training_b.training_id)
        training_page.update_trainings()
        training_manager.select(training_a.training_id)
        training_page.update_trainings()
        self.assertFalse(training_page._dirty)

        with patch("src.ui.pages.training_page.TrainingJobRunner") as mock_runner_cls:
            training_page.start_training()

        mock_runner_cls.return_value.start.assert_called_once()
        self.assertEqual(len(training_a.jobs), 1)
        job = training_a.jobs[0]
        job_paths = training_manager.job_paths(training_a.training_id, job.job_id)
        snapshot = json.loads(Path(job_paths.config_snapshot_path).read_text(encoding="utf-8"))
        self.assertEqual(snapshot["epochs"], 40)

    # --- CAS C: existence of an old file is never treated as freshness -

    def test_start_ignores_existing_file_and_rebuilds_from_current_domain_state(self):
        """
        Directly corrupts the on-disk onetrainer_config.json to a value
        that could never come from the current Training state, without
        going through Save/Prepare — simulating "an old prepared file
        exists" independently of any in-memory session flag. Start must
        never treat that file's mere existence as proof of freshness:
        the Job created must reflect the Training's real current state,
        not whatever the file on disk happened to contain.
        """
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        training = self._make_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.update_trainings()
        training_manager.prepare_onetrainer_config(training.training_id)

        config_path = self._config_path(training)
        corrupted = json.loads(config_path.read_text(encoding="utf-8"))
        corrupted["epochs"] = 999999
        config_path.write_text(json.dumps(corrupted), encoding="utf-8")

        self.assertFalse(training_page._dirty)

        with patch("src.ui.pages.training_page.TrainingJobRunner") as mock_runner_cls:
            training_page.start_training()

        mock_runner_cls.return_value.start.assert_called_once()
        job = training.jobs[0]
        job_paths = training_manager.job_paths(training.training_id, job.job_id)
        snapshot = json.loads(Path(job_paths.config_snapshot_path).read_text(encoding="utf-8"))
        self.assertNotEqual(snapshot["epochs"], 999999)
        self.assertEqual(snapshot["epochs"], training.epochs)

    # --- CAS F: strict operation order ----------------------------------

    def test_start_calls_prepare_then_create_job_then_run_in_that_order(self):
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        self._make_training(workspace_manager, character_manager, dataset_manager, training_manager)
        training_page.update_trainings()

        call_order = []
        real_prepare = training_manager.prepare_onetrainer_config
        real_create_job = training_manager.create_job

        def recording_prepare(*args, **kwargs):
            call_order.append("prepare")
            return real_prepare(*args, **kwargs)

        def recording_create_job(*args, **kwargs):
            call_order.append("create_job")
            return real_create_job(*args, **kwargs)

        with patch.object(
            training_manager, "prepare_onetrainer_config", side_effect=recording_prepare
        ), patch.object(
            training_manager, "create_job", side_effect=recording_create_job
        ), patch("src.ui.pages.training_page.TrainingJobRunner") as mock_runner_cls:
            mock_runner_cls.return_value.start.side_effect = lambda *a, **k: call_order.append("run")
            training_page.start_training()

        self.assertEqual(call_order, ["prepare", "create_job", "run"])

    # --- Mission 124 M: a new M124 field benefits from the pre-M124 fix -

    def test_a_new_m124_field_modified_just_before_start_reaches_the_prepared_config(self):
        """
        M: does not duplicate the whole _config_stale test battery above
        — a single, direct proof that a Mission 124 field (never existed
        when the pre-M124 correction landed) modified right before Start,
        without a separate Prepare click, ends up in the configuration
        actually prepared before create_job(), exactly like every other
        field already proven by CAS A-F above.
        """
        workspace_manager, character_manager, dataset_manager, training_manager, training_page = self._wire()
        training = self._make_training(
            workspace_manager, character_manager, dataset_manager, training_manager
        )
        training_page.update_trainings()
        training_manager.prepare_onetrainer_config(training.training_id)

        training_page.text_encoder_train_combo.setCurrentIndex(
            training_page.text_encoder_train_combo.findData(False)
        )
        self.assertTrue(training_page._dirty)

        with patch("src.ui.pages.training_page.TrainingJobRunner") as mock_runner_cls:
            training_page.start_training()

        mock_runner_cls.return_value.start.assert_called_once()
        job = training.jobs[0]
        job_paths = training_manager.job_paths(training.training_id, job.job_id)
        snapshot = json.loads(Path(job_paths.config_snapshot_path).read_text(encoding="utf-8"))
        self.assertEqual(snapshot["text_encoder"], {"train": False})


if __name__ == "__main__":
    unittest.main()
