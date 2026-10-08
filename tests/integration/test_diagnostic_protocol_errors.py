"""
Diagnostic protocol errors: the closed list of raw transport/shape errors that diagnostic callers (the Settings
connection tests and discovery buttons, GenerationManager's list_*() and the Inference page's refresh button) turn into a
visible status, and the proof that the decisions the lifecycle managers' pre-start check and the readiness workers take on
the very same errors are unchanged.

Real ComfyUIEngine / ForgeEngine / OllamaEngine objects throughout, never a mocked engine class. What is replaced is the
transport (urllib.request.urlopen), with the error injected where it really arises: urlopen() itself, response.read(),
HTTPError.read(), or a response body. For the lifecycle managers QProcess and the readiness thread are replaced too, so no
process, no thread and no real engine is ever started. A few tests run the real http.client machinery against a socket
server bound to 127.0.0.1, with proxies disabled for the test, to prove that the injected classes are the classes that
really emerge.

Families:
- DiagnosticErrorsContractTest / ScopeGuardTest: the closed list, the formatter, the layering, the untouched modules.
- EngineTransportCharacterizationTest: the engines still let those errors through raw (the lifecycle decisions rely on it).
- EngineResponseShapeGuardTest: a non-object root is a typed error, nested shape errors keep their historical type.
- GenerationManager / SettingsPage / InferencePage frontier tests: the regressions this change fixes, plus invariants.
- Pre-start check / readiness worker preservation tests, run against the real engines.
- LoopbackEndToEndTest: genuine classes from a genuine socket.
"""

import ast
import http.client
import io
import json
import logging
import shutil
import socket
import socketserver
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from src.core.event_bus import EventBus
from src.engines import diagnostic_errors
from src.engines.ai_backend import AIBackendError
from src.engines.comfyui_engine import ComfyUIEngine, ComfyUIEngineError, ComfyUIUnexpectedResponseError
from src.engines.comfyui_launch import ComfyUILaunchConfig
from src.engines.diagnostic_errors import DIAGNOSTIC_PROTOCOL_ERRORS, describe_protocol_error
from src.engines.forge_engine import ForgeEngine, ForgeEngineError
from src.engines.forge_launch import ForgeLaunchConfig
from src.engines.ollama_engine import OllamaEngine
from src.managers.application_settings_manager import ApplicationSettingsManager
from src.managers.generation_manager import GenerationError, GenerationManager
from src.managers.settings_manager import SettingsManager
from src.managers.workspace_manager import WorkspaceManager
from src.ui import comfyui_lifecycle_manager as comfyui_lifecycle_module
from src.ui import comfyui_readiness_worker as comfyui_worker_module
from src.ui import forge_lifecycle_manager as forge_lifecycle_module
from src.ui import forge_readiness_worker as forge_worker_module
from src.ui.comfyui_lifecycle_manager import ComfyUILifecycleManager
from src.ui.comfyui_readiness_worker import ComfyUIReadinessWorker
from src.ui.forge_lifecycle_manager import ForgeLifecycleManager
from src.ui.forge_readiness_worker import ForgeReadinessWorker
from src.ui.pages.inference_page import InferencePage
from src.ui.pages.settings_page import SettingsPage

_app = QApplication.instance() or QApplication([])

# Never contacted: every test replaces urllib.request.urlopen, or talks to its own 127.0.0.1 server.
URL = "http://127.0.0.1:18188"


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
    def __init__(self, error):
        super().__init__(b"")
        self._error = error

    def read(self, *args):
        raise self._error


def _http_error(body_or_stream, status=500):
    stream = io.BytesIO(body_or_stream) if isinstance(body_or_stream, bytes) else body_or_stream
    return urllib.error.HTTPError(URL + "/x", status, "Internal Server Error", {}, stream)


def _raising(error):
    def transport(request, timeout=None):
        raise error

    return transport


def _returning(response):
    def transport(request, timeout=None):
        return response

    return transport


def _json(payload):
    return _returning(_Response(body=json.dumps(payload).encode("utf-8")))


def _body(raw):
    return _returning(_Response(body=raw))


def _transport_for(kind, error):
    if kind == "urlopen":
        return _raising(error)
    if kind == "read":
        return _returning(_Response(read_error=error))
    if kind == "http_error_read":
        return _raising(_http_error(_UnreadableBody(error)))
    raise ValueError(kind)


# (label, injected error, where it is injected). Each is raised raw by all three engines.
PROTOCOL_VECTORS = [
    ("InvalidURL raised by urlopen()", http.client.InvalidURL("nonnumeric port: 'abc'"), "urlopen"),
    ("BadStatusLine raised by urlopen()", http.client.BadStatusLine("ABSURD"), "urlopen"),
    ("LineTooLong raised by urlopen()", http.client.LineTooLong("header line"), "urlopen"),
    ("UnknownProtocol raised by urlopen()", http.client.UnknownProtocol("HTTP/2.0"), "urlopen"),
    ("IncompleteRead raised by response.read()", http.client.IncompleteRead(b"ab", 10), "read"),
    ("IncompleteRead raised by HTTPError.read()", http.client.IncompleteRead(b"ab", 10), "http_error_read"),
]

NON_OBJECT_ROOTS = [b"[]", b'"x"', b"1", b"null", b"true"]
NON_LIST_ROOTS = [b"{}", b'"x"', b"1", b"null", b"true"]
UNDECODABLE = b"\xff\xff\xff"

