# Mission 032 — Prompt Assistant dans PromptsPage

**État final (voir sections 8/11/12)** : implémentée, 597/597 tests automatisés verts, **et validée par un smoke test manuel réel complet — PASS**. **Clôture Git non encore effectuée** (aucun commit/tag/Release créé à ce stade) — en attente de validation explicite de l'architecte.

## 1. Contexte

Mission 031 a livré `PromptAssistantManager` comme service partagé (Qt-free, Option C long terme), en ne câblant qu'un seul consommateur : `InferencePage`. Un audit de priorisation post-Mission 031 a confirmé que le second consommateur prévu, `PromptsPage`, ne nécessite aucune dépendance manquante — toutes les fondations sont déjà en place et réutilisables sans modification.

## 2. Objectif

1. Intégrer le `PromptAssistantManager` déjà existant dans `PromptsPage`, sans en créer un second.
2. Reproduire la distinction Créer/Améliorer, adaptée à l'état réel de `PromptsPage` (gating sur la sélection d'un Prompt, pas sur la simple présence de texte dans l'éditeur).
3. Utiliser le texte **actuellement visible** dans l'éditeur (édité ou non, sauvegardé ou non) comme base du mode Améliorer.
4. Ne jamais persister automatiquement le résultat — l'utilisateur reste seul décideur via « Enregistrer le texte » déjà existant.
5. Ne pas implémenter `Prompts → Envoyer vers Inference`.

## 3. Architecture retenue

```
InferencePage ─┐
                ├→ PromptAssistantManager → AIBackend (OllamaEngine) → Ollama
PromptsPage ───┘
```

Instance unique, construite une fois dans `MainWindow.__init__()` (inchangé depuis Mission 031), désormais injectée dans les deux Pages. Aucune connaissance d'`OllamaEngine`/`urllib` dans `PromptsPage` — vérifié par le test architectural Mission 031 (`test_inference_page_and_prompts_page_never_import_ollamaengine_or_urllib`), qui couvrait déjà `prompts_page.py` par prévention et reste vert sans modification de sa logique.

## 4. Fonctionnalités livrées

Nouveau bouton **« Assistant IA »** dans `PromptsPage`, toujours activé, ouvrant `PromptAssistantDialog` (Mission 031, réutilisé **sans aucune modification**) :

- **Aucun Prompt sélectionné** : `existing_prompt=""` transmis au dialogue, quel que soit le contenu de `text_edit` (un texte libre non sauvegardé sans sélection est explicitement ignoré) — seul le mode **Créer** est proposé.
- **Prompt sélectionné** : `existing_prompt` = texte **actuellement visible** dans `text_edit` au moment de l'ouverture, jamais rechargé depuis le Domain `Prompt` persisté — un texte modifié manuellement mais non sauvegardé sert donc de base au mode **Améliorer**.
- **« Utiliser ce texte »** remplace le contenu de `text_edit`. Aucun appel `PromptManager.update_text()`/sauvegarde automatique. La persistance reste exclusivement gouvernée par le bouton existant **« Enregistrer le texte »**, strictement inchangé.

## 5. Audit pré-implémentation — points vérifiés

