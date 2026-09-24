# Mission 150 — Fail Fast on ComfyUI Terminal Execution Errors

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente.** `ComfyUIEngine.wait_for_result()` (`src/engines/comfyui_engine.py`) détectait le succès uniquement via la présence d'une image exploitable dans `outputs` — il ignorait totalement le statut terminal officiel que ComfyUI fournit déjà dans le même appel `/history/{prompt_id}` (`status.status_str`). Un crash réel de node ComfyUI était donc indiscernable de « pas encore prêt » et le Toolkit continuait de poller jusqu'au timeout applicatif générique (~120s), masquant l'erreur réelle derrière un message de timeout non informatif. M150 ajoute une détection positive, minimale et rétrocompatible de cet échec terminal, sans toucher au contrat de succès historique ni à aucun fichier hors de `src/engines/comfyui_engine.py`. Voir §22 pour le scope exact, §3 pour la démonstration du contrat ComfyUI réel confirmé par lecture directe du code source officiel, et §23 pour les résultats réels de l'implémentation.

## 1. Root cause

`ComfyUIEngine.wait_for_result()` (`src/engines/comfyui_engine.py:104-130`) poll `GET /history/{prompt_id}` et détermine le succès exclusivement par :
```python
entry = data.get(prompt_id)
if entry and entry.get("outputs") and self._first_image_reference(entry["outputs"]) is not None:
    return entry["outputs"]
```
Aucune lecture de `entry.get("status")` n'existe nulle part dans la méthode ni dans `_first_image_reference()` (`:574-589`). Le history entry ComfyUI porte pourtant un statut terminal explicite (`status.status_str`), confirmé par lecture directe du code source officiel `comfyanonymous/ComfyUI` (`execution.py`/`main.py`, branche `main`) pendant le mini-audit préalable — pas inféré :

```python
class ExecutionStatus(NamedTuple):
    status_str: Literal['success', 'error']
    completed: bool
    messages: List[str]
```

construit dans `main.py` via :
```python
status=execution.PromptQueue.ExecutionStatus(
    status_str='success' if e.success else 'error',
    completed=e.success,
    messages=e.status_messages)
```

Lorsqu'un node crashe réellement en cours d'exécution, `status_str` vaut `"error"` dès l'entrée `/history` suivante — mais Toolkit continue de poller jusqu'au timeout générique de `self._timeout` (120s par défaut), au lieu de fail-fast avec l'information déjà disponible dans la même réponse HTTP qu'il interroge déjà.

## 2. Contrat fondamental M150

Ajouter dans `wait_for_result()` une détection **positive uniquement** de l'échec terminal :

```
entry.status.status_str == "error"  →  fail fast avec ComfyUIEngineError
```

Toute absence ou valeur inconnue de ce champ **conserve intégralement le comportement historique** — jamais transformé en erreur simplement parce qu'un succès n'est pas encore prouvé :
- `status` absent
- `status` présent sans `status_str`
- `status_str` à une valeur inconnue (ni `"success"` ni `"error"`)
- `entry` sans `outputs`

Le timeout existant (`self._timeout`, inchangé) reste l'unique filet de sécurité pour tout état non reconnu ou non terminal.

## 3. Ordre obligatoire de la boucle de polling

Pour chaque history entry reçue, dans cet ordre exact :

1. Détecter un éventuel `status.status_str == "error"`.
2. Si échec terminal détecté : lever immédiatement `ComfyUIEngineError` (voir §6-§8 pour le contenu du message) — **avant** toute autre vérification.
3. Sinon, appliquer le critère de succès historique inchangé (`_first_image_reference()` sur `outputs`).
4. Sinon, continuer le polling (`time.sleep(poll_interval)`, re-vérifier le `deadline`).

La détection d'échec doit donc **précéder** le retour d'un output image dans le code — voir §4 pour la justification.

## 4. Contradiction `outputs` valides + `status_str == "error"`

Si une réponse contient simultanément une image exploitable dans `outputs` **et** `status.status_str == "error"`, **l'échec terminal prime** — l'image n'est jamais retournée.

