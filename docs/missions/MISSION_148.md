# Mission 148 — Preserve Successful Training Output After Late Cancel

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en cours.** `TrainingJobRunner._on_process_finished()` testait `self._cancel_requested` avant toute lecture de `exit_status`/`exit_code`/de l'existence du fichier de sortie attendu — protection nécessaire contre un `CrashExit` provoqué par `terminate()`/`kill()`, mais qui produisait un résultat incorrect si le stop coopératif envoyé à OneTrainer aboutissait à une fin propre (`NormalExit`, `exit_code == 0`) avec un fichier de sortie réellement écrit : le Job devenait `cancelled`, `final_output_path` restait vide, et un LoRA pourtant valide et présent sur disque devenait inaccessible à l'Import et à l'Inference depuis l'UI, sans qu'aucune erreur ne soit jamais montrée. Corrigé par une simple réévaluation de l'invariant de succès déjà existant, à l'intérieur de la seule branche `_cancel_requested` — aucune nouvelle définition du succès, aucun nouvel état, aucune modification `training_page.py`/`training_manager.py`. **+3 tests nets** (2839 → 2842 tests collectés), suite complète finale 2842/2842, 0 échoué — voir §13 pour le détail des tests et le rapport d'implémentation transmis pour le détail complet des résultats réels.

## 1. Root cause

`TrainingJobRunner.cancel()` (`src/ui/training_job_runner.py:116-127`) déclenche une séquence d'arrêt en trois paliers (Mission 100 §8) : stop coopératif (`_send_cooperative_stop()`, `:129-145`, via `onetrainer_cancel_helper.py`, exécuté sous l'interpréteur OneTrainer) → attente bornée (`COOPERATIVE_STOP_TIMEOUT_SECONDS = 30.0`, `:37`) → `QProcess.terminate()` → attente bornée (`TERMINATE_TIMEOUT_SECONDS = 10.0`, `:38`) → `QProcess.kill()`. Le stop coopératif est un vrai signal `TrainCommands.stop()` dont le rôle exact est de laisser OneTrainer terminer proprement son étape courante et sortir de lui-même — donc, par construction, un stop coopératif réussi peut parfaitement aboutir à un `exit_code == 0` avec un fichier de sortie réel déjà écrit, **avant même** que les paliers `terminate()`/`kill()` n'aient besoin d'intervenir.

`_on_process_finished(exit_code, exit_status)` (`training_job_runner.py:162-194`) teste `self._cancel_requested` en tout premier (`:171-173`), avant toute autre lecture :

```python
def _on_process_finished(self, exit_code, exit_status) -> None:
    self._cooperative_timer.stop()
    self._terminate_timer.stop()

    # Checked first, deliberately: a real Cancel almost always ends
    # with QProcess.terminate()/kill() forcing the process down,
    # which Qt itself reports as exit_status == CrashExit — an
    # intentional termination we asked for must never be
    # misreported as a native crash.
    if self._cancel_requested:
        self._finish("cancelled", "", "")
        return

    if exit_status == QProcess.ExitStatus.CrashExit:
        self._finish(
            "failed",
            f"OneTrainer process terminated abnormally (native crash), exit_code={exit_code}",
            "",
        )
        return

    if exit_code != 0:
        self._finish("failed", f"OneTrainer process exited with code {exit_code}", "")
        return

    if Path(self._job_paths.expected_output_path).is_file():
        self._finish("succeeded", "", self._job_paths.expected_output_path)
    else:
        self._finish(
            "failed",
            "OneTrainer process exited successfully but no output file was found",
            "",
        )
```

Le commentaire `:166-170` documente précisément *pourquoi* ce check existe (ne jamais confondre un `CrashExit` provoqué par `terminate()`/`kill()` avec un vrai crash natif) — mais sa portée actuelle est trop large : il court-circuite **tous** les cas Cancel, y compris celui où le process est sorti proprement avec un artefact valide.

