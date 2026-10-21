# Changelog — archive : Missions 083 à 042

> **Archive de `CHANGELOG.md`.** Ce fichier reçoit, **sans aucune modification**, les entrées de missions 083 à 042 du journal d'origine (copie exacte, vérifiée par empreinte ; voir [`README.md` de l'archive](../README.md) et la [table de correspondance](../CORRESPONDANCE.md)). Le Sommaire ci-dessous reprend, mot pour mot, les lignes correspondantes du Sommaire d'origine : ses ancres restent valides dans ce fichier. L'index de toutes les missions, avec renvoi vers chaque entrée, est en tête de [`CHANGELOG.md`](../../../CHANGELOG.md). Les états décrits dans ces entrées sont ceux **de leur date** ; l'état courant est dans [`docs/PROJECT_CONTEXT.md`](../../PROJECT_CONTEXT.md). Ce fichier et son manifeste de référence sont immuables : un archivage ultérieur crée de nouveaux fichiers avec leur propre manifeste ; seuls les index de navigation sont actualisés.

## Sommaire

- **Mission 083 — Protect InferencePage.prompt Against Silent Loss on Workspace Context Change**
  - [Résumé (Mission 083)](#résumé-mission-083)
  - [Tests ajoutés (Mission 083)](#tests-ajoutés-mission-083)
  - [État du projet (Mission 083)](#état-du-projet-mission-083)
- **Mission 082 — Preserve Multi-Selection Across Unrelated UI Rebuilds**
  - [Résumé (Mission 082)](#résumé-mission-082)
  - [Tests ajoutés (Mission 082)](#tests-ajoutés-mission-082)
  - [État du projet (Mission 082)](#état-du-projet-mission-082)
- **Mission 081 — Normalize Invalid Ollama URL Errors**
  - [Résumé (Mission 081)](#résumé-mission-081)
  - [Tests ajoutés (Mission 081)](#tests-ajoutés-mission-081)
  - [État du projet (Mission 081)](#état-du-projet-mission-081)
- **Mission 080 — Automatic Cleanup of the Previous LoRA Thumbnail After a Successful Replacement**
  - [Résumé (Mission 080)](#résumé-mission-080)
  - [Tests ajoutés (Mission 080)](#tests-ajoutés-mission-080)
  - [État du projet (Mission 080)](#état-du-projet-mission-080)
- **Mission 079 — Protect Dirty Drafts on Application Close (MainWindow.closeEvent())**
  - [Résumé (Mission 079)](#résumé-mission-079)
  - [Tests ajoutés (Mission 079)](#tests-ajoutés-mission-079)
  - [État du projet (Mission 079)](#état-du-projet-mission-079)
- **Mission 078 — Dirty-State Protection for CharactersPage/LoRAPage/SettingsPage**
  - [Résumé (Mission 078)](#résumé-mission-078)
  - [Tests ajoutés (Mission 078)](#tests-ajoutés-mission-078)
  - [État du projet (Mission 078)](#état-du-projet-mission-078)
- **Mission 077 — Rollback SettingsManager.update() theme/language on Persistence Failure**
  - [Résumé (Mission 077)](#résumé-mission-077)
  - [Tests ajoutés (Mission 077)](#tests-ajoutés-mission-077)
  - [État du projet (Mission 077)](#état-du-projet-mission-077)
- **Mission 076 — Rollback DatasetManager.remove_images() / LoRAManager.add_files() / remove_files() on Persistence Failure**
  - [Résumé (Mission 076)](#résumé-mission-076)
  - [Tests ajoutés (Mission 076)](#tests-ajoutés-mission-076)
  - [État du projet (Mission 076)](#état-du-projet-mission-076)
- **Mission 075 — Transactional Physical Cleanup of Dataset/LoRA Folders on Deletion**
  - [Résumé (Mission 075)](#résumé-mission-075)
  - [Tests ajoutés (Mission 075)](#tests-ajoutés-mission-075)
  - [État du projet (Mission 075)](#état-du-projet-mission-075)
- **Mission 074 — Rollback CharacterManager.update() Identity on Persistence Failure**
  - [Résumé (Mission 074)](#résumé-mission-074)
  - [Tests ajoutés (Mission 074)](#tests-ajoutés-mission-074)
  - [État du projet (Mission 074)](#état-du-projet-mission-074)
- **Mission 073 — Rollback LoRAManager.update() Metadata on Persistence Failure**
  - [Résumé (Mission 073)](#résumé-mission-073)
  - [Tests ajoutés (Mission 073)](#tests-ajoutés-mission-073)
  - [État du projet (Mission 073)](#état-du-projet-mission-073)
- **Mission 072 — Rollback Domain-Only create() on Persistence Failure**
  - [Résumé (Mission 072)](#résumé-mission-072)
  - [Tests ajoutés (Mission 072)](#tests-ajoutés-mission-072)
  - [État du projet (Mission 072)](#état-du-projet-mission-072)
- **Mission 071 — Rollback PromptManager.delete() on Persistence Failure**
  - [Résumé (Mission 071)](#résumé-mission-071)
  - [Tests ajoutés (Mission 071)](#tests-ajoutés-mission-071)
  - [État du projet (Mission 071)](#état-du-projet-mission-071)
- **Mission 070 — Rollback Scalar Domain-Only Mutations on Persistence Failure**
  - [Résumé (Mission 070)](#résumé-mission-070)
  - [Tests ajoutés (Mission 070)](#tests-ajoutés-mission-070)
  - [État du projet (Mission 070)](#état-du-projet-mission-070)
- **Mission 069 — Protect PromptsPage Draft Before New/Open Project**
  - [Résumé (Mission 069)](#résumé-mission-069)
  - [Tests ajoutés (Mission 069)](#tests-ajoutés-mission-069)
  - [État du projet (Mission 069)](#état-du-projet-mission-069)
- **Mission 068 — Rollback Domain-Only Deletions on Persistence Failure**
  - [Résumé (Mission 068)](#résumé-mission-068)
  - [Tests ajoutés (Mission 068)](#tests-ajoutés-mission-068)
  - [État du projet (Mission 068)](#état-du-projet-mission-068)
- **Mission 067 — Rollback Additive Filesystem Mutations on Persistence Failure**
  - [Résumé (Mission 067)](#résumé-mission-067)
  - [Tests ajoutés (Mission 067)](#tests-ajoutés-mission-067)
  - [État du projet (Mission 067)](#état-du-projet-mission-067)
- **Mission 066 — Safe Image Deletion Persistence**
  - [Résumé (Mission 066)](#résumé-mission-066)
  - [Tests ajoutés (Mission 066)](#tests-ajoutés-mission-066)
  - [État du projet (Mission 066)](#état-du-projet-mission-066)
- **Mission 065 — Block Prompt Assistant Close While Generation Is Running**
  - [Résumé (Mission 065)](#résumé-mission-065)
  - [Tests ajoutés (Mission 065)](#tests-ajoutés-mission-065)
  - [État du projet (Mission 065)](#état-du-projet-mission-065)
- **Mission 064 — Thumbnail Cache**
  - [Résumé (Mission 064)](#résumé-mission-064)
  - [Tests ajoutés (Mission 064)](#tests-ajoutés-mission-064)
  - [État du projet (Mission 064)](#état-du-projet-mission-064)
- **Mission 063 — Synchronize Delete Action with Selection**
  - [Résumé (Mission 063)](#résumé-mission-063)
  - [Tests ajoutés (Mission 063)](#tests-ajoutés-mission-063)
  - [État du projet (Mission 063)](#état-du-projet-mission-063)
- **Mission 062 — Confirm Destructive Entity Deletion**
  - [Résumé (Mission 062)](#résumé-mission-062)
  - [Tests ajoutés (Mission 062)](#tests-ajoutés-mission-062)
  - [État du projet (Mission 062)](#état-du-projet-mission-062)
- **Mission 061 — Adaptive Dialog Sizing**
  - [Résumé (Mission 061)](#résumé-mission-061)
  - [Tests ajoutés (Mission 061)](#tests-ajoutés-mission-061)
  - [État du projet (Mission 061)](#état-du-projet-mission-061)
- **Mission 060 — Adaptive Initial Window Size**
  - [Résumé (Mission 060)](#résumé-mission-060)
  - [Tests ajoutés (Mission 060)](#tests-ajoutés-mission-060)
  - [État du projet (Mission 060)](#état-du-projet-mission-060)
- **Mission 059 — ComfyUI LoRA Selection for Generation**
  - [Résumé (Mission 059)](#résumé-mission-059)
  - [Tests ajoutés (Mission 059)](#tests-ajoutés-mission-059)
  - [État du projet (Mission 059)](#état-du-projet-mission-059)
- **Mission 058 — Dead Code and Stale Documentation Cleanup (Round 2)**
  - [Résumé (Mission 058)](#résumé-mission-058)
  - [Tests ajoutés (Mission 058)](#tests-ajoutés-mission-058)
  - [État du projet (Mission 058)](#état-du-projet-mission-058)
- **Mission 057 — Remove Vestigial Workspace Fields and Dead Code**
  - [Résumé (Mission 057)](#résumé-mission-057)
  - [Tests ajoutés (Mission 057)](#tests-ajoutés-mission-057)
  - [État du projet (Mission 057)](#état-du-projet-mission-057)
- **Mission 056 — Typed Inference Reference Primitive**
  - [Résumé (Mission 056)](#résumé-mission-056)
  - [Tests ajoutés (Mission 056)](#tests-ajoutés-mission-056)
  - [État du projet (Mission 056)](#état-du-projet-mission-056)
- **Mission 055 — Graceful Settings Save Errors**
  - [Résumé (Mission 055)](#résumé-mission-055)
  - [Tests ajoutés (Mission 055)](#tests-ajoutés-mission-055)
  - [État du projet (Mission 055)](#état-du-projet-mission-055)
- **Mission 054 — Rename Dataset and Training after Creation**
  - [Résumé (Mission 054)](#résumé-mission-054)
  - [Tests ajoutés (Mission 054)](#tests-ajoutés-mission-054)
  - [État du projet (Mission 054)](#état-du-projet-mission-054)
- **Mission 053 — Rename Prompt after Creation**
  - [Résumé (Mission 053)](#résumé-mission-053)
  - [Tests ajoutés (Mission 053)](#tests-ajoutés-mission-053)
  - [État du projet (Mission 053)](#état-du-projet-mission-053)
- **Mission 052 — Rename Model, Workflow and LoRA after Creation**
  - [Résumé (Mission 052)](#résumé-mission-052)
  - [Tests ajoutés (Mission 052)](#tests-ajoutés-mission-052)
  - [État du projet (Mission 052)](#état-du-projet-mission-052)
- **Mission 051 — Sort Remaining Entity Lists by Name**
  - [Résumé (Mission 051)](#résumé-mission-051)
  - [Tests ajoutés (Mission 051)](#tests-ajoutés-mission-051)
  - [État du projet (Mission 051)](#état-du-projet-mission-051)
- **Mission 050 — Remove Individual Files from a LoRA**
  - [Résumé (Mission 050)](#résumé-mission-050)
  - [Tests ajoutés (Mission 050)](#tests-ajoutés-mission-050)
  - [État du projet (Mission 050)](#état-du-projet-mission-050)
- **Mission 049 — Sort Images and Dataset Galleries by File Date**
  - [Résumé (Mission 049)](#résumé-mission-049)
  - [Tests ajoutés (Mission 049)](#tests-ajoutés-mission-049)
  - [État du projet (Mission 049)](#état-du-projet-mission-049)
- **Mission 048 — Sort Images and Dataset Galleries by Filename**
  - [Résumé (Mission 048)](#résumé-mission-048)
  - [Tests ajoutés (Mission 048)](#tests-ajoutés-mission-048)
  - [État du projet (Mission 048)](#état-du-projet-mission-048)
- **Mission 047 — LoRA Metadata Fiche**
  - [Résumé (Mission 047)](#résumé-mission-047)
  - [Tests ajoutés (Mission 047)](#tests-ajoutés-mission-047)
  - [État du projet (Mission 047)](#état-du-projet-mission-047)
- **Mission 046 — Remove Images from the Workspace Gallery**
  - [Résumé (Mission 046)](#résumé-mission-046)
  - [Tests ajoutés (Mission 046)](#tests-ajoutés-mission-046)
  - [État du projet (Mission 046)](#état-du-projet-mission-046)
- **Mission 045 — Remove Images from a Dataset**
  - [Résumé (Mission 045)](#résumé-mission-045)
  - [Tests ajoutés (Mission 045)](#tests-ajoutés-mission-045)
  - [État du projet (Mission 045)](#état-du-projet-mission-045)
- **Mission 044 — Feed a Dataset from the Images Gallery**
  - [Résumé (Mission 044)](#résumé-mission-044)
  - [Tests ajoutés (Mission 044)](#tests-ajoutés-mission-044)
  - [État du projet (Mission 044)](#état-du-projet-mission-044)
- **Mission 043 — Dashboard Training Indicator**
  - [Résumé (Mission 043)](#résumé-mission-043)
  - [Tests ajoutés (Mission 043)](#tests-ajoutés-mission-043)
  - [État du projet (Mission 043)](#état-du-projet-mission-043)
- **Mission 042 — Dataset Thumbnail Gallery**
  - [Résumé (Mission 042)](#résumé-mission-042)
  - [Tests ajoutés (Mission 042)](#tests-ajoutés-mission-042)
  - [État du projet (Mission 042)](#état-du-projet-mission-042)

---

## v0.2-mission083 — 2026-08-28

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 083 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 083)

L'audit mené après la clôture de Mission 082 a identifié qu'`InferencePage.prompt` (le `QTextEdit` de saisie du prompt de génération) restait la seule Page de l'application à porter un contenu utilisateur non sauvegardé sans être protégée par le contrat dirty-state déjà généralisé aux Missions 038 (`PromptsPage`), 078 (`CharactersPage`/`LoRAPage`/`SettingsPage`) et 079 (branchement dans `MainWindow.closeEvent()`). Un prompt tapé manuellement, ou produit par le Prompt Assistant (potentiellement coûteux à régénérer), était silencieusement perdu à la fermeture complète de l'application ou lors d'un changement de projet, sans aucun avertissement Save/Discard/Cancel.

Un mini-audit contractuel préalable, mené avant toute implémentation, a découvert un risque non trivial : `InferencePage.reset_for_workspace_change()` (propriétaire exclusif du résultat de génération en attente `_pending_path` et de la référence, abonnée à 4 événements Workspace incluant `WORKSPACE_RENAMED`) ne pouvait pas être réutilisée pour vider le prompt — un simple renommage de projet aurait alors silencieusement effacé un brouillon non sauvegardé, un cas ne passant aujourd'hui par aucun guard. Une nouvelle méthode strictement séparée, `reset_for_context_change()`, abonnée à exactement 3 événements (`WORKSPACE_CREATED`/`OPENED`/`CLOSED`, jamais `RENAMED`), a été introduite à la place ; `reset_for_workspace_change()` reste entièrement inchangée.

**Implémentation** : `InferencePage` porte désormais un flag `_dirty` local, mis à `True` par la saisie manuelle et par l'injection d'un résultat du Prompt Assistant, mais jamais par un chargement programmatique (`set_prompt_text()`, utilisé exclusivement par le flux « Send to Inference » de `PromptsPage`, charge une copie de travail non-dirty via `blockSignals()`). `confirm_context_change() -> bool` réutilise le contrat déjà établi par les quatre Pages sœurs, branché en 5ᵉ position — après `Prompts → Characters → LoRA → Settings` — dans les 3 chaînes de `MainWindow` (`new_project()`, `open_project()`, `closeEvent()`), sans réordonner les 4 guards existants. Le choix Save depuis ce guard réutilise le dialogue de nom obligatoire déjà existant (`QInputDialog.getText()`), jamais de nom auto-généré ; la primitive de création (`PromptManager.create()` + gestion des deux échecs) est extraite dans une méthode privée unique partagée avec le bouton « Enregistrer » existant, évitant toute duplication. Une anomalie contractuelle distincte a été découverte et documentée sans être traitée : un résultat de génération non encore Accept/Reject (`_pending_path`) reste silencieusement détruit sans confirmation par `reset_for_workspace_change()` à chaque changement de contexte — hors périmètre de cette mission par décision explicite de l'architecte, candidat à réévaluer par l'audit post-Mission 083.

### Tests ajoutés (Mission 083)

- **30 tests ciblés nets nouveaux** répartis en trois fichiers : `InferencePagePromptDirtyStateTest` (16, `test_inference_page.py`) — saisie manuelle/Assistant marquent dirty, `set_prompt_text()` charge non-dirty puis dirty après édition, `reset_for_context_change()` vide et réinitialise, `reset_for_workspace_change()` (`WORKSPACE_RENAMED`) préserve texte et dirty (régression du mini-audit), et les 8 scénarios de `confirm_context_change()` (non-dirty, texte dirty vide, Cancel, Discard, Save réussi, nom annulé, nom vide, aucun Character, échec de persistence) ; 6 tests nouveaux dans `test_main_window_close_event.py` — garde Inference fausse stoppant la chaîne avant `shutdown()`, ordre des 5 guards, Cancel/Discard/Save/nom-annulé réels via `closeEvent()` avec persistence réelle vérifiée dans `project.json` ; `MainWindowInferencePromptGuardTest` (8, `test_main_window_new_project.py`) — Save/Discard/Cancel réels pour `new_project()`/`open_project()`, garde fausse, ordre des 5 guards.
- Non-régression complète : `test_inference_page.py` (98/98), `test_main_window_close_event.py` (18/18), `test_main_window_new_project.py` (24/24), et les fichiers adjacents instanciant `MainWindow` (`test_main_window_prompts_to_inference.py`, `test_dashboard_page.py`, `test_main_toolbar.py`, `test_main_window_comfyui_settings.py`, `test_main_window_initial_size.py`, `test_main_window_ollama_settings.py`, `test_main_window_rename_project.py` — 40/40, aucune modification requise).
- **1517/1517 tests verts au total** (1487 précédents + 30 nets nouveaux), une exécution complète `unittest discover`, 155.1s, aucun crash.
- Anomalie de test découverte et corrigée avant clôture (aucun impact sur le contrat de production) : deux tests initiaux laissaient `InferencePage._dirty = True` en fin de corps sans le neutraliser directement, collidant avec la vraie méthode `tearDown()` (et non `addCleanup()`) de leur classe — un `QMessageBox.exec()` bloquant non simulé se déclenchait alors au `close()` de fin de test, confirmé par un test isolé à timeout dur. Corrigé en réinitialisant `_dirty = False` directement en fin de corps de test, avant toute exécution de la suite complète.
- Smoke test Qt réel, exécuté par Claude, `MainWindow`/`InferencePage`/`WorkspaceManager`/`CharacterManager`/`PromptManager` réels, Workspaces temporaires réels sur disque (y compris un renommage physique réel) — **PASS, 23/23 assertions** : saisie manuelle + Save avec nom + New (persistence réelle vérifiée dans `project.json`, ancien prompt absent du nouveau contexte), Discard, Cancel, annulation du dialogue de nom, échec de persistence injecté, Send to Inference non-dirty puis dirty après édition, résultat du Prompt Assistant dirty, renommage réel du Workspace préservant texte et dirty-state.

### État du projet (Mission 083)

1517/1517 tests automatisés verts. Commit fonctionnel `3aadb59` (`feat: protect InferencePage.prompt from silent loss on context change`), tag `v0.2-mission083`, GitHub Release publiée. Voir `docs/missions/MISSION_083.md` pour le détail complet.

---

## v0.2-mission082 — 2026-08-28

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 082 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 082)

L'audit mené après la clôture de Mission 081 a réévalué le candidat B2, identifié dès l'audit post-Mission 080 : les trois seules listes `ExtendedSelection` de l'application (`ImagesPage.list_widget`, `DatasetsPage.images_list`, `LoRAPage.files_list`) perdaient silencieusement leur sélection multiple à chaque reconstruction déclenchée par un événement sans rapport avec leur propre contenu (n'importe quel `WORKSPACE_SAVED` provenant d'une mutation Settings/Character/Dataset totalement indépendante), alors que les listes maîtres à sélection simple (`dataset_list`, `lora_list`) restaurent déjà leur sélection par identité depuis des missions antérieures. Reproduit empiriquement (10/10 assertions) avant validation du candidat.

Un mini-audit contractuel préalable a caractérisé empiriquement le comportement Qt exact avant toute implémentation. Deux découvertes ont façonné le contrat final : `list_widget.setCurrentItem(item)` (forme nue) perturbe lui-même, de façon non triviale, une sélection multiple déjà restaurée (`{a, c}` devient `{a, b}` après `setCurrentItem(b)`) — la forme sûre, vérifiée à ne jamais toucher la sélection existante, est `setCurrentItem(item, QItemSelectionModel.NoUpdate)`. Plus important encore : une restauration naïve par identité aurait introduit un nouveau bug distinct — `DatasetManager.add_images()` fait du passthrough sans copie lorsque la source est déjà interne au Workspace, si bien que deux Datasets différents peuvent légitimement partager le même `file_path` (via « Ajouter depuis Images… » sur chacun) ; le même risque existe pour `LoRA.files` (références externes jamais copiées, un même fichier externe pouvant légitimement appartenir à deux LoRA). Un basculement réel entre deux entités partageant coïncidentellement une identité de fichier n'aurait donc jamais dû transférer la sélection — prouvé empiriquement avant d'être exclu par construction.

**Implémentation** : `ImagesPage.update_images()` restaure `selectedItems()`/`currentItem()` par `Qt.UserRole` sans aucun garde cross-entité (chaque Workspace copie ses images sous sa propre racine, collision structurellement impossible). `DatasetsPage.update_datasets()` applique la même restauration pour `images_list`, gardée par une nouvelle variable d'instance dédiée `self._displayed_dataset_id` (lecture de `dataset_list.currentItem()` en tête de méthode s'étant révélée empiriquement invalide comme garde, Qt ayant déjà déplacé `currentItem()` avant l'exécution du handler). `LoRAPage._load_non_metadata_details()` restaure `files_list` par `item.text()` sans jamais restaurer `currentItem()` (aucun consommateur), gardée par la variable d'instance déjà existante `self._loaded_lora_id` (Mission 078) ; `_force_refresh_lora()` continue de passer `restore_selection=False` sans exception, préservant son contrat de reset inconditionnel. Aucun helper générique partagé entre les trois Pages — les trois différences structurelles démontrées (identité, pertinence de `currentItem()`, garde cross-entité) rendaient un traitement uniforme incorrect pour au moins l'une des trois. Aucun changement Domain/Manager/EventBus.

### Tests ajoutés (Mission 082)

- **20 tests ciblés nets nouveaux** répartis en trois nouvelles classes (`ImagesPageSelectionPreservationTest` ×7, `DatasetsPageImagesSelectionPreservationTest` ×8, `LoRAPageFilesSelectionPreservationTest` ×6), exerçant les vrais rebuilds des Pages : refresh sans changement de contenu, restauration de `currentItem()` sans perturber la sélection restaurée (régression `QItemSelectionModel.NoUpdate`), ajout d'un nouvel élément sans sélection artificielle, suppression d'un élément sélectionné avec conservation des survivants, suppression complète avec désactivation correcte des boutons, et les deux régressions cross-entité (Dataset A→B et LoRA A→B avec fichier partagé, aucun transfert).
- **2 tests préexistants réécrits** (leur nom et leurs assertions encodaient littéralement l'ancien comportement bogué) : `test_refresh_after_adding_another_image_preserves_previous_selection` (`test_images_page.py`), `test_reimporting_into_the_same_dataset_preserves_previous_selection` (`test_datasets_page.py`).
- **1 test préexistant retiré** : `test_selecting_again_after_refresh_re_enables_the_button` (`test_images_page.py`), entièrement subsumé par la nouvelle couverture.
- Non-régression : `test_images_page.py` (57/57), `test_datasets_page.py` (53/53), `test_lora_roundtrip.py` (173/173), `test_dataset_roundtrip.py`/`test_character_roundtrip.py` (188/188).
- **1487/1487 tests verts au total** (1467 précédents + 20 nets nouveaux), une exécution complète `unittest discover`, 238.4s, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage`/`DatasetsPage`/`LoRAPage` réelles, `WorkspaceManager`/`CharacterManager`/`DatasetManager`/`LoRAManager` réels, Workspaces temporaires réels sur disque, aucun mock — **PASS, 29/29 assertions** : sélection multiple conservée après refresh sans rapport (3 listes), `currentItem()` restauré (Images/Datasets), suppression d'un élément sélectionné avec conservation des survivants, suppression complète avec désactivation des boutons, et les deux régressions cross-entité (Dataset A→B, LoRA A→B avec fichier partagé) sans aucun transfert.

### État du projet (Mission 082)

1487/1487 tests automatisés verts. Commit fonctionnel `f547e2f` (`feat: preserve multi-selection across unrelated UI rebuilds`), tag `v0.2-mission082`, GitHub Release publiée. Voir `docs/missions/MISSION_082.md` pour le détail complet.

---

## v0.2-mission081 — 2026-08-28

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 081 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 081)

L'audit mené après la clôture de Mission 080 a identifié une asymétrie de robustesse réelle : `OllamaEngine.list_models()`/`generate_text()` laissaient échapper un `ValueError` brut lorsque la base URL Ollama configurée est structurellement invalide (vide, sans schéma reconnu), alors que `ComfyUIEngine.list_checkpoints()`/`list_loras()` protègent déjà ce même cas exact contre `AIBackendError`. Confirmée empiriquement (`urlopen('')`/`urlopen('notaurl')` lèvent bien un `ValueError` brut, jamais `URLError`).

Un mini-audit contractuel préalable avait initialement validé une capture centralisée dans `_request_json()`. L'implémentation des deux tests ciblés a réellement invalidé cette hypothèse : `urllib.request.Request(...)` lève lui-même ce `ValueError` lors de sa propre validation interne, **avant** que `_request_json()` ne soit même invoqué — `list_models()`/`generate_text()` construisent chacune leur `Request(...)` avant d'appeler `_request_json()`. Le correctif final, corrigé avant clôture, place donc un `try/except ValueError` à chacun des deux appelants, encadrant la construction de `Request(...)` et l'appel à `_request_json()`, exactement le pattern per-caller réel de `ComfyUIEngine`. `_request_json()` reste entièrement inchangé — aucune capture large, évitant tout risque de masquer un `ValueError` d'origine différente (notamment `json.JSONDecodeError`, une sous-classe de `ValueError`, déjà gérée par son propre `except` dédié dans un bloc `try` distinct).

**Implémentation** : le correctif est volontairement dupliqué sur `list_models()` et `generate_text()` (2 méthodes publiques seulement, même pattern déjà éprouvé côté ComfyUI, aucune abstraction commune introduite), convertissant en `AIBackendError` avec le message `f"Ollama base URL is invalid: {self._base_url!r}"`. `SettingsPage.refresh_ollama_models()`, `PromptAssistantManager.assist()` et `PromptAssistantWorker` géraient déjà correctement `AIBackendError` — aucun changement nécessaire.

### Tests ajoutés (Mission 081)

- **2 tests ciblés nets nouveaux**, sans mock, même patron que le précédent `ComfyUIEngine` (`test_list_checkpoints_raises_on_structurally_invalid_base_url`) : `test_list_models_raises_on_structurally_invalid_base_url` (`OllamaEngineListModelsTest`) et `test_generate_text_raises_on_structurally_invalid_base_url` (`OllamaEngineGenerateTextTest`) — `OllamaEngine(base_url="")` doit lever `AIBackendError`, jamais `ValueError`, message vérifié pour prouver le chemin « invalid base URL » et non « server unreachable ».
- Non-régression complète : `test_ollama_engine.py` (23/23 — 21 précédents + 2 nets nouveaux) ; `test_settings_page.py`/`test_main_window_ollama_settings.py`/`test_prompt_assistant_dialog.py` (89/89, aucun changement de comportement).
- **1467/1467 tests verts au total** (1465 précédents + 2 nets nouveaux), une exécution complète `unittest discover`, 142.8s, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `SettingsPage`/`SettingsManager`/`ApplicationSettingsManager` réels, `OllamaEngine` réel (aucun mock) — **PASS, 4/4 assertions** sur 2 scénarios réels : URL Ollama vide + clic réel sur « Rafraîchir les modèles » → aucune exception, message « Découverte impossible... » affiché ; URL structurellement invalide (`"notaurl"`) + même clic réel → même résultat contrôlé, aucune trace `ValueError` brute.

### État du projet (Mission 081)

1467/1467 tests automatisés verts. Commit fonctionnel `195543c` (`feat: normalize invalid Ollama URL errors to AIBackendError`), tag `v0.2-mission081`, GitHub Release publiée. Voir `docs/missions/MISSION_081.md` pour le détail complet.

---

## v0.2-mission080 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 080 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 080)

L'audit mené après la clôture de Mission 079 a réévalué la famille dirty-state (close, aucun nouveau chemin utilisateur accessible), les créations Domain-only (closes depuis Mission 072) et `LoRAManager.update()` (déjà résolu par Mission 073). Le seul candidat réel identifié concernait `LoRAManager.set_thumbnail()` : chaque remplacement de miniature (bouton « Choisir une miniature… », réel et visible) copie un nouveau fichier dans `models/loras/<lora_id>/` sans jamais supprimer l'ancien — un artefact technique s'accumulant silencieusement et indéfiniment, sans avertissement, sans limite. Ce candidat nécessitait une décision produit préalable : l'architecte a tranché que l'ancienne copie interne doit être supprimée automatiquement après un remplacement persisté avec succès, sans confirmation supplémentaire, la sécurité des fichiers restant prioritaire.

Un mini-audit technique préalable a découvert que le passthrough de `WorkspaceStorage.copy_into_workspace()` teste `is_inside(source, workspace_root)` contre le Workspace entier, pas contre le dossier propre à la LoRA — `lora.thumbnail` peut donc légitimement pointer n'importe où dans le Workspace (galerie, dataset, dossier d'une autre LoRA). L'ownership ne peut donc être démontrée qu'au niveau `destination_folder` (le dossier privé `models/loras/<lora_id>/` de cette LoRA précise), jamais au niveau du Workspace entier.

**Implémentation** : `LoRAManager.set_thumbnail()` retourne désormais `LoRAThumbnailResult` (NamedTuple minimal `thumbnail`/`cleanup_failed`/`residual_path`, même principe que `LoRADeletionResult`/`DatasetDeletionResult` de Mission 075). Le contrat transactionnel Mission 067 (rollback + compensation de la nouvelle copie sur échec de `save()`) reste entièrement inchangé — le cleanup de l'ancienne miniature ne s'exécute qu'après un `save()` réussi, et uniquement si l'ancien fichier est non vide, différent du nouveau chemin résolu, **et** situé sous `destination_folder`. `FileNotFoundError` est traité comme un nettoyage déjà accompli ; tout autre `OSError` est reporté via `cleanup_failed`/`residual_path` sans jamais lever d'exception ni annuler la nouvelle miniature déjà persistée. `LoRAPage.choose_thumbnail()` affiche un `QMessageBox.warning()` non bloquant en cas d'échec de cleanup, réutilisant le wording déjà établi par `delete_lora()` (Mission 075), jamais présenté comme un échec du changement de miniature.

### Tests ajoutés (Mission 080)

- **7 tests ciblés nets nouveaux** : `LoRAManagerThumbnailCleanupTest` (6, Manager — première miniature sans rien à nettoyer ; remplacement d'une miniature owned avec suppression réelle vérifiée dans `project.json` ; échec de suppression après succès de la nouvelle persistence, `cleanup_failed=True` sans exception ; ancien fichier owned mais déjà absent, traité comme déjà propre ; passthrough hors du dossier owned jamais supprimé, test de sécurité ; passthrough vers le dossier d'une autre LoRA jamais supprimé, test de sécurité) ; `LoRARoundTripTest.test_choose_thumbnail_cleanup_failure_warns_but_keeps_new_thumbnail_active` (1, Presentation).
- Non-régression complète : `test_lora_roundtrip.py` (167/167 — 158 précédents + 8 tests existants adaptés mécaniquement vers `.thumbnail` + 1 test remplacé/renommé pour le nouveau comportement volontaire + 7 nets nouveaux).
- **1465/1465 tests verts au total** (1458 précédents + 7 nets nouveaux), une exécution complète `unittest discover`, 152.1s, aucun crash, aucun blocage.
- Smoke test Qt réel, exécuté par Claude, `LoRAManager`/`LoRAPage`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque — **PASS, 16/16 assertions** sur 5 scénarios réels (miniature externe A copiée et persistée ; miniature externe B active et A réellement supprimée du disque ; passthrough vers une image de galerie réelle survivant intacte à un remplacement ultérieur ; échec réel de suppression après persistence réussie du nouveau fichier, aucune exception, ancien fichier résiduel ; échec réel de `save()` confirmant le contrat Mission 067 intégralement préservé).

### État du projet (Mission 080)

1465/1465 tests automatisés verts. Commit fonctionnel `67fc499` (`feat: automatic cleanup of previous LoRA thumbnail after successful replacement`), tag `v0.2-mission080`, GitHub Release publiée. Voir `docs/missions/MISSION_080.md` pour le détail complet.

---

## v0.2-mission079 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 079 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 079)

L'audit mené après la clôture de Mission 078 a réévalué directement les interactions avec ce que cette mission venait de livrer (les quatre `confirm_context_change()` sur `PromptsPage`/`CharactersPage`/`LoRAPage`/`SettingsPage`, jusque-là uniquement branchés dans `MainWindow.new_project()`/`open_project()`). Il a découvert que `MainWindow.closeEvent()` ne consultait aucun des quatre guards et acceptait la fermeture inconditionnellement (`self.inference_page.shutdown(); super().closeEvent(event)`), même en présence d'un brouillon non sauvegardé sur l'une de ces quatre Pages. Fermer l'application (bouton X, Alt+F4, fermeture OS — aucune action « Quitter » distincte n'existe) effaçait donc silencieusement tout brouillon, alors que le même scénario lors d'un changement de Workspace était déjà correctement protégé depuis les Missions 069/078. Une reproduction empirique réelle (`MainWindow` réel, Workspace temporaire réel sur disque) a confirmé le bug avant toute implémentation.

Un mini-audit contractuel préalable a confirmé, par lecture directe du code, l'absence de toute anomalie sur les quatre points requis : ordre exact identique à New/Open (`prompts_page` → `characters_page` → `lora_page` → `settings_page`) ; contrat identique des quatre `confirm_context_change()` (non dirty → `True` immédiat, Cancel → `False`, Save réussi → `True`, Save échoué → resynchronisation forcée + `False`) ; aucune cinquième Page concernée (la section « Application » de `SettingsPage` n'a structurellement pas ce risque, `ApplicationSettingsManager.update()` n'ayant qu'un seul appelant dans tout `src/`) ; sémantique multi-dirty séquentielle de New/Open confirmée (aucun rollback global d'un Save déjà réussi sur une Page précédente).

**Implémentation** : les quatre guards sont désormais interrogés dans `MainWindow.closeEvent()`, dans le même ordre que New/Open, avant tout code de fermeture. Dès qu'un guard retourne `False` : `event.ignore()` puis `return` immédiat — les guards suivants ne sont jamais appelés, et `inference_page.shutdown()` (Mission 013) n'est jamais atteint. Si les quatre retournent `True`, le comportement de fermeture reste exactement celui d'avant cette mission.

**Anomalie de non-régression détectée et actée avant implémentation** : étendre le guard à `closeEvent()` aurait rendu 9 tests préexistants (2 dans `test_main_window_new_project.py`, 7 dans `test_main_window_prompts_to_inference.py`) susceptibles de déclencher un vrai `QMessageBox.exec()` bloquant pendant leur teardown implicite (`self.addCleanup(self.window.close)`), un risque de blocage du process de test. Validée par l'architecte comme incluse dans le périmètre de Mission 079 (adaptation de non-régression nécessaire au nouveau contrat, pas un élargissement fonctionnel), la correction neutralise uniquement le teardown (via `addCleanup` enregistré après les assertions, LIFO) sans modifier aucune assertion fonctionnelle existante.

### Tests ajoutés (Mission 079)

- **12 tests nets nouveaux** (`tests/integration/test_main_window_close_event.py`), en deux classes : `MainWindowCloseEventOrchestrationTest` (7, guards mockés — tous `True` accepte et appelle `shutdown()` ; chacun des quatre guards `False` individuellement refuse et arrête la chaîne immédiatement ; ordre identique à New/Open ; `shutdown()` jamais appelé si refus) ; `MainWindowCloseEventRealStateTest` (5, état réel — aucune Page dirty ferme immédiatement ; brouillon réel + Cancel refuse et préserve ; + Save accepte et persiste réellement ; échec réel de persistence + Save refuse et resynchronise (contrat Mission 077 inchangé) ; deux Pages dirty simultanément — Prompts sauvegardé puis Characters annulé — refuse sans jamais annuler le Save déjà effectué).
- **1458/1458 tests verts au total** (1446 précédents + 12 nets nouveaux) : non-régression complète sur `test_main_window_new_project.py` (17/17), `test_main_window_prompts_to_inference.py` (7/7) et les 6 autres fichiers `MainWindow()` non concernés (32/32). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `MainWindow`/`SettingsPage`/`CharactersPage`/`PromptsPage`/Managers réels contre des Workspaces temporaires réels sur disque — **PASS, 17/17 assertions** sur 5 scénarios réels (brouillon réel + Cancel refuse et préserve ; + Save accepte et persiste réellement dans `project.json` ; + Discard accepte sans jamais persister ; échec réel de persistence injecté + Save refuse et resynchronise ; deux Pages dirty simultanément confirmant la sémantique séquentielle avec persistance réelle vérifiée sur disque).

### État du projet (Mission 079)

1458/1458 tests automatisés verts. Commit fonctionnel `92b6d94` (`feat: protect dirty drafts on application close (MainWindow.closeEvent)`), tag `v0.2-mission079`, GitHub Release publiée. Voir `docs/missions/MISSION_079.md` pour le détail complet.

---

## v0.2-mission078 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 078 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 078)

L'audit mené après la clôture de Mission 077 a confirmé que la série de sécurisation transactionnelle Domain → persistence (Missions 066–077) est close pour tous les chemins réellement accessibles depuis l'UI. En cherchant un bug réel et démontrable plutôt qu'un besoin produit futur, l'audit a découvert que `CharactersPage.update_characters()`, `LoRAPage.update_loras()` et `SettingsPage.update_settings()` réécrivaient **inconditionnellement** leurs champs texte à chaque événement `WORKSPACE_CREATED/OPENED/SAVED/CLOSED/RENAMED` (et `CHARACTER_*`/`LORA_*` selon la Page) — sans aucune garde de dirty-state. C'est exactement le bug déjà corrigé pour `PromptsPage` par la Mission 038, jamais généralisé à ces trois autres Pages, qui partagent le même patron (bouton « Enregistrer » explicite, pas de sauvegarde sur perte de focus). Une reproduction empirique réelle a confirmé le bug sur les 3 Pages avant toute implémentation.

L'analogie avec `PromptsPage` a été vérifiée Page par Page, pas recopiée mécaniquement : `CharactersPage` n'a aucune dimension de sélection réellement accessible depuis l'UI (liste cachée depuis Mission 026) — seul un Workspace créé/ouvert/fermé constitue un vrai changement de contexte ; `LoRAPage` a une dimension de sélection réellement accessible (liste visible), nécessitant la même garde de changement de sélection que `PromptsPage` ; `SettingsPage` n'a ni sélection ni identité par entité, seulement une distinction Workspace ouvert/fermé.

**Contrat retenu, décliné par Page** : chaque Page reçoit un flag `_dirty`/`_metadata_dirty` local, mis à `True` uniquement par un signal `textChanged` réel (jamais par une écriture programmatique, protégée par `blockSignals()`). Deux méthodes de refresh par Page — `update_*()` (abonnée aux événements non destructeurs, préserve un brouillon dirty) et `reset_for_context_change()` (abonnée aux changements réels de contexte, toujours inconditionnelle). `confirm_context_change()` ajouté aux trois Pages, branché dans `MainWindow.new_project()`/`open_project()`, comme `PromptsPage` depuis Mission 069. `LoRAPage` gagne en plus une garde de changement réel de sélection (Enregistrer/Ignorer/Annuler) et adapte son dialogue de suppression en présence d'un brouillon.

**Affinement par rapport à `PromptsPage`, découvert par régression de tests** : la préservation du brouillon dans `update_*()` exige l'identité affichée inchangée **et** le champ réellement dirty — pas seulement l'identité seule comme le fait `PromptsPage.update_prompts()`. Une première version utilisant uniquement la comparaison d'identifiant a fait régresser 3 tests préexistants attendant qu'une mutation `LoRAManager.update()` directe (hors `save_metadata()`) reste reflétée par la Page. La garde combinée corrige ce cas sans réintroduire le bug initial.

Les contrats de resynchronisation après échec des Missions 073 (LoRA), 074 (Character) et 077 (Settings) restent intégralement préservés — chacun conserve son helper de rechargement inconditionnel, désormais combiné à la remise à `False` du nouveau flag dirty. Aucune nouvelle abstraction transversale de dirty-state, `CharacterManager.delete()` non touché, périmètre strictement limité aux 3 Pages.

### Tests ajoutés (Mission 078)

- **42 tests nets nouveaux** répartis en 3 classes (`CharactersPageDirtyStateTest` 13, `LoRAPageDirtyStateTest` 15, `SettingsPageDirtyStateTest` 14), couvrant pour chaque Page : brouillon préservé à travers un `WORKSPACE_SAVED` indépendant (reproduction permanente des 3 scénarios empiriques de l'audit) ; plusieurs champs dirty simultanément ; save réussi (dirty effacé, persistance réelle) ; save échoué (contrat Missions 073/074/077 préservé) ; absence de faux dirty lors d'un rafraîchissement programmatique ; un rafraîchissement non-dirty reflétant correctement une mutation externe directe du Manager ; changement réel de contexte ; `confirm_context_change()` (Enregistrer/Ignorer/Annuler/échec, avec retry réel) ; pour LoRA spécifiquement, changement réel de sélection et suppression d'une LoRA avec brouillon.
- **1446/1446 tests verts au total** (1404 précédents + 42 nets nouveaux) : non-régression complète sur `test_character_roundtrip.py` (75/75), `test_lora_roundtrip.py` (160/160), `test_settings_roundtrip.py` (42/42), `test_settings_page.py` (48/48) et `test_application_settings_roundtrip.py` (16/16). Trois fichiers câblant `CharactersPage`/`LoRAPage`/`SettingsPage` avec l'ancien schéma d'abonnement à tous les événements Workspace ont dû être corrigés pour refléter la scission `update_*()`/`reset_for_context_change()`. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `CharactersPage`/`LoRAPage`/`SettingsPage`/Managers réels contre un Workspace temporaire réel sur disque — **PASS, 20/20 assertions** sur 7 scénarios réels (saisie et brouillon préservés après mutation indépendante ; save réussi ; échec de persistence réel injecté avec resynchronisation ; sauvegarde ultérieure ne contaminant plus `project.json` ; changement réel de sélection LoRA avec brouillon ; fermeture réelle de Workspace ; retry réel).

### État du projet (Mission 078)

1446/1446 tests automatisés verts. Commit fonctionnel `0c7c30e` (`feat: dirty-state protection for CharactersPage/LoRAPage/SettingsPage`), tag `v0.2-mission078`, GitHub Release publiée. Voir `docs/missions/MISSION_078.md` pour le détail complet.

---

## v0.2-mission077 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 077 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 077)

L'audit exhaustif mené après Mission 076 a relu systématiquement tous les appels `_workspace_manager.save()` des 8 Managers du projet et reconfirmé qu'il ne restait que deux sites non protégés contre la mutation fantôme mémoire/disque sur échec de persistence : `CharacterManager.delete()` et `SettingsManager.update()`. Le premier a été reconfirmé structurellement inaccessible depuis l'UI (`new_button`/`delete_button`/`list_widget` tous `setVisible(False)` de façon permanente dans `characters_page.py`, décision produit Mission 026 : « 1 Workspace = 1 personnage principal »). Le second a été retenu comme périmètre, avec une reproduction empirique confirmant le défaut avant tout code : après un `save()` échoué, `theme`/`language` rejetés restaient en mémoire, `project.json` restant correctement inchangé — mais une sauvegarde ultérieure totalement indépendante persistait ensuite silencieusement ces valeurs rejetées, une contamination croisée plus grave que tous les cas précédemment traités.

Un audit préalable a confirmé que `workspace.settings` est l'objet Domain partagé et durable de la classe `Workspace` (mêmes conventions que `Character`/`Dataset`/`LoRA`/`Model`/`Workflow`/`Training`), qu'aucun autre composant ne conserve de référence vers cette même instance, qu'aucun événement n'est publié par `SettingsManager`, et qu'aucun autre état n'est modifié.

**Stratégie retenue** : rollback local — snapshot des anciennes valeurs de `theme`/`language`, application des nouvelles, tentative de `save()`, restauration exacte des deux anciennes valeurs sur la même instance `Settings` en cas d'échec, ré-élévation de l'exception. Deux stratégies étaient envisageables : candidate-before-save (comme `ApplicationSettingsManager.update()`) ou ce rollback local. La première a été explicitement écartée : `workspace.settings` est un objet Domain partagé, pas un singleton privé au Manager comme `ApplicationSettings._settings` — recopier mécaniquement ce pattern aurait dévié de la convention dominante déjà établie pour toute mise à jour de champ scalaire sur une entité Domain partagée (`CharacterManager.update()`, `LoRAManager.update_name()`, `ModelManager`/`WorkflowManager`).

`SettingsPage.save_settings()` conserve l'interception `WorkspaceManagerError` de Mission 055, sans modification. Une incohérence UX réelle a été identifiée et corrigée : `theme_edit`/`language_edit` sont des `QLineEdit` affichant en permanence la saisie de l'utilisateur — après un rollback, ils continuaient d'afficher la valeur rejetée alors que le Domain (et le disque) étaient revenus à l'ancienne valeur, la même nature d'incohérence déjà traitée pour `DatasetsPage.rename_dataset()` (Mission 070). Un appel explicite à `update_settings(payload=True)` a été ajouté dans le bloc `except`.

Changement limité à 2 fichiers de production (`src/managers/settings_manager.py`, `src/ui/pages/settings_page.py`), 1 fichier de tests, plus le document de mission.

**Cette mission clôt la série de sécurisation transactionnelle Domain → persistence des chemins réellement accessibles depuis l'UI, ouverte à la Mission 066** : il n'existe plus aucun chemin Domain → `WorkspaceManager.save()` réellement accessible depuis l'UI pouvant laisser une mutation fantôme après un échec de persistence. `CharacterManager.delete()` reste le seul site technique non protégé, sciemment non corrigé — il reste structurellement inaccessible depuis l'UI par décision produit, pas par oubli.

### Tests ajoutés (Mission 077)

- **19 tests nets nouveaux** : 14 au niveau `SettingsManagerUpdateRollbackTest` (succès normal inchangé ; `theme` seul, `language` seul et les deux simultanément sur succès ; échec `save()` levant `WorkspaceManagerError` ; restauration exacte des deux valeurs, combinée puis isolément ; même instance `Settings` conservée ; `project.json` inchangé après échec ; aucun événement publié sur échec ; aucun autre état Workspace modifié ; retry réel après rollback avec vérification du contenu exact persisté sur disque ; test de non-régression permanent reproduisant le scénario empirique de l'audit — une sauvegarde ultérieure sans rapport ne persiste plus la valeur rejetée) ; 5 au niveau `SettingsPagePersistenceFailureTest` (erreur critique affichée, `theme_edit`/`language_edit` resynchronisés à l'état Domain restauré, champs et bouton restés activables, `project.json` inchangé, retry réel effectif depuis la Page).
- **1404/1404 tests verts au total** (1385 précédents + 19 nets nouveaux) : non-régression complète sur `test_settings_roundtrip.py` (28/28) et `test_settings_page.py` (48/48, aucune régression sur la couverture Mission 055 existante). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `SettingsPage`/`SettingsManager`/`CharacterManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque — **PASS, 16/16 assertions** sur 4 scénarios réels (mise à jour normale ; échec de persistence injecté avec rollback mémoire/disque/widgets vérifié ; sauvegarde ultérieure totalement indépendante ne contaminant plus `project.json` ; retry réel).

### État du projet (Mission 077)

1404/1404 tests automatisés verts. Commit fonctionnel `1177791` (`feat: rollback SettingsManager.update() theme/language on persistence failure`), tag `v0.2-mission077`, GitHub Release publiée. Voir `docs/missions/MISSION_077.md` pour le détail complet.

---

## v0.2-mission076 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 076 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 076)

L'audit exhaustif mené après Mission 075 a relu systématiquement tous les appels `_workspace_manager.save()` des 8 Managers du projet pour confirmer que la liste de dettes transactionnelles connue restait exhaustive. Il ne restait que quatre sites non protégés contre la mutation fantôme mémoire/disque sur échec de persistence : `DatasetManager.remove_images()`, `LoRAManager.add_files()`, `LoRAManager.remove_files()` (Candidat F) et `SettingsManager.update()` (Candidat I). Le Candidat F a été retenu en priorité : les trois méthodes sont réellement accessibles depuis l'UI (boutons jamais cachés, contrairement à `CharacterManager.delete()`) et présentent le même risque déjà traité par les Missions 066/067/070/071/072/073/074/075 pour d'autres méthodes.

Un audit préalable a confirmé qu'aucune des trois méthodes ne touche jamais un fichier physique, `active_dataset_id`/`active_lora_id`, ni ne publie d'événement dédié — le rollback reste donc strictement Domain-only, sans aucune opération filesystem à compenser (contrairement à Mission 075).

**Stratégie retenue** : snapshot par réassignation, exactement la convention déjà établie par `DatasetManager.add_images()` (Mission 067). Chaque méthode capture l'ancienne liste (`dataset.images`/`lora.files`) par simple référence, puis réassigne l'attribut à une nouvelle liste — jamais de mutation en place (`[:]`/`.extend()`). Comme l'ancienne liste n'est jamais mutée, la restaurer sur échec de `save()` est exacte par construction : même ordre, mêmes doublons éventuels préexistants, même identité d'objet — pas une reconstruction approximative. Les deux méthodes `remove_*`, qui utilisaient auparavant une mutation en place, ont été réécrites dans ce style pour la même garantie.

Les trois call sites Presentation réels (`DatasetsPage.remove_selected_images_from_dataset()`, `LoRAPage.import_files()`, `LoRAPage.remove_selected_files()`) interceptent désormais `WorkspaceManagerError`, affichent `QMessageBox.critical()` et resynchronisent explicitement l'UI via `update_datasets()`/`update_loras()` — `WORKSPACE_SAVED` n'étant jamais publié sur un `save()` en échec, aucun rafraîchissement automatique ne peut être supposé.

`LoRA.files` reste une collection de références externes jamais copiées physiquement (seul `set_thumbnail()` écrit dans le dossier privé d'une LoRA) : retirer un fichier de cette liste ne supprime jamais le fichier physique, préservant la compatibilité avec la future bibliothèque LoRA centralisée.

`SettingsManager.update()` reste explicitement hors périmètre, laissé comme candidat naturel pour un audit ultérieur.

Changement limité à 4 fichiers de production (`src/managers/dataset_manager.py`, `src/managers/lora_manager.py`, `src/ui/pages/datasets_page.py`, `src/ui/pages/lora_page.py`), 2 fichiers de tests, plus le document de mission.

### Tests ajoutés (Mission 076)

- **30 tests nets nouveaux** : 7 au niveau `DatasetManagerRemoveImagesRollbackTest`, 7 au niveau `LoRAManagerAddFilesRollbackTest`, 7 au niveau `LoRAManagerRemoveFilesRollbackTest` (succès normal inchangé ; échec `save()` restaurant la liste exacte avec plusieurs éléments retirés/ajoutés en une seule opération ; `project.json` inchangé après échec ; aucun événement `WORKSPACE_SAVED` publié sur échec ; une autre entité sans rapport non affectée ; préservation de doublons préexistants simulant un `project.json` édité à la main ; pour `add_files()`, un échec ne retire que ce que la tentative venait d'ajouter ; retry réel après rollback avec vérification du contenu exact persisté sur disque) ; 3 au niveau `DatasetsPageRemoveImagesPersistenceFailureTest` et 6 au niveau `LoRAPageFilesPersistenceFailureTest` (erreur affichée, aucune mutation réelle sur échec, `project.json` inchangé, retry réel effectif depuis la Page).
- **1385/1385 tests verts au total** (1355 précédents + 30 nets nouveaux) : non-régression complète sur `test_dataset_roundtrip.py` (113/113) et `test_lora_roundtrip.py` (145/145). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`DatasetManager`/`LoRAManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, fichiers réels écrits/lus à chaque étape — **PASS, 24/24 assertions** sur 3 scénarios réels (Dataset `remove_selected_images_from_dataset()`, LoRA `import_files()`, LoRA `remove_selected_files()`, chacun avec un échec de persistence injecté, rollback vérifié, et un retry réel effectif).

### État du projet (Mission 076)

1385/1385 tests automatisés verts. Commit fonctionnel `a0207d6` (`feat: rollback DatasetManager.remove_images() and LoRAManager.add_files()/remove_files() on persistence failure`), tag `v0.2-mission076`, GitHub Release publiée. Voir `docs/missions/MISSION_076.md` pour le détail complet.

---

## v0.2-mission075 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 075 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 075)

L'audit mené après Mission 074 a révélé, par reproduction empirique directe (création, peuplement puis suppression réelles d'un Dataset/LoRA), que `DatasetManager.delete()`/`LoRAManager.delete()` — déjà protégés au niveau Domain-only depuis Mission 068 — ne supprimaient jamais le dossier physique privé de l'entité (`datasets/<id>/`, `models/loras/<id>/`) : une fuite se produisant sur le chemin **normal** de toute suppression, pas seulement en cas d'échec de persistence rare.

Contrairement aux Missions 068–074, cette mission introduit une suppression physique potentiellement irréversible et a donc suivi une phase de conception séparée, auditée puis explicitement validée par l'architecte avant tout code — audit portant sur la structure physique réelle de Dataset/LoRA, les primitives `WorkspaceStorage` existantes, et les précédents Missions 027/046/066/068.

**Stratégie retenue (Option C)** : déplacement atomique préalable du dossier vers une zone `.trash/` interne du Workspace (réutilisant `WorkspaceStorage.rename_folder()` de Mission 027 telle quelle) → mutation Domain selon le contrat Mission 068 → `WorkspaceManager.save()`. En cas d'échec de persistence, le rollback Domain s'exécute **toujours** en premier — instructions séquentielles qui ne peuvent elles-mêmes échouer — suivi d'une tentative indépendante de restauration filesystem ; si celle-ci échoue également (**double échec**), une `WorkspaceManagerError` enrichie est levée précisant que le Domain est sûr et où se trouve réellement le dossier dans `.trash/`, sur le modèle du précédent de `WorkspaceManager.rename()` (Mission 027). En cas de succès de persistence, le résidu dans `.trash/` est définitivement supprimé en best-effort via la nouvelle primitive `WorkspaceStorage.delete_folder()`, sans jamais rollbacker le Domain déjà persisté si ce nettoyage échoue.

L'audit a confirmé qu'un Dataset entièrement peuplé depuis la galerie Images n'a structurellement aucun dossier physique (cas normal, pas une corruption), et qu'un dossier LoRA supprimable ne peut jamais contenir un fichier partagé ni un fichier de la future bibliothèque LoRA centralisée : `LoRA.files` n'est jamais copié physiquement dans ce dossier (uniquement des références externes), `set_thumbnail()` étant l'unique site d'écriture de tout le projet.

`delete()` retourne désormais un `NamedTuple` par entité (`DatasetDeletionResult`/`LoRADeletionResult` — `deleted`/`cleanup_failed`/`residual_path`) au lieu d'un `bool` nu, même principe que `RemovalResult` de Mission 066 pour un problème structurellement identique. Le texte de confirmation de `DatasetsPage.delete_dataset()` a été mis à jour pour distinguer explicitement les images de galerie (qui survivent) des copies privées importées directement (supprimées avec le dataset).

Restent explicitement hors périmètre, non traités par cette mission : `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; `CharacterManager.delete()` (UI réellement cachée) ; le segfault Qt/PySide6 déjà documenté ; la future bibliothèque LoRA centralisée (seulement vérifiée pour compatibilité, non implémentée).

Changement limité à 5 fichiers de production (`src/infrastructure/storage/workspace_storage.py`, `src/managers/dataset_manager.py`, `src/managers/lora_manager.py`, `src/ui/pages/datasets_page.py`, `src/ui/pages/lora_page.py`), 3 fichiers de tests, plus le document de mission.

### Tests ajoutés (Mission 075)

- **22 tests nets nouveaux** : 9 au niveau `DatasetManagerPhysicalDeletionTest` et 10 au niveau `LoRAManagerPhysicalDeletionTest` (suppression normale avec dossier réel ; absence de dossier, cas normal ; échec du déplacement initial, abandon avant toute mutation ; échec `save()` restaurant le dossier à son emplacement d'origine avec son contenu exact ; **double échec** — `save()` et le renommage inverse échouent tous deux — Domain néanmoins restauré au même index avec `active_*_id`, dossier laissé dans `.trash/`, aucune autre entité touchée, erreur contenant l'information de récupération manuelle ; échec du nettoyage définitif après persistence réussie, jamais de rollback Domain ; retry réel ; non-impact sur une entité voisine ; collision de noms de transit) ; 3 au niveau Presentation (texte de confirmation Dataset mis à jour, warning affiché sur `cleanup_failed` pour Dataset et LoRA).
- **1355/1355 tests verts au total** (1333 précédents + 22 nets nouveaux) : non-régression complète sur `test_dataset_roundtrip.py` (103/103), `test_lora_roundtrip.py` (125/125), `test_training_roundtrip.py` (67/67, 3 assertions adaptées mécaniquement au nouveau type de retour) et `test_workspace_roundtrip.py` (97/97). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`DatasetManager`/`LoRAManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, fichiers réels écrits/lus à chaque étape — **PASS, 19/19 assertions** sur 5 scénarios réels (suppression normale et rollback sur échec de persistence pour Dataset et LoRA, plus un flux Presentation réel).

### État du projet (Mission 075)

1355/1355 tests automatisés verts. Commit fonctionnel `3742d38` (`feat: transactional physical cleanup of Dataset/LoRA folders on deletion`), tag `v0.2-mission075`, GitHub Release publiée. Voir `docs/missions/MISSION_075.md` pour le détail complet.

---

## v0.2-mission074 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 074 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 074)

L'audit mené après Mission 073 a réévalué la dette regroupée depuis plusieurs missions sous l'intitulé unique « `CharacterManager.delete()`/`update()` — UI cachée, inatteignable ». Une vérification directe du code a confirmé que cette caractérisation reste exacte pour `delete()` (`CharactersPage.new_button`/`.delete_button`/`.list_widget` sont bien `setVisible(False)`, jamais réaffichés) mais **inexacte pour `update()`** : `CharactersPage.save_identity()`, branché sur `self.save_identity_button` — un bouton jamais caché, « Enregistrer l'identité » — appelait `CharacterManager.update()` sans aucune protection, ni au niveau Manager (pas même un `try` nu autour de `self._workspace_manager.save()`) ni au niveau Presentation. C'est le chemin d'édition principal et le plus utilisé de toute l'entité Character.

**Correction d'audit documentée** : `CharacterManager.delete()` reste inaccessible depuis l'UI réelle (confirmé) ; `CharacterManager.update()`, à l'inverse, est actif et accessible via le bouton « Enregistrer l'identité » — les deux méthodes ne doivent plus être regroupées sous une même dette « UI cachée » dans les audits futurs.

Un mini-audit contractuel dédié a confirmé que `update()` mute exactement 7 champs (`name`/`bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token`), ne touche aucun autre état (jamais `active_character_id`) et ne publie aucun événement, avant comme après cette mission — invariant vérifié par test plutôt que supposé. `CharacterManager.update()` reçoit désormais un rollback local exact : capture des 7 valeurs précédentes avant mutation, et en cas de `WorkspaceManagerError`, restauration simultanée des 7 champs sur le même objet `Character` avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée.

`CharactersPage.save_identity()` intercepte désormais `WorkspaceManagerError` et affiche `QMessageBox.critical()`. Une découverte architecturale a directement justifié le choix UX : `WorkspaceManager.save()` ne publie `WORKSPACE_SAVED` qu'après une écriture réussie, et en production tous les `update_X()` de Page — dont `CharactersPage.update_characters()` — y sont abonnés, ce qui resynchronise déjà silencieusement la fiche après un succès. Un échec ne publie jamais cet événement, donc `save_identity()` appelle désormais explicitement `update_characters()` dans son bloc `except`, resynchronisant les 7 widgets sur les valeurs restaurées — décision confirmée par lecture directe du wiring réel de `main_window.py`, pas seulement par analogie avec les précédents `DatasetsPage.rename_dataset()` (Mission 070) et `LoRAPage.save_metadata()` (Mission 073).

Restent explicitement hors périmètre, non traités par cette mission : `CharacterManager.delete()` (UI réellement cachée) ; `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA après suppression ; le segfault Qt/PySide6 déjà documenté.

Changement strictement limité à 2 fichiers de code (`src/managers/character_manager.py`, `src/ui/pages/characters_page.py`) et 1 fichier de tests, plus le document de mission.

### Tests ajoutés (Mission 074)

- **11 tests nets nouveaux** : 7 au niveau Manager (`CharacterManagerUpdateRollbackTest` — succès normal des 7 champs, échec `save()` restaurant les 7 champs simultanément sur le même objet, échec restaurant un seul champ modifié isolément afin de ne pas prouver le rollback uniquement sur le cas à 7 champs, aucun événement publié sur échec — invariant vérifié, `project.json` inchangé, un autre Character préexistant non concerné inchangé via `assertIs`, retry réellement neuf après rollback persistant effectivement) ; 4 au niveau Presentation (`CharactersPageIdentityPersistenceFailureTest` — erreur affichée et Character restant présent/visible, Domain restauré **et** les 7 widgets resynchronisés sur les valeurs restaurées via `update_characters()`, `project.json` inchangé, retry réel effectif depuis la Page).
- **1333/1333 tests verts au total** (1322 précédents + 11 nets nouveaux) : non-régression complète sur `test_character_roundtrip.py` (62/62). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `CharactersPage`/`CharacterManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque — **PASS, 9/9 assertions** sur 3 scénarios réels (update normal, échec de persistence avec rollback mémoire/disque/widgets vérifié, retry réel).

### État du projet (Mission 074)

1333/1333 tests automatisés verts. Commit fonctionnel `ec15312` (`feat: rollback CharacterManager.update() identity on persistence failure`), tag `v0.2-mission074`, GitHub Release publiée. Voir `docs/missions/MISSION_074.md` pour le détail complet.

---

## v0.2-mission073 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 073 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 073)

L'audit mené après Mission 072 a confirmé que `LoRAManager.update()` (les 4 métadonnées texte `engine`/`architecture`/`trigger_word`/`version`, mutées simultanément) mutait ces champs en mémoire puis appelait `WorkspaceManager.save()` **sans aucun `try/except`**. `LoRAPage.save_metadata()`, son unique site d'appel Presentation, n'interceptait rien non plus. Un échec de `save()` laissait les 4 champs mutés en mémoire sans persistance ni message d'erreur — le même motif déjà corrigé pour `create()`/`delete()`/les mutations scalaires par Missions 068/070/071/072, jamais traité pour cette méthode multi-champs (explicitement exclue du périmètre de Mission 070 du fait de son contrat à 4 champs simultanés).

Un mini-audit contractuel dédié a confirmé que `update()` ne touche aucun autre état que les 4 champs (jamais `active_lora_id`, jamais `name`/`files`/`thumbnail`) et ne publie aucun événement, avant comme après cette mission — même contrat que `CharacterManager.update()`, vérifié par test plutôt que supposé. `LoRAManager.update()` reçoit désormais un rollback local exact : capture des 4 valeurs précédentes avant mutation, et en cas de `WorkspaceManagerError`, restauration simultanée des 4 champs sur le même objet `LoRA` avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée.

`LoRAPage.save_metadata()` intercepte désormais `WorkspaceManagerError` et affiche `QMessageBox.critical()`. Contrairement aux missions create()/delete(), cette mission nécessitait une décision UX explicite : les 4 `QLineEdit` de métadonnées sont des champs de saisie directe qui, sans rafraîchissement, continueraient d'afficher les valeurs rejetées après un échec alors que le Domain aurait été restauré. `save_metadata()` appelle désormais `update_loras()` dans son bloc `except`, resynchronisant les 4 widgets sur les valeurs restaurées — décision directement dérivée du précédent déjà établi par `DatasetsPage.rename_dataset()` (Mission 070), pas une nouvelle décision produit.

Restent explicitement hors périmètre, non traités par cette mission : `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA après suppression ; `CharacterManager.delete()`/`update()` (UI cachée, inatteignable) ; le segfault Qt/PySide6 déjà documenté.

Changement strictement limité à 2 fichiers de code (`src/managers/lora_manager.py`, `src/ui/pages/lora_page.py`) et 1 fichier de tests, plus le document de mission.

### Tests ajoutés (Mission 073)

- **11 tests nets nouveaux** : 7 au niveau Manager (`LoRAManagerMetadataRollbackTest` — succès normal des 4 champs, échec `save()` restaurant les 4 champs simultanément sur le même objet, échec restaurant un seul champ modifié isolément afin de ne pas prouver le rollback uniquement sur le cas multi-champs, aucun événement publié sur échec — invariant vérifié, `project.json` inchangé, une LoRA préexistante non concernée inchangée via `assertIs`, retry réellement neuf après rollback persistant effectivement) ; 4 au niveau Presentation (`LoRAPageMetadataPersistenceFailureTest` — erreur affichée et LoRA restant visible/sélectionnée, Domain restauré **et** widgets resynchronisés sur les valeurs restaurées via `update_loras()`, `project.json` inchangé, retry réel effectif depuis la Page).
- **1322/1322 tests verts au total** (1311 précédents + 11 nets nouveaux) : non-régression complète sur `test_lora_roundtrip.py` (114/114). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `LoRAPage`/`LoRAManager`/`WorkspaceManager`/`CharacterManager` réels contre un Workspace temporaire réel sur disque — **PASS, 10/10 assertions** sur 3 scénarios réels (update normal, échec de persistence avec rollback mémoire/disque vérifié, retry réel).

### État du projet (Mission 073)

1322/1322 tests automatisés verts. Commit fonctionnel `add35c1` (`feat: rollback LoRAManager.update() metadata on persistence failure`), tag `v0.2-mission073`, GitHub Release publiée. Voir `docs/missions/MISSION_073.md` pour le détail complet.

---

## v0.2-mission072 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 072 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 072)

L'audit mené après Mission 071 a révélé que les 7 méthodes `create()` (`DatasetManager`, `CharacterManager`, `ModelManager`, `WorkflowManager`, `LoRAManager`, `TrainingManager`, `PromptManager`) sont rigoureusement isomorphes : construction de l'entité → `append()` dans la collection Domain parente → `WorkspaceManager.save()` **sans aucun `try/except`** → publication de l'événement de succès. Aucun des 9 sites d'appel Presentation n'interceptait quoi que ce soit autour de l'appel. Une reproduction empirique réelle (`QApplication` réel, `DatasetsPage` réelle, `WorkspaceStorage.save` mocké, déclenchement via `button.clicked.emit()`) a confirmé qu'un échec laisse l'entité créée résidente en mémoire alors que `project.json` n'a jamais été modifié, sans aucun message d'erreur — le processus ne crashe pas (PySide6 sans `excepthook` personnalisé imprime et continue), mais une sauvegarde ultérieure totalement indépendante persiste alors silencieusement cette création jamais confirmée. C'était la dernière famille homogène et la plus largement utilisée du triptyque create/update/delete encore non sécurisée.

Chacune des 7 méthodes reçoit désormais le même contrat de rollback local déjà établi par Missions 068/070/071 : en cas de `WorkspaceManagerError`, la même instance tout juste ajoutée est retirée de sa collection avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée. Les 9 handlers Presentation correspondants interceptent `WorkspaceManagerError` et affichent `QMessageBox.critical()` ; aucun rafraîchissement de liste n'est nécessaire, l'entité n'ayant jamais été ajoutée visuellement.

Une découverte pendant l'implémentation : `character_manager.py` et `characters_page.py` n'importaient jamais `WorkspaceManagerError` — le seul Manager/Page du projet dans ce cas, ajout strictement nécessaire au périmètre, détecté immédiatement par un `NameError` lors des tests et corrigé avant toute autre action.

Restent explicitement hors périmètre, non traités par cette mission : `LoRAManager.update()` (4 métadonnées) ; `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; `CharacterManager.delete()`/`update()` (UI cachée, inatteignable) ; le segfault Qt/PySide6 déjà documenté.

Changement strictement limité à 7 Managers, 8 Pages et leurs fichiers de tests correspondants (24 fichiers au total, incluant le nouveau document de mission).

### Tests ajoutés (Mission 072)

- **66 tests nets nouveaux** : 42 au niveau Manager (6 par entité × 7 — succès normal, échec `save()` retirant l'entité fantôme au même objet, aucun événement de succès publié, `project.json` inchangé, retry réellement neuf après rollback persistant effectivement, entité préexistante non concernée inchangée via `assertIs`) ; 24 au niveau Presentation (3 par site × 8, `PromptsPage` comptant pour 5 du fait de ses 2 sites — erreur affichée et liste UI vide/inchangée, `project.json` inchangé, retry réel effectif) ; 1 test `InferencePage` (style mock existant, vérifiant que `select()`/`update_text()` ne sont jamais appelés sur l'échec).
- **1311/1311 tests verts au total** (1245 précédents + 66 nets nouveaux) : non-régression complète sur les 8 fichiers de tests concernés (`test_dataset_roundtrip.py` + `test_character_roundtrip.py` + `test_model_roundtrip.py` + `test_workflow_roundtrip.py` + `test_lora_roundtrip.py` + `test_training_roundtrip.py` + `test_prompt_roundtrip.py` + `test_inference_page.py`). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`CharactersPage`/`ModelsPage`/`WorkflowsPage`/`LoRAPage`/`TrainingPage`/`PromptsPage` réelles contre des Workspaces temporaires réels sur disque — **PASS, 38/38 assertions** sur 7 scénarios réels (une création normale, un échec de persistence avec rollback mémoire/disque vérifié, un retry réel — pour chacune des 7 entités).

### État du projet (Mission 072)

1311/1311 tests automatisés verts. Commit fonctionnel `2319b0b` (`feat: rollback Domain-only create() on persistence failure`, suivi du correctif documentaire `e93af7c`), tag `v0.2-mission072`, GitHub Release publiée. Voir `docs/missions/MISSION_072.md` pour le détail complet.

---

## v0.2-mission071 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 071 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 071)

L'audit mené après Mission 070 a révélé que Mission 068 (« Rollback Domain-Only Deletions on Persistence Failure ») énonce explicitement son périmètre comme portant sur **cinq** Managers — `DatasetManager.delete()`, `LoRAManager.delete()`, `ModelManager.delete()`, `TrainingManager.delete()`, `WorkflowManager.delete()` — et ne mentionne `PromptManager.delete()` nulle part, y compris dans sa section « Hors périmètre », qui liste pourtant explicitement `CharacterManager.delete()` comme exclusion volontaire. `PromptManager.delete()` n'avait donc jamais été analysé ni corrigé par Mission 068 : un oubli d'audit, non une exclusion délibérée. Une reproduction empirique a confirmé qu'il suivait exactement le motif pré-Mission 068 : retrait de `character.prompts` en mémoire → `WorkspaceManager.save()` sans aucun `try/except`, laissant une suppression fantôme en mémoire silencieusement persistable par une sauvegarde ultérieure totalement indépendante en cas d'échec.

`PromptManager.delete()` reçoit désormais le contrat de rollback **rigoureusement identique** aux cinq Managers déjà corrigés par Mission 068 : capture de l'index d'origine et de l'ancien `active_prompt_id`, retrait, `save()`, et en cas de `WorkspaceManagerError`, réinsertion du même objet Prompt à son index exact et restauration de `active_prompt_id`, avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée. `PromptsPage.delete_prompt()` intercepte `WorkspaceManagerError` et affiche `QMessageBox.critical()` ; aucun rafraîchissement manuel de `prompt_list` n'est nécessaire, la ligne n'étant retirée que réactivement via `PROMPT_DELETED`, jamais publié en cas d'échec.

Restent explicitement hors périmètre, non traités par cette mission : `create()` Domain-only (6 entités) ; `LoRAManager.update()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA ; segfault Qt/PySide6 ; `CharacterManager.delete()` ; toute abstraction transactionnelle générique.

Changement strictement limité à `PromptManager.delete()`, `PromptsPage.delete_prompt()` et leurs fichiers de tests correspondants (4 fichiers au total, incluant le nouveau document de mission).

### Tests ajoutés (Mission 071)

- **10 tests nets nouveaux** : au niveau Manager (`PromptManagerDeleteRollbackTest`, 6 tests) — succès normal ; échec `save()` restaurant le même objet à l'index exact (`assertIs`) ; `active_prompt_id` restauré ; un `active_prompt_id` pointant vers un autre Prompt reste inchangé ; `project.json` inchangé octet pour octet après échec ; retry après échec constituant une tentative réellement neuve. Au niveau Presentation (`PromptsPageDeletePersistenceFailureTest`, 4 tests) — erreur affichée et Prompt toujours présent/sélectionné ; `project.json` inchangé ; retry réel effectif ; suppression tentée avec un brouillon dirty (Discard puis échec) préservant le texte édité et l'état dirty.
- **1245/1245 tests verts au total** (1235 précédents + 10 nets nouveaux) : 109/109 non-régression complète sur `test_prompt_roundtrip.py`, 3.6s. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction.
- Smoke test Qt réel, exécuté par Claude, `PromptsPage`/`PromptManager`/`WorkspaceManager`/`CharacterManager` réels contre un Workspace temporaire réel sur disque — **PASS, 24/24 assertions** sur trois scénarios réels : suppression normale, échec de persistence + retry, brouillon dirty préservé après échec de suppression.
- Un incident de test auto-détecté et corrigé pendant l'implémentation est documenté dans `docs/missions/MISSION_071.md` (section 11) : un mock initial sans effet sur une méthode jamais appelée par le code réel a laissé s'exécuter un vrai dialogue Qt non mocké pendant ~32 minutes ; corrigé par adoption de l'idiome de mock déjà établi ailleurs dans le même fichier de tests.

### État du projet (Mission 071)

1245/1245 tests automatisés verts. Commit fonctionnel `33101ef9bbe1628a6c6c0e48405d8787b330d31c` (`feat: rollback PromptManager.delete() on persistence failure`), tag `v0.2-mission071`, GitHub Release publiée. Voir `docs/missions/MISSION_071.md` pour le détail complet.

---

## v0.2-mission070 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 070 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 070)

L'audit mené après Mission 069, puis un mini-audit contractuel dédié, ont démontré empiriquement qu'un groupe homogène de 9 méthodes Domain-only (`DatasetManager.update_name()`, `LoRAManager.update_name()`, `ModelManager.update_name()`/`update_file_path()`, `TrainingManager.update_name()`, `WorkflowManager.update_name()`/`update_file_path()`, `PromptManager.update_name()`/`update_text()`) mutent un scalaire **avant** `WorkspaceManager.save()`, sans aucun rollback en cas d'échec de persistence. Deux conséquences concrètes ont été reproduites : une mutation « fantôme » reste résidente en mémoire après un échec, silencieusement persistable par un `save()` ultérieur sans rapport ; et le garde d'idempotence préexistant (`if old == new: return False`), légitime pour éviter un `save()` redondant sur une valeur déjà persistée, neutralisait également tout retry identique après un premier échec — la valeur en mémoire ayant déjà été mutée, un second appel avec la même valeur ne relevait même plus l'exception, il retournait silencieusement `False` sans jamais retenter `save()`.

Un cas prioritaire distinct a également été isolé et corrigé : `PromptsPage.on_prompt_selection_changed()`, où un changement de Prompt avec un brouillon dirty et un choix « Enregistrer » qui échoue laissait Qt avec une sélection visuelle déjà avancée alors que `active_prompt_id`/`_loaded_prompt_id` restaient bloqués sur l'ancien Prompt — une divergence UI/Domain réelle. Le correctif réutilise **exactement** le mécanisme de restauration visuelle déjà existant pour le choix Cancel (`blockSignals(True)` → `setCurrentItem(previous)` → `blockSignals(False)` → synchronisation du bouton Supprimer), sans réécrire le système dirty-state de Missions 038/069.

Chacune des 9 méthodes reçoit désormais le même contrat de rollback local : capture de l'ancienne valeur, mutation, `save()`, et en cas de `WorkspaceManagerError`, restauration exacte de l'ancienne valeur sur le même objet avant de relever l'exception — aucun snapshot Workspace global, aucun mécanisme filesystem, aucune abstraction transactionnelle partagée, chaque Manager implémentant son propre rollback local comme pour Missions 066/067/068. Les 10 handlers Presentation correspondants interceptent `WorkspaceManagerError` et affichent `QMessageBox.critical()` : pour les 6 renommages, le refresh `update_*()` déjà existant de la Page redessine automatiquement le widget avec l'ancienne valeur (aucune restauration manuelle) ; pour les 2 chemins de fichiers (Model/Workflow), le widget concerné n'est jamais pré-muté visuellement (peuplé uniquement par le refresh d'événement, jamais directement par le picker), un simple `try/except` suffit.

Restent explicitement hors périmètre, non traités par cette mission : `LoRAManager.update()` et ses 4 métadonnées (cycle Presentation par bouton multi-champs, contrat structurellement distinct des 9 autres méthodes) ; les créations Domain-only (candidat futur important, non prédéterminé) ; `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `CharacterManager.update()` (UI cachée, inatteignable) ; la miniature LoRA physique potentiellement orpheline après remplacement ; le segfault Qt/PySide6 déjà documenté ; toute abstraction transactionnelle générique.

Changement strictement limité à 6 Managers, 6 Pages et leurs fichiers de tests correspondants (19 fichiers au total, incluant le nouveau document de mission).

### Tests ajoutés (Mission 070)

- **56 tests nets nouveaux**, répartis sur les 6 entités concernées : pour chacune des 9 méthodes Manager — succès normal ; échec `save()` restaurant l'ancienne valeur exacte sur le même objet (identité vérifiée par `assertIs`) ; `project.json` inchangé octet pour octet après échec ; aucun événement de succès publié ; retry avec la même valeur précédemment refusée constituant une tentative réelle après rollback (garde d'idempotence toujours valide sur une valeur réellement persistée). Pour les 6 renommages Presentation : erreur affichée, widget restauré à l'ancienne valeur via le refresh existant, retry ultérieur réellement persisté. Pour les 2 chemins de fichiers : erreur affichée, aucune divergence visuelle à corriger. Pour `PromptsPage.on_prompt_selection_changed()` : scénario complet (brouillon dirty → sélection d'un autre Prompt → Save → échec → sélection visuelle restaurée → `active_prompt_id`/`_loaded_prompt_id` inchangés → texte utilisateur conservé → `_dirty=True` → `Prompt.text` rollbacké → `project.json` inchangé → retry ultérieur réussi). Pour `PromptsPage.save_text()` (troisième site d'appel réel de `update_text()`) : erreur affichée, aucune mutation fantôme.
- **1235/1235 tests verts au total** (1179 précédents + 56 nets nouveaux) : 457/457 non-régression sur les 8 fichiers de tests concernés (`test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_model_roundtrip.py` + `test_workflow_roundtrip.py` + `test_training_roundtrip.py` + `test_prompt_roundtrip.py` + `test_main_window_new_project.py` + `test_main_window_rename_project.py`). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`ModelsPage`/`WorkflowsPage`/`TrainingPage`/`PromptsPage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 40/40 assertions** sur sept scénarios réels : les 6 renommages, les 2 chemins de fichiers Model/Workflow, et le cas complet Prompt → Prompt (brouillon dirty, Save en échec, sélection visuelle restaurée, retry ultérieur réussi).

### État du projet (Mission 070)

1235/1235 tests automatisés verts. Commit fonctionnel `a9e162473379c8c54fa214fdcda423e1580a1c4d` (`feat: rollback scalar Domain-only mutations on persistence failure`), tag `v0.2-mission070`, GitHub Release publiée. Voir `docs/missions/MISSION_070.md` pour le détail complet.

---

## v0.2-mission069 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 069 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 069)

L'audit mené après Mission 068 avait révélé, par reproduction Python réelle, qu'un brouillon `PromptsPage` non sauvegardé était silencieusement perdu lors d'un `MainWindow.new_project()`/`open_project()` : `WorkspaceManager.create()`/`.open()` remplacent `current_workspace` **avant** de publier `WORKSPACE_CREATED`/`WORKSPACE_OPENED`, événements auxquels `PromptsPage.reset_for_context_change()` est abonné — au moment où ce handler s'exécute, le contexte a déjà changé, rendant tout Save ou Cancel structurellement impossibles à ce stade. Mission 038 protégeait déjà la navigation prompt-à-prompt et la suppression via un dialogue Save/Discard/Cancel (`_confirm_discard_before_switch()`), mais jamais les deux seuls chemins réellement atteignables par un utilisateur qui détruisent le contexte Workspace lui-même.

Mission 069 introduit `PromptsPage.confirm_context_change() -> bool`, seule addition à l'API de la Page, réutilisant verbatim le dialogue existant de Mission 038 sans dupliquer sa logique. Sans brouillon dirty, la méthode retourne `True` immédiatement, sans aucun dialogue — New/Open se comporte exactement comme avant. Avec un brouillon dirty : **Cancel** retourne `False` sans la moindre mutation (Workspace, Prompt actif, texte de l'éditeur et `_dirty` restent strictement inchangés, le changement de projet est entièrement abandonné) ; **Discard** retourne `True` sans persister, laissant `reset_for_context_change()` assurer seul le nettoyage une fois le nouveau Workspace chargé ; **Save** appelle `prompt_manager.update_text()` pendant que l'**ancien** Workspace est encore actif — en cas de succès, persistance réelle dans l'ancien projet puis `True` ; en cas d'échec (`WorkspaceManagerError`), `QMessageBox.critical()` est affiché, `_dirty` reste `True`, et la méthode retourne `False` — un échec de persistence ne permet jamais au changement de Workspace de continuer.

`MainWindow.new_project()`/`open_project()` reçoivent chacun un unique appel à `self.prompts_page.confirm_context_change()`, inséré après l'acceptation du sélecteur (`NewProjectDialog`/`QFileDialog.getExistingDirectory`) et avant tout appel à `workspace_manager.create()`/`.open()`. Si le sélecteur est annulé par l'utilisateur, le guard n'est jamais invoqué — aucun dialogue dirty-state superflu dans ce cas. Aucun framework générique de dirty-state/veto n'a été introduit : `PromptsPage` reste aujourd'hui la seule Page concernée par ce mécanisme.

Restent explicitement hors périmètre, non traités par cette mission : le défaut préexistant de `on_prompt_selection_changed()` (un `update_text()` en échec pendant un changement prompt→prompt n'est pas intercepté, `_dirty` reste bloqué à `True` sans message, avec un risque de divergence entre la sélection visuelle Qt et la sélection Domain) ; le cas `_dirty=True` sans Prompt actif (texte du Prompt Assistant jamais rattaché, `update_text()` y est un no-op silencieux hérité de Mission 038) ; toute protection lors de la fermeture générale de l'application (`closeEvent()` ne touche aujourd'hui ni `workspace_manager` ni `PromptsPage`) ; et les créations Domain-only sans rollback, candidat A distinct conservé pour un audit futur.

Changement strictement limité à `src/ui/pages/prompts_page.py` et `src/ui/main_window.py`.

### Tests ajoutés (Mission 069)

- **17 tests nets nouveaux** : `PromptsPageConfirmContextChangeTest` (5, dans `test_prompt_roundtrip.py`) — pas de dirty → `True` sans dialogue ; Save réussi → texte persisté dans l'ancien Workspace, `True`, `_dirty=False` ; Discard → `True`, rien persisté ; Cancel → `False`, tout inchangé (Workspace, Prompt actif, texte éditeur, `_dirty`) ; Save en échec → `QMessageBox.critical` affiché, `False`, `_dirty` toujours `True`, `project.json` inchangé. `MainWindowConfirmContextChangeTest` (12, dans `test_main_window_new_project.py`, réel `MainWindow` avec deux dossiers de projet réels) — `new_project()`/`open_project()` × Save/Discard/Cancel avec persistance/absence de persistance vérifiée réellement dans l'ancien `project.json` ; guard retournant `False` → `create()`/`open()` jamais appelé ; picker annulé → guard jamais appelé ; ordre d'exécution guard-avant-`create()`/`open()` vérifié explicitement.
- **1179/1179 tests verts au total** (1162 précédents + 17 nets nouveaux) : 112/112 non-régression sur `test_prompt_roundtrip.py` + `test_main_window_new_project.py` + `test_main_window_rename_project.py`. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `MainWindow`/`PromptsPage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 24/24 assertions** sur huit scénarios réels : New Project × Save/Discard/Cancel/échec de Save injecté/picker annulé, Open Project × Save/Discard/Cancel (avec un second projet réel indépendamment pré-créé).

### État du projet (Mission 069)

1179/1179 tests automatisés verts. Commit fonctionnel `896fb51c8af3024096984fa4075df008d696ea94` (`feat: protect PromptsPage draft before New/Open Project`), tag `v0.2-mission069`, GitHub Release publiée. Voir `docs/missions/MISSION_069.md` pour le détail complet.

---

## v0.2-mission068 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 068 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 068)

L'audit mené après Mission 067 a démontré empiriquement que les suppressions Domain-only (`DatasetManager.delete()`, `LoRAManager.delete()`, `ModelManager.delete()`, `TrainingManager.delete()`, `WorkflowManager.delete()`) suivent toutes le même ordre non transactionnel : retrait de l'objet de la collection en mémoire → `save()`, sans aucun rollback en cas d'échec de persistence. Motif rigoureusement identique dans les cinq Managers, confirmé par lecture directe du code. Conséquence : un échec de `save()` laisse la suppression appliquée en mémoire — l'objet a disparu de `character.datasets`/`character.loras`/`character.trainings`/`workspace.models`/`workspace.workflows` — sans que `project.json` ne soit modifié et sans qu'aucun événement de succès ne soit publié. L'utilisateur ne voit rien se passer (aucun message, aucun refresh de liste), mais l'entité est réellement absente du Domain ; une sauvegarde ultérieure sans rapport la persisterait alors silencieusement, sans nouvelle confirmation.

Mission 068 capture, pour chacun des cinq Managers, l'index exact de l'objet dans sa collection et la valeur courante de `active_*_id` avant toute mutation. Si `save()` échoue après le retrait, le même objet Python (jamais recréé) est réinséré à son index exact et `active_*_id` est restauré avant que l'exception `WorkspaceManagerError` ne soit relevée — un rollback purement local, Domain-only, sans aucune opération filesystem ni snapshot du Workspace entier, puisqu'aucun fichier n'est jamais en jeu dans ces cinq suppressions. La garde préexistante « Dataset référencé par une Training → suppression refusée » (Mission 062) continue de s'exécuter avant toute mutation et reste donc entièrement en dehors du nouveau chemin transactionnel — un Dataset dont la suppression est refusée par cette garde n'entre jamais dans le rollback.

Les cinq handlers Presentation correspondants (`DatasetsPage.delete_dataset()`, `LoRAPage.delete_lora()`, `ModelsPage.delete_model()`, `TrainingPage.delete_training()`, `WorkflowsPage.delete_workflow()`) interceptent désormais `WorkspaceManagerError` et affichent `QMessageBox.critical()` — la suppression n'est jamais présentée comme réussie. Aucun refresh UI supplémentaire n'a été nécessaire : la confirmation (Mission 062) et le retrait effectif de la liste ne se produisent que via l'événement `*_DELETED`, jamais publié en cas d'échec — l'entité n'a donc jamais été retirée visuellement, aucun état à reconstruire après l'erreur.

Cette mission complète la trilogie transactionnelle établie par Missions 066/067/068, chacune répondant à un profil de risque structurellement différent :
- **Mission 066** — suppression physique de fichiers : persistence-first (Domain → `save()` → suppression physique uniquement après succès), car une suppression physique est irréversible.
- **Mission 067** — mutation additive filesystem : rollback Domain + compensation best-effort des copies physiques réellement créées, car une copie physique peut être annulée sans jamais toucher un fichier préexistant.
- **Mission 068** — suppression Domain-only : rollback Domain local pur (réinsertion à l'index d'origine), sans aucune compensation filesystem puisqu'aucun fichier n'est jamais en jeu.

Changement strictement limité à `src/managers/{dataset_manager,lora_manager,model_manager,training_manager,workflow_manager}.py` et `src/ui/pages/{datasets_page,lora_page,models_page,training_page,workflows_page}.py`. `CharacterManager.delete()`/`CharactersPage.delete_character()` restent hors périmètre (suppression volontairement inaccessible dans l'UX actuelle) ; créations, renommages, modifications scalaires et associations/désassociations Domain-only restent également hors périmètre — candidats distincts, non traités ici.

### Tests ajoutés (Mission 068)

- **41 tests nets nouveaux**, répartis à l'identique sur les cinq entités : `DatasetManagerDeleteRollbackTest` (7, avec un test dédié vérifiant que la garde Training bloque toujours la suppression avant même que `save()` ne soit tenté) + `DatasetsPageDeleteConfirmationTest` (+2) dans `test_dataset_roundtrip.py` ; `LoRAManagerDeleteRollbackTest` (6) + `LoRAPageDeleteConfirmationTest` (+2) dans `test_lora_roundtrip.py` ; `ModelManagerDeleteRollbackTest` (6) + `ModelsPageDeleteConfirmationTest` (+2) dans `test_model_roundtrip.py` ; `TrainingManagerDeleteRollbackTest` (6, avec vérification explicite que `dataset_id` reste intact après rollback) + `TrainingPageDeleteConfirmationTest` (+2) dans `test_training_roundtrip.py` ; `WorkflowManagerDeleteRollbackTest` (6) + `WorkflowsPageDeleteConfirmationTest` (+2) dans `test_workflow_roundtrip.py`. Chaque suite Manager couvre : succès normal ; échec `save()` restaurant l'objet à son index exact (identité vérifiée par `assertIs`) sans publier d'événement de succès ; `active_*_id` restauré ; `active_*_id` non lié jamais touché ; `project.json` inchangé octet pour octet après échec ; retry réellement neuf après un premier échec.
- **1162/1162 tests verts au total** (1121 précédents + 41 nets nouveaux) : 289/289 sur les cinq fichiers de tests concernés, y compris l'intégralité des suites de non-régression Mission 062 (confirmation avant suppression) et Mission 063 (bouton synchronisé avec la sélection) déjà existantes. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`ModelsPage`/`TrainingPage`/`WorkflowsPage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 24/24 assertions** sur cinq scénarios : Dataset (échec de persistence injecté → erreur affichée, dataset toujours présent avec la même instance, `active_dataset_id` restauré, `project.json` inchangé ; garde Training vérifiée toujours active sur ce même dataset ; retry réel réussi après retrait de la Training bloquante), LoRA/Model/Workflow/Training (même principe).

### État du projet (Mission 068)

1162/1162 tests automatisés verts. Commit fonctionnel `969d70c4c0133e95045b0bfeda8822dbc148e3f1` (`feat: rollback Domain-only deletions on persistence failure`), tag `v0.2-mission068`, GitHub Release publiée. Voir `docs/missions/MISSION_068.md` pour le détail complet.

---

## v0.2-mission067 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 067 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 067)

Le mini-audit transactionnel mené avant Mission 066 avait identifié un second défaut, structurellement distinct de celui résolu par cette mission : les mutations **additives** (`WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`) copiaient physiquement un fichier puis mutaient le Domain **avant** `save()`, sans aucun rollback en cas d'échec de persistence. Conséquences démontrées : copie physique orpheline, mutation Domain silencieusement persistable par un `save()` ultérieur sans rapport, et pour `InferencePage._on_accept_clicked()` (dont l'image pending est déjà interne au Workspace, sous `outputs/`) un cas aggravé — un second clic sur « Accepter » après un échec obtenait silencieusement `added=0` sans jamais retenter la persistence, et un « Rejeter » après un « Accepter » échoué pouvait supprimer physiquement le fichier pending tout en laissant une référence Domain fantôme, persistable plus tard sans le moindre avertissement.

Mission 067 complète le contrat transactionnel introduit par Mission 066 pour ce cas structurellement différent : `filesystem → Domain → persistence`. Pour chaque nouvelle entrée, une comparaison entre le chemin effectif résolu et la source résolue détermine si une vraie copie physique a été créée ou s'il s'agit d'un passthrough (source déjà interne au Workspace, retournée telle quelle) — cette même comparaison protège la compensation de ne jamais supprimer un fichier préexistant. En cas d'échec de `save()`, le Domain est restauré à son état antérieur exact (mêmes objets, même ordre) et chaque copie réellement créée par cet appel est supprimée en best-effort, jamais un passthrough ; l'exception de persistence d'origine reste la cause première même si le nettoyage échoue à son tour (mirroir exact du précédent déjà établi par `WorkspaceManager.rename()`, Mission 027). Rollback implémenté localement et indépendamment dans chacun des trois Managers, sans framework transactionnel partagé (mirroir du principe déjà établi par Mission 063).

Les 5 handlers Presentation concernés (`ImagesPage.import_images()`, `DatasetsPage.import_images()`/`add_images_from_gallery()`, `LoRAPage.choose_thumbnail()`) interceptent désormais `WorkspaceManagerError` et affichent `QMessageBox.critical()` — l'action n'est jamais présentée comme réussie. Cas prioritaire `InferencePage._on_accept_clicked()` : un Accept échoué n'appelle plus `_clear_pending()` ni ne réactive `generate_button`/les contrôles de référence — la page reste exactement dans l'état pré-Accept (image toujours visible, Accepter/Rejeter/Régénérer toujours disponibles). Grâce au rollback du Manager, un second « Accepter » retente réellement la persistence (l'entrée n'existe plus en mémoire, corrigeant le faux `added=0` silencieux précédent), et un « Rejeter » après un « Accepter » échoué ne laisse plus aucune référence fantôme — vérifié y compris après un `save()` ultérieur sans rapport, le critère essentiel de cette mission.

Changement strictement limité à `src/managers/{workspace_manager,dataset_manager,lora_manager}.py` et `src/ui/pages/{images_page,datasets_page,lora_page,inference_page}.py`. Explicitement hors périmètre, non modifié : les ~30 handlers Type 1 sans opération filesystem, `WorkspaceManager.remove_images()` (déjà traité par Mission 066), A-4 (libellés de liste obsolètes après renommage), et la politique préexistante laissant l'ancienne miniature LoRA physique sur disque après un remplacement **réussi** — dette distincte, non traitée ici.

### Tests ajoutés (Mission 067)

- **20 tests nets nouveaux** : `WorkspaceManagerAddImagesCopyTest` (5) — échec `save()` + vraie copie (rollback + copie supprimée) ; échec `save()` + passthrough (jamais supprimé, reproduisant le cas `InferencePage`) ; retry après échec (tentative réellement neuve, aucun suffixe parasite) ; échec de compensation (erreur d'origine préservée, information orpheline jointe) ; lot multi-fichiers (préexistants jamais touchés, identité d'objet préservée). `DatasetManagerAddImagesCopyTest` (4) + `DatasetsPageImportPersistenceFailureTest` (2, nouvelle classe) — mêmes garanties côté Dataset, passthrough via image déjà présente dans la galerie Workspace, Presentation n'important jamais l'image en cas d'échec. `LoRAManagerMetadataTest` (3) + 1 test Presentation — restauration de `old_thumbnail`, passthrough jamais supprimé, échec de compensation, `choose_thumbnail()` affichant l'erreur avec l'ancienne miniature conservée. `ImagesPageImportPersistenceFailureTest` (2, nouvelle classe) — erreur affichée sans rien importer, retry réellement fonctionnel. `InferencePageTest` (3) — Accept échoué conserve l'état pending exact (contrôles cohérents, image toujours présente, aucune entrée Domain) ; retry Accept persiste réellement ; Rejeter après Accept échoué ne laisse aucune référence fantôme, vérifié y compris après un `save()` ultérieur sans rapport.
- **1121/1121 tests verts au total** (1101 précédents + 20 nets nouveaux) : 294/294 sur `test_workspace_roundtrip.py` + `test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_images_page.py`, 81/81 sur `test_inference_page.py`. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage`/`DatasetsPage`/`LoRAPage`/`InferencePage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 29/29 assertions** sur quatre scénarios : import Images (échec de persistence injecté, rollback, aucune copie orpheline, source intacte, retry réel réussi), import Dataset (même principe), miniature LoRA (ancienne miniature restaurée et toujours présente, nouvelle copie compensée, retry réel réussi), Inference Accept (échec injecté → message affiché, image toujours pending, absente de `workspace.images`, fichier toujours présent → second Accept avec persistence fonctionnelle → succès réel ; puis, dans un second scénario, Accept échoué → Rejeter → fichier supprimé, aucune entrée Domain, et aucune référence fantôme dans `project.json` après un `save()` ultérieur sans rapport).

### État du projet (Mission 067)

1121/1121 tests automatisés verts. Commit fonctionnel `9105c9214de478b30368c0d4bdcff167f6690432` (`feat: rollback additive filesystem mutations on persistence failure`), tag `v0.2-mission067`, GitHub Release publiée. Voir `docs/missions/MISSION_067.md` pour le détail complet.

---

## v0.2-mission066 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 066 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 066)

Un mini-audit transactionnel dédié, mené après Mission 065, a reproduit empiriquement un scénario de perte de données réelle dans `WorkspaceManager.remove_images()` : l'ordre précédent (`Path.unlink()` physique → mutation `Workspace.images` → `save()`) pouvait détruire définitivement un fichier alors qu'un échec du `save()` qui suit laissait `project.json` continuer à le référencer — confirmé y compris après fermeture/réouverture du projet. Un échec d'`unlink()` au milieu d'un lot levait par ailleurs un `PermissionError` brut, jamais converti en `WorkspaceManagerError`, avec le Domain déjà désynchronisé du filesystem avant même toute tentative de `save()`.

Mission 066 réordonne `remove_images()` en **persistence-first** : détermination des images à retirer → mutation du Domain → `save()` → suppressions physiques uniquement après succès de la persistence. Si `save()` échoue, `Workspace.images` est restauré verbatim (mêmes objets, même ordre) et l'exception `WorkspaceManagerError` remonte — aucun fichier n'est jamais touché, un rollback local simple et sûr sans snapshot du Workspace entier. Si `save()` réussit, la suppression logique est déjà durable ; chaque suppression physique est ensuite tentée indépendamment (un échec n'interrompt jamais le traitement des fichiers suivants), les échecs étant collectés dans un nouveau champ `RemovalResult.deletion_failed` plutôt que rollbackés — la politique de risque retenue devient : fichier orphelin récupérable plutôt qu'un fichier détruit encore référencé par le projet. `ImagesPage.delete_selected_images()` distingue désormais un échec de persistence (`QMessageBox.critical`, rien n'a été supprimé) d'un échec filesystem après persistence réussie (`QMessageBox.warning`, la suppression est déjà persistée) — aucune nouvelle logique de rafraîchissement n'a été nécessaire, le câblage `WORKSPACE_SAVED` déjà existant suffisant à refléter l'état persisté.

Changement strictement limité à `src/managers/workspace_manager.py` (`remove_images()`/`RemovalResult`) et `src/ui/pages/images_page.py`. Aucune modification de `WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`, `InferencePage`, ou de tout autre Manager — ces mutations additives filesystem partagent un problème transactionnel distinct, explicitement laissé ouvert pour un futur audit dédié.

### Tests ajoutés (Mission 066)

- **5 tests nets nouveaux** : 3 dans `WorkspaceManagerRemoveImagesTest` (`test_remove_images_when_save_fails_deletes_no_file_and_restores_domain` — le test de sécurité principal, `save()` en échec, aucun `unlink()` exécuté, fichiers intacts, `project.json` inchangé, Domain restauré exactement ; `test_remove_images_batch_survives_one_unlink_failure_and_reports_it` — lot A/B/C, l'échec de B n'empêche pas la suppression de C ; `test_remove_images_collects_every_unlink_failure_not_only_the_first` — plusieurs échecs tous collectés) et 2 dans `ImagesPageTest` (persistence échouée → `QMessageBox.critical`, aucun fichier détruit ; échec filesystem post-`save()` → `QMessageBox.warning`, suppression déjà persistée, galerie cohérente).
- **1101/1101 tests verts au total** (1096 précédents + 5 nets nouveaux) : 17/17 sur `WorkspaceManagerRemoveImagesTest`, 92/92 sur `test_workspace_roundtrip.py`, 49/49 sur `test_images_page.py`, 132/132 de non-régression croisée (`test_datasets_page.py`/`test_inference_page.py`/`test_thumbnails.py`). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage`/`WorkspaceManager` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 18/18 assertions** sur trois scénarios : suppression normale (fichier détruit, projet mis à jour), échec de persistence injecté (aucun fichier détruit, Domain/`project.json` restaurés, message d'erreur), échec filesystem intermédiaire après persistence réussie sur un lot de trois (deux fichiers supprimés, un orphelin conservé, avertissement affiché, galerie cohérente avec l'état persisté).

### État du projet (Mission 066)

1101/1101 tests automatisés verts. Commit fonctionnel `c06fe82569cef35ea29fc7c5ce47da6a7f921f33` (`feat: make WorkspaceManager.remove_images() persistence-first`), tag `v0.2-mission066`, GitHub Release publiée. Voir `docs/missions/MISSION_066.md` pour le détail complet.

**Candidat futur explicitement conservé** : les mutations filesystem additives (`WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`) et le scénario `InferencePage.accept()` qui en dépend partagent un problème transactionnel distinct de celui résolu ici — démontré par le même mini-audit, non traité par Mission 066, à réévaluer par un futur audit dédié plutôt qu'automatiquement promu.

---

## v0.2-mission065 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 065 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 065)

L'audit consécutif à Mission 064 avait laissé en suspens le candidat B2, identifié dès l'audit post-Mission 063 : pendant une génération de `PromptAssistantDialog` (Mission 031), le bouton Annuler est désactivé, mais `Escape` et la fermeture native de la fenêtre contournaient ce garde-fou (`QDialog.reject()` n'était jamais surchargé), abandonnant le worker/`QThread` en arrière-plan et pouvant faire apparaître un `QMessageBox.critical()` tardif sur un dialogue que l'utilisateur croyait déjà fermé. L'architecte a tranché l'arbitrage produit resté ouvert : **Option A — interdire la fermeture pendant une génération**, plutôt que l'alternative (fermeture autorisée avec annulation/discard propre du résultat).

Une vérification empirique préalable (script de sonde exécuté dans le scratchpad, sans modification) a établi que `dialog.close()` déclenche à la fois `closeEvent()` et `reject()`, tandis que `Escape` appelle `reject()` directement sans passer par `closeEvent()` — `reject()` est donc l'unique point de passage commun à `Escape`, à la fermeture native et au bouton Annuler (`cancel_button.clicked.connect(self.reject)`). Mission 065 surcharge uniquement `reject()` dans `src/ui/dialogs/prompt_assistant_dialog.py` : si `cancel_button.isEnabled()` est faux (état busy déjà piloté par `_set_controls_enabled()` depuis Mission 031), la tentative de fermeture est silencieusement ignorée, sans nouvelle popup ; sinon `super().reject()` s'exécute normalement. Aucun nouvel état n'est introduit — `cancel_button.isEnabled()` est réutilisé tel quel comme source de vérité busy/idle, délibérément préféré à `self._thread is not None` (dont la remise à `None` par `_cleanup_thread()` est asynchrone et retardée, ce qui aurait ouvert une fenêtre où le bouton semble réactivé alors que la fermeture resterait bloquée). Aucun mécanisme d'annulation du worker/`QThread` n'a été introduit : le cycle continue à s'exécuter normalement jusqu'à son terme (succès ou échec), après quoi la fermeture normale est restaurée.

Changement strictement limité à `src/ui/dialogs/prompt_assistant_dialog.py` (une seule méthode ajoutée, +15 lignes). Aucun changement `InferencePage`, `PromptsPage`, Domain/Manager/Infrastructure/EventBus, ou tout autre dialogue.

### Tests ajoutés (Mission 065)

- Nouvelle classe `PromptAssistantDialogCloseGuardTest` (5 tests, sans `QThread` réel — `cancel_button.setEnabled(False)` simule directement l'état busy, avec de vrais événements Qt pour Escape/fermeture) : Escape/fermeture ferment normalement à l'état idle, sont tous deux ignorés à l'état busy, fermeture de nouveau possible une fois l'état busy terminé.
- 2 tests ajoutés à la classe préexistante `PromptAssistantDialogGenerateTest` (cycle `QThread` réel réutilisé, pas une nouvelle classe threadée) : Escape et fermeture native tentés pendant une génération réelle restent sans effet, le worker termine normalement, le résultat atterrit correctement, et la fermeture redevient possible ensuite — vérifié à la fois sur le chemin de succès et sur le chemin d'échec (`QMessageBox.critical` mocké).
- **7 tests nets nouveaux**. Comportement observable testé (`isVisible()` via de vrais `dialog.show()`/`QTest.keyClick`/`dialog.close()`), jamais l'existence de l'override ou d'un booléen interne.
- **7/7 tests ciblés PASS. 38/38 sur la suite complète du fichier du dialogue. 159/159 en non-régression** (`test_inference_page.py` + `test_prompt_roundtrip.py`).
- **Suite complète : 3 exécutions consécutives `unittest discover` propres à 1096/1096** (1089 précédents + 7 nets nouveaux), aucun échec imputable à Mission 065 dans aucune des trois exécutions.
- Smoke test Qt réel, exécuté par Claude, dialogue et `QThread`/`PromptAssistantWorker` réels contre un écran non mocké — **PASS, 14/14 assertions** : idle (Escape/fermeture ferment normalement), busy (les deux tentatives sont ignorées, bouton Annuler désactivé), fin de génération réussie (fermeture de nouveau possible, résultat correct), et chemin d'échec (`QMessageBox.critical` réellement déclenché, fermeture de nouveau possible après l'erreur).

### État du projet (Mission 065)

1096/1096 tests automatisés verts sur 3 exécutions consécutives. Commit fonctionnel `17c44dceeecf0d277038edc0bea2118a740dd7ba` (`feat: block PromptAssistantDialog close while a generation is running`), tag `v0.2-mission065`, GitHub Release publiée. Voir `docs/missions/MISSION_065.md` pour le détail complet.

**Segfault Qt/PySide6** : l'aléa natif déjà documenté après Mission 063/064 **ne s'est pas manifesté pendant les 3 exécutions complètes de validation de Mission 065**. Cette absence d'observation est une **observation de stabilité sur ces 3 runs, pas une preuve de correction** : la cause racine reste non isolée, aucune modification visant ce sujet n'a été apportée dans Mission 065, et l'hypothèse simple « tests terminés avant la fin du cleanup du `QThread` » reste **expérimentalement réfutée** (deux expériences dédiées après Mission 064, toutes deux sans effet sur le crash à l'époque — voir `docs/missions/MISSION_064.md`).

---

## v0.2-mission064 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 064 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 064)

L'audit consécutif à Mission 063 a confirmé que `load_thumbnail_icon()` (`src/ui/thumbnails.py`) décodait intégralement chaque image en pleine résolution puis la redimensionnait, de façon synchrone sur le thread UI, **sans aucun cache** — à chaque appel, quel qu'en soit le déclencheur. Un mini-audit technique ciblé a établi que le déclencheur dominant n'est pas seulement le tri explicite mais `WORKSPACE_SAVED` : `ImagesPage.update_images()` et `DatasetsPage.update_datasets()` y sont tous deux abonnés, un événement publié après quasiment toute mutation de l'application — chaque déclenchement reconstruit intégralement la liste et redécode toutes les vignettes affichées, y compris celles totalement inchangées.

Mission 064 introduit un cache LRU partagé et borné, strictement localisé à `src/ui/thumbnails.py`, sans toucher à l'API publique `load_thumbnail_icon(file_path, size, style)` ni aux trois consommateurs (`ImagesPage`, `DatasetsPage`, `SelectImagesDialog`). La fonction publique lit d'abord `Path(file_path).stat()` — avant toute possibilité d'accès au cache, pour qu'un fichier absent/modifié/remplacé ne puisse jamais être satisfait par une entrée obsolète — puis délègue à une fonction interne `_decode_and_scale(file_path, mtime_ns, file_size, width, height)` décorée `functools.lru_cache(maxsize=256)`. Le décodage `QPixmap()` pleine résolution n'a lieu que lors d'un cache miss ; seul le `QIcon` construit à partir du résultat déjà redimensionné est retourné/conservé — le pixmap pleine résolution reste local et sort de portée aussitôt après. Un fichier modifié ou remplacé au même chemin change sa signature (`mtime_ns`/`file_size`), provoquant un nouveau décodage automatique ; un fichier supprimé échoue au `stat()` préalable et retombe directement sur l'icône de fallback, sans jamais interroger le cache.

Aucune normalisation de chemin supplémentaire n'a été ajoutée : les chemins de ce flux sont déjà construits de façon canonique par `WorkspaceStorage.copy_into_workspace()`, sans preuve concrète justifiant d'y déroger. La borne `maxsize=256` (≈16 Mo pour des vignettes 128×128 RGBA) est un choix d'ingénierie proportionné, pas un arbitrage produit.

### Tests ajoutés (Mission 064)

- Nouveau fichier `tests/integration/test_thumbnails.py`, classe `ThumbnailCacheTest` (**9 tests nets nouveaux**) : premier appel/cache miss, appel suivant sur fichier inchangé/cache hit, fichier modifié (réécriture réelle du contenu, pas un simple `os.utime()`) ou remplacé au même chemin/nouveau miss, dimensions différentes/entrées distinctes, fichier inexistant/fallback sans jamais toucher le cache, fichier supprimé après un chargement réussi/fallback sans réutiliser l'ancienne vignette, borne du cache conforme à la constante documentée. Comptage fiable des décodages via `_decode_and_scale.cache_info()` (`hits`/`misses`, mécanisme stdlib, aucune dépendance à un détail Qt fragile) ; `cache_clear()` systématique pour l'isolation entre tests (cache process-wide).
- Non-régression des trois consommateurs couverte par les suites existantes : **99/99 PASS** (`test_images_page.py` + `test_datasets_page.py` + `test_select_images_dialog.py`), aucun test supplémentaire redondant ajouté.
- **1089/1089 tests verts au total, démontrés par décomposition** (1080 précédents + 9 nets nouveaux) : l'aléa d'environnement natif Qt/PySide6 déjà documenté après Mission 063 est devenu **reproductible à 5/5 exécutions complètes `unittest discover`** pendant cette mission, systématiquement localisé dans `PromptAssistantDialogGenerateTest` (`tests/integration/test_prompt_assistant_dialog.py`, un test préexistant utilisant un vrai `QThread`, sans rapport avec ce diff). Non attribué à Mission 064 : la suite complète à l'exclusion des deux seuls modules `QThread` réels (`test_prompt_assistant_dialog.py`, `test_inference_page.py`) tourne à **980/980**, ces deux modules exécutés ensemble isolément à **109/109** — soit 980+109 = 1089, le total exact attendu.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage` et `SelectImagesDialog` réels contre un Workspace réel sur l'écran non mocké de l'environnement de développement — **PASS** : aucun redécodage sur reconstruction déclenchée par une mutation sans rapport avec les images (`workspace_manager.save()`), exactement un nouveau décodage pour un fichier réellement modifié, partage de cache démontré entre `ImagesPage` et `SelectImagesDialog` (mêmes chemins internes exacts, sans copie).

### État du projet (Mission 064)

1089/1089 tests automatisés verts (démontrés par décomposition, voir ci-dessus). Commit fonctionnel `90689d0beb0e126700872310813e9e18e2c26edd` (`feat: add a bounded, mtime/size-keyed thumbnail cache`), tag `v0.2-mission064`, GitHub Release publiée. Voir `docs/missions/MISSION_064.md` pour le détail complet. L'aléa Qt/PySide6, désormais reproductible à 5/5, est élevé au rang de priorité d'investigation pour Mission 065.

---

## v0.2-mission063 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 063 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 063)

L'audit consécutif à Mission 062 a identifié que 6 des 7 pages CRUD du projet — `Dataset`, `LoRA`, `Model`, `Training`, `Workflow`, `Prompts` — laissaient leur bouton « Supprimer » **toujours activé**, indépendamment de toute sélection réelle dans la liste, contrairement à `ImagesPage.delete_button` (Mission 046), seule page correcte. Chaque `delete_<entité>()` de Page garde bien `if item is None: return`, donc aucun crash n'était possible — mais un clic sur « Supprimer » sans sélection produisait un **no-op silencieux, sans aucun retour visuel**, en particulier sur une liste vide ou juste après un changement de Workspace/Character. `Character` reste hors périmètre : `CharactersPage.delete_button` est volontairement caché depuis Mission 026, inaccessible depuis l'application réelle.

Mission 063 étend à chacune des 6 pages le motif déjà établi par `ImagesPage` : `delete_button.setEnabled(False)` à la construction, état recalculé au tout début du handler de sélection (`on_<entité>_selection_changed`) et à la fin de chaque reconstruction de liste (`update_<entité>s()`), puisque `blockSignals(True)` pendant une reconstruction supprime le signal `currentItemChanged` que le handler écoute normalement. `PromptsPage` diffère des 5 autres pages : sa sélection peut être annulée et revenir en arrière par la garde de brouillon non enregistré de Mission 038 (`on_prompt_selection_changed` → `_confirm_discard_before_switch()` → Annuler → `setCurrentItem(previous)`) — le bouton suit alors la sélection **réellement en vigueur après ce retour en arrière**, pas la tentative de bascule annulée. Pour `Dataset`, la garde préexistante `is_referenced_by_training()` (Mission 062) n'est **pas** répercutée sur l'état du bouton : un Dataset sélectionné, même référencé par un Training, active « Supprimer » selon la règle générale ; la garde continue d'intervenir uniquement au clic, dans `delete_dataset()`, strictement inchangée. Aucune abstraction partagée introduite — 6 adaptations locales indépendantes.

Changement strictement limité aux 6 fichiers `src/ui/pages/{datasets,lora,models,training,workflows,prompts}_page.py`. Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : `Character`, mécanisme de confirmation de Mission 062 (wording/comportement strictement inchangés), toute désactivation dynamique de « Supprimer » selon `is_referenced_by_training()` (évolution UX distincte, non traitée ici), candidats A-2 (cache des vignettes) et B2 (fermeture de `PromptAssistantDialog` pendant une génération), tous deux réservés à une future mission.

### Tests ajoutés (Mission 063)

- Pour chacune des 6 pages, une nouvelle classe `*PageDeleteButtonStateTest` dans le fichier `test_<entité>_roundtrip.py` existant, couvrant a minima : désactivé avant tout Workspace ; désactivé sans sélection puis activé après sélection réelle ; désactivé après désélection réelle ; état cohérent après reconstruction de liste ; désactivé après fermeture du Workspace ; désactivé après suppression de l'élément sélectionné.
- Pour Dataset spécifiquement, un test additionnel `test_selecting_a_dataset_referenced_by_training_still_enables_button` — preuve explicite que la garde Training n'intervient pas sur l'état du bouton.
- Pour Prompts spécifiquement, deux tests additionnels couvrant la bascule annulée par la garde dirty-state de Mission 038, avec et sans sélection préalable.
- **39 tests nets nouveaux** au total (6+7+6+6+6+8). **1080/1080 tests verts au total** (1041 précédents + 39 nets nouveaux) — un run complet propre confirmé ; un aléa d'environnement natif Qt/PySide6 (segfault intermittent) a été observé sur plusieurs runs complets, reproduit indépendamment de ce diff sur le baseline (`git stash`), jamais reproduit dans les runs ciblés/groupés des modules modifiés — voir `docs/missions/MISSION_063.md` section 9.
- Smoke test Qt réel, exécuté par Claude, les 6 pages construites contre un Workspace réel sur l'écran non mocké de l'environnement de développement — **PASS** : désactivé/activé/désactivé conformes à la sélection réelle, cohérence après reconstruction de liste, et cycle de confirmation Mission 062 intact rejoué de bout en bout (vrai `QMessageBox`, suppression réelle, bouton redevient désactivé) sur les 5 pages concernées.

### État du projet (Mission 063)

1080/1080 tests automatisés verts. Commit fonctionnel `538c943b7eb9f35e84634fce6e13785fcfbda365` (`feat: disable Supprimer when no CRUD entity is selected`), tag `v0.2-mission063`, GitHub Release publiée. Voir `docs/missions/MISSION_063.md` pour le détail complet.

---

## v0.2-mission062 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 062 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 062)

L'audit consécutif à Mission 061 (deux passes exploratoires successives, la seconde corrigée après réexamen de l'architecte) a identifié que 5 des 6 entités du projet — `Dataset`, `LoRA`, `Model`, `Training`, `Workflow` — exposaient une méthode `delete_<entité>()` de Page appelant directement le Manager sans aucune confirmation utilisateur : un simple clic sur « Supprimer » suffisait à effacer irréversiblement l'enregistrement, contrairement à `ImagesPage.delete_selected_images()` (Mission 046) et `PromptsPage.delete_prompt()` (Mission 038), qui confirment déjà.

La 6ᵉ entité initialement suspectée, `Character`, a été explicitement exclue après audit approfondi : `CharactersPage.delete_button` est volontairement caché (`setVisible(False)`) depuis Mission 026 (orientation produit « 1 Workspace = 1 personnage principal »), verrouillé par un test de régression dédié (`test_character_roundtrip.py`, `isHidden()`) — `CharactersPage.delete_character()` est donc inaccessible depuis l'application réelle. `CharacterManager.delete()` reste légitime et nécessaire, appelé par de nombreux tests de régression validant le pattern Character-owned (cascade `Dataset`/`LoRA`/`Prompt`/`Training`) — ajouter une confirmation sur un chemin UI inaccessible n'aurait protégé personne.

Mission 062 ajoute à chacune des 5 pages restantes un `QMessageBox` de confirmation avant suppression, reprenant exactement le motif déjà établi par `ImagesPage`/`PromptsPage` (`addButton`/`AcceptRole`/`RejectRole`, `setDefaultButton(cancel_button)`, `Annuler` par défaut) : Annuler (y compris fermeture via la croix ou Échap) n'appelle jamais le Manager et ne mute aucun état ; Supprimer exécute exactement l'appel au Manager déjà existant, sans autre changement de comportement. Pour `Dataset`, la garde préexistante `is_referenced_by_training()` reste la **première** vérification, avant toute construction de `QMessageBox` — un Dataset dont la suppression est refusée par cette garde n'affiche jamais de confirmation trompeuse. Aucune abstraction/helper partagé introduit — 5 adaptations locales indépendantes.

Changement strictement limité aux 5 fichiers `src/ui/pages/{datasets,lora,models,training,workflows}_page.py`. Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : `Character` (voir ci-dessus), cache des vignettes (candidat A-2 identifié pendant le même audit, réservé à une future mission).

### Tests ajoutés (Mission 062)

- Pour chacune des 5 entités, une nouvelle classe `*PageDeleteConfirmationTest` dans le fichier `test_<entité>_roundtrip.py` existant : `test_delete_with_no_selection_is_a_no_op`, `test_delete_confirmed_removes_<entité>`, `test_delete_cancelled_calls_neither_manager_nor_mutates_state` (mockage `QMessageBox` au niveau classe, technique déjà éprouvée par `test_images_page.py`, `patch.object(manager, "delete")` prouvant l'absence d'appel).
- Pour Dataset spécifiquement, une 4ᵉ méthode `test_delete_blocked_by_training_reference_never_shows_confirmation` : garde Training toujours active, `QMessageBox.warning()` appelé, `QMessageBox().exec()` jamais appelé, dataset toujours présent.
- **16 tests nets nouveaux** au total. **1041/1041 tests verts au total** (1025 précédents + 16 nets nouveaux), 16/16 de tests ciblés.
- Smoke test Qt réel, exécuté par Claude, les 5 pages construites contre un Workspace réel sur l'écran non mocké de l'environnement de développement — **PASS** : dialogue construit avec le bon titre/texte/boutons (`["Annuler", "Supprimer"]`), `defaultButton()` confirmé « Annuler », Annuler → entité conservée et sélection inchangée, Confirmer → entité effectivement supprimée ; cas Dataset référencé par un Training : `QMessageBox.exec()` jamais appelé (0 mesuré), seule la garde préexistante s'est déclenchée.

### État du projet (Mission 062)

1041/1041 tests automatisés verts. Commit fonctionnel `a630b4f6884b6bf204fdeb42cb7a94f39a639a4b` (`feat: confirm before deleting Dataset, LoRA, Model, Training and Workflow`), tag `v0.2-mission062`, GitHub Release publiée. Voir `docs/missions/MISSION_062.md` pour le détail complet.

---

## v0.2-mission061 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 061 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 061)

L'audit consécutif à Mission 060 a cherché à vérifier si la même classe de dette UX (taille initiale fixée en dur, jamais bornée à l'écran réellement disponible) existait ailleurs dans le code. Recherche exhaustive des 6 sous-classes `QDialog` du projet : exactement deux appellent `.resize()` avec des valeurs fixes — `ImagePreviewDialog` (`self.resize(1000, 750)`) et `PromptAssistantDialog` (`self.resize(800, 700)`) ; les quatre autres (`ImportCollisionDialog`, `NewProjectDialog`, `SelectImagesDialog`, `RenameProjectDialog`) se dimensionnent déjà de façon adaptative via le `sizeHint()` agrégé de leur contenu et n'étaient pas concernées.

Mission 061 applique aux deux dialogues exactement le même calcul que Mission 060 : `self.screen()` borné à `screen().availableGeometry()`, repli sur `QApplication.primaryScreen()` si `None`, repli final sur la taille historique de chacun (`1000×750`/`800×700`) si aucun écran n'est disponible du tout. La taille par défaut préférée reste conservée à l'identique dès que l'écran dispose de la place nécessaire ; elle n'est réduite que sur un écran dont l'espace disponible est effectivement inférieur. Les deux dialogues restent librement redimensionnables ensuite, exactement comme avant cette mission.

Changement strictement limité à deux points de code (`src/ui/dialogs/image_preview_dialog.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, import `QApplication` ajouté dans chacun). Aucune abstraction/helper partagé introduit — deux adaptations locales indépendantes. Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : persistance/restauration de géométrie entre sessions, centrage explicite, gestion multi-écrans avancée, tout autre dialogue du projet.

### Tests ajoutés (Mission 061)

- `tests/integration/test_image_preview_dialog.py` : nouvelle classe `ImagePreviewDialogInitialSizeTest` (5 tests) — écran disponible plus petit (borné à `availableGeometry()`, prouvé distinct de `geometry()`) ; écran disponible plus grand (`1000×750` conservé) ; repli `QApplication.primaryScreen()` ; repli historique sans écran, sans exception ; redimensionnement manuel toujours accepté après construction.
- `tests/integration/test_prompt_assistant_dialog.py` : le test préexistant `test_initial_size_is_at_least_800_by_700`, qui imposait un plancher **inconditionnel** contredisant directement le nouveau contrat, est **remplacé** (non étendu) par la nouvelle classe `PromptAssistantDialogInitialSizeTest`, 5 tests strictement symétriques, adaptés à `800×700`.
- **1025/1025 tests verts au total** (1016 précédents + 9 nets nouveaux : 5+5 ajoutés, 1 remplacé), 49/49 de tests ciblés, 248/248 de non-régression.
- Smoke test Qt réel, exécuté par Claude, les deux dialogues construits sur l'écran non mocké de l'environnement de développement — **PASS** : `ImagePreviewDialog` `QSize(1000, 750)`, `PromptAssistantDialog` `QSize(800, 700)`, tous deux dans les bornes de `availableGeometry() = QRect(0, 0, 1920, 1040)`, redimensionnement manuel confirmé pour chacun.

### État du projet (Mission 061)

1025/1025 tests automatisés verts. Commit fonctionnel `e2466292fd25d457eb2261414646597686c5240d` (`feat: bound ImagePreviewDialog and PromptAssistantDialog to available screen geometry`), tag `v0.2-mission061`, GitHub Release publiée. Voir `docs/missions/MISSION_061.md` pour le détail complet.

---

## v0.2-mission060 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 060 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 060)

`MainWindow.__init__()` fixait `self.resize(1700, 950)` inconditionnellement depuis le commit racine du fichier (2026-08-08), sans aucune prise en compte de l'espace d'écran réellement disponible — dette UX signalée pendant le smoke test réel de Mission 059, alors documentée séparément faute d'entrer dans le périmètre validé de cette mission-là.

Mission 060 remplace ce `resize()` fixe par un calcul borné à `screen().availableGeometry()` — la zone réellement utilisable de l'écran, à l'exclusion de la barre des tâches et des autres zones réservées, mesurée dans cet environnement à `1920×1040` contre `1920×1080` pour `geometry()` (40px de différence, une barre des tâches réelle). `self.screen()` se replie sur `QApplication.primaryScreen()` s'il retourne `None`, puis sur le défaut historique `1700×950` si aucun écran n'est disponible du tout — la construction de `MainWindow` ne peut jamais échouer pour cette raison. La taille par défaut préférée `1700×950` reste conservée à l'identique dès que l'écran dispose de la place nécessaire (le cas courant, confirmé par le smoke test réel de cet environnement) ; elle n'est réduite que sur un écran dont l'espace disponible est effectivement inférieur. La fenêtre reste librement redimensionnable ensuite, exactement comme avant cette mission.

Changement strictement limité à un seul point de code dans `src/ui/main_window.py` (import `QApplication` ajouté). Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : persistance/restauration de géométrie entre sessions, centrage explicite, gestion multi-écrans avancée, modification des tailles minimales (`MainWindow.minimumSizeHint()` reste `865×769`, mesuré par Mission 059).

### Tests ajoutés (Mission 060)

- Nouveau fichier `tests/integration/test_main_window_initial_size.py` (`MainWindowInitialSizeTest`, 5 tests) : écran disponible plus petit que `1700×950` (borné à `availableGeometry()`, prouvé distinct de `geometry()` par des valeurs volontairement différentes dans chaque mock) ; écran disponible plus grand (taille historique `1700×950` conservée) ; repli sur `QApplication.primaryScreen()` quand `self.screen()` retourne `None` ; repli final sur `1700×950` quand aucun écran n'est disponible, sans exception ; redimensionnement manuel toujours accepté après construction.
- **1016/1016 tests verts au total** (1011 précédents + 5 nets nouveaux), 75/75 de non-régression ciblée.
- Smoke test Qt réel, exécuté par Claude (pas seulement décrit), `MainWindow` réelle construite sur l'écran non mocké de l'environnement de développement — **PASS** : `screen.geometry() = QRect(0, 0, 1920, 1080)`, `screen.availableGeometry() = QRect(0, 0, 1920, 1040)` (mesurés, jamais supposés), taille initiale obtenue `QSize(1700, 950)` dans les bornes, redimensionnement manuel (`resize(800, 600)`) confirmé après construction.

### État du projet (Mission 060)

1016/1016 tests automatisés verts. Commit fonctionnel `bee1ec46db9a54b08f7e165fa4aba66bfe00b8e5` (`feat: bound initial window size to available screen geometry`), tag `v0.2-mission060`, GitHub Release publiée. Voir `docs/missions/MISSION_060.md` pour le détail complet.

---

## v0.2-mission059 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 059 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 059)

`LoRAManager`/`LoRAPage` géraient déjà intégralement la fiche technique d'une LoRA côté Workspace (fichiers, miniature, `engine`/`architecture`/`trigger_word`/`version`) depuis Mission 047/050, mais aucune LoRA n'était jamais appliquée lors d'une génération, quel que soit le moteur. Mission 059 livre la première application réelle d'une LoRA pendant une génération ComfyUI.

`ComfyUIEngine.list_loras()` (nouvelle méthode) interroge `GET /object_info/LoraLoader` sur le serveur ComfyUI réellement actif — mirroir exact du mécanisme de découverte du checkpoint (Mission 025) — et échoue explicitement (`ComfyUIEngineError`) sur toute réponse inattendue, jamais de liste partielle ou devinée. `SettingsPage` gagne un `QComboBox` LoRA éditable et un bouton de rafraîchissement dédiés, ainsi qu'un contrôle de force unique (`QDoubleSpinBox`, défaut `1.0`), persistés dans `ApplicationSettings` (`comfyui_lora_name`, `comfyui_lora_strength`) — sélection Settings-level/globale, comme le checkpoint, lue une seule fois au démarrage par `MainWindow` (contrat "pas de hot reload" déjà établi).

`build_txt2img_workflow()`/`build_img2img_workflow()` (`comfyui_workflows.py`) gagnent une nouvelle fonction interne `_apply_lora()` : quand aucune LoRA n'est configurée, le graphe retourné reste structurellement identique à avant cette mission (égalité de dict Python, seed aléatoire neutralisé pour la comparaison) ; quand une LoRA est configurée, un nœud natif `LoraLoader` est inséré entre `CheckpointLoaderSimple` et tout consommateur de `model`/`clip` (`KSampler`, les deux `CLIPTextEncode`), la même force alimentant à la fois `strength_model` et `strength_clip` — `vae` reste toujours issu directement du checkpoint, `LoraLoader` ne le touchant jamais. Le mécanisme `Reference(path, pose_composition)` de Mission 056 reste totalement inchangé et cohabite sans interaction avec le nouveau nœud LoRA, confirmé aussi bien en test automatisé qu'en génération réelle.

**Compatibilité architecture (SD1.5/SDXL/FLUX)** : le pipeline actuel (`CheckpointLoaderSimple` + nœuds génériques) couvre SD1.5 et SDXL — confirmé par preuve historique réelle (le smoke test de Mission 012 avait détecté des checkpoints SDXL via ce même mécanisme). **FLUX est explicitement hors périmètre** : son workflow natif ComfyUI (`UNETLoader`/`DualCLIPLoader`/VAE séparé) est structurellement différent et n'existe nulle part dans ce dépôt — limitation pré-existante depuis Mission 012/013, non introduite par cette mission. `/object_info/LoraLoader` n'expose aucune métadonnée d'architecture par fichier ; aucune détection ou filtrage automatique n'est donc implémenté, et aucune heuristique par nom de fichier n'est introduite. Une LoRA d'une architecture incompatible avec le checkpoint actif échoue explicitement côté serveur ComfyUI — jamais de substitution silencieuse.

**Hors périmètre explicite** : aucun mapping entre une entité `LoRA` du Workspace (`LoRA.files`) et un `lora_name` ComfyUI — `LoRA.files` contient des chemins externes bruts jamais copiés dans le Workspace (à la différence de `LoRA.thumbnail`), et aucun mécanisme fiable de correspondance n'existe aujourd'hui ; ce candidat sélectionne uniquement parmi les LoRA déjà connues du serveur ComfyUI actif. Aucune sélection par génération (`InferencePage`) ni par `Character`, aucune LoRA simultanée, aucun autre moteur.

**Régression de taille de fenêtre détectée et corrigée** : pendant l'audit de compatibilité architecture de cette même mission, l'allongement du texte d'un hint `SettingsPage` (`application_hint`, dépourvu de `setWordWrap()`) a fait presque doubler sa largeur naturelle, ce qui — via l'agrégation par `QStackedWidget` du `sizeHint()` maximal de toutes ses pages, y compris non affichées — a fait exploser la taille minimale de `MainWindow` bien au-delà des résolutions d'écran courantes, visible dès le Dashboard au lancement. Cause établie avec certitude par mesure directe de `sizeHint()`/`minimumSizeHint()` avec des widgets Qt réels, y compris une comparaison A/B contrôlée entre la version `settings_page.py` committée avant cette mission et la version actuelle. Corrigée par un seul appel `application_hint.setWordWrap(True)`, sans toucher au `self.resize(1700, 950)` fixe et non adaptatif à l'écran de `MainWindow` — celui-ci est authentiquement préexistant (commit racine du fichier) et n'est pas la cause de la régression ; il reste une dette UX distincte, non résolue par cette mission.

Aucun changement Domain au-delà de deux champs additifs `ApplicationSettings` (`comfyui_lora_name`, `comfyui_lora_strength`), aucun changement EventBus, aucune nouvelle dépendance.

### Tests ajoutés (Mission 059)

- 6 fichiers de test existants étendus, aucun nouveau fichier créé : `test_comfyui_workflows.py` (+`NoLoraProducesTheExactPreMission059WorkflowTest`, +`LoraInsertedWhenConfiguredTest`), `test_comfyui_engine.py` (+`ComfyUIEngineListLorasTest`, +`ComfyUIEngineGenerateImageLoraTest`), `test_generation_manager.py` (+`GenerationManagerLoraTest`, assertions existantes étendues), `test_application_settings_roundtrip.py` (nouveau test de compatibilité legacy sans champs LoRA, littéraux existants étendus), `test_settings_page.py` (+`SettingsPageLoraDiscoveryTest`, +`SettingsPageSizeHintRegressionTest`), `test_main_window_comfyui_settings.py` (assertions existantes étendues).
- Le test "sans LoRA" prouve une égalité structurelle complète du workflow Python (comparaison de dict via `assertEqual`, seed aléatoire du graphe neutralisé par un `random.randint` patché) — pas une comparaison JSON octet par octet.
- `SettingsPageSizeHintRegressionTest` verrouille `SettingsPage.sizeHint()`/`.minimumSizeHint()` sous 900px de large, en garde contre une régression future de même nature.
- **1011/1011 tests verts au total** (967 précédents + 44 nets nouveaux : 43 fonctionnels + 1 non-régression de taille de fenêtre).
- Vérification manuelle réelle en deux temps : smoke test **mocké** (objets Qt/Manager réels — `SettingsPage`, `ApplicationSettingsManager`, `ComfyUIEngine`, `GenerationManager` — mais réseau simulé, aucun serveur ComfyUI accessible dans l'environnement de développement) **PASS** (19/19) ; puis smoke test **réel**, exécuté par l'architecte sur son installation ComfyUI réelle **PASS** — découverte de 5 LoRA réels, génération txt2img réelle avec LoRA, génération img2img réelle avec `Reference(pose_composition)` + LoRA simultanément.

### État du projet (Mission 059)

1011\1011 tests automatisés verts. Commit fonctionnel `c96b984606bbac83d6276d7dca54b9efe4307c53` (`feat: add ComfyUI LoRA selection for generation`), tag `v0.2-mission059`, GitHub Release publiée. Voir `docs/missions/MISSION_059.md` pour le détail complet.

---

## v0.2-mission058 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 058 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 058)

Un audit factuel du dépôt, réalisé après la clôture complète de Mission 057, a identifié quatre éléments frais de code mort/documentation obsolète, distincts de ceux déjà traités par Mission 057 : `EventBus.unsubscribe()` (méthode publique jamais appelée nulle part, aucun test ne l'exerçant) ; une branche structurellement inatteignable dans `TrainingPage.create_training()` (une garde identique existe déjà en tête de la même méthode, rendant la seconde impossible à atteindre — confirmé par analyse de flot de `TrainingManager.create()` et de son seul abonné `TRAINING_CREATED`, une pure UI refresh) ; un commentaire obsolète de `Workspace.from_dict()` affirmant que `Workspace.models` « n'a jamais tenu de vraie donnée », alors que `ModelManager`/`ModelsPage` le consomment activement ; deux références obsolètes à `BasePage` dans `docs/PROJECT_CONTEXT.md`, encore décrit comme présent bien que Mission 057 l'ait déjà supprimé.

Les quatre éléments sont retirés/corrigés. `EventBus.subscribe()`/`publish()`/`_freeze()` et le reste de `create_training()` restent strictement inchangés. Aucun comportement utilisateur observable ne change — confirmé par un cycle Qt réel exécuté manuellement sur les quatre scénarios de `create_training()` (aucun Workspace ouvert, Workspace sans Dataset, création réelle d'une Training, suppression du Character).

Aucun changement Domain (au-delà du seul commentaire corrigé)/Manager/Inference/Settings/portabilité des chemins.

### Tests ajoutés (Mission 058)

- **Aucun test ajouté ni retiré** — décision explicite du contrat : `EventBus.unsubscribe()` n'avait aucun test le couvrant, la branche morte de `training_page.py` était par construction non testable (inatteignable), et le seul cas réel restant (« Aucun personnage ») était déjà couvert par `test_training_roundtrip.py` avant cette mission.
- **967/967 tests verts** au total — décompte strictement identique à l'état pré-mission. Non-régression confirmée sur `test_training_roundtrip.py` (34/34).
- Vérification manuelle réelle (hors suite `unittest`) : cycle Qt complet de `TrainingPage.create_training()`, PASS sur les quatre scénarios réellement atteignables.

### État du projet (Mission 058)

967/967 tests automatisés verts. Commit fonctionnel `9e35c4497fe880123f46a6edd6b10603727d123c` (`chore: remove dead code and stale documentation (round 2)`), tag `v0.2-mission058`, GitHub Release publiée. Voir `docs/missions/MISSION_058.md` pour le détail complet.

---

## v0.2-mission057 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 057 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 057)

**Mission 057 — Remove Vestigial Workspace Fields and Dead Code.** Un audit factuel du dépôt post-Mission 056 a confirmé, code à l'appui, que trois éléments étaient du code/état mort : `Workspace.datasets`/`.loras`/`.training` (champs génériques non typés, jamais lus par aucun Manager — `DatasetManager`/`LoRAManager`/`TrainingManager` lisent exclusivement `Character.datasets`/`.loras`/`.trainings`, une violation du principe Single Source of Truth de `CLAUDE.md`), `Character.history` (sérialisé depuis son introduction mais jamais peuplé ni lu nulle part), et `src/ui/pages/base_page.py` (`BasePage`, jamais hérité par aucune des 11 Pages du projet).

Les trois éléments sont retirés. `Workspace.models`/`.workflows`/`.images`/`.characters`/`.settings`/`.root` et `Character.datasets`/`.loras`/`.prompts`/`.trainings` — les collections réellement possédées et consommées — restent strictement inchangés.

**Compatibilité défensive démontrée par tests, pas seulement affirmée** (précision explicitement exigée par l'architecte avant implémentation) : un `project.json` écrit avant cette mission et contenant encore ces clés, même peuplées de données non vides, continue de se charger sans erreur ; ces clés ne sont plus jamais réémises une fois le Workspace sauvegardé avec cette version — un nettoyage d'un schéma mort, jamais présenté comme une migration de données fonctionnelles, ces champs n'ayant jamais porté de donnée réelle à aucun stade du projet.

Aucun changement Inference/Settings/portabilité des chemins/Domain (au-delà des retraits ci-dessus)/EventBus.

### Tests ajoutés (Mission 057)

- 9 tests nets nouveaux dans `test_workspace_roundtrip.py` (aucun nouveau fichier) : nouvelle classe `WorkspaceVestigialFieldsRemovalTest` — chargement réussi d'un `project.json` legacy avec `datasets`/`loras`/`training`/`history` peuplés ; collections réelles (`Character.datasets`/`.loras`/`.prompts`/`.trainings`, `Workspace.models`/`.workflows`) intactes après ce chargement ; clés absentes après re-sauvegarde ; Workspace neuf n'émettant jamais ces clés ; cycle création/fermeture/réouverture sans régression ; absence totale de référence à `BasePage`/`base_page` dans `src/ui/pages/*.py`.
- 2 tests nets nouveaux dans `test_character_roundtrip.py` : nouvelle classe `CharacterHistoryFieldRemovalTest` — preuve Domain-level isolée, indépendante du cycle Workspace complet.
- 8 assertions obsolètes retirées (comparaisons portant sur les champs supprimés) dans `test_workflow_roundtrip.py` (2) et `test_settings_roundtrip.py` (6, répartis sur 2 tests) — aucune autre logique de test modifiée.
- **967/967 tests verts** au total (956 précédents + 11 nets nouveaux). Non-régression confirmée sur `test_workspace_roundtrip.py` (89/89), `test_character_roundtrip.py` (42/42), `test_workflow_roundtrip.py` (21/21), `test_settings_roundtrip.py` (9/9), `test_dataset_roundtrip.py` (49/49), `test_lora_roundtrip.py` (67/67), `test_training_roundtrip.py` (34/34).
- **Cycle réel création → sauvegarde → fermeture → réouverture, exécuté manuellement en dehors de `unittest`, JSON produit inspecté directement : PASS** — un `project.json` legacy écrit à la main (clés retirées peuplées de données non vides, aux côtés d'un Dataset/LoRA/Prompt/Training réels) se charge sans erreur ; après réouverture avec une pile entièrement neuve puis sauvegarde, le fichier réécrit ne contient plus les clés retirées, et les données fonctionnelles (Dataset/LoRA/Prompt/Training/Model/Workflow) sont toutes préservées intactes. Aucun smoke test Qt requis — aucun comportement UI observable n'est modifié par cette mission.

### État du projet (Mission 057)

Le dépôt referme une incohérence architecturale documentée depuis les Missions 026-029 (migration de la propriété de `Dataset`/`LoRA`/`Training` de `Workspace` vers `Character`, jamais suivie du retrait des champs `Workspace` devenus obsolètes) et une dette mineure plus ancienne (`Character.history`, `BasePage`). Validée par la suite automatisée complète et par un cycle réel d'utilisation avec inspection directe du fichier produit. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `c7eb1fe0c32f677226f5b14c93dbbf82832e3bef` — `refactor: remove vestigial Workspace fields and dead code`, tag `v0.2-mission057`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et non résolu — Mission 057 n'y touche strictement pas (nettoyage Domain/dead-code uniquement, aucun changement Inference) ; la primitive typée `Reference(path, role)` introduite par Mission 056 reste la seule brique posée, avec `pose_composition` comme seul rôle réellement actionnable.

---

## v0.2-mission056 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 056 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 056)

**Mission 056 — Typed Inference Reference Primitive.** Un audit dédié de l'architecture Inference a confirmé que la limitation à une seule référence était codée à toutes les couches (`InferencePage._reference_image_path` scalaire, `GenerationManager.generate()` rejetant `len(reference_images) > 1`, `ComfyUIEngine.generate_image(reference_image: Optional[dict])` structurellement singulier), alors que l'architecture « 0..N références avec rôles » documentée dans `PROJECT_CONTEXT.md` n'existait que dans des commentaires — zéro code. L'architecte a validé une orientation (Option B) restreinte à une primitive typée générique, sans intégrer aucun mécanisme moteur concret (IP-Adapter/ControlNet/InstantID/PuLID, chacun réservé à une mission future distincte).

Nouvelle primitive transitoire `Reference(path, role)` (`NamedTuple`, colocalisée dans `GenerationManager` — même précédent architectural que `CharacterContext` dans `PromptAssistantManager`) et constante unique `REFERENCE_ROLE_POSE_COMPOSITION` — le seul rôle réellement actionnable, retypant sans le modifier le mécanisme img2img mono-référence déjà existant. `InferencePage._start_generation()` construit désormais réellement un `Reference` pour son flux de production, au lieu de transmettre un chemin brut. Compatibilité legacy intégrale : un appelant passant une simple chaîne continue de fonctionner sans migration, normalisé en interne vers `role=pose_composition`.

**Distinction stricte entre modèle de collection et capacité de génération réellement livrée** : `reference_images` reste une collection `List[Union[str, Reference]]` conçue pour recevoir un jour 0..N références typées, mais la capacité de génération réellement livrée par cette mission reste strictement **0..1 référence actionnable**. Aucune référence → `txt2img` inchangé. Une référence de rôle `pose_composition` → `img2img` inchangé, un seul appel `upload_image()`, résultat transmis à `generate_image()` sans modification. Une référence de tout autre rôle → `GenerationError` explicite avant tout upload. Plusieurs références (quel que soit leur rôle) → `GenerationError` explicite indiquant que la représentation multi-références existe mais que la génération simultanée n'est pas encore supportée — aucun upload tenté, aucun fallback silencieux, aucun choix implicite de « la première » référence.

Aucun changement `ComfyUIEngine`/`comfyui_workflows.py`/Domain/EventBus. Aucune constante ou enum créée pour les rôles futurs (identité, tenue, décor/environnement, style) — documentés en prose uniquement dans les docstrings, pour éviter toute taxonomie morte. Ne livre ni intégration IP-Adapter/ControlNet/InstantID/PuLID, ni génération simultanée multi-références, ni « Dataset de références → Inference ».

### Tests ajoutés (Mission 056)

- 6 tests nets nouveaux dans `test_generation_manager.py` (aucun nouveau fichier) : nouvelle classe `GenerationManagerTypedReferenceTest` — `Reference(path, "pose_composition")` explicite reproduit exactement le comportement legacy ; rôle non supporté lève `GenerationError` avant tout upload et sans passer `busy` à `True` ; deux références (rôles mêlés) lèvent une erreur distincte avant tout upload ; valeur de la constante `REFERENCE_ROLE_POSE_COMPOSITION` ; `Reference` strictement minimal (`path`, `role`, aucun champ supplémentaire).
- `test_inference_page.py` : 4 assertions `reference_images=[...]` migrées de chaînes brutes vers `Reference(...)`, 2 assertions de libellé mises à jour (`"<fichier> — Pose / composition"`), aucun nouveau test — preuve directe qu'`InferencePage` construit désormais réellement un `Reference`.
- **956/956 tests verts** au total (950 précédents + 6 nets nouveaux) : `test_generation_manager.py` 33/33, `test_inference_page.py` 78/78.
- **Smoke test manuel réel du rendu Qt, PASS** (21/21 assertions) — génération réelle sans référence (`reference_image=None`, aucun upload), sélection réelle via le vrai `QFileDialog` (libellé naturel affiché, jamais le terme technique brut), génération réelle avec la référence (`upload_image()` appelé exactement une fois, résultat transmis inchangé à `generate_image()` avec `denoise=0.75`), Regenerate/Reject réels sans régression, appel contrôlé avec un rôle non supporté prouvant zéro upload et zéro génération.

### État du projet (Mission 056)

`InferencePage`/`GenerationManager` disposent désormais d'une fondation structurelle réelle pour les références typées, immédiatement utilisée par le flux mono-référence de production — pas une abstraction vide « pour plus tard ». Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `f095b74c07b63ba5d5293cef8684e4acb0400f9c` — `feat: introduce typed Inference reference primitive`, tag `v0.2-mission056`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et **non résolu** : la primitive typée nécessaire existe désormais, mais l'intégration pratique reste bloquée sur un premier mécanisme moteur réel pour un second rôle, puis sur la consommation simultanée de plusieurs références — chacun nécessitant son propre audit dédié.

---

## v0.2-mission055 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 055 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 055)

**Mission 055 — Graceful Settings Save Errors.** Un audit factuel du dépôt post-Mission 054 a révélé une exception définie et réellement levée, mais jamais interceptée nulle part : `ApplicationSettingsStorageError`, levée par `ApplicationSettingsStorage.save()` en cas d'échec d'écriture, dont la propagation non capturée était documentée et volontaire au niveau `ApplicationSettingsManager`, mais jamais traitée en amont côté UI. Le même défaut existait pour les Workspace Settings : `SettingsPage.save_settings()` ne capturait pas `WorkspaceManagerError`, alors que ce type est déjà intercepté quatre fois ailleurs dans `main_window.py` pour toute autre opération de sauvegarde du Workspace.

`SettingsPage.save_settings()`/`save_application_settings()` interceptent désormais respectivement `WorkspaceManagerError`/`ApplicationSettingsStorageError` et affichent `QMessageBox.critical(self, "Erreur", str(exc))` — remploi exact de la convention déjà validée quatre fois dans `main_window.py`, aucun nouveau texte métier inventé. Le chemin de succès reste strictement inchangé, l'UI reste pleinement utilisable après une erreur (champs/boutons toujours activés), et un second enregistrement réel réussit une fois la cause corrigée.

Aucun changement Domain/Manager/Storage/EventBus — mission strictement additive côté UI. Ne résout ni la refonte Settings, ni l'exploitation de `comfyui_path`, ni l'organisation multi-engine.

### Tests ajoutés (Mission 055)

- 5 tests nets nouveaux dans `test_settings_page.py` (aucun nouveau fichier) : nouvelle classe `SettingsPageSaveErrorTest` — échec `ApplicationSettingsStorageError` intercepté sans lever, `ApplicationSettings` inchangés en mémoire après l'échec, page réutilisable pour un vrai enregistrement ensuite ; échec `WorkspaceManagerError` intercepté sans lever, champs/bouton toujours activés, page réutilisable pour un vrai enregistrement ensuite.
- **950/950 tests verts** au total (945 précédents + 5 nets nouveaux) : `test_settings_page.py` 33/33, non-régression Settings (`test_settings_roundtrip.py`/`test_application_settings_roundtrip.py`/`test_main_window_comfyui_settings.py`/`test_main_window_ollama_settings.py`) 29/29.
- **Smoke test manuel réel du rendu Qt, PASS** — échec réel du système de fichiers pour Application Settings (aucun mock sur le chemin d'échec lui-même : cible occupée par un vrai sous-dossier, `OSError` réelle enveloppée en `ApplicationSettingsStorageError` réelle), patch contrôlé pour Workspace Settings (rendre un dossier réellement inaccessible en écriture s'étant avéré peu fiable sous Windows dans cet environnement) — dans les deux cas, `QMessageBox.critical` confirmé invoqué, aucun crash, UI confirmée réutilisable, second enregistrement réel confirmé fonctionnel après correction de la cause.

### État du projet (Mission 055)

Les deux boutons « Enregistrer » de `SettingsPage` (Workspace Settings et Application Settings) traitent désormais gracieusement un échec d'écriture réel, au même titre que toute autre opération de sauvegarde de l'application. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `6469193f0e189a85525c3d3168851c54f69455b9` — `fix: handle Settings save errors gracefully`, tag `v0.2-mission055`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et non résolu, dépendant toujours de l'introduction d'une primitive Inference 0..N références avec rôles qui n'existe pas encore.

---

## v0.2-mission054 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 054 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 054)

**Mission 054 — Rename Dataset and Training after Creation.** Étend à `Dataset` et `Training` le renommage post-création déjà livré pour `Character`/`Model`/`Workflow`/`LoRA`/`Prompt` — refermant la dernière asymétrie de renommage de l'application. `Dataset` et `Training` ne possédaient encore, avant cette mission, **aucune** méthode `update()` d'aucune sorte ; `update_name()` en est la toute première pour chacun des deux Managers, mais le contrat, entièrement dicté par les cinq précédents directs, ne comportait aucune décision produit ou architecturale substantielle restant ouverte.

`DatasetManager.update_name(name)` et `TrainingManager.update_name(name)` opèrent implicitement sur `self.active_dataset`/`self.active_training` (mirroir de `ModelManager.update_name()`/`PromptManager.update_name()`, pas du style `lora_id` explicite de `LoRAManager.update_name()`) : `False`/aucun `save()` si aucune entité active ou si le nom est identique à la valeur stockée, aucun événement dédié publié, chaîne vide légitime et non validée.

Côté UI, `DatasetsPage` et `TrainingPage` gagnent chacune un champ `name_edit` éditable, renommé sur `editingFinished`, sans bouton ni dialogue dédié. `dataset_id`/`training_id`, `Dataset.images` et `Training.dataset_id` restent strictement inchangés par un renommage — une Training référençant un Dataset renommé continue de pointer vers le même `dataset_id`, et `TrainingPage.dataset_label` reflète le nouveau nom du Dataset sans aucun nouveau wiring EventBus, via le seul canal `WORKSPACE_SAVED` déjà souscrit.

Comportement de tri confirmé et **délibérément asymétrique** entre les deux entités : `training_list` (triée depuis Mission 051) se retrie automatiquement après un renommage, sélection conservée par `training_id`. `dataset_list` n'a jamais été triée (hors périmètre de Mission 051, vérifié par relecture directe du code) et Mission 054 n'y introduit aucun tri nouveau — le Dataset renommé garde simplement sa position d'insertion, sélectionné par `dataset_id`.

Aucun changement Domain/EventBus.

### Tests ajoutés (Mission 054)

- 24 tests nets nouveaux, aucun nouveau fichier : 8 `DatasetManagerRenameTest` + 5 `DatasetsPageRenameTest` (`test_dataset_roundtrip.py`), 6 `TrainingManagerRenameTest` + 5 `TrainingPageRenameTest` (`test_training_roundtrip.py`).
- Couverture : renommage réel via le vrai widget, idempotence, `dataset_id`/`training_id`/`images`/`dataset_id` de Training préservés, référence Training→Dataset conservée par ID après renommage du Dataset, `dataset_list` confirmée en ordre d'insertion après renommage, `training_list` confirmée retriée dans les deux sens avec sélection par ID, `TrainingPage.dataset_label` confirmée rafraîchie, aucune entité active → no-op, persistance après fermeture/réouverture.
- **945/945 tests verts** au total (921 précédents + 24 nets nouveaux), suite ciblée : `test_dataset_roundtrip.py` 49/49, `test_datasets_page.py` 45/45, `test_training_roundtrip.py` 34/34.
- **Smoke test manuel réel du rendu Qt, PASS** — Dataset avec image physique réelle référencé par une Training réelle : renommage réel des deux entités, IDs et relation préservés, `dataset_label` rafraîchi, `is_referenced_by_training()` toujours vrai, non-régression de `add_images()`/`remove_images()`, persistance confirmée après fermeture/réouverture réelle du Workspace.

### État du projet (Mission 054)

Toutes les entités possédant un champ `name` (`Character`, `Model`, `Workflow`, `LoRA`, `Prompt`, `Dataset`, `Training`) sont désormais renommables après leur création — dernière asymétrie de renommage de l'application résolue. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `a892f57b3f6fabffcc84203b0417a622fb80974d` — `feat: rename Dataset and Training after creation`, tag `v0.2-mission054`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et non résolu, dépendant toujours de l'introduction d'une primitive Inference 0..N références avec rôles qui n'existe pas encore.

---

## v0.2-mission053 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 053 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 053)

**Mission 053 — Rename Prompt after Creation.** Étend à `Prompt` le renommage post-création déjà livré pour `Model`, `Workflow` et `LoRA` par Mission 052 — la seule exclusion de Mission 052, dont le mini-audit dédié a confirmé qu'elle ne comportait en réalité aucune incompatibilité avec le dirty-state introduit par Mission 038.

`PromptManager` gagne une nouvelle méthode sibling additive **`update_name(name)`**, mirroir exact du contrat idempotent déjà établi par `update_text()` : opère implicitement sur `self.active_prompt`, `False`/aucun `save()` si aucun prompt actif ou si `name` est identique à la valeur stockée, aucun événement dédié publié, `text` jamais touché.

Côté UI, `PromptsPage` gagne un champ `name_edit` éditable, peuplé à l'intérieur de `_refresh_prompt_list()` et renommé sur `editingFinished`, sans bouton ni dialogue dédié. `name_edit` est entièrement indépendant du mécanisme de dirty-state de Mission 038 : `_dirty`/`_loaded_prompt_id` restent pilotés exclusivement par `text_edit.textChanged`, jamais par le renommage. Un brouillon non sauvegardé survit intact à un renommage — texte affiché inchangé, `_dirty` toujours `True` — et `save_text()` reste pleinement fonctionnel ensuite.

`prompt_id` et le texte persisté restent strictement inchangés par un renommage. Le renommage interagit correctement avec le tri alphabétique de Mission 051 : la liste se retrie automatiquement, dans les deux sens, tandis que la sélection reste sur l'entité renommée par **ID**, jamais par position d'affichage. Politique de validation du nom identique au précédent de Mission 052 : aucune (pas de `.strip()`, pas de rejet du vide, pas de contrainte d'unicité).

Aucun changement Domain/EventBus. `Dataset` et `Training` restent explicitement hors périmètre — aucune méthode `update()` d'aucune sorte n'existe encore pour ces deux entités.

### Tests ajoutés (Mission 053)

- 8 tests nets nouveaux dans `test_prompt_roundtrip.py` (aucun nouveau fichier) : 2 dans `PromptRoundTripTest` (`test_update_name_is_idempotent`, `test_rename_persists_after_close_reopen`) et 6 dans la nouvelle classe `PromptsPageRenameTest`.
- Couverture : renommage réel via le vrai widget, idempotence, `prompt_id`/texte préservés, retri correct dans les deux sens avec sélection conservée par ID, aucun prompt actif → no-op, persistance après fermeture/réouverture. Le test `test_rename_with_unsaved_text_preserves_dirty_state_and_draft` couvre le scénario critique explicitement requis : texte non sauvegardé → renommage → retri → dirty-state et brouillon intacts → `save_text()` toujours fonctionnel ensuite.
- **921/921 tests verts** au total (913 précédents + 8 nets nouveaux), suite ciblée : `test_prompt_roundtrip.py` 73/73 OK, confirmant l'absence de régression sur le Prompt Assistant, « Envoyer vers Inference » et « Enregistrer comme nouveau Prompt… ».
- **Smoke test manuel réel du rendu Qt, PASS** — renommage réel via `name_edit`, retri confirmé, sélection conservée par ID, texte sauvegardé jamais touché, brouillon non sauvegardé confirmé intact après renommage, `save_text()` confirmé fonctionnel ensuite, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 053)

L'asymétrie de renommage entre `Character`/`Model`/`Workflow`/`LoRA` (renommables) et `Prompt` (jusque-là non renommable) est désormais résolue. Seuls `Dataset`/`Training` restent explicitement non renommables — candidats probables pour une mission future distincte, chacun nécessitant l'introduction de sa toute première méthode `update()`. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `97384521ee1b487280707593c009305359893891` — `feat: rename Prompt after creation`, tag `v0.2-mission053`, GitHub Release publiée).

---

## v0.2-mission052 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 052 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 052)

**Mission 052 — Rename Model, Workflow and LoRA after Creation.** Étend à `Model`, `Workflow` et `LoRA` la capacité de renommage post-création déjà disponible pour `Character` (`CharacterManager.update(name=...)`) — un écart mécanique découvert par audit direct du code, pas un besoin déjà documenté.

Chaque Manager gagne une nouvelle méthode sibling additive **`update_name(...)`**, suivant le même contrat idempotent déjà établi par `update_file_path()`/`update_text()`/`update()` : `ModelManager.update_name(name)` et `WorkflowManager.update_name(name)` opèrent sur l'entité active (mirroir de `update_file_path()`), `LoRAManager.update_name(lora_id, name)` cible par `lora_id` explicite (mirroir de `update()`). Aucune méthode existante n'est renommée ou fusionnée ; aucun événement dédié n'est publié — `WORKSPACE_SAVED` suffit déjà à déclencher le rafraîchissement des Pages déjà abonnées.

Côté UI, `ModelsPage`/`WorkflowsPage`/`LoRAPage` gagnent un champ `name_edit` éditable, renommage déclenché sur `editingFinished` (perte de focus/Entrée), sans bouton ni dialogue dédié — cohérent avec le mécanisme d'édition immédiate déjà en place pour `file_path_edit`/les champs Metadata LoRA. Pour LoRA, `name_edit` reste explicitement hors du panneau Metadata (Mission 047), n'interfère pas avec le bouton « Enregistrer les métadonnées ». Politique de validation du nom : aucune (pas de `.strip()`, pas de rejet du vide, pas de contrainte d'unicité) — mirroir exact du seul précédent de renommage existant, `CharactersPage.save_identity()`.

`model_id`/`workflow_id`/`lora_id` et toute autre propriété (`file_path` ; `LoRA.files`/`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`) restent strictement inchangés par un renommage. Le renommage interagit correctement avec le tri alphabétique de Mission 051 : la liste se retrie automatiquement après un renommage, dans les deux sens (déplacement vers le début ou la fin de liste), tandis que la sélection reste sur l'entité renommée par **ID**, jamais par position d'affichage.

Aucun changement Domain/EventBus. `Prompt`, `Dataset`, `Training` et `Character` sont explicitement hors périmètre — `Prompt` a une structure de Page incompatible (dirty-state), `Dataset`/`Training` n'ont aujourd'hui aucune méthode `update()` d'aucune sorte, `Character` dispose déjà de cette capacité.

### Tests ajoutés (Mission 052)

- 28 tests nets nouveaux, répartis sur trois suites existantes (aucun nouveau fichier) : `test_model_roundtrip.py` (+7, dont `ModelsPageRenameTest`), `test_workflow_roundtrip.py` (+7, mirroir exact), `test_lora_roundtrip.py` (+14 — `LoRAManagerRenameTest` 7 + `LoRAPageRenameTest` 7).
- Chaque suite couvre : renommage réel, idempotence (aucun `save()` si valeur inchangée), `save()` appelé une seule fois lors d'une mutation réelle, préservation de l'ID et des autres propriétés, chaîne vide légitime, entité/`lora_id` inconnu → `False`, persistance après fermeture/réouverture, renommage via le vrai widget Qt, retri correct dans les deux sens avec sélection conservée par ID. `LoRAPageRenameTest` ajoute la non-régression explicite de `add_files()`/`remove_files()`/`save_metadata()`/`set_thumbnail()` après un renommage.
- **913/913 tests verts** au total (885 précédents + 28 nets nouveaux), suite ciblée : 28/28 OK (`test_model_roundtrip.py` 20/20, `test_workflow_roundtrip.py` 21/21, `test_lora_roundtrip.py` 67/67).
- **Smoke test manuel réel du rendu Qt, PASS** — renommage réel via `name_edit` sur les trois Pages, retri confirmé dans les deux sens, sélection conservée par ID, `file_path`/`LoRA.files`/Metadata/thumbnail confirmés intacts, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 052)

L'asymétrie de renommage entre `Character` (déjà renommable) et `Model`/`Workflow`/`LoRA` (jusque-là non renommables) est désormais résolue. `Prompt`/`Dataset`/`Training` restent explicitement non renommables — candidats probables pour une mission future distincte, chacun nécessitant son propre audit (structure de Page différente pour `Prompt`, absence totale d'`update()` pour `Dataset`/`Training`). Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `a0e792e9cc6f321c29af673a4755ca4abeb77ed6` — `feat: rename Model, Workflow and LoRA after creation`, tag `v0.2-mission052`, GitHub Release publiée).

---

## v0.2-mission051 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 051 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 051)

**Mission 051 — Sort Remaining Entity Lists by Name.** Étend aux cinq dernières listes d'entités de l'application (`ModelsPage.model_list`, `WorkflowsPage.workflow_list`, `TrainingPage.training_list`, `PromptsPage.prompt_list`, `LoRAPage.lora_list`) le tri par nom déjà livré pour les galeries `ImagesPage`/`DatasetsPage` par Mission 048 — la dernière dette de tri d'affichage encore ouverte dans l'application.

Chaque Page trie désormais sa liste par `name`, **alphabétique (A → Z), insensible à la casse, toujours actif, sans aucun contrôle UI** (pas de combobox/bouton — un seul critère de tri existant pour ces cinq entités, contrairement aux galeries Images/Datasets où Mission 049 a dû introduire un sélecteur Nom/Date). Le tri (`sorted()`, garanti stable par Python) est appliqué sur une **copie temporaire** construite juste avant la boucle de peuplement de chaque `QListWidget` — `Workspace.models`/`.workflows` et `Character.loras`/`.prompts`/`.trainings` (Domain) ne sont **jamais mutés ni réordonnés**.

Changement strictement Presentation : aucune modification de `Model`/`Workflow`/`Prompt`/`Training`/`LoRA` (Domain), d'aucun Manager, ni d'aucun wiring EventBus. `PromptsPage._refresh_prompt_list()` reçoit le tri sans toucher au dirty-state, à l'éditeur, au Prompt Assistant, à « Send to Inference » ni à « Save as New Prompt ». `LoRAPage.update_loras()` ne trie que `lora_list` — la boucle `files_list` introduite par Mission 050 reste intacte, ainsi que `LoRA.files`/Metadata/thumbnail.

### Tests ajoutés (Mission 051)

- 26 tests nets nouveaux, répartis sur les cinq suites existantes (aucun nouveau fichier) : `ModelsPageSortTest` (5), `WorkflowsPageSortTest` (5), `TrainingPageSortTest` (5), `PromptsPageSortTest` (6 — un test dédié à la non-régression du dirty-state/`save_text()`), `LoRAPageSortTest` (5 — un test dédié confirmant `LoRA.files`/Metadata/thumbnail intacts après sélection sur liste triée).
- Chaque classe couvre : affichage alphabétique insensible à la casse, préservation de l'ordre d'insertion de la collection Domain source, stabilité du tri à noms identiques, sélection/édition ciblant correctement la bonne entité malgré un déplacement d'affichage, retri correct après un second rafraîchissement.
- **885/885 tests verts** au total (859 précédents + 26 nets nouveaux), suite ciblée : 26/26 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — cinq scénarios réels (un par Page), tri visuel confirmé, sélection après tri confirmée cibler la bonne entité, collections Domain confirmées non réordonnées par inspection directe, dirty-state/éditeur `PromptsPage` et `LoRA.files`/Metadata/thumbnail confirmés intacts.

### État du projet (Mission 051)

La dette de tri d'affichage, résolue pour les galeries Images/Datasets par Mission 048/049, est désormais résolue pour l'ensemble des listes d'entités de l'application. Aucun nouveau besoin distinct identifié en retour par cette mission — changement purement Presentation, sans impact Domain/Manager/EventBus. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `0d6a2c54a79dc42701c1c250e8f63167857e948c` — `feat: sort Models, Workflows, Trainings, Prompts and LoRAs lists by name`, tag `v0.2-mission051`, GitHub Release publiée).

---

## v0.2-mission050 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 050 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 050)

**Mission 050 — Remove Individual Files from a LoRA.** Referme un manque symétrique à `add_files()` : `LoRAManager` ne proposait aucune méthode pour retirer un fichier individuel d'une LoRA, seule la suppression de la LoRA entière (`delete_lora()`) existait — une conséquence devenue plus coûteuse depuis Mission 047, qui a rendu la fiche LoRA (`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`) réellement éditable et donc perdable en cas de suppression complète pour corriger un simple fichier mal importé.

`LoRAManager.remove_files(paths: List[str]) -> int` retire les chemins correspondants de `LoRA.files` par **égalité de chaîne exacte** (même convention que `add_files()` — jamais une résolution/normalisation de chemin, puisque `LoRA.files` référence toujours des fichiers externes jamais copiés physiquement), sauvegarde uniquement si une mutation réelle a eu lieu, ne touche jamais le fichier physique ni `name`/`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`.

`LoRAPage.files_list` passe en `QListWidget.ExtendedSelection` (retrait multiple en une seule opération), nouveau bouton « Retirer les fichiers sélectionnés » activé uniquement si une LoRA active existe et qu'au moins un fichier est sélectionné (mirroir de `_update_metadata_buttons_state()`). Aucune confirmation avant retrait — cohérent avec le précédent non destructif établi par Mission 045. Retirer la dernière référence laisse simplement `LoRA.files == []`, la LoRA restant pleinement valide avec sa fiche de métadonnées intacte.

**Distinction explicite** : cette mission ne retire qu'une **référence** dans `LoRA.files` — à aucun moment un fichier n'est supprimé, déplacé ou copié sur disque, à la différence de `ImagesPage.delete_selected_images()` (Mission 046) qui peut supprimer physiquement un fichier interne au Workspace. Aucun changement Domain/EventBus ; rafraîchissement via le seul canal `WORKSPACE_SAVED` déjà existant.

**Ne résout ni la sélection de LoRA multi-engine ni une gestion générale des assets** — ces besoins restent entièrement ouverts.

### Tests ajoutés (Mission 050)

- 19 tests nets nouveaux : nouvelle classe `LoRAManagerRemoveFilesTest` (9 tests — retrait simple/multiple, chemin inconnu sans sauvegarde, sauvegarde uniquement si mutation réelle, retrait de la dernière entrée, sans LoRA active, fichier physique confirmé intact, métadonnées/miniature confirmées inchangées, persistance après fermeture/réouverture) et extension de `LoRARoundTripTest` (10 tests, widgets Qt réels — `ExtendedSelection`, activation/désactivation du bouton, retrait simple/multiple réel, no-op sans sélection, liste vide après dernier retrait, changement de LoRA active, Métadonnées/miniature intactes après retrait).
- **859/859 tests verts** au total (840 précédents + 19 nets nouveaux), suite ciblée : 19/19 OK (48/48 sur `test_lora_roundtrip.py` au total).
- **Smoke test manuel réel du rendu Qt, PASS** — 3 fichiers externes réels importés, fiche Métadonnées et miniature réellement remplies, retrait réel de 2 fichiers sur 3 confirmé (fichiers physiques toujours présents, Métadonnées/miniature strictement intactes), retrait du dernier fichier confirmé (`files == []`, LoRA toujours valide), persistance confirmée après fermeture/réouverture réelle du Workspace.

### État du projet (Mission 050)

Le retrait de fichier individuel d'une LoRA, absent depuis l'origine et devenu plus coûteux depuis Mission 047, est désormais **résolu**. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission — la sélection de LoRA multi-engine et la gestion générale des assets restent explicitement hors périmètre. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `14ffc9c25367707a52ef7ae8f87e105f19016603` — `feat: add removing individual files from a LoRA`, tag `v0.2-mission050`, GitHub Release publiée).

---

## v0.2-mission049 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 049 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 049)

**Mission 049 — Sort Images and Dataset Galleries by File Date.** Referme le tri par date resté ouvert depuis Mission 048 : `ImagesPage` et `DatasetsPage` gagnent un contrôle explicite « Trier par : » à deux critères fixes — **Nom (A → Z)** (inchangé depuis Mission 048) et **Date du fichier (plus récent d'abord)**.

Le tri par date est fondé sur `Path(file_path).stat().st_mtime`, ordre décroissant, tri stable, via un petit helper Presentation partagé (`file_mtime_sort_key()`, `src/ui/thumbnails.py`) — aucun nouveau champ Domain, aucune modification de `Image.to_dict()`/`from_dict()`, aucune migration des anciens `project.json`.

**Compromis explicitement accepté** : `WorkspaceStorage.copy_into_workspace()` utilise `shutil.copy2()`, qui préserve le `mtime` du fichier source lors d'un import. Une photo ancienne importée aujourd'hui conserve donc son ancien `mtime` — le tri reflète la **date de dernière modification du fichier sur disque**, jamais sa **date d'ajout au Workspace/Dataset**. Ce comportement est volontaire pour cette mission, aucun mécanisme de date d'import n'est introduit.

Un fichier dont `stat()` échoue (supprimé, inaccessible, ...) retombe sur une clé `float("-inf")` — la plus petite valeur possible — le plaçant systématiquement en toute dernière position sous un tri décroissant, jamais accidentellement en tête. Plusieurs fichiers manquants conservent leur ordre relatif d'origine (tri stable). Le critère sélectionné est un état de session propre à chaque Page : il survit aux rafraîchissements `WORKSPACE_SAVED` et aux changements de Dataset actif sans être réinitialisé, mais n'est pas persisté au-delà de la session. Aucun changement Manager ou EventBus — `Workspace.images`/`Dataset.images` conservent toujours leur ordre stocké d'origine, le tri ne s'appliquant que sur une copie temporaire, exactement comme Mission 048.

### Tests ajoutés (Mission 049)

- 17 tests nets nouveaux, étendant `ImagesPageGallerySortTest`/`DatasetsPageGallerySortTest` (Mission 048, aucun nouveau fichier) : tri par date décroissant sur `mtime` réels échelonnés (`os.utime()`), fichier interne et externe, fichier manquant en fin de liste, plusieurs fichiers manquants et `mtime` identiques tous deux stables, bascule réelle Nom↔Date via le `QComboBox`, critère conservé après un `WORKSPACE_SAVED` réel et après un changement de Dataset actif, ordre `Workspace.images`/`Dataset.images` confirmé inchangé.
- **840/840 tests verts** au total (823 précédents + 17 nets nouveaux), suite ciblée : 17/17 OK, non-régression `test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py` : 128/128 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — fichiers à noms désordonnés/casse mixte et `mtime` explicitement échelonnés importés dans les deux galeries ; bascule réelle du contrôle confirmée décroissante dans `ImagesPage` et `DatasetsPage` ; fichier manquant confirmé en fin de liste sans exception ; critère confirmé conservé après un rafraîchissement `WORKSPACE_SAVED` réel ; `Workspace.images`/`Dataset.images` confirmés inchangés par inspection directe.

### État du projet (Mission 049)

Le besoin "tri de la galerie Images" (identifié Mission 023) est désormais **entièrement résolu** — tri par nom (Mission 048) et tri par date (Mission 049) tous deux livrés. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `8deae97e9c15b7bb27b57c8df3b4a2101468a4d9` — `feat: add sorting Images and Dataset galleries by file date`, tag `v0.2-mission049`, GitHub Release publiée).

---

## v0.2-mission048 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 048 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 048)

**Mission 048 — Sort Images and Dataset Galleries by Filename.** Les galeries `ImagesPage` et `DatasetsPage` sont désormais triées, toujours actif, facilitant la recherche d'une image précise à mesure que la collection d'un projet grandit.

Le tri est calculé sur `Path(file_path).name`, **insensible à la casse**, via le `sorted()` stable de Python — deux éléments partageant la même clé après normalisation de casse conservent leur ordre relatif d'origine. Appliqué de façon cohérente à **`ImagesPage`** (galerie principale du Workspace) et **`DatasetsPage`** (galerie du Dataset actif). Le tri est purement un ordre d'affichage : calculé sur une copie temporaire juste avant peuplement de la galerie — **aucune mutation de `Workspace.images` ni de `Dataset.images`**, qui conservent tous deux leur ordre d'insertion d'origine dans les données du projet. Aucun contrôle UI n'est introduit : pas de combobox/bouton de critère, pas d'ordre ascendant/descendant configurable, pas de préférence persistée — la galerie est simplement toujours affichée triée par nom.

Un test existant qui localisait un item par sa position d'insertion (`test_missing_file_item_still_created_with_fallback_icon_and_user_role`) a été rendu indépendant de cet ordre — il localise désormais l'item par identité (`Qt.UserRole`), comme son voisin déjà existant. Aucun changement de ce que le test vérifie réellement. Aucun changement Domain, Manager, ou EventBus — modification strictement confinée à la couche Presentation.

### Tests ajoutés (Mission 048)

- Nouvelles classes `ImagesPageGallerySortTest` et `DatasetsPageGallerySortTest` (6 tests chacune, 12 au total) — tri alphabétique sur noms volontairement désordonnés et de casse mixte, stabilité pour deux fichiers de même nom affiché, `Workspace.images`/`Dataset.images` confirmés dans leur ordre d'insertion d'origine, re-tri confirmé après un second `WORKSPACE_SAVED`, sélection/aperçu confirmés fonctionnels après réordonnancement de l'affichage.
- **823/823 tests verts** au total (811 précédents + 12 nets nouveaux), suite ciblée : 12/12 OK, non-régression `test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py` : 111/111 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — noms désordonnés et casse mixte importés dans les deux galeries, ordre affiché confirmé sorté alphabétiquement ; stabilité confirmée ; sélection et aperçu confirmés fonctionnels après réordonnancement ; `Workspace.images`/`Dataset.images` confirmés inchangés dans leur ordre d'insertion d'origine par inspection directe.

### État du projet (Mission 048)

Le besoin "tri de la galerie Images" (identifié Mission 023) est **partiellement résolu** — le tri par nom est désormais livré. **Le tri par date reste explicitement ouvert et non traité par cette mission** — besoin précisé par l'architecte : permettre d'afficher notamment les images les plus récentes en premier. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `714b40e41dc5f72245a3a5d524f716eee2519c1c` — `feat: sort Images and Dataset galleries by filename`, tag `v0.2-mission048`, GitHub Release publiée).

---

## v0.2-mission047 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 047 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 047)

**Mission 047 — LoRA Metadata Fiche.** Rend enfin éditables et persistantes les métadonnées LoRA prévues par le Domain depuis l'origine (Mission 006), jamais exposées jusqu'ici : un audit exhaustif avait confirmé que `LoRA.engine`/`.architecture`/`.trigger_word`/`.version`/`.thumbnail` restaient bloqués à `""` de façon permanente, aucun Manager ni aucune Page ne les exposant.

`LoRAPage` gagne une section « Métadonnées » pour la LoRA active — 4 champs texte libres (Engine/Architecture/Trigger word/Version, aucune liste fermée, aucune taxonomie multi-engine prématurée) sauvegardés uniquement via le bouton explicite « Enregistrer les métadonnées » (aucun auto-save), et un aperçu de miniature avec bouton « Choisir une miniature… ». Nouvelle `LoRAManager.update(lora_id, engine=None, architecture=None, trigger_word=None, version=None)`, strictement idempotente (mirroir exact de `CharacterManager.update()`).

Nouvelle `LoRAManager.set_thumbnail(lora_id, source_path)`, distincte car elle exécute une opération d'E/S réelle : un mini-audit dédié a révélé une tension architecturale réelle entre le Blueprint (LoRA documentée comme ressource partagée entre Workspaces) et le précédent `LoRAManager.add_files()` (jamais copié) d'une part, et l'ergonomie voulue pour l'aperçu d'autre part — tranchée explicitement par l'architecte après présentation de deux options : la miniature choisie est copiée via `WorkspaceStorage.copy_into_workspace()` vers `<workspace_root>/models/loras/<lora_id>/`, **tandis que `LoRA.files` reste strictement inchangé, toujours externe**. Échec de copie : `LoRA.thumbnail` reste strictement inchangé, aucune sauvegarde partielle, échec signalé (`None` + avertissement UI) — jamais de perte silencieuse de la miniature existante. Aucune migration implicite d'une ancienne valeur `thumbnail` déjà persistée. Aucun changement Domain/EventBus, aucun nouveau wiring (`WORKSPACE_SAVED`/`LORA_DELETED` existants suffisent).

### Tests ajoutés (Mission 047)

- Nouvelle classe `LoRAManagerMetadataTest` dans `test_lora_roundtrip.py` (13 tests) — `update()` : mutation réelle et persistance, idempotence (valeur identique → `False`), `None` laisse un champ inchangé, chaîne vide acceptée comme valeur légitime, LoRA inconnue → `False` ; `set_thumbnail()` : copie réelle sous `models/loras/<lora_id>/` (source externe intacte), source déjà interne réutilisée sans nouvelle copie, `LoRA.files` jamais touché, échec de copie (`WorkspaceStorageError` simulée) → `None` et valeur précédente strictement conservée, LoRA inconnue → `None`, persistance après fermeture/réouverture, remplacement d'une miniature existante → nouvelle copie distincte, ancien fichier laissé intact.
- `LoRARoundTripTest` (6 tests nets nouveaux, widgets Qt réels) — fiche vidée/désactivée sans LoRA active, repeuplée à la sélection puis correctement remplacée au changement de LoRA, sauvegarde réelle des 4 champs via le bouton dédié, sélection réelle d'un fichier de miniature copiant le fichier et affichant un `QPixmap` réel, repli exact (`UNAVAILABLE_MESSAGE`) pour un `thumbnail` manquant, échec de copie → avertissement affiché et valeur précédente conservée.
- **811/811 tests verts** au total (792 précédents + 19 nets nouveaux), suite ciblée `test_lora_roundtrip.py` : 29/29 OK (10 précédents + 19 nouveaux).
- **Smoke test manuel réel du rendu Qt, PASS** — édition réelle des 4 champs et sauvegarde confirmées, sélection réelle d'une miniature externe copiée sous le Workspace avec aperçu réel affiché, fichier LoRA lui-même confirmé binaire-identique avant/après, changement/suppression de LoRA correctement reflétés, persistance des métadonnées et du fichier de miniature confirmée après fermeture/réouverture réelle.

### État du projet (Mission 047)

Les métadonnées LoRA (`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`), sérialisées depuis l'origine mais jamais exposées, sont désormais **résolues**. La sélection de LoRA multi-engine/multi-moteur, toute taxonomie fermée pour `engine`/`architecture`, le renommage de la LoRA et tout système de gestion d'assets général restent explicitement hors périmètre et non traités — besoins distincts, non refermés par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `9afc3a2f32be3aaeef9d64448f8720b6bc23b58e` — `feat: add editable LoRA metadata fiche with Workspace-owned thumbnail`, tag `v0.2-mission047`, GitHub Release publiée).

---

## v0.2-mission046 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 046 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 046)

**Mission 046 — Remove Images from the Workspace Gallery.** Referme la dette distincte laissée ouverte par Mission 045 : `ImagesPage`/`Workspace.images` — la galerie principale du Workspace — ne proposait aucune suppression d'image, à la différence de `DatasetsPage` qui sait déjà retirer une référence (Mission 045) ou supprimer un Dataset entier.

Un mini-audit dédié a établi qu'un `Image.file_path` de `Workspace.images` n'est **pas** garanti physiquement interne au Workspace (chemins externes/hérités déjà tolérés et testés avant cette mission) — la politique produit retenue est donc : suppression physique réelle (`Path.unlink()`) uniquement pour un fichier à la fois interne (`WorkspaceStorage.is_inside()`) et présent sur disque ; tout fichier externe ou manquant voit seulement sa référence retirée de `Workspace.images`, sans jamais exposer cette distinction technique à l'utilisateur. Toute image encore référencée par un Dataset bloque atomiquement la suppression de l'ensemble de la sélection — `WorkspaceManager` re-vérifie lui-même la référence, jamais une simple confiance envers un pré-contrôle UI (même schéma d'autorité que `DatasetManager.delete()`).

`ImagesPage` gagne un bouton « Supprimer », `list_widget` passant en sélection étendue (`ExtendedSelection`) pour un retrait multiple en une opération. Une confirmation explicite est désormais obligatoire avant toute mutation, avec trois libellés dédiés selon la composition de la sélection (tout supprimable, tout retrait de référence seul, mixte avec comptage). Nouvelles primitives `WorkspaceManager.images_referenced_by_datasets(paths)`, `preview_image_removal(paths) -> RemovalPreview` et `remove_images(paths) -> RemovalResult` (`NamedTuple`, même convention qu'`ImportResult`/`CollisionInfo`). Le retrait de référence Dataset (Mission 045) et la suppression réelle Workspace (Mission 046) restent deux mécanismes fonctionnellement distincts et non confondus. Aucun changement Domain/EventBus, `DatasetsPage`/`DatasetManager` strictement inchangés.

### Tests ajoutés (Mission 046)

- Nouvelle classe `WorkspaceManagerRemoveImagesTest` dans `test_workspace_roundtrip.py` (14 tests) — `images_referenced_by_datasets()`/`preview_image_removal()`/`remove_images()` : suppression physique réelle d'un fichier interne et présent, fichier externe jamais supprimé physiquement, fichier manquant retiré sans erreur, blocage atomique si au moins une image reste référencée par un Dataset, retrait de référence Dataset (Mission 045) débloquant ensuite la suppression réelle, sauvegarde déclenchée uniquement si mutation réelle, persistance après un cycle fermeture/réouverture.
- `test_images_page.py` (10 tests nets nouveaux) — sélection étendue, état du bouton « Supprimer » (sans/avec sélection simple/multiple), les trois libellés exacts de confirmation, annulation = aucune mutation, blocage Dataset affiché sans confirmation préalable, rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` existant, non-régression de « Voir en grand » avec une sélection multiple active.
- `test_datasets_page.py`/`test_dataset_roundtrip.py` : exécutés intégralement — **strictement inchangés**, aucune régression détectée.
- **792/792 tests verts** au total (768 précédents + 24 nets nouveaux), suite ciblée `WorkspaceManagerRemoveImagesTest` : 14/14 OK, `test_images_page.py` : 33/33 OK, non-régression Workspace/Dataset/DatasetsPage : 146/146 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — suppression réelle d'un fichier interne confirmée disparue du disque avec le libellé exact « Supprimer », retrait d'un fichier externe confirmé conservé sur disque avec le libellé exact « Retirer », blocage réel observé pour une image référencée par un Dataset puis suppression réussie après retrait de la référence, sélection mixte (1 interne + 1 externe) confirmée avec le libellé « Continuer » et le comptage exact, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 046)

La dette distincte laissée ouverte par Mission 045 (suppression d'une image depuis `ImagesPage`) est désormais **résolue**. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `40feee77150d5f52af00c6011db8630a449fe730` — `feat: add deleting images from the Workspace gallery`, tag `v0.2-mission046`, GitHub Release publiée).

---

## v0.2-mission045 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 045 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 045)

**Mission 045 — Remove Images from a Dataset.** Referme la dette identifiée en retour par Mission 044 : seule la suppression d'un Dataset entier existait (`delete_dataset()`), sans moyen de corriger une erreur d'ajout individuelle — devenu plus visible depuis Mission 044, qui permet à un Dataset de référencer directement une image du Workspace sans copie physique.

`DatasetsPage` gagne un bouton « Retirer du dataset », à côté de « Voir en grand », `images_list` passant en sélection étendue (`ExtendedSelection`) pour permettre un retrait multiple en une seule opération. Nouvelle primitive `DatasetManager.remove_images(paths)`, symétrique à `add_images()` (même convention de comparaison de chemins résolus, sauvegarde uniquement si une mutation réelle a eu lieu, aucun événement dédié publié).

Le retrait ne mute **que** la référence du Dataset actif : le fichier physique n'est jamais supprimé, `Workspace.images` reste inchangé, et tout autre Dataset référençant le même fichier (chaque Dataset possédant son propre pool `Image` indépendant, Mission 011) reste intact. Aucun nouveau wiring EventBus : le chemin `WORKSPACE_SAVED` déjà existant suffit. `ImagesPage` et le Domain restent strictement inchangés. La suppression d'une image depuis `ImagesPage` (retrait de `Workspace.images` et/ou suppression physique) reste une dette **distincte, entièrement ouverte**, non traitée par cette mission.

### Tests ajoutés (Mission 045)

- `test_datasets_page.py` (10 tests nets nouveaux) — sélection étendue, état du bouton « Retirer du dataset » (sans/avec sélection simple/multiple), retrait d'une image et de plusieurs en une opération, no-op sans sélection, retrait de la dernière image, rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` existant, non-régression de « Voir en grand » avec une sélection multiple active.
- Nouvelle classe `DatasetManagerRemoveImagesTest` dans `test_dataset_roundtrip.py` (8 tests) — retrait simple/multiple, chemin inconnu, sans Dataset actif, fichier physique jamais touché, `Workspace.images` jamais touché, sauvegarde déclenchée uniquement si mutation réelle, et la **propriété déterminante de référence partagée entre deux Datasets**.
- `test_dataset_roundtrip.py` (1 test net nouveau) — cycle complet réel confirmant que cette propriété de référence partagée survit à une fermeture/réouverture réelle du Workspace.
- `test_images_page.py` : exécuté intégralement — **strictement inchangé**, aucune régression détectée.
- **768/768 tests verts** au total (749 précédents + 19 nets nouveaux), suite ciblée `test_datasets_page.py` : 30/30 OK, `test_dataset_roundtrip.py` : 36/36 OK, `test_images_page.py` : 23/23 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — deux Datasets partageant la même image, sélection réelle et clic réel sur « Retirer du dataset », retrait observé uniquement dans le Dataset visé, second Dataset et `Workspace.images` intacts, fichier physique intact, retrait multiple réel confirmé, persistance de la propriété confirmée après fermeture/réouverture réelle.

### État du projet (Mission 045)

La dette identifiée en retour par Mission 044 (retrait d'une image d'un Dataset) est désormais **résolue**. La suppression d'une image depuis `ImagesPage` (retrait de `Workspace.images` et/ou suppression physique du fichier) reste explicitement hors périmètre et non traitée — dette distincte nécessitant son propre audit dédié. Aucun autre nouveau besoin n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `b83c4eb0ac1e582718afd73915b519e131c7dffe` — `feat: add removing images from a Dataset`, tag `v0.2-mission045`, GitHub Release publiée).

---

## v0.2-mission044 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 044 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 044)

**Mission 044 — Feed a Dataset from the Images Gallery.** Referme la dette UX documentée depuis Mission 028 : le seul moyen d'alimenter un Dataset était de réimporter une image depuis le disque via `QFileDialog`, même lorsqu'elle était déjà présente dans la galerie `Images` du Workspace.

`DatasetsPage` gagne un nouveau bouton « Ajouter depuis Images… », à côté de « Importer des images » existant, ouvrant un nouveau dialogue dédié `SelectImagesDialog` (galerie de miniatures multi-sélectionnable des images de `Workspace.images`, réutilisant le helper `load_thumbnail_icon()` introduit par Mission 042). La sélection est ajoutée au Dataset **actuellement actif** via `DatasetManager.add_images()`, strictement inchangé — aucune nouvelle logique de déduplication ni de copie n'a été ajoutée en Presentation.

Une image déjà interne au Workspace n'est **jamais physiquement dupliquée** : `WorkspaceStorage.copy_into_workspace()` (Mission 028) reconnaissait déjà ce cas et réutilise le fichier tel quel. Une image déjà présente dans le Dataset actif est silencieusement ignorée par le même mécanisme de déduplication déjà existant. Aucun nouveau wiring EventBus n'a été nécessaire : le chemin `WORKSPACE_SAVED` déjà utilisé pour rafraîchir `DatasetsPage` s'est révélé suffisant. `ImagesPage`, le Domain, `DatasetManager`, `WorkspaceManager` et l'EventBus restent tous strictement inchangés — l'action est intégralement hébergée dans `DatasetsPage`, qui possédait déjà les deux dépendances nécessaires.

### Tests ajoutés (Mission 044)

- Nouveau fichier `tests/integration/test_select_images_dialog.py` (7 tests) — mode galerie, sélection multiple activée, métadonnées par image (icône/texte/tooltip/`Qt.UserRole`), sélection vide/simple/multiple, galerie vide.
- `test_datasets_page.py` (8 tests nets nouveaux) — garde « aucun dataset actif », garde « galerie Images vide », dialogue peuplé des images réelles du Workspace, annulation, ajout d'une image et de plusieurs images sans nouveau fichier sur disque, doublon ignoré sans duplication, rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` existant.
- `test_dataset_roundtrip.py` (1 test net nouveau) — cycle complet réel : ajout depuis la galerie, sauvegarde, fermeture, réouverture — persistance confirmée et absence de copie physique vérifiée explicitement.
- `test_images_page.py` : exécuté intégralement — **strictement inchangé**, aucune régression détectée.
- **749/749 tests verts** au total (733 précédents + 16 nets nouveaux), suite ciblée `test_select_images_dialog.py` : 7/7 OK, `test_datasets_page.py` : 20/20 OK, `test_dataset_roundtrip.py` : 27/27 OK, `test_images_page.py` : 23/23 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — sélection réelle (clic + Ctrl-clic) et clic réel sur le bouton OK du dialogue, ajout de 2 images observé, galerie Dataset rafraîchie sans appel manuel, aucun dossier `datasets/<dataset_id>/` créé à aucune étape, doublon correctement ignoré, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 044)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'alimentation d'un Dataset depuis la galerie Images est désormais **résolue**. La suppression avancée d'images, le tri de la galerie Images et la portabilité des chemins restent explicitement hors périmètre et non traités. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `542e0fef67a426f800220a2a5e43f25ecce57e5b` — `feat: add feeding a Dataset from the Images gallery`, tag `v0.2-mission044`, GitHub Release publiée).

---

## v0.2-mission043 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 043 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 043)

**Mission 043 — Dashboard Training Indicator.** Referme la dette UX documentée depuis Mission 029 : `DashboardPage.trainingCard` affichait en permanence le texte figé `"Idle"`, jamais mis à jour par `update_project()` et jamais réinitialisé à la fermeture d'un projet — la seule carte du Dashboard qui ne reflétait aucune donnée réelle du Workspace, contrairement à `imagesCard`/`datasetsCard`/`modelsCard`/`lorasCard`.

`trainingCard` affiche désormais le nombre réel de sessions Training enregistrées dans le Workspace, via `sum(len(character.get("trainings") or []) for character in (project.get("characters") or []))` — exactement le même principe d'agrégation déjà utilisé pour `datasetsCard`/`lorasCard` — et se remet explicitement à `"0"` lorsqu'aucun Workspace n'est ouvert. Aucun état d'exécution (`Idle`/`Running`/`Failed`) n'est introduit ni simulé : ce choix est délibéré, aucun moteur d'entraînement réel n'existant à ce jour dans AI Studio Toolkit ; `trainingButton` reste inchangé, visible et désactivé.

Un mini-audit ciblé a confirmé qu'aucun nouveau wiring EventBus n'était nécessaire : `TrainingManager.create()`/`delete()` appellent déjà `WorkspaceManager.save()`, qui publie `WORKSPACE_SAVED`, événement auquel `DashboardPage.update_project()` est déjà abonné — exactement le mécanisme qui fait déjà fonctionner `datasetsCard`/`lorasCard`. Modification strictement confinée à `src/ui/pages/dashboard_page.py` : aucun changement Domain, Manager, EventBus ou persistance.

### Tests ajoutés (Mission 043)

- `test_training_roundtrip.py::test_full_create_select_save_close_reopen_cycle` (existant, étendu) : assertions ajoutées sur `dashboard.trainingCard.value.text()` — `"0"` avant création, `"1"` après création, `"0"` après fermeture du Workspace, `"1"` restauré après réouverture.
- `test_dashboard_training_card_default_value_without_any_workspace` (nouveau) : un `DashboardPage()` fraîchement construit, sans aucun Workspace, affiche `"0"`.
- `test_dashboard_training_card_reflects_multiple_sessions_and_deletion` (nouveau) : création de 2 sessions Training (`"1"` puis `"2"`), suppression des 2 (`"1"` puis `"0"`).
- `test_dashboard_and_images_unaffected_by_training_events` : confirmé non modifié — ses assertions ne portent jamais sur `trainingCard`.
- **733/733 tests verts** au total (731 précédents + 2 nets nouveaux), suite ciblée `test_training_roundtrip.py` : 18/18 OK, non-régression croisée (`test_dashboard_page.py`/`test_workspace_roundtrip.py`/`test_dataset_roundtrip.py`/`test_lora_roundtrip.py`) : 108/108 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — compteur observé à `"0"` (avant Workspace, puis Workspace sans Training), `"1"`/`"2"` (création de sessions), `"1"` (suppression), `"0"` (fermeture), `"1"` restauré (réouverture), non-régression des autres cartes et de `trainingButton` confirmée.

### État du projet (Mission 043)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'indicateur Training figé du Dashboard est désormais **résolue**. La notion d'état d'exécution (`Idle`/`Running`/`Failed`) est explicitement abandonnée tant qu'aucun moteur d'entraînement réel n'existe, plutôt que reportée. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `9eec7c5754faaf8bd077969c4d9580df4d3484b1` — `fix: reflect real Training session count on Dashboard`, tag `v0.2-mission043`, GitHub Release publiée).

---

## v0.2-mission042 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 042 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 042)

**Mission 042 — Dataset Thumbnail Gallery.** Referme la dette UX documentée depuis Mission 028 : `DatasetsPage` affichait le contenu d'un Dataset comme une simple liste de chemins texte, sans aucun aperçu visuel — à la différence d'`ImagesPage`, passée en galerie de miniatures dès Mission 019.

`DatasetsPage.images_list` devient une galerie de miniatures en parité stricte avec `ImagesPage` (`IconMode`, miniatures 128×128, grille 150×170) : chaque image affiche son nom de fichier, conserve son chemin complet en tooltip et dans `Qt.UserRole`, et bénéficie d'un repli robuste vers une icône native d'avertissement pour tout fichier absent, invalide ou non décodable — sans jamais faire planter la galerie. Un aperçu agrandi est désormais disponible via double-clic ou le nouveau bouton « Voir en grand », réutilisant `ImagePreviewDialog` **sans aucune modification**.

La logique de chargement de miniature, jusqu'ici privée à `ImagesPage`, a été extraite dans un helper UI partagé minimal (`src/ui/thumbnails.py`, une seule fonction, aucune classe, aucun nouveau package) — `ImagesPage` migrée vers ce helper sans aucun changement de comportement observable. Aucun changement Domain, Manager ou persistance : cette mission est strictement confinée à la couche Presentation.

### Tests ajoutés (Mission 042)

- Nouveau fichier `tests/integration/test_datasets_page.py` (12 tests, `DatasetsPageGalleryTest`) — mode galerie, image valide (icône/texte/tooltip/`Qt.UserRole`), fichier absent et fichier invalide (tous deux avec repli robuste), plusieurs images avec `Qt.UserRole` distincts, activation/désactivation de « Voir en grand » selon la sélection, ouverture de `ImagePreviewDialog` par bouton et par double-clic, réinitialisation de la sélection au changement/rafraîchissement de Dataset.
- `test_dataset_roundtrip.py` : deux assertions existantes adaptées au nouveau contrat de présentation (`item.text()` = nom de fichier, `Qt.UserRole` = chemin complet), aucun autre changement.
- `test_images_page.py` : exécuté intégralement après la migration vers le helper partagé — **strictement inchangé**, aucune régression détectée.
- **731/731 tests verts** au total (719 précédents + 12 nets nouveaux), aucune régression détectée, suite ciblée `test_datasets_page.py` : 12/12 OK, `test_images_page.py` : 23/23 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — miniature valide et icône de repli natif observées dans la même galerie, nom de fichier lisible, sélection activant correctement « Voir en grand », aperçu ouvert avec succès par le bouton et par le double-clic, réinitialisation confirmée au changement de Dataset.

### État du projet (Mission 042)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'absence de miniatures pour les images d'un Dataset est désormais **résolue**. L'alimentation d'un Dataset depuis la galerie Images, la suppression/gestion avancée des images du Dataset, le tri et le workflow Training restent explicitement hors périmètre et non traités. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `5c13619bcf236fbf8366c74af74ddc207daaeb06` — `feat: add thumbnail gallery to Datasets page`, tag `v0.2-mission042`, GitHub Release publiée).

---
