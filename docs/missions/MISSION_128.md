# Mission 128 — Training Advanced Configuration: Text Encoder Training Duration

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en attente de validation finale de l'architecte.** Rédigé à la suite de trois étapes préalables validées explicitement par l'architecte : l'audit de couverture Training post-M126, le micro-audit ciblé sur `stop_training_after`/`stop_training_after_unit` (traçage complet de `TimedActionMixin`, `BaseModelSetup`, presets officiels réels), et le micro-audit final de verrouillage (sémantique exacte de `TimeUnit.ALWAYS`, frontières exactes de `STEP` avec gradient accumulation, contrat produit et Domain). Implémentation conforme à ce contrat, **+57 tests nets (2605 → 2662 tests collectés), 458/458 tests ciblés M128 verts** — voir résultats en section 13/14. Aucun smoke GPU requis ni exécuté.

## 1. Contexte

L'audit de couverture Training post-M126 puis le micro-audit dédié (validés séparément par l'architecte) ont établi que `TrainModelPartConfig.stop_training_after`/`stop_training_after_unit` (moteur OneTrainer, `modules/util/config/TrainConfig.py`) gouvernent la durée d'entraînement de chaque Text Encoder, et que ce réglage est aujourd'hui **structurellement inaccessible** depuis AI Studio Toolkit : ni exposé en UI, ni atteignable via `extra_overrides` (`text_encoder`/`text_encoder_2` étant des clés structurées entièrement réservées depuis Mission 121). Le micro-audit final de verrouillage a ensuite résolu tous les points encore ouverts (sémantique exacte de `TimeUnit.ALWAYS`, frontières précises de `STEP` sous gradient accumulation, matrice définitive des presets officiels réels, contrat Domain/Manager/traduction recommandé) avant la rédaction du présent contrat.

Mission 128 expose ce réglage sous une forme structurée, alignée sur les conventions Toolkit déjà établies (sentinelles `""`/`None`, accumulateur nested component de Mission 124, architecture gating de Mission 124), sans reproduire les pièges de l'UI brute OneTrainer (`0+EPOCH`/`0+STEP` gelant immédiatement, `ALWAYS` sans bénéfice produit identifié, unités temporelles hors sujet pour ce contexte).

## 2. Décisions d'architecture validées par l'architecte (avant rédaction)