Justification confirmée par le contrat source réel (pas une supposition) : `status_str`/`completed` dérivent de `e.success`, un indicateur qui résume si le **graphe entier** s'est terminé sans exception non gérée — pas si un node isolé en amont a produit un output. Un node de prévisualisation exécuté avec succès avant qu'un node d'upscale ultérieur ne crashe laisserait un `outputs` non vide alors que le graphe soumis, dans son ensemble, n'a jamais atteint son résultat final voulu. Retourner cette image partielle comme si elle était le résultat serait trompeur.

## 5. Succès — contrat historique préservé, non redéfini

Le succès **n'est jamais redéfini** autour de `status_str == "success"`. Le critère historique reste : une image exploitable trouvée par `_first_image_reference()` dans `outputs` permet le retour des outputs, **tant qu'aucune erreur terminale explicite (§2-§4) n'a été détectée en premier**. Ceci préserve la compatibilité intégrale avec :
- les anciennes réponses ComfyUI sans champ `status` ;
- d'éventuels forks ComfyUI ;
- toute réponse partielle où `status` serait absent mais `outputs` déjà exploitable.

## 6. États inconnus — comportement historique préservé

Les cas suivants continuent de poller exactement comme aujourd'hui, sans aucun nouveau délai ni nouveau timer :
- `status` absent
- `status_str` absent
- `status_str` à une valeur inconnue
- `completed` absent ou non lu (voir §7)
- `entry` sans `outputs`
- `outputs` sans image exploitable

Ils continuent jusqu'à : apparition d'une image exploitable, apparition d'un échec terminal explicite, erreur réseau déjà gérée (`ComfyUIEngineError` immédiat existant, inchangé), ou expiration du timeout existant.

## 7. `completed` — non utilisé, delibérément

Le predicate d'échec ne dépend **pas** de `status.completed`. Le mini-audit préalable a confirmé par lecture du code source officiel que `completed` est directement dérivé de la même variable (`e.success`) que `status_str`, au même instant — redondant en pratique. Le predicate reste minimal et strictement basé sur `status_str == "error"`, pour rester aussi rétrocompatible et robuste que possible face à un éventuel fork qui découplerait un jour ces deux champs.

## 8. Extraction du message d'erreur

Sur `status_str == "error"`, inspecter `status.messages` — une liste d'entrées `[event_name, data]` (tuple ou liste JSON), confirmée par lecture du code source officiel (`PromptExecutor.add_message()`/`handle_execution_error()`).

**A. `execution_error` (priorité 1)** : si une entrée dont l'`event_name == "execution_error"` est trouvée, utiliser les champs disponibles de son `data`, principalement `node_type` et `exception_message`. Message conceptuel :
```
ComfyUI execution failed on node '<node_type>': <exception_message>
```
Le code doit rester défensif si un champ manque (voir §10).

