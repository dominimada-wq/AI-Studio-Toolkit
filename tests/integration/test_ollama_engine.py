"""
Coverage for src/engines/ollama_engine.py — OllamaEngine's minimal
protocol contract (list_models/generate_text, Mission 030), verified
against the official Ollama API documentation. Entirely mocked: no
network access, no real Ollama instance.
"""

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from src.engines.ai_backend import AIBackend, AIBackendError, AIModelInfo
from src.engines.ollama_engine import OllamaEngine


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
        url="http://127.0.0.1:11434/api/generate",
        code=status,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(json.dumps(body).encode("utf-8")),
    )


class OllamaEngineListModelsTest(unittest.TestCase):

    def setUp(self):
        self.engine = OllamaEngine()

    @staticmethod
    def _tags_response(models):
        return _FakeResponse(json.dumps({"models": models}).encode("utf-8"))

    @patch("urllib.request.urlopen")
    def test_list_models_returns_multiple_models(self, mock_urlopen):
        mock_urlopen.return_value = self._tags_response(
            [{"name": "llama3.2:latest"}, {"name": "mistral:latest"}]
        )

        models = self.engine.list_models()

        self.assertEqual(
            models, [AIModelInfo(name="llama3.2:latest"), AIModelInfo(name="mistral:latest")]
        )

    @patch("urllib.request.urlopen")
    def test_list_models_returns_single_model(self, mock_urlopen):
        mock_urlopen.return_value = self._tags_response([{"name": "only:latest"}])

        models = self.engine.list_models()

        self.assertEqual(models, [AIModelInfo(name="only:latest")])

    @patch("urllib.request.urlopen")
    def test_list_models_returns_empty_list_when_none_installed(self, mock_urlopen):
        mock_urlopen.return_value = self._tags_response([])

        models = self.engine.list_models()

        self.assertEqual(models, [])

    @patch("urllib.request.urlopen")
    def test_list_models_sends_get_request_to_tags_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = self._tags_response([{"name": "a"}])

        self.engine.list_models()

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/api/tags"))
        self.assertEqual(sent_request.get_method(), "GET")

    @patch("urllib.request.urlopen")
    def test_list_models_ignores_defensively_malformed_entries(self, mock_urlopen):
        # Extra fields (details/size/digest) are real per Ollama's API
        # but deliberately unused; malformed entries are skipped rather
        # than raising, same discipline as list_checkpoints().
        mock_urlopen.return_value = self._tags_response(
            [
                {"name": "good:latest", "size": 123, "details": {"family": "llama"}},
                {"name": ""},
                {"name": 42},
                {"no_name": "x"},
                "not-a-dict",
            ]
        )

        models = self.engine.list_models()

        self.assertEqual(models, [AIModelInfo(name="good:latest")])

    @patch("urllib.request.urlopen")
    def test_list_models_raises_when_models_key_missing(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({}).encode("utf-8"))

        with self.assertRaises(AIBackendError):
            self.engine.list_models()

    @patch("urllib.request.urlopen")
    def test_list_models_raises_when_models_is_not_a_list(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(json.dumps({"models": "oops"}).encode("utf-8"))

        with self.assertRaises(AIBackendError):
            self.engine.list_models()

    @patch("urllib.request.urlopen")
    def test_list_models_raises_on_invalid_json_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"not json")

        with self.assertRaises(AIBackendError):
            self.engine.list_models()

    @patch("urllib.request.urlopen")
    def test_list_models_raises_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(AIBackendError):
            self.engine.list_models()

    @patch("urllib.request.urlopen")
    def test_list_models_raises_on_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(500, {"error": "internal error"})

        with self.assertRaises(AIBackendError):
            self.engine.list_models()

    @patch("urllib.request.urlopen")
    def test_list_models_uses_the_engine_instance_timeout(self, mock_urlopen):
        mock_urlopen.return_value = self._tags_response([{"name": "a"}])
        engine = OllamaEngine(timeout=7.0)

        engine.list_models()

        self.assertEqual(mock_urlopen.call_args.kwargs.get("timeout"), 7.0)


