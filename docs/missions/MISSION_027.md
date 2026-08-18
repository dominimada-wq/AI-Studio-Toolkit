# Mission 027 — Project Rename

Source : audit READ-ONLY préalable sur le renommage du dossier Windows d'un projet AI Studio Toolkit, validé par l'architecte. Conclusion de cet audit, reprise ici comme point de départ de la spécification :

> **Le renommage manuel actuel (Explorateur Windows) est SAFE SOUS CONDITIONS lorsque le projet est fermé dans l'application, mais UNSAFE à chaud (projet ouvert), et casse au minimum les références absolues internes au Workspace** — en particulier les images générées et acceptées depuis `Inference`, physiquement stockées sous `<workspace>/outputs/` mais dont le chemin absolu est enregistré tel quel dans `Workspace.images[]`. `Workspace.name` reste par ailleurs indéfiniment désynchronisé du nom réel du dossier après un renommage manuel, faute de tout mécanisme de mise à jour existant aujourd'hui.

Spécification uniquement — **aucune implémentation, aucun commit, aucun test modifié dans cette passe.**

## 1. Contexte

`Workspace.root` (chemin du dossier) est *runtime-only*, jamais sérialisé — reconstruit à chaque `create()`/`open()` depuis le chemin réellement fourni (`src/domain/workspace.py`). `Workspace.name`, à l'inverse, est un champ persisté dans `project.json`, dérivé une seule fois du nom du dossier à la création (`WorkspaceManager.create()`) et jamais recalculé ensuite. Aucune fonction de renommage n'existe aujourd'hui dans le code — un renommage ne peut se faire qu'en dehors de l'application, via l'Explorateur Windows, ce qui désynchronise `Workspace.name` et casse les chemins absolus qui pointaient réellement à l'intérieur de l'ancien dossier.

L'objectif de cette mission est de fournir un mécanisme de renommage **piloté par l'application elle-même**, qui maintienne `Workspace.root`/`Workspace.name`/les chemins internes cohérents en une seule opération, sans jamais toucher aux chemins externes au Workspace (fichiers Modèle/Workflow/LoRA/Image choisis ailleurs sur le disque, `ApplicationSettings.comfyui_path`/`python_path`/`onetrainer_path`, qui vivent de toute façon dans un fichier séparé hors de tout Workspace).

## 2. Objectif

Permettre de renommer proprement un projet depuis AI Studio Toolkit (menu **Fichier → Renommer le projet…**), en une seule opération garantissant :
- le renommage physique du dossier ;
- la mise à jour de `Workspace.root`/`Workspace.name` ;
- la réécriture des chemins internes au Workspace vers le nouveau dossier ;
- la préservation stricte, byte-for-byte, de tout chemin externe au Workspace ;
- l'utilisation immédiate du projet renommé, sans fermeture/réouverture ;
- un comportement défini et sûr en cas d'échec à n'importe quelle étape (section 8).

## 3. Périmètre exhaustif des champs de chemins concernés

Audit complet du Domain (`src/domain/*.py`) confirmant 6 champs, atteints par traversée de `Workspace` :

| # | Champ | Chemin de traversée depuis `Workspace` | Nature actuelle |
|---|---|---|---|
| 1 | `Image.file_path` | `workspace.images[*].file_path` | Absolu, choisi via `QFileDialog` **ou** généré par ComfyUI sous `<root>/outputs/` |
| 2 | `Image.file_path` (pool indépendant) | `workspace.characters[*].datasets[*].images[*].file_path` | Absolu, choisi via `QFileDialog` (`DatasetsPage`) |
| 3 | `Model.file_path` | `workspace.models[*].file_path` | Absolu, choisi via `QFileDialog` (`ModelsPage`), peut être vide (`""`, légitime) |
| 4 | `Workflow.file_path` | `workspace.workflows[*].file_path` | Absolu, choisi via `QFileDialog` (`WorkflowsPage`), peut être vide |
| 5 | `LoRA.files[]` | `workspace.characters[*].loras[*].files[*]` | Liste d'absolus, choisis via `QFileDialog` (`LoRAPage`) |
| 6 | `LoRA.thumbnail` | `workspace.characters[*].loras[*].thumbnail` | Absolu si renseigné — **aucun Manager n'écrit ce champ aujourd'hui** (toujours `""` en pratique), inclus par exhaustivité et cohérence : le remap générique le laisse de toute façon inchangé tant qu'il est vide (règle 6, section 4) |

Champs explicitement **exclus**, vérifiés non pertinents : `Prompt.text` (texte libre, jamais interprété comme chemin), `Training.dataset_id` (référence UUID interne, pas un chemin), `Character.bio/description/character_lock/personality/interests/trigger_token` (texte libre), `Settings.theme/language`, et l'intégralité d'`ApplicationSettings` (`comfyui_path`, `python_path`, `onetrainer_path`, `comfyui_url`, `comfyui_checkpoint_name`) — stockée dans un fichier séparé (`%LOCALAPPDATA%\AIStudioToolkit\application_settings.json`), structurellement hors de tout Workspace, donc **jamais touchée par cette mission, à aucun titre**.

## 4. Stratégie de distinction interne / externe — pathlib robuste

Pas de substitution de préfixe sur la chaîne brute. Mécanisme retenu, appliqué à chaque chemin candidat :

