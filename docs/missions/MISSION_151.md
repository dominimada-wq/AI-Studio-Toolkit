# Mission 151 — Fail Fast on ComfyUI HTTP Errors

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente.** `ComfyUIEngine._request_json()` (`src/engines/comfyui_engine.py:687-707`) capture `urllib.error.HTTPError`, lit son corps, puis passe ce corps dans le même `json.loads()` que le chemin HTTP réussi — si ce corps est un JSON valide, il est retourné à l'appelant comme s'il provenait d'une réponse 2xx, et le code HTTP réel (`error.code`) n'est jamais lu nulle part dans cette méthode. Le symptôme le plus visible est dans `wait_for_result()` : une `HTTPError` avec un corps JSON parseable pendant le polling `/history/{prompt_id}` peut être interprétée comme « résultat pas encore disponible » et finir masquée derrière le timeout applicatif générique (~120s). M151 centralise dans `_request_json()` un invariant simple : toute réponse HTTP non-2xx doit produire immédiatement une `ComfyUIEngineError`, jamais un JSON métier normal. Voir §12 pour le scope exact, §5 pour le contrat source confirmé du body `/prompt`, et §23 pour les résultats réels de l'implémentation.

## 1. Root cause

`_request_json()` traite aujourd'hui `HTTPError` ainsi (`comfyui_engine.py:696-707`) :
```python
try:
    with urllib.request.urlopen(request, timeout=effective_timeout) as response:
        raw = response.read()
except urllib.error.HTTPError as error:
    raw = error.read()
except (urllib.error.URLError, OSError) as error:
    raise ComfyUIEngineError(...) from error

try:
    return json.loads(raw)
except json.JSONDecodeError as error:
    raise ComfyUIEngineError(f"ComfyUI returned an invalid response: {raw!r}") from error
```
Sur `HTTPError`, `raw = error.read()` (`:700`) rejoint ensuite le même bloc `json.loads(raw)` que le chemin succès (`:704-705`) — si ce corps est un JSON valide, il est `return`é tel quel, sans jamais consulter `error.code`/`error.reason`. Le mini-audit READ-ONLY pré-M151 a confirmé que ce bug est strictement borné au cas **HTTPError + corps JSON-parseable qui ne correspond pas à la forme attendue par l'appelant** : un corps non-JSON ou vide lève déjà correctement aujourd'hui (via `JSONDecodeError`, mais avec un message trompeur — voir §8), et `URLError`/`OSError`/timeout socket sont déjà et restent correctement gérés par la clause séparée (`:701-702`).

Les 6 call sites actuels (voir §12) n'échouent pas tous pour la même raison aujourd'hui : 5 d'entre eux lèvent déjà `ComfyUIEngineError` **par accident** — une clé attendue (`prompt_id`, `CheckpointLoaderSimple`, `LoraLoader`, un champ `KSampler`, `name`/`subfolder`/`type`) est simplement absente du corps d'erreur reçu, ce qui déclenche leur propre validation métier post-retour. Seul `wait_for_result()` n'a aucun filet de sécurité accidentel : `entry = data.get(prompt_id)` retourne `None` si le corps d'erreur ne contient pas la clé `prompt_id` interrogée, et le polling continue silencieusement jusqu'au timeout générique — c'est le symptôme le plus visible et le plus coûteux en expérience utilisateur (jusqu'à 120s d'attente pour un message qui ne dit jamais qu'une vraie erreur HTTP a été rencontrée).

## 2. Invariant architectural M151

Après M151 :
```
Toute réponse HTTP représentée par urllib.error.HTTPError → ComfyUIEngineError immédiate.
```
Une `HTTPError` ne doit **jamais** être retournée comme JSON métier normal par `_request_json()`. Cette responsabilité est **centralisée** dans `_request_json()` — aucun des 6 call sites n'a à déterminer lui-même si le JSON qu'il reçoit provenait en réalité d'une erreur HTTP masquée. Ceci élimine structurellement la classe entière de bug, plutôt que de la corriger call-site par call-site.

## 3. Chemin HTTP 2xx — inchangé

Le comportement HTTP réussi n'est **pas** redéfini par cette mission :
- **2xx + JSON valide** → retourné tel quel, exactement comme aujourd'hui.
- **2xx + JSON invalide** → `ComfyUIEngineError` via le `JSONDecodeError` existant (`:706-707`), message inchangé.
- **2xx + body vide** → même chemin que ci-dessus (`json.loads(b"")` échoue), comportement d'échec JSON inchangé.

M151 ne profite pas de ce chantier pour redéfinir la réponse à un 2xx vide ou invalide — ce chemin reste strictement celui déjà établi.

## 4. Chemin `HTTPError`

Dans le bloc `except HTTPError` :
1. Lire le corps **au maximum une fois** (`error.read()`).
2. Ne **jamais** le retourner comme donnée normale — plus de chute partagée vers le `json.loads()`-vers-`return` du chemin succès.
3. Construire un message d'erreur court et utile (voir §6 pour l'extraction, §7 pour ce qui est exclu).
4. Lever immédiatement `ComfyUIEngineError`.

