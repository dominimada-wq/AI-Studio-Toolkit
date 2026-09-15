# Mission 124 — Training Advanced Configuration: Phase 2 (Text Encoder Training & Layer Filter)

> **MISSION IMPLÉMENTÉE, VALIDÉE, SMOKE RÉEL RÉUSSI.** Contrat figé avant tout code, validé explicitement par l'architecte (y compris les 4 points nécessitant confirmation en section 4.2/2.D/2.B/PROJECT_CONTEXT.md), implémentée exactement selon ce document, validée par la suite complète (2525/2525) et par un smoke réel SDXL de bout en bout sur la Quadro P4000 8 Go réelle (section 9), résultats explicitement validés par l'architecte. Commit(s), tag et Release : voir rapport de clôture.

## 1. Contexte

Trois missions précédentes (120, 121, 122) ont posé et étendu `OneTrainerSettings`, une structure Domain typée nichée dans `Training.onetrainer_settings`, permettant de configurer directement depuis Toolkit des réglages OneTrainer réels (scheduler, dtypes, optimizer) sans jamais ouvrir l'interface OneTrainer. Un audit dédié post-Mission 123 (« Training Advanced Configuration audit », lecture seule) a comparé le comportement actuel de Toolkit aux presets LoRA officiels réellement installés (`J:\Programmes\Onetrainer\training_presets\#sd 1.5 LoRA.json`, `#sdxl 1.0 LoRA.json`, `#flux LoRA.json`) et a identifié deux divergences réelles :

1. **`text_encoder.train`/`text_encoder_2.train`** : Toolkit ne les écrit jamais, alors que les presets officiels SDXL et FLUX les mettent explicitement à `false` — divergence potentiellement coûteuse en mémoire sur le GPU cible documenté du projet (Quadro P4000, 8 Go).
2. **`layer_filter_preset`** : un audit plus poussé a démontré que ce champ n'a **aucun effet** sur le chemin d'exécution headless que Toolkit utilise réellement (`scripts/train_remote.py`) — seul le champ `layer_filter` (chaîne de motifs) compte réellement.

Un correctif indépendant, pré-M124, a par ailleurs déjà corrigé un bug de fiabilité de `TrainingPage.start_training()` (`_config_stale` supprimé, Prepare désormais systématique avant `create_job()` — commit `64833ce377626024c84bba10287af16a38419e34`). Ce correctif garantit que tout nouveau champ M124 modifié juste avant Start atteindra bien la configuration réellement préparée.

## 2. Audit final pré-rédaction (preuves)

### 2.A — Domain Training actuel (confirmé inchangé depuis Mission 122)

`src/domain/onetrainer_settings.py` — `OneTrainerSettings` :

| Champ existant | Type | Sentinel « non configuré » | Validé par architecture ? |
|---|---|---|---|
| `learning_rate_scheduler` | `str` | `""` | Non (accepté pour toutes) |
| `train_dtype` | `str` | `""` | Non (global, toutes architectures) |
| `unet_weight_dtype` | `str` | `""` | Oui — SD15/SDXL uniquement |
| `transformer_weight_dtype` | `str` | `""` | Oui — FLUX uniquement |
| `text_encoder_weight_dtype` | `str` | `""` | Oui — toutes (SD15/SDXL/FLUX) |
| `text_encoder_2_weight_dtype` | `str` | `""` | Oui — SDXL/FLUX (interdit SD15) |
| `vae_weight_dtype` | `str` | `""` | Oui — toutes |
| `optimizer_settings` | `OneTrainerOptimizerSettings` (nichée) | — | — |
| `extra_overrides` | `dict` | `{}` | — |

`to_dict()`/`from_dict()` : symétriques, round-trip complet, `from_dict()` défensif (`data.get(key, default)` pour les scalaires, `isinstance(x, dict)` pour les objets nichés). Validation par architecture centralisée exclusivement dans `src/engines/onetrainer_config.py::build_training_config()` — jamais dans le Domain ni dans l'UI seule. Valeurs par défaut historiques : toute Training créée avant Mission 124 charge ces nouveaux champs à leur sentinel via `from_dict()`'s propre `data.get(key, default)`, sans migration, sans changement de comportement.

