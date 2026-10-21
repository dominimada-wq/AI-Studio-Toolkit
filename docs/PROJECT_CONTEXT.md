# PROJECT_CONTEXT.md — État courant du projet AI Studio Toolkit

> **Rôle de ce document.** Il décrit l'**état courant et synthétique** du projet : architecture, comportement actuel, dernière mission close, réserves ouvertes et prochaine étape. C'est la référence de `AGENTS.md` pour savoir « où en est le projet aujourd'hui ». Il **n'est pas un journal** : les détails d'une mission vivent dans `docs/missions/MISSION_NNN.md`, l'index de toutes les missions et les entrées récentes dans [`CHANGELOG.md`](../CHANGELOG.md), et les contenus plus anciens (anciennes versions de ce document, entrées anciennes du journal) dans [`docs/archive/`](archive/README.md). Les statuts datés successifs n'y sont plus recopiés : seul le **statut courant** figure ici.
>
> **Lecture à la reprise.** Lire ce document ; ouvrir `docs/missions/MISSION_NNN.md` pour le détail d'une mission précise ; ne consulter `docs/archive/` que pour retrouver un contenu précis, en passant par l'[index des anciennes sections](#index-des-anciennes-sections) ou par l'index des missions du journal. Il n'y a **aucune lecture systématique des archives** à prévoir.

> **Statut courant (mis à jour le 2026-10-21).** Dernière mission close : **Mission 183 — consolidation documentaire (documentaire uniquement) — publiée et close administrativement ; validation documentaire seulement ; réserves techniques inchangées ; suite complète non validée.** Dernière mission de code close : **Mission 182 — publiée et close administrativement avec réserves ; validation ciblée examinée ; suite complète non validée.** Une clôture administrative ne constitue pas une validation technique complète : elle ne ferme aucune réserve, n'autorise pas L18 et ne rouvre pas le plantage de Mission 177. Les statuts datés antérieurs de la Mission 183 sont dans `docs/missions/MISSION_183.md`. Aucune mission de code suivante n'est sélectionnée.

## Sommaire

- [État actuel du projet](#état-actuel-du-projet)
- [Architecture actuelle](#architecture-actuelle)
- [Fonctionnalités terminées](#fonctionnalités-terminées)
- [Décisions techniques importantes à retenir](#décisions-techniques-importantes-à-retenir)
- [Problèmes connus / dettes](#problèmes-connus--dettes-registre-des-réserves-ouvertes)
- [Besoins futurs identifiés par l'usage réel](#besoins-futurs-identifiés-par-lusage-réel)
- [Orientation architecturale validée](#orientation-architecturale-validée)
- [Dernière mission terminée](#dernière-mission-terminée)
- [HEAD du repository, dernier commit et dernier tag de mission](#head-du-repository-dernier-commit-et-dernier-tag-de-mission)
- [Prochaine mission prévue](#prochaine-mission-prévue)
- [Règles de maintenance de ce document](#règles-de-maintenance-de-ce-document)
- [Index des anciennes sections](#index-des-anciennes-sections)

## État actuel du projet

- **Produit.** Application desktop (PySide6) qui **orchestre** la production de personnages numériques générés par IA (workspace, personnage, images, datasets, LoRA, prompts, modèles, workflows, entraînement, génération d'images) sans remplacer les moteurs existants. Source de vérité produit et architecture : `docs/blueprint/` (5 fichiers, jamais modifiés sans décision architecte séparée). Règles permanentes : `CLAUDE.md`.
- **Moteurs intégrés (lecture du code).** ComfyUI et Forge pour la génération d'images (clients HTTP, installation et lancement locaux configurables), Ollama pour l'assistant de prompt (abstraction `AIBackend`), OneTrainer pour l'entraînement (unique backend d'entraînement supporté ; Kohya/sd-scripts est un backend potentiel futur, non engagé, voir `CLAUDE.md`).
- **Environnement des exécutions consignées.** Les exécutions de tests consignées dans les archives de mission l'ont été sous Windows 10, Python 3.11.9 et PySide6 du venv du projet (6.11.1 constaté en Mission 182) ; tests `unittest` uniquement. Python 3.10, annoncé par le README, **n'a pas été exécuté** dans ces validations : c'est un **écart de couverture**, non une incompatibilité constatée ; Linux et macOS n'ont pas été vérifiés. Ce paragraphe décrit ce qui a été exécuté, pas ce qui est garanti.
- **Dernière mission close.** Mission 183 (documentaire) ; dernière mission de code close : Mission 182 (voir « Dernière mission terminée »).
- **Validation du logiciel (à lire avec les réserves).**
  - **Dernière suite complète dont tous les tests ont réussi : Mission 176** (3 512 tests), classée `OK_NON_NET` (supervision incomplète), donc sans validation globale nette.
  - **Mission 177** : tentative de suite complète interrompue par un arrêt anormal du processus testé (`0xC0000374`), non résolu.
  - **Mission 181** : campagne partitionnée (un processus par module de tests, 66 lots canoniques) **incomplète** — 65 lots sur 66 et 3 486 identifiants distincts sur 3 627 retenus. Ces 3 486 identifiants **proviennent de résultats répartis sur trois manifestes et deux états du code** : 61 lots `NET` (3 061 identifiants), 3 lots `OK_NON_NET` (308) et le lot L04 (117) **retenu par une réévaluation distincte du seul critère Qt, non par une exécution `NET`** ; le lot L66 a réussi après correction du test sur un second état du code. **Ce n'est pas une campagne intégralement réussie sur un état unique.** Le lot L18 (141 tests, fixtures Forge) n'a pas été exécuté et n'est pas autorisé.
  - **Mission 182** : validation **ciblée** de 585 tests (quatre lots `NET`, 346 tests, et L26 `OK_NON_NET`, 239 tests), qui n'est pas une suite complète.
  - **Mission 183** : documentation seulement ; elle ne modifie aucun résultat de validation du logiciel.
  - Le nombre total de tests du projet n'est pas recalculé depuis la Mission 181 (3 627 identifiants canoniques ; Mission 182 en a ajouté 22). **La suite complète n'est pas validée.**
- **Tests.** `tests/integration/` : 66 modules `test_*.py` (les 66 lots de la campagne de Mission 181), des modules d'appui (`_fake_*`, `_qt_dialog_safety_net.py`) et `isolated_test_onetrainer_cancel_helper.py`, volontairement hors de la découverte canonique. Commande canonique : `./.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` — suite complète non validée en l'état : ne pas la lancer sans autorisation explicite.
- **Dépendances.** `requirements.txt` : `PySide6`, `pydantic`, `opencv-python`, `numpy`, `pillow` ; tests en `unittest` de la bibliothèque standard uniquement. Aucune dépendance n'est ajoutée sans validation explicite de l'architecte. Le répertoire de `ApplicationSettings` est résolu par `os`/`pathlib` (Infrastructure indépendante de Qt).
- **Répertoires structurants.** `src/` (couches ci-dessous), `tests/integration/`, `docs/blueprint/` (5 fichiers, source de vérité produit), `docs/missions/` (une archive par mission), `docs/archive/` (archives exactes de la documentation courante), `CLAUDE.md` et `AGENTS.md` (règles et consignes), `README.md` et `CHANGELOG.md` (documentation publique et journal).

**Principe de non-auto-référence (règle permanente pour ce document)** : la documentation versionnée ne doit jamais tenter de figer en dur le hash du commit qui la contient elle-même, ni la cible exacte d'un tag pas encore créé au moment de la rédaction — un tel hash n'existe pas encore, et toute tentative de le documenter force soit une prédiction qui devient fausse dès que le commit/tag réel est créé, soit une chaîne infinie de commits correctifs cherchant chacun à documenter le hash du précédent. Ce piège a été rencontré concrètement en clôture de Mission 011 (voir `docs/missions/MISSION_011.md`) et corrigé définitivement par ce principe. En conséquence : seuls des hashes de commits **déjà existants** au moment de la rédaction (typiquement, le commit fonctionnel d'une mission déjà committé) peuvent être cités en dur dans ce document. Pour "HEAD du repository" et "cible exacte du tag", Git reste en permanence la seule source de vérité — ce document ne les recopie jamais en dur, il indique seulement la commande à exécuter.

## Architecture actuelle

```
Presentation (src/ui/) → Managers (src/managers/) → Domain (src/domain/) → Infrastructure (src/infrastructure/) → Core/EventBus (src/core/)
```

Principes, patterns d'ownership et conventions : `CLAUDE.md` (Single Source of Truth, Dependency Rule, Event Driven UI, Domain indépendant de Qt, Infrastructure ignorant le Domain, Managers sans widgets Qt, EventBus générique sans constante d'événement). L'inventaire ci-dessous est un **constat statique** : il a été relevé par analyse syntaxique des fichiers du dépôt au commit de base de la consolidation, sans exécution ni import. Il ne dit rien du comportement à l'exécution ; il remplace l'ancienne énumération (arrêtée à « 11 classes »), conservée dans `docs/archive/project_context/PC_02_architecture_actuelle.md`.

### Domain (`src/domain/`)

| Classe | Fichier (`src/domain/`) | Champs | Rôle / ownership |
|---|---|---|---|
| `ApplicationSettings` | `application_settings.py` | `python_path`, `comfyui_path`, `comfyui_install_path`, `onetrainer_path`, `comfyui_url`, `comfyui_checkpoint_name`, `comfyui_lora_name`, `comfyui_lora_strength`, `ollama_url`, `ollama_path`, `ollama_model_name`, `lora_library_path`, `comfyui_lora_expose_path`, `forge_path`, `forge_url`, `forge_lora_expose_path` | Application-level, singleton, hors `project.json` |
| `Character` | `character.py` | `character_id`, `name`, `bio`, `description`, `character_lock`, `personality`, `interests`, `trigger_token`, `datasets`, `loras`, `prompts`, `trainings` | Workspace-owned (`Workspace.characters`) |
| `DatasetEntryMetadata` | `dataset.py` | `caption` | métadonnée par image d'un Dataset (`Dataset.entries`) |
| `Dataset` | `dataset.py` | `dataset_id`, `name`, `images`, `entries` | Character-owned |
| `GenerationReference` | `generation_metadata.py` | `path`, `role` | référence d'une provenance (`GenerationMetadata.references`) |
| `GenerationMetadata` | `generation_metadata.py` | `engine`, `prompt`, `negative_prompt`, `seed`, `width`, `height`, `steps`, `cfg`, `sampler_name`, `scheduler`, `checkpoint_name`, `lora_name`, `lora_strength`, `references`, `reference_strength` | provenance d'une image générée (`Image.generation_metadata`) |
| `Image` | `image.py` | `image_id`, `file_path`, `generation_metadata` | contextuel : `Workspace.images` et `Dataset.images` (deux pools indépendants) |
| `LoRA` | `lora.py` | `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version` | Character-owned |
| `Model` | `model.py` | `model_id`, `name`, `file_path` | Workspace-owned |
| `OneTrainerOptimizerSettings` | `onetrainer_optimizer_settings.py` | `optimizer`, `extra_overrides` | sous-réglages de `OneTrainerSettings` |
| `OneTrainerSettings` | `onetrainer_settings.py` | `learning_rate_scheduler`, `train_dtype`, `gradient_checkpointing_mode`, `unet_weight_dtype`, `transformer_weight_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype`, `text_encoder_train`, `text_encoder_2_train`, `text_encoder_stop_training_mode`, `text_encoder_stop_training_after`, `text_encoder_2_stop_training_mode`, `text_encoder_2_stop_training_after`, `lora_layer_filter`, `timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift`, `optimizer_settings`, `extra_overrides` | réglages structurés d'un Training (`Training.onetrainer_settings`) |
| `Prompt` | `prompt.py` | `prompt_id`, `name`, `text` | Character-owned |
| `Settings` | `settings.py` | `theme`, `language` | Workspace-owned, singleton (`Workspace.settings`) |
| `Training` | `training.py` | `training_id`, `name`, `dataset_id`, `base_model_source`, `architecture`, `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `batch_size`, `gradient_accumulation_steps`, `trigger_word`, `onetrainer_settings`, `jobs` | Character-owned |
| `TrainingJob` | `training_job.py` | `job_id`, `state`, `config_snapshot_path`, `expected_output_path`, `final_output_path`, `created_at`, `ended_at`, `error_message`, `imported_lora_id` | exécution d'un Training (`Training.jobs`) |
| `Workflow` | `workflow.py` | `workflow_id`, `name`, `file_path` | Workspace-owned |
| `Workspace` | `workspace.py` | `name`, `version`, `root`, `images`, `models`, `workflows`, `settings`, `characters` | racine (un par `project.json`) |

D'après cet inventaire, `Workspace` n'a plus de collection `datasets`, `loras` ni de champ `training` ; selon un commentaire de `workspace.py`, ces anciennes clés d'un `project.json` ne sont plus lues ni réécrites (retrait des champs vestigiaux : voir l'archive de la Mission 057). Règle de `CLAUDE.md` : le Domain n'importe jamais PySide6.

### Managers (`src/managers/`)

| Manager | Fichier (`src/managers/`) | Événements publiés (constantes locales) |
|---|---|---|
| `ApplicationSettingsManager` | `application_settings_manager.py` | `application_settings.updated` |
| `CharacterManager` | `character_manager.py` | `character.created`, `character.selected`, `character.deleted` |
| `DatasetManager` | `dataset_manager.py` | `dataset.created`, `dataset.selected`, `dataset.deleted` |
| `GenerationManager` | `generation_manager.py` | — |
| `LoRALibraryManager` | `lora_library_manager.py` | `lora_library.imported`, `lora_library.deleted`, `lora_library.updated` |
| `LoRAManager` | `lora_manager.py` | `lora.created`, `lora.selected`, `lora.deleted` |
| `ModelManager` | `model_manager.py` | `model.created`, `model.selected`, `model.deleted` |
| `PromptAssistantManager` | `prompt_assistant_manager.py` | — |
| `PromptManager` | `prompt_manager.py` | `prompt.created`, `prompt.selected`, `prompt.deleted` |
| `SettingsManager` | `settings_manager.py` | — |
| `TrainingManager` | `training_manager.py` | `training.created`, `training.selected`, `training.deleted`, `training_job.created`, `training_job.state_changed` |
| `WorkflowManager` | `workflow_manager.py` | `workflow.created`, `workflow.selected`, `workflow.deleted` |
| (module de fonctions) | `workspace_lifecycle.py` | — |
| `WorkspaceManager` | `workspace_manager.py` | `workspace.created`, `workspace.opened`, `workspace.saved`, `workspace.closed`, `workspace.renamed` |

`GenerationManager` et `PromptAssistantManager` sont décrits par leurs missions comme Qt-free ; ils coordonnent respectivement la génération (via `GenerationWorker`/`QThread`) et l'assistant de prompt (via `AIBackend`). Les dépendances entre Managers suivent les patterns de `CLAUDE.md`.

### Infrastructure (`src/infrastructure/storage/`)

- `WorkspaceStorage` : un seul fichier `project.json` par Workspace ; écriture atomique puis durcie (Missions 027 et 140) ; copie des fichiers importés dans le Workspace (Mission 028) ; erreurs de lecture traduites en `WorkspaceStorageError` (fichier inutilisable, racine non objet, collections de premier niveau mal typées — Missions 162, 178 et 179).
- `ApplicationSettingsStorage` : `ApplicationSettings` hors de tout Workspace (`%LOCALAPPDATA%\AIStudioToolkit\application_settings.json` sous Windows, repli déterministe si `LOCALAPPDATA` est absent).
- `LoRALibraryStorage` : registre de la Bibliothèque LoRA centrale (fichier distinct, hors Workspace).

### Engines (`src/engines/`)

`ComfyUIEngine` (client HTTP d'une instance ComfyUI : soumission, attente, téléchargement, envoi d'images, découverte de checkpoints, diagnostic de connexion) et le module `workflows/` (construction des graphes txt2img et img2img, séparée du transport) ; `ForgeEngine` (client HTTP de Forge) ; `OllamaEngine` (satisfait `AIBackend` ; erreurs d'URL et dépassement de délai distingués) ; configurations d'installation et de lancement locaux de ComfyUI, de Forge et d'OneTrainer ; traduction de la configuration d'entraînement vers le format OneTrainer et assistant d'annulation (`onetrainer_config.py`, `onetrainer_cancel_helper.py`).

### UI (`src/ui/`)

- `MainWindow` : composition root d'après les missions (construit les Managers, les moteurs et les pages, câble le Sidebar et la pile de pages, porte les gardes de fermeture). Règle de `CLAUDE.md` : Sidebar et pile sont alignés **positionnellement** et tout ajout de page est vérifié par exécution réelle ; cette consolidation **n'a pas ré-exécuté** cette vérification (constat statique : `sidebar.py` déclare onze pages).
- Pages, dans l'ordre déclaré du Sidebar : Dashboard, Characters, Images, Datasets, Models, Workflows, LoRA, Prompts, Training, Inference, Settings.
- Dialogues : `NewProjectDialog`, `RenameProjectDialog`, `ImagePreviewDialog`, `ImportCollisionDialog`, `SelectImagesDialog`, `PromptAssistantDialog`.
- Gestionnaires de cycle de vie locaux de ComfyUI et de Forge et leurs workers de disponibilité ; `GenerationWorker`, `PromptAssistantWorker`, `TrainingJobRunner` (processus d'entraînement via `QProcess`) ; module `thumbnails.py` (miniatures avec cache borné, Mission 064) ; barre de menu, d'outils et d'état.
- Principe de `CLAUDE.md` : les pages ne s'appellent jamais entre elles ; rafraîchissement par `EventBus`, ou médiation par `MainWindow` pour les intentions de navigation (par exemple Prompts → Inference, Mission 033).

### Core (`src/core/`), utilitaires, services

`EventBus` générique (aucune constante d'événement : chaque constante `"domaine.verbe"` est définie dans son Manager), configuration, journalisation et point d'entrée (`python -m src.core.main`). `src/utils/` : sources de modèle de base et chemin de la Bibliothèque LoRA. `src/services/` et `src/resources/` ne contiennent que `__init__.py` ; il n'existe pas de `src/plugins/`.

## Fonctionnalités terminées

**Synthèse issue des missions** (titres et récits de leurs archives) : elle n'est **pas une nouvelle vérification** de chaque comportement. Les preuves de chaque point (tests automatisés, smoke tests réels, limites) sont consignées dans l'archive de la mission citée ; elles n'ont pas été rejouées par la consolidation, et les réserves ouvertes (registre ci-dessous) s'appliquent. Index complet : [`CHANGELOG.md`](../CHANGELOG.md#index-des-missions). L'ancienne liste détaillée, arrêtée à la Mission 033, est dans `docs/archive/project_context/PC_04_fonctionnalites_terminees.md`.

- **Workspace et projets.** Création directe d'un dossier de projet avec validation du nom (M016), ouverture, sauvegarde atomique puis durcie (M027, M140), renommage du projet avec remappage des chemins internes (M027, M166, M167), actions du Dashboard et de la barre d'outils câblées (M017, M020), taille adaptative des fenêtres et dialogues (M060, M061), refus de fermeture ou de renommage pendant une génération active (M085).
- **Personnage.** Un projet = un personnage principal créé automatiquement (M026, invariant confirmé en M036) ; fiche d'identité (bio, description, verrou de cohérence, personnalité, centres d'intérêt, jeton déclencheur) ; autres personnages : mécanisme interne conservé, non exposé selon M026.
- **Images et galerie.** Import par copie dans le Workspace avec dialogue de collisions (M028), galerie à miniatures et aperçu agrandi (M015, M019, M064), suppression d'images (M046, M066, M169), tri par nom (M048), par date (M049) et par « Ordre d'ajout (derniers ajouts d'abord) », **défaut** des galeries Images et Datasets (M180) ; métadonnées de provenance des générations (M123).
- **Datasets.** CRUD avec intégrité référentielle vis-à-vis de Training, miniatures (M042), alimentation depuis la galerie Images (M044) par le sélecteur `SelectImagesDialog`, qui présente depuis M182 la liste enregistrée inversée (derniers ajouts d'abord) ; retrait d'images (M045), captions par image (M098) avec protection des brouillons de caption (M158 à M160, M167) et de nom (M165), renommage (M054).
- **LoRA.** LoRA du personnage avec fichiers et fiche de métadonnées (M004, M047, M050) ; **Bibliothèque LoRA centrale** (registre, import, consultation, édition, miniature, M087 à M093) et exposition à ComfyUI et à Forge par lien physique NTFS (M095, M135, M149, M152, M155, M173).
- **Prompts et assistant.** CRUD et renommage (M005, M053) ; assistant IA via Ollama dans Inference et dans Prompts (M030 à M032, M039 à M041, M065, M081, M177), contexte du personnage (M034), transfert Prompts → Inference (M033), enregistrement d'un brouillon comme nouveau prompt (M035).
- **Models et Workflows.** CRUD avec association d'un fichier (M006, M007, M052).
- **Training.** Définition d'un entraînement et adaptateur de configuration OneTrainer avec matérialisation du dataset (M097), exécution (TrainingJob, runner `QProcess`, protocole d'annulation, M100), smoke réel consigné par M101 sur une configuration locale précise (voir R12), réglages de base et avancés (M120 à M132), import du résultat dans la Bibliothèque LoRA (M103, M104), passage vers Inference (M109), report du mot déclencheur (M110, M111), robustesse (M134, M139, M145, M148, M157, M161, M168, M175).
- **Inference.** Génération ComfyUI txt2img et img2img avec image de référence (M013, M022 à M024, M056, M086), validation Accept/Reject/Regenerate avant enregistrement (M014), sélection de checkpoint (M025), de LoRA (M059, M102) et paramètres réels (M096), moteur Forge (M107, M108), démarrage et arrêt locaux des moteurs (M114 à M117, M119, M141, M142, M146, M147), diagnostics de connexion (M112, M174), noms locaux propres aux sorties téléchargées (M176), sélecteur de référence aligné sur le défaut des galeries (M182).
- **Réglages.** Réglages de Workspace (thème, langue) et d'application (chemins, URL, moteurs) ; la Mission 009 décrivait thème et langue comme enregistrés mais non appliqués à l'interface, et une recherche textuelle dans `src/ui` n'y trouve aucune application de ces valeurs (constat lexical, qui ne prouve pas l'absence) ; page réorganisée (M118) ; échecs de persistance gérés (M055, M144, M154).
- **Robustesse transversale.** Retour arrière des mutations lorsque la sauvegarde échoue (M066 à M077), protection des brouillons non sauvegardés à la navigation, au changement de contexte et à la fermeture (M038, M069, M078, M079, M083, M084, M105, M163, M165, M171, M172), isolation des fautes de l'`EventBus` (M136), refus explicite des fichiers de stockage inutilisables et des collections de premier niveau mal typées (M178, M179).

## Décisions techniques importantes à retenir

Décisions **durables** ; le raisonnement complet est dans les archives de mission et dans `docs/archive/project_context/PC_05_decisions_fichiers_dependances.md` (décisions historiques par mission, arrêtées à la Mission 024).

- **Ownership.** Character-owned, Workspace-owned, deux singletons (Settings de Workspace, ApplicationSettings d'application) et un pattern contextuel pour `Image` (deux pools indépendants). Aucune donnée d'application dans `project.json` ni de donnée de Workspace dans `application_settings.json`.
- **Persistance.** `project.json` écrit de façon atomique et durable ; toute mutation Domain suivie d'une sauvegarde échouée est annulée (série M066 à M077) ; les fichiers de stockage inutilisables sont refusés explicitement plutôt que remplacés silencieusement (M144, M178, M179). Compatibilité défensive (`isinstance`) pour les listes imbriquées, jamais présentée comme une migration.
- **Source de vérité unique de configuration.** La configuration des moteurs vit dans `ApplicationSettings` ; un changement ne prend effet qu'au redémarrage pour les moteurs construits au composition root (décision de M018).
- **Génération.** Transport HTTP séparé de la construction des graphes ; images de référence représentées en collection 0..N à toutes les frontières, instantané défensif avant le lancement du thread ; résultat en attente lié au Workspace d'origine et jamais enregistré ailleurs ; New/Open Project autorisés pendant une génération (décision produit de M085).
- **UI.** `Qt.UserRole` porte la donnée fiable (jamais le texte affiché) ; `ImagePreviewDialog` ne reçoit qu'un chemin ; câblage des actions uniquement dans `MainWindow` ; boutons sans cible légitime désactivés avec infobulle plutôt qu'inertes ; protection des brouillons par un contrat dirty-state commun.
- **Assistant.** Aucune page n'appelle `OllamaEngine` directement (décision de M031) ; un seul `PromptAssistantManager` partagé par Inference et Prompts, construit au composition root.
- **Tests.** Convention de `CLAUDE.md` : widgets Qt réels pour l'UI, garde de dialogues modaux dans les fixtures, jamais de `LoRALibraryManager()` sans `storage_directory` temporaire explicite (voir R13), scripts de vérification temporaires uniquement hors dépôt.
- **Documentation.** Principe de non-auto-référence (ci-dessus) ; état courant dans ce document, détails dans `docs/missions/`, index et entrées récentes dans `CHANGELOG.md`, contenus anciens dans `docs/archive/` (en ajout seulement) ; le Blueprint n'est pas modifié sans décision séparée.

## Problèmes connus / dettes (registre des réserves ouvertes)

Ce registre est la **liste unique des réserves ouvertes** ; la publication ou la clôture administrative d'une mission n'en ferme aucune. Les dettes résolues (Missions 011 à 155) ne sont plus recopiées ici : elles sont dans `docs/archive/project_context/PC_06_problemes_connus_dettes.md` et dans les archives de mission. La colonne **Nature** distingue trois cas, qu'il ne faut pas confondre :

- **Réserve établie** : constat consigné dans les archives de mission (observation, résultat de validation, décision) ;
- **Limite de couverture** : ce que les validations consignées n'ont pas exécuté ou observé — cela ne prouve ni un succès ni un échec ;
- **Piste non confirmée** : hypothèse ou constat de lecture sans occurrence observée. Une recherche textuelle sans résultat n'est pas une preuve d'absence.

| Réf. | Nature | Réserve ouverte | Origine | Où lire |
|---|---|---|---|---|
| R1 | Réserve établie | **Suite complète non validée.** Dernière réussite : Mission 176 (3 512 tests, `OK_NON_NET`). Campagne partitionnée de Mission 181 incomplète (65/66 lots, 3 486/3 627 identifiants, résultats répartis sur trois manifestes et deux états du code, L04 retenu par réévaluation) ; validation ciblée de Mission 182 (585 tests) qui n'en tient pas lieu | M176, M181, M182 | MISSION_181 §8 et §13, MISSION_182 §10 et §12 |
| R2 | Limite de couverture | **L18 non exécuté et non autorisé** (`test_forge_lifecycle_manager`, 141 tests : vraies arborescences de processus et vrai `taskkill`) | M181 | MISSION_181 §8 |
| R3 | Réserve établie | **Plantage `0xC0000374` de Mission 177** (arrêt anormal du processus testé en suite complète) : non résolu, non reproduit ni expliqué. Dettes de harnais voisines : fuite de fenêtres Qt en test monoprocessus (M097, +16 sur 126 tests), tentative de correctif rejetée avec preuve et **à ne pas retenter naïvement** (M099), fichier `isolated_test_onetrainer_cancel_helper.py` exécuté à part (M100) | M097, M099, M100, M177 | MISSION_177, MISSION_099, MISSION_100 |
| R4 | Réserve établie | **Réserves Forge F1 à F5** (vrai `taskkill /PID /T /F`, fenêtres de réutilisation de PID, faiblesses de `_LifecycleCase`) | désignées « réserves Forge (K1) » en M179–M180, « F1 à F5 » en M181 | MISSION_181 §1 et §13 |
| R5 | Réserve établie | **Supervision incomplète (`OK_NON_NET`)** : lots L07, L26, L60 et fichier isolé I1 ; en M182, L26 a compté 9 processus dont 5 identifiés (M181 : 7 et 3 sur le même module, dont le contenu a changé : écart non expliqué) ; un `python.exe` enfant sorti avec le code 62097 (`0xF291`) reste **non attribué** (correspondance probable avec la terminaison par `kill()` d'un `QProcess` lancé par les tests, non démontrée) | M176, M181, M182 | MISSION_182 §9 |
| R6 | Réserve établie (observation) ; cause non confirmée | **`Traceback` `QLabel.setText(MagicMock)`** imprimé pendant un test rapporté `ok` (déjà consigné en M175, M176, M181, M182). Test émetteur identifié par les preuves de M182 : `InferencePageEngineSelectorTest.test_switching_engine_preserves_a_real_lora_selection` (cadres `_on_lora_selection_changed` puis `_refresh_lora_trigger_widgets`). **Observé** : le passage d'un `MagicMock` à `setText`. **Non établi** : l'attribution causale (double de test, code de production, ou les deux) ; la production n'est pas exonérée | M175 à M182 | MISSION_182 §9 |
| R7 | Limite de couverture | **Effet à l'écran non observé** pour M180 et M182 ; ordre rendu par `selectedItems()` et par le sélecteur de fichiers **sous interaction réelle** non vérifié (les tests sélectionnent par `setSelected`) | M180, M182 | MISSION_180 §8, MISSION_182 §8 |
| R8 | Limite de couverture | **17 modules de tests atteignent le code modifié par M182 sans avoir été exécutés** dans cette mission (dont les modules construisant un vrai `MainWindow`) : étendue non couverte par la dérogation de M182, non preuve d'échec | M182 | MISSION_182 §8 et §10 |
| R9 | Piste non confirmée | **`project.json` : champs non contrôlés** — collections imbriquées (`datasets`, `loras`, `prompts`, `trainings` du personnage, `Dataset.images`, `LoRA.files`, `Training.jobs`), `settings`, `name`, `version` ; `RecursionError`, autres `ValueError`, fichier modifié pendant la lecture. Le code est établi par lecture ; le risque est **conditionnel à des données mal typées** (édition manuelle, autre outil) ; aucune occurrence ni perte observée | M179, M180 | MISSION_179 §9 |
| R10 | Piste non confirmée | **Relecture de `onetrainer_config.json`** par `TrainingManager.create_job()` : la forme du contenu n'est pas protégée (`config["concepts"][0]["path"]`, établi par lecture) ; déclencheur inconnu | M179 | MISSION_179 §9 |
| R11 | Réserve établie (observations) ; cause non confirmée | **Tests intermittents** : anomalie non attribuée de la clôture de M126 ; échec `1.25 not less than 1.0` du test de garde de dialogue (clôture de M127 et M128, seuil durci par M133, cause sous-jacente non confirmée) ; `ForgeLifecycleManagerRealProcessTest` historiquement instable | M126, M127, M128, M133 | PC_06 (archive) |
| R12 | Réserve établie | **OneTrainer** : constante `__version: 10` de la configuration produite (à revalider à chaque mise à jour de l'installation OneTrainer) ; adaptations locales du smoke de M101 (GPU Pascal / PyTorch, `close_pipe()` Windows) qui sont des correctifs de cette machine, pas des règles universelles ; `CPU_OFFLOADED` n'est pas universellement plus économe en VRAM (M127) | M097, M101, M127 | PC_06 (archive) |
| R13 | Réserve établie | **Piège de test** : `LoRALibraryManager()` sans `storage_directory` explicite écrit dans le registre réel de la machine ; toujours fournir un dossier temporaire | M102, M103 | PC_06 (archive) |
| R14 | Réserve établie | **Blueprint** (non modifié sans décision séparée) : ambiguïté `Training` / `Training History` ; références mortes vers `04_DATA_MODEL.md` et `05_CHARACTER_SYSTEM.md` ; incohérences mineures autour de `Job` ; `00_VISION.md` écrit que Kohya_ss reste responsable de l'entraînement avancé de LoRA, alors que `01_PRODUCT_REQUIREMENTS.md` le déclare backend futur non engagé : **contradiction signalée, non corrigée** | M011 et audits ultérieurs | PC_06 (archive) |
| R15 | Réserve établie | **Documentation.** Corrigés par les modifications de la Mission 183 à partir de sources consignées : mentions de Kohya_ss du README, ligne de statut, fonctionnalités, tests, arborescence et historique des missions du README, état courant et journal. **Restent ouverts** : la contradiction du Blueprint (R14) ; la section « Architecture actuelle » du README, qui est un récit daté des Missions 001 à 010 (signalée comme telle, non réécrite) ; les captures d'écran du README, absentes ; les synthèses du README et de ce document, qui reprennent les missions sans rejouer leurs vérifications | audits post-M177 à post-M182, M183 | README, MISSION_183 |
| R16 | Réserve établie | **Réserves historiques des Missions 173 à 181** (dont la sortie anormale `0xC0000409` du lot ciblé de M174 et l'écart de ce lot au protocole, les incidents de M173, les observations non résolues de M175 et M176, les limites de la supervision) : restent ouvertes | M173 à M181 | documents `MISSION_173` à `MISSION_181` |
| R17 | Piste non confirmée | **Pistes inventoriées par les audits préparatoires (hors dépôt), non sélectionnées** : ordre des gardes de `closeEvent` (répondre « Oui » à l'arrêt d'un moteur puis annuler une garde de brouillon laisse l'application ouverte avec le moteur arrêté ; faible, récupérable) ; nettoyage après construction échouée de `MainWindow` (non validé) ; `TrainingManager.create_job()` (R10) ; assistant de prompt : boîte modale sans annulation jusqu'à 120 s, aucune mesure sur un Ollama réel ; verrou d'instance : une recherche lexicale n'en a pas trouvé, ce qui n'établit pas leur absence ; cache de miniatures : aucun défaut établi par la lecture ; radicaux `-masklabel` / `-condlabel` exclus par OneTrainer (contrat externe, constat statique) | audits post-M177 à post-M182 | MISSION_177 §10 pour une partie ; le reste est ici |
| R18 | Limite de couverture | **Reproductibilité non établie** (une exécution par lot et par état) ; **équivalence avec une exécution monoprocessus non démontrée** | M176 à M182 | MISSION_181 §13, MISSION_182 §10 |
| R19 | Limite de couverture | **Portée des exécutions consignées** : Windows 10 et Python 3.11.9 seulement ; Python 3.10 non exécuté ; Linux et macOS non vérifiés (`ApplicationSettingsStorage.default_directory()` n'est testé que sous Windows) | M011, M179, M182 | PC_06 (archive), MISSION_182 §8 |

## Besoins futurs identifiés par l'usage réel

Besoins UX et architecture **non décidés** enregistrés au fil des missions. Cette consolidation n'a **pas réévalué** leur statut : le tableau reprend les intitulés de l'archive et n'indique « résolu » que lorsque l'intitulé de la source le déclare. Le texte complet, les options et les précisions de l'architecte sont dans `docs/archive/project_context/PC_07_besoins_futurs.md`. Aucun de ces besoins n'est une feuille de route obligatoire.

| Besoin (intitulé abrégé) | Statut | Où le lire |
|---|---|---|
| `InferencePage` — images de référence : usages avancés (rôles/1..N réel/IP-Adapter/ControlNet) | statut non réévalué par la consolidation | PC_07, ligne 5 |
| Envoyer un Dataset de références vers Inference | statut non réévalué par la consolidation | PC_07, ligne 6 |
| `InferencePage` — sélection du moteur/backend | statut non réévalué par la consolidation | PC_07, ligne 7 |
| Sélection de LoRA multi-engine/multi-moteur | statut non réévalué par la consolidation | PC_07, ligne 8 |
| Bibliothèque LoRA centralisée multi-engine | statut non réévalué par la consolidation | PC_07, ligne 9 |
| Cache des vignettes / suppression des redécodages complets inutiles | résolu (selon l'intitulé de la source) | PC_07, ligne 10 |
| `PromptAssistantDialog` — Échap/fermeture pendant une génération active contournent le bouton Annuler désactivé | résolu (selon l'intitulé de la source) | PC_07, ligne 11 |
| Aléa d'environnement natif Qt/PySide6 (segfault en suite complète — priorité d'investigation depuis Mission 064, initialement observé pendant Missi… | statut non réévalué par la consolidation | PC_07, ligne 12 |
| Publication sur réseaux sociaux | statut non réévalué par la consolidation | PC_07, ligne 13 |
| `ComfyUI Installation Folder` — exploitation du champ `comfyui_path` déjà existant | statut non réévalué par la consolidation | PC_07, ligne 18 |
| Réglage utilisateur de la force img2img / `denoise` | statut non réévalué par la consolidation | PC_07, ligne 21 |
| `ImagesPage`/`DatasetsPage` — tri de la galerie | résolu (selon l'intitulé de la source) | PC_07, ligne 22 |
| Refonte et organisation future de la page Settings | statut non réévalué par la consolidation | PC_07, ligne 29 |
| Import d'images — copie dans le dossier `images` du projet | résolu (selon l'intitulé de la source) | PC_07, ligne 39 |
| Alimentation d'un Dataset depuis la galerie Images | résolu (selon l'intitulé de la source) | PC_07, ligne 40 |
| `DatasetsPage` — miniatures des images du Dataset | résolu (selon l'intitulé de la source) | PC_07, ligne 45 |
| Retrait d'une image d'un Dataset | résolu (selon l'intitulé de la source) | PC_07, ligne 51 |
| Dette de cohérence Character — `active_character` vs `principal_character` dans `LoRAManager`/`PromptManager`/`TrainingManager` | résolu (selon l'intitulé de la source) | PC_07, ligne 58 |
| Dashboard — clarification de l'indicateur Training | résolu (selon l'intitulé de la source) | PC_07, ligne 59 |
| Internationalisation / localisation de l'interface | statut non réévalué par la consolidation | PC_07, ligne 62 |
| Assistant IA / LLM intégré à AI Studio Toolkit | statut non réévalué par la consolidation | PC_07, ligne 63 |
| Prompt Library structurée | statut non réévalué par la consolidation | PC_07, ligne 84 |
| RAG local dérivé de la Prompt Library | statut non réévalué par la consolidation | PC_07, ligne 87 |
| `PromptsPage` — perte silencieuse d'un texte non sauvegardé | résolu (selon l'intitulé de la source) | PC_07, ligne 100 |
| `PromptAssistantDialog` — clarté visuelle du sélecteur de mode Créer/Améliorer | résolu (selon l'intitulé de la source) | PC_07, ligne 106 |
| Ambiguïté transversale des messages « Aucun personnage » lorsqu'aucun projet/Workspace n'est ouvert | résolu (selon l'intitulé de la source) | PC_07, ligne 110 |
| Ambiguïté distincte — `TrainingPage.create_training()` affiche « Aucun dataset disponible » lorsqu'aucun Workspace n'est ouvert | résolu (selon l'intitulé de la source) | PC_07, ligne 114 |
| Support de la génération vidéo par IA | statut non réévalué par la consolidation | PC_07, ligne 118 |
| Évolution future de `DatasetEntryMetadata` | statut non réévalué par la consolidation | PC_07, ligne 129 |
| Génération de captions par IA | statut non réévalué par la consolidation | PC_07, ligne 130 |
| Stratégies de captions selon le moteur d'entraînement cible | statut non réévalué par la consolidation | PC_07, ligne 131 |
| Miniature de Prompt dans la future Prompt Library | statut non réévalué par la consolidation | PC_07, ligne 132 |
| Exposition progressive des réglages OneTrainer dans `TrainingPage` — Basic/Advanced/Presets | statut non réévalué par la consolidation | PC_07, ligne 133 |
| Diagnostic de compatibilité Training Engine / GPU / PyTorch | statut non réévalué par la consolidation | PC_07, ligne 134 |
| Gestion automatique du backend ComfyUI par AI Studio Toolkit | statut non réévalué par la consolidation | PC_07, ligne 135 |
| Gestion automatique du backend Forge par AI Studio Toolkit, à étudier conjointement avec le besoin ComfyUI ci-dessus | statut non réévalué par la consolidation | PC_07, ligne 144 |
| Refonte UX/UI de `InferencePage` | statut non réévalué par la consolidation | PC_07, ligne 155 |
| Séparation application / données persistantes / projets / bibliothèques de modèles / caches pour la distribution future de Toolkit | statut non réévalué par la consolidation | PC_07, ligne 156 |
| Emplacement racine configurable pour les projets, avec migration sécurisée | statut non réévalué par la consolidation | PC_07, ligne 157 |
| Dossiers physiques de la Central LoRA Library — nom humainement lisible plutôt qu'UUID seul | statut non réévalué par la consolidation | PC_07, ligne 158 |
| Sélection graphique (parcourir un dossier) pour les champs d'installation ComfyUI | statut non réévalué par la consolidation | PC_07, ligne 159 |
| Réorganisation de `SettingsPage` | résolu (selon l'intitulé de la source) | PC_07, ligne 160 |
| Amélioration UX de l'import automatique des sidecars `.txt` de caption | statut non réévalué par la consolidation | PC_07, ligne 161 |
| Liaison Character ↔ Training ↔ LoRA pour le trigger | statut non réévalué par la consolidation | PC_07, ligne 162 |
| Hardware-aware Training defaults/presets + Training Preflight | statut non réévalué par la consolidation | PC_07, ligne 163 |

## Orientation architecturale validée

**1 Project/Workspace = 1 personnage IA principal.** La section Characters représente la fiche d'identité du personnage principal ; Images, Datasets, LoRA, Training, Prompts et Inference restent rattachés au même projet. Première brique : Mission 026 ; invariant confirmé par la Mission 036 (un projet ouvert possède nécessairement un personnage principal). La liste multi-personnages interne est conservée comme mécanisme transitoire. Texte complet : `docs/archive/project_context/PC_08_orientation_et_travaux_en_attente.md`.

## Dernière mission terminée

**Mission 183 — Consolidation documentaire : état courant synthétique, archives exactes et index des missions** (documentaire uniquement ; titre de Release : « Consolidate Project Documentation and Preserve Historical Archives »). **Publiée et close administrativement ; validation documentaire seulement ; réserves techniques inchangées ; suite complète non validée.** Ce document, le journal indexé, les archives exactes de `docs/archive/` et les corrections du README en sont les résultats ; aucun test applicatif n'a été lancé, aucune production ni aucun test n'a été modifié. Détail, décisions datées, vérifications et limites : `docs/missions/MISSION_183.md` (sections 6, 7 et 10).

**Dernière mission de code terminée : Mission 182 — Harmoniser l'ordre des sélecteurs de miniatures avec le défaut des galeries** (titre de Release : « Show Recent Gallery Additions First in Image Pickers »). **Publiée et close administrativement avec réserves ; validation ciblée examinée ; suite complète non validée.**

- **Comportement.** Depuis la Mission 180, les galeries Images et Datasets présentent par défaut la liste enregistrée inversée. Les deux sélecteurs de miniatures — « Ajouter depuis Images… » (Datasets) et le choix de l'image de référence (Inference) — présentent désormais la liste enregistrée **inversée** aussi, par un paramètre nommé `reversed_display` de `SelectImagesDialog` (défaut `False`, les deux appelants passent `True`). Ce n'est ni une date ni une chronologie garantie. `selected_paths()` retourne les éléments sélectionnés dans l'ordre de la liste fournie au dialogue, pour les deux valeurs du paramètre : c'est une **clarification du contrat**, qui ne prétend pas préserver tous les comportements historiques non spécifiés de Qt. Aucun changement du Domain, des Managers ni du stockage.
- **Validation.** 585 tests ciblés réussis en cinq lots : quatre `NET` (L54 22, L12 108, L20 49, L11 167 : 346 tests) et L26 `OK_NON_NET` (239 tests, inventaire de processus incomplet exclusivement). Une découverte sans exécution de tests, deux comparatifs sur l'ancien code (A1 : arrêt d'outillage historique conservé ; A2 : prévisions confirmées, un identifiant exploratoire rapporté à part) précèdent le lancement B. Dérogation de validation **propre à M182**. Ce n'est pas une suite complète.
- **Réserves.** R1, R5, R6, R7, R8 ci-dessus.
- **Détail.** `docs/missions/MISSION_182.md` (sections 7 à 10 pour la validation, 15 pour la publication).

Missions précédentes (toutes publiées et closes administrativement avec réserves ; récits dans leurs archives) : M181 — campagne de validation partitionnée et correction du test L66 ; M180 — critère de tri « Ordre d'ajout » des galeries ; M179 — refus des collections de premier niveau mal typées ; M178 — refus explicite des fichiers de stockage inutilisables ; M177 — délais d'Ollama distingués et délai de l'assistant allongé. Les statuts datés successifs de chacune sont dans `docs/archive/project_context/PC_01_en-tete_et_etat_actuel.md` et `PC_09_derniere_mission_terminee.md`.

## HEAD du repository, dernier commit et dernier tag de mission

- **HEAD.** Git fait autorité : `git rev-parse HEAD`. Ce document ne fige jamais cette valeur.
- **Dernier commit fonctionnel de mission de code.** Mission 182 : `a761ef97c9caffee8503990aca6346e8718cc4f6` (`Show recent gallery additions first in image pickers`, dix fichiers : trois de production, quatre de tests, trois documents). Il est précédé par le commit documentaire de régularisation de Mission 181 (non référencé en dur) et par le commit de Mission 181 `943238d300428515861433f15d3d84b084f4c9b4`. Les commits documentaires de régularisation ne sont jamais la cible d'un tag. **Mission 183 (documentaire)** : commits de contenu `d66cc51bce4363dc48c0ff58352081dbe0ef887c` puis `f1dc978e4972cfa74c74582967074e18ab8e56b9` ; le commit documentaire de régularisation qui consigne cette publication n'est pas référencé ici (non-auto-référence).
- **Dernier tag.** `v0.2-mission183` (annoté), objet `ff997f002ee7aba6812876afdf32520af7d8daa7`, ciblant exactement le second commit de contenu de la Mission 183 (`f1dc978e4972cfa74c74582967074e18ab8e56b9`). Vérifier avec `git rev-list -n 1 v0.2-mission183` (`git rev-parse v0.2-mission183` seul retourne l'objet tag annoté lui-même). GitHub Release `v0.2-mission183` publiée manuellement le 2026-10-21 (identifiant 419326095). Dernier tag d'une mission de code : `v0.2-mission182` (annoté), objet `4225080f735b73ac7fb76683c5739db8263daefa`, ciblant exactement le commit de Mission 182 ; GitHub Release publiée manuellement le 2026-10-20 (identifiant 418508035). Les tags `v0.2-mission001` à `v0.2-mission183` existent, **à l'exception de la Mission 138** (pas de tag, constat Git) ; **l'existence d'un tag atteste une publication, ni la clôture ni la validation complète de la mission** (le statut de chaque mission est dans son archive). `CLAUDE.md` documente deux exceptions historiques en tags légers (`v0.2-mission003`, `v0.2-mission006`) ; les tags récents sont annotés. L'état de chaque tag antérieur n'est plus recopié ici : `git tag -n1 -l 'v0.2-mission*'`.

## Prochaine mission prévue

- **Aucune mission de code n'est sélectionnée.** L18 reste non autorisé ; le plantage `0xC0000374` de Mission 177 reste hors périmètre.
- **Mission 183 (documentaire)** : close administrativement (voir « Dernière mission terminée ») ; aucune suite de cette mission n'est en attente.
- **Candidats restants** (audit post-M182, hors dépôt) : B — collections imbriquées de `project.json` (R9) ; C — ordre des gardes de `closeEvent` (R17) ; E — attribution du `Traceback` `setText(MagicMock)` (R6) ; étapes de validation sans code (vérification à l'écran par l'utilisateur, exécution des modules non couverts, instrumentation de la supervision), chacune soumise à autorisation séparée.
- **Décisions que l'architecte devra prendre avant toute mission de code** : candidat retenu et variante ; politique de validation (dérogation motivée ou campagne autorisée séparément, sort de L18 distinct).

## Règles de maintenance de ce document

1. **Un statut courant, pas d'empilement.** À la clôture d'une mission, remplacer le statut courant ; ne pas recopier les statuts datés antérieurs. Ils vivent dans `docs/missions/MISSION_NNN.md` (section de statut) et dans `CHANGELOG.md`.
2. **Ce qui doit être mis à jour à chaque mission** : « Statut courant », « État actuel du projet » (validation, tests), « Architecture actuelle » si elle change, « Fonctionnalités terminées » (une puce par domaine), le registre des réserves (ajouter ou clore avec sa source, jamais effacer silencieusement ; une réserve fermée est mentionnée dans l'archive de la mission qui la ferme), « Dernière mission terminée », « Dernier commit/tag », « Prochaine mission prévue ».
3. **Les réserves restent visibles** dans le registre tant qu'elles sont ouvertes ; une clôture administrative n'en ferme aucune. Distinguer réserves établies, limites de couverture et pistes non confirmées.
4. **Pas de journal ici.** Un récit détaillé, une chronologie de validation, une liste de pièces hors dépôt vont dans `docs/missions/MISSION_NNN.md`.
5. **Archives immuables, index actualisables.** Les **contenus archivés** de `docs/archive/` et leurs **manifestes de référence** (`MANIFEST.json`, `CORRESPONDANCE.md`) ne se modifient jamais ; toute copie y est exacte et vérifiée par empreinte (voir son README). Un archivage ultérieur — par exemple celui des entrées du journal qui sortent des dix dernières missions — crée de **nouveaux** fichiers d'archive avec **leur propre manifeste**. Seuls les **index de navigation** (l'index de `CHANGELOG.md`, l'index des anciennes sections ci-dessous, `docs/archive/README.md`) sont actualisés, pour référencer les nouvelles archives, sans toucher aux archives précédentes. L'archive ne couvre pas les règles permanentes : les anciennes formulations de `CLAUDE.md` et `AGENTS.md` se retrouvent dans l'historique Git.
6. **Ordre de grandeur visé** : quelques dizaines de kilo-octets. Un dépassement durable signale qu'un récit s'est glissé dans l'état courant.
7. **Non-auto-référence** : voir le principe ci-dessus.

## Index des anciennes sections

Les renvois textuels des documents de mission (« voir *Besoins futurs identifiés*… ») restent valides : chaque ancienne section est ou bien conservée sous le même nom dans ce document, ou bien archivée à l'identique. Aucun lien direct vers une ancre de ce document n'existe ailleurs dans le dépôt (contrôle de la Mission 183).

| Ancienne section de `PROJECT_CONTEXT.md` | Où la lire aujourd'hui |
|---|---|
| En-tête, bandeaux de statut, « État actuel du projet » (statuts datés successifs des missions récentes, suite de tests) | `docs/archive/project_context/PC_01_en-tete_et_etat_actuel.md` ; état courant résumé ci-dessus |
| « Architecture actuelle » (Domain, Managers, Infrastructure, Engines, UI, EventBus) | `PC_02_architecture_actuelle.md` ; remplacée par l'inventaire à jour ci-dessus |
| « Tests » (énumération historique par fichier, non maintenue) | `PC_03_tests_enumeration_historique.md` |
| « Fonctionnalités terminées » (arrêtée à la Mission 033) | `PC_04_fonctionnalites_terminees.md` ; synthèse à jour ci-dessus |
| « Décisions techniques importantes à retenir », « Fichiers et répertoires structurants », « Dépendances importantes » | `PC_05_decisions_fichiers_dependances.md` |
| « Problèmes connus / dettes » | `PC_06_problemes_connus_dettes.md` ; réserves ouvertes dans le registre ci-dessus |
| « Besoins futurs identifiés par l'usage réel » | `PC_07_besoins_futurs.md` ; intitulés ci-dessus |
| « Orientation architecturale validée », « Travaux encore en attente » | `PC_08_orientation_et_travaux_en_attente.md` |
| « Dernière mission terminée » (récits des missions récentes) | `PC_09_derniere_mission_terminee.md` |
| « HEAD du repository », « Dernier commit de mission », « Dernier tag de mission » | `PC_10_head_commit_tag.md` ; état courant ci-dessus |
| « Prochaine mission prévue » (énoncés datés empilés) | `PC_11_prochaine_mission_prevue.md` |

Les fichiers `docs/archive/project_context/PC_01` à `PC_11` sont des **tranches contiguës et exactes** du document d'origine (commit `cd86418dacf3cd6c332dc9259d8d0883c6365774`) : leur concaténation, dans l'ordre, redonne le document d'origine octet pour octet (voir `docs/archive/README.md`).
