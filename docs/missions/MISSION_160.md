# Mission 160 — Protect Unsaved Dataset Caption When Deleting Its Dataset

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `DatasetsPage.delete_dataset()` (`src/ui/pages/datasets_page.py`) ne consultait pas `_caption_dirty` avant de supprimer le Dataset actif. Lorsqu'une caption modifiée mais non sauvegardée appartenait à une image de ce Dataset, la confirmation destructive existante ne mentionnait rien de ce brouillon, et le refresh synchrone consécutif à la suppression l'écrasait silencieusement — un chemin utilisateur direct, à un clic, découvert par l'audit global post-Mission 159.

## 1. Invariant

**Une caption modifiée mais non enregistrée ne doit jamais être perdue silencieusement lorsque l'utilisateur demande la suppression du Dataset qui la contient.** La décision utilisateur doit être prise avant toute mutation, dans la confirmation destructive déjà existante — jamais dans un second dialogue.

## 2. Bug

`delete_dataset()` affichait un dialogue de confirmation générique, puis appelait `DatasetManager.delete()`. `WorkspaceManager.save()`, appelé à l'intérieur de `delete()`, publie `WORKSPACE_SAVED` de façon **synchrone, avant même que `delete()` ne retourne** à son appelant — `update_datasets()` (câblé sur cet événement) s'exécute alors immédiatement, le Dataset supprimé disparaît de `active_images`, l'identité de l'image chargée dans l'éditeur de caption ne peut plus être retrouvée, et `_load_caption_into_editor()` écrase inconditionnellement le brouillon — sans qu'aucun avertissement n'ait jamais été montré à l'utilisateur.

## 3. Invariant propriétaire — aucune comparaison d'identité supplémentaire nécessaire

**`_caption_dirty == True` implique nécessairement que l'image actuellement chargée appartient au Dataset actif — celui-là même que `delete_dataset()` s'apprête à supprimer.** Preuve : `caption_edit` n'est activé, et `_on_caption_changed()` (seule méthode positionnant `_caption_dirty = True`) n'est atteignable, que via `_load_caption_into_editor(image_id)` avec un `image_id` non `None`, lui-même toujours issu d'`active_images` du Dataset actif (`update_datasets()`). Un changement de Dataset est intercepté par `on_dataset_selection_changed()` (Mission 158) : tant que le brouillon n'est pas résolu (Save/Discard/Cancel), `DatasetManager.select()` n'est jamais appelé et la sélection Qt reste sur l'ancien Dataset. `delete_dataset()` ne lit que `dataset_list.currentItem()`, toujours synchronisé avec `active_dataset_id` par cette même garde. **Il n'existe donc aucun scénario UI où un Dataset B serait sélectionné pour suppression pendant qu'un brouillon dirty appartient à un Dataset A distinct** — la garde se réduit à la seule condition `if self._caption_dirty:`, sans comparaison d'`image_id` contre un quelconque ensemble, contrairement à Mission 159 (dont la garde devait vérifier l'appartenance de l'image au lot retiré, un sous-ensemble réel du Dataset actif).

## 4. Confirmation destructive existante enrichie conditionnellement — aucun second dialogue

`delete_dataset()` possédait déjà une confirmation à 2 boutons (Supprimer/Annuler, Annuler par défaut). Plutôt que d'empiler un second dialogue pour une décision qui reste logiquement unique (« je détruis le Dataset — et donc aussi mon brouillon — oui/non »), ce même dialogue est désormais enrichi conditionnellement :

- **Caption clean** (`_caption_dirty == False`) : texte et comportement strictement historiques — irréversibilité, distinction galerie/copies privées, aucun changement.
- **Caption dirty** (`_caption_dirty == True`) : le même texte reçoit une phrase supplémentaire avertissant que l'image actuellement sélectionnée possède des modifications de caption non enregistrées, et que celles-ci seront également perdues si la suppression est confirmée.

Boutons inchangés : Supprimer / Annuler, Annuler par défaut. **Aucun troisième bouton, aucun Save.**

## 5. Pourquoi aucun Save

