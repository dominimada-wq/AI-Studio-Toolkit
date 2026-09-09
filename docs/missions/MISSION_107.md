# Mission 107 — Forge Engine Foundation

> **MISSION CLÔTURÉE — FONDATION FORGE LIVRÉE, INVISIBLE DANS L'UI, AUCUN COUPLAGE PAR TYPE DE MOTEUR DANS `GenerationManager`.** Ce document a d'abord servi de contrat avant implémentation (sections 1-11, inchangées). Voir section 12 pour le résultat réel complet, y compris la correction architecturale demandée après une première ébauche.

## 1. Contexte

L'audit post-Mission 106 a établi que le workflow principal (`Images → Dataset/captions → OneTrainer → LoRA → Central Library → Inference/ComfyUI → Images`) est réellement fonctionnel et sans blocage structurel. Trois mini-audits read-only successifs ont ensuite préparé cette mission :

1. **Progression OneTrainer vs Fooocus/Forge** : la progression structurée d'OneTrainer reste différée (aucune piste ROBUSTE-et-immédiatement-actionnable — `tqdm`/`on_update_status` sont FRAGILE, `callback.pipe` est institutionnellement bloqué depuis Mission 100, TensorBoard est une piste ACCEPTABLE mais jamais vérifiée empiriquement). **Forge** (Stable Diffusion WebUI Forge, installé réellement sur cette machine, `J:\Programmes\WebUI Forge CU121`) a été retenu comme deuxième moteur d'Inference, sur la base d'une API HTTP native complète (`/sdapi/v1/txt2img`, `/img2img`, `/sd-models`, `/samplers`, `/schedulers`, `/loras`, schéma OpenAPI auto-généré) — **Fooocus est différé** tant qu'aucune API fiable n'est disponible (aucune route applicative propre, seul l'endpoint générique non contractuel de Gradio existerait).
2. **Audit architectural Settings/sélection/cycle de vie/références/LoRA** a établi, par lecture du code réel :
   - `comfyui_url`/`comfyui_checkpoint_name`/`comfyui_lora_expose_path` sont aujourd'hui des configurations globales lues une seule fois au démarrage (`MainWindow.__init__`, `main_window.py:170-180`) — aucun hot-reload.
   - Aucun sélecteur de checkpoint n'existe aujourd'hui dans `InferencePage` (contrairement à sampler/scheduler, Mission 096) — le choix vit exclusivement dans `SettingsPage`. L'harmonisation `Engine → Checkpoint` directement dans Inference est une question ouverte, à traiter lors de la préparation de M108, **jamais dans M107**.
   - `ComfyUIEngine`/le futur `ForgeEngine` sont de purs wrappers HTTP sans état (`ComfyUIEngine.__init__` ne stocke que `base_url`/`timeout`, aucune connexion persistante) — les deux peuvent être construits une seule fois sans risque d'état périmé, ce qui rend un sélecteur de moteur vivant entièrement dans `InferencePage` (jamais en Settings) réalisable sans reconstruire `MainWindow`.
   - `reference_strength` (Toolkit/ComfyUI `denoise`) et `denoising_strength` (Forge) ont été vérifiés **réellement équivalents**, pas seulement homonymes : les deux calculent `t_enc = int(denoising_strength * steps)` (confirmé dans `sd_samplers_common.py` de l'installation Forge réelle), le même algorithme historique d'img2img Stable Diffusion, avec le même défaut `0.75` des deux côtés.
   - `LoRALibraryManager.expose_to_comfyui()` (hardlink NTFS, zéro duplication physique, alias indexé par `lora_id`) est déjà mécaniquement générique — seul son nom et l'appel direct depuis `InferencePage` sont couplés à ComfyUI. Sa généralisation appartient à M108, jamais à M107.

Cette mission est la première des deux missions décidées : une **fondation technique invisible** (M107), suivie d'une **intégration UX réelle** (M108, non encore rédigée).

## 2. Objectif

Introduire `ForgeEngine`, un client HTTP Qt-free pour l'API native Forge/A1111, et lever dans `GenerationManager` le seul couplage structurel qui l'empêcherait conceptuellement d'utiliser un second moteur — **sans rendre Forge visible ou sélectionnable nulle part dans l'UI**. À la fin de M107, l'application doit se comporter exactement comme avant pour l'utilisateur : aucun nouveau champ Settings, aucun nouveau contrôle, aucun changement de comportement observable.

## 3. Décisions retenues (issues des mini-audits, non rediscutées ici)

### 3.1 `ForgeEngine` — un client au même rang que `ComfyUIEngine`, pas une variante

Même famille architecturale que `ComfyUIEngine` (`src/engines/comfyui_engine.py`) : Infrastructure layer, Qt-free, ignore le Domain, retourne des `str`/`dict` bruts, jamais un objet Domain. Contrairement à ComfyUI, l'API Forge attend un JSON plat (modèle Pydantic généré depuis `StableDiffusionProcessingTxt2Img`/`Img2Img`, confirmé par lecture de `modules/api/models.py` de l'installation réelle) — **pas un graphe de nœuds**. En conséquence, `ForgeEngine` n'a probablement pas besoin d'un module `forge_workflows.py` séparé comme ComfyUI (`src/engines/workflows/comfyui_workflows.py`) : la construction du payload peut rester interne à `forge_engine.py`, sous réserve de confirmation au moment de l'implémentation — si la complexité réelle justifie une séparation, elle devra être proposée avant d'être ajoutée (voir section 4, liste fermée de fichiers).

