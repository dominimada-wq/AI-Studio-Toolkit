# Mission 147 — Fix `confirm_safe_to_close()` Modal Reentrancy Race (Forge + ComfyUI)

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en cours.** `ForgeLifecycleManager.confirm_safe_to_close()` et `ComfyUILifecycleManager.confirm_safe_to_close()` assignaient `_pending_close_widget` puis appelaient `stop()` sans jamais relire `self._state` après le retour de `QMessageBox.question()` — une régression directe de Mission 146 : si le process possédé meurt spontanément pendant que ce dialogue modal est ouvert (la boucle d'événements Qt imbriquée qu'il pompe continue de livrer les signaux Qt en attente, dont `QProcess.finished`), la nouvelle branche M146 fait `RUNNING_OWNED → START_FAILED` *avant* que l'utilisateur ne clique « Oui ». `stop()` devenait alors un no-op silencieux (l'état n'est plus `RUNNING_OWNED`), `confirm_safe_to_close()` retournait quand même `False`, et `_pending_close_widget` restait une référence dangling indéfiniment — la fenêtre ne se fermait pas, sans aucune erreur affichée, et un cycle Stop ultérieur totalement sans rapport pouvait plus tard fermer l'application par surprise. Corrigé indépendamment pour chaque manager par une simple relecture de l'état après le dialogue — aucune abstraction commune, aucun nouveau popup, aucun changement de teardown/timer. **+6 tests nets** (2833 → 2839 tests collectés), suite complète finale 2839/2839, 0 échoué — voir §12/§13 pour le détail des tests et le rapport d'implémentation transmis pour le détail complet des résultats réels.

## 1. Root cause commune

Les deux `confirm_safe_to_close(parent_widget)` suivent le même schéma, structurellement daté d'avant Mission 146 et jamais révisé depuis :

```
état == RUNNING_OWNED
  → QMessageBox.question(...)          # boucle d'événements Qt imbriquée
  → answer == Yes
      → self._pending_close_widget = parent_widget   # AUCUNE relecture de self._state
      → self.stop()                                  # relit self._state en interne, mais trop tard
      → return False                                 # valeur figée, indépendante du résultat réel de stop()
```

`QDialog.exec()` (utilisé en interne par la fonction statique `QMessageBox.question()`) démarre une boucle d'événements locale qui continue de traiter l'intégralité de la file d'événements du thread principal — timers armés, et surtout les signaux Qt déjà postés ou émis pendant cette fenêtre, dont `QProcess.finished`. Seule la livraison des événements d'entrée utilisateur (clic, clavier) vers les widgets sous le champ du modal est bloquée ; la livraison de signal/slot ne l'est jamais. C'est exactement ce mécanisme qui permet à la nouvelle branche Mission 146 (`elif self._state == RUNNING_OWNED:` dans `_on_process_finished()`, pour les deux managers) de s'exécuter *pendant* l'appel à `QMessageBox.question()`, avant qu'il ne retourne.

Avant Mission 146, cette même mort spontanée pendant le dialogue ne produisait aucune transition d'état (l'état restait `RUNNING_OWNED` figé indéfiniment) — `stop()`, appelé après le « Oui », voyait donc encore `RUNNING_OWNED`, constatait le process déjà `NotRunning` via son propre re-check interne, et résolvait normalement vers `STOPPED` → fermeture réussie silencieusement. Le correctif M146 élimine ce chemin périmé-mais-inoffensif et le remplace par une transition d'état réelle (`START_FAILED`) qui atterrit désormais dans une fenêtre de réentrance auparavant impossible.

## 2. Preuve exacte — Forge (`src/ui/forge_lifecycle_manager.py:597-632`)

