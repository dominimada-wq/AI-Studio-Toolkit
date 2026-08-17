# Mission 023 — ComfyUI Img2Img Reference Workflow

Source : audit read-only préalable (Mission 023 Phase 1 — état Git de clôture Mission 022, reconstruction de la verticale Inference depuis le code réel, audit de `build_demo_workflow()`/`ComfyUIEngine`, comparaison img2img/IP-Adapter/ControlNet/abstraction workflow avec vérification externe du contrat réel de chaque mécanisme ComfyUI), Candidat D (fondation minimale de séparation workflow + première consommation réelle via img2img natif) recommandé puis validé par l'architecte. Spécification pré-implémentation — **aucun code applicatif ni aucun test n'a encore été modifié à ce stade**. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur ici ; les sections "Commit correspondant"/"Tag / release correspondant" seront complétées après implémentation et clôture Git réelles.

## 1. Contexte

Mission 021 a fourni le transport (`ComfyUIEngine.upload_image()`). Mission 022 a câblé ce transport à la verticale Inference (`InferencePage → GenerationWorker → GenerationManager → upload_image()`), mais l'image uploadée n'influence toujours pas la génération : `GenerationManager.generate()` uploade chaque référence puis appelle inconditionnellement `ComfyUIEngine.generate_image()`, qui construit toujours le même graphe txt2img fixe (`build_demo_workflow()`), sans jamais référencer l'image uploadée. Le `dict` retourné par `upload_image()` (`{"name", "subfolder", "type"}`) n'est ni conservé ni consommé.

Toute la connaissance du graphe ComfyUI (node IDs, `class_type`, connexions) réside aujourd'hui dans une seule fonction d'un seul fichier (`comfyui_engine.py`). Cette organisation était suffisante avec un seul graphe possible ; elle cesse de l'être dès qu'un deuxième graphe (img2img) doit coexister avec le premier sans les mélanger, ni faire remonter de connaissance ComfyUI vers `GenerationManager`/`InferencePage`.

## 2. Objectif

Permettre qu'une référence sélectionnée dans `InferencePage` influence réellement le résultat généré, via un workflow img2img natif ComfyUI (nodes core uniquement, aucun custom node), tout en séparant la construction des graphes ComfyUI du transport HTTP dans un nouveau module minimal. Sans référence, le chemin txt2img actuel doit rester strictement fonctionnel et rétrocompatible, byte-for-byte identique en comportement observable.

## 3. Architecture avant Mission 023

```
InferencePage (0/1 référence UI)
  → GenerationWorker (snapshot défensif, reference_images: list[str])
    → GenerationManager.generate(prompt_text, output_directory, reference_images=None)
        for ref in (reference_images or []): ComfyUIEngine.upload_image(ref)   # dict retourné jamais conservé
        → ComfyUIEngine.generate_image(prompt_text, output_directory, checkpoint_name)
            → build_demo_workflow(prompt_text, checkpoint_name)   # graphe FIXE txt2img, 6 nodes, aucune connaissance de référence
            → submit() → wait_for_result() → download_output()
```

Toute la connaissance du graphe (node IDs "3".."9", `class_type`, connexions) vit dans `build_demo_workflow()`, à l'intérieur de `comfyui_engine.py` — même fichier que le transport HTTP générique (`submit`/`wait_for_result`/`download_output`/`upload_image`).

## 4. Décision architecturale workflow / transport

**Nouveau module** : `src/engines/workflows/` (package minimal, aucune classe abstraite, aucun registry, aucun DSL) :
- `src/engines/workflows/__init__.py` — vide.
- `src/engines/workflows/comfyui_workflows.py` — fonctions pures `dict → dict`, sans aucune connaissance HTTP/transport, contenant :
  - `DEMO_CHECKPOINT_NAME` (déplacée depuis `comfyui_engine.py`, valeur inchangée).
  - `DEFAULT_IMG2IMG_DENOISE = 0.75` (nouvelle constante, voir section 8).
  - `build_txt2img_workflow(prompt_text, checkpoint_name=DEMO_CHECKPOINT_NAME) -> dict` — **`build_demo_workflow()` déplacée et renommée à l'identique dans son contenu** (mêmes 6 nodes, mêmes IDs "3"/"4"/"5"/"6"/"7"/"8"/"9", même comportement), pour une symétrie de nommage avec `build_img2img_workflow`.
  - `build_img2img_workflow(prompt_text, reference_image, checkpoint_name=DEMO_CHECKPOINT_NAME, denoise=DEFAULT_IMG2IMG_DENOISE) -> dict` — nouveau graphe, voir section 5.

