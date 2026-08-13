# PROJECT_CONTEXT.md — État consolidé du projet AI Studio Toolkit

> Ce document reflète l'état du projet à la clôture fonctionnelle de la **Mission 014** (code et tests). À mettre à jour à la fin de chaque future mission. Pour les règles permanentes (architecture, conventions, procédures), voir `CLAUDE.md` à la racine. Pour le détail de chaque mission, voir `docs/missions/`.

## État actuel du projet

- **HEAD du repository** : Git fait autorité — vérifier avec `git rev-parse HEAD`. Ce document ne fige jamais cette valeur en dur (voir "Principe de non-auto-référence" ci-dessous).
- **Dernier commit de mission (Git)** : au moment de la rédaction de cette mise à jour, la clôture Git de la Mission 014 n'a pas encore eu lieu — le dernier commit de mission réellement présent dans l'historique reste celui de Mission 013 (`feat: connect Inference UI to ComfyUI generation`). Le message et le hash du commit clôturant Mission 014 seront déterminés lors de cette clôture — jamais fixés en dur ici avant leur création, conformément au principe de non-auto-référence.
- **Dernier tag de mission (Git)** : `v0.2-mission013` (annoté, message `Mission 013 - Inference UI Integration`) reste le dernier tag existant — Mission 014 n'est pas encore taguée. Cible exacte de `v0.2-mission013` : Git fait autorité — vérifier avec `git rev-list -n 1 v0.2-mission013`. GitHub Release `v0.2-mission013` **publiée** — confirmé directement par l'architecte du projet (information fiable ; non re-vérifiable techniquement depuis cet environnement, `gh` CLI absent).
- Suite de tests : **159/159 verts** (138 précédents + 21 nets nouveaux dans `test_inference_page.py`, passé de 9 à 30 tests avec la validation post-génération de Mission 014 ; `test_generation_manager.py` (10), `test_generation_worker.py` (4) et `test_comfyui_engine.py` (25) strictement inchangés).
- Statut général : Mission 013 a introduit la première verticale fonctionnelle réelle du projet (`GenerationManager`, `GenerationWorker`, `InferencePage` fonctionnelle, premier consommateur réel de `ComfyUIEngine`). **Mission 014 ajoute une étape de validation explicite entre génération et persistance** : `Generate → Preview → Accept/Reject/Regenerate`, une génération réussie n'étant plus jamais automatiquement ajoutée à `Workspace.images`. Un défaut réel (absence de liaison entre un résultat pending et le Workspace où il a été généré, permettant en théorie une persistance croisée entre Workspaces) a été trouvé en revue technique finale et corrigé avant clôture. Un smoke test réel complet couvrant six scénarios (Accept, Reject, Regenerate, persistance/reload, changement de Workspace avec pending, fermeture avec pending terminé) a validé la chaîne complète en conditions réelles, contre ComfyUI Desktop réel — voir `docs/missions/MISSION_014.md`.

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

### Managers (`src/managers/`, 11 — `GenerationManager` ajouté en Mission 013)

`WorkspaceManager`, `CharacterManager`, `DatasetManager`, `LoRAManager`, `PromptManager`, `ModelManager`, `WorkflowManager`, `TrainingManager`, `SettingsManager`, `ApplicationSettingsManager`, `GenerationManager`. `WorkspaceManager.add_images()` et `DatasetManager.add_images()` construisent des `Image` (Mission 011) au lieu de chaînes brutes ; déduplication prospective toujours par `file_path`.

`GenerationManager` (Mission 013) — première variante volontairement différente des 10 autres : pas de collection Domain, pas d'`active_id`, un unique flag transitoire `busy` (même nature qu'un `active_*_id`, jamais persisté). Coordonne `ComfyUIEngine.generate_image()` (`prompt_text`, `output_directory` ; `checkpoint_name` fixé à la construction, non exposé par appel). Strictement Qt-free (aucun import PySide6, vérifié par test), ignore tout de `WorkspaceManager`/l'UI/le thread appelant — retourne uniquement le chemin généré, laissant l'ownership entièrement à l'appelant. Normalise `ComfyUIEngineError` et `OSError` en `GenerationError`.

### Infrastructure (`src/infrastructure/storage/`, 2)

