# Mission 075 — Transactional Physical Cleanup of Dataset/LoRA Folders on Deletion

> **MISSION FONCTIONNELLEMENT VALIDÉE, IMPLÉMENTATION TERMINÉE.** 22 tests ciblés nets nouveaux (11 Dataset, 11 LoRA), non-régression complète sur `test_dataset_roundtrip.py` (103/103), `test_lora_roundtrip.py` (125/125) et `test_training_roundtrip.py` (67/67), suite complète 1355/1355, smoke test Qt réel exécuté et **PASS** (19/19 assertions, 5 scénarios réels avec de vrais fichiers sur disque — voir section 11). Voir section 12 pour l'état de clôture Git.

## 1. Contexte

L'audit post-Mission 074 a balayé systématiquement tous les appels `_workspace_manager.save()` des 8 Managers pour confirmer que la liste de dettes connue restait exhaustive (aucun appel non protégé supplémentaire trouvé). Cette même recherche a en revanche révélé, par reproduction empirique directe, une dette plus large que ce que la liste laissait supposer : `DatasetManager.delete()` et `LoRAManager.delete()` (protégés par Mission 068 au niveau Domain-only) ne suppriment jamais le dossier physique privé de l'entité (`datasets/<dataset_id>/`, `models/loras/<lora_id>/`). Contrairement aux candidats F/I (rollback-sur-échec, rares), cette fuite se produit sur **le chemin normal de toute suppression**, pas seulement en cas d'échec — confirmée par une reproduction empirique (dossier de test recréé, image copiée, suppression effectuée, dossier toujours présent avec son contenu après coup) pour Dataset **et** LoRA.

Contrairement aux Missions 068–074, cette mission introduit une suppression physique potentiellement irréversible et a donc suivi une phase de conception séparée, validée avant tout code (audit détaillé : structure physique réelle de Dataset/LoRA, primitives `WorkspaceStorage` existantes, précédents Missions 027/046/066/068).

## 2. Objectif

Supprimer physiquement, de façon transactionnellement sûre, le dossier privé d'un Dataset/LoRA lors de sa suppression Domain — sans jamais risquer une perte de données si la persistence échoue, et sans jamais rollbacker une suppression Domain déjà persistée à cause d'un échec de nettoyage physique.

## 3. Audit préalable — constats structurants

