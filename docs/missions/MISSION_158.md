# Mission 158 — Protect Unsaved Dataset Captions Across Dataset and Context Changes

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente.** Une caption modifiée mais non sauvegardée dans `DatasetsPage` (`src/ui/pages/datasets_page.py`) pouvait être écrasée silencieusement par deux familles de transitions non protégées : (1) sélectionner un autre Dataset dans `dataset_list` — le bug réellement live, atteignable en un seul clic ordinaire ; (2) fermer/ouvrir/créer un nouveau Workspace (New/Open/Close), `DatasetsPage` étant la seule des 7 pages à draft à ne jamais consulter le mécanisme générique `confirm_context_change()` déjà établi ailleurs dans le Toolkit. Le changement d'image au sein d'un même Dataset était déjà protégé avant cette mission (`on_image_selection_changed()`, Mission 098) — **non modifié, non corrigé par M158**. Le changement de Character (`CHARACTER_SELECTED`/`CHARACTER_DELETED`) est câblé pour la même cohérence architecturale mais reste un hardening dormant : l'UI multi-Character correspondante est cachée depuis Mission 026, aucun utilisateur réel ne peut l'atteindre aujourd'hui.

## 1. Invariant

**Une caption modifiée mais non sauvegardée ne doit jamais être écrasée silencieusement par une opération de navigation ou de changement de contexte — le comportement canonique est Save / Discard / Cancel, en réutilisant le dialogue et les mécanismes existants de `DatasetsPage`.**

## 2. Le bug réellement live — changement de Dataset

`on_dataset_selection_changed()` appelait `self.dataset_manager.select(current.data(Qt.UserRole))` sans jamais vérifier `_caption_dirty`. `DatasetManager.select()` publie `DATASET_SELECTED` de façon synchrone, câblé à `update_datasets()`, qui reconstruit `images_list` pour le nouveau Dataset et appelle inconditionnellement `_refresh_caption_panel_for_current_selection()` → écrasement silencieux et immédiat d'une caption en cours d'édition. Scénario concret : éditer une caption non sauvegardée, cliquer directement sur un autre Dataset dans `dataset_list` — la perte survient en un seul clic, aussi fréquente que le changement d'image (déjà protégé).

## 3. Les bugs globaux — New / Open / Close

`DatasetsPage` était absente des trois chaînes `confirm_context_change()` de `MainWindow` (`new_project()`, `open_project()`, `closeEvent()`), alors que les 6 autres pages à draft (Prompts/Characters/LoRA/Settings/Inference/Training) y participent déjà toutes. Une caption dirty survivait donc silencieusement à une création/ouverture/fermeture de projet, écrasée dès que `update_datasets()` était rappelé pour le nouveau contexte.

## 4. Déjà correct avant M158 — changement d'image (non modifié)

`on_image_selection_changed()` (Mission 098) implémentait déjà exactement le contrat Save/Discard/Cancel attendu : vérification de `_caption_dirty`, dialogue partagé, restauration de la sélection précédente via `blockSignals()` sur Cancel et sur échec de Save. **Ce chemin n'a fait l'objet d'aucune réécriture** — M158 en réutilise le pattern, jamais le code lui-même, et les tests existants qui le couvrent (`DatasetsPageCaptionPanelTest.test_switching_selection_while_dirty_*`) restent inchangés et verts. Ne pas présenter ce chemin comme une correction de cette mission : il était déjà sûr.

## 5. Character switch — hardening architectural dormant, pas une correction de bug utilisateur

`CHARACTER_SELECTED`/`CHARACTER_DELETED` ne sont publiés que depuis `CharactersPage.on_selection_changed()`/`CharacterManager.delete()`, dont l'unique appelant de production (`CharactersPage.list_widget` et ses boutons associés) est `setVisible(False)` depuis la révision UX de Mission 026 (« 1 Workspace = 1 Character principal »). Le câblage `datasets_page.reset_for_context_change()` sur ces deux événements est ajouté par cohérence avec `CharactersPage`/`LoRAPage`/`SettingsPage`/`TrainingPage`, qui réagissent déjà de la même façon — **ce n'est la correction d'aucun chemin utilisateur réellement atteignable aujourd'hui.**

