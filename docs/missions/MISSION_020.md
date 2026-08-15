# Mission 020 — MainToolBar Actions Wiring

Source : audit read-only préalable (Mission 020 Phase 1, état Git, code réel `src/ui/toolbar.py`/`src/ui/main_window.py`/`tests/integration/test_dashboard_page.py`/`test_main_window_new_project.py`), spécification validée par l'architecte, implémentation réalisée et vérifiée par exécution réelle de la suite de tests complète. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur dans ce document tant que la clôture Git n'a pas eu lieu.

## Contexte

`MainToolBar` (`src/ui/toolbar.py`) déclare trois `QAction` ("Open", "Save", "Run") depuis l'origine du projet, ajoutées via `addAction(...)` sans jamais être stockées comme attributs — structurellement impossibles à connecter depuis `MainWindow`. Cette dette a été identifiée lors de l'audit préalable de Mission 018 (Candidat D) puis revérifiée lors des audits Mission 019 et Mission 020, sans jamais être traitée. `MainWindow` possède déjà deux méthodes publiques fonctionnelles et déjà utilisées par le menu (`MainMenuBar`) : `open_project()` et `save_project()`. Aucune cible fonctionnelle légitime n'existe pour "Run" (voir "Décisions" ci-dessous).

## Problème constaté

Audit du code réel (Phase 1, lecture seule, revérifié en Phase de spécification) : les trois `QAction` de `MainToolBar` sont visibles et cliquables dans l'interface mais strictement inertes — aucun `.triggered.connect()` ne les cible nulle part dans le code. `MainToolBar()` elle-même n'est pas conservée comme attribut de `MainWindow` (`self.addToolBar(MainToolBar())`), ce qui rend toute connexion externe impossible sans modification.

## Objectif

Rendre Open et Save fonctionnels en réutilisant strictement les méthodes déjà existantes de `MainWindow` (`open_project()`/`save_project()`), sans dupliquer la moindre logique. Trancher explicitement le sort de Run : bouton visible, désactivé, avec un tooltip explicite — comme `DashboardPage.trainingButton` (Mission 017) — plutôt qu'un comportement inventé.

## Périmètre

**In scope**
- `MainToolBar.action_open`/`action_save`/`action_run` stockées comme attributs (au lieu de `QAction` anonymes).
- `MainToolBar.action_run` : `setEnabled(False)` + tooltip explicite, appliqué directement dans `MainToolBar.__init__`.
- `MainWindow` conserve une référence explicite au toolbar (`self.toolbar`).
- `self.toolbar.action_open.triggered.connect(self.open_project)` / `self.toolbar.action_save.triggered.connect(self.save_project)`, câblés dans `MainWindow.__init__`, aucune méthode intermédiaire.
- Nouveau fichier de tests `tests/integration/test_main_toolbar.py`.

**Out of scope** (voir section dédiée en fin de document)

## Décisions

- **Aucune duplication de logique** : `MainToolBar` ne reçoit aucune dépendance Manager/Workspace nouvelle. Le câblage d'Open/Save est effectué exclusivement dans `MainWindow` (composition root), exactement comme pour `DashboardPage` en Mission 017 — les actions du menu et celles du toolbar convergent vers les mêmes méthodes `MainWindow` (`open_project()`/`save_project()`), sans second chemin de logique.
- **Comportement Open/Save strictement hérité** : aucune règle de `open_project()`/`save_project()` n'est modifiée par cette mission (sélection de dossier, annulation, `WorkspaceManager.open()`/`.save()`, feedback status bar, gestion d'erreur via `QMessageBox.critical`). En particulier, `save_project()` sans Workspace ouvert continue d'afficher `"Aucun projet ouvert"` dans la status bar, sans appel à `WorkspaceManager.save()` et sans crash.
- **Run — aucune cible fonctionnelle légitime** : confirmé par audit (Mission 018 Phase 1, Mission 019 Phase 1, Mission 020 Phase 1) qu'aucun `run()`/lancement générique n'existe dans le projet — aucune exécution réelle de Training, aucun Job/Plugin/Service, `InferencePage.generate_button` étant une action contextuelle à une page précise et non un lancement générique adapté à une barre d'outils toujours visible. Décision définitive : Run reste visible, `setEnabled(False)`, avec un tooltip expliquant l'indisponibilité — même traitement que `DashboardPage.trainingButton` (Mission 017), sans handler, sans connexion, sans invention de sémantique.
- **`MainToolBar` conservée comme attribut `MainWindow`** (`self.toolbar = MainToolBar()` puis `self.addToolBar(self.toolbar)`, au lieu de `self.addToolBar(MainToolBar())`) — condition nécessaire pour que `MainWindow` puisse connecter ses actions, cohérent avec le style déjà existant (`self.menu = MainMenuBar()` puis `self.setMenuBar(self.menu)`).
- Aucun nouveau Domain, Manager, Service, Engine, Job, Plugin, Command pattern, Action dispatcher. Aucune nouvelle dépendance.

