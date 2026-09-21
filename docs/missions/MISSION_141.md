# Mission 141 — Guard Forge Stop Teardown Against Stale Cross-Cycle Callbacks

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** Un audit global post-Mission 140 avait initialement soupçonné une flakiness de test liée à `test_forge_lifecycle_manager.py`. Une reconstruction exacte du lifecycle des objets (`_terminate_timer`, `_taskkill_process`, `_process`, les quatre flags de rendez-vous), demandée avant toute implémentation, a confirmé qu'il ne s'agissait pas seulement d'une fragilité de test : `ForgeLifecycleManager` contenait un vrai bug produit, déterministe et atteignable par un usage normal (Stop → Start rapide), pouvant faire échouer à tort un Démarrage légitime et/ou tuer le mauvais process. Corrigé et vérifié — voir §10 pour les résultats réels et §11 pour la clôture Git.

## 1. Problème

`ForgeLifecycleManager` (`src/ui/forge_lifecycle_manager.py`) est instancié **une seule fois** pour toute la session applicative (`src/ui/main_window.py:200`, `self.forge_lifecycle_manager = ForgeLifecycleManager()`) — chaque cycle Start/Stop réel réutilise la même instance et les mêmes attributs d'instance (`_process`, `_taskkill_process`, `_terminate_timer`, `_stop_confirmed`, `_owned_process_gone`, `_taskkill_resolved`, `_terminating_owned_process`).

`_terminate_owned_process()` (`:463-499`) crée, à chaque tentative d'arrêt réelle (Stop utilisateur ou cleanup de readiness-timeout), un `QTimer` borné à `TERMINATE_TIMEOUT_SECONDS` (10.0s en production) :

```python
timer = QTimer(self)
timer.setSingleShot(True)
timer.timeout.connect(self._on_terminate_timeout)
timer.start(int(TERMINATE_TIMEOUT_SECONDS * 1000))
self._terminate_timer = timer
```

