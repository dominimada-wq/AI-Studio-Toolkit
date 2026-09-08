# Mission 101 — Real OneTrainer Smoke Training

> **MISSION CLÔTURÉE — SMOKE RÉEL RÉUSSI DE BOUT EN BOUT.** Cette mission n'était pas une mission de développement — l'audit post-Mission 100 n'avait identifié aucun blocage de code entre AI Studio Toolkit et un premier entraînement OneTrainer réel. Le premier `TrainingJob` réel s'est terminé `succeeded`, avec un `.safetensors` réellement produit (78 489 976 octets), après deux corrections locales à l'installation OneTrainer elle-même (jamais au code AI Studio Toolkit) — voir section 12 pour le récit complet et section 13 pour la distinction explicite entre ce que cette mission valide côté Toolkit et ce qui reste spécifique à cette installation.

## 1. Contexte

L'audit post-Mission 100 (voir `docs/PROJECT_CONTEXT.md`) a tracé le chemin complet `TrainingPage.start_training()` → `TrainingManager.create_job()` → `TrainingJobRunner.start()` → `resolve_onetrainer_launch()` → `QProcess` lançant `train_remote.py`, et a confirmé contre le vrai OneTrainer installé (`J:\Programmes\Onetrainer\`) que la configuration générée par `src/engines/onetrainer_config.py` est suffisante pour un premier run réel. Les deux seuls éléments manquants identifiés sont une configuration utilisateur (`ApplicationSettings.onetrainer_path`) et un Training réellement paramétré — aucun des deux n'est un défaut de code. Mission 101 ne construit donc rien de nouveau : elle exécute, sous autorisation, le premier run réel et documente ce qui se passe réellement.

## 2. Objectif

Vérifier que la chaîne technique déjà livrée par Mission 100 fonctionne réellement, de bout en bout, avec un run OneTrainer minimal — **jamais** d'évaluer la qualité du LoRA produit, jamais de développer une nouvelle capacité.

## 3. Périmètre exact du smoke

