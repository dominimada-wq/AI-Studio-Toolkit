# Mission 144 — Prevent Silent Fallback on Corrupt Settings and LoRA Library Storage

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente de validation externe.** `ApplicationSettingsStorage.load()`/`LoRALibraryStorage.load()` confondaient un fichier présent mais corrompu/illisible avec un fichier absent (premier lancement), ouvrant la voie à un écrasement silencieux et définitif lors de la prochaine sauvegarde routinière. Corrigé au niveau Storage + composition root uniquement — voir §10 pour les résultats réels.

## 1. Root cause

`ApplicationSettingsStorage.load()` (`src/infrastructure/storage/application_settings_storage.py`) et `LoRALibraryStorage.load()` (`src/infrastructure/storage/lora_library_storage.py`) capturaient `json.JSONDecodeError`/`OSError`, journalisaient un simple `logger.warning`, puis retournaient `None` — exactement la même valeur que pour un fichier absent. `ApplicationSettingsManager.__init__()`/`LoRALibraryManager.__init__()` interprètent alors ce `None` comme « premier lancement » et repartent silencieusement sur des valeurs par défaut (`ApplicationSettings()` vide, `self._loras = []`).

`WorkspaceStorage.load()` (`project.json`) gère exactement les mêmes exceptions mais **lève** `WorkspaceStorageError` — c'est le pattern volontaire déjà établi ailleurs dans ce dépôt pour protéger des données réelles contre un fichier corrompu. `ApplicationSettingsStorage`/`LoRALibraryStorage` en divergeaient sans justification documentée.

## 2. Distinction MISSING / VALID / PRESENT+CORROMPU

Invariant retenu, identique pour les deux Storages :

| Cas | Avant M144 | Après M144 |
|---|---|---|
| MISSING (fichier absent) | `None` | `None` — **inchangé**, comportement first-run légitime |
| VALID (dict JSON) | dict retourné tel quel | **inchangé** |
| MALFORMED JSON | `None` + warning | lève `...StorageError` |
| READ OSError | `None` + warning | lève `...StorageError` |
| VALID JSON / racine non-dict (`[]`, `"str"`, `42`, `null`) | `None` + warning | lève `...StorageError` |

## 3. Overwrite différé démontré (avant correctif)

**Settings** : fichier corrompu → `load()` retourne `None` → `ApplicationSettings()` (tous defaults) → un seul `ApplicationSettingsManager.update(champ_quelconque=...)` → `candidate` reconstruit avec **tous** les 16 champs = defaults sauf celui changé → `ApplicationSettingsStorage.save(...)` écrit ce candidate intégralement, écrasant définitivement la configuration réelle précédente.

**LoRA Library** : registre corrompu → `load()` retourne `None` → `self._loras = []` → un seul `import_lora()`/`update()`/`delete()` réussi → `self._save()` écrit `{"loras": [...]}` avec uniquement les entrées post-corruption, écrasant définitivement le catalogue précédent.

Les deux chemins ont été tracés bout en bout dans le code avant implémentation (audit de conception), pas supposés.

## 4. `save()` déjà durable — hors scope

Les trois `save()` (`WorkspaceStorage`, `ApplicationSettingsStorage`, `LoRALibraryStorage`) suivent déjà tous le même schéma `tempfile → json.dump → flush → fsync → os.replace`, avec nettoyage du tempfile sur `OSError`. `ApplicationSettingsStorage.save()`/`LoRALibraryStorage.save()` avaient **déjà** ce durcissement **avant** Mission 140 (qui l'a seulement ajouté à `WorkspaceStorage.save()`, en s'alignant sur elles). **Aucun `save()` n'a été modifié par cette mission.**

## 5. Structure minimale validée — ApplicationSettings

Racine attendue : un objet JSON (`dict`). Tout JSON syntaxiquement valide mais non-dict (`[]`, `"str"`, `42`, `null`) est classé structurellement invalide. Aucune validation de schéma au-delà de cette racine — `ApplicationSettings.from_dict()` reste permissif par champ (`.get(clé, défaut)`), volontairement inchangé (voir §7 exclusions).

## 6. Structure minimale validée — LoRA Library

Racine attendue : `{"loras": [...]}`. Règles :
- racine non-dict → invalide (même traitement que Settings) ;
- clé `"loras"` **absente** (`{}`) → **toujours tolérée**, catalogue vide, comportement permissif préexistant inchangé ;
- clé `"loras"` **présente** mais de type autre qu'une liste (`"foo"`, `{}`, `42`, `null`) → structurellement invalide, lève `LoRALibraryStorageError`.

## 7. Distinction invalid ROOT / invalid type de `loras` / entrée individuelle tolérée

