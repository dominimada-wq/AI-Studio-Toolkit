# Mission 121 — Advanced Training Settings: Precision / Weight Dtypes

> **MISSION CLÔTURÉE.** Implémentée exactement selon ce document, validée par la suite complète (2444/2444) et par un smoke réel SD1.5 de bout en bout contre l'installation OneTrainer réelle, commitée, taguée et publiée. Commit fonctionnel `d07c063b73ca6d7b6d4da7453855579d59578c60` (`Add advanced OneTrainer precision settings`), tag `v0.2-mission121`, GitHub Release publiée. Un correctif post-release distinct (section 12) a ensuite rendu `TrainingPage` verticalement défilable — commit `c5c6850dacb058b387afc2d4915ca12066da3362` (`Fix Training page vertical scrolling`), jamais rattaché au tag `v0.2-mission121` ni à la Release déjà publiée.

## 1. Contexte

Le micro-audit dédié (lecture seule, `J:\Programmes\Onetrainer\modules\util\config\TrainConfig.py`, enums réels, presets JSON officiels) a établi que le comportement historique actuel de Toolkit — aucun champ dtype jamais envoyé à OneTrainer — laisse tous les `weight_dtype` par composant (`unet`/`transformer`/`text_encoder`/`text_encoder_2`/`vae`/`lora`/`embedding`) retomber sur le défaut réel `FLOAT_32` d'OneTrainer, alors que `train_dtype` (calcul) est déjà `FLOAT_16` par défaut. Les presets LoRA officiels SD1.5/SDXL ne modifient que les `weight_dtype` par composant (`FLOAT_16` pour `unet`/`text_encoder(_2)`, `FLOAT_32` conservé pour `vae`) et `batch_size` — jamais `optimizer`, jamais les mécanismes mémoire adjacents (gradient checkpointing/offloading/quantification), qui ne sont d'ailleurs pas câblés pour SD1.5/SDXL dans les modelLoaders réels (`StableDiffusionModel.py`/`StableDiffusionXLModel.py` ne possèdent aucun `LayerOffloadConductor`). Le candidat 1 identifié lors de l'audit post-Mission 120 est donc scindé : M121 couvre uniquement la **variante A — Precision/Memory (dtypes)**, seul sous-ensemble pour lequel l'audit apporte une preuve directe d'utilité pour les trois architectures actuellement exposées (SD1.5/SDXL/FLUX_DEV_1). `optimizer` est explicitement différé à une mission ultérieure.

## 2. Objectif de M121

