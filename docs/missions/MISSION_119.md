# Mission 119 — Forge Local Lifecycle Management (Start/Stop/Ownership/Readiness)

> **MISSION CLÔTURÉE.** Implémentée, validée par la suite complète et par un smoke réel A/B/C contre une installation Forge réelle, commitée, taguée et publiée. Commit fonctionnel `745dbf57dd7b5b3fe54ef1b481eb3b7c71e42ac1` (`Add Forge Local lifecycle management (Start/Stop/ownership/readiness)`), tag `v0.2-mission119`, GitHub Release publiée.

## 1. Contexte

Depuis Mission 108, `ApplicationSettings.forge_url`/`forge_lora_expose_path` ne couvrent que la connexion API et l'exposition de la Central LoRA Library — Forge reste supposé démarré et arrêté manuellement par l'architecte. Missions 112/113 ont ajouté le diagnostic de joignabilité (`ForgeEngine.check_connection()`) et la validation statique de l'installation locale (`resolve_forge_install()`, `forge_path`), sans jamais lancer ni terminer le process réel. Mission 114 a livré ce lifecycle complet pour ComfyUI Local (`ComfyUILifecycleManager`), en documentant explicitement que le blocage Stop propre à Forge — son entrée réelle (`run.bat`) génère un `cmd.exe` qui lui-même ne fait qu'exécuter `python.exe launch.py` comme petit-enfant, jamais atteint par une terminaison Windows standard appliquée au seul process direct — restait entier et non résolu.

## 2. Objectif

Implémenter un lifecycle Forge Local fiable, strictement limité à Start/Stop/ownership/readiness et à son pilotage depuis `SettingsPage`, en reprenant le modèle `ComfyUILifecycleManager` (états explicites, readiness non bloquante, ownership strict jamais persisté, distinction backend Toolkit vs externe) partout où il s'applique tel quel, sans le copier mécaniquement là où le mode de lancement réel de Forge impose une stratégie différente.

## 3. Décision retenue

Audit empirique préalable du lancement réel (avant toute implémentation) :

