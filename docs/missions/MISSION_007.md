# Mission 007 — Workflow Domain

Source : `CHANGELOG.md` (section "Mission 007 — Workflow Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `Workflow`, deuxième ressource explicitement Workspace-owned après `Model` (`Workspace.workflows`), conformément à l'architecture "Workflow Library" (`04_DOMAIN_MODEL.md` §14, `02_ARCHITECTURE.md` §6/§10/§12).

## Modifications principales

- `Workflow` (dataclass, 3 champs : `workflow_id`, `name`, `file_path` — choix d'implémentation, pas un attribut Blueprint nommé, contrairement à `Model.file_path`/"Installation Path").
- `Workspace.workflows` — nouveau champ, aucune conversion de type (jamais existé auparavant), filtrage défensif `isinstance(w, dict)`.
- `WorkflowManager` — CRUD, `update_file_path()` idempotent, aucune dépendance à `CharacterManager` (deuxième Manager de ce type après `ModelManager`).
- `WorkflowsPage` — nouvelle page, sélection fichier via `QFileDialog` (filtre `*.json`).
- Entrée Sidebar "Workflows" insérée après "Models" (regroupement des deux ressources Workspace-owned).
- Isolation Character vérifiée par preuve inversée par exécution.

## Fichiers importants créés ou modifiés

Créés : `workflow.py`, `workflow_manager.py`, `workflows_page.py`, `test_workflow_roundtrip.py`.
Modifiés : `workspace.py`, `sidebar.py`, `main_window.py`.

## Décisions techniques

- Ownership Workspace-owned retenu malgré une formulation isolée de `01_PRODUCT_REQUIREMENTS.md` §11 suggérant un Character-owned — divergence documentaire identifiée, laissée à une clarification future.
- Filtre `*.json` motivé par les formats `ComfyUI Workflow`/`Forge Preset`/`Fooocus Preset` — ne constitue pas une prise en charge fonctionnelle (aucun parsing/exécution).

## Tests et validations

`test_workflow_roundtrip.py` (9 tests) : round-trip Domain (avec compatibilité `project.json` sans clé `"workflows"`), cycle complet, idempotence `update_file_path()`, suppression + persistance, preuve inversée isolation Character, reconstruction `WorkflowsPage`, absence de duplication d'abonnements, non-impact Dashboard/Images, non-mutation des autres collections Workspace.

## Commit correspondant

`git log --oneline --reverse` entre `v0.2-mission006` et `v0.2-mission007` (6 commits dans la plage git, dont 1 explicitement exclu par le CHANGELOG lui-même) :

```
cb60856 docs: correct Mission 006 modelsCard claim after Mission 007 audit   [HORS Mission 007, cf. note ci-dessus]
6d2b193 Introduce Workflow domain object (workflow_id, name, file_path)
4a96733 Add Workspace workflows collection
85b5aa0 Add WorkflowManager
ac9e86b Wire WorkflowManager and a real WorkflowsPage into MainWindow
4a0ad5d tests: add Workflow roundtrip and persistence coverage
082a577 docs: document Workflow Library and close Mission 007
```

Le CHANGELOG confirme explicitement : *"Le commit `cb60856` ... est une correction documentaire post-publication relative à la Mission 006 ... il n'appartient pas à la Mission 007."* Les 5 commits restants correspondent exactement au chiffre du CHANGELOG ("5 commits atomiques").

## Tag / release correspondant

`v0.2-mission007` — **annoté**, cible `082a577150916b4ad29f4b590f113d62d754d059`.

## État final

Mission terminée. Six entités Domain fonctionnelles, 46 tests d'intégration, deux ressources Workspace-owned cohérentes (`Model`, `Workflow`).
