# Mission 054 — Rename Dataset and Training after Creation

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat validé par l'architecte, implémentation réalisée conformément au contrat, 24/24 tests ciblés nets nouveaux (8 `DatasetManagerRenameTest` + 5 `DatasetsPageRenameTest` + 6 `TrainingManagerRenameTest` + 5 `TrainingPageRenameTest`), 945/945 tests automatisés verts, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS — y compris le comportement asymétrique confirmé du tri (`dataset_list` en ordre d'insertion, `training_list` retrié — Mission 051) et la propagation de `TrainingPage.dataset_label` via le seul canal `WORKSPACE_SAVED` déjà existant. Commit fonctionnel `a892f57b3f6fabffcc84203b0417a622fb80974d`, tag `v0.2-mission054`, GitHub Release publiée.

## 1. Contexte

Missions 052 et 053 ont étendu à `Model`, `Workflow`, `LoRA` puis `Prompt` le renommage post-création déjà disponible pour `Character`. `Dataset` et `Training` restaient explicitement hors périmètre des deux missions — non par incompatibilité constatée, mais parce que ni l'un ni l'autre n'expose aujourd'hui **aucune** méthode `update()` d'aucune sorte, un précédent structurel plus significatif que celui d'étendre une famille `update_*()` déjà existante (le cas de Model/Workflow/LoRA/Prompt). Ce mini-audit vérifie que cette absence de précédent ne cache aucune décision substantielle et que le mécanisme déjà établi cinq fois (`Character`/`Model`/`Workflow`/`LoRA`/`Prompt`) s'applique tel quel.

## 2. Mini-audit réalisé

**`Dataset`** ([domain/dataset.py](src/domain/dataset.py)) : `dataset_id`, `name`, `images: list[Image]`. Le champ `name` existe déjà, sérialisé symétriquement par `to_dict()`/`from_dict()`.

**`Training`** ([domain/training.py](src/domain/training.py)) : `training_id`, `name`, `dataset_id`. Même constat — `name` existe déjà.

**`DatasetManager`** ([dataset_manager.py](src/managers/dataset_manager.py)) : méthodes actuelles — `create()`, `select()`, `is_referenced_by_training()`, `delete()`, `preview_collisions()`, `add_images()`, `remove_images()`. **Aucune méthode `update()` d'aucune sorte** — `update_name()` en serait la toute première. `active_dataset`/`_find()` opèrent par `dataset_id`, jamais par position.

**`TrainingManager`** ([training_manager.py](src/managers/training_manager.py)) : méthodes actuelles — `create()`, `select()`, `delete()`. Même constat, **aucune méthode `update()`**. `active_training`/`_find()` opèrent par `training_id`.

**`DatasetsPage`** ([datasets_page.py](src/ui/pages/datasets_page.py)) : `update_datasets()` suit le pattern `blockSignals(True)` → `clear()` → reconstruction → `setCurrentItem()` → `blockSignals(False)`, sans aucun dirty-state propre (contrairement à `PromptsPage`). **Précision confirmée par relecture directe (correction par rapport à une première impression) : `dataset_list` n'est PAS trié** — `update_datasets()` itère `self.dataset_manager.list_datasets()` tel quel, sans `sorted()` ; le `sort_combo`/tri Nom-Date de Mission 048/049 s'applique uniquement à `images_list` (les images du Dataset actif), jamais à `dataset_list` lui-même, qui reste donc en ordre d'insertion de `Character.datasets`. `dataset_list` n'a jamais fait partie du périmètre de Mission 051 (qui a trié `ModelsPage`/`WorkflowsPage`/`TrainingPage`/`PromptsPage`/`LoRAPage`, pas `DatasetsPage`). Aucun mécanisme comparable à `text_edit`/`_dirty` à préserver.

**`TrainingPage`** ([training_page.py](src/ui/pages/training_page.py)) : `update_trainings()` suit le même pattern exact, sans dirty-state. Note d'interaction observée, non bloquante : `dataset_label` affiche `f"Dataset : {dataset['name']} [...]"`, recalculé à chaque appel de `update_trainings()` via `_describe_dataset()` — un renommage de Dataset via `DatasetsPage` publiera `WORKSPACE_SAVED`, qui rafraîchira `TrainingPage` par le canal déjà existant si elle est actuellement affichée/abonnée ; aucun changement de `TrainingPage` n'est requis pour ce comportement, déjà correct par construction.

