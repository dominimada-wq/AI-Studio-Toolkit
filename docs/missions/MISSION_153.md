# Mission 153 — Roll Back Workspace Materialization Failures Before Publication

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `create_workspace_with_default_character()` (`src/managers/workspace_lifecycle.py`) ne roulait en arrière que l'échec du *second* point de défaillance possible (`ensure_default_character()`, qui écrit le Character par défaut) — un échec du *premier* point (`create_without_publishing()`, qui crée le dossier/sous-dossiers et écrit le tout premier `project.json`) laissait un dossier Workspace partiellement matérialisé sur disque, sans aucune tentative de nettoyage, découvert et reproduit empiriquement par l'audit global READ-ONLY post-Mission 152. Corrigé en englobant les deux points de défaillance dans le même bloc `try/except` déjà existant et déjà testé — aucune nouvelle abstraction, aucun nouveau type d'exception, aucune branche spécifique par point d'échec. **+3 tests nets** (2891 → 2894 tests collectés), suite complète confirmée **2894/2894, 0 échoué** — voir §7 pour le détail.

## 1. Root cause

`create_workspace_with_default_character()` appelait `workspace_manager.create_without_publishing(folder)` **avant** le bloc `try/except WorkspaceManagerError` qui gère le rollback filesystem — ce bloc n'englobait que `character_manager.ensure_default_character()`. `create_without_publishing()` (`src/managers/workspace_manager.py:136-162`) exécute elle-même, dans son propre `try` interne, `WorkspaceStorage.create_directories(folder)` (création du dossier racine + des 12 sous-dossiers) puis le tout premier `WorkspaceStorage.save(folder, workspace.to_dict())` (écriture initiale de `project.json`, un Workspace sans Character) — toute `WorkspaceStorageError` levée par l'un ou l'autre est re-levée en `WorkspaceManagerError`, mais comme cet appel se trouvait hors du bloc de rollback du fichier appelant, cette exception remontait telle quelle, sans jamais déclencher `WorkspaceStorage.delete_folder(folder)`.

## 2. Séquence actuelle (avant cette mission) — deux points de défaillance à traitement asymétrique

```
create_without_publishing(folder)          # HORS du try/except — AUCUN rollback si échec ici
  create_directories(folder)                 # mkdir racine + 12 sous-dossiers
  save(folder, workspace.to_dict())          # 1er save : project.json, 0 Character
  current_workspace = workspace              # jamais atteint si l'un des deux appels ci-dessus échoue
try:
    ensure_default_character()               # DANS le try/except — rollback déjà correct si échec ici
        CharacterManager.create(name)          # append Domain + 2e save() ; rollback Domain interne si save() échoue
except WorkspaceManagerError:
    current_workspace = previous_workspace
    delete_folder(folder)                    # jamais atteint pour le 1er point d'échec
    raise (message enrichi si delete_folder échoue aussi)
publish_created()
```

