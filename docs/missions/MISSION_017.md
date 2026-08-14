# Mission 017 — Dashboard Actions Wiring

Source : audit read-only préalable (état Git, code réel, tests réels), spécification validée par l'architecte, implémentation réalisée et vérifiée par exécution réelle de la suite de tests complète. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur dans ce document tant que la clôture Git n'a pas eu lieu.

## Contexte

`DashboardPage` (`src/ui/pages/dashboard_page.py`) déclare quatre boutons d'action depuis l'origine du projet : `newProjectButton`, `openProjectButton`, `importImagesButton`, `trainingButton`. Les comportements qu'ils devraient déclencher existent déjà ailleurs dans l'application : `MainWindow.new_project()` (Mission 016, flux `NewProjectDialog → WorkspaceManager.create()`), `MainWindow.open_project()`, et `ImagesPage.import_images()`. Aucune session d'entraînement réelle n'existe (`TrainingPage`/`TrainingManager` couvrent uniquement la *définition* d'une session depuis Mission 008 — "aucun bouton de lancement, aucune console", décision explicite non révisée depuis).

## Problème constaté

Audit du code réel (Phase 1, lecture seule) : aucun des quatre boutons `DashboardPage` n'est connecté à quoi que ce soit. Recherche exhaustive (`grep` sur tout `src/`) : aucune occurrence de `.clicked.connect(...)` sur ces quatre boutons, ni dans `dashboard_page.py` lui-même, ni dans `main_window.py`. Ce sont des boutons visibles, cliquables, strictement inertes — un défaut UX réel, observable, non couvert par aucun test existant (aucun fichier `test_dashboard*.py` au moment de l'audit).

## Objectif

Rendre les trois premiers boutons du Dashboard fonctionnels en réutilisant strictement les comportements déjà existants, sans dupliquer la moindre logique métier dans `DashboardPage`. Trancher explicitement le sort de `trainingButton` : bouton visible, désactivé, avec un tooltip explicite — plutôt qu'un comportement factice.

## Périmètre

**In scope**
- `DashboardPage.newProjectButton` → déclenche exactement `MainWindow.new_project()` (flux Mission 016 inchangé : `NewProjectDialog → WorkspaceManager.create()`).
- `DashboardPage.openProjectButton` → déclenche exactement `MainWindow.open_project()`.
- `DashboardPage.importImagesButton` → déclenche exactement `ImagesPage.import_images()` (flux existant inchangé, y compris ses `QMessageBox` de résultat).
- `DashboardPage.trainingButton` → reste visible, devient explicitement désactivé (`setEnabled(False)`), porte un tooltip clair sur l'indisponibilité du lancement réel d'entraînement.
- Tests couvrant le comportement observable des quatre boutons depuis `DashboardPage`/`MainWindow`.

**Out of scope** (voir section dédiée en fin de document)

## Décisions

