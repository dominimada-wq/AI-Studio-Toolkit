# Mission 127 — Training Advanced Configuration: Gradient Checkpointing Exposure

> **MISSION IMPLÉMENTÉE, TESTÉE ET SMOKE VALIDÉ — clôture (commit/tag/Release) en attente de validation finale de l'architecte.** Contrat rédigé avant toute implémentation, à la suite de deux audits préalables validés explicitement par l'architecte : l'audit de couverture Training post-M126 et le micro-audit ciblé sur la sémantique réelle de `gradient_checkpointing`/`CPU_OFFLOADED`. Implémentation conforme à ce contrat, suite complète **2605/2605** (2580 après M126 + 25 nets M127), smoke réel SDXL OFF/ON réussi sur les deux runs — voir résultats en sections 12/13.

## 1. Contexte

L'audit de couverture Training post-Mission 126 (trajectoires possibles) a identifié `gradient_checkpointing` comme le levier mémoire le plus déterminant actuellement invisible dans AI Studio Toolkit : absent de tout champ structuré, absent de l'UI, non réglable sans éditer `extra_overrides` à la main — alors qu'il conditionne directement la capacité à entraîner SDXL/FLUX sur un GPU contraint (Quadro P4000, 8 Go). Cet audit a recommandé Mission 127 comme trajectoire prioritaire, avant tout Preset Toolkit ou Hardware-aware Training.

Un micro-audit ciblé, validé par l'architecte, a ensuite tracé exactement la sémantique réelle de ce réglage dans le code OneTrainer installé (`J:\Programmes\Onetrainer`) — révélant une asymétrie architecture-dépendante non documentée jusque-là entre SD1.5/SDXL et FLUX pour la valeur `CPU_OFFLOADED`. Ce micro-audit a également confirmé, sans l'implémenter, un second finding distinct — le gel automatique du Text Encoder après 30 epochs (`stop_training_after`) — conservé ici comme dette explicite pour une mission ultérieure (section 16).

Mission 127 expose `gradient_checkpointing` seul, sans reproduire l'ensemble de la fenêtre « Offloading » d'OneTrainer (`enable_activation_offloading`/`enable_async_offloading`/`layer_offload_fraction` restent hors périmètre, section 15).

## 2. Décisions d'architecture validées par l'architecte (avant rédaction)

1. **Domain** : `gradient_checkpointing_mode: str = ""`, sentinelle `""` = non configuré, jamais transformée en `"ON"` lors de la sérialisation.
2. **Compatibilité historique** : un `project.json` sans cette clé reste strictement inchangé dans le comportement produit — OneTrainer applique son propre défaut moteur (`ON`), exactement comme avant cette mission.
3. **Manager** : pas de `_UNSET` — pattern `Optional[str] = None` déjà utilisé pour `train_dtype`/`learning_rate_scheduler`, jamais généralisé au-delà de ce champ.
4. **Traduction** : clé plate top-level `gradient_checkpointing`, valeurs `"OFF"`/`"ON"`/`"CPU_OFFLOADED"` transmises telles quelles (aucune table de traduction Toolkit → OneTrainer, contrairement à `lora_layer_filter`) ; toute autre valeur structurée lève `OneTrainerConfigError`.
5. **`extra_overrides`** : `gradient_checkpointing` rejoint `_STRUCTURED_CONFIG_KEYS` dès son introduction — décision confirmée en section 9.
6. **UI** : un unique combo générique (Non configuré/OFF/ON/CPU_OFFLOADED) dans la section Advanced existante « Precision / Memory », visible et identique pour les 3 architectures — aucune nouvelle section.
7. **Sémantique UI de `CPU_OFFLOADED`** : jamais présentée comme un gain VRAM universel — le tooltip/documentation doit refléter l'asymétrie réelle prouvée par le code (section 5).
8. **Hors périmètre strict** : `enable_activation_offloading`/`enable_async_offloading`/`layer_offload_fraction`, Text Encoder stop condition, `QuantizationConfig`, EMA, noise/loss avancés, masked training, DoRA/LoKr/OFT, presets Toolkit, Hardware-aware Training, Training Preflight, tout smoke/téléchargement/authentification FLUX (liste complète section 15).
9. **Smoke** : un smoke réel SDXL contrôlé OFF/ON (2 runs, jamais 3) est prévu **après** validation complète des tests, protocole figé en section 13 — aucun smoke FLUX, aucun troisième run `CPU_OFFLOADED` sur SDXL (redondant avec `ON`, prouvé par le micro-audit).
10. **Correction méthodologique actée** : ce document ne doit jamais présenter `gradient_checkpointing=ON` comme la cause démontrée du succès mémoire du smoke SDXL de Mission 124 — seul un fait établi (le réglage était actif) est affirmé, son rôle causal quantitatif reste à mesurer par le smoke de cette mission (section 13).
11. **Documentation** : ce document doit être examiné et autorisé par l'architecte avant tout début d'implémentation — pas de bascule automatique vers le code à la fin de la rédaction (même convention que Mission 126).

