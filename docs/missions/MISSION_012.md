# Mission 012 — ComfyUI Engine minimal

Source : historique direct de la conversation de développement (décision architecturale préalable local/cloud avec ComfyUI comme premier moteur choisi, audit technique de la frontière AI Studio Toolkit / ComfyUI sourcé sur la documentation officielle, complément d'audit local/cloud, implémentation, revue technique finale), vérifié contre le code réel et la suite de tests.

## Objectif

Introduire la première infrastructure IA réelle du projet sous la forme d'un moteur ComfyUI minimal, sans introduire prématurément `Plugin`, `Service`, `AI Orchestrator`, `Job` ou une UI d'exécution. Mission strictement limitée à l'établissement d'un contrat technique validé entre AI Studio Toolkit et une instance serveur ComfyUI — aucune fonctionnalité de génération n'est exposée à l'utilisateur.

## Décision architecturale préalable

Deux audits préalables (hors implémentation) ont établi, avant tout code :
- Le choix du premier moteur concret : **ComfyUI local**, premier cas d'usage : génération d'image à partir d'un workflow fixe/minimal — décision explicite de l'architecte, motivée par le besoin de sortir des abstractions hypothétiques (`Service`/`AI Orchestrator`/`Plugin`/`Engine`/`Job` génériques, jamais construits sans premier cas réel).
- La frontière retenue : `AI Studio Toolkit → ComfyUI`, jamais `AI Studio Toolkit → un modèle/provider particulier`. Un complément d'audit dédié a vérifié que le protocole HTTP de ComfyUI (`/prompt`, `/history`, `/view`) est générique par construction — il ne distingue pas un node exécutant un modèle local d'un node appelant un service cloud (confirmé par l'existence réelle de custom nodes communautaires type Gemini/Nano Banana s'intégrant au même protocole). Cette généricité a justifié de concevoir `ComfyUIEngine` autour de primitives génériques plutôt que d'une seule méthode opinionated.

## Architecture

```
AI Studio Toolkit → ComfyUIEngine → instance serveur ComfyUI (locale ou distante)
```

`ComfyUIEngine` (`src/engines/comfyui_engine.py`, couche Infrastructure) expose trois primitives génériques, qui constituent le contrat architectural réel du moteur :

- `submit(workflow: dict, client_id: str) -> str` — soumet un workflow API-format opaque, retourne le `prompt_id`.
- `wait_for_result(prompt_id: str, poll_interval: float = 1.0) -> dict` — attend un résultat exploitable par polling, retourne la structure `outputs` de ComfyUI.
- `download_output(filename: str, subfolder: str, type_: str, output_directory: str) -> str` — télécharge un fichier de sortie nommé, retourne son chemin local.

Aucune des trois ne connaît le contenu du workflow (checkpoint, LoRA, modèle, provider) — vérifié par test dédié (inspection du code source des trois méthodes).

`generate_image(prompt_text: str, output_directory: str) -> str` est une **convenience method de démonstration**, composée strictement des trois primitives ci-dessus + `build_demo_workflow()`. Elle ne fait partie ni du contrat générique ni de son extension — un futur Manager pourra utiliser directement `submit()`/`wait_for_result()`/`download_output()` avec n'importe quel workflow, sans jamais passer par `generate_image()`.

`build_demo_workflow(prompt_text: str, checkpoint_name: str = DEMO_CHECKPOINT_NAME) -> dict`, fonction libre **hors de la classe** `ComfyUIEngine`, construit le graphe API-format fixe de démonstration (CheckpointLoaderSimple → 2×CLIPTextEncode → EmptyLatentImage → KSampler → VAEDecode → SaveImage). `checkpoint_name` (défaut `v1-5-pruned-emaonly.safetensors`) reste entièrement isolé dans cette fonction — jamais une propriété de `ComfyUIEngine`.

`ComfyUIEngine` n'importe rien de `src/domain/` et ne retourne jamais d'objet Domain — uniquement des `str`/`dict` (contrainte "Infrastructure ignorant le Domain" de `CLAUDE.md`). Aucune image générée n'est ajoutée à `Workspace.images` ou `Dataset.images` : cette décision d'ownership reste différée jusqu'à l'existence d'un vrai consommateur/Manager (cohérence stricte avec le modèle d'ownership `Image` établi en Mission 011).

