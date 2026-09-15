# Mission 125 — TrainingPage Settings Audit & Basic/Advanced Reorganization (Phase 1)

> **MISSION IMPLÉMENTÉE ET VALIDÉE.** Contrat rédigé et figé avant implémentation, conformément aux 8 décisions d'architecture validées explicitement par l'architecte avant toute rédaction. Implémentée exactement selon ce document, aucune incompatibilité détectée pendant l'audit réel d'OneTrainer (section 3). Suite complète **2527/2527**, 0 régression. Commit(s), tag et Release : voir rapport de clôture.

## 1. Contexte

Après les Missions 120 (fondations `OneTrainerSettings`), 121 (precision/dtypes), 122 (optimizer discriminant) et 124 (Text Encoder training/Layer Filter), `TrainingPage` expose 20 réglages OneTrainer répartis sur 23 lignes de formulaire (`docs/PROJECT_CONTEXT.md`, item "Exposition progressive des réglages OneTrainer... Basic/Advanced/Presets", identifié dès Mission 101). Cet item documente explicitement, depuis Mission 101, qu'une évolution significative de `TrainingPage` doit être précédée d'un audit produisant une matrice exhaustive Réglage → SD1.5/SDXL/FLUX → Basic/Advanced → exposé/non exposé → automatique/réglable, avant toute nouvelle extension importante — jamais produite jusqu'ici.

Un symptôme concret a déjà été observé : le commit `c5c6850` (*Fix Training page vertical scrolling*, entre M121 et M122) a dû corriger un dépassement de hauteur de `TrainingPage` causé par la croissance de la section Advanced. La Mission 121 a par ailleurs déjà posé un mécanisme repliable réel (`self.advanced_settings_toggle`/`self.advanced_settings_container`, fermé par défaut) — non généralisé à l'ensemble du formulaire ni fondé sur une classification Basic/Advanced auditée : jusqu'ici, seuls les champs *postérieurs* à Mission 120 y ont été placés, par défaut chronologique et non par une analyse d'usage réel.

Mission 125 est la **Phase 1** de cet item : audit + matrice + réorganisation UI des réglages déjà implémentés, **sans** presets, **sans** hardware-awareness, **sans** nouveau réglage OneTrainer.

## 2. Décisions d'architecture validées par l'architecte (avant rédaction)

1. **Mécanisme Basic/Advanced** : zone Basic toujours visible + zone Advanced repliable fermée par défaut ; pas d'onglets. Le mécanisme Qt exact est laissé au choix de l'implémentation parmi les composants déjà utilisés dans le projet, sous réserve de : séparation visuellement claire, ouverture/fermeture facile, aucune perte de valeur au repli, compatibilité avec le scrolling existant.
2. **Portée de la matrice** : ne pas se limiter aux 20 réglages déjà exposés — auditer l'installation réelle `J:\Programmes\Onetrainer` et cartographier aussi les principaux réglages pertinents pour un entraînement complet SD1.5/SDXL/FLUX qui ne sont pas encore exposés. Ces derniers sont **cartographiés uniquement**, jamais implémentés pendant M125.
3. **Item 411** : M125 constitue sa Phase 1 (audit, matrice, classification, réorganisation UI) — ne pas le considérer clos à la fin de cette mission.
4. **Presets et hardware-aware Training** : strictement hors périmètre (Recommended/Memory Efficient/Custom, détection GPU, adaptation automatique, Training Preflight).
5. **Principe UX de classification** : Basic = ce qu'un utilisateur doit normalement comprendre/modifier pour un entraînement courant ; Advanced = technique, spécialisé, architecture-specific ou rarement modifié — jamais "ce qui a été ajouté en premier historiquement".
6. **Périmètre fonctionnel** : réorganisation UI uniquement des réglages déjà implémentés. Aucun changement volontaire au Domain, à `TrainingManager`, à `build_training_config()`, à la configuration générée, au pipeline d'exécution, ni à l'environnement OneTrainer/CUDA/PyTorch. Les valeurs sauvegardées/générées doivent rester fonctionnellement équivalentes avant/après M125.
7. **Smoke** : pas de smoke GPU/OneTrainer réel si l'audit confirme l'absence de changement à la logique Training/configuration (confirmé — voir section 7). Validation Qt réelle requise à la place.
8. **Documentation** : créer ce document, corriger l'incohérence documentaire de l'item 411 dans `PROJECT_CONTEXT.md` (progression M120→M121→M122→M124 jamais reflétée), implémenter, tester, valider, puis clôturer selon le workflow habituel si tout est vert.

