# PROJECT_CONTEXT.md — État consolidé du projet AI Studio Toolkit

> Ce document reflète l'état du projet à la clôture de la **Mission 011**. À mettre à jour à la fin de chaque future mission. Pour les règles permanentes (architecture, conventions, procédures), voir `CLAUDE.md` à la racine. Pour le détail de chaque mission, voir `docs/missions/`.

## État actuel du projet

- **HEAD du repository** : Git fait autorité — vérifier avec `git rev-parse HEAD`. Ce document ne fige jamais cette valeur en dur (voir "Principe de non-auto-référence" ci-dessous).
- **Dernier commit fonctionnel de mission** : `242453e7a39a452d16a1eadc3d93a6181cd5305c` (`feat: introduce Image Domain`) — hash citable sans risque, puisqu'il existait déjà avant la rédaction de cette ligne.
- **Dernier tag de mission** : `v0.2-mission011` (annoté, message `Mission 011 - Image Domain`). Cible exacte : Git fait autorité — vérifier avec `git rev-list -n 1 v0.2-mission011` (ou le déréférencement du tag annoté, `git rev-parse v0.2-mission011^{}`).
- Suite de tests : **90/90 verts** (80 précédents + 10 nouveaux tests `test_image_roundtrip.py`).
- Statut général : phase de fondations architecturales. Aucune fonctionnalité IA réelle (génération, entraînement, moteurs) n'est encore implémentée — uniquement la définition, la persistance et la restauration des données. Le Domain `Image` (Mission 011) élimine la dernière incohérence de représentation connue avant toute future mission Generation.

