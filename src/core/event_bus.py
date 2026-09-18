"""
Events are identified by plain string names (e.g. "workspace.created"),
not by a dedicated Event class hierarchy — this mirrors how
02_ARCHITECTURE.md §14 names events, and avoids introducing an envelope
type before any current subscriber needs one (no scaffolding ahead of
need).

Payloads are immutable: publish() deep-copies dict payloads and wraps
them in a MappingProxyType before handing them to subscribers, so no
subscriber can mutate state belonging to the publisher.

No Event wrapper (name + payload + metadata such as timestamp or
correlation id) is introduced yet, intentionally. If a future
requirement needs event replay, persistent history, or metadata beyond
"which event, what data" (e.g. the Blueprint's Job/History system),
that is the point to add one — either as a generic Event envelope
here, or as a dedicated HistoryService that wraps what it receives —
without changing this minimal API for existing publishers/subscribers.
"""

import copy
import logging
from collections import defaultdict
from types import MappingProxyType
from typing import Callable, DefaultDict, List

_logger = logging.getLogger(__name__)


def _describe_callback(callback: Callable) -> str:
    # Mission 136: functions and bound methods (every real subscriber in
    # this repo today) have __qualname__; a callable object generally
    # does not, and falls back to its repr(). Wrapped defensively so a
    # pathological callback (e.g. a broken __repr__) can never itself
    # crash the dispatcher while it's already handling one failure.
    try:
        return getattr(callback, "__qualname__", None) or repr(callback)
    except Exception:
        return "<unrepresentable callback>"


class EventBus:
    """
    Lightweight, Qt-free publish/subscribe event bus.

    Domain and Application-layer code (Workspace, WorkspaceManager) must
    not depend on Qt (02_ARCHITECTURE.md §19: "Domain -> Qt" forbidden;
    Managers never touch Qt widgets). This lets those layers notify the
    Presentation layer without importing PySide6, so the dependency
    direction UI -> Managers stays one-way.
    """

    def __init__(self):
        self._subscribers: DefaultDict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        self._subscribers[event_name].append(callback)

    def publish(self, event_name: str, payload=None) -> None:
        """
        Mission 136: every real publisher in this repo calls publish()
        only after its own mutation/persistence has already succeeded
        (verified across WorkspaceManager/CharacterManager/
        LoRALibraryManager) — EventBus is a synchronous, post-commit
        observation mechanism, never part of the business transaction
        itself. A subscriber's exception is therefore caught and logged
        individually, never re-raised: every other subscriber for this
        event is still attempted, and the caller always sees its
        already-successful operation as a success — never a false
        failure risking a duplicate retry (MISSION_136.md §4.3 documents
        the concrete case this prevents).
        """

        payload = self._freeze(payload)

        for callback in list(self._subscribers[event_name]):
            try:
                callback(payload)
            except Exception:
                _logger.exception(
                    "Subscriber %s raised while handling event %r",
                    _describe_callback(callback), event_name,
                )

    @staticmethod
    def _freeze(payload):
        # Dict payloads are deep-copied before being wrapped read-only, so
        # subscribers can neither reassign a key nor mutate a nested
        # list/dict and have that leak back into the emitter's own state
        # (e.g. a shared list reference inside Workspace.to_dict()).
        if isinstance(payload, dict):
            return MappingProxyType(copy.deepcopy(payload))

        return payload
