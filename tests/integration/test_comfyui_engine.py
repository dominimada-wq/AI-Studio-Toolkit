"""
Coverage for src/engines/comfyui_engine.py — ComfyUIEngine's generic
ComfyUI protocol contract (submit/wait_for_result/download_output/
upload_image, the last added Mission 021), its generate_image()
convenience method, and the architectural properties required by
Mission 012 (no Domain import, no provider-specific knowledge in the
generic contract). Entirely mocked: no network access, no real
ComfyUI instance, no GPU.
"""

import inspect
import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.engines import comfyui_engine
from src.engines.comfyui_engine import (
    ComfyUIEngine,
    ComfyUIEngineError,
    build_demo_workflow,
)


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
        url="http://127.0.0.1:8188/prompt",
        code=status,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(json.dumps(body).encode("utf-8")),
    )


class ComfyUIEngineSubmitTest(unittest.TestCase):

    def setUp(self):
        self.engine = ComfyUIEngine()

    @patch("urllib.request.urlopen")
    def test_submit_returns_prompt_id_on_success(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"prompt_id": "abc-123", "number": 1, "node_errors": {}}).encode("utf-8")
        )

        prompt_id = self.engine.submit({"1": {"class_type": "Foo", "inputs": {}}}, "client-1")

        self.assertEqual(prompt_id, "abc-123")

        # The request actually sent must carry the exact body ComfyUI's
        # /prompt endpoint expects: {"prompt": <workflow>, "client_id": ...}.
        sent_request = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(sent_body["client_id"], "client-1")
        self.assertEqual(sent_body["prompt"], {"1": {"class_type": "Foo", "inputs": {}}})
        self.assertTrue(sent_request.full_url.endswith("/prompt"))

    @patch("urllib.request.urlopen")
    def test_submit_does_not_mutate_the_workflow_it_is_given(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"prompt_id": "abc-123", "number": 1, "node_errors": {}}).encode("utf-8")
        )
        workflow = {
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "whatever.safetensors"}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox"}},
        }
        original = json.loads(json.dumps(workflow))  # deep copy, independent of the object below

        self.engine.submit(workflow, "client-1")

        self.assertEqual(workflow, original, "submit() must treat the workflow as opaque and never edit it")

    @patch("urllib.request.urlopen")
    def test_submit_raises_when_workflow_rejected(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(
            400, {"error": {"message": "invalid prompt"}, "node_errors": {"4": {}}}
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.submit({"1": {"class_type": "Foo", "inputs": {}}}, "client-1")

    @patch("urllib.request.urlopen")
    def test_submit_raises_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(ComfyUIEngineError):
            self.engine.submit({"1": {"class_type": "Foo", "inputs": {}}}, "client-1")

    @patch("urllib.request.urlopen")
    def test_submit_raises_on_invalid_json_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"not json")

        with self.assertRaises(ComfyUIEngineError):
            self.engine.submit({"1": {"class_type": "Foo", "inputs": {}}}, "client-1")


class ComfyUIEngineWaitForResultTest(unittest.TestCase):

    def setUp(self):
        self.engine = ComfyUIEngine(timeout=5.0)

    @patch("urllib.request.urlopen")
    def test_wait_for_result_returns_outputs_when_already_ready(self, mock_urlopen):
        history = {
            "abc-123": {
                "outputs": {
                    "9": {"images": [{"filename": "img.png", "subfolder": "", "type": "output"}]}
                }
            }
        }
        mock_urlopen.return_value = _FakeResponse(json.dumps(history).encode("utf-8"))

        outputs = self.engine.wait_for_result("abc-123", poll_interval=0.01)

        self.assertEqual(outputs["9"]["images"][0]["filename"], "img.png")

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_wait_for_result_polls_until_ready(self, mock_urlopen, mock_sleep):
        not_ready = _FakeResponse(json.dumps({}).encode("utf-8"))
        ready = _FakeResponse(
            json.dumps(
                {"abc-123": {"outputs": {"9": {"images": [{"filename": "img.png"}]}}}}
            ).encode("utf-8")
        )
        mock_urlopen.side_effect = [not_ready, ready]

        outputs = self.engine.wait_for_result("abc-123", poll_interval=0.01)

        self.assertEqual(outputs["9"]["images"][0]["filename"], "img.png")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(0.01)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_wait_for_result_times_out_without_result(self, mock_urlopen, mock_sleep):
        mock_urlopen.return_value = _FakeResponse(json.dumps({}).encode("utf-8"))
        engine = ComfyUIEngine(timeout=0.0)

        with self.assertRaises(ComfyUIEngineError):
            engine.wait_for_result("abc-123", poll_interval=0.01)

    @patch("urllib.request.urlopen")
    def test_wait_for_result_raises_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(ComfyUIEngineError):
            self.engine.wait_for_result("abc-123", poll_interval=0.01)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_wait_for_result_does_not_stop_on_outputs_without_images_key(self, mock_urlopen, mock_sleep):
        # A node ran and produced *some* output, but none of it is an
        # image (e.g. a non-image node, or the image step hasn't
        # landed in this history snapshot) — must not be treated as
        # a finished, exploitable result.
        not_yet_exploitable = _FakeResponse(
            json.dumps({"abc-123": {"outputs": {"3": {"latents": ["something"]}}}}).encode("utf-8")
        )
        ready = _FakeResponse(
            json.dumps(
                {"abc-123": {"outputs": {"9": {"images": [{"filename": "img.png"}]}}}}
            ).encode("utf-8")
        )
        mock_urlopen.side_effect = [not_yet_exploitable, ready]

        outputs = self.engine.wait_for_result("abc-123", poll_interval=0.01)

        self.assertEqual(outputs["9"]["images"][0]["filename"], "img.png")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_wait_for_result_does_not_stop_on_empty_images_list(self, mock_urlopen, mock_sleep):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"abc-123": {"outputs": {"9": {"images": []}}}}).encode("utf-8")
        )
        engine = ComfyUIEngine(timeout=0.0)

        with self.assertRaises(ComfyUIEngineError):
            engine.wait_for_result("abc-123", poll_interval=0.01)

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_wait_for_result_does_not_stop_on_image_reference_missing_filename(self, mock_urlopen, mock_sleep):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps(
                {"abc-123": {"outputs": {"9": {"images": [{"subfolder": "", "type": "output"}]}}}}
            ).encode("utf-8")
        )
        engine = ComfyUIEngine(timeout=0.0)

        with self.assertRaises(ComfyUIEngineError):
            engine.wait_for_result("abc-123", poll_interval=0.01)


