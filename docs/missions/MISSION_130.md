# Mission 130 — OneTrainer Structured Value Validation Hardening

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en attente de validation finale de l'architecte.** Rédigé à la suite de l'audit post-M129 (couverture Training, dette de validation confirmée, candidats de mission) et du micro-audit technique en lecture seule qui l'a suivi (matrice exacte des 9 champs candidats, vocabulaire OneTrainer réel relu directement dans le code installé, contrat translator/UI, ordre validation/architecture gating), tous deux validés explicitement par l'architecte avec une décision produit/architecture importante (Contrat B, vocabulaire par rôle pour les dtypes). Implémentation conforme à ce contrat, **+37 tests nets (2672 → 2709 tests collectés)**, tous les tests ciblés M130 verts, une suite complète unique exécutée : **2709 collectés, 2707 passés, 2 échoués** — les deux échecs correspondent aux flakes historiques déjà documentés (`ForgeLifecycleManagerRealProcessTest`, `dialog_guard`) et n'ont pas été reproduits lors de leur reproduction isolée (1/1 vert chacun), aucun test M130 concerné — voir section "Résultats réels" en fin de document. Aucun smoke GPU requis ni exécuté.

## 1. Contexte

L'audit post-M129 a confirmé un défaut réel et démontrable dans `src/engines/onetrainer_config.py::build_training_config()` : neuf champs structurés (`learning_rate_scheduler`, `train_dtype`, les cinq `*_weight_dtype`, `optimizer`, `timestep_distribution`) sont des chaînes Domain permissives, transmises telles quelles vers la configuration OneTrainer générée, **sans aucune validation de vocabulaire**. Contrairement à `gradient_checkpointing_mode`, `text_encoder_stop_training_mode`/`_2` et `lora_layer_filter` — les quatre seuls champs qui possèdent déjà une validation de valeur dédiée (`_GRADIENT_CHECKPOINTING_VALUES`, `_STOP_TRAINING_MODE_VALUES`, `_LORA_LAYER_FILTER_TRANSLATION`) —, ces neuf champs n'ont aujourd'hui qu'un gating d'architecture (quand il existe), jamais un contrôle de la valeur elle-même.

Le chemin normal (UI Toolkit) restreint déjà les choix proposés à l'utilisateur à un sous-ensemble sûr. Le chemin réellement ouvert, confirmé par le micro-audit, est un `project.json` édité ou manipulé manuellement — aucune autre construction Domain n'existe dans `src/` en dehors de la construction UI normale (`TrainingManager.update()`) et du chargement disque (`Training.from_dict()`/`OneTrainerSettings.from_dict()`/`OneTrainerOptimizerSettings.from_dict()`), et aucun de ces chemins ne valide la valeur d'un champ structuré.

## 2. Problème démontré précisément

Le vrai `BaseConfig.from_dict()` d'OneTrainer (`J:\Programmes\Onetrainer\modules\util\config\BaseConfig.py:110-138`) résout une valeur de champ Enum par lookup du nom du membre (`self.types[name][data[name]]`, `Enum.__getitem__`). Toute la conversion par champ est encadrée par un `except Exception` **qui ne relève jamais l'exception** — la seule trace est un `print(f"Could not set {name} as {value}")` sur la sortie standard du processus OneTrainer, invisible pour Toolkit et pour l'utilisateur.

Conséquence exacte : une valeur non reconnue pour l'un des neuf champs ci-dessus n'est **jamais rejetée par personne** — ni par Toolkit (aucune validation), ni par OneTrainer (exception avalée). Le champ conserve alors silencieusement le default de la dataclass OneTrainer correspondante (ex. `Optimizer.ADAMW`, `LearningRateScheduler.CONSTANT`, `DataType.FLOAT_32`/`FLOAT_16` selon le composant, `TimestepDistribution.UNIFORM`), et l'entraînement démarre avec un réglage **différent** de celui que l'utilisateur pensait avoir configuré — sans aucune erreur, à aucune étape.

Mission 130 durcit précisément cette frontière translator/provider : elle transforme une défaillance silencieuse en une erreur explicite, au plus tôt possible côté Toolkit, sans toucher à aucune autre responsabilité.

## 3. Principe architectural retenu — Contrat B (validé par l'architecte)

Le translator **ne valide pas contre le sous-ensemble actuellement exposé par l'UI Toolkit**. Il valide contre les valeurs réellement reconnues et utilisables par OneTrainer pour le champ — et, lorsque c'est démontré nécessaire (cas des dtypes, voir section 4), pour le composant — concernés.

Séparation stricte des responsabilités, non négociable pour cette mission :

- **Translator** : « Cette valeur est-elle structurellement supportée par OneTrainer pour ce rôle ? » — question factuelle, tranchée par lecture directe du code OneTrainer installé, indépendante de tout choix produit Toolkit.
- **UI Toolkit** : « Quelles valeurs souhaitons-nous proposer aujourd'hui comme choix de premier rang ? » — question de scope produit, totalement indépendante, non traitée par cette mission.

Ce découplage évite qu'une future extension de l'UI (nouveau widget, nouveau choix de combo) n'oblige à modifier en parallèle la validation du translator, et évite qu'un `project.json` légitimement construit avec une valeur qu'OneTrainer sait traiter — même si l'UI Toolkit ne la propose pas encore — soit rejeté sans raison technique.

Aucune preuve trouvée pendant le micro-audit ne contredit ce choix : aucun test existant, aucune documentation de mission, aucun preset officiel OneTrainer déjà référencé par Toolkit n'utilise de valeur hors du vocabulaire réel OneTrainer — le Contrat B ne casse donc rien de l'existant.

## 4. Décision dtype — vocabulaire par rôle (option retenue)

