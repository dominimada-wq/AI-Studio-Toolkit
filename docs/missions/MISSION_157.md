# Mission 157 — Guarantee Training Job Terminalization on Filesystem Inspection Failure

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `TrainingJobRunner._on_process_finished()` (`src/ui/training_job_runner.py`) et `resolve_onetrainer_launch()` (`src/engines/onetrainer_launch.py`) réalisaient chacun deux inspections `Path(...).is_file()` non protégées. Une `OSError` (verrou antivirus, partage réseau interrompu — hors des `_IGNORED_ERRNOS`/`_IGNORED_WINERRORS` de `pathlib`) laissait s'échapper une exception brute avant que le Job ne puisse atteindre un état terminal, le laissant bloqué indéfiniment dans `STARTING` ou `RUNNING` (`TRAINING_JOB_ACTIVE_STATES`), bloquant à son tour `MainWindow.closeEvent()`/`new_project()`/`open_project()`/`rename_project()`. Corrigé sans filet générique — chaque inspection est protégée précisément à sa propre frontière, avec une distinction sémantique à trois états (présent / absent avec certitude / inspection impossible) préservée jusqu'au message final.

## 1. Invariant lifecycle

**Une inspection filesystem inconclusive ne doit jamais laisser un Training Job silencieusement bloqué dans un état actif (`STARTING`/`RUNNING`) — le Job doit toujours atteindre un état terminal explicite (`succeeded`/`failed`/`cancelled`) via `_finish()`, quelle que soit l'issue de l'inspection de son fichier de sortie ou de la résolution de son lancement.**

## 2. 4a — `TrainingJobRunner._on_process_finished()`

Deux inspections `Path(self._job_paths.expected_output_path).is_file()` (chemin Cancel et chemin normal) n'étaient enveloppées d'aucun `try/except`. Une `OSError` interrompait la méthode avant tout appel à `_finish()` — `self.finished` jamais émis, `TrainingPage._on_job_finished()` jamais exécuté, `update_job_state()` jamais appelé : le Job restait bloqué en `"running"` jusqu'à un redémarrage complet de l'application (`_recover_stale_jobs()`).

## 3. 4b — `resolve_onetrainer_launch()`

Deux inspections `is_file()` (exécutable Python du venv OneTrainer, `train_remote.py`) non protégées. Appelée par `TrainingPage` (gating du bouton Start, faible risque) et par `TrainingJobRunner.start()` — dans ce second cas, le Job vient d'être créé en état `"starting"` par `TrainingManager.create_job()` ; si l'`OSError` s'échappe, `start()` s'interrompt avant `QProcess.start()`, aucun signal `started`/`finished` n'est jamais émis, et le Job reste bloqué en `"starting"` indéfiniment — même conséquence catastrophique que 4a, déclenchée avant le lancement plutôt qu'après.

## 4. Pourquoi 4a et 4b appartiennent à la même mission

Un seul invariant lifecycle (§1) est en jeu dans les deux cas — la même garantie de terminalisation du Job, aux deux extrémités de son cycle de vie (démarrage et fin). Le risque de regroupement est bas : le correctif 4b ne touche jamais `training_job_runner.py`, les tests des deux volets sont totalement orthogonaux, et le titre même de la mission (« Guarantee Training Job Terminalization ») décrit une garantie unique sur l'ensemble du cycle de vie, pas seulement sur sa terminaison post-process.

## 5. Frontières de responsabilité distinctes

- **4a** : la responsabilité est intégralement interne à `TrainingJobRunner` — cette méthode ne dispose d'aucun mécanisme préexistant de traduction d'exception ; le correctif introduit une protection nouvelle, locale.
- **4b** : la responsabilité est entièrement dans `resolve_onetrainer_launch()` elle-même — `TrainingJobRunner.start()` possédait déjà un traitement correct et déjà testé de `OneTrainerLaunchError` (`except OneTrainerLaunchError as exc: self._finish("failed", str(exc), ""); return`) ; il suffisait que la fonction honore son propre contrat documenté. **`TrainingJobRunner.start()` n'a donc nécessité aucune modification** — vérifié par le test préexistant `test_missing_onetrainer_settings_reports_failed_before_launching`, toujours vert sans changement.

