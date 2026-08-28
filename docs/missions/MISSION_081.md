# Mission 081 — Normalize Invalid Ollama URL Errors

> **MISSION ENTIÈREMENT CLOSE ET PUBLIÉE.** 2 tests ciblés nets nouveaux, non-régression complète sur `test_ollama_engine.py` (23/23), `test_settings_page.py`/`test_main_window_ollama_settings.py`/`test_prompt_assistant_dialog.py` (89/89), suite complète 1467/1467, smoke test Qt réel exécuté et **PASS** (4/4 assertions, 2 scénarios réels — voir section 5). Commit fonctionnel `195543c0f0fb57abbdf9b2e3da9f36dcbd764e73`, tag annoté `v0.2-mission081`, GitHub Release publiée. Voir section 7 pour l'état de clôture Git.

## 1. Contexte

L'audit réalisé après la clôture de Mission 080 a réévalué le cycle des thumbnails LoRA (clos, aucun trou fonctionnel restant), réaudité l'intégralité des 43 sites `_workspace_manager.save()` des 12 Managers (aucun nouveau site non protégé, `CharacterManager.delete()` restant la seule exclusion connue et confirmée structurellement inaccessible), puis a mené une recherche ouverte de bugs utilisateur réels à travers les principales Pages. Deux candidats A ont été retenus : `OllamaEngine` ne capture pas le `ValueError` brut produit par une URL Ollama structurellement invalide (ce candidat, Mission 081), et une perte de sélection multiple silencieuse sur Images/Datasets/LoRA après tout `WORKSPACE_SAVED` sans rapport (Candidat B2, explicitement hors périmètre de cette mission, reporté à l'audit post-Mission 081).

Le candidat retenu a été confirmé par comparaison directe avec `ComfyUIEngine.list_checkpoints()`/`list_loras()`, qui protègent déjà ce même cas pour ComfyUI, alors que `OllamaEngine.list_models()`/`generate_text()` ne le font pas — une asymétrie de robustesse réelle, vérifiée empiriquement (`urlopen('')`/`urlopen('notaurl')` lèvent bien un `ValueError` brut, jamais `URLError`).

## 2. Objectif

Garantir que `OllamaEngine.list_models()` et `OllamaEngine.generate_text()` lèvent toutes deux `AIBackendError` — jamais un `ValueError` brut — lorsque la base URL Ollama configurée est structurellement invalide (vide, sans schéma reconnu), sans modifier aucun autre comportement existant (communication réseau, parsing JSON, contrat des appelants Presentation).

## 3. Mini-audit contractuel préalable

- **Chemins publics** : `OllamaEngine` n'expose que deux méthodes publiques, `list_models()` et `generate_text()`, toutes deux passant par `_request_json()` — confirmé exhaustivement, aucun autre point d'accès réseau.
- **Précédent `ComfyUIEngine`, vérifié précisément** : `list_checkpoints()`/`list_loras()` encadrent chacune, dans leur **propre** `try/except ValueError`, à la fois la construction de `Request(...)` et l'appel à `_request_json()` — la protection n'est **pas** centralisée dans `_request_json()` lui-même, qui reste structurellement identique côté Ollama et ComfyUI (aucune capture de `ValueError`). Cette protection n'existe d'ailleurs que pour les deux méthodes de découverte (`list_checkpoints()`/`list_loras()`) ; `submit()`/`wait_for_result()`/`upload_image()` ne l'ont pas — asymétrie préexistante côté ComfyUI, non touchée par cette mission.
- **Handlers Presentation, vérifiés sans modification nécessaire** : `SettingsPage.refresh_ollama_models()` capture déjà `except AIBackendError:` ; `PromptAssistantManager.assist()` capture déjà `except AIBackendError` et la retraduit en `PromptAssistantError` ; `PromptAssistantWorker` capture déjà `PromptAssistantError` en priorité avec un filet `except Exception` en dernier recours (ce chemin n'était donc jamais exposé à un crash, seulement à un message moins précis).

**Anomalie découverte pendant l'implémentation, corrigée avant clôture** : l'hypothèse initiale — un unique `except ValueError` ajouté dans le premier bloc `try` de `_request_json()` (autour de `urlopen()`/`response.read()`) protégerait les deux appelants — s'est révélée factuellement fausse. Les deux premiers tests ciblés écrits pour ce contrat ont réellement échoué avec un `ValueError` non intercepté, révélant la cause exacte par trace complète : `urllib.request.Request(...)` lève lui-même ce `ValueError` (validation interne `_parse()`), **avant** que `_request_json()` ne soit même invoqué — `list_models()`/`generate_text()` construisent chacune leur `Request(...)` avant d'appeler `_request_json()`. Le placement correct, aligné sur le précédent réel de `ComfyUIEngine`, est donc au niveau de chacun des deux appelants, englobant la construction de `Request(...)` et l'appel à `_request_json()` — jamais une capture large à l'intérieur de `_request_json()`, qui aurait par ailleurs risqué de chevaucher son propre `except json.JSONDecodeError` (une sous-classe de `ValueError`) sur un bloc `try` différent. `_request_json()` reste donc entièrement inchangé.

## 4. Implémentation

**`OllamaEngine.list_models()`** et **`OllamaEngine.generate_text()`** ([ollama_engine.py](../../src/engines/ollama_engine.py)) : la construction de `urllib.request.Request(...)` et l'appel à `_request_json()` sont désormais chacun encadrés d'un `try/except ValueError`, convertissant en `raise AIBackendError(f"Ollama base URL is invalid: {self._base_url!r}") from error"` — même message et même convention `!r`/chaining que le précédent `ComfyUIEngine`. Le correctif est volontairement dupliqué sur les deux méthodes (2 méthodes publiques seulement, même pattern déjà éprouvé côté ComfyUI, aucune abstraction commune introduite). `_request_json()` conserve strictement son contrat antérieur : `HTTPError`, `(URLError, OSError)`, `json.JSONDecodeError` inchangés, aucune capture large de `ValueError`.

## 5. Tests automatisés et smoke test Qt réel

**2 tests ciblés nets nouveaux** (`tests/integration/test_ollama_engine.py`, sans mock, même patron que `test_list_checkpoints_raises_on_structurally_invalid_base_url` de `ComfyUIEngine`) : `test_list_models_raises_on_structurally_invalid_base_url` (`OllamaEngineListModelsTest`) et `test_generate_text_raises_on_structurally_invalid_base_url` (`OllamaEngineGenerateTextTest`) — `OllamaEngine(base_url="")` doit lever `AIBackendError` (jamais `ValueError`), message vérifié pour prouver qu'il s'agit bien du chemin « invalid base URL » et non du chemin « server unreachable ».

**Non-régression** : `test_ollama_engine.py` (23/23 — 21 précédents + 2 nets nouveaux) ; `test_settings_page.py`/`test_main_window_ollama_settings.py`/`test_prompt_assistant_dialog.py` (89/89, aucun changement de comportement). **Suite complète : 1467/1467** (1465 précédents + 2 nets nouveaux), une exécution complète `unittest discover`, 142.8s, aucun crash.

**Smoke test Qt réel**, exécuté par Claude, `SettingsPage`/`SettingsManager`/`ApplicationSettingsManager` réels, `OllamaEngine` réel (aucun mock) — **PASS, 4/4 assertions**, 2 scénarios réels : URL Ollama vide + clic réel sur « Rafraîchir les modèles » → aucune exception, message « Découverte impossible... » affiché ; URL structurellement invalide (`"notaurl"`) + même clic réel → même résultat contrôlé, aucune trace `ValueError` brute.

## 6. Conclusion

`OllamaEngine.list_models()`/`generate_text()` lèvent désormais systématiquement `AIBackendError` pour une base URL structurellement invalide, au même titre que le comportement déjà correct de `ComfyUIEngine.list_checkpoints()`/`list_loras()`. `SettingsPage`, `PromptAssistantManager`/`PromptAssistantWorker` n'ont nécessité aucune modification, gérant déjà correctement `AIBackendError`. L'asymétrie résiduelle côté `ComfyUIEngine` (`submit()`/`wait_for_result()`/`upload_image()` non protégés) et le Candidat B2 (perte de sélection multiple sur Images/Datasets/LoRA) restent explicitement hors périmètre, à réévaluer lors d'un futur audit du dépôt réel.

## 7. État d'avancement et clôture Git

- Mini-audit contractuel préalable : **terminé**, une hypothèse de placement initiale invalidée par les tests eux-mêmes puis corrigée avant clôture.
- Implémentation : **réalisée**, strictement limitée à `src/engines/ollama_engine.py`.
- Tests automatisés : **exécutés, verts — 2/2 ciblés nets nouveaux, non-régression complète**.
- Suite complète : **1467/1467, aucun crash**.
- `git diff --check` : **propre** (seuls des avertissements de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme** (1 fichier de production + 1 fichier de tests + ce document de mission).
- Smoke test Qt réel : **réalisé, PASS, 4/4 assertions, 2 scénarios réels**.
- Clôture Git (commit/tag/Release) : **entièrement effectuée** — commit fonctionnel `195543c0f0fb57abbdf9b2e3da9f36dcbd764e73` (`feat: normalize invalid Ollama URL errors to AIBackendError`), tag annoté `v0.2-mission081` (peelé exactement sur `195543c0f0fb57abbdf9b2e3da9f36dcbd764e73`), GitHub Release `v0.2-mission081` publiée manuellement par l'architecte.