**Principe de non-auto-référence (règle permanente pour ce document)** : la documentation versionnée ne doit jamais tenter de figer en dur le hash du commit qui la contient elle-même, ni la cible exacte d'un tag pas encore créé au moment de la rédaction — un tel hash n'existe pas encore, et toute tentative de le documenter force soit une prédiction qui devient fausse dès que le commit/tag réel est créé, soit une chaîne infinie de commits correctifs cherchant chacun à documenter le hash du précédent. Ce piège a été rencontré concrètement en clôture de Mission 011 (voir `docs/missions/MISSION_011.md`) et corrigé définitivement par ce principe. En conséquence : seuls des hashes de commits **déjà existants** au moment de la rédaction (typiquement, le commit fonctionnel d'une mission déjà committé) peuvent être cités en dur dans ce document. Pour "HEAD du repository" et "cible exacte du tag", Git reste en permanence la seule source de vérité — ce document ne les recopie jamais en dur, il indique seulement la commande à exécuter.

## Architecture actuelle

```
Presentation (src/ui/) → Managers (src/managers/) → Domain (src/domain/) → Infrastructure (src/infrastructure/) → Core/EventBus (src/core/)
```

Voir `CLAUDE.md` pour le détail des principes (Single Source of Truth, Dependency Rule, Event Driven UI, etc.) et des patterns d'ownership.

### Domain (`src/domain/`, 11 classes)

| Classe | Fichier | Champs | Ownership |
|---|---|---|---|
| `Workspace` | `workspace.py` | `name`, `version`, `root` (runtime), `images: list[Image]`, `datasets`, `models`, `workflows`, `loras`, `training` (dict brut), `settings: Settings`, `characters` | racine |
| `Character` | `character.py` | `character_id`, `name`, `datasets`, `loras`, `prompts`, `trainings`, `history` (list[str] brut) | Workspace-owned |
| `Dataset` | `dataset.py` | `dataset_id`, `name`, `images: list[Image]` | Character-owned |
| `Image` | `image.py` | `image_id`, `file_path` | Contextuel — voir "Ownership Image" ci-dessous, pas un pattern des 4 précédents |
| `LoRA` | `lora.py` | `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version` | Character-owned |
| `Prompt` | `prompt.py` | `prompt_id`, `name`, `text` | Character-owned |
| `Model` | `model.py` | `model_id`, `name`, `file_path` | Workspace-owned |
| `Workflow` | `workflow.py` | `workflow_id`, `name`, `file_path` | Workspace-owned |
| `Training` | `training.py` | `training_id`, `name`, `dataset_id` (pas de `character_id`) | Character-owned |
| `Settings` | `settings.py` | `theme`, `language` | Workspace-owned, singleton |
| `ApplicationSettings` | `application_settings.py` | `python_path`, `comfyui_path`, `onetrainer_path` | Application-level, singleton, hors Workspace |

#### Ownership `Image` (Mission 011 — Modèle D, contextuel et structurel)

- Deux pools indépendants : `Workspace.images: list[Image]` et `Dataset.images: list[Image]` (ce dernier Character-owned par transitivité, comme `Dataset` lui-même).
- **Aucune source de vérité globale**, **aucun registre partagé**, **aucune référence croisée** entre les deux pools — une même valeur `file_path` présente dans les deux représente deux instances `Image` totalement indépendantes (`image_id` distincts).
- `Character.images` **supprimé** (Mission 011) : champ historiquement déclaré mais jamais peuplé ni consommé par aucun Manager ni aucune Page depuis sa création (Mission 002) — dette confirmée et éliminée, pas une régression. La relation `Character → Image` reste strictement transitive via `Character → Dataset → Image`.
- **Aucun `ImageManager`** : `WorkspaceManager.add_images()` et `DatasetManager.add_images()` (déjà responsables de leurs collections respectives) construisent directement des `Image` — `Image` n'a pas de cycle de vie CRUD autonome justifiant un Manager dédié, à la différence de `Model`/`Workflow`/`Settings`/`ApplicationSettings`.
- **Aucun nouvel événement EventBus** : le canal `WORKSPACE_SAVED` existant (déjà déclenché par les deux méthodes `add_images()`) reste l'unique canal de rafraîchissement UI.

### Managers (`src/managers/`, 10 — inchangé, `Image` n'introduit aucun nouveau Manager)

`WorkspaceManager`, `CharacterManager`, `DatasetManager`, `LoRAManager`, `PromptManager`, `ModelManager`, `WorkflowManager`, `TrainingManager`, `SettingsManager`, `ApplicationSettingsManager`. `WorkspaceManager.add_images()` et `DatasetManager.add_images()` construisent désormais des `Image` (Mission 011) au lieu de chaînes brutes ; déduplication prospective toujours par `file_path`.

### Infrastructure (`src/infrastructure/storage/`, 2)

- `WorkspaceStorage` — `project.json`, non atomique, lève `WorkspaceStorageError` sur corruption. Depuis Mission 011, `"images"` (au niveau Workspace et de chaque Dataset) est sérialisé au format `[{"image_id": "...", "file_path": "..."}]` ; l'ancien format `["chemin", ...]` reste lu de façon rétrocompatible (migration en mémoire au chargement, jamais de réécriture forcée), voir `docs/missions/MISSION_011.md`.
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

Générique, aucune constante propre. 26 événements définis localement dans les Managers : 4 `WORKSPACE_*`, 3 chacun pour `CHARACTER`/`DATASET`/`LORA`/`MODEL`/`PROMPT`/`TRAINING`/`WORKFLOW` (created/selected/deleted), 1 `application_settings.updated`. `SettingsManager` et `ApplicationSettingsManager` ne publient/n'écoutent aucun événement CRUD (pas de collection). Mission 011 n'introduit aucun événement : l'ajout d'images continue de déclencher uniquement `WORKSPACE_SAVED` (via `WorkspaceManager.save()`, appelé directement ou par `DatasetManager.add_images()`).

### Tests (`tests/integration/`, 90 tests, 11 suites)

`test_workspace_roundtrip.py` (2), `test_character_roundtrip.py` (7), `test_dataset_roundtrip.py` (7), `test_image_roundtrip.py` (10), `test_lora_roundtrip.py` (7), `test_prompt_roundtrip.py` (7), `test_model_roundtrip.py` (8), `test_workflow_roundtrip.py` (9), `test_training_roundtrip.py` (11), `test_settings_roundtrip.py` (9), `test_application_settings_roundtrip.py` (13).

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
- Image Domain (Mission 011) : représentation structurée (`image_id`, `file_path`) des images de `Workspace.images` et `Dataset.images`, remplaçant les chaînes brutes ; migration rétrocompatible depuis l'ancien format, **aucun traitement d'image, aucune suppression individuelle, aucune métadonnée de génération**.

## Décisions techniques importantes à retenir

- Deux patterns d'ownership (Character-owned / Workspace-owned) + deux variantes singleton (Workspace-owned singleton `Settings` / Application-level singleton `ApplicationSettings`) + un pattern contextuel (`Image`, Mission 011, deux pools indépendants sans registre partagé) — voir `CLAUDE.md`.
- Aucune donnée Application (`ApplicationSettings`) n'est jamais stockée dans `project.json` ; aucune donnée Workspace (`Settings`) n'est jamais stockée dans `application_settings.json`. Aucune migration automatique entre les deux — jamais liées.
- Stratégie **"candidate-first"** pour `ApplicationSettingsManager.update()` : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire (contrairement à `SettingsManager`, Mission 009, qui mute avant de sauvegarder — divergence assumée, non rétrofittée).
- Intégrité référentielle Dataset → Training : un Dataset référencé par ≥1 Training ne peut pas être supprimé, sans suppression en cascade.
- `TrainingPage` et `SettingsPage` sont les seules Pages du projet dépendant de deux Managers.
- Ownership `Training` : Character-owned avec un niveau de preuve Blueprint plus nuancé que `Model`/`Workflow` (ambiguïté `Training` vs `Training History` non résolue — voir dettes).
- **Migration `Image` (Mission 011)** — première migration du projet portant sur des données réellement présentes (contrairement à `Model`/`Workflow`, dont les champs équivalents n'avaient jamais contenu de données réelles) : `Image.list_from_data()` convertit `list[str]` (legacy) et `list[dict]` (nouveau format) de façon unifiée, partagée entre `Workspace.from_dict()` et `Dataset.from_dict()`. Un identifiant `uuid4()` est généré pour chaque entrée `str` legacy à chaque chargement tant qu'aucune sauvegarde n'a eu lieu ; il devient stable dès la première sauvegarde au nouveau format. Les doublons de chemin historiques sont préservés comme instances distinctes (aucune fusion, aucune perte).
- **Correction découverte en revue finale de Mission 011** : la première implémentation de `Image.list_from_data()` acceptait silencieusement des entrées `dict` sans `file_path` exploitable (ex. `{}`, `{"image_id": "abc"}` auraient produit une `Image` avec `file_path=""`). Corrigée avant commit : une entrée `dict` n'est conservée que si son `file_path` est un `str` non vide ; une entrée `str` legacy n'est conservée que si elle est non vide. Test de régression ajouté. Fait partie de l'historique technique réel de la mission, volontairement non effacé.

## Fichiers et répertoires structurants

```
src/
├── core/event_bus.py, main.py
├── domain/ (11 fichiers, voir tableau ci-dessus)
├── infrastructure/storage/ (workspace_storage.py, application_settings_storage.py)
├── managers/ (10 fichiers)
└── ui/main_window.py, sidebar.py, toolbar.py, statusbar.py, menubar.py, pages/ (12 fichiers dont base_page.py mort)
tests/integration/ (11 fichiers de test)
docs/blueprint/ (5 fichiers Blueprint, source de vérité produit — jamais modifiés)
docs/missions/ (ce dossier — historique par mission)
CLAUDE.md (règles permanentes)
README.md, CHANGELOG.md (documentation publique du projet)
```

## Dépendances importantes

`requirements.txt` : `PySide6`, `pydantic`, `opencv-python`, `numpy`, `pillow`. Tests : stdlib `unittest` uniquement. Aucune dépendance ajoutée pour la résolution de répertoire Application Settings (Python standard `os`/`pathlib` uniquement, décision explicite de ne pas utiliser `QStandardPaths` ni `platformdirs`/`appdirs` pour garder Infrastructure indépendante de Qt).

## Problèmes connus / dettes (non résolues, signalées, jamais transformées en roadmap obligatoire)

- **Ambiguïté ownership `Training` vs `Training History`** — Blueprint incohérent entre `04_DOMAIN_MODEL.md` §4 (Trainings sous Characters) et les arbres structurels de `00_VISION.md`/`01_PRODUCT_REQUIREMENTS.md`/`02_ARCHITECTURE.md` (qui ne nomment que "Training History"). Non résolue — Mission 011 n'a volontairement pas traité ce point (hors périmètre).
- **Références mortes** dans `01_PRODUCT_REQUIREMENTS.md` : `04_DATA_MODEL.md` et `05_CHARACTER_SYSTEM.md`, fichiers absents de `docs/blueprint/`.
- **`BasePage`** (`src/ui/pages/base_page.py`) — code mort, jamais importé. Mission 011 n'a volontairement pas traité ce point (hors périmètre, pas de refactoring général).
- **Incohérences documentaires mineures Job** — état `Queued` absent de `01_PRODUCT_REQUIREMENTS.md` §12 (présent dans `04_DOMAIN_MODEL.md` §17) ; "Engine Manager" cité dans `00_VISION.md` §11 mais absent de la liste canonique des Managers `02_ARCHITECTURE.md` §6.
- **Support Linux/macOS non vérifié** pour `ApplicationSettingsStorage.default_directory()` — uniquement Windows testé/requis à ce jour. Mission 011 n'a volontairement pas traité ce point (hors périmètre).
- **`test_dataset_roundtrip.py`** ne teste pas directement `is_referenced_by_training()`/le garde de `delete()` (Mission 008) — couvert uniquement côté `test_training_roundtrip.py`, choix assumé documenté à l'époque.

**Dette résolue par Mission 011** : `Image` Domain manquant (`Workspace.images`/`Dataset.images` en `list[str]`, `Character.images` mort) — voir `docs/missions/MISSION_011.md`.

## Travaux encore en attente

Aucune direction n'est arrêtée pour Mission 012. L'audit architectural de Mission 010 (confirmé toujours valable à la clôture de Mission 011) a établi que `Job`/`Generation`/`Video`/exécution de `Training` nécessitent tous une chaîne quasi entièrement absente : `Service` (`src/services/` existe mais vide) → `AI Orchestrator` (inexistant) → `Plugin` (inexistant) → `Engine` (inexistant) — **inchangée par Mission 011**, qui n'a touché à aucun de ces éléments (hors périmètre explicite). Le Domain `Image` étant désormais cohérent, la dette qui restait explicitement documentée comme "à traiter avant toute mission Generation" est levée ; le prérequis suivant pour une mission Generation reste la chaîne `Service → AI Orchestrator → Plugin → Engine`, qui n'a pas encore d'existant architectural sur lequel s'appuyer et nécessitera son propre audit avant toute implémentation, probablement décomposé en plusieurs missions plutôt qu'une seule (cf. audit préparatoire Mission 011).

## Dernière mission terminée

**Mission 011 — Image Domain.** Voir `docs/missions/MISSION_011.md`.

## HEAD du repository

Git fait autorité — vérifier avec `git rev-parse HEAD`. Non documenté en dur ici (voir "Principe de non-auto-référence", section "État actuel du projet").

## Dernier commit fonctionnel de mission

`242453e7a39a452d16a1eadc3d93a6181cd5305c` — `feat: introduce Image Domain`.

## Dernier tag de mission

`v0.2-mission011` (annoté, message `Mission 011 - Image Domain`). Cible exacte : Git fait autorité — vérifier avec `git rev-list -n 1 v0.2-mission011`.

## Prochaine mission prévue

**Non définie.** Mission 012 nécessitera son propre audit architectural avant tout choix, suivant le même format que les audits Mission 009/010/011 (relecture complète du Blueprint, inventaire du code existant, comparaison de candidats crédibles, recommandation motivée — jamais un choix par défaut). Le prérequis architectural le plus probable pour toute mission Generation reste la chaîne `Service → AI Orchestrator → Plugin → Engine`, entièrement absente du code à ce jour.
