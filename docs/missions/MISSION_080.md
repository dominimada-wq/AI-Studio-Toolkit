# Mission 080 — Automatic Cleanup of the Previous LoRA Thumbnail After a Successful Replacement

> **MISSION ENTIÈREMENT CLOSE ET PUBLIÉE.** 7 tests ciblés nets nouveaux (6 Manager + 1 Presentation), non-régression complète sur `test_lora_roundtrip.py` (167/167), suite complète 1465/1465, smoke test Qt réel exécuté et **PASS** (16/16 assertions, 5 scénarios réels — voir section 6). Commit fonctionnel `67fc499a78c48b30b68f16461602bf10e7b07cc6`, tag annoté `v0.2-mission080`, GitHub Release publiée. Voir section 8 pour l'état de clôture Git.

## 1. Contexte

L'audit réalisé après la clôture de Mission 079 a réévalué la famille dirty-state (close, aucun nouveau chemin utilisateur accessible), les créations Domain-only (closes depuis Mission 072), les oublis de rollback (aucun trouvé au-delà de l'exclusion déjà documentée de `CharacterManager.delete()`), et `LoRAManager.update()` (déjà résolu par Mission 073). Le seul candidat réel identifié concernait `LoRAManager.set_thumbnail()` : chaque remplacement de miniature (bouton « Choisir une miniature… », réel et visible) copie un nouveau fichier dans `models/loras/<lora_id>/` sans jamais supprimer l'ancien — un artefact technique de stockage s'accumulant silencieusement et indéfiniment, sans avertissement, sans limite.

Ce candidat nécessitait une décision produit préalable (candidat B) : l'architecte a tranché que l'ancienne copie interne doit être supprimée automatiquement après un remplacement persisté avec succès, sans confirmation supplémentaire, la sécurité des fichiers restant prioritaire — jamais de suppression d'un fichier qui n'est pas démontrablement possédé par cette LoRA.

## 2. Objectif

Étendre `LoRAManager.set_thumbnail()` pour supprimer, après une persistence réussie de la nouvelle miniature, l'ancienne miniature devenue inutile — uniquement si elle est démontrablement une copie interne possédée par le dossier privé de cette LoRA (`workspace_root/models/loras/<lora_id>/`), jamais un passthrough externe ou une zone du Workspace appartenant à une autre entité.

## 3. Mini-audit technique préalable

