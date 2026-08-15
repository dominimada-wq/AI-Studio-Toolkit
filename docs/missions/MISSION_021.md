# Mission 021 — ComfyUI Image Upload

Source : audit read-only préalable (Mission 021 Phase 1, état Git, code réel `src/engines/comfyui_engine.py`/`tests/integration/test_comfyui_engine.py`), vérification du contrat réel de l'endpoint ComfyUI `POST /upload/image` (documentation officielle + code source `server.py`, aucune supposition non vérifiée), spécification validée par l'architecte, implémentation réalisée et vérifiée par exécution réelle de la suite de tests complète. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur ici — les sections "Commit correspondant"/"Tag / release correspondant" ci-dessous restent en attente : la clôture Git de Mission 021 n'a pas encore eu lieu à ce stade (implémentation et documentation validées, pas encore commitées).

## Contexte

`ComfyUIEngine` (`src/engines/comfyui_engine.py`) expose trois primitives génériques depuis Mission 012 (`submit`/`wait_for_result`/`download_output`), toutes construites sur `urllib.request` (stdlib uniquement, aucune dépendance HTTP externe). Aucune des trois ne permet d'envoyer un fichier local vers l'instance ComfyUI — seul le sens `ComfyUI → AI Studio Toolkit` (téléchargement du résultat) existe aujourd'hui. Toute utilisation future d'une image locale par un workflow ComfyUI distant (img2img, IP-Adapter, ControlNet, ou tout autre mécanisme non encore choisi) nécessite d'abord ce transfert : un node `LoadImage` côté ComfyUI ne peut référencer qu'un fichier déjà présent sur le serveur, jamais un chemin de la machine cliente.

## Problème constaté

Aucune primitive de transport `AI Studio Toolkit → ComfyUI` n'existe. Ce manque bloque structurellement tout besoin futur d'image d'entrée (identifié dans `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés par l'usage réel" — reference image), quel que soit le mécanisme de génération finalement choisi (img2img, IP-Adapter, ControlNet, ou un usage encore non anticipé).

## Objectif

Ajouter à `ComfyUIEngine` une primitive de transport, `upload_image()`, permettant d'envoyer un fichier image local vers l'instance ComfyUI, afin qu'il devienne référençable par un futur workflow. Cette mission reste strictement Infrastructure : aucune sémantique de rôle, aucune orchestration multi-image, aucun branchement dans un workflow réel.

## Contrainte de conception — compatibilité 1..N images futures

Un besoin fonctionnel futur (non implémenté ici) est qu'une génération puisse utiliser une ou plusieurs images d'entrée, chacune pouvant avoir un rôle sémantique distinct (identité, planche de personnage, vêtement, décor, pose...) et un mécanisme moteur distinct (img2img, IP-Adapter, ControlNet, FaceID...). `upload_image()` doit rester une primitive de **transport pur**, strictement indépendante de toute notion de rôle ou d'orchestration :

- Elle ne connaît et ne doit jamais connaître de concept de "rôle" (identité, vêtement, décor...) — cette responsabilité appartiendra à une future couche d'orchestration, non conçue ici.
- Elle ne connaît et ne doit jamais connaître le mécanisme moteur final (img2img, IP-Adapter, ControlNet...) — cette responsabilité appartiendra à une future couche de construction de workflow, non conçue ici.
- Elle ne conserve **aucun état d'instance propre à cette méthode** (`ComfyUIEngine` ne gagne aucun nouvel attribut `self._...` pour ce besoin) : chaque appel à `upload_image(file_path)` est strictement indépendant des autres. Rien n'empêche structurellement de l'appeler une fois, deux fois, ou N fois pour une même génération future — sans qu'aucune modification de `upload_image()` elle-même ne soit nécessaire pour cela.
- Elle ne construit pas de méthode `upload_images()` batch : le protocole ComfyUI vérifié (voir ci-dessous) n'expose qu'un endpoint unitaire (`POST /upload/image`, un fichier par requête) — aucun endpoint batch natif n'existe. Un futur besoin de N images s'obtiendra par N appels indépendants à la primitive unitaire, jamais par une nouvelle primitive batch construite par anticipation.

Ce besoin multi-image/multi-rôle est documenté ici uniquement comme contexte — **aucun modèle, enum, ou abstraction n'a été créé pour lui dans cette mission.**