1. `old_root_resolved = old_root.resolve()`, calculé **avant** le renommage physique du dossier (tant qu'il existe encore sur disque), et réutilisé pour toutes les comparaisons — jamais recalculé après coup.
2. Pour chaque chemin candidat `path_str` :
   - chaîne vide (`""`) → toujours laissée inchangée (valeur légitime "aucun fichier associé", `Model.file_path`/`Workflow.file_path`) ;
   - sinon, `candidate = Path(path_str).resolve()` (sûr même si le fichier a disparu — `resolve()` sans `strict=True` normalise sans lever d'exception) ;
   - comparaison **composant par composant** (`candidate.parts` vs `old_root_resolved.parts`), chaque composant normalisé via `os.path.normcase()` — gère explicitement l'insensibilité à la casse de Windows/NTFS et la normalisation des séparateurs, sans dépendre d'un comportement implicite de `pathlib` supposé mais non garanti par version de Python ; no-op sur les autres OS, mécanisme portable ;
   - si tous les composants de `old_root_resolved` correspondent au préfixe de `candidate` → chemin **interne** : la partie restante est recalculée sous `new_root` (`new_root.joinpath(*partie_restante)`) ;
   - sinon → chemin **externe** : valeur laissée **strictement inchangée**, aucune écriture.
3. Cas limite couvert explicitement par test : `candidate == old_root_resolved` exactement (partie restante vide) → remappé vers `new_root` lui-même, sans erreur d'indexation.

Cette logique est **générique** (un seul point d'implémentation), appliquée aux 6 champs de la section 3 — aucune règle dupliquée par type d'entité.

## 5. Emplacement exact de la logique de renommage

Respect strict des couches (`CLAUDE.md`) : aucune logique de renommage dans le Domain (dataclasses inchangées), aucune dans l'UI au-delà de la validation de saisie déjà déléguée à la Presentation par convention.

- **`src/infrastructure/storage/workspace_storage.py`** (Infrastructure — toute I/O brute déjà centralisée ici) :
  - `WorkspaceStorage.save()` **durci** (voir section 8) — écriture atomique (fichier temporaire dans le même dossier + `os.replace()`), signature et comportement inchangés pour tous les appelants existants.
  - Nouvelle méthode statique `WorkspaceStorage.rename_folder(old_root, new_root) -> None` : vérifie `new_root.exists()` → lève `WorkspaceStorageError` ; sinon tente `old_root.rename(new_root)`, toute `OSError` (permission refusée, verrouillage, périphérique différent) capturée et enveloppée en `WorkspaceStorageError`. Même contrat d'erreur que `load()`/`save()`/`create_directories()` existants.

- **`src/managers/workspace_manager.py`** (Managers — orchestration d'état, aucun widget) :
  - Nouvelle constante `WORKSPACE_RENAMED = "workspace.renamed"`.
  - Nouvelle méthode publique `rename(self, new_name: str) -> bool` — orchestration complète (section 7), seule méthode publique de cette mission touchant l'état.
  - Deux méthodes privées, **pures, sans mutation de `self.current_workspace`** : `_build_renamed_payload(workspace, old_root_resolved, new_root, new_name) -> dict` (calcule un `to_dict()` entièrement neuf avec `name` et les 6 champs de la section 3 remappés, sans toucher aux objets Domain vivants) et `_remap_path(path_str, old_root_resolved, new_root) -> str` (logique unitaire de la section 4, pure, sans I/O). Révisé en section 7 : `self.current_workspace` n'est mutable qu'une fois le renommage physique **et** la sauvegarde tous deux réussis — voir la justification détaillée de l'ordonnancement transactionnel.
  - Aucune dépendance nouvelle vers `CharacterManager`/`DatasetManager`/`LoRAManager` : `WorkspaceManager` accède directement à `self.current_workspace.characters[*].datasets/loras`, exactement comme `Workspace` expose déjà cette collection nested — aucune violation du Dependency Rule, aucun sens de dépendance inversé.

- **`src/ui/dialogs/rename_project_dialog.py`** (nouveau fichier, Presentation) : `RenameProjectDialog`, calqué sur `NewProjectDialog` (`src/ui/dialogs/new_project_dialog.py`) mais réduit à un seul champ (le dossier parent est fixe = dossier parent du projet actuel, non modifiable). **Réutilise `validate_project_name()` déjà défini dans `new_project_dialog.py`** (import direct, aucune duplication de règle de validation) et calcule en plus, comme `NewProjectDialog._compute_target_path()` le fait déjà pour la création, un message d'erreur immédiat si le dossier cible existe déjà. Aucune validation de contenu métier ajoutée dans le Manager (`CLAUDE.md`) — la couche UI reste seule responsable de ce filtrage préalable ; le Manager/Storage effectue uniquement les vérifications de précondition filesystem (section 7).

- **`src/ui/menubar.py`** : nouvelle `QAction self.action_rename_project = QAction("Renommer le projet…", self)`, ajoutée au `file_menu` juste après `action_save_project` (avant le séparateur qui précède `action_exit`) :
  ```python
  self.file_menu.addAction(self.action_save_project)
  self.file_menu.addAction(self.action_rename_project)
  self.file_menu.addSeparator()
  self.file_menu.addAction(self.action_exit)
  ```

- **`src/ui/main_window.py`** : nouvelle méthode `rename_project()`, câblée à `self.menu.action_rename_project.triggered`, suivant exactement le squelette de `new_project()`/`save_project()` (ouvre `RenameProjectDialog`, sur acceptation appelle `workspace_manager.rename(dialog.new_name)`, capture `WorkspaceManagerError` → `QMessageBox.critical`, message de succès en `statusBar()`). `WORKSPACE_RENAMED` ajouté à deux abonnements existants (section 6) — aucune nouvelle boucle de câblage introduite.

## 6. `WORKSPACE_RENAMED` — qui s'abonne, qui ne s'abonne pas, et pourquoi

- **Ajouté** au tuple `workspace_events` de `main_window.py` (déjà `CREATED, OPENED, SAVED, CLOSED`, câblé à `dashboard_page.update_project`, `images_page.update_images`, `characters_page.update_characters`, `datasets_page.update_datasets`, `lora_page.update_loras`, `prompts_page.update_prompts`, `training_page.update_trainings`, `models_page.update_models`, `workflows_page.update_workflows`, `settings_page.update_settings`) — chaque Page relit l'état complet depuis son Manager, exactement l'effet recherché après un renommage (nouveau nom de projet affiché, nouveaux chemins visibles).
- **Ajouté** à la boucle dédiée `(WORKSPACE_CREATED, WORKSPACE_OPENED, WORKSPACE_CLOSED)` qui réinitialise `inference_page.reset_for_workspace_change` — le commentaire déjà présent dans le code justifie précisément ce choix : *"WORKSPACE_SAVED deliberately excluded, since saving... never changes that context"* ; un renommage, lui, **change** `current_workspace.root`, donc entre exactement dans la même catégorie que Created/Opened/Closed selon cette règle déjà écrite. Sans cet ajout, un résultat de génération en attente (non encore Accepté) dont le chemin absolu pointait sous l'ancien dossier resterait affiché comme valide après un renommage, alors que le fichier physique est désormais introuvable à ce chemin — `_on_accept_clicked()` échouerait alors avec "Fichier introuvable" au moment de l'Accept, un échec tardif et évitable.
- **Non ajouté** aux abonnements internes de `CharacterManager`/`DatasetManager`/`ModelManager`/`WorkflowManager`/`LoRAManager` qui réinitialisent leur `active_*_id` sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED` (définis dans le `__init__` de chaque Manager, jamais dans `main_window.py`) — décision architecturale explicite : un renommage ne change l'identité d'aucune entité ni la sélection en cours, seulement des chemins internes ; réinitialiser la sélection active serait une régression UX (l'utilisateur perdrait sa sélection courante pour une opération qui ne le justifie pas). Couvert par test dédié (section 12).

## 7. Comportement de `WorkspaceManager.rename()` — ordonnancement transactionnel révisé

Contrat idempotent, même famille que `CharacterManager.update()`/`ModelManager.update_file_path()` — mais avec une différence délibérée et importante par rapport à ces précédents : **`self.current_workspace` n'est mutable qu'une fois que *toutes* les opérations risquées (renommage physique, sauvegarde) ont déjà réussi.** Ce choix ("commit en dernier", détaillé et justifié ci-dessous) remplace la formulation initiale de cette spécification ("muter puis retenter"), à la demande explicite de l'architecte de sécuriser précisément ce point avant implémentation.

```python
def rename(self, new_name: str) -> bool:
```

**Ordre réellement implémenté**, correspondant point par point à l'ordre demandé par l'architecte :

1. **Validation du nouveau nom et calcul du nouveau root.** La validation de contenu (`validate_project_name`) reste entièrement à la charge de l'UI (`RenameProjectDialog`, section 10) — `rename()` lui-même ne fait aucune validation de contenu métier (`CLAUDE.md`). Si `self.current_workspace is None` → lève `WorkspaceManagerError` immédiatement, aucun effet. `new_root` est calculé (`old_root.parent / new_name`) dès que `folder_needs_rename` est déterminé vrai (voir étape 2).
2. **Capture de l'état nécessaire au rollback.** `old_root = workspace.root`, `old_root_resolved = old_root.resolve()`, `old_name = workspace.name` — capturés en variables locales **avant toute autre opération**. Aucune copie profonde de `Workspace` n'est nécessaire : puisque `workspace` (l'objet Domain vivant, `self.current_workspace`) n'est mutable qu'à l'étape 6 (après succès complet), ces trois valeurs simples suffisent à reconstruire tout message de rollback ou d'erreur — il n'y a littéralement rien d'autre à restaurer, l'objet n'ayant jamais été touché avant ce point.
   - `folder_needs_rename = (new_name != old_root.name)`
   - `name_needs_update = (new_name != old_name)`
   - Si ni l'un ni l'autre → `return False` (aucun `save()`, aucun événement, aucune I/O) — idempotence stricte.
3. **Calcul des remappings internes sans mutation prématurée.** `new_data = self._build_renamed_payload(workspace, old_root_resolved, new_root, new_name)` — fonction **pure**, opère sur `workspace.to_dict()` (une copie fraîche, jamais partagée avec les objets Domain vivants — chaque `to_dict()` de ce projet construit systématiquement des dicts neufs) : remplace `"name"`, remappe les 6 champs de chemins de la section 3 selon la règle de la section 4. **`self.current_workspace` n'est touché à aucun moment par cette étape.**
4. **Renommage filesystem.** Si `folder_needs_rename` : `WorkspaceStorage.rename_folder(old_root, new_root)`. Si cette étape échoue (dossier cible déjà existant, `OSError`) → `WorkspaceManagerError` levée immédiatement, **`self.current_workspace` toujours strictement identique à avant l'appel** (rien n'a encore été mutable) — pas de rollback à effectuer, l'état était déjà cohérent.
5. **Sauvegarde atomique du nouveau `project.json`.** `WorkspaceStorage.save(new_root, new_data)` — tentée **avant** toute mutation de `self.current_workspace`. Deux issues :
   - **Succès** → seulement maintenant, étape 6 : `self.current_workspace = Workspace.from_dict(new_data, root=new_root)` (remplacement complet de l'objet, jamais mutation champ par champ — voir justification ci-dessous), puis `self._publish(WORKSPACE_RENAMED)`, puis `return True`.
   - **Échec** → séquence de rollback détaillée en section 8 ; dans tous les cas, une `WorkspaceManagerError` est levée et **aucune mutation de `self.current_workspace` n'a lieu, aucun événement n'est publié**.

**Pourquoi remplacer `self.current_workspace` en bloc (étape 6) plutôt que muter `root`/`name`/les chemins un par un ?** Trois raisons :
- Cela **élimine structurellement** le besoin de restaurer un état Domain partiellement muté en cas d'échec de sauvegarde : puisque la mutation n'intervient qu'après le succès de la sauvegarde, il n'y a, dans les deux chemins d'échec de l'étape 5, absolument rien à défaire côté Domain — l'objet est resté intact du début à la fin de l'opération.
- `new_data` est déjà exactement le contenu qui vient d'être écrit sur disque avec succès — reconstruire l'objet en mémoire à partir de ce même dict (`Workspace.from_dict(new_data, root=new_root)`) garantit par construction que l'état en mémoire est **byte-identique** à l'état persisté, sans risque de divergence entre une mutation manuelle des 6 champs de chemins et le contenu réellement sauvegardé.
- Vérifié explicitement dans le code existant que ce remplacement est sûr pour tous les Managers dépendants : `CharacterManager`/`DatasetManager`/`ModelManager`/`WorkflowManager`/`LoRAManager` ne conservent jamais de référence directe vers un objet `Character`/`Dataset`/`Model`/`Workflow`/`LoRA` — chacun ne retient qu'un `*_id` (chaîne stable, préservée par le round-trip `to_dict()`/`from_dict()`) et re-résout l'objet vivant via une recherche fraîche (`_find()`) à chaque accès (`active_character`, `active_dataset`, etc. sont des `@property`, jamais un champ caché). Remplacer entièrement `self.current_workspace` est donc exactement le même mécanisme, sans risque, que celui déjà utilisé par `WorkspaceManager.open()` (`self.current_workspace = Workspace.from_dict(data, root=folder)`).

**Effet observable secondaire, non recherché mais correct** : si `Workspace.name` était déjà désynchronisé du nom réel du dossier (séquelle d'un ancien renommage manuel via l'Explorateur, cas documenté par l'audit), un appel avec `new_name == old_root.name` (l'utilisateur "renomme" vers le nom déjà affiché du dossier) ne déclenche que `name_needs_update` (vrai), `folder_needs_rename` restant faux : aucun renommage physique, simple correction de `Workspace.name` et sauvegarde (`new_root == old_root` dans ce cas). C'est une conséquence directe et gratuite de l'application symétrique du principe d'idempotence aux deux faits indépendants (nom réel du dossier, `Workspace.name`) — pas une fonctionnalité de "réparation" développée séparément, mais à documenter comme comportement attendu et couvert par test (section 14).

`Character.name` n'est **jamais** lu ni modifié par `rename()` — aucune ligne de cette méthode ne touche `Workspace.characters[*].name` (le remap de la section 3 porte exclusivement sur les 6 champs de chemins, jamais sur `name`), cohérent avec la règle déjà actée en Mission 026 (`Workspace.name`/`Character.name` volontairement indépendants après l'initialisation).

## 8. Atomicité et stratégie de rollback

Analyse scénario par scénario, comme demandé — révisée pour intégrer un **rollback filesystem best-effort** en cas d'échec de sauvegarde après un renommage physique réussi (demande explicite de l'architecte, remplaçant la version initiale "aucune tentative automatique" de cette spécification) :

| Scénario | Comportement retenu |
|---|---|
| Nouveau nom invalide (vide, caractère interdit, nom réservé Windows, séparateur, espace/point final) | Bloqué **au niveau UI** par `validate_project_name()` avant même l'appel à `rename()` — bouton "Renommer" désactivé, message affiché, aucune tentative filesystem. Défense en profondeur non ajoutée côté Manager (cohérent avec "aucune validation de contenu métier dans les Managers", `CLAUDE.md`) — un appel direct à `rename()` avec un nom invalide (hors UI, ex. test) tente le renommage OS, qui échoue alors nativement avec une `OSError` remontée en `WorkspaceManagerError`. |
| Dossier cible déjà existant | Vérifié explicitement dans `WorkspaceStorage.rename_folder()` avant tout `Path.rename()` → `WorkspaceStorageError` dédiée, aucune tentative de renommage physique, `current_workspace` intact. |
| Permission refusée / dossier ou fichier verrouillé (renommage initial) | `Path.rename()` lève `OSError` (ex. `PermissionError`), capturée et enveloppée en `WorkspaceManagerError`. Aucun état modifié : `current_workspace` strictement intact (section 7, étape 4 — rien n'a encore été mutable à ce stade). |
| Échec du renommage filesystem initial (cas général, ex. périphérique réseau instable) | Identique au cas précédent — `old_root.rename(new_root)` est la seule opération OS non purement locale de toute la séquence ; sur un même volume (cas normal d'un projet AI Studio Toolkit), cette opération est atomique au niveau OS (Windows `MoveFileEx`/`os.rename` sur un même volume ne laisse jamais un état partiel — succès ou échec complet, jamais un renommage "à moitié"). `current_workspace` intact, aucun rollback à effectuer. |
| **Échec de sauvegarde de `project.json` après renommage filesystem réussi** | Voir déroulé complet ci-dessous — c'est le scénario central de cette section. |
| Erreur pendant le calcul des remappings internes (`_build_renamed_payload`) | Opération **purement en mémoire, sans I/O** (`Path.resolve()`/comparaison de composants/`Path.joinpath()` sur une copie `to_dict()`) — aucune écriture disque, aucune mutation de `self.current_workspace` à cette étape (section 7, étape 3). Le seul risque réaliste est une erreur de programmation (ex. accès à un champ inexistant), couvert par les tests unitaires de la section 14, pas par une gestion d'exception runtime dédiée : une régression ici serait un bug à corriger, pas un cas d'échec utilisateur normal à absorber — et puisqu'elle survient strictement avant toute I/O (étape 3 précède l'étape 4), une exception non gérée à ce stade laisserait de toute façon `current_workspace` et le filesystem tous deux intacts. |

### Déroulé détaillé — échec de sauvegarde après renommage filesystem réussi

C'est le seul scénario où une compensation est réellement nécessaire, puisque c'est le seul point de la séquence où une opération filesystem a déjà réussi (le renommage) avant qu'une étape suivante échoue (la sauvegarde). Séquence retenue, dans cet ordre précis :

1. `WorkspaceStorage.save(new_root, new_data)` échoue → `WorkspaceStorageError` interceptée.
2. **Tentative de rollback filesystem** : `WorkspaceStorage.rename_folder(new_root, old_root)` (renomme le dossier en sens inverse). Choix déterminant d'ordonnancement : cette tentative a lieu **avant** toute éventuelle restauration de l'état Domain en mémoire — mais comme établi en section 7, `self.current_workspace` n'a de toute façon **jamais été mutable** à ce stade (le remplacement de l'étape 6 n'intervient qu'après un succès complet), donc il n'y a structurellement rien à restaurer côté Domain dans les deux branches ci-dessous : seul l'état du filesystem doit être réconcilié avec l'état (inchangé) de `self.current_workspace`.
3. **Si le rollback filesystem réussit** (dossier de nouveau nommé `old_name`) : le `project.json` original, jamais ouvert en écriture grâce à la sauvegarde atomique (section 9), est physiquement revenu avec le dossier, intact, avec son contenu d'avant tentative. `self.current_workspace` (jamais muté) reste cohérent avec cet état. Une `WorkspaceManagerError` est levée, décrivant l'échec de sauvegarde d'origine — **l'opération est un échec propre et intégralement annulé**, pas un succès partiel : aucun `WORKSPACE_RENAMED` n'est publié, `rename()` ne retourne jamais `True` sur ce chemin.
4. **Si le rollback filesystem échoue également** (ex. le même verrou qui a fait échouer la sauvegarde bloque aussi le second renommage) : **jamais masqué derrière un simple retour** — une `WorkspaceManagerError` distincte est levée, avec un message explicite contenant toutes les informations nécessaires à une récupération manuelle : l'échec de sauvegarde d'origine, l'échec du rollback lui-même, le nom et le chemin réels du dossier sur disque à cet instant (`new_root`, toujours nommé `new_name`), le fait que `project.json` à l'intérieur reflète encore l'ancien état (`old_name`, chemins non remappés) grâce à l'écriture atomique, et le fait que `self.current_workspace` en mémoire pointe toujours vers `old_root` — un chemin qui **n'existe plus sur disque**. Le message recommande explicitement à l'utilisateur soit de renommer le dossier manuellement vers `old_name`, soit de rouvrir le projet depuis son emplacement réel actuel (`new_root`) puis de retenter le renommage. Aucun événement publié, aucune mutation de `self.current_workspace`.

**Pourquoi cet ordre (rollback filesystem avant toute restauration Domain) plutôt que l'inverse ?** Restaurer d'abord `self.current_workspace` vers l'état "ancien" puis tenter le renommage filesystem en sens inverse créerait une fenêtre où l'objet en mémoire (déjà revenu à `old_root`) et le disque (encore nommé `new_name`) seraient en désaccord si le second renommage échouait — exactement le type d'incohérence que cette section cherche à éviter. En ne mutant jamais `self.current_workspace` avant la confirmation complète du succès (section 7), ce risque est éliminé structurellement : dans les deux branches (rollback réussi ou non), l'état en mémoire de `self.current_workspace` — toujours celui d'avant tout l'appel — est déjà correct par construction vis-à-vis d'au moins l'un des deux états filesystem possibles (`old_root` si le rollback réussit), et l'erreur remontée en cas contraire l'indique explicitement plutôt que de prétendre à une cohérence qui n'existe pas.

**Stratégie retenue, formulée explicitement** : pas de transaction générale distribuée, pas de journal de rollback générique — chaque étape individuelle est rendue soit **atomique par construction** (renommage de dossier = garantie OS sur un même volume ; sauvegarde de `project.json` = écriture fichier temporaire + `os.replace()`, section 9), soit **sans effet de bord tant qu'elle n'a pas réussi** (remap en mémoire, mutation Domain différée). Le seul scénario intrinsèquement délicat (renommage réussi, sauvegarde échouée) bénéficie d'un **rollback filesystem best-effort explicite**, dont l'échec éventuel est lui-même toujours signalé de façon détaillée et actionnable — jamais absorbé silencieusement. C'est une stratégie proportionnée : elle couvre exactement le point soulevé par l'architecte ("ne doit pas pouvoir laisser facilement le Workspace dans un état moitié ancien / moitié nouveau", "ne masque jamais cette situation derrière un simple False") sans construire un mécanisme de transaction générique non justifié par le reste du projet.

**`WORKSPACE_RENAMED` — garantie de publication unique et conditionnelle au succès complet** : dans le code de `rename()` (section 7), l'appel à `self._publish(WORKSPACE_RENAMED)` est la toute dernière instruction du chemin de succès, atteinte uniquement après le remplacement réussi de `self.current_workspace`. Chacun des chemins d'échec décrits ci-dessus se termine par une `WorkspaceManagerError` levée **avant** d'atteindre cette ligne — structurellement, aucun chemin d'échec ne peut publier cet événement, et le chemin de succès ne peut le publier plus d'une fois (aucune boucle, un seul appel possible par exécution de `rename()`). Couvert explicitement par test (section 14).

## 9. Durcissement de `WorkspaceStorage.save()` — écriture atomique

Modification nécessaire à la stratégie de rollback ci-dessus, donc incluse dans le périmètre de cette mission bien qu'elle bénéficie à **tous** les appelants existants de `save()`, pas seulement au renommage :

```python
@staticmethod
def save(folder, data: dict) -> None:
    folder = Path(folder)
    target = folder / WorkspaceStorage.WORKSPACE_FILE
    try:
        fd, tmp_name = tempfile.mkstemp(dir=folder, prefix=".project_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(tmp_name, target)
        except Exception:
            os.unlink(tmp_name)  # best-effort cleanup, jamais laissé traîner
            raise
    except OSError as exc:
        ...  # WorkspaceStorageError, comme aujourd'hui
```

Comportement observable **strictement inchangé** pour tout appelant existant (même signature, même exception levée en cas d'échec) — seul le mécanisme interne change : le fichier `project.json` cible n'est jamais ouvert en écriture directe (ce qui le tronquerait immédiatement), il est remplacé en une seule opération atomique (`os.replace()`, garantie POSIX/Windows) une fois le contenu entièrement écrit avec succès dans un fichier temporaire voisin. Fichier temporaire créé **dans le même dossier** (`dir=folder`) pour garantir que `os.replace()` reste une opération sur le même volume (donc atomique) — jamais dans un dossier temporaire système séparé.

### Nécessité vérifiée pour Mission 027 (et non simple amélioration collatérale)

Question posée explicitement par l'architecte avant implémentation : ce durcissement est-il réellement indispensable à Mission 027, ou seulement une bonne pratique séparable ? Réponse, après vérification du comportement actuel de `save()` (`open(folder / WORKSPACE_FILE, "w", ...)`) : **il est indispensable**, pas seulement souhaitable. `open(..., "w")` tronque immédiatement le fichier cible dès l'ouverture, avant même la moindre écriture — si `json.dump()` échoue ensuite en cours d'écriture (ex. disque plein), l'ancien `project.json` serait déjà détruit/tronqué, quel que soit le dossier dans lequel il se trouve à ce moment. Or la section 8 promeut explicitement, dans le scénario "renommage réussi puis sauvegarde échouée", la garantie suivante : *"le `project.json` original... reste physiquement intact"*, condition nécessaire à ce que le rollback filesystem (renommer le dossier en sens inverse) restaure réellement un état identique à l'état de départ. Sans écriture atomique, cette garantie serait fausse dans le cas général — le rollback filesystem réussirait à renommer le dossier, mais le fichier à l'intérieur pourrait déjà être corrompu par la tentative de sauvegarde ayant échoué. Le durcissement de `save()` est donc une **dépendance directe et nécessaire** de la stratégie de rollback de la section 8, pas une amélioration indépendante — il reste néanmoins bénéfique à tous les appelants existants (`create()`, `open()`→`save()` implicite via chaque Manager, `save_project()`) sans changer leur contrat observable, comme démontré ci-dessus.

**Vérification de non-régression prévue avant implémentation** (section 14) : tous les tests de persistance existants (`test_workspace_roundtrip.py` et les 9 fichiers `test_*_roundtrip.py` qui appellent transitivement `WorkspaceManager.save()`) doivent rester verts sans modification — le changement est interne à `WorkspaceStorage.save()`, invisible depuis `WorkspaceManager`. Un test dédié nouveau vérifie explicitement qu'un échec simulé **avant** `os.replace()` (ex. `json.dump` mocké pour lever une exception) laisse l'ancien `project.json` **totalement inchangé**, byte pour byte.

## 10. `RenameProjectDialog` — comportement UI

- Champ `QLineEdit` pré-rempli avec `workspace.root.name` (le nom réel actuel du dossier — pas `workspace.name`, potentiellement désynchronisé, pour que l'utilisateur voie la valeur réelle qu'il s'apprête à changer).
- Validation live via `validate_project_name()` (importé de `new_project_dialog.py`) à chaque frappe, plus vérification `target_path.exists()` (dossier parent fixe + nouveau nom) — bouton "Renommer" désactivé tant que le nom est invalide, identique au nom actuel du dossier, ou en collision avec un dossier existant ; message d'erreur affiché dans un `QLabel`, même mécanique que `NewProjectDialog.preview_label`.
- Re-validation au moment exact de l'acceptation (`_on_accept_clicked`), même principe que `NewProjectDialog` ("le dossier cible a pu apparaître entre la dernière frappe et le clic").
- Expose `dialog.new_name: str` (analogue à `NewProjectDialog.target_path`), lu par `MainWindow.rename_project()` après `dialog.exec() == QDialog.Accepted`.

## 11. Besoin architectural à documenter (hors périmètre d'implémentation Mission 027)

À consigner dans `docs/PROJECT_CONTEXT.md` **à la clôture** de cette mission (pas avant, pas pendant l'implémentation) comme besoin futur ouvert, formulé exactement tel que demandé par l'architecte :

> Les ressources internes au Workspace devraient-elles être persistées relativement à `Workspace.root` plutôt qu'en chemins absolus ? Cette question dépasse le seul renommage — elle concerne aussi la portabilité/copie/déplacement d'un projet vers un autre disque ou une autre machine (l'audit Mission 027 a confirmé qu'un déplacement inter-disque casse aujourd'hui potentiellement *tous* les chemins absolus internes, pas seulement ceux contenant l'ancien nom de dossier). Peut être traitée séparément de Mission 027 pour limiter le risque de cette mission au renommage seul.

**Aucune migration de chemins relatifs n'est effectuée dans Mission 027** — le remap de la section 4 réécrit des chemins absolus vers de nouveaux chemins absolus, il ne change pas le modèle de stockage.

## 12. Périmètre IN

- `WorkspaceStorage.rename_folder()` (nouvelle méthode statique) + `WorkspaceStorage.save()` durci en écriture atomique (section 9).
- `WorkspaceManager.rename(new_name) -> bool` + `WORKSPACE_RENAMED` + les deux méthodes privées de remap (sections 4, 7).
- `RenameProjectDialog` (nouveau fichier) réutilisant `validate_project_name()`.
- `MainMenuBar.action_rename_project` + `MainWindow.rename_project()`.
- Ajout de `WORKSPACE_RENAMED` aux deux abonnements existants pertinents de `main_window.py` (section 6) — aucune nouvelle boucle de câblage, extension de tuples existants uniquement.
- Tests exhaustifs (section 13).

## 13. Périmètre OUT (explicitement différé)

Renommage automatique de `Character.name` (jamais touché par `rename()`, section 7) ; migration générale de tous les projets vers des chemins relatifs (section 11, différée) ; déplacement du projet vers un autre disque (question distincte, non traitée) ; refonte globale du stockage ; toute évolution du multi-Character/cardinalité ; tout changement ComfyUI/Inference sans rapport avec les chemins (seul `reset_for_workspace_change()` gagne un abonnement supplémentaire, section 6, aucune autre modification d'`InferencePage`) ; refonte de `Settings`/`ApplicationSettings` (ni l'un ni l'autre n'est touché — confirmé hors de portée par l'audit, section 3) ; annulation/undo d'un renommage déjà réussi (un renommage réussi est définitif, comme la création d'un projet) ; détection/réparation automatique de références cassées préexistantes à cette mission (chemins déjà brisés par un ancien renommage manuel avant Mission 027 — non réparés rétroactivement, seul le cas `folder_needs_rename=False && name_needs_update=True` de la section 7 offre une réparation partielle, en sous-produit, non un objectif dédié).

## 14. Stratégie de tests

**Recherche préalable de mocks à signature obsolète** avant tout lancement Qt, même procédure que chaque mission précédente — `WorkspaceStorage.save()` change de mécanisme interne (impact potentiel sur des tests qui mockeraient `open()` directement plutôt que `WorkspaceStorage.save()` elle-même ; à vérifier explicitement avant implémentation).

Tests prévus, tous dans `tests/integration/test_workspace_roundtrip.py` sauf mention contraire (nouvelle classe dédiée `WorkspaceRenameTest`, réutilisant le pattern `setUp`/`_wire` déjà présent dans ce fichier) :

- **Renommage simple** : dossier physiquement renommé sur disque (ancien absent, nouveau présent), `Workspace.root`/`Workspace.name` mis à jour, `rename()` retourne `True`.
- **Idempotence** : `rename(new_name)` avec `new_name` égal au nom de dossier actuel **et** à `Workspace.name` actuel → `False`, aucun `save()`, aucun événement (mock sur `WorkspaceStorage.save`/`event_bus.publish`).
- **Réparation `Workspace.name` sans renommage physique** : `new_name` égal au nom de dossier actuel mais différent de `Workspace.name` (désynchronisation simulée) → dossier non touché, `Workspace.name` corrigé, `save()` appelé, événement publié.
- **`Character.name` strictement inchangé** après renommage (assertion explicite avant/après, sur un Character autre que le principal si plusieurs existent, pour exclure toute confusion avec la logique Mission 026).
- **Image `outputs/` interne correctement remappée** : simuler une image dont `file_path` est construite sous l'ancien `root / "outputs"`, vérifier le nouveau `file_path` sous le nouveau `root`, fichier physique effectivement déplacé (le renommage de dossier déplace le contenu, donc le fichier existe bien au nouveau chemin après coup).
- **Dataset interne correctement remappé** : `Character.datasets[].images[].file_path` sous l'ancien root → remappé.
- **Model/Workflow/LoRA internes correctement remappés** : au moins un cas par type, `file_path`/`files[]` sous l'ancien root → remappés ; `LoRA.thumbnail` inclus par cohérence (section 3) même si toujours vide en pratique.
- **Ressources externes strictement inchangées** : au moins un `file_path` situé hors de l'ancien `root` (autre dossier du disque) pour chaque type (Image/Dataset image/Model/Workflow/LoRA files) → valeur identique avant/après, comparaison stricte.
- **Chaîne vide préservée** : `Model.file_path == ""` / `Workflow.file_path == ""` → reste `""` après renommage (pas d'erreur, pas de remap sur une valeur "vide" — voir règle de la section 4).
- **Persistance après fermeture/réouverture** : renommage, puis `close()` + nouveau `WorkspaceManager` + `open(new_root)` → toutes les valeurs remappées relues à l'identique depuis le `project.json` réellement écrit sur disque.
- **Ancien dossier absent / nouveau dossier présent** : vérification directe sur le filesystem réel (`Path.exists()`), pas seulement sur l'état en mémoire.
- **Dossier cible déjà existant** : `WorkspaceManagerError` levée, dossier source **toujours présent et inchangé**, `Workspace.root`/`.name` inchangés (aucun effet partiel).
- **Échec du rename filesystem initial → état Domain strictement inchangé** (`Path.rename`/`WorkspaceStorage.rename_folder` mocké pour lever une erreur avant tout renommage réel) : `WorkspaceManagerError` levée ; `self.current_workspace` (identité d'objet **et** valeurs — `root`, `name`, tous les chemins internes) rigoureusement identique, par comparaison directe, à l'état capturé juste avant l'appel à `rename()` — pas seulement "des valeurs équivalentes", le même objet, jamais remplacé (section 7, étape 6 jamais atteinte).
- **Échec de sauvegarde après renommage réussi → rollback Domain + filesystem** : `WorkspaceStorage.rename_folder()` s'exécute réellement (dossier physiquement renommé sur disque temporaire de test), puis `WorkspaceStorage.save()` mocké pour lever `WorkspaceStorageError`. Vérifications : (a) le rollback filesystem s'exécute et réussit — l'ancien nom de dossier existe de nouveau sur disque, le nouveau nom n'existe plus ; (b) `project.json` à l'intérieur du dossier (revenu à son nom d'origine) contient exactement son contenu d'avant la tentative de renommage (byte pour byte, preuve directe que l'écriture atomique de la section 9 a bien empêché toute troncature pendant l'échec de `save()`) ; (c) `self.current_workspace` strictement inchangé (même vérification qu'au point précédent — jamais muté, section 7) ; (d) `WorkspaceManagerError` levée, message mentionnant l'échec de sauvegarde d'origine.
- **Échec simulé du rollback lui-même → erreur explicite, jamais un simple `False`** : même montage que le test précédent, mais le second `WorkspaceStorage.rename_folder()` (celui du rollback) est *lui aussi* mocké pour échouer. Vérifications : (a) une `WorkspaceManagerError` est levée (jamais un retour silencieux, jamais `False`) ; (b) le message de l'exception contient, vérifié explicitement par assertion sur le texte : le nom/chemin réel du dossier sur disque à cet instant (`new_root`), la mention explicite que `project.json` à cet endroit reflète encore l'ancien état, et une indication actionnable de récupération manuelle (rouvrir depuis le nouvel emplacement ou renommer manuellement) ; (c) dossier physiquement resté nommé `new_name` sur disque (confirmé par `Path.exists()`), cohérent avec le message d'erreur ; (d) `self.current_workspace` toujours inchangé (jamais muté, comme dans tous les autres chemins d'échec).
- **Absence de corruption de `project.json`** en cas d'échec d'écriture pendant `WorkspaceStorage.save()` elle-même, hors tout renommage (test dédié sur `WorkspaceStorage` directement : simuler un échec d'écriture du fichier temporaire, par exemple `json.dump` levant une exception avant que `os.replace()` ne soit atteint) → fichier `project.json` original **totalement inchangé**, byte pour byte (pas de troncature) — complète la couverture déjà existante de `save()`/`load()`, et constitue la preuve unitaire directe sur laquelle s'appuient les deux tests de rollback ci-dessus.
- **Aucun `WORKSPACE_RENAMED` sur tous les chemins d'échec** : test paramétré/regroupé couvrant chacun des scénarios d'échec ci-dessus (nom invalide tenté directement, dossier cible existant, échec du rename initial, échec de sauvegarde avec rollback réussi, échec de sauvegarde avec rollback lui-même en échec) — un espion (`Mock`/liste d'événements capturés) sur `event_bus.publish` confirme qu'aucun de ces scénarios ne publie jamais `WORKSPACE_RENAMED`.
- **`WORKSPACE_RENAMED` publié exactement une fois après succès complet** : sur un renommage réellement réussi (dossier renommé, sauvegarde réussie), le compteur d'appels à `event_bus.publish(WORKSPACE_RENAMED, ...)` vaut exactement `1` — jamais `0`, jamais `2` — payload = `to_dict()` à jour (nouveau `name`, chemins remappés), et `self.current_workspace` désormais bien le nouvel objet reconstruit via `Workspace.from_dict(new_data, root=new_root)`.
- **`active_character_id`/`active_dataset_id`/`active_model_id`/`active_workflow_id`/`active_lora_id` préservés** après un renommage réussi (aucune réinitialisation) — confirme la décision de la section 6 (`WORKSPACE_RENAMED` non abonné aux resets internes des Managers). Vérifié aussi que ces mêmes identifiants restent valides après le remplacement complet de `self.current_workspace` (étape 6, section 7) — cohérent avec le mécanisme de résolution par `*_id` déjà en place (section 7, justification du remplacement en bloc).
- **`InferencePage.reset_for_workspace_change` appelé** sur `WORKSPACE_RENAMED` (test d'intégration ciblé, `tests/integration/test_inference_page.py` étendu ou nouveau test dans `test_main_window_rename_project.py`) — un résultat en attente est invalidé par un renommage.
- **Non-régression des roundtrips existants** : suite complète relancée sans modification d'assertions substantielles dans `test_dataset_roundtrip.py`/`test_lora_roundtrip.py`/`test_model_roundtrip.py`/`test_workflow_roundtrip.py`/`test_character_roundtrip.py`/`test_application_settings_roundtrip.py`.

Nouveaux fichiers de test UI, sur le modèle exact de `test_new_project_dialog.py`/`test_main_window_new_project.py` :

- `tests/integration/test_rename_project_dialog.py` : validation live du champ (réutilise les cas déjà couverts pour `validate_project_name` sans les dupliquer — teste le câblage du dialogue, pas la fonction elle-même), pré-remplissage depuis `workspace.root.name`, désactivation du bouton sur nom identique/collision, `new_name` correctement exposé après acceptation.
- `tests/integration/test_main_window_rename_project.py` : `RenameProjectDialog` toujours patché (jamais de `exec()` réel, même règle que Mission 016) — annulation n'appelle jamais `workspace_manager.rename()` ; acceptation appelle `rename()` avec exactement `dialog.new_name` ; `WorkspaceManagerError` affichée via `QMessageBox.critical` ; `open_project()`/`save_project()`/`new_project()` non affectés (test de non-régression du fichier existant).

Nombre exact de tests final à confirmer après implémentation, comme pour chaque mission précédente (402 + N).

## 15. Fichiers concernés (aucun modifié dans cette passe — liste prévisionnelle pour l'implémentation)

- `src/infrastructure/storage/workspace_storage.py` — `save()` durci, `rename_folder()` ajouté.
- `src/managers/workspace_manager.py` — `WORKSPACE_RENAMED`, `rename()`, deux méthodes privées de remap.
- `src/ui/dialogs/rename_project_dialog.py` — nouveau fichier.
- `src/ui/menubar.py` — nouvelle `QAction`.
- `src/ui/main_window.py` — `rename_project()`, deux abonnements étendus.
- `tests/integration/test_workspace_roundtrip.py` — nouvelle classe `WorkspaceRenameTest` + tests dédiés à l'atomicité de `save()`.
- `tests/integration/test_rename_project_dialog.py` — nouveau fichier.
- `tests/integration/test_main_window_rename_project.py` — nouveau fichier.
- `tests/integration/test_inference_page.py` — extension ciblée (abonnement `WORKSPACE_RENAMED`).
- `docs/missions/MISSION_027.md` — cette spécification, puis complétée avec les résultats réels à la clôture.
- `docs/PROJECT_CONTEXT.md` / `CHANGELOG.md` — **non modifiés dans cette passe** (section 16).

Aucun fichier Domain (`src/domain/*.py`) modifié — confirmé par construction (section 5 : aucune logique de renommage n'entre dans les dataclasses).

## 16. `docs/PROJECT_CONTEXT.md` — non modifié à ce stade

Conformément à l'instruction de l'architecte, `docs/PROJECT_CONTEXT.md` n'est pas modifié pendant cette passe de spécification. Une seule décision architecturale nouvelle mériterait d'y être enregistrée avant même l'implémentation, mais elle n'est **pas urgente** et peut attendre la clôture normale de la mission comme toutes les précédentes : l'introduction de `WORKSPACE_RENAMED` comme quatrième catégorie d'événement "changement de contexte Workspace" aux côtés de `CREATED`/`OPENED`/`CLOSED` (section 6) formalise une règle déjà présente en commentaire dans le code (`main_window.py`) mais jamais énoncée dans la documentation projet. Elle sera intégrée à la mise à jour standard de `docs/PROJECT_CONTEXT.md` à la clôture de Mission 027, en même temps que le besoin architectural de la section 11 — aucune des deux ne bloque le début de l'implémentation.

## 17. Risques résiduels

- **Renommage à chaud concurrent hors de l'application** : si un processus externe (autre instance de l'Explorateur, antivirus, sync cloud type OneDrive/Google Drive si le projet y est stocké) verrouille un fichier au moment précis du `Path.rename()`, l'échec est correctement capturé (`WorkspaceManagerError`), mais la cause exacte (quel processus, quel fichier) ne sera pas diagnosticable depuis l'application — limitation acceptée, cohérente avec le niveau de diagnostic déjà offert par les erreurs filesystem existantes (`create()`/`open()`/`save()`).
- **Dossier synchronisé par un service cloud** (OneDrive, etc.) : un renommage physique déclenché par l'application peut interagir de façon non déterministe avec la synchronisation en cours (fichiers temporairement verrouillés par le client de synchronisation) — non testé spécifiquement dans cette mission (hors périmètre, pas de dépendance à un service cloud dans le projet).
- **Chemins déjà cassés avant Mission 027** (séquelles d'un ancien renommage manuel non couvert par cette mission) ne sont pas détectés ni réparés automatiquement — seuls les chemins actuellement valides sous l'ancien `root` sont remappés ; un chemin déjà orphelin avant le renommage le reste après (comportement neutre, ni amélioré ni dégradé).
- **Fenêtre d'incohérence dossier-renommé/`project.json`-pas-encore-réécrit** (section 8) : si l'utilisateur ferme l'application immédiatement après cette erreur précise, sans relancer la sauvegarde, le projet reste dans cet état jusqu'à la prochaine ouverture — à ce moment-là, `WorkspaceManager.open(new_root)` lira l'ancien contenu (ancien `name`, anciens chemins) mais avec `root` pointant correctement vers le nouveau dossier : fonctionnellement proche de l'état "juste après un renommage manuel Explorateur" déjà documenté comme SAFE SOUS CONDITIONS par l'audit — pas un état pire que celui que Mission 027 cherche à améliorer, simplement pas la garantie de cohérence immédiate visée par le cas nominal.
- **Volume de remap sur un projet très volumineux** (des milliers d'images/fichiers internes) : le remap reste une opération en mémoire, linéaire en nombre d'entrées — aucun risque de performance identifié à l'échelle réaliste de ce projet, non traité comme un risque significatif.
- **Renommage bloqué par une fenêtre de l'Explorateur Windows ouverte dans un sous-dossier du projet** (cause confirmée, voir section 20) : `explorer.exe` peut détenir des handles sur `images/`, `outputs/`, `models/`, etc., empêchant le renommage du dossier racine avec `WinError 5`. Ce n'est pas un défaut applicatif ni une corruption du Workspace — c'est un verrouillage Windows externe, légitime, que l'application ne peut pas et ne doit pas contourner. Traité par un message utilisateur clair et actionnable (`WorkspaceRenamePermissionError`, section 20) plutôt que par une correction du symptôme — risque résiduel accepté : l'utilisateur doit fermer les fenêtres de l'Explorateur concernées avant de réessayer, ce que le message indique explicitement.

## 18. Critères d'acceptation

- Suite de tests complète verte, nombre exact confirmé, aucune régression sur les roundtrips existants.
- `git diff --stat` confirmant exactement le périmètre de fichiers de la section 15.
- Un renommage réel (smoke test, section 19) laisse le projet immédiatement utilisable sans fermeture/réouverture.
- **La chaîne de renommages consécutifs `ProjetA → ProjetB → ProjetC` (sans redémarrage), puis `fermeture → réouverture → ProjetD` (protocole révisé, section 19) réussit intégralement** — critère ajouté après l'échec du premier smoke test (section 20), désormais obligatoire pour toute clôture de cette mission.
- Aucun chemin externe modifié dans le smoke test réel.
- `Character.name` strictement inchangé dans le smoke test réel.
- Les scénarios d'échec de la section 8 sont chacun couverts par au moins un test automatisé, avec vérification explicite de l'absence de corruption de `project.json`.
- **Un renommage bloqué par une fenêtre de l'Explorateur Windows ouverte dans un sous-dossier du projet affiche le message français actionnable (`QMessageBox.warning`, section 20), jamais le message technique générique** — à vérifier lors du smoke test final en laissant délibérément un sous-dossier ouvert dans l'Explorateur avant de tenter un renommage.

## 19. Protocole de smoke test manuel réel

**Révisé après échec du premier smoke test réel (section 20)** — la chaîne de renommages consécutifs `ProjetA → ProjetB → ProjetC` (sans redémarrage) et le cycle fermeture/réouverture suivi d'un nouveau renommage sont désormais **obligatoires**, avec au moins une image réellement présente sous `outputs/` tout au long du protocole — c'est précisément la combinaison qui a révélé le bug de la section 20.

À exécuter par l'architecte, sur un projet temporaire réel (Windows), après implémentation et suite automatisée verte :

1. Créer un nouveau projet temporaire, **ProjetA**.
2. Aller dans `Inference`, générer une image, l'Accepter — confirmer qu'elle apparaît dans `Images` avec un chemin sous `<dossier>\outputs\`. Cette image doit rester présente dans le Workspace pour tout le reste du protocole (ne pas la supprimer).
3. Importer, via `Datasets`/`Models`/`Workflows`/`LoRA`, au moins un fichier **externe** au projet (ex. depuis `Téléchargements` ou tout autre dossier hors du projet) — noter précisément le chemin choisi.
4. Menu **Fichier → Renommer le projet…**, renommer **ProjetA → ProjetB**, confirmer.
5. Vérifier immédiatement, **sans fermer l'application** :
   - le dossier sur disque porte le nouveau nom (Explorateur Windows) ;
   - l'ancien nom de dossier n'existe plus ;
   - `Dashboard` affiche le nouveau nom de projet ;
   - `Images` affiche toujours la vignette de l'image générée à l'étape 2 (chemin remappé, fichier physiquement présent au nouvel emplacement) ;
   - `Datasets`/`Models`/`Workflows`/`LoRA` affichent toujours normalement les entrées internes ;
   - la ressource externe importée à l'étape 3 est toujours référencée avec son chemin **identique, inchangé** ;
   - `Characters` affiche toujours le même nom de personnage qu'avant le renommage.
6. **Sans redémarrer AI Studio Toolkit**, renommer immédiatement à nouveau : **ProjetB → ProjetC**. Confirmer un succès identique à l'étape 5 (c'est exactement l'étape qui a échoué avec `WinError 5` lors du premier smoke test).
7. Sauvegarder explicitement (`Fichier → Sauvegarder` ou `Ctrl+S` si câblé) — confirmer l'absence d'erreur.
8. Fermer puis rouvrir le projet depuis le dossier **ProjetC** — confirmer que tout l'état vérifié à l'étape 5 est identique après ce cycle réel de fermeture/réouverture.
9. Renommer à nouveau : **ProjetC → ProjetD** — confirmer un succès (le premier smoke test a montré que fermer/rouvrir ne suffisait pas à garantir ce succès).
10. Tenter un second renommage vers un nom déjà utilisé par un autre dossier existant dans le même parent — confirmer un message d'erreur clair, sans aucun effet sur le projet actuel.
11. Tenter un renommage avec un nom invalide (ex. contenant `:` ou un espace final) — confirmer que le bouton "Renommer" reste désactivé, aucune tentative filesystem.

## 20. Bug découvert au premier smoke test réel — `WinError 5` sur un renommage consécutif

**Symptôme rapporté par l'architecte** : premier renommage d'un projet A réussi ; tentative de renommage immédiatement suivante du même projet A → `Could not rename ... [WinError 5] Accès refusé`. Rouvrir le projet A (fermeture/réouverture réelle) ne corrige pas le problème — la même erreur se reproduit. Un projet B distinct ne présente pas le problème, y compris pour un enchaînement de deux renommages consécutifs sur B. Chemin réel concerné : `J:\Downloads PC\ai toolkit essai 31` → `ai toolkit essai 21`.

### Diagnostic effectué (strictement READ-ONLY, aucune correction avant démonstration)

Quatre scripts de diagnostic exécutés dans l'environnement réel Windows du dépôt (jamais commités, scratchpad de session), testant chaque piste demandée par l'architecte avant toute conclusion :

1. **Hypothèse verrou Qt (`QPixmap`/`QIcon`)** : un `QPixmap` chargé depuis un fichier à l'intérieur du dossier, conservé vivant dans un `QListWidgetItem` (exactement le mécanisme de `ImagesPage._load_thumbnail_icon`/`_build_item`), puis tentative de renommage du dossier parent — **succès**, aucun verrou. Testé pour les 4 formats acceptés par `QFileDialog` (`PNG`, `BMP`, `JPG`, `WEBP`), avec rechargement du thumbnail depuis le nouveau chemin après un premier renommage puis nouvelle tentative de renommage (reproduisant exactement le cycle réel `WORKSPACE_RENAMED` → `ImagesPage.update_images()`), et avec cinq chargements répétés du même fichier sans jamais vider la liste — **succès dans tous les cas**. Hypothèse **infirmée**, pas seulement non confirmée.
2. **Hypothèse écriture atomique de `project.json`** : déjà couverte par les tests automatisés dédiés (section 14) — l'écriture atomique n'implique aucune ouverture de fichier au-delà de la durée du `with` bloc, temp file toujours nettoyé ou remplacé. Aucune trace d'un fichier temporaire résiduel observée après un renommage réel (vérifié physiquement : contenu du nouveau dossier après renommage, aucun fichier `.project_*.tmp` présent).
3. **Recherche exhaustive de ressources potentiellement non libérées dans le code de l'application** : aucun `open()` sans context manager (grep exhaustif sur `src/`) ; aucun `QFileSystemWatcher`/`FileHandler`/`logging.basicConfig` (le dossier `logs/` créé par `WorkspaceStorage` n'est en réalité jamais écrit par le code actuel) ; aucun `os.chdir()`/répertoire courant du processus jamais modifié ; aucun `iterdir()`/`scandir()`/`glob()`/`os.walk()` nulle part dans `src/` (un itérateur de répertoire partiellement consommé aurait pu, en théorie, retenir un handle Windows — écarté par absence totale d'utilisation). `datasets_page.py`/`models_page.py`/`lora_page.py`/`workflows_page.py` ne chargent aucune image/fichier (texte seul) — seuls `images_page.py`, `image_preview_dialog.py` et `inference_page.py` touchent des fichiers image, tous les trois couverts par le point 1.
4. **Reproduction bout-en-bout avec le vrai `WorkspaceManager.rename()`** (pas une réimplémentation) : `WorkspaceManager` + `DashboardPage` + `ImagesPage` + `InferencePage` câblés exactement comme `MainWindow` sur `WORKSPACE_RENAMED`, une vraie image PNG générée dans `outputs/` et enregistrée dans `Workspace.images`, **quatre renommages consécutifs dans la même session** (avec rafraîchissement réel des vignettes entre chacun) suivis d'un cycle fermeture/réouverture puis d'un cinquième renommage — **tous réussis**, y compris exécuté directement sous `J:\Downloads PC\` (le disque et le dossier réels du rapport de bug, testé spécifiquement pour écarter un comportement propre à ce volume) plutôt que sous un répertoire temporaire Windows standard.

### Résultat du diagnostic interne — non concluant à ce stade, honnêtement rapporté

**Aucune reproduction obtenue depuis le code applicatif seul.** Chaque piste interne explicitement listée par l'architecte (verrou Qt, écriture atomique, handle applicatif non libéré, spécificité du volume `J:`) a été testée activement et **infirmée par la preuve**, pas seulement non retenue par défaut. Les deux tests de régression automatisés ajoutés à la demande de l'architecte (`test_two_consecutive_renames_in_the_same_session`, `test_rename_still_works_after_a_close_and_reopen_cycle`, section 14) passent tous les deux — **conformément à l'avertissement explicite de l'architecte, ce succès n'a pas été interprété comme une preuve de résolution**, seulement comme la confirmation que le code applicatif, tel qu'il peut être exercé par ces tests, ne reproduit pas le symptôme.

### Diagnostic réel confirmé — Process Explorer (Sysinternals)

L'architecte a reproduit l'échec en conditions réelles et l'a diagnostiqué avec *Process Explorer* au moment exact où `WinError 5` se produisait. Résultat : **`explorer.exe` détient plusieurs handles ouverts sur des sous-dossiers du Workspace** (`images`, `outputs`, `models`, `training`, `datasets`, `logs`, `captions`, etc.) au moment de l'échec.

**Test discriminant, décisif** :
- dossier racine du projet ouvert dans l'Explorateur Windows, **sans** être positionné dans un sous-dossier → renommage **réussi** ;
- un **sous-dossier** du projet ouvert dans l'Explorateur Windows → renommage du dossier racine → **`WinError 5`** ;
- fermeture des fenêtres de l'Explorateur concernées → le même renommage **réussit**.

**Cause racine confirmée** : verrouillage externe par `explorer.exe` (une fenêtre de l'Explorateur Windows navigant dans un sous-dossier du projet), **et non** une corruption du Workspace, ni un défaut de libération de handle dans AI Studio Toolkit — cohérent avec l'intégralité du diagnostic interne ci-dessus, qui avait déjà infirmé toute cause applicative sans jamais parvenir à identifier la cause réelle faute d'accès à l'état Windows réel de l'architecte au moment de l'échec.

### Différence Projet A / Projet B — expliquée

Confirme l'hypothèse déjà formulée avant la confirmation Sysinternals : la différence entre A (échoue) et B (fonctionne) n'a jamais été une différence de **contenu** du Workspace, mais un pur effet de **navigation Explorateur** — l'architecte avait vraisemblablement une fenêtre de l'Explorateur Windows ouverte dans un sous-dossier de A (probablement `outputs/`, après y avoir vérifié l'image générée) au moment du second renommage, sans fenêtre équivalente ouverte dans un sous-dossier de B au moment de son propre test.

### Correction appliquée — traitement UX ciblé, aucun contournement du verrouillage Windows

Conformément à la demande explicite de l'architecte : **aucune tentative de terminer `explorer.exe`, fermer des handles externes, ou contourner le verrouillage Windows de quelque façon que ce soit.** Le mécanisme transactionnel/rollback (sections 7-8) est **conservé intégralement, sans aucune modification de sa logique** — seul le traitement de l'erreur en sortie change, pour distinguer ce cas précis et proposer un message actionnable.

**Nouveau type d'exception, à deux niveaux (couches Infrastructure puis Manager)** :
- `WorkspaceRenamePermissionError(WorkspaceStorageError)` (`workspace_storage.py`) — levée par `rename_folder()` uniquement quand `Path.rename()` échoue avec un `PermissionError` réel (Python mappe automatiquement `WinError 5` sur `PermissionError`, sous-classe d'`OSError` — détection native du langage, aucune inspection de code d'erreur ad hoc). Tout autre `OSError` continue de lever le `WorkspaceStorageError` générique, inchangé.
- `WorkspaceRenamePermissionError(WorkspaceManagerError)` (`workspace_manager.py`) — levée par `rename()` uniquement quand le renommage **initial** échoue avec cette erreur spécifique côté Storage ; `current_workspace` reste strictement intact (le renommage physique n'a jamais eu lieu), exactement comme tout autre échec de cette étape (section 7). Pour l'échec de **rollback** après une sauvegarde ratée (cas plus rare et plus sévère, section 8), le message technique détaillé existant est **conservé intégralement** (la récupération manuelle décrite y reste nécessaire) — un indice supplémentaire est simplement ajouté au texte lorsque ce rollback échoue lui-même pour la même cause (`isinstance(rollback_exc, WorkspaceRenamePermissionError)`), sans jamais remplacer les instructions de récupération par le message simplifié.
- `MainWindow.rename_project()` capte `WorkspaceRenamePermissionError` **avant** le `WorkspaceManagerError` générique et affiche un `QMessageBox.warning` dédié, en français, avec le texte exact demandé (dossier du projet ou sous-dossier probablement utilisé par une autre application, fermer les fenêtres de l'Explorateur Windows ouvertes dans le projet ou ses sous-dossiers, réessayer). **Aucun autre type d'erreur n'est concerné** — tout `WorkspaceManagerError` qui n'est pas cette sous-classe précise continue de tomber dans le `QMessageBox.critical` générique existant, inchangé (vérifié par test dédié : une erreur "dossier cible déjà existant" reste sur `.critical`, jamais reclassée).

Choix délibéré de `QMessageBox.warning` plutôt que `.critical` pour ce cas précis : contrairement aux autres échecs de `rename()` (dossier cible déjà pris, disque plein), celui-ci est un blocage externe temporaire et directement actionnable par l'utilisateur (fermer une fenêtre), pas une erreur technique de l'application — cohérent avec l'usage déjà établi de `.warning` ailleurs dans le projet pour des situations récupérables (ex. `CharactersPage`).

### Fichiers modifiés pour ce correctif

- `src/infrastructure/storage/workspace_storage.py` — `WorkspaceRenamePermissionError`, `rename_folder()` distingue désormais `PermissionError` du reste des `OSError`.
- `src/managers/workspace_manager.py` — `WorkspaceRenamePermissionError` (niveau Manager), `rename()` propage le type spécifique pour l'échec initial, enrichit (sans le remplacer) le message détaillé de rollback quand celui-ci échoue pour la même cause.
- `src/ui/main_window.py` — `rename_project()` capte le nouveau type en premier, affiche le message français dédié via `QMessageBox.warning`.
- `tests/integration/test_workspace_roundtrip.py` — 7 nouveaux tests (`WorkspaceRenameTest` : 4 ; nouvelle classe `WorkspaceStorageRenameFolderErrorTest` : 3).
- `tests/integration/test_main_window_rename_project.py` — 2 nouveaux tests.

### Résultat

**452/452 tests verts** (443 précédents + 9 nouveaux). Suites ciblées (`test_workspace_roundtrip.py` + `test_main_window_rename_project.py`) : 41/41.

### Smoke test final réel — PASS

Exécuté par l'architecte après redémarrage d'AI Studio Toolkit avec le code corrigé (le premier essai du correctif avait affiché le message technique générique, non le message français — confirmé n'être qu'un artefact de ne pas avoir redémarré l'application après la modification du code, pas un défaut du correctif). Résultat, protocole complet (section 19, y compris la chaîne `ProjetA → ProjetB → ProjetC` sans redémarrage puis fermeture/réouverture/`ProjetD`, avec une image réelle sous `outputs/`) :

- sous-dossier du projet ouvert dans l'Explorateur Windows → renommage refusé proprement (aucun crash, aucun état incohérent) ;
- la boîte **« Renommage impossible »** apparaît, avec le message français attendu (dossier/sous-dossier probablement utilisé par une autre application, mention explicite de l'Explorateur Windows) ;
- fermeture de la fenêtre Explorateur concernée puis nouvelle tentative → renommage réussi immédiatement, sans redémarrage de l'application ;
- la chaîne de renommages consécutifs et le cycle fermeture/réouverture → renommage supplémentaire, tous confirmés réussis.

**PASS.**

## Commit correspondant

`7a532608722e8a2959062c4a71ce7dabfbb4bfe1` — `feat: add project folder rename`.

## Tag / release correspondant

`v0.2-mission027` (annoté, message `Mission 027 - Project Folder Rename`), ciblant exactement `7a532608722e8a2959062c4a71ce7dabfbb4bfe1`. GitHub Release `v0.2-mission027` **publiée** — confirmée par l'architecte et vérifiée indépendamment (page de Release publique accessible, non marquée draft/pre-release, titre "v0.2-Mission027 - Project Folder Rename", cible exacte confirmée).

## État final

**Implémentation, suite automatisée (452/452) et smoke test manuel réel complet validés — PASS.** Le mécanisme de renommage de projet (`WorkspaceManager.rename()`, ordonnancement transactionnel "commit en dernier", rollback filesystem best-effort en cas d'échec de sauvegarde après renommage réussi, écriture atomique de `project.json`) fonctionne comme spécifié, y compris pour des renommages consécutifs dans la même session et après un cycle fermeture/réouverture. Le bug de renommages consécutifs rencontré au premier smoke test réel a été **résolu par un diagnostic réel confirmé** (Process Explorer — `explorer.exe` détient des handles sur les sous-dossiers du projet lorsqu'une fenêtre de l'Explorateur y navigue, un verrouillage Windows externe et légitime, jamais une corruption du Workspace ni un défaut de libération de handle applicatif) et un **traitement UX ciblé** (`WorkspaceRenamePermissionError`, message français actionnable) — **sans jamais contourner le verrouillage Windows** ni tenter de fermer un handle/processus externe. **Clôture Git et publication entièrement effectuées** — commit fonctionnel `7a532608722e8a2959062c4a71ce7dabfbb4bfe1` (`feat: add project folder rename`), tag `v0.2-mission027`, GitHub Release publiée.
