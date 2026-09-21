# Mission 142 — Guard ComfyUI Teardown Against Stale Terminate Timers

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente de validation externe.** L'audit global post-Mission 141 avait identifié dans `ComfyUILifecycleManager` la même classe de défaut que celle corrigée par Mission 141 dans `ForgeLifecycleManager`. Une reconstruction exacte et indépendante du lifecycle ComfyUI (sans copier-coller aveugle du raisonnement Forge) a confirmé que le bug était réel, déterministe et atteignable par un usage normal — mais avec une architecture interne suffisamment différente de Forge (pas de process `taskkill` séparé, pas de rendez-vous à deux flags, pas de méthode unique `_maybe_finish_teardown()`) pour nécessiter une adaptation précise des deux points d'insertion du correctif. Corrigé et vérifié — voir §10 pour les résultats réels.

## 1. Problème

`ComfyUILifecycleManager` (`src/ui/comfyui_lifecycle_manager.py`) est instancié **une seule fois** pour toute la session applicative (`src/ui/main_window.py:195`, `self.comfyui_lifecycle_manager = ComfyUILifecycleManager()`), et cette même instance est partagée avec `SettingsPage` et `InferencePage` (`main_window.py:300`, `:473`) — exactement la même architecture single-instance-per-session que `ForgeLifecycleManager` (`main_window.py:200`). Chaque cycle Start/Stop réel réutilise la même instance et les mêmes attributs (`_process`, `_terminate_timer`, `_readiness_thread`, `_readiness_worker`).

`_terminate_owned_process()` (`:288-298`) crée, à chaque tentative d'arrêt réelle (Stop utilisateur pendant `RUNNING_OWNED`/`STARTING`, ou cleanup de readiness-timeout), un `QTimer` borné à `TERMINATE_TIMEOUT_SECONDS` (10.0s en production) :

```python
self._process.terminate()
timer = QTimer(self)
timer.setSingleShot(True)
timer.timeout.connect(self._on_terminate_timeout)
timer.start(int(TERMINATE_TIMEOUT_SECONDS * 1000))
self._terminate_timer = timer
```

Ce timer n'est **jamais explicitement arrêté** lorsque le processus répond à `terminate()` et se termine de lui-même avant l'échéance (le cas normal et rapide) — ni dans `_on_process_finished()` (`:245-263`), ni dans `_finish_process_teardown()` (`:304-316`), les deux seuls endroits où une tentative d'arrêt se résout réellement. Comme le timer est parenté (`QTimer(self)`), Qt le garde vivant tant que le manager lui-même est vivant (toute la session) — il continue donc à décompter et à émettre `timeout` environ 10 secondes après l'appel initial, quoi qu'il arrive entre-temps, y compris si un tout nouveau cycle Start/Stop a commencé sur la même instance.

`_on_terminate_timeout()` (`:300-302`) ne possède **aucune** protection contre un signal tardif d'un cycle antérieur :

```python
def _on_terminate_timeout(self) -> None:
    if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
        self._process.kill()
```

Il n'existe ici ni `_taskkill_process` séparé, ni rendez-vous à deux flags comme dans Forge — l'architecture ComfyUI est plus simple : `terminate()` (arrêt gracieux) → un seul timer → `kill()` (escalade forcée) si le processus n'a pas fini avant l'échéance. La seule voie de résolution du teardown est le signal `QProcess.finished` du process lui-même (`_on_process_finished()`), déclenché soit par `terminate()` ayant réussi, soit par `kill()` ayant réussi. Il n'y a donc pas de « deuxième voie de résolution » indépendante comme le `taskkill` de Forge — mais le timer reste néanmoins un objet asynchrone totalement déconnecté de cette résolution une fois créé.

Un précédent local existe déjà dans ce même fichier pour un risque analogue : `_on_readiness_ready()`/`_on_readiness_timed_out()` (`:214-232`) gardent chacun explicitement `worker = self.sender(); if self._readiness_worker is not worker or self._state != STARTING: return` — un garde d'identité déjà établi pour le worker de readiness, mais jamais étendu au terminate timer.

## 2. Preuve — scénario cross-cycle exact confirmé (reconstruction indépendante, pas une transposition de Forge)

