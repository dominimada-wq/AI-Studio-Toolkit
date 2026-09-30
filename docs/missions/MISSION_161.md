# Mission 161 — Recover From Training Terminalization Persistence Failure

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `TrainingPage._on_job_finished()` (`src/ui/pages/training_page.py`) capturait déjà correctement `WorkspaceManagerError` en cas d'échec de persistence du résultat terminal d'un entraînement, mais effaçait ensuite son tracking Page (`_active_runner`/`_active_job_id`) **sans condition** — alors que `TrainingManager.update_job_state()` avait déjà correctement annulé la mutation (rollback Mission 100/068) et laissait le Job Domain `starting`/`running`. Résultat : `TrainingManager.has_active_job()` continuait de retourner `True` indéfiniment, alors que le processus réel était déjà et définitivement terminé — verrouillant New/Open/Rename/Close pour le reste de la session, sans aucune récupération possible autrement qu'en tuant le processus AI Studio Toolkit et en le relançant. Découvert par l'audit global post-Mission 160, priorisé et re-analysé en détail sur le code actuel.

## 1. Bug initial

Chaîne exacte : un vrai processus OneTrainer termine → `TrainingJobRunner._on_process_finished()` détermine `state` ∈ {`succeeded`, `failed`, `cancelled`} avec certitude (jamais deviné) et émet `finished` une seule fois (`_finished_emitted`, garde idempotente) → `TrainingPage._on_job_finished(state, error_message, final_output_path)` appelle `TrainingManager.update_job_state(self._active_job_id, state, ...)` → celle-ci mute le Job puis appelle `WorkspaceManager.save()` → si ce `save()` lève `WorkspaceManagerError` (disque plein, verrou antivirus, partage réseau interrompu), `update_job_state()` restaure exactement l'état précédent du Job (`previous = (state, final_output_path, error_message, ended_at)`) puis re-lève. Le code historique affichait alors un message d'erreur et effaçait `_active_runner = None` / `_active_job_id = None` sans condition.

## 2. Processus définitivement terminé, rollback Manager correct

Le rollback de `TrainingManager.update_job_state()` est intact et n'a jamais été la source du problème : il restaure fidèlement `(state, final_output_path, error_message, ended_at)` à leur valeur d'avant la mutation, garantissant que la mémoire du Domain reste toujours cohérente avec ce qui est réellement écrit sur disque (aucune divergence mémoire/disque, aucune corruption). Le Runner, lui, a déjà émis `finished` de façon définitive et idempotente (`_finished_emitted = True`) — aucun second signal ne viendra jamais, et `TrainingJobRunner.cancel()` sur ce même Runner est déjà un no-op garanti.

## 3. Incohérence Page/Domain

Le vrai défaut n'était donc jamais dans le Manager, mais dans la Page : elle effaçait son propre tracking (`_active_runner`/`_active_job_id`) comme si le Job était résolu, alors que le Domain — la seule source de vérité consultée par `has_active_job()` — continuait légitimement à dire `starting`/`running`. `TrainingManager.delete()` refusait alors la suppression de ce Training (`TrainingActiveError`, comportement correct et inchangé), mais surtout `is_training_active()`/`confirm_no_active_training()` bloquaient indéfiniment `new_project()`/`open_project()`/`rename_project()`/`closeEvent()` — un Job réellement mort continuait d'empêcher toute sortie normale de session, y compris la fermeture propre de l'application (Qt achemine X/Alt+F4 par le même `closeEvent()`, aucun chemin de fermeture alternatif n'existe). `cancel_training()` était lui-même un no-op immédiat (`_active_runner is None`), offrant aucune échappatoire.

## 4. Pourquoi un simple `return` est faux

Conserver `_active_runner`/`_active_job_id` référencés après l'échec (au lieu de les effacer) a été explicitement étudié et rejeté : le Runner a déjà émis son unique signal `finished` (`_finished_emitted = True`), donc `cancel_training()` dessus resterait un no-op garanti même si le bouton Cancel redevenait cliquable — un bouton actif qui ne fait rien est une régression UX, pas une solution. Cela ne répare rien côté Domain (`has_active_job()` reste `True` de toute façon) et bloquerait en plus `start_training()` (qui refuse tant que `_active_runner is not None`), empêchant même le contournement partiel déjà disponible aujourd'hui. Un simple `return` déplace l'incohérence sans jamais la résoudre.

## 5. Pourquoi le Domain n'est jamais forcé terminal

