# Mission 114 — ComfyUI Local Lifecycle (Start / Ownership / Readiness / Stop)

> **MISSION CLÔTURÉE — LIFECYCLE COMFYUI LOCAL (START/STOP/OWNERSHIP/READINESS) LIVRÉ, SUITE COMPLÈTE 2289/2289, SMOKE RÉEL DOUBLE SCÉNARIO PASS.** Commit fonctionnel `de618eab4876de38795d3d749df8320e12be83aa` (`Add ComfyUI Local lifecycle management (Start/Stop/ownership/readiness)`), tag `v0.2-mission114`, GitHub Release publiée. Voir `CHANGELOG.md` (`## v0.2-mission114`) pour le résumé complet et le détail des tests ajoutés. Le contrat ci-dessous, rédigé avant implémentation, a été respecté avec deux corrections mineures fondées sur des preuves réelles (voir §13 « Écarts constatés à la clôture ») : le budget de readiness est passé de 60s à **120s**, et le resolver ajoute `--user-directory`/`--database-url` en plus de ce que §3 décrivait initialement.

## 1. Contexte

Le micro-audit de cadrage post-Mission 113 (lecture seule, aucun process ComfyUI lancé) a établi, par inspection directe du code réel :

- `ComfyUIEngine.check_connection()` (`comfyui_engine.py:356-371`, Mission 112) est un wrapper de `list_checkpoints()` : toute erreur (serveur injoignable, `HTTPError`, JSON invalide) lève `ComfyUIEngineError` **sans distinguer la cause** — `_request_json()` (`comfyui_engine.py:591-611`) confirme qu'une erreur réseau et une réponse structurellement invalide empruntent exactement le même chemin. Un échec de `check_connection()` ne peut donc jamais être documenté comme la preuve qu'aucun processus ComfyUI n'existe.
- `resolve_comfyui_install()` (`src/engines/comfyui_install.py`, Mission 113) ne valide que `<comfyui_install_path>/resources/ComfyUI/main.py` ; il ignore `comfyui_path` et ne valide donc jamais l'interpréteur Python.
- Le seul précédent de resolver combinant plusieurs pièces d'un même lancement est `resolve_onetrainer_launch()` (`src/engines/onetrainer_launch.py`, Mission 100), mais il ne combine qu'une seule racine (`onetrainer_path`) — ComfyUI diverge structurellement : le Python (`.venv/Scripts/python.exe`) vit sous `comfyui_path`, `main.py` vit sous `comfyui_install_path`, deux racines confirmées distinctes par l'audit environnemental de Mission 113.
- `ApplicationSettings.comfyui_url` (`application_settings.py:46`) est un `str` brut, jamais parsé nulle part dans le code actuel.
- `src/ui/training_job_runner.py` est le seul précédent réel de gestion de process via `QProcess` dans ce dépôt : `started`/`log_line`/`finished`, arrêt en trois temps (stop coopératif → `terminate()` avec attente bornée `TERMINATE_TIMEOUT_SECONDS = 10.0` → `kill()`). Conçu pour un job **borné** avec un protocole de pipe coopératif propre à OneTrainer — jamais réutilisé tel quel pour un service long-lived comme ComfyUI, qui n'a aucun protocole d'arrêt coopératif connu de ce dépôt.
- `src/ui/generation_worker.py` est le précédent établi pour exécuter un appel bloquant hors du thread UI : un `QObject` avec une méthode `run()`, déplacé vers un `QThread` via `moveToThread()`, démarré par `QThread.started`, communiquant son résultat par signaux — c'est le mécanisme Qt déjà présent dans ce dépôt pour tout appel réseau potentiellement bloquant, réutilisé ici pour le polling de readiness plutôt qu'un nouveau mécanisme.
- `MainWindow.closeEvent()` (`main_window.py:785-825`) bloque déjà la fermeture sur un état actif/ambigu via deux guards non-dirty (`confirm_no_active_generation()` Mission 085, `confirm_no_active_training()` Mission 100), chacun avec le contrat `True=proceed/False=abandon`, jamais d'arrêt automatique silencieux. Ce précédent guide directement le comportement de fermeture retenu ci-dessous.
- `SettingsPage` regroupe déjà, dans cet ordre, tous les contrôles ComfyUI : `comfyui_path` (+Parcourir) → `comfyui_install_path` (+Parcourir) → validation d'installation (Mission 113) → `onetrainer_path` → `comfyui_url` → test de connexion (Mission 112) → sélection de checkpoint. Trois informations resteront donc visuellement distinctes après cette mission : installation valide/invalide (M113), connexion HTTP joignable/non joignable (M112), lifecycle/ownership Toolkit (M114).

