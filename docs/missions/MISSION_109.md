# Mission 109 — Training Result → Inference Handoff

> **IMPLÉMENTÉE ET VALIDÉE PAR SMOKE RÉEL — NON ENCORE COMMITÉE.** Ce document a d'abord servi de contrat avant implémentation (sections 1-11, inchangées). Voir §12 pour le résultat réel complet.

## 1. Contexte

L'audit post-Mission 108 a établi que le flux principal `Images → Dataset/captions → OneTrainer → LoRA → Central Library → Inference (ComfyUI/Forge) → Images` est désormais complet de bout en bout pour la génération, mais qu'un maillon reste entièrement manuel et sans aide : après l'import réussi d'un résultat de Training dans la Central LoRA Library (`TrainingPage.import_selected_job_to_library()`, Mission 103), rien ne relie ce LoRA fraîchement importé à une utilisation immédiate dans Inference — l'utilisateur doit ouvrir `InferencePage`, dérouler le combo LoRA et deviner lequel des noms correspond au LoRA qu'il vient de produire.

Un audit ciblé complémentaire (voir échanges de préparation de cette mission) a établi, par lecture directe du code réel :

- `TrainingPage.import_selected_job_to_library()` (`training_page.py:1161`) a déjà `lora.lora_id` en scope local immédiatement après `LoRALibraryManager.import_lora()`, avant même `set_job_imported_lora_id()` et le `QMessageBox.information` de succès — aucune indirection nécessaire pour retrouver ce LoRA.
- `LoRALibraryManager.import_lora()` publie déjà `LORA_LIBRARY_IMPORTED` avec l'objet `LoRA` complet en payload (`lora_library_manager.py:247`), et `main_window.py:447` a déjà câblé cet événement sur `InferencePage.refresh_lora_selector` — **le rafraîchissement automatique du combo LoRA sans redémarrage existe déjà depuis Mission 108**. `refresh_lora_selector(self, _payload=None)` ignore cependant ce payload ("payload always ignored in favor of a full re-read") : il restaure la sélection précédente ou retombe sur "Aucun LoRA", jamais sur le LoRA qui vient d'être importé.
- `TrainingPage._describe_job()`/`_importable_job()` (`training_page.py:1098`/`1132`) recalculent déjà, à chaque affichage, l'état exact d'un Job (`importable` / `importé : {name}` / `LoRA supprimé, réimport possible`) par relecture fraîche de `job.imported_lora_id` contre `LoRALibraryManager.get()` — jamais un booléen mis en cache. C'est exactement le même calcul dont a besoin l'action "Utiliser dans Inference".
- Le pattern Presentation-layer déjà établi par Mission 033 (`Prompts → Envoyer vers Inference`) — signal Qt local sur la Page source, `MainWindow` médiateur, aucune mutation Domain, aucun EventBus — reste directement réutilisable pour ce nouveau handoff `TrainingPage → InferencePage`, sans dupliquer la responsabilité déjà couverte par `LORA_LIBRARY_IMPORTED`.

## 2. Objectif

Permettre à l'utilisateur, depuis `TrainingPage`, d'envoyer explicitement un LoRA déjà importé dans la Central LoRA Library vers Inference : `Job avec imported_lora_id valide` → clic **« Utiliser dans Inference »** → navigation vers `InferencePage` → liste LoRA rafraîchie → LoRA concerné présélectionné exactement. Aucun redémarrage requis. Aucun `trigger_word` inséré automatiquement dans le prompt.

## 3. Décisions retenues (issues de l'audit ciblé, non rediscutées ici)

### 3.1 Architecture — pattern Presentation-layer de Mission 033, pas d'EventBus supplémentaire

`TrainingPage` émet un signal Qt local contenant le `lora_id` (ex. `use_lora_in_inference_requested = Signal(str)`, mirroir exact de `PromptsPage.send_to_inference_requested`). `MainWindow` connecte ce signal à une méthode médiatrice privée (mirroir de `_on_prompts_send_to_inference`), qui appelle `InferencePage.refresh_lora_selector(target_lora_id=lora_id)` puis `Sidebar.select_page("inference")`. `TrainingPage` ne référence jamais `InferencePage` directement, exactement comme `PromptsPage` ne référence jamais `InferencePage`.

`LORA_LIBRARY_IMPORTED` (EventBus) n'est pas modifié et continue de couvrir seul la synchronisation générale de la bibliothèque (multi-page, sémantique "un LoRA a changé quelque part"). Cette mission ne duplique pas cette responsabilité : le nouveau signal ne porte qu'une intention de navigation propre à un clic dans `TrainingPage`, jamais une notification de changement de données.