**Propriété architecturale réellement vérifiée** : `upload_image()` n'écrit aucun attribut d'instance sur `ComfyUIEngine` — vérifié empiriquement par `test_upload_image_two_independent_calls_produce_two_independent_results` (deux fichiers locaux distincts, deux réponses ComfyUI mockées distinctes, deux résultats corrects et indépendants, aucune interférence). La méthode reste appelable N fois, sans qu'aucune modification d'`upload_image()` elle-même ne soit nécessaire pour un futur besoin de plusieurs images (portrait, planche de référence, vêtement, décor, pose, ou tout autre rôle futur) — `ComfyUIEngine` ne connaît et ne conserve aucune notion de rôle.

## Contrat ComfyUI vérifié

Vérifié directement contre le code source de `server.py` (dépôt officiel `comfyanonymous/ComfyUI`, fonction partagée `image_upload()` utilisée par les deux routes `POST /upload/image` et `POST /upload/mask`) :

**Requête** — `multipart/form-data`, champs lus par le serveur :
- `image` (fichier) — champ obligatoire ; le serveur renvoie `HTTP 400` (corps vide, sans JSON) si absent ou illisible.
- `type` (texte, optionnel) — `"input"` / `"output"` / `"temp"` ; toute valeur non reconnue (y compris absente) retombe silencieusement sur `"input"` côté serveur (`get_dir_by_type()`), sans erreur.
- `subfolder` (texte, optionnel) — sous-dossier relatif sous le répertoire du `type` choisi ; créé automatiquement (`os.makedirs`) s'il n'existe pas. Le serveur valide que le chemin résolu reste sous le répertoire racine (protection path traversal) — renvoie `HTTP 400` (corps vide) si la validation échoue.
- `overwrite` (texte, optionnel) — seules les valeurs `"true"`/`"1"` déclenchent un écrasement direct du fichier existant. Toute autre valeur (y compris absente, comportement par défaut) déclenche un renommage automatique en cas de collision (`nom (1).ext`, `nom (2).ext`, ...), sauf si le contenu uploadé est bit-à-bit identique à un fichier déjà présent (détection par hash), auquel cas le fichier existant est réutilisé sans réécriture.

**Réponse (succès, `HTTP 200`)** — corps JSON :
```json
{"name": "<nom_fichier_final_sur_le_serveur>", "subfolder": "<subfolder_reçu>", "type": "<type_effectif>"}
```
Les trois clés (`name`/`subfolder`/`type`) sont systématiquement présentes ensemble dans une réponse normale — **la réponse n'est jamais un simple nom de fichier isolé**, elle inclut toujours le sous-dossier et le type effectifs, nécessaires ensemble pour qu'un futur node `LoadImage` puisse retrouver exactement le fichier uploadé (un même nom de fichier peut exister dans plusieurs sous-dossiers/types simultanément).

**Échec** : `HTTP 400` avec corps vide (fichier manquant, ou tentative de path traversal) — aucun message JSON structuré n'est fourni par ComfyUI dans ces deux cas précis.

Aucun endpoint batch (plusieurs fichiers en une requête) n'est exposé par le protocole — confirmé par l'absence de toute route équivalente dans `server.py`.

## Signature livrée

Implémentée exactement conforme à la spécification validée, aucun écart :

```python
def upload_image(self, file_path: str, subfolder: str = "", overwrite: bool = False) -> dict:
```

