# Mission 131 — Training UI Dtype Harmonization & Safe Persistence

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en attente de validation finale de l'architecte.** Rédigé à la suite de l'audit post-M130 (candidats de mission, priorisation) et du micro-audit technique en lecture seule qui l'a suivi (correspondance exacte des whitelists translator, contraintes OneTrainer réelles des formats avancés, mécanisme UNet/Transformer, TE2, bug de perte silencieuse démontré), tous deux validés explicitement par l'architecte avec une correction de périmètre importante : le Transformer UI expose **7** valeurs, pas 10 — les trois formats GGUF restent acceptés par le translator M130 mais ne sont **pas** proposés dans l'UI. Implémentation conforme à ce contrat, **+17 tests nets (2709 → 2726 tests collectés)**, tous les tests ciblés M131 verts (353/353 sur `test_training_roundtrip.py`), une suite complète unique exécutée : **2726 collectés, 2726 passés, 0 échoué** — aucun des deux flakes historiques (`ForgeLifecycleManagerRealProcessTest`, `dialog_guard`) ne s'est manifesté sur ce run précis, ce qui n'est jamais présenté comme leur résolution permanente. Aucun smoke GPU requis ni exécuté. Voir section "Résultats réels" en fin de document.

## 1. Contexte

Mission 130 a durci la validation de neuf champs structurés du translator (`src/engines/onetrainer_config.py::build_training_config()`) contre le vocabulaire réel d'OneTrainer, lu directement dans son code source installé — jamais le sous-ensemble actuellement exposé par l'UI de ce Toolkit. Cette décision (Contrat B) a révélé, sans le corriger (hors périmètre M130, documenté MISSION_130.md sections 6/7/8), un écart réel entre les six combos dtype de `TrainingPage` et les whitelists translator :

- `train_dtype_combo` propose `NFLOAT_4`, une valeur que le translator rejette pour ce rôle.
- Les cinq combos `*_weight_dtype` proposent `TFLOAT_32`, une valeur que le translator rejette pour tous les rôles weight_dtype.
- Aucun des six combos ne propose les formats avancés (`FLOAT_W8A8`/`INT_W8A8` pour UNet/Transformer, `GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT` pour Transformer) que le translator accepte pourtant pour ces composants.

L'audit post-M130 a proposé cette harmonisation comme candidat prioritaire (incohérence UI/translator introduite par M130 lui-même, périmètre déjà entièrement auditable, risque minime). Le micro-audit technique dédié a validé la correspondance exacte des listes, mais a établi une distinction cruciale que ce document formalise : **« vocabulaire structurellement accepté par le translator » n'équivaut pas à « option autonome sûre à exposer dans l'UI »**. Ce même micro-audit a également découvert, en traçant précisément `_load_training_parameters()`/`save_training_parameters()`, un **bug de perte silencieuse préexistant** : une valeur Domain non représentable dans un combo peut être remplacée par `""` au premier Save suivant un chargement, même si l'utilisateur n'a jamais touché le champ concerné. Mission 131 corrige les deux problèmes ensemble, car ils partagent la même cause structurelle (un combo qui ne peut représenter toute valeur Domain valide) et la même correction (un mécanisme de draft généralisé).

## 2. Objectif

