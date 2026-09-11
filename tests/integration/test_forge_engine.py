"""
Coverage for src/engines/forge_engine.py — ForgeEngine's generic
Forge/A1111 protocol contract (discovery, generate_image()'s
txt2img/img2img dispatch, the <lora:...> syntax encapsulation, the
checkpoint override/restoration contract, and base64 decoding).
Entirely mocked: no network access, no real Forge instance, no GPU.
"""

import base64
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.engines.forge_engine import ForgeEngine, ForgeEngineError


class _FakeResponse:
    """Minimal stand-in for the object urllib.request.urlopen() returns."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


def _http_error(status: int, body: dict):
    return urllib.error.HTTPError(
        url="http://127.0.0.1:7860/sdapi/v1/txt2img",
        code=status,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(json.dumps(body).encode("utf-8")),
    )


class ForgeEngineConstructionTest(unittest.TestCase):

    def test_default_base_url_and_timeout(self):
        engine = ForgeEngine()
        self.assertEqual(engine._base_url, "http://127.0.0.1:7860")
        self.assertEqual(engine._timeout, 120.0)

    def test_explicit_base_url_and_timeout(self):
        engine = ForgeEngine(base_url="http://example.com:9999/", timeout=5.0)
        self.assertEqual(engine._base_url, "http://example.com:9999")
        self.assertEqual(engine._timeout, 5.0)


class ForgeEngineDiscoveryTest(unittest.TestCase):

    def setUp(self):
        self.engine = ForgeEngine()

    @patch("urllib.request.urlopen")
    def test_list_checkpoints_returns_titles(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps(
                [
                    {"title": "model_a.safetensors [abc123]", "model_name": "model_a"},
                    {"title": "model_b.safetensors [def456]", "model_name": "model_b"},
                ]
            ).encode("utf-8")
        )

        result = self.engine.list_checkpoints()

        self.assertEqual(result, ["model_a.safetensors [abc123]", "model_b.safetensors [def456]"])
        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/sd-models"))
        self.assertEqual(sent_request.get_method(), "GET")

    @patch("urllib.request.urlopen")
    def test_list_checkpoints_raises_on_http_failure(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, {"detail": "internal error"})

        with self.assertRaises(ForgeEngineError):
            self.engine.list_checkpoints()

    @patch("urllib.request.urlopen")
    def test_list_checkpoints_raises_on_malformed_shape(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"not": "a list"}).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.list_checkpoints()

    @patch("urllib.request.urlopen")
    def test_list_checkpoints_raises_when_entries_lack_title(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps([{"model_name": "model_a"}]).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.list_checkpoints()

    @patch("urllib.request.urlopen")
    def test_list_loras_returns_names(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps(
                [
                    {"name": "my_style", "alias": "my_style", "path": "J:\\...\\my_style.safetensors"},
                ]
            ).encode("utf-8")
        )

        result = self.engine.list_loras()

        self.assertEqual(result, ["my_style"])
        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/loras"))

    @patch("urllib.request.urlopen")
    def test_list_loras_raises_on_http_failure(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, {"detail": "internal error"})

        with self.assertRaises(ForgeEngineError):
            self.engine.list_loras()

    @patch("urllib.request.urlopen")
    def test_list_loras_raises_on_malformed_shape(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps("not a list").encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.list_loras()

    @patch("urllib.request.urlopen")
    def test_list_samplers_returns_names(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps([{"name": "Euler", "aliases": [], "options": {}}]).encode("utf-8")
        )

        result = self.engine.list_samplers()

        self.assertEqual(result, ["Euler"])
        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/samplers"))

    @patch("urllib.request.urlopen")
    def test_list_samplers_raises_on_http_failure(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, {"detail": "internal error"})

        with self.assertRaises(ForgeEngineError):
            self.engine.list_samplers()

    @patch("urllib.request.urlopen")
    def test_list_samplers_raises_on_malformed_shape(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps([{"aliases": []}]).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.list_samplers()

    @patch("urllib.request.urlopen")
    def test_list_schedulers_returns_names(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps([{"name": "Automatic", "label": "Automatic", "aliases": []}]).encode("utf-8")
        )

        result = self.engine.list_schedulers()

        self.assertEqual(result, ["Automatic"])
        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/schedulers"))

    @patch("urllib.request.urlopen")
    def test_list_schedulers_raises_on_http_failure(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, {"detail": "internal error"})

        with self.assertRaises(ForgeEngineError):
            self.engine.list_schedulers()

    @patch("urllib.request.urlopen")
    def test_list_schedulers_raises_on_malformed_shape(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps([{"label": "x"}]).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.list_schedulers()

    @patch("urllib.request.urlopen")
    def test_discovery_forwards_explicit_timeout(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps([]).encode("utf-8"))

        self.engine.list_samplers(timeout=5.0)

        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 5.0)


class ForgeEngineCheckConnectionTest(unittest.TestCase):
    """
    Mission 112: check_connection() is a thin wrapper around
    list_checkpoints() — same GET /sdapi/v1/sd-models call, same
    structural validation, no new HTTP path. A structurally valid
    response (empty checkpoint list included) is True; any failure
    already raised by list_checkpoints() propagates unchanged, never
    swallowed into a bare False.
    """

    def setUp(self):
        self.engine = ForgeEngine()

    @patch("urllib.request.urlopen")
    def test_returns_true_on_a_structurally_valid_response_with_checkpoints(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps([{"title": "model_a.safetensors [abc123]"}]).encode("utf-8")
        )

        self.assertTrue(self.engine.check_connection())

    @patch("urllib.request.urlopen")
    def test_returns_true_on_a_structurally_valid_response_with_zero_checkpoints(
        self, mock_urlopen
    ):
        # A reachable, correctly configured server exposing no
        # checkpoint yet must never be reported as unreachable.
        mock_urlopen.return_value = _FakeResponse(json.dumps([]).encode("utf-8"))

        self.assertTrue(self.engine.check_connection())

    @patch("urllib.request.urlopen")
    def test_propagates_forge_engine_error_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(ForgeEngineError):
            self.engine.check_connection()

    @patch("urllib.request.urlopen")
    def test_propagates_forge_engine_error_on_structurally_invalid_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"not": "a list"}).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.check_connection()

    @patch("urllib.request.urlopen")
    def test_forwards_a_custom_timeout_to_urlopen(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps([]).encode("utf-8"))

        self.engine.check_connection(timeout=5.0)

        self.assertEqual(mock_urlopen.call_args.kwargs.get("timeout"), 5.0)


class ForgeEngineUploadImageTest(unittest.TestCase):
    """
    Mission 107: upload_image() makes no network call at all (Forge's
    own API takes the reference inline) — it only validates the local
    file exists and wraps its path, the same "local filesystem
    precondition, not a protocol error" convention already used by
    ComfyUIEngine.upload_image().
    """

    def setUp(self):
        self.engine = ForgeEngine()
        self.tmp_dir = tempfile.mkdtemp()

    @patch("urllib.request.urlopen")
    def test_upload_image_makes_no_network_call(self, mock_urlopen):
        reference = Path(self.tmp_dir) / "ref.png"
        reference.write_bytes(b"\x89PNG\r\n\x1a\nfake")

        result = self.engine.upload_image(str(reference))

        self.assertEqual(result, {"path": str(reference)})
        mock_urlopen.assert_not_called()

    def test_upload_image_raises_uncaught_for_a_missing_file(self):
        missing = str(Path(self.tmp_dir) / "does-not-exist.png")

        with self.assertRaises(FileNotFoundError):
            self.engine.upload_image(missing)


class ForgeEngineTxt2ImgPayloadTest(unittest.TestCase):
    """
    Mission 107 (MISSION_107.md section 6, test list items 6/7/9):
    txt2img payload content — prompt/negative prompt, dimensions/
    steps/CFG, sampler/scheduler, seed, checkpoint (override_settings +
    restoration), and LoRA syntax encapsulation.
    """

    def setUp(self):
        self.engine = ForgeEngine()
        self.tmp_dir = tempfile.mkdtemp()

    def _respond_with(self, mock_urlopen, images):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": images}).encode("utf-8"))

    def _one_pixel_png_base64(self) -> str:
        # A real, minimal 1x1 PNG, base64-encoded — exercises the real
        # decode path rather than an opaque placeholder string.
        return base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
                "de0000000c4944415408d763f8cfc0c0c00004000104010a30d47f0000000049"
                "454e44ae426082"
            )
        ).decode("ascii")

    @patch("urllib.request.urlopen")
    def test_txt2img_endpoint_is_used_without_a_reference(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir)

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/txt2img"))
        self.assertEqual(sent_request.get_method(), "POST")

    @patch("urllib.request.urlopen")
    def test_txt2img_payload_carries_every_generation_parameter(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image(
            "a fox",
            self.tmp_dir,
            width=768,
            height=1024,
            steps=33,
            cfg=6.5,
            sampler_name="DPM++ 2M",
            scheduler="Karras",
            seed=999,
            negative_prompt="ugly",
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox")
        self.assertEqual(payload["negative_prompt"], "ugly")
        self.assertEqual(payload["width"], 768)
        self.assertEqual(payload["height"], 1024)
        self.assertEqual(payload["steps"], 33)
        self.assertEqual(payload["cfg_scale"], 6.5)
        self.assertEqual(payload["sampler_name"], "DPM++ 2M")
        self.assertEqual(payload["scheduler"], "Karras")
        self.assertEqual(payload["seed"], 999)

    @patch("urllib.request.urlopen")
    def test_omitted_seed_is_sent_as_minus_one(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["seed"], -1)

    @patch("urllib.request.urlopen")
    def test_omitted_scheduler_is_never_sent(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertNotIn("scheduler", payload)

    @patch("urllib.request.urlopen")
    def test_omitted_checkpoint_never_sends_override_settings(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertNotIn("override_settings", payload)
        self.assertNotIn("override_settings_restore_afterwards", payload)

    @patch("urllib.request.urlopen")
    def test_checkpoint_uses_override_settings_with_restoration_enabled(self, mock_urlopen):
        # Mission 107, explicit architect constraint: a per-call
        # checkpoint must never durably change Forge's global
        # checkpoint. Verified against the real installed Forge source
        # (modules/processing.py::process_images()) that
        # override_settings + override_settings_restore_afterwards=True
        # is the native mechanism guaranteeing this — never
        # /sdapi/v1/options, which would persist beyond this request.
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir, checkpoint_name="my_checkpoint.safetensors")

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/txt2img"))
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(
            payload["override_settings"], {"sd_model_checkpoint": "my_checkpoint.safetensors"}
        )
        self.assertIs(payload["override_settings_restore_afterwards"], True)

    @patch("urllib.request.urlopen")
    def test_checkpoint_never_reaches_sdapi_options(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir, checkpoint_name="my_checkpoint.safetensors")

        for call in mock_urlopen.call_args_list:
            sent_request = call[0][0]
            self.assertNotIn("/sdapi/v1/options", sent_request.full_url)

    @patch("urllib.request.urlopen")
    def test_lora_is_appended_to_the_prompt_never_a_separate_field(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image(
            "a fox", self.tmp_dir, lora_name="my_style", lora_strength=0.8
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:my_style:0.8>")
        self.assertNotIn("lora", payload)
        self.assertNotIn("lora_name", payload)
        self.assertNotIn("loras", payload)

    @patch("urllib.request.urlopen")
    def test_empty_lora_name_never_appends_any_syntax(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir, lora_name="")

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox")

    # --- Mission 108 real-smoke correction: LoRA name normalization to
    # Forge's own <lora:name:weight> convention (bare basename, no
    # subfolder, no extension) — verified against the installed Forge's
    # own extra_networks_lora.py/networks.py, see _forge_lora_tag_name()'s
    # own docstring for the full evidence chain. ---

    @patch("urllib.request.urlopen")
    def test_lora_name_with_windows_subfolder_and_extension_is_normalized(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image(
            "a fox",
            self.tmp_dir,
            lora_name="AIStudioToolkit\\my_lora__37ca771a.safetensors",
            lora_strength=1.0,
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:my_lora__37ca771a:1.0>")

    @patch("urllib.request.urlopen")
    def test_lora_name_with_forward_slash_subfolder_and_extension_is_normalized(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image(
            "a fox",
            self.tmp_dir,
            lora_name="AIStudioToolkit/my_lora__37ca771a.safetensors",
            lora_strength=1.0,
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:my_lora__37ca771a:1.0>")

    @patch("urllib.request.urlopen")
    def test_lora_name_without_subfolder_or_extension_is_left_unchanged(self, mock_urlopen):
        # Non-regression: the pre-existing Mission 107 test above already
        # covers this exact shape ("my_style") — this test makes the
        # invariant explicit under the new normalization helper's own
        # name, so a future change to it cannot silently reintroduce a
        # subfolder/extension assumption without this test also failing.
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image("a fox", self.tmp_dir, lora_name="my_style", lora_strength=0.8)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:my_style:0.8>")

    @patch("urllib.request.urlopen")
    def test_lora_name_with_spaces_hyphens_and_underscores_is_preserved(self, mock_urlopen):
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image(
            "a fox",
            self.tmp_dir,
            lora_name="AIStudioToolkit\\Zaraya Koyah-SDX_v2.safetensors",
            lora_strength=0.5,
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:Zaraya Koyah-SDX_v2:0.5>")

    @patch("urllib.request.urlopen")
    def test_lora_name_with_a_different_forge_supported_extension_is_normalized(self, mock_urlopen):
        # Forge's own process_network_files() accepts .pt/.ckpt/.safetensors
        # — the normalization must be extension-agnostic, not hardcoded to
        # ".safetensors".
        self._respond_with(mock_urlopen, [self._one_pixel_png_base64()])

        self.engine.generate_image(
            "a fox",
            self.tmp_dir,
            lora_name="AIStudioToolkit\\legacy_lora.pt",
            lora_strength=1.0,
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:legacy_lora:1.0>")


class ForgeEngineImg2ImgPayloadTest(unittest.TestCase):
    """
    Mission 107 (test list items 8/14/15): the img2img path — endpoint
    selection, init_images encoding, denoise/denoising_strength
    forwarding.
    """

    def setUp(self):
        self.engine = ForgeEngine()
        self.tmp_dir = tempfile.mkdtemp()
        self.reference_path = Path(self.tmp_dir) / "reference.png"
        self.reference_bytes = b"\x89PNG\r\n\x1a\nfake-reference-bytes"
        self.reference_path.write_bytes(self.reference_bytes)

    def test_generate_image_parameter_is_named_denoise_not_denoising_strength(self):
        # Architect's explicit correction: the Python-facing parameter
        # must match ComfyUIEngine.generate_image()'s own "denoise"
        # name exactly, so GenerationManager never has to know which
        # engine it is calling — only this method's own internal
        # payload construction uses Forge's native wire field name.
        import inspect

        signature = inspect.signature(ForgeEngine.generate_image)
        self.assertIn("denoise", signature.parameters)
        self.assertNotIn("denoising_strength", signature.parameters)

    def _respond_with(self, mock_urlopen, images):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": images}).encode("utf-8"))

    @patch("urllib.request.urlopen")
    def test_img2img_endpoint_is_used_when_a_reference_is_present(self, mock_urlopen):
        self._respond_with(mock_urlopen, [base64.b64encode(b"output-bytes").decode("ascii")])
        reference = self.engine.upload_image(str(self.reference_path))

        self.engine.generate_image("a fox", self.tmp_dir, reference_image=reference)

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/img2img"))

    @patch("urllib.request.urlopen")
    def test_reference_is_encoded_as_base64_in_init_images(self, mock_urlopen):
        self._respond_with(mock_urlopen, [base64.b64encode(b"output-bytes").decode("ascii")])
        reference = self.engine.upload_image(str(self.reference_path))

        self.engine.generate_image("a fox", self.tmp_dir, reference_image=reference)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(len(payload["init_images"]), 1)
        decoded = base64.b64decode(payload["init_images"][0])
        self.assertEqual(decoded, self.reference_bytes)

    @patch("urllib.request.urlopen")
    def test_lora_name_is_normalized_on_the_img2img_path_too(self, mock_urlopen):
        # Mission 108 real-smoke correction: _apply_lora_syntax() runs
        # once, before the txt2img/img2img endpoint branch — this proves
        # the normalization applies uniformly to both, not just txt2img.
        self._respond_with(mock_urlopen, [base64.b64encode(b"output-bytes").decode("ascii")])
        reference = self.engine.upload_image(str(self.reference_path))

        self.engine.generate_image(
            "a fox",
            self.tmp_dir,
            reference_image=reference,
            lora_name="AIStudioToolkit\\my_lora__37ca771a.safetensors",
            lora_strength=1.0,
        )

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/sdapi/v1/img2img"))
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["prompt"], "a fox <lora:my_lora__37ca771a:1.0>")

    @patch("urllib.request.urlopen")
    def test_denoise_parameter_is_translated_to_forges_native_wire_field(self, mock_urlopen):
        # Mission 107 (architect's explicit correction): the Python
        # parameter is named "denoise" — identically to
        # ComfyUIEngine.generate_image()'s own parameter — so
        # GenerationManager never needs to know which engine it is
        # calling. Only the JSON payload sent over the wire uses
        # Forge's own native field name, "denoising_strength".
        self._respond_with(mock_urlopen, [base64.b64encode(b"output-bytes").decode("ascii")])
        reference = self.engine.upload_image(str(self.reference_path))

        self.engine.generate_image(
            "a fox", self.tmp_dir, reference_image=reference, denoise=0.3
        )

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["denoising_strength"], 0.3)
        self.assertNotIn("denoise", payload)

    @patch("urllib.request.urlopen")
    def test_default_denoising_strength_matches_forges_own_default(self, mock_urlopen):
        self._respond_with(mock_urlopen, [base64.b64encode(b"output-bytes").decode("ascii")])
        reference = self.engine.upload_image(str(self.reference_path))

        self.engine.generate_image("a fox", self.tmp_dir, reference_image=reference)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(payload["denoising_strength"], 0.75)

    @patch("urllib.request.urlopen")
    def test_no_reference_never_sends_init_images_or_denoising_strength(self, mock_urlopen):
        self._respond_with(mock_urlopen, [base64.b64encode(b"output-bytes").decode("ascii")])

        self.engine.generate_image("a fox", self.tmp_dir)

        sent_request = mock_urlopen.call_args[0][0]
        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertNotIn("init_images", payload)
        self.assertNotIn("denoising_strength", payload)


class ForgeEngineResponseDecodingTest(unittest.TestCase):
    """
    Mission 107 (test list items 9/13): decoding the response's base64
    image(s), robust to an optional data:image/...;base64, prefix,
    writing the result to output_directory and returning its path.
    """

    def setUp(self):
        self.engine = ForgeEngine()
        self.tmp_dir = tempfile.mkdtemp()

    @patch("urllib.request.urlopen")
    def test_raw_base64_response_is_decoded_and_written_to_disk(self, mock_urlopen):
        image_bytes = b"\x89PNG\r\n\x1a\nsome-png-bytes"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": [encoded]}).encode("utf-8"))

        path = self.engine.generate_image("a fox", self.tmp_dir)

        self.assertTrue(Path(path).is_file())
        self.assertEqual(Path(path).read_bytes(), image_bytes)
        self.assertTrue(path.startswith(self.tmp_dir))

    @patch("urllib.request.urlopen")
    def test_data_uri_prefixed_response_is_decoded_correctly(self, mock_urlopen):
        image_bytes = b"\x89PNG\r\n\x1a\nsome-png-bytes"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        prefixed = f"data:image/png;base64,{encoded}"
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": [prefixed]}).encode("utf-8"))

        path = self.engine.generate_image("a fox", self.tmp_dir)

        self.assertEqual(Path(path).read_bytes(), image_bytes)

    @patch("urllib.request.urlopen")
    def test_written_file_extension_matches_the_real_png_signature(self, mock_urlopen):
        image_bytes = b"\x89PNG\r\n\x1a\nsome-png-bytes"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": [encoded]}).encode("utf-8"))

        path = self.engine.generate_image("a fox", self.tmp_dir)

        self.assertTrue(path.endswith(".png"))

    @patch("urllib.request.urlopen")
    def test_written_file_extension_matches_a_jpeg_signature(self, mock_urlopen):
        image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": [encoded]}).encode("utf-8"))

        path = self.engine.generate_image("a fox", self.tmp_dir)

        self.assertTrue(path.endswith(".jpg"))

    @patch("urllib.request.urlopen")
    def test_only_the_first_image_is_used_when_several_are_returned(self, mock_urlopen):
        first = base64.b64encode(b"\x89PNG\r\n\x1a\nfirst").decode("ascii")
        second = base64.b64encode(b"\x89PNG\r\n\x1a\nsecond").decode("ascii")
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"images": [first, second]}).encode("utf-8")
        )

        path = self.engine.generate_image("a fox", self.tmp_dir)

        self.assertEqual(Path(path).read_bytes(), b"\x89PNG\r\n\x1a\nfirst")


class ForgeEngineErrorHandlingTest(unittest.TestCase):
    """
    Mission 107 (test list items 10/11): HTTP failures and malformed/
    invalid Forge responses always raise ForgeEngineError, never a bare
    propagation of the underlying exception.
    """

    def setUp(self):
        self.engine = ForgeEngine()
        self.tmp_dir = tempfile.mkdtemp()

    @patch("urllib.request.urlopen")
    def test_connection_refused_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_timeout_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_non_2xx_http_status_raises_forge_engine_error_with_detail(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(422, {"detail": "invalid sampler_name"})

        with self.assertRaisesRegex(ForgeEngineError, "invalid sampler_name"):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_invalid_json_response_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"not json at all")

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_response_missing_images_key_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"info": "{}"}).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_response_with_empty_images_list_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"images": []}).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_response_that_is_not_an_object_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps([1, 2, 3]).encode("utf-8"))

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_invalid_base64_image_raises_forge_engine_error(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"images": ["not-valid-base64!!!"]}).encode("utf-8")
        )

        with self.assertRaises(ForgeEngineError):
            self.engine.generate_image("a fox", self.tmp_dir)


if __name__ == "__main__":
    unittest.main()