- **Aucune duplication de logique** : `DashboardPage` ne reçoit aucune dépendance Manager/Workspace nouvelle. Le câblage des trois premiers boutons est effectué au niveau de `MainWindow` (composition root déjà responsable de tout le câblage EventBus/Manager existant), qui possède déjà `self.dashboard_page`, `self.images_page`, `self.new_project()` et `self.open_project()`.
- **`importImagesButton`** est connecté directement à `self.images_page.import_images` (méthode publique déjà existante) — pas de méthode intermédiaire dans `MainWindow`, puisqu'aucune orchestration supplémentaire n'est nécessaire (contrairement à `new_project()`/`open_project()`, qui sont déjà les points d'entrée canoniques exposés par `MainWindow` pour ces actions).
- **Aucune navigation automatique ajoutée** après import depuis le Dashboard : le bouton "Importer des images" natif d'`ImagesPage` ne navigue déjà vers aucune autre page après import (vérifié par lecture de `images_page.py`) — reproduire un comportement identique signifie ne rien ajouter. Naviguer automatiquement vers `ImagesPage` serait un comportement nouveau, non demandé, non nécessaire fonctionnellement.
- **`trainingButton`** : configuration purement présentationnelle (`setEnabled(False)` + `setToolTip(...)`), appliquée directement dans `DashboardPage.__init__` — aucune dépendance externe requise, donc aucune raison de faire remonter cette décision à `MainWindow`. Texte retenu : *"Lancement de l'entraînement non disponible dans cette version."* (texte recommandé par l'architecte, repris tel quel).
- Aucun nouveau Domain, Manager, Service, Engine, Job, Plugin. Aucune nouvelle dépendance.

## Architecture retenue

```
DashboardPage.newProjectButton.clicked   → MainWindow.new_project()          (inchangé, Mission 016)
DashboardPage.openProjectButton.clicked  → MainWindow.open_project()         (inchangé)
DashboardPage.importImagesButton.clicked → ImagesPage.import_images()        (inchangé, appelé directement)
DashboardPage.trainingButton             → désactivé + tooltip (Presentation pure, aucun câblage MainWindow)
```

Câblage effectué dans `MainWindow.__init__`, au même endroit et selon le même style que le câblage EventBus déjà en place (`self.menu.action_new_project.triggered.connect(self.new_project)` etc.) — trois lignes `connect()` supplémentaires, aucune méthode intermédiaire créée dans `MainWindow` pour `importImagesButton` (appel direct à la méthode déjà publique d'`ImagesPage`).

`DashboardPage` reste une vue UI pure : elle ne reçoit toujours aucune référence à un Manager, à `WorkspaceManager`, ni à `ImagesPage`. Le câblage reste entièrement une responsabilité de composition de `MainWindow`, cohérent avec le principe déjà établi que les Pages n'orchestrent jamais d'autres Pages entre elles.

## Tests

Comportement observable exercé via de vrais widgets Qt (`MainWindow` réel, clic réel sur les boutons `DashboardPage` — pas une simple vérification que `.connect()` a été appelé). Réalisé exactement comme spécifié, dans un unique nouveau fichier `tests/integration/test_dashboard_page.py` (6 tests) :

1. `test_new_project_button_accepted_calls_workspace_manager_create` — clic sur `dashboard_page.newProjectButton` avec `NewProjectDialog` patché (accepté) → `WorkspaceManager.create()` appelé exactement une fois avec le `target_path` attendu.
2. `test_new_project_button_cancelled_never_calls_create` — clic avec dialogue annulé → `WorkspaceManager.create()` jamais appelé.
3. `test_open_project_button_calls_workspace_manager_open` — clic sur `dashboard_page.openProjectButton` avec `QFileDialog.getExistingDirectory` patché → `WorkspaceManager.open()` appelé exactement une fois avec le dossier attendu.
4. `test_import_images_button_actually_adds_the_image_to_the_workspace` — clic sur `dashboard_page.importImagesButton`, Workspace réel ouvert, `QFileDialog.getOpenFileNames` patché pour retourner un fichier réel temporaire → l'image est effectivement ajoutée à `Workspace.images` (comportement observable de bout en bout, vérifié sur l'état réel du Domain, pas un simple espionnage d'appel).
5. `test_training_button_is_disabled` — `dashboard_page.trainingButton.isEnabled()` → `False`.
6. `test_training_button_tooltip_explains_unavailability` — `dashboard_page.trainingButton.toolTip()` → contient le message d'indisponibilité.

**Résultat Mission 017 seule** : `Ran 6 tests in 0.673s — OK` (6/6, verts au premier passage, aucune correction nécessaire).

**Résultat suite complète** : `Ran 231 tests in 74.872s — OK` (231/231 : 225 tests préexistants inchangés + 6 nouveaux, aucune régression constatée sur Mission 016 (création de projet), l'ouverture de Workspace, l'import d'images, Inference/Generate/Preview/Accept/Reject/Regenerate, `ImagePreviewDialog`, `ComfyUIEngine`, la persistance du pending state, le changement de Workspace, ni la fermeture de l'application).

Non-régression confirmée : les tests déjà existants pour `new_project()`/`open_project()`/`save_project()` directement appelés (`test_main_window_new_project.py`, sans passer par le Dashboard) restent verts sans aucune modification de ce fichier.

## Critères d'acceptation — état final

- `newProjectButton` réutilise `MainWindow.new_project()` sans seconde logique de création : ✅.
- `openProjectButton` réutilise `MainWindow.open_project()` sans duplication de dialogue/logique Workspace : ✅.
- `importImagesButton` réutilise `ImagesPage.import_images()` sans logique d'import recréée dans `DashboardPage` : ✅.
- `trainingButton` reste visible, est désactivé, porte un tooltip clair sur l'indisponibilité du lancement réel : ✅ (aucun handler connecté, aucun faux comportement).
- Aucune logique fonctionnelle dupliquée dans `DashboardPage` : ✅ — `DashboardPage` ne reçoit aucune nouvelle dépendance (ni Manager, ni `WorkspaceManager`, ni `ImagesPage`), le câblage reste entièrement dans `MainWindow`.
- Aucun nouveau Domain, Manager, Service, Engine, Job ou Plugin : ✅.
- Comportements couverts par des tests utilisant de vrais widgets Qt, exerçant un comportement observable (pas une simple présence de `.connect()`) : ✅ (6 tests, voir "Tests" ci-dessus).
- Suite de tests complète verte, nombre exact confirmé : ✅ (231/231).
- Aucune régression sur Mission 016 (création de projet), ouverture Workspace, import d'images, Inference/Generate/Preview/Accept/Reject/Regenerate, `ImagePreviewDialog`, `ComfyUIEngine`, persistance du pending state, changement de Workspace, fermeture de l'application : ✅.
- Aucune nouvelle dépendance ajoutée : ✅, `requirements.txt` inchangé.
- Aucune modification hors périmètre : ✅, vérifié par `git status`/`git diff --stat`.

## Fichiers modifiés / créés

- `src/ui/pages/dashboard_page.py` (modifié) — `trainingButton.setEnabled(False)` + `setToolTip(...)` ajoutés dans `__init__`, juste après la création des 4 boutons. Aucun handler connecté, aucune nouvelle logique.
- `src/ui/main_window.py` (modifié) — 3 lignes `connect()` ajoutées dans `__init__`, juste après la création de `settings_page` (une fois `dashboard_page`/`images_page` existants) : `dashboard_page.newProjectButton.clicked` → `self.new_project`, `dashboard_page.openProjectButton.clicked` → `self.open_project`, `dashboard_page.importImagesButton.clicked` → `self.images_page.import_images`. Aucune méthode intermédiaire créée.
- `tests/integration/test_dashboard_page.py` (créé, 6 tests).

Liste vérifiée directement depuis `git status --short`/`git diff --stat`. Aucun fichier hors ce périmètre (pas de Domain, pas de Manager, pas d'Infrastructure, pas d'EventBus, pas de `requirements.txt`, pas de `CLAUDE.md`/`AGENTS.md`).

## Hors périmètre

Galerie/miniatures `ImagesPage` ; image de référence pour Inference ; IP-Adapter ; ControlNet ; image-to-image ; choix du checkpoint ; choix du moteur ; deuxième Engine (RunComfy, GPT-Image, Seedream, Seedance, Kling ou autre) ; lancement réel d'un entraînement ; console d'entraînement ; `Job`/`Plugin`/`Service`/`AI Orchestrator` ; tout refactoring architectural sans nécessité directe avec le câblage des boutons Dashboard. Toutes les dettes déjà connues avant Mission 017 (ambiguïté `Training`/`Training History`, `BasePage` mort, `ApplicationSettings.comfyui_url`, limite shutdown Mission 013, incohérences Blueprint mineures) restent inchangées, non traitées par cette mission.

## Commit correspondant

Mission 017 sera clôturée en commit(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash ni message définitif n'est fixé en dur dans ce document avant la création du commit — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log` une fois la clôture Git effectuée.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission017`), si l'architecte confirme vouloir suivre cette convention pour cette mission. Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission017` une fois créé.

## État final

**Mission 017 est terminée (implémentation et tests).** Les trois boutons `newProjectButton`/`openProjectButton`/`importImagesButton` du Dashboard, jusqu'ici strictement inertes, sont désormais câblés directement depuis `MainWindow` vers les comportements déjà existants (`new_project()`, `open_project()`, `ImagesPage.import_images()`), sans aucune logique dupliquée dans `DashboardPage`. `trainingButton` reste visible mais explicitement désactivé, avec un tooltip clair, plutôt que de simuler un comportement inexistant. Validée par 231 tests d'intégration (225 précédents + 6 nouveaux), aucune régression. **Clôture Git (commit/tag/Release) non encore effectuée** à la rédaction de ce document — à réaliser après validation explicite de l'architecte. Mission 018 non définie ; devra tenir compte des trois besoins réels toujours non traités (galerie `ImagesPage`, images de référence Inference, sélection multi-engine).