Le message doit inclure au minimum, lorsqu'ils sont disponibles : le **code HTTP** (`error.code`) et la **reason** (`error.reason`). Exemple conceptuel : `"ComfyUI request failed with HTTP 500 Internal Server Error"` — le wording exact doit rester cohérent avec le style déjà établi ailleurs dans ce même moteur (ex. `download_output()` : `f"ComfyUI returned HTTP {error.code} for /view ({filename})"`, `:245` — déjà correct, hors scope car `download_output()` n'utilise pas `_request_json()`).

## 5. Extraction défensive du body JSON — contrat confirmé par source

Une extraction best-effort **limitée** est autorisée, si le body est un JSON dict parseable :

**Priorité 1 — structure officiellement confirmée `/prompt`.** Recherche externe effectuée pendant le mini-audit préalable (WebFetch, source officielle `comfyanonymous/ComfyUI`, citée précisément) :
- `execution.py::validate_prompt()` retourne `(valid, error, good_outputs, node_errors)`, où `error` a la forme confirmée `{"type": str, "message": str, "details": str, "extra_info": dict}`.
- `server.py`, route `POST /prompt` : sur échec de validation, confirmé littéralement `return web.json_response({"error": valid[1], "node_errors": valid[3]}, status=400)`.

Donc, si `data.get("error")` est un dict et que `data["error"].get("message")` est une string non vide (après un traitement raisonnable, ex. `.strip()`), ce texte est utilisé comme détail.

**Priorité 2 — champ `message` de premier niveau.** Si la priorité 1 ne s'applique pas, et que `data.get("message")` est une string non vide, ce texte est utilisé comme détail — un filet de sécurité générique, sans preuve qu'un endpoint ComfyUI l'utilise réellement aujourd'hui, mais sans risque puisqu'il ne trouve simplement rien s'il est absent.

**Sinon** — aucun détail supplémentaire issu du body ; le message se limite au code HTTP + reason (§4).

Ne pas chercher récursivement d'autres structures. Ne pas créer un extracteur générique complexe — cette règle mirrore exactement la philosophie déjà établie par `_comfyui_execution_error_message()` (Mission 150) : champs connus, priorité fixe, fallback générique systématique, jamais de traversée arbitraire.

**Note pour `/history`** (confirmée par la même recherche source) : `server.py`, route `GET /history/{prompt_id}`, retourne **toujours 200**, y compris pour un `prompt_id` inconnu — le handler appelle simplement `self.prompt_queue.get_history(prompt_id=prompt_id)` sans jamais fixer de statut d'erreur. Une `HTTPError` sur `/history` ne peut donc provenir ni d'un « prompt_id inconnu » (déjà et toujours un 200), ni d'aucun cas d'usage normal du protocole ComfyUI — uniquement d'une véritable exception serveur non gérée ou d'une couche réseau/proxy intermédiaire. C'est un signal d'autant plus important à ne jamais masquer derrière un timeout (voir §14).

## 6. Informations interdites dans le message

Ne jamais exposer automatiquement, dans le message de `ComfyUIEngineError` :
- le body JSON complet ;
- un body HTML complet ;
- `node_errors` (peut contenir des structures imbriquées volumineuses par node) ;
- `extra_info` ;
- `details` ;
- un traceback serveur ;
- les headers complets ;
- toute structure JSON brute non filtrée.