**Emplacement retenu pour les 3 nouveaux champs** : directement sur `OneTrainerSettings`, au même niveau que les champs `*_weight_dtype` existants (jamais sur `Training` lui-même — ce sont des réglages OneTrainer-shaped, pas des concepts Toolkit génériques comme `lora_rank`/`architecture`).

### 2.B — Traduction OneTrainer : point de fusion critique confirmé

`build_training_config()` (`src/engines/onetrainer_config.py:373-402`) construit aujourd'hui chaque composant nichée par **assignation directe**, jamais par fusion :

```python
for field_name, value in dtype_fields.items():
    if value:
        component_key = _DTYPE_FIELD_TO_COMPONENT_KEY[field_name]
        config[component_key] = {"weight_dtype": value}   # <-- assignation, pas update()
```

**Confirmé exactement comme signalé par l'architecte** : ajouter `text_encoder_train` via une boucle séparée qui ferait `config["text_encoder"] = {"train": value}` **écraserait silencieusement** le `{"weight_dtype": ...}` déjà construit par la boucle dtype si les deux sont configurés pour le même Training — perte de données silencieuse, jamais détectée par les tests actuels (aucun test existant ne configure dtype+train simultanément, puisque train n'existe pas encore).

**Mécanisme de fusion retenu pour M124** : construire un dictionnaire intermédiaire `component_configs: dict[str, dict]` accumulant tous les sous-champs (`weight_dtype` et/ou `train`) par clé de composant AVANT toute assignation dans `config`, puis assigner chaque composant une seule fois :

```python
component_configs: dict = {}

for field_name, value in dtype_fields.items():
    if value:
        component_key = _DTYPE_FIELD_TO_COMPONENT_KEY[field_name]
        component_configs.setdefault(component_key, {})["weight_dtype"] = value

for field_name, value in train_fields.items():
    if value is not None:
        component_key = _TRAIN_FIELD_TO_COMPONENT_KEY[field_name]
        component_configs.setdefault(component_key, {})["train"] = value

for component_key, component_dict in component_configs.items():
    config[component_key] = component_dict
```

Ceci remplace la boucle dtype existante (refactor nécessaire, pas seulement additif) — non-régression prouvée par les tests G/H de la section 8.

### 2.C — Sémantique de `train`, réauditée dans l'installation réelle

Reconfirmé à l'identique de l'audit précédent, aucune divergence trouvée :

| | Défaut moteur (`TrainModelPartConfig.default_values()`, `TrainConfig.py:281`) | Preset LoRA officiel SD1.5 | Preset LoRA officiel SDXL | Preset LoRA officiel FLUX |
|---|---|---|---|---|
| `text_encoder.train` | `True` | absent → `True` hérité | `false` explicite | `false` explicite |
| `text_encoder_2.train` | `True` | n/a (pas de second TE) | `false` explicite | `false` explicite |

Distinction confirmée et à préserver dans toute documentation/UI future :
1. **Défaut moteur** : `True` inconditionnellement.
2. **Choix des presets officiels** : SDXL/FLUX désactivent explicitement les deux TE ; SD1.5 n'y touche pas.
3. **Recommandation Toolkit** : aucune — M124 n'impose aucun défaut différent du moteur (voir section 9, hors périmètre : pas de presets Recommended/Memory Efficient).
4. **Optimisation mémoire** : réelle et démontrée dans le code (`text_encoder_1_on_train_device = config.train_text_encoder_or_embedding() or not config.latent_caching`, `StableDiffusionXLLoRASetup.py:138-145` et équivalent Flux) — avec `latent_caching=True` (défaut moteur) et `train=False`, le Text Encoder est physiquement déchargé du device d'entraînement. Aucune mesure VRAM réelle effectuée à ce stade (voir section 11).

### 2.D — Architectures : mécanisme de validation réutilisé

Confirmé : `_DTYPE_FIELDS_BY_ARCHITECTURE` (`onetrainer_config.py:160-178`) définit déjà, par architecture, l'ensemble des composants valides — `text_encoder_weight_dtype` autorisé pour les 3, `text_encoder_2_weight_dtype` interdit pour SD15. Le mécanisme (`incompatible_fields = sorted(f for f, v in fields.items() if v and f not in allowed)` → `OneTrainerConfigError`) est directement réutilisable pour les champs `train`.