## 3. Preuves des deux audits préalables (reprises intégralement)

### 3.1 Traçage réel de `gradient_checkpointing`

- **Déclaration** : `TrainConfig.py:377`, `gradient_checkpointing: GradientCheckpointingMethod`.
- **Défaut moteur** : `TrainConfig.py:972`, `GradientCheckpointingMethod.ON`.
- **Enum réel** (`modules/util/enum/GradientCheckpointingMethod.py`) : `OFF`/`ON`/`CPU_OFFLOADED`, avec `.enabled()` (`True` pour `ON` et `CPU_OFFLOADED`) et `.offload()` (`True` **seulement** pour `CPU_OFFLOADED`).
- **Porte d'entrée unique de consommation**, identique dans les 3 fichiers de setup d'architecture : `if config.gradient_checkpointing.enabled():` (`BaseStableDiffusionSetup.py`, `BaseStableDiffusionXLSetup.py`, `BaseFluxSetup.py`). Si `OFF`, aucun mécanisme de checkpointing n'est installé nulle part — comportement PyTorch/diffusers standard, activations conservées.
- Si `enabled()` (`ON` ou `CPU_OFFLOADED`) : SD1.5/SDXL appellent `model.unet.enable_gradient_checkpointing()` (natif diffusers) + `enable_checkpointing_for_basic_transformer_blocks(model.unet, config, offload_enabled=False)` **avec `offload_enabled` explicitement `False`** + `enable_checkpointing_for_clip_encoder_layers(...)` pour leurs Text Encoders. FLUX appelle `enable_checkpointing_for_flux_transformer(model.transformer, config)` **sans** ce paramètre (donc `True` par défaut) + les mêmes helpers pour ses deux Text Encoders.

### 3.2 Finding critique — asymétrie SD1.5/SDXL vs FLUX pour `CPU_OFFLOADED`

`LayerOffloadConductor.__init__` (`modules/util/LayerOffloadConductor.py:583-585`) :

```python
self.__offload_activations = config.gradient_checkpointing.offload() and config.enable_activation_offloading
self.__offload_layers = config.gradient_checkpointing.offload() and config.layer_offload_fraction > 0
self.__async_transfer = self.__train_device.type == "cuda" and config.enable_async_offloading
```

`enable_activation_offloading` (défaut `True`) et `enable_async_offloading` (défaut `True`) sont déjà vrais par défaut moteur, indépendamment de `gradient_checkpointing` — `CPU_OFFLOADED` (`.offload()`) est la condition qui **rend effectif** ce qui est déjà activé par défaut, jamais une activation implicite d'un nouveau flag. `layer_offload_fraction` (défaut `0.0`) doit en revanche être réglé explicitement `>0` pour produire un quelconque déplacement de couches entières — jamais implicite.

Pour SD1.5/SDXL, `enable_checkpointing_for_basic_transformer_blocks(model.unet, config, offload_enabled=False)` transmet `conductor=None` pour les blocs UNet (`checkpointing_util.py::create_checkpoint()`) — **aucun `LayerOffloadConductor` n'est jamais rattaché à l'UNet de ces deux architectures**, quelle que soit la valeur de `gradient_checkpointing`. Leurs Text Encoders CLIP obtiennent un conducteur (`offload_enabled` par défaut `True`), mais avec `include_from_offload_param_names=[]` (liste vide, commentaire du code : *"No activation offloading for text encoders, because the output might be taken from the middle of the network"*) — aucun tenseur d'activation n'y est donc jamais réellement déplacé, et le déplacement de couches entières reste à `0` par défaut.