Corriger l'écart entre les choix dtype proposés par `TrainingPage` et les choix réellement utilisables de façon autonome avec le pipeline Toolkit actuel, **et** éliminer le risque de perte silencieuse d'une valeur Domain dtype non représentable dans son combo. Mission strictement UI + persistence UI — aucune modification Domain/Manager/translator prévue (voir section 16 pour la clause STOP si l'implémentation découvre le contraire).

## 3. Contrat UI exact — listes par rôle

Les quatre listes ci-dessous remplacent l'actuelle `_DTYPE_UI_CHOICES` unique et partagée (`src/ui/pages/training_page.py:78`).

### 3.1 `TRAIN_DTYPE` UI — 4 valeurs

```
FLOAT_32
FLOAT_16
BFLOAT_16
TFLOAT_32
```

Identique à la whitelist translator `_TRAIN_DTYPE_VALUES` (`onetrainer_config.py:438`). `NFLOAT_4` disparaît de `train_dtype_combo`.

### 3.2 `TE1 / TE2 / VAE WEIGHT DTYPE` UI — 5 valeurs

```
FLOAT_32
BFLOAT_16
FLOAT_16
FLOAT_8
NFLOAT_4
```

Identique à la whitelist translator `_TE_TE2_VAE_WEIGHT_DTYPE_VALUES` (`onetrainer_config.py:450`). `TFLOAT_32` disparaît de `text_encoder_weight_dtype_combo`, `text_encoder_2_weight_dtype_combo`, `vae_weight_dtype_combo`.

### 3.3 `UNET WEIGHT DTYPE` UI — 7 valeurs

```
FLOAT_32
BFLOAT_16
FLOAT_16
FLOAT_8
NFLOAT_4
FLOAT_W8A8
INT_W8A8
```

Identique à la whitelist translator `_UNET_WEIGHT_DTYPE_VALUES` (`onetrainer_config.py:460`). `TFLOAT_32` disparaît ; `FLOAT_W8A8`/`INT_W8A8` apparaissent (nouveauté, voir section 5).

### 3.4 `TRANSFORMER WEIGHT DTYPE` UI — 7 valeurs (sous-ensemble sûr, PAS 10)

```
FLOAT_32
BFLOAT_16
FLOAT_16
FLOAT_8
NFLOAT_4
FLOAT_W8A8
INT_W8A8
```

**Identique à la liste UNet ci-dessus — ce n'est PAS la whitelist translator complète (10 valeurs, `_TRANSFORMER_WEIGHT_DTYPE_VALUES`, `onetrainer_config.py:469`).** Voir section 4 pour la justification de cet écart intentionnel.

## 4. Distinction UI / translator — pourquoi Transformer UI ≠ Transformer translator

Le translator M130 accepte 10 valeurs pour `transformer_weight_dtype` (les 7 ci-dessus + `GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT`). **Mission 131 n'expose que 7 de ces 10 dans l'UI.**

Les trois valeurs volontairement **non exposées** dans l'UI :

```
GGUF
GGUF_A8_FLOAT
GGUF_A8_INT
```

**restent structurellement valides côté translator.** Mission 131 ne retire **rien** à `_TRANSFORMER_WEIGHT_DTYPE_VALUES` ni à aucune autre constante de `src/engines/onetrainer_config.py` — le translator continue d'accepter ces trois valeurs exactement comme M130 les a validées. Seule l'UI ne les propose pas.

**Raison auditée (micro-audit technique, vérifiée directement dans le code OneTrainer installé)** : leur utilisation réelle par OneTrainer nécessite que le transformer soit chargé depuis un fichier `.gguf` pré-quantifié — `FluxModelLoader.py:126` applique `GGUFQuantizationConfig` via `from_single_file()` uniquement lorsque `weight_dtypes.transformer.is_gguf()` est vrai, un mécanisme qui suppose que le chemin résolu pointe vers un fichier réellement au format GGUF, pas vers le checkpoint diffusers standard (`black-forest-labs/FLUX.1-dev`). Toolkit ne modélise aujourd'hui aucun champ `transformer_model_name`/override de source de checkpoint distinct de `base_model_name` — sans ce champ compagnon, sélectionner GGUF dans l'UI produirait une configuration en apparence valide mais runtime-incomplète, menant probablement à un échec OneTrainer non anticipé par Toolkit. **Exposer ces trois valeurs maintenant recréerait exactement le problème que cette mission cherche à éliminer.** Elles resteront un candidat pour une future mission distincte, une fois qu'un mécanisme de sélection de checkpoint GGUF existera dans ce Toolkit.

## 5. `FLOAT_W8A8` / `INT_W8A8` — ajout justifié

Ajoutés aux listes UNet et Transformer (sections 3.3/3.4). Le micro-audit a établi qu'ils sont autonomes dans le contexte Toolkit actuel :

- Aucun format de checkpoint spécial requis — simple remplacement post-chargement de `nn.Linear` par `LinearW8A8` (`quantization_util.py::replace_linear_with_quantized_layers()`), le même mécanisme générique que les formats déjà exposés (`FLOAT_8`/`NFLOAT_4`).
- Seule contrainte réelle trouvée dans le code OneTrainer : `LinearInt8Function.backward()`/`LinearFp8Function.backward()` lèvent `NotImplementedError("...cannot be used for full finetuning")` si le gradient est demandé sur le poids lui-même (finetuning complet). **Cette contrainte est déjà satisfaite structurellement** : `training_method` reste hardcodé à `"LORA"` dans `build_training_config()` (`onetrainer_config.py:884`), jamais un paramètre, jamais `FINE_TUNE`. Mission 131 ne touche pas `training_method`.
- Aucune dépendance hardware/capability trouvée dans `DataType.py` pour ces deux valeurs.

## 6. Pas d'égalité globale UI ↔ translator — implication pour les tests

**Aucun test de contrat ne doit affirmer que toutes les listes UI sont exactement égales à leurs whitelists translator respectives — ce serait faux pour Transformer.** Les contrats attendus, par rôle :

- Train UI == `_TRAIN_DTYPE_VALUES` (égalité totale).
- TE/TE2/VAE UI == `_TE_TE2_VAE_WEIGHT_DTYPE_VALUES` (égalité totale).
- UNet UI == `_UNET_WEIGHT_DTYPE_VALUES` (égalité totale).
- Transformer UI == sous-ensemble explicite de 7 valeurs, **strict sous-ensemble** de `_TRANSFORMER_WEIGHT_DTYPE_VALUES` (10), jamais une égalité.
- `GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT` : présents dans `_TRANSFORMER_WEIGHT_DTYPE_VALUES` (translator) **et** absents de la liste UI Transformer — asymétrie intentionnelle, à prouver par un test dédié explicite (jamais une simple omission d'assertion).

## 7. Bug de perte silencieuse — description exacte

**État actuel démontré par le micro-audit, à corriger obligatoirement.**

`_load_training_parameters()` bloque les signaux (`field.blockSignals(True)`, `training_page.py:1243`, jusqu'à `blockSignals(False)` à la ligne 1413) pendant tout le chargement. Pour chaque combo dtype, le code appelle `combo.findData(value)` puis `setCurrentIndex(index if index != -1 else 0)`. Si `value` n'est pas dans la liste du combo, l'affichage retombe sur `"(non configuré)"` — sans écrire dans le Domain à cet instant précis (signaux bloqués).

**Le problème apparaît ensuite** : `save_training_parameters()` écrit, pour `train_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype`, directement `combo.currentData()` (`training_page.py:1836,1840-1842`) — qui vaut désormais `""`, puisque le combo n'a jamais été programmatiquement restauré à l'ancienne valeur. **Un Save déclenché par la modification d'un champ totalement différent (ex. `trigger_word`) écrase donc silencieusement l'ancienne valeur Domain en `""`.** Seuls `unet_weight_dtype`/`transformer_weight_dtype` échappent à ce risque aujourd'hui, car ils utilisent déjà un draft (`_unet_weight_dtype_draft`/`_transformer_weight_dtype_draft`) écrit indépendamment du combo affiché.

Ce bug est **préexistant** — il touche déjà, avant même M131, toute Training contenant une valeur avancée non proposée par l'UI actuelle (`FLOAT_W8A8`, `GGUF`, etc., si créée via project.json/API). M131 ne l'introduit pas, mais le retrait de `NFLOAT_4`/`TFLOAT_32` de certains combos rendrait le risque bien plus probable en pratique (des Trainings pré-M130 pouvaient légitimement contenir ces valeurs). **Corriger ce bug est une condition obligatoire de clôture de M131, pas une amélioration optionnelle.**

## 8. Drafts généralisés — principe

Étendre le pattern déjà existant pour `unet_weight_dtype`/`transformer_weight_dtype` aux quatre champs restants : `train_dtype`, `text_encoder_weight_dtype`, `text_encoder_2_weight_dtype`, `vae_weight_dtype`.

**Principe** : le draft représente la valeur Domain canonique même lorsque le combo ne peut pas l'afficher.

- **Au chargement** (`_load_training_parameters()`) : `draft = onetrainer_settings.get(field, "")`, inconditionnellement. Si cette valeur existe dans la liste du combo courant, l'afficher. Sinon, afficher `"(non configuré)"` tout en conservant le draft original en mémoire.
- **Au Save** (`save_training_parameters()`) : écrire le draft, jamais `combo.currentData()` directement, pour ces quatre champs — exactement le traitement déjà appliqué à `unet_weight_dtype`/`transformer_weight_dtype`.
- **Une sauvegarde déclenchée par un autre champ ne doit jamais écraser un draft dtype que l'utilisateur n'a pas explicitement modifié.**

## 9. Action utilisateur explicite — quand un draft peut changer

Un draft dtype ne doit changer que lorsqu'une action utilisateur réelle modifie le combo correspondant — concrètement, un `currentIndexChanged` réellement émis (jamais pendant `_load_training_parameters()`, dont les signaux restent bloqués). Ceci a une conséquence Qt précise, auditée et confirmée par exécution réelle : `QComboBox.setCurrentIndex()` (qu'il soit déclenché par du code ou par un clic utilisateur sur l'item déjà courant du menu déroulant) n'émet `currentIndexChanged` que si l'index change réellement — resélectionner l'item déjà actif n'émet rien.

Trois cas à distinguer explicitement, y compris dans les tests (section 15/19). Les cas 1 et 2 partent tous deux de l'état suivant : une ancienne Training contient `train_dtype="NFLOAT_4"` (une valeur non représentable dans `train_dtype_combo` depuis M131) ; après chargement, le draft vaut `"NFLOAT_4"` mais le combo affiche `"(non configuré)"` (l'index 0, faute de pouvoir représenter la valeur réelle) :

1. **Aucune action sur le champ** : l'utilisateur modifie uniquement `trigger_word` puis Save, sans toucher `train_dtype_combo`. → `train_dtype` reste `"NFLOAT_4"` dans le Domain.
2. **Sélection explicite d'une valeur valide** : l'utilisateur choisit `"FLOAT_16"` dans `train_dtype_combo` — l'index change réellement (de 0 vers celui de `FLOAT_16`), `currentIndexChanged` s'émet — puis Save. → le draft devient `"FLOAT_16"`, remplace `"NFLOAT_4"` dans le Domain.
3. **Sélection explicite de `"(non configuré)"`** : ce cas ne peut PAS continuer directement depuis l'état des cas 1/2 ci-dessus — le combo y affiche déjà `"(non configuré)"` (index 0), et recliquer ce même item déjà sélectionné ne change pas l'index, donc n'émet aucun `currentIndexChanged` ; la valeur legacy invisible reste alors préservée, exactement comme au cas 1. Ce cas suppose au contraire que le combo affiche déjà une valeur réellement représentée (par exemple immédiatement après le cas 2 ci-dessus, ou pour toute Training dont `train_dtype` est déjà une valeur valide) : l'utilisateur choisit alors explicitement `"(non configuré)"` — l'index change réellement, `currentIndexChanged` s'émet — puis Save. → le draft devient `""`, l'ancienne valeur affichée est volontairement et légitimement supprimée (ce n'est plus une perte silencieuse, c'est un choix explicite de l'utilisateur).

**Effacer une valeur legacy invisible (cas 1) avec l'UI actuelle** requiert donc de passer explicitement par une valeur réellement sélectionnée : `NFLOAT_4` legacy invisible → UI `"(non configuré)"` → choisir `FLOAT_16` (cas 2, le draft devient `"FLOAT_16"`) → choisir de nouveau `"(non configuré)"` (cas 3, le deuxième changement d'index est réel, le draft devient `""`). Ce n'est pas un défaut du contrat de sécurité : la propriété recherchée — qu'une valeur non représentable ne soit jamais supprimée sans une modification réelle du combo — reste entièrement satisfaite ; un simple reclic sur l'item déjà sélectionné ne constitue précisément pas une telle modification. Ceci n'introduit aucune dette UX ni aucune mission future : permettre l'effacement en un seul reclic nécessiterait de connecter ces combos au signal `activated` (qui s'émet même en resélectionnant l'item courant) en plus de `currentIndexChanged`, un changement de code délibérément hors périmètre de cette mission.

