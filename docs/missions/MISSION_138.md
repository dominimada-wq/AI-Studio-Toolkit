# Mission 138 — Investigate Training Crash/Interruption Recovery

> **MISSION AUDIT/CONCEPTION — orientation générale validée par l'architecte et ChatGPT (Architecture B), décisions de conception finalisées ci-dessous. Aucune implémentation autorisée à ce stade.** L'audit post-Mission 137 a confirmé que `TrainingManager._recover_stale_jobs()` transforme tout job `STARTING`/`RUNNING` interrompu en `UNKNOWN` sans jamais tenter de reprise réelle, alors qu'OneTrainer dispose d'un mécanisme de backup/reprise réel et fonctionnel, entièrement inexploité par AI Studio Toolkit aujourd'hui. Cette version du document ferme les décisions de conception restantes (snapshot concept, validation de backup, processus orphelin, sémantique des états, champs verrouillés, backup policy, cleanup, UI, smoke, séquencement en missions atomiques) et propose la première mission d'implémentation.

## 1. Problème

Après un crash applicatif, un kill forcé, une coupure de courant ou un redémarrage OS pendant un run OneTrainer réel, AI Studio Toolkit ne fait que marquer le job `UNKNOWN` à la réouverture du Workspace (`_recover_stale_jobs()`, `src/managers/training_manager.py:225-241`) — aucune reprise n'est proposée, alors qu'un travail de calcul GPU potentiellement long peut être définitivement perdu. OneTrainer lui-même sait reprendre un entraînement interrompu (backup contenant poids LoRA + état optimizer + EMA + compteurs), mais ce mécanisme n'est ni configuré, ni exposé, ni consommé par Toolkit aujourd'hui.

## 2. Preuves Toolkit (lifecycle actuel réel)

*(Inchangé depuis la première itération — voir §2.1 à §2.6 ci-dessous pour la cartographie complète.)*

### 2.1 Cartographie complète

