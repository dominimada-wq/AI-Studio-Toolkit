# README — extraits retirés lors de la consolidation documentaire (archive)

> Copie exacte, au commit `cd86418dacf3cd6c332dc9259d8d0883c6365774`, de deux sections retirées du `README.md` par la Mission 183 : « Roadmap des prochaines missions » puis « Structure du dépôt » (arborescence d'origine, arrêtée à la Mission 010). Chaque section est reproduite sans modification dans un bloc de code ; les liens y sont volontairement inactifs. Ce fichier est immuable.

## Section « Roadmap des prochaines missions »

````markdown
## Roadmap des prochaines missions

L'historique détaillé et le raisonnement derrière chaque décision se trouvent dans [`CHANGELOG.md`](CHANGELOG.md).

| Mission | Statut | Contenu |
|---|---|---|
| Mission 001 | ✅ Terminée (`v0.2-mission001`) | Refactoring Blueprint 02 : couches Presentation / Managers / Domain / Infrastructure / Core, `EventBus`, tests d'intégration |
| Mission 002 | ✅ Terminée (`v0.2-mission002`) | Introduction du domaine `Character`, entité centrale du Blueprint : CRUD, sélection, persistance, page dédiée |
| Mission 003 | ✅ Terminée (`v0.2-mission003`) | Introduction du domaine `Dataset` : CRUD, sélection, import d'images fonctionnel dès cette mission (déduplication, ordre préservé) |
| Mission 004 | ✅ Terminée (`v0.2-mission004`) | Introduction du domaine `LoRA` : CRUD, sélection, import de fichiers fonctionnel dès cette mission (déduplication, ordre préservé) ; Domain volontairement étendu (8 champs) au-delà du minimalisme appliqué à `Character`/`Dataset` |
| Mission 005 | ✅ Terminée (`v0.2-mission005`) | Introduction du domaine `Prompt` : CRUD, sélection, édition de texte (`update_text()`, idempotent) ; Domain volontairement minimal (3 champs), catégories différées ; correctif Dashboard "LoRA" traité en ouverture |
| Mission 006 | ✅ Terminée (`v0.2-mission006`) | Introduction du domaine `Model` : CRUD, sélection, association de fichier (`update_file_path()`, idempotent) ; première ressource Workspace-owned, premier Manager sans dépendance à `CharacterManager` ; carte Dashboard "Models" déjà correcte sans correctif nécessaire (confirmé lors de l'audit Mission 007) |
| Mission 007 | ✅ Terminée (`v0.2-mission007`) | Introduction du domaine `Workflow` : CRUD, sélection, association de fichier externe (`update_file_path()`, idempotent) ; deuxième ressource Workspace-owned après `Model` ; Domain minimal, aucune fonctionnalité d'exécution |
| Mission 008 | ✅ Terminée (`v0.2-mission008`) | Introduction du domaine `Training` : CRUD (création, sélection, suppression) de sessions d'entraînement au sein du personnage actif, sélection du Dataset source ; nouvelle entité Character-owned aux côtés de `Dataset`/`LoRA`/`Prompt` ; première intégrité référentielle inter-entités du projet (Dataset → Training) ; aucune exécution d'entraînement |
| Mission 009 | ✅ Terminée (`v0.2-mission009`) | Introduction du domaine `Settings` (Workspace) : singleton `Workspace.settings` (`theme`, `language`), `SettingsManager` sans collection ni sélection, `SettingsPage` réelle avec sauvegarde explicite ; retrait des anciens champs machine-locale, actés comme relevant d'une future Application Settings ; aucun événement dédié |
| Mission 010 | ✅ Terminée (`v0.2-mission010`) | Introduction du domaine `ApplicationSettings` (Application-level, hors `project.json`) : `python_path`, `comfyui_path`, `onetrainer_path`, stockage local dédié (`ApplicationSettingsStorage`, écriture atomique), `ApplicationSettingsManager`, intégration dans `SettingsPage` en section indépendante de Workspace Settings ; aucune validation de chemin, aucun lancement d'outil |
| Mission 011 | 📋 À définir | — |
| Missions suivantes | 📋 Planifiées | `Job`, `Engine`, `Plugin` (une entité par mission, sans anticipation non justifiée) ; migration de `ImagesPage`/`Workspace.images` vers `Character.images` (toujours différée) ; couche Services dès qu'une logique métier réelle la justifie ; `src/engines/` et `src/plugins/` lors de la première intégration réelle avec un moteur externe |

Amélioration UX ponctuelle identifiée en cours de route, hors périmètre des missions d'architecture : création du dossier cible directement depuis le dialogue "Nouveau projet", sans devoir le créer manuellement au préalable dans l'explorateur Windows.

````

## Section « Structure du dépôt » (arborescence d'origine)

````markdown
## Structure du dépôt

```
AI-Studio-Toolkit/
├── assets/                     # Icônes, thèmes, templates — vide pour l'instant
├── datasets/                   # Datasets importés — vide pour l'instant
├── docs/
│   ├── blueprint/              # Documents de référence architecturale (source de vérité)
│   │   ├── 00_VISION.md
│   │   ├── 01_PRODUCT_REQUIREMENTS.md
│   │   ├── 02_ARCHITECTURE.md
│   │   ├── 03_PROJECT_STRUCTURE.md
│   │   └── 04_DOMAIN_MODEL.md
│   └── images/                 # Captures d'écran (à venir)
├── examples/                   # Exemples d'utilisation — vide pour l'instant
├── models/                     # Checkpoints, LoRA, VAE partagés — vide pour l'instant
├── scripts/                    # Scripts utilitaires, packaging — vide pour l'instant
├── src/
│   ├── core/                   # EventBus, point d'entrée, bootstrap
│   │   ├── event_bus.py
│   │   └── main.py
│   ├── domain/                 # Objets métier (Workspace, Character, Dataset, LoRA, Prompt, Model, Workflow, Training, Settings, ApplicationSettings, ...)
│   │   ├── workspace.py
│   │   ├── character.py
│   │   ├── dataset.py
│   │   ├── lora.py
│   │   ├── prompt.py
│   │   ├── model.py
│   │   ├── workflow.py
│   │   ├── training.py
│   │   ├── settings.py
│   │   └── application_settings.py
│   ├── infrastructure/         # Persistance
│   │   └── storage/
│   │       ├── workspace_storage.py
│   │       └── application_settings_storage.py
│   ├── managers/                # Coordination applicative (WorkspaceManager, CharacterManager, DatasetManager, LoRAManager, PromptManager, ModelManager, WorkflowManager, TrainingManager, SettingsManager, ApplicationSettingsManager, ...)
│   │   ├── workspace_manager.py
│   │   ├── character_manager.py
│   │   ├── dataset_manager.py
│   │   ├── lora_manager.py
│   │   ├── prompt_manager.py
│   │   ├── model_manager.py
│   │   ├── workflow_manager.py
│   │   ├── training_manager.py
│   │   ├── settings_manager.py
│   │   └── application_settings_manager.py
│   ├── ui/                     # Fenêtre principale, pages, widgets
│   │   ├── main_window.py
│   │   └── pages/
│   │       ├── characters_page.py
│   │       ├── datasets_page.py
│   │       ├── lora_page.py
│   │       ├── prompts_page.py
│   │       ├── models_page.py
│   │       ├── workflows_page.py
│   │       ├── training_page.py
│   │       └── settings_page.py
│   ├── resources/               # Ressources embarquées (icônes, thèmes...) — vide pour l'instant
│   ├── services/                 # Opérations métier réutilisables — vide pour l'instant
│   └── utils/                   # Utilitaires transverses — vide pour l'instant
├── tests/
│   └── integration/
│       ├── test_workspace_roundtrip.py
│       ├── test_character_roundtrip.py
│       ├── test_dataset_roundtrip.py
│       ├── test_lora_roundtrip.py
│       ├── test_prompt_roundtrip.py
│       ├── test_model_roundtrip.py
│       ├── test_workflow_roundtrip.py
│       ├── test_training_roundtrip.py
│       ├── test_settings_roundtrip.py
│       └── test_application_settings_roundtrip.py
├── workflows/                   # Workflows ComfyUI/Fooocus, presets — vide pour l'instant
├── CHANGELOG.md
├── README.md
├── pyproject.toml
└── requirements.txt
```

````
