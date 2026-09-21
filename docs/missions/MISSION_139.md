# Mission 139 — Isolate Materialized Training Concept Per Job

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente de validation externe.** L'audit Mission 138 (Resume) avait établi que le dossier concept matérialisé qu'OneTrainer lit réellement est partagé au niveau `Training`, jamais isolé par `TrainingJob` — un défaut d'isolation filesystem indépendant du sujet Resume, mais qui en est aussi un bloqueur direct. Cette mission corrige ce défaut : chaque `TrainingJob` possède désormais son propre snapshot concept, copié au moment de sa création, jamais partagé ni rematérialisable par un autre Job du même Training. Aucune fonctionnalité de reprise (Resume) n'est implémentée ici.

## 1. Problème

`TrainingManager._materialize_concept()` matérialise le Dataset (images + légendes `.txt`) dans `training/<training_id>/concept/` — un chemin **au niveau Training**, pas au niveau Job. `create_job()` fige une copie de la configuration OneTrainer pour chaque Job, mais reportait jusqu'ici tel quel le chemin (chaîne) de ce dossier partagé dans `concepts[0]["path"]`, sans jamais le copier. Puisque `prepare_onetrainer_config()` (donc `_materialize_concept()`) est appelée **inconditionnellement à chaque clic sur Démarrer, pour n'importe quel Job du Training** (`TrainingPage.start_training()`), un second Job du même Training pouvait silencieusement réécrire les données qu'un premier Job, déjà créé, croyait figées — violant l'isolation `1 TrainingJob → 1 environnement d'exécution isolé` déjà appliquée à `output`/`workspace`/`cache`/`debug` depuis Mission 100.

## 2. Preuve (vérifiée dans le code réel avant toute modification)

- **Emplacement du concept partagé** : `<workspace_root>/training/<training_id>/concept/` — `_training_folder()` + `_CONCEPT_SUBFOLDER_NAME` (`training_manager.py:695-696,111`).
- **Emplacement du `workspace_dir` du Job** : `<workspace_root>/training/<training_id>/jobs/<job_id>/workspace/` — `job_paths()` (`training_manager.py:960-979`), un dossier frère de `output`/`cache`/`debug`, tous déjà isolés par `job_id`.
- **Ordre réel** : `prepare_onetrainer_config()` (appelle `_materialize_concept()` puis écrit `training/<id>/onetrainer_config.json`) → `create_job()` (relit ce fichier, fige une copie dans `jobs/<job_id>/onetrainer_config.json`, override seulement `output_model_destination`/`workspace_dir`/`cache_dir`/`debug_dir`) → lancement du process. `create_job()` ne crée jamais de nouvelle matérialisation lui-même — il ne fait, avant cette mission, que référencer celle déjà écrite par le dernier Prepare.
- **Endroit exact où le chemin concept était fixé dans la config figée** : nulle part avant cette mission — `create_job()` ne touchait jamais `config["concepts"]`, la valeur restait celle écrite par `build_training_config()` (`src/engines/onetrainer_config.py:894-899`, clé `"concepts": [{"name": ..., "path": ...}]`, liste à un seul élément), c'est-à-dire le chemin du dossier Training-scope partagé.
- **Propriétaire du cleanup** : aucun. `TrainingManager.delete(training_id)` est une mutation Domain-only, confirmée sans aucun accès filesystem (`training_manager.py:1199-1201` — dette distincte, déjà documentée dans `MISSION_138.md` §20, non traitée ici).

## 3. Invariant cible (atteint)

Pour deux Jobs A et B issus du même Training : `job_paths(training_id, A).concept_dir != job_paths(training_id, B).concept_dir`, et le contenu du dossier concept de A n'est jamais modifié par la création, la préparation ou le lancement de B, ni par un changement ultérieur du Dataset source.

## 4. Architecture retenue

Exactement le même mécanisme d'isolation que `workspace_dir`/`cache_dir`/`debug_dir` (Mission 100) — un nouveau sous-dossier owned par le Job, sous son propre `job_folder` :

