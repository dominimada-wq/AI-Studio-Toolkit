# Mission 091 — Test Harness Reliability: Eliminate Unmocked Blocking QMessageBox in Generation-Active Tests

> **MISSION IMPLÉMENTÉE ET VALIDÉE PAR L'ARCHITECTE, CLÔTURE GIT EN COURS.** Voir section 7 pour l'état d'avancement.

## 1. Contexte

Pendant la clôture de Mission 090, deux full suites consécutives ont produit deux échecs intermittents différents (`test_inference_page.py`, puis `test_main_window_close_event.py`), tous deux dans la zone du threading `QThread` réel introduite par Mission 085 (guard « génération active »), sous une charge machine visiblement très élevée (durées ×3 par rapport à la normale). Un `git stash` a confirmé qu'un de ces échecs reproduisait à l'identique sur le code d'avant Mission 090, écartant une régression de cette mission — mais l'architecte a demandé un audit dédié plutôt que de classer cela comme un simple aléa non résolu de plus.

L'audit post-Mission 090 (agent d'exploration dédié, puis vérification manuelle ligne par ligne de chaque instance) a établi que le phénomène observé — de vraies `QMessageBox` bloquantes apparaissant parfois sur un écran secondaire, sans qu'aucun humain ne sache qu'un clic est attendu — n'est **pas** un aléa d'environnement mais un **bug reproductible et localisé du harness de test**, entièrement concentré sur un seul point d'entrée : `InferencePage.confirm_no_active_generation()` (`src/ui/pages/inference_page.py:917-946`, dialogue réel `QMessageBox.warning()` à la ligne 945). Ce guard, introduit par Mission 085, est le **premier** guard de `MainWindow.closeEvent()` et de `rename_project()` — et les tests qui pilotent une génération réellement active via l'idiome partagé `_controlled_generate()`/`_start_controlled_generation()` (également Mission 085) omettent systématiquement de le mocker, alors qu'ils mockent scrupuleusement tous les guards suivants dans la même chaîne. **10 instances exactes** ont été confirmées, vérifiées individuellement par lecture directe du code (pas seulement par l'agent) :

- `tests/integration/test_inference_page.py:2038,2080` (classe `InferencePageGenerationActiveGuardTest`)
- `tests/integration/test_main_window_close_event.py:743,770,785,806` (classe `MainWindowCloseEventRealStateTest`)
- `tests/integration/test_main_window_rename_project.py:418,433,445,460` (classe `MainWindowRenameGenerationActiveGuardTest`)

`tests/integration/test_main_window_new_project.py` (classe `MainWindowNewOpenGenerationActiveNonRegressionTest`) utilise le même idiome mais reste aujourd'hui saine : `new_project()`/`open_project()` n'ont délibérément jamais reçu ce guard (décision Mission 085 documentée), donc aucun dialogue réel n'y est jamais atteint.

Second mécanisme identifié, expliquant l'empilement de dialogues observé : `GenerationWorker.run()` (`src/ui/generation_worker.py:52-67`) attrape toute exception et la republie via son signal `failed`, connecté à `InferencePage._on_generation_failed()` (`inference_page.py:440-451`), qui affiche un **second** `QMessageBox.critical` réel — également non mocké dans ces mêmes 10 tests. Le timeout interne de 30s de `_controlled_generate()` (`RuntimeError("release_evt never set - test harness bug")`, observé littéralement comme message d'erreur affiché) peut se déclencher pendant qu'un premier dialogue est déjà bloqué sans clic, produisant exactement l'empilement de boîtes invisibles rapporté.

Un mini-audit contractuel dédié, mené avant toute écriture de code, a validé un premier mécanisme de filet de sécurité par **vérification empirique directe** (deux scripts Python réels exécutés dans cet environnement) : patcher `QMessageBox.exec` au niveau classe semblait intercepter correctement tout dialogue réel, y compris via les méthodes statiques `.warning()`/`.critical()` — avec la réserve déjà identifiée que **lever une exception depuis l'intérieur de ce patch est silencieusement avalée** par la frontière Shiboken/C++ quand l'appel transite par ces méthodes statiques (confirmé empiriquement, comportement non documenté), imposant de **capturer** puis **lever l'erreur après coup, en Python pur**.

