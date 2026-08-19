# Mission 035 — Enregistrer comme nouveau Prompt… depuis un brouillon libre

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 667/667 tests automatisés verts, smoke test manuel réel PASS, clôture Git effectuée, GitHub Release `v0.2-mission035` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Le smoke test manuel réel de Mission 034 a révélé une observation UX non bloquante, enregistrée dans `docs/PROJECT_CONTEXT.md` : dans `PromptsPage`, sans Prompt sélectionné, l'Assistant IA reste utilisable en mode Créer et « Utiliser ce texte » place correctement le résultat dans `text_edit` — mais aucun chemin clair n'existe ensuite pour l'enregistrer comme nouveau `Prompt` (`save_text()` exige un Prompt actif ; `create_prompt()` crée un Prompt vide, sans reprendre le texte visible). Comportement confirmé préexistant (Missions 031/032), non introduit ni aggravé par Mission 034.

## 2. Objectif

Permettre à l'utilisateur, depuis `PromptsPage`, de transformer explicitement le texte actuellement visible dans l'éditeur en nouveau `Prompt` nommé et persisté — avec ou sans Prompt actuellement actif — en réutilisant le contrat déjà existant `PromptManager.create(name, text="")` (Mission 031), sans le modifier.

## 3. Audit ciblé — constats vérifiés par lecture directe du code

- `PromptManager.create(name: str, text: str = "") -> Optional[Prompt]` ([prompt_manager.py:81-105](src/managers/prompt_manager.py:81)) construit un `Prompt`, l'ajoute à `principal_character.prompts`, sauvegarde, publie `PROMPT_CREATED`, retourne `None` si aucun personnage principal — **ne sélectionne jamais** l'objet créé. Contrat déjà additif et suffisant depuis Mission 031, aucune extension nécessaire.
- `PromptsPage.create_prompt()` ([prompts_page.py:113-132](src/ui/pages/prompts_page.py:113)) ne lit jamais `text_edit` — texte toujours `""`.
- `PromptsPage.save_text()` ([prompts_page.py:195-205](src/ui/pages/prompts_page.py:195)) exige `active_prompt_id`, ne crée jamais de nouveau Prompt.
- `InferencePage._on_save_prompt_clicked()` ([inference_page.py:248-276](src/ui/pages/inference_page.py:248)) réalise déjà exactement ce besoin depuis Inference — `QInputDialog.getText` puis `create(name.strip(), text=text)` — mais **ne sélectionne jamais** le Prompt créé (`test_create_with_text_does_not_select_or_affect_prompts_page_selection`), garantie nécessaire car cette action se déclenche depuis une autre Page que `PromptsPage`.
- `EventBus.publish()` ([event_bus.py:46-50](src/core/event_bus.py:46)) est **synchrone** — `PROMPT_CREATED` déclenche `update_prompts()` avant même que `create()` ne retourne à l'appelant. `update_prompts()` réécrit inconditionnellement `text_edit` selon `active_prompt_id` : sans sélection explicite du nouveau Prompt, ce rafraîchissement viderait visuellement l'éditeur (aucun Prompt ne correspondrait encore à `active_prompt_id`).

## 4. Décision d'architecture — sélection explicite après création

Contrairement à `InferencePage._on_save_prompt_clicked()` (qui ne doit jamais sélectionner, pour ne pas perturber la sélection de `PromptsPage` depuis une autre Page), la nouvelle action de `PromptsPage` appelle `self.prompt_manager.select(prompt.prompt_id)` explicitement juste après `create()` — décision locale à sa propre Page, sans lien avec la garantie Mission 031. Sans cet appel, le rafraîchissement synchrone déclenché par `PROMPT_CREATED` viderait `text_edit` alors même que le texte vient d'être persisté avec succès.

`PromptManager.create()` lui-même n'est **pas modifié** pour sélectionner automatiquement — cela aurait cassé le contrat déjà utilisé et testé par Inference.

## 5. Périmètre IN

- Nouveau bouton **« Enregistrer comme nouveau Prompt… »** dans `PromptsPage`, activé/désactivé sur le même critère que `send_to_inference_button` (texte non vide, indépendant de `active_prompt_id`).
- Nouvelle méthode `save_as_new_prompt()` : dialogue de nommage (idiome déjà établi), `prompt_manager.create(name, text=...)`, puis `select(prompt.prompt_id)` en cas de succès, avertissement identique à `create_prompt()` si aucun personnage principal.

## 6. Périmètre OUT (strict, explicitement différé)

Dirty-state général de `PromptsPage` ; propreté de la sortie du Prompt Assistant ; sélecteur visuel Créer/Améliorer ; Prompt Library, tags, RAG, vision, Character Context avancé ; toute extension du Domain `Prompt` ; toute modification de `PromptManager.create()`/`select()`/`update_text()`, d'`InferencePage`, ou du Prompt Assistant.

## 7. Fichiers concernés

- `src/ui/pages/prompts_page.py`
- `tests/integration/test_prompt_roundtrip.py`

Aucun autre fichier — `PromptManager`, `Prompt`, `InferencePage`, `PromptAssistantDialog`/`Manager`/`Worker`, `main_window.py` strictement inchangés.

## 8. Fonctionnalités livrées (implémentation réelle)