Ce timer n'est **jamais explicitement arrêté** lorsque le rendez-vous de teardown (`_maybe_finish_teardown()`) se résout par l'autre voie (taskkill répondant avant l'échéance — le cas normal et rapide). Comme le timer est parenté (`QTimer(self)`), Qt le garde vivant tant que le manager lui-même est vivant (toute la session) — **il continuera donc à décompter et à émettre `timeout` environ 10 secondes après l'appel initial, quoi qu'il arrive entre-temps**, y compris si un tout nouveau cycle Start/Stop a commencé sur la même instance.

Par ailleurs, `_on_terminate_timeout()` (`:527-545`) est le seul des trois callbacks résolvant `_taskkill_resolved` à ne posséder **aucune** protection contre un signal tardif d'un cycle antérieur — contrairement à `_on_taskkill_finished()` (`:501-503`) et `_on_taskkill_error_occurred()` (`:516-518`), qui gardent chacun explicitement `if self.sender() is not self._taskkill_process: return`.

## 2. Preuve — scénario cross-cycle exact confirmé

Reconstruction précise, objet par objet, exactement demandée avant toute implémentation :

**Cycle A — Stop résolu normalement, timer jamais arrêté :**
1. Utilisateur clique Stop pendant `RUNNING_OWNED`. `stop()` → `_set_state(STOPPING)` → `_terminate_owned_process()`.
2. `_terminate_owned_process()` (`:468-499`) : réinitialise `_stop_confirmed=False`, `_owned_process_gone=False`, `_taskkill_resolved=False`, `_terminating_owned_process=True` ; crée `taskkill_A` (`self._taskkill_process = taskkill_A`) ; crée `timer_A` (`self._terminate_timer = timer_A`, `singleShot=True`, 10.0s).
3. `taskkill_A` répond vite (cas normal, quasi toujours < 10s) avec exit code 0 → `_on_taskkill_finished(0, ...)` (`:501-514`) : `self.sender() is self._taskkill_process` → vrai (c'est bien `taskkill_A`) → `_stop_confirmed=True`, `_taskkill_resolved=True`, `_taskkill_process=None`, appelle `_maybe_finish_teardown()`.
4. Suppose `_owned_process_gone` déjà vrai (cmd.exe déjà terminé) → `_maybe_finish_teardown()` (`:379-414`) passe le garde des deux flags, `_state == STOPPING` et `_stop_confirmed` vrai → `_set_state(STOPPED)`.
5. **`timer_A` n'est jamais arrêté.** Il continue de décompter en arrière-plan, toujours connecté à `self._on_terminate_timeout`, `self._terminate_timer` pointant toujours dessus.

**Cycle B — Start légitime, victime du timer périmé :**
6. Peu après (avant que 10 secondes se soient écoulées depuis l'étape 2), l'utilisateur clique Start. `start()` (`:177-253`) crée un **nouveau** `QProcess` (`process_B`, `self._process = process_B`), passe à `STARTING`, lance le worker de readiness.
7. **`_terminate_owned_process()` n'a PAS été rappelé pour le cycle B** (aucun Stop, aucun readiness-timeout ne s'est encore produit pour B) — donc `self._terminate_timer` **n'a pas été réassigné** : il pointe toujours sur `timer_A`. C'est exactement la trappe signalée : un garde d'identité naïf comparant `self.sender()` à `self._terminate_timer` ne détecterait **rien d'anormal** ici, puisque les deux valent `timer_A`.
8. À `t ≈ 10s` après l'étape 2, `timer_A.timeout` s'émet (jamais arrêté) → invoque `self._on_terminate_timeout()` sur la **même** instance de manager :
   ```python
   if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
       self._process.kill()          # <- tue process_B, le process LÉGITIME du cycle B
   self._taskkill_resolved = True    # <- vrai à tort pour le cycle B (aucun taskkill B n'existe)
   self._taskkill_process = None     # <- déjà None, écrasement inoffensif
   self._maybe_finish_teardown()
   ```
   `self._process` vaut maintenant `process_B` (le process du cycle B, actif) → **`process_B.kill()` tue le cmd.exe légitime du cycle B** (seul le cmd.exe est atteint — `kill()` ne descend pas dans l'arbre — le vrai `python.exe` de Forge B pourrait même survivre en orphelin, aggravant encore la situation).
9. `_maybe_finish_teardown()` : `self._state` vaut `STARTING` (cycle B) → passe le garde d'état (`STARTING` est une valeur autorisée). `_taskkill_resolved` vient d'être forcé à `True` à l'étape 8. `_owned_process_gone` — **jamais réinitialisé pour le cycle B** (seul `_terminate_owned_process()` le remet à `False`, jamais appelé pour B) — vaut donc encore `True`, résidu de l'étape 3 du cycle A. **Les deux flags sont vrais alors qu'aucune tentative d'arrêt réelle n'a jamais eu lieu pour le cycle B.**
10. Le rendez-vous se résout : `_state == STARTING` → branche « readiness-timeout Start-failure cleanup » (`:416-438`), bien que le cycle B n'ait **jamais** eu de readiness-timeout. `_stop_confirmed` vaut encore `True`, résidu de l'étape 3 du cycle A (jamais réinitialisé pour B) → `_set_state(START_FAILED, "Forge process was terminated before becoming available")`.

**Résultat concret** : un Démarrage parfaitement légitime du cycle B est signalé `START_FAILED` avec un message trompeur, et son process réel (`cmd.exe`) a effectivement été tué par un timer appartenant à un cycle Stop antérieur déjà résolu avec succès. C'est un **faux échec déterministe** (catégorie 2), pas une simple fragilité de test — reproductible dès que Start est recliqué dans la fenêtre des 10 secondes suivant un Stop résolu rapidement, ce qui est un usage tout à fait normal.

**Variante encore plus silencieuse** : si le cycle B a déjà atteint `RUNNING_OWNED` au moment où `timer_A` tire, `process_B.kill()` tue quand même le process réel, mais `_on_process_finished()` ne fait alors **rien du tout** (ni la branche `_terminating_owned_process`, ni la branche `_state == STARTING` ne s'appliquent à `RUNNING_OWNED`) : l'état reste `RUNNING_OWNED` indéfiniment alors que le process réel est mort — une incohérence d'état silencieuse, sans même un message d'erreur. Cette variante touche à une question plus large (détection de crash pendant `RUNNING_OWNED`, jamais couverte même hors de tout timer périmé) — **explicitement hors périmètre de Mission 141**, mais documentée ici comme observation dérivée de cet audit.

## 3. Comportement actuel / Invariant cible

**Avant** : un `_terminate_timer` créé lors d'une tentative d'arrêt reste actif indéfiniment si le rendez-vous se résout par l'autre voie (taskkill) avant son échéance — rien ne l'arrête, rien ne l'invalide. `_on_terminate_timeout()` n'a aucune protection contre un signal différé.

**Cible** : un callback asynchrone appartenant au cycle d'arrêt A ne doit jamais résoudre le teardown du cycle B, changer son état, tuer son process, ni produire un faux succès/faux échec pour B. Une fois qu'un terminate timer n'est plus nécessaire, il ne doit plus pouvoir agir sur un cycle ultérieur.

## 4. Architecture minimale retenue (Question 3)

**Réponse : C — les deux mécanismes, aucun troisième.**

- **A seul (arrêter le timer) suffirait déjà à fermer le scénario démontré ci-dessus** : si `timer_A` est explicitement arrêté (`.stop()`) dès que le rendez-vous se résout par la voie taskkill, il ne peut plus jamais émettre — le scénario du §2 devient impossible puisque `timer_A.timeout` ne se déclenche jamais tardivement.
- **B seul (garde d'identité sans jamais arrêter le timer) NE suffit PAS** — démontré précisément à l'étape 7 : tant que le cycle B n'a pas lui-même appelé `_terminate_owned_process()`, `self._terminate_timer` n'est jamais réassigné, donc `self.sender() is self._terminate_timer` reste vrai pour le timer périmé. Un garde d'identité seul est aveugle exactement dans le cas le plus dangereux (Start légitime, jamais de nouveau Stop).
- **C (les deux) est retenu** : arrêter explicitement `_terminate_timer` dans `_maybe_finish_teardown()` dès que le rendez-vous se résout (ferme réellement tous les chemins démontrés), **et** ajouter un garde d'identité dans `_on_terminate_timeout()` en miroir exact des deux gardes déjà existants sur `_on_taskkill_finished()`/`_on_taskkill_error_occurred()` — défense en profondeur cohérente avec le pattern déjà établi deux fois dans le même fichier, coût quasi nul, aucune régression possible (démontré au §6 contre le test existant qui appelle `_on_terminate_timeout()` directement).
- **D (jeton de génération/cycle) rejeté** : aucun mécanisme générique n'est nécessaire — le pattern Qt existant (`QTimer.stop()` + garde `sender()` identique aux deux callbacks jumeaux) ferme intégralement le scénario démontré, sans introduire d'abstraction nouvelle.

## 5. Lifecycle timer/process — réponses aux questions d'audit

**Question 1 — Timer** :
- Type exact : `PySide6.QtCore.QTimer`, parenté `QTimer(self)` (le manager lui-même) — donc gardé vivant par Qt tant que le manager existe, indépendamment de la référence Python `self._terminate_timer`.
- `singleShot=True` — ne peut émettre `timeout` qu'une seule fois dans sa vie, mais ce « une fois » suffit à causer le dégât démontré s'il tire au mauvais moment.
- Durée production : `TERMINATE_TIMEOUT_SECONDS = 10.0` secondes (`:70`).
- Création : à **chaque** appel à `_terminate_owned_process()` — jamais réutilisé, toujours un nouvel objet `QTimer`.
- Réassignation de l'attribut : uniquement dans `_terminate_owned_process()` (`:499`), donc uniquement lorsque **ce même cycle** initie une tentative d'arrêt — jamais lors d'un simple `start()`.
- Arrêt aujourd'hui : **jamais**, avant cette mission.
- Destruction : jamais explicitement — reste un enfant Qt du manager indéfiniment (fuite d'objet mineure, sans incidence fonctionnelle en soi, puisque `singleShot` l'empêche de re-tirer — le vrai problème est qu'il tire une fois, tardivement, avec effet de bord réel).
- Timeout tardif après résolution normale : confirmé réel et déterministe (voir §2), pas seulement théorique.

**Question 2 — Callback stale** : scénario exact documenté au §2, étapes 6-10. Callback : `_on_terminate_timeout()`. Sender au moment du tir tardif : `timer_A`. Valeur de `self._terminate_timer` à cet instant (avant correctif) : toujours `timer_A` (jamais réassigné, cycle B n'ayant jamais appelé `_terminate_owned_process()`). Valeur de `self._process` : `process_B` (le process réel et actif du cycle B). État du manager : `STARTING` (ou `RUNNING_OWNED` selon le timing — les deux variantes documentées au §2). Effet incorrect précis : `process_B.kill()` (process légitime tué) et/ou `_set_state(START_FAILED, ...)` prononcé à tort sur un Start qui progressait normalement.

**Question 4 — `_maybe_finish_teardown()`** :
- Les deux flags (`_owned_process_gone`, `_taskkill_resolved`) deviennent vrais exactement au moment où le code dépasse le garde `if not self._owned_process_gone or not self._taskkill_resolved: return` (`:381-382`) — c'est le point d'insertion retenu, avant toute autre mutation d'état.
- Le timer n'est plus jamais nécessaire après ce point, quelle que soit la sous-branche (`STOPPING` confirmé/non confirmé, ou `STARTING` readiness-timeout confirmé/non confirmé) — les quatre sous-chemins partagent le même constat : le rendez-vous est clos, plus rien n'attend le timer.
- `.stop()` seul suffit — un `QTimer` arrêté ne peut plus émettre `timeout`, qu'il ait déjà expiré (`singleShot` déjà inerte, `.stop()` est un no-op sûr) ou qu'il soit encore en cours de décompte (cas réel visé ici).
- `disconnect()` : non nécessaire — la connexion reste inoffensive une fois le timer arrêté ; aucun autre code du fichier n'appelle jamais `.disconnect()` sur `_taskkill_process` non plus (même convention : attribut simplement remis à `None`).
- `deleteLater()` : non nécessaire — même convention que `_taskkill_process`, jamais explicitement détruit, seulement dé-référencé ; l'objet Qt reste un enfant du manager, sans incidence fonctionnelle une fois arrêté.
- Mettre l'attribut à `None` : oui — exactement le même traitement que `_taskkill_process` reçoit déjà dans les trois callbacks existants, pour cohérence et pour que le garde d'identité de `_on_terminate_timeout()` rejette correctement tout signal futur (`self.sender() is not self._terminate_timer` devient vrai dès que `_terminate_timer` vaut `None` ou pointe sur un timer plus récent).

## 6. Implémentation

Deux modifications strictement additives dans `src/ui/forge_lifecycle_manager.py`, aucun changement de signature, d'API publique, de constante de timing, ni de structure de fichier :

**(a) `_maybe_finish_teardown()`** — arrêt et dé-référencement du timer dès que le rendez-vous se résout, avant toute autre action :

```python
if self._state not in (STARTING, STOPPING):
    return
if not self._owned_process_gone or not self._taskkill_resolved:
    return

if self._terminate_timer is not None:
    self._terminate_timer.stop()
    self._terminate_timer = None

self._terminating_owned_process = False
...
```

**(b) `_on_terminate_timeout()`** — garde d'identité en miroir exact de `_on_taskkill_finished()`/`_on_taskkill_error_occurred()` :

```python
def _on_terminate_timeout(self) -> None:
    if self.sender() is not self._terminate_timer:
        return  # stale signal from an earlier Stop cycle
    ...
```

## 7. Failure semantics

Aucun changement de sémantique d'échec : les quatre issues déjà existantes de `_maybe_finish_teardown()` (`STOPPED` confirmé, `START_FAILED` Stop non confirmé, `START_FAILED` readiness-timeout confirmé, `START_FAILED` readiness-timeout non confirmé) restent identiques bit pour bit — le correctif agit uniquement sur la fenêtre temporelle pendant laquelle un timer périmé pourrait interférer avec un cycle ultérieur, jamais sur la logique de résolution elle-même. Le seul comportement nouveau est négatif : un signal qui n'aurait jamais dû produire d'effet n'en produit désormais plus aucun.

## 8. Tests

**Fichier concerné** : `tests/integration/test_forge_lifecycle_manager.py` uniquement.

**Test de régression principal** (nouveau, `ForgeLifecycleManagerGuardTest`) : reproduit fidèlement le scénario du §2 avec la même instance de manager, prouvant un effet métier réel (le process du cycle B n'est jamais tué, son état n'est jamais altéré) plutôt qu'une simple assertion "timer.stop a été appelé" :
1. Fabrique un cycle A résolu (`_terminate_owned_process()` réellement appelé, puis résolution via `_on_taskkill_finished()` avant toute expiration du timer réel — timer réel patché à une durée courte pour rester rapide, jamais simulé par un mock qui ne pourrait pas prouver l'identité `sender()`).
2. Démarre un cycle B légitime sur la même instance (`self.manager._process` réassigné à un nouveau `MagicMock` représentant le process réel de B, état `STARTING`).
3. Laisse le vrai `QTimer` du cycle A (non arrêté si le correctif était absent) émettre son `timeout` réel — ou, de façon déterministe et sans dépendre d'un vrai minutage, invoque explicitement le callback avec `self.sender()` patché pour retourner l'objet timer du cycle A capturé à l'étape 1.
4. Vérifie : `self.manager._process` (le process du cycle B) n'a jamais reçu `.kill()` ; l'état du manager reste inchangé (toujours celui du cycle B, jamais `START_FAILED`) ; `self.manager._taskkill_resolved` n'est pas altéré pour le cycle B.

**Tests complémentaires** :
- Le timer courant fonctionne toujours normalement (le vrai timeout, non périmé, continue de déclencher le fallback `kill()` et la résolution `START_FAILED` — non-régression du comportement `ForgeLifecycleManagerStopConfirmationTest`/`ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest` déjà existant).
- `_maybe_finish_teardown()` arrête bien `_terminate_timer` et le remet à `None` une fois résolu (vérifié via un vrai `QTimer` : `isActive()` faux après résolution).
- Le garde stale de `_on_terminate_timeout()` est symétrique à celui déjà testé pour `_on_taskkill_finished()`/`_on_taskkill_error_occurred()` (`test_stale_taskkill_finished_signal_is_ignored`) — mimé avec le même idiome `patch.object(ForgeLifecycleManager, "sender", return_value=...)`.
- Non-régression explicite de `test_pending_close_never_resumes_via_the_no_taskkill_needed_fallback_message` (`:538-556`), seul test existant appelant `_on_terminate_timeout()` directement sans patcher `sender()` — vérifié compatible : `self.sender()` non patché retourne `None` hors contexte de signal réel, et `self.manager._terminate_timer` vaut `None` par défaut (`ForgeLifecycleManager()` frais dans `setUp()`), donc le nouveau garde (`None is not None` → faux) laisse le test se dérouler exactement comme avant.

## 9. Exclusions confirmées

Rolling backup OneTrainer, Resume Training, `TrainingManager.delete()`, nettoyage filesystem de `create_job()`, Settings morts, événements Training sans subscriber, backup/versioning de `project.json`, tout changement général des timeouts Forge (`TERMINATE_TIMEOUT_SECONDS`/`READINESS_*` restent inchangés), toute refonte du lifecycle Forge au-delà du correctif ciblé ci-dessus. La variante `RUNNING_OWNED` silencieuse documentée au §2 (détection de crash process pendant l'exécution normale) est explicitement hors périmètre — observation dérivée, non traitée par cette mission.

## 10. Résultats réels après implémentation

**Fichiers modifiés** :
- `src/ui/forge_lifecycle_manager.py` — 18 lignes ajoutées (arrêt/dé-référencement du timer dans `_maybe_finish_teardown()` + garde d'identité dans `_on_terminate_timeout()`), aucune ligne supprimée, aucun changement de signature/constante/structure.
- `tests/integration/test_forge_lifecycle_manager.py` — import `QTimer` ajouté, **+4 tests nets** dans `ForgeLifecycleManagerGuardTest` : `test_maybe_finish_teardown_stops_and_clears_the_terminate_timer_once_resolved`, `test_stale_terminate_timeout_signal_is_ignored`, `test_terminate_timeout_from_the_current_timer_is_not_treated_as_stale`, `test_stale_terminate_timeout_from_a_resolved_cycle_never_affects_a_later_cycle` (le test principal, reproduisant fidèlement le scénario cross-cycle du §2 contre un effet métier réel — le process du cycle B n'est jamais tué, son état n'est jamais altéré).

**Résultats** :
- `ForgeLifecycleManagerGuardTest` seule : **41/41** (37 existants inchangés + 4 nouveaux).
- `test_forge_lifecycle_manager.py` complet (les 4 classes, y compris les tests process-réel `ForgeLifecycleManagerRealProcessTest`/`ForgeLifecycleManagerStopConfirmationTest`/`ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest`) : **52/52**, aucun flake sur ce run.
- `test_main_window_close_event.py` + `test_settings_page.py` (seuls fichiers hors suite Forge référençant `ForgeLifecycleManager`) : **136/136**, non-régression confirmée.
- **Suite complète** : **2786 tests collectés, 2786 passés, 0 échoué, exit 0 (347.400s)**. Équation : 2782 (clôture Mission 140) + 4 nets ajoutés par Mission 141 = **2786**, cohérent. Aucun flake Forge sur ce run (les deux flakes historiques observés pendant Mission 139 concernaient des tests différents de ce même fichier, non reproduits ici).
- `git diff --check` : propre (seuls des avertissements LF→CRLF inoffensifs).

**Smoke réel Forge** : non effectué, décision justifiée après implémentation — le bug a été intégralement démontré et corrigé au niveau du lifecycle Qt automatisé, avec de vrais objets `QTimer` (jamais mockés) pour prouver `.stop()`/`isActive()`, et le comportement du process réel (taskkill/cmd.exe/`kill()` sur l'arbre réel) reste couvert, inchangé et toujours vert, par les classes `ForgeLifecycleManagerRealProcessTest`/`ForgeLifecycleManagerStopConfirmationTest`/`ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest` déjà existantes (real `cmd.exe` → `python.exe`, vrai `taskkill`). Un smoke manuel avec une installation Forge réelle n'apporterait aucune preuve supplémentaire sur le point précis corrigé (l'identité et le cycle de vie d'un objet `QTimer` Python/Qt) et ajouterait un risque opérationnel (lancement réel d'un serveur Forge) sans bénéfice de vérification correspondant.

**Écarts par rapport au design demandé** : aucun. L'implémentation suit exactement l'architecture retenue au §4 (réponse C), sans jeton de génération/cycle, sans changement de timeouts, sans modification hors de `src/ui/forge_lifecycle_manager.py` et `tests/integration/test_forge_lifecycle_manager.py`.

## 11. Clôture Git

Commit fonctionnel `2b8e3dcccdf5205786f327e58be2d737c0cb67db` (« Guard Forge teardown against stale terminate timers », 3 fichiers : `src/ui/forge_lifecycle_manager.py`, `tests/integration/test_forge_lifecycle_manager.py`, `docs/missions/MISSION_141.md`), poussé sur `main` (`3a2fcc4..2b8e3dc`). Tag annoté `v0.2-mission141` créé exactement sur ce commit (objet tag local et distant `0c95937672b048c7b6fdf3019b3727220fe7eb69`, peeled target local et distant tous deux `2b8e3dcccdf5205786f327e58be2d737c0cb67db`, vérifiés identiques), poussé et confirmé sur `origin`. GitHub Release `v0.2-mission141` publiée manuellement (titre « v0.2-mission141 — Guard Forge Teardown Against Stale Terminate Timers »).
