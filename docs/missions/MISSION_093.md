# Mission 093 — Central LoRA Library Thumbnail Selector

> **MISSION IMPLÉMENTÉE ET VALIDÉE PAR L'ARCHITECTE, CLÔTURE GIT EFFECTUÉE.** Voir section 5 pour l'état final.

## 1. Contexte

L'audit post-Mission 092, assisté par Graphify (première utilisation de l'outil sur ce projet) puis vérifié directement en source, a confirmé une asymétrie UX concrète et documentée à trois reprises sans jamais être traitée : l'onglet « Bibliothèque centrale » de `LoRAPage` n'offre **aucun moyen de définir ou remplacer une miniature** — ni bouton, ni méthode Manager — alors que l'onglet « Personnage » dispose de ce mécanisme depuis la Mission 047 (avec nettoyage automatique de l'ancienne miniature depuis la Mission 080).

**Preuves directes** (vérifiées en source, indépendamment de Graphify) :
- `src/ui/pages/lora_page.py` : l'onglet central ne possède que `library_thumbnail_label` (affichage passif, `_render_thumbnail_preview()`) — aucun `choose_thumbnail_button` équivalent.
- `src/managers/lora_library_manager.py` : seules `import_lora()` (thumbnail optionnel à l'import uniquement) et `update()` (texte seul) existent — **aucun `set_thumbnail()`**.
- `tests/integration/test_lora_roundtrip.py` : les 3 seuls tests thumbnail de l'onglet central (`test_thumbnail_displayed_when_present`, `test_no_thumbnail_shows_placeholder_message`, `test_thumbnail_with_missing_file_shows_unavailable_without_crash`) sont exclusivement des tests d'affichage — zéro test de mutation.
- Ce gap est explicitement noté comme « pré-existant, non traité, non aggravé » dans les mini-audits des Missions 088, 090 et 092 sans jamais être résolu.

Ce choix ferme cette asymétrie sans engager aucune décision architecturale plus large (scopes Character/Workspace/Global, exposition aux moteurs) — périmètre strictement UI + Manager, réutilisant deux contrats déjà éprouvés (Missions 047/067/080).

## 2. Objectif

Ajouter à l'onglet « Bibliothèque centrale » de `LoRAPage` un bouton « Choisir une miniature… » agissant sur l'entrée actuellement sélectionnée, et la méthode `LoRALibraryManager.set_thumbnail()` correspondante — mirroir transactionnel exact de `LoRAManager.set_thumbnail()` (Missions 047/067/080), adapté aux conventions propres de `LoRALibraryManager` (paramètre `library_root` explicite, échecs réels toujours levés via `LoRALibraryError`, jamais un simple retour `None`).

## 3. Contrat verrouillé par le mini-audit

### 3.1 Contrat Manager — `LoRALibraryManager.set_thumbnail()`

**Signature** : `set_thumbnail(self, lora_id: str, source_path: str, library_root) -> Optional[LoRALibraryThumbnailResult]`.

**Point de transposition critique identifié par l'audit** : `LoRAManager.set_thumbnail()` retourne `None` de façon uniforme pour DEUX cas distincts — `lora_id` inconnu ET échec de copie — sans jamais lever d'exception pour un échec de copie. Ce n'est **pas** le contrat propre à `LoRALibraryManager` : `import_lora()`/`update()`/`delete()` y suivent tous la même règle, explicitement documentée dans `import_lora()` — « Never returns None ... Any real failure raises LoRALibraryError » — où `None`/`False`/`deleted=False` signifient exclusivement « rien ne s'est passé » (entrée inconnue), jamais « un vrai échec a eu lieu ». **Décision retenue : transposer le contrat propre à `LoRALibraryManager`, pas celui de `LoRAManager`** :
- `lora_id` inconnu → `return None` (rien ne s'est passé, cohérent avec `get()`/`update()`/`delete()` pour une entrée inconnue).
- Échec de copie (`WorkspaceStorageError`) → **lève `LoRALibraryError`** (échec réel), pas un retour `None` silencieux.
- Échec de persistance après copie réussie → rollback puis **lève `LoRALibraryError`** (déjà le contrat commun à `import_lora()`/`update()`/`delete()`).
- Succès → retourne un nouveau `LoRALibraryThumbnailResult` (dupliqué, jamais partagé avec `LoRAThumbnailResult` de `LoRAManager` — même principe déjà énoncé par `LoRALibraryDeletionResult` : « Duplicated rather than shared, per this codebase's existing convention for these small per-Manager result types »).

**Emplacement de copie** : `destination_folder = Path(library_root) / lora_id` — identique au calcul déjà utilisé par `import_lora()`/`delete()`, jamais un sous-dossier `models/loras/` (convention propre à `LoRAManager`, sans rapport ici).

**Copie** : `WorkspaceStorage.copy_into_workspace(Path(source_path), destination_folder, workspace_root=destination_folder)` — **`workspace_root` doit rester `destination_folder`** (le dossier propre de CETTE entrée), jamais le `library_root` plus large. C'est le même choix déjà fait par `import_lora()`, et il garantit une propriété structurellement non ambiguë : si une source est déjà interne à une AUTRE entrée de la bibliothèque, `is_inside(source, destination_folder)` renvoie `False` pour ce dossier-ci, donc une vraie copie indépendante est créée — jamais un passthrough accidentel vers le fichier d'une autre entrée.

**Nommage** : délégué intégralement à `copy_into_workspace()` (résolution de collision par suffixe numérique déjà éprouvée, Mission 087) — aucune logique de nommage ajoutée ici.

**Valeur persistée** : `lora.thumbnail = str(effective_path)`, champ déjà existant sur le dataclass `LoRA`.

**Aucune miniature préalable** : `old_thumbnail = lora.thumbnail` vaut `""` (défaut du dataclass) → le garde `if old_thumbnail and ...` déjà présent dans `LoRAManager.set_thumbnail()` saute le nettoyage — transposition directe, sans changement.

**Ancienne miniature déjà possédée par le dossier de cette entrée** : `WorkspaceStorage.is_inside(old_thumbnail, destination_folder)` → `True` → suppression best-effort (`FileNotFoundError` ignorée, autre `OSError` → `cleanup_failed=True`/`residual_path`).

**Ancien `thumbnail_path` externe/passthrough** : **constaté structurellement impossible en pratique aujourd'hui** pour la bibliothèque centrale — contrairement à `LoRAManager` (où `copy_into_workspace()` peut légitimement laisser `lora.thumbnail` pointer n'importe où sous `workspace_root`, y compris le dossier d'une AUTRE LoRA), tous les chemins d'écriture actuels de `LoRALibraryManager` (`import_lora()`, et ce nouveau `set_thumbnail()`) utilisent `workspace_root=destination_folder` — le dossier propre de l'entrée elle-même. Le garde `is_inside()` est néanmoins **conservé intégralement, sans condition**, en pure défense en profondeur (coût négligeable, protection contre un futur chemin d'écriture qui ne respecterait pas cet invariant) — exactement le principe de sécurité de la Mission 080, jamais retiré même quand une preuve actuelle suggère qu'il ne se déclenchera jamais côté « externe ».

**Rollback si la copie échoue** : rien n'est encore muté (`lora.thumbnail` intact) ; `copy_into_workspace()` nettoie déjà lui-même tout fichier de destination partiel en cas d'échec (Mission 028, `test_copy_failure_cleans_up_partial_destination_file`) — aucun nettoyage de dossier supplémentaire n'est nécessaire côté Manager, contrairement à `import_lora()` (qui gère un import multi-fichiers).

**Rollback si la persistance échoue après copie** : `lora.thumbnail` restauré à `old_thumbnail` ; si un nouveau fichier a réellement été copié (`is_new_copy`, calculé par comparaison de chemins résolus normalisés — identique à `LoRAManager.set_thumbnail()`), il est supprimé au mieux ; un double échec (persistance + nettoyage) est rapporté dans le message `LoRALibraryError` enrichi, jamais masqué.

**Absence de suppression d'un fichier externe** : garantie par le garde `is_inside()` ci-dessus, jamais contourné.

**Événement** : `LORA_LIBRARY_UPDATED` (voir §3.2), publié en toute dernière instruction, uniquement après persistance réussie.

**Nécessite** un nouvel `import os` en tête de `lora_library_manager.py` (absent aujourd'hui, requis pour `os.path.normcase()`).

### 3.2 Événement — réutilisation de `LORA_LIBRARY_UPDATED`, aucun nouvel événement

Audit direct (`grep` sur `src/`) : `LORA_LIBRARY_UPDATED` n'a **qu'un seul consommateur** dans tout le projet — `LoRAPage.update_central_library()`, câblé dans `main_window.py:330`. Sa propre docstring confirme qu'il **ignore systématiquement le payload de l'événement** et relit toujours `list_loras()` en intégralité (« always re-reads LoRALibraryManager.list_loras() in full, ignoring the event's own single-entry payload »). Un changement de miniature est une mutation de l'entrée centrale au même titre qu'un changement de texte — **décision confirmée : réutiliser `LORA_LIBRARY_UPDATED` tel quel, payload `lora.to_dict()` inchangé, aucun nouvel événement créé.** Publication uniquement après succès complet (copie + persistance), dernière instruction de la méthode — identique au contrat déjà en vigueur pour `update()`.

### 3.3 Dirty-state — point verrouillé par l'audit, **contrainte réelle non anticipée dans la proposition initiale**

L'audit a lu le corps exact de `update_central_library()` et découvert une contrainte fonctionnelle concrète, pas seulement une question de style :

```python
still_exists = any(lora.lora_id == self._loaded_library_lora_id for lora in loras)
preserve_panel = self._library_metadata_dirty and still_exists
...
if preserve_panel:
    ...
    return
# sinon : panneau totalement réinitialisé (_loaded_library_lora_id = None, _load_library_details(None))
```

Deux échecs concrets si le nouveau handler se contentait de publier `LORA_LIBRARY_UPDATED` et de compter sur ce rafraîchissement passif (comme le fait `save_library_metadata()` pour le texte) :

1. **Si `_library_metadata_dirty` est `False`** au moment du clic (aucun brouillon texte en cours) : `preserve_panel` vaut `False` → le panneau entier est réinitialisé (`_load_library_details(None)`), la sélection est perdue — l'utilisateur ne verrait **pas** sa nouvelle miniature mais un panneau vide.
2. **Si `_library_metadata_dirty` est `True`** sur la même entrée : `preserve_panel` vaut `True` → le panneau est **préservé tel quel, jamais rechargé** — la miniature affichée resterait l'ancienne, alors que `lora.thumbnail` a déjà changé en mémoire.

Dans les deux cas, l'exigence « aperçu central mis à jour immédiatement » (§4) est violée par un simple rafraîchissement passif. **Contrat retenu, combinant les deux mécanismes déjà éprouvés séparément ailleurs dans ce fichier :**
1. **Avant même l'ouverture du sélecteur de fichiers**, évaluer le garde dirty-state déjà utilisé par `import_to_library_from_disk()` (Cancel → arrêt complet ; Save → persister le brouillon texte via `update()`, abandon sur `LoRALibraryError` ; Discard → poursuivre sans persister) — ce garde ramène `_library_metadata_dirty` à `False` avant que `set_thumbnail()` ne s'exécute, dans tous les cas.
2. **Après un `set_thumbnail()` réussi**, appeler explicitement `self._display_library_entry(lora_id)` — exactement le mécanisme déjà utilisé par `import_to_library_from_disk()` pour forcer un rechargement correct et immédiat, plutôt que de compter sur le rafraîchissement passif d'`update_central_library()`.

Le garde de l'étape 1 est ce qui rend l'étape 2 sûre : `_display_library_entry()` réinitialise inconditionnellement les 5 champs texte et `_library_metadata_dirty` — sans le garde préalable, un brouillon texte non enregistré serait silencieusement détruit par cet appel. **Aucun brouillon utilisateur ne peut donc être perdu** : soit il a été résolu (Save/Discard) avant que la mutation de miniature ne s'exécute, soit l'action entière est annulée (Cancel) avant que rien ne soit modifié.

### 3.4 UX

- **Bouton** : « Choisir une miniature… », placé juste après `library_thumbnail_label` et avant `save_library_metadata_button` (regroupe l'action avec l'affichage qu'elle modifie, cohérent avec la disposition en colonne déjà établie de cet onglet : import → liste → formulaire → miniature → **[nouveau bouton]** → enregistrer → supprimer).
- **État activé/désactivé** : mirroir exact de `delete_from_library_button` (activé dès qu'une entrée est sélectionnée/chargée, désactivé sinon) — **pas** le garde plus strict de `save_library_metadata_button` (qui exige un changement réel), puisque changer la miniature n'a aucune précondition de brouillon préexistant. Basculé aux mêmes 3 emplacements que `delete_from_library_button.setEnabled(...)` : les deux branches d'`on_library_selection_changed()` et `_display_library_entry()`.
- **Sans entrée sélectionnée** : le bouton étant désactivé, ce cas n'est normalement pas atteignable par un clic réel ; garde défensive minimale `if item is None: return` dans le handler, **sans boîte de dialogue** — c'est la convention déjà établie de CET onglet (`save_library_metadata()`/`delete_from_library()` font un no-op silencieux sur absence de sélection), délibérément différente de la boîte d'avertissement qu'affiche `choose_thumbnail()` côté Personnage (convention propre à cet autre onglet, non reproduite ici).
- **Filtre `QFileDialog`** : `"Images (*.png *.jpg *.jpeg *.webp *.bmp)"` — identique caractère pour caractère au filtre déjà utilisé par `choose_thumbnail()` (Personnage), aucune extension inventée.
- **Cancel du sélecteur** : `if not file_path: return` — no-op strict, aucun appel Manager, aucune mutation.
- **Après succès** : `self._display_library_entry(lora_id)` — sélection réaffirmée, formulaire texte rechargé (déjà cohérent puisque §3.3 garantit qu'aucun brouillon n'était en jeu), aperçu de la nouvelle miniature affiché immédiatement.
- **Aucune boîte de confirmation de succès** : convention déjà établie par cet onglet (ni `save_library_metadata()` ni `delete_from_library()` — hors avertissement de nettoyage partiel — n'affichent de confirmation de réussite) ; le retour visuel (aperçu mis à jour) suffit.
- **Erreurs** : `QMessageBox.critical()` sur `LoRALibraryError` (échec de copie ou de persistance), mirroir du wording déjà utilisé par `choose_thumbnail()`/`delete_from_library()` ; `QMessageBox.warning()` non bloquant sur `result.cleanup_failed` (nettoyage partiel de l'ancienne miniature), mirroir exact de `choose_thumbnail()`.

### 3.5 Hors périmètre

Confirmé par l'audit, aucune preuve contraire trouvée :
- Modification de `import_lora()`.
- Modèle de scopes Character/Workspace/Global.
- Exposition de la bibliothèque aux moteurs.
- Migration de `project.json`.
- Déduplication par hash.
- Import automatique de thumbnail depuis les métadonnées internes `.safetensors`.
- Éditeur/cropper d'image.
- Multi-référence pour Inference.
- Dette `_pump(seconds)` / couverture partielle du filet de sécurité Mission 091.

**Aucune décision architecturale plus importante que prévu n'a été révélée par ce mini-audit** — le seul point non anticipé par la proposition initiale (le garde dirty-state avant ET après la mutation, §3.3) est une contrainte fonctionnelle locale à cet onglet, déjà résolue avec des mécanismes qui existent déjà dans ce même fichier — pas une nouvelle décision d'architecte.

## 4. Tests attendus

- **`LoRALibraryManagerSetThumbnailTest`** (nouvelle classe, `test_lora_library_roundtrip.py`, mirroir de `LoRAManagerThumbnailCleanupTest`/`LoRAManagerMetadataTest`) : première miniature ajoutée avec succès (copie réelle vérifiée sous `<library_root>/<lora_id>/`, `thumbnail_path` correct) ; remplacement d'une miniature déjà possédée par l'entrée (ancienne supprimée après succès) ; ancien `thumbnail_path` externe jamais supprimé (scénario construit artificiellement pour vérifier le garde `is_inside()`, même s'il est structurellement inatteignable via les chemins d'écriture actuels) ; échec de copie → `LoRALibraryError`, aucune mutation, `lora.thumbnail` inchangé ; échec de persistance après copie → rollback mémoire complet + nettoyage best-effort du nouveau fichier, message enrichi si le nettoyage échoue aussi ; `lora_id` inconnu → `None`, aucun effet ; `LORA_LIBRARY_UPDATED` publié uniquement après réussite complète, jamais sur un échec.
- **`LoRAPageCentralLibraryTabTest`** (extension) : Cancel du sélecteur de fichiers → no-op strict ; bouton désactivé sans sélection, activé dès sélection ; après succès → aperçu central rafraîchi immédiatement (assertion directe sur `library_thumbnail_label.pixmap()`) ; brouillon texte dirty sur la même entrée → garde Cancel/Save/Discard déclenché avant l'ouverture du sélecteur, les 3 branches ; échec de copie/persistance → message d'erreur, aucune mutation visible ; non-régression complète de la consultation/édition/suppression/import direct (Missions 089-092).
- **Non-régression** : suite ciblée `LoRAPageCentralLibraryTabTest` + `LoRALibraryManagerImportTest`/`UpdateTest`/`DeleteTest`/`ListGetTest`, suite complète `test_lora_roundtrip.py` + `test_lora_library_roundtrip.py`.
- **Smoke test Qt réel** : sélection d'une entrée → clic « Choisir une miniature… » → `QFileDialog` réel → copie réelle sur disque → événement `LORA_LIBRARY_UPDATED` reçu → aperçu affiché → remplacement par une seconde miniature → ancienne miniature correctement nettoyée (fichier vérifié absent) → nouvelle miniature affichée. Grâce à la Mission 091, aucune intervention humaine attendue.

## 5. État d'avancement

- Mini-audit ciblé : **terminé**, contrat verrouillé ci-dessus.
- Implémentation : **terminée**, strictement conforme au contrat — `LoRALibraryManager.set_thumbnail()` + `LoRALibraryThumbnailResult`, bouton « Choisir une miniature… » sur l'onglet central, garde dirty-state avant le sélecteur, `_display_library_entry()` explicite après succès.
- **Tests ciblés Manager** (`LoRALibraryManagerSetThumbnailTest`, `test_lora_library_roundtrip.py`) : **9/9 OK** (nets nouveaux).
- **Tests ciblés UI** (`LoRAPageCentralLibraryTabTest`, `test_lora_roundtrip.py`) : **67/67 OK** (54 préexistants + 13 nets nouveaux).
- **Non-régression LoRA complète** (`test_lora_roundtrip.py` + `test_lora_library_roundtrip.py`) : **314/314 OK** (292 préexistants + 22 nets nouveaux).
- **Smoke test Qt réel** (clics réels sur les vrais widgets, filet Mission 091 armé) : **22/22 assertions PASS**, 4 scénarios (première miniature, Cancel du sélecteur, garde dirty Cancel, garde dirty Save puis remplacement réel).
- **Full suite finale** : **1737/1737 OK** (1715 préexistants + 22 nets nouveaux). Exécutée avec une instrumentation temporaire dédiée, non committée, jamais destinée à devenir permanente — un patch direct sur `QMessageBox.exec()` qui neutralise automatiquement (clic « Annuler » sur le vrai bouton) toute occurrence réelle d'une boîte, en distinguant explicitement les occurrences déjà diagnostiquées de la dette de cleanup Mission 084 de toute boîte véritablement inattendue. Résultat de cette exécution instrumentée : **5 occurrences connues du défaut de cleanup Mission 084 interceptées et neutralisées automatiquement** (toutes dans `MainWindowInferencePendingResultGuardTest`/`MainWindowRenamePendingResultGuardTest`, aucune dans un fichier modifié par M093 — voir « Incident et diagnostic complémentaire » ci-dessous), **0 QMessageBox inattendue**, **0 intervention humaine pendant cette exécution**, **1 seul thread vivant en fin d'exécution** (`MainThread`), aucun processus Python résiduel confirmé par `tasklist` juste après. Cette validation ne doit **pas** être présentée comme « 1737/1737 sans aucun dialogue » : cinq tentatives réelles de dialogue ont bien eu lieu, ont été détectées avec preuve (stack + test responsable), et neutralisées automatiquement — elles sont indépendantes de M093. L'instrumentation et ses logs ont été intégralement supprimés avant la clôture ; aucun fichier de production n'a été modifié pour cette validation.
- **Incident et diagnostic complémentaire (hors périmètre fonctionnel M093)** : pendant la validation, l'architecte a observé à l'écran une réapparition de la boîte réelle « Génération en attente » (2ᵉ occurrence après celle de Mission 092), nécessitant une intervention manuelle. Un diagnostic dédié, avec instrumentation temporaire (patch sur `QMessageBox.exec()` + suivi du test courant), a établi la cause exacte : `MainWindowInferencePendingResultGuardTest`/`MainWindowRenamePendingResultGuardTest` (`test_main_window_new_project.py`/`test_main_window_rename_project.py`) mockent `_confirm_pending_before_switch()` uniquement à l'intérieur d'un bloc `with patch.object(...)` scopé au corps du test ; pour les scénarios où le résultat attendu est que `_pending_path` reste intentionnellement non-`None` (Cancel préservé, échec de persistance préservé), `addCleanup(self.window.close)` — enregistré en `setUp()`, exécuté après la sortie du bloc `with` — retombe sur un vrai `closeEvent()` entièrement démocké, qui affiche la vraie boîte. 5 occurrences exactes, 100 % reproductibles sur 3 exécutions consécutives. Le filet de sécurité Mission 091 ne couvre pas ce chemin : il n'est armé que dans 4 classes dédiées à la famille de guard Mission 085 (« génération active »), jamais dans ces deux classes de la famille Mission 084 (« résultat en attente »). **Aucun fichier M093 n'est impliqué dans cette dette** — confirmé par les 5 stacks capturées, qui pointent exclusivement vers `main_window.py`/`inference_page.py`. Cette dette est **conservée pour l'audit post-M093** en tant que candidat prioritaire (extension du filet Mission 091 aux classes Pending Result / Mission 084, et correction du lifetime gap entre le mock du corps du test et `addCleanup(self.window.close)`) — **non traitée dans cette mission**, conformément à la décision explicite de l'architecte de ne pas élargir silencieusement le périmètre de M093.
- Aucun écart au contrat verrouillé en section 3 — l'implémentation suit exactement les décisions retenues (transposition du contrat propre à `LoRALibraryManager`, réutilisation de `LORA_LIBRARY_UPDATED`, garde dirty-state combiné à `_display_library_entry()`).
- `git diff --check` : propre.
- Périmètre respecté à la lettre : uniquement `src/managers/lora_library_manager.py`, `src/ui/pages/lora_page.py`, `tests/integration/test_lora_library_roundtrip.py`, `tests/integration/test_lora_roundtrip.py`, ce document.
- Commit de mission : `b99d6e6fd2430617f19a75d0af1401fae5476c45` — "Add thumbnail selector to the central LoRA library", poussé sur `main`.
- Tag annoté : `v0.2-mission093`, ciblant exactement le commit de mission ci-dessus, poussé.
- GitHub Release `v0.2-mission093` : **publiée manuellement par l'architecte** (`gh` indisponible dans cet environnement) — vérifiée indépendamment via l'API GitHub (`published`, `tag_name: v0.2-mission093`, `target_commitish: main`).
