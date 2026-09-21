# Mission 140 — Harden WorkspaceStorage.save() Durability Before Atomic Replace

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** Un audit global post-Mission 139 a établi que `WorkspaceStorage.save()` — la méthode qui écrit `project.json`, le fichier porteur de l'état persistant de tout le Workspace (Characters, Datasets, LoRA, Prompts, Trainings, Models, Workflows) — n'appelait jamais `f.flush()`/`os.fsync(f.fileno())` avant son remplacement atomique via `os.replace()`, contrairement aux deux autres fichiers de storage du projet (`ApplicationSettingsStorage`, `LoRALibraryStorage`), qui appliquent déjà ce pattern depuis leur introduction. Cette mission harmonise `WorkspaceStorage.save()` avec ce pattern déjà établi deux fois ailleurs dans le dépôt.

## 1. Problème

`WorkspaceStorage.save()` (`src/infrastructure/storage/workspace_storage.py:94-133` avant cette mission) écrivait le contenu JSON dans un fichier temporaire puis appelait `os.replace(tmp_path, target)` pour le substituer atomiquement à `project.json` existant — mais sans jamais forcer la synchronisation de ce contenu vers le disque physique avant ce remplacement. `os.replace()` garantit l'atomicité du renommage lui-même (le fichier cible passe instantanément de l'ancien contenu au nouveau, jamais un état intermédiaire), mais ne garantit rien sur la durabilité des octets du fichier temporaire au moment du remplacement : sans `fsync()`, ces octets peuvent encore résider uniquement dans le cache d'écriture de l'OS. Un crash, une coupure de courant ou un BSOD survenant juste après un `save()` apparemment réussi pouvait donc, dans certains cas, laisser `project.json` refléter un contenu tronqué ou obsolète malgré le remplacement atomique.

## 2. Preuve (vérifiée dans le code réel avant toute modification)

- `src/infrastructure/storage/workspace_storage.py:116-119` (avant modification) :
  ```python
  with os.fdopen(fd, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=4, ensure_ascii=False)
  os.replace(tmp_path, target)
  ```
  Aucun `flush()`/`fsync()` entre l'écriture JSON et le remplacement.
- Comparaison directe avec les deux autres storages du projet, tous deux confirmés appliquer déjà exactement ce pattern :
  - `src/infrastructure/storage/application_settings_storage.py:70-75` :
    ```python
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, file)
    ```
  - `src/infrastructure/storage/lora_library_storage.py:78-83` : structure identique.
- Historique Git confirmé : `WorkspaceStorage` est le plus ancien des trois storages (`1e3f42f`, 2026-08-08). `ApplicationSettingsStorage` (`10dd467`, 2026-08-12) et `LoRALibraryStorage` (`dcc27ca`, 2026-08-29) sont arrivés après et ont adopté le pattern fsync — jamais rétroporté sur `WorkspaceStorage`.
- Gestion des erreurs (avant modification) : `WorkspaceStorage.save()` utilise une structure imbriquée — `try` externe capturant tout `OSError` et le reconvertissant en `WorkspaceStorageError(...) from exc`, et un `try/finally` interne qui nettoie le fichier temporaire (`tmp_path.unlink()`) si `tmp_path` n'a pas été remis à `None` (ce qui n'arrive qu'après un `os.replace()` réussi). Un échec de `json.dump()` (déjà testé, `WorkspaceStorageAtomicSaveTest.test_failure_before_replace_*`) laisse l'ancien `project.json` intact et ne laisse aucun fichier temporaire résiduel — ce même mécanisme de nettoyage protège nativement tout nouveau point d'échec inséré à l'intérieur du même bloc `with`.
- Comportement actuel si `os.replace()` échoue : déjà couvert par la structure existante — propage `OSError`, capté par le `try` externe, `tmp_path` toujours non-`None` à ce stade donc nettoyé par le `finally`, `WorkspaceStorageError` levée avec la cause préservée. Non modifié par cette mission.