- **Représentation actuelle** : `old_thumbnail = lora.thumbnail` (chaîne, `""` si jamais définie) capturé avant mutation ; `effective_path` (nouveau chemin résolu) assigné après. Aucun événement publié par cette méthode.
- **Anti-collision / passthrough de `copy_into_workspace()`** ([workspace_storage.py:252-253](../../src/infrastructure/storage/workspace_storage.py:252)) : le test `is_inside(source, workspace_root)` est effectué contre **`workspace_root` entier**, pas contre `destination_folder`. Une source déjà interne au Workspace mais située n'importe où ailleurs (`images/`, `datasets/<id>/`, ou même `models/loras/<autre_lora_id>/`) est traitée comme passthrough et jamais copiée — `lora.thumbnail` peut donc légitimement pointer hors du dossier propre à cette LoRA. **Conséquence directe** : le garde-fou d'ownership ne peut pas se contenter de `is_inside(old, workspace_root)` — il doit être vérifié contre `destination_folder` (le dossier spécifique à cette LoRA), le seul niveau de granularité où l'appartenance exclusive est démontrable (chaque LoRA a son propre dossier dédié, jamais écrit par une autre LoRA).
- **Ordre exact et emplacement du cleanup** : `copie/passthrough → mutation → save() → [nouveau : cleanup de l'ancienne miniature] → return`. Le cleanup ne s'exécute que dans la branche succès de `save()`, jamais avant, jamais sur échec.
- **Ancienne miniature déjà absente / échec d'`unlink()`** : convention reprise de `dataset_manager.py`/`lora_manager.py` (M067) — `FileNotFoundError` traité comme nettoyage déjà accompli (silencieux), tout autre `OSError` reporté sans jamais lever d'exception ni annuler la nouvelle miniature.
- **Mécanisme de warning** : réutilisation exacte du pattern `LoRADeletionResult`/`DatasetDeletionResult` (Mission 075) et du `QMessageBox.warning()` déjà écrit dans `lora_page.py` pour `delete_lora()`.
- **Point non anticipé** : le changement de signature de retour (`Optional[str]` → `Optional[LoRAThumbnailResult]`) impacte 8 méthodes de test existantes utilisant la valeur de retour comme chaîne brute (adaptation mécanique `.thumbnail`), et une neuvième (`test_set_thumbnail_replacement_does_not_delete_previous_file`) devait être remplacée/renommée car son assertion affirmait exactement le comportement inverse de celui voulu par cette mission — ce n'est pas une régression masquée, c'est le contrat fonctionnel même de Mission 080. Le comportement `unknown lora`/`copie échouée` → `None` est conservé tel quel (aucune de ces deux branches n'a de résultat de cleanup à décrire), limitant l'adaptation mécanique aux seuls appels qui capturaient un résultat de succès.

Aucune anomalie contractuelle : le mécanisme d'ownership est entièrement démontrable via `WorkspaceStorage.is_inside(old_thumbnail, destination_folder)`, déjà existant et déjà réutilisé ailleurs (`dataset_manager.py`) pour un usage analogue.

## 4. Implémentation

**`LoRAManager.set_thumbnail()`** ([lora_manager.py:415](../../src/managers/lora_manager.py:415)) : nouveau type de retour `LoRAThumbnailResult` (NamedTuple minimal `thumbnail`/`cleanup_failed`/`residual_path`, même principe que `LoRADeletionResult`/`DatasetDeletionResult`). Le contrat transactionnel Mission 067 (rollback + compensation de la nouvelle copie sur échec de `save()`) reste **entièrement inchangé** — le cleanup de l'ancienne miniature ne s'exécute que dans la branche succès, après le `try/except` de `save()`. Ancien fichier examiné pour suppression uniquement si : non vide, différent du nouveau chemin après résolution, **et** situé sous `destination_folder` (dossier privé de cette LoRA spécifique, jamais `workspace_root`). Suppression tentée via `Path.unlink()` ; `FileNotFoundError` traité comme déjà nettoyé ; tout autre `OSError` reporté via `cleanup_failed=True`/`residual_path` sans jamais lever d'exception ni toucher à la nouvelle miniature déjà persistée.

**`LoRAPage.choose_thumbnail()`** ([lora_page.py:442](../../src/ui/pages/lora_page.py:442)) : comportement de succès complet inchangé. Nouvelle branche `elif result.cleanup_failed:` affichant un `QMessageBox.warning()` non bloquant, réutilisant le wording établi par `delete_lora()` (Mission 075) — jamais présenté comme un échec du changement de miniature, qui a déjà réussi.

## 5. Tests automatisés

**7 tests ciblés nets nouveaux** :
- `LoRAManagerThumbnailCleanupTest` (6, Manager) : première miniature sans rien à nettoyer ; remplacement d'une miniature owned → ancien fichier supprimé, nouvelle miniature vérifiée directement dans `project.json` ; échec de suppression de l'ancien fichier après succès de la nouvelle persistence → `cleanup_failed=True`, `residual_path` correct, aucune exception, nouvelle miniature intacte ; ancien fichier owned mais déjà absent → traité comme déjà propre, aucune erreur ; ancien thumbnail passthrough vers une zone du Workspace hors du dossier de cette LoRA (image de galerie) → jamais supprimé (test de sécurité) ; ancien thumbnail owned par une **autre** LoRA (passthrough vers son dossier privé) → jamais supprimé (test de sécurité).
- `LoRARoundTripTest.test_choose_thumbnail_cleanup_failure_warns_but_keeps_new_thumbnail_active` (1, Presentation) : échec de cleanup réel → `QMessageBox.warning()` appelé une fois, `QMessageBox.critical()` jamais appelé, nouvelle miniature affichée et active.

**Non-régression complète** : `test_lora_roundtrip.py` (167/167 — 158 précédents + 8 tests existants adaptés mécaniquement vers `.thumbnail` + 1 test remplacé/renommé pour le nouveau comportement volontaire + 7 nets nouveaux), aucune autre suite touchée (seul `set_thumbnail()` était référencé, confirmé par recherche exhaustive dans `src/`/`tests/`).

**Suite complète : 1465/1465** (1458 précédents + 7 nets nouveaux), une exécution complète `unittest discover`, 152.1s, aucun crash, aucun blocage.

## 6. Smoke test Qt réel

Exécuté par Claude, `LoRAManager`/`LoRAPage`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, **PASS, 16/16 assertions**, 5 scénarios réels :
1. Choix d'une miniature externe A → copie réelle dans le dossier privé de la LoRA, persistée dans `project.json`.
2. Choix d'une miniature externe B → B active et persistée, A réellement supprimée du disque.
3. Ancienne miniature repointée vers une image de galerie réelle (passthrough hors dossier owned) → survit intacte à un remplacement ultérieur.
4. Échec réel de suppression de l'ancien fichier après persistence réussie du nouveau → nouvelle miniature active et persistée, ancien fichier résiduel sur disque, aucune exception.
5. Échec réel de `save()` → contrat Mission 067 intégralement préservé (rollback, nouvelle copie compensée, ancienne miniature intacte).

## 7. Conclusion

`LoRAManager.set_thumbnail()` ne laisse plus s'accumuler indéfiniment d'anciens fichiers miniatures orphelins après un remplacement réussi, tout en garantissant qu'aucun fichier non démontrablement possédé par le dossier privé de la LoRA concernée ne peut jamais être supprimé — passthrough externe, image de galerie, ou dossier d'une autre LoRA restent systématiquement intacts. Le contrat transactionnel Mission 067 (rollback sur échec de `save()`) reste entièrement inchangé. Aucune nouvelle confirmation utilisateur, aucun nettoyage des orphelins historiques déjà présents, aucun scanner de dossiers, aucune fonction de nettoyage générale, aucune modification de `WorkspaceStorage.copy_into_workspace()` ni de `LoRA.files`.

## 8. État d'avancement et clôture Git

- Mini-audit technique préalable : **terminé, aucune anomalie, ownership démontrée via `is_inside(old, destination_folder)`**.
- Implémentation : **réalisée**, strictement limitée à `LoRAManager.set_thumbnail()` et `LoRAPage.choose_thumbnail()`.
- Tests automatisés : **exécutés, verts — 7/7 ciblés nets nouveaux, non-régression complète de `test_lora_roundtrip.py`**.
- Suite complète : **1465/1465, aucun crash, aucun blocage**.
- `git diff --check` : **propre** (seuls des avertissements de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme** (2 fichiers de production + 1 fichier de tests + ce document de mission).
- Smoke test Qt réel : **réalisé, PASS, 16/16 assertions, 5 scénarios réels**.
- Clôture Git (commit/tag/Release) : **entièrement effectuée** — commit fonctionnel [`67fc499a78c48b30b68f16461602bf10e7b07cc6`](https://github.com/dominimada-wq/AI-Studio-Toolkit/commit/67fc499a78c48b30b68f16461602bf10e7b07cc6) poussé sur `origin/main`, tag annoté `v0.2-mission080` créé sur ce commit et poussé, GitHub Release `v0.2-mission080` publiée manuellement par l'architecte.
