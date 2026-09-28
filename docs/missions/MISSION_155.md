# Mission 155 — Fail Closed on Inconclusive LoRA Alias Inspection

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `_find_existing_alias()` (`src/managers/lora_library_manager.py`) localisait un alias d'exposition existant via `Path.is_dir()`/`Path.glob()` — deux primitives `pathlib` qui avalent silencieusement plusieurs classes d'erreurs filesystem distinctes (permission refusée, volume non prêt/déconnecté, toute autre `OSError`) en les réduisant à « aucun alias trouvé », exactement comme un alias réellement absent. `_expose()`/`_unexpose()` ne pouvaient donc pas distinguer une inspection filesystem réellement inconclusive d'une absence prouvée — Mission 152 avait déjà résolu exactement ce problème pour `has_any_exposure()`, mais avait explicitement laissé `_find_existing_alias()` intact. Corrigé en réutilisant la primitive sûre de Mission 152 (`_list_expose_subfolder()`) à l'intérieur de `_find_existing_alias()`, convertissant toute inspection inconclusive en `LoRALibraryError` — le contrat externe déjà établi de `_expose()`/`_unexpose()` — sans introduire de nouvelle exception ni toucher `LoRAPage`/`InferencePage`.

## 1. Root cause

`Path.is_dir()` et `Path.glob()` (module `pathlib` de la stdlib) avalent en interne certaines `OSError` — notamment celles portant `winerror` 21 (« device not ready ») ou 123 (« invalid filename syntax ») sous Windows, ainsi que `ENOENT`/`ENOTDIR`/`EBADF`/`ELOOP` — en les traitant comme une preuve d'absence (`False`/liste vide), sans distinction avec une inspection réellement inconclusive. `_find_existing_alias()` (avant cette mission) :

```python
if not subfolder.is_dir():
    return None

matches = sorted(subfolder.glob(f"*__{lora_id}.*"))
```

Un `os.stat()` (utilisé en interne par `is_dir()`) échouant avec `OSError(winerror=21)` sur un volume amovible/réseau temporairement déconnecté produit exactement le même résultat (`None`) qu'un sous-dossier `AIStudioToolkit/` réellement jamais créé. Aucun appelant ne pouvait distinguer les deux cas.

Mission 152 avait déjà résolu ce problème exact pour `has_any_exposure()` (guard de changement de chemin d'exposition en Settings), via une nouvelle primitive dédiée `_list_expose_subfolder()` — mais son propre docstring déclare explicitement n'avoir *pas* touché `_find_existing_alias()`/`_expose()`/`_unexpose()`, laissant `_find_existing_alias()` porteur du même défaut jusqu'à cette mission.

## 2. Différence absence prouvée / inspection inconclusive

- **Absence prouvée** (`FileNotFoundError`/`NotADirectoryError`, `errno` `ENOENT`/`ENOTDIR`) : le sous-dossier `AIStudioToolkit/` n'existe réellement pas encore — comportement normal, « aucun alias » est la bonne réponse.
- **Inspection inconclusive** (`PermissionError`, volume non prêt/déconnecté, tout autre `OSError`) : l'état réel du sous-dossier ne peut pas être établi — répondre « aucun alias » serait une supposition non vérifiée, potentiellement fausse.

## 3. Scénario `_unexpose()` → suppression canonique → hardlink orphelin (avant correction)

`LoRAPage.delete_from_library()` → `unexpose_from_comfyui()`/`unexpose_from_forge()` → `_unexpose()` → `_find_existing_alias()` : si le root d'exposition devient transitoirement inaccessible pendant l'inspection, `_find_existing_alias()` retournait `None` sans erreur → `_unexpose()` retournait `False` (son contrat documenté pour « jamais exposé » ou « déjà retiré ») → `delete_from_library()` ne voit aucun échec (`unexpose_failures` reste vide) → `lora_library_manager.delete()` s'exécute, déplaçant puis supprimant le fichier canonique → le hardlink d'exposition, jamais retiré, **survit physiquement** dans `expose_root/AIStudioToolkit/`, toujours visible par Forge/ComfyUI, alors que l'utilisateur voit une suppression réussie.

## 4. Scénario `_expose()` (avant correction)

`LoRAPage.expose_selected_to_comfyui()`/génération `InferencePage` → `expose_to_comfyui()`/`expose_to_forge()` → `_expose()` → `_find_existing_alias()` retournait `None` par la même inspection inconclusive → branche « aucun alias existant » : soit `os.link()` échoue avec `FileExistsError` si l'alias réel occupe déjà le nom déterministe attendu (erreur trompeuse : « impossible de créer le hardlink » alors que l'exposition existe déjà), soit — si la LoRA a été renommée depuis sa dernière exposition — un second hardlink est créé sous le nouveau nom sans jamais nettoyer l'ancien, laissant un alias orphelin supplémentaire.

