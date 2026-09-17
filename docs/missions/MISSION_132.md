# Mission 132 — OneTrainer Timestep Distribution: Full UI Exposure & Safe Persistence

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en cours.** Les 7 valeurs translator-valides de `timestep_distribution` sont désormais exposées dans l'UI, avec un brouillon (`_timestep_distribution_draft`) généralisant le pattern Mission 131/121 pour préserver toute valeur legacy/invalide/future non représentable. Implémentation conforme à ce contrat, **+6 tests nets (2726 → 2732 tests collectés)**, tous les tests ciblés M132 verts (359/359 sur `test_training_roundtrip.py`), une suite complète unique exécutée : **2732 collectés, 2732 passés, 0 échoué** — aucun des deux flakes historiques (`ForgeLifecycleManagerRealProcessTest`, `dialog_guard`) ne s'est manifesté sur ce run précis, ce qui n'est jamais présenté comme leur résolution permanente. Aucun smoke GPU requis ni exécuté. Aucune modification de Domain/Manager/translator/runtime OneTrainer.

## 1. Contexte

L'audit post-Mission 131 a découvert que `timestep_distribution` (réglage flow-matching FLUX-only, introduit par Mission 126) souffre exactement de la même classe de défaut que celle corrigée par Mission 131 pour les 6 champs dtype — mais n'a pas été traité par M131, dont le périmètre était strictement limité aux dtypes.

Preuves relevées par lecture directe du code (aucune ne suppose, toutes vérifiées) :

