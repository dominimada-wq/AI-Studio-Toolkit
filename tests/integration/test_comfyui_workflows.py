"""
Coverage for src/engines/workflows/comfyui_workflows.py — Mission 023's
pure graph-construction functions. No network, no mocking needed: these
are plain functions returning dict, tested directly against their
output structure.
"""

import unittest
from unittest.mock import patch

from src.engines.workflows.comfyui_workflows import (
    DEFAULT_CFG,
    DEFAULT_HEIGHT,
    DEFAULT_IMG2IMG_DENOISE,
    DEFAULT_NEGATIVE_PROMPT,
    DEFAULT_SAMPLER_NAME,
    DEFAULT_SCHEDULER,
    DEFAULT_STEPS,
    DEFAULT_WIDTH,
    DEMO_CHECKPOINT_NAME,
    build_img2img_workflow,
    build_txt2img_workflow,
)


class BuildTxt2ImgWorkflowTest(unittest.TestCase):
    """
    Mission 023: build_txt2img_workflow() replaces Mission 012's
    build_demo_workflow() — these tests lock in that the move changed
    nothing about the graph itself (same node IDs, same class_type
    values, same connections, same defaults), the equivalence required
    by the mission spec.
    """

    def test_workflow_has_the_seven_expected_nodes(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(set(workflow.keys()), {"3", "4", "5", "6", "7", "8", "9"})

    def test_node_class_types_are_unchanged(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["3"]["class_type"], "KSampler")
        self.assertEqual(workflow["4"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(workflow["5"]["class_type"], "EmptyLatentImage")
        self.assertEqual(workflow["6"]["class_type"], "CLIPTextEncode")
        self.assertEqual(workflow["7"]["class_type"], "CLIPTextEncode")
        self.assertEqual(workflow["8"]["class_type"], "VAEDecode")
        self.assertEqual(workflow["9"]["class_type"], "SaveImage")

    def test_prompt_text_reaches_the_positive_clip_text_encode_node(self):
        workflow = build_txt2img_workflow("a blue sphere")
        self.assertEqual(workflow["6"]["inputs"]["text"], "a blue sphere")

    def test_negative_prompt_is_the_fixed_default(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["7"]["inputs"]["text"], "text, watermark")

    def test_checkpoint_name_defaults_to_demo_checkpoint(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["4"]["inputs"]["ckpt_name"], DEMO_CHECKPOINT_NAME)

    def test_checkpoint_name_is_overridable(self):
        workflow = build_txt2img_workflow("a red fox", checkpoint_name="custom.safetensors")
        self.assertEqual(workflow["4"]["inputs"]["ckpt_name"], "custom.safetensors")

    def test_latent_image_comes_from_empty_latent_image_node(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["3"]["inputs"]["latent_image"], ["5", 0])
        self.assertEqual(
            workflow["5"]["inputs"], {"batch_size": 1, "height": 512, "width": 512}
        )

    def test_denoise_is_full_strength(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["3"]["inputs"]["denoise"], 1)

    def test_sampler_cfg_and_steps_are_unchanged(self):
        workflow = build_txt2img_workflow("a red fox")
        inputs = workflow["3"]["inputs"]
        self.assertEqual(inputs["sampler_name"], "euler")
        self.assertEqual(inputs["scheduler"], "normal")
        self.assertEqual(inputs["cfg"], 8)
        self.assertEqual(inputs["steps"], 20)

    def test_positive_and_negative_encode_share_the_checkpoint_clip(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["6"]["inputs"]["clip"], ["4", 1])
        self.assertEqual(workflow["7"]["inputs"]["clip"], ["4", 1])

    def test_ksampler_wires_model_positive_negative(self):
        workflow = build_txt2img_workflow("a red fox")
        inputs = workflow["3"]["inputs"]
        self.assertEqual(inputs["model"], ["4", 0])
        self.assertEqual(inputs["positive"], ["6", 0])
        self.assertEqual(inputs["negative"], ["7", 0])

    def test_vae_decode_and_save_image_are_unchanged(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(workflow["8"]["inputs"], {"samples": ["3", 0], "vae": ["4", 2]})
        self.assertEqual(
            workflow["9"]["inputs"], {"filename_prefix": "AIStudioToolkit", "images": ["8", 0]}
        )

    def test_seed_is_randomized_between_calls(self):
        first = build_txt2img_workflow("a red fox")
        second = build_txt2img_workflow("a red fox")
        # Extremely unlikely to collide (random.randint(0, 2**32 - 1)) —
        # confirms the graph isn't built with the exact same fixed seed
        # every time, same property build_demo_workflow() already had.
        self.assertNotEqual(first["3"]["inputs"]["seed"], second["3"]["inputs"]["seed"])


class BuildImg2ImgWorkflowTest(unittest.TestCase):
    """
    Mission 023: build_img2img_workflow() — the first non-txt2img
    graph, native ComfyUI core nodes only.
    """

    def setUp(self):
        self.reference_image = {"name": "portrait.png", "subfolder": "", "type": "input"}

    def test_workflow_has_the_expected_eight_nodes(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(set(workflow.keys()), {"3", "4", "5", "6", "7", "8", "9", "10"})

    def test_load_image_node_class_type_and_input(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["10"]["class_type"], "LoadImage")
        self.assertEqual(workflow["10"]["inputs"]["image"], "portrait.png")

    def test_load_image_uses_bare_name_when_subfolder_is_empty(self):
        reference = {"name": "portrait.png", "subfolder": "", "type": "input"}
        workflow = build_img2img_workflow("a red fox", reference)
        self.assertEqual(workflow["10"]["inputs"]["image"], "portrait.png")

    def test_load_image_uses_subfolder_prefixed_name_when_subfolder_present(self):
        reference = {"name": "portrait.png", "subfolder": "characters/alice", "type": "input"}
        workflow = build_img2img_workflow("a red fox", reference)
        self.assertEqual(workflow["10"]["inputs"]["image"], "characters/alice/portrait.png")

    def test_type_field_of_the_upload_result_is_not_required_by_the_graph(self):
        # The graph only needs "image" on the LoadImage node — "type"
        # is part of the upload_image() contract (Mission 021) but has
        # no equivalent LoadImage input; confirms this function reads
        # only what it actually needs from the dict.
        reference = {"name": "portrait.png", "subfolder": "", "type": "input"}
        workflow = build_img2img_workflow("a red fox", reference)
        self.assertNotIn("type", workflow["10"]["inputs"])

    def test_vae_encode_node_replaces_empty_latent_image(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["5"]["class_type"], "VAEEncode")
        self.assertEqual(workflow["5"]["inputs"], {"pixels": ["10", 0], "vae": ["4", 2]})

    def test_no_empty_latent_image_node_in_the_img2img_graph(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        class_types = {node["class_type"] for node in workflow.values()}
        self.assertNotIn("EmptyLatentImage", class_types)

    def test_ksampler_latent_image_comes_from_vae_encode(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["3"]["inputs"]["latent_image"], ["5", 0])

    def test_denoise_defaults_to_the_module_constant(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["3"]["inputs"]["denoise"], DEFAULT_IMG2IMG_DENOISE)
        self.assertEqual(DEFAULT_IMG2IMG_DENOISE, 0.75)

    def test_denoise_is_explicitly_overridable(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image, denoise=0.4)
        self.assertEqual(workflow["3"]["inputs"]["denoise"], 0.4)

    def test_checkpoint_loader_model_and_vae_connections_unchanged(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["4"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(workflow["3"]["inputs"]["model"], ["4", 0])
        self.assertEqual(workflow["6"]["inputs"]["clip"], ["4", 1])
        self.assertEqual(workflow["7"]["inputs"]["clip"], ["4", 1])
        self.assertEqual(workflow["5"]["inputs"]["vae"], ["4", 2])
        self.assertEqual(workflow["8"]["inputs"]["vae"], ["4", 2])

    def test_positive_and_negative_prompt_encoding_unchanged(self):
        workflow = build_img2img_workflow("a blue sphere", self.reference_image)
        self.assertEqual(workflow["6"]["inputs"]["text"], "a blue sphere")
        self.assertEqual(workflow["7"]["inputs"]["text"], "text, watermark")
        self.assertEqual(workflow["3"]["inputs"]["positive"], ["6", 0])
        self.assertEqual(workflow["3"]["inputs"]["negative"], ["7", 0])

    def test_vae_decode_and_save_image_unchanged(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["8"]["class_type"], "VAEDecode")
        self.assertEqual(workflow["8"]["inputs"], {"samples": ["3", 0], "vae": ["4", 2]})
        self.assertEqual(workflow["9"]["class_type"], "SaveImage")
        self.assertEqual(
            workflow["9"]["inputs"], {"filename_prefix": "AIStudioToolkit", "images": ["8", 0]}
        )

    def test_checkpoint_name_is_overridable(self):
        workflow = build_img2img_workflow(
            "a red fox", self.reference_image, checkpoint_name="custom.safetensors"
        )
        self.assertEqual(workflow["4"]["inputs"]["ckpt_name"], "custom.safetensors")


class NoLoraProducesTheExactPreMission059WorkflowTest(unittest.TestCase):
    """
    Mission 059's own compatibility proof: with lora_name unset (or
    explicitly ""), both builders must return the exact dict they
    returned before this mission existed — not merely "no node 11",
    every single key/value.

    random.randint() makes the "seed" field non-deterministic between
    any two calls regardless of LoRA (a pre-existing property — see
    BuildTxt2ImgWorkflowTest.test_seed_is_randomized_between_calls —,
    not something Mission 059 introduces), so a literal byte-for-byte
    JSON string comparison would be misleading: it would need the seed
    patched anyway to be meaningful, and dict equality on JSON-primitive
    values (str/int/float/list/dict only, verified by every field
    below) is a strictly more rigorous check than comparing serialized
    bytes — it is immune to key-ordering artifacts a naive JSON string
    diff could wrongly flag as a difference. random.randint is patched
    here purely so the two dicts under comparison share the same seed;
    it does not change what is being proven.
    """

    @patch("src.engines.workflows.comfyui_workflows.random.randint", return_value=42)
    def test_txt2img_workflow_without_lora_is_dict_equal_to_the_pre_mission_059_shape(self, _mock_randint):
        workflow = build_txt2img_workflow("a red fox", checkpoint_name="custom.safetensors")

        expected = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 8,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": 42,
                    "steps": 20,
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "custom.safetensors"},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": 512, "width": 512},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "a red fox"},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "text, watermark"},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "AIStudioToolkit", "images": ["8", 0]},
            },
        }

        self.assertEqual(workflow, expected)

    @patch("src.engines.workflows.comfyui_workflows.random.randint", return_value=42)
    def test_txt2img_workflow_explicit_empty_lora_name_matches_omitted_default(self, _mock_randint):
        omitted = build_txt2img_workflow("a red fox", checkpoint_name="custom.safetensors")
        explicit_empty = build_txt2img_workflow(
            "a red fox", checkpoint_name="custom.safetensors", lora_name="", lora_strength=1.0
        )

        self.assertEqual(omitted, explicit_empty)

    @patch("src.engines.workflows.comfyui_workflows.random.randint", return_value=42)
    def test_img2img_workflow_without_lora_is_dict_equal_to_the_pre_mission_059_shape(self, _mock_randint):
        reference_image = {"name": "portrait.png", "subfolder": "", "type": "input"}

        workflow = build_img2img_workflow(
            "a red fox", reference_image, checkpoint_name="custom.safetensors", denoise=0.6
        )

        expected = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 8,
                    "denoise": 0.6,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": 42,
                    "steps": 20,
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "custom.safetensors"},
            },
            "5": {
                "class_type": "VAEEncode",
                "inputs": {"pixels": ["10", 0], "vae": ["4", 2]},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "a red fox"},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "text, watermark"},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "AIStudioToolkit", "images": ["8", 0]},
            },
            "10": {
                "class_type": "LoadImage",
                "inputs": {"image": "portrait.png"},
            },
        }

        self.assertEqual(workflow, expected)

    @patch("src.engines.workflows.comfyui_workflows.random.randint", return_value=42)
    def test_img2img_workflow_explicit_empty_lora_name_matches_omitted_default(self, _mock_randint):
        reference_image = {"name": "portrait.png", "subfolder": "", "type": "input"}

        omitted = build_img2img_workflow(
            "a red fox", reference_image, checkpoint_name="custom.safetensors"
        )
        explicit_empty = build_img2img_workflow(
            "a red fox",
            reference_image,
            checkpoint_name="custom.safetensors",
            lora_name="",
            lora_strength=1.0,
        )

        self.assertEqual(omitted, explicit_empty)


