# Mission 126 — FLUX Training Alignment: Quantized Weight Dtype & Flow-Matching Timestep Settings (Phase 2 de l'item 411)

> **MISSION IMPLÉMENTÉE ET VALIDÉE.** Contrat rédigé et figé avant implémentation, conformément aux 16 décisions d'architecture validées explicitement par l'architecte avant toute rédaction. Implémentée exactement selon ce document. Suite complète **2580/2580**, 0 régression (2525 après M124 + 2 nets M125 = 2527 baseline M126 + 53 nets M126 = 2580 — équation vérifiée directement par exécution de la suite complète aux commits fonctionnels M124/M125 réels, voir section 10). Validation headless FLUX confirmée. Commit(s), tag et Release : voir rapport de clôture.

## 1. Contexte

L'item « Exposition progressive des réglages OneTrainer dans `TrainingPage` — Basic/Advanced/Presets » (`docs/PROJECT_CONTEXT.md`, identifié Mission 101, poursuivi Missions 120-122/124) a été avancé par la Mission 125 (Phase 1) : audit réel de l'installation OneTrainer, production d'une matrice exhaustive des réglages exposés/non exposés, réorganisation Basic/Advanced de `TrainingPage`. Cette matrice (`docs/missions/MISSION_125.md`, section 3.1) a établi un constat chiffré : le preset FLUX LoRA officiel d'OneTrainer configure `transformer.weight_dtype=NFLOAT_4`, `text_encoder_2.weight_dtype=NFLOAT_4`, `timestep_distribution=LOGIT_NORMAL` et `dynamic_timestep_shifting=true` — quatre réglages absents ou non réglables dans Toolkit aujourd'hui. Un LoRA FLUX produit par Toolkit diverge donc mesurablement du preset recommandé par OneTrainer lui-même.

Un micro-audit ciblé, préalable à cette mission, a approfondi ce constat par lecture directe du code source réel d'OneTrainer (`J:\Programmes\Onetrainer`), de ses 3 presets officiels LoRA (SD1.5/SDXL/FLUX) et de l'environnement réel (venv OneTrainer, `nvidia-smi`). Ses résultats, repris intégralement en section 3, ont corrigé et affiné le périmètre initialement envisagé.

Mission 126 est la **Phase 2** de cet item : elle expose les deux écarts FLUX chiffrés par cet audit (quantification 4 bits, réglages de bruitage flow-matching), **sans** presets, **sans** hardware-awareness, **sans** `QuantizationConfig`, **sans** gradient checkpointing.

## 2. Décisions d'architecture validées par l'architecte (avant rédaction)

