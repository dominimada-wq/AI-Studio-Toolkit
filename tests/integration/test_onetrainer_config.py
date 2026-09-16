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
    _DTYPE_FIELDS_BY_ARCHITECTURE,
    _FLOW_MATCHING_FIELDS_BY_ARCHITECTURE,
    _GRADIENT_CHECKPOINTING_VALUES,
    _LORA_LAYER_FILTER_TRANSLATION,
    _OPTIMIZER_STRUCTURED_SUBKEYS,
    _PROTECTED_CONFIG_KEYS,
    _STOP_TRAINING_FIELD_TO_COMPONENT_KEY,
    _STOP_TRAINING_FIELDS_BY_ARCHITECTURE,
    _STOP_TRAINING_MODE_VALUES,
    _STRUCTURED_CONFIG_KEYS,
    _TRAIN_FIELD_TO_COMPONENT_KEY,
    _TRAIN_FIELDS_BY_ARCHITECTURE,
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
                    "train_dtype",
                    "unet",
                    "transformer",
                    "text_encoder",
                    "text_encoder_2",
                    "vae",
                    "optimizer",
                    "layer_filter",
                    "layer_filter_regex",
                    "timestep_distribution",
                    "dynamic_timestep_shifting",
                    "timestep_shift",
                    "gradient_checkpointing",
                }
            ),
        )

    # --- Mission 121: train_dtype/*_weight_dtype -----------------------

    def test_train_dtype_omitted_when_not_configured(self):
        config = self._build()
        self.assertNotIn("train_dtype", config)

    def test_train_dtype_forwarded_when_configured(self):
        config = self._build(train_dtype="BFLOAT_16")
        self.assertEqual(config["train_dtype"], "BFLOAT_16")

    def test_weight_dtype_fields_omitted_when_not_configured(self):
        # Mission 121 section 3.6: the non-regression case — none of the
        # 5 nested component keys ever appear when every field stays at
        # its "" sentinel, for any of the three architectures.
        for architecture in ("SD15", "SDXL", "FLUX"):
            with self.subTest(architecture=architecture):
                config = self._build(architecture=architecture)
                for key in ("unet", "transformer", "text_encoder", "text_encoder_2", "vae"):
                    self.assertNotIn(key, config)

    def test_unet_weight_dtype_translated_into_nested_component_shape(self):
        config = self._build(architecture="SD15", unet_weight_dtype="FLOAT_16")
        self.assertEqual(config["unet"], {"weight_dtype": "FLOAT_16"})

    def test_transformer_weight_dtype_translated_into_nested_component_shape(self):
        config = self._build(architecture="FLUX", transformer_weight_dtype="BFLOAT_16")
        self.assertEqual(config["transformer"], {"weight_dtype": "BFLOAT_16"})

    def test_text_encoder_weight_dtype_translated_into_nested_component_shape(self):
        config = self._build(architecture="SD15", text_encoder_weight_dtype="FLOAT_16")
        self.assertEqual(config["text_encoder"], {"weight_dtype": "FLOAT_16"})

    def test_text_encoder_2_weight_dtype_translated_into_nested_component_shape(self):
        config = self._build(architecture="SDXL", text_encoder_2_weight_dtype="FLOAT_16")
        self.assertEqual(config["text_encoder_2"], {"weight_dtype": "FLOAT_16"})

    def test_vae_weight_dtype_translated_into_nested_component_shape(self):
        config = self._build(architecture="SD15", vae_weight_dtype="FLOAT_32")
        self.assertEqual(config["vae"], {"weight_dtype": "FLOAT_32"})

    def test_dtype_fields_by_architecture_enumerated_exactly(self):
        # Mission 121 section 3.3: centralized and tested explicitly,
        # confirmed directly against the real component fields of
        # modules/model/StableDiffusionModel.py/StableDiffusionXLModel.py/
        # FluxModel.py — a future silent change must break this test.
        self.assertEqual(
            _DTYPE_FIELDS_BY_ARCHITECTURE,
            {
                "SD15": frozenset(
                    {"unet_weight_dtype", "text_encoder_weight_dtype", "vae_weight_dtype"}
                ),
                "SDXL": frozenset(
                    {
                        "unet_weight_dtype",
                        "text_encoder_weight_dtype",
                        "text_encoder_2_weight_dtype",
                        "vae_weight_dtype",
                    }
                ),
                "FLUX": frozenset(
                    {
                        "transformer_weight_dtype",
                        "text_encoder_weight_dtype",
                        "text_encoder_2_weight_dtype",
                        "vae_weight_dtype",
                    }
                ),
            },
        )

    def test_sd15_accepts_every_one_of_its_valid_dtype_fields(self):
        config = self._build(
            architecture="SD15",
            train_dtype="FLOAT_16",
            unet_weight_dtype="FLOAT_16",
            text_encoder_weight_dtype="FLOAT_16",
            vae_weight_dtype="FLOAT_32",
        )
        self.assertEqual(config["train_dtype"], "FLOAT_16")
        self.assertEqual(config["unet"], {"weight_dtype": "FLOAT_16"})
        self.assertEqual(config["text_encoder"], {"weight_dtype": "FLOAT_16"})
        self.assertEqual(config["vae"], {"weight_dtype": "FLOAT_32"})

    def test_sd15_rejects_transformer_weight_dtype(self):
        # SD1.5 has no transformer component (modules/model/
        # StableDiffusionModel.py: unet/text_encoder/vae only).
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", transformer_weight_dtype="FLOAT_16")

    def test_sd15_rejects_text_encoder_2_weight_dtype(self):
        # SD1.5 has no text_encoder_2 component.
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_2_weight_dtype="FLOAT_16")

    def test_sdxl_accepts_every_one_of_its_valid_dtype_fields(self):
        config = self._build(
            architecture="SDXL",
            train_dtype="FLOAT_16",
            unet_weight_dtype="FLOAT_16",
            text_encoder_weight_dtype="FLOAT_16",
            text_encoder_2_weight_dtype="FLOAT_16",
            vae_weight_dtype="FLOAT_32",
        )
        self.assertEqual(config["unet"], {"weight_dtype": "FLOAT_16"})
        self.assertEqual(config["text_encoder_2"], {"weight_dtype": "FLOAT_16"})

    def test_sdxl_rejects_transformer_weight_dtype(self):
        # SDXL has no transformer component (uses unet, not transformer).
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SDXL", transformer_weight_dtype="FLOAT_16")

    def test_flux_accepts_every_one_of_its_valid_dtype_fields(self):
        config = self._build(
            architecture="FLUX",
            train_dtype="BFLOAT_16",
            transformer_weight_dtype="BFLOAT_16",
            text_encoder_weight_dtype="FLOAT_16",
            text_encoder_2_weight_dtype="FLOAT_16",
            vae_weight_dtype="FLOAT_32",
        )
        self.assertEqual(config["transformer"], {"weight_dtype": "BFLOAT_16"})
        self.assertEqual(config["text_encoder_2"], {"weight_dtype": "FLOAT_16"})

    def test_flux_rejects_unet_weight_dtype(self):
        # FLUX_DEV_1 has no unet component (modules/model/FluxModel.py
        # has `transformer`, never `unet`).
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="FLUX", unet_weight_dtype="FLOAT_16")

    def test_incompatible_dtype_field_error_names_the_offending_field(self):
        with self.assertRaisesRegex(OneTrainerConfigError, "transformer_weight_dtype"):
            self._build(architecture="SD15", transformer_weight_dtype="FLOAT_16")

    def test_extra_overrides_rejects_every_new_mission_121_structured_key(self):
        # Covered generically by test_extra_overrides_rejects_every_
        # already_structured_key (loops over the whole current
        # _STRUCTURED_CONFIG_KEYS) — this test locks in that the 6 new
        # keys are genuinely part of that set, not merely present by
        # coincidence, and that a *nested dict* value (the realistic
        # shape a caller might mistakenly pass) is rejected exactly like
        # a scalar one.
        for key in ("train_dtype", "unet", "transformer", "text_encoder", "text_encoder_2", "vae"):
            with self.subTest(key=key):
                self.assertIn(key, _STRUCTURED_CONFIG_KEYS)
                with self.assertRaises(OneTrainerConfigError):
                    self._build(extra_overrides={key: {"weight_dtype": "FLOAT_16"}})

    # --- Mission 122: optimizer/optimizer_extra_overrides -------------

    def test_optimizer_omitted_when_nothing_configured(self):
        # Mission 122 section 3.2: the non-regression case — no
        # "optimizer" key ever appears when both optimizer=="" and
        # optimizer_extra_overrides is empty, for any architecture.
        for architecture in ("SD15", "SDXL", "FLUX"):
            with self.subTest(architecture=architecture):
                config = self._build(architecture=architecture)
                self.assertNotIn("optimizer", config)

    def test_optimizer_adam_translated_into_nested_shape(self):
        config = self._build(optimizer="ADAM")
        self.assertEqual(config["optimizer"], {"optimizer": "ADAM"})

    def test_optimizer_adamw_translated_into_nested_shape(self):
        config = self._build(optimizer="ADAMW")
        self.assertEqual(config["optimizer"], {"optimizer": "ADAMW"})

    def test_optimizer_sgd_translated_into_nested_shape(self):
        config = self._build(optimizer="SGD")
        self.assertEqual(config["optimizer"], {"optimizer": "SGD"})

    def test_optimizer_extra_overrides_merged_alongside_discriminant(self):
        # Mission 122 section 3.2: optimizer_extra_overrides is a second,
        # narrower escape hatch than the global extra_overrides — legal
        # to combine with the structured discriminant in the same call.
        config = self._build(
            optimizer="ADAMW", optimizer_extra_overrides={"weight_decay": 0.01}
        )
        self.assertEqual(config["optimizer"], {"optimizer": "ADAMW", "weight_decay": 0.01})

    def test_optimizer_extra_overrides_alone_without_discriminant_is_legal(self):
        # OneTrainer's own partial-merge semantics (BaseConfig.from_dict())
        # accept a nested object missing the "optimizer" sub-key — it
        # simply merges onto TrainOptimizerConfig.default_values() (real
        # default ADAMW), so this is a legitimate way to tweak a
        # hyperparameter without explicitly re-selecting the default.
        config = self._build(optimizer_extra_overrides={"weight_decay": 0.01})
        self.assertEqual(config["optimizer"], {"weight_decay": 0.01})

    def test_optimizer_extra_overrides_rejects_local_optimizer_collision(self):
        # Mission 122 section 3.3: the local escape hatch may never
        # redefine the "optimizer" discriminant itself — every other
        # real OneTrainer optimizer hyperparameter stays legal there.
        with self.assertRaises(OneTrainerConfigError):
            self._build(optimizer="ADAMW", optimizer_extra_overrides={"optimizer": "SGD"})

    def test_optimizer_extra_overrides_default_adds_nothing(self):
        config_without = self._build()
        config_with_empty = self._build(optimizer_extra_overrides={})
        config_with_none = self._build(optimizer_extra_overrides=None)
        self.assertEqual(config_without, config_with_empty)
        self.assertEqual(config_without, config_with_none)

    def test_optimizer_structured_subkeys_enumerated_exactly(self):
        # Mission 122 section 3.3: centralized and tested explicitly —
        # a future change (e.g. promoting weight_decay to a typed field)
        # must add its key here in the same change, never after the
        # fact, exactly like _STRUCTURED_CONFIG_KEYS itself.
        self.assertEqual(_OPTIMIZER_STRUCTURED_SUBKEYS, frozenset({"optimizer"}))

    def test_extra_overrides_rejects_legacy_optimizer_root_with_actionable_message(self):
        # Mission 122 section 3.4: extra_overrides["optimizer"] was legal
        # before this mission (the key was not yet in
        # _STRUCTURED_CONFIG_KEYS) — a hand-edited project.json could
        # already carry it, correctly nested, and have it work. This
        # reproduces exactly that legacy case: rejected explicitly, with
        # a message naming the reserved root key and pointing at the new
        # location, never a silent migration.
        with self.assertRaisesRegex(
            OneTrainerConfigError, "extra_overrides\\['optimizer'\\]"
        ) as ctx:
            self._build(extra_overrides={"optimizer": {"optimizer": "ADAMW", "beta1": 0.5}})
        self.assertIn("optimizer_settings.extra_overrides", str(ctx.exception))

    def test_optimizer_and_global_extra_overrides_can_both_be_used_together(self):
        # The structured optimizer field and an unrelated global
        # extra_overrides key coexist without interference.
        config = self._build(optimizer="SGD", extra_overrides={"loss_weight_fn": "MIN_SNR_GAMMA"})
        self.assertEqual(config["optimizer"], {"optimizer": "SGD"})
        self.assertEqual(config["loss_weight_fn"], "MIN_SNR_GAMMA")

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

    # --- Mission 124: text_encoder_train/text_encoder_2_train/lora_layer_filter

    # H. Sentinel — no key written when not configured.

    def test_train_fields_omitted_when_not_configured(self):
        for architecture in ("SD15", "SDXL", "FLUX"):
            with self.subTest(architecture=architecture):
                config = self._build(architecture=architecture)
                for key in ("unet", "transformer", "text_encoder", "text_encoder_2", "vae"):
                    self.assertNotIn(key, config)

    def test_lora_layer_filter_omitted_when_not_configured(self):
        config = self._build()
        self.assertNotIn("layer_filter", config)
        self.assertNotIn("layer_filter_regex", config)

    # D/E/F. train fields translated into the real nested component shape,
    # per architecture.

    def test_text_encoder_train_translated_into_nested_component_shape(self):
        config = self._build(architecture="SD15", text_encoder_train=True)
        self.assertEqual(config["text_encoder"], {"train": True})

    def test_text_encoder_train_false_translated_explicitly(self):
        # False must be forwarded exactly — never confused with "not
        # configured" (None), which is a real, distinct Python value.
        config = self._build(architecture="SD15", text_encoder_train=False)
        self.assertEqual(config["text_encoder"], {"train": False})

    def test_text_encoder_2_train_translated_into_nested_component_shape(self):
        config = self._build(architecture="SDXL", text_encoder_2_train=False)
        self.assertEqual(config["text_encoder_2"], {"train": False})

    def test_flux_text_encoder_train_fields_independent(self):
        config = self._build(
            architecture="FLUX", text_encoder_train=False, text_encoder_2_train=True,
        )
        self.assertEqual(config["text_encoder"], {"train": False})
        self.assertEqual(config["text_encoder_2"], {"train": True})

    # G. Fusion — dtype and train for the same component must land in
    # ONE merged nested object, never two independent assignments to the
    # same config[component_key] silently discarding each other.

    def test_text_encoder_dtype_and_train_merge_into_one_object(self):
        config = self._build(
            architecture="SD15",
            text_encoder_weight_dtype="FLOAT_16",
            text_encoder_train=False,
        )
        self.assertEqual(config["text_encoder"], {"weight_dtype": "FLOAT_16", "train": False})

    def test_text_encoder_2_dtype_and_train_merge_into_one_object(self):
        config = self._build(
            architecture="SDXL",
            text_encoder_2_weight_dtype="FLOAT_32",
            text_encoder_2_train=True,
        )
        self.assertEqual(
            config["text_encoder_2"], {"weight_dtype": "FLOAT_32", "train": True}
        )

    def test_unet_dtype_alone_never_gains_a_train_key(self):
        # Non-regression: a component with only a dtype configured (no
        # corresponding train field exists for unet/transformer/vae)
        # must keep its exact pre-Mission-124 shape.
        config = self._build(architecture="SD15", unet_weight_dtype="FLOAT_16")
        self.assertEqual(config["unet"], {"weight_dtype": "FLOAT_16"})

    # I. Architecture validation — same algorithm/style as the dtype
    # fields, applied to _TRAIN_FIELDS_BY_ARCHITECTURE.

    def test_train_fields_by_architecture_enumerated_exactly(self):
        self.assertEqual(
            _TRAIN_FIELDS_BY_ARCHITECTURE,
            {
                "SD15": frozenset({"text_encoder_train"}),
                "SDXL": frozenset({"text_encoder_train", "text_encoder_2_train"}),
                "FLUX": frozenset({"text_encoder_train", "text_encoder_2_train"}),
            },
        )

    def test_train_field_to_component_key_enumerated_exactly(self):
        self.assertEqual(
            _TRAIN_FIELD_TO_COMPONENT_KEY,
            {"text_encoder_train": "text_encoder", "text_encoder_2_train": "text_encoder_2"},
        )

    def test_sd15_rejects_text_encoder_2_train(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_2_train=True)

    def test_sd15_rejects_text_encoder_2_train_even_when_false(self):
        # False is still a real, explicit configuration — SD1.5 has no
        # text_encoder_2 component to apply it to, regardless of value.
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_2_train=False)

    def test_incompatible_train_field_error_names_the_offending_field(self):
        with self.assertRaisesRegex(OneTrainerConfigError, "text_encoder_2_train"):
            self._build(architecture="SD15", text_encoder_2_train=True)

    def test_sd15_accepts_text_encoder_train(self):
        # SD1.5 has exactly one Text Encoder — text_encoder_train is
        # valid for it, unlike text_encoder_2_train.
        config = self._build(architecture="SD15", text_encoder_train=True)
        self.assertEqual(config["text_encoder"], {"train": True})

    # D/E/F. lora_layer_filter translated per architecture — confirmed
    # directly against the real OneTrainer LAYER_PRESETS dicts (never
    # layer_filter_preset itself, which has no effect in the headless
    # path this project uses).

    def test_lora_layer_filter_translation_table_enumerated_exactly(self):
        self.assertEqual(
            _LORA_LAYER_FILTER_TRANSLATION,
            {
                "ATTN_MLP": {
                    "SD15": {"layer_filter": "attentions", "layer_filter_regex": False},
                    "SDXL": {"layer_filter": "attentions", "layer_filter_regex": False},
                    "FLUX": {"layer_filter": "attn,ff.net", "layer_filter_regex": False},
                },
            },
        )

    def test_lora_layer_filter_attn_mlp_sd15(self):
        config = self._build(architecture="SD15", lora_layer_filter="ATTN_MLP")
        self.assertEqual(config["layer_filter"], "attentions")
        self.assertIs(config["layer_filter_regex"], False)

    def test_lora_layer_filter_attn_mlp_sdxl(self):
        config = self._build(architecture="SDXL", lora_layer_filter="ATTN_MLP")
        self.assertEqual(config["layer_filter"], "attentions")
        self.assertIs(config["layer_filter_regex"], False)

    def test_lora_layer_filter_attn_mlp_flux(self):
        # F: FLUX's own official LoRA preset does not configure any
        # layer filter at all (transformer trained in full) — this
        # value is a capability this project offers, never a
        # reproduction of an official OneTrainer recommendation for
        # FLUX. This test locks in the translated value; the "not an
        # official FLUX recommendation" fact is documented in
        # build_training_config()'s own docstring and MISSION_124.md
        # section 2.F, never silently implied by this test alone.
        config = self._build(architecture="FLUX", lora_layer_filter="ATTN_MLP")
        self.assertEqual(config["layer_filter"], "attn,ff.net")
        self.assertIs(config["layer_filter_regex"], False)

    def test_lora_layer_filter_never_writes_layer_filter_preset(self):
        # Section 2.E: layer_filter_preset has zero effect in the
        # headless path Toolkit uses — it must never be written at all.
        config = self._build(architecture="SDXL", lora_layer_filter="ATTN_MLP")
        self.assertNotIn("layer_filter_preset", config)

    def test_unsupported_lora_layer_filter_value_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(lora_layer_filter="BOGUS")

    # K. extra_overrides collision — layer_filter/layer_filter_regex are
    # now structured/protected, exactly like the Mission 121/122 keys.

    def test_extra_overrides_rejects_layer_filter_and_layer_filter_regex(self):
        for key in ("layer_filter", "layer_filter_regex"):
            with self.subTest(key=key):
                self.assertIn(key, _STRUCTURED_CONFIG_KEYS)
                with self.assertRaises(OneTrainerConfigError):
                    self._build(extra_overrides={key: "attentions"})

    def test_extra_overrides_rejects_text_encoder_train_via_component_key(self):
        # text_encoder/text_encoder_2 were already reserved by Mission
        # 121 (section 3.5) — confirming here that this reservation
        # already fully blocks any attempt to reach the new `train`
        # sub-field through extra_overrides, exactly as designed: no
        # extra_overrides change was needed for this mission's own new
        # fields, only for lora_layer_filter's new keys above.
        with self.assertRaises(OneTrainerConfigError):
            self._build(extra_overrides={"text_encoder": {"train": False}})

    # --- Mission 126: NFLOAT_4 / timestep_distribution /
    # dynamic_timestep_shifting / timestep_shift

    # J. NFLOAT_4 is a plain dtype value — no value-level validation
    # exists in this module (only field-name-by-architecture validation
    # does), so it must translate exactly like any of the 4 pre-existing
    # values, on every component, with zero new restriction.

    def test_nfloat_4_translated_on_every_dtype_component(self):
        cases = (
            ("SD15", "unet_weight_dtype", "unet"),
            ("SD15", "text_encoder_weight_dtype", "text_encoder"),
            ("SD15", "vae_weight_dtype", "vae"),
            ("SDXL", "unet_weight_dtype", "unet"),
            ("SDXL", "text_encoder_weight_dtype", "text_encoder"),
            ("SDXL", "text_encoder_2_weight_dtype", "text_encoder_2"),
            ("SDXL", "vae_weight_dtype", "vae"),
            ("FLUX", "transformer_weight_dtype", "transformer"),
            ("FLUX", "text_encoder_weight_dtype", "text_encoder"),
            ("FLUX", "text_encoder_2_weight_dtype", "text_encoder_2"),
            ("FLUX", "vae_weight_dtype", "vae"),
        )
        for architecture, field_name, component_key in cases:
            with self.subTest(architecture=architecture, field_name=field_name):
                config = self._build(architecture=architecture, **{field_name: "NFLOAT_4"})
                self.assertEqual(config[component_key], {"weight_dtype": "NFLOAT_4"})

    def test_nfloat_4_never_rejected_for_any_architecture(self):
        # Non-regression: this module never turns the FLUX official
        # preset's own choice (transformer/text_encoder_2 only) into a
        # Toolkit-side validation rule — MISSION_126.md section 3.1.
        for architecture, field_name in (
            ("SD15", "unet_weight_dtype"),
            ("SDXL", "unet_weight_dtype"),
            ("FLUX", "vae_weight_dtype"),
        ):
            with self.subTest(architecture=architecture, field_name=field_name):
                self._build(architecture=architecture, **{field_name: "NFLOAT_4"})

    def test_existing_dtype_values_unaffected_by_nfloat_4_addition(self):
        # Non-regression on the 4 pre-existing dtype values.
        for value in ("FLOAT_16", "FLOAT_32", "BFLOAT_16", "TFLOAT_32"):
            with self.subTest(value=value):
                config = self._build(architecture="SD15", unet_weight_dtype=value)
                self.assertEqual(config["unet"], {"weight_dtype": value})

    # E. Sentinel — no key written when not configured, for a FLUX
    # config that otherwise configures nothing else flow-matching-related.

    def test_flow_matching_fields_omitted_when_not_configured(self):
        config = self._build(architecture="FLUX")
        for key in ("timestep_distribution", "dynamic_timestep_shifting", "timestep_shift"):
            self.assertNotIn(key, config)

    # E/F. Flat top-level translation, each field independent.

    def test_timestep_distribution_forwarded_when_configured(self):
        config = self._build(architecture="FLUX", timestep_distribution="LOGIT_NORMAL")
        self.assertEqual(config["timestep_distribution"], "LOGIT_NORMAL")

    def test_timestep_distribution_uniform_forwarded_when_configured(self):
        config = self._build(architecture="FLUX", timestep_distribution="UNIFORM")
        self.assertEqual(config["timestep_distribution"], "UNIFORM")

    def test_dynamic_timestep_shifting_true_forwarded(self):
        config = self._build(architecture="FLUX", dynamic_timestep_shifting=True)
        self.assertIs(config["dynamic_timestep_shifting"], True)

    def test_dynamic_timestep_shifting_false_forwarded_explicitly(self):
        # False must be forwarded exactly — never confused with "not
        # configured" (None), which is a real, distinct Python value —
        # same discipline as text_encoder_train's own False test.
        config = self._build(architecture="FLUX", dynamic_timestep_shifting=False)
        self.assertIs(config["dynamic_timestep_shifting"], False)

    # F. timestep_shift — 1.0 explicit must be written, distinct from
    # the absent-key case above (both are "falsy-looking" in a naive
    # `if timestep_shift:` check, which is exactly why the real
    # translation uses `is not None`).

    def test_timestep_shift_one_point_zero_explicit_is_written(self):
        config = self._build(architecture="FLUX", timestep_shift=1.0)
        self.assertIn("timestep_shift", config)
        self.assertEqual(config["timestep_shift"], 1.0)

    def test_timestep_shift_other_float_is_written(self):
        config = self._build(architecture="FLUX", timestep_shift=1.15)
        self.assertEqual(config["timestep_shift"], 1.15)

    # G. dynamic_timestep_shifting=True + timestep_shift configured
    # together — both keys must be written independently, never one
    # suppressing the other. OneTrainer itself ignores timestep_shift at
    # runtime in this case, but that is an engine execution fact, never
    # reproduced here as a Toolkit-side field suppression.

    def test_dynamic_true_and_timestep_shift_both_written_independently(self):
        config = self._build(
            architecture="FLUX", dynamic_timestep_shifting=True, timestep_shift=1.5,
        )
        self.assertIs(config["dynamic_timestep_shifting"], True)
        self.assertEqual(config["timestep_shift"], 1.5)

    # H. Architecture validation — same algorithm/style as the dtype/
    # train fields, applied to _FLOW_MATCHING_FIELDS_BY_ARCHITECTURE.

    def test_flow_matching_fields_by_architecture_enumerated_exactly(self):
        self.assertEqual(
            _FLOW_MATCHING_FIELDS_BY_ARCHITECTURE,
            {
                "SD15": frozenset(),
                "SDXL": frozenset(),
                "FLUX": frozenset(
                    {"timestep_distribution", "dynamic_timestep_shifting", "timestep_shift"}
                ),
            },
        )

    def test_sd15_rejects_timestep_distribution(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", timestep_distribution="LOGIT_NORMAL")

    def test_sdxl_rejects_timestep_distribution(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SDXL", timestep_distribution="LOGIT_NORMAL")

    def test_sd15_rejects_dynamic_timestep_shifting_even_when_false(self):
        # False is still a real, explicit configuration — SD1.5 has no
        # flow-matching path to apply it to, regardless of value.
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", dynamic_timestep_shifting=False)

    def test_sdxl_rejects_timestep_shift(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SDXL", timestep_shift=1.0)

    def test_incompatible_flow_matching_field_error_names_the_offending_field(self):
        with self.assertRaisesRegex(OneTrainerConfigError, "timestep_distribution"):
            self._build(architecture="SD15", timestep_distribution="LOGIT_NORMAL")

    def test_flux_accepts_every_flow_matching_field_together(self):
        config = self._build(
            architecture="FLUX",
            timestep_distribution="LOGIT_NORMAL",
            dynamic_timestep_shifting=True,
            timestep_shift=1.0,
        )
        self.assertEqual(config["timestep_distribution"], "LOGIT_NORMAL")
        self.assertIs(config["dynamic_timestep_shifting"], True)
        self.assertEqual(config["timestep_shift"], 1.0)

    # I. extra_overrides collision — the three new flat keys are now
    # structured/protected, exactly like every prior mission's own new
    # keys.

    def test_extra_overrides_rejects_the_three_flow_matching_keys(self):
        for key, value in (
            ("timestep_distribution", "LOGIT_NORMAL"),
            ("dynamic_timestep_shifting", True),
            ("timestep_shift", 1.0),
        ):
            with self.subTest(key=key):
                self.assertIn(key, _STRUCTURED_CONFIG_KEYS)
                with self.assertRaises(OneTrainerConfigError):
                    self._build(architecture="FLUX", extra_overrides={key: value})

    # M. Validation headless FLUX — a representative configuration
    # matching the FLUX official LoRA preset's own choices on the axes
    # this mission covers, checked as a complete object, never just an
    # isolated string.

    def test_headless_flux_representative_configuration(self):
        config = self._build(
            architecture="FLUX",
            base_model_source="black-forest-labs/FLUX.1-dev",
            train_dtype="BFLOAT_16",
            transformer_weight_dtype="NFLOAT_4",
            text_encoder_weight_dtype="BFLOAT_16",
            text_encoder_2_weight_dtype="NFLOAT_4",
            vae_weight_dtype="FLOAT_32",
            timestep_distribution="LOGIT_NORMAL",
            dynamic_timestep_shifting=True,
        )
        self.assertEqual(config["train_dtype"], "BFLOAT_16")
        self.assertEqual(config["transformer"], {"weight_dtype": "NFLOAT_4"})
        self.assertEqual(config["text_encoder"], {"weight_dtype": "BFLOAT_16"})
        self.assertEqual(config["text_encoder_2"], {"weight_dtype": "NFLOAT_4"})
        self.assertEqual(config["vae"], {"weight_dtype": "FLOAT_32"})
        self.assertEqual(config["timestep_distribution"], "LOGIT_NORMAL")
        self.assertIs(config["dynamic_timestep_shifting"], True)
        self.assertNotIn("timestep_shift", config)
        self.assertNotIn("unet", config)

    def test_headless_flux_representative_configuration_with_explicit_timestep_shift(self):
        # Variant: timestep_shift explicitly configured alongside
        # dynamic_timestep_shifting=True — both must be present, exactly
        # the same independence already locked in by test G above,
        # re-verified here against the full representative object.
        config = self._build(
            architecture="FLUX",
            base_model_source="black-forest-labs/FLUX.1-dev",
            train_dtype="BFLOAT_16",
            transformer_weight_dtype="NFLOAT_4",
            text_encoder_weight_dtype="BFLOAT_16",
            text_encoder_2_weight_dtype="NFLOAT_4",
            vae_weight_dtype="FLOAT_32",
            timestep_distribution="LOGIT_NORMAL",
            dynamic_timestep_shifting=True,
            timestep_shift=1.0,
        )
        self.assertEqual(config["timestep_distribution"], "LOGIT_NORMAL")
        self.assertIs(config["dynamic_timestep_shifting"], True)
        self.assertEqual(config["timestep_shift"], 1.0)

    # --- Mission 127: gradient_checkpointing_mode -----------------------
    # Flat top-level key, generic to every architecture (never a
    # per-architecture table like the dtype/train/flow-matching fields) —
    # and the first field in this module whose *value* (not just its
    # field name/architecture) is validated (MISSION_127.md section 8).

    # F. "" (not configured) never adds the key.

    def test_gradient_checkpointing_mode_empty_omits_the_key(self):
        for architecture in ("SD15", "SDXL", "FLUX"):
            with self.subTest(architecture=architecture):
                config = self._build(architecture=architecture, gradient_checkpointing_mode="")
                self.assertNotIn("gradient_checkpointing", config)

    # G/H/I. Each real value is forwarded verbatim.

    def test_gradient_checkpointing_mode_off_forwarded(self):
        config = self._build(architecture="SD15", gradient_checkpointing_mode="OFF")
        self.assertEqual(config["gradient_checkpointing"], "OFF")

    def test_gradient_checkpointing_mode_on_forwarded(self):
        config = self._build(architecture="SDXL", gradient_checkpointing_mode="ON")
        self.assertEqual(config["gradient_checkpointing"], "ON")

    def test_gradient_checkpointing_mode_cpu_offloaded_forwarded(self):
        config = self._build(architecture="FLUX", gradient_checkpointing_mode="CPU_OFFLOADED")
        self.assertEqual(config["gradient_checkpointing"], "CPU_OFFLOADED")

    def test_gradient_checkpointing_values_enumerated_exactly(self):
        self.assertEqual(
            _GRADIENT_CHECKPOINTING_VALUES,
            frozenset({"OFF", "ON", "CPU_OFFLOADED"}),
        )

    # J. Any other non-empty value is a hard error — no case-correction,
    # no silent fallback.

    def test_gradient_checkpointing_mode_unknown_value_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", gradient_checkpointing_mode="MAYBE")

    def test_gradient_checkpointing_mode_lowercase_is_not_silently_corrected(self):
        # No case-correction: OneTrainer's own enum values are uppercase
        # only — a lowercase variant is a real, distinct, rejected value,
        # never silently uppercased on the caller's behalf.
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", gradient_checkpointing_mode="off")

    def test_gradient_checkpointing_mode_unknown_value_error_names_the_field(self):
        with self.assertRaisesRegex(OneTrainerConfigError, "gradient_checkpointing_mode"):
            self._build(architecture="SD15", gradient_checkpointing_mode="MAYBE")

    # K. extra_overrides collision — the new flat key is now structured/
    # protected, exactly like every prior mission's own new keys.

    def test_extra_overrides_rejects_gradient_checkpointing(self):
        self.assertIn("gradient_checkpointing", _STRUCTURED_CONFIG_KEYS)
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", extra_overrides={"gradient_checkpointing": "OFF"})

    # Generic to every architecture — never rejected, unlike the dtype/
    # train/flow-matching fields, which are each restricted to a subset.

    def test_gradient_checkpointing_mode_accepted_on_every_architecture(self):
        for architecture in ("SD15", "SDXL", "FLUX"):
            with self.subTest(architecture=architecture):
                config = self._build(
                    architecture=architecture, gradient_checkpointing_mode="CPU_OFFLOADED"
                )
                self.assertEqual(config["gradient_checkpointing"], "CPU_OFFLOADED")

    # Q. Cohabitation — gradient_checkpointing must coexist in the
    # produced JSON without ever overwriting, or being overwritten by,
    # train_dtype/component weight dtypes/text_encoder.train/layer_filter/
    # the Mission 126 flow-matching fields.

    def test_gradient_checkpointing_cohabits_with_every_other_structured_field(self):
        config = self._build(
            architecture="FLUX",
            base_model_source="black-forest-labs/FLUX.1-dev",
            train_dtype="BFLOAT_16",
            gradient_checkpointing_mode="CPU_OFFLOADED",
            transformer_weight_dtype="NFLOAT_4",
            text_encoder_weight_dtype="BFLOAT_16",
            text_encoder_2_weight_dtype="NFLOAT_4",
            vae_weight_dtype="FLOAT_32",
            text_encoder_train=False,
            lora_layer_filter="ATTN_MLP",
            timestep_distribution="LOGIT_NORMAL",
            dynamic_timestep_shifting=True,
        )
        self.assertEqual(config["train_dtype"], "BFLOAT_16")
        self.assertEqual(config["gradient_checkpointing"], "CPU_OFFLOADED")
        self.assertEqual(config["transformer"], {"weight_dtype": "NFLOAT_4"})
        self.assertEqual(
            config["text_encoder"], {"weight_dtype": "BFLOAT_16", "train": False}
        )
        self.assertEqual(config["text_encoder_2"], {"weight_dtype": "NFLOAT_4"})
        self.assertEqual(config["vae"], {"weight_dtype": "FLOAT_32"})
        self.assertEqual(config["layer_filter"], "attn,ff.net")
        self.assertEqual(config["timestep_distribution"], "LOGIT_NORMAL")
        self.assertIs(config["dynamic_timestep_shifting"], True)

    # --- Mission 128: text_encoder_stop_training_mode/_after ------------
    # Merges into the same nested component object as weight_dtype/train
    # (Mission 124's accumulator) — never a flat top-level key like
    # gradient_checkpointing above.

    # I. "" (not configured) + after=None never adds either key.

    def test_stop_training_mode_empty_omits_keys(self):
        config = self._build(architecture="SD15")
        self.assertNotIn("text_encoder", config)

    # J. "NEVER" writes the unit alone — stop_training_after is never
    # written alongside it, even though OneTrainer's own default (30)
    # would otherwise still be lurking under the hood.

    def test_stop_training_never_mode_writes_unit_only(self):
        config = self._build(architecture="SD15", text_encoder_stop_training_mode="NEVER")
        self.assertEqual(config["text_encoder"], {"stop_training_after_unit": "NEVER"})

    # K/L/M/N. EPOCH/STEP forward both keys verbatim.

    def test_stop_training_epoch_after_1_forwarded(self):
        config = self._build(
            architecture="SD15",
            text_encoder_stop_training_mode="EPOCH",
            text_encoder_stop_training_after=1,
        )
        self.assertEqual(
            config["text_encoder"],
            {"stop_training_after": 1, "stop_training_after_unit": "EPOCH"},
        )

    def test_stop_training_epoch_after_n_forwarded(self):
        config = self._build(
            architecture="SD15",
            text_encoder_stop_training_mode="EPOCH",
            text_encoder_stop_training_after=30,
        )
        self.assertEqual(
            config["text_encoder"],
            {"stop_training_after": 30, "stop_training_after_unit": "EPOCH"},
        )

    def test_stop_training_step_after_1_forwarded(self):
        config = self._build(
            architecture="SD15",
            text_encoder_stop_training_mode="STEP",
            text_encoder_stop_training_after=1,
        )
        self.assertEqual(
            config["text_encoder"],
            {"stop_training_after": 1, "stop_training_after_unit": "STEP"},
        )

    def test_stop_training_step_after_n_forwarded(self):
        config = self._build(
            architecture="SD15",
            text_encoder_stop_training_mode="STEP",
            text_encoder_stop_training_after=500,
        )
        self.assertEqual(
            config["text_encoder"],
            {"stop_training_after": 500, "stop_training_after_unit": "STEP"},
        )

    def test_stop_training_mode_values_enumerated_exactly(self):
        self.assertEqual(_STOP_TRAINING_MODE_VALUES, frozenset({"NEVER", "EPOCH", "STEP"}))

    # O. Any other non-empty mode is a hard error — ALWAYS/SECOND/
    # MINUTE/HOUR are real OneTrainer TimeUnit values this mission never
    # exposes (MISSION_128.md section 4/5).

    def test_stop_training_invalid_mode_raises(self):
        with self.assertRaisesRegex(OneTrainerConfigError, "text_encoder_stop_training_mode"):
            self._build(architecture="SD15", text_encoder_stop_training_mode="ALWAYS")

    def test_stop_training_time_unit_mode_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_stop_training_mode="SECOND")

    # P/Q. EPOCH/STEP without a paired after is a hard error — never an
    # implicit "unlimited".

    def test_stop_training_epoch_without_after_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_stop_training_mode="EPOCH")

    def test_stop_training_step_without_after_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_stop_training_mode="STEP")

    # R/S. 0 is a real, immediate-freeze engine value under EPOCH/STEP —
    # never accepted from Toolkit's own UI/API as "unlimited".

    def test_stop_training_epoch_after_zero_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_stop_training_mode="EPOCH",
                text_encoder_stop_training_after=0,
            )

    def test_stop_training_step_after_zero_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_stop_training_mode="STEP",
                text_encoder_stop_training_after=0,
            )

    # T. A negative value is never a legitimate configuration.

    def test_stop_training_after_negative_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_stop_training_mode="EPOCH",
                text_encoder_stop_training_after=-1,
            )

    # A/B. bool is a Python subclass of int — must never pass as a real
    # stop_training_after value (MISSION_128.md section 7).

    def test_stop_training_after_true_rejected(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_stop_training_mode="EPOCH",
                text_encoder_stop_training_after=True,
            )

    def test_stop_training_after_false_rejected(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_stop_training_mode="EPOCH",
                text_encoder_stop_training_after=False,
            )

    # U/V. "" or "NEVER" with a configured after is a hard error — an
    # unused numeric value is never silently accepted.

    def test_stop_training_empty_mode_with_after_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(architecture="SD15", text_encoder_stop_training_after=5)

    def test_stop_training_never_mode_with_after_raises(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_stop_training_mode="NEVER",
                text_encoder_stop_training_after=5,
            )

    # W/X/Y. Cohabitation in the same nested component object — never a
    # fourth independent assignment discarding weight_dtype/train.

    def test_stop_training_cohabits_with_train(self):
        config = self._build(
            architecture="SD15",
            text_encoder_train=True,
            text_encoder_stop_training_mode="EPOCH",
            text_encoder_stop_training_after=10,
        )
        self.assertEqual(
            config["text_encoder"],
            {"train": True, "stop_training_after": 10, "stop_training_after_unit": "EPOCH"},
        )

    def test_stop_training_cohabits_with_weight_dtype(self):
        config = self._build(
            architecture="SD15",
            text_encoder_weight_dtype="FLOAT_16",
            text_encoder_stop_training_mode="NEVER",
        )
        self.assertEqual(
            config["text_encoder"],
            {"weight_dtype": "FLOAT_16", "stop_training_after_unit": "NEVER"},
        )

    def test_stop_training_cohabits_with_train_and_dtype_in_same_nested_object(self):
        config = self._build(
            architecture="SD15",
            text_encoder_weight_dtype="FLOAT_16",
            text_encoder_train=True,
            text_encoder_stop_training_mode="STEP",
            text_encoder_stop_training_after=10,
        )
        self.assertEqual(
            config["text_encoder"],
            {
                "weight_dtype": "FLOAT_16",
                "train": True,
                "stop_training_after": 10,
                "stop_training_after_unit": "STEP",
            },
        )

    # Z/AA. TE2 forwarded normally for SDXL/FLUX.

    def test_stop_training_te2_on_sdxl(self):
        config = self._build(
            architecture="SDXL",
            text_encoder_2_stop_training_mode="EPOCH",
            text_encoder_2_stop_training_after=7,
        )
        self.assertEqual(
            config["text_encoder_2"],
            {"stop_training_after": 7, "stop_training_after_unit": "EPOCH"},
        )

    def test_stop_training_te2_on_flux(self):
        config = self._build(
            architecture="FLUX",
            base_model_source="black-forest-labs/FLUX.1-dev",
            text_encoder_2_stop_training_mode="NEVER",
        )
        self.assertEqual(config["text_encoder_2"], {"stop_training_after_unit": "NEVER"})

    # AB. TE2 has no real component on SD15 — deliberately silently
    # excluded from the built config, never raised (MISSION_128.md
    # section 10: this mission's own UI persists a Text Encoder 2
    # duration configured under SDXL/FLUX even while the Training is
    # temporarily on SD1.5, so building a config from that Domain state
    # must never fail just because the now-inapplicable value is still
    # there — deliberately UNLIKE the dtype/train fields, which raise).

    def test_stop_training_te2_silently_omitted_on_sd15(self):
        config = self._build(
            architecture="SD15",
            text_encoder_2_stop_training_mode="EPOCH",
            text_encoder_2_stop_training_after=5,
        )
        self.assertNotIn("text_encoder_2", config)

    def test_stop_training_te2_invalid_value_still_raises_even_on_sd15(self):
        # Value/coherence validation is never skipped just because the
        # field also happens to be architecture-inapplicable — only the
        # architecture-gated *emission* is silently skipped, never the
        # validation of the value itself.
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                text_encoder_2_stop_training_mode="EPOCH",
                text_encoder_2_stop_training_after=0,
            )

    def test_stop_training_fields_by_architecture_enumerated_exactly(self):
        self.assertEqual(
            _STOP_TRAINING_FIELDS_BY_ARCHITECTURE,
            {
                "SD15": frozenset({"text_encoder_stop_training_mode"}),
                "SDXL": frozenset(
                    {"text_encoder_stop_training_mode", "text_encoder_2_stop_training_mode"}
                ),
                "FLUX": frozenset(
                    {"text_encoder_stop_training_mode", "text_encoder_2_stop_training_mode"}
                ),
            },
        )

    def test_stop_training_field_to_component_key_enumerated_exactly(self):
        self.assertEqual(
            _STOP_TRAINING_FIELD_TO_COMPONENT_KEY,
            {
                "text_encoder_stop_training_mode": "text_encoder",
                "text_encoder_2_stop_training_mode": "text_encoder_2",
            },
        )

    # extra_overrides protection: no new top-level key was introduced by
    # this mission — "text_encoder"/"text_encoder_2" already reserve the
    # whole nested object since Mission 121, confirmed still blocking a
    # nested stop_training_after injection attempt.

    def test_extra_overrides_still_rejects_nested_text_encoder_stop_training_injection(self):
        with self.assertRaises(OneTrainerConfigError):
            self._build(
                architecture="SD15",
                extra_overrides={"text_encoder": {"stop_training_after": 5}},
            )


if __name__ == "__main__":
    unittest.main()