**Test-order-contract** : `grep` de `dataset_list.item(`/`training_list.item(` sur `tests/integration/test_dataset_roundtrip.py`, `test_datasets_page.py`, `test_training_roundtrip.py` — aucune occurrence pour `dataset_list`, et les seules occurrences pour `training_list` (`TrainingPageSortTest`, Mission 051) portent sur l'ordre d'affichage trié, jamais sur l'ordre d'insertion. **Aucune reformulation de test existant nécessaire.**

**Politique de validation du nom** : `DatasetsPage.create_dataset()`/`TrainingPage.create_training()` strippent et rejettent le nom vide via `QInputDialog`, exactement comme tous les flux de création déjà audités (`create_character()`/`create_model()`/`create_workflow()`/`create_lora()`/`create_prompt()`) — un flux différent du renommage. Le seul précédent de renommage existant (`Character`/`Model`/`Workflow`/`LoRA`/`Prompt`) ne stripe ni ne rejette. Mission 054 suit ce même précédent, sans en inventer un nouveau.

**EventBus/Domain/persistance** : aucun changement nécessaire. `update_name()` appellera `self._workspace_manager.save()`, qui publie `WORKSPACE_SAVED` — déjà souscrit par `DatasetsPage.update_datasets`/`TrainingPage.update_trainings`. `Dataset.to_dict()`/`from_dict()`/`Training.to_dict()`/`from_dict()` inchangés, aucune migration `project.json`.

**Aucune décision produit ou architecturale substantielle ne reste ouverte** — le contrat, le mécanisme et la politique de validation sont tous entièrement déterminés par les cinq précédents directs (`Character`/`Model`/`Workflow`/`LoRA`/`Prompt`).

## 3. Objectif

Étendre à `Dataset` et `Training` le renommage post-création déjà livré pour `Character`/`Model`/`Workflow`/`LoRA`/`Prompt`, refermant ainsi la dernière asymétrie de renommage restant dans l'application — toutes les entités possédant un champ `name` deviennent renommables après leur création.

## 4. Contrat fonctionnel — réellement implémenté

- `DatasetManager.update_name(name: str) -> bool` — nouvelle méthode sibling additive, première méthode `update()` de ce Manager. Opère sur `self.active_dataset` (implicite, mirroir de `ModelManager.update_name()`/`update_text()`/`PromptManager.update_name()` plutôt que du style `lora_id` explicite de `LoRAManager.update_name(lora_id, name)`). Idempotent : `False`/aucun `save()` si aucun dataset actif ou si `name` identique à la valeur stockée. Aucun événement dédié publié. Chaîne vide légitime, non validée, non strippée.
- `TrainingManager.update_name(name: str) -> bool` — même contrat exact, opère sur `self.active_training`.
- `DatasetsPage` gagne un `QLineEdit` **`name_edit`**, ajouté juste après `dataset_list`. Renommage déclenché sur `editingFinished` — `rename_dataset()` : si `self.dataset_manager.active_dataset_id is None: return`, sinon `self.dataset_manager.update_name(self.name_edit.text())`.
- `TrainingPage` gagne un `QLineEdit` **`name_edit`**, ajouté juste après `training_list`. Même mécanisme, `rename_training()`.
- `update_datasets()`/`update_trainings()` gagnent le peuplement de `name_edit` — capture du nom de l'entité active pendant la boucle existante, `self.name_edit.setText(active_name)` (chaîne vide si aucune entité active) en fin de méthode.
- `dataset_id`/`training_id`, `Dataset.images`, `Training.dataset_id` restent strictement inchangés par un renommage — vérifié par test dédié et smoke test réel.
- **Comportement de tri confirmé, asymétrique entre les deux entités** : `training_list` (trié depuis Mission 051) se retrie automatiquement après un renommage, sélection conservée par `training_id`, jamais par position — mirroir exact de Model/Workflow/LoRA/Prompt. `dataset_list` (jamais trié) **n'a reçu aucun tri nouveau** — Mission 054 n'introduit aucun `sorted()` là où il n'existait pas déjà ; le Dataset renommé reste simplement sélectionné par `dataset_id`, sa position dans la liste ne change pas puisque l'ordre d'insertion, lui, ne change pas.
- `TrainingPage.dataset_label` reflète le nouveau nom du Dataset après un renommage, sans aucun nouveau wiring EventBus — `_describe_dataset()` relit `dataset_manager.list_datasets()` à chaque appel de `update_trainings()`, déjà souscrite à `WORKSPACE_SAVED` (canal déjà publié par `DatasetManager.update_name()` via `save()`), confirmé par test et smoke test réel.

