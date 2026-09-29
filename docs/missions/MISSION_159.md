# Mission 159 — Protect Unsaved Dataset Caption When Removing Images

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente.** `DatasetsPage.remove_selected_images_from_dataset()` (`src/ui/pages/datasets_page.py`) ne consultait ni `_caption_dirty` ni `_caption_loaded_image_id` avant de retirer les images sélectionnées du Dataset actif. Lorsque l'image portant une caption modifiée mais non sauvegardée faisait partie des images retirées, le refresh synchrone consécutif (`WORKSPACE_SAVED` → `update_datasets()` → `_refresh_caption_panel_for_current_selection()`) écrasait silencieusement le brouillon — un chemin utilisateur direct, à un clic, découvert par l'audit global post-Mission 158.

## 1. Invariant

**Une caption modifiée mais non sauvegardée ne doit jamais être détruite silencieusement lorsqu'une action retire du Dataset l'image à laquelle appartient ce brouillon.** Mission 159 protège exclusivement cette frontière utilisateur.

## 2. Bug

Retirer l'image portant la caption dirty provoquait synchroniquement un refresh (`WORKSPACE_SAVED` publié par `WorkspaceManager.save()` à l'intérieur de `DatasetManager.remove_images()`, avant même le retour de l'appel) et la perte silencieuse du brouillon — sans dialogue, sans avertissement.

## 3. Cause

`remove_selected_images_from_dataset()` ne consultait ni `_caption_dirty` ni `_caption_loaded_image_id`. La perte se produisait dans `_refresh_caption_panel_for_current_selection()` : l'image retirée disparaît de `active_images`, la restauration de sélection par identité (Mission 082) ne peut donc pas la retrouver, `currentItem()` change d'identité, le garde `new_image_id == self._caption_loaded_image_id` échoue nécessairement, et `_load_caption_into_editor()` est appelé inconditionnellement.

## 4. Pourquoi pas Save

La caption appartient à `dataset.entries[image_id]` (`DatasetEntryMetadata`). `DatasetManager.remove_images()` supprime inconditionnellement cette entrée pour toute image effectivement retirée, quelle que soit sa fraîcheur. Sauvegarder la caption juste avant de retirer l'image n'aurait donc **aucun effet durable** — l'entrée fraîchement persistée serait détruite par le retrait lui-même, quelques instants plus tard, dans le même geste utilisateur. Un bouton « Enregistrer » dans ce contexte serait trompeur : le nouveau dialogue (`_confirm_discard_caption_before_removal()`) propose donc uniquement **Retirer quand même / Annuler**, jamais Save — distinct de `_confirm_discard_caption_before_switch()` (Mission 098/158), dont le Save conserve durablement la caption lors d'un changement d'image/Dataset/contexte.

## 5. Condition exacte de déclenchement

```python
removed_image_ids = {item.data(Qt.UserRole + 1) for item in selected_items}
if self._caption_dirty and self._caption_loaded_image_id in removed_image_ids:
    ...
```
Une seule condition, fondée sur l'identité canonique (`image_id`, jamais `file_path`), couvre indifféremment la sélection simple et la multi-sélection : dès lors que l'image portant le brouillon dirty appartient au lot réellement retiré, le dialogue apparaît — qu'une seule image ou plusieurs soient sélectionnées.

## 6. Contrat