class OllamaEngineGenerateTextTest(unittest.TestCase):

    def setUp(self):
        self.engine = OllamaEngine()

    @staticmethod
    def _generate_response(text, done=True):
        return _FakeResponse(
            json.dumps(
                {
                    "model": "llama3.2",
                    "created_at": "2023-08-04T19:22:45.499127Z",
                    "response": text,
                    "done": done,
                }
            ).encode("utf-8")
        )

    @patch("urllib.request.urlopen")
    def test_generate_text_returns_the_response_field(self, mock_urlopen):
        mock_urlopen.return_value = self._generate_response("The sky is blue because...")

        result = self.engine.generate_text("Why is the sky blue?", model="llama3.2")

        self.assertEqual(result, "The sky is blue because...")

    @patch("urllib.request.urlopen")
    def test_generate_text_posts_to_generate_endpoint_with_exact_body(self, mock_urlopen):
        mock_urlopen.return_value = self._generate_response("answer")

        self.engine.generate_text("hello there", model="mistral:latest")

        sent_request = mock_urlopen.call_args[0][0]
        self.assertTrue(sent_request.full_url.endswith("/api/generate"))
        sent_body = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(
            sent_body, {"model": "mistral:latest", "prompt": "hello there", "stream": False}
        )

    @patch("urllib.request.urlopen")
    def test_generate_text_raises_when_response_field_missing(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"model": "llama3.2", "done": True}).encode("utf-8")
        )

        with self.assertRaises(AIBackendError):
            self.engine.generate_text("hi", model="llama3.2")

    @patch("urllib.request.urlopen")
    def test_generate_text_raises_with_ollama_error_message(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(
            json.dumps({"error": "model 'ghost' not found"}).encode("utf-8")
        )

        with self.assertRaises(AIBackendError) as ctx:
            self.engine.generate_text("hi", model="ghost")

        self.assertIn("model 'ghost' not found", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_generate_text_raises_on_invalid_json_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeResponse(b"not json")

        with self.assertRaises(AIBackendError):
            self.engine.generate_text("hi", model="llama3.2")

    @patch("urllib.request.urlopen")
    def test_generate_text_raises_when_server_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaises(AIBackendError):
            self.engine.generate_text("hi", model="llama3.2")

    @patch("urllib.request.urlopen")
    def test_generate_text_raises_on_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = _http_error(404, {"error": "not found"})

        with self.assertRaises(AIBackendError):
            self.engine.generate_text("hi", model="llama3.2")

    @patch("urllib.request.urlopen")
    def test_generate_text_two_independent_calls_produce_two_independent_results(self, mock_urlopen):
        mock_urlopen.side_effect = [
            self._generate_response("first answer"),
            self._generate_response("second answer"),
        ]

        first = self.engine.generate_text("first prompt", model="llama3.2")
        second = self.engine.generate_text("second prompt", model="llama3.2")

        self.assertEqual(first, "first answer")
        self.assertEqual(second, "second answer")

        first_body = json.loads(mock_urlopen.call_args_list[0][0][0].data.decode("utf-8"))
        second_body = json.loads(mock_urlopen.call_args_list[1][0][0].data.decode("utf-8"))
        self.assertEqual(first_body["prompt"], "first prompt")
        self.assertEqual(second_body["prompt"], "second prompt")


class OllamaEngineArchitecturalConstraintsTest(unittest.TestCase):
    """
    Mission 030's explicit requirement: OllamaEngine must structurally
    satisfy the AIBackend Protocol without any inheritance — proving
    the abstraction is real, not just a document.
    """

    def test_ollama_engine_satisfies_ai_backend_protocol(self):
        self.assertIsInstance(OllamaEngine(), AIBackend)

    def test_ollama_engine_does_not_subclass_ai_backend(self):
        # Protocol conformance must be structural (duck typing), not
        # nominal — OllamaEngine deliberately has no base class, same
        # as ComfyUIEngine.
        self.assertNotIn(AIBackend, OllamaEngine.__mro__)


if __name__ == "__main__":
    unittest.main()