Trois niveaux strictement distincts, seuls les deux premiers relevant de cette mission :
1. **Racine invalide** (non-dict) — corrigé (§5/§6).
2. **Type de `loras` invalide** (présent mais pas une liste) — corrigé (§6), même nature de garde structurelle que (1), ajoutée dans `LoRALibraryStorage.load()`.
3. **Entrée individuelle malformée à l'intérieur d'une liste par ailleurs valide** (`{"loras": [entrée_valide, "garbage", 42, null]}`, ou deux entrées partageant le même `lora_id`) — **tolérance déjà existante et déjà testée avant cette mission** (`LoRALibraryManager.__init__()`, filtre `isinstance(entry, dict)`) — **strictement inchangée**. Cette mission ne transforme pas ce cas en erreur Storage.

## 8. Exception chaining

`ApplicationSettingsStorageError`/`LoRALibraryStorageError` existaient déjà (aucune nouvelle classe créée, docstrings élargies pour couvrir la lecture en plus de l'écriture). `JSONDecodeError`/`OSError` → `raise ...StorageError(...) from exc`, cause préservée (`__cause__`), cohérent avec la convention déjà uniforme des trois Storages. Racine/structure invalide (pas d'exception source, condition détectée après un `json.load()` réussi) → levée sans `from`, même précédent que `WorkspaceStorageError` pour « dossier déjà existant » dans `rename_folder()`.

## 9. Architecture startup retenue

```
ApplicationSettingsStorage.load() / LoRALibraryStorage.load()
    → lève une exception Storage dédiée
ApplicationSettingsManager.__init__() / LoRALibraryManager.__init__()
    → aucun try/except, laisse propager (déjà le cas avant cette mission)
MainWindow.__init__() (src/ui/main_window.py, lignes 156 et 161-164)
    → construction échoue naturellement, propage sans modification du fichier
core/main.py::main()
    → intercepte les deux types d'exception séparément
    → un seul QMessageBox.critical(None, ...) fatal, message distinct par cause
    → return (aucun window.show(), aucun app.exec())
```

**`src/ui/main_window.py` n'a reçu strictement aucune modification** — vérifié avant implémentation : `ApplicationSettingsManager.__init__()`/`LoRALibraryManager.__init__()` n'avaient déjà aucun `try/except` autour de leur appel `Storage.load()`, donc une exception levée par `load()` remontait déjà, sans aucun changement, jusqu'au niveau de `main()`. Un seul point d'interception pour les deux causes, aucune répartition de responsabilité entre `MainWindow` et le composition root.

## 10. Politique FAIL CLOSED

Le démarrage de l'application entière échoue explicitement, avec un message clair distinguant Application Settings de LoRA Library, avant que `MainWindow` ne soit jamais affichée et avant que la boucle d'événements (`app.exec()`) ne démarre. Alternative « degraded mode » (Option B) explicitement rejetée en conception : `ComfyUIEngine`/`ForgeEngine` consomment `application_settings_manager.settings` immédiatement après sa construction (`main_window.py:174-176` et suivants) — tolérer un Manager en état d'erreur aurait exigé de faire tolérer un état `None`/dégradé à de nombreux consommateurs en cascade, une architecture nouvelle hors du périmètre borné de cette mission.

## 11. Aucune modification du filesystem

Ni la levée de l'exception, ni le `QMessageBox`, ne suppriment, ne renomment, ni ne recréent de fichier. Le fichier corrompu reste octet pour octet intact — prouvé par test dédié (§13). Aucune récupération automatique, aucun `.bak`, aucune UI de recréation de defaults.

## 12. Tests

**Storage — ApplicationSettings** (`tests/integration/test_application_settings_roundtrip.py`) : `test_storage_load_compatibility_matrix` (transformé — 6 cas malformés dont l'ajout de `root_is_null`, désormais `assertRaises` au lieu de `assertIsNone`, plus l'OSError avec vérification de `__cause__`) ; nouveaux `test_storage_load_malformed_json_preserves_original_cause`, `test_storage_load_failure_never_modifies_the_corrupt_file` (preuve bytes avant/après).

**Storage — LoRA Library** (`tests/integration/test_lora_library_roundtrip.py`) : `test_invalid_json_returns_none_with_warning` → renommé `test_invalid_json_raises_storage_error_with_error_log` (transformé) ; `test_non_dict_root_returns_none` → renommé `test_non_dict_root_raises_storage_error` (transformé, 4 sous-cas) ; nouveaux `test_non_list_loras_value_raises_storage_error`, `test_missing_loras_key_still_tolerated_as_empty_catalog`, `test_read_oserror_raises_storage_error_with_cause_preserved`, `test_load_failure_never_modifies_the_corrupt_file`. Les deux tests déjà existants sur la tolérance d'entrées individuelles malformées (`test_corrupted_registry_entries_are_kept_as_is_never_silently_dropped`, `test_non_dict_entries_in_registry_are_ignored_defensively`) sont **inchangés**, non modifiés, toujours verts.

