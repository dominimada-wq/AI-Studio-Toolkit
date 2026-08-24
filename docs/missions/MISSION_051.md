# Mission 051 — Sort Remaining Entity Lists by Name (Models, Workflows, Prompts, Trainings, LoRAs)

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat validé par l'architecte, implémentation réalisée conformément au contrat, 26/26 tests ciblés nets nouveaux (5 `ModelsPageSortTest` + 5 `WorkflowsPageSortTest` + 5 `TrainingPageSortTest` + 6 `PromptsPageSortTest` + 5 `LoRAPageSortTest`), 885/885 tests automatisés verts, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS sur les cinq Pages. Commit fonctionnel `0d6a2c54a79dc42701c1c250e8f63167857e948c` (`feat: sort Models, Workflows, Trainings, Prompts and LoRAs lists by name`), tag annoté `v0.2-mission051` (`Mission 051 - Sort Remaining Entity Lists by Name`), GitHub Release `v0.2-mission051` **publiée** — confirmée par l'architecte du projet.

## 1. Contexte

Un audit read-only du dépôt après clôture de Mission 050 a comparé le traitement des listes d'entités à travers toute l'application. Mission 048 a établi un tri alphabétique (insensible à la casse, toujours actif, sans contrôle UI) pour les deux galeries d'images (`ImagesPage`/`DatasetsPage`), au motif que l'ordre brut d'insertion rend plus difficile la recherche d'un élément précis à mesure que la collection grandit.

La lecture directe des cinq autres Pages à liste d'entités confirme qu'**aucune n'a jamais reçu ce traitement** : `ModelsPage.update_models()` ([models_page.py:113](src/ui/pages/models_page.py:113)), `WorkflowsPage.update_workflows()` ([workflows_page.py:113](src/ui/pages/workflows_page.py:113)), `TrainingPage.update_trainings()` ([training_page.py:142](src/ui/pages/training_page.py:142)), `PromptsPage._refresh_prompt_list()` ([prompts_page.py:360](src/ui/pages/prompts_page.py:360)) et `LoRAPage.update_loras()` ([lora_page.py:291](src/ui/pages/lora_page.py:291), boucle sur `lora_list` uniquement — `files_list`, traité par Mission 050, n'est pas concerné) itèrent chacune leur liste respective (`list_models()`/`list_workflows()`/`list_trainings()`/`list_prompts()`/`list_loras()`) dans l'ordre brut retourné par leur Manager — lui-même l'ordre d'insertion de la liste Domain sous-jacente (`character.loras`, `character.prompts`, `character.trainings`, `workspace.models`, `workspace.workflows`). Aucune de ces cinq classes Domain (`Model`, `Workflow`, `Prompt`, `Training`, `LoRA`) ne porte de champ date exploitable pour un tri alternatif, et aucune n'expose de fichier unique dont le `mtime` représenterait sans ambiguïté l'entité entière (`LoRA.files` est une liste de 0..N fichiers depuis Mission 050 — un tri par date de fichier n'aurait pas de sens univoque pour cette entité).

Une vérification ciblée des tests existants (`test_model_roundtrip.py`, `test_workflow_roundtrip.py`, `test_training_roundtrip.py`, `test_prompt_roundtrip.py`, `test_lora_roundtrip.py`) confirme qu'**aucun test n'accède à ces cinq `QListWidget` par position** (`grep` de `model_list.item(`, `workflow_list.item(`, `training_list.item(`, `lora_list.item(` : aucune occurrence) — `test_prompt_roundtrip.py::_item_for_prompt()` localise déjà par identité (`Qt.UserRole`), pas par position. **Aucune contradiction de test n'existe**, à la différence de Mission 048 qui avait dû reformuler un test.

## 2. Problème

Cinq listes d'entités (`ModelsPage.model_list`, `WorkflowsPage.workflow_list`, `TrainingPage.training_list`, `PromptsPage.prompt_list`, `LoRAPage.lora_list`) restent affichées dans l'ordre brut d'insertion, sans tri — la même dette déjà résolue pour les galeries Images/Datasets par Mission 048, mais jamais étendue au reste de l'application.

## 3. Objectif

Appliquer aux cinq listes d'entités restantes exactement le même traitement déjà validé et livré par Mission 048 pour les galeries : tri par nom, insensible à la casse, toujours actif, sans aucun contrôle UI, sans persistance, sans changement Domain/Manager/EventBus.

## 4. Contrat fonctionnel validé

