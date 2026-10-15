"""
Coverage for the client-timeout contract of OllamaEngine: how a timeout is
recognized, which exception it becomes, what is deliberately left untouched,
and how the message reaches PromptAssistantManager.

The transport is meant to be entirely substituted (urllib.request.urlopen is
replaced by doubles): no socket, no real Ollama, no waiting. A double fixes the
classification the engine is meant to apply to the exception it is given; it
does not show which exception a real network stack raises.

The tests are grouped by NATURE OF RESULT, so that one run against the
previous production stays readable. Each group is described by what it is
meant to verify:

- invariants (OllamaTimeoutContractInvariantTest): behaviours that must hold
  before and after the change;
- behavioural regression (OllamaHttpErrorBodyTimeoutRegressionTest): expected
  to fail on the previous production on an observable behaviour and to pass
  afterwards;
- assertions of the new contract (OllamaTimeoutContractNewTest): expected to
  fail on the previous production by construction (the class, the message and
  the 120 s policy did not exist), so they would carry no before/after
  evidence.

The new class is looked up with getattr() so that this module imports on the
previous production; the tests that need it then fail on an assertion, never
on an ImportError.
"""

import http.client
import inspect
import io
import json
import socket
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from src.engines import ollama_engine
from src.engines.ai_backend import AIBackendError
from src.engines.ollama_engine import OllamaEngine
from src.managers.prompt_assistant_manager import PromptAssistantError, PromptAssistantManager

TIMEOUT_ERROR_CLASS = getattr(ollama_engine, "OllamaTimeoutError", None)

BASE_URL = "http://127.0.0.1:11434"
GENERATE_REPLY = json.dumps({"model": "m", "response": "answer", "done": True}).encode("utf-8")
TAGS_REPLY = json.dumps({"models": [{"name": "a"}]}).encode("utf-8")


# ---------------------------------------------------------------------------------------------------------------- doubles
class _Response:
    """Stand-in for the object urlopen() returns: read() answers with a body, or raises."""

    def __init__(self, body=b"", read_error=None):
        self._body = body
        self._read_error = read_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        if self._read_error is not None:
            raise self._read_error
        return self._body


class _UnreadableBody(io.BytesIO):
    """Body of an HTTPError whose read() raises."""

    def __init__(self, error):
        super().__init__(b"")
        self._error = error

    def read(self, *args):
        raise self._error


def _http_error(body_or_stream, status=500):
    stream = io.BytesIO(body_or_stream) if isinstance(body_or_stream, bytes) else body_or_stream
    return urllib.error.HTTPError(BASE_URL + "/api/generate", status, "Internal Server Error", {}, stream)


def _raising(error):
    def transport(request, timeout=None):
        raise error

    return transport


def _returning(response):
    def transport(request, timeout=None):
        return response

    return transport


# Where an error is injected: urlopen() itself, response.read(), or the read() of an HTTPError body.
POINTS = {
    "urlopen": lambda error: _raising(error),
    "read": lambda error: _returning(_Response(read_error=error)),
    "http_error_read": lambda error: _raising(_http_error(_UnreadableBody(error))),
}

CALLS = {
    "generate_text": lambda engine: engine.generate_text("hello", model="m"),
    "list_models": lambda engine: engine.list_models(),
}


def _capture(call, engine, transport):
    """Runs `call(engine)` with the transport substituted and returns the exception it raised (or None)."""
    with patch("urllib.request.urlopen", side_effect=transport):
        try:
            call(engine)
        except BaseException as error:  # the test inspects whatever came out, including a raw exception
            return error
    return None


def _timeout_message(timeout_text, base_url=BASE_URL):
    """The exact message of the contract, written out literally (not rebuilt with the engine's own formatting)."""
    return (
        "Communication with Ollama at %s timed out (configured timeout: %s s). "
        "The request did not complete; the server's state is unknown." % (base_url, timeout_text)
    )