Aucune stratégie envisagée ne force artificiellement le Job vers un état terminal en mémoire sans confirmation de persistence réelle (option B explicitement rejetée dès la conception) : cela romprait la garantie stricte « mémoire == disque » déjà exploitée par tout le reste de ce Manager (rollback Mission 068/076/100/145) et par tous les autres appelants de `update_job_state()` (`_on_job_started()`, `_recover_stale_jobs()`). `update_job_state(job_id, TRAINING_JOB_STATE_UNKNOWN)` a aussi été explicitement écarté comme échappatoire (§ conception) : il appelle la même frontière `WorkspaceManager.save()` déjà cassée — aucune fiabilité supplémentaire, seulement une perte d'information déjà connue avec certitude.

## 6. Retry explicite

Sur `WorkspaceManagerError`, `_on_job_finished()` affiche désormais un dialogue (« Résultat non enregistré ») offrant `Réessayer` (`AcceptRole`, bouton par défaut) et `Continuer` (`RejectRole`). `Réessayer` retente exactement le même appel `update_job_state(self._active_job_id, state, **kwargs)` — même `job_id`, même `state`, même `final_output_path`/`error_message`, jamais altérés depuis la détermination du Runner — dans une boucle `while True` strictement itérative, jamais récursive. Chaque tentative exige un clic explicite de l'utilisateur ; aucun retry automatique/temporisé. En cas de succès, le chemin historique reprend intégralement (tracking nettoyé, `_refresh_job_controls()`, dialogue succès/échec historique, `TRAINING_JOB_STATE_CHANGED` publié naturellement par `update_job_state()` lui-même).

## 7. « Continuer » et Job différé

Si l'utilisateur choisit `Continuer` — ou ferme le dialogue via X/Escape, **vérifié empiriquement** comme se comportant strictement à l'identique (`clickedButton()` retourne `None`, jamais le bouton `Continuer` lui-même : `QMessageBox` n'assigne pas automatiquement un bouton `RejectRole` comme bouton d'échappement ; le code de production teste donc `is retry_button`, jamais `is continue_button`, rendant tout ce qui n'est pas un clic explicite sur Réessayer sûr et identique) — `self._deferred_job_id = self._active_job_id` est affecté, puis `_active_runner`/`_active_job_id`/`_cancel_in_flight` sont nettoyés exactement comme avant. **Le Job Domain reste volontairement `starting` ou `running`, selon son état rollbacké — jamais modifié artificiellement.**

## 8. Exemption Page-level uniquement pour les guards de contexte

`is_training_active()` ne délègue plus à `has_active_job()` mais reproduit le même scan (`job.state in TRAINING_JOB_ACTIVE_STATES`) directement, avec une seule exception : `job.job_id != self._deferred_job_id`. Tout autre Job actif — sur ce Training ou un autre — continue de faire retourner `True` exactement comme avant. Cette exemption ne sert qu'aux 4 appelants de `confirm_no_active_training()` (`new_project()`, `open_project()`, `rename_project()`, `closeEvent()`, tous dans `main_window.py`) — `is_training_active()` n'a aucun autre appelant (vérifié exhaustivement).

## 9. `TrainingManager.has_active_job()` inchangé

Non modifié, ni dans sa signature ni dans son comportement — reste la source de vérité Domain pure utilisée par `TrainingManager.delete()`. Après un `Continuer`, `has_active_job()` continue de retourner `True` tant que le Job différé n'est pas réellement résolu (retry ultérieur ou `_recover_stale_jobs()` à la prochaine ouverture).

## 10. Delete Training toujours bloqué

`TrainingManager.delete()` utilise son propre garde indépendant (`any(job.state in TRAINING_JOB_ACTIVE_STATES for job in training.jobs)`) — jamais `has_active_job()`/`is_training_active()`. Le Job différé restant réellement actif au Domain, `delete()` continue de lever `TrainingActiveError` pour son Training — volontaire : cette mission permet de quitter le contexte, jamais de supprimer silencieusement un Job dont la terminalisation n'est pas persistée.

## 11. Nouveau Start bloqué tant qu'un différé existe

`_refresh_job_controls()` désactive `start_training_button` tant que `self._deferred_job_id is not None` (en plus des conditions historiques), et affiche le libellé « Résultat d'entraînement non enregistré — nouvel entraînement impossible pour l'instant. » `cancel_training_button` reste géré exclusivement par `_active_runner` (inchangé) — correctement désactivé, puisque le processus réel est déjà terminé, il n'y a rien à annuler. **Défense en profondeur** : `start_training()` refuse également programmatiquement (`self._deferred_job_id is not None` ajouté à sa garde d'entrée), rendant l'invariant de cardinalité structurel et non purement visuel.