**Rejetée** : une whitelist unique à 5 valeurs partagée par `train_dtype` et les cinq `*_weight_dtype`.

**Retenue** : des ensembles distincts reflétant les capacités réelles d'OneTrainer par rôle, avec au minimum une distinction TRAIN DTYPE / COMPONENT WEIGHT DTYPE, et pour les WEIGHT DTYPE une distinction supplémentaire entre `unet`/`transformer` (formats avancés réellement supportés) et `text_encoder`/`text_encoder_2`/`vae` (vocabulaire de base uniquement).

Source autoritaire relue directement dans le code OneTrainer installé (`J:\Programmes\Onetrainer`), pas déduite du micro-audit :

- Dropdown `train_dtype` officiel : `modules/ui/TrainingTab.py:394-399`.
- Fonction de construction des choix `weight_dtype` officiels : `modules/ui/ModelTab.py::__create_dtype_options(include_gguf=False, include_a8=False)`, lignes 351-372.
- Appels réels par composant : `unet.weight_dtype` → `__create_dtype_options(include_a8=True)` (ligne 424) ; `transformer.weight_dtype` → `__create_dtype_options(include_gguf=True, include_a8=True)` (ligne 460) ; `text_encoder.weight_dtype` (ligne 500), `text_encoder_2.weight_dtype` (ligne 518), `vae.weight_dtype` (ligne 562) → tous les trois appelés **sans** `include_a8` ni `include_gguf`, donc vocabulaire de base uniquement.

## 5. Listes exactes — DataType (13 membres réels, source `modules/util/enum/DataType.py:6-19`)

```
NONE, FLOAT_8, FLOAT_16, FLOAT_32, BFLOAT_16, TFLOAT_32, INT_8,
NFLOAT_4, FLOAT_W8A8, INT_W8A8, GGUF, GGUF_A8_FLOAT, GGUF_A8_INT
```

Aucune de ces 13 valeurs n'est utilisable telle quelle dans tous les contextes — confirmé par lecture directe de `ModelTab.py`/`TrainingTab.py`, pas supposé par appartenance commune à l'Enum.

### 5.1. `TRAIN_DTYPE_VALUES` — 4 valeurs

Source : `modules/ui/TrainingTab.py:394-399` (dropdown `train_dtype` officiel), littéralement :

```python
("float32", DataType.FLOAT_32),
("float16", DataType.FLOAT_16),
("bfloat16", DataType.BFLOAT_16),
("tfloat32", DataType.TFLOAT_32),
```

→ **`{FLOAT_32, FLOAT_16, BFLOAT_16, TFLOAT_32}`**.

Exclusions justifiées : `NFLOAT_4`/`FLOAT_8`/`INT_8`/`FLOAT_W8A8`/`INT_W8A8`/`GGUF*`/`NONE` ne sont jamais proposés par le dropdown `train_dtype` officiel d'OneTrainer, et leur consommation réelle (`torch.autocast(dtype=..., ...)` via `torch_dtype()`, `modules/util/dtype_util.py:44-48` + `modules/util/enum/DataType.py:31-41`) confirme que `NFLOAT_4` en particulier ne quantifie rien à ce niveau global — `torch_dtype()` retourne `None` pour ce cas (`case _: return None`), dégradant silencieusement l'autocast vers un comportement par défaut non lié à NFLOAT_4.

### 5.2. `COMPONENT_WEIGHT_DTYPE_BASE_VALUES` — 5 valeurs (base commune)

Source : `modules/ui/ModelTab.py:352-359` (corps de `__create_dtype_options()`, sans `include_a8`/`include_gguf`) :

```python
("float32", DataType.FLOAT_32),
("bfloat16", DataType.BFLOAT_16),
("float16", DataType.FLOAT_16),
("float8 (W8)", DataType.FLOAT_8),
# ("int8", DataType.INT_8),  # TODO: reactivate when the int8 implementation is fixed in bitsandbytes
("nfloat4", DataType.NFLOAT_4),
```

→ **`{FLOAT_32, BFLOAT_16, FLOAT_16, FLOAT_8, NFLOAT_4}`**.

`INT_8` est **explicitement commenté** dans le code source OneTrainer lui-même (ligne 357), avec la justification exacte « TODO: reactivate when the int8 implementation is fixed in bitsandbytes ». `INT_8` reste donc un membre de l'Enum `DataType` mais n'est une valeur fonctionnelle pour aucun `weight_dtype` dans la version actuellement installée — il doit être **rejeté** par le translator, exactement comme OneTrainer le désactive lui-même.

### 5.3. `TE_TE2_VAE_WEIGHT_DTYPE_VALUES` — 5 valeurs (identique à la base)

Source : `modules/ui/ModelTab.py:500,518,562` — `text_encoder.weight_dtype`, `text_encoder_2.weight_dtype`, `vae.weight_dtype` sont tous les trois construits par `self.__create_dtype_options()` **sans argument** (ni `include_a8=True`, ni `include_gguf=True`).

→ **`{FLOAT_32, BFLOAT_16, FLOAT_16, FLOAT_8, NFLOAT_4}`** — identique à 5.2, aucun format avancé.

Ces trois composants doivent donc **rejeter** `TFLOAT_32`, `INT_8`, `FLOAT_W8A8`, `INT_W8A8`, `GGUF`, `GGUF_A8_FLOAT`, `GGUF_A8_INT`, `NONE`.

### 5.4. `UNET_WEIGHT_DTYPE_VALUES` — 7 valeurs

Source : `modules/ui/ModelTab.py:424-425` — `unet.weight_dtype` construit par `self.__create_dtype_options(include_a8=True)` (`include_gguf` non passé → `False` par défaut).