**Décision** : ne pas renommer/réutiliser `_DTYPE_FIELDS_BY_ARCHITECTURE` lui-même (risque de casser des tests existants qui l'énumèrent par nom), mais ajouter une **constante jumelle** `_TRAIN_FIELDS_BY_ARCHITECTURE` avec la même forme (`{"SD15": frozenset({"text_encoder_train"}), "SDXL": frozenset({"text_encoder_train", "text_encoder_2_train"}), "FLUX": frozenset({"text_encoder_train", "text_encoder_2_train"})}`) et le même algorithme de validation, exactement comme `_OPTIMIZER_STRUCTURED_SUBKEYS` existe déjà à côté de `_STRUCTURED_CONFIG_KEYS` sans être une réécriture de ce dernier. Ce n'est pas un second *système* de validation — c'est la même fonction de validation, appliquée à une seconde table de données, comme le fait déjà `optimizer_extra_overrides` vis-à-vis d'`extra_overrides`.

### 2.E — Layer filter : réaudit final confirmé décisif

`layer_filter_preset` (`TrainConfig.py:1136`, défaut `"full"`) n'est lu **nulle part** dans le chemin réel d'entraînement (`*LoRASetup.py`), uniquement dans le code Tkinter (`modules/util/ui/components.py::preset_set_layer_choice()`, `modules/ui/TrainingTab.py`). Le champ réellement consommé est `layer_filter` (chaîne, `ModuleFilter.create()` → `config.layer_filter.split(",")`) + `layer_filter_regex` (bool). `scripts/train_remote.py` (le script headless exact que Toolkit invoque) ne fait que `TrainConfig.default_values().from_dict(json.load(f))` — aucune résolution de `layer_filter_preset`, confirmé absolument inerte dans ce chemin.

**Résolution du mapping "attn-mlp"** (`BaseStableDiffusionSetup.py:40-42`, `BaseStableDiffusionXLSetup.py`, `BaseFluxSetup.py:41`) :

```python
LAYER_PRESETS = {"attn-mlp": ["attentions"], "attn-only": ["attn"], "full": []}   # SD1.5/SDXL
LAYER_PRESETS = {"attn-mlp": ["attn", "ff.net"], ...}                             # FLUX
```

résolu via `",".join(patterns)` (`components.py:311`) → `layer_filter="attentions"` (SD1.5/SDXL) ou `layer_filter="attn,ff.net"` (FLUX), toujours avec `layer_filter_regex=False` pour ce preset.

**Vérification sémantique du libellé "Attention + MLP uniquement"** (demandée explicitement par l'architecte) : `ModuleFilter` fait un matching par **sous-chaîne sur le chemin complet du module** (`modules/util/ModuleFilter.py`, confirmé par ses propres tests intégrés : `"lora.unet.down_blocks.2.attentions.0.transformer_blocks.0.ff.net.0.proj"` contient bien la sous-chaîne `"attentions"`). Dans un UNet diffusers, chaque bloc `attentions.N` contient un `Transformer2DModel` dont les `transformer_blocks` regroupent à la fois l'auto-attention, l'attention croisée **et** la couche feed-forward (MLP, `ff.net...`) comme sous-modules du même sous-arbre. Le filtre `"attentions"` inclut donc réellement attention **et** MLP, et exclut les resnets/convolutions/embeddings temporels qui vivent hors de ce sous-arbre. **Conclusion : le libellé « Attention + MLP uniquement » n'est pas trompeur — il est techniquement exact pour SD1.5/SDXL comme pour FLUX.** Aucun changement de libellé nécessaire par rapport à la proposition de l'architecte.

### 2.F — Cas FLUX : confirmé, aucune contre-indication technique trouvée

Le preset LoRA officiel FLUX ne configure ni `layer_filter_preset` ni `layer_filter` (transformer entraîné intégralement). `ATTN_MLP` pour FLUX reste donc une capacité **proposée par Toolkit**, jamais une reproduction d'une recommandation officielle OneTrainer — à documenter explicitement dans l'UI/les tests, jamais présenté comme « recommandé par OneTrainer ». Aucune raison technique trouvée de l'exclure : le mécanisme `LAYER_PRESETS`/`ModuleFilter` fonctionne identiquement pour les trois architectures.

### 2.G — Collision `extra_overrides` : tranchée

`layer_filter`/`layer_filter_regex` ne figurent aujourd'hui dans **aucune** des deux listes de protection (`_PROTECTED_CONFIG_KEYS`, `_STRUCTURED_CONFIG_KEYS`) — un `project.json` édité à la main pourrait actuellement les placer librement dans `extra_overrides`.

**Décision, alignée sur le précédent établi par Missions 120-122** : dès que `lora_layer_filter` devient un champ structuré réel, `"layer_filter"` et `"layer_filter_regex"` **doivent** être ajoutés à `_STRUCTURED_CONFIG_KEYS` — exactement le même traitement que `train_dtype`/`unet`/`transformer`/`text_encoder`/`text_encoder_2`/`vae`/`optimizer` ont déjà reçu à chaque fois qu'un champ structuré équivalent a été introduit (principe déjà écrit dans le code : « a future mission that promotes another field to a structured parameter must add its OneTrainer key here in the same change »). Ne pas le faire créerait exactement la double-source-de-vérité que ce mécanisme existe pour empêcher. Aucune nouvelle clé n'est ajoutée à `_PROTECTED_CONFIG_KEYS` (ces clés ne sont jamais calculées/écrites en dernier par `TrainingManager`, contrairement à `workspace_dir`/`concepts`/etc.).

## 3. Objectif de M124

Permettre à l'utilisateur de configurer, directement depuis `TrainingPage` et sans jamais ouvrir OneTrainer :
- l'entraînement (ou le gel) indépendant de chaque Text Encoder d'un Training LoRA (SD1.5/SDXL/FLUX) ;
- une restriction optionnelle des couches LoRA entraînées à « Attention + MLP uniquement », plutôt que l'entraînement complet historique.

Aucun changement du comportement historique pour un Training qui ne configure aucun de ces champs.

## 4. Décision architecturale

### 4.1 — Domain : `OneTrainerSettings` (extension)

```python
# "" jamais réutilisé ici — Optional[bool]/None est une déviation
# volontaire du patron str="" (voir section 6), car un booléen n'a pas
# d'équivalent naturel à la chaîne vide. None = non configuré, jamais
# une des deux valeurs réelles True/False.
text_encoder_train: Optional[bool] = None
text_encoder_2_train: Optional[bool] = None

# "" = non configuré, jamais l'un des discriminants réels ("ATTN_MLP").
# Volontairement une valeur fonctionnelle Toolkit ("ATTN_MLP"), jamais
# la chaîne OneTrainer résolue ("attentions"/"attn,ff.net") — le Domain
# exprime l'intention, la traduction provider (section 4.3) résout la
# valeur réelle par architecture.
lora_layer_filter: str = ""
```

`to_dict()`/`from_dict()` étendus symétriquement. `from_dict()` : `data.get("text_encoder_train")` (retourne déjà `None` si absent — aucune coercition supplémentaire nécessaire, contrairement aux champs `str` qui utilisent `data.get(key, "")` pour se prémunir d'un `None` JSON explicite ; un `null` JSON explicite et une clé absente doivent tous deux résoudre à `None` ici, ce qui est déjà le comportement naturel de `dict.get`). `lora_layer_filter` : `data.get("lora_layer_filter", "")`, identique au patron des autres discriminants (`optimizer`, `learning_rate_scheduler`).

### 4.2 — `TrainingManager.update()` : point de vigilance sentinel (nouveau, à valider explicitement)

**Problème identifié par cet audit, non anticipé dans le contrat initial de l'architecte** : `TrainingManager.update()` (`training_manager.py:337-357`) utilise déjà `Optional[X] = None` pour **tous** ses paramètres, avec la convention documentée « a field left as None is untouched ». Pour les champs `str` existants, ceci ne pose aucune ambiguïté : `None` (au niveau de l'appel) = « ne pas toucher », tandis que `""` (au niveau de la valeur Domain) = « explicitement non configuré » — deux valeurs distinctes, aucune collision.

Pour `text_encoder_train`/`text_encoder_2_train`, la valeur Domain « non configuré » est elle-même `None` — **identique** au sentinel « ne pas toucher » de `update()`. Conséquence concrète : si l'UI veut explicitement repasser un Text Encoder de `True`/`False` à « Non configuré » et appelle `update(text_encoder_train=None)`, `update()` interpréterait cela comme « ne rien changer », et la valeur précédente resterait silencieusement en place — un vrai bug, jamais rencontré jusqu'ici car aucun champ booléen n'existait.

**Recommandation** (nouveau motif, à valider explicitement par l'architecte — aucun précédent dans le code actuel) : introduire un sentinel dédié « non fourni à cet appel », distinct de `None`, uniquement pour ces deux paramètres de `update()` :

```python
_UNSET = object()  # module-level, training_manager.py

def update(
    self,
    ...,
    text_encoder_train: Optional[bool] = _UNSET,
    text_encoder_2_train: Optional[bool] = _UNSET,
    ...,
):
    ...
    if text_encoder_train is not _UNSET:
        # applique la valeur, y compris None (reset explicite vers "non configuré")
        ...
```

`save_training_parameters()` continue d'appeler `update()` avec **tous** les champs à chaque sauvegarde (patron déjà en place, jamais un appel partiel depuis l'UI réelle) — ce nouveau sentinel ne change donc rien pour l'UI elle-même, il protège uniquement l'API `update()` pour tout appelant (tests inclus) qui voudrait explicitement réinitialiser ces deux champs. `lora_layer_filter` (type `str`, sentinel `""`) ne pose aucun problème de cette nature et garde `Optional[str] = None` classique.

### 4.3 — Traduction OneTrainer (`src/engines/onetrainer_config.py`)

- Nouveaux paramètres de `build_training_config()` : `text_encoder_train: Optional[bool] = None`, `text_encoder_2_train: Optional[bool] = None`, `lora_layer_filter: str = ""`.
- Nouvelle constante `_TRAIN_FIELD_TO_COMPONENT_KEY = {"text_encoder_train": "text_encoder", "text_encoder_2_train": "text_encoder_2"}`.
- Nouvelle constante `_TRAIN_FIELDS_BY_ARCHITECTURE` (section 2.D), validée par le même algorithme que `_DTYPE_FIELDS_BY_ARCHITECTURE`, jamais dupliqué en un second système.
- Nouvelle constante centralisée, côté provider (jamais dans `TrainingPage`) :
  ```python
  _LORA_LAYER_FILTER_TRANSLATION = {
      "SD15": {"layer_filter": "attentions", "layer_filter_regex": False},
      "SDXL": {"layer_filter": "attentions", "layer_filter_regex": False},
      "FLUX": {"layer_filter": "attn,ff.net", "layer_filter_regex": False},
  }
  ```
  utilisée uniquement pour la valeur fonctionnelle `"ATTN_MLP"` — `lora_layer_filter == ""` n'ajoute ni `layer_filter` ni `layer_filter_regex` au dict retourné (comportement historique).
- Fusion des composants `text_encoder`/`text_encoder_2` avec les dtypes existants via le mécanisme décrit en 2.B (refactor de la boucle dtype existante en accumulation par composant avant assignation).
- `_STRUCTURED_CONFIG_KEYS` étendu avec `"layer_filter"` et `"layer_filter_regex"` (décision 2.G). Aucune clé ajoutée à `_PROTECTED_CONFIG_KEYS`.
- `TrainingManager.prepare_onetrainer_config()` : trois nouveaux arguments forwardés verbatim depuis `training.onetrainer_settings`, même discipline que les Missions 120-122.

### 4.4 — UI (`TrainingPage`)

**Text Encoders** : deux nouvelles `QComboBox` tri-état, à côté des combos dtype existants (`text_encoder_weight_dtype_combo`, `text_encoder_2_weight_dtype_combo`), mêmes conventions de style/langue que le reste de la page :

| Libellé UI | Valeur Domain |
|---|---|
| Non configuré | `None` |
| Entraîné | `True` |
| Gelé | `False` |

Visibilité de Text Encoder 2 : **réutilise exactement** `_apply_architecture_to_dtype_fields()`'s `text_encoder_2_applies = architecture != TRAINING_ARCHITECTURE_SD15` déjà calculé (`training_page.py:1085-1091`) — aucune seconde logique d'architecture, la nouvelle combo est simplement ajoutée à la même section `setVisible(text_encoder_2_applies)`/reset-si-incompatible déjà écrite pour son dtype jumeau.

**Layer Filter** : une nouvelle `QComboBox` discriminant, valable pour les 3 architectures (aucune restriction de visibilité) :

| Libellé UI | Valeur Domain |
|---|---|
| Non configuré | `""` |
| Attention + MLP uniquement | `"ATTN_MLP"` |

Aucune chaîne interne OneTrainer (`attentions`, `attn,ff.net`) n'apparaît dans `TrainingPage` — la traduction reste exclusivement dans l'adapter (section 4.3).

`save_training_parameters()` étendu avec les 3 nouveaux `currentData()`. `_load_training_parameters()` étendu symétriquement (mêmes `findData()`/fallback index 0 que les combos existants).

## 5. Compatibilité historique

- Un `project.json` antérieur à M124 ne contient aucune des 3 nouvelles clés → `from_dict()` résout `text_encoder_train=None`, `text_encoder_2_train=None`, `lora_layer_filter=""` → `build_training_config()` n'ajoute ni `"train"` dans les composants TE ni `"layer_filter"`/`"layer_filter_regex"` → configuration OneTrainer générée strictement identique à celle produite avant cette mission, prouvé par un test de non-régression byte-à-byte (même patron que Missions 121/122).
- Round-trip `None`/`True`/`False` et `""`/`"ATTN_MLP"` testé explicitement (section 8, tests A/C).
- Aucune migration implicite, aucun changement de defaults pour un Training existant.

## 6. Écart de convention documenté

`Optional[bool] = None` pour `text_encoder_train`/`text_encoder_2_train` est une **déviation volontaire** du patron `str = ""` déjà utilisé par `learning_rate_scheduler`/tous les champs `*_weight_dtype`/`optimizer` — un booléen n'a pas d'équivalent naturel à la chaîne vide, et `None` reste le sentinel Python le plus direct pour « non configuré » sur un type booléen tri-état. Cette déviation est délibérée, documentée dans le docstring du champ Domain lui-même, et ne doit pas être généralisée par analogie à un futur champ qui aurait un sentinel `str`/`int` naturel disponible.

## 7. Fichiers concernés

- `src/domain/onetrainer_settings.py` — 3 nouveaux champs + `to_dict()`/`from_dict()`.
- `src/engines/onetrainer_config.py` — nouveaux paramètres, `_TRAIN_FIELD_TO_COMPONENT_KEY`, `_TRAIN_FIELDS_BY_ARCHITECTURE`, `_LORA_LAYER_FILTER_TRANSLATION`, refactor du mécanisme de fusion par composant, extension de `_STRUCTURED_CONFIG_KEYS`.
- `src/managers/training_manager.py` — `update()` (sentinel `_UNSET` pour les 2 champs bool, forward `lora_layer_filter`), `prepare_onetrainer_config()` (forward des 3 nouveaux champs).
- `src/ui/pages/training_page.py` — 3 nouvelles combos, extension de `_apply_architecture_to_dtype_fields()` pour la visibilité TE2, `save_training_parameters()`/`_load_training_parameters()` étendus.
- `tests/integration/test_onetrainer_config.py`, `tests/integration/test_training_roundtrip.py` — voir section 8.
- `docs/missions/MISSION_124.md` (ce document).

## 8. Tests

**A. Defaults Domain** — nouveau Training : `text_encoder_train is None`, `text_encoder_2_train is None`, `lora_layer_filter == ""`.
**B. Compatibilité `project.json` ancien** — absence des 3 champs → chargement réussi, valeurs sentinel, config générée identique à avant M124 (byte-à-byte).
**C. Round-trip** — `None`/`True`/`False` et `""`/`"ATTN_MLP"` conservés exactement à travers `to_dict()`/`from_dict()`.
**D. SD1.5** — `text_encoder_train` accepté (`True`/`False`) ; `text_encoder_2_train` configuré → `OneTrainerConfigError` ; `lora_layer_filter="ATTN_MLP"` → `layer_filter="attentions"`, `layer_filter_regex=False`.
**E. SDXL** — `text_encoder_train`/`text_encoder_2_train` indépendants, les 9 combinaisons `None`/`True`/`False` × `None`/`True`/`False` testées ; layer filter → `"attentions"`.
**F. FLUX** — mêmes combinaisons TE1/TE2 ; layer filter → `"attn,ff.net"` ; test explicite documentant que ceci est une capacité Toolkit, pas une reproduction du preset officiel FLUX (assertion sur un commentaire/docstring, pas seulement le comportement).
**G. Fusion objets imbriqués** — configurer simultanément `text_encoder_weight_dtype` ET `text_encoder_train` pour le même Training → un seul `config["text_encoder"]` contenant `weight_dtype` **et** `train`. Même test pour `text_encoder_2`. Ce test aurait échoué avec l'implémentation naïve (assignation directe) décrite en 2.B — verrouille explicitement le mécanisme de fusion.
**H. Sentinel** — `None` → aucune clé `"train"` écrite dans le composant ; `""` sur `lora_layer_filter` → ni `"layer_filter"` ni `"layer_filter_regex"` ajoutés.
**I. Validation architecture** — `text_encoder_2_train` configuré pour SD15 → `OneTrainerConfigError`, message nommant le champ fautif (même style que les erreurs dtype existantes).
**J. UI** — chargement/sauvegarde des 3 états pour les 2 TE ; changement d'architecture SD15↔SDXL↔FLUX → visibilité/reset TE2 corrects (réutilisant `_apply_architecture_to_dtype_fields()`) ; chargement/sauvegarde Layer Filter.
**K. `extra_overrides`** — un `project.json` plaçant `"layer_filter"` dans `extra_overrides` après extension de `_STRUCTURED_CONFIG_KEYS` → `OneTrainerConfigError` (collision structurée), même comportement que `"train_dtype"`/`"optimizer"` aujourd'hui.
**L. `update()` sentinel** — `update(text_encoder_train=None)` appelé explicitement réinitialise bien le champ à `None` (jamais interprété comme « ne pas toucher ») ; un appel `update()` sans ce paramètre du tout laisse la valeur existante intacte. Verrouille explicitement la distinction `_UNSET` vs `None` décrite en 4.2.
**M. Intégration Start/Prepare** — un nouveau champ M124 modifié juste avant Start (sans clic Prepare séparé) apparaît bien dans la configuration réellement préparée par `create_job()`, bénéficiant directement du correctif pré-M124 (`64833ce`) sans dupliquer sa propre batterie de tests.

## 9. Smoke réel — exécuté, résultats validés par l'architecte

Exécuté sur la Quadro P4000 8 Go réelle, contre l'installation OneTrainer réelle (`J:\Programmes\Onetrainer`), via un script ad hoc (`TrainingManager`/`TrainingJobRunner` réels, sans UI). Le script vivait exclusivement dans le scratchpad de session, jamais dans le dépôt (mêmes conventions que tous les smokes précédents, Missions 097-122) — contenant des chemins absolus propres à cette machine (checkpoint, image source), il n'a aucune vocation à être conservé comme outil réutilisable et n'a jamais été ajouté au projet. Aucune modification de l'environnement (Python/PyTorch/CUDA/drivers/OneTrainer/dépendances/checkpoint).

**Configuration commune aux deux runs** : checkpoint SDXL réel `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors` (7 105 348 188 octets, déjà référencé par `ApplicationSettings.comfyui_checkpoint_name`), architecture SDXL, résolution 1024, 1 image réelle, 1 epoch/1 step, batch_size 1 (délibérément minimal, pas le 4 du preset officiel), lora_rank 16, lora_alpha 1.0, learning_rate 0.0003, dtypes `unet=FLOAT_16`/`text_encoder=FLOAT_16`/`text_encoder_2=FLOAT_16`/`vae=FLOAT_32` (identiques au preset LoRA officiel SDXL), optimizer/scheduler non configurés (défauts moteur ADAMW/CONSTANT), latent caching au défaut moteur (activé, jamais touché), `lora_layer_filter` non configuré dans les deux runs GPU. Seule variable expérimentale : `text_encoder_train`/`text_encoder_2_train`.

### A. Validation fonctionnelle

| | Run A (`text_encoder_train=None`, `text_encoder_2_train=None`) | Run B (`text_encoder_train=False`, `text_encoder_2_train=False`) |
|---|---|---|
| Config générée | `"text_encoder": {"weight_dtype": "FLOAT_16"}` (aucune clé `train`) | `"text_encoder": {"weight_dtype": "FLOAT_16", "train": false}` — un seul objet fusionné, confirmant le mécanisme de fusion (section 2.B/4.3) avec des données réelles |
| Résultat | `succeeded`, aucun OOM | `succeeded`, aucun OOM |
| Checkpoint/concept | Chargés et acceptés par OneTrainer réel | Chargés et acceptés par OneTrainer réel |
| Step réel | 1 step atteint, `loss=0.0963` | 1 step atteint, `loss=0.0963` (valeur quasi identique attendue : delta LoRA proche de zéro à l'initialisation) |

Les deux runs confirment que les valeurs M124 (absence de `train` comme présence explicite `train=false`, fusionné avec le dtype) sont réellement acceptées par OneTrainer et permettent d'atteindre un entraînement GPU réel.

### B. Mesure expérimentale VRAM/performance (ce smoke uniquement, jamais une promesse générale)

Mesure par `nvidia-smi`, échantillonnage **1 Hz** — toute valeur de VRAM ci-dessous est un **maximum observé**, jamais un pic exact.

| | Run A | Run B |
|---|---|---|
| Maximum VRAM observé | **8062 MiB** | **8062 MiB** |
| Durée totale | 272,0 s | 118,7 s |
| Durée du step | 118,21 s | 13,12 s |

**Le maximum VRAM observé est identique entre A et B — ceci n'est pas documenté comme une réduction de VRAM apportée par le gel des Text Encoders.** Ce maximum correspond au pic transitoire de chargement du checkpoint/VAE, commun aux deux runs puisque le même checkpoint complet est chargé avant que la différence Text Encoder ne prenne effet.

Le **profil temporel** diffère en revanche nettement, observé directement dans les échantillons horodatés (jamais une extrapolation) : le Run A reste à 8058-8062 MiB en continu pendant la quasi-totalité du step (~90-120 s, utilisation GPU proche de 100 % en continu) ; le Run B ne touche 8062 MiB que 2-3 échantillons puis redescend immédiatement sous 3000 MiB pour le reste du step. Les rapports ~2,3× (durée totale) et ~9× (durée du step) sont des résultats expérimentaux de ce smoke précis, jamais une promesse générale de performance.

**Non généralisable** : ces résultats sont spécifiques à cette Quadro P4000 8 Go, ce checkpoint SDXL, cette résolution (1024), ce batch_size (1) et cette configuration exacte. Ils ne doivent pas être étendus à d'autres GPU 8 Go, d'autres checkpoints, d'autres résolutions, d'autres batch sizes, ni à FLUX (non testé dans ce smoke — voir section 11, hors périmètre). Ils constituent une première donnée utile pour le besoin futur « Hardware-aware Training defaults/presets + Training Preflight » consigné dans `docs/PROJECT_CONTEXT.md`.

### Layer Filter — vérification headless (sans GPU)

`build_training_config(architecture="SDXL", lora_layer_filter="ATTN_MLP")` produit `layer_filter="attentions"`, `layer_filter_regex=False`, et **aucune clé `layer_filter_preset`** — confirmé sur données réelles, cohérent avec les tests automatisés D/E/F.

## 10. Critères de clôture

- Suite complète verte, nombre exact confirmé (2525/2525, aucune régression).
- Tests A à M tous présents et verts.
- `git diff --check` propre, aucun fichier hors périmètre.
- Aucune régression sur `test_onetrainer_config.py`/`test_training_roundtrip.py` existants.
- Smoke réel exécuté sur la Quadro P4000 8 Go réelle — **RÉUSSI**, résultats validés explicitement par l'architecte (section 9).

## 11. Hors périmètre strict de M124

Éditeur JSON générique/`extra_overrides` ; presets Toolkit (Recommended/Memory Efficient/Custom) ; ajustement automatique selon le GPU détecté ; EMA ; échantillonnage avancé pendant l'entraînement ; Backup avancé ; Cloud ; Additional Embeddings ; Dataset Tools/Video Tools/Convert Model Tools/Profiling (outils OneTrainer natifs) ; refonte générale de `TrainingPage` ; nouvelle architecture de provider/abstraction multi-trainer ; toute modification de l'environnement CUDA/PyTorch/OneTrainer installé ; lancement réel d'un entraînement pendant cette mission.

## 12. Autorisation

Contrat validé par l'architecte avant implémentation ; implémentation, tests et smoke réel exécutés conformément à ce document ; résultats du smoke (section 9) explicitement validés par l'architecte. Mission close.