## 12. Pourquoi `Optional[str]` suffit — pourquoi aucun `set` n'est nécessaire

Un simple `Optional[str]` suffit **uniquement parce que** `start_training()` refuse tout nouveau Job tant qu'un différé existe (§11) — sans cette garde, un second Job différé écraserait le premier dans une variable scalaire, redevenant bloquant sans jamais se résoudre (scénario explicitement tracé en conception : A différé → B autorisé → B différé → A redevient bloquant). En bloquant Start structurellement, au plus un Job différé peut exister à la fois — invariant simple, aucune accumulation possible, aucun besoin de structure de données plus riche (`set[str]` explicitement écarté : aurait permis une accumulation illimitée de Jobs différés jamais résolus dans la session si le problème disque est durable, sans bénéfice correspondant).

## 13. `update_trainings()` ne doit surtout pas nettoyer le deferred state

**`update_trainings()` n'est pas modifiée — interdiction explicite et vérifiée.** Câblage réel confirmé dans `main_window.py` : `update_trainings()` est abonnée à `WORKSPACE_SAVED`/`WORKSPACE_RENAMED`, `CHARACTER_CREATED`, et `TRAINING_CREATED`/`SELECTED`/`DELETED` — tous des événements pouvant survenir dans le même contexte, totalement indépendants du Job différé (`WORKSPACE_SAVED` en particulier se déclenche à **chaque** sauvegarde réussie de tout le Workspace — Dataset, Character, LoRA, Settings...). Un reset placé là aurait effacé le marqueur au tout premier `save()` non lié, recréant le verrouillage M161 dans le même Workspace sans que l'utilisateur n'ait rien fait de pertinent — testé explicitement (§16, T4).

## 14. Reset uniquement au vrai changement de contexte