## 5. Périmètre — réellement modifié

Production (4) :
- `src/managers/dataset_manager.py` (nouvelle méthode `update_name()`)
- `src/managers/training_manager.py` (nouvelle méthode `update_name()`)
- `src/ui/pages/datasets_page.py` (import `QLineEdit` si nécessaire, `name_edit`, `rename_dataset()`, peuplement dans `update_datasets()`)
- `src/ui/pages/training_page.py` (import `QLineEdit` si nécessaire, `name_edit`, `rename_training()`, peuplement dans `update_trainings()`)

Tests (2, aucun nouveau fichier) :
- `tests/integration/test_dataset_roundtrip.py` (`DatasetManagerRenameTest` + `DatasetsPageRenameTest`, nouvelles classes)
- `tests/integration/test_training_roundtrip.py` (`TrainingManagerRenameTest` + `TrainingPageRenameTest`, nouvelles classes)

## 6. Hors périmètre

- Toute contrainte d'unicité de nom, toute confirmation avant renommage.
- Toute modification de `Dataset.images`/`Training.dataset_id` ou de leur mécanisme d'ajout/retrait d'images/de sélection de Dataset source.
- Tout nouveau wiring EventBus.
- Rafraîchissement explicite de `TrainingPage.dataset_label` par un mécanisme dédié — déjà correct par construction via `WORKSPACE_SAVED` existant (voir mini-audit).
- Le besoin futur « Dataset de références → Inference » (documenté dans `docs/PROJECT_CONTEXT.md`, dépendant d'une primitive Inference 0..N références avec rôles qui n'existe pas encore) — non implémenté, aucun scaffolding créé.
- Toute autre entité, toute autre dette UX documentée dans `docs/PROJECT_CONTEXT.md`.

## 7. Stratégie de tests — réellement mise en œuvre

`DatasetManagerRenameTest` (8 tests, `test_dataset_roundtrip.py`) : renommage réel, idempotence (`save()` non appelé si valeur inchangée, `patch.object`), aucun dataset actif → `False`, `dataset_id`/`images` préservés, chaîne vide légitime, fichier physique jamais touché, **référence Training conservée par ID après renommage du Dataset** (`test_rename_preserves_training_reference_by_id`), persistance après fermeture/réouverture.

`DatasetsPageRenameTest` (5 tests) : renommage via le vrai widget, aucun dataset actif → no-op, **`dataset_list` reste en ordre d'insertion après renommage** (`test_dataset_list_stays_in_insertion_order_after_rename` — le Dataset renommé garde sa position, sélection par `dataset_id`), **`TrainingPage.dataset_label` reflète le nouveau nom** (`test_rename_updates_training_dataset_label`), persistance après fermeture/réouverture via l'UI.

`TrainingManagerRenameTest` (6 tests, `test_training_roundtrip.py`) : renommage réel, idempotence, aucune training active → `False`, `training_id`/`dataset_id` préservés, chaîne vide légitime, persistance après fermeture/réouverture.

`TrainingPageRenameTest` (5 tests) : renommage via le vrai widget, aucune training active → no-op, **retri Mission 051 confirmé dans les deux sens** (déplacement en tête et en fin de liste) avec sélection conservée par `training_id`, persistance après fermeture/réouverture via l'UI.

**Non-régressions vérifiées** par la suite complète (`test_dataset_roundtrip.py` 49/49, `test_datasets_page.py` 45/45, `test_training_roundtrip.py` 34/34) : `add_images()`/`remove_images()`/`is_referenced_by_training()`/suppression Dataset, cycle Training complet, compteur Training du Dashboard, `DatasetsPageGalleryTest`/`DatasetsPageGallerySortTest`/`TrainingPageSortTest`/`TrainingCreationWithoutManualCharacterSelectionTest` tous inchangés.

**24/24 tests ciblés nets nouveaux, tous verts** (8+5+6+5). **945/945 tests automatisés verts** au total (921 précédents + 24 nets nouveaux).