**Composition root** (nouveau fichier `tests/integration/test_main_startup.py`) : `QApplication`/`MainWindow`/`QMessageBox` patchés (pas de vrai `QApplication([])` supplémentaire dans un process de test qui en possède déjà une instance partagée) — un test par type d'exception (message contient la bonne cause, `app.exec()` jamais appelé), un test confirmant que les deux messages sont distincts et ne se chevauchent pas, un test de non-régression du chemin de succès (`window.show()`/`app.exec()` bien appelés, aucun `QMessageBox`).

**Aucun test Qt réel permanent supplémentaire ajouté** pour re-démontrer qu'un `QMessageBox.critical(None, ...)` fonctionne avant `app.exec()` — déjà couvert par la suite existante (`tests/integration/test_qt_dialog_safety_net.py`, dialogues réels sans parent) et vérifié une fois, empiriquement, avec PySide6 réel pendant la conception de cette mission (script jetable, hors dépôt).

## 13. Résultats réels après implémentation

**Fichiers modifiés** :
- `src/infrastructure/storage/application_settings_storage.py` — `load()` lève `ApplicationSettingsStorageError` sur JSON invalide/OSError/racine non-dict (au lieu de retourner `None`), docstring de l'exception élargie.
- `src/infrastructure/storage/lora_library_storage.py` — même traitement pour `LoRALibraryStorageError`, plus le contrôle `isinstance(data["loras"], list)` quand la clé est présente.
- `src/core/main.py` — `try/except` à deux branches autour de `MainWindow()`, un `QMessageBox.critical(None, ...)` distinct par cause, `return` (aucun changement de contrat public de `main()` : pas de `SystemExit`, cohérent avec l'absence de tout consommateur du code de sortie).
- `src/ui/main_window.py` — **non modifié**, confirmé.

**Tests** :
- `tests/integration/test_application_settings_roundtrip.py` — `test_storage_load_compatibility_matrix` transformé (6 cas malformés dont le nouveau `root_is_null`, `assertRaises` au lieu de `assertIsNone`, cause OSError vérifiée) ; **+2 tests nets** (`test_storage_load_malformed_json_preserves_original_cause`, `test_storage_load_failure_never_modifies_the_corrupt_file`).
- `tests/integration/test_lora_library_roundtrip.py` — 2 tests transformés/renommés (`test_invalid_json_raises_storage_error_with_error_log`, `test_non_dict_root_raises_storage_error`) ; **+4 tests nets** (`test_non_list_loras_value_raises_storage_error`, `test_missing_loras_key_still_tolerated_as_empty_catalog`, `test_read_oserror_raises_storage_error_with_cause_preserved`, `test_load_failure_never_modifies_the_corrupt_file`). Les deux tests de tolérance d'entrées individuelles malformées, déjà existants, restent inchangés et toujours verts.
- `tests/integration/test_main_startup.py` — nouveau fichier, **+4 tests nets** (aucun test n'existait auparavant pour `src/core/main.py`).

**+10 tests nets au total** (2792 → 2798 → 2808 : équation 2798 (clôture Mission 143) + 10 = **2808**, cohérent).

**Résultats** :
- Les 3 fichiers de test ciblés M144 ensemble : **122/122**.
- Suite `test_main_window_*.py` (10 fichiers, 136 tests) — non-régression de la famille MainWindow, fichier non modifié : **136/136**.
- **Suite complète : 2808 tests collectés, 2808 passés, 0 échoué, exit 0 (340.594s)**. Aucun flake — les lignes « Failed to copy »/« disk full »/« Access is denied »/« does not contain a JSON object »/« has a non-list 'loras' value »/« is not valid JSON » visibles dans le log sont soit des injections d'erreurs simulées volontaires de tests préexistants, soit les logs `logger.error()` volontaires des nouveaux tests M144 eux-mêmes — pas des échecs réels (confirmé : une seule occurrence de `OK`, aucune occurrence de `FAILED`/`ERROR` de résultat de test dans tout le log). `git diff --check` : propre.

**Smoke** : aucun smoke manuel demandé — le comportement `QMessageBox.critical(None, ...)` avant `app.exec()` a été observé réellement pendant la conception (script PySide6 réel exécuté dans cet environnement), et le comportement composition root est couvert par test automatisé (`test_main_startup.py`). Le safety-net Qt déjà existant (`test_qt_dialog_safety_net.py`) couvre déjà, à grande échelle, un `QMessageBox` sans parent.

**Écarts par rapport au design demandé** : aucun. `main()` conserve `return` (pas de `SystemExit`), le contrat public de `main()` reste inchangé, cohérent avec l'absence de tout appelant qui inspecterait un code de sortie.

## 14. Exclusions confirmées

`from_dict()` permissif (Settings et LoRA), validation complète de schéma, récupération automatique, `.bak`/rename automatique, degraded mode, `src/ui/main_window.py`, `TrainingManager.delete()` filesystem, cascade filesystem Character, nettoyage `WorkspaceManager.create_without_publishing()`, sidecar caption, rolling backup OneTrainer, Training Resume, Forge, ComfyUI, EventBus, Settings réservés (`python_path`/`ollama_path`).