### 3.2 LoRA — syntaxe encapsulée, aucun câblage Central Library

Forge n'a pas de champ dédié pour un LoRA dans son API `txt2img`/`img2img` — l'application se fait par la syntaxe `<lora:nom:force>` concaténée dans le `prompt` (convention stable de tout l'écosystème A1111/Forge, confirmée par absence de tout champ `lora`/`loras` dans les modèles Pydantic générés). `ForgeEngine.generate_image()` (ou équivalent) accepte `lora_name`/`lora_strength` en paramètres et encapsule entièrement cette syntaxe — **aucun appelant de `ForgeEngine` ne doit jamais construire cette syntaxe lui-même**. Ceci reste un détail d'implémentation interne à l'engine : M107 ne câble aucun appelant réel vers cette capacité (pas de Central Library, pas de Settings, pas d'UI).

### 3.3 Références — mapping vérifié, pas supposé

`reference_image` + `reference_strength` (contrat déjà utilisé par `GenerationManager.generate()` pour ComfyUI) se mappe vers Forge en : `img2img` (au lieu de `txt2img`) + `init_images` (liste base64, un seul élément pour ce Domain) + `denoising_strength` (valeur transmise telle quelle, sémantique vérifiée équivalente à `reference_strength`/`denoise`, section 1 ci-dessus). `ForgeEngine` décide lui-même txt2img vs img2img selon la présence d'une référence, comme `ComfyUIEngine.generate_image()` le fait déjà.

### 3.4 `GenerationManager` — override par-appel, pas de registry

Le couplage structurel actuel : `GenerationManager.__init__(comfyui_engine: ComfyUIEngine, checkpoint_name, lora_name, lora_strength)` nomme et type le moteur explicitement, et `generate()` n'a aucun paramètre `engine`/`checkpoint_name` — seuls `lora_name`/`lora_strength` sont déjà des overrides par-appel (Mission 102, avec fallback sur la valeur du constructeur si `None`). La plus petite évolution cohérente avec ce pattern déjà établi : étendre `generate()` avec un `engine`/`checkpoint_name` optionnels, même contrat de fallback (`None` → valeur du constructeur, donc comportement ComfyUI historique strictement inchangé pour tout appelant qui ne les fournit pas). Aucun registry, aucune factory, aucune hiérarchie abstraite : le nombre de moteurs possibles reste fermé à deux, jamais une liste dynamique.

## 4. Périmètre exact — fichiers concernés