## Protocole

`POST /prompt` (corps `{"prompt": workflow, "client_id": ...}`) → `GET /history/{prompt_id}` (polling) → `GET /view?filename=&subfolder=&type=`. Pas de WebSocket en Mission 012 — la progression n'est pas observée en temps réel, seule la complétion l'est, par polling avec timeout. Protocole vérifié contre la documentation officielle ComfyUI (`docs.comfy.org/development/comfyui-server/comms_routes`, `docs.comfy.org/development/api-development/workflow-api-format`) au moment de l'audit préalable.

## Local / cloud

**Support architectural actuel** : une instance serveur ComfyUI compatible avec le protocole utilisé (`/prompt`/`/history`/`/view`) peut recevoir un workflow opaque via `submit()`. Ce workflow peut conceptuellement contenir des nodes exécutant des modèles locaux, ou des nodes appelant eux-mêmes des services/API cloud (le protocole ComfyUI ne distingue pas les deux). `ComfyUIEngine` ne connaît et ne doit connaître ni le modèle ni le provider utilisé par les nodes d'un workflow donné — vérifié automatiquement par test (absence des termes `checkpoint`/`sdxl`/`flux`/`lora`/`gemini`/`gpt`/`nano_banana` dans les signatures des méthodes génériques).

**Non implémenté** — explicitement hors périmètre de Mission 012 : client direct vers une éventuelle API Comfy Cloud hébergée (endpoints, authentification et protocole propres, potentiellement différents de ceux d'une instance serveur ComfyUI classique) ; credentials cloud ; clés API ; gestionnaire de providers ; `GPTImageEngine` ; `NanoBananaEngine` ; `FluxEngine` ; `SDXLEngine`. Cette distinction est documentée explicitement pour éviter toute fausse promesse architecturale future : Mission 012 rend AI Studio Toolkit capable de parler à **une instance serveur ComfyUI**, pas à un service cloud hébergé par l'écosystème Comfy directement.

## Corrections de revue finale

Une revue technique dédiée, effectuée avant clôture, a identifié deux divergences réelles entre l'implémentation initiale et la spécification validée :

1. `wait_for_result()` considérait initialement comme terminé tout `outputs` non vide, sans vérifier qu'une image réellement exploitable y figurait — un `outputs` présent mais sans `images`, une liste `images` vide, ou une référence sans `filename` auraient été traités comme un succès.
2. `_first_image_reference()` acceptait initialement une référence image sans `filename`.

Corrigées avant clôture :
- `wait_for_result()` continue désormais le polling tant qu'aucune référence image structurellement exploitable n'est trouvée dans `outputs`, jusqu'à l'apparition d'un résultat exploitable ou l'expiration du timeout — aucun système de Job ou de machine à états introduit, seule la condition de sortie de la boucle de polling déjà existante a changé.
- `_first_image_reference()` ne retourne désormais une référence que si elle porte un `filename` non vide.
- 7 tests ajoutés pour couvrir précisément ces propriétés (polling face à `outputs` sans `images`, liste `images` vide, référence sans `filename` ; non-mutation du workflow par `submit()` ; encodage URL des caractères spéciaux dans `download_output()` ; écriture des octets sans transformation ; séparation architecturale des primitives vis-à-vis du workflow de démonstration), 1 test existant réécrit pour refléter le nouveau comportement correct.

Cette information fait partie de l'historique technique réel de la mission et est volontairement conservée, conformément à la règle du projet de ne jamais effacer une divergence corrigée en cours de mission.

## Tests

- Nouveau fichier `tests/integration/test_comfyui_engine.py` — **23 tests**, entièrement mockés (`unittest.mock.patch` sur `urllib.request.urlopen`) : aucun accès réseau réel, aucune instance ComfyUI réelle, aucun GPU. Couverture : contrat `submit()` (succès, rejet, serveur inaccessible, réponse invalide, non-mutation du workflow), `wait_for_result()` (résultat immédiat, polling multi-appels, timeout, 3 cas de non-exploitabilité), `download_output()` (écriture/retour de chemin, encodage URL, octets non transformés, erreurs HTTP/réseau), `generate_image()` (flux complet mocké, absence d'image après timeout), et 4 tests architecturaux dédiés (absence d'import Domain, absence de connaissance provider dans le contrat générique, isolation de `checkpoint_name`, séparation stricte primitives/workflow de démonstration).
- **113/113 tests d'intégration verts** (90 précédents inchangés + 23 nouveaux).
- Les tests ne valident que le contrat Python et le comportement face à des réponses HTTP simulées déterministes — **aucun test n'effectue de requête réelle vers ComfyUI**.

## Limites — état après smoke test empirique post-clôture

À la clôture de Mission 012 (commit et tag), les points suivants étaient explicitement non validés empiriquement. Un smoke test manuel réalisé après le tag et la publication de la Release (voir "Validation empirique post-clôture" ci-dessous) en a validé une partie :

**Validés empiriquement depuis** :
- Connexion réelle à une instance ComfyUI (ComfyUI Desktop, locale, `http://127.0.0.1:8000`).
- Soumission réelle de `build_demo_workflow()` à un serveur ComfyUI réel (`submit()`, `wait_for_result()`, `download_output()` tous exercés sans mock).
- Génération GPU réelle (NVIDIA Quadro P4000).
- Disponibilité réelle d'un checkpoint compatible via le paramètre `checkpoint_name` (le nom par défaut de `build_demo_workflow()` n'existait pas exactement sur cette installation — voir détail ci-dessous).

