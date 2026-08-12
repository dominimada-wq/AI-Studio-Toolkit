# Mission 009 — Settings Domain (Workspace)

Source : historique direct de la conversation de développement + `CHANGELOG.md` (section "Mission 009 — Settings Domain (Workspace)"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire `Settings`, entité Domain Workspace-owned sous forme de **singleton** (`Workspace.settings: Settings`), pas une collection — aucun identifiant, aucune sélection, aucun événement dédié. Domain minimal : `theme`, `language`.

## Modifications principales

- `Settings` (dataclass, 2 champs).
- `Workspace.settings: dict` → `Workspace.settings: Settings` — désérialisation par **garde de type explicite** (`isinstance(x, dict)`), pas une simple vérité (`x or {}`), afin de rejeter aussi les valeurs truthy mal typées (`42`, `"abc"`, `[...]`).
- `SettingsManager(workspace_manager)` — `settings` (lecture), `update(theme=None, language=None)` (écriture idempotente, multi-champs en une seule sauvegarde). **Aucune dépendance à `EventBus`** — ne publie ni ne s'abonne à rien ; `WorkspaceManager.save()` → `WORKSPACE_SAVED` est l'unique canal de notification.
- `SettingsPage` — page réelle, bouton "Enregistrer" explicite, désactivée sans Workspace. **Retrait** des trois anciens champs machine-locale (`python_path`, `comfyui_path`, `onetrainer_path`), jugés Application-level, jamais migrés.
- Commit d'ouverture (dette Mission 008) : test de non-régression — suppression d'un Character possédant Dataset + Training référencé, comportement existant confirmé correct, aucun changement de `CharacterManager` nécessaire.

## Fichiers importants créés ou modifiés

Créés : `settings.py`, `settings_manager.py`, `test_settings_roundtrip.py`.
Modifiés : `workspace.py`, `settings_page.py`, `main_window.py`, `test_character_roundtrip.py`.

## Décisions techniques

- Ownership Workspace-owned, singleton — pas de `settings_id` (même principe que `Workspace` lui-même).
- Clés inconnues sous `settings` (y compris les 3 anciennes clés machine-locale) silencieusement ignorées, jamais conservées.
- Sauvegarde exclusivement par bouton explicite ; saisie non enregistrée abandonnée silencieusement au changement de Workspace, sans dialogue.
- Hors périmètre explicite : Application Settings, Character/Engine/Plugin/Cloud Settings, application réelle du thème à Qt, localisation réelle, événements `SettingChanged`/`SettingReset`/`SettingImported`/`SettingExported`.

## Tests et validations

`test_character_roundtrip.py` (+1) : suppression Character avec Dataset/Training — aucune donnée orpheline. `test_settings_roundtrip.py` (9 tests) : round-trip et défauts Domain, compatibilité historique complète (`absent`/`{}`/`null`/`[]`/`""`/`42`/dict partiel/clés machine-locale/clés inconnues), idempotence et atomicité multi-champs, persistance réelle, isolation entre Workspaces, non-mutation des autres collections, cycle de vie complet `SettingsPage`, absence de duplication d'abonnements.

## Commit correspondant

7 commits, vérifiés par `git log --oneline --reverse` entre `v0.2-mission008` et `v0.2-mission009` :

```
3c78c25 tests: cover Character deletion with Dataset and Training subtree
d749491 Introduce Workspace Settings domain object
f70a072 Type Workspace settings with defensive persistence compatibility
f65315c Add singleton Workspace SettingsManager
15d5ca9 Add functional Workspace SettingsPage
ebd6cd3 tests: add Workspace Settings persistence and lifecycle coverage
94b8cdb docs: document Workspace Settings and close Mission 009
```

Correspond exactement aux "6 commits atomiques" du CHANGELOG (le premier étant une dette héritée de Mission 008, les 5 suivants le développement, le 7ᵉ la clôture documentaire).

## Tag / release correspondant

`v0.2-mission009` — **annoté**, cible `94b8cdbaec91b600954f8f582a002340993cce91`. GitHub Release publiée (confirmé dans l'historique de conversation).

## État final

Mission terminée. `Settings` comme premier singleton Workspace-owned du projet, persistance/restauration réelles des préférences de Workspace, 67 tests d'intégration.