Introduire la première vraie structure `Training parameters` / `Advanced settings` dans `TrainingPage`, avec une sous-section `Precision / Memory`, et permettre à `Training` de représenter explicitement les dtypes OneTrainer pertinents pour SD1.5/SDXL/FLUX_DEV_1 — **sans changer aucun défaut historique**. Un Training qui ne configure aucun des nouveaux champs doit produire, après M121, une configuration OneTrainer strictement identique à celle produite par le code issu de M120 (comportement M120 inchangé, critère d'acceptation central, comme pour M120 lui-même vis-à-vis de M119).

## 3. Décision architecturale

### 3.1 Champs Domain retenus — extension de `OneTrainerSettings`

Six nouveaux champs `str = ""` sur `OneTrainerSettings`, sentinelle `""` = non configuré (jamais une valeur `DataType` réelle — confirmé dans l'audit qu'aucune valeur vide n'existe dans l'enum réel) :

```
OneTrainerSettings
├── learning_rate_scheduler: str = ""   (existant, M120)
├── extra_overrides: dict               (existant, M120)
├── train_dtype: str = ""               (nouveau — dtype de calcul, global)
├── unet_weight_dtype: str = ""         (nouveau — composant unet, SD1.5/SDXL)
├── transformer_weight_dtype: str = ""  (nouveau — composant transformer, FLUX)
├── text_encoder_weight_dtype: str = "" (nouveau — composant text_encoder, les 3 architectures)
├── text_encoder_2_weight_dtype: str = ""  (nouveau — composant text_encoder_2, SDXL/FLUX)
└── vae_weight_dtype: str = ""          (nouveau — composant vae, les 3 architectures)
```

**`unet_weight_dtype` et `transformer_weight_dtype` restent deux champs strictement distincts, jamais fusionnés** — même si l'UI les présente comme un seul concept ergonomique « modèle principal » (section 7). Ce choix suit le vocabulaire réel du backend (`TrainConfig.unet`/`TrainConfig.transformer` sont deux composants distincts, jamais interchangeables — confirmé dans `modules/model/StableDiffusionModel.py`/`FluxModel.py`) plutôt qu'une abstraction Toolkit qui masquerait cette distinction dans la persistance.

`to_dict()`/`from_dict()` étendus symétriquement, même convention que les champs M120 (`data.get(key, "")`), rétrocompatibles avec tout `project.json` écrit avant M121.

### 3.2 Vocabulaire dtype — quatre niveaux strictement distincts, jamais confondus

Une capacité à représenter syntaxiquement une valeur n'est **jamais** une preuve de compatibilité — ni architecturale, ni matérielle. Quatre niveaux séparés, chacun avec sa propre autorité :

1. **Vocabulaire OneTrainer représentable (persistance/Domain)** : les 6 champs sont de simples `str`, capables de porter n'importe laquelle des 13 valeurs réelles de l'enum `DataType` audité (`NONE`/`FLOAT_8`/`FLOAT_16`/`FLOAT_32`/`BFLOAT_16`/`TFLOAT_32`/`INT_8`/`NFLOAT_4`/`FLOAT_W8A8`/`INT_W8A8`/`GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT`) — jamais une enum Toolkit réduite qui prétendrait être le contrat complet. Un `project.json` contenant une valeur non proposée par l'UI actuelle (écrite à la main, ou par une UI future élargie) reste chargée telle quelle, sans erreur — même tolérance défensive que `learning_rate_scheduler` déjà établie par M120. **Accepter syntaxiquement une valeur à ce niveau ne dit rien de plus que « ce texte peut être stocké et transmis »** — ni qu'un composant donné l'accepte, ni qu'elle fonctionne sur notre matériel.
2. **Compatibilité architecture** (section 3.3) : `_DTYPE_FIELDS_BY_ARCHITECTURE` détermine uniquement **quel champ** (quel composant) est valide pour quelle architecture (ex. `transformer_weight_dtype` invalide pour `SD15`) — ce niveau ne dit rien sur **quelles valeurs** de `DataType` sont elles-mêmes chargeables par ce composant.
3. **Vocabulaire proposé par l'UI (M121)** : restreint à 4 valeurs non quantifiées, confirmées réellement chargeables par les modelLoaders SD1.5/SDXL/Flux audités (aucun modelLoader de ces trois familles n'implémente de chemin de chargement quantifié — `NFLOAT_4`/`FLOAT_8`/`INT_W8A8`/`GGUF*` ne sont câblés que pour les familles DiT modernes absentes de Toolkit) : `FLOAT_16`, `FLOAT_32`, `BFLOAT_16`, `TFLOAT_32`. **Identique pour les trois architectures**, y compris Flux : le fait qu'un preset officiel Flux utilise `NFLOAT_4`/`FLOAT_8`/`INT_W8A8` prouve seulement que ces valeurs sont représentables au niveau 1 et chargeables par *certains* modelLoaders au niveau 2 (les familles DiT modernes) — **ce n'est ni une preuve de compatibilité avec la Quadro P4000/Pascal/sm_61, ni une raison de les proposer dans l'UI de cette mission**, faute de toute vérification de kernel quantifié effectuée sur ce matériel.
4. **Compatibilité matériel réellement démontrée** : vide à ce jour — aucune valeur, même parmi les 4 proposées par l'UI, n'a encore été prouvée par un smoke réel avant l'exécution de la section 9. Le smoke M121 validera un sous-ensemble concret, sans que cela n'élargisse automatiquement le vocabulaire UI (niveau 3) ni ne devienne un nouveau défaut (section 3.6).

### 3.3 Validation par architecture — Domain/translation, pas seulement UI