COMFY_CALLS = {
    "comfyui.check_connection": lambda: ComfyUIEngine(URL, 1.0).check_connection(timeout=1.0),
    "comfyui.list_checkpoints": lambda: ComfyUIEngine(URL, 1.0).list_checkpoints(timeout=1.0),
    "comfyui.list_loras": lambda: ComfyUIEngine(URL, 1.0).list_loras(),
    "comfyui.list_samplers": lambda: ComfyUIEngine(URL, 1.0).list_samplers(timeout=1.0),
    "comfyui.list_schedulers": lambda: ComfyUIEngine(URL, 1.0).list_schedulers(timeout=1.0),
}
FORGE_CALLS = {
    "forge.check_connection": lambda: ForgeEngine(URL, 1.0).check_connection(timeout=1.0),
    "forge.list_checkpoints": lambda: ForgeEngine(URL, 1.0).list_checkpoints(timeout=1.0),
    "forge.list_loras": lambda: ForgeEngine(URL, 1.0).list_loras(timeout=1.0),
    "forge.list_samplers": lambda: ForgeEngine(URL, 1.0).list_samplers(timeout=1.0),
    "forge.list_schedulers": lambda: ForgeEngine(URL, 1.0).list_schedulers(timeout=1.0),
}
OLLAMA_CALLS = {"ollama.list_models": lambda: OllamaEngine(URL, 1.0).list_models()}
ALL_CALLS = {**COMFY_CALLS, **FORGE_CALLS, **OLLAMA_CALLS}


def _capture(call, transport):
    """The exception `call` raises through `transport`; the test fails if it raises nothing."""
    with patch("urllib.request.urlopen", side_effect=transport):
        try:
            call()
        except BaseException as error:  # noqa: BLE001 - the test inspects exactly what escapes
            return error
    raise AssertionError("the call did not raise")


class _QtCase(unittest.TestCase):
    """Records what reaches sys.excepthook: an exception that escapes a Qt slot lands there and the test goes on."""

    def record_escaped_exceptions(self):
        self.escaped = []
        previous = sys.excepthook
        sys.excepthook = lambda exc_type, exc_value, traceback: self.escaped.append(exc_value)
        self.addCleanup(setattr, sys, "excepthook", previous)

    def silence_loggers(self, *modules):
        for module in modules:
            logger = logging.getLogger(module.__name__)
            previous = logger.disabled
            logger.disabled = True
            self.addCleanup(setattr, logger, "disabled", previous)


# ----------------------------------------------------------------------------------------------------- contract / scope
class DiagnosticErrorsContractTest(unittest.TestCase):

    def test_the_closed_list_is_exactly_these_classes(self):
        self.assertEqual(
            DIAGNOSTIC_PROTOCOL_ERRORS,
            (
                http.client.InvalidURL,
                http.client.BadStatusLine,
                http.client.IncompleteRead,
                http.client.LineTooLong,
                http.client.UnknownProtocol,
                UnicodeDecodeError,
                ComfyUIUnexpectedResponseError,
            ),
        )

    def test_nothing_broader_or_unrelated_is_covered(self):
        outside = [
            Exception, BaseException, AttributeError, TypeError, KeyError, RuntimeError, RecursionError, OverflowError,
            ValueError, OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError,
            http.client.HTTPException, http.client.CannotSendRequest, http.client.ResponseNotReady,
            http.client.ImproperConnectionState, http.client.NotConnected,
            ComfyUIEngineError, ForgeEngineError, AIBackendError, GenerationError,
        ]
        for cls in outside:
            with self.subTest(cls.__name__):
                self.assertFalse(issubclass(cls, DIAGNOSTIC_PROTOCOL_ERRORS))

    def test_the_unexpected_response_error_is_not_an_engine_error(self):
        self.assertTrue(issubclass(ComfyUIUnexpectedResponseError, Exception))
        self.assertFalse(issubclass(ComfyUIUnexpectedResponseError, ComfyUIEngineError))
        self.assertFalse(issubclass(ComfyUIEngineError, ComfyUIUnexpectedResponseError))

    def test_formatter_format_and_truncation(self):
        self.assertEqual(describe_protocol_error(http.client.InvalidURL("nonnumeric port: 'abc'")), "InvalidURL: nonnumeric port: 'abc'")
        self.assertEqual(describe_protocol_error(ValueError()), "ValueError: ")
        long_text = describe_protocol_error(ValueError("x" * 1000))
        self.assertEqual(len(long_text), 300)
        self.assertTrue(long_text.endswith("..."))
        exact = describe_protocol_error(ValueError("y" * (300 - len("ValueError: "))))
        self.assertEqual(len(exact), 300)
        self.assertFalse(exact.endswith("..."))

    def test_formatter_never_raises_for_an_ordinary_exception_whose_str_fails(self):
        class StrRaises(Exception):
            def __str__(self):
                raise RuntimeError("str failed")

        class StrNotAString(Exception):
            def __str__(self):
                return 5

        self.assertEqual(describe_protocol_error(StrRaises()), "StrRaises")
        self.assertEqual(describe_protocol_error(StrNotAString()), "StrNotAString")

    def test_formatter_never_masks_keyboard_interrupt_or_system_exit(self):
        class StrInterrupts(Exception):
            def __str__(self):
                raise KeyboardInterrupt()

        class StrExits(Exception):
            def __str__(self):
                raise SystemExit(3)

        with self.assertRaises(KeyboardInterrupt):
            describe_protocol_error(StrInterrupts())
        with self.assertRaises(SystemExit):
            describe_protocol_error(StrExits())

    def test_formatter_output_equals_the_existing_lifecycle_formatter(self):
        class StrRaises(Exception):
            def __str__(self):
                raise RuntimeError("no")

        for error in (http.client.BadStatusLine("A"), ValueError("x" * 1000), StrRaises(), ValueError(), AttributeError("boom")):
            with self.subTest(type(error).__name__):
                self.assertEqual(describe_protocol_error(error), comfyui_worker_module.describe_unexpected_exception(error))
                self.assertEqual(describe_protocol_error(error), forge_worker_module.describe_unexpected_exception(error))


