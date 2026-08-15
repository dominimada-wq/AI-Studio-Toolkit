# Mission 022 — Reference Image Transport Wiring

Source : audit read-only préalable (Mission 022 Phase 1 — état Git de clôture Mission 021, reconstruction de la verticale Inference depuis le code réel `src/ui/pages/inference_page.py`/`src/ui/generation_worker.py`/`src/managers/generation_manager.py`/`src/engines/comfyui_engine.py`, audit des primitives de sélection/manipulation d'image existantes, analyse architecturale 0..N), option "Fondation + preuve technique isolée" recommandée puis validée par l'architecte avec précisions, spécification validée, implémentation réalisée et vérifiée par exécution réelle de la suite de tests complète. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur ici ; les sections "Commit correspondant"/"Tag / release correspondant" restent en attente — la clôture Git de Mission 022 n'a pas encore eu lieu à ce stade (implémentation, correction des mocks obsolètes et documentation validées, pas encore commitées).

## 1. Contexte

Mission 021 a ajouté à `ComfyUIEngine` une primitive de transport générique, `upload_image(file_path, subfolder="", overwrite=False) -> dict`, permettant d'envoyer un fichier image local vers l'instance ComfyUI. Cette primitive est entièrement testée (18 tests, `ComfyUIEngineUploadImageTest`) mais **n'est appelée nulle part dans le code applicatif** — elle existe en isolation, non câblée à la verticale Inference réelle (`InferencePage → GenerationWorker → GenerationManager → ComfyUIEngine`).

Le besoin utilisateur réel (identifié depuis l'audit préalable de Mission 015, reconfirmé lors des audits Missions 018-021) est qu'une génération puisse à terme utiliser une ou plusieurs images de référence, avec des rôles potentiellement distincts (identité, planche de personnage, vêtement, décor, pose...) et des mécanismes moteur potentiellement distincts (img2img, IP-Adapter, ControlNet...). Aucune de ces décisions (rôle, mécanisme moteur, workflow concret) n'est prise par cette mission — voir section 17 "Non-objectifs".

## 2. Objectif

Construire le premier câblage applicatif bout-en-bout permettant à l'utilisateur de sélectionner une image de référence locale depuis `InferencePage`, et prouver — par un test automatisé réel, pas seulement par confiance dans le code — que cette référence est effectivement uploadée vers ComfyUI via `ComfyUIEngine.upload_image()` au moment de la génération. La référence uploadée **n'influence pas encore** le workflow ni l'image générée : le chemin txt2img actuel (`build_demo_workflow()`) continue de fonctionner exactement comme avant, à l'identique, avec ou sans référence sélectionnée.

## 3. Architecture concernée

```
InferencePage (sélection UI, snapshot au lancement)
    → GenerationWorker.__init__(generation_manager, prompt_text, output_directory, reference_images)
        → GenerationWorker.run()
            → GenerationManager.generate(prompt_text, output_directory, reference_images=None)
                → pour chaque chemin de reference_images (0..N, réellement 0 ou 1 cette mission) :
                    ComfyUIEngine.upload_image(file_path)   [Mission 021, INCHANGÉE]
                → ComfyUIEngine.generate_image(prompt_text, output_directory, checkpoint_name=...)   [INCHANGÉE]
                    → build_demo_workflow(prompt_text, checkpoint_name)   [INCHANGÉE, txt2img fixe]
```

Couches touchées : `src/ui/pages/inference_page.py` (Presentation), `src/ui/generation_worker.py` (pont Qt↔Manager), `src/managers/generation_manager.py` (Application/Manager). **Couche non touchée** : `src/engines/comfyui_engine.py` (Infrastructure) — `upload_image()`, `generate_image()`, `build_demo_workflow()`, `submit()`, `wait_for_result()`, `download_output()` restent tous strictement inchangés.

## 4. Périmètre IN

- Un contrôle de sélection d'image de référence dans `InferencePage` (bouton + affichage du nom de fichier sélectionné + bouton de retrait), réutilisant `QFileDialog` comme `ImagesPage.import_images()`/`DatasetsPage.import_images()`.
- `GenerationManager.generate(prompt_text, output_directory, reference_images=None)` — paramètre additionnel, backward-compatible.
- Pour chaque chemin dans `reference_images` (0, 1, ou en théorie N — réellement 0 ou 1 exercé cette mission), un appel à `ComfyUIEngine.upload_image(file_path)`, **avant** l'appel à `generate_image()`.
- `GenerationWorker.__init__()` reçoit `reference_images` en plus de `prompt_text`/`output_directory`, capturé par valeur au même instant que ces deux paramètres (voir section 8).
- `InferencePage._start_generation()` construit un snapshot de la sélection courante au moment du lancement (voir section 8), transmis au `GenerationWorker`.
- Réinitialisation de la sélection de référence sur changement de contexte Workspace (voir section 6).
- Propagation des erreurs d'upload dans la chaîne `GenerationError` existante (voir section 11).
- Tests couvrant : câblage UI → Worker → Manager → `upload_image()`, absence d'appel à `upload_image()` sans référence, échec d'upload propagé en échec de génération.

## 5. Périmètre OUT

- Aucun node `LoadImage` dans un workflow ComfyUI.
- Aucun img2img, aucun `denoise`/`strength`.
- Aucun IP-Adapter, ControlNet, FaceID, InstantID, pose estimation.
- Aucune logique de rôle (pas d'enum, pas de dictionnaire `role → image`, pas de taxonomie identité/vêtement/décor/pose).
- Aucun nouveau Domain (`ReferenceImage` ou équivalent), aucun nouveau Manager (`ReferenceImageManager` ou équivalent), aucun nouveau Service.
- Aucune modification de `build_demo_workflow()`, `generate_image()`, `submit()`, `wait_for_result()`, `download_output()`, `upload_image()`.
- Aucune modification du résultat visuel généré — le chemin txt2img reste identique avec ou sans référence sélectionnée.
- Aucune galerie complexe, aucun drag-and-drop, aucune sélection depuis `ImagesPage`/`DatasetsPage`.
- Aucune gestion multi-image visible dans l'UI (l'UI reste 0 ou 1 image ; seule la couche `GenerationManager`/`GenerationWorker` expose une collection).
- Aucune persistance de la référence dans `project.json`/`Workspace`.
- Aucun nouvel événement EventBus.
- Aucune décision sur Mission 023 (img2img vs IP-Adapter vs ControlNet vs abstraction générique de workflows) — hors périmètre, à auditer séparément.

## 6. Comportement fonctionnel attendu

### Sans référence sélectionnée
`generate()` se comporte **exactement comme aujourd'hui** : aucun appel à `upload_image()`, uniquement `generate_image()`. Aucune régression du chemin existant, aucun test préexistant ne doit changer de comportement observable.

### Avec référence sélectionnée
Au clic sur "Générer" (ou "Regenerate"), la référence actuellement sélectionnée dans l'UI est capturée dans un snapshot (liste à 0 ou 1 élément) transmis au `GenerationWorker`, puis à `GenerationManager.generate()`. Pour chaque chemin de la liste (fail-fast, dans l'ordre), `ComfyUIEngine.upload_image(file_path)` est appelée **avant** `generate_image()`. Le `dict` retourné par `upload_image()` (`{"name", "subfolder", "type"}`) **n'est pas conservé** — aucun consommateur n'existe encore pour cette information (voir section 17) ; l'appel sert uniquement à prouver et exercer le transport. La génération txt2img continue ensuite normalement, produisant un résultat visuellement identique à un appel sans référence.

### Cycle de vie de la sélection UI (workspace)
La référence sélectionnée est un état **transitoire** de `InferencePage`, jamais persisté dans `Workspace`/`project.json` (elle n'est jamais transmise à `WorkspaceManager`/`WorkspaceManager.add_images()`). Elle est réinitialisée sur `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED`, en réutilisant le point d'intégration déjà existant `InferencePage.reset_for_workspace_change()` (déjà abonné à ces trois événements par `main_window.py` pour invalider un résultat `pending`) — un seul point d'intégration pour l'ensemble de l'état transitoire de la page, plutôt qu'un second mécanisme parallèle. Justification : contrairement au résultat `pending` (qui est *destiné* à être persisté dans le Workspace actif via Accept, donc structurellement lié à son contexte), la référence sélectionnée n'est *jamais* persistée nulle part — mais la réinitialiser sur changement de Workspace évite toute confusion pour l'utilisateur ("pourquoi cette référence d'un autre projet est-elle encore attachée ?") et garde un seul hook de reset transitoire par page, cohérent avec le principe déjà établi.

## 7. Représentation 0..N des références

**Règle architecturale verrouillée** : à partir de la frontière `InferencePage → GenerationWorker → GenerationManager`, la référence est représentée comme une **collection** (`list[str]`, nommée `reference_images`), jamais comme un singleton `reference_image`/`reference_image_path` dans les signatures inter-couches.

- **UI** (`InferencePage`) : état interne `self._reference_image_path: Optional[str]` (0 ou 1, car l'UI de cette mission ne permet de sélectionner qu'une seule image) — **scalaire uniquement à l'intérieur de la Page**, jamais exposé tel quel aux couches inférieures.
- **Frontière de snapshot** (`InferencePage._start_generation()`) : le scalaire UI est converti en liste au moment de la construction du `GenerationWorker` : `[self._reference_image_path] if self._reference_image_path else []`. C'est la seule conversion scalaire→collection de tout le flux.
- **`GenerationWorker.__init__()`** : reçoit `reference_images: list[str]` (ou `None`), la stocke telle quelle (ou copiée défensivement — voir section 9).
- **`GenerationManager.generate()`** : reçoit `reference_images: Optional[list[str]] = None`, itère dessus (`for reference_path in (reference_images or [])`).
- **`ComfyUIEngine.upload_image()`** : **inchangée**, continue de n'accepter qu'un seul `file_path` par appel — appelée une fois par élément de la collection, jamais en batch (cohérent avec l'absence d'endpoint batch natif ComfyUI, déjà constaté en Mission 021).

Aucune abstraction supplémentaire n'est créée pour cette représentation : pas de `ReferenceImage` Domain, pas de `ReferenceImageManager`, pas d'enum de rôles, pas de dictionnaire `role → image`. Cette liste plate reste volontairement l'unique structure de données introduite par cette mission — une future notion de rôle s'ajoutera *à côté* d'elle plus tard (ex. une structure distincte associant rôle et chemin), sans jamais nécessiter de migrer un design singulier vers pluriel : le pluriel existe déjà dès cette mission.

## 8. Cycle de vie de l'état UI

Nouveaux éléments dans `InferencePage.__init__()` :
- `self._reference_image_path: Optional[str] = None`.
- Un bouton de sélection (ex. `self.select_reference_button`, libellé "Sélectionner une image de référence"), connecté à une nouvelle méthode `_on_select_reference_clicked()`.
- Un `QLabel` affichant le nom du fichier sélectionné (ex. `self.reference_label`), texte neutre par défaut (ex. "Aucune référence sélectionnée") quand `self._reference_image_path is None`.
- Un bouton de retrait (ex. `self.remove_reference_button`), `setEnabled(False)` par défaut, connecté à une nouvelle méthode `_on_remove_reference_clicked()` (ou réutilisation d'une méthode privée commune `_clear_reference_selection()` — voir ci-dessous).

Comportement :
- `_on_select_reference_clicked()` : ouvre `QFileDialog.getOpenFileName(...)` (sélection **simple**, pas `getOpenFileNames`, car l'UI ne permet qu'une seule image cette mission), filtre identique à `ImagesPage`/`DatasetsPage` (`"Images (*.png *.jpg *.jpeg *.webp *.bmp)"`). Si annulé (chaîne vide), aucun changement. Sinon, `self._reference_image_path` mis à jour, `self.reference_label` mis à jour avec `Path(file_path).name`, `self.remove_reference_button.setEnabled(True)`.
- `_clear_reference_selection()` (méthode privée réutilisée par `_on_remove_reference_clicked()` **et** par `reset_for_workspace_change()`) : `self._reference_image_path = None`, `self.reference_label` remis au texte par défaut, `self.remove_reference_button.setEnabled(False)`.
- Aucune validation métier de l'existence du fichier à la sélection (cohérent avec `CLAUDE.md` — la vérification d'existence appartient naturellement à la frontière Infrastructure au moment de l'upload, pas à l'UI ; un fichier supprimé entre la sélection et le clic sur "Générer" échoue naturellement via `GenerationError`, voir section 11).
- Le bouton de sélection et le bouton de retrait sont désactivés pendant qu'une génération est en cours (`setEnabled(False)` dans `_start_generation()`, `setEnabled(True)`/état cohérent restauré dans `_on_generation_finished()`/`_on_generation_failed()`), par cohérence UX avec `generate_button` — **mesure de confort, pas une garantie de correction** : la garantie réelle de non-interférence vient du snapshot (section 9), pas de ce verrou UI.

## 9. Propagation `InferencePage → GenerationWorker → GenerationManager`

**Point verrouillé explicitement par l'architecte** : la génération doit travailler avec un **snapshot** des références sélectionnées au démarrage, de la même manière que `_generation_workspace_root` capture déjà la racine du Workspace avant lancement (voir `inference_page.py`, section "Mission 014 final review" existante).

**Décision retenue** : `GenerationWorker.__init__()` reçoit `reference_images` en paramètre supplémentaire (aux côtés de `prompt_text`/`output_directory`), au même instant de construction — c'est-à-dire dans `InferencePage._start_generation()`, **avant** `worker.moveToThread(thread)` et **avant** `thread.start()`. Ce choix est retenu plutôt qu'une alternative (ex. lire `self._reference_image_path` depuis le worker/thread au moment de `run()`) parce que :
- Il reproduit exactement le mécanisme déjà éprouvé et déjà audité pour `prompt_text`/`output_directory` (capturés par valeur à la construction du `GenerationWorker`, jamais relus depuis `InferencePage` une fois le thread démarré) — aucun nouveau pattern de snapshot n'est inventé.
- Il élimine structurellement toute race condition : `self._reference_image_path` peut changer sur le thread Qt principal pendant qu'une génération tourne sur le thread secondaire (l'utilisateur retire ou change sa sélection) sans jamais affecter le job en cours, puisque le worker ne détient plus qu'une copie capturée avant `thread.start()`.

Séquence exacte dans `InferencePage._start_generation(self, prompt_text)` :
```python
reference_images = [self._reference_image_path] if self._reference_image_path else []
...
worker = GenerationWorker(self._generation_manager, prompt_text, output_directory, reference_images)
```

`GenerationWorker.__init__()` stocke une copie défensive (`list(reference_images)` plutôt que la référence à l'objet reçu) — bien que `InferencePage` construise déjà une liste fraîche à chaque appel (donc jamais mutée après coup dans l'implémentation prévue), la copie défensive à la frontière `Worker` reste la garantie structurelle explicite plutôt qu'une garantie implicite reposant sur la discipline de l'appelant, cohérent avec la rigueur déjà appliquée aux autres frontières de ce fichier (`worker`/`thread` capturés par valeur dans `_cleanup_thread`, voir docstring existante).

`GenerationWorker.run()` transmet la liste capturée telle quelle : `self._generation_manager.generate(self._prompt_text, self._output_directory, reference_images=self._reference_images)`.

## 10. Utilisation de `ComfyUIEngine.upload_image()`

`GenerationManager.generate()` itère sur `reference_images or []` et appelle `self._comfyui_engine.upload_image(reference_path)` pour chacun, **avant** l'appel à `generate_image()`, à l'intérieur du même bloc `try` qui englobe déjà `generate_image()` (voir section 11 pour la raison). Aucun paramètre `subfolder`/`overwrite` n'est transmis par `GenerationManager` cette mission (valeurs par défaut de `upload_image()` utilisées telles quelles — `subfolder=""`, `overwrite=False`) : aucun besoin réel n'a été démontré pour les personnaliser à ce stade. Le `dict` retourné par chaque appel n'est ni stocké, ni loggé, ni transmis plus loin — **confirmé volontairement non exploité cette mission**, la preuve de câblage se fait par assertion de test sur l'appel mocké (`assert_called_once_with(...)`), pas sur une valeur de retour consommée. `ComfyUIEngine.upload_image()` elle-même n'est pas modifiée : son contrat (signature, validation, erreurs) est déjà suffisamment générique et stateless pour cet usage, confirmé par l'audit Phase 1 (section C).

## 11. Stratégie de gestion des erreurs

Aucune nouvelle catégorie d'erreur n'est introduite. La frontière existante est réutilisée telle quelle :

```
ComfyUIEngine.upload_image() ou generate_image()
    → ComfyUIEngineError / FileNotFoundError / OSError
GenerationManager.generate()
    → normalise en GenerationError (déjà existant, try/except déjà en place)
GenerationWorker.run()
    → worker.failed.emit(str(error))   [déjà existant]
InferencePage._on_generation_failed()
    → QMessageBox.critical(...), generate_button réactivé   [déjà existant]
```

Concrètement, les appels `upload_image()` sont placés **dans le même bloc `try`** que l'appel `generate_image()` existant dans `GenerationManager.generate()` — les clauses `except ComfyUIEngineError`/`except OSError` déjà présentes couvrent donc nativement les deux phases (upload et génération) sans duplication de logique, et sans distinction de message spécifique par phase (le message de l'exception d'origine — ex. "ComfyUI server unreachable at ..." pour un échec réseau, ou le message natif de `FileNotFoundError` pour un fichier supprimé après sélection — reste suffisamment explicite tel quel).

**Sémantique fail-fast explicite** : si `reference_images` contient plusieurs éléments (non exercé cette mission mais l'architecture doit le supporter sans modification), le premier échec d'upload interrompt immédiatement `generate()` — aucun élément suivant n'est traité, `generate_image()` n'est jamais atteinte. Une génération ne doit jamais continuer silencieusement après l'échec d'un upload explicitement demandé par l'utilisateur.

Cas couverts explicitement par cette stratégie :
- Fichier de référence supprimé entre la sélection et le clic sur "Générer" → `FileNotFoundError` (native, non enveloppée par `ComfyUIEngine.upload_image()` elle-même, Mission 021) → capturée par `except OSError` dans `GenerationManager.generate()` → `GenerationError` → `worker.failed` → `QMessageBox.critical`.
- Fichier illisible (permissions) → `OSError` → même chemin.
- Serveur ComfyUI injoignable pendant l'upload → `ComfyUIEngineError` → même chemin.
- Réponse ComfyUI structurellement invalide pendant l'upload → `ComfyUIEngineError` (Mission 021) → même chemin.

`self._busy` reste correctement géré : le `try/finally` existant de `GenerationManager.generate()` englobe déjà la totalité de la méthode (guard busy posé avant la boucle d'upload, relâché dans le `finally` existant, qu'un upload ou `generate_image()` échoue).

## 12. Compatibilité avec le chemin sans référence

- Signature `GenerationManager.generate(self, prompt_text: str, output_directory: str, reference_images: Optional[list[str]] = None) -> str` — paramètre additionnel avec défaut `None`, tout appel positionnel/nommé existant (`generate(prompt_text, output_directory)`) reste valide sans modification.
- `GenerationWorker.__init__(self, generation_manager, prompt_text: str, output_directory: str, reference_images=None)` — même principe additif.
- Quand `reference_images` est `None`/`[]`, **aucun appel à `upload_image()` n'a lieu** — le comportement observable (requêtes HTTP envoyées, résultat produit) est strictement identique à avant cette mission. Tous les tests existants (`test_generation_manager.py`, `test_generation_worker.py`, `test_inference_page.py`, `test_comfyui_engine.py`) doivent continuer de passer sans modification de leur comportement attendu — seule une extension (nouveaux tests) est prévue, jamais une réécriture des tests existants.
- Aucune donnée persistée (`project.json`) n'est affectée — aucune question de compatibilité de données existantes.

## 13. Fichiers réellement modifiés

- `src/managers/generation_manager.py` (modifié, +23/-2 lignes) — `import typing` ajouté, signature `generate()` étendue avec `reference_images: Optional[List[str]] = None`, boucle d'upload `for reference_path in (reference_images or []): self._comfyui_engine.upload_image(reference_path)` ajoutée avant `generate_image()`, à l'intérieur du bloc `try` déjà existant.
- `src/ui/generation_worker.py` (modifié, +16/-2 lignes) — `__init__()` gagne `reference_images=None`, copié défensivement (`list(reference_images) if reference_images else []`) ; `run()` transmet `reference_images=self._reference_images` à chaque appel.
- `src/ui/pages/inference_page.py` (modifié, +88/-1 lignes) — import `QFileDialog` ajouté, état `_reference_image_path`, widgets `select_reference_button`/`reference_label`/`remove_reference_button`, méthodes `_on_select_reference_clicked`/`_on_remove_reference_clicked`/`_clear_reference_selection`/`_set_reference_controls_enabled`, snapshot construit dans `_start_generation()`, extension de `reset_for_workspace_change()`.
- `tests/integration/test_generation_manager.py` (modifié, +103 lignes) — nouvelle classe `GenerationManagerReferenceImagesTest`, 9 nouveaux tests.
- `tests/integration/test_generation_worker.py` (modifié, +73/-2 lignes) — nouvelle classe `GenerationWorkerReferenceImagesTest` (3 tests), adaptation de `_run_worker()` et de 2 tests existants (voir section "Écarts" du rapport de clôture).
- `tests/integration/test_inference_page.py` (modifié, +176/-2 lignes) — 11 nouveaux tests de sélection/propagation, adaptation de 2 assertions existantes (`assert_called_once_with`/`assert_called_with`) et **correction de 6 fonctions locales préexistantes** (`generate_side_effect`/`slow_generate`) dont l'ancienne signature à 2 paramètres provoquait un `TypeError` non anticipé lors de l'exécution — voir section "Écarts" ci-dessous.
- `docs/missions/MISSION_022.md` (ce document, complété après implémentation).

**Confirmés non touchés** (vérifié par `git diff`/`git status`) : `src/engines/comfyui_engine.py` (diff vide), `src/domain/`, `src/core/event_bus.py`, `src/ui/toolbar.py`, `src/ui/pages/images_page.py`, `src/ui/pages/datasets_page.py`, `src/ui/dialogs/`, `requirements.txt`, `CLAUDE.md`, `AGENTS.md`.

## 14. Critères d'acceptation — état final

- Un contrôle de sélection/retrait de référence existe dans `InferencePage`, réutilisant `QFileDialog` selon le pattern déjà établi : ✅.
- `GenerationManager.generate()` accepte `reference_images: Optional[List[str]] = None`, rétrocompatible : ✅.
- Sans référence : aucun appel à `upload_image()` — comportement strictement identique à avant : ✅, vérifié par test dédié.
- Avec référence : `upload_image()` appelée exactement une fois par référence, avec le chemin exact, avant `generate_image()` : ✅, ordre vérifié explicitement (y compris avec plusieurs références au niveau `GenerationManager`, non exposées par l'UI).
- Le résultat généré (le chemin txt2img) n'est aucunement modifié par la présence d'une référence : ✅ — `build_demo_workflow()`/`generate_image()` strictement inchangés.
- La sélection de référence est un snapshot capturé à la construction du `GenerationWorker`, immunisé contre tout changement de sélection UI après le lancement : ✅, prouvé par `test_worker_snapshot_is_independent_of_the_caller_list_object` et `test_changing_selection_after_launch_does_not_affect_the_in_flight_snapshot`.
- Un échec d'upload (fichier supprimé, réseau, protocole) interrompt la génération et remonte comme `GenerationError` via le chemin d'erreur existant, sans jamais poursuivre silencieusement vers `generate_image()` : ✅, fail-fast vérifié y compris avec plusieurs références.
- La référence sélectionnée est réinitialisée sur `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED`, jamais persistée dans `project.json` : ✅.
- `ComfyUIEngine.upload_image()`, `generate_image()`, `build_demo_workflow()`, `submit()`, `wait_for_result()`, `download_output()` strictement inchangés : ✅ — `git diff -- src/engines/comfyui_engine.py` vide, confirmé.
- Aucun nouveau Domain/Manager/Service/EventBus event : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ — **287/287** (264 précédents + 23 nouveaux).

## 15. Stratégie de tests

Inspecter et réutiliser les conventions déjà établies (`unittest.mock.patch`/`MagicMock`, `QFileDialog` mocké comme dans `test_dashboard_page.py`/`test_images_page.py`, widgets Qt réels via une vraie `MainWindow`/`InferencePage` comme dans `test_inference_page.py`).

**`test_generation_manager.py`** (nouveaux tests, `ComfyUIEngine` mocké comme aujourd'hui) :
- Sans `reference_images` (ou `None`, ou `[]`) : `upload_image` jamais appelée, comportement identique aux tests existants.
- Avec une référence : `upload_image` appelée exactement une fois avec le chemin exact, **avant** `generate_image`.
- Échec d'`upload_image` (`ComfyUIEngineError`) → `GenerationError` levée, `generate_image` jamais appelée (fail-fast), `busy` retombe à `False`.
- Échec d'`upload_image` (`FileNotFoundError`/`OSError`) → même normalisation `GenerationError`.
- (Optionnel selon lisibilité) Plusieurs références (2+, purement pour prouver l'architecture 0..N sans que l'UI ne les expose) → `upload_image` appelée une fois par référence, dans l'ordre.

**`test_generation_worker.py`** (vérifier d'abord si un changement est réellement nécessaire — probable adaptation minimale de construction si les tests existants instancient `GenerationWorker` positionnellement) :
- `reference_images` transmis tel quel du constructeur à l'appel `generation_manager.generate(...)`.
- Absence de `reference_images` à la construction reste valide (défaut).

**`test_inference_page.py`** (widgets Qt réels, `QFileDialog` patché) :
- Sélection réussie : `reference_label` mis à jour, `remove_reference_button` activé.
- Sélection annulée : aucun changement.
- Retrait : état remis à zéro.
- Génération lancée avec une référence sélectionnée : `GenerationWorker`/`generation_manager.generate` reçoit bien `[chemin]`.
- Génération lancée sans référence : `generation_manager.generate` reçoit `[]`/`None`, comportement identique à avant cette mission.
- Changement de sélection *après* le lancement d'une génération (avant la fin) ne modifie pas le snapshot déjà transmis au worker en cours (test de la propriété de non-interférence explicitement demandée par l'architecte).
- Réinitialisation de la référence sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED` (réutilisation de `reset_for_workspace_change()`).
- Échec d'upload propagé jusqu'à `QMessageBox.critical` (mock), `generate_button` réactivé, aucune persistance.

### Résultats réels

**`GenerationManagerReferenceImagesTest` (9 nouveaux tests, `tests/integration/test_generation_manager.py`)** : sans/avec `None`/liste vide → aucun appel `upload_image` ; une référence → upload avant génération, ordre prouvé ; plusieurs références → uploadées dans l'ordre ; échec d'upload (`ComfyUIEngineError`, `FileNotFoundError`) → `generate_image` jamais appelée, fail-fast prouvé y compris au milieu d'une liste de plusieurs références ; `busy` retombe à `False` après un échec d'upload.

**`GenerationWorkerReferenceImagesTest` (3 nouveaux tests, `tests/integration/test_generation_worker.py`)** : `reference_images` transmis tel quel à `generate()` ; absence de `reference_images` transmet `[]` ; le worker reste indépendant de toute mutation ultérieure de la liste de l'appelant (snapshot défensif prouvé explicitement).

**11 nouveaux tests dans `tests/integration/test_inference_page.py`** : état initial, sélection réussie, annulation, remplacement d'une sélection existante, retrait, génération sans référence (`[]`), génération avec référence (`[chemin]`), non-interférence d'un changement de sélection après lancement, réinitialisation sur changement de Workspace, non-persistance dans `Workspace.images`, contrôles de référence désactivés pendant la génération et tout le long de l'état pending (réactivés seulement à Accept/Reject, comme `generate_button`).

**Résultat `test_generation_manager.py` + `test_generation_worker.py` ciblés** : `Ran 26 tests in 0.177s — OK`.

**Résultat `test_inference_page.py`** : `Ran 48 tests in 79.809s — OK` (37 précédents + 11 nouveaux).

**Résultat suite complète** : `Ran 287 tests in 86.6s — OK` (264 précédents + 23 nouveaux : 9 + 3 + 11).

**Incident découvert et corrigé pendant la validation** (non anticipé par la spécification initiale) : `GenerationWorker.run()` transmettant désormais systématiquement `reference_images=` en mot-clé, 6 fonctions locales préexistantes de `test_inference_page.py` (`generate_side_effect`/`slow_generate`, utilisées comme `side_effect` de `generation_manager.generate` mocké) conservaient l'ancienne signature à 2 paramètres — provoquant un `TypeError` immédiat, capturé par le `except Exception` déjà existant de `GenerationWorker.run()`, qui émettait `failed` ; `_on_generation_failed()` ouvrait alors une véritable `QMessageBox.critical` **non mockée** dans le test concerné (`test_click_disables_button_immediately_and_ui_is_not_blocked`), bloquant indéfiniment le processus de test sur un dialogue modal sans utilisateur pour le fermer. Diagnostiqué par reproduction isolée hors suite (script scratchpad, supprimé après diagnostic, jamais commité) confirmant que le mécanisme `GenerationWorker`/signal `failed` fonctionnait correctement et que seule la boîte de dialogue réelle bloquait. Corrigé en ajoutant `reference_images=None` aux 6 fonctions concernées — aucune modification du code de production pour contourner le problème. Recherche exhaustive confirmée sur toute la suite (`slow_generate`/`fake_generate`/`mock_generate`/lambdas/`side_effect=`) : aucune autre occurrence obsolète.

## 16. Risques de régression

- `GenerationManager.generate()` : risque si l'ajout du paramètre casse un appel positionnel existant — mitigé par un paramètre nommé à la fin avec défaut `None`, vérifié par la suite complète.
- `GenerationWorker` : risque similaire sur sa construction — même mitigation.
- `InferencePage` : risque que le nouvel état `_reference_image_path` ne soit pas correctement réinitialisé par `reset_for_workspace_change()`, ou qu'il interfère avec l'état `pending` existant — à couvrir explicitement par test dédié (les deux états doivent rester indépendants : un pending pour un Workspace A ne doit jamais être affecté par la présence/absence d'une référence, et réciproquement).
- `ComfyUIEngine` : aucun risque, aucune modification prévue (confirmé par l'audit Phase 1).
- Projets/Workspaces existants : aucun risque, aucune donnée persistée n'est concernée par cette mission.
- Compatibilité `project.json` : sans objet, aucun changement de format.

## 17. Non-objectifs

- Décider du mécanisme moteur (img2img, IP-Adapter, ControlNet, ou une abstraction générique de workflows) pour une future Mission 023 — explicitement laissé à un audit ultérieur dédié, non anticipé ni engagé par cette mission.
- Exploiter le `dict` retourné par `upload_image()` dans un quelconque workflow ou node.
- Introduire une notion de rôle d'image (identité, character sheet, vêtement, décor, pose...).
- Introduire un `ReferenceImage` Domain, un `ReferenceImageManager`, ou tout Service dédié.
- Permettre la sélection de plusieurs images depuis l'UI (l'architecture le permet, l'UI ne l'expose pas cette mission).
- Réutiliser `ImagesPage`/`DatasetsPage`/une galerie pour la sélection.
- Modifier le résultat visuel de la génération de quelque façon que ce soit.
- Multi-engine (Fooocus, Automatic1111, Forge).
- Agrandissement/fullscreen du preview post-génération (besoin UX distinct, sans rapport avec cette mission).

## 18. Définition de Done — état final

- Implémentation conforme aux sections 6 à 13 ci-dessus, vérifiée par lecture réelle du code : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ — 287/287 (264 + 23 nouveaux).
- `git diff --stat` confirmant exactement le périmètre de fichiers listé en section 13 : ✅, `comfyui_engine.py` strictement inchangé (diff vide).
- Chemin txt2img sans référence strictement inchangé : ✅, aucune assertion de comportement des tests préexistants modifiée (seuls deux appels `assert_called_*_with` étendus pour inclure `reference_images=[]`, et 6 mocks locaux corrigés pour accepter la nouvelle signature — voir "Résultats réels" ci-dessus).
- Documentation de clôture (ce document, `PROJECT_CONTEXT.md`, `CHANGELOG.md`) réalisée après validation explicite de l'implémentation : ✅, en cours dans cette même passe.
- Clôture Git (commit → push → tag → push tag) : **non encore effectuée**, en attente de validation explicite de l'architecte.
- GitHub Release rédigée par Claude mais publiée uniquement par l'architecte : à venir après clôture Git.

## Commit correspondant

À compléter après clôture Git réelle (non encore effectuée à ce stade).

## Tag / release correspondant

À compléter après clôture Git réelle (non encore effectuée à ce stade).

## État final

**Implémentation et tests validés.** `InferencePage → GenerationWorker → GenerationManager → ComfyUIEngine.upload_image()` entièrement câblé, prouvé par 287/287 tests automatisés (264 précédents inchangés + 23 nouveaux), sans aucune influence sur le chemin de génération txt2img (`generate_image()`/`build_demo_workflow()` strictement inchangés, `comfyui_engine.py` avec un diff vide). UI volontairement limitée à 0/1 référence ; représentation `reference_images: list[str]` dès la frontière `InferencePage → GenerationWorker`, snapshot défensif prouvé indépendant de toute mutation ultérieure de la sélection UI. Aucune notion de rôle, aucun `LoadImage`, aucune persistance. **Clôture Git de Mission 022 non encore effectuée** — implémentation et documentation validées, en attente de validation explicite de l'architecte avant commit.
