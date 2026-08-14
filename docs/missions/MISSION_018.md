# Mission 018 — ComfyUI Application Settings

Source : audit read-only préalable (état Git, code réel, tests réels — Mission 018 Phase 1), spécification validée par l'architecte (avec un ajustement architectural avant implémentation, voir "Décisions"), implémentation réalisée et vérifiée par exécution réelle de la suite de tests complète. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur dans ce document tant que la clôture Git n'a pas eu lieu.

## Contexte

Depuis Mission 013, `main_window.py` construit `ComfyUIEngine`/`GenerationManager` à partir de deux constantes codées en dur, explicitement documentées dans le code comme spécifiques à la machine de développement :
```python
COMFYUI_BASE_URL = "http://127.0.0.1:8000"
COMFYUI_CHECKPOINT_NAME = "v1-5-pruned-emaonly-fp16.safetensors"
```
`ApplicationSettings` (Mission 010) possède déjà un champ `comfyui_path`, mais celui-ci désigne le chemin d'installation local de ComfyUI — jamais consommé par aucun code — et ne peut pas servir de substitut à une URL de serveur ou à un nom de checkpoint.

## Problème

Confirmé par audit Mission 018 Phase 1 (lecture seule) : l'application ne peut se connecter à un serveur ComfyUI que sur la machine de développement exacte où ces constantes ont été validées empiriquement (Mission 012). Aucune configuration utilisateur n'est possible sans éditer le code source. `ApplicationSettings.comfyui_url` est un besoin identifié depuis l'audit Mission 013, jamais traité depuis.

## Objectif

Rendre configurables et persistants, via le mécanisme `ApplicationSettings` déjà existant :
- l'URL du serveur ComfyUI (`comfyui_url`) ;
- le nom du checkpoint ComfyUI utilisé par défaut (`comfyui_checkpoint_name`).

Sans introduire de nouveau Manager, Service, ni système de reconfiguration à chaud.

## Périmètre

**In scope**
- Deux nouveaux champs Domain sur `ApplicationSettings` : `comfyui_url`, `comfyui_checkpoint_name`.
- Extension de `ApplicationSettingsManager.update()` pour ces deux champs (même mécanisme que `python_path`/`comfyui_path`/`onetrainer_path`).
- Deux nouveaux champs dans la section Application de `SettingsPage`.
- `MainWindow` lit ces deux valeurs directement depuis `ApplicationSettingsManager`, qui devient l'unique source (les constantes codées en dur sont supprimées, pas remplacées par un repli).
- Compatibilité ascendante avec un `application_settings.json` existant ne contenant pas ces deux clés.

**Out of scope** (voir section dédiée en fin de document)

## Décisions