## 3. Audit réel de l'installation OneTrainer

Source de vérité : `J:\Programmes\Onetrainer\modules\util\config\TrainConfig.py` (`config_version=10`, identique à `_AUDITED_CONFIG_VERSION` déjà audité et utilisé par `src/engines/onetrainer_config.py` depuis Mission 097 — **aucune dérive détectée**, le contrat existant reste valide). Recommandations par architecture croisées avec les presets officiels réellement livrés par cette installation : `training_presets/#sd 1.5 LoRA.json`, `training_presets/#sdxl 1.0 LoRA.json`, `training_presets/#flux LoRA.json` — les trois seuls presets `training_method=LORA` correspondant exactement aux trois architectures que Toolkit supporte.

Aucune incompatibilité avec le présent contrat n'a été détectée pendant cet audit — la clause d'arrêt de la section 12 du message d'autorisation ne s'applique pas.

### 3.1 Constat notable : FLUX diverge du défaut OneTrainer sur plusieurs axes

Le preset FLUX LoRA officiel configure explicitement `train_dtype=BFLOAT_16` (au lieu du défaut `FLOAT_16`), `transformer.weight_dtype=NFLOAT_4` et `text_encoder_2.weight_dtype=NFLOAT_4` (quantification 4 bits, **absente de `_DTYPE_UI_CHOICES`**), ainsi que `timestep_distribution=LOGIT_NORMAL` et `dynamic_timestep_shifting=true` (réglages de bruitage propres aux modèles à flow-matching, **totalement non exposés** aujourd'hui). Un LoRA FLUX produit aujourd'hui par Toolkit diverge donc du preset officiel sur ces axes, au-delà du seul Layer Filter déjà documenté (Mission 124, section 2.E). Ce n'est pas un défaut de M120-124 (hors périmètre à chaque fois) mais une confirmation concrète, chiffrée, de ce que l'item 411 anticipait déjà. Cartographié en section 5, non implémenté.

## 4. Matrice — réglages actuellement exposés par AI Studio Toolkit

Valeurs "SD1.5/SDXL/FLUX" = valeur par défaut réelle d'OneTrainer pour cette architecture, ou valeur du preset officiel `LORA` correspondant lorsqu'il diffère du défaut (signalé par *(preset)*).

| Réglage (Toolkit) | Champ OneTrainer | SD1.5 | SDXL | FLUX | Basic/Advanced | Auto/Réglable | Remarques |
|---|---|---|---|---|---|---|---|
| Architecture | `model_type` (discriminant) | — | — | — | **Basic** | Réglable | Discriminant Toolkit (`TRAINING_ARCHITECTURE_*`), pas un réglage OneTrainer au sens strict |
| Modèle de base | `base_model_name` | `stable-diffusion-v1-5/...` | `stabilityai/stable-diffusion-xl-base-1.0` | `black-forest-labs/FLUX.1-dev` | **Basic** | Réglable | L'utilisateur fournit son propre checkpoint local ; ces valeurs sont les défauts HuggingFace d'OneTrainer, pas une recommandation Toolkit |
| Résolution | `resolution` | `512` | `1024` | `768` *(preset)* | **Basic** | Réglable | |
| Epochs | `epochs` | `100` (défaut global) | idem | idem | **Basic** | Réglable | Aucun des 3 presets LoRA ne surcharge — dépend surtout de la taille du Dataset, aucune valeur universelle |
| Learning rate | `learning_rate` | `0.0003` *(preset)* | `0.0003` *(preset)* | `0.0003` *(preset)* | **Basic** | Réglable | Convergence remarquable des 3 presets officiels |
| LoRA rank | `lora_rank` | `16` (défaut global) | idem | idem | **Basic** | Réglable | Non surchargé par les 3 presets |
| LoRA alpha | `lora_alpha` | `1.0` (défaut global) | idem | idem | **Basic** | Réglable | Non surchargé par les 3 presets |
| Trigger word | *(aucun — Toolkit uniquement)* | — | — | — | **Basic** | Réglable | Injecté dans le contenu des captions, jamais un champ OneTrainer dédié (contrat établi Mission 097) |
| Batch size | `batch_size` | `1` (défaut global) / `4` *(preset)* | idem | idem | **Basic** | Réglable | Les 3 presets recommandent `4` ; Toolkit n'affiche aujourd'hui aucune valeur suggérée pour "non configuré" |
| Gradient accumulation steps | `gradient_accumulation_steps` | `1` (défaut, non surchargé) | idem | idem | **Advanced** *(reclassé — voir §6)* | Réglable | Réglage mémoire/technique, jamais surchargé par un preset officiel |
| Learning rate scheduler | `learning_rate_scheduler` | `CONSTANT` (défaut, non surchargé) | idem | idem | **Advanced** *(reclassé — voir §6)* | Réglable | |
| Training dtype | `train_dtype` | `FLOAT_16` (défaut) | `FLOAT_16` (défaut) | `BFLOAT_16` *(preset)* | Advanced | Réglable | Seul FLUX diverge du défaut |
| UNet/Transformer weight dtype | `unet.weight_dtype` / `transformer.weight_dtype` | `FLOAT_16` *(preset)* | `FLOAT_16` *(preset)* | `NFLOAT_4` *(preset)* | Advanced | Réglable SD1.5/SDXL — **`NFLOAT_4` absent de `_DTYPE_UI_CHOICES`, non réglable pour FLUX** | Écart réel documenté §3.1 |
| Text Encoder weight dtype | `text_encoder.weight_dtype` | `FLOAT_16` *(preset)* | `FLOAT_16` *(preset)* | `BFLOAT_16` *(preset)* | Advanced | Réglable (les 3 valeurs sont déjà dans `_DTYPE_UI_CHOICES`) | |
| Text Encoder 2 weight dtype | `text_encoder_2.weight_dtype` | n/a (pas de TE2) | `FLOAT_16` *(preset)* | `NFLOAT_4` *(preset)* | Advanced | Réglable SDXL — **`NFLOAT_4` non réglable pour FLUX** | Même écart que ci-dessus |
| VAE weight dtype | `vae.weight_dtype` | `FLOAT_32` | `FLOAT_32` | `FLOAT_32` | Advanced | Réglable | La valeur "non configurée" de Toolkit correspond déjà à la valeur recommandée pour les 3 architectures |
| Text Encoder train | `text_encoder.train` | `true` (défaut, non gelé) | `false` *(preset — gelé)* | `false` *(preset — gelé)* | Advanced | Réglable | |
| Text Encoder 2 train | `text_encoder_2.train` | n/a | `false` *(preset — gelé)* | `false` *(preset — gelé)* | Advanced | Réglable | |
| LoRA layer filter (`ATTN_MLP`) | `layer_filter`/`layer_filter_regex` (traduits, jamais `layer_filter_preset`) | `attentions` *(preset "attn-mlp")* | `attentions` *(preset "attn-mlp")* | *(aucun override officiel — transformer entraîné en entier)* | Advanced | Réglable | `ATTN_MLP` pour FLUX reste une capacité Toolkit, jamais une reproduction du preset officiel (déjà documenté Mission 124) |
| Optimizer | `optimizer.optimizer` | `ADAMW` (défaut, non surchargé) | idem | idem | Advanced | Réglable (3 choix UI sur 43 valeurs réelles) | |

## 5. Matrice — principaux réglages OneTrainer pertinents non encore exposés

**Cartographiés uniquement — aucune implémentation dans cette mission.** Sert de contrat pour éviter d'ajouter ces réglages un par un sans vision d'ensemble dans une future mission.

| Réglage OneTrainer | Champ(s) | SD1.5 | SDXL | FLUX | Basic/Advanced pressenti | Auto/Réglable pressenti | Remarques |
|---|---|---|---|---|---|---|---|
| Gradient checkpointing | `gradient_checkpointing` | `ON` (défaut) | idem | idem | Advanced | Réglable | Compromis vitesse/VRAM direct, pertinent pour le futur besoin hardware-aware (item 441) |
| EMA | `ema`/`ema_decay`/`ema_update_step_interval` | `OFF` (défaut, non surchargé) | idem | idem | Advanced | Réglable | Plus pertinent en fine-tune complet qu'en LoRA ; déjà explicitement exclu du périmètre de Mission 124 |
| Quantification (couche transformer) | `quantization.layer_filter`/`layer_filter_preset`/`layer_filter_regex`/`svd_dtype`/`svd_rank` | n/a | n/a | Pertinent (checkpoints quantifiés 8/24 Go) | Advanced | Réglable | **Objet distinct** du `layer_filter` LoRA déjà exposé — même nom de champ, structure OneTrainer différente (`QuantizationConfig` vs `TrainConfig`), risque de confusion à documenter clairement si implémenté un jour |
| Distribution des timesteps (flow-matching) | `timestep_distribution`/`dynamic_timestep_shifting`/`timestep_shift` | n/a (non flow-matching) | n/a | `LOGIT_NORMAL`/`true`/`1.0` *(preset)* | Advanced, visible FLUX uniquement | Réglable | Écart réel documenté §3.1 — un LoRA FLUX Toolkit actuel diverge du preset officiel sur cet axe |
| Bruit (offset/min-max noising strength) | `offset_noise_weight`/`min_noising_strength`/`max_noising_strength` | `0.0`/`0.0`/`1.0` (défauts, non surchargés) | idem | idem | Advanced | Réglable | Aucun des 3 presets LoRA ne les surcharge |
| Réglages de perte | `clip_grad_norm`/`loss_weight_fn`/`mse_strength` | `1.0`/`CONSTANT`/`1.0` (défauts) | idem | idem | Advanced | Réglable | Rarement modifiés en usage courant |
| Entraînement masqué | `masked_training`/`unmasked_probability`/`unmasked_weight` | `False` (défaut) | idem | idem | Advanced | Réglable | Non pertinent tant que le Dataset Toolkit ne modélise aucun masque — prérequis Dataset avant toute implémentation |
| Échantillonnage pendant l'entraînement | `sample_after`/`samples`/`non_ema_sampling` | — | — | — | Advanced | Réglable | Déjà explicitement exclu du périmètre de Mission 124 ("échantillonnage avancé") |
| Sauvegarde/backup périodique | `backup_after`/`rolling_backup`/`save_every`/`continue_last_backup` | `backup_before_save=True` forcé par Toolkit | idem | idem | — | **Automatique** | Déjà un choix Job-owned établi (Missions 097/100) — periodic save désactivable par défaut ; ne doit pas devenir un réglage utilisateur sans nouvelle décision explicite |
| Chemins internes | `workspace_dir`/`cache_dir`/`debug_dir`/`concept_file_name`/`output_model_destination` | — | — | — | — | **Automatique, protégé** | Déjà dans `_PROTECTED_CONFIG_KEYS` — ne doit jamais devenir réglable |
| Multi-GPU | `multi_gpu`/`device_indexes` | `False` (défaut) | idem | idem | — | Non pertinent | Toolkit ne modélise aucune notion de job multi-GPU aujourd'hui |
| Dataloader / bucketing / cache latents | `aspect_ratio_bucketing`/`latent_caching`/`dataloader_threads` | `True`/`True`/`2` (défauts) | idem | idem | Advanced | Réglable | Défauts déjà adaptés à l'usage courant, faible priorité |
| Compilation (torch.compile) | `compile` | `False` (défaut) | idem | idem | Advanced | Réglable | Expérimental, non surchargé par les 3 presets |
| Variantes PEFT (LoHa/LoKr/OFT/DoRA) | `peft_type`/`lokr_*`/`oft_*`/`lora_decompose*` | `LORA` (Toolkit ne supporte que LoRA) | idem | idem | — | **Décision architecturale distincte** | `training_method="LORA"` est un choix figé de Toolkit (Mission 097) — étendre à d'autres PEFT types n'est pas un simple ajout de champ, nécessite son propre audit dédié |
| Text Encoder layer skip / séquence | `text_encoder_layer_skip`/`text_encoder_2_sequence_length` | `0`/n/a | `0`/`77` (défaut) | `0`/n/a | Advanced | Réglable | Niche, faible priorité |
| Embeddings additionnels | `embedding`/`additional_embeddings` | — | — | — | — | Non implémenté | Déjà explicitement exclu du périmètre de Mission 124 ("Additional Embeddings") |

## 6. Classification Basic/Advanced retenue pour les réglages déjà implémentés

Appliquant strictement le principe UX de la section 2.5 (Basic = compréhension/modification normale pour un entraînement courant ; Advanced = technique/spécialisé/rarement modifié) :

- **Reste en Basic** (9 champs, inchangé) : Modèle de base, Architecture, Résolution, Epochs, Learning rate, LoRA rank, LoRA alpha, Trigger word, Batch size — tous des paramètres qu'un utilisateur doit obligatoirement comprendre pour lancer n'importe quel entraînement.
- **Reclassé de Basic vers Advanced** (2 champs) :
  - **Gradient accumulation steps** — un réglage mémoire/technique (simuler un batch effectif plus grand) que la majorité des utilisateurs n'a pas besoin de comprendre pour un entraînement courant ; regroupé avec la section Precision/Memory existante.
  - **Learning rate scheduler** — un réglage d'optimisation spécialisé, non surchargé par aucun des 3 presets officiels (`CONSTANT` convient à l'usage courant) ; nouvelle sous-section "Training schedule".
