# Mission 117 — Explicit Cancel for the ComfyUI Auto-Start Wait in InferencePage

> **MISSION CLÔTURÉE.** Implémentée, validée par la suite complète, commitée, taguée et publiée. Commit fonctionnel `76fc1435ac40cd55e91acb519f8647099b56904d` (`Add explicit cancel for pending ComfyUI auto-start in InferencePage`), tag `v0.2-mission117`, GitHub Release publiée.

## 1. Contexte

Mission 116 a rendu visible l'attente d'auto-start ComfyUI Local introduite par Mission 115 (`comfyui_status_label`), mais cette attente restait purement subie : le seul moyen d'en sortir avant la fin du budget de readiness (~120 secondes) était un signal lifecycle externe — un échec (`START_FAILED`) ou un Stop déclenché ailleurs (typiquement depuis `SettingsPage`). Si ComfyUI Local était réellement bloqué (par exemple `custom_nodes` cassés), l'utilisateur n'avait aucun recours depuis `InferencePage` elle-même.

## 2. Objectif

Ajouter dans `InferencePage` un moyen explicite d'annuler une génération en attente pendant le démarrage de ComfyUI Local, sans jamais interrompre ou prendre ownership du Start applicatif lui-même.

## 3. Décision retenue

Un nouveau `QPushButton` (`self.cancel_comfyui_start_button`, "Annuler"), ajouté juste après `comfyui_status_label`, invisible au repos — même convention idle/actif que ce label. Rendu visible exactement quand un pending est créé (`_start_generation()`, branches `STOPPED`/`START_FAILED`/`STARTING`), cliquer dessus appelle un nouveau handler (`_on_cancel_comfyui_start_clicked()`) qui invalide uniquement `self._pending_generation_request`, réactive l'UI de génération, efface le statut — et n'appelle jamais `comfyui_lifecycle_manager.stop()`. Ce handler mirrore la restauration déjà établie par `_abort_pending_generation()` (Mission 115), sans son `QMessageBox` puisqu'annuler n'est pas une erreur.

## 4. Comportement implémenté

| État / transition | Comportement |
|---|---|
| Pending créé (`STOPPED`/`START_FAILED`/`STARTING`) | `cancel_comfyui_start_button` devient visible, aux côtés du statut |
| Clic sur "Annuler" | Pending invalidé, statut effacé, bouton caché, `generate_button`/contrôles de génération réactivés — **aucun appel à `stop()`** |
| Clic sur "Annuler" sans pending existant | No-op sûr (garde défensive) |
| Le Start applicatif déjà en cours (jamais interrompu) atteint ensuite `RUNNING_OWNED`/`EXTERNAL_ACTIVE` | Aucune génération n'est lancée — `_on_comfyui_lifecycle_state_changed()` ignore ce signal via sa garde d'identité déjà existante (`_pending_generation_request is None`) |
| Le Start atteint ensuite `START_FAILED` | Aucun effet parasite — même garde d'identité, aucun `QMessageBox` déclenché |
| Lancement immédiat (`RUNNING_OWNED`/`EXTERNAL_ACTIVE` au clic) ou refus immédiat (`STOPPING`) | Bouton jamais affiché |
| Abandon du pending par ailleurs (échec/Stop externe), lancement réel de la génération, changement de Workspace/contexte, `shutdown()` | Bouton caché aux mêmes points que `comfyui_status_label` (Mission 116) |
| Forge sélectionné | Jamais touché — bouton toujours invisible |

## 5. Périmètre exact — fichiers concernés

- `src/ui/pages/inference_page.py` (modifié) — nouveau `QPushButton` dans le constructeur ; rendu visible dans `_start_generation()` (branche pending) ; nouveau handler `_on_cancel_comfyui_start_clicked()` ; caché dans `_abort_pending_generation()`, `_launch_generation_worker()`, `reset_for_workspace_change()` et `shutdown()`.
- `tests/integration/test_inference_page.py` (modifié) — 8 tests nets nouveaux (annulation après nouveau Start, annulation en s'attachant à un `STARTING`, no-op sans pending, `RUNNING_OWNED`/`START_FAILED` tardifs après annulation sans effet, workspace change/shutdown après annulation, un test réel avec le harnais de process factice de Mission 114 prouvant que le vrai Start reste en vie sans générer), plus assertions de visibilité (`isVisibleTo`, précédent déjà établi par `test_prompt_assistant_dialog.py`) ajoutées à tous les tests M115/M116 existants concernés.

**Aucun changement** à `src/ui/comfyui_lifecycle_manager.py`, `src/managers/generation_manager.py`, `src/ui/pages/settings_page.py`, `src/engines/forge_engine.py` — confirmé par audit avant implémentation, aucun écart architectural rencontré.

## 6. Hors périmètre strict

- Tout appel à `comfyui_lifecycle_manager.stop()` depuis `InferencePage` — le Start applicatif reste piloté indépendamment de l'intérêt d'une seule page pour son résultat, exactement comme `reset_for_workspace_change()` l'établissait déjà pour un changement de Workspace.
- Tout changement du contrat fonctionnel de Mission 115/116 (six états, snapshot immuable, source de configuration, statut transitoire).
- Tout système général de notifications/statuts réutilisable par d'autres pages.

## 7. Tests

26/26 tests ciblés (`InferencePageComfyUILifecycleHandoffTest` + `InferencePageComfyUILifecycleRealStartTest`), 221/221 `test_inference_page.py` complet, 103/103 tests MainWindow concernés (aucune boîte de dialogue réelle inattendue), suite complète **2318/2318** (2310 avant Mission 117 + 8 nets nouveaux), `git diff --check` propre.

## 8. Critères de clôture

1. Bouton d'annulation visible uniquement pendant un pending réel, jamais sur les branches de lancement/refus immédiat.
2. Annulation : pending invalidé, UI réactivée, statut effacé, jamais d'appel à `stop()`.
3. Un signal lifecycle tardif (`RUNNING_OWNED`/`EXTERNAL_ACTIVE`/`START_FAILED`) après annulation reste sans effet — aucune génération, aucun message parasite.
4. Aucune modification de `ComfyUILifecycleManager`/`GenerationManager`/`SettingsPage`/`ForgeEngine`.
5. Suite complète verte au nombre exact, `git diff --check` propre, seuls `inference_page.py`/`test_inference_page.py` modifiés.

## 9. Documentation

Cette mission ferme le second gap UX identifié après la clôture de Mission 116 (attente ComfyUI visible mais non actionnable). La régularisation documentaire post-clôture suit le même processus que les missions précédentes.

## 10. Autorisation

Mission autorisée par l'architecte avec contraintes architecturales et liste de tests minimale fournies en amont ; aucun écart architectural n'ayant été rencontré pendant l'audit préalable, l'implémentation a procédé directement, conformément à l'autorisation donnée.