## 5. Réutilisation de `_list_expose_subfolder()` (Mission 152)

`_find_existing_alias()` délègue désormais l'inspection du sous-dossier à `_list_expose_subfolder()` (déjà introduite par Mission 152, `os.scandir()`, contrat à trois états) au lieu de `Path.is_dir()`/`Path.glob()`. La logique de correspondance par `lora_id` (`fnmatch(name, f"*__{lora_id}.*")`, identique au motif déjà utilisé par `has_any_exposure()`), la construction des `Path` complets, le comportement zéro/un match et le comportement multi-match/ambiguïté existant (`LoRALibraryError` sur plus d'un match) sont **strictement préservés**. Un sous-dossier réellement absent retourne toujours `[]` (`FileNotFoundError`/`NotADirectoryError`), donc `None` — comportement historique inchangé.

## 6. Maintien du contrat externe `LoRALibraryError`

`_list_expose_subfolder()` lève `LoRAExposureRootInspectionError` sur inspection inconclusive — cette exception n'est catchée par aucun appelant de `_expose()`/`_unexpose()` (`LoRAPage`, `InferencePage` ne catchent que `LoRALibraryError`). `_find_existing_alias()` catche donc `LoRAExposureRootInspectionError` et la retraduit immédiatement en `LoRALibraryError`, avec chaînage `from exc` préservé :

```python
try:
    entry_names = LoRALibraryManager._list_expose_subfolder(subfolder)
except LoRAExposureRootInspectionError as exc:
    raise LoRALibraryError(
        f"Could not reliably determine whether an existing exposure "
        f"alias for LoRA {lora_id!r} is present under {subfolder} "
        f"({exc}) — refusing to assume none exists. Retry once "
        f"access to the exposure path is restored."
    ) from exc
```

Aucune nouvelle classe d'exception, aucune modification de `LoRAPage`/`InferencePage` — les 3 sites d'appel existants (`delete_from_library()`, `expose_selected_to_comfyui()`, génération `InferencePage`) continuent de fonctionner sans changement, leurs `except LoRALibraryError` absorbant déjà le nouveau cas.

## 7. Restauration du fail-closed

Avant cette mission, `_unexpose()` pouvait retourner un « succès apparent » (`False`, sans exception) alors que l'inspection était en réalité inconclusive — brisant la propriété fail-closed sur laquelle repose la séquence de suppression (`delete_from_library()` : unexpose doit réussir avant toute suppression canonique). Après cette mission, la même situation lève désormais `LoRALibraryError`, catchée par `delete_from_library()` exactement comme tout autre échec d'unexpose — la suppression canonique est refusée, la propriété fail-closed est intégralement restaurée **sans qu'aucun guard supplémentaire lié à une génération active n'ait été nécessaire**.

## 8. Relation avec Missions 149/152

Consomme directement la primitive de Mission 152 (`_list_expose_subfolder()`) sans modifier `has_any_exposure()` ni le verrou Settings de Mission 149 (`LoRAExposureRootLockedError`, `ApplicationSettingsManager.update()`) — ces deux mécanismes restent inchangés et hors du chemin de code concerné par `_find_existing_alias()` (`has_any_exposure()` ne délègue jamais à `_find_existing_alias()`, confirmé par son propre docstring).

## 9. Hors périmètre (non-goals confirmés)