**Conclusion prouvée par le code : sur SD1.5/SDXL, avec les valeurs par défaut, `CPU_OFFLOADED` se comporte exactement comme `ON` — aucun gain VRAM.** Seul FLUX bénéficie réellement de `CPU_OFFLOADED` par défaut, via l'offloading d'activations de son transformer (`hidden_states`/`encoder_hidden_states`), jamais via un offloading de couches entières (fraction toujours à `0` par défaut).

### 3.3 UI officielle OneTrainer

`TrainingTab.py:379-388` : combo `options_adv` (3 valeurs de l'enum) avec un bouton d'engrenage ouvrant une fenêtre secondaire dédiée (`OffloadingWindow.py`), plus un champ `layer_offload_fraction` juste en dessous, tooltip *« Only available if checkpointing is set to CPU_OFFLOADED »* (non grisé dynamiquement, seulement documenté). `OffloadingWindow.py` regroupe dans une seule fenêtre `gradient_checkpointing` + `enable_async_offloading` + `enable_activation_offloading` + `layer_offload_fraction` — OneTrainer traite ces 4 champs comme un groupe fonctionnel, jamais comme des réglages dispersés indépendants. Mission 127 expose volontairement un sous-ensemble de ce groupe (un seul combo) — la documentation UI Toolkit doit donc rester factuelle sur cette réduction de périmètre (section 6/10).

### 3.4 Correction méthodologique — smoke M124

`gradient_checkpointing=ON` était actif pendant le smoke SDXL réel de Mission 124 (confirmé par défaut moteur, jamais modifié par le preset officiel ni par Toolkit). Ce mécanisme est connu par le code pour réduire la conservation des activations (recomputation au backward). **Son rôle causal quantitatif dans le succès mémoire de ce run n'a jamais été isolé expérimentalement** (aucune comparaison OFF/ON n'a été effectuée à cette date) — le smoke de la présente mission (section 13) sert précisément à produire cette donnée. Vérification effectuée : cette formulation causale erronée n'a jamais été écrite dans un fichier persistant du dépôt (`PROJECT_CONTEXT.md`, `MISSION_124.md`, `MISSION_126.md`, `CHANGELOG.md` tous vérifiés propres) — aucune correction documentaire n'est donc nécessaire.

## 4. Problème produit

Un utilisateur Toolkit ne peut aujourd'hui ni vérifier ni modifier `gradient_checkpointing` sans ouvrir l'interface OneTrainer ou écrire un `extra_overrides` à la main — alors que ce réglage conditionne directement la capacité à entraîner SDXL/FLUX sur un GPU à VRAM limitée, et qu'il constitue le premier levier mémoire structuré nécessaire à tout futur Preset « Memory Efficient » ou Hardware-aware Training.

## 5. Sémantique OFF/ON/CPU_OFFLOADED et asymétrie SD1.5/SDXL/FLUX

| Valeur | Comportement moteur prouvé par le code |
|---|---|
| `OFF` | Aucun mécanisme de checkpointing installé — activations conservées normalement, comportement PyTorch/diffusers standard. |
| `ON` | Recomputation d'activations standard (checkpointing natif diffusers + wrapper OneTrainer par blocs), aucun offloading, conducteur jamais fonctionnellement actif. |
| `CPU_OFFLOADED` — **FLUX** | Recomputation d'activations (comme `ON`) **+** offloading réel des activations du transformer (`hidden_states`/`encoder_hidden_states`) vers la RAM système, grâce au défaut moteur `enable_activation_offloading=True`. Aucun offloading de couches entières tant que `layer_offload_fraction` reste à `0.0` (défaut). |
| `CPU_OFFLOADED` — **SD1.5/SDXL** | **Strictement identique à `ON`** — aucun offloading d'activation ni de couche, quels que soient les défauts `enable_activation_offloading`/`enable_async_offloading`, car l'UNet n'a structurellement jamais de conducteur d'offloading attaché (`offload_enabled=False` câblé en dur) et les Text Encoders CLIP ont une liste de paramètres offloadables vide. |

