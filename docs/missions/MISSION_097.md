# Mission 097 — Training Contract + OneTrainer Configuration Adapter + Dataset Materialization

> **MISSION CLÔTURÉE, GITHUB RELEASE PUBLIÉE.** Commit fonctionnel `0dd44ec787d083ad3b82be5eb8c60b74b9f9421e`, tag annoté `v0.2-mission097` sur ce même commit. Voir section 12 pour l'investigation complète de l'incident natif STATUS_HEAP_CORRUPTION, section 13 pour l'état d'avancement final et section 14 pour la clôture Git.

## 1. Contexte

L'audit post-Mission 096 a établi que Training reste, aujourd'hui, un CRUD pur (`Training` = 3 champs scalaires, `TrainingManager` = create/select/update_name/delete, aucune exécution, aucun appel à un moteur) — alors qu'Inference dispose désormais d'une chaîne réellement opérationnelle jusqu'à ComfyUI (Mission 096). Un premier mini-audit architectural Training a établi factuellement l'état du pipeline existant, comparé les moteurs envisageables, et recommandé OneTrainer comme premier moteur cible — validé par l'architecte, avec des arbitrages précis sur la frontière Domain/adapter, les valeurs par défaut, la matérialisation du dataset et l'emplacement du résultat.

Ce document est le contrat de Mission 097, resserré à la demande explicite de l'architecte : **préparer le véritable pipeline Training (contrat de données, traducteur OneTrainer, matérialisation du dataset, validation structurelle réelle) sans encore lancer OneTrainer** — évitant délibérément toute UX intermédiaire (« Générer → lancer manuellement → importer ») vouée à être remplacée dès la mission suivante.

## 2. Objectif

`Dataset Toolkit → Training générique → concept OneTrainer matérialisé → configuration OneTrainer réelle → validation par le vrai TrainConfig installé`, sans lancement d'entraînement, sans suivi de progression, sans annulation, sans import (même temporaire) dans la Bibliothèque centrale.

## 3. Mini-audit — format OneTrainer réellement observé (installation locale, lecture seule)