**Écart de conception découvert pendant l'implémentation (accepté par l'architecte, voir section 4)** : ce premier mécanisme, bien que validé par le mini-audit, s'est révélé **inopérant en pratique** dès le premier test de démonstration réel — une vraie `QMessageBox` bloquante (`Critical Title`/`OK`) a exigé un clic humain, exactement le défaut que la mission visait à éliminer. Cause racine isolée après investigation directe : `QMessageBox.warning()`/`.critical()` sont des wrappers Shiboken autour des fonctions C++ **natives** de Qt (`QMessageBox::warning`/`::critical`), qui construisent leur propre instance `QMessageBox` C++ et appellent `.exec()` dessus par un appel de vtable C++ direct — jamais via un attribut Python. Un monkeypatch Python de `QMessageBox.exec` (qui ne modifie que le `__dict__` du type Python) n'a donc strictement aucun effet sur cet appel interne. Le mécanisme retenu en section 3.2 a été redesigné en conséquence, toujours sur la base d'une vérification empirique réelle dans cet environnement.

## 2. Objectif

Garantir qu'aucune suite de tests automatisés de ce projet ne puisse plus jamais rester bloquée indéfiniment à cause d'une vraie `QMessageBox` inattendue attendant un clic humain — sans modifier le comportement fonctionnel d'AI Studio Toolkit. Mission strictement de fiabilisation du harness de test.

## 3. Contrat final validé

### 3.1 Correctif primaire — les 10 tests fautifs

Chacune des 10 méthodes reçoit le mock positif exact déjà utilisé correctement ailleurs dans le même fichier pour ce même guard :
- `test_inference_page.py:2038,2080` : englober l'appel à `confirm_no_active_generation()` dans `with patch("src.ui.pages.inference_page.QMessageBox.warning"):` — mirroir exact de `test_confirm_refuses_and_shows_message_while_genuinely_active` (ligne 2033), déjà correcte.
- `test_main_window_close_event.py:743,770,785,806` : ajouter `patch("src.ui.pages.inference_page.QMessageBox")` à l'ensemble `with` existant (ou en créer un) englobant l'appel réel à `closeEvent()` — mirroir exact du patch déjà appliqué aux 4 autres pages dans `test_close_refused_immediately_while_generation_genuinely_active` (lignes 746-749), simplement complété par la 5ᵉ page manquante.
- `test_main_window_rename_project.py:418,433,445,460` : même principe, `patch("src.ui.pages.inference_page.QMessageBox")` autour de l'appel réel à `rename_project()`.

Aucune assertion existante n'est affaiblie ou supprimée — chaque test continue de vérifier exactement le même comportement qu'aujourd'hui (état du thread, `_pending_path`, workspace inchangé, etc.), seul le dialogue devient silencieux plutôt que réellement affiché.

### 3.2 Filet de sécurité — module partagé `tests/integration/_qt_dialog_safety_net.py`

**Version finalement implémentée (redesign en cours d'implémentation — voir la note d'écart en section 1 et le détail en section 4).** Le patch de `QMessageBox.exec` initialement validé par le mini-audit n'intercepte pas les méthodes statiques Qt (`.warning()`/`.critical()`/etc. sont des wrappers C++ natifs, jamais dispatchés via Python). Le mécanisme retenu détecte donc, depuis l'extérieur, toute vraie `QMessageBox` devenant réellement visible dans l'application :

```python
class UnexpectedDialogError(AssertionError):
    """A real QMessageBox appeared during a test and was never mocked."""

class _DialogGuard(QObject):
    """
    Combines a QApplication-wide QEvent.Show event filter (fires the
    instant a real QMessageBox is about to appear — the fast path) with
    a 15ms repeating QTimer scan of QApplication.topLevelWidgets() (an
    unconditional deterministic fallback), so a real dialog can never be
    left waiting for a human click regardless of who constructed it
    (pure Python code or Qt's internal C++ static convenience methods).
    The close itself is deferred by one event-loop tick
    (QTimer.singleShot(0, ...)) rather than done synchronously inside
    the Show-event filter — verified against QDialog.exec()'s own
    internal ordering (show() runs before its QEventLoop is created and
    assigned), so a synchronous close there would just hide the dialog
    while the not-yet-armed event loop still starts and blocks forever
    right after, an invisible hang worse than the original bug.
    """

@contextlib.contextmanager
def guard_against_unexpected_dialogs():
    """
    Starts the watcher for the duration of the block. Any real dialog
    that becomes visible is captured (title/text/buttons) and closed via
    .done() before a human could plausibly interact with it. If anything
    was captured, raises UnexpectedDialogError once the watcher is
    already stopped (plain Python, outside any Qt/C++ call stack).
    """

def start_dialog_guard():
    """Manual open/close pair for setUp()/tearDown() composition."""

def stop_dialog_guard(guard):
    ...
```

