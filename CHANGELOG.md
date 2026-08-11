# Changelog

Toutes les évolutions notables du projet **AI Studio Toolkit** sont documentées dans ce fichier.

## Sommaire

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
- Hors périmètre, différé et non abandonné : scan automatique de fichiers, métadonnées du Domain (`provider`, `hash`, `architecture`, `thumbnail`...), `Character.favorite_models`, correctif de la carte Dashboard "Models".

### Tests ajoutés (Mission 006)

`tests/integration/test_model_roundtrip.py` (8 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_file_path()` (y compris la chaîne vide comme changement réel), suppression avec persistance, **preuve inversée** qu'un changement de personnage ne réinitialise jamais `active_model_id`, reconstruction de `ModelsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images, et un test dédié au round-trip `to_dict()`/`from_dict()` du Domain `Model` (valeurs par défaut, clé absente, filtrage défensif sur liste mixte).

### Prochaines étapes (Mission 006)

Sans engagement définitif :

- Correctif différé de la carte Dashboard "Models" — non traité cette mission, `Workspace.models` étant désormais réellement peuplé mais l'affichage nécessite sa propre réflexion (pas d'agrégation par personnage possible, contrairement à `datasetsCard`/`lorasCard`).
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