Installation vérifiée : `J:\Programmes\Onetrainer\` (OneTrainer réellement installé sur cette machine, aux côtés de `J:\Programmes\kohya_ss\`). Aucun fichier de cette installation n'a été modifié pendant cet audit.

### 3.1 Point d'entrée CLI headless — confirmé

`scripts/train.py` (lu intégralement) : `TrainArgs.parse_args()` exige `--config-path` (obligatoire) et accepte `--secrets-path` (optionnel, identifiants cloud) — aucune interaction UI requise. Chargement : `TrainConfig.default_values().from_dict(json.load(f))` (merge sur des valeurs par défaut complètes — structurellement, aucune clé n'est obligatoire, un JSON vide chargerait sans erreur). Aucun flag `--validate-only`/`--dry-run` n'existe dans `TrainArgs`.

### 3.1bis Mécanisme de migration de version — découvert pendant le smoke test réel, non anticipé par le mini-audit initial

Le smoke test réel (validation via le vrai `TrainConfig` installé, §7) a révélé un second mécanisme dans `BaseConfig.from_dict()` distinct du simple merge sur défauts déjà vérifié en §3.1 : si la clé top-level `"__version"` est **absente** du JSON, `from_dict()` initialise `version = 0` et rejoue **toutes** les fonctions de migration enregistrées jusqu'au `config_version` courant de l'installation (confirmé : `TrainConfig.config_version = 10` sur cette installation, `grep config_version= TrainConfig.py`). Chacune de ces migrations suppose transformer un **ancien fichier de sauvegarde OneTrainer complet**, jamais un JSON volontairement minimal construit par un tiers — rejouées contre le dict minimal de ce module, elles échouent (`KeyError: 'weight_dtype'` dans `__migration_9`, confirmé empiriquement via le vrai parseur).

**Correctif retenu, vérifié empiriquement** : le dict produit inclut désormais toujours `"__version": _AUDITED_CONFIG_VERSION` (= 10), ce qui rend la boucle de rejeu des migrations un no-op et laisse s'exécuter le simple merge sur défauts déjà conçu en §3.1/§3.2 — revérifié champ par champ contre le vrai `TrainConfig` installé (§7).

**`_AUDITED_CONFIG_VERSION` n'est jamais présenté comme une constante universelle du format OneTrainer** — c'est le `config_version` de **cette installation précise**, au moment de cette mission. Le contrat de M097 est explicitement : *M097 produit une configuration compatible avec la version OneTrainer réellement auditée sur cette installation, dont `TrainConfig.config_version == 10`.* Aucune détection dynamique de version n'est introduite en production par cette mission (voir §8 hors périmètre) — une constante documentée, figée, suffit au périmètre de M097, qui ne lance jamais OneTrainer.

**Dette/condition future explicitement actée** : toute mise à jour de l'installation OneTrainer sur cette machine exige de revalider `TrainConfig.config_version` avant de continuer à considérer les configurations produites par ce module comme compatibles — sans cette revalidation, un JSON envoyé avec un `"__version"` obsolète pourrait à nouveau déclencher un rejeu de migrations inapproprié (dans un sens ou dans l'autre selon que la version installée a augmenté ou non). La mission qui lancera réellement OneTrainer décidera si cette vérification doit devenir une précondition d'exécution (runtime), pas cette mission-ci.

### 3.2 Un seul fichier JSON suffit — confirmé en source

`DataLoaderMgdsMixin.py:24-27` : `concepts = config.concepts; if concepts is None: charger concept_file_name`. Les concepts (= Dataset) peuvent donc être embarqués directement sous la clé `"concepts"` du même JSON — aucun second fichier `concepts.json` n'est nécessaire. Décision retenue : **toujours embarquer `"concepts"` directement**.

### 3.3 Formes réellement acceptées pour le modèle de base — confirmé en source

Lecture de `StableDiffusionModelLoader.load()` (et confirmée identique pour SDXL via `StableDiffusionXLModelLoader.py`) : la chaîne `base_model_name` est essayée dans cet ordre — format interne (`meta.json`), **dossier Diffusers local ou identifiant HuggingFace Hub** (les deux passent par le même `from_pretrained(base_model_name, ...)`, indiscernables au niveau du code), **fichier `.safetensors` local unique** (`download_from_original_stable_diffusion_ckpt(..., from_safetensors=True)`), et enfin **fichier `.ckpt` local legacy** (explicitement marqué « legacy code... some features may not be supported » dans le code lui-même).

**Décision retenue** : le Domain n'appelle jamais ce concept `base_model_name`. Nouveau champ générique `Training.base_model_source: str` — une chaîne opaque pour le Toolkit (chemin local `.safetensors`/`.ckpt`/dossier Diffusers, ou identifiant Hugging Face), jamais interprétée ni validée par le Domain. **Seule forme activement exposée par l'UI de M097 : un chemin local** (fichier ou dossier), cohérent avec la convention déjà établie partout ailleurs dans le Toolkit (aucun flux de téléchargement réseau n'existe nulle part dans l'application aujourd'hui — introduire un téléchargement HuggingFace implicite serait une décision UX/réseau distincte, non demandée, non tranchée). La forme Hugging Face reste techniquement acceptée par le traducteur sans validation supplémentaire (l'utilisateur avancé peut toujours la saisir), mais n'est ni suggérée ni documentée comme le chemin recommandé.

### 3.4 Architecture — mapping minimal retenu

`ModelType` (`modules/util/enum/ModelType.py`) est un enum fermé d'environ 25 valeurs (SD1.5/2.0/2.1/3/3.5, SDXL, Wuerstchen, PixArt, Flux, Sana, HunyuanVideo, HiDream, Chroma, Qwen, Z-Image, Ernie...) — **jamais exposé au Domain**, conformément à l'arbitrage.

Architectures génériques retenues pour `Training.architecture` :
- **`SD15`** → `ModelType.STABLE_DIFFUSION_15` — confirmé supporté (`StableDiffusionLoRAModelLoader.py`, preset `#sd 1.5 LoRA.json` réel).
- **`SDXL`** → `ModelType.STABLE_DIFFUSION_XL_10_BASE` — confirmé supporté (`StableDiffusionXLLoRAModelLoader.py`, preset `#sdxl 1.0 LoRA.json` réel).
- **`FLUX`** → `ModelType.FLUX_DEV_1` — **structurellement supporté** (`FluxLoRAModelLoader.py` réellement présent, preset `#flux LoRA.json` réel) et le pipeline de matérialisation Dataset (§3.5) est indépendant de l'architecture, donc sans blocage technique connu. **Réserve factuelle non bloquante pour M097** (qui n'exécute rien) mais pertinente pour la mission suivante : le GPU de cette machine (Quadro P4000, 8 Go VRAM, confirmé via `/system_stats` pendant le smoke Mission 096) est en dessous des recommandations usuelles pour Flux même quantifié — un entraînement Flux réel sur cette machine reste non vérifié et probablement risqué. Décision proposée : **inclure `FLUX` dans l'enum générique** (le mapping est trivial et gratuit à définir correctement dès maintenant), sans le mettre en avant comme choix par défaut dans l'UI.

L'adapter OneTrainer possède l'unique responsabilité de la traduction `architecture Toolkit → ModelType` — un dictionnaire fermé à 3 entrées, jamais un mécanisme générique.

### 3.5 Dataset → concept OneTrainer — découverte structurante