## 8. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels), script exclusivement dans le scratchpad de session, confirmé absent du dépôt (`git status --porcelain --ignored`).

Points observés réellement, tous conformes : Dataset créé avec une image physique réelle, utilisé par une Training réelle → renommage réel du Dataset → `dataset_id`/`images` inchangés, fichier physique toujours présent, `dataset_list` reste en ordre d'insertion (aucun tri introduit), sélection conservée par `dataset_id` → `Training.dataset_id` toujours identique, `TrainingPage.dataset_label` reflète le nouveau nom sans aucun wiring EventBus nouveau, `is_referenced_by_training()` toujours `True` → renommage réel de la Training → `training_id`/`dataset_id` inchangés, `training_list` retrié (Mission 051), sélection conservée par `training_id` → non-régression de `add_images()`/`remove_images()` après le renommage du Dataset → fermeture/réouverture réelle du Workspace : noms et relations (`Training.dataset_id`) tous confirmés persistés à l'identique.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 9. Risques / non-régressions

- **Risque de sur-portée** : écarté — `Dataset.images`/`Training.dataset_id` confirmés inchangés par test et smoke test, `git diff --stat` limité aux 4 fichiers de production + 2 fichiers de test attendus.
- **Risque d'interaction avec le tri Mission 051** : écarté pour `training_list` — retri confirmé dans les deux sens, sélection par ID. **`dataset_list` confirmé non trié, aucun tri introduit par cette mission** (vérifié par test dédié).
- **Premier `update()` pour ces deux Managers** : aucune contradiction constatée — contrat entièrement dicté par les cinq précédents directs.

## 10. Pourquoi maintenant

Ce candidat referme la dernière asymétrie de renommage de l'application (toutes les entités à champ `name` deviennent renommables) et ne comportait, après inspection directe du code, aucune décision produit ou architecturale substantielle restant ouverte — contrairement aux autres besoins documentés dans `docs/PROJECT_CONTEXT.md` (`comfyui_path`, sélection multi-engine, refonte Settings, i18n, publication sociale, primitive Inference multi-références), qui nécessitent chacun un arbitrage produit/architectural explicite avant toute implémentation.

## État d'avancement

- Audit de sélection (candidats Mission 054), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 24/24 ciblés (8+5+6+5), 945/945 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git (commit/tag/Release) : **entièrement effectuée**.

## 11. Fichiers concernés

Production (4) :
- `src/managers/dataset_manager.py` (nouvelle méthode `update_name()`)
- `src/managers/training_manager.py` (nouvelle méthode `update_name()`)
- `src/ui/pages/datasets_page.py` (import `QLineEdit`, `name_edit`, `rename_dataset()`, peuplement dans `update_datasets()`)
- `src/ui/pages/training_page.py` (import `QLineEdit`, `name_edit`, `rename_training()`, peuplement dans `update_trainings()`)

Tests (2, aucun nouveau fichier) :
- `tests/integration/test_dataset_roundtrip.py`
- `tests/integration/test_training_roundtrip.py`

Documentation (1, nouveau fichier) :
- `docs/missions/MISSION_054.md`

## 12. Commit correspondant

- Hash : `a892f57b3f6fabffcc84203b0417a622fb80974d`
- Message : `feat: rename Dataset and Training after creation`
- 7 fichiers modifiés, 698 insertions.

## 13. Tag-release correspondant

- Tag annoté : `v0.2-mission054`, ciblant exactement le commit `a892f57b3f6fabffcc84203b0417a622fb80974d`.
- GitHub Release : `Mission 054 - Rename Dataset and Training after Creation`, publiée.

## 14. État final

**Mission 054 entièrement close.** La dernière asymétrie de renommage de l'application est résolue — toutes les entités possédant un champ `name` (`Character`, `Model`, `Workflow`, `LoRA`, `Prompt`, `Dataset`, `Training`) sont désormais renommables après leur création. `dataset_list` reste délibérément non triée (comportement préexistant, confirmé inchangé), `training_list` reste triée depuis Mission 051. Le besoin futur « Dataset de références → Inference » reste enregistré dans `docs/PROJECT_CONTEXT.md`, non implémenté, dépendant d'une primitive Inference 0..N références avec rôles qui n'existe pas encore.
