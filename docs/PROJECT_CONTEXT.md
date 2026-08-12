# PROJECT_CONTEXT.md — État consolidé du projet AI Studio Toolkit

> Ce document reflète l'état du projet à la clôture de la **Mission 010**. À mettre à jour à la fin de chaque future mission. Pour les règles permanentes (architecture, conventions, procédures), voir `CLAUDE.md` à la racine. Pour le détail de chaque mission, voir `docs/missions/`.

## État actuel du projet

Trois notions sont désormais distinguées explicitement, pour éviter toute ambiguïté entre l'état technique du dépôt et l'état fonctionnel des missions :

- **HEAD actuel de `main`** : `e28f89f0a06bd93ced174cff310491f3aa6dd230` (`docs: add persistent project memory`), synchronisé avec `origin/main` (vérifié).
- **Dernier commit de clôture de mission** : `089d8e338b4649a8242ed094bab74f748f765187` (`docs: document Application Settings and close Mission 010`).
- **Dernier tag / Release de mission** : `v0.2-mission010` (annoté), cible `089d8e338b4649a8242ed094bab74f748f765187`. Présent localement et sur `origin` (vérifié). GitHub Release publiée — confirmé directement par l'architecte du projet (non re-vérifiable techniquement depuis cet environnement, `gh` CLI absent).
- Suite de tests : **80/80 verts**.
- Statut général : phase de fondations architecturales. Aucune fonctionnalité IA réelle (génération, entraînement, moteurs) n'est encore implémentée — uniquement la définition, la persistance et la restauration des données.

**Règle documentaire** : lorsqu'un commit purement documentaire ou administratif intervient après la clôture d'une mission (ex. sauvegarde de la mémoire persistante), le HEAD actuel de `main` peut différer du dernier commit de clôture de mission. Ces deux valeurs sont alors conservées séparément dans ce document, jamais fusionnées ni l'une substituée à l'autre.

## Architecture actuelle

```
Presentation (src/ui/) → Managers (src/managers/) → Domain (src/domain/) → Infrastructure (src/infrastructure/) → Core/EventBus (src/core/)
```

Voir `CLAUDE.md` pour le détail des principes (Single Source of Truth, Dependency Rule, Event Driven UI, etc.) et des patterns d'ownership.

### Domain (`src/domain/`, 10 classes)

| Classe | Fichier | Champs | Ownership |
|---|---|---|---|
| `Workspace` | `workspace.py` | `name`, `version`, `root` (runtime), `images`, `datasets`, `models`, `workflows`, `loras`, `training` (dict brut), `settings: Settings`, `characters` | racine |
| `Character` | `character.py` | `character_id`, `name`, `images`, `datasets`, `loras`, `prompts`, `trainings`, `history` (list[str] brut) | Workspace-owned |
| `Dataset` | `dataset.py` | `dataset_id`, `name`, `images` | Character-owned |
| `LoRA` | `lora.py` | `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version` | Character-owned |
| `Prompt` | `prompt.py` | `prompt_id`, `name`, `text` | Character-owned |
| `Model` | `model.py` | `model_id`, `name`, `file_path` | Workspace-owned |
| `Workflow` | `workflow.py` | `workflow_id`, `name`, `file_path` | Workspace-owned |
| `Training` | `training.py` | `training_id`, `name`, `dataset_id` (pas de `character_id`) | Character-owned |
| `Settings` | `settings.py` | `theme`, `language` | Workspace-owned, singleton |
| `ApplicationSettings` | `application_settings.py` | `python_path`, `comfyui_path`, `onetrainer_path` | Application-level, singleton, hors Workspace |

### Managers (`src/managers/`, 10)

`WorkspaceManager`, `CharacterManager`, `DatasetManager`, `LoRAManager`, `PromptManager`, `ModelManager`, `WorkflowManager`, `TrainingManager`, `SettingsManager`, `ApplicationSettingsManager`.

### Infrastructure (`src/infrastructure/storage/`, 2)

