# Mission 163 — Protect Unsaved Renames in ModelsPage/WorkflowsPage

> **MISSION ENTIÈREMENT CLOSE — commit fonctionnel, tag et GitHub Release publiés.** `ModelsPage`/`WorkflowsPage` utilisent un patron commit-on-blur pour `name_edit` (`editingFinished` uniquement, aucun bouton Save, aucun suivi de brouillon) — `update_models()`/`update_workflows()` écrasaient inconditionnellement ce champ à chaque événement `WORKSPACE_SAVED`/`RENAMED`/`MODEL_*`/`WORKFLOW_*`, effaçant silencieusement un renommage en cours de frappe dès qu'un événement sans rapport survenait ailleurs dans le même Workspace (ex. un Training terminant en arrière-plan). Découvert par l'audit global post-Mission 162, priorisé #1, conçu READ-ONLY sur cinq rounds de revue architecte successifs, puis implémenté strictement dans le périmètre validé. Commit fonctionnel `231c82362778fd26855f9fe4861098271ea3dd77`, tag annoté `v0.2-mission163` (objet `93a58ccbcc9c23073a62e08b84683f9beb400f3b`, cible `231c82362778fd26855f9fe4861098271ea3dd77`), GitHub Release publiée manuellement par l'architecte.

## 1. Défaut initial

`src/ui/pages/models_page.py`/`src/ui/pages/workflows_page.py` — `name_edit = QLineEdit()` connecté uniquement à `editingFinished` (commit-on-blur), sans flag `_dirty` ni bouton Save. `update_models()`/`update_workflows()` appelaient inconditionnellement `self.name_edit.setText(active_name)` à chaque rafraîchissement, y compris pour des événements totalement sans rapport avec le champ en cours d'édition. `QLineEdit.setText()` n'émet jamais `editingFinished` — un texte tapé mais non encore commité (Entrée/perte de focus) était donc remplacé sans avertissement, sans dialogue, et sans aucune récupération possible.

## 2. Preuve empirique du chemin de déclenchement

Chemin tracé et vérifié : `WorkspaceManager.save()` (`src/managers/workspace_manager.py:197-210`) publie `WORKSPACE_SAVED` de façon synchrone et inconditionnelle après toute écriture réussie, quel que soit le Manager appelant — canal unique pour toute mutation Workspace persistée (Character, Dataset, LoRA, Training, Model, Workflow). `EventBus.publish()` (`src/core/event_bus.py:59-83`) est synchrone, itère les abonnés dans l'ordre d'enregistrement. `update_models`/`update_workflows` sont abonnées à ce canal au même titre que `dashboard_page.update_project`/`images_page.update_images` (`src/ui/main_window.py:333-345`), sans aucune protection dirty-state contrairement aux 7 autres pages à brouillon (Prompts/Characters/LoRA/Settings/Inference/Training/Datasets).

Déclencheur réellement atteignable, focus conservé, sans action de l'utilisateur sur une autre page : un Training démarré plus tôt se termine (`TrainingJobRunner.finished` → `TrainingManager.update_job_state()` → `WorkspaceManager.save()`) pendant que l'utilisateur tape dans `ModelsPage.name_edit`/`WorkflowsPage.name_edit`.

Vérifié empiriquement (scripts jetables scratchpad, `QTest.keyClicks`/`keyClick`/`mouseClick` réels sur des widgets réellement affichés, jamais un `signal.emit()` synthétique) pendant la conception :
- `editingFinished` se déclenche avant tout changement de sélection réel (clic souris).
- Un vrai dialogue `QMessageBox.critical()` ouvert depuis `rename_model()` ne provoque aucune récursion naturelle.
- `hasFocus()` n'est **pas** fiable après un vrai dialogue d'erreur — d'où le choix final de ne jamais fonder la réconciliation sur le focus (voir §5).

## 3. Conception retenue — trois états locaux, par Page, non factorisés

`_name_editor_owner_id` (identité pour laquelle `name_edit` a été chargé), `_name_editor_loaded_value` (valeur exacte chargée), `_renaming_in_progress` (opération de renommage en cours — distinct du dirty-state). Aucune connexion `textEdited` : la présence d'un brouillon est dérivée par comparaison directe (`name_edit.text() != _name_editor_loaded_value`), jamais par un flag « a été édité » qui resterait vrai même après un retour exact au texte d'origine.

## 4. Vérification d'identité au point d'écriture

`rename_model()`/`rename_workflow()` vérifient explicitement, avant tout appel à `update_name()` : l'objet actif existe réellement (`self.model_manager.active_model is not None`, jamais déduit de la seule présence d'un id) **et** son identité correspond à celle chargée dans l'éditeur (`_name_editor_owner_id == active_model.model_id`). Toute discordance (objet absent ou identité différente) recharge simplement l'éditeur sans jamais envoyer le texte affiché au Manager — garantie qui ne dépend d'aucun ordre d'événement Qt observé, contrairement à une version antérieure de la conception qui s'appuyait uniquement sur l'ordre empirique d'un clic souris.