- **Dirty image retirée** (seule ou parmi d'autres) → dialogue « Retirer quand même » / « Annuler », Annuler par défaut.
- **Dirty image non retirée** (d'autres images du lot sont retirées) → aucun dialogue, brouillon conservé. Prouvé sûr par le mécanisme déjà existant : la restauration de sélection par identité (Mission 082) retrouve l'image dirty (toujours présente), `_refresh_caption_panel_for_current_selection()` court-circuite sur l'égalité d'identité — aucun appel à `_load_caption_into_editor()`.
- **Caption clean** → aucun dialogue, comportement historique inchangé.
- **Cancel** → `return` immédiat ; `DatasetManager.remove_images()` jamais appelé ; aucune image retirée ; `_caption_dirty` reste `True` ; texte de `caption_edit` intact. Le clic sur « Retirer du dataset » ne modifie lui-même aucun état Qt de sélection avant l'exécution du handler (contrairement aux gardes de sélection M158) — aucun `blockSignals()`/restauration nécessaire.
- **Retirer quand même** → le brouillon est explicitement considéré comme abandonné (`_caption_dirty = False`, `save_caption_button.setEnabled(False)`), jamais sauvegardé ; le retrait de toutes les images sélectionnées se poursuit selon le comportement historique de `remove_selected_images_from_dataset()`.
- **Échec de `remove_images()` après confirmation** → le rollback Manager (déjà existant, Mission 076) restaure `dataset.images`/`dataset.entries` ; le chemin d'erreur historique affiche le message et rappelle `update_datasets()` ; l'image reste dans le Dataset. `_refresh_caption_panel_for_current_selection()`'s propre court-circuit d'identité (inchangé) empêche `update_datasets()` seul de recharger l'éditeur, puisque l'identité de l'image n'a en réalité jamais changé — le chemin d'échec de `remove_selected_images_from_dataset()` appelle donc explicitement `self._load_caption_into_editor(abandoned_dirty_image_id)` juste après, pour resynchroniser l'UI sur la caption persistée originale. Le brouillon abandonné par le choix explicite de l'utilisateur n'est **jamais** ressuscité — mais un `_caption_dirty == False` correspond toujours désormais à la valeur canonique réellement persistée : `caption_edit` affiche la caption d'origine restaurée, jamais le texte abandonné.

## 7. Nouveau dialogue

`_confirm_discard_caption_before_removal()` — distinct de `_confirm_discard_caption_before_switch()`, jamais réutilisé ni modifié. Mirroir du pattern à deux boutons déjà utilisé par `delete_dataset()` (`AcceptRole`/`RejectRole`, comparaison par identité via `clickedButton()`), plutôt que le pattern à trois boutons standards Save/Discard/Cancel :
```python
def _confirm_discard_caption_before_removal(self) -> bool:
    box = QMessageBox(self)
    box.setWindowTitle("Modifications non enregistrées")
    box.setText(
        "L'image actuellement sélectionnée possède des modifications "
        "de caption non enregistrées. Retirer cette image du dataset "
        "fera perdre ces modifications. Continuer ?"
    )
    remove_button = box.addButton("Retirer quand même", QMessageBox.AcceptRole)
    cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is remove_button
```
Aucun bouton Save. Annuler par défaut. Ce n'est **pas** une confirmation destructive générale du retrait d'image (« Êtes-vous sûr ? ») — ce dernier reste hors scope, décision produit distincte déjà confirmée cohérente avec `LoRAPage.remove_selected_files()` (aucune confirmation non plus, puisque ni l'un ni l'autre ne touche le fichier physique).

## 8. Emplacement de la garde

Exclusivement en tête de `remove_selected_images_from_dataset()`, avant tout appel à `DatasetManager.remove_images()` — jamais dans `update_datasets()`/`_refresh_caption_panel_for_current_selection()`/`_load_caption_into_editor()`, qui restent de purs refreshs programmatiques sans dialogue, exactement le principe déjà établi par Mission 158.

## 9. Non-régression Mission 158

**Aucune méthode M158 modifiée** : `on_image_selection_changed()`, `on_dataset_selection_changed()`, `confirm_context_change()`, `reset_for_context_change()`, `_confirm_discard_caption_before_switch()`, `_save_caption_or_report_error()` sont restées intactes (confirmé par relecture directe du diff Git). Aucun changement de `main_window.py` — cette garde protège une action locale à la Page, pas un changement de contexte global, contrairement aux guards New/Open/Close de M158.

## 10. Scope

**Un seul fichier de production modifié** : `src/ui/pages/datasets_page.py`. Aucun changement Manager/Domain/MainWindow.

## 11. Tests ajoutés

**+6 tests nets** (2917 → 2923 tests collectés), tous dans `DatasetsPageCaptionPanelTest` (`tests/integration/test_datasets_page.py`) :
- `test_removing_the_dirty_image_cancel_keeps_draft_and_image`
- `test_removing_a_selection_including_the_dirty_image_cancel_keeps_draft_and_all_images`
- `test_removing_the_dirty_image_discard_removes_it_and_clears_the_draft`
- `test_removing_other_images_while_a_different_image_is_dirty_never_prompts_and_preserves_draft` (preuve explicite du Cas C — brouillon exclu du retrait)
- `test_removing_images_without_any_dirty_draft_never_prompts`
- `test_removing_the_dirty_image_remove_failure_after_discard_shows_error_and_preserves_original_caption`

## 12. Résultats réels

- Ciblés (25 tests de `DatasetsPageCaptionPanelTest`, incluant les 6 nouveaux) : **25/25 passés**.
- `test_datasets_page.py` complet : **83/83 passés** (77 préexistants + 6 nets — non-régression `remove_*` historiques et `DatasetsPageConfirmContextChangeTest` M158 confirmée, aucune modification).
- Suite voisine `test_dataset_roundtrip.py` (Manager non touché) : **137/137 passés**.
- Suites M158 `test_main_window_new_project.py` + `test_main_window_close_event.py` : **45/45** + **47/47** — aucun dialogue M159 dans les transitions New/Open/Close.
- **Suite complète : 2923 collectés/2923 passés, 0 échoué** (328.518s). Équation : 2917 (clôture Mission 158) + 6 nets ajoutés par Mission 159 = **2923**, cohérent.
- `git diff --check` : clean (avertissement `LF will be replaced by CRLF` uniquement, non bloquant).
- Exactement 1 fichier de production modifié (`src/ui/pages/datasets_page.py`), plus 1 fichier de test — aucun deuxième fichier de production.
