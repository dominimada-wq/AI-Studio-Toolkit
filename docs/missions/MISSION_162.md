# Mission 162 — Complete Storage I/O Error Translation Boundaries

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `LoRALibraryStorage.save()` et `ApplicationSettingsStorage.save()` (`src/infrastructure/storage/`) appelaient `directory.mkdir()` et `tempfile.mkstemp()` **en dehors** du bloc `try/except OSError` qui protège le reste de l'écriture atomique — un `OSError` provenant de l'une ou l'autre de ces deux primitives s'échappait donc brut au lieu d'être traduit vers `LoRALibraryStorageError`/`ApplicationSettingsStorageError`. Découvert par l'audit global post-Mission 161, priorisé #1 (risque de divergence registry/filesystem réelle et non récupérable automatiquement), conçu READ-ONLY sur trois points de vérification, puis implémenté strictement dans le périmètre validé.

## 1. Défaut initial

Les deux `save()` suivaient exactement la même structure fautive :

```python
directory.mkdir(parents=True, exist_ok=True)          # hors frontière
fd, tmp_path = tempfile.mkstemp(dir=directory, ...)    # hors frontière
try:
    ...  # écriture, flush, fsync, os.replace — seul ce bloc était protégé
except OSError as exc:
    ...
    raise <Storage>Error(...) from exc
```

Un `OSError` sur `mkdir()` (permission refusée, disque plein, verrou antivirus sur un dossier tout juste créé) ou sur `mkstemp()` (mêmes causes, ou trop de fichiers ouverts) n'était jamais capturé, jamais traduit — il traversait `save()` brut.

## 2. Deux primitives hors frontière

Confirmées identiques dans les deux fichiers : `Path.mkdir(parents=True, exist_ok=True)` et `tempfile.mkstemp(dir=directory, ...)`. Le reste de la frontière (`os.fdopen`, `json.dump`, `flush`, `fsync`, `os.replace`, cleanup du tempfile) était déjà correctement protégé — confirmé par comparaison directe avec `WorkspaceStorage.save()` (Mission 140), seule référence déjà correcte du dépôt sur ce point.

## 3. Conséquence LoRA