`dataset.entries` (où vivent les captions) est un champ du `Dataset` lui-même, sérialisé uniquement via `Dataset.to_dict()`. `DatasetManager.delete()` retire l'objet `Dataset` complet — donc l'intégralité de `dataset.entries`, pas seulement l'entrée de l'image courante — de `character.datasets`, puis persiste cette suppression. Un Save juste avant Delete écrirait la caption dans `project.json`, immédiatement effacée par la suppression du Dataset entier quelques instants plus tard, dans le même geste utilisateur — aussi trompeur que pour Mission 159, mais de façon encore plus totale (c'est tout le Dataset, pas une seule entrée, qui disparaît).

## 6. Contrat

- **Cancel** (avec ou sans caption dirty) : `item`/`dataset_id` sont lus avant l'affichage du dialogue, qui ne modifie lui-même aucun widget Qt — un `return` immédiat suffit. `DatasetManager.delete()` jamais appelé, Dataset intact, image courante intacte, sélection intacte, texte exact du brouillon intact, `_caption_dirty == True`, bouton Save toujours activé. Aucune restauration Qt artificielle, aucun refresh forcé.
- **Confirm — succès** : **aucun pré-abandon du brouillon avant l'appel Manager** (différence volontaire avec Mission 159 — voir §7). `WorkspaceManager.save()`, appelé à l'intérieur de `DatasetManager.delete()`, publie `WORKSPACE_SAVED` de façon synchrone ; `update_datasets()` → `_refresh_caption_panel_for_current_selection()` constate une identité rompue (`active_dataset_id` devient `None`, `images_list` se vide, `new_image_id` devient `None`, ne peut jamais égaler `_caption_loaded_image_id`) → `_load_caption_into_editor(None)` s'exécute sans condition, produisant naturellement : Dataset supprimé, aucune image courante, éditeur de caption vidé et désactivé, `_caption_dirty == False`, bouton Save désactivé. Aucune ligne de code supplémentaire n'est nécessaire dans `delete_dataset()` pour ce chemin.
- **Confirm — échec Manager** : `WorkspaceManager.save()` ne publie `WORKSPACE_SAVED` qu'après une écriture réussie (jamais avant/pendant un échec) — sur `WorkspaceManagerError`, le rollback Manager (Mission 068) restaure le Dataset à son index exact et `active_dataset_id`, **et aucun refresh ne se déclenche jamais**. Puisque le brouillon n'a jamais été touché avant l'appel, il reste exactement dans l'état où l'utilisateur l'a laissé : Dataset toujours présent, image courante toujours sélectionnée (même `QListWidgetItem`, jamais reconstruit), texte exact du brouillon toujours affiché, `_caption_dirty == True`, bouton Save toujours activé, message d'erreur historique affiché. Le brouillon n'est **pas** considéré comme abandonné puisque la suppression n'a pas réussi.

## 7. Différence volontaire avec Mission 159 — pas de pré-abandon du brouillon

Mission 159 marquait explicitement le brouillon comme abandonné (`_caption_dirty = False`, bouton désactivé) **avant** d'appeler `DatasetManager.remove_images()`, parce que ce Manager publie lui aussi `WORKSPACE_SAVED` de façon synchrone en cas de succès, nécessitant une resynchronisation explicite en cas d'échec (l'image restant présente et sélectionnée, l'identité ne change pas, le court-circuit d'identité empêchait tout resync naturel). Mission 160 **n'a pas besoin de ce pré-abandon** : sur succès, l'identité change nécessairement (le Dataset entier disparaît, `new_image_id` devient toujours `None`) — le refresh existant suffit seul ; sur échec, ne rien pré-abandonner signifie que rien n'a besoin d'être restauré, puisque rien n'a été perdu (le Dataset n'a pas réellement été supprimé). Ce choix évite de reproduire l'incohérence corrigée en fin de Mission 159 (`caption_edit` affichant un brouillon abandonné pendant que `_caption_dirty == False` et le Domain contenant la caption originale) — ici, cette incohérence ne peut structurellement jamais apparaître, puisqu'aucune valeur n'est jamais marquée « propre » avant que le succès ne soit acquis.

## 8. Aucun helper supplémentaire

`_confirm_discard_caption_before_switch()` et `_confirm_discard_caption_before_removal()` ne sont pas réutilisés (leur option Save, ou leur texte dédié à une action différente, seraient inadaptés ici). Aucun nouveau helper n'a été créé — la modification se limite à la construction conditionnelle du texte du dialogue déjà existant, à l'intérieur de `delete_dataset()` elle-même.

## 9. Emplacement de la garde

Exclusivement dans `delete_dataset()`, au moment de la construction du texte du dialogue — jamais dans `DatasetManager.delete()`, `update_datasets()`, l'EventBus ou `_refresh_caption_panel_for_current_selection()`, qui restent de purs refreshs programmatiques sans dialogue.

## 10. Non-régression Missions 158/159

**Aucune méthode M158/M159 modifiée** : `on_image_selection_changed()`, `on_dataset_selection_changed()`, `confirm_context_change()`, `reset_for_context_change()`, `_confirm_discard_caption_before_switch()`, `_confirm_discard_caption_before_removal()`, `_save_caption_or_report_error()`, `remove_selected_images_from_dataset()`, `update_datasets()`, `_refresh_caption_panel_for_current_selection()`, `_load_caption_into_editor()` sont restées intactes (confirmé par lecture directe du diff Git). Aucun changement de `DatasetManager`, `Dataset` (Domain), `MainWindow` ou EventBus.

## 11. Scope

**Un seul fichier de production modifié** : `src/ui/pages/datasets_page.py`. Diff strictement confiné à la construction du texte du dialogue de confirmation dans `delete_dataset()` — aucune nouvelle méthode, aucun nouveau dialogue.

## 12. Tests ajoutés

**+5 tests nets** (2923 → 2928 tests collectés), tous dans `DatasetsPageCaptionPanelTest` (`tests/integration/test_datasets_page.py`) :
- `test_deleting_the_dataset_with_a_dirty_caption_cancel_keeps_dataset_and_draft`
- `test_deleting_the_dataset_with_a_dirty_caption_confirm_deletes_and_clears_the_draft`
- `test_deleting_the_dataset_without_a_dirty_caption_shows_the_historical_confirmation_text`
- `test_deleting_the_dataset_with_a_dirty_caption_confirmation_text_mentions_the_lost_draft`
- `test_deleting_the_dataset_with_a_dirty_caption_manager_failure_preserves_the_draft` (preuve empirique du contrat d'échec §6 — provoque un échec réel via `patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError(...))`, exerçant le vrai rollback `DatasetManager.delete()`, et prouve explicitement que le Domain conserve la caption originale plutôt que le brouillon non sauvegardé)

## 13. Résultats réels

- Ciblés (5 nouveaux) : **5/5 passés**.
- `DatasetsPageCaptionPanelTest` complet : **30/30 passés** (25 préexistants + 5 nets — non-régression image switch/Dataset switch/context change/retrait M159/échec M159 confirmée).
- `DatasetsPageConfirmContextChangeTest` (M158) : **5/5 passés**.
- `test_datasets_page.py` complet : **88/88 passés** (83 préexistants + 5 nets).
- `DatasetsPageDeleteConfirmationTest` (`test_dataset_roundtrip.py`, 8 tests historiques Mission 062/068/075) : **8/8 passés**, non modifiés.
- `test_dataset_roundtrip.py` complet : **137/137 passés**, inchangé.
- **Suite complète : 2928 collectés/2928 passés, 0 échoué** (338.105s). Équation : 2923 (clôture Mission 159) + 5 nets ajoutés par Mission 160 = **2928**, cohérent. Une première exécution a rencontré un crash natif (exit 139) sans rapport avec ce diff — dette de harnais déjà documentée (`STATUS_HEAP_CORRUPTION`-class, voir `docs/missions/MISSION_097.md`/`MISSION_100.md`) ; la seconde exécution complète, indépendante, a abouti proprement à 2928/2928.
- `git diff --check` : clean (avertissement `LF will be replaced by CRLF` uniquement, non bloquant).
- Exactement 1 fichier de production modifié (`src/ui/pages/datasets_page.py`), plus 1 fichier de test — aucun deuxième fichier de production.

## 14. Clôture Git

Commit fonctionnel : `97787a90a02b5ec0761454c7ed8e61763db90992` (« Protect unsaved dataset caption when deleting dataset », 3 fichiers : `src/ui/pages/datasets_page.py`, `tests/integration/test_datasets_page.py`, `docs/missions/MISSION_160.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission160` (objet `671697e2339b3e2e7c6f43dcaa2ea431024b81b1`, cible `97787a90a02b5ec0761454c7ed8e61763db90992`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission160 — Protect Unsaved Dataset Caption When Deleting Its Dataset` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2928/2928, 0 échoué** (338.105s). Le tag `v0.2-mission159` (`4a0d355f35966fcf11814078b13b67a1264ef60b` → objet `ac96e12f75886a1bc8f97da1c6ae41d3b6055daf`) reste inchangé. Distinctions préservées : bug corrigé = perte silencieuse d'une caption dirty lors de la suppression du Dataset qui la contient ; changement de Dataset = déjà protégé par Mission 158, non une correction de cette mission ; retrait de l'image propriétaire du brouillon = déjà protégé par Mission 159, non une correction de cette mission ; aucun Save n'a jamais été proposé (la caption est supprimée par la suppression du Dataset lui-même) ; aucun pré-abandon du brouillon avant l'appel Manager, différence volontaire avec Mission 159 (§7) ; une première exécution de la suite complète a rencontré le crash natif `exit 139` déjà associé à la dette de harnais documentée (`docs/missions/MISSION_097.md`/`MISSION_100.md`) — dette préexistante, non introduite et non corrigée par cette mission ; les guards Mission 158/159 et les refreshs génériques restent intégralement inchangés.
