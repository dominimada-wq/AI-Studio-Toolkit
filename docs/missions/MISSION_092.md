# Mission 092 — Direct Import to the Central LoRA Library (from disk)

> **MISSION IMPLÉMENTÉE ET VALIDÉE PAR L'ARCHITECTE, CLÔTURE GIT EFFECTUÉE.** Voir section 5 pour l'état final.

## 1. Contexte

L'audit post-Mission 091 a confirmé que toute la série de sécurisation transactionnelle Domain → persistence (Missions 066–077) et toutes les dettes dirty-state/UX (038, 078–086, 091) sont closes, et qu'aucune preuve nouvelle ne justifie de rouvrir le harness de test Qt. La zone la plus active du projet reste la bibliothèque LoRA centrale (Missions 087–090) : fondation + import depuis une LoRA Character-scoped (087/088), consultation/suppression (089), édition des métadonnées (090). Les rapports de clôture de Mission 088, 089 **et** 090 listent tous les trois, sans exception, « l'import direct depuis l'onglet Bibliothèque centrale » comme besoin explicitement laissé ouvert — c'est le seul point de cette famille qui ne nécessite aucune décision architecturale préalable (contrairement au modèle de scopes Character/Workspace/Global ou à l'exposition aux moteurs, tous deux volontairement écartés du périmètre de cette mission).