`LoRALibraryManager.delete()` (`src/managers/lora_library_manager.py:482-554`) déplace d'abord le dossier vers `.trash/` (protégé), mute le Domain en mémoire, puis appelle `self._save()`. Son `except LoRALibraryStorageError` (L.525) ne capturait jamais un `OSError` brut de `mkdir()`/`mkstemp()` — le rollback (réinsertion Domain + restauration du dossier depuis `.trash/`) ne s'exécutait donc jamais, laissant `lora_library.json` (toujours l'ancienne liste) et le filesystem (dossier déjà déplacé) réellement divergents : un LoRA fantôme référencé dans le registry, dont le dossier réel n'est plus à l'emplacement attendu.

## 4. Conséquence Application Settings

`ApplicationSettingsManager.update()` construit un candidat puis appelle `Storage.save()` sans aucun `try/except` (contrat "candidate-before-save" volontaire — rien n'est muté en mémoire avant succès, donc aucun rollback n'est nécessaire côté Manager, quel que soit le type d'exception). Le vrai problème était en aval : `SettingsPage.save_application_settings()` ne capturait que 4 types nommés dont `ApplicationSettingsStorageError` (Mission 154) — un `OSError` brut de `mkdir()`/`mkstemp()` échappait intégralement au slot Qt, non géré.

## 5. Contrat `OSError → StorageError`

Établi par `WorkspaceStorage.save()` et les docstrings des deux exceptions elles-mêmes : *tout* `OSError` survenant pendant `save()` doit devenir l'exception Storage métier correspondante, sans distinction de sous-étape. Ce contrat est désormais respecté intégralement par les deux Storages concernés.

## 6. Pourquoi `TypeError`/`ValueError` restent hors scope

`json.dump()` peut lever `TypeError` (objet non sérialisable) ou `ValueError` — mais `WorkspaceStorage.save()`, la référence déjà établie du dépôt, ne les capture pas non plus (`except OSError` uniquement). Ce n'est donc pas un oubli propre aux deux Storages corrigés : c'est le contrat existant partout dans ce dépôt, fondé sur l'hypothèse que les données passées à `save()` viennent toujours de `to_dict()` internes déjà bien formées. Aucune preuve d'un besoin réel de les ajouter — non ajoutés.

## 7. Stratégie `tmp_path` avant le `try`

`tmp_path = None` est désormais initialisé avant le `try`, qui englobe maintenant `mkdir()`, `mkstemp()` (qui réassigne `tmp_path` seulement s'il réussit), l'écriture, et `os.replace()`. Le bloc `except OSError` ne tente un cleanup (`os.remove(tmp_path)`) que si `tmp_path is not None` — évitant tout `unlink` invalide lorsque `mkdir()`/`mkstemp()` échouent avant qu'un fichier temporaire n'ait jamais existé.

## 8. Cleanup best-effort ne masquant jamais l'erreur primaire

Le pattern existant (cleanup à l'intérieur du bloc `except`, avec son propre `try/except OSError: pass` avalant toute erreur secondaire) a été **conservé tel quel**, pas remplacé par le `finally` de `WorkspaceStorage.save()` — celui-ci laisserait une erreur de cleanup (`tmp_path.unlink()` non protégé) remplacer activement l'erreur primaire comme exception propagée. Le pattern conservé ici garantit que `exc` (l'erreur primaire — écriture, fsync, replace) reste systématiquement celle enveloppée dans l'exception Storage remontée, quelle que soit l'issue du cleanup.

## 9. Atomic-write préservé

Aucune régression sur le chemin de succès : tempfile toujours dans le même dossier que la cible (`os.replace()` reste atomique, jamais de rename cross-filesystem), `flush()`+`fsync()` toujours avant le swap, ancien fichier canonique intact tant que `os.replace()` n'a pas réussi, cleanup best-effort du tempfile en cas d'échec — confirmé par les tests d'atomic-write existants, tous encore verts, inchangés.

## 10. Managers/Pages inchangés

Aucune modification de `LoRALibraryManager`, `ApplicationSettingsManager`, `SettingsPage`, `WorkspaceStorage`, Domain, EventBus, ou tout autre fichier de production — confirmé par le scope final (§ ci-dessous), exactement les deux fichiers Storage annoncés.

## 11. Réutilisation du rollback LoRA existant

`test_delete_persistence_failure_restores_folder_and_domain` (préexistant) prouvait déjà que le rollback de `LoRALibraryManager.delete()` (L.526-541, non modifié par cette mission) fonctionne correctement dès lors que `LoRALibraryStorageError` est effectivement levée. La correction Storage seule suffit à réactiver ce mécanisme déjà écrit — confirmé par un nouveau test de bout en bout injectant une vraie panne `tempfile.mkstemp()` (§ Tests ajoutés).

## 12. Réutilisation M154

`test_application_settings_widgets_resync_to_manager_after_storage_failure` (préexistant) prouvait déjà que `SettingsPage.save_application_settings()` resynchronise correctement les widgets dès lors que `ApplicationSettingsStorageError` est effectivement levée. La correction Storage seule suffit — confirmé par un nouveau test de bout en bout injectant une vraie panne `tempfile.mkstemp()` (§ Tests ajoutés).

## 13. Fichiers modifiés

**Production (2, exactement le scope validé)** :
- `src/infrastructure/storage/lora_library_storage.py`
- `src/infrastructure/storage/application_settings_storage.py`

**Tests (3)** :
- `tests/integration/test_lora_library_roundtrip.py`
- `tests/integration/test_application_settings_roundtrip.py`
- `tests/integration/test_settings_page.py`

## 14. Tests ajoutés

**+6 tests nets** :
- `LoRALibraryStorageTest.test_directory_creation_failure_raises_the_storage_exception`
- `LoRALibraryStorageTest.test_tempfile_creation_failure_raises_the_storage_exception`
- `LoRALibraryManagerDeleteTest.test_delete_real_mkstemp_failure_rolls_back_exactly_like_the_wrapped_exception` (preuve de bout en bout via une vraie panne `tempfile.mkstemp()`, pas un mock de `Storage.save()`)
- `ApplicationSettingsRoundTripTest.test_directory_creation_failure_raises_the_storage_exception`
- `ApplicationSettingsRoundTripTest.test_tempfile_creation_failure_raises_the_storage_exception`
- `SettingsPageSaveErrorTest.test_application_settings_widgets_resync_after_a_real_low_level_storage_failure` (preuve de bout en bout M154 via une vraie panne `tempfile.mkstemp()`)

Un seul scénario bas niveau (`mkstemp`) a suffi au niveau Manager/Page — les deux primitives (`mkdir`/`mkstemp`) sont déjà couvertes indépendamment au niveau Storage, évitant toute duplication inutile entre les couches.

## 15. Résultats réels

- Ciblés `LoRALibraryStorageTest` : **12/12**.
- Ciblés `LoRALibraryManagerDeleteTest` : **8/8**.
- Ciblés `ApplicationSettingsRoundTripTest` : **23/23**.
- Ciblés `SettingsPageSaveErrorTest` : **11/11**.
- Modules voisins (`test_lora_library_roundtrip.py` + `test_application_settings_roundtrip.py` + `test_settings_page.py` + `test_main_startup.py`) : **256/256**.
- **Suite complète : 2940 collectés/2940 passés, 0 échoué** (340.035s). Équation : 2934 (clôture Mission 161) + 6 nets ajoutés par Mission 162 = **2940**, cohérent.
- `git diff --check` : clean.
- Exactement 2 fichiers de production modifiés — aucun troisième.

## 16. Clôture Git

Commit fonctionnel : `1aaa82b6abddef679e5de25f04128df7a462c735` (« Complete storage I/O error translation boundaries », 6 fichiers : `src/infrastructure/storage/lora_library_storage.py`, `src/infrastructure/storage/application_settings_storage.py`, `tests/integration/test_lora_library_roundtrip.py`, `tests/integration/test_application_settings_roundtrip.py`, `tests/integration/test_settings_page.py`, `docs/missions/MISSION_162.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission162` (objet `5107f4a0f3349ba2dd10260c4b2396a95af05252`, cible `1aaa82b6abddef679e5de25f04128df7a462c735`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission162 — Complete Storage I/O Error Translation Boundaries` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2940/2940, 0 échoué** (340.035s). Le tag `v0.2-mission161` (`f154a82df7bcd31109431296fe14210bee28a1f4` → objet `b1a63a949208b8cdc23e87affd6de08318ab8de1`) reste inchangé. Distinctions préservées : bug corrigé = `mkdir()`/`mkstemp()` hors frontière `try/except OSError` dans les deux Storages, jamais un défaut du reste de l'écriture atomique ; le rollback `LoRALibraryManager.delete()` (lignes 526-541) n'a jamais été la source du problème et reste inchangé ; la resynchronisation M154 de `SettingsPage` reste inchangée ; `TypeError`/`ValueError` de `json.dump()` restent délibérément hors du contrat de traduction, comme pour `WorkspaceStorage.save()` ; le cleanup best-effort du tempfile reste à l'intérieur du bloc `except`, jamais remplacé par un `finally` non protégé ; aucune modification de `LoRALibraryManager`, `ApplicationSettingsManager`, `SettingsPage`, `WorkspaceStorage`, Domain ou EventBus.
