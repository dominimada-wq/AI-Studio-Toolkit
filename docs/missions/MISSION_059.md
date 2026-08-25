# Mission 059 — ComfyUI LoRA Selection for Generation

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat validé le 2026-08-24 (portée server-side-uniquement, force combinée unique défaut 1.0, exclusion du mapping `LoRA.files`↔ComfyUI). Audit complémentaire n°2 (compatibilité architecture SD1.5/SDXL/FLUX, section 13) réalisé : pipeline confirmé SD1.5/SDXL uniquement, FLUX hors périmètre pré-existant, Option A retenue. **Smoke test réel exécuté par l'architecte contre son installation ComfyUI réelle — PASS** (découverte de 5 LoRA réels, génération txt2img réelle avec LoRA, génération img2img réelle avec `Reference(pose_composition)` + LoRA simultanément, voir section 14). Une régression de taille de fenêtre introduite pendant l'audit d'architecture (section 13.4, hint UI non retourné à la ligne) a été détectée pendant le smoke test réel, sa cause établie avec certitude par la mesure, et corrigée (`application_hint.setWordWrap(True)`, section 15). **1011/1011 tests automatisés verts** (967 précédents + 44 nets nouveaux), `git diff --check` propre. **Validation technique finale accordée par l'architecte le 2026-08-24. Clôture Git et publication GitHub Release entièrement effectuées** — voir section 16.

## 1. Contexte

Un audit factuel du dépôt, réalisé après la clôture complète de Mission 058, a cherché en priorité une fonctionnalité utilisateur concrète encore manquante, une capacité déjà partiellement présente mais non exploitable, ou un besoin futur documenté dont les prérequis sont désormais réunis — plutôt qu'un nouveau tour de nettoyage de code mort (Mission 057/058 en ont déjà traité deux rounds ; aucune anomalie de taille comparable n'a été trouvée cette fois).

**Constat vérifié** : `LoRAManager`/`LoRAPage` gèrent intégralement la fiche technique d'une LoRA côté Workspace depuis Mission 047/050 (fichiers, miniature, `engine`/`architecture`/`trigger_word`/`version`, renommage) — mais **aucune LoRA n'est jamais appliquée lors d'une génération**, quel que soit le moteur. `src/engines/workflows/comfyui_workflows.py` le documente explicitement dans son propre docstring depuis Mission 023 : « not an anticipation of future mechanisms (IP-Adapter, ControlNet, LoRA), which would each get their own function here only once a real need for them is decided. » `GenerationManager`/`ComfyUIEngine`/`ApplicationSettings` ne connaissent aucun concept de LoRA. C'est un cas exact de la distinction déjà documentée dans `PROJECT_CONTEXT.md` (besoin « Sélection de LoRA multi-engine ») entre la **sélection/configuration** du LoRA (déjà livrée, générique, côté Toolkit) et son **chargement/application effective** (spécifique au moteur, jamais livrée pour aucun moteur).

**Mécanisme déjà établi à mirroiter (Mission 025 — sélection de checkpoint)** : `ComfyUIEngine.list_checkpoints()` interroge `GET /object_info/CheckpointLoaderSimple` sur le serveur ComfyUI réellement actif (jamais un dossier local deviné), extrait la liste des noms utilisables, échoue explicitement (`ComfyUIEngineError`) sur toute forme de réponse inattendue — jamais de liste partielle. `SettingsPage` peuple un `QComboBox` éditable avec cette liste (bouton de rafraîchissement), la valeur choisie est persistée dans `ApplicationSettings.comfyui_checkpoint_name`, lue une seule fois au démarrage par `MainWindow` pour construire `GenerationManager` — **contrat "pas de hot reload" déjà explicitement documenté et assumé** pour ComfyUI/Ollama (`main_window.py`, commentaire Mission 018/031), donc pas une nouvelle décision à prendre pour ce candidat.

**`LoraLoader` est un nœud natif ComfyUI** (au même titre que `CheckpointLoaderSimple`/`KSampler`/`CLIPTextEncode`), pas un custom node — contrairement au besoin « second rôle Inference » (IP-Adapter/ControlNet/InstantID/PuLID), ce candidat ne dépend d'aucun mécanisme externe non vérifiable dans mon environnement. Le risque de dépendance externe non maîtrisée, qui bloque explicitement le candidat « second rôle Inference/Dataset de références » (voir section 5), ne s'applique pas ici.

## 2. Mini-audit réalisé

**Comportement actuel** : `build_txt2img_workflow()`/`build_img2img_workflow()` (`comfyui_workflows.py`) construisent un graphe `CheckpointLoaderSimple → (model→KSampler, clip→CLIPTextEncode×2, vae→VAEDecode/VAEEncode)`, sans aucun nœud LoRA. `GenerationManager.__init__(comfyui_engine, checkpoint_name=...)` ne connaît que `checkpoint_name`. `ApplicationSettings` (`src/domain/application_settings.py`) ne porte aucun champ LoRA. `SettingsPage` ne propose aucun contrôle LoRA.

**Comportement cible** : `ComfyUIEngine.list_loras()` (nouvelle méthode, GET `/object_info/LoraLoader`, même parsing défensif que `list_checkpoints()` — `ComfyUIEngineError` sur toute réponse inattendue, jamais de résultat partiel/deviné). `ApplicationSettings` gagne `comfyui_lora_name: str = ""` (vide = aucun LoRA, comportement strictement inchangé — même convention que `ollama_model_name`, pas de valeur hardcodée préexistante à préserver contrairement à `comfyui_checkpoint_name`) et `comfyui_lora_strength: float = 1.0` (valeur par défaut native de `LoraLoader` côté ComfyUI). `SettingsPage` gagne un `QComboBox` LoRA (peuplé via `list_loras()`, même bouton de rafraîchissement que le checkpoint) et un contrôle de force. `GenerationManager` transmet `lora_name`/`lora_strength` à `ComfyUIEngine.generate_image()`, qui les transmet aux deux builders. Quand `lora_name` est vide, les deux graphes restent **strictement identiques (égalité structurelle complète du dict Python, seed aléatoire neutralisé pour la comparaison)**, à leur forme actuelle (même garantie de compatibilité ascendante déjà démontrée par Mission 021/023/024 pour `reference_image`/`denoise`). Quand un `lora_name` est fourni, un nœud `LoraLoader` est inséré entre `CheckpointLoaderSimple` et tout consommateur de `model`/`clip` (`KSampler`, les deux `CLIPTextEncode`) — `vae` continue de venir directement de `CheckpointLoaderSimple`, `LoraLoader` ne le touchant jamais nativement.