- **Reste en Advanced** (9 champs, inchangé) : Training dtype, UNet/Transformer weight dtype, Text Encoder weight dtype, Text Encoder train, Text Encoder 2 weight dtype, Text Encoder 2 train, VAE weight dtype, LoRA layer filter, Optimizer — tous déjà correctement classés depuis leur mission d'origine (121/124/122).

## 7. Mécanisme UI retenu

Réutilisation stricte du mécanisme déjà existant depuis Mission 121 (`self.advanced_settings_toggle`/`self.advanced_settings_container`, `QToolButton` + `QWidget` replié par défaut, déjà couvert par des tests réels de non-régression dirty-state/géométrie) — **aucun nouveau composant Qt introduit**, conformément à la décision 1 (le mécanisme existant satisfait déjà les 4 critères : séparation visuelle claire, ouverture/fermeture facile, aucune perte de valeur au repli déjà prouvée par `test_toggling_advanced_settings_never_marks_dirty_or_changes_values`, compatibilité scrolling déjà prouvée par `test_opening_advanced_settings_increases_required_height_closing_recomputes_it`).

Changements strictement limités à :
1. Ajout d'un label "Basic settings" (gras, même style que "Precision / Memory"/"LoRA layers"/"Optimizer") juste avant `training_form`, pour une symétrie visuelle avec le toggle "Advanced settings" existant.
2. Déplacement des deux `addRow()` de `gradient_accumulation_steps_spinbox` et `learning_rate_scheduler_combo` de `training_form` vers `advanced_settings_form`, sous une nouvelle sous-section "Training schedule" (scheduler) et dans la sous-section "Precision / Memory" existante (gradient accumulation).
3. Aucune re-création de widget, aucun changement de signal/connexion, aucun changement de logique de sauvegarde/chargement — uniquement l'ordre des appels `addRow()` sur les deux `QFormLayout` déjà existants.