- `WorkspaceStorage` — `project.json`, non atomique, lève `WorkspaceStorageError` sur corruption. Depuis Mission 011, `"images"` (au niveau Workspace et de chaque Dataset) est sérialisé au format `[{"image_id": "...", "file_path": "..."}]` ; l'ancien format `["chemin", ...]` reste lu de façon rétrocompatible (migration en mémoire au chargement, jamais de réécriture forcée), voir `docs/missions/MISSION_011.md`.
- `ApplicationSettingsStorage` — `application_settings.json` (`%LOCALAPPDATA%\AIStudioToolkit\` sous Windows, repli `Path.home()/AppData/Local/AIStudioToolkit`), écriture atomique (temp file + `flush`+`fsync`+`os.replace()`), lecture non bloquante (défauts silencieux + warning si absent/corrompu/mal typé), lève `ApplicationSettingsStorageError` uniquement sur échec d'écriture. `comfyui_path` reste inutilisé (Mission 012 ne le consomme pas — voir section Engines).

### Engines (`src/engines/`, 1 — introduit Mission 012, consommé réellement depuis Mission 013)

- `ComfyUIEngine` (`comfyui_engine.py`) — client HTTP minimal (stdlib `urllib` uniquement) vers une instance serveur ComfyUI, locale ou distante. Frontière architecturale : `AI Studio Toolkit → ComfyUI`, jamais `AI Studio Toolkit → un modèle/provider particulier` — vérifié par test automatisé (aucune connaissance de checkpoint/SDXL/FLUX/LoRA/Gemini/GPT Image dans les 3 primitives génériques).
- Trois primitives génériques constituent le contrat réel, **inchangées depuis Mission 012** : `submit(workflow, client_id)` (`POST /prompt`), `wait_for_result(prompt_id, poll_interval)` (`GET /history/{prompt_id}`, polling jusqu'à résultat exploitable ou timeout), `download_output(filename, subfolder, type_, output_directory)` (`GET /view`). Pas de WebSocket.
- `generate_image(prompt_text, output_directory, checkpoint_name=DEMO_CHECKPOINT_NAME)` : convenience method de démonstration, composée strictement des 3 primitives + `build_demo_workflow()`. Le paramètre `checkpoint_name` a été ajouté en Mission 013 (extension additive, rétrocompatible) — nécessité réelle démontrée par l'intégration (le checkpoint par défaut n'existe pas exactement sous ce nom sur l'installation réelle testée).
- N'importe rien de `src/domain/`, ne retourne que des `str`/`dict` — aucune image générée n'est ajoutée automatiquement à `Workspace.images`/`Dataset.images` par `ComfyUIEngine` lui-même ; cette décision revient à l'appelant (`GenerationManager` et sa couche d'orchestration, Mission 013 — voir section Managers).
- Le protocole peut transporter un workflow contenant des nodes locaux ou des nodes appelant des services cloud (le protocole ComfyUI ne distingue pas les deux) — mais aucun client direct vers une éventuelle API Comfy Cloud hébergée n'est implémenté. Détail complet : `docs/missions/MISSION_012.md`, `docs/missions/MISSION_013.md`.
- `base_url`/`checkpoint_name` réellement utilisés (`http://127.0.0.1:8000`, `v1-5-pruned-emaonly-fp16.safetensors`) sont injectés au niveau de la composition root (`main_window.py`, constantes `COMFYUI_BASE_URL`/`COMFYUI_CHECKPOINT_NAME`, explicitement documentées comme spécifiques à une machine, pas universelles) — `ComfyUIEngine` conserve son défaut générique `8188`, `ApplicationSettings` non modifié.

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
| `InferencePage` | ✅ (Mission 013, étendue Mission 014) — saisie prompt, bouton "Générer" fonctionnel, génération asynchrone (`QThread`/`GenerationWorker`). Depuis Mission 014 : le résultat n'est plus enregistré automatiquement — aperçu (`QLabel`/`QPixmap`) puis validation explicite Accept/Reject/Regenerate, avec protection contre tout enregistrement dans un Workspace différent de celui où la génération a été lancée. Pas de sélection Dataset, pas d'images de référence, pas de sélection de checkpoint/moteur, pas d'aperçu agrandi/plein écran (voir "Besoins futurs identifiés" ci-dessous) |

`BasePage` (`base_page.py`) — code mort, jamais importé.

`src/ui/generation_worker.py` — `GenerationWorker` (`QObject`), seule classe du projet connaissant à la fois Qt et `GenerationManager`. Déplacé dans un `QThread` via `moveToThread()` (premier code de threading du projet). Traduit succès/échec de `GenerationManager.generate()` en signaux `finished(str)`/`failed(str)`, aucune exception ne traverse la frontière de thread.

### EventBus (`src/core/event_bus.py`)

Générique, aucune constante propre. 26 événements définis localement dans les Managers : 4 `WORKSPACE_*`, 3 chacun pour `CHARACTER`/`DATASET`/`LORA`/`MODEL`/`PROMPT`/`TRAINING`/`WORKFLOW` (created/selected/deleted), 1 `application_settings.updated`. `SettingsManager` et `ApplicationSettingsManager` ne publient/n'écoutent aucun événement CRUD (pas de collection). Mission 011 n'introduit aucun événement : l'ajout d'images continue de déclencher uniquement `WORKSPACE_SAVED` (via `WorkspaceManager.save()`, appelé directement ou par `DatasetManager.add_images()`).

### Tests (`tests/integration/`, 159 tests, 15 suites)

`test_workspace_roundtrip.py` (2), `test_character_roundtrip.py` (7), `test_dataset_roundtrip.py` (7), `test_image_roundtrip.py` (10), `test_lora_roundtrip.py` (7), `test_prompt_roundtrip.py` (7), `test_model_roundtrip.py` (8), `test_workflow_roundtrip.py` (9), `test_training_roundtrip.py` (11), `test_settings_roundtrip.py` (9), `test_application_settings_roundtrip.py` (13), `test_comfyui_engine.py` (25 — entièrement mocké, inchangé depuis Mission 013), `test_generation_manager.py` (10 — pur Python, `ComfyUIEngine` mocké, inchangé), `test_generation_worker.py` (4 — `QThread` réel, `GenerationManager` mocké, inchangé), `test_inference_page.py` (30 — widgets Qt réels, `GenerationManager` mocké ; étendu en Mission 014 de 9 à 30 tests : preview sans persistance, Accept exactement une fois, Reject, Regenerate, changement de Workspace pendant pending et pendant génération, fichier disparu avant Accept, erreurs de suppression filesystem, shutdown avec pending, et les tests de course QThread Mission 013 toujours verts). Aucun test n'effectue de requête réseau réelle, n'utilise une instance ComfyUI réelle ni un GPU. Deux validations empiriques complètes ont été réalisées séparément par smoke test manuel, hors suite automatisée : deux générations GPU réelles (Mission 013) et six scénarios réels couvrant Accept/Reject/Regenerate/persistance/changement de Workspace/fermeture (Mission 014) — voir `docs/missions/MISSION_013.md` et `docs/missions/MISSION_014.md`.

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
- ComfyUI Engine minimal (Mission 012) : client HTTP (`ComfyUIEngine`) vers une instance serveur ComfyUI — `submit`/`wait_for_result`/`download_output` génériques + `generate_image` de démonstration.
- Verticale Inference fonctionnelle (Mission 013) : `InferencePage` → `GenerationManager` (Qt-free) → `GenerationWorker`/`QThread` → `ComfyUIEngine` → `Workspace.images`. Génération d'image réelle depuis l'UI, asynchrone (thread dédié, UI non bloquée). **Validée par 138 tests automatisés (entièrement mockés) et par un smoke test réel complet (deux générations GPU successives contre ComfyUI Desktop)** — voir `docs/missions/MISSION_013.md`.
- Validation post-génération (Mission 014) : une génération réussie n'est plus enregistrée automatiquement — `Generate → Preview (QLabel/QPixmap) → Accept/Reject/Regenerate`, seul Accept persiste dans `Workspace.images` (`WORKSPACE_SAVED`/`ImagesPage` inchangés, désormais déclenchés uniquement après Accept). Protection structurelle contre l'enregistrement d'un résultat dans un Workspace différent de celui où il a été généré (défaut réel trouvé en revue technique finale et corrigé avant clôture). **Validée par 159 tests automatisés (entièrement mockés) et par un smoke test réel complet couvrant six scénarios (Accept, Reject, Regenerate, persistance/reload, changement de Workspace avec pending, fermeture avec pending terminé) contre ComfyUI Desktop réel** — voir `docs/missions/MISSION_014.md`. Toujours hors périmètre : `Job`/`Service`/`AI Orchestrator`/`Plugin`, sélection de checkpoint/moteur, images de référence, galerie `ImagesPage`, aperçu agrandi/plein écran, annulation d'une génération en cours, historique de générations (voir "Besoins futurs identifiés par l'usage réel" ci-dessous).

## Décisions techniques importantes à retenir

- Deux patterns d'ownership (Character-owned / Workspace-owned) + deux variantes singleton (Workspace-owned singleton `Settings` / Application-level singleton `ApplicationSettings`) + un pattern contextuel (`Image`, Mission 011, deux pools indépendants sans registre partagé) — voir `CLAUDE.md`.
- Aucune donnée Application (`ApplicationSettings`) n'est jamais stockée dans `project.json` ; aucune donnée Workspace (`Settings`) n'est jamais stockée dans `application_settings.json`. Aucune migration automatique entre les deux — jamais liées.
- Stratégie **"candidate-first"** pour `ApplicationSettingsManager.update()` : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire (contrairement à `SettingsManager`, Mission 009, qui mute avant de sauvegarder — divergence assumée, non rétrofittée).
- Intégrité référentielle Dataset → Training : un Dataset référencé par ≥1 Training ne peut pas être supprimé, sans suppression en cascade.
- `TrainingPage` et `SettingsPage` sont les seules Pages du projet dépendant de deux Managers.
- Ownership `Training` : Character-owned avec un niveau de preuve Blueprint plus nuancé que `Model`/`Workflow` (ambiguïté `Training` vs `Training History` non résolue — voir dettes).
- **Migration `Image` (Mission 011)** — première migration du projet portant sur des données réellement présentes (contrairement à `Model`/`Workflow`, dont les champs équivalents n'avaient jamais contenu de données réelles) : `Image.list_from_data()` convertit `list[str]` (legacy) et `list[dict]` (nouveau format) de façon unifiée, partagée entre `Workspace.from_dict()` et `Dataset.from_dict()`. Un identifiant `uuid4()` est généré pour chaque entrée `str` legacy à chaque chargement tant qu'aucune sauvegarde n'a eu lieu ; il devient stable dès la première sauvegarde au nouveau format. Les doublons de chemin historiques sont préservés comme instances distinctes (aucune fusion, aucune perte).
- **Correction découverte en revue finale de Mission 011** : la première implémentation de `Image.list_from_data()` acceptait silencieusement des entrées `dict` sans `file_path` exploitable (ex. `{}`, `{"image_id": "abc"}` auraient produit une `Image` avec `file_path=""`). Corrigée avant commit : une entrée `dict` n'est conservée que si son `file_path` est un `str` non vide ; une entrée `str` legacy n'est conservée que si elle est non vide. Test de régression ajouté. Fait partie de l'historique technique réel de la mission, volontairement non effacé.
- **Frontière `AI Studio Toolkit → ComfyUI` (Mission 012)** : décidée après un audit dédié montrant que le protocole HTTP de ComfyUI (`/prompt`/`/history`/`/view`) ne distingue pas un node exécutant un modèle local d'un node appelant un service cloud (confirmé par l'existence de custom nodes communautaires type Gemini/Nano Banana s'intégrant au même protocole). `ComfyUIEngine` traite donc tout workflow comme un `dict` opaque — ses primitives génériques (`submit`/`wait_for_result`/`download_output`) ne connaissent ni checkpoint, ni modèle, ni provider. `Plugin`/`AI Orchestrator` volontairement non introduits : avec un seul moteur, ils seraient un pass-through sans logique réelle à porter.
- **Distinction Comfy Cloud API directe (Mission 012)** : Mission 012 implémente le protocole d'une instance serveur ComfyUI (locale ou distante), pas un client direct vers une éventuelle API "Comfy Cloud" hébergée (endpoints/authentification propres, potentiellement différents). Cette distinction est documentée explicitement pour éviter toute fausse promesse architecturale future.
- **Correction découverte en revue finale de Mission 012** : la première implémentation de `wait_for_result()` considérait comme terminé tout `outputs` non vide, sans vérifier qu'une image exploitable y figurait ; `_first_image_reference()` acceptait une référence sans `filename`. Corrigées avant commit : `wait_for_result()` continue le polling jusqu'à l'apparition d'une référence image structurellement exploitable (ou timeout) ; `_first_image_reference()` exige un `filename` non vide. 7 tests ajoutés. Fait partie de l'historique technique réel de la mission, volontairement non effacé.
- **Premier threading Qt du projet (Mission 013)** : idiome standard `QObject` (`GenerationWorker`) déplacé dans un `QThread` via `moveToThread()`. `GenerationManager` reste strictement Qt-free — le worker est la seule classe à connaître à la fois Qt et le Manager. `WorkspaceManager.add_images()` est appelé depuis le thread principal (slot connecté au signal `finished`), jamais depuis le worker, car `Workspace`/`WorkspaceManager` ne sont pas thread-safe.
- **Correction découverte en revue finale de Mission 013 — condition de course QThread** : `_cleanup_thread()` relisait `self._worker`/`self._thread` au moment de son exécution différée (postérieure à la réactivation du bouton) ; une génération relancée dans cette fenêtre pouvait faire détruire/réinitialiser par l'ancien cycle les références du nouveau cycle en cours. Corrigée avant clôture : `worker`/`thread` capturés par valeur dans le callback de cleanup, remise à `None` de `self._worker`/`self._thread` conditionnée à ce qu'ils pointent encore vers ce cycle précis. 4 tests ajoutés (dont 2 avec de vrais `QThread` et reclic immédiat, capturant tout message Qt via `qInstallMessageHandler`). Fait partie de l'historique technique réel de la mission, volontairement non effacé.
- **Limite shutdown Mission 013** : `thread.quit()+wait()` ne constitue pas une annulation — un appel `ComfyUIEngine` déjà en cours (le worker n'a pas encore atteint sa propre boucle d'événements) ne peut être interrompu ; la fermeture de l'application peut donc attendre jusqu'au timeout interne de `ComfyUIEngine` (120 s par défaut). Limite acceptée et documentée, non résolue, non testée empiriquement pendant les smoke tests réels (Mission 013 et Mission 014).
- **Validation post-génération (Mission 014)** : `InferencePage` mémorise un état `pending` transitoire (chemin du fichier téléchargé, jamais persisté avant Accept) et le Workspace actif au lancement de la génération (`_generation_workspace_root`). Aucun nouveau Domain/Manager — `GenerationManager`/`GenerationWorker`/`ComfyUIEngine` strictement inchangés. Aucun nouveau canal EventBus.
- **Correction découverte en revue finale de Mission 014 — liaison pending/Workspace manquante** : ni le passage en pending ni Accept ne vérifiaient que le Workspace actif correspondait à celui actif au lancement de la génération ; `WorkspaceManager.create()`/`.open()` remplacent `current_workspace` sans jamais appeler `close()`, ce qui aurait permis en théorie qu'un résultat né dans un Workspace A soit enregistré dans un Workspace B ouvert entre-temps. Corrigée avant clôture : mémorisation de la racine du Workspace au lancement, vérification à l'arrivée du résultat et à Accept, invalidation proactive du pending via `InferencePage.reset_for_workspace_change()` abonnée par `main_window.py` à `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED` (jamais `WORKSPACE_SAVED`). Vérifiée par tests automatisés dédiés et par le scénario E du smoke test réel. Fait partie de l'historique technique réel de la mission, volontairement non effacé.

## Fichiers et répertoires structurants

```
src/
├── core/event_bus.py, main.py
├── domain/ (11 fichiers, voir tableau ci-dessus)
├── infrastructure/storage/ (workspace_storage.py, application_settings_storage.py)
├── engines/ (comfyui_engine.py — Mission 012, voir section Engines ci-dessus)
├── managers/ (11 fichiers, dont generation_manager.py — Mission 013)
└── ui/main_window.py, sidebar.py, toolbar.py, statusbar.py, menubar.py, generation_worker.py (Mission 013), pages/ (12 fichiers dont base_page.py mort)
tests/integration/ (15 fichiers de test)
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

## Besoins futurs identifiés par l'usage réel (Missions 013 et 014 — non décidés, non implémentés)

Cinq besoins UX/architecture réels sont apparus pendant et après les smoke tests réels des Missions 013 et 014. Ils ne constituent **aucune décision architecturale** — simple constat à évaluer par un futur audit :

- **`ImagesPage` — galerie et aperçu** : l'affichage actuel (liste de chemins de fichiers bruts) est fonctionnel mais insuffisant à l'usage réel — besoin de miniatures, galerie visuelle, sélection, aperçu agrandi, informations de base de l'image.
- **`InferencePage` — images de référence** : besoin réel d'utiliser une ou plusieurs images de référence avec le prompt (planche de personnage, portrait, tenue, pose, décor...), à concevoir de façon compatible avec différents mécanismes ComfyUI futurs (image-to-image, IP-Adapter, ControlNet ou autres) — aucune architecture supposée.
- **`InferencePage` — sélection du moteur/backend** : le besoin multi-engine (ComfyUI, Automatic1111, Fooocus, Forge...) est désormais un besoin utilisateur réel observé, plus seulement une anticipation du Blueprint — à prendre en compte lors des futurs audits Engine/Plugin. ComfyUI reste le seul Engine réellement implémenté et validé ; aucun autre Engine, `Plugin` ou `AI Orchestrator` n'est créé pour anticiper ce besoin. La compatibilité de ComfyUI avec des workflows locaux ou des nodes/services cloud (Mission 012) reste inchangée et pertinente pour ce futur audit.

**Besoin résolu par Mission 014** : "Validation post-génération avant enregistrement" (aperçu avant persistance, Accept/Reject/Regenerate, distinction résultat temporaire/`Image` persistée) — implémenté, voir `docs/missions/MISSION_014.md` et la section "Fonctionnalités terminées" ci-dessus. Retiré de la liste des besoins non implémentés.

### Aperçu agrandi / visualisation plein écran

Constat (Mission 014) : l'aperçu post-génération introduit par Mission 014 fonctionne (ratio conservé, redimensionnement dynamique) mais sa taille actuelle, contrainte par la mise en page d'`InferencePage`, est trop petite pour une inspection visuelle détaillée. Besoin futur identifié, **non décidé, non implémenté** :

- clic sur l'aperçu pour l'agrandir et/ou bouton dédié "Voir en grand" ;
- possibilité d'une fenêtre modale ou d'un affichage plein écran dans AI Studio Toolkit ;
- possibilité éventuelle d'ouvrir l'image dans le visualiseur système (notamment Windows) ;
- Accept/Reject/Regenerate doivent rester indépendants de cette visualisation — ouvrir l'image en grand ne doit jamais modifier son état pending ;
- réutilisation future possible du même mécanisme par `ImagesPage` (voir besoin "galerie et aperçu" ci-dessus) — ces deux besoins restent distincts, aucune architecture commune n'est décidée ici.

## Travaux encore en attente

Aucune direction n'est arrêtée pour Mission 015 — elle nécessitera son propre audit, comme chaque mission précédente, et devra notamment tenir compte des cinq besoins réels listés ci-dessus. Mission 014 a introduit la validation post-génération (`Generate → Preview → Accept/Reject/Regenerate`) au-dessus de la verticale Inference livrée en Mission 013, validée par smoke test réel — mais `src/services/` reste vide, `AI Orchestrator`/`Plugin`/Domain `Engine`/`Job` restent inexistants, `ApplicationSettings.comfyui_url` reste différé, aucune sélection de checkpoint/moteur ni image de référence n'existe, aucun aperçu agrandi/plein écran n'existe. La limite de shutdown sans annulation réelle (voir Décisions techniques) reste non résolue.

## Dernière mission terminée

**Mission 014 — Validation post-génération avant enregistrement.** Voir `docs/missions/MISSION_014.md`. Clôture Git (commit/tag/Release) non encore effectuée au moment de la rédaction de cette mise à jour — voir "État actuel du projet" ci-dessus.

## HEAD du repository

Git fait autorité — vérifier avec `git rev-parse HEAD`. Non documenté en dur ici (voir "Principe de non-auto-référence", section "État actuel du projet").

## Dernier commit de mission

Voir "État actuel du projet" ci-dessus : au moment de la rédaction, le dernier commit de mission réellement présent dans l'historique Git reste celui de Mission 013 (`feat: connect Inference UI to ComfyUI generation`) — la clôture Git de Mission 014 n'a pas encore eu lieu.

## Dernier tag de mission

`v0.2-mission013` (annoté, message `Mission 013 - Inference UI Integration`) reste le dernier tag existant. Cible exacte : Git fait autorité — vérifier avec `git rev-list -n 1 v0.2-mission013`. GitHub Release `v0.2-mission013` publiée — confirmé directement par l'architecte du projet. Le tag de Mission 014 (`v0.2-mission014`, à créer selon la convention établie) n'existe pas encore.

## Prochaine mission prévue

**Non définie.** Mission 015 nécessitera son propre audit architectural avant tout choix, suivant le même format que les audits précédents (relecture complète du Blueprint, inventaire du code existant, comparaison de candidats crédibles, recommandation motivée — jamais un choix par défaut), et devra tenir compte des cinq besoins réels identifiés en Missions 013 et 014 — voir "Besoins futurs identifiés par l'usage réel" ci-dessus.