- Nouvelle constante `_JOB_CONCEPT_SUBFOLDER_NAME = "concept"` (`training_manager.py`), au même endroit que les autres constantes `_JOB_*_SUBFOLDER_NAME`.
- Nouveau champ `TrainingJobPaths.concept_dir: str`, calculé par `job_paths()` comme `job_folder / _JOB_CONCEPT_SUBFOLDER_NAME` — chemin final réel : `training/<training_id>/jobs/<job_id>/concept/`.
- `create_job()` copie désormais, fichier par fichier (`shutil.copy2`, même primitive que `_materialize_concept()` elle-même), le contenu du dossier concept Training-scope (déjà matérialisé par le Prepare requis en amont) vers ce nouveau `concept_dir`, puis réécrit `config["concepts"][0]["path"] = paths.concept_dir` dans la copie figée avant de l'écrire sur disque.
- Aucune nouvelle représentation Dataset, aucun fichier supplémentaire copié — exactement les images et les sidecars `.txt` déjà présents dans le dossier source, rien d'autre (confirmé : `_materialize_concept()` n'écrit aucun autre type de fichier dans ce dossier).

## 5. Lifecycle filesystem

- **Immutabilité pratique** : une fois `create_job()` terminé avec succès, plus rien ne réécrit son `concept_dir` — seul `_materialize_concept()` (Prepare) touche le dossier Training-scope partagé, jamais un dossier Job-scope. Aucun système de permissions/ACL introduit — l'isolation est architecturale (deux chemins distincts), pas un verrou filesystem.
- **Cleanup des 4 dossiers historiques** (`output`/`workspace`/`cache`/`debug`) : inchangé, aucun mécanisme nouveau ajouté — ils conservent la convention déjà en vigueur avant cette mission (« additive, per-job-id folder, harmless to leave orphaned if save() subsequently fails »). Une éventuelle faiblesse analogue sur ces dossiers historiques est documentée comme **dette découverte, non traitée** — voir §14.
- **Échec de matérialisation du concept snapshot (copie vers le Job) — correction demandée en revue ChatGPT, implémentée** : contrairement aux 4 dossiers historiques, le `concept_dir` du Job est un artefact introduit par cette mission et ne bénéficie plus de la même tolérance à l'orphelinat. La création (`mkdir`) et la copie du concept vers `concept_dir` sont désormais isolées dans leur propre bloc `try/except OSError`, exécuté **avant** la création des 4 autres dossiers et avant toute construction/persistance du `TrainingJob`. Sur échec :
  1. nettoyage best-effort de `paths.concept_dir` uniquement, via `WorkspaceStorage.delete_folder()` — la même primitive déjà utilisée par `_materialize_concept()` elle-même, vérifiée adaptée (suppression récursive générique, no-op si absent, propage une vraie erreur si le nettoyage échoue réellement, jamais de `shutil.rmtree(ignore_errors=True)`) ;
  2. **aucun autre dossier n'est jamais supprimé** — ni `jobs/<job_id>/` lui-même, ni les 4 dossiers historiques, ni a fortiori le dossier concept Training-scope partagé (jamais référencé par ce nettoyage) ;
  3. `TrainingJobError` est levée avec la cause primaire préservée (`raise ... from exc`) — aucun `TrainingJob` n'est jamais construit ni persisté sur ce chemin ;
  4. si le nettoyage lui-même échoue (`WorkspaceStorageError`), le message diagnostique les deux échecs (primaire + nettoyage) sans jamais remplacer la cause primaire — même idiome exact que `_materialize_concept()`/`LoRALibraryManager.import_lora()` (mention générique de l'échec de nettoyage et du chemin résiduel, jamais le texte de l'exception de nettoyage elle-même — convention déjà établie dans ce fichier et dans `lora_library_manager.py`) ; `ctx.exception.__cause__` reste dans tous les cas l'exception primaire d'origine, jamais celle du nettoyage.

## 6. Config OneTrainer

Le point critique demandé — vérifié par test dédié, pas seulement par l'existence de deux dossiers distincts : `test_job_config_snapshot_references_its_own_concept_path_not_the_shared_one` relit le JSON réellement écrit sur disque (`job.config_snapshot_path`) et vérifie `snapshot["concepts"][0]["path"] == paths.concept_dir` — pour chaque Job indépendamment.

## 7. Concurrence