- Le tri est calculé à partir de `name` (`model["name"]`/`workflow["name"]`/`training["name"]`/`prompt["name"]`/`lora["name"]`), comparé insensible à la casse (`.lower()` sur la clé de tri uniquement — le nom affiché n'est jamais altéré).
- Le tri est **toujours actif**, sans contrôle UI (pas de combobox/bouton), sans ordre configurable, sans persistance de préférence — mêmes raisons que Mission 048 : un seul critère possible (le nom), donc aucun contrôle n'est justifié (seuil déjà établi par Mission 049 : un second critère coexistant justifierait un contrôle, ce qui n'est pas le cas ici).
- Le tri est **stable** (`sorted()`, garanti stable par Python) : à noms identiques (après normalisation de casse), l'ordre relatif d'origine (ordre de la liste Domain source) est conservé. Aucun second critère de tri n'est ajouté.
- Le tri est appliqué sur une **copie/itérable temporaire** construite juste avant la boucle de peuplement de chaque `QListWidget` — `character.loras`/`character.prompts`/`character.trainings`/`workspace.models`/`workspace.workflows` (Domain) ne sont jamais mutés ni réordonnés, exactement comme Mission 048/049.
- S'applique identiquement aux cinq Pages, pour la cohérence globale déjà recherchée par Mission 048 entre `ImagesPage`/`DatasetsPage`.
- Aucun champ date, aucune combobox/bouton de critère, aucun ordre ascendant/descendant configurable, aucune persistance, aucune modification Domain/Manager/EventBus — tous explicitement hors périmètre (section 6).

## 5. Périmètre