- `QProcess` ne peut pas exécuter directement un `.bat` (`started=False` immédiat) — lancement via `cmd.exe ["/c", run_bat_path]`, seul point d'entrée fiable.
- `call` à l'intérieur d'un script batch n'ouvre jamais de nouveau process : `run.bat → environment.bat → webui-user.bat → webui.bat` s'exécutent tous dans le **même** `cmd.exe` ; seul l'appel final non-`call` `%PYTHON% launch.py` engendre un vrai process enfant (`python.exe`). Arbre réel confirmé : `cmd.exe → conhost.exe` (frère) + `python.exe launch.py` (enfant).
- `NoDefaultCurrentDirectoryInExePath=1` (confirmé actif sur cette machine) désactive la recherche de fichiers nus dans le répertoire courant par `cmd.exe`, cassant les `call environment.bat`/`call webui-user.bat` internes de `run.bat` — corrigé en prépendant `forge_root` et `forge_root\webui` au `PATH` du process enfant, via une copie de `QProcessEnvironment.systemEnvironment()` (jamais l'environnement du process Toolkit lui-même, jamais le registre).
- `taskkill /PID <pid> /T /F` vérifié empiriquement scopé strictement à l'arbre descendant du PID donné (`cmd.exe` + `conhost.exe` + `python.exe`), sans jamais affecter de process non apparenté. `QProcess.terminate()`/`.kill()` ne signalent que le seul process ciblé sur Windows, jamais ses descendants (confirmé empiriquement) — c'est pourquoi `taskkill` est le mécanisme principal de Stop, pas une solution de repli.

`src/engines/forge_launch.py::resolve_forge_launch()` (resolver Qt-free, hôte toujours restreint à `127.0.0.1`/`localhost` avec port explicite, `extra_path_dirs=(forge_root, forge_root/webui)`) ne construit jamais les arguments CLI propres de Forge (`--api`, etc.) — ceux-ci restent la responsabilité de `webui-user.bat`, contrat déjà posé par Mission 107.

`src/ui/forge_lifecycle_manager.py::ForgeLifecycleManager` reprend les six états de `ComfyUILifecycleManager` (`STOPPED`/`EXTERNAL_ACTIVE`/`STARTING`/`RUNNING_OWNED`/`STOPPING`/`START_FAILED`) et `src/ui/forge_readiness_worker.py::ForgeReadinessWorker` (readiness non bloquante sur `QThread` dédié, budget 120 s) — sans introduire de septième état pour les cas d'échec de confirmation, traités par un latch interne dédié (voir ci-dessous).

Quatre rounds de revue de sécurité, chacun audité/corrigé/testé avant validation :

1. **Confirmation du Stop** : `taskkill` est lancé via un `QProcess` réellement suivi (jamais `startDetached`), avec un rendez-vous à deux signaux — `_owned_process_gone` (fin du `cmd.exe` possédé) et `_taskkill_resolved` (issue réelle de `taskkill`, via `finished`/`errorOccurred`/timeout de `TERMINATE_TIMEOUT_SECONDS`). Découverte empirique déterminante : le `cmd.exe` possédé se termine **avant** que `taskkill` ne rapporte sa propre issue (jamais l'inverse) — d'où la nécessité d'un vrai rendez-vous plutôt que de conclure sur le premier signal reçu. `_stop_confirmed` ne devient vrai que sur code de sortie `0` de `taskkill`.
2. **Sécurité de la fermeture différée** : un Stop non confirmé ne referme jamais silencieusement Toolkit — `_abandon_pending_close_after_unconfirmed_stop()` affiche une erreur explicite (`QMessageBox.critical()`) et laisse Toolkit ouvert, au lieu de reprendre une fermeture différée (`_resume_close_if_pending()`, réservée à un Stop confirmé).
3. **Latch anti-duplication** : `_stop_unconfirmed`, interne et jamais persisté, s'arme sur tout Stop/cleanup non confirmé et bloque un nouveau `start()` tant qu'un backend externe confirmé (`EXTERNAL_ACTIVE`) ou un Stop confirmé ne l'a pas levé — sans introduire de septième état de la machine.
4. **Unification du cleanup readiness-timeout** : `_on_readiness_timed_out() → _terminate_owned_process()` partage exactement le même rendez-vous de confirmation (`_maybe_finish_teardown()`, renommé depuis `_maybe_finish_stopping()`) que le Stop explicite, distingué uniquement par le nouveau drapeau `_terminating_owned_process` — même contrat lifecycle/ownership appliqué au cleanup d'un Start échoué, sans dupliquer la logique ni perdre le message de cause de l'échec de readiness.

## 4. Comportement implémenté

| Élément | Comportement |
|---|---|
| `start()` | No-op hors `STOPPED`/`EXTERNAL_ACTIVE`/`START_FAILED`. Pré-vérifie `check_connection()` : succès → `EXTERNAL_ACTIVE`, latch levé ; échec avec `_stop_unconfirmed` armé → refus explicite sans lancer de process ; sinon → lancement réel via `cmd.exe /c run.bat`, readiness démarrée. |
| Readiness atteinte | `RUNNING_OWNED`. |
| Échec/timeout de readiness | Termine le process possédé via le même chemin que Stop, `START_FAILED` avec message de cause conservé (+ mention de non-confirmation si applicable). |
| `stop()` | `STOPPING` → `taskkill /PID <pid> /T /F` suivi réellement → `STOPPED` uniquement si confirmé, sinon `START_FAILED` explicite + latch armé. |
| Backend externe déjà actif | `EXTERNAL_ACTIVE`, aucun ownership pris, jamais affecté par `stop()`. |
| Fermeture de Toolkit | `MainWindow.closeEvent()` consulte `ForgeLifecycleManager.confirm_safe_to_close()` (même contrat que ComfyUI) ; un Stop différé non confirmé bloque la fermeture avec message explicite. |
| `SettingsPage` | Boutons Démarrer/Arrêter Forge + label de statut lifecycle, indépendants des contrôles préexistants (connexion M112, installation M113). |

## 5. Périmètre exact — fichiers concernés

- `src/engines/forge_launch.py` (nouveau) — `resolve_forge_launch()`, `ForgeLaunchConfig`, `ForgeLaunchError`.
- `src/ui/forge_lifecycle_manager.py` (nouveau) — `ForgeLifecycleManager`.
- `src/ui/forge_readiness_worker.py` (nouveau) — `ForgeReadinessWorker`.
- `src/ui/main_window.py` (modifié) — construction de `ForgeLifecycleManager`, guard de fermeture.
- `src/ui/pages/settings_page.py` (modifié) — boutons Démarrer/Arrêter Forge, label de statut.
- `tests/integration/test_forge_launch.py` (nouveau) — 10 tests.
- `tests/integration/test_forge_lifecycle_manager.py` (nouveau) — 48 tests (process réel factice, latch/rendez-vous fabriqués, confirmation de Stop avec `taskkill` réellement rendu indisponible, cleanup readiness-timeout).
- `tests/integration/test_settings_page.py` (modifié) — `SettingsPageForgeLifecycleTest` + smoke réel minimal.
- `tests/integration/test_main_window_close_event.py` (modifié) — `MainWindowCloseEventForgeLifecycleGuardTest`.

**Aucun changement** à `ForgeEngine`, `GenerationManager`, `InferencePage`, `ComfyUILifecycleManager`, Domain/Manager/Storage/EventBus.

## 6. Hors périmètre strict

- Auto-start Forge depuis `InferencePage` (mirroir du besoin fermé pour ComfyUI par Mission 115) — non implémenté.
- Pending génération Forge, message d'attente/bouton Annuler dans `InferencePage` (mirroir des Missions 116/117) — non implémenté.
- Toute refonte UX d'`InferencePage`, ComfyUI, Fooocus, providers cloud, vidéo/audio.

## 7. Tests

Suite complète : **2399/2399**, aucune régression. `git diff --check` propre. Trois scénarios de smoke réel exécutés contre l'installation réelle `J:\Programmes\WebUI Forge CU121` :

- **Scénario A** (Start Toolkit-owned) : `STOPPED → STARTING → RUNNING_OWNED`, arbre réel confirmé (`cmd.exe` + `python.exe`), `check_connection()` réel réussi, ~50 s de démarrage à froid.
- **Scénario B** (Stop) : `taskkill /T /F` termine réellement l'arbre entier, confirmé indépendamment via `tasklist`/`netstat` (port 7860 libéré), `STOPPED` confirmé (`stop_confirmed=True`).
- **Scénario C** (backend externe) : un Forge lancé en dehors de Toolkit est détecté `EXTERNAL_ACTIVE`, zéro ownership pris, process externe laissé strictement intact, non affecté par `stop()`.

Environnement Forge entièrement restauré à son état initial après le Scénario C. Aucun script de smoke conservé dans le dépôt.

## 8. Critères de clôture

1. Lifecycle Start/Stop/ownership/readiness fonctionnel pour Forge Local, piloté depuis `SettingsPage`.
2. Stop confirmé de façon fiable (rendez-vous à deux signaux) avant tout `STOPPED` — jamais un faux succès.
3. Aucune fermeture silencieuse de Toolkit sur un Stop non confirmé.
4. Aucune duplication/orphelin de process Forge possible après un Stop non confirmé (latch interne, non persisté).
5. Cleanup de readiness-timeout unifié avec le contrat de confirmation du Stop explicite, sans état supplémentaire.
6. Aucune modification de `ForgeEngine`, `GenerationManager`, `InferencePage`, Domain/Manager/Storage/EventBus/ComfyUI.
7. Suite complète verte au nombre exact, `git diff --check` propre, smoke réel A/B/C PASS.

## 9. Documentation

Cette mission ferme, pour Forge, le blocage Stop documenté depuis Mission 108/114 (`docs/PROJECT_CONTEXT.md`, entrée « Gestion automatique du backend Forge »). Restent explicitement non tranchés et hors périmètre : l'auto-start Forge depuis `InferencePage` et toute UX d'attente/annulation associée — mirroir des besoins déjà fermés pour ComfyUI par les Missions 115/116/117, non rouverts ici.

## 10. Autorisation

Mission autorisée par l'architecte avec contrainte architecturale explicite (reprendre `ComfyUILifecycleManager` où pertinent, sans copie mécanique), priorité technique absolue donnée à l'audit empirique du lancement réel et à la validation réelle du Stop avant de le considérer sûr, suivie de quatre rounds de revue de sécurité successifs (confirmation du Stop, sécurité de la fermeture différée, latch anti-duplication, unification du cleanup readiness-timeout) et d'un smoke réel A/B/C, chacun explicitement validé avant le suivant.