# Transport errors that are NOT timeouts and must keep their current treatment ("server unreachable").
NON_TIMEOUT_ERRORS = [
    ("URLError with a text reason", lambda: urllib.error.URLError("Connection refused")),
    ("URLError whose text reason says 'timed out' (never classified by text)", lambda: urllib.error.URLError("timed out")),
    ("URLError wrapping ConnectionRefusedError", lambda: urllib.error.URLError(ConnectionRefusedError())),
    ("URLError wrapping ConnectionResetError", lambda: urllib.error.URLError(ConnectionResetError())),
    ("URLError wrapping socket.gaierror", lambda: urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))),
    (
        "URLError wrapping a URLError that wraps a TimeoutError (the reason is not searched recursively)",
        lambda: urllib.error.URLError(urllib.error.URLError(TimeoutError("timed out"))),
    ),
    ("ConnectionResetError", lambda: ConnectionResetError("reset")),
    ("plain OSError", lambda: OSError("boom")),
]

# Timeouts, as recognized by type: a TimeoutError directly, or in the immediate reason of a URLError.
TIMEOUT_SOURCES = [
    ("urlopen raises TimeoutError", "urlopen", lambda: TimeoutError("timed out")),
    ("urlopen raises socket.timeout", "urlopen", lambda: socket.timeout("timed out")),
    ("urlopen raises URLError(reason=TimeoutError)", "urlopen", lambda: urllib.error.URLError(TimeoutError("timed out"))),
    ("urlopen raises URLError(reason=socket.timeout)", "urlopen", lambda: urllib.error.URLError(socket.timeout("timed out"))),
    ("response.read() raises TimeoutError", "read", lambda: TimeoutError("timed out")),
    ("HTTPError.read() raises TimeoutError", "http_error_read", lambda: TimeoutError("timed out")),
]