1. **NFLOAT_4** : ajouté à `_DTYPE_UI_CHOICES`, exposé via le mécanisme dtype générique existant, **sans restriction artificielle par architecture/composant** — le support technique OneTrainer est uniforme (confirmé section 3.1). Les futurs presets décideront quand le recommander ; M126 expose seulement la capacité.
2. **`QuantizationConfig`** (`layer_filter_preset`/`svd_dtype`/`svd_rank`/etc.) : strictement hors périmètre, jamais fusionné architecturalement avec `weight_dtype=NFLOAT_4` — deux mécanismes distincts.
3. **Flow-matching** : les trois champs `timestep_distribution`/`dynamic_timestep_shifting`/`timestep_shift` sont traités **ensemble** — `timestep_shift` n'est pas différé, il forme un couple fonctionnel indissociable avec `dynamic_timestep_shifting` (voir section 3.2).
4. **Sentinels Domain** : `timestep_distribution: str = ""`, `dynamic_timestep_shifting: Optional[bool] = None`, `timestep_shift: Optional[float] = None`. `_UNSET` utilisé dans `TrainingManager.update()` uniquement pour ces deux champs `Optional`, jamais généralisé au reste de la méthode.
5. **UI — Timestep distribution** : vocabulaire restreint à Non configuré / `UNIFORM` / `LOGIT_NORMAL`. Le Domain et le traducteur restent conçus pour permettre une extension future propre (SIGMOID/HEAVY_TAIL/COS_MAP/INVERTED_PARABOLA/BETA) — cette restriction est un choix de vocabulaire UI, jamais présentée comme une limite technique d'OneTrainer.
6. **UI — Dynamic timestep shifting** : combo tri-état, même pattern que Mission 124 (Non configuré/Activé/Désactivé → None/True/False).
7. **UI — Timestep shift** : case à cocher « Configurer le timestep shift » + `QDoubleSpinBox`, jamais de valeur sentinelle flottante artificielle. Non cochée → Domain `None` ; cochée → Domain = valeur du spinbox, y compris `1.0` explicite.
8. **Interaction dynamic/static** : le contrôle `timestep_shift` est visuellement désactivé quand `dynamic_timestep_shifting=True` (OneTrainer ignore alors la valeur statique), **sans jamais effacer la valeur Domain** — elle redevient disponible si l'utilisateur repasse `dynamic_timestep_shifting` à `False`/non configuré. La traduction OneTrainer reste indépendante par champ : si `timestep_shift` est explicitement configuré, la clé est écrite dans le JSON même quand `dynamic_timestep_shifting=True` l'ignore à l'exécution — jamais de mutation silencieuse d'un champ Domain en fonction d'un autre.
9. **Section UI** : « Flow-matching (FLUX) » dans Advanced, visible uniquement en architecture FLUX. Aucun changement UI pour SD1.5/SDXL sur ces trois champs. `NFLOAT_4` reste disponible dans les sélecteurs dtype génériques (non filtré par architecture).
10. **`extra_overrides`** : `timestep_distribution`/`dynamic_timestep_shifting`/`timestep_shift` rejoignent `_STRUCTURED_CONFIG_KEYS` dès leur introduction. `NFLOAT_4` est une valeur d'un champ déjà structuré (`transformer_weight_dtype`/`text_encoder_2_weight_dtype`/etc.) — aucune nouvelle protection nécessaire pour cette valeur.
11. **Gradient checkpointing** : hors périmètre, confirmé orthogonal par l'audit (section 3.3) — différé à une mission ultérieure sur les réglages Training manquants.
12. **Smoke** : pas de smoke GPU FLUX réel — validation headless/configurationnelle uniquement. Raison documentée en section 3.4 : blocage réel sur l'authentification/le cache local du repo gated `black-forest-labs/FLUX.1-dev`, résolution explicitement hors périmètre M126. Aucun téléchargement, aucune installation, aucune modification d'environnement.
13. **Tests** : liste détaillée en section 12, reprise du contrat validé par l'architecte.
14. **Hardware-aware/Preflight** : rappelé uniquement comme perspective (section 13) — `NFLOAT_4` devient un futur levier mémoire structuré ; les réglages flow-matching sont des leviers de comportement/qualité, jamais classés comme leviers mémoire. Rien n'est implémenté de ce besoin dans M126.
15. **Hors périmètre explicite** : voir section 14 — liste exhaustive validée par l'architecte.
16. **Documentation** : rédiger ce document, le faire examiner et autoriser par l'architecte avant tout début d'implémentation (contrairement à Mission 125, cette mission ne bascule pas automatiquement vers l'implémentation à la fin de la rédaction).

## 3. Preuves de l'audit réel (micro-audit préalable)

### 3.1 NFLOAT_4 — support technique / preset officiel / recommandation Toolkit

Confirmé par lecture directe de `quantization_util.py` (`replace_linear_with_quantized_layers()`, backend `bitsandbytes` — `bnb.functional.quantize_4bit`/`matmul_4bit`, type `nf4`, via la classe `LinearNf4`) : `quantize_layers()` est appelée de façon **strictement uniforme** par les trois architectures —

- `BaseStableDiffusionSetup.py` (SD1.5) : `text_encoder`, `vae`, `unet` ;
- `BaseStableDiffusionXLSetup.py` (SDXL) : `text_encoder_1`, `text_encoder_2`, `vae`, `unet` ;
- `BaseFluxSetup.py` (FLUX) : `text_encoder_1`, `text_encoder_2`, `vae`, `transformer`.

L'UI officielle OneTrainer (`ModelTab.py::__create_dtype_options()`) propose déjà `NFLOAT_4` sur **tous** les combos `weight_dtype`, quel que soit le composant — confirmant que le support technique n'est jamais restreint par composant ou par architecture dans OneTrainer lui-même.

Valeurs exactes des 3 presets officiels (relevées directement dans les fichiers JSON réels) :

| Architecture × composant | Support technique OneTrainer | Preset officiel | Recommandation Toolkit M126 |
|---|---|---|---|
| SD1.5 — UNet | ✅ | `FLOAT_16` | Exposer, ne pas suggérer |
| SD1.5 — Text Encoder | ✅ | `FLOAT_16` | Exposer, ne pas suggérer |
| SDXL — UNet | ✅ | `FLOAT_16` | Exposer, ne pas suggérer |
| SDXL — Text Encoder 1 | ✅ | `FLOAT_16` | Exposer, ne pas suggérer |
| SDXL — Text Encoder 2 | ✅ | `FLOAT_16` | Exposer, ne pas suggérer |
| FLUX — Transformer | ✅ | **`NFLOAT_4`** | Exposer — aligné sur le preset officiel |
| FLUX — Text Encoder 1 (CLIP-L) | ✅ | `BFLOAT_16` (**pas** NFLOAT_4) | Exposer, ne pas suggérer |
| FLUX — Text Encoder 2 (T5-XXL) | ✅ | **`NFLOAT_4`** | Exposer — aligné sur le preset officiel |
| FLUX — VAE | ✅ | `FLOAT_32` | Exposer, ne pas suggérer — quantifier le VAE dégraderait la fidélité de décodage |

`train_dtype` du preset FLUX : `BFLOAT_16` (déjà réglable aujourd'hui via le mécanisme Mission 121 — aucun changement nécessaire sur ce point précis).

`NFLOAT_4` quantifie réellement le **stockage et la représentation en mémoire pendant l'entraînement** (pas seulement le disque) : au chargement, chaque `nn.Linear` du composant ciblé est remplacé par un `LinearNf4`, quantifié une fois (`block_size=64`), puis déquantifié à la volée à chaque forward (`bnb.matmul_4bit`) en `compute_dtype` (bf16/fp16). Les poids quantifiés ne sont jamais entraînables (`requires_grad_(False)` explicite dans `LinearNf4`) — cohérent avec l'usage LoRA (backbone gelé, adaptateur non quantifié). Réduction de stockage ~4× pour les couches `nn.Linear` du composant ciblé — propriété structurelle du format, pas une estimation. `bitsandbytes` (version 0.49.1) est déjà installé dans le venv réel d'OneTrainer — aucune nouvelle dépendance.

### 3.2 Flow-matching — relation `dynamic_timestep_shifting` / `timestep_shift`

Champs réels dans `TrainConfig.py` (déclaration ligne 439-450, défauts ligne 1029-1035) :

| Champ | Type | Défaut moteur | Preset FLUX |
|---|---|---|---|
| `timestep_distribution` | enum `TimestepDistribution` (7 valeurs) | `UNIFORM` | `LOGIT_NORMAL` |
| `dynamic_timestep_shifting` | bool | `False` | `True` |
| `timestep_shift` | float | `1.0` | absent (reste au défaut, non pertinent car ignoré) |

Ces trois champs sont **plats** (top-level `TrainConfig`), jamais nichés sous un objet composant — traduction directe, sans table de translation comme celle du Layer Filter (Mission 124).

Consommation réelle confirmée (`BaseFluxSetup.py`, `ModelSetupNoiseMixin.py`) :

```python
shift = model.calculate_timestep_shift(height, width)   # calculé automatiquement depuis la résolution latente réelle du batch — jamais un réglage utilisateur
timestep = self._get_timestep_discrete(
    ...,
    shift = shift if config.dynamic_timestep_shifting else config.timestep_shift,
)
```

**Relation exacte** : ce ne sont pas deux réglages indépendants. `timestep_shift` est la valeur statique utilisée quand `dynamic_timestep_shifting=False` (défaut). Quand `dynamic_timestep_shifting=True`, `timestep_shift` est **totalement ignoré à l'exécution**, remplacé par une valeur calculée automatiquement à partir de la résolution du batch. Les deux valeurs alimentent ensuite la même formule finale (`ModelSetupNoiseMixin.py`, dans `_get_timestep_discrete()`) qui déforme le timestep échantillonné — appliquée à **toutes** les distributions continues, y compris `LOGIT_NORMAL` (celle du preset officiel). `model.calculate_timestep_shift()` est une méthode interne à chaque modèle flow-matching (FluxModel, QwenModel, etc.) — automatique, jamais exposée comme réglage.

`noising_bias`/`noising_weight` (utilisés par la formule `LOGIT_NORMAL` : `bias=noising_bias`, `scale=noising_weight+1.0`) restent à leurs défauts (`0.0`/`0.0`) dans le preset officiel — un logit-normal(0,1) standard. Ces deux champs restent donc légitimement hors périmètre : leur valeur par défaut est déjà exactement ce que le preset utilise.

Ces trois champs (`timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift`) ne sont réellement consommés, dans ce fork OneTrainer, que par les architectures flow-matching (Flux/Flux2/Qwen/ZImage/Ernie/SD3/Sana/HiDream/Chroma) — jamais par `BaseStableDiffusionSetup.py`/`BaseStableDiffusionXLSetup.py` (diffusion classique, aucune référence à ces champs). Confirme la restriction stricte à FLUX pour les trois architectures actuellement supportées par Toolkit.

### 3.3 Gradient checkpointing — orthogonalité confirmée

`gradient_checkpointing: GradientCheckpointingMethod` (enum `OFF`/`ON`/`CPU_OFFLOADED`), défaut moteur `ON`. Aucun des 3 presets officiels (SD1.5/SDXL/FLUX) ne le surcharge — les trois tournent donc déjà avec gradient checkpointing actif par défaut aujourd'hui, y compris le smoke réel de Mission 124. Aucune interaction directe trouvée avec `NFLOAT_4` ou les réglages flow-matching dans le code (mécanismes indépendants : recompute d'activations au backward vs quantification du stockage des poids). Confirme la décision de différer.

### 3.4 Smoke FLUX réel — faisabilité

Checkpoints déjà présents localement (aucun téléchargement effectué) : `flux1-dev.safetensors` (23,8 Go, transformer bf16), `flux1-dev-fp8.safetensors` (17,2 Go, variante fp8 format ComfyUI — **pas** le format NF4 d'OneTrainer, non directement réutilisable), `clip_l.safetensors` (246 Mo), `t5xxl_fp16.safetensors` (9,8 Go), `ae.safetensors` (335 Mo, VAE).

Blocage concret identifié dans `FluxModelLoader.py` : le loader attend un dossier diffusers HF complet ou un pipeline single-file, et charge dans les deux cas le tokenizer T5 (et potentiellement les text encoders) depuis `black-forest-labs/FLUX.1-dev` — repo **gated** sur HuggingFace. Aucun cache local de ce repo n'existe (`C:\Users\dlero\.cache\huggingface\hub` ne contient que Blip/CLIP/SDXL). `ModelNames` n'a pas de paramètre dédié pour des fichiers text encoder locaux séparés (contrairement à `transformer_model`/`vae_model`).

Compatibilité Pascal/sm_61 (Quadro P4000, confirmé via `nvidia-smi`/`torch.cuda.get_device_capability` : compute capability `(6, 1)`) : `bitsandbytes` 0.49.1 installé dans le venv OneTrainer réel. Le seul seuil de compute capability trouvé dans son code (`cuda_specs.py::has_imma`, CC≥7.5) gouverne uniquement les tensor cores **int8** — son propre message de diagnostic recommande explicitement la quantification 4 bits comme alternative quand ce seuil n'est pas atteint, suggérant que NF4 (dequant vers bf16/fp16 + matmul standard) est plausible sur Pascal. Aucun seuil bloquant explicite trouvé pour NF4 dans le code statique — **mais ceci reste à mesurer expérimentalement, non déductible de la seule lecture du code**.

Conclusion : validation **headless/configurationnelle uniquement** pour M126 — cohérent avec la méthode déjà employée par Mission 124 pour son propre Layer Filter FLUX (traduction vérifiée sans run GPU). Un futur smoke réel FLUX nécessite une décision explicite séparée de l'architecte (authentification HF gated), hors périmètre de cette mission.

## 4. Problème traité

Un LoRA FLUX produit par Toolkit aujourd'hui diverge mesurablement du preset FLUX officiel d'OneTrainer sur deux axes : absence de `NFLOAT_4` dans les choix de dtype (empêchant la quantification 4 bits du transformer/Text Encoder 2, le principal levier mémoire qui rend FLUX entraînable sur un GPU contraint), et absence totale des réglages de bruitage flow-matching (`timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift`).

## 5. Contrat Domain

Aucun changement de type pour les champs dtype existants (`unet_weight_dtype`, `transformer_weight_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype` restent des `str`, acceptant déjà n'importe quelle valeur — `NFLOAT_4` n'exige aucune modification du Domain, seulement de la liste de choix UI, section 8).

Trois nouveaux champs dans `OneTrainerSettings` (`src/domain/onetrainer_settings.py`), documentés avec le même luxe de détail que les champs Mission 120-124 existants :

```python
# Mission 126: flow-matching timestep/noise settings — FLUX-only
# (validated the same way as text_encoder_2_weight_dtype: rejected for
# SD1.5/SDXL by build_training_config(), never here).
#
# "" means "not configured" — never one of TimestepDistribution's own
# real enum values. UI vocabulary deliberately restricted to
# "" / "UNIFORM" / "LOGIT_NORMAL" (MISSION_126.md section 3.2) — the
# Domain field itself stays a plain str, capable of carrying any of the
# 7 real enum values (e.g. from a hand-edited project.json), same
# defensive tolerance as every other str sentinel field in this class.
timestep_distribution: str = ""

# Deliberately Optional[bool], never a str="" sentinel — same reasoning
# as text_encoder_train (Mission 124 section 6): a boolean has no
# natural empty-string equivalent. None is omitted from the built
# config entirely, letting OneTrainer's own real default
# (dynamic_timestep_shifting=False) apply exactly as it did before this
# mission.
dynamic_timestep_shifting: Optional[bool] = None

# Deliberately Optional[float], never a numeric sentinel (0.0 would
# collide with a value the user could conceivably want to set, and is
# mathematically degenerate in OneTrainer's own shift formula) — same
# reasoning as GenerationMetadata.lora_strength. None is omitted from
# the built config entirely, letting OneTrainer's own real default
# (timestep_shift=1.0) apply exactly as it did before this mission.
# Explicitly independent from dynamic_timestep_shifting at the Domain
# level (MISSION_126.md section 3.2/2.8): configuring one never
# resets or mutates the other.
timestep_shift: Optional[float] = None
```

`to_dict()`/`from_dict()` étendus selon le patron exact déjà utilisé pour `text_encoder_train`/`text_encoder_2_train` (garde de type explicite `isinstance(x, bool)`/`isinstance(x, (int, float))` sur `from_dict()`, jamais une vérité simple, pour dégrader une valeur mal typée vers le sentinel sûr).

## 6. Contrat Manager

`TrainingManager.update()` gagne deux nouveaux paramètres `Optional`, tous deux nécessitant le sentinel privé `_UNSET` déjà existant (`_UNSET = object()`, Mission 124) — **réutilisé tel quel, jamais un second sentinel** :

```python
dynamic_timestep_shifting: Optional[bool] = _UNSET,
timestep_shift: Optional[float] = _UNSET,
```

`timestep_distribution` reste un `str` avec sentinel `""` — pas besoin de `_UNSET` (même raisonnement que `learning_rate_scheduler`/`train_dtype`/`lora_layer_filter` : `""` distingue déjà nativement "non fourni à cet appel" de "remis à non configuré", puisque `update()` ne réinitialise jamais un champ `str` à `""` sauf appel explicite avec `""`).

Conformément à la décision validée (point 4) : `_UNSET` n'est **pas** généralisé au reste de `TrainingManager` pendant M126 — utilisé exclusivement pour `dynamic_timestep_shifting`/`timestep_shift`, exactement le même périmètre que Mission 124 pour `text_encoder_train`/`text_encoder_2_train`.

## 7. Contrat traduction OneTrainer (`src/engines/onetrainer_config.py`)

Nouvelle table de validation architecturale, jumelle de `_DTYPE_FIELDS_BY_ARCHITECTURE`/`_TRAIN_FIELDS_BY_ARCHITECTURE` — **jamais fusionnée avec elles** (même précédent que Mission 124 section 2.D) :

```python
_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE = {
    "SD15": frozenset(),
    "SDXL": frozenset(),
    "FLUX": frozenset({
        "timestep_distribution",
        "dynamic_timestep_shifting",
        "timestep_shift",
    }),
}
```

Même algorithme de validation que les deux tables existantes (champ configuré + architecture n'autorisant pas ce champ → `OneTrainerConfigError` nommant l'architecture et les champs en cause) — toujours actif quel que soit l'appelant (UI, `project.json` édité à la main), jamais une restriction seulement côté UI.

Traduction en clés plates (jamais nichées sous un objet composant, contrairement aux champs dtype/train) :

```python
if timestep_distribution:
    config["timestep_distribution"] = timestep_distribution
if dynamic_timestep_shifting is not None:
    config["dynamic_timestep_shifting"] = dynamic_timestep_shifting
if timestep_shift is not None:
    config["timestep_shift"] = timestep_shift
```

**Traduction strictement indépendante par champ** (décision validée point 8) : `timestep_shift`, une fois configuré, est écrit dans le JSON que `dynamic_timestep_shifting` soit `True`, `False` ou non configuré — jamais une condition croisée entre les deux champs au niveau de la traduction. La sémantique « OneTrainer ignore `timestep_shift` à l'exécution quand `dynamic_timestep_shifting=True` » est un fait du moteur (section 3.2), jamais reproduit comme une suppression de champ côté Toolkit.

`NFLOAT_4` ne nécessite aucun changement dans ce fichier : les champs dtype existants transportent déjà n'importe quelle chaîne vers `component_configs[...]["weight_dtype"]` sans validation de valeur (confirmé, seule la validation de **nom de champ** par architecture existe aujourd'hui — jamais de validation de **valeur** de dtype dans le moteur).

## 8. Contrat UI (`src/ui/pages/training_page.py`)

- **`_DTYPE_UI_CHOICES`** étendu : `("FLOAT_16", "FLOAT_32", "BFLOAT_16", "TFLOAT_32", "NFLOAT_4")` — un seul ajout, partagé par tous les combos dtype existants (UNet/Transformer/Text Encoder/Text Encoder 2/VAE), sans nouvelle restriction par architecture ou composant (décision validée point 1).
- **`timestep_distribution`** : nouveau `QComboBox`, vocabulaire `[("Non configuré", ""), ("UNIFORM", "UNIFORM"), ("LOGIT_NORMAL", "LOGIT_NORMAL")]` — même mécanisme `findData()`/`currentData()` que tous les autres combos dtype de cette page.
- **`dynamic_timestep_shifting`** : nouveau `QComboBox` tri-état, réutilisant tel quel le pattern de `_build_text_encoder_train_combo()` — libellés à confirmer avec la convention exacte de la page (`"Non configuré"`/`"Activé"`/`"Désactivé"`, mapping `None`/`True`/`False`).
- **`timestep_shift`** : une `QCheckBox` (« Configurer le timestep shift ») couplée à un `QDoubleSpinBox`, désactivé (`setEnabled(False)`) tant que la case n'est pas cochée. Case décochée → Domain `None` ; case cochée → Domain = valeur courante du spinbox, y compris `1.0`. Bornes/décimales/step du spinbox à déterminer à partir des contraintes réelles de `TrainConfig.py` si elles existent (aucune contrainte min/max explicite trouvée sur `timestep_shift: float` dans `TrainConfig.py` au moment de cet audit — à reconfirmer explicitement en tout début d'implémentation avant de figer des bornes arbitraires ; le défaut moteur `1.0` sert de point de repère mais n'est pas une borne).
- **Interaction dynamic/static** (décision validée point 8) : quand `dynamic_timestep_shifting` passe à `True` (Activé), la case à cocher et le spinbox de `timestep_shift` sont désactivés visuellement (`setEnabled(False)`), **jamais décochés ni réinitialisés** — la valeur Domain déjà saisie reste intacte et redevient modifiable dès que `dynamic_timestep_shifting` repasse à `False`/Non configuré.
- **Section « Flow-matching (FLUX) »** : nouvelle sous-section dans `advanced_settings_form`, visible uniquement quand `architecture == TRAINING_ARCHITECTURE_FLUX` — même mécanisme de visibilité que `text_encoder_2_weight_dtype`/`text_encoder_2_train` (`_apply_architecture_to_dtype_fields()` ou son équivalent étendu). Aucun changement UI pour SD1.5/SDXL.
- **Changement d'architecture** : en sortant de FLUX (`reset_incompatible=True`, changement réellement piloté par l'utilisateur), les trois champs flow-matching sont explicitement réinitialisés à leur sentinel (`""`/`None`/`None`) — même principe que `text_encoder_2_weight_dtype` lors d'un passage vers SD1.5 (« jamais laissé silencieusement de côté, jamais ressurgissant plus tard dans la même session si l'architecture est reswitchée »). Sur un rechargement programmatique (`reset_incompatible=False`, ouverture d'un Training existant), ces champs ne sont jamais réinitialisés.
- **Dirty-state** : les 5 nouveaux widgets (dtype combo étendu ne compte pas comme nouveau widget ; les 2 nouveaux combos + la checkbox + le spinbox) suivent le même branchement `_mark_dirty()` que tout autre widget de cette page.

## 9. Compatibilité architectures

| Architecture | `NFLOAT_4` sur les dtypes existants | Section Flow-matching (FLUX) |
|---|---|---|
| SD1.5 | Disponible (aucune restriction), jamais suggéré | Invisible, aucun champ réglable — toute valeur configurée serait rejetée par `_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE` |
| SDXL | Disponible (aucune restriction), jamais suggéré | Invisible, même rejet |
| FLUX | Disponible, aligné sur le preset officiel pour Transformer/Text Encoder 2 | Visible et réglable |

## 10. Compatibilité historique

Un `project.json` existant, écrit avant M126, ne contient aucune des 3 nouvelles clés — `from_dict()` restaure les sentinels par défaut (`""`/`None`/`None`) exactement comme pour toute mission précédente ayant ajouté un champ à `OneTrainerSettings`. Un Training existant utilisant déjà un dtype parmi les 4 valeurs actuelles n'est jamais affecté par l'ajout de `NFLOAT_4` à la liste de choix — comportement strictement additif.

## 11. `extra_overrides`

`timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift` rejoignent `_STRUCTURED_CONFIG_KEYS` dans le même commit que leur introduction comme champs structurés — même discipline que chaque mission précédente ayant structuré un nouveau réglage (Missions 120/121/124). `NFLOAT_4` en tant que valeur ne nécessite aucune nouvelle entrée : `transformer`/`text_encoder_2`/etc. sont déjà protégés depuis Mission 121.

## 12. Stratégie de tests

Reprise exacte du contrat validé par l'architecte :

- **A. Defaults Domain** : `timestep_distribution == ""`, `dynamic_timestep_shifting is None`, `timestep_shift is None`.
- **B. Ancien `project.json`** : absence des nouveaux champs acceptée, sentinels restaurés.
- **C. Round-trip Domain** : `""`/`UNIFORM`/`LOGIT_NORMAL` ; `None`/`True`/`False` ; `None`/float quelconque ; `1.0` explicite préservé (distinct de `None`).
- **D. Manager** : `_UNSET` distingue argument absent (valeur Domain inchangée) et reset explicite vers `None`.
- **E. Traduction** : champs absents du JSON quand non configurés ; valeurs exactes quand configurés.
- **F. `timestep_shift`** : `1.0` explicite réellement écrit dans le JSON (distinct de l'absence de clé) ; un autre float (ex. `1.15`) réellement écrit.
- **G. Interaction dynamic/static** : `dynamic_timestep_shifting=True` + `timestep_shift` configuré → les deux valeurs Domain préservées ; rechargement identique ; le contrôle UI statique se désactive seul (jamais décoché/réinitialisé) ; aucune suppression silencieuse de `timestep_shift` dans le JSON généré.
- **H. Architecture** : section Flow-matching visible en FLUX, invisible en SD1.5/SDXL ; toute valeur configurée pour ces 3 champs hors FLUX rejetée par `build_training_config()` avec le même style d'erreur que les tables existantes.
- **I. `extra_overrides`** : impossible d'écraser les trois nouvelles clés structurées via `extra_overrides`.
- **J. `NFLOAT_4`** : présent dans les combos dtype existants (toutes architectures/composants) ; round-trip correct ; traduction correcte ; aucune régression sur `FLOAT_16`/`FLOAT_32`/`BFLOAT_16`/`TFLOAT_32` ; absence de toute restriction Toolkit artificielle contredisant le support OneTrainer audité (section 3.1).
- **K. Dirty-state UI** : toute modification des nouveaux widgets marque correctement le Training comme modifié.
- **L. Changement d'architecture** : sortie de FLUX réinitialise les 3 champs flow-matching (`reset_incompatible=True`) ; rechargement programmatique d'un Training existant ne les réinitialise jamais (`reset_incompatible=False`) — même contrat que `text_encoder_2_weight_dtype`.
- **M. Validation headless FLUX** : construire une configuration représentative —

  ```python
  train_dtype = "BFLOAT_16"
  transformer_weight_dtype = "NFLOAT_4"
  text_encoder_weight_dtype = "BFLOAT_16"
  text_encoder_2_weight_dtype = "NFLOAT_4"
  vae_weight_dtype = "FLOAT_32"
  timestep_distribution = "LOGIT_NORMAL"
  dynamic_timestep_shifting = True
  ```

  et vérifier que le JSON produit par `build_training_config()` contient exactement ces valeurs aux emplacements attendus (`transformer.weight_dtype`, `text_encoder.weight_dtype`, `text_encoder_2.weight_dtype`, `vae.weight_dtype`, `train_dtype`, `timestep_distribution`, `dynamic_timestep_shifting`), reproduisant fidèlement le preset FLUX officiel sur ces axes. Variante avec `timestep_shift` explicitement configuré (ex. `1.0`) pour vérifier sa présence correcte dans le JSON même avec `dynamic_timestep_shifting=True`. Aucun lancement GPU.

### Résultats réels

**Baseline vérifiée par exécution directe** (jamais supposée) : suite complète exécutée dans deux worktrees Git détachés, aux commits fonctionnels réels —

```
2525 tests  (2af32b9 — commit fonctionnel Mission 124, exécution directe confirmée)
+  2 tests  (Mission 125 : test_gradient_accumulation_and_scheduler_are_reclassified_into_advanced,
             test_reclassified_fields_keep_their_value_across_a_fold_unfold_cycle — confirmés
             par diff exact entre 2af32b9 et e70f773)
= 2527 tests (e70f773 — commit fonctionnel Mission 125, exécution directe confirmée, baseline M126)
+ 53 tests  (Mission 126 — 21 dans test_onetrainer_config.py, 13 dans TrainingManagerUpdateTest,
             19 dans TrainingPageOnetrainerParametersTest ; 2 tests préexistants étendus par pure
             addition, jamais affaiblis, ne comptent pas dans les 53 nets)
= 2580 tests (suite complète finale, exécutée deux fois, résultat identique)
```

**Tests ciblés** : `test_onetrainer_config.py` 98/98 ; `test_training_roundtrip.py` 278/278.
**Suite complète** : **2580/2580, OK**, 0 régression.
**Validation headless FLUX** : `test_headless_flux_representative_configuration` et sa variante avec `timestep_shift` explicite — JSON complet vérifié, fidèle au preset FLUX officiel sur les axes couverts par cette mission.
**Vérification `timestep_shift` UI** (section 1 du micro-audit de clôture) : confirmé par lecture directe de `modules/ui/TrainingTab.py` qu'OneTrainer expose ce champ via un simple champ texte libre (`components.entry(..., required=True)`), sans borne min/max/decimals/step — les bornes du `QDoubleSpinBox` Toolkit (`-1000.0`/`1000.0`/3 décimales/pas `0.1`) sont donc explicitement documentées dans le code comme des choix techniques Qt, jamais une limite OneTrainer, FLUX ou une plage d'entraînement recommandée.

## 13. Perspective Hardware-aware / Preflight (rappel, non implémenté)

`NFLOAT_4` constitue désormais un futur levier mémoire structuré que les presets ou un futur Training Preflight pourront proposer d'activer face à un risque OOM détecté (voir le besoin futur Hardware-aware Training/Preflight, `docs/PROJECT_CONTEXT.md`). Les réglages flow-matching (`timestep_distribution`/`dynamic_timestep_shifting`/`timestep_shift`) sont des réglages de comportement/qualité du modèle — ils ne doivent **jamais** être classés comme leviers mémoire dans une future architecture hardware-aware. Rien de ce besoin n'est implémenté par M126.

## 14. Hors périmètre strict de M126

- `QuantizationConfig` complet (`layer_filter_preset`/`svd_dtype`/`svd_rank`/etc.).
- Gradient checkpointing.
- EMA.
- Bruit/noise avancé au-delà de ce qui est strictement nécessaire au couple flow-matching ci-dessus (`noising_bias`/`noising_weight`/`min_noising_strength`/`max_noising_strength`/`offset_noise_weight` restent non exposés).
- Entraînement masqué.
- Variantes PEFT (LoHa/LoKr/OFT/DoRA).
- Presets Recommended/Memory Efficient/Custom.
- Hardware-aware Training.
- Training Preflight.
- Authentification/téléchargement HuggingFace (repo gated `black-forest-labs/FLUX.1-dev`).
- Smoke GPU FLUX réel.
- Toute modification de l'environnement OneTrainer/CUDA/PyTorch/bitsandbytes.

## 15. Critères de clôture

- [x] `OneTrainerSettings` étendu avec les 3 sentinels validés, `to_dict()`/`from_dict()` symétriques et défensifs.
- [x] `TrainingManager.update()` étendu avec `_UNSET` pour `dynamic_timestep_shifting`/`timestep_shift` uniquement.
- [x] `build_training_config()` : nouvelle table `_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE`, traduction indépendante des 3 champs, `NFLOAT_4` fonctionnel sans changement de validation de valeur.
- [x] `_STRUCTURED_CONFIG_KEYS` étendu aux 3 nouvelles clés.
- [x] `TrainingPage` : `_DTYPE_UI_CHOICES` étendu, section « Flow-matching (FLUX) » visible uniquement en FLUX, interaction dynamic/static conforme à la section 8, réinitialisation conforme au changement d'architecture.
- [x] Tests A à M (section 12) tous verts.
- [x] Suite complète verte, régression zéro confirmée (2580/2580).
- [x] Validation headless FLUX (test M) confirmant une configuration fidèle au preset officiel sur les axes couverts.
- [ ] Documentation (`PROJECT_CONTEXT.md`, `CHANGELOG.md`) mise à jour selon le workflow habituel — différée après confirmation de publication de la Release, même convention que M120-M125 (item 411 restera explicitement non clos après cette mission).

## 16. Autorisation

Mission implémentée, auditée et validée par l'architecte. Contrat exécuté exactement selon ce document — aucune divergence fonctionnelle. Audit final de clôture (baseline des tests, diff fonctionnel complet, bornes UI, interaction dynamic/static, changement d'architecture) réalisé et documenté ci-dessus. Mission close.