- `file_path` : chemin local du fichier à uploader (obligatoire, pas de valeur par défaut — contrairement à `subfolder`/`overwrite`, il n'existe aucune valeur neutre sensée).
- `subfolder` : transmis tel quel au serveur, défaut `""` (racine du dossier `type`), symétrique au paramètre `subfolder` déjà existant sur `download_output()`.
- `overwrite` : `bool` Python traduit en `"true"`/absence de champ, plus lisible côté appelant que de manipuler directement la chaîne `"true"`/`"1"` attendue par ComfyUI. Défaut `False` (comportement le plus sûr : jamais d'écrasement silencieux d'un fichier existant portant le même nom sur le serveur).
- `type` **n'est délibérément pas exposé en paramètre** : la primitive existe pour qu'une image devienne référençable par un futur `LoadImage`, qui ne lit que le répertoire `"input"` — c'est la seule valeur ayant un sens pour l'usage déjà motivé aujourd'hui. Valeur `"input"` envoyée en dur dans la requête. Une extension additive (paramètre `type_` avec défaut `"input"`, backward-compatible) reste possible plus tard si un besoin réel de `"temp"`/`"output"` apparaît — même logique que l'ajout de `checkpoint_name` à `generate_image()` en Mission 013.

## Type de retour

`dict`, reflet direct (pas une réinterprétation) de la réponse JSON de ComfyUI : `{"name": ..., "subfolder": ..., "type": ...}`.

**Pourquoi un `dict` plutôt qu'un `str` ou un nouveau type structuré** :
- Perdre `subfolder`/`type` en ne retournant que `name` (un `str`) rendrait l'information insuffisante pour un futur `LoadImage` dans le cas où le même nom de fichier existe dans plusieurs sous-dossiers/types — cas réel dès qu'une deuxième image est uploadée un autre jour avec un nom de fichier local identique.
- Un nouveau type structuré dédié (dataclass/NamedTuple) envelopperait une réponse HTTP déjà auto-descriptive sans бénéfice réel : aucune méthode/comportement ne s'y attacherait, seulement 3 champs `str` — un objet métier de complaisance. `CLAUDE.md` proscrit déjà tout nouveau Domain sans consommateur réel, et il n'en existe aucun aujourd'hui.
- Cohérent avec le précédent déjà établi dans cette même classe : `wait_for_result()` retourne déjà un `dict` brut (le mapping `outputs` de ComfyUI, non retravaillé) plutôt qu'un objet dédié — `upload_image()` suit exactement le même principe : retourner la structure ComfyUI telle quelle, aussi minimalement transformée que possible.
- Un `dict` reste directement injectable, sans traduction, dans les `inputs` d'un futur node `LoadImage` (qui attend précisément `name`/`type` — `LoadImage` ne prend pas `subfolder` séparément côté node, ComfyUI encode généralement `subfolder/name` dans le seul champ `image` du node ; cette translation appartient explicitement à la future couche workflow, hors périmètre ici).
- Compatibilité 1..N : rien dans un `dict` de retour n'empêche d'en accumuler N (ex. `[engine.upload_image(p) for p in paths]` côté futur appelant) — aucune structure ne présuppose une cardinalité de 1.

**Validation réellement appliquée** (implémentée exactement comme spécifié, sur les trois champs, pas seulement `name`) : `name` doit être un `str` non vide ; `subfolder` doit être un `str` (chaîne vide acceptée — c'est la valeur par défaut légitime de ComfyUI pour la racine du dossier `type`) ; `type` doit être un `str` non vide. Si l'un des trois échoue, `ComfyUIEngineError("ComfyUI upload response is structurally invalid: {data}")` est levée — aucune donnée partielle/mal formée n'est jamais retournée à l'appelant. La méthode ne réduit à aucun moment la référence serveur à un simple nom de fichier.

## Multipart — implémentation réelle

Implémentée exactement comme spécifié, aucune nouvelle dépendance ajoutée (`requirements.txt` inchangé). Construction manuelle du corps `multipart/form-data`, stdlib uniquement (`uuid`, `mimetypes`) (`uuid` déjà importé dans le module pour `client_id`, ajout de `mimetypes` pour deviner le `Content-Type` du fichier, défaut `application/octet-stream` si indéterminé) — aucune nouvelle dépendance, cohérent avec le choix déjà fait en Mission 012 de ne pas utiliser `requests`/`httpx`/`aiohttp` pour ce module.

- Frontière (`boundary`) générée via `uuid.uuid4().hex`, comme `client_id` l'est déjà dans `generate_image()`.
- Corps assemblé en `bytes` : partie `image` (`Content-Disposition: form-data; name="image"; filename="<nom_local>"`, `Content-Type` deviné), puis une partie texte par champ optionnel réellement transmis (`subfolder` toujours envoyé, même vide, pour rester explicite ; `type` toujours envoyé (`"input"`) ; `overwrite` envoyé uniquement si `True` — omis sinon, pour laisser ComfyUI appliquer son propre comportement par défaut plutôt que de lui envoyer une valeur explicitement "fausse").
- `urllib.request.Request(f"{self._base_url}/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")`, puis passage direct à `self._request_json(request)` — **méthode déjà existante et inchangée**, qui gère déjà correctement : erreur réseau (`URLError`/`OSError` → `ComfyUIEngineError`), erreur HTTP avec corps vide (`HTTPError` → tentative de décodage JSON d'un corps vide → `ComfyUIEngineError`, comportement déjà correct pour le cas réel `HTTP 400` à corps vide de ComfyUI), et réponse non-JSON (`ComfyUIEngineError`). Aucune modification de `_request_json()` n'est nécessaire.
- Lecture du fichier local : `Path(file_path).read_bytes()`, appelée avant toute construction de requête — un fichier absent (`FileNotFoundError`) ou illisible (`PermissionError`/`OSError`) se propage tel quel, **non enveloppé dans `ComfyUIEngineError`**, exactement comme `download_output()` laisse déjà remonter un `OSError` pour une précondition de système de fichiers local plutôt qu'une erreur de protocole ComfyUI (voir sa propre docstring existante).

## Gestion des erreurs — implémentation réelle

Séparation explicitement maintenue entre deux catégories, exactement comme spécifié :

**Erreurs locales (préconditions de système de fichiers, jamais enveloppées)**
- Fichier local inexistant → `FileNotFoundError` (sous-classe d'`OSError`), propagée telle quelle.
- Fichier local illisible (permissions, autre erreur de lecture) → `OSError`, propagée telle quelle.

Ces deux cas suivent exactement la convention déjà établie par `download_output()` pour `output_directory` : une précondition de système de fichiers local n'est jamais une erreur de protocole ComfyUI.

**Erreurs ComfyUI / transport (converties en `ComfyUIEngineError`)**
- Serveur injoignable (réseau) → via `_request_json()`, inchangée.
- Erreur HTTP (ex. `400` fichier manquant/traversal, corps vide) → via `_request_json()`, inchangée — un corps vide échoue déjà au décodage JSON, ce qui produit déjà `ComfyUIEngineError`.
- Réponse JSON invalide (non-JSON) → via `_request_json()`, inchangée.
- Réponse JSON valide mais structurellement invalide (`name`/`subfolder`/`type` manquant, mal typé ou vide selon le champ) → nouvelle garde explicite dans `upload_image()`, même schéma que la garde `prompt_id` de `submit()`.

Aucune nouvelle classe d'exception créée : `ComfyUIEngineError` existant suffit, cohérent avec la convention déjà établie du module.

## Architecture retenue

```
ComfyUIEngine.upload_image(file_path, subfolder="", overwrite=False)
    → lit file_path localement (échec = OSError natif, non enveloppé)
    → construit un corps multipart/form-data (stdlib uniquement)
    → POST {base_url}/upload/image via self._request_json() (inchangée)
    → valide "name" non vide, retourne {"name", "subfolder", "type"}
```

Aucun nouveau Domain, Manager, Service, EventBus event. `GenerationManager`, `InferencePage`, `build_demo_workflow()` restent strictement inchangés — `upload_image()` n'est appelée nulle part dans le code applicatif à l'issue de cette mission, elle est seulement testable et appelable de façon autonome (par les tests, ou manuellement).

## Tests

Inspecté : `tests/integration/test_comfyui_engine.py` (conventions déjà établies — `_FakeResponse`, `_http_error()`, `@patch("urllib.request.urlopen")`, inspection de `mock_urlopen.call_args` pour vérifier la requête réellement envoyée, `tempfile.mkdtemp()` + `addCleanup(shutil.rmtree, ...)` pour les fichiers locaux réels). Nouvelle classe `ComfyUIEngineUploadImageTest` dans le même fichier, aucune duplication d'infrastructure de test.

Tests envisagés (nombre exact confirmé après implémentation, pas forcé à l'avance) :

1. Upload réussi — réponse mockée `{"name": "...", "subfolder": "...", "type": "input"}`, valeur de retour vérifiée exactement.
2. Requête multipart correcte — le corps envoyé contient bien la partie `name="image"` avec le nom de fichier local et les octets exacts du fichier temporaire réel créé pour le test.
3. `Content-Type` de la requête commence par `multipart/form-data; boundary=` (frontière extraite dynamiquement de l'en-tête envoyé, jamais supposée fixe).
4. `subfolder` transmis correctement dans le corps multipart lorsqu'il est non vide, et correctement restitué dans la valeur de retour.
5. `type` envoyé en dur à `"input"` dans le corps multipart (vérifié par inspection du corps envoyé).
6. `overwrite=True` → champ `overwrite` présent avec la valeur `"true"` dans le corps envoyé ; `overwrite=False` (défaut) → champ `overwrite` absent du corps.
7. Réponse avec `name` absent/vide → `ComfyUIEngineError`.
8. Réponse non-JSON → `ComfyUIEngineError`.
9. Erreur HTTP (corps vide, cas réel ComfyUI) → `ComfyUIEngineError`.
10. Serveur injoignable (`URLError`) → `ComfyUIEngineError`.
11. Fichier local inexistant → `FileNotFoundError` propagée telle quelle, **pas** de `ComfyUIEngineError`.
12. Deux appels indépendants (deux fichiers temporaires distincts, deux réponses mockées distinctes) produisent deux résultats indépendants et corrects, sans état partagé incorrect entre les deux appels — preuve de réutilisabilité N fois, sans introduire de concept de rôle.

Aucun test contre une instance ComfyUI réelle, aucune dépendance réseau, aucun GPU — même discipline que le reste du fichier.

### Résultats réels

**Nouveaux tests ajoutés (18, `ComfyUIEngineUploadImageTest`, dans `tests/integration/test_comfyui_engine.py`)** — delta de +6 par rapport aux 12 initialement envisagés en Phase 2, dû à la séparation explicitement demandée des cas de validation structurelle invalide (manquant / mal typé / vide, pour chacun des trois champs `name`/`subfolder`/`type`) :

- `test_upload_image_returns_structured_response_on_success`
- `test_upload_image_posts_multipart_to_upload_endpoint`
- `test_upload_image_carries_exact_filename_and_bytes`
- `test_upload_image_sends_type_input`
- `test_upload_image_forwards_subfolder_in_request_and_return_value`
- `test_upload_image_overwrite_true_sends_overwrite_field`
- `test_upload_image_overwrite_false_omits_overwrite_field`
- `test_upload_image_raises_when_name_missing`
- `test_upload_image_raises_when_name_is_empty_string`
- `test_upload_image_raises_when_subfolder_missing`
- `test_upload_image_raises_when_subfolder_is_not_a_string`
- `test_upload_image_raises_when_type_missing`
- `test_upload_image_raises_when_type_is_empty_string`
- `test_upload_image_raises_on_invalid_json_response`
- `test_upload_image_raises_on_http_error_with_empty_body`
- `test_upload_image_raises_when_server_unreachable`
- `test_upload_image_raises_file_not_found_error_uncaught_for_missing_local_file`
- `test_upload_image_two_independent_calls_produce_two_independent_results` — démontre l'indépendance de deux uploads successifs (deux fichiers locaux distincts, deux réponses ComfyUI mockées distinctes) sans aucun état partagé sur `self`, propriété centrale de la compatibilité future 1..N images.

**25 tests `ComfyUIEngine` préexistants** (`ComfyUIEngineSubmitTest`, `ComfyUIEngineWaitForResultTest`, `ComfyUIEngineDownloadOutputTest`, `ComfyUIEngineGenerateImageTest`, `ComfyUIEngineArchitecturalConstraintsTest`) — **strictement inchangés**, aucun test supprimé ni modifié.

**Résultat `test_comfyui_engine.py` seul** : `Ran 43 tests in 0.336s — OK` (25 préexistants + 18 nouveaux, verts au premier passage, aucune correction nécessaire).

**Résultat suite complète** : `Ran 264 tests in 77.951s — OK` (246 tests préexistants inchangés + 18 nouveaux, aucune régression constatée sur `GenerationManager`, `InferencePage`, `ImagesPage`, `ImagePreviewDialog`, `MainToolBar`, Application Settings, `WorkspaceManager`, EventBus, Training).

## Critères d'acceptation — état final

- `upload_image()` existe, signature conforme à la spécification : ✅.
- Corps multipart correctement formé, vérifié par inspection réelle de la requête envoyée (pas seulement par confiance dans le code) : ✅.
- Retour = `dict` `{"name", "subfolder", "type"}` reflétant fidèlement la réponse ComfyUI, jamais réduit à un `str` : ✅.
- Validation structurelle des trois champs (pas seulement `name`) : ✅.
- Séparation erreurs locales (non enveloppées) / erreurs ComfyUI-transport (`ComfyUIEngineError`) : ✅.
- Aucune nouvelle dépendance ajoutée (`requirements.txt` inchangé) : ✅.
- `_request_json()`, `submit()`, `wait_for_result()`, `download_output()`, `generate_image()`, `build_demo_workflow()` strictement inchangés : ✅, vérifié par `git diff`.
- `GenerationManager`, `InferencePage` strictement inchangés : ✅, absents du diff.
- Aucun nouveau Domain/Manager/Service/EventBus event : ✅.
- Aucun état d'upload conservé dans `ComfyUIEngine`, plusieurs uploads indépendants supportés : ✅ (voir test dédié ci-dessus).
- Suite de tests complète verte, nombre exact confirmé : ✅ (264/264 : 246 précédents + 18 nouveaux).

## Hors périmètre

Sélection d'image dans `InferencePage` ; modification de `GenerationManager` ; node `LoadImage` dans un workflow ; img2img ; `denoise`/`strength` ; IP-Adapter ; FaceID ; ControlNet ; preprocessors ; conditioning vêtement/décor/pose ; rôles d'image (enum ou autre) ; `ReferenceImageManager` ou tout nouveau Domain/Manager/Service dédié aux images de référence ; nouvel événement EventBus ; abstraction multi-engine (interface commune ComfyUI/Fooocus/Automatic1111/Forge) ; méthode batch `upload_images()` (aucun endpoint natif ne le justifie, voir "Contrat ComfyUI vérifié") ; branchement de `upload_image()` dans `generate_image()` ; modification de `build_demo_workflow()`.

## Perspective future (non implémentée, non engagée)

À documenter uniquement comme contexte, sans créer aucun modèle ni enum dès maintenant : une génération AI Studio Toolkit pourra à terme recevoir 1..N images d'entrée, chacune avec un rôle sémantique (ex. `identity_face`, `identity_sheet`, `clothing`, `environment`, `pose` — noms illustratifs, non engagés) et un mécanisme moteur distinct (img2img, IP-Adapter, ControlNet, FaceID...). L'ordre probable des prochaines étapes, à titre indicatif et non contractuel :

1. **Mission 021 (celle-ci)** — transport : `ComfyUIEngine.upload_image()`.
2. **Mission ultérieure** — premier usage réel : img2img natif ComfyUI avec une seule image (consommation de `upload_image()`, choix du workflow, `denoise`).
3. **Mission ultérieure** — orchestration : plusieurs images et rôles.
4. **Plus tard** — mécanismes spécialisés (IP-Adapter, FaceID, ControlNet, vêtements, décors, poses).
5. **Encore plus tard** — adaptation des concepts aux autres moteurs (Fooocus, Automatic1111, Forge), si et quand un second Engine réel est introduit.

Cette séquence n'est pas un engagement architectural — chaque étape future nécessitera son propre audit indépendant, comme toute mission précédente.

## Fichiers modifiés / créés

- `src/engines/comfyui_engine.py` (modifié, +87 lignes) — `import mimetypes` ajouté, méthode `upload_image()` ajoutée après `download_output()`. Aucune autre méthode touchée.
- `tests/integration/test_comfyui_engine.py` (modifié, +235/-5 lignes) — nouvelle classe `ComfyUIEngineUploadImageTest` (18 tests), docstring de module mise à jour. Les 25 tests préexistants non modifiés.
- `docs/missions/MISSION_021.md` (créé en Phase 2, complété ici avec les résultats réels).

Liste vérifiée directement depuis `git status --short`/`git diff --stat`. Aucun fichier hors ce périmètre (pas de Domain, pas de Manager, pas d'Infrastructure autre que `comfyui_engine.py`, pas d'EventBus, pas d'UI, pas de `requirements.txt`, pas de `CLAUDE.md`/`AGENTS.md`).

## Hors périmètre — confirmé inchangé

`GenerationManager` ; `InferencePage` ; node `LoadImage` dans un workflow ; img2img ; `denoise`/`strength` ; rôles d'image (enum ou autre) ; UI multi-image ; IP-Adapter ; FaceID ; ControlNet ; preprocessors ; Fooocus ; Automatic1111 ; Forge ; abstraction multi-engine ; méthode batch `upload_images()` ; branchement de `upload_image()` dans `generate_image()` ; modification de `build_demo_workflow()`. Tous confirmés strictement inchangés par inspection du diff réel (`git diff --stat` : 2 fichiers applicatifs uniquement).

## Commit correspondant

À compléter après clôture Git réelle (non encore effectuée à ce stade — implémentation et documentation validées, pas encore commitées).

## Tag / release correspondant

À compléter après clôture Git réelle (non encore effectuée à ce stade).

## État final

**Implémentation et documentation de Mission 021 validées.** `ComfyUIEngine.upload_image()` livre une primitive de transport stateless, testée par 264/264 tests automatisés (246 précédents inchangés + 18 nouveaux), sans aucun branchement dans le reste de l'application — `GenerationManager`, `InferencePage`, `generate_image()`, `build_demo_workflow()` strictement inchangés. **Clôture Git de Mission 021 non encore effectuée** (commit/tag/Release en attente de validation explicite de l'architecte).