class ComfyUIEngineDownloadOutputTest(unittest.TestCase):

    def setUp(self):
        self.engine = ComfyUIEngine()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    @patch("urllib.request.urlopen")
    def test_download_output_writes_file_and_returns_path(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"fake-image-bytes")

        path = self.engine.download_output("img.png", "", "output", self.tmp_dir)

        self.assertEqual(Path(path), Path(self.tmp_dir) / "img.png")
        self.assertEqual(Path(path).read_bytes(), b"fake-image-bytes")

        sent_request = mock_urlopen.call_args[0][0]
        self.assertIn("filename=img.png", sent_request.full_url)
        self.assertIn("type=output", sent_request.full_url)

    @patch("urllib.request.urlopen")
    def test_download_output_raises_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(ComfyUIEngineError):
            self.engine.download_output("img.png", "", "output", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_download_output_raises_on_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(404, {"error": "not found"})

        with self.assertRaises(ComfyUIEngineError):
            self.engine.download_output("missing.png", "", "output", self.tmp_dir)

    @patch("urllib.request.urlopen")
    def test_download_output_url_encodes_special_characters(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"bytes")

        path = self.engine.download_output(
            "my image (1).png", "café / sub", "output", self.tmp_dir
        )

        # The request sent to ComfyUI must carry percent-encoded query
        # values — a raw space or "/" in a query parameter would be
        # ambiguous/invalid.
        sent_request = mock_urlopen.call_args[0][0]
        self.assertIn("filename=my+image+%281%29.png", sent_request.full_url)
        self.assertIn("subfolder=caf%C3%A9+%2F+sub", sent_request.full_url)

        # The local file, however, is written under the exact original
        # (unencoded) filename — no percent-encoding leaks into the
        # filesystem path.
        self.assertEqual(Path(path), Path(self.tmp_dir) / "my image (1).png")
        self.assertEqual(Path(path).read_bytes(), b"bytes")

    @patch("urllib.request.urlopen")
    def test_download_output_writes_bytes_without_any_transformation(self, mock_urlopen):
        # Arbitrary, non-image-like bytes: download_output must not
        # attempt to decode, validate, or reinterpret the payload in
        # any way — it is agnostic to the image format/origin.
        raw_bytes = bytes(range(256))
        mock_urlopen.return_value = _FakeResponse(raw_bytes)

        path = self.engine.download_output("raw.bin", "", "output", self.tmp_dir)

        self.assertEqual(Path(path).read_bytes(), raw_bytes)


class ComfyUIEngineUploadImageTest(unittest.TestCase):
    """
    Mission 021: upload_image() is a pure transport primitive — these
    tests deliberately never attach any semantic role (identity,
    clothing, environment, pose...) to an uploaded image; that concept
    does not exist yet anywhere in the codebase. The independence test
    at the end exists specifically to demonstrate the property a future
    1..N-image orchestration will rely on: no state survives between
    calls.
    """

    def setUp(self):
        self.engine = ComfyUIEngine()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.image_path = str(Path(self.tmp_dir) / "portrait.png")
        Path(self.image_path).write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")

    @staticmethod
    def _success_response(name="portrait.png", subfolder="", type_="input"):
        return _FakeResponse(
            json.dumps({"name": name, "subfolder": subfolder, "type": type_}).encode("utf-8")
        )

    @patch("urllib.request.urlopen")
    def test_upload_image_returns_structured_response_on_success(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response(
            name="portrait.png", subfolder="characters", type_="input"
        )

        result = self.engine.upload_image(self.image_path, subfolder="characters")

        self.assertEqual(
            result, {"name": "portrait.png", "subfolder": "characters", "type": "input"}
        )

    @patch("urllib.request.urlopen")
    def test_upload_image_posts_multipart_to_upload_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response()

        self.engine.upload_image(self.image_path)

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/upload/image"))
        content_type_header = sent_request.get_header("Content-type")
        self.assertTrue(content_type_header.startswith("multipart/form-data; boundary="))

    @patch("urllib.request.urlopen")
    def test_upload_image_carries_exact_filename_and_bytes(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response()
        raw_bytes = Path(self.image_path).read_bytes()

        self.engine.upload_image(self.image_path)

        body = mock_urlopen.call_args[0][0].data
        self.assertIn(b'filename="portrait.png"', body)
        self.assertIn(raw_bytes, body)

    @patch("urllib.request.urlopen")
    def test_upload_image_sends_type_input(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response()

        self.engine.upload_image(self.image_path)

        body = mock_urlopen.call_args[0][0].data
        self.assertIn(b'name="type"', body)
        self.assertIn(b"\r\n\r\ninput\r\n", body)

    @patch("urllib.request.urlopen")
    def test_upload_image_forwards_subfolder_in_request_and_return_value(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response(subfolder="characters/alice")

        result = self.engine.upload_image(self.image_path, subfolder="characters/alice")

        body = mock_urlopen.call_args[0][0].data
        self.assertIn(b'name="subfolder"', body)
        self.assertIn(b"characters/alice", body)
        self.assertEqual(result["subfolder"], "characters/alice")

    @patch("urllib.request.urlopen")
    def test_upload_image_overwrite_true_sends_overwrite_field(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response()

        self.engine.upload_image(self.image_path, overwrite=True)

        body = mock_urlopen.call_args[0][0].data
        self.assertIn(b'name="overwrite"', body)
        self.assertIn(b"\r\n\r\ntrue\r\n", body)

    @patch("urllib.request.urlopen")
    def test_upload_image_overwrite_false_omits_overwrite_field(self, mock_urlopen):
        mock_urlopen.return_value = self._success_response()

        self.engine.upload_image(self.image_path, overwrite=False)

        body = mock_urlopen.call_args[0][0].data
        self.assertNotIn(b'name="overwrite"', body)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_name_missing(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"subfolder": "", "type": "input"}).encode("utf-8")
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_name_is_empty_string(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"name": "", "subfolder": "", "type": "input"}).encode("utf-8")
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_subfolder_missing(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"name": "portrait.png", "type": "input"}).encode("utf-8")
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_subfolder_is_not_a_string(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"name": "portrait.png", "subfolder": 123, "type": "input"}).encode("utf-8")
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_type_missing(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"name": "portrait.png", "subfolder": ""}).encode("utf-8")
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_type_is_empty_string(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"name": "portrait.png", "subfolder": "", "type": ""}).encode("utf-8")
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_on_invalid_json_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"not json")

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_on_http_error_with_empty_body(self, mock_urlopen):
        # The real ComfyUI /upload/image endpoint returns a bare 400
        # with no JSON body for a missing file field or a path
        # traversal attempt — verified against server.py's
        # image_upload().
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://127.0.0.1:8188/upload/image",
            code=400,
            msg="error",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_raises_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(ComfyUIEngineError):
            self.engine.upload_image(self.image_path)

    def test_upload_image_raises_file_not_found_error_uncaught_for_missing_local_file(self):
        # Local filesystem precondition, not a ComfyUI protocol error —
        # same convention already used by download_output() for a
        # missing/unwritable output_directory. Must never be wrapped
        # into ComfyUIEngineError.
        missing_path = str(Path(self.tmp_dir) / "does_not_exist.png")

        with self.assertRaises(FileNotFoundError):
            self.engine.upload_image(missing_path)

    @patch("urllib.request.urlopen")
    def test_upload_image_two_independent_calls_produce_two_independent_results(self, mock_urlopen):
        # Demonstrates the property a future 1..N-image orchestration
        # will rely on: ComfyUIEngine keeps no upload-related state on
        # self, so two calls for two different local images (no role
        # concept involved) never interfere with each other.
        second_image_path = str(Path(self.tmp_dir) / "outfit.png")
        Path(second_image_path).write_bytes(b"different-bytes-for-second-image")

        mock_urlopen.side_effect = [
            self._success_response(name="portrait.png", subfolder="", type_="input"),
            self._success_response(name="outfit.png", subfolder="clothing", type_="input"),
        ]

        first_result = self.engine.upload_image(self.image_path)
        second_result = self.engine.upload_image(second_image_path, subfolder="clothing")

        self.assertEqual(
            first_result, {"name": "portrait.png", "subfolder": "", "type": "input"}
        )
        self.assertEqual(
            second_result, {"name": "outfit.png", "subfolder": "clothing", "type": "input"}
        )

        first_body = mock_urlopen.call_args_list[0][0][0].data
        second_body = mock_urlopen.call_args_list[1][0][0].data
        self.assertIn(b'filename="portrait.png"', first_body)
        self.assertIn(b'filename="outfit.png"', second_body)
        self.assertNotEqual(first_body, second_body)


