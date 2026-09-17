# Mission 129 — Architecture-Aware Field Persistence Harmonization

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en attente de validation finale de l'architecte.** Rédigé à la suite de l'audit post-M128 (couverture Training, gaps réels, chantiers hors Training) et du micro-audit technique en lecture seule qui l'a suivi (traçage complet de `_apply_architecture_to_dtype_fields()`, de `build_training_config()`, de `TrainingManager.update()`/`prepare_onetrainer_config()`, et des tests existants), tous deux validés explicitement par l'architecte. Implémentation conforme à ce contrat, **+10 tests nets (2662 → 2672 tests collectés)**, 468/468 tests ciblés M129 verts (`test_onetrainer_config.py` + `test_training_roundtrip.py`), une suite complète unique exécutée **2672/2672, OK, exit 0**, sans aucune failure ni flake observé sur ce run — voir section "Résultats réels" en fin de document. Aucun smoke GPU requis ni exécuté.

## 1. Contexte

L'audit post-M128 a recommandé, parmi trois candidats, la correction d'une perte de données réelle et démontrable découverte par l'audit de clôture de Mission 128 elle-même : lorsqu'un utilisateur bascule temporairement l'architecture d'une Training (SDXL/FLUX → SD1.5 → retour), cinq réglages architecture-aware déjà persistés sont **irrémédiablement effacés** si la Training est sauvegardée pendant que l'architecture incompatible est sélectionnée — pas un défaut cosmétique, une perte silencieuse d'une configuration déjà enregistrée par l'utilisateur.

Mission 128 avait déjà introduit, pour ses deux propres nouveaux champs (`text_encoder_2_stop_training_mode`/`_after`), un mécanisme correct : Domain persistant, UI masquée sans reset, JSON omis sans erreur, restauration automatique au retour d'architecture compatible. Le micro-audit technique a confirmé que ce même mécanisme peut être généralisé aux cinq champs architecture-aware plus anciens identifiés par l'audit, avec une extension minimale et sans risque du translator, et sans aucune modification Domain/Manager.

## 2. Décisions validées par l'architecte (avant rédaction)