**Cycle A — Stop résolu normalement pendant `RUNNING_OWNED`, timer jamais arrêté :**
1. Utilisateur clique Stop pendant `RUNNING_OWNED`. `stop()` (`:282-286`) → `_set_state(STOPPING)` → `_terminate_owned_process()`.
2. `_terminate_owned_process()` : `self._process` (`process_A`) est vivant → `process_A.terminate()` → crée `timer_A` (`self._terminate_timer = timer_A`, `singleShot=True`, 10.0s).
3. `process_A` répond vite à `terminate()` (cas normal, quasi toujours < 10s) → Qt émet `finished` → `_on_process_finished(exit_code, exit_status)` (`:245-263`) : `self._state == STOPPING` → `self._process = None` → `_set_state(STOPPED)` → `_resume_close_if_pending()`.
4. **`timer_A` n'est jamais arrêté ni dé-référencé.** Il continue de décompter en arrière-plan, `self._terminate_timer` pointant toujours dessus.

**Cycle B — Start légitime, victime du timer périmé :**
5. Peu après (avant que 10 secondes se soient écoulées depuis l'étape 2), l'utilisateur clique Start. `start()` (`:110-157`) : état `STOPPED` autorisé → crée un **nouveau** `QProcess` (`process_B`, `self._process = process_B`), passe à `STARTING`, lance le worker de readiness.
6. **`_terminate_owned_process()` n'a PAS été rappelé pour le cycle B** (aucun Stop, aucun readiness-timeout ne s'est encore produit pour B) — donc `self._terminate_timer` **n'a pas été réassigné** : il pointe toujours sur `timer_A`. Un garde d'identité naïf comparant `self.sender()` à `self._terminate_timer` ne détecterait rien d'anormal ici, puisque les deux valent `timer_A` — exactement la même trappe que celle démontrée pour Forge, reconstruite ici indépendamment sur le code ComfyUI réel.
7. À `t ≈ 10s` après l'étape 2, `timer_A.timeout` s'émet (jamais arrêté) → invoque `self._on_terminate_timeout()` sur la **même** instance de manager :
   ```python
   if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
       self._process.kill()          # <- tue process_B, le process LÉGITIME du cycle B
   ```
   `self._process` vaut maintenant `process_B` (actif, légitime) → **`process_B.kill()` tue le process ComfyUI légitime du cycle B.**
8. La suite dépend de l'état exact de B à cet instant :
   - **Si B est encore `STARTING`** (readiness pas encore résolue) : le `kill()` déclenche `finished` sur `process_B` → `_on_process_finished()` : `self._state == STARTING` → annule le worker de readiness de B (encore actif, faussement annulé) → `message = self._readiness_timeout_message or f"ComfyUI process exited before becoming available (exit_code={exit_code})"` (`_readiness_timeout_message` vaut `None` pour B, jamais positionné) → `self._process = None` → `_set_state(START_FAILED, message)`. **Faux échec déterministe** : un Démarrage parfaitement légitime, en cours de réussir, est signalé `START_FAILED` avec un message trompeur ("process exited before becoming available"), alors qu'en réalité un timer d'un cycle Stop antérieur, déjà résolu avec succès, a tué le process.
   - **Si B a déjà atteint `RUNNING_OWNED`** (readiness déjà réussie) : le `kill()` tue quand même le process réel, `finished` se déclenche, mais `_on_process_finished()` ne vérifie que `STARTING`/`STOPPING` (`:246`, `:260`) — **`RUNNING_OWNED` ne correspond à aucune des deux branches** → la méthode ne fait strictement rien : ni changement d'état, ni remise à `None` de `self._process`. **L'état reste `RUNNING_OWNED` indéfiniment alors que le processus réel est mort**, sans aucun message d'erreur — une incohérence d'état totalement silencieuse. Le système se corrigerait seulement si l'utilisateur reclique Stop plus tard (`_terminate_owned_process()` détecterait alors `self._process.state() == NotRunning` et résoudrait proprement via `_finish_process_teardown()`), mais entre-temps l'UI (`SettingsPage`, `InferencePage`) continue d'afficher/utiliser un état `RUNNING_OWNED` mensonger.