`update_models()`/`update_workflows()` : la préservation du brouillon exige les trois conditions réunies — objet actif présent, identité correspondant à celle chargée, texte encore différent de la valeur chargée (`_has_unsaved_name_draft()`). Sur disparition ou changement d'identité (Workspace fermé/créé/ouvert, sélection différente), l'éditeur est rechargé normalement, `_name_editor_owner_id` explicitement remis à `None` en l'absence d'objet actif.

## 5. Réconciliation explicite, indépendante du focus

`_reload_name_editor()` est appelée dans un `finally` englobant l'appel Manager et le dialogue d'erreur éventuel, garantissant la réconciliation après succès, retour idempotent **ou** échec — jamais déduite d'un état de focus laissé par `QMessageBox.critical()` (empiriquement démontré non fiable, §2). Le comportement existant sur échec (message puis restauration de la valeur canonique après rollback) est conservé sans changement fonctionnel.

## 6. Protection contre la réentrance

`_renaming_in_progress` couvre l'appel Manager, le dialogue et la réconciliation finale (structure `try/finally` imbriquée) — un appel réentrant (ex. un second `editingFinished` pendant la boucle événementielle du dialogue) retourne immédiatement sans nouvelle écriture, nouveau dialogue ni réconciliation supplémentaire. La protection est libérée même si la réconciliation lève une exception (`finally` imbriqué le plus interne). Les callbacks `update_models()`/`update_workflows()` ne consultent jamais ce flag — le rafraîchissement général reste toujours autorisé, y compris en réentrance pendant un renommage réussi.

## 7. Commit-on-blur préservé

Aucune modification du modèle d'interaction existant — pas de bouton Save, pas de dialogue Save/Discard/Cancel ajouté, `editingFinished` reste l'unique mécanisme de commit. Aucune modification de `MainWindow`/Manager. Aucune factorisation entre les deux Pages — code strictement symétrique mais indépendant, conformément à la convention du dépôt de ne jamais transposer un précédent sans revalider chaque entité indépendamment.

## 8. Fichiers modifiés

**Production (2, exactement le périmètre validé)** :
- `src/ui/pages/models_page.py`
- `src/ui/pages/workflows_page.py`

**Tests (2)** :
- `tests/integration/test_model_roundtrip.py`
- `tests/integration/test_workflow_roundtrip.py`

## 9. Tests ajoutés

**+26 tests nets** (13 par Page, structurellement symétriques) dans `ModelsPageDirtyDraftProtectionTest`/`WorkflowsPageDirtyDraftProtectionTest` :
- `test_unrelated_workspace_saved_preserves_a_real_unsaved_draft` — le test principal, **vérifié échouer sur le code pré-correctif** (`'Alpha' != 'Alpha EDIT'`, stash Git temporaire des deux fichiers de production, production restaurée aussitôt après) puis **passer après correction**.
- `test_repeated_events_and_workspace_renamed_preserve_the_draft` — corrigé après revue : `_wire()` n'abonnait pas `update_models()`/`update_workflows()` à `WORKSPACE_RENAMED` (absent du tuple `WORKSPACE_EVENTS` partagé, volontairement non modifié pour ne pas affecter les autres classes de test de ce fichier). Abonnement réel ajouté localement à cette classe de test. Le test isole désormais `WorkspaceManager.rename()` (qui ne publie jamais `WORKSPACE_SAVED`, vérifié par lecture directe) d'un éventuel `WORKSPACE_SAVED` masquant, et trace explicitement que le callback de Page s'exécute bien pour cet événement précis (substitution de la référence dans `event_bus._subscribers`, pas de la seule reassignation d'attribut d'instance).
- `test_focused_clean_editor_reflects_a_domain_update`
- `test_return_to_original_name_before_commit_is_not_persisted`
- `test_synchronous_success_persists_exactly_once_and_shows_the_new_name`
- `test_failure_restores_canonical_value_independent_of_focus`
- `test_workspace_close_with_focused_draft_clears_editor_without_writing`
- `test_identity_change_via_real_click_never_transfers_or_misrenames_draft`
- `test_identity_change_without_prior_focus_loss_refuses_the_write` (défense en profondeur) — corrigé après revue : la version précédente appelait `Manager.select(beta_id)`, qui publie l'événement de sélection et déclenche un rafraîchissement réconciliant l'éditeur sur Beta **avant** `editingFinished` — aucune discordance ne subsistait réellement au point d'écriture testé. Remplacé par une construction directe et déterministe (`Manager.active_<entité>_id = beta_id`, sans passer par `select()`) : l'éditeur possède encore l'identité et le brouillon d'Alpha, l'objet actif est Beta, aucun refresh intermédiaire n'a eu lieu — la discordance est affirmée explicitement avant l'appel direct à `rename_*()` (jamais via `.emit()`), puis `update_name()` et la tentative de persistence sont comptés séparément et doivent valoir zéro.
- `test_no_active_object_is_a_no_op_and_editor_stays_empty`
- `test_enter_then_real_focus_loss_persists_only_once`
- `test_reentrant_rename_during_error_dialog_is_ignored` (réentrance forcée déterministe) — corrigé après revue : le mock de `WorkspaceStorage.save` est désormais capturé (`as save_mock`) et son `call_count` affirmé explicitement à `1`, en plus des comptages déjà présents sur `update_name()` et le dialogue.
- `test_reentrancy_guard_released_even_if_reconciliation_fails`

