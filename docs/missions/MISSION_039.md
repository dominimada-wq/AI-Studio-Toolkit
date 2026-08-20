# Mission 039 — Enforce a clean output contract for the Prompt Assistant

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 713/713 tests automatisés verts, smoke test manuel réel PASS, clôture Git effectuée, GitHub Release `v0.2-mission039` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Besoin identifié pendant le smoke test réel de Mission 031, reconfirmé toujours ouvert lors de l'audit de sélection de Mission 039 : le Prompt Assistant retournait directement la réponse brute du LLM à l'utilisateur. Selon le modèle local configuré (Ollama), cette réponse pouvait contenir un préambule, des explications, une analyse, du Markdown ou des commentaires autour du prompt final — l'action « Utiliser ce texte » pouvait donc récupérer autre chose que le seul prompt exploitable.

## 2. Objectif

Améliorer de façon fiable la récupération du prompt final exploitable, sans transformer `AIBackend` en protocole de sortie structurée général — le contrat de délimitation devait rester propre au seul consommateur ayant ce besoin, `PromptAssistantManager`.

## 3. Contrat de sortie

`PromptAssistantManager` demande désormais explicitement au modèle de retourner uniquement le prompt final — sans explication, sans analyse, sans préambule, sans commentaire avant ou après, sans bloc Markdown englobant — et d'encadrer ce prompt final avec des marqueurs dédiés :

- Marqueur de début : `@@AISTUDIO_PROMPT_START@@`
- Marqueur de fin : `@@AISTUDIO_PROMPT_END@@`

Le bloc d'instructions (`OUTPUT_CONTRACT_BLOCK`) est construit à partir de ces mêmes constantes (le texte demandé au modèle et le texte recherché à l'extraction ne peuvent jamais diverger), ajouté **une seule fois** en fin de texte combiné dans `_build_combined_text()`, identiquement pour les modes Créer et Améliorer, avec ou sans `CharacterContext` (Mission 034 inchangée).

## 4. Extraction déterministe

`PromptAssistantManager.assist()` applique désormais un post-traitement déterministe via `_extract_final_prompt()` sur la réponse du backend. L'extraction n'a lieu que si, simultanément :

- `START` apparaît exactement une fois ;
- `END` apparaît exactement une fois ;
- `START` précède `END` ;
- le contenu interne, après `.strip()`, n'est pas vide.

Dans ce cas, seul le contenu interne est retourné, sans aucun nettoyage heuristique supplémentaire — le contenu multilignes ou le Markdown légitime à l'intérieur du prompt final est préservé tel quel.

## 5. Fallback non destructeur

Dans tous les autres cas — délimiteurs absents, un seul des deux présents, ordre inversé, occurrences multiples, ou contenu interne vide/whitespace-only — le comportement est `response.strip()` : la réponse complète du modèle reste disponible, non tronquée. **Ce fallback est volontaire** : aucune heuristique ne tente de deviner quelle portion de la réponse constitue le prompt (pas de suppression de Markdown, de premier paragraphe, de motif `"Prompt:"`, ou de phrases jugées analytiques) — l'objectif est de ne jamais perdre une réponse valide du modèle, pas d'atteindre 100 % de respect du contrat par celui-ci.

## 6. Architecture conservée

- `AIBackend.generate_text(prompt, model) -> str` : **strictement inchangé**.
- `OllamaEngine` : **strictement inchangé**.
- Aucun JSON mode générique, aucun protocole de sortie structurée universel, aucune nouvelle méthode Backend, aucun changement Domain, EventBus ou persistance.
- Le contrat de délimitation appartient pour l'instant exclusivement à `PromptAssistantManager` — cette décision ne préjuge d'aucune évolution future d'`AIBackend` pour Prompt Library, tags, RAG, vision/multimodal ou d'autres providers IA.

## 7. Fichiers concernés

Production (1) : `src/managers/prompt_assistant_manager.py`.
Tests (1) : `tests/integration/test_prompt_assistant_manager.py`.

Aucun autre fichier — `AIBackend`, `OllamaEngine`, `PromptAssistantDialog`, `PromptAssistantWorker`, `PromptsPage`, `InferencePage`, Domain, EventBus strictement inchangés.

## 8. Tests ajoutés/modifiés (17 nets nouveaux)

- 6 tests existants adaptés (texte littéral envoyé au backend désormais suffixé par `OUTPUT_CONTRACT_BLOCK`) : instruction Créer, instruction Créer avec demande vide, instruction Améliorer, les deux tests de non-régression "sans contexte" (renommés pour refléter leur portée réelle : absence de bloc identité, pas byte-for-byte avec le texte antérieur à Mission 039), et l'assertion d'égalité stricte sans contexte.
- `PromptAssistantManagerOutputContractInstructionTest` (4 nouveaux) : présence du bloc en Créer/Améliorer, unicité avec `CharacterContext`, ordre identité → demande actuelle → instructions de sortie.
- `PromptAssistantManagerExtractFinalPromptTest` (9 nouveaux) : paire valide, espaces périphériques, sans délimiteur, START seul, END seul, paires multiples, délimiteurs inversés, contenu multilignes préservé, Markdown interne préservé, contenu vide/whitespace-only entre délimiteurs valides → fallback.
- `PromptAssistantManagerAssistExtractionIntegrationTest` (3 nouveaux) : `assist()` bout-en-bout — contrat respecté, contrat ignoré, erreur backend n'atteint jamais l'extraction.