## 10. Prepare/Start avec valeur legacy — ne jamais neutraliser l'erreur M130

**Safe Persistence ne signifie pas rendre une ancienne valeur invalide valide.** Reprenant l'exemple de la section 9 (cas 1) : Domain `train_dtype="NFLOAT_4"`, UI `"(non configuré)"`, draft `"NFLOAT_4"` préservé. `Prepare Config`/`Start Training` doivent **continuer** à transmettre la valeur Domain réelle (`"NFLOAT_4"`, pas le draft ni l'état visuel du combo) au translator M130, qui doit **continuer** à lever `OneTrainerConfigError` tant que l'utilisateur n'a pas explicitement corrigé le champ (cas 2/3 de la section 9). Mission 131 ne doit jamais transformer silencieusement `"NFLOAT_4"` → `""` → défaut moteur pour faire disparaître l'erreur — même principe pour `"TFLOAT_32"` comme weight dtype de composant. Le pipeline `OneTrainerConfigError` → `QMessageBox.critical` déjà existant (M130) reste strictement inchangé et doit continuer à s'activer sur ces valeurs.

## 11. Valeurs avancées existantes — représentation, pas juste préservation

Une Training existante peut déjà contenir `unet_weight_dtype`/`transformer_weight_dtype` = `FLOAT_W8A8` ou `INT_W8A8`. Après M131, ces valeurs doivent être :

