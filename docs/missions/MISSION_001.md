# Mission 001 — Blueprint Refactoring

Source : `CHANGELOG.md` (section "Mission 001 — Blueprint Refactoring"), vérifié contre `git log`/`git tag`.

## Objectif

Mettre le prototype existant (gestion de "Project" ad hoc, logique métier dispersée dans l'UI, managers non utilisés) en conformité avec l'architecture définie par `docs/blueprint/02_ARCHITECTURE.md`, en cohérence avec le reste du Blueprint. **Aucune fonctionnalité nouvelle ajoutée** — objectif purement structurel, comportement observable préservé.

## Modifications principales

- Introduction du Domain Layer : `src/domain/workspace.py::Workspace` (remplace l'ancienne dataclass `Project`, jamais utilisée). Champ `root` explicitement runtime-only, jamais sérialisé.
- Introduction de l'Infrastructure Layer : `src/infrastructure/storage/workspace_storage.py::WorkspaceStorage` (portage durci de l'ancien `ProjectIO`, erreurs typées `WorkspaceStorageError`).
- Introduction de l'Application Layer : `src/managers/workspace_manager.py::WorkspaceManager` (remplace `ProjectManager`, jamais réellement instancié).
- Introduction du Core/EventBus : `src/core/event_bus.py::EventBus`, pub/sub Qt-indépendant, payloads immuables (copie profonde + vue lecture seule).
- `MainWindow` délègue entièrement à `WorkspaceManager` — suppression de l'accès direct à l'Infrastructure et de l'état dupliqué.
- Extraction de la logique métier hors des widgets (`ImagesPage`).
- Réorganisation : `src/pages/` → `src/ui/pages/` ; suppression de `src/config/`, `src/models/`, `src/widgets/`, `src/project/`.

## Bugs corrigés

1. Dashboard non rafraîchi après création/ouverture d'un projet — corrigé par câblage événementiel.
2. Une ouverture de dossier invalide fermait silencieusement le workspace déjà ouvert — corrigé, protégé par un test de non-régression permanent.
3. `WorkspaceManager.close()` ne publiait plus `workspace.closed` (régression) — détecté et corrigé par le test d'intégration de cette même mission.

## Fichiers importants créés ou modifiés

Créés : `src/domain/workspace.py`, `src/infrastructure/storage/workspace_storage.py`, `src/managers/workspace_manager.py`, `src/core/event_bus.py`, `tests/integration/test_workspace_roundtrip.py`.
Supprimés : `src/config/`, `src/models/`, `src/widgets/`, `src/project/`.

## Décisions techniques

- `Workspace.root` runtime-only, jamais sérialisé (portabilité de `project.json`).
- `WorkspaceStorage` : API dict-only, aucune dépendance vers le Domain.
- `EventBus` : payloads réellement immuables (deep copy + `MappingProxyType`).

## Tests et validations

`tests/integration/test_workspace_roundtrip.py` (2 tests) : `test_full_create_import_save_close_reopen_cycle`, `test_failed_open_does_not_close_current_workspace`.

## Commit correspondant

**Incertitude signalée** : le CHANGELOG indique "9 commits atomiques", mais `git log --oneline --reverse <tag001>` (vérifié) montre **12 commits** dans cette plage, dont plusieurs semblent antérieurs au périmètre strict de la mission (import initial, documentation Blueprint) :

```
9fa32a2 AI Studio Toolkit v0.4 initial
3a29ac3 Add blueprint foundation documentation
804a94e Remove unused empty packages (config, models, widgets)
fe4871b Introduce Workspace domain object
1e3f42f Introduce WorkspaceStorage infrastructure layer
1eef915 Introduce WorkspaceManager, remove dead ProjectManager/Project
c2452ea Introduce EventBus and wire WorkspaceManager to emit events
9d9b391 Document EventBus API design decision (module docstring)
c42ad39 Wire MainWindow to WorkspaceManager; DashboardPage subscribes to events
fc8633e Relocate src/pages/ under src/ui/pages/
3efdfc2 Extract ImagesPage business logic into WorkspaceManager; fix open()
67df364 Remove src/project/; add integration test suite; fix close() event bug
```

Impossible de déterminer avec certitude, à partir de l'historique disponible, quels 9 commits exacts le CHANGELOG désigne — non résolu, à ne pas deviner.

## Tag / release correspondant

`v0.2-mission001` — **annoté** (`git cat-file -t` = `tag`), cible `67df3641d4952a49c42f27e495e609e2ca27fcdb`.

## État final

Mission terminée. Architecture conforme au Blueprint 02, suite de tests d'intégration en place, documentation à jour.