- [`training_page.py:127`](../../src/ui/pages/training_page.py#L127) : `_TIMESTEP_DISTRIBUTION_UI_CHOICES = ("UNIFORM", "LOGIT_NORMAL")` — 2 valeurs seulement.
- [`onetrainer_config.py:553-563`](../../src/engines/onetrainer_config.py#L553) : `_TIMESTEP_DISTRIBUTION_VALUES` (durci par Mission 130) accepte réellement **7 valeurs** : `UNIFORM`, `SIGMOID`, `LOGIT_NORMAL`, `HEAVY_TAIL`, `COS_MAP`, `INVERTED_PARABOLA`, `BETA`.
- [`training_page.py:1463-1469`](../../src/ui/pages/training_page.py#L1463) : au chargement, `findData()` échoue pour toute valeur Domain hors des 2 choix UI → repli `setCurrentIndex(0)` (`UNIFORM`) — **sans aucun brouillon** (`_draft`), contrairement aux 6 champs harmonisés par Mission 131.
- [`training_page.py:1971`](../../src/ui/pages/training_page.py#L1971) : la sauvegarde lit `self.timestep_distribution_combo.currentData()` **directement**.
- [`training_page.py:674-676`](../../src/ui/pages/training_page.py#L674) : le combo est câblé sur le handler générique `_on_training_parameters_changed` (marqueur "dirty" seul), pas de handler dédié — état identique à celui des 6 champs dtype **avant** Mission 131.
- Aucun test de `test_training_roundtrip.py` n'exerce une valeur hors `{"", "UNIFORM", "LOGIT_NORMAL"}` pour ce champ — le trou n'est pas seulement présent, il est aussi non couvert.

Conséquence concrète : si `Training.onetrainer_settings.timestep_distribution` contient `SIGMOID` (ou toute autre des 5 valeurs non exposées, ou une valeur legacy/invalide), le prochain Save de **n'importe quel autre champ** de `TrainingPage` écrase silencieusement cette valeur par `"UNIFORM"`.

## 2. Objectif

1. Exposer les 7 valeurs translator-valides de `timestep_distribution` dans l'UI (au lieu de 2).
2. Garantir qu'aucune valeur Domain existante — représentable ou non dans le nouveau combo à 7 valeurs — ne puisse être écrasée silencieusement par un Save non lié à ce champ, en réutilisant le pattern de brouillon (`_draft`) déjà éprouvé par Mission 131/Mission 121.
3. Ne modifier ni le translator, ni le Domain, ni `TrainingManager`, ni aucune sémantique runtime OneTrainer.

## 3. Contrat UI exact — `TIMESTEP_DISTRIBUTION` — 7 valeurs

```
_TIMESTEP_DISTRIBUTION_UI_CHOICES = (
    "UNIFORM",
    "SIGMOID",
    "LOGIT_NORMAL",
    "HEAVY_TAIL",
    "COS_MAP",
    "INVERTED_PARABOLA",
    "BETA",
)
```

Ceci est une **égalité stricte** avec `_TIMESTEP_DISTRIBUTION_VALUES` du translator (contrairement au cas Transformer de Mission 131, ici il n'existe aucune exclusion volontaire — les 7 valeurs sont sans dépendance non modélisée, contrairement à GGUF qui exigeait un `transformer_model_name` absent du Domain). L'ordre exact d'affichage (ci-dessus, `UNIFORM` en premier comme valeur actuelle par défaut) reste à la discrétion de l'implémentation ; seul l'ensemble des 7 valeurs est contractuel.

## 4. Investigation préalable — le brouillon (`_draft`) reste-t-il nécessaire une fois les 7 valeurs exposées ?

**Réponse : OUI, le brouillon reste nécessaire**, malgré l'exposition exhaustive des 7 valeurs translator-valides. Preuve :

- `OneTrainerSettings.timestep_distribution` (`src/domain/onetrainer_settings.py:153`) est un simple `str = ""`, **sans énumération, sans validation indépendante** — exactement comme `train_dtype`/`text_encoder_weight_dtype`/`text_encoder_2_weight_dtype`/`vae_weight_dtype` avant Mission 131.
- `TrainingManager.update()` ne valide jamais la valeur (confirmé par lecture de `src/managers/training_manager.py`) — un appelant (test, script, ou une future fonctionnalité) peut y écrire n'importe quelle chaîne.
- Seul `build_training_config()` valide, et seulement au moment de préparer/lancer un Training (`onetrainer_config.py:1167`, qui lève `OneTrainerConfigError` pour toute valeur non reconnue — le commentaire du code cite lui-même l'exemple `timestep_distribution="NOT_A_DISTRIBUTION"`). Ni le Domain, ni le Manager, ni le chargement UI ne rejettent jamais une valeur invalide.
- Un `QComboBox` ne peut par construction représenter que les éléments de sa propre liste finie — quelle que soit l'exhaustivité de cette liste vis-à-vis du vocabulaire translator **actuellement connu**. Une valeur legacy (héritée d'un `project.json` édité à la main, d'une expérimentation, d'un futur ajout de vocabulaire côté OneTrainer non encore répercuté ici, ou simplement d'une faute de frappe tolérée par le Domain permissif) reste structurellement possible et non représentable.

Cette conclusion est cohérente avec Mission 131 elle-même : `train_dtype`/`text_encoder_weight_dtype`/`text_encoder_2_weight_dtype`/`vae_weight_dtype` sont, eux aussi, en égalité stricte avec leur whitelist translator respective — et ont pourtant reçu un brouillon, précisément pour cette même raison (Domain permissif, jamais parce que l'UI leur manquait une valeur translator-valide). `timestep_distribution` est structurellement dans la même situation que ces quatre champs, pas dans celle, plus étroite, d'UNet/Transformer (sous-ensemble volontaire).

**Conséquence directement opérationnelle pour l'implémentation** : ne pas se contenter d'étendre `_TIMESTEP_DISTRIBUTION_UI_CHOICES` à 7 valeurs et laisser `combo.currentData()` en lecture directe au Save — cela laisserait le bug de perte silencieuse intact pour toute valeur hors de ces 7 (par ex. une valeur invalide déjà présente dans un `project.json`, ou un futur ajout de vocabulaire translator).

## 5. Généralisation du brouillon — principe (réutilisation stricte du pattern M131/M121)

Un unique champ à ajouter, suivant exactement le pattern déjà généralisé quatre fois par Mission 131 :

1. Nouveau brouillon dans `__init__` : `self._timestep_distribution_draft = ""`.
2. Le combo est reconnecté à un handler dédié (au lieu du générique `_on_training_parameters_changed` seul) :
   ```python
   def _on_timestep_distribution_changed(self, _index=None):
       self._timestep_distribution_draft = self.timestep_distribution_combo.currentData()
       self._on_training_parameters_changed()
   ```
3. `_load_training_parameters()` : le brouillon est **toujours** initialisé depuis la valeur Domain, avant tout `findData()`/`setCurrentIndex()` :
   ```python
   self._timestep_distribution_draft = onetrainer_settings.get("timestep_distribution", "")
   timestep_distribution_index = self.timestep_distribution_combo.findData(
       self._timestep_distribution_draft
   )
   self.timestep_distribution_combo.setCurrentIndex(
       timestep_distribution_index if timestep_distribution_index != -1 else 0
   )
   ```
4. `save_training_parameters()` : `timestep_distribution=self._timestep_distribution_draft` (jamais `self.timestep_distribution_combo.currentData()` directement).

Aucune nouvelle abstraction : c'est la 5ᵉ occurrence du même mécanisme exact (après `unet_weight_dtype`/`transformer_weight_dtype` de Mission 121, et les 4 champs de Mission 131).

## 6. Action utilisateur explicite — même nuance Qt que Mission 131

`currentIndexChanged` ne se déclenche jamais lors d'une resélection d'un index déjà courant (comportement Qt, indépendant de ce Toolkit, déjà documenté et corrigé dans `MISSION_131.md` section 9). Conséquence identique ici : si `timestep_distribution_combo` affiche déjà `UNIFORM` par repli (valeur legacy invisible en dessous), un reclic sur `UNIFORM` ne déclenche pas le handler et ne modifie donc pas le brouillon — propriété de sécurité voulue, pas un défaut, à documenter de la même façon dans le rapport d'implémentation, sans réouvrir la question ni introduire le signal `activated`.

## 7. Architecture switch — ne pas rouvrir Mission 129

`timestep_distribution_combo`/`_label` sont déjà, exclusivement, `.setVisible()` par `_apply_architecture_to_dtype_fields()` (`training_page.py:1748-1759`, section "Flow-matching (FLUX)"), **jamais réinitialisés** lors d'un changement d'architecture — comportement déjà correct et conforme à Mission 129, à ne pas modifier. Le nouveau brouillon `_timestep_distribution_draft` ne doit **jamais** être ajouté à la liste des drafts réinitialisés par cette méthode (qui ne concerne, et doit continuer à ne concerner, que le couple mutuellement exclusif `unet_weight_dtype`/`transformer_weight_dtype` — voir `MISSION_131.md` section 12, même règle reconduite ici).

## 8. Load / Save — ordre à auditer précisément à l'implémentation

Même exigence que Mission 131 section 15 : vérifier que l'initialisation du brouillon a bien lieu **avant** `findData()`/`setCurrentIndex()` dans `_load_training_parameters()`, à l'intérieur de la fenêtre `blockSignals(True)`/`blockSignals(False)` déjà existante (le combo `timestep_distribution_combo` fait déjà partie du tuple `fields` bloqué pendant le chargement) ; et que `save_training_parameters()` lit exclusivement le brouillon, jamais `combo.currentData()`, pour ce champ.

## 9. Domain / Manager / translator — inchangés, clause STOP

Aucune modification attendue de `src/domain/onetrainer_settings.py`, `src/managers/training_manager.py`, ou `src/engines/onetrainer_config.py` — les 7 valeurs et leur validation existent déjà depuis Mission 130 ; le gating d'architecture existe déjà depuis Mission 126/129 ; seul `TrainingPage` doit changer. **Si l'implémentation découvre qu'une modification Domain/Manager/translator est réellement nécessaire, elle doit s'arrêter et remonter le constat avant de continuer**, comme pour Mission 131.

## 10. Fichiers probables d'implémentation

- `src/ui/pages/training_page.py`
- `tests/integration/test_training_roundtrip.py`
- `docs/missions/MISSION_132.md` (ce document, mis à jour avec les résultats réels après implémentation)

Hors périmètre : Domain, `TrainingManager`, translator OneTrainer, runtime OneTrainer, tout autre réglage Training non directement lié à `timestep_distribution`.

## 11. Tests prévus

1. **Contrat UI exact** : `timestep_distribution_combo` expose exactement les 7 valeurs de `_TIMESTEP_DISTRIBUTION_VALUES` (égalité stricte, set comparison), ni plus ni moins.
2. **Chargement correct de chacune des 7 valeurs** : pour chacune, seeder `training_manager.update(...)` puis vérifier que le combo affiche bien cette valeur après `_load_training_parameters()`.
3. **Round-trip/persistence** : sélection explicite de chacune des valeurs pertinentes (au moins une hors des 2 anciennement exposées, ex. `SIGMOID`), Save, reload, valeur inchangée dans le Domain.
4. **Save non lié ne modifie pas `timestep_distribution`** : seeder une valeur (y compris une valeur hors des 7, ex. legacy/invalide côté Domain) directement via le Manager, éditer un champ sans rapport dans l'UI, Save, vérifier que `training_manager.active_training.onetrainer_settings.timestep_distribution` est inchangé — c'est le test qui aurait échoué avant cette mission.
5. **Valeur non représentable (legacy/invalide) préservée** : reprend le test 4 avec une valeur structurellement absente des 7 (ex. une chaîne arbitraire), combo affichant le repli `UNIFORM`, confirmant que le brouillon — et non le combo — est la source de vérité au Save.
6. **Non-régression architecture-switch (Mission 129)** : un changement temporaire d'architecture (FLUX → SD1.5 → FLUX) masque/réaffiche le widget sans jamais réinitialiser la valeur Domain ni le brouillon — même scénario que les tests M129/M131 existants, appliqué à ce champ.
7. **Conservation des protections M131** : exécution complète de `test_training_roundtrip.py` pour confirmer l'absence de régression sur les 6 champs dtype déjà harmonisés.

## 12. Non-objectifs (hors M132, explicitement)

- Aucune modification du translator, du Domain, de `TrainingManager`.
- Aucune modification des dtypes (train/TE/TE2/VAE/UNet/Transformer) déjà traités par Mission 131.
- Aucune modification de `dynamic_timestep_shifting`/`timestep_shift` (champs voisins mais distincts, non concernés par cette découverte).
- Aucune modification du mécanisme d'architecture-switch (`_apply_architecture_to_dtype_fields()`) au-delà de la non-régression vérifiée.
- Aucune nouvelle abstraction générique de "champ à brouillon" — la 5ᵉ occurrence reste écrite explicitement, comme les 4 précédentes.

## 13. Smoke

**Aucun smoke GPU/OneTrainer requis, sous réserve de confirmation à l'implémentation.** Cette mission reste strictement UI/persistance : elle n'ajoute ni ne modifie aucune sémantique runtime OneTrainer, ni aucune traduction de configuration déjà validée par Mission 130 — seules les valeurs offertes en UI et la protection contre leur écrasement silencieux changent. Ce jugement doit être reconfirmé explicitement dans le rapport d'implémentation (comme Mission 131 l'a fait), pas seulement présumé ici.

## 14. Baseline

2726 tests collectés à la clôture de Mission 131 (353/353 ciblés M131 verts, full suite unique 2726/2726/0). Toute exécution complète de clôture de M132 doit être comparée à cette base, en conservant la formulation stricte déjà établie (jamais "X/X" sans le nombre exact, jamais "flakes résolus").

## 15. Critères d'acceptation

- [x] `timestep_distribution_combo` expose exactement les 7 valeurs translator-valides.
- [x] Un brouillon `_timestep_distribution_draft` est initialisé depuis le Domain à chaque chargement, avant tout `findData()`/`setCurrentIndex()`.
- [x] `save_training_parameters()` lit exclusivement le brouillon pour ce champ.
- [x] Une valeur Domain non représentable (legacy/invalide) survit à un Save non lié.
- [x] Le mécanisme d'architecture-switch (Mission 129) reste inchangé pour ce champ (masquage seul, jamais de reset, brouillon jamais ajouté à la liste réinitialisée).
- [x] Les protections apportées par Mission 131 pour les 6 champs dtype restent intactes (suite complète verte).
- [x] Aucune modification de Domain/Manager/translator.
- [x] Nécessité (ou non) d'un smoke confirmée explicitement dans le rapport d'implémentation.

### Résultats réels

**Fichiers modifiés** : exactement les 2 fichiers fonctionnels prévus (`src/ui/pages/training_page.py`, `tests/integration/test_training_roundtrip.py`) plus ce document — confirmé par `git diff --name-status` (aucune trace dans `src/domain/`, `src/managers/`, `src/engines/onetrainer_config.py`).

**Implémentation** : conforme section par section à ce document — `_TIMESTEP_DISTRIBUTION_UI_CHOICES` étendu à 7 valeurs (section 3), `_timestep_distribution_draft` ajouté et jamais inclus dans la liste de reset de `_apply_architecture_to_dtype_fields()` (section 7), handler dédié `_on_timestep_distribution_changed()` remplaçant le câblage générique, `_load_training_parameters()`/`save_training_parameters()` mis à jour exactement selon l'ordre décrit en section 5/8.

**Tests** : **+6 tests nets** (2726 → 2732 tests collectés) : `test_timestep_distribution_combo_exposes_exactly_the_seven_translator_values`, `test_each_of_the_seven_timestep_distribution_values_loads_correctly`, `test_newly_exposed_timestep_distribution_value_round_trips_through_reload`, `test_timestep_distribution_legacy_invalid_value_survives_unrelated_save_and_reload`, `test_explicit_selection_replaces_a_preserved_legacy_timestep_distribution_value`, `test_timestep_distribution_draft_survives_a_temporary_architecture_switch`. Les tests préexistants (Mission 126/129, dont le round-trip `LOGIT_NORMAL` et les tests d'architecture-switch) n'ont nécessité aucune modification et restent verts tels quels. **359/359 tests ciblés `test_training_roundtrip.py` verts.** Une unique suite complète exécutée : **2732 collectés, 2732 passés, 0 échoué** — aucun des deux flakes historiques ne s'est manifesté sur ce run précis, ce qui n'est jamais présenté comme leur résolution permanente. `git diff --check` : clean.

**Smoke** : confirmé non requis — aucune modification de `src/engines/onetrainer_config.py`, de Domain, de `TrainingManager`, ni d'aucune sémantique runtime OneTrainer. Le chemin de validation/gating d'architecture au moment de Prepare/Start reste exactement celui déjà établi par Mission 130/129.

**Écarts par rapport au contrat** : aucun. L'investigation de la section 4 (nécessité du brouillon malgré 7/7 valeurs exposées) s'est confirmée exactement comme prévu à l'implémentation — aucune anomalie ni dette nouvelle découverte.

## 16. Hors périmètre strict

Domain, `TrainingManager`, translator OneTrainer, runtime OneTrainer, tout réglage Training non directement lié à `timestep_distribution`, toute nouvelle abstraction générique de brouillon.

## 17. Autorisation

**Implémentée et testée.** Validée par l'architecte et par validation externe à chaque étape (rédaction, implémentation, clôture). Clôture Git (commit/tag/Release) en cours de traitement.