## 2. Séquence exacte du bug (scénario reproductible)

1. Training `RUNNING`.
2. Utilisateur demande Cancel → `cancel()` → `self._cancel_requested = True`.
3. `_send_cooperative_stop()` envoie le signal coopératif à OneTrainer.
4. OneTrainer termine proprement son travail courant et écrit le fichier attendu à `self._job_paths.expected_output_path`.
5. Le process sort avec `NormalExit` et `exit_code == 0`, avant même l'expiration de `COOPERATIVE_STOP_TIMEOUT_SECONDS`.
6. `QProcess.finished` déclenche `_on_process_finished(0, NormalExit)`.
7. `self._cancel_requested` est vrai → `_finish("cancelled", "", "")` immédiat, sans jamais lire `exit_status`/`exit_code`/l'existence du fichier.
8. `TrainingPage._on_job_finished()` (`src/ui/pages/training_page.py:2261-2280`) relaie `state="cancelled"` à `TrainingManager.update_job_state()` (`src/managers/training_manager.py:1164-1217`, qui ne valide jamais `state` — persiste tel quel, `:1179-1185`).
9. `job.state = "cancelled"`, `job.final_output_path` reste à sa valeur par défaut (jamais renseigné).
10. `TrainingPage._describe_job()`/`_importable_job()`/`_usable_in_inference_job()` (`training_page.py:2365-2391`, `:2406-2433`, `:2435+`) gatent tous exclusivement sur `job.state == TRAINING_JOB_STATE_SUCCEEDED` — un Job `cancelled` n'est jamais reconnu comme importable/utilisable, quel que soit le contenu réel du disque.

Résultat : le fichier `.safetensors` existe, est valide, mais reste invisible et inaccessible depuis toute l'UI, sans aucune erreur affichée à aucun moment.

## 3. Invariant de succès existant — à ne jamais redéfinir

Le chemin normal (non-Cancel) reconnaît déjà un succès avec exactement trois conditions, ni plus ni moins (`:175-188`) :

```
exit_status == QProcess.ExitStatus.NormalExit
ET exit_code == 0
ET Path(expected_output_path).is_file()
```

Aucune validation de taille minimale, d'extension, ou de contenu `.safetensors` n'existe pour ce chemin — c'est la barre déjà en production depuis Mission 100. **M148 réutilise cet invariant tel quel pour le cas Cancel tardif, sans l'alourdir.** Introduire une validation plus stricte uniquement pour le cas Cancel créerait une incohérence entre deux chemins qui doivent produire le même résultat pour la même preuve de succès.

## 4. Contrat comportemental cible

```
_on_process_finished(exit_code, exit_status):
    si self._cancel_requested :
        succès = (exit_status == NormalExit) ET (exit_code == 0)
                 ET Path(expected_output_path).is_file()
        si succès :
            state = "succeeded"
            error_message = ""
            final_output_path = self._job_paths.expected_output_path
        sinon :
            state = "cancelled"       (comportement historique, inchangé)
            error_message = ""
            final_output_path = ""
    sinon :
        (branches existantes L175-194, strictement inchangées)
```

Le résultat réel prime sur l'intention antérieure de Cancel **uniquement** quand les trois conditions de l'invariant §3 sont simultanément vraies. Dans tous les autres cas provoqués par un Cancel — `terminate()`/`kill()` forcé, `CrashExit`, exit non-zéro, exit 0 sans fichier — le comportement historique `cancelled` / `""` / `""` est strictement préservé, y compris la protection contre la mauvaise classification d'un `CrashExit` provoqué (le `CrashExit` échoue automatiquement la condition `exit_status == NormalExit`, donc retombe toujours sur `cancelled`).

## 5. Matrice des scénarios (verrouillée par le mini-audit)