### 3.2 UX — action persistante, état recalculé, aucune navigation automatique

Un nouveau bouton persistant « Utiliser dans Inference » dans `TrainingPage`, à côté de `import_lora_button`, mirroir du pattern déjà établi par `_refresh_import_button_state()`/`_importable_job()`. Son état d'activation est recalculé à chaque changement de sélection de `jobs_list` (même déclencheur que `_refresh_import_button_state()`), par une nouvelle méthode symétrique `_usable_in_inference_job()` : retourne le Job sélectionné si et seulement si `job.imported_lora_id` est renseigné **et** résout encore vers un LoRA réel via `LoRALibraryManager.get()` — jamais un booléen mis en cache, jamais un état figé au moment de l'import. Si le LoRA a été supprimé de la Central Library après import, le bouton redevient indisponible dès la prochaine relecture.

Le `QMessageBox.information` de succès d'import existant n'est pas modifié, et aucune navigation automatique vers Inference n'a lieu après un import — l'action reste strictement un clic explicite et distinct, réutilisable à tout moment ultérieur (pas seulement juste après l'import) tant que le Job reste sélectionnable et son LoRA existant.

### 3.3 `InferencePage.refresh_lora_selector()` — extension additive, compatible EventBus

Signature étendue à `refresh_lora_selector(self, _payload=None, target_lora_id: Optional[str] = None)`. Lorsque `target_lora_id` est fourni et correspond à une entrée réellement présente dans le combo reconstruit, il prend priorité sur `previous_choice` pour le calcul de l'index restauré — sinon (absent, `None`, ou ne correspondant à aucune entrée reconstruite), le comportement actuel est strictement inchangé : repli sur `previous_choice` si toujours valide, sinon "Aucun LoRA". Les 3 abonnements EventBus existants (`LORA_LIBRARY_IMPORTED`/`DELETED`/`UPDATED`, tous connectés sans argument positionnel supplémentaire aujourd'hui) continuent d'appeler cette méthode avec leur seul argument positionnel habituel (le payload de l'événement) — `target_lora_id` reste un paramètre nommé, jamais positionnel côté EventBus, non fourni par ces abonnements, donc `None` par défaut pour eux, comportement byte-for-byte identique à avant cette mission.

## 4. Périmètre exact — fichiers concernés

