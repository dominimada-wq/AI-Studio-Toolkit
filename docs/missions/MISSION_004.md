# Mission 004 — LoRA Domain

Source : `CHANGELOG.md` (section "Mission 004 — LoRA Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `LoRA`, positionnée dans `Character → LoRAs`. Contrairement au minimalisme strict de `Dataset`, le Domain `LoRA` est volontairement étendu dès sa conception (8 champs) pour éviter une migration future.

## Modifications principales

- `LoRA` (dataclass, 8 champs : `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version`).
- `Character.loras` : `list[str]` → `list[LoRA]` ; migration prouvée inutile par recherche Git.
- `LoRAManager` — CRUD, sélection, `add_files()` (déduplication, ordre préservé), miroir exact de `DatasetManager`.
- `LoRAPage` — remplace le placeholder (bouton "Entraîner" hors périmètre retiré).
- `DashboardPage.datasetsCard` — corrigé en ouverture de mission : lisait le champ vestigial `Workspace.datasets` au lieu d'agréger `Character.datasets`.

## Fichiers importants créés ou modifiés

Créés : `lora.py`, `lora_manager.py`, `test_lora_roundtrip.py`.
Modifiés : `dashboard_page.py`, `character.py`, `main_window.py`, `lora_page.py`.

## Décisions techniques

- Domain `LoRA` volontairement plus riche que `Dataset` — exception bornée et justifiée.
- `thumbnail` distinct de `files` (vocabulaire aligné CivitAI/ComfyUI/A1111/Forge).
- Correctif Dashboard "LoRA" (même bug, non encore corrigé côté LoRA) explicitement différé hors de cette mission.

## Tests et validations

`test_lora_roundtrip.py` (7 tests) : cycle complet, ordre/déduplication fichiers, reset sélection à la suppression, reset de contexte, reconstruction `LoRAPage`, absence de duplication d'abonnements, non-impact Dashboard/Images.

## Commit correspondant

`git log --oneline --reverse` entre `v0.2-mission003` et `v0.2-mission004` (7 commits — correspond exactement au chiffre du CHANGELOG) :

```
4dc11ea Fix Dashboard Datasets card to reflect real Character-owned datasets
229dd18 Introduce LoRA domain object
5149e5e Convert Character.loras from list[str] to list[LoRA]
d9d9996 Introduce LoRAManager (CRUD, selection, add_files())
c8c75af Wire LoRAManager and a real LoRAPage into MainWindow
ef8995d Add LoRA lifecycle integration test suite
89bb7c7 docs: document Mission 004 (LoRA domain) in README and CHANGELOG
```

## Tag / release correspondant

`v0.2-mission004` — **annoté**, cible `89bb7c718fe4b8bed498548495249bacdc622d47`.

## État final

Mission terminée. `Character`/`Dataset`/`LoRA` fonctionnels, 22 tests d'intégration, dette d'audit de démarrage corrigée.
