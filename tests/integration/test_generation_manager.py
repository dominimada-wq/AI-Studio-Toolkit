"""
Coverage for src/managers/generation_manager.py — GenerationManager's
delegation to ComfyUIEngine, its busy-flag guard, and its error
normalization. ComfyUIEngine is entirely mocked: no network access, no
ComfyUI instance. GenerationManager is also verified Qt-free (Mission
013 architecture requirement — it must stay testable without a
QApplication and never become a QObject unless a real architectural
necessity demonstrates otherwise).
"""

import inspect
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.engines.comfyui_engine import ComfyUIEngineError
from src.engines.forge_engine import ForgeEngine, ForgeEngineError
from src.managers.generation_manager import (
    REFERENCE_ROLE_POSE_COMPOSITION,
    GenerationError,
    GenerationManager,
    Reference,
)


class GenerationManagerTest(unittest.TestCase):

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_successful_generation_returns_path_and_forwards_arguments(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        path = self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(path, "/tmp/out/image.png")
        self.engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image=None,
            lora_name="",
            lora_strength=1.0,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
        )

    def test_empty_prompt_is_rejected_without_calling_the_engine(self):
        with self.assertRaises(GenerationError):
            self.manager.generate("", "/tmp/out")

        with self.assertRaises(GenerationError):
            self.manager.generate("   ", "/tmp/out")

        self.engine.generate_image.assert_not_called()

    def test_comfyui_engine_error_is_normalized_into_generation_error(self):
        self.engine.generate_image.side_effect = ComfyUIEngineError("server unreachable")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out")

    def test_local_filesystem_oserror_is_normalized_into_generation_error(self):
        # download_output() can raise a plain OSError (Mission 012's
        # own documented behavior for local filesystem failures, never
        # wrapped in ComfyUIEngineError) — GenerationManager must
        # normalize this too, not just ComfyUIEngineError.
        self.engine.generate_image.side_effect = OSError("disk full")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out")

    def test_busy_flag_is_true_only_during_generation_and_resets_after_success(self):
        observed_busy_during_call = []

        def fake_generate_image(
            prompt_text, output_directory, checkpoint_name, reference_image=None,
            lora_name="", lora_strength=1.0, **kwargs,
        ):
            observed_busy_during_call.append(self.manager.busy)
            return "/tmp/out/image.png"

        self.engine.generate_image.side_effect = fake_generate_image

        self.assertFalse(self.manager.busy)
        self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(observed_busy_during_call, [True])
        self.assertFalse(self.manager.busy)

    def test_busy_flag_resets_after_error(self):
        self.engine.generate_image.side_effect = ComfyUIEngineError("boom")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out")

        self.assertFalse(self.manager.busy)

    def test_second_generation_refused_while_one_is_in_progress(self):
        # A side_effect that re-enters generate() while _busy is
        # already True, proving the guard organically rather than
        # poking a private attribute directly.
        def fake_generate_image(
            prompt_text, output_directory, checkpoint_name, reference_image=None,
            lora_name="", lora_strength=1.0, **kwargs,
        ):
            with self.assertRaises(GenerationError):
                self.manager.generate("a second fox", "/tmp/out")
            return "/tmp/out/image.png"

        self.engine.generate_image.side_effect = fake_generate_image

        path = self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(path, "/tmp/out/image.png")
        self.engine.generate_image.assert_called_once()

    def test_generate_can_be_called_again_after_a_previous_generation_completed(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("first", "/tmp/out")
        self.manager.generate("second", "/tmp/out")

        self.assertEqual(self.engine.generate_image.call_count, 2)

    def test_module_does_not_import_qt(self):
        source = Path(inspect.getfile(GenerationManager)).read_text(encoding="utf-8")
        lowered = [line.strip().lower() for line in source.splitlines()]
        offending = [
            line for line in lowered
            if (line.startswith("import ") or line.startswith("from ")) and "qt" in line
        ]
        self.assertEqual(offending, [])

    def test_generation_manager_is_not_a_qobject(self):
        # Guards Mission 013's explicit constraint: GenerationManager
        # must not become a QObject unless a real necessity is
        # demonstrated and reported.
        from PySide6.QtCore import QObject

        self.assertFalse(issubclass(GenerationManager, QObject))


class GenerationManagerReferenceImagesTest(unittest.TestCase):
    """
    Mission 022/023: generate()'s optional reference_images parameter
    stays a 0..N list[str] at this boundary — Mission 023 only narrows
    how many of them *this* workflow can actually use (at most one),
    it does not retract the collection-based architecture. With
    exactly one reference, ComfyUIEngine.upload_image() (Mission 021)
    is called once and its result forwarded, unexamined, to
    generate_image()'s reference_image parameter (Mission 023) — never
    inspected here. None/empty must produce byte-for-byte the same
    behavior as before these parameters existed: no upload_image()
    call at all. More than one reference is rejected before any upload
    is attempted (see GenerationManagerMultipleReferencesTest below).
    """

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_generate_without_reference_images_argument_never_calls_upload(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        path = self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(path, "/tmp/out/image.png")
        self.engine.upload_image.assert_not_called()

    def test_generate_with_none_reference_images_never_calls_upload(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out", reference_images=None)

        self.engine.upload_image.assert_not_called()

    def test_generate_with_empty_reference_images_never_calls_upload(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out", reference_images=[])

        self.engine.upload_image.assert_not_called()

    def test_generate_with_one_reference_forwards_upload_result_to_generate_image_untouched(self):
        # Mission 023's actual boundary requirement: GenerationManager
        # never inspects the dict upload_image() returns — it just
        # hands the exact same object to generate_image()'s
        # reference_image parameter.
        call_order = []
        upload_result = {"name": "ref.png", "subfolder": "", "type": "input"}
        self.engine.upload_image.side_effect = (
            lambda path: call_order.append(("upload", path)) or upload_result
        )
        self.engine.generate_image.side_effect = (
            lambda *args, **kwargs: call_order.append(("generate",)) or "/tmp/out/image.png"
        )

        path = self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/ref.png"])

        self.assertEqual(path, "/tmp/out/image.png")
        self.engine.upload_image.assert_called_once_with("/tmp/ref.png")
        self.engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image=upload_result,
            lora_name="",
            lora_strength=1.0,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
        )
        self.assertEqual(call_order, [("upload", "/tmp/ref.png"), ("generate",)])

    def test_generate_stops_and_never_calls_generate_image_when_upload_fails(self):
        self.engine.upload_image.side_effect = ComfyUIEngineError("server unreachable")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/ref.png"])

        self.engine.generate_image.assert_not_called()

    def test_upload_local_filesystem_error_is_normalized_into_generation_error(self):
        # Same normalization download_output()'s own OSError already
        # receives — a reference file deleted after selection but
        # before Generate must not crash or bypass GenerationError.
        self.engine.upload_image.side_effect = FileNotFoundError("missing")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/ref.png"])

        self.engine.generate_image.assert_not_called()

    def test_busy_flag_resets_after_an_upload_failure(self):
        self.engine.upload_image.side_effect = ComfyUIEngineError("boom")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/ref.png"])

        self.assertFalse(self.manager.busy)

    def test_reference_images_parameter_is_still_a_0_to_n_list_based_collection(self):
        # Mission 023 narrows how many references *this* workflow can
        # use, not the shape of the parameter itself — it must remain
        # a plain list[str], never collapse back into a scalar
        # reference_image/reference_image_path at this boundary.
        signature = inspect.signature(GenerationManager.generate)
        self.assertIn("reference_images", signature.parameters)
        self.assertIsNone(signature.parameters["reference_images"].default)
        self.assertNotIn("reference_image_path", signature.parameters)


class GenerationManagerMultipleReferencesTest(unittest.TestCase):
    """
    Mission 023: this img2img workflow supports at most one reference
    image — more than one is rejected explicitly and immediately,
    never silently reduced to reference_images[0]. This is a limit of
    this particular workflow, not a retraction of the 0..N
    architecture (see test_reference_images_parameter_is_still_a_0_to_n_
    list_based_collection above and MISSION_023.md section 6): a future
    workflow able to use several references would lift this specific
    check without changing reference_images' shape anywhere else.
    """

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_generate_with_two_references_raises_before_any_upload(self):
        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/a.png", "/tmp/b.png"])

        self.engine.upload_image.assert_not_called()
        self.engine.generate_image.assert_not_called()

    def test_generate_with_three_references_also_raises_before_any_upload(self):
        # Confirms the guard rejects "more than one", not a
        # special-cased "exactly two".
        with self.assertRaises(GenerationError):
            self.manager.generate(
                "a fox", "/tmp/out", reference_images=["/tmp/a.png", "/tmp/b.png", "/tmp/c.png"]
            )

        self.engine.upload_image.assert_not_called()
        self.engine.generate_image.assert_not_called()

    def test_generate_with_two_references_does_not_set_busy(self):
        # The >1 check happens before busy=True, alongside the existing
        # empty-prompt guard — a rejected call must never leave the
        # manager appearing to be mid-generation.
        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/a.png", "/tmp/b.png"])

        self.assertFalse(self.manager.busy)

    def test_generate_with_two_references_does_not_block_a_subsequent_valid_call(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/a.png", "/tmp/b.png"])

        path = self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(path, "/tmp/out/image.png")


class GenerationManagerTypedReferenceTest(unittest.TestCase):
    """
    Mission 056: reference_images now accepts either a plain str
    (legacy local file path, normalized in-memory to
    role=REFERENCE_ROLE_POSE_COMPOSITION) or an explicit
    Reference(path, role). The generation capacity actually delivered
    stays 0..1 *actionable* reference — the collection itself can hold
    N typed references, but only a single REFERENCE_ROLE_POSE_COMPOSITION
    reference is ever actionable. Any other role is rejected before any
    upload; more than one reference (regardless of role) is rejected
    before any upload too — never a silent fallback, never an implicit
    "take the first one".
    """

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_explicit_pose_composition_reference_matches_legacy_string_behavior(self):
        upload_result = {"name": "ref.png", "subfolder": "", "type": "input"}
        self.engine.upload_image.return_value = upload_result
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        path = self.manager.generate(
            "a fox",
            "/tmp/out",
            reference_images=[Reference("/tmp/ref.png", REFERENCE_ROLE_POSE_COMPOSITION)],
        )

        self.assertEqual(path, "/tmp/out/image.png")
        self.engine.upload_image.assert_called_once_with("/tmp/ref.png")
        self.engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image=upload_result,
            lora_name="",
            lora_strength=1.0,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
        )

    def test_unsupported_role_raises_before_any_upload(self):
        with self.assertRaises(GenerationError):
            self.manager.generate(
                "a fox", "/tmp/out", reference_images=[Reference("/tmp/ref.png", "identity")]
            )

        self.engine.upload_image.assert_not_called()
        self.engine.generate_image.assert_not_called()

    def test_unsupported_role_does_not_set_busy(self):
        with self.assertRaises(GenerationError):
            self.manager.generate(
                "a fox", "/tmp/out", reference_images=[Reference("/tmp/ref.png", "identity")]
            )

        self.assertFalse(self.manager.busy)

    def test_two_typed_references_raise_before_any_upload_regardless_of_role(self):
        with self.assertRaises(GenerationError):
            self.manager.generate(
                "a fox",
                "/tmp/out",
                reference_images=[
                    Reference("/tmp/a.png", REFERENCE_ROLE_POSE_COMPOSITION),
                    Reference("/tmp/b.png", "identity"),
                ],
            )

        self.engine.upload_image.assert_not_called()
        self.engine.generate_image.assert_not_called()

    def test_reference_role_constant_value(self):
        self.assertEqual(REFERENCE_ROLE_POSE_COMPOSITION, "pose_composition")

    def test_reference_is_a_minimal_namedtuple_of_path_and_role(self):
        reference = Reference("/tmp/ref.png", REFERENCE_ROLE_POSE_COMPOSITION)
        self.assertEqual(reference.path, "/tmp/ref.png")
        self.assertEqual(reference.role, REFERENCE_ROLE_POSE_COMPOSITION)
        self.assertEqual(Reference._fields, ("path", "role"))


class GenerationManagerReferenceStrengthTest(unittest.TestCase):
    """
    Mission 024: reference_strength is a generic 0.0-1.0 concept at
    this boundary — GenerationManager never imports
    DEFAULT_IMG2IMG_DENOISE and only translates it into
    generate_image()'s denoise= keyword (the one point where the
    ComfyUI-native name is used) when a reference is actually present
    and a value was actually given. Omitting it must reproduce Mission
    023's behavior byte-for-byte (see MISSION_024.md section 4).
    """

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_generate_with_reference_and_no_strength_never_forwards_denoise(self):
        self.engine.upload_image.return_value = {"name": "ref.png", "subfolder": "", "type": "input"}
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out", reference_images=["/tmp/ref.png"])

        _, kwargs = self.engine.generate_image.call_args
        self.assertNotIn("denoise", kwargs)

    def test_generate_with_reference_and_strength_forwards_it_as_denoise(self):
        self.engine.upload_image.return_value = {"name": "ref.png", "subfolder": "", "type": "input"}
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate(
            "a fox", "/tmp/out", reference_images=["/tmp/ref.png"], reference_strength=0.3
        )

        self.engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image={"name": "ref.png", "subfolder": "", "type": "input"},
            lora_name="",
            lora_strength=1.0,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
            denoise=0.3,
        )

    def test_generate_with_strength_but_no_reference_never_forwards_denoise(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out", reference_strength=0.3)

        self.engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image=None,
            lora_name="",
            lora_strength=1.0,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
        )

    def test_reference_strength_parameter_is_a_generic_optional_float(self):
        signature = inspect.signature(GenerationManager.generate)
        self.assertIn("reference_strength", signature.parameters)
        self.assertIsNone(signature.parameters["reference_strength"].default)


class GenerationManagerLoraTest(unittest.TestCase):
    """
    Mission 059 established lora_name/lora_strength as construction-only
    values, forwarded on every call regardless of reference_images,
    entirely independent of the reference/pose_composition mechanism
    (Mission 021/023/056). Mission 102 lifts the "never a per-call
    parameter" half of that contract (construction-time values remain,
    unchanged, as the fallback — see GenerationManagerLoraOverrideTest
    below for the three distinct override states this introduces).
    Default construction (no lora_name given) must still reproduce this
    manager's pre-Mission-059 forwarding byte-for-byte ("" / 1.0) when
    no override is given, already covered by every
    assert_called_once_with above.
    """

    def test_configured_lora_name_and_strength_are_forwarded_on_every_call(self):
        engine = MagicMock()
        engine.generate_image.return_value = "/tmp/out/image.png"
        manager = GenerationManager(
            engine,
            checkpoint_name="some-checkpoint.safetensors",
            lora_name="my_style.safetensors",
            lora_strength=0.7,
        )

        manager.generate("a fox", "/tmp/out")

        engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image=None,
            lora_name="my_style.safetensors",
            lora_strength=0.7,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
        )

    def test_configured_lora_is_forwarded_alongside_a_reference_image_too(self):
        # LoRA and the reference/pose_composition mechanism are
        # independent — both must be forwarded together without either
        # one suppressing the other.
        engine = MagicMock()
        engine.upload_image.return_value = {"name": "ref.png", "subfolder": "", "type": "input"}
        engine.generate_image.return_value = "/tmp/out/image.png"
        manager = GenerationManager(
            engine,
            checkpoint_name="some-checkpoint.safetensors",
            lora_name="my_style.safetensors",
            lora_strength=0.7,
        )

        manager.generate("a fox", "/tmp/out", reference_images=["/tmp/ref.png"])

        engine.generate_image.assert_called_once_with(
            "a fox",
            "/tmp/out",
            checkpoint_name="some-checkpoint.safetensors",
            reference_image={"name": "ref.png", "subfolder": "", "type": "input"},
            lora_name="my_style.safetensors",
            lora_strength=0.7,
            width=512,
            height=512,
            steps=20,
            cfg=8,
            sampler_name="euler",
            scheduler="normal",
            seed=None,
            negative_prompt="text, watermark",
        )

    def test_default_construction_forwards_empty_lora_name_and_native_default_strength(self):
        engine = MagicMock()
        engine.generate_image.return_value = "/tmp/out/image.png"
        manager = GenerationManager(engine, checkpoint_name="some-checkpoint.safetensors")

        manager.generate("a fox", "/tmp/out")

        _, kwargs = engine.generate_image.call_args
        self.assertEqual(kwargs["lora_name"], "")
        self.assertEqual(kwargs["lora_strength"], 1.0)

    def test_lora_name_and_strength_are_optional_generate_call_parameters(self):
        # Mission 102: unlike checkpoint_name (still construction-only,
        # untouched), lora_name/lora_strength are now also accepted as
        # optional per-call overrides — defaulting to None so an
        # omitted call reproduces the construction-only behavior above
        # byte-for-byte (see GenerationManagerLoraOverrideTest).
        signature = inspect.signature(GenerationManager.generate)
        self.assertIn("lora_name", signature.parameters)
        self.assertIn("lora_strength", signature.parameters)
        self.assertIsNone(signature.parameters["lora_name"].default)
        self.assertIsNone(signature.parameters["lora_strength"].default)


class GenerationManagerLoraOverrideTest(unittest.TestCase):
    """
    Mission 102: generate()'s lora_name/lora_strength per-call overrides
    — three distinct states, contract in MISSION_102.md section 3.2:

      A. omitted (None) -> falls back to the values given at
         construction (compatibility with Mission 059's "global Settings
         LoRA" behavior) ;
      B. lora_name="" given explicitly -> forwarded as-is, exactly
         ComfyUIEngine's own pre-existing "no LoRA" value — must NEVER
         fall back to a non-empty construction-time lora_name, or a
         global LoRA would silently reappear after being explicitly
         turned off ;
      C. any other non-empty lora_name -> forwarded as-is, together
         with whatever lora_strength was given.
    """

    def setUp(self):
        self.engine = MagicMock()
        self.engine.generate_image.return_value = "/tmp/out/image.png"
        # A non-empty construction-time LoRA, so state B's "must not
        # fall back" guarantee is actually exercised, not vacuously true.
        self.manager = GenerationManager(
            self.engine,
            checkpoint_name="some-checkpoint.safetensors",
            lora_name="global_from_settings.safetensors",
            lora_strength=0.8,
        )

    def test_state_a_no_override_falls_back_to_construction_values(self):
        self.manager.generate("a fox", "/tmp/out")

        _, kwargs = self.engine.generate_image.call_args
        self.assertEqual(kwargs["lora_name"], "global_from_settings.safetensors")
        self.assertEqual(kwargs["lora_strength"], 0.8)

    def test_state_b_explicit_empty_string_never_falls_back_to_settings_lora(self):
        self.manager.generate("a fox", "/tmp/out", lora_name="")

        _, kwargs = self.engine.generate_image.call_args
        self.assertEqual(kwargs["lora_name"], "")

    def test_state_c_explicit_lora_overrides_construction_value(self):
        self.manager.generate(
            "a fox", "/tmp/out", lora_name="character_x.safetensors", lora_strength=0.5
        )

        _, kwargs = self.engine.generate_image.call_args
        self.assertEqual(kwargs["lora_name"], "character_x.safetensors")
        self.assertEqual(kwargs["lora_strength"], 0.5)

    def test_state_c_strength_override_is_independent_of_lora_name(self):
        self.manager.generate("a fox", "/tmp/out", lora_strength=0.2)

        _, kwargs = self.engine.generate_image.call_args
        self.assertEqual(kwargs["lora_name"], "global_from_settings.safetensors")
        self.assertEqual(kwargs["lora_strength"], 0.2)


class GenerationManagerSamplerSchedulerDiscoveryTest(unittest.TestCase):
    """
    Mission 096: list_samplers()/list_schedulers() are thin passthroughs
    to the already-configured ComfyUIEngine — kept on GenerationManager
    rather than letting InferencePage reach ComfyUIEngine directly
    (Presentation -> Managers -> Infrastructure layering, CLAUDE.md).
    ComfyUIEngineError is normalized into GenerationError, same
    convention as generate() itself.
    """

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine)

    def test_list_samplers_forwards_the_engine_result(self):
        self.engine.list_samplers.return_value = ["euler", "dpmpp_2m"]

        result = self.manager.list_samplers()

        self.assertEqual(result, ["euler", "dpmpp_2m"])

    def test_list_samplers_forwards_timeout_to_the_engine(self):
        self.engine.list_samplers.return_value = ["euler"]

        self.manager.list_samplers(timeout=5.0)

        self.engine.list_samplers.assert_called_once_with(timeout=5.0)

    def test_list_samplers_normalizes_comfyui_engine_error(self):
        self.engine.list_samplers.side_effect = ComfyUIEngineError("server unreachable")

        with self.assertRaises(GenerationError):
            self.manager.list_samplers()

    def test_list_schedulers_forwards_the_engine_result(self):
        self.engine.list_schedulers.return_value = ["normal", "karras"]

        result = self.manager.list_schedulers()

        self.assertEqual(result, ["normal", "karras"])

    def test_list_schedulers_forwards_timeout_to_the_engine(self):
        self.engine.list_schedulers.return_value = ["normal"]

        self.manager.list_schedulers(timeout=5.0)

        self.engine.list_schedulers.assert_called_once_with(timeout=5.0)

    def test_list_schedulers_normalizes_comfyui_engine_error(self):
        self.engine.list_schedulers.side_effect = ComfyUIEngineError("server unreachable")

        with self.assertRaises(GenerationError):
            self.manager.list_schedulers()