## 6. Comportement — Save / Discard / Cancel (changement de Dataset)

Réutilise exactement `_confirm_discard_caption_before_switch()` (aucun nouveau dialogue, aucun nouveau vocabulaire) :

- **Save** → `_save_caption_or_report_error()` ; succès → `dataset_manager.select(target_dataset_id)` appelé, Dataset cible chargé ; **échec → `DatasetManager.select()` n'est jamais appelé**, `dataset_list` restauré sur l'ancien Dataset (`blockSignals`), brouillon conservé intact.
- **Discard** → `_caption_dirty = False`, `dataset_manager.select(target_dataset_id)` appelé, Dataset cible chargé sans persistance.
- **Cancel** → `DatasetManager.select()` n'est jamais appelé, `dataset_list` restauré sur l'ancien Dataset (`blockSignals` anti-réentrance), brouillon intact.

## 7. `confirm_context_change()`

```python
def confirm_context_change(self) -> bool:
    if not self._caption_dirty:
        return True
    choice = self._confirm_discard_caption_before_switch()
    if choice == QMessageBox.Cancel:
        return False
    if choice == QMessageBox.Save:
        if not self._save_caption_or_report_error():
            return False
    self._caption_dirty = False
    return True
```

Contrat identique à `LoRAPage.confirm_context_change()` : clean → `True` sans dialogue ; Save réussi ou Discard → `True` ; Cancel ou échec de Save → `False`. Ne réinitialise jamais l'éditeur lui-même — c'est le rôle de `reset_for_context_change()`, invoqué séparément une fois le changement de contexte réellement effectué.

## 8. `reset_for_context_change()`

```python
def reset_for_context_change(self, _payload=None):
    self.update_datasets()
```