Base (5, section 5.2) + `include_a8=True` (lignes 360-363 de `__create_dtype_options()`) :

```python
("float W8A8", DataType.FLOAT_W8A8),
("int W8A8", DataType.INT_W8A8),
```

→ **`{FLOAT_32, BFLOAT_16, FLOAT_16, FLOAT_8, NFLOAT_4, FLOAT_W8A8, INT_W8A8}`** — **7 valeurs**.

**Correction explicite par rapport au micro-audit** : le micro-audit avait rapporté « unet/transformer ≈ 10 valeurs » en groupant les deux composants. La lecture directe du code prouve que ce n'est **pas** le cas : `unet.weight_dtype` n'active que `include_a8=True`, **jamais** `include_gguf` — `unet` n'a donc que **7** valeurs valides, pas 10. Le compte de 10 ne s'applique qu'à `transformer` (section 5.5). Cette correction est appliquée ici conformément à l'instruction de faire autorité sur le code source plutôt que sur le résumé du micro-audit précédent.

### 5.5. `TRANSFORMER_WEIGHT_DTYPE_VALUES` — 10 valeurs

Source : `modules/ui/ModelTab.py:460-461` — `transformer.weight_dtype` construit par `self.__create_dtype_options(include_gguf=True, include_a8=True)`.

Base (5) + `include_a8=True` (2, section 5.4) + `include_gguf=True` (lignes 366-372 de `__create_dtype_options()`, y compris le sous-cas `include_a8` imbriqué) :

```python
options.append(("GGUF", DataType.GGUF))
if include_a8:
    options += [
        ("GGUF A8 float", DataType.GGUF_A8_FLOAT),
        ("GGUF A8 int", DataType.GGUF_A8_INT),
    ]
```

→ **`{FLOAT_32, BFLOAT_16, FLOAT_16, FLOAT_8, NFLOAT_4, FLOAT_W8A8, INT_W8A8, GGUF, GGUF_A8_FLOAT, GGUF_A8_INT}`** — **10 valeurs**, confirmées exactement (le compte du micro-audit était correct pour `transformer` spécifiquement, mais pas pour `unet`).

## 6. `TRAIN_DTYPE` — impact UI réel, dette explicite

Toolkit expose aujourd'hui, pour `train_dtype`, la même liste `_DTYPE_UI_CHOICES` que pour tous les `*_weight_dtype` (`training_page.py:78`) : `FLOAT_16, FLOAT_32, BFLOAT_16, TFLOAT_32, NFLOAT_4` — **`NFLOAT_4` y est actuellement sélectionnable pour `train_dtype`**, alors que la section 5.1 prouve que `TRAIN_DTYPE_VALUES` réel d'OneTrainer ne comprend **pas** `NFLOAT_4`.

**Conséquence assumée et à documenter sans l'atténuer** : après implémentation de M130, un utilisateur qui a déjà sélectionné `NFLOAT_4` comme `train_dtype` dans l'UI Toolkit actuelle verra ce choix **rejeté par le translator** (`OneTrainerConfigError`) au moment de Prepare Config/Start — un changement de comportement utilisateur réel, pas seulement un durcissement invisible. C'est un effet secondaire correct (la valeur ne fonctionnait déjà pas comme un `train_dtype` — elle dégradait silencieusement l'autocast, section 5.1) mais qui devient visible pour la première fois avec M130.

**M130 ne modifie pas l'UI.** Le widget `train_dtype_combo` continue de proposer `NFLOAT_4` tel quel après cette mission — seule une future mission d'harmonisation UI (hors périmètre M130, voir section 22) devra retirer ce choix de la combo ou le traiter différemment. Cette divergence ne doit pas être oubliée à la clôture de M130.

## 7. `COMPONENT WEIGHT DTYPE` — impact UI réel, dette explicite

Même dette symétrique : `_DTYPE_UI_CHOICES` (`training_page.py:78`) propose `TFLOAT_32` pour les cinq combos `*_weight_dtype`, alors que la section 5.2/5.3/5.4/5.5 prouve qu'aucun composant OneTrainer (ni la base, ni `unet`, ni `transformer`) n'accepte réellement `TFLOAT_32` comme `weight_dtype` — ce format n'existe dans aucune des listes construites par `__create_dtype_options()`. Fonctionnellement, un `weight_dtype=TFLOAT_32` est aujourd'hui indiscernable d'un `FLOAT_32` pour ce composant (le TF32 n'est jamais consulté au niveau composant, seulement au niveau `train_dtype` global via `enable_tf()`).

**Même conséquence assumée** : après M130, `TFLOAT_32` sélectionné comme `weight_dtype` pour n'importe lequel des cinq composants sera rejeté par le translator. Même traitement que pour `NFLOAT_4`/`train_dtype` — UI inchangée dans cette mission, dette d'harmonisation UI documentée séparément (section 22).

`INT_8` (section 5.2) reste rejeté pour tous les composants tant que sa désactivation reste actée dans le code OneTrainer audité (il n'est aujourd'hui proposé par aucun widget Toolkit, donc aucune régression UI visible sur ce point précis — seul un futur hand-edited `project.json` avec `INT_8` serait concerné).

## 8. Synthèse de la dette UI dtype — à ne pas absorber dans M130

- `train_dtype` : `NFLOAT_4` proposé par l'UI Toolkit mais désormais rejeté par le translator après M130.
- `*_weight_dtype` (les cinq composants) : `TFLOAT_32` proposé par l'UI Toolkit mais désormais rejeté par le translator après M130.
- Ces deux divergences sont **prouvées, assumées et documentées ici** — elles ne doivent pas être « oubliées » à la clôture de M130. Une future mission d'harmonisation UI (hors périmètre, voir section 22) devra aligner `_DTYPE_UI_CHOICES` sur les vocabulaires par rôle établis en section 5, potentiellement en distinguant elle aussi `train_dtype_combo` des cinq combos `weight_dtype`, et en distinguant éventuellement `unet`/`transformer` des trois autres composants pour exposer les formats avancés réellement supportés.