Événements Qt réels (`QTest.keyClicks`/`keyClick`/`mouseClick`) utilisés pour tout scénario reposant sur l'ordre réel de frappe/focus/clic — jamais un `signal.emit()` synthétique pour ces cas précis. Le test de réentrance déterministe complète ces tests, il ne les remplace pas.

## 10. Résultats

**Résultats antérieurs à cette correction de couverture** (exécutés avant les 3 corrections ci-dessus, conservés pour traçabilité) :
- Ciblés `ModelsPageDirtyDraftProtectionTest` + `WorkflowsPageDirtyDraftProtectionTest` : 26/26.
- **Suite complète : 2966 collectés/2966 passés, 0 échoué** (337.166s). Équation : 2940 (clôture Mission 162) + 26 nets ajoutés par Mission 163 = **2966**, cohérent.

**Résultats ciblés fraîchement exécutés après correction des 2 fichiers de test uniquement** (aucun changement de production, suite complète non relancée — non requise pour une correction de couverture de test sans changement de comportement) :
- `test_model_roundtrip.py` + `test_workflow_roundtrip.py` complets : **141/141** (nombre de tests inchangé : les 3 corrections modifient des corps de tests existants, aucun test net ajouté).
- Ciblés `ModelsPageDirtyDraftProtectionTest` + `WorkflowsPageDirtyDraftProtectionTest` : **26/26**.
- `git diff --check` : clean.
- Les deux fichiers de production (`src/ui/pages/models_page.py`, `src/ui/pages/workflows_page.py`) confirmés byte-identiques à la version déjà revue par l'architecte (comparaison directe des diffs avant/après cette étape). Aucun changement `MainWindow`/Manager.
- Démonstration avant/après conservée telle quelle pour le test principal (`test_unrelated_workspace_saved_preserves_a_real_unsaved_draft`, les deux pages) — non répétée à cette étape, aucun changement de production ne le justifiait.

## 11. Limitations connues, non closes par cette mission

- Le chemin du bouton Supprimer (perte de focus au clic) n'a pas été vérifié empiriquement de façon indépendante — extrapolation par analogie au mécanisme de clic sur la liste, structurellement identique mais non testé séparément.
- Un raccourci clavier global (ex. Ctrl+N) pourrait théoriquement déclencher `WORKSPACE_CREATED` sans perte de focus préalable sur `name_edit` — New/Open/Close restent explicitement hors périmètre de cette mission (décision architecte), donc non traités ; le garde d'identité empêche toute écriture erronée mais n'empêche pas la perte silencieuse du brouillon dans ce cas précis, exactement comme avant cette mission (aucune régression, pas une amélioration sur ce point).

## 12. Références Git (vérifiées lors de la publication)

- **Commit fonctionnel** : `231c82362778fd26855f9fe4861098271ea3dd77` (`Protect unsaved model and workflow renames`) — exactement 5 fichiers (`src/ui/pages/models_page.py`, `src/ui/pages/workflows_page.py`, `tests/integration/test_model_roundtrip.py`, `tests/integration/test_workflow_roundtrip.py`, `docs/missions/MISSION_163.md`).
- **Tag annoté** : `v0.2-mission163`, objet `93a58ccbcc9c23073a62e08b84683f9beb400f3b`, cible déréférencée `231c82362778fd26855f9fe4861098271ea3dd77` — vérifié identique en local et sur le remote au moment de la publication.
- **GitHub Release** : publiée manuellement par l'architecte, rattachée au tag `v0.2-mission163` — publication confirmée par l'architecte ; aucune vérification technique indépendante de la Release elle-même n'a été effectuée dans cette session (`gh` CLI indisponible, aucun jeton GitHub en variable d'environnement).
- **Tag précédent** : `v0.2-mission162` confirmé inchangé — objet `5107f4a0f3349ba2dd10260c4b2396a95af05252`, cible `1aaa82b6abddef679e5de25f04128df7a462c735`.
- Voir `CHANGELOG.md` (section Mission 163) et `docs/PROJECT_CONTEXT.md` ("Dernière mission terminée") pour la régularisation documentaire complète.
