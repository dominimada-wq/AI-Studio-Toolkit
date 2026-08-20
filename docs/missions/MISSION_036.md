# Mission 036 — Distinguish no open project from no principal character in warnings

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 678/678 tests automatisés verts, smoke test manuel réel PASS, clôture Git effectuée, GitHub Release `v0.2-mission036` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Le smoke test manuel réel de Mission 035 a révélé une dette UX transversale, enregistrée dans `docs/PROJECT_CONTEXT.md` : plusieurs Pages affichaient un message « Aucun personnage » aussi bien lorsqu'aucun projet/Workspace n'était ouvert que lorsqu'un Workspace existait sans personnage principal — deux causes distinctes confondues en un seul signal `None`, sans que l'utilisateur ne puisse les distinguer. Comportement préexistant depuis au moins Mission 026/029, non introduit ni aggravé par Mission 035.

## 2. Objectif

Distinguer correctement, aux emplacements concernés, « aucun projet/Workspace ouvert » (message « Aucun projet ouvert » demandant d'ouvrir ou créer un projet) de « Workspace ouvert mais aucun personnage principal disponible » (message « Aucun personnage » existant, conservé à l'identique) — sans modifier aucune règle métier.

## 3. Audit ciblé — constats vérifiés par lecture directe du code

- `CharacterManager.principal_character` ([character_manager.py:98-122](src/managers/character_manager.py:98)) retourne `None` aussi bien quand `current_workspace is None` que lorsqu'un Workspace existe avec `characters` vide — les quatre Managers Character-owned (`DatasetManager`, `LoRAManager`, `PromptManager`, `TrainingManager`) en héritent la même ambiguïté dans leur `create()`.
- `CharactersPage.create_character()` ([characters_page.py:143-157](src/ui/pages/characters_page.py:143)) était déjà correct : `CharacterManager.create()` ne retourne `None` que si `current_workspace is None`, donc son message « Aucun projet ouvert » était déjà exact — seul emplacement non concerné par la correction.
- **Découverte clé de l'audit** : les cinq Managers Character-owned (`CharacterManager`, `DatasetManager`, `LoRAManager`, `PromptManager`, `TrainingManager`) reçoivent **déjà** `workspace_manager` en dépendance constructeur privée (`self._workspace_manager`), conformément au pattern Character-owned de `CLAUDE.md` — mais ne l'exposent pas publiquement. `InferencePage` détient déjà `workspace_manager` directement et utilise déjà `self._workspace_manager.opened` pour un besoin analogue ([inference_page.py:219](src/ui/pages/inference_page.py:219)) — précédent architectural déjà en production.
- Nuance découverte sur `TrainingPage.create_training()` : le bloc « Aucun personnage » n'est en pratique quasiment jamais atteint, car `dataset_manager.list_datasets()` (même cause racine ambiguë) est interrogé et refuse d'abord avec « Aucun dataset disponible » si la liste est vide — ambiguïté distincte, confirmée hors périmètre.

## 4. Décision d'architecture — Option A (injection directe), après réexamen explicite

Deux options ont été comparées :
- **Option A — Injection directe de `WorkspaceManager`** dans les Pages qui en ont réellement besoin.
- **Option C — Propriété `workspace_opened` déléguée** sur chacun des cinq Managers métier concernés, chacun réexposant sa référence `_workspace_manager` déjà détenue.

