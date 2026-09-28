# Mission 156 — Normalize Structurally Invalid Forge URLs

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente.** `ForgeEngine._request_json()` (`src/engines/forge_engine.py`) construisait l'objet `urllib.request.Request(...)` en dehors de tout `try/except` — une `base_url` structurellement invalide (vide, sans schéma reconnu) faisait lever à `Request()` une `ValueError` brute, jamais convertie en `ForgeEngineError`, le seul type que `SettingsPage.test_forge_connection()`/`GenerationManager`/`ForgeReadinessWorker` savent gérer. Résultat observable : un clic parfaitement ordinaire sur « Tester la connexion » (Forge) avec le champ URL vide ne produisait strictement aucun effet visible — aucun crash (une exception non catchée dans un slot Qt de ce projet ne termine pas le process, déjà vérifié empiriquement par Mission 152), mais le label de statut restait figé sur son texte précédent, sans le moindre indice pour l'utilisateur. Corrigé en centralisant la conversion `ValueError → ForgeEngineError` dans `_request_json()` elle-même — le point unique par lequel convergent déjà les 5 méthodes publiques qui touchent le réseau.

## 1. Root cause exacte

`urllib.request.Request()` lève une `ValueError` **à sa propre construction**, avant même que `urlopen()` ne soit atteint — confirmé empiriquement pendant l'audit/conception préalable (`Request('' + '/sdapi/v1/sd-models')` → `ValueError: unknown url type: '/sdapi/v1/sd-models'`), et non par `urlopen()` comme le suggérait (de façon imprécise) le commentaire existant de `comfyui_engine.py` — le commentaire équivalent d'`ollama_engine.py` était, lui, déjà exact sur ce point. Dans `ForgeEngine._request_json()` (avant cette mission), la construction de `Request()` se trouvait **avant** le `try` protégeant `urlopen()` — cette `ValueError` n'était donc catchée nulle part dans toute la classe.

## 2. Cinq callers directs de `_request_json()`

Confirmé par grep exhaustif : `list_checkpoints()`, `list_loras()`, `list_samplers()`, `list_schedulers()`, `generate_image()` — exactement 5, chacun appelant `self._request_json(...)` une seule fois. `upload_image()` ne touche jamais le réseau (validation locale de fichier uniquement) — non concernée.

## 3. `check_connection()` concernée transitivement

`check_connection()` ne construit jamais de requête elle-même — elle délègue entièrement à `list_checkpoints()` (`self.list_checkpoints(timeout=timeout)`), donc hérite automatiquement de la correction sans avoir eu besoin d'être touchée. C'est le point d'entrée réellement exercé par le nouveau test Engine (§6) et par `SettingsPage.test_forge_connection()`/`ForgeReadinessWorker.run()` en production.

## 4. Centralisation du correctif dans `_request_json()`

Contrairement à `ComfyUIEngine` (où chaque appelant construit son propre `Request` et où le `except ValueError` a dû être dupliqué individuellement, uniquement dans `list_checkpoints()`/`list_loras()`/`_list_ksampler_combo_values()` — jamais dans `submit()`/`wait_for_result()`/`download_output()`/`upload_image()`), `ForgeEngine._request_json()` construit déjà elle-même l'objet `Request()` en interne. Le correctif consiste donc à déplacer cette construction **à l'intérieur** du `try` déjà existant (celui qui protège `urlopen()`) et à ajouter une clause `except ValueError` supplémentaire — un seul changement, une seule fonction, qui couvre automatiquement les 5 callers directs et `check_connection()` sans qu'aucun d'eux n'ait eu besoin d'être modifié individuellement.

```python
try:
    request = urllib.request.Request(
        f"{self._base_url}{path}", data=body, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=effective_timeout) as response:
        raw = response.read()
except urllib.error.HTTPError as error:
    ...
except (urllib.error.URLError, OSError) as error:
    ...
except ValueError as error:
    raise ForgeEngineError(f"Forge base URL is invalid: {self._base_url!r}") from error
```