**Résultat concret** : reproductible dès que Start est recliqué dans la fenêtre des 10 secondes suivant un Stop résolu rapidement — un usage tout à fait normal. Catégorie (2) faux succès/faux échec, combinée à (4) lifecycle process incomplet.

**Variante intra-cycle dérivée, non traitée (hors périmètre)** : `stop()` (`:275-280`) reste actionnable tant que `self._state == STARTING`, y compris pendant qu'un readiness-timeout-cleanup (`_on_readiness_timed_out()` → `_terminate_owned_process()`) est déjà en cours pour ce même cycle (le commentaire du fichier lui-même précise que l'état reste délibérément `STARTING`, jamais `STOPPING`, pendant cette fenêtre). Un second appel à `_terminate_owned_process()` dans cette fenêtre créerait un `timer_A2` sans jamais arrêter `timer_A1`, qui resterait un `QTimer` Qt vivant et indépendant. Ce n'est PAS le scénario cross-cycle démontré ci-dessus (c'est intra-cycle, pas inter-cycle) et n'est pas corrigé par cette mission — mais le garde d'identité retenu au §4 neutralise déjà ce cas en bonus (`timer_A1`, orphelin, ne sera jamais égal à `self._terminate_timer` au moment où il tire, donc rejeté). Observation dérivée de cet audit, documentée ici comme telle, non retenue comme nécessitant une correction séparée.

## 3. Comportement actuel / Invariant cible

**Avant** : un `_terminate_timer` créé lors d'une tentative d'arrêt reste actif indéfiniment si le processus se termine de lui-même avant son échéance — rien ne l'arrête, rien ne l'invalide. `_on_terminate_timeout()` n'a aucune protection contre un signal différé.

**Cible** : un callback asynchrone appartenant au cycle d'arrêt A ne doit jamais résoudre le teardown du cycle B, changer son état, tuer son process, ni produire un faux succès/faux échec pour B. Une fois qu'un terminate timer n'est plus nécessaire, il ne doit plus pouvoir agir sur un cycle ultérieur.

## 4. Comparaison avec M141 / Architecture minimale retenue

**Différences structurelles avec Forge, confirmées par lecture directe :**

| | Forge | ComfyUI |
|---|---|---|
| Process d'arrêt | `terminate()` + `taskkill` séparé (process externe) | `terminate()` seul (pas de `taskkill`) |
| Rendez-vous de résolution | 2 flags (`_owned_process_gone`/`_taskkill_resolved`) + `_maybe_finish_teardown()` unique | Aucun flag — résolution directe via le signal `QProcess.finished` (`_on_process_finished()`) ou l'absence de process (`_finish_process_teardown()`) |
| Garde d'identité existant | Déjà présent sur `_on_taskkill_finished()`/`_on_taskkill_error_occurred()` | Déjà présent sur `_on_readiness_ready()`/`_on_readiness_timed_out()` (worker de readiness, pas le terminate timer) |
| Point d'insertion du stop+clear | Un seul (`_maybe_finish_teardown()`) | Deux (`_on_process_finished()` et `_finish_process_teardown()`), car il n'existe pas de méthode de rendez-vous unique |

**Réponse à la Question 3 : C — les deux mécanismes, aucun troisième, adaptés à l'architecture ComfyUI.**

