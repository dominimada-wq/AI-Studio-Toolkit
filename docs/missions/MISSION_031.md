# Mission 031 — Prompt Assistant Minimal (Inference)

**État final (voir sections 9/10)** : implémentée, testée (589/589 tests automatisés verts) **et validée par un smoke test manuel réel complet contre une instance Ollama réelle — PASS**. **Clôture Git et publication GitHub Release entièrement effectuées** — commit fonctionnel `1226342d808936f98673804eb654f6cc048103da`, tag `v0.2-mission031`.

## 1. Contexte

Mission 030 a posé la fondation structurelle d'un assistant IA/LLM (`AIBackend`, `OllamaEngine`) sans aucun câblage vers une Page UI. Un audit de priorisation dédié (post-Mission 030) a comparé plusieurs candidats pour la mission suivante et recommandé un **Prompt Assistant minimal** comme premier usage utilisateur réel de cette fondation — candidat validant la fondation Mission 030 sans dépendance bloquante, contrairement à un Character Context qui aurait exigé une identité Character déjà stabilisée.

Avant toute spécification, un audit dédié a été mené sur l'architecture Prompt actuelle (`src/domain/prompt.py`, `PromptManager`, `PromptsPage`), l'architecture Inference (`InferencePage`, `GenerationWorker`/`QThread`), et l'architecture `AIBackend`/`OllamaEngine` (Mission 030) — confirmant notamment qu'aucun Manager/Service n'existait encore pour construire un `AIBackend` autrement que la construction jetable déjà faite par `SettingsPage.refresh_ollama_models()`.

## 2. Objectif

1. Donner une première utilisation utilisateur réelle à la fondation IA de Mission 030, sans jamais coupler l'UI à `OllamaEngine` directement.
2. Concevoir la logique applicative (`PromptAssistantManager`) comme un service partagé réutilisable, même si Mission 031 n'en câble qu'un seul consommateur (`InferencePage`).
3. Distinguer explicitement, côté UX, les intentions **Créer** et **Améliorer** — un prompt existant ne doit jamais être transmis silencieusement au backend comme base.
4. Garder l'appel non bloquant, en réutilisant le patron `Worker + QThread` déjà validé par `GenerationWorker` (Mission 013).
5. Permettre, en complément, l'enregistrement du résultat comme `Prompt` persistant depuis Inference, sans dupliquer de logique métier déjà portée par `PromptManager`, et sans modifier silencieusement le Prompt déjà actif dans `PromptsPage`.

## 3. Architecture retenue

```
InferencePage → PromptAssistantDialog → PromptAssistantWorker (QThread) → PromptAssistantManager → AIBackend (OllamaEngine) → Ollama
```

Aucune Page n'importe `OllamaEngine`/`urllib` directement — vérifié par test architectural couvrant `InferencePage` **et** `PromptsPage` (cette dernière non modifiée, vérifiée par prévention). `OllamaEngine` est construit une seule fois dans `MainWindow.__init__`, à la composition root, exactement comme `ComfyUIEngine` — aucun rechargement à chaud, un changement sauvegardé via `SettingsPage` ne prend effet qu'au prochain démarrage (comportement confirmé par audit pré-implémentation dédié et par test dédié, voir section 7).

**Architecture long terme confirmée : Option C — service `PromptAssistantManager` partagé.** `PromptsPage` et `InferencePage` sont destinées à devenir deux consommateurs d'un même service, jamais deux implémentations distinctes de la logique IA. Mission 031 retient tactiquement l'intégration **Option B** (Assistant principalement dans Inference) : `InferencePage.prompt` constituait déjà le point d'entrée exact du texte de génération, l'intégration la moins invasive. `PromptAssistantManager` est néanmoins conçu dès cette mission sous la forme requise par Option C (Qt-free, service unique, aucune connaissance de Page), directement réutilisable par une future intégration `PromptsPage` sans réécriture.

## 4. Fonctionnalités livrées

### 4.1 Prompt Assistant dans Inference

Nouveau bouton **« Assistant IA »** dans `InferencePage`, ouvrant `PromptAssistantDialog` (nouveau, `src/ui/dialogs/prompt_assistant_dialog.py`) :

- **Créer** : à partir d'une demande utilisateur, l'Assistant IA propose un nouveau prompt.
- **Améliorer** : disponible uniquement si `InferencePage.prompt` contient déjà du texte au moment de l'ouverture (le bouton correspondant n'existe même pas sinon, jamais simplement grisé) — le prompt actuel est affiché **en lecture seule** comme base avant tout envoi, jamais transmis silencieusement ; l'utilisateur fournit une instruction d'amélioration.
- **« Utiliser ce texte »** transfère le résultat proposé dans le champ prompt d'Inference.