`ConceptConfig.path: str` (`ConceptConfig.py:130`) : un concept OneTrainer est **un chemin de dossier unique**, jamais une liste de fichiers. `DataLoaderText2ImageMixin.py:79` confirme le mécanisme de caption : `ModifyPath(in_name='image_path', ..., extension='.txt')` — **chaque image doit avoir un fichier `.txt` de même nom qu'elle, dans le même dossier** (convention sidecar standard). `prompt_source="sample"` (défaut) sélectionne ce mode.

`Dataset.images` (Toolkit) autorise des références externes sans copie physique (passthrough, Missions 044/082) — les images d'un Dataset ne vivent donc pas nécessairement toutes dans un seul dossier aujourd'hui. **Une matérialisation réelle est donc structurellement nécessaire**, pas une simple sérialisation JSON — voir contrat détaillé §6.

Aucun champ OneTrainer dédié n'existe pour un « trigger word » — il se réalise entièrement par le **contenu** des fichiers caption. Conformément à l'arbitrage de l'architecte, ce contenu (le mot-clé seul, M097) est explicitement documenté comme **minimum fonctionnel provisoire** — voir §6.4.

### 3.6 Emplacements déterministes — réutilisation d'une convention déjà existante

`WorkspaceStorage.DIRECTORIES` (`workspace_storage.py:37-51`) déclare déjà, et crée systématiquement dans **chaque** Workspace depuis les toutes premières missions, un dossier top-level `training/` (aux côtés de `datasets/`, `models/loras/`, etc.) — **jamais consommé par aucun code à ce jour**. C'est l'emplacement naturel, déjà réservé, pour tout ce que Mission 097 doit produire :
- Concept matérialisé : `<Workspace.root>/training/<training_id>/concept/`
- Résultat attendu : `<Workspace.root>/training/<training_id>/output/lora.safetensors`

**Aucun chemin absolu n'est stocké dans `Training`** — les deux emplacements se dérivent entièrement de `Workspace.root` (déjà connu de tout appelant via `WorkspaceManager`) et de `training_id` (déjà un champ existant). `training_id` garantit à lui seul l'isolation totale entre sessions, y compris entre deux sessions du même Dataset.

**Nommage sans collision** : `WorkspaceStorage.resolve_collision_free_name(source, destination_folder, also_avoid=frozenset())` (`workspace_storage.py:294`) existe déjà et résout exactement le problème soulevé par l'architecte (deux images `001.png` de dossiers sources différents) — nom de la source si libre, sinon suffixe `_1`, `_2`, ... jamais d'écrasement. **Réutilisable directement pour la matérialisation.**

**Nuance technique identifiée, à trancher pendant l'implémentation** : `WorkspaceStorage.copy_into_workspace()` (qui combine cette même résolution de nom avec la copie physique) contient un court-circuit délibéré — si la source est déjà à l'intérieur de `workspace_root`, aucune copie n'est faite, le chemin d'origine est retourné tel quel (comportement correct pour son usage actuel : import Dataset/LoRA, jamais pour de la matérialisation). **Ce court-circuit serait incorrect pour la matérialisation d'un concept**, qui doit toujours produire une copie physique réelle dans le dossier du concept, quelle que soit la localisation de la source. M097 devra donc soit introduire une primitive de copie dédiée (toujours copier, réutilisant uniquement `resolve_collision_free_name()`), soit contourner explicitement ce court-circuit — décision de conception à trancher précisément pendant l'implémentation, pas ici.

### 3.7 Valeurs par défaut — provenance documentée par architecture

Presets LoRA réels inspectés : `#sd 1.5 LoRA.json`, `#sdxl 1.0 LoRA.json`, `#flux LoRA.json`.

| Champ | SD1.5 (réel) | SDXL (réel) | Flux (réel) | Décision Toolkit |
|---|---|---|---|---|
| `resolution` | `"512"` | `"1024"` | `"768"` | **Par architecture, jamais un défaut commun** — trop différent pour être générique (confirmé empiriquement par les 3 presets officiels eux-mêmes) |
| `learning_rate` | `0.0003` | `0.0003` | `0.0003` | **Défaut commun 0.0003** — identique dans les 3 presets officiels réels, donc un partage générique n'est pas artificiel ici |
| `lora_rank` | *(non surchargé — défaut `16`)* | *(non surchargé)* | *(non surchargé)* | **Défaut commun 16** — aucun des 3 presets officiels ne juge nécessaire de le changer par architecture |
| `lora_alpha` | *(non surchargé — défaut `1.0`)* | *(non surchargé)* | *(non surchargé)* | **Défaut commun 1.0** — même constat |
| `epochs` | *(non surchargé — défaut `100`)* | *(non surchargé)* | *(non surchargé)* | **Défaut commun 100** — même constat |
| `training_method` | `"LORA"` | `"LORA"` | `"LORA"` | Constante Toolkit, jamais configurable en M097 |

