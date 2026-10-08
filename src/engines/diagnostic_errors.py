"""
Protocol failures that a diagnostic call can surface as raw exceptions.

ComfyUIEngine, ForgeEngine and OllamaEngine translate the failures they know
into their own error type, but let a few transport-level errors of
http.client (and a few shape errors) through untouched. Two kinds of callers
rely on that: the lifecycle managers' pre-start check and the readiness
workers classify those raw errors themselves, so the engines stay unchanged.
Diagnostic callers -- the Settings connection tests and discovery buttons, and
GenerationManager's list_*() used by the Inference page -- have no such
classification and must never let one of these errors escape a Qt slot. They
catch exactly DIAGNOSTIC_PROTOCOL_ERRORS, nothing broader.

The list is closed on purpose: never Exception, never AttributeError, never the
bare http.client.HTTPException (its family also describes the HTTP client's own
state machine, which is not a server failure). It does not cover a bare
HTTPException, RecursionError or OverflowError: those keep propagating.
RemoteDisconnected is a subclass of BadStatusLine, but the engines already
translate it (it is an OSError), so it never reaches a diagnostic caller raw.

Infrastructure layer: no Qt, no UI, no Manager, no Domain.
"""

import http.client

from src.engines.comfyui_engine import ComfyUIUnexpectedResponseError

DIAGNOSTIC_PROTOCOL_ERRORS = (
    http.client.InvalidURL,
    http.client.BadStatusLine,
    http.client.IncompleteRead,
    http.client.LineTooLong,
    http.client.UnknownProtocol,
    UnicodeDecodeError,
    ComfyUIUnexpectedResponseError,
)

_MAX_DETAIL_CHARS = 300


def describe_protocol_error(error) -> str:
    """
    A short, user-presentable description of an ordinary exception --
    "TypeName: message", truncated to _MAX_DETAIL_CHARS. Never raises for an
    ordinary exception: if str(error) itself fails the type name alone is used.
    Only `except Exception` is used, so KeyboardInterrupt and SystemExit are
    never masked.
    """
    try:
        text = "%s: %s" % (type(error).__name__, error)
    except Exception:
        try:
            text = type(error).__name__
        except Exception:
            text = "unexpected exception"
    if len(text) > _MAX_DETAIL_CHARS:
        text = text[: _MAX_DETAIL_CHARS - 3] + "..."
    return text