- `datasets/<dataset_id>/` n'est créé que **paresseusement**, par `DatasetManager.add_images()`, uniquement pour une image **réellement externe** (jamais pour une image déjà référencée depuis la galerie `Workspace.images`, qui n'est jamais copiée). `Dataset.create()` ne crée jamais ce dossier. Un Dataset entièrement peuplé depuis la galerie n'a donc **structurellement aucun dossier physique** — cas normal et fréquent, pas une corruption.
- `models/loras/<lora_id>/` n'est créé, dans tout le projet, que par un unique site d'écriture : `LoRAManager.set_thumbnail()`. `LoRAManager.add_files()` ne copie jamais physiquement les chemins de `LoRA.files` — ce sont des références externes arbitraires, jamais dupliquées dans ce dossier. **Confirmé : un dossier LoRA supprimable ne peut donc jamais contenir un fichier partagé/global ni un fichier appartenant à la future bibliothèque LoRA centralisée**, tant que celle-ci continue de référencer ses fichiers par chemin externe plutôt que par copie interne partagée — la mission reste compatible avec cette orientation architecturale.
- `WorkspaceStorage.rename_folder(old_root, new_root)` (Mission 027) est déjà générique (deux `Path` quelconques), déjà atomique au niveau OS, distingue déjà `WorkspaceRenamePermissionError` (verrou/permission, précédent du diagnostic réel Mission 027 — `explorer.exe` tenant un handle ouvert) du cas générique, et refuse déjà d'écraser une destination existante — réutilisable telle quelle pour le déplacement transactionnel, sans nouvelle primitive de déplacement.
- Aucune primitive de suppression physique définitive de dossier n'existe — à ajouter.
- Aucun `os.walk`/`glob` récursif nulle part dans le code de production — une zone `.trash/` interne ne peut jamais être découverte accidentellement par une autre fonctionnalité.
- Le texte de confirmation actuel de `DatasetsPage.delete_dataset()` (« les images qu'il contient resteront dans la galerie Images ») reste vrai mais est incomplet : il ne prévient pas qu'une image importée directement (jamais dans la galerie) sera réellement supprimée avec le dataset.

## 4. Stratégie retenue — Option C (déplacement transactionnel vers `.trash/`)

Écartée : suppression physique directe du dossier vivant après `save()` (Option A) — un `shutil.rmtree()` interrompu à mi-chemin (verrou, permission) laisserait un dossier partiellement vidé exactement à l'emplacement où vivait l'entité, sans mécanisme de reprise. Écartée d'emblée : suppression physique avant la mutation Domain (Option B) — un rollback Domain (Mission 068) après une suppression physique déjà effectuée résurrecterait une entité dont les fichiers sont irrémédiablement détruits.

Retenue : déplacement atomique du dossier vers `.trash/<prefixe>_<id>_<suffixe uuid4 unique>` (réutilisant `rename_folder()` tel quel) → mutation Domain + `save()` → sur échec, renommage inverse + rollback Domain → sur succès, suppression définitive best-effort de la copie déplacée. Le déplacement atomique garantit qu'immédiatement après cette étape, l'emplacement vivant original est either intact (échec du déplacement, abandon complet) either totalement vide (succès) — jamais un état intermédiaire visible à l'emplacement de l'entité.

`.trash/` n'est pas ajoutée à `WorkspaceStorage.DIRECTORIES` — créée paresseusement au premier besoin (même principe que `copy_into_workspace()` pour ses propres dossiers de destination), pour ne jamais polluer un Workspace qui ne supprime jamais rien.

## 5. Ordre exact des opérations (identique Dataset/LoRA)

1. Gardes métier existantes (`is_referenced_by_training` pour Dataset ; aucune pour LoRA) — inchangées, avant toute autre chose.
2. Calcul du dossier privé (`datasets/<id>/` ou `models/loras/<id>/`).
3. Absence du dossier → aucune opération filesystem, comportement Domain inchangé (cas normal).
4. Présence du dossier → déplacement atomique vers `.trash/<prefixe>_<id>_<uuid4().hex>` via `WorkspaceStorage.rename_folder()` (qui crée désormais paresseusement le parent de sa destination si besoin — extension mineure et rétrocompatible de la primitive, sans effet sur l'usage Mission 027 où le parent existe déjà toujours).
5. Échec du déplacement → abandon complet avant toute mutation Domain ; `WorkspaceManagerError` levée, rien n'est modifié.
6. Mutation Domain selon le contrat Mission 068 (capture index + `active_*_id`, retrait de la collection).
7. `WorkspaceManager.save()`.
8. Échec de persistence :
   - Le Domain est **toujours** restauré en premier (réinsertion au même index, restauration d'`active_*_id`) — instructions Python séquentielles qui ne peuvent pas échouer, donc garanties d'exécuter avant toute tentative de restauration filesystem.
   - Si un dossier avait été déplacé, tentative de renommage inverse.
     - Les deux restaurations réussissent → l'exception de persistence d'origine est simplement relevée (comportement inchangé depuis Mission 068).
     - Le Domain est restauré mais le renommage inverse échoue → une nouvelle `WorkspaceManagerError` enrichie est levée (message détaillé sur le modèle de `WorkspaceManager.rename()` — Mission 027 — précisant que le Domain est sûr, où se trouve réellement le dossier, et comment le restaurer manuellement).
9. Succès de persistence : suppression définitive best-effort de la copie dans `.trash/` via la nouvelle primitive `WorkspaceStorage.delete_folder()`. Un échec ne rollback jamais le Domain déjà persisté ; le résidu reste dans `.trash/`, signalé via le résultat retourné par `delete()`.

## 6. Primitive `WorkspaceStorage` ajoutée

`delete_folder(path)` : `shutil.rmtree()` enveloppé, idempotent (chemin déjà absent → no-op, pas une erreur), `OSError` → `WorkspaceStorageError`. `rename_folder()` étendu pour créer paresseusement `new_root.parent` (`mkdir(parents=True, exist_ok=True)`) avant le renommage — no-op pour son usage Mission 027 existant (le parent y existe déjà toujours), nécessaire pour la création paresseuse de `.trash/`.

Aucune abstraction transactionnelle générique introduite : la responsabilité (ordre des opérations, gestion des deux catégories d'échec) reste dupliquée indépendamment dans `DatasetManager.delete()` et `LoRAManager.delete()`, comme pour tous les précédents Missions 066–074.

## 7. Changement de contrat de retour

`delete()` retournait `bool`. Le nettoyage définitif best-effort (étape 9) peut échouer indépendamment d'un succès de persistence complet — un signal que le seul booléen ne peut pas porter sans ambiguïté. `delete()` retourne désormais un NamedTuple dédié par entité (`DatasetDeletionResult`/`LoRADeletionResult`, `deleted: bool`, `cleanup_failed: bool`, `residual_path: Optional[str]`) — même principe que `WorkspaceManager.remove_images()` (Mission 066) retournant `RemovalResult` pour un problème structurellement identique (persistence réussie, nettoyage physique best-effort séparé). `deleted` reflète exactement l'ancien booléen (`False` pour « non trouvé »/« bloqué par une Training », `True` sinon) ; `cleanup_failed`/`residual_path` ne sont significatifs que si `deleted=True`.

Impact du changement de signature, entièrement mécanique : les call sites (`DatasetsPage.delete_dataset()`, `LoRAPage.delete_lora()`) et les assertions de tests existantes qui comparaient `result` à un booléen nu (`assertTrue`/`assertFalse`) sont adaptées à `.deleted`, y compris dans `tests/integration/test_training_roundtrip.py` (garde Dataset↔Training, touché uniquement pour cette raison mécanique, aucun changement de comportement Training).

## 8. Contrat Presentation

- `DatasetsPage.delete_dataset()`/`LoRAPage.delete_lora()` : `QMessageBox.critical()` inchangé sur `WorkspaceManagerError` (le message enrichi du double-échec s'affiche tel quel, `str(exc)` le contient déjà). Sur succès (`result.deleted`), si `result.cleanup_failed`, `QMessageBox.warning()` non bloquant signalant une suppression partielle (précédent `ImagesPage`/Mission 066), mentionnant le chemin résiduel.
- Texte de confirmation de `DatasetsPage.delete_dataset()` mis à jour : distingue explicitement les images provenant de la galerie (qui y restent) des copies importées directement dans le dataset (qui seront supprimées avec lui) — sans mentionner `.trash/`.
- `LoRAPage.delete_lora()` : texte de confirmation inchangé (déjà générique « action irréversible », pas de promesse à corriger).

## 9. Hors périmètre (confirmé)

`DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; `CharacterManager.delete()` (UI cachée) ; segfault Qt/PySide6 ; refonte générale du stockage ; future bibliothèque LoRA centralisée (seulement vérifiée pour compatibilité, non implémentée).

## 10. Tests automatisés

**Niveau Manager** (par entité, classes `DatasetManagerPhysicalDeletionTest`/`LoRAManagerPhysicalDeletionTest`) : suppression normale avec dossier existant (dossier réellement absent après, vérifié sur disque) ; suppression avec dossier déjà absent (no-op physique, `deleted=True`, `cleanup_failed=False`) ; échec du déplacement initial simulé → Domain et disque tous deux intacts, rien n'est muté ; échec `save()` après déplacement → dossier restauré à son emplacement d'origine avec son contenu exact, Domain restauré (même objet, même index, `active_*_id`) ; **double échec** (`save()` échoue **et** le renommage inverse échoue) → Domain néanmoins restauré (même objet, même index, `active_*_id`), dossier laissé dans `.trash/`, aucune autre entité/dossier touché, message d'erreur contenant les informations de récupération manuelle ; échec de la suppression définitive après persistence réussie → `deleted=True`, `cleanup_failed=True`, Domain non rollické ; retry réel après un échec de déplacement/persistence ; absence d'impact sur une entité voisine ; génération du nom de transit garantissant qu'un retry ou un résidu antérieur dans `.trash/` ne provoque pas de collision destructrice.

**Niveau Presentation** : texte de confirmation Dataset mis à jour et vérifié ; warning affiché sur `cleanup_failed` ; comportement inchangé sur succès total et sur échec `save()` simple (adaptation des assertions `.deleted`).

**Non-régression** : `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_training_roundtrip.py` (guard Dataset↔Training, adaptation mécanique de 3 assertions).

## 11. Smoke test Qt réel — réellement exécuté

Exécuté par Claude, `DatasetsPage`/`LoRAPage`/`DatasetManager`/`LoRAManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, fichiers réels écrits/lus à chaque étape (jamais de simple objet Domain) :

1. Dataset — suppression normale : fichier réel copié dans `datasets/<id>/`, suppression, dossier réellement absent ensuite, `project.json` ne référence plus le Dataset.
2. Dataset — rollback sur échec de persistence : dossier réellement restauré à son emplacement d'origine avec son contenu binaire exact, objet Domain préservé (`assertIs`), `project.json` strictement inchangé.
3. LoRA — suppression normale : miniature réelle copiée dans `models/loras/<id>/`, suppression, dossier réellement absent ensuite.
4. LoRA — rollback sur échec de persistence : dossier réellement restauré avec son contenu binaire exact, objet Domain préservé.
5. Flux Presentation réel : sélection réelle dans `DatasetsPage.dataset_list`, `delete_dataset()` réellement invoqué (confirmation mockée en headless, même technique que les tests existants), dossier réellement supprimé du disque via le vrai chemin UI.

**19/19 assertions PASS.**

## 12. Vérifications finales — réellement exécutées

- **Tests ciblés** : **22/22 nets nouveaux PASS** (`DatasetManagerPhysicalDeletionTest` 9 + 2 Presentation, `LoRAManagerPhysicalDeletionTest` 10 + 1 Presentation).
- **Non-régression complète** : `test_dataset_roundtrip.py` **103/103**, `test_lora_roundtrip.py` **125/125**, `test_training_roundtrip.py` **67/67** (garde Dataset↔Training, 3 assertions adaptées mécaniquement à `.deleted`), `test_workspace_roundtrip.py` **97/97** (extension de `rename_folder()` sans régression).
- **Suite complète** : **1355/1355** (1333 précédents + 22 nets nouveaux), une exécution complète `unittest discover`, 130.5s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.
- **`git diff --check`** : propre (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 5 fichiers de production (`workspace_storage.py`, `dataset_manager.py`, `lora_manager.py`, `datasets_page.py`, `lora_page.py`) + 3 fichiers de tests (`test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_training_roundtrip.py`) + ce document de mission.

## État d'avancement

- Phase 1 (conception) : **terminée et validée par l'architecte**.
- Implémentation : **réalisée, conforme au contrat validé (Option C, déplacement transactionnel vers `.trash/`)**.
- Correction obligatoire du double échec (rollback Domain toujours exécuté, erreur enrichie sur échec du rollback filesystem) : **implémentée et testée explicitement**.
- Tests automatisés : **exécutés, verts — 22/22 ciblés nets nouveaux, non-régression complète des 4 fichiers de tests concernés**.
- Suite complète : **1355/1355, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (5 fichiers de code + 3 fichiers de tests + 1 document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 5 scénarios réels avec de vrais fichiers sur disque, 19/19 assertions** (section 11).
- Clôture Git (commit/tag/Release) : **en cours**.