- `src/engines/forge_engine.py` (nouveau) — `ForgeEngine`, `ForgeEngineError`.
- `src/managers/generation_manager.py` (modifié) — généralisation minimale décrite en 3.4 uniquement.
- `tests/integration/test_forge_engine.py` (nouveau, même convention que `test_comfyui_engine.py`).
- `tests/integration/test_generation_manager.py` (modifié) — tests des nouveaux paramètres par-appel + non-régression du chemin ComfyUI historique.
- `docs/missions/MISSION_107.md` (ce document).

**Si l'implémentation démontre qu'un autre fichier fonctionnel est nécessaire (par exemple un `forge_workflows.py` séparé si la construction du payload s'avère trop volumineuse pour rester inline), arrêt et rapport avant tout élargissement — jamais une extension silencieuse de cette liste.**

**Aucune modification** de `src/domain/`, `ApplicationSettings`, `src/ui/pages/settings_page.py`, `src/ui/pages/inference_page.py`, `src/managers/lora_library_manager.py`, ni de tout fichier `src/ui/`.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Tout nouveau champ `ApplicationSettings` (`forge_url`, `forge_lora_expose_path`, `forge_checkpoint_name`, `forge_lora_name`/`strength` — tous appartiennent à M108).
- Toute modification de `SettingsPage` ou `InferencePage`.
- Tout sélecteur ComfyUI/Forge, visible ou caché.
- Auto-lancement de Forge, installation/modification de l'installation Forge existante, activation automatique de `--api` — Forge reste sous l'entière responsabilité manuelle de l'architecte, exactement comme `onetrainer_path` en Mission 101.
- Toute modification de `LoRALibraryManager`/Central LoRA Library, y compris sa généralisation pourtant déjà identifiée comme mécaniquement triviale (section 1) — appartient à M108.
- Toute refonte du placement UX du checkpoint ComfyUI.
- Toute refonte générale de Settings.
- Fooocus, progression OneTrainer, TensorBoard.
- Toute architecture générique multi-engine au-delà du minimum à deux adapters nommés (pas de registry, pas de plugins, pas de factory générique, pas de hiérarchie abstraite complexe).
- Le smoke réel Forge (voir section 8) — reporté à M108.

## 6. Étapes techniques attendues

1. **`src/engines/forge_engine.py`** :
   - `ForgeEngineError(Exception)`.
   - `ForgeEngine(base_url: str, timeout: float = ...)` — même contrat minimal que `ComfyUIEngine.__init__` (aucun état persistant au-delà de `base_url`/`timeout`).
   - Découverte : `list_checkpoints()` (`GET /sdapi/v1/sd-models`), `list_loras()` (`GET /sdapi/v1/loras`), `list_samplers()` (`GET /sdapi/v1/samplers`), `list_schedulers()` (`GET /sdapi/v1/schedulers`) — chacune lève `ForgeEngineError` sur toute réponse HTTP en échec, communication impossible, ou forme de réponse inattendue, jamais une liste partielle/devinée (même discipline que `ComfyUIEngine.list_samplers()`/`list_checkpoints()`, Mission 096).
   - Génération : une méthode `generate_image(...)`-équivalente couvrant, selon la présence d'une référence, `POST /sdapi/v1/txt2img` ou `POST /sdapi/v1/img2img` avec : `prompt`, `negative_prompt`, `width`, `height`, `steps`, `cfg_scale`, `sampler_name`, `scheduler` (si le déploiement Forge le sépare de `sampler_name` — à vérifier contre le schéma réel des modèles Pydantic au moment de l'implémentation), `seed`, `override_settings.sd_model_checkpoint` (ou équivalent confirmé), LoRA encapsulé dans `prompt` via `<lora:nom:force>` (section 3.2), `init_images`/`denoising_strength` uniquement en mode img2img (section 3.3).
   - Décodage : la réponse `/sdapi/v1/txt2img`/`/img2img` contient les images en base64 dans son corps JSON (`images: list[str]`) — décodage et écriture sur disque dans `output_directory`, retour du chemin local (même contrat de retour que `ComfyUIEngine.generate_image()` : un `str`, jamais un dict).
   - Toute erreur HTTP (connexion refusée, timeout, code non-2xx) ou réponse structurellement invalide (JSON absent/malformé, champ `images` absent ou vide) lève `ForgeEngineError` avec un message distinguant la cause, jamais une propagation brute d'une exception réseau — même discipline que `ComfyUIEngineError`.