**Situation actuelle** : `LoRAPage.add_to_central_library()` (`src/ui/pages/lora_page.py:654`) est l'unique appelant de `LoRALibraryManager.import_lora()` dans tout le projet — il copie obligatoirement la LoRA Character-scoped actuellement active. Un fichier LoRA destiné dès l'origine à un usage générique (style, skin, réalisme — cas explicitement anticipé par la décision d'architecture de Mission 060 sur les scopes `Global/Shared`, non traitée ici) n'a aujourd'hui aucun moyen d'entrer dans la bibliothèque centrale sans passer par le détour artificiel de le créer d'abord comme LoRA d'un personnage.

## 2. Objectif

Ajouter à l'onglet « Bibliothèque centrale » de `LoRAPage` un second point d'entrée d'import — depuis le disque, sans LoRA Character-scoped préalable — en réutilisant intégralement le pipeline `import_lora()` déjà posé et testé depuis Mission 087. Aucun second pipeline d'import parallèle, aucune ouverture des chantiers scopes/exposition moteurs.

## 3. Contrat verrouillé par le mini-audit

### 3.1 Réutilisation de `LoRALibraryManager.import_lora()` — aucun changement de signature

Lecture directe de `src/managers/lora_library_manager.py:97-202` et de la suite `LoRALibraryManagerImportTest` (`tests/integration/test_lora_library_roundtrip.py:116-336`, 12 tests déjà verts) :

- **Signature actuelle** : `import_lora(name, file_paths, library_root, thumbnail_path=None, engine="", architecture="", trigger_word="", version="")` — **déjà strictement suffisante**, aucune précondition Workspace/Character (confirmé par le docstring : « Never returns None — LoRALibraryManager has no Workspace/Character precondition »). Rien à généraliser.
- **`lora_id`** : toujours un `uuid.uuid4()` frais, jamais dérivé du nom/chemin/contenu — identique quelle que soit la source. Inchangé.
- **Copie des fichiers** : `WorkspaceStorage.copy_into_workspace(source, destination_folder, workspace_root=destination_folder)` — ignore totalement la provenance de `source_path`, fonctionne à l'identique pour un chemin Character-scoped ou un chemin disque arbitraire. `file_paths: List[str]` supporte déjà nativement le multi-fichier (`test_import_multiple_files`) ; une collision de basename entre deux fichiers d'un même import est déjà résolue automatiquement par `copy_into_workspace()` (suffixe `_1`, `test_filename_collision_within_the_same_entry_is_resolved`).
- **Thumbnail** : paramètre optionnel déjà supporté. **Aucune source de thumbnail n'existe dans l'UX d'import direct** (pas de sélecteur d'image à ce stade — voir 3.2) : l'entrée créée aura `thumbnail=""`, exactement le comportement déjà couvert par `test_import_without_thumbnail_leaves_it_empty`. **Gap pré-existant confirmé, non aggravé par M092** : l'onglet central n'a aujourd'hui aucun bouton « Choisir une miniature » (contrairement à l'onglet Personnage) — une entrée sans thumbnail, qu'elle vienne du chemin Character (Mission 088, si la LoRA source n'en avait pas) ou d'un import direct (M092), reste sans miniature tant qu'une future mission n'ajoute pas ce bouton à l'onglet central. **Hors périmètre M092**, non aggravé.
- **Validation de chemins/fichiers** : aucune au niveau Manager au-delà de ce que `copy_into_workspace()` fait déjà (lève `WorkspaceStorageError` sur une source manquante/inaccessible, déjà couvert par `test_partial_copy_failure_leaves_no_entry_and_no_orphaned_folder`). Rien à ajouter.
- **Rollback partiel** : déjà entièrement couvert et testé — échec de copie → nettoyage best-effort du dossier de destination avant `LoRALibraryError` (`test_partial_copy_failure_leaves_no_entry_and_no_orphaned_folder`, `test_partial_copy_failure_cleanup_itself_failing_is_reported_in_the_message`) ; échec de `_save()` après copie réussie → `self._loras.remove(lora)` + nettoyage best-effort du dossier avant `LoRALibraryError` (`test_persistence_failure_after_copy_rolls_back_memory_and_cleans_up_disk`, `test_persistence_failure_cleanup_itself_failing_is_reported_in_the_message`).
- **Événement `LORA_LIBRARY_IMPORTED`** : publié uniquement après succès complet (copie **et** persistance) — dernière instruction de la méthode, inchangée.
- **Rafraîchissement UI** : déjà entièrement câblé (`main_window.py` abonne `LORA_LIBRARY_IMPORTED` à `lora_page.update_central_library`, confirmé par le test `LoRAPageCentralLibraryTabTest.setUp()`). **Point identifié par l'audit, à câbler explicitement côté Presentation** : `update_central_library()` ne présélectionne jamais une entrée qu'il n'a jamais chargée (`preserve_panel` reste `False` pour un `lora_id` totalement nouveau) — la nouvelle entrée apparaîtrait dans la liste mais sans être sélectionnée ni chargée dans le formulaire. Le handler du nouveau bouton doit donc appeler explicitement `self._display_library_entry(nouvelle_lora.lora_id)` après un `import_lora()` réussi — méthode déjà existante (`lora_page.py:1067`), déjà utilisée pour re-sélectionner une entrée par identité après une reconstruction réentrante de liste (branche Save de `on_library_selection_changed()`). Aucune nouvelle méthode nécessaire.

**Conclusion** : `import_lora()` reste **strictement inchangé**. Tout le travail de M092 est côté `LoRAPage` — un nouveau handler qui alimente le même appel `import_lora()` déjà fait par `add_to_central_library()`, à partir de dialogues au lieu d'un objet `LoRA` Character-scoped actif. Ce n'est pas un second pipeline : c'est le même appel, avec une source différente.

### 3.2 UX de l'import direct

- **Bouton** : « Importer depuis le disque… » sur l'onglet « Bibliothèque centrale », placé au-dessus de `library_list` (mirroir de la position d'`import_files_button` sur l'onglet Personnage). **Toujours activé** — aucune précondition (ni entrée active, ni Workspace ouvert), à la différence de `save_library_metadata_button`/`delete_from_library_button` : mirroir de `new_button`/`create_lora()`, qui créent également une entité sans précondition de sélection.
- **Garde dirty-state — point verrouillé par l'audit, absent du contrat initial** : `_display_library_entry()` change la sélection via `setCurrentItem(item, QItemSelectionModel.NoUpdate)` **sous `blockSignals(True)`**, donc **sans jamais déclencher `on_library_selection_changed()`** — son garde `_library_metadata_dirty` habituel serait donc contourné, écrasant silencieusement un brouillon d'édition en cours sur une autre entrée. Le nouveau handler doit reproduire **en tête**, avant même l'ouverture du sélecteur de fichiers, exactement le garde déjà utilisé par `add_to_central_library()` côté Personnage : si `self._library_metadata_dirty`, appeler `_confirm_discard_library_metadata_before_switch()` — Cancel → arrêt complet, aucun dialogue de fichier ouvert ; Save → tenter `lora_library_manager.update(...)` sur l'entrée actuellement chargée, abandon sur `LoRALibraryError` ; Discard → poursuivre sans persister.
- **Sélecteur de fichier** : `QFileDialog.getOpenFileNames()` (multi-sélection, mirroir exact d'`import_files()`).
- **Extensions acceptées** : réutilisation stricte du filtre déjà utilisé par `import_files()` — `"Fichiers LoRA (*.safetensors *.ckpt *.pt *.bin *.json);;Tous les fichiers (*)"`. Aucune extension inventée.
- **Ordre des dialogues** : fichiers d'abord, puis nom — un Cancel au sélecteur de fichiers est un no-op strict avant même qu'un nom soit demandé (évite une saisie inutile en cas d'abandon précoce).
- **Initialisation du `name`** : `QInputDialog.getText(self, "Importer dans la bibliothèque centrale", "Nom :")`, mirroir exact de `create_lora()` — `if not ok or not name.strip(): return` (no-op strict).
- **`engine`/`architecture`/`trigger_word`/`version`** : `""` chacun (défauts du dataclass `LoRA`), jamais déduits du fichier — immédiatement complétables via le formulaire d'édition M090 déjà existant, qui se charge automatiquement grâce à `_display_library_entry()`. Confirme qu'aucune UX de saisie de métadonnées supplémentaire n'est nécessaire à l'import.
- **Après import réussi** : `self._display_library_entry(lora.lora_id)` — sélectionne la ligne, charge nom/métadonnées/thumbnail (vide) dans le formulaire, active `delete_from_library_button`. **Aucune boîte de confirmation de succès** : convention déjà établie par ce même onglet — ni `save_library_metadata()` ni `delete_from_library()` (hors avertissement de nettoyage partiel) n'affichent de confirmation de succès ; le retour visuel (nouvelle ligne, sélectionnée, formulaire chargé) suffit. Diverge délibérément d'`add_to_central_library()` (qui affiche « Ajout terminé ») — ce bouton-là confirme qu'une action a quitté l'onglet Personnage vers un autre onglet, besoin psychologique différent, absent ici puisque tout se passe dans le même onglet sous les yeux de l'utilisateur.
- **Erreurs** : uniquement `QMessageBox.critical()` sur `LoRALibraryError` (échec de copie ou de persistance), mirroir exact du wording déjà utilisé par `delete_from_library()`/`save_library_metadata()`.

### 3.3 Identité et doublons

Confirmé par lecture directe et par les tests déjà existants (`test_two_imports_of_the_same_source_produce_two_distinct_entries_and_copies`) : **deux imports du même fichier sont déjà explicitement autorisés et documentés** depuis Mission 087 (« Two imports of the same source file produce two independent LoRA entries with two independent physical copies — no hash-based deduplication in Mission 087 »). Aucune détection de doublon n'existe à aucune couche (Manager, Storage, UI). Ce comportement est **inchangé par la source de l'import** (copie depuis Character vs. disque direct) — M092 ne fait qu'ajouter un second appelant au même contrat déjà en production depuis 3 missions sans qu'aucun problème n'ait jamais été signalé. **Décision** : aucune notion d'identité globale, aucun hashing, aucune garde anti-collision de nom n'est introduite par M092 — conformément à l'instruction explicite de ne pas ajouter de déduplication sans nécessité démontrée.

### 3.4 Garanties transactionnelles

Toutes déjà couvertes et testées au niveau Manager (section 3.1) — aucune n'est affaiblie, aucune n'a besoin d'être réimplémentée :
- Aucune entrée de registre persistée si la copie échoue — `test_partial_copy_failure_leaves_no_entry_and_no_orphaned_folder`.
- Aucun dossier central partiellement abandonné après échec — même test, plus `test_partial_copy_failure_cleanup_itself_failing_is_reported_in_the_message`.
- Rollback/cleanup correct si la persistance échoue après copie — `test_persistence_failure_after_copy_rolls_back_memory_and_cleans_up_disk`.
- `LORA_LIBRARY_IMPORTED` publié uniquement après réussite complète — inchangé, dernière instruction de `import_lora()`.
- Aucune modification de `Character.loras`/`project.json` — confirmé : `import_lora()`/`LoRALibraryManager` n'importent ni ne référencent jamais `LoRAManager`/`WorkspaceManager`/`CharacterManager`.
- Aucune dépendance à un Workspace ouvert — confirmé par lecture complète de tous les handlers de l'onglet central existants (`add_to_central_library()` mis à part, qui lit une LoRA Character-scoped par nécessité propre à *son* chemin) : aucun ne référence `self.workspace_manager`.

### 3.5 Hors périmètre (confirmé par l'audit, aucune preuve contraire trouvée)

- Scopes/associations Character / Workspace / Global.
- Liaison d'une entrée centrale à un Character.
- Exposition/mapping de la bibliothèque vers ComfyUI, Forge, Fooocus, Automatic1111 ou cloud.
- Import automatique depuis les dossiers des moteurs.
- Téléchargement de LoRA depuis Internet.
- Lecture automatique des métadonnées internes `.safetensors`.
- Migration de `project.json`.
- Déduplication par hash ou toute nouvelle notion d'identité globale (voir 3.3).
- Refonte générale de la bibliothèque centrale.
- Ajout d'un sélecteur de thumbnail à l'onglet central (gap pré-existant confirmé en 3.1, non traité ici, non aggravé).

**Aucune décision architecturale plus importante que prévu n'a été révélée par ce mini-audit** — le contrat reste exactement ce qui était anticipé : un second point d'entrée UI vers un pipeline déjà entièrement construit, testé et transactionnellement sûr depuis Mission 087.

## 4. Tests attendus

- **`LoRAPageCentralLibraryTabTest`** (extension, `test_lora_roundtrip.py`) : import direct réussi (fichier réellement copié sous `<library_root>/<lora_id>/`, nouvelle entrée avec un nouvel `lora_id`, aucune mutation de `LoRAManager`/`Character.loras`) ; événement `LORA_LIBRARY_IMPORTED` reçu et `update_central_library()` déclenché correctement ; nouvelle entrée sélectionnée et formulaire correctement chargé après import (`_display_library_entry`) ; échec de copie (`LoRALibraryError` → `QMessageBox.critical`, aucune entrée créée) ; échec de persistance après copie (rollback + message) ; Cancel du sélecteur de fichiers → no-op strict (aucun dialogue de nom, aucun appel `import_lora()`) ; Cancel/nom vide au `QInputDialog` → no-op strict ; garde dirty-state déclenchée avant l'ouverture du sélecteur de fichiers si `_library_metadata_dirty` (Cancel/Save/Discard, les 3 branches) ; second import du même fichier → deux entrées distinctes (confirme le contrat 3.3 côté UI).
- **Non-régression** : `test_lora_roundtrip.py` (chemin Character-scoped inchangé), `test_lora_library_roundtrip.py` (aucune régression Manager, signature inchangée), suite complète `LoRAPageCentralLibraryTabTest` existante (consultation/édition/suppression M089/M090 non affectées).
- **Smoke test Qt réel** (exécuté par Claude, conformément à la règle habituelle) : bouton → `QFileDialog` réel → sélection réelle de fichier(s) → `QInputDialog` réel → nouvelle ligne réelle dans `library_list` → entrée réellement sélectionnée → formulaire réellement chargé → édition/enregistrement immédiat des métadonnées fonctionnel → suppression fonctionnelle. Grâce à Mission 091, le filet de sécurité Qt (`tests/integration/_qt_dialog_safety_net.py`) garantit qu'aucune `QMessageBox` réelle non mockée ne peut bloquer silencieusement l'exécution — aucune intervention humaine attendue pendant les tests automatisés.

## 5. État d'avancement

- Mini-audit ciblé : **terminé**, contrat verrouillé ci-dessus.
- Implémentation : **terminée**, strictement conforme au contrat — zéro changement Manager/Storage, garde dirty-state évaluée avant le sélecteur de fichiers comme verrouillé en section 3.2.
- Tests ciblés (`LoRAPageCentralLibraryTabTest`) : **54/54 OK** (41 préexistants + 13 nets nouveaux).
- Non-régression LoRA complète (`test_lora_roundtrip.py` + `test_lora_library_roundtrip.py`) : **292/292 OK**.
- Smoke test Qt réel (clics réels sur les vrais widgets, filet Mission 091 armé) : **19/19 assertions PASS**, 4 scénarios (import réussi, Cancel du sélecteur, garde dirty Cancel, garde dirty Save).
- Deux full suites consécutives : **1715/1715 OK** chacune (354s puis 204s).
- **Incident résolu avant clôture** : l'architecte a signalé avoir vu apparaître une vraie `QMessageBox` « Génération en attente » pendant une exécution antérieure de la suite. Analyse complémentaire dédiée (lecture exhaustive des 35 occurrences pertinentes de `confirm_pending_result_change()`/`_confirm_pending_before_switch()` dans les 4 fichiers concernés — toutes mockent la construction même du dialogue ; aucun fichier lié à ce guard modifié par M092) plus une **troisième full suite, surveillée empiriquement en temps réel** (`tasklist /v` interrogé toutes les 3 s pendant toute l'exécution) : **1715/1715 OK**, aucune occurrence de « Génération en attente » captée. Incident jugé non reproductible et non attribuable à M092 par l'architecte — la couverture partielle du filet Mission 091 (limitée à 4 classes de test, non globale) est actée comme dette potentielle future, hors périmètre de cette mission.
- `git diff --check` : propre.
- Périmètre respecté à la lettre : uniquement `src/ui/pages/lora_page.py`, `tests/integration/test_lora_roundtrip.py`, ce document.
- Commit de mission : `25e313301fbe1f78eeb37f38cdb024672b819785` — "Add direct import to the central LoRA library from disk", poussé sur `main`.
- Tag annoté : `v0.2-mission092`, ciblant exactement le commit de mission ci-dessus, poussé.
- GitHub Release : titre et Release Notes préparés, publication manuelle par l'architecte à venir (`gh` indisponible dans cet environnement).
