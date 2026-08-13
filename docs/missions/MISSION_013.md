# Mission 013 — Verticale minimale Inference

Source : historique direct de la conversation de développement (audit architectural préalable du premier consommateur de `ComfyUIEngine`, implémentation, revue technique finale ayant identifié et corrigé une condition de course QThread, smoke test réel complet contre ComfyUI Desktop), vérifié contre le code réel et la suite de tests.

## Objectif

Livrer la première verticale fonctionnelle réelle d'AI Studio Toolkit : un utilisateur saisit un prompt dans `InferencePage`, clique sur "Générer", obtient une image réelle sans bloquer l'interface, et retrouve cette image dans `Workspace.images`/`ImagesPage`. Premier consommateur réel de `ComfyUIEngine` (Mission 012).

## Architecture

```
InferencePage (bouton "Générer", saisie prompt)
  ↓ clic
GenerationWorker (QObject) déplacé dans un QThread
  ↓ appel bloquant, hors thread UI
GenerationManager (Qt-free)
  ↓ délégation
ComfyUIEngine (Mission 012, inchangé dans son contrat générique)
  ↓ fichier local téléchargé
signal Qt finished(path)
  ↓ slot exécuté sur le thread principal
WorkspaceManager.add_images([path]) (déjà existant, Mission 006/011)
  ↓
Workspace.images → save() → WORKSPACE_SAVED (déjà existant)
  ↓
ImagesPage.update_images() (déjà câblé, aucun nouveau canal)
```

### `GenerationManager` (`src/managers/generation_manager.py`)

Nouveau Manager minimal, volontairement d'une forme différente des Managers CRUD existants : pas de collection Domain, pas d'`active_id`, un unique flag transitoire `_busy` (même nature que les `active_*_id` déjà utilisés partout — état runtime, jamais persisté). Responsabilités strictes : recevoir `prompt_text`/`output_directory`, déléguer à `ComfyUIEngine.generate_image()`, retourner le chemin généré, refuser une génération concurrente. **Strictement Qt-free** (aucun import PySide6, vérifié par test) — ne connaît ni `WorkspaceManager`, ni l'UI, ni le thread qui l'appelle. Normalise `ComfyUIEngineError` et `OSError` (erreurs filesystem locales, documentées ainsi depuis Mission 012) en une unique `GenerationError`, même principe que `WorkspaceManagerError` enveloppant `WorkspaceStorageError`.

Signature retenue : `generate(self, prompt_text: str, output_directory: str) -> str` — dérivée directement du contrat réel de `ComfyUIEngine.generate_image()`, aucun paramètre ajouté par anticipation. `checkpoint_name` est fixé à la construction du Manager (`__init__(comfyui_engine, checkpoint_name=DEMO_CHECKPOINT_NAME)`), pas par appel — `InferencePage` n'a aujourd'hui aucun sélecteur de checkpoint.

### `GenerationWorker` (`src/ui/generation_worker.py`)

Unique classe du projet connaissant à la fois Qt et `GenerationManager`. `QObject` déplacé dans un `QThread` via `moveToThread()` (premier code de threading du projet — idiome Qt standard "Worker Object", sans précédent interne à respecter). Exécute l'appel bloquant hors thread principal, traduit succès/échec en signaux `finished(str)`/`failed(str)`. Toute exception (y compris non documentée) est capturée avant de quitter le worker — aucune ne traverse la frontière de thread.

### `InferencePage` (`src/ui/pages/inference_page.py`)

Devient fonctionnelle (`❌` → `✅`). Validation minimale (prompt vide refusé proprement, aucun Workspace ouvert refusé proprement), bouton désactivé pendant la génération et systématiquement réactivé (succès ou erreur), `output_directory` recalculé à chaque clic depuis `workspace.root / "outputs"` (dossier déjà créé par `WorkspaceStorage.create_directories()` — aucune nouvelle logique de persistance). `WorkspaceManager.add_images()` est appelé **depuis le thread principal** (jamais depuis le worker), décision explicite : `Workspace`/`WorkspaceManager` ne sont pas thread-safe.

### `main_window.py` — composition root

