# Mission 145 — Guard Training Deletion Against Active Jobs and Filesystem Orphaning

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente de validation externe.** `TrainingManager.delete()` pouvait être appelée pendant qu'un job du Training ciblé tournait réellement (le job devenait alors introuvable pour toute mise à jour d'état ultérieure, silencieusement) et ne supprimait jamais `training/<training_id>/` du disque, laissant configs/sorties/checkpoints orphelins indéfiniment. Corrigé au niveau `TrainingManager`/`TrainingPage` uniquement — voir §9 pour les résultats réels.

## 1. Root cause

`TrainingManager.delete()` (`src/managers/training_manager.py`) était une mutation Domain pure : retrait de `character.trainings`, `active_training_id` remis à `None` si concerné, `WorkspaceManager.save()`. Aucun appel filesystem, aucune vérification d'activité — confirmé par sa propre docstring d'avant-mission (« Domain-only mutation, no filesystem involved »). Deux défauts en résultaient, appartenant au même invariant de suppression et à la même méthode :

**A. Suppression pendant job actif.** Rien n'empêchait de supprimer un Training dont un job était `STARTING`/`RUNNING`. Le process OS réel continuait de tourner, ignorant la suppression. À sa terminaison, `TrainingJobRunner` appelle `TrainingManager.update_job_state()`, qui résout le job via `_find_job()` — lequel itère `self.trainings` et ne retrouve plus rien puisque le Training a disparu. `update_job_state()` retourne alors `False` silencieusement, **avant** toute mutation de `job.state`, **avant** `save()`, **avant** la publication d'événement — aucune exception, aucun log, aucun événement EventBus. Le résultat final du job (succès/échec, `.safetensors` produit) n'est jamais enregistré.

**B. Filesystem jamais nettoyé.** `training/<training_id>/` — configs, `jobs/<job_id>/output|workspace|cache|debug|concept`, `.safetensors`, backups OneTrainer — reste sur disque indéfiniment après suppression Domain, sans plus aucune référence dans `project.json`. Dette déjà documentée deux fois sans être traitée (`MISSION_138.md` §20/§26, `MISSION_139.md` §15).

Le bouton « Supprimer » de `TrainingPage` est réel, activé, sans garde — contrairement à `CharactersPage.delete_character()` (Mission 143), dont l'UI multi-Character reste `setVisible(False)`. Cette mission corrige donc un chemin réellement atteignable par tout utilisateur aujourd'hui.

## 2. Garde active-job — scoping corrigé

