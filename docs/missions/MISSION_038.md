# Mission 038 — Protect unsaved prompt drafts in PromptsPage

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 696/696 tests automatisés verts, smoke test manuel réel PASS, clôture Git effectuée, GitHub Release `v0.2-mission038` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Dette documentée dans `docs/PROJECT_CONTEXT.md` depuis l'audit pré-implémentation de Mission 032 : `PromptsPage.update_prompts()` réécrivait inconditionnellement `text_edit` à chaque événement EventBus pertinent (`WORKSPACE_CREATED`/`OPENED`/`SAVED`/`CLOSED`/`RENAMED`, `CHARACTER_CREATED`/`SELECTED`/`DELETED`, `PROMPT_CREATED`/`SELECTED`/`DELETED`) — y compris des événements déclenchés ailleurs dans l'application sans rapport avec le Prompt réellement édité (ex. `WORKSPACE_SAVED` publié par « Enregistrer dans Prompts » depuis `InferencePage`). Un texte modifié mais non sauvegardé via « Enregistrer le texte » pouvait donc être perdu silencieusement.

## 2. Objectif

Empêcher la perte silencieuse d'un brouillon modifié dans `PromptsPage`, en distinguant les causes de rafraîchissement plutôt qu'en ajoutant une confirmation générique devant tout appel à `update_prompts()`.

## 3. Audit UX préalable — constats vérifiés par lecture directe du code

- 11 événements distincts déclenchaient `update_prompts()` : 5 Workspace, 3 Character, 3 Prompt.
- `PromptManager._on_context_changed()` réinitialise `active_prompt_id = None` sur `CHARACTER_SELECTED`/`DELETED`, `WORKSPACE_CREATED`/`OPENED`/`CLOSED` — jamais sur `WORKSPACE_SAVED`/`WORKSPACE_RENAMED`/`CHARACTER_CREATED`.
- `PromptManager.select()`/`create()`/`delete()` mutent `active_prompt_id` de façon synchrone **avant** de publier leur événement — aucun mécanisme de veto possible depuis un abonné EventBus.
- Trois catégories d'événements identifiées : **A** — refresh non destructeur (`active_prompt_id` inchangé : `WORKSPACE_SAVED`/`RENAMED`, `CHARACTER_CREATED`, `PROMPT_CREATED` sans sélection) ; **B** — changement de contexte, dont seule la sélection volontaire d'un autre Prompt (via `on_prompt_selection_changed`) est réellement interceptable **avant** l'action, les événements Workspace/Character ne l'étant pas (le Manager a déjà transitionné lorsque `PromptsPage` en est informée) ; **C** — suppression du Prompt actuellement édité, rendant le brouillon sans cible.
- Quatre options comparées (dirty-state + confirmation ; sauvegarde explicite renforcée ; autosave ; protection ciblée) — la solution hybride **dirty-state local + refresh intelligent** retenue, seule à traiter indépendamment chaque catégorie identifiée.

## 4. Décision — dirty-state local + refresh intelligent

Deux nouveaux attributs d'instance `PromptsPage` : `self._dirty` et `self._loaded_prompt_id` (le `active_prompt_id` correspondant au contenu actuellement chargé dans `text_edit`, distinct de `PromptManager.active_prompt_id`). Aucun changement Domain, `PromptManager`, format Workspace, persistance ou contrat Manager.

## 5. Changement de Prompt

`on_prompt_selection_changed()` intercepte avant `prompt_manager.select()` si `self._dirty` : **Enregistrer** (sauvegarde puis poursuit), **Ignorer les modifications** (abandonne puis poursuit), **Annuler** (aucun `select()`, sélection visuelle restaurée via `previous`, signaux de `prompt_list` bloqués pour éviter toute récursion, texte et dirty conservés, `active_prompt_id` du Manager inchangé).

## 6. Suppression d'un Prompt dirty

`delete_prompt()` intercepte avant `prompt_manager.delete()` si `self._dirty` : confirmation à 2 choix (Supprimer/Ignorer les modifications vs Annuler). Aucune notion de brouillon orphelin — après suppression effective, le mécanisme générique de refresh (section 8) nettoie l'éditeur.

## 7. Séparation EventBus finale — architecture retenue après réexamen explicite