## Architecture retenue

```
MainToolBar.action_open.triggered   → MainWindow.open_project()   (inchangé, Mission 016)
MainToolBar.action_save.triggered   → MainWindow.save_project()   (inchangé)
MainToolBar.action_run              → désactivé + tooltip (Presentation pure, aucun câblage MainWindow)
```

Câblage effectué dans `MainWindow.__init__`, au même endroit et selon le même style que le câblage du menu déjà en place (`self.menu.action_open_project.triggered.connect(self.open_project)` etc.) — deux lignes `connect()` supplémentaires, aucune méthode intermédiaire créée dans `MainWindow`.

`MainToolBar` reste une vue UI pure : elle ne reçoit toujours aucune référence à un Manager, à `WorkspaceManager`, ni à une Page. Le câblage reste entièrement une responsabilité de composition de `MainWindow`, cohérent avec le principe déjà établi en Mission 017.

## Tests

Comportement observable exercé via de vrais widgets Qt (`MainWindow` réelle, `action.trigger()` réel — pas une simple vérification que `.connect()` a été appelé), dans un nouveau fichier `tests/integration/test_main_toolbar.py`, selon les conventions de `test_dashboard_page.py`/`test_main_window_new_project.py` :

1. Open — dossier sélectionné : `action_open.trigger()` avec `QFileDialog.getExistingDirectory` patché → `WorkspaceManager.open()` appelé exactement une fois avec le dossier attendu.
2. Open — annulation : dialogue retournant une chaîne vide → `WorkspaceManager.open()` jamais appelé.
3. Save — Workspace ouvert : `action_save.trigger()` avec un Workspace réel/simulé ouvert → `WorkspaceManager.save()` appelé via le flux existant.
4. Save — aucun Workspace : `action_save.trigger()` sans Workspace ouvert → aucun crash, `WorkspaceManager.save()` jamais appelé, `statusBar().currentMessage() == "Aucun projet ouvert"`.
5. Run — désactivé : `toolbar.action_run.isEnabled() == False`.
6. Run — tooltip : `toolbar.action_run.toolTip()` contient le message d'indisponibilité.

Le nombre exact de tests sera documenté après implémentation plutôt que forcé à un chiffre prédéterminé.

### Résultats réels

**Nouveaux tests ajoutés (6, `tests/integration/test_main_toolbar.py`)** :
- `test_action_open_selected_folder_calls_workspace_manager_open`
- `test_action_open_cancelled_never_calls_open`
- `test_action_save_with_open_workspace_calls_workspace_manager_save`
- `test_action_save_without_workspace_shows_existing_status_message`
- `test_action_run_is_disabled`
- `test_action_run_tooltip_explains_unavailability`

**Résultat `test_main_toolbar.py` seul** : `Ran 6 tests in 0.710s — OK` (6/6, verts au premier passage, aucune correction nécessaire).

**Tests complémentaires relancés** (`test_dashboard_page.py` + `test_main_window_new_project.py`, pour couvrir le menu File et le Dashboard, potentiellement affectés par le changement de câblage de `MainWindow.__init__`) : `Ran 10 tests in 0.829s — OK` (10/10, aucune régression sur `open_project()`/`save_project()` appelés directement, ni sur le câblage Dashboard de Mission 017).

**Résultat suite complète** : `Ran 246 tests in 76.512s — OK` (240 tests préexistants inchangés + 6 nouveaux, aucune régression constatée sur le menu File, Dashboard, ImagesPage, Inference, `ImagePreviewDialog`, Application Settings, `WorkspaceManager`, EventBus, ComfyUI, Training).

## Critères d'acceptation — état final

