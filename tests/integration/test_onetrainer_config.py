"""
Coverage for src/engines/onetrainer_config.py — Mission 097's pure
OneTrainer configuration-dict construction. No filesystem I/O, no
network, no dependency on OneTrainer actually being installed: these
are plain functions returning dict, tested directly against their
output structure — same philosophy as test_comfyui_workflows.py.
"""

import unittest

from src.engines.onetrainer_config import (
    OneTrainerConfigError,
    _AUDITED_CONFIG_VERSION,
    _PROTECTED_CONFIG_KEYS,
    _STRUCTURED_CONFIG_KEYS,
    build_training_config,
)


class BuildTrainingConfigTest(unittest.TestCase):

    def _build(self, **overrides):
        kwargs = {
            "architecture": "SD15",
            "base_model_source": "/models/v1-5-pruned.safetensors",
            "resolution": 512,
            "epochs": 100,
            "learning_rate": 0.0003,
            "lora_rank": 16,
            "lora_alpha": 1.0,
            "output_model_destination": "/workspace/training/T1/output/lora.safetensors",
            "concept_name": "Session 1",
            "concept_path": "/workspace/training/T1/concept",
        }
        kwargs.update(overrides)
        return build_training_config(**kwargs)

    def test_training_method_is_always_lora(self):
        self.assertEqual(self._build()["training_method"], "LORA")

    def test_sd15_maps_to_the_real_onetrainer_model_type(self):
        self.assertEqual(self._build(architecture="SD15")["model_type"], "STABLE_DIFFUSION_15")

    def test_sdxl_maps_to_the_real_onetrainer_model_type(self):
        self.assertEqual(self._build(architecture="SDXL")["model_type"], "STABLE_DIFFUSION_XL_10_BASE")

    def test_flux_maps_to_the_real_onetrainer_model_type(self):
        self.assertEqual(self._build(architecture="FLUX")["model_type"], "FLUX_DEV_1")

    def test_unknown_architecture_raises_explicitly(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="POKEMON")

    def test_base_model_source_is_forwarded_verbatim_as_base_model_name(self):
        config = self._build(base_model_source="stabilityai/stable-diffusion-xl-base-1.0")
        self.assertEqual(config["base_model_name"], "stabilityai/stable-diffusion-xl-base-1.0")

    def test_resolution_int_is_converted_to_the_onetrainer_string_form(self):
        # Mission 097 section 3: OneTrainer's own real presets use a
        # string ("512"/"1024"/"768"), never an int.
        config = self._build(resolution=1024)
        self.assertEqual(config["resolution"], "1024")
        self.assertIsInstance(config["resolution"], str)

    def test_epochs_learning_rate_lora_rank_lora_alpha_are_forwarded_verbatim(self):
        config = self._build(epochs=50, learning_rate=0.0005, lora_rank=32, lora_alpha=2.0)
        self.assertEqual(config["epochs"], 50)
        self.assertEqual(config["learning_rate"], 0.0005)
        self.assertEqual(config["lora_rank"], 32)
        self.assertEqual(config["lora_alpha"], 2.0)

    def test_output_model_format_is_always_safetensors(self):
        self.assertEqual(self._build()["output_model_format"], "SAFETENSORS")

    def test_output_model_destination_is_forwarded_verbatim(self):
        config = self._build(output_model_destination="/x/output/lora.safetensors")
        self.assertEqual(config["output_model_destination"], "/x/output/lora.safetensors")

    def test_concepts_is_a_single_element_list_embedded_directly(self):
        # Mission 097 section 3.2: never a separate concepts.json file —
        # embedded directly under the "concepts" key.
        config = self._build(concept_name="Session 1", concept_path="/x/concept")
        self.assertEqual(config["concepts"], [{"name": "Session 1", "path": "/x/concept"}])

    def test_concept_dict_is_deliberately_minimal(self):
        # Mission 097 section 3.2: only name/path — every other
        # ConceptConfig field is left for OneTrainer's own
        # ConceptConfig.default_values() to fill in.
        concept = self._build()["concepts"][0]
        self.assertEqual(set(concept.keys()), {"name", "path"})

    def test_no_key_beyond_the_documented_minimal_set(self):
        # Locks in the "deliberately minimal" contract itself — a
        # regression here would mean this adapter started silently
        # duplicating OneTrainer's own schema.
        config = self._build()
        self.assertEqual(
            set(config.keys()),
            {
                "__version", "training_method", "model_type", "base_model_name", "resolution",
                "epochs", "learning_rate", "lora_rank", "lora_alpha",
                "output_model_format", "output_model_destination", "concepts",
            },
        )

    # --- Mission 120: batch_size/gradient_accumulation_steps/
    # learning_rate_scheduler/extra_overrides -----------------------

    def test_batch_size_and_gradient_accumulation_steps_omitted_when_not_configured(self):
        # Mission 120 section 3.2/4: 0 is the "not configured" sentinel
        # for both — the built config must not carry either key at all,
        # letting OneTrainer's own real default (1 for both) apply
        # exactly as it did before this mission.
        config = self._build()
        self.assertNotIn("batch_size", config)
        self.assertNotIn("gradient_accumulation_steps", config)

    def test_batch_size_and_gradient_accumulation_steps_forwarded_when_configured(self):
        config = self._build(batch_size=4, gradient_accumulation_steps=2)
        self.assertEqual(config["batch_size"], 4)
        self.assertEqual(config["gradient_accumulation_steps"], 2)

    def test_learning_rate_scheduler_omitted_when_not_configured(self):
        # "" is the "not configured" sentinel — never one of
        # LearningRateScheduler's own real enum values.
        config = self._build()
        self.assertNotIn("learning_rate_scheduler", config)

    def test_learning_rate_scheduler_forwarded_when_configured(self):
        config = self._build(learning_rate_scheduler="COSINE")
        self.assertEqual(config["learning_rate_scheduler"], "COSINE")

    def test_extra_overrides_default_adds_nothing(self):
        config_without = self._build()
        config_with_empty = self._build(extra_overrides={})
        config_with_none = self._build(extra_overrides=None)
        self.assertEqual(config_without, config_with_empty)
        self.assertEqual(config_without, config_with_none)

    def test_extra_overrides_without_collision_is_propagated_verbatim(self):
        config = self._build(extra_overrides={"loss_weight_fn": "MIN_SNR_GAMMA"})
        self.assertEqual(config["loss_weight_fn"], "MIN_SNR_GAMMA")

    def test_extra_overrides_rejects_every_protected_internal_key(self):
        # Mission 120 section 3.3: these are always computed and written
        # last by TrainingManager — never overridable, regardless of
        # whether this function itself ever sets them.
        for key in sorted(_PROTECTED_CONFIG_KEYS):
            with self.subTest(key=key):
                with self.assertRaises(OneTrainerConfigError):
                    self._build(extra_overrides={key: "anything"})

    def test_extra_overrides_rejects_every_already_structured_key(self):
        # Mission 120 section 3.3: never two sources of truth for the
        # same structured Training/OneTrainerSettings-backed value.
        for key in sorted(_STRUCTURED_CONFIG_KEYS):
            with self.subTest(key=key):
                with self.assertRaises(OneTrainerConfigError):
                    self._build(extra_overrides={key: "anything"})

    def test_extra_overrides_collision_raises_before_any_mutation_concern(self):
        # A rejected extra_overrides never partially lands — the whole
        # call raises, nothing is returned.
        with self.assertRaises(OneTrainerConfigError):
            self._build(extra_overrides={"workspace_dir": "C:\\evil", "loss_weight_fn": "MIN_SNR_GAMMA"})

    def test_protected_config_keys_enumerated_exactly(self):
        # Mission 120 section 3.3: centralized and tested explicitly —
        # a future silent change to this set must break this test.
        self.assertEqual(
            _PROTECTED_CONFIG_KEYS,
            frozenset(
                {
                    "workspace_dir",
                    "cache_dir",
                    "debug_dir",
                    "output_model_destination",
                    "concept_file_name",
                    "concepts",
                    "__version",
                }
            ),
        )

    def test_structured_config_keys_enumerated_exactly(self):
        self.assertEqual(
            _STRUCTURED_CONFIG_KEYS,
            frozenset(
                {
                    "training_method",
                    "model_type",
                    "base_model_name",
                    "resolution",
                    "epochs",
                    "learning_rate",
                    "lora_rank",
                    "lora_alpha",
                    "batch_size",
                    "gradient_accumulation_steps",
                    "learning_rate_scheduler",
                    "output_model_format",
                }
            ),
        )

    def test_version_key_is_present_and_matches_the_audited_config_version(self):
        # Mission 097: discovered via this mission's own real smoke
        # test — BaseConfig.from_dict() replays every historical
        # migration against a dict with no "__version" key (defaulting
        # to version 0), which crashes against this adapter's
        # deliberately minimal shape (a migration assumes a fully
        # populated old config). Sending the installed TrainConfig's
        # own current config_version makes that replay a no-op. See
        # _AUDITED_CONFIG_VERSION's own module-level comment — this is
        # this specific installation's audited version, never presented
        # as a universal OneTrainer format constant.
        config = self._build()
        self.assertIn("__version", config)
        self.assertEqual(config["__version"], _AUDITED_CONFIG_VERSION)
        self.assertEqual(_AUDITED_CONFIG_VERSION, 10)


if __name__ == "__main__":
    unittest.main()