Chaque valeur ci-dessus provient soit d'un preset réel explicitement inspecté, soit de `TrainConfig.default_values()` elle-même (jamais d'une valeur inventée) — traçabilité conforme à la demande de l'architecte.

## 4. Frontière Domain / Adapter — verrouillée

**Dans `Training` (Domain, générique)** : `base_model_source`, `architecture` (`"SD15"`/`"SDXL"`/`"FLUX"`, chaîne validée contre un ensemble fermé côté Manager/UI, jamais l'enum OneTrainer), `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `trigger_word` (caption minimale provisoire, §6.4).

**Strictement dans l'adapter OneTrainer, jamais dans le Domain** : `model_type` (résultat de la traduction), `training_method` (constante), `optimizer`/`optimizer_defaults`, `learning_rate_scheduler` et ses paramètres, `workspace_dir`/`cache_dir`/`concept_file_name`, tous les champs `vae`/`unet`/`text_encoder`/`transformer` (dtype), la structure `ConceptConfig` complète au-delà du strict nécessaire (augmentation d'image, dropout de tags, etc. — non exposés).

## 5. Contrat définitif par couche

1. **`src/domain/training.py`** : `Training` étendu avec les 7 champs génériques ci-dessus, tous à défaut sûr (`""`/`0`/valeurs de §3.7) pour une compatibilité stricte avec tout `project.json` existant sans ces clés — motif déjà établi partout ailleurs dans ce codebase (`data.get(key, default)`).
2. **Nouveau module `src/engines/onetrainer_config.py`** (nom exact à confirmer en implémentation, symétrique à `comfyui_workflows.py`) : fonction(s) pures construisant le dict `TrainConfig` réel — mapping architecture → `model_type`, insertion de `base_model_source` en `base_model_name`, `training_method="LORA"`, `resolution`/`epochs`/`learning_rate`/`lora_rank`/`lora_alpha` transmis, `output_model_destination` dérivé de `training/<training_id>/output/lora.safetensors`, `concepts` embarqué directement (§3.2). Aucune connaissance de `Workspace`/`Training` au-delà des valeurs qu'on lui passe — même isolement que `comfyui_workflows.py` vis-à-vis d'`InferencePage`.
3. **Nouveau module de matérialisation** (nom à confirmer) : copie déterministe des images du Dataset actif vers `training/<training_id>/concept/` (jamais de modification des sources), nommage sans collision via `WorkspaceStorage.resolve_collision_free_name()` (§3.6), génération d'un fichier `.txt` par image copiée contenant `trigger_word` (§6.4) — conçu pour qu'une future source de caption (par image, par dataset, générée) puisse remplacer ce contenu sans changer la structure du dossier produit.
4. **`TrainingManager`** : inchangé dans sa forme CRUD ; les nouveaux champs suivent le même patron `update_*()` déjà établi pour tous les Managers Character-owned (idempotence stricte, rollback local sur échec de `save()` — Missions 068/070).
5. **`TrainingPage`** : nouveaux champs UI pour les 7 paramètres génériques, plus une action explicite déclenchant matérialisation + génération de la configuration + validation (§7) — libellé exact à définir en implémentation, aucun bouton « Lancer l'entraînement ».
6. **Aucune modification de `LoRALibraryManager`/`LoRAManager`/`ComfyUIEngine`** — la connexion à la Bibliothèque centrale reste un point d'intégration documenté, pas implémenté.

## 6. Contrat de matérialisation du Dataset

1. **Déterministe** : mêmes entrées → même contenu produit (à l'ordre de nommage `_1`/`_2` près, stable si l'ordre des images du Dataset est stable).
2. **Isolée par `training_id`** : `training/<training_id>/concept/`, jamais de dossier partagé entre deux sessions.
3. **Reproductible/nettoyable/reconstructible** : le dossier peut être supprimé et régénéré à l'identique à partir du Dataset source et de `trigger_word` — aucun état non reconstructible n'y est stocké.
4. **Aucune modification des images sources du Dataset** — copie uniquement, jamais un déplacement, jamais une écriture dans le dossier d'origine.
5. **Sans collision de nommage** — réutilisation de `resolve_collision_free_name()` (§3.6), garantissant que deux sources `001.png` distinctes produisent deux fichiers distincts dans le concept matérialisé.
6. **Captions — minimum fonctionnel explicitement provisoire** : chaque image copiée reçoit un fichier `.txt` de même nom contenant `trigger_word` (chaîne vide acceptée, caption vide alors valide). Cette décision est **documentée comme provisoire** dans le code et cette mission — une future source de caption (par image, importée, générée) remplacera ce contenu sans modification de la structure de dossier ni du contrat de nommage.