- `src/ui/pages/prompts_page.py` : nouveau `save_as_new_prompt_button`, piloté par `_on_text_changed()` au même titre que `send_to_inference_button` ; nouvelle méthode `save_as_new_prompt()` — garde texte vide, `QInputDialog.getText("Nouveau prompt", "Nom :")` (idiome déjà utilisé par `create_prompt()`/`InferencePage._on_save_prompt_clicked()`), `prompt_manager.create(name.strip(), text=text)`, avertissement « Aucun personnage » si `None` (texte identique à `create_prompt()`), puis `prompt_manager.select(prompt.prompt_id)` explicite en cas de succès.
- Fonctionne identiquement avec ou sans Prompt actif : le Prompt actif d'origine, s'il existe, n'est jamais lu ni modifié (`update_text()` jamais appelé par cette méthode).
- Après création, le nouveau Prompt devient la sélection de `PromptsPage` — liste rafraîchie, éditeur affichant le même texte qu'avant le clic (pas de vidage visuel).
- Aucune sauvegarde implicite : ouvrir ou utiliser l'Assistant IA ne crée jamais de Prompt par lui-même — seul un clic explicite sur ce nouveau bouton le fait.

## 9. Tests ajoutés/modifiés (12 nets nouveaux)

- `tests/integration/test_prompt_roundtrip.py`, classe `PromptRoundTripTest` (+2, Managers/EventBus réels) : `test_save_as_new_prompt_without_active_prompt_creates_and_selects_it` (création + sélection, éditeur inchangé après le rafraîchissement synchrone) ; `test_save_as_new_prompt_with_active_prompt_leaves_original_untouched` (Prompt d'origine strictement intact, second Prompt distinct créé et sélectionné).
- Nouvelle classe `PromptsPageSaveAsNewPromptTest` (+10, Managers mockés, mirroir de `PromptsPageSendToInferenceTest`) : présence/activation du bouton (éditeur vide, whitespace, texte présent, activé même avec Prompt actif, désactivation après effacement) ; création avec `select()` appelé sur l'id exact ; avec Prompt actif, `update_text` jamais appelé et `select()` pointe vers le nouveau Prompt ; annulation du dialogue → aucune création ; nom vide → aucune création ; aucun personnage principal → avertissement affiché, `select()` jamais appelé.
- Aucun test existant modifié — en particulier `test_create_with_text_does_not_select_or_affect_prompts_page_selection` (garantie Mission 031 pour `InferencePage`) reste intact et vert sans aucune adaptation.

## 10. Résultats de tests (automatisés)

- Suite ciblée (`test_prompt_roundtrip.py`) : **40/40 OK**.
- Suite complète (`python -m unittest discover -s tests -p "test_*.py"`) : **667/667 OK** (655 précédents + 12 nets nouveaux), une seule exécution après implémentation.

## 11. Smoke test manuel réel — résultat

**Résultat global : PASS.** Aucune anomalie bloquante liée à Mission 035 constatée.

| # | Cas | Résultat |
|---|---|---|
| 1 | Bouton « Enregistrer comme nouveau Prompt… » présent, désactivé sur éditeur vide | PASS |
| 2 | Création sans Prompt actif — nouveau Prompt créé, sélectionné, éditeur inchangé visuellement | PASS |
| 3 | Création avec Prompt actif — Prompt d'origine intact, nouveau Prompt distinct créé et sélectionné | PASS |
| 4 | Annulation du dialogue de nommage — aucun effet observable | PASS |
| 5 | Aucune régression de « Enregistrer le texte » / « Nouveau prompt » / Assistant IA / `Prompts → Envoyer vers Inference` | PASS |

## 12. Observation UX non bloquante découverte pendant le smoke test manuel

Une ambiguïté UX **préexistante et transversale**, sans lien avec l'implémentation de Mission 035, a été constatée : lorsqu'aucun projet/Workspace n'est ouvert, plusieurs Pages (`Characters`, `Prompts`, `Datasets`, `LoRA`, `Training`, `Inference`) affichent un message du type « Aucun personnage » alors que le vrai problème est qu'aucun projet n'est ouvert — `CharacterManager.principal_character`/`principal_character_id` (et les `create()` des Managers qui en dépendent) retournent `None` aussi bien dans ce cas que lorsqu'un Workspace existe sans personnage principal, ce qui empêche les Pages concernées de distinguer les deux causes. Un audit dédié (voir échange de session) a confirmé le caractère transversal du sujet (7 emplacements sur 6 fichiers) et une incohérence interne à `characters_page.py` (`create_character()` distingue déjà correctement le cas « aucun projet ouvert », `save_identity()` non). **Non traité par Mission 035, non introduit ni aggravé par elle** — enregistré comme besoin futur dans `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés", sans décision architecturale de correction.

## Commit correspondant

`a2766b6063859db85ec87e49b9a372d51d6c1c6f` — `feat: add save-as-new-prompt action to PromptsPage`. Inclut l'implémentation fonctionnelle (code + tests) de Mission 035.

## Tag / release correspondant

`v0.2-mission035` (annoté, message `Mission 035 - Save as new Prompt from a free draft`), ciblant exactement `a2766b6063859db85ec87e49b9a372d51d6c1c6f`. GitHub Release `v0.2-mission035` **publiée**.

## État d'avancement

- Audit et spécification : **validés**.
- Implémentation : **réalisée**, conforme à la spécification validée.
- Tests automatisés ciblés (40/40) et suite complète (667/667) : **exécutés, verts**.
- Smoke test manuel réel : **PASS** (voir section 11) — une dette UX transversale préexistante remontée (section 12), hors périmètre, sans lien avec le résultat.
- Clôture Git : **effectuée** — commit fonctionnel `a2766b6063859db85ec87e49b9a372d51d6c1c6f`, tag `v0.2-mission035`.
- GitHub Release : **publiée**.

## État final

Mission 035 — Enregistrer comme nouveau Prompt… depuis un brouillon libre — est **entièrement close** : implémentation, 667/667 tests automatisés, smoke test manuel réel complet PASS, clôture Git et publication GitHub Release toutes effectuées. La dette UX transversale remontée pendant le smoke test (section 12) reste enregistrée comme besoin futur dans `docs/PROJECT_CONTEXT.md`, non traitée par cette mission.
