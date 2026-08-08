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

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        if callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)

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