## 7. Contrat de validation (smoke test M097)

Conditions strictes autorisées par l'architecte : import et exécution en lecture de `modules.util.config.TrainConfig` (l'installation OneTrainer réellement présente), chargement du JSON produit par le Toolkit, confirmation qu'il round-trip sans exception. **Jamais** `trainer.start()`/`trainer.train()`/`create_trainer()`, **jamais** de sous-processus, **jamais** l'UI OneTrainer, **aucune** modification de l'installation OneTrainer, **aucune** installation/mise à jour de dépendance, **aucun** usage GPU volontaire.

## 8. Hors périmètre explicite

Lancement d'OneTrainer (`scripts/train.py` en sous-processus), suivi d'état (running/succeeded/failed), progression, annulation, récupération/import réel du `.safetensors` dans la Bibliothèque centrale (le chemin est déterministe et prêt, l'import lui-même n'est pas déclenché), tout provider autre qu'OneTrainer, toute UX d'import manuel transitoire, captioning avancé (au-delà du trigger word), Kohya_ss, tout provider cloud.

## 9. Tests et smoke tests prévus (implémentation future, non commencée)

- **Automatisé, sans OneTrainer** : round-trip du contrat `Training` étendu (compatibilité `project.json` existants sans les nouveaux champs) ; génération de la configuration OneTrainer (fonction pure — inspection du dict produit, mapping architecture → `model_type`) ; matérialisation sur un Dataset de test (vraies copies sur disque temporaire, vrais fichiers `.txt`, collision de noms provoquée délibérément et vérifiée résolue) ; dérivation des chemins déterministes (`training/<training_id>/concept/`, `.../output/lora.safetensors`) sans jamais stocker de chemin absolu dans `Training`.
- **Smoke test réel autorisé** : chargement du JSON produit par le Toolkit via la classe `TrainConfig` réelle de l'installation OneTrainer présente sur cette machine — round-trip sans exception, aucune exécution, aucun GPU.
- **Non couvert par M097** : toute preuve qu'un entraînement réel aboutit — nécessite la mission suivante.

## 10. Ce qui reste pour la mission suivante

`configuration validée → scripts/train.py (sous-processus) → état running/succeeded/failed → récupération du .safetensors produit → import réel dans la Bibliothèque centrale`. Progression fine et annulation restent elles-mêmes différables en une mission ultérieure si leur propre audit le démontre.

## 11. Critères de clôture

- Contrat `Training` étendu, compatibilité stricte des `project.json` existants démontrée par test.
- Configuration OneTrainer générée pour au moins SD15 et SDXL, conforme aux formats réellement observés (§3.3-§3.7), avec traçabilité de chaque défaut retenu.
- Matérialisation du Dataset conforme au contrat §6, testée avec un cas de collision de noms réel.
- Validation réelle via `TrainConfig` de l'installation OneTrainer présente : round-trip sans exception, sur au moins un cas SD15 et un cas SDXL.
- Aucun lancement, aucune modification, aucune installation touchant OneTrainer.
- Suite complète verte, nombre exact confirmé.

## 12. Incident natif STATUS_HEAP_CORRUPTION — investigation et clôture

### 12.1 Découverte