# ---------------------------------------------------------------------------------------------------------- invariants
class OllamaTimeoutContractInvariantTest(unittest.TestCase):
    """Must hold on the previous production and on the new one."""

    def test_the_generate_request_is_unchanged_and_carries_the_instance_timeout(self):
        engine = OllamaEngine(BASE_URL, 7.5)

        with patch("urllib.request.urlopen", side_effect=_returning(_Response(GENERATE_REPLY))) as mock_urlopen:
            result = engine.generate_text("hello", model="m")

        self.assertEqual(result, "answer")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, BASE_URL + "/api/generate")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"model": "m", "prompt": "hello", "stream": False})
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(mock_urlopen.call_args.kwargs.get("timeout"), 7.5)

    def test_the_tags_request_is_unchanged_and_carries_the_instance_timeout(self):
        engine = OllamaEngine(BASE_URL, 5.0)

        with patch("urllib.request.urlopen", side_effect=_returning(_Response(TAGS_REPLY))) as mock_urlopen:
            models = engine.list_models()

        self.assertEqual([model.name for model in models], ["a"])
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, BASE_URL + "/api/tags")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(mock_urlopen.call_args.kwargs.get("timeout"), 5.0)

    def test_the_constructor_default_and_positional_signature_are_unchanged(self):
        parameters = list(inspect.signature(OllamaEngine.__init__).parameters.values())

        self.assertEqual([p.name for p in parameters], ["self", "base_url", "timeout"])
        self.assertEqual(parameters[1].default, "http://127.0.0.1:11434")
        self.assertEqual(parameters[2].default, 30.0)
        self.assertEqual(OllamaEngine()._timeout, 30.0)
        positional = OllamaEngine("http://192.168.1.50:11434", 5.0)
        self.assertEqual(positional._base_url, "http://192.168.1.50:11434")
        self.assertEqual(positional._timeout, 5.0)

    def test_socket_timeout_is_an_alias_of_timeout_error_on_the_supported_versions(self):
        # The recognition rule relies on this documented alias (Python 3.10 and later).
        self.assertIs(socket.timeout, TimeoutError)

    def test_errors_that_are_not_timeouts_keep_the_unreachable_treatment_and_their_cause(self):
        for label, factory in NON_TIMEOUT_ERRORS:
            for point in ("urlopen", "read"):
                for call_name, call in CALLS.items():
                    with self.subTest(error=label, point=point, call=call_name):
                        error = factory()

                        raised = _capture(call, OllamaEngine(BASE_URL, 7.5), POINTS[point](error))

                        self.assertIs(type(raised), AIBackendError)
                        self.assertIs(raised.__cause__, error)
                        self.assertEqual(str(raised), "Ollama server unreachable at %s: %s" % (BASE_URL, error))

    def test_an_http_error_with_a_json_error_body_keeps_its_message(self):
        raised = _capture(
            CALLS["generate_text"],
            OllamaEngine(BASE_URL, 7.5),
            _raising(_http_error(b'{"error": "model not found"}', status=404)),
        )

        self.assertIs(type(raised), AIBackendError)
        self.assertEqual(str(raised), "Ollama returned an error: model not found")

    def test_an_http_error_with_a_body_that_is_not_json_keeps_its_message(self):
        raised = _capture(
            CALLS["generate_text"],
            OllamaEngine(BASE_URL, 7.5),
            _raising(_http_error(b"not json", status=502)),
        )

        self.assertIs(type(raised), AIBackendError)
        self.assertEqual(str(raised), "Ollama returned an invalid response: b'not json'")

    def test_http_protocol_errors_still_come_out_raw_at_every_point(self):
        for point in POINTS:
            for call_name, call in CALLS.items():
                with self.subTest(point=point, call=call_name):
                    error = http.client.IncompleteRead(b"ab", 10)

                    raised = _capture(call, OllamaEngine(BASE_URL, 7.5), POINTS[point](error))

                    self.assertIs(raised, error)

    def test_non_timeout_exceptions_raised_while_reading_an_http_error_body_keep_their_identity_or_their_historical_conversion(self):
        """
        An exception that is not a timeout, raised while the body of an HTTP error response is read, is not touched
        by _read_error_body(). What a caller sees depends on the level:

        - a ConnectionResetError and a plain OSError come out of the two public methods as the very same object;
        - a ValueError comes out of _request_json() as the very same object, but each public method already
          intercepts ValueError around _request_json() and converts it into AIBackendError("Ollama base URL is
          invalid: ..."), with the original exception as its cause. That historical conversion, whose message is
          misleading in this case, is pinned here and not changed.
        """
        for label, factory in (
            ("ConnectionResetError", lambda: ConnectionResetError("reset")),
            ("plain OSError", lambda: OSError("boom")),
        ):
            for call_name, call in CALLS.items():
                with self.subTest(error=label, level="public method", call=call_name):
                    error = factory()

                    raised = _capture(call, OllamaEngine(BASE_URL, 7.5), POINTS["http_error_read"](error))

                    self.assertIs(raised, error)

        request = urllib.request.Request(BASE_URL + "/api/generate")
        with self.subTest(error="ValueError", level="_request_json", call="_request_json"):
            error = ValueError("odd")

            raised = _capture(
                lambda engine: engine._request_json(request), OllamaEngine(BASE_URL, 7.5), POINTS["http_error_read"](error)
            )

            self.assertIs(raised, error)

        for call_name, call in CALLS.items():
            with self.subTest(error="ValueError", level="public method, historical conversion", call=call_name):
                error = ValueError("odd")

                raised = _capture(call, OllamaEngine(BASE_URL, 7.5), POINTS["http_error_read"](error))

                self.assertIs(type(raised), AIBackendError)
                self.assertIs(raised.__cause__, error)
                self.assertEqual(str(raised), "Ollama base URL is invalid: 'http://127.0.0.1:11434'")