**B. `execution_interrupted` (priorité 2)** : si aucune entrée `execution_error` exploitable n'est trouvée mais qu'une entrée `execution_interrupted` est présente, produire un message **explicitement différent**, indiquant que l'exécution a été interrompue plutôt qu'un crash de node — utiliser `node_type` si disponible. Ne jamais présenter une interruption externe comme un crash de node : le contrat source (§1) confirme que `status_str == "error"` couvre indifféremment un vrai crash **et** une interruption ComfyUI externe (`/interrupt` appelé hors Toolkit) — seule la présence de `execution_interrupted` (sans champs d'exception) plutôt que `execution_error` permet de distinguer les deux cas.

**C. Fallback (priorité 3)** : si `status_str == "error"` mais qu'aucune entrée reconnue/exploitable n'est disponible dans `messages`, lever tout de même immédiatement `ComfyUIEngineError` avec un message générique court indiquant que ComfyUI a signalé un échec d'exécution pour ce `prompt_id`. Un history entry explicitement terminal `"error"` doit **toujours** aboutir à une exception, au minimum avec ce fallback.

## 9. Robustesse de l'extraction — jamais d'exception secondaire

L'extraction du message ne doit jamais elle-même provoquer une exception non gérée, quelle que soit la malformation de la structure rencontrée :
- `messages` absent ;
- `messages` n'est pas une liste ;
- une entrée est mal formée (pas un couple `[event_name, data]`) ;
- `data` absent ou n'est pas un dict ;
- `node_type` absent ;
- `exception_message` absent.

Dans tous ces cas, retomber sur le fallback générique du §8.C plutôt que de laisser une `KeyError`/`TypeError`/`IndexError` remonter à la place de `ComfyUIEngineError`.

## 10. Informations à ne jamais afficher à l'utilisateur

Ne jamais copier automatiquement dans le message final :
- `traceback` (liste de chaînes, potentiellement volumineuse) ;
- `current_inputs` / `current_outputs` (structures de debug volumineuses) ;
- le JSON complet de `status`/`history`.

Concernant `exception_message` : **aucune limite de troncature arbitraire (ex. 300 caractères) n'est fixée par ce contrat.** Recherche effectuée pendant la rédaction : aucune convention de troncature de message existante n'a été trouvée ailleurs dans `src/engines/` (`ForgeEngineError`, `ComfyUIEngineError` existants ne tronquent jamais leurs messages). En l'absence de précédent, `exception_message` est conservé tel quel, sans troncature.

## 11. Propagation vers l'UI — confirmée suffisante, aucun autre fichier modifié

Chaîne tracée intégralement pendant le mini-audit préalable :
```
ComfyUIEngine.wait_for_result()  (lève ComfyUIEngineError)
  → GenerationManager.generate()  (generation_manager.py:312-313, catch (ComfyUIEngineError, ForgeEngineError) → raise GenerationError(str(error)), message préservé verbatim)
  → GenerationWorker.run()  (generation_worker.py:132-134, catch GenerationError → self.failed.emit(str(error)), message préservé)
  → InferencePage._on_generation_failed(message)  (inference_page.py:1434-1450, QMessageBox.critical(self, "Erreur de génération", message), affichage direct sans transformation)
```
Confirmé : lever `ComfyUIEngineError` avec un message informatif suffit intégralement pour que l'UI l'affiche correctement. **M150 ne modifie ni `GenerationManager`, ni `GenerationWorker`, ni `InferencePage`.**

## 12. Scope production

Prévu, exclusivement : `src/engines/comfyui_engine.py`, limité à `wait_for_result()` et, seulement si cela améliore réellement la lisibilité/testabilité, un petit helper privé d'extraction du message (ex. une fonction/méthode statique dédiée à l'analyse de `status.messages`). **Aucune nouvelle abstraction générale d'erreurs moteur** — `ComfyUIEngineError` existant est réutilisé tel quel, jamais renommé, jamais remplacé par une hiérarchie d'exceptions.

## 13. Scope tests

Prévu, exclusivement : `tests/integration/test_comfyui_engine.py`. La classe existante `ComfyUIEngineWaitForResultTest` (`:120-217`) doit être étendue — **aucun nouveau fichier de test créé.**

## 14. Tests historiques à préserver

Les 7 tests actuels de `ComfyUIEngineWaitForResultTest` doivent rester sémantiquement inchangés :
1. `test_wait_for_result_returns_outputs_when_already_ready`
2. `test_wait_for_result_polls_until_ready`
3. `test_wait_for_result_times_out_without_result`
4. `test_wait_for_result_raises_when_server_unreachable`
5. `test_wait_for_result_does_not_stop_on_outputs_without_images_key`
6. `test_wait_for_result_does_not_stop_on_empty_images_list`
7. `test_wait_for_result_does_not_stop_on_image_reference_missing_filename`

Aucun de ces 7 tests n'inclut de clé `"status"` dans ses réponses simulées — vérifié pendant le mini-audit préalable. Le nouveau predicate d'échec (`entry.get("status", {}).get("status_str") == "error"`) évaluera systématiquement à faux pour ces 7 fixtures (clé absente), laissant tomber inchangé sur la logique existante. Ils servent notamment de preuve de rétrocompatibilité pour les réponses sans `status` — ne pas les réécrire inutilement.

## 15. Matrice de tests M150 à prévoir

