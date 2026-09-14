# Mission 120 — Training Configuration Foundation (Generic / OneTrainer-Structured / Extra Overrides)

> **MISSION PRÉPARÉE, NON IMPLÉMENTÉE.** Ce document fixe le périmètre autorisé par l'architecte après le micro-audit post-Mission 119 et sa décision architecturale de correction. Aucun code n'est encore écrit. Implémentation à ouvrir uniquement après validation explicite de ce document.

## 1. Contexte

Le micro-audit post-Mission 119 a confirmé, en lisant le code réel de l'intégration (`src/domain/training.py`, `src/engines/onetrainer_config.py`, `src/managers/training_manager.py`) et le schéma réel de l'installation OneTrainer présente sur la machine (`J:\Programmes\Onetrainer\modules\util\config\TrainConfig.py`, `ConceptConfig.py`, enums réels, 52 presets JSON réels) que :

- `Training` n'expose que 7 champs (`base_model_source`, `architecture`, `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `trigger_word`) alors que `TrainConfig` réel comporte environ 150 champs.
- `src/engines/onetrainer_config.py::build_training_config()` n'en traduit que 8, le reste retombant sur les défauts internes d'OneTrainer — dont certains sont concrètement moins bons que les presets officiels du même OneTrainer (`batch_size` jamais envoyé → `1` de fait, contre `4` dans les presets SD1.5/SDXL/Flux officiels ; `weight_dtype` des composants jamais envoyé → `FLOAT_32` de fait, contre `FLOAT_16` dans ces mêmes presets).
- Le mécanisme de snapshot (`TrainingJob.config_snapshot_path`, une copie JSON complète figée à chaque Start dans `<workspace>/training/<id>/jobs/<job_id>/onetrainer_config.json`) est déjà correct et n'a pas besoin d'être repensé — seul ce qui alimente ce dict doit grandir.

L'objectif produit à long terme, fixé explicitement par l'architecte : **AI Studio Toolkit doit pouvoir configurer et lancer tous les entraînements OneTrainer supportés que le projet décidera de couvrir, sans jamais obliger l'architecte à ouvrir l'interface OneTrainer pour un réglage avancé.** L'UI peut organiser/masquer la complexité, elle ne doit jamais supprimer de capacité.

Mission 120 est explicitement la **fondation** de cette trajectoire — pas une couverture complète, pas une UI Advanced, pas une optimisation des valeurs par défaut pour cette machine.

## 2. Objectif de M120

Poser l'architecture Domain/persistance/traduction qui permettra aux missions suivantes d'exposer progressivement l'intégralité des réglages OneTrainer pertinents, en distinguant explicitement les niveaux de configuration ci-dessous, et prouver que cette architecture fonctionne réellement de bout en bout avec un petit ensemble représentatif de champs, **chacun placé au niveau où il appartient réellement dans le schéma OneTrainer** — sans changer le comportement d'un seul Training existant qui ne configure pas explicitement ces nouveaux champs.

## 3. Décision architecturale

### 3.1 Décision retenue — `OneTrainerSettings` dans le Domain, structure dédiée plutôt qu'un dictionnaire libre comme mécanisme principal

**Décision actée par l'architecte, non plus ouverte.** `Training` porte directement une configuration OneTrainer structurée :

```
Training
├── champs génériques (indépendants du provider — inchangés dans leur nature)
└── onetrainer_settings: OneTrainerSettings
        ├── quelques réglages OneTrainer structurés, typés (grandit mission après mission)
        └── extra_overrides: dict (échappatoire pour tout réglage non encore modélisé)
```

