# Mission 040 — Restore "Utiliser ce texte" actionability after a failed follow-up generation

> **STATUT : SPÉCIFICATION VALIDÉE, IMPLÉMENTATION NON COMMENCÉE.** Audit de sélection et réévaluation du contrat fonctionnel effectués et validés par l'architecte. Aucun code, aucun test, aucun commit, aucun tag n'existe encore pour cette mission au moment de la rédaction de ce document.

## 1. Contexte

Mission 039 a introduit un contrat de sortie propre pour le Prompt Assistant (`@@AISTUDIO_PROMPT_START@@`/`@@AISTUDIO_PROMPT_END@@`, extraction déterministe, fallback non destructeur). Son smoke test manuel réel a identifié en retour une dette UX distincte, non corrigée par cette mission : dans `PromptAssistantDialog`, un résultat précédemment généré avec succès reste affiché dans « Résultat proposé » (`result_edit`) après l'échec d'une génération suivante, sous la boîte d'erreur — voir `docs/missions/MISSION_039.md` section 11 et `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés".

L'audit de sélection de Mission 040 a d'abord qualifié ce constat comme un défaut d'affichage à corriger (vider ou marquer le résultat comme obsolète). L'architecte a explicitement rejeté cette lecture : la conservation du dernier résultat valide dans `result_edit` après un échec est le comportement **voulu**, pas un bug. Une réévaluation du code réel (`src/ui/dialogs/prompt_assistant_dialog.py`) a alors établi que le contenu de `result_edit` respecte déjà exactement ce contrat de conservation, sans qu'aucune modification n'y soit nécessaire — mais qu'un défaut distinct et réel subsiste : `use_result_button` (« Utiliser ce texte ») ne suit pas la même logique. Il est désactivé à chaque lancement de génération (`_on_generate_clicked()`) et n'est jamais réactivé par `_on_assist_failed()` en cas d'échec — seul `_on_assist_finished()` (succès) le réactive. Conséquence vérifiée par lecture directe du code : après une génération réussie suivie d'une génération échouée, le résultat précédent reste affiché mais devient **inutilisable** via le bouton, alors qu'il demeure le dernier résultat valide.

Confirmé par ailleurs que le test automatisé existant `test_prompt_assistant_error_does_not_crash_and_re_enables_controls` (`tests/integration/test_prompt_assistant_dialog.py`) ne couvre que le cas « aucun résultat préalable + échec » (`result_edit` vide, bouton désactivé — correct) ; le cas « résultat préalable valide + échec suivant » n'est couvert par aucun test existant.

## 2. Problème

`use_result_button` reste désactivé après l'échec d'une génération, même lorsque `result_edit` affiche encore un résultat valide et utilisable issu d'une génération précédente réussie — incohérence entre ce qui est affiché et ce qui est actionnable.

**Explicitement hors sujet** : le contenu de `result_edit` lui-même. Il ne doit jamais être vidé ni modifié au lancement d'une nouvelle génération, ni à l'échec d'une génération — ce comportement de conservation est déjà correct et ne doit pas changer.

## 3. Objectif

Faire dépendre l'état de `use_result_button` de la présence d'un résultat valide utilisable dans `result_edit`, plutôt que du seul succès de la dernière tentative de génération.

## 4. Contrat fonctionnel validé

**Scénario principal** :
1. génération A réussie ;
2. résultat A affiché ;
3. `use_result_button` activé ;
4. génération B lancée ;
5. résultat A reste affiché pendant B ;
6. les contrôles peuvent conserver leur comportement actuel pendant le traitement, notamment la désactivation temporaire du bouton ;
7. génération B échoue ;
8. résultat A reste affiché ;
9. `use_result_button` doit redevenir activé ;
10. la boîte d'erreur actuelle reste affichée normalement.

**Scénario sans résultat préalable** :
1. aucun résultat valide n'est présent ;
2. une génération échoue ;
3. `result_edit` reste vide ;
4. `use_result_button` reste désactivé ;
5. la boîte d'erreur actuelle apparaît normalement.

**Scénario succès après succès** :
1. A réussit ;
2. A est affiché ;
3. B réussit ;
4. B remplace A ;
5. `use_result_button` est activé pour B.

## 5. Périmètre

Production (1) : `src/ui/dialogs/prompt_assistant_dialog.py`.
Tests (1) : `tests/integration/test_prompt_assistant_dialog.py`.
Documentation : ce fichier (`docs/missions/MISSION_040.md`), puis `docs/PROJECT_CONTEXT.md`/`CHANGELOG.md` à la clôture de la mission (workflow standard, non anticipé ici).

## 6. Hors périmètre