## 6. Pourquoi un `except Exception` global a été rejeté

Un filet générique autour de `_on_process_finished()` masquerait une véritable erreur de programmation (ex. un `AttributeError` sur `self._job_paths`) en la faisant passer pour un `Training failed` ordinaire — contraire au principe de ne valider qu'aux frontières réelles du système (`CLAUDE.md`). Le recensement exhaustif de la méthode (audit de conception préalable) n'a identifié que les deux `is_file()` comme points de défaillance réels ; aucun autre appel de cette méthode ne peut raisonnablement lever. Seules ces deux primitives sont protégées, via un helper dédié — jamais un filet générique.

## 7. Helper 4a — trois états

```python
def _inspect_expected_output(self):
    path = self._job_paths.expected_output_path
    try:
        exists = Path(path).is_file()
    except OSError as error:
        return None, f"could not determine whether the output file exists at {path}: {error}"
    if exists:
        return True, ""
    return False, "OneTrainer process exited successfully but no output file was found"
```

`is_present` vaut `True` (présent, certitude), `False` (absent, certitude) ou `None` (inspection impossible) — jamais deviné. `detail` ne porte un message utile que lorsque `is_present` n'est pas `True`.

## 8. Comportement — chemin normal (`NormalExit`, `exit_code == 0`)

| État `is_present` | Résultat | Message |
|---|---|---|
| `True` | `succeeded` (inchangé) | — |
| `False` | `failed` (inchangé) | `"OneTrainer process exited successfully but no output file was found"` (texte historique préservé au caractère près) |
| `None` (nouveau) | `failed` | `"could not determine whether the output file exists at {path}: {error}"` |

Jamais `succeeded` sans preuve positive.

## 9. Comportement — Cancel (préservation M148)

```python
if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
    is_present, _ = self._inspect_expected_output()
else:
    is_present = False
if is_present is True:
    self._finish("succeeded", "", self._job_paths.expected_output_path)
else:
    self._finish("cancelled", "", "")
```

L'évaluation court-circuitée est préservée à l'identique : l'inspection filesystem n'est **jamais** effectuée si `exit_status`/`exit_code` ne qualifient pas déjà pour un succès potentiel — exactement le comportement historique. Seul `is_present is True` déclenche `succeeded` ; `False` et `None` produisent tous deux `cancelled`, jamais une confusion entre absence prouvée et inspection impossible. Les tests M148 (`test_cancel_with_nonzero_exit_code_still_reports_cancelled`, `test_cancel_with_crash_exit_still_reports_cancelled`, `test_cooperative_cancel_with_output_already_written_reports_succeeded`) restent verts sans aucune modification — confirmé par exécution explicite (§14).

## 10. Contrat `OSError → OneTrainerLaunchError` (4b)

```python
try:
    python_executable_present = python_executable.is_file()
except OSError as error:
    raise OneTrainerLaunchError(
        f"Could not determine whether OneTrainer's Python environment "
        f"is present at {python_executable}: {error}"
    ) from error
...
try:
    script_path_present = script_path.is_file()
except OSError as error:
    raise OneTrainerLaunchError(
        f"Could not determine whether OneTrainer's train_remote.py is "
        f"present at {script_path}: {error}"
    ) from error
```

Deux blocs `try/except` distincts (un par inspection) plutôt qu'un seul englobant — chaque message nomme précisément l'élément concerné, le chemin exact et l'erreur filesystem sous-jacente. Chaînage `raise ... from error` préservé, cohérent avec le pattern déjà établi trois fois dans le dépôt (Forge M156, ComfyUI M108, Ollama M081). Aucune nouvelle classe d'exception.

