# Mission 116 — ComfyUI Auto-Start Progress Feedback in InferencePage

> **MISSION CLÔTURÉE.** Implémentée, validée par la suite complète, commitée, taguée et publiée. Commit fonctionnel `7fe55cefd836f526e900ad7528d6a576c3cbc902` (`Add ComfyUI auto-start progress feedback to InferencePage`), tag `v0.2-mission116`, GitHub Release publiée.

## 1. Contexte

Mission 115 a livré l'auto-start ComfyUI Local depuis `InferencePage` : un clic sur Generate avec ComfyUI arrêté déclenche désormais un démarrage automatique, une attente non bloquante de readiness, puis le lancement automatique de la génération originellement demandée. Ce mécanisme fonctionne réellement (deux scénarios de smoke réel PASS, voir `docs/missions/MISSION_115.md` §14), mais laisse un gap UX : pendant l'attente (jusqu'à ~120 secondes, budget de readiness fixé par Mission 114), `generate_button` est simplement désactivé, sans aucune indication visible de ce qui se passe — l'utilisateur ne peut pas distinguer une attente de démarrage ComfyUI normale d'un blocage.

## 2. Objectif

Ajouter un retour visuel transitoire dans `InferencePage`, indiquant clairement que ComfyUI est en cours de démarrage pendant cette attente, sans modifier le contrat fonctionnel de Mission 115 (six états lifecycle, un seul pending, snapshot immuable, configuration persistée uniquement, Forge inchangé).

## 3. Décision retenue

Un nouveau `QLabel` (`self.comfyui_status_label`), ajouté juste après `generate_button`, texte vide au repos — même convention que `sampler_scheduler_status_label` déjà présent dans cette page. Ce label reste un indicateur de progression pur, jamais un second canal d'erreur : chaque abandon du pending continue de passer par exactement un `QMessageBox.critical`/`warning` déjà existant (Mission 115), le label étant systématiquement vidé au même moment, jamais un texte d'erreur dupliqué.

## 4. Comportement implémenté

| État / transition | Statut affiché |
|---|---|
| Clic avec `STOPPED`/`START_FAILED` (nouveau Start engagé) | `"Démarrage de ComfyUI en cours…"` |
| Clic avec `STARTING` (rattachement, aucun second Start) | `"Un démarrage de ComfyUI est déjà en cours…"` |
| Clic avec `RUNNING_OWNED`/`EXTERNAL_ACTIVE` (génération immédiate) | Aucun statut — jamais écrit |
| Clic avec `STOPPING` (refus immédiat) | Aucun statut — jamais écrit, aucun pending créé |
| Readiness atteinte (`RUNNING_OWNED`/`EXTERNAL_ACTIVE` en attente) | Statut effacé avant/au lancement réel de la génération |
| `START_FAILED` pendant l'attente | Statut effacé, `QMessageBox.critical` inchangé (Mission 115) |
| Stop déclenché ailleurs pendant l'attente (`STOPPED` reçu) | Statut effacé, `QMessageBox.critical` inchangé (Mission 115) |
| Changement de Workspace/contexte pendant l'attente | Statut effacé (`reset_for_workspace_change()`) |
| `shutdown()` | Statut effacé défensivement |
| Forge sélectionné | Jamais touché — label toujours vide |

## 5. Périmètre exact — fichiers concernés

- `src/ui/pages/inference_page.py` (modifié) — nouveau `QLabel` dans le constructeur ; texte défini dans `_start_generation()` (branche pending) ; effacé dans `_launch_generation_worker()` (point de passage unique commun aux deux chemins de lancement, immédiat et pending résolu), `_abort_pending_generation()`, `reset_for_workspace_change()` et `shutdown()`.
- `tests/integration/test_inference_page.py` (modifié) — 1 test net nouveau (`test_shutdown_clears_pending_status_label`), assertions de statut ajoutées à 10 tests M115 existants dans `InferencePageComfyUILifecycleHandoffTest`, et à `InferencePageComfyUILifecycleRealStartTest::test_stopped_to_starting_to_running_owned_launches_original_generation` (vérification du texte réellement affiché pendant la phase `STARTING` réelle, avec le harnais de process factice de Mission 114).

**Aucun changement** à `src/ui/comfyui_lifecycle_manager.py`, `src/managers/generation_manager.py`, `src/ui/pages/settings_page.py`, `src/engines/forge_engine.py` — confirmé par audit avant implémentation, aucun écart architectural rencontré.

## 6. Hors périmètre strict

- Tout changement du contrat fonctionnel de Mission 115 (six états, snapshot immuable, source de configuration, anti-double-clic, invalidation par contexte).
- Tout système général de notifications/statuts réutilisable par d'autres pages.
- Tout polling supplémentaire — le label ne réagit qu'au signal `state_changed` déjà consommé par Mission 115.
- Smoke réel séparé — jugé non nécessaire, le lifecycle réel étant déjà validé par Mission 115 ; une vérification équivalente est intégrée au test réel existant (`InferencePageComfyUILifecycleRealStartTest`).

## 7. Tests

18/18 tests ciblés (`InferencePageComfyUILifecycleHandoffTest` + `InferencePageComfyUILifecycleRealStartTest`), 213/213 `test_inference_page.py` complet, 103/103 tests MainWindow concernés (`test_main_window_close_event.py`/`test_main_window_new_project.py`/`test_main_window_rename_project.py` — aucune boîte de dialogue réelle inattendue), suite complète **2310/2310** (2309 avant Mission 116 + 1 net nouveau), `git diff --check` propre.

## 8. Critères de clôture

1. Statut visible pendant l'attente de démarrage, texte distinct selon nouveau Start vs rattachement à un Start en cours.
2. Aucun statut dans les branches de lancement immédiat ni dans le refus `STOPPING`.
3. Statut systématiquement effacé au lancement réel de la génération, à l'abandon (échec/annulation), au changement de contexte et à `shutdown()`.
4. Aucune modification de `ComfyUILifecycleManager`/`GenerationManager`/`SettingsPage`/`ForgeEngine`.
5. Aucune duplication du contenu déjà affiché par les `QMessageBox` existants.
6. Suite complète verte au nombre exact, `git diff --check` propre, seuls `inference_page.py`/`test_inference_page.py` modifiés.

## 9. Documentation

Cette mission ferme le gap UX identifié immédiatement après la clôture de Mission 115 (statut d'attente invisible pendant l'auto-start ComfyUI). La régularisation documentaire post-clôture suit le même processus que les missions précédentes.

## 10. Autorisation

Mission autorisée par l'architecte avec plan détaillé fourni en amont ; aucun écart architectural n'ayant été rencontré pendant l'audit préalable, l'implémentation a procédé directement, conformément à l'autorisation donnée.