| # | Scénario | Comportement M148 |
|---|---|---|
| 1 | Pas de Cancel, exit 0, output présent | `succeeded`, chemin réel — **inchangé** |
| 2 | Pas de Cancel, exit 0, output absent | `failed` — **inchangé** |
| 3 | Pas de Cancel, exit ≠ 0 | `failed` — **inchangé** |
| 4 | Cancel + `terminate()`/`kill()` forcé (`CrashExit`) | `cancelled` — **inchangé** |
| 5 | Cancel + exit ≠ 0 (`NormalExit`) | `cancelled` — **inchangé** |
| 6 | Cancel + exit 0, output absent | `cancelled` — **inchangé** |
| 7 | **Cancel + exit 0 + output valide présent** | **`succeeded`, chemin réel — corrigé (c'était `cancelled`, `""`)** |

Seul le cas 7 change de résultat. Les six autres cas sont des non-régressions à verrouiller explicitement.

## 6. Conception — point d'insertion exact

Restructuration locale de la seule branche `if self._cancel_requested:` (`training_job_runner.py:171-173`) — aucune autre ligne de `_on_process_finished()` n'est modifiée :

```python
if self._cancel_requested:
    if (
        exit_status == QProcess.ExitStatus.NormalExit
        and exit_code == 0
        and Path(self._job_paths.expected_output_path).is_file()
    ):
        self._finish("succeeded", "", self._job_paths.expected_output_path)
    else:
        self._finish("cancelled", "", "")
    return
```

Les branches `CrashExit`/`exit_code != 0`/`is_file()` du chemin non-Cancel (`:175-194`) restent identiques, non touchées, non dupliquées différemment — la même condition littérale y est simplement réévaluée dans le nouveau bloc, pas réinventée. Aucune autre méthode du fichier n'est modifiée : `cancel()`, `_send_cooperative_stop()`, `_on_cooperative_timeout()`, `_on_terminate_timeout()`, `_on_error_occurred()`, `_finish()`, `_on_stdout()`, `_on_stderr()` restent strictement inchangées.

## 7. Aucun nouvel état

`SUCCEEDED` décrit déjà, et exclusivement, « un job ayant produit avec succès son artefact final reconnu » (§3) — le cas 7 corrigé satisfait cette définition à l'identique du cas 1, ce n'est pas un état hybride. Introduire `CANCELLED_BUT_COMPLETED` ou équivalent forcerait une modification des constantes `TRAINING_JOB_STATE_*`/`TRAINING_JOB_TERMINAL_STATES` (`src/managers/training_manager.py:53-68`) et des trois méthodes de gating UI (§8) pour un bénéfice nul. **Aucun changement Domain, aucune migration, aucun changement de constantes d'état, aucun changement de schéma `project.json`.**

## 8. `final_output_path` et composition UI — aucune modification `training_page.py`

Le mini-audit a vérifié directement, par lecture du code actuel, que `TrainingPage._describe_job()` (`:2365-2391`), `_importable_job()` (`:2406-2433`) et `_usable_in_inference_job()` (`:2435+`) recalculent systématiquement leur résultat à partir de `job.state`/`job.final_output_path` — jamais de valeur mise en cache. Une fois que `_on_process_finished()` émet correctement `state="succeeded"` avec le vrai `final_output_path` (contrat §4), ces trois méthodes reconnaissent le Job comme importable/utilisable **par composition, sans aucune modification**. `_on_job_finished()` (`training_page.py:2261-2280`) affiche déjà la boîte de dialogue de succès standard dès que `state == "succeeded"` (`:2282-2287`), quelle que soit l'origine de cet état — aucun contournement UI spécifique à ajouter.

## 9. Tests requis (`tests/integration/test_training_job_runner.py`)

Scaffolding réutilisé tel quel : `_fake_onetrainer_process.py` (déjà existant) supporte nativement, via le polling réel de `command.pipe` (`FAKE_RESPECT_STOP=1`, aucun minutage arbitraire), la séquence exacte `Cancel → cooperative stop → écriture réelle de l'output → NormalExit → exit_code 0`. Le test principal est un near-mirror de `test_cooperative_cancel_end_to_end_reports_cancelled` (`:220-256`) — même montage (`fake_onetrainer_root`, `FAKE_MODULES_ROOT`, `TrainCommands` factice, `_pump_until`), seule différence : `FAKE_WRITE_OUTPUT="1"` au lieu de `"0"`.

1. **Cancel + cooperative stop + exit 0 + output présent → `succeeded` + vrai `final_output_path`.** Test principal, déterministe via le polling du command pipe, aucun `sleep` arbitraire pour provoquer la race.
2. Cancel + exit 0 sans output → `cancelled` (non-régression cas 6).
3. Cancel + `terminate()`/`kill()` forcé (`CrashExit`) → `cancelled` (non-régression cas 4, protège explicitement la garde historique `:166-170`).
4. Cancel + exit non-zéro → `cancelled` (non-régression cas 5).
5. Succès normal sans Cancel → comportement inchangé (non-régression cas 1, `test_cooperative_cancel_end_to_end_reports_cancelled` et les tests existants de succès simple restent verts sans modification).
6. Persistence/composition : le résultat du scénario 1 ci-dessus, une fois relayé (directement, sans passer par `TrainingPage` — teste `TrainingJobRunner.finished` en isolation comme les tests existants du fichier), transporte bien `state="succeeded"` et le véritable `final_output_path`, jamais une chaîne vide.
7. Couverture `TrainingPage` supplémentaire : **non prévue**, sauf preuve nouvelle démontrant que la composition décrite en §8 est insuffisante — à ne pas ajouter par anticipation.

Tous unitaires/mockés-process déterministes — aucun `time.sleep` arbitraire, aucune dépendance à un minutage réel autre que le polling déjà existant du command pipe.

**Réalisé (voir §13 pour le détail complet)** : les points 2 et 5 de cette liste se sont révélés déjà intégralement couverts par des tests préexistants (`test_cooperative_cancel_end_to_end_reports_cancelled` pour le point 2 — Cancel coopératif réel avec `FAKE_WRITE_OUTPUT="0"`, déjà vert sans modification ; `test_success_reports_succeeded_with_output_path` pour le point 5) — aucun nouveau test n'a donc été ajouté pour ces deux points, conformément à l'instruction de ne pas dupliquer artificiellement la suite. 3 tests réellement nouveaux ont été ajoutés pour les points 1, 3 et 4 (le point 6 étant vérifié par les mêmes assertions que le point 1, sans test séparé).

## 10. Suites voisines à revérifier (non-régression, aucune modification attendue)

- `tests/integration/test_training_job_runner.py` — l'ensemble de `TrainingJobRunnerTest`/`TrainingJobRunnerCancelEscalationTest` rejoué intégralement.
- `tests/integration/test_training_roundtrip.py` — `update_job_state()` n'est pas modifié, aucune régression attendue.
- `tests/integration/test_training_page.py` (si présent sous ce nom ou équivalent) — non-régression des trois méthodes de gating UI, sans modification de leur code.

## 11. Exclusions confirmées (non-goals explicites)

Cascade de suppression Character (dette architecturale distincte, dépriorisée — son UI reste volontairement cachée depuis Mission 026, aucune tentative de correction ici) ; réactivation multi-Character ; validation path-traversal de `_training_folder()` ; gestion HTTP de `ComfyUIEngine` ; `rolling_backup` OneTrainer ; caption sidecars ; Training Resume ; nettoyage `create_job()` ; nettoyage des expositions LoRA orphelines ; lifecycle Forge ; flakiness des tests réel-process Forge ; tout nouvel état `TrainingJob` ; toute modification Domain ; toute modification du schéma `project.json` ; toute modification de OneTrainer lui-même.

## 12. Fichiers attendus

- `src/ui/training_job_runner.py` (production — strictement la branche `_cancel_requested` de `_on_process_finished()`)
- `tests/integration/test_training_job_runner.py` (tests)
- `docs/missions/MISSION_148.md` (documentation)

Aucun autre fichier de production n'est identifié comme nécessaire — en particulier `training_manager.py`/`training_page.py` restent inchangés (§7/§8). Si la rédaction détaillée de l'implémentation révèle qu'un fichier hors de cette liste doit être modifié, ce point devra être signalé et justifié avant toute modification — jamais ajouté silencieusement au scope.

## 13. Résultats réels (implémentation)

**Fichiers effectivement modifiés** — strictement les 3 fichiers annoncés au §12, aucun autre :
- `src/ui/training_job_runner.py` : +20/-1, restructuration locale de la seule branche `if self._cancel_requested:` dans `_on_process_finished()`, exactement conforme au contrat §4/§6. Aucune autre méthode touchée.
- `tests/integration/test_training_job_runner.py` : +75/-0, 3 nouveaux tests ajoutés dans `TrainingJobRunnerTest`.
- `docs/missions/MISSION_148.md` : cette régularisation.

**Tests réellement ajoutés** (3, dans `TrainingJobRunnerTest`) :
- `test_cooperative_cancel_with_output_already_written_reports_succeeded` — test principal, real subprocess/`command.pipe`/`onetrainer_cancel_helper.py`, `FAKE_WRITE_OUTPUT="1"`, déterministe via le polling du command pipe (aucun `sleep` arbitraire) ; asserte `state == "succeeded"`, `error_message == ""`, `final_output_path == expected_output_path`, `Path(final_output_path).is_file()`.
- `test_cancel_with_nonzero_exit_code_still_reports_cancelled` — appel direct de `_on_process_finished(3, NormalExit)` avec `_cancel_requested = True` ; asserte `cancelled`/`""`/`""`.
- `test_cancel_with_crash_exit_still_reports_cancelled` — appel direct de `_on_process_finished(0, CrashExit)` avec `_cancel_requested = True` (verrouille explicitement que `exit_code == 0` seul ne suffit jamais si `exit_status != NormalExit`) ; asserte `cancelled`/`""`/`""`.

**Tests réutilisés sans modification** (déjà couvrants, voir §9) : `test_cooperative_cancel_end_to_end_reports_cancelled` (scénario non-régression : Cancel coopératif réel + output absent → `cancelled`) et `test_success_reports_succeeded_with_output_path` (succès normal sans Cancel, inchangé).

**Résultats ciblés** :
- `tests.integration.test_training_job_runner` seul : **15/15 passés** (12 existants + 3 nouveaux), 2.084s.
- `tests.integration.test_training_roundtrip` + `tests.integration.test_main_window_training_to_inference` (propagation Import/Inference, non-régression) : **389/389 passés**, 35.449s.

**Résultat suite complète** : **2842/2842 collectés/passés, 0 échoué, 0 skip**, exit 0, 326.584s. Équation : 2839 (clôture Mission 147) + 3 nets ajoutés par Mission 148 = **2842**, cohérent. Les lignes `Failed to copy.../disk full/...` interlignées dans la sortie sont des logs attendus de tests d'échec simulé déjà existants ailleurs dans la suite (LoRA Library, Workspace, Dataset), non liées à Mission 148, confirmées non bloquantes par le résultat `OK`/exit 0.

**`git diff --check`** : clean, exit 0 (avertissements `LF will be replaced by CRLF` uniquement — normalisation de fin de ligne, non bloquants).

**Écarts par rapport au draft** : les points 2 et 5 du §9 n'ont pas nécessité de nouveau test (déjà couverts par des tests préexistants, voir §9 « Réalisé »). Aucun autre écart — le contrat, le périmètre fichiers et l'invariant de succès sont strictement ceux validés avant implémentation. Aucune découverte inattendue nécessitant un élargissement de scope ; `training_page.py`/`training_manager.py` n'ont nécessité aucune modification, confirmant les §7/§8.