## 9. `LEARNING_RATE_SCHEDULER_VALUES` — 8 valeurs

Source : `modules/util/enum/LearningRateScheduler.py:4-12`, complet :

```
CONSTANT, LINEAR, COSINE, COSINE_WITH_RESTARTS, COSINE_WITH_HARD_RESTARTS,
REX, ADAFACTOR, CUSTOM
```

`CUSTOM` doit être traité comme une valeur **structurellement reconnue** par le translator — ce n'est pas un membre marginal ou déprécié de l'Enum, c'est un mode de fonctionnement légitime d'OneTrainer.

**Hors périmètre explicite** : `CUSTOM` nécessite, pour fonctionner réellement dans OneTrainer, deux champs compagnons — `custom_learning_rate_scheduler` (chemin de classe Python, `TrainConfig.py:393`) et `scheduler_params` (liste de paramètres, `TrainConfig.py:396`) — **non modélisés dans le Domain Toolkit aujourd'hui**. Si ces champs sont absents, OneTrainer lève lui-même une `AssertionError` explicite dès `create_lr_scheduler()` (`modules/util/create.py:1170-1175`) — un mode d'échec déjà bruyant, différent du problème M130 (fallback silencieux sur une valeur d'Enum inconnue). **M130 valide uniquement que `CUSTOM` est une valeur reconnue du champ `learning_rate_scheduler` ; elle n'ajoute ni ne valide `custom_learning_rate_scheduler`/`scheduler_params`.** Cette dette de cohérence reste séparée (section 22).

## 10. `OPTIMIZER_VALUES` — 43 valeurs

Source : `modules/util/enum/Optimizer.py:10-78`, liste complète et exacte (respecter la casse — deux membres, `AdEMAMix`/`AdEMAMix_8BIT`, ne sont **pas** en majuscules, contrairement à tous les autres) :

```
ADAGRAD, ADAGRAD_8BIT,
ADAM, ADAM_8BIT,
ADAMW, ADAMW_8BIT, ADAMW_ADV,
AdEMAMix, AdEMAMix_8BIT,
ADOPT, ADOPT_ADV,
LAMB, LAMB_8BIT,
LARS, LARS_8BIT,
LION, LION_8BIT, LION_ADV,
RMSPROP, RMSPROP_8BIT,
SGD, SGD_8BIT, SIGNSGD_ADV,
SCHEDULE_FREE_ADAMW, SCHEDULE_FREE_SGD,
DADAPT_ADA_GRAD, DADAPT_ADAM, DADAPT_ADAN, DADAPT_LION, DADAPT_SGD,
PRODIGY, PRODIGY_PLUS_SCHEDULE_FREE, PRODIGY_ADV,
ADAFACTOR,
CAME, CAME_8BIT,
MUON, MUON_ADV, ADAMUON_ADV,
ADABELIEF, TIGER, AIDA, YOGI
```

(43 membres exacts — vérifié par comptage direct sur le fichier source, pas déduit du micro-audit précédent.)

Le translator doit accepter ces 43 valeurs, pas seulement `ADAM`/`ADAMW`/`SGD` actuellement exposés par l'UI. Confirmé par le micro-audit : `OPTIMIZER_DEFAULT_PARAMETERS` (`modules/util/optimizer_util.py:95-642`) couvre les 43 membres sans exception, `create_optimizer()` (`modules/util/create.py`) dispatche les 43 sans case manquant, et toutes les dépendances tierces nécessaires (`bitsandbytes`, `lion_pytorch`, `dadaptation`, `prodigyopt`, `schedulefree`, `prodigy-plus-schedule-free`, `adv_optm`, `muon`, `timm`, `pytorch_optimizer`) sont confirmées installées dans le venv OneTrainer réel (`requirements-global.txt`/`requirements-cuda.txt`).

**Hors périmètre explicite** : ne pas étendre l'UI (`_OPTIMIZER_UI_CHOICES` reste `("ADAM", "ADAMW", "SGD")`), ne pas modifier les defaults d'optimizer, ne pas ajouter les hyperparamètres avancés, ne pas modifier `optimizer_extra_overrides` (section 18).

## 11. `TIMESTEP_DISTRIBUTION_VALUES` — 7 valeurs

Source : `modules/util/enum/TimestepDistribution.py:4-11`, complet :

```
UNIFORM, SIGMOID, LOGIT_NORMAL, HEAVY_TAIL, COS_MAP, INVERTED_PARABOLA, BETA
```

Consommation tracée dans `modules/modelSetup/mixin/ModelSetupNoiseMixin.py::_get_timestep_discrete()` (lignes 122-253) — aucune des 7 valeurs ne provoque de crash ; certaines (`LOGIT_NORMAL`, `HEAVY_TAIL`, `BETA`, `SIGMOID`, `INVERTED_PARABOLA`) consomment `noising_bias`/`noising_weight`, deux champs `TrainConfig` réels non modélisés par Toolkit, qui restent alors à leur défaut OneTrainer (`0.0`/`0.0`) sans erreur. Le gating d'architecture FLUX-only (`_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE`) reste **inchangé** après validation — voir section 12 pour l'ordre exact.

**Hors périmètre explicite** : `noising_bias`/`noising_weight` ne sont pas ajoutés au Domain par cette mission (section 22).

## 12. Ordre validation / architecture gating — contrat impératif

1. **Validation structurelle de la valeur** (nouvelle, M130) — s'exécute en premier, indépendamment de l'architecture courante.
2. **Architecture gating** (existant, M124–M129, inchangé) — s'exécute ensuite, uniquement sur une valeur déjà reconnue comme structurellement valide.

Ce contrat réutilise exactement l'ordre déjà établi par `text_encoder_stop_training_mode`/`_2` (validation/cohérence toujours levée en premier, gating d'architecture ensuite en omission silencieuse, jamais un raise).