```python
def confirm_safe_to_close(self, parent_widget) -> bool:
    if self._state in (STARTING, STOPPING):
        QMessageBox.warning(...)
        return False

    if self._state != RUNNING_OWNED:
        return True

    answer = QMessageBox.question(
        parent_widget, "Forge en cours d'exécution",
        "Forge a été démarré par AI Studio Toolkit. "
        "Voulez-vous également arrêter Forge ?",
        QMessageBox.Yes | QMessageBox.No,
    )
    if answer == QMessageBox.No:
        return True

    self._pending_close_widget = parent_widget
    self.stop()
    return False
```

`stop()` (`forge_lifecycle_manager.py:472-489`) relit `self._state` :
```python
def stop(self) -> None:
    if self._state == STARTING:
        ...  # non applicable ici
    if self._state != RUNNING_OWNED:
        return          # no-op silencieux si l'état a changé pendant le dialogue
    self._set_state(STOPPING)
    self._terminate_owned_process()
```

Si l'état est passé à `START_FAILED` pendant le dialogue (via `_on_process_finished()`, `forge_lifecycle_manager.py:354-365`), `stop()` fait un `return` immédiat — `_terminate_owned_process()` (et donc tout le mécanisme `taskkill`/rendez-vous à deux drapeaux/`_terminating_owned_process`) **n'est jamais engagé**. `_pending_close_widget` reste positionné. `_resume_close_if_pending()` (`forge_lifecycle_manager.py:634-638`) et `_abandon_pending_close_after_unconfirmed_stop()` (`forge_lifecycle_manager.py:640-665`) ne sont tous deux atteints que depuis `_maybe_finish_teardown()` (branche `STOPPING`), jamais atteinte ici puisque l'état n'est jamais entré en `STOPPING`.

## 3. Preuve exacte — ComfyUI (`src/ui/comfyui_lifecycle_manager.py:341-378`)

```python
def confirm_safe_to_close(self, parent_widget) -> bool:
    if self._state in (STARTING, STOPPING):
        QMessageBox.warning(...)
        return False

    if self._state != RUNNING_OWNED:
        return True

    answer = QMessageBox.question(
        parent_widget, "ComfyUI en cours d'exécution",
        "ComfyUI a été démarré par AI Studio Toolkit. "
        "Voulez-vous également arrêter ComfyUI ?",
        QMessageBox.Yes | QMessageBox.No,
    )
    if answer == QMessageBox.No:
        return True

    self._pending_close_widget = parent_widget
    self.stop()
    return False
```

Structurellement identique, en plus simple : ComfyUI n'a ni `taskkill`, ni rendez-vous à deux drapeaux, ni `_terminating_owned_process`, ni `_abandon_pending_close_after_unconfirmed_stop()` — seul `_resume_close_if_pending()` (`comfyui_lifecycle_manager.py:380-384`) existe, atteint uniquement depuis `_on_process_finished()`/`_finish_process_teardown()` (branche `STOPPING`), jamais atteinte ici pour la même raison que Forge. `stop()` (`comfyui_lifecycle_manager.py:283-300`) fait le même `if self._state != RUNNING_OWNED: return` no-op.

**Conclusion** : les deux managers sont **symétriques dans ce scénario précis** — `_pending_close_widget` reste dangling silencieusement pour les deux, sans aucun message, jusqu'à un cycle Stop ultérieur sans rapport (voir §8 pour la conséquence différée exacte de chaque manager, qui elle diverge).

## 4. Contrat comportemental cible (validé, commun aux deux managers)

```
RUNNING_OWNED
  → QMessageBox.question(...) ouvert
  → [le process meurt spontanément pendant le dialogue -- ou non]
  → answer == No  → return True                                    (inchangé)
  → answer == Yes → relire self._state MAINTENANT
       si self._state == RUNNING_OWNED (inchangé) :
           → comportement historique exact, inchangé :
             _pending_close_widget = parent_widget
             self.stop()
             return False
       si self._state != RUNNING_OWNED (uniquement START_FAILED atteignable, voir §7) :
           → NE PAS assigner _pending_close_widget
           → NE PAS appeler stop()
           → return True
           → MainWindow.closeEvent() poursuit normalement ses guards suivants
```