Au minimum, ces 7 cas (compacts, sans dupliquer les invariants déjà couverts par les 7 tests historiques — status absent, timeout, succès image-based, polling) :

1. `status_str == "error"` + entrée `execution_error` détaillée (`node_type`, `exception_message`) → fail fast, `ComfyUIEngineError`, message contient le détail utile.
2. `status_str == "error"` + entrée `execution_interrupted` (sans `execution_error`) → fail fast, message explicitement distinct d'un crash de node.
3. `status_str == "error"` sans aucune entrée `messages` exploitable → fail fast avec le message de repli générique.
4. `status_str == "error"` **avec** `outputs`/image exploitable présents simultanément → l'erreur prime, l'image n'est jamais retournée.
5. `status_str` à une valeur inconnue (ni `"success"` ni `"error"`) → pas de fail-fast, comportement image-based historique inchangé.
6. Structure `messages`/`data` malformée ou inattendue (liste absente, entrée non conforme, `data` non-dict, champs manquants) → aucune exception secondaire, retombe sur le fallback générique de `ComfyUIEngineError`.
7. Le message final, dans le cas `execution_error`, ne contient jamais `traceback`/`current_inputs`/`current_outputs`.

## 16. Fail-fast réellement démontré (pas un timeout déguisé)

Les tests d'erreur doivent prouver que l'exception est levée dès la **première** réponse history explicitement terminale reçue par le polling — pas après expiration du timeout avec un meilleur message. Utiliser des doubles/mocks déterministes (`side_effect` sur `urllib.request.urlopen`, mêmes conventions que les tests existants), aucun `time.sleep()` réel/arbitraire (patché comme dans les tests existants).

## 17. Erreurs HTTP pendant le polling — explicitement hors scope

Le mini-audit préalable a découvert, séparément, que `_request_json()` peut lire le corps JSON d'une `HTTPError` survenant pendant `/history` comme une réponse normale (au lieu de la relever) — un finding distinct, non lié à la détection du statut terminal `status_str`. **M150 ne modifie ni `_request_json()`, ni le traitement `HTTPError`, ni la soumission `/prompt`, ni aucun timeout réseau/socket, ni le budget global de polling.** Ce finding est conservé pour un audit/une mission ultérieure.

## 18. Non-goals (exclusions confirmées)

Timeout Forge/génération async Forge, processus OneTrainer orphelin, Jobs `unknown`, angle mort filesystem `PermissionError`/`OSError` de M149 (`has_any_exposure()`), verrou Settings pendant `RUNNING_OWNED`, resync UI sur `ApplicationSettingsStorageError`, rollback Workspace premier `save()`, caption sidecars, validation de path `training_id`/`dataset_id`, cleanup partiel de `create_job()`, Resume/process identity, cascade de suppression Character, alias LoRA historiques orphelins, flakiness des tests Forge lifecycle, tout refactor général de `ComfyUIEngine` au-delà de `wait_for_result()`, toute nouvelle infrastructure de logging.

## 19. Risque

**Faible.** Le predicate d'échec est positif et explicite (`status_str == "error"` uniquement) ; toute absence/valeur inconnue conserve l'ancien comportement ; le contrat de succès historique reste inchangé ; la propagation UI est déjà confirmée compatible sans modification ; le scope est limité à une seule méthode d'un seul moteur et à son fichier de test existant.

Point à surveiller, non un risque de régression mais une nuance produit à formuler clairement dans le message : le cas `execution_interrupted` peut provenir d'une interruption ComfyUI externe au Toolkit (ex. quelqu'un appelle `/interrupt` directement sur l'instance ComfyUI pendant qu'un Job Toolkit est en file). Le message doit signaler correctement que l'exécution a été interrompue, sans prétendre que le Toolkit lui-même en est nécessairement la cause.

## 20. Tests à exécuter pendant l'implémentation

Au minimum, dans cet ordre : (1) `ComfyUIEngineWaitForResultTest` seule ; (2) `tests/integration/test_comfyui_engine.py` complet ; (3) suites voisines Generation/Inference pertinentes si elles existent et sont rapides ; (4) suite complète si tout est vert. Référence actuelle avant M150 : **2862/2862**, 0 échoué.

