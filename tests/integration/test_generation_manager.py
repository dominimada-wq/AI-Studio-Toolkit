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
from src.managers.generation_manager import GenerationError, GenerationManager


class GenerationManagerTest(unittest.TestCase):

    def setUp(self):
        self.engine = MagicMock()
        self.manager = GenerationManager(self.engine, checkpoint_name="some-checkpoint.safetensors")

    def test_successful_generation_returns_path_and_forwards_arguments(self):
        self.engine.generate_image.return_value = "/tmp/out/image.png"

        path = self.manager.generate("a fox", "/tmp/out")

        self.assertEqual(path, "/tmp/out/image.png")
        self.engine.generate_image.assert_called_once_with(
            "a fox", "/tmp/out", checkpoint_name="some-checkpoint.safetensors", reference_image=None
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

        def fake_generate_image(prompt_text, output_directory, checkpoint_name, reference_image=None):
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
        def fake_generate_image(prompt_text, output_directory, checkpoint_name, reference_image=None):
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


if __name__ == "__main__":
    unittest.main()