- `WorkspaceStorage` — `project.json`, non atomique, lève `WorkspaceStorageError` sur corruption.
- `ApplicationSettingsStorage` — `application_settings.json` (`%LOCALAPPDATA%\AIStudioToolkit\` sous Windows, repli `Path.home()/AppData/Local/AIStudioToolkit`), écriture atomique (temp file + `flush`+`fsync`+`os.replace()`), lecture non bloquante (défauts silencieux + warning si absent/corrompu/mal typé), lève `ApplicationSettingsStorageError` uniquement sur échec d'écriture.

### UI (`src/ui/`)

11 sections Sidebar/Stack (index fixe) : Dashboard, Characters, Images, Datasets, Models, Workflows, LoRA, Prompts, Training, Inference, Settings.

| Page | Fonctionnelle ? |
|---|---|
| `DashboardPage` | ✅ |
| `CharactersPage` | ✅ |
| `ImagesPage` | ✅ |
| `DatasetsPage` | ✅ |
| `ModelsPage` | ✅ |
| `WorkflowsPage` | ✅ |
| `LoRAPage` | ✅ |
| `PromptsPage` | ✅ |
| `TrainingPage` | ✅ (définition de session uniquement, aucune exécution) |
| `SettingsPage` | ✅ — 2 sections indépendantes : Workspace Settings (`theme`/`language`) et Application Settings (`python_path`/`comfyui_path`/`onetrainer_path`), Managers/cycles de vie/persistances/canaux de rafraîchissement strictement séparés |
| `InferencePage` | ❌ vitrine, aucune logique métier |

`BasePage` (`base_page.py`) — code mort, jamais importé.

### EventBus (`src/core/event_bus.py`)

Générique, aucune constante propre. 26 événements définis localement dans les Managers : 4 `WORKSPACE_*`, 3 chacun pour `CHARACTER`/`DATASET`/`LORA`/`MODEL`/`PROMPT`/`TRAINING`/`WORKFLOW` (created/selected/deleted), 1 `application_settings.updated`. `SettingsManager` et `ApplicationSettingsManager` ne publient/n'écoutent aucun événement CRUD (pas de collection).

### Tests (`tests/integration/`, 80 tests, 10 suites)

`test_workspace_roundtrip.py` (2), `test_character_roundtrip.py` (7), `test_dataset_roundtrip.py` (7), `test_lora_roundtrip.py` (7), `test_prompt_roundtrip.py` (7), `test_model_roundtrip.py` (8), `test_workflow_roundtrip.py` (9), `test_training_roundtrip.py` (11), `test_settings_roundtrip.py` (9), `test_application_settings_roundtrip.py` (13).

## Fonctionnalités terminées

- Gestion de Workspace (création/ouverture/sauvegarde, `project.json`).
- Gestion de Character (CRUD).
- Gestion de Dataset (CRUD + images, intégrité référentielle avec Training : suppression bloquée si référencé, sans cascade).
- Gestion de LoRA (CRUD + fichiers).
- Gestion de Prompt (CRUD + édition de texte idempotente).
- Gestion de Model (CRUD, Workspace-owned).
- Gestion de Workflow (CRUD, Workspace-owned, association fichier externe).
- Gestion de Training (CRUD de **définition** de session uniquement — aucune exécution, aucun Job, aucun Engine).
- Workspace Settings (`theme`/`language`, persistés dans `project.json`, **non appliqués à l'UI**).
- Application Settings (`python_path`/`comfyui_path`/`onetrainer_path`, persistés hors `project.json`, **aucune validation d'existence, aucun lancement d'outil**).

## Décisions techniques importantes à retenir

- Deux patterns d'ownership (Character-owned / Workspace-owned) + deux variantes singleton (Workspace-owned singleton `Settings` / Application-level singleton `ApplicationSettings`) — voir `CLAUDE.md`.
- Aucune donnée Application (`ApplicationSettings`) n'est jamais stockée dans `project.json` ; aucune donnée Workspace (`Settings`) n'est jamais stockée dans `application_settings.json`. Aucune migration automatique entre les deux — jamais liées.
- Stratégie **"candidate-first"** pour `ApplicationSettingsManager.update()` : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire (contrairement à `SettingsManager`, Mission 009, qui mute avant de sauvegarder — divergence assumée, non rétrofittée).
- Intégrité référentielle Dataset → Training : un Dataset référencé par ≥1 Training ne peut pas être supprimé, sans suppression en cascade.
- `TrainingPage` et `SettingsPage` sont les seules Pages du projet dépendant de deux Managers.
- Ownership `Training` : Character-owned avec un niveau de preuve Blueprint plus nuancé que `Model`/`Workflow` (ambiguïté `Training` vs `Training History` non résolue — voir dettes).

## Fichiers et répertoires structurants

```
src/
├── core/event_bus.py, main.py
├── domain/ (10 fichiers, voir tableau ci-dessus)
├── infrastructure/storage/ (workspace_storage.py, application_settings_storage.py)
├── managers/ (10 fichiers)
└── ui/main_window.py, sidebar.py, toolbar.py, statusbar.py, menubar.py, pages/ (12 fichiers dont base_page.py mort)
tests/integration/ (10 fichiers de test)
docs/blueprint/ (5 fichiers Blueprint, source de vérité produit — jamais modifiés)
docs/missions/ (ce dossier — historique par mission)
CLAUDE.md (règles permanentes)
README.md, CHANGELOG.md (documentation publique du projet)
```

## Dépendances importantes

`requirements.txt` : `PySide6`, `pydantic`, `opencv-python`, `numpy`, `pillow`. Tests : stdlib `unittest` uniquement. Aucune dépendance ajoutée pour la résolution de répertoire Application Settings (Python standard `os`/`pathlib` uniquement, décision explicite de ne pas utiliser `QStandardPaths` ni `platformdirs`/`appdirs` pour garder Infrastructure indépendante de Qt).

## Problèmes connus / dettes (non résolues, signalées, jamais transformées en roadmap obligatoire)

- **Ambiguïté ownership `Training` vs `Training History`** — Blueprint incohérent entre `04_DOMAIN_MODEL.md` §4 (Trainings sous Characters) et les arbres structurels de `00_VISION.md`/`01_PRODUCT_REQUIREMENTS.md`/`02_ARCHITECTURE.md` (qui ne nomment que "Training History"). Non résolue.
- **Références mortes** dans `01_PRODUCT_REQUIREMENTS.md` : `04_DATA_MODEL.md` et `05_CHARACTER_SYSTEM.md`, fichiers absents de `docs/blueprint/`.
- **`Image` Domain manquant** — `Workspace.images`/`Dataset.images` restent `list[str]`, pas d'objet `Image` conforme à `04_DOMAIN_MODEL.md` §8. Dette explicitement actée à traiter avant/au début d'une future mission Generation (migration de données réelles, contrairement aux migrations précédentes qui n'avaient jamais de données réelles en jeu).
- **`BasePage`** (`src/ui/pages/base_page.py`) — code mort, jamais importé.
- **Incohérences documentaires mineures Job** — état `Queued` absent de `01_PRODUCT_REQUIREMENTS.md` §12 (présent dans `04_DOMAIN_MODEL.md` §17) ; "Engine Manager" cité dans `00_VISION.md` §11 mais absent de la liste canonique des Managers `02_ARCHITECTURE.md` §6.
- **Support Linux/macOS non vérifié** pour `ApplicationSettingsStorage.default_directory()` — uniquement Windows testé/requis à ce jour.
- **`test_dataset_roundtrip.py`** ne teste pas directement `is_referenced_by_training()`/le garde de `delete()` (Mission 008) — couvert uniquement côté `test_training_roundtrip.py`, choix assumé documenté à l'époque.

## Travaux encore en attente

Aucune direction n'est arrêtée pour Mission 011. Un audit architectural (Mission 010, avant implémentation) a établi que `Job`/`Generation`/`Video`/exécution de `Training` nécessitent tous une chaîne quasi entièrement absente : `Service` (`src/services/` existe mais vide) → `AI Orchestrator` (inexistant) → `Plugin` (inexistant) → `Engine` (inexistant). Candidats déjà écartés pour Mission 010 au profit d'`ApplicationSettings` : `Job` seul (risque de machine à états sans utilisateur réel) et `Image` seul (migration de données réelles sans consommateur — Generation — encore inexistant).

## Dernière mission terminée

**Mission 010 — Application Settings Domain.** Voir `docs/missions/MISSION_010.md`.

## HEAD actuel de `main`

`e28f89f0a06bd93ced174cff310491f3aa6dd230` — `docs: add persistent project memory` (commit documentaire, postérieur à la clôture de la Mission 010 — voir règle documentaire ci-dessus).

## Dernier commit de clôture de mission

`089d8e338b4649a8242ed094bab74f748f765187` — `docs: document Application Settings and close Mission 010`.

## Dernier tag / release de mission

`v0.2-mission010` (annoté, cible `089d8e338b4649a8242ed094bab74f748f765187`, présent sur `origin`). GitHub Release **publiée** — confirmé directement par l'architecte du projet.

## Prochaine mission prévue

**Non définie.** Mission 011 nécessitera son propre audit architectural avant tout choix, suivant le même format que les audits Mission 009/010 (relecture complète du Blueprint, inventaire du code existant, comparaison de candidats crédibles, recommandation motivée — jamais un choix par défaut).