# ------------------------------------------------------------------------------------------- behavioural regression
class OllamaHttpErrorBodyTimeoutRegressionTest(unittest.TestCase):
    """
    Expected to fail on the previous production, where
    a timeout raised while the body of an HTTP error response is being read
    escaped _request_json() as a raw TimeoutError, outside the AIBackendError
    contract of AIBackend. The assertion does not mention the new class, so it
    is meant to be meaningful on both versions. It is meant to show this on a
    double; whether a test server can produce that situation was observed
    separately, by a loopback probe run on the previous production (docs/
    missions/MISSION_177.md, S5).
    """

    def test_a_timeout_while_reading_an_http_error_body_stays_inside_the_backend_error_contract(self):
        for call_name, call in CALLS.items():
            with self.subTest(call=call_name):
                raised = _capture(
                    call, OllamaEngine(BASE_URL, 7.5), POINTS["http_error_read"](TimeoutError("timed out"))
                )

                self.assertIsInstance(raised, AIBackendError, "got %r instead" % (raised,))


# ----------------------------------------------------------------------------------------------- new contract
class OllamaTimeoutContractNewTest(unittest.TestCase):
    """Assertions of the new contract: expected to fail on the previous production by construction."""

    def _error_class(self):
        self.assertIsNotNone(TIMEOUT_ERROR_CLASS, "OllamaTimeoutError does not exist in src.engines.ollama_engine")
        return TIMEOUT_ERROR_CLASS

    def test_the_timeout_error_is_a_subclass_of_the_backend_error(self):
        error_class = self._error_class()

        self.assertTrue(issubclass(error_class, AIBackendError))

    def test_every_recognized_timeout_becomes_the_timeout_error_with_the_original_as_cause(self):
        error_class = self._error_class()

        for label, point, factory in TIMEOUT_SOURCES:
            for call_name, call in CALLS.items():
                with self.subTest(source=label, call=call_name):
                    error = factory()

                    raised = _capture(call, OllamaEngine(BASE_URL, 7.5), POINTS[point](error))

                    self.assertIsInstance(raised, error_class)
                    self.assertIs(raised.__cause__, error)
                    self.assertEqual(str(raised), _timeout_message("7.5"))

    def test_the_message_is_exact_for_the_assistant_timeout(self):
        self._error_class()

        raised = _capture(
            CALLS["generate_text"], OllamaEngine(BASE_URL, 120.0), POINTS["urlopen"](TimeoutError("timed out"))
        )

        self.assertEqual(
            str(raised),
            "Communication with Ollama at http://127.0.0.1:11434 timed out (configured timeout: 120 s). "
            "The request did not complete; the server's state is unknown.",
        )

    def test_the_message_carries_the_base_url_and_timeout_of_the_instance(self):
        self._error_class()

        raised = _capture(
            CALLS["list_models"],
            OllamaEngine("http://192.168.1.50:11434", 5.0),
            POINTS["urlopen"](TimeoutError("timed out")),
        )

        self.assertEqual(str(raised), _timeout_message("5", base_url="http://192.168.1.50:11434"))

    def test_the_category_is_shared_with_discovery(self):
        error_class = self._error_class()

        for label, point, factory in TIMEOUT_SOURCES:
            with self.subTest(source=label):
                raised = _capture(CALLS["list_models"], OllamaEngine(BASE_URL, 5.0), POINTS[point](factory()))

                self.assertIsInstance(raised, error_class)

    def test_errors_that_are_not_timeouts_are_not_reported_as_timeouts(self):
        error_class = self._error_class()

        for label, factory in NON_TIMEOUT_ERRORS:
            for point in ("urlopen", "read"):
                with self.subTest(error=label, point=point):
                    raised = _capture(CALLS["generate_text"], OllamaEngine(BASE_URL, 7.5), POINTS[point](factory()))

                    self.assertNotIsInstance(raised, error_class)

    def test_the_manager_carries_the_exact_message_and_clears_its_busy_flag(self):
        error_class = self._error_class()
        manager = PromptAssistantManager(OllamaEngine(BASE_URL, 120.0), model_name="m")

        with patch("urllib.request.urlopen", side_effect=_raising(TimeoutError("timed out"))):
            with self.assertRaises(PromptAssistantError) as context:
                manager.assist("a red car")

        self.assertEqual(str(context.exception), _timeout_message("120"))
        self.assertIsInstance(context.exception.__cause__, error_class)
        self.assertFalse(manager.busy)


if __name__ == "__main__":
    unittest.main()