class ScopeGuardTest(unittest.TestCase):

    def test_the_new_module_depends_on_nothing_but_http_client_and_the_comfyui_engine(self):
        tree = ast.parse(Path(diagnostic_errors.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {"http.client", "src.engines.comfyui_engine"})

    def test_modules_whose_behaviour_must_not_change_do_not_know_the_new_names(self):
        from src.engines import forge_engine, ollama_engine
        from src.ui.pages import inference_page

        for module in (
            comfyui_lifecycle_module, forge_lifecycle_module, comfyui_worker_module, forge_worker_module,
            forge_engine, ollama_engine, inference_page,
        ):
            with self.subTest(module.__name__):
                source = Path(module.__file__).read_text(encoding="utf-8")
                self.assertNotIn("diagnostic_errors", source)
                self.assertNotIn("ComfyUIUnexpectedResponseError", source)


# ------------------------------------------------------------------------------------------- engines: raw pass-through
class EngineTransportCharacterizationTest(unittest.TestCase):
    """The engines are unchanged: the closed-list errors still come out of every call raw, which is what the pre-start
    check and the readiness workers classify. Errors the engines translate stay translated."""

    def test_protocol_errors_come_out_of_every_engine_call_raw(self):
        for label, error, kind in PROTOCOL_VECTORS:
            for call_name, call in ALL_CALLS.items():
                with self.subTest(label=label, call=call_name):
                    raised = _capture(call, _transport_for(kind, error))
                    self.assertIs(raised, error)

    def test_a_forge_response_body_that_cannot_be_decoded_comes_out_raw(self):
        for call_name, call in FORGE_CALLS.items():
            with self.subTest(call=call_name, where="200 body"):
                self.assertIsInstance(_capture(call, _body(UNDECODABLE)), UnicodeDecodeError)
            with self.subTest(call=call_name, where="HTTPError body"):
                self.assertIsInstance(_capture(call, _raising(_http_error(UNDECODABLE))), UnicodeDecodeError)

    def test_errors_the_engines_translate_stay_translated(self):
        expected = {"comfyui": ComfyUIEngineError, "forge": ForgeEngineError, "ollama": AIBackendError}
        for error in (
            urllib.error.URLError("Connection refused"),
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            TimeoutError("timed out"),
        ):
            for call_name, call in ALL_CALLS.items():
                with self.subTest(error=type(error).__name__, call=call_name):
                    raised = _capture(call, _raising(error))
                    self.assertIsInstance(raised, expected[call_name.split(".")[0]])
                    self.assertNotIsInstance(raised, DIAGNOSTIC_PROTOCOL_ERRORS)


class EngineResponseShapeGuardTest(unittest.TestCase):

    def test_comfyui_list_checkpoints_and_check_connection_raise_the_distinct_type_for_a_non_object_root(self):
        for raw in NON_OBJECT_ROOTS:
            for call_name in ("comfyui.list_checkpoints", "comfyui.check_connection"):
                with self.subTest(root=raw, call=call_name):
                    raised = _capture(COMFY_CALLS[call_name], _body(raw))
                    self.assertIsInstance(raised, ComfyUIUnexpectedResponseError)
                    self.assertNotIsInstance(raised, ComfyUIEngineError)
                    self.assertNotIsInstance(raised, AttributeError)

    def test_comfyui_other_discovery_calls_raise_an_engine_error_for_a_non_object_root(self):
        for raw in NON_OBJECT_ROOTS:
            for call_name in ("comfyui.list_loras", "comfyui.list_samplers", "comfyui.list_schedulers"):
                with self.subTest(root=raw, call=call_name):
                    raised = _capture(COMFY_CALLS[call_name], _body(raw))
                    self.assertIsInstance(raised, ComfyUIEngineError)

    def test_ollama_raises_its_backend_error_for_a_non_object_root_and_for_a_non_object_error_body(self):
        for raw in NON_OBJECT_ROOTS:
            with self.subTest(root=raw):
                self.assertIsInstance(_capture(OLLAMA_CALLS["ollama.list_models"], _body(raw)), AIBackendError)
        with self.subTest("HTTP 404 with a list body"):
            self.assertIsInstance(
                _capture(OLLAMA_CALLS["ollama.list_models"], _raising(_http_error(b"[]", status=404))), AIBackendError
            )

    def test_forge_non_list_roots_keep_raising_forge_engine_error(self):
        for raw in NON_LIST_ROOTS:
            for call_name, call in FORGE_CALLS.items():
                with self.subTest(root=raw, call=call_name):
                    self.assertIsInstance(_capture(call, _body(raw)), ForgeEngineError)

    def test_nested_shape_errors_keep_their_historical_engine_error(self):
        cases = [
            {"CheckpointLoaderSimple": None},
            {"CheckpointLoaderSimple": {}},
            {"CheckpointLoaderSimple": {"input": None}},
            {"CheckpointLoaderSimple": {"input": {"required": []}}},
            {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": []}}}},
            {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": "abc"}}}},
            {},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                raised = _capture(COMFY_CALLS["comfyui.list_checkpoints"], _json(payload))
                self.assertIsInstance(raised, ComfyUIEngineError)
                self.assertNotIsInstance(raised, ComfyUIUnexpectedResponseError)
        for payload in ([1], [None], [{}], [{"title": "a"}, 3]):
            with self.subTest(forge=payload):
                self.assertIsInstance(_capture(FORGE_CALLS["forge.list_checkpoints"], _json(payload)), ForgeEngineError)

    def test_valid_responses_still_work(self):
        comfy = ComfyUIEngine(URL, 1.0)
        with patch("urllib.request.urlopen", side_effect=_json(
            {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a.safetensors", 1, None]]}}}}
        )):
            self.assertEqual(comfy.list_checkpoints(timeout=1.0), ["a.safetensors"])
            self.assertTrue(comfy.check_connection(timeout=1.0))
        with patch("urllib.request.urlopen", side_effect=_json({"LoraLoader": {"input": {"required": {"lora_name": [["l"]]}}}})):
            self.assertEqual(comfy.list_loras(), ["l"])
        ksampler = {"KSampler": {"input": {"required": {"sampler_name": [["euler"]], "scheduler": [["normal"]]}}}}
        with patch("urllib.request.urlopen", side_effect=_json(ksampler)):
            self.assertEqual(comfy.list_samplers(timeout=1.0), ["euler"])
            self.assertEqual(comfy.list_schedulers(timeout=1.0), ["normal"])
        with patch("urllib.request.urlopen", side_effect=_json({"models": [{"name": "m"}, 5, {"name": ""}]})):
            self.assertEqual([m.name for m in OllamaEngine(URL, 1.0).list_models()], ["m"])
        with patch("urllib.request.urlopen", side_effect=_json([])):
            self.assertTrue(ForgeEngine(URL, 1.0).check_connection(timeout=1.0))


# ------------------------------------------------------------------------------------------------------ GenerationManager
class GenerationManagerDiagnosticFrontierTest(unittest.TestCase):

    METHODS = ("list_checkpoints", "list_samplers", "list_schedulers")

    def _call(self, method, engine_key):
        manager = GenerationManager(ComfyUIEngine(URL, 1.0))
        kwargs = {"timeout": 1.0}
        if engine_key == "forge":
            kwargs["engine"] = ForgeEngine(URL, 1.0)
        return getattr(manager, method)(**kwargs)

    def _manager_error(self, method, engine_key, transport):
        with patch("urllib.request.urlopen", side_effect=transport):
            with self.assertRaises(GenerationError) as context:
                self._call(method, engine_key)
        return context.exception

    def test_closed_list_errors_become_a_generation_error_with_the_formatted_detail_and_the_cause(self):
        for label, error, kind in PROTOCOL_VECTORS:
            for engine_key in ("comfyui", "forge"):
                for method in self.METHODS:
                    with self.subTest(label=label, engine=engine_key, method=method):
                        raised = self._manager_error(method, engine_key, _transport_for(kind, error))
                        self.assertEqual(str(raised), describe_protocol_error(error))
                        self.assertIs(raised.__cause__, error)

    def test_a_comfyui_non_object_root_on_list_checkpoints_becomes_a_generation_error(self):
        raised = self._manager_error("list_checkpoints", "comfyui", _body(b"[]"))
        self.assertIsInstance(raised.__cause__, ComfyUIUnexpectedResponseError)
        self.assertTrue(str(raised).startswith("ComfyUIUnexpectedResponseError: "))

    def test_a_forge_undecodable_body_becomes_a_generation_error(self):
        for method in self.METHODS:
            with self.subTest(method):
                raised = self._manager_error(method, "forge", _body(UNDECODABLE))
                self.assertIsInstance(raised.__cause__, UnicodeDecodeError)
                self.assertTrue(str(raised).startswith("UnicodeDecodeError: "))

    def test_engine_errors_keep_their_historical_conversion(self):
        for engine_key, engine_error in (("comfyui", ComfyUIEngineError), ("forge", ForgeEngineError)):
            for method in self.METHODS:
                with self.subTest(engine=engine_key, method=method):
                    raised = self._manager_error(method, engine_key, _raising(urllib.error.URLError("Connection refused")))
                    self.assertIsInstance(raised.__cause__, engine_error)
                    self.assertEqual(str(raised), str(raised.__cause__))

    def test_errors_outside_the_closed_list_still_propagate(self):
        outside = [
            RuntimeError("x"), TypeError("x"), AttributeError("x"), RecursionError("x"), OverflowError("x"),
            http.client.HTTPException("got more than 100 headers"), http.client.CannotSendRequest("x"),
            http.client.ResponseNotReady("x"),
        ]
        for error in outside:
            for method in self.METHODS:
                with self.subTest(error=type(error).__name__, method=method):
                    with patch("urllib.request.urlopen", side_effect=_raising(error)):
                        with self.assertRaises(type(error)) as context:
                            self._call(method, "comfyui")
                    self.assertIs(context.exception, error)

    def test_keyboard_interrupt_is_not_caught(self):
        with patch("urllib.request.urlopen", side_effect=_raising(KeyboardInterrupt())):
            with self.assertRaises(KeyboardInterrupt):
                self._call("list_checkpoints", "comfyui")


# ----------------------------------------------------------------------------------------------------------- SettingsPage
SETTINGS_SITES = {
    "comfyui_connection": dict(
        button="comfyui_test_connection_button", label="comfyui_connection_status_label", url="comfyui_url_edit",
        call="comfyui.check_connection", neutral="Connexion non testée.",
        expected="ComfyUI : URL invalide ou réponse inattendue du serveur ({detail})."),
    "forge_connection": dict(
        button="forge_test_connection_button", label="forge_connection_status_label", url="forge_url_edit",
        call="forge.check_connection", neutral="Connexion non testée.",
        expected="Forge : URL invalide ou réponse inattendue du serveur ({detail})."),
    "checkpoints": dict(
        button="refresh_checkpoints_button", label="checkpoint_discovery_status_label", url="comfyui_url_edit",
        call="comfyui.list_checkpoints", combo="comfyui_checkpoint_name_edit", neutral="",
        expected="Découverte impossible : réponse inattendue du serveur ou URL invalide ({detail}). "
                 "La saisie manuelle du checkpoint reste disponible."),
    "loras": dict(
        button="refresh_loras_button", label="lora_discovery_status_label", url="comfyui_url_edit",
        call="comfyui.list_loras", combo="comfyui_lora_name_edit", neutral="",
        expected="Découverte impossible : réponse inattendue du serveur ou URL invalide ({detail}). "
                 "La saisie manuelle du LoRA reste disponible."),
    "ollama_models": dict(
        button="refresh_ollama_models_button", label="ollama_discovery_status_label", url="ollama_url_edit",
        call="ollama.list_models", combo="ollama_model_name_edit", neutral="",
        expected="Découverte impossible : réponse inattendue du serveur ou URL invalide ({detail}). "
                 "La saisie manuelle du modèle reste disponible."),
}


class _SettingsCase(_QtCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        self.settings_manager = SettingsManager(workspace_manager)
        self.application_settings_manager = ApplicationSettingsManager(
            storage_directory=Path(self.tmp_dir) / "AppSettings", event_bus=event_bus
        )
        self.page = SettingsPage(self.settings_manager, self.application_settings_manager)
        self.record_escaped_exceptions()

    def click(self, site, transport):
        """A real click on the real button, the typed URL being the one used. Returns the combo state before the click."""
        spec = SETTINGS_SITES[site]
        getattr(self.page, spec["url"]).setText(URL)
        before = None
        if "combo" in spec:
            combo = getattr(self.page, spec["combo"])
            combo.clear()
            combo.addItems(["keep-1", "keep-2"])
            combo.setCurrentText("typed-by-hand")
            before = ([combo.itemText(i) for i in range(combo.count())], combo.currentText())
        with patch("urllib.request.urlopen", side_effect=transport):
            getattr(self.page, spec["button"]).click()
        return before

    def combo_state(self, site):
        combo = getattr(self.page, SETTINGS_SITES[site]["combo"])
        return ([combo.itemText(i) for i in range(combo.count())], combo.currentText())


class SettingsPageDiagnosticFrontierTest(_SettingsCase):

    def assert_status(self, site, transport, error):
        before = self.click(site, transport)
        spec = SETTINGS_SITES[site]
        self.assertEqual(self.escaped, [], "nothing may escape the slot")
        self.assertEqual(getattr(self.page, spec["label"]).text(), spec["expected"].format(detail=describe_protocol_error(error)))
        if before is not None:
            self.assertEqual(self.combo_state(site), before, "the combo and the typed value are untouched")

    def test_every_closed_list_error_gives_a_visible_status_on_every_site(self):
        for site in SETTINGS_SITES:
            for label, error, kind in PROTOCOL_VECTORS:
                with self.subTest(site=site, vector=label):
                    self.assert_status(site, _transport_for(kind, error), error)
                    self.escaped.clear()

    def test_a_comfyui_non_object_root_gives_a_visible_status_on_the_connection_test_and_on_checkpoints(self):
        for site in ("comfyui_connection", "checkpoints"):
            with self.subTest(site=site):
                error = _capture(COMFY_CALLS["comfyui.list_checkpoints"], _body(b"[]"))
                self.assertIsInstance(error, ComfyUIUnexpectedResponseError)
                self.assert_status(site, _body(b"[]"), error)
                self.escaped.clear()

    def test_a_forge_undecodable_body_gives_a_visible_status_on_the_connection_test(self):
        # A fresh transport per use: an HTTPError body is a one-shot stream.
        for make_transport in (lambda: _body(UNDECODABLE), lambda: _raising(_http_error(UNDECODABLE))):
            error = _capture(FORGE_CALLS["forge.check_connection"], make_transport())
            self.assertIsInstance(error, UnicodeDecodeError)
            self.assert_status("forge_connection", make_transport(), error)
            self.escaped.clear()

    def test_a_non_object_root_on_loras_and_ollama_keeps_the_historical_discovery_status(self):
        self.click("loras", _body(b"[]"))
        self.assertEqual(self.escaped, [])
        self.assertTrue(self.page.lora_discovery_status_label.text().startswith("Découverte impossible : ComfyUI injoignable"))
        self.click("ollama_models", _body(b"[]"))
        self.assertEqual(self.escaped, [])
        self.assertTrue(self.page.ollama_discovery_status_label.text().startswith("Découverte impossible : Ollama injoignable"))

    def test_the_other_engines_connection_label_is_not_touched(self):
        self.click("comfyui_connection", _raising(http.client.BadStatusLine("ABSURD")))
        self.assertEqual(self.page.forge_connection_status_label.text(), "Connexion non testée.")

    def test_historical_engine_error_statuses_are_unchanged(self):
        self.click("comfyui_connection", _raising(urllib.error.URLError("Connection refused")))
        self.assertIn("unreachable", self.page.comfyui_connection_status_label.text().lower())
        self.click("forge_connection", _raising(urllib.error.URLError("Connection refused")))
        self.assertIn("unreachable", self.page.forge_connection_status_label.text().lower())
        self.click("checkpoints", _raising(urllib.error.URLError("Connection refused")))
        self.assertTrue(self.page.checkpoint_discovery_status_label.text().startswith("Découverte impossible : ComfyUI injoignable"))
        self.assertEqual(self.escaped, [])

    def test_success_is_unchanged(self):
        self.click("comfyui_connection", _json({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a"]]}}}}))
        self.assertEqual(self.page.comfyui_connection_status_label.text(), "ComfyUI disponible.")
        self.click("forge_connection", _json([]))
        self.assertEqual(self.page.forge_connection_status_label.text(), "Forge disponible.")
        self.assertEqual(self.escaped, [])

    def test_errors_outside_the_closed_list_still_reach_the_excepthook_and_change_no_status(self):
        for error in (RuntimeError("x"), http.client.HTTPException("got more than 100 headers"), RecursionError("x")):
            with self.subTest(type(error).__name__):
                self.escaped.clear()
                self.click("comfyui_connection", _raising(error))
                self.assertEqual(len(self.escaped), 1)
                self.assertIs(self.escaped[0], error)
                self.assertEqual(self.page.comfyui_connection_status_label.text(), "Connexion non testée.")


# ---------------------------------------------------------------------------------------------------------- InferencePage
INFERENCE_GENERIC_STATUS = (
    "Découverte impossible : moteur injoignable ou configuration invalide. "
    "La saisie manuelle du checkpoint/sampler/scheduler reste disponible."
)


class InferencePageDiagnosticFrontierTest(_QtCase):
    """A real click on the Inference page's refresh button, a real GenerationManager and real engines."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        event_bus = EventBus()
        workspace_manager = WorkspaceManager(event_bus=event_bus)
        workspace_manager.create(Path(self.tmp_dir) / "InferenceProject")
        lora_library_manager = MagicMock()
        lora_library_manager.list_loras.return_value = []
        character_manager = MagicMock()
        character_manager.principal_character = None
        self.comfyui_engine = ComfyUIEngine(URL)
        self.forge_engine = ForgeEngine(URL)
        self.page = InferencePage(
            GenerationManager(self.comfyui_engine),
            workspace_manager,
            MagicMock(),
            MagicMock(),
            character_manager,
            lora_library_manager,
            MagicMock(),
            self.comfyui_engine,
            self.forge_engine,
            comfyui_lifecycle_manager=MagicMock(),
        )
        self.addCleanup(self.page.shutdown)
        self.record_escaped_exceptions()

    def refresh(self, engine_key, transport):
        self.page.engine_combo.setCurrentIndex(self.page.engine_combo.findData(engine_key))
        for combo, items, typed in (
            (self.page.checkpoint_combo, ["c1"], "typed-checkpoint"),
            (self.page.sampler_combo, ["s1"], "typed-sampler"),
            (self.page.scheduler_combo, ["n1"], "typed-scheduler"),
        ):
            combo.clear()
            combo.addItems(items)
            combo.setCurrentText(typed)
        with patch("urllib.request.urlopen", side_effect=transport):
            self.page.refresh_sampler_scheduler_button.click()

    def assert_generic_status_and_untouched_combos(self):
        self.assertEqual(self.escaped, [], "nothing may escape the slot")
        self.assertEqual(self.page.sampler_scheduler_status_label.text(), INFERENCE_GENERIC_STATUS)
        self.assertEqual(self.page.checkpoint_combo.currentText(), "typed-checkpoint")
        self.assertEqual(self.page.sampler_combo.currentText(), "typed-sampler")
        self.assertEqual(self.page.scheduler_combo.currentText(), "typed-scheduler")
        self.assertEqual(self.page.checkpoint_combo.count(), 1)

    def test_closed_list_errors_give_the_unchanged_generic_status_for_both_engines(self):
        for engine_key in ("comfyui", "forge"):
            for label, error, kind in PROTOCOL_VECTORS:
                with self.subTest(engine=engine_key, vector=label):
                    self.refresh(engine_key, _transport_for(kind, error))
                    self.assert_generic_status_and_untouched_combos()
                    self.escaped.clear()

    def test_a_comfyui_non_object_root_and_a_forge_undecodable_body_give_the_generic_status(self):
        self.refresh("comfyui", _body(b"[]"))
        self.assert_generic_status_and_untouched_combos()
        self.refresh("forge", _body(UNDECODABLE))
        self.assert_generic_status_and_untouched_combos()

    def test_the_historical_engine_error_path_and_success_are_unchanged(self):
        self.refresh("comfyui", _raising(urllib.error.URLError("Connection refused")))
        self.assert_generic_status_and_untouched_combos()
        self.page.engine_combo.setCurrentIndex(self.page.engine_combo.findData("forge"))
        replies = iter([_json([{"title": "forge-a"}]), _json([{"name": "euler"}]), _json([{"name": "normal"}])])
        with patch("urllib.request.urlopen", side_effect=lambda request, timeout=None: next(replies)(request, timeout)):
            self.page.refresh_sampler_scheduler_button.click()
        self.assertEqual(self.escaped, [])
        self.assertIn("1 checkpoint(s), 1 sampler(s), 1 scheduler(s)", self.page.sampler_scheduler_status_label.text())


# ----------------------------------------------------------------------------------- lifecycle pre-start check preservation
class _PreStartCheckPreservation:
    """Real engine, controlled transport, QProcess and readiness thread replaced: nothing is ever launched."""

    def make_manager(self):
        manager = self.manager_class()
        manager._start_readiness_worker = MagicMock()
        manager.states = []
        manager.state_changed.connect(manager.states.append)
        return manager

    def start(self, transport):
        manager = self.make_manager()
        with patch.object(self.lifecycle_module, self.resolve_name, return_value=self.launch), \
                patch("urllib.request.urlopen", side_effect=transport), \
                patch.object(self.lifecycle_module, "QProcess") as process_cls:
            manager.start(*self.start_args)
        return manager, process_cls

    def assert_blocked(self, transport, error=None):
        manager, process_cls = self.start(transport)
        self.assertEqual(manager.state, self.START_FAILED)
        self.assertEqual(manager.states, [self.START_FAILED], "never passes through STARTING")
        process_cls.assert_not_called()
        manager._start_readiness_worker.assert_not_called()
        self.assertTrue(manager.last_error_message.startswith(f"{self.engine_name} pre-start check failed unexpectedly ("))
        if error is not None:
            self.assertIn(type(error).__name__ + ":", manager.last_error_message)
        return manager

    def assert_launches(self, transport):
        manager, process_cls = self.start(transport)
        self.assertEqual(manager.state, self.STARTING)
        self.assertEqual(manager.states, [self.STARTING])
        process_cls.assert_called_once()
        manager._start_readiness_worker.assert_called_once()

    def test_closed_list_errors_that_the_engine_lets_through_still_block_the_launch(self):
        for label, error, kind in PROTOCOL_VECTORS:
            with self.subTest(label):
                self.assert_blocked(_transport_for(kind, error), error)

    def test_errors_outside_the_closed_list_still_block_the_launch(self):
        for error in (http.client.CannotSendRequest("x"), http.client.HTTPException("got more than 100 headers"), RuntimeError("x")):
            with self.subTest(type(error).__name__):
                self.assert_blocked(_raising(error), error)

    def test_errors_the_engine_translates_still_proceed_to_the_launch(self):
        for error in (
            urllib.error.URLError("Connection refused"),
            http.client.RemoteDisconnected("Remote end closed connection without response"),
            TimeoutError("timed out"),
        ):
            with self.subTest(type(error).__name__):
                self.assert_launches(_raising(error))

    def test_a_service_that_answers_is_still_reported_as_external(self):
        manager, process_cls = self.start(self.valid_transport)
        self.assertEqual(manager.state, self.EXTERNAL_ACTIVE)
        process_cls.assert_not_called()


class ComfyUIPreStartCheckPreservationTest(_PreStartCheckPreservation, _QtCase):
    manager_class = ComfyUILifecycleManager
    lifecycle_module = comfyui_lifecycle_module
    resolve_name = "resolve_comfyui_launch"
    engine_name = "ComfyUI"
    START_FAILED = comfyui_lifecycle_module.START_FAILED
    STARTING = comfyui_lifecycle_module.STARTING
    EXTERNAL_ACTIVE = comfyui_lifecycle_module.EXTERNAL_ACTIVE
    valid_transport = staticmethod(_json({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a"]]}}}}))
    start_args = ("fake-comfyui-path", "fake-install-path", "http://127.0.0.1:8000")

    def setUp(self):
        self.launch = ComfyUILaunchConfig(
            python_executable=sys.executable, entry_point="main.py", working_directory=".", listen_host="127.0.0.1",
            port=8000, user_directory="user", database_url="sqlite:///x.db",
        )
        self.silence_loggers(comfyui_lifecycle_module, comfyui_worker_module)

    def test_a_non_object_root_is_not_an_engine_error_so_it_still_blocks_the_launch(self):
        for raw in NON_OBJECT_ROOTS:
            with self.subTest(root=raw):
                manager = self.assert_blocked(_body(raw))
                self.assertIn("ComfyUIUnexpectedResponseError", manager.last_error_message)

    def test_an_object_root_without_the_node_is_still_an_engine_error_and_proceeds_to_the_launch(self):
        self.assert_launches(_json({}))
        self.assert_launches(_json({"CheckpointLoaderSimple": None}))


class ForgePreStartCheckPreservationTest(_PreStartCheckPreservation, _QtCase):
    manager_class = ForgeLifecycleManager
    lifecycle_module = forge_lifecycle_module
    resolve_name = "resolve_forge_launch"
    engine_name = "Forge"
    START_FAILED = forge_lifecycle_module.START_FAILED
    STARTING = forge_lifecycle_module.STARTING
    EXTERNAL_ACTIVE = forge_lifecycle_module.EXTERNAL_ACTIVE
    valid_transport = staticmethod(_json([]))
    start_args = ("fake-forge-path", "http://127.0.0.1:7860")

    def setUp(self):
        self.launch = ForgeLaunchConfig(
            working_directory=".", run_bat_path="run.bat", extra_path_dirs=(), listen_host="127.0.0.1", port=7860
        )
        self.silence_loggers(forge_lifecycle_module, forge_worker_module)

    def test_an_undecodable_body_still_blocks_the_launch(self):
        self.assert_blocked(_body(UNDECODABLE))
        self.assert_blocked(_raising(_http_error(UNDECODABLE)))

    def test_a_non_list_root_is_still_an_engine_error_and_proceeds_to_the_launch(self):
        # Characterization of the historical behaviour, not an endorsement of it.
        for raw in NON_LIST_ROOTS:
            with self.subTest(root=raw):
                self.assert_launches(_body(raw))


# ------------------------------------------------------------------------------------------- readiness worker preservation
class _ReadinessWorkerPreservation:

    def run_worker(self, transport, budget=0.05):
        worker = self.worker_class(
            self.engine_class(URL), budget_seconds=budget, poll_interval_seconds=0.01, attempt_timeout_seconds=0.05
        )
        events = []
        worker.ready.connect(lambda: events.append(("ready",)))
        worker.timed_out.connect(lambda: events.append(("timed_out",)))
        worker.cancelled.connect(lambda: events.append(("cancelled",)))
        worker.failed.connect(lambda detail: events.append(("failed", detail)))
        with patch("urllib.request.urlopen", side_effect=transport):
            worker.run()
        return events

    def test_a_truncated_or_garbled_response_is_still_tolerated_until_the_budget_ends(self):
        for label, error, kind in PROTOCOL_VECTORS:
            if isinstance(error, (http.client.BadStatusLine, http.client.IncompleteRead)):
                with self.subTest(label):
                    self.assertEqual(self.run_worker(_transport_for(kind, error)), [("timed_out",)])

    def test_other_protocol_errors_still_end_in_failed(self):
        for label, error, kind in PROTOCOL_VECTORS:
            if not isinstance(error, (http.client.BadStatusLine, http.client.IncompleteRead)):
                with self.subTest(label):
                    events = self.run_worker(_transport_for(kind, error))
                    self.assertEqual(len(events), 1)
                    self.assertEqual(events[0][0], "failed")
                    self.assertTrue(events[0][1].startswith(type(error).__name__ + ":"))

    def test_a_translated_engine_error_keeps_polling_and_a_valid_answer_is_ready(self):
        self.assertEqual(self.run_worker(_raising(urllib.error.URLError("Connection refused"))), [("timed_out",)])
        self.assertEqual(self.run_worker(self.valid_transport), [("ready",)])


class ComfyUIReadinessWorkerPreservationTest(_ReadinessWorkerPreservation, _QtCase):
    worker_class = ComfyUIReadinessWorker
    engine_class = ComfyUIEngine
    valid_transport = staticmethod(_json({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["a"]]}}}}))

    def setUp(self):
        self.silence_loggers(comfyui_worker_module)

    def test_a_non_object_root_still_ends_in_failed(self):
        for raw in NON_OBJECT_ROOTS:
            with self.subTest(root=raw):
                events = self.run_worker(_body(raw))
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0][0], "failed")
                self.assertTrue(events[0][1].startswith("ComfyUIUnexpectedResponseError:"))


class ForgeReadinessWorkerPreservationTest(_ReadinessWorkerPreservation, _QtCase):
    worker_class = ForgeReadinessWorker
    engine_class = ForgeEngine
    valid_transport = staticmethod(_json([]))

    def setUp(self):
        self.silence_loggers(forge_worker_module)

    def test_an_undecodable_body_still_ends_in_failed(self):
        events = self.run_worker(_body(UNDECODABLE))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "failed")
        self.assertTrue(events[0][1].startswith("UnicodeDecodeError:"))


# ------------------------------------------------------------------------------------------------- real sockets, loopback
class _LoopbackHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(2.0)
        data = b""
        try:
            while b"\r\n\r\n" not in data and len(data) < 65536:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                data += chunk
            self.request.sendall(self.server.reply)
            self.request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class _LoopbackServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, reply):
        super().__init__(("127.0.0.1", 0), _LoopbackHandler)
        self.reply = reply
        self.port = self.server_address[1]


ABSURD_STATUS_LINE = b"ABSURD\r\n\r\n"
TRUNCATED_BODY = (
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\nConnection: close\r\n\r\n" + b"x" * 10
)
REDIRECT_TO_A_BAD_PORT = b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:abc/x\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


class LoopbackEndToEndTest(_SettingsCase):
    """The real http.client machinery against a server on 127.0.0.1: the classes that really emerge are the covered ones."""

    def direct(self):
        """No system proxy may sit between a test and its 127.0.0.1 server (restored afterwards)."""
        previous_opener = urllib.request._opener
        urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
        self.addCleanup(setattr, urllib.request, "_opener", previous_opener)

    def serve(self, reply):
        self.direct()
        server = _LoopbackServer(reply)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()

        def stop():
            server.shutdown()
            server.server_close()
            thread.join(2.0)

        self.addCleanup(stop)
        return f"http://127.0.0.1:{server.port}", server.port

    def test_a_non_numeric_port_typed_in_settings_gives_a_visible_status(self):
        self.direct()
        self.page.comfyui_url_edit.setText("http://127.0.0.1:abc")
        self.page.comfyui_test_connection_button.click()
        self.assertEqual(self.escaped, [])
        self.assertEqual(
            self.page.comfyui_connection_status_label.text(),
            "ComfyUI : URL invalide ou réponse inattendue du serveur (InvalidURL: nonnumeric port: 'abc').",
        )

    def test_an_absurd_status_line_gives_a_visible_status_in_settings(self):
        url, _port = self.serve(ABSURD_STATUS_LINE)
        self.page.comfyui_url_edit.setText(url)
        self.page.comfyui_test_connection_button.click()
        self.assertEqual(self.escaped, [])
        self.assertIn("BadStatusLine", self.page.comfyui_connection_status_label.text())

    def test_a_truncated_body_gives_a_visible_status_in_settings_for_forge(self):
        url, _port = self.serve(TRUNCATED_BODY)
        self.page.forge_url_edit.setText(url)
        self.page.forge_test_connection_button.click()
        self.assertEqual(self.escaped, [])
        self.assertIn("IncompleteRead", self.page.forge_connection_status_label.text())

    def test_generation_manager_turns_a_genuine_bad_status_line_into_a_generation_error(self):
        url, _port = self.serve(ABSURD_STATUS_LINE)
        manager = GenerationManager(ComfyUIEngine(url, 2.0))
        with self.assertRaises(GenerationError) as context:
            manager.list_checkpoints(engine=ForgeEngine(url, 2.0), timeout=2.0)
        self.assertTrue(str(context.exception).startswith("BadStatusLine:"))

    def test_a_redirect_to_an_invalid_port_still_blocks_the_comfyui_launch(self):
        # The pre-start URL is fixed (127.0.0.1 and a validated port), but a service on that port can still redirect
        # to an invalid URL: InvalidURL then comes out of the engine raw and the pre-start check must not launch.
        _url, port = self.serve(REDIRECT_TO_A_BAD_PORT)
        self.silence_loggers(comfyui_lifecycle_module)
        launch = ComfyUILaunchConfig(
            python_executable=sys.executable, entry_point="main.py", working_directory=".", listen_host="127.0.0.1",
            port=port, user_directory="user", database_url="sqlite:///x.db",
        )
        manager = ComfyUILifecycleManager()
        manager._start_readiness_worker = MagicMock()
        with patch.object(comfyui_lifecycle_module, "resolve_comfyui_launch", return_value=launch), \
                patch.object(comfyui_lifecycle_module, "QProcess") as process_cls:
            manager.start("p", "i", f"http://127.0.0.1:{port}")
        self.assertEqual(manager.state, comfyui_lifecycle_module.START_FAILED)
        self.assertIn("InvalidURL", manager.last_error_message)
        process_cls.assert_not_called()

    def test_the_readiness_worker_still_tolerates_genuine_garbled_and_truncated_responses(self):
        for reply in (ABSURD_STATUS_LINE, TRUNCATED_BODY):
            with self.subTest(reply=reply[:12]):
                url, _port = self.serve(reply)
                worker = ComfyUIReadinessWorker(ComfyUIEngine(url), 0.3, 0.05, 1.0)
                events = []
                worker.ready.connect(lambda: events.append("ready"))
                worker.timed_out.connect(lambda: events.append("timed_out"))
                worker.failed.connect(lambda detail: events.append("failed"))
                self.silence_loggers(comfyui_worker_module)
                worker.run()
                self.assertEqual(events, ["timed_out"])


if __name__ == "__main__":
    unittest.main()