Cette asymétrie est un fait de code (`offload_enabled=False` explicite pour l'UNet SD1.5/SDXL), jamais une supposition — elle doit être reflétée fidèlement dans la documentation UI (section 10) sans jamais promettre un gain VRAM universel pour `CPU_OFFLOADED`.

## 6. Contrat Domain

Nouveau champ dans `OneTrainerSettings` (`src/domain/onetrainer_settings.py`), suivant le patron exact des sentinels `str` existants (`train_dtype`, `learning_rate_scheduler`) :

```python
# Mission 127: which of OneTrainer's own GradientCheckpointingMethod
# values applies — "" means "not configured", never one of the real
# enum's own values (OFF/ON/CPU_OFFLOADED), omitted from the built
# config when empty, letting OneTrainer's own real default (ON) apply
# exactly as it did before this mission — the exact historical Toolkit
# behavior (see MISSION_127.md section 3.2 for the confirmed asymmetry:
# CPU_OFFLOADED behaves exactly like ON on SD1.5/SDXL with default
# offloading settings, and only differs for FLUX).
gradient_checkpointing_mode: str = ""
```

`to_dict()`/`from_dict()` étendus selon le patron déjà utilisé pour `train_dtype` (`data.get("gradient_checkpointing_mode", "")`, aucune garde de type spécifique nécessaire — un `str` mal typé dans un `project.json` édité à la main resterait un `str`, comme pour tout autre champ dtype existant). La différence entre `""` et `"ON"` reste observable à tout instant dans le Domain et dans le JSON généré (section 11) — `""` n'est jamais réécrit en `"ON"` lors d'un `to_dict()`/`from_dict()`.

## 7. Contrat Manager

`TrainingManager.update()` gagne un paramètre supplémentaire, **sans** `_UNSET` (décision validée point 3, section 2) :

```python
gradient_checkpointing_mode: Optional[str] = None,
```

Motif identique à `train_dtype`/`learning_rate_scheduler` : `None` signifie « non fourni à cet appel » (valeur Domain inchangée), tandis qu'un appel explicite avec `gradient_checkpointing_mode=""` réinitialise le champ à « non configuré ». `changed` étendu par la clause `(gradient_checkpointing_mode is not None and gradient_checkpointing_mode != onetrainer_settings.gradient_checkpointing_mode)`, `previous`/rollback étendus dans la même position que les autres champs `str`, assignation `if gradient_checkpointing_mode is not None: onetrainer_settings.gradient_checkpointing_mode = gradient_checkpointing_mode`. `build_training_config()` appelé avec `gradient_checkpointing_mode=training.onetrainer_settings.gradient_checkpointing_mode`, même position que `train_dtype` dans l'appel existant.

## 8. Contrat traduction OneTrainer (`src/engines/onetrainer_config.py`)

Ajout d'un paramètre `gradient_checkpointing_mode: str = ""` à `build_training_config()`. Contrairement à `lora_layer_filter` (intention fonctionnelle Toolkit traduite via une table), ce champ transmet **directement** une des 3 valeurs réelles de l'enum OneTrainer — même style que `train_dtype`/les champs `*_weight_dtype`, à une différence près : **ce mission introduit la première validation de valeur** (les champs dtype existants n'en ont aucune, confirmé Mission 126 section 7 — ils acceptent n'importe quelle chaîne). Le mécanisme le plus proche à réutiliser est celui déjà employé pour rejeter une valeur `lora_layer_filter` non reconnue (`_LORA_LAYER_FILTER_TRANSLATION.get(...)  is None → OneTrainerConfigError`) — même style d'erreur, appliqué ici à un ensemble de valeurs autorisées plutôt qu'à une table de traduction :

```python
_GRADIENT_CHECKPOINTING_VALUES = frozenset({"OFF", "ON", "CPU_OFFLOADED"})

...

if gradient_checkpointing_mode:
    if gradient_checkpointing_mode not in _GRADIENT_CHECKPOINTING_VALUES:
        raise OneTrainerConfigError(
            f"Unsupported gradient_checkpointing_mode: {gradient_checkpointing_mode!r} "
            f"(expected one of {sorted(_GRADIENT_CHECKPOINTING_VALUES)} or \"\")"
        )
    config["gradient_checkpointing"] = gradient_checkpointing_mode
```

Cette validation est **indépendante de l'architecture** — aucune table `_..._FIELDS_BY_ARCHITECTURE` n'est nécessaire, puisque `gradient_checkpointing` est un champ générique valide pour les 3 architectures (confirmé par le code : la porte `config.gradient_checkpointing.enabled()` existe identiquement dans les 3 fichiers de setup, section 3.1). `""` (non configuré) n'ajoute aucune clé, laissant le défaut moteur `ON` s'appliquer exactement comme aujourd'hui.

## 9. `extra_overrides`

`"gradient_checkpointing"` rejoint `_STRUCTURED_CONFIG_KEYS` dans le même commit que son introduction comme champ structuré — même discipline que chaque mission précédente ayant structuré un nouveau réglage plat (Missions 120/121/126). Une tentative `extra_overrides={"gradient_checkpointing": "OFF"}` est rejetée par le contrôle générique déjà existant (`structured_hits = sorted(_STRUCTURED_CONFIG_KEYS & extra_overrides.keys())`), sans nouveau mécanisme de validation à écrire pour ce rejet précis.

## 10. Contrat UI (`src/ui/pages/training_page.py`)

Un unique `QComboBox` ajouté dans la section Advanced existante « Precision / Memory » (aucune nouvelle section — juste après ou avant le combo `train_dtype`, position exacte à confirmer en implémentation selon la lisibilité du formulaire), vocabulaire `[("Non configuré", ""), ("OFF", "OFF"), ("ON", "ON"), ("CPU_OFFLOADED", "CPU_OFFLOADED")]`, même mécanisme `findData()`/`currentData()` que les combos dtype existants. Visible et identique pour les 3 architectures (SD1.5/SDXL/FLUX) — aucune logique de visibilité conditionnelle par architecture, contrairement à la section Flow-matching de Mission 126.

**Tooltip/aide UI — obligatoire, jamais optionnel** (décision validée point 7, section 2) : le texte doit rester strictement factuel, sans promettre de gain VRAM chiffré ni universel. Formulation de référence, à adapter au style existant de la page :

> *ON: Standard gradient checkpointing (recomputes activations, reduces VRAM, increases training time).*
> *CPU_OFFLOADED: Adds activation offloading where supported by the OneTrainer architecture. With the current default offloading settings, this provides additional activation offloading for FLUX; SD1.5/SDXL behave like ON unless layer offloading is configured separately (not yet exposed by this Toolkit).*

`_on_training_parameters_changed()` (dirty-state) branché comme tout autre combo de la page. Chargement/sauvegarde suivant le patron exact de `train_dtype` (`_load_training_parameters()`/`save_training_parameters()`).

## 11. Compatibilité historique

Un `project.json` écrit avant Mission 127 ne contient pas `gradient_checkpointing_mode` — `from_dict()` restaure la sentinelle `""` par défaut, exactement comme pour tout champ ajouté par une mission précédente. `prepare_onetrainer_config()`/`build_training_config()` n'écrivent alors aucune clé `gradient_checkpointing` dans le JSON produit — OneTrainer applique son propre défaut moteur (`ON`), strictement identique au comportement produit avant cette mission. Aucun Training existant ne change de comportement du seul fait de cette mission.

## 12. Stratégie de tests (A–Q, reprise intégrale du contrat validé)

- **A. Domain default** : `OneTrainerSettings().gradient_checkpointing_mode == ""`.
- **B. Ancien `project.json`** : champ absent du dict d'entrée → `from_dict()` produit `""`.
- **C. Round-trip Domain** : `""`, `"OFF"`, `"ON"`, `"CPU_OFFLOADED"` tous préservés à l'identique par `to_dict()`/`from_dict()`.
- **D. Manager update** : appel avec une valeur explicite modifie le champ et déclenche `save()` ; `changed=False` si valeur identique (idempotence stricte, convention `CLAUDE.md`).
- **E. Manager prepare forwarding** : `prepare_onetrainer_config()`/`build_training_config()` reçoit bien la valeur courante de `onetrainer_settings.gradient_checkpointing_mode`.
- **F. Traduction `""`** : clé `gradient_checkpointing` absente du JSON produit.
- **G. Traduction `OFF`** : `config["gradient_checkpointing"] == "OFF"`.
- **H. Traduction `ON`** : `config["gradient_checkpointing"] == "ON"`.
- **I. Traduction `CPU_OFFLOADED`** : `config["gradient_checkpointing"] == "CPU_OFFLOADED"`.
- **J. Valeur inconnue** : toute chaîne hors `{"", "OFF", "ON", "CPU_OFFLOADED"}` (ex. `"MAYBE"`) lève `OneTrainerConfigError`.
- **K. `extra_overrides`** : `extra_overrides={"gradient_checkpointing": "OFF"}` rejeté par le contrôle `_STRUCTURED_CONFIG_KEYS` existant.
- **L. UI round-trip** : les 4 états (`Non configuré`/`OFF`/`ON`/`CPU_OFFLOADED`) chargés et sauvegardés correctement par le combo.
- **M. Dirty-state** : modifier le combo marque le Training comme modifié.
- **N. Reload** : fermeture/réouverture (ou changement de Training puis retour) restaure l'état exact du combo.
- **O. Architecture switching** : le combo reste visible et sa valeur reste strictement inchangée en changeant d'architecture entre SD1.5/SDXL/FLUX (contrairement aux champs Flow-matching de Mission 126, ce réglage n'est jamais réinitialisé — il est générique aux 3 architectures).
- **P. Ancien Training** : un Training préexistant avec `gradient_checkpointing_mode` non configuré ne voit aucune différence dans le JSON produit après cette mission (non-régression stricte).
- **Q. Configuration représentative** : construire une configuration combinant `gradient_checkpointing_mode` avec `train_dtype`, un `*_weight_dtype` par composant, `text_encoder_train`, `lora_layer_filter` et (en FLUX) les 3 champs flow-matching de Mission 126 — vérifier que `gradient_checkpointing` cohabite dans le JSON produit sans écraser ni être écrasé par aucun de ces champs.