## 8. Fichiers concernés

- `src/ui/pages/training_page.py` — réorganisation UI décrite en section 7.
- `docs/missions/MISSION_125.md` — ce document.
- `docs/PROJECT_CONTEXT.md` — correction de l'incohérence documentaire item 411 (section 9 ci-dessous).
- `tests/integration/test_training_roundtrip.py` — tests ciblés étendus (section 10).

Aucun changement attendu dans `src/domain/onetrainer_settings.py`, `src/domain/onetrainer_optimizer_settings.py`, `src/domain/training.py`, `src/managers/training_manager.py`, `src/engines/onetrainer_config.py`.

## 9. Correction documentaire — item 411 de PROJECT_CONTEXT.md

L'entrée "Exposition progressive des réglages OneTrainer..." s'arrêtait à *« Mission 120 a posé la première fondation réelle de cette trajectoire, sans la clore »*, sans mentionner les Missions 121 (precision/dtypes), 122 (optimizer) ni 124 (Text Encoder training/Layer Filter) — sous-représentant la progression réelle sans être factuellement fausse (le besoin restait non clos). Mise à jour pour refléter la trajectoire complète M120→M121→M122→M124→**M125 (Phase 1 : audit, matrice, réorganisation Basic/Advanced)**, en conservant explicitement que les presets et le hardware-aware restent non traités.