Aucune distinction d'état supplémentaire n'est introduite au-delà de ce simple test binaire — voir §7 (un seul état cible existe réellement, `START_FAILED`, ce qui rend une branche `elif` par état non justifiée par le code actuel).

## 5. Conception Forge — point d'insertion exact

Dans `confirm_safe_to_close()` (`forge_lifecycle_manager.py`), entre la ligne `if answer == QMessageBox.No: return True` et l'affectation de `_pending_close_widget` :

```python
if answer == QMessageBox.No:
    return True

if self._state != RUNNING_OWNED:
    # Mission 147: le process possédé a disparu tout seul pendant le
    # dialogue modal (Mission 146) -- rien à arrêter, la fermeture est
    # déjà sûre sans confirmation supplémentaire.
    return True

self._pending_close_widget = parent_widget
self.stop()
return False
```

Aucune autre méthode de `ForgeLifecycleManager` n'est modifiée. `_terminate_owned_process()`, `_maybe_finish_teardown()`, `_on_terminate_timeout()`, `_abandon_pending_close_after_unconfirmed_stop()`, le mécanisme `taskkill`, `_stop_confirmed`/`_stop_unconfirmed`/`_terminating_owned_process` restent strictement inchangés — ce correctif est purement additif et localisé dans `confirm_safe_to_close()`.

## 6. Conception ComfyUI — point d'insertion exact

Même correctif, même emplacement relatif, dans `confirm_safe_to_close()` (`comfyui_lifecycle_manager.py`) :

```python
if answer == QMessageBox.No:
    return True

if self._state != RUNNING_OWNED:
    # Mission 147: symétrique à ForgeLifecycleManager -- voir MISSION_147.md.
    return True

self._pending_close_widget = parent_widget
self.stop()
return False
```

Aucune autre méthode de `ComfyUILifecycleManager` n'est modifiée. `_terminate_owned_process()`, `_on_terminate_timeout()`, `_finish_process_teardown()`, le repli `terminate()`→`kill()` restent strictement inchangés.

**Aucune abstraction commune** entre les deux managers — deux correctifs symétriques indépendants, cohérent avec la politique déjà appliquée par M141/M142/M146.

## 7. États atteignables pendant le modal (analyse verrouillée par le mini-audit)

Pendant que `RUNNING_OWNED` et que le dialogue est ouvert, **aucun timer interne à l'une ou l'autre classe n'est armé** (`_terminate_timer` n'existe que pendant `STOPPING` ; le `_readiness_thread`/`_readiness_worker` n'existe que pendant `STARTING`). La seule source d'événement asynchrone pouvant modifier l'état est le `QProcess` réellement possédé lui-même (`self._process`), via `finished`/`errorOccurred`.

| État cible | Chemin réel ? | Analyse |
|---|---|---|
| **`START_FAILED`** | **Oui — seul chemin réel** | Mort spontanée du process possédé → `QProcess.finished` → branche M146 `elif self._state == RUNNING_OWNED:`. Aucun `stop()`/`start()` n'est déclenché par autre chose pendant le dialogue (aucun timer armé ; `QMessageBox.question` étant modal, aucun clic utilisateur sur un autre contrôle du même `MainWindow` — seule fenêtre de premier niveau de l'application — ne peut être délivré pendant que le dialogue attend une réponse). |
| `STOPPED` | Non | N'est atteignable que via un `stop()` déjà résolu — rien n'appelle `stop()` pendant le dialogue. |
| `STOPPING` | Non | Nécessite un appel `stop()` explicite, impossible avant le retour du dialogue. |
| `STARTING` | Non | Nécessite un appel `start()` explicite depuis `STOPPED`/`EXTERNAL_ACTIVE`/`START_FAILED` — aucune de ces transitions n'est déclenchée pendant le dialogue. |
| `EXTERNAL_ACTIVE` | Non | Même raison — n'est jamais atteint que depuis `start()`. |