La correction doit notamment améliorer `/prompt`, qui peut aujourd'hui finir par dumper un dict d'erreur complet incluant `node_errors` dans le message de `submit()` (`f"ComfyUI rejected the workflow: {data}"`, `:100`) — ce dump n'est atteint aujourd'hui que parce que l'`HTTPError` a déjà été absorbée en amont ; après M151, `_request_json()` lèvera avant que `submit()` n'ait la moindre occasion de construire ce message (voir §13).

## 7. Body invalide ou vide sur `HTTPError`

Une `HTTPError` avec un corps non-JSON ou vide doit **toujours** produire immédiatement `ComfyUIEngineError` avec le code/reason HTTP — elle ne doit plus jamais être présentée comme une simple « invalid JSON response » indiscernable du cas 2xx-JSON-invalide (§3). Aujourd'hui, ce cas lève déjà (via `JSONDecodeError`), mais avec un message qui ne mentionne jamais qu'il s'agissait d'une erreur HTTP — cette confusion de message doit disparaître, sans changer le fait que l'exception est levée.

## 8. `URLError` / `OSError` / socket timeout — inchangés

Le comportement actuel de la clause `except (urllib.error.URLError, OSError) as error: raise ComfyUIEngineError(...)` (`:701-702`) est **conservé à l'identique**, sans changement de classification ni fusion de son message avec celui des `HTTPError`. Le mini-audit préalable a confirmé qu'en Python 3.10+, `socket.timeout` est un alias d'`OSError` — un timeout socket/réseau tombe donc déjà dans cette même clause et lève déjà correctement `ComfyUIEngineError`, confirmé par le test existant `test_list_checkpoints_raises_on_socket_timeout`.

## 9. Pas de retry

M151 ne crée **aucune** politique de retry HTTP. Toute `HTTPError` → fail-fast, sans exception. Explicitement non introduits : retry sur 5xx, retry sur 429, exponential backoff, compteur de tentatives, délai supplémentaire. Le polling métier `/history` (attendre que ComfyUI termine un travail légitime) reste un mécanisme entièrement distinct d'un éventuel retry réseau/HTTP (réessayer une requête ayant échoué au niveau transport) — le mini-audit a confirmé, par la source officielle (§5), que `/history` retourne toujours 200 y compris pour un `prompt_id` inconnu, donc une vraie `HTTPError` sur cet endpoint ne peut provenir que d'un incident serveur réel — un signal à surfacer immédiatement, jamais à masquer par un retry silencieux.

## 10. Interaction avec Mission 150 — séparation stricte préservée

- **HTTP 2xx** avec `status.status_str == "error"` → relève exclusivement du contrat Mission 150 (`_comfyui_execution_error_message()`), inchangé.
- **HTTP non-2xx** → relève désormais exclusivement du contrat M151 dans `_request_json()`, qui lève avant que `wait_for_result()` n'ait le moindre `data`/`entry` à examiner pour un éventuel `status`.

M151 ne modifie ni `_comfyui_execution_error_message()`, ni le failure predicate de M150 (`status_str == "error"`), ni la priorité error-before-image de `wait_for_result()`, ni `_first_image_reference()`. Les deux mécanismes restent strictement scopés à des couches différentes — transport HTTP (M151) vs statut métier applicatif porté par un body 200 (M150) — sans aucun chevauchement possible.

## 11. Les six call sites de `_request_json()`

Confirmé exhaustivement par le mini-audit préalable (grep, exactement 6, aucun autre) :

1. `submit()` (`:96`) → `POST /prompt`
2. `wait_for_result()` (`:140`) → `GET /history/{prompt_id}`
3. `upload_image()` (`:325`) → `POST /upload/image`
4. `list_checkpoints()` (`:379`) → `GET /object_info/CheckpointLoaderSimple`
5. `list_loras()` (`:430`) → `GET /object_info/LoraLoader`
6. `_list_ksampler_combo_values()` (`:490`, backing `list_samplers()`/`list_schedulers()`) → `GET /object_info/KSampler`

`download_output()` (`:242-247`) n'est **pas** un call site de `_request_json()` — il a déjà sa propre gestion inline correcte (`except HTTPError as error: raise ComfyUIEngineError(f"...HTTP {error.code}...")`) et reste hors scope.