## 10. Tests

Aucun changement de comportement fonctionnel n'étant introduit, les tests ciblés couvrent uniquement la réorganisation UI :

- Les deux champs reclassés (`gradient_accumulation_steps_spinbox`, `learning_rate_scheduler_combo`) sont bien à l'intérieur de `advanced_settings_container` (invisibles tant que replié, visibles une fois déplié) — nouveaux tests.
- Non-régression complète des tests déjà existants sur `advanced_settings_toggle`/`advanced_settings_container` (repli par défaut, non-dirty au toggle, géométrie) — doivent rester verts sans modification.
- Non-régression complète du round-trip Domain↔UI déjà couvert par M120/M121/M122/M124 pour ces deux champs et pour les 20 réglages au total (aucune perte de valeur, aucun changement de comportement de sauvegarde).
- Un test explicite : replier Advanced après avoir modifié un des deux champs reclassés ne perd pas la valeur en mémoire (widget non détruit, juste masqué) — avant `save_training_parameters()`.

**Résultats réels** : **2 tests nets nouveaux** (`test_gradient_accumulation_and_scheduler_are_reclassified_into_advanced` — preuve d'ancestry réelle sous `advanced_settings_container`, jamais sous `training_form` ; `test_reclassified_fields_keep_their_value_across_a_fold_unfold_cycle` — valeur conservée sur un cycle replié→déplié→replié). `test_training_roundtrip.py` seul : **246/246** (244 + 2), 0 régression sur les 244 tests préexistants (dont l'intégralité des tests `advanced_settings_*`/dtype/optimizer/Text Encoder/Layer Filter des Missions 120-124, tous verts sans aucune modification de leur propre code). Suite complète : **2527/2527** (2525 + 2), 0 régression.