`_on_process_error_occurred()` ne réagit qu'à `self._state == STARTING` — un no-op pendant `RUNNING_OWNED`, même si `QProcess` émet `errorOccurred(Crashed)` en plus de `finished` sur un crash. Ne modifie donc jamais la conclusion ci-dessus.

**Verdict verrouillé** : un seul état cible est réellement atteignable de façon asynchrone pendant le dialogue à partir de `RUNNING_OWNED` : `START_FAILED`. Le test `self._state != RUNNING_OWNED` du §4/§5/§6 est donc suffisant — aucune branche supplémentaire par état n'est justifiée par le code actuel, et il ne faut pas en ajouter une par anticipation.

## 8. B2 — aucun nouveau popup (décision confirmée, hors scope)

Décision provisoire de ChatGPT confirmée par le mini-audit : **aucun nouveau popup informatif** pour le cas où le process s'est déjà terminé pendant que l'utilisateur répond au dialogue. L'utilisateur a déjà demandé à fermer l'application et accepté l'arrêt du backend ; si celui-ci est déjà mort, la condition qu'il souhaitait est déjà silencieusement satisfaite.

- Le correctif des §5/§6, en retournant `True` sans jamais appeler `stop()` ni assigner `_pending_close_widget`, empêche par construction toute apparition future — différée et hors contexte — du message critique Forge `_abandon_pending_close_after_unconfirmed_stop()` (« Impossible de confirmer l'arrêt de Forge »), qui n'est atteint que via un `_pending_close_widget` resté positionné. C'est un effet secondaire positif du correctif, obtenu sans aucune modification de cette méthode.
- **B2 n'est donc pas engagé par cette mission** au sens où `_abandon_pending_close_after_unconfirmed_stop()` (Forge) reste totalement inchangée, hors scope, continuant de servir son propre cas d'usage (un Stop réellement lancé mais dont le teardown échoue à se confirmer).
- Aucune raison de sécurité/comportement n'exige un message dans le scénario visé ici.
- Forge et ComfyUI ne sont **pas** artificiellement symétrisés par cette mission — Forge garde son mécanisme de message pour son propre cas (Stop non confirmé après un vrai teardown), ComfyUI n'en a pas et n'en a pas besoin ; ni l'un ni l'autre n'est touché par le correctif ci-dessus.

## 9. MainWindow.closeEvent() — contrat inchangé, vérifié

`closeEvent()` (`src/ui/main_window.py:820-931`) est une chaîne séquentielle stricte de 11 guards, chacun de forme `if not guard(): event.ignore(); return`. Les guards ComfyUI (ligne 858) et Forge (ligne 865) sont interrogés en 3e/4e position, avant les 6 guards de brouillon non enregistré et avant `inference_page.shutdown()`.

Vérifié par cette mission (aucune modification requise dans `main_window.py`) :
- `confirm_safe_to_close() == False` → `event.ignore(); return` immédiat, aucun guard suivant ne s'exécute.
- `confirm_safe_to_close() == True` → simple passage au guard suivant dans la chaîne — jamais un raccourci de fermeture en lui-même.
- Un `return True` pris dans la nouvelle branche du §4 **ne contourne aucun brouillon non enregistré** (les 6 guards suivants s'exécutent normalement), **ne contourne aucun autre lifecycle/backend** (le guard de l'autre manager, dans l'ordre ComfyUI puis Forge, s'exécute normalement ensuite), et **ne provoque aucune double fermeture** : contrairement au chemin « Oui, état inchangé », ce nouveau chemin ne programme jamais de `.close()` différé (`_pending_close_widget` n'est jamais assigné) — le mécanisme de reprise déjà testé et vert (`test_real_running_owned_yes_defers_close_until_stop_actually_finishes`, `tests/integration/test_main_window_close_event.py:558-591`) reste totalement inchangé et n'est simplement jamais activé dans ce nouveau chemin.

## 10. Reproduction déterministe de la race (référence pour les tests, voir §12/§13)

```python
def _kill_process_during_dialog(*args, **kwargs):
    self.manager._state = START_FAILED
    self.manager._process = None
    return QMessageBox.Yes

with patch("src.ui.comfyui_lifecycle_manager.QMessageBox") as box:
    box.Yes, box.No = QMessageBox.Yes, QMessageBox.No
    box.question.side_effect = _kill_process_during_dialog
    result = self.manager.confirm_safe_to_close(parent)
# comportement actuel (avant correctif) : result is False, _pending_close_widget est parent (dangling)
# comportement attendu (après correctif) : result is True, _pending_close_widget reste None
```

Aucun test existant (dans les trois fichiers concernés) n'utilise `side_effect` sur `QMessageBox.question` — tous utilisent `return_value` statique et mockent `stop()` lui-même, ce qui masque structurellement cette race. Aucun vrai `QProcess` n'est nécessaire : le bug est une réentrance de dialogue Qt, pas une race de timing sur un process réel — un test déterministe par `side_effect` en constitue une preuve plus forte.

## 11. Autres appelants de `stop()` — vérifiés, aucun autre correctif nécessaire

| Appelant | Fichier:ligne | Classification |
|---|---|---|
| `SettingsPage.stop_comfyui()` | `settings_page.py:879` | **SAFE** — appel direct et synchrone depuis un clic bouton (activé uniquement quand `state == RUNNING_OWNED`), aucune boucle d'événements imbriquée entre la lecture d'état et l'appel ; `stop()` relit de toute façon `self._state` en interne. |
| `SettingsPage.stop_forge()` | `settings_page.py:934` | **SAFE** — identique, symétrique. |
| `ForgeLifecycleManager.confirm_safe_to_close()` | `forge_lifecycle_manager.py:631` | **SAME RACE** — sujet de cette mission, corrigé par §5. |
| `ComfyUILifecycleManager.confirm_safe_to_close()` | `comfyui_lifecycle_manager.py:377` | **SAME RACE** — sujet de cette mission, corrigé par §6. |
| `InferencePage` | — | **NOT APPLICABLE** — n'appelle jamais `stop()` sur l'un ou l'autre manager (confirmé par grep et par les commentaires explicites `inference_page.py:353`/`:1972`). |

Aucun autre fichier de production ne reproduit le pattern « lire l'état → opération réentrante/asynchrone → `stop()` ».

## 12. Tests requis — Forge (`tests/integration/test_forge_lifecycle_manager.py`)

1. `RUNNING_OWNED` + `Yes` + état inchangé pendant le dialogue → comportement historique exact préservé (`_pending_close_widget` assigné, `stop()` appelé, `return False`) — non-régression des tests existants (`test_confirm_safe_to_close_running_owned_yes_defers_close_until_stopped`), à revérifier verts sans modification attendue.
2. `RUNNING_OWNED` + `No` → aucune modification — non-régression de `test_confirm_safe_to_close_running_owned_no_leaves_forge_running`.
3. `RUNNING_OWNED` + transition déterministe vers `START_FAILED` pendant le dialogue (via `side_effect`, voir §10) + `Yes` → `confirm_safe_to_close()` retourne `True`.
4. Dans le scénario 3 : `_pending_close_widget` reste `None` après l'appel.
5. Dans le scénario 3 : `stop()` n'est jamais appelé (`patch.object(self.manager, "stop")` + `assert_not_called()`).
6. Dans le scénario 3 : aucun teardown déclenché — `_terminate_owned_process` jamais appelé, `_taskkill_process is None`, `_terminate_timer is None`, `_terminating_owned_process` reste `False`.
7. Absence de fermeture différée parasite ultérieure : après le scénario 3, un cycle Start+Stop normal et distinct plus tard (avec un nouveau `parent.close` en `MagicMock`) ne doit jamais déclencher `parent.close()` de façon inattendue — `_pending_close_widget is None` avant et après ce cycle ultérieur.
8. Non-régression du teardown volontaire : `RUNNING_OWNED` + `Yes` + état inchangé pendant le dialogue + `stop()` réellement exécuté (non mocké) → le teardown Forge (`taskkill`, rendez-vous à deux drapeaux) se déroule normalement, `_resume_close_if_pending()` ferme bien la fenêtre au bout du compte — revérification des tests déjà existants et déjà verts, aucun nouveau test nécessaire pour ce point.

Tous unitaires/mockés, déterministes par `side_effect` — aucun vrai `QProcess` requis pour cette mission (le bug testé est une réentrance de dialogue Qt).

## 13. Tests requis — ComfyUI (`tests/integration/test_comfyui_lifecycle_manager.py`)

Même matrice, miroir exact des points 1 à 8 du §12, adaptée à l'absence de `_terminating_owned_process`/`_taskkill_process`/rendez-vous chez ComfyUI (le point 6 se limite à vérifier `_terminate_timer is None` et l'absence d'appel à `_terminate_owned_process`).

## 14. Suites voisines à revérifier (non-régression, aucune modification attendue)

- `tests/integration/test_main_window_close_event.py` — les classes `MainWindowCloseEventComfyUILifecycleGuardTest`/`MainWindowCloseEventForgeLifecycleGuardTest` existantes, en particulier `test_real_running_owned_yes_defers_close_until_stop_actually_finishes` (et son équivalent Forge) : doivent rester vertes sans modification, puisque le chemin qu'elles couvrent (état inchangé pendant le dialogue) n'est pas touché par ce correctif.
- Si jugé utile pour couvrir explicitement l'interaction d'orchestration (le nouveau `return True` laisse bien `closeEvent()` continuer vers le guard suivant), un test d'orchestration supplémentaire peut être ajouté dans ce fichier — décision de rédaction, sans impact sur le contrat.
- `tests/integration/test_settings_page.py` — non-régression des boutons Démarrer/Arrêter, aucun changement attendu.

## 15. Exclusions confirmées (non-goals explicites)

Aucun nouveau popup/message informatif (§8, décision B2) ; aucune harmonisation de message entre Forge et ComfyUI ; aucun refactor du lifecycle ; aucun nouvel état ; aucune modification de `_on_process_finished()` ou de tout autre comportement introduit par Mission 146 ; aucune modification du teardown Forge (`_terminate_owned_process()`, `_maybe_finish_teardown()`, `taskkill`, rendez-vous à deux drapeaux) ; aucune modification du teardown ComfyUI (`terminate()`/`kill()`) ; aucune modification de `_abandon_pending_close_after_unconfirmed_stop()` ; aucune modification de `MainWindow.closeEvent()` ni de `SettingsPage` ; le race `TrainingJobRunner` Cancel-vs-achèvement-naturel (candidat distinct de l'audit post-M146) ; Workspace create failure cleanup ; `create_job()` partial cleanup ; caption sidecars ; `rolling_backup` OneTrainer ; Training Resume ; `ComfyUIEngine` gestion des erreurs HTTP ; flakiness Forge des tests réel-process ; toute autre dette identifiée par l'audit global post-M146.

## 16. Fichiers attendus

- `src/ui/forge_lifecycle_manager.py` (production)
- `src/ui/comfyui_lifecycle_manager.py` (production)
- `tests/integration/test_forge_lifecycle_manager.py` (tests)
- `tests/integration/test_comfyui_lifecycle_manager.py` (tests)
- `tests/integration/test_main_window_close_event.py` (tests, seulement si un test d'orchestration supplémentaire est jugé utile — voir §14)
- `docs/missions/MISSION_147.md` (documentation)

Aucun autre fichier de production n'est identifié comme nécessaire — en particulier `main_window.py` et `settings_page.py` restent inchangés (§9/§11). Si la rédaction détaillée de l'implémentation révèle qu'un fichier hors de cette liste doit être modifié, ce point devra être signalé et justifié avant toute modification — jamais ajouté silencieusement au scope.