### Résultats réels

**53 tests A-Q implémentés** (11 dans `test_onetrainer_config.py`, 14 dans `test_training_roundtrip.py` — répartis Manager/Engine/UI). **25 tests nets** (2580 avant M127 → **2605**, exécuté deux fois consécutives, résultat identique). Fichiers ciblés au complet : `test_onetrainer_config.py` **109/109**, `test_training_roundtrip.py` **292/292**. Diff `git diff --numstat` confirmé strictement additif sur les 6 fichiers `src/`/`tests/` (0 suppression), aucune assertion préexistante affaiblie ou supprimée.

## 13. Protocole de smoke réel SDXL (après validation des tests)

**Deux runs seulement, jamais trois.** Un troisième run `CPU_OFFLOADED` sur SDXL est explicitement exclu — le micro-audit démontre déjà, par le code (`offload_enabled=False` sur l'UNet), qu'il serait strictement redondant avec `ON` tant que `layer_offload_fraction` (hors périmètre) reste à `0`.

- **Run A** : `gradient_checkpointing = OFF`.
- **Run B** : `gradient_checkpointing = ON`.
- **Configuration strictement identique par ailleurs** : même checkpoint SDXL, même dataset/image/caption, même résolution, même batch, même accumulation de gradient, même rank/alpha, mêmes dtypes, même état Text Encoder, même optimizer/scheduler, même caching, mêmes epochs/steps, même seed si possible — **seule variable : `gradient_checkpointing`.**
- **Run A ne doit jamais être adapté en cas d'OOM** — un échec OOM du Run A est une donnée expérimentale valide en soi, à rapporter telle quelle, jamais masquée en modifiant un autre paramètre.
- **Aucun run FLUX** — le pipeline FLUX réel reste bloqué par l'absence locale des ressources du dépôt gated `black-forest-labs/FLUX.1-dev` (confirmé Mission 126). Aucun téléchargement, aucune authentification, aucune modification d'environnement pendant cette mission. La compatibilité runtime de `CPU_OFFLOADED` sur la P4000 restera donc **non confirmée** à l'issue de Mission 127 — à tester ultérieurement quand un pipeline FLUX réel sera disponible.
- **Mesures prévues par run** : VRAM avant lancement, maximum VRAM observé pendant chargement/cache, maximum VRAM observé pendant le step, comportement VRAM soutenu, RAM système, durée de step, durée totale, succès/OOM/erreur explicite. Toute mesure issue d'un polling `nvidia-smi` doit être qualifiée **« maximum VRAM observé »**, jamais « peak VRAM exact ».
- **Interprétation stricte** : le smoke isole uniquement OFF vs ON sur cette configuration SDXL précise — les résultats ne doivent jamais être généralisés à tous les GPU 8 Go, à FLUX, à toutes les résolutions/batch sizes, ni à toute autre configuration SDXL.

### Résultats réels

**Configuration commune réelle** : checkpoint `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors` (7 105 348 188 octets, réutilisé de M124), 1 image réelle, résolution 1024, batch 1, accumulation 1, 3 epochs → 3 steps réels, rank 16/alpha 1.0, learning rate 0.0003, dtypes UNet/TE1/TE2=FLOAT_16, VAE=FLOAT_32, Text Encoders 1 et 2 explicitement gelés (identique pour A et B), optimizer/scheduler/train_dtype/latent caching/layer filter/seed = **ENGINE DEFAULT** (non configurés). Diff programmatique des deux `onetrainer_config.json` réels (après neutralisation des seuls chemins par run et de `gradient_checkpointing`) : **identiques**.

**Run A (OFF)** : succès, exit 0, steps 203.37 s / 184.25 s / 154.21 s (moyenne **180.61 s**, médiane **184.25 s**), durée totale processus **690.65 s**. Maximum VRAM observé **8060 MiB**, sustenu en continu entre 8048-8060 MiB pendant la quasi-totalité des 3 steps.

**Run B (ON)** : premier lancement interrompu — voir incident ci-dessous — puis succès au retry strictement identique, exit 0, steps 16.46 s / 19.10 s / 12.49 s (moyenne **16.02 s**, médiane **16.46 s**), durée totale processus **208.88 s**. Maximum VRAM observé **8062 MiB** (un seul échantillon), le reste du temps oscillant entre 6994 et 8048 MiB avec des redescentes régulières (ex. 6994/7252/7632 MiB).

**Maximum VRAM observé quasi identique entre A et B (8060 vs 8062 MiB) — jamais interprété comme une réduction de VRAM apportée par `ON`.** Différence réellement observée : la **durée passée près du plafond VRAM**, très longue pour OFF (~9 min sustenues), brève pour ON — corrélée à un écart de performance marqué (ratio moyenne OFF/moyenne ON = **11.28**, ratio médiane = **11.19**, ratio durée totale processus = **3.31**), mesuré strictement sur cette configuration. Le mécanisme exact (pression VRAM/comportement mémoire GPU sous Windows) reste une **hypothèse non profilée**, jamais confirmée comme la cause du gain de performance.

Losses loguées identiques aux mêmes steps sur les deux runs (`0.0963`/`0.00383`/`0.0857`) — un fait vérifié sur ces deux exécutions précises, jamais interprété comme un déterminisme général (aucun seed explicitement fixé par Toolkit).

**Incident, premier lancement Run B** : warning `CUDA initialization: Unexpected error from cudaGetDeviceCount()` suivi d'une exécution sur CPU (0% GPU, 0 MiB VRAM, un processus enfant consommant fortement la RAM système). Processus arrêté (`taskkill`, aucune modification d'environnement). Un retry strictement identique a immédiatement réussi sur GPU, sans avertissement. Classé **incident transitoire d'initialisation CUDA, cause non déterminée, non reproduit**.