class ComfyUIEngineGenerateImageTest(unittest.TestCase):

    def setUp(self):
        self.engine = ComfyUIEngine()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    @patch("urllib.request.urlopen")
    def test_generate_image_full_flow_returns_downloaded_path(self, mock_urlopen):
        submit_response = _FakeResponse(
            json.dumps({"prompt_id": "abc-123", "number": 1, "node_errors": {}}).encode("utf-8")
        )
        history_response = _FakeResponse(
            json.dumps(
                {
                    "abc-123": {
                        "outputs": {
                            "9": {
                                "images": [
                                    {"filename": "result.png", "subfolder": "", "type": "output"}
                                ]
                            }
                        }
                    }
                }
            ).encode("utf-8")
        )
        view_response = _FakeResponse(b"generated-image-bytes")
        mock_urlopen.side_effect = [submit_response, history_response, view_response]

        path = self.engine.generate_image("a red fox in a forest", self.tmp_dir)

        self.assertEqual(Path(path), Path(self.tmp_dir) / "result.png")
        self.assertEqual(Path(path).read_bytes(), b"generated-image-bytes")

        # The prompt text actually reaches the submitted workflow.
        submit_call_request = mock_urlopen.call_args_list[0][0][0]
        submitted_body = json.loads(submit_call_request.data.decode("utf-8"))
        self.assertEqual(submitted_body["prompt"]["6"]["inputs"]["text"], "a red fox in a forest")

    @patch("urllib.request.urlopen")
    def test_generate_image_forwards_checkpoint_name_override(self, mock_urlopen):
        submit_response = _FakeResponse(
            json.dumps({"prompt_id": "abc-123", "number": 1, "node_errors": {}}).encode("utf-8")
        )
        history_response = _FakeResponse(
            json.dumps(
                {"abc-123": {"outputs": {"9": {"images": [{"filename": "r.png"}]}}}}
            ).encode("utf-8")
        )
        view_response = _FakeResponse(b"bytes")
        mock_urlopen.side_effect = [submit_response, history_response, view_response]

        self.engine.generate_image(
            "a fox", self.tmp_dir, checkpoint_name="v1-5-pruned-emaonly-fp16.safetensors"
        )

        submit_call_request = mock_urlopen.call_args_list[0][0][0]
        submitted_body = json.loads(submit_call_request.data.decode("utf-8"))
        self.assertEqual(
            submitted_body["prompt"]["4"]["inputs"]["ckpt_name"],
            "v1-5-pruned-emaonly-fp16.safetensors",
        )

    @patch("time.sleep")
    @patch("urllib.request.urlopen")
    def test_generate_image_raises_when_no_image_ever_appears(self, mock_urlopen, mock_sleep):
        # wait_for_result() must never treat "outputs" without an
        # exploitable image as a finished result (see
        # ComfyUIEngineWaitForResultTest) — so with a history that
        # never carries an image, generate_image() ultimately fails
        # via wait_for_result()'s timeout, not via an early "no image"
        # short-circuit after a single poll.
        submit_response = _FakeResponse(
            json.dumps({"prompt_id": "abc-123", "number": 1, "node_errors": {}}).encode("utf-8")
        )
        no_image_response = _FakeResponse(json.dumps({"abc-123": {"outputs": {"9": {}}}}).encode("utf-8"))
        mock_urlopen.side_effect = [submit_response] + [no_image_response] * 5

        engine = ComfyUIEngine(timeout=0.0)

        with self.assertRaises(ComfyUIEngineError):
            engine.generate_image("a red fox in a forest", self.tmp_dir)