- Modification du contenu de `result_edit` lors d'un échec.
- Effacement du résultat précédent au lancement d'une génération.
- Changement du contrat Create/Improve.
- Refonte du sélecteur de mode (`create_mode_button`/`improve_mode_button` — dette distincte, voir "Besoins futurs identifiés").
- Modification du backend Ollama / `AIBackend`.
- Domain, Managers, EventBus, persistance.
- Character Context.
- Toute autre dette UX du Prompt Assistant (clarté du sélecteur de mode, miniatures Dataset, etc. — candidats Mission 040 écartés lors de l'audit de sélection).

## 7. Stratégie d'implémentation proposée

Modification minimale, localisée à `_on_assist_failed()` :

- Après l'affichage de la boîte d'erreur (`QMessageBox.critical`), faire dépendre l'état de `use_result_button` de la présence de contenu utilisable dans `result_edit` : activé si `result_edit.toPlainText().strip()` est non vide, désactivé sinon.
- `_on_generate_clicked()` reste inchangé (désactivation temporaire de `use_result_button` en tête de tentative, conforme au point 6 du contrat — "les contrôles peuvent conserver leur comportement actuel pendant le traitement").
- `_on_assist_finished()` reste inchangé (remplace `result_edit` par le nouveau résultat et active `use_result_button` inconditionnellement en cas de succès — déjà correct, scénario "succès après succès" du contrat).
- Aucune nouvelle méthode, aucun nouvel attribut, aucun changement de signature — la correction consiste à faire lire à `_on_assist_failed()` l'état réel de `result_edit` plutôt que de laisser `use_result_button` hériter silencieusement de son état précédent (désactivé par `_on_generate_clicked()`).

Cette approche est délibérément la plus petite modification cohérente avec l'architecture existante : elle ne touche qu'un seul gestionnaire d'événement, ne modifie aucun autre contrôle, et fait de l'état du bouton une fonction directe et vérifiable du contenu actuellement affiché plutôt que de l'historique de la dernière tentative.

## 8. Stratégie de tests

Dans `PromptAssistantDialogGenerateTest` (`tests/integration/test_prompt_assistant_dialog.py`) :

- **Nouveau test** reproduisant exactement le scénario de régression demandé : génération A réussie (`manager.assist` retourne un texte), puis génération B échouée (`manager.assist` lève `PromptAssistantError` au second appel, via `side_effect` en liste) — vérifie au minimum :
  - `result_edit.toPlainText()` contient toujours exactement le texte de A après l'échec de B ;
  - `use_result_button.isEnabled()` est de nouveau `True` après l'échec de B ;
  - la boîte d'erreur (`QMessageBox.critical`, mockée) a bien été appelée.
- **Non-régression explicite du scénario "aucun résultat préalable + échec"** : le test existant `test_prompt_assistant_error_does_not_crash_and_re_enables_controls` doit continuer à passer sans modification — `result_edit` vide et `use_result_button` désactivé après un échec sans résultat préalable.
- **Non-régression implicite du scénario "succès après succès"** : déjà couvert par les tests existants (`test_create_mode_calls_assist_without_existing_prompt`, `test_improve_mode_calls_assist_with_the_existing_prompt`) qui vérifient `use_result_button.isEnabled()` après un succès — aucun nouveau test requis pour ce scénario, seule la non-régression compte.

## 9. Critères d'acceptation

- Le nouveau test de régression (succès A → échec B) passe.
- Le test existant de non-régression (aucun résultat préalable → échec) passe sans modification de son corps.
- L'ensemble des tests déjà existants pour `PromptAssistantDialog` et `PromptAssistantManager` passent sans modification de leurs assertions (hors l'ajout du nouveau test).
- Suite complète du projet exécutée et verte, nombre exact de tests confirmé.
- Aucun fichier hors du périmètre validé (section 5) n'est modifié.

## 10. Smoke test manuel

Cette mission ne modifie aucun comportement du backend IA (`AIBackend`/`OllamaEngine` strictement hors périmètre) — seul l'état d'un contrôle Qt local à `PromptAssistantDialog` change. Un smoke test manuel réel contre une instance Ollama réelle reste néanmoins utile pour confirmer visuellement le contrat, notamment le scénario principal (déclenchement volontaire d'un timeout ou d'une erreur après une première génération réussie). Modalités exactes (nécessité, conditions de déclenchement d'un échec réel) à confirmer par l'architecte au moment de la validation post-implémentation, conformément à la procédure habituelle du projet.

## 11. Risques / non-régressions

- **Risque principal** : une réactivation trop large de `use_result_button` (ex. inconditionnelle dans `_on_assist_failed()`) réintroduirait un bouton actionnable sur un `result_edit` vide — explicitement exclu par le contrat et par la consigne de l'architecte ("ne pas simplement réactiver inconditionnellement"). La condition sur le contenu réel de `result_edit` élimine ce risque par construction.
- **Non-régression Create/Improve** : aucun changement aux méthodes `_build_combined_text()`/`assist()` de `PromptAssistantManager`, ni à la construction des boutons de mode — hors périmètre, non touché.
- **Non-régression du scénario "aucun résultat préalable"** : couverte explicitement par la conservation du test existant, sans modification de son corps.
- **Non-régression architecturale** : aucun changement Domain/Manager/EventBus/persistance ; modification strictement confinée à la couche Presentation (`PromptAssistantDialog`), cohérent avec le fait que ce défaut n'a jamais engagé aucune autre couche.