Les traitements existants (`HTTPError`, `URLError`/`OSError`, décodage JSON, timeouts, GET/POST, payloads) restent inchangés au caractère près — seule la position de la construction de `Request()` a bougé (de avant le `try` à l'intérieur), et une clause `except` a été ajoutée.

## 5. Contrat `ValueError → ForgeEngineError`

Chaînage préservé (`raise ... from error`), message métier clair et cohérent avec les précédents déjà établis trois fois dans ce dépôt (`ComfyUIEngine.list_checkpoints()`/`list_loras()`, `OllamaEngine.list_models()`/`generate_text()`) : `f"Forge base URL is invalid: {self._base_url!r}"`. Aucune nouvelle classe d'exception créée.

## 6. Absence de modification UI/Manager

Confirmé : `src/ui/pages/settings_page.py`, `src/ui/pages/inference_page.py`, `src/managers/generation_manager.py`, `src/ui/forge_readiness_worker.py` — **aucun n'a été modifié**. Les 3 catch existants (`ForgeEngineError` seul dans `SettingsPage.test_forge_connection()`/`ForgeReadinessWorker.run()` ; `(ComfyUIEngineError, ForgeEngineError)` dans `GenerationManager`) absorbent déjà le nouveau cas sans élargissement, exactement comme prévu par l'audit de conception préalable.

## 7. Tests ajoutés

**+2 tests nets** :

- `ForgeEngineCheckConnectionTest.test_raises_a_clean_error_on_a_structurally_invalid_base_url` (`tests/integration/test_forge_engine.py`) : `ForgeEngine(base_url="")` + `check_connection()` → `ForgeEngineError` levée (jamais `ValueError`), message contenant « invalid ». Aucun `mock_urlopen` utilisé — la défaillance survient avant `urlopen()`, un seul test suffit puisque le diff confirme que les 5 opérations directes convergent vers le même `_request_json()`.
- `SettingsPageConnectionDiagnosticsTest.test_forge_structurally_invalid_url_shows_a_status_without_crashing` (`tests/integration/test_settings_page.py`) : seul test de cette classe à **ne pas** mocker la classe `ForgeEngine` — champ `forge_url_edit` vidé, clic réel sur `forge_test_connection_button`, exerce le vrai chemin `test_forge_connection()` → `ForgeEngine.check_connection()` → `_request_json()`, vérifie que `forge_connection_status_label` affiche un message contenant « invalid » plutôt que de rester figé sur son texte précédent. Aucun appel réseau réel (la défaillance intervient avant tout socket).

**Non-vacuité vérifiée explicitement** : les deux tests ont été exécutés contre le code pré-correctif (`git stash` temporaire du seul fichier de production, tests relancés, puis restauration) — les deux échouent bien sans le correctif (`ERROR`/`FAIL`), confirmant qu'ils détectent réellement la régression et ne sont pas des tests vides. Le test Settings a de plus démontré empiriquement le symptôme exact prédit par l'audit : sans correctif, `forge_connection_status_label` reste sur `"Connexion non testée."`, sans jamais afficher d'erreur — confirmation directe de l'échec silencieux décrit dans l'audit de conception.

Aucun test Inference ajouté (hors scope explicite — le contrat `ForgeEngineError → GenerationError` est une frontière déjà existante, aucun code de cette couche ne change).

## 8. Constat hors scope, non traité

L'audit de conception a découvert que **`ComfyUIEngine` porte la même lacune** sur son propre chemin de génération : `submit()`, `wait_for_result()`, `download_output()`, `upload_image()` (et donc `generate_image()` par composition) n'ont jamais reçu le `except ValueError` que `list_checkpoints()`/`list_loras()`/`_list_ksampler_combo_values()` ont, eux, déjà reçu. Ce constat est documenté ici pour traçabilité mais **n'est pas traité par cette mission** — `ComfyUIEngine` n'a été touché en aucune façon.

## 9. Hors périmètre (non-goals confirmés)

- `ComfyUIEngine` non modifié (voir §8 pour le constat adjacent découvert mais non corrigé).
- `SettingsPage`, `InferencePage`, `GenerationManager`, `GenerationWorker` non modifiés.
- `TrainingJobRunner`, `resolve_onetrainer_launch()`, `TrainingManager.create_job()` non traités (constat Training du dernier audit global, réévaluation différée à un cycle ultérieur).
- D5 (`_same_volume()`), D6, D2, les chemins de suppression Dataset/Training/Workspace non traités.
- Aucune nouvelle classe d'exception.
- Aucun test Inference/Generation ajouté.

## 10. Résultats réels

- Tests ciblés M156 (`ForgeEngineCheckConnectionTest` + `SettingsPageConnectionDiagnosticsTest`) : **20/20 passés** (1.105s), dont les 2 nouveaux. Non-vacuité vérifiée explicitement : les 2 nouveaux tests ont été relancés contre le code pré-correctif (`git stash` temporaire du seul `forge_engine.py`) — les deux échouent bien sans le correctif (`ERROR ValueError`/`FAIL`), confirmant qu'ils détectent réellement la régression.
- `tests/integration/test_forge_engine.py` complet : **58/58 passés** (0.087s ; 57 préexistants + 1 nouveau).
- `tests/integration/test_settings_page.py` complet : **96/96 passés** (2.596s ; 95 préexistants + 1 nouveau).
- Suites voisines Forge/Generation/Inference (`test_forge_lifecycle_manager.py` + `test_generation_manager.py` + `test_generation_worker.py` + `test_inference_page.py` + `test_main_window_forge_settings.py`) : **384/384 passés** (210.631s), après reconfirmation isolée d'un flake historique unique et déjà documenté (`ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest.test_readiness_timeout_with_taskkill_success_confirms_cleanup`, timing sur lecture de fichier PID réel — même classe de flakiness process-réel déjà notée par les Missions 097/099/128/139/141, sans aucun rapport avec `forge_engine.py`/`_request_json()`) — repassé vert 1/1 en isolation immédiatement après.
- **Suite complète : 2899 collectés/2899 passés, 0 échoué** (327.463s). Équation : 2897 (clôture Mission 155) + 2 nets ajoutés par Mission 156 = **2899**, cohérent.
- `git diff --check` : clean (avertissements `LF will be replaced by CRLF` uniquement, non bloquants).