1. Quatre nouveaux champs Domain : `text_encoder_stop_training_mode`/`text_encoder_stop_training_after` et `text_encoder_2_stop_training_mode`/`text_encoder_2_stop_training_after` — jamais un couple unique partagé entre TE1/TE2.
2. `*_stop_training_mode: str = ""` avec exactement 4 valeurs autorisées : `""`/`"NEVER"`/`"EPOCH"`/`"STEP"` — jamais `"ALWAYS"`, jamais une unité temporelle.
3. `*_stop_training_after: Optional[int] = None` — `None` est le sentinel "non configuré", **`0` n'est jamais un sentinel** (valeur moteur réelle, jamais convertie silencieusement en "illimité").
4. Validation de la cohérence mode/valeur dans la couche de traduction (`src/engines/onetrainer_config.py`), jamais dans le Domain — même principe que `_GRADIENT_CHECKPOINTING_VALUES` (M127).
5. `TimeUnit.ALWAYS` n'est **jamais** exposé par l'UI Toolkit — primitive moteur sans besoin produit identifié (voir section 5), sans que le support OneTrainer lui-même ne soit modifié.
6. `SECOND`/`MINUTE`/`HOUR` ne sont **jamais** exposées pour ce réglage — alignement avec l'exclusion volontaire de l'UI officielle OneTrainer elle-même (`time_entry(..., supports_time_units=False)`), jamais une restriction Toolkit arbitraire.
7. TE1 : SD1.5/SDXL/FLUX. TE2 : SDXL/FLUX uniquement (SD1.5 n'expose jamais TE2). Aucun TE3/TE4 — hors périmètre des architectures Toolkit actuelles.
8. Écriture minimale pour `NEVER` : uniquement `stop_training_after_unit`, jamais un `stop_training_after` d'accompagnement (`0` ou `30`) sans effet moteur.
9. Réutilisation stricte de l'accumulateur `component_configs` introduit par Mission 124 — les nouvelles sous-clés (`stop_training_after`/`stop_training_after_unit`) s'ajoutent au même objet nested que `weight_dtype`/`train`, sans jamais l'écraser.
10. `train=False` + durée configurée reste **valide, persistée et traduite** — la condition est simplement inactive pour ce run (court-circuit moteur), jamais reset automatiquement par Toolkit.
11. Aucun smoke GPU n'est requis pour l'acceptation fonctionnelle de M128 — un smoke expérimental de transition (`1/EPOCH`) reste possible séparément, après validation fonctionnelle complète, sur autorisation explicite distincte.

## 3. Preuves des audits préalables (reprises intégralement)

### 3.1 Défauts moteur exacts (`TrainConfig.py`)

| Composant | `train` | `stop_training_after` | `stop_training_after_unit` |
|---|---|---|---|
| `text_encoder` | `True` | `30` | `EPOCH` |
| `text_encoder_2` | `True` | `30` | `EPOCH` |
| `unet`/`prior`/`transformer` (référence, hors périmètre M128) | `True` | `0` | `NEVER` |

### 3.2 `single_action_elapsed()` (`TimedActionMixin.py`)

```python
case TimeUnit.EPOCH:  return (train_progress.epoch + 1) > int(delay)
case TimeUnit.STEP:   return (train_progress.global_step + 1) > int(delay)
case TimeUnit.NEVER:  return False   # delay jamais lu
case TimeUnit.ALWAYS: return True    # delay jamais lu
```

Réévalué après **chaque** step réel (`GenericTrainer.py:811`, `after_optimizer_step()`), plus une évaluation initiale dans `setup_model()` (avant tout step, `epoch=0`/`global_step=0`).

### 3.3 `TimeUnit.ALWAYS` — sans besoin produit identifié

`grep` exhaustif : `TimeUnit.ALWAYS` n'apparaît que dans `TimedActionMixin.py` lui-même — aucun défaut, aucun preset, aucune autre référence. Avec `train=True` + `unit=ALWAYS` : l'évaluation initiale de `setup_model()` retourne déjà `True` → **0 step réellement entraîné**, strictement identique à `0+EPOCH`/`0+STEP` en pratique. Mais contrairement à `train=False` : le wrapper LoRA du Text Encoder est quand même créé (`create_te1 = config.text_encoder.train or ...`), ses paramètres sont quand même ajoutés au groupe de l'optimizer (`_create_model_part_parameters` ne teste que `config.train`), et le composant reste résident sur le GPU (`train_text_encoder_or_embedding()` ne teste que `config.text_encoder.train`) — VRAM/compute gaspillés pour zéro bénéfice, jamais préférable à `text_encoder_train=False`. Aucun cas d'usage produit identifié.

### 3.4 `STEP` — micro-batchs, pas mises à jour optimizer

`train_progress.global_step` est incrémenté à **chaque micro-batch** (`GenericTrainer.py:831`), tandis que la vérification de la condition d'arrêt n'a lieu que lors d'un vrai step d'optimizer (`__is_update_step()`, ligne 551-554, teste `(global_step+1) % gradient_accumulation_steps == 0`). Avec `gradient_accumulation_steps > 1`, `stop_training_after`/`STEP` compte donc des micro-batchs, **pas** des mises à jour réelles de poids — jamais promis comme un nombre exact d'optimizer updates dans l'UI Toolkit (voir section 10).

### 3.5 Matrice définitive des presets officiels (fichiers réels lus directement)

|  | **SD1.5** | **SDXL** | **FLUX** |
|---|---|---|---|
| TE1 `train` | ABSENT → moteur `True` | `false` explicite | `false` explicite |
| TE1 `stop_training_after`/`_unit` | ABSENT → moteur `30`/`EPOCH` | ABSENT (sans effet) | ABSENT (sans effet) |
| TE2 `train` | n/a (pas de TE2) | `false` explicite | `false` explicite |
| TE2 `stop_training_after`/`_unit` | n/a | ABSENT (sans effet) | ABSENT (sans effet) |

Sous SD1.5, le TE s'entraîne réellement avec le gel automatique à 30 epochs silencieusement actif. Sous SDXL et FLUX, aucun des deux Text Encoders ne s'entraîne dans le preset officiel — la question de la durée y est sans objet.

## 4. Problème produit

Toute Training Toolkit où `text_encoder_train=True` (explicite ou implicitement via le défaut moteur quand `text_encoder_train` est `None`) hérite silencieusement d'un gel automatique après 30 epochs, sans qu'aucun réglage Toolkit actuel ne permette de le changer, de le désactiver, ou même de le savoir. Ce n'est pas un bug introduit par une mission antérieure — c'est un comportement moteur historique jamais rendu contrôlable jusqu'ici. Mission 128 rend ce comportement explicite et pilotable, sans reproduire l'UI brute OneTrainer (champ numérique libre + 4 unités dont deux sans intérêt produit avéré).

## 5. Sémantique des 3 modes exposés

| Mode Toolkit | Traduction OneTrainer | Effet |
|---|---|---|
| `""` (Non configuré) | Aucune clé écrite | Défaut moteur conservé (`30`/`EPOCH`) — comportement historique inchangé |
| `"NEVER"` (Toujours entraîner) | `stop_training_after_unit` seul | Aucune limite — corrige le piège historique |
| `"EPOCH"` (Arrêter après N epochs) | `stop_training_after`/`stop_training_after_unit` | Gel après N epochs pleines (+ un step de tolérance, cf. section 3.2) |
| `"STEP"` (Arrêter après N steps) | `stop_training_after`/`stop_training_after_unit` | Gel après N micro-batchs (jamais promis comme N mises à jour optimizer exactes) |

`TimeUnit.ALWAYS`, `SECOND`, `MINUTE`, `HOUR` restent des primitives moteur valides mais **jamais exposées** par cette mission (sections 2.5/2.6).

## 6. Contrat Domain (`src/domain/onetrainer_settings.py`)

```python
# Mission 128: which OneTrainer TimeUnit governs this Text Encoder's
# stop_training_after — "" means "not configured", never one of the real
# engine values (NEVER/EPOCH/STEP), omitted from the built config when
# empty, letting OneTrainer's own real default (30/EPOCH) apply exactly
# as it did before this mission — the exact historical Toolkit behavior.
# 0 is never a sentinel for the paired *_after field: it is a real engine
# value (an immediate freeze under EPOCH/STEP), never silently converted
# to "unlimited" (see MISSION_128.md section 3 for the confirmed
# semantics of TimeUnit.ALWAYS and the STEP/EPOCH boundary behavior).
text_encoder_stop_training_mode: str = ""
text_encoder_stop_training_after: Optional[int] = None

text_encoder_2_stop_training_mode: str = ""
text_encoder_2_stop_training_after: Optional[int] = None
```

Positionnement : juste après `text_encoder_train`/`text_encoder_2_train` (Mission 124), avant `lora_layer_filter`. `to_dict()`/`from_dict()` étendus symétriquement (mode : `data.get(..., "")` ; after : garde de type `isinstance(x, int)` avant conservation, sinon `None` — même garde défensive que tout champ `Optional[int]` existant, tolérant un `project.json` édité à la main).

## 7. Contrat Manager (`src/managers/training_manager.py`)

`TrainingManager.update()` étendu avec quatre nouveaux paramètres :

```python
text_encoder_stop_training_mode: Optional[str] = None,
text_encoder_stop_training_after: int | _UNSET_TYPE = _UNSET,
text_encoder_2_stop_training_mode: Optional[str] = None,
text_encoder_2_stop_training_after: int | _UNSET_TYPE = _UNSET,
```

- Champs `*_mode` (`str`) : pattern M127 — `None` = argument non fourni (ne touche pas la valeur existante), `""` = reset explicite vers "non configuré". Le sentinel "non configuré" du Domain étant déjà `""`, aucun `_UNSET` n'est nécessaire ici.
- Champs `*_after` (`Optional[int]`) : le sentinel "non configuré" du Domain est `None` lui-même — une signature `Optional[int] = None` ne permettrait pas de distinguer "argument non fourni" de "reset explicite vers `None`". **Réutilisation du `_UNSET = object()` déjà introduit par Mission 124** pour `text_encoder_train`/`text_encoder_2_train` (même problème structurel, même solution, pas de nouveau mécanisme) : `_UNSET` (défaut) = argument non fourni, valeur conservée telle quelle ; `None` explicite = reset ; tout entier = nouvelle valeur.
- Contrat de non-ambiguïté explicitement vérifié par test (section 12.G) : depuis `after=10`, `update()` sans l'argument conserve `10` ; `update(text_encoder_stop_training_after=None)` reset bien vers `None`.
- Les quatre nouveaux champs rejoignent les tuples `previous`/rollback dans le même ordre exact que leur déclaration Domain, juste après `text_encoder_train`/`text_encoder_2_train`.
- `prepare_onetrainer_config()` : les quatre champs transmis tels quels à `build_training_config()`.

## 8. Contrat traduction OneTrainer (`src/engines/onetrainer_config.py`)

Réutilisation de l'accumulateur `component_configs` introduit par Mission 124 (une troisième paire de boucles, après celles de `weight_dtype`/`train`) :

```python
stop_training_fields = {
    "text_encoder_stop_training_mode": (text_encoder_stop_training_mode, text_encoder_stop_training_after),
    "text_encoder_2_stop_training_mode": (text_encoder_2_stop_training_mode, text_encoder_2_stop_training_after),
}
for field_name, (mode, after) in stop_training_fields.items():
    if mode:
        component_key = _STOP_TRAINING_FIELD_TO_COMPONENT_KEY[field_name]
        component_dict = component_configs.setdefault(component_key, {})
        if after is not None:
            component_dict["stop_training_after"] = after
        component_dict["stop_training_after_unit"] = mode
```

Validation (avant la traduction, même style que `_GRADIENT_CHECKPOINTING_VALUES`) :
- `mode` non vide hors `{"NEVER", "EPOCH", "STEP"}` → `OneTrainerConfigError`.
- `mode=""` + `after` configuré → `OneTrainerConfigError` ("" implique after=None).
- `mode="NEVER"` + `after` configuré → `OneTrainerConfigError`.
- `mode in {"EPOCH", "STEP"}` + `after is None` → `OneTrainerConfigError`.
- `mode in {"EPOCH", "STEP"}` + `after <= 0` → `OneTrainerConfigError`.
- Architecture gating : `_STOP_TRAINING_FIELDS_BY_ARCHITECTURE`, table jumelle dédiée de `_TRAIN_FIELDS_BY_ARCHITECTURE` (M124), détermine si `text_encoder_2_stop_training_mode` est applicable à l'architecture courante. **Correction découverte pendant l'implémentation, par rapport au brouillon initial de cette section** : contrairement au mécanisme des champs dtype/train (qui lèvent `OneTrainerConfigError` en cas d'incompatibilité), un champ TE2 configuré mais inapplicable à l'architecture courante (ex. SD1.5) n'est **jamais rejeté par une erreur** — il est simplement exclu silencieusement de la configuration construite. Décision produit intentionnelle, cohérente avec la persistance Domain introduite section 10 : un Training temporairement basculé sur SD1.5 avec une durée TE2 déjà configurée sous SDXL/FLUX doit pouvoir être préparé (JSON généré) sans échec, la valeur simplement omise. La validation de valeur/cohérence (mode/after) reste, elle, toujours appliquée indépendamment de l'architecture — seule l'émission JSON est conditionnée par l'applicabilité architecture.
- Aucune correction silencieuse de la **valeur** : une configuration mode/after invalide lève toujours, jamais une conversion automatique (ex. `0` → `NEVER`) — cette règle ne concerne pas l'omission par inapplicabilité architecture décrite ci-dessus, qui porte sur une valeur par ailleurs valide.

Exemple TE1 complet (cohabitation train + dtype + stop, même objet nested) :
```json
"text_encoder": {
    "weight_dtype": "FLOAT_16",
    "train": true,
    "stop_training_after": 10,
    "stop_training_after_unit": "EPOCH"
}
```

Écriture minimale pour `NEVER` (`after=None`) :
```json
"text_encoder": { "stop_training_after_unit": "NEVER" }
```
Jamais de `"stop_training_after": 0` ni `30` en accompagnement.

## 9. `extra_overrides`

Aucun nouveau mécanisme de réservation nécessaire : `"text_encoder"`/`"text_encoder_2"` sont déjà des clés structurées protégées dans `_STRUCTURED_CONFIG_KEYS` (Mission 121) — la réservation porte sur la clé composant entière, pas sur un sous-chemin. Une tentative `extra_overrides = {"text_encoder": {"stop_training_after": ...}}` reste rejetée par le mécanisme existant, sans modification. Un test dédié (section 12.section traduction) confirme explicitement ce rejet pour les nouveaux sous-champs.

## 10. Contrat UI (`src/ui/pages/training_page.py`)

Pour chaque Text Encoder disponible pour l'architecture active, à proximité du combo `Train Text Encoder` existant (Mission 124) : un nouveau contrôle « Training duration » avec 3 états utilisateur :
- **Non configuré**
- **Toujours entraîner**
- **Arrêter après**, révélant alors deux sous-contrôles : **Value** (entier ≥ 1) et **Unit** (Epochs / Steps).

`NEVER`/`EPOCH`/`STEP` (valeurs moteur réelles) ne sont jamais montrées telles quelles à l'utilisateur — seuls les labels `Toujours entraîner`/`Epochs`/`Steps` apparaissent. Le Domain conserve les valeurs moteur exactes en interne. Value/Unit sont cachés ou désactivés hors du mode "Arrêter après" — jamais laissés visibles-mais-sans-effet comme le fait l'UI officielle OneTrainer elle-même.

Tooltip factuel pour Unit=Steps (jamais un nombre exact d'optimizer updates promis) :
> *"Steps follows OneTrainer's own training-step counter. With gradient accumulation greater than 1, this does not necessarily equal the number of optimizer updates."*

Comportement architecture-aware : TE2 visible/masqué pour SDXL/FLUX vs SD1.5 selon le même gating architecture (`_STOP_TRAINING_FIELDS_BY_ARCHITECTURE`, jumelle de `_TRAIN_FIELDS_BY_ARCHITECTURE`), le contrôle TE1 restant générique aux 3 architectures, jamais masqué.

**Correction découverte pendant l'implémentation** : le brouillon initial de cette section affirmait que ce masquage suivait « le même mécanisme exact » que `text_encoder_2_train`/`text_encoder_2_weight_dtype` (M121/M124) — cette affirmation était **factuellement incorrecte**. La lecture directe de `_apply_architecture_to_dtype_fields(reset_incompatible=True)` (`training_page.py`) montre que ces champs historiques sont réellement **réinitialisés** (`setCurrentIndex(0)`) lors d'un changement réel vers une architecture incompatible, sans jamais être restaurés au retour dans la même session d'édition — documenté ainsi de manière intentionnelle depuis Mission 121/124 (« never resurfaces later in the same editing session if the architecture is switched back »).

**M128 introduit intentionnellement une politique différente et volontairement plus généreuse pour ses seuls nouveaux champs TE2 stop-training** : le gating architecture ne contrôle que la **visibilité/l'activation** des widgets `text_encoder_2_stop_training_mode`/`text_encoder_2_stop_training_after` — il ne touche jamais leur valeur Domain. Un passage temporaire SDXL → SD1.5 → SDXL conserve donc la configuration TE2 déjà saisie (visible de nouveau au retour sur SDXL/FLUX), alors que le composant `text_encoder_2_train` de la même ligne UI, lui, resterait reset par son mécanisme historique inchangé. Cette divergence entre deux contrôles de la même ligne UI est assumée : la valeur Domain et l'applicabilité architecture-courante sont deux notions distinctes, et rendre une configuration temporairement inapplicable ne signifie pas que l'utilisateur souhaite la perdre. **L'harmonisation éventuelle du comportement historique (`text_encoder_2_train`/`text_encoder_2_weight_dtype`/champs flow-matching FLUX) avec ce nouveau principe de persistance reste explicitement hors périmètre de M128** — dette à trancher séparément, jamais implémentée par anticipation ici.

Traduction (`build_training_config()`) : la persistance Domain ne signifie jamais émission JSON — pour une architecture où TE2 n'est pas applicable (SD1.5), `text_encoder_2_stop_training_mode`/`_after` peuvent rester non vides dans le Domain sans qu'aucune clé `stop_training_after`/`stop_training_after_unit` TE2 ne soit jamais écrite (le gating architecture de la traduction, section 8, l'empêche structurellement — jamais une simple convention UI).

`train=False` ne réinitialise jamais la durée configurée (persistance volontaire, section 2.10). Chargement d'un Training existant : jamais de dirty state artificiel déclenché par le simple affichage des valeurs chargées.

## 11. Compatibilité historique

Pour toute Training antérieure à Mission 128 (les 4 nouveaux champs valent `""`/`None` par défaut), aucune nouvelle clé n'est écrite dans la configuration OneTrainer produite — comportement strictement identique à avant cette mission :

| `text_encoder_train` | Résultat moteur avant/après M128 |
|---|---|
| `None` | `train=True`, `stop=30/EPOCH` (défaut moteur, inchangé) |
| `True` | `train=True`, `stop=30/EPOCH` (défaut moteur, inchangé — le piège historique reste présent tant que l'utilisateur ne configure pas explicitement `NEVER`) |
| `False` | `train=False`, stop condition sans effet (inchangé) |

Mission 128 ne modifie aucune Training existante ; elle donne seulement à l'utilisateur, pour la première fois, la possibilité explicite de choisir `Toujours entraîner` pour corriger ce comportement.

## 12. Stratégie de tests

### Domain / round-trip (A–H)
A. Defaults des 4 nouveaux champs. B. `to_dict()`/`from_dict()` round-trip. C. Valeurs TE1. D. Valeurs TE2. E. Reset explicite `mode` vers `""`. F. Reset explicite `after` vers `None`. G. Manager : distinction argument non fourni (`_UNSET`) vs `None` explicite pour `*_after`, réplique littérale du contrat. H. Rollback Manager restaure les 4 champs sur le même objet après échec de sauvegarde.

### Traduction (I–AB)
I. `""`/`None` → aucune stop key. J. `NEVER`/`None` → unit seul. K. `EPOCH`/1. L. `EPOCH`/N. M. `STEP`/1. N. `STEP`/N. O. Mode invalide → erreur. P. `EPOCH`/`None` → erreur. Q. `STEP`/`None` → erreur. R. `EPOCH`/0 → erreur. S. `STEP`/0 → erreur. T. Valeur négative → erreur. U. `""` + `after` configuré → erreur. V. `NEVER` + `after` configuré → erreur. W. Cohabitation avec `train` dans le même objet nested. X. Cohabitation avec `weight_dtype`. Y. Cohabitation train + dtype + stop dans le même objet nested (config FLUX représentative complète, dans l'esprit des tests M126). Z. TE2 SDXL. AA. TE2 FLUX. AB. TE2 stop-training valide conservé dans le Domain mais omis du JSON pour SD1.5 (jamais une erreur — voir section 8 pour la correction documentaire sur ce point précis). Plus : rejet `extra_overrides` sur les nouvelles sous-clés (section 9).

### UI (AC–AP)
AC. Contrôles visibles TE1 SD1.5. AD. TE2 absent/masqué SD1.5. AE. TE1+TE2 visibles SDXL. AF. TE1+TE2 visibles FLUX. AG. "Non configuré" charge correctement. AH. "Toujours entraîner" charge correctement. AI. "Arrêter après" + Epoch charge value/unit. AJ. "Arrêter après" + Step charge value/unit. AK. Value/Unit cachés ou désactivés hors mode "Arrêter après". AL. Value ≥ 1 imposé côté UI. AM. Changement UI persiste dans le Domain via `save_training_parameters()`. AN. Rechargement d'un Training existant sans dirty state artificiel. AO. Changement d'architecture temporaire (SDXL → SD1.5 → SDXL) conserve les valeurs TE2. AP. `train=False` ne réinitialise jamais la durée déjà configurée.

### Non-régression
`project.json` historique (sans les 4 nouveaux champs) charge sans erreur ; `prepare_onetrainer_config()` sur une Training historique produit une configuration JSON fonctionnellement identique à avant M128 ; comportement de `text_encoder_train`/`text_encoder_2_train` inchangé quand la durée reste non configurée ; suites de tests Mission 124/125/126/127 restent entièrement vertes (aucune assertion affaiblie ou supprimée).

## 13. Smoke — statut

**Non requis pour l'acceptation fonctionnelle de M128.** La mission porte sur Domain/Manager/UI/traduction JSON/validation — entièrement vérifiable sans entraînement réel (même principe que la validation FLUX headless de Mission 126, jamais un smoke GPU FLUX). Un smoke expérimental optionnel (SDXL, TE1 `train=True`, `duration=1/EPOCH`, ≥ 3 epochs, pour observer la transition dynamique réelle `requires_grad`/VRAM/temps de step) reste envisageable **séparément**, après validation fonctionnelle complète, sur autorisation explicite distincte — jamais exécuté automatiquement dans le cadre de cette mission.

### Résultat réel

**Confirmé : aucun smoke GPU n'a été exécuté**, conformément à la décision ci-dessus — l'acceptation fonctionnelle de M128 repose exclusivement sur les tests réels détaillés en section 14.

## 14. Critères d'acceptation

- [x] Domain TE1/TE2 (4 champs) ajouté avec sentinelles conformes (`""`/`None`, `0` jamais un sentinel).
- [x] Manager étendu, rollback correct, `_UNSET` réutilisé pour `*_after` sans nouvelle ambiguïté.
- [x] Reset explicite `after=None` fonctionnel et testé (distinction non-fourni vs `None`).
- [x] Traduction nested sans collision avec `weight_dtype`/`train` existants.
- [x] `NEVER` traduit en écriture minimale (unit seul, jamais de `stop_training_after` d'accompagnement).
- [x] `EPOCH`/`STEP` : validation stricte `after >= 1`, jamais de correction silencieuse.
- [x] UI architecture-aware (TE2 masqué SD1.5, visible SDXL/FLUX) — **avec une divergence intentionnelle par rapport au brouillon initial, voir "Résultats réels" ci-dessous**.
- [x] `train=False` conserve la durée déjà configurée, jamais reset automatiquement.
- [x] `extra_overrides` reste protégé sur `text_encoder`/`text_encoder_2` (confirmé par test, aucun nouveau mécanisme).
- [x] Compatibilité historique démontrée (`project.json` antérieur → configuration JSON fonctionnellement identique).
- [x] Tests ciblés verts (Domain, Manager, traduction, UI, non-régression).
- [x] Suite complète — voir formulation exacte ci-dessous (jamais un simple "2662/2662").
- [x] Aucun smoke GPU requis pour cette validation.
- [x] Aucun changement hors périmètre (section 15).

### Résultats réels

**Tests : +57 nets (2580+25 après M127 = 2605 → 2662 tests collectés)**, répartis `test_onetrainer_config.py` 109→137 (+28) et `test_training_roundtrip.py` 292→321 (+29). **458/458 tests ciblés M128 verts** (les deux fichiers ci-dessus, exécutés intégralement à plusieurs reprises, toujours verts).

**Suite complète — formulation exacte retenue** (jamais "2662/2662 OK", faute d'une capture complète démontrant un run intégral vert) :
- 2662 tests collectés (confirmé par comptage direct, hors exécution) ;
- 458/458 tests ciblés M128 verts, sans exception, sur toutes les exécutions ;
- plusieurs exécutions complètes de la suite ont rencontré des échecs intermittents dans des tests **préexistants** de timing/lifecycle de processus, tous deux **hors du diff M128** :
  - `tests/integration/test_main_window_new_project.py::MainWindowInferencePendingResultGuardTest::test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure` — flake déjà observé et documenté à la clôture de Mission 127 (même test, même assertion `assertLess(elapsed, 1.0)`, taux 1/8 en isolation à l'époque) ;
  - `tests/integration/test_forge_lifecycle_manager.py::ForgeLifecycleManagerRealProcessTest::test_stop_on_running_owned_kills_the_real_process_tree` — fichier historiquement instable depuis Mission 097 (`docs/PROJECT_CONTEXT.md`) ;
- aucun échec ciblé M128 n'a été observé sur aucune exécution ;
- aucun élément établi ne démontre une régression M128 ;
- un canal Qt indirect (poids d'objets `QWidget` ajoutés à `TrainingPage`, donc à toute construction de `MainWindow`) reste théoriquement possible pour le flake `dialog_guard` et n'est pas formellement exclu — mais ce même flake était déjà documenté à un taux comparable avant l'existence de M128.

**Divergence architecture TE2 — résolution finale** : le brouillon initial prévoyait de réutiliser "le même mécanisme exact" que `text_encoder_2_train` pour le masquage TE2 lors d'un changement d'architecture. L'implémentation a révélé que ce mécanisme historique **réinitialise réellement** la valeur (jamais restaurée). Décision retenue et implémentée : les nouveaux champs TE2 stop-training **persistent leur valeur Domain** à travers un changement temporaire d'architecture (seule la visibilité change), avec omission JSON silencieuse (jamais une erreur) pour une architecture incompatible — divergence intentionnelle par rapport aux champs historiques, documentée aux sections 8/10, harmonisation éventuelle explicitement hors périmètre (voir section 10, dernier paragraphe).

**Micro-correction post-implémentation** : `_load_stop_training_widgets()` laissait un résidu visuel (le spinbox Value conservait la valeur numérique d'une Training précédemment chargée lorsque le mode rechargé était `""`/`NEVER`) — jamais écrit dans le Domain, purement cosmétique, corrigé par une réinitialisation explicite à `1` dans ce cas, avec 4 tests dédiés ajoutés.

## 15. Hors périmètre strict de M128

`text_encoder_3`/`text_encoder_4` (aucune architecture Toolkit actuelle ne les utilise) ; condition d'arrêt pour `unet`/`transformer`/`prior` (jamais un besoin identifié) ; `TimeUnit.ALWAYS` et les unités `SECOND`/`MINUTE`/`HOUR` (primitives moteur valides, jamais exposées par cette mission) ; nettoyage de l'état optimizer après gel ; déplacement automatique GPU→temp_device après gel ; `QuantizationConfig` complet ; offloading avancé (`enable_activation_offloading`/`enable_async_offloading`/`layer_offload_fraction`) ; presets Training Toolkit ; Hardware-aware Training ; Training Preflight.

## 16. Rappel — dette Text Encoder désormais traitée par cette mission

Le finding confirmé par les audits préalables — `text_encoder_train=True` (ou `None`, défaut moteur) sans durée configurée hérite silencieusement de `30`/`EPOCH` côté moteur, sans que Toolkit ne l'expose ni ne permette de le changer — **n'est pas un bug introduit par une mission antérieure**, c'est un comportement moteur historique jamais rendu contrôlable jusqu'ici (`docs/PROJECT_CONTEXT.md`, section "Problèmes connus / dettes", dette enregistrée lors de la régularisation post-M127). Mission 128 rend ce comportement explicite et pilotable via le mode `Toujours entraîner`, sans modifier aucune Training existante (section 11).

## 17. Perspective Presets / Hardware-aware / Preflight (rappel, non implémenté)

Les presets Toolkit (`Recommended`/`Memory Efficient`/`Custom`), l'adaptation Hardware-aware Training et le Training Preflight restent hors périmètre. La matrice des presets officiels reproduite en section 3.5 constitue une référence pour une future mission Presets, jamais une implémentation anticipée par M128.

## 18. Autorisation

Contrat validé par l'architecte à la suite de l'audit de couverture post-M126, du micro-audit `stop_training_after`/`stop_training_after_unit`, et du micro-audit final de verrouillage (`TimeUnit.ALWAYS`, frontières `STEP`, contrat Domain/Manager/traduction). Implémentation, tests, et clôture (commit/tag/Release) à mener dans les tours suivants, chacun sur validation explicite séparée, conformément au workflow de mission permanent (`CLAUDE.md`).