`has_active_job()` (Mission 100, garde de fermeture d'application) scanne **tous** les Trainings du Character principal — utiliser ce prédicat tel quel pour `delete()` aurait bloqué à tort la suppression d'un Training B inactif simplement parce qu'un Training A sans rapport possède un job actif. `has_active_job()` reste **strictement inchangée** ; un nouveau prédicat local, scopé au seul Training ciblé (`any(job.state in TRAINING_JOB_ACTIVE_STATES for job in training.jobs)`), est utilisé exclusivement par `delete()`.

| État du job | Bloque la suppression de **ce** Training ? |
|---|---|
| `STARTING` | Oui |
| `RUNNING` | Oui |
| `SUCCEEDED` | Non |
| `FAILED` | Non |
| `CANCELLED` | Non |
| `UNKNOWN` | Non |

Un job actif sur un **autre** Training n'a aucune influence — vérifié par test dédié (§7).

## 3. `TrainingActiveError` — enforcement dans le Manager

Nouvelle exception `TrainingActiveError(Exception)`, levée par `delete()` **avant** toute mutation Domain ou filesystem si le Training ciblé a un job actif. Aucun `QMessageBox` dans `TrainingManager` ; aucune annulation automatique du job ; aucune attente `QProcess` ; aucune orchestration asynchrone. L'utilisateur doit utiliser le mécanisme Cancel déjà existant, puis réessayer — Option A du comparatif de conception (refus net), retenue pour sa taille minimale face à une orchestration Cancel-then-Delete jugée hors de portée d'une seule mission bornée.

## 4. Structure physique et Central LoRA Library — indépendance tracée

`training/<training_id>/` (Training-level `concept/`, `output/`, `onetrainer_config.json`, et `jobs/<job_id>/` pour chaque job) est un seul sous-arbre — un move unique suffit à capturer tous les jobs d'un Training, sans itération par job.

Tracé dans le code, pas supposé : `TrainingPage.import_selected_job_to_library()` → `LoRALibraryManager.import_lora()` **copie** physiquement le fichier (`WorkspaceStorage.copy_into_workspace()`, `workspace_root` délibérément pointé sur le dossier de destination pour forcer une vraie copie) dans un nouveau `<library_root>/<lora_id>/`, `library_root` par défaut `~/AI Studio Toolkit/LoRA Library` — arbre totalement distinct du Workspace. L'exposition Forge/ComfyUI (`_expose()`) hardlink toujours depuis `lora.files[0]`, jamais depuis `training/<id>/`. **Conséquence** : supprimer `training/<training_id>/` est sûr pour la Central LoRA Library et toute exposition Forge/ComfyUI, à condition que le LoRA ait déjà été importé — vérifié par test d'intégration dédié (§7), sans lancer Forge/ComfyUI réels.

## 5. Ordre transactionnel — mirroring `LoRAManager.delete()`

`TrainingManager` est Character-scoped exactement comme `LoRAManager` (`character.trainings`/`active_training_id`/`WorkspaceManager.save()`/`WorkspaceManagerError`) — retenu comme pattern le plus proche plutôt que `DatasetManager` (dont le rollback inclut une préoccupation de référencement croisé non pertinente ici) ou `LoRALibraryManager` (Application-level, pas de `active_id`, backend de persistance distinct).

```
1. retrouver le Training (sinon TrainingDeletionResult(deleted=False))
2. garde active-job scopée (sinon TrainingActiveError, rien touché)
3. déterminer training/<training_id>/
4. si le dossier existe : move atomique vers .trash/training_<id>_<uuid>/
   (WorkspaceStorage.rename_folder()) — échec ici : aucune mutation
   Domain, aucun save, aucun événement
5. capturer index + previous_active_training_id, muter Domain
6. WorkspaceManager.save()
   échec : reinsert Domain + restore active_training_id (toujours),
   PUIS reverse-rename le dossier trashed — échec du reverse-rename :
   WorkspaceManagerError enrichie chaînée from rollback_exc, message
   de récupération manuelle (identique au pattern LoRAManager.delete())
7. succès : purge best-effort du dossier trash — échec : deleted=True
   quand même, cleanup_failed=True, residual_path renseigné (aucun
   rollback Domain — même politique que Dataset/LoRA/LoRALibrary)
8. publish TRAINING_DELETED (en dernier, uniquement sur succès complet)
9. return TrainingDeletionResult
```

Un dossier absent (Training jamais démarré) saute l'étape 3-4-7 entièrement — tolérance identique à Dataset/LoRA.

## 6. Contrat public — `TrainingDeletionResult`

`delete()` retournait `bool` ; retourne désormais `TrainingDeletionResult(deleted, cleanup_failed, residual_path)`, même convention que `LoRADeletionResult`/`DatasetDeletionResult` (Mission 075), nécessaire pour rapporter un échec de purge sans le confondre avec un échec de suppression. Tous les appelants existants migrés vers `.deleted` — le seul appelant production ignorait déjà la valeur de retour.

**Audit exhaustif des call sites** (exigé avant clôture, exécuté sur le dépôt réel) : un seul appelant production, `TrainingPage.delete_training()` (`src/ui/pages/training_page.py:1105`), qui capture désormais `result` (voir §6bis). Tous les autres usages sont des appels de test sans vérité simple sur l'objet retourné lui-même — chaque `assertTrue(...)`/`assertFalse(...)` porte explicitement sur `.deleted`, jamais sur `result` nu (un `NamedTuple` est toujours vrai au sens Python, quel que soit son contenu — un `assertTrue(result)` nu serait devenu un test vide de sens). Une occurrence de ce piège exact a été trouvée et corrigée pendant cette vérification (`TrainingManagerDeleteRollbackTest.test_delete_succeeds_normally_when_save_works`, `assertTrue(result)` → `assertTrue(result.deleted)`).

## 6bis. `cleanup_failed` côté UI — convention produit existante suivie

Comparaison exhaustive avec les trois callers UI existants d'un `*DeletionResult` : `DatasetsPage.delete_dataset()` (`datasets_page.py:280-301`), `LoRAPage.delete_lora()` (`lora_page.py:368-389`) et `LoRAPage.delete_from_library()` (`lora_page.py:1422-1444`) vérifient **tous les trois** `result.cleanup_failed` et affichent, sur succès partiel uniquement, un `QMessageBox.warning(self, "Suppression partielle", "... certains fichiers associés n'ont pas pu être supprimés du disque (dossier résiduel : {result.residual_path}).")` — jamais présenté comme un échec de la suppression elle-même, qui a déjà réussi. Cette convention est confirmée **affichée**, jamais journalisée seule ni ignorée. `TrainingPage.delete_training()` suit désormais exactement le même patron, avec le même titre de dialogue et la même formulation adaptée au vocabulaire Training.

## 7. Tests

**`TrainingManagerDeleteFilesystemAndActiveJobTest`** (nouvelle classe, `tests/integration/test_training_roundtrip.py`) : delete normal avec filesystem réel supprimé ; dossier absent toléré ; refus sur job `STARTING` ; refus sur job `RUNNING` ; Training B supprimable pendant que Training A a un job actif (verrouille la correction de granularité du §2) ; échec du move-to-trash (aucune mutation Domain/filesystem) ; échec de `save()` avec restauration Domain **et** filesystem prouvée (dossier restauré, sentinelles de contenu intactes, `jobs/<job_id>/output/` toujours présent) ; échec de `save()` **et** du reverse-rename (message chaîné avec indication de récupération manuelle) ; échec de purge après `save()` réussi (`deleted=True`, `cleanup_failed=True`) ; Training multi-job (un seul move capture tous les jobs) ; `TRAINING_DELETED` publié uniquement sur succès complet.

**`TrainingPageDeleteConfirmationTest`** : texte de confirmation mentionnant fichiers/résultats locaux et survie de la Bibliothèque LoRA ; `TrainingActiveError` intercepté par un `QMessageBox.warning` dédié, Domain/filesystem intacts ; `cleanup_failed=True` affiche le warning « Suppression partielle » avec le `residual_path` exact ; suppression pleinement réussie n'affiche aucun warning.

**`TrainingPageJobImportTest`** : Central LoRA Library démontrée indépendante après suppression du Training source (fichier Library byte-identique, entrée toujours exploitable via `LoRALibraryManager.get()`).

4 tests déjà existants asserting sur la valeur de retour de `delete()` (`test_delete_active_training_resets_selection_and_persists`, `test_full_create_select_save_close_reopen_cycle`, et les deux de `TrainingManagerDeleteRollbackTest` couvrant le succès normal et le retry) sont **transformés** (`.deleted` au lieu de la vérité simple de l'ancien booléen), aucune assertion fonctionnelle nouvelle.

Aucun test Forge/ComfyUI réel requis pour la preuve d'indépendance Central LoRA Library — copie physique et hardlink déjà tracés au niveau code (§4).

## 8. Exclusions confirmées

Training Resume, PID/process identity (M138), `rolling_backup`, nettoyage des 4 dossiers historiques `create_job()`, cascade filesystem Character, nettoyage `WorkspaceManager.create_without_publishing()`, sidecar caption, validation path-traversal de `_training_folder()` (dette distincte découverte pendant l'audit, non corrigée ici), crash `RUNNING_OWNED` Forge/ComfyUI, redesign Central LoRA, tracking "output importé" (aucun lien Domain fiable pour le déterminer), framework transactionnel générique.

## 9. Résultats réels après implémentation

**Fichiers modifiés** (3, aucun fichier étranger) :
- `src/managers/training_manager.py` — `TrainingActiveError`, `TrainingDeletionResult`, `delete()` réécrite (garde scopée + trash-then-purge). +107/-8.
- `src/ui/pages/training_page.py` — import `TrainingActiveError`, texte de confirmation mis à jour, bloc `except TrainingActiveError`, et warning « Suppression partielle » sur `cleanup_failed` (§6bis). +48/-5.
- `tests/integration/test_training_roundtrip.py` — 4 tests existants transformés (migration `.deleted`, y compris une occurrence manquée détectée et corrigée pendant l'audit call-site du §6), **+16 tests nets** (11 dans `TrainingManagerDeleteFilesystemAndActiveJobTest`, 4 dans `TrainingPageDeleteConfirmationTest`, 1 dans `TrainingPageJobImportTest`). +405/-6.

**+16 tests nets au total** (2808 → 2824 : équation 2808 (clôture Mission 144) + 16 = **2824**, cohérent).

**Résultats** :
- `tests/integration/test_training_roundtrip.py` complet (fichier ciblé, contient tous les tests M145) : **384/384**.
- Suites voisines exécutées isolément : `test_training_job_runner.py` **12/12** ; `test_workspace_roundtrip.py` **107/107** ; `test_lora_library_roundtrip.py` **97/97** ; `test_lora_roundtrip.py` **275/275** (`datasets_page.py`/`lora_page.py`, dont la convention `cleanup_failed` a servi de référence, non modifiés — non-régression confirmée par ces mêmes suites).
- **Suite complète : 2824 tests collectés, 2824 passés, 0 échoué, exit 0 (336.977s)**. Un seul traceback visible dans le log, bénin et déjà pré-existant (`inference_page.py:789/865`, `QLabel.setText(MagicMock)`, sans rapport avec ce diff — même occurrence déjà documentée non-régressive par Missions 142/143). Toutes les autres lignes « Failed to copy »/« disk full »/« Corrupted »/« has a non-list 'loras' value » sont des injections d'erreurs simulées volontaires de tests préexistants. `git diff --check` : propre.

**Smoke** : aucun smoke manuel requis — mécanisme entièrement synchrone et déterministe côté Domain/filesystem (mêmes primitives `WorkspaceStorage.rename_folder()`/`delete_folder()` déjà exercées par Dataset/LoRA), aucune UI Qt nouvelle au-delà d'un texte et d'un `QMessageBox.warning` supplémentaire déjà couvert par test automatisé.

**Écarts par rapport au design demandé** : aucun. Le prédicat active-job est bien scopé au Training ciblé (jamais `has_active_job()` modifiée) ; le contrat public de `delete()` change de `bool` à `TrainingDeletionResult` — nécessaire pour rapporter l'échec de purge sans confusion avec l'échec de suppression, seul changement de contrat non anticipé littéralement dans la conception mais dérivé directement du mirroring `LoRAManager.delete()` explicitement demandé.

## 10. Dette découverte, non traitée dans cette mission

`TrainingManager._training_folder()` ne valide pas `training_id` contre le path traversal et suppose un Workspace ouvert (lèverait `AttributeError` sinon) — préexistante, non spécifique à `delete()`, hors périmètre de cette mission (voir §8).