1. Généralisation du principe de persistance introduit par M128 aux cinq champs listés en section 3 — le comportement historique de reset (`setCurrentIndex(0)`/`.setChecked(False)` sur incompatibilité d'architecture) est abandonné pour ces champs précisément, jamais réintroduit.
2. **Aucune nouvelle validation de valeur n'est ajoutée.** Le micro-audit a démontré que ces cinq champs n'ont aujourd'hui aucune validation structurelle de leur propre valeur (contrairement à `stop_training_mode` de M128, qui a un enum dédié) — seule l'appartenance architecture/champ est actuellement vérifiée. M129 supprime uniquement l'erreur liée à cette appartenance ; il n'invente aucun contrôle de valeur qui n'existait pas avant cette mission.
3. `unet_weight_dtype`/`transformer_weight_dtype` restent **strictement hors périmètre** — mécanisme de `_draft` structurellement différent (deux champs Domain mutuellement exclusifs, pas un simple masquage d'un même champ), comportement de validation architecture inchangé.
4. Domain et Manager (`src/managers/training_manager.py`) ne sont **a priori pas modifiés** — hypothèse forte confirmée par le micro-audit (aucune logique architecture-dépendante n'existe à ce niveau pour ces cinq champs). Toute divergence découverte en implémentation doit être un motif d'arrêt et de rapport avant modification, jamais un contournement silencieux.
5. Le mécanisme `component_configs` (nested per-composant) introduit par Mission 124 et déjà réutilisé par Mission 128 n'est **pas réarchitecturé** — seule la condition d'admission dans les boucles d'accumulation change.
6. Neuf tests existants qui attendent aujourd'hui `OneTrainerConfigError` pour ces cinq champs doivent être réécrits pour prouver le nouveau contrat (configuration acceptée, clé incompatible omise) — jamais simplement supprimés.
7. Aucun smoke GPU n'est requis pour l'acceptation fonctionnelle de M129 — aucune sémantique moteur OneTrainer n'est modifiée, seule la construction du dictionnaire de configuration et l'état des widgets changent.

## 3. Preuves du micro-audit technique (reprises intégralement)

### 3.1 Matrice des 5 champs dans le périmètre

| Champ | Architectures compatibles | Sentinelle Domain | Widget UI | Reset actuel sur incompatibilité | Lu au Save depuis |
|---|---|---|---|---|---|
| `text_encoder_2_weight_dtype` | SDXL, FLUX | `""` | `text_encoder_2_weight_dtype_combo` | `setCurrentIndex(findData(""))` | `combo.currentData()` (aucun draft) |
| `text_encoder_2_train` | SDXL, FLUX | `None` | `text_encoder_2_train_combo` | `setCurrentIndex(0)` | `combo.currentData()` (aucun draft) |
| `timestep_distribution` | FLUX uniquement | `""` | `timestep_distribution_combo` | `setCurrentIndex(findData(""))` | `combo.currentData()` (aucun draft) |
| `dynamic_timestep_shifting` | FLUX uniquement | `None` | `dynamic_timestep_shifting_combo` | `setCurrentIndex(0)` | `combo.currentData()` (aucun draft) |
| `timestep_shift` | FLUX uniquement | `None` | `timestep_shift_checkbox` + `timestep_shift_spinbox` | `checkbox.setChecked(False)` | `spinbox.value() if checkbox.isChecked() else None` |

Tous les cinq sont lus **directement depuis leur widget au moment du Save**, jamais depuis une variable Domain ou un draft intermédiaire — confirmé par lecture directe de `save_training_parameters()`. Il n'existe donc, dès aujourd'hui, aucune seconde source de vérité à démonter : le seul obstacle à la persistance est le reset explicite listé ci-dessus, à l'intérieur de `_apply_architecture_to_dtype_fields(reset_incompatible=True)`.

### 3.2 Comportement translator actuel (`src/engines/onetrainer_config.py`)

Confirmé par lecture directe et vérifié cas par cas :

- SD1.5 + `text_encoder_2_weight_dtype="FLOAT_16"` → lève `OneTrainerConfigError` (boucle `dtype_fields`/`_DTYPE_FIELDS_BY_ARCHITECTURE`).
- SD1.5 + `text_encoder_2_train=False` → lève `OneTrainerConfigError` (`train_fields`/`_TRAIN_FIELDS_BY_ARCHITECTURE` — `False` compte comme "configuré").
- SDXL + `timestep_distribution="LOGIT_NORMAL"` → lève `OneTrainerConfigError` (`_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE["SDXL"]` est vide).
- SDXL + `dynamic_timestep_shifting=True` → lève `OneTrainerConfigError` (même mécanisme).
- SDXL + `timestep_shift=3.0` → lève `OneTrainerConfigError` (même mécanisme).

Aucun de ces cinq champs ne possède de validation de valeur indépendante : `text_encoder_2_weight_dtype`/`timestep_distribution` acceptent aujourd'hui n'importe quelle chaîne non vide sans vérification tant que l'architecture est compatible ; `text_encoder_2_train`/`dynamic_timestep_shifting`/`timestep_shift` n'ont qu'une contrainte de type Python jamais vérifiée par cette fonction. La seule chose actuellement validée est l'appartenance architecture/champ — exactement ce que cette mission relâche, rien de plus.

### 3.3 `TrainingManager.update()`/`prepare_onetrainer_config()`

Confirmé : `update()` ne valide aucune compatibilité d'architecture et n'appelle jamais `build_training_config()` — c'est une simple mutation Domain avec rollback local sur échec de persistence. Le translator n'est invoqué que par `prepare_onetrainer_config()`, uniquement au lancement réel d'un Training. `update()` accepte donc déjà, sans erreur, une valeur "inapplicable" pour l'architecture courante — confirme que la persistance Save-sous-architecture-incompatible (section 8) ne requiert aucune modification Manager.

### 3.4 Dirty-state

`on_architecture_changed()` positionne `self._dirty = True` directement, avant tout appel à `_apply_architecture_to_dtype_fields()` — jamais le gating visuel (`.setVisible()`) lui-même, qui ne déclenche aucun signal Qt pertinent. Un changement d'architecture reste, à raison, une action qui rend la Training dirty ; supprimer les resets explicites réduit même le nombre de signaux `currentIndexChanged` déclenchés en cascade.

### 3.5 Recherche exhaustive d'autres champs architecture-aware

Confirmé par grep de toutes les tables `_BY_ARCHITECTURE` (`onetrainer_config.py`) et de toute occurrence d'`architecture` dans `training_page.py` : les seules tables de gating existantes sont `_DTYPE_FIELDS_BY_ARCHITECTURE`, `_TRAIN_FIELDS_BY_ARCHITECTURE`, `_STOP_TRAINING_FIELDS_BY_ARCHITECTURE` (déjà conforme M128), `_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE`. Aucun champ architecture-aware n'existe en dehors des cinq listés en section 3.1 et du couple `unet_weight_dtype`/`transformer_weight_dtype` (hors périmètre, section 14).

## 4. Objectif produit

Contrat cible, pour chacun des cinq champs :

- **configuration applicable** → visible/utilisable dans l'UI → émise dans le JSON, exactement comme aujourd'hui.
- **configuration temporairement incompatible** → conservée dans le Domain → UI masquée/inapplicable → non émise dans le JSON → aucune erreur d'incompatibilité levée → restaurée automatiquement (Domain, UI, JSON) dès que l'architecture redevient compatible.

Un changement temporaire d'architecture ne doit plus jamais effacer une préférence déjà configurée — que ce changement reste dans la session courante ou qu'il survive à une sauvegarde, une fermeture et une réouverture de l'application.

## 5. Champs exactement dans le périmètre

- `text_encoder_2_weight_dtype` (SDXL/FLUX)
- `text_encoder_2_train` (SDXL/FLUX)
- `timestep_distribution` (FLUX uniquement)
- `dynamic_timestep_shifting` (FLUX uniquement)
- `timestep_shift` (FLUX uniquement)

Aucun autre champ n'entre dans le périmètre de cette mission.

## 6. Correction de contrat — aucune nouvelle validation de valeur

Le micro-audit a établi que ces cinq champs n'ont aujourd'hui aucune validation structurelle de leur contenu (ex. `timestep_distribution="INVALID"` n'est actuellement rejeté sur aucune architecture où le champ est applicable). M129 :

- conserve toutes les validations existantes qui ne concernent pas le gating d'architecture ;
- supprime uniquement l'erreur provoquée par une incompatibilité d'architecture, pour ces cinq champs ;
- n'ajoute **aucune** nouvelle validation d'enum, **aucun** nouveau type guard, **aucune** modification de la sémantique des valeurs aujourd'hui acceptées.

Un test du type « `timestep_distribution="INVALID"` sur architecture incompatible doit lever » **ne doit pas être ajouté** — ce comportement n'existe pas aujourd'hui et ne doit pas être inventé par cette mission (voir section 17). La validation structurelle future de ces champs, si elle est un jour souhaitée, constitue une dette distincte, documentée en section 19, jamais traitée ici.

## 7. Contrat UI (`src/ui/pages/training_page.py`)

Dans `_apply_architecture_to_dtype_fields()` : supprimer uniquement les lignes de reset explicite (`setCurrentIndex(...)`/`.setChecked(False)`) des cinq champs listés en section 5. La logique `.setVisible(...)` déjà en place reste strictement inchangée.

Explicitement interdit : aucun draft, aucun cache, aucun `previous_value`, aucune seconde source de vérité. Le Domain reste l'unique source canonique — un widget déjà chargé depuis le Domain conserve simplement la valeur qu'il affichait avant de devenir masqué, exactement comme un widget masqué le fait déjà nativement en Qt.

## 8. Save sous architecture incompatible

Le contrat doit tenir même si l'utilisateur sauvegarde réellement pendant que l'architecture incompatible est sélectionnée. Scénario de référence, obligatoire en test (matrice section 17, item D) :

```
Training SDXL, text_encoder_2_weight_dtype = FLOAT_16
→ switch SD1.5
→ Save
→ fermeture / rechargement de la Training
→ switch SDXL
→ FLOAT_16 restauré (Domain, UI, JSON)
```

Même exigence pour `text_encoder_2_train`, `timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift`. La persistance ne doit dépendre à aucun moment de widgets encore vivants dans la session courante — elle doit reposer entièrement sur le Domain sérialisé, exactement comme le prouve déjà, pour M128, `test_text_encoder_2_stop_training_persists_domain_and_json_across_temporary_sd15_switch`.

## 9. Contrat translator cible (`src/engines/onetrainer_config.py`)

Pour chacun des cinq champs :

- valeur configurée + architecture compatible → émission identique à aujourd'hui, aucun changement.
- valeur configurée + architecture incompatible → aucune `OneTrainerConfigError` liée à l'architecture ; aucune émission JSON pour ce champ ; Domain inchangé.

Aucune autre validation/gating n'est modifié (dtype `unet`/`transformer`, `optimizer`, `lora_layer_filter`, `gradient_checkpointing_mode`, `extra_overrides`, cohérence mode/valeur des stop-training M128 — tous inchangés).

## 10. Stratégie technique translator

Réutiliser au maximum les ensembles `allowed_*` déjà existants — ne pas réécrire le translator au-delà du strict nécessaire :

- **`text_encoder_2_weight_dtype`** : l'extraire de la boucle de rejet actuelle sur `dtype_fields`/`_DTYPE_FIELDS_BY_ARCHITECTURE` — celle-ci doit continuer à lever pour `unet_weight_dtype`/`transformer_weight_dtype` (section 14), mais plus pour `text_encoder_2_weight_dtype`. La condition d'admission dans la boucle d'accumulation de `component_configs` devient une garde d'appartenance à l'ensemble autorisé, sur le modèle exact de `if mode and mode_field_name in allowed_stop_training_fields:` déjà utilisé par M128.
- **`text_encoder_2_train`** : `text_encoder_train` (TE1) est valide pour les 3 architectures et ne déclenche jamais le rejet — la bascule de toute la boucle `train_fields`/`_TRAIN_FIELDS_BY_ARCHITECTURE` du rejet vers une garde d'émission peut donc se faire sans distinction de champ, sans effet sur `text_encoder_train`.
- **Les 3 champs flow-matching** : tous les trois sont dans le périmètre M129 (aucun champ flow-matching ne doit rester en mode rejet) — la bascule de `_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE` du rejet vers une garde d'émission peut également se faire sans distinction de champ.

## 11. `text_encoder_2` — cohabitation nested

Le mécanisme `component_configs` existant (accumulateur par composant, introduit Mission 124, déjà étendu par M128) reste inchangé dans sa structure. Sur SDXL/FLUX, toute combinaison de `weight_dtype`/`train`/`stop_training_after`/`stop_training_after_unit` configurée pour `text_encoder_2` doit continuer à fusionner dans un seul objet nested `text_encoder_2`, sans écrasement mutuel — déjà garanti par le pattern `setdefault(component_key, {})[...] = value` existant. Sur SD1.5, aucune propriété `text_encoder_2` (ancienne ou M128) ne doit être émise. Les champs de stop-training M128 sont déjà conformes à ce contrat et ne doivent pas être réarchitecturés par cette mission.

## 12. Flow-matching — interactions métier préservées

M129 modifie **uniquement** le gating d'architecture des trois champs flow-matching, jamais leur interaction métier existante. En particulier : `dynamic_timestep_shifting=True` peut rendre `timestep_shift` sans effet côté moteur OneTrainer, mais le Domain continue de conserver `timestep_shift` et le translator continue de l'émettre indépendamment lorsque FLUX est l'architecture courante — comportement déjà en place, non modifié, non redocumenté par cette mission.

## 13. Domain / Manager

Hypothèse de travail forte, confirmée par le micro-audit : **aucune modification n'est nécessaire** dans `src/domain/` ni dans `src/managers/training_manager.py`. Les sentinelles Domain existantes (`""` pour les champs `str`, `None` + `_UNSET` déjà en place pour les champs `Optional[bool]`/`Optional[float]`) sont déjà exactement celles requises par ce contrat.

**Si l'implémentation découvre qu'une modification Domain ou Manager devient réellement nécessaire, la règle est : STOP avant toute modification, et rapporter la raison précise avant de poursuivre.** Aucune extension silencieuse de ce périmètre.

## 14. UNet / Transformer weight dtype — strictement hors périmètre

`unet_weight_dtype`/`transformer_weight_dtype` restent entièrement hors périmètre. Leur mécanisme de `_draft` (`_unet_weight_dtype_draft`/`_transformer_weight_dtype_draft`) est structurellement différent — deux champs Domain mutuellement exclusifs partageant un seul widget visible, pas un simple masquage d'un champ unique. Leur comportement de validation architecture actuel (rejet via `OneTrainerConfigError` en cas d'incompatibilité) reste **entièrement inchangé**. Une non-régression explicite doit être ajoutée aux tests (section 17, item K) pour verrouiller cette exclusion.

## 15. Dirty-state

Le changement manuel d'architecture continue de rendre la Training dirty, exactement comme aujourd'hui (`on_architecture_changed()` positionne `_dirty = True` indépendamment de tout reset). Le simple gating visuel automatique (`.setVisible()`) ne doit créer aucun dirty supplémentaire — déjà vrai aujourd'hui, confirmé par le micro-audit. Aucune nouvelle logique dirty-state n'est attendue ; la suppression des resets explicites réduit même le nombre de changements de widgets automatiques déclenchés pendant un changement d'architecture.

## 16. Tests existants à adapter

Le micro-audit a identifié neuf tests existants attendant aujourd'hui `OneTrainerConfigError` pour l'un des cinq champs M129. Ils doivent être réécrits pour prouver le nouveau contrat (configuration acceptée, clé incompatible omise du JSON, Domain inchangé) — jamais simplement supprimés ni vidés de leurs assertions :

`tests/integration/test_onetrainer_config.py` :
- `test_sd15_rejects_text_encoder_2_weight_dtype`
- `test_sd15_rejects_text_encoder_2_train`
- `test_sd15_rejects_text_encoder_2_train_even_when_false`
- `test_sd15_rejects_timestep_distribution`
- `test_sdxl_rejects_timestep_distribution`
- `test_sd15_rejects_dynamic_timestep_shifting_even_when_false`
- `test_sdxl_rejects_timestep_shift`

`tests/integration/test_training_roundtrip.py` :
- `test_prepare_config_surfaces_an_incompatible_train_field_as_a_critical_error`
- `test_prepare_config_surfaces_an_incompatible_flow_matching_field_as_a_critical_error`

Deux cas supplémentaires nécessitent une restructuration plutôt qu'une simple réécriture :

- **`test_incompatible_flow_matching_field_error_names_the_offending_field`** ne peut plus utiliser un champ M129 comme exemple d'erreur d'architecture — rediriger sa responsabilité vers un cas qui continue réellement de lever (`unet_weight_dtype`/`transformer_weight_dtype`, section 14), si cela correspond encore à son intention ; si son nom devient factuellement faux après redirection, le renommer/restructurer proprement plutôt que de conserver un nom trompeur.
- **`test_switching_flux_to_sd15_resets_transformer_and_text_encoder_2`** mélange une assertion hors périmètre (`transformer_weight_dtype`, comportement historique conservé) et une assertion en périmètre (`text_encoder_2_weight_dtype`, nouveau comportement persistant) — le scinder en deux tests à responsabilité unique plutôt que de modifier les deux attentes dans le même test.

Pendant l'implémentation, revérifier la liste exacte de tous les tests concernés avant toute modification — cette liste, établie par le micro-audit, n'est pas garantie exhaustive au caractère près.

## 17. Matrice minimale de tests M129

- **A.** SDXL, `text_encoder_2_weight_dtype=FLOAT_16` → switch SD1.5 → switch SDXL → `FLOAT_16` restauré (Domain + UI).
- **B.** SDXL, `text_encoder_2_train=False` → switch SD1.5 → switch SDXL → `False` restauré (Domain + UI).
- **C.** FLUX, les 3 champs flow-matching configurés → switch SDXL → switch FLUX → valeurs restaurées (Domain + UI).
- **D.** Save pendant architecture incompatible → reload → retour à l'architecture compatible → valeurs restaurées. Couvrir explicitement pour TE2 (dtype + train) et pour les 3 champs flow-matching.
- **E.** JSON : TE2 configuré + SD1.5 → clé `text_encoder_2` absente du JSON produit (si aucune autre donnée applicable pour ce composant).
- **F.** JSON : flow-matching configuré + SD1.5/SDXL → les 3 clés flow-matching absentes du JSON produit.
- **G.** Retour à une architecture compatible → le JSON contient de nouveau les valeurs persistées, identiques à avant le passage par l'architecture incompatible.
- **H.** TE2 : `weight_dtype` + `train` + stop-training M128 configurés simultanément → fusion correcte dans le même objet nested `text_encoder_2`, sans écrasement mutuel.
- **I.** Dirty-state : le hide/show automatique ne crée aucun dirty parasite au-delà du changement d'architecture lui-même (déjà dirty par ailleurs).
- **J.** Training sans valeur explicite sur les 5 champs → comportement historique inchangé (aucune clé émise, aucune régression).
- **K.** Non-régression : `unet_weight_dtype`/`transformer_weight_dtype` incompatibles avec l'architecture continuent de lever `OneTrainerConfigError` exactement comme avant cette mission.
- **L.** Non-régression : les protections `extra_overrides` existantes (clés structurées `text_encoder_2`/`timestep_distribution`/`dynamic_timestep_shifting`/`timestep_shift`) restent inchangées, indépendamment de l'architecture.

## 18. Tests à ne pas ajouter

Ne pas ajouter de nouvelle validation de valeurs qui n'existait pas avant cette mission. En particulier, ne pas ajouter un test du type « `timestep_distribution="INVALID"` doit lever, même sur architecture incompatible » — ce comportement n'existe pas aujourd'hui pour aucune architecture et ne doit pas être inventé par M129 (voir section 6). Si l'absence de validation structurelle est jugée problématique, elle doit être documentée comme dette séparée (section 19), jamais corrigée incidemment ici.

## 19. Dette de validation — documentée, hors périmètre

Finding du micro-audit, à conserver explicitement mais à ne pas traiter : les cinq champs de cette mission (et plus largement tout champ `*_weight_dtype`/`timestep_distribution`) ne possèdent aujourd'hui aucune validation structurelle de leur propre valeur dans le translator, contrairement à `stop_training_mode` (M128), qui a un enum dédié (`_STOP_TRAINING_MODE_VALUES`). M129 ne corrige pas cette absence de validation — elle ne fait que retirer l'erreur liée au gating d'architecture. Cette dette n'est pas régularisée dans `docs/PROJECT_CONTEXT.md`/`CHANGELOG.md` à ce stade ; sa conservation au niveau global sera décidée à la clôture de cette mission.

## 20. `extra_overrides`

Aucune protection existante n'est modifiée sauf preuve technique contraire découverte en implémentation. Les clés structurées concernées (`text_encoder_2`, `timestep_distribution`, `dynamic_timestep_shifting`, `timestep_shift`) sont déjà protégées par `_STRUCTURED_CONFIG_KEYS` — seule une non-régression est attendue (matrice section 17, item L), jamais une nouvelle règle.

## 21. Risques

- Changement volontaire de neuf tests existants (rejet → acceptation + omission) — à documenter explicitement comme changement de contrat assumé, jamais une réparation de bug de test.
- Interaction avec M128 : le mécanisme `component_configs` est partagé — toute régression y serait immédiatement visible dans les tests M128 existants (`test_stop_training_te2_*`), à revalider en non-régression sans modifier leur propre logique.
- Accumulation nested TE2 : risque d'écrasement mutuel entre `weight_dtype`/`train`/`stop_training_after(_unit)` si la garde d'admission est mal placée — à couvrir explicitement (item H).
- Save sous architecture incompatible : risque que la persistance ne survive pas à un cycle Save/reload si elle reposait implicitement sur un widget vivant — à couvrir explicitement (item D).
- Flow-matching : risque de modifier par erreur l'indépendance `dynamic_timestep_shifting`/`timestep_shift` en touchant au gating — à valider par non-régression sur les tests M126 existants.
- Dirty-state : risque de dirty parasite si une garde est mal placée en dehors du contrôle de signal existant — à couvrir explicitement (item I).
- `unet_weight_dtype`/`transformer_weight_dtype` : risque de régression accidentelle si la boucle de rejet dtype est modifiée trop largement au lieu d'être scindée précisément — à couvrir explicitement (item K).
- `extra_overrides` : risque de collision si la restructuration touche par erreur `_STRUCTURED_CONFIG_KEYS`/`_PROTECTED_CONFIG_KEYS` — à couvrir explicitement (item L).
- Compatibilité des projets historiques : une Training pré-M129 sans aucune de ces cinq valeurs configurées doit produire un JSON strictement identique à avant cette mission — à couvrir explicitement (item J).

## 22. Smoke — statut

Aucun smoke GPU n'est prévu ni requis pour l'acceptation fonctionnelle de M129. Justification : cette mission ne modifie aucun modèle, aucun champ moteur, aucune sémantique d'entraînement OneTrainer réelle — elle modifie uniquement la persistance UI, le gating d'architecture, et la construction du dictionnaire de configuration. Validation entièrement déterministe par tests Domain/Manager/traduction/UI, sur le même principe que M128.

## 23. Baseline tests

Baseline reprise telle que clôturée par Mission 128, sans en modifier la formulation : **2662 tests collectés**, **458/458 tests ciblés M128 verts**. Cette baseline ne doit jamais être présentée comme « suite complète 2662/2662 OK » — plusieurs runs complets de clôture M128 ont rencontré des failures intermittentes dans des tests préexistants de timing/process lifecycle (`test_main_window_new_project.py`, `test_forge_lifecycle_manager.py`), hors diff M128, sans qu'aucun échec ciblé M128 n'ait jamais été observé. Cette nuance historique doit être préservée telle quelle dans tout futur document de clôture de M129.

## 24. Fichiers attendus à l'implémentation

A priori :

- `src/ui/pages/training_page.py`
- `src/engines/onetrainer_config.py`
- `tests/integration/test_onetrainer_config.py`
- `tests/integration/test_training_roundtrip.py`
- `docs/missions/MISSION_129.md` (mise à jour de clôture)

`src/domain/` et `src/managers/training_manager.py` non modifiés (section 13). Si d'autres fichiers deviennent nécessaires en cours d'implémentation : STOP avant toute extension de périmètre, et rapport de la raison avant de poursuivre.

## 25. Critères d'acceptation

- [x] Aucune perte de valeur sur un switch temporaire d'architecture, pour les 5 champs listés en section 5.
- [x] Persistance vérifiée après un cycle Save/reload effectué pendant que l'architecture incompatible est sélectionnée (section 8, matrice item D).
- [x] Omission JSON confirmée pour chaque champ lorsque l'architecture courante est incompatible (matrice items E/F).
- [x] Restauration JSON confirmée au retour vers une architecture compatible (matrice item G).
- [x] Aucun nouveau cache/draft/`previous_value` introduit — Domain unique source de vérité (section 7).
- [x] Aucune nouvelle validation de valeur ajoutée (section 6/18).
- [x] Mission 128 non régressée (mécanisme `component_configs`, cohabitation nested TE2, tests stop-training existants).
- [x] `unet_weight_dtype`/`transformer_weight_dtype` strictement inchangés, y compris leur comportement de rejet (matrice item K).
- [x] Dirty-state cohérent — aucun dirty parasite lié au seul gating visuel (matrice item I).
- [x] `extra_overrides` inchangé (matrice item L).
- [x] Aucun smoke GPU nécessaire pour la clôture fonctionnelle.

### Résultats réels

**Fichiers effectivement modifiés** (exactement le périmètre attendu, section 24) : `src/engines/onetrainer_config.py`, `src/ui/pages/training_page.py`, `tests/integration/test_onetrainer_config.py`, `tests/integration/test_training_roundtrip.py`. `src/domain/` et `src/managers/training_manager.py` confirmés inchangés — l'hypothèse forte de la section 13 s'est vérifiée exactement, aucune divergence rencontrée.

**Translator** : `_DTYPE_FIELDS_STILL_RAISING_ON_INCOMPATIBLE_ARCHITECTURE` (nouvelle constante) sépare désormais `text_encoder_2_weight_dtype` (bascule vers la garde d'émission) de `unet_weight_dtype`/`transformer_weight_dtype`/`text_encoder_weight_dtype`/`vae_weight_dtype` (rejet inchangé). `train_fields`/`_FLOW_MATCHING_FIELDS_BY_ARCHITECTURE` basculés en bloc vers la garde d'émission (aucun split requis — `text_encoder_train` n'a jamais déclenché ce rejet). Aucune nouvelle validation de valeur introduite.

**UI** : les resets explicites des 5 champs supprimés dans `_apply_architecture_to_dtype_fields()` ; `.setVisible()` conservé à l'identique ; aucun draft/cache introduit.

**Tests existants réécrits/restructurés** : les 9 tests identifiés par le micro-audit, plus `test_stop_training_te2_silently_omitted_on_sd15`'s voisin commentaire (mise à jour d'un commentaire devenu factuellement faux, section AB de `test_onetrainer_config.py`) et le split de `test_switching_flux_to_sd15_resets_transformer_and_text_encoder_2` en deux tests à responsabilité unique. Deux tests génériques d'erreur (`test_incompatible_train_field_error_names_the_offending_field`, `test_incompatible_flow_matching_field_error_names_the_offending_field`) supprimés avec justification explicite en commentaire — leur sujet exact (un rejet architecture pour un champ M129) n'existe plus, sans aucun champ restant vers lequel les rediriger.

**Tests nets ajoutés** : +10 (2662 → 2672 tests collectés) — +1 dans `test_onetrainer_config.py` (137 → 138, après -2 supprimés/+3 ajoutés), +9 dans `test_training_roundtrip.py` (321 → 330). Couvrent la matrice A–L complète, y compris la preuve explicite `dynamic_timestep_shifting=False` survivant un aller-retour SD1.5↔FLUX (item M), et deux scénarios Save-sous-architecture-incompatible-puis-reload-complet (`update_trainings()`) pour TE2 et flow-matching (item D), au-delà d'un simple aller-retour de widgets en session.

**Ciblé** : `test_onetrainer_config.py` + `test_training_roundtrip.py` — **468/468 verts**.

**Suite complète** : une seule exécution, **2672/2672, OK, exit 0** — aucune failure, aucun flake observé sur ce run (ni dialog_guard, ni Forge lifecycle). Conformément à la consigne de ne pas boucler à la recherche d'un run vert, une seule exécution a été effectuée ; ce résultat ne doit pas être extrapolé comme une garantie d'absence permanente des flakes déjà documentés (M126/M127/M128).

**Smoke** : aucun exécuté, conformément à la section 22 — aucune sémantique moteur OneTrainer modifiée.

**Écarts par rapport au contrat initial** : aucun. Le mécanisme translator anticipé en section 10 (réutilisation des ensembles `allowed_*` existants, split isolé au seul champ dtype concerné) s'est vérifié exactement tel qu'audité — aucune surprise, aucune extension de périmètre, aucune modification Domain/Manager.

## 26. Hors périmètre strict de M129

`unet_weight_dtype`/`transformer_weight_dtype` (section 14) ; toute nouvelle validation structurelle de valeur pour l'un des 5 champs ou pour tout autre champ dtype/flow-matching (section 6/18/19, dette documentée séparément) ; réarchitecture du mécanisme `component_configs` ; modification de la sémantique d'interaction `dynamic_timestep_shifting`/`timestep_shift` (section 12) ; toute modification Domain/Manager sans découverte technique préalable rapportée (section 13) ; `QuantizationConfig` complet ; offloading avancé ; presets Training Toolkit ; Hardware-aware Training ; Training Preflight ; toute évolution de Forge/ComfyUI/Central LoRA Library.

## 27. Autorisation

Contrat validé par l'architecte à la suite de l'audit post-M128 (recommandation du candidat A) et du micro-audit technique en lecture seule qui a verrouillé la stratégie translator/UI, la liste exacte des tests à adapter, et la correction de contrat sur l'absence de nouvelle validation de valeur. Implémentation, tests, et clôture (commit/tag/Release) à mener dans les tours suivants, chacun sur validation explicite séparée, conformément au workflow de mission permanent (`CLAUDE.md`).