- **Ajustement architectural décidé avant implémentation** (validé par l'architecte, remplace la première version de cette section) : `ApplicationSettings` devient la **source de vérité unique** pour `comfyui_url`/`comfyui_checkpoint_name` — pas de second niveau de configuration ni de repli dans `MainWindow`. Une première approche (défauts Domain à `""` + constantes de repli dans `main_window.py`) a été explicitement écartée : elle aurait créé deux niveaux de configuration et fait apparaître des champs vides dans `SettingsPage` alors que l'application utilise réellement des valeurs implicites ailleurs — contraire à l'objectif d'une source de vérité unique.
- **`comfyui_path` non détourné** : reste le chemin d'installation local, conceptuellement distinct de `comfyui_url` (adresse serveur) et `comfyui_checkpoint_name` (nom de checkpoint) — les trois champs coexistent sans se substituer l'un à l'autre.
- **Défauts Domain = valeurs réellement utilisées, pas `""`** : `comfyui_url`/`comfyui_checkpoint_name` prennent directement comme valeur par défaut du dataclass les valeurs actuellement codées en dur dans `main_window.py`. C'est une exception assumée au principe "`""` = non configuré" appliqué à tous les autres champs `ApplicationSettings`/`Settings` (`python_path`, `onetrainer_path`, `theme`, `language`) — justifiée ici parce que ces deux champs, contrairement aux autres, ont déjà un comportement fonctionnel réel et actif aujourd'hui (l'application se connecte déjà à un ComfyUI avec ces valeurs précises), qu'aucune régression de comportement ne doit silencieusement introduire.
- **Aucun repli dans `MainWindow`** : les deux constantes `COMFYUI_BASE_URL`/`COMFYUI_CHECKPOINT_NAME` sont supprimées de `main_window.py`, pas renommées ni conservées comme filet de sécurité. `MainWindow` lit directement `application_settings_manager.settings.comfyui_url`/`.comfyui_checkpoint_name` et les transmet telles quelles — une seule résolution possible, entièrement dans `ApplicationSettings`.
- **`ComfyUIEngine`/`GenerationManager` non modifiés** : ils acceptent déjà `base_url`/`checkpoint_name` en paramètres — seule la source de ces valeurs change dans `main_window.py`.
- **Pas de reconstruction à chaud** : un changement sauvegardé dans `SettingsPage` ne reconstruit pas `ComfyUIEngine`/`GenerationManager` pendant la session en cours — il ne prend effet qu'au prochain démarrage. Aucun signal, aucun hot reload, aucun lifecycle Engine introduit. Rappel textuel ajouté à l'indication déjà existante de la section Application de `SettingsPage` (`application_hint`), en français, cohérent avec le reste de l'interface — pas une seconde étiquette séparée.
- **Aucun nouveau Manager/Service/abstraction** : le mécanisme `ApplicationSettingsManager.update()` déjà existant est étendu, pas remplacé.

## Architecture retenue

```
SettingsPage (comfyui_url_edit, comfyui_checkpoint_name_edit)
  → ApplicationSettingsManager.update(comfyui_url=..., comfyui_checkpoint_name=...)
  → ApplicationSettingsStorage.save() (atomique, déjà existant)
  → application_settings.updated (déjà existant)

MainWindow.__init__ (composition root, lu une seule fois au démarrage) :
  ComfyUIEngine(base_url=application_settings_manager.settings.comfyui_url)
  GenerationManager(engine, checkpoint_name=application_settings_manager.settings.comfyui_checkpoint_name)
```

`ApplicationSettingsManager` est déjà construit avant `ComfyUIEngine`/`GenerationManager` dans `MainWindow.__init__` — aucun réordonnancement nécessaire. Aucun fallback, aucune résolution supplémentaire : la valeur lue dans `ApplicationSettings` est transmise telle quelle.

## Valeurs par défaut

Portées directement par le Domain (`src/domain/application_settings.py`), pas par `MainWindow` :
```python
comfyui_url: str = "http://127.0.0.1:8000"
comfyui_checkpoint_name: str = "v1-5-pruned-emaonly-fp16.safetensors"
```
Valeurs identiques à celles actuellement codées en dur dans `main_window.py` avant Mission 018 — comportement ComfyUI strictement inchangé pour toute installation existante, sans qu'aucune constante équivalente ne subsiste ailleurs dans le code.

## Compatibilité ascendante des settings

- `ApplicationSettings.from_dict()` utilise `data.get("comfyui_url", "http://127.0.0.1:8000")`/`data.get("comfyui_checkpoint_name", "v1-5-pruned-emaonly-fp16.safetensors")` — un fichier `application_settings.json` antérieur à Mission 018 (sans ces deux clés) charge exactement ces valeurs, pas des chaînes vides.
- `ApplicationSettingsStorage.load()` n'est pas modifié : il continue de retourner le dict brut tel quel, la compatibilité est entièrement gérée côté Domain (`from_dict()`), comme pour tous les champs existants.
- Aucune migration, aucune réécriture forcée du fichier au chargement — le nouveau format n'est écrit qu'à la prochaine sauvegarde normale via `SettingsPage`.

## Stratégie de tests

Comportement observable, pas simple présence d'attribut :
1. Valeurs par défaut Domain (`ApplicationSettings().comfyui_url == "http://127.0.0.1:8000"`, `.comfyui_checkpoint_name == "v1-5-pruned-emaonly-fp16.safetensors"`) et round-trip `to_dict()`/`from_dict()`.
2. Persistance réelle de `comfyui_url` à travers deux instances de `ApplicationSettingsManager` (fermeture/réouverture).
3. Persistance réelle de `comfyui_checkpoint_name`, même mécanisme.
4. Chargement d'un fichier "ancien" (sans ces deux clés) → `ApplicationSettingsManager.settings.comfyui_url`/`comfyui_checkpoint_name` valent respectivement `http://127.0.0.1:8000`/`v1-5-pruned-emaonly-fp16.safetensors` (pas des chaînes vides), aucune exception.
5. `SettingsPage` affiche les deux valeurs chargées depuis `ApplicationSettingsManager`.
6. Modification des deux champs dans `SettingsPage` puis sauvegarde → persistée réellement via `ApplicationSettingsManager`/`ApplicationSettingsStorage`.
7. `MainWindow` construit réellement `ComfyUIEngine` avec l'URL issue d'`ApplicationSettings` — vérifié à la fois sans configuration explicite (valeur par défaut du Domain utilisée directement, aucun fallback propre à `MainWindow` à valider puisqu'il n'en existe plus) et avec une configuration personnalisée (valeur custom effectivement utilisée) — instanciation réelle de `MainWindow` (comme `test_main_window_new_project.py`/`test_dashboard_page.py`), `ApplicationSettingsStorage.default_directory()` redirigé vers un répertoire temporaire (jamais le vrai `%LOCALAPPDATA%`).
8. Même vérification pour `GenerationManager`/`comfyui_checkpoint_name`.

Adaptations nécessaires (pas une nouvelle couverture, une conséquence directe de l'extension du Domain) : les deux assertions de `test_application_settings_roundtrip.py` comparant `ApplicationSettings.to_dict()`/un payload d'événement à un littéral `dict` exact devront inclure les deux nouvelles clés (`http://127.0.0.1:8000`/`v1-5-pruned-emaonly-fp16.safetensors` par défaut) — sans quoi elles échoueraient dès l'ajout des champs.

### Résultats réels

**Tests existants étendus (4)** :
- `test_application_settings_domain_object_roundtrip_and_defaults` — défauts réels (`http://127.0.0.1:8000`/`v1-5-pruned-emaonly-fp16.safetensors`), round-trip `to_dict()`/`from_dict()` avec les 2 nouveaux champs, cas legacy (`from_dict()` sans les 2 clés → mêmes défauts, pas `""`), chaîne vide explicite prouvée distincte du défaut.
- `test_application_settings_manager_update_is_idempotent_and_atomic` — 2 littéraux `dict` existants mis à jour avec les 2 nouvelles clés (adaptation nécessaire, pas une régression volontaire) ; nouveau bloc dédié `update(comfyui_url=..., comfyui_checkpoint_name=...)` : un seul `save()`, un seul événement, puis no-op idempotent sur valeurs identiques.
- `test_application_settings_persist_across_manager_instances` — `comfyui_url`/`comfyui_checkpoint_name` inclus dans la vérification de persistance réelle entre deux instances de `ApplicationSettingsManager`.
- `test_settings_page_application_section_lifecycle` — les deux nouveaux champs affichent les défauts réels sans Workspace ouvert, se sauvegardent réellement via `save_application_settings()`, et sont relus depuis `application_settings_manager.settings` après sauvegarde.

**Nouveaux tests (3)** :
- `test_manager_loads_legacy_settings_file_without_comfyui_url_or_checkpoint_fields` (`test_application_settings_roundtrip.py`) — fichier JSON strictement au format pré-Mission-018 (`python_path`/`comfyui_path`/`onetrainer_path` seuls) → `ApplicationSettingsManager.settings.comfyui_url`/`comfyui_checkpoint_name` valent exactement `http://127.0.0.1:8000`/`v1-5-pruned-emaonly-fp16.safetensors`, aucune exception.
- `test_main_window_uses_default_comfyui_settings_when_none_configured` (nouveau fichier `test_main_window_comfyui_settings.py`) — `MainWindow` réel construit avec `ApplicationSettingsStorage.default_directory()` redirigé vers un répertoire temporaire vide (jamais le vrai `%LOCALAPPDATA%`) → `window.comfyui_engine._base_url`/`window.generation_manager._checkpoint_name` valent les défauts `ApplicationSettings`, sans aucun fallback propre à `MainWindow`.
- `test_main_window_uses_configured_comfyui_url_and_checkpoint_from_application_settings` (même fichier) — répertoire temporaire pré-rempli avec des valeurs custom (`http://192.168.1.50:8188`/`sdxl_base.safetensors`) → l'`Engine`/le `Manager` utilisent réellement ces valeurs.

**Résultat tests ciblés** : `Ran 25 tests in 0.897s — OK`.

**Résultat suite complète** : `Ran 234 tests in 74.709s — OK` (231 tests préexistants inchangés + 3 nouveaux, aucune régression sur Workspace/Dashboard/Images/Inference/`ImagePreviewDialog`/persistance du pending state/changement de Workspace/fermeture de l'application).

## Critères d'acceptation — état final

- `comfyui_url`/`comfyui_checkpoint_name` existent sur `ApplicationSettings`, persistés via le mécanisme existant, sans nouveau Manager/Service : ✅.
- `comfyui_path` non détourné, reste sémantiquement distinct : ✅.
- Comportement ComfyUI par défaut strictement inchangé pour une installation existante (fichier de settings absent ou sans ces clés) : ✅, vérifié par test dédié.
- `SettingsPage` permet de consulter et modifier les deux valeurs, dans le style déjà existant de la section Application : ✅.
- `main_window.py` ne contient plus `COMFYUI_BASE_URL`/`COMFYUI_CHECKPOINT_NAME` du tout — `MainWindow` lit exclusivement `ApplicationSettingsManager`, sans repli propre : ✅.
- Aucune reconstruction à chaud de `ComfyUIEngine`/`GenerationManager` introduite : ✅.
- `ComfyUIEngine`/`GenerationManager` non modifiés : ✅, vérifié par `git diff` (aucun de ces deux fichiers ne figure dans le périmètre modifié).
- Suite de tests complète verte, nombre exact confirmé : ✅ (234/234).
- Aucune régression sur Workspace/Dashboard/Images/Inference (state machine complète)/`ImagePreviewDialog`/persistance du pending state/changement de Workspace/fermeture de l'application : ✅.
- Aucune nouvelle dépendance : ✅, `requirements.txt` inchangé.
- Aucune modification hors périmètre : ✅, vérifié par `git status`/`git diff --stat`.

## Fichiers modifiés / créés

- `src/domain/application_settings.py` (modifié) — 2 champs ajoutés (`comfyui_url`, `comfyui_checkpoint_name`), défauts littéraux, `to_dict()`/`from_dict()` étendus.
- `src/managers/application_settings_manager.py` (modifié) — `update()` étendu avec les 2 nouveaux paramètres, même mécanisme d'idempotence/atomicité.
- `src/ui/pages/settings_page.py` (modifié) — 2 nouveaux `QLineEdit` dans la section Application, câblés sur `save_application_settings()`/`update_application_settings()` ; `application_hint` complété avec l'indication de redémarrage.
- `src/ui/main_window.py` (modifié) — `COMFYUI_BASE_URL`/`COMFYUI_CHECKPOINT_NAME` supprimées ; `ComfyUIEngine`/`GenerationManager` lisent directement `application_settings_manager.settings.comfyui_url`/`.comfyui_checkpoint_name`.
- `tests/integration/test_application_settings_roundtrip.py` (modifié) — 4 tests étendus, 1 nouveau test.
- `tests/integration/test_main_window_comfyui_settings.py` (créé, 2 tests).

Liste vérifiée directement depuis `git status --short`/`git diff --stat`. Aucun fichier hors ce périmètre — en particulier, `src/engines/comfyui_engine.py` et `src/managers/generation_manager.py` ne figurent dans aucun diff.

## Hors périmètre

Test de connexion ComfyUI, bouton "Test connection", détection automatique de ComfyUI, découverte automatique des checkpoints, liste déroulante récupérée depuis ComfyUI, changement de configuration à chaud, redémarrage automatique, multi-engine, RunComfy, ComfyUI Cloud, GPT-Image, Seedream, Seedance, Kling, image de référence, img2img, IP-Adapter, ControlNet, galerie `ImagesPage`, modifications du `MainToolBar`, lancement réel de Training, Job system, Plugin system, AI Orchestrator. Toutes les dettes déjà connues avant Mission 018 (ambiguïté `Training`/`Training History`, `BasePage` mort, `MainToolBar` inerte, limite shutdown Mission 013) restent inchangées, non traitées par cette mission.

## Commit correspondant

Mission 018 sera clôturée en commit(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash ni message définitif n'est fixé en dur dans ce document avant la création du commit — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log` une fois la clôture Git effectuée.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission018`), si l'architecte confirme vouloir suivre cette convention pour cette mission. Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission018` une fois créé.

## État final

**Mission 018 est terminée (implémentation et tests).** `ApplicationSettings` est désormais la source de vérité unique pour `comfyui_url`/`comfyui_checkpoint_name`, avec des défauts littéraux identiques au comportement précédemment codé en dur — aucune régression pour une installation existante. `main_window.py` ne contient plus aucune constante de configuration ComfyUI ; `SettingsPage` permet de consulter et modifier ces deux valeurs, avec une indication claire que les changements prennent effet au redémarrage. `ComfyUIEngine`/`GenerationManager` restent strictement inchangés. Validée par 234 tests d'intégration (231 précédents + 3 nouveaux), aucune régression. **Clôture Git (commit/tag/Release) non encore effectuée** à la rédaction de ce document — à réaliser après validation explicite de l'architecte. Mission 019 non définie.