## 11. Smoke réel

**Non nécessaire — confirmé.** L'audit confirme qu'aucun fichier de `src/domain/`, `src/managers/` ni `src/engines/onetrainer_config.py` n'a été modifié (voir §8) — la configuration générée pour OneTrainer est strictement identique avant/après M125. La validation Qt réelle remplaçant le smoke GPU a été exécutée via la suite de tests existante et étendue, contre une vraie `QApplication`/de vrais widgets (jamais de mock Qt) :

- **Basic visible immédiatement** : `training_form` reste hors du conteneur repliable, jamais masqué (non-régression des tests `TrainingPageOnetrainerParametersTest` déjà existants, tous verts).
- **Advanced fermé par défaut** : `test_advanced_settings_container_starts_folded` (préexistant, Mission 121) — toujours vert.
- **Ouverture/fermeture correcte** : `test_toggling_advanced_settings_never_marks_dirty_or_changes_values` (préexistant) — toujours vert.
- **Widgets Advanced accessibles et fonctionnels une fois ouverts, y compris les deux champs reclassés** : `test_gradient_accumulation_and_scheduler_are_reclassified_into_advanced` (nouveau) — ancestry réelle vérifiée via `QWidget.isAncestorOf()`.
- **Conservation des valeurs au repli/dépli** : `test_reclassified_fields_keep_their_value_across_a_fold_unfold_cycle` (nouveau) — cycle replié→déplié→replié, valeurs identiques à chaque étape.
- **Scrolling correct** : `test_page_content_is_wrapped_in_a_resizable_scroll_area`/`test_content_overflows_a_reduced_window_and_bottom_is_reachable_via_scroll`/`test_opening_advanced_settings_increases_required_height_closing_recomputes_it` (préexistants, avec un vrai `training_page.show()`+`QApplication.processEvents()` sur une fenêtre réelle 800×900) — tous verts sans aucune adaptation nécessaire.
- **Absence de régression visuelle évidente** : les 20 réglages restent tous présents et fonctionnels (aucune suppression, aucune duplication), seul leur regroupement Basic/Advanced a changé — confirmé par l'intégralité de la suite `test_training_roundtrip.py` (246/246).