class GenerationManagerGenerationParametersTest(unittest.TestCase):
    """
    Mission 096: generate()'s new width/height/steps/cfg/sampler_name/
    scheduler/seed/negative_prompt parameters are forwarded
    unconditionally to ComfyUIEngine.generate_image() — unlike
    reference_strength, none of these needs conditional forwarding (see
    generate()'s own docstring). Omitting all of them must reproduce
    the pre-Mission-096 call exactly (already covered by every
    assert_called_once_with in GenerationManagerTest/
    GenerationManagerReferenceImagesTest/GenerationManagerLoraTest
    above, each updated with the new default kwargs).
    """

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_custom_generation_parameters_are_all_forwarded(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate(
            "a fox",
            "/tmp/out",
            width=768,
            height=1024,
            steps=33,
            cfg=6.5,
            sampler_name="dpmpp_2m",
            scheduler="karras",
            seed=999,
            negative_prompt="ugly",
        )

        _, kwargs = self.engine.generate_image.call_args
        self.assertEqual(kwargs["width"], 768)
        self.assertEqual(kwargs["height"], 1024)
        self.assertEqual(kwargs["steps"], 33)
        self.assertEqual(kwargs["cfg"], 6.5)
        self.assertEqual(kwargs["sampler_name"], "dpmpp_2m")
        self.assertEqual(kwargs["scheduler"], "karras")
        self.assertEqual(kwargs["seed"], 999)
        self.assertEqual(kwargs["negative_prompt"], "ugly")

    def test_width_and_height_are_forwarded_even_with_a_reference_present(self):
        # GenerationManager itself never special-cases width/height on
        # reference_images — that omission-on-img2img decision belongs
        # entirely to ComfyUIEngine.generate_image() (see
        # MISSION_096.md section 3/10). Forwarding them here regardless
        # of a reference has no effect on that path.
        self.engine.upload_image.return_value = {"name": "ref.png", "subfolder": "", "type": "input"}
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate(
            "a fox", "/tmp/out", reference_images=["/tmp/ref.png"], width=768, height=1024
        )

        _, kwargs = self.engine.generate_image.call_args
        self.assertEqual(kwargs["width"], 768)
        self.assertEqual(kwargs["height"], 1024)

    def test_omitted_seed_forwards_none(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out")

        _, kwargs = self.engine.generate_image.call_args
        self.assertIsNone(kwargs["seed"])

    def test_generate_does_not_import_random(self):
        # MISSION_096.md section 5: seed resolution belongs to
        # InferencePage alone — GenerationManager must stay a pure
        # forwarder, never generating a random seed itself.
        source = Path(inspect.getfile(GenerationManager)).read_text(encoding="utf-8")
        self.assertNotIn("import random", source)


class GenerationManagerComfyUIAgnosticismTest(unittest.TestCase):
    """
    Mission 023: GenerationManager must never learn ComfyUI's JSON
    graph vocabulary (node IDs, class_type values, LoadImage/VAEEncode/
    KSampler...) — that knowledge stays entirely in
    src/engines/workflows/. This is what keeps the dict
    upload_image() returns opaque all the way through
    GenerationManager, per MISSION_023.md section 7.
    """

    def test_module_source_contains_no_comfyui_graph_vocabulary(self):
        source = Path(inspect.getfile(GenerationManager)).read_text(encoding="utf-8").lower()
        forbidden_terms = (
            "loadimage",
            "vaeencode",
            "vaedecode",
            "ksampler",
            "class_type",
            "checkpointloadersimple",
            "cliptextencode",
            "saveimage",
        )
        for term in forbidden_terms:
            self.assertNotIn(
                term,
                source,
                f"GenerationManager must not reference ComfyUI graph vocabulary ('{term}')",
            )


class GenerationManagerEngineOverrideTest(unittest.TestCase):
    """
    Mission 107 (MISSION_107.md section 3.4): generate()'s optional
    engine/checkpoint_name per-call overrides — the same fallback-to-
    constructor-value shape as lora_name/lora_strength (Mission 102).
    Omitting either must reproduce the exact historical ComfyUI-only
    behavior (every assert_called_once_with above, all unchanged); an
    explicit engine/checkpoint_name must be used instead of the
    constructor's own, without GenerationManager ever holding a
    "current engine" of its own between calls.
    """

    def setUp(self):
        self.comfyui_engine = MagicMock()
        self.manager = GenerationManager(
            self.comfyui_engine, checkpoint_name="constructor-checkpoint.safetensors"
        )

    def test_engine_and_checkpoint_name_are_optional_generate_call_parameters(self):
        signature = inspect.signature(GenerationManager.generate)
        self.assertIn("engine", signature.parameters)
        self.assertIn("checkpoint_name", signature.parameters)
        self.assertIsNone(signature.parameters["engine"].default)
        self.assertIsNone(signature.parameters["checkpoint_name"].default)

    def test_omitted_engine_falls_back_to_constructor_engine(self):
        self.comfyui_engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out")

        self.comfyui_engine.generate_image.assert_called_once()

    def test_omitted_checkpoint_name_falls_back_to_constructor_value(self):
        self.comfyui_engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out")

        _, kwargs = self.comfyui_engine.generate_image.call_args
        self.assertEqual(kwargs["checkpoint_name"], "constructor-checkpoint.safetensors")

    def test_explicit_engine_override_is_used_instead_of_the_constructor_engine(self):
        other_engine = MagicMock()
        other_engine.generate_image.return_value = "/tmp/out/image.png"

        path = self.manager.generate("a fox", "/tmp/out", engine=other_engine)

        self.assertEqual(path, "/tmp/out/image.png")
        other_engine.generate_image.assert_called_once()
        self.comfyui_engine.generate_image.assert_not_called()

    def test_explicit_checkpoint_name_override_is_forwarded_instead_of_constructor_value(self):
        self.comfyui_engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate("a fox", "/tmp/out", checkpoint_name="override.safetensors")

        _, kwargs = self.comfyui_engine.generate_image.call_args
        self.assertEqual(kwargs["checkpoint_name"], "override.safetensors")

    def test_explicit_engine_and_checkpoint_together(self):
        other_engine = MagicMock()
        other_engine.generate_image.return_value = "/tmp/out/other.png"

        path = self.manager.generate(
            "a fox", "/tmp/out", engine=other_engine, checkpoint_name="forge-checkpoint"
        )

        self.assertEqual(path, "/tmp/out/other.png")
        _, kwargs = other_engine.generate_image.call_args
        self.assertEqual(kwargs["checkpoint_name"], "forge-checkpoint")
        self.comfyui_engine.generate_image.assert_not_called()

    def test_engine_can_be_switched_back_and_forth_across_successive_calls(self):
        # Mission 107's explicit requirement: ComfyUI -> Forge -> ComfyUI
        # within the same session, no reconstruction of GenerationManager,
        # no stale state carried between calls.
        forge_engine = MagicMock()
        self.comfyui_engine.generate_image.return_value = "/tmp/out/comfy1.png"
        forge_engine.generate_image.return_value = "/tmp/out/forge.png"

        first = self.manager.generate("a fox", "/tmp/out")
        second = self.manager.generate("a fox", "/tmp/out", engine=forge_engine)
        self.comfyui_engine.generate_image.return_value = "/tmp/out/comfy2.png"
        third = self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(first, "/tmp/out/comfy1.png")
        self.assertEqual(second, "/tmp/out/forge.png")
        self.assertEqual(third, "/tmp/out/comfy2.png")

    def test_forge_engine_error_is_normalized_into_generation_error(self):
        forge_engine = MagicMock()
        forge_engine.generate_image.side_effect = ForgeEngineError("server unreachable")

        with self.assertRaises(GenerationError):
            self.manager.generate("a fox", "/tmp/out", engine=forge_engine)

    def test_engine_is_duck_typed_never_isinstance_checked_against_comfyui(self):
        # Any object exposing generate_image()/upload_image() is
        # accepted — never type-checked against ComfyUIEngine
        # specifically (it already never was, MagicMock has always
        # stood in for it in every test above).
        class BareEngine:
            def generate_image(self, *args, **kwargs):
                return "/tmp/out/bare.png"

        path = self.manager.generate("a fox", "/tmp/out", engine=BareEngine())

        self.assertEqual(path, "/tmp/out/bare.png")


class GenerationManagerReferenceStrengthEngineAgnosticismTest(unittest.TestCase):
    """
    Mission 107 (architect's explicit correction to this mission's
    first draft, MISSION_107.md section 3.4): GenerationManager must
    forward reference_strength under exactly one common keyword,
    "denoise", regardless of which concrete engine is targeted — never
    branch on the engine's identity or type. ForgeEngine.generate_image()
    accepts that same "denoise" parameter name (see its own docstring)
    and is the only place that translates it into Forge's own native
    wire field, "denoising_strength" — GenerationManager itself never
    knows that second name exists.
    """

    def setUp(self):
        self.manager = GenerationManager(
            MagicMock(), checkpoint_name="constructor-checkpoint.safetensors"
        )

    def test_reference_strength_is_forwarded_as_denoise_for_the_default_comfyui_engine(self):
        comfyui_engine = MagicMock()
        comfyui_engine.upload_image.return_value = {"name": "ref.png"}
        comfyui_engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate(
            "a fox",
            "/tmp/out",
            engine=comfyui_engine,
            reference_images=["/tmp/ref.png"],
            reference_strength=0.3,
        )

        _, kwargs = comfyui_engine.generate_image.call_args
        self.assertEqual(kwargs["denoise"], 0.3)

    def test_reference_strength_is_also_forwarded_as_denoise_for_a_forge_engine(self):
        forge_engine = MagicMock(spec=ForgeEngine)
        forge_engine.upload_image.return_value = {"path": "/tmp/ref.png"}
        forge_engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate(
            "a fox",
            "/tmp/out",
            engine=forge_engine,
            reference_images=["/tmp/ref.png"],
            reference_strength=0.3,
        )

        _, kwargs = forge_engine.generate_image.call_args
        self.assertEqual(kwargs["denoise"], 0.3)
        self.assertNotIn("denoising_strength", kwargs)

    def test_no_strength_forwards_no_extra_keyword_for_a_forge_engine(self):
        forge_engine = MagicMock(spec=ForgeEngine)
        forge_engine.upload_image.return_value = {"path": "/tmp/ref.png"}
        forge_engine.generate_image.return_value = "/tmp/out/image.png"

        self.manager.generate(
            "a fox", "/tmp/out", engine=forge_engine, reference_images=["/tmp/ref.png"]
        )

        _, kwargs = forge_engine.generate_image.call_args
        self.assertNotIn("denoise", kwargs)
        self.assertNotIn("denoising_strength", kwargs)

    def test_generation_manager_source_never_mentions_denoising_strength(self):
        # Locks in the invariant directly: GenerationManager must never
        # gain any knowledge of Forge's own native wire field name.
        source = Path(inspect.getfile(GenerationManager)).read_text(encoding="utf-8")
        self.assertNotIn("denoising_strength", source)

    def test_generation_manager_source_never_isinstance_checks_an_engine_type(self):
        source = Path(inspect.getfile(GenerationManager)).read_text(encoding="utf-8")
        self.assertNotIn("isinstance(target_engine", source)
        self.assertNotIn("isinstance(engine", source)


if __name__ == "__main__":
    unittest.main()
