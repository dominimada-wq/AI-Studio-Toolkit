# Mission 002 — Character Domain

Source : `CHANGELOG.md` (section "Mission 002 — Character Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `Character`, présentée par le Blueprint comme l'entité centrale du logiciel (`04_DOMAIN_MODEL.md` §6). Périmètre volontairement minimal : identité + listes de référence vides (`images`, `datasets`, `loras`, `prompts`, `history`), CRUD complet, persistance via `WorkspaceManager` existant.

## Modifications principales

- `Character` (dataclass, 7 champs, domaine passif, aucune génération d'ID).
- `Workspace.characters` — extension rétrocompatible, robuste à `"characters": null`.
- `CharacterManager` — CRUD/sélection, événements `character.created`/`selected`/`deleted`, `active_character_id` runtime-only réinitialisé sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED`.
- `CharactersPage` — lit exclusivement des dicts, protection `blockSignals()`.
- Aucune migration d'images `Workspace` → `Character` (différée).

## Fichiers importants créés ou modifiés

Créés : `src/domain/character.py`, `src/managers/character_manager.py`, `src/ui/pages/characters_page.py`, `tests/integration/test_character_roundtrip.py`.
Modifiés : `workspace.py`, `sidebar.py`, `main_window.py`.

## Décisions techniques

- `active_character_id` runtime-only, jamais persisté.
- `favorite_models` retiré du périmètre.
- `datasets`/`loras`/`prompts` = listes d'identifiants futurs, pas des chemins.
- Génération de `character_id` dans `CharacterManager.create()`, jamais dans le dataclass.
- Entrée Sidebar "Characters" positionnée juste après Dashboard.

## Tests et validations

`tests/integration/test_character_roundtrip.py` (6 tests) : cycle complet, persistance de suppression, non-réinitialisation sur ouverture échouée, non-impact Dashboard/Images, reconstruction `CharactersPage`, absence de duplication d'abonnements.

## Commit correspondant

`git log --oneline --reverse` entre `v0.2-mission001` et `v0.2-mission002` (9 commits) :

```
e552bc3 Add CHANGELOG.md for Mission 001
a1e9a8b docs: enrich README with badges, architecture diagram, and roadmap table
97c1cab docs: improve README and CHANGELOG
7767277 Introduce Character domain object
10945a0 Extend Workspace with a characters field
d09359b Introduce CharacterManager (CRUD, selection, no lifecycle wiring)
04d95ce Wire CharacterManager and CharactersPage into MainWindow
e45b2d1 Add Character lifecycle integration test suite
1f5c04d docs: document Mission 002 (Character domain) in README and CHANGELOG
```

Le CHANGELOG indique "6 commits atomiques" ; le git log montre 9 commits dans cette plage, dont les 3 premiers (`e552bc3`, `a1e9a8b`, `97c1cab`) semblent être des commits de clôture documentaire de Mission 001 plutôt que Mission 002 elle-même — ce qui ramènerait à 6 commits fonctionnels (`7767277` → `1f5c04d`), cohérent avec le chiffre du CHANGELOG. Hypothèse plausible, non confirmée avec certitude par l'historique disponible — signalée comme telle plutôt que présentée comme un fait établi.

## Tag / release correspondant

`v0.2-mission002` — **annoté**, cible `1f5c04d113cb94fe4ceb909870d9a2150706cd69`.

## État final

Mission terminée. `Character` complet en CRUD, intégré à la navigation, couvert par des tests.
