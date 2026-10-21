# Changelog — archive : Missions 123 à 084

> **Archive de `CHANGELOG.md`.** Ce fichier reçoit, **sans aucune modification**, les entrées de missions 123 à 084 du journal d'origine (copie exacte, vérifiée par empreinte ; voir [`README.md` de l'archive](../README.md) et la [table de correspondance](../CORRESPONDANCE.md)). Le Sommaire ci-dessous reprend, mot pour mot, les lignes correspondantes du Sommaire d'origine : ses ancres restent valides dans ce fichier. L'index de toutes les missions, avec renvoi vers chaque entrée, est en tête de [`CHANGELOG.md`](../../../CHANGELOG.md). Les états décrits dans ces entrées sont ceux **de leur date** ; l'état courant est dans [`docs/PROJECT_CONTEXT.md`](../../PROJECT_CONTEXT.md). Ce fichier et son manifeste de référence sont immuables : un archivage ultérieur crée de nouveaux fichiers avec leur propre manifeste ; seuls les index de navigation sont actualisés.

## Sommaire

- **Mission 123 — Generation Provenance/Metadata Persistence**
  - [Résumé (Mission 123)](#résumé-mission-123)
  - [Tests ajoutés (Mission 123)](#tests-ajoutés-mission-123)
  - [État du projet (Mission 123)](#état-du-projet-mission-123)
- **Mission 122 — Advanced Training Settings: Optimizer**
  - [Résumé (Mission 122)](#résumé-mission-122)
  - [Tests ajoutés (Mission 122)](#tests-ajoutés-mission-122)
  - [État du projet (Mission 122)](#état-du-projet-mission-122)
- **Mission 121 — Advanced OneTrainer Precision Settings (Training/Weight Dtypes)**
  - [Résumé (Mission 121)](#résumé-mission-121)
  - [Tests ajoutés (Mission 121)](#tests-ajoutés-mission-121)
  - [Correctif post-release (Mission 121)](#correctif-post-release-mission-121)
  - [État du projet (Mission 121)](#état-du-projet-mission-121)
- **Mission 120 — Advanced OneTrainer Training Configuration Foundation**
  - [Résumé (Mission 120)](#résumé-mission-120)
  - [Tests ajoutés (Mission 120)](#tests-ajoutés-mission-120)
  - [État du projet (Mission 120)](#état-du-projet-mission-120)
- **Mission 119 — Forge Local Lifecycle Management (Start/Stop/Ownership/Readiness)**
  - [Résumé (Mission 119)](#résumé-mission-119)
  - [Tests ajoutés (Mission 119)](#tests-ajoutés-mission-119)
  - [État du projet (Mission 119)](#état-du-projet-mission-119)
- **Mission 118 — SettingsPage Navigation Reorganization**
  - [Résumé (Mission 118)](#résumé-mission-118)
  - [Tests ajoutés (Mission 118)](#tests-ajoutés-mission-118)
  - [État du projet (Mission 118)](#état-du-projet-mission-118)
- **Mission 117 — Explicit Cancel for the ComfyUI Auto-Start Wait in InferencePage**
  - [Résumé (Mission 117)](#résumé-mission-117)
  - [Tests ajoutés (Mission 117)](#tests-ajoutés-mission-117)
  - [État du projet (Mission 117)](#état-du-projet-mission-117)
- **Mission 116 — ComfyUI Auto-Start Progress Feedback in InferencePage**
  - [Résumé (Mission 116)](#résumé-mission-116)
  - [Tests ajoutés (Mission 116)](#tests-ajoutés-mission-116)
  - [État du projet (Mission 116)](#état-du-projet-mission-116)
- **Mission 115 — ComfyUI Auto-Start from Inference with Pending Generation Handoff**
  - [Résumé (Mission 115)](#résumé-mission-115)
  - [Tests ajoutés (Mission 115)](#tests-ajoutés-mission-115)
  - [État du projet (Mission 115)](#état-du-projet-mission-115)
- **Mission 114 — ComfyUI Local Lifecycle Management (Start/Stop/Ownership/Readiness)**
  - [Résumé (Mission 114)](#résumé-mission-114)
  - [Tests ajoutés (Mission 114)](#tests-ajoutés-mission-114)
  - [État du projet (Mission 114)](#état-du-projet-mission-114)
- **Mission 113 — Local ComfyUI/Forge Installation Paths and Static Launcher Validation**
  - [Résumé (Mission 113)](#résumé-mission-113)
  - [Tests ajoutés (Mission 113)](#tests-ajoutés-mission-113)
  - [État du projet (Mission 113)](#état-du-projet-mission-113)
- **Mission 112 — Explicit ComfyUI / Forge Connection Diagnostics in Settings**
  - [Résumé (Mission 112)](#résumé-mission-112)
  - [Tests ajoutés (Mission 112)](#tests-ajoutés-mission-112)
  - [État du projet (Mission 112)](#état-du-projet-mission-112)
- **Mission 111 — Character.trigger_token → Training.trigger_word Default Prefill**
  - [Résumé (Mission 111)](#résumé-mission-111)
  - [Tests ajoutés (Mission 111)](#tests-ajoutés-mission-111)
  - [État du projet (Mission 111)](#état-du-projet-mission-111)
- **Mission 110 — Training → LoRA Trigger Carryover + Explicit Trigger Use in Inference**
  - [Résumé (Mission 110)](#résumé-mission-110)
  - [Tests ajoutés (Mission 110)](#tests-ajoutés-mission-110)
  - [État du projet (Mission 110)](#état-du-projet-mission-110)
- **Mission 109 — Training Result → Inference Handoff**
  - [Résumé (Mission 109)](#résumé-mission-109)
  - [Tests ajoutés (Mission 109)](#tests-ajoutés-mission-109)
  - [État du projet (Mission 109)](#état-du-projet-mission-109)
- **Mission 108 — Forge Inference Integration**
  - [Résumé (Mission 108)](#résumé-mission-108)
  - [Tests ajoutés (Mission 108)](#tests-ajoutés-mission-108)
  - [État du projet (Mission 108)](#état-du-projet-mission-108)
- **Mission 107 — Forge Engine Foundation**
  - [Résumé (Mission 107)](#résumé-mission-107)
  - [Tests ajoutés (Mission 107)](#tests-ajoutés-mission-107)
  - [État du projet (Mission 107)](#état-du-projet-mission-107)
- **Mission 106 — Reject base_model_source Only When No OneTrainer Form Could Ever Use It**
  - [Résumé (Mission 106)](#résumé-mission-106)
  - [Tests ajoutés (Mission 106)](#tests-ajoutés-mission-106)
  - [État du projet (Mission 106)](#état-du-projet-mission-106)
- **Mission 105 — Dirty-State Protection for TrainingPage and the Prepare/Start Config Invariant**
  - [Résumé (Mission 105)](#résumé-mission-105)
  - [Tests ajoutés (Mission 105)](#tests-ajoutés-mission-105)
  - [État du projet (Mission 105)](#état-du-projet-mission-105)
- **Mission 104 — Guard Central LoRA Library Imports Against a Blank Library Path**
  - [Résumé (Mission 104)](#résumé-mission-104)
  - [Tests ajoutés (Mission 104)](#tests-ajoutés-mission-104)
  - [État du projet (Mission 104)](#état-du-projet-mission-104)
- **Mission 103 — Training Result Import into the Central LoRA Library**
  - [Résumé (Mission 103)](#résumé-mission-103)
  - [Tests ajoutés (Mission 103)](#tests-ajoutés-mission-103)
  - [État du projet (Mission 103)](#état-du-projet-mission-103)
- **Mission 102 — Dynamic LoRA Selection from Inference**
  - [Résumé (Mission 102)](#résumé-mission-102)
  - [Tests ajoutés (Mission 102)](#tests-ajoutés-mission-102)
  - [État du projet (Mission 102)](#état-du-projet-mission-102)
- **Mission 101 — Real OneTrainer Smoke Training**
  - [Résumé (Mission 101)](#résumé-mission-101)
  - [Tests ajoutés (Mission 101)](#tests-ajoutés-mission-101)
  - [État du projet (Mission 101)](#état-du-projet-mission-101)
- **Mission 100 — Training Execution Foundation (TrainingJob, QProcess Runner, Cancel Protocol)**
  - [Résumé (Mission 100)](#résumé-mission-100)
  - [Tests ajoutés (Mission 100)](#tests-ajoutés-mission-100)
  - [État du projet (Mission 100)](#état-du-projet-mission-100)
- **Mission 099 — Qt Test Harness Lifecycle Debt Characterization**
  - [Résumé (Mission 099)](#résumé-mission-099)
  - [Tests ajoutés (Mission 099)](#tests-ajoutés-mission-099)
  - [État du projet (Mission 099)](#état-du-projet-mission-099)
- **Mission 098 — Dataset Captions (per-image, per-Dataset)**
  - [Résumé (Mission 098)](#résumé-mission-098)
  - [Tests ajoutés (Mission 098)](#tests-ajoutés-mission-098)
  - [État du projet (Mission 098)](#état-du-projet-mission-098)
- **Mission 097 — Training Contract + OneTrainer Configuration Adapter + Dataset Materialization**
  - [Résumé (Mission 097)](#résumé-mission-097)
  - [Tests ajoutés (Mission 097)](#tests-ajoutés-mission-097)
  - [État du projet (Mission 097)](#état-du-projet-mission-097)
- **Mission 096 — Real Generation Parameters for Inference**
  - [Résumé (Mission 096)](#résumé-mission-096)
  - [Tests ajoutés (Mission 096)](#tests-ajoutés-mission-096)
  - [État du projet (Mission 096)](#état-du-projet-mission-096)
- **Mission 095 — Central LoRA Library: ComfyUI Exposure via NTFS Hardlink**
  - [Résumé (Mission 095)](#résumé-mission-095)
  - [Tests ajoutés (Mission 095)](#tests-ajoutés-mission-095)
  - [État du projet (Mission 095)](#état-du-projet-mission-095)
- **Mission 094 — Fix the Mission-084 Test-Cleanup Lifetime Gap (Pending Result Guard Tests)**
  - [Résumé (Mission 094)](#résumé-mission-094)
  - [Tests ajoutés (Mission 094)](#tests-ajoutés-mission-094)
  - [État du projet (Mission 094)](#état-du-projet-mission-094)
- **Mission 093 — Central LoRA Library Thumbnail Selector**
  - [Résumé (Mission 093)](#résumé-mission-093)
  - [Tests ajoutés (Mission 093)](#tests-ajoutés-mission-093)
  - [État du projet (Mission 093)](#état-du-projet-mission-093)
- **Mission 092 — Direct Import to the Central LoRA Library (from disk)**
  - [Résumé (Mission 092)](#résumé-mission-092)
  - [Tests ajoutés (Mission 092)](#tests-ajoutés-mission-092)
  - [État du projet (Mission 092)](#état-du-projet-mission-092)
- **Mission 091 — Test Harness Reliability: Eliminate Unmocked Blocking QMessageBox in Generation-Active Tests**
  - [Résumé (Mission 091)](#résumé-mission-091)
  - [Tests ajoutés (Mission 091)](#tests-ajoutés-mission-091)
  - [État du projet (Mission 091)](#état-du-projet-mission-091)
- **Mission 090 — Central LoRA Library Entry Editing (Name and Metadata)**
  - [Résumé (Mission 090)](#résumé-mission-090)
  - [Tests ajoutés (Mission 090)](#tests-ajoutés-mission-090)
  - [État du projet (Mission 090)](#état-du-projet-mission-090)
- **Mission 089 — Central LoRA Library: Read-Only Consultation and Deletion**
  - [Résumé (Mission 089)](#résumé-mission-089)
  - [Tests ajoutés (Mission 089)](#tests-ajoutés-mission-089)
  - [État du projet (Mission 089)](#état-du-projet-mission-089)
- **Mission 088 — Add an Existing LoRA to the Central Library**
  - [Résumé (Mission 088)](#résumé-mission-088)
  - [Tests ajoutés (Mission 088)](#tests-ajoutés-mission-088)
  - [État du projet (Mission 088)](#état-du-projet-mission-088)
- **Mission 087 — Central LoRA Library Foundation (Registry + Configurable Path)**
  - [Résumé (Mission 087)](#résumé-mission-087)
  - [Tests ajoutés (Mission 087)](#tests-ajoutés-mission-087)
  - [État du projet (Mission 087)](#état-du-projet-mission-087)
- **Mission 086 — Select an Inference Reference Image from the Workspace Gallery**
  - [Résumé (Mission 086)](#résumé-mission-086)
  - [Tests ajoutés (Mission 086)](#tests-ajoutés-mission-086)
  - [État du projet (Mission 086)](#état-du-projet-mission-086)
- **Mission 085 — Refuse Close/Rename While a Generation Is Genuinely Active**
  - [Résumé (Mission 085)](#résumé-mission-085)
  - [Tests ajoutés (Mission 085)](#tests-ajoutés-mission-085)
  - [État du projet (Mission 085)](#état-du-projet-mission-085)
- **Mission 084 — Protect Pending Generation Result Against Silent Loss on Workspace Context Change**
  - [Résumé (Mission 084)](#résumé-mission-084)
  - [Tests ajoutés (Mission 084)](#tests-ajoutés-mission-084)
  - [État du projet (Mission 084)](#état-du-projet-mission-084)

---

## v0.2-mission123 — 2026-09-15

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 123 — commit fonctionnel, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 123)

Introduit la persistance de la provenance/métadonnées de génération pour toute image acceptée depuis `InferencePage`. Jusqu'ici, seul le chemin fichier de l'image survivait à l'acceptation : le prompt, le seed, le checkpoint, le sampler et tous les autres paramètres réellement utilisés pour produire l'image étaient perdus dès que l'objet `_PendingGenerationRequest` sortait de portée. Un audit préalable dédié (lecture de `image.py` et sa sérialisation, de tous les appelants réels de `WorkspaceManager.add_images()`, du cycle de vie complet de `_PendingGenerationRequest`/`_accept_pending_result()`, et de `ImagesPage`/`ImagePreviewDialog`) a confirmé qu'aucune donnée de ce type n'était conservée nulle part, et a orienté le modèle retenu.

Deux nouvelles structures Domain Qt-free, `GenerationMetadata` et `GenerationReference` (`src/domain/generation_metadata.py`), attachées à `Image.generation_metadata: Optional[GenerationMetadata] = None` — `None` signifie explicitement « aucune provenance de génération » (image importée manuellement, ou acceptée avant cette mission), jamais une valeur inventée. `GenerationReference(path, role)` reproduit délibérément, sans l'importer, la forme du `Reference` NamedTuple de `src/managers/generation_manager.py` (une classe Manager), pour respecter la Dependency Rule (Domain ne dépend jamais d'un Manager) — la conversion a lieu côté Presentation, dans `InferencePage`. `references` utilise `field(default_factory=list)` (jamais un défaut mutable partagé), et `GenerationReference.path` est documenté comme une provenance strictement historique — jamais une base de Replay, jamais un `image_id` inventé.

Le point le plus sensible architecturalement était le moment exact de capture : la metadata est construite **une seule fois**, de façon eager, dans `_launch_generation_worker(request)` — au moment où la génération est réellement lancée, à partir de l'instantané déjà immuable `_PendingGenerationRequest` — et jamais reconstruite ni relue depuis l'état courant des widgets au moment de l'Accept. Elle est conservée sous un nouvel attribut nommé explicitement `_pending_result_metadata`, distinct de `_pending_generation_request` (une étape antérieure et non liée : une requête encore en attente du démarrage de ComfyUI Local). Un tableau de nettoyage complet couvre chaque chemin réel du cycle de vie : Accept réussi (persistée puis nettoyée), Reject (nettoyée sans persistance), échec de génération (nettoyée), changement/invalidation de Workspace et fermeture de l'application (nettoyée) — et, cas notable, un échec d'Accept (ex. erreur disque) préserve délibérément la metadata intacte pour permettre un retry, exactement comme le contrat déjà établi par Mission 067 pour `_pending_path`.

`WorkspaceManager.add_images()` gagne un unique paramètre optionnel `generation_metadata_by_path` (dict), avec une clé strictement alignée sur celle déjà utilisée par `renames` — le chemin source avant renommage/copie, jamais le chemin final. Omis par tout appelant (ce que fait systématiquement `ImagesPage.import_images()`), il laisse le comportement d'import manuel byte-à-byte inchangé ; `DatasetManager.add_images()`, une méthode entièrement séparée opérant sur un autre pool (`Dataset.images`), n'a pas été touché. La désérialisation reste strictement défensive (clé absente, valeur non-dict, liste non-list, éléments non-dict, champs optionnels restant optionnels), sans jamais devenir un système de validation générique de `project.json`.

Décision explicite de report côté UI : `ImagePreviewDialog` porte, depuis Mission 015, la contrainte documentée d'être un visualiseur passif recevant uniquement un `file_path` — jamais un objet Domain, un Manager ou une Page. L'ajout d'un affichage détaillé de la metadata y créerait une incohérence entre ses deux points d'usage (`ImagesPage`, `InferencePage`) ou violerait cette contrainte ; cet affichage est donc explicitement différé à une mission future, sans aucune modification de `ImagePreviewDialog`.

### Tests ajoutés (Mission 123)

**18 tests nets nouveaux** (2465 → 2483) répartis sur `test_image_roundtrip.py` (5 tests — round-trip `GenerationReference`/`GenerationMetadata`, désérialisation défensive, absence de partage d'état mutable entre instances), `test_workspace_roundtrip.py` (4 tests — non-régression sans `generation_metadata_by_path`, attribution correcte par chemin source, indépendance entre plusieurs images d'un même appel, clé alignée sur le chemin source et non le chemin effectif) et `test_inference_page.py` (9 tests — construction avant l'arrivée du résultat, persistance correspondant exactement à l'instantané de lancement, nettoyage sur Reject/échec de génération, préservation sur échec d'Accept pour retry, non-contamination par une mutation de widget après Generate, indépendance entre deux générations acceptées, survie après rechargement du Workspace, nettoyage sur incompatibilité de Workspace à l'arrivée du résultat).

`test_image_roundtrip.py` seul : **15/15**. `test_workspace_roundtrip.py` seul : **101/101**. `test_inference_page.py` seul : **230/230**. Les trois fichiers combinés : **346/346**. Suite complète **2483/2483**, 0 failure, 0 error, `git diff --check` propre. Un échec isolé de `test_comfyui_lifecycle_manager.py::test_process_exits_before_readiness_is_start_failed`, observé lors d'un des runs de la suite complète, a été identifié comme un flake préexistant et non lié à Mission 123 (fichier jamais touché par cette mission) — confirmé par un rerun isolé immédiatement vert, puis par une nouvelle exécution complète propre.

Validé par un smoke réel de bout en bout contre une instance ComfyUI réelle, auto-démarrée par le mécanisme de production existant (`ComfyUILifecycleManager`, déjà validé par Mission 115) au sein d'une vraie `MainWindow()` : une première génération avec un prompt/seed distinctifs, dont les widgets (`prompt`, `seed_edit`) sont délibérément mutés après que le résultat soit en attente mais avant que l'Accept ne soit cliqué — une relecture directe de `project.json` sur disque confirme que la metadata persistée correspond exactement à l'instantané original de lancement, jamais à la mutation post-génération. Une seconde génération, indépendante, avec des paramètres distincts, confirme l'absence de toute contamination croisée entre les deux images acceptées. Enfin, le Workspace est fermé puis rouvert via un `WorkspaceManager` entièrement neuf, confirmant que la metadata des deux images survit intacte à un rechargement réel. Aucun script de smoke conservé dans le dépôt. Voir `docs/missions/MISSION_123.md` pour le détail complet.

### État du projet (Mission 123)

**2483/2483** tests automatisés verts (2465 avant Mission 123 + 18 nets nouveaux), aucune régression. Commit fonctionnel `4745b1ba826b91421663e1b00d518f3fae7674c4` (`Add generation provenance metadata persistence`), tag `v0.2-mission123`, GitHub Release publiée.

---

## v0.2-mission122 — 2026-09-14

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 122 — commit fonctionnel, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 122)

Introduit une configuration Optimizer structurée et extensible pour `Training`, en s'appuyant directement sur la fondation posée par Mission 120 et étendue par Mission 121. Un micro-audit dédié préalable (lecture seule de `Optimizer.py`/`create.py::create_optimizer()`/`TrainConfig.py`/`BaseConfig.py`, presets JSON réels, venv réel) a confirmé que `Optimizer` compte 43 valeurs réelles, que `build_training_config()` n'envoyait jusqu'ici jamais de clé `optimizer` (défaut réel `ADAMW` implicite), que `TrainConfig.optimizer` est un objet nichée (jamais un enum plat), que `optimizer_defaults` reste exclusivement lu/écrit par l'UI OneTrainer elle-même (jamais par le runtime réel), et que seules `ADAM`/`ADAMW`/`SGD` utilisent directement `torch.optim` sans aucune dépendance tierce ni variante 8-bit/quantifiée.

Une vérification architecturale dédiée, déclenchée par une objection explicite de l'architecte sur le brouillon initial, a établi qu'une réservation en bloc de la racine `"optimizer"` dans `_STRUCTURED_CONFIG_KEYS`, sans échappatoire locale, aurait constitué une régression de capacité — bloquant l'expression des ~99 sous-paramètres optimizer réels non encore typés, contrairement au principe déjà établi par Mission 120 de typage progressif avec échappatoire préservée. La mission introduit donc une nouvelle structure Domain dédiée, `OneTrainerOptimizerSettings` (`src/domain/onetrainer_optimizer_settings.py`) : `optimizer: str = ""` (discriminant, sentinelle `""` = non configuré, jamais une des 43 valeurs réelles) et `extra_overrides: dict` — une **seconde** échappatoire, scopée exclusivement à l'objet optimizer, distincte de l'échappatoire globale `OneTrainerSettings.extra_overrides`. Cette structure est nichée dans `OneTrainerSettings.optimizer_settings` ; le discriminant n'est délibérément **jamais** un champ plat direct de `OneTrainerSettings`, précisément pour que son échappatoire reste un objet distinct et scopé.

`build_training_config()` gagne `optimizer: str = ""` et `optimizer_extra_overrides: Optional[dict] = None`, et construit conditionnellement l'objet nichée réel d'OneTrainer (`{"optimizer": {"optimizer": "<ENUM>", ...}}`) — aucune clé `"optimizer"` n'est ajoutée si rien n'est configuré, comportement historique OneTrainer strictement inchangé (`ADAMW` reste implicite). La politique de collision opère désormais à deux niveaux distincts : `_STRUCTURED_CONFIG_KEYS` (niveau global, déjà en place) gagne la clé racine `"optimizer"`, empêchant l'échappatoire globale de recréer une seconde source de vérité pour le discriminant structuré ; une nouvelle constante dédiée `_OPTIMIZER_STRUCTURED_SUBKEYS = frozenset({"optimizer"})` (niveau optimizer) protège uniquement le sous-champ `"optimizer"` à l'intérieur de l'échappatoire scopée — tout autre sous-paramètre optimizer réel (`weight_decay`, `beta1`, etc.) y reste librement exprimable, sans interruption de service pour l'architecte.

Un `project.json` hérité portant déjà `OneTrainerSettings.extra_overrides["optimizer"]` (légal et fonctionnel avant cette mission, puisque la racine n'était pas encore réservée) est désormais rejeté explicitement, avec un message actionnable dédié nommant la clé devenue réservée et l'emplacement de repli — jamais une migration automatique silencieuse, conformément à la convention permanente du projet.

`TrainingManager.update()` gagne `optimizer: Optional[str] = None`, muté in-place sur `onetrainer_settings.optimizer_settings.optimizer` — jamais un remplacement du conteneur, qui perdrait son `extra_overrides` scopé. `TrainingPage` gagne une nouvelle sous-section `Optimizer` dans `Advanced settings` : un combo `(non configuré)`/`ADAM`/`ADAMW`/`SGD` — les trois seules valeurs réelles de l'enum OneTrainer backées directement par `torch.optim`, sans dépendance tierce ni variante 8-bit, **jamais présentées comme la liste complète** des 43 valeurs réelles qu'`OneTrainerOptimizerSettings.optimizer` reste capable de représenter (même tolérance défensive que `learning_rate_scheduler`/les dtypes de Mission 121) — même contrat dirty-state/scroll que l'existant. Aucun changement de comportement pour un Training existant qui ne configure aucune donnée optimizer, prouvé par comparaison byte-à-byte explicite.

### Tests ajoutés (Mission 122)

**16 tests nets nouveaux** (2449 → 2465) répartis sur `test_onetrainer_config.py` (11 tests — traduction de `ADAM`/`ADAMW`/`SGD`, fusion avec `optimizer_extra_overrides`, collision locale sur le sous-champ `optimizer`, rejet de la clé racine héritée avec message actionnable, énumération exacte de `_OPTIMIZER_STRUCTURED_SUBKEYS`, non-régression byte-à-byte du comportement Mission 121) et `test_training_roundtrip.py` (5 tests — round-trip `OneTrainerOptimizerSettings`, rétrocompatibilité, dirty-state UI sur `optimizer_combo`, immutabilité du snapshot `TrainingJob`, scroll toujours fonctionnel avec la section Optimizer).

`test_onetrainer_config.py` seul : **54/54**. `test_training_roundtrip.py` seul : **227/227**. Les deux fichiers exécutés ensemble : **281/281**. Suite complète **2465/2465**, 0 failure, 0 error, `git diff --check` propre.

Validé par un smoke réel SD1.5 de bout en bout contre l'installation OneTrainer réelle, en réutilisant le scénario déjà validé par les Missions 097-121, sans aucune modification d'environnement : `optimizer="SGD"` explicitement configuré — première valeur non-`ADAMW` jamais réellement exécutée par ce projet —, tracé jusqu'au snapshot `TrainingJob` immuable (`{"optimizer": {"optimizer": "SGD"}}` identique à la configuration préparée), process OneTrainer réel démarré, checkpoint SD1.5 réellement chargé, un vrai step GPU exécuté (`loss=0.0852`, observé mais non requis comme critère de validation — aucune comparaison avec `ADAMW` n'était nécessaire), run terminé `succeeded` en 54,6 s, `lora.safetensors` réel produit (78 489 976 octets). Aucun log runtime de cette exécution ne nomme explicitement l'optimizer — preuve retenue : `create.py::create_optimizer()` utilise un `match`/`case` exhaustif sans branche de repli générique, et les signatures de construction `SGD`/`AdamW` sont incompatibles entre elles, si bien qu'un vrai step GPU réussi n'est possible que si la branche `SGD` a été correctement atteinte et instanciée. Aucun script de smoke conservé dans le dépôt. Voir `docs/missions/MISSION_122.md` pour le détail complet.

### État du projet (Mission 122)

**2465/2465** tests automatisés verts (2449 avant Mission 122 + 16 nets nouveaux), aucune régression. Commit fonctionnel `b98a55de7673ae76c6664d6880650b87c05e4805` (`Add structured OneTrainer optimizer settings`), tag `v0.2-mission122`, GitHub Release publiée.

---

## v0.2-mission121 — 2026-09-14

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 121 — commit fonctionnel, tag, Release et correctif post-release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 121)

Introduit la première vraie section « Advanced settings » de `TrainingPage`, sous-section `Precision / Memory`, en s'appuyant directement sur la fondation posée par Mission 120. Un micro-audit dédié préalable (lecture seule du contrat dtype/optimizer/mémoire réel d'OneTrainer) a confirmé que tous les `weight_dtype` par composant retombaient jusqu'ici sur le défaut réel `FLOAT_32` d'OneTrainer, alors que les presets LoRA officiels SD1.5/SDXL/Flux configurent explicitement `FLOAT_16` pour la plupart des composants — sans jamais toucher à `optimizer` ni aux mécanismes mémoire adjacents (non câblés pour SD1.5/SDXL dans les modelLoaders réels), explicitement différés à une mission ultérieure.

`OneTrainerSettings` gagne 6 nouveaux champs `str = ""` (`train_dtype`, `unet_weight_dtype`, `transformer_weight_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype`, sentinelle `""` = non configuré). `unet_weight_dtype`/`transformer_weight_dtype` restent deux champs strictement distincts en persistance — jamais fusionnés — même si l'UI les présente comme un seul concept ergonomique « modèle principal » avec libellé dynamique (« UNet » ou « Transformer ») selon l'architecture sélectionnée.

`build_training_config()` valide désormais explicitement, au niveau Domain/translation et non plus seulement via le masquage UI, la compatibilité champ/architecture via une nouvelle constante `_DTYPE_FIELDS_BY_ARCHITECTURE` (SD1.5/SDXL/FLUX_DEV_1, table exacte des composants réels par architecture) — toute incompatibilité (ex. `transformer_weight_dtype` configuré pour `SD15`) lève `OneTrainerConfigError` nommant explicitement l'architecture et le ou les champs fautifs, que la valeur incompatible provienne de l'UI ou d'un `project.json` édité à la main. Chaque champ configuré est ensuite traduit vers la structure nichée réelle d'OneTrainer (`{"unet": {"weight_dtype": ...}}`, etc.), confirmée compatible avec le mécanisme de fusion partielle réel d'OneTrainer. `_STRUCTURED_CONFIG_KEYS` protège désormais aussi les 6 nouvelles clés (`train_dtype`/`unet`/`transformer`/`text_encoder`/`text_encoder_2`/`vae`), réservées inconditionnellement dans `extra_overrides`, que le champ Toolkit correspondant soit configuré ou non.

Le vocabulaire proposé par l'UI reste volontairement restreint à 4 dtypes non quantifiés (`FLOAT_16`/`FLOAT_32`/`BFLOAT_16`/`TFLOAT_32`), identiques pour les trois architectures y compris Flux : un preset officiel Flux utilisant une valeur quantifiée (`NFLOAT_4`/`FLOAT_8`/`INT_W8A8`) n'est jamais retenu comme preuve de compatibilité avec la Quadro P4000/Pascal/sm_61, faute de toute vérification de kernel quantifié effectuée sur ce matériel — distinction explicite entre vocabulaire représentable, compatibilité architecture, vocabulaire proposé par l'UI, et compatibilité matérielle réellement démontrée.

La nouvelle section est repliable via un `QToolButton` (titre-bascule) associé à un `QWidget` conteneur dont seule la propriété `visible` change — délibérément pas un `QGroupBox` cochable, dont la sémantique Qt conventionnelle (« coché = ce réglage s'applique ») aurait créé une ambiguïté réelle avec un simple repli visuel. Plier/déplier la section ne modifie jamais aucune valeur ni ne déclenche le dirty-state à lui seul. Un changement d'architecture réinitialise explicitement à `""` tout champ dtype devenu incompatible avec la nouvelle architecture, sans jamais le conserver silencieusement hors de vue. Aucun changement de comportement pour un Training existant qui ne configure aucun de ces nouveaux champs — prouvé par comparaison byte-à-byte explicite avec le comportement de Mission 120.

### Tests ajoutés (Mission 121)

**31 tests nets nouveaux** (2413 → 2444) répartis sur `test_onetrainer_config.py` (18 tests — traduction de chaque champ, validation par architecture dans les deux sens, collisions `extra_overrides` sur les 6 nouvelles clés, non-régression byte-à-byte du comportement Mission 120) et `test_training_roundtrip.py` (13 tests — round-trip `OneTrainerSettings`, rétrocompatibilité, dirty-state UI, visibilité/libellés par architecture, reset explicite sur changement d'architecture, immutabilité du snapshot `TrainingJob`).

Suite complète **2444/2444**, `git diff --check` propre. Validé par un smoke réel SD1.5 de bout en bout contre l'installation OneTrainer réelle, en réutilisant le scénario déjà validé par les Missions 097-101/120, sans aucune modification d'environnement : `train_dtype="FLOAT_16"`/`unet_weight_dtype="FLOAT_16"`/`text_encoder_weight_dtype="FLOAT_16"`/`vae_weight_dtype="FLOAT_32"` (valeurs reprises du preset LoRA SD1.5 officiel, jamais présentées comme un nouveau défaut Toolkit) réellement configurés et tracés jusqu'au snapshot `TrainingJob` immuable, process OneTrainer réel démarré, checkpoint réellement chargé, un vrai step GPU exécuté (`loss=0.0852`), run terminé `succeeded` en 102,1 s, `lora.safetensors` réel produit (78 489 976 octets). Aucun script de smoke conservé dans le dépôt. Voir `docs/missions/MISSION_121.md` pour le détail complet.

### Correctif post-release (Mission 121)

Un smoke visuel manuel réalisé par l'architecte après la publication de la GitHub Release de Mission 121 a révélé une régression UX directement causée par l'ajout de la section « Advanced settings » : sur la résolution/fenêtre réelle utilisée, la hauteur totale de `TrainingPage` dépassait désormais celle d'une fenêtre normale, rendant la zone « Résultats des entraînements » et les boutons d'action sous elle physiquement inatteignables — même symptôme déjà rencontré et déjà résolu pour `SettingsPage` (Mission 115).

Corrigé par le même pattern minimal (`QScrollArea` avec `setWidgetResizable(True)` enveloppant le contenu existant, inchangé, de `TrainingPage`) — aucune section réorganisée, aucune logique de sauvegarde modifiée, aucun changement de comportement `Training`. **5 tests nets nouveaux** (2444 → 2449), dont une preuve réelle de dépassement de viewport sur fenêtre réduite avec bas de page atteignable par scroll. Commit correctif séparé `c5c6850dacb058b387afc2d4915ca12066da3362` (`Fix Training page vertical scrolling`), sur `main` après le commit fonctionnel — **jamais rattaché au tag `v0.2-mission121` ni à la Release déjà publiée**, qui restent tous deux attachés exclusivement au commit fonctionnel original. Voir `docs/missions/MISSION_121.md` section 12 pour le détail complet.

### État du projet (Mission 121)

**2449/2449** tests automatisés verts (2413 avant Mission 121 + 31 nets nouveaux + 5 nets nouveaux du correctif post-release), aucune régression. Commit fonctionnel `d07c063b73ca6d7b6d4da7453855579d59578c60` (`Add advanced OneTrainer precision settings`), tag `v0.2-mission121`, GitHub Release publiée. Correctif post-release `c5c6850dacb058b387afc2d4915ca12066da3362` (`Fix Training page vertical scrolling`), non tagué.

---

## v0.2-mission120 — 2026-09-14

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 120 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 120)

Pose la fondation architecturale permettant à AI Studio Toolkit d'exposer progressivement l'intégralité des réglages OneTrainer pertinents, sans jamais obliger l'architecte à ouvrir l'interface OneTrainer pour un réglage avancé. Un micro-audit préalable a cartographié le schéma OneTrainer réellement installé (`TrainConfig` ~150 champs, `ConceptConfig`, 26 `ModelType`, ~40 `Optimizer`, 52 presets officiels) et confirmé que `Training` (7 champs) et `build_training_config()` (8 clés traduites, le reste retombant sur les défauts OneTrainer) laissaient l'essentiel de cette surface hors d'atteinte de Toolkit.

`Training` gagne deux champs génériques réels (`batch_size: int = 0`, `gradient_accumulation_steps: int = 0`, sentinelle `0` — jamais une valeur légitime pour ces champs) et `onetrainer_settings: OneTrainerSettings` — une nouvelle structure Domain dédiée (`src/domain/onetrainer_settings.py`, Qt-free, `to_dict()`/`from_dict()` symétriques) portant `learning_rate_scheduler: str = ""` (sentinelle `""`, vocabulaire restreint `CONSTANT`/`LINEAR`/`COSINE`/`COSINE_WITH_RESTARTS`/`COSINE_WITH_HARD_RESTARTS`/`REX`/`ADAFACTOR`, `CUSTOM` explicitement exclu) et `extra_overrides: dict` (échappatoire secondaire pour tout réglage OneTrainer non encore modélisé). `OneTrainerSettings` est délibérément une structure typée dédiée à OneTrainer — seul provider Training réellement intégré à ce jour — plutôt qu'une abstraction `TrainingProviderConfig` multi-provider anticipée sans second consommateur réel ; refactorable le jour où un second provider deviendrait un besoin réel, jamais anticipée. `seed` a été explicitement exclu du périmètre après vérification qu'il appartient à `ConceptConfig` (pas `TrainConfig`) et que `0` y est une graine légitime, disqualifiant toute sentinelle — préférer un ensemble réduit à 3 champs réellement bien placés plutôt qu'un quatrième champ forcé au mauvais niveau.

`src/engines/onetrainer_config.py::build_training_config()` fusionne ces champs selon une politique à quatre niveaux explicite et jamais implicite : défauts OneTrainer historiques → champs structurés (générique puis OneTrainer) uniquement quand non-sentinelles → `extra_overrides` validés → chemins internes protégés (ce dernier niveau, déjà correct dans `TrainingManager.create_job()`, reste inchangé). Deux constantes centralisées et testées (`_PROTECTED_CONFIG_KEYS`, `_STRUCTURED_CONFIG_KEYS`) font lever `OneTrainerConfigError` sur toute clé d'`extra_overrides` qui tenterait de redéfinir un chemin interne ou de dupliquer un champ déjà structuré — jamais un écrasement silencieux dans un sens ou l'autre. `TrainingManager.prepare_onetrainer_config()`/`update()` propagent les nouveaux champs, avec mutation in-place de l'objet `OneTrainerSettings` existant (jamais un remplacement qui perdrait un `extra_overrides` déjà présent) ; `create_job()` reste inchangé. `TrainingPage` gagne 3 widgets minimaux (`batch_size_spinbox`/`gradient_accumulation_steps_spinbox`/`learning_rate_scheduler_combo`) dans le formulaire existant, avec exactement le même contrat dirty-state que les 8 champs préexistants — aucune UI Advanced, aucun réagencement visuel.

Aucun changement de comportement pour tout Training existant ne configurant pas ces nouveaux champs : la sentinelle « non configuré » reproduit exactement le silence actuel, laissant OneTrainer appliquer son propre défaut historique — prouvé par une comparaison byte-à-byte explicite du dict produit, pas seulement par absence d'erreur.

### Tests ajoutés (Mission 120)

**14 tests nets nouveaux** (2399 → 2413) répartis sur `test_onetrainer_config.py` (11 tests — traduction des nouveaux champs, non-régression byte-à-byte du dict historique, protection des clés internes et détection de collision énumérées exhaustivement) et `test_training_roundtrip.py` (3 tests — round-trip `Training`/`OneTrainerSettings`, rétrocompatibilité d'un `project.json` pré-Mission 120, immutabilité du snapshot `TrainingJob`).

Suite complète **2413/2413**, `git diff --check` propre. Validé par un smoke réel SD1.5 de bout en bout contre l'installation OneTrainer réelle, en réutilisant le scénario déjà validé par les Missions 097-101 (checkpoint `v1-5-pruned-emaonly-fp16.safetensors`, 1 image, résolution 512, 1 epoch), sans aucune modification d'environnement (Python/Torch/CUDA/OneTrainer/drivers inchangés) : `batch_size=1`/`gradient_accumulation_steps=1`/`learning_rate_scheduler=CONSTANT` réellement configurés et tracés jusqu'au snapshot `TrainingJob` immuable, process OneTrainer réel démarré, checkpoint réellement chargé, un vrai step GPU exécuté (`loss=0.0852`), run terminé `succeeded` en 140,5 s, `lora.safetensors` réel produit (78 489 976 octets). Aucun script de smoke conservé dans le dépôt. Voir `docs/missions/MISSION_120.md` pour le détail complet.

### État du projet (Mission 120)

**2413/2413** tests automatisés verts (2399 avant Mission 120 + 14 nets nouveaux), aucune régression. Commit fonctionnel `773304f3b107c55bb10e14bcde122be47fe8e2b4` (`Add advanced OneTrainer training configuration foundation`), tag `v0.2-mission120`, GitHub Release publiée.

---

## v0.2-mission119 — 2026-09-14

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 119 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 119)

Ferme, pour Forge Local, le blocage Stop documenté depuis Mission 108/114 : l'entrée réelle de Forge (`run.bat`) génère un `cmd.exe` qui n'exécute lui-même `python.exe launch.py` que comme petit-enfant, jamais atteint par une terminaison Windows standard appliquée au seul process direct — Forge restait donc supposé démarré et arrêté manuellement par l'architecte. AI Studio Toolkit gagne désormais un lifecycle Start/Stop/ownership/readiness complet pour Forge Local, piloté depuis `SettingsPage`, mirroir du modèle `ComfyUILifecycleManager` (Mission 114) là où il s'applique tel quel, mais divergent où le mode de lancement réel de Forge l'imposait.

Un audit empirique préalable du lancement réel a établi que `QProcess` ne peut pas exécuter directement un `.bat` — lancement via `cmd.exe ["/c", run_bat_path]` — et que `call` à l'intérieur d'un script batch n'ouvre jamais de nouveau process : `run.bat → environment.bat → webui-user.bat → webui.bat` s'exécutent tous dans le même `cmd.exe`, seul l'appel final `%PYTHON% launch.py` engendrant le vrai process enfant (`python.exe`). `NoDefaultCurrentDirectoryInExePath=1` (actif sur la machine de test) cassait les `call` internes de `run.bat` — corrigé en prépendant `forge_root`/`forge_root\webui` au `PATH` du process enfant uniquement (`src/engines/forge_launch.py::resolve_forge_launch()`, resolver Qt-free, hôte toujours restreint à `127.0.0.1`/`localhost`, ne construit jamais les arguments CLI propres de Forge — repris tels quels depuis `webui-user.bat`, contrat Mission 107 inchangé).

`src/ui/forge_lifecycle_manager.py::ForgeLifecycleManager` reprend les six états de `ComfyUILifecycleManager` (`STOPPED`/`EXTERNAL_ACTIVE`/`STARTING`/`RUNNING_OWNED`/`STOPPING`/`START_FAILED`) et termine l'arbre possédé via `taskkill /PID <pid> /T /F`, vérifié empiriquement scopé strictement à cet arbre — `QProcess.terminate()`/`.kill()` ne signalant jamais que le seul process ciblé sur Windows. Quatre rounds de revue de sécurité ont durci le contrat avant validation : (1) `taskkill` est suivi par un vrai `QProcess` (jamais fire-and-forget), un Stop n'étant rapporté `STOPPED` qu'après un rendez-vous à deux signaux confirmés — fin du `cmd.exe` possédé et issue réelle de `taskkill`, empiriquement observés dans cet ordre et non l'inverse ; (2) un Stop non confirmé ne referme jamais silencieusement Toolkit — une fermeture différée bascule sur une erreur explicite plutôt que de reprendre en silence ; (3) un latch interne non persisté (`_stop_unconfirmed`) bloque tout nouveau Start tant qu'un backend externe confirmé ou un Stop confirmé ne l'a pas levé, sans introduire de septième état ; (4) le cleanup d'un Start ayant échoué au readiness-timeout partage exactement le même rendez-vous de confirmation que le Stop explicite, plutôt que de dupliquer la logique. `MainWindow.closeEvent()` gagne le même guard que ComfyUI ; `SettingsPage` gagne les boutons Démarrer/Arrêter Forge + un label de statut lifecycle. Aucune modification de `ForgeEngine`, `InferencePage`, `GenerationManager` (aucun auto-start Forge câblé, hors périmètre explicite), aucune abstraction ComfyUI/Fooocus/cloud.

### Tests ajoutés (Mission 119)

**72 tests nets nouveaux** (2327 → 2399) répartis sur `test_forge_launch.py` (10 tests), `test_forge_lifecycle_manager.py` (48 tests — process réel factice `cmd.exe → python.exe`, garde/latch/rendez-vous fabriqués, confirmation de Stop avec `taskkill` réellement rendu indisponible via un binaire inexistant, cleanup readiness-timeout suivant le même chemin de confirmation), `test_settings_page.py` (7 tests) et `test_main_window_close_event.py` (7 tests).

Suite complète **2399/2399**, `git diff --check` propre. Trois scénarios de smoke réel PASS contre l'installation réelle `J:\Programmes\WebUI Forge CU121` : **Scénario A** (Start Toolkit-owned, arbre réel confirmé, ~50 s de démarrage à froid, `check_connection()` réel réussi), **Scénario B** (Stop confirmé, arbre réel entièrement terminé, absence vérifiée indépendamment via `tasklist`/`netstat`), **Scénario C** (backend externe détecté `EXTERNAL_ACTIVE`, zéro ownership, process externe laissé intact, non affecté par `stop()`) — environnement restauré à son état initial après le Scénario C. Voir `docs/missions/MISSION_119.md` pour le détail complet.

### État du projet (Mission 119)

**2399/2399** tests automatisés verts (2327 avant Mission 119 + 72 nets nouveaux), aucune régression. Commit fonctionnel `745dbf57dd7b5b3fe54ef1b481eb3b7c71e42ac1` (`Add Forge Local lifecycle management (Start/Stop/ownership/readiness)`), tag `v0.2-mission119`, GitHub Release publiée.

---

## v0.2-mission118 — 2026-09-12

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 118 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 118)

`SettingsPage` avait accumulé, mission après mission (M025 à M117), un unique `QFormLayout` linéaire — un mini-correctif (Mission 115) avait déjà dû l'envelopper dans un `QScrollArea` pour garder `application_save_button` atteignable. Cette mission remplace ce formulaire plat par une navigation par catégories : un `QListWidget` (`settings_nav_list`) pilote un `QStackedWidget` (`settings_stack`), réutilisant l'idiome Sidebar/stack déjà établi pour `MainWindow`. Cinq pages : **General** (Workspace + Bibliothèque LoRA centrale), **Training → OneTrainer**, **Local Image Generation → ComfyUI Local / Stable Diffusion Forge**, **AI Assistants** (Ollama). La structure sépare explicitement les moteurs **locaux** d'une future catégorie **cloud**, et laisse la place à de futurs domaines **Video Generation**/**Audio Generation** — aucun n'est peuplé aujourd'hui, aucune page vide n'a été créée pour eux. Les deux boutons Save existants restent globaux, hors du `QStackedWidget`, comportement strictement inchangé. Aucun widget renommé, aucune méthode publique modifiée, aucun changement Domain/Manager/Storage/EventBus/providers. Voir `docs/missions/MISSION_118.md` pour le détail complet.

### Tests ajoutés (Mission 118)

**9 tests nets nouveaux** (`SettingsPageNavigationTest`) couvrant la sélection par défaut, le contenu par catégorie, les lignes d'en-tête non sélectionnables, et la préservation d'une saisie non sauvegardée lors d'un changement de catégorie. Les 74 tests préexistants de `test_settings_page.py` n'ont nécessité **aucune** modification. `test_settings_page.py` complet : **83/83**. Suites dépendantes (`test_main_window_close_event`, `test_main_window_ollama_settings`, `test_application_settings_roundtrip`, `test_training_roundtrip`, `test_settings_roundtrip`) : **304/304**. Suite complète **2327/2327**, `git diff --check` propre.

### État du projet (Mission 118)

**2327/2327** tests automatisés verts (2318 avant Mission 118 + 9 nets nouveaux), aucune régression. Commit fonctionnel `6edd411f9c1f5bc0a310bd0735fb89bf41b6edff` (`Reorganize SettingsPage into a category-based navigation`), tag `v0.2-mission118`, GitHub Release publiée.

## v0.2-mission117 — 2026-09-12

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 117 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 117)

Ferme le second gap UX identifié immédiatement après la clôture de Mission 116 : l'attente de démarrage de ComfyUI Local, désormais visible grâce au statut de Mission 116, restait purement subie — le seul moyen d'en sortir avant la fin du budget de readiness (~120 secondes) était un signal lifecycle externe (échec de démarrage, ou Stop déclenché ailleurs, typiquement depuis `SettingsPage`). Si ComfyUI Local était réellement bloqué, `InferencePage` n'offrait aucun recours.

`InferencePage` gagne un nouveau `QPushButton` transitoire (`cancel_comfyui_start_button`, « Annuler »), placé juste après `comfyui_status_label`, invisible au repos. Il devient visible exactement quand une génération est mise en attente sur le Start ComfyUI (`STOPPED`/`START_FAILED`/`STARTING`), jamais sur les branches de lancement immédiat (`RUNNING_OWNED`/`EXTERNAL_ACTIVE`) ni sur le refus immédiat (`STOPPING`). Un clic invalide uniquement `self._pending_generation_request`, efface le statut, réactive `generate_button` et les contrôles de génération — **sans jamais appeler `comfyui_lifecycle_manager.stop()`** : le Start applicatif que cette page a elle-même déclenché est laissé en vie, exactement comme `reset_for_workspace_change()` l'établissait déjà pour un changement de Workspace (Mission 115), l'ownership du Start restant indépendant de l'intérêt d'une seule page pour son résultat. Si ce même Start atteint ensuite `RUNNING_OWNED`/`EXTERNAL_ACTIVE` ou `START_FAILED` après l'annulation, rien ne se produit — aucune génération, aucun message parasite — grâce à la garde d'identité que `_on_comfyui_lifecycle_state_changed()` possédait déjà depuis Mission 115. Forge reste entièrement inaffecté.

Aucun écart architectural rencontré : `ComfyUILifecycleManager`, `GenerationManager`, `SettingsPage` et `ForgeEngine` restent strictement inchangés.

### Tests ajoutés (Mission 117)

**8 tests nets nouveaux** (2310 → 2318) dans `InferencePageComfyUILifecycleHandoffTest`/`InferencePageComfyUILifecycleRealStartTest` : annulation après un nouveau Start, annulation en s'attachant à un Start déjà `STARTING`, clic d'annulation sans pending existant (no-op sûr), arrivée tardive de `RUNNING_OWNED`/`START_FAILED` après annulation (sans effet), sécurité d'un changement de Workspace/`shutdown()` après annulation, et un test réel réutilisant le harnais de process factice de Mission 114 prouvant que le vrai Start reste en vie et ne génère jamais après annulation. Assertions de visibilité (`isVisibleTo`, précédent déjà établi par `test_prompt_assistant_dialog.py`) ajoutées à tous les tests M115/M116 existants concernés.

Suite complète **2318/2318**, `git diff --check` propre, 103/103 tests `MainWindow` concernés (aucune boîte de dialogue réelle inattendue). Voir `docs/missions/MISSION_117.md` pour le détail complet.

### État du projet (Mission 117)

**2318/2318** tests automatisés verts (2310 avant Mission 117 + 8 nets nouveaux), aucune régression. Commit fonctionnel `76fc1435ac40cd55e91acb519f8647099b56904d` (`Add explicit cancel for pending ComfyUI auto-start in InferencePage`), tag `v0.2-mission117`, GitHub Release publiée. Voir `docs/missions/MISSION_117.md` pour le détail complet.

---

## v0.2-mission116 — 2026-09-12

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 116 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 116)

Ferme le gap UX identifié immédiatement après la clôture de Mission 115 : pendant l'attente de démarrage de ComfyUI Local déclenchée automatiquement par un clic sur Generate (jusqu'à ~120 secondes, budget de readiness fixé par Mission 114), `generate_button` se contentait de se désactiver sans aucune indication visible — indiscernable d'un blocage pour l'utilisateur.

`InferencePage` gagne un nouveau `QLabel` transitoire (`comfyui_status_label`), texte vide au repos. Au clic, si un nouveau démarrage ComfyUI est engagé (`STOPPED`/`START_FAILED`), il affiche « Démarrage de ComfyUI en cours… » ; s'il s'agit d'un rattachement à un démarrage déjà en vol (`STARTING`, aucun second appel `start()`), il affiche « Un démarrage de ComfyUI est déjà en cours… ». Aucun statut n'est jamais écrit sur les branches de lancement immédiat (`RUNNING_OWNED`/`EXTERNAL_ACTIVE`) ni sur le refus immédiat (`STOPPING`). Le statut est effacé au même point de passage unique que les deux chemins de lancement (immédiat et pending résolu) convergent déjà, garantissant sa disparition exactement au démarrage réel de la génération ; il est également effacé à chaque abandon du pending (échec de démarrage, Stop déclenché ailleurs), au changement de Workspace/contexte, et à la fermeture de l'application — toujours au même moment que le mécanisme d'invalidation ou d'erreur déjà existant de Mission 115, jamais un second canal d'erreur concurrent aux `QMessageBox` déjà en place. Forge reste entièrement inaffecté.

Aucun écart architectural rencontré : `ComfyUILifecycleManager`, `GenerationManager`, `SettingsPage` et `ForgeEngine` restent strictement inchangés.

### Tests ajoutés (Mission 116)

**1 test net nouveau** (2309 → 2310) : `test_shutdown_clears_pending_status_label`. Assertions de statut ajoutées à 10 tests M115 existants dans `InferencePageComfyUILifecycleHandoffTest` (visibilité/texte pour `STOPPED`/`START_FAILED`/`STARTING`, absence pour `RUNNING_OWNED`/`EXTERNAL_ACTIVE`/`STOPPING`/Forge, nettoyage après succès/échec/annulation/changement de workspace) et à `InferencePageComfyUILifecycleRealStartTest::test_stopped_to_starting_to_running_owned_launches_original_generation` (texte réellement affiché pendant la phase `STARTING` réelle contre le harnais de process factice de Mission 114, puis effacé après readiness — sert de vérification visuelle légère, aucun smoke réel séparé jugé nécessaire).

Suite complète **2310/2310**, `git diff --check` propre, 103/103 tests `MainWindow` concernés (aucune boîte de dialogue réelle inattendue). Voir `docs/missions/MISSION_116.md` pour le détail complet.

### État du projet (Mission 116)

**2310/2310** tests automatisés verts (2309 avant Mission 116 + 1 net nouveau), aucune régression. Commit fonctionnel `7fe55cefd836f526e900ad7528d6a576c3cbc902` (`Add ComfyUI auto-start progress feedback to InferencePage`), tag `v0.2-mission116`, GitHub Release publiée. Voir `docs/missions/MISSION_116.md` pour le détail complet.

---

## v0.2-mission115 — 2026-09-12

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 115 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 115)

Ferme, pour ComfyUI Local uniquement, le sous-point « auto-start déclenché depuis Inference » resté ouvert par Mission 114 : un clic sur Generate avec ComfyUI arrêté démarre désormais automatiquement le backend via le `ComfyUILifecycleManager` partagé (la même instance que `SettingsPage`), attend sa disponibilité de façon non bloquante, puis lance automatiquement la génération originellement demandée — sans second clic, sans devoir ouvrir ComfyUI Desktop ni visiter Settings au préalable.

`InferencePage._start_generation()` capture désormais l'intégralité des paramètres de génération dans une structure immuable (`_PendingGenerationRequest`) au moment du clic, avant toute attente — jamais reconstruite depuis les widgets. Six comportements par état lifecycle : `RUNNING_OWNED`/`EXTERNAL_ACTIVE` lancent la génération immédiatement, sans jamais appeler `start()` ; `STOPPED`/`START_FAILED` mettent la requête en attente et démarrent ComfyUI ; `STARTING` s'attache au démarrage déjà en cours sans second appel ; `STOPPING` refuse immédiatement, sans mise en file d'attente. La configuration ComfyUI utilisée pour un démarrage automatique provient exclusivement de `ApplicationSettingsManager.settings` (persistée) — jamais des `QLineEdit` de `SettingsPage`, même en cas de saisie non enregistrée. Forge reste strictement inchangé, ce mécanisme étant entièrement gated sur le moteur ComfyUI.

Pendant la préparation du smoke réel, un défaut UI pré-existant et sans rapport avec cette mission a été découvert et corrigé séparément (commit distinct, hors tag `v0.2-mission115`) : `SettingsPage` ne disposait d'aucun `QScrollArea`, rendant son bouton Enregistrer physiquement inatteignable une fois le contenu de la page devenu plus haut que la fenêtre — bloquant de fait toute sauvegarde de `comfyui_install_path` depuis l'UI. Voir `docs/missions/MISSION_115.md` §13 pour le détail complet de ce correctif préalable, explicitement hors périmètre fonctionnel de Mission 115.

### Tests ajoutés (Mission 115)

**17 tests ciblés nets nouveaux** pour le mécanisme d'auto-start (2289 → 2306) : `tests/integration/test_inference_page.py` (16 tests couvrant les six états lifecycle, l'anti-double-clic, l'invalidation par changement de contexte, la garde d'identité contre un signal tardif, la confirmation de la source de configuration persistée, et l'instance lifecycle partagée ; 1 test de cycle réel `STOPPED→STARTING→RUNNING_OWNED` réutilisant le harnais de process factice de Mission 114). Trois fichiers de tests `MainWindow` préexistants (`test_main_window_close_event.py`, `test_main_window_new_project.py`, `test_main_window_rename_project.py`) ont été adaptés pour forcer `RUNNING_OWNED` avant leurs générations contrôlées par mock — un effet de bord attendu du nouveau gate lifecycle sur des tests sans rapport avec cette mission, sans changement de leurs assertions fonctionnelles propres.

**3 tests ciblés nets nouveaux** pour le correctif préalable `QScrollArea` (hors périmètre fonctionnel, commit séparé) : `tests/integration/test_settings_page.py::SettingsPageScrollableContentTest`. `tests/integration/test_settings_page.py` : 74/74 ; `tests/integration/test_main_window_initial_size.py` : 5/5 (aucune régression sur l'agrégation de taille du `QStackedWidget`).

Suite complète **2309/2309** (2289 + 17 nets Mission 115 + 3 nets QScrollArea), `git diff --check` propre. Deux scénarios de smoke réel PASS : **Scénario A** (`STOPPED → STARTING → RUNNING_OWNED`, ComfyUI réellement fermé au départ, démarrage réel, génération réelle automatique, image produite et confirmée sur disque) et **Scénario B** (`EXTERNAL_ACTIVE`, backend démarré hors du lifecycle Toolkit, génération immédiate sans aucun ownership pris, backend confirmé intact après la génération et après la fermeture de Toolkit). Voir `docs/missions/MISSION_115.md` pour le détail complet.

### État du projet (Mission 115)

**2309/2309** tests automatisés verts (2289 avant Mission 115 + 17 nets Mission 115 + 3 nets QScrollArea), aucune régression. Commit fonctionnel `c20bc8dfa9abeb93fccc15666345d4889a6f2d71` (`Add ComfyUI auto-start from Inference with pending generation handoff`), précédé du commit distinct `daba6bb2d823319b7bcd0bea3fe984776f532e13` (`Add QScrollArea to SettingsPage so all content stays reachable`, correctif préalable hors périmètre fonctionnel de Mission 115, hors tag), tag `v0.2-mission115`, GitHub Release publiée. Voir `docs/missions/MISSION_115.md` pour le détail complet.

---

## v0.2-mission114 — 2026-09-11

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 114 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 114)

Ferme, pour ComfyUI Local uniquement, le sous-point « démarrage/arrêt automatique » resté ouvert depuis le mini-audit post-Mission 105 : AI Studio Toolkit peut désormais démarrer et arrêter ComfyUI Local directement depuis `SettingsPage`, sans jamais devoir lancer ComfyUI Desktop manuellement au préalable. `ComfyUIEngine` reste un client HTTP pur, sans responsabilité process ajoutée — toute la logique nouvelle vit dans deux composants dédiés : un resolver Qt-free (`src/engines/comfyui_launch.py::resolve_comfyui_launch()`) et un composant Qt (`src/ui/comfyui_lifecycle_manager.py::ComfyUILifecycleManager`) qui possède le seul `QProcess` réellement lancé par Toolkit.

Le resolver combine `comfyui_path` (interpréteur `.venv/Scripts/python.exe`) et `comfyui_install_path` (`main.py`, via `resolve_comfyui_install()` de Mission 113 réutilisé inchangé) en une commande de lancement validée, avec une liste blanche stricte d'hôtes locaux (`127.0.0.1`/`localhost`, jamais `0.0.0.0`) pour `--listen`. Un diagnostic réel autorisé après un premier échec de smoke a révélé qu'un `--user-directory`/`--database-url` (dérivés de `comfyui_path`, format `sqlite:///` à trois slashes copié de la commande Desktop réelle) étaient nécessaires en pratique pour éviter une erreur réelle d'ouverture de base de données — ajoutés au resolver, aucun autre argument Desktop non prouvé nécessaire.

Six états explicites (`STOPPED`, `EXTERNAL_ACTIVE`, `STARTING`, `RUNNING_OWNED`, `STOPPING`, `START_FAILED`) pilotent le cycle de vie. Avant tout lancement, un `check_connection()` ponctuel détecte un backend déjà actif — succès → `EXTERNAL_ACTIVE`, aucun `QProcess` créé, aucun ownership pris, Stop neutralisé, fermeture sans dialogue. Un worker de disponibilité dédié (`src/ui/comfyui_readiness_worker.py::ComfyUIReadinessWorker`, même patron `moveToThread()` que `GenerationWorker`) interroge l'API en arrière-plan sans jamais bloquer le thread UI, avec un budget total de **120 secondes** (porté de 60s après qu'un premier smoke réel a montré un démarrage réel de 58,9s incluant l'initialisation CUDA/PyTorch et le scan des `custom_nodes`). Un timeout de readiness déclenche un nettoyage interne (`terminate()` → attente bornée → `kill()`) et atterrit directement sur `START_FAILED` avec le message d'échec préservé — jamais rétrogradé silencieusement vers un simple `STOPPED`. Stop est réservé strictement à un process réellement possédé par Toolkit, idempotent, avec le même repli `terminate()`→`kill()`.

`MainWindow.closeEvent()` gagne un nouveau guard (`confirm_safe_to_close()`, même contrat `True=proceed/False=abandon` que les guards existants) : fermeture bloquée pendant `STARTING`/`STOPPING` ; sur `RUNNING_OWNED`, une confirmation Oui/Non explicite propose d'arrêter ComfyUI avant de fermer, la fermeture réelle étant différée jusqu'à ce que Stop atteigne effectivement `STOPPED` ; sur `STOPPED`/`EXTERNAL_ACTIVE`/`START_FAILED`, fermeture immédiate sans dialogue. `SettingsPage` gagne deux boutons (Démarrer/Arrêter) et un label de statut lifecycle, visuellement distinct des labels d'installation (M113) et de connexion (M112).

Un bug Qt réel a été découvert et corrigé pendant l'implémentation : connecter un signal cross-thread à un `lambda` plutôt qu'à une méthode liée d'un `QObject` fait exécuter le slot sur le thread émetteur (une `lambda` n'a pas d'affinité de thread Qt introspectable), empêchant un `QTimer` de se déclencher — corrigé en connectant des méthodes liées réelles et en récupérant le worker émetteur via `self.sender()`.

Deux scénarios de smoke réel (jamais mockés) ont validé le contrat sur la machine de référence : **Scénario A** (ownership Toolkit) — démarrage réel, `RUNNING_OWNED` confirmé par un vrai test HTTP, Stop réel avec repli `kill()` effectivement nécessaire, zéro process orphelin ; **Scénario B** (backend externe) — un ComfyUI démarré manuellement est détecté immédiatement comme `EXTERNAL_ACTIVE`, sans second lancement, sans ownership, backend laissé intact et joignable à l'issue du test. Deux anomalies environnementales sans rapport avec cette mission ont été observées et documentées comme explicitement hors périmètre, non corrigées : une incompatibilité `comfyui-fluxtrainer`/`transformers` et une erreur Alembic de migration de base ComfyUI préexistante. Zéro modification de Forge, d'`InferencePage`/`GenerationManager` (aucun auto-start câblé), et aucune abstraction Provider/Executor pour un futur ComfyUI Cloud.

### Tests ajoutés (Mission 114)

**49 tests ciblés nets nouveaux** (2240 → 2289) : `tests/integration/test_comfyui_launch.py` (11 tests, resolver — validation de chemin/host/port, dérivation `--user-directory`/`--database-url`) ; `tests/integration/test_comfyui_lifecycle_manager.py` (25 tests — process factice déterministe pour le cycle de vie complet via un vrai `QProcess`, plus des tests d'appel direct pour l'escalade `terminate()`/`kill()` et les guards de fermeture, y compris protection contre les signaux tardifs d'un worker obsolète et absence de thread vivant après tout état terminal) ; `tests/integration/test_settings_page.py` (6 tests — délégation des boutons, mapping état→label/activation, indépendance vis-à-vis des labels M112/M113) ; `tests/integration/test_main_window_close_event.py` (7 tests — guard de fermeture pour les six états, y compris le flux Oui/Non différé sur `RUNNING_OWNED`). Une correction a également été apportée à ce dernier fichier pendant la mission : son `tearDown()` provoquait une vraie boîte de dialogue modale bloquante pendant la suite automatisée lorsqu'un test laissait l'état lifecycle à `STARTING` derrière lui — corrigé par une réinitialisation défensive systématique de l'état avant la fermeture réelle en fin de test. Suite complète **2289/2289**, `git diff --check` propre, smoke réel double scénario PASS. Voir `docs/missions/MISSION_114.md` pour le détail complet.

### État du projet (Mission 114)

**2289/2289** tests automatisés verts (2240 avant Mission 114 + 49 nets nouveaux), aucune régression. Commit fonctionnel `de618eab4876de38795d3d749df8320e12be83aa` (`Add ComfyUI Local lifecycle management (Start/Stop/ownership/readiness)`), tag `v0.2-mission114`, GitHub Release publiée. Voir `docs/missions/MISSION_114.md` pour le détail complet.

---

## v0.2-mission113 — 2026-09-11

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 113 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 113)

Prolonge Mission 112 (diagnostic de joignabilité HTTP) en fermant une autre facette de la même friction : l'absence de toute connaissance, côté Toolkit, de l'emplacement réel des installations locales ComfyUI Desktop et Forge sur le disque. Un micro-audit environnemental read-only préalable (aucun backend lancé) a établi par inspection directe des fichiers réels de la machine que `comfyui_path` désignait déjà correctement la racine de données (`--base-directory`, confirmé identique au `basePath` de `%APPDATA%\ComfyUI\config.json`), mais que le véritable point d'entrée exécuté par ComfyUI Desktop (`resources/ComfyUI/main.py`) vit dans une installation Electron entièrement distincte, non dérivable de `comfyui_path` ; Forge, de son côté, ne disposait d'aucun champ de chemin d'installation local, alors que son installation portable réelle (`run.bat` à la racine, encapsulant l'environnement Python portable avant `webui-user.bat`/`launch.py`) était déjà connue depuis l'audit pré-smoke de Mission 108.

`ApplicationSettings` gagne deux réglages nouveaux et strictement indépendants, `""` par défaut, rétrocompatibles avec un `application_settings.json` existant qui ne les contient pas : `comfyui_install_path` (racine de l'installation ComfyUI Local/Desktop) et `forge_path` (racine d'une installation Forge locale). `comfyui_path` garde exactement sa signification actuelle — les deux concepts ne sont jamais fusionnés, la distinction étant confirmée par des preuves factuelles indépendantes plutôt que supposée. Deux resolvers Qt-free dans `src/engines/` (`comfyui_install.py::resolve_comfyui_install()`, `forge_install.py::resolve_forge_install()`) mirent le patron déjà établi par `resolve_onetrainer_launch()` (Mission 100) : chacun valide par simple existence de fichier la présence réelle du point d'entrée attendu (`resources/ComfyUI/main.py`, `run.bat`) — jamais seulement « le dossier existe » — et lève une exception dédiée à message actionnable (`ComfyUIInstallError`/`ForgeInstallError`) nommant le chemin exact vérifié. Aucun des deux ne touche au réseau ni ne lance de process ; construire une commande de lancement réelle reste délibérément différé à une future mission « Start ».

`SettingsPage` gagne un bouton « Parcourir… » pour `comfyui_path_edit` et `onetrainer_path_edit` (deux champs déjà réellement dossiers, mais qui n'en disposaient pas jusqu'ici) ainsi que pour les deux nouveaux champs, plus un bouton « Vérifier l'installation » et un label de statut par moteur, testant le chemin actuellement saisi — pas nécessairement déjà sauvegardé — sans jamais déclencher de sauvegarde implicite. `python_path_edit` reste volontairement exclu de ce périmètre : aucun code du dépôt ne le consomme, et sa sémantique exacte (dossier ou exécutable direct) demeure indéterminée — lui appliquer `getExistingDirectory()` par simple analogie aurait été une supposition non vérifiée. Le statut de validation statique et le statut de connexion HTTP de Mission 112 restent deux mécanismes et deux états strictement indépendants : modifier ou parcourir un chemin d'installation n'invalide jamais que le statut d'installation de son propre moteur, jamais celui de l'autre moteur ni un statut de connexion — comportement vérifié explicitement par test. Zéro modification d'`InferencePage`, `GenerationManager`, `ComfyUIEngine`/`ForgeEngine`, OneTrainer ou de `MainWindow` : aucun processus n'est démarré, arrêté, ni possédé par cette mission. ComfyUI Local et un futur ComfyUI Cloud restent deux concepts distincts — `comfyui_install_path` et son resolver décrivent exclusivement une installation locale.

### Tests ajoutés (Mission 113)

**10 tests ciblés nets nouveaux** (2230 → 2240) : 4 dans `tests/integration/test_comfyui_install.py` et 4 dans `tests/integration/test_forge_install.py` (chemin vide/blanc, chemin inexistant, dossier existant sans le point d'entrée attendu, installation complète — tous contre de vrais répertoires temporaires jetables, jamais l'installation réelle de la machine), et 2 nouveaux tests dans `test_application_settings_roundtrip.py` (chargement d'un `application_settings.json` antérieur à cette mission sans `comfyui_install_path`/`forge_path`, tombant sur `""` sans erreur ; contrat complet de validation statique/invalidation/indépendance vis-à-vis de Mission 112 dans `SettingsPage`, avec de vrais widgets Qt et de vrais répertoires temporaires jouant le rôle d'installations, sans jamais mocker un resolver). Suite complète **2240/2240**, `git diff --check` propre, smoke Qt réel PASS. Voir `docs/missions/MISSION_113.md` pour le détail complet.

### État du projet (Mission 113)

**2240/2240** tests automatisés verts (2230 avant Mission 113 + 10 nets nouveaux), aucune régression. Commit fonctionnel `5053abaa613fa06a8928c9bec2ac9c397ba66728` (`Add local ComfyUI/Forge installation paths and static launcher validation`), tag `v0.2-mission113`, GitHub Release publiée. Voir `docs/missions/MISSION_113.md` pour le détail complet.

---

## v0.2-mission112 — 2026-09-11

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 112 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 112)

Ferme une friction réelle laissée ouverte depuis Mission 107/108 : l'utilisateur ne découvrait qu'ComfyUI ou Forge est indisponible qu'au moment d'une vraie action (une génération, ou un clic « Rafraîchir » dans Inference), et cette découverte était structurellement inégale entre les deux moteurs dans Settings — ComfyUI n'y disposait que d'un test indirect (`refresh_checkpoints()`, dont le succès signifie « des checkpoints ont été trouvés », jamais explicitement « le backend est joignable ») et Forge n'y disposait d'aucun mécanisme de connexion d'aucune sorte. `ComfyUIEngine` et `ForgeEngine` gagnent chacun une méthode `check_connection(timeout=None) -> bool`, un pur wrapper de leur `list_checkpoints()` déjà existant — même endpoint applicatif (`GET /object_info/CheckpointLoaderSimple` / `GET /sdapi/v1/sd-models`), même validation structurelle, aucune nouvelle route HTTP. Une réponse structurellement valide, y compris avec zéro checkpoint, retourne `True` : la joignabilité n'est jamais confondue avec « a des modèles ». Tout échec propage `ComfyUIEngineError`/`ForgeEngineError` — l'exception déjà levée par `list_checkpoints()` — strictement inchangée, jamais absorbée en un simple `False`, préservant l'information diagnostique (URL, raison exacte) dont `SettingsPage` a besoin pour un feedback actionnable.

`SettingsPage` gagne un bouton « Tester la connexion » et un label de statut par moteur, positionnés directement sous chaque champ URL. Chaque test cible la valeur actuellement saisie, pas nécessairement déjà sauvegardée, via un engine transitoire — exactement le pattern déjà établi par `refresh_checkpoints()`/`refresh_loras()` (Mission 025) — sans jamais toucher à un combo checkpoint/LoRA ni déclencher `save_application_settings()`. Forge obtient ainsi son premier mécanisme de connexion de toute nature dans Settings ; ComfyUI obtient un test d'accessibilité explicite, distinct de l'effet de bord existant de la découverte de checkpoints. Le statut de chaque moteur s'invalide indépendamment vers un état neutre sur une vraie saisie utilisateur dans son champ URL (`textEdited`, jamais `textChanged`) — un rechargement programmatique de Settings (`update_application_settings()`, qui recharge ces champs via `setText()` sans `blockSignals()`) ne déclenche donc jamais une fausse invalidation. Zéro modification d'`InferencePage`, `GenerationManager`, OneTrainer, ou de la gestion de processus : aucun démarrage/arrêt automatique des backends n'est introduit par cette mission, qui ferme strictement le diagnostic de connexion.

### Tests ajoutés (Mission 112)

**27 tests ciblés nets nouveaux** (2203 → 2230) : 5 dans `test_comfyui_engine.py` (nouvelle classe `ComfyUIEngineCheckConnectionTest` — succès avec et sans checkpoints, propagation de `ComfyUIEngineError` sur backend injoignable et sur réponse structurellement invalide, transmission du timeout personnalisé), 5 dans `test_forge_engine.py` (même structure, `ForgeEngineCheckConnectionTest`, adaptée à `/sdapi/v1/sd-models` et `ForgeEngineError`), et 17 dans `test_settings_page.py` (13 dans une nouvelle classe `SettingsPageConnectionDiagnosticsTest` — URL actuellement saisie utilisée par chaque bouton, statut positif/négatif par moteur, aucune sauvegarde implicite, invalidation indépendante par moteur sur `textEdited`, absence d'invalidation sur un rechargement programmatique, isolation stricte entre les deux moteurs — et 4 dans une classe `SettingsPageConnectionDiagnosticsRealEngineSmokeTest`, un smoke Qt réel ne mockant que la frontière réseau `urllib.request.urlopen` — jamais les classes Engine elles-mêmes — pour exercer le vrai `check_connection()` de bout en bout depuis un vrai clic de bouton sur un vrai widget `SettingsPage`). Suite complète **2230/2230**, `git diff --check` propre. Le smoke réel a été jugé pertinent ici, contrairement à Mission 111, précisément parce que `SettingsPage` — un widget Qt réel — était modifiée. Voir `docs/missions/MISSION_112.md` pour le détail complet.

### État du projet (Mission 112)

**2230/2230** tests automatisés verts (2203 avant Mission 112 + 27 nets nouveaux), aucune régression. Commit fonctionnel `1c40fca14ef1e73e05deb792240388a3fd46131b` (`Add explicit ComfyUI/Forge connection diagnostics in Settings`), tag `v0.2-mission112`, GitHub Release publiée. Voir `docs/missions/MISSION_112.md` pour le détail complet.

---

## v0.2-mission111 — 2026-09-11

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 111 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 111)

Ferme le premier maillon de la chaîne de provenance du trigger, resté ouvert après Mission 110 : `Character.trigger_token` et `Training.trigger_word` existaient côte à côte sans jamais être reliés, obligeant à ressaisir manuellement le même trigger d'identité à chaque nouveau `Training` d'un Character qui en possédait déjà un — une friction réelle et désormais évitable, puisque Mission 110 garantit déjà la propagation fidèle de `Training.trigger_word` jusqu'à la Central LoRA Library puis Inference. `TrainingManager.create()` initialise désormais `trigger_word` depuis le `trigger_token` du principal Character (`character.trigger_token or ""`), mais uniquement comme valeur de départ, appliquée une seule fois, au moment de la construction de l'objet. Aucune modification de `TrainingPage` (`active_training["trigger_word"]` était déjà affiché tel quel) : le mécanisme entier tient dans `TrainingManager.create()`, la simplification architecturale découverte pendant la rédaction du contrat de mission et validée par l'architecte avant implémentation.

Une fois le `Training` créé, `trigger_word` redevient une donnée entièrement autonome : une modification ultérieure de `Character.trigger_token` ne touche plus jamais ce `Training` ; recharger ou sélectionner un `Training` existant — même avec un `trigger_word` vide — ne déclenche jamais de préremplissage tardif ; une valeur saisie manuellement n'est jamais écrasée. Un Character sans `trigger_token` produit un `Training` avec `trigger_word` vide, comportement strictement inchangé. Mission 110 continue de transmettre fidèlement à la Central LoRA Library et à Inference la valeur réellement stockée sur le `Training`, qu'elle soit préremplie automatiquement ou saisie à la main — indiscernable pour la suite du parcours. Zéro modification de `TrainingPage`, `CharacterManager`, Domain, `MainWindow`, Engines ou EventBus.

### Tests ajoutés (Mission 111)

**7 tests ciblés nets nouveaux** (2196 → 2203), tous dans `test_training_roundtrip.py` : 6 dans une nouvelle classe `TrainingManagerTriggerWordDefaultPrefillTest` couvrant directement `TrainingManager.create()` (préremplissage depuis un `trigger_token` non vide, absence de préremplissage si le Character n'en a pas, non-modification d'un `Training` existant au rechargement qu'il soit renseigné ou vide, non-écrasement d'une valeur saisie manuellement, non-effet d'un changement ultérieur de `Character.trigger_token` sur un `Training` déjà créé) et 1 dans la classe existante `TrainingPageJobImportTest` (non-régression Mission 110 : un `trigger_word` préremplid par cette mission est transmis à l'import de la Central LoRA Library exactement comme une valeur saisie manuellement). Suite complète **2203/2203**, `git diff --check` propre. Aucun smoke Qt ajouté : le comportement est entièrement contenu dans `TrainingManager.create()`, `TrainingPage` reste inchangée, et les tests d'intégration ci-dessus couvrent déjà directement le comportement réel — un smoke supplémentaire n'aurait apporté aucune preuve additionnelle fiable. Voir `docs/missions/MISSION_111.md` pour le détail complet.

### État du projet (Mission 111)

**2203/2203** tests automatisés verts (2196 avant Mission 111 + 7 nets nouveaux), aucune régression. Commit fonctionnel `ba66caa68df7f7eda80950dd134769321f18cd7c` (`Prefill Training.trigger_word from Character.trigger_token at creation`), tag `v0.2-mission111`, GitHub Release publiée. Voir `docs/missions/MISSION_111.md` pour le détail complet.

---

## v0.2-mission110 — 2026-09-11

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 110 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 110)

Ferme la dernière rupture sémantique du parcours principal identifiée par l'audit post-Mission 109 : le `trigger_word` saisi pendant un `Training` ne survivait pas à son import dans la Central LoRA Library, et `InferencePage` ne l'exposait ni ne l'exploitait nulle part, malgré la présélection automatique du bon LoRA livrée par Mission 109. `TrainingPage.import_selected_job_to_library()` transmet désormais `training.trigger_word` à `LoRALibraryManager.import_lora()` (paramètre déjà accepté depuis Mission 088 — seul l'appelant change, aucune modification du Manager) ; un `Training` sans trigger produit toujours un `LoRA` avec `trigger_word` vide, comportement inchangé. `InferencePage` affiche désormais le trigger du LoRA sélectionné en lecture seule (nouveau `QLabel` + méthode partagée `_refresh_lora_trigger_widgets()`), recalculé aux deux seuls points existants qui font varier `self._selected_lora_choice` — `_on_lora_selection_changed()` et `refresh_lora_selector()`, y compris via le `target_lora_id=...` du handoff Mission 109 — et propose une action explicite « Insérer le trigger » (`insert_selected_lora_trigger_into_prompt()`) : prompt vide → trigger seul ; prompt existant → trigger inséré en tête, séparé par `, `, reste du prompt strictement inchangé. Non-duplication par comparaison exacte et sensible à la casse contre les éléments du prompt découpé sur les virgules (jamais une recherche de sous-chaîne, jamais insensible à la casse). Le trigger n'est **jamais** inséré automatiquement, y compris pendant le handoff Mission 109, qui continue de ne jamais toucher au prompt. Zéro modification de `LoRALibraryManager`/`TrainingManager`/Domain/`MainWindow`/Engines/EventBus.

### Tests ajoutés (Mission 110)

**12 tests ciblés nets nouveaux** (2184 → 2196) : 2 dans `test_training_roundtrip.py` (carryover du trigger à l'import, avec et sans `trigger_word`) et 10 dans `test_inference_page.py` (affichage/état du trigger selon la sélection, insertion dans un prompt vide et dans un prompt existant, non-duplication sur une correspondance exacte, distinction de casse explicitement vérifiée par un test dédié, non-régression du handoff Mission 109 — le prompt reste intact). Suite complète **2196/2196**, `git diff --check` propre. Validation réelle non mockée : smoke test avec des widgets Qt réels (`MainWindow` réelle), `lora_library_manager.list_loras()`/`get()` patchés avec des LoRA fixtures contrôlées (aucune mutation réelle de la Central LoRA Library) — trigger affiché et bouton d'insertion activé pour un LoRA avec trigger, prompt correctement modifié après insertion, absence de duplication après un second clic, affichage/bouton réinitialisés pour un LoRA sans trigger. Voir `docs/missions/MISSION_110.md` pour le détail complet.

### État du projet (Mission 110)

**2196/2196** tests automatisés verts (2184 avant Mission 110 + 12 nets nouveaux), aucune régression. Commit fonctionnel `0e4c8df6679d056f5379c5082193506828a752f9` (`Carry Training trigger_word into imported LoRA and expose it in Inference`), tag `v0.2-mission110`, GitHub Release publiée. Voir `docs/missions/MISSION_110.md` pour le détail complet.

---

## v0.2-mission109 — 2026-09-10

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 109 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 109)

Le flux principal `Images → Dataset/captions → OneTrainer → LoRA → Central Library → Inference` gagne son dernier maillon manuel : après l'import d'un résultat de Training dans la Central LoRA Library (Mission 103), l'utilisateur pouvait déjà voir ce LoRA apparaître automatiquement dans le combo `InferencePage` sans redémarrage (`LORA_LIBRARY_IMPORTED` déjà câblé sur `refresh_lora_selector` depuis Mission 108), mais devait ensuite le retrouver manuellement par son nom. Un nouveau bouton persistant « Utiliser dans Inference » apparaît dans `TrainingPage`, à côté de l'action d'import — activé uniquement lorsque le Job sélectionné a un `imported_lora_id` qui résout encore vers une entrée réelle de la Central Library, recalculé à chaque changement de sélection par une nouvelle méthode `_usable_in_inference_job()` symétrique à `_importable_job()` (jamais un état mis en cache : si le LoRA est ensuite supprimé de la bibliothèque, le bouton redevient indisponible).

Un clic émet un signal Qt local (`use_lora_in_inference_requested`, mirroir exact de `PromptsPage.send_to_inference_requested` de Mission 033) ; `MainWindow` reste seul médiateur, appelant `InferencePage.refresh_lora_selector(target_lora_id=lora_id)` puis naviguant vers Inference — aucun nouvel événement EventBus, `TrainingPage` ne référence jamais `InferencePage`. `refresh_lora_selector()` gagne un unique paramètre nommé optionnel `target_lora_id`, prioritaire sur la sélection précédente lorsqu'il est fourni et présent dans le combo reconstruit ; les 3 abonnements EventBus existants (`LORA_LIBRARY_IMPORTED`/`DELETED`/`UPDATED`) continuent de l'appeler sans ce paramètre, comportement byte-for-byte inchangé. Aucun `trigger_word` inséré automatiquement, aucune modification du prompt, aucune navigation automatique après un import (le `QMessageBox` de succès existant n'est pas remplacé). Zéro modification de `LoRALibraryManager`/`TrainingManager`/Domain/`ComfyUIEngine`/`ForgeEngine`. Les besoins futurs déjà enregistrés pendant Mission 108 (liaison Character → Training → LoRA → trigger, refonte UX/UI de `InferencePage`, gestion automatique des backends, séparation application/données, emplacement configurable des projets, lisibilité des dossiers physiques de la Central LoRA Library) restent tous ouverts, non tranchés par cette mission.

### Tests ajoutés (Mission 109)

**18 tests ciblés nets nouveaux** (2166 → 2184) : 8 dans `test_training_roundtrip.py` (nouvelle classe `TrainingPageUseLoraInInferenceTest` — bouton désactivé sans Job/pour un Job non importé, activé pour un `imported_lora_id` réel, désactivé de nouveau après suppression du LoRA, réactivé après réimport, émission exacte du signal, aucune émission sans Job utilisable, non-régression du dirty-state), 5 dans `test_inference_page.py` (`target_lora_id` sélectionné par défaut, prioritaire sur `previous_choice`, absence/`None`/valeur inconnue répliquant le comportement historique), 5 dans le nouveau `test_main_window_training_to_inference.py` (câblage réel du signal, navigation réelle vers Inference, présélection réelle, non-modification du prompt, non-régression de `workspace_manager.save()`). Suite complète **2184/2184**, `git diff --check` propre. Validation réelle non mockée : smoke test avec des widgets Qt réels (`MainWindow` réelle), réutilisant le LoRA réel « Zaraya Koyah SDX » déjà présent dans la Central LoRA Library (jamais réimporté, supprimé, renommé, ni modifié — vérifié par comparaison avant/après) via un Job/Workspace isolé et temporaire référençant son `lora_id` existant. Voir `docs/missions/MISSION_109.md` §12 pour le détail complet.

### État du projet (Mission 109)

**2184/2184** tests automatisés verts (2166 avant Mission 109 + 18 nets nouveaux), aucune régression. Commit fonctionnel `528f45abc1d21ed207c8ee1ff309dc95413d5ad1` (`Add Training result to Inference handoff`), tag `v0.2-mission109`, GitHub Release publiée. Voir `docs/missions/MISSION_109.md` pour le détail complet, notamment §12 pour le résultat réel et les preuves du smoke réel.

---

## v0.2-mission108 — 2026-09-10

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 108 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 108)

Forge devient un second moteur d'Inference réellement utilisable depuis l'UI, au-dessus de la fondation technique invisible posée par Mission 107. `InferencePage` gagne un sélecteur de moteur ComfyUI/Forge (prompt, négatif, référence, force de transformation, dimensions/steps/CFG/seed et sélection LoRA logique préservés au changement de moteur ; checkpoint/sampler/scheduler invalidés et à redécouvrir, jamais réutilisés d'un moteur à l'autre), une découverte réelle de checkpoints/samplers/schedulers ciblant le moteur actif (`GenerationManager.list_checkpoints()`/`list_samplers()`/`list_schedulers()` étendus d'un paramètre `engine=` optionnel par-appel, même généralisation que `generate()` depuis Mission 107), et un combo LoRA simplifié à deux états partagés par les deux moteurs (« Aucun LoRA » ou une entrée réelle de la Central LoRA Library — le repli implicite sur un LoRA par défaut de Settings, historique de Mission 059, est retiré). Un checkpoint explicite est obligatoire pour générer avec Forge (aucun repli Settings, contrairement à ComfyUI qui conserve son comportement historique).

`LoRALibraryManager.expose_to_comfyui()` est généralisé en une méthode privée `_expose()` partagée, avec un nouveau `expose_to_forge()` symétrique — même mécanisme de hardlink NTFS zéro-duplication, même idempotence, même gestion de collision. Settings Forge strictement minimaux : `forge_url`/`forge_lora_expose_path` (`ApplicationSettings`, `SettingsPage`, avec bouton « Parcourir… ») — aucun champ checkpoint/LoRA par défaut côté Forge, Forge restant supposé démarré extérieurement par l'architecte, exactement comme ComfyUI et OneTrainer.

**Défaut fonctionnel découvert par le premier smoke LoRA réel contre un serveur Forge réellement démarré, corrigé avant clôture** : une génération HTTP réussie sans erreur ne signifiait pas que le LoRA avait réellement été appliqué — confirmé par l'absence de la ligne `Lora hashes:` dans les métadonnées PNG retournées par Forge (option native Forge activée par défaut). Root cause, établie par lecture directe du code source de l'extension Forge réellement installée (`extra_networks_lora.py`/`networks.py`) : `ForgeEngine._apply_lora_syntax()` transmettait tel quel l'alias `LoRALibraryManager` (sous-dossier + extension, convention correcte pour `ComfyUIEngine.LoraLoader`) dans la syntaxe `<lora:nom:force>`, alors que Forge indexe en réalité ses LoRA par le seul nom de fichier, sans sous-dossier ni extension (`os.path.splitext(os.path.basename(filename))[0]`) — Forge ignorait donc silencieusement toute référence non résolue, sans jamais lever d'erreur HTTP, un défaut fonctionnel invisible à toute vérification purement HTTP. Corrigé par une nouvelle méthode statique `ForgeEngine._forge_lora_tag_name()`, confinée à `forge_engine.py` (aucun `isinstance` contre un type de moteur concret introduit dans `GenerationManager`/`InferencePage`), convertissant explicitement `/` en `\` avant `ntpath.basename()`/`ntpath.splitext()` — `ntpath` choisi délibérément pour reproduire l'algorithme natif de Forge avec une sémantique Windows garantie, indépendamment de l'OS exécutant les tests. **Second smoke réel après correction** : le tag `<lora:...>` corrigé et la ligne `Lora hashes:` retournée par Forge confirment l'application réelle du LoRA par le serveur, hash cross-vérifié contre le `sshs_model_hash` embarqué dans l'en-tête du fichier `.safetensors` canonique de la Central LoRA Library. Parcours `Generate → Preview → Accept → Images` validé de bout en bout, aussi bien pour une génération txt2img simple que pour une génération avec LoRA exposé.

Plusieurs besoins futurs ont été enregistrés en documentation pendant cette mission, sans modifier son périmètre fermé ni engager d'implémentation : gestion automatique du backend Forge (à étudier conjointement avec le besoin équivalent déjà identifié pour ComfyUI), refonte UX/UI de `InferencePage` (hiérarchie visuelle et regroupement par zones fonctionnelles, une fois les moteurs stabilisés), séparation application/données persistantes/projets/bibliothèques de modèles/caches pour la distribution future de Toolkit, emplacement racine configurable pour les projets avec migration sécurisée, et lisibilité des dossiers physiques de la Central LoRA Library (nom humainement lisible plutôt qu'un `lora_id` UUID seul). Voir "Besoins futurs identifiés par l'usage réel" dans `docs/PROJECT_CONTEXT.md` pour le détail complet de chacun.

### Tests ajoutés (Mission 108)

**43 tests ciblés nets nouveaux** (2123 → 2166, en deux temps) : 37 pour l'intégration initiale (2123 → 2160 — sélecteur de moteur et checkpoint dans `test_inference_page.py`, override `engine=` dans `test_generation_manager.py`, `expose_to_forge()` dans `test_lora_library_roundtrip.py`, champs Settings Forge dans `test_application_settings_roundtrip.py` et le nouveau `test_main_window_forge_settings.py`, propagation `engine`/`checkpoint_name` dans `test_generation_worker.py`, `list_checkpoints()` dans `test_comfyui_engine.py`), puis 6 pour le correctif de normalisation du nom LoRA découvert par le smoke réel (2160 → 2166, dans `test_forge_engine.py` — sous-dossier Windows avec extension, sous-dossier avec séparateur `/`, non-régression sans sous-dossier ni extension, espaces/tirets/underscores, une autre extension supportée par Forge, non-régression txt2img et img2img). Suite complète **2166/2166**, `git diff --check` propre. Validation réelle non mockée : smoke test contre un serveur Forge réellement démarré par l'architecte (découverte checkpoints/samplers/schedulers, génération txt2img réelle via l'UI réelle, exposition d'un LoRA réel de la Central Library par hardlink vérifié au niveau filesystem — device/inode identiques, zéro duplication physique —, génération avec LoRA confirmée appliquée par la métadonnée `Lora hashes:` de Forge lui-même, cross-vérifiée contre le hash d'entraînement embarqué du fichier `.safetensors`). Voir `docs/missions/MISSION_108.md` §7/§12.3/§12.5 pour le détail complet.

### État du projet (Mission 108)

**2166/2166** tests automatisés verts (2123 avant Mission 108 + 43 nets nouveaux), aucune régression. Commit fonctionnel `8e0e61f5d2b4677f34657c186591e59970e6491c` (`Add Forge engine support to InferencePage with real LoRA exposure`), tag `v0.2-mission108`, GitHub Release publiée. Voir `docs/missions/MISSION_108.md` pour le détail complet, notamment §12 pour le résultat réel, le correctif de normalisation LoRA et les preuves du smoke réel.

---

## v0.2-mission107 — 2026-09-09

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 107 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 107)

Trois mini-audits read-only préparatoires ont retenu **Forge** (Stable Diffusion WebUI Forge, installé réellement sur cette machine, `J:\Programmes\WebUI Forge CU121`) comme deuxième moteur d'Inference, sur la base d'une API HTTP native complète (`/sdapi/v1/txt2img`, `/img2img`, `/sd-models`, `/samplers`, `/schedulers`, `/loras`) — Fooocus a été différé faute d'API fiable. Il a également été vérifié, par lecture directe du code source réel de l'installation Forge, que `reference_strength`/`denoise` (ComfyUI) et `denoising_strength` (Forge) sont réellement équivalents : les deux calculent `t_enc = int(strength * steps)`, le même algorithme historique d'img2img Stable Diffusion, avec le même défaut `0.75`.

Cette mission est une **fondation technique invisible** : elle introduit `ForgeEngine` (`src/engines/forge_engine.py`, nouveau), un client HTTP Qt-free de même rang que `ComfyUIEngine` — découverte de checkpoints/LoRA/samplers/schedulers, `generate_image()` choisissant `POST /sdapi/v1/txt2img` ou `/img2img` selon la présence d'une référence, LoRA encapsulé via la syntaxe `<lora:nom:force>` (Forge n'a aucun champ API dédié pour un LoRA), décodage base64 des images retournées. Le checkpoint par appel est appliqué via `override_settings={"sd_model_checkpoint": ...}` avec `override_settings_restore_afterwards=True` — vérifié directement dans le code réel de l'installation Forge (`modules/processing.py::process_images()`, dont le docstring confirme littéralement l'application puis la restauration des overrides) : la valeur globale précédente est automatiquement restaurée après chaque génération, et `/sdapi/v1/options` (qui persisterait un changement) n'est jamais utilisé par `ForgeEngine`.

`GenerationManager.generate()` est généralisé avec `engine`/`checkpoint_name` en paramètres optionnels par-appel, repliant sur les valeurs du constructeur si omis — comportement ComfyUI historique strictement inchangé pour tout appelant existant. **Correction architecturale demandée par l'architecte après une première ébauche, appliquée avant clôture** : la première implémentation faisait dépendre `GenerationManager` de l'identité concrète du moteur (`isinstance(target_engine, ForgeEngine)`) pour choisir entre transmettre `denoise` (ComfyUI) ou `denoising_strength` (Forge) — un couplage jugé contraire à l'objectif même de la mission. Corrigé en renommant le paramètre Python de `ForgeEngine.generate_image()` de `denoising_strength` en `denoise`, identique au nom déjà utilisé par `ComfyUIEngine.generate_image()` depuis Mission 024 : `GenerationManager` transmet désormais toujours `denoise=reference_strength` quel que soit le moteur ciblé, sans aucun `isinstance` contre un type de moteur concret — verrouillé par deux tests dédiés lisant directement le source du module. `ForgeEngine` reste seul responsable de la traduction de ce nom Python commun vers le champ natif `denoising_strength` du payload JSON réellement envoyé à Forge. **Aucune modification de `ComfyUIEngine`/`comfyui_engine.py`** n'a été nécessaire.

**Aucune fonctionnalité Forge visible dans l'UI** : zéro nouveau champ `ApplicationSettings`, zéro modification de `SettingsPage`, `InferencePage`, `LoRALibraryManager`, `src/domain/` — l'application se comporte exactement comme avant pour l'architecte. Aucun smoke Forge réel exécuté ni exigé par cette mission, conformément à la politique définie en amont : reporté à **Mission 108**, seule responsable de l'intégration utilisateur réelle (Settings Forge minimaux, sélecteur de moteur dans `InferencePage`, généralisation de l'exposition Central Library, câblage checkpoint/LoRA/références, et le smoke réel lui-même avec `--api` activé manuellement par l'architecte).

### Tests ajoutés (Mission 107)

**60 tests ciblés nets nouveaux** (2063 → 2123) : 46 dans `test_forge_engine.py` (construction, découverte checkpoints/LoRA/samplers/schedulers avec succès/échec HTTP/forme invalide pour chacune, upload sans appel réseau, payload txt2img complet, checkpoint via `override_settings` avec restauration, LoRA encapsulé dans le prompt, payload img2img avec référence et `denoise`↔`denoising_strength`, décodage base64 avec et sans préfixe `data:image/`, extension devinée depuis la signature binaire réelle, erreurs HTTP/réponses invalides normalisées en `ForgeEngineError`, signature Python de `generate_image()` verrouillée sur `denoise`), 14 dans `test_generation_manager.py` (`engine`/`checkpoint_name` par-appel, bascule ComfyUI→Forge→ComfyUI sans état périmé au sein d'une même session, duck-typing explicite jamais `isinstance`, normalisation `ForgeEngineError`, agnosticisme de moteur pour `denoise` verrouillé par lecture directe du source de `GenerationManager`). Suite complète **2123/2123**, `git diff --check` propre, aucun appel réseau réel, aucun Forge/ComfyUI/GPU réel sollicité par aucun test — transport HTTP entièrement contrôlé (mock/fake). Voir `docs/missions/MISSION_107.md` §7/§12.4 pour le détail complet.

### État du projet (Mission 107)

**2123/2123** tests automatisés verts (2063 avant Mission 107 + 60 nets nouveaux), aucune régression. Commit fonctionnel `4a36d134822cbe5827afcc7a2108baf979e7d475` (`Add ForgeEngine foundation and generalize GenerationManager for a second engine`), tag `v0.2-mission107`, GitHub Release publiée. Voir `docs/missions/MISSION_107.md` pour le détail complet, notamment §12 pour le résultat réel et la correction architecturale demandée par l'architecte.

---

## v0.2-mission106 — 2026-09-09

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 106 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 106)

L'audit post-Mission 105 a réexaminé une dette IMPORTANTE identifiée avant Mission 105 : `Training.base_model_source` n'était validé nulle part avant qu'un Job réel ne soit créé. Un chemin vide, blanc, ou manifestement invalide n'échouait qu'après que `TrainingManager` avait déjà copié le Dataset et lancé un vrai sous-processus OneTrainer (chargement `torch`/venv réel), avec un message générique sans rapport avec la cause réelle.

Un mini-audit dédié, fondé sur la lecture directe du code source réel de l'installation OneTrainer (`StableDiffusionModelLoader.py`/`FluxModelLoader.py`/`TrainConfig.py`), a établi que `base_model_source` représente légitimement trois formes — fichier checkpoint local, dossier Diffusers local, ou identifiant Hugging Face (la valeur par défaut native d'OneTrainer lui-même) — invalidant l'hypothèse initiale d'une simple vérification `Path.is_file()`, qui aurait à tort bloqué deux de ces trois formes légitimes. Le principe retenu : Toolkit ne rejette que les valeurs dont il peut être certain qu'aucune forme acceptée par OneTrainer ne pourrait jamais les utiliser.

`validate_base_model_source()` (nouveau module Qt-free `src/utils/base_model_source.py`, même famille que `src/utils/lora_library_path.py` de Mission 104) rejette uniquement une valeur vide/blanche, ou un chemin absolu Windows (`os.path.isabs()` — backslash, slash, ou UNC, les trois formes vérifiées empiriquement comme équivalentes sur cette machine) qui n'existe ni comme fichier ni comme dossier, ou qui est inaccessible (une `OSError` sur un hôte UNC injoignable, découverte pendant l'implémentation, est traitée comme une inexistence). Un fichier existant, un dossier existant, une chaîne relative, ou un identifiant Hugging Face continuent de passer sans aucune vérification de contenu ni appel réseau.

La validation s'exécute en un point unique, `TrainingManager.prepare_onetrainer_config()`, avant toute résolution de Character/Dataset — le même point de convergence déjà emprunté par le bouton Prepare et par l'auto-Prepare de Start (invariant `_config_stale` de Mission 105), garantissant qu'aucune des deux voies ne peut diverger. `InvalidBaseModelSourceError` est reconvertie en `TrainingPreparationError`, déjà capturée par `TrainingPage` aux deux sites d'appel — aucune modification de `TrainingPage`, du Domain, de `onetrainer_config.py`, ni de Settings.

**Zéro modification de `src/ui/pages/training_page.py`, `src/domain/`, `src/engines/`, ni `src/ui/pages/settings_page.py`.**

### Tests ajoutés (Mission 106)

**16 tests ciblés nets nouveaux** (2047 → 2063) : 9 dans `ValidateBaseModelSourceTest` (Qt-free — vide, whitespace, `C:\`/`C:/`/UNC manquants, fichier/dossier existants, chaîne relative, identifiant Hugging Face sans accès réseau), 5 dans `TrainingManagerPrepareOnetrainerConfigTest` (rejet avant toute matérialisation du Dataset, aucune configuration écrite, aucun Job créé, message actionnable), 2 dans `TrainingPageDirtyStateTest` (interaction réelle avec l'invariant Mission 105 : formulaire dirty → sauvegarde réelle → validation → arrêt avant tout Job, sans jamais écraser une configuration existante). `test_training_roundtrip.py` complet **184/184**, suite complète **2063/2063**, `git diff --check` clean.

Pendant l'implémentation, deux gaps latents ont été mis au jour et corrigés strictement côté test (convention M091, aucun changement de production) : une trentaine de fixtures pré-existantes utilisaient une valeur factice `/models/...` — traitée comme un chemin absolu par `os.path.isabs()` sous Windows même sans lettre de lecteur — normalisées en valeurs relatives ; et deux tests de `TrainingPageDirtyStateTest` (Mission 105) n'interceptaient jamais `QMessageBox.information`, un chemin resté invisible jusqu'à ce que cette mission le rende atteignable en échec.

Aucun besoin de smoke Qt réel supplémentaire (politique définie en amont, confirmée a posteriori — voir `docs/missions/MISSION_106.md` §11.5) : la validation ne touche à aucun moteur, et les tests d'intégration exercent déjà des widgets Qt et Managers réels avec des fichiers/dossiers temporaires réels.

### État du projet (Mission 106)

**2063/2063** tests automatisés verts (2047 avant Mission 106 + 16 nets nouveaux), aucune régression. Commit fonctionnel `bac74b6018287fdec6d1411f87ec8f45ba5aee4d` (`Reject Training.base_model_source only when no OneTrainer form could ever use it`), tag `v0.2-mission106`, GitHub Release publiée. Voir `docs/missions/MISSION_106.md` pour le détail complet.

---

## v0.2-mission105 — 2026-09-09

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 105 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 105)

L'audit post-Mission 104 a identifié la friction réelle la plus disruptive restante : `TrainingPage` était la seule Page à saisie manuelle de l'application n'ayant jamais reçu de protection dirty-state (déjà livrée pour `PromptsPage` en Mission 038 et pour `CharactersPage`/`LoRAPage`/`SettingsPage` en Mission 078). Une modification non enregistrée de l'un des 8 paramètres de Training (`base_model_source`, `architecture`, `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `trigger_word`) était silencieusement perdue lors d'un changement de sélection de Training, de Character ou de Workspace — juste avant une opération réelle, consommatrice de GPU.

Un second problème, distinct, est apparu pendant l'audit du contrat de la mission : `TrainingManager.prepare_onetrainer_config()` écrit une configuration OneTrainer totalement découplée des widgets. Un simple enregistrement du formulaire avant Start ne suffisait pas à garantir qu'un `TrainingJob` nouvellement créé utilise réellement les valeurs affichées à l'écran — un enregistrement sans Prepare intercalé pouvait laisser `create_job()` lire une configuration périmée.

`TrainingPage` reçoit désormais le même contrat dirty-state canonique déjà éprouvé ailleurs : un unique drapeau `_dirty` couvrant les 8 paramètres, une séparation nette entre rafraîchissement non destructif (`update_trainings()`) et réinitialisation de contexte réelle (`reset_for_context_change()`), une confirmation Save/Discard/Cancel aussi bien sur un changement réel de Training que sur un changement de contexte Workspace/Character (avec restauration réelle de la sélection précédente sur Cancel), et une confirmation de suppression enrichie lorsque le Training supprimé porte encore un brouillon non enregistré. `TrainingPage.confirm_context_change()` est désormais câblé dans les gardes New Project / Open Project / Close de `MainWindow`, aux côtés du garde d'opération active `confirm_no_active_training()` déjà existant — l'ordre a été vérifié correct dans les deux sens (gardes d'opération active en premier à la fermeture, gardes dirty-state en premier sur New/Open) afin qu'un Cancel ou un refus d'opération active ne laisse jamais un changement de contexte partiel.

Un second drapeau, indépendant — `_config_stale`, volontairement limité à la Présentation/session, jamais un hash, un timestamp ou une validation persistée — suit si le Training persisté a pu changer depuis le dernier Prepare réussi de la session en cours. Prepare et Start enregistrent désormais automatiquement le formulaire s'il est dirty, et Start reprépare en plus automatiquement (en réutilisant `TrainingManager.prepare_onetrainer_config()` tel quel — aucune deuxième voie de génération de configuration n'a été introduite) uniquement lorsque `_config_stale` est vrai. Un formulaire propre et non périmé conserve exactement le comportement historique : aucun appel supplémentaire avant la création d'un Job.

**Zéro modification de `src/domain/`, `TrainingManager` ou `src/engines/`.**

### Tests ajoutés (Mission 105)

**26 tests ciblés nets nouveaux** (2021 → 2047) : 24 dans `TrainingPageDirtyStateTest` couvrant le marquage dirty par widget, le cycle Save/Discard/Cancel sur changement de sélection et de contexte, la confirmation de suppression enrichie, l'invariant Prepare/Start (`_config_stale`), et l'échec de sauvegarde ; 2 dans `TrainingPageJobImportTest` confirmant que la sélection de Job et les callbacks de cycle de vie ne marquent jamais les paramètres dirty ou périmés. **168/168** sans régression sur `test_training_roundtrip.py`, **74/74** tests de gardes `MainWindow` inchangés et non régressés.

**Smoke réel isolé, exécuté par Claude**, avec uniquement `TrainingJobRunner` remplacé (aucun sous-processus ni GPU réel) — chaque `Manager` et chaque widget `TrainingPage` exercé est du code de production réel et non mocké. **26/26** vérifications réussies, démontrant de bout en bout : modifier un champ marque le formulaire dirty ; cliquer sur Start sauvegarde réellement la modification, reprépare automatiquement la configuration OneTrainer, et crée un `TrainingJob` réel dont l'instantané de configuration sur disque contient réellement la nouvelle valeur ; un cycle Save/Discard/Cancel réel sur un changement de sélection de Training (Cancel restaure la sélection Qt précédente et préserve le brouillon ; Discard change et efface les champs ; Save persiste réellement avant de changer) ; un Start propre et non périmé ne déclenche jamais de Prepare supplémentaire ; l'activité de la liste des Jobs et les callbacks de cycle de vie (Missions 100/103) ne marquent jamais les paramètres dirty ou périmés.

### État du projet (Mission 105)

**2047/2047** tests automatisés verts (2021 avant Mission 105 + 26 nets nouveaux), aucune régression. Commit fonctionnel `ef952f50f73349ba2b838714e7f3a042da063805` (`Add dirty-state protection to TrainingPage and guarantee the Prepare/Start config invariant`), tag `v0.2-mission105`, GitHub Release publiée. `TrainingPage` rejoint désormais `PromptsPage`/`CharactersPage`/`LoRAPage`/`SettingsPage` avec une protection dirty-state complète, et l'invariant de session « paramètres affichés → Prepare/Start → configuration réellement utilisée » est garanti sans nouvelle voie de configuration. Voir `docs/missions/MISSION_105.md` pour le détail complet.

---

## v0.2-mission104 — 2026-09-08

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 104 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 104)

L'audit post-Mission 103 a identifié une faille réelle, non bloquante mais IMPORTANTE : les quatre sites UI qui appellent `LoRALibraryManager.import_lora()`/`set_thumbnail()` (`LoRAPage.add_to_central_library()`, `LoRAPage.import_to_library_from_disk()`, `LoRAPage.choose_library_thumbnail()`, `TrainingPage.import_selected_job_to_library()`) transmettaient `ApplicationSettings.lora_library_path` sans aucune validation. Une valeur vide ou blanche se résolvait silencieusement en `Path("") / lora_id`, un chemin relatif au répertoire de travail du processus — produisant un faux succès complet : la copie réussissait, une entrée `LoRA` était créée, `LORA_LIBRARY_IMPORTED` était publié et un message de succès était affiché, alors que le fichier atterrissait hors de tout emplacement réellement configuré par l'utilisateur.

Un unique garde-fou partagé, `resolve_lora_library_root()` (`src/utils/lora_library_path.py`), Qt-free et sans effet de bord, rejette désormais `""` et toute valeur dont `.strip()` est vide, avec un message actionnable renvoyant vers Réglages. Il ne crée jamais de dossier et ne duplique aucune validation déjà correctement gérée par `LoRALibraryManager`/`WorkspaceStorage` — un chemin syntaxiquement valide mais pas encore existant reste accepté sans changement (bootstrap par `mkdir(parents=True)`, comportement historique). Placé dans `src/utils/` plutôt que `src/engines/` (validation sans rapport avec un moteur backend, malgré le précédent `onetrainer_launch.py`) ou `src/services/` (dépendance UI → Services interdite par le Blueprint).

**Zéro modification de `src/domain/`, `LoRALibraryManager`, `ApplicationSettingsManager`, `SettingsPage` ou `InferencePage`.**

### Tests ajoutés (Mission 104)

**13 tests ciblés nets nouveaux** (2008 → 2021) : 5 dans `ResolveLoraLibraryRootTest` (chaîne vide, chaîne blanche, valeur valide, chemin pas-encore-existant accepté, aucun accès disque), 6 répartis sur `LoRAPageAddToCentralLibraryTest`/`LoRAPageCentralLibraryTabTest` couvrant les trois sites `LoRAPage`, 2 dans `TrainingPageJobImportTest` pour le site `TrainingPage`. Chaque test confirme l'absence d'appel à `import_lora()`/`set_thumbnail()`, l'absence d'événement `LORA_LIBRARY_IMPORTED`, l'absence de message de succès, et un répertoire de travail réel inchangé (`set(os.listdir(os.getcwd()))` comparé avant/après).

**Smoke réel isolé, exécuté par Claude depuis un répertoire de travail dédié** (hors dépôt, précaution supplémentaire compte tenu du risque spécifique de cette mission) : `LoRAPage`/`TrainingPage`/`LoRALibraryManager`/`ApplicationSettingsManager` réels et non mockés, registre/Workspace/Bibliothèque entièrement temporaires. Avec `lora_library_path` à `""` puis `"   "`, les deux sites déclenchés (`add_to_central_library()`, `TrainingPage.import_selected_job_to_library()`) ont chacun été bloqués sans écriture, sans événement et sans faux succès, avec le message actionnable affiché ; le répertoire de travail réel de l'architecte est resté identique avant/après. Avec une racine temporaire valide restaurée ensuite, les deux parcours d'import ont réellement fonctionné de bout en bout. **24/24** vérifications réussies.

### État du projet (Mission 104)

**2021/2021** tests automatisés verts (2008 avant Mission 104 + 13 nets nouveaux), aucune régression — y compris **81/81** sur la couverture d'erreurs filesystem déjà existante de `LoRALibraryManager` (destination non-répertoire, permission refusée, échec en cours de copie). Commit fonctionnel `e01aa81145656a4d670bf5ac4f11a85a9ddbda4e` (`Guard Training/LoRA library imports against a blank lora_library_path`), tag `v0.2-mission104`, GitHub Release publiée. Le faux succès identifié par l'audit post-Mission 103 est éliminé sur les quatre sites concernés. Voir `docs/missions/MISSION_104.md` pour le détail complet.

---

## v0.2-mission103 — 2026-09-08

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 103 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 103)

L'audit post-Mission 102 a identifié le dernier trou concret de la chaîne `Images → Dataset/captions → OneTrainer → LoRA → Inference → Images` : un `TrainingJob` réussi produisait bien un `.safetensors` réel, mais celui-ci n'avait aucun chemin découvrable, depuis l'interface, vers la Bibliothèque LoRA centrale — seule une boîte de dialogue de succès ponctuelle affichait un chemin de fichier interne, sans historique de secours si elle était manquée.

`TrainingPage` affiche désormais une liste minimale et persistante des Jobs du Training sélectionné, lue directement depuis la collection déjà persistée `Training.jobs` — aucun nouveau stockage. Chaque Job porte une seule action contextuelle, couvrant quatre états explicites : jamais importé, importé (action désactivée, aucun doublon silencieux possible), entrée de Bibliothèque supprimée (réimport proposé si le fichier source existe toujours) et fichier de sortie manquant (import bloqué, aucune copie tentée). `TrainingManager` gagne `set_job_imported_lora_id(job_id, lora_id)`, avec la même discipline idempotente/rollback que `update_job_state()`. Aucun nouvel événement `EventBus` : `TRAINING_JOB_IMPORTED` a été envisagé puis abandonné avant implémentation faute de consommateur réel — `TrainingPage` connaît déjà le résultat de son propre appel et se rafraîchit directement.

L'import réutilise `LoRALibraryManager.import_lora()` tel quel — aucun nouveau mécanisme physique de stockage LoRA. Une stratégie délibérément non compensatoire gère la frontière entre les deux backends de persistance indépendants concernés : si l'import dans la Bibliothèque réussit mais que la persistance du lien du Job échoue ensuite, l'entrée de Bibliothèque réelle et déjà utilisable n'est jamais annulée — un avertissement explicite (jamais le message de succès normal) informe l'utilisateur qu'une nouvelle tentative créera une entrée distincte, sans fusion automatique.

**Zéro modification de `src/domain/`, `LoRALibraryManager` ou `InferencePage`.** `LORA_LIBRARY_IMPORTED` (déjà publié par `import_lora()`, déjà consommé par `InferencePage.refresh_lora_selector` depuis Mission 102) suffit à rendre un LoRA nouvellement importé immédiatement sélectionnable en Inference, sans redémarrage et sans aucun nouveau code d'intégration.

### Tests ajoutés (Mission 103)

**17 tests ciblés nets nouveaux** (1991 → 2008) : 6 dans `TrainingManagerImportJobToLibraryTest` (job inconnu, persistance du lien, idempotence, rollback sur échec de sauvegarde, non-interférence avec l'état/`final_output_path`, survie à une fermeture/réouverture), 11 dans `TrainingPageJobImportTest` (liste multi-Jobs, Job réussi avec sortie valide importable, Jobs échoués/annulés/inconnus jamais importables, fichier de sortie manquant bloque l'import, import réel créant une entrée de Bibliothèque réelle et persistant `imported_lora_id`, double import empêché tant que l'entrée existe, entrée supprimée affichée comme réimportable, échec d'`import_lora()` laissant le Job inchangé, échec de persistance de `imported_lora_id` après import réussi avertissant sans faux succès, sélection d'un Job non réussi n'activant jamais l'import, disponibilité immédiate du LoRA importé dans le sélecteur Inference).

**Un défaut d'isolation de test a été trouvé et corrigé pendant l'implémentation** : `LoRALibraryManager()` sans `storage_directory` explicite retombe sur le registre réel de la machine — cinq entrées de test jetables y ont été écrites, détectées puis nettoyées (avec une entrée orpheline préexistante du script de smoke v1 de Mission 102). Documenté comme mise en garde permanente dans `docs/PROJECT_CONTEXT.md` pour les futurs tests/scripts touchant `LoRALibraryManager`.

**Smoke réel, exécuté par Claude** : aucun nouvel entraînement OneTrainer, aucune interaction avec le backend ComfyUI. Un vrai fichier `.safetensors` déjà présent sur disque (85 425 204 octets) a été copié — jamais déplacé ni modifié, MD5 identique avant/après — pour représenter la sortie d'un `TrainingJob` réel, marqué `succeeded` via le vrai `TrainingManager`. Le parcours utilisateur complet a été vérifié réellement : ligne de Job affichée comme importable → import réel via la vraie action UI de `TrainingPage` → entrée réelle créée dans la Bibliothèque LoRA centrale (copie identique) → `TrainingJob.imported_lora_id` réellement persisté et relu → nouveau LoRA immédiatement présent et sélectionnable dans `InferencePage`, sans redémarrage → resélection du même Job affichant correctement l'état déjà importé, action désactivée.

### État du projet (Mission 103)

**2008/2008** tests automatisés verts (1991 avant Mission 103 + 17 nets nouveaux), aucune régression, smoke réel réussi de bout en bout. Commit fonctionnel `1f92634d42d55327a0a57f768d22d024bbdea4ad` (`Add Training result import into the Central LoRA Library`), tag `v0.2-mission103`, GitHub Release publiée. Le parcours principal `Images → Dataset/captions → OneTrainer → LoRA → Inference → Images` ne nécessite désormais plus aucune manipulation manuelle de fichiers entre un entraînement réussi et sa disponibilité en Inference. Voir `docs/missions/MISSION_103.md` pour le détail complet.

---

## v0.2-mission102 — 2026-09-08

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 102 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 102)

L'audit post-Mission 101 a identifié un unique blocage réel sur la chaîne `Images → Dataset/captions → OneTrainer → LoRA → Inference → Images` : `GenerationManager` figeait `lora_name`/`lora_strength` une seule fois à la construction de l'application (contrat "no hot reload" de Mission 059), imposant un redémarrage complet d'AI Studio Toolkit pour changer de LoRA entre deux personnages.

Mission 102 ajoute un sélecteur réel sur `InferencePage`, à trois états explicites et jamais confondus : **A** — aucun override (comportement historique, retombe sur le LoRA global de `ApplicationSettings`) ; **B** — "Aucun LoRA" choisi explicitement (`lora_name=""`, ne réintroduit jamais silencieusement le LoRA global) ; **C** — un LoRA réel de la Bibliothèque LoRA centrale choisi (identité conservée par `lora_id`, relu à chaque génération, jamais mis en cache), exposé à ComfyUI à la demande via la primitive déjà existante et déjà idempotente `LoRALibraryManager.expose_to_comfyui()` — aucune nouvelle mécanique de copie/hardlink. `GenerationManager.generate()` et `GenerationWorker` gagnent chacun deux paramètres optionnels par appel (`lora_name`, `lora_strength`), suivant exactement le même pattern que les paramètres déjà introduits par Mission 096 — aucune refonte du Manager. `ComfyUIEngine` n'a nécessité aucune modification : il portait déjà la sémantique `lora_name=""` = "aucun LoRA" avant cette mission. `comfyui_lora_name`/`comfyui_lora_strength` restent inchangés dans Settings, comme valeurs de repli.

**Zéro modification de `src/domain/`, `LoRALibraryManager`, `ComfyUIEngine` ou `SettingsPage`** — le périmètre pré-validé par contrat (`docs/missions/MISSION_102.md`) a été strictement respecté.

### Tests ajoutés (Mission 102)

**19 tests ciblés nets nouveaux** (1972 → 1991) : 4 dans `GenerationManagerLoraOverrideTest` (les trois états A/B/C, indépendance de `lora_strength`), 4 dans `GenerationWorkerLoraTest` (transmission conditionnelle `is not None`, y compris chaîne vide non omise), 11 dans `InferencePageLoraSelectorTest` (contenu du sélecteur, sélection/exposition/génération réelle avec un LoRA de la Bibliothèque, changement de LoRA sans redémarrage, retour explicite à "Aucun LoRA" sans jamais réintroduire le réglage global, transmission de la force, activation/désactivation du contrôle de force, blocage propre sur échec d'exposition avec message d'erreur réel affiché, rafraîchissement du sélecteur sur renommage/suppression/import, non-régression d'une génération sans toucher au sélecteur).

**Smoke réel ComfyUI, exécuté deux fois** contre l'installation réelle de l'architecte (`J:\Programmes\ComfyUI`, lancée via ComfyUI Desktop, API réelle sur `http://127.0.0.1:8000`) : la première tentative a révélé un défaut du **script de vérification** (Bibliothèque temporaire placée sur un volume différent de `comfyui_lora_expose_path`, provoquant un refus correct et déjà testé d'`expose_to_comfyui()`, suivi d'un blocage sur une vraie `QMessageBox` modale sans utilisateur présent pour la fermer) — diagnostic confirmé sans aucune modification de code de production. La seconde tentative (script corrigé, Bibliothèque temporaire déplacée sur le même volume, garde anti-dialogue ajoutée) a réussi intégralement, 3/3 : génération réelle sans LoRA (`lora_name=""`, 363 750 octets), génération réelle avec un LoRA réel de la Bibliothèque réellement exposé (`lora_name` = alias exposé, `lora_strength=0.65`, 310 226 octets), retour réel à "Aucun LoRA" **sans redémarrage** d'AI Studio Toolkit (`lora_name=""`, 311 976 octets, jamais le LoRA global de Settings). Artefacts de smoke nettoyés, installation ComfyUI de l'architecte confirmée restaurée à son état exact d'origine.

### État du projet (Mission 102)

**1991/1991** tests automatisés verts (1972 avant Mission 102 + 19 nets nouveaux), aucune régression, smoke réel ComfyUI 3/3. Commit fonctionnel `bbe6991df6c0f6d5cc29992ad272168c4b63f760` (`Add dynamic LoRA selection to Inference from the Central LoRA Library`), tag `v0.2-mission102`, GitHub Release publiée. AI Studio Toolkit permet désormais de choisir et de changer un LoRA appliqué à une génération réelle, directement depuis `InferencePage`, sans jamais redémarrer l'application. Quatre besoins futurs identifiés pendant cette mission restent explicitement hors périmètre et non priorisés : lancement automatique du backend ComfyUI, sélection graphique de répertoires pour les chemins ComfyUI de Settings, réorganisation de `SettingsPage`, amélioration UX de l'import des sidecars `.txt` de caption — voir `docs/missions/MISSION_102.md` §11.5 et `docs/PROJECT_CONTEXT.md`. Voir `docs/missions/MISSION_102.md` pour le détail complet.

---

## v0.2-mission101 — 2026-09-08

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 101 — commit, tag et Release sont déjà tous réels au moment de la rédaction. **Cette mission n'est pas un correctif de code** : aucun changement de `src/` ni de `tests/` n'est conservé au final ; son résultat substantiel est la preuve réelle d'un premier entraînement OneTrainer réussi de bout en bout, documentée ici et dans `docs/missions/MISSION_101.md`.

### Résumé (Mission 101)

L'audit post-Mission 100 n'ayant identifié aucun blocage de code entre AI Studio Toolkit et un premier entraînement OneTrainer réel, Mission 101 n'a construit aucune nouvelle capacité — elle a exécuté, sous une série d'autorisations ponctuelles explicites, le premier run réel et corrigé uniquement ce qui a réellement échoué (« observer d'abord, corriger ensuite sur preuve »).

Quatre tentatives réelles : (1) échec avant tout lancement — `ApplicationSettings.onetrainer_path` non réellement sauvegardé, corrigé par l'architecte dans Settings ; (2) lancement réel, échec GPU — la Quadro P4000 (Pascal, compute capability sm_61) n'est plus supportée par le build `torch==2.12.0+cu130` (CUDA 13.0) installé par OneTrainer ; (3) GPU fonctionnel après correction, un vrai step d'entraînement exécuté avec une vraie loss, puis échec après l'entraînement dû à un bug Windows réel dans `scripts/train_remote.py::close_pipe()` d'OneTrainer (suppression d'un fichier encore ouvert, non fixé en amont) ; (4) **succès complet**.

Deux corrections ont été appliquées, chacune sur preuve et sous autorisation explicite séparée, **exclusivement dans l'installation externe OneTrainer — aucune modification de code AI Studio Toolkit à aucun moment de cette mission** :
- réinstallation, dans le seul venv OneTrainer, de `torch==2.12.0+cu126`/`torchvision==0.27.0+cu126` (mêmes versions, seul le tag de build CUDA change — dernier index PyTorch officiel compilant encore pour l'architecture Pascal) ;
- patch local d'une seule fonction dans `scripts/train_remote.py` (`close_pipe()` referme désormais le handle avant de tenter la suppression du fichier).

Ces deux adaptations sont documentées comme strictement locales à cette machine/installation, jamais comme des règles universelles OneTrainer ni comme une hypothèse à coder en dur dans AI Studio Toolkit.

### Tests ajoutés (Mission 101)

Aucun — aucune modification de `src/` ni de `tests/` du dépôt AI Studio Toolkit à aucun moment de cette mission. Validation entièrement réelle et manuelle : chargement réel du checkpoint SD1.5 (`v1-5-pruned-emaonly-fp16.safetensors`), 1 vrai step GPU exécuté (`loss=0.0664`), epoch complété, sauvegarde finale réellement écrite, `TrainingJob` reconnu `succeeded` par `TrainingManager`/`TrainingJobRunner` — `jobs/<job_id>/output/lora.safetensors` réellement présent, **78 489 976 octets**, vérifié indépendamment sur disque. Aucun OOM, aucune erreur CUDA restante, aucun Cancel déclenché.

### État du projet (Mission 101)

1972/1972 tests automatisés verts (décompte inchangé — Mission 101 ne touche ni `src/` ni `tests/`). Premier entraînement OneTrainer réel réussi de bout en bout depuis AI Studio Toolkit (SD1.5, 1 image, caption minimale, résolution 512, 1 epoch, 1 step, checkpoint réel, Quadro P4000/Pascal/sm_61). Commit et tag de clôture enregistrés dans le commit qui suit immédiatement celui-ci (principe de non-auto-référence, voir `docs/PROJECT_CONTEXT.md`). Le futur diagnostic automatique de compatibilité GPU/PyTorch reste un besoin non prioritaire, non implémenté. Voir `docs/missions/MISSION_101.md` pour le détail complet.

---

## v0.2-mission100 — 2026-09-07

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 100 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 100)

L'audit post-Mission 099 a confirmé que la frontière laissée ouverte par Mission 097 — préparer une configuration OneTrainer sans jamais l'exécuter — restait le point qui bloquait structurellement la promesse produit centrale (produire un LoRA utilisable). Deux audits dédiés, validés par l'architecte avant tout code (architecture générale de l'exécution réelle OneTrainer, puis un audit de verrouillage empirique sans GPU sur les deux protocoles IPC réels — callback et Cancel), ont abouti à un contrat entièrement prouvable avec un faux processus déterministe.

Mission 100 introduit `TrainingJob` (nouveau Domain, `Training`-owned — `Training.jobs: list[TrainingJob]`, un niveau d'imbrication non répertorié parmi les 4 patterns d'ownership déjà établis, audité pour lui-même), créé uniquement au clic Start avec une **copie figée** de la configuration OneTrainer à cet instant précis — un Prepare postérieur ne modifie jamais rétroactivement un Job déjà créé. Un runner `QProcess` (`src/ui/training_job_runner.py`) lance le CLI headless réel d'OneTrainer (`scripts/train_remote.py`) sous l'interpréteur du `venv` OneTrainer, dérivé exclusivement d'`ApplicationSettings.onetrainer_path` (jamais `python_path`, sémantique vérifiée non spécifique à OneTrainer avant implémentation) — le processus principal PySide6 n'importe à aucun moment le runtime interne d'OneTrainer, préservant l'isolation déjà établie. `stdout`/`stderr` (capturés nativement par `QProcess`) deviennent l'unique canal runtime : `callback.pipe` est intégralement abandonné, une contrainte d'identité de classe cross-processus de `pickle` rendant même son usage best-effort dépendant d'un import de la classe interne `TrainProgress` d'OneTrainer dans le processus principal — exactement la frontière refusée pour `TrainCommands` (Cancel). Le Cancel coopératif écrit un `TrainCommands.stop()` picklé dans un `command.pipe` pré-créé (vide) avant le lancement du sous-processus — contrat non négociable, un fichier absent au démarrage du thread lecteur d'OneTrainer le fait sortir définitivement dès sa première itération, vérifié empiriquement — via un petit helper externe (`src/engines/onetrainer_cancel_helper.py`) exécuté sous l'interpréteur OneTrainer, jamais un import direct de `TrainCommands` dans PySide6 ; en cas de non-réponse, `QProcess.terminate()` puis `QProcess.kill()` prennent le relais, avec une vérification de l'état Cancel effectuée avant tout `CrashExit` (une terminaison volontaire étant elle-même rapportée `CrashExit` par Qt). Un close guard (`TrainingPage.is_training_active()`/`confirm_no_active_training()`, précédent direct `InferencePage`/Mission 085) empêche toute fermeture silencieuse pendant un Job `starting`/`running` ; un Job actif retrouvé sans supervision `QProcess` au redémarrage passe à `unknown`, jamais deviné `succeeded`/`failed` sans preuve.

En validant la suite complète après implémentation, un incident natif reproductible `0xC0000374`/`STATUS_HEAP_CORRUPTION` est apparu — bissection rigoureuse (même méthodologie que Mission 099) isolant la cause à un seul fichier, `isolated_test_onetrainer_cancel_helper.py` (renommé depuis `test_onetrainer_cancel_helper.py`), qui n'utilise ni Qt ni `QProcess`, uniquement `subprocess.run()` de la stdlib — confirmant que le déclencheur est la création de tout processus enfant OS après l'accumulation cumulative d'objets Qt déjà caractérisée en Missions 097/099, jamais spécifique à `QProcess`. Un smoke test réel hors harnais (processus Python frais, `QApplication` réelle, runner réel, faux processus déterministe réel, jamais un mock) a confirmé **zéro crash natif** dans l'usage réel du composant. Traitement retenu, sans aucune modification de code de production ni suppression de test : ce fichier reste versionné et continue de vérifier réellement le lancement d'un sous-processus, exclu du motif `test_*.py` de la suite principale par son seul nom, exécuté séparément dans un processus Python frais comme validation obligatoire distincte — dette documentée et bornée, non transformée automatiquement en mission future.

### Tests ajoutés (Mission 100)

- **46 tests ciblés nets nouveaux au total**, dont **42 dans la suite principale monoprocessus** (1930 → 1972) — `TrainingJobDomainRoundTripTest`/`TrainingManagerCreateJobTest`/`TrainingManagerUpdateJobStateTest`/`TrainingManagerHasActiveJobTest`/`TrainingManagerRecoverStaleJobsTest` (`test_training_roundtrip.py`), `test_onetrainer_launch.py` (résolution de l'interpréteur/du script OneTrainer), `test_training_job_runner.py` (`TrainingJobRunnerTest`/`TrainingJobRunnerCancelEscalationTest` — succès/échec/`FailedToStart`/crash natif via `os.abort()`/logs stdout-stderr/Cancel coopératif de bout en bout avec un vrai helper et un vrai `command.pipe`/idempotence de `cancel()`/escalade `terminate()`→`kill()` par appel direct avec `QProcess` espionné) — et **4 dans une piste séparée obligatoire**, `isolated_test_onetrainer_cancel_helper.py`, exécutée dans un processus Python frais, jamais dans la suite principale.
- **Smoke test réel hors GPU (hors harnais unittest) : PASS** — processus Python autonome, `QApplication` réelle, `TrainingJobRunner` réel, faux sous-processus déterministe réel : démarrage, réception `stdout`/`stderr`, terminaison, fermeture propre, tous confirmés.
- **Piste A — suite principale monoprocessus canonique : 1972/1972, exit 0**, 0 `STATUS_HEAP_CORRUPTION`, 0 dialogue bloquant, 0 intervention humaine. **Piste B — `isolated_test_onetrainer_cancel_helper.py` en processus frais : 4/4, exit 0.**

### État du projet (Mission 100)

1972/1972 tests automatisés verts (Piste A) + 4/4 verts (Piste B, processus séparé obligatoire) + smoke réel hors GPU PASS. Commit fonctionnel `531f10fb731434b495ab088b8cd5424d2fe250c5` (`Add Training execution foundation (TrainingJob, QProcess runner, Cancel protocol)`), tag `v0.2-mission100`, GitHub Release publiée. AI Studio Toolkit peut désormais réellement lancer, suivre (stdout/stderr), annuler et récupérer l'état d'un Job OneTrainer — **aucun entraînement OneTrainer réel et aucun usage GPU n'ont eu lieu à aucun moment de cette mission** ; l'exécution réelle reste différée à une mission future, sans en présumer le périmètre automatique. La dette de harnais `STATUS_HEAP_CORRUPTION`-via-création-de-sous-processus est caractérisée et bornée (isolation du test concerné, jamais une correction de production) — voir `docs/missions/MISSION_100.md` §17bis. Voir `docs/missions/MISSION_100.md` pour le détail complet.

---

## v0.2-mission099 — 2026-09-07

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 099 — commit, tag et Release sont déjà tous réels au moment de la rédaction. **Cette mission n'est pas un correctif Qt** : aucun changement de `src/` ni de `tests/` n'est conservé au final ; son résultat substantiel est une caractérisation et un bornage de dette, documentés ici et dans `docs/missions/MISSION_099.md`.

### Résumé (Mission 099)

L'audit post-Mission 098 a retenu la dette de harnais de test Qt documentée depuis Mission 097 (`docs/missions/MISSION_097.md` §12.5 : un drift de `QApplication.topLevelWidgets()` mesuré à `+16` net sur 126 tests réels construisant une `MainWindow`) comme candidat de Mission 099, avec un cadrage explicitement révisé par l'architecte : ne pas présumer qu'il s'agit d'une « fuite Qt » au sens strict avant d'en avoir établi la cause par la preuve — démarche `audit ciblé → preuve de la cause → correctif minimal → validation`.

L'audit a isolé deux mécanismes indépendants. Le premier, dominant (~93 % du drift mesuré), est une rétention structurelle par `unittest.TestSuite` : les 9 fichiers `test_main_window_*`/`test_dashboard_page.py`/`test_main_toolbar.py` stockent `self.window = MainWindow()` sans jamais vider l'attribut, et `TestSuite` garde toute instance `TestCase` vivante jusqu'à la fin du run entier — maintenant tout le graphe `MainWindow` atteignable côté Python, donc jamais détruit côté C++, pendant toute la durée de la suite. Le second (~7 % résiduel) est une particularité native PySide6/Qt reproduite avec zéro ligne de code du projet, autour de `QMainWindow.setMenuBar(QMenuBar externe)`, orpheline après destruction du wrapper Python parent — non corrigible par `deleteLater()` (aggrave au contraire, cohérent avec un rejet déjà documenté en Mission 097). Les 8 `QFrame` autrefois inexpliqués dans `topLevelWidgets()` ont été définitivement élucidés comme les popups internes de 8 `QComboBox` réels de l'application, correctement parentés — aucun défaut de parenté de production.

Un correctif minimal (libération explicite de `self.window` après les cleanups Qt existants, 13 lignes sur 6 fichiers, ordre LIFO vérifié) a été implémenté et validé sur cible (126/126 tests ciblés, safety net Qt 7/7). Validé ensuite avec le runner canonique du projet (`python -m unittest discover`) à l'échelle de la suite complète, il a déclenché une terminaison native reproductible confirmée comme `0xC0000374`/`STATUS_HEAP_CORRUPTION` (code de sortie réel obtenu via PowerShell) — jamais observée sur le sous-ensemble ciblé de 126 tests. Un diagnostic différentiel rigoureux (isolation hors `unittest`, réduction de préfixe, comparaison canonique vs harnais manuel) n'a pas expliqué le mécanisme exact mais a établi sans ambiguïté, par rollback exact et comparaison directe, que ce correctif est l'élément déclencheur/amplificateur du crash à l'échelle de la suite complète. **Le correctif a donc été intégralement rejeté et retiré** ; la rétention actuelle est acceptée comme dette de harnais mieux maîtrisée qu'un correctif dont le risque démontré (corruption mémoire native) est strictement supérieur au problème qu'il résout.

### Tests ajoutés (Mission 099)

Aucun — décompte de tests inchangé (1930 avant et après). Le code de test a été modifié pendant l'investigation (13 lignes sur 6 fichiers) puis intégralement revenu à l'état exact d'avant Mission 099 après rejet du correctif (`git diff` vide sur les 9 fichiers concernés). Validation finale : 126/126 tests ciblés OK, safety net Qt 7/7 OK, suite complète monoprocessus canonique **1930/1930, exit 0**, 0 `STATUS_HEAP_CORRUPTION`, 0 dialogue bloquant, 0 intervention humaine — sur le code de test revenu à la baseline.

### État du projet (Mission 099)

1930/1930 tests automatisés verts (décompte inchangé). Commit documentaire substantiel `199e7b8d72a40bb0dedb711aeefd418843d51118` (`docs: characterize Qt test harness lifecycle debt`) — exceptionnellement pas un commit fonctionnel, aucune modification de `src/` ni de `tests/` n'étant conservée — tag `v0.2-mission099`, GitHub Release publiée. La dette Qt du harnais de test est désormais considérée caractérisée et bornée : toute tentative future de `self.window = None`, `deleteLater()`, ou nettoyage agressif équivalent ne doit pas être retentée sans élément technique nouveau (nouvelle version de PySide6/Qt, nouvelle preuve isolant précisément le mécanisme de corruption mémoire). Aucun entraînement OneTrainer réel n'a été lancé à aucun moment de cette mission. Voir `docs/missions/MISSION_099.md` pour le détail complet.

---

## v0.2-mission098 — 2026-09-07

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 098 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 098)

L'audit post-Mission 097 a identifié un besoin réel documenté au Blueprint depuis l'origine mais jamais implémenté : `docs/blueprint/04_DOMAIN_MODEL.md` §7 liste "Store captions"/"Caption Count"/"Captions" comme enfant structurel du Dataset, jamais concrétisé. Ce besoin est directement synergique avec ce que Mission 097 venait de livrer : `TrainingManager._materialize_concept()` écrivait le **même** `trigger_word` sur chaque image d'un concept OneTrainer matérialisé, explicitement documenté comme minimum fonctionnel provisoire. Un mini-audit contractuel dédié, puis une révision demandée par l'architecte sur l'arbitrage architectural exact, ont verrouillé le contrat avant toute implémentation : une caption appartient à l'association Dataset ↔ Image (jamais à l'`Image` globale, la même image pouvant appartenir à plusieurs Datasets avec des objectifs différents), dans l'esprit d'une future structure `DatasetEntry`/`DatasetItem`.

Mission 098 introduit `DatasetEntryMetadata` (`caption: str = ""`) et `Dataset.entries: dict[image_id, DatasetEntryMetadata]`, une collection additive strictement distincte de `Dataset.images` — dont le contrat historique reste intégralement inchangé, aucune migration requise pour un `project.json` antérieur (`entries` absent se recharge en `{}`). Cette structure est explicitement établie comme le seul emplacement futur pour toute métadonnée par image propre à un Dataset (jamais une nouvelle collection parallèle). La distinction entre **caption absente** (pas d'entrée — repli sur `trigger_word`) et **caption explicitement vide** (entrée présente avec `caption == ""` — jamais remplacée) est strictement respectée, y compris dans le matérialiseur OneTrainer (`metadata = dataset.entries.get(image.image_id)` puis `caption = metadata.caption if metadata is not None else training.trigger_word` — jamais `caption or training.trigger_word`, qui aurait conflaté les deux cas). L'import d'images depuis le disque détecte désormais automatiquement un sidecar `.txt` de même nom pour préremplir la caption (`detect_caption_sidecars: bool = False`, désactivé par défaut, activé uniquement par l'import disque — jamais par l'ajout depuis la galerie du Workspace). `DatasetsPage` gagne un panneau de caption éditable (affichage/édition/sauvegarde par image sélectionnée), avec le même contrat dirty-state (Save/Discard/Cancel) déjà établi par `LoRAPage`, et un indicateur visuel de présence de caption sur chaque miniature.

### Tests ajoutés (Mission 098)

- **41 tests ciblés nets nouveaux** (1889 → 1930) : `test_dataset_roundtrip.py` (+24 — 9 round-trip Domain `DatasetEntryMetadata`, 15 `DatasetManagerCaptionTest` couvrant `set_caption()`, le nettoyage d'entrée par `remove_images()`, et la détection sidecar présente/vide/absente/désactivée par défaut/rollback) ; `test_training_roundtrip.py` (+3 — caption explicite prioritaire, caption explicitement vide jamais remplacée, captions mixtes au sein d'un même Dataset) ; `test_datasets_page.py` (+14 — panneau de caption réel, dirty-state Save/Discard/Cancel sur changement de sélection, caption explicitement vidée puis sauvegardée restant vide après reselection).
- **Smoke test Qt réel PASS (18/18 assertions)** — widgets réels (`QMessageBox.exec()` seul stubbé pour éviter un blocage modal) : sélection, affichage/édition/sauvegarde de caption, indicateur de présence, Save/Discard/Cancel au changement de sélection.
- **Smoke test filesystem réel PASS (9/9 assertions)** — disque temporaire réel : caption récupérée depuis un sidecar à l'import disque, aucune caption créée sans sidecar, le sidecar `.txt` jamais traité comme une image, matérialisation Training correcte dans les trois cas (caption explicite, absence → `trigger_word`, caption explicitement vide → fichier vide).
- **Deux suites complètes monoprocessus consécutives : 1930/1930 OK les deux fois**, 0 crash natif, 0 dialogue bloquant, 0 intervention humaine.

### État du projet (Mission 098)

1930/1930 tests automatisés verts. Commit fonctionnel `a56a46cd6dd9c4ae483f7915f163bb35cdd55f7f` (`Add per-image, per-Dataset captions (DatasetEntryMetadata)`), tag `v0.2-mission098`, GitHub Release publiée. Aucun entraînement OneTrainer réel n'a été lancé à aucun moment de cette mission. Restent explicitement hors périmètre, enregistrés comme besoins futurs : génération de captions par IA (import/validation/correction), stratégies de captions selon le moteur d'entraînement cible, évolution éventuelle de `DatasetEntryMetadata` vers une structure plus riche, et la miniature de Prompt dans la future Prompt Library (besoin déjà validé par l'architecte, sans rapport avec ce périmètre). Voir `docs/missions/MISSION_098.md` pour le détail complet.

---

## v0.2-mission097 — 2026-09-04

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 097 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 097)

L'audit post-Mission 096 a établi que `Training` restait un CRUD pur (3 champs scalaires, `create`/`select`/`update_name`/`delete`, aucune exécution, aucun moteur), alors qu'Inference dispose désormais d'une chaîne réellement opérationnelle jusqu'à ComfyUI. Un mini-audit architectural Training a comparé les moteurs envisageables et recommandé OneTrainer comme premier moteur cible ; un second mini-audit, portant spécifiquement sur le format OneTrainer réellement observé sur l'installation locale (`J:\Programmes\Onetrainer\`, lecture seule), a verrouillé le contrat exact avant toute implémentation — y compris un mécanisme de migration de version non anticipé, découvert seulement pendant le smoke test réel (`BaseConfig.from_dict()` rejoue toutes les migrations enregistrées si la clé `"__version"` est absente, ce qui échoue contre un JSON volontairement minimal).

Mission 097 prépare le véritable pipeline Training — **contrat de données, traducteur OneTrainer, matérialisation du dataset, validation structurelle réelle — sans encore lancer OneTrainer**, évitant délibérément toute UX intermédiaire vouée à être remplacée dès la mission suivante. `Training` (Domain) gagne 7 champs génériques (`base_model_source`, `architecture` — `SD15`/`SDXL`/`FLUX`, jamais l'enum OneTrainer —, `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `trigger_word`), tous à défaut sûr pour compatibilité stricte avec tout `project.json` existant. Un nouveau module pur `src/engines/onetrainer_config.py` traduit ce contrat générique vers le dict `TrainConfig` réel (mapping fermé à 3 entrées architecture → `ModelType`, valeurs par défaut tracées champ par champ contre les presets LoRA officiels réellement inspectés) et injecte `"__version": _AUDITED_CONFIG_VERSION` (= 10, le `config_version` réellement observé sur l'installation auditée — documenté comme spécifique à cette installation, pas une constante universelle). `TrainingManager.prepare_onetrainer_config()` orchestre la matérialisation réelle du Dataset actif en un concept OneTrainer (`ConceptConfig.path` = un dossier unique) : copies physiques déterministes vers `training/<training_id>/concept/` (jamais de modification des sources), nommage sans collision via `resolve_collision_free_name()` déjà existant, un sidecar `.txt` par image copiée contenant `trigger_word` (captioning minimum fonctionnel explicitement documenté comme provisoire). Aucun chemin absolu n'est jamais stocké dans `Training` — tout se dérive de `Workspace.root` et de `training_id`. `TrainingPage` reçoit les nouveaux champs regroupés dans un `QFormLayout` (pattern déjà établi ailleurs dans le projet) et une action de préparation, sans aucun bouton « Lancer l'entraînement ».

Un incident natif intermittent (`STATUS_HEAP_CORRUPTION`, Windows) a été rencontré pendant la validation de la suite complète, investigué en profondeur : isolation différentielle A/B/C a établi le corrélat comme le poids brut d'objets Qt ajouté par la nouvelle `TrainingPage` (19 → 75 objets `QObject` descendants), indépendant de la nature des champs ou du câblage de signal. Un amplificateur indépendant et préexistant a été identifié et supprimé (le polling périodique 15ms du safety net Qt de test, Mission 091 — l'`eventFilter` + fermeture différée suffisent seuls). Une anomalie ciblée supplémentaire — un plantage reproductible spécifique à une seule classe de test, lié à l'ordre d'armement du safety net avant construction de `MainWindow` — a été corrigée par un réordonnancement minimal et strictement localisé (LIFO de nettoyage préservé), validé 0/3 → 5/5 propre en isolation, **non généralisé** aux autres classes partageant le même ordre faute de preuve de plantage sur celles-ci. Une fuite de fenêtres Qt préexistante en harnais de test (drift `+16`/126 tests, strictement identique en baseline et en Mission 097 complète) a été investiguée séparément et actée comme dette non résolue, non introduite par cette mission — deux tentatives de correction (`Qt.WA_DeleteOnClose`, un helper `deleteLater()` tests-only) ont été explorées et rejetées après preuve empirique qu'elles n'apportent aucune amélioration.

### Tests ajoutés (Mission 097)

- **44 tests ciblés nets nouveaux** (1845 → 1889) : `test_training_roundtrip.py` (+28 — exact-shape mis à jour pour les 7 nouveaux champs, trois nouvelles classes couvrant les paramètres UI OneTrainer, `TrainingManager.update()`, et `prepare_onetrainer_config()` avec matérialisation réelle sur disque temporaire, collision de noms provoquée délibérément et vérifiée résolue, et une vérification explicite que le Manager n'importe jamais OneTrainer lui-même) ; `test_onetrainer_config.py` (nouveau fichier, 14 tests, dont la présence et la valeur de `"__version"`) ; `test_qt_dialog_safety_net.py` (+2 net — contrat adapté après suppression du polling, 7/7) ; `test_main_window_new_project.py` (0 net — réordonnancement ciblé d'une seule classe).
- **Smoke test réel OneTrainer : 18/18 PASS** — chargement du JSON produit par le Toolkit via le vrai `TrainConfig` de l'installation OneTrainer présente sur cette machine, round-trip sans exception, pour SD15 et SDXL ; FLUX structurellement supporté (mapping trivial) mais non validé sur le GPU actuel (Quadro P4000, 8 Go VRAM). Aucune exécution, aucun `trainer.start()`/`trainer.train()`, aucun sous-processus, aucune modification de l'installation OneTrainer, aucun usage GPU.
- **Couverture complète partitionnée (un processus Python frais par fichier, 41 fichiers) : 1889/1889 OK**, sans regroupement nécessaire, 0 échec, 0 erreur, 0 fichier planté.
- **Deux full suites monoprocessus consécutives (`unittest discover`) : 1889/1889 OK les deux fois**, sans instrumentation temporaire, 0 `STATUS_HEAP_CORRUPTION`, 0 dialogue visible, 0 intervention humaine.

### État du projet (Mission 097)

1889/1889 tests automatisés verts. Commit fonctionnel `0dd44ec787d083ad3b82be5eb8c60b74b9f9421e` (`Add Training contract, OneTrainer configuration adapter, and dataset materialization`), tag `v0.2-mission097`, GitHub Release publiée. Aucun entraînement réel n'a été lancé (aucun `trainer.start()`/`trainer.train()`, aucun sous-processus, aucun usage GPU volontaire) — le lancement réel (`scripts/train.py` en sous-processus), le suivi running/succeeded/failed, la récupération du `.safetensors` produit et son import dans la Bibliothèque centrale restent explicitement hors périmètre, à auditer par la mission suivante sans présumer qu'elle en est le périmètre automatique. Voir `docs/missions/MISSION_097.md` pour le détail complet.

---

## v0.2-mission096 — 2026-09-04

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 096 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 096)

L'audit global de maturité post-Mission 095 a établi, par lecture directe du code, un constat non documenté jusqu'alors : la génération d'image réelle restait, telle quelle depuis la Mission 012, le workflow de démonstration fixe de cette mission — résolution figée à 512×512, `batch_size=1`, `steps=20`/`cfg=8`/`sampler_name="euler"`/`scheduler="normal"` codés en dur, prompt négatif codé en dur (`"text, watermark"`), seed aléatoire non reproductible et jamais retourné à l'appelant. `GenerationManager.generate()` n'acceptait alors que `prompt_text`/`reference_images`/`reference_strength`.

Un mini-audit contractuel préalable a verrouillé, avant toute implémentation, le trajet exact de chaque nouveau paramètre à travers les quatre couches `InferencePage → GenerationManager → ComfyUIEngine → comfyui_workflows`, la stratégie de compatibilité (chaque nouveau paramètre reproduit par défaut la valeur pré-Mission-096 exacte), et trois décisions structurantes : (1) la largeur/hauteur ne s'applique qu'au chemin txt2img — `build_img2img_workflow()` n'a structurellement aucun paramètre largeur/hauteur, les dimensions provenant de l'image de référence via `VAEEncode` — les champs correspondants se désactivent donc automatiquement dès qu'une référence est active ; (2) le batch reste volontairement à 1, le contrat de résultat en attente (Accept/Reject/Regenerate, Missions 014/084/085) étant structurellement mono-résultat — le multi-image est documenté comme extension future distincte, non entamée ; (3) aucune persistance nouvelle — chaque paramètre suit le précédent déjà établi par `reference_strength` (état local `InferencePage`, jamais écrit dans `ApplicationSettings` ni le Workspace).

Mission 096 rend ainsi Inference réellement configurable : résolution libre 64–2048 (validée multiple de 8, contrainte technique réelle du VAE, jamais une simple limite arbitraire), steps/CFG ajustables, sampler/scheduler découverts dynamiquement depuis le serveur ComfyUI réel (`GET /object_info/KSampler`, jamais une liste codée en dur — même mécanisme déjà éprouvé par `list_checkpoints()`/`list_loras()`, avec repli gracieux et timeout court dédié si ComfyUI est injoignable), prompt négatif éditable (valeur initiale rétrocompatible), et deux modes de seed explicites (aléatoire/fixe) — dans les deux cas, `InferencePage` résout elle-même la valeur concrète avant soumission et l'affiche immédiatement après lancement, permettant d'afficher "le seed réellement utilisé" sans changer le type de retour de `generate_image()`. Deux écarts techniques ont été nécessaires et documentés : un `QLineEdit` (pas `QSpinBox`, limité à un entier 32 bits signé) pour couvrir la plage complète `0..2**32-1` du seed fixe, et un paramètre `timeout` optionnel ajouté à `ComfyUIEngine._request_json()`/`list_samplers()`/`list_schedulers()` pour qu'un rafraîchissement sampler/scheduler ne gèle jamais l'UI jusqu'au timeout de génération (120s) si ComfyUI est injoignable.

Un incident environnemental a été diagnostiqué pendant la validation — un crash natif `STATUS_HEAP_CORRUPTION` reproductible lors de l'exécution isolée de `test_main_window_new_project.py` via `unittest discover` — et confirmé pré-existant et sans rapport avec cette mission : reproduit à l'identique sur le code de base (`git stash` des changements M096, même commande, même point de crash), correspondant à l'aléa d'environnement natif Qt/PySide6 déjà documenté depuis les Missions 063-069+. Ne s'est manifesté à aucun moment pendant les deux suites complètes finales.

### Tests ajoutés (Mission 096)

- **459 tests ciblés nets nouveaux/étendus** répartis sur 8 fichiers : `test_comfyui_workflows.py` (paramètres forwardés aux bons nœuds, asymétrie txt2img/img2img sur largeur/hauteur), `test_comfyui_engine.py` (`list_samplers()`/`list_schedulers()`, forwarding `generate_image()`), `test_generation_manager.py` (passthroughs de découverte, normalisation d'erreur, forwarding inconditionnel des nouveaux paramètres), `test_generation_worker.py` (inchangé, confirmé compatible sans modification), `test_inference_page.py` (nouvelle classe `InferencePageGenerationParametersTest`, 28 tests : validation résolution, activation/désactivation largeur-hauteur selon référence, seed aléatoire/fixe, sémantique Regenerate, découverte et repli gracieux sampler/scheduler), et 3 fixtures `test_main_window_*.py` mises à jour pour accepter les nouveaux kwargs forwardés (aucun comportement testé changé).
- **Smoke test Qt réel (widgets réels) : 25/25 PASS** — changement de résolution, changement des paramètres avancés, seed fixe/aléatoire (Regenerate inclus), activation/désactivation largeur-hauteur à l'ajout/retrait réel d'une référence, rejet réel d'une résolution invalide, découverte sampler/scheduler et son repli.
- **Deux full suites consécutives (`unittest discover`) : 1845/1845 OK** (209.5s puis 212.0s), sans instrumentation temporaire, 0 dialogue visible, 0 intervention humaine.
- **Smoke test ComfyUI réel : 16/16 PASS**, contre l'instance de l'architecte (redémarrée manuellement après un plantage au premier lancement, anomalie externe non traitée) — découverte sampler/scheduler réelle confirmée conforme, génération txt2img réelle avec valeurs non par défaut (576×704, seed vérifié via les métadonnées PNG natives de ComfyUI), génération img2img réelle confirmant que les dimensions de sortie proviennent exactement de l'image de référence (384×576), et **constat empirique déterminant** : une résolution non multiple de 8 (513×513) soumise directement à ComfyUI n'est **pas rejetée** par son API — elle est acceptée puis silencieusement arrondie à 512×512 lors de l'exécution, confirmant que la validation stricte côté Toolkit n'est pas une simple précaution UX mais une nécessité réelle. Nettoyage complet effectué (artefacts `output/`, file d'attente vérifiée vide), backend confirmé sain après coup.

### État du projet (Mission 096)

1845/1845 tests automatisés verts. Commit fonctionnel `8121904140985396e85fa369b343f45599a0803e` (`Add real generation parameters to Inference (width/height/steps/CFG/sampler/scheduler/seed/negative prompt)`), tag `v0.2-mission096`, GitHub Release publiée. Batch multi-image, persistance des paramètres de génération, et l'anomalie externe de premier démarrage de ComfyUI Desktop restent explicitement hors périmètre. Voir `docs/missions/MISSION_096.md` pour le détail complet.

---

## v0.2-mission095 — 2026-09-03

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 095 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 095)

L'audit post-Mission 094 avait établi, par preuve directe (code + `/system_stats` réel + tests empiriques contre l'installation ComfyUI Desktop réelle de l'architecte), que la bibliothèque LoRA centrale (Missions 087–093), mature côté stockage/CRUD, restait totalement déconnectée de la sélection LoRA réellement utilisée en génération : `SettingsPage.comfyui_lora_name_edit` est peuplé exclusivement par `ComfyUIEngine.list_loras()` (découverte serveur, Mission 059), sans aucune référence à `LoRALibraryManager`. Une relecture critique du contrat initial par l'architecte a identifié deux angles morts avant toute implémentation : une contradiction interne entre « dossier d'exposition dédié », « alias plat sans préfixe » et « aucune modification de configuration ComfyUI » (ces trois propriétés ne peuvent pas coexister), et l'absence d'un contrat explicite de cycle de vie des hardlinks — un hardlink n'est pas supprimé automatiquement avec la source, un nettoyage incomplet laisse des données physiquement présentes et toujours visibles par ComfyUI.

Mission 095 comble ce fossé via un mécanisme d'exposition par hardlink NTFS (`os.link()`, aucune duplication physique, aucun privilège élevé requis), validé empiriquement sur l'installation réelle de l'architecte. `LoRALibraryManager` gagne deux méthodes symétriques : `expose_to_comfyui(lora, expose_root)` et `unexpose_from_comfyui(lora, expose_root)`. Le hardlink est créé dans un sous-dossier fixe et non configurable `AIStudioToolkit\`, à l'intérieur d'une racine `loras` **déjà déclarée** à ComfyUI par l'architecte (`ApplicationSettings.comfyui_lora_expose_path`, nouveau champ, `""` par défaut — aucune racine n'est jamais déclarée automatiquement par le Toolkit). Le nom d'alias est déterministe et robuste au renommage : `<slug(lora.name)>__<lora_id_complet>.<ext>`, recherche systématiquement par UUID complet (jamais tronqué, jamais recalculé à partir du nom courant) — un renommage entre deux expositions ne fait donc jamais perdre l'alias existant. L'exposition est strictement idempotente (`os.path.samefile()`), refuse explicitement toute collision avec un fichier existant différent (jamais d'écrasement), vérifie une contrainte de même volume NTFS avant toute opération disque (erreur explicite, aucun repli automatique par copie/symlink), et exige une cardinalité strictement égale à un fichier modèle (`len(lora.files) == 1`, refus explicite — jamais un `files[0]` implicite). `LoRAPage.delete_from_library()` appelle désormais `unexpose_from_comfyui()` avant `LoRALibraryManager.delete()` et **bloque** la suppression si ce retrait échoue, empêchant toute suppression d'entrée canonique de laisser un alias ComfyUI orphelin référencer encore les données physiques — invariant confirmé structurellement garanti par audit exhaustif des appelants de `delete()` (`LoRAPage` en est l'unique appelant applicatif). Une fois exposée, une entrée devient immédiatement sélectionnable via le mécanisme `SettingsPage.refresh_loras()`/`ComfyUIEngine.list_loras()` déjà existant depuis Mission 059 — aucun changement à `SettingsPage`, `GenerationManager` ni `LoRA.files`.

Un incident de harnais de test a été rencontré et corrigé pendant le développement : 3 tests de la nouvelle classe UI appelaient l'action d'exposition sans mocker `QMessageBox`, provoquant un blocage sur une vraie boîte de dialogue — corrigé par mock explicite des 3 appels et armement du filet de sécurité Mission 091 sur toute la classe (défense en profondeur), avec une preuve dédiée ajoutée ; le comportement de production (confirmation réelle affichée à l'architecte) reste strictement inchangé.

### Tests ajoutés (Mission 095)

- **21 tests** `LoRALibraryManagerComfyUIExposureTest` (`test_lora_library_roundtrip.py`) couvrant chaque ligne de la table de décision d'exposition/retrait : hardlink réel sur disque, idempotence, ré-exposition après renommage, collision refusée, volumes incompatibles, cardinalité 0/>1, `unexpose` normal/absent/alias-correct/alias-erroné (jamais supprimé arbitrairement).
- **10 tests** `LoRAPageComfyUIExposureTest` (`test_lora_roundtrip.py`) couvrant l'action UI, l'orchestration suppression→`unexpose` (bloquante en cas d'échec), et une preuve dédiée du filet de sécurité Mission 091.
- Assertions étendues dans les suites `ApplicationSettings`/`SettingsPage` existantes pour le nouveau champ `comfyui_lora_expose_path` (défauts, round-trip, idempotence du `update()`, UI, persistance).
- Non-régression ciblée (`test_lora_library_roundtrip.py`, `test_lora_roundtrip.py`, `test_application_settings_roundtrip.py`, suites `SettingsPage`/`ComfyUI`/`Ollama` liées) : **456/456 OK**.
- Smoke test réel contre l'instance ComfyUI démarrée manuellement par l'architecte (`127.0.0.1:8000`, jamais lancée/redémarrée/fermée par l'agent) : entrée centrale de test isolée → exposition → alias confirmé via `ComfyUIEngine.list_loras()` sans redémarrage → retrait → disparition confirmée → racine ComfyUI réelle strictement restaurée. **PASS**.
- **Deux full suites consécutives, sans instrumentation temporaire** : **1771/1771 OK** puis **1771/1771 OK** — 0 dialogue visible, 0 intervention humaine, aucun processus Qt/Python résiduel.
- `git diff --check` : propre.

### État du projet (Mission 095)

1771/1771 tests automatisés verts. Commit fonctionnel `50eea64` (`Add ComfyUI exposure for the central LoRA library via NTFS hardlink`), tag `v0.2-mission095`, GitHub Release publiée. Bibliothèque centrale LoRA désormais réellement exposable et sélectionnable en génération via ComfyUI ; modèle de scopes Character/Workspace/Global, support d'un moteur autre que ComfyUI, et mise à jour automatique d'un alias lors d'un renommage restent explicitement hors périmètre. Voir `docs/missions/MISSION_095.md` pour le détail complet.

---

## v0.2-mission094 — 2026-09-03

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 094 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 094)

L'audit post-Mission 093 avait identifié, avec preuve directe et reproductible (5 occurrences, 100 % reproductibles sur 3 exécutions instrumentées), un défaut structurel du harness de test distinct de tout comportement applicatif : `MainWindowInferencePendingResultGuardTest`/`MainWindowRenamePendingResultGuardTest` mockaient `InferencePage._confirm_pending_before_switch()` uniquement à l'intérieur d'un bloc `with patch.object(...)` scopé au corps du test. Pour les 5 scénarios (3 + 2, sur les deux classes) où `_pending_path` reste intentionnellement non-`None` en fin de test (Cancel, échec de persistance), `self.addCleanup(self.window.close)` — enregistré en premier dans `setUp()` — s'exécutait après la sortie de ce bloc et retombait sur un `MainWindow.closeEvent()` réel et entièrement démocké, affichant la vraie `QMessageBox` « Génération en attente » — l'incident observé à deux reprises par l'architecte (Missions 092 et 093).

Un mini-audit ciblé a confirmé, par lecture directe du code, que `confirm_pending_result_change()` vérifie `self._pending_path is None` comme toute première instruction et retourne `True` sans aucun dialogue si c'est le cas — `_pending_path = None` est donc strictement nécessaire et suffisant pour neutraliser le guard. Il a également établi que l'ordre LIFO des `addCleanup()` d'`unittest` garantit qu'un cleanup enregistré pendant le corps du test s'exécute avant celui enregistré plus tôt dans `setUp()` — et découvert que le correctif primaire existait déjà, éprouvé, dans les mêmes fichiers : `addCleanup(setattr, self.window.inference_page, "_dirty", False)`, utilisé pour le guard-frère de Mission 083 (`MainWindowInferencePromptGuardTest`), jamais répliqué pour `_pending_path` — un oubli localisé, pas un mécanisme à inventer.

Mission 094 applique ce même correctif (`addCleanup(setattr, ..., "_pending_path", None)`) aux exactement 5 tests concernés, et arme en défense en profondeur le filet de sécurité Mission 091 (`start_dialog_guard()`/`stop_dialog_guard()`, patron déjà validé par 4 classes existantes) sur les deux classes entières — avec des responsabilités explicitement distinctes : le cleanup est le correctif qui rend ces tests réellement corrects, le filet n'existe que comme garde-fou contre une régression future, jamais comme substitut. Deux preuves dédiées par classe complètent le contrat : l'une reproduit la séquence défaillante exacte avec `QMessageBox` patché pour démontrer que le guard réel n'est jamais atteint après cleanup, l'autre déclenche volontairement un dialogue réellement inattendu pour démontrer que le filet le transforme en échec propre plutôt qu'en blocage. Recherche exhaustive confirmée : aucune 6ᵉ occurrence cachée n'existe ailleurs dans la suite (`MainWindowCloseEventOrchestrationTest`, `MainWindowCloseEventRealStateTest` et `test_inference_page.py` sont structurellement sûrs par construction). Mission strictement tests-only — aucun changement `src/`, aucune modification du comportement applicatif réel du guard Mission 084.

### Tests ajoutés (Mission 094)

- **4 tests dédiés nets nouveaux** (2 par classe) : preuve du lifetime gap (`test_pending_cleanup_prevents_real_dialog_reaching_close`) et preuve du filet (`test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure`).
- Suite ciblée des deux classes : `MainWindowInferencePendingResultGuardTest` **14/14 OK**, `MainWindowRenamePendingResultGuardTest` **7/7 OK**.
- Non-régression ciblée (5 fichiers : les deux classes concernées, `test_main_window_close_event.py`, `test_inference_page.py`, `test_qt_dialog_safety_net.py`) : **229/229 OK**.
- **Deux full suites consécutives, sans aucune instrumentation diagnostique temporaire** (contrairement à la clôture de M093) : **1741/1741 OK** puis **1741/1741 OK** — **0 tentative réelle de « Génération en attente » provenant des 5 chemins précédemment connus, 0 dialogue inattendu, 0 intervention humaine sur les deux exécutions**, aucun processus Qt/Python résiduel constaté ensuite.
- `git diff --check` : propre.

### État du projet (Mission 094)

1741/1741 tests automatisés verts. Commit fonctionnel `6f173ae` (`Fix Mission-084 test-cleanup lifetime gap in pending-result guard tests`), tag `v0.2-mission094`, GitHub Release publiée. Mission strictement tests-only, aucun changement `src/`. Voir `docs/missions/MISSION_094.md` pour le détail complet.

---

## v0.2-mission093 — 2026-09-03

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 093 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 093)

L'audit post-Mission 092, première mission de ce projet assistée par Graphify (utilisé strictement comme couche de navigation, chaque piste vérifiée directement en source), a confirmé une asymétrie UX documentée sans être traitée depuis les Missions 088/089/090 : l'onglet « Bibliothèque centrale » de `LoRAPage` n'offrait aucun moyen de définir ou remplacer une miniature — ni bouton, ni méthode Manager — alors que l'onglet « Personnage » dispose de ce mécanisme depuis la Mission 047, avec nettoyage automatique de l'ancienne miniature depuis la Mission 080.

Un mini-audit contractuel préalable a établi la transposition précise du contrat existant de `LoRAManager.set_thumbnail()` (Missions 047/067/080) vers `LoRALibraryManager`, en l'adaptant délibérément aux conventions propres de ce second Manager plutôt qu'en le copiant à l'identique : là où `LoRAManager.set_thumbnail()` retourne un simple `None` aussi bien pour un `lora_id` inconnu que pour un échec de copie, `LoRALibraryManager.set_thumbnail()` réserve `None` exclusivement au cas « rien ne s'est passé » (entrée inconnue) et lève désormais `LoRALibraryError` pour tout échec réel — cohérent avec `import_lora()`/`update()`/`delete()`, dont la docstring de `import_lora()` documente déjà explicitement cette règle. Le mini-audit a également révélé une contrainte fonctionnelle non anticipée : un rafraîchissement passif via le seul événement `LORA_LIBRARY_UPDATED` (réutilisé tel quel, aucun nouvel événement créé) est structurellement insuffisant pour afficher immédiatement la nouvelle miniature — un garde dirty-state (Save/Discard/Cancel, déjà utilisé par `import_to_library_from_disk()`) doit être résolu avant l'ouverture du sélecteur de fichiers, et un appel explicite à `_display_library_entry()` doit suivre tout succès, exactement pour la même raison déjà rencontrée par Mission 092.

Un nouveau bouton « Choisir une miniature… » a été ajouté à l'onglet central, mirroir d'activation de `delete_from_library_button`. Aucune extension du modèle de scopes Character/Workspace/Global ni de l'exposition aux moteurs.

Pendant la validation, l'architecte a de nouveau observé la vraie `QMessageBox` « Génération en attente » (2ᵉ occurrence, après celle de Mission 092), cette fois jugée suffisamment reproductible pour exiger un diagnostic empirique dédié plutôt qu'un classement en incident résiduel. Une instrumentation temporaire, jamais committée, a établi la cause exacte avec preuve : `MainWindowInferencePendingResultGuardTest`/`MainWindowRenamePendingResultGuardTest` mockent le guard de Mission 084 uniquement à l'intérieur d'un bloc `with patch.object(...)` scopé au corps du test ; pour les scénarios où `_pending_path` reste intentionnellement non-`None`, `addCleanup(self.window.close)` — exécuté après la sortie de ce bloc — retombe sur un `closeEvent()` réel et entièrement démocké. Le filet de sécurité de Mission 091 ne couvre pas ces deux classes (armé uniquement sur 4 classes de la famille Mission 085 « génération active »). Cinq occurrences exactes, aucune n'impliquant un fichier modifié par cette mission — dette explicitement conservée, non corrigée dans cette mission.

### Tests ajoutés (Mission 093)

- **22 tests dédiés nets nouveaux** : 9 (`LoRALibraryManagerSetThumbnailTest`, `test_lora_library_roundtrip.py`) — première miniature, remplacement d'une miniature déjà possédée, garde contre la suppression d'une miniature externe, échec de copie sans mutation, échec de persistance avec rollback complet et nettoyage best-effort, `lora_id` inconnu, événement publié uniquement après succès complet ; 13 (`LoRAPageCentralLibraryTabTest`, `test_lora_roundtrip.py`) — activation du bouton, Cancel strict du sélecteur, aperçu rafraîchi immédiatement après succès, remplacement avec nettoyage de l'ancienne miniature, les trois branches du garde dirty-state avant ouverture du sélecteur, erreurs de copie/persistance/nettoyage partiel.
- Suite ciblée Manager : **9/9 OK**. Suite ciblée UI (`LoRAPageCentralLibraryTabTest`) : **67/67 OK** (54 préexistants + 13 nets nouveaux).
- Non-régression LoRA complète (`test_lora_roundtrip.py` + `test_lora_library_roundtrip.py`) : **314/314 OK**.
- Smoke test Qt réel (clics réels sur les vrais widgets) : **22/22 assertions PASS**, 4 scénarios réels.
- **1737/1737 tests verts au total** (1715 précédents + 22 nets nouveaux). Cette full suite finale a été exécutée avec une instrumentation temporaire dédiée, non committée, distinguant explicitement les occurrences déjà diagnostiquées de la dette Mission 084 de toute boîte véritablement inattendue : **5 occurrences connues neutralisées automatiquement**, **0 boîte inattendue**, **0 intervention humaine pendant cette exécution**, aucun processus/thread Qt résiduel constaté ensuite. Cette validation ne doit pas être lue comme « sans aucun dialogue » : cinq tentatives réelles ont eu lieu, détectées avec preuve et neutralisées, indépendantes de cette mission.
- `git diff --check` : propre.

### État du projet (Mission 093)

1737/1737 tests automatisés verts. Commit fonctionnel `b99d6e6` (`Add thumbnail selector to the central LoRA library`), tag `v0.2-mission093`, GitHub Release publiée. Dette conservée pour un futur audit dédié : extension du filet de sécurité Mission 091 aux classes Pending Result de la famille Mission 084, et correction du lifetime gap entre le mock du corps du test et `addCleanup(self.window.close)`. Voir `docs/missions/MISSION_093.md` pour le détail complet.

---

## v0.2-mission092 — 2026-09-02

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 092 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 092)

Les rapports de clôture des Missions 088, 089 et 090 listaient tous trois, sans exception, « l'import direct depuis l'onglet Bibliothèque centrale » comme besoin explicitement laissé ouvert : jusqu'ici, `LoRAPage.add_to_central_library()` était l'unique appelant de `LoRALibraryManager.import_lora()`, et copiait obligatoirement la LoRA Character-scoped actuellement active — un fichier LoRA destiné dès l'origine à un usage générique (style, skin, réalisme) n'avait aucun moyen d'entrer dans la bibliothèque centrale sans passer par le détour artificiel de le créer d'abord comme LoRA d'un personnage.

Un second point d'entrée UI a été ajouté à l'onglet « Bibliothèque centrale » : un bouton « Importer depuis le disque… », toujours activé, qui ouvre un sélecteur de fichiers puis un dialogue de nom et appelle directement `LoRALibraryManager.import_lora()` — exactement le même appel déjà utilisé par `add_to_central_library()`, sans aucun second pipeline parallèle et sans aucun changement de signature Manager/Storage. Un mini-audit préalable a confirmé que `import_lora()` était déjà strictement suffisant (aucune précondition Workspace/Character, multi-fichier déjà supporté, rollback transactionnel déjà entièrement testé depuis Mission 087) et a identifié le seul point réellement absent du contrat initial : `_display_library_entry()`, utilisée pour sélectionner et charger la nouvelle entrée après import, change la sélection sous `blockSignals(True)` et ne déclenche donc jamais le garde `_library_metadata_dirty` habituel de `on_library_selection_changed()`. Le nouveau handler reproduit explicitement ce garde en tête, avant même l'ouverture du sélecteur de fichiers, avec les trois branches Cancel/Save/Discard déjà établies ailleurs sur cet onglet.

Deux imports du même fichier restent explicitement autorisés et indépendants, conformément au contrat de Mission 087 — aucune déduplication par hash ni aucune nouvelle notion d'identité globale n'a été introduite. Aucun sélecteur de thumbnail n'a été ajouté à l'onglet central (gap pré-existant, non aggravé). Aucun changement au modèle de scopes Character/Workspace/Global, à `project.json`, ni à l'exposition des moteurs.

Pendant la validation, l'architecte a signalé avoir vu apparaître une vraie `QMessageBox` « Génération en attente » (guard de Mission 084, distinct du guard de Mission 085 traité par Mission 091) pendant une exécution antérieure de la suite. Une analyse dédiée — lecture exhaustive des 35 occurrences pertinentes de ce guard, confirmant qu'aucune n'en construit réellement l'instance, et une troisième full suite surveillée empiriquement en temps réel — a conclu à un incident non reproductible et non attribuable à Mission 092 ; la couverture partielle du filet de sécurité de Mission 091 (limitée à 4 classes de test, non globale) reste actée comme dette potentielle future, hors périmètre de cette mission.

### Tests ajoutés (Mission 092)

- **13 tests dédiés nets nouveaux** (`LoRAPageCentralLibraryTabTest`, `test_lora_roundtrip.py`) : import direct réussi avec copie physique réelle vérifiée ; sélection et chargement automatique de la nouvelle entrée ; Cancel du sélecteur de fichiers et Cancel/nom vide du dialogue de nom, chacun un no-op strict ; deux imports du même fichier source produisant deux entrées indépendantes ; échec de copie et échec de persistance, chacun sans création d'entrée ; garde dirty-state avant ouverture du sélecteur, les trois branches Cancel/Save/Discard ; bouton toujours activé.
- Suite ciblée `LoRAPageCentralLibraryTabTest` : **54/54 OK** (41 préexistants + 13 nets nouveaux).
- Non-régression LoRA complète (`test_lora_roundtrip.py` + `test_lora_library_roundtrip.py`) : **292/292 OK**.
- Smoke test Qt réel (clics réels sur les vrais widgets, filet Mission 091 armé) : **19/19 assertions PASS**, 4 scénarios.
- **1715/1715 tests verts au total**, full suite exécutée deux fois consécutivement sans intervention humaine, plus une troisième exécution surveillée empiriquement pour l'investigation de l'incident « Génération en attente » (voir résumé) — également 1715/1715, zéro dialogue observé.
- `git diff --check` : propre.

### État du projet (Mission 092)

1715/1715 tests automatisés verts. Commit fonctionnel `25e3133` (`Add direct import to the central LoRA library from disk`), tag `v0.2-mission092`, GitHub Release publiée. Voir `docs/missions/MISSION_092.md` pour le détail complet.

---

## v0.2-mission091 — 2026-08-31

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 091 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 091)

Pendant la clôture de Mission 090, deux full suites consécutives avaient produit deux échecs intermittents différents, tous deux dans la zone du threading `QThread` réel introduite par Mission 085 (guard « génération active »). Plutôt que de classer cela comme un simple aléa d'environnement de plus, un audit dédié a établi que le phénomène observé — de vraies `QMessageBox` bloquantes apparaissant parfois sur un écran secondaire, sans qu'aucun humain ne sache qu'un clic est attendu — était en réalité un **bug reproductible et localisé du harness de test**, entièrement concentré sur `InferencePage.confirm_no_active_generation()` : ce guard, premier de la chaîne dans `MainWindow.closeEvent()`/`rename_project()`, était systématiquement omis par les tests qui pilotent une génération réellement active via l'idiome partagé `_controlled_generate()`, alors que ces mêmes tests mockaient scrupuleusement tous les guards suivants. **10 instances exactes** ont été confirmées par lecture directe du code, réparties sur `test_inference_page.py`, `test_main_window_close_event.py` et `test_main_window_rename_project.py`.

Un mini-audit contractuel avait initialement validé, par vérification empirique dans cet environnement, un premier mécanisme de filet de sécurité fondé sur un patch de `QMessageBox.exec` au niveau classe. **Ce mécanisme s'est révélé inopérant en pratique dès le premier test de démonstration réel** : une vraie `QMessageBox` bloquante (« Critical Title »/OK) a exigé un clic humain — exactement le défaut que la mission visait à éliminer. La cause racine, isolée par investigation directe : `QMessageBox.warning()`/`.critical()` sont des wrappers Shiboken autour des fonctions C++ **natives** de Qt, qui construisent leur propre instance `QMessageBox` C++ et appellent `.exec()` dessus par un appel de vtable C++ direct — jamais via un attribut Python, rendant tout monkeypatch Python de `QMessageBox.exec` structurellement sans effet sur cet appel interne.

Le mécanisme a été entièrement redesigné, toujours sur la base d'une vérification empirique réelle : `tests/integration/_qt_dialog_safety_net.py` implémente désormais un watcher `QApplication`-wide (`_DialogGuard`) combinant un filtre d'événement `QEvent.Show` (chemin rapide) et un `QTimer` de repli à 15 ms scannant `QApplication.topLevelWidgets()` (filet déterministe inconditionnel), pour détecter toute vraie `QMessageBox` devenant visible quelle que soit son origine (code Python ou méthode statique C++ native). La fermeture est différée d'un tick d'event-loop (`QTimer.singleShot(0, ...)`) plutôt que synchrone — vérifié nécessaire contre l'ordre interne de `QDialog.exec()` (`show()` est appelé avant que le `QEventLoop` interne ne soit créé et assigné), sous peine de transformer le bug en un hang invisible pire que l'original. `UnexpectedDialogError` n'est levée qu'en Python pur, après restauration complète du timer et du filtre d'événement.

Les 10 tests fautifs sont corrigés par le mock positif déjà utilisé correctement ailleurs dans le même fichier pour ce même guard — aucune assertion existante n'est affaiblie ou supprimée. Le filet est appliqué via des appels explicites `start_dialog_guard()`/`stop_dialog_guard()` dans `setUp()`/`tearDown()` (jamais via une classe mixin en héritage, les 4 classes concernées n'appelant jamais `super()`) aux 4 classes à risque, dont `MainWindowNewOpenGenerationActiveNonRegressionTest` en défense en profondeur (confirmée saine, aucun bug actuel).

Une fois ce filet réellement opérant, la première exécution des tests ciblés a révélé 7 échecs supplémentaires — non des faux positifs, mais deux catégories de fragilités de test authentiques jusqu'ici invisibles : (1) une **race de nettoyage de thread** (5 tests, 3 fichiers) où le test se terminait avant que `InferencePage._thread` n'ait genuinement atteint `None`, laissant une fenêtre où `is_generation_active()` pouvait encore répondre `True` au moment du vrai `close()`/`rename_project()` de `tearDown()`/`addCleanup()` ; (2) un **`_dirty` non réinitialisé après Discard/Cancel sur fermeture** (2 tests, `test_main_window_close_event.py`) — vérifié comme un comportement préexistant, intentionnel et identique dans `PromptsPage.confirm_context_change()`, donc une omission de test et non un bug de production. Les deux catégories sont corrigées entièrement côté test, sans aucun changement de code applicatif.

### Tests ajoutés (Mission 091)

- Tests ciblés des 4 fichiers concernés (`test_inference_page.py`, `test_main_window_close_event.py`, `test_main_window_rename_project.py`, `test_main_window_new_project.py`) : **220/220 OK**, 0 intervention humaine, 0 dialogue visible.
- **5 tests dédiés nets nouveaux** du nouveau filet (`test_qt_dialog_safety_net.py`, classe `QtDialogSafetyNetTest`) : dialogues réels `.warning()` et `.critical()` déclenchés volontairement, chacun capturé et converti en `UnexpectedDialogError` en moins d'une seconde, aucun affichage à l'écran ; cas sans dialogue ; nettoyage du timer/event-filter après usage ; non-déclenchement sur un dialogue déjà mocké.
- **1702/1702 tests verts au total** (1697 précédents + 5 nets nouveaux), full suite exécutée **deux fois consécutivement sans aucune intervention humaine**, zéro dialogue visible et zéro processus/thread Qt résiduel constaté après chaque run.
- `git diff --check` : propre (seuls avertissements CRLF/LF cosmétiques, aucune violation réelle).
- Aucun test métier ajouté ni retiré, aucun changement de comportement fonctionnel — mission strictement de fiabilisation du harness de test.

### État du projet (Mission 091)

1702/1702 tests automatisés verts. Commit fonctionnel `9289ee5` (`Add Qt dialog safety net and fix 10 unmocked generation-active tests`), tag `v0.2-mission091`, GitHub Release publiée. Voir `docs/missions/MISSION_091.md` pour le détail complet.

---

## v0.2-mission090 — 2026-08-31

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 090 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 090)

L'audit mené après la clôture de Mission 089 a confirmé que l'onglet « Bibliothèque centrale » de `LoRAPage`, désormais consultable et supprimable, ne permettait toujours aucune correction d'une entrée existante : `LoRALibraryManager` n'exposait que `list_loras()`/`get()`/`import_lora()`/`delete()`, aucune méthode `update()`. Si le nom ou l'une des 4 métadonnées copiées à l'import (Mission 088) s'avérait erronée, la seule solution restait de supprimer l'entrée et de la réimporter, ou d'éditer `lora_library.json` à la main. Un mini-audit contractuel a fermé deux points avant toute écriture de code : un nouvel événement `LORA_LIBRARY_UPDATED` est réellement nécessaire — contrairement à `LoRAManager.update()`/`update_name()` (Character-scoped), qui n'ont jamais eu besoin d'événement propre car portés gratuitement par `WORKSPACE_SAVED`, la bibliothèque centrale n'a aucun équivalent générique, son registre étant un fichier de persistance entièrement séparé ; et `update_central_library()` doit gagner une garde d'identité+dirty (mirroir de `update_loras()`, Mission 078) pour ne plus détruire silencieusement un brouillon en cours d'édition à chaque événement `IMPORTED`/`DELETED`/`UPDATED` concernant une autre entrée.

**Implémentation** : `LoRALibraryManager` gagne une unique méthode combinée `update(lora_id, name=, engine=, architecture=, trigger_word=, version=)` — mirroir de `CharacterManager.update()` (Mission 074) plutôt que du split historique `update()`/`update_name()` de `LoRAManager` (artefact de deux missions distinctes, 052 puis 073, non pertinent ici puisque les 5 champs arrivent en une seule fois via un seul formulaire) : idempotence stricte (OU logique des 5 comparaisons individuelles), rollback mémoire exact des 5 champs si `_save()` échoue, événement `LORA_LIBRARY_UPDATED` publié uniquement après persistance réussie, aucune opération filesystem (le dossier de l'entrée est indexé par `lora_id`, jamais par `name`). Côté UI, le panneau de détail de l'onglet Bibliothèque centrale devient un formulaire éditable : nouveau widget `library_name_edit` (le nom n'avait aucun widget dédié auparavant), les 4 `QLabel` métadonnées deviennent des `QLineEdit`, nouveau bouton « Enregistrer » activé uniquement lorsqu'une modification effective existe (délibérément plus strict que le précédent Personnage). Le brouillon non enregistré est protégé sur tous les chemins de perte réels identifiés par le mini-audit : changement de sélection (Save/Discard/Cancel, mirroir du Personnage), suppression de l'entrée en cours d'édition (confirmation adaptée, pas de second dialogue), événement concernant une autre entrée (brouillon préservé, seule la liste se rafraîchit autour de lui), et fermeture complète de l'application via un nouveau guard `confirm_library_context_change()`, branché uniquement dans `MainWindow.closeEvent()` — jamais sur New/Open/Rename de Workspace, ceux-ci ne menaçant structurellement rien dans cet onglet Application-level.

### Tests ajoutés (Mission 090)

- **33 tests ciblés nets nouveaux** : `LoRALibraryManagerUpdateTest` (10, `test_lora_library_roundtrip.py`) — id inconnu, aucun champ fourni, valeurs identiques, `name` seul sans toucher aux 4 autres, les 5 champs simultanément avec un seul `_save()`/un seul événement, chaîne vide légitime, retour exact aux valeurs d'origine → de nouveau idempotent, `lora_id`/`files` jamais touchés, aucune opération filesystem, échec de `_save()` → rollback exact des 5 champs sans événement. `LoRAPageCentralLibraryTabTest` (23 nets nouveaux, classe M089 étendue à 41 au total) — état du bouton Enregistrer, persistance d'un seul champ et des 5 champs simultanément avec mise à jour immédiate de la ligne de liste, no-op silencieux sur un retour à la valeur d'origine, échec de sauvegarde avec restauration, tous les branchements du guard de changement de sélection (Cancel/Discard/Save/échec de Save, y compris la reconstruction réentrante de liste déclenchée par la propre sauvegarde de l'entrée), texte de confirmation de suppression adapté, suppression de l'entrée en cours d'édition, événement concernant une autre entrée pendant un brouillon dirty, et tous les branchements de `confirm_library_context_change()`.
- Non-régression complète : `test_lora_roundtrip.py` (205 préexistants + 23 nets nouveaux = 228/228), `test_lora_library_roundtrip.py` (41 préexistants + 10 nets nouveaux = 51/51), `test_application_settings_roundtrip.py` (17/17), suite ciblée `MainWindow`/`closeEvent`/guards sur 7 fichiers (445/445).
- **1697/1697 tests verts au total** (1664 précédents + 33 nets nouveaux), une exécution complète `unittest discover`, aucun crash.
- Smoke test Qt réel, exécuté par Claude, run 3 fois consécutives pour la stabilité — **PASS, 28/28 assertions à chaque exécution** : sélection réelle, saisie réelle, clic réel sur Enregistrer avec rafraîchissement automatique via l'événement réel et resélection correcte après la reconstruction réentrante de la liste, renommage réel sans déplacement de dossier, changement de sélection dirty avec Cancel réel puis Save réel, texte de confirmation de suppression réellement adapté, guard de fermeture d'application exercé avec Cancel et Save réels, et confirmation finale que les fichiers/thumbnail de la LoRA Character-scoped source restent strictement inchangés sur tout le cycle.

### État du projet (Mission 090)

1697/1697 tests automatisés verts. Commit fonctionnel `9ea1165` (`feat: allow editing central LoRA library entries (name and metadata)`), tag `v0.2-mission090`, GitHub Release publiée. Voir `docs/missions/MISSION_090.md` pour le détail complet.

---

## v0.2-mission089 — 2026-08-31

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 089 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 089)

L'audit mené après la clôture de Mission 088 a confirmé que la bibliothèque centrale posée par Mission 087 et alimentée depuis l'UI par Mission 088 restait fonctionnellement présente mais entièrement inconsultable : `LoRALibraryManager.delete()` (Mission 087) était entièrement implémentée et testée mais n'avait aucun appelant Presentation, et les événements `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_DELETED` (Mission 087) n'avaient aucun abonné — la seule façon d'inspecter ou de corriger la bibliothèque centrale était d'éditer `lora_library.json` à la main. Un premier mini-audit avait envisagé trois emplacements UI (nouvelle Page Sidebar, section `SettingsPage`, deux onglets dans `LoRAPage`) sans trancher ; l'architecte a ensuite orienté explicitement vers la solution à deux onglets et demandé sa vérification contre le code réel avant validation finale. Cette vérification a confirmé qu'aucun `QTabWidget` n'existait encore dans le projet mais que le déplacement du contenu existant dans un premier onglet ne changeait que le parent Qt de chaque widget, jamais son nom d'attribut Python ; que `LoRALibraryManager.list_loras()` retourne des objets `LoRA` (accès par attribut) contrairement à `LoRAManager.list_loras()` qui retourne des `dict` ; et que le helper `_load_thumbnail_preview()` existant n'était pas directement réutilisable tel quel (il mutait un unique `QLabel` codé en dur), corrigé par extraction d'une primitive paramétrée `_render_thumbnail_preview(label, thumbnail_path)`. Comparée aux deux alternatives, la solution à deux onglets l'a emporté sur la cohérence UX et l'évolution future.

**Implémentation** : `LoRAPage.__init__()` est restructuré autour d'un `QTabWidget` (`self.tab_widget`) à deux onglets — « Personnage » (contenu Character-scoped strictement inchangé, déplacé tel quel) et « Bibliothèque centrale » (nouveau, exclusivement `LoRALibraryManager`, jamais fusionné avec `LoRAManager`). Le nouvel onglet ajoute `library_list` (tri alphabétique insensible à la casse, nom + nombre de fichiers), un panneau détail en lecture seule (`QLabel` pour `engine`/`architecture`/`trigger_word`/`version`), un aperçu miniature via `_render_thumbnail_preview()`, et `delete_from_library_button` (désactivé sans sélection). `update_central_library()` relit systématiquement `list_loras()` en entier, ignore le payload de l'événement, est appelée une première fois à la construction, et n'est jamais abonnée à un événement Workspace/Character. `delete_from_library()` suit le même contrat transactionnel que tout autre chemin de suppression du projet : confirmation `QMessageBox` explicite (Annuler par défaut), `LoRALibraryManager.delete(lora_id, library_root)` avec `library_root` relu en direct depuis `application_settings_manager.settings.lora_library_path` (jamais mis en cache), `QMessageBox.critical` sur `LoRALibraryError`, avertissement non bloquant sur `cleanup_failed` — aucun rafraîchissement manuel après un succès, l'événement `LORA_LIBRARY_DELETED` déjà publié par le Manager déclenchant `update_central_library()` via l'EventBus. `main_window.py` gagne deux nouveaux abonnements dédiés (`LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_DELETED` → `lora_page.update_central_library`), strictement séparés des abonnements Workspace/Character existants. Mission strictement de consultation/suppression : aucune édition, aucun import depuis cet onglet, aucune association Character/Workspace, aucun modèle de scopes, aucune migration de `project.json`, aucune exposition moteur/provider.

### Tests ajoutés (Mission 089)

- **18 tests ciblés nets nouveaux** (`LoRAPageCentralLibraryTabTest`, `test_lora_roundtrip.py`) : structure des deux onglets et ordre ; non-régression de tous les widgets de l'onglet Personnage (toujours présents, toujours parentés) ; bibliothèque vide ; une entrée (nom + nombre de fichiers) ; plusieurs entrées triées ; les 4 métadonnées affichées à la sélection ; miniature présente ; aucune miniature ; miniature physiquement disparue sans crash ; sélection → bouton activé, désélection → bouton désactivé et panneau vidé ; Cancel → aucune mutation ; suppression confirmée réelle (registre, disque et UI tous vérifiés) ; erreur Manager → message et entrée conservée ; `cleanup_failed` → suppression logique maintenue avec avertissement ; apparition automatique après un import via l'EventBus ; suppression automatique après une suppression via l'EventBus ; événements New/Open/Close/Rename de Workspace et création de Character n'affectant jamais la bibliothèque centrale.
- Non-régression complète : `test_lora_roundtrip.py` (187 préexistants + 18 nets nouveaux = 205/205), `test_lora_library_roundtrip.py` (41/41), `test_application_settings_roundtrip.py` (17/17).
- **1664/1664 tests verts au total** (1646 précédents + 18 nets nouveaux), une exécution complète `unittest discover`, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `LoRAPage`/`LoRAManager`/`LoRALibraryManager`/`ApplicationSettingsManager` réels, Workspace/Character/LoRA réels avec fichiers et thumbnail réels sur disque, bibliothèque centrale pointée vers un dossier temporaire réel — **PASS, 25/25 assertions** (stable sur 3 exécutions consécutives) : clic réel sur « Ajouter à la bibliothèque centrale » suivi d'une mise à jour automatique de l'onglet Bibliothèque centrale via l'EventBus (sans appel manuel) ; bascule réelle d'onglet ; sélection réelle affichant les 4 métadonnées et une miniature réelle non nulle ; `lora_library.json` et le dossier physique de l'entrée vérifiés directement sur disque avant suppression ; clic réel sur « Supprimer » (confirmé) suivi d'une mise à jour automatique de la liste/du panneau/du bouton via l'EventBus ; registre et dossier physique confirmés vidés/supprimés après la suppression ; **fichiers et thumbnail de la LoRA Character-scoped source confirmés strictement inchangés après l'ensemble du cycle import → consultation → suppression**.

### État du projet (Mission 089)

1664/1664 tests automatisés verts. Commit fonctionnel `153bf93` (`feat: add read-only central library tab to LoRAPage`), tag `v0.2-mission089`, GitHub Release publiée. Voir `docs/missions/MISSION_089.md` pour le détail complet.

---

## v0.2-mission088 — 2026-08-29

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 088 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 088)

L'audit mené après la clôture de Mission 087 a confirmé que la fondation posée par cette dernière (`LoRALibraryManager`/`LoRALibraryStorage`, `ApplicationSettings.lora_library_path`) restait fonctionnellement présente mais entièrement déconnectée : aucun appelant Presentation n'existait, la bibliothèque centrale restait vide et invisible en dehors de `SettingsPage` (qui n'affiche que le chemin configuré). L'action d'import depuis `LoRAPage` a été retenue — c'est littéralement l'action nommée par la décision C de l'architecte lors du mini-audit LoRA de Mission 087 et l'item (1) de sa feuille de route, sans exiger aucune décision architecturale nouvelle. Un mini-audit contractuel ciblé, mené à partir du code réel post-Mission 087, a fermé trois points avant toute écriture de code : la signature réelle de `LoRALibraryManager.import_lora()` ne transmettait alors ni `engine`, ni `architecture`, ni `trigger_word`, ni `version` au `LoRA` central créé — une copie appauvrie aurait été produite sans extension additive de l'API, corrigée par le contrat ci-dessous ; le comportement tout-ou-rien déjà existant de `import_lora()` face à une miniature déclarée mais dont le fichier a disparu a été confirmé et retenu tel quel, sans pré-vérification UI destinée à l'ignorer silencieusement ; et les deux nouvelles dépendances `LoRAPage` (`lora_library_manager`/`application_settings_manager`) ont été tranchées comme paramètres **requis**, non `Optional`, cohérents avec `lora_manager`/`workspace_manager` déjà requis dans ce même constructeur.

**Implémentation** : `LoRALibraryManager.import_lora()` gagne quatre nouveaux paramètres optionnels mots-clés (`engine=""`, `architecture=""`, `trigger_word=""`, `version=""`), transmis tels quels au `LoRA` central construit — purement additif, les 39 tests Mission 087 existants n'appelant jamais ces paramètres, leur comportement testé (défauts `""`) reste identique. `LoRAPage` gagne un nouveau bouton explicite « Ajouter à la bibliothèque centrale », activé/désactivé via `_update_metadata_buttons_state()` (même source que les boutons Metadata existants), et une méthode `add_to_central_library()` : si les 4 champs métadonnées ont un brouillon non sauvegardé, le dialogue Save/Discard/Cancel déjà existant (`_confirm_discard_metadata_before_switch()`, relu intégralement et réutilisé tel quel — aucune hypothèse ni effet de bord propre au changement de sélection) est affiché en premier ; Cancel abandonne l'action, Save persiste le brouillon avant d'importer les valeurs désormais synchronisées, Discard restaure les champs à l'état persisté avant d'importer cet état. Le chemin de la bibliothèque centrale est résolu depuis `ApplicationSettings` au moment du clic, jamais mis en cache. Aucune association retour n'est stockée sur la LoRA Character-scoped source — une réimportation ultérieure crée une entrée centrale supplémentaire indépendante, avec sa propre copie physique, conformément au contrat Mission 087 (aucune déduplication). Mission strictement additive et toujours déconnectée : `Character.loras`, `project.json`, toute UI globale de bibliothèque, Inference et tout moteur/provider restent entièrement inchangés.

### Tests ajoutés (Mission 088)

- **16 tests ciblés nets nouveaux** : `LoRAPageAddToCentralLibraryTest` (14, `test_lora_roundtrip.py`) — bouton désactivé sans LoRA active / activé après sélection ; import réussi produisant une entrée centrale avec fichiers, thumbnail et les 4 métadonnées corrects ; import multi-fichiers ; import sans thumbnail ; fichier principal manquant → erreur, aucune entrée créée ; thumbnail déclarée mais fichier disparu → échec total de l'import (contrat tout-ou-rien verrouillé par un test dédié) ; échec de persistence → erreur, aucune entrée créée ; deux imports successifs → deux entrées et deux copies physiques indépendantes ; fichiers/thumbnail Character-scoped source strictement inchangés après import ; les 4 chemins du dirty-state (Cancel, Save, Discard, échec de Save pendant la résolution). `LoRALibraryManagerImportTest` (2, `test_lora_library_roundtrip.py`) — les 4 métadonnées transmises fidèlement et persistées après rechargement du registre ; comportement pré-Mission-088 inchangé quand elles sont omises.
- Non-régression complète : `test_lora_roundtrip.py` (187/187, y compris les 12 sites de construction `LoRAPage(...)` préexistants mis à jour mécaniquement pour les deux nouvelles dépendances requises), `test_lora_library_roundtrip.py` (41/41), `test_application_settings_roundtrip.py` (17/17), `test_settings_page.py`/`test_settings_roundtrip.py` (90/90), suite `MainWindow` ciblée sur 9 fichiers (122/122).
- **1646/1646 tests verts au total** (1630 précédents + 16 nets nouveaux), une exécution complète `unittest discover`, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `LoRAPage`/`LoRAManager`/`LoRALibraryManager`/`ApplicationSettingsManager` réels, Workspace/Character/LoRA réels avec fichiers et thumbnail réels sur disque, bibliothèque centrale pointée vers un dossier temporaire réel, clic réel sur le nouveau bouton — **PASS, 25/25 assertions** (stable sur 3 exécutions consécutives) : registre `lora_library.json` réellement écrit, copie physique du fichier de poids présente sous `library_root/<lora_id>/` avec le contenu exact de la source, thumbnail centrale présente, les 4 métadonnées correctement transmises, **fichiers et thumbnail Character-scoped source strictement inchangés (mêmes chemins, même contenu, toujours présents sur disque)**, copie centrale physiquement distincte de la source, import répété créant une seconde entrée indépendante.

### État du projet (Mission 088)

1646/1646 tests automatisés verts. Commit fonctionnel `2702bea` (`feat: add explicit Add-to-central-library action to LoRAPage`), tag `v0.2-mission088`, GitHub Release publiée. Voir `docs/missions/MISSION_088.md` pour le détail complet.

---

## v0.2-mission087 — 2026-08-29

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 087 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 087)

L'audit mené après la clôture de Mission 086 a réévalué le besoin « bibliothèque LoRA centralisée multi-engine », déjà enregistré et partiellement décidé lors de la régularisation de Mission 060 (stockage physique centralisé et unique, appartenance logique séparée du stockage physique, trois scopes `Character`/`Workspace`/`Global-Shared`, exposition moteur différée à un futur audit dédié). Un premier mini-audit a confirmé, à partir du code réel, que `LoRA` est aujourd'hui nichée dans `Character.loras` sans collection top-level ni Manager Workspace-owned ; que `LoRA.files` ne sont jamais copiés physiquement (références externes brutes), seul `LoRA.thumbnail` étant physiquement possédé sous `workspace_root/models/loras/<lora_id>/` ; qu'aucune persistance hors Workspace n'existe dans ce dépôt à une seule exception, `ApplicationSettingsStorage` ; et que deux systèmes « LoRA » déjà déconnectés coexistent (`Character.loras`, jamais consommé par une génération, et `ApplicationSettings.comfyui_lora_name`/`comfyui_lora_strength`, seul réellement utilisé par `GenerationManager`). L'architecte a ensuite tranché quatre décisions structurantes (modèle Domain unifié sans type `SharedLoRA` parallèle ; suppression défensive sans index global cross-Workspace ; grandfathering, aucune migration physique forcée des LoRA existantes ; stockage binaire configurable, jamais `%LOCALAPPDATA%` imposé), puis validé qu'une fondation minimale (registre + configuration du chemin), sans toucher à `Character.loras`/`LoRAManager`/`project.json`/l'UI existante/l'exposition moteur, est le périmètre correct pour Mission 087. Un dernier mini-audit contractuel a fermé les questions de stockage restantes (emplacement exact du registre, réutilisation prudente de `WorkspaceStorage`, contrat précis du Manager, valeur par défaut du chemin binaire, politique de changement de chemin).

**Implémentation** : `LoRALibraryStorage` (nouveau) persiste un registre séparé `%LOCALAPPDATA%\AIStudioToolkit\lora_library.json` (même répertoire qu'`ApplicationSettingsStorage`, délégation via `default_directory()`, écriture atomique, tolérance fichier absent/JSON invalide). `LoRALibraryManager` (nouveau) réutilise intégralement le dataclass `LoRA` existant — `list_loras() -> list[LoRA]`, `get(lora_id) -> Optional[LoRA]`, `import_lora(name, file_paths, library_root, thumbnail_path=None) -> LoRA` (jamais `Optional`, vérifié contre le précédent réel `ModelManager.create()`), `delete(lora_id, library_root) -> LoRALibraryDeletionResult` — et copie réellement chaque fichier importé dans `<library_root>/<lora_id>/`, contrairement au contrat actuel de `Character.loras`. Contrat transactionnel dès la création : copie avant toute mutation Domain (abandon + nettoyage best-effort si une copie échoue), suppression via `.trash/` (mirroir exact des Missions 066/067/075), aucun état de chemin conservé par le Manager (`library_root` passé explicitement à chaque appel mutant, évitant toute dépendance circulaire avec `ApplicationSettingsManager`). Nouveau champ `ApplicationSettings.lora_library_path` (défaut `%USERPROFILE%\AI Studio Toolkit\LoRA Library`, écarté `%LOCALAPPDATA%` et `Documents` — risque de synchronisation OneDrive automatique) avec un champ Settings réel (saisie libre + bouton « Parcourir »). Politique de changement de chemin définitive : modifiable librement tant que le registre central est vide, refusée avec un message explicite dès qu'il contient au moins une entrée, aucune migration/copie/déplacement automatique jamais tentée, resaisir la valeur déjà configurée restant un no-op autorisé même registre non vide. Le verrou (nouvelle exception `LoRALibraryPathLockedError`) vit dans `ApplicationSettingsManager.update()` — seul point de passage réel de la persistence `ApplicationSettings`, jamais contournable depuis `SettingsPage`. Réutilisation précise de `WorkspaceStorage.copy_into_workspace(source, destination_folder, workspace_root=destination_folder)` (jamais la racine entière de la bibliothèque) pour préserver l'ownership strict par dossier d'entrée. Mission strictement fondationnelle et déconnectée : `Character.loras`, `LoRAManager`, `project.json`, `LoRAPage`, Inference et tout moteur (ComfyUI inclus) restent entièrement inchangés.

### Tests ajoutés (Mission 087)

- **40 tests ciblés nets nouveaux** : `test_lora_library_roundtrip.py` (39, nouveau fichier) — `LoRALibraryStorageTest` (registre absent/JSON invalide/non-dict, délégation de `default_directory()`, écriture atomique), `LoRALibraryManagerImportTest` (import mono/multi-fichiers, thumbnail optionnelle, collision de noms, deux imports de la même source → deux entrées et deux copies physiques distinctes sans déduplication, sources jamais modifiées/supprimées, échec de copie partielle et de persistence avec et sans échec du nettoyage de secours), `LoRALibraryManagerDeleteTest` (suppression réussie, ID inconnu, échec de déplacement/persistence avec restauration, double échec, cleanup final en échec sans jamais annuler une suppression déjà persistée, confinement strict au dossier propre à l'entrée), `LoRALibraryManagerListGetTest` (`list_loras()` retourne des `LoRA`, jamais des `dict`), `LoRALibraryPersistenceRoundTripTest` (persistence entre instances de Manager), `ApplicationSettingsLoraLibraryLockTest` (les 6 points du contrat de verrouillage). `test_application_settings_roundtrip.py` (1 net nouveau parmi 17 au total) — champ `lora_library_path` intégré à chaque test existant exhaustif.
- Non-régression complète : `test_application_settings_roundtrip.py` (17/17), `test_settings_page.py`/`test_settings_roundtrip.py` (90/90), `test_lora_roundtrip.py` (173/173, `LoRAManager` Character-scoped entièrement inchangé), suite `MainWindow` ciblée (122/122).
- **1630/1630 tests verts au total** (1590 précédents + 40 nets nouveaux), une exécution complète `unittest discover` isolée sans charge concurrente, 191,7 s, aucun crash. Deux défaillances isolées observées lors d'exécutions combinées à forte charge système auto-infligée (`InferencePageGenerationActiveGuardTest.test_confirm_does_not_touch_thread_or_pending_when_refusing`, hérité de Mission 085, et `test_close_refused_immediately_while_generation_genuinely_active`, hérité de Mission 085) ont été reproduites en isolation et confirmées vertes (3,2 s et 12,4 s respectivement) — anomalie de contention ponctuelle déjà documentée depuis Mission 085/086, non un défaut introduit par cette mission.
- Smoke test Qt réel, exécuté par Claude, `SettingsPage`/`ApplicationSettingsManager`/`LoRALibraryManager` réels, dossiers temporaires réels — **PASS, 12/12 assertions** (stable sur 3 exécutions consécutives) : valeur par défaut réelle affichée, clic réel sur Parcourir mettant à jour le champ, sauvegarde réelle persistée sur disque, rechargement depuis une nouvelle instance de Manager restaurant la valeur, refus réel une fois qu'une vraie entrée existe dans la bibliothèque.

### État du projet (Mission 087)

1630/1630 tests automatisés verts. Commit fonctionnel `dcc27ca` (`feat: add central LoRA library foundation (registry + configurable path)`), tag `v0.2-mission087`, GitHub Release publiée. Voir `docs/missions/MISSION_087.md` pour le détail complet.

---

## v0.2-mission086 — 2026-08-29

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 086 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 086)

L'audit mené après la clôture de Mission 085 a identifié une friction utilisateur réelle et démontrable : `InferencePage._on_select_reference_clicked()` ne permettait de choisir une image de référence que via `QFileDialog` (parcours du disque), sans jamais pouvoir réutiliser une image déjà présente dans la galerie `Images` du Workspace (`Workspace.images`) — alors que `DatasetsPage` offre déjà ce choix pour l'ajout d'images à un Dataset depuis Mission 044 (`SelectImagesDialog`). Aucune décision produit n'expliquait cette asymétrie. Un mini-audit contractuel préalable a établi trois faits déterminants avant toute implémentation : `self._reference_image_path` est un simple `Optional[str]`, jamais copié ni persisté quelle que soit sa source — `GenerationManager.generate()`/`ComfyUIEngine.upload_image()` ne font que **lire** ce chemin (`Path(file_path).read_bytes()`) pour le POSTer vers ComfyUI, sans jamais écrire dans le Workspace, donc une image de galerie utilisée comme référence n'est jamais dupliquée physiquement, exactement comme une image choisie sur le disque ; aucun pattern de menu-sur-bouton n'existe nulle part dans le codebase, `DatasetsPage` résolvant déjà la même dualité disque/galerie avec deux boutons explicites côte à côte, pattern retenu pour Inference plutôt qu'une invention esthétique ; `SelectImagesDialog` était déjà une pure couche de présentation sans dépendance Dataset, sa généralisation par 3 paramètres constructeur optionnels (`selection_mode`, `title`, `info_text`), tous à valeur par défaut reproduisant le comportement Dataset actuel byte-for-byte, a été jugée petite, propre et sans risque de régression, écartant un second dialogue quasi identique.

**Implémentation** : `SelectImagesDialog.__init__()` gagne les 3 paramètres optionnels ci-dessus, sans modifier aucun appelant existant. `InferencePage` gagne un second bouton explicite « Choisir depuis Images… » dans la zone de référence, à côté du bouton disque existant ; `_on_select_reference_from_gallery_clicked()` mirroir exact de `DatasetsPage.add_images_from_gallery()` (garde `workspace_manager.opened`, garde galerie vide, ouverture de `SelectImagesDialog` en `SingleSelection` avec un titre/texte spécifiques à Inference, Cancel/aucune sélection sans mutation) ; un petit helper privé `_apply_selected_reference(file_path)` évite la duplication des 4 lignes de mise à jour d'état entre les deux chemins de sélection (disque et galerie), tous deux alimentant exactement la même primitive `self._reference_image_path`. `_set_reference_controls_enabled()` étendu pour inclure le nouveau bouton, désactivé/réactivé exactement comme les contrôles de référence existants. Mission strictement mono-référence (0..1) : `GenerationManager.generate()` reste plafonné à une seule référence actionable, `Reference(path, role)` et la réserve de capacité 0..N (Mission 056) restent intacts sans aucune modification — Mission 086 ajoute seulement une seconde façon de peupler l'élément unique actuel. Aucun changement Domain/Manager/EventBus/Engine.

### Tests ajoutés (Mission 086)

- **15 tests ciblés nets nouveaux** : `test_select_images_dialog.py` (3) — titre/texte par défaut inchangés, `selection_mode`/`title`/`info_text` configurables, `SingleSelection` empêche réellement plus d'un item sélectionné simultanément (vérifié empiriquement). `test_inference_page.py` (12, `InferencePageTest`) — aucun Workspace ouvert → avertissement contrôlé sans dialogue construit ; galerie vide → information contrôlée sans dialogue construit ; dialogue peuplé avec les images réelles du Workspace en `SingleSelection` ; Cancel/aucune sélection → aucune mutation ; sélection réelle → état mis à jour exactement comme le picker disque ; remplacement disque↔galerie dans les deux sens ; re-sélection de la même image galerie inoffensive ; aucune duplication physique sous `images/` ; bouton galerie désactivé pendant une génération active et pendant un pending, réactivé après Reject ; reset complet sur un changement de Workspace réel. Le cas « fichier de galerie disparu physiquement » n'a délibérément pas reçu de nouveau test dédié — couvert génériquement par la gestion existante de `GenerationError`, indépendante de la provenance de la référence.
- Non-régression complète : `test_select_images_dialog.py` (10/10), `test_inference_page.py` (128/128), `test_datasets_page.py` (non modifié, vert) — 138/138 sur l'ensemble ciblé.
- **1590/1590 tests verts au total** (1575 précédents + 15 nets nouveaux), une exécution complète `unittest discover`, 188,6 s, aucun crash. Une défaillance isolée observée pendant une exécution intermédiaire à forte charge système (`InferencePageGenerationActiveGuardTest.test_confirm_does_not_touch_thread_or_pending_when_refusing`, un test hérité de Mission 085 sans rapport avec le code de Mission 086) a été reproduite en isolation et confirmée verte en 4,9 s — anomalie de contention ponctuelle déjà documentée depuis Mission 085, non un défaut introduit par cette mission.
- Smoke test Qt réel, exécuté par Claude, `InferencePage`/`WorkspaceManager` réels, vraies images PNG écrites sur disque, vrai `SelectImagesDialog` construit — **PASS, 17/17 assertions** (stable sur 3 exécutions consécutives) : galerie réelle à 2 images, bouton galerie actif, dialogue réel construit en `SingleSelection` avec le titre Inference, référence correctement chargée, aucun nouveau fichier écrit sous `images/` après sélection, remplacement par une seconde image de galerie, reset complet après un changement de Workspace réel, avertissement contrôlé et aucun dialogue construit quand aucun Workspace n'est ouvert.

### État du projet (Mission 086)

1590/1590 tests automatisés verts. Commit fonctionnel `3b770c9` (`feat: select an Inference reference image from the Workspace gallery`), tag `v0.2-mission086`, GitHub Release publiée. Voir `docs/missions/MISSION_086.md` pour le détail complet.

---

## v0.2-mission085 — 2026-08-28

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 085 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 085)

L'audit mené après la clôture de Mission 084 a identifié, puis confirmé par reproduction empirique déterministe (worker piloté par `threading.Event`, jamais `sleep()`), que fermer l'application pendant qu'une génération est **réellement encore en cours** (réseau ComfyUI toujours en attente, fichier pas encore écrit) provoquait la suppression silencieuse du résultat produit une fois la génération terminée. Cause racine : `InferencePage.shutdown()` appelle `self._thread.wait()` (bloquant jusqu'à la fin réelle du worker) puis `self._clear_pending(delete_file=True)`, qui remet `self._generation_workspace_root = None` sans condition, y compris quand il n'y avait rien à nettoyer. Le signal cross-thread `worker.finished` n'est délivré qu'après le retour de `closeEvent()` ; `_on_generation_finished()` s'exécute alors avec `_generation_workspace_root` déjà à `None`, ce que `_workspace_context_matches()` interprète à tort comme « le Workspace a changé », et supprime le fichier fraîchement écrit via la branche prévue par la Mission 014 pour un cas totalement différent. Reproduit à 100% sur 4 délais différents. Un audit historique (`docs/missions/MISSION_013.md`) a confirmé que ce scénario n'a jamais été une décision produit — seul le contrat « aucun thread orphelin, aucun crash » était garanti. Une vérification empirique dédiée a également révélé un second défaut, distinct : renommer le projet pendant une génération active déplace physiquement tout le dossier racine pendant que le worker s'apprête à écrire dans `outputs/`, provoquant un échec technique confus (pas de perte silencieuse, mais une expérience dégradée). New Project et Open Project ont été vérifiés empiriquement comme déjà corrects — aucun des deux ne touche `_generation_workspace_root`, et le mécanisme de Mission 014 écarte alors légitimement et silencieusement le résultat une fois la génération terminée.

L'architecte a validé l'Option B (refus immédiat, sans jamais attendre ni tenter d'annuler le worker, la génération continue en arrière-plan et redevient un pending normal protégé par Mission 084 dès qu'elle se termine), après comparaison explicite avec l'attente bloquante (UX dégradée) et le laisser-fermer-puis-jeter (aucune récupération possible). Le mini-audit contractuel préalable a établi la définition fiable de « génération active » — `self._thread is not None and self._thread.isRunning()`, jamais `_thread is not None` seul — vérifiée empiriquement : au moment exact où `shutdown()` appelait `_clear_pending()`, `isRunning()` était déjà `False` alors que `_thread` restait non-`None`, exactement la fenêtre à l'origine du bug.

**Implémentation** : `InferencePage.is_generation_active() -> bool` et `InferencePage.confirm_no_active_generation(blocked_message: str) -> bool` encapsulent localement l'état du thread — `MainWindow` n'inspecte jamais `_thread` directement. Sans génération active, retourne `True` immédiatement ; sinon affiche `QMessageBox.warning()` avec le message fourni par l'appelant (même précédent que les autres avertissements « opération temporairement impossible » de l'application) et retourne `False`, sans jamais toucher `_thread`/`_pending_path`. `MainWindow.closeEvent()` ajoute ce guard en toute première position, avant les 6 guards existants et avant `InferencePage.shutdown()` — aucun brouillon n'est inutilement sauvegardé avant que l'utilisateur apprenne que la fermeture est impossible. `rename_project()` ajoute le même contrôle juste après la vérification `workspace_manager.opened`, avant même la construction de `RenameProjectDialog`. `new_project()`/`open_project()` restent délibérément inchangés — le mécanisme `_generation_workspace_root`/`_workspace_context_matches()` de Mission 014 gère déjà correctement ce cas, vérifié empiriquement et figé par 4 tests de non-régression dédiés.

### Tests ajoutés (Mission 085)

- **23 tests ciblés nets nouveaux** répartis en quatre fichiers, tous utilisant un worker piloté par `threading.Event` : `InferencePageGenerationActiveGuardTest` (7, `test_inference_page.py`) — aucune génération → `True` sans dialogue ; génération réellement active → `is_generation_active()` `True`, guard refuse et affiche le message exact fourni, ne touche jamais `_thread`/`_pending_path` ; le test critique — un vrai `QThread` démarré puis `quit()`/`wait()` directement confirme que `isRunning() == False` avec `_thread` encore non-`None` n'est jamais considéré comme actif ; la génération continue normalement et devient un pending réel après un refus. 7 tests dans `test_main_window_close_event.py` — orchestration (guard faux stoppe la chaîne avant les 6 autres et avant `shutdown()`, ordre exact des 7 guards tracé) et état réel (fermeture refusée pendant génération active, génération se termine et devient pending, seconde fermeture retombe sur Mission 084, un prompt dirty en parallèle n'est jamais consulté avant le nouveau guard, aucune génération → comportement inchangé). `MainWindowNewOpenGenerationActiveNonRegressionTest` (4, `test_main_window_new_project.py`) — New/Open pendant une génération active procèdent sans blocage, le résultat de l'ancien Workspace est écarté silencieusement une fois terminé (contrat Mission 014 figé comme non-régression), aucun crash quel que soit le délai de livraison du signal différé. `MainWindowRenameGenerationActiveGuardTest` (5, `test_main_window_rename_project.py`) — renommage refusé avant même la construction du dialogue, dossier physiquement inchangé, génération se termine normalement dans le Workspace non renommé, second renommage après formation du pending retombe sur le contrat Mission 084, aucune génération → comportement inchangé.
- Non-régression complète : `test_inference_page.py` (116/116), `test_main_window_close_event.py` (32/32), `test_main_window_new_project.py` (40/40), `test_main_window_rename_project.py` (20/20) — 208/208 au total, exécuté deux fois consécutivement pour confirmer l'absence de fragilité, et les fichiers adjacents instanciant `MainWindow` (30/30, aucune modification requise).
- **1575/1575 tests verts au total** (1552 précédents + 23 nets nouveaux), une exécution complète `unittest discover`, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `MainWindow`/`InferencePage`/`WorkspaceManager` réels, vrai `QThread`/`GenerationWorker`, génération pilotée par événements — **PASS, 18/18 assertions** (stable sur 3 exécutions consécutives) : fermeture refusée immédiatement pendant génération active, aucun des 6 guards existants exécuté, `shutdown()` jamais appelé, génération se termine normalement, seconde fermeture accepte via Mission 084 Accept avec persistence réelle ; renommage refusé avant même la construction du dialogue, dossier physiquement inchangé, génération se termine dans le Workspace non renommé, second renommage via Mission 084 Accept avec remap de chemin réel et déplacement physique du fichier confirmés ; aucune génération active → comportement inchangé, aucun message affiché.

### État du projet (Mission 085)

1575/1575 tests automatisés verts. Commit fonctionnel `5b6e25d` (`feat: refuse Close/Rename while a generation is genuinely active`), tag `v0.2-mission085`, GitHub Release publiée. Voir `docs/missions/MISSION_085.md` pour le détail complet.

---

## v0.2-mission084 — 2026-08-28

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 084 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 084)

L'audit mené après la clôture de Mission 083 avait identifié — puis, dans un audit dédié, confirmé par reproduction empirique directe (scripts Qt réels) — qu'`InferencePage._pending_path` (un résultat de génération déjà écrit sur disque dans `outputs/` mais pas encore Accept/Reject) était détruit sans aucune confirmation par `reset_for_workspace_change()` à chaque changement de contexte Workspace (New Project, Open Project, fermeture de l'application, renommage du projet), même quand rien d'autre n'était dirty ailleurs dans l'application. Aucun des 5 guards `confirm_context_change()` déjà établis (Missions 038/078/079/083) ne connaissait cet état, structurellement indépendant du texte du prompt.

L'architecte a tranché la politique produit : un choix explicite Accepter/Rejeter/Annuler avant toute transition qui détruirait un résultat pending. Un mini-audit contractuel préalable, mené avant toute implémentation, a découvert une distinction non triviale : parmi les 3 issues d'échec de la primitive Accept existante (`_on_accept_clicked()`), seul un vrai échec de persistence (`WorkspaceManagerError`, retry possible) doit bloquer la transition — un contexte Workspace périmé ou un fichier déjà disparu du disque détruisent déjà le pending comme effet de bord de leur propre gestion existante, donc rien à protéger, la transition doit être autorisée. Le mini-audit a également exigé une vérification empirique — non supposée — du cas Rename : un Accept suivi d'un renommage réel du Workspace remappe-t-il correctement le chemin de l'image acceptée ? La réponse, confirmée par script dédié (16/16 assertions), est oui : `WorkspaceManager.rename()`/`_build_renamed_payload()`/`_remap_path()` remappent déjà `Workspace.images[].file_path` (contrat Mission 027/028, inchangé), et le renommage physique du dossier racine (`old_root.rename(new_root)`) déplace intrinsèquement le fichier accepté avec lui — aucune anomalie détectée.

**Implémentation** : `_on_accept_clicked()`/`_on_reject_clicked()` sont réduits à de simples délégations vers deux nouvelles primitives privées à comportement byte-identique — `_accept_pending_result() -> bool` et `_reject_pending_result() -> None` — désormais partagées entre les boutons existants et le nouveau guard. `confirm_pending_result_change() -> bool` est une méthode strictement séparée de `confirm_context_change()` (les deux états — texte du prompt, résultat pending — ne sont jamais mélangés dans une seule méthode/dialogue) : sans pending, retourne `True` immédiatement sans dialogue ; sinon affiche `_confirm_pending_before_switch()`, un `QMessageBox` à trois boutons personnalisés (« Accepter l'image » / « Rejeter l'image » / « Annuler », défaut). `Cancel` refuse la transition sans rien modifier ; `Accept` appelle la primitive et distingue le vrai échec de persistence (transition refusée, `_pending_path` préservé) des deux issues déjà résolues (transition autorisée) ; `Reject` supprime puis autorise toujours la transition, même si la suppression physique échoue. Ce nouveau guard est ajouté en 6ᵉ et dernière position — après `Prompts → Characters → LoRA → Settings → Inference prompt` — dans `new_project()`/`open_project()`/`closeEvent()` de `MainWindow`, et comme **seul** guard ajouté à `rename_project()` (aucun des 5 guards texte, cohérent avec Mission 083 : un rename ne détruit aucun brouillon de texte). `InferencePage.reset_for_workspace_change()` reste entièrement inchangée, devenue un pur filet de sécurité inerte dans le flux normal — `_pending_path` est déjà `None` avant que l'événement Workspace ne soit publié.

### Tests ajoutés (Mission 084)

- **35 tests ciblés nets nouveaux** répartis en quatre fichiers : `InferencePagePendingResultGuardTest` (11, `test_inference_page.py`) — aucun pending → `True` sans dialogue, Cancel, Accept réussi (persistence réelle), Reject (suppression réelle, non bloquant même en cas d'échec physique), Accept avec `WorkspaceManagerError` (pending préservé) explicitement distingué d'Accept avec contexte périmé et d'Accept avec fichier disparu (les deux autorisent la transition), retry après échec de persistence, absence de double suppression ; 7 tests nouveaux dans `test_main_window_close_event.py` — guard pending faux stoppant la chaîne avant `shutdown()`, ordre des 6 guards tracé explicitement, Cancel/Reject/Accept/échec de persistence réels via `closeEvent()` avec persistence réelle vérifiée dans `project.json` ; `MainWindowInferencePendingResultGuardTest` (12, `test_main_window_new_project.py`) — Accept/Reject/Cancel réels pour `new_project()` et `open_project()`, échec de persistence, contexte périmé, fichier disparu, échec de suppression physique (jamais bloquant), garde fausse, ordre des 6 guards jusqu'à `workspace_manager.create()` ; `MainWindowRenamePendingResultGuardTest` (5, `test_main_window_rename_project.py`) — aucun pending (aucun dialogue), Cancel (aucun rename), Reject (suppression puis rename), échec de persistence (aucun rename, fichier préservé), et le test critique : Accept réel suivi d'un renommage physique réel, chemin remappé vérifié, fichier physiquement présent au nouveau chemin avec contenu intact, projet réouvert avec référence valide.
- **1 test préexistant adapté** : `test_pending_generation_result_invalidated_after_rename` (`test_main_window_rename_project.py`) encodait directement l'ancien comportement (destruction silencieuse sans guard) — un `rename_project()` réel non mocké provoquerait désormais un vrai dialogue bloquant. Adapté pour mocker le choix du guard (`"reject"`), atteignant le même état final par le nouveau chemin explicite ; `reset_for_workspace_change()` reste vérifié comme filet de sécurité toujours câblé.
- Non-régression complète : `test_inference_page.py` (109/109), `test_main_window_close_event.py` (25/25), `test_main_window_new_project.py` (36/36), `test_main_window_rename_project.py` (15/15), et les fichiers adjacents instanciant `MainWindow` (`test_dashboard_page.py`, `test_main_toolbar.py`, `test_main_window_comfyui_settings.py`, `test_main_window_initial_size.py`, `test_main_window_ollama_settings.py`, `test_main_window_prompts_to_inference.py` — 30/30, aucune modification requise).
- **1552/1552 tests verts au total** (1517 précédents + 35 nets nouveaux), une exécution complète `unittest discover`, 175.3s, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `MainWindow`/`InferencePage`/`WorkspaceManager`/`CharacterManager`/`PromptsPage` réels, Workspaces temporaires réels sur disque (y compris un renommage physique réel), seuls les dialogues modaux simulés — **PASS, 29/29 assertions** : Accept réel + New Project (persistence réelle vérifiée dans `project.json`, fichier préservé), Reject réel + Open Project (suppression physique réelle), Cancel + fermeture (refusée, `shutdown()` jamais atteint), Accept avec échec de persistence injecté (transition refusée, fichier/pending préservés, retry possible), pending + prompt Inference dirty (deux guards indépendants résolus séparément), pending + `PromptsPage` dirty (guard pending fonctionnel indépendamment de la Page dirty), ordre exact des 6 guards, Accept réel suivi d'un renommage physique réel (chemin remappé, fichier intact, projet réouvert valide), aucun pending → aucun dialogue.

### État du projet (Mission 084)

1552/1552 tests automatisés verts. Commit fonctionnel `5cd63b0` (`feat: protect pending generation result from silent loss on context change`), tag `v0.2-mission084`, GitHub Release publiée. Voir `docs/missions/MISSION_084.md` pour le détail complet.

---