- **D5** (`_same_volume()`/`os.stat()` brut) explicitement non traité — invariant différent (toute erreur = échec, contrat à 2 états), primitive différente, call site unique (`_expose()` seul, jamais `_unexpose()`), correctif autonome ne dépendant pas de `_list_expose_subfolder()`. Mini-audit de conception préalable a confirmé que la seule proximité fichier ne justifiait pas une mission commune.
- Aucune modification de `ApplicationSettingsManager`.
- Aucune modification de `has_any_exposure()` ni de `_list_expose_subfolder()` elles-mêmes — réutilisées telles quelles.
- Aucune nouvelle classe d'exception.
- Aucune modification de `LoRAPage`/`InferencePage` — le contrat `LoRALibraryError` existant suffisait.
- Aucun guard « génération active » ajouté pour D7 — la restauration du fail-closed (§7) rend un tel guard inutile, D7 reste confirmé NON-ISSUE.
- D2/D3/D6 non traités par cette mission.
- Aucun refactor général de la Central LoRA Library.

## 10. Tests

**+2 tests nets**, ajoutés à `LoRALibraryManagerComfyUIExposureTest` (`tests/integration/test_lora_library_roundtrip.py`), juste avant `test_expose_finding_more_than_one_alias_for_the_same_lora_id_raises` :

- `test_expose_treats_inconclusive_inspection_as_a_failure_not_an_absence` : `os.scandir` simulé avec `OSError(winerror=21)` pendant `expose_to_comfyui()` → `LoRALibraryError` levée (jamais `OSError` brute, jamais de traceback dans le message), aucun hardlink créé.
- `test_unexpose_treats_inconclusive_inspection_as_a_failure_not_a_no_op` : même inspection inconclusive pendant `unexpose_from_comfyui()` sur un alias réellement exposé → `LoRALibraryError` levée (jamais un `False` silencieux), l'alias reste physiquement intact.

**Tests réutilisés sans duplication** :
- Absence légitime du sous-dossier (invariant 4) : déjà démontrée par `test_expose_creates_a_real_hardlink_under_a_dedicated_subfolder` (premier `expose_to_comfyui()`, sous-dossier `AIStudioToolkit/` pas encore créé) — non dupliquée.
- Propriété UI « unexpose échoue → suppression canonique refusée » : déjà démontrée génériquement par `LoRAPageComfyUIExposureTest.test_delete_is_refused_when_unexpose_fails_and_the_entry_survives` (`tests/integration/test_lora_roundtrip.py:5378`) et son équivalent Forge — ces tests simulent déjà `unexpose_from_comfyui` levant `LoRALibraryError` et prouvent que `delete()` n'est jamais appelé ; comme l'inspection inconclusive lève désormais ce même type d'exception, la propriété est déjà couverte sans test UI supplémentaire.
- Contrat à trois états de `has_any_exposure()`/`_list_expose_subfolder()` elles-mêmes : entièrement couvert par Mission 152, non dupliqué ici.

## 11. Résultats réels

- `LoRALibraryManagerComfyUIExposureTest` (`test_lora_library_roundtrip.py`) : **23/23 passés** (21 préexistants + 2 nouveaux, 0.627s).
- `tests/integration/test_lora_library_roundtrip.py` complet : **129/129 passés** (5.585s).
- Non-régression ciblée : `test_lora_roundtrip.py` + `test_settings_page.py` : **370/370 passés** (24.379s).
- **Suite complète : 2897 collectés/2897 passés, 0 échoué** (318.043s). Équation : 2895 (clôture Mission 154) + 2 nets ajoutés par Mission 155 = **2897**, cohérent.
- `git diff --check` : clean (avertissements `LF will be replaced by CRLF` uniquement, non bloquants).

## 12. Clôture Git

Commit fonctionnel : `6fd67ac5c84f479fbbd301ebaad04a34ff701941` (« Fail closed on inconclusive LoRA alias inspection », 3 fichiers : `src/managers/lora_library_manager.py`, `tests/integration/test_lora_library_roundtrip.py`, `docs/missions/MISSION_155.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission155` (objet `9e52807e3376e280db93cb02e57fe9923b1c5823`, cible `6fd67ac5c84f479fbbd301ebaad04a34ff701941`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission155 — Fail Closed on Inconclusive LoRA Alias Inspection` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2897/2897, 0 échoué** (318.043s). Le tag `v0.2-mission154` (`4f5aa1807f0a01958ce57c44c636355ae67d1e2c` → objet `a9dfb5afe0c73cc86c3142660e98de41a658ceef`) reste inchangé.