## 21. Vérifications pré-rédaction effectuées

Relu avant rédaction de ce document : `ComfyUIEngine.wait_for_result()` et `_first_image_reference()` (`src/engines/comfyui_engine.py:104-130`, `:574-589`), `ComfyUIEngineError` (`:59-60`), les 7 tests actuels de `ComfyUIEngineWaitForResultTest` (`tests/integration/test_comfyui_engine.py:120-217`), et la chaîne de propagation `GenerationManager.generate()` (`generation_manager.py:280-317`) → `GenerationWorker.run()` (`generation_worker.py:100-139`) → `InferencePage._on_generation_failed()` (`inference_page.py:1434-1450`) — confirmé qu'aucun de ces trois derniers fichiers n'a besoin d'être modifié.

## 22. Résultats réels (implémentation)

**Fichiers effectivement modifiés** — strictement les 3 fichiers annoncés, aucun autre :
- `src/engines/comfyui_engine.py` : +99/-3. `wait_for_result()` gagne un appel à `self._comfyui_execution_error_message(entry.get("status"), prompt_id)`, exécuté avant le test image-based existant, ainsi qu'un garde `isinstance(data, dict)`/`isinstance(entry, dict)` explicite avant tout accès `.get()` (défense demandée §3/§10 du draft). Nouvelle méthode statique privée `_comfyui_execution_error_message(status, prompt_id) -> Optional[str]` ajoutée juste après `wait_for_result()`. `_request_json()`, `submit()`, `download_output()`, `_first_image_reference()`, `generate_image()`, `_submit_and_download()` tous confirmés octet pour octet inchangés (seul hunk du diff, vérifié).
- `tests/integration/test_comfyui_engine.py` : +219/-0, entièrement additif — 8 nouveaux tests insérés dans `ComfyUIEngineWaitForResultTest`, juste après les 7 tests historiques (inchangés) et avant `ComfyUIEngineDownloadOutputTest`. Aucun import supplémentaire nécessaire (`ComfyUIEngine`/`ComfyUIEngineError` déjà importés).
- `docs/missions/MISSION_150.md` : banner + présente section.

**Implémentation exacte du failure predicate** : `isinstance(status, dict)` puis `status.get("status_str") != "error"` → `None` (état inconnu, comportement historique) sinon poursuite de l'extraction — jamais une comparaison de vérité simple, toujours une garde de type explicite en premier (convention CLAUDE.md respectée).

**Ordre failure-before-image** : confirmé dans le diff — `error_message = self._comfyui_execution_error_message(...)` est évalué et son `raise` potentiel exécuté **avant** la ligne `if entry.get("outputs") and self._first_image_reference(...)`, à l'intérieur du même bloc `if isinstance(entry, dict):`.

**Stratégie `execution_error`** : recherche de la première entrée `messages` dont `event_name == "execution_error"` et dont `data` est un dict ; 4 branches selon les champs réellement présents (`node_type` + `exception_message`, `exception_message` seul, `node_type` seul, ni l'un ni l'autre → repli générique nommant `prompt_id`) — jamais de formulation dégradée du type `on node 'None': None`.

**Stratégie `execution_interrupted`** : recherche en second (seulement si aucune `execution_error` exploitable), 2 branches (`node_type` présent ou non), message toujours distinct ("interrupted", jamais "failed"), jamais présenté comme causé par le Toolkit.

**Fallback** : `status_str == "error"` sans aucune entrée `execution_error`/`execution_interrupted` exploitable (messages absents/vides/malformés) → message générique nommant `prompt_id`, toujours levé, jamais d'exception secondaire.

**Robustesse `status`/`messages` malformés** : `status` non-dict (chaîne, liste, `null`, nombre) → `None` immédiat (état inconnu). `messages` non-liste → traité comme liste vide (repli générique atteint). Chaque entrée de `messages` validée individuellement (`isinstance(message, (list, tuple))` et `len(message) == 2`) avant déballage ; `data` validé `isinstance(data, dict)` avant tout `.get()`. Aucune de ces vérifications ne peut lever `AttributeError`/`TypeError`/`IndexError` — confirmé par test dédié avec des entrées délibérément malformées mélangées à une entrée valide.

