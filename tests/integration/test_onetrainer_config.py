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
