"""
Coverage for src/engines/workflows/comfyui_workflows.py — Mission 023's
pure graph-construction functions. No network, no mocking needed: these
are plain functions returning dict, tested directly against their
output structure.
"""

import unittest

from src.engines.workflows.comfyui_workflows import (
    DEFAULT_IMG2IMG_DENOISE,
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


if __name__ == "__main__":
    unittest.main()