### 4.2 UI non bloquante

L'appel est exécuté hors du thread Qt principal via `PromptAssistantWorker` (`QObject`, signaux `finished(str)`/`failed(str)`) déplacé dans un `QThread` — calque structurel exact de `GenerationWorker`. Pendant l'appel : boutons désactivés, indicateur « Génération en cours... » visible, aucun appel concurrent possible (`PromptAssistantManager._busy`, miroir de `GenerationManager._busy`). Succès et `PromptAssistantError` (normalisant `AIBackendError` et le cas "appel déjà en cours") rétablissent tous deux correctement l'état de l'interface, sans crash.

### 4.3 Enregistrer dans Prompts

Nouveau bouton indépendant **« Enregistrer dans Prompts »** dans `InferencePage`, activé uniquement si `InferencePage.prompt` n'est pas vide — opère sur le texte actuellement présent, qu'il provienne de l'Assistant ou d'une saisie manuelle :

```
texte actuel Inference → QInputDialog (nom obligatoire, garde "not ok or not name.strip()")
→ PromptManager.create(name, text=texte) → Prompt persistant → visible dans PromptsPage
```

Nom vide/uniquement des espaces refusé (même garde que `PromptsPage.create_prompt()`, dupliquée à l'identique — une factorisation aurait exigé soit une règle de validation dans `PromptManager` (interdit par CLAUDE.md), soit un nouveau module UI partagé pour une seule ligne, jugé disproportionné). Doublons de noms toujours autorisés (comportement historique inchangé, aucune nouvelle règle créée).

**Aucun effet de bord sur le Prompt actif.** `PromptManager.create()` a été étendu de façon **additive et rétrocompatible** : `create(name, text="")` — tout appelant historique (`PromptsPage.create_prompt()`) reste inchangé (défaut `""` identique au comportement précédent). `InferencePage` n'appelle **jamais** `select()`/`update_text()` : ces méthodes modifieraient `active_prompt_id` et publieraient `PROMPT_SELECTED`, déjà câblé vers `PromptsPage.update_prompts()` — un effet de bord réel et visible (sélection/`text_edit` écrasés) qu'un audit pré-implémentation dédié a explicitement identifié et évité.

## 5. Audit pré-implémentation — deux vérifications ciblées

Avant toute implémentation, deux points ont été vérifiés explicitement, à la demande de l'architecte :

1. **Configuration Ollama runtime** : confirmé qu'aucun rechargement à chaud n'existe nulle part dans l'application — `ComfyUIEngine`/`GenerationManager` sont déjà lus une seule fois au démarrage, comportement déjà documenté côté utilisateur dans `SettingsPage.application_hint` (qui anticipait déjà "ComfyUI/Ollama"). `OllamaEngine`/`PromptAssistantManager` reproduisent ce même patron sans nouveau mécanisme — vérifié par 3 tests dédiés (`test_main_window_ollama_settings.py`).
2. **Effet de bord de `select()`** : confirmé que `select()` modifierait silencieusement la sélection déjà affichée dans `PromptsPage` — résolu par l'extension additive `create(name, text="")` plutôt que par un appel `select()`/`update_text()` (voir section 4.3), vérifié par un test dédié au niveau Manager réel (`test_prompt_roundtrip.py`) et par des assertions `assert_not_called()` côté UI mockée (`test_inference_page.py`).

## 6. Périmètre IN

- `src/managers/prompt_assistant_manager.py` (nouveau) : `PromptAssistantManager`/`PromptAssistantError`.
- `src/ui/prompt_assistant_worker.py` (nouveau) : `PromptAssistantWorker`.
- `src/ui/dialogs/prompt_assistant_dialog.py` (nouveau) : `PromptAssistantDialog`.
- `src/managers/prompt_manager.py` : extension additive `create(name, text="")`.
- `src/ui/main_window.py` : construction `ollama_engine`/`prompt_assistant_manager` à la composition root, injection dans `InferencePage`.
- `src/ui/pages/inference_page.py` : boutons « Assistant IA »/« Enregistrer dans Prompts », constructeur étendu (`prompt_manager`, `prompt_assistant_manager`).
- Ajustement UX (voir section 8) : dialogue redimensionnable, taille initiale 800×700, zones de texte extensibles.

## 7. Périmètre OUT (strict, explicitement différé)

Assistant IA dans `PromptsPage` ; `Prompts → Envoyer vers Inference` ; Character Context ; modification profonde de Character Identity ; analyse d'image/vision/multimodal ; Qwen3-VL ; téléchargement/benchmark de modèle ; Prompt Library structurée complète ; RAG ; embeddings ; vector database ; exploitation automatique des anciens prompts ; providers cloud ; streaming LLM ; workflows ComfyUI supplémentaires ; génération d'image elle-même ; refonte générale de Settings/`PromptsPage`/`InferencePage` ; modification du timeout Ollama (30 s, cold start toujours documenté Mission 030, non traité) ; toute nouvelle règle de gestion des doublons de nom de Prompt.

## 8. Ajustement UX — dialogue `PromptAssistantDialog`

Le smoke test manuel réel a révélé que la taille par défaut du dialogue était trop petite pour lire/travailler confortablement avec les prompts générés. Corrigé avant clôture :

- Taille initiale `800 × 700` px (`self.resize(800, 700)`).
- Dialogue redimensionnable (comportement par défaut de `QDialog`, aucun `setFixedSize()`).
- Facteurs d'étirement sur les trois zones de texte (`existing_prompt_preview`/`request_edit` : 1, `result_edit` : 2) — l'espace supplémentaire lors d'un agrandissement profite proportionnellement plus au résultat.
- Hauteurs minimales (90/90/150 px) garantissant un confort de lecture même avant redimensionnement.
- **Aucune persistance de taille/position ajoutée. Aucun comportement fonctionnel modifié.**

Un second problème, découvert pendant l'exécution automatisée des tests suite à cet ajustement, a été corrigé : deux tests de `test_prompt_assistant_dialog.py` (demande vide, erreur backend) laissaient s'afficher de **vraies** boîtes `QMessageBox`, exigeant une intervention humaine pour que la suite continue — un défaut de harness de tests, jamais un défaut applicatif (`PromptAssistantDialog` appelle correctement `QMessageBox.warning`/`.critical` en conditions réelles). Corrigé en mockant `QMessageBox.warning`/`.critical` dans ces deux tests uniquement (`@patch("src.ui.dialogs.prompt_assistant_dialog.QMessageBox.warning/critical")`), scénarios et assertions conservés à l'identique.

## 9. Stratégie de tests et résultat final

**589/589 tests automatisés verts** (549 précédents + 40 nets nouveaux), entièrement mockés — aucune requête réseau réelle, aucune boîte modale réelle, aucune intervention humaine. Dernière exécution complète unique (pas d'exécution parallèle), ~104 secondes.

- `tests/integration/test_prompt_assistant_manager.py` (7, nouveau) — intentions Créer/Améliorer, construction déterministe et testée du texte combiné envoyé au backend, `model_name` jamais codé en dur, normalisation `AIBackendError`/appel concurrent en `PromptAssistantError`.
- `tests/integration/test_prompt_assistant_worker.py` (5, nouveau) — calque exact de `test_generation_worker.py`, `QThread` réel, exécution hors thread principal prouvée.
- `tests/integration/test_prompt_assistant_dialog.py` (13, nouveau) — modes Créer/Améliorer, aperçu du prompt existant affiché uniquement en mode Améliorer, appel non bloquant, boutons désactivés pendant l'appel, `PromptAssistantError` gérée sans crash (`QMessageBox` mockées), handoff du résultat via `result_text`, taille initiale ≥800×700, redimensionnement réellement effectif, part d'étirement du résultat supérieure à celle de la demande.
- `tests/integration/test_main_window_ollama_settings.py` (3, nouveau) — calque exact de `test_main_window_comfyui_settings.py`, confirme explicitement l'absence de rechargement à chaud.
- `tests/integration/test_inference_page.py` (+11 nets, 71 au total) — boutons « Assistant IA »/« Enregistrer dans Prompts », garde de nom, absence de `select()`/`update_text()` depuis Inference, avertissement si aucun personnage principal, test architectural anti-`OllamaEngine`/`urllib` étendu à `inference_page.py` **et** `prompts_page.py`.
- `tests/integration/test_prompt_roundtrip.py` (+1) — `create(name, text=...)` au niveau Manager réel confirmé sans effet sur `active_prompt_id` ni sur la sélection déjà affichée dans `PromptsPage`.

## 10. Smoke test manuel réel — résultat

**PASS.** Confirmés manuellement contre une instance Ollama réelle : ouverture de l'Assistant IA ; fonctionnement avec une instance Ollama réelle ; génération réelle via le modèle configuré ; mode Créer ; mode Améliorer ; affichage du prompt actuel comme base en mode Améliorer ; résultat proposé affiché ; « Utiliser ce texte » vers Inference ; « Enregistrer dans Prompts » avec nom choisi par l'utilisateur ; Prompt sauvegardé visible dans `PromptsPage` ; gestion propre d'un backend Ollama inaccessible ; message d'erreur utilisateur sans crash ; UI réutilisable après erreur ; amélioration de la taille du dialogue validée visuellement (section 8).

**Observation future enregistrée — sortie LLM trop explicative (non bloquante, non corrigée cette mission).** Ollama a parfois retourné, autour du prompt proposé, du Markdown, des titres, une analyse du prompt et des explications (exemple observé : `**Amélioration du prompt...**` suivi d'une analyse), plutôt que le seul texte final directement exploitable — « Utiliser ce texte » peut donc actuellement récupérer autre chose que le seul prompt final. Enregistrée comme besoin futur (voir `docs/PROJECT_CONTEXT.md`, rattachée au besoin "Assistant IA/LLM") : étudier un contrat/instruction de Prompt Assistant demandant explicitement au LLM de ne retourner que le prompt final exploitable, sans Markdown, préambule, analyse ni commentaire parasite. Le contrat de `PromptAssistantManager.assist()`/`_build_combined_text()` n'a **pas** été modifié pour ce point pendant cette clôture.

## 11. Risques résiduels / limites volontairement ouvertes

Timeout Ollama toujours fixé à 30 s ; cold start Ollama pouvant dépasser ce timeout (limite empirique déjà documentée Mission 030, non revisitée) ; aucun warm-up automatique ; aucun streaming ; aucun Character Context ; aucune analyse d'image ; aucun multimodal ; aucun Qwen3-VL ; aucun Prompt Assistant dans `PromptsPage` ; aucun `Prompts → Envoyer vers Inference` ; aucune Prompt Library structurée ; aucun RAG ; aucun embeddings ; aucun provider cloud ; sortie LLM potentiellement bruitée de Markdown/analyse (section 10).

## 12. Critères d'acceptation

- Aucun import d'`OllamaEngine`/`urllib` dans `InferencePage`/`PromptsPage` — vérifié par test architectural. ✅
- Appel Assistant démontrablement non bloquant (test dédié, calque de `GenerationWorker`). ✅
- Deux intentions Créer/Améliorer distinctes dans l'UI et dans les tests, jamais de transmission silencieuse du prompt existant. ✅
- `PromptAssistantError` gérée sans crash, UI réactivée après échec, y compris en cas de timeout. ✅
- Modèle utilisé toujours celui configuré dans Settings, jamais codé en dur. ✅
- Génération d'image existante strictement non régressée. ✅
- Comportement historique de `PromptsPage` strictement non régressé. ✅
- « Enregistrer dans Prompts » : nom vide refusé, doublons acceptés, prompt visible dans `PromptsPage` sans action supplémentaire, aucune modification de `Prompt`/`PromptManager` au-delà de l'extension additive `create(name, text="")`. ✅
- 589/589 tests automatisés verts, aucune dépendance à une instance Ollama réelle ni à une intervention humaine dans la suite automatisée. ✅
- Smoke test manuel réel PASS (section 10), dialogue redimensionné validé visuellement (section 8). ✅

## Fichiers concernés — liste finale

**Créés** : `src/managers/prompt_assistant_manager.py`, `src/ui/prompt_assistant_worker.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `tests/integration/test_main_window_ollama_settings.py`, `tests/integration/test_prompt_assistant_manager.py`, `tests/integration/test_prompt_assistant_worker.py`, `tests/integration/test_prompt_assistant_dialog.py`.

**Modifiés** : `src/managers/prompt_manager.py`, `src/ui/main_window.py`, `src/ui/pages/inference_page.py`, `tests/integration/test_inference_page.py`, `tests/integration/test_prompt_roundtrip.py`, plus `docs/PROJECT_CONTEXT.md`/`CHANGELOG.md`/ce document.

**Non modifiés** : `src/domain/prompt.py`, `src/ui/pages/prompts_page.py`, `src/engines/ai_backend.py`, `src/engines/ollama_engine.py`, `src/domain/application_settings.py`, `src/domain/character.py`.

## Commit correspondant

`1226342d808936f98673804eb654f6cc048103da` — `feat: add minimal AI Prompt Assistant for Inference`.

## Tag / release correspondant

`v0.2-mission031` (annoté, message `Mission 031 - Prompt Assistant Minimal (Inference)`), ciblant exactement `1226342d808936f98673804eb654f6cc048103da`. GitHub Release `v0.2-mission031` **publiée** — confirmée par l'architecte du projet.

## État final

**Implémentation, suite automatisée complète (589/589) et smoke test manuel réel complet contre une instance Ollama réelle tous validés — PASS.** Ajustement UX du dialogue (taille 800×700, redimensionnable) et correction du harness de tests (boîtes modales mockées) intégrés avant clôture. **Clôture Git et publication GitHub Release entièrement effectuées** — commit fonctionnel `1226342d808936f98673804eb654f6cc048103da`, tag `v0.2-mission031`. Une observation future sur la propreté de la sortie LLM (Markdown/analyse parasite) a été documentée (section 10) — non bloquante, non corrigée cette mission.