## 11. `TrainingManager.create_job()` — explicitement hors scope

Son `is_file()` (ligne ~1074) s'exécute avant toute génération de `job_id`/mutation Domain — un échec ici n'a créé et ne mute aucun Job, retry-safe par construction. Reconfirmé sans modification, dette technique distincte, non traitée par cette mission.

## 12. Tests ajoutés

**+4 tests nets** :
- `TrainingJobRunnerTest.test_process_finished_with_inconclusive_output_inspection_reports_failed` (`tests/integration/test_training_job_runner.py`) : `Path.is_file` simulé levant `OSError` sur le chemin normal → `failed`, message contenant « could not determine », jamais de `OSError` brute.
- `TrainingJobRunnerTest.test_cancel_with_inconclusive_output_inspection_reports_cancelled_not_succeeded` : même simulation sur le chemin Cancel → `cancelled`, jamais `succeeded` sans preuve.
- `ResolveOnetrainerLaunchTest.test_raises_onetrainer_launch_error_when_python_executable_check_is_inconclusive` (`tests/integration/test_onetrainer_launch.py`) : `Path.is_file` simulé levant `OSError` → `OneTrainerLaunchError`, message contenant « Python environment » et « determine ».
- `ResolveOnetrainerLaunchTest.test_raises_onetrainer_launch_error_when_train_remote_script_check_is_inconclusive` : même principe, ciblé précisément sur `train_remote.py` (venv Python réel présent, seul le second `is_file()` simulé via `autospec=True` + fonction de sélection par nom de fichier) → message contenant « train_remote.py » et « determine ».

Aucun test Runner supplémentaire pour 4b : `test_missing_onetrainer_settings_reports_failed_before_launching` démontrait déjà, avant cette mission, que `TrainingJobRunner.start()` consomme et terminalise correctement `OneTrainerLaunchError` — non dupliqué.

## 13. Résultats réels

- Tests ciblés 4a (2 nouveaux) : **2/2 passés**.
- Tests ciblés 4b (2 nouveaux) : **2/2 passés**.
- Non-régression M148 explicite (`test_cooperative_cancel_with_output_already_written_reports_succeeded`, `test_cancel_with_nonzero_exit_code_still_reports_cancelled`, `test_cancel_with_crash_exit_still_reports_cancelled`) : **3/3 passés**, comportement historique inchangé.
- `test_training_job_runner.py` complet : **17/17 passés** (15 préexistants + 2 nouveaux).
- `test_onetrainer_launch.py` complet : **7/7 passés** (5 préexistants + 2 nouveaux).
- Suites voisines Training (`test_training_roundtrip.py` + `test_onetrainer_config.py`) : **553/553 passés**.
- **Suite complète : 2903 collectés/2903 passés, 0 échoué** (361.127s). Équation : 2899 (clôture Mission 156) + 4 nets ajoutés par Mission 157 = **2903**, cohérent.
- `git diff --check` : clean (avertissements `LF will be replaced by CRLF` uniquement, non bloquants).

## 14. Clôture Git

Commit fonctionnel : `1804c605f424c3b401a18a167f54eed296145160` (« Guarantee training job terminalization on filesystem inspection failure », 5 fichiers : `src/ui/training_job_runner.py`, `src/engines/onetrainer_launch.py`, `tests/integration/test_training_job_runner.py`, `tests/integration/test_onetrainer_launch.py`, `docs/missions/MISSION_157.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission157` (objet `d928f06d9d320b11bc722f63434e368038c94234`, cible `1804c605f424c3b401a18a167f54eed296145160`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission157 — Guarantee Training Job Terminalization on Filesystem Inspection Failure` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2903/2903, 0 échoué** (361.127s). Le tag `v0.2-mission156` (`dfd4bec213b34c8c523f18fa465056c7417a4d0c` → objet `5994a30d0f6f507c48f64372d0e48d7b85383ed2`) reste inchangé.