Au moment du second échec, `create_without_publishing()` a déjà entièrement réussi : dossier + sous-dossiers + `project.json` existent, et `current_workspace` a déjà été réaffecté — le rollback existant restaure alors un état réellement changé. Au moment du premier échec, rien de tout cela n'est encore garanti cohérent, et `current_workspace` n'a jamais été réaffecté (l'affectation dans `create_without_publishing()` intervient après son propre `try/except`) — mais aucun nettoyage n'était tenté pour ce cas.

## 3. Conséquence réelle (séquence de bug, confirmée pendant l'audit post-M152)

1. `MainWindow.new_project()` appelle `create_workspace_with_default_character(...)` avec un `folder` garanti neuf (voir §6).
2. `create_directories(folder)` réussit (dossier + sous-dossiers créés).
3. Le tout premier `WorkspaceStorage.save()` échoue (disque plein, permission refusée juste après la création du dossier, verrou antivirus, etc.).
4. `WorkspaceManagerError` remonte immédiatement, sans passer par aucun bloc de nettoyage.
5. `MainWindow.new_project()` affiche `QMessageBox.critical(self, "Erreur", str(exc))` — un message brut (`"Could not create workspace folders in {folder}"` ou `"Could not write project.json in {folder}"`), sans aucune mention qu'un dossier a pu être laissé sur disque.
6. Le dossier (racine + tout ou partie des 12 sous-dossiers) reste orphelin, sans `project.json`, indéfiniment — jusqu'à suppression manuelle par l'utilisateur.

Confirmé également pendant l'audit : deux tests déjà existants (`test_character_creation_failure_raises_workspace_manager_error`, `test_workspace_created_is_never_published_on_failure`) patchaient déjà `WorkspaceStorage.save` sans compteur — déclenchant donc déjà cet échec exact — sans jamais vérifier l'état du dossier après coup. Le bug était donc déjà exercé par la suite de tests existante, seulement jamais détecté faute d'assertion sur le filesystem.

## 4. Contrat retenu (invariant transactionnel)

**Avant `publish_created()`, toute `WorkspaceManagerError` survenant pendant `create_without_publishing(folder)` (y compris `create_directories()` ou le premier `save()`) ou pendant `ensure_default_character()` (incluant le second `save()`) doit passer par le même mécanisme de rollback filesystem, sans distinction de branche entre les deux points d'échec :**

- tenter `WorkspaceStorage.delete_folder(folder)` (best-effort, idempotente) ;
- restaurer `current_workspace` à sa valeur d'avant l'appel (`previous_workspace`) — un no-op correct pour le premier point d'échec (jamais réellement muté à ce stade), une vraie restauration pour le second (réellement changé par un `create_without_publishing()` déjà réussi) ;
- ne jamais publier `WORKSPACE_CREATED` dans les deux cas ;
- si `delete_folder()` échoue également : ne jamais remplacer la cause primaire par l'échec du cleanup — la chaîner comme `__cause__` de la cause primaire (`from exc`), et signaler explicitement dans le message l'orphelin potentiel, son chemin exact, et la nécessité d'une suppression manuelle.

Un seul bloc `except WorkspaceManagerError`, commun aux deux points d'échec, suffit — aucune branche conditionnelle par point d'échec n'est nécessaire ni introduite.

## 5. Correction appliquée

Dans `src/managers/workspace_lifecycle.py`, `workspace_manager.create_without_publishing(folder)` a été déplacé **à l'intérieur** du `try` déjà existant, immédiatement avant `character_manager.ensure_default_character()` :

```python
previous_workspace = workspace_manager.current_workspace

try:
    workspace = workspace_manager.create_without_publishing(folder)
    character_manager.ensure_default_character()
except WorkspaceManagerError as exc:
    workspace_manager.current_workspace = previous_workspace
    try:
        WorkspaceStorage.delete_folder(folder)
    except WorkspaceStorageError:
        raise WorkspaceManagerError(
            f"{exc} Additionally, the incomplete project folder could not be "
            f"cleaned up and remains on disk at {folder}. Manual recovery "
            f"required: delete {folder} yourself once the underlying issue is "
            f"resolved."
        ) from exc
    raise WorkspaceManagerError(str(exc)) from exc

workspace_manager.publish_created()
return workspace
```

Le corps du bloc `except` (restauration, nettoyage, message enrichi, chaînage de cause) est resté **strictement inchangé** — aucune nouvelle abstraction, aucun nouveau type d'exception, aucune branche `if`/`elif` par point d'échec. Seule la portée du `try` a été élargie.

## 6. Précondition externe de sûreté — `delete_folder(folder)` non défensif par lui-même

`WorkspaceStorage.delete_folder(folder)` fait un `shutil.rmtree(path)` inconditionnel sur tout ce qui existe sous `folder`. Cette opération n'est sûre que parce que `folder` est garanti **neuf** (n'existait pas avant cet appel) — sans quoi elle détruirait du contenu étranger préexistant. Cette garantie est vérifiée par lecture directe du code, pas supposée :

- `NewProjectDialog._compute_target_path()`/`_on_accept_clicked()` (`src/ui/dialogs/new_project_dialog.py`) rejette explicitement (`TARGET_EXISTS_MESSAGE`) tout `target_path` qui existe déjà, revérifié au moment exact du clic « Créer » (pas seulement à la dernière frappe/sélection) ;
- `create_workspace_with_default_character()` n'a, à ce jour, **qu'un seul appelant en production** : `MainWindow.new_project()` (`src/ui/main_window.py:615`), confirmé par recherche exhaustive dans `src/`.

