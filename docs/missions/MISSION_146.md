# Mission 146 — Guard Owned Lifecycle Managers Against Undetected RUNNING_OWNED Death

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `ForgeLifecycleManager`/`ComfyUILifecycleManager` (`_on_process_finished()`) ne possédaient, dans les deux fichiers, aucune branche traitant le cas où un process réellement possédé et `RUNNING_OWNED` meurt spontanément (crash, OOM, kill externe) sans qu'aucun `stop()` n'ait été demandé — l'état interne restait bloqué sur `RUNNING_OWNED` indéfiniment, `Start` était refusé, seul un `Stop` manuel (qui revérifie l'état réel du `QProcess`) permettait de récupérer. Bug conceptuellement identique dans les deux managers, confirmé par lecture directe du code actuel et déjà partiellement documenté dans `MISSION_142.md` §2 (variante silencieuse `RUNNING_OWNED`, notée hors périmètre à l'époque). Corrigé indépendamment pour chaque manager — aucune abstraction commune. Voir §14/§15 pour les tests requis. **+9 tests nets** (2824 → 2833 tests collectés), suite complète 2833/2833, 0 échoué — voir §19 pour la clôture Git.

## 1. Root cause commune

`_on_process_finished()` a été conçu, dans les deux fichiers, pour ne résoudre que les cycles où le manager a lui-même provoqué ou attend la fin du process (`STARTING` en échec, `STOPPING`/kill actif). Aucun des deux ne prévoit le cas où le process qu'il croit posséder et fonctionnel (`RUNNING_OWNED`) meurt de sa propre initiative, sans qu'aucun `stop()` n'ait jamais été appelé. Ce n'est pas un problème de timing/callback stale (contrairement à M141/M142) — c'est une branche manquante dans chacune des deux méthodes. La divergence d'implémentation (flag `_terminating_owned_process` côté Forge vs `elif` simple côté ComfyUI) ne change rien à la nature du trou : dans les deux cas, l'état `RUNNING_OWNED` seul, sans kill actif en cours, n'est simplement jamais testé.

## 2. Preuve — état actuel exact, Forge (`src/ui/forge_lifecycle_manager.py`)

```python
def _on_process_finished(self, exit_code, exit_status) -> None:          # :325
    if self._readiness_worker is not None:
        self._readiness_worker.cancel()
    if self._terminating_owned_process:                                  # :329
        self._process = None
        self._owned_process_gone = True
        self._maybe_finish_teardown()
        return
    if self._state == STARTING:                                         # :342
        message = self._readiness_timeout_message or (
            f"Forge process exited before becoming available (exit_code={exit_code})"
        )
        self._readiness_timeout_message = None
        self._process = None
        self._set_state(START_FAILED, message)
```

Le premier `if` ne teste **pas** `self._state` — il couvre déjà `STARTING` (cleanup readiness-timeout) *et* `STOPPING` (Stop utilisateur) tant que `_terminating_owned_process` est vrai (positionné uniquement par `_terminate_owned_process()`, `:488`). Le second `if` couvre `STARTING` sans kill actif (crash pendant le démarrage). **Aucune branche ne couvre `RUNNING_OWNED` avec `_terminating_owned_process=False`** : la méthode retourne implicitement — `self._process` reste positionné sur le `QProcess` mort, `self._state` reste `RUNNING_OWNED`, aucun `state_changed` émis. `_on_process_error_occurred()` (`:318-323`) est symétriquement muet en dehors de `STARTING`.

**Récupération manuelle actuelle** : `stop()` accepte `RUNNING_OWNED` (`:473-477`) → `STOPPING` → `_terminate_owned_process()` (`:479`) → `self._process.state() == NotRunning` est vrai (Qt maintient l'état du `QProcess` même sans lecture du signal) → `_finish_process_teardown()` direct (**aucun taskkill relancé**, rien à tuer) → `STOPPED`. Chemin fonctionnel mais silencieux (aucun message n'explique pourquoi Stop a réussi instantanément), et incohérent avec le contrat cible (§4 : la cible attendue est `START_FAILED` avec message, pas un `STOPPED` muet).

## 3. Preuve — état actuel exact, ComfyUI (`src/ui/comfyui_lifecycle_manager.py`)

```python
def _on_process_finished(self, exit_code, exit_status) -> None:          # :245
    if self._terminate_timer is not None:
        self._terminate_timer.stop()
        self._terminate_timer = None
    if self._state == STARTING:                                         # :249
        ...
        self._set_state(START_FAILED, message)
    elif self._state == STOPPING:                                       # :263
        self._process = None
        self._set_state(STOPPED)
        self._resume_close_if_pending()
```

Même trou exact : `STARTING` et `STOPPING` sont couverts, **`RUNNING_OWNED` ne correspond à aucune branche** — pas même une garde par flag comme Forge, la résolution passe uniquement par l'état courant. `self._process` reste non réinitialisé. Ce scénario précis est déjà documenté noir sur blanc dans `MISSION_142.md` §2 :

> « Si B a déjà atteint `RUNNING_OWNED` [...] `_on_process_finished()` ne vérifie que `STARTING`/`STOPPING` [...] — `RUNNING_OWNED` ne correspond à aucune des deux branches → la méthode ne fait strictement rien [...] L'état reste `RUNNING_OWNED` indéfiniment alors que le processus réel est mort, sans aucun message d'erreur [...] Le système se corrigerait seulement si l'utilisateur reclique Stop plus tard. »

**Récupération manuelle actuelle** : identique dans l'esprit à Forge — `stop()` (`:272-289`) accepte `RUNNING_OWNED` → `STOPPING` → `_terminate_owned_process()` → `self._process.state()==NotRunning` → `_finish_process_teardown()` (`:309-324`) → `STOPPED`, silencieusement.

## 4. Contrat comportemental cible (validé, commun aux deux managers)

Pour chaque manager, indépendamment :

```
RUNNING_OWNED (aucun kill actif en cours)
→ process possédé disparaît spontanément
→ QProcess.finished reçu
→ _process = None
→ transition vers START_FAILED
→ last_error_message décrit une fin/disparition inattendue du process local,
  SANS prétendre en connaître la cause (pas de mention OOM/crash applicatif/kill externe)
→ state_changed émis normalement (via _set_state())
→ SettingsPage affiche déjà START_FAILED via last_error_message — aucune UI nouvelle
→ start() immédiatement possible (START_FAILED fait déjà partie du garde d'entrée
  des deux start(), aucune modification de ce garde n'est nécessaire)
```

`START_FAILED` a été retenu plutôt que `STOPPED` silencieux car c'est le seul état pour lequel `SettingsPage` affiche `last_error_message` (`settings_page.py:893`/`:949`) — réutiliser ce canal évite toute UI nouvelle, conformément à la contrainte explicite de cette mission.

## 5. Conception Forge — point d'insertion exact

Le nouveau branch doit s'insérer **après** le test `if self._terminating_owned_process:` existant (qui reste strictement prioritaire, inchangé), sous la forme d'un `elif self._state == RUNNING_OWNED:` :

- **Ne doit jamais être atteint** quand `_terminating_owned_process` est vrai — garanti par sa position `elif` après ce test, jamais avant.
- **Ne doit pas appeler `_terminate_owned_process()`** : le process possédé (`cmd.exe`) est déjà mort, rien à tuer, aucun taskkill à lancer.
- **Ne touche à aucune donnée du rendez-vous** `_stop_confirmed`/`_owned_process_gone`/`_taskkill_resolved`/`_terminate_timer` — ces attributs n'ont de sens que pour un teardown volontaire déjà engagé, jamais pour ce chemin.
- Doit faire : `self._process = None`, puis `self._set_state(START_FAILED, <message>)`.
- Le message doit être distinct du message readiness-timeout existant (`"Forge process exited before becoming available (exit_code=...)"`, réservé à `STARTING`) pour ne pas laisser croire que Forge n'a jamais démarré — cf. §4 pour le contenu autorisé.

## 6. Conception ComfyUI — point d'insertion exact

Le nouveau branch est un troisième `elif self._state == RUNNING_OWNED:` ajouté après le `elif STOPPING` existant, dans `_on_process_finished()` — position la plus directe des deux managers puisqu'il n'existe ni flag ni méthode de rendez-vous à respecter côté ComfyUI :

- Le bloc `if self._terminate_timer is not None: ...` déjà en tête de la méthode (`:246-248`) s'exécute inconditionnellement avant le test d'état — le nouveau branch en hérite gratuitement sans modification.
- Ne doit pas appeler `_terminate_owned_process()`.
- Doit faire : `self._process = None`, puis `self._set_state(START_FAILED, <message>)`.
- Le contrat normal `STARTING`/`STOPPING` de la méthode reste bit pour bit inchangé — le nouveau branch est strictement additif.

## 7. Timers

Aucun des deux nouveaux branches ne crée, ne réarme, ni ne consulte de timer. Aucun `terminate()`/`kill()`/`taskkill` n'est déclenché. Les protections anti-stale-timer M141 (Forge : arrêt+déréférencement dans `_maybe_finish_teardown()`, garde d'identité dans `_on_terminate_timeout()`) et M142 (ComfyUI : arrêt+déréférencement dans `_on_process_finished()` et `_finish_process_teardown()`, garde d'identité dans `_on_terminate_timeout()`) restent entièrement inchangées et ne sont invoquées par aucun chemin ajouté par cette mission.

## 8. `exitCode` / `exitStatus`

Aucune classification fondée sur `exitCode`/`exitStatus` n'est introduite. Le critère déterminant reste exclusivement : *le process possédé se termine alors que le lifecycle est encore réellement `RUNNING_OWNED` et qu'aucun teardown volontaire n'est engagé* (`_terminating_owned_process` faux côté Forge ; absence de toute branche `STOPPING` correspondante côté ComfyUI). Confirmé par lecture directe : les deux implémentations actuelles n'inspectent déjà `exit_status` nulle part (paramètre reçu, jamais lu) et ne consultent `exit_code` que pour l'inclure dans un message texte, jamais pour décider d'un chemin — cette convention est reconduite à l'identique. `exit_code` peut être inclus dans le nouveau message (cohérent avec le message `STARTING` existant qui le fait déjà), sans jamais l'utiliser pour deviner une cause (OOM, crash applicatif, kill externe) qui ne peut être démontrée par l'API Qt disponible ici.

## 9. `errorOccurred`

Non étendu. `_on_process_error_occurred()` reste strictement limité à `self._state == STARTING` dans les deux fichiers, comme aujourd'hui. Aucun scénario démontré pendant l'audit ne justifie un traitement de `errorOccurred` en `RUNNING_OWNED` — hors périmètre explicite.

## 10. UI

Aucune UI nouvelle, aucune popup. `SettingsPage._on_comfyui_lifecycle_state_changed()` (`settings_page.py:881-898`) et `_on_forge_lifecycle_state_changed()` (`settings_page.py:936-956`) traitent déjà `START_FAILED` en affichant `last_error_message` et en réactivant le bouton Start (`setEnabled(state in (..., START_FAILED))`) — strictement inchangés, aucune modification requise dans `settings_page.py`.

## 11. `stop()` — analyse de compatibilité

Aucune modification de `stop()` n'est requise ni justifiée. Une fois la récupération effectuée par les nouveaux branches, l'état devient `START_FAILED` — `stop()` (Forge `:473`, ComfyUI `:285`) fait déjà `if self._state != RUNNING_OWNED: return` (ComfyUI) / vérifie `RUNNING_OWNED` explicitement (Forge `:466-477`) : un `stop()` appelé sur `START_FAILED` reste un no-op strict dans les deux fichiers, déjà couvert par les tests existants (`test_stop_is_a_no_op_on_stopped`/équivalent `START_FAILED` implicite via la même garde). Aucune contradiction identifiée pendant la rédaction — si l'implémentation détaillée en révélait une, ce point réclamerait un STOP et un rapport avant toute modification de `stop()`.

## 12. Interaction M141 — invariants à préserver (Forge)

`MISSION_141.md` a établi : `_terminate_timer` ne doit jamais rester actif au-delà de la résolution du rendez-vous `_maybe_finish_teardown()`, et `_on_terminate_timeout()` doit rejeter tout signal dont le `sender()` n'est pas l'objet timer courant. Le nouveau branch (§5) ne crée, ne modifie, ni ne consulte `_terminate_timer` — invariant préservé par construction, sans vérification supplémentaire requise au niveau du code, mais à verrouiller par test (§14, point 9).

## 13. Interaction M142 — invariants à préserver (ComfyUI)

`MISSION_142.md` a établi : `_terminate_timer` doit être arrêté et déréférencé aux deux points de résolution (`_on_process_finished()`, `_finish_process_teardown()`), et `_on_terminate_timeout()` doit rejeter tout signal stale. Le nouveau branch (§6) hérite du nettoyage de timer déjà en tête de `_on_process_finished()` (§6) — invariant préservé par construction. À verrouiller par test que le test existant `test_stale_terminate_timeout_from_a_resolved_stop_never_kills_a_later_running_owned_process` (`:437`, qui construit déjà un état `RUNNING_OWNED` factice pour prouver que le garde anti-stale-timer ne tue pas le process B) reste vert sans modification — ce test ne couvre pas le nouveau chemin (il n'appelle jamais `_on_process_finished()` directement en `RUNNING_OWNED`) mais partage le même état factice et doit continuer à passer.

## 14. Tests requis — Forge (`tests/integration/test_forge_lifecycle_manager.py`)

Nouvelle classe ou ajout à `ForgeLifecycleManagerGuardTest` (idiome existant — état fabriqué directement, pas de vrai process), verrouillant au minimum :

1. `_state=RUNNING_OWNED`, `_terminating_owned_process=False` → `_on_process_finished(exit_code, exit_status)` appelé directement → `self.manager.state == START_FAILED`.
2. `self.manager._process is None` après l'appel.
3. `self.manager.last_error_message` non vide et distinct du message `STARTING`-readiness-timeout existant.
4. `state_changed` correctement observé (assertion sur `self.manager.state` après coup, cohérent avec le style déjà utilisé dans ce fichier — aucun spy de signal n'est utilisé ailleurs dans ce fichier, pas d'introduction d'un nouveau pattern).
5. `start()` appelé immédiatement après (mock `resolve_forge_launch`/`ForgeEngine`, même idiome que `test_start_uses_cmd_exe_with_the_resolved_run_bat_and_prepended_path`) réussit et atteint `STARTING`.
6. Le nouveau `QProcess` créé par ce `start()` est un objet distinct de l'ancien (comparaison d'identité `is not`).
7. `_terminate_owned_process()` n'est **jamais** appelée par ce chemin — vérifiable en patchant/espionnant la méthode et en assertant qu'elle n'a pas été invoquée, ou indirectement en vérifiant qu'aucun `taskkill` (`QProcess` supplémentaire) n'a été créé.
8. Non-régression : un `stop()` volontaire pendant un `RUNNING_OWNED` réellement actif continue de fonctionner exactement comme avant (`test_stop_on_running_owned_kills_the_real_process_tree`, `test_stop_is_idempotent_on_running_owned` — aucune modification attendue).
9. Non-régression M141 explicite : `test_stale_terminate_timeout_from_a_resolved_cycle_never_affects_a_later_cycle` (`:485`) reste vert sans modification.
10. Suite `ForgeLifecycleManagerGuardTest` complète + `ForgeLifecycleManagerRealProcessTest`/`ForgeLifecycleManagerStopConfirmationTest`/`ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest` rejouées intégralement, toutes vertes.

**Test avec vrai `QProcess` (à évaluer, inclure si déterministe)** : `ForgeLifecycleManagerRealProcessTest` réutilise déjà `_fake_comfyui_process.py` (script générique « reste en vie jusqu'à être tué, ou sort sur commande », contrôlé par les variables d'environnement `FAKE_EXIT_CODE`/`FAKE_RUN_SECONDS`). En lançant Forge normalement jusqu'à `RUNNING_OWNED` (comme `test_readiness_success_reaches_running_owned_and_stops_polling`), puis en laissant le fake process s'auto-terminer via un `FAKE_RUN_SECONDS` court configuré pour expirer après l'atteinte de `RUNNING_OWNED` (sans jamais appeler `stop()`), on obtient un scénario réel, déterministe, dans le même style que les tests process-réels déjà présents. À inclure si la mise en place reste aussi simple que les tests existants du même fichier ; ne pas forcer un test fragile si le timing s'avère instable pendant l'implémentation — dans ce cas, documenter pourquoi et se limiter aux tests 1-10 ci-dessus.

## 15. Tests requis — ComfyUI (`tests/integration/test_comfyui_lifecycle_manager.py`)

Structure miroir, adaptée au vocabulaire et à l'absence de flag `_terminating_owned_process` :

1. `_state=RUNNING_OWNED` → `_on_process_finished(exit_code, exit_status)` appelé directement → `self.manager.state == START_FAILED`.
2. `self.manager._process is None` après l'appel.
3. `self.manager.last_error_message` non vide et distinct du message `STARTING` existant.
4. `state_changed`/état observé après coup, même idiome que le fichier existant.
5. `start()` immédiatement après réussit et atteint `STARTING`.
6. Nouveau `QProcess` distinct de l'ancien.
7. Aucun `terminate()`/`kill()` déclenché sur l'ancien `_process` par ce chemin de récupération (le process est déjà mort — vérifiable en s'assurant qu'aucun `_terminate_timer` n'est créé, cf. point 9).
8. Non-régression : `stop()` volontaire pendant `RUNNING_OWNED` réel inchangé.
9. Non-régression M142 explicite : `test_stale_terminate_timeout_from_a_resolved_stop_never_kills_a_later_running_owned_process` (`:437`) et `test_stale_terminate_timeout_from_a_resolved_stop_never_affects_a_later_start` (`:405`) restent verts sans modification ; `test_process_finished_ignored_shape_never_double_transitions` (`:341`, seul test existant appelant `_on_process_finished()` hors `STARTING`/`STOPPING`, sur `EXTERNAL_ACTIVE`) reste vert et n'est pas affecté par le nouveau `elif RUNNING_OWNED` (état différent).
10. Suite `ComfyUILifecycleManagerGuardTest` + `ComfyUILifecycleManagerRealProcessTest` rejouées intégralement, toutes vertes.

**Test avec vrai `QProcess`** : même approche que Forge (§14), en réutilisant `_fake_comfyui_process.py` directement (pas de wrapper `cmd.exe`, plus simple que Forge) — `FAKE_RUN_SECONDS` court après `RUNNING_OWNED`, sans `stop()`. Mêmes réserves de robustesse qu'au §14.

## 16. Suites voisines à revérifier (non-régression, aucune modification attendue)

- `tests/integration/test_main_window_close_event.py` — consomme `confirm_safe_to_close()` des deux managers, non touché par cette mission, doit rester vert.
- `tests/integration/test_settings_page.py` — consomme `state_changed`/`last_error_message`/les labels des deux managers ; `START_FAILED` est déjà un état existant qu'il sait afficher, aucune régression attendue.
- `tests/integration/test_inference_page.py` — référence `ComfyUILifecycleManager` (partagé avec `InferencePage`), non touché.
- Suite complète (`unittest discover`) pour confirmer le compte exact de tests nets ajoutés et l'absence de régression transverse.

## 17. Exclusions confirmées (non-goals explicites)

Aucune refactorisation commune Forge/ComfyUI ; aucune nouvelle classe de base lifecycle ; aucune modification générale de la machine à états ; aucun nouvel état ; aucune modification du teardown Forge (`_terminate_owned_process()`, `_maybe_finish_teardown()`, taskkill) ; aucune modification du teardown ComfyUI (`_terminate_owned_process()`, `_finish_process_teardown()`) ; aucune refonte des protections M141/M142 ; aucun nouveau système de timers ; aucune nouvelle UI ; aucune popup ; aucune nouvelle politique `exitCode`/`exitStatus` ; aucune extension du traitement de `errorOccurred` ; aucune intégration Forge↔GenerationManager/Inference ; aucun autre bug/dette découvert par l'audit global (Workspace create failure cleanup, `create_job()` partial cleanup, caption sidecar, `_training_folder()` path validation, Character filesystem cleanup, Storage sweep, rolling backup OneTrainer) ; aucun travail sur Training Resume ; aucun Job/Queue unifié ; aucune fonctionnalité issue de l'estimation indicative des missions restantes (section L de l'audit précédent).

## 18. Fichiers attendus

- `src/ui/forge_lifecycle_manager.py` (production)
- `src/ui/comfyui_lifecycle_manager.py` (production)
- `tests/integration/test_forge_lifecycle_manager.py` (tests)
- `tests/integration/test_comfyui_lifecycle_manager.py` (tests)
- `docs/missions/MISSION_146.md` (documentation)

Aucun autre fichier de production n'est actuellement identifié comme nécessaire. Si la rédaction détaillée de l'implémentation révèle qu'un fichier hors de cette liste doit être modifié (notamment `src/ui/pages/settings_page.py`, dont l'audit ci-dessus confirme qu'il n'a besoin d'aucun changement), ce point devra être signalé et justifié avant toute modification — jamais ajouté silencieusement au scope.

## 19. Clôture Git

Commit fonctionnel `24613861960e3f4e6c87c9a80c8f111f00f74b7a` (« Fix owned process spontaneous exit recovery », 5 fichiers : `src/ui/forge_lifecycle_manager.py`, `src/ui/comfyui_lifecycle_manager.py`, `tests/integration/test_forge_lifecycle_manager.py`, `tests/integration/test_comfyui_lifecycle_manager.py`, `docs/missions/MISSION_146.md`), poussé sur `main` (`9238a02..2461386`). Tag annoté `v0.2-mission146` créé exactement sur ce commit (objet tag local et distant `0c0277ba8631704f15367fb4d921136a9182e2d9`, peeled target local et distant tous deux `24613861960e3f4e6c87c9a80c8f111f00f74b7a`, vérifiés identiques), poussé et confirmé sur `origin`. GitHub Release `v0.2-mission146` publiée manuellement (titre « v0.2-mission146 — Owned Process Spontaneous Exit Recovery for Forge and ComfyUI »).