class ComfyUIEngineArchitecturalConstraintsTest(unittest.TestCase):
    """
    Mission 012's explicit architectural requirements: ComfyUIEngine
    must import no src.domain object, and its generic contract
    (everything except the clearly-separated demo workflow builder)
    must carry no knowledge of any particular model or provider.
    """

    def test_module_does_not_import_domain(self):
        source = Path(comfyui_engine.__file__).read_text(encoding="utf-8")
        import_lines = [line.strip() for line in source.splitlines() if "domain" in line.lower()]
        offending = [
            line for line in import_lines if line.startswith("import ") or line.startswith("from ")
        ]
        self.assertEqual(offending, [])

    def test_generic_primitives_carry_no_provider_specific_parameters(self):
        # __init__/submit/wait_for_result/download_output are the true
        # generic contract (Mission 012). generate_image() is
        # deliberately excluded here: Mission 013 gave it an optional
        # checkpoint_name (see test_checkpoint_name_is_forwardable_to_
        # generate_image below) precisely because a real integration
        # demonstrated the need — it stays a convenience method, not
        # part of the generic contract these primitives define.
        forbidden_terms = ("checkpoint", "sdxl", "flux", "lora", "gemini", "gpt", "nano_banana")

        for method_name in ("__init__", "submit", "wait_for_result", "download_output"):
            signature = inspect.signature(getattr(ComfyUIEngine, method_name))
            parameter_names = " ".join(signature.parameters.keys()).lower()
            for term in forbidden_terms:
                self.assertNotIn(
                    term,
                    parameter_names,
                    f"{method_name}() must not reference '{term}' — that belongs to the demo workflow only",
                )

    def test_checkpoint_name_is_isolated_to_the_demo_workflow_builder(self):
        signature = inspect.signature(build_demo_workflow)
        self.assertIn("checkpoint_name", signature.parameters)

    def test_checkpoint_name_is_forwardable_to_generate_image(self):
        # Mission 013: a real ComfyUI installation does not necessarily
        # have a checkpoint under DEMO_CHECKPOINT_NAME's exact default
        # name (confirmed empirically, Mission 012's post-release smoke
        # test) — generate_image() must let a caller override it,
        # additively and backward-compatibly (a default is still
        # provided).
        signature = inspect.signature(ComfyUIEngine.generate_image)
        self.assertIn("checkpoint_name", signature.parameters)
        self.assertEqual(
            signature.parameters["checkpoint_name"].default,
            comfyui_engine.DEMO_CHECKPOINT_NAME,
        )

    def test_generic_primitives_never_reference_the_demo_workflow(self):
        forbidden_terms = ("build_demo_workflow", "checkpoint", "demo_checkpoint_name")

        for method_name in ("submit", "wait_for_result", "download_output"):
            body = inspect.getsource(getattr(ComfyUIEngine, method_name)).lower()
            for term in forbidden_terms:
                self.assertNotIn(
                    term,
                    body,
                    f"{method_name}() must stay independent from the Mission 012 demo workflow",
                )

        # Only generate_image() — the convenience method — is allowed
        # to know about the demo workflow.
        generate_image_body = inspect.getsource(ComfyUIEngine.generate_image).lower()
        self.assertIn("build_demo_workflow", generate_image_body)


if __name__ == "__main__":
    unittest.main()