**Exemples imposés, devant être couverts par la matrice de tests (section 19) :**

| Architecture | Champ | Valeur | Résultat attendu |
|---|---|---|---|
| SD1.5 | `text_encoder_2_weight_dtype` | `"FLOAT_16"` | valide + architecture incompatible → **omission silencieuse (M129 préservé)**, aucune erreur |
| SD1.5 | `text_encoder_2_weight_dtype` | `"NOT_A_DTYPE"` | invalide → **`OneTrainerConfigError`**, peu importe l'incompatibilité d'architecture |
| SDXL | `timestep_distribution` | `"UNIFORM"` | valide + architecture incompatible (flow-matching FLUX-only) → **omission silencieuse (M129 préservé)** |
| SDXL | `timestep_distribution` | `"NOT_A_DISTRIBUTION"` | invalide → **`OneTrainerConfigError`** |

Ce contrat s'applique identiquement aux cinq `*_weight_dtype` (y compris ceux qui lèvent déjà sur incompatibilité d'architecture — `unet`/`transformer`/`text_encoder`/`vae` — et à `text_encoder_2_weight_dtype`, seul à omettre depuis M129) et aux trois champs flow-matching FLUX (`timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift`) : la validation de valeur précède toujours, sans exception, le comportement d'architecture déjà en place.

## 13. Pattern de validation à réutiliser

Réutilisation conceptuelle du pattern déjà établi par `_STOP_TRAINING_MODE_VALUES` (validation stricte, toujours levée avant tout gating d'architecture, message nommant le champ et la valeur via `!r}` et l'ensemble attendu via `sorted(...)`). Constantes auditées explicites à ajouter dans `src/engines/onetrainer_config.py`, au même niveau que les constantes existantes (`_GRADIENT_CHECKPOINTING_VALUES`, `_STOP_TRAINING_MODE_VALUES`, `_LORA_LAYER_FILTER_TRANSLATION`).