**Option A retenue** après comparaison stricte sur la responsabilité architecturale (l'état du Workspace appartient à `WorkspaceManager`, pas aux Managers Character-owned), la source d'autorité (un seul point d'accès public plutôt que cinq façades identiques), la nature de la dépendance (explicite et déclarée au constructeur plutôt que transitive et cachée derrière un autre Manager), la maintenabilité future (tout nouveau besoin Workspace se lit directement, sans toucher aux Managers) et le précédent déjà établi par `InferencePage`. Le coût de l'Option A a été chiffré précisément avant la décision : 22 sites d'instanciation au total (5 constructeurs de Page + `main_window.py` + 8 fichiers de tests), chacun ayant déjà `workspace_manager` en scope.

`WorkspaceManager.opened` reste la seule source d'autorité. Aucune propriété `workspace_opened` n'a été ajoutée à aucun Manager métier. Aucun contrat Manager modifié.

## 5. Périmètre IN

- Injection de `WorkspaceManager` dans les constructeurs de `CharactersPage`, `DatasetsPage`, `LoRAPage`, `PromptsPage`, `TrainingPage`.
- `InferencePage` réutilise sa dépendance `WorkspaceManager` déjà existante — aucun changement de constructeur.
- Correction de la branche `None` aux 7 emplacements validés : `CharactersPage.save_identity()`, `PromptsPage.create_prompt()`, `PromptsPage.save_as_new_prompt()`, `DatasetsPage.create_dataset()`, `LoRAPage.create_lora()`, `TrainingPage.create_training()` (bloc « Aucun personnage » uniquement), `InferencePage._on_save_prompt_clicked()`.
- Mise à jour des 5 sites d'instanciation dans `main_window.py` et des 22 sites de tests concernés (réutilisation de la variable `workspace_manager` déjà en scope partout).

## 6. Périmètre OUT (strict, explicitement différé)

`CharactersPage.create_character()` (déjà correct, non touché) ; ambiguïté distincte `TrainingPage → « Aucun dataset disponible »` ; dirty-state de `PromptsPage` ; Prompt Library, tags, RAG, vision, Character Context avancé ; i18n ; toute refonte générale des Managers ou de la gestion des erreurs ; toute nouvelle propriété `workspace_opened` sur un Manager métier.

## 7. Fichiers concernés

Production (7) : `src/ui/main_window.py`, `src/ui/pages/characters_page.py`, `src/ui/pages/datasets_page.py`, `src/ui/pages/lora_page.py`, `src/ui/pages/prompts_page.py`, `src/ui/pages/training_page.py`, `src/ui/pages/inference_page.py`.
Tests (8) : `test_character_roundtrip.py`, `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py`, `test_inference_page.py`, `test_model_roundtrip.py`, `test_workflow_roundtrip.py` (ces deux derniers uniquement pour leur wiring `CharactersPage(...)` partagé).

Aucun autre fichier — `CharacterManager`/`DatasetManager`/`LoRAManager`/`PromptManager`/`TrainingManager`, `src/domain/`, `src/core/event_bus.py` strictement inchangés.

## 8. Fonctionnalités livrées (implémentation réelle)

Aux 7 emplacements, la branche `None` existante teste désormais `workspace_manager.opened` (ou `self._workspace_manager.opened` pour `InferencePage`) : `False` → nouveau message « Aucun projet ouvert » / « Ouvrez ou créez un projet avant de *\<action\>*. » (gabarit repris de `CharactersPage.create_character()`) ; `True` → message « Aucun personnage »/« Aucun personnage sélectionné » existant, texte inchangé. Séquencement d'appel (`create()`/`update()` toujours en premier) strictement inchangé partout.

## 9. Tests ajoutés/modifiés (11 nets nouveaux)

- `test_character_roundtrip.py` (+1, `CharactersPageIdentityFicheTest`) : `test_save_identity_without_open_workspace_shows_no_project_warning`, plus `test_save_identity_without_any_character_shows_warning` renforcé d'une assertion exacte de message.
- `test_dataset_roundtrip.py`/`test_lora_roundtrip.py` (+2 chacun, classes `*CreationWithoutManualCharacterSelectionTest` existantes) : un test par cause, assertions exactes de titre/texte.
- `test_prompt_roundtrip.py` (+3) : `PromptCreationWithoutManualCharacterSelectionTest` (+2, pour `create_prompt()`) ; `PromptsPageSaveAsNewPromptTest` (+1 nouveau, +1 existant renforcé, pour `save_as_new_prompt()`).
- `test_training_roundtrip.py` (+2, `TrainingCreationWithoutManualCharacterSelectionTest`) : `dataset_manager` mocké (`list_datasets()` non vide) pour isoler la branche « Aucun personnage », normalement non atteignable en usage réel (voir section 3).
- `test_inference_page.py` (+1 nouveau, +1 existant renforcé, `InferencePagePromptAssistantTest`).

Aucune nouvelle classe de test créée — toutes les assertions s'insèrent dans des classes existantes.

## 10. Résultats de tests (automatisés)

- Suite ciblée (8 fichiers concernés) : **228/228 OK**.
- Suite complète (`python -m unittest discover -s tests -p "test_*.py"`) : **678/678 OK** (667 précédents + 11 nets nouveaux), une seule exécution après implémentation.

## 11. Smoke test manuel réel — résultat

**Résultat global : PASS.** Aucune anomalie bloquante constatée.

| # | Cas | Résultat |
|---|---|---|
| 1 | Aucun projet ouvert — actions concernées (Characters/Prompts ×2/Datasets/LoRA/Inference) — message « Aucun projet ouvert » | PASS |
| 2 | Aucune action métier ne se produit malgré l'avertissement | PASS |
| 3 | `CharactersPage.create_character()` conserve son comportement correct existant | PASS |
| 4 | Workspace ouvert avec personnage valide — flux habituels (création Prompt/Dataset/LoRA, Training, identité, Inference → Enregistrer dans Prompts) inchangés | PASS |
| 5 | Ambiguïté `TrainingPage → « Aucun dataset disponible »` confirmée hors périmètre, non corrigée | PASS (confirmé) |

**Observation importante confirmée pendant le smoke test** : dans le fonctionnement normal de l'application, un Workspace ouvert possède toujours un Character principal auto-créé (nom repris du projet, fiche pouvant rester vide) — l'état « Workspace ouvert sans personnage principal » n'est donc pas un scénario UX normalement atteignable ; il reste couvert comme cas technique/défensif par la suite automatisée (section 9), sans avoir été reproduit manuellement. Voir `docs/PROJECT_CONTEXT.md`, section "Orientation architecturale validée", pour l'invariant désormais explicite.

## 12. Observation hors périmètre confirmée pendant le smoke test manuel

`TrainingPage.create_training()` peut afficher « Aucun dataset disponible » avant même d'atteindre la branche « Aucun personnage » lorsqu'aucun Workspace n'est ouvert — ambiguïté distincte des 7 emplacements corrigés, **non traitée par Mission 036**, enregistrée comme besoin futur dans `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés", sans décision architecturale de correction.

## Commit correspondant

`ebd49d5f451448802e2732de9e4da718cd735506` — `feat: distinguish no open project from no principal character in warnings`. Inclut l'implémentation fonctionnelle (code + tests) de Mission 036.

## Tag / release correspondant

`v0.2-mission036` (annoté, message `Mission 036 - Distinguish no open project from no principal character in warnings`), ciblant exactement `ebd49d5f451448802e2732de9e4da718cd735506`. GitHub Release `v0.2-mission036` **publiée**.

## État d'avancement

- Audit et spécification : **validés**, y compris une révision architecturale explicite (Option A retenue sur Option C, voir section 4).
- Implémentation : **réalisée**, conforme à la spécification validée.
- Tests automatisés ciblés (228/228) et suite complète (678/678) : **exécutés, verts**.
- Smoke test manuel réel : **PASS** (voir section 11) — invariant Workspace/Character clarifié, une ambiguïté distincte reconfirmée hors périmètre (section 12).
- Clôture Git : **effectuée** — commit fonctionnel `ebd49d5f451448802e2732de9e4da718cd735506`, tag `v0.2-mission036`.
- GitHub Release : **publiée**.

## État final

Mission 036 — Distinguish no open project from no principal character in warnings — est **entièrement close** : implémentation, 678/678 tests automatisés, smoke test manuel réel complet PASS, clôture Git et publication GitHub Release toutes effectuées. La dette UX transversale enregistrée pendant Mission 035 est résolue. La dette distincte `TrainingPage → « Aucun dataset disponible »` reste enregistrée comme besoin futur dans `docs/PROJECT_CONTEXT.md`, non traitée par cette mission.
