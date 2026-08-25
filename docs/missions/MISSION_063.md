# Mission 063 — Synchronize Delete Action with Selection

> **STATUT : MISSION ENTIÈREMENT CLOSE.** 39 tests ciblés nets nouveaux (cycle de vie du bouton « Supprimer » sur 6 pages), suite complète verte (voir section 9 pour le détail — un aléa d'environnement natif, non lié à ce diff, est documenté séparément et conservé comme observation pour l'audit suivant), smoke test Qt réel exécuté et **PASS** sur les 6 pages concernées (section 10). Commit fonctionnel `538c943b7eb9f35e84634fce6e13785fcfbda365`, tag annoté `v0.2-mission063`, GitHub Release publiée. Voir section 11 pour l'état de clôture Git et de publication.

## 1. Contexte

L'audit consécutif à Mission 062 (deux catégories ciblées — accessibilité/clavier et cohérence des états après changement de contexte) a établi que le bouton « Supprimer » de 6 des 7 pages CRUD du projet (`Dataset`, `LoRA`, `Model`, `Training`, `Workflow`, `Prompts`) reste **toujours activé**, indépendamment de toute sélection réelle dans la liste — contrairement à `ImagesPage.delete_button`, seule page correcte (`setEnabled(False)` à la construction, recalculé par `_update_enlarge_button_state()` sur `itemSelectionChanged` et après chaque reconstruction de liste, Mission 046). Chaque `delete_<entité>()` garde bien `if item is None: return`, donc aucun crash n'était possible — mais un clic sur « Supprimer » sans sélection produisait un **no-op silencieux, sans aucun retour visuel**, sur une liste vide ou juste après un changement de Workspace/Character.

`Character` est hors périmètre (voir Mission 062 section 1) : `CharactersPage.delete_button` reste volontairement caché depuis Mission 026, inaccessible depuis l'application réelle — ni ses contrôles CRUD masqués ni `CharacterManager` ne sont modifiés par cette mission.

## 2. Objectif

Faire en sorte que `delete_button` reflète réellement la possibilité d'agir, sur les 6 pages concernées :
- aucune sélection valide → désactivé ;
- élément sélectionné → activé ;