## 3. Comportement avant / Invariant cible

**Avant** : `write JSON → close (fdopen __exit__) → os.replace()`. Les octets du fichier temporaire pouvaient encore être uniquement en cache OS au moment du remplacement.

**Cible (atteint)** : `write JSON → flush() → fsync() → close (fdopen __exit__) → os.replace()`. `flush()` et `fsync()` demandent à l'OS de synchroniser les données du fichier temporaire vers le disque **avant** que `os.replace()` ne soit appelé — jamais après, jamais en parallèle.

**Nuance explicitement non revendiquée** : ce correctif ne garantit *pas* que `project.json` ne peut plus jamais être perdu ou corrompu après une coupure de courant. Il réduit la fenêtre de perte/corruption liée au cache d'écriture du contenu du fichier temporaire lui-même. La durabilité du renommage/de la mise à jour des métadonnées de répertoire reste dépendante de l'OS/du filesystem et reste hors périmètre de cette mission (aucun `fsync()` de répertoire, aucune API Win32 spécifique, aucun journal de transaction, aucune double-écriture, aucune abstraction générale de cohérence-après-crash).

## 4. Implémentation

Modification strictement localisée à `WorkspaceStorage.save()`, à l'intérieur du bloc `with os.fdopen(fd, ...) as f:` déjà existant, entre `json.dump(...)` et la sortie du bloc :

```python
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp_path, target)
tmp_path = None
```

Aucun changement de format JSON, d'indentation, d'encodage, de nom de fichier temporaire, de stratégie `os.replace()`, d'API publique, de Domain, de Manager, ou d'UI. `ApplicationSettingsStorage`/`LoRALibraryStorage` non modifiés — leur lecture a confirmé qu'ils appliquent déjà correctement le pattern cible, sans aucune incohérence nécessitant d'élargir le périmètre.

## 5. Failure semantics

Le nouveau point d'échec (`os.fsync()` levant `OSError`, par exemple disque plein) est couvert nativement par la structure de gestion d'erreurs déjà existante, sans aucune modification de cette structure :

1. `os.fsync()` lève `OSError` **à l'intérieur** du bloc `with os.fdopen(...) as f:` — le gestionnaire de contexte ferme `f` (donc le descripteur de fichier) avant que l'exception ne se propage, exactement comme pour un échec de `json.dump()`.
2. L'exception atteint le `try/finally` interne : `tmp_path` est toujours non-`None` à ce stade (il n'est mis à `None` qu'après un `os.replace()` réussi, qui n'a pas été atteint) — le fichier temporaire est donc supprimé par `tmp_path.unlink()`.
3. L'exception atteint le `try/except OSError` externe : `WorkspaceStorageError(f"Could not write project.json in {folder}") from exc` est levée, avec l'`OSError` d'origine préservée comme `__cause__` — jamais masquée, jamais remplacée.
4. **`os.replace()` n'est jamais atteint** dans ce scénario — l'ancien `project.json` reste donc byte-for-byte intact, exactement comme pour tout échec survenant avant le remplacement.