2. **`src/managers/generation_manager.py`** : ajout de `engine`/`checkpoint_name` en paramètres optionnels de `generate()`, `None` → valeur du constructeur (comportement ComfyUI historique inchangé). Aucune autre modification de la méthode.
3. Aucun appelant existant (`InferencePage`, `GenerationWorker`) n'est modifié — ils continuent d'appeler `generate()` sans ces nouveaux paramètres, comportement byte-for-byte identique.

## 7. Tests attendus

`tests/integration/test_forge_engine.py` (Qt-free, transport HTTP entièrement contrôlé — mock/fake, **aucun appel réseau réel**) :

1. Construction — `base_url`/`timeout` par défaut et explicites.
2. Découverte checkpoints — réponse valide, réponse HTTP en échec, réponse structurellement invalide.
3. Découverte LoRA — mêmes trois cas.
4. Découverte samplers — mêmes trois cas.
5. Découverte schedulers — mêmes trois cas.
6. Payload txt2img — prompt/negative prompt, dimensions/steps/CFG, sampler/scheduler, seed, checkpoint demandé, tous présents et correctement nommés dans la requête envoyée.
7. LoRA/strength — vérifie que `<lora:nom:force>` est bien concaténé au prompt envoyé, jamais un champ séparé dans le payload.
8. Payload img2img — `init_images` contient la référence correctement encodée en base64, `denoising_strength` transmis tel quel.
9. Réponse base64 — décodage correct, fichier écrit dans `output_directory`, chemin retourné.
10. Erreurs HTTP — connexion refusée/timeout/code non-2xx → `ForgeEngineError` explicite.
11. Réponses Forge invalides/malformées — JSON absent, champ `images` absent ou vide → `ForgeEngineError` explicite, jamais une exception brute.

`tests/integration/test_generation_manager.py` (extension) :