M151 doit préserver le contrat métier 2xx de chacun des 6 call sites (§3). Confirmé par le mini-audit : **aucun** des 6 ne traite volontairement une réponse non-2xx comme une réponse métier normale — la centralisation dans `_request_json()` ne casse donc aucun comportement intentionnel.

## 12. `/prompt` — impact détaillé

Avant correction : `submit()` ne découvre un rejet HTTP que par ricochet — `data.get("prompt_id")` est absent du corps d'erreur absorbé, ce qui déclenche `raise ComfyUIEngineError(f"ComfyUI rejected the workflow: {data}")` (`:100`), un dump Python brut du dict entier (`error` + `node_errors`), sans jamais mentionner le vrai code HTTP.

Après correction : `_request_json()` lève directement dans le bloc `except HTTPError`, avant que `submit()` n'exécute son propre `data.get("prompt_id")` — le message contient le code HTTP réel (`400`) et, si disponible, `error.message` extrait selon la priorité 1 du §5, sans jamais dumper `node_errors`/`extra_info`/`details`. `submit()` ne doit plus dépendre de l'absence de `prompt_id` pour découvrir indirectement qu'une requête HTTP avait déjà échoué — cette voie de détection devient obsolète pour le cas HTTP, mais reste le seul mécanisme pertinent pour un 2xx qui rejetterait le workflow sans lever d'HTTPError (cas non observé dans la source, conservé par prudence, sans changement de comportement).

## 13. `/history` — impact détaillé

Avant correction : une `HTTPError` avec un corps JSON parseable pendant le polling est absorbée silencieusement — `entry = data.get(prompt_id)` retourne `None` (clé absente), le polling continue jusqu'à épuisement de `self._timeout`, aboutissant à `ComfyUIEngineError(f"Timed out waiting for ComfyUI result for prompt {prompt_id}")`, message générique ne mentionnant jamais qu'une erreur HTTP a été rencontrée.

Après correction : `_request_json()` lève dès le premier appel `/history` en erreur — la boucle `while True` de `wait_for_result()` n'a jamais l'occasion de continuer, aucun `time.sleep(poll_interval)` supplémentaire n'est exécuté, le timeout applicatif générique n'est jamais atteint pour ce cas. Le fail-fast doit être démontré par un test déterministe (call count sur le mock d'`urlopen`, assertion que `time.sleep` n'a jamais été appelé) — jamais par une mesure temporelle, exactement la même convention déjà établie par les 8 tests fail-fast de Mission 150.

## 14. Les quatre autres call sites — impact détaillé

`upload_image()`, `list_checkpoints()`, `list_loras()` et `_list_ksampler_combo_values()` (backing `list_samplers()`/`list_schedulers()`) doivent continuer à lever `ComfyUIEngineError` sur `HTTPError` — comportement déjà observable aujourd'hui pour ces 4 (bien que par accident, via une clé métier absente plutôt que via le code HTTP). M151 rend simplement cette levée explicite, centralisée dans `_request_json()`, et indépendante de la shape accidentelle du body reçu — aucune modification fonctionnelle supplémentaire de ces 4 méthodes n'est prévue au-delà de ce changement de fondation partagé. Tous les tests `assertRaises(ComfyUIEngineError)` existants sur ces 4 méthodes restent vrais sans modification.

## 15. Scope production prévu

Strictement : `src/engines/comfyui_engine.py`. La modification doit idéalement rester localisée à `_request_json()`. Un petit helper privé déterministe d'extraction/formatage du détail HTTP (mirroir de `_comfyui_execution_error_message()`) est autorisé si cela améliore réellement la lisibilité, mais reste optionnel — pas de nouvelle classe, pas de dataclass, pas d'abstraction réseau générale, pas de nouveau module. `submit()` ne doit être modifié que si strictement nécessaire pour éviter un message devenu redondant après la centralisation ; le mini-audit indique qu'une modification de `submit()` devrait probablement être inutile puisque `_request_json()` lèvera avant que son propre traitement métier (`data.get("prompt_id")`) ne soit jamais atteint pour le cas HTTPError.