La suite complète (`unittest discover -s tests -p "test_*.py"`, exécutée en un seul processus) a présenté des plantages natifs intermittents `Windows fatal exception: code 0xc0000374` (STATUS_HEAP_CORRUPTION) une fois l'implémentation de M097 en place, avec une fréquence apparemment plus élevée qu'avant M097. Le site du plantage variait d'une exécution à l'autre (`MainWindow.__init__`, `InferencePage.__init__`, à l'intérieur même du timer du safety net Qt) — signature cohérente avec une corruption mémoire native qui se manifeste après sa cause réelle, jamais à l'endroit qui l'a provoquée.

### 12.2 Isolation différentielle A/B/C

Méthode : worktree Git isolé, réapplication progressive des groupes de fichiers M097 sur une base `main` propre, comparaison de fréquence de plantage.

- **Groupe A** (Domain/Manager/adapter OneTrainer, aucun changement Qt) : stable.
- **Groupe A+C** (A + nouveaux tests, sans le nouvel UI `TrainingPage`) : stable.
- **Groupe A+B** (A + nouvel UI `TrainingPage`, sans les nouveaux tests) : plantage reproductible.
- **M097 complet (A+B+C)** : plantage reproductible.

Conclusion : le corrélat est le nouvel UI de `TrainingPage`, jamais les nouveaux tests. Une bissection plus fine (suite préfixe déterministe de 22 fichiers reproduisant le point de plantage, construction/destruction isolée de widgets) a établi qu'il s'agit d'un **effet de seuil sur le nombre brut d'objets Qt** ajoutés par `TrainingPage` (mesuré : 19 objets `QObject` descendants avant M097, 75 après — ~4×), indépendant de la nature des champs et indépendant de tout câblage de signal (des variantes strictement construites, sans aucun `connect()` au-delà du code baseline, reproduisaient déjà le plantage).

### 12.3 Amplificateur identifié et supprimé — polling du Qt dialog safety net

`tests/integration/_qt_dialog_safety_net.py` (Mission 091) faisait reposer sa protection contre les dialogues réels non mockés sur deux mécanismes : un `eventFilter` sur `QEvent.Show`, et un `QTimer` répétitif de 15 ms parcourant inconditionnellement `QApplication.topLevelWidgets()`. Une comparaison contrôlée (safety net normal vs polling désactivé, M097 complet dans les deux cas) a montré 3/3 suites complètes propres avec le polling désactivé, contre un taux de plantage proche de 100 % avec le polling actif — le plantage a même été surpris une fois littéralement à l'intérieur de `_scan()`, pendant une séquence réelle de fermeture/génération.

**Correctif appliqué** (tests uniquement, `tests/integration/_qt_dialog_safety_net.py`) : suppression du `QTimer` périodique et de `_scan()`. L'`eventFilter` + fermeture différée via `QTimer.singleShot(0, ...)` suffisent seuls — vérifié par les tests dédiés adaptés au nouveau contrat (`tests/integration/test_qt_dialog_safety_net.py`, 7/7). Ce n'est pas un défaut de M097 : c'est un amplificateur indépendant, préexistant dans l'infrastructure de test, que M097 rend simplement plus facile à déclencher en élevant la pression ambiante d'objets Qt.

### 12.4 Simplification structurelle conservée — QFormLayout

`TrainingPage` a été restructurée pour regrouper ses 8 champs génériques dans un unique `QFormLayout` (pattern déjà établi dans `LoRAPage.metadata_form`, `SettingsPage`, `CharactersPage`) au lieu de 6 `QHBoxLayout` séparés — même fonctionnalité, mêmes champs, structure plus simple, cohérente avec l'idiome déjà utilisé ailleurs dans le projet. Mesure : réduction modeste du nombre d'objets Qt (75 → 71 objets descendants). **Cette simplification est conservée dans M097 comme amélioration structurelle légitime, jamais présentée comme la correction du plantage** — elle ne l'est pas à elle seule (une suite complète avec cette seule simplification, safety net non corrigé, a encore plantué une fois sur deux tentatives).

### 12.5 Fuite de fenêtres Qt — dette de harness préexistante, non introduite par M097, non corrigée

Investigation plus profonde après le correctif du safety net : une mesure directe de `QApplication.topLevelWidgets()` avant/après chacun des 126 tests réels construisant une `MainWindow` (tous les fichiers `test_main_window_*`/`test_dashboard_page`/`test_main_toolbar`) a révélé une croissance quasi monotone (121/126 tests laissent le compteur plus haut qu'avant), avec un drift net de **+16 sur 126 tests**.

**Cette fuite est strictement identique en baseline et en M097 complet (+16 dans les deux cas)** — M097 n'introduit ni n'aggrave le nombre de fenêtres fuitées ; il augmente uniquement le poids de chaque fenêtre déjà fuitée (via `TrainingPage`, 19 → 75 objets), ce qui rend le seuil de corruption native plus facile à atteindre au fil d'une suite longue.

Deux tentatives de correction ont été explorées et **toutes deux rejetées** après preuve empirique qu'elles ne corrigent pas (voire aggravent) la fuite :

- **`Qt.WA_DeleteOnClose` sur `MainWindow`** (prototype worktree uniquement, jamais appliqué en production) : aucun effet mesuré (drift toujours +16) — cause identifiée précisément : cet attribut ne déclenche la destruction C++ que si le widget a été affiché (`.show()`) au moins une fois avant `close()`, or **aucune des 26 `MainWindow()` de la suite n'appelle jamais `.show()`**. Confirmé isolément (widget nu affiché vs non affiché) et sur `MainWindow` elle-même.
- **Helper tests-only `close_and_delete_widget()`** (`close()` puis, si accepté, `deleteLater()` explicite + purge de la file Qt) : appliqué aux 22 sites de nettoyage `MainWindow` des 9 fichiers concernés par la mesure des 126 tests (les appels directs à `closeEvent()` pour tester les guards de fermeture n'ont jamais été touchés). Résultat mesuré : **aggravation nette, drift +254 au lieu de +16**, avec un nouvel échec de test lié au timing. Cause : un `deleteLater()` explicite sur un widget top-level jamais affiché n'est pas non plus traité par de simples `processEvents()` sans boucle `exec()` réelle — le helper a été entièrement rejeté et retiré du worktree diagnostique, il n'entre dans aucune branche du dépôt.

**Aucun défaut d'ownership Qt, de signal, de widget ou de fixture propre à M097 n'a été identifié.** Un stress test isolé nettement plus agressif que la suite réelle (500 cycles de construction/destruction de `TrainingPage`, 100 de `MainWindow`, hors harness `unittest`) n'a jamais reproduit le plantage — celui-ci dépend du contexte allocateur cumulé de la suite `unittest` complète (dont le mécanisme précis de rétention n'a pas été élucidé), pas de la seule construction répétée des widgets.

**Cette fuite est actée comme dette préexistante du harness Qt monoprocessus, indépendante de Training, à auditer ultérieurement dans une mission dédiée** — elle n'est pas présentée comme corrigée par M097.

### 12.5bis Ordre d'armement du safety net — correctif ciblé trouvé et validé

Investigation complémentaire, ciblée sur une anomalie précise : `test_main_window_new_project.py` plantait de façon reproductible en isolation totale (3/3), toujours dans `MainWindowInferencePendingResultGuardTest::setUp()`, exactement pendant `MainWindow()` — avec le safety net déjà armé à ce moment (`start_dialog_guard()` appelé avant la construction de la fenêtre).

Audit exhaustif de toutes les classes armant le safety net (`grep` sur `start_dialog_guard()` dans tout `tests/integration/`) : 5 classes construisent une `MainWindow` réelle après avoir armé le guard (`MainWindowInferencePendingResultGuardTest`, `MainWindowNewOpenGenerationActiveNonRegressionTest`, `MainWindowRenamePendingResultGuardTest`, `MainWindowRenameGenerationActiveGuardTest`, `MainWindowCloseEventRealStateTest`) ; 2 autres arment le guard mais ne construisent pas de `MainWindow` (juste une `Page` isolée — `InferencePageGenerationActiveGuardTest`, `LoRAPageComfyUIExposureTest`). Seule la première des 5 a jamais présenté de plantage.

**Correctif appliqué, strictement localisé à cette seule classe** (`tests/integration/test_main_window_new_project.py`, `MainWindowInferencePendingResultGuardTest::setUp()`) : `MainWindow()` est désormais construite **avant** l'armement du safety net (`start_dialog_guard()`), puisque le guard n'a aucune responsabilité pendant la construction elle-même — seulement pendant le corps du test et la fermeture réelle. L'ordre LIFO des `addCleanup()` est préservé exactement (`window.close()` s'exécute toujours avant `stop_dialog_guard()` au teardown, en enregistrant le cleanup de `stop_dialog_guard` en premier).

**Preuve empirique, avant/après, sur le même fichier isolé** :
- Ordre d'origine (guard avant `MainWindow()`) : M097 = 0/3 propre (baseline testé aussi = 2/3 propre, confirmant que même la baseline n'est pas totalement immunisée — juste moins fréquemment touchée).
- Nouvel ordre (`MainWindow()` avant le guard), M097 : **5/5 propre** en isolation.