Analysé : aucun garde-fou Domain n'empêche aujourd'hui de créer/démarrer deux Jobs du même Training en succession rapide (le seul garde existant, `_active_runner is not None`, est en mémoire et local à l'instance de `TrainingPage` — inchangé par cette mission, hors périmètre). Cette mission ne construit aucun framework de concurrence, conformément à l'autorisation. **Aucune autre collision filesystem découverte** : chaque `create_job()` génère un `job_id` UUID neuf et donc un `concept_dir` neuf et unique — l'isolation par dossier élimine structurellement la seule collision identifiée par l'audit Mission 138 (deux Jobs du même Training se marchant sur le même dossier concept), sans qu'aucune autre collision ne soit apparue pendant l'implémentation ou les tests.

## 8. Compatibilité

- Aucune modification de `Training`/`TrainingJob` Domain — `concept_dir` est une valeur purement calculée par `job_paths()` (Manager), jamais persistée sur l'objet Domain, exactement comme `workspace_dir`/`cache_dir`/`debug_dir` déjà aujourd'hui.
- Aucune modification de la machine à états, d'EventBus, de l'UI, de la Central LoRA Library, d'Inference, du mécanisme de backup OneTrainer, de Resume, ou de la gestion PID/process.
- `src/engines/onetrainer_config.py` (`build_training_config()`) **non modifié** — la valeur `concept_path` qu'il reçoit reste celle du dossier Training-scope ; seule la copie figée que `create_job()` écrit ensuite sur disque diffère.
- Compatibilité `project.json` : aucun champ Domain ajouté, donc aucune question de rétrocompatibilité ne se pose — un `project.json` existant continue de se charger sans aucun changement de comportement pour tout Job déjà créé avant cette mission (son `config_snapshot_path` déjà écrit sur disque n'est jamais retouché rétroactivement).

## 9. Tests

**Fichiers modifiés** :
- `tests/integration/test_training_roundtrip.py` — 6 tests nets ajoutés dans `TrainingManagerCreateJobTest`.
- `tests/integration/test_training_job_runner.py` — 2 constructions existantes de `TrainingJobPaths(...)` complétées avec le nouveau champ `concept_dir` (aucune assertion modifiée, aucun comportement testé n'a changé).

**Nouveaux tests** (`TrainingManagerCreateJobTest`) :
1. `test_job_gets_its_own_concept_snapshot_folder_distinct_from_the_shared_one` — le `concept_dir` du Job diffère du dossier Training-scope partagé.
2. `test_two_jobs_of_the_same_training_never_share_a_concept_path` — deux Jobs successifs du même Training obtiennent des `concept_dir` distincts.
3. `test_job_concept_snapshot_contains_the_image_and_caption_sidecar` — le snapshot du Job contient bien l'image et le sidecar `.txt` (contenu du trigger_word vérifié).
4. `test_job_config_snapshot_references_its_own_concept_path_not_the_shared_one` — la config OneTrainer réellement sérialisée sur disque pour ce Job référence son propre chemin, pas le partagé.
5. `test_second_job_creation_never_mutates_the_first_jobs_concept_snapshot` — **preuve principale de la mission** : Job A créé, son snapshot capturé (fichiers + contenu de la légende) ; le Dataset est modifié (image ajoutée) et `trigger_word` changé ; Job B créé après un nouveau Prepare ; vérifie que le snapshot de A est resté strictement identique (mêmes fichiers, même contenu), que B reflète le nouvel état (2 images), et que la config figée de chacun pointe toujours vers son propre `concept_dir`.
6. `test_create_job_raises_persists_no_job_and_cleans_up_the_partial_concept_snapshot` (renommé depuis la version initiale de cette mission pour refléter le comportement corrigé) — une copie qui échoue (`shutil.copy2` patché pour lever `OSError("disk full")`) fait lever `TrainingJobError` (cause primaire visible dans le message), ne laisse aucun Job dans `training.jobs`, et **vérifie qu'aucun sous-dossier de `jobs/` ne conserve un `concept/` résiduel** — sans dépendre du `job_id` généré en interne (parcours de tous les sous-dossiers de `jobs/`, s'il en existe).
7. `test_create_job_cleanup_failure_is_diagnosed_without_replacing_the_primary_cause` (ajouté en revue) — double échec simulé (`shutil.copy2` **et** `WorkspaceStorage.delete_folder` patchés pour échouer simultanément) : le message diagnostique contient à la fois la cause primaire (« disk full ») et la mention générique de l'échec de nettoyage (« could not be cleaned up »), et `ctx.exception.__cause__` reste strictement l'exception primaire d'origine (jamais celle du nettoyage).

**Résultats réels** :
- Suite ciblée `TrainingManagerCreateJobTest` : **19/19** (12 existants inchangés + 7 nouveaux — 6 de la version initiale + 1 test de double échec ajouté en revue).
- `test_training_job_runner.py` complet : **12/12** (inchangé).
- `test_training_roundtrip.py` complet : **368/368**.
- `test_onetrainer_config.py` complet : **169/169** (fichier non modifié, non-régression confirmée).
- **Suite complète (après correction du cleanup)** : première exécution **2779 tests collectés, 1 échec** — isolé à `test_forge_lifecycle_manager.py::ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest.test_readiness_timeout_with_taskkill_success_confirms_cleanup` (fichier de gestion de processus réel Forge, aucun rapport avec les fichiers modifiés par cette mission). Rapporté honnêtement puis reproduit en isolation : le fichier complet (48/48) et le test isolé (3/3) sont passés systématiquement au vert — confirmé comme flake de timing/process réel préexistant, pas une régression introduite par M139. **Seconde équation** : 2772 (clôture Mission 137) + 6 (version initiale M139) + 1 (test de double échec ajouté en revue) = **2779**, cohérent avec le total collecté. Le seul autre élément visible dans les logs (`_refresh_lora_trigger_widgets`/`QLabel.setText(MagicMock)`) reste l'artefact de mock déjà identifié comme non-régression par l'audit post-Mission 137, sans rapport avec cette mission.

## 10. Smoke

Aucun smoke manuel — conformément à l'autorisation, la config OneTrainer réellement sérialisée sur disque est vérifiée directement par test automatisé (`test_job_config_snapshot_references_its_own_concept_path_not_the_shared_one`), aucun entraînement GPU réel requis pour valider ce périmètre.

## 11. Fichiers modifiés

**Production (1 fichier)** :
- `src/managers/training_manager.py` — nouvelle constante `_JOB_CONCEPT_SUBFOLDER_NAME`, nouveau champ `TrainingJobPaths.concept_dir`, `job_paths()` étendu, `create_job()` copie le concept et réécrit `concepts[0]["path"]` dans la config figée, avec cleanup-then-raise dédié en cas d'échec de cette copie (correction de revue, §5).

**Tests (2 fichiers)** :
- `tests/integration/test_training_roundtrip.py` — 7 tests nets ajoutés (6 de la version initiale + 1 test de double échec ajouté en revue).
- `tests/integration/test_training_job_runner.py` — 2 constructions `TrainingJobPaths(...)` complétées (champ obligatoire ajouté), aucune assertion modifiée.

**Documentation (1 fichier, nouveau)** :
- `docs/missions/MISSION_139.md` (ce document).

## 12. Écarts par rapport au design initial

Un écart corrigé suite à la revue ChatGPT (voir §5) : la version initiale de cette mission laissait le `concept_dir` orphelin sur échec de copie, par analogie directe avec la convention déjà en vigueur pour les 4 dossiers historiques de `create_job()`. La revue a jugé cette analogie insuffisante pour un artefact **nouvellement introduit** par cette mission — corrigé avec un cleanup-then-raise dédié, sans toucher au comportement des 4 dossiers historiques (voir §14, dette découverte mais non traitée).

Écart mineur inchangé depuis la version initiale : `TrainingJobPaths` étant un `NamedTuple` à champs tous obligatoires (aucun défaut), l'ajout de `concept_dir` a nécessité la mise à jour des deux seules constructions manuelles existantes dans les tests (`test_training_job_runner.py`) — un ajout mécanique d'un mot-clé, sans changement de comportement testé.

## 13. Exclusions confirmées

Aucune implémentation de Resume, aucune modification de `Training`/`TrainingJob` Domain, de la machine à états, d'EventBus, de l'UI, de la Central LoRA Library, d'Inference, du backup OneTrainer, du PID/process management — conformément au périmètre autorisé.

## 14. Dette découverte (non traitée par cette mission)

En corrigeant le cleanup du `concept_dir`, l'implémentation a confirmé que les 4 dossiers historiques de `create_job()` (`output`/`workspace`/`cache`/`debug`) partagent la même absence de nettoyage sur échec — une convention déjà en vigueur avant Mission 139 (documentée dans le code comme « additive, per-job-id folder, harmless to leave orphaned if save() subsequently fails »), jamais remise en cause par cette mission. Conformément au périmètre strict demandé en revue (« M139 corrige uniquement l'artefact qu'elle introduit »), cette faiblesse analogue n'a **pas** été corrigée ici — elle est documentée comme dette distincte, candidate pour une mission future si jugée nécessaire, jamais mélangée au correctif du `concept_dir`.