**Cette mission ne modifie ni ne déplace cette validation** — elle reste dans `NewProjectDialog`, hors périmètre de `workspace_lifecycle.py`. Le docstring de `create_workspace_with_default_character()` documente désormais explicitement cette précondition externe, afin qu'un futur appelant ne puisse pas ignorer cette hypothèse de sûreté : réutiliser cette fonction contre un dossier pouvant déjà contenir du contenu non lié rendrait ce nettoyage destructif — la fonction elle-même ne s'en défend pas.

**Divergence documentaire relevée pour traçabilité (non traitée par cette mission)** : le docstring de `WorkspaceStorage.delete_folder()` (`src/infrastructure/storage/workspace_storage.py:346-363`) la décrit comme utilisée « only after the corresponding Domain mutation is already durably persisted (never as a rollback step) » — description qui reflète son usage d'origine (Mission 075, suppression physique définitive d'une entité déjà retirée du Domain). `workspace_lifecycle.py` l'utilise déjà comme mécanisme de rollback depuis Mission 137, pour le second point d'échec — cette mission étend simplement le même usage déjà établi au premier point d'échec, sans créer de nouveau précédent contradictoire. Le docstring lui-même n'a pas été mis à jour, cette mission n'ayant pas vocation à une régularisation documentaire de ce fichier.

## 7. Tests

**+3 tests nets**, ajoutés à `WorkspaceLifecycleFailureTest` (`tests/integration/test_workspace_lifecycle.py`), verrouillant précisément le contrat du §4 pour le premier point d'échec — mirroir des tests déjà existants pour le second point, sans les dupliquer inutilement :

1. `test_no_zombie_workspace_folder_survives_a_first_save_failure` — échec du premier `save()` → `folder` n'existe plus après l'exception.
2. `test_current_workspace_preserved_after_a_first_save_failure` — un Workspace précédemment ouvert (objet réel, pas seulement `None`) survit intact à une tentative échouée de création d'un second Workspace sur ce même point d'échec.
3. `test_first_save_primary_cause_is_preserved_when_cleanup_also_fails` — échec du premier `save()` **et** échec du `delete_folder()` → message contenant la cause primaire (« disk full »), la mention de l'orphelin (« cleaned up »), le chemin exact, et `__cause__` pointant vers la `WorkspaceManagerError` primaire (jamais vers l'échec du cleanup).

**Non-doublons délibérés, documentés** :
- Un seul test couvre la préservation de `current_workspace` (point 2), avec un Workspace précédent réel plutôt que `None` — cas strictement plus fort, puisqu'il prouve une préservation effective plutôt qu'une absence de mutation trivialement vraie ; le cas `None` symétrique existant pour le second point d'échec (`test_current_workspace_restored_to_none_when_none_before`) n'a pas été dupliqué pour le premier point, la logique de restauration étant strictement identique (même ligne de code, même bloc `except`) pour les deux points d'échec.
- **Aucun test dédié à un échec de `create_directories()` distinct d'un échec de `save()`** : les deux surviennent dans le même `try` interne de `create_without_publishing()` et sont re-levés de façon strictement identique (`WorkspaceManagerError` générique) — depuis `workspace_lifecycle.py`, ce sont exactement le même code path, le même bloc `except`, exerçant les mêmes lignes. Un test spécifique à `create_directories()` n'apporterait aucune garantie distincte sur le fichier sous test ; il prouverait seulement qu'un second appelant interne de `WorkspaceStorage` peut aussi lever `WorkspaceStorageError`, déjà implicite dans la mécanique d'exception Python et hors périmètre de cette mission (la robustesse propre de `create_directories()` relève de la suite de tests de `WorkspaceStorage`, non modifiée ici).
- Les invariants Domain (aucun Character créé) et EventBus (`WORKSPACE_CREATED` jamais publié) pour ce premier point d'échec sont déjà couverts par les deux tests existants qui, sans le savoir, déclenchaient déjà ce chemin (`test_character_creation_failure_raises_workspace_manager_error`, `test_workspace_created_is_never_published_on_failure`) — non dupliqués.