**Toujours non validés** :
- Comportement face à de vrais custom nodes (y compris les nodes cloud Gemini/GPT Image/Nano Banana cités dans l'audit local/cloud).
- Tout appel direct à une éventuelle API Comfy Cloud hébergée.
- Ce smoke test reste manuel et ponctuel, réalisé hors du dépôt Git — `tests/integration/test_comfyui_engine.py` reste entièrement mocké, sans accès réseau réel ; la suite automatisée du projet ne dépend et ne dépendra pas d'une instance ComfyUI disponible.

## Validation empirique post-clôture (smoke test réel)

Après le tag `v0.2-mission012` et la publication de la GitHub Release, à la demande de l'architecte, un smoke test manuel a été exécuté contre une instance ComfyUI réellement démarrée sur la machine de développement — hors périmètre de la mission elle-même, sans modification du dépôt.

- **Backend** : ComfyUI Desktop pour Windows. URL réellement détectée : `http://127.0.0.1:8000` — identifiée depuis les logs Desktop (`app.log`, ligne `[INFO] To see the GUI go to: http://127.0.0.1:8000`), corroborée indépendamment par `GET /system_stats` (HTTP 200) et par le port TCP réellement en écoute (processus `python.exe` confirmé via `Get-NetTCPConnection`). Le port par défaut `8188` n'était pas utilisé — vérifié, non supposé.
- **Environnement** : ComfyUI `0.24.1`, PyTorch `2.5.1+cu121`, GPU NVIDIA Quadro P4000.
- **Checkpoints réellement détectés** (`GET /object_info/CheckpointLoaderSimple`) : `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors`, `juggernautXL_v8Rundiffusion.safetensors`, `v1-5-pruned-emaonly-fp16.safetensors`.
- **Checkpoint réellement utilisé** : `v1-5-pruned-emaonly-fp16.safetensors`. Le nom par défaut de `build_demo_workflow()` (`v1-5-pruned-emaonly.safetensors`, sans `-fp16`) n'était pas présent exactement sous ce nom sur cette installation — confirmé, pas supposé. Le paramètre `checkpoint_name` a permis d'utiliser le checkpoint réellement disponible **sans aucune modification de `ComfyUIEngine`**, exactement comme conçu — cette observation confirme empiriquement que le choix de rendre le checkpoint du workflow de démonstration paramétrable fonctionne comme prévu.
- **Séquence réelle validée, sans aucun mock** : `submit()` (un `prompt_id` réel a été obtenu), `wait_for_result()` (lecture réelle de `GET /history/{prompt_id}` jusqu'à résultat exploitable), extraction de la référence image, `download_output()` (`GET /view`, image réellement téléchargée). Image PNG valide obtenue (signature `89 50 4E 47 0D 0A 1A 0A`), 282 113 octets.
- **Workflow utilisé** : uniquement `build_demo_workflow()` de Mission 012, temporaire — jamais le workflow affiché dans l'UI ComfyUI Desktop au moment du test.
- **Aucun fichier du repository modifié pendant ce smoke test** — confirmé par `git status --short` avant/après, `HEAD` inchangé.

## Fichiers créés

- `src/engines/__init__.py`
- `src/engines/comfyui_engine.py`
- `tests/integration/test_comfyui_engine.py`

## Fichiers modifiés

- `docs/PROJECT_CONTEXT.md`

Liste vérifiée directement depuis `git status --short`/`git diff --stat` au moment de la clôture. Aucun fichier hors ce périmètre (pas de Domain, pas de Manager, pas d'UI, pas d'EventBus, pas d'`ApplicationSettings`, pas de `requirements.txt`, pas de `CLAUDE.md`/`AGENTS.md`).

## Critères d'acceptation — état final

- Frontière architecturale `AI Studio Toolkit → ComfyUI` (pas `→ modèle particulier`) : ✅, vérifiée par test automatisé.
- Primitives génériques (`submit`/`wait_for_result`/`download_output`) indépendantes du workflow de démonstration : ✅, vérifiée par test automatisé.
- `ComfyUIEngine` sans dépendance Domain : ✅, vérifiée par test automatisé.
- Aucune image générée automatiquement ajoutée à `Workspace.images`/`Dataset.images` : ✅ (aucun code de cette nature n'existe).
- Aucune connexion UI/`InferencePage` : ✅.
- Aucun `Job`/`Service`/`AI Orchestrator`/`Plugin`/Domain `Engine`/Domain `Generation`/Manager ComfyUI : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ (113/113).
- Aucune nouvelle dépendance : ✅, `requirements.txt` inchangé.
- Documentation de fin de mission complète : ✅ (ce document + `docs/PROJECT_CONTEXT.md`).

## Dettes hors périmètre (volontairement non traitées par Mission 012)

- Validation réelle contre une instance ComfyUI — aucun environnement ComfyUI n'était disponible pendant l'implémentation de cette mission ; réalisée ultérieurement, hors périmètre de la mission elle-même, via un smoke test manuel post-clôture (voir "Validation empirique post-clôture" ci-dessus).
- Câblage UI (`InferencePage` ou tout autre bouton Qt), et le problème de threading associé (un appel `generate_image()` bloquant depuis le thread Qt gèlerait l'interface) — explicitement différé, non résolu.
- `comfyui_url`/configurabilité de l'adresse du serveur dans `ApplicationSettings` — identifié comme besoin futur, non ajouté (`ApplicationSettings` non modifié).
- Toutes les dettes déjà connues avant Mission 012 (ambiguïté `Training`/`Training History`, `BasePage` mort, incohérences Blueprint `Job`, support Linux/macOS `ApplicationSettingsStorage`) — inchangées, non traitées par cette mission.

## Commit correspondant

Mission 012 est clôturée en **un commit unique** regroupant code, tests et documentation (`src/engines/__init__.py`, `src/engines/comfyui_engine.py`, `tests/integration/test_comfyui_engine.py`, `docs/PROJECT_CONTEXT.md`, `docs/missions/MISSION_012.md`), message `feat: introduce minimal ComfyUI Engine`. Conformément au principe de non-auto-référence adopté après Mission 011, son hash n'est pas fixé en dur dans ce document — vérifier avec `git rev-parse HEAD` immédiatement après clôture, ou en recherchant le message exact dans `git log`.

## Tag / release correspondant

Tag annoté `v0.2-mission012` (message `Mission 012 - ComfyUI Engine`), ciblant le commit de clôture ci-dessus. Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission012`.

## État final

Mission terminée. Première infrastructure IA réelle du projet (`src/engines/`, `ComfyUIEngine`) introduite, sans Plugin/Service/AI Orchestrator/Job/UI d'exécution. 113 tests d'intégration, tous mockés pour cette nouvelle suite. Une génération ComfyUI réelle a depuis été validée empiriquement par un smoke test manuel post-clôture, hors dépôt (voir "Validation empirique post-clôture"). Mission 013 non définie ; le point logique le plus probable à examiner reste le choix du premier consommateur du moteur (Manager et/ou UI), sans décision prise sur ce point à ce stade.