**Confirmation success predicate historique inchangé** : `_first_image_reference()` non modifiée, aucune ligne touchée ; le succès reste basé exclusivement sur une image exploitable dans `outputs`, jamais sur `status_str == "success"` — testé explicitement (`status_str` inconnu + image → succès identique au comportement historique).

**Confirmation timeout/polling inchangés** : `self._timeout`, `deadline = time.monotonic() + self._timeout`, `poll_interval`, `time.sleep(poll_interval)` tous confirmés non modifiés dans le diff.

**Confirmation `_request_json()` inchangé** : confirmé — zéro hunk sur cette méthode, zéro changement au traitement `HTTPError`/JSON, zéro changement à `/prompt`, zéro changement de timeout socket.

**Tests ajoutés** : **8 tests nets** dans `ComfyUIEngineWaitForResultTest` : `execution_error` détaillé (couvre aussi l'absence de traceback/current_inputs/current_outputs dans le message et le fail-fast par call-count), `execution_interrupted`, repli générique sans message exploitable, contradiction outputs+error (priorité à l'erreur), `status_str` inconnu (succès image-based préservé), `status` non-dict traité comme état inconnu, entrées `messages` malformées mélangées à une entrée valide (aucune exception secondaire), `messages` non-liste (aucune exception secondaire).

**Résultats ciblés** :
- `ComfyUIEngineWaitForResultTest` seule : **15/15 passés** (7 historiques + 8 nouveaux), 0.030s.
- `tests/integration/test_comfyui_engine.py` complet : **110/110 passés** (102 avant M150 + 8 nets), 0.838s.

**Résultats voisins (propagation/non-régression)** :
- `tests/integration/test_generation_manager.py` + `tests/integration/test_generation_worker.py` : **91/91 passés** — chaîne `GenerationManager`/`GenerationWorker` non modifiée, non-régression confirmée.
- `tests/integration/test_inference_page.py` (complet, widgets Qt réels) : **230/230 passés** (196.915s) — un traceback bénin préexistant (`QLabel.setText(MagicMock)`) observé pendant l'exécution, déjà documenté et reconfirmé non lié (aucun rapport avec `comfyui_engine.py`), suite toujours `OK`.

**Résultat suite complète** : **2870/2870 collectés/passés, 0 échoué**, exit 0, 355.686s. Équation : 2862 (clôture Mission 149) + 8 nets ajoutés par Mission 150 = **2870**, cohérent. Les lignes `Failed to copy .../disk full/...`/`LoRA library registry file ... does not contain a JSON object` interlignées dans la sortie sont des logs attendus de tests d'échec simulé déjà existants ailleurs dans la suite (LoRA Library, Workspace, Dataset), sans aucun rapport avec Mission 150.

**`git diff --check`** : clean, exit 0 (avertissements `LF will be replaced by CRLF` uniquement — normalisation de fin de ligne, non bloquants).

**`git status --short`** : exactement les 3 fichiers M150 (2 modifiés + 1 documentation) — aucun fichier hors scope, `graphify-out/` inchangé par cette session.

**Écarts par rapport au draft** : aucun. L'implémentation suit exactement le contrat du §2-§18 sans déviation.

**Findings inattendus** : aucun. Aucune découverte nécessitant un élargissement de scope.

**Non-goals confirmés** : `_request_json()`, soumission `/prompt`, timeouts réseau/socket, budget global de polling, `GenerationManager`, `GenerationWorker`, `InferencePage`, Settings, lifecycle managers — tous confirmés non modifiés par lecture directe du diff complet. Le finding distinct concernant le traitement `HTTPError` pendant `/history` (`_request_json()`) reste ouvert, non traité par cette mission, conformément au §17/§18 de la conception.

**Rappel explicite** : M150 ne corrige pas et ne prétend pas corriger le finding séparé sur `_request_json()`/`HTTPError` pendant `/history`. La GitHub Release n'est pas publiée à ce stade — clôture Git en attente de validation.