## 12. Hors périmètre strict de M125

Presets (`Recommended`/`Memory Efficient`/`Custom`) ; détection automatique du GPU ; adaptation automatique aux capacités VRAM ; Training Preflight ; modification automatique des réglages selon le hardware ; tout nouveau réglage OneTrainer listé en section 5 (cartographié uniquement) ; support de PEFT types autres que LoRA ; refonte générale au-delà de la classification Basic/Advanced (pas de tri/recherche de champs, pas de personnalisation de l'ordre par l'utilisateur) ; toute modification de l'environnement CUDA/PyTorch/OneTrainer installé ; lancement réel d'un entraînement pendant cette mission.

## 13. Critères de clôture

- [x] Matrice des sections 4/5 produite à partir de l'audit réel de l'installation OneTrainer.
- [x] `TrainingPage` affiche une séparation Basic/Advanced réelle et clairement justifiée (label "Basic settings" + réutilisation du toggle "Advanced settings" existant ; 2 champs reclassés selon le principe UX de la section 2.5, jamais selon leur ordre historique d'ajout).
- [x] Aucune valeur, aucun comportement de sauvegarde/chargement modifié pour les 20 réglages existants — confirmé par les 244 tests préexistants, tous verts sans modification.
- [x] Suite complète verte, nombre exact confirmé : **2527/2527** (2525 + 2 nets nouveaux).
- [x] Validation Qt réelle explicite (section 11) exécutée et documentée.
- [x] Item 411 de `PROJECT_CONTEXT.md` mis à jour pour refléter cette Phase 1, explicitement non close entièrement (presets, hardware-aware et réglages de la section 5 restent non traités).

## 14. Autorisation

Contrat validé par l'architecte (8 décisions d'architecture, section 2) avant toute implémentation. Implémentation, tests et validation Qt réelle exécutés conformément à ce document. Mission close.