- Moteur : OneTrainer uniquement.
- Architecture : `SD15`.
- Modèle de base : `J:\Programmes\ComfyUI\models\checkpoints\v1-5-pruned-emaonly-fp16.safetensors` (fichier réel déjà présent sur la machine, confirmé chargeable par `StableDiffusionModelLoader` lors de l'audit post-M100).
- Dataset : 1 image réelle, caption/trigger word minimal.
- Résolution : 512.
- Epochs : 1.
- Batch size : 1 (défaut OneTrainer, jamais exposé par Toolkit).
- Tous les autres paramètres : valeurs par défaut actuelles de Toolkit (`learning_rate`/`lora_rank`/`lora_alpha` inchangés) — aucun nouveau réglage n'est ajouté pour ce smoke.

## 4. Étapes techniques attendues

1. Prepare (`prepare_onetrainer_config()`) réussi sur cette Training minimale.
2. Start réel depuis AI Studio Toolkit (`TrainingPage.start_training()`).
3. Lancement réel de `train_remote.py` via `QProcess`.
4. Chargement réel du checkpoint SD15 ci-dessus.
5. Au moins un vrai pas d'entraînement exécuté.
6. Terminaison normale du processus OneTrainer (`trainer.end()` atteint).
7. Création réelle de `jobs/<job_id>/output/lora.safetensors`.
8. AI Studio Toolkit reconnaît le Job comme `succeeded` (état persisté + fichier vérifié par `TrainingJobRunner`).

La qualité du `.safetensors` produit n'est **pas** évaluée par cette mission.

## 5. VRAM — aucune garantie présumée

La Quadro P4000 (8 Go) rend ce scénario SD1.5 minimal raisonnable **a priori**, mais l'absence d'OOM ou de tout autre problème réel n'est jamais présumée acquise avant le run réel. En cas de limite VRAM ou de tout autre problème réel rencontré pendant le run, la mission s'arrête et rapporte les faits (section 6) — aucune modification préventive n'est faite pour éviter une erreur hypothétique.

## 6. En cas d'échec réel — procédure stricte

Si le run échoue, à quelque étape que ce soit, cette mission :

- capture `stdout`/`stderr` réels du processus OneTrainer ;
- rapporte l'état final exact du `TrainingJob` (state/error_message) ;
- rapporte l'exception/trace réelle observée (jamais reformulée) ;
- constate les fichiers réellement produits ou absents (`jobs/<job_id>/...`) ;
- rapporte la configuration Job réellement utilisée (`onetrainer_config.json` du snapshot).

Puis **s'arrête avant toute correction qui nécessiterait une nouvelle décision architecturale** et attend la décision de l'architecte. Un correctif strictement local et manifestement nécessaire au seul succès du smoke (jamais une refonte, jamais une nouvelle abstraction) pourra être proposé sur la base de cette preuve — jamais implémenté avant que l'architecte n'ait vu les faits.

## 7. Configuration préalable (hors périmètre de cette mission)

`ApplicationSettings.onetrainer_path` doit être renseigné avec `J:\Programmes\Onetrainer` par l'architecte lui-même, via l'usage normal de Settings — cette mission ne configure jamais Settings à la place de l'architecte et ne modifie aucun code pour cela.

## 8. Cancel — explicitement non déclenché dans ce smoke

Le premier objectif est un run normal jusqu'à la sauvegarde finale. Cancel n'est **pas** volontairement déclenché pendant ce premier smoke. La calibration réelle du protocole Cancel (`COOPERATIVE_STOP_TIMEOUT_SECONDS`/`TERMINATE_TIMEOUT_SECONDS`, actuellement calibrés uniquement contre le faux processus de Mission 100) ne sera vérifiée séparément que si l'architecte la juge encore nécessaire après ce premier succès.

## 9. Hors périmètre strict — ne pas ajouter à cette mission

- Progression structurée (barre `%`, parsing tqdm).
- Réintroduction de `callback.pipe`.
- Import automatique dans la Bibliothèque LoRA centrale.
- Nouveaux réglages Training.
- Abstraction multi-engine Training (OneTrainer reste l'unique moteur prévu).
- Reprise/reconnexion avancée après crash.
- Amélioration générale de `TrainingPage`.
- Optimisation des paramètres d'entraînement.
- Support additionnel Fooocus/Forge/ComfyUI (hors périmètre Training).

## 10. Critères de clôture — tous satisfaits

1. Les 8 étapes de la section 4 ont été observées réellement, à la tentative finale (section 12) — **satisfait**.
2. Les deux échecs réels intermédiaires ont été intégralement rapportés selon la section 6, sans correction spéculative — **satisfait**.
3. Aucune modification de code n'a été faite avant l'observation du run réel qui l'a rendue nécessaire — **satisfait** (voir section 12 : chaque correction suit un échec réel documenté, jamais anticipée).
4. Aucun Cancel volontaire n'a été déclenché — **satisfait**.
5. Aucune nouvelle capacité listée en section 9 n'a été ajoutée — **satisfait**.

## 11. Autorisation

Ce document a servi de contrat avant exécution. Chaque lancement réel d'OneTrainer (GPU inclus) et chaque correction d'environnement ont été exécutés uniquement après autorisation explicite et séparée de l'architecte — voir section 12 pour l'enchaînement réel des autorisations et des faits.

## 12. Résultat réel — chronologie complète

Quatre tentatives réelles au total, chacune sous autorisation ponctuelle distincte, aucune automatique :

1. **Tentative 1 — échec avant tout lancement.** `TrainingJobRunner.start()` a refusé de lancer `QProcess` : `ApplicationSettings.onetrainer_path` était vide sur la machine (`resolve_onetrainer_launch()` a levé `OneTrainerLaunchError`), contrairement à ce qui était supposé configuré — un simple réglage utilisateur non réellement sauvegardé, aucun défaut de code. Corrigé par l'architecte lui-même dans Settings.
2. **Tentative 2 — lancement réel, échec GPU.** `train_remote.py` a réellement démarré, chargé torch/CUDA, tenté un vrai calcul GPU, et a échoué avec `torch.AcceleratorError: CUDA error: no kernel image is available for execution on the device`. Cause confirmée par audit read-only dédié : l'installation OneTrainer utilisait `torch==2.12.0+cu130`/`torchvision==0.27.0+cu130` — CUDA 13.0 a supprimé la compilation offline pour toute architecture antérieure à sm_75, or la machine embarque une **Quadro P4000 (Pascal, compute capability sm_61, 8 Go VRAM)**, absente de `torch.cuda.get_arch_list()` sur ce build.
3. **Correction d'environnement (autorisée séparément, appliquée uniquement dans le venv OneTrainer)** : mêmes versions `torch==2.12.0`/`torchvision==0.27.0`, seul le tag de build CUDA change vers `+cu126` (dernier index PyTorch officiel compilant encore pour Pascal) — `pip uninstall torch torchvision` puis `pip install torch==2.12.0 torchvision==0.27.0 --index-url https://download.pytorch.org/whl/cu126 --no-deps`. Vérifié après installation : `sm_61` présent dans `torch.cuda.get_arch_list()`, et un vrai calcul CUDA (tenseur + `backward()` + `torch.cuda.synchronize()`) réussit.
4. **Tentative 3 — GPU fonctionnel, échec après le vrai step.** Avec l'environnement corrigé : chargement réel du checkpoint, **1 vrai step GPU exécuté avec une vraie loss (`loss=0.0664`)**, epoch réellement complété — puis le processus a échoué (code de sortie 1) dans le bloc `finally` de `train_remote.py`, avant `trainer.end()` (donc avant toute sauvegarde). Diagnostic confirmé par preuve indirecte (`command.pipe` toujours présent, 0 octet, jamais supprimé ; `output/` vide) puis par audit read-only du code source : `close_pipe()` (`scripts/train_remote.py`) appelle `os.remove(filename)` **pendant que le fichier est encore ouvert** (`with open(filename, 'wb'): os.remove(filename)`) — Windows refuse de supprimer un fichier dont un handle est encore ouvert, contrairement à POSIX. Confirmé identique sur `master` upstream (`Nerogar/OneTrainer`) à la date de l'audit ; aucune issue/PR existante ne couvre ce cas précis (probablement jamais exercé côté Windows en amont, `--command-path` étant surtout utilisé par la fonctionnalité Cloud d'OneTrainer, exécutée sur Linux).
5. **Correction locale minimale (autorisée séparément, un seul fichier, une seule fonction, appliquée uniquement dans l'installation OneTrainer)** : dans `J:\Programmes\Onetrainer\scripts\train_remote.py`, `close_pipe()` referme explicitement le handle avant de tenter la suppression :
   ```python
   def close_pipe(filename):
       with open(filename, 'wb'):
           pass
       with suppress(FileNotFoundError):
           os.remove(filename)
   ```
   Vérifié par `py_compile` (syntaxe/imports OK) et par un test réel sans GPU (création réelle du fichier, appel réel de `close_pipe()`, suppression réelle sans exception, double appel protégé par `suppress(FileNotFoundError)`) avant toute nouvelle tentative GPU.
6. **Tentative 4 — succès complet.** Chargement réel du checkpoint, 1 vrai step GPU (`loss=0.0664`), epoch complété, backup créé (`backup_before_save=True`), sauvegarde finale réellement écrite, processus terminé avec le code de sortie 0. `TrainingJob` reconnu `succeeded` par AI Studio Toolkit. `jobs/<job_id>/output/lora.safetensors` réellement présent, **78 489 976 octets**, vérifié indépendamment sur disque.

## 13. Validation Toolkit vs adaptations locales à cette installation — distinction explicite

**Validation Toolkit : PASS.** La chaîne `TrainingPage.start_training()` → `TrainingManager.create_job()` → `TrainingJobRunner.start()` → `resolve_onetrainer_launch()` → `QProcess` → `train_remote.py` → `TrainingManager.update_job_state()` fonctionne de bout en bout, sans aucune modification de code AI Studio Toolkit à aucun moment de cette mission. Toutes les corrections ont eu lieu strictement en dehors du dépôt, dans l'installation OneTrainer elle-même.

**Adaptations locales à cette installation OneTrainer — jamais des règles universelles** :
1. **Build PyTorch compatible Pascal** (`torch==2.12.0+cu126`/`torchvision==0.27.0+cu126`) : solution ponctuelle pour cette machine précise (Quadro P4000). `requirements-cuda.txt` du dépôt OneTrainer reste pinné sur `+cu130` en amont ; une future réinstallation/mise à jour d'OneTrainer depuis ce fichier réintroduirait l'incompatibilité. Ne doit jamais devenir une hypothèse codée en dur du type « OneTrainer ⇒ toujours cu126 ».
2. **Patch Windows ponctuel de `train_remote.py`** (`close_pipe()`) : correctif local non versionné d'un fichier tiers, absent de tout dépôt officiel OneTrainer à la date de cette mission. Sera silencieusement perdu si OneTrainer est réinstallé/mis à jour, à réappliquer manuellement si nécessaire après une telle opération.

Ces deux adaptations sont des particularités documentées de **cette installation OneTrainer sur cette machine** — jamais une caractéristique générale d'OneTrainer, jamais une contrainte à coder en dur dans AI Studio Toolkit. Le besoin futur d'un diagnostic automatique de compatibilité GPU/PyTorch (voir `docs/PROJECT_CONTEXT.md`, section « Besoins futurs ») reste non prioritaire et non implémenté.

## 14. Clôture Git

Aucune modification de `src/` ni de `tests/` dans cette mission — le dépôt AI Studio Toolkit lui-même n'a subi aucun changement fonctionnel ; les deux corrections réelles ont eu lieu exclusivement dans l'installation externe `J:\Programmes\Onetrainer\`, hors de ce dépôt. Le commit substantiel de cette clôture est documentaire (même principe que Mission 099) — son hash exact et le tag `v0.2-mission101` sont enregistrés dans le commit qui suit immédiatement celui-ci dans l'historique Git, jamais figés en dur ici (principe de non-auto-référence, `docs/PROJECT_CONTEXT.md`).