en couvrant tout le cycle de vie pertinent de chaque liste (construction initiale, sélection, désélection, reconstruction/rafraîchissement, fermeture de Workspace, suppression de l'élément sélectionné) — pas seulement le signal de changement de sélection.

## 3. Contrat fonctionnel implémenté

**Audit préalable du cycle de vie réel de chaque page** (avant toute modification) : les 5 pages `Dataset`/`LoRA`/`Model`/`Training`/`Workflow` partagent un motif strictement identique — un handler `on_<entité>_selection_changed(current, previous)` connecté à `currentItemChanged`, et une méthode `update_<entité>s()` qui reconstruit la liste avec `blockSignals(True)` (donc `currentItemChanged` ne se déclenche jamais pendant une reconstruction). `PromptsPage` diffère : sa sélection peut être **annulée et revenir en arrière** par la garde de brouillon non enregistré de Mission 038 (`on_prompt_selection_changed` → `_confirm_discard_before_switch()` → `Annuler` → `setCurrentItem(previous)`), et ses deux chemins de rafraîchissement (`update_prompts()`/`reset_for_context_change()`) partagent un unique point commun, `_refresh_prompt_list()`.

**Pour les 5 pages au motif identique** (`datasets_page.py`, `lora_page.py`, `models_page.py`, `training_page.py`, `workflows_page.py`) :
- `delete_button.setEnabled(False)` ajouté à la construction, juste après la création du bouton ;
- `on_<entité>_selection_changed()` : `self.delete_button.setEnabled(current is not None)` ajouté en tout premier, avant le `if current is None: return` existant (qui, lui, continue de ne piloter que l'appel au Manager) ;
- `update_<entité>s()` : `self.delete_button.setEnabled(self.<entité>_list.currentItem() is not None)` ajouté juste après `blockSignals(False)`, pour couvrir toute reconstruction (y compris celles déclenchées par `*_DELETED`, une fermeture de Workspace, ou tout autre événement métier).

**Pour `PromptsPage`** (motif adapté, pas copié) :
- `delete_button.setEnabled(False)` à la construction ;
- `on_prompt_selection_changed()` : `current is None` → désactivé, retour immédiat ; la branche `Cancel` de la garde dirty-state → l'état suit `previous` (la sélection réellement en vigueur après l'annulation, pas la tentative de bascule annulée) ; la branche qui aboutit à `self.prompt_manager.select(target_prompt_id)` → activé ;
- `_refresh_prompt_list()` (partagée par `update_prompts()`/`reset_for_context_change()`) : `self.delete_button.setEnabled(self.prompt_list.currentItem() is not None)` ajouté juste après `blockSignals(False)`.

**Dataset — clarification explicite** : la garde préexistante `is_referenced_by_training()` (Mission 062) n'est **pas** répercutée sur l'état du bouton — un Dataset sélectionné, même référencé par un Training, active « Supprimer » selon la règle générale ; la garde continue d'intervenir uniquement au clic, dans `delete_dataset()`, inchangée. Vérifié par un test dédié (section 8).

**Aucune abstraction partagée introduite** — 6 adaptations locales indépendantes, chacune dans son fichier, suivant le motif déjà établi par `ImagesPage`.

**Fichiers modifiés** (Presentation uniquement) :
- `src/ui/pages/datasets_page.py`, `lora_page.py`, `models_page.py`, `training_page.py`, `workflows_page.py`, `prompts_page.py`.

**Domain/Manager/Infrastructure/EventBus** : aucun changement.

## 4. Hors périmètre (explicitement différé)

- `Character` — voir section 1 ; `CharactersPage.delete_button`/`CharacterManager` non modifiés.
- Le mécanisme de confirmation introduit par Mission 062 (`QMessageBox`, Cancel par défaut) — strictement intact, aucune modification de wording ni de comportement ; vérifié par le smoke test réel (section 10) qui exécute un cycle de confirmation complet après avoir activé le bouton.
- Toute désactivation dynamique de « Supprimer » selon `is_referenced_by_training()` — évolution UX distincte, non traitée ici (voir section 3).
- A-2 (cache des vignettes) et B2 (fermeture de `PromptAssistantDialog` pendant une génération) — candidats identifiés lors d'audits précédents, explicitement conservés pour réévaluation future, non traités ici.

## 5. Risques

- **Risque de régression fonctionnelle** : très faible — motif déjà validé par `ImagesPage` (Mission 046), 6 adaptations mécaniques, aucun changement de signature Manager, aucune règle métier touchée.
- **Risque d'interaction avec Mission 038 (PromptsPage)** : neutralisé par l'audit préalable du cycle de sélection réel de cette page avant toute modification — deux tests dédiés couvrent explicitement la bascule annulée (avec et sans sélection préalable), tous deux verts en conditions réelles (section 8/10).
- **Risque d'interaction avec Mission 062** : neutralisé — la confirmation existante n'est appelée qu'après un clic sur un bouton désormais correctement activé/désactivé ; le smoke test réel exécute le cycle de confirmation complet sur les 6 pages pour le prouver.

## 6. Pourquoi maintenant

Candidat identifié et comparé à deux alternatives (A-2, B2) lors de l'audit post-Mission 062 : meilleur rapport impact/périmètre/risque — motif déjà établi dans le dépôt, zéro décision architecturale ouverte, contrairement à A-2 (borne de cache à trancher) et B2 (cycle de vie thread/dialogue plus délicat).

## 7. Autres candidats évalués et écartés pour cette mission

- **A-2 — cache des vignettes / redécodages complets inutiles** : dette réelle, toujours présente, nécessite un micro-choix d'implémentation (borne/éviction du cache) — conservée comme candidat futur, non implémentée ici.
- **B2 — fermeture de `PromptAssistantDialog` pendant une génération** : Échap/fermeture contournent le bouton Annuler désactivé pendant qu'un `QThread` tourne encore — conservée comme candidat futur pour un audit dédié du cycle de vie dialogue/thread, non traitée ici sur instruction explicite de l'architecte.

## 8. Tests automatisés ajoutés

**39 tests nets nouveaux**, une nouvelle classe `*PageDeleteButtonStateTest` par page :

- `LoRAPageDeleteButtonStateTest` (6 tests), `ModelsPageDeleteButtonStateTest` (6), `WorkflowsPageDeleteButtonStateTest` (6), `TrainingPageDeleteButtonStateTest` (6) : désactivé avant tout Workspace ; désactivé sans sélection puis activé après sélection réelle ; désactivé après désélection réelle (`setCurrentItem(None)`) ; état cohérent après reconstruction de liste (création d'un second élément pendant que le premier reste sélectionné) ; désactivé après fermeture du Workspace ; désactivé après suppression de l'élément sélectionné (déclenchée directement via le Manager, indépendamment du flux de confirmation Mission 062).
- `DatasetsPageDeleteButtonStateTest` (7 tests) : les 6 ci-dessus, plus `test_selecting_a_dataset_referenced_by_training_still_enables_button` — preuve explicite que la garde Training n'intervient pas sur l'état du bouton (section 3).
- `PromptsPageDeleteButtonStateTest` (8 tests) : les 6 scénarios de base (adaptés au cycle propre à `PromptsPage` — `_refresh_prompt_list()`, `reset_for_context_change()`), plus deux tests spécifiques : `test_switch_cancelled_while_dirty_keeps_button_enabled_on_reverted_selection` (bascule annulée avec une sélection préalable — le bouton suit la sélection réellement restaurée) et `test_switch_cancelled_while_dirty_with_no_prior_selection_disables_button` (brouillon non enregistré sans aucune sélection préalable, bascule annulée — le bouton reste désactivé, `select()` jamais appelé).

Les tests M062 de confirmation Cancel/Confirm (`*PageDeleteConfirmationTest`) sont strictement inchangés. Aucun test préexistant modifié ou supprimé.

## 9. Vérifications finales — réellement exécutées

**Tests ciblés** — **39/39 PASS** (les 6 nouvelles classes de test, exécutées ensemble et individuellement).

**Suite complète** : un run propre confirmé à **1080/1080 tests automatisés verts** (1041 précédents + 39 nets nouveaux). **Aléa d'environnement constaté et documenté honnêtement** : sur plusieurs exécutions consécutives de la suite complète (~1080 tests réels, PySide6/Qt, environnement Windows), un crash natif (segmentation fault) est apparu de façon intermittente, à des emplacements différents et non reproductibles d'une exécution à l'autre — jamais une erreur d'assertion Python, toujours un arrêt brutal du process. Isolé et diagnostiqué avant de poursuivre : `git stash` a permis de confirmer que cet aléa existe **indépendamment de ce diff** (la suite de base à 1041 tests, sans les modifications de Mission 063, présente elle aussi une instabilité similaire sur des runs répétés dans cet environnement) ; tous les runs ciblés sur les modules concernés par cette mission (`test_lora_roundtrip`, `test_dataset_roundtrip`, `test_model_roundtrip`, `test_training_roundtrip`, `test_workflow_roundtrip`, `test_prompt_roundtrip`, seuls ou groupés) sont **systématiquement verts sans exception**. Conclusion : aléa d'environnement (probablement lié au nettoyage natif Qt/PySide6 sur un très grand nombre de widgets réels créés dans un seul process, sensibilisé par le volume total plutôt que par un test spécifique), non introduit par ce diff, sans lien avec la logique Presentation modifiée — signalé pour information, ne bloque pas cette mission.

`git diff --check` : propre, aucun avertissement.

**Périmètre du diff** : exactement 12 fichiers — `src/ui/pages/{datasets,lora,models,training,workflows,prompts}_page.py` (production, Presentation uniquement) et `tests/integration/test_{dataset,lora,model,training,workflow,prompt}_roundtrip.py` (tests), plus ce document. Aucun fichier Domain/Manager/Infrastructure/EventBus touché. Aucun résidu scratch dans le dépôt.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

Construction réelle des 6 Pages contre un Workspace réel (dossiers temporaires), sélection/désélection réelle via `QListWidget.setCurrentItem()` (signal `currentItemChanged` réellement émis, jamais simulé), lecture directe de `delete_button.isEnabled()` sur le widget réel.

Pour chacune des 6 pages (Dataset, LoRA, Model, Training, Workflow, Prompts) :
- **désactivé** avant tout Workspace, et juste après ouverture d'un Workspace sans sélection ;
- **activé** après une sélection réelle ;
- **désactivé** après une désélection réelle ;
- **cohérent après reconstruction** de la liste (Dataset : second élément créé pendant que le premier reste sélectionné) et, pour LoRA, après une fermeture puis réouverture du Workspace ;
- **cycle de confirmation Mission 062 intact** : sur Dataset/LoRA/Model/Training/Workflow, après activation du bouton par une sélection réelle, le clic déclenche le vrai `QMessageBox` de confirmation (motif Mission 062 inchangé — seul `.exec()` est patché pour cliquer le vrai bouton, comme le smoke test Mission 062), la suppression s'exécute réellement, et le bouton redevient correctement désactivé ensuite ; sur Prompts (pas de confirmation M062, mécanisme Mission 038 propre), la suppression réelle (brouillon non dirty) désactive correctement le bouton après coup.

**Verdict : PASS sur les 6 pages**, toutes assertions vérifiées (voir sortie complète de `m063_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## 11. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `538c943b7eb9f35e84634fce6e13785fcfbda365` (« feat: disable Supprimer when no CRUD entity is selected »), 13 fichiers (6 production + 6 tests + ce document), 843 insertions / 1 suppression.
- **Push** : `8fe5031..538c943 main -> main`, `HEAD == origin/main` vérifié, divergence `0 0`.
- **Tag annoté** : `v0.2-mission063`, créé sur `538c943b7eb9f35e84634fce6e13785fcfbda365`, poussé, vérifié en local (`git rev-list -n1` → même commit) et à distance (`git ls-remote --tags` → objet tag `a5355174ba41b36252dbfa18ce11329c8feb83b8` peelé sur le même commit).
- **GitHub Release** : `v0.2-mission063` — *Mission 063 - Synchronize Delete Action with Selection* — **publiée manuellement par l'architecte**.
- **Aléa segfault Qt/PySide6** : observation conservée telle quelle (non attribuée à ce diff, non résolue) — **candidat à réévaluer lors de l'audit Mission 064** pour déterminer si une investigation autonome est justifiée (voir audit post-M063).

## État d'avancement

- Audit du dépôt (candidats Mission 063, robustesse/UX + performance + accessibilité) : **réalisé**, choix validé par l'architecte.
- Audit préalable du cycle de vie réel des 6 pages avant implémentation : **réalisé** (section 3).
- Implémentation : **réalisée, conforme au contrat**.
- Tests automatisés : **exécutés, verts — 39/39 ciblés, 1080/1080 suite complète (run propre confirmé)**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (12 fichiers exactement)**.
- Smoke test Qt réel : **réalisé, PASS sur les 6 pages** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (section 11).
