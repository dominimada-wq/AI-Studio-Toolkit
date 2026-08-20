# Changelog

Toutes les évolutions notables du projet **AI Studio Toolkit** sont documentées dans ce fichier.

## Sommaire

- **Mission 036 — Distinguish no open project from no principal character in warnings**
  - [Résumé (Mission 036)](#résumé-mission-036)
  - [Tests ajoutés (Mission 036)](#tests-ajoutés-mission-036)
  - [État du projet (Mission 036)](#état-du-projet-mission-036)
- **Mission 035 — Enregistrer comme nouveau Prompt… depuis un brouillon libre**
  - [Résumé (Mission 035)](#résumé-mission-035)
  - [Tests ajoutés (Mission 035)](#tests-ajoutés-mission-035)
  - [État du projet (Mission 035)](#état-du-projet-mission-035)
- **Mission 034 — Character Context minimal pour le Prompt Assistant**
  - [Résumé (Mission 034)](#résumé-mission-034)
  - [Tests ajoutés (Mission 034)](#tests-ajoutés-mission-034)
  - [État du projet (Mission 034)](#état-du-projet-mission-034)
- **Mission 033 — Prompts → Envoyer vers Inference**
  - [Résumé (Mission 033)](#résumé-mission-033)
  - [Tests ajoutés (Mission 033)](#tests-ajoutés-mission-033)
  - [État du projet (Mission 033)](#état-du-projet-mission-033)
- **Mission 032 — Prompt Assistant dans PromptsPage**
  - [Résumé (Mission 032)](#résumé-mission-032)
  - [Tests ajoutés (Mission 032)](#tests-ajoutés-mission-032)
  - [État du projet (Mission 032)](#état-du-projet-mission-032)
- **Mission 031 — Prompt Assistant Minimal (Inference)**
  - [Résumé (Mission 031)](#résumé-mission-031)
  - [Tests ajoutés (Mission 031)](#tests-ajoutés-mission-031)
  - [État du projet (Mission 031)](#état-du-projet-mission-031)
- **Mission 030 — Ollama Local AI Backend**
  - [Résumé (Mission 030)](#résumé-mission-030)
  - [Tests ajoutés (Mission 030)](#tests-ajoutés-mission-030)
  - [État du projet (Mission 030)](#état-du-projet-mission-030)
- **Mission 029 — Principal Character Consistency (LoRA / Prompts / Training)**
  - [Résumé (Mission 029)](#résumé-mission-029)
  - [Tests ajoutés (Mission 029)](#tests-ajoutés-mission-029)
  - [État du projet (Mission 029)](#état-du-projet-mission-029)
- **Mission 028 — Import Images into Workspace**
  - [Résumé (Mission 028)](#résumé-mission-028)
  - [Tests ajoutés (Mission 028)](#tests-ajoutés-mission-028)
  - [État du projet (Mission 028)](#état-du-projet-mission-028)
- **Mission 027 — Project Rename**
  - [Résumé (Mission 027)](#résumé-mission-027)
  - [Tests ajoutés (Mission 027)](#tests-ajoutés-mission-027)
  - [État du projet (Mission 027)](#état-du-projet-mission-027)
- **Mission 026 — Character Identity Foundation**
  - [Résumé (Mission 026)](#résumé-mission-026)
  - [Tests ajoutés (Mission 026)](#tests-ajoutés-mission-026)
  - [État du projet (Mission 026)](#état-du-projet-mission-026)
- **Mission 025 — ComfyUI Checkpoint Discovery & Selection**
  - [Résumé (Mission 025)](#résumé-mission-025)
  - [Tests ajoutés (Mission 025)](#tests-ajoutés-mission-025)
  - [État du projet (Mission 025)](#état-du-projet-mission-025)
- **Mission 024 — Réglage utilisateur de la force img2img**
  - [Résumé (Mission 024)](#résumé-mission-024)
  - [Tests ajoutés (Mission 024)](#tests-ajoutés-mission-024)
  - [État du projet (Mission 024)](#état-du-projet-mission-024)
- **Mission 023 — ComfyUI Img2Img Reference Workflow**
  - [Résumé (Mission 023)](#résumé-mission-023)
  - [Tests ajoutés (Mission 023)](#tests-ajoutés-mission-023)
  - [État du projet (Mission 023)](#état-du-projet-mission-023)
- **Mission 022 — Reference Image Transport Wiring**
  - [Résumé (Mission 022)](#résumé-mission-022)
  - [Tests ajoutés (Mission 022)](#tests-ajoutés-mission-022)
  - [État du projet (Mission 022)](#état-du-projet-mission-022)
- **Mission 021 — ComfyUI Image Upload**
  - [Résumé (Mission 021)](#résumé-mission-021)
  - [Tests ajoutés (Mission 021)](#tests-ajoutés-mission-021)
  - [État du projet (Mission 021)](#état-du-projet-mission-021)
- **Mission 020 — MainToolBar Actions Wiring**
  - [Résumé (Mission 020)](#résumé-mission-020)
  - [Tests ajoutés (Mission 020)](#tests-ajoutés-mission-020)
  - [État du projet (Mission 020)](#état-du-projet-mission-020)
- **Mission 019 — Images Gallery / Thumbnails**
  - [Résumé (Mission 019)](#résumé-mission-019)
  - [Tests ajoutés (Mission 019)](#tests-ajoutés-mission-019)
  - [État du projet (Mission 019)](#état-du-projet-mission-019)
- **Mission 018 — ComfyUI Application Settings**
  - [Résumé (Mission 018)](#résumé-mission-018)
  - [Tests ajoutés (Mission 018)](#tests-ajoutés-mission-018)
  - [État du projet (Mission 018)](#état-du-projet-mission-018)
- **Mission 017 — Dashboard Actions Wiring**
  - [Résumé (Mission 017)](#résumé-mission-017)
  - [Tests ajoutés (Mission 017)](#tests-ajoutés-mission-017)
  - [État du projet (Mission 017)](#état-du-projet-mission-017)
- **Mission 016 — Direct Project Folder Creation**
  - [Résumé (Mission 016)](#résumé-mission-016)
  - [Tests ajoutés (Mission 016)](#tests-ajoutés-mission-016)
  - [État du projet (Mission 016)](#état-du-projet-mission-016)
- **Mission 015 — Enlarged Image Preview**
  - [Résumé (Mission 015)](#résumé-mission-015)
  - [Statistiques (Mission 015)](#statistiques-mission-015)
  - [Évolutions architecturales (Mission 015)](#évolutions-architecturales-mission-015)
  - [Décisions de conception (Mission 015)](#décisions-de-conception-mission-015)
  - [Correction en revue finale (Mission 015)](#correction-en-revue-finale-mission-015)
  - [Hors périmètre (Mission 015)](#hors-périmètre-mission-015)
  - [Tests ajoutés (Mission 015)](#tests-ajoutés-mission-015)
  - [Prochaines étapes (Mission 015)](#prochaines-étapes-mission-015)
  - [État du projet (Mission 015)](#état-du-projet-mission-015)
- **Mission 014 — Validation post-génération avant enregistrement**
  - [Résumé (Mission 014)](#résumé-mission-014)
  - [Statistiques (Mission 014)](#statistiques-mission-014)
  - [Évolutions architecturales (Mission 014)](#évolutions-architecturales-mission-014)
  - [Décisions de conception (Mission 014)](#décisions-de-conception-mission-014)
  - [Correction en revue finale (Mission 014)](#correction-en-revue-finale-mission-014)
  - [Hors périmètre (Mission 014)](#hors-périmètre-mission-014)
  - [Tests ajoutés (Mission 014)](#tests-ajoutés-mission-014)
  - [Prochaines étapes (Mission 014)](#prochaines-étapes-mission-014)
  - [État du projet (Mission 014)](#état-du-projet-mission-014)
- **Mission 013 — Verticale minimale Inference**
  - [Résumé (Mission 013)](#résumé-mission-013)
  - [Statistiques (Mission 013)](#statistiques-mission-013)
  - [Évolutions architecturales (Mission 013)](#évolutions-architecturales-mission-013)
  - [Décisions de conception (Mission 013)](#décisions-de-conception-mission-013)
  - [Correction en revue finale (Mission 013)](#correction-en-revue-finale-mission-013)
  - [Hors périmètre (Mission 013)](#hors-périmètre-mission-013)
  - [Tests ajoutés (Mission 013)](#tests-ajoutés-mission-013)
  - [Prochaines étapes (Mission 013)](#prochaines-étapes-mission-013)
  - [État du projet (Mission 013)](#état-du-projet-mission-013)
- **Mission 012 — ComfyUI Engine minimal**
  - [Résumé (Mission 012)](#résumé-mission-012)
  - [Statistiques (Mission 012)](#statistiques-mission-012)
  - [Évolutions architecturales (Mission 012)](#évolutions-architecturales-mission-012)
  - [Décisions de conception (Mission 012)](#décisions-de-conception-mission-012)
  - [Correction en revue finale (Mission 012)](#correction-en-revue-finale-mission-012)
  - [Hors périmètre (Mission 012)](#hors-périmètre-mission-012)
  - [Tests ajoutés (Mission 012)](#tests-ajoutés-mission-012)
  - [Prochaines étapes (Mission 012)](#prochaines-étapes-mission-012)
  - [État du projet (Mission 012)](#état-du-projet-mission-012)
- **Mission 011 — Image Domain**
  - [Résumé (Mission 011)](#résumé-mission-011)
  - [Statistiques (Mission 011)](#statistiques-mission-011)
  - [Évolutions architecturales (Mission 011)](#évolutions-architecturales-mission-011)
  - [Décisions de conception (Mission 011)](#décisions-de-conception-mission-011)
  - [Correction en revue finale (Mission 011)](#correction-en-revue-finale-mission-011)
  - [Hors périmètre (Mission 011)](#hors-périmètre-mission-011)
  - [Tests ajoutés (Mission 011)](#tests-ajoutés-mission-011)
  - [Prochaines étapes (Mission 011)](#prochaines-étapes-mission-011)
  - [État du projet (Mission 011)](#état-du-projet-mission-011)
- **Mission 010 — Application Settings Domain**
  - [Résumé (Mission 010)](#résumé-mission-010)
  - [Statistiques (Mission 010)](#statistiques-mission-010)
  - [Évolutions architecturales (Mission 010)](#évolutions-architecturales-mission-010)
  - [Décisions de conception (Mission 010)](#décisions-de-conception-mission-010)
  - [Hors périmètre (Mission 010)](#hors-périmètre-mission-010)
  - [Tests ajoutés (Mission 010)](#tests-ajoutés-mission-010)
  - [Prochaines étapes (Mission 010)](#prochaines-étapes-mission-010)
  - [État du projet (Mission 010)](#état-du-projet-mission-010)
- **Mission 009 — Settings Domain (Workspace)**
  - [Résumé (Mission 009)](#résumé-mission-009)
  - [Statistiques (Mission 009)](#statistiques-mission-009)
  - [Évolutions architecturales (Mission 009)](#évolutions-architecturales-mission-009)
  - [Décisions de conception (Mission 009)](#décisions-de-conception-mission-009)
  - [Hors périmètre (Mission 009)](#hors-périmètre-mission-009)
  - [Tests ajoutés (Mission 009)](#tests-ajoutés-mission-009)
  - [Prochaines étapes (Mission 009)](#prochaines-étapes-mission-009)
  - [État du projet (Mission 009)](#état-du-projet-mission-009)
- **Mission 008 — Training Domain**
  - [Résumé (Mission 008)](#résumé-mission-008)
  - [Statistiques (Mission 008)](#statistiques-mission-008)
  - [Évolutions architecturales (Mission 008)](#évolutions-architecturales-mission-008)
  - [Décisions de conception (Mission 008)](#décisions-de-conception-mission-008)
  - [Hors périmètre (Mission 008)](#hors-périmètre-mission-008)
  - [Tests ajoutés (Mission 008)](#tests-ajoutés-mission-008)
  - [Prochaines étapes (Mission 008)](#prochaines-étapes-mission-008)
  - [État du projet (Mission 008)](#état-du-projet-mission-008)
- **Mission 007 — Workflow Domain**
  - [Résumé (Mission 007)](#résumé-mission-007)
  - [Statistiques (Mission 007)](#statistiques-mission-007)
  - [Évolutions architecturales (Mission 007)](#évolutions-architecturales-mission-007)
  - [Décisions de conception (Mission 007)](#décisions-de-conception-mission-007)
  - [Tests ajoutés (Mission 007)](#tests-ajoutés-mission-007)
  - [Prochaines étapes (Mission 007)](#prochaines-étapes-mission-007)
  - [État du projet (Mission 007)](#état-du-projet-mission-007)
- **Mission 006 — Model Domain**
  - [Résumé (Mission 006)](#résumé-mission-006)
  - [Statistiques (Mission 006)](#statistiques-mission-006)
  - [Évolutions architecturales (Mission 006)](#évolutions-architecturales-mission-006)
  - [Décisions de conception (Mission 006)](#décisions-de-conception-mission-006)
  - [Tests ajoutés (Mission 006)](#tests-ajoutés-mission-006)
  - [Prochaines étapes (Mission 006)](#prochaines-étapes-mission-006)
  - [État du projet (Mission 006)](#état-du-projet-mission-006)
- **Mission 005 — Prompt Domain**
  - [Résumé (Mission 005)](#résumé-mission-005)
  - [Statistiques (Mission 005)](#statistiques-mission-005)
  - [Évolutions architecturales (Mission 005)](#évolutions-architecturales-mission-005)
  - [Décisions de conception (Mission 005)](#décisions-de-conception-mission-005)
  - [Tests ajoutés (Mission 005)](#tests-ajoutés-mission-005)
  - [Prochaines étapes (Mission 005)](#prochaines-étapes-mission-005)
  - [État du projet (Mission 005)](#état-du-projet-mission-005)
- **Mission 004 — LoRA Domain**
  - [Résumé (Mission 004)](#résumé-mission-004)
  - [Statistiques (Mission 004)](#statistiques-mission-004)
  - [Évolutions architecturales (Mission 004)](#évolutions-architecturales-mission-004)
  - [Décisions de conception (Mission 004)](#décisions-de-conception-mission-004)
  - [Tests ajoutés (Mission 004)](#tests-ajoutés-mission-004)
  - [Prochaines étapes (Mission 004)](#prochaines-étapes-mission-004)
  - [État du projet (Mission 004)](#état-du-projet-mission-004)
- **Mission 003 — Dataset Domain**
  - [Résumé (Mission 003)](#résumé-mission-003)
  - [Statistiques (Mission 003)](#statistiques-mission-003)
  - [Évolutions architecturales (Mission 003)](#évolutions-architecturales-mission-003)
  - [Décisions de conception (Mission 003)](#décisions-de-conception-mission-003)
  - [Tests ajoutés (Mission 003)](#tests-ajoutés-mission-003)
  - [Prochaines étapes (Mission 003)](#prochaines-étapes-mission-003)
  - [État du projet (Mission 003)](#état-du-projet-mission-003)
- **Mission 002 — Character Domain**
  - [Résumé (Mission 002)](#résumé-mission-002)
  - [Statistiques (Mission 002)](#statistiques-mission-002)
  - [Évolutions architecturales (Mission 002)](#évolutions-architecturales-mission-002)
  - [Décisions de conception (Mission 002)](#décisions-de-conception-mission-002)
  - [Tests ajoutés (Mission 002)](#tests-ajoutés-mission-002)
  - [Prochaines étapes](#prochaines-étapes)
  - [État du projet (Mission 002)](#état-du-projet-mission-002)
- **Mission 001 — Blueprint Refactoring**
  - [Résumé de la mission](#résumé-de-la-mission)
  - [Statistiques de la mission](#statistiques-de-la-mission)
  - [Évolutions architecturales principales](#évolutions-architecturales-principales)
  - [Bugs corrigés](#bugs-corrigés)
  - [Tests ajoutés](#tests-ajoutés)
  - [Prochaines étapes (Mission 002)](#prochaines-étapes-mission-002)
  - [Améliorations UX futures](#améliorations-ux-futures)
  - [État du projet](#état-du-projet)

---

## v0.2-mission036 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 036 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 036)

**Mission 036 — Distinguish no open project from no principal character in warnings.** Referme la dette UX transversale enregistrée pendant le smoke test manuel réel de Mission 035 : plusieurs messages affichaient « Aucun personnage » aussi bien lorsqu'aucun projet n'était ouvert que lorsqu'un Workspace existait sans personnage principal.

Sept emplacements (`CharactersPage.save_identity()`, `PromptsPage.create_prompt()`/`save_as_new_prompt()`, `DatasetsPage.create_dataset()`, `LoRAPage.create_lora()`, `TrainingPage.create_training()`, `InferencePage._on_save_prompt_clicked()`) distinguent désormais correctement les deux causes : « Aucun projet ouvert » (nouveau message, demandant d'ouvrir ou créer un projet) lorsqu'aucun Workspace n'est ouvert, contre le message « Aucun personnage »/« Aucun personnage sélectionné » existant — texte inchangé — lorsqu'un Workspace est réellement ouvert sans personnage principal.

Après un réexamen architectural explicite comparant deux options, `WorkspaceManager` est **injecté directement** dans les constructeurs de `CharactersPage`, `DatasetsPage`, `LoRAPage`, `PromptsPage` et `TrainingPage` (Option A) plutôt que d'ajouter une propriété `workspace_opened` dupliquée sur les cinq Managers métier concernés (Option C, explicitement écartée pour préserver `WorkspaceManager.opened` comme source d'autorité unique). `InferencePage` réutilise sa dépendance `WorkspaceManager` déjà existante depuis Mission 013, sans aucun changement de constructeur. **Aucun contrat Manager modifié** — `create()`/`update()`/`principal_character`/EventBus/Domain/persistance strictement inchangés. `CharactersPage.create_character()` reste inchangé, déjà correct.

Le smoke test manuel réel a également clarifié un invariant déjà réel de l'application : un Workspace ouvert possède toujours un Character principal auto-créé (Mission 026) — l'état « Workspace ouvert sans personnage principal » reste donc un cas technique/défensif couvert par les tests automatisés, pas un scénario utilisateur normalement atteignable. Une ambiguïté distincte a été confirmée et volontairement laissée hors périmètre : `TrainingPage.create_training()` peut afficher « Aucun dataset disponible » avant même d'atteindre la branche « Aucun personnage » lorsqu'aucun Workspace n'est ouvert.

### Tests ajoutés (Mission 036)

- `test_character_roundtrip.py` (+1) : `test_save_identity_without_open_workspace_shows_no_project_warning`, plus un test existant renforcé d'une assertion exacte de message.
- `test_dataset_roundtrip.py`/`test_lora_roundtrip.py` (+2 chacun) : un test par cause (aucun Workspace ouvert / Workspace ouvert sans personnage), assertions exactes de titre et de texte.
- `test_prompt_roundtrip.py` (+3) : couverture de `create_prompt()` et `save_as_new_prompt()`.
- `test_training_roundtrip.py` (+2) : `dataset_manager` mocké pour isoler la branche « Aucun personnage » de `create_training()`, normalement non atteignable en usage réel.
- `test_inference_page.py` (+1 nouveau, +1 existant renforcé).
- **678/678 tests verts** au total (667 précédents + 11 nets nouveaux), aucune régression détectée, suite ciblée (8 fichiers concernés) : 228/228 OK.
- **Smoke test manuel réel complet, PASS** — voir `docs/missions/MISSION_036.md` pour le détail complet.

### État du projet (Mission 036)

`WorkspaceManager.opened` reste la seule source d'autorité pour l'état du Workspace. Aucun Manager métier n'expose de propriété `workspace_opened`. La dette UX transversale documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'ambiguïté « Aucun personnage » est désormais **résolue**. Une nouvelle dette distincte (`TrainingPage → « Aucun dataset disponible »`) a été enregistrée, non traitée. L'invariant « Workspace ouvert ⇒ Character principal » a été explicitement documenté dans `docs/PROJECT_CONTEXT.md`, section "Orientation architecturale validée", sans aucune modification du Domain. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `ebd49d5f451448802e2732de9e4da718cd735506` — `feat: distinguish no open project from no principal character in warnings`, tag `v0.2-mission036`, GitHub Release publiée).

---

## v0.2-mission035 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 035 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 035)

**Mission 035 — Enregistrer comme nouveau Prompt… depuis un brouillon libre.** Referme l'observation UX enregistrée pendant le smoke test manuel réel de Mission 034 : dans `PromptsPage`, sans Prompt sélectionné, l'Assistant IA restait utilisable en mode Créer et « Utiliser ce texte » plaçait correctement le résultat dans l'éditeur — mais aucun chemin clair n'existait ensuite pour l'enregistrer comme nouveau `Prompt`.

Nouveau bouton « Enregistrer comme nouveau Prompt… » dans `PromptsPage`, disponible avec ou sans Prompt actuellement actif. Réutilise intégralement `PromptManager.create(name, text="")`, introduit en Mission 031, **sans aucune modification de son contrat**. Avec un Prompt actif, celui-ci reste strictement intact (jamais lu ni modifié) et un second Prompt distinct est créé à partir du texte actuellement visible. Dans les deux cas, `PromptsPage` appelle explicitement `prompt_manager.select(prompt.prompt_id)` juste après la création — décision locale à cette Page, délibérément différente de la garantie testée de Mission 031 pour `InferencePage` (qui, elle, ne doit jamais sélectionner, pour ne pas perturber la sélection de `PromptsPage` depuis une autre Page) — afin que le rafraîchissement synchrone déclenché par `PROMPT_CREATED` n'efface pas visuellement l'éditeur alors que le texte vient d'être persisté avec succès.

Aucune sauvegarde implicite : ouvrir ou utiliser l'Assistant IA ne crée jamais de Prompt par lui-même — seul ce nouveau bouton, actionné explicitement, le fait. Aucune modification d'`InferencePage`, du Domain `Prompt`, ni d'aucune partie du Prompt Assistant (`PromptAssistantManager`/`PromptAssistantDialog`/`PromptAssistantWorker`).

**Explicitement hors périmètre** : dirty-state général de `PromptsPage`, propreté de la sortie du Prompt Assistant, sélecteur visuel Créer/Améliorer, Prompt Library, tags, RAG, vision, Character Context avancé, toute extension du Domain `Prompt`.

Une dette UX transversale préexistante et sans lien avec cette mission a été constatée pendant le smoke test manuel réel : plusieurs Pages (`Characters`, `Prompts`, `Datasets`, `LoRA`, `Training`, `Inference`) affichent un message ambigu « Aucun personnage » aussi bien lorsqu'aucun projet n'est ouvert que lorsqu'un Workspace existe sans personnage principal — enregistrée comme besoin futur, aucune décision architecturale de correction prise.

### Tests ajoutés (Mission 035)

- `tests/integration/test_prompt_roundtrip.py`, classe `PromptRoundTripTest` (+2, Managers/EventBus réels) : `test_save_as_new_prompt_without_active_prompt_creates_and_selects_it` (création + sélection explicite, éditeur affichant le même texte après le rafraîchissement synchrone) ; `test_save_as_new_prompt_with_active_prompt_leaves_original_untouched` (Prompt d'origine strictement intact, second Prompt distinct créé et sélectionné).
- Nouvelle classe `PromptsPageSaveAsNewPromptTest` (+10, Managers mockés, mirroir de `PromptsPageSendToInferenceTest`) — présence/activation du bouton, création avec `select()` sur l'id exact, `update_text()` jamais appelé avec un Prompt actif, annulation/nom vide → aucune création, aucun personnage principal → avertissement affiché et `select()` jamais appelé.
- **667/667 tests verts** au total (655 précédents + 12 nets nouveaux), aucune régression détectée, suite ciblée (`test_prompt_roundtrip.py`) : 40/40 OK.
- **Smoke test manuel réel complet, PASS** — voir `docs/missions/MISSION_035.md` pour le détail complet.

### État du projet (Mission 035)

`PromptManager.create(name, text="")` reste strictement inchangé, réutilisé sans extension. `src/domain/prompt.py` strictement inchangé. La dette UX documentée de `PromptsPage` (voir `docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés") concernant l'absence de chemin clair pour transformer un texte libre en nouveau Prompt est désormais **résolue**. Une nouvelle dette UX transversale (ambiguïté « aucun projet ouvert » / « aucun personnage ») a été enregistrée, non traitée. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `a2766b6063859db85ec87e49b9a372d51d6c1c6f` — `feat: add save-as-new-prompt action to PromptsPage`, tag `v0.2-mission035`, GitHub Release publiée).

---

## v0.2-mission034 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 034 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 034)

**Mission 034 — Character Context minimal pour le Prompt Assistant.** Livre une première matérialisation concrète et explicite de la hiérarchie d'autorité « Identité canonique > demande actuelle > mémoire/anciens prompts/RAG », en exploitant les champs d'identité `Character` déjà existants depuis Mission 026, restés jusqu'ici totalement inertes côté Prompt Assistant.

Nouveau DTO minimal et provider-neutral `CharacterContext` (`character_lock`/`trigger_token`/`description`/`personality` — `bio`/`interests` volontairement exclus), converti depuis `Character` par un unique point `CharacterContext.from_character()`, colocalisé avec `PromptAssistantManager` dans `prompt_assistant_manager.py` : `PromptAssistantManager` (la classe) ne référence jamais `Character`, seule cette classmethod le fait. `assist(request_text, existing_prompt="", character_context=None)` reste une extension strictement additive — sans contexte, le texte envoyé au backend reste byte-for-byte identique à avant cette mission. Avec un contexte, `_build_combined_text()` préfixe un bloc `[IDENTITÉ CANONIQUE DU PERSONNAGE — priorité absolue, ne jamais contredire]` (Character Lock et Trigger token en tête, Description/Personnalité conditionnels, aucune ligne de champ vide) avant le bloc `[DEMANDE ACTUELLE]` déjà existant.

`PromptAssistantDialog` reçoit un `CharacterContext | None` déjà résolu par l'appelant — il ne connaît ni `Character` ni `CharacterManager` — et propose une `QCheckBox` « Utiliser l'identité du personnage », créée uniquement si un contexte utilisable existe, toujours décochée par défaut (aucune injection automatique). L'identité est capturée en snapshot avant le lancement de l'appel asynchrone : `PromptAssistantWorker` ne reçoit jamais `Character`/`CharacterManager`, aucune résolution dynamique pendant l'exécution. `PromptsPage` et `InferencePage` gagnent chacune `character_manager` en dépendance constructeur et résolvent identiquement `CharacterContext.from_character(character_manager.principal_character)` au moment d'ouvrir le dialogue — fonctionnalité strictement identique depuis les deux Pages, aucune logique dupliquée.

**Explicitement hors périmètre** : `bio`/`interests` dans le contexte IA, nouveaux champs Character, références d'identité 1..N, planche d'identité, Identity LoRA, tags, Prompt Library, inspiration depuis anciens prompts, RAG, embeddings, vision/multimodal, image → analyse → prompt, Qwen3-VL, auto-tagging, correction générale de la sortie Markdown du LLM, injection automatique de l'identité.

### Tests ajoutés (Mission 034)

- `tests/integration/test_prompt_assistant_manager.py` (+20) — `CharacterContextFromCharacterTest` (Character complet/partiel/quatre champs vides/blancs uniquement espaces/`bio` et `interests` jamais lus/`None`→`None`), `PromptAssistantManagerNoContextRegressionTest` (texte backend strictement identique à avant Mission 034 sans contexte), `PromptAssistantManagerWithContextTest` (ordre identité puis demande, Character Lock/Trigger token en tête, champs conditionnels, aucune ligne vide), `PromptAssistantManagerCharacterDependencyArchitectureTest` (aucune annotation `Character` sur `assist()`/`_build_combined_text()`, aucun import Qt).
- `tests/integration/test_prompt_assistant_worker.py` (+2) — snapshot `character_context` transmis tel quel, défaut `None`.
- `tests/integration/test_prompt_assistant_dialog.py` (+8, nouvelle classe `PromptAssistantDialogIdentityCheckboxTest`) — case absente/présente selon le contexte, décochée par défaut, décochée → `None` transmis, cochée → contexte transmis, non-régression Créer/Améliorer, erreur backend toujours gérée sans boîte modale réelle.
- `tests/integration/test_prompt_roundtrip.py` (+3) et `tests/integration/test_inference_page.py` (+3) — résolution `CharacterContext.from_character(character_manager.principal_character)` identique dans les deux Pages (aucun Character → `None` ; identité présente → contexte résolu ; identité vide → `None`).
- **655/655 tests verts** au total (619 précédents + 36 nets nouveaux), aucune régression détectée, dernière exécution complète unique (suite ciblée des 5 fichiers concernés : 160/160 OK).
- **Smoke test manuel réel complet, PASS** — case présente/absente selon l'identité disponible, décochée par défaut, génération avec et sans identité fonctionnelle depuis `PromptsPage` et `InferencePage`, non-régression Créer/Améliorer et `Prompts → Envoyer vers Inference` — voir `docs/missions/MISSION_034.md` pour le détail complet.

### État du projet (Mission 034)

`src/domain/character.py` strictement inchangé (aucun nouveau champ). Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) voit son besoin Character Context recevoir une première brique minimale — reste ouvert (Character Context avancé, Prompt Library, RAG, vision, propreté de la sortie LLM). Une observation UX non bloquante a été enregistrée pendant le smoke test réel (absence de chemin clair pour transformer un texte libre en nouveau Prompt depuis `PromptsPage` sans Prompt actif — comportement préexistant, non introduit par cette mission), rattachée à la dette UX déjà documentée de `PromptsPage`. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `d10afb47ac88a94944ea8eb86bbbfc94c9332ba5` — `feat: add Character Context to Prompt Assistant`, tag `v0.2-mission034`, GitHub Release publiée).

---

## v0.2-mission033 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 033 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 033)

**Mission 033 — Prompts → Envoyer vers Inference.** Livre le sens `Prompts → Envoyer vers Inference`, resté explicitement hors périmètre de Mission 032, fermant la boucle utilisateur `Créer/sélectionner un Prompt → Assistant IA → édition → Envoyer vers Inference → génération`. `PromptsPage` gagne un bouton « Envoyer vers Inference », activé/désactivé dynamiquement selon le texte actuellement visible dans l'éditeur (indépendamment de tout Prompt sélectionné), émettant un signal Qt local `send_to_inference_requested` capté uniquement par `MainWindow`.

Architecture Option A (signal Qt + `MainWindow` médiateur) retenue plutôt qu'un événement `EventBus` : aucune mutation Domain n'a lieu dans ce flux, seulement une intention Presentation-layer, hors du contrat `"domaine.verbe"` déjà établi par l'`EventBus`. `PromptsPage` ne référence jamais `InferencePage`. Deux nouvelles méthodes publiques minimales sur `InferencePage` (`prompt_text()`/`set_prompt_text()`) évitent tout accès direct au `QTextEdit` interne depuis `MainWindow` ; nouvelle `Sidebar.select_page(name)` (recherche dans `self.pages` déjà existant) évite tout index numérique codé en dur pour la navigation.

Le texte transféré est exactement le texte actuellement visible dans l'éditeur, y compris une modification locale non sauvegardée, jamais relu depuis le Domain `Prompt`. Gestion de collision par **comparaison exacte de chaînes** (aucune normalisation d'espaces/casse) : Inference vide ou identique → transfert et navigation immédiats, sans confirmation ; texte différent → `QMessageBox` à boutons personnalisés `Remplacer`/`Annuler` (premier usage d'une confirmation dans la base, aucun précédent réutilisable identifié), bouton par défaut `Annuler`. Annulation : aucune modification d'aucune des deux pages, aucune navigation. Aucune sauvegarde implicite à aucun moment (`PromptManager.update_text()`/`create()`, `WorkspaceManager.save()` jamais appelés par ce flux) — « Envoyer vers Inference » reste une opération d'usage du texte, jamais une sauvegarde du Prompt.

**Explicitement hors périmètre** : Prompt Library, tags, inspiration depuis anciens prompts, Character Context/« Utiliser l'identité », RAG, vision/multimodal, dirty-state général de `PromptsPage`, retour automatique Inference → Prompts.

### Tests ajoutés (Mission 033)

- `tests/integration/test_prompt_roundtrip.py` (+8, nouvelle classe standalone `PromptsPageSendToInferenceTest`) — bouton présent, désactivé si éditeur vide/espaces uniquement, activé dès qu'un texte est présent y compris sans Prompt actif, désactivé de nouveau après effacement, signal émis avec le texte exact actuellement visible (y compris non sauvegardé), aucun appel `update_text()`/`create()`.
- `tests/integration/test_inference_page.py` (+3, `InferencePagePromptAssistantTest`) — `prompt_text()`/`set_prompt_text()` corrects, aucun effet de bord `PromptManager`.
- `tests/integration/test_sidebar.py` (3, nouveau fichier) — `select_page()` positionne la ligne correcte (dérivée de `self.pages`, jamais un littéral codé en dur), fonctionne pour la première page, nom inconnu → `False` sans déplacement.
- `tests/integration/test_main_window_prompts_to_inference.py` (8, nouveau fichier, même patron que `test_main_window_new_project.py`) — Inference vide/espaces → transfert immédiat sans confirmation ; texte identique (comparaison stricte) → aucune confirmation ; texte différent → confirmation affichée ; confirmation acceptée → remplacement + navigation ; confirmation annulée → aucun changement ni navigation ; aucun appel `PromptManager.update_text()`/`create()` ; aucun appel `WorkspaceManager.save()`. `QMessageBox` toujours entièrement mocké, aucune boîte modale réelle.
- **619/619 tests verts** au total (597 précédents + 22 nets nouveaux), aucune régression détectée, dernière exécution complète unique.
- **Smoke test manuel réel complet, PASS** — bouton correctement activé/désactivé, transfert fonctionnel avec et sans Prompt actif, texte non sauvegardé transféré tel quel, les trois cas de collision confirmés, `Annuler`/`Remplacer` tous deux confirmés, aucune sauvegarde implicite constatée, aucune régression du Prompt Assistant ni de la navigation/édition des prompts — voir `docs/missions/MISSION_033.md` pour le détail complet.

### État du projet (Mission 033)

`src/domain/prompt.py`, `src/managers/prompt_manager.py`, `src/managers/prompt_assistant_manager.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `src/core/event_bus.py` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) voit son sens `Prompts → Envoyer vers Inference` désormais livré — reste ouvert (Character Context, Prompt Library, RAG, vision, propreté de la sortie LLM). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `2ee53f71780bb638b5ec9bd5af0603fb8d8241a2` — `feat: add Prompts to Inference transfer`, tag `v0.2-mission033`, GitHub Release publiée).

---

## v0.2-mission032 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 032 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 032)

**Mission 032 — Prompt Assistant dans PromptsPage.** Second usage utilisateur réel du service `PromptAssistantManager` (Mission 031, Option C long terme confirmée), désormais partagé entre `InferencePage` et `PromptsPage` — même instance construite une seule fois au composition root, aucun second Manager/Worker/dialogue créé. `PromptsPage` gagne un bouton « Assistant IA » (toujours activé) ouvrant `PromptAssistantDialog` réutilisé **sans aucune modification**.

Aucun Prompt sélectionné → `existing_prompt=""` transmis au dialogue quel que soit le contenu de l'éditeur (un texte libre non sauvegardé sans sélection est explicitement ignoré) — seul le mode **Créer** est proposé. Prompt sélectionné → `existing_prompt` = texte **actuellement visible** dans `text_edit` au moment de l'ouverture, jamais rechargé depuis le Domain `Prompt` persisté — un texte modifié manuellement mais non sauvegardé sert donc de base au mode **Améliorer**, vérifié par audit pré-implémentation dédié (un gating naïf sur la simple présence de texte, calque direct d'`InferencePage`, aurait permis à tort le mode Améliorer sans aucune sélection).

« Utiliser ce texte » remplace uniquement le contenu de l'éditeur — aucun appel `PromptManager.update_text()`/sauvegarde automatique, la persistance restant exclusivement gouvernée par le bouton existant « Enregistrer le texte », strictement inchangé. `Prompts → Envoyer vers Inference` reste explicitement hors périmètre.

Deux besoins futurs enregistrés pendant le smoke test manuel réel : confirmation que la dette UX préexistante de `PromptsPage` (perte silencieuse d'un texte non sauvegardé sur certains événements EventBus déclenchés ailleurs dans l'application) n'est pas une régression de cette mission ; observation UX non bloquante sur la clarté visuelle du sélecteur de mode Créer/Améliorer (`PromptAssistantDialog`, partagé par les deux Pages) — deux boutons ordinaires visuellement indiscernables de boutons d'action alors qu'ils fonctionnent comme un sélecteur de mode, non implémentée cette mission.

### Tests ajoutés (Mission 032)

- `tests/integration/test_prompt_roundtrip.py` (+8, aucun nouveau fichier) :
  - `PromptRoundTripTest` (+1) — `test_assistant_result_does_not_persist_until_explicit_save` : test de bout en bout avec `WorkspaceManager`/`CharacterManager`/`PromptManager` réels (`PromptAssistantDialog` mocké), confirmant qu'un texte édité manuellement mais non sauvegardé est bien transmis comme `existing_prompt` et que le résultat de l'Assistant ne modifie jamais le `Prompt` Domain avant sauvegarde explicite.
  - `PromptsPagePromptAssistantTest` (7, nouvelle classe standalone, calque d'`InferencePagePromptAssistantTest`) — bouton toujours présent/activé ; aucun Prompt actif → `existing_prompt=""` même avec du texte libre non sauvegardé ; Prompt actif → `existing_prompt` = texte actuellement affiché, jamais relu depuis `PromptManager.active_prompt` ; « Utiliser ce texte » sans sauvegarde automatique ; annulation sans modification ; non-régression de « Enregistrer le texte ».
- `tests/integration/test_inference_page.py` : commentaire du test architectural existant mis à jour pour refléter `PromptsPage` comme second consommateur réel, comportement du test inchangé.
- **597/597 tests verts** au total (589 précédents + 8 nets nouveaux), aucune régression détectée, dernière exécution complète unique, ~104 s.
- **Smoke test manuel réel complet, PASS** — ouverture de l'Assistant depuis `PromptsPage`, mode Créer avec génération réelle via Ollama, mode Améliorer utilisant correctement le texte actuellement visible dans l'éditeur (y compris une modification manuelle non sauvegardée) comme base, « Utiliser ce texte », sauvegarde explicite via « Enregistrer le texte » et persistance confirmée après rechargement, annulation du dialogue sans modification, gestion propre d'un backend Ollama inaccessible sans crash ni gel, absence confirmée du bouton `Prompts → Envoyer vers Inference` — voir `docs/missions/MISSION_032.md` pour le détail complet.

### État du projet (Mission 032)

`src/managers/prompt_assistant_manager.py`, `src/ui/prompt_assistant_worker.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `src/managers/prompt_manager.py`, `src/domain/prompt.py`, `src/engines/ai_backend.py`, `src/engines/ollama_engine.py` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) reçoit son second usage utilisateur réel, dans `PromptsPage` — reste ouvert (`Prompts → Envoyer vers Inference`, Character Context, Prompt Library, RAG, vision, propreté de la sortie LLM). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `e21447786795abe6cd9e0af5ef9f3cb6b9d2d94e` — `feat: add Prompt Assistant to PromptsPage`, tag `v0.2-mission032`, GitHub Release publiée).

---

## v0.2-mission031 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 031 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 031)

**Mission 031 — Prompt Assistant Minimal (Inference).** Premier usage utilisateur réel du backend IA posé par Mission 030. `InferencePage` gagne une action « Assistant IA » ouvrant `PromptAssistantDialog` (nouveau, redimensionnable, 800×700 px par défaut, zones de texte extensibles priorisant le résultat proposé), présentant deux intentions explicites : **Créer** (à partir d'une demande utilisateur) et **Améliorer** (le prompt actuellement présent dans Inference affiché en lecture seule comme base avant tout envoi, jamais transmis silencieusement au backend). L'appel est exécuté hors du thread Qt principal via un nouveau `PromptAssistantWorker`/`QThread`, calque structurel exact de `GenerationWorker` (Mission 013) : interface réactive pendant l'appel, appel concurrent refusé, succès et erreur rétablissent tous deux correctement l'état de l'interface.

Nouveau `PromptAssistantManager` (Qt-free, même forme que `GenerationManager`) coordonne l'appel via l'abstraction `AIBackend` (Mission 030) — jamais `OllamaEngine` directement depuis l'UI, vérifié par test architectural couvrant `InferencePage` **et** `PromptsPage`. Construit une seule fois au composition root (`MainWindow`) depuis `ApplicationSettings.ollama_url`/`ollama_model_name`, sans aucun rechargement à chaud (même contrat que ComfyUI, confirmé par audit pré-implémentation dédié). Architecture long terme confirmée comme un service `PromptAssistantManager` partagé (Option C) — Mission 031 n'intègre volontairement que ce premier consommateur, `InferencePage` (Option B tactique), l'intégration `PromptsPage` restant une mission future.

« Utiliser ce texte » transfère le résultat proposé dans le prompt d'Inference ; bouton indépendant « Enregistrer dans Prompts » (nom obligatoire, doublons toujours autorisés) crée un `Prompt` persistant via une extension additive et rétrocompatible `PromptManager.create(name, text="")`, **sans jamais appeler `select()`** — le Prompt déjà actif dans `PromptsPage` n'est jamais modifié silencieusement (audit pré-implémentation dédié + test dédié).

Ajustement UX pendant le smoke test : dialogue agrandi (800×700, redimensionnable, zones extensibles), et correction d'un défaut de harness de tests (deux `QMessageBox` réelles bloquaient l'exécution automatisée — corrigé en les mockant, comportement applicatif inchangé). **Observation future enregistrée, non implémentée** : Ollama peut retourner du Markdown/une analyse autour du prompt proposé plutôt que le seul texte exploitable — besoin futur d'un contrat LLM plus strict, non traité cette mission.

### Tests ajoutés (Mission 031)

- `tests/integration/test_prompt_assistant_manager.py` (7, **nouveau fichier**) — intentions Créer/Améliorer, construction déterministe et testée du texte combiné envoyé au backend, `model_name` jamais codé en dur, normalisation `AIBackendError`/appel concurrent en une unique `PromptAssistantError`.
- `tests/integration/test_prompt_assistant_worker.py` (5, **nouveau fichier**) — calque exact de `test_generation_worker.py`, `QThread` réel, exécution hors thread principal prouvée.
- `tests/integration/test_prompt_assistant_dialog.py` (13, **nouveau fichier**) — modes Créer/Améliorer, aperçu du prompt existant affiché uniquement en mode Améliorer, appel non bloquant, boutons désactivés pendant l'appel, erreur gérée, handoff du résultat, taille initiale ≥800×700, redimensionnement réellement effectif, part d'étirement du résultat supérieure à celle de la demande ; `QMessageBox.warning`/`.critical` mockées dans les deux scénarios d'erreur (correction de harness post-smoke-test).
- `tests/integration/test_main_window_ollama_settings.py` (3, **nouveau fichier**) — calque exact de `test_main_window_comfyui_settings.py`, confirme explicitement l'absence de rechargement à chaud.
- `tests/integration/test_inference_page.py` (+11 nets) — boutons « Assistant IA »/« Enregistrer dans Prompts », garde de nom identique à `PromptsPage.create_prompt()`, absence de `select()`/`update_text()` depuis Inference, avertissement si aucun personnage principal, test architectural étendu anti-`OllamaEngine`/`urllib`.
- `tests/integration/test_prompt_roundtrip.py` (+1) — `create(name, text=...)` au niveau Manager réel confirmé sans effet sur `active_prompt_id` ni sur la sélection déjà affichée dans `PromptsPage`.
- **589/589 tests verts** au total (549 précédents + 40 nets nouveaux), aucune régression, dernière exécution complète unique sans intervention humaine ni boîte modale réelle (~104 s).
- **Smoke test manuel réel complet contre une instance Ollama réelle, PASS** — ouverture de l'Assistant, modes Créer/Améliorer, prompt actuel affiché comme base, génération réelle, récupération du résultat, « Utiliser ce texte », « Enregistrer dans Prompts » avec nom choisi par l'utilisateur, prompt visible dans `PromptsPage`, gestion propre d'un backend Ollama inaccessible sans crash, UI réutilisable après erreur, taille du dialogue validée visuellement — voir `docs/missions/MISSION_031.md` pour le détail complet.

### État du projet (Mission 031)

`src/domain/prompt.py`, `PromptsPage`, `src/engines/ai_backend.py`, `src/engines/ollama_engine.py` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) reçoit son premier usage utilisateur réel, dans `InferencePage` uniquement — reste ouvert (intégration `PromptsPage`, Character Context, Prompt Library, RAG, vision, propreté de la sortie LLM). La question architecturale d'articulation `PromptsPage`↔`InferencePage` est partiellement tranchée (Option B tactique, Option C confirmée long terme). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `1226342d808936f98673804eb654f6cc048103da` — `feat: add minimal AI Prompt Assistant for Inference`, tag `v0.2-mission031`, GitHub Release publiée).

---

## v0.2-mission030 — 2026-08-18

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 030 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction (contrairement au précédent "clôture Git en attente" de Missions 017/027/028/029, ici la clôture Git et la publication étaient déjà effectives avant que cette entrée CHANGELOG ne soit rédigée, un oubli comblé lors de cette régularisation ; le smoke test réel, initialement non confirmé lors d'une première passe de régularisation, a depuis été exécuté et son résultat est intégré ci-dessous).

### Résumé (Mission 030)

**Mission 030 — Ollama Local AI Backend.** Première fondation d'un assistant IA/LLM intégré à AI Studio Toolkit, avec Ollama comme premier backend concret. Nouvelle abstraction structurelle `AIBackend` (`src/engines/ai_backend.py`, `typing.Protocol` `@runtime_checkable`, deux méthodes — `list_models()`/`generate_text()` — plus `AIModelInfo`/`AIBackendError`), pour qu'aucune future fonctionnalité IA ne dépende directement d'un provider particulier — même séparation que `GenerationManager` maintient déjà vis-à-vis de `ComfyUIEngine`. `OllamaEngine` (`src/engines/ollama_engine.py`, nouveau, stdlib `urllib` uniquement, aucune nouvelle dépendance) implémente ce contrat sans en hériter, vérifié contre l'API Ollama réelle documentée : `GET /api/tags` pour la découverte des modèles (seul le nom de chaque modèle est retenu ; la capacité vision n'est pas exposée de façon fiable par cet endpoint — limite documentée, non résolue, `AIModelInfo` reste additif pour l'accueillir plus tard), `POST /api/generate` en mode non-streaming (`"stream": false`) pour la génération de texte — `POST /api/chat`, l'historique de conversation et tout usage vision restent explicitement hors périmètre.

`ApplicationSettings`/`ApplicationSettingsManager`/`SettingsPage` gagnent trois champs (`ollama_url`, `ollama_path`, `ollama_model_name`) suivant exactement le patron déjà établi par `comfyui_url`/`comfyui_path`/`comfyui_checkpoint_name` (Missions 010/018/025), y compris le bouton "Rafraîchir les modèles" et le repli systématique sur la saisie manuelle en cas d'échec — `ollama_path` stocké mais **non consommé par aucun code**, exactement comme `comfyui_path` depuis Mission 010. `ApplicationSettingsManager.update()` passe de 5 à 8 paramètres explicites, un signal concret renforçant le besoin déjà documenté de refonte Settings par provider, non traité cette mission.

**Aucun câblage vers `InferencePage`/`PromptsPage`/`CharactersPage`** — fondation seule, aucune fonctionnalité IA utilisateur finale, aucun contexte Character, aucun historique de prompts, aucune vision, aucun RAG, aucun provider cloud.

### Tests ajoutés (Mission 030)

- `tests/integration/test_ollama_engine.py` (19, **nouveau fichier**) — entièrement mocké, aucune requête réseau réelle : `list_models()` (plusieurs/un seul/zéro modèle, entrées malformées filtrées défensivement, `"models"` absent/non-liste → `AIBackendError`, endpoint `GET /api/tags` vérifié), `generate_text()` (réponse retournée telle quelle, corps de requête exact `model`/`prompt`/`stream: false`, `"response"` absent/non-`str` → `AIBackendError`, message d'erreur Ollama repris dans l'exception, deux appels indépendants sans état partagé), communication (serveur injoignable, JSON invalide, erreur HTTP), et un test architectural dédié confirmant que `OllamaEngine` satisfait structurellement `AIBackend` sans en hériter.
- `tests/integration/test_application_settings_roundtrip.py` (+1 net nouveau) — round-trip/défauts/idempotence `update()`/persistance étendus aux 3 nouveaux champs, nouveau test dédié `test_manager_loads_legacy_settings_file_without_ollama_fields` (un fichier antérieur à Mission 030 charge les défauts littéraux Ollama, pas des chaînes vides).
- `tests/integration/test_settings_page.py` (+14 nets nouveaux) — `SettingsPageOllamaDiscoveryTest`, miroir exact de la couverture ComfyUI existante appliquée au champ modèle Ollama et au bouton de rafraîchissement.
- **549/549 tests verts** au total (513 précédents + 36 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet contre une instance Ollama réelle, PASS** — machine NVIDIA Quadro P4000 (8 Go VRAM), 48 Go RAM, Intel Core i7-7920HQ, Ollama `0.32.14`, modèle `llama3.2:3b` (~2,0 Go) : installation, découverte depuis `SettingsPage` (`1 modèle(s) détecté(s).`), sélection, sauvegarde puis restauration fidèle après redémarrage complet, appel réel `OllamaEngine.generate_text()` hors UI (réponse texte réelle reçue), cas d'erreur URL invalide confirmé sans plantage (message de repli, saisie manuelle toujours disponible). Cas "zéro modèle détecté" non reproduit manuellement (pour ne pas supprimer le modèle installé) — reste couvert par la suite automatisée mockée. **Limite empirique découverte et documentée, non corrigée cette mission** : le tout premier appel `generate_text()` a expiré au bout du timeout par défaut d'`OllamaEngine` (30 s) — Ollama charge le modèle en mémoire/VRAM à la demande lors de sa première utilisation ("cold start"), une opération ayant dépassé 30 s sur cette machine avec ce modèle ; un appel identique suivant, modèle déjà chargé, a réussi immédiatement. Comportement propre à Ollama, pas un défaut du backend — voir `docs/missions/MISSION_030.md` section 13 pour le détail complet.

### État du projet (Mission 030)

Aucun fichier Domain hors `ApplicationSettings` modifié — `InferencePage`, `PromptsPage`, `CharactersPage`, `CharacterManager`, `PromptManager`, `DatasetManager`, `ComfyUIEngine` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) reçoit une première fondation partielle mais reste ouvert — aucun usage utilisateur final (Prompt Assistant, analyse vision, Character Context, Prompt Library, mémoire sémantique) n'est câblé. Validée par la suite automatisée complète **et par un smoke test manuel réel complet, PASS**. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `3a37817b96400d7bd2e6fe7e82f12e230cc6c530` — `feat: add Ollama local AI backend`, tag `v0.2-mission030`, GitHub Release publiée).

---

## v0.2-mission029 — 2026-08-18

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 029 — commit, tag et Release non encore créés à la rédaction (même précédent que Missions 017/027/028). Clôture fonctionnelle uniquement : implémentation, tests et smoke test manuel réel tous validés.

### Résumé (Mission 029)

**Mission 029 — Principal Character Consistency (LoRA / Prompts / Training).** Mission 028 avait identifié, pendant le diagnostic de sa propre régression `DatasetManager`, que `LoRAManager`, `PromptManager` et `TrainingManager` partageaient le même défaut structurel : dépendre de `CharacterManager.active_character` plutôt que de `principal_character`, jamais réaffecté depuis que `CharactersPage` (Mission 026) ne fait plus que lire `principal_character` sans jamais rappeler `select()`. Conséquence réelle, confirmée par lecture directe du code avant toute correction : dans tout Workspace existant rouvert, les trois pages affichaient une liste vide (au lieu des LoRA/Prompts/Trainings réellement enregistrés) et toute création était silencieusement ignorée, sans qu'aucune action utilisateur ne puisse le corriger — la liste multi-personnage étant masquée de l'UI depuis Mission 026.

Un audit exhaustif préalable (`grep -rn "active_character\b"`/`"active_character_id\b"`/`"\.select\("` sur l'intégralité de `src/` et `tests/`, au-delà des neuf occurrences déjà repérées) a classifié chaque occurrence trouvée contre trois catégories — à corriger, à préserver pour la compatibilité multi-Character interne, ou hors périmètre — avant tout remplacement. Il a notamment confirmé que **la totalité** des tests existants de `test_lora_roundtrip.py`/`test_prompt_roundtrip.py`/`test_training_roundtrip.py` appellent `character_manager.select()` explicitement, masquant structurellement le bug réel — exactement la situation qui avait permis à la régression `DatasetManager` de passer inaperçue jusqu'au smoke test réel de Mission 028.

Corrigé par le remplacement à l'identique déjà validé deux fois (`CharactersPage` Mission 026, `DatasetManager` Mission 028) : `active_character` → `principal_character` sur 9 usages Manager (property de collection + `create()` + `delete()`, ×3 Managers), plus mise à jour de 3 docstrings de classe et reformulation de 3 messages UI (`LoRAPage`/`PromptsPage`/`TrainingPage`) devenus trompeurs, sur le modèle exact du message déjà corrigé de `DatasetsPage` en Mission 028. **Aucune modification de `CharacterManager`** (`active_character`, `active_character_id`, `select()`, `_ensure_default_character()` strictement inchangés) **ni de `DatasetManager`** (aucune régression liée découverte). La compatibilité multi-Character interne reste intégralement préservée — confirmée par les 21 tests historiques appelant `select()` explicitement, tous verts sans aucune modification.

### Tests ajoutés (Mission 029)

- `tests/integration/test_lora_roundtrip.py` (+1) — `LoRACreationWithoutManualCharacterSelectionTest` : séquence exacte création Workspace → attache une LoRA → fermeture → réouverture (sans jamais appeler `CharacterManager.select()`) → LoRA existante toujours visible (pas de liste vide) → création d'une seconde LoRA réussie et rattachée au même Character principal (`assertIn`, pas seulement un retour non-`None`) → suppression réussie → persistance confirmée après un second cycle fermeture/réouverture. Vérifie explicitement `active_character_id is None` juste avant l'action testée.
- `tests/integration/test_prompt_roundtrip.py` (+1) — `PromptCreationWithoutManualCharacterSelectionTest` : même séquence, avec en plus la vérification que `update_text()`/`select()` (sélection de l'entité elle-même, mécanisme entièrement indépendant de `CharacterManager.active_character`, non concerné par la correction) continuent de fonctionner à l'identique après réouverture.
- `tests/integration/test_training_roundtrip.py` (+1) — `TrainingCreationWithoutManualCharacterSelectionTest` : même séquence avec un Dataset pré-existant du Character principal, vérifiant que le contrôle d'appartenance du Dataset référencé par `create()` continue de fonctionner correctement une fois `character` résolu via `principal_character`.
- **513/513 tests verts** au total (510 précédents + 3 nets nouveaux), aucune régression Dataset/Character détectée — les 21 tests historiques multi-Character des trois fichiers concernés restent inchangés et verts.
- **Smoke test manuel réel complet, PASS** : après fermeture/réouverture du Workspace, sans jamais visiter Characters ni faire de sélection manuelle, les LoRA/Prompts/Trainings existants sont restés visibles, la création de nouvelles entrées a réussi dans les trois domaines, la suppression a réussi, la persistance a été confirmée après un second cycle fermeture/réouverture. Un point observé (`Training: Idle` affiché par le Dashboard, sans lien avec cette correction — `Idle` reflète l'état d'exécution du moteur Training, pas le nombre de sessions enregistrées) a été enregistré comme nouveau besoin futur distinct, non implémenté cette mission.

### État du projet (Mission 029)

Aucun fichier Domain (`src/domain/*.py`) modifié. Le besoin futur "dette de cohérence Character — `active_character` vs `principal_character` dans `LoRAManager`/`PromptManager`/`TrainingManager`", identifié pendant Mission 028, est désormais **résolu** — retiré de la liste des besoins ouverts dans `docs/PROJECT_CONTEXT.md`. Un nouveau besoin futur a été identifié et consigné, non implémenté cette mission : clarification de l'indicateur `Training: Idle` du Dashboard (distinction nombre de sessions enregistrées / état d'exécution du moteur). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte.

---

## v0.2-mission028 — 2026-08-18

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 028 — commit, tag et Release non encore créés à la rédaction (même précédent que Missions 017/027). Clôture fonctionnelle uniquement : implémentation, tests et smoke test manuel réel tous validés.

### Résumé (Mission 028)

**Mission 028 — Import Images into Workspace.** "Importer des images" ne se contente plus de référencer le chemin externe choisi via `QFileDialog` — AI Studio Toolkit copie désormais physiquement chaque source externe dans le Workspace, le fichier source restant toujours intact à son emplacement d'origine. Nouvelle primitive Infrastructure `WorkspaceStorage.copy_into_workspace()` (+ `is_inside()`, `resolve_collision_free_name()`), appelée par `WorkspaceManager.add_images()` (destination `<workspace_root>/images/`) et `DatasetManager.add_images()` (destination `<workspace_root>/datasets/<dataset_id>/`, un sous-dossier par Dataset identifié par `dataset_id` plutôt que par son nom, pour rester filesystem-safe et sans collision entre Datasets). Une source déjà interne au Workspace — n'importe où sous `Workspace.root`, notamment une image déjà générée sous `outputs/` par le flux Accept d'Inference (Mission 013/014) — est reconnue et réutilisée telle quelle, sans copie ni renommage : découverte pendant l'audit exhaustif des appelants d'`add_images()`, cette règle large (et non limitée au seul dossier de destination exact) est ce qui évite qu'Accept ne duplique silencieusement chaque image générée vers `images/` — vérifié par test dédié, comportement Accept strictement inchangé.

`add_images()` retourne désormais `ImportResult(added, failed, skipped)` plutôt qu'un simple entier : traitement best-effort d'un import multiple (un échec de copie n'empêche jamais les autres fichiers du lot), aucune persistance pour une copie échouée, un doublon (de lot ou source déjà enregistrée) toujours classé `skipped`, jamais confondu avec un `failed`.

**Révisée après un premier smoke test réel (FAIL) ayant révélé deux problèmes fonctionnels**, non corrigés avant un second smoke test réel :

1. **Collision de nom silencieuse, jugée non conforme à l'UX attendue.** Le suffixage automatique (`photo.jpg` → `photo_1.jpg`) fonctionnait mais restait silencieux. Remplacé, côté UI uniquement, par un dialogue unique (`ImportCollisionDialog`, jamais une série d'un dialogue par fichier) : nouvelle méthode `preview_collisions()` (Manager) détecte à l'avance les collisions — y compris entre fichiers du même lot pas encore physiquement copiés — et l'utilisateur choisit, pour chacune, de renommer (nom proposé éditable, pré-rempli avec le même nom collision-safe que l'automatique aurait choisi) ou d'ignorer (`skipped`, jamais `failed`). La primitive Infrastructure non destructive reste inchangée et sert toujours de filet de sécurité par défaut pour tout appelant hors UI (tests, usage programmatique).
2. **Régression bloquante : création de Dataset impossible dans un Workspace existant rouvert.** `DatasetManager` (`datasets`, `create()`, `is_referenced_by_training()`, `delete()`) dépendait encore de `CharacterManager.active_character`, jamais réaffecté depuis que `CharactersPage` (Mission 026) ne fait plus que lire `principal_character` sans jamais rappeler `select()` — un Workspace existant rouvert (`WORKSPACE_OPENED`, sans re-sélection automatique) laissait donc `active_character_id` à `None` pendant toute la session, bloquant "Nouveau dataset" sans qu'aucune action utilisateur ne puisse le corriger (liste multi-personnage masquée). Corrigé en basculant `DatasetManager` sur `CharacterManager.principal_character` — exactement le mécanisme déjà validé par Mission 026 pour `CharactersPage`. Le même défaut, identifié mais **non corrigé** dans cette mission (hors périmètre), affecte aussi `LoRAManager`/`PromptManager`/`TrainingManager` — enregistré comme besoin/audit futur distinct.

Aucune migration rétroactive des références externes déjà persistées ; aucun changement de format de sérialisation (`Image.file_path` reste un `str` absolu — la conversion vers des chemins relatifs appartient à la future Mission 029) ; remap correct par `WorkspaceManager.rename()` (Mission 027) vérifié par test dédié pour toute nouvelle copie interne.

### Tests ajoutés (Mission 028)

- `tests/integration/test_workspace_roundtrip.py` (35 nets nouveaux) — `WorkspaceStorageCopyIntoWorkspaceTest` (14) : `is_inside()` (enfant direct/imbriqué/racine/casse Windows/chemin disparu), `copy_into_workspace()` (copie + source intacte, création défensive du dossier, collision par suffixe numérique enchaîné, source introuvable, nettoyage best-effort d'un fichier partiel, source déjà interne réutilisée sans copie même depuis un sous-dossier différent). `WorkspaceManagerAddImagesCopyTest` (20, dont 9 pour `preview_collisions()`/`renames`) : copie réelle et chemin persisté, source intacte, deux sources différentes même nom jamais écrasées, doublon de lot `skipped`, échec partiel n'empêche pas le reste du lot, aucune persistance pour une copie échouée, source déjà interne réutilisée, persistance après fermeture/réouverture, ancien `project.json` externe inchangé, prévisualisation des collisions (vide/réelle/intra-lot/déjà interne), renommage appliqué verbatim, nom déjà pris → `failed`, comportement automatique silencieux toujours disponible hors UI. 1 test de synergie ajouté à `WorkspaceRenameTest` (import puis renommage → remap correct).
- `tests/integration/test_dataset_roundtrip.py` (17 nets nouveaux) — `DatasetManagerAddImagesCopyTest` (10, dont 3 pour `preview_collisions()`/`renames`) : copie sous `datasets/<dataset_id>/`, source intacte, deux Datasets sans collision croisée, échec partiel, aucune persistance sur échec, source déjà interne réutilisée, ancien `project.json` externe inchangé, persistance après fermeture/réouverture, remap après renommage. `DatasetsPageCollisionDialogTest` (4) : aucun dialogue sans collision, renommer/ignorer appliqués, `Cancel` annule tout l'import. `DatasetCreationWithoutManualCharacterSelectionTest` (1, régression) : séquence exacte create → close → open (sans `select()`) → "Nouveau dataset" réussi → import réussi → persistance après un second cycle fermeture/réouverture.
- `tests/integration/test_images_page.py` (6 nets nouveaux, 17 adaptés) — `ImagesPageCollisionDialogTest` : aucun dialogue sans collision, un seul dialogue pour plusieurs collisions, `Cancel` annule l'import entier, renommer/ignorer appliqués correctement. Les 17 tests existants adaptés distinguent désormais la source externe de la copie interne (assertions basées sur le chemin persisté, plus le nom fictif d'origine) ; les scénarios de fichier "manquant à l'import" reformulés en fichier réel au contenu non chargeable, une source inexistante ne pouvant plus devenir une `Image`.
- `tests/integration/test_image_roundtrip.py`, `test_dataset_roundtrip.py` (tests Manager historiques), `test_dashboard_page.py`, `test_inference_page.py` : fixtures adaptées (fichiers temporaires réels remplaçant les noms fictifs), `test_accept_persists_pending_image_exactly_once` enrichi d'une vérification directe (`shutil.copy2` jamais appelé, `images/` reste vide) prouvant la non-régression du flux Accept.
- **510/510 tests verts** au total (452 précédents + 58 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet, PASS après correction** (un premier smoke test avait révélé les deux problèmes ci-dessus, corrigés puis revalidés) : copie physique confirmée dans `Workspace/images/`, disponibilité indépendante du fichier source externe, dialogue de collision fonctionnel (renommer/ignorer), aucune série de dialogues pour plusieurs collisions, création de Dataset et import d'images fonctionnels sans aucune sélection manuelle de personnage, images de Dataset confirmées sous `datasets/<dataset_id>/`, persistance après renommage de projet et après fermeture/réouverture, flux Inference/Accept confirmé sans copie artificielle vers `images/`.

### État du projet (Mission 028)

Aucun fichier Domain (`src/domain/*.py`) modifié — `Image.file_path` reste un `str` absolu, seule sa provenance change (copie interne plutôt que chemin externe), jamais sa forme ni son type. Deux besoins futurs identifiés et consignés dans `docs/PROJECT_CONTEXT.md`, non implémentés cette mission : alimentation d'un Dataset depuis la galerie Images (sélection multiple dans `ImagesPage`, ajout à un Dataset sans repasser par le sélecteur de fichiers) ; dette de cohérence `active_character`/`principal_character` affectant encore `LoRAManager`/`PromptManager`/`TrainingManager` (`DatasetManager` seul corrigé, strictement dans le périmètre de cette mission). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte.

---

## v0.2-mission027 — 2026-08-18

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 027 — commit, tag et Release non encore créés à la rédaction (même précédent que Mission 017). Clôture fonctionnelle uniquement : implémentation, tests et smoke test manuel réel tous validés.

### Résumé (Mission 027)

**Mission 027 — Project Rename.** AI Studio Toolkit permet désormais de renommer proprement un projet depuis l'application (menu **Fichier → Renommer le projet…**, `RenameProjectDialog`), plutôt que de dépendre d'un renommage manuel du dossier dans l'Explorateur Windows. Un audit read-only préalable a établi qu'un tel renommage manuel est SAFE SOUS CONDITIONS uniquement lorsque le projet est fermé, et casse au minimum les chemins absolus internes réellement situés sous l'ancien dossier — en particulier les images générées via `Inference` et acceptées, physiquement stockées sous `<workspace>/outputs/` mais dont le chemin absolu est enregistré tel quel dans `Workspace.images[]`.

`WorkspaceManager.rename(new_name) -> bool` orchestre l'opération : renommage physique du dossier (`WorkspaceStorage.rename_folder()`), mise à jour de `Workspace.root`/`Workspace.name`, et remappage des 6 champs de chemins internes identifiés par l'audit (`Workspace.images[].file_path`, `Character.datasets[].images[].file_path`, `Workspace.models[].file_path`, `Workspace.workflows[].file_path`, `Character.loras[].files[]`/`.thumbnail`) — toujours par comparaison composant par composant du chemin (`Path.parts`, normalisée pour l'insensibilité à la casse Windows/NTFS), jamais par substitution de préfixe de chaîne brute. Tout chemin situé hors de l'ancien dossier, et `Character.name`, restent strictement inchangés — aucun couplage introduit entre le nom du projet et celui du personnage (règle déjà actée en Mission 026).

Ordonnancement transactionnel délibéré ("commit en dernier") : `Workspace.rename()` calcule d'abord, sans aucune mutation, le nouveau contenu complet à écrire ; `self.current_workspace` n'est remplacé qu'une fois le renommage physique **et** la sauvegarde de `project.json` tous deux réussis. Si la sauvegarde échoue après un renommage physique réussi, un rollback filesystem best-effort est tenté (renommage en sens inverse) ; son éventuel échec est toujours signalé par une erreur explicite et actionnable, jamais masqué. Cette stratégie s'appuie sur un durcissement nécessaire de `WorkspaceStorage.save()` en écriture atomique (fichier temporaire + `os.replace()`), bénéfique à tous les appelants existants sans changer leur contrat observable.

Un premier smoke test réel a révélé un bug reproductible : un second renommage du même projet, dans la même session ou après fermeture/réouverture, pouvait échouer avec `WinError 5 — Accès refusé`. Un diagnostic exhaustif a d'abord infirmé toute cause interne à l'application (verrou Qt/`QPixmap`, écriture atomique, handle applicatif non libéré — chacune testée activement, jamais reproduite), puis un diagnostic réel avec *Process Explorer* (Sysinternals) a confirmé la cause exacte : `explorer.exe` détient des handles ouverts sur les sous-dossiers du projet (`images`, `outputs`, `models`...) lorsqu'une fenêtre de l'Explorateur Windows y navigue, bloquant le renommage du dossier racine — un verrouillage Windows externe et légitime, jamais une corruption du Workspace ni un défaut de libération de handle applicatif. Traité par un type d'exception dédié (`WorkspaceRenamePermissionError`, à deux niveaux Infrastructure/Manager) et un message utilisateur français actionnable (`QMessageBox.warning`, « Renommage impossible » — dossier/sous-dossier probablement utilisé par une autre application, fermer les fenêtres de l'Explorateur Windows concernées puis réessayer) — **sans jamais tenter de fermer un handle ou un processus externe**, et sans masquer aucune autre erreur sous ce message.

### Tests ajoutés (Mission 027)

- `tests/integration/test_workspace_roundtrip.py` (29 nets nouveaux) — `WorkspaceRenameTest` (23) : renommage simple, idempotence, réparation d'un `Workspace.name` désynchronisé sans renommage physique, `Character.name` jamais touché, remap des 6 champs de chemins internes et préservation stricte des chemins externes et des valeurs vides légitimes, persistance après fermeture/réouverture, `active_*_id` préservés (aucun reset sur `WORKSPACE_RENAMED`), dossier cible déjà existant, échec du rename filesystem initial → Domain strictement inchangé, échec de sauvegarde après renommage réussi → rollback filesystem + Domain jamais muté, échec du rollback lui-même → erreur explicite jamais un `False` silencieux, aucun `WORKSPACE_RENAMED` sur tout chemin d'échec, événement publié exactement une fois au succès, deux renommages consécutifs dans la même session et après un cycle fermeture/réouverture (régression du bug `WinError 5`), `PermissionError` levée comme type dédié et jamais publié d'événement, autres erreurs jamais reclassées comme permission-denied. `WorkspaceStorageAtomicSaveTest` (3) : échec avant `os.replace()` laisse `project.json` intact sans fichier temporaire résiduel. `WorkspaceStorageRenameFolderErrorTest` (3) : `PermissionError` distinguée de tout autre `OSError`.
- `tests/integration/test_rename_project_dialog.py` (10, nouveau fichier) — pré-remplissage depuis le nom réel du dossier, bouton désactivé sur nom vide/invalide/identique/collision, réutilisation de `validate_project_name()` sans duplication, collision de dernière seconde revérifiée à l'instant de l'acceptation, aucune écriture disque.
- `tests/integration/test_main_window_rename_project.py` (10, nouveau fichier) — câblage du menu vers `RenameProjectDialog`/`WorkspaceManager.rename()`, `WorkspaceRenamePermissionError` affichée via `QMessageBox.warning` dédié avec le texte français attendu (jamais `.critical`), toute autre erreur restant sur `.critical` (jamais `.warning`), `open_project()`/`save_project()`/`new_project()` non affectés, résultat de génération pending invalidé après un renommage réussi.
- `tests/integration/test_inference_page.py` (1 nouveau) — `WORKSPACE_RENAMED` ajouté à l'abonnement `reset_for_workspace_change`, invalidant un résultat pending exactement comme `CREATED`/`OPENED`/`CLOSED`.
- **452/452 tests verts** au total (402 précédents + 50 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet, PASS après correction** (un premier smoke test avait révélé le bug `WinError 5` ci-dessus, corrigé puis revalidé) : chaîne `ProjetA → ProjetB → ProjetC` sans redémarrage, cycle fermeture/réouverture puis renommage vers `ProjetD`, image réelle sous `outputs/` correctement remappée, ressource externe strictement inchangée, `Character.name` inchangé, blocage propre et message français actionnable confirmés avec une fenêtre de l'Explorateur Windows ouverte dans un sous-dossier du projet, résolution immédiate après fermeture de cette fenêtre.

### État du projet (Mission 027)

Aucun fichier Domain (`src/domain/*.py`) modifié. Nouvel événement `WORKSPACE_RENAMED`, ajouté aux abonnements de rafraîchissement des Pages et à celui d'invalidation du résultat pending d'`InferencePage` — jamais aux resets internes `active_*_id` des autres Managers (un renommage ne change l'identité d'aucune entité). Besoin architectural identifié mais non implémenté cette mission, consigné dans `docs/PROJECT_CONTEXT.md` : les ressources internes au Workspace devraient-elles être persistées relativement à `Workspace.root` plutôt qu'en chemins absolus (pertinent aussi pour la portabilité/déplacement d'un projet) ; et, distinctement, les images importées devraient-elles être copiées dans le dossier `images` du projet plutôt que simplement référencées par leur emplacement externe, pour l'autonomie du projet. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte.

---

## v0.2-mission026 — 2026-08-17

### Résumé (Mission 026)

**Mission 026 — Character Identity Foundation.** `Character` gagne six champs additifs et rétrocompatibles — `bio`, `description`, `character_lock`, `personality`, `interests`, `trigger_token` (tous `str`, défaut `""`) — organisés conceptuellement en 5 catégories (Identité, Apparence/identité visuelle, Personnalité, Goûts et centres d'intérêt, Informations techniques IA) mais stockés en dataclass plate, sans sur-conception en sous-objets : une catégorie sans consommateur technique identifié reçoit un seul champ texte libre consolidé plutôt que des scalaires spéculatifs individuels ; `character_lock`/`trigger_token` gardent leur champ dédié, leur usage technique futur étant déjà nommé. `CharacterManager.update()` (idempotent, jamais d'événement publié, même contrat que `PromptManager.update_text()`) gère aussi bien ces champs que le renommage du personnage.

**Révisée deux fois après smoke test réel**, chacune corrigeant une incohérence constatée en conditions réelles :
1. Un Workspace nouvellement créé n'avait initialement aucun Character, obligeant un clic "Nouveau personnage" avant de pouvoir remplir la fiche — contraire à l'orientation produit "1 Workspace = 1 personnage principal". Corrigé : `CharacterManager` crée et sélectionne désormais automatiquement un personnage principal (nommé depuis `Workspace.name`) dès qu'un Workspace vide de personnages reçoit `WORKSPACE_CREATED` — jamais sur `WORKSPACE_OPENED`, pour ne jamais annuler silencieusement une suppression volontaire de l'utilisateur.
2. Une fois cette création automatique en place, la liste et les boutons "Nouveau personnage"/"Supprimer" ne correspondaient plus à l'UX cible, et un bug empêchait la sauvegarde de la fiche dans le flux le plus simple (`QMessageBox` "Aucun personnage sélectionné" malgré une fiche correctement affichée). Corrigé : `CharactersPage` masque désormais (`setVisible(False)`, jamais retiré) la liste et les boutons multi-personnage — `Characters` représente directement la fiche du personnage principal — et `save_identity()` utilise `CharacterManager.principal_character_id` (repli sur le premier personnage si aucune sélection active) plutôt que de dépendre du mécanisme historique de sélection.

`Workspace.characters: list[Character]` et le CRUD multi-personnage (`create()`/`delete()`, sérialisation) restent des **mécanismes internes transitoires intacts** — aucune migration, aucune contrainte de cardinalité `max=1` introduite ; les 7 tests historiques multi-personnage passent sans modification de leurs assertions substantielles. `Workspace.name` et `Character.name` peuvent diverger librement après l'initialisation : renommer le Character ne modifie jamais le Workspace/dossier du projet, et réciproquement.

### Tests ajoutés (Mission 026)

- `tests/integration/test_character_roundtrip.py` (39 — 7 précédents adaptés + 32 nets nouveaux) : défauts/`to_dict()`/`from_dict()`/rétrocompatibilité legacy des six champs d'identité ; `CharacterManager.update()` idempotent (renommage inclus, jamais d'événement) ; création/sélection automatique du personnage principal sur `WORKSPACE_CREATED` (nom = `workspace.name`, persistée, aucun double si republié, jamais sur `WORKSPACE_OPENED`) ; fiche `CharactersPage` en 5 sections peuplée/vidée sans fuite entre personnages, immédiatement active sans aucun clic ; contrôles multi-personnage masqués (`isHidden()`) ; `principal_character_id` avec repli sur le premier personnage y compris quand `active_character_id` a été perdu (test de régression, confirmé FAIL avant correction, PASS après) ; test architectural confirmant l'absence de toute référence aux nouveaux champs dans le code de génération.
- `tests/integration/test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py` (0 nouveau test chacun, assertions adaptées) : recherche explicite du Character par nom (jamais par index de liste) après réouverture, compteur d'abonnés `WORKSPACE_CREATED` mis à jour.
- `tests/integration/test_model_roundtrip.py`, `test_workflow_roundtrip.py` (0 nouveau test chacun) : compteur d'abonnés `WORKSPACE_CREATED` mis à jour (découverte complémentaire, hors périmètre initialement balisé, signalée par transparence).
- **402/402 tests verts** au total (370 précédents + 32 nets nouveaux), aucune régression détectée, aucune assertion supprimée pour faire passer la suite.
- **Smoke test manuel réel complet, troisième tentative concluante** (les deux premières ayant chacune révélé une incohérence corrigée avant re-test) : personnage principal auto-créé et immédiatement utilisable dès la création d'un projet, `Nom` initial = nom du projet, aucune liste ni bouton multi-personnage visible, sauvegarde réussie y compris répétée dans la même session, fermeture/réouverture avec restauration fidèle de toute la fiche (renommage inclus), aucune `QMessageBox` d'erreur, nom du Workspace/projet inchangé malgré le renommage du personnage. PASS.

### État du projet (Mission 026)

Aucun nouvel événement EventBus publié par les nouveaux champs/méthodes d'identité. `Workspace.characters` reste `list[Character]`, sans migration ni contrainte de cardinalité — compatibilité interne multi-Character conservée temporairement, en attente d'une future décision architecturale sur la cardinalité produit "1 Workspace = 1 personnage principal". Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission025 — 2026-08-17

### Résumé (Mission 025)

**Mission 025 — ComfyUI Checkpoint Discovery & Selection.** `SettingsPage` expose désormais `ComfyUI Checkpoint` comme un `QComboBox` éditable (`comfyui_checkpoint_name_edit`, attribut conservé) plutôt qu'un `QLineEdit` en texte libre, accompagné d'un nouveau bouton "Rafraîchir les checkpoints". La découverte des checkpoints est réalisée par une nouvelle méthode additive `ComfyUIEngine.list_checkpoints()` (`GET /object_info/CheckpointLoaderSimple`, réutilisant `_request_json()` déjà existant, timeout court dédié distinct du timeout de génération) — **délibérément pas** par un scan du champ `comfyui_path` déjà existant, contrairement à l'hypothèse initiale de la spécification. Un audit read-only complémentaire, mené avant toute implémentation, a établi que l'installation réelle de l'architecte (ComfyUI Desktop pour Windows) démarre avec `--extra-model-paths-config .../shared_models.yaml` : les checkpoints réellement exposés peuvent provenir de chemins additionnels/partagés que ComfyUI résout déjà correctement en interne. Interroger directement le serveur en cours d'exécution via `comfyui_url` (déjà exploité depuis Mission 018) évite toute réimplémentation de cette résolution de chemins, et fonctionne identiquement pour une installation locale, portable, Desktop ou distante. La découverte n'est déclenchée que sur clic explicite du bouton (jamais au chargement de Settings, aucune surveillance filesystem/réseau permanente), avec un repli systématique et permanent sur la saisie manuelle en cas d'échec (serveur injoignable, URL invalide, réponse inattendue) — `ComfyUIEngineError` toujours capturée par `SettingsPage`, qui ne plante jamais. `comfyui_path` reste, à l'issue de cette mission, un champ existant mais **non consommé par aucun code** — son besoin d'exploitation future reste entièrement ouvert, désormais documenté indépendamment de la sélection de checkpoint (voir `docs/PROJECT_CONTEXT.md`).

### Tests ajoutés (Mission 025)

- `tests/integration/test_comfyui_engine.py` (15 nouveaux tests) — `list_checkpoints()` : extraction correcte de plusieurs/un seul/zéro checkpoint, requête `GET` vers le bon endpoint, retour strictement `list[str]` sans fuite de la structure brute `object_info`, entrées non-`str` filtrées défensivement, `ComfyUIEngineError` sur `CheckpointLoaderSimple` absent/forme inattendue/`ckpt_name` non-liste/JSON invalide/erreur HTTP/serveur injoignable/timeout socket/URL structurellement invalide, timeout effectivement transmis à `urlopen()`.
- `tests/integration/test_settings_page.py` (14 nouveaux tests, **nouveau fichier** — première couverture Qt dédiée à `SettingsPage`) — champ checkpoint est un `QComboBox` éditable, valeur persistée restaurée au chargement, rafraîchissement peuplant la liste, valeur actuellement affichée toujours conservée même absente de la liste découverte, sélection puis sauvegarde, saisie manuelle puis sauvegarde, rechargement restaurant la valeur, URL actuellement tapée utilisée (pas nécessairement enregistrée), timeout court dédié confirmé, échec de découverte sans plantage et `SettingsPage` toujours utilisable, zéro checkpoint découvert sans erreur, bouton présent, aucune interférence avec les autres champs Application, aucune découverte automatique au chargement.
- `tests/integration/test_application_settings_roundtrip.py` (0 nouveau test, 2 lignes corrigées) — `test_settings_page_application_section_lifecycle` adapté au changement de type `QLineEdit` → `QComboBox` (`.text()`/`.setText()` → `.currentText()`/`.setCurrentText()`), trouvé par la recherche préalable systématique de mocks/signatures obsolètes (procédure établie Mission 022).
- **370/370 tests verts** au total (341 précédents + 29 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet** contre ComfyUI Desktop (`http://127.0.0.1:8000`) : découverte réelle des checkpoints exposés, liste déroulante fonctionnelle, sélection, sauvegarde, restauration après redémarrage de l'application, génération txt2img réelle confirmant le checkpoint effectivement utilisé, et validation explicite du cas de fallback (ComfyUI arrêté/URL invalide) — aucun plantage, message d'indisponibilité affiché, saisie manuelle toujours disponible. PASS.

### État du projet (Mission 025)

Aucun nouveau Domain/Manager/Service/EventBus event. `comfyui_workflows.py`, `generation_manager.py`, `generation_worker.py`, `inference_page.py` strictement inchangés (aucun paramètre Mission 024 affecté). `comfyui_path` reste non consommé. Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission024 — 2026-08-17

### Résumé (Mission 024)

**Mission 024 — Réglage utilisateur de la force img2img.** `DEFAULT_IMG2IMG_DENOISE` (Mission 023, fixé à `0.75`) devient ajustable par l'utilisateur : `InferencePage` gagne un `QSlider` (plage `0`–`100`, valeur par défaut `75`) libellé « Force de transformation », accompagné d'un label numérique synchronisé (`"0.75"`, deux décimales) — visible mais désactivé sans référence, activé dès qu'une référence est sélectionnée, réinitialisé (valeur et état) au retrait de la référence et au changement de Workspace, sans aucune persistance (ni session, ni `project.json`). Le concept reste générique (`reference_strength: float`, `0.0`–`1.0`) à travers `InferencePage`/`GenerationWorker`/`GenerationManager.generate()` ; la traduction vers le vocabulaire natif ComfyUI (`denoise`) n'a lieu qu'à l'unique appel `GenerationManager` → `ComfyUIEngine.generate_image(denoise=...)`, et uniquement lorsqu'une référence est présente et qu'une valeur est fournie — sinon `ComfyUIEngine`/`build_img2img_workflow()` retombent sur leur défaut existant, garantissant structurellement (pas par convention) que le comportement historique `0.75` reste inchangé pour un utilisateur qui ne touche jamais au slider. `build_img2img_workflow()`/`comfyui_workflows.py` strictement inchangés (le paramètre `denoise` y existait déjà depuis Mission 023). Sans référence, le chemin txt2img reste strictement inchangé. Aucun terme `"denoise"` n'apparaît dans `inference_page.py`, vérifié par test architectural dédié.

### Tests ajoutés (Mission 024)

- `tests/integration/test_comfyui_engine.py` (2 nouveaux tests) — `generate_image(denoise=X)` transmet bien `X` au graphe img2img soumis ; comportement par défaut préservé si omis.
- `tests/integration/test_generation_manager.py` (4 nouveaux tests) — `reference_strength` transmis comme `denoise=` uniquement quand une référence est présente et une valeur fournie ; ignoré dans tous les autres cas ; signature générique confirmée.
- `tests/integration/test_generation_worker.py` (3 nouveaux tests) — `reference_strength` capturé immédiatement à la construction (valeur immuable) et transmis à `generate()` ; défaut `None` inchangé.
- `tests/integration/test_inference_page.py` (11 nouveaux tests) — libellé, état initial du slider, activation/désactivation selon la présence d'une référence, synchronisation du label numérique, conversion `75 → 0.75`, transmission de la valeur par défaut et d'une valeur personnalisée, reset au retrait de la référence et au changement de Workspace, désactivation pendant une génération avec réactivation conditionnelle, test architectural anti-`"denoise"`.
- **341/341 tests verts** au total (321 précédents + 20 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet** contre ComfyUI Desktop (`http://127.0.0.1:8000`), même référence et même prompt que Mission 023, trois forces testées : `0.20` (résultat très proche de la référence), `0.75` par défaut (transformation intermédiaire, cohérente avec la régression Mission 023), `0.95` (transformation forte, prompt nettement dominant) — progression jugée clairement perceptible et cohérente avec le comportement attendu. PASS.

### État du projet (Mission 024)

Aucun nouveau Domain/Manager/Service/EventBus event. `comfyui_workflows.py` strictement inchangé. Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission023 — 2026-08-17

### Résumé (Mission 023)

**Mission 023 — ComfyUI Img2Img Reference Workflow.** La référence sélectionnée dans `InferencePage` (Mission 022) influence désormais réellement le résultat généré, pour la première fois, via un workflow img2img natif ComfyUI. Nouveau module `src/engines/workflows/comfyui_workflows.py` séparant la construction des graphes ComfyUI du transport HTTP — `build_demo_workflow()` déplacée à l'identique et renommée `build_txt2img_workflow()` (mêmes node IDs, mêmes `class_type`, mêmes valeurs, aucun changement de comportement), et nouveau `build_img2img_workflow()` : `LoadImage → VAEEncode → KSampler(denoise=0.75) → VAEDecode → SaveImage`, nodes core ComfyUI uniquement, aucun custom node, aucun IP-Adapter, aucun ControlNet. `ComfyUIEngine.generate_image()` choisit le graphe selon la présence d'un `reference_image` (le `dict` structuré retourné par `upload_image()`, Mission 021) ; une nouvelle méthode privée `_submit_and_download()` factorise la séquence `submit → wait_for_result → download_output`, partagée sans duplication entre les deux graphes. `GenerationManager.generate()` uploade au plus une référence et transmet le résultat d'upload de façon strictement opaque à `generate_image()` — sans jamais interpréter de structure JSON/node ComfyUI. Plus d'une référence est explicitement rejetée (`GenerationError`, avant tout upload) : une limite propre à ce workflow, pas un retrait de l'architecture `reference_images: list[str]` (0..N) déjà établie en Mission 022. Sans référence, le chemin txt2img reste strictement inchangé. `InferencePage`/`GenerationWorker` non modifiés. Validée par la suite automatisée complète **et par un smoke test manuel réel** contre ComfyUI Desktop : régression txt2img confirmée, img2img confirmé (référence et prompt tous deux observés comme influençant réellement le résultat), avec l'observation que l'équilibre entre les deux dépend de la proximité sémantique référence/prompt et du checkpoint utilisé — enregistré comme besoin futur (réglage utilisateur de la force img2img), non implémenté cette mission.

### Tests ajoutés (Mission 023)

- `tests/integration/test_comfyui_workflows.py` (27 nouveaux tests, nouveau fichier) — `build_txt2img_workflow()` équivalente en tous points à l'ancienne `build_demo_workflow()`, `build_img2img_workflow()` : présence `LoadImage`/`VAEEncode`, absence d'`EmptyLatentImage`, `denoise` par défaut `0.75` et surchargeable, traduction correcte de `name`/`subfolder` en input `LoadImage`.
- `tests/integration/test_comfyui_engine.py` (3 nouveaux tests) — `generate_image()` sans/avec `reference_image` soumet respectivement le graphe txt2img/img2img ; tests architecturaux renommés et étendus (`build_txt2img_workflow`/`build_img2img_workflow`, `_submit_and_download()` toujours agnostique de tout graphe).
- `tests/integration/test_generation_manager.py` (6 nets nouveaux tests — 2 tests Mission 022 sur l'upload de plusieurs références supprimés et remplacés, changement de contrat assumé) — plus d'une référence rejetée avant tout upload, transmission opaque du résultat d'upload prouvée explicitement, test architectural confirmant l'absence de toute connaissance JSON/node ComfyUI dans `GenerationManager`.
- **321/321 tests verts** au total (287 précédents + 34 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet** contre ComfyUI Desktop (`http://127.0.0.1:8000`, checkpoint `v1-5-pruned-emaonly-fp16.safetensors`) : régression txt2img PASS, img2img avec prompt cohérent PASS, diagnostic de câblage sans anomalie détectée, img2img avec prompt volontairement contradictoire PASS.

### État du projet (Mission 023)

Aucun nouveau Domain/Manager/Service/EventBus event. `submit()`/`wait_for_result()`/`download_output()`/`upload_image()` strictement inchangées. `InferencePage`/`GenerationWorker` non modifiés. Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission022 — 2026-08-15

### Résumé (Mission 022)

**Mission 022 — Reference Image Transport Wiring.** La primitive `ComfyUIEngine.upload_image()` (Mission 021), jusque-là non appelée nulle part dans le code applicatif, est désormais réellement câblée à la verticale Inference. `InferencePage` gagne une sélection 0/1 d'image de référence locale, réutilisant le pattern `QFileDialog` déjà employé par `ImagesPage`/`DatasetsPage` : bouton de sélection, label affichant le nom du fichier, bouton de retrait — état transitoire, jamais persisté dans `project.json`, réinitialisé sur changement de Workspace. À la frontière `InferencePage → GenerationWorker`, la sélection devient une collection `reference_images: list[str]` — jamais un singleton — capturée dans un snapshot défensif avant le démarrage du thread, immunisé contre tout changement de sélection UI pendant que la génération tourne. `GenerationManager.generate(prompt_text, output_directory, reference_images=None)` uploade chaque référence via `upload_image()`, dans l'ordre, avant `generate_image()`, avec un comportement fail-fast : le premier échec d'upload interrompt immédiatement la génération (normalisée en `GenerationError`, comme toute autre erreur de cette méthode), sans jamais atteindre `generate_image()`. Sans référence, le comportement reste strictement identique à avant cette mission — aucun appel à `upload_image()`. Cette mission reste volontairement une fondation de transport : la référence uploadée n'est utilisée dans aucun workflow, aucun node `LoadImage`, aucun img2img, aucune notion de rôle — `generate_image()`, `build_demo_workflow()` et `upload_image()` elle-même restent strictement inchangés, et le résultat généré n'est visuellement affecté en rien par la présence d'une référence.

### Tests ajoutés (Mission 022)

- `tests/integration/test_generation_manager.py` (9 nouveaux tests) — `reference_images` `None`/vide sans appel `upload_image`, une puis plusieurs références uploadées dans l'ordre, fail-fast au premier échec d'upload, normalisation `GenerationError` cohérente.
- `tests/integration/test_generation_worker.py` (3 nouveaux tests) — propagation de `reference_images` au constructeur, défaut `[]`, snapshot défensif prouvé indépendant de toute mutation ultérieure de la liste de l'appelant.
- `tests/integration/test_inference_page.py` (11 nouveaux tests) — sélection/annulation/remplacement/retrait de référence, propagation `[]`/`[chemin]` vers `GenerationManager`, non-interférence d'un changement de sélection après lancement, réinitialisation sur changement de Workspace, non-persistance dans `Workspace.images`. Correction, sans changement de comportement applicatif, de 6 fonctions locales préexistantes (`generate_side_effect`/`slow_generate`) dont l'ancienne signature à 2 paramètres était devenue incompatible avec l'appel `generate()` désormais toujours muni de `reference_images=`.
- **287/287 tests verts** au total (264 précédents + 23 nouveaux), aucune régression détectée.

### État du projet (Mission 022)

Aucun nouveau Domain/Manager/Service/EventBus event. `ComfyUIEngine.upload_image()`/`generate_image()`/`build_demo_workflow()` inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission021 — 2026-08-15

### Résumé (Mission 021)

**Mission 021 — ComfyUI Image Upload.** `ComfyUIEngine` gagne une quatrième primitive générique, `upload_image(file_path, subfolder="", overwrite=False)`, qui envoie un fichier image local vers l'instance ComfyUI (`POST /upload/image`) — le premier sens de transport `AI Studio Toolkit → ComfyUI`, les trois primitives existantes (`submit`/`wait_for_result`/`download_output`) ne couvrant jusqu'ici que le sens inverse. Le corps `multipart/form-data` est construit manuellement avec la seule bibliothèque standard (`uuid` pour la frontière, `mimetypes` pour deviner le `Content-Type`, repli `application/octet-stream`) — aucune nouvelle dépendance. Le champ `type` est envoyé en dur à `"input"` (seule valeur utile à un futur node `LoadImage`, non exposée en paramètre) ; `subfolder` est transmis tel quel ; `overwrite` n'est envoyé que lorsqu'il vaut `True`, conformément au contrat réel de ComfyUI (vérifié directement contre le code source `server.py`). La méthode retourne un `dict` structuré `{"name", "subfolder", "type"}` reflétant fidèlement la réponse ComfyUI — jamais réduit à un simple nom de fichier — et valide les trois champs (chaînes non vides pour `name`/`type`, chaîne pour `subfolder`) avant de le retourner, sinon lève `ComfyUIEngineError`. Les erreurs locales (fichier introuvable ou illisible) restent des exceptions natives (`FileNotFoundError`/`OSError`) non enveloppées, cohérent avec la convention déjà établie par `download_output()`. `ComfyUIEngine` ne conserve aucun état lié aux uploads : chaque appel est strictement indépendant, appelable autant de fois que nécessaire pour des images distinctes — propriété vérifiée par un test dédié. Cette mission reste volontairement une primitive de transport pure : aucune sélection d'image dans `InferencePage`, aucune modification de `GenerationManager`, `generate_image()` ou `build_demo_workflow()`, aucune orchestration de rôle (identité, vêtement, décor, pose...), aucun mécanisme moteur (img2img, IP-Adapter, ControlNet) — cette primitive prépare seulement, sans l'implémenter, un futur besoin d'images de référence multiples.

### Tests ajoutés (Mission 021)

- `tests/integration/test_comfyui_engine.py` (18 nouveaux tests, classe `ComfyUIEngineUploadImageTest`, 25 tests existants conservés sans modification) — upload réussi et retour structuré, requête multipart réelle (endpoint, boundary, filename et octets exacts, champ `type="input"`), `subfolder` transmis et restitué, `overwrite` présent uniquement si demandé, validation structurelle de la réponse (`name`/`subfolder`/`type` manquant, mal typé ou vide → `ComfyUIEngineError`), JSON invalide, erreur HTTP à corps vide, serveur injoignable, fichier local inexistant (`FileNotFoundError` non enveloppée), deux appels indépendants pour deux images distinctes sans état partagé.
- **264/264 tests verts** au total (246 précédents + 18 nouveaux), aucune régression détectée.

### État du projet (Mission 021)

Aucun nouveau Domain/Manager/Service/EventBus event. `GenerationManager`, `InferencePage`, `generate_image()`, `build_demo_workflow()` strictement inchangés. Aucune orchestration Reference Image introduite. Validée par la suite automatisée complète.

---

## v0.2-mission020 — 2026-08-15

### Résumé (Mission 020)

**Mission 020 — MainToolBar Actions Wiring.** Les trois `QAction` de `MainToolBar` ("Open", "Save", "Run"), jusque-là anonymes et strictement inertes (aucun `.triggered.connect()` nulle part, la barre d'outils elle-même n'étant pas conservée comme attribut de `MainWindow`), sont désormais stockées comme attributs explicites (`action_open`, `action_save`, `action_run`). Open et Save sont câblées directement dans `MainWindow` vers `open_project()`/`save_project()` déjà existants — réutilisation stricte, aucune méthode intermédiaire, aucun comportement modifié (sélection de dossier, annulation, feedback status bar, gestion d'erreur, y compris le cas "aucun Workspace ouvert" pour Save, qui continue d'afficher `"Aucun projet ouvert"` sans appeler `WorkspaceManager.save()`). Run reste visible mais explicitement désactivé (`setEnabled(False)`), avec un tooltip expliquant que l'exécution depuis la barre d'outils n'est pas encore disponible — aucune sémantique inventée, même traitement que le bouton "Lancer un entraînement" du Dashboard (Mission 017), faute de toute cible fonctionnelle générique légitime dans le projet. `MainToolBar` reste un composant Presentation pur, sans logique métier, Workspace ou Manager.

### Tests ajoutés (Mission 020)

- `tests/integration/test_main_toolbar.py` (nouveau, 6 tests) — comportement observable via de vrais widgets Qt et une vraie `MainWindow` : Open avec dossier sélectionné/annulé, Save avec/sans Workspace ouvert (y compris le message de status bar existant), Run désactivé avec son tooltip d'indisponibilité.
- **246/246 tests verts** au total (240 précédents + 6 nouveaux), aucune régression détectée.

### État du projet (Mission 020)

Aucun nouveau Domain/Manager/Service/Engine. `open_project()`/`save_project()` inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission019 — 2026-08-15

### Résumé (Mission 019)

**Mission 019 — Images Gallery / Thumbnails.** `ImagesPage` passe d'une liste texte de chemins de fichiers bruts à une galerie visuelle avec miniatures : `QListWidget` conservé (pas de `QListView`/modèle custom), passé en `QListWidget.IconMode`. Chaque image reste représentée par un seul `QListWidgetItem` : une miniature (`QPixmap` redimensionné, ratio conservé via `Qt.KeepAspectRatio`, transformation lissée via `Qt.SmoothTransformation`, construite avant le `QIcon` — jamais un icône sur pixmap pleine résolution), un label court (`Path(file_path).name`) et un tooltip affichant le chemin complet. Le chemin complet est désormais stocké dans `Qt.UserRole`, devenu la seule source utilisée par le double-clic et le bouton "Voir en grand" (`item.text()` n'est plus qu'un label de présentation). Pour tout fichier manquant ou illisible, une icône de repli Qt standard est utilisée — l'item reste conservé dans la galerie, `Qt.UserRole`/tooltip restent renseignés, et `ImagePreviewDialog` (non modifié) continue d'afficher son message d'indisponibilité existant. Sélection, import, `WorkspaceManager`, `Image` Domain et EventBus restent strictement inchangés. Aucun cache de miniatures, aucun lazy loading, aucun worker thread introduit.

### Tests ajoutés (Mission 019)

- `tests/integration/test_images_page.py` (6 nouveaux tests, 11 existants conservés sans modification) — `IconMode` actif, image valide (icône non nulle, label court, tooltip et `Qt.UserRole` corrects), fichier manquant et fichier invalide (icône de repli, item conservé, `Qt.UserRole` préservé, sélection/preview toujours fonctionnels), plusieurs images avec `Qt.UserRole` distincts.
- `tests/integration/test_inference_page.py` — adaptation minimale d'un helper de test interne (`_images_page_paths()`) vers `item.data(Qt.UserRole)`, imposée par le changement de représentation des items ; aucune modification du comportement Inference.
- **240/240 tests verts** au total (234 précédents + 6 nouveaux), aucune régression détectée.

### État du projet (Mission 019)

Aucun nouveau Domain/Manager/Service/Engine. `ImagePreviewDialog`/`WorkspaceManager`/`Image` Domain/EventBus inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission018 — 2026-08-14

### Résumé (Mission 018)

**Mission 018 — ComfyUI Application Settings.** L'URL du serveur ComfyUI et le nom du checkpoint utilisé par défaut, jusqu'ici codés en dur dans `main_window.py` (`COMFYUI_BASE_URL`/`COMFYUI_CHECKPOINT_NAME`, désormais supprimées), sont devenus deux champs (`comfyui_url`, `comfyui_checkpoint_name`) d'`ApplicationSettings`, qui en est la source de vérité unique — pas de second niveau de configuration ni de repli ailleurs dans le code. Leurs valeurs par défaut sont identiques au comportement précédemment codé en dur (`http://127.0.0.1:8000`, `v1-5-pruned-emaonly-fp16.safetensors`), y compris pour un fichier `application_settings.json` antérieur à cette mission et dépourvu de ces deux clés — comportement ComfyUI strictement inchangé pour toute installation existante. Les deux valeurs sont consultables et modifiables depuis la section Application de `SettingsPage`, persistées via `ApplicationSettingsManager.update()` déjà existant (aucun nouveau Manager, Service ni abstraction). Un changement sauvegardé ne prend effet qu'au prochain démarrage de l'application — aucune reconfiguration à chaud, un rappel textuel en informe l'utilisateur dans `SettingsPage`. `ComfyUIEngine` et `GenerationManager` restent strictement inchangés.

### Tests ajoutés (Mission 018)

- `tests/integration/test_application_settings_roundtrip.py` (4 tests étendus, 1 nouveau) et `tests/integration/test_main_window_comfyui_settings.py` (nouveau, 2 tests) — **3 nouveaux tests**, comportement observable (défauts réels, round-trip, compatibilité avec un fichier de settings antérieur à cette mission, affichage/sauvegarde depuis `SettingsPage`, `MainWindow` réel utilisant effectivement la configuration ComfyUI issue d'`ApplicationSettings`).
- **234/234 tests verts** au total (231 précédents + 3 nouveaux), aucune régression détectée.

### État du projet (Mission 018)

Aucun nouveau Domain/Manager/Service/Engine. `ComfyUIEngine`/`GenerationManager` inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission017 — 2026-08-14

### Résumé (Mission 017)

**Mission 017 — Dashboard Actions Wiring.** Les quatre boutons d'action du Dashboard (`newProjectButton`, `openProjectButton`, `importImagesButton`, `trainingButton`), visibles mais strictement inertes jusqu'à cette mission (aucun `.clicked.connect()` nulle part dans le code, confirmé par audit), sont désormais fonctionnels pour les trois premiers : câblés directement depuis `MainWindow` vers les comportements déjà existants — `MainWindow.new_project()` (flux `NewProjectDialog` → `WorkspaceManager.create()`, Mission 016, strictement inchangé), `MainWindow.open_project()`, et `ImagesPage.import_images()` (méthode publique déjà utilisée par le bouton d'import natif d'`ImagesPage`). Aucune logique de création, d'ouverture ou d'import n'est dupliquée dans `DashboardPage`, qui reste une vue UI pure sans référence Manager. Le bouton "Lancer un entraînement" reste visible mais devient explicitement désactivé, avec un tooltip indiquant que le lancement réel de l'entraînement n'est pas disponible dans cette version — aucun faux handler, aucun stub de Training Service, aucun nouveau Domain/Manager/Engine/Job/Plugin.

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 017 — tag et Release non encore créés à la rédaction. Voir `docs/missions/MISSION_017.md` pour l'état exact.

### Tests ajoutés (Mission 017)

- `tests/integration/test_dashboard_page.py` (nouveau, 6 tests) — widgets Qt réels, clic effectif sur les boutons via une `MainWindow` réelle, comportement observable exercé de bout en bout (seules les E/S externes sont patchées) : création de projet acceptée/annulée, ouverture de projet, import réel d'une image dans `Workspace.images`, désactivation et tooltip du bouton Training.
- **231/231 tests verts** au total (225 précédents + 6 nouveaux), aucune régression détectée.

### État du projet (Mission 017)

Aucun nouveau Domain/Manager/Service/Engine/Job/Plugin. `DashboardPage` reste une vue UI pure. Validée par la suite automatisée complète.

---

## [v0.2-mission016](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission016) — 2026-08-14

### Résumé (Mission 016)

**Mission 016 — Direct Project Folder Creation.** Le flux "Nouveau projet" repose désormais sur un dialogue dédié (`NewProjectDialog`) permettant de créer directement le dossier du nouveau projet depuis AI Studio Toolkit, sans devoir le créer au préalable dans l'Explorateur Windows : choix d'un dossier parent existant, saisie du nom, aperçu du chemin final, création automatique du dossier et de la structure Workspace standard (`project.json` + sous-répertoires), ouverture immédiate. Validation du nom (chaîne vide, caractères Windows interdits, noms réservés, espace/point final) et refus explicite d'une collision avec un dossier ou fichier déjà existant — jamais d'écrasement silencieux, revérifié à l'instant exact de la validation pour couvrir le cas d'une cible apparue entretemps sur le disque. Les flux "Ouvrir un projet" et "Sauvegarder" restent strictement inchangés.

### Tests ajoutés (Mission 016)

- `tests/integration/test_new_project_dialog.py` (31 tests) et `tests/integration/test_main_window_new_project.py` (4 tests) — **35 nouveaux tests**.
- **225/225 tests verts** au total (190 précédents + 35 nouveaux), aucune régression détectée.

### État du projet (Mission 016)

`WorkspaceManager`/`WorkspaceStorage` inchangés — ils étaient déjà capables de créer un dossier inexistant ; seule l'interface en était incapable. Validée par la suite automatisée complète et par un smoke test manuel réel dans l'application.

---

## v0.2-mission015 — 2026-08-14

### Résumé (Mission 015)

**Mission 015 — Enlarged Image Preview.** Introduction d'un composant Qt partagé, `ImagePreviewDialog` (`src/ui/dialogs/`), permettant de consulter une image en grand depuis deux consommateurs réels : `ImagesPage` (double-clic ou bouton "Voir en grand" sur une image de `Workspace.images`) et `InferencePage` (bouton "Voir en grand" sur le résultat pending introduit par Mission 014, avant toute décision Accept/Reject/Regenerate). Le dialogue est strictement passif : son constructeur ne reçoit qu'un `file_path` (`str`), jamais de référence Domain/Manager/Page, ce qui garantit structurellement qu'il ne peut jamais modifier `Workspace.images`, un état pending, ni déclencher `WORKSPACE_SAVED`. Redimensionnement dynamique avec conservation du ratio (`QPixmap.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`), plein écran par bouton et raccourci `F11` (même callback). Aucune nouvelle dépendance, aucun nouveau Domain/Manager/événement EventBus. La galerie/miniatures `ImagesPage` reste explicitement différée.

### Statistiques (Mission 015)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`52c1005`) |
| Nouveaux fichiers | `dialogs/__init__.py`, `image_preview_dialog.py`, `test_image_preview_dialog.py`, `test_images_page.py` |
| Fichiers modifiés | `images_page.py`, `inference_page.py`, `test_inference_page.py` |
| Tests ajoutés | 31 (13 + 11 + 7) |
| Total tests du projet | 190/190 verts (159 précédents + 31 nouveaux) |

### Évolutions architecturales (Mission 015)

- **`ImagePreviewDialog`** (`src/ui/dialogs/image_preview_dialog.py`, nouveau sous-package `src/ui/dialogs/`) — `QPixmap` chargé une seule fois au constructeur, jamais rechargé depuis le disque ; fichier absent/illisible géré par un message texte explicite, sans exception.
- **`ImagesPage`** — double-clic et bouton "Voir en grand" convergent vers la même méthode interne `_open_preview(file_path)` ; bouton activé/désactivé selon la sélection courante ; `update_images()` mis en conformité avec le pattern `blockSignals(True)/clear()/reconstruction/blockSignals(False)`.
- **`InferencePage`** — bouton "Voir en grand" branché sur le point d'activation déjà existant `_set_validation_buttons_enabled()`, actif uniquement en état PENDING (state machine Mission 014 strictement inchangée).
- Dialogue modal (`exec()`) : aucune action Accept/Reject/Regenerate/Generate n'est possible pendant la consultation.

### Décisions de conception (Mission 015)

- Composant strictement passif (aucune référence Domain/Manager/Page) — la garantie de non-mutation vient de la conception, pas d'un garde-fou ajouté après coup.
- Aucune nouvelle dépendance (`Pillow`/`opencv-python`, présents dans `requirements.txt` mais jamais utilisés dans `src/ui/`, ne sont pas sollicités).
- Galerie/miniatures `ImagesPage` et visualiseur système Windows délibérément non traités par cette mission.

### Correction en revue finale (Mission 015)

Une revue technique dédiée, effectuée avant clôture et fondée sur une investigation empirique (widgets Qt réels), a identifié que `QLabel.minimumSizeHint()` se calait automatiquement sur le dernier pixmap affiché : `_update_scaled_pixmap()` réassignant un pixmap redimensionné à chaque `resizeEvent`/`showEvent`, la taille minimale de la fenêtre remontait silencieusement à chaque agrandissement, empêchant tout rétrécissement ultérieur. Corrigée avant clôture par `self.image_label.setMinimumSize(1, 1)`, qui découple la contrainte de layout du pixmap courant. Un test de régression dédié a été ajouté (`test_window_can_shrink_back_after_displaying_a_large_scaled_image`), revalidé pendant le smoke test réel par un cycle manuel agrandissement → fort rétrécissement → réagrandissement.

### Hors périmètre (Mission 015)

Galerie/miniatures `ImagesPage`, visualiseur système Windows, multi-sélection `ImagesPage`, images de référence `InferencePage`, sélection multi-engine/backend, suppression/édition/renommage d'image, métadonnées d'image, annulation d'une génération en cours, historique de générations. Nouveau besoin identifié par l'usage réel de cette mission : absence de création directe de dossier lors de "Nouveau projet" (résolu depuis par Mission 016).

### Tests ajoutés (Mission 015)

`tests/integration/test_image_preview_dialog.py` (13 tests, nouveau) : image paysage/portrait valides, fichier absent, fichier invalide, redimensionnement réel avec ratio conservé, régression du bug de rétrécissement, fenêtre très petite, ouvertures/fermetures multiples, plein écran par bouton et par `F11`, fermeture directement depuis le plein écran. `tests/integration/test_images_page.py` (11 tests, nouveau) : bouton désactivé/activé selon sélection, bouton et double-clic ouvrent le même fichier, fichier absent sans mutation du Domain, consultation sans `add_images()`/`save()`, refresh réinitialisant correctement la sélection et le bouton. `tests/integration/test_inference_page.py` (30 → 37, 7 nouveaux) : bouton "Voir en grand" suivant strictement la state machine Mission 014, aucune persistance déclenchée par la simple consultation. Suite entièrement mockée, aucun accès réseau réel, aucune instance ComfyUI, aucun GPU.

Smoke test réel complet réalisé depuis l'application réelle (`src/core/main.py`), couvrant les deux consommateurs (trois images réelles dans `ImagesPage`, une génération ComfyUI réelle dans `InferencePage`), le cas du fichier absent, et une fermeture propre — aucune divergence relevée entre comportement automatisé et comportement réel observé.

### Prochaines étapes (Mission 015)

Sans engagement définitif — Mission 016 à définir selon son propre audit architectural. Nouveau besoin identifié par l'usage réel : création directe de dossier lors de "Nouveau projet" (traité depuis par Mission 016). Dettes déjà connues avant cette mission inchangées (voir Mission 014 et précédentes).

### État du projet (Mission 015)

**Mission 015 est terminée.** `ImagePreviewDialog` introduit un visualiseur d'image agrandi partagé, strictement passif, entre `ImagesPage` et `InferencePage`. 190 tests d'intégration, smoke test réel complet validé.

---

## v0.2-mission014 — 2026-08-13

### Résumé (Mission 014)

**Mission 014 — Validation post-génération avant enregistrement.** Introduction d'une étape de validation explicite entre génération et persistance dans `InferencePage` : `Generate → résultat temporaire (pending) → Preview → Accept/Reject/Regenerate`. Avant cette mission, une génération réussie était automatiquement ajoutée à `Workspace.images` dès que `GenerationWorker` émettait `finished(path)` (Mission 013) ; désormais, seule l'action explicite Accept transforme un résultat temporaire en `Image` persistée. État pending (`_pending_path`, `_pending_pixmap`) porté exclusivement par `InferencePage`, jamais partagé. Aucun nouveau Domain/Manager, `GenerationManager`/`GenerationWorker`/`ComfyUIEngine` strictement inchangés.

### Statistiques (Mission 014)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`5828c35`) |
| Nouveaux fichiers | aucun |
| Fichiers modifiés | `inference_page.py` (state machine complète), `main_window.py` (abonnement `reset_for_workspace_change`) |
| Tests ajoutés | 21 (`test_inference_page.py` : 9 → 30) |
| Total tests du projet | 159/159 verts (138 précédents + 21 nouveaux) |

### Évolutions architecturales (Mission 014)

- **State machine `InferencePage`** : INITIAL → GENERATING → PENDING → ACCEPT/REJECT/REGENERATE/ERROR, avec états dédiés pour un changement de Workspace pendant PENDING ou GENERATING, et pour le shutdown.
- **`_generation_workspace_root`** — nouvel état transitoire mémorisant le Workspace actif au lancement du cycle de génération, utilisé pour la protection contre l'enregistrement croisé entre Workspaces (voir "Correction en revue finale").
- **Aperçu** : `QLabel`/`QPixmap.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`, recalculé dans `resizeEvent`, aucune nouvelle dépendance.
- **`InferencePage.reset_for_workspace_change()`** — abonnée par `main_window.py` à `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED` (jamais `WORKSPACE_SAVED`), invalide immédiatement un pending existant dès que le contexte change.

### Décisions de conception (Mission 014)

- Aucun nouveau Domain (`GenerationResult`/`PendingImage`) — un scalaire (chemin) et une référence (racine Workspace) suffisent, portés par de simples attributs d'instance.
- `FileNotFoundError` au nettoyage du fichier pending traitée comme un succès (l'état désiré est déjà atteint) ; `OSError` réelle affiche un avertissement, avec possibilité résiduelle de fichier orphelin non résolue davantage.
- `QPixmap` non chargeable pour l'aperçu n'invalide pas le pending — l'incapacité de Qt à décoder les octets ne prouve pas que le fichier généré soit invalide ; considérée hors périmètre une validation de contenu plus poussée.

### Correction en revue finale (Mission 014)

Une revue technique dédiée, effectuée avant clôture, a identifié que ni le passage en pending ni Accept ne vérifiaient que le Workspace actif correspondait à celui actif au lancement de la génération — `WorkspaceManager.create()`/`.open()` remplaçant `current_workspace` sans jamais appeler `close()`, un résultat né dans un Workspace A aurait pu être silencieusement enregistré dans un Workspace B ouvert entre-temps. Corrigée avant clôture par la mémorisation de la racine du Workspace au lancement (`_generation_workspace_root`), une vérification à l'arrivée du résultat et à Accept, et une invalidation proactive via `reset_for_workspace_change()`. Vérifiée par tests automatisés dédiés et par le scénario E du smoke test réel.

### Hors périmètre (Mission 014)

Limite shutdown sans annulation réelle pendant une génération active (déjà connue depuis Mission 013, non résolue). Possibilité résiduelle de fichier orphelin sur échec réel de suppression. Galerie `ImagesPage`, images de référence, sélection multi-engine (déjà identifiés en Mission 013, toujours non implémentés). Nouveau besoin identifié par l'usage réel de cette mission : aperçu agrandi/plein écran (résolu depuis par Mission 015).

### Tests ajoutés (Mission 014)

`tests/integration/test_inference_page.py` étendu (9 → 30 tests, 21 nouveaux) : preview sans persistance, Accept exactement une fois (spy sur `add_images`), Reject, Regenerate, changement de Workspace pendant pending et pendant génération en cours, fichier pending disparu avant Accept, erreurs de suppression filesystem, shutdown avec pending, races `QThread` de Mission 013 toujours protégées. Suite entièrement mockée. Smoke test réel complet réalisé depuis l'application réelle, six scénarios (A à F : Accept, Reject, Regenerate, persistance/reload, changement de Workspace A→B avec pending, fermeture avec pending terminé), deux Workspaces de test dédiés, aucune divergence relevée.

### Prochaines étapes (Mission 014)

Sans engagement définitif — Mission 015 à définir selon son propre audit architectural, devant tenir compte du nouveau besoin d'aperçu agrandi/plein écran identifié par l'usage réel de cette mission (traité depuis par Mission 015).

### État du projet (Mission 014)

**Mission 014 est terminée.** `InferencePage` introduit une étape de validation explicite entre génération et persistance, avec protection structurelle contre tout enregistrement croisé entre Workspaces — défaut réel trouvé en revue technique finale et corrigé avant clôture. 159 tests d'intégration, smoke test réel complet validé (six scénarios).

---

## v0.2-mission013 — 2026-08-13

### Résumé (Mission 013)

**Mission 013 — Verticale minimale Inference.** Livraison de la première verticale fonctionnelle réelle d'AI Studio Toolkit : un utilisateur saisit un prompt dans `InferencePage`, clique sur "Générer", obtient une image réelle sans bloquer l'interface, et la retrouve dans `Workspace.images`/`ImagesPage`. Premier consommateur réel de `ComfyUIEngine` (Mission 012), via `GenerationManager` (Qt-free) et `GenerationWorker` (`QObject` déplacé dans un `QThread`, premier threading Qt du projet).

### Statistiques (Mission 013)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`78c6937`) |
| Nouveaux fichiers | `generation_manager.py`, `generation_worker.py`, `test_generation_manager.py`, `test_generation_worker.py`, `test_inference_page.py` |
| Fichiers modifiés | `comfyui_engine.py` (paramètre additif `checkpoint_name`), `main_window.py` (composition root), `inference_page.py`, `test_comfyui_engine.py` |
| Tests ajoutés | 25 (10 + 4 + 9 nouveaux fichiers + 2 adaptations `test_comfyui_engine.py`) |
| Total tests du projet | 138/138 verts (113 précédents + 25 nouveaux) |

### Évolutions architecturales (Mission 013)

- **`GenerationManager`** (`src/managers/generation_manager.py`) — Manager minimal sans collection Domain ni `active_id`, un unique flag transitoire `_busy` ; strictement Qt-free (vérifié par test) ; normalise `ComfyUIEngineError`/`OSError` en `GenerationError`.
- **`GenerationWorker`** (`src/ui/generation_worker.py`) — unique classe connaissant à la fois Qt et `GenerationManager`, idiome "Worker Object" standard (`moveToThread()`), signaux `finished(str)`/`failed(str)`.
- **`InferencePage`** devient fonctionnelle : validation minimale, bouton désactivé pendant la génération, `output_directory` recalculé depuis `workspace.root / "outputs"`. `WorkspaceManager.add_images()` appelé depuis le thread principal uniquement.
- **`main_window.py`** — composition root instanciant `ComfyUIEngine`/`GenerationManager`, avec deux constantes explicitement documentées comme propres à la machine de développement (`COMFYUI_BASE_URL`, `COMFYUI_CHECKPOINT_NAME`).
- **`ComfyUIEngine`** étendu de façon additive : `generate_image()` gagne un paramètre optionnel `checkpoint_name` — les trois primitives génériques restent strictement inchangées.

### Décisions de conception (Mission 013)

- Ownership de l'image générée : `Workspace.images`, via `WorkspaceManager.add_images()` déjà existant — aucune ligne de persistance nouvelle, modèle d'ownership Mission 011 non modifié.
- `Workspace`/`WorkspaceManager` jugés non thread-safe : toute mutation reste exécutée depuis le thread principal, jamais depuis le worker.
- Limite acceptée : shutdown sans annulation réelle (`thread.quit()+wait()` ne peut interrompre un appel réseau déjà en cours).

### Correction en revue finale (Mission 013)

Une revue technique dédiée a identifié une condition de course réelle : `worker.finished`/`worker.failed` réactivaient le bouton avant que `thread.finished → _cleanup_thread()` ne s'exécute, et `_cleanup_thread()` relisait `self._worker`/`self._thread` au moment de son exécution différée — un ancien cleanup pouvait détruire les références d'un nouveau cycle relancé entretemps. Corrigée avant clôture : `worker`/`thread` capturés par valeur dans le callback `thread.finished`, remise à `None` conditionnée à l'identité du cycle. 4 tests ajoutés, dont deux avec de vrais `QThread` et reclic immédiat, capturant tout message Qt anormal.

### Hors périmètre (Mission 013)

Limite shutdown sans annulation réelle. `ApplicationSettings.comfyui_url` toujours différé. Historique de générations, annulation, générations simultanées, sélection Dataset comme pool alternatif — non traités. Trois besoins futurs identifiés par l'usage réel : galerie/miniatures `ImagesPage`, images de référence `InferencePage`, sélection multi-engine/backend — explicitement non implémentés, non architecturés.

### Tests ajoutés (Mission 013)

`test_generation_manager.py` (10, pur Python, `ComfyUIEngine` mocké), `test_generation_worker.py` (4, `QThread` réel, `GenerationManager` mocké), `test_inference_page.py` (9, widgets Qt réels, `GenerationManager` mocké), `test_comfyui_engine.py` étendu (23 → 25) pour la nouvelle paramétrisation `checkpoint_name`. Suite entièrement mockée, aucun accès réseau réel.

Smoke test réel complet réalisé depuis l'application réelle (`src/core/main.py`), backend ComfyUI Desktop réel (`http://127.0.0.1:8000`), deux générations GPU réelles successives validées, UI responsive pendant la génération, persistance/reload vérifiée, aucune divergence relevée.

### Prochaines étapes (Mission 013)

Sans engagement définitif — Mission 014 à définir selon son propre audit architectural, devant tenir compte des trois besoins réels identifiés (galerie Images, images de référence Inference, sélection multi-engine).

### État du projet (Mission 013)

**Mission 013 est terminée.** Première verticale fonctionnelle réelle du projet : `InferencePage → GenerationManager → GenerationWorker/QThread → ComfyUIEngine → Workspace.images → ImagesPage`, validée par 138 tests automatisés et par un smoke test réel complet (deux générations GPU réussies). Une condition de course réelle a été trouvée et corrigée avant clôture.

---

## [v0.2-mission012](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission012) — 2026-08-13

### Résumé (Mission 012)

**Mission 012 — ComfyUI Engine minimal.** Introduction de la première infrastructure IA réelle du projet : `ComfyUIEngine` (`src/engines/comfyui_engine.py`), établissant un contrat technique validé entre AI Studio Toolkit et une instance serveur ComfyUI, sans introduire `Plugin`, `Service`, `AI Orchestrator`, `Job` ni UI d'exécution. Frontière retenue : `AI Studio Toolkit → ComfyUI`, jamais `→ un modèle/provider particulier` — le protocole HTTP de ComfyUI (`/prompt`, `/history`, `/view`) étant générique par construction. Trois primitives génériques (`submit`, `wait_for_result`, `download_output`) constituent le contrat réel ; `generate_image()` est une convenience method de démonstration composée strictement de ces primitives.

### Statistiques (Mission 012)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`1388f9d`) |
| Nouveaux fichiers | `engines/__init__.py`, `engines/comfyui_engine.py`, `test_comfyui_engine.py` |
| Fichiers modifiés | `docs/PROJECT_CONTEXT.md` |
| Tests ajoutés | 23 |
| Total tests du projet | 113/113 verts (90 précédents + 23 nouveaux) |

### Évolutions architecturales (Mission 012)

- **`ComfyUIEngine`** (couche Infrastructure) — `submit(workflow, client_id) -> prompt_id`, `wait_for_result(prompt_id, poll_interval) -> outputs`, `download_output(filename, subfolder, type_, output_directory) -> chemin local`. Aucune des trois ne connaît le contenu du workflow (checkpoint, LoRA, modèle, provider).
- **`generate_image()`** — convenience method de démonstration, composée strictement des trois primitives + `build_demo_workflow()` (fonction libre, hors classe).
- `ComfyUIEngine` n'importe rien de `src/domain/`, ne retourne que des `str`/`dict` — aucune image générée n'est ajoutée automatiquement à `Workspace.images`/`Dataset.images`.
- Protocole : `POST /prompt` → `GET /history/{prompt_id}` (polling, pas de WebSocket) → `GET /view`.

### Décisions de conception (Mission 012)

- ComfyUI local retenu comme premier moteur concret, décision explicite de l'architecte motivée par le besoin de sortir des abstractions hypothétiques (`Service`/`AI Orchestrator`/`Plugin`/`Engine`/`Job` génériques).
- Support architectural actuel limité à une instance serveur ComfyUI (locale ou distante) parlant le protocole `/prompt`/`/history`/`/view` — explicitement pas un client direct vers une éventuelle API Comfy Cloud hébergée (endpoints/authentification propres, non implémentés).
- `checkpoint_name` isolé dans `build_demo_workflow()`, jamais une propriété de `ComfyUIEngine`.

### Correction en revue finale (Mission 012)

Une revue technique dédiée a identifié deux divergences réelles : `wait_for_result()` considérait comme terminé tout `outputs` non vide, sans vérifier qu'une image exploitable y figurait ; `_first_image_reference()` acceptait une référence sans `filename`. Corrigées avant clôture : le polling continue jusqu'à l'apparition d'une référence image structurellement exploitable ou l'expiration du timeout ; une référence sans `filename` non vide n'est plus retournée. 7 tests ajoutés pour couvrir précisément ces cas.

### Hors périmètre (Mission 012)

Câblage UI (`InferencePage`) et le problème de threading associé — différé (traité par Mission 013). `comfyui_url`/configurabilité de l'adresse serveur dans `ApplicationSettings` — non ajouté. Client direct vers une éventuelle API Comfy Cloud hébergée, credentials cloud, gestionnaire de providers, moteurs concurrents (`GPTImageEngine`, `NanoBananaEngine`, `FluxEngine`, `SDXLEngine`) — non implémentés.

### Tests ajoutés (Mission 012)

`tests/integration/test_comfyui_engine.py` (23 tests, entièrement mockés via `unittest.mock.patch` sur `urllib.request.urlopen`) : contrat `submit()`, `wait_for_result()`, `download_output()`, `generate_image()`, et 4 tests architecturaux dédiés (absence d'import Domain, absence de connaissance provider, isolation de `checkpoint_name`, séparation primitives/démonstration). Aucun accès réseau réel, aucune instance ComfyUI, aucun GPU dans la suite automatisée.

**Validation empirique post-clôture** : après le tag `v0.2-mission012` et la **publication de la GitHub Release**, un smoke test manuel a été réalisé contre une instance ComfyUI Desktop réellement démarrée (`http://127.0.0.1:8000`, GPU NVIDIA Quadro P4000) — séquence complète `submit()`/`wait_for_result()`/`download_output()` validée sans aucun mock, image PNG valide obtenue. Ce smoke test est resté manuel et ponctuel, hors dépôt, sans modification du code versionné.

### Prochaines étapes (Mission 012)

Sans engagement définitif — Mission 013 à définir selon son propre audit architectural, le point logique le plus probable étant le choix du premier consommateur du moteur (Manager et/ou UI).

### État du projet (Mission 012)

**Mission 012 est terminée.** Première infrastructure IA réelle du projet (`src/engines/`, `ComfyUIEngine`) introduite, sans Plugin/Service/AI Orchestrator/Job/UI d'exécution. 113 tests d'intégration, tous mockés pour cette nouvelle suite. Une génération ComfyUI réelle a depuis été validée empiriquement par un smoke test manuel post-clôture, hors dépôt.

---

## v0.2-mission011 — 2026-08-13

### Résumé (Mission 011)

**Mission 011 — Image Domain.** Introduction d'une représentation Domain minimale et cohérente des images existantes (`Image`, 2 champs : `image_id`, `file_path`), en remplacement des chaînes brutes (`list[str]`) dispersées entre `Workspace.images`, `Dataset.images` et un `Character.images` mort (supprimé par cette mission — jamais lu ni écrit par aucun Manager ni aucune Page depuis son introduction). Ownership retenu (Modèle D, contextuel et structurel) : `Workspace` et chaque `Dataset` possèdent chacun leur propre pool `list[Image]`, strictement indépendants, sans registre global ni référence croisée. Première migration du projet portant sur des données réellement présentes (`list[str]` → `list[Image]`), rétrocompatible, sans réécriture forcée au chargement.

*Note de clôture Git* : le tag `v0.2-mission011` ne cible pas directement le commit fonctionnel (`242453e`) mais le commit documentaire final de clôture (`c23283c`) — trois commits complémentaires (`26606e3`, `2634518`, `c23283c`) ont été nécessaires après le commit fonctionnel pour stabiliser les références documentaires, un piège d'auto-référence (documenter un hash pas encore créé) rencontré et résolu à cette occasion, à l'origine du principe de non-auto-référence désormais appliqué (`docs/PROJECT_CONTEXT.md`).

### Statistiques (Mission 011)

| Indicateur | Valeur |
|---|---|
| Commits | commit fonctionnel unique (`242453e`) + 3 commits documentaires de clôture (`26606e3`, `2634518`, `c23283c` — ce dernier ciblé par le tag) |
| Nouveaux fichiers | `domain/image.py`, `test_image_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `dataset.py`, `character.py`, `workspace_manager.py`, `dataset_manager.py`, `images_page.py`, `datasets_page.py`, `test_dataset_roundtrip.py`, `test_training_roundtrip.py` |
| Tests ajoutés | 10 |
| Total tests du projet | 90/90 verts (80 précédents + 10 nouveaux) |

### Évolutions architecturales (Mission 011)

- **`Image`** (`src/domain/image.py`) — dataclass Qt-indépendante, 2 champs (`image_id`, `file_path`), domaine passif.
- **`Character.images`** supprimé — relation `Character → Image` restant strictement transitive via `Character → Dataset → Image`.
- **`WorkspaceManager.add_images()`/`DatasetManager.add_images()`** adaptés pour construire des `Image` au lieu de chaînes brutes ; déduplication prospective continue de fonctionner par `file_path`.
- **Aucun `ImageManager`** introduit — `Image` n'a pas de cycle de vie CRUD autonome (pas de sélection, pas d'`active_id`), contrairement à `Model`/`Workflow`/`Settings`/`ApplicationSettings`.
- **`Image.list_from_data()`**, partagée entre `Workspace.from_dict()` et `Dataset.from_dict()`, gère la conversion `list[str]` legacy → `list[Image]` à la lecture uniquement.

### Décisions de conception (Mission 011)

- Modèle d'ownership retenu après audit dédié comparant quatre modèles (Workspace-owned seul, Character-owned seul, Dataset-owned seul, hybride contextuel) contre le comportement réel du code, pas seulement le Blueprint — seul modèle ne rompant aucun comportement fonctionnel déjà existant.
- Un `uuid4()` est généré pour chaque entrée `str` legacy convertie ; identifiant stable dès la première sauvegarde au nouveau format, non stable avant (comportement attendu, vérifié explicitement).
- Déduplication strictement prospective (nouveaux imports via `add_images()`), jamais rétroactive sur des données déjà migrées ; doublons historiques préservés comme instances `Image` distinctes.

### Correction en revue finale (Mission 011)

Une revue technique dédiée à `Image.list_from_data()`, effectuée avant commit, a révélé que la première implémentation acceptait silencieusement tout `dict`, sans vérifier la validité de `file_path` — `{}` aurait produit une `Image` avec `file_path=""`. Corrigée avant tout commit : une entrée `dict` n'est conservée que si `file_path` est un `str` non vide ; une entrée `str` legacy n'est conservée que si elle est non vide. Test de régression ajouté (`test_list_from_data_filters_dicts_without_usable_file_path`).

### Hors périmètre (Mission 011)

`BasePage` (code mort). Ambiguïté `Training` vs `Training History`. Incohérences documentaires `Job` dans le Blueprint. Support Linux/macOS non vérifié pour `ApplicationSettingsStorage`. `Generation`, exécution réelle de `Job`, `Service`, `Plugin`, `Engine`, `AI Orchestrator`. Suppression individuelle d'une `Image`. Tout traitement physique de fichier (copie, redimensionnement, thumbnailing).

### Tests ajoutés (Mission 011)

`tests/integration/test_image_roundtrip.py` (10 tests) : défauts/round-trip Domain, migration Workspace et Dataset, round-trip nouveau format avec conservation exacte des `image_id`, stabilité des identifiants après sauvegarde/réouverture réelle, déduplication prospective par `file_path`, indépendance prouvée des deux pools (même `file_path`, deux instances, deux `image_id`), suppression de `Character.images`, filtrage explicite des `dict` sans `file_path` exploitable.

### Prochaines étapes (Mission 011)

Sans engagement définitif — Mission 012 à définir selon la roadmap/Blueprint ; le prérequis architectural le plus probable pour une future mission Generation reste la chaîne `Service → AI Orchestrator → Plugin → Engine`, entièrement absente du code à ce jour.

### État du projet (Mission 011)

**Mission 011 est terminée.** `Image` devient la 11ᵉ entité Domain du projet, premier pattern d'ownership contextuel (deux pools indépendants d'un même type, sans registre partagé). Première migration du projet portant sur des données réellement présentes. 90 tests d'intégration.

---

## [v0.2-mission010](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission010) — 2026-08-12

### Résumé (Mission 010)

**Mission 010 — Application Settings Domain.** Introduction d'`ApplicationSettings`, objet Domain **Application-level** — un niveau de configuration distinct de `Workspace.settings` (Mission 009), jamais persisté dans `project.json`. Domain minimal : `python_path`, `comfyui_path`, `onetrainer_path`. Stockage dédié dans un fichier séparé, hors de tout Workspace :

```
Workspace                          Application
└── Settings                       └── ApplicationSettings
    ├── theme                          ├── python_path
    └── language                       ├── comfyui_path
         ↓                             └── onetrainer_path
     project.json                           ↓
                                     application_settings.json
```

Ces deux périmètres restent strictement indépendants : Managers, cycles de vie, persistances et canaux de rafraîchissement distincts, sans aucun couplage.

### Statistiques (Mission 010)

| Indicateur | Valeur |
|---|---|
| Commits | 5 |
| Nouveaux fichiers | `application_settings.py`, `application_settings_storage.py`, `application_settings_manager.py`, `test_application_settings_roundtrip.py` |
| Fichiers modifiés | `settings_page.py`, `main_window.py`, `test_settings_roundtrip.py` |
| Tests ajoutés | 13 |
| Total tests du projet | 80/80 verts (67 existants + 13 nouveaux) |

### Évolutions architecturales (Mission 010)

- **`ApplicationSettings`** (`src/domain/application_settings.py`) — dataclass Qt-indépendante, 3 champs, domaine passif.
- **`ApplicationSettingsStorage`** (`src/infrastructure/storage/application_settings_storage.py`) — répertoire résolu via `%LOCALAPPDATA%\AIStudioToolkit\` sous Windows (comportement Windows spécifiquement ; repli déterministe `Path.home()/AppData/Local/AIStudioToolkit` si `LOCALAPPDATA` est absent), fichier `application_settings.json`. Lecture non bloquante : fichier absent, vide, JSON invalide, racine non-`dict` ou erreur `OSError` → valeurs par défaut, jamais d'exception au démarrage. Écriture atomique (fichier temporaire dans le même répertoire, `flush()` + `os.fsync()`, puis `os.replace()`) : le dernier fichier valide est garanti intact si une sauvegarde échoue ; `ApplicationSettingsStorageError` levée dans ce cas.
- **`ApplicationSettingsManager`** (`src/managers/application_settings_manager.py`) — `settings` (lecture) et `update(python_path=None, comfyui_path=None, onetrainer_path=None)` (écriture idempotente, multi-champs en une seule sauvegarde). Stratégie "candidat d'abord" : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire — un échec de sauvegarde laisse donc la mémoire strictement inchangée. Aucune dépendance à `WorkspaceManager`.
- **`SettingsPage`** — deux sections indépendantes (Workspace / Application), chacune avec son propre bouton "Enregistrer". La section Application reste disponible et activée en permanence, y compris sans aucun Workspace ouvert.
- **Événement `application_settings.updated`** — publié uniquement après une sauvegarde réussie ; aucun événement sur mise à jour idempotente ou échec.

### Décisions de conception (Mission 010)

- Séparation stricte des scopes : `python_path`/`comfyui_path`/`onetrainer_path` ne sont jamais écrits dans `project.json` ; `theme`/`language` ne sont jamais écrits dans `application_settings.json`.
- Aucune migration automatique depuis `Workspace.settings` — les deux stockages n'ont jamais été liés, aucune donnée à transférer.
- Résolution du répertoire de configuration en Python standard uniquement (`os`/`pathlib`) — aucune dépendance nouvelle, aucun import Qt dans Infrastructure/Managers.
- Aucun `settings_id` — singleton, même principe que `Settings`/`Workspace`.
- Un événement Workspace ne rafraîchit jamais la section Application, et réciproquement — vérifié dans les deux sens.

### Hors périmètre (Mission 010)

Non implémentés : validation d'existence des chemins, lancement réel de Python/ComfyUI/OneTrainer, clés API, secrets, chiffrement, `Job`, `Engine`, `Plugin`, `Service`, `AI Orchestrator`, `Image` Domain.

### Tests ajoutés (Mission 010)

`tests/integration/test_application_settings_roundtrip.py` (13 tests) : round-trip et défauts du Domain, résolution de `default_directory()` (`LOCALAPPDATA` simulé + repli), matrice de compatibilité de `load()`, round-trip Unicode réel, écriture atomique et préservation du dernier fichier valide en cas d'échec, chargement/idempotence/atomicité de `ApplicationSettingsManager`, cohérence mémoire/disque après échec de sauvegarde, persistance entre deux instances, indépendance totale vis-à-vis de `WorkspaceManager`, cycle de vie complet de la section Application dans `SettingsPage`, étanchéité bidirectionnelle entre les deux sections, absence de duplication d'abonnements. `tests/integration/test_settings_roundtrip.py` adapté à la marge (signature de `SettingsPage`, aucune nouvelle assertion).

### Prochaines étapes (Mission 010)

Sans engagement définitif — Mission 011 à définir selon la roadmap/Blueprint. Dettes restant indépendantes : `Job`/`Engine`/`Plugin`/`Service`/`AI Orchestrator`, migration `Image`, ambiguïté `Training`/`Training History`, références mortes `04_DATA_MODEL.md`/`05_CHARACTER_SYSTEM.md`, nettoyage de `BasePage`.

### État du projet (Mission 010)

**Mission 010 est terminée.** L'application dispose désormais de deux niveaux de préférences strictement séparés — Workspace Settings (`project.json`) et Application Settings (stockage local dédié) — et de 80 tests d'intégration.

---

## [v0.2-mission009](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission009) — 2026-08-12

### Résumé (Mission 009)

**Mission 009 — Settings Domain (Workspace).** Introduction de `Settings`, entité Domain Workspace-owned prenant la forme d'un **singleton** (`Workspace.settings: Settings`) plutôt que d'une collection — aucun identifiant, aucune sélection, aucun événement dédié. Domain minimal : `theme`, `language`. `Workspace.settings` (`dict` non typé depuis Mission 001) est converti vers ce type avec une compatibilité défensive stricte par garde de type, et `SettingsPage` devient une page réelle, remplaçant les trois champs de configuration machine-locale (`python_path`, `comfyui_path`, `onetrainer_path`) — actés comme relevant d'un futur niveau Application Settings, distinct du Workspace.

Le travail a été mené en 6 commits atomiques. Le premier comble une dette de couverture de tests identifiée lors de l'audit d'ouverture de mission (suppression d'un Character possédant Dataset et Training associés) — le comportement existant s'est révélé correct, aucun changement de `CharacterManager` n'a été nécessaire.

### Statistiques (Mission 009)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `settings.py`, `settings_manager.py`, `test_settings_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `settings_page.py`, `main_window.py`, `test_character_roundtrip.py` |
| Tests ajoutés | 10 (1 régression Character/Dataset/Training + 9 Settings) |
| Total tests du projet | 67/67 verts (57 existants + 10 nouveaux) |

### Évolutions architecturales (Mission 009)

- **`Settings`** (`src/domain/settings.py`) — dataclass Qt-indépendante, 2 champs (`theme`, `language`), domaine passif.
- **`Workspace.settings: Settings`** — remplace le `dict` non typé. Désérialisation par garde de type explicite (`isinstance(..., dict)`) plutôt que par simple vérité (`or {}`), afin de rejeter aussi les valeurs truthy mal typées (`42`, `"abc"`, `[...]`), pas seulement les valeurs falsy.
- **`SettingsManager`** (`src/managers/settings_manager.py`) — `settings` (lecture) et `update(theme=None, language=None)` (écriture idempotente, multi-champs en une seule sauvegarde). Aucune dépendance à `EventBus` : ce Manager ne publie ni ne s'abonne à rien.
- **`SettingsPage`** — page réelle : `theme`/`language`, bouton "Enregistrer" explicite, désactivée sans Workspace, texte explicatif indiquant que ces préférences ne sont pas encore appliquées à l'interface.

### Décisions de conception (Mission 009)

- Ownership Workspace-owned, singleton — pas de `settings_id` (même principe que `Workspace` lui-même, qui n'a pas de `workspace_id`).
- `python_path`/`comfyui_path`/`onetrainer_path` jugés Application-level (chemins propres à la machine), jamais Workspace-level — retirés de `SettingsPage`, non migrés, aucun fichier Application Settings créé.
- Clés inconnues sous `settings` (y compris les trois anciennes clés machine-locale) silencieusement ignorées, jamais conservées — décision consciente du passage à un schéma typé, pas un bug de sérialisation.
- Aucun événement Settings dédié : `SettingsManager.update()` → `WorkspaceManager.save()` → `WORKSPACE_SAVED`, seul canal de notification de `SettingsPage`.
- Sauvegarde exclusivement par bouton explicite ; une saisie non enregistrée est silencieusement abandonnée au changement de Workspace, sans dialogue de confirmation.

### Hors périmètre (Mission 009)

Non implémentés, différés : Application Settings, Character/Engine/Plugin/Cloud Settings, application réelle du thème à Qt, localisation réelle de l'interface, événements `SettingChanged`/`SettingReset`/`SettingImported`/`SettingExported`.

### Tests ajoutés (Mission 009)

`tests/integration/test_character_roundtrip.py` (+1) : suppression d'un Character avec Dataset référencé par un Training — aucune donnée orpheline, aucune exception. `tests/integration/test_settings_roundtrip.py` (9) : round-trip et défauts du Domain `Settings`, compatibilité historique complète de `Workspace.settings` (absent/`{}`/`null`/mauvais type/clés inconnues), idempotence et atomicité multi-champs de `SettingsManager.update()`, persistance réelle fermeture/réouverture, isolation stricte entre deux Workspaces, non-mutation des autres collections, cycle de vie complet de `SettingsPage`, absence de duplication d'abonnements.

### Prochaines étapes (Mission 009)

Sans engagement définitif — Mission 010 à définir selon la roadmap/Blueprint. Dettes restant indépendantes, non transformées en feuille de route : migration `Image` vers un vrai Domain object, ambiguïté `Training`/`Training History`, références mortes `04_DATA_MODEL.md`/`05_CHARACTER_SYSTEM.md`, nettoyage de `BasePage`.

### État du projet (Mission 009)

**Mission 009 est terminée.** L'application dispose désormais de `Settings`, entité Domain Workspace-owned sous forme de singleton, avec persistance et restauration réelles des préférences de Workspace, et 67 tests d'intégration.

---

## [v0.2-mission008](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission008) — 2026-08-11

### Résumé (Mission 008)

**Mission 008 — Training Domain.** La Mission 008 introduit `Training` comme nouvelle entité Domain Character-owned. Elle rejoint `Dataset`, `LoRA` et `Prompt` parmi les entités possédées par `Character` (`Character.trainings: list[Training]`). L'ownership retenu s'appuie sur `04_DOMAIN_MODEL.md` §4, qui place explicitement `Trainings` sous `Characters` dans la hiérarchie d'entités ; les arbres structurels de `00_VISION.md`, `01_PRODUCT_REQUIREMENTS.md` et `02_ARCHITECTURE.md` ne nomment à cet emplacement que `Training History` — un concept distinct, non implémenté par cette mission — jamais `Training` elle-même. Cette divergence documentaire est signalée, non résolue.

`Training` introduit également le premier mécanisme d'intégrité référentielle inter-entités du projet : un Dataset du personnage actif référencé par au moins un Training ne peut pas être supprimé tant que cette référence existe.

Le travail a été mené en 6 commits fonctionnels atomiques, chacun avec rapport d'impact validé avant exécution.

### Statistiques (Mission 008)

| Indicateur | Valeur |
|---|---|
| Commits fonctionnels | 6 |
| Nouveaux fichiers | `training.py`, `training_manager.py`, `training_page.py`, `test_training_roundtrip.py` |
| Fichiers modifiés | `character.py`, `dataset_manager.py`, `datasets_page.py`, `main_window.py` |
| Tests Training ajoutés | 11 (`test_training_roundtrip.py`) |
| Total tests du projet | 57/57 verts (46 existants + 11 nouveaux) |

### Évolutions architecturales (Mission 008)

- **`Training`** (`src/domain/training.py`) — dataclass Qt-indépendante, 3 champs (`training_id`, `name`, `dataset_id`), domaine passif. Aucun `character_id` stocké — l'appartenance est implicite via `Character.trainings`, même principe que `Dataset`/`LoRA`/`Prompt`. `dataset_id` est en revanche une vraie référence inter-entités, matérialisée en champ.
- **`Character.trainings`** — nouveau champ `list[Training]`, filtrage défensif `isinstance(t, dict)` à la désérialisation (compatibilité, pas migration — le champ n'a jamais existé sous aucune forme antérieure).
- **`TrainingManager`** (`src/managers/training_manager.py`) — `create(name, dataset_id)`, `select(training_id)`, `delete(training_id)`, `list_trainings()`, `active_training_id` (runtime-only, non persisté, réinitialisé sur changement de personnage et de workspace — pattern Character-owned identique à `Dataset`/`Prompt`). La validation de `dataset_id` est strictement limitée à `active_character.datasets` : un Dataset existant mais appartenant à un autre personnage est refusé. Aucune méthode `update_*()` — Training n'a pas de champ éditable en place.
- **Événements réellement publiés** : `training.created`, `training.selected`, `training.deleted`. Aucun autre événement Training n'existe dans le code.
- **Intégrité référentielle Dataset → Training** (`DatasetManager.is_referenced_by_training()` + garde dans `DatasetManager.delete()`) — un Dataset du personnage actif référencé par au moins un Training ne peut pas être supprimé tant que cette référence existe : pas de cascade, aucun Training supprimé automatiquement, aucun `dataset_id` réécrit. Le Dataset redevient supprimable une fois tous les Trainings qui le référencent supprimés. `DatasetsPage.delete_dataset()` effectue un contrôle préalable pour afficher un message explicite ; `DatasetManager.delete()` réapplique la même règle indépendamment de l'UI (défense en profondeur).
- **`TrainingPage`** — interface CRUD de définition de sessions d'entraînement : lister, créer (avec sélection du Dataset source via `QInputDialog`, noms de Dataset dupliqués désambiguïsés par un fragment de `dataset_id`), sélectionner, supprimer, afficher le Dataset associé. Une référence historique vers un Dataset supprimé s'affiche comme `"Dataset introuvable [dataset_id]"`, sans lever d'exception. Aucun bouton de lancement, aucune console — ce n'est pas un moteur d'entraînement.

### Décisions de conception (Mission 008)

- Ownership Character-owned retenu avec un niveau de preuve Blueprint plus nuancé que pour `Model`/`Workflow` (voir Résumé) — décision documentée, pas présentée comme une certitude absolue.
- Aucun `character_id` sur `Training` — ownership implicite par containment, cohérent avec `Dataset`/`LoRA`/`Prompt`.
- Aucune suppression en cascade lorsqu'un Dataset référencé est visé par une suppression — le refus est la seule réponse, jamais une correction automatique des données.
- `TrainingPage` est la première Page du projet dépendante de deux Managers en lecture (`training_manager` pour les mutations, `dataset_manager` en lecture seule pour peupler le sélecteur) — orchestration au niveau Presentation, aucune dépendance Manager-à-Manager introduite.
- Suppression volontaire du bouton "Lancer l'entraînement" et de la console placeholder hérités du prototype initial, pour que l'interface ne suggère aucune capacité d'exécution non implémentée.

### Hors périmètre (Mission 008)

Non implémentés, différés : `Training Engine`, `Job`, lancement réel d'un entraînement, pause/reprise/annulation, progression, loss, logs d'exécution, `Output LoRA`, `Base Model`, epochs, learning rate, optimizer, batch size, résolution, événements `TrainingStarted`/`TrainingPaused`/`TrainingResumed`/`TrainingFinished`/`TrainingCancelled`/`TrainingFailed`. Aucun de ces éléments n'existe dans le code livré par cette mission.

### Tests ajoutés (Mission 008)

`tests/integration/test_training_roundtrip.py` (11 tests) : round-trip et valeurs par défaut du Domain `Training`, compatibilité de `Character.trainings` (clé absente/`[]`/`None`/liste mixte), création valide et persistance réelle, refus d'un `dataset_id` vide ou inexistant et d'un Dataset appartenant à un autre personnage (atomicité complète : aucune mutation, aucun `save()`, aucun événement), réinitialisation du contexte au changement de personnage/workspace, suppression active/non-active/invalide avec persistance, cycle complet d'intégrité référentielle Dataset → Training (blocage, absence de cascade, déblocage), isolation des autres collections (y compris du Dataset référencé lui-même), reconstruction de `TrainingPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact Dashboard/Images.

### Prochaines étapes (Mission 008)

Sans engagement définitif :

- Mission 009 — à définir selon la roadmap/Blueprint.
- *(Dette documentaire Blueprint constatée pendant l'audit d'ouverture de mission, indépendante du Domain Training : `01_PRODUCT_REQUIREMENTS.md` référence `04_DATA_MODEL.md` et `05_CHARACTER_SYSTEM.md`, deux fichiers absents de `docs/blueprint/`. Correction laissée à une décision documentaire séparée.)*

### État du projet (Mission 008)

**Mission 008 est terminée.** L'application dispose désormais de `Training` comme nouvelle entité Domain Character-owned, aux côtés de `Dataset`, `LoRA` et `Prompt`, avec une première intégrité référentielle inter-entités (Dataset → Training), et 57 tests d'intégration.

---

## [v0.2-mission007](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission007) — 2026-08-11

### Résumé (Mission 007)

**Mission 007 — Workflow Domain.** Introduction de l'entité `Workflow`, sixième objet du Domain Model et deuxième ressource explicitement Workspace-owned après `Model` (`Workspace.workflows`), conformément à l'architecture "Workflow Library" retenue pour cette mission (`04_DOMAIN_MODEL.md` §14, `02_ARCHITECTURE.md` §6/§10/§12). Domain minimal : `workflow_id`, `name`, `file_path`. `file_path` est un choix d'implémentation propre à cette mission — le Blueprint ne nomme aucun attribut de type chemin pour `Workflow` (contrairement à `Model`, dont `file_path` traduit directement l'attribut "Installation Path") ; il permet uniquement de référencer un fichier externe, sans parsing, validation, détection d'origine ni exécution de son contenu.

Le travail a été mené en 5 commits atomiques, chacun avec rapport d'impact validé avant exécution. *(Le commit `cb60856`, situé chronologiquement entre la clôture de la Mission 006 et l'ouverture de cette mission, est une correction documentaire post-publication relative à la Mission 006 — il n'appartient pas à la Mission 007.)*

### Statistiques (Mission 007)

| Indicateur | Valeur |
|---|---|
| Commits | 5 |
| Nouveaux fichiers | `workflow.py`, `workflow_manager.py`, `workflows_page.py`, `test_workflow_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 9 (8 habituels + 1 dédié à l'isolation des collections Workspace) |
| Total tests du projet | 46/46 verts (37 existants + 9 nouveaux) |

### Évolutions architecturales (Mission 007)

- **`Workflow`** (`src/domain/workflow.py`) — dataclass Qt-indépendant, 3 champs (`workflow_id`, `name`, `file_path`), domaine passif.
- **`Workspace.workflows`** — nouveau champ `list[Workflow]` ; aucune conversion de type (contrairement à `models`/`datasets`/`loras`/`prompts`), le champ n'ayant jamais existé sous aucune forme auparavant. Sérialisation en liste de dictionnaires (`to_dict()`), désérialisation avec filtrage défensif `isinstance(w, dict)` (compatibilité, pas migration). Un `project.json` antérieur à cette mission, sans clé `"workflows"`, se charge normalement et produit `workflows == []`.
- **`WorkflowManager`** (`src/managers/workflow_manager.py`) — CRUD (`create`, `select`, `delete`), sélection via `active_workflow_id` (runtime-only), `update_file_path()` strictement idempotent (chaîne vide acceptée comme valeur légitime). Persistance déléguée à `WorkspaceManager.save()`. **Aucune dépendance à `CharacterManager`**, deuxième Manager du projet dans ce cas après `ModelManager`.
- **Événements réellement publiés** : `workflow.created`, `workflow.selected`, `workflow.deleted`. `update_file_path()` ne publie aucun événement dédié — la mutation est suivie de `WorkspaceManager.save()`, qui émet `workspace.saved` (seul mécanisme notifiant l'UI de ce changement). Ni `workflow.updated`, ni `workflow.imported`, ni `workflow.executed` (évoqués par le Blueprint §14) ne sont implémentés.
- **`WorkflowsPage`** — nouvelle page (`workflows_page.py`), création/sélection/suppression, association d'un fichier via `QFileDialog` (filtre `Workflows (*.json)`), affichage en lecture seule de `file_path`. Fonctionne indépendamment de l'existence ou de la sélection d'un `Character` — vérifié par exécution.
- **Intégration Sidebar/MainWindow** — nouvelle entrée "Workflows" insérée immédiatement après "Models" (regroupement des deux ressources Workspace-owned), alignement Sidebar/`QStackedWidget` vérifié sur les 11 entrées.
- **Isolation Character** — vérifiée par preuve inversée par exécution : la création, sélection ou suppression d'un `Character` n'a strictement aucun effet sur `active_workflow_id`, `WorkflowsPage`, ni sur les collections `workspace.models`/`.datasets`/`.loras`/`.characters`.

### Décisions de conception (Mission 007)

- `file_path` : choix d'implémentation minimal de Mission 007 permettant l'association à un fichier externe. Non implémenté dans Mission 007 / différé pour toute notion de parsing, validation ou exécution du contenu référencé. Ce n'est pas la traduction d'un attribut Blueprint nommé.
- Les formats `ComfyUI Workflow`, `Forge Preset`, `Fooocus Preset` (`01_PRODUCT_REQUIREMENTS.md`, "Workflow Library", priorité P1) sont les cas d'usage ayant motivé le filtre `*.json` du sélecteur de fichier — cela ne constitue **pas** une prise en charge fonctionnelle de ces formats : le fichier n'est ni ouvert, ni analysé, ni exécuté.
- **Ownership des workflows** — Mission 007 implémente `Workflow` comme ressource appartenant au `Workspace` (`Workspace.workflows`), conformément à l'architecture de Workflow Library retenue pour cette mission. Une formulation de `01_PRODUCT_REQUIREMENTS.md` §11 indique qu'un Character stocke ses propres workflows ; cette divergence documentaire est identifiée et laissée à une clarification architecturale ultérieure. Aucun couplage `WorkflowManager` ↔ `CharacterManager` n'est introduit dans Mission 007.
- `create()` reste un miroir strict de `ModelManager`/`DatasetManager`/`LoRAManager`/`PromptManager` : aucune validation de nom côté Manager, aucune sélection automatique après création.
- Attributs Blueprint `Description`, `Compatible Engine`, `Inputs`, `Outputs`, `Parameters`, `Version`, `Category`, `Author`, `Thumbnail`, `Tags`, `Metadata` : non implémentés dans Mission 007 / différés — aucun engagement n'est pris sur leur forme future.

### Tests ajoutés (Mission 007)

`tests/integration/test_workflow_roundtrip.py` (9 tests) : round-trip et valeurs par défaut du Domain `Workflow` (y compris compatibilité historique explicite d'un `project.json` sans clé `"workflows"`), cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture avec persistance disque réelle, idempotence complète d'`update_file_path()`, suppression avec persistance, preuve inversée d'isolation Character, reconstruction de `WorkflowsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact Dashboard/Images, et un test dédié vérifiant qu'aucune opération `WorkflowManager` ne mute `workspace.models`/`.datasets`/`.loras`/`.characters`.

### Prochaines étapes (Mission 007)

Sans engagement définitif :

- Clarification future de la tension documentaire Workspace-owned / Character-owned identifiée dans `01_PRODUCT_REQUIREMENTS.md` §11.
- Mission 008 — à définir selon la roadmap/Blueprint.

### État du projet (Mission 007)

**Mission 007 est terminée.** L'application dispose désormais de six entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`, `Model`, `Workflow`), 46 tests d'intégration, et deux ressources Workspace-owned cohérentes (`Model`, `Workflow`).

---

## [v0.2-mission006](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission006) — 2026-08-11

### Résumé (Mission 006)

**Mission 006 — Model Domain.** Introduction de l'entité `Model`, cinquième objet du Domain Model après `Character`, `Dataset`, `LoRA` et `Prompt` — et la première rattachée exclusivement au `Workspace`, pas au `Character`. Cette conclusion a été démontrée par huit citations Blueprint indépendantes (`04_DOMAIN_MODEL.md` §4/§5/§10/§27/§28, `02_ARCHITECTURE.md` §10/§11/§12), toutes convergentes : *"Models belong to the Workspace Library."* Le Domain reste volontairement minimal (`model_id`, `name`, `file_path`), dans la continuité directe de `Dataset`/`Prompt`.

Conséquence architecturale majeure : `ModelManager` est le **premier Manager du projet sans dépendance à `CharacterManager`**. `active_model_id` ne se réinitialise que sur les événements de cycle de vie du workspace, jamais sur un changement de personnage — l'inverse exact de ce qui avait été vérifié pour `LoRAManager`/`PromptManager`, et démontré ici par une preuve comportementale par exécution dédiée.

Le travail a été mené en 6 commits atomiques, chacun avec rapport d'impact validé avant exécution.

### Statistiques (Mission 006)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `model.py`, `model_manager.py`, `test_model_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `models_page.py` (placeholder statique → page réelle), `main_window.py` |
| Tests d'intégration ajoutés | 8 (7 habituels + 1 dédié au round-trip et aux valeurs par défaut du Domain `Model`) |
| Total tests du projet | 37/37 verts (29 existants + 8 nouveaux) |

### Évolutions architecturales (Mission 006)

- **`Model`** (`src/domain/model.py`) — dataclass Qt-indépendant, 3 champs (`model_id`, `name`, `file_path`), domaine passif.
- **`Workspace.models`** — `list` (non typé, jamais peuplé) → `list[Model]` ; aucune preuve historique de migration nécessaire au sens strict (le champ n'avait jamais été typé, contrairement aux conversions `list[str]` précédentes), même principe de compatibilité défensive (`isinstance(m, dict)`).
- **`ModelManager`** (`src/managers/model_manager.py`) — CRUD, sélection, `update_file_path()` (miroir du contrat d'idempotence de `update_text()`) ; **aucune dépendance à `CharacterManager`**, `active_model_id` réinitialisé uniquement sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED`.
- **`ModelsPage`** — remplace le placeholder à liste statique (`"Flux"`, `"SDXL"`...) ; sélection de fichier via `QFileDialog.getOpenFileName` (singulier) plutôt que le pattern d'import multi-fichiers ; fonctionne sans qu'aucun personnage n'existe.

### Décisions de conception (Mission 006)

- `Model` rattaché exclusivement au `Workspace`, jamais au `Character` — démontré par le Blueprint, pas supposé.
- `file_path` scalaire, pas une liste — nommage aligné sur la convention déjà en place dans le projet (`LoRA.files`, `lora_page.py`) pour désigner un chemin de fichier individuel.
- `create()` reste un miroir strict des trois Managers précédents : **aucune validation de nom** côté Manager, cette responsabilité reste exclusivement dans la Page — décision explicite pour ne pas introduire de divergence où `Model` deviendrait plus robuste que `Dataset`/`LoRA`/`Prompt`.
- Pas de sélection automatique après `create()` — comportement déjà existant pour les trois domaines précédents, reproduit à l'identique plutôt que "corrigé" à l'occasion de cette mission.
- Chaîne vide (`""`) traitée comme valeur légitime de `file_path` ("aucun fichier associé"), pas une erreur à valider.
- Hors périmètre, différé et non abandonné : scan automatique de fichiers, métadonnées du Domain (`provider`, `hash`, `architecture`, `thumbnail`...), `Character.favorite_models`.

### Tests ajoutés (Mission 006)

`tests/integration/test_model_roundtrip.py` (8 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_file_path()` (y compris la chaîne vide comme changement réel), suppression avec persistance, **preuve inversée** qu'un changement de personnage ne réinitialise jamais `active_model_id`, reconstruction de `ModelsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images, et un test dédié au round-trip `to_dict()`/`from_dict()` du Domain `Model` (valeurs par défaut, clé absente, filtrage défensif sur liste mixte).

### Prochaines étapes (Mission 006)

Sans engagement définitif :

- *(Correction post-publication, audit Mission 007 : la carte Dashboard "Models" ne nécessitait en réalité aucun correctif — sa lecture de `Workspace.models` était déjà correcte depuis la Mission 001 ; seule la donnée était vide avant cette mission. L'affirmation initiale ci-dessus était erronée.)*
- Poursuite du Domain Model : `Job`, `Engine`, `Plugin`, couche Services — périmètre exact à préciser dans son propre rapport d'impact.

### État du projet (Mission 006)

**Mission 006 est terminée.** L'application dispose désormais de cinq entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`, `Model`), 37 tests d'intégration, et un premier pattern architectural "ressource partagée au niveau Workspace" validé et documenté.

---

## [v0.2-mission005](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission005) — 2026-08-11

### Résumé (Mission 005)

**Mission 005 — Prompt Domain.** Introduction de l'entité `Prompt`, quatrième objet du Domain Model après `Character`, `Dataset` et `LoRA`, positionnée dans la hiérarchie `Character → Prompt Library` (`docs/blueprint/04_DOMAIN_MODEL.md` §13). Contrairement à l'extension volontaire de `LoRA` en Mission 004, le Domain `Prompt` revient à un périmètre strictement minimal (`prompt_id`, `name`, `text`), cohérent avec la discipline appliquée à `Character`/`Dataset`. Les catégories de prompts prévues par le Blueprint (`Master Prompt`, `Negative Prompt`, `Generation Prompt`, `Training Prompt`, `Template Prompt`, `Dynamic Prompt`...) sont **explicitement différées, non abandonnées** — décision d'architecture documentée directement dans le code (`src/domain/prompt.py`) : leur ajout n'aura de sens que le jour où un consommateur réel existera (pipeline de génération, entraînement, bibliothèque de prompts filtrable), et ne nécessitera aucune migration puisqu'il s'agirait d'un simple ajout de champ scalaire avec valeur par défaut.

Le travail a été mené en 7 commits atomiques, chacun avec rapport d'impact validé avant exécution. Comme pour les Missions 003/004, deux points sensibles ont fait l'objet d'une preuve comportementale par exécution plutôt que par seule lecture de code : l'indépendance de deux instances de `PromptManager` vis-à-vis de l'`EventBus`, et l'idempotence stricte du contrat `update_text()` (aucune sauvegarde ni événement publié lorsque le texte est inchangé).

### Statistiques (Mission 005)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `prompt.py`, `prompt_manager.py`, `prompts_page.py`, `test_prompt_roundtrip.py` |
| Fichiers modifiés | `dashboard_page.py`, `character.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 7 |
| Bug corrigé | Carte Dashboard "LoRA" lisait le champ vestigial `Workspace.loras` au lieu d'agréger `Character.loras` (même bug que "Datasets" en Mission 004, corrigé en ouverture de mission) |
| Total tests du projet | 29/29 verts (22 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 005)

- **`Prompt`** (`src/domain/prompt.py`) — dataclass Qt-indépendant, 3 champs (`prompt_id`, `name`, `text`), domaine passif.
- **`Character.prompts`** — `list[str]` → `list[Prompt]` ; migration prouvée inutile par recherche exhaustive de l'historique Git, même méthodologie que `Character.datasets`/`Character.loras`.
- **`PromptManager`** (`src/managers/prompt_manager.py`) — CRUD, sélection, `update_text()` en remplacement du pattern `add_images()`/`add_files()` (texte scalaire édité en place plutôt que liste accumulée), strictement idempotent.
- **`PromptsPage`** — nouvelle page (aucun placeholder à remplacer, contrairement à `Dataset`/`LoRA`) ; nouvelle entrée `sidebar.py` entre "LoRA" et "Training" ; lit exclusivement des dicts via `PromptManager.list_prompts()`.
- **`DashboardPage.lorasCard`** — corrigé en ouverture de mission : agrège désormais les `Character.loras` réels au lieu du champ vestigial `Workspace.loras`.

### Décisions de conception (Mission 005)

- Domain `Prompt` volontairement minimal — retour à la discipline `Dataset`/`Character` après l'exception justifiée de `LoRA`.
- Catégories/types de prompts (Blueprint §13) explicitement différées, pas abandonnées : documentées en commentaire dans `prompt.py`, seront réintroduites dès qu'un consommateur réel existera, sans rupture de compatibilité. Lors de cette réintroduction future, elles devront être implémentées comme une extension naturelle du Domain `Prompt` existant, sans remettre en cause le modèle minimal ni casser la compatibilité des données déjà persistées.
- `update_text()` remplace `add_images()`/`add_files()` : un texte s'édite en place, il ne s'accumule pas — aucune logique de déduplication n'a de sens ici.
- Filtrage défensif `isinstance(p, dict)` dans `Character.from_dict()` explicitement qualifié de **compatibilité défensive**, jamais de migration implicite — principe désormais posé comme référence pour toute future conversion `list[str] → list[Objet]` du projet.
- Correctif `lorasCard` traité en ouverture de mission, même pattern que `datasetsCard` en Mission 004.

### Tests ajoutés (Mission 005)

`tests/integration/test_prompt_roundtrip.py` (7 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_text()` (no-op sans sauvegarde ni événement, vérifié par espionnage direct de `WorkspaceManager.save()`), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `PromptsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 005)

Sans engagement définitif :

- Poursuite du Domain Model : `Model` — ressource partagée au niveau Workspace (`Workspace → Models → Characters`), un pattern architectural encore jamais implémenté dans ce projet, nécessitant sa propre conception avant toute implémentation.
- Réintroduction des catégories/types de `Prompt` dès qu'une fonctionnalité réelle le justifiera.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 005)

**Mission 005 est terminée.** L'application dispose désormais de quatre entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`), 29 tests d'intégration.

---

## [v0.2-mission004](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission004) — 2026-08-10

### Résumé (Mission 004)

**Mission 004 — LoRA Domain.** Introduction de l'entité `LoRA`, troisième objet du Domain Model après `Character` et `Dataset`, positionnée dans la hiérarchie `Character → LoRAs` (`docs/blueprint/04_DOMAIN_MODEL.md`). Contrairement au minimalisme strict appliqué à `Dataset`, le Domain `LoRA` a été volontairement étendu dès sa conception (8 champs : `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version`) — décision explicite pour éviter une migration future, compte tenu de la richesse intrinsèque d'un LoRA par rapport à un simple regroupement d'images. Comme `Dataset.images` en Mission 003, `LoRA.files` est fonctionnel dès son introduction.

Le travail a été mené en 7 commits atomiques, chacun avec rapport d'impact validé avant exécution. Deux points sensibles ont fait l'objet d'une preuve comportementale par exécution plutôt que par seule lecture de code : l'indépendance de deux instances de `LoRAManager` vis-à-vis de l'`EventBus`, et l'équivalence stricte du contrat `add_files()`/`DatasetManager.add_images()`.

### Statistiques (Mission 004)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `lora.py`, `lora_manager.py`, `test_lora_roundtrip.py` |
| Fichiers modifiés | `dashboard_page.py`, `character.py`, `main_window.py`, `lora_page.py` (placeholder → page réelle) |
| Tests d'intégration ajoutés | 7 |
| Bug corrigé | Carte Dashboard "Datasets" lisait le champ vestigial `Workspace.datasets` au lieu d'agréger `Character.datasets` (corrigé en ouverture de mission) |
| Total tests du projet | 22/22 verts (15 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 004)

- **`LoRA`** (`src/domain/lora.py`) — dataclass Qt-indépendant, 8 champs, domaine passif (aucune génération d'ID).
- **`Character.loras`** — `list[str]` → `list[LoRA]` (dépendance Domain→Domain, autorisée) ; migration de données prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle n'a jamais existé sous l'ancien format), même méthodologie que `Character.datasets` en Mission 003.
- **`LoRAManager`** (`src/managers/lora_manager.py`) — CRUD, sélection, `add_files()` avec déduplication et préservation de l'ordre ; `active_lora_id` runtime-only, réinitialisé au changement de personnage actif ou de workspace ; miroir exact de `DatasetManager`.
- **`LoRAPage`** — remplace le placeholder existant (qui incluait un bouton "Entraîner" hors périmètre, retiré) ; miroir strict de `DatasetsPage` ; lit exclusivement des dicts via `LoRAManager.list_loras()`.
- **`DashboardPage.datasetsCard`** — corrigé en ouverture de mission : agrège désormais les `Character.datasets` réels au lieu du champ vestigial `Workspace.datasets`.

### Décisions de conception (Mission 004)

- Domain `LoRA` volontairement plus riche que `Dataset` dès sa création — exception bornée et justifiée au minimalisme strict appliqué à `Character`/`Dataset`.
- `thumbnail` distinct de `files` : un aperçu n'est pas un fichier constitutif du LoRA — distinction reprise de CivitAI/ComfyUI/A1111/Forge, vocabulaire aligné sur celui du Blueprint pour `Model`/`Workflow`.
- `add_files()` reste générique vis-à-vis des types de fichiers (le Manager ne connaît aucune extension), à l'image d'`add_images()`.
- Correctif de la carte Dashboard "LoRA" (même bug que "Datasets", non encore corrigé) explicitement différé hors du Commit 5, pour préserver le découpage atomique de la mission — sera traité séparément si décidé.

### Tests ajoutés (Mission 004)

`tests/integration/test_lora_roundtrip.py` (7 tests) : cycle complet création/sélection/import/sauvegarde/fermeture/réouverture, préservation de l'ordre et déduplication des fichiers, réinitialisation de la sélection à la suppression de la LoRA active (avec persistance vérifiée), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `LoRAPage` sur les événements pertinents, absence de duplication d'abonnements entre deux instanciations, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 004)

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Poursuite du Domain Model : `Prompt` (déjà anticipé par `Character.prompts`, actuellement vide), ou `Model`.
- Correctif différé de la carte Dashboard "LoRA" (même nature que le correctif "Datasets" traité en Mission 004).
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, toujours différée.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 004)

**Mission 004 est terminée.** L'application dispose désormais de trois entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`), 22 tests d'intégration, et une dette identifiée lors de l'audit de démarrage corrigée.

---

## [v0.2-mission003](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission003) — 2026-08-10

### Résumé (Mission 003)

**Mission 003 — Dataset Domain.** Introduction de l'entité `Dataset`, deuxième objet du Domain Model après `Character`, positionnée dans la hiérarchie `Character → Datasets` (`docs/blueprint/04_DOMAIN_MODEL.md` §7). Contrairement à `Character.images` en Mission 002, `Dataset.images` est fonctionnel dès cette mission : import d'images propre à chaque dataset, avec déduplication et préservation de l'ordre — un chemin d'import indépendant de `Workspace.images`/`ImagesPage`, sans migration requise.

Le travail a été mené en 7 commits atomiques, chacun accompagné d'un rapport d'impact validé avant exécution, avec un niveau de preuve comportementale renforcé par rapport aux missions précédentes (espionnage d'appels, vérification directe des abonnements `EventBus`, tests sur widgets Qt réels plutôt que sur les managers isolés).

### Statistiques (Mission 003)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `dataset.py`, `dataset_manager.py`, `test_dataset_roundtrip.py` |
| Fichiers modifiés | `character.py`, `main_window.py`, `datasets_page.py` (placeholder → page réelle), `workspace_manager.py` |
| Tests d'intégration ajoutés | 7 |
| Dette technique corrigée | Import direct Presentation → Infrastructure (`WorkspaceStorageError` dans `MainWindow`) remplacé par `WorkspaceManagerError` |
| Total tests du projet | 15/15 verts (8 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 003)

- **`Dataset`** (`src/domain/dataset.py`) — dataclass Qt-indépendant, 3 champs (`dataset_id`, `name`, `images`), domaine passif (aucune génération d'ID).
- **`Character.datasets`** — `list[str]` → `list[Dataset]` (dépendance Domain→Domain, autorisée) ; migration de données prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle n'a jamais existé sous l'ancien format).
- **`DatasetManager`** (`src/managers/dataset_manager.py`) — CRUD, sélection, `add_images()` fonctionnel avec déduplication et préservation de l'ordre ; `active_dataset_id` runtime-only, réinitialisé au changement de personnage actif ou de workspace.
- **`DatasetsPage`** — remplace le placeholder existant ; CRUD + import d'images à deux niveaux (liste des datasets avec compteur d'images, liste des images du dataset sélectionné) ; lit exclusivement des dicts via `DatasetManager.list_datasets()`, jamais des objets `Dataset` directement.
- **`WorkspaceManagerError`** — nouvelle exception publique portée par `WorkspaceManager`, remplace l'import direct de `WorkspaceStorageError` (Infrastructure) dans `MainWindow`, corrigeant une dette identifiée lors de l'audit de démarrage de mission.

### Décisions de conception (Mission 003)

- `Dataset.images` fonctionnel dès cette mission, contrairement à `Character.images` en Mission 002 — import propre à chaque dataset, sans dépendre d'une migration de `Workspace.images`.
- Ownership de `Dataset` implicite (pas de `character_id` stocké), même principe que `Character` vis-à-vis de `Workspace`.
- `add_images(paths)` opère sur le dataset actif implicitement, sans paramètre d'identifiant — même logique que `WorkspaceManager.add_images()`.
- Robustesse de désérialisation : `Character.from_dict()` filtre explicitement les entrées non-`dict` dans `datasets` plutôt que de laisser fuiter une `AttributeError`.
- Correctif de dette technique (`WorkspaceManagerError`) traité en ouverture de mission plutôt qu'en fin, pour établir le bon pattern avant que `DatasetManager` n'en ait besoin à son tour.

### Tests ajoutés (Mission 003)

`tests/integration/test_dataset_roundtrip.py` (7 tests) : cycle complet création/sélection/import/sauvegarde/fermeture/réouverture, préservation de l'ordre et déduplication des images, réinitialisation de la sélection à la suppression du dataset actif (avec persistance vérifiée), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `DatasetsPage` sur les événements pertinents (y compris `workspace.saved` après un import), absence de duplication d'abonnements entre deux instanciations, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 003)

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Poursuite du Domain Model : `LoRA`/`Prompt` (déjà anticipés par `Character.loras`/`Character.prompts`, actuellement vides), ou `Model`.
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, toujours différée.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 003)

**Mission 003 est terminée.** L'application dispose désormais de deux entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`), 15 tests d'intégration, et une dette technique identifiée lors de l'audit post-Mission-002 corrigée.

---

## [v0.2-mission002](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission002) — 2026-08-10

### Résumé (Mission 002)

**Mission 002 — Character Domain.** Introduction de l'entité `Character`, présentée par le Blueprint comme l'entité centrale du logiciel (`docs/blueprint/04_DOMAIN_MODEL.md` §6). Périmètre volontairement minimal : identité + listes de référence vides (`images`, `datasets`, `loras`, `prompts`, `history`), CRUD complet (créer/sélectionner/supprimer), persistance dans `project.json` via le mécanisme `WorkspaceManager` déjà existant — aucune nouvelle infrastructure de stockage. La migration des images de `Workspace` vers `Character` est explicitement différée à une mission future.

Le travail a été mené en 6 commits atomiques, chacun accompagné d'un rapport d'impact validé avant exécution — même discipline que la Mission 001.

### Statistiques (Mission 002)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `character.py`, `character_manager.py`, `characters_page.py`, `test_character_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 6 |
| Bugs applicatifs introduits | 0 (une erreur de comptage dans un test a été trouvée et corrigée **dans le test**, pas dans le code applicatif) |
| Nouvelle page Sidebar | Characters (9ᵉ page, positionnée juste après Dashboard) |

### Évolutions architecturales (Mission 002)

- **`Character`** (`src/domain/character.py`) — dataclass Qt-indépendant, 7 champs (`character_id`, `name`, `images`, `datasets`, `loras`, `prompts`, `history`), domaine passif (aucune génération d'ID).
- **`Workspace.characters`** — extension rétrocompatible, liste de vrais objets `Character` (dépendance Domain→Domain, autorisée), robuste à `"characters": null`.
- **`CharacterManager`** (`src/managers/character_manager.py`) — CRUD/sélection, persistance déléguée à `WorkspaceManager.save()`, publication d'événements (`character.created`/`selected`/`deleted`), abonnement à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` pour réinitialiser `active_character_id` (runtime-only, jamais persisté) à chaque changement de workspace.
- **`CharactersPage`** — lit exclusivement des dicts via `CharacterManager.list_characters()`, jamais des objets `Character` (Presentation reste indépendante du Domain) ; protection `blockSignals()` contre les boucles d'événements Qt.
- **Dashboard/Images inchangés** — aucune carte "Characters" ajoutée, aucune migration de `ImagesPage` vers `Character.images` — choix explicites, différés à une mission future.

### Décisions de conception (Mission 002)

- Pas de migration d'images cette mission (`Workspace.images` reste la source utilisée par `ImagesPage`).
- `active_character_id` runtime-only, non persisté — même principe que `Workspace.root`.
- `favorite_models` retiré du périmètre — uniquement les 7 champs réellement nécessaires.
- `datasets`/`loras`/`prompts` sont des listes d'identifiants destinés à des objets futurs, pas des chemins de fichiers.
- Aucune carte Dashboard ajoutée.
- Génération de `character_id` dans `CharacterManager.create()`, jamais dans le dataclass `Character` — le Domain reste passif.
- Entrée Sidebar "Characters" positionnée juste après Dashboard, pas en fin de liste.

### Tests ajoutés (Mission 002)

`tests/integration/test_character_roundtrip.py` (6 tests) : cycle complet créer/sélectionner/sauvegarder/fermer/rouvrir, persistance de la suppression, non-réinitialisation d'`active_character_id` sur ouverture échouée, non-impact sur Dashboard/Images, reconstruction correcte de `CharactersPage` sur les événements Workspace, absence de duplication d'abonnements entre deux instanciations.

### Prochaines étapes

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Piste envisagée pour la prochaine mission : le domaine `Dataset`, entité suivante de la hiérarchie `Character → Datasets` déjà anticipée par `Character.datasets` (liste vide, prête à recevoir des identifiants).
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, différée depuis cette mission.
- Reste du Domain Model : `Model`, `LoRA`, `Job`, `Engine`, `Plugin`.

### État du projet (Mission 002)

**Mission 002 est terminée.** L'application dispose désormais d'une entité `Character` complète en CRUD, intégrée dans la navigation et couverte par des tests d'intégration.

---

## [v0.2-mission001](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission001) — 2026-08-10

### Résumé de la mission

**Mission 001 — Blueprint Refactoring.** Cette mission correspond au **Blueprint 02 (`docs/blueprint/02_ARCHITECTURE.md`)** : le prototype initial (gestion de "Project" ad hoc, logique métier dispersée dans l'UI, managers non utilisés) a été refactoré pour se conformer à l'architecture qui y est décrite, en cohérence avec les autres documents du Blueprint (`00_VISION.md` → `04_DOMAIN_MODEL.md`).

Cette mission n'a **ajouté aucune fonctionnalité nouvelle** : son unique objectif était de mettre le code existant en conformité avec les couches, les responsabilités et le sens de dépendance définis par le Blueprint (`Presentation → Managers → Services → Domain → Infrastructure → Engines`), tout en préservant le comportement observable de l'application.

Le travail a été mené en 9 commits atomiques, chacun revu, testé manuellement et validé avant exécution.

### Statistiques de la mission

| Indicateur | Valeur |
|---|---|
| Commits | 9 |
| Bugs corrigés | 3 |
| Tests d'intégration ajoutés | 2 |
| Packages morts supprimés | `src/config/`, `src/models/`, `src/widgets/`, `src/project/` |
| Architecture | Refactorisée (Presentation / Managers / Domain / Infrastructure / Core) |

### Évolutions architecturales principales

- **Introduction du Domain Layer** — `src/domain/workspace.py::Workspace`, un dataclass Qt-indépendant remplaçant l'ancienne dataclass `Project` (jamais utilisée) et reflétant fidèlement le schéma JSON réel. Le champ `root` (chemin du dossier) est explicitement runtime-only, jamais sérialisé, pour garder `project.json` portable.
- **Introduction de l'Infrastructure Layer** — `src/infrastructure/storage/workspace_storage.py::WorkspaceStorage`, portage durci de l'ancien `ProjectIO` : gestion d'erreurs typée (`WorkspaceStorageError`), journalisation, API dict-only (aucune dépendance vers le Domain, conformément au sens de dépendance du Blueprint).
- **Introduction de l'Application Layer** — `src/managers/workspace_manager.py::WorkspaceManager`, source unique de vérité pour le workspace courant, remplaçant l'ancien `ProjectManager` (jamais réellement instancié) et l'état dupliqué de `MainWindow`.
- **Introduction du Core / EventBus** — `src/core/event_bus.py::EventBus`, pub/sub minimal, Qt-indépendant, avec payloads réellement immuables (copie profonde + vue en lecture seule), permettant à la Presentation de réagir aux événements du workspace sans que les Managers ne dépendent de Qt.
- **`MainWindow` délègue entièrement à `WorkspaceManager`** — suppression de l'accès direct à l'Infrastructure (`ProjectIO`) et de l'état dupliqué (`current_project`/`project_folder`) ; `DashboardPage` et `ImagesPage` s'abonnent désormais aux événements du workspace plutôt que d'être mises à jour manuellement.
- **Extraction de la logique métier hors des widgets** — `ImagesPage` ne détient plus d'état privé ; l'import d'images passe par `WorkspaceManager.add_images()`, avec déduplication, et persiste réellement dans `project.json`.
- **Réorganisation de la structure de fichiers** — `src/pages/` déplacé sous `src/ui/pages/` ; suppression des packages vides non conformes (`src/config/`, `src/models/`, `src/widgets/`) ; suppression finale de `src/project/`, devenu totalement orphelin.

### Bugs corrigés

- **Dashboard non rafraîchi après création/ouverture d'un projet** — corrigé structurellement par le câblage événementiel (`WorkspaceManager` → `EventBus` → `DashboardPage.update_project`), plutôt que par un correctif ponctuel.
- **Une tentative d'ouverture d'un dossier invalide fermait silencieusement le workspace déjà ouvert** — `WorkspaceManager.open()` réinitialisait `current_workspace` à `None` même en cas d'échec, faisant perdre le projet en cours sans avertissement visible. Corrigé : un échec d'ouverture laisse désormais l'état courant inchangé. Cette règle métier est maintenant protégée par un test de non-régression permanent.
- **`WorkspaceManager.close()` ne publiait plus l'événement `workspace.closed`** — régression introduite lors de l'ajout d'`add_images()` (ligne de publication déplacée par erreur après un `return`, dans la mauvaise méthode). Détectée par le test d'intégration écrit pour cette même mission, corrigée dans la foulée.

### Tests ajoutés

- `tests/integration/test_workspace_roundtrip.py` (stdlib `unittest`, aucune nouvelle dépendance) :
  - `test_full_create_import_save_close_reopen_cycle` — cycle complet création → import d'images → sauvegarde → fermeture → réouverture (avec instances fraîches, simulant un vrai redémarrage), vérifiant la persistance des images et la mise à jour correcte du Dashboard et de la page Images.
  - `test_failed_open_does_not_close_current_workspace` — garde de non-régression permanente pour la règle métier « une ouverture échouée ne doit jamais fermer le workspace courant ».

### Prochaines étapes (Mission 002)

Hors périmètre de la Mission 001, à traiter dans des missions dédiées ultérieures :

- Introduction du domaine **Character** (entité centrale du Blueprint, actuellement absente) et de la propriété des ressources (Datasets, LoRAs, Prompts, Historique) qui lui revient.
- Introduction progressive des autres objets du Domain Model (`Dataset`, `Model`, `LoRA`, `Job`, `Engine`, `Plugin`) — un par mission, sans scaffolding anticipé.
- Introduction de la couche **Services** dès qu'une logique métier réelle la justifiera.
- Introduction de `src/engines/` et `src/plugins/` lors de la première intégration réelle avec un moteur externe (ComfyUI, OneTrainer, etc.).

### Améliorations UX futures

- Création automatique du dossier cible directement depuis le dialogue "Nouveau projet", sans devoir le créer manuellement au préalable dans l'explorateur Windows.

### État du projet

**Mission 001 est terminée.** L'application dispose désormais d'une architecture conforme au Blueprint 02, d'une suite de tests d'intégration et d'une documentation à jour (`README.md`, ce `CHANGELOG.md`).

**Mission 002** introduira le domaine **Character**, entité centrale du Blueprint (`docs/blueprint/04_DOMAIN_MODEL.md`), actuellement absente du code.

---

*Généré à l'issue de la Mission 001 — Blueprint Refactoring.*