Aucun run `CPU_OFFLOADED`, aucun smoke FLUX, aucune modification d'environnement.

## 14. Critères d'acceptation

- [x] `OneTrainerSettings.gradient_checkpointing_mode` ajouté, sentinelle `""`, `to_dict()`/`from_dict()` symétriques.
- [x] `TrainingManager.update()` étendu sans `_UNSET`, motif `Optional[str] = None` identique à `train_dtype`.
- [x] `build_training_config()` : nouveau paramètre, validation par ensemble de valeurs autorisées (`_GRADIENT_CHECKPOINTING_VALUES`), `OneTrainerConfigError` sur valeur inconnue, clé omise si `""`.
- [x] `_STRUCTURED_CONFIG_KEYS` étendu avec `"gradient_checkpointing"`.
- [x] `TrainingPage` : combo ajouté dans « Precision / Memory », visible pour les 3 architectures, tooltip factuel conforme à la section 10, dirty-state branché.
- [x] Tests A à Q (section 12) tous verts, suite complète verte, régression zéro (2605/2605).
- [x] Smoke SDXL OFF/ON réalisé et documenté (section 13), sans troisième run ni smoke FLUX.
- [ ] Documentation (`PROJECT_CONTEXT.md`, `CHANGELOG.md`) mise à jour selon le workflow habituel, après confirmation de publication de la Release (même convention que M120-M126).