**Résultats** :
- `tests/integration/test_workspace_lifecycle.py` complet : **17/17 passés** (14 préexistants + 3 nouveaux, 0.364s).
- Non-régression ciblée : `test_workspace_roundtrip.py` + `test_character_roundtrip.py` + `test_main_window_new_project.py` : **230/230 passés** (19.244s).
- **Suite complète : 2894 collectés/2894 passés, 0 échoué** (327.900s). Équation : 2891 (baseline post-M152) + 3 nets ajoutés par Mission 153 = **2894**, cohérent. Durée cohérente avec la baseline post-M152 (334.491s) — un run intermédiaire, exécuté pendant que 5 agents d'audit tournaient encore en arrière-plan sur la même machine, avait semblé anormalement lent/bloqué (arrêté manuellement à ~34% de progression) ; diagnostiqué comme un ralentissement transitoire lié à la charge machine (aucun processus orphelin retrouvé, aucun test réellement bloqué — `test_inference_page.py` et `test_forge_lifecycle_manager.py` reproduits isolément sans aucune erreur), sans aucun rapport avec cette mission, non traité ici (hors périmètre).

## 8. Non-régression du second point d'échec

Tous les tests existants du second point d'échec (`test_character_creation_failure_raises_workspace_manager_error`, `test_workspace_created_is_never_published_on_failure`, `test_filesystem_is_cleaned_up_on_failure`, `test_domain_has_no_character_left_after_failure`, `test_current_workspace_restored_to_none_when_none_before`, `test_current_workspace_restored_to_the_previous_one_when_it_existed`, `test_no_zombie_workspace_folder_survives_a_failure`, `test_primary_cause_is_preserved_when_cleanup_also_fails`, `test_cleanup_failure_is_also_diagnosed_without_replacing_the_primary_cause`, `test_invariant_does_not_depend_on_any_eventbus_exception`) repassent verts **sans aucune modification de leur propre code** — `_fail_on_second_save()` continue de cibler exactement le second appel à `WorkspaceStorage.save()` via son compteur, non affecté par l'élargissement de la portée du `try`.

## 9. Périmètre volontairement limité (non-goals confirmés)

- Aucune modification de `WorkspaceManager.create_without_publishing()`/`create()`/`save()` — leur contrat, leurs exceptions, leur ordre d'opérations restent strictement inchangés.
- Aucune modification de `CharacterManager.ensure_default_character()`/`create()` — le rollback Domain interne de Mission 072 reste inchangé.
- Aucune modification de `WorkspaceStorage.create_directories()`/`save()`/`delete_folder()` — aucune nouvelle sémantique filesystem introduite.
- Aucune validation ajoutée dans `NewProjectDialog` ni ailleurs pour re-garantir que `folder` est neuf — la précondition existante suffit et est désormais documentée, pas dupliquée par une nouvelle garde redondante.
- Aucun refactor architectural déplaçant la responsabilité de validation du dossier cible.
- Aucune autre dette découverte par l'audit global post-Mission 152 (fuite `OSError` via `_find_existing_alias()`, suppression LoRA pendant génération active, `ApplicationSettingsStorageError` sans resync, dettes Training/OneTrainer) n'est traitée par cette mission — hors périmètre, document mais non corrigé.

## 10. Clôture Git

Commit fonctionnel : `8913f15214d06f51962dde664d9d4c43fd3b2cc0` (« Guard workspace creation rollback », 3 fichiers : `src/managers/workspace_lifecycle.py`, `tests/integration/test_workspace_lifecycle.py`, `docs/missions/MISSION_153.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission153` (objet `b5a4600c33965f7da2c9f44804ef74d6204292d6`, cible `8913f15214d06f51962dde664d9d4c43fd3b2cc0`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission153 — Guard Workspace Creation Rollback` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2894/2894, 0 échoué** (327.900s). Le tag `v0.2-mission152` (`dd6b4a3c34b755c9acab68e181414668917028e0` → `0148986472bc9d18d3c1bb3f7645c2c7d15531a1`) reste inchangé.