- `action_open`/`action_save`/`action_run` stockées comme attributs de `MainToolBar`, `QAction` conservées (pas de nouvelle abstraction) : ✅.
- Open/Save réutilisent strictement `MainWindow.open_project()`/`save_project()`, aucune logique dupliquée, aucun comportement existant modifié (sélection, annulation, feedback, gestion d'erreur, cas "aucun Workspace ouvert") : ✅ — `open_project()`/`save_project()` non modifiés, vérifié par `git diff`.
- Run reste visible, désactivé (`setEnabled(False)`), tooltip explicite (`"L'exécution depuis la barre d'outils n'est pas encore disponible."`), aucun handler connecté, aucune sémantique inventée : ✅.
- Aucune logique métier/Workspace/Manager dans `MainToolBar` : ✅.
- Aucune méthode intermédiaire créée dans `MainWindow` : ✅, câblage direct `self.toolbar.action_open.triggered.connect(self.open_project)`/`.action_save` → `self.save_project`.
- Aucun Domain/Manager/Infrastructure/EventBus/Engine modifié : ✅, vérifié par `git diff --stat`.
- Menu File et ses actions existantes continuent de fonctionner exactement comme avant : ✅ (10/10 tests complémentaires).
- Aucune régression sur Dashboard/ImagesPage/ImagePreviewDialog/Inference/Application Settings/WorkspaceManager/EventBus/ComfyUI/Training : ✅.
- Comportements couverts par des tests utilisant de vrais widgets Qt, exerçant un comportement observable (pas une simple présence de `.connect()`) : ✅ (6 tests, voir "Résultats réels" ci-dessus).
- Suite de tests complète verte, nombre exact confirmé : ✅ (246/246 : 240 précédents + 6 nouveaux).
- Aucune modification hors périmètre : ✅, vérifié par `git status`/`git diff --stat`.

## Fichiers modifiés / créés

- `src/ui/toolbar.py` (modifié) — `action_open`/`action_save`/`action_run` stockées comme attributs, `action_run.setEnabled(False)` + tooltip ajoutés dans `__init__`. Aucun handler connecté, aucune nouvelle logique.
- `src/ui/main_window.py` (modifié) — `self.addToolBar(MainToolBar())` remplacé par `self.toolbar = MainToolBar()` puis `self.addToolBar(self.toolbar)` ; 2 lignes `connect()` ajoutées juste après le câblage du menu existant. Aucune méthode intermédiaire, `open_project()`/`save_project()` non touchés.
- `tests/integration/test_main_toolbar.py` (créé, 6 tests).

Liste vérifiée directement depuis `git status --short`/`git diff --stat`. Aucun fichier hors ce périmètre (pas de Domain, pas de Manager, pas d'Infrastructure, pas d'EventBus, pas d'Engine, pas de `requirements.txt`, pas de `CLAUDE.md`/`AGENTS.md`).

## Hors périmètre

Sémantique réelle de "Run" ; méthode générique `run()` ; lancement Inference/Training/Workflow depuis le toolbar ; Job system ; Plugin system ; Service ; Command pattern ; Action dispatcher ; refactoring du menu ; refactoring Sidebar/Stack ; Preview Enlargement ; clic direct sur l'aperçu Inference ; image de référence Inference ; img2img ; IP-Adapter ; ControlNet ; multi-engine.

## Commit correspondant

Mission 020 sera clôturée en commit(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash ni message définitif n'est fixé en dur dans ce document avant la création du commit — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log` une fois la clôture Git effectuée.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission020`), si l'architecte confirme vouloir suivre cette convention pour cette mission. Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission020` une fois créé.

## État final

**Mission 020 est terminée (implémentation et tests).** `MainToolBar` expose désormais `action_open`/`action_save`/`action_run` comme attributs explicites. Open et Save réutilisent strictement `MainWindow.open_project()`/`save_project()`, sans aucune logique dupliquée ni méthode intermédiaire. Run reste visible mais explicitement désactivé, avec un tooltip clair, plutôt que de simuler un comportement inexistant — même traitement que `DashboardPage.trainingButton` (Mission 017). Validée par 246 tests d'intégration (240 précédents + 6 nouveaux), aucune régression. **Clôture Git (commit/tag/Release) non encore effectuée** à la rédaction de ce document — à réaliser après validation explicite de l'architecte. Mission 021 non définie.