- `src/ui/pages/training_page.py` (modifié) — nouveau bouton, `_usable_in_inference_job()`, signal, handler de clic.
- `src/ui/pages/inference_page.py` (modifié) — extension de `refresh_lora_selector()` uniquement.
- `src/ui/main_window.py` (modifié) — connexion du nouveau signal + méthode médiatrice, mirroir de `_on_prompts_send_to_inference`.
- `tests/integration/test_training_roundtrip.py` (modifié) — tests du nouveau bouton/état/signal (fichier où vivent déjà les tests `TrainingPage`, y compris ceux de Mission 103 sur l'import).
- `tests/integration/test_inference_page.py` (modifié) — tests de `refresh_lora_selector(target_lora_id=...)`.
- `tests/integration/test_main_window_training_to_inference.py` (nouveau) — mirroir de `test_main_window_prompts_to_inference.py`.
- `docs/missions/MISSION_109.md` (ce document).

**Toute nécessité de modifier un Manager, un objet Domain ou un Engine doit déclencher un arrêt et un rapport avant tout élargissement de cette liste — jamais une extension silencieuse.** Aucune modification attendue de `LoRALibraryManager`, `TrainingManager`, `Job`/`Training`/`LoRA` (Domain), `ComfyUIEngine`, `ForgeEngine`, `GenerationManager`, ni de l'EventBus lui-même (aucun nouvel événement).

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Insertion automatique du `trigger_word` dans le prompt d'Inference.
- Toute modification automatique du prompt.
- Liaison complète Character → Training → LoRA → trigger (besoin déjà documenté séparément dans `docs/PROJECT_CONTEXT.md`, non traité ici).
- Refonte générale de `InferencePage` (besoin déjà documenté séparément, non traité ici).
- Tout nouvel événement EventBus.
- Historique Training/LoRA.
- Changement de la structure de stockage physique de la Central LoRA Library.
- Toute modification de `ComfyUIEngine`/`ForgeEngine`/`GenerationManager`.
- Un nouveau Training réel GPU, sauf si le smoke l'exige réellement (voir section 8 — a priori non nécessaire, un Job déjà importé ou un scénario isolé équivalent suffit).
- Remplacement du `QMessageBox` de succès d'import existant, ou navigation automatique après import.

## 6. Étapes techniques attendues

1. **`src/ui/pages/training_page.py`** :
   - Nouveau `self.use_lora_in_inference_button = QPushButton("Utiliser dans Inference")`, `setEnabled(False)` initialement, placé à côté d'`import_lora_button`.
   - Nouveau signal de classe `use_lora_in_inference_requested = Signal(str)`.
   - Nouvelle méthode `_usable_in_inference_job()`, symétrique à `_importable_job()` : retourne le Job actuellement sélectionné dans `jobs_list` si `job.imported_lora_id` est renseigné et que `self.lora_library_manager.get(job.imported_lora_id)` retourne un LoRA réel, sinon `None`.
   - `_refresh_import_button_state()` étendue (ou nouvelle méthode jumelle appelée au même endroit, `_on_job_selection_changed()` et après tout import/suppression pertinente) pour recalculer `use_lora_in_inference_button.setEnabled(self._usable_in_inference_job() is not None)`.
   - Nouveau handler connecté au clic du bouton : émet `use_lora_in_inference_requested.emit(job.imported_lora_id)` pour le Job retourné par `_usable_in_inference_job()` — aucune émission si `None`.
2. **`src/ui/pages/inference_page.py`** :
   - `refresh_lora_selector(self, _payload=None, target_lora_id: Optional[str] = None)` — calcul de `restored_index` : si `target_lora_id` et `target_lora_id in lora_ids`, l'utiliser directement (`self.lora_combo.findData(target_lora_id)`) ; sinon, logique actuelle inchangée (`previous_choice` puis repli sur 0).
3. **`src/ui/main_window.py`** :
   - `self.training_page.use_lora_in_inference_requested.connect(self._on_training_use_lora_in_inference)`.
   - Nouvelle méthode privée `_on_training_use_lora_in_inference(self, lora_id: str)` : appelle `self.inference_page.refresh_lora_selector(target_lora_id=lora_id)` puis `self.sidebar.select_page("inference")` — aucune confirmation/collision à gérer (contrairement à M033, il n'y a ici aucune donnée utilisateur non sauvegardée en jeu, seulement un changement de sélection LoRA).

Aucun autre appelant existant de `refresh_lora_selector()` n'est modifié — les 3 abonnements EventBus continuent de l'appeler sans `target_lora_id`, comportement byte-for-byte identique.

## 7. Tests attendus

`tests/integration/test_training_roundtrip.py` (extension) :

1. Bouton désactivé sans Job sélectionné.
2. Bouton désactivé pour un Job non importé (`imported_lora_id` vide).
3. Bouton activé lorsque `imported_lora_id` référence un LoRA existant de la Central Library.
4. Bouton désactivé si ce LoRA a ensuite été supprimé de la Central Library (relecture fraîche, jamais un état mis en cache depuis l'import).
5. Émission du signal `use_lora_in_inference_requested` avec le `lora_id` exact du Job sélectionné.
6. Non-régression de l'import Mission 103 (`import_selected_job_to_library()`, `_importable_job()`, `_describe_job()`) et du `QMessageBox` de succès existant, inchangé.

`tests/integration/test_inference_page.py` (extension) :

7. `refresh_lora_selector(target_lora_id=...)` présélectionne exactement l'entrée demandée dans le combo reconstruit.
8. `target_lora_id` prioritaire sur `previous_choice` lorsque les deux sont fournis/valides.
9. `target_lora_id` absent ou ne correspondant à aucune entrée reconstruite → comportement historique strictement inchangé (repli `previous_choice` puis "Aucun LoRA").
10. Non-régression du rafraîchissement Mission 108 : les 3 événements `LORA_LIBRARY_IMPORTED`/`DELETED`/`UPDATED` continuent de déclencher `refresh_lora_selector` sans `target_lora_id`, comportement identique à avant cette mission.

`tests/integration/test_main_window_training_to_inference.py` (nouveau, mirroir de `test_main_window_prompts_to_inference.py`) :

11. `MainWindow` connecte bien le signal de `TrainingPage` à son handler.
12. Un signal émis navigue réellement vers Inference (`Sidebar.select_page("inference")` réellement appelé/page active réellement changée) et transmet le bon `lora_id` à `refresh_lora_selector`.
13. Suite complète : nombre exact confirmé, exit 0.

Aucun appel réseau réel, aucun ComfyUI/Forge/GPU réel sollicité par aucun de ces tests.

## 8. Smoke réel attendu

Un nouveau Training GPU réel n'est pas requis a priori — le smoke peut réutiliser un Job déjà importé dans la Central LoRA Library (par exemple celui produit pendant le smoke Mission 108) ou un scénario isolé équivalent (import direct d'un fichier `.safetensors` existant via `import_lora()`, sans passer par un entraînement réel).

Si Claude peut observer ce comportement de façon fiable avec des widgets Qt réels (construction réelle de `MainWindow`/`TrainingPage`/`InferencePage`, pas seulement des mocks), il exécute ce smoke lui-même, en confirmant par lecture d'état réel des widgets (jamais une simulation) :

1. Sélectionner, dans une instance réelle de `TrainingPage`, un Job dont le LoRA existe dans la Central Library.
2. Déclencher le bouton « Utiliser dans Inference » (ou émettre directement le signal si le clic Qt réel n'est pas fiable à automatiser).
3. Vérifier que l'application est réellement passée sur la page Inference (page active du `stack`).
4. Vérifier que le LoRA exact est sélectionné dans `lora_combo` (`itemData`/texte affiché).
5. Vérifier que le prompt d'Inference n'a pas été modifié et qu'aucun `trigger_word` n'a été inséré automatiquement.

Si un point précis de ce smoke s'avère non observable de façon fiable par les outils disponibles (cas déjà rencontré en Mission 108 pour le pilotage direct de l'UI via computer-use), seul ce point précis est délégué à l'architecte avec une action et une vérification exactes à effectuer — jamais l'ensemble du smoke par défaut.

## 9. Critères de clôture

1. `TrainingPage`/`InferencePage`/`MainWindow` implémentés exactement selon le périmètre de la section 6, testés selon la section 7.
2. `refresh_lora_selector()` accepte `target_lora_id` avec un comportement byte-for-byte identique pour tout appel existant qui ne le fournit pas (les 3 abonnements EventBus).
3. Zéro nouvel événement EventBus, zéro modification de `LoRALibraryManager`/`TrainingManager`/Domain/Engines.
4. Suite complète verte au nombre exact, `git diff --check` propre.
5. Aucun élément de la section 5 n'a été ajouté.
6. Bouton « Utiliser dans Inference » recalculé depuis les données réelles à chaque affichage, jamais un état mis en cache — vérifié explicitement par un test couvrant la suppression du LoRA après import.
7. Smoke réel (section 8) exécuté et documenté, avec délégation précise à l'architecte uniquement pour ce qui n'est pas observable de façon fiable.

## 10. Documentation

- Cette mission ne modifie ni ne referme les besoins futurs déjà enregistrés dans `docs/PROJECT_CONTEXT.md` pendant Mission 108 (liaison Character/Training/LoRA pour le trigger, refonte UX/UI d'Inference, gestion automatique du backend Forge, séparation application/données, emplacement configurable des projets, lisibilité des dossiers physiques de la Central LoRA Library) — tous restent explicitement ouverts et non tranchés.
- La régularisation documentaire post-clôture (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`) suivra le même processus que les missions précédentes, après commit/tag/Release.

## 11. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte.

## 12. Résultat réel

### 12.1 Implémentation — conforme au périmètre exact de la section 6

`src/ui/pages/training_page.py` : nouveau signal de classe `use_lora_in_inference_requested = Signal(str)`, nouveau `use_lora_in_inference_button` placé directement sous `import_lora_button`, nouvelle méthode `_usable_in_inference_job()` (symétrique de `_importable_job()` — relit `job.imported_lora_id` puis `lora_library_manager.get()` à chaque appel, jamais une valeur mise en cache), `_refresh_import_button_state()` étendue en place pour recalculer les deux boutons ensemble (les deux call sites existants — `_on_job_selection_changed()` et `_refresh_jobs_list()`, elle-même appelée par `_refresh_job_controls()` et après chaque import réussi — couvrent donc automatiquement le nouveau bouton sans câblage additionnel), nouvelle méthode `use_selected_lora_in_inference()` (même discipline que `import_selected_job_to_library()` : réutilise `_usable_in_inference_job()` pour que le clic et l'état d'activation ne divergent jamais).

`src/ui/pages/inference_page.py` : `refresh_lora_selector()` étendue d'un unique paramètre nommé `target_lora_id: Optional[str] = None`, prioritaire sur `previous_choice` lorsqu'il est fourni et présent parmi les entrées reconstruites — sinon, comportement strictement inchangé. Les 3 abonnements EventBus (`LORA_LIBRARY_IMPORTED`/`DELETED`/`UPDATED`, câblés dans `main_window.py`) continuent d'appeler cette méthode avec leur seul argument positionnel habituel, `target_lora_id` restant `None` pour eux.

`src/ui/main_window.py` : `self.training_page.use_lora_in_inference_requested.connect(self._on_training_use_lora_in_inference)`, nouvelle méthode médiatrice `_on_training_use_lora_in_inference(lora_id)` — `refresh_lora_selector(target_lora_id=lora_id)` puis `sidebar.select_page("inference")`, aucune confirmation (aucune donnée utilisateur non sauvegardée en jeu, contrairement à Mission 033). `TrainingPage` ne référence `InferencePage` à aucun moment.

**Aucun élargissement du périmètre** : aucune modification de `LoRALibraryManager`, `TrainingManager`, du Domain, de `ComfyUIEngine`/`ForgeEngine`, ni de l'EventBus (zéro nouvel événement) — conforme à la section 4/5, jamais de stop-and-report nécessaire.

### 12.2 Tests

**18 tests ciblés nets nouveaux** (2166 → 2184) : 8 dans `test_training_roundtrip.py` (nouvelle classe `TrainingPageUseLoraInInferenceTest` — bouton désactivé sans sélection/pour un Job non importé, activé pour un `imported_lora_id` réel, désactivé de nouveau après suppression du LoRA depuis la Library, réactivé après réimport, émission exacte du signal, aucune émission sans Job utilisable, non-régression du dirty-state Mission 105), 5 dans `test_inference_page.py` (nouvelle section de `InferencePageLoraSelectorTest` — `target_lora_id` sélectionné par défaut, prioritaire sur `previous_choice`, absence/`None`/valeur inconnue tous répliquant le comportement historique), 5 dans le nouveau `test_main_window_training_to_inference.py` (câblage réel du signal, navigation réelle vers Inference, présélection réelle, non-modification du prompt, non-régression `workspace_manager.save()`). Suite complète finale : **2184/2184**, `python -m unittest discover -s tests -p "test_*.py"`, `git diff --check` propre.

### 12.3 Smoke réel — exécuté par Claude, widgets Qt réels, conforme à la section 8

Une véritable instance `MainWindow()` a été construite (storage réel de `LoRALibraryManager`/`ApplicationSettingsManager`, comme tout autre test `MainWindow()` existant de la suite). Le LoRA réel « Zaraya Koyah SDX » déjà présent dans la Central LoRA Library a été localisé par une lecture réelle (`list_loras()`), jamais réimporté, supprimé, renommé ni modifié — vérifié explicitement après coup par comparaison de `lora_id`/`name`/`files` avant/après. Un Workspace/Training/Job **isolé et temporaire** (répertoire temp dédié, jamais `M108_Forge_Smoke` ni aucun autre projet réel) a été créé uniquement pour porter un `imported_lora_id` référençant ce `lora_id` réel via `TrainingManager.set_job_imported_lora_id()` — aucun appel à `LoRALibraryManager.import_lora()`/`delete()`/`update()`. Résultat, chaque point de la section 8 confirmé :

1. Job sélectionné dans une `TrainingPage` réelle, `use_lora_in_inference_button.isEnabled()` → `True`.
2. Clic réel sur le bouton (`QPushButton.click()`).
3. `window.stack.currentWidget() is window.inference_page` → `True`.
4. `inference_page.lora_combo` sélectionne exactement `lora_id=37ca771a-08d2-4b6e-8858-fac6c742f193`, libellé affiché « Zaraya Koyah SDX ».
5. `inference_page.prompt_text()` strictement inchangé (`""` avant et après), aucun `trigger_word` inséré.

Répertoire temporaire nettoyé après exécution (`shutil.rmtree`), aucun résidu, `git status --short` confirmé identique avant/après (hors bruit `graphify-out/*` pré-existant). Aucun appel réel à Forge/ComfyUI, aucune génération d'image — conforme à la section 8, ce smoke valide uniquement le handoff UI.

### 12.4 Points ambigus de la section pré-implémentation — résolus

1. Placement du bouton : directement sous `import_lora_button`, même colonne verticale, aucun redesign.
2. Calcul de l'état : `_refresh_import_button_state()` étendue en place (option retenue) plutôt qu'une méthode jumelle séparée — les deux boutons partagent déjà exactement les deux mêmes déclencheurs de rafraîchissement.
3. Smoke : le LoRA réel « Zaraya Koyah SDX » a bien été réutilisé, via un Job/projet isolé et temporaire référençant son `lora_id`, jamais un nouvel import/suppression/modification.
