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
from collections import defaultdict
from types import MappingProxyType
from typing import Callable, DefaultDict, List


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
        payload = self._freeze(payload)

        for callback in list(self._subscribers[event_name]):
            callback(payload)

    @staticmethod
    def _freeze(payload):
        # Dict payloads are deep-copied before being wrapped read-only, so
        # subscribers can neither reassign a key nor mutate a nested
        # list/dict and have that leak back into the emitter's own state
        # (e.g. a shared list reference inside Workspace.to_dict()).
        if isinstance(payload, dict):
            return MappingProxyType(copy.deepcopy(payload))

        return payload