**Interdits explicites** (cohérents avec l'architecture actuelle du projet) : aucune introspection dynamique des Enums OneTrainer, aucun import d'OneTrainer dans le processus Toolkit, aucun sous-processus de découverte. Toolkit ne touche jamais le GPU ni l'environnement Python d'OneTrainer depuis son processus principal — principe déjà établi et documenté ailleurs dans le projet, non remis en cause par M130.

## 14. Version coupling

Les constantes M130 sont auditées contre la version/l'installation OneTrainer réellement présente sur cette machine au moment de la rédaction de cette mission (les mêmes fichiers source que ceux déjà référencés par `_AUDITED_CONFIG_VERSION = 10`, `_GRADIENT_CHECKPOINTING_VALUES`, `_STOP_TRAINING_MODE_VALUES`, `_LORA_LAYER_FILTER_TRANSLATION`). Une future évolution des Enums OneTrainer (nouveau membre ajouté, membre renommé) pourra nécessiter une mise à jour manuelle de ces constantes — un risque déjà porté par le projet pour les quatre constantes existantes, pas un risque nouveau introduit par M130.

Stratégies alternatives explicitement écartées : introspection dynamique des Enums OneTrainer (romprait le principe « Toolkit n'importe jamais OneTrainer dans son processus principal ») ; validation conditionnée par version (aucun mécanisme de détection de version n'existe dans le projet, en introduire un pour ce seul besoin serait une sur-ingénierie hors de proportion avec le problème traité). **Constantes Toolkit auditées manuellement, alignées sur le pattern déjà en place — aucun mécanisme automatique de version negotiation.**

## 15. Domain / Manager — aucune modification prévue

`Training.from_dict()`, `OneTrainerSettings.from_dict()`, `OneTrainerOptimizerSettings.from_dict()`, `TrainingManager.update()`, `TrainingManager.create()` restent strictement inchangés. Le Domain reste permissif : un `project.json` contenant une valeur invalide pour l'un des neuf champs reste **chargeable sans crash** — aucune validation n'intervient à l'ouverture. La validation intervient uniquement au moment de la traduction (`build_training_config()`, appelée par `prepare_onetrainer_config()`/`start_training()`). Ce choix permet l'ouverture du projet, son inspection et sa correction sans blocage prématuré — cohérent avec le principe déjà établi ailleurs dans le projet (« Domain permissif, translator strict »).

## 16. Error UX — pipeline existant réutilisé, aucune modification UI

Le pipeline `OneTrainerConfigError` → `TrainingPage` → `QMessageBox.critical` fonctionne déjà, aussi bien depuis `prepare_onetrainer_config()` (bouton « Préparer la configuration ») que depuis `start_training()` (bouton « Démarrer l'entraînement »), avec un message qui nomme déjà le champ et la valeur fautive (via `!r}`) pour les quatre champs déjà validés. M130 réutilise ce pipeline sans le modifier — les nouvelles erreurs de validation apparaîtront avec le même format et au même endroit que les erreurs déjà existantes.

`save_training_parameters()` (bouton Save) n'appelle jamais le translator aujourd'hui et continuera de ne pas l'appeler après M130 — une valeur invalide pourra donc toujours être sauvegardée sans retour immédiat ; le rejet n'intervient qu'à Prepare Config/Start, jamais à Save. Ce contrat est documenté ici et ne doit pas être perçu comme un oubli.

## 17. `extra_overrides` — confirmation d'étanchéité

Le micro-audit a confirmé que les neuf champs (ou leurs clés composant `unet`/`transformer`/`text_encoder`/`text_encoder_2`/`vae`) sont tous couverts par `_STRUCTURED_CONFIG_KEYS`, avec une garde dédiée supplémentaire pour la clé racine `"optimizer"`. **Aucun chemin de contournement de la future validation via `extra_overrides` n'a été trouvé.** Ces protections ne seront modifiées que si l'implémentation démontre un besoin réel et imprévu — aucune modification n'est anticipée par ce contrat de mission.

## 18. `optimizer_extra_overrides` — explicitement hors périmètre

Dette réelle, confirmée par le micro-audit : `optimizer_extra_overrides` accepte n'importe quelle clé/valeur, sans validation contre les ~99 champs réels de `TrainOptimizerConfig` (`J:\Programmes\Onetrainer\modules\util\config\TrainConfig.py:36-140`) ni contre leur type respectif. Une clé mal orthographiée ou une clé inconnue de l'optimizer réellement sélectionné peut être silencieusement ignorée par OneTrainer. Cette dette est **explicitement hors périmètre de M130** — sa correction nécessiterait de valider un ensemble de champs typés et dépendants de l'optimizer, d'une ampleur nettement supérieure aux neuf discriminants structurés traités ici. Elle ne doit pas être mélangée avec cette mission, ni implémentée à cette occasion.

## 19. Matrice minimale de tests (A–Q)

| # | Scénario |
|---|---|
| A | Chaque valeur de chaque whitelist retenue (8 scheduler, 4 train_dtype, 5 base + 2 unet + 3 transformer weight_dtype, 43 optimizer, 7 timestep_distribution) est acceptée sans erreur. |
| B | Une valeur inventée (`"NOT_A_SCHEDULER"`, `"NOT_A_DTYPE"`, `"NOT_AN_OPTIMIZER"`, `"NOT_A_DISTRIBUTION"`) est rejetée pour chacun des 9 champs. |
| C | Le message de `OneTrainerConfigError` nomme le champ et la valeur invalide pour chaque cas de B. |
| D | Valeur valide + architecture incompatible → omission M129 préservée (exemples imposés section 12). |
| E | Valeur invalide + architecture incompatible → erreur M130 levée malgré l'incompatibilité (exemples imposés section 12). |
| F | Sentinelle `""` (non configuré) continue d'être acceptée sans déclencher la validation pour les 9 champs. |
| G | `False`/`None` des champs voisins déjà couverts par M128/M129 (`text_encoder_2_train`, `dynamic_timestep_shifting`) restent inchangés — non-régression croisée. |
| H | `extra_overrides`/`optimizer_extra_overrides` ne permettent toujours pas de contourner la nouvelle validation. |
| I | Un `Training` chargé depuis un `project.json` contenant une valeur invalide pour l'un des 9 champs reste chargeable sans crash (`from_dict()` ne lève rien). |
| J | `prepare_onetrainer_config()`, appelé ensuite sur ce même Training, rejette proprement via `OneTrainerConfigError`. |
| K | Le pipeline `TrainingPage` (`QMessageBox.critical`) remonte l'erreur sans modification UX, si une couverture existante (test Qt réel déjà en place pour les champs déjà validés) permet de le vérifier proprement sans nouveau smoke. |
| L | Les valeurs déjà utilisées par les tests/presets officiels existants (`FLOAT_16`, `FLOAT_32`, `BFLOAT_16`, `NFLOAT_4` en tant que `*_weight_dtype`, `LOGIT_NORMAL`, `UNIFORM`, `ADAM`, `ADAMW`, `SGD`, `CONSTANT`, `LINEAR`, `COSINE`) restent acceptées. |
| M | `NFLOAT_4` est rejeté comme `train_dtype` (dette UI section 6 — changement de comportement assumé). |
| N | `TFLOAT_32` est rejeté comme `*_weight_dtype` pour les 5 composants (dette UI section 7). |
| O | `FLOAT_W8A8`/`INT_W8A8` acceptés pour `unet_weight_dtype` ; `FLOAT_W8A8`/`INT_W8A8`/`GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT` acceptés pour `transformer_weight_dtype` — même si l'UI Toolkit ne les propose pas aujourd'hui. |
| P | Ces mêmes formats avancés (`FLOAT_W8A8`, `INT_W8A8`, `GGUF*`) sont rejetés pour `text_encoder_weight_dtype`/`text_encoder_2_weight_dtype`/`vae_weight_dtype`. |
| Q | `INT_8` est rejeté pour les 5 `*_weight_dtype` tant que sa désactivation reste actée dans le code OneTrainer audité (commentaire `ModelTab.py:357`). |

## 20. Tests existants potentiellement impactés (à identifier avant implémentation, ne rien modifier ici)

Le micro-audit a établi que toutes les valeurs actuellement utilisées dans `tests/integration/test_onetrainer_config.py` et `tests/integration/test_training_roundtrip.py` pour ces 9 champs (`"ADAM"`, `"ADAMW"`, `"SGD"`, `"FLOAT_16"`, `"FLOAT_32"`, `"BFLOAT_16"`, `"NFLOAT_4"`, `"COSINE"`, `"LINEAR"`, `"CONSTANT"`, `"LOGIT_NORMAL"`, `"UNIFORM"`) appartiennent déjà au vocabulaire réel retenu — **aucun test existant n'utilise `train_dtype="NFLOAT_4"` ni un `*_weight_dtype="TFLOAT_32"`** (recherche Grep négative, confirmée). Aucun test connu ne devrait donc être cassé par ce changement de contrat. Cette liste devra être reconfirmée par une recherche Grep explicite au tout début de l'implémentation, avant toute modification, et aucune couverture existante ne devra être supprimée sans remplacement si un cas imprévu apparaît.

## 21. Fichiers probables d'implémentation

**Attendus :**
- `docs/missions/MISSION_130.md` (ce fichier, à mettre à jour en fin d'implémentation).
- `src/engines/onetrainer_config.py` (nouvelles constantes de validation + intégration dans `build_training_config()`, ordre validation puis gating).
- `tests/integration/test_onetrainer_config.py`.
- `tests/integration/test_training_roundtrip.py`.
- Éventuellement un test Qt déjà existant, uniquement si nécessaire pour prouver que le pipeline `OneTrainerConfigError` → `QMessageBox.critical` déjà en place remonte bien une nouvelle erreur M130 (item K de la matrice) — aucun nouveau mécanisme UI, seulement une preuve sur le mécanisme existant.

**Explicitement non modifiés :**
- `src/domain/` (aucun fichier).
- `src/managers/` (aucun fichier).
- `src/ui/pages/training_page.py` — **malgré la divergence UI dtype découverte et documentée (sections 6/7/8), ce fichier n'est pas modifié par M130.** Cette harmonisation UI reste une dette distincte.

**Si l'implémentation démontre qu'un fichier hors de ce périmètre doit être modifié : STOP avant toute modification et rapport à l'architecte avant de continuer.**

## 22. Dettes à garder explicitement séparées de M130

- Harmonisation UI dtype (`NFLOAT_4` proposé pour `train_dtype`, `TFLOAT_32` proposé pour `*_weight_dtype` — sections 6/7/8).
- Extension UI des optimizers/schedulers/dtypes vers un choix plus large que le sous-ensemble actuel.
- Cohérence de `CUSTOM` (learning rate scheduler) avec ses champs compagnons `custom_learning_rate_scheduler`/`scheduler_params`, non modélisés par Toolkit (section 9).
- Validation de `optimizer_extra_overrides` (~99 clés réelles de `TrainOptimizerConfig`, section 18).
- Training presets (`Recommended`/`Memory Efficient`/`Custom`).
- Hardware-aware Training / Preflight (détection GPU/VRAM/compute capability).
- Forge — auto-start + pending-generation handoff + annulation depuis `InferencePage`.
- Fooocus — intégration complète, aucune trace de code existante.
- Avertissement sémantique `dynamic_timestep_shifting`/`timestep_shift` (contradiction déjà connue, non bloquante, non traitée par M129 ni par M130).
- `noising_bias`/`noising_weight` (champs consommés par plusieurs `TimestepDistribution`, non modélisés par Toolkit, section 11).
- Tout autre réglage OneTrainer non exposé aujourd'hui (EMA, masked training, sampling pendant training, save/backup périodique, multi-GPU, `torch.compile`, `QuantizationConfig` complet, offloading avancé, etc. — voir audit post-M129).

## 23. Smoke

**Aucun smoke GPU prévu.** Justification : mission de validation translator/configuration uniquement, aucune modification de la logique runtime OneTrainer, aucune sémantique d'entraînement touchée — cohérent avec le précédent établi par M124/M127/M128/M129 (missions translator-only, toutes closes sans smoke).

## 24. Baseline

État de référence exact au moment de la rédaction de ce contrat de mission (post-M129, avant toute implémentation M130) :

- **2672 tests collectés** (état final confirmé par Mission 129 : 2662 à la clôture de Mission 128 + 10 nets ajoutés par Mission 129).
- Mission 129 : **468/468 tests ciblés verts**, **2672/2672 sur une unique exécution complète de la suite**, exit 0, aucune failure ni flake observé sur ce run précis — non extrapolable à une disparition des anomalies intermittentes historiques (Mission 126, `dialog_guard` Mission 127/128, `Forge lifecycle` Mission 128).
- La baseline Mission 128 reste, pour mémoire et sans réécriture : **2662 tests collectés, 458/458 tests ciblés Mission 128 verts**, avec ses propres anomalies full-suite déjà documentées séparément.

## 25. Critères d'acceptation

- [x] Aucune valeur non reconnue par OneTrainer, pour aucun des 9 champs, n'atteint la configuration JSON générée — toujours rejetée par `OneTrainerConfigError` avant écriture.
- [x] Toutes les valeurs réellement supportées par OneTrainer et retenues par les whitelists des sections 5/9/10/11 sont acceptées sans erreur, y compris les formats avancés `unet`/`transformer` non proposés par l'UI Toolkit actuelle (item O de la matrice).
- [x] Le vocabulaire par rôle dtype (`TRAIN_DTYPE_VALUES` ≠ `COMPONENT_WEIGHT_DTYPE` de base ≠ `UNET_WEIGHT_DTYPE_VALUES` ≠ `TRANSFORMER_WEIGHT_DTYPE_VALUES`) est appliqué exactement comme documenté en section 5, sans confusion entre l'appartenance à l'Enum `DataType` et l'utilisabilité réelle par champ.
- [x] Le contrat M129 (valeur reconnue + architecture incompatible → Domain conservé, JSON omis, aucune erreur) reste intégralement préservé — vérifié par les exemples imposés de la section 12.
- [x] `src/domain/`, `src/managers/` restent strictement inchangés.
- [x] `src/ui/pages/training_page.py` reste strictement inchangé, malgré la dette UI dtype documentée (sections 6/7/8).
- [x] Le comportement de `save_training_parameters()` (Save permissif, sans appel au translator) reste inchangé.
- [x] `prepare_onetrainer_config()`/`start_training()` restent le point strict de rejet, via le pipeline `OneTrainerConfigError` → `QMessageBox.critical` déjà existant, sans modification UX.
- [x] Aucune introspection dynamique d'OneTrainer, aucun import d'OneTrainer dans le processus Toolkit, aucun sous-processus de découverte n'est introduit.
- [x] Aucun bypass de la nouvelle validation via `extra_overrides`/`optimizer_extra_overrides` n'est possible.
- [x] Les dettes connexes listées en section 22 ne sont pas absorbées dans cette mission.
- [x] Tests ciblés M130 verts.
- [x] Une suite complète exécutée selon la procédure habituelle du projet, résultat rapporté avec les chiffres exacts (pas d'arrondi, pas d'extrapolation).
- [x] Aucun smoke GPU exécuté.

### Résultats réels

**Divergence détectée pendant la vérification pré-implémentation (section 2 du contrat d'implémentation)** : un test historique, `test_existing_dtype_values_unaffected_by_nfloat_4_addition` (`tests/integration/test_onetrainer_config.py`), affirmait auparavant que `TFLOAT_32` était un `unet_weight_dtype` valide — hypothèse de test antérieure à M130, jamais mise en cause avant l'audit de vocabulaire par rôle. Le micro-audit initial avait manqué cette occurrence (recherche négative erronée). La vérification pré-implémentation imposée par le contrat M130 l'a détectée ; la preuve directe lue dans le code OneTrainer installé (`ModelTab.py::__create_dtype_options()`) établit que `TFLOAT_32` n'est jamais un `weight_dtype` valide pour aucun composant. Traitement validé par l'architecte : la couverture n'a pas été supprimée mais reclassée — l'ancienne assertion de succès pour `TFLOAT_32` est devenue une assertion de rejet (`test_weight_dtype_rejects_tfloat_32_for_every_component`), la couverture de non-régression pour `FLOAT_16`/`FLOAT_32`/`BFLOAT_16` restant intégralement conservée. Ce n'est pas une anomalie produit — c'est la correction d'une hypothèse de test antérieure, exactement le genre de découverte que la vérification pré-implémentation de M130 était censée capter.

**Fichiers modifiés** : exactement les 3 fichiers attendus — `src/engines/onetrainer_config.py` (nouvelles constantes de vocabulaire + validation intégrée dans `build_training_config()`, ordre validation-puis-gating), `tests/integration/test_onetrainer_config.py`, `tests/integration/test_training_roundtrip.py`. Aucun test UI supplémentaire n'a été nécessaire — le pipeline `OneTrainerConfigError` → `QMessageBox.critical` déjà existant (prouvé par `test_prepare_config_surfaces_an_incompatible_dtype_field_as_a_critical_error`) a simplement été réexercé avec une valeur M130 (`test_prepare_config_surfaces_an_unrecognized_optimizer_value_as_a_critical_error`), sans aucune modification de `training_page.py`. `src/domain/`, `src/managers/` confirmés inchangés.

**Tests nets ajoutés** : **+37** (2672 → 2709 tests collectés) — `test_onetrainer_config.py` : 138 → 169 (+31, dont 1 test historique adapté sans perte de couverture) ; `test_training_roundtrip.py` : 330 → 336 (+6).

**Tests ciblés** : tous verts (169/169 dans `test_onetrainer_config.py`, 336/336 dans `test_training_roundtrip.py` — 505/505 au total sur l'exécution combinée des deux fichiers ciblés).

**Suite complète** : une unique exécution complète — **2709 collectés, 2707 passés, 2 échoués** : `ForgeLifecycleManagerRealProcessTest.test_stop_is_idempotent_on_running_owned` et `MainWindowInferencePendingResultGuardTest.test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure`. Les deux échecs correspondent aux flakes historiques déjà documentés et n'ont pas été reproduits lors de leur reproduction isolée (1/1 vert pour chacun) — par nom et par nature, il s'agit exactement des deux flakes déjà documentés dans `docs/PROJECT_CONTEXT.md` (course réelle `taskkill`/`cmd.exe` pour le premier, assertion de timing `elapsed < 1.0` pour le second) ; aucun des deux ne touche `onetrainer_config.py` ni l'un des deux fichiers de tests modifiés par cette mission. Aucun nouvel échec, aucun échec touchant un test M130.

**Dette UI dtype** : confirmée toujours présente et non résolue par cette mission, exactement comme documenté aux sections 6/7/8 — `NFLOAT_4` reste sélectionnable dans l'UI Toolkit comme `train_dtype`, `TFLOAT_32` reste sélectionnable comme `weight_dtype` pour les 5 composants ; le translator rejette désormais les deux. Cette divergence UI/translator n'est pas présentée comme harmonisée — une future mission distincte devra aligner les combos UI sur les vocabulaires par rôle établis ici.

**Écarts par rapport au contrat** : aucun — le contrat de MISSION_130.md a été suivi exactement, à l'exception de la correction ponctuelle validée par l'architecte (traitement du test `TFLOAT_32` historique, documentée ci-dessus).

## 26. Hors périmètre strict

Tout ce qui figure en section 22, sans exception. Aucune Mission 131 n'est présumée par ce document — la mission suivante sera déterminée par un nouvel audit, après clôture de M130.

## 27. Autorisation

Ce document constitue le contrat de Mission 130 tel que validé par l'architecte à l'issue du micro-audit technique en lecture seule. Il n'engage aucune implémentation tant que l'architecte n'a pas explicitement autorisé la phase suivante. Les décisions produit/architecture actées ici (Contrat B, vocabulaire par rôle pour les dtypes, correction du compte `unet`/`transformer`, UI inchangée malgré la dette découverte) sont considérées comme figées pour la durée de cette mission et ne doivent pas être rouvertes sans une nouvelle validation explicite.