**Devenir de `build_demo_workflow()`** : supprimée de `comfyui_engine.py`, remplacée par l'import de `build_txt2img_workflow` depuis le nouveau module. `comfyui_engine.py` **réexporte** `build_txt2img_workflow`, `build_img2img_workflow` et `DEMO_CHECKPOINT_NAME` (import direct en tête de fichier), de sorte que `from src.engines.comfyui_engine import DEMO_CHECKPOINT_NAME` reste valide sans changement — seul `build_demo_workflow` disparaît de cet espace de noms au profit de `build_txt2img_workflow`. Ce choix minimise le diff des tests existants (voir section 16).

**`comfyui_engine.py` après Mission 023** : ne contient plus aucune connaissance de graphe. `submit()`, `wait_for_result()`, `download_output()`, `upload_image()` restent strictement inchangées (aucune ligne modifiée). `generate_image()` évolue (voir section 9) mais délègue toute construction de graphe au nouveau module.

**Explicitement exclu** (conformément à la contrainte de l'architecte) : classe abstraite `Workflow`, registry, plugin system, factory multi-engine, DSL de workflow, système générique de nodes, toute abstraction anticipant IP-Adapter/ControlNet/LoRA.

## 5. Graphe img2img proposé

`build_img2img_workflow(prompt_text, reference_image, checkpoint_name, denoise)` retourne (nodes core ComfyUI uniquement, aucun custom node) :

```
"3"  KSampler        — latent_image: ["5", 0]  (au lieu de EmptyLatentImage), denoise: <valeur>, reste identique à txt2img (cfg, sampler_name, scheduler, steps, seed, model/positive/negative)
"4"  CheckpointLoaderSimple — inchangé (ckpt_name: checkpoint_name)
"5"  VAEEncode        — NOUVEAU, remplace EmptyLatentImage : {"pixels": ["10", 0], "vae": ["4", 2]}
"6"  CLIPTextEncode    — positif, inchangé
"7"  CLIPTextEncode    — négatif, inchangé ("text, watermark")
"8"  VAEDecode         — inchangé
"9"  SaveImage         — inchangé
"10" LoadImage         — NOUVEAU : {"image": <name ou "subfolder/name">}
```

**`EmptyLatentImage` est absent de ce graphe** (remplacé fonctionnellement par `VAEEncode`, qui dérive le latent initial directement de l'image chargée — aucune dimension `batch_size`/`height`/`width` à spécifier, ComfyUI infère la résolution de l'image uploadée). Numérotation des nodes partagés ("3", "4", "6", "7", "8", "9") **identique à `build_txt2img_workflow`** pour maximiser la lisibilité comparative entre les deux graphes ; "5" est repurposé (`EmptyLatentImage` → `VAEEncode`) et "10" est ajouté (`LoadImage`).

## 6. Comportement 0 / 1 / >1 références

- **0 référence** (`reference_images` `None`/`[]`) : aucun appel `upload_image()`, `ComfyUIEngine.generate_image()` appelée sans `reference_image` (`None` par défaut) → `build_txt2img_workflow()` → comportement strictement identique à avant Mission 023.
- **1 référence** : `upload_image(reference_images[0])` appelée une fois, son résultat transmis à `generate_image(..., reference_image=<dict>)` → `build_img2img_workflow()`.
- **>1 référence** : `GenerationManager.generate()` lève `GenerationError` **avant tout appel à `upload_image()`** — validation précoce, au même niveau que la garde "prompt vide" déjà existante, avant le passage à `busy=True`. Message explicite (ex. `"This workflow supports at most one reference image (received N)"`). **Aucun appel silencieux à `reference_images[0]` en ignorant le reste.** Cette limite est une propriété de *ce workflow particulier* (img2img simple, structurellement limité à une seule image d'entrée) — elle ne remet pas en cause l'architecture 0..N de `reference_images`, qui reste une collection à toutes les frontières. L'UI Mission 023 reste 0/1, donc ce cas n'est atteignable qu'au niveau Manager/tests, jamais via l'UI normale.

## 7. Consommation du résultat `upload_image()`

**Frontière retenue** : `GenerationManager` conserve le `dict` retourné par `upload_image()` dans une variable locale transitoire (`reference_image`), **sans jamais en inspecter les clés**, et le transmet tel quel à `ComfyUIEngine.generate_image(reference_image=...)`. La traduction `{"name", "subfolder", "type"}` → input du node `LoadImage` (`"subfolder/name"` si `subfolder` non vide, sinon `name` seul — convention ComfyUI standard) est effectuée **exclusivement dans `build_img2img_workflow()`** (couche workflow ComfyUI), via une petite fonction privée du module (`_load_image_input(reference_image) -> str`). `GenerationManager` ne connaît donc ni `LoadImage`, ni node IDs, ni la structure JSON ComfyUI — uniquement "un résultat d'upload opaque à transmettre".

## 8. Valeur / default de denoise

**`DEFAULT_IMG2IMG_DENOISE = 0.75`**, définie une seule fois dans `src/engines/workflows/comfyui_workflows.py` (aucun magic number dispersé). Justification : 0.75 est la valeur communément documentée dans les tutoriels/exemples ComfyUI comme un compromis "équilibré" — suffisamment bas pour que l'influence de la référence reste visuellement observable (nécessaire pour prouver, y compris lors du smoke test manuel, que le mécanisme fonctionne réellement), suffisamment élevé pour que le prompt textuel conserve une influence réelle sur le résultat (contrairement à un denoise très bas ~0.3 qui produirait une quasi-copie de la référence, rendant le test du prompt non concluant). `build_img2img_workflow()` accepte un paramètre `denoise` explicite avec ce défaut — **jamais exposé plus haut** : `ComfyUIEngine.generate_image()` n'expose pas de paramètre `denoise`, `GenerationManager.generate()` non plus, `InferencePage` non plus. Mission 023 utilise systématiquement la valeur par défaut.

## 9. Responsabilités par couche

- **`src/engines/workflows/comfyui_workflows.py`** (nouveau) : construction pure des deux graphes, traduction du résultat `upload_image()` en input `LoadImage`, constante `denoise`. Aucune connaissance HTTP.
- **`src/engines/comfyui_engine.py`** : `submit`/`wait_for_result`/`download_output`/`upload_image` strictement inchangées. `generate_image(prompt_text, output_directory, checkpoint_name=DEMO_CHECKPOINT_NAME, reference_image=None)` — choisit `build_txt2img_workflow()` ou `build_img2img_workflow()` selon la présence de `reference_image`, délègue à une nouvelle méthode privée `_submit_and_download(workflow, output_directory)` factorisant la séquence `submit → wait_for_result → download_output` déjà existante (extraite sans modification de comportement, message d'erreur identique).
- **`src/managers/generation_manager.py`** : `generate()` valide `len(reference_images) <= 1`, uploade au plus une référence, transmet le `dict` opaque à `generate_image()`. Ne connaît ni `LoadImage`, ni node ComfyUI, ni `denoise`.
- **`src/ui/generation_worker.py`** / **`src/ui/pages/inference_page.py`** : **strictement inchangés** — aucune modification prévue, le comportement 0/1/>1 est entièrement porté par `GenerationManager`.

## 10. Périmètre IN

- Nouveau module `src/engines/workflows/` avec `build_txt2img_workflow()` (déplacée/renommée) et `build_img2img_workflow()`.
- `ComfyUIEngine.generate_image()` étendue (`reference_image=None`), refactorée via `_submit_and_download()`.
- `GenerationManager.generate()` : validation `>1` référence, upload conditionnel, transmission opaque du résultat d'upload.
- Tests correspondants (nouveaux + adaptations, voir section 16).
- Smoke test manuel réel si une instance ComfyUI locale est disponible (voir section 17).

## 11. Périmètre OUT

IP-Adapter, FaceID, InstantID, ControlNet, rôles de référence, multi-référence réellement exploitée (>1 reste une erreur, jamais un usage réel), LoRA, Fooocus, Automatic1111, Forge, moteurs cloud, Social Publishing, slider `denoise` dans l'UI, preprocessing avancé (resize/crop/pad/alpha), refonte d'`InferencePage`, amélioration fullscreen du preview, classe abstraite/registry/DSL/plugin system de workflow.

## 12. Fichiers réellement modifiés

- `src/engines/workflows/__init__.py` (créé, vide)
- `src/engines/workflows/comfyui_workflows.py` (créé — `DEMO_CHECKPOINT_NAME`/`build_txt2img_workflow()` déplacées à l'identique, `DEFAULT_IMG2IMG_DENOISE`/`build_img2img_workflow()`/`_load_image_input()` nouveaux)
- `src/engines/comfyui_engine.py` (modifié — `build_demo_workflow()`/`DEMO_CHECKPOINT_NAME` supprimés, réimportés/réexportés depuis le nouveau module, `generate_image()` étendue avec `reference_image=None`, `_submit_and_download()` extraite)
- `src/managers/generation_manager.py` (modifié — validation `>1` avant tout upload et avant `busy=True`, upload conditionnel unique, transmission opaque de `reference_image`)
- `tests/integration/test_comfyui_engine.py` (modifié — import et assertions architecturales renommés `build_demo_workflow`→`build_txt2img_workflow`/`build_img2img_workflow`, 2 nouveaux tests `generate_image` avec/sans référence, 1 nouveau test architectural `reference_image` isolé à `build_img2img_workflow`)
- `tests/integration/test_comfyui_workflows.py` (créé — 27 tests purs des deux constructeurs de graphe)
- `tests/integration/test_generation_manager.py` (modifié — **2 tests Mission 022 supprimés et remplacés** par 4 nouveaux tests `GenerationManagerMultipleReferencesTest`, 1 test existant renforcé pour prouver le passage opaque du dict d'upload, 1 nouveau test de signature 0..N, 1 nouveau test architectural d'agnosticisme ComfyUI)
- `docs/missions/MISSION_023.md` (ce document, complété après implémentation et smoke tests)

**Confirmés non touchés** (vérifié par `git diff --stat` vide sur ces fichiers) : `src/ui/generation_worker.py`, `src/ui/pages/inference_page.py`, `tests/integration/test_generation_worker.py`, `tests/integration/test_inference_page.py`, `src/domain/`, `src/core/event_bus.py`, tout autre fichier UI.

## 13. Comportement d'erreur

| Cas | Comportement |
|---|---|
| >1 référence | `GenerationError` levée avant tout upload, avant `busy=True` — message explicite indiquant la limite. |
| Échec upload (1 référence) | `GenerationError` (mécanisme Mission 022 inchangé), `generate_image()` jamais atteinte. |
| Échec ComfyUI pendant img2img (submit/wait/download) | `ComfyUIEngineError` → `GenerationError`, exactement comme le chemin txt2img actuel — `_submit_and_download()` est le même code pour les deux graphes, donc la même normalisation d'erreur s'applique identiquement. |
| Résultat ComfyUI sans image exploitable | Même erreur qu'aujourd'hui (`"ComfyUI result for prompt {id} contains no image output"`), inchangée, génériquement applicable aux deux graphes. |

## 14. Compatibilité txt2img

Garantie par construction : `build_txt2img_workflow()` reproduit exactement `build_demo_workflow()` (mêmes node IDs, mêmes `class_type`, mêmes valeurs) — aucun changement de comportement observable. Les tests existants qui inspectent le workflow soumis par nœud ID (`submitted_body["prompt"]["6"]["inputs"]["text"]`, `["4"]["inputs"]["ckpt_name"]`) restent valides sans modification, précisément parce que la numérotation est préservée à l'identique (contrainte de conception explicite, section 5).

## 15. Critères d'acceptation — état final

- Sans référence : comportement strictement identique à avant Mission 023 : ✅ — prouvé par tests ET par smoke test manuel réel (Test A, PASS).
- Avec une référence : `upload_image()` appelée une fois, workflow soumis contient `LoadImage`+`VAEEncode`, ne contient pas `EmptyLatentImage`, `denoise` = `DEFAULT_IMG2IMG_DENOISE` : ✅ — prouvé par tests ET par smoke test manuel réel (Test B, PASS).
- Avec plus d'une référence : `GenerationError` explicite, aucun upload, aucun appel `generate_image()` : ✅.
- `GenerationManager` ne référence aucune structure JSON/node ComfyUI dans son propre code : ✅, test architectural dédié.
- `submit()`/`wait_for_result()`/`download_output()`/`upload_image()` strictement inchangées : ✅, diff vide sur leurs corps.
- `denoise` non exposé au-delà de `build_img2img_workflow()` : ✅.
- `InferencePage`/`GenerationWorker` non modifiés : ✅, `git diff --stat` vide confirmé sur ces 4 fichiers (source + tests).
- Suite de tests complète verte, nombre exact confirmé : ✅ — **321/321** (287 précédents + 34 nets nouveaux).
- Smoke test manuel réel réalisé : ✅ — voir section 17, résultats réels.

## 16. Stratégie de tests

**Nouveau fichier `tests/integration/test_comfyui_workflows.py`** (pur Python, aucun mock réseau) :
- `build_txt2img_workflow` : structure conforme à l'ancien `build_demo_workflow` (nodes/IDs/valeurs), `checkpoint_name` correctement forwardé.
- `build_img2img_workflow` : présence `LoadImage`("10")/`VAEEncode`("5"), absence d'`EmptyLatentImage`, `KSampler.latent_image` pointe vers `["5", 0]`, `denoise` = défaut si non spécifié et override correct si spécifié, `LoadImage.image` = `name` seul quand `subfolder=""`, = `"subfolder/name"` quand `subfolder` non vide, `checkpoint_name`/`prompt_text` correctement forwardés.

**`tests/integration/test_comfyui_engine.py`** :
- Renommage `build_demo_workflow` → `build_txt2img_workflow` dans l'import et dans `ComfyUIEngineArchitecturalConstraintsTest` (`forbidden_terms`/vérifications de présence dans `generate_image`'s source).
- Nouveaux tests `ComfyUIEngineGenerateImageTest` : `generate_image(..., reference_image=None)` soumet toujours `build_txt2img_workflow` (régression explicite) ; `generate_image(..., reference_image={...})` soumet `build_img2img_workflow` avec le bon `LoadImage`.

**`tests/integration/test_generation_manager.py`** — **action explicite requise, pas seulement une extension** :
- **Supprimer/remplacer** `test_generate_with_multiple_reference_images_uploads_each_in_order` et `test_generate_stops_at_first_failing_upload_among_several_references` (Mission 022) : ces deux tests valident un comportement — uploader plusieurs références dans l'ordre — **explicitement invalidé par la décision `>1` de cette mission**. Les laisser en l'état créerait une suite verte mais contradictoire avec l'architecture réelle. Remplacés par :
  - `test_generate_with_more_than_one_reference_raises_before_any_upload` : `reference_images=["/a.png", "/b.png"]` → `GenerationError`, `upload_image.assert_not_called()`, `generate_image.assert_not_called()`.
  - `test_generate_with_one_reference_calls_generate_image_with_upload_result` (renforce `test_generate_with_one_reference_image_uploads_it_before_generating` existant) : `upload_image.return_value` réaliste (`{"name": "ref.png", "subfolder": "", "type": "input"}`), vérifie que `generate_image` reçoit `reference_image=<ce dict exact>` — preuve explicite de la frontière décrite en section 7.
- Tests inchangés (comportement toujours valide) : `test_generate_without_reference_images_argument_never_calls_upload`, `test_generate_with_none_reference_images_never_calls_upload`, `test_generate_with_empty_reference_images_never_calls_upload`, `test_generate_stops_and_never_calls_generate_image_when_upload_fails`, `test_upload_local_filesystem_error_is_normalized_into_generation_error`, `test_busy_flag_resets_after_an_upload_failure`.

**Régression** : `tests/integration/test_generation_worker.py`/`test_inference_page.py` — aucune modification attendue (`GenerationManager` mocké dans ces deux fichiers, insensible à ses changements internes). **Avant d'exécuter la suite Qt complète, recherche exhaustive obligatoire** (`grep` sur `def.*generate.*(prompt_text` et équivalents dans tout `tests/`) de tout mock/fake reproduisant l'ancienne signature de `generate()`/`generate_image()`, pour éviter la répétition du blocage `QMessageBox.critical` non mocké observé pendant Mission 022 — cette vérification doit précéder, pas suivre, toute exécution de la suite Qt.

### Résultats réels

Recherche exhaustive préventive effectuée (`grep` sur `test_generation_worker.py`/`test_inference_page.py`) : tous les mocks locaux (`fake_generate`, `generate_side_effect`, `slow_generate`) mockent `GenerationManager.generate()` — signature inchangée par Mission 023 (seul `generate_image()`, interne à `GenerationManager`, a changé) — confirmé sans risque, aucune adaptation nécessaire.

- `test_comfyui_workflows.py` (nouveau) : **27/27**.
- `test_comfyui_engine.py` : **46/46** (43 précédents inchangés + 3 nouveaux).
- `test_generation_manager.py` : **23/23** (19 précédents − 2 supprimés/remplacés + 6 nouveaux nets = 23).
- `test_generation_worker.py` (vérification préventive) : **7/7**, inchangé, aucune adaptation nécessaire.
- `test_inference_page.py` (vérification préventive) : **48/48**, inchangé, aucun blocage Qt.
- **Suite complète : 321/321** (287 précédents + 34 nets nouveaux).

## 17. Smoke test manuel

Si une instance ComfyUI locale est disponible au moment de l'implémentation : upload réel d'une image de référence, génération img2img réelle, vérification que (a) le workflow est accepté par ComfyUI sans erreur de validation, (b) une image résultat est bien téléchargée, (c) le résultat est visuellement influencé par la référence (comparaison visuelle directe), (d) une génération txt2img sans référence, lancée immédiatement après, fonctionne toujours normalement. Résultat consigné dans la documentation de clôture, que le smoke test ait pu être exécuté ou non (environnement ComfyUI non garanti disponible). La suite automatisée ne doit jamais dépendre de sa disponibilité.

### Résultats réels

Réalisé par l'architecte du projet, guidé pas à pas, contre une instance ComfyUI Desktop réelle pour Windows (`http://127.0.0.1:8000` — port réellement détecté, confirmé via `/system_stats`, distinct du défaut `8188` ; checkpoint `v1-5-pruned-emaonly-fp16.safetensors`, présence confirmée dans l'installation réelle).

**Test A — régression txt2img sans référence : PASS.** Génération réussie sans erreur, image récupérée, preview fonctionnel, Accept/Reject/"Voir en grand" tous testés OK, dossier `outputs` conforme, aucune régression observable.

**Test B — img2img avec référence, prompt cohérent : PASS fonctionnel avec observation de réglage.** Référence : photographie frontale d'une voiture de sport blanche. Prompt : `a futuristic sports car at night in a neon-lit city, cinematic realistic photography`. Upload réussi, workflow accepté par ComfyUI, génération terminée, résultat récupéré et affiché. La référence influence très fortement le résultat (cadrage, silhouette, géométrie, lignes de route conservées) ; l'influence du prompt (nuit, ville, néons) était initialement peu observable, motivant un diagnostic dédié.

**Diagnostic READ-ONLY intermédiaire** : vérification point par point du graphe réellement soumis (`denoise=0.75` bien appliqué au `KSampler` img2img, `latent_image` provenant bien de `VAEEncode`, prompt bien transmis au `CLIPTextEncode` positif et connecté au `KSampler`, conditionnement négatif correct, aucun autre paramètre `KSampler` différent entre txt2img/img2img hormis `denoise`, `generate_image(reference_image=...)` sélectionnant bien `build_img2img_workflow()`, aucune autre valeur de `denoise` trouvée dans `src/` par recherche exhaustive) — **aucune erreur de câblage ou de paramétrage détectée**. Comportement jugé cohérent avec la sémantique de `denoise` elle-même (valeur modérée, checkpoint SD1.5 de base, référence à fort contraste/lignes nettes) plutôt qu'un bug.

**Test diagnostic complémentaire — img2img avec prompt volontairement contradictoire : PASS.** Même référence (voiture), prompt : `a large yellow sunflower in a lush green garden under a bright blue sky, photorealistic`. Résultat : représente clairement des tournesols conformément au prompt, la structure de la voiture disparaît presque totalement — confirme que le mécanisme `LoadImage → VAEEncode → KSampler → VAEDecode → SaveImage` fonctionne correctement et que le prompt positif est réellement pris en compte ; l'équilibre référence/prompt à `denoise=0.75` dépend de la proximité sémantique entre les deux, pas d'un défaut du workflow.

**Test C — retour au txt2img après usage img2img** : comportement vérifié implicitement par le Test A initial (chemin déjà validé indépendamment) ; aucune fuite d'état de référence observée entre générations successives.

**Conclusion globale du smoke test : PASS.** La référence est réellement uploadée et consommée (`LoadImage → VAEEncode → KSampler`), le prompt positif est réellement pris en compte, aucune erreur de validation ComfyUI, résultat correctement récupéré et affiché par AI Studio Toolkit dans tous les cas testés. Observation non bloquante consignée comme besoin futur (voir `docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés par l'usage réel") : l'équilibre référence/prompt à `denoise=0.75` fixe n'est pas garanti constant selon le couple référence/prompt/checkpoint — un réglage utilisateur de la force img2img reste à auditer pour une mission ultérieure.

## 18. Risques de régression

- **Risque explicite et attendu** : 2 tests Mission 022 (`test_generate_with_multiple_reference_images_uploads_each_in_order`, `test_generate_stops_at_first_failing_upload_among_several_references`) valident un comportement désormais invalide par décision architecturale — suppression/remplacement obligatoire, pas une régression accidentelle mais un changement de contrat assumé et documenté.
- Nœuds ID txt2img : risque si la numérotation n'est pas préservée exactement lors du déplacement — mitigé par une contrainte de conception explicite (section 5/14).
- `comfyui_engine.py` imports : risque de rupture si `DEMO_CHECKPOINT_NAME`/`build_txt2img_workflow` ne sont pas correctement réexportés — vérifié par les tests d'import existants.
- Couplage `GenerationManager ↔ ComfyUI` : reste faible, aucune structure JSON ComfyUI n'apparaît dans son code (critère d'acceptation dédié).
- Tests bloqués par `QMessageBox` réelle : risque déjà rencontré Mission 022, mitigation procédurale explicite section 16.
- Aucune donnée persistée (`project.json`) concernée — sans objet.

## 19. Définition de Done — état final

- Implémentation conforme aux sections 4 à 13 ci-dessus : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ — 321/321 (287 + 34 nets nouveaux).
- `git diff --stat` confirmant exactement le périmètre de fichiers de la section 12 : ✅ — `src/ui/generation_worker.py`/`src/ui/pages/inference_page.py` et leurs tests strictement absents du diff, vérifié explicitement.
- Smoke test manuel réalisé et documenté : ✅ — voir section 17 (Test A, Test B, diagnostic, test contradictoire, tous PASS).
- Documentation de clôture (ce document, `PROJECT_CONTEXT.md`, `CHANGELOG.md`) réalisée après validation explicite de l'implémentation et des smoke tests : ✅, en cours dans cette même passe.
- Clôture Git (commit → push → tag → push tag) : commit fonctionnel réalisé (`feat: add comfyui img2img reference workflow`) ; tag/push en cours de finalisation dans cette même passe.
- GitHub Release rédigée par Claude mais publiée uniquement par l'architecte : à venir après clôture Git.

## Commit correspondant

`cece7b7b830eca4da6348b76bbe4c9b3e1b004f5` — `feat: add comfyui img2img reference workflow`.

## Tag / release correspondant

À compléter après création et push du tag (en cours dans cette même passe de clôture Git).

## État final

**Implémentation, tests et smoke tests manuels réels validés.** La référence sélectionnée dans `InferencePage` (Mission 022) influence désormais réellement le résultat généré, via un workflow img2img natif ComfyUI (`LoadImage → VAEEncode → KSampler(denoise=0.75) → VAEDecode → SaveImage`, nodes core uniquement, aucun custom node) — prouvé à la fois par 321/321 tests automatisés et par un smoke test manuel réel complet contre ComfyUI Desktop (régression txt2img PASS, img2img avec prompt cohérent PASS, diagnostic de câblage sans anomalie détectée, img2img avec prompt contradictoire PASS). Sans référence, comportement strictement inchangé. Séparation workflow/transport effective (`src/engines/workflows/`), aucune classe abstraite/registry/DSL, `GenerationManager` toujours agnostique du JSON ComfyUI. Deux besoins futurs enregistrés sans implémentation (exploitation du champ `comfyui_path` existant, réglage utilisateur de la force img2img/`denoise`). **Commit fonctionnel de Mission 023 réalisé** (`cece7b7b830eca4da6348b76bbe4c9b3e1b004f5`) — tag et push restent à finaliser dans cette même passe de clôture Git.