- **représentables** dans l'UI (présentes dans les listes UNet/Transformer, section 3.3/3.4) ;
- **sélectionnées correctement au chargement** (`findData()` les trouve, le combo les affiche réellement, pas juste un fallback) ;
- **survivantes au Save/reload** (round-trip complet).

Une Training contenant `transformer_weight_dtype` = `GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT` reste un cas différent et volontairement non résolu de la même façon : le translator accepte la valeur, l'UI ne la propose pas (section 4). Le draft doit préserver cette valeur lors d'un Save sans action utilisateur sur ce champ précis — elle ne doit jamais être silencieusement remplacée par `""` (exactement le mécanisme de la section 7/8, appliqué à ce cas précis).

## 12. Architecture switch — ne pas rouvrir M129

Le comportement historique de reset lors d'un changement réel d'architecture (SD1.5/SDXL ↔ FLUX) pour `unet_weight_dtype`/`transformer_weight_dtype` **reste inchangé**. Ce comportement (`_apply_architecture_to_dtype_fields()` avec `reset_incompatible=True`, qui vide le draft du champ principal devenu inactif lors d'un changement de rôle UNet↔Transformer) est un contrat Mission 129 préexistant et distinct du bug de la section 7 — M131 ne doit **pas** exploiter le nouveau système de drafts généralisé pour modifier cette sémantique. Les tests M129 existants couvrant ce contrat (`test_switching_sd15_to_sdxl_never_resets_unet_weight_dtype`, `test_switching_sdxl_to_flux_resets_unet_weight_dtype_and_never_resurfaces`, `test_switching_flux_to_sd15_still_resets_transformer_weight_dtype`, `test_switching_flux_to_sd15_hides_but_never_resets_text_encoder_2_weight_dtype`) doivent rester verts sans modification de leur assertion — une non-régression explicite doit le confirmer.

TE2 reste un mécanisme différent, inchangé par M131 : `text_encoder_2_weight_dtype_combo` est un widget dédié jamais partagé, jamais repeuplé — un changement SDXL/FLUX → SD1.5 masque le champ (`.setVisible(False)`) sans jamais réinitialiser sa valeur Domain ; au retour SDXL/FLUX, la valeur réapparaît automatiquement. Le vocabulaire cible de TE2 (liste section 3.2) est identique quelle que soit l'architecture où il est visible (SDXL ou FLUX) — aucun repeuplement dynamique n'est nécessaire pour ce combo, seule sa liste statique doit être corrigée.

## 13. `main_model_weight_dtype_combo` — solution minimale requise

Ce widget reste partagé entre UNet (SD1.5/SDXL) et Transformer (FLUX). **Point important** : avec les listes de la section 3, UNet UI et Transformer UI contiennent actuellement les **7 mêmes valeurs** — mais le code doit conserver une distinction sémantique explicite par rôle (deux constantes UI nommées séparément, section 14), pour ne pas recréer une liste globale unique qui masquerait le fait que ce sont deux contrats indépendants (susceptibles de diverger à l'avenir, ex. si une future mission ajoute un format spécifique à un seul des deux rôles).

**L'implémentation doit choisir la solution minimale qui préserve cette distinction sans introduire de comportement observable inutile.** Concrètement : si les deux listes UI effectives sont identiques aujourd'hui, un repeuplement dynamique complexe du combo à chaque changement d'architecture n'apporte aucune valeur observable et ne doit pas être ajouté artificiellement — mais le code doit référencer explicitement « la liste UNet » ou « la liste Transformer » selon `_main_model_dtype_field`, jamais une troisième liste fusionnée créée pour l'occasion. **Si l'implémentation retient malgré tout un repeuplement dynamique** (par exemple pour rester robuste à une future divergence), il doit impérativement suivre : `blockSignals(True)` → `clear()`/`addItem()` → restauration via `findData(draft)` avec le fallback existant (`index if index != -1 else 0`) → `blockSignals(False)` — afin de ne jamais laisser un `currentIndexChanged` transitoire écraser un draft pendant la reconstruction.

## 14. Structure UI — pas d'import des constantes privées du translator

Remplacer `_DTYPE_UI_CHOICES` par des listes locales explicites, définies dans `training_page.py` :

```
_TRAIN_DTYPE_UI_CHOICES
_TE_WEIGHT_DTYPE_UI_CHOICES        (réutilisable TE1 / TE2 / VAE)
_UNET_WEIGHT_DTYPE_UI_CHOICES
_TRANSFORMER_WEIGHT_DTYPE_UI_CHOICES
```

**`TrainingPage` ne doit pas importer les constantes privées `_...` du translator** (`_TRAIN_DTYPE_VALUES`, `_UNET_WEIGHT_DTYPE_VALUES`, etc.) pour construire ses combos — ce sont des couches strictement descendantes (Presentation → Managers → Domain → Infrastructure, CLAUDE.md), et ces symboles `_`-préfixés ne sont pas un contrat public du module translator. Les quatre listes UI ci-dessus sont dupliquées explicitement, avec un commentaire citant leur source (les whitelists M130), et leur correspondance (égalité totale pour Train/TE/TE2/VAE/UNet, sous-ensemble strict pour Transformer) est vérifiée par des tests de contrat dédiés (section 6), jamais par un couplage d'import direct.

## 15. Load / Save — ordre à auditer précisément à l'implémentation

L'implémentation doit vérifier soigneusement, avant de coder, l'ordre exact des opérations dans :

- `_load_training_parameters()` : signal blocking → initialisation des 6 drafts (valeur Domain brute, inconditionnelle) → repeuplement éventuel du combo partagé (section 13) → restauration de chaque combo via `findData(draft)` avec fallback → fin du signal blocking.
- `save_training_parameters()` : lecture des 6 drafts (jamais `combo.currentData()` pour les 4 champs concernés par cette mission) → `training_manager.update(...)`.

Objectif explicite : éviter (a) un écrasement silencieux d'un draft par un `currentIndexChanged` artificiel pendant un repeuplement, (b) un draft resté périmé (stale) après une action utilisateur réelle, (c) une différence de comportement entre le tout premier chargement d'une Training fraîchement créée et un reload d'une Training existante.

## 16. Domain / Manager / translator — inchangés, clause STOP

**Aucune modification prévue** dans `src/domain/`, `src/managers/`, `src/engines/onetrainer_config.py`. Mission 131 est une mission UI + persistence UI uniquement. **Si l'implémentation découvre qu'une modification dans l'un de ces trois emplacements est réellement nécessaire, elle doit STOPPER avant de modifier ce fichier et rapporter précisément pourquoi, avant toute autre action.**

## 17. Fichiers probables d'implémentation

- `docs/missions/MISSION_131.md` (ce document, mis à jour en fin de mission avec les résultats réels).
- `src/ui/pages/training_page.py` (listes UI par rôle, drafts généralisés, éventuel repeuplement du combo partagé).
- `tests/integration/test_training_roundtrip.py` (tests ciblés — c'est le fichier qui héberge déjà tous les tests UI/roundtrip de `TrainingPage`).
- Éventuellement un autre fichier de test UI déjà existant, uniquement si réellement nécessaire — à justifier explicitement si utilisé.

`docs/PROJECT_CONTEXT.md`/`CHANGELOG.md` restent hors périmètre de cette mission, réservés à la régularisation documentaire post-Release (précédent M124–M130).

## 18. Tests prévus

### 18.1 Test historique `test_nfloat_4_available_in_every_existing_dtype_combo` — devient faux, à reclasser

Ce test (`test_training_roundtrip.py:2988`) boucle sur les 5 combos y compris `train_dtype_combo` et affirme que `NFLOAT_4` y est présent — faux après M131. **Ne pas simplement supprimer cette couverture** : la remplacer par une couverture qui prouve explicitement :

- `NFLOAT_4` **absent** de `train_dtype_combo`.
- `NFLOAT_4` **présent** dans UNet, Transformer, TE1, TE2, VAE.

### 18.2 Test `test_existing_dtype_choices_unaffected_by_nfloat_4_addition` — conserver l'intention, étendre la couverture

Conserver l'assertion existante : `TFLOAT_32` reste valide dans `train_dtype_combo`. Ajouter la couverture manquante : `TFLOAT_32` **absent** de tous les combos component weight dtype (UNet, Transformer, TE1, TE2, VAE).

### 18.3 Tests W8A8 — nouvelle couverture

- UNet : `FLOAT_W8A8`/`INT_W8A8` présents dans `main_model_weight_dtype_combo` en rôle UNet.
- Transformer : `FLOAT_W8A8`/`INT_W8A8` présents dans `main_model_weight_dtype_combo` en rôle Transformer.
- Sélection réelle d'une de ces valeurs → Save → reload → valeur restaurée (round-trip complet, pas seulement présence dans la liste).

### 18.4 Tests GGUF — asymétrie intentionnelle

- Contrat explicite : `GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT` **absents** de la liste UI Transformer.
- **Ne pas modifier** les tests translator M130 (`test_onetrainer_config.py`) qui prouvent que ces trois valeurs sont structurellement acceptées par `build_training_config()` — cette acceptation translator reste intégralement inchangée.
- Test de safe persistence dédié : Domain `transformer_weight_dtype="GGUF"` → chargement UI → `"(non configuré)"` affiché → modification d'un champ sans rapport → Save → reload → Domain toujours `"GGUF"`.

### 18.5 Tests anti-perte-silencieuse — couverture minimale obligatoire

Pour chacun des cas suivants : chargement d'une valeur legacy non représentable → combo `"(non configuré)"` → modification d'un champ sans rapport → Save → reload → **valeur originale préservée** :

- `train_dtype` legacy invalide (ex. `"NFLOAT_4"`).
- `text_encoder_weight_dtype` legacy invalide (ex. `"TFLOAT_32"`).
- `text_encoder_2_weight_dtype` legacy invalide (ex. `"TFLOAT_32"`).
- `vae_weight_dtype` legacy invalide (ex. `"TFLOAT_32"`).
- `transformer_weight_dtype` = `"GGUF"` (non représenté dans l'UI, voir 18.4).

Puis, au moins un test doit prouver l'inverse — **action utilisateur explicite** sur le combo remplace volontairement l'ancienne valeur (les trois cas de la section 9), et un test doit prouver que `Prepare Config`/`Start Training` continuent de rejeter une valeur legacy réellement invalide via `OneTrainerConfigError` tant qu'elle n'a pas été explicitement corrigée (section 10).

### 18.6 Non-régression architecture M129

Confirmer explicitement que les tests M129 existants (section 12) restent verts sans modification de leur assertion.

## 19. Non-objectifs (hors M131, explicitement)

```
Support runtime GGUF complet
transformer_model_name / override de checkpoint
QuantizationConfig complet
Hardware / preflight
Presets
Extension UI optimizer
Extension UI scheduler
CUSTOM scheduler et ses champs compagnons
Forge
Fooocus
training_method (reste hardcodé "LORA")
Contrat de reset architecture UNet/Transformer (Mission 129, section 12)
```

Si l'implémentation constate qu'un de ces sujets est réellement nécessaire pour clore M131 proprement, cela doit être rapporté comme un STOP (section 16) ou comme une dette explicitement documentée à séparer — jamais silencieusement absorbé.

## 20. Smoke

**Aucun smoke GPU prévu.** M131 ne modifie ni le translator (`src/engines/onetrainer_config.py`), ni aucune sémantique runtime OneTrainer — uniquement `TrainingPage` et sa persistence UI. Cohérent avec le précédent établi par M124/M127/M128/M129/M130 (missions UI/translator-only, toutes closes sans smoke).

## 21. Baseline

État de référence exact au moment de la rédaction de ce contrat de mission (post-M130, avant toute implémentation M131) :

- **2709 tests collectés** (2672 à la clôture de Mission 129 + 37 nets ajoutés par Mission 130).
- Mission 130 : **505/505 tests ciblés verts**, une unique exécution complète de la suite : **2709 collectés, 2707 passés, 2 échoués** — les deux échecs correspondent aux flakes historiques déjà documentés (`ForgeLifecycleManagerRealProcessTest.test_stop_is_idempotent_on_running_owned`, `MainWindowInferencePendingResultGuardTest.test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure`), non reproduits en isolation (1/1 vert chacun).
- **Ne pas présumer** du nouveau total de tests collectés avant implémentation — il sera rapporté exactement une fois les tests M131 écrits (targeted, puis une seule full suite). Si un flake historique réapparaît sur cette full suite, il doit être classifié séparément (nom exact, comparaison aux flakes déjà documentés) — un rerun isolé confirmant 1/1 vert ne doit jamais être présenté comme la preuve que la full suite initiale était globalement verte.

## 22. Critères d'acceptation

- [x] `train_dtype` UI = exactement les 4 valeurs de la section 3.1.
- [x] `TE1`/`TE2`/`VAE` weight dtype UI = exactement les 5 valeurs de la section 3.2, pour chacun des trois combos.
- [x] `UNet` weight dtype UI = exactement les 7 valeurs de la section 3.3.
- [x] `Transformer` weight dtype UI = exactement les 7 valeurs sûres de la section 3.4 (pas 10).
- [x] `NFLOAT_4` absent de `train_dtype_combo`.
- [x] `TFLOAT_32` absent des 5 combos weight dtype.
- [x] `FLOAT_W8A8`/`INT_W8A8` présents dans UNet et Transformer, sélectionnables et persistants (round-trip Save/reload prouvé).
- [x] `GGUF`/`GGUF_A8_FLOAT`/`GGUF_A8_INT` absents de l'UI Transformer, mais toujours acceptés par le translator M130 (tests translator M130 non modifiés, un test UI dédié prouve l'asymétrie).
- [x] Aucune constante privée du translator (`_...`) importée par `training_page.py` — les contrats sont vérifiés par tests, pas par couplage d'import.
- [x] Toute valeur Domain dtype non représentable dans son combo (legacy invalide ou format avancé non exposé) est préservée sans perte silencieuse à travers un Save déclenché par un champ sans rapport, et à travers un reload.
- [x] Une action utilisateur explicite sur un combo dtype peut remplacer une ancienne valeur (valide ou non) — les trois cas de la section 9 sont distingués par les tests.
- [x] `Prepare Config`/`Start Training` continuent de rejeter, via `OneTrainerConfigError`, toute valeur Domain réellement invalide pour son rôle — y compris une valeur legacy préservée par le nouveau mécanisme de draft.
- [x] Le contrat d'architecture Mission 129 (reset UNet/Transformer lors d'un switch réel, préservation TE2) reste inchangé, prouvé par les tests M129 existants toujours verts sans modification.
- [x] `src/domain/`, `src/managers/`, `src/engines/onetrainer_config.py` restent inchangés, sauf STOP documenté et validé séparément (section 16).
- [x] Tests ciblés M131 verts.
- [x] Une suite complète exécutée, résultat rapporté avec les chiffres exacts (collectés/passés/échoués — jamais un raccourci du type « X/X »).
- [x] Aucun smoke GPU exécuté.

### Résultats réels

**Fichiers modifiés** : exactement les 2 fichiers de code attendus — `src/ui/pages/training_page.py` (4 listes UI locales par rôle remplaçant `_DTYPE_UI_CHOICES`, `_build_dtype_combo()` paramétré, 6 nouveaux drafts au total dont 4 nouveaux généralisant le pattern UNet/Transformer préexistant, 4 nouveaux handlers `_on_..._changed()`, `_load_training_parameters()`/`save_training_parameters()` adaptés) et `tests/integration/test_training_roundtrip.py` (imports étendus + nouveaux tests). Aucun fichier de test UI supplémentaire n'a été nécessaire. `docs/missions/MISSION_131.md` complète le diff. `src/domain/`, `src/managers/`, `src/engines/onetrainer_config.py`, `PROJECT_CONTEXT.md`, `CHANGELOG.md` confirmés inchangés (aucun STOP nécessaire — le périmètre UI + persistence UI s'est révélé suffisant, exactement comme anticipé section 1).

**`main_model_weight_dtype_combo`** : solution minimale retenue conformément à la section 7/13 — construit une seule fois depuis `_UNET_WEIGHT_DTYPE_UI_CHOICES` (7 valeurs), aucun repeuplement dynamique introduit puisque `_TRANSFORMER_WEIGHT_DTYPE_UI_CHOICES` contient actuellement exactement les 7 mêmes valeurs. Les deux constantes restent déclarées indépendamment (aucune dérivation de l'une à partir de l'autre) et un commentaire documente explicitement où un repeuplement réel (`blockSignals`/`clear`/`addItem`/`findData`) devrait être ajouté si les deux listes venaient un jour à diverger.

**Correction de test découverte pendant l'implémentation (pas un STOP, pas une anomalie produit)** : le test initial `test_explicit_selection_of_not_configured_clears_a_preserved_legacy_train_dtype_value` tentait de resélectionner `"(non configuré)"` alors que le combo l'affichait déjà (cas d'une valeur legacy non représentable) — Qt ne déclenche jamais `currentIndexChanged` pour une resélection du même index, donc ce scénario exact n'est pas une action utilisateur réellement réalisable en un clic. Corrigé en `test_explicit_selection_of_not_configured_clears_a_previously_configured_train_dtype_value`, qui part d'une valeur réellement configurée (`FLOAT_16`) avant de sélectionner explicitement `"(non configuré)"` — un scénario Qt réel, qui déclenche effectivement le signal. Aucune conséquence sur le contrat de préservation legacy lui-même (couvert séparément et intégralement par les tests de non-perte-silencieuse).

**Tests nets ajoutés** : **+17** (2709 → 2726 tests collectés), tous dans `tests/integration/test_training_roundtrip.py` (336 → 353) : 1 test historique reclassé (`test_nfloat_4_available_in_every_existing_dtype_combo` → `test_nfloat_4_absent_from_train_dtype_but_present_in_every_weight_dtype_combo`, sans perte de couverture), 1 test historique conservé tel quel (`test_existing_dtype_choices_unaffected_by_nfloat_4_addition`, intention toujours exacte), 17 tests nets ajoutés couvrant : le vocabulaire exact par rôle (4 tests, dont l'asymétrie Transformer 7/10 prouvée par soustraction d'ensemble plutôt que par un simple comptage), W8A8 (présence + 2 round-trips Save/reload UNet et Transformer), l'absence GGUF de l'UI Transformer, 5 tests anti-perte-silencieuse (train_dtype, TE1, TE2, VAE legacy invalides + Transformer GGUF non représentable), le remplacement explicite et l'effacement explicite d'une valeur préservée, et la préservation du rejet `OneTrainerConfigError` par `Prepare Config` pour une valeur legacy conservée.

**Tests ciblés** : **353/353** verts dans `test_training_roundtrip.py` (seul fichier de test modifié).

**Suite complète** : une unique exécution complète — **2726 collectés, 2726 passés, 0 échoué**, exit 0. Aucun des deux flakes historiques (`ForgeLifecycleManagerRealProcessTest.test_stop_is_idempotent_on_running_owned`, `MainWindowInferencePendingResultGuardTest.test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure`) ne s'est manifesté sur ce run précis — aucune reproduction isolée n'a donc été nécessaire. Cette absence n'est pas présentée comme la preuve d'une résolution permanente de ces deux anomalies intermittentes déjà documentées ailleurs (`docs/PROJECT_CONTEXT.md`).

**Non-régression M129** : les 4 tests d'architecture-switch existants (`test_switching_sd15_to_sdxl_never_resets_unet_weight_dtype`, `test_switching_sdxl_to_flux_resets_unet_weight_dtype_and_never_resurfaces`, `test_switching_flux_to_sd15_still_resets_transformer_weight_dtype`, `test_switching_flux_to_sd15_hides_but_never_resets_text_encoder_2_weight_dtype`) sont restés strictement inchangés et verts, sans aucune adaptation nécessaire.

**Écarts par rapport au contrat** : aucun — le contrat de MISSION_131.md a été suivi exactement, à l'exception de la correction de test ponctuelle documentée ci-dessus (scénario Qt irréalisable, sans impact sur la couverture réelle du contrat de sécurité).

## 23. Hors périmètre strict

Tout ce qui figure en section 19, sans exception. Aucune Mission 132 n'est présumée par ce document — la mission suivante sera déterminée par un nouvel audit, après clôture de M131.

## 24. Autorisation

Ce document formalise le périmètre validé par l'architecte à l'issue du micro-audit read-only post-M130. L'implémentation a été réalisée conformément à ce contrat, testée (voir "Résultats réels" ci-dessus), sans aucun staging/commit/tag/Release à ce stade — la clôture Git (commit/tag/push/Release) reste en attente d'une validation finale explicite et séparée de l'architecte, conformément au workflow permanent de ce projet (`CLAUDE.md`).