## 15. Hors périmètre strict de M127

- `enable_activation_offloading`, `enable_async_offloading`, `layer_offload_fraction` (déjà vrais/nuls par défaut moteur ; `layer_offload_fraction` est une primitive mémoire distincte méritant son propre audit/contrat, seul levier qui affecterait réellement SD1.5/SDXL).
- Text Encoder stop condition (`stop_training_after`/`stop_training_after_unit`) — voir dette conservée section 16.
- `QuantizationConfig` complet.
- EMA.
- Noise/loss avancés au-delà de ce que Mission 126 a déjà exposé.
- Entraînement masqué.
- Variantes PEFT (DoRA/LoKr/OFT).
- Presets Toolkit (Recommended/Memory Efficient/Custom).
- Hardware-aware Training.
- Training Preflight.
- Téléchargement/authentification HuggingFace (repo gated `black-forest-labs/FLUX.1-dev`).
- Smoke GPU FLUX.
- Toute modification de l'environnement OneTrainer/CUDA/PyTorch.

## 16. Dette conservée — Text Encoder stop condition (ne pas implémenter)

Finding confirmé par le micro-audit précédent, à ne **pas** traiter dans Mission 127 : `text_encoder.stop_training_after=30`/`stop_training_after_unit=EPOCH` (idem `text_encoder_2`) — défaut moteur, jamais surchargé par aucun preset officiel. Avec `train=True`, le Text Encoder est automatiquement gelé (`requires_grad_(False)`) une fois l'epoch 30 atteinte (`(train_progress.epoch + 1) > 30`), sans erreur ni log dédié. Avec `train=False`, cette condition est sans effet (le composant ne s'entraîne jamais de toute façon). Pour désactiver la limite, seul `stop_training_after_unit=TimeUnit.NEVER` fonctionne — **`stop_training_after=0` avec `unit=EPOCH` ne désactive pas la limite, il provoque au contraire un gel immédiat** (`(0+1)>0` est vrai dès l'epoch 0). Ce réglage reste aujourd'hui structurellement inaccessible via `extra_overrides`, puisque `"text_encoder"`/`"text_encoder_2"` sont des clés entières réservées dans `_STRUCTURED_CONFIG_KEYS` (Mission 121), sans échappement plus étroit équivalent à celui de l'optimiseur. **Candidat prioritaire pour la mission suivant Mission 127** — non implémenté ici.

## 17. Perspective Presets / Hardware-aware / Preflight (rappel, non implémenté)

Après Mission 127, `gradient_checkpointing_mode` devient un levier mémoire structuré directement utilisable par de futurs Presets Toolkit (`Recommended`/`Memory Efficient`) et par un futur Training Preflight/Hardware-aware Training — par exemple, forcer `ON` ou (si un jour exposé) `CPU_OFFLOADED`+`layer_offload_fraction` face à un risque OOM détecté. **Aucun de ces systèmes n'est implémenté par Mission 127.** Aucun réglage explicitement configuré par l'utilisateur ne devra jamais être modifié silencieusement par un futur système de ce type — principe déjà établi par les missions précédentes (jamais de migration implicite, `CLAUDE.md`).

## 18. Autorisation

Document rédigé conformément aux deux audits préalables validés par l'architecte (audit de couverture Training post-M126, micro-audit gradient_checkpointing/CPU_OFFLOADED). Aucune contradiction avec le code réel identifiée pendant la rédaction. En attente de validation explicite de l'architecte avant tout début d'implémentation — cette création de document n'implique, à elle seule, aucune autorisation d'implémenter.
