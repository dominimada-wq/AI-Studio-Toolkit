# Mission 053 — Rename Prompt after Creation

> **STATUT : IMPLÉMENTATION TERMINÉE, EN ATTENTE DE COMMIT.** Contrat validé par l'architecte, implémentation réalisée conformément au contrat, 8/8 tests ciblés nets nouveaux (2 dans `PromptRoundTripTest` + 6 dans `PromptsPageRenameTest`), 921/921 tests automatisés verts, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS — y compris le scénario critique texte non sauvegardé → renommage → dirty-state et texte toujours intacts → `save_text()` fonctionnel ensuite.
> Aucun commit, tag ou Release n'existe encore pour cette mission — conformément au principe de non-auto-référence, ce document ne contient aucune valeur Git réelle avant la clôture effective (commit, puis tag/Release lors d'une étape ultérieure explicitement autorisée).

## 1. Contexte

Mission 052 a étendu à `Model`, `Workflow` et `LoRA` le renommage post-création déjà disponible pour `Character`, en excluant explicitement `Prompt` (structure de Page jugée potentiellement incompatible avec le dirty-state de Mission 038, nécessitant son propre audit). Le mini-audit ci-dessous confirme que cette incompatibilité redoutée **n'existe pas** : le mécanisme de renommage peut être ajouté à `PromptsPage` exactement selon le même contrat que Mission 052, sans toucher au dirty-state.

## 2. Mini-audit réalisé

**`PromptManager`** ([prompt_manager.py](src/managers/prompt_manager.py)) : `update_text(text: str) -> bool` ([prompt_manager.py:143](src/managers/prompt_manager.py:143)) édite `active_prompt.text` en place, idempotent (`False`/aucun `save()` si `text` identique ou si `active_prompt is None`), aucun événement dédié. `select()`/`_find()` confirmés opérer par `prompt_id`, jamais par position. `Prompt` ([domain/prompt.py](src/domain/prompt.py)) n'a que trois champs : `prompt_id`, `name`, `text` — aucune autre propriété à préserver.

**`PromptsPage`** ([prompts_page.py](src/ui/pages/prompts_page.py)) :
- `self._dirty`/`self._loaded_prompt_id` ([prompts_page.py:55-56](src/ui/pages/prompts_page.py:55)) sont exclusivement pilotés par `text_edit.textChanged` → `_on_text_changed()` ([prompts_page.py:267](src/ui/pages/prompts_page.py:267)), qui ne réagit qu'aux modifications de `text_edit`. Aucun autre widget ne touche `_dirty`.
- `_refresh_prompt_list(active_prompt_id)` ([prompts_page.py:360](src/ui/pages/prompts_page.py:360)) — partagée par `update_prompts()` et `reset_for_context_change()` (split EventBus de Mission 038) — reconstruit `prompt_list` (triée par nom depuis Mission 051) et sélectionne l'item actif par `prompt_id`, **sans jamais toucher `text_edit`**.
- `update_prompts()` ([prompts_page.py:385](src/ui/pages/prompts_page.py:385)) appelle d'abord `_refresh_prompt_list()` inconditionnellement, puis compare `active_prompt_id == self._loaded_prompt_id` : si identique (rafraîchissement non destructif, ex. après `update_text()`/`update_name()`), la méthode retourne **avant** de toucher `text_edit`/`_dirty`. C'est exactement ce mécanisme, déjà validé par le test `test_sorted_display_does_not_disturb_dirty_state_or_editor` de Mission 051, qui garantit qu'un renommage (lequel ne change jamais `active_prompt_id`) ne touchera jamais `text_edit`/`_dirty`.
- **Conclusion du mini-audit : aucune incompatibilité.** Un widget `name_edit` peuplé à l'intérieur de `_refresh_prompt_list()` (qui dispose déjà de `prompt["name"]` et de `active_prompt_id` dans sa boucle existante) est rafraîchi à chaque appel, y compris les rafraîchissements non destructifs — exactement le comportement voulu pour un champ qui reflète toujours l'état réel, sans dirty-state propre, mirroir exact de `LoRAPage.name_edit` (Mission 052) vis-à-vis du panneau Metadata.

**Test-order-contract** : `grep` de `prompt_list.item(` dans `tests/integration/test_prompt_roundtrip.py` — toutes les occurrences existantes sont dans `PromptRoundTripTest._item_for_prompt()` (recherche par identité, `Qt.UserRole`) et dans `PromptsPageSortTest` (assertions volontaires sur l'ordre d'affichage trié, pas sur l'ordre d'insertion). **Aucune reformulation de test existant nécessaire.**

**Politique de validation du nom** : confirmée identique au précédent de Mission 052 — `CharactersPage.save_identity()` passe `self.name_edit.text()` à `CharacterManager.update()` sans `.strip()` ni garde anti-vide ; `ModelManager.update_name()`/`WorkflowManager.update_name()`/`LoRAManager.update_name()` suivent ce même contrat. Aucune contradiction avec les flux de création de Prompt (`create_prompt()`/`save_as_new_prompt()`, qui strippent et rejettent le vide via `QInputDialog` — un flux différent). Mission 053 suit le seul précédent de renommage existant, sans en inventer un nouveau.