## 2. Objectif

Permettre à l'utilisateur de démarrer et arrêter ComfyUI Local depuis `SettingsPage`, sans jamais devoir lancer ComfyUI Desktop manuellement au préalable — avec un contrat d'ownership strict (Toolkit n'arrête jamais un backend qu'il n'a pas lui-même lancé) et sans bloquer le thread UI pendant l'attente de disponibilité réelle de l'API. Cette mission ne connecte pas encore ce lifecycle à `InferencePage`/`GenerationManager` — elle livre la fondation réutilisable qu'une mission ultérieure pourra consommer pour un auto-start déclenché par Generate.

## 3. Décision retenue — architecture

**`ComfyUIEngine` reste un client HTTP pur** — aucune responsabilité process ajoutée, aucun changement à son contrat existant ou à celui de `GenerationManager`/`InferencePage`.

**Nouveau resolver Qt-free** `src/engines/comfyui_launch.py` :

```python
class ComfyUILaunchError(Exception): ...

class ComfyUILaunchConfig(NamedTuple):
    python_executable: str
    entry_point: str
    working_directory: str
    listen_host: str  # toujours "127.0.0.1"
    port: int

def resolve_comfyui_launch(comfyui_path: str, comfyui_install_path: str, comfyui_url: str) -> ComfyUILaunchConfig:
    # 1. comfyui_path vide/blanc -> ComfyUILaunchError actionnable
    # 2. <comfyui_path>/.venv/Scripts/python.exe absent -> ComfyUILaunchError actionnable
    # 3. resolve_comfyui_install(comfyui_install_path) réutilisé tel quel pour entry_point
    #    (ComfyUIInstallError propagée telle quelle, jamais ré-enveloppée)
    # 4. urllib.parse.urlparse(comfyui_url) ; host absent de {"127.0.0.1", "localhost"} -> ComfyUILaunchError
    #    ; port absent/non numérique -> ComfyUILaunchError ; URL non parsable -> ComfyUILaunchError
    # 5. host "localhost" normalisé en listen_host="127.0.0.1" ; jamais "0.0.0.0"
```

Ce contrat ne modifie ni `ComfyUIEngine` (qui reste configurable pour toute URL, y compris distante — restriction de lancement seulement, pas de restriction de client HTTP) ni `resolve_comfyui_install()`/`resolve_onetrainer_launch()`, réutilisés inchangés.

**Nouveau composant Qt** `src/ui/comfyui_lifecycle_manager.py::ComfyUILifecycleManager(QObject)` — possède le `QProcess` réellement lancé par Toolkit, jamais un backend externe. Six états explicites (`Enum` ou constantes `str`, pas de state machine générique) :

```
STOPPED · EXTERNAL_ACTIVE · STARTING · RUNNING_OWNED · STOPPING · START_FAILED
```

**Readiness non bloquante** : un second composant Qt minimal, `ComfyUIReadinessWorker(QObject)` — même patron exact que `GenerationWorker` (Mission 013) : une méthode `run()` déplacée vers un `QThread` dédié via `moveToThread()`, démarrée par `QThread.started`. `run()` boucle en interne (sur le thread du worker, jamais celui de l'UI) : appelle `check_connection(timeout=2.0)` ; succès → émet `ready` et retourne immédiatement ; échec → `time.sleep(1.0)` puis reboucle, jusqu'à un budget total borné. Aucun nouveau framework de polling générique — le seul mécanisme Qt déjà utilisé deux fois dans ce dépôt (`GenerationWorker`, et la paire `QTimer` de `training_job_runner.py` pour ses propres délais).

## 4. Comportement contractuel

1. **Résolution** : `resolve_comfyui_launch(comfyui_path, comfyui_install_path, comfyui_url)` est appelé à chaque clic sur « Démarrer » — jamais mise en cache d'une résolution précédente, exactement le principe déjà retenu par `resolve_onetrainer_launch()` (revalidé à chaque lancement réel, jamais fait confiance à un état de bouton).
2. **Backend déjà actif** : avant tout `QProcess.start()`, un appel synchrone `check_connection()` est tenté (ponctuel, même coût que le bouton « Tester la connexion » de Mission 112 — pas de polling à ce stade). Succès → état `EXTERNAL_ACTIVE`, aucun `QProcess` créé, aucun ownership pris, bouton Stop désactivé/sans effet. Échec → tentative de lancement réelle engagée ; un échec de ce check n'est **jamais** documenté comme preuve qu'aucun process n'existe — un conflit de port réel se manifestera naturellement via `QProcess.errorOccurred`/`finished` ou via l'expiration du timeout de readiness (jamais deviné à l'avance).
3. **Host/port/local-only** : liste blanche stricte `{"127.0.0.1", "localhost"}` pour le host de `comfyui_url` — tout autre host refuse le Start avec un message actionnable. `--listen` reçoit toujours exactement `"127.0.0.1"`, jamais `"0.0.0.0"`, jamais une valeur dérivée d'un host arbitraire. Ceci concerne uniquement le Start local de cette mission — le contrat général de `ComfyUIEngine` (client HTTP configurable pour toute URL, y compris distante) reste inchangé.
4. **Readiness** : `QProcess.started` fait transiter `STOPPED → STARTING`, jamais directement `RUNNING_OWNED`. `ComfyUIReadinessWorker` est démarré immédiatement après, sur son propre `QThread` — le thread UI n'est jamais bloqué par l'attente HTTP. Premier succès de `check_connection()` → `STARTING → RUNNING_OWNED`, polling arrêté immédiatement (le worker retourne, son `QThread` est arrêté/nettoyé). Timeout global atteint sans succès → nettoyage obligatoire (`terminate()` → attente bornée → `kill()` si nécessaire) puis `STARTING → START_FAILED`, avec un message indiquant que ComfyUI n'est pas devenu disponible dans le délai attendu, citant un conflit de port comme **possibilité**, jamais comme diagnostic certain. Si le `QProcess` se termine (signal `finished`) avant tout succès de readiness → `STARTING → START_FAILED` immédiat, polling arrêté.
5. **Timeout readiness retenu** : budget total **60 secondes**, intervalle de poll **1 seconde**, timeout par tentative HTTP individuelle **2 secondes** (`check_connection(timeout=2.0)`) — valeurs conservatrices non calibrées contre un vrai démarrage ComfyUI (chargement de `torch`/scan des `custom_nodes` pouvant prendre plusieurs dizaines de secondes), à ajuster après le smoke réel si nécessaire. Aucune de ces valeurs ne bloque le thread UI : elles bornent uniquement la boucle interne du worker sur son propre thread.
6. **Stop** : réservé strictement à un `QProcess` possédé (`RUNNING_OWNED → STOPPING`). `terminate()` → attente bornée **10 secondes** (même valeur que `TERMINATE_TIMEOUT_SECONDS` de `training_job_runner.py`, déjà calibrée dans ce dépôt) → `kill()` si le process n'a pas quitté. Idempotent (un second appel pendant un Stop déjà en cours, ou après un Stop déjà terminé, est un no-op). `STOPPING → STOPPED` une fois le `QProcess` réellement terminé. Si `check_connection()` reste vrai après ce Stop, c'est un signal explicite qu'une **autre** instance répond désormais sur cette URL — jamais interprété comme un échec du Stop lui-même, jamais une preuve pour retenter un `terminate()`/`kill()` sur autre chose.
7. **Ownership jamais persistant** : aucun PID, aucun état lifecycle écrit dans `ApplicationSettings` ou tout autre stockage. Au prochain démarrage de Toolkit, l'état lifecycle repart toujours à `STOPPED` ; si ComfyUI tourne encore (laissé actif volontairement à une fermeture précédente), un clic sur « Démarrer » le détectera via `check_connection()` et transitionnera vers `EXTERNAL_ACTIVE` — Toolkit ne tente jamais de « récupérer » un ownership antérieur.
8. **Fermeture de Toolkit** (`MainWindow.closeEvent()`) : nouveau guard `ComfyUILifecycleManager.confirm_safe_to_close(parent_widget) -> bool`, inséré juste après `confirm_no_active_training()` et avant les quatre guards dirty-state, même contrat `True=proceed/False=abandon` :
   - `STOPPED` / `START_FAILED` / `EXTERNAL_ACTIVE` → aucune confirmation, aucune tentative d'arrêt, fermeture normale.
   - `RUNNING_OWNED` → `QMessageBox.question` explicite (« ComfyUI a été démarré par AI Studio Toolkit. Voulez-vous également arrêter ComfyUI ? », boutons Oui/Non) : **Oui** → Stop synchrone du process possédé (bornée par les mêmes délais qu'au point 6) puis fermeture poursuivie ; **Non** → fermeture poursuivie, ComfyUI laissé actif, aucun ownership persisté nulle part.
   - `STARTING` / `STOPPING` → fermeture **bloquée** (retourne `False`, mirroir exact de `confirm_no_active_training()`), avec un message expliquant qu'un démarrage/arrêt de ComfyUI est en cours et qu'il faut attendre son issue avant de fermer — jamais de `QProcess` possédé abandonné dans un état ambigu pendant la destruction de l'UI.
9. **UX Settings** : deux boutons (« Démarrer »/« Arrêter », activation mutuellement exclusive selon l'état) + un label de statut lifecycle, positionnés juste après la ligne de test de connexion (Mission 112) et avant la sélection de checkpoint — troisième information visuellement distincte des labels d'installation (M113) et de connexion (M112), jamais fusionnée avec eux.
10. **Portée ComfyUI Local uniquement** : aucune structure ne suppose qu'un futur ComfyUI Cloud possède un exécutable/venv/process local — `resolve_comfyui_launch()`/`ComfyUILifecycleManager` prennent uniquement `comfyui_path`/`comfyui_install_path`/`comfyui_url` en entrée, aucune interface `Provider`/`Executor` générique introduite.

## 5. Périmètre exact — fichiers concernés

- `src/engines/comfyui_launch.py` (nouveau) — `resolve_comfyui_launch()`, `ComfyUILaunchConfig`, `ComfyUILaunchError`.
- `src/ui/comfyui_lifecycle_manager.py` (nouveau) — `ComfyUILifecycleManager`, états, `confirm_safe_to_close()`.
- `src/ui/comfyui_readiness_worker.py` (nouveau) — `ComfyUIReadinessWorker`, patron `GenerationWorker`.
- `src/ui/main_window.py` (modifié) — construction de `ComfyUILifecycleManager`, branchement du nouveau guard dans `closeEvent()`.
- `src/ui/pages/settings_page.py` (modifié) — boutons Démarrer/Arrêter + label lifecycle.
- `tests/integration/test_comfyui_launch.py` (nouveau).
- `tests/integration/test_comfyui_lifecycle_manager.py` (nouveau).
- `tests/integration/test_settings_page.py` (modifié).
- `tests/integration/test_main_window_close_guards.py` ou fichier équivalent déjà existant pour les guards de fermeture (modifié — nom exact à confirmer par audit du fichier réel au moment de l'implémentation).

**Aucun changement attendu** à `src/engines/comfyui_engine.py`, `src/managers/generation_manager.py`, `src/ui/pages/inference_page.py`, `src/engines/comfyui_install.py`, `src/engines/onetrainer_launch.py`, `src/engines/forge_engine.py`, `src/engines/forge_install.py`, Domain, EventBus — si l'implémentation réelle révèle qu'un changement dans l'un de ces fichiers est nécessaire, arrêt et rapport avant tout élargissement.

## 6. Hors périmètre strict — ne pas ajouter à cette mission

- Forge (Start, Stop, ownership) — aucun changement à `ForgeEngine`/`forge_path`/`forge_url`.
- ComfyUI Cloud — aucune abstraction Provider/Executor, aucune implémentation.
- Auto-start déclenché depuis `InferencePage`/`GenerationManager` (« Generate → ComfyUI absent → auto-start ») — différé à une mission ultérieure, non préjugée comme étant M115.
- Toute persistance d'ownership/PID dans `ApplicationSettings` ou ailleurs.
- Toute tentative de résolution de PID externe, de scan de ports, ou de récupération d'un ownership antérieur au redémarrage de Toolkit.
- Toute modification du contrat général de `ComfyUIEngine` (reste un client HTTP configurable pour toute URL).
- Tout protocole d'arrêt coopératif propre à ComfyUI (aucun mécanisme de ce type n'est documenté ou requis ici — `terminate()`/`kill()` suffisent, ComfyUI étant un enfant direct du `QProcess`).

## 7. Étape technique attendue

**`src/engines/comfyui_launch.py`** : voir §3 pour le contrat exact — mêmes principes que `comfyui_install.py`/`onetrainer_launch.py` (docstring expliquant la distinction avec les resolvers existants, exceptions à message actionnable, `NamedTuple` de résultat, aucun import Qt).

**`src/ui/comfyui_readiness_worker.py`** : `QObject` avec `run()` (aucun paramètre Qt dans le constructeur au-delà de ce qui est strictement nécessaire — `ComfyUIEngine` déjà construit, budget total, intervalle de poll), signaux `ready`/`timed_out`, boucle interne avec `time.sleep()`, jamais de `QTimer` ici (le `QTimer` reste pertinent uniquement pour orchestrer le teardown du thread depuis `ComfyUILifecycleManager`, pas pour le polling lui-même).

**`src/ui/comfyui_lifecycle_manager.py`** : possède `QProcess` + `QThread`/`ComfyUIReadinessWorker`, expose l'état courant (propriété ou signal `state_changed`), méthodes `start()`/`stop()`/`confirm_safe_to_close(parent_widget)`. Suit le patron d'assemblage déjà utilisé par `InferencePage` pour `GenerationWorker` (`moveToThread()`, connexion `thread.finished`, nettoyage symétrique).

**`src/ui/main_window.py`** : construction de `self.comfyui_lifecycle_manager` après `self.comfyui_engine` (même position logique) ; nouveau guard dans `closeEvent()`, inséré après `confirm_no_active_training()`.

**`SettingsPage`** : deux nouveaux boutons + label, méthodes `start_comfyui()`/`stop_comfyui()` déléguant directement à `comfyui_lifecycle_manager`, mise à jour du label sur chaque signal de changement d'état.

## 8. Tests attendus

**`tests/integration/test_comfyui_launch.py`** (répertoires temporaires réels, jamais l'installation machine, même famille que `test_comfyui_install.py`) : `comfyui_path` vide → erreur ; `.venv/Scripts/python.exe` absent → erreur citant ce chemin ; `main.py` absent (via `resolve_comfyui_install()`) → erreur propagée ; host hors liste blanche → erreur ; port absent/non numérique → erreur ; URL non parsable → erreur ; `localhost` normalisé en `127.0.0.1` ; cas complet réussi.

**`tests/integration/test_comfyui_lifecycle_manager.py`** (process factice déterministe, jamais un vrai ComfyUI — même principe que le harnais `training_job_runner` déjà existant pour OneTrainer) :
- `check_connection()` simulée réussie avant Start → `EXTERNAL_ACTIVE`, aucun `QProcess` créé, Stop no-op.
- `check_connection()` simulée en échec → Start engagé, transition `STOPPED → STARTING`.
- Readiness réussie après N tentatives simulées → `STARTING → RUNNING_OWNED`, polling arrêté (aucun appel `check_connection()` supplémentaire après le succès).
- Process qui se termine avant readiness → `STARTING → START_FAILED`.
- Timeout global de readiness atteint → nettoyage (`terminate()`/`kill()` simulés) puis `START_FAILED`.
- Stop sur `RUNNING_OWNED` → `terminate()` puis `STOPPING → STOPPED` ; fallback `kill()` si le process factice ignore `terminate()`.
- Stop idempotent (appel répété sans effet indésirable).
- Stop refusé/no-op sur `EXTERNAL_ACTIVE`.
- `check_connection()` restant vrai après un Stop réussi → état/label distinct, jamais un nouvel appel `terminate()`/`kill()`.
- `confirm_safe_to_close()` : `True` immédiat pour `STOPPED`/`START_FAILED`/`EXTERNAL_ACTIVE` ; dialogue Oui/Non simulé pour `RUNNING_OWNED` (Oui → Stop puis `True` ; Non → `True` sans Stop) ; `False` pour `STARTING`/`STOPPING`.

**`tests/integration/test_settings_page.py`** : boutons Démarrer/Arrêter activés/désactivés selon l'état lifecycle ; label lifecycle distinct des labels M112/M113 (modifier l'un ne modifie jamais les deux autres) ; smoke Qt réel avec le lifecycle manager construit contre un process factice (jamais un vrai ComfyUI).

**Guards de fermeture** : test du nouveau guard dans le fichier de tests `MainWindow.closeEvent()` déjà existant — `RUNNING_OWNED` avec Oui/Non simulés, `STARTING`/`STOPPING` bloquant la fermeture, `EXTERNAL_ACTIVE` fermant sans dialogue.

## 9. Smoke réel prévu (non exécuté sans autorisation explicite)

Scénario 1 (ownership Toolkit) : ComfyUI fermé → Démarrer depuis Toolkit → process Python réellement lancé → `STARTING` → API réellement prête → `RUNNING_OWNED` → test de connexion HTTP (M112) réussi → Arrêter depuis Toolkit → backend réellement injoignable → aucun process ComfyUI possédé laissé actif.

Scénario 2 (détection externe) : ComfyUI démarré extérieurement (Desktop ou manuellement) → Toolkit le détecte via `check_connection()` → `EXTERNAL_ACTIVE` → aucun second lancement proposé/exécuté → Stop refusé/sans effet pour cette instance.

## 10. Critères de clôture

1. `resolve_comfyui_launch()` implémenté et testé selon §8, aucune modification de `resolve_comfyui_install()`/`resolve_onetrainer_launch()`.
2. `ComfyUILifecycleManager`/`ComfyUIReadinessWorker` implémentés, six états couverts, readiness jamais bloquante pour le thread UI (prouvé par test).
3. Ownership strict démontré par test : jamais de `terminate()`/`kill()` sur `EXTERNAL_ACTIVE`.
4. Fermeture de Toolkit couverte pour les six états, jamais de `QProcess` possédé abandonné dans un état ambigu.
5. Zéro modification d'`InferencePage`, `GenerationManager`, `ComfyUIEngine`, `ForgeEngine`/`forge_path`, ComfyUI Cloud — sauf anomalie réelle découverte et rapportée avant tout élargissement.
6. Suite complète verte au nombre exact, `git diff --check` propre.
7. Aucun élément de la section 6 (hors périmètre) n'a été ajouté.
8. Smoke réel exécuté uniquement après autorisation explicite, les deux scénarios du §9 validés.

## 11. Documentation

Cette mission referme, pour ComfyUI Local uniquement, le sous-point « démarrage/arrêt automatique » resté ouvert dans `docs/PROJECT_CONTEXT.md` depuis le mini-audit post-Mission 105 — l'entrée Forge équivalente reste, elle, entièrement ouverte et non affectée. La régularisation documentaire post-clôture suivra le même processus que les missions précédentes, après commit/tag/Release.

## 12. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte.

## 13. Clôture réelle — écarts constatés, smoke réel, anomalies hors périmètre

**Implémentation** : les 11 fichiers listés au §5 ont été livrés exactement tels que prévus (aucun fichier supplémentaire, aucune omission). Un bug Qt réel a été découvert et corrigé pendant l'implémentation, non anticipé par ce contrat : connecter un signal cross-thread (`worker.ready`/`worker.timed_out`) à un `lambda` plutôt qu'à une méthode liée d'un `QObject` fait exécuter le slot sur le thread émetteur plutôt que sur le thread du destinataire (une `lambda` n'a pas d'affinité de thread Qt introspectable) — un `QTimer` créé dans le mauvais thread ne se déclenchait alors jamais. Corrigé en connectant des méthodes liées réelles et en récupérant le worker émetteur via `self.sender()`.

**Écart n°1 — budget de readiness** : le §3/§4 prévoyait 60 secondes. Le premier smoke réel (scénario A) a échoué à ce budget — ComfyUI n'avait pas atteint l'état prêt. Un relancement diagnostique unique autorisé, avec capture complète stdout/stderr, a confirmé que le port HTTP s'ouvrait réellement à 58,9s sur la machine de référence (initialisation CUDA/PyTorch + scan des `custom_nodes`, incluant un import `comfyui-fluxtrainer` systématiquement en échec à cause d'une incompatibilité de version `transformers`, non liée à cette mission). Le budget a été porté à **120 secondes** — intervalle de poll (1s) et timeout par tentative (2s) inchangés.

**Écart n°2 — arguments de lancement** : le même diagnostic a révélé une erreur réelle et jusque-là non observée, `Failed to initialize database ... unable to open database file`, absente de l'audit initial. `resolve_comfyui_launch()` a été enrichi avec exactement deux arguments supplémentaires, tous deux dérivés de `comfyui_path` : `--user-directory <comfyui_path>\user` et `--database-url sqlite:///<comfyui_path>/user/comfyui.db` (format à trois slashes, chemin en slashes avant, copié à l'identique de la commande réelle observée dans les logs ComfyUI Desktop). Aucun autre argument Desktop (`--front-end-root`, `--input-directory`, `--output-directory`, `--extra-model-paths-config`, `--enable-manager`, `--log-stdout`) n'a été ajouté — le diagnostic réel a prouvé que la commande minimale sans ces arguments atteint bien un état HTTP prêt (ComfyUI recourt à son propre package `comfyui_frontend_package` embarqué et à ses valeurs par défaut).

**Smoke réel — Scénario A (ownership Toolkit)** : PASS complet après la correction ci-dessus. Démarrage réel du process Python, `STARTING → RUNNING_OWNED` confirmé par un vrai test HTTP, Stop réel avec repli `kill()` effectivement nécessaire (`terminate()` seul insuffisant sur cette machine pour ce process console Windows), zéro process orphelin, zéro thread résiduel constatés après coup.

**Smoke réel — Scénario B (backend externe)** : PASS complet. Un ComfyUI démarré manuellement par l'architecte est détecté immédiatement comme `EXTERNAL_ACTIVE`, sans second lancement, sans ownership pris, Stop neutralisé, fermeture de Toolkit sans dialogue ni tentative d'arrêt, backend externe confirmé toujours joignable après le test.

**Anomalies environnementales observées, explicitement hors périmètre M114, non corrigées** :
- Incompatibilité `comfyui-fluxtrainer` / version `transformers` installée (custom node en échec d'import constaté dans les logs du smoke réel) — problème d'environnement Python de l'installation ComfyUI de la machine, sans rapport avec le lifecycle Start/Stop livré ici.
- Erreur Alembic `Can't locate revision identified by '0006_add_loader_path'`, observée pendant le smoke réel après correction de l'écart n°2 — problème de migration de la base ComfyUI existante sur cette machine, sans rapport avec le contrat de lancement/lifecycle de cette mission.

Ces deux anomalies ne sont pas transformées en mission future par ce document — elles restent des observations environnementales, à ne traiter que si un besoin réel futur le justifie.

**Tests** : 49 tests ciblés nets nouveaux (2240 → 2289 après les deux corrections), suite complète verte, `git diff --check` propre.

**Périmètre respecté** : aucune modification de Forge, d'`InferencePage`/`GenerationManager` (aucun auto-start câblé), aucune abstraction Provider/Executor pour un futur ComfyUI Cloud.
