# Changelog

Toutes les évolutions notables du projet **AI Studio Toolkit** sont documentées dans ce fichier.

## Sommaire

- **Mission 010 — Application Settings Domain**
  - [Résumé (Mission 010)](#résumé-mission-010)
  - [Statistiques (Mission 010)](#statistiques-mission-010)
  - [Évolutions architecturales (Mission 010)](#évolutions-architecturales-mission-010)
  - [Décisions de conception (Mission 010)](#décisions-de-conception-mission-010)
  - [Hors périmètre (Mission 010)](#hors-périmètre-mission-010)
  - [Tests ajoutés (Mission 010)](#tests-ajoutés-mission-010)
  - [Prochaines étapes (Mission 010)](#prochaines-étapes-mission-010)
  - [État du projet (Mission 010)](#état-du-projet-mission-010)
- **Mission 009 — Settings Domain (Workspace)**
  - [Résumé (Mission 009)](#résumé-mission-009)
  - [Statistiques (Mission 009)](#statistiques-mission-009)
  - [Évolutions architecturales (Mission 009)](#évolutions-architecturales-mission-009)
  - [Décisions de conception (Mission 009)](#décisions-de-conception-mission-009)
  - [Hors périmètre (Mission 009)](#hors-périmètre-mission-009)
  - [Tests ajoutés (Mission 009)](#tests-ajoutés-mission-009)
  - [Prochaines étapes (Mission 009)](#prochaines-étapes-mission-009)
  - [État du projet (Mission 009)](#état-du-projet-mission-009)
- **Mission 008 — Training Domain**
  - [Résumé (Mission 008)](#résumé-mission-008)
  - [Statistiques (Mission 008)](#statistiques-mission-008)
  - [Évolutions architecturales (Mission 008)](#évolutions-architecturales-mission-008)
  - [Décisions de conception (Mission 008)](#décisions-de-conception-mission-008)
  - [Hors périmètre (Mission 008)](#hors-périmètre-mission-008)
  - [Tests ajoutés (Mission 008)](#tests-ajoutés-mission-008)
  - [Prochaines étapes (Mission 008)](#prochaines-étapes-mission-008)
  - [État du projet (Mission 008)](#état-du-projet-mission-008)
- **Mission 007 — Workflow Domain**
  - [Résumé (Mission 007)](#résumé-mission-007)
  - [Statistiques (Mission 007)](#statistiques-mission-007)
  - [Évolutions architecturales (Mission 007)](#évolutions-architecturales-mission-007)
  - [Décisions de conception (Mission 007)](#décisions-de-conception-mission-007)
  - [Tests ajoutés (Mission 007)](#tests-ajoutés-mission-007)
  - [Prochaines étapes (Mission 007)](#prochaines-étapes-mission-007)
  - [État du projet (Mission 007)](#état-du-projet-mission-007)
- **Mission 006 — Model Domain**
  - [Résumé (Mission 006)](#résumé-mission-006)
  - [Statistiques (Mission 006)](#statistiques-mission-006)
  - [Évolutions architecturales (Mission 006)](#évolutions-architecturales-mission-006)
  - [Décisions de conception (Mission 006)](#décisions-de-conception-mission-006)
  - [Tests ajoutés (Mission 006)](#tests-ajoutés-mission-006)
  - [Prochaines étapes (Mission 006)](#prochaines-étapes-mission-006)
  - [État du projet (Mission 006)](#état-du-projet-mission-006)
- **Mission 005 — Prompt Domain**
  - [Résumé (Mission 005)](#résumé-mission-005)
  - [Statistiques (Mission 005)](#statistiques-mission-005)
  - [Évolutions architecturales (Mission 005)](#évolutions-architecturales-mission-005)
  - [Décisions de conception (Mission 005)](#décisions-de-conception-mission-005)
  - [Tests ajoutés (Mission 005)](#tests-ajoutés-mission-005)
  - [Prochaines étapes (Mission 005)](#prochaines-étapes-mission-005)
  - [État du projet (Mission 005)](#état-du-projet-mission-005)
- **Mission 004 — LoRA Domain**
  - [Résumé (Mission 004)](#résumé-mission-004)
  - [Statistiques (Mission 004)](#statistiques-mission-004)
  - [Évolutions architecturales (Mission 004)](#évolutions-architecturales-mission-004)
  - [Décisions de conception (Mission 004)](#décisions-de-conception-mission-004)
  - [Tests ajoutés (Mission 004)](#tests-ajoutés-mission-004)
  - [Prochaines étapes (Mission 004)](#prochaines-étapes-mission-004)
  - [État du projet (Mission 004)](#état-du-projet-mission-004)
- **Mission 003 — Dataset Domain**
  - [Résumé (Mission 003)](#résumé-mission-003)
  - [Statistiques (Mission 003)](#statistiques-mission-003)
  - [Évolutions architecturales (Mission 003)](#évolutions-architecturales-mission-003)
  - [Décisions de conception (Mission 003)](#décisions-de-conception-mission-003)
  - [Tests ajoutés (Mission 003)](#tests-ajoutés-mission-003)
  - [Prochaines étapes (Mission 003)](#prochaines-étapes-mission-003)
  - [État du projet (Mission 003)](#état-du-projet-mission-003)
- **Mission 002 — Character Domain**
  - [Résumé (Mission 002)](#résumé-mission-002)
  - [Statistiques (Mission 002)](#statistiques-mission-002)
  - [Évolutions architecturales (Mission 002)](#évolutions-architecturales-mission-002)
  - [Décisions de conception (Mission 002)](#décisions-de-conception-mission-002)
  - [Tests ajoutés (Mission 002)](#tests-ajoutés-mission-002)
  - [Prochaines étapes](#prochaines-étapes)
  - [État du projet (Mission 002)](#état-du-projet-mission-002)
- **Mission 001 — Blueprint Refactoring**
  - [Résumé de la mission](#résumé-de-la-mission)
  - [Statistiques de la mission](#statistiques-de-la-mission)
  - [Évolutions architecturales principales](#évolutions-architecturales-principales)
  - [Bugs corrigés](#bugs-corrigés)
  - [Tests ajoutés](#tests-ajoutés)
  - [Prochaines étapes (Mission 002)](#prochaines-étapes-mission-002)
  - [Améliorations UX futures](#améliorations-ux-futures)
  - [État du projet](#état-du-projet)

---

## [v0.2-mission010](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission010) — 2026-08-12

### Résumé (Mission 010)

**Mission 010 — Application Settings Domain.** Introduction d'`ApplicationSettings`, objet Domain **Application-level** — un niveau de configuration distinct de `Workspace.settings` (Mission 009), jamais persisté dans `project.json`. Domain minimal : `python_path`, `comfyui_path`, `onetrainer_path`. Stockage dédié dans un fichier séparé, hors de tout Workspace :

```
Workspace                          Application
└── Settings                       └── ApplicationSettings
    ├── theme                          ├── python_path
    └── language                       ├── comfyui_path
         ↓                             └── onetrainer_path
     project.json                           ↓
                                     application_settings.json
```

Ces deux périmètres restent strictement indépendants : Managers, cycles de vie, persistances et canaux de rafraîchissement distincts, sans aucun couplage.

### Statistiques (Mission 010)

| Indicateur | Valeur |
|---|---|
| Commits | 5 |
| Nouveaux fichiers | `application_settings.py`, `application_settings_storage.py`, `application_settings_manager.py`, `test_application_settings_roundtrip.py` |
| Fichiers modifiés | `settings_page.py`, `main_window.py`, `test_settings_roundtrip.py` |
| Tests ajoutés | 13 |
| Total tests du projet | 80/80 verts (67 existants + 13 nouveaux) |

### Évolutions architecturales (Mission 010)

- **`ApplicationSettings`** (`src/domain/application_settings.py`) — dataclass Qt-indépendante, 3 champs, domaine passif.
- **`ApplicationSettingsStorage`** (`src/infrastructure/storage/application_settings_storage.py`) — répertoire résolu via `%LOCALAPPDATA%\AIStudioToolkit\` sous Windows (comportement Windows spécifiquement ; repli déterministe `Path.home()/AppData/Local/AIStudioToolkit` si `LOCALAPPDATA` est absent), fichier `application_settings.json`. Lecture non bloquante : fichier absent, vide, JSON invalide, racine non-`dict` ou erreur `OSError` → valeurs par défaut, jamais d'exception au démarrage. Écriture atomique (fichier temporaire dans le même répertoire, `flush()` + `os.fsync()`, puis `os.replace()`) : le dernier fichier valide est garanti intact si une sauvegarde échoue ; `ApplicationSettingsStorageError` levée dans ce cas.
- **`ApplicationSettingsManager`** (`src/managers/application_settings_manager.py`) — `settings` (lecture) et `update(python_path=None, comfyui_path=None, onetrainer_path=None)` (écriture idempotente, multi-champs en une seule sauvegarde). Stratégie "candidat d'abord" : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire — un échec de sauvegarde laisse donc la mémoire strictement inchangée. Aucune dépendance à `WorkspaceManager`.
- **`SettingsPage`** — deux sections indépendantes (Workspace / Application), chacune avec son propre bouton "Enregistrer". La section Application reste disponible et activée en permanence, y compris sans aucun Workspace ouvert.
- **Événement `application_settings.updated`** — publié uniquement après une sauvegarde réussie ; aucun événement sur mise à jour idempotente ou échec.

### Décisions de conception (Mission 010)

- Séparation stricte des scopes : `python_path`/`comfyui_path`/`onetrainer_path` ne sont jamais écrits dans `project.json` ; `theme`/`language` ne sont jamais écrits dans `application_settings.json`.
- Aucune migration automatique depuis `Workspace.settings` — les deux stockages n'ont jamais été liés, aucune donnée à transférer.
- Résolution du répertoire de configuration en Python standard uniquement (`os`/`pathlib`) — aucune dépendance nouvelle, aucun import Qt dans Infrastructure/Managers.
- Aucun `settings_id` — singleton, même principe que `Settings`/`Workspace`.
- Un événement Workspace ne rafraîchit jamais la section Application, et réciproquement — vérifié dans les deux sens.

### Hors périmètre (Mission 010)

Non implémentés : validation d'existence des chemins, lancement réel de Python/ComfyUI/OneTrainer, clés API, secrets, chiffrement, `Job`, `Engine`, `Plugin`, `Service`, `AI Orchestrator`, `Image` Domain.

### Tests ajoutés (Mission 010)

`tests/integration/test_application_settings_roundtrip.py` (13 tests) : round-trip et défauts du Domain, résolution de `default_directory()` (`LOCALAPPDATA` simulé + repli), matrice de compatibilité de `load()`, round-trip Unicode réel, écriture atomique et préservation du dernier fichier valide en cas d'échec, chargement/idempotence/atomicité de `ApplicationSettingsManager`, cohérence mémoire/disque après échec de sauvegarde, persistance entre deux instances, indépendance totale vis-à-vis de `WorkspaceManager`, cycle de vie complet de la section Application dans `SettingsPage`, étanchéité bidirectionnelle entre les deux sections, absence de duplication d'abonnements. `tests/integration/test_settings_roundtrip.py` adapté à la marge (signature de `SettingsPage`, aucune nouvelle assertion).

### Prochaines étapes (Mission 010)

Sans engagement définitif — Mission 011 à définir selon la roadmap/Blueprint. Dettes restant indépendantes : `Job`/`Engine`/`Plugin`/`Service`/`AI Orchestrator`, migration `Image`, ambiguïté `Training`/`Training History`, références mortes `04_DATA_MODEL.md`/`05_CHARACTER_SYSTEM.md`, nettoyage de `BasePage`.

### État du projet (Mission 010)

**Mission 010 est terminée.** L'application dispose désormais de deux niveaux de préférences strictement séparés — Workspace Settings (`project.json`) et Application Settings (stockage local dédié) — et de 80 tests d'intégration.

---

## [v0.2-mission009](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission009) — 2026-08-12

### Résumé (Mission 009)

**Mission 009 — Settings Domain (Workspace).** Introduction de `Settings`, entité Domain Workspace-owned prenant la forme d'un **singleton** (`Workspace.settings: Settings`) plutôt que d'une collection — aucun identifiant, aucune sélection, aucun événement dédié. Domain minimal : `theme`, `language`. `Workspace.settings` (`dict` non typé depuis Mission 001) est converti vers ce type avec une compatibilité défensive stricte par garde de type, et `SettingsPage` devient une page réelle, remplaçant les trois champs de configuration machine-locale (`python_path`, `comfyui_path`, `onetrainer_path`) — actés comme relevant d'un futur niveau Application Settings, distinct du Workspace.

Le travail a été mené en 6 commits atomiques. Le premier comble une dette de couverture de tests identifiée lors de l'audit d'ouverture de mission (suppression d'un Character possédant Dataset et Training associés) — le comportement existant s'est révélé correct, aucun changement de `CharacterManager` n'a été nécessaire.

### Statistiques (Mission 009)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `settings.py`, `settings_manager.py`, `test_settings_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `settings_page.py`, `main_window.py`, `test_character_roundtrip.py` |
| Tests ajoutés | 10 (1 régression Character/Dataset/Training + 9 Settings) |
| Total tests du projet | 67/67 verts (57 existants + 10 nouveaux) |

### Évolutions architecturales (Mission 009)

- **`Settings`** (`src/domain/settings.py`) — dataclass Qt-indépendante, 2 champs (`theme`, `language`), domaine passif.
- **`Workspace.settings: Settings`** — remplace le `dict` non typé. Désérialisation par garde de type explicite (`isinstance(..., dict)`) plutôt que par simple vérité (`or {}`), afin de rejeter aussi les valeurs truthy mal typées (`42`, `"abc"`, `[...]`), pas seulement les valeurs falsy.
- **`SettingsManager`** (`src/managers/settings_manager.py`) — `settings` (lecture) et `update(theme=None, language=None)` (écriture idempotente, multi-champs en une seule sauvegarde). Aucune dépendance à `EventBus` : ce Manager ne publie ni ne s'abonne à rien.
- **`SettingsPage`** — page réelle : `theme`/`language`, bouton "Enregistrer" explicite, désactivée sans Workspace, texte explicatif indiquant que ces préférences ne sont pas encore appliquées à l'interface.

### Décisions de conception (Mission 009)

- Ownership Workspace-owned, singleton — pas de `settings_id` (même principe que `Workspace` lui-même, qui n'a pas de `workspace_id`).
- `python_path`/`comfyui_path`/`onetrainer_path` jugés Application-level (chemins propres à la machine), jamais Workspace-level — retirés de `SettingsPage`, non migrés, aucun fichier Application Settings créé.
- Clés inconnues sous `settings` (y compris les trois anciennes clés machine-locale) silencieusement ignorées, jamais conservées — décision consciente du passage à un schéma typé, pas un bug de sérialisation.
- Aucun événement Settings dédié : `SettingsManager.update()` → `WorkspaceManager.save()` → `WORKSPACE_SAVED`, seul canal de notification de `SettingsPage`.
- Sauvegarde exclusivement par bouton explicite ; une saisie non enregistrée est silencieusement abandonnée au changement de Workspace, sans dialogue de confirmation.

### Hors périmètre (Mission 009)

Non implémentés, différés : Application Settings, Character/Engine/Plugin/Cloud Settings, application réelle du thème à Qt, localisation réelle de l'interface, événements `SettingChanged`/`SettingReset`/`SettingImported`/`SettingExported`.

### Tests ajoutés (Mission 009)

`tests/integration/test_character_roundtrip.py` (+1) : suppression d'un Character avec Dataset référencé par un Training — aucune donnée orpheline, aucune exception. `tests/integration/test_settings_roundtrip.py` (9) : round-trip et défauts du Domain `Settings`, compatibilité historique complète de `Workspace.settings` (absent/`{}`/`null`/mauvais type/clés inconnues), idempotence et atomicité multi-champs de `SettingsManager.update()`, persistance réelle fermeture/réouverture, isolation stricte entre deux Workspaces, non-mutation des autres collections, cycle de vie complet de `SettingsPage`, absence de duplication d'abonnements.

### Prochaines étapes (Mission 009)

Sans engagement définitif — Mission 010 à définir selon la roadmap/Blueprint. Dettes restant indépendantes, non transformées en feuille de route : migration `Image` vers un vrai Domain object, ambiguïté `Training`/`Training History`, références mortes `04_DATA_MODEL.md`/`05_CHARACTER_SYSTEM.md`, nettoyage de `BasePage`.

### État du projet (Mission 009)

**Mission 009 est terminée.** L'application dispose désormais de `Settings`, entité Domain Workspace-owned sous forme de singleton, avec persistance et restauration réelles des préférences de Workspace, et 67 tests d'intégration.

---

## [v0.2-mission008](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission008) — 2026-08-11

### Résumé (Mission 008)

**Mission 008 — Training Domain.** La Mission 008 introduit `Training` comme nouvelle entité Domain Character-owned. Elle rejoint `Dataset`, `LoRA` et `Prompt` parmi les entités possédées par `Character` (`Character.trainings: list[Training]`). L'ownership retenu s'appuie sur `04_DOMAIN_MODEL.md` §4, qui place explicitement `Trainings` sous `Characters` dans la hiérarchie d'entités ; les arbres structurels de `00_VISION.md`, `01_PRODUCT_REQUIREMENTS.md` et `02_ARCHITECTURE.md` ne nomment à cet emplacement que `Training History` — un concept distinct, non implémenté par cette mission — jamais `Training` elle-même. Cette divergence documentaire est signalée, non résolue.

`Training` introduit également le premier mécanisme d'intégrité référentielle inter-entités du projet : un Dataset du personnage actif référencé par au moins un Training ne peut pas être supprimé tant que cette référence existe.

Le travail a été mené en 6 commits fonctionnels atomiques, chacun avec rapport d'impact validé avant exécution.

### Statistiques (Mission 008)

| Indicateur | Valeur |
|---|---|
| Commits fonctionnels | 6 |
| Nouveaux fichiers | `training.py`, `training_manager.py`, `training_page.py`, `test_training_roundtrip.py` |
| Fichiers modifiés | `character.py`, `dataset_manager.py`, `datasets_page.py`, `main_window.py` |
| Tests Training ajoutés | 11 (`test_training_roundtrip.py`) |
| Total tests du projet | 57/57 verts (46 existants + 11 nouveaux) |

### Évolutions architecturales (Mission 008)

- **`Training`** (`src/domain/training.py`) — dataclass Qt-indépendante, 3 champs (`training_id`, `name`, `dataset_id`), domaine passif. Aucun `character_id` stocké — l'appartenance est implicite via `Character.trainings`, même principe que `Dataset`/`LoRA`/`Prompt`. `dataset_id` est en revanche une vraie référence inter-entités, matérialisée en champ.
- **`Character.trainings`** — nouveau champ `list[Training]`, filtrage défensif `isinstance(t, dict)` à la désérialisation (compatibilité, pas migration — le champ n'a jamais existé sous aucune forme antérieure).
- **`TrainingManager`** (`src/managers/training_manager.py`) — `create(name, dataset_id)`, `select(training_id)`, `delete(training_id)`, `list_trainings()`, `active_training_id` (runtime-only, non persisté, réinitialisé sur changement de personnage et de workspace — pattern Character-owned identique à `Dataset`/`Prompt`). La validation de `dataset_id` est strictement limitée à `active_character.datasets` : un Dataset existant mais appartenant à un autre personnage est refusé. Aucune méthode `update_*()` — Training n'a pas de champ éditable en place.
- **Événements réellement publiés** : `training.created`, `training.selected`, `training.deleted`. Aucun autre événement Training n'existe dans le code.
- **Intégrité référentielle Dataset → Training** (`DatasetManager.is_referenced_by_training()` + garde dans `DatasetManager.delete()`) — un Dataset du personnage actif référencé par au moins un Training ne peut pas être supprimé tant que cette référence existe : pas de cascade, aucun Training supprimé automatiquement, aucun `dataset_id` réécrit. Le Dataset redevient supprimable une fois tous les Trainings qui le référencent supprimés. `DatasetsPage.delete_dataset()` effectue un contrôle préalable pour afficher un message explicite ; `DatasetManager.delete()` réapplique la même règle indépendamment de l'UI (défense en profondeur).
- **`TrainingPage`** — interface CRUD de définition de sessions d'entraînement : lister, créer (avec sélection du Dataset source via `QInputDialog`, noms de Dataset dupliqués désambiguïsés par un fragment de `dataset_id`), sélectionner, supprimer, afficher le Dataset associé. Une référence historique vers un Dataset supprimé s'affiche comme `"Dataset introuvable [dataset_id]"`, sans lever d'exception. Aucun bouton de lancement, aucune console — ce n'est pas un moteur d'entraînement.

### Décisions de conception (Mission 008)

- Ownership Character-owned retenu avec un niveau de preuve Blueprint plus nuancé que pour `Model`/`Workflow` (voir Résumé) — décision documentée, pas présentée comme une certitude absolue.
- Aucun `character_id` sur `Training` — ownership implicite par containment, cohérent avec `Dataset`/`LoRA`/`Prompt`.
- Aucune suppression en cascade lorsqu'un Dataset référencé est visé par une suppression — le refus est la seule réponse, jamais une correction automatique des données.
- `TrainingPage` est la première Page du projet dépendante de deux Managers en lecture (`training_manager` pour les mutations, `dataset_manager` en lecture seule pour peupler le sélecteur) — orchestration au niveau Presentation, aucune dépendance Manager-à-Manager introduite.
- Suppression volontaire du bouton "Lancer l'entraînement" et de la console placeholder hérités du prototype initial, pour que l'interface ne suggère aucune capacité d'exécution non implémentée.

### Hors périmètre (Mission 008)

Non implémentés, différés : `Training Engine`, `Job`, lancement réel d'un entraînement, pause/reprise/annulation, progression, loss, logs d'exécution, `Output LoRA`, `Base Model`, epochs, learning rate, optimizer, batch size, résolution, événements `TrainingStarted`/`TrainingPaused`/`TrainingResumed`/`TrainingFinished`/`TrainingCancelled`/`TrainingFailed`. Aucun de ces éléments n'existe dans le code livré par cette mission.

### Tests ajoutés (Mission 008)

`tests/integration/test_training_roundtrip.py` (11 tests) : round-trip et valeurs par défaut du Domain `Training`, compatibilité de `Character.trainings` (clé absente/`[]`/`None`/liste mixte), création valide et persistance réelle, refus d'un `dataset_id` vide ou inexistant et d'un Dataset appartenant à un autre personnage (atomicité complète : aucune mutation, aucun `save()`, aucun événement), réinitialisation du contexte au changement de personnage/workspace, suppression active/non-active/invalide avec persistance, cycle complet d'intégrité référentielle Dataset → Training (blocage, absence de cascade, déblocage), isolation des autres collections (y compris du Dataset référencé lui-même), reconstruction de `TrainingPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact Dashboard/Images.

### Prochaines étapes (Mission 008)

Sans engagement définitif :

- Mission 009 — à définir selon la roadmap/Blueprint.
- *(Dette documentaire Blueprint constatée pendant l'audit d'ouverture de mission, indépendante du Domain Training : `01_PRODUCT_REQUIREMENTS.md` référence `04_DATA_MODEL.md` et `05_CHARACTER_SYSTEM.md`, deux fichiers absents de `docs/blueprint/`. Correction laissée à une décision documentaire séparée.)*

### État du projet (Mission 008)

**Mission 008 est terminée.** L'application dispose désormais de `Training` comme nouvelle entité Domain Character-owned, aux côtés de `Dataset`, `LoRA` et `Prompt`, avec une première intégrité référentielle inter-entités (Dataset → Training), et 57 tests d'intégration.

---

## [v0.2-mission007](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission007) — 2026-08-11

### Résumé (Mission 007)

**Mission 007 — Workflow Domain.** Introduction de l'entité `Workflow`, sixième objet du Domain Model et deuxième ressource explicitement Workspace-owned après `Model` (`Workspace.workflows`), conformément à l'architecture "Workflow Library" retenue pour cette mission (`04_DOMAIN_MODEL.md` §14, `02_ARCHITECTURE.md` §6/§10/§12). Domain minimal : `workflow_id`, `name`, `file_path`. `file_path` est un choix d'implémentation propre à cette mission — le Blueprint ne nomme aucun attribut de type chemin pour `Workflow` (contrairement à `Model`, dont `file_path` traduit directement l'attribut "Installation Path") ; il permet uniquement de référencer un fichier externe, sans parsing, validation, détection d'origine ni exécution de son contenu.

Le travail a été mené en 5 commits atomiques, chacun avec rapport d'impact validé avant exécution. *(Le commit `cb60856`, situé chronologiquement entre la clôture de la Mission 006 et l'ouverture de cette mission, est une correction documentaire post-publication relative à la Mission 006 — il n'appartient pas à la Mission 007.)*

### Statistiques (Mission 007)

| Indicateur | Valeur |
|---|---|
| Commits | 5 |
| Nouveaux fichiers | `workflow.py`, `workflow_manager.py`, `workflows_page.py`, `test_workflow_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 9 (8 habituels + 1 dédié à l'isolation des collections Workspace) |
| Total tests du projet | 46/46 verts (37 existants + 9 nouveaux) |

### Évolutions architecturales (Mission 007)

- **`Workflow`** (`src/domain/workflow.py`) — dataclass Qt-indépendant, 3 champs (`workflow_id`, `name`, `file_path`), domaine passif.
- **`Workspace.workflows`** — nouveau champ `list[Workflow]` ; aucune conversion de type (contrairement à `models`/`datasets`/`loras`/`prompts`), le champ n'ayant jamais existé sous aucune forme auparavant. Sérialisation en liste de dictionnaires (`to_dict()`), désérialisation avec filtrage défensif `isinstance(w, dict)` (compatibilité, pas migration). Un `project.json` antérieur à cette mission, sans clé `"workflows"`, se charge normalement et produit `workflows == []`.
- **`WorkflowManager`** (`src/managers/workflow_manager.py`) — CRUD (`create`, `select`, `delete`), sélection via `active_workflow_id` (runtime-only), `update_file_path()` strictement idempotent (chaîne vide acceptée comme valeur légitime). Persistance déléguée à `WorkspaceManager.save()`. **Aucune dépendance à `CharacterManager`**, deuxième Manager du projet dans ce cas après `ModelManager`.
- **Événements réellement publiés** : `workflow.created`, `workflow.selected`, `workflow.deleted`. `update_file_path()` ne publie aucun événement dédié — la mutation est suivie de `WorkspaceManager.save()`, qui émet `workspace.saved` (seul mécanisme notifiant l'UI de ce changement). Ni `workflow.updated`, ni `workflow.imported`, ni `workflow.executed` (évoqués par le Blueprint §14) ne sont implémentés.
- **`WorkflowsPage`** — nouvelle page (`workflows_page.py`), création/sélection/suppression, association d'un fichier via `QFileDialog` (filtre `Workflows (*.json)`), affichage en lecture seule de `file_path`. Fonctionne indépendamment de l'existence ou de la sélection d'un `Character` — vérifié par exécution.
- **Intégration Sidebar/MainWindow** — nouvelle entrée "Workflows" insérée immédiatement après "Models" (regroupement des deux ressources Workspace-owned), alignement Sidebar/`QStackedWidget` vérifié sur les 11 entrées.
- **Isolation Character** — vérifiée par preuve inversée par exécution : la création, sélection ou suppression d'un `Character` n'a strictement aucun effet sur `active_workflow_id`, `WorkflowsPage`, ni sur les collections `workspace.models`/`.datasets`/`.loras`/`.characters`.

### Décisions de conception (Mission 007)

- `file_path` : choix d'implémentation minimal de Mission 007 permettant l'association à un fichier externe. Non implémenté dans Mission 007 / différé pour toute notion de parsing, validation ou exécution du contenu référencé. Ce n'est pas la traduction d'un attribut Blueprint nommé.
- Les formats `ComfyUI Workflow`, `Forge Preset`, `Fooocus Preset` (`01_PRODUCT_REQUIREMENTS.md`, "Workflow Library", priorité P1) sont les cas d'usage ayant motivé le filtre `*.json` du sélecteur de fichier — cela ne constitue **pas** une prise en charge fonctionnelle de ces formats : le fichier n'est ni ouvert, ni analysé, ni exécuté.
- **Ownership des workflows** — Mission 007 implémente `Workflow` comme ressource appartenant au `Workspace` (`Workspace.workflows`), conformément à l'architecture de Workflow Library retenue pour cette mission. Une formulation de `01_PRODUCT_REQUIREMENTS.md` §11 indique qu'un Character stocke ses propres workflows ; cette divergence documentaire est identifiée et laissée à une clarification architecturale ultérieure. Aucun couplage `WorkflowManager` ↔ `CharacterManager` n'est introduit dans Mission 007.
- `create()` reste un miroir strict de `ModelManager`/`DatasetManager`/`LoRAManager`/`PromptManager` : aucune validation de nom côté Manager, aucune sélection automatique après création.
- Attributs Blueprint `Description`, `Compatible Engine`, `Inputs`, `Outputs`, `Parameters`, `Version`, `Category`, `Author`, `Thumbnail`, `Tags`, `Metadata` : non implémentés dans Mission 007 / différés — aucun engagement n'est pris sur leur forme future.

### Tests ajoutés (Mission 007)

`tests/integration/test_workflow_roundtrip.py` (9 tests) : round-trip et valeurs par défaut du Domain `Workflow` (y compris compatibilité historique explicite d'un `project.json` sans clé `"workflows"`), cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture avec persistance disque réelle, idempotence complète d'`update_file_path()`, suppression avec persistance, preuve inversée d'isolation Character, reconstruction de `WorkflowsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact Dashboard/Images, et un test dédié vérifiant qu'aucune opération `WorkflowManager` ne mute `workspace.models`/`.datasets`/`.loras`/`.characters`.

### Prochaines étapes (Mission 007)

Sans engagement définitif :

- Clarification future de la tension documentaire Workspace-owned / Character-owned identifiée dans `01_PRODUCT_REQUIREMENTS.md` §11.
- Mission 008 — à définir selon la roadmap/Blueprint.

### État du projet (Mission 007)

**Mission 007 est terminée.** L'application dispose désormais de six entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`, `Model`, `Workflow`), 46 tests d'intégration, et deux ressources Workspace-owned cohérentes (`Model`, `Workflow`).

---

## [v0.2-mission006](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission006) — 2026-08-11

### Résumé (Mission 006)

**Mission 006 — Model Domain.** Introduction de l'entité `Model`, cinquième objet du Domain Model après `Character`, `Dataset`, `LoRA` et `Prompt` — et la première rattachée exclusivement au `Workspace`, pas au `Character`. Cette conclusion a été démontrée par huit citations Blueprint indépendantes (`04_DOMAIN_MODEL.md` §4/§5/§10/§27/§28, `02_ARCHITECTURE.md` §10/§11/§12), toutes convergentes : *"Models belong to the Workspace Library."* Le Domain reste volontairement minimal (`model_id`, `name`, `file_path`), dans la continuité directe de `Dataset`/`Prompt`.

Conséquence architecturale majeure : `ModelManager` est le **premier Manager du projet sans dépendance à `CharacterManager`**. `active_model_id` ne se réinitialise que sur les événements de cycle de vie du workspace, jamais sur un changement de personnage — l'inverse exact de ce qui avait été vérifié pour `LoRAManager`/`PromptManager`, et démontré ici par une preuve comportementale par exécution dédiée.

Le travail a été mené en 6 commits atomiques, chacun avec rapport d'impact validé avant exécution.

### Statistiques (Mission 006)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `model.py`, `model_manager.py`, `test_model_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `models_page.py` (placeholder statique → page réelle), `main_window.py` |
| Tests d'intégration ajoutés | 8 (7 habituels + 1 dédié au round-trip et aux valeurs par défaut du Domain `Model`) |
| Total tests du projet | 37/37 verts (29 existants + 8 nouveaux) |

### Évolutions architecturales (Mission 006)

- **`Model`** (`src/domain/model.py`) — dataclass Qt-indépendant, 3 champs (`model_id`, `name`, `file_path`), domaine passif.
- **`Workspace.models`** — `list` (non typé, jamais peuplé) → `list[Model]` ; aucune preuve historique de migration nécessaire au sens strict (le champ n'avait jamais été typé, contrairement aux conversions `list[str]` précédentes), même principe de compatibilité défensive (`isinstance(m, dict)`).
- **`ModelManager`** (`src/managers/model_manager.py`) — CRUD, sélection, `update_file_path()` (miroir du contrat d'idempotence de `update_text()`) ; **aucune dépendance à `CharacterManager`**, `active_model_id` réinitialisé uniquement sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED`.
- **`ModelsPage`** — remplace le placeholder à liste statique (`"Flux"`, `"SDXL"`...) ; sélection de fichier via `QFileDialog.getOpenFileName` (singulier) plutôt que le pattern d'import multi-fichiers ; fonctionne sans qu'aucun personnage n'existe.

### Décisions de conception (Mission 006)

- `Model` rattaché exclusivement au `Workspace`, jamais au `Character` — démontré par le Blueprint, pas supposé.
- `file_path` scalaire, pas une liste — nommage aligné sur la convention déjà en place dans le projet (`LoRA.files`, `lora_page.py`) pour désigner un chemin de fichier individuel.
- `create()` reste un miroir strict des trois Managers précédents : **aucune validation de nom** côté Manager, cette responsabilité reste exclusivement dans la Page — décision explicite pour ne pas introduire de divergence où `Model` deviendrait plus robuste que `Dataset`/`LoRA`/`Prompt`.
- Pas de sélection automatique après `create()` — comportement déjà existant pour les trois domaines précédents, reproduit à l'identique plutôt que "corrigé" à l'occasion de cette mission.
- Chaîne vide (`""`) traitée comme valeur légitime de `file_path` ("aucun fichier associé"), pas une erreur à valider.
- Hors périmètre, différé et non abandonné : scan automatique de fichiers, métadonnées du Domain (`provider`, `hash`, `architecture`, `thumbnail`...), `Character.favorite_models`.

### Tests ajoutés (Mission 006)

`tests/integration/test_model_roundtrip.py` (8 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_file_path()` (y compris la chaîne vide comme changement réel), suppression avec persistance, **preuve inversée** qu'un changement de personnage ne réinitialise jamais `active_model_id`, reconstruction de `ModelsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images, et un test dédié au round-trip `to_dict()`/`from_dict()` du Domain `Model` (valeurs par défaut, clé absente, filtrage défensif sur liste mixte).

### Prochaines étapes (Mission 006)

Sans engagement définitif :

- *(Correction post-publication, audit Mission 007 : la carte Dashboard "Models" ne nécessitait en réalité aucun correctif — sa lecture de `Workspace.models` était déjà correcte depuis la Mission 001 ; seule la donnée était vide avant cette mission. L'affirmation initiale ci-dessus était erronée.)*
- Poursuite du Domain Model : `Job`, `Engine`, `Plugin`, couche Services — périmètre exact à préciser dans son propre rapport d'impact.

### État du projet (Mission 006)

**Mission 006 est terminée.** L'application dispose désormais de cinq entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`, `Model`), 37 tests d'intégration, et un premier pattern architectural "ressource partagée au niveau Workspace" validé et documenté.

---

## [v0.2-mission005](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission005) — 2026-08-11

### Résumé (Mission 005)

**Mission 005 — Prompt Domain.** Introduction de l'entité `Prompt`, quatrième objet du Domain Model après `Character`, `Dataset` et `LoRA`, positionnée dans la hiérarchie `Character → Prompt Library` (`docs/blueprint/04_DOMAIN_MODEL.md` §13). Contrairement à l'extension volontaire de `LoRA` en Mission 004, le Domain `Prompt` revient à un périmètre strictement minimal (`prompt_id`, `name`, `text`), cohérent avec la discipline appliquée à `Character`/`Dataset`. Les catégories de prompts prévues par le Blueprint (`Master Prompt`, `Negative Prompt`, `Generation Prompt`, `Training Prompt`, `Template Prompt`, `Dynamic Prompt`...) sont **explicitement différées, non abandonnées** — décision d'architecture documentée directement dans le code (`src/domain/prompt.py`) : leur ajout n'aura de sens que le jour où un consommateur réel existera (pipeline de génération, entraînement, bibliothèque de prompts filtrable), et ne nécessitera aucune migration puisqu'il s'agirait d'un simple ajout de champ scalaire avec valeur par défaut.

Le travail a été mené en 7 commits atomiques, chacun avec rapport d'impact validé avant exécution. Comme pour les Missions 003/004, deux points sensibles ont fait l'objet d'une preuve comportementale par exécution plutôt que par seule lecture de code : l'indépendance de deux instances de `PromptManager` vis-à-vis de l'`EventBus`, et l'idempotence stricte du contrat `update_text()` (aucune sauvegarde ni événement publié lorsque le texte est inchangé).

### Statistiques (Mission 005)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `prompt.py`, `prompt_manager.py`, `prompts_page.py`, `test_prompt_roundtrip.py` |
| Fichiers modifiés | `dashboard_page.py`, `character.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 7 |
| Bug corrigé | Carte Dashboard "LoRA" lisait le champ vestigial `Workspace.loras` au lieu d'agréger `Character.loras` (même bug que "Datasets" en Mission 004, corrigé en ouverture de mission) |
| Total tests du projet | 29/29 verts (22 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 005)

- **`Prompt`** (`src/domain/prompt.py`) — dataclass Qt-indépendant, 3 champs (`prompt_id`, `name`, `text`), domaine passif.
- **`Character.prompts`** — `list[str]` → `list[Prompt]` ; migration prouvée inutile par recherche exhaustive de l'historique Git, même méthodologie que `Character.datasets`/`Character.loras`.
- **`PromptManager`** (`src/managers/prompt_manager.py`) — CRUD, sélection, `update_text()` en remplacement du pattern `add_images()`/`add_files()` (texte scalaire édité en place plutôt que liste accumulée), strictement idempotent.
- **`PromptsPage`** — nouvelle page (aucun placeholder à remplacer, contrairement à `Dataset`/`LoRA`) ; nouvelle entrée `sidebar.py` entre "LoRA" et "Training" ; lit exclusivement des dicts via `PromptManager.list_prompts()`.
- **`DashboardPage.lorasCard`** — corrigé en ouverture de mission : agrège désormais les `Character.loras` réels au lieu du champ vestigial `Workspace.loras`.

### Décisions de conception (Mission 005)

- Domain `Prompt` volontairement minimal — retour à la discipline `Dataset`/`Character` après l'exception justifiée de `LoRA`.
- Catégories/types de prompts (Blueprint §13) explicitement différées, pas abandonnées : documentées en commentaire dans `prompt.py`, seront réintroduites dès qu'un consommateur réel existera, sans rupture de compatibilité. Lors de cette réintroduction future, elles devront être implémentées comme une extension naturelle du Domain `Prompt` existant, sans remettre en cause le modèle minimal ni casser la compatibilité des données déjà persistées.
- `update_text()` remplace `add_images()`/`add_files()` : un texte s'édite en place, il ne s'accumule pas — aucune logique de déduplication n'a de sens ici.
- Filtrage défensif `isinstance(p, dict)` dans `Character.from_dict()` explicitement qualifié de **compatibilité défensive**, jamais de migration implicite — principe désormais posé comme référence pour toute future conversion `list[str] → list[Objet]` du projet.
- Correctif `lorasCard` traité en ouverture de mission, même pattern que `datasetsCard` en Mission 004.

### Tests ajoutés (Mission 005)

`tests/integration/test_prompt_roundtrip.py` (7 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_text()` (no-op sans sauvegarde ni événement, vérifié par espionnage direct de `WorkspaceManager.save()`), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `PromptsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 005)

Sans engagement définitif :

- Poursuite du Domain Model : `Model` — ressource partagée au niveau Workspace (`Workspace → Models → Characters`), un pattern architectural encore jamais implémenté dans ce projet, nécessitant sa propre conception avant toute implémentation.
- Réintroduction des catégories/types de `Prompt` dès qu'une fonctionnalité réelle le justifiera.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 005)

**Mission 005 est terminée.** L'application dispose désormais de quatre entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`), 29 tests d'intégration.

---

## [v0.2-mission004](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission004) — 2026-08-10

### Résumé (Mission 004)

**Mission 004 — LoRA Domain.** Introduction de l'entité `LoRA`, troisième objet du Domain Model après `Character` et `Dataset`, positionnée dans la hiérarchie `Character → LoRAs` (`docs/blueprint/04_DOMAIN_MODEL.md`). Contrairement au minimalisme strict appliqué à `Dataset`, le Domain `LoRA` a été volontairement étendu dès sa conception (8 champs : `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version`) — décision explicite pour éviter une migration future, compte tenu de la richesse intrinsèque d'un LoRA par rapport à un simple regroupement d'images. Comme `Dataset.images` en Mission 003, `LoRA.files` est fonctionnel dès son introduction.

Le travail a été mené en 7 commits atomiques, chacun avec rapport d'impact validé avant exécution. Deux points sensibles ont fait l'objet d'une preuve comportementale par exécution plutôt que par seule lecture de code : l'indépendance de deux instances de `LoRAManager` vis-à-vis de l'`EventBus`, et l'équivalence stricte du contrat `add_files()`/`DatasetManager.add_images()`.

### Statistiques (Mission 004)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `lora.py`, `lora_manager.py`, `test_lora_roundtrip.py` |
| Fichiers modifiés | `dashboard_page.py`, `character.py`, `main_window.py`, `lora_page.py` (placeholder → page réelle) |
| Tests d'intégration ajoutés | 7 |
| Bug corrigé | Carte Dashboard "Datasets" lisait le champ vestigial `Workspace.datasets` au lieu d'agréger `Character.datasets` (corrigé en ouverture de mission) |
| Total tests du projet | 22/22 verts (15 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 004)

- **`LoRA`** (`src/domain/lora.py`) — dataclass Qt-indépendant, 8 champs, domaine passif (aucune génération d'ID).
- **`Character.loras`** — `list[str]` → `list[LoRA]` (dépendance Domain→Domain, autorisée) ; migration de données prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle n'a jamais existé sous l'ancien format), même méthodologie que `Character.datasets` en Mission 003.
- **`LoRAManager`** (`src/managers/lora_manager.py`) — CRUD, sélection, `add_files()` avec déduplication et préservation de l'ordre ; `active_lora_id` runtime-only, réinitialisé au changement de personnage actif ou de workspace ; miroir exact de `DatasetManager`.
- **`LoRAPage`** — remplace le placeholder existant (qui incluait un bouton "Entraîner" hors périmètre, retiré) ; miroir strict de `DatasetsPage` ; lit exclusivement des dicts via `LoRAManager.list_loras()`.
- **`DashboardPage.datasetsCard`** — corrigé en ouverture de mission : agrège désormais les `Character.datasets` réels au lieu du champ vestigial `Workspace.datasets`.

### Décisions de conception (Mission 004)

- Domain `LoRA` volontairement plus riche que `Dataset` dès sa création — exception bornée et justifiée au minimalisme strict appliqué à `Character`/`Dataset`.
- `thumbnail` distinct de `files` : un aperçu n'est pas un fichier constitutif du LoRA — distinction reprise de CivitAI/ComfyUI/A1111/Forge, vocabulaire aligné sur celui du Blueprint pour `Model`/`Workflow`.
- `add_files()` reste générique vis-à-vis des types de fichiers (le Manager ne connaît aucune extension), à l'image d'`add_images()`.
- Correctif de la carte Dashboard "LoRA" (même bug que "Datasets", non encore corrigé) explicitement différé hors du Commit 5, pour préserver le découpage atomique de la mission — sera traité séparément si décidé.

### Tests ajoutés (Mission 004)

`tests/integration/test_lora_roundtrip.py` (7 tests) : cycle complet création/sélection/import/sauvegarde/fermeture/réouverture, préservation de l'ordre et déduplication des fichiers, réinitialisation de la sélection à la suppression de la LoRA active (avec persistance vérifiée), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `LoRAPage` sur les événements pertinents, absence de duplication d'abonnements entre deux instanciations, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 004)

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Poursuite du Domain Model : `Prompt` (déjà anticipé par `Character.prompts`, actuellement vide), ou `Model`.
- Correctif différé de la carte Dashboard "LoRA" (même nature que le correctif "Datasets" traité en Mission 004).
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, toujours différée.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 004)

**Mission 004 est terminée.** L'application dispose désormais de trois entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`), 22 tests d'intégration, et une dette identifiée lors de l'audit de démarrage corrigée.

---

## [v0.2-mission003](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission003) — 2026-08-10

### Résumé (Mission 003)

**Mission 003 — Dataset Domain.** Introduction de l'entité `Dataset`, deuxième objet du Domain Model après `Character`, positionnée dans la hiérarchie `Character → Datasets` (`docs/blueprint/04_DOMAIN_MODEL.md` §7). Contrairement à `Character.images` en Mission 002, `Dataset.images` est fonctionnel dès cette mission : import d'images propre à chaque dataset, avec déduplication et préservation de l'ordre — un chemin d'import indépendant de `Workspace.images`/`ImagesPage`, sans migration requise.

Le travail a été mené en 7 commits atomiques, chacun accompagné d'un rapport d'impact validé avant exécution, avec un niveau de preuve comportementale renforcé par rapport aux missions précédentes (espionnage d'appels, vérification directe des abonnements `EventBus`, tests sur widgets Qt réels plutôt que sur les managers isolés).

### Statistiques (Mission 003)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `dataset.py`, `dataset_manager.py`, `test_dataset_roundtrip.py` |
| Fichiers modifiés | `character.py`, `main_window.py`, `datasets_page.py` (placeholder → page réelle), `workspace_manager.py` |
| Tests d'intégration ajoutés | 7 |
| Dette technique corrigée | Import direct Presentation → Infrastructure (`WorkspaceStorageError` dans `MainWindow`) remplacé par `WorkspaceManagerError` |
| Total tests du projet | 15/15 verts (8 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 003)

- **`Dataset`** (`src/domain/dataset.py`) — dataclass Qt-indépendant, 3 champs (`dataset_id`, `name`, `images`), domaine passif (aucune génération d'ID).
- **`Character.datasets`** — `list[str]` → `list[Dataset]` (dépendance Domain→Domain, autorisée) ; migration de données prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle n'a jamais existé sous l'ancien format).
- **`DatasetManager`** (`src/managers/dataset_manager.py`) — CRUD, sélection, `add_images()` fonctionnel avec déduplication et préservation de l'ordre ; `active_dataset_id` runtime-only, réinitialisé au changement de personnage actif ou de workspace.
- **`DatasetsPage`** — remplace le placeholder existant ; CRUD + import d'images à deux niveaux (liste des datasets avec compteur d'images, liste des images du dataset sélectionné) ; lit exclusivement des dicts via `DatasetManager.list_datasets()`, jamais des objets `Dataset` directement.
- **`WorkspaceManagerError`** — nouvelle exception publique portée par `WorkspaceManager`, remplace l'import direct de `WorkspaceStorageError` (Infrastructure) dans `MainWindow`, corrigeant une dette identifiée lors de l'audit de démarrage de mission.

### Décisions de conception (Mission 003)

- `Dataset.images` fonctionnel dès cette mission, contrairement à `Character.images` en Mission 002 — import propre à chaque dataset, sans dépendre d'une migration de `Workspace.images`.
- Ownership de `Dataset` implicite (pas de `character_id` stocké), même principe que `Character` vis-à-vis de `Workspace`.
- `add_images(paths)` opère sur le dataset actif implicitement, sans paramètre d'identifiant — même logique que `WorkspaceManager.add_images()`.
- Robustesse de désérialisation : `Character.from_dict()` filtre explicitement les entrées non-`dict` dans `datasets` plutôt que de laisser fuiter une `AttributeError`.
- Correctif de dette technique (`WorkspaceManagerError`) traité en ouverture de mission plutôt qu'en fin, pour établir le bon pattern avant que `DatasetManager` n'en ait besoin à son tour.

### Tests ajoutés (Mission 003)

`tests/integration/test_dataset_roundtrip.py` (7 tests) : cycle complet création/sélection/import/sauvegarde/fermeture/réouverture, préservation de l'ordre et déduplication des images, réinitialisation de la sélection à la suppression du dataset actif (avec persistance vérifiée), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `DatasetsPage` sur les événements pertinents (y compris `workspace.saved` après un import), absence de duplication d'abonnements entre deux instanciations, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 003)

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Poursuite du Domain Model : `LoRA`/`Prompt` (déjà anticipés par `Character.loras`/`Character.prompts`, actuellement vides), ou `Model`.
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, toujours différée.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 003)

**Mission 003 est terminée.** L'application dispose désormais de deux entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`), 15 tests d'intégration, et une dette technique identifiée lors de l'audit post-Mission-002 corrigée.

---

## [v0.2-mission002](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission002) — 2026-08-10

### Résumé (Mission 002)

**Mission 002 — Character Domain.** Introduction de l'entité `Character`, présentée par le Blueprint comme l'entité centrale du logiciel (`docs/blueprint/04_DOMAIN_MODEL.md` §6). Périmètre volontairement minimal : identité + listes de référence vides (`images`, `datasets`, `loras`, `prompts`, `history`), CRUD complet (créer/sélectionner/supprimer), persistance dans `project.json` via le mécanisme `WorkspaceManager` déjà existant — aucune nouvelle infrastructure de stockage. La migration des images de `Workspace` vers `Character` est explicitement différée à une mission future.

Le travail a été mené en 6 commits atomiques, chacun accompagné d'un rapport d'impact validé avant exécution — même discipline que la Mission 001.

### Statistiques (Mission 002)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `character.py`, `character_manager.py`, `characters_page.py`, `test_character_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 6 |
| Bugs applicatifs introduits | 0 (une erreur de comptage dans un test a été trouvée et corrigée **dans le test**, pas dans le code applicatif) |
| Nouvelle page Sidebar | Characters (9ᵉ page, positionnée juste après Dashboard) |

### Évolutions architecturales (Mission 002)

- **`Character`** (`src/domain/character.py`) — dataclass Qt-indépendant, 7 champs (`character_id`, `name`, `images`, `datasets`, `loras`, `prompts`, `history`), domaine passif (aucune génération d'ID).
- **`Workspace.characters`** — extension rétrocompatible, liste de vrais objets `Character` (dépendance Domain→Domain, autorisée), robuste à `"characters": null`.
- **`CharacterManager`** (`src/managers/character_manager.py`) — CRUD/sélection, persistance déléguée à `WorkspaceManager.save()`, publication d'événements (`character.created`/`selected`/`deleted`), abonnement à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` pour réinitialiser `active_character_id` (runtime-only, jamais persisté) à chaque changement de workspace.
- **`CharactersPage`** — lit exclusivement des dicts via `CharacterManager.list_characters()`, jamais des objets `Character` (Presentation reste indépendante du Domain) ; protection `blockSignals()` contre les boucles d'événements Qt.
- **Dashboard/Images inchangés** — aucune carte "Characters" ajoutée, aucune migration de `ImagesPage` vers `Character.images` — choix explicites, différés à une mission future.

### Décisions de conception (Mission 002)

- Pas de migration d'images cette mission (`Workspace.images` reste la source utilisée par `ImagesPage`).
- `active_character_id` runtime-only, non persisté — même principe que `Workspace.root`.
- `favorite_models` retiré du périmètre — uniquement les 7 champs réellement nécessaires.
- `datasets`/`loras`/`prompts` sont des listes d'identifiants destinés à des objets futurs, pas des chemins de fichiers.
- Aucune carte Dashboard ajoutée.
- Génération de `character_id` dans `CharacterManager.create()`, jamais dans le dataclass `Character` — le Domain reste passif.
- Entrée Sidebar "Characters" positionnée juste après Dashboard, pas en fin de liste.

### Tests ajoutés (Mission 002)

`tests/integration/test_character_roundtrip.py` (6 tests) : cycle complet créer/sélectionner/sauvegarder/fermer/rouvrir, persistance de la suppression, non-réinitialisation d'`active_character_id` sur ouverture échouée, non-impact sur Dashboard/Images, reconstruction correcte de `CharactersPage` sur les événements Workspace, absence de duplication d'abonnements entre deux instanciations.

### Prochaines étapes

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Piste envisagée pour la prochaine mission : le domaine `Dataset`, entité suivante de la hiérarchie `Character → Datasets` déjà anticipée par `Character.datasets` (liste vide, prête à recevoir des identifiants).
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, différée depuis cette mission.
- Reste du Domain Model : `Model`, `LoRA`, `Job`, `Engine`, `Plugin`.

### État du projet (Mission 002)

**Mission 002 est terminée.** L'application dispose désormais d'une entité `Character` complète en CRUD, intégrée dans la navigation et couverte par des tests d'intégration.

---

## [v0.2-mission001](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission001) — 2026-08-10

### Résumé de la mission

**Mission 001 — Blueprint Refactoring.** Cette mission correspond au **Blueprint 02 (`docs/blueprint/02_ARCHITECTURE.md`)** : le prototype initial (gestion de "Project" ad hoc, logique métier dispersée dans l'UI, managers non utilisés) a été refactoré pour se conformer à l'architecture qui y est décrite, en cohérence avec les autres documents du Blueprint (`00_VISION.md` → `04_DOMAIN_MODEL.md`).

Cette mission n'a **ajouté aucune fonctionnalité nouvelle** : son unique objectif était de mettre le code existant en conformité avec les couches, les responsabilités et le sens de dépendance définis par le Blueprint (`Presentation → Managers → Services → Domain → Infrastructure → Engines`), tout en préservant le comportement observable de l'application.

Le travail a été mené en 9 commits atomiques, chacun revu, testé manuellement et validé avant exécution.

### Statistiques de la mission

| Indicateur | Valeur |
|---|---|
| Commits | 9 |
| Bugs corrigés | 3 |
| Tests d'intégration ajoutés | 2 |
| Packages morts supprimés | `src/config/`, `src/models/`, `src/widgets/`, `src/project/` |
| Architecture | Refactorisée (Presentation / Managers / Domain / Infrastructure / Core) |

### Évolutions architecturales principales

- **Introduction du Domain Layer** — `src/domain/workspace.py::Workspace`, un dataclass Qt-indépendant remplaçant l'ancienne dataclass `Project` (jamais utilisée) et reflétant fidèlement le schéma JSON réel. Le champ `root` (chemin du dossier) est explicitement runtime-only, jamais sérialisé, pour garder `project.json` portable.
- **Introduction de l'Infrastructure Layer** — `src/infrastructure/storage/workspace_storage.py::WorkspaceStorage`, portage durci de l'ancien `ProjectIO` : gestion d'erreurs typée (`WorkspaceStorageError`), journalisation, API dict-only (aucune dépendance vers le Domain, conformément au sens de dépendance du Blueprint).
- **Introduction de l'Application Layer** — `src/managers/workspace_manager.py::WorkspaceManager`, source unique de vérité pour le workspace courant, remplaçant l'ancien `ProjectManager` (jamais réellement instancié) et l'état dupliqué de `MainWindow`.
- **Introduction du Core / EventBus** — `src/core/event_bus.py::EventBus`, pub/sub minimal, Qt-indépendant, avec payloads réellement immuables (copie profonde + vue en lecture seule), permettant à la Presentation de réagir aux événements du workspace sans que les Managers ne dépendent de Qt.
- **`MainWindow` délègue entièrement à `WorkspaceManager`** — suppression de l'accès direct à l'Infrastructure (`ProjectIO`) et de l'état dupliqué (`current_project`/`project_folder`) ; `DashboardPage` et `ImagesPage` s'abonnent désormais aux événements du workspace plutôt que d'être mises à jour manuellement.
- **Extraction de la logique métier hors des widgets** — `ImagesPage` ne détient plus d'état privé ; l'import d'images passe par `WorkspaceManager.add_images()`, avec déduplication, et persiste réellement dans `project.json`.
- **Réorganisation de la structure de fichiers** — `src/pages/` déplacé sous `src/ui/pages/` ; suppression des packages vides non conformes (`src/config/`, `src/models/`, `src/widgets/`) ; suppression finale de `src/project/`, devenu totalement orphelin.

### Bugs corrigés

- **Dashboard non rafraîchi après création/ouverture d'un projet** — corrigé structurellement par le câblage événementiel (`WorkspaceManager` → `EventBus` → `DashboardPage.update_project`), plutôt que par un correctif ponctuel.
- **Une tentative d'ouverture d'un dossier invalide fermait silencieusement le workspace déjà ouvert** — `WorkspaceManager.open()` réinitialisait `current_workspace` à `None` même en cas d'échec, faisant perdre le projet en cours sans avertissement visible. Corrigé : un échec d'ouverture laisse désormais l'état courant inchangé. Cette règle métier est maintenant protégée par un test de non-régression permanent.
- **`WorkspaceManager.close()` ne publiait plus l'événement `workspace.closed`** — régression introduite lors de l'ajout d'`add_images()` (ligne de publication déplacée par erreur après un `return`, dans la mauvaise méthode). Détectée par le test d'intégration écrit pour cette même mission, corrigée dans la foulée.

### Tests ajoutés

- `tests/integration/test_workspace_roundtrip.py` (stdlib `unittest`, aucune nouvelle dépendance) :
  - `test_full_create_import_save_close_reopen_cycle` — cycle complet création → import d'images → sauvegarde → fermeture → réouverture (avec instances fraîches, simulant un vrai redémarrage), vérifiant la persistance des images et la mise à jour correcte du Dashboard et de la page Images.
  - `test_failed_open_does_not_close_current_workspace` — garde de non-régression permanente pour la règle métier « une ouverture échouée ne doit jamais fermer le workspace courant ».

### Prochaines étapes (Mission 002)

Hors périmètre de la Mission 001, à traiter dans des missions dédiées ultérieures :

- Introduction du domaine **Character** (entité centrale du Blueprint, actuellement absente) et de la propriété des ressources (Datasets, LoRAs, Prompts, Historique) qui lui revient.
- Introduction progressive des autres objets du Domain Model (`Dataset`, `Model`, `LoRA`, `Job`, `Engine`, `Plugin`) — un par mission, sans scaffolding anticipé.
- Introduction de la couche **Services** dès qu'une logique métier réelle la justifiera.
- Introduction de `src/engines/` et `src/plugins/` lors de la première intégration réelle avec un moteur externe (ComfyUI, OneTrainer, etc.).

### Améliorations UX futures

- Création automatique du dossier cible directement depuis le dialogue "Nouveau projet", sans devoir le créer manuellement au préalable dans l'explorateur Windows.

### État du projet

**Mission 001 est terminée.** L'application dispose désormais d'une architecture conforme au Blueprint 02, d'une suite de tests d'intégration et d'une documentation à jour (`README.md`, ce `CHANGELOG.md`).

**Mission 002** introduira le domaine **Character**, entité centrale du Blueprint (`docs/blueprint/04_DOMAIN_MODEL.md`), actuellement absente du code.

---

*Généré à l'issue de la Mission 001 — Blueprint Refactoring.*