Souscrit à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` et `CHARACTER_SELECTED`/`CHARACTER_DELETED` — jamais aux événements déjà non destructifs. `update_datasets()` seul suffit : par construction, `DatasetManager._on_context_changed()` (souscrit aux 5 mêmes événements, toujours enregistré avant la Page) réinitialise déjà `active_dataset_id` à `None` avant que cette méthode ne s'exécute, donc `_refresh_caption_panel_for_current_selection()` recharge toujours correctement `_caption_dirty`/`_caption_loaded_image_id`/l'éditeur/le bouton Save/les sélections — vérifié explicitement par test (§12).

## 9. Wiring `MainWindow`

- **New/Open/Close** : `datasets_page.confirm_context_change()` ajouté comme **8ᵉ et dernier garde**, après `training_page.confirm_context_change()`, sans réordonner aucun garde existant — conforme au précédent historique (Missions 083/084/105 : toujours ajouté en fin de séquence). `closeEvent()` : `False` → `event.ignore()`, identique aux 7 autres pages.
- **`WORKSPACE_SAVED`/`RENAMED`** → `datasets_page.update_datasets` (inchangé, non destructif).
- **`WORKSPACE_CREATED`/`OPENED`/`CLOSED`** → `datasets_page.reset_for_context_change` (nouveau, remplace le câblage direct `update_datasets`).
- **`CHARACTER_SELECTED`/`CHARACTER_DELETED`** → `datasets_page.reset_for_context_change` (nouveau, hardening dormant — voir §5).

## 10. Événements volontairement laissés sur `update_datasets()`

`WORKSPACE_SAVED`, `WORKSPACE_RENAMED`, `CHARACTER_CREATED`, `DATASET_CREATED`, `DATASET_SELECTED`, `DATASET_DELETED` — aucun n'est destructif pour un brouillon de caption : `WORKSPACE_SAVED`/`RENAMED` ne changent ni le Dataset ni l'image affichés ; `CHARACTER_CREATED` ne mute pas `active_dataset_id` ; `DATASET_CREATED` ne sélectionne jamais le nouveau Dataset ; `DATASET_SELECTED` n'est atteint qu'une fois le garde `on_dataset_selection_changed()` déjà résolu (Save/Discard déjà effectué, ou l'appel `select()` jamais émis sur Cancel) ; `DATASET_DELETED` d'un Dataset différent de l'actif ne touche pas `active_dataset_id`. Aucun dialogue n'a été ajouté dans `_load_caption_into_editor()` ni dans `update_datasets()` elle-même — ces méthodes restent de purs refresh programmatiques, jamais des points de garde.

## 11. Suppressions — explicitement hors scope

Ni la suppression du Dataset actuellement affiché (déjà protégée par sa propre confirmation destructive explicite, `delete_dataset()`), ni la suppression de l'image en cours d'édition (`remove_selected_images_from_dataset()`, action immédiate sans confirmation — un invariant distinct, candidat futur séparé) n'ont été modifiées. Aucun bundling.

## 12. Tests ajoutés

**+14 tests nets** (2903 → 2917 tests collectés) :

`tests/integration/test_datasets_page.py` — `DatasetsPageCaptionPanelTest` (+5, changement de Dataset) :
- `test_switching_dataset_while_dirty_cancel_keeps_draft_and_dataset`
- `test_switching_dataset_while_dirty_discard_loads_the_target_dataset`
- `test_switching_dataset_while_dirty_save_persists_then_loads_the_target_dataset`
- `test_switching_dataset_without_dirty_never_prompts`
- `test_switching_dataset_while_dirty_save_failure_keeps_draft_and_dataset` (preuve explicite : `DatasetManager.select()` jamais appelé après un échec de Save)

`tests/integration/test_datasets_page.py` — nouvelle classe `DatasetsPageConfirmContextChangeTest` (+5) :
- `test_confirm_context_change_without_dirty_draft_returns_true_no_dialog`
- `test_confirm_context_change_cancel_returns_false_and_keeps_draft`
- `test_confirm_context_change_save_choice_persists_and_returns_true`
- `test_confirm_context_change_save_failure_returns_false_and_keeps_draft`
- `test_reset_for_context_change_clears_a_stale_draft_and_resyncs_from_domain`

`tests/integration/test_main_window_new_project.py` — `MainWindowConfirmContextChangeTest` (+3, wiring réel bout-en-bout) :
- `test_new_project_dirty_dataset_caption_cancel_abandons_new_project_entirely` (caption dirty → `new_project()` → Cancel → création abandonnée → caption préservée, sur une vraie `MainWindow`)
- `test_new_project_dataset_guard_false_never_calls_workspace_manager_create`
- `test_open_project_dataset_guard_false_never_calls_workspace_manager_open`

`tests/integration/test_main_window_close_event.py` — `MainWindowCloseEventOrchestrationTest` (+1) :
- `test_datasets_guard_false_ignores_close_and_stops_the_chain`

## 13. Résultats réels

- Ciblés `DatasetsPageCaptionPanelTest` + `DatasetsPageConfirmContextChangeTest` : **24/24 passés**.
- `test_datasets_page.py` complet : **77/77 passés** (non-régression changement d'image confirmée : les 4 tests historiques `test_switching_selection_while_dirty_*`/`test_switching_selection_without_dirty_never_prompts`/`test_unrelated_refresh_never_discards_a_dirty_draft` toujours verts sans modification).
- `test_main_window_new_project.py` + `test_main_window_close_event.py` (ciblés `MainWindowConfirmContextChangeTest` + `MainWindowCloseEventOrchestrationTest`) : **29/29 passés**.
- `test_main_window_new_project.py` + `test_main_window_close_event.py` complets : **92/92 passés** — aucun dialogue parasite introduit (tous les guards New/Open/Close préexistants des 6 autres pages, y compris les tests `test_guard_order_*`/`test_shutdown_runs_only_after_*`, restent verts sans modification).
- Suite voisine `test_dataset_roundtrip.py` : **137/137 passés**.
- Suite voisine `test_main_window_rename_project.py` (non touchée, `rename_project()` ne consulte aucun `confirm_context_change()`) : **22/22 passés**.
- **Suite complète : 2917 collectés/2917 passés, 0 échoué** (330.335s). Équation : 2903 (clôture Mission 157) + 14 nets ajoutés par Mission 158 = **2917**, cohérent.
- `git diff --check` : clean (avertissement `LF will be replaced by CRLF` uniquement, non bloquant).
- Exactement les 2 fichiers de production annoncés modifiés (`src/ui/pages/datasets_page.py`, `src/ui/main_window.py`), plus 3 fichiers de test — aucun troisième fichier de production.