## 16. Scope tests prévu

Strictement : `tests/integration/test_comfyui_engine.py`. Étendre les classes de test existantes (`ComfyUIEngineSubmitTest`, `ComfyUIEngineWaitForResultTest`, et ponctuellement `ComfyUIEngineUploadImageTest`/`ComfyUIEngineListCheckpointsTest`/`ComfyUIEngineListLorasTest`/`ComfyUIEngineListSamplersTest` pour la non-régression) plutôt que créer une nouvelle classe/infrastructure de test.

## 17. Matrice de tests M151

Au minimum, ces invariants (compacts, sans dupliquer ce que les tests historiques couvrent déjà) :

**A. HTTPError + JSON `/prompt`** — HTTP 400, body `{"error": {"message": "..."}}` → `ComfyUIEngineError`, message contient `400` et le texte utile, ne contient ni `node_errors` ni `extra_info` ni `details` bruts.

**B. HTTPError + JSON `/history`** — ex. HTTP 500, body JSON parseable → `ComfyUIEngineError` immédiate, un seul appel à `urlopen` (call-count == 1), aucun `time.sleep()` appelé.

**C. HTTPError + JSON premier niveau `message`** — fallback `{"message": "..."}` (priorité 2 du §5) correctement extrait.

**D. HTTPError + JSON sans champ textuel connu** — exception immédiate, code/reason présents dans le message, aucun dump du dict.

**E. HTTPError + JSON invalide** — exception immédiate, code HTTP présent dans le message, ne passe plus par le message générique « invalid response » du chemin 2xx.

**F. HTTPError + body vide** — exception immédiate, code HTTP présent dans le message.

**G. Garde de non-régression M150** — un HTTP 2xx contenant `status.status_str == "error"` continue d'emprunter exclusivement le mécanisme M150 ; le message reste celui de l'erreur d'exécution ComfyUI, jamais un message de type HTTPError.

**H. HTTP 2xx + JSON invalide** — comportement historique conservé ; peut être couvert par les tests existants (`test_submit_raises_on_invalid_json_response`, `test_list_checkpoints_raises_on_invalid_json_response`, etc.) s'ils démontrent déjà suffisamment l'invariant, sans duplication nécessaire.

Ne pas multiplier artificiellement les tests par call site pour la logique d'extraction elle-même (elle vit une seule fois dans `_request_json()`) — un test ciblé sur `submit()` (A, C, D, E, F) et un sur `wait_for_result()` (B, G) suffisent pour la logique complète, complétés par une vérification légère de non-régression sur les 4 autres call sites (§14).

## 18. Tests historiques à préserver

Ces tests existants doivent rester sémantiquement valides (leurs assertions `assertRaises(ComfyUIEngineError)` restent vraies) : `test_submit_raises_when_workflow_rejected`, `test_submit_raises_when_server_unreachable`, `test_submit_raises_on_invalid_json_response`, `test_wait_for_result_raises_when_server_unreachable`, `test_upload_image_raises_on_http_error_with_empty_body`, `test_upload_image_raises_when_server_unreachable`, `test_list_checkpoints_raises_on_http_error`, `test_list_checkpoints_raises_when_server_unreachable`, `test_list_checkpoints_raises_on_socket_timeout`, `test_list_loras_raises_on_http_error`, `test_list_loras_raises_when_server_unreachable`, `test_list_samplers_raises_on_http_error`, `test_list_samplers_raises_when_server_unreachable`, ainsi que les 15 tests de `ComfyUIEngineWaitForResultTest` couvrant le mécanisme Mission 150 (7 historiques + 8 Mission 150). Le mini-audit confirme qu'aucun de ces tests n'inspecte le contenu du message levé (uniquement `assertRaises`) — aucune réécriture massive n'est attendue ; un ajustement d'assertion n'est prévu que si un test venait à vérifier explicitement un message désormais volontairement amélioré.

## 19. Tests à exécuter pendant l'implémentation

Dans cet ordre : (1) tests M151 ciblés (nouvelles/étendues classes) ; (2) `tests/integration/test_comfyui_engine.py` complet ; (3) suites voisines pertinentes si rapides — `test_generation_manager.py`, `test_generation_worker.py`, et `test_inference_page.py` si raisonnable en durée ; (4) suite complète si tout est vert. Référence actuelle avant M151 : **2870/2870**, 0 échoué. Le total final sera déterminé par le nombre net réel de nouveaux tests ajoutés.