Une première conception envisageait une double souscription (`update_prompts()` sur les 11 événements + `reset_for_context_change()` en filet de sécurité enregistré après elle pour 5 d'entre eux). Réexamen demandé par l'architecte : cette approche fonctionnait mais faisait reposer la correction sur l'ordre d'enregistrement des abonnés EventBus. **Séparation stricte retenue** — un événement, un seul chemin Presentation :

- **`update_prompts()`** : `WORKSPACE_SAVED`, `WORKSPACE_RENAMED`, `CHARACTER_CREATED`, `PROMPT_CREATED`, `PROMPT_SELECTED`, `PROMPT_DELETED`.
- **`reset_for_context_change()`** : `WORKSPACE_CREATED`, `WORKSPACE_OPENED`, `WORKSPACE_CLOSED`, `CHARACTER_SELECTED`, `CHARACTER_DELETED` — exactement les 5 événements que `PromptManager._on_context_changed()` traite lui-même comme un changement de contexte réel. Ces événements sont déjà survenus lorsque `PromptsPage` en est informée : elle accepte le nouveau contexte et réinitialise son état local, sans tentative de veto tardif.

Aucune double souscription pour ces 5 événements ; aucune dépendance à l'ordre des abonnés. La reconstruction de la liste (`_refresh_prompt_list()`) est factorisée et partagée par les deux méthodes, évitant toute duplication de logique.

## 8. Refresh intelligent — `update_prompts()`

Compare `prompt_manager.active_prompt_id` à `self._loaded_prompt_id` : identiques → liste reconstruite, `text_edit`/`dirty` inchangés (Catégorie A) ; différents → `text_edit` rechargé (signaux bloqués pendant le `setPlainText()`), `dirty=False`, `self._loaded_prompt_id` synchronisé, boutons recalculés.

## 9. Assistant IA, sauvegarde, Save as New Prompt, Create Prompt

- Résultat de l'Assistant IA (« Utiliser ce texte ») : `setPlainText()` **non protégé**, `_on_text_changed()` marque `dirty=True` normalement.
- `save_text()` : `dirty=False` inconditionnellement après l'appel, y compris le cas idempotent (`update_text()` retournant `False`).
- `save_as_new_prompt()` (Mission 035) : séquence `create()`→`select()` inchangée ; aucune confirmation parasite (la confirmation ne vit que dans `on_prompt_selection_changed()`) ; `dirty=False` obtenu automatiquement via le rechargement générique déclenché par `PROMPT_SELECTED`.
- `create_prompt()` : inchangé, aucune sélection automatique ; le brouillon dirty existant survit automatiquement puisque `active_prompt_id` ne change pas.

## 10. Correction de robustesse Qt découverte pendant les tests

Le choix « Enregistrer » lors d'un changement de Prompt dirty appelle `update_text()`, qui publie `WORKSPACE_SAVED` de façon synchrone — ce refresh reconstruit `prompt_list` (`clear()`), détruisant l'objet Qt `current` sous-jacent avant que `on_prompt_selection_changed()` n'ait fini de l'utiliser. Corrigé en capturant `current.data(Qt.UserRole)` en tout début de méthode, avant tout appel Manager pouvant déclencher ce rafraîchissement réentrant. Correction de robustesse interne, pas une fonctionnalité distincte.

## 11. Fichiers concernés

Production (2) : `src/ui/pages/prompts_page.py`, `src/ui/main_window.py`.
Tests (1) : `tests/integration/test_prompt_roundtrip.py`.

Aucun autre fichier — `PromptManager`, `src/domain/`, `src/core/event_bus.py` strictement inchangés.

## 12. Tests ajoutés/modifiés (16 nets nouveaux)

- `PromptRoundTripTest` (+14) : refresh non destructeur (`WORKSPACE_SAVED`/`RENAMED`/`PROMPT_CREATED` sans sélection) ; changement de Prompt dirty (Enregistrer/Ignorer/Annuler avec restauration de sélection) ; changement sans dirty (régression) ; suppression dirty (Annuler/Confirmer) et non dirty (régression) ; `create_prompt()` préservant le brouillon ; `reset_for_context_change()` sur fermeture de Workspace et sur le cas limite `_loaded_prompt_id`/`active_prompt_id` tous deux `None` ; `reset_for_context_change()` sur `CHARACTER_SELECTED`/`DELETED` ; vérification programmatique du routage EventBus déterministe ; 2 tests existants corrigés pour refléter le nouveau comportement Catégorie A (`WORKSPACE_SAVED` ne doit plus recharger l'éditeur).
- `PromptsPagePromptAssistantTest` (+3) : résultat Assistant IA marque dirty ; `save_text()` remet dirty à `False` (cas normal et idempotent).

## 13. Résultats de tests (automatisés)

- Suite ciblée (`test_prompt_roundtrip.py`) : **59/59 OK**.
- Tests dépendants (`test_main_window_prompts_to_inference.py` + `test_inference_page.py`) : **86/86 OK**.
- Suite complète : **696/696 OK** (680 précédents + 16 nets nouveaux).

## 14. Smoke test manuel réel — résultat

**Résultat global : PASS.** Confirmé par l'architecte du projet — aucune anomalie relevée.

## Commit correspondant

`f705377111cefe31c7a8be3bb0581c93cbedbef9` — `feat: protect unsaved prompt drafts in PromptsPage`. Inclut l'implémentation fonctionnelle (code + tests) de Mission 038.

## Tag / release correspondant

`v0.2-mission038` (annoté, message `Mission 038 - Protect unsaved prompt drafts in PromptsPage`), ciblant exactement `f705377111cefe31c7a8be3bb0581c93cbedbef9`. GitHub Release `v0.2-mission038` **publiée**.

## État d'avancement

- Mini-audit UX et spécification : **validés**, y compris un réexamen architectural explicite (séparation EventBus stricte retenue, voir section 7).
- Implémentation : **réalisée**, conforme à la spécification validée, avec une correction de robustesse Qt identifiée pendant les tests (section 10).
- Tests automatisés ciblés (59/59), dépendants (86/86) et suite complète (696/696) : **exécutés, verts**.
- Smoke test manuel réel : **PASS**.
- Clôture Git : **effectuée** — commit fonctionnel `f705377111cefe31c7a8be3bb0581c93cbedbef9`, tag `v0.2-mission038`.
- GitHub Release : **publiée**.

## État final

Mission 038 — Protect unsaved prompt drafts in PromptsPage — est **entièrement close** : implémentation, 696/696 tests automatisés, smoke test manuel réel PASS, clôture Git et publication GitHub Release toutes effectuées. La dette documentée depuis Mission 032 (`PromptsPage` — perte silencieuse d'un texte non sauvegardé) est résolue. La limitation architecturale concernant les changements Workspace/Character non annulables depuis `PromptsPage` est documentée comme volontaire, non transformée en nouvelle dette active.