- **Training (persistant, lié au Dataset)** : `TrainingManager.create()` (`training_manager.py:265-303`) crée l'entité, l'ajoute à `character.trainings`, publie `TRAINING_CREATED`.
- **Prepare (Training-scope, sans Job)** : `prepare_onetrainer_config()` (`training_manager.py:794-958`) valide `base_model_source`, appelle `_materialize_concept()` (`:698-792` — reconstruit `training/<id>/concept/` depuis les images/captions **actuelles** du Dataset, à chaque appel), construit la config OneTrainer, l'écrit dans `training/<id>/onetrainer_config.json`. Ne crée jamais de `TrainingJob` (décision Mission 100).
- **Job creation (Start)** : `TrainingPage.start_training()` (`training_page.py:2097-2190`) ré-appelle systématiquement `prepare_onetrainer_config()` (donc reflète toujours l'écran courant), puis `TrainingManager.create_job(training_id)` (`training_manager.py:981-1073`) : nouveau `job_id`, `TrainingJobPaths` sous `training/<id>/jobs/<job_id>/{output,workspace,cache,debug}` (`job_paths()`, `:960-979`), copie figée de la config avec **seuls** `output_model_destination`/`workspace_dir`/`cache_dir`/`debug_dir` réécrits vers les dossiers du Job.
- **Launch** : `TrainingJobRunner` (`src/ui/training_job_runner.py`) lance `QProcess(python_executable, [train_remote.py, --config-path, --command-path])`, `cwd` = racine OneTrainer.
- **STARTING → RUNNING** : signal `started` → `update_job_state(RUNNING)` → `TRAINING_JOB_STATE_CHANGED`.
- **Sortie** : stdout/stderr ligne par ligne uniquement (aucun `callback.pipe` lu).
- **Transition terminale** : `_on_process_finished()` (`training_job_runner.py:162-194`) — `_cancel_requested` vérifié **avant** `exit_status` ; sinon `CrashExit`/code non nul → `failed` ; sinon `expected_output_path.is_file()` → `succeeded` ou `failed`.
- **Import Central LoRA** : manuel uniquement, `import_selected_job_to_library()` (`training_page.py:2439-2522`), gated sur `state == SUCCEEDED` + fichier réel + `imported_lora_id` non déjà résolu — lien unidirectionnel Job → Library.

### 2.2 Machine à états — exhaustive

| État | Terminal ? | Notes |
|---|---|---|
| `STARTING` | Non | `TRAINING_JOB_ACTIVE_STATES` |
| `RUNNING` | Non | `TRAINING_JOB_ACTIVE_STATES` |
| `SUCCEEDED` | Oui | seul état important pour Import/Use-in-Inference |
| `FAILED` | Oui | `error_message` renseigné |
| `CANCELLED` | Oui | annulation utilisateur volontaire, jamais confondue avec crash natif |
| `UNKNOWN` | Oui | **aucune transition ne quitte jamais `UNKNOWN`** — confirmé, et la politique retenue (§9) préserve ce fait |

`_recover_stale_jobs()` (souscrit uniquement à `WORKSPACE_OPENED`) bascule inconditionnellement tout job `STARTING`/`RUNNING` en `UNKNOWN` — sans vérification de PID, sans inspection filesystem.

### 2.3 Processus orphelin — risque confirmé, aucune protection existante aujourd'hui

`TrainingJobRunner` crée un `QProcess` par défaut (`training_job_runner.py:64-90`) — aucun Job Object Windows, aucun groupe de processus lié au cycle de vie du parent. Confirmé par grep direct (`processId()`/`QProcess` dans `training_job_runner.py`) : **`QProcess.processId()` n'est appelé nulle part dans le code actuel** — aucun PID n'est persisté. Si Toolkit meurt anormalement, le processus enfant OneTrainer peut survivre en orphelin, continuant d'écrire dans `jobs/<job_id>/workspace/`. Voir §9 pour la stratégie retenue.

### 2.4 Cancel — état bien distingué, mais cause non tracée pour UNKNOWN

`_cancel_requested` est vérifié avant `exit_status` : un vrai Cancel est fiablement stocké comme `"cancelled"`, jamais confondu avec un crash natif.

### 2.5 Rationale Mission 100 pour l'isolation `workspace_dir` par Job

Deux raisons documentées (`MISSION_100.md` §3.1, §9) : (1) les champs OneTrainer `workspace_dir`/`cache_dir`/`debug_dir` sont relatifs et atterriraient sinon dans l'installation OneTrainer ; (2) deux runs successifs du même Training ne doivent jamais s'écraser — exigence explicite de cette mission.

### 2.6 UI actuelle

Boutons : Nouvelle session, Supprimer, Enregistrer les paramètres, Préparer la configuration, **Démarrer** (toujours = `create_job()` neuf), **Annuler**, Importer dans la Bibliothèque, Utiliser dans Inference. **Aucun bouton Resume/Retry.** `jobs_list` est un historique en lecture seule.

## 3. Preuves OneTrainer (mécanisme réel, code source installé)

### 3.1 Mécanisme de backup — bout en bout

- **Champs config** (`modules/util/config/TrainConfig.py`) : `backup_after` (défaut `30`), `backup_after_unit` (défaut `MINUTE`), `rolling_backup` (défaut **`False`**), `rolling_backup_count` (défaut `3`), `backup_before_save` (défaut `True`), `continue_last_backup` (défaut `False`).
- **Emplacement/nommage** : `<workspace_dir>/backup/<timestamp>-backup-<progress>/` (`GenericTrainer.py:431-476`).
- **Contenu exact d'un backup LoRA** (confirmé fichier par fichier, `modules/modelSaver/GenericLoRAModelSaver.py:28-47` + `InternalModelSaverMixin.py:19-42`, dans l'ordre d'écriture réel) :
  1. `lora/lora.safetensors` — poids LoRA (adaptateur uniquement, **jamais les poids du modèle de base**), écrit en premier, inconditionnel.
  2. fichiers d'embeddings additionnels éventuels (conditionnel, hors périmètre LoRA simple).
  3. `optimizer/optimizer.pt` — état optimizer complet, inconditionnel.
  4. `ema/ema.pt` — état EMA, **conditionnel** (seulement si EMA activé).
  5. `meta.json` — `epoch`/`epoch_step`/`epoch_sample`/`global_step`, écrit **en dernier**.
  6. `onetrainer_config/args.json`/`concepts.json`/`samples.json` — audit trail, **jamais relu par aucun code**, écrit après tout le reste.
- **Non sauvegardés** : état AMP GradScaler, état RNG (torch/numpy/python), position exacte du dataloader intra-époque (les époques complètes sont sautées, une époque partielle redémarre du début avec un ordre de mélange différent).
- **Aucune écriture atomique** (pas de write-temp-puis-rename, pas de `fsync`) nulle part dans ce chemin de sauvegarde — une coupure de courant en cours d'écriture peut laisser un fichier tronqué/corrompu à n'importe quelle étape de la séquence ci-dessus.

### 3.2 Sémantique de `continue_last_backup` et mécanisme cross-job exact

- **Détermination du « dernier backup »** : scan pur du répertoire, `TrainConfig.get_last_backup_path()`, tri par nom décroissant.
- **`continue_last_backup=True` sur `workspace_dir` neuf/vide** : démarre silencieusement à zéro (`print()` console uniquement, aucune exception).
- **Mécanisme réel de restauration (précisé)** : `InternalModelLoaderMixin._load_internal_data()` (`modules/modelLoader/mixin/InternalModelLoaderMixin.py:16-42`) est appelée **inconditionnellement**, sur le chemin résolu par le champ **`lora_model_name`** pour un entraînement LoRA (confirmé : `TrainConfig.model_names()` mappe `lora_model_name` → `ModelNames.lora`, consommé par `GenericLoRAModelLoader.load()`). Elle vérifie l'existence de `meta.json` à cet endroit, puis restaure `optimizer/optimizer.pt`, `ema/ema.pt` (si présent) et `train_progress` — **indépendamment de `continue_last_backup`**.
- **`base_model_name` reste inchangé lors d'une reprise** : puisque le backup LoRA ne contient **jamais** les poids du modèle de base (confirmé, `StableDiffusionXLLoRASaver._get_state_dict()` et équivalents architecture par architecture — seuls `text_encoder_*_lora`/`unet_lora`/`lora_state_dict` sont sauvegardés), `base_model_name` doit continuer à pointer vers le checkpoint de base original, non modifié entre le run original et la reprise.
- **La restauration des poids LoRA eux-mêmes est une fonction séparée** : `LoRALoaderMixin.__load_internal()` (`modules/modelLoader/mixin/LoRALoaderMixin.py:48-58`) re-vérifie indépendamment `meta.json`, puis charge `lora/lora.safetensors` **seulement si ce fichier existe** — sinon elle **retourne silencieusement sans erreur**.
- **Découverte critique de sécurité** : si `meta.json` existe (donc `_load_internal_data()` réussit et restaure optimizer/EMA/step) mais que `lora/lora.safetensors` est absent (ex. copie/déplacement du dossier de backup par Toolkit lui-même interrompue), la reprise se poursuit **silencieusement sans les poids LoRA réels**, avec un compteur de step avancé — un résultat corrompu, sans qu'aucune exception ne soit levée. Ce cas doit être explicitement exclu par la validation structurelle (§4/§15).
- **Comportement sur fichier corrompu** : `meta.json` tronqué/invalide → `json.decoder.JSONDecodeError` **non intercepté**, crash immédiat et bruyant du process. `optimizer.pt`/`ema.pt` corrompus (pas absents) → exception `torch.load()` **non interceptée** (le seul `except` present est `contextlib.suppress(FileNotFoundError)`, qui ne couvre pas un fichier présent mais corrompu) → crash immédiat et bruyant. **Seul le cas « `lora.safetensors` manquant, `meta.json` présent et valide » est silencieux** — tous les autres cas de corruption sont des crashs bruyants et donc déjà auto-détectables (le process se termine en échec quasi immédiat après lancement).
- **Conclusion pour Toolkit** : `continue_last_backup` n'est PAS le mécanisme central pour une reprise cross-job — Toolkit doit piloter directement `lora_model_name` (jamais `continue_last_backup`, qui reste à `False`), en pointant explicitement vers le dossier de backup choisi du Job source, tout en laissant `base_model_name` intact.

### 3.3 Backup vs Save vs Output final — inchangé depuis la première itération, confirmé

| Artefact | Emplacement | Contenu | Déclenchement |
|---|---|---|---|
| **Backup** | `workspace_dir/backup/...` | poids LoRA + optimizer + EMA + compteurs | `backup_after`/`backup_after_unit` |
| **Save** | `workspace_dir/save/...` | poids LoRA seuls, pas de reprise possible | `save_every` (défaut `NEVER`, désactivé) |
| **Output final** | `output_model_destination` | poids LoRA seuls, livrable réel | une seule fois, fin de run |

### 3.4 Immutabilité de la config au resume — non garantie par OneTrainer (inchangé, voir §9/§10 pour la politique Toolkit retenue)

### 3.5 Dépendances fichiers externes — aucune gestion gracieuse côté OneTrainer (inchangé)

## 4. Fonctionnement exact des backups — defaults réels appliqués aujourd'hui par Toolkit (précisé)

**Vérifié par grep exhaustif** : aucun des 8 champs backup (`backup_after`, `backup_after_unit`, `rolling_backup`, `rolling_backup_count`, `backup_before_save`, `continue_last_backup`, `save_every`, `save_every_unit`) n'apparaît nulle part dans `src/`. `build_training_config()` (`src/engines/onetrainer_config.py:878-900`) construit un dict Python minimal **de zéro**, jamais dérivé d'un objet `TrainConfig` sérialisé — chaque clé absente du dict signifie que le default OneTrainer s'applique tel quel, confirmé par la lecture de `BaseConfig.from_dict()` (`modules/util/config/BaseConfig.py:66-138`, qui `pass` silencieusement sur toute clé absente du dict fourni) et par `scripts/train_remote.py:69-71` (`TrainConfig.default_values()` suivi de `.from_dict(json.load(f))` — les valeurs par défaut restent donc actives sauf override explicite).

**Confirmé : tout entraînement lancé par Toolkit aujourd'hui tourne avec, littéralement et sans aucune modification** : `backup_after=30` (`MINUTE`), `rolling_backup=False` (**accumulation illimitée de backups complets, jamais purgés**), `rolling_backup_count=3` (inactif tant que `rolling_backup=False`), `backup_before_save=True`, `save_every=0`/`NEVER`, `continue_last_backup=False`.

## 5-6. Lifecycle actuel / machine à états actuelle — voir §2.1/§2.2

## 7. Scénarios d'interruption — analyse par cas

*(Inchangé depuis la première itération — tableau des 10 cas A-J déjà validé dans le document précédent.)*

| Cas | État Toolkit | État process | Reprise sûre ? |
|---|---|---|---|
| A. OneTrainer crash, Toolkit ouvert | `FAILED` | mort | Oui, si `can_resume()` |
| B. Toolkit crash, OneTrainer meurt aussi | `UNKNOWN` au reopen | mort | Oui, si `can_resume()` |
| C. Toolkit crash, OneTrainer continue de tourner | `UNKNOWN` au reopen | **vivant, orphelin** | **Non sans détection PID (§9)** |
| D. Windows/machine redémarre | `UNKNOWN` au reopen | mort | Oui, si `can_resume()` |
| E. Coupure de courant | `UNKNOWN` au reopen | mort, backup potentiellement tronqué | Oui, seulement si validation structurelle passe (§4/§15 du présent document) |
| F. Cancel utilisateur | `CANCELLED` | mort proprement | **Non par politique** (§8) |
| G. Fermeture volontaire pendant Training | bloqué par guard existant | — | hors périmètre |
| H. Process tué manuellement | `UNKNOWN` au reopen | mort | Oui, si `can_resume()` |
| I. Erreur Python/CUDA/OOM | `FAILED` | mort | Oui, seulement si backup exploitable |
| J. Job UNKNOWN au prochain lancement | couvert par B/C/D/E/H | — | dépend du sous-cas réel |

## 8. Processus orphelin — stratégie retenue

**Décision : Option C — PID + information de création persistés, prérequis au Resume (pas seulement documenté comme limite acceptée).**

Analyse des options :
- **A (aucune persistance + confirmation utilisateur seule)** : rejetée — explicitement jugée insuffisante par l'architecte quand une détection raisonnable est possible.
- **B (PID seul)** : insuffisant seul — un PID peut être réutilisé par l'OS après la mort du process original, un simple `tasklist`/`ctypes` "PID existe" pourrait donc donner un faux positif (un processus sans rapport, même PID, confondu avec l'ancien OneTrainer).
- **C (PID + horodatage de création du process) — retenue** : au lancement de `QProcess`, Toolkit peut obtenir le PID réel via `QProcess.processId()` (**disponible aujourd'hui, jamais appelé — confirmé par grep**), et persister `{pid, started_at}` dans un petit fichier `jobs/<job_id>/process.json`, écrit au moment du signal `started`. Pour vérifier ultérieurement si ce process est *toujours celui-là* (pas un PID recyclé), Toolkit peut interroger l'heure de création réelle du process portant ce PID via un appel Windows natif (`tasklist /fo csv /v` parse la colonne heure de démarrage, ou `ctypes`+`OpenProcess`+`GetProcessTimes`) — **aucune nouvelle dépendance externe requise** (`psutil` reste exclu, conformément à la décision Mission 100). Si le PID existe toujours ET que son heure de création correspond (tolérance de quelques secondes) à celle enregistrée : le job est considéré potentiellement encore actif, et `can_resume()` doit refuser la reprise avec un message explicite nommant le PID et l'heure de démarrage constatée, invitant à vérifier manuellement (Gestionnaire des tâches) avant toute action destructive. Si le PID n'existe plus, ou existe mais avec une heure de création différente : le verrou est considéré obsolète, la reprise peut être autorisée sous réserve des autres critères de `can_resume()`.
- **D (autre)** : non retenue — un Job Object Windows/groupe de process lié au cycle de vie du parent réglerait le problème à la racine (le process enfant mourrait automatiquement avec Toolkit) mais constitue un changement plus profond du mécanisme de lancement (`TrainingJobRunner`), hors périmètre de cette conception ; à documenter comme piste d'amélioration future distincte, non nécessaire pour livrer un Resume v1 sûr.

**Ce mécanisme PID+horodatage devient un prérequis Domain/Manager de la mission d'implémentation (voir Mission C, §17), pas une simple recommandation différée.**

## 9. Sémantique des états — politique confirmée et verrouillée

Décision de l'architecte confirmée compatible avec le Domain et l'UI actuels, sans aucune dérogation nécessaire :

- Le Job **source** (`UNKNOWN` ou `FAILED`) **reste inchangé et terminal** — aucune transition `UNKNOWN → RUNNING` n'est introduite, la machine à états existante n'est pas modifiée.
- Un Resume crée systématiquement un **nouveau** `TrainingJob` : `STARTING → RUNNING → (SUCCEEDED | FAILED | CANCELLED | UNKNOWN)`, exactement le cycle de vie existant, sans aucun nouvel état.
- `resumed_from_job_id` (§10) porte la seule information de filiation nécessaire.
- Aucun cas OneTrainer tracé (§3) ne justifie de déroger à cette politique — le mécanisme de reprise OneTrainer lui-même ne connaît d'ailleurs aucune notion d'« état de job » ; toute la sémantique d'état est de la responsabilité de Toolkit.

## 10. `resumed_from_job_id` — spécification exacte

- **Champ Domain** : `TrainingJob.resumed_from_job_id: str = ""` (convention du projet : chaîne vide par défaut, jamais `None`, cohérent avec `imported_lora_id` et les autres champs de référence optionnels de `TrainingJob`).
- **Persistence** : symétrique `to_dict()`/`from_dict()`, lu via `data.get("resumed_from_job_id", "")`.
- **Compatibilité ascendante** : un `project.json` existant sans cette clé se charge sans erreur — absence traitée comme chaîne vide, exactement le même idiome que tout autre champ optionnel du projet.
- **Affichage UI** : `_describe_job()` peut annexer une mention (« reprise de <horodatage du job source> ») quand le champ est non vide — amélioration mineure, non bloquante pour une première version.
- **Profondeur de chaîne** : aucune structure généalogique dédiée nécessaire — un simple pointeur vers le job précédent suffit (Job C → `resumed_from_job_id=B`, Job B → `resumed_from_job_id=A`) ; une éventuelle lecture de la chaîne complète se fait par suivi répété du champ, jamais par une nouvelle abstraction.

## 11. Snapshot concept/Dataset — architecture retenue

### 11.1 Analyse du code actuel (précisée)

- **Chemin exact** : `<workspace_root>/training/<training_id>/concept/` (`_training_folder()` + `_CONCEPT_SUBFOLDER_NAME`, `training_manager.py:695-696,111`) — **scope Training, pas Job**.
- **Propriétaire de création** : `_materialize_concept()` (`training_manager.py:698-792`), seule et unique méthode qui écrit ce dossier.
- **Moment de matérialisation** : à chaque appel de `prepare_onetrainer_config()` (`:845`), lui-même déclenché par le bouton « Préparer » **et** inconditionnellement par `start_training()` à **chaque** clic sur Démarrer, pour **n'importe quel** Job du Training (`training_page.py:2153`, juste avant `create_job()` — confirmé, aucune garde n'empêche cela pendant qu'un autre Job du même Training est encore actif, la seule garde étant un `_active_runner is not None` en mémoire, local à l'instance de Page).
- **Contenu exact** : le dossier est vidé puis reconstruit (`WorkspaceStorage.delete_folder()` + `mkdir()`), puis pour chaque image du Dataset : copie physique réelle (`shutil.copy2`, jamais un lien) + un fichier `.txt` de légende de même nom (caption réelle ou `training.trigger_word` en repli). **Aucun autre fichier** n'est écrit dans ce dossier.
- **Durée de vie** : n'est **jamais supprimé** par `TrainingManager.delete(training_id)`, qui est une mutation Domain-only sans aucun accès filesystem (`training_manager.py:1199-1201`, confirmé) — **constat collatéral découvert par cette investigation, indépendant du sujet Resume** : supprimer un Training laisse déjà aujourd'hui tout son arbre filesystem (`concept/`, config, tous les Jobs et leurs backups) orphelin en permanence. Signalé comme dette distincte, hors périmètre de M138, candidate pour une mission future séparée (ne pas la traiter dans l'implémentation Resume).
- **Réutilisation entre Jobs** : confirmée — `create_job()` fige une copie de la config mais **ne copie jamais le dossier concept**, se contentant de reporter tel quel le chemin (string) du dossier Training-scope partagé dans le `"concepts"` du snapshot figé.
- **Lecture par OneTrainer** : tracée précisément côté OneTrainer (`mgds/pipelineModules/CollectPaths.py` + `mgds/LoadingPipeline.start_next_epoch()`, guard `if not module.started`) — le contenu du dossier concept est listé **une seule fois, au tout début du process**, jamais relu ensuite pendant la même exécution. Conséquence : un process OneTrainer déjà en cours d'exécution est totalement insensible à une mutation du dossier concept — **mais un Resume, étant nécessairement un nouveau process, relit l'état du dossier au moment où il démarre**, rendant le partage/mutabilité du dossier concept un risque spécifique et réel au Resume, pas un risque généralisé au fonctionnement normal actuel.

### 11.2 Architecture retenue : **Option A — snapshot concept par TrainingJob**

`create_job()` doit désormais **copier** le contenu du dossier concept (images + fichiers `.txt` de légende — c'est l'intégralité de ce qu'il contient, §11.1) vers un sous-dossier propre au Job (ex. `jobs/<job_id>/concept/`), exactement selon le même mécanisme d'isolation déjà appliqué à `output`/`workspace`/`cache`/`debug`. Le `"concepts"` du snapshot de config figé du Job doit référencer ce nouveau chemin Job-scope, jamais le dossier Training-scope partagé.

**Ce qui doit être figé par Job** (répondant précisément à la demande de l'architecte) :
- les fichiers image (copie physique, déjà le comportement de `_materialize_concept()` — il suffit de rediriger la destination) ;
- les fichiers `.txt` de légende associés (même remarque) ;
- le mot déclencheur (`trigger_word`) : **déjà implicitement figé** puisqu'il est gravé directement dans le contenu des fichiers `.txt` au moment de la matérialisation — aucun stockage séparé n'est nécessaire ;
- l'entrée de configuration `concepts[].path` dans le snapshot JSON du Job (déjà figé par construction dès lors qu'il pointe vers le nouveau dossier Job-scope) ;
- **rien d'autre** : aucune résolution n'est pré-appliquée aux images (`_materialize_concept()` ne redimensionne jamais rien, confirmé), aucun autre fichier n'existe dans le dossier concept aujourd'hui.

**Cette correction est un prérequis général de correction de Job**, pas seulement une nécessité pour Resume : elle corrige aussi le risque latent déjà présent aujourd'hui (§11.1, dernier point) qu'un second Job du même Training, démarré pendant qu'un autre est encore actif, réécrive silencieusement les données que le premier croit figées. Elle doit donc être livrée comme une mission indépendante et antérieure à toute UI de Resume (voir Mission A, §17).

**Sécurité pour le Resume lui-même** : une reprise doit toujours utiliser le **snapshot concept original du Job source** (déjà isolé grâce à cette correction), jamais l'état courant du Dataset — le nouveau Job de reprise copie lui-même ce même snapshot concept (celui du Job source) vers son propre dossier Job-scope, garantissant que la reprise voit exactement les mêmes données que le run interrompu.

## 12. Fichiers externes / modèle de base

Inchangé depuis la première itération — vérification d'existence simple des chemins de fichiers externes référencés dans la config figée avant d'autoriser une reprise (§13, `can_resume`).

## 13. Politique FAILED / UNKNOWN / CANCELLED — confirmée et verrouillée

- **`SUCCEEDED`** : jamais Resume (aucun besoin, le Job a réussi).
- **`STARTING`/`RUNNING`** : jamais Resume tant qu'ils sont considérés actifs — un Resume ne s'applique qu'à un Job déjà terminal.
- **`UNKNOWN`** : potentiellement Resume, uniquement si `can_resume()` (§15) est vrai — jamais sur le seul état.
- **`FAILED`** : potentiellement Resume, mêmes conditions — un `FAILED` par OOM/config invalide n'aura généralement aucun backup exploitable, donc `can_resume()` le filtre naturellement sans logique spécifique par cause.
- **`CANCELLED`** : **exclu du Resume en v1**, sans exception. Aucun cas OneTrainer tracé ne justifie de déroger à cette politique — le mécanisme de reprise d'OneTrainer ne fait aucune distinction entre les causes d'arrêt, la distinction est entièrement portée par Toolkit. Si l'utilisateur souhaite repartir après un Cancel : nouveau Start normal (`create_job()`), pas un Resume.

## 14. Validation de backup — `can_resume(job)` précisé en quatre niveaux

Comme demandé, la présence seule d'un dossier `backup/` n'est pas une preuve suffisante. Quatre niveaux distincts :

1. **Backup absent** : aucun sous-dossier de `jobs/<job_id>/workspace/backup/` — `can_resume()` faux immédiatement.
2. **Backup incomplet** : le dossier existe mais échoue à l'un des tests structurels ci-dessous — traité comme absent pour ce backup précis (voir stratégie « plus récent valide », §16).
3. **Backup structurellement valide (le niveau que `can_resume()` vérifie réellement, sans charger les poids)** :
   - le dossier existe ;
   - `meta.json` existe, est un JSON valide, et contient les clés attendues (`epoch`, `epoch_step`, `epoch_sample`, `global_step`) ;
   - `lora/lora.safetensors` existe et a une taille non nulle (exclut explicitement le cas de corruption silencieuse identifié en §3.2 — `meta.json` présent mais poids LoRA absents) ;
   - `optimizer/optimizer.pt` existe et a une taille non nulle ;
   - `ema/ema.pt` existe et a une taille non nulle **si et seulement si** la config source du Job a EMA activé (sinon son absence est normale, pas une preuve d'invalidité) ;
   - les fichiers externes référencés par la config figée du Job source (modèle de base, VAE, text encoders) existent toujours à l'emplacement attendu (§12).
   - **Pas de checksum/hash** — non justifié : aucun mécanisme d'intégrité n'existe côté OneTrainer de toute façon (confirmé, §3.1), un hash ne validerait qu'une corruption que les tests d'existence/taille/parsing détectent déjà en pratique dans les cas réalistes (fichier tronqué, JSON invalide, fichier manquant).
4. **Backup réellement confirmé par un smoke OneTrainer** : seul un lancement réel (le smoke de la future mission d'implémentation, §19, ou le Resume réel lui-même) prouve que le chargement aboutit effectivement sans exception `torch.load()`/`safetensors.load_file()` masquée par un test structurel imparfait. **Décision retenue** : ne pas dupliquer la logique de chargement d'OneTrainer dans Toolkit (éviterait un second loader à maintenir en parallèle) — le niveau 3 gate uniquement l'activation du bouton Reprendre et la sélection automatique du backup ; un échec malgré un niveau 3 positif (ex. corruption non détectée par les tests structurels) se traduit par un crash immédiat et bruyant du process OneTrainer repris (confirmé §3.2 : tous les cas de corruption sauf un sont bruyants), que Toolkit doit alors afficher clairement comme « échec de la reprise, backup probablement corrompu » plutôt que comme un échec d'entraînement générique.

## 15. `can_resume(job)` — prédicat final

Un Job est éligible si **toutes** ces conditions sont vraies :
1. `job.state in {FAILED, UNKNOWN}` (§13) ;
2. le snapshot de config du Job existe toujours sur disque ;
3. au moins un backup de niveau 3 (« structurellement valide », §14) existe sous `jobs/<job_id>/workspace/backup/` ;
4. les fichiers externes référencés par la config figée existent toujours (§12) ;
5. aucun `TrainingJobRunner` actif de la session Toolkit courante ne suit déjà ce `job_id` ;
6. le fichier de verrou `process.json` du Job (§8), s'il existe, ne correspond à aucun process actuellement vivant avec la même heure de création — sinon `can_resume()` retourne faux avec un message explicite nommant le PID/l'heure constatée.

## 16. Stratégie de sélection du dernier backup valide

**Décision retenue (option recommandée par l'architecte) : parcourir les backups du plus récent au plus ancien (même ordre de tri qu'OneTrainer lui-même) et sélectionner le premier qui passe la validation de niveau 3 (§14)** — ne jamais se limiter au seul plus récent, puisqu'une coupure de courant peut précisément avoir laissé le tout dernier backup incomplet (§7.E). Si aucun backup de la liste n'est structurellement valide, `can_resume()` est faux (niveau 1 ou 2 pour tous, §14).

## 17. Configuration de Resume — source et champs verrouillés

**Décision** : le Resume ne reconstruit **jamais** sa configuration depuis les réglages courants de `TrainingPage`. Il part **exclusivement** du snapshot déjà figé du Job source (`jobs/<job_id>/onetrainer_config.json`, déjà persistant et complet — confirmé suffisant, aucune nouvelle représentation Domain structurée n'est nécessaire : c'est l'option **B** de la question posée, « config OneTrainer matérialisée du job source », qui suffit seule).

**Conséquence directe et volontairement simplificatrice** : puisque la configuration de reprise est une **copie verbatim** de la config figée du Job source, **la question du champ-par-champ IMMUTABLE/MODIFIABLE/INCONNU ne se pose plus en v1** — tout est implicitement verrouillé par construction, aucune UI de ré-édition n'est nécessaire ni proposée. Les **seules** valeurs que Toolkit réécrit explicitement dans la copie, toutes strictement nécessaires à l'isolation filesystem et au ciblage du backup, sont :
- `output_model_destination`, `workspace_dir`, `cache_dir`, `debug_dir` → nouveaux chemins Job-scope du Job de reprise (mécanisme déjà existant, identique à `create_job()` normal) ;
- `concepts[].path` → nouveau dossier concept Job-scope, copié depuis le snapshot concept du Job source (§11.2) ;
- `lora_model_name` → chemin du backup sélectionné (§16) du Job source ;
- `continue_last_backup` → explicitement laissé/forcé à `False` (Toolkit pilote directement `lora_model_name`, §3.2, jamais le scan ambiant OneTrainer).

Tout le reste (modèle de base, rang LoRA, optimizer, précision, timestep distribution, etc.) est copié tel quel, sans modification possible dans l'UI v1. Une future v2 pourrait envisager d'autoriser l'édition de champs prouvés sûrs (ex. prolonger le nombre d'époques) — **explicitement hors périmètre et non décidé par cette mission**.

## 18. Backup policy et rolling backups — décision

Puisque les defaults réels (§4) s'appliquent sans modification aujourd'hui, la politique cible Toolkit v1 est :
- **Cadence (`backup_after`/`backup_after_unit`)** : conserver le default OneTrainer (30 minutes) en l'absence de toute mesure empirique de coût réel sur le matériel du projet — ne pas fixer arbitrairement une autre valeur sans justification chiffrée (à valider lors de l'implémentation, avec le smoke réel comme première mesure).
- **`rolling_backup`** : passer à **`True`**, avec `rolling_backup_count` conservé au default OneTrainer (**3**) sauf preuve contraire — objectif : borner la croissance disque déjà en cours aujourd'hui (§4) sans perdre la marge de sécurité offerte par « plus récent valide, sinon le précédent » (§16), qui a justement besoin de plus d'un backup disponible pour fonctionner correctement.
- **Estimation qualitative du coût disque** : un backup LoRA ne contient **aucun poids de modèle de base** (§3.1/§3.2) — seulement l'adaptateur LoRA (petit, dépend du rang), l'état optimizer (généralement du même ordre de grandeur ou un peu plus que les poids LoRA pour un optimizer à moments comme Adam), et un `ema.pt` optionnel de taille comparable aux poids. Le coût par backup est donc **faible comparé à un checkpoint de modèle de base complet** — mais `rolling_backup=False` aujourd'hui signifie que ce coût, même faible, croît **sans borne** sur toute la durée d'un run long (un run de plusieurs heures peut accumuler des dizaines de backups). Aucune valeur exacte en Mo/Go n'est avancée ici faute de mesure réelle — à quantifier lors de l'implémentation.

## 19. Correctif backup indépendant — séquencement proposé

**Oui, il est utile de l'activer avant même l'implémentation du Resume** — c'est un correctif de dette à risque quasi nul (un seul changement de clés de config), bénéfique indépendamment du sort du Resume. Voir Mission B, §21 (séquencement) — proposée comme mission courte et autonome, avant ou en parallèle de la Mission A. **Aucune modification n'est faite dans M138 lui-même.**

## 20. Cleanup / rétention — précisé

- **Backups du Job source après un Resume réussi** : conservés en v1, aucune suppression automatique (permet l'audit/debug, évite une nouvelle surface d'opération destructive automatique tant qu'aucun usage réel ne l'a validée).
- **Backups du nouveau Job (Resume)** : suivent la même politique que tout Job normal — bornés par `rolling_backup=True` (§18).
- **Suppression d'un `TrainingJob` individuel** : mécanisme non confirmé comme existant aujourd'hui de façon distincte de la suppression du Training entier — à spécifier lors de l'implémentation si un tel besoin apparaît, pas dans M138.
- **Suppression d'un Training** : **découverte collatérale** — `TrainingManager.delete()` est Domain-only, ne supprime **jamais** le filesystem (`training/<id>/` reste orphelin indéfiniment, concept + config + tous les Jobs et leurs backups inclus). C'est une dette préexistante, indépendante de M137 et du sujet Resume — **non traitée par cette mission**, signalée pour une mission future distincte, à ne surtout pas mélanger avec l'implémentation Resume.
- **Suppression du Workspace** : couvre déjà tout récursivement — inchangé, aucun risque.
- **SUCCEEDED / FAILED / UNKNOWN** : aucune action de cleanup automatique supplémentaire proposée en v1 au-delà de `rolling_backup` (§18).

## 21. Output final / Central LoRA Library — reconfirmé compatible

Job B (Resume), une fois `SUCCEEDED`, est un `TrainingJob` normal et complet avec son propre `final_output_path` sous son propre dossier Job-scope isolé — entièrement indépendant des chemins du Job A. Le mécanisme d'import existant (`imported_lora_id`, jamais mis en cache, revalidé à l'affichage) s'applique sans aucune modification. Le Job A source reste un enregistrement historique non-importable (jamais `SUCCEEDED`). **Aucune modification de la Central LoRA Library n'est nécessaire.**

## 22. UI proposée — précisée

- **Nom** : bouton « Reprendre », strictement distinct de « Démarrer ».
- **Apparition** : visible dans le contexte de sélection d'un Job passé dans `jobs_list` (à côté d'Import/Use-in-Inference).
- **Activation** : uniquement quand `can_resume(job)` (§15) est vrai pour le Job sélectionné.
- **Message si backup absent/invalide** : message inline explicite distinct de la désactivation par état (ex. « Aucun backup exploitable trouvé pour ce job » vs « Ce job ne peut pas être repris [état incompatible] »).
- **Indication du job source** : horodatage/identifiant du Job source affiché, ainsi que l'horodatage du backup sélectionné automatiquement (§16).
- **Paramètres affichés** : vue en lecture seule des paramètres clés de la configuration figée du Job source (modèle de base, rang LoRA, optimizer, résolution, etc.) — pour permettre une revue avant confirmation.
- **Paramètres modifiables** : **aucun en v1** (§17) — pas de sélection manuelle de backup, pas de ré-édition de configuration. Réutilise le pattern d'activation-par-état déjà en place dans `_refresh_job_controls()`.

## 23. Smoke réel futur — étendu

Le smoke de la future mission d'implémentation (Mission D, §21) doit prouver, dans l'ordre :

1. un petit entraînement réel démarre ;
2. au moins un backup réel est créé (avec `backup_after` réduit pour la durée du test) ;
3. le `global_step` est noté avant interruption ;
4. une interruption contrôlée est effectuée (kill du process) ;
5. un nouveau `TrainingJob` de reprise est créé (`resume_job()`) ;
6. avec un nouveau `workspace_dir` isolé ;
7. chargeant explicitement le backup de l'ancien Job (`lora_model_name` pointé dessus) ;
8. le `global_step` repris est bien `> 0` (pas un redémarrage silencieux à zéro) ;
9. la progression continue au-delà du point du backup ;
10. un résultat final est produit ;
11. le Job B atteint `SUCCEEDED` ;
12. le Job A reste `UNKNOWN`/`FAILED` selon le scénario, sans transition ;
13. aucun conflit avec la Central LoRA Library (import du seul Job B possible, A non importable).

Conformément à la règle du projet, **Claude doit exécuter lui-même ce smoke** lors de l'implémentation, le matériel documenté (Quadro P4000 8 Go, environnement CUDA sm_61 stabilisé) le permettant de façon fiable pour un entraînement LoRA minimal. **M138 n'exécute aucun entraînement réel.**

## 24. Séquencement recommandé en missions atomiques

Conformément à la demande explicite d'éviter une mission monolithique touchant simultanément Domain + filesystem + translator + process + UI + GPU réel, le découpage suivant est recommandé — quatre missions atomiques, testables et réversibles indépendamment :

**Mission A — Isolate Training concept folder per Job.** `create_job()` copie le dossier concept (images + légendes, §11.2) vers un sous-dossier propre au Job au lieu de référencer le dossier partagé au niveau Training. Corrige un risque latent déjà présent aujourd'hui (deux Jobs du même Training pouvant se marcher dessus), indépendamment du sort du Resume. Fichiers : `training_manager.py` (`create_job()`). Tests : le dossier concept d'un Job existant reste intact malgré un Prepare/Start ultérieur d'un autre Job du même Training ; non-régression complète de la suite Training existante. Aucun changement de comportement pour le cas actuel (un seul Job actif à la fois).

**Mission B — Bound Training backup disk growth.** Active `rolling_backup=True`/`rolling_backup_count=3` dans `build_training_config()` (§18/§19). Changement minimal, risque quasi nul, valeur indépendante du Resume. Tests : assertion sur les clés générées par `build_training_config()`.

**Mission C — Training Job lineage & can_resume primitives (sans exécution, sans UI).** Ajoute `resumed_from_job_id` à `TrainingJob` (§10), implémente `can_resume(job)` (§15) et la sélection du dernier backup valide (§16) comme fonctions pures testables sans GPU, implémente le verrou PID+horodatage (§8, écriture au `started`, lecture par `can_resume()`). Aucun lancement de process, aucune UI. Tests : détection de backup absent/incomplet/valide (fixtures de dossiers factices) ; `can_resume()` pour chaque état ; détection de verrou PID actif/obsolète (mockable, sans process réel) ; compatibilité ascendante `project.json` sans le nouveau champ.

**Mission D — Execute Resume + UI + smoke réel.** `resume_job(source_job)` dans `TrainingManager` (construit la config de reprise depuis le snapshot figé, §17), wiring inchangé vers `TrainingJobRunner`, bouton « Reprendre » + affichage lecture seule dans `TrainingPage` (§22), smoke réel exécuté par Claude (§23). Dépend de A, B, C déjà livrées.

**Première mission d'implémentation recommandée : Mission A.** C'est la plus petite, la plus sûre, elle corrige un risque déjà présent indépendamment de Resume, et elle est un prérequis strict de toute reprise sûre — un point de départ naturel qui apporte une valeur immédiate même si le reste du séquencement était interrompu ou reconsidéré.

## 25. Risques résiduels

- Le verrou PID+horodatage (§8) réduit fortement mais n'élimine pas totalement le risque de double-exécution — un scénario resterait non couvert (ex. horloge système modifiée entre les deux mesures) ; documenté comme risque résiduel accepté, pas comme un problème résolu à 100 %.
- La validation structurelle de niveau 3 (§14) ne garantit pas un chargement réussi à 100 % (pas de checksum) — le filet de sécurité final reste le crash bruyant d'OneTrainer lui-même en cas de corruption non détectée, correctement affiché comme tel par Toolkit.
- La dette de nettoyage filesystem sur suppression de Training (§20) reste ouverte, non traitée, à ne pas confondre avec le périmètre Resume.
- La cadence de backup exacte reste à valider empiriquement (§18) — le smoke réel de la Mission D constitue la première mesure fiable.

## 26. Dettes explicitement non traitées par cette mission

- `ApplicationSettings.comfyui_lora_name`/`comfyui_lora_strength` (dette Settings vérifiée, hors périmètre, conservée pour une mission future distincte).
- L'incident QMessageBox « Aucun personnage » de Mission 137 reste clos.
- `CharacterManager.delete()` sans garde (dette Mission 077).
- Suppression de Training laissant le filesystem orphelin (nouvelle découverte §20, hors périmètre Resume).

## 27. Exclusions explicites de M138

Aucune implémentation de Resume ; aucune modification de `TrainingManager`/`TrainingPage`/du translator OneTrainer ; aucun entraînement réel lancé ; aucune modification d'EventBus, de la Central LoRA Library, d'Inference ; aucun traitement du sujet Settings LoRA ; aucun système générique de checkpoints ; aucune refonte des `TrainingJob` existants sans nécessité démontrée.

## 28. Décisions désormais fermées (anciennement ouvertes)

1. ~~Liste exacte des champs à verrouiller~~ → résolu : aucun champ éditable en v1, config de reprise = copie verbatim du snapshot du Job source (§17).
2. ~~Suivi PID/verrou minimal~~ → résolu : retenu comme prérequis (Option C, §8), intégré à la Mission C.
3. ~~Reprise malgré Cancel~~ → résolu : exclue définitivement en v1 (§13).
4. ~~Politique de cleanup définitive~~ → résolu pour v1 : aucune suppression automatique de backups (§20), au-delà du bornage par `rolling_backup`.
5. Cadence `backup_after` cible exacte — **reste ouvert**, à valider empiriquement lors de la Mission D (smoke réel).
6. ~~Activation immédiate de `rolling_backup=True`~~ → résolu : oui, via une mission indépendante (Mission B), séquencée avant/parallèlement à la Mission A.
7. ~~Séquencement du correctif dataset/concept~~ → résolu : mission dédiée et antérieure (Mission A), pas intégrée à l'implémentation Resume elle-même.
