# Mission 100 — Training Execution Foundation (TrainingJob, QProcess Runner, Cancel Protocol)

> **CONTRAT VALIDÉ, IMPLÉMENTATION NON COMMENCÉE.** Ce document verrouille l'architecture d'exécution réelle d'OneTrainer après deux audits dédiés (architecture générale, puis verrouillage empirique) — voir section 3 pour la synthèse des faits établis. **Aucun entraînement OneTrainer réel, aucun GPU, aucune écriture sous `J:\Programmes\Onetrainer`** à aucun moment de cette mission — M100 doit être entièrement prouvable avec un faux processus déterministe. L'exécution réelle, la calibration en conditions réelles et l'import fonctionnel dans la Bibliothèque LoRA centrale sont différés à Mission 101 (section 15).

## 1. Contexte

L'audit post-Mission 099 a confirmé que la frontière laissée ouverte par Mission 097 — préparer une configuration OneTrainer sans jamais l'exécuter — reste le point qui bloque structurellement la promesse produit centrale (produire un LoRA utilisable). `TrainingManager.prepare_onetrainer_config()` (Mission 097) s'arrête à l'écriture d'un `onetrainer_config.json` ; `Training` (Domain) n'a aucun champ d'état d'exécution ; `TrainingPage` n'a aucun bouton au-delà de « Préparer la configuration OneTrainer ». Étant donné le risque (processus externe réel, incidents natifs déjà documentés en Mission 097/099, exigence explicite de conserver le contrôle du lancement des moteurs externes), l'architecte a exigé un audit architectural dédié avant tout code — lui-même mené en deux temps : un audit général de l'installation OneTrainer réelle et des options d'architecture, puis un audit de verrouillage empirique (tests réels sans GPU) sur les deux points de risque concrets identifiés (protocole callback IPC, protocole Cancel).

## 2. Objectif

Construire la fondation d'exécution — un `TrainingJob` Domain, un runner `QProcess` piloté depuis AI Studio Toolkit, un protocole Cancel à deux paliers, une arborescence de fichiers Job-owned, un canal de progression best-effort — entièrement validée par un faux processus déterministe, **sans jamais avoir besoin d'un GPU ou d'un entraînement OneTrainer réel pour clôturer la mission**. L'exécution réelle valide seulement, a posteriori et sous votre autorisation, ce que M100 aura déjà prouvé par ailleurs (Mission 101).

## 3. Audit préalable — synthèse des faits établis (deux audits déjà validés par l'architecte)

### 3.1 Fonctionnement réel d'OneTrainer

