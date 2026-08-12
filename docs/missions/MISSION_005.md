# Mission 005 — Prompt Domain

Source : `CHANGELOG.md` (section "Mission 005 — Prompt Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `Prompt`, positionnée dans `Character → Prompt Library` (`04_DOMAIN_MODEL.md` §13). Retour à un périmètre strictement minimal (3 champs), après l'exception volontaire de `LoRA`.

## Modifications principales

- `Prompt` (dataclass, 3 champs : `prompt_id`, `name`, `text`).
- `Character.prompts` : `list[str]` → `list[Prompt]` ; migration prouvée inutile.
- `PromptManager` — CRUD, sélection, `update_text()` (remplace le pattern `add_*()` : texte édité en place, pas accumulé), strictement idempotent.
- `PromptsPage` — nouvelle page (aucun placeholder à remplacer).
- `DashboardPage.lorasCard` — corrigé en ouverture de mission (même bug que "Datasets" en Mission 004).

## Fichiers importants créés ou modifiés

Créés : `prompt.py`, `prompt_manager.py`, `prompts_page.py`, `test_prompt_roundtrip.py`.
Modifiés : `dashboard_page.py`, `character.py`, `sidebar.py`, `main_window.py`.

## Décisions techniques

- Catégories de prompts du Blueprint (§13) explicitement différées, pas abandonnées — documentées en commentaire dans `prompt.py` à l'époque (Domain depuis débarrassé de ce type de commentaire par convention ultérieure, voir `CLAUDE.md`).
- `update_text()` remplace `add_images()`/`add_files()` : édition en place, pas d'accumulation.
- Filtrage défensif `isinstance(p, dict)` explicitement qualifié de "compatibilité défensive, jamais migration implicite" — principe de référence pour toute future conversion.

## Tests et validations

`test_prompt_roundtrip.py` (7 tests) : cycle complet, idempotence `update_text()` (espionnage direct de `save()`), reset de contexte, reconstruction `PromptsPage`, absence de duplication d'abonnements, non-impact Dashboard/Images.

## Commit correspondant

`git log --oneline --reverse` entre `v0.2-mission004` et `v0.2-mission005` (7 commits — correspond exactement au chiffre du CHANGELOG) :

```
506457f Fix Dashboard "LoRA" card to aggregate real Character.loras
b16fd20 Introduce Prompt domain object (prompt_id, name, text)
ca86114 Convert Character.prompts from list[str] to list[Prompt]
2ac512f Introduce PromptManager (CRUD, selection, update_text())
f7121e0 Wire PromptManager and a new PromptsPage into MainWindow
adb0c4e Add Prompt lifecycle integration test suite
3a1aca7 docs: document Mission 005 (Prompt domain) in README and CHANGELOG
```

## Tag / release correspondant

`v0.2-mission005` — **annoté**, cible `3a1aca7a7673bfcd358439288526e2e28865dccf`.

## État final

Mission terminée. Quatre entités Domain fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`), 29 tests d'intégration.
