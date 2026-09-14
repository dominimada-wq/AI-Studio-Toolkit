# Mission 122 — Advanced Training Settings: Optimizer (discriminant seul, échappatoire scopée)

> **MISSION IMPLÉMENTÉE, VALIDÉE, COMMITÉE, TAGUÉE ET PUBLIÉE.** Implémentée exactement selon ce document, validée par la suite complète (2465/2465) et par un smoke réel SD1.5 de bout en bout contre l'installation OneTrainer réelle avec `optimizer="SGD"`. Commit fonctionnel `b98a55de7673ae76c6664d6880650b87c05e4805` (`Add structured OneTrainer optimizer settings`), tag `v0.2-mission122`, GitHub Release publiée manuellement.

## 1. Contexte

Le micro-audit dédié (lecture seule, `J:\Programmes\Onetrainer\modules\util\enum\Optimizer.py`, `modules/util/create.py::create_optimizer()`, `modules/util/config/TrainConfig.py`/`BaseConfig.py`, presets JSON réels, venv réel) a établi que :

- `Optimizer` compte 43 valeurs réelles ; `build_training_config()` n'envoie aujourd'hui jamais de clé `optimizer`, laissant OneTrainer appliquer son défaut réel `ADAMW` (`TrainConfig.py:150,1176`).
- `TrainConfig.optimizer` est un objet `TrainOptimizerConfig` nichée (pas un enum plat) — la forme réelle attendue par `BaseConfig.from_dict()` pour toute configuration externe est `{"optimizer": {"optimizer": "<ENUM>", ...}}`, confirmée par un preset réel (`training_presets/#qwen Finetune 16GB.json`).
- `TrainConfig.optimizer_defaults` est confirmé, par un second grep exhaustif indépendant du micro-audit M121, **exclusivement lu/écrit par du code UI OneTrainer** (`modules/ui/OptimizerParamsWindow.py`/`TrainingTab.py`/`TopBar.py`) — jamais par `create.py`. Reste hors périmètre Toolkit.
- Seules `ADAM`/`ADAMW`/`SGD` utilisent directement `torch.optim`, sans aucune dépendance tierce (`bitsandbytes`/`prodigyopt`/`lion_pytorch`/`dadaptation`/`adv_optm`/`schedulefree`/`muon`/`timm`/`pytorch_optimizer`, toutes confirmées installées dans le venv réel mais non retenues pour cette mission) ni variante 8-bit/quantifiée.
- Aucun preset réel SD1.5/SDXL/Flux(1) LoRA ne définit d'optimizer explicite (tous implicitement `ADAMW`) ; les seuls presets non-`ADAMW` observés utilisent `ADAFACTOR`, exclusivement pour des Finetune de gros modèles DiT hors périmètre Toolkit.
- **Vérification architecturale finale (déclenchée par une objection explicite de l'architecte sur le brouillon initial)** : réserver la racine `"optimizer"` en bloc dans `_STRUCTURED_CONFIG_KEYS`, sans échappatoire locale, bloquerait la totalité des ~99 sous-paramètres non typés — contraire au principe M120 de typage progressif avec échappatoire préservée pour tout réglage non encore modélisé. `OneTrainerOptimizerSettings` (section 3) résout ce problème par une échappatoire **scopée à l'objet optimizer**, distincte de l'échappatoire globale `OneTrainerSettings.extra_overrides`.

## 2. Objectif de M122

Introduire une configuration Optimizer structurée et extensible : permettre à `Training` de sélectionner explicitement un optimizer OneTrainer parmi un premier sous-ensemble validé techniquement (`ADAM`/`ADAMW`/`SGD`, section 7), **sans jamais perdre la capacité d'exprimer, via une échappatoire dédiée, les sous-paramètres OneTrainer réels encore non typés** — contrairement à une réservation de racine sans échappatoire, qui aurait constitué une régression de capacité par rapport au principe déjà établi par M120. Un Training qui ne configure aucune donnée optimizer doit produire, après M122, une configuration OneTrainer strictement identique à celle produite par le code issu de M121.

## 3. Décision architecturale

### 3.1 Nouvelle structure Domain — `OneTrainerOptimizerSettings`

Nouvelle dataclass Qt-free, dans un nouveau fichier `src/domain/onetrainer_optimizer_settings.py`, même convention exacte que `OneTrainerSettings` (`to_dict()`/`from_dict()` symétriques, garde `isinstance(x, dict)` sur désérialisation) :

```
OneTrainerOptimizerSettings
├── optimizer: str = ""        (discriminant — sentinelle "" = non configuré, jamais une des 43 valeurs réelles)
└── extra_overrides: dict = field(default_factory=dict)   (échappatoire scopée à l'objet optimizer uniquement)
```

`OneTrainerSettings` gagne :

```
OneTrainerSettings
├── ... champs M120/M121 existants (inchangés)
└── optimizer_settings: OneTrainerOptimizerSettings = field(default_factory=OneTrainerOptimizerSettings)
```

**Décision actée explicitement par l'architecte, non négociable pour cette mission** : le discriminant `optimizer` n'est **pas** un champ plat direct de `OneTrainerSettings` (ce qu'un premier brouillon avait proposé) — il vit exclusivement dans `OneTrainerSettings.optimizer_settings.optimizer`, précisément pour que son échappatoire (`optimizer_settings.extra_overrides`) reste un objet distinct et scopé, jamais mélangée à l'échappatoire globale `OneTrainerSettings.extra_overrides`. Ce nouveau niveau d'imbrication suit exactement le même pattern que celui déjà établi par `Training.onetrainer_settings: OneTrainerSettings` lui-même (Mission 120) — aucun nouveau précédent architectural, un niveau de plus, avec la même garde défensive `isinstance(x, dict)` sur désérialisation.

`OneTrainerSettings.to_dict()`/`from_dict()` délèguent à `OneTrainerOptimizerSettings.to_dict()`/`from_dict()` pour la clé `"optimizer_settings"`, avec garde `isinstance(data.get("optimizer_settings"), dict)` avant délégation — sinon repli sur `OneTrainerOptimizerSettings()` (valeurs sentinelles), même convention que tout sous-objet Domain imbriqué du projet.

### 3.2 Traduction OneTrainer — construction conditionnelle de l'objet nichée

`build_training_config()` gagne deux nouveaux paramètres optionnels : `optimizer: str = ""`, `optimizer_extra_overrides: Optional[dict] = None`.

Construction, après validation des collisions (section 3.3) :

```python
optimizer_object = {}
if optimizer:
    optimizer_object["optimizer"] = optimizer
if optimizer_extra_overrides:
    optimizer_object.update(optimizer_extra_overrides)
if optimizer_object:
    config["optimizer"] = optimizer_object
```

Aucune clé `"optimizer"` n'est ajoutée au dict produit si `optimizer_settings.optimizer == ""` **et** `optimizer_settings.extra_overrides == {}` — comportement historique OneTrainer strictement inchangé, `ADAMW` reste implicite exactement comme aujourd'hui (comme pour M120/M121, jamais un défaut Toolkit imposé). Exemple valide confirmé compatible avec le merge partiel réel d'OneTrainer (`BaseConfig.from_dict()`, même précédent que `concepts`/les dtypes M121) : `optimizer_settings.optimizer="ADAMW"` + `optimizer_settings.extra_overrides={"weight_decay": 0.01}` → `{"optimizer": {"optimizer": "ADAMW", "weight_decay": 0.01}}`.

### 3.3 Politique de collisions — deux niveaux distincts

**Niveau global (déjà en place, étendu)** : `_STRUCTURED_CONFIG_KEYS` gagne la clé racine `"optimizer"` — réservée inconditionnellement, empêchant `OneTrainerSettings.extra_overrides` (l'échappatoire **globale**, pré-existante) de porter une clé top-level `"optimizer"` sous quelque forme que ce soit (scalaire ou dict), qui contournerait le discriminant structuré ou recréerait une seconde source de vérité — même mécanisme de détection déjà en place (`_STRUCTURED_CONFIG_KEYS & extra_overrides.keys()`), aucune nouvelle logique introduite à ce niveau.

**Niveau optimizer (nouveau)** : une constante dédiée `_OPTIMIZER_STRUCTURED_SUBKEYS = frozenset({"optimizer"})`, vérifiée exclusivement contre `optimizer_extra_overrides.keys()` (jamais contre l'échappatoire globale). Toute collision — ex. `optimizer_settings.extra_overrides = {"optimizer": "SGD"}` — lève `OneTrainerConfigError` nommant explicitement la clé fautive, avant toute fusion. Tout autre sous-paramètre (`{"weight_decay": 0.01}`, ou tout autre champ réel de `TrainOptimizerConfig` non encore typé) reste autorisé sans restriction — c'est précisément l'objet de cette architecture à deux niveaux : la racine est protégée globalement, l'intérieur de l'objet optimizer reste une échappatoire fonctionnelle.

**Conçue pour évoluer** : lorsqu'un futur champ (ex. `weight_decay`) devient un champ typé de `OneTrainerOptimizerSettings`, son nom rejoint `_OPTIMIZER_STRUCTURED_SUBKEYS` **dans le même changement** — jamais après coup, même discipline que `_STRUCTURED_CONFIG_KEYS` aujourd'hui. Les sous-paramètres non encore typés à ce moment-là restent accessibles via `optimizer_settings.extra_overrides`, sans interruption de service pour l'architecte.

### 3.4 Rétrocompatibilité — rejet explicite, jamais de migration silencieuse

Un `project.json` antérieur sans `optimizer_settings` charge `OneTrainerOptimizerSettings()` (valeurs sentinelles), sans erreur, sans migration — comportement standard déjà établi par M120/M121.

**Cas distinct, à traiter explicitement** : la clé racine `"optimizer"` n'étant réservée dans `_STRUCTURED_CONFIG_KEYS` qu'à partir de cette mission, un `project.json` hand-édité pourrait déjà légitimement porter `OneTrainerSettings.extra_overrides["optimizer"]` (fonctionnel aujourd'hui, avant M122). Après M122, la validation existante (section 3.3, niveau global) rejette désormais cette clé — un changement de comportement réel pour ce cas précis, jamais atteignable depuis l'UI Toolkit (aucune UI n'a jamais exposé `extra_overrides` lui-même). **Décision actée : rejet explicite et immédiat au prochain `prepare_onetrainer_config()`/`build_training_config()`, jamais de migration automatique** — cohérent avec `CLAUDE.md` (« compatibilité défensive, jamais migration implicite ») et avec le principe déjà en vigueur (« jamais un écrasement silencieux, toujours une erreur explicite »). Le message d'erreur pour ce cas précis doit nommer explicitement la clé devenue réservée et indiquer où déplacer la valeur (dans l'esprit de : *`extra_overrides['optimizer']` is now managed by structured optimizer settings — move nested optimizer parameters to `optimizer_settings.extra_overrides`*), distinct du message générique de collision `_STRUCTURED_CONFIG_KEYS` déjà en place, pour rester immédiatement actionnable même pour un architecte qui n'a jamais lu ce document.

### 3.5 Vocabulaire — quatre niveaux distincts (même discipline que M121 section 3.2)

1. **Représentable OneTrainer** : 43 valeurs réelles de l'enum `Optimizer`.
2. **Dépendance présente dans ce venv** : les 43 (toutes confirmées installées — n'exclut donc rien à ce stade, contrairement à une hypothèse initiale).
3. **Proposé par l'UI M122** : `ADAM`, `ADAMW`, `SGD` — les trois seules valeurs backées directement par `torch.optim`, sans dépendance optimizer tierce, sans variante 8-bit/quantifiée, sans chemin CUDA distinct de celui déjà utilisé par tous les smokes réels précédents (Missions 097-121). **Jamais présenté comme la liste complète OneTrainer** — le Domain (`OneTrainerOptimizerSettings.optimizer: str`) reste capable de stocker n'importe laquelle des 43 valeurs, y compris via un `project.json` hand-édité ou une future UI élargie, sans erreur (même tolérance défensive que `learning_rate_scheduler`/les dtypes).
4. **Validé matériellement sur le P4000** : `ADAMW` seul, de facto (exécuté avec succès à chaque smoke M097-121, jamais explicitement configuré comme champ Toolkit avant cette mission). `SGD` sera nouvellement validé par le smoke de cette mission (section 9). `ADAM` reste proposé sur la base du même backend torch natif que `ADAMW`/`SGD`, **mais n'est pas déclaré « smoke-validé »** tant qu'aucun run réel ne l'utilise explicitement — distinction à ne jamais confondre.

## 4. Fichiers concernés

- `src/domain/onetrainer_optimizer_settings.py` (nouveau) — `OneTrainerOptimizerSettings` (dataclass : `optimizer: str = ""`, `extra_overrides: dict = field(default_factory=dict)`, `to_dict()`/`from_dict()`).
- `src/domain/onetrainer_settings.py` (modifié) — nouveau champ `optimizer_settings: OneTrainerOptimizerSettings`, `to_dict()`/`from_dict()` étendus avec délégation + garde `isinstance(..., dict)`.
- `src/engines/onetrainer_config.py` (modifié) — nouveaux paramètres optionnels de `build_training_config()` (`optimizer=""`, `optimizer_extra_overrides=None`) ; extension de `_STRUCTURED_CONFIG_KEYS` avec `"optimizer"` ; nouvelle constante `_OPTIMIZER_STRUCTURED_SUBKEYS` et validation de collision locale (section 3.3) ; construction conditionnelle de l'objet nichée (section 3.2) ; message d'erreur dédié et actionnable pour le cas `extra_overrides["optimizer"]` hérité (section 3.4).
- `src/managers/training_manager.py` (modifié) — `prepare_onetrainer_config()` transmet `optimizer`/`optimizer_extra_overrides` ; `update()` étendu pour le nouveau champ (mutation in-place de `training.onetrainer_settings.optimizer_settings`, jamais un remplacement de l'objet parent qui perdrait `extra_overrides`).
- `src/ui/pages/training_page.py` (modifié) — nouvelle sous-section `Optimizer` dans le conteneur `Advanced settings` existant (section 6), un combo `optimizer_combo` (`(non configuré)`/`ADAM`/`ADAMW`/`SGD`), même câblage dirty-state que les combos dtype M121.
- `tests/integration/test_onetrainer_config.py` (modifié) — traduction, collisions aux deux niveaux, rejet du cas hérité, non-régression byte-à-byte du comportement M121.
- `tests/integration/test_training_roundtrip.py` (modifié) — round-trip `OneTrainerOptimizerSettings`, rétrocompatibilité, dirty-state UI, snapshot immuable, scroll toujours fonctionnel avec la section Optimizer.

**Aucun changement** à `TrainingJob` (Domain), au mécanisme de snapshot (`create_job()`), à `ForgeEngine`/`ComfyUIEngine`, à l'EventBus, à `_PROTECTED_CONFIG_KEYS`, aux 6 champs dtype de M121.

## 5. Hors périmètre strict

- Tout sous-paramètre optimizer typé individuellement : `beta1`, `beta2`, `weight_decay`, `eps`, `momentum`, `stochastic_rounding`, `fused_back_pass` — restent accessibles uniquement via `optimizer_settings.extra_overrides`, jamais des champs Toolkit dans cette mission.
- `optimizer_defaults` (confirmé exclusivement UI OneTrainer, jamais lu par le runtime réel — section 1).
- `PRODIGY`, `LION`, toute variante `_8BIT`/quantifiée, `bitsandbytes`, `D-Adaptation`, `MUON`, `ADAFACTOR` et toute autre valeur de l'enum au-delà de `ADAM`/`ADAMW`/`SGD` dans l'UI — représentables au niveau Domain (section 3.5), jamais proposés dans l'UI de cette mission.
- `TrainingPreset` (architecture de presets).
- Réglages Dataset/Concept (`seed`, augmentation, balancing/repeats, tag dropout).
- Tout changement de défaut de production OneTrainer (`ADAMW` reste implicite quand rien n'est configuré).
- Toute modification de l'environnement CUDA/Torch/OneTrainer/drivers/checkpoint.

## 6. UI — `Advanced settings` → nouvelle sous-section `Optimizer`

Dans le conteneur repliable déjà introduit par M121 (`QToolButton`+`QWidget.setVisible()`, jamais un `QGroupBox` cochable — voir MISSION_121.md section 7, mécanisme inchangé), une nouvelle sous-section `Optimizer` (même style que `Precision / Memory` : label de section, puis un combo) :

- **Optimizer** (combo, `optimizer_settings.optimizer`) — items : `"(non configuré)"` → `""`, `"ADAM"`, `"ADAMW"`, `"SGD"`, suivant exactement le patron déjà établi par `_build_dtype_combo()`/`learning_rate_scheduler_combo` (`findData()`/`setCurrentIndex()` avec repli explicite sur l'index 0 si la valeur chargée n'est pas dans la liste proposée — ex. un `project.json` configurant `"PRODIGY"` via `extra_overrides` reste chargé sans erreur côté Domain, simplement non représenté dans ce combo).

**Contrat dirty-state, identique à l'existant, sans exception** :
- Chargement (`_load_training_parameters()`) : `optimizer_combo` ajouté à la liste des champs `blockSignals(True)`/`blockSignals(False)`, jamais de dirty-state déclenché par un rechargement.
- Modification manuelle → `_on_training_parameters_changed()` (même connexion `currentIndexChanged` que `train_dtype_combo`).
- `Save` → `training_manager.update(optimizer=...)` persiste la valeur ; `reload` restaure exactement la valeur persistée.
- **Repli/dépliage de la section Advanced settings ne modifie aucune valeur et ne déclenche jamais le dirty-state à lui seul** — `_on_advanced_settings_toggled()` reste le seul handler connecté à `toggled`, inchangé depuis M121.
- **Le scroll vertical ajouté par le correctif post-M121 reste inchangé** — `optimizer_combo` est un widget de plus dans `advanced_settings_form` (le `QFormLayout` du conteneur repliable), déjà contenu dans le `QScrollArea` existant ; aucune modification du layout racine n'est nécessaire ni prévue par cette mission.

## 7. Tests

1. Round-trip `OneTrainerOptimizerSettings` : `optimizer`/`extra_overrides` survivent à `to_dict()`/`from_dict()` à l'identique.
2. Rétrocompatibilité : un `project.json` sans `optimizer_settings` se charge avec `OneTrainerOptimizerSettings()` (sentinelles), sans erreur.
3. Non-régression stricte du comportement M121 : `optimizer_settings` à ses valeurs sentinelles produit un dict `build_training_config()` identique à celui de M121 — comparaison byte-à-byte, pas seulement absence d'exception.
4. Traduction de `optimizer="ADAM"` seul.
5. Traduction de `optimizer="ADAMW"` seul.
6. Traduction de `optimizer="SGD"` seul.
7. Traduction combinée `optimizer` + `extra_overrides` (ex. `{"optimizer": "ADAMW", "weight_decay": 0.01}` produit exactement `{"optimizer": {"optimizer": "ADAMW", "weight_decay": 0.01}}`).
8. Passage d'un sous-paramètre seul via `optimizer_settings.extra_overrides` sans `optimizer` configuré (ex. `{"weight_decay": 0.01}` seul → `{"optimizer": {"weight_decay": 0.01}}`).
9. Rejet de collision locale : `optimizer_settings.extra_overrides = {"optimizer": "SGD"}` lève `OneTrainerConfigError`.
10. Rejet de la clé racine héritée : `OneTrainerSettings.extra_overrides = {"optimizer": {...}}` lève `OneTrainerConfigError` avec un message actionnable nommant la clé et l'emplacement de repli (section 3.4) — test dédié reproduisant explicitement un ancien projet hand-edit utilisant cette racine.
11. `_STRUCTURED_CONFIG_KEYS`/`_OPTIMIZER_STRUCTURED_SUBKEYS` énumérées exactement (même discipline que M120/M121, pour qu'un oubli futur casse la suite plutôt que de rester silencieux).
12. Snapshot `TrainingJob` : immuabilité inchangée, contenu étendu au champ optimizer quand configuré.
13. UI : dirty-state sur `optimizer_combo` (chargement neutre, modification → dirty, Save → persistance, reload → valeur restaurée).
14. Repli/dépliage d'`Advanced settings` avec la section Optimizer présente : aucune valeur modifiée, aucun dirty-state déclenché (extension du test M121 existant).
15. La section `Advanced settings` reste scrollable et son contenu correctement recalculé avec le champ Optimizer en plus (extension de `TrainingPageScrollableContentTest`, aucune régression du correctif post-M121).

Les 15 points ci-dessus sont couverts par 16 tests nets nouveaux (11 dans `tests/integration/test_onetrainer_config.py`, 5 dans `tests/integration/test_training_roundtrip.py`). Résultats réels : `test_onetrainer_config.py` **54/54** (43 hérités + 11 nets nouveaux), `test_training_roundtrip.py` **227/227** (222 hérités + 5 nets nouveaux) — les deux fichiers exécutés ensemble donnent **281/281**. Suite complète exécutée : **2465/2465** (2449 hérités du correctif post-M121 + 16 nets nouveaux), 0 failure, 0 error, `git diff --check` propre.

## 8. Smoke réel

**Exécuté et validé, avec autorisation explicite de l'architecte, après la suite complète verte.** Scénario réutilisant le petit cas SD1.5 déjà validé par les Missions 097-121 (checkpoint `v1-5-pruned-emaonly-fp16.safetensors`, 1 image, résolution 512, 1 epoch), sans aucune modification d'environnement (Python/Torch/CUDA/OneTrainer/drivers/checkpoint inchangés). Un `Training` réel a été explicitement configuré avec `optimizer_settings.optimizer = "SGD"` — première valeur non-`ADAMW` jamais réellement exécutée par ce projet. Chemin complet tracé et prouvé à chaque étape via des valeurs réelles observées : `Training`/`OneTrainerOptimizerSettings` → `prepare_onetrainer_config()` (configuration préparée contenant exactement `{"optimizer": {"optimizer": "SGD"}}`) → `create_job()` (snapshot `TrainingJob.config_snapshot_path` contenant la même valeur) → lancement réel via `TrainingJobRunner` contre l'installation OneTrainer réelle. Résultat : process démarré réellement, checkpoint SD1.5 réellement chargé, un vrai step GPU exécuté (`loss=0.0852`, observé mais non requis comme critère de validation — aucune comparaison avec `ADAMW` n'était nécessaire), run terminé `succeeded` en 54,6 s, `lora.safetensors` réel produit (78 489 976 octets). Aucun script de smoke conservé dans le dépôt (scratchpad de session uniquement, hors du répertoire du projet, nettoyé après exécution).

**Mécanisme de preuve** (décidé lors de la vérification architecturale, section 1, confirmé à l'exécution) : `create.py::create_optimizer()` utilise un `match`/`case` exhaustif sans branche de repli générique ; les signatures de construction `SGD` (`lr`/`momentum`/`dampening`/`weight_decay`/`nesterov`) et `AdamW` (`betas`/`eps`/...) sont incompatibles entre elles. Le run réel a bien atteint un vrai step GPU avec `optimizer="SGD"` configuré, ce qui n'est possible que si la branche `SGD` a été correctement atteinte et instanciée avec ses propres paramètres — toute confusion de branche aurait produit un échec immédiat à la construction, avant tout step. Aucun log runtime de cette exécution ne nomme explicitement l'optimizer (vérifié : aucune occurrence de "sgd"/"optimizer" dans la sortie complète du process) — la réussite réelle du run jusqu'au step GPU est donc la preuve retenue, exactement comme anticipé par cette section avant l'exécution.

Aucun changement d'environnement CUDA/Torch/OneTrainer/drivers/checkpoint.

## 9. Critères de clôture

1. `OneTrainerOptimizerSettings`/`OneTrainerSettings` round-trip exact, rétrocompatible avec tout `project.json` antérieur ne portant pas `optimizer_settings`.
2. `build_training_config()` traduit exactement `optimizer`/`extra_overrides` vers la structure nichée réelle quand configurés, et ne change rien quand ils ne le sont pas (comparaison byte-à-byte).
3. Collision à deux niveaux appliquée et testée : racine `"optimizer"` protégée globalement, sous-clé `"optimizer"` protégée localement, tout autre sous-paramètre restant librement accessible via `optimizer_settings.extra_overrides`.
4. Rejet explicite et actionnable de la clé racine héritée `OneTrainerSettings.extra_overrides["optimizer"]`, jamais de migration silencieuse — testé explicitement avec un scénario reproduisant un ancien projet hand-edit.
5. UI minimale fonctionnelle pour le nouveau champ, même contrat dirty-state que l'existant, scroll M121 non affecté.
6. Suite complète verte au nombre exact, aucune régression sur les tests hérités de Mission 121.
7. Aucun changement de comportement pour un Training existant qui ne configure aucune donnée optimizer — vérifié par test explicite.
8. Smoke réel SD1.5 de bout en bout validé avec `optimizer="SGD"` explicitement configuré, sans modification d'environnement.

## 10. Autorisation

Mission autorisée par l'architecte après micro-audit dédié du contrat `Optimizer` réel d'OneTrainer et une vérification architecturale finale explicitement déclenchée par l'architecte sur le brouillon initial de cette mission. Décisions architecturales actées explicitement : (1) le discriminant `optimizer` vit exclusivement dans une nouvelle structure imbriquée `OneTrainerOptimizerSettings`, jamais un champ plat direct de `OneTrainerSettings`, précisément pour porter sa propre échappatoire scopée ; (2) la réservation de la racine `"optimizer"` dans `_STRUCTURED_CONFIG_KEYS` (niveau global) est distincte et complémentaire d'une nouvelle réservation locale `_OPTIMIZER_STRUCTURED_SUBKEYS` (niveau optimizer), permettant de protéger le discriminant sans jamais bloquer les sous-paramètres non encore typés — corrigeant une régression de capacité identifiée avant toute implémentation ; (3) un `project.json` hérité portant déjà `extra_overrides["optimizer"]` (légal avant cette mission) doit être rejeté explicitement et de façon actionnable au moment de la préparation, jamais migré silencieusement ; (4) l'UI M122 se limite à `ADAM`/`ADAMW`/`SGD` — les trois seules valeurs de l'enum réel utilisant directement `torch.optim` sans dépendance tierce — jamais présentée comme la liste complète OneTrainer, le Domain restant capable de représenter les 43 valeurs réelles.