class LoraInsertedWhenConfiguredTest(unittest.TestCase):
    """
    Mission 059: the flip side of NoLoraProducesTheExactPreMission059
    WorkflowTest above — with a non-empty lora_name, exactly one
    LoraLoader node ("11") is present, model/clip consumers ("3".model,
    "6"/"7".clip) are rewired onto it, and vae stays wired to the
    checkpoint ("4") — LoraLoader never outputs one.
    """

    def test_txt2img_lora_loader_is_inserted_and_wired(self):
        workflow = build_txt2img_workflow(
            "a red fox", lora_name="style.safetensors", lora_strength=0.65
        )

        self.assertEqual(
            workflow["11"],
            {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": ["4", 0],
                    "clip": ["4", 1],
                    "lora_name": "style.safetensors",
                    "strength_model": 0.65,
                    "strength_clip": 0.65,
                },
            },
        )
        self.assertEqual(workflow["3"]["inputs"]["model"], ["11", 0])
        self.assertEqual(workflow["6"]["inputs"]["clip"], ["11", 1])
        self.assertEqual(workflow["7"]["inputs"]["clip"], ["11", 1])
        self.assertEqual(workflow["8"]["inputs"]["vae"], ["4", 2])

    def test_txt2img_lora_loader_uses_native_default_strength_when_unspecified(self):
        workflow = build_txt2img_workflow("a red fox", lora_name="style.safetensors")

        self.assertEqual(workflow["11"]["inputs"]["strength_model"], 1.0)
        self.assertEqual(workflow["11"]["inputs"]["strength_clip"], 1.0)

    def test_txt2img_exactly_one_lora_loader_node(self):
        workflow = build_txt2img_workflow("a red fox", lora_name="style.safetensors")

        lora_nodes = [n for n in workflow.values() if n["class_type"] == "LoraLoader"]
        self.assertEqual(len(lora_nodes), 1)

    def test_img2img_lora_loader_is_inserted_and_wired(self):
        reference_image = {"name": "portrait.png", "subfolder": "", "type": "input"}

        workflow = build_img2img_workflow(
            "a red fox", reference_image, lora_name="style.safetensors", lora_strength=0.65
        )

        self.assertEqual(
            workflow["11"],
            {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": ["4", 0],
                    "clip": ["4", 1],
                    "lora_name": "style.safetensors",
                    "strength_model": 0.65,
                    "strength_clip": 0.65,
                },
            },
        )
        self.assertEqual(workflow["3"]["inputs"]["model"], ["11", 0])
        self.assertEqual(workflow["6"]["inputs"]["clip"], ["11", 1])
        self.assertEqual(workflow["7"]["inputs"]["clip"], ["11", 1])
        # Both vae wires (VAEEncode "5" and VAEDecode "8") stay on the
        # checkpoint — LoraLoader touches neither.
        self.assertEqual(workflow["5"]["inputs"]["vae"], ["4", 2])
        self.assertEqual(workflow["8"]["inputs"]["vae"], ["4", 2])
        # The reference mechanism (Mission 023/056) is untouched.
        self.assertEqual(workflow["5"]["inputs"]["pixels"], ["10", 0])
        self.assertEqual(workflow["10"]["class_type"], "LoadImage")

    def test_img2img_exactly_one_lora_loader_node(self):
        reference_image = {"name": "portrait.png", "subfolder": "", "type": "input"}
        workflow = build_img2img_workflow(
            "a red fox", reference_image, lora_name="style.safetensors"
        )

        lora_nodes = [n for n in workflow.values() if n["class_type"] == "LoraLoader"]
        self.assertEqual(len(lora_nodes), 1)