**EventBus/Domain/persistance** : aucun changement nécessaire. `update_name()` appellera `self._workspace_manager.save()`, qui publie `WORKSPACE_SAVED` — déjà souscrit par `PromptsPage.update_prompts` ([main_window.py](src/ui/main_window.py), confirmé par `_wire()` de tous les tests existants). `Prompt.to_dict()`/`from_dict()` inchangés, aucune migration `project.json`.

**Aucune décision produit ou architecturale substantielle ne reste ouverte** — le contrat, le mécanisme et la politique de validation sont tous entièrement déterminés par les précédents directs de Mission 052 (elle-même dérivée de `CharacterManager.update()`).

## 3. Objectif

Étendre à `Prompt` le renommage post-création déjà livré pour `Model`/`Workflow`/`LoRA` par Mission 052, en réutilisant exactement le même contrat idempotent et le même mécanisme d'édition immédiate.

## 4. Contrat fonctionnel validé

- `PromptManager.update_name(name: str) -> bool` — nouvelle méthode sibling additive de `update_text()`, mirroir exact : opère sur `self.active_prompt` (implicite, comme `update_text()` — pas d'id explicite, à la différence de `LoRAManager.update_name(lora_id, name)`). Idempotent : `False`/aucun `save()` si aucun prompt actif ou si `name` identique à la valeur stockée. Aucun événement dédié publié. Chaîne vide légitime, non validée, non strippée.
- `PromptsPage` gagne un `QLineEdit` **`name_edit`**, ajouté juste après `prompt_list` et avant `text_edit` dans la disposition (ordre de lecture naturel : liste → nom → texte). Renommage déclenché sur `editingFinished`, sans bouton ni dialogue dédié — `rename_prompt()` : si `self.prompt_manager.active_prompt_id is None: return`, sinon `self.prompt_manager.update_name(self.name_edit.text())`.
- `_refresh_prompt_list(active_prompt_id)` gagne le peuplement de `name_edit` : capture de `prompt["name"]` pour l'entité active pendant la boucle existante, `self.name_edit.setText(active_name)` (chaîne vide si aucune entité active) en fin de méthode — même endroit exact que le tri de Mission 051, aucun autre changement à `update_prompts()`/`reset_for_context_change()`.
- **`text_edit`/`_dirty`/`_loaded_prompt_id` ne sont touchés d'aucune façon** par ce changement — confirmé par le mini-audit ci-dessus.
- Après renommage, `WORKSPACE_SAVED` déclenche `update_prompts()` → `_refresh_prompt_list()` retrie la liste (Mission 051) et repositionne l'item — la sélection reste sur l'entité renommée par `prompt_id` (jamais par position), exactement comme Mission 051/052 l'ont déjà vérifié pour Model/Workflow/LoRA.

## 5. Périmètre

Production (2) :
- `src/managers/prompt_manager.py` (nouvelle méthode `update_name()`)
- `src/ui/pages/prompts_page.py` (import `QLineEdit`, `name_edit`, `rename_prompt()`, peuplement dans `_refresh_prompt_list()`)

Tests (1, aucun nouveau fichier) :
- `tests/integration/test_prompt_roundtrip.py`

## 6. Hors périmètre

- `Dataset` et `Training` : toujours aucune méthode `update()` d'aucune sorte — restent des candidats distincts pour une mission future, chacun nécessitant son propre audit (voir rapport d'audit de Mission 053).
- Toute contrainte d'unicité de nom, toute confirmation avant renommage.
- Toute modification de `Prompt` (Domain — le champ `name` existe déjà).
- Tout nouveau wiring EventBus.
- Le mécanisme de dirty-state de `text_edit` (Mission 038), le bouton « Enregistrer le texte », le Prompt Assistant, « Envoyer vers Inference », « Enregistrer comme nouveau Prompt… » — tous confirmés non affectés, non modifiés.
- Le besoin futur « Dataset de références → Inference » (documenté dans `docs/PROJECT_CONTEXT.md`, dépendant d'une primitive Inference 0..N références avec rôles qui n'existe pas encore) — non implémenté, aucun scaffolding créé.

## 7. Wiring de rafraîchissement — aucun ajout

```
WORKSPACE_SAVED / WORKSPACE_RENAMED / CHARACTER_CREATED / PROMPT_*
  → PromptsPage.update_prompts() → _refresh_prompt_list()  (name_edit peuplé, tri Mission 051 déjà appliqué)

WORKSPACE_CREATED / WORKSPACE_OPENED / WORKSPACE_CLOSED / CHARACTER_SELECTED / CHARACTER_DELETED
  → PromptsPage.reset_for_context_change() → _refresh_prompt_list(None)  (name_edit vidé)
```

Aucune souscription EventBus nouvelle, aucun changement de canal.

## 8. Stratégie de tests — réellement mise en œuvre