## 9. Résultats de tests (automatisés)

- Suite ciblée (`test_prompt_assistant_manager.py`) : **44/44 OK**.
- Suite complète : **713/713 OK** (696 précédents + 17 nets nouveaux).

## 10. Smoke test manuel réel — résultat

**Résultat global : PASS.** Deux comportements clés vérifiés contre une instance Ollama réelle (`llama3.2:3b`) :

- **Contrat respecté** : une génération a produit une paire de délimiteurs valide — seul le prompt final était visible dans « Résultat proposé », aucun marqueur affiché. Extraction confirmée fonctionnelle.
- **Contrat incomplet** : une autre génération a produit `START` sans `END` — le marqueur `START` restait visible dans la réponse brute affichée, aucune partie de la réponse n'a été supprimée. Fallback non destructeur confirmé conforme à la spécification, non une anomalie.

**Timeout Ollama observé pendant le smoke test** : `Ollama server unreachable at http://127.0.0.1:11434: timed out`, occasionnel. Diagnostiqué et confirmé comme comportement préexistant : `OllamaEngine` utilise un timeout par défaut de `30.0 s` (inchangé depuis Mission 030), cohérent avec la limite de cold start Ollama déjà documentée (voir `docs/missions/MISSION_030.md` section 13). `OllamaEngine` n'a pas été modifié par Mission 039 et aucun lien causal avec cette mission n'a été établi — non traité comme une régression.

## 11. Nouvelle dette UX découverte pendant le smoke test — non corrigée par Mission 039

**`PromptAssistantDialog` — résultat précédent conservé après échec d'une génération suivante.** Constaté pendant le smoke test réel : lorsqu'une génération réussit puis qu'une génération suivante échoue (ex. timeout Ollama), le contenu précédent de « Résultat proposé » reste affiché tel quel, sous la boîte d'erreur. Cause vérifiée par lecture directe du code : `_on_assist_failed()` affiche l'erreur (`QMessageBox.critical`) mais ne vide jamais `result_edit` ; `_on_generate_clicked()` ne le vide pas non plus avant de relancer un appel. Conséquence UX : l'utilisateur peut voir simultanément un message d'erreur portant sur la nouvelle génération et un ancien résultat toujours affiché, pouvant laisser croire à tort que ce texte appartient à la requête qui vient d'échouer. **Comportement préexistant, antérieur à Mission 039** (fichier `prompt_assistant_dialog.py` non modifié par cette mission), volontairement non corrigé ici — enregistré comme besoin futur, aucune décision UX prise (vider au lancement, vider seulement après échec, ou conserver en le marquant explicitement comme ancien restent des options non tranchées). Voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés", pour l'enregistrement complet.

## 12. Mode Améliorer sans Workspace ouvert — non une dette Mission 039

Diagnostiqué pendant le smoke test : sans Workspace/Prompt actif, le bouton « Améliorer le prompt actuel » n'est jamais créé dans `PromptAssistantDialog` (`existing_prompt` toujours vide dans ce cas, `prompts_page.py::_on_assistant_clicked()`). Confirmé comme comportement architectural préexistant, établi dès Mission 031, non modifié par Mission 039 — aucune dette enregistrée sur ce point.

## Commit correspondant

`d379f92db6d2a6d3554eb40e6edb5d353f51ca53` — `feat: enforce a clean output contract for the Prompt Assistant`. Inclut l'implémentation fonctionnelle (code + tests) de Mission 039.

## Tag / release correspondant

`v0.2-mission039` (annoté, message `Mission 039 - Enforce a clean output contract for the Prompt Assistant`), ciblant exactement `d379f92db6d2a6d3554eb40e6edb5d353f51ca53`. GitHub Release `v0.2-mission039` **publiée**.

## État d'avancement

- Audit de sélection, mini-décision technique (instruction + délimitation + fallback défensif) et spécification : **validés**, y compris l'ajout défensif final (garde contenu vide → fallback).
- Implémentation : **réalisée**, conforme à la spécification validée, périmètre strictement respecté (2 fichiers).
- Tests automatisés ciblés (44/44) et suite complète (713/713) : **exécutés, verts**.
- Smoke test manuel réel : **PASS**, deux chemins clés vérifiés (contrat respecté / fallback non destructeur), une nouvelle dette UX distincte identifiée en retour (section 11), non corrigée par cette mission.
- Clôture Git : **effectuée** — commit fonctionnel `d379f92db6d2a6d3554eb40e6edb5d353f51ca53`, tag `v0.2-mission039`.
- GitHub Release : **publiée**.

## État final

Mission 039 — Enforce a clean output contract for the Prompt Assistant — est **entièrement close** : implémentation, 713/713 tests automatisés, smoke test manuel réel PASS, clôture Git et publication GitHub Release toutes effectuées. Le besoin documenté depuis Mission 031 (sortie du Prompt Assistant potentiellement polluée par du préambule/analyse/Markdown) est résolu par un contrat de délimitation déterministe et un fallback strictement non destructeur, sans évolution d'`AIBackend`/`OllamaEngine`. Une nouvelle dette UX distincte (résultat précédent conservé après échec dans `PromptAssistantDialog`) a été identifiée en retour et enregistrée comme besoin futur, non transformée en correction de cette mission.