- **A seul (arrêter le timer)** suffirait à fermer le scénario cross-cycle démontré ci-dessus : si `timer_A` est explicitement arrêté dès que `process_A` se termine réellement (dans `_on_process_finished()`) ou dès que `_terminate_owned_process()` constate l'absence de process vivant (`_finish_process_teardown()`), il ne peut plus jamais émettre tardivement — ces deux méthodes sont les deux seuls points où une tentative d'arrêt de la CYCLE COURANTE se conclut, et Start ne peut être rappelé qu'après que l'un des deux ait tourné.
- **B seul (garde d'identité sans jamais arrêter le timer) NE suffit PAS** — démontré précisément à l'étape 6 : tant que le cycle B n'a pas lui-même appelé `_terminate_owned_process()`, `self._terminate_timer` n'est jamais réassigné, donc `self.sender() is self._terminate_timer` reste vrai pour le timer périmé. Identique à la démonstration Forge, reconstruite ici indépendamment sur le code ComfyUI.
- **C (les deux) est retenu**, avec un bénéfice supplémentaire propre à ComfyUI : le garde d'identité neutralise aussi, en prime, la variante intra-cycle dérivée du §2 (un `timer_A1` orphelin issu d'un double appel à `_terminate_owned_process()` dans la même fenêtre `STARTING`) — un argument encore plus fort qu'avec Forge pour retenir les deux protections. Coût quasi nul, cohérent avec le pattern déjà établi dans ce même fichier pour le worker de readiness.
- **D (jeton de génération/cycle) rejeté** : aucun mécanisme générique n'est nécessaire — le pattern Qt existant (`QTimer.stop()` + garde `sender()`, déjà utilisé pour le worker de readiness dans ce même fichier) ferme intégralement le scénario démontré.

## 5. Lifecycle timer/process — réponses aux questions d'audit

**Type/parenté/singleShot** : `PySide6.QtCore.QTimer`, parenté `QTimer(self)` (le manager) — gardé vivant par Qt tant que le manager existe. `singleShot=True`. Durée production : `TERMINATE_TIMEOUT_SECONDS = 10.0` secondes (`:64`).

**Création par cycle** : à chaque appel à `_terminate_owned_process()` qui trouve un process vivant (`:293-298`) — jamais réutilisé, toujours un nouvel objet `QTimer`.

**Réassignation de l'attribut** : uniquement dans `_terminate_owned_process()` (`:298`), donc uniquement lorsque **ce même cycle** initie une tentative d'arrêt (Stop utilisateur ou readiness-timeout-cleanup) — jamais lors d'un simple `start()`.

**Arrêt actuel** : jamais, avant cette mission.

**Destruction** : jamais explicitement — reste un enfant Qt du manager indéfiniment (fuite d'objet mineure une fois arrêté et dé-référencé, sans incidence fonctionnelle, `singleShot` l'empêchant de re-tirer).

**Comportement quand le process se termine avant le timeout** : c'est exactement le cas normal (étape 3 du §2) — `_on_process_finished()` résout le cycle correctement, mais sans jamais toucher au timer, qui continue de décompter séparément.

**Timer A → teardown A résolu → nouveau Start B → process B RUNNING → Timer A expire → peut-il agir sur Process B ?** Oui, confirmé (§2, étapes 6-8) : `self._process` valant `process_B` au moment où `timer_A` expire, `_on_terminate_timeout()` appelle inconditionnellement `process_B.kill()`.

## 6. Implémentation

Deux modifications strictement additives dans `src/ui/comfyui_lifecycle_manager.py`, aucun changement de signature, d'API publique, de constante de timing, ni de structure de fichier :

**(a) `_on_process_finished()`** — arrêt et dé-référencement du timer dès que le process se termine réellement, avant toute autre action (couvre le cas normal — process répondant à `terminate()` — et le cas où `kill()` a été nécessaire) :

```python
def _on_process_finished(self, exit_code, exit_status) -> None:
    if self._terminate_timer is not None:
        self._terminate_timer.stop()
        self._terminate_timer = None
    if self._state == STARTING:
        ...
    elif self._state == STOPPING:
        ...
```

**(b) `_finish_process_teardown()`** — même traitement, pour le cas où `_terminate_owned_process()` ne trouve aucun process vivant à cet instant (aucun nouveau timer n'est créé dans ce cas précis, mais un timer résiduel d'un cycle antérieur pourrait encore traîner — c'est exactement ce second point d'insertion qui ferme cette variante) :

```python
def _finish_process_teardown(self) -> None:
    self._process = None
    if self._terminate_timer is not None:
        self._terminate_timer.stop()
        self._terminate_timer = None
    if self._state == STARTING:
        ...
    elif self._state == STOPPING:
        ...
```

**(c) `_on_terminate_timeout()`** — garde d'identité en miroir du pattern déjà établi dans ce même fichier pour le worker de readiness :

```python
def _on_terminate_timeout(self) -> None:
    if self.sender() is not self._terminate_timer:
        return  # stale signal from an earlier Stop/readiness-timeout cleanup cycle
    if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
        self._process.kill()
```