`reset_for_context_change()` — abonnée exclusivement à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` et `CHARACTER_SELECTED`/`DELETED`, un ensemble disjoint de celui d'`update_trainings()` — reçoit `self._deferred_job_id = None` en toute fin de méthode. Ce reset est un **nettoyage d'hygiène, jamais une garantie de correction** : `is_training_active()` scanne `self.training_manager.trainings`, déjà scopé au contexte courant (`principal_character.trainings`) — après un changement réel de Workspace/Character, l'ancien Job différé ne peut structurellement plus jamais être rencontré par ce scan, rendant l'exemption automatiquement inerte même sans ce reset explicite.

## 15. Stale recovery inchangé

`TrainingManager._recover_stale_jobs()` n'a subi aucune modification — reste abonnée uniquement à `WORKSPACE_OPENED`, convertit tout Job `starting`/`running` retrouvé vers `TRAINING_JOB_STATE_UNKNOWN` via le même `update_job_state()`, sans jamais deviner `succeeded`/`failed`/`cancelled`. À la prochaine ouverture réelle du Workspace laissé derrière (via `open_project()`), ce mécanisme reste responsable — à condition que la persistence fonctionne alors, sans garantie automatique, exactement la sémantique déjà établie par Mission 100.

## 16. M148 préservée

`_on_job_finished()` ne modifie jamais `state`/`final_output_path`/`error_message` reçus du Runner — la distinction succès/cancelled du Cancel tardif (Mission 148) se décide entièrement en amont, dans `TrainingJobRunner._on_process_finished()`, jamais touchée par cette mission. La boucle retry/continuer rejoue fidèlement le même triplet déjà décidé, quel que soit le résultat.

## 17. Scope exact

**Un seul fichier de production modifié** : `src/ui/pages/training_page.py`. Zones touchées : import (`TRAINING_JOB_ACTIVE_STATES` ajouté), `__init__` (+1 attribut runtime), `start_training()` (garde d'entrée étendue), `_on_job_finished()` (boucle retry/continuer), `is_training_active()` (scan avec exemption), `_refresh_job_controls()` (condition Start + libellé), `reset_for_context_change()` (+1 ligne d'hygiène). Aucun changement à `TrainingManager`, Domain, `TrainingJobRunner`, OneTrainer launch, `WorkspaceManager`/Storage, `MainWindow` (production), EventBus, ou toute autre Page.

## 18. Tests réels

**+6 tests nets** (2928 → 2934 tests collectés) :

`tests/integration/test_training_roundtrip.py`, classe `TrainingPageTerminalizationPersistenceFailureTest` (+4, fixture `_wire()`/`_make_training()` mirroir de `TrainingPageStartPrepareTest`) :
- `test_terminalization_persistence_failure_retry_succeeds_resolves_job_and_unblocks_workspace_guards`
- `test_terminalization_without_persistence_failure_never_opens_retry_dialog` (`subTest` succeeded/failed/cancelled)
- `test_unrelated_workspace_saved_never_clears_a_deferred_job`
- `test_deferred_job_blocks_start_training_preventing_a_second_deferred_job`

`tests/integration/test_main_window_new_project.py`, classe `MainWindowTrainingTerminalizationDeferredJobTest` (+2, `MainWindow()` réelle, mirroir de `MainWindowNewOpenGenerationActiveNonRegressionTest`) :
- `test_deferred_job_after_continue_lets_new_project_proceed_for_real` (preuve par l'effet réel — le Workspace change effectivement — et confirmation directe que `TrainingManager.delete()` refuse toujours, `has_active_job()` reste `True`)
- `test_a_genuinely_active_job_still_blocks_new_project_even_with_a_different_deferred_job` (un second Job réellement actif, créé indépendamment du différé, bloque toujours `new_project()`)

## 19. Résultats réels

- Ciblés `TrainingPageTerminalizationPersistenceFailureTest` : **4/4 passés**.
- Ciblés `MainWindowTrainingTerminalizationDeferredJobTest` : **2/2 passés**.
- `test_training_roundtrip.py` complet : **388/388 passés**.
- `test_main_window_new_project.py` + `test_training_job_runner.py` + `test_main_window_close_event.py` complets : **111/111 passés** (non-régression M148/M157/M100/M085/M114 confirmée).
- **Suite complète : 2934 collectés/2934 passés, 0 échoué** (338.707s). Équation : 2928 (clôture Mission 160) + 6 nets ajoutés par Mission 161 = **2934**, cohérent. Une première exécution a rencontré le crash natif `exit 139` déjà associé à la dette de harnais connue (`docs/missions/MISSION_097.md`/`MISSION_100.md`), sans rapport avec ce diff (aucun traceback, arrêt au milieu des tests Dataset, avant même d'atteindre les tests Training) ; la relance indépendante a abouti proprement à 2934/2934. Ne présente pas cette dette comme corrigée par M161.
- `git diff --check` : clean.
- Exactement 1 fichier de production modifié (`src/ui/pages/training_page.py`) — aucun deuxième fichier de production.

## 20. Clôture Git

Commit fonctionnel : `f154a82df7bcd31109431296fe14210bee28a1f4` (« Recover from training terminalization persistence failure », 4 fichiers : `src/ui/pages/training_page.py`, `tests/integration/test_training_roundtrip.py`, `tests/integration/test_main_window_new_project.py`, `docs/missions/MISSION_161.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission161` (objet `b1a63a949208b8cdc23e87affd6de08318ab8de1`, cible `f154a82df7bcd31109431296fe14210bee28a1f4`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission161 — Recover From Training Terminalization Persistence Failure` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2934/2934, 0 échoué** (338.707s). Le tag `v0.2-mission160` (`97787a90a02b5ec0761454c7ed8e61763db90992` → objet `671697e2339b3e2e7c6f43dcaa2ea431024b81b1`) reste inchangé. Distinctions préservées : bug corrigé = incohérence Page/Domain après échec de persistence de la terminalisation d'un entraînement déjà réellement terminé ; le rollback `TrainingManager.update_job_state()` (Mission 068/100) n'a jamais été la source du problème et reste inchangé ; `TrainingManager.has_active_job()` reste inchangé, source de vérité Domain pure ; l'exemption ajoutée est strictement Page-level, limitée aux 4 guards de contexte (`new_project()`/`open_project()`/`rename_project()`/`closeEvent()`) ; Delete Training reste refusé tant que le Job différé n'est pas réellement résolu ; nouveau Start bloqué structurellement (UI + programmatique) tant qu'un Job différé existe ; `update_trainings()` n'a jamais été modifiée, le nettoyage du marqueur restant confiné à `reset_for_context_change()` ; stale recovery (`_recover_stale_jobs()`) et Mission 148 (préservation du succès après Cancel tardif) intégralement inchangés ; une première exécution de la suite complète a rencontré le crash natif `exit 139` déjà associé à la dette de harnais documentée (`docs/missions/MISSION_097.md`/`MISSION_100.md`) — dette préexistante, non introduite et non corrigée par cette mission.