Instancie `ComfyUIEngine`/`GenerationManager`, câble `InferencePage`, ajoute `closeEvent()`. Deux constantes explicitement documentées comme spécifiques à cette machine, non universelles :
```python
COMFYUI_BASE_URL = "http://127.0.0.1:8000"        # observé, pas le défaut 8188 de ComfyUIEngine
COMFYUI_CHECKPOINT_NAME = "v1-5-pruned-emaonly-fp16.safetensors"  # observé, pas DEMO_CHECKPOINT_NAME
```
`ApplicationSettings` non modifié — `comfyui_url` reste hors périmètre, identifié comme besoin futur.

### Extension `ComfyUIEngine` (Mission 012 → 013)

Seule `generate_image()` gagne un paramètre optionnel `checkpoint_name: str = DEMO_CHECKPOINT_NAME`, transmis à `build_demo_workflow()` — nécessité réelle démontrée (le checkpoint par défaut n'existe pas exactement sous ce nom sur l'installation réelle). Additif, rétrocompatible (l'appel à 2 arguments positionnels de Mission 012 reste valide, comportement par défaut identique). **Les trois primitives génériques (`submit`/`wait_for_result`/`download_output`) restent strictement inchangées** — aucune connaissance de checkpoint/modèle/provider n'y entre.

## Ownership de l'image générée

`Workspace.images`, via `WorkspaceManager.add_images()` déjà existant — aucune ligne de persistance nouvelle. `Dataset.images` non touché. Aucun nouvel événement EventBus : `WORKSPACE_SAVED` (déjà déclenché par `add_images()`) reste l'unique canal, `ImagesPage` se rafraîchit via son câblage déjà existant dans `main_window.py`. Le modèle d'ownership Mission 011 (deux pools indépendants) n'est pas modifié — seule la pool `Workspace.images` est choisie pour ce premier cas d'usage, cohérente avec le fait qu'`InferencePage` n'a aucun contexte Character/Dataset.

## Correction de revue finale — condition de course QThread

Une revue technique dédiée, effectuée avant clôture, a identifié une divergence réelle : `worker.finished`/`worker.failed` réactivaient le bouton **avant** que `thread.finished → _cleanup_thread()` ne s'exécute (livraison en file sur le thread principal). `_cleanup_thread()` relisait `self._worker`/`self._thread` **au moment de son exécution différée** — si une génération était relancée dans cette fenêtre, l'ancien cleanup pouvait détruire/réinitialiser les références du nouveau cycle en cours.

Corrigée avant clôture : `worker`/`thread` sont désormais **capturés par valeur** dans la lambda connectée à `thread.finished` (`thread.finished.connect(lambda: self._cleanup_thread(worker, thread))`), et `_cleanup_thread(self, worker, thread)` n'agit que sur les objets reçus — la remise à `None` de `self._worker`/`self._thread` est conditionnée (`if self._worker is worker: ...`), ne s'appliquant que si ces références pointent encore vers ce cycle précis. 4 tests ajoutés, dont deux avec de vrais `QThread` et reclic immédiat dès réactivation du bouton, capturant tout message Qt via `qInstallMessageHandler` — aucune occurrence de "destroyed while running" observée.

Cette information fait partie de l'historique technique réel de la mission et est volontairement conservée, conformément à la règle du projet de ne jamais effacer une divergence corrigée en cours de mission.

## Limite connue — shutdown sans annulation réelle

`MainWindow.closeEvent() → InferencePage.shutdown() → thread.quit() → thread.wait()`. `quit()` ne peut interrompre un appel `submit()`/`wait_for_result()`/`download_output()` déjà en cours (le worker n'a pas encore atteint sa propre boucle d'événements à ce stade — il exécute encore `run()` de façon synchrone). `wait()` (sans timeout) bloque donc la fermeture de l'application jusqu'à la fin naturelle de l'appel réseau ou l'expiration du timeout interne de `ComfyUIEngine` (120 s par défaut). Shutdown propre (aucun thread orphelin, aucun crash) mais **pas une annulation** — limite explicitement acceptée pour Mission 013, non résolue, non testée empiriquement pendant le smoke test réel (fermeture effectuée uniquement hors génération active).

## Tests

- Nouveaux fichiers : `test_generation_manager.py` (10, pur Python, `ComfyUIEngine` mocké, vérifie l'absence d'import Qt et que `GenerationManager` n'est pas un `QObject`), `test_generation_worker.py` (4, `QThread` réel, `GenerationManager` mocké), `test_inference_page.py` (9, widgets Qt réels, `GenerationManager` mocké — comportement bouton, non-blocage UI, ownership Image, rafraîchissement `ImagesPage`, cycle complet répété, condition de course).
- `test_comfyui_engine.py` étendu (23 → 25) pour la nouvelle paramétrisation de `checkpoint_name`.
- **138/138 tests d'intégration verts** (113 précédents + 25 nouveaux). Suite entièrement mockée, aucun accès réseau réel, aucune instance ComfyUI, aucun GPU.

## Smoke test réel — verticale complète validée

Réalisé depuis la vraie interface (point d'entrée `src/core/main.py`, wiring de production réel `MainWindow → InferencePage → GenerationManager → ComfyUIEngine`), aucun mock, aucun appel direct depuis un script.

- **Backend** : ComfyUI Desktop `v1.0.38`, backend ComfyUI `0.24.1`, `http://127.0.0.1:8000` (port réellement détecté, pas le défaut 8188 — confirmé par log, port TCP en écoute, et `/system_stats`).
- **Checkpoint réellement utilisé** : `v1-5-pruned-emaonly-fp16.safetensors`, injecté via la composition root (`main_window.py`), sans modification de `ComfyUIEngine` ni de `GenerationManager`.
- **Workspace de test** : `Mission013-SmokeTest`, créé depuis l'application réelle, hors dépôt.
- **Deux générations GPU réelles successives validées** : "a red cube on a white background" (`prompt_id 491be886-3736-49a7-870d-99c8c7ce8ebc`, node `9`/`SaveImage`, fichier `AIStudioToolkit_00002_.png`) puis, après cycle QThread complètement terminé, "a blue sphere on a white background" (fichier `AIStudioToolkit_00003_.png`) — les deux fichiers confirmés identiques en taille entre le répertoire de sortie interne de ComfyUI et le téléchargement local AI Studio Toolkit, PNG valides.
- **UI responsive** : navigation réelle vers `ImagesPage` effectuée pendant la première génération, sans freeze.
- **Persistance/reload** : Workspace fermé puis rouvert via l'UI réelle — image toujours présente, `image_id` strictement stable (`606dc604-0a8b-46fa-81ea-abf69fb37caa`).
- **`ImagesPage` rafraîchie via `WORKSPACE_SAVED`** exclusivement, sans rafraîchissement manuel, sans nouveau canal.
- **Aucun ajout dans `Dataset.images`** (`"datasets": []` confirmé dans `project.json` aux deux vérifications).
- **Aucun message Qt anormal** (sortie process vide sur toute la durée, `exit code 0` à la fermeture normale de l'application).
- **Aucune divergence** entre le comportement réel et les garanties déjà couvertes par la suite automatisée.

## Besoins futurs identifiés par l'usage réel (non décidés, non implémentés)

Trois besoins UX/architecture réels sont apparus pendant le smoke test — explicitement **hors périmètre de Mission 013**, à évaluer par un futur audit, aucune architecture ni décision anticipée ici :

1. **`ImagesPage` — galerie et aperçu** : l'affichage actuel en simples chemins de fichiers est fonctionnel mais insuffisant à l'usage (miniatures, galerie visuelle, sélection, aperçu agrandi, informations de base).
2. **`InferencePage` — images de référence** : le premier cas réel montre le besoin d'utiliser une ou plusieurs images de référence avec le prompt (planche de personnage, portrait, tenue, pose, décor...), à concevoir de façon compatible avec différents mécanismes ComfyUI futurs (image-to-image, IP-Adapter, ControlNet ou autres) — architecture non supposée ici.
3. **`InferencePage` — sélection du moteur/backend** : le besoin multi-engine (ComfyUI, Automatic1111, Fooocus, Forge...) est désormais un besoin utilisateur réel observé, plus seulement une anticipation du Blueprint — fait à prendre en compte lors des futurs audits Engine/Plugin. ComfyUI reste aujourd'hui le seul Engine réellement implémenté et validé ; aucun autre Engine, ni Plugin, ni AI Orchestrator n'est créé pour anticiper ce besoin. La compatibilité de ComfyUI avec des workflows locaux ou des nodes/services cloud (établie en Mission 012) reste inchangée et pertinente pour ce futur audit.

## Fichiers créés

- `src/managers/generation_manager.py`
- `src/ui/generation_worker.py`
- `tests/integration/test_generation_manager.py`
- `tests/integration/test_generation_worker.py`
- `tests/integration/test_inference_page.py`

## Fichiers modifiés

- `src/engines/comfyui_engine.py` (extension additive `checkpoint_name` sur `generate_image()` uniquement)
- `src/ui/main_window.py` (composition root)
- `src/ui/pages/inference_page.py` (fonctionnelle)
- `tests/integration/test_comfyui_engine.py` (2 tests adaptés/ajoutés)
- `docs/PROJECT_CONTEXT.md`

Liste vérifiée directement depuis `git status --short`/`git diff --stat` au moment de la clôture. Aucun fichier hors ce périmètre (pas de nouveau Domain, pas d'`ApplicationSettings`, pas de `requirements.txt`, pas de `CLAUDE.md`/`AGENTS.md`, pas de Job/Service/Plugin/AI Orchestrator).

## Critères d'acceptation — état final

- Bouton "Générer" fonctionnel sans geler l'UI : ✅, vérifié par test automatisé et smoke test réel.
- Image réellement ajoutée à `Workspace.images`, visible dans `ImagesPage` : ✅.
- `GenerationManager` sans dépendance Qt, testable sans `QApplication` : ✅, vérifié par test dédié.
- Condition de course QThread éliminée : ✅, corrigée et testée (déterministe + bout en bout).
- Aucun `Job`/`Service`/`AI Orchestrator`/`Plugin` introduits : ✅.
- Aucune modification du modèle d'ownership Mission 011 : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ (138/138).
- Smoke test réel complet, deux générations GPU successives validées : ✅.
- Aucune nouvelle dépendance : ✅, `requirements.txt` inchangé.
- Documentation de fin de mission complète : ✅ (ce document + `docs/PROJECT_CONTEXT.md`).

## Dettes hors périmètre (volontairement non traitées par Mission 013)

- Limite shutdown sans annulation réelle (voir section dédiée ci-dessus) — non résolue.
- `ApplicationSettings.comfyui_url` — toujours différé.
- Réutilisation `Prompt`/`Workflow`/`Model` Domain — toujours différée (mêmes réserves qu'en Mission 012 : formats non garantis).
- Historique de générations, annulation, générations simultanées, sélection Dataset comme pool alternatif — non traités.
- Les trois besoins futurs identifiés par l'usage réel (section dédiée ci-dessus) — explicitement non implémentés, non architecturés.
- Toutes les dettes déjà connues avant Mission 013 (ambiguïté `Training`/`Training History`, `BasePage` mort, incohérences Blueprint `Job`, support Linux/macOS `ApplicationSettingsStorage`) — inchangées.

## Commit correspondant

Mission 013 sera clôturée en commit(s) documentaire(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash n'est fixé en dur dans ce document avant sa création — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log`.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission013`). Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission013` une fois créé.

## État final

Mission terminée. Première verticale fonctionnelle réelle du projet : `InferencePage → GenerationManager → GenerationWorker/QThread → ComfyUIEngine → Workspace.images → ImagesPage`, validée à la fois par 138 tests automatisés entièrement mockés et par un smoke test réel complet (deux générations GPU réussies contre ComfyUI Desktop). Une condition de course réelle dans le cycle de vie QThread a été trouvée et corrigée avant clôture. Trois besoins futurs ont été identifiés par l'usage réel (galerie Images, images de référence Inference, sélection multi-engine) sans être architecturés ni implémentés. Mission 014 non définie ; nécessitera son propre audit architectural, qui devra notamment tenir compte de ces trois besoins désormais réels.