## 20. Non-goals (exclusions confirmées)

Politique de retry HTTP, exponential backoff, retry sur 429/5xx, nouvelles Settings timeout/retry, changement du polling métier `/history`, changement du timeout applicatif, Forge, OneTrainer, lifecycle managers, `GenerationManager`, `GenerationWorker`, `InferencePage`, l'angle mort filesystem M149 (`has_any_exposure()`), la garde New/Open Project vs génération en cours, la garde suppression LoRA Central Library vs génération active, la resync `ApplicationSettingsStorageError`, le rollback premier `save()` Workspace, les captions sidecar, la validation de path IDs Training/Dataset, le cleanup partiel de `create_job()`, le cycle de vie Character, tout refactor réseau général au-delà de `_request_json()`.

## 21. Risque

**Faible.** Modification bornée à une seule méthode partagée (`_request_json()`), déjà couverte par des tests existants sur ses 6 call sites (tous continuent de lever `ComfyUIEngineError`, aucune assertion de message actuelle à casser d'après le mini-audit) ; le chemin 2xx (succès et JSON invalide) reste totalement inchangé ; les erreurs réseau non-HTTP (`URLError`/`OSError`/timeout socket) restent inchangées ; aucune nouvelle dépendance ; aucune nouvelle politique de retry ; aucun call site ne dépend du comportement actuellement erroné (confirmé par lecture exhaustive pendant le mini-audit préalable).

## 22. Vérifications pré-rédaction effectuées

Relu avant rédaction de ce document : `_request_json()` et ses 6 call sites en intégralité (`comfyui_engine.py:79-102, 104-154, 255-339, 341-406, 408-450, 469-508, 687-707`), `_comfyui_execution_error_message()` (`:157-226`, Mission 150, confirmé non modifié par cette conception), `download_output()` (`:228-253`, confirmé hors scope, déjà correct), la totalité de `tests/integration/test_comfyui_engine.py` (structure des classes et tests existants pertinents listés en §18), ainsi que le contrat source officiel confirmé de `comfyanonymous/ComfyUI` (`execution.py::validate_prompt()`, `server.py` routes `POST /prompt` et `GET /history/{prompt_id}`) via le mini-audit READ-ONLY préalable, validé par ChatGPT.

## 23. Résultats réels (implémentation)

**Fichiers effectivement modifiés** — strictement les 2 fichiers annoncés, aucun autre :
- `src/engines/comfyui_engine.py` : +67/-1, un seul hunk. Dans `_request_json()` (`:687-720`), le bloc `except urllib.error.HTTPError as error:` ne fait plus `raw = error.read()` puis ne chute plus dans le `json.loads()`-vers-`return` partagé avec le chemin succès — il construit désormais un message (`f"ComfyUI request failed with HTTP {error.code} {error.reason}"`, optionnellement suffixé du détail extrait) et lève immédiatement `ComfyUIEngineError`. Nouvelle méthode statique privée `_comfyui_http_error_detail(error) -> Optional[str]` ajoutée juste après `_request_json()` (`:721-772`). Le chemin 2xx (`json.loads(raw)` / `JSONDecodeError`, `:718-720`), la clause `URLError`/`OSError` (`:715-716`), `_comfyui_execution_error_message()` (`:157-226`), le failure predicate M150, la priorité error-before-image, `_first_image_reference()`, `deadline`/`poll_interval`/la boucle de polling de `wait_for_result()`, et les 6 call sites eux-mêmes (`submit()`, `wait_for_result()`, `upload_image()`, `list_checkpoints()`, `list_loras()`, `_list_ksampler_combo_values()`) sont tous confirmés octet pour octet inchangés — un seul hunk dans le diff, vérifié.
- `tests/integration/test_comfyui_engine.py` : +130/-0, entièrement additif. 6 nouveaux tests insérés dans `ComfyUIEngineSubmitTest` juste après les 3 tests historiques (inchangés) ; 1 nouveau test inséré dans `ComfyUIEngineWaitForResultTest` juste après les 15 tests existants (7 historiques + 8 Mission 150, tous inchangés) et avant `ComfyUIEngineDownloadOutputTest`.

**Helper ajouté** : `_comfyui_http_error_detail(error: urllib.error.HTTPError) -> Optional[str]`, méthode statique privée, mirroir architectural direct de `_comfyui_execution_error_message()` (Mission 150) — mêmes conventions : priorité de champs fixes et confirmés par source, aucune recherche récursive, aucun fallback `str(data)`/sérialisation du dict, `None` systématique en cas d'échec d'extraction (jamais d'exception secondaire — `error.read()` est protégé par `except OSError`, `json.loads()` par `except JSONDecodeError`, chaque accès `.get()` protégé par un `isinstance(..., dict)` préalable).

**Aucun des 6 call sites n'a nécessité de modification** — confirmé par réinspection après implémentation (§13 du draft) : `_request_json()` lève désormais avant que `submit()`/`upload_image()`/`list_checkpoints()`/`list_loras()`/`_list_ksampler_combo_values()`/`wait_for_result()` n'atteignent leur propre traitement métier post-retour pour le cas `HTTPError` — aucune preuve concrète n'imposait d'adapter l'un d'eux. `download_output()` confirmé hors scope, non modifié.

**Comportement HTTPError + JSON utile** : le code HTTP et la reason apparaissent toujours dans le message ; si le body JSON est un dict contenant `error.message` (priorité 1, contrat `/prompt` confirmé par source) ou un `message` de premier niveau (priorité 2), ce texte est ajouté au message — jamais `node_errors`/`extra_info`/`details`/le dict complet. Démontré par `test_submit_http_error_message_includes_http_code_and_prompt_error_detail` (priorité 1, avec marqueurs uniques prouvant l'absence de fuite de `node_errors`/`extra_info`/`details`) et `test_submit_http_error_falls_back_to_top_level_message_field` (priorité 2).

**Comportement HTTPError + JSON sans champ textuel connu** : repli sur le code HTTP + reason seuls, aucun champ du body (même présent) n'est incorporé. Démontré par `test_submit_http_error_falls_back_to_code_and_reason_when_no_known_message_field`.

**Comportement HTTPError + JSON invalide** : `ComfyUIEngineError` immédiate avec le code HTTP, ne passe plus jamais par le message générique « invalid response » réservé au chemin 2xx. Démontré par `test_submit_http_error_with_invalid_json_body_still_raises_with_http_code`.

**Comportement HTTPError + body vide** : identique — `ComfyUIEngineError` immédiate avec le code HTTP, jamais « invalid response ». Démontré par `test_submit_http_error_with_empty_body_still_raises_with_http_code`. La `reason` HTTP (ex. « Internal Server Error ») est confirmée présente dans le message par `test_submit_http_error_message_includes_reason_when_exploitable`.

**Comportement 2xx (succès, JSON invalide, body vide)** : confirmé intégralement inchangé — même chemin de code, mêmes messages, aucune ligne modifiée dans cette portion de `_request_json()`. Les 3 tests historiques de `ComfyUIEngineSubmitTest` couvrant ce chemin restent verts sans modification.

**`URLError`/`OSError`/timeout socket** : confirmés inchangés — clause non touchée par le diff, mêmes messages, classification identique. `test_submit_raises_when_server_unreachable`, `test_list_checkpoints_raises_on_socket_timeout` et équivalents restent verts sans modification.

**Interaction M150** : séparation confirmée intacte par le diff (aucune ligne touchée dans `_comfyui_execution_error_message()`/le failure predicate/la priorité error-before-image/`_first_image_reference()`/le polling) et par les tests : les 15 tests de `ComfyUIEngineWaitForResultTest` couvrant le mécanisme M150 (7 historiques + 8 Mission 150) restent verts sans aucune modification de leur code, prouvant par re-confirmation qu'un HTTP 2xx avec `status.status_str == "error"` continue d'emprunter exclusivement le mécanisme M150 — aucun nouveau test dédié à cette garde n'a été ajouté pour éviter une redondance avec cette couverture déjà exhaustive (cohérent avec §14/§17 du draft : « évite les tests redondants »).

**État des six call sites après implémentation** :
1. `submit()` → `/prompt` : inchangé, bénéficie du nouveau message centralisé.
2. `wait_for_result()` → `/history/{prompt_id}` : inchangé, bénéficie du fail-fast centralisé (voir test dédié ci-dessous).
3. `upload_image()` → `/upload/image` : inchangé, `test_upload_image_raises_on_http_error_with_empty_body` reste vert.
4. `list_checkpoints()` → `/object_info/CheckpointLoaderSimple` : inchangé, `test_list_checkpoints_raises_on_http_error` reste vert.
5. `list_loras()` → `/object_info/LoraLoader` : inchangé, `test_list_loras_raises_on_http_error` reste vert.
6. `_list_ksampler_combo_values()` → `/object_info/KSampler` : inchangé, `test_list_samplers_raises_on_http_error` reste vert.

**Tests ajoutés** : **7 tests nets**. Dans `ComfyUIEngineSubmitTest` (6) : `test_submit_http_error_message_includes_http_code_and_prompt_error_detail`, `test_submit_http_error_falls_back_to_top_level_message_field`, `test_submit_http_error_falls_back_to_code_and_reason_when_no_known_message_field`, `test_submit_http_error_with_invalid_json_body_still_raises_with_http_code`, `test_submit_http_error_with_empty_body_still_raises_with_http_code`, `test_submit_http_error_message_includes_reason_when_exploitable`. Dans `ComfyUIEngineWaitForResultTest` (1) : `test_wait_for_result_fails_fast_on_http_error_during_polling` — prouve le fail-fast par `mock_urlopen.assert_called_once()`/`mock_sleep.assert_not_called()`, jamais par mesure de durée, exactement la convention déjà établie par Mission 150.

**Résultats ciblés** :
- `ComfyUIEngineSubmitTest` + `ComfyUIEngineWaitForResultTest` : **27/27 passés** (11 + 16), 0.054s.
- `tests/integration/test_comfyui_engine.py` complet : **117/117 passés** (110 avant M151 + 7 nets), 1.720s.

**Résultats voisins (propagation/non-régression)** :
- `tests/integration/test_generation_manager.py` + `tests/integration/test_generation_worker.py` : **91/91 passés** — chaîne `GenerationManager`/`GenerationWorker` non modifiée, non-régression confirmée, `ComfyUIEngineError` continue de se propager sans transformation.
- `tests/integration/test_inference_page.py` (complet, widgets Qt réels) : **230/230 passés** (201.949s) — un traceback bénin préexistant (`QLabel.setText(MagicMock)`, déjà documenté depuis Mission 150 comme non-régression noise, sans rapport avec `comfyui_engine.py`) observé pendant l'exécution, suite toujours `OK`.

**Résultat suite complète** : **2877/2877 collectés/passés, 0 échoué**, exit 0, 322.639s. Équation : 2870 (clôture Mission 150) + 7 nets ajoutés par Mission 151 = **2877**, cohérent. Les lignes `Failed to copy .../disk full/...` interlignées dans la sortie sont des logs attendus de tests d'échec simulé déjà existants ailleurs dans la suite (Workspace, LoRA Library, Dataset), sans aucun rapport avec Mission 151.

**`git diff --check`** : clean, exit 0 (avertissement `LF will be replaced by CRLF` uniquement — normalisation de fin de ligne, non bloquant).

**`git status --short`** : exactement les 2 fichiers M151 modifiés (`src/engines/comfyui_engine.py`, `tests/integration/test_comfyui_engine.py`) + `docs/missions/MISSION_151.md` (déjà présent en `??` depuis le draft) — aucun fichier hors scope, `graphify-out/` inchangé par cette session (modifications préexistantes non liées).

**Écarts par rapport au draft** : aucun. L'implémentation suit exactement le contrat des §1-§21 sans déviation. `submit()` n'a nécessité aucune modification, exactement comme anticipé par le mini-audit préalable (§16/§20 du draft).

**Findings inattendus** : aucun. Aucune découverte nécessitant un élargissement de scope.

**Rappel explicite** : la GitHub Release n'est pas publiée à ce stade — clôture Git en attente de validation. Aucun commit, aucun push, aucun tag créés par cette implémentation.