Le fait que `OneTrainerSettings` porte le nom du provider et vive dans `src/domain/` est jugé acceptable pour la raison retenue par l'architecte : **il s'agit d'une configuration persistante appartenant réellement au `Training`** (elle décrit ce qui doit être entraîné et comment, au même titre que `epochs`/`learning_rate`), **pas d'un détail d'exécution temporaire** — contrairement, par exemple, aux chemins internes calculés par `TrainingManager` (niveau 4, jamais dans le Domain). OneTrainer est aujourd'hui le seul moteur Training réellement intégré dans le code — introduire une abstraction multi-provider (`TrainingProviderConfig` + discriminant `provider: str`) sans second provider réel serait le scaffolding sans consommateur actuel que `CLAUDE.md` interdit explicitement. **Si un second provider Training devient un besoin réel**, `OneTrainerSettings` sera refactorée vers une abstraction commune à ce moment-là, jamais anticipée maintenant.

`OneTrainerSettings` vit dans `src/domain/onetrainer_settings.py`, dataclass Qt-free, même convention `to_dict()`/`from_dict()` que tout le reste du Domain.

### 3.2 Sentinelles « non configuré » — critère explicite, pas une convention automatique

Chaque nouveau champ a besoin d'une valeur qui signifie sans ambiguïté « l'utilisateur n'a pas configuré ceci, laisse OneTrainer appliquer son propre comportement historique ». `0`/`""`/`False` ne sont des sentinelles valides **que lorsqu'elles ne peuvent jamais être une valeur OneTrainer légitime pour ce champ précis** — vérifié individuellement pour chaque champ de cette mission (section 4), jamais supposé par défaut. Pour un champ où `0`/`False`/`""` seraient des valeurs réelles possibles, la représentation retenue est `None` (`Optional[T] = None`), cohérent avec la distinction déjà actée en permanence par ce projet entre une valeur scalaire légitime et « non fourni » (`CLAUDE.md` — *« Chaîne vide ("") est une valeur légitime, distincte de "non fourni" (None) »*, déjà appliqué à `update()`/idempotence ; le même principe s'applique ici au choix de la sentinelle de configuration).

C'est précisément ce critère qui a fait retirer `seed` du périmètre de cette mission (section 4) : `seed` est un entier où `0` est une valeur de graine aléatoire parfaitement légitime dans la convention OneTrainer — l'utiliser comme sentinelle « non configuré » aurait été un bug latent, pas une simplification.

### 3.3 Politique de fusion — quatre niveaux, priorité explicite, jamais un ordre implicite

Ordre de construction retenu, dans les termes de l'architecte :

1. **Configuration OneTrainer historique/base** — tout ce que `build_training_config()` ne traduit toujours pas explicitement retombe sur les défauts internes d'OneTrainer (`BaseConfig.from_dict()` sur `TrainConfig.default_values()`), exactement comme aujourd'hui.
2. **Paramètres structurés explicitement configurés** — champs génériques de `Training` (niveau générique) puis champs typés de `OneTrainerSettings` (niveau OneTrainer structuré), fusionnés dans le dict construit par `build_training_config()` uniquement quand ils diffèrent de leur sentinelle « non configuré » (section 3.2).
3. **`extra_overrides` autorisés** — fusionnés uniquement après validation (voir ci-dessous), jamais avant les niveaux 1-2, jamais après le niveau 4.
4. **Valeurs internes/protégées imposées par Toolkit en dernier** — `workspace_dir`, `cache_dir`, `debug_dir`, `output_model_destination`, `concept_file_name`/chemin du concept, `__version` : **déjà appliqué aujourd'hui**, sans changement requis (`TrainingManager.create_job()` réécrit déjà inconditionnellement ces clés après avoir chargé le JSON préparé) — ce comportement existant devient la garantie de dernier rempart, pas une nouveauté de cette mission.

**Double protection contre une source de vérité contradictoire, appliquée dans `build_training_config()` avant toute fusion de `extra_overrides`, centralisée et testée explicitement** :

- **Liste de clés strictement interdites**, centralisée dans une seule constante nommée (`_PROTECTED_CONFIG_KEYS`) : `workspace_dir`, `cache_dir`, `debug_dir`, `output_model_destination`, `concept_file_name`, `concepts`, `__version`. Toute présence dans `extra_overrides` lève `OneTrainerConfigError` explicitement, nommant la ou les clés fautives — jamais un écrasement silencieux ultérieur par le niveau 4.
- **Détection de collision avec les clés déjà couvertes par les niveaux 1-2**, centralisée dans une seconde constante nommée (`_STRUCTURED_CONFIG_KEYS`) : `model_type`, `base_model_name`, `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `batch_size`, `gradient_accumulation_steps`, `learning_rate_scheduler`, `training_method`, `output_model_format`. Toute présence dans `extra_overrides` lève également `OneTrainerConfigError` — jamais deux sources de vérité pour un même paramètre déjà structuré. Un utilisateur voulant changer l'une de ces valeurs doit le faire via son champ structuré, pas via `extra_overrides`.

Les deux constantes sont couvertes chacune par un test dédié qui énumère explicitement leur contenu (section 7) — une future mission qui ajoute un champ structuré doit l'ajouter à `_STRUCTURED_CONFIG_KEYS` au même moment, jamais après coup.

## 4. Champs réels introduits par M120 (ensemble représentatif, pas la configuration finale)

Choisis après vérification directe du schéma OneTrainer réel et du critère de sentinelle (section 3.2) — **chaque champ n'est retenu que si son niveau de configuration réel est correctement représenté**, quitte à réduire l'ensemble de démonstration plutôt que de forcer un mauvais niveau :

| Champ | Niveau | Type OneTrainer réel confirmé | Sentinelle « non configuré » | Justification de la sentinelle |
|---|---|---|---|---|
| `Training.batch_size` | Générique (`Training`) | `TrainConfig.batch_size: int`, défaut réel `1` | `0` | `0` n'est jamais une taille de batch valide pour un entraînement réel — sentinelle sûre, même convention déjà établie que `Training.resolution` (Mission 097) |
| `Training.gradient_accumulation_steps` | Générique (`Training`) | `TrainConfig.gradient_accumulation_steps: int`, défaut réel `1` | `0` | idem — `0` pas de sens réel pour un nombre de pas d'accumulation |
| `OneTrainerSettings.learning_rate_scheduler` | Structuré OneTrainer | `TrainConfig.learning_rate_scheduler: LearningRateScheduler`, défaut réel `CONSTANT` | `""` | chaîne vide n'est jamais une des valeurs réelles de l'enum — sentinelle sûre. Vocabulaire exposé restreint à `CONSTANT`/`LINEAR`/`COSINE`/`COSINE_WITH_RESTARTS`/`COSINE_WITH_HARD_RESTARTS`/`REX`/`ADAFACTOR` — **`CUSTOM` explicitement exclu** (nécessiterait `custom_learning_rate_scheduler`/`scheduler_params`, hors périmètre) |
| `OneTrainerSettings.extra_overrides` | Extra/raw | n/a — mécanisme générique | `{}` | dict vide = aucune clé supplémentaire ajoutée, sans ambiguïté possible |

**`seed` retiré du périmètre de cette mission** : confirmé dans `ConceptConfig.py` qu'il s'agit d'un champ par concept (`ConceptConfig.seed`), jamais un champ `TrainConfig` de premier niveau — et `0` y est une valeur de graine légitime, disqualifiant la sentinelle utilisée pour les deux champs ci-dessus (section 3.2). Le forcer sur `Training` uniquement pour disposer d'un quatrième champ de démonstration aurait été une mauvaise représentation du modèle réel. Les réglages par Dataset/Concept (dont `seed`, l'augmentation d'image, le balancing/repeats, le tag dropout) feront l'objet de leur propre structure dédiée lorsqu'une future mission exposera les paramètres Dataset/Concept avancés — non traité ici.

Cet ensemble réduit à 3 champs réels (2 génériques + 1 structuré OneTrainer) plutôt que 4 est délibéré et préférable à une abstraction incorrecte — il valide néanmoins le chemin complet `Training → persistance → OneTrainerSettings/extra_overrides → build_training_config() → Prepare → TrainingJob snapshot` pour les deux niveaux réellement introduits par cette mission.

**Aucune valeur par défaut de production n'est changée par cette mission** — chaque nouveau champ utilise une sentinelle « non configuré » qui reproduit exactement le comportement actuel (silence = défaut OneTrainer déjà en vigueur aujourd'hui, jamais une valeur Toolkit imposée). La correction des défauts identifiés comme sous-optimaux par le micro-audit (`batch_size`, `weight_dtype`) est explicitement différée à une mission ultérieure, avec sa propre justification et son propre test réel.

## 5. Fichiers concernés

- `src/domain/onetrainer_settings.py` (nouveau) — `OneTrainerSettings` (dataclass : `learning_rate_scheduler: str = ""`, `extra_overrides: dict = field(default_factory=dict)`, `to_dict()`/`from_dict()`).
- `src/domain/training.py` (modifié) — nouveaux champs `batch_size: int = 0`, `gradient_accumulation_steps: int = 0`, `onetrainer_settings: OneTrainerSettings = field(default_factory=OneTrainerSettings)` ; `to_dict()`/`from_dict()` étendus, rétrocompatibles (`data.get(key, default)`, garde `isinstance(x, dict)` sur le sous-objet imbriqué comme pour tout objet Domain imbriqué existant dans ce projet).
- `src/engines/onetrainer_config.py` (modifié) — `build_training_config()` gagne des paramètres optionnels (`batch_size=0`, `gradient_accumulation_steps=0`, `onetrainer_settings=None`) ; ajout de `_PROTECTED_CONFIG_KEYS`/`_STRUCTURED_CONFIG_KEYS` et de la validation de collision (section 3.3).
- `src/managers/training_manager.py` (modifié) — `prepare_onetrainer_config()` transmet les nouveaux champs de `Training`/`OneTrainerSettings` à `build_training_config()` ; **aucun changement à `create_job()`** (le comportement de niveau 4 est déjà correct, voir section 3.3).
- `src/ui/pages/training_page.py` (modifié, minimal) — 3 nouveaux champs dans le `QFormLayout` existant (`batch_size_spinbox`, `gradient_accumulation_steps_spinbox`, `learning_rate_scheduler_combo`), même câblage dirty-state que les champs existants (`_on_training_parameters_changed`, `_load_training_parameters()`, `save_training_parameters()`) — **aucune nouvelle section/catégorie, aucun réagencement visuel** : ce n'est pas l'UI Advanced, seulement 3 lignes de plus dans le formulaire actuel, pour rendre les nouveaux champs réellement testables depuis un vrai parcours utilisateur. Aucune UI pour `extra_overrides` dans cette mission.
- `tests/integration/test_training_roundtrip.py` (modifié) — confirmé comme le fichier réel couvrant à la fois le round-trip Domain `Training` **et** `TrainingPage` (`_load_training_parameters()`/`architecture_combo`/dirty-state) ; il n'existe pas de `test_training_page.py` séparé dans ce projet. Round-trip des nouveaux champs `Training`/`OneTrainerSettings`, rétrocompatibilité d'un `project.json` sans ces clés, et les 3 nouveaux champs de formulaire (dirty-state, sauvegarde, rechargement) y sont ajoutés.
- `tests/integration/test_onetrainer_config.py` (modifié) — traduction des nouveaux champs, protection des clés internes, détection de collision, non-régression du dict produit quand rien n'est configuré (comparaison byte-à-byte avec le dict actuel pour SD15/SDXL/FLUX).
- `tests/integration/test_training_job_runner.py` — à auditer en début d'implémentation pour confirmer si une modification est réellement nécessaire (le contrat de snapshot lui-même ne change pas ; seul le contenu du dict copié peut différer si un Training de test configure les nouveaux champs).

**Aucun changement** à `TrainingJob` (Domain), au mécanisme de snapshot lui-même (`create_job()`'s copy-then-override), à `ForgeEngine`/`ComfyUIEngine`/tout autre Manager, à l'EventBus.

## 6. Hors périmètre strict

- Grande UI Advanced (sections repliables, organisation par catégories façon `SettingsPage` Mission 118) — différée.
- Presets utilisateur (`TrainingPreset`, dupliquer/modifier) — différé, architecture pensée pour rester compatible mais rien d'implémenté ici.
- Réglages par Dataset/Concept (`seed`, augmentation d'image, balancing/repeats, tag dropout) — différés à une future structure dédiée (section 4).
- Couverture des 26 `ModelType` réels — reste à `SD15`/`SDXL`/`FLUX` (Toolkit) uniquement.
- Validation réelle de Flux sur cette machine (VRAM/flow-matching) — non traité.
- Toute modification de l'environnement CUDA/Torch/OneTrainer.
- Changement massif des valeurs par défaut (`batch_size`, `weight_dtype`, etc.) — explicitement différé, voir section 4.
- Éditeur JSON avancé complet pour `extra_overrides` — le champ existe et se sérialise correctement, mais n'a aucune UI dans cette mission.
- Variantes PEFT au-delà de LoRA (`LoHa`/`OFT`/`LoKr`), embedding/fine-tune methods (`training_method` reste `"LORA"` uniquement).

## 7. Tests prévus

1. **Round-trip `Training`** : nouveaux champs (`batch_size`, `gradient_accumulation_steps`, `onetrainer_settings`) survivent à `to_dict()`/`from_dict()` à l'identique, y compris `extra_overrides` non vide.
2. **Rétrocompatibilité** : un `project.json` construit sans ces nouvelles clés (simulant un Training pré-M120) se charge avec les valeurs sentinelles par défaut, sans erreur, sans migration.
3. **Traduction exacte, niveaux 1-2** : `build_training_config()` avec `batch_size`/`gradient_accumulation_steps`/`learning_rate_scheduler` explicitement configurés produit exactement les clés OneTrainer attendues, avec les bonnes valeurs.
4. **Non-régression du comportement historique** : `build_training_config()` avec les nouveaux champs à leur valeur sentinelle produit un dict strictement identique (mêmes clés, mêmes valeurs) à celui produit avant cette mission pour SD15/SDXL/FLUX — comparaison explicite, pas seulement « pas d'exception ». **Critère d'acceptation central de cette mission.**
5. **`extra_overrides` autorisé, propagé** : une clé sans collision (ex. `"loss_weight_fn": "MIN_SNR_GAMMA"`) apparaît telle quelle dans le dict produit.
6. **`extra_overrides` protégé — chemins internes** : une clé de `_PROTECTED_CONFIG_KEYS` (ex. `"workspace_dir"`) fait lever `OneTrainerConfigError` par `build_training_config()`, sans jamais atteindre `TrainingJob`/le filesystem.
7. **`extra_overrides` protégé — collision avec un champ structuré** : une clé de `_STRUCTURED_CONFIG_KEYS` (ex. `"batch_size"`) présente dans `extra_overrides` fait lever `OneTrainerConfigError` explicitement, que `Training.batch_size` soit configuré ou non — jamais un écrasement silencieux dans un sens ou l'autre.
8. **Constantes protégées énumérées** : un test dédié vérifie le contenu exact de `_PROTECTED_CONFIG_KEYS`/`_STRUCTURED_CONFIG_KEYS`, pour qu'un oubli lors d'un futur ajout de champ structuré casse la suite plutôt que de rester silencieux.
9. **Snapshot `TrainingJob`** : `create_job()` produit un `config_snapshot_path` dont le contenu reflète exactement la configuration résolue au moment du Start, nouveaux champs inclus.
10. **Immutabilité du snapshot** : modifier `Training`/`OneTrainerSettings` (via `save_training_parameters()`/`TrainingManager.update()`) après un `create_job()` ne modifie jamais le fichier déjà écrit sous `jobs/<job_id>/onetrainer_config.json` — test déjà existant en principe pour les 7 champs actuels (Mission 100), étendu aux nouveaux.
11. **UI** : les 3 nouveaux champs suivent le même contrat dirty-state que les 8 champs existants (`_on_training_parameters_changed`, préservation d'un brouillon non sauvegardé, rechargement sur changement de Training actif).

Suite complète exécutée et nombre exact confirmé avant tout commit, comme pour toute mission.

## 8. Compatibilité avec les Trainings existants

Aucune migration. Tout `project.json` antérieur charge `batch_size=0`/`gradient_accumulation_steps=0`/`onetrainer_settings=OneTrainerSettings()` (défauts sentinelles) et produit, une fois préparé, un dict `build_training_config()` strictement identique à celui produit par le code actuel — testé explicitement (section 7, test 4), pas seulement supposé. Un Training déjà existant, jamais retouché après cette mission, se comporte exactement comme avant.

## 9. Smoke réel

**Non lancé dans cette mission sans validation explicite de l'architecte.** Un smoke réel n'a de sens que si l'implémentation venait à changer la configuration effectivement envoyée à un run historique (ce que cette mission évite explicitement, section 4/8) — ou si l'architecte souhaite, une fois l'implémentation faite, prouver qu'un Training explicitement configuré avec un des trois nouveaux champs (ex. `batch_size=2`) lance réellement un run OneTrainer valide, en réutilisant l'environnement déjà validé par les Missions 097-101 (Quadro P4000, patch `close_pipe()` local, torch `+cu126`) sans aucune modification d'environnement. À proposer, jamais à exécuter automatiquement.

## 10. Documentation de la cible long terme

`docs/PROJECT_CONTEXT.md` devra, à la clôture de cette mission, documenter explicitement la trajectoire validée par l'architecte : **AI Studio Toolkit doit permettre de configurer et lancer tous les entraînements OneTrainer que le projet décidera de supporter, sans jamais nécessiter l'ouverture de l'interface OneTrainer pour un réglage avancé** — l'UI organise/masque la complexité, elle ne retire jamais de capacité. Cette mission n'est qu'une fondation ; `OneTrainerSettings` est délibérément conçue pour grandir mission après mission (section 3.1) sans jamais nécessiter de nouvelle refonte architecturale — seul le nombre de champs structurés augmente. Si un second provider Training devenait un jour un besoin réel, `OneTrainerSettings` serait refactorée vers une abstraction commune à ce moment-là — décision explicitement différée, jamais anticipée par cette mission.

## 11. Critères de clôture

1. `Training`/`OneTrainerSettings` round-trip exact, rétrocompatible avec tout `project.json` antérieur.
2. `build_training_config()` traduit exactement les 3 nouveaux champs représentatifs quand ils sont configurés, et ne change rien quand ils ne le sont pas.
3. Politique de fusion à quatre niveaux appliquée et testée : chemins internes jamais détournables, jamais deux sources de vérité pour un même paramètre structuré, constantes protégées centralisées et testées.
4. Snapshot `TrainingJob` inchangé dans son mécanisme, étendu dans son contenu, toujours immuable après coup.
5. UI minimale fonctionnelle pour les 3 nouveaux champs, même contrat dirty-state que l'existant.
6. Suite complète verte au nombre exact, aucune régression sur les 2399 tests hérités de Mission 119.
7. Aucun changement de comportement pour un Training existant qui ne configure aucun des nouveaux champs — vérifié par test explicite, pas par absence de crash.

## 12. Autorisation

Mission autorisée par l'architecte après micro-audit du code réel de l'intégration OneTrainer, avec les corrections architecturales suivantes actées explicitement : (1) `OneTrainerSettings`, structure dédiée dans le Domain, comme mécanisme principal de configuration OneTrainer structurée — jamais un dictionnaire libre en première intention, celui-ci (`extra_overrides`) restant un échappatoire secondaire, snapshoté et protégé par une politique de fusion à quatre niveaux explicitement centralisée et testée ; (2) aucun changement arbitraire des valeurs de training existantes — les presets officiels OneTrainer restent une référence future, pas une justification suffisante pour modifier silencieusement le comportement actuel ; (3) chaque champ de démonstration introduit doit être placé au niveau où il appartient réellement dans le schéma OneTrainer, quitte à réduire l'ensemble représentatif (`seed` retiré pour cette raison) plutôt que de forcer un mauvais niveau pour atteindre un nombre de champs arbitraire.