Chaque architecture n'expose qu'un sous-ensemble réel de composants (confirmé directement dans `modules/model/*.py`, pas seulement dans les presets) :

| Architecture | Composant "modèle principal" | Text Encoder 2 | Champs dtype valides |
|---|---|---|---|
| `SD15` | `unet_weight_dtype` | absent | `train_dtype`, `unet_weight_dtype`, `text_encoder_weight_dtype`, `vae_weight_dtype` |
| `SDXL` | `unet_weight_dtype` | présent | `train_dtype`, `unet_weight_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype` |
| `FLUX_DEV_1` (Toolkit `"FLUX"`) | `transformer_weight_dtype` | présent | `train_dtype`, `transformer_weight_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype` |

**Double protection, jamais UI seule** :
- **UI** : `training_page.py` masque les lignes de formulaire non pertinentes pour l'architecture sélectionnée (ex. `transformer_weight_dtype` invisible quand `architecture == "SD15"`) — empêche un utilisateur normal de configurer un champ incompatible.
- **Domain/translation, toujours active, indépendante de l'UI** : `build_training_config()` reçoit une nouvelle constante `_DTYPE_FIELDS_BY_ARCHITECTURE` (architecture → ensemble des noms de champs Toolkit valides, table ci-dessus) et **lève `OneTrainerConfigError` explicitement**, nommant l'architecture et le ou les champs fautifs, si un champ dtype hors de cet ensemble est non vide — que la valeur incompatible provienne de l'UI (normalement impossible), d'un `project.json` édité à la main, ou d'un futur appelant direct. Jamais un envoi silencieux d'un composant qui n'existe pas pour l'architecture choisie.

### 3.4 Traduction vers la structure imbriquée réelle d'OneTrainer

`build_training_config()` traduit chaque champ Toolkit plat non vide vers la clé nichée réelle correspondante :

| Champ Toolkit | Clé OneTrainer générée |
|---|---|
| `train_dtype` | `"train_dtype"` (plate, globale) |
| `unet_weight_dtype` | `{"unet": {"weight_dtype": ...}}` |
| `transformer_weight_dtype` | `{"transformer": {"weight_dtype": ...}}` |
| `text_encoder_weight_dtype` | `{"text_encoder": {"weight_dtype": ...}}` |
| `text_encoder_2_weight_dtype` | `{"text_encoder_2": {"weight_dtype": ...}}` |
| `vae_weight_dtype` | `{"vae": {"weight_dtype": ...}}` |

Confirmé compatible avec le mécanisme de fusion partielle réel d'OneTrainer (`BaseConfig.from_dict()` merge un dict partiel sur `TrainModelPartConfig.default_values()`, même précédent que `concepts` depuis M097) : n'envoyer que `{"weight_dtype": ...}` laisse tous les autres champs du composant (`include`/`train`/`learning_rate`/`dropout_probability`/...) à leur défaut OneTrainer, jamais dupliqués ni réinventés par Toolkit.

### 3.5 Politique `extra_overrides` — clés nichées, jamais un écrasement silencieux

`_STRUCTURED_CONFIG_KEYS` (déjà centralisée et testée depuis M120) gagne 6 entrées : `"train_dtype"` (plate) et **`"unet"`, `"transformer"`, `"text_encoder"`, `"text_encoder_2"`, `"vae"`** (les clés nichées elles-mêmes, pas un sous-chemin). Le mécanisme de détection reste strictement celui déjà en place, sans logique de fusion nichée spécifique nouvelle : `_STRUCTURED_CONFIG_KEYS & extra_overrides.keys()` interdit tout simplement à `extra_overrides` de porter une clé top-level `"unet"`/`"transformer"`/`"text_encoder"`/`"text_encoder_2"`/`"vae"`, quelle que soit sa forme (dict complet ou partiel) — un utilisateur voulant fixer `unet.weight_dtype` doit passer par `OneTrainerSettings.unet_weight_dtype`, jamais par `extra_overrides["unet"]`, qui lèverait `OneTrainerConfigError` explicitement. **Réservation inconditionnelle**, comme pour `batch_size`/`gradient_accumulation_steps` depuis M120 (test dédié M120 §7 point 7) : ces 6 clés sont interdites dans `extra_overrides` que le Training configure ou non les champs dtype correspondants — jamais deux sources de vérité possibles pour le même sous-objet, même partiellement.