class Txt2ImgGenerationParametersTest(unittest.TestCase):
    """
    Mission 096: build_txt2img_workflow() replaces Mission 012's fixed
    demo values with real parameters. DEFAULT_* constants reproduce the
    exact literals this function hardcoded before this mission — a call
    that never passes these new arguments must keep producing
    byte-for-byte the same workflow as before (see
    BuildTxt2ImgWorkflowTest above, all unmodified).
    """

    def test_default_call_still_uses_the_pre_mission_096_literals(self):
        workflow = build_txt2img_workflow("a red fox")
        self.assertEqual(
            workflow["5"]["inputs"], {"batch_size": 1, "height": 512, "width": 512}
        )
        self.assertEqual(workflow["3"]["inputs"]["steps"], 20)
        self.assertEqual(workflow["3"]["inputs"]["cfg"], 8)
        self.assertEqual(workflow["3"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(workflow["3"]["inputs"]["scheduler"], "normal")
        self.assertEqual(workflow["7"]["inputs"]["text"], "text, watermark")

    def test_default_constants_match_the_pre_mission_096_literals(self):
        # Locks the DEFAULT_* constants themselves to the exact values
        # they must reproduce — a change to any of these would silently
        # break backward compatibility even if the test above still
        # passed (both would move together).
        self.assertEqual(DEFAULT_WIDTH, 512)
        self.assertEqual(DEFAULT_HEIGHT, 512)
        self.assertEqual(DEFAULT_STEPS, 20)
        self.assertEqual(DEFAULT_CFG, 8)
        self.assertEqual(DEFAULT_SAMPLER_NAME, "euler")
        self.assertEqual(DEFAULT_SCHEDULER, "normal")
        self.assertEqual(DEFAULT_NEGATIVE_PROMPT, "text, watermark")

    def test_custom_width_and_height_reach_empty_latent_image_node(self):
        workflow = build_txt2img_workflow("a red fox", width=768, height=1024)
        self.assertEqual(
            workflow["5"]["inputs"], {"batch_size": 1, "height": 1024, "width": 768}
        )

    def test_batch_size_is_never_a_parameter(self):
        # Mission 096 section 7: batch stays a literal 1, not exposed —
        # confirms this function's signature was never given a
        # batch_size parameter, not just that the default is 1.
        import inspect
        signature = inspect.signature(build_txt2img_workflow)
        self.assertNotIn("batch_size", signature.parameters)

    def test_custom_steps_cfg_sampler_scheduler_reach_ksampler_node(self):
        workflow = build_txt2img_workflow(
            "a red fox", steps=35, cfg=12.5, sampler_name="dpmpp_2m", scheduler="karras"
        )
        inputs = workflow["3"]["inputs"]
        self.assertEqual(inputs["steps"], 35)
        self.assertEqual(inputs["cfg"], 12.5)
        self.assertEqual(inputs["sampler_name"], "dpmpp_2m")
        self.assertEqual(inputs["scheduler"], "karras")

    def test_custom_negative_prompt_reaches_the_negative_clip_text_encode_node(self):
        workflow = build_txt2img_workflow("a red fox", negative_prompt="blurry, extra limbs")
        self.assertEqual(workflow["7"]["inputs"]["text"], "blurry, extra limbs")
        # The positive prompt node must stay untouched by this change.
        self.assertEqual(workflow["6"]["inputs"]["text"], "a red fox")

    def test_omitted_seed_still_randomizes_between_calls(self):
        # Locks in the exact contract MISSION_096.md section 5 requires:
        # the internal random.randint() fallback survives unmodified —
        # same property already covered by
        # BuildTxt2ImgWorkflowTest.test_seed_is_randomized_between_calls,
        # re-asserted here alongside the other new parameters for
        # completeness of this test class.
        first = build_txt2img_workflow("a red fox")
        second = build_txt2img_workflow("a red fox")
        self.assertNotEqual(first["3"]["inputs"]["seed"], second["3"]["inputs"]["seed"])

    def test_explicit_seed_is_used_verbatim(self):
        workflow = build_txt2img_workflow("a red fox", seed=123456789)
        self.assertEqual(workflow["3"]["inputs"]["seed"], 123456789)

    def test_explicit_seed_zero_is_not_treated_as_falsy_random(self):
        # seed=0 is a legitimate fixed value — must not be silently
        # treated as "no seed given" by an `if seed:` style bug.
        workflow = build_txt2img_workflow("a red fox", seed=0)
        self.assertEqual(workflow["3"]["inputs"]["seed"], 0)

    def test_new_parameters_are_independent_of_lora(self):
        # Confirms width/height/steps/cfg/sampler/scheduler/seed/
        # negative_prompt survive _apply_lora()'s post-processing
        # unchanged — that function only ever rewires model/clip edges.
        workflow = build_txt2img_workflow(
            "a red fox",
            lora_name="style.safetensors",
            lora_strength=0.5,
            width=640,
            height=896,
            steps=30,
            cfg=6,
            sampler_name="euler_ancestral",
            scheduler="simple",
            seed=42,
            negative_prompt="ugly",
        )
        self.assertEqual(workflow["5"]["inputs"], {"batch_size": 1, "height": 896, "width": 640})
        inputs = workflow["3"]["inputs"]
        self.assertEqual(inputs["steps"], 30)
        self.assertEqual(inputs["cfg"], 6)
        self.assertEqual(inputs["sampler_name"], "euler_ancestral")
        self.assertEqual(inputs["scheduler"], "simple")
        self.assertEqual(inputs["seed"], 42)
        self.assertEqual(workflow["7"]["inputs"]["text"], "ugly")
        self.assertEqual(workflow["11"]["class_type"], "LoraLoader")


class Img2ImgGenerationParametersTest(unittest.TestCase):
    """
    Mission 096: build_img2img_workflow() gains the same steps/cfg/
    sampler/scheduler/seed/negative_prompt parameters as txt2img — but
    deliberately NOT width/height, which this function's own
    longstanding contract already excludes (dimensions come from the
    loaded reference image via VAEEncode, never from a parameter). See
    MISSION_096.md section 3/10.
    """

    def setUp(self):
        self.reference_image = {"name": "portrait.png", "subfolder": "", "type": "input"}

    def test_default_call_still_uses_the_pre_mission_096_literals(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image)
        self.assertEqual(workflow["3"]["inputs"]["steps"], 20)
        self.assertEqual(workflow["3"]["inputs"]["cfg"], 8)
        self.assertEqual(workflow["3"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(workflow["3"]["inputs"]["scheduler"], "normal")
        self.assertEqual(workflow["7"]["inputs"]["text"], "text, watermark")

    def test_width_and_height_are_not_accepted_parameters(self):
        # The defining property of this function per MISSION_096.md
        # section 3: passing width/height must fail loudly (TypeError),
        # never be silently accepted and ignored.
        with self.assertRaises(TypeError):
            build_img2img_workflow("a red fox", self.reference_image, width=768)
        with self.assertRaises(TypeError):
            build_img2img_workflow("a red fox", self.reference_image, height=768)

    def test_dimensions_still_come_from_the_reference_image_not_a_literal(self):
        workflow = build_img2img_workflow(
            "a red fox", self.reference_image, steps=35, cfg=9, sampler_name="dpmpp_2m",
            scheduler="karras", seed=7, negative_prompt="ugly",
        )
        self.assertEqual(workflow["5"]["class_type"], "VAEEncode")
        self.assertEqual(workflow["5"]["inputs"], {"pixels": ["10", 0], "vae": ["4", 2]})
        self.assertNotIn("width", workflow["5"]["inputs"])
        self.assertNotIn("height", workflow["5"]["inputs"])

    def test_custom_steps_cfg_sampler_scheduler_reach_ksampler_node(self):
        workflow = build_img2img_workflow(
            "a red fox", self.reference_image, steps=40, cfg=11, sampler_name="ddim", scheduler="ddim_uniform"
        )
        inputs = workflow["3"]["inputs"]
        self.assertEqual(inputs["steps"], 40)
        self.assertEqual(inputs["cfg"], 11)
        self.assertEqual(inputs["sampler_name"], "ddim")
        self.assertEqual(inputs["scheduler"], "ddim_uniform")

    def test_custom_negative_prompt_reaches_the_negative_clip_text_encode_node(self):
        workflow = build_img2img_workflow(
            "a red fox", self.reference_image, negative_prompt="blurry"
        )
        self.assertEqual(workflow["7"]["inputs"]["text"], "blurry")

    def test_explicit_seed_is_used_verbatim(self):
        workflow = build_img2img_workflow("a red fox", self.reference_image, seed=987654321)
        self.assertEqual(workflow["3"]["inputs"]["seed"], 987654321)

    def test_omitted_seed_still_randomizes_between_calls(self):
        first = build_img2img_workflow("a red fox", self.reference_image)
        second = build_img2img_workflow("a red fox", self.reference_image)
        self.assertNotEqual(first["3"]["inputs"]["seed"], second["3"]["inputs"]["seed"])

    def test_denoise_stays_independent_of_the_new_parameters(self):
        # denoise (Mission 023/024) must not be disturbed by the new
        # Mission 096 parameters living on the same KSampler node.
        workflow = build_img2img_workflow(
            "a red fox", self.reference_image, denoise=0.4, steps=25, cfg=7
        )
        self.assertEqual(workflow["3"]["inputs"]["denoise"], 0.4)


if __name__ == "__main__":
    unittest.main()