12. `generate(engine=..., checkpoint_name=...)` — un engine/checkpoint explicite est bien utilisé pour l'appel, jamais celui du constructeur.
13. Omission de ces paramètres — comportement strictement identique à avant cette mission (non-régression du chemin ComfyUI historique, y compris l'interaction déjà existante avec `lora_name`/`lora_strength`).
14. Suite complète : nombre exact confirmé, exit 0.

Aucun appel réseau réel dans aucun de ces tests. Aucun Forge, ComfyUI ou GPU réel sollicité.

## 8. Smoke réel — explicitement reporté à M108

M107 est une fondation invisible, entièrement vérifiable avec un transport HTTP contrôlé (mocks). **Le smoke Forge réel n'est pas un critère de clôture de cette mission** — il sera exigé en M108, lorsque la chaîne complète `Settings → Inference → Forge → génération → preview → Accept/Reject/Regenerate → Images` sera réellement câblée. Forge ne sera jamais lancé par Claude sans autorisation explicite de l'architecte, exactement comme pour ComfyUI et OneTrainer — et son API (`--api`) devra être activée manuellement par l'architecte lorsque ce smoke deviendra nécessaire.

## 9. Critères de clôture

1. `ForgeEngine` implémenté exactement selon le périmètre de la section 6, testé selon la section 7.
2. `GenerationManager.generate()` accepte `engine`/`checkpoint_name` par-appel, avec un comportement byte-for-byte identique pour tout appel existant qui ne les fournit pas.
3. Zéro nouveau champ `ApplicationSettings`, zéro nouveau widget `SettingsPage`/`InferencePage` — l'application démarre et se comporte exactement comme avant.
4. Suite complète verte au nombre exact, `git diff --check` propre.
5. Aucun élément de la section 5 n'a été ajouté.
6. Aucune modification de `src/domain/`, `src/ui/`, `ApplicationSettings`, `LoRALibraryManager`.

## 10. Documentation

- M107 ne livre **aucune fonctionnalité Forge visible** — c'est une fondation technique pure.
- **M108** est la mission destinée à l'intégration utilisateur réelle : Settings Forge minimaux, sélecteur de moteur dans `InferencePage`, généralisation de l'exposition Central Library, câblage checkpoint/LoRA/références, smoke réel.
- Le smoke réel Forge est explicitement reporté à M108. L'architecte devra alors autoriser et démarrer Forge avec `--api` activé lui-même, avant que ce smoke ne soit exécuté.
- La petite erreur documentaire déjà signalée (le bouton "Parcourir" attribué à tort à `onetrainer_path` dans `docs/PROJECT_CONTEXT.md`) reste hors périmètre de M107 et sera corrigée lors d'une régularisation documentaire appropriée.

## 11. Autorisation

Ce document a servi de contrat avant toute implémentation. Le code n'a été écrit qu'après validation explicite de ce périmètre par l'architecte — voir section 12 pour le résultat réel complet.

## 12. Résultat réel

### 12.1 Implémentation — conforme au périmètre exact, avec une correction architecturale

`src/engines/forge_engine.py` créé exactement selon le périmètre de la section 6 : `ForgeEngine`/`ForgeEngineError`, découverte (`list_checkpoints()`/`list_loras()`/`list_samplers()`/`list_schedulers()` via `GET /sdapi/v1/sd-models`/`/loras`/`/samplers`/`/schedulers`), `generate_image()` choisissant `POST /sdapi/v1/txt2img` ou `/img2img` selon la présence d'une référence, LoRA encapsulé via `<lora:nom:force>` (aucun champ séparé), décodage base64 robuste (préfixe `data:image/...;base64,` optionnel toléré en défense), erreurs HTTP/réponses invalides normalisées en `ForgeEngineError`. Payload plat confirmé — aucun `forge_workflows.py` séparé n'a été nécessaire, la construction du payload est restée interne à `forge_engine.py` (section 3.1, hypothèse confirmée).

`src/managers/generation_manager.py` généralisé exactement selon la section 3.4/6 : `generate()` accepte `engine`/`checkpoint_name` en paramètres optionnels par-appel, `None` repliant sur les valeurs du constructeur — comportement ComfyUI historique strictement inchangé pour tout appelant qui ne les fournit pas. `InferencePage`/`GenerationWorker` n'ont reçu aucune modification.

**Correction architecturale demandée par l'architecte après une première ébauche, appliquée avant clôture** : la première implémentation faisait dépendre `GenerationManager` de l'identité concrète du moteur (`isinstance(target_engine, ForgeEngine)`) pour choisir entre transmettre `denoise` (ComfyUI) ou `denoising_strength` (Forge) — un couplage explicitement refusé, contraire à l'objectif même de cette mission. Corrigé en renommant le paramètre Python de `ForgeEngine.generate_image()` de `denoising_strength` en **`denoise`**, identique au nom déjà utilisé par `ComfyUIEngine.generate_image()` (Mission 024, jamais modifié) : `GenerationManager` transmet désormais toujours `denoise=reference_strength`, quel que soit le moteur ciblé, sans branchement d'aucune sorte sur son type. `ForgeEngine` reste le seul endroit qui traduit ce nom Python commun vers le nom natif du champ JSON réellement envoyé à l'API Forge (`payload["denoising_strength"] = denoise`) — la séparation entre le nom du paramètre Python (contrat Toolkit commun) et le nom du champ du protocole réseau (contrat propre à Forge) est désormais explicite et documentée dans `forge_engine.py`. **Aucune modification de `ComfyUIEngine`/`comfyui_engine.py` n'a été nécessaire** — resté hors du périmètre fermé de cette mission du début à la fin.

`GenerationManager` ne contient, après correction, aucun `isinstance` contre un type de moteur concret, aucune connaissance de `denoising_strength`, aucune connaissance de `/sdapi/...`, et aucune syntaxe LoRA spécifique à un moteur — verrouillé par deux tests dédiés lisant directement le source du module (`test_generation_manager_source_never_mentions_denoising_strength`, `test_generation_manager_source_never_isinstance_checks_an_engine_type`).

### 12.2 Checkpoint — `override_settings` avec restauration garantie, vérifié contre le code réel

Contrainte ajoutée par l'architecte avant l'implémentation de ce point précis : un `checkpoint_name` par appel ne doit jamais modifier durablement le checkpoint global de Forge. Vérifié directement dans le code source réel de l'installation Forge (`modules/processing.py::process_images()`, dont le docstring dit littéralement *"applies settings overrides (if any) before processing images, then restores settings as applicable"*) : `override_settings={"sd_model_checkpoint": ...}` associé à `override_settings_restore_afterwards=True` (déjà le défaut natif de Forge) est le mécanisme utilisé — Forge capture la valeur globale précédente (`stored_opts`) avant d'appliquer l'override (`set_config(..., save_config=False)`, jamais persisté sur disque) et la restaure dans un bloc `finally` une fois la génération terminée. **`/sdapi/v1/options` n'est jamais utilisé par `ForgeEngine`**, à aucun moment. Test dédié : `test_checkpoint_uses_override_settings_with_restoration_enabled` (vérifie le payload exact envoyé) et `test_checkpoint_never_reaches_sdapi_options`.

### 12.3 Périmètre respecté — aucun débordement

Confirmé par l'audit final du diff avant staging : aucune modification de `ApplicationSettings`, `SettingsPage`, `InferencePage`, `LoRALibraryManager`, ni de tout autre fichier `src/ui/`/`src/domain/`. Aucun smoke Forge réel exécuté ni exigé — reporté à M108, qui reste seule responsable de l'intégration utilisateur réelle (Settings Forge minimaux, sélecteur de moteur dans `InferencePage`, généralisation de l'exposition Central Library, câblage checkpoint/LoRA/références, et le smoke réel lui-même, avec `--api` activé manuellement par l'architecte au moment voulu).

### 12.4 Tests

**60 tests ciblés nets nouveaux** : 46 dans `test_forge_engine.py` (construction, découverte ×4 avec les trois cas — succès/échec HTTP/forme invalide — chacune, upload sans réseau, payload txt2img complet, checkpoint/`override_settings`, LoRA encapsulé, payload img2img/référence/`denoise`↔`denoising_strength`, décodage base64 avec et sans préfixe `data:image/`, extension devinée depuis la signature binaire réelle, erreurs HTTP/réponses invalides, signature Python de `generate_image()` verrouillée sur `denoise`), 14 dans `test_generation_manager.py` (`engine`/`checkpoint_name` par-appel, bascule ComfyUI→Forge→ComfyUI sans état périmé, duck-typing, normalisation `ForgeEngineError`, agnosticisme de moteur pour `denoise` verrouillé par lecture directe du source). Suite complète **2123/2123** (2063 avant M107 + 60 nets nouveaux — 45 puis 46 dans `test_forge_engine.py` après l'ajout d'un test de signature lors de la correction, 12 puis 14 dans `test_generation_manager.py` après remplacement de la classe de test dédiée au bridging par une classe verrouillant l'absence de couplage), `git diff --check` propre, aucun appel réseau réel, aucun Forge/ComfyUI/GPU réel sollicité par aucun test.

### 12.5 Smoke réel — non exécuté, conformément à la politique de la section 8

Aucun smoke Forge réel n'a été exécuté ni exigé pour cette mission — confirmé conforme à la section 8 : M107 est une fondation entièrement vérifiable par transport HTTP contrôlé, et le smoke réel (nécessitant que l'architecte démarre Forge avec `--api` activé manuellement) reste explicitement la responsabilité de M108.