Production (5) :
- `src/ui/pages/models_page.py` (`update_models()` — tri de `models` avant la boucle de peuplement)
- `src/ui/pages/workflows_page.py` (`update_workflows()` — tri de `workflows` avant la boucle de peuplement)
- `src/ui/pages/training_page.py` (`update_trainings()` — tri de `trainings` avant la boucle de peuplement)
- `src/ui/pages/prompts_page.py` (`_refresh_prompt_list()` — tri de `prompts` avant la boucle de peuplement ; `update_prompts()`/`reset_for_context_change()` non touchées au-delà de cet appel déjà existant)
- `src/ui/pages/lora_page.py` (`update_loras()` — tri de `loras` avant la boucle de peuplement du `lora_list` ; la boucle `files_list` de Mission 050 n'est pas concernée)

Tests (5, aucun nouveau fichier) :
- `tests/integration/test_model_roundtrip.py`
- `tests/integration/test_workflow_roundtrip.py`
- `tests/integration/test_training_roundtrip.py`
- `tests/integration/test_prompt_roundtrip.py`
- `tests/integration/test_lora_roundtrip.py`

## 6. Hors périmètre

- Tri par date ou tout autre critère, toute combobox/bouton de sélection du critère (aucun besoin de coexistence de critères identifié ici, à la différence des galeries Images/Datasets après Mission 049).
- Ordre ascendant/descendant configurable, persistance d'une préférence de tri.
- Toute modification de `Model`, `Workflow`, `Prompt`, `Training`, `LoRA` (Domain), `ModelManager`, `WorkflowManager`, `PromptManager`, `TrainingManager`, `LoRAManager`.
- Tout nouveau wiring EventBus.
- `LoRAPage.files_list` (déjà traité par Mission 050, non concerné par le tri par nom d'entité).
- Renommage d'une entité après création (`Model`/`Workflow`/`Prompt`/`Training`/`LoRA` n'ont aujourd'hui aucune méthode `update`/`rename` pour leur `name` — comportement uniforme constaté, non une incohérence, et hors périmètre de cette mission).
- Tout autre fichier au-delà des cinq Pages et de leurs tests.

## 7. Wiring de rafraîchissement — aucun ajout

```
WORKSPACE_SAVED / WORKSPACE_CREATED / WORKSPACE_OPENED / WORKSPACE_CLOSED / MODEL_*
  → ModelsPage.update_models()        (tri appliqué localement avant peuplement)

WORKSPACE_SAVED / WORKSPACE_CREATED / WORKSPACE_OPENED / WORKSPACE_CLOSED / WORKFLOW_*
  → WorkflowsPage.update_workflows()  (tri appliqué localement avant peuplement)

WORKSPACE_SAVED / ... / TRAINING_*
  → TrainingPage.update_trainings()   (tri appliqué localement avant peuplement)

WORKSPACE_SAVED / ... / PROMPT_*
  → PromptsPage.update_prompts() → _refresh_prompt_list()  (tri appliqué localement avant peuplement)

WORKSPACE_SAVED / ... / LORA_*
  → LoRAPage.update_loras()           (tri appliqué localement avant peuplement, lora_list uniquement)
```

Aucune souscription EventBus nouvelle, aucun changement de canal — chaque Page conserve exactement ses abonnements actuels (voir `main_window.py`).

## 8. Stratégie d'implémentation — réellement mise en œuvre

Pour chacune des cinq méthodes, l'itération directe de la liste retournée par le Manager a été remplacée par une itération sur `sorted(<liste>, key=lambda entry: entry["name"].lower())`, juste avant la boucle `for ... in ...: <list_widget>.addItem(...)` existante — aucun autre changement de logique (sélection de l'item actif, `blockSignals`, mise à jour des champs annexes tous inchangés).

`ModelsPage.update_models()` ([models_page.py:113](src/ui/pages/models_page.py:113)) :
```python
models = sorted(
    self.model_manager.list_models(),
    key=lambda model: model["name"].lower(),
)
```

Même traitement appliqué, avec le nom de variable local adapté, à `WorkflowsPage.update_workflows()` (`workflows`), `TrainingPage.update_trainings()` (`trainings`), `PromptsPage._refresh_prompt_list()` (`prompts`) et `LoRAPage.update_loras()` (`loras`, boucle `lora_list` uniquement — la boucle `files_list` de Mission 050 est restée inchangée). Aucun nouvel import n'a été nécessaire dans aucun des cinq fichiers (le tri porte directement sur le champ `name`, une chaîne déjà présente dans chaque dict).

Aucun changement à `ModelManager`/`WorkflowManager`/`PromptManager`/`TrainingManager`/`LoRAManager`, à aucun Domain, à aucun EventBus — confirmé par inspection du diff complet (`git diff --stat` : uniquement les 5 Pages + leurs 5 fichiers de test).

## 9. Stratégie de tests — réellement mise en œuvre

Pour chacun des cinq fichiers de test, une nouvelle classe a été ajoutée (mirroir de `ImagesPageGallerySortTest`/`DatasetsPageGallerySortTest`, adaptée à des entités nommées sans miniature) :
- `ModelsPageSortTest` (5 tests, `test_model_roundtrip.py`)
- `WorkflowsPageSortTest` (5 tests, `test_workflow_roundtrip.py`)
- `TrainingPageSortTest` (5 tests, `test_training_roundtrip.py`)
- `PromptsPageSortTest` (6 tests, `test_prompt_roundtrip.py` — un test supplémentaire dédié à la non-régression du dirty-state/`save_text()` face au tri, section PromptsPage du contrat)
- `LoRAPageSortTest` (5 tests, `test_lora_roundtrip.py` — un test dédié confirme que `LoRA.files`/Metadata/thumbnail restent intacts après une sélection sur liste triée)

Chaque classe vérifie : affichage alphabétique insensible à la casse sur des noms volontairement désordonnés et de casse mixte ; la liste Domain source (`character.loras`/`.prompts`/`.trainings`, `workspace.models`/`.workflows`) reste dans son ordre d'insertion d'origine après rafraîchissement ; stabilité du tri pour deux entités de même nom exact (ordre relatif d'insertion conservé, vérifié via `Qt.UserRole`) ; sélection/édition ciblant correctement la bonne entité malgré un déplacement d'affichage ; un second rafraîchissement (après une nouvelle création) retrie correctement l'ensemble.

**26/26 tests ciblés nets nouveaux, tous verts** (5+5+5+6+5). Aucun test Domain/Manager dupliqué. **885/885 tests automatisés verts** au total (859 précédents + 26 nets nouveaux) — suites `test_model_roundtrip.py`/`test_workflow_roundtrip.py`/`test_training_roundtrip.py`/`test_prompt_roundtrip.py`/`test_lora_roundtrip.py` intégralement vertes, confirmant l'absence de régression sur le reste de chaque fichier (changement purement Presentation).

## 10. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels). Script exclusivement dans le scratchpad de session, 5 scénarios courts (un par Page, plutôt qu'un unique scénario combinant les cinq types — jugé plus lisible, autorisé explicitement par le contrat).

Points observés réellement, tous conformes :
- **ModelsPage** : "Zebra Model"/"mango Model"/"Apple Model" créés dans cet ordre → affichage réel `["Apple Model", "mango Model", "Zebra Model"]` ; `Workspace.models` confirmé dans son ordre d'insertion d'origine par inspection directe ; sélection réelle d'"Apple Model" (position d'affichage 0, position d'insertion 2) confirmée cibler le bon `file_path`.
- **WorkflowsPage** : mêmes vérifications, tri et ordre Domain confirmés.
- **TrainingPage** : mêmes vérifications avec Character/Dataset réels ("Portraits") ; ordre Domain (`Character.trainings`) confirmé préservé.
- **PromptsPage** : tri confirmé ; sélection réelle d'"Apple Prompt" confirmée charger le bon texte dans `text_edit` malgré le déplacement d'affichage ; édition réelle du texte + clic réel sur "Enregistrer le texte" confirmés fonctionner normalement (dirty-state correctement mis à `True` puis `False`, texte persisté) — le tri n'a aucun effet sur ce mécanisme.
- **LoRAPage** : tri confirmé sur `lora_list` ; sélection réelle d'"Apple Style" (déplacée en position 0) confirmée afficher ses propres `files_list`/`engine_edit` réels, sans aucune confusion avec "Zebra Style" ; `Character.loras` confirmé dans son ordre d'insertion d'origine.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 11. Risques / non-régressions

- **Risque architectural** : nul — aucun changement Domain/EventBus, aucun Manager touché, changement strictement Presentation, mirroir exact d'un pattern déjà validé et livré par Mission 048, confirmé par inspection du diff complet.
- **Risque de régression sur la sélection active** (`setCurrentItem`) : écarté — la sélection continue de se faire par correspondance d'identité (`model_id`/`workflow_id`/`training_id`/`prompt_id`/`lora_id`) sur la liste triée, jamais par position, exactement comme le fait déjà `ImagesPage`/`DatasetsPage` depuis Mission 048 ; vérifié par test et par smoke test réel.
- **Risque de confusion avec `LoRAPage.files_list`** (Mission 050) : écarté par un périmètre explicitement limité à `lora_list` uniquement (section 6), vérifié par test dédié et smoke test réel (Metadata/thumbnail/`LoRA.files` tous intacts après sélection sur liste triée).
- **Risque de régression sur `PromptsPage`** (dirty-state, éditeur, Prompt Assistant, Send to Inference, Save as New Prompt) : écarté — `PromptsPagePromptAssistantTest`/`PromptsPageSendToInferenceTest`/`PromptsPageSaveAsNewPromptTest` existants restés verts sans modification ; test dédié + smoke test réel confirment le dirty-state/`save_text()` inchangé face au tri.
- **Risque de test contradictoire** : écarté par la vérification ciblée effectuée avant implémentation (section 1) — confirmé qu'aucun test n'accédait ces cinq `QListWidget` par position ; aucune reformulation de test existant n'a été nécessaire, à la différence de Mission 048.

## 12. Pourquoi maintenant plutôt que différée

Ce candidat est retenu plutôt que les autres pistes identifiées lors de l'audit (portabilité des chemins/`Workspace.root`, sélection de LoRA multi-engine, refonte Settings, internationalisation, Prompt Library/RAG, Character Context avancé) parce qu'il est le seul candidat sans aucune décision produit ou architecturale substantielle restant ouverte : le pattern, le critère de tri, le seuil UI-control et la stratégie de test sont tous déjà entièrement déterminés par le précédent direct de Mission 048/049, avec un périmètre mécanique et vérifiable. Les autres candidats nécessitent chacun un arbitrage réel (voir rapport d'audit associé) et restent donc différés.

## État d'avancement

- Audit de sélection (candidat Mission 051), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 26/26 ciblés (5+5+5+6+5), 885/885 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git (commit/tag/Release) : **entièrement effectuée**.

## Fichiers concernés

Production (5) : `src/ui/pages/models_page.py`, `src/ui/pages/workflows_page.py`, `src/ui/pages/training_page.py`, `src/ui/pages/prompts_page.py`, `src/ui/pages/lora_page.py`.
Tests (5, aucun nouveau fichier) : `tests/integration/test_model_roundtrip.py`, `tests/integration/test_workflow_roundtrip.py`, `tests/integration/test_training_roundtrip.py`, `tests/integration/test_prompt_roundtrip.py`, `tests/integration/test_lora_roundtrip.py`.
Documentation (1, nouveau) : `docs/missions/MISSION_051.md`.

## Commit correspondant

Commit fonctionnel unique : `0d6a2c54a79dc42701c1c250e8f63167857e948c` — `feat: sort Models, Workflows, Trainings, Prompts and LoRAs lists by name`. 11 fichiers modifiés (739 insertions, 5 suppressions) : les 5 fichiers de production, les 5 fichiers de test, `docs/missions/MISSION_051.md` (version pré-implémentation). Poussé vers `origin/main` (`55f25f0..0d6a2c5`), `HEAD == origin/main`, divergence `0 0`.

## Tag / release correspondant

Tag annoté `v0.2-mission051` (message `Mission 051 - Sort Remaining Entity Lists by Name`), ciblant exactement `0d6a2c54a79dc42701c1c250e8f63167857e948c` — vérifié localement (`git rev-list -n1 v0.2-mission051`) et à distance (`git ls-remote --tags origin v0.2-mission051 "v0.2-mission051^{}"`). GitHub Release `v0.2-mission051` **publiée** — confirmée par l'architecte du projet.

## État final

Mission entièrement close : implémentation conforme au contrat, 26/26 tests ciblés + 885/885 suite complète, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS, commit fonctionnel poussé, tag annoté créé et poussé, GitHub Release publiée. Documentation consolidée (`docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`) régularisée dans le commit documentaire qui suit immédiatement ce commit fonctionnel, sans déplacer le tag.