Appliqué aux 4 classes à risque via des appels explicites dans leurs `setUp()`/`tearDown()` **existants** (jamais via une classe mixin en héritage : vérifié que ces 4 classes n'appellent jamais `super().setUp()`/`super().tearDown()` aujourd'hui, rendant un mixin silencieusement inopérant) :
- `InferencePageGenerationActiveGuardTest` (`test_inference_page.py`)
- `MainWindowCloseEventRealStateTest` (`test_main_window_close_event.py`)
- `MainWindowRenameGenerationActiveGuardTest` (`test_main_window_rename_project.py`)
- `MainWindowNewOpenGenerationActiveNonRegressionTest` (`test_main_window_new_project.py`) — défense en profondeur, aucun bug actuel à corriger ici.

`start_dialog_guard()` en tout début de `setUp()` ; `stop_dialog_guard()` en tout dernier, dans un `finally` englobant le corps existant de `tearDown()` — pour que le filet reste actif jusqu'au bout du nettoyage (y compris `shutdown()`) et se restaure correctement même si le corps existant lève.

Aucune interférence avec les mocks déjà corrects (patcher `QMessageBox.warning` ou toute la classe `QMessageBox` d'un module ne passe jamais par le vrai `QMessageBox.exec` — vérifié) : le filet ne réagit qu'aux appels qui atteindraient réellement un `QMessageBox` non mocké, exactement les 10 cas visés et tout futur régression similaire dans ces 4 classes.

### 3.3 Démonstration volontaire du filet

Nouvelle classe de test dédiée (ex. `QtDialogSafetyNetTest`, dans un nouveau petit fichier `tests/integration/test_qt_dialog_safety_net.py`), utilisant directement `guard_against_unexpected_dialogs()` en `with` (jamais le couple `setUp()`/`tearDown()`, pour rester lisible en isolation) :
- provoque volontairement un vrai `QMessageBox.warning(...)`/`.critical(...)` non mocké à l'intérieur du `with` ;
- vérifie via `assertRaises(UnexpectedDialogError)` que l'erreur est bien levée, avec le titre/texte capturés présents dans le message ;
- vérifie que l'opération est bornée dans le temps (quelques millisecondes, jamais un blocage réel) ;
- confirme qu'aucun thread/processus Qt n'est laissé vivant après (rien n'a été démarré dans ce test — la preuve vient de la full suite exécutée immédiatement après, sans hang).

### 3.4 Threading et timeouts

`threading.Event` reste la primitive déterministe correcte pour la synchronisation cross-thread — aucun remplacement nécessaire. Les deux bornes techniques identifiées (`started.wait(timeout=5.0)`, `_wait_until(..., timeout=10.0)`), utilisées à l'identique dans les 4 fichiers concernés, sont portées à **15.0/30.0** (×3, proportionné au ralentissement réellement observé pendant la clôture M090) — un changement sûr et borné car ces valeurs ne sont jamais réellement consommées en cas de succès (le wait retourne dès que l'événement est posé), donc sans impact sur la durée normale de la suite.

`_pump(seconds)` (14 sites dans `test_inference_page.py`, répartis sur la quasi-totalité des classes du fichier, bien au-delà des 4 classes à risque) reste **explicitement hors périmètre** : c'est une pause à durée fixe non déterministe distincte de `_wait_until`, et sa conversion en attente déterministe toucherait un périmètre disproportionné pour cette mission — documentée comme dette résiduelle en section 6, non traitée ici.

### 3.5 Hors périmètre (confirmé)

Aucun changement de code applicatif (`src/`) sauf découverte contraire pendant l'implémentation, auquel cas STOP et rapport avant d'élargir. Aucun repositionnement forcé de fenêtre, `AlwaysOnTop`, ou autre workaround multi-écrans côté production — aucune preuve trouvée que les vraies `QMessageBox` de production soient mal parentées (toutes construites avec `self` comme parent). Aucun refactoring global des tests Qt du projet ni des autres pages (`ImagesPage`/`DatasetsPage`/`ModelsPage`/etc., dont les dialogues sont déjà correctement mockés selon l'audit). Aucune nouvelle dépendance externe (`pytest-timeout` ou équivalent) — mécanisme entièrement stdlib `unittest`/PySide6. **Confirmé tenu en fin de mission : zéro fichier `src/` modifié.**

### 3.6 Deux corrections de test supplémentaires révélées par le filet, une fois réellement fonctionnel

Une fois le redesign de la section 3.2 en place et réellement opérant, la première exécution des tests ciblés a révélé 7 échecs — non pas des faux positifs du filet, mais deux catégories de fragilités de test authentiques, jusqu'ici invisibles faute d'un filet capable de les détecter :

1. **Race de nettoyage de thread (5 tests, 3 fichiers)** : `MainWindowNewOpenGenerationActiveNonRegressionTest` (3 tests) et `MainWindowRenameGenerationActiveGuardTest` (2 tests) n'attendaient que `_pending_path`/l'existence du fichier de sortie avant la fin du test, sans attendre explicitement `_thread is None` — laissant une fenêtre où `InferencePage.is_generation_active()` pouvait encore répondre `True` au moment du vrai `window.close()`/`rename_project()` exécuté en `tearDown()`/`addCleanup()`, déclenchant le vrai dialogue "Génération en cours" de `confirm_no_active_generation()`. Corrigé en ajoutant l'attente déterministe `_wait_until(lambda: ...inference_page._thread is None, timeout=30.0)`, déjà utilisée correctement dans `test_no_crash_when_generation_finishes_well_after_new_project` (seul test de cette classe qui n'a jamais échoué).
2. **`_dirty` non réinitialisé après un choix Discard/Cancel sur fermeture (2 tests, `test_main_window_close_event.py`)** : `test_dirty_inference_prompt_discard_accepts_close_without_creating_prompt` et `test_dirty_settings_cancel_refuses_close_and_keeps_draft` ne réinitialisaient pas manuellement l'état "dirty" laissé par leur scénario avant la fin du test, contrairement à leurs tests voisins dans le même fichier qui le font déjà explicitement (ex. `test_dirty_inference_prompt_cancel_refuses_close_and_keeps_draft`). Or `InferencePage.confirm_context_change()`/`_confirm_discard_before_switch()` ne remettent `_dirty` à `False` que sur **Save** — le nettoyage normal d'un Discard passe par `reset_for_context_change()`, déclenché uniquement par un changement réel de Workspace, qui ne se produit jamais lors d'une simple fermeture de fenêtre. Comportement **vérifié identique et intentionnel** dans `PromptsPage.confirm_context_change()` (même structure exacte) — ce n'est donc pas un bug de production, seulement deux tests qui omettaient le reset manuel déjà pratiqué par leurs voisins. Corrigé à l'identique (`self.window.inference_page._dirty = False` / `self.window.settings_page._dirty = False` en fin de test).

Aucun changement de code applicatif n'a été nécessaire pour ces deux corrections — entièrement scopées aux fichiers de test.

## 4. Implémentation

Conforme au contrat de la section 3, avec l'écart de conception documenté en section 1 et le complément de la section 3.6 :

- `tests/integration/_qt_dialog_safety_net.py` (nouveau) : implémente `_DialogGuard` (watcher `QApplication`-wide combinant filtre d'événement `QEvent.Show` et `QTimer` de repli à 15 ms, fermeture différée via `QTimer.singleShot(0, ...)` puis `.done()`), `UnexpectedDialogError`, `guard_against_unexpected_dialogs()`, `start_dialog_guard()`/`stop_dialog_guard()` — remplace intégralement le design à base de patch de `QMessageBox.exec` initialement retenu par le mini-audit (voir section 1).
- `tests/integration/test_qt_dialog_safety_net.py` (nouveau) : 5 tests de démonstration volontaire (`.warning()` et `.critical()` réels déclenchés séparément, cas sans dialogue, nettoyage du timer/event-filter après usage, non-déclenchement sur un dialogue déjà mocké).
- `tests/integration/test_inference_page.py` : import du filet ; `start_dialog_guard()`/`stop_dialog_guard()` dans `setUp()`/`tearDown()` de `InferencePageGenerationActiveGuardTest` ; les 2 tests fautifs enveloppés du mock positif `QMessageBox.warning` déjà utilisé par leurs voisins corrects ; `started.wait(timeout=5.0)` → `15.0`.
- `tests/integration/test_main_window_close_event.py` : import du filet ; guard dans `setUp()`/`tearDown()` de `MainWindowCloseEventRealStateTest` ; les 4 tests fautifs enveloppés du mock positif `QMessageBox` déjà utilisé pour les 4 autres pages ; `started.wait` → `15.0` ; 5 occurrences `_wait_until(..., timeout=10.0)` → `30.0` ; les 2 corrections de la section 3.6 (reset `_dirty` manuel).
- `tests/integration/test_main_window_rename_project.py` : import du filet ; guard via `addCleanup` (classe sans `tearDown()` explicite, enregistré en premier pour s'exécuter en dernier, LIFO) dans `MainWindowRenameGenerationActiveGuardTest` ; les 4 tests fautifs enveloppés du mock positif `QMessageBox` ; `started.wait` → `15.0` ; 5 occurrences `timeout=10.0` → `30.0` ; les 2 corrections thread-race de la section 3.6.
- `tests/integration/test_main_window_new_project.py` : import du filet ; guard via `addCleanup` (même pattern) dans `MainWindowNewOpenGenerationActiveNonRegressionTest` (défense en profondeur, confirmée saine) ; `started.wait` → `15.0` ; 8 occurrences `timeout=10.0` → `30.0` (la pause intentionnelle `timeout=0.5` non touchée) ; les 3 corrections thread-race de la section 3.6.

Aucun fichier `src/` modifié.

## 5. Tests automatisés

- Tests ciblés des 4 fichiers concernés (`test_inference_page.py`, `test_main_window_close_event.py`, `test_main_window_rename_project.py`, `test_main_window_new_project.py`) : **220/220 OK**, 0 intervention humaine, 0 dialogue visible.
- Tests dédiés du nouveau filet (`test_qt_dialog_safety_net.py`) : **5/5 OK**, dialogues réels (`.warning()` et `.critical()`) déclenchés volontairement, capturés et convertis en `UnexpectedDialogError` en moins d'1 seconde chacun, aucun affichage à l'écran, timer/event-filter proprement nettoyés après usage.
- Full suite, exécutée deux fois consécutivement sans aucune intervention : **1702/1702 OK** à chaque run (~165 s puis ~169 s) — 1697 tests de la baseline Mission 090 + 5 nouveaux tests du filet.
- Aucun processus/thread Qt résiduel constaté après chaque run (vérifié).
- `git diff --check` : propre (seuls avertissements CRLF/LF cosmétiques liés à `core.autocrlf`, aucune violation réelle).

## 6. Conclusion

Mission de fiabilisation du harness de test entièrement remplie : les 10 instances confirmées par l'audit ne peuvent plus jamais déclencher de vraie `QMessageBox` bloquante, et un filet de sécurité générique protège désormais les 4 classes à risque contre toute régression future du même type — y compris via les méthodes statiques Qt (`.warning()`/`.critical()`), grâce au redesign fondé sur la détection de visibilité plutôt que sur l'interception d'appel. Le filet a lui-même permis de découvrir et corriger deux fragilités de test additionnelles (race de nettoyage de thread, reset `_dirty` manquant) qui étaient restées invisibles jusqu'ici. Aucun changement de comportement fonctionnel d'AI Studio Toolkit n'a été nécessaire — la mission reste strictement circonscrite au harness de test, conformément au contrat.

Dette résiduelle explicitement documentée et non traitée dans cette mission : la conversion de `_pump(seconds)` (14 sites dans `test_inference_page.py`, hors des 4 classes à risque) en attente déterministe.

## 7. État d'avancement et clôture Git

- Mini-audit contractuel : **terminé**, validé par l'architecte.
- Contrat détaillé (section 3) : **validé par l'architecte**.
- Implémentation : **terminée**, y compris l'écart de conception documenté en section 1 et les 2 corrections supplémentaires de la section 3.6, tous deux validés explicitement par l'architecte a posteriori.
- Tests ciblés (220/220), tests du filet (5/5), deux full suites consécutives (1702/1702 chacune) sans aucune intervention humaine ni dialogue visible, aucun processus Qt résiduel : **exécutés et validés**.
- Clôture Git (commit/tag/Release) : **en cours**.