1. **Règle Créer/Améliorer vs état réel de `PromptsPage`** : `text_edit` n'est jamais désactivé, y compris sans Prompt sélectionné — un gating naïf sur la simple présence de texte (calque direct d'`InferencePage`) aurait permis au mode Améliorer d'apparaître à tort avec du texte libre non sauvegardé et aucune sélection. Résolu par un calcul explicite au point d'appel (`prompt_manager.active_prompt_id is not None` détermine `existing_prompt`), sans toucher `PromptAssistantDialog`.
2. **Réutilisabilité du dialogue** : confirmée intégrale par lecture complète du fichier — API générique (`prompt_assistant_manager`, `existing_prompt`, `parent`), `existing_prompt` capturé une seule fois à la construction (jamais relu dynamiquement, ce qui correspond exactement au besoin : l'éditeur `PromptsPage` ne peut de toute façon pas être modifié pendant que le dialogue modal est ouvert), résultat exposé via `result_text`. **Aucune modification apportée à `prompt_assistant_dialog.py`.**
3. **Injection du Manager** : `PromptAssistantManager` déjà construit dans `MainWindow.__init__()` avant `PromptsPage(...)` — extension additive du constructeur (`prompt_manager, prompt_assistant_manager`), un seul site d'appel modifié (`main_window.py`). Un second site de construction existait dans `tests/integration/test_prompt_roundtrip.py`, également mis à jour.
4. **Comportement non sauvegardé (dette UX pré-existante)** : `PromptsPage.update_prompts()` réécrit déjà inconditionnellement `text_edit` sur plusieurs événements EventBus (`WORKSPACE_CREATED/OPENED/SAVED/CLOSED/RENAMED`, `CHARACTER_CREATED/SELECTED/DELETED`, `PROMPT_CREATED/SELECTED/DELETED`) — comportement antérieur à Mission 031/032, non lié au Prompt Assistant, non corrigé (aucun dirty-state introduit), enregistré comme besoin futur (voir `docs/PROJECT_CONTEXT.md`).

## 6. Périmètre IN

- `src/ui/pages/prompts_page.py` : constructeur étendu (`prompt_manager, prompt_assistant_manager`), bouton « Assistant IA », méthode `_on_assistant_clicked()`.
- `src/ui/main_window.py` : injection de l'instance `PromptAssistantManager` déjà construite.
- Tests correspondants (voir section 7).

## 7. Périmètre OUT (strict, explicitement différé)

`Prompts → Envoyer vers Inference` ; tout mécanisme cross-page (EventBus supplémentaire, navigation programmée) ; dirty-state/confirmation avant perte/autosave/restauration automatique dans `PromptsPage` ; Character Context ; Prompt Library structurée ; RAG ; embeddings ; tags de prompts ; recherche/analyse des anciens prompts ; auto-tagging IA ; correction de la sortie LLM bruitée de Markdown ; modification de `_build_combined_text()`/du contrat `PromptAssistantManager` ; modification du timeout/cold start/hot-reload Ollama ; tout changement à `InferencePage` au-delà de deux commentaires de documentation mis à jour pour rester factuellement exacts (voir section 9).

## 8. Stratégie de tests et résultat

**597/597 tests automatisés verts** (589 précédents + 8 nets nouveaux), entièrement mockés côté Assistant — aucune requête réseau réelle, aucune boîte modale réelle. Suite complète exécutée une seule fois, ~104 secondes.

- `tests/integration/test_prompt_roundtrip.py` (+8) :
  - `PromptRoundTripTest` (+1) : `test_assistant_result_does_not_persist_until_explicit_save` — test de bout en bout avec `WorkspaceManager`/`CharacterManager`/`PromptManager` réels (`PromptAssistantDialog` mocké) : un texte édité manuellement mais non sauvegardé est bien transmis comme `existing_prompt`, le résultat de l'Assistant remplace l'éditeur sans toucher au `Prompt` Domain, la sauvegarde explicite existante reste ensuite pleinement fonctionnelle.
  - `PromptsPagePromptAssistantTest` (7, nouvelle classe standalone — calque du choix déjà fait pour `InferencePagePromptAssistantTest`, Managers mockés, jamais une sous-classe de `PromptRoundTripTest`) : bouton toujours présent/activé ; aucun Prompt actif → `existing_prompt=""` même avec du texte libre non sauvegardé dans l'éditeur ; Prompt actif → `existing_prompt` = texte actuellement affiché, jamais relu depuis `PromptManager.active_prompt` ; résultat « Utiliser ce texte » remplace l'éditeur sans appeler `update_text()`/`create()` ; annulation du dialogue laisse l'éditeur inchangé ; non-régression de « Enregistrer le texte ».
- `tests/integration/test_inference_page.py` : aucune régression (71/71), commentaire du test architectural existant mis à jour pour refléter que `PromptsPage` est désormais un consommateur réel (pas seulement une couverture préventive) — comportement du test inchangé.

## 9. Fichiers concernés

**Modifiés** : `src/ui/pages/prompts_page.py`, `src/ui/main_window.py`, `tests/integration/test_prompt_roundtrip.py`, `tests/integration/test_inference_page.py` (commentaire uniquement), `src/ui/pages/inference_page.py` (commentaire uniquement — référence à jour à « PromptsPage devenue second consommateur en Mission 032 »).

**Non modifiés** : `src/managers/prompt_assistant_manager.py`, `src/ui/prompt_assistant_worker.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `src/managers/prompt_manager.py`, `src/domain/prompt.py`, `src/engines/ai_backend.py`, `src/engines/ollama_engine.py`.

## 10. Besoins futurs enregistrés pendant cette mission (non implémentés)

Voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés", pour le détail complet — rattachés aux besoins déjà existants (Assistant IA/LLM, Prompt Library structurée, RAG local dérivé), pas créés comme besoins autonomes :

- Assistant IA capable de s'inspirer explicitement des anciens prompts pertinents (sur commande, jamais l'historique complet), via une future Prompt Library filtrée par tags/recherche sémantique.
- Utilisation sur commande de la future fiche d'identité canonique du personnage par le Prompt Assistant, avec la règle d'autorité **Identité canonique > demande actuelle > mémoire/anciens prompts/RAG**.
- Tags structurés (style/ambiance, cadrage, pose, vêtements, décor, éclairage, optique) et tags personnalisés pour la future Prompt Library, y compris une possibilité future de proposition automatique de tags par l'IA.
- Séparation architecturale à préserver : les tags d'un ancien prompt décrivent ce prompt, jamais l'identité canonique du personnage.

De plus, la dette UX identifiée pendant l'audit (section 5, point 4) — perte silencieuse d'un texte non sauvegardé dans `PromptsPage.text_edit` lors de certains événements EventBus déclenchés ailleurs dans l'application — est également enregistrée comme besoin futur distinct, **confirmée non régressive par le smoke test réel** (section 11).

**Observation UX supplémentaire enregistrée pendant le smoke test réel (non bloquante, non implémentée)** : `create_mode_button`/`improve_mode_button` (`PromptAssistantDialog`, Mission 031, partagé sans modification par `InferencePage` et `PromptsPage`) sont deux `QPushButton` ordinaires visuellement indiscernables de boutons d'action, alors qu'ils fonctionnent comme un sélecteur de mode — cliquer sur le mode déjà actif ne produit aucun changement visible, ce qui peut momentanément laisser croire à un dysfonctionnement. Besoin futur enregistré : rendre le choix Créer/Améliorer plus explicitement identifiable comme une sélection de mode (onglets, boutons radio, ou état actif visuellement plus marqué) — solution UI non tranchée, aucune modification apportée à `PromptAssistantDialog` par Mission 032. Voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés".

## 11. Smoke test manuel réel — résultat

**PASS.** Exécuté par l'architecte dans l'application réelle, avec appels Ollama réels.

| # | Étape | Résultat |
|---|---|---|
| 1 | Ouverture de l'Assistant IA depuis `PromptsPage`, dialogue utilisable | PASS |
| 2 | Mode Créer (aucun Prompt actif), génération réelle via Ollama | PASS |
| 3 | Mode Améliorer disponible avec un texte de base, aperçu « Prompt actuel utilisé comme base » correctement affiché | PASS |
| 4 | Changement de mode Créer ↔ Améliorer fonctionnel dans les deux sens | PASS (voir observation UX ci-dessus, non bloquante) |
| 5 | Texte courant repris comme base en mode Améliorer | PASS |
| 6 | Appels réels Ollama (génération et amélioration) | PASS |
| 7 | Utilisation du résultat proposé (« Utiliser ce texte ») | PASS |
| 8 | Sauvegarde via « Enregistrer le texte » après usage de l'Assistant | PASS |
| 9 | Absence du bouton « Envoyer vers Inference » depuis `PromptsPage` | PASS (conforme — hors périmètre Mission 032, confirmé) |

Vérifications complémentaires explicitement confirmées PASS : aucune persistance automatique après « Utiliser ce texte » (le `Prompt` Domain n'est modifié qu'après « Enregistrer le texte » explicite) ; le mode Améliorer utilise bien le texte **actuellement visible** dans l'éditeur, y compris une modification manuelle non sauvegardée, jamais l'ancienne version persistée ; persistance confirmée après rechargement suite à une sauvegarde explicite ; annulation du dialogue (« Annuler ») laisse l'éditeur inchangé ; cas d'erreur Ollama testé sans crash ni gel, UI/dialogue réutilisables après acquittement du message. La dette UX préexistante (perte de texte non sauvegardé sur certains événements `PromptsPage`) n'a pas été constatée comme régression de Mission 032 et reste hors périmètre, conformément à l'audit pré-implémentation.

## 12. Critères d'acceptation

- Aucun second `PromptAssistantManager`, aucune instance `OllamaEngine` supplémentaire. ✅ (vérifié par lecture de `main_window.py`, test architectural, confirmé en usage réel)
- Aucun Prompt sélectionné → seul le mode Créer disponible, y compris avec du texte libre non sauvegardé dans l'éditeur. ✅ (test dédié + smoke test réel)
- Prompt sélectionné → Créer et Améliorer disponibles, Améliorer basé sur le texte actuellement visible. ✅ (test dédié + smoke test réel, y compris avec modification manuelle non sauvegardée)
- « Utiliser ce texte » ne déclenche aucune sauvegarde automatique. ✅ (test dédié, Manager réel + smoke test réel)
- « Enregistrer le texte » reste l'unique mécanisme de persistance, strictement inchangé. ✅ (test de non-régression + smoke test réel)
- `Prompts → Envoyer vers Inference` non implémenté. ✅ (confirmé par smoke test réel — bouton absent)
- Aucune régression sur `PromptsPage`/`InferencePage`/`PromptManager` existants. ✅ (597/597 + smoke test réel)
- Smoke test manuel réel : ✅ **PASS** (section 11).

## État final

**Implémentation, suite automatisée complète (597/597) et smoke test manuel réel complet tous validés — PASS.** Une observation UX non bloquante (clarté du sélecteur de mode Créer/Améliorer) a été enregistrée comme besoin futur (section 10), ainsi que la confirmation que la dette UX préexistante de `PromptsPage` n'est pas une régression de cette mission. **Clôture Git restant à faire** — aucun commit, tag ou Release créés à ce stade, en attente de validation explicite de l'architecte.