Ce choix évite délibérément d'introduire un mécanisme de fusion nichée générique (`extra_overrides` scopé par sous-objet) — non nécessaire tant qu'aucun besoin réel de personnaliser un champ non modélisé d'un `TrainModelPartConfig` (ex. `dropout_probability` d'un composant) n'est démontré ; à réévaluer par une mission future si un tel besoin apparaît.

### 3.6 Comportement historique strictement préservé

Chaque champ à sa sentinelle `""` est omis de la configuration générée — un Training pré-M121 (tous les nouveaux champs absents de son `project.json`, donc `""` par défaut) produit un dict `build_training_config()` strictement identique à celui produit par le code M120, testé explicitement par comparaison, jamais seulement supposé. M121 n'injecte **jamais** `FLOAT_16`/`BFLOAT_16` ou toute autre valeur au nom d'un défaut ou d'un preset officiel OneTrainer — seule une configuration explicite de l'utilisateur produit une valeur dans le dict généré.

## 4. Composants réels par architecture (rappel condensé, voir 3.3)

- **SD1.5** (`modules/model/StableDiffusionModel.py`) : `unet`, `text_encoder` (CLIP), `vae`.
- **SDXL** (`modules/model/StableDiffusionXLModel.py`) : `unet`, `text_encoder`+`text_encoder_2` (CLIP-L + CLIP-G), `vae`.
- **FLUX_DEV_1** (`modules/model/FluxModel.py`) : `transformer` (jamais `unet`), `text_encoder`(CLIP)+`text_encoder_2`(T5), `vae`.

## 5. Fichiers concernés