Conformément à la consigne explicite de ne pas généraliser automatiquement, **les 4 autres classes partageant le même ordre "guard avant `MainWindow()`" n'ont pas été modifiées** — aucune n'a jamais présenté de plantage dans aucune des exécutions de cette investigation, et les modifier sans preuve aurait été un changement non justifié.

### 12.6 Stratégie de validation finale retenue et résultats

Compte tenu de cette dette baseline désormais démontrée, M097 n'exige pas qu'un unique processus Python exécute la suite complète (~1900 tests) jusqu'au bout sans jamais atteindre le seuil de corruption natif. La validation finale a combiné :

1. **Tests ciblés M097 + safety net + fichiers consommateurs du safety net** (processus unique) : `test_training_roundtrip.py` + `test_onetrainer_config.py` + `test_qt_dialog_safety_net.py` = 116/116 ; `test_inference_page.py` + `test_main_window_rename_project.py` + `test_main_window_new_project.py` + `test_main_window_close_event.py` + `test_lora_roundtrip.py` (regroupés) = 515/515. **Tous verts, aucun échec, aucun plantage.**
2. **Couverture complète de la suite canonique (41 fichiers), partitionnée en processus Python frais — avant le correctif d'ordre §12.5bis** : 40 fichiers passés chacun dans son propre processus isolé, tous verts (1847 tests). Le 41ᵉ fichier (`test_main_window_new_project.py`) a plantué de façon reproductible en isolation totale (3/3 tentatives, toujours exactement la même classe/ligne — `MainWindowInferencePendingResultGuardTest`, `setUp()` ligne 610). Regroupé avec un seul autre fichier léger dans un même processus frais (méthode explicitement acceptée par l'architecte), ce fichier passait proprement (45/45). Total à cette étape : 1889/1889, 0 échec, 0 erreur, aucun test retiré.
3. **Une tentative de suite complète monoprocessus, avant le correctif d'ordre** : a planté avec `0xc0000374`, exactement à la même classe/ligne que ci-dessus.
4. **Après le correctif d'ordre du safety net (§12.5bis)** : `test_main_window_new_project.py` seul, en isolation totale, **5/5 propre** (contre 0/3 avant correctif). **Couverture partitionnée complète re-exécutée : 1889/1889 tests, sur la totalité des 41 fichiers, chacun en isolation totale sans aucun regroupement nécessaire cette fois — 0 échec, 0 erreur, 0 fichier planté.** **Deux suites complètes monoprocessus consécutives exécutées après le correctif : 1889/1889 les deux fois, aucun `STATUS_HEAP_CORRUPTION`, aucun dialogue bloquant, aucune intervention humaine.**
5. **Smoke test réel OneTrainer** (`TrainConfig` de l'installation réelle, `J:\Programmes\Onetrainer\`) : 18/18 PASS pour SD15 et SDXL — vérification préalable `TrainConfig.config_version == _AUDITED_CONFIG_VERSION` passée, matérialisation réelle du Dataset (copies physiques, sidecars `.txt`, collision de noms résolue entre deux images `001.png` de dossiers sources différents), configuration round-trip sans exception via le vrai parseur, aucun entraînement, aucun `trainer.start()`/`trainer.train()`, aucun sous-processus Training, aucune modification de l'installation OneTrainer, aucun usage GPU.

## 13. État d'avancement

Mini-audit architectural et mini-audit ciblé sur le format OneTrainer **terminés**, contrat verrouillé sur la base de vérifications directes en source (jamais de supposition sur le format réel). Implémentation **terminée** (Domain/Manager/adapter/UI/tests). Incident natif STATUS_HEAP_CORRUPTION rencontré pendant la validation, investigué en profondeur et documenté en détail en section 12 : cause de fond identifiée comme une dette préexistante du harness de test (fuite de fenêtres Qt monoprocessus, drift `+16` identique en baseline et en M097 sur 126 tests), non introduite par M097 mais rendue plus probable par le poids accru de `TrainingPage` (19 → 75 objets Qt descendants). Un amplificateur indépendant (polling du safety net) a été identifié et corrigé (tests uniquement). Deux tentatives de correction du lifecycle des fenêtres Qt (`WA_DeleteOnClose`, helper `deleteLater()` tests-only) ont été explorées et rejetées après preuve qu'elles n'apportent aucune amélioration (voire l'aggravent) — aucune n'est entrée dans le dépôt.

Une dernière anomalie ciblée (§12.5bis) — un plantage reproductible spécifique à une seule classe de test, lié à l'ordre d'armement du safety net avant la construction de `MainWindow` — a été investiguée, corrigée par un changement minimal et strictement localisé (ordre des deux lignes dans `setUp()`, aucune ligne de production touchée), puis validée par une preuve empirique avant/après (0/3 → 5/5 propre en isolation) sans généralisation aux autres classes non affectées.

**Validation finale, après ce dernier correctif** : tests ciblés M097/safety net verts, `test_main_window_new_project.py` 5/5 propre en isolation, couverture complète partitionnée 1889/1889 (0 échec, 0 erreur, 0 fichier planté, aucun regroupement nécessaire), **deux suites complètes monoprocessus consécutives, 1889/1889 les deux fois, aucun `STATUS_HEAP_CORRUPTION`**, smoke OneTrainer réel 18/18 PASS. **Critère de stabilité de l'architecte satisfait.**

## 14. Clôture Git

- Commit fonctionnel : `0dd44ec787d083ad3b82be5eb8c60b74b9f9421e` — *Add Training contract, OneTrainer configuration adapter, and dataset materialization*.
- Fichiers commités : `src/domain/training.py`, `src/managers/training_manager.py`, `src/ui/pages/training_page.py`, `src/engines/onetrainer_config.py` (nouveau), `tests/integration/_qt_dialog_safety_net.py`, `tests/integration/test_qt_dialog_safety_net.py`, `tests/integration/test_main_window_new_project.py`, `tests/integration/test_training_roundtrip.py`, `tests/integration/test_onetrainer_config.py` (nouveau), `docs/missions/MISSION_097.md` (nouveau).
- Tag annoté : `v0.2-mission097`, sur ce même commit exact (vérifié via `git rev-parse`).
- `main` et le tag poussés vers `origin` sans divergence ni commit étranger intercalé.
- GitHub Release `v0.2-mission097` : **publiée**, confirmée par l'architecte.