## 7. Failure semantics

Aucun changement de sémantique d'échec : les issues déjà existantes (`STOPPED`, `START_FAILED` pour readiness-timeout ou sortie prématurée) restent identiques bit pour bit — le correctif agit uniquement sur la fenêtre temporelle pendant laquelle un timer périmé pourrait interférer avec un cycle ultérieur, jamais sur la logique de résolution elle-même. Le seul comportement nouveau est négatif : un signal qui n'aurait jamais dû produire d'effet n'en produit désormais plus aucun.

## 8. Tests

**Fichier concerné** : `tests/integration/test_comfyui_lifecycle_manager.py` uniquement.

**Test de régression principal** (nouveau, dans `ComfyUILifecycleManagerGuardTest`) : reproduit fidèlement le scénario du §2 avec la même instance de manager, prouvant un effet métier réel (le process du cycle B n'est jamais tué, son état n'est jamais altéré) plutôt qu'une simple assertion "timer.stop a été appelé" :
1. Fabrique un cycle A résolu (`_terminate_owned_process()` réellement appelé avec un process factice, puis `_on_process_finished()` invoqué pour simuler sa résolution — timer réel `QTimer`, jamais un mock, pour pouvoir prouver l'identité `sender()`).
2. Démarre un cycle B légitime sur la même instance (`self.manager._process` réassigné à un nouveau `MagicMock` représentant le process réel de B, état `STARTING` ou `RUNNING_OWNED` selon la variante testée).
3. Invoque `_on_terminate_timeout()` avec `self.sender()` patché pour retourner l'objet timer du cycle A capturé à l'étape 1.
4. Vérifie : `self.manager._process` (le process du cycle B) n'a jamais reçu `.kill()` ; l'état du manager reste inchangé (jamais `START_FAILED`, jamais altéré depuis `RUNNING_OWNED`).

**Tests complémentaires** :
- `_on_process_finished()` arrête bien `_terminate_timer` et le remet à `None` une fois résolu (vérifié via un vrai `QTimer` : `isActive()` faux après résolution).
- `_finish_process_teardown()` arrête et dé-référence également un timer résiduel s'il en existe un au moment de son appel.
- Le timer courant, légitime, continue de fonctionner normalement (non-régression du comportement déjà couvert par `ComfyUILifecycleManagerRealProcessTest`).
- Le garde stale de `_on_terminate_timeout()` est symétrique à celui déjà testé pour le worker de readiness (`test_readiness_timed_out_from_a_stale_worker_is_ignored`) — mimé avec le même idiome `patch.object(ComfyUILifecycleManager, "sender", return_value=...)` déjà établi dans ce fichier (`_fake_sender`).
- Non-régression explicite de `test_process_finished_ignored_shape_never_double_transitions` (seul test existant appelant `_on_process_finished()` directement en dehors de `STARTING`/`STOPPING`) — vérifié compatible : ce test positionne l'état à `EXTERNAL_ACTIVE` sans jamais toucher `_terminate_timer` (reste `None` par défaut), donc le nouveau `if self._terminate_timer is not None:` ajouté en tête de fonction est un no-op pour ce test, comportement inchangé.
- Aucune régression attendue sur `confirm_safe_to_close()` ni sur les guards du worker de readiness — aucun des deux n'est touché par ce correctif.

## 9. Exclusions confirmées

Forge (`forge_lifecycle_manager.py`, déjà clos par Mission 141 — aucune modification), rolling backup OneTrainer, Resume Training, `TrainingManager.delete()`, nettoyage filesystem de `create_job()`, backup/versioning de `project.json`, gestion d'erreur des sidecars caption, Settings réservés (`python_path`/`ollama_path`), événements Training sans subscriber, tout changement général des timeouts ComfyUI (`TERMINATE_TIMEOUT_SECONDS`/`READINESS_*` restent inchangés), toute refonte du lifecycle ComfyUI au-delà du correctif ciblé ci-dessus. La variante intra-cycle dérivée documentée au §2 (double appel à `_terminate_owned_process()` dans la fenêtre `STARTING`) est explicitement hors périmètre — observation dérivée, neutralisée en bonus par le garde d'identité mais non corrigée à sa source par cette mission.

## 10. Résultats réels après implémentation

**Fichiers modifiés** :
- `src/ui/comfyui_lifecycle_manager.py` — 8 lignes ajoutées (arrêt/dé-référencement du timer dans `_on_process_finished()` et dans `_finish_process_teardown()`, garde d'identité dans `_on_terminate_timeout()`), aucune ligne supprimée, aucun changement de signature/constante/structure.
- `tests/integration/test_comfyui_lifecycle_manager.py` — import `QTimer` ajouté, **+6 tests nets** dans `ComfyUILifecycleManagerGuardTest` : `test_on_process_finished_stops_and_clears_the_terminate_timer_once_resolved`, `test_finish_process_teardown_stops_and_clears_a_residual_terminate_timer`, `test_stale_terminate_timeout_signal_is_ignored`, `test_terminate_timeout_from_the_current_timer_is_not_treated_as_stale`, `test_stale_terminate_timeout_from_a_resolved_stop_never_affects_a_later_start` (test de régression principal, reproduisant fidèlement le scénario cross-cycle du §2 contre un effet métier réel — le process du cycle B n'est jamais tué, son état n'est jamais altéré), `test_stale_terminate_timeout_from_a_resolved_stop_never_kills_a_later_running_owned_process` (variante silencieuse `RUNNING_OWNED` du même scénario).

**Résultats** :
- `ComfyUILifecycleManagerGuardTest` seule : **23/23** (17 existants inchangés + 6 nouveaux).
- `test_comfyui_lifecycle_manager.py` complet (les 2 classes, y compris les tests process-réel `ComfyUILifecycleManagerRealProcessTest`) : **31/31**, aucun flake sur ce run.
- `test_main_window_close_event.py` : **46/46**, non-régression confirmée.
- `test_inference_page.py` + `test_settings_page.py` (les deux autres fichiers référençant `ComfyUILifecycleManager`) : **320/320** — un traceback bénin et déjà pré-existant (`inference_page.py:789`/`:865`, `QLabel.setText(MagicMock)`), sans rapport avec ce diff, imprimé pendant le run sans provoquer d'échec, non-régression confirmée.
- **Suite complète** : **2792 tests collectés, 2792 passés, 0 échoué, exit 0 (334.878s)**. Équation : 2786 (clôture Mission 141) + 6 nets ajoutés par Mission 142 = **2792**, cohérent. Aucun flake Forge sur ce run (les lignes « Failed to copy »/« disk full »/« Access is denied » visibles dans le log sont des injections d'erreurs simulées volontaires de tests préexistants, pas des échecs réels — confirmé par `Ran 2792 tests ... OK` et zéro occurrence de `FAIL`/`ERROR`). `git diff --check` : propre (seuls des avertissements LF→CRLF inoffensifs).

**Smoke réel ComfyUI** : non effectué, décision justifiée après implémentation — le bug a été intégralement démontré et corrigé au niveau du lifecycle Qt automatisé, avec de vrais objets `QTimer` (jamais mockés) pour prouver `.stop()`/`isActive()`, et le comportement du process réel (terminate/kill sur le vrai `QProcess`, sans taskkill dans ce fichier) reste couvert, inchangé et toujours vert, par `ComfyUILifecycleManagerRealProcessTest` déjà existante (vrai process factice `_fake_comfyui_process.py`). Un smoke manuel avec une installation ComfyUI réelle n'apporterait aucune preuve supplémentaire sur le point précis corrigé (identité et cycle de vie d'un objet `QTimer` Python/Qt) et ajouterait un risque opérationnel (lancement réel d'un serveur ComfyUI) sans bénéfice de vérification correspondant.

**Écarts par rapport au design demandé** : aucun. L'implémentation suit exactement l'architecture retenue au §4 (réponse C, adaptée aux deux points de résolution propres à ComfyUI plutôt qu'au point unique de Forge), sans jeton de génération/cycle, sans changement de timeouts, sans modification hors de `src/ui/comfyui_lifecycle_manager.py` et `tests/integration/test_comfyui_lifecycle_manager.py`.