Installation auditée : `J:\Programmes\Onetrainer\` (identique à celle auditée en Mission 097, horodatage des fichiers sources inchangé). Aucun fichier de cette installation n'a été ni modifié ni exécuté pendant cette mission.

- **CLI headless réel** : [`scripts/train_remote.py`](file:///J:/Programmes/Onetrainer/scripts/train_remote.py) (`--config-path`, `--secrets-path`, `--callback-path`, `--command-path`), retenu de préférence à `scripts/train.py` — seul `train_remote.py` appelle `trainer.end()` dans un bloc `finally`, garantissant une tentative de sauvegarde finale même après un arrêt coopératif (`train.py` peut sauter cette sauvegarde selon `backup_before_save`).
- **Aucun point d'entrée Python à importer directement** — `create.create_trainer()` charge `torch`/CUDA/tout l'écosystème modèle dans le processus appelant. **Un processus séparé est requis, pas une préférence** : importer OneTrainer dans le processus PySide6 combinerait deux runtimes natifs lourds, exactement le terrain des `STATUS_HEAP_CORRUPTION` déjà documentés (Mission 097 §12, Mission 099).
- **Progression réelle disponible** : `TrainCallbacks.on_update_train_progress(TrainProgress, max_step, max_epoch)` est appelé à chaque étape réelle (`GenericTrainer.py:831-832`) — `TrainProgress.global_step`/`epoch`/`epoch_step` sont réels, un pourcentage authentique est calculable (jamais fabriqué). `TrainCommands.stop()` est un vrai mécanisme coopératif, vérifié par le trainer à la fin de chaque étape/epoch.
- **Trois catégories d'artefacts, jamais confondues par OneTrainer lui-même** : sauvegarde finale (`output_model_destination`, écrite uniquement si `self.one_step_trained`), checkpoints périodiques « save » (désactivés par défaut, `save_every_unit=NEVER`), et backups complets (`backup_before_save=True` par défaut, un backup avant chaque sauvegarde finale) — les deux derniers écrits sous `workspace_dir`, jamais sous `output_model_destination`.
- **Constat critique** : `workspace_dir` (défaut `"workspace/run"`), `cache_dir` (défaut `"workspace-cache/run"`) et `debug_dir` (défaut `"debug"`) sont des chemins **relatifs**, jamais renseignés par `src/engines/onetrainer_config.py` — sans correction explicite, ils atterriraient à l'intérieur de l'installation OneTrainer elle-même. Voir section 9.

### 3.2 Compatibilité M097 revalidée aujourd'hui

Test réel (chargement/parsing seul, zéro GPU, zéro entraînement) : configuration produite par `build_training_config()` pour SD15/SDXL/FLUX, rechargée via le vrai `TrainConfig.default_values().from_dict()` de l'installation actuelle. `config_version` réellement installé = **10**, identique à `_AUDITED_CONFIG_VERSION`. Migrations enregistrées jusqu'à la clé `9` seulement — envoyer `__version: 10` ne déclenche **aucune migration** (vérifié en instrumentant les fonctions de migration : aucune invoquée, pour les trois architectures). **Le contrat M097 reste valide, sans migration destructive, contre l'installation actuelle.**

### 3.3 Résultat empirique — protocole callback IPC de `train_remote.py` sous Windows

Reproduction fidèle de `write_request()`/`close_pipe()` (writer) et d'un lecteur imitant ce que ferait Toolkit (rename → lecture → suppression), lancés comme deux processus OS réels concurrents (`subprocess.Popen`), sans OneTrainer ni GPU :

| Scénario | Résultat mesuré |
|---|---|
| Rafale (200 écritures instantanées) + lecteur rapide (poll 10ms) | Le writer a levé une `PermissionError` non gérée sur `os.rename` |
| Rafale + lecteur lent (poll 500ms) | 201/201 reçus, zéro perte |
| Écriture cadencée (20ms/pas) + lecteur modéré | 51/51 reçus, zéro perte |
| Lecteur plus rapide que l'écriture cadencée | 50/51 — le dernier message perdu (course structurelle marqueur-de-fin vs dernière écriture) |
| Lecteur démarré en retard, chevauchant une rafale | 138/201 reçus (~31 % de perte), plusieurs exceptions de lecture réelles |

Dans le vrai `train_remote.py`, `TrainCallbacks` enveloppe chaque callback dans `contextlib.suppress(Exception)` — une erreur comme celle observée ne ferait donc jamais planter le processus d'entraînement réel, seulement disparaître silencieusement une mise à jour de progression précise. **Décision initiale (dépassée par la section 7 — voir plus bas) : canal callback strictement best-effort.** Un second examen a montré que même ce best-effort exigerait de désérialiser une classe interne OneTrainer (`TrainProgress`) dans le processus principal — la section 7 documente la décision finale : `callback.pipe` est abandonné entièrement, `stdout`/`stderr` devient l'unique canal.

### 3.4 Résultat empirique — protocole Cancel (`--command-path`)

Test réel avec la vraie classe `TrainCommands` d'OneTrainer et une reproduction fidèle de `command_thread_function()` (aucun `Trainer` créé, aucun GPU) :

- Fichier `command.pipe` **pré-créé (vide) avant démarrage du thread lecteur** → `stop()` transmis avec succès.
- Fichier **absent** au démarrage du thread lecteur → **le thread lecteur d'OneTrainer sort définitivement dès la première itération** (`except FileNotFoundError: break`) — confirmé empiriquement, `stop_command` jamais délivré ensuite même si le fichier est créé plus tard.
- 50 envois rapprochés (5ms d'intervalle) : zéro erreur — ce protocole (un seul objet picklé par écriture) est nettement plus robuste que le protocole callback.

**Conséquence contractuelle non négociable** : `command.pipe` doit être créé vide par Toolkit **avant** le lancement du sous-processus, jamais à la demande au clic Cancel (section 8).

## 4. Frontière stricte M100

- Aucune modification de Datasets/captions/Prompt Library/Inference/LoRA library fonctionnelle, hors ce qui est strictement nécessaire à l'appel de `LoRALibraryManager.import_lora()` en Mission 101 (aucune intégration fonctionnelle réelle en M100 — voir section 15).
- Aucune nouvelle tentative de correctif sur la dette Qt du harnais de test (Mission 099) — caractérisée et bornée, non remise en cause ici.
- **Aucun entraînement OneTrainer réel, aucun usage GPU, aucun démarrage/redémarrage d'OneTrainer** à aucun moment de cette mission.
- Aucune écriture, à aucun moment, sous `J:\Programmes\Onetrainer`.
- Si l'implémentation découvre un défaut de production hors de ce périmètre (Datasets, captions, autre Manager), arrêt et rapport avant toute correction — jamais de correction silencieuse sous couvert de cette mission.

## 5. Contrat Domain — `TrainingJob`

### 5.1 Ownership et création (Option B validée)

`prepare_onetrainer_config()` reste strictement `Training`-scoped, inchangée — aucun `TrainingJob` n'est créé par un Prepare, aussi souvent qu'il soit rejoué. Un `TrainingJob` est créé **uniquement** au clic Start, et capture à cet instant une **copie figée** de la configuration alors présente à `training/<id>/onetrainer_config.json` (voir section 9) — jamais une simple référence à ce chemin partagé, qui reste réécrit par tout Prepare ultérieur. **Un Prepare postérieur à un Start ne doit jamais pouvoir modifier rétroactivement la configuration associée à un `TrainingJob` déjà créé.**

**Point d'audit à valider explicitement en implémentation** (nouveau par rapport aux patterns déjà répertoriés dans `CLAUDE.md`) : `TrainingJob` est **`Training`-owned**, un niveau d'imbrication sous le pattern Character-owned déjà établi pour `Training` lui-même (`Character.trainings: list[Training]`) — proposé ici comme `Training.jobs: list[TrainingJob] = field(default_factory=list)`. Ce nesting n'est pas un des 4 patterns déjà listés dans `CLAUDE.md` ; il doit être audité pour lui-même (génération d'ID, réinitialisation d'un éventuel `active_job_id` runtime-only, événements) et non copié par analogie.

### 5.2 États validés

`starting` → `running` → `succeeded` | `failed` | `cancelled` | `unknown`. Pas d'état `prepared` — le Prepare reste une action `Training`-level sans lien avec le cycle de vie du Job.

- **`starting`** : un vrai état actif (pas transitoire/ignoré) — couvre l'intervalle entre la création du `TrainingJob` et la confirmation que `QProcess` a effectivement démarré. Un échec à ce stade (`QProcess.errorOccurred(FailedToStart)` — chemin invalide vers l'interpréteur du `venv` OneTrainer, `venv` absent) est une catégorie d'échec distincte, jamais confondue avec un échec survenu après un pas d'entraînement réel.
- **`running`** : le sous-processus est confirmé démarré (`QProcess.ProcessState.Running`).
- **`succeeded`** : code de sortie normal (0) **et** présence vérifiée de l'artefact final attendu (jamais l'un sans l'autre).
- **`failed`** : code de sortie non nul, ou `QProcess.ProcessError`/`CrashExit`, avec le code natif réel conservé dans le message d'erreur (précédent direct : diagnostic PowerShell de Mission 099).
- **`cancelled`** : arrêt résultant du protocole Cancel (section 8), qu'un artefact partiel existe ou non.
- **`unknown`** : voir section 12 — jamais transformé automatiquement en un autre état.

### 5.3 Champs persistés vs runtime-only

- **Persisté** (`project.json`, sous `Training.jobs`) : `job_id`, `state`, `config_snapshot_path` (chemin vers la copie figée, section 9), `expected_output_path`, `final_output_path` (renseigné seulement quand confirmé), `created_at`/`ended_at`, `error_message` (si `failed`), `imported_lora_id` (Mission 101 — champ réservé, jamais peuplé en M100).
- **Runtime-only** (jamais persisté) : handle/PID `QProcess`, dernier `global_step`/pourcentage calculé (best-effort, section 7), tampon de logs stdout/stderr récents.

## 6. Contrat runner — `QProcess`

- Lancement de `<onetrainer_path>\venv\Scripts\python.exe <onetrainer_path>\scripts\train_remote.py --config-path <snapshot Job> --command-path <command.pipe Job>` (**jamais `--callback-path`**, section 7) avec `cwd` fixé à `<onetrainer_path>` (nécessaire pour la résolution de `secrets.json`, tolérée absente). `<onetrainer_path>` provient exclusivement d'`ApplicationSettings.onetrainer_path`, résolu et revalidé via `resolve_onetrainer_launch()` (`src/engines/onetrainer_launch.py`) — jamais `python_path` (sémantique vérifiée non spécifique à OneTrainer, voir section 6bis).
- **`command.pipe` doit être créé (fichier vide) avant l'appel `QProcess.start()`**, jamais après — contrat non négociable (section 3.4).
- `stdout`/`stderr` capturés nativement via `QProcess` (`readyReadStandardOutput`/`readyReadStandardError`) — seul canal runtime, section 7.
- Terminaison détectée via `QProcess.finished(exitCode, exitStatus)` — `exitStatus == CrashExit` route vers `failed` avec le code natif réel, jamais présenté comme un échec métier générique. **Vérifié en premier, avant même `CrashExit`** : si un Cancel était en cours, l'état est toujours `cancelled`, quel que soit `exitStatus` — `QProcess.terminate()`/`kill()` provoquent eux-mêmes un `CrashExit` aux yeux de Qt, qui ne doit jamais être confondu avec un vrai crash non sollicité.
- **Aucune dépendance de l'état terminal (`succeeded`/`failed`/`cancelled`) à un quelconque canal de progression** — uniquement code de sortie + vérification de présence du fichier final (section 5.2).

### 6bis. `ApplicationSettings.python_path` — vérifié, délibérément non consommé

Sémantique vérifiée avant implémentation : `01_PRODUCT_REQUIREMENTS.md` §8 liste « Python » comme un item de Settings autonome, au même niveau que ComfyUI/Fooocus/Forge/AUTOMATIC1111/OneTrainer/Kohya_ss — jamais documenté comme « l'interpréteur destiné à OneTrainer ». L'installation OneTrainer auditée possède son propre `venv` dédié (`venv\Scripts\python.exe`, dépendances déjà installées) ; un `python_path` générique n'aurait presque certainement pas ces dépendances. **`python_path` n'est pas consommé par M100** — l'interpréteur est systématiquement dérivé de `onetrainer_path` seul (`resolve_onetrainer_launch()`). Le champ existant reste inchangé dans `ApplicationSettings`, non supprimé, simplement inutilisé pour l'instant.

## 7. Canal runtime OneTrainer — stdout/stderr uniquement (contrat révisé, remplace le best-effort callback)

**Décision finale, révisant la section 3.3/6 initiales** : `callback.pipe` est intégralement abandonné pour M100 — jamais créé, jamais consommé, jamais passé en argument (`train_remote.py` est lancé sans `--callback-path`, donc son propre `TrainCallbacks` reste un no-op pur côté OneTrainer et n'écrit jamais ce fichier).

**Raison** : `on_update_train_progress(train_progress: TrainProgress, ...)` transporte une vraie instance de `modules.util.TrainProgress.TrainProgress` — désérialiser cet enregistrement dans le processus principal exigerait d'y importer une classe interne OneTrainer, exactement la frontière que la section 3 refuse de franchir pour `TrainCommands` (Cancel). Contrairement à `on_update_status` (une simple chaîne), cet enregistrement est de loin le plus fréquent du flux (un par pas réel) — impossible à « sauter » sans le désérialiser, ce qui aurait bloqué la lecture de tout enregistrement de statut suivant.

**Contrat final** : `stdout`/`stderr` du sous-processus (capturés nativement par `QProcess`) sont l'**unique** canal de logs/progression/statut. Si la barre `tqdm` réelle d'OneTrainer est exploitable telle quelle dans ce flux, elle apparaît simplement comme texte brut dans les logs — **aucun parseur tqdm n'est développé** pour en extraire un pourcentage structuré. Une future progression structurée pourra être réévaluée seulement si l'usage réel démontre que c'est nécessaire (hors périmètre M100/M101 tant que ce besoin n'est pas démontré).

## 8. Contrat Cancel

`Cancel requested` → écriture de `TrainCommands.stop()` picklé dans `command.pipe` (déjà pré-créé, section 3.4/6) → attente bornée → `QProcess.terminate()` → attente bornée → `QProcess.kill()` si nécessaire.

Les deux délais sont des **constantes internes nommées et documentées** (ex. `COOPERATIVE_STOP_TIMEOUT_SECONDS`, `TERMINATE_TIMEOUT_SECONDS`), déterminées et testées avec le faux processus déterministe pendant cette mission — **aucun précédent dans le dépôt** pour un délai de terminaison de processus externe (le seul précédent, `InferencePage`, annule un `threading.Event` Python coopératif, pas un processus OS), donc aucune valeur n'est présumée a priori. Ces valeurs ne constituent **pas** une calibration définitive contre OneTrainer réel — cette calibration appartient explicitement à Mission 101.

## 9. Arborescence de fichiers — Job-owned, déterministe, jamais sous l'installation OneTrainer

```
<Workspace root>/training/<training_id>/
├── concept/                          (existant Mission 097, inchangé — Training-level)
├── onetrainer_config.json            (existant Mission 097, inchangé — configuration de préparation courante)
└── jobs/<job_id>/                    (NOUVEAU — un dossier autonome par tentative d'exécution)
    ├── onetrainer_config.json        (copie figée au moment du Start — section 5.1 — jamais réécrite ensuite)
    ├── output/lora.safetensors       (artefact final DE CE JOB, jamais partagé entre deux Jobs)
    ├── workspace/                    (workspace_dir OneTrainer — save/ et backup/ redirigés ici)
    ├── cache/                        (cache_dir OneTrainer)
    ├── debug/                        (debug_dir OneTrainer)
    └── command.pipe                  (--command-path — DOIT être pré-créé vide par Toolkit avant lancement)
```

Pas de `callback.pipe` (section 7 — jamais créé, `train_remote.py` lancé sans `--callback-path`). Les logs `stdout`/`stderr` capturés par `QProcess` restent en mémoire côté runner (affichés dans l'UI, section 13) — aucun fichier `.log` persisté sur disque par cette implémentation initiale, non requis par le contrat minimal.

**Changement de contrat par rapport à Mission 097**, explicitement validé ici : l'artefact final passe d'`training/<id>/output/` (Training-level, partagé, contrat M097 initial) à `jobs/<job_id>/output/` (Job-level) — nécessaire pour que deux runs successifs du même `Training` ne s'écrasent jamais l'un l'autre (exigence explicite de cette mission). Le fichier `training/<id>/onetrainer_config.json` produit par Prepare continue d'exister comme configuration de préparation éditable, mais **ne constitue plus** la configuration historique canonique d'un Job après Start — le snapshot du Job (`jobs/<job_id>/onetrainer_config.json`) remplit ce rôle.

## 10. `backup_before_save` — conservé à `True`

Décision validée : ne pas désactiver `backup_before_save` (défaut OneTrainer). Le désactiver supprimerait l'unique filet de sécurité en cas d'échec de la sauvegarde finale après un entraînement GPU réel potentiellement long — aucun artefact récupérable n'existerait alors. Le coût (espace disque du backup, potentiellement significatif) est réel mais borné et nettoyable a posteriori ; la perte sans backup ne l'est pas. Les dossiers concernés sont explicitement redirigés dans l'espace Job-owned (`jobs/<job_id>/workspace/`, section 9) — jamais sous l'installation OneTrainer. **Aucun mécanisme de nettoyage automatique supplémentaire** n'est introduit en M100 au-delà de ce que le code existant impose déjà.

## 11. Close guard

AI Studio Toolkit ne doit jamais permettre une fermeture normale silencieuse laissant un entraînement actif détaché — précédent architectural direct : `InferencePage.is_generation_active()`/`confirm_no_active_generation()` (Mission 085). États actifs couverts : **`starting` et `running`** (pas `unknown`, qui ne représente jamais un Job en cours réel — voir section 12). Comportement attendu, sans refonte générale du système de fermeture : blocage/confirmation explicite avant `MainWindow.closeEvent()`/`new_project()`/`open_project()`/`rename_project()` si un `TrainingJob` de la Character principale est `starting`/`running`, sur le modèle des guards déjà chaînés (Missions 069/078/079/083/084/085).

## 12. Sémantique de récupération après redémarrage/crash — `unknown`

Faits vérifiés (pas supposés) : `QProcess` ne peut structurellement pas se rattacher à un processus externe déjà en cours par PID — aucune API Qt ne le permet. Confirmer qu'un PID persisté correspond toujours au même processus (et non à un PID recyclé par Windows) nécessiterait une information supplémentaire non disponible en stdlib pur sans une dépendance nouvelle (type `psutil`) — **exclue sans validation explicite de l'architecte**. Puisque le close guard (section 11) bloque désormais la fermeture normale pendant un Job actif, un `TrainingJob` retrouvé `starting`/`running` au redémarrage **ne peut provenir que d'un crash/kill forcé/coupure**, jamais d'une fermeture normale.

**Contrat** : au démarrage, tout `TrainingJob` persisté dans un état actif (`starting` ou `running`) sans supervision `QProcess` disponible **passe à `unknown`** — jamais réputé `succeeded`/`failed`/`cancelled` sans preuve. La présence de `final_output_path` sur disque peut être affichée comme un indice non autoritaire, jamais transformée automatiquement en `succeeded`. Résolution laissée à une action manuelle de l'utilisateur (constat, jamais une suppression automatique). **Aucun système de réattachement n'est demandé ni construit en M100.**

**Limite acceptée, à documenter explicitement** : puisque cette mission ne conçoit pas encore de trainings volontairement détachés, un crash d'AI Studio Toolkit (pas une fermeture normale, empêchée par le guard) peut laisser un vrai processus OneTrainer orphelin continuer à tourner en Mission 101, invisible depuis Toolkit, jusqu'à intervention manuelle — risque accepté de cette première itération, pas un oubli.

## 13. UI minimale M100

Extension de `TrainingPage` (aucune refonte) : **Start** (actif uniquement après un Prepare réussi **et** si `ApplicationSettings.onetrainer_path` résout correctement — sinon désactivé avec une indication actionnable dans `job_state_label`, jamais un dialogue modal juste pour un bouton indisponible, section 6bis), zone d'état textuelle (`Starting…`/`Running…`/`Annulation en cours…`), zone de logs bruts stdout/stderr (`QPlainTextEdit` en lecture seule, aucun parsing), **Cancel** (actif uniquement pendant un Job actif), affichage du résultat final `Succeeded`/`Failed`/`Cancelled` (message + chemin de l'artefact si `succeeded`, sans bouton d'import — Mission 101). **Aucune barre `%`** (section 7 — décision finale, callback.pipe abandonné).

## 14. Tests et validation prévus — deux pistes distinctes (section 17bis)

- **Faux processus de test** (`tests/integration/_fake_onetrainer_process.py`) : un script Python déterministe, jamais un composant de production, simulant `train_remote.py` (accepte `--config-path`/`--command-path`, respecte ou ignore un stop coopératif via `command.pipe` selon variable d'environnement, se termine avec un code configurable, écrit ou non le fichier de sortie, peut simuler un crash natif via `os.abort()`).
- **Scénarios couverts** (`tests/integration/test_training_job_runner.py`, faux processus) : succès déterministe (exit 0 + fichier présent) → `succeeded` ; échec code non-zéro → `failed` ; `FailedToStart` → jamais `running` ; crash (`CrashExit` réel via `os.abort()`) → `failed` avec détail natif conservé, jamais confondu avec un Cancel réel (section 6, ordre des vérifications) ; logs stdout/stderr effectivement capturés ; Cancel coopératif de bout en bout → `cancelled` ; idempotence de `cancel()` ; escalade `terminate()`/`kill()` vérifiée par appel direct des méthodes avec `QProcess` espionné (jamais dépendante du timing réel de terminaison Windows).
- **Domain/Manager** (`tests/integration/test_training_roundtrip.py`) : plusieurs `TrainingJob` successifs isolés, snapshot de config réellement immuable après un Prepare postérieur, `command.pipe` pré-créé (jamais `callback.pipe`, qui n'existe plus du tout dans `TrainingJobPaths`), rollback sur échec de `save()`, événements publiés, récupération `starting`/`running` → `unknown` au redémarrage.
- **Non requis pour clôturer M100** : tout smoke test contre le vrai `train_remote.py`/OneTrainer avec GPU — différé à Mission 101, sous autorisation explicite. Un smoke test réel **sans GPU** (runner réel + faux processus réel + `QApplication` réelle) est en revanche exigé avant clôture — voir section 17bis.2.

## 15. Hors périmètre — différé à Mission 101 (Real OneTrainer Lifecycle)

- Premier entraînement réel, sur GPU, avec autorisation explicite préalable pour chaque lancement.
- Validation réelle SD15/SDXL (contenu/validité du `.safetensors` produit, chargement dans ComfyUI si retenu à ce moment).
- Toute réévaluation d'une progression structurée (barre `%`) — hors périmètre tant que l'usage réel n'en démontre pas le besoin (section 7).
- Calibration réelle des délais de Cancel (section 8) — les valeurs choisies en M100 avec le faux processus ne sont pas présentées comme définitives.
- Intégration fonctionnelle réelle avec `LoRALibraryManager.import_lora()` — l'architecture (champ `imported_lora_id` réservé, bouton d'import différé) peut être préparée en M100 si strictement nécessaire à la cohérence du Domain, mais **aucune intégration fonctionnelle réelle** n'est requise pour clôturer M100.
- Toute décision produit encore ouverte identifiée par l'audit (ex. contrat exact si l'utilisateur souhaite un jour des trainings volontairement détachés) reste hors périmètre des deux missions.
- **Dette actée par Mission 097** (`_AUDITED_CONFIG_VERSION`, voir `docs/PROJECT_CONTEXT.md` § « Problèmes connus / dettes ») : cette dette désigne explicitement *« la mission qui lancera réellement OneTrainer »* pour décider si une vérification dynamique de `TrainConfig.config_version` doit devenir une précondition d'exécution. M100 revalide (section 3.2) que la valeur figée reste correcte aujourd'hui, mais ne lance rien de réel — cette décision (précondition dynamique ou non) revient donc à Mission 101, au moment du premier lancement réel.
- **Résolution de la dette M100 §17bis** (voir cette section) — réévaluée uniquement si elle affecte l'application réelle, le runner réel, plusieurs tests subprocess, ou la fiabilité générale de la validation ; jamais automatiquement absorbée dans une prochaine mission.

## 16. Critères de clôture M100

1. `TrainingJob` Domain + persistance implémentés, `Training`-owned, ownership auditée pour elle-même (section 5.1).
2. Plusieurs `TrainingJob` successifs pour un même `Training`, chacun isolé (config, output, workspace/cache/debug jamais partagés).
3. Snapshot de configuration réellement immuable après tout Prepare/modification postérieurs à un Start.
4. Runner `QProcess` fonctionnel contre le faux processus : succès déterministe, échec code non-zéro, `FailedToStart`, crash (`CrashExit`).
5. `stdout`/`stderr` comme unique canal runtime, implémenté et testé — aucun `callback.pipe` créé ni consommé (section 7).
6. Protocole Cancel complet et testé : coopératif (helper externe, section 4) → `terminate()` → `kill()`, avec `command.pipe` systématiquement pré-créé avant lancement.
7. Close guard actif sur `starting`/`running`, sur le modèle Mission 085.
8. Récupération d'un état actif persisté vers `unknown` au redémarrage, jamais une invention de résultat.
9. Aucune écriture, à aucun moment testé, sous l'installation OneTrainer réelle.
10. **Piste A — suite principale monoprocessus** : verte, terminaison normale, zéro dialogue parasite, zéro `STATUS_HEAP_CORRUPTION` (voir section 17bis pour le détail exact de ce qui en est exclu et pourquoi).
11. **Piste B — test subprocess isolé** (`tests/integration/isolated_test_onetrainer_cancel_helper.py`) : exécuté séparément dans un processus Python frais, intégralement vert — obligatoire pour la clôture, documenté comme volontairement exclu de la Piste A, jamais un test oublié.
12. **Smoke réel hors GPU** (section 17bis.2) : runner réel + faux processus réel + `QApplication` réelle, dans un processus autonome hors harnais de test — démarrage, réception stdout/stderr, terminaison, fermeture propre, tous confirmés.
13. Zéro entraînement GPU/OneTrainer réel exécuté à quelque moment que ce soit de cette mission.
14. `git diff --check` propre, aucun artefact de diagnostic dans le dépôt, tous les scripts temporaires restés en scratchpad de session.

## 17bis. Incident `STATUS_HEAP_CORRUPTION` rencontré pendant l'implémentation — diagnostic, décision, dette bornée

### 17bis.1 Diagnostic

En validant la suite complète (`python -m unittest discover -s tests -p "test_*.py"`), un code de sortie opaque (127 sous Git Bash) sans résumé est apparu — signature identique à celle déjà rencontrée en Mission 097/099. Code de sortie réel obtenu via `subprocess.run()` (Python, contournant l'opacité de Git Bash) : **`3221226356` = `0xC0000374` = `STATUS_HEAP_CORRUPTION`**, reproduit deux fois de suite.

Bissection réalisée avant tout rapport :
- Les 3 nouveaux fichiers de test M100 passent chacun proprement en isolation.
- Suite complète sans les 3 nouveaux fichiers (mais avec tout le reste du code M100 en place) : **1955/1955, OK**.
- Suite complète + `test_training_job_runner.py` seul ajouté : **1967/1967, OK**.
- **Suite complète + `test_onetrainer_cancel_helper.py` (devenu `isolated_test_onetrainer_cancel_helper.py`) seul ajouté : `0xC0000374`, reproduit deux fois de suite.**

Constat notable : ce fichier n'utilise ni Qt ni `QProcess` — uniquement `subprocess.run()` de la stdlib. Le déclencheur n'est donc pas spécifique à `QProcess`, mais à la création d'un vrai processus enfant OS (quel que soit le mécanisme) après l'accumulation cumulative de milliers d'objets Qt déjà caractérisée comme dette de harnais en Mission 097/099 — jamais observé en isolation, jamais observé dans l'application réelle (voir 17bis.2).

### 17bis.2 Distinction harnais vs application réelle — smoke test réel

Un script autonome (hors `unittest`, hors accumulation de ~2000 tests) a été exécuté dans un processus Python frais : `QApplication` réelle, `TrainingJobRunner` réel pointé vers le faux processus déterministe réel (jamais un mock), démarrage réel, réception réelle de `stdout`/`stderr` via les signaux `QProcess`, détection réelle de la terminaison (`finished` avec `state="succeeded"`), fermeture propre de la `QApplication`. **Résultat : PASS, exit code 0, zéro crash natif.** Ceci confirme que le problème est structurellement confiné au harnais de test après accumulation, jamais dans le composant réel ni dans son usage réel par l'application.

### 17bis.3 Décision

Aucune correction de cette dette n'est tentée dans M100 — ni modification de code de production, ni réordonnancement artificiel de la suite, ni suppression du test. `tests/integration/test_onetrainer_cancel_helper.py` est renommé `isolated_test_onetrainer_cancel_helper.py` (mécanisme le plus simple compatible avec le harnais actuel : ce nom ne correspond plus au motif canonique `test_*.py` utilisé par `discover`, donc n'est plus jamais ramassé par la suite principale — sans nouvelle infrastructure de test). Il reste versionné, continue de vérifier réellement le lancement d'un sous-processus, et doit être exécuté séparément (`python -m unittest tests.integration.isolated_test_onetrainer_cancel_helper -v`) comme validation obligatoire distincte de M100 (Piste B, critère de clôture 11).

### 17bis.4 Dette actée, bornée, non transformée en mission automatique

**La longue suite Qt monoprocessus peut provoquer un `STATUS_HEAP_CORRUPTION` lorsqu'un test crée un nouveau processus OS après l'accumulation cumulative des widgets Qt déjà caractérisée en Mission 097/099.** Les tests nécessitant un vrai sous-processus peuvent donc devoir être exécutés dans un processus de test frais, séparé de la suite principale, jusqu'à résolution future du lifecycle global du harnais. Cette dette n'est **pas** automatiquement la prochaine mission — elle sera réévaluée uniquement si elle affecte l'application réelle, le runner réel, plusieurs tests subprocess (au-delà de celui-ci), ou la fiabilité générale de la validation.