**Fichiers concernés** :
- `src/engines/comfyui_engine.py` — nouvelle méthode `list_loras()` ; `generate_image()` gagne `lora_name`/`lora_strength`.
- `src/engines/workflows/comfyui_workflows.py` — les deux builders gagnent `lora_name`/`lora_strength`, insertion conditionnelle du nœud `LoraLoader`.
- `src/managers/generation_manager.py` — `__init__` gagne `lora_name`/`lora_strength`, forwarding vers `generate_image()`.
- `src/domain/application_settings.py` — 2 nouveaux champs additifs, `to_dict()`/`from_dict()` symétriques.
- `src/managers/application_settings_manager.py` — `update()` étendu (mêmes règles d'idempotence que les champs existants).
- `src/ui/pages/settings_page.py` — nouveau `QComboBox`/contrôle de force, refresh via `list_loras()`, même pattern que le checkpoint.
- `src/ui/main_window.py` — `GenerationManager(...)` reçoit les deux nouveaux paramètres depuis `ApplicationSettings`.

**Domain/Manager/UI/Infrastructure** : Domain = `ApplicationSettings` (2 champs additifs uniquement). Manager = `GenerationManager` (constructeur), `ApplicationSettingsManager` (`update()` étendu). UI = `SettingsPage` uniquement. Infrastructure = aucun changement (`ApplicationSettingsStorage` existant suffit, aucune migration).

**EventBus** : aucun nouveau canal — `APPLICATION_SETTINGS_SAVED` (déjà existant) suffit, exactement comme pour `comfyui_checkpoint_name` aujourd'hui.

**Persistance** : `application_settings.json` (hors Workspace, `%LOCALAPPDATA%`) — 2 champs additifs, compatibilité rétroactive triviale (`data.get("comfyui_lora_name", "")`/`data.get("comfyui_lora_strength", 1.0)`), aucune migration nécessaire.

**Tests existants à étendre par symétrie directe** (pattern déjà utilisé pour `checkpoint_name`) : `tests/integration/test_generation_manager.py`, `tests/integration/test_application_settings_roundtrip.py`, `tests/integration/test_settings_roundtrip.py`, `tests/integration/test_settings_page.py`, `tests/integration/test_main_window_comfyui_settings.py`.

**Nouveaux tests à écrire** : `list_loras()` (succès, réponse `LoraLoader` absente/malformée, échec réseau/URL invalide — mirroir exact de `list_checkpoints()`) ; builders (`LoraLoader` inséré quand `lora_name` fourni, absent et graphe structurellement identique sinon — égalité de dict Python, seed aléatoire neutralisé pour la comparaison) ; `GenerationManager.generate()` (forwarding correct, comportement inchangé sans LoRA) ; roundtrip `ApplicationSettings` (nouveaux champs, compatibilité JSON antérieur sans ces clés) ; `SettingsPage` (combobox peuplé, sauvegarde, persistance après réouverture).

**Smoke test réellement exécutable** : cycle manuel réel `SettingsPage` (découverte/sélection d'un LoRA, sauvegarde) + `GenerationManager`/`ComfyUIEngine` contre une instance ComfyUI réelle si disponible au moment de l'implémentation (même format que le smoke test Mission 025/012) ; à défaut, vérification manuelle avec un serveur ComfyUI mocké, comme déjà pratiqué pour d'autres missions Inference sans accès à un serveur réel au moment du test.

**Aucune décision produit ou architecturale substantielle ne reste ouverte.** Trois choix d'implémentation mineurs sont recommandés par précédent direct, à confirmer explicitement avant implémentation (voir section 8).

## 2 bis. Mini-audit complémentaire — mapping LoRA↔ComfyUI, UX, force, workflow

Réalisé à la demande explicite de l'architecte avant validation du contrat, sur quatre points structurants.

**Contrat réel de `LoraLoader`** : nœud natif ComfyUI (pas un custom node). Entrées : `model` (MODEL), `clip` (CLIP), `lora_name` (COMBO, énuméré serveur), `strength_model` (FLOAT, défaut `1.0`), `strength_clip` (FLOAT, défaut `1.0`) — **deux forces réellement distinctes dans le contrat natif, non masquées ici**. Sorties : `MODEL` (0), `CLIP` (1).

**Mapping `LoRA.files` ↔ noms ComfyUI — vérifié, pas supposé** : `LoRAManager.remove_files()` (`src/managers/lora_manager.py:170-196`) documente explicitement que les fichiers de `LoRA.files` « are never copied for this field » — contrairement à `set_thumbnail()`, qui copie réellement dans `<workspace_root>/models/loras/<lora_id>/`. `LoRA.files` contient donc des chemins bruts, potentiellement n'importe où sur le disque de l'utilisateur, **jamais garantis visibles ou nommés identiquement dans le dossier `models/loras/` de ComfyUI**. **Conclusion factuelle : aucun mapping fiable `LoRA.files[i]` → `lora_name` ComfyUI n'existe aujourd'hui.** Un chemin absolu de `LoRA.files` n'est jamais directement consommable par `LoraLoader`.

**Primitive manquante identifiée** (pas une simple absence de code, une vraie question architecturale distincte) : pour rendre un `LoRA` du Workspace réellement utilisable par ComfyUI, il faudrait soit **(a)** une copie physique du fichier vers le dossier `models/loras/` (ou un chemin `extra_model_paths`) de l'installation ComfyUI réelle — nécessiterait de consommer `ApplicationSettings.comfyui_path`, aujourd'hui jamais lu par aucun code —, soit **(b)** une correspondance par nom de fichier (basename) — fragile et contraire à l'exigence explicite de ne jamais substituer silencieusement une LoRA. **Aucune des deux n'est traitée par M059** ; cette primitive est réservée à une future mission dédiée, qui devra elle-même arbitrer la question de fond (AI Studio Toolkit doit-il écrire dans le dossier d'une application tierce ?).

**Conséquence directe sur l'UX (Option A/B/C)** : la valeur réellement sélectionnable aujourd'hui est un **nom serveur ComfyUI**, pas une entité `LoRA` du Workspace — l'Option C (« LoRA active du Workspace ») est donc **techniquement irréalisable sans la primitive manquante ci-dessus**, un fait technique, pas un choix UX. Entre Option A (Settings globale) et Option B (`InferencePage`, par génération) : la valeur étant structurellement une config moteur (identique en nature à `checkpoint_name`), l'Option A hérite d'un mécanisme de dégradation gracieuse déjà éprouvé (`SettingsPage.refresh_checkpoints()` : `setCurrentText()` préserve toujours la valeur affichée même absente de la liste fraîche, `settings_page.py:202-209`), reste insensible au changement de Workspace (comme `checkpoint_name` aujourd'hui) et évite de fragmenter la future refonte multi-engine entre deux philosophies UX. L'Option B resterait cohérente en théorie (une LoRA est intuitivement plus « par génération » qu'un checkpoint), mais imposerait une décision de persistance non résolue (nouveau champ Domain Workspace, ou re-sélection à chaque session) sans gagner la valeur qui la justifierait vraiment (le lien à une LoRA réelle du Character, bloqué par la même primitive manquante). **Recommandation confirmée : Option A**, avec la sélection « LoRA réelle du Character/Workspace » explicitement actée comme besoin futur distinct, bloqué sur la primitive manquante, non sur un simple choix UX.

**Câblage workflow confirmé dans `comfyui_workflows.py`** : `CheckpointLoaderSimple ("4") → [si LoRA] LoraLoader (nouveau nœud "11") → model/clip modifiés → reste du graphe`. Sans LoRA : graphe inchangé, égalité structurelle complète du dict Python (aucun nœud `"11"`). Avec LoRA : nœud `"11"` (`class_type: "LoraLoader"`, `inputs: {model: ["4",0], clip: ["4",1], lora_name, strength_model, strength_clip}`) ; `KSampler ("3").inputs.model` passe de `["4",0]` à `["11",0]` ; les deux `CLIPTextEncode ("6", "7").inputs.clip` passent de `["4",1]` à `["11",1]` ; `vae` (`VAEDecode`/`VAEEncode`) reste `["4",2]` inchangé dans les deux builders — `LoraLoader` ne produit que `MODEL`/`CLIP`, jamais de VAE. Le nœud `"10"` (`LoadImage`, référence `pose_composition` M056) et `_load_image_input()` restent totalement inchangés — les deux mécanismes se superposent sans interaction.

**Gestion des erreurs — jamais de substitution silencieuse** : aucun LoRA détecté → combobox vide, statut explicite, `comfyui_lora_name` reste `""`, comportement inchangé. Serveur injoignable au refresh → `ComfyUIEngineError` capturée, statut explicite, valeur déjà affichée jamais effacée (mirroir exact du comportement checkpoint). LoRA sauvegardée devenue absente du serveur au moment de générer → ComfyUI rejette le workflow (valeur hors de son enum), `submit()` lève `ComfyUIEngineError` → `GenerationManager` relève `GenerationError` → `InferencePage` l'affiche via `QMessageBox.critical` — chemin d'erreur déjà existant, réutilisé tel quel, aucun code d'erreur spécifique au LoRA nécessaire. Changement de Workspace : sans effet, la valeur est Settings-level.

## 3. Objectif

Permettre, pour la première fois, l'application réelle d'un LoRA lors d'une génération ComfyUI — en mirroitant exactement le mécanisme de découverte/sélection déjà validé pour le checkpoint (Mission 025), sans dépendre d'aucun custom node ni d'aucune décision produit non tranchée.

## 4. Contrat fonctionnel — réellement implémenté

- `ComfyUIEngine.list_loras()` : nouvelle méthode, GET `/object_info/LoraLoader`, extraction défensive de la liste de noms (`lora_name`), échec explicite (`ComfyUIEngineError`) sur toute forme de réponse inattendue — jamais de résultat partiel ou deviné. Aucun changement à `list_checkpoints()`/`submit()`/`wait_for_result()`/`download_output()`/`upload_image()`.
- `build_txt2img_workflow()`/`build_img2img_workflow()` (`comfyui_workflows.py`) : nouveaux paramètres optionnels `lora_name: str = ""`/`lora_strength: float = 1.0`. Quand `lora_name` est vide, le graphe retourné reste strictement identique (égalité structurelle complète du dict Python, seed aléatoire neutralisé pour la comparaison) à aujourd'hui. Quand fourni, un nœud `LoraLoader` (id `"11"`) est inséré, recevant `model`/`clip` de `CheckpointLoaderSimple` (`"4"`) ; `KSampler ("3").inputs.model` et les deux `CLIPTextEncode ("6"/"7").inputs.clip` sont rebranchés sur `"11"` ; `vae` (`VAEDecode`/`VAEEncode`) reste `["4",2]`, jamais touché par `LoraLoader` (voir section 2 bis pour le détail nœud par nœud, confirmé dans le fichier réel).
- `ComfyUIEngine.generate_image()` : nouveaux paramètres optionnels `lora_name`/`lora_strength`, forwardés sans interprétation aux deux builders.
- `GenerationManager.__init__` : nouveaux paramètres optionnels `lora_name: str = ""`/`lora_strength: float = 1.0` (mêmes défauts, même position dans la responsabilité que `checkpoint_name`), forwardés à `generate_image()` dans `generate()`.
- `ApplicationSettings` : `comfyui_lora_name: str = ""` (défaut vide, honnête — pas de valeur préexistante à préserver), `comfyui_lora_strength: float = 1.0` (défaut natif ComfyUI). `to_dict()`/`from_dict()` symétriques, compatibles avec un `application_settings.json` antérieur sans ces clés.
- `ApplicationSettingsManager.update()` : étendu pour ces deux champs, mêmes règles d'idempotence (valeur identique → `False`, aucun `save()`, aucun événement) déjà appliquées à `comfyui_checkpoint_name`.
- `SettingsPage` : nouveau `QComboBox` LoRA éditable (`comfyui_lora_name_edit`), bouton dédié « Rafraîchir les LoRA » (mirroir exact de « Rafraîchir les checkpoints », propre statut `lora_discovery_status_label`, propre timeout `LORA_DISCOVERY_TIMEOUT`), + un contrôle de force unique (`QDoubleSpinBox`, plage indicative 0.0–2.0 — non vérifiée contre un serveur réel, ComfyUI rejetterait de toute façon explicitement une valeur hors de sa propre plage acceptée, même mécanisme d'erreur que section 2 bis), défaut `1.0`, appliqué à la fois à `strength_model` et `strength_clip` du nœud natif (qui les distingue réellement — voir section 2 bis, non masqué). Persistance via le même `save_application_settings()` existant.
- `MainWindow` : `GenerationManager(...)` reçoit `lora_name`/`lora_strength` depuis `ApplicationSettings`, même lecture unique au démarrage, même contrat "pas de hot reload" déjà documenté pour ComfyUI/Ollama.

## 5. Hors périmètre (explicitement différé)

- Intégration avec `LoRAManager`/les fichiers LoRA gérés par le Workspace (`LoRA.files`) — un fichier LoRA géré par le Toolkit n'est pas automatiquement visible par le serveur ComfyUI (aucun mécanisme d'upload de LoRA connu côté ComfyUI, contrairement à `upload_image()` pour les images de référence) ; ce candidat sélectionne uniquement parmi les LoRA déjà connus du serveur ComfyUI actif, exactement comme le checkpoint aujourd'hui.
- Sélection du LoRA par génération dans `InferencePage`, ou par `Character` (LoRA d'identité) — reste Settings-level/global, comme le checkpoint. Le besoin « Character Context avancé — LoRA d'identité » (documenté depuis Mission 034) reste entier et distinct.
- Application simultanée de plusieurs LoRA.
- Tout autre moteur (Automatic1111, Forge, Fooocus, futurs moteurs cloud) — le besoin « sélection de LoRA multi-engine » (identifié Mission 022) reste ouvert au-delà de ce candidat, qui ne livre que le mécanisme ComfyUI.
- Second rôle Inference (IP-Adapter/ControlNet/InstantID/PuLID), consommation simultanée de plusieurs références, « Dataset de références → Inference » — aucun lien avec ce candidat, restent entièrement ouverts (voir section 8 de ce document pour le statut détaillé, confirmé inchangé par cet audit).
- **FLUX (checkpoint et LoRA)** — le pipeline actuel (`CheckpointLoaderSimple` + nœuds génériques) ne charge jamais un modèle FLUX correctement (workflow natif FLUX = `UNETLoader`/`DualCLIPLoader`/VAE séparé, jamais présents dans ce dépôt) — limitation **pré-existante depuis Mission 012/013**, non introduite par M059, qui ne touche à aucun mécanisme de chargement de checkpoint. Voir section 13 pour l'audit complet. Un support FLUX réel nécessiterait un nouveau workflow, de nouveaux Settings moteur et potentiellement `LoraLoaderModelOnly` — **explicitement hors périmètre, réservé à une mission/branche moteur distincte**.
- Détection/filtrage automatique de l'architecture d'une LoRA (SD1.5 vs SDXL vs FLUX) — aucune information fiable n'est exposée par `/object_info/LoraLoader` pour cela (voir section 13) ; aucune heuristique par nom de fichier n'est introduite.
- Portabilité des chemins, i18n, Prompt Library/RAG, refonte Settings, Training réel — non concernés par ce candidat.

## 6. Risques

- **Risque de régression fonctionnelle** : faible — mécanisme calqué sur un pattern déjà validé (Mission 025), garantie de compatibilité ascendante déjà démontrée pour des extensions similaires de `generate_image()`/des builders (`reference_image`/Mission 021/023, `denoise`/Mission 024) : comportement strictement inchangé quand le nouveau paramètre n'est pas fourni.
- **Risque de dépendance externe non vérifiable** : faible et structurellement contenu — `LoraLoader` est un nœud natif ComfyUI (pas un custom node), et `list_loras()` suit la même dégradation gracieuse que `list_checkpoints()` : si jamais absent d'une installation non standard, la liste retournée est simplement vide, sans impact tant qu'aucun LoRA n'est configuré.
- **Risque de désaccord sur la portée** : faible — les trois choix d'implémentation mineurs (section 8) suivent tous un précédent direct et documenté (Mission 025), signalés pour confirmation explicite plutôt que décidés silencieusement.
- **Risque de sélection d'une LoRA d'une architecture incompatible avec le checkpoint actif** (ex. LoRA FLUX sélectionnée avec un checkpoint SD1.5/SDXL) : réel, identifié par un second audit complémentaire (section 13) — **jamais silencieux** : la génération échoue explicitement côté serveur (mécanisme déjà établi, aucun changement d'implémentation nécessaire), documenté dans l'UI (hint `SettingsPage`) et dans ce document. Aucune détection/filtrage automatique n'est possible sans information fiable exposée par ComfyUI (confirmé absente) ni heuristique par nom de fichier (explicitement exclue). Ce risque existe uniquement parce que `list_loras()` énumère toutes les LoRA connues du serveur sans distinction d'architecture — comportement identique et déjà accepté pour `list_checkpoints()` depuis Mission 018/025.

## 7. Pourquoi maintenant

Le besoin est documenté depuis Mission 022 et précisé conceptuellement par Mission 047 (distinction sélection/configuration vs chargement/application) — jamais livré pour aucun moteur à ce jour. Le prérequis technique (mécanisme de découverte serveur, contrat "pas de hot reload", pattern UI Settings) est mûr et directement réutilisable depuis Mission 025 : aucune nouvelle réflexion architecturale n'est nécessaire, seulement une extension symétrique d'un mécanisme déjà validé. Contrairement au besoin « second rôle Inference »/« Dataset de références → Inference », ce candidat ne dépend d'aucun custom node ni d'aucun modèle externe non vérifiable dans mon environnement — il est réellement actionnable dès maintenant.

## 8. Décisions — validées par l'architecte le 2026-08-24

1. **Portée Settings-level/globale** (comme le checkpoint), et non une sélection par génération dans `InferencePage` ni par `Character` — validé. L'Option C était techniquement irréalisable sans la primitive manquante (mapping `LoRA.files`↔ComfyUI), et l'Option B n'aurait pas apporté la valeur qui la justifierait sans cette même primitive. La sélection d'une LoRA réellement issue du Workspace/Character reste un besoin futur distinct, non résolu par M059.
2. **Une seule force combinée** (`strength_model` == `strength_clip`, tous deux réglés par la même valeur), plutôt que deux valeurs séparées que `LoraLoader` natif distingue réellement (non masqué) — validé.
3. **Valeur par défaut de la force** : `1.0`, la valeur par défaut native de ComfyUI lui-même — validé.
4. **Périmètre confirmé** : sélection strictement server-side (liste `list_loras()`), aucune intégration `LoRAManager`/`LoRA.files` dans M059 — validé. La primitive manquante identifiée en section 2 bis reste explicitement signalée comme besoin futur (voir "Important pour la roadmap" ci-dessous) pour une mission dédiée ultérieure.

## 9. Autres candidats évalués et écartés pour cette mission

- **Portabilité des chemins internes** (`Workspace.root`, chemins relatifs `Image.file_path`/`LoRA.thumbnail`) : besoin réel documenté depuis Mission 029, mais le périmètre exact (quels champs précisément, `Model.file_path`/`Workflow.file_path`/`LoRA.files` restant légitimement externes) n'a jamais été tranché — nécessite un audit dédié pour scoper la liste exacte des champs concernés avant toute implémentation.
- **Second rôle Inference / consommation simultanée de plusieurs références** (`Reference(path, role)`, Mission 056) : dépend d'un mécanisme moteur réel (IP-Adapter/ControlNet/InstantID/PuLID) nécessitant des custom nodes/modèles dont la disponibilité sur l'installation ComfyUI réelle de l'architecte n'est pas vérifiable dans mon environnement — traité comme un blocage, pas comme acquis, conformément à l'instruction explicite de cet audit.
- **« Dataset de références → Inference »** : reste bloqué sur le point précédent — aucun changement de statut depuis Mission 057/058 (voir confirmation ci-dessous).
- **Model/Workflow → Inference** (faire consommer réellement `Workspace.models`/`.workflows` par la génération, au lieu du champ `ApplicationSettings.comfyui_checkpoint_name` actuel, entièrement déconnecté de `ModelManager`) : gap réel identifié pendant cet audit, symétrique à celui résolu pour LoRA par ce candidat — mais implique une décision produit non triviale (le concept "Model" du Workspace doit-il fusionner avec la notion de "checkpoint" Settings-level, ou rester délibérément distinct comme aujourd'hui ?) non tranchée ici ; candidat probable pour une future mission dédiée.
- **Exploitation de `comfyui_path`** : jamais consommé par aucun code ; aucun besoin utilisateur concret identifié au-delà d'un usage diagnostic/détection potentiel, déjà noté comme réservé pour `ollama_path` également — pas prioritaire.
- **Training réel (moteurs d'exécution OneTrainer/Kohya)** : exclu (multi-engine, périmètre large, aucune décision moteur tranchée).
- **Settings/multi-engine (sélection de moteur généralisée)** : décision d'architecture Engine/Plugin non tranchée (`AI Orchestrator`/`Plugin`/Domain `Engine`/`Job` tous inexistants) — nécessite son propre audit architectural dédié.
- **i18n** : périmètre jamais scopé, large.
- **Prompt Library structurée / RAG local** : modèle de données non défini, décision produit ouverte (tags structurés/personnalisés, articulation avec l'identité canonique) — nécessite son propre audit dédié.

**Confirmation explicite demandée par cet audit — statut « Dataset de références → Inference »** : reste **non résolu**, inchangé par Mission 057 et Mission 058 (toutes deux hors périmètre Inference). La primitive typée `Reference(path, role)` existe depuis Mission 056, mais l'intégration pratique reste bloquée sur un premier mécanisme moteur réel pour un second rôle, lui-même bloqué sur une dépendance externe non vérifiable dans mon environnement — voir `docs/PROJECT_CONTEXT.md`, section « Besoins futurs identifiés ». **Non affecté par M059** — nettoyage/extension ComfyUI strictement limités à la LoRA server-side, aucun changement au mécanisme de référence.

**Besoin futur explicitement conservé pour la roadmap (révélé par l'audit complémentaire de cette mission)** : permettre ultérieurement d'associer de manière fiable une entité `LoRA` du Workspace (`LoRA.files`) à une LoRA réellement exploitable par un moteur tel que ComfyUI. Cette future mission devra trancher explicitement la stratégie (installation/copie physique vers le dossier du moteur, enregistrement/upload auprès du moteur si un mécanisme existe, ou tout autre mécanisme fiable) — **jamais un mapping ambigu par simple basename**. Non traité par M059, qui ne consomme que les noms server-side découverts par `list_loras()`.

## 10. Fichiers réellement modifiés

Production (7, exactement le périmètre du contrat) :
- `src/engines/comfyui_engine.py` — `list_loras()` (nouvelle méthode), `generate_image()` étendu.
- `src/engines/workflows/comfyui_workflows.py` — `_apply_lora()` (nouvelle fonction interne), les deux builders étendus.
- `src/managers/generation_manager.py` — `__init__` étendu, forwarding dans `generate()`.
- `src/domain/application_settings.py` — `comfyui_lora_name`/`comfyui_lora_strength` additifs.
- `src/managers/application_settings_manager.py` — `update()` étendu, même contrat d'idempotence.
- `src/ui/pages/settings_page.py` — combobox LoRA, spinbox de force, bouton/label de découverte dédiés.
- `src/ui/main_window.py` — `GenerationManager(...)` reçoit les deux nouveaux paramètres.

Tests (6 fichiers existants étendus, aucun nouveau fichier de test) :
- `tests/integration/test_comfyui_workflows.py` — +2 classes (`NoLoraProducesTheExactPreMission059WorkflowTest`, `LoraInsertedWhenConfiguredTest`).
- `tests/integration/test_comfyui_engine.py` — +2 classes (`ComfyUIEngineListLorasTest`, `ComfyUIEngineGenerateImageLoraTest`).
- `tests/integration/test_generation_manager.py` — +1 classe (`GenerationManagerLoraTest`), 5 assertions `assert_called_once_with` existantes étendues, 2 fonctions `fake_generate_image` étendues.
- `tests/integration/test_application_settings_roundtrip.py` — +1 nouveau test (fichier légataire sans champs LoRA), assertions/littéraux existants étendus dans 5 tests.
- `tests/integration/test_settings_page.py` — +1 classe (`SettingsPageLoraDiscoveryTest`, 13 tests).
- `tests/integration/test_main_window_comfyui_settings.py` — 2 tests existants étendus.

Aucun fichier hors de ce périmètre modifié. `git status --short`/`git diff --stat` confirmés (section 12).

## 11. Vérification manuelle réelle — smoke test **MOCKÉ, PAS UN SERVEUR RÉEL**

**Aucun serveur ComfyUI n'était joignable dans cet environnement** — vérifié explicitement avant le smoke test : `curl -m 3 http://127.0.0.1:8188/system_stats` → connexion refusée. Conformément à l'instruction de ne jamais présenter un test mocké comme un test réel, ce smoke test est un script scratchpad (jamais committé) qui construit les **objets réels** (`SettingsPage`, `ApplicationSettingsManager`, `ComfyUIEngine`, `GenerationManager`, exactement le câblage de `MainWindow`) mais **patche `urllib.request.urlopen`** pour simuler les réponses serveur — aucun octet n'a transité sur le réseau, aucun modèle LoRA réel n'a été exercé.

19/19 vérifications PASS :
1. `SettingsPage.refresh_loras_button` découvre bien 2 LoRA depuis une réponse `/object_info/LoraLoader` simulée.
2. Sélection + force (0.8) + sauvegarde réelle persistés dans `ApplicationSettingsManager`.
3. Une valeur déjà configurée, absente d'une découverte fraîche, n'est **jamais** remplacée silencieusement.
4. `GenerationManager` construit à la manière de `MainWindow` reprend bien le LoRA/la force sauvegardés.
5. Génération txt2img : nœud `LoraLoader` unique, `lora_name`/`strength_model`/`strength_clip` corrects, `KSampler.model`/les deux `CLIPTextEncode.clip` rebranchés sur `"11"`, `vae` intact sur `"4"`.
6. Génération img2img avec `Reference(..., pose_composition)` **et** la même LoRA simultanément : `LoraLoader` présent, mécanisme de référence (`LoadImage`/`VAEEncode`) intact et non perturbé.
7. Aucune LoRA configurée : aucun nœud `"11"`, `model`/`clip` toujours directement sur `"4"`.
8. Une LoRA configurée rejetée par le serveur (réponse sans `prompt_id`) lève `GenerationError` — jamais de substitution silencieuse.

**Ce que ce smoke test prouve** : le câblage réel bout-en-bout (Settings → Manager → Engine → workflow) fonctionne comme spécifié, avec les vrais objets Qt/Manager. **Ce qu'il ne prouve pas** : que `LoraLoader` se comporte réellement ainsi sur un vrai serveur ComfyUI, que `strength_model`/`strength_clip` acceptent bien la plage 0.0–2.0, ou qu'une LoRA réelle produit un résultat visuellement altéré — ces points nécessitent un serveur ComfyUI réel avec au moins une LoRA installée, non disponible dans cet environnement, et restent à vérifier par l'architecte sur son installation réelle avant ou après la publication.

## 12. Vérifications finales

- Suite ciblée : `test_comfyui_workflows.py` (36/36), `test_comfyui_engine.py` (78/78), `test_generation_manager.py` (37/37), `test_application_settings_roundtrip.py` (16/16), `test_settings_page.py` (47/47), `test_main_window_comfyui_settings.py` + `test_settings_roundtrip.py` (11/11) — tous verts.
- Non-régression : `test_inference_page.py` + `test_generation_worker.py` (88/88) — verts.
- Suite complète : **1010/1010 tests verts** (967 précédents + 43 nets nouveaux, décompte exact confirmé).
- `git diff --check` : propre (seuls avertissements CRLF/LF habituels sous Windows, aucune erreur de contenu).
- `git status --short`/`git diff --stat` : périmètre exactement conforme au contrat (7 fichiers de production, 6 fichiers de test existants étendus, plus un ajout ponctuel — le hint UI de la section 13 — dans un fichier déjà du périmètre), aucun résidu scratch dans le dépôt.

## 13. Audit complémentaire — compatibilité architecture LoRA (SD1.5/SDXL/FLUX)

Réalisé à la demande explicite de l'architecte, **avant** le smoke test réel et avant tout commit — l'architecte a signalé que son dossier `models/loras` ComfyUI contient des LoRA de plusieurs architectures (SDXL, FLUX), non interchangeables.

### 13.1 Périmètre moteur réellement supporté aujourd'hui

`build_txt2img_workflow()`/`build_img2img_workflow()` (`comfyui_workflows.py`) construisent exclusivement un graphe `CheckpointLoaderSimple → CLIPTextEncode(×2)/KSampler/VAEDecode`, sans aucun nœud spécifique à une famille de modèle — confirmé par lecture directe du fichier, inchangé par M059. `ApplicationSettings.comfyui_checkpoint_name`/`SettingsPage.comfyui_checkpoint_name_edit` sont un simple champ texte/combobox sans validation de famille.

Ce graphe est le graphe **générique "checkpoint unifié"** de ComfyUI : `CheckpointLoaderSimple` charge un unique fichier bundlant UNet + CLIP + VAE, et fonctionne aussi bien pour SD1.5 que pour SDXL — ComfyUI gère en interne la différence d'architecture du checkpoint chargé. Ce n'est pas une déduction depuis l'extension `.safetensors` : c'est confirmé indirectement par un fait déjà présent dans l'historique du dépôt — le smoke test réel de Mission 012 (`docs/missions/MISSION_012.md:86`) a détecté via ce même mécanisme (`GET /object_info/CheckpointLoaderSimple`) des checkpoints **SDXL réels** (`Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors`, `juggernautXL_v8Rundiffusion.safetensors`) aux côtés du SD1.5 par défaut (`v1-5-pruned-emaonly-fp16.safetensors`) — le pipeline a donc déjà été exposé, avec succès, à des checkpoints SD1.5 et SDXL.

**FLUX n'a en revanche jamais été mentionné, testé, ni détecté nulle part dans l'historique du dépôt.** Le workflow officiel/natif FLUX de ComfyUI charge le modèle de diffusion, les encodeurs texte et le VAE **séparément** (`UNETLoader`/« Load Diffusion Model », `DualCLIPLoader`, VAE dédié) — trois catégories de fichiers distinctes de la catégorie « checkpoints » que `CheckpointLoaderSimple` interroge. Un fichier FLUX « tout-en-un » repackagé par la communauté pourrait en théorie apparaître dans la liste de `list_checkpoints()`/`CheckpointLoaderSimple` s'il est placé dans le dossier `checkpoints`, mais ce n'est ni le workflow officiel, ni quelque chose de vérifiable dans mon environnement, ni quelque chose que ce graphe a jamais été conçu ou testé pour gérer correctement (résolution latente, double encodeur texte T5, etc., tous absents de ce graphe).

**Conclusion, sans supposition sur l'extension de fichier** : le pipeline actuel est un vertical slice **SD1.5/SDXL**, confirmé par preuve historique réelle (Mission 012) pour ces deux familles, jamais FLUX — limitation **pré-existante depuis Mission 012/013**, entièrement indépendante de M059, qui ne modifie ni ne touche `CheckpointLoaderSimple` ni le chargement de checkpoint.

### 13.2 Mécanisme LoRA par architecture

Pour SD1.5/SDXL — le seul périmètre réellement supporté aujourd'hui — `LoraLoader` (MODEL + CLIP, sorties MODEL + CLIP) est effectivement le nœud natif standard et cohérent avec le graphe existant : c'est exactement ce que M059 a implémenté (section 4/8 de ce document, `_apply_lora()`).

Pour FLUX (information générale sur les workflows natifs ComfyUI, **non vérifiée contre un serveur réel** dans cet environnement) : les exemples LoRA FLUX officiels utilisent le plus souvent `LoraLoaderModelOnly` (LoRA appliquée au seul modèle de diffusion, sans branche CLIP — cohérent avec la séparation `UNETLoader`/`DualCLIPLoader` de FLUX), un nœud et un graphe entièrement différents de ceux que M059 — ou tout autre code de ce dépôt — construit.

**Conclusion** : le `LoraLoader` générique de M059 est approprié **uniquement** pour le graphe SD1.5/SDXL existant. Il ne serait de toute façon jamais exercé pour FLUX dans ce dépôt, puisqu'aucun graphe FLUX n'existe — la question ne se pose donc pas au niveau du nœud LoRA en pratique, elle se pose en amont, au niveau du graphe de génération lui-même (hors périmètre M059, voir 13.1).

### 13.3 Ce que `list_loras()`/`/object_info/LoraLoader` permet réellement de savoir

Confirmé par lecture du code réel de `list_loras()` (`comfyui_engine.py`) et du contrat `/object_info/<node_class>` déjà exploité pour les checkpoints : cet endpoint retourne uniquement `node_info["input"]["required"]["lora_name"][0]`, une **liste plate de noms de fichiers (`list[str]`)** — aucune métadonnée d'architecture, de base model, ni quoi que ce soit d'autre associé à chaque entrée.

- **Peut-on distinguer SDXL de FLUX automatiquement depuis cette API ?** Non — confirmé, aucune métadonnée n'est exposée par ce endpoint pour aucune entrée de la liste.
- **Existe-t-il une autre information ComfyUI exploitable sans lire/interpréter le fichier `.safetensors` ?** Non identifiée. Certains outils d'entraînement (kohya_ss, OneTrainer) embarquent des métadonnées d'architecture (`ss_base_model_version`, `modelspec.architecture`, ...) directement dans l'en-tête du fichier `.safetensors` — mais cela exigerait de lire/interpréter le fichier lui-même, exactement ce que l'architecte a explicitement exclu, et rien dans le contrat HTTP `/object_info` de ComfyUI ne réexpose cette métadonnée-là aujourd'hui, à ma connaissance non vérifiée contre un serveur réel.
- **Le serveur valide-t-il la compatibilité uniquement à l'exécution ?** Oui, par déduction du contrat déjà établi dans ce dépôt : `list_checkpoints()`/`list_loras()` n'exposent qu'une énumération de noms valides pour leur propre champ, sans validation croisée entre deux champs différents. La validation `/prompt` de ComfyUI (déjà exploitée par `submit()`) vérifie qu'une valeur appartient bien à l'enum déclaré par le nœud — jamais une compatibilité tensorielle entre deux modèles chargés par deux nœuds différents, qui ne peut se révéler qu'à l'exécution réelle du graphe (chargement/fusion des poids). **Point non vérifié contre un serveur réel dans cet environnement, signalé honnêtement** : selon la version de ComfyUI, une incompatibilité réelle pourrait se traduire soit par une erreur d'exécution rapportée dans l'entrée d'historique (`status.status_str == "error"`), soit — property déjà pré-existante de ce dépôt, non spécifique à M059 — par un blocage silencieux de `wait_for_result()` jusqu'à expiration du timeout (120 s par défaut), `wait_for_result()` ne lisant aujourd'hui que le champ `outputs`, jamais `status`. Cette dernière propriété existe déjà pour toute erreur d'exécution ComfyUI (checkpoint manquant, image de référence invalide, etc.) et n'est ni introduite ni aggravée par M059 — signalée ici pour complétude, hors périmètre de correction pour cette mission.

### 13.4 Politique retenue pour M059

**Option A retenue** — M059 reste tel qu'implémenté : la combobox continue d'afficher toutes les LoRA connues du serveur (SD1.5, SDXL, FLUX confondues, sans distinction possible), le serveur ComfyUI reste seul juge final de la compatibilité, une incompatibilité produit un échec explicite (jamais une substitution silencieuse — déjà démontré en test et en smoke test mocké, section 11 point 8).

- **Option B (filtrage automatique) rejetée** : aucune information fiable d'architecture n'est exposée par ComfyUI sans lire/interpréter arbitrairement le fichier `.safetensors` — explicitement exclu par l'architecte, et non implémenté.
- **Option C (reporter M059) rejetée** : le pipeline actuel ne « mélange » pas plusieurs familles de checkpoints sans moyen fiable de charger leur LoRA — il ne supporte qu'une seule famille de graphe (SD1.5/SDXL, `CheckpointLoaderSimple` générique), déjà exercée avec succès pour les deux (Mission 012). Le risque réel n'est pas un mélange interne incohérent, mais un **choix utilisateur** d'une LoRA d'une architecture que ce pipeline n'a jamais prétendu supporter (FLUX) — un risque de sélection, pas un défaut du vertical slice lui-même, et un risque déjà accepté implicitement pour les checkpoints depuis Mission 018/025 (`list_checkpoints()` ne filtre pas non plus par architecture). Reporter M059 pénaliserait le cas d'usage réellement servi (SD1.5/SDXL, majoritaire chez la plupart des utilisateurs ComfyUI) pour un risque déjà géré explicitement (échec serveur, jamais silencieux) et déjà documenté.

**Aucune décision produit ou architecturale substantielle ne reste ouverte** — Option A est un choix de documentation/transparence, pas une décision d'architecture bloquante, cohérente avec le précédent déjà établi pour le checkpoint.

**Correction apportée** : `src/ui/pages/settings_page.py`, le hint UI existant (`application_hint`) précise désormais explicitement : « Le LoRA choisi doit être compatible avec le checkpoint sélectionné (ex. SD1.5/SDXL) — ComfyUI reste seul juge de cette compatibilité et rejette explicitement toute combinaison incompatible. » Un seul label modifié, aucun test cassé (aucun test n'affirme le texte exact de ce hint — vérifié).

### 13.5 Instructions précises pour le smoke test réel

Pour un smoke test M059 valide sur l'installation réelle de l'architecte :

- **Checkpoint** : un checkpoint SD1.5 **ou** SDXL (single-file, catégorie « checkpoints » de ComfyUI) — les deux familles sont couvertes par le pipeline actuel.
- **LoRA** : une LoRA **confirmée entraînée pour/compatible avec cette même famille** (SD1.5 avec SD1.5, SDXL avec SDXL — les deux ne sont pas interchangeables entre elles non plus, pas seulement vis-à-vis de FLUX).
- **Ne pas sélectionner de LoRA FLUX** pour ce smoke test — le workflow M059 n'est, et ne prétend pas être, conçu pour FLUX (voir 13.1/13.2). Une telle combinaison ne validerait rien d'utile pour M059 et échouerait probablement côté serveur (explicitement, jamais silencieusement) ou à un timeout, selon la version de ComfyUI (voir 13.3).

## 14. Smoke test réel — PASS (exécuté par l'architecte, installation ComfyUI réelle)

Remplace/complète le smoke test mocké de la section 11 : celui-ci reste une preuve automatisée utile (câblage bout-en-bout avec des objets réels, réseau simulé), mais la présente section est la **validation sur un vrai serveur ComfyUI**, la seule à prouver le comportement réel de `LoraLoader`/`list_loras()` en dehors de toute simulation.

**1. Découverte réelle des LoRA — PASS.** Le bouton « Rafraîchir les LoRA » interroge le serveur ComfyUI réel de l'architecte ; 5 LoRA détectés et affichés dans le sélecteur. Confirme `ComfyUIEngine.list_loras()`/`GET /object_info/LoraLoader` fonctionnels contre un vrai serveur. La bibliothèque contient des LoRA de familles différentes (SDXL, FLUX) — ce test ne valide donc pas tous les fichiers détectés indifféremment (voir section 13, non résolu et non prétendu résolu par ce test).

**2. Génération réelle txt2img avec LoRA — PASS.** Checkpoint compatible avec le pipeline actuel + LoRA d'identité sélectionné dans Settings + prompt simple → génération aboutie, image produite par le serveur réel. La fidélité d'identité du résultat est discutable, mais **explicitement hors critère d'évaluation de M059** — la qualité d'un LoRA entraîné est indépendante du bon fonctionnement du pipeline de chargement/application ; un réentraînement futur (Kohya/OneTrainer, non encore intégrés) est prévu séparément. Le critère pertinent ici, validé, est : le pipeline avec LoRA sélectionné est accepté par ComfyUI et produit effectivement une image.

**3. Génération réelle avec `Reference(pose_composition)` + LoRA — PASS.** Une image de référence sélectionnée dans `InferencePage` (affichage confirmé : `nom_du_fichier.png — Pose / composition`, force 0.75) combinée au LoRA sélectionné → génération terminée sans erreur ComfyUI, image produite, reprenant perceptiblement des éléments structurels de la référence (sujet, orientation, composition, environnement) sans conservation stricte de l'identité/tenue/pose exacte — cohérent avec le mécanisme img2img/`denoise=0.75` existant (Mission 023/024), qui n'a jamais promis ControlNet/OpenPose/IP-Adapter/InstantID. **Validation clé** : coexistence réelle du mécanisme LoRA de M059 avec la primitive `Reference(path, pose_composition)` de Mission 056 dans un seul appel `generate()`, sur un serveur réel — le smoke test mocké (section 11, point 5) l'avait déjà prouvé en simulation ; ceci le confirme en conditions réelles.

**Ce qui est validé par ce smoke test réel** : découverte des LoRA depuis un vrai ComfyUI ; affichage dans AI Studio Toolkit ; sélection d'un LoRA ; génération txt2img réelle avec LoRA ; génération img2img réelle avec LoRA + `Reference(pose_composition)` ; absence d'erreur ComfyUI dans ces deux scénarios ; coexistence réelle des mécanismes M056/M059.

**Ce qui n'est PAS validé par ce smoke test, et ne doit pas être présenté comme tel** : FLUX ; l'ensemble des fichiers `.safetensors` découverts (5 LoRA détectés, 1 seul réellement exercé) ; une détection automatique d'architecture ; une compatibilité automatique checkpoint↔LoRA (le serveur reste seul juge, conformément à la section 13) ; plusieurs LoRA simultanés ; la qualité d'identité du LoRA utilisé. La distinction architecturale de la section 13 reste entièrement valide : pipeline testé = checkpoint SD1.5/SDXL existant + `LoraLoader` ; FLUX reste un futur pipeline moteur distinct.

**Verdict** : smoke test fonctionnel M059 **PASS** pour le périmètre réellement testé et réellement revendiqué par cette mission.

## 15. Régression UX détectée et corrigée — taille excessive de la fenêtre principale au lancement

Signalée par l'architecte pendant le smoke test réel : fenêtre principale anormalement grande à l'ouverture, dépassant visiblement les dimensions de l'écran, particulièrement visible sur le Dashboard (page affichée par défaut au lancement). Redimensionnement manuel possible ensuite, mais la taille initiale n'est pas acceptable.

### 15.1 Audit — reproduction et mesure avec des widgets Qt réels

Instructions suivies à la lettre : ne pas modifier `MainWindow`/sa taille au hasard, établir la cause exacte par la mesure avant toute décision.

**Mesure n°1 — état avant correction, `MainWindow` réelle construite** (`w = MainWindow()`, avant tout `.show()`) :
```
window.size()               = (1700, 950)   # exactement resize(1700, 950), appel explicite préexistant
window.minimumSizeHint()    = (2225, 769)   # > à la largeur de l'écran de test (1920)
window.sizeHint()           = (2256, 1330)
stack.sizeHint()            = (2000, 1261)
stack.minimumSizeHint()     = (2000, 700)
primaryScreen.availableGeometry() = (0, 0, 1920, 1040)   # écran de l'environnement de test
```
`SettingsPage` isolée : `sizeHint() = (2000, 700)` — la page la plus large de loin (les 10 autres pages vont de 195 à 467 px de large). `QStackedWidget` agrège le **maximum** des `sizeHint()`/`minimumSizeHint()` de **toutes** ses pages, visible ou non (propriété Qt documentée, pas une supposition) — c'est ce mécanisme qui propage la largeur de `SettingsPage`, jamais affichée en premier, jusqu'à `MainWindow.minimumSizeHint()`, expliquant pourquoi l'anomalie est visible dès le Dashboard.

**Mesure n°2 — isolement de la cause exacte**, comparaison contrôlée entre la version de `settings_page.py` **committée** (`git show HEAD:...`, donc strictement antérieure à toute modification de cette mission) et la version **actuelle** (avant correction) :
```
AVANT M059 (HEAD)                  : SettingsPage.sizeHint() = (996, 596)
APRÈS M059, avant correction du 15.2 : SettingsPage.sizeHint() = (2004, 704)
```
Cause isolée avec certitude : le label `application_hint` (`QLabel`, jamais en retour à la ligne — `setWordWrap()` n'était appelé nulle part dans ce fichier avant la correction ci-dessous) voit son texte allongé par la correction apportée en section 13.4 de cette même mission (ajout d'une phrase sur la compatibilité LoRA↔checkpoint). Mesure isolée du label seul :
```
QLabel(ancien texte, hint pré-M059)  .sizeHint() = (974, 16)
QLabel(nouveau texte, hint section 13.4) .sizeHint() = (1982, 16)
```
Le quasi-doublement de la largeur du label (974 → 1982) explique intégralement l'écart observé sur `SettingsPage`/`stack`/`MainWindow` ci-dessus. Les nouveaux widgets LoRA eux-mêmes (`QComboBox`, `QDoubleSpinBox`, bouton, label de statut) n'ajoutent que des lignes de formulaire supplémentaires (hauteur, pas largeur significative) — confirmé par la mesure, pas supposé.

### 15.2 Verdict factuel

**Régression réellement introduite par cette mission — confirmée, pas préexistante.** Précisément : non par les nouveaux contrôles LoRA de `SettingsPage` eux-mêmes, mais par l'allongement du label `application_hint` effectué pendant l'audit de compatibilité architecture (section 13.4) de cette même mission, combiné à l'absence préexistante de `setWordWrap()` sur ce label (un défaut mineur déjà présent avant M059 — 974 px de large sur un label pré-M059 — mais resté sous la plupart des largeurs d'écran réelles, donc jamais suffisant pour déclencher le problème avant que cette mission ne double sa longueur).

L'appel `self.resize(1700, 950)` (`main_window.py:185`) est lui **authentiquement préexistant** (commit racine du fichier, 2026-08-08, très antérieur à Mission 059) et **n'est pas la cause** du dépassement — il fixe une taille explicite, mais c'est la largeur minimale imposée par le layout (`minimumSizeHint`, gouvernée par `SettingsPage` via `QStackedWidget`) qui la dépasse une fois la fenêtre réellement affichée à l'écran. Ce `resize()` fixe et non adaptatif à l'écran reste, en toute rigueur, une amélioration UX future possible (fenêtre non redimensionnée dynamiquement selon `screen().availableGeometry()`) — mais **non responsable de la régression constatée** et **non absorbé dans M059** : voir note ci-dessous pour `PROJECT_CONTEXT.md`.

### 15.3 Correction appliquée — minimale, ciblée sur la cause réelle

`src/ui/pages/settings_page.py` : `application_hint.setWordWrap(True)` — un seul appel ajouté, aucune autre ligne touchée, `MainWindow`/`resize()` non modifiés.

**Mesure après correction** :
```
window.minimumSizeHint()    = (865, 769)    # < écran de test (1920) — conforme
stack.sizeHint()            = (640, 1261)
stack.minimumSizeHint()     = (640, 700)
SettingsPage.sizeHint()     = (640, 748)
SettingsPage.minimumSizeHint() = (640, 700)
```
`MainWindow.minimumSizeHint()` passe de `(2225, 769)` à `(865, 769)`, largement sous la résolution de l'écran de test (1920×1040) et sous les résolutions courantes.

**Non-régression ajoutée** : `SettingsPageSizeHintRegressionTest` (`test_settings_page.py`) — verrouille `SettingsPage.sizeHint().width() < 900` et `.minimumSizeHint().width() < 900` (marge confortable au-dessus des 996 px pré-M059, largement sous toute résolution d'écran courante), pour qu'une régression future de cette nature échoue immédiatement en CI plutôt qu'au lancement réel.

### 15.4 Note pour `PROJECT_CONTEXT.md` (non traitée par M059)

Le `self.resize(1700, 950)` fixe, non adapté à la taille d'écran disponible, reste une dette UX distincte et préexistante, **non introduite ni corrigée par M059** — la fenêtre devrait idéalement démarrer avec une taille adaptée à `screen().availableGeometry()` tout en restant librement redimensionnable. Signalé pour un futur candidat de mission, non absorbé ici pour respecter le périmètre strict validé.

## 16. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `c96b984606bbac83d6276d7dca54b9efe4307c53` (`feat: add ComfyUI LoRA selection for generation`), 14 fichiers (7 production, 6 fichiers de test existants étendus, ce document dans son état pré-clôture) — périmètre exactement conforme au contrat (section 10), `docs/PROJECT_CONTEXT.md`/`CHANGELOG.md` délibérément exclus (convention du projet), régularisés séparément après publication.
- **Push** : `0880cf0..c96b984 main -> main`. Vérifié après coup : `HEAD == origin/main`, divergence `0 0`, working tree propre.
- **Tag** : `v0.2-mission059` (annoté, message `Mission 059 - ComfyUI LoRA Selection for Generation`), ciblant exactement `c96b984606bbac83d6276d7dca54b9efe4307c53` — peeled commit vérifié identique local (`git rev-list -n1`) et distant (`git ls-remote --tags origin v0.2-mission059 "v0.2-mission059^{}"`), tag object `50c7dcf4a1cfb1228353ff77495b9b405eaed454`.
- **GitHub Release `v0.2-mission059`** : Release Notes rédigées en anglais par Claude (portée, coexistence M056, SD1.5/SDXL uniquement, FLUX hors périmètre, absence de mapping `LoRA.files`, 44 tests nets nouveaux, 1011/1011, smoke test mocké PASS, smoke test réel PASS, correction de la régression de taille de fenêtre) — **publiée par l'architecte**.
- **Régularisation documentaire post-Release** : `docs/PROJECT_CONTEXT.md` (état consolidé, dette UX `resize(1700, 950)` réintégrée, besoin futur "mapping LoRA Workspace↔moteur" enregistré, statut "Dataset de références → Inference" reconfirmé inchangé) et `CHANGELOG.md` (entrée `v0.2-mission059`) mis à jour et committés séparément, conformément à la convention établie (Missions 054-058).

## État d'avancement

- Audit du dépôt (candidats Mission 059) : **réalisé**.
- Choix de mission : **validé par l'architecte** (2026-08-24).
- Mini-audit complémentaire (mapping LoRA↔ComfyUI, UX, force, workflow) : **réalisé, contrat corrigé, validé par l'architecte** (2026-08-24).
- Audit complémentaire n°2 (compatibilité architecture LoRA SD1.5/SDXL/FLUX) : **réalisé** (section 13), Option A retenue, hint UI corrigé.
- Spécification (ce document) : **rédigée**, conforme à l'implémentation réalisée.
- Implémentation : **réalisée**, conforme au contrat.
- Tests automatisés : **exécutés, verts** — **1011/1011** (44 nets nouveaux : 43 fonctionnels + 1 non-régression taille de fenêtre).
- `git diff --check` : **propre**.
- Vérification manuelle mockée (smoke test) : **réalisée, PASS** (section 11).
- **Smoke test réel (installation ComfyUI de l'architecte) : réalisé, PASS** (section 14).
- **Régression UX (taille de fenêtre au lancement) : détectée, cause établie avec certitude par la mesure, corrigée, verrouillée par un test** (section 15).
- **Validation technique finale : accordée par l'architecte** (2026-08-24).
- **Clôture Git (commit/tag/Release) : entièrement effectuée** — voir section 16.
- **Mission 059 : ENTIÈREMENT CLOSE.**