Aucune fausse réussite possible : le storage ne rapporte de succès (retour normal, pas d'exception) que si `flush()`, `fsync()` **et** `os.replace()` ont tous réussi dans cet ordre.

## 6. Tests

**Fichiers modifiés** :
- `src/infrastructure/storage/workspace_storage.py` — implémentation (12 lignes ajoutées : docstring + 2 lignes de code).
- `tests/integration/test_workspace_roundtrip.py` — `import os` ajouté, 3 tests nets ajoutés dans la classe existante `WorkspaceStorageAtomicSaveTest` (76 lignes).

**Nouveaux tests** (`WorkspaceStorageAtomicSaveTest`) :
1. `test_fsync_receives_the_tempfiles_own_descriptor_before_replace` — preuve d'ordre et d'identité : `tempfile.mkstemp`, `os.fsync` et `os.replace` sont tous trois enveloppés par des wrappers qui appellent la vraie fonction tout en enregistrant l'ordre d'appel (même idiome que `test_start_calls_prepare_then_create_job_then_run_in_that_order` dans `test_training_roundtrip.py`) — prouve que `os.fsync()` est appelé exactement une fois, avec le descripteur de fichier réellement retourné par `tempfile.mkstemp()` (capturé indépendamment), et que cet appel précède `os.replace()`.
2. `test_fsync_failure_leaves_existing_project_json_intact_and_never_calls_replace` — `os.fsync` patché pour lever `OSError("disk full during fsync")` : `os.replace()` n'est jamais appelé (liste de wrapper vide), l'ancien `project.json` reste byte-for-byte identique, `WorkspaceStorageError` levée avec `__cause__` de type `OSError`.
3. `test_fsync_failure_does_not_leave_a_stray_temp_file` — même échec simulé : aucun fichier résiduel autre que `project.json` dans le dossier, mirroir exact de `test_failure_before_replace_does_not_leave_a_stray_temp_file` (le test équivalent déjà existant pour un échec de `json.dump`).

**Résultats réels** :
- Suite ciblée `WorkspaceStorageAtomicSaveTest` : **6/6** (3 existants inchangés + 3 nouveaux).
- `test_workspace_roundtrip.py` complet : **107/107**.
- `test_application_settings_roundtrip.py` + `test_lora_library_roundtrip.py` (non modifiés, non-régression des deux storages déjà durcis) : **112/112**.
- **Suite complète** : **2782 tests collectés, 2782 passés, 0 échoué, exit 0 (370.341s)** — aucun flake Forge cette fois-ci, run entièrement propre. Équation : 2779 (clôture Mission 139) + 3 nets ajoutés par Mission 140 = **2782**, cohérent.

## 7. Smoke

Aucun smoke manuel requis — conformément à l'autorisation, aucun test de coupure électrique réelle. Le point critique (ordre `write → flush → fsync → replace`, et non-appel de `replace` sur échec de `fsync`) est vérifié directement par test automatisé, avec les vraies fonctions `os.fsync`/`os.replace`/`tempfile.mkstemp` réellement invoquées (wrappers d'enregistrement, jamais de stub qui remplacerait leur comportement réel) — pas seulement mockées comme boîtes noires.

## 8. Exclusions confirmées

Aucun changement à `ApplicationSettingsStorage`/`LoRALibraryStorage` (déjà corrects, servent uniquement de référence). Aucun changement Domain/Manager/UI. Aucun traitement du rolling backup OneTrainer, de Resume Training, du nettoyage filesystem de `TrainingManager.delete()`, de la dette historique des 4 dossiers `create_job()`, de la flakiness Forge, des Settings morts, du garde `CharacterManager.delete()`, d'EventBus, de Central LoRA, d'Inference, ou d'UI — tous strictement hors périmètre de cette mission, conformément à l'autorisation.

## 9. Écarts par rapport au design demandé

Aucun. L'implémentation suit exactement le pattern déjà établi par les deux autres storages, sans aucune abstraction nouvelle, sans changement d'API, sans décision de conception supplémentaire.

## 10. Clôture Git

Commit fonctionnel `8649fb5587ed496d09df122b3b56f9bc4f059732` (« Harden WorkspaceStorage save durability », 3 fichiers : `src/infrastructure/storage/workspace_storage.py`, `tests/integration/test_workspace_roundtrip.py`, `docs/missions/MISSION_140.md`), poussé sur `main` (`14a78e3..8649fb5`). Tag annoté `v0.2-mission140` créé exactement sur ce commit (objet tag local `63cf4a93382cb2ee666e61b290d3c7b5eec1e329`, peeled target local et distant tous deux `8649fb5587ed496d09df122b3b56f9bc4f059732`, vérifiés identiques), poussé et confirmé sur `origin`. GitHub Release `v0.2-mission140` publiée manuellement (titre « v0.2-mission140 — Harden WorkspaceStorage Save Durability »).