`PromptRoundTripTest` gagne `test_update_name_is_idempotent` (mirroir exact de `test_update_text_is_idempotent`) et `test_rename_persists_after_close_reopen` : idempotence (`save()` non appelé si valeur identique, vérifié par `patch.object`), renommage réel (`save()` appelé une fois, aucun `prompt.*` publié), aucun prompt actif → `False`, `prompt_id`/`text` préservés, chaîne vide légitime, persistance après fermeture/réouverture (avec `workspace_manager.close()` puis re-sélection du Character restauré par nom, mirroir exact de `test_full_create_select_edit_save_close_reopen_cycle`).

Nouvelle classe `PromptsPageRenameTest` (6 tests, `_wire()` répliquant le split EventBus exact de `PromptRoundTripTest._wire()`) :
- `test_rename_via_widget_updates_manager_display_and_preserves_text` — renommage via le vrai widget, `prompt_id`/`text` inchangés.
- `test_rename_moving_entity_to_front_keeps_correct_selection` / `test_rename_moving_entity_to_back_keeps_correct_selection` — déplacement dans les deux sens, sélection conservée par `prompt_id`.
- `test_rename_with_no_active_prompt_is_a_no_op`.
- `test_rename_with_unsaved_text_preserves_dirty_state_and_draft` — **le scénario critique explicitement demandé** : texte modifié non sauvegardé (`_dirty = True`) → renommage → retri de la liste → `_dirty` toujours `True` → `text_edit` toujours le brouillon non sauvegardé → texte persisté toujours l'ancienne valeur sauvegardée (le renommage n'a jamais touché `text`) → `save_text()` fonctionne ensuite normalement (`_dirty` redevient `False`, le brouillon est bien persisté).
- `test_rename_persists_after_close_reopen_via_ui`.

**Vérification préalable confirmée** : aucun accès positionnel `prompt_list.item(` ne contractualisait l'ordre d'insertion (déjà confirmé par l'audit de Mission 051/section 2 de ce document) — aucune reformulation de test existant n'a été nécessaire.

**8/8 tests ciblés nets nouveaux, tous verts** (2+6). **921/921 tests automatisés verts** au total (913 précédents + 8 nets nouveaux) — `test_prompt_roundtrip.py` intégralement vert (73/73), confirmant l'absence de régression sur `PromptsPagePromptAssistantTest`/`PromptsPageSendToInferenceTest`/`PromptsPageSaveAsNewPromptTest`/`PromptsPageSortTest`.

## 9. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels), script exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Sélection de "Apple Prompt" (texte sauvegardé "apple saved text") → `name_edit`/`text_edit` correctement peuplés, `_dirty` à `False`.
- Édition réelle de `text_edit` (texte non sauvegardé) → `_dirty` passe à `True`.
- Renommage réel vers "Zzz Prompt" (déplacement vers la fin de liste) → liste retriée `["Zebra Prompt", "Zzz Prompt"]`, sélection conservée sur le même `prompt_id`, `name` mis à jour, **`text` toujours "apple saved text"** (jamais touché par le renommage).
- **`_dirty` toujours `True` après le renommage, `text_edit` toujours "apple text edited but NOT saved yet"** — le brouillon non sauvegardé survit intact au renommage.
- `save_text()` appelé ensuite : `_dirty` redevient `False`, le texte édité est bien persisté.
- Fermeture/réouverture réelle du Workspace : nom, texte et `prompt_id` tous confirmés persistés à l'identique.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 10. Risques / non-régressions

- **Risque d'interférence avec le dirty-state (Mission 038)** : écarté — confirmé par test dédié et smoke test réel, `_dirty`/`_loaded_prompt_id` restent pilotés exclusivement par `text_edit.textChanged`.
- **Risque d'interaction avec le tri Mission 051** : écarté — sélection par `prompt_id` vérifiée dans les deux sens de déplacement, par test et smoke test réel.
- **Risque de sur-portée** : écarté — `Dataset`/`Training` non touchés, confirmé par `git diff --stat` (2 fichiers de production + 1 fichier de test).

## 11. Pourquoi maintenant plutôt que différée

Ce candidat referme la seule exclusion de Mission 052 dont le mini-audit confirme l'absence de toute décision substantielle restante — contrairement à `Dataset`/`Training`, qui nécessiteraient chacun l'introduction de leur toute première méthode `update()` (un précédent structurel plus significatif) et n'ont pas encore été audités individuellement. Le besoin « Dataset de références → Inference », également identifié lors de l'audit de Mission 052, reste délibérément différé : il dépend d'une primitive Inference 0..N références avec rôles qui n'existe pas encore (`GenerationManager` rejette explicitement plus d'une référence) — un chantier architectural distinct, non entamé par cette mission.

## État d'avancement

- Audit de sélection (candidat Mission 053), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 8/8 ciblés (2+6), 921/921 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**, y compris le scénario critique dirty-state/renommage explicitement demandé.
- Clôture Git (commit/tag/Release) : **non encore effectuée** — en attente d'autorisation explicite de commit.