- `src/domain/onetrainer_settings.py` (modifié) — 6 nouveaux champs `str = ""`, `to_dict()`/`from_dict()` étendus.
- `src/engines/onetrainer_config.py` (modifié) — nouveaux paramètres optionnels de `build_training_config()` (`train_dtype=""`, `unet_weight_dtype=""`, `transformer_weight_dtype=""`, `text_encoder_weight_dtype=""`, `text_encoder_2_weight_dtype=""`, `vae_weight_dtype=""`) ; nouvelle constante `_DTYPE_FIELDS_BY_ARCHITECTURE` et validation explicite (section 3.3) ; extension de `_STRUCTURED_CONFIG_KEYS` (section 3.5) ; traduction vers la structure nichée (section 3.4).
- `src/managers/training_manager.py` (modifié) — `prepare_onetrainer_config()` transmet les 6 nouveaux champs ; `update()` étendu (mutation in-place de `training.onetrainer_settings`, même précédent que `learning_rate_scheduler` depuis M120 — jamais un remplacement de l'objet qui perdrait `extra_overrides`).
- `src/ui/pages/training_page.py` (modifié) — nouvelle section repliable `Advanced settings` (bouton de titre + conteneur dont seule la visibilité change, voir section 7) avec sous-section `Precision / Memory` (5 combos + 1 pour `train_dtype`) ; visibilité/libellés/valeurs applicables recalculés sur changement d'architecture ; reset explicite à `""` des champs devenus incompatibles avec la nouvelle architecture (section 7).
- `tests/integration/test_onetrainer_config.py` (modifié) — traduction de chaque champ, validation par architecture (rejet explicite), collisions `extra_overrides` sur les 6 nouvelles clés, non-régression byte-à-byte du comportement M120.
- `tests/integration/test_training_roundtrip.py` (modifié) — round-trip `OneTrainerSettings`, rétrocompatibilité, dirty-state UI, changement d'architecture, snapshot immuable.
- `tests/integration/test_training_job_runner.py` — à auditer en début d'implémentation (même conclusion attendue que M120 : contrat de snapshot inchangé), non modifié sauf découverte contraire.

**Aucun changement** à `TrainingJob` (Domain), au mécanisme de snapshot (`create_job()`), à `ForgeEngine`/`ComfyUIEngine`, à l'EventBus, à `_PROTECTED_CONFIG_KEYS`.

## 6. Hors périmètre strict

- `optimizer`, tout paramètre spécifique à un optimizer, `optimizer_defaults` (confirmé par audit comme un cache exclusif à l'UI OneTrainer elle-même, jamais lu par l'entraînement réel).
- `gradient_checkpointing`, `enable_async_offloading`, `enable_activation_offloading`, `layer_offload_fraction` (confirmé non câblés pour SD1.5/SDXL — `LayerOffloadConductor` absent de leurs modelLoaders).
- `QuantizationConfig`/SVD, et toute valeur `DataType` quantifiée (`FLOAT_8`/`INT_8`/`NFLOAT_4`/`FLOAT_W8A8`/`INT_W8A8`/`GGUF*`) — non proposée dans l'UI de cette mission, pour aucune architecture.
- `fallback_train_dtype`, `lora_weight_dtype`, `embedding_weight_dtype` — jamais touchés par les presets officiels consultés, non retenus par cette mission.
- `text_encoder_3`/`text_encoder_4` (familles hors périmètre Toolkit).
- Réglages Dataset/Concept.
- Toute architecture de presets (`TrainingPreset`).
- Tout changement de défaut de production, toute optimisation automatique pour la Quadro P4000.
- Toute nouvelle architecture (`ModelType`) au-delà des trois déjà exposées.
- Toute modification de l'environnement CUDA/Torch/OneTrainer.

## 7. UI — `Training parameters` / `Advanced settings` → `Precision / Memory`

**Constat d'audit préalable** : aucun composant Qt de repli visuel de section n'existe actuellement dans `src/ui/` (vérifié par recherche exhaustive de `QToolButton`/`setArrowType`/`QGroupBox`/`QToolBox`/tout patron de bouton-titre → `setVisible()` sur un conteneur). Le seul mécanisme apparenté trouvé est `QCheckBox.toggled` connecté à l'activation/désactivation d'un widget dépendant (ex. `random_seed_checkbox` dans `InferencePage`) — un patron sémantiquement différent (« coché = ce réglage s'applique ») d'un repli purement visuel. Introduire une section repliable est donc une première pour ce projet.

**Correction actée après revue** : un `QGroupBox("Advanced settings")` rendu cochable (`setCheckable(True)`) a été explicitement écarté. `QGroupBox.setCheckable()` est la propriété Qt normalement destinée à **activer/désactiver** le contenu (un groupe décoché signifie conventionnellement « ce groupe de réglages ne s'applique pas »), jamais à le replier/déplier — l'utiliser pour un simple repli visuel créerait une ambiguïté réelle : un utilisateur pourrait légitimement lire « Advanced settings décoché » comme « ignorer les réglages avancés », alors que replier la section ne doit avoir **aucun** effet sur les valeurs déjà configurées.

**Décision retenue — section réellement repliable, mécanisme Qt simple, local à `TrainingPage`** :
- un `QToolButton` (ou bouton similaire) portant le titre `"Advanced settings"`, cliqué pour togger un état plié/déplié — jamais interprété comme une case à cocher/activer ;
- un `QWidget` conteneur (contenant la sous-zone `Precision / Memory` et ses widgets) dont seule la propriété `visible` change sur ce clic (`QWidget.setVisible()`) ;
- **replier/déplier ne modifie jamais aucune valeur des champs et ne déclenche jamais le dirty-state à lui seul** — seul un changement réel de valeur dans un des 6 widgets le déclenche, exactement comme pour tout autre champ du formulaire ;
- aucune nouvelle abstraction générale de type Accordion introduite pour cette mission — ce mécanisme reste local à `TrainingPage`, scopé à cette seule section ; une généralisation éventuelle (plusieurs catégories Advanced) sera une décision d'une mission future, seulement si un second besoin réel apparaît, jamais anticipée ici.

À l'intérieur du conteneur repliable, une sous-zone `Precision / Memory` (simple regroupement visuel, label de section ou second `QGroupBox` non cochable — à trancher au moment de l'implémentation selon ce qui reste le plus proche du style déjà utilisé par `training_form`) contient :

- **Training dtype** (combo, `train_dtype`) — proposé pour les trois architectures.
- **Main model weight dtype** (combo unique à l'écran, libellé dynamique « UNet » ou « Transformer » selon `architecture_combo` ; lié en interne à `unet_weight_dtype` **ou** `transformer_weight_dtype` selon l'architecture — jamais les deux en même temps affichés, jamais fusionnés dans la persistance, section 3.1).
- **Text Encoder weight dtype** (combo, `text_encoder_weight_dtype`) — les trois architectures.
- **Text Encoder 2 weight dtype** (combo, `text_encoder_2_weight_dtype`) — masqué pour `SD15`, visible pour `SDXL`/`FLUX`.
- **VAE weight dtype** (combo, `vae_weight_dtype`) — les trois architectures.

Chaque combo suit le même patron que `learning_rate_scheduler_combo` (M120) : premier item `"(non configuré)"` → `""`, items suivants → les 4 valeurs du vocabulaire UI (section 3.2), `findData()`/`setCurrentIndex()` avec repli explicite sur l'index 0 (`""`, jamais une valeur réelle par défaut) si la valeur chargée n'est pas dans la liste proposée.

**Changement d'architecture** : `on_architecture_changed()` (déjà existant) recalcule, dans l'ordre, (1) la visibilité des lignes (`text_encoder_2`, et le libellé dynamique du composant principal), (2) puis **réinitialise explicitement à `""` tout champ dtype devenu incompatible avec la nouvelle architecture** (ex. passer de `FLUX` à `SD15` remet `transformer_weight_dtype` à `""` s'il était configuré) — jamais une valeur silencieusement conservée hors de vue puis rejetée seulement au moment du `Start` par la validation Domain (section 3.3). Ce reset participe au dirty-state normal du formulaire au même titre qu'une modification manuelle de champ (`_on_training_parameters_changed`) — **mais reste un état de brouillon en mémoire, jamais persisté avant un `Save` explicite**, exactement comme toute autre modification de `training_form` : `Training.onetrainer_settings` sur disque n'est réécrit qu'au moment de `save_training_parameters()`, jamais au moment du changement d'architecture lui-même. Testable explicitement (section 8).

## 8. Tests

1. Round-trip `OneTrainerSettings` : les 6 nouveaux champs survivent à `to_dict()`/`from_dict()` à l'identique.
2. Rétrocompatibilité : un `project.json` sans ces clés se charge avec `""` partout, sans erreur.
3. Non-régression stricte du comportement M120 : les 6 champs à `""` produisent un dict `build_training_config()` identique à celui de M120, pour `SD15`/`SDXL`/`FLUX_DEV_1`.
4. Traduction de `train_dtype` quand configuré.
5. Traduction de chaque `weight_dtype` par composant quand configuré (5 champs × structure nichée attendue).
6. `SD15` : les 4 champs valides (`train_dtype`/`unet_weight_dtype`/`text_encoder_weight_dtype`/`vae_weight_dtype`) acceptés ; `transformer_weight_dtype`/`text_encoder_2_weight_dtype` non vides lèvent `OneTrainerConfigError`.
7. `SDXL` : les 5 champs valides acceptés ; `transformer_weight_dtype` non vide lève `OneTrainerConfigError`.
8. `FLUX_DEV_1` : les 5 champs valides acceptés ; `unet_weight_dtype` non vide lève `OneTrainerConfigError`.
9. `extra_overrides` : chacune des 6 nouvelles clés de `_STRUCTURED_CONFIG_KEYS` (`train_dtype`/`unet`/`transformer`/`text_encoder`/`text_encoder_2`/`vae`) testée individuellement, y compris quand le champ Toolkit correspondant n'est pas configuré (réservation inconditionnelle, section 3.5).
10. UI : dirty-state sur chacun des 6 nouveaux widgets, sauvegarde/rechargement, visibilité correcte par architecture, reset explicite des champs incompatibles sur changement d'architecture (avec assertion qu'aucune valeur non voulue n'apparaît après le changement).
11. Snapshot `TrainingJob` : immuabilité inchangée, contenu étendu aux nouveaux champs quand configurés.

Les 11 points ci-dessus sont couverts par 31 tests nets nouveaux (18 dans `tests/integration/test_onetrainer_config.py`, 13 dans `tests/integration/test_training_roundtrip.py`). Résultats réels : `test_onetrainer_config.py` **43/43** (25 hérités + 18 nets nouveaux), `test_training_roundtrip.py` **217/217** (204 hérités + 13 nets nouveaux), `test_training_job_runner.py` audité et confirmé **12/12** sans modification nécessaire (contrat de snapshot inchangé, comme prévu section 5). Suite complète exécutée : **2444/2444** (2413 hérités de Mission 120 + 31 nets nouveaux), 0 failure, 0 error, `git diff --check` propre. Une première tentative de capture non-verbose de la suite complète a produit une sortie tronquée dans l'environnement de session (artefact de bufferisation du shell, jamais un crash réel — confirmé par un second run identique en mode verbose/unbuffered aboutissant proprement à `OK`) ; sans rapport avec le code de cette mission.

## 9. Smoke réel

**Exécuté et validé, avec autorisation explicite de l'architecte, après la suite complète verte.** Scénario réutilisant le petit cas SD1.5 déjà validé par les Missions 097-101/120 (checkpoint `v1-5-pruned-emaonly-fp16.safetensors`, 1 image, résolution 512, 1 epoch), sans aucune modification d'environnement (Python/Torch/CUDA/OneTrainer/drivers/checkpoint inchangés). Un `Training` réel a été explicitement configuré avec un sous-ensemble du vocabulaire UI (section 3.2), valeurs reprises telles quelles du preset LoRA SD1.5 officiel d'OneTrainer (jamais présentées comme un nouveau défaut Toolkit) : `train_dtype="FLOAT_16"`, `unet_weight_dtype="FLOAT_16"`, `text_encoder_weight_dtype="FLOAT_16"`, `vae_weight_dtype="FLOAT_32"`. Chemin complet tracé et prouvé à chaque étape via des valeurs réelles observées : `Training`/`OneTrainerSettings` → `prepare_onetrainer_config()` (configuration préparée contenant `train_dtype`/`unet.weight_dtype`/`text_encoder.weight_dtype`/`vae.weight_dtype`) → `create_job()` (snapshot `TrainingJob.config_snapshot_path` contenant les mêmes valeurs) → lancement réel via `TrainingJobRunner` contre l'installation OneTrainer réelle. Résultat : process démarré réellement, checkpoint SD1.5 réellement chargé, un vrai step GPU exécuté (`loss=0.0852`), run terminé `succeeded` en 102.1 s, `lora.safetensors` réel produit (78 489 976 octets). Aucun script de smoke conservé dans le dépôt (scratchpad de session uniquement, nettoyé après exécution).

## 10. Critères de clôture

1. `OneTrainerSettings` round-trip exact, rétrocompatible avec tout `project.json` antérieur.
2. `build_training_config()` traduit exactement les 6 nouveaux champs vers la structure nichée réelle quand configurés, et ne change rien quand ils ne le sont pas (comparaison byte-à-byte, pas seulement absence d'erreur).
3. Validation par architecture appliquée au niveau Domain/translation (pas seulement UI), testée explicitement pour les trois architectures et les deux sens (champ valide accepté, champ invalide rejeté explicitement).
4. `extra_overrides` ne peut redéfinir aucune des 6 nouvelles clés structurées, testé individuellement et inconditionnellement.
5. UI minimale fonctionnelle pour les 6 nouveaux champs, changement d'architecture géré proprement (visibilité, libellés, reset explicite), même contrat dirty-state que l'existant.
6. Suite complète verte au nombre exact, aucune régression sur les tests hérités de Mission 120.
7. Aucun changement de comportement pour un Training existant qui ne configure aucun des nouveaux champs — vérifié par test explicite.
8. Smoke réel SD1.5 de bout en bout validé avec au moins un dtype explicitement configuré, sans modification d'environnement.

## 12. Correctif post-release — TrainingPage rendu verticalement défilable

**Hors périmètre fonctionnel de M121 elle-même** — aucun changement de comportement `Training`, aucune valeur ni champ dtype affecté. Un smoke visuel manuel réalisé par l'architecte après la publication de la GitHub Release de M121 a révélé une régression UX directement causée par l'ajout de la section `Advanced settings` (section 7) : sur la résolution/fenêtre réelle utilisée par l'architecte, la hauteur totale de `TrainingPage` dépassait désormais celle d'une fenêtre normale, rendant le bas de la page (dont la zone « Résultats des entraînements » et les deux boutons d'action sous elle) physiquement inatteignable — capture d'écran à l'appui.

**Cause exacte** : `TrainingPage.__init__()` construisait tout son contenu directement dans `layout = QVBoxLayout(self)`, sans aucun `QScrollArea` — symptôme déjà rencontré et déjà résolu une première fois pour `SettingsPage` (mini-correctif hors périmètre Mission 115).

**Correction appliquée** : réplique exacte du même pattern déjà en place dans `SettingsPage` (`outer_layout` à marges nulles → `QScrollArea` avec `setWidgetResizable(True)` → `content_widget` → `layout = QVBoxLayout(content_widget)`, tout le contenu existant continuant à peupler `layout` sans aucun changement) — aucune section réorganisée, aucun onglet introduit, aucune logique de sauvegarde modifiée, aucune police/espacement réduit, aucune fonction masquée.

**Fichiers concernés** : `src/ui/pages/training_page.py` (restructuration du layout racine uniquement) et `tests/integration/test_training_roundtrip.py` (nouvelle classe `TrainingPageScrollableContentTest`, 5 tests : présence/unicité du `QScrollArea`, atteignabilité réelle de `jobs_list`/des boutons d'action depuis le contenu défilable, preuve réelle de dépassement de viewport sur fenêtre réduite avec bas de page atteignable par scroll, recalcul correct de la hauteur requise à l'ouverture/fermeture d'`Advanced settings`, non-régression du contrat « pliage ne marque jamais dirty » sous fenêtre réduite).

**Résultats** : tests ciblés 5/5, `test_training_roundtrip.py` complet 222/222, suites connexes (`test_onetrainer_config.py` + `test_settings_page.py`) 133/133, suite complète **2449/2449** (2444 + 5 nets nouveaux), 0 failure/error, `git diff --check` propre.

**Commit correctif séparé** `c5c6850dacb058b387afc2d4915ca12066da3362` (`Fix Training page vertical scrolling`), sur `main` après le commit fonctionnel M121 — **le tag `v0.2-mission121` et la Release déjà publiée restent attachés exclusivement au commit fonctionnel original `d07c063b73ca6d7b6d4da7453855579d59578c60`, jamais déplacés ni retagués.**

## 13. Autorisation

Mission autorisée par l'architecte après micro-audit dédié du contrat dtype/optimizer/mémoire réel d'OneTrainer (variante A — Precision/Memory uniquement, `optimizer` explicitement différé). Décisions architecturales actées explicitement pour cette mission : (1) `unet_weight_dtype`/`transformer_weight_dtype` restent deux champs distincts, jamais fusionnés dans la persistance ; (2) validation de compatibilité architecture/champ appliquée au niveau `build_training_config()` (Domain/translation), la protection UI n'étant qu'une couche supplémentaire, jamais la seule ; (3) le vocabulaire proposé par l'UI reste volontairement restreint aux dtypes non quantifiés pour les trois architectures, y compris Flux, un preset officiel utilisant une valeur quantifiée n'étant pas retenu comme preuve de compatibilité avec la Quadro P4000/Pascal/sm_61 ; (4) `_STRUCTURED_CONFIG_KEYS` protège les clés nichées elles-mêmes (`unet`/`transformer`/`text_encoder`/`text_encoder_2`/`vae`) plutôt que d'introduire un mécanisme de fusion `extra_overrides` scopé par sous-objet, non justifié par un besoin réel actuel. Le correctif post-release de scroll (section 12) a été autorisé séparément, comme un correctif distinct du commit/tag fonctionnel M121.
