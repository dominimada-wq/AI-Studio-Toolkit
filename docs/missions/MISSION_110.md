# Mission 110 — Training → LoRA Trigger Carryover + Explicit Trigger Use in Inference

> **CONTRAT PRÉ-IMPLÉMENTATION — NON ENCORE IMPLÉMENTÉE.** Ce document sert de périmètre fermé avant toute implémentation. Le code ne sera écrit qu'après validation explicite par l'architecte.

## 1. Contexte

L'audit post-Mission 109 a établi que le parcours mécanique `Images → Dataset/captions → OneTrainer → LoRA → Central Library → Inference → Images` est désormais complet et automatique de bout en bout (aucune étape manuelle d'exposition au moteur, présélection automatique du bon LoRA depuis Training), mais qu'une rupture sémantique subsiste : le `trigger_word` nécessaire pour réellement invoquer le concept entraîné dans une génération n'est ni transmis ni exploité nulle part dans ce parcours.

Trois champs `trigger_word`/`trigger_token` existent déjà, indépendamment les uns des autres, et aucune mission n'a encore relié le second au troisième :

- `Character.trigger_token` (`character.py:26`).
- `Training.trigger_word` (`training.py:64`), saisi manuellement par l'utilisateur dans `TrainingPage.trigger_word_edit` avant/pendant la préparation d'un Training.
- `LoRA.trigger_word` (`lora.py:29`), champ déjà éditable manuellement pour toute entrée de la Central LoRA Library via l'onglet « Central Library » de `LoRAPage`.

Vérification directe du code réel :

- `TrainingPage.import_selected_job_to_library()` (`training_page.py:1231-1283`) a déjà `training = self.training_manager.active_training` en scope local — donc `training.trigger_word` — au moment où elle appelle `LoRALibraryManager.import_lora(name.strip(), [job.final_output_path], library_root=library_root)`. Cet appel ne transmet actuellement aucun `trigger_word`, alors que `import_lora()` accepte déjà ce paramètre nommé (`lora_library_manager.py:144-154`, défaut `""`) depuis Mission 088. Chaque LoRA importé démarre donc systématiquement avec `trigger_word=""`, quel que soit le trigger réellement saisi pendant l'entraînement.
- `InferencePage` ne référence `trigger_word` nulle part (confirmé par recherche exhaustive dans `src/`) : même après le handoff explicite livré par Mission 109 (bon LoRA présélectionné), rien n'indique à l'utilisateur quel mot invoquer, et rien ne l'aide à l'insérer dans le prompt.
- `InferencePage._on_lora_selection_changed()` (`inference_page.py:630-636`) et `InferencePage.refresh_lora_selector()` (`inference_page.py:638-695`) sont les deux seuls points qui font varier `self._selected_lora_choice` — donc les deux seuls points où un futur état d'affichage du trigger doit être recalculé, jamais mis en cache ailleurs.
- `InferencePage.prompt_text()`/`set_prompt_text()` (`inference_page.py:1477-1480+`) sont déjà les accesseurs publics existants du prompt (`QTextEdit`), réutilisables tels quels pour lire/écrire le prompt sans jamais toucher `self.prompt` directement depuis une nouvelle méthode.

## 2. Objectif

Fermer la rupture sémantique restante après Mission 108/109 : le `trigger_word` d'un `Training` doit survivre à son import dans la Central LoRA Library, et l'utilisateur doit pouvoir — par un geste explicite, jamais automatique — l'insérer proprement dans le prompt d'Inference lorsqu'un LoRA en possède un.

## 3. Décisions retenues (validées par l'architecte, non rediscutées ici)

### 3.1 Carryover Training → LoRA — additif, sans toucher au Manager

`TrainingPage.import_selected_job_to_library()` passe désormais `trigger_word=training.trigger_word` à `import_lora()`. Aucune modification de `LoRALibraryManager.import_lora()` elle-même — le paramètre existe déjà depuis Mission 088, seul l'appelant change. Un `Training.trigger_word` vide (`""`, cas normal pour beaucoup de Trainings) produit un `LoRA.trigger_word` vide, comportement strictement identique à aujourd'hui.

### 3.2 Affichage du trigger dans Inference — lecture seule, recalculé aux deux points de changement existants

Nouveau `QLabel` affichant le trigger du LoRA actuellement sélectionné, recalculé par une nouvelle méthode partagée (ex. `_refresh_lora_trigger_widgets()`) appelée depuis les deux points déjà existants qui font varier `self._selected_lora_choice` — `_on_lora_selection_changed()` et la fin de `refresh_lora_selector()` — jamais un état mis en cache indépendamment. Aucun LoRA sélectionné ou `trigger_word` vide → label vide et action d'insertion désactivée (même discipline que `lora_strength_spinbox.setEnabled(bool(choice))` juste à côté).

### 3.3 Insertion explicite — jamais automatique, jamais lors du handoff M109

Nouveau bouton d'action (ex. « Insérer le trigger »), désactivé par défaut, activé uniquement quand un LoRA sélectionné a un `trigger_word` non vide. Un clic appelle une nouvelle méthode (ex. `insert_selected_lora_trigger_into_prompt()`) qui :

- lit le prompt actuel via `prompt_text()` ;
- si le trigger est déjà présent comme élément exact du prompt (prompt découpé par `,`, chaque élément strippé, comparaison exacte sensible à la casse — voir section 12 pour la confirmation de cette règle), ne fait rien ;
- sinon, prompt vide → nouveau prompt = trigger seul ; prompt non vide → nouveau prompt = `"{trigger}, {prompt existant}"`, écrit via `set_prompt_text()`.

Cette méthode n'est **jamais** appelée automatiquement : ni par `refresh_lora_selector()`, ni par `_on_lora_selection_changed()`, ni par `MainWindow._on_training_use_lora_in_inference()` (le médiateur du handoff Mission 109, non modifié par cette mission) — le prompt reste strictement inchangé lors du handoff Training → Inference, conformément à Mission 109 et reconfirmé ici.

## 4. Périmètre exact — fichiers concernés

- `src/ui/pages/training_page.py` (modifié) — un seul changement, l'appel `import_lora(..., trigger_word=training.trigger_word)`.
- `src/ui/pages/inference_page.py` (modifié) — nouveau label + bouton, méthode de rafraîchissement partagée, méthode d'insertion.
- `tests/integration/test_training_roundtrip.py` (modifié) — carryover du trigger à l'import.
- `tests/integration/test_inference_page.py` (modifié) — affichage/état du trigger, insertion dans toutes ses variantes, non-duplication.
- `docs/missions/MISSION_110.md` (ce document).

**Toute nécessité de modifier `LoRALibraryManager`, `TrainingManager`, un objet Domain, `MainWindow`, un Engine ou l'EventBus doit déclencher un arrêt et un rapport avant tout élargissement de cette liste.** Aucune modification attendue de ces fichiers — `import_lora()` accepte déjà `trigger_word`, aucun nouveau champ Domain n'est nécessaire (`LoRA.trigger_word`/`Training.trigger_word` existent déjà), et le handoff Mission 109 (`main_window.py::_on_training_use_lora_in_inference`) n'a besoin d'aucun changement puisque `refresh_lora_selector(target_lora_id=...)` reste le seul point d'entrée et continue de ne jamais toucher au prompt.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Préremplissage `Character.trigger_token → Training.trigger_word`.
- Liaison complète Character ↔ Training ↔ LoRA.
- Association `LoRA ↔ Character`.
- Génération automatique d'un trigger.
- Injection automatique du trigger dans le prompt, en toute circonstance — y compris pendant le handoff Mission 109.
- Modification automatique du prompt pendant le handoff `Training → "Utiliser dans Inference" → Inference`.
- Refonte générale de l'UX `InferencePage`.
- Correctif de détection des sidecars `.txt` depuis la galerie (Candidat 2 de l'audit post-M109).
- Captioning assisté par IA (Candidat 3 de l'audit post-M109).
- Gestion Start/Stop/Recheck des backends.
- Restructuration de `SettingsPage`.
- Fooocus.
- Tout autre besoin futur déjà documenté dans `docs/PROJECT_CONTEXT.md`.

## 6. Étapes techniques attendues

1. **`src/ui/pages/training_page.py`** :
   - Dans `import_selected_job_to_library()`, étendre l'appel existant : `self.lora_library_manager.import_lora(name.strip(), [job.final_output_path], library_root=library_root, trigger_word=training.trigger_word)`. Aucun autre changement dans cette méthode.

2. **`src/ui/pages/inference_page.py`** :
   - Nouveaux widgets dans une ligne dédiée, juste après `lora_row` (à côté de `lora_strength_label`/`lora_strength_spinbox`, même esprit que le placement libre déjà pratiqué en Mission 109) : `self.lora_trigger_label = QLabel("")` et `self.insert_lora_trigger_button = QPushButton("Insérer le trigger")`, ce dernier `setEnabled(False)` initialement.
   - Nouvelle méthode `_refresh_lora_trigger_widgets()` : relit `self._lora_library_manager.get(self._selected_lora_choice)` si `self._selected_lora_choice` est non vide, met à jour `lora_trigger_label.setText(lora.trigger_word)` et `insert_lora_trigger_button.setEnabled(bool(lora and lora.trigger_word))` ; si aucun LoRA sélectionné ou introuvable, label vidé et bouton désactivé.
   - Appel de `_refresh_lora_trigger_widgets()` ajouté à la fin de `_on_lora_selection_changed()` et à la fin de `refresh_lora_selector()` — les deux seuls points existants qui font varier `self._selected_lora_choice`.
   - Nouvelle méthode `insert_selected_lora_trigger_into_prompt()`, connectée au clic du bouton : relit le trigger courant (même relecture fraîche que `_refresh_lora_trigger_widgets()`, jamais une valeur mise en cache dans le label), applique la règle d'insertion de la section 3.3, `set_prompt_text()` uniquement si une insertion réelle a lieu.

Aucun changement à `MainWindow`, `LoRALibraryManager`, `TrainingManager`, ni au Domain.

## 7. Tests attendus

`tests/integration/test_training_roundtrip.py` (extension) :

1. `import_selected_job_to_library()` transmet exactement `training.trigger_word` à `import_lora()` — LoRA importé porte ce `trigger_word`.
2. `training.trigger_word == ""` → LoRA importé avec `trigger_word == ""`, comportement inchangé.

`tests/integration/test_inference_page.py` (extension) :

3. Sélection d'un LoRA avec `trigger_word` non vide → label affiche exactement ce trigger, bouton d'insertion activé.
4. Changement de sélection vers un autre LoRA → label et état du bouton mis à jour en conséquence (pas de valeur résiduelle de l'ancien LoRA).
5. Sélection d'un LoRA sans `trigger_word` (ou "Aucun LoRA") → label vide, bouton désactivé.
6. Insertion dans un prompt vide → prompt devient exactement le trigger seul.
7. Insertion dans un prompt existant → trigger inséré en tête, séparé par `", "`, reste du prompt strictement inchangé.
8. Trigger déjà présent comme élément exact du prompt → clic sur insertion ne modifie pas le prompt (pas de duplication).
9. `refresh_lora_selector(target_lora_id=...)` (mirroir du handoff Mission 109) présélectionne le bon LoRA, met à jour le label/bouton du trigger, et **ne modifie jamais le prompt** — non-régression explicite du contrat Mission 109.
10. Non-régression du comportement Mission 108/109 sans rapport avec le trigger (sélection LoRA, force du LoRA, présélection par `target_lora_id`).

Aucun appel réseau réel, aucun ComfyUI/Forge/GPU réel sollicité par aucun de ces tests.

## 8. Smoke réel attendu

Aucune génération réelle ComfyUI/Forge n'est nécessaire — cette mission ne modifie pas l'exécution des moteurs. Si Claude peut observer ce comportement de façon fiable avec des widgets Qt réels, il exécute ce smoke lui-même, en confirmant par lecture d'état réel des widgets :

1. Sélectionner, dans une `InferencePage` réelle, un LoRA de la Central Library possédant un `trigger_word` non vide.
2. Vérifier que le trigger s'affiche correctement.
3. Cliquer sur l'action d'insertion.
4. Vérifier que le prompt est modifié correctement (trigger en tête, séparation `", "` si un prompt existait déjà).
5. Cliquer une seconde fois sur l'action d'insertion et vérifier l'absence de duplication.

Si un point précis s'avère non observable de façon fiable, seul ce point est délégué à l'architecte avec une action et une vérification exactes à effectuer — jamais l'ensemble du smoke par défaut.

## 9. Critères de clôture

1. `TrainingPage`/`InferencePage` implémentés exactement selon le périmètre de la section 6, testés selon la section 7.
2. Le carryover Training → LoRA fonctionne pour un `trigger_word` vide comme non vide, sans régression.
3. L'insertion du trigger n'est jamais automatique, en toute circonstance — vérifié explicitement par un test couvrant le handoff Mission 109.
4. Aucune duplication du trigger lorsqu'il est déjà présent comme élément exact du prompt.
5. Zéro modification de `LoRALibraryManager`/`TrainingManager`/Domain/`MainWindow`/Engines/EventBus.
6. Suite complète verte au nombre exact, `git diff --check` propre.
7. Aucun élément de la section 5 n'a été ajouté.
8. Smoke réel (section 8) exécuté et documenté, avec délégation précise à l'architecte uniquement pour ce qui n'est pas observable de façon fiable.

## 10. Documentation

- Cette mission ne modifie ni ne referme aucun des besoins futurs déjà enregistrés dans `docs/PROJECT_CONTEXT.md` (liaison Character/Training/LoRA complète, association LoRA↔Character, refonte UX/UI d'Inference, gestion automatique des backends, sidecars galerie, captioning IA, réorganisation Settings, etc.) — tous restent explicitement ouverts et non tranchés.
- La régularisation documentaire post-clôture (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`) suivra le même processus que les missions précédentes, après commit/tag/Release.

## 11. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte.

## 12. Point découvert pendant la rédaction nécessitant une confirmation

**Règle exacte de non-duplication (section 3.3, test 8)** : la mission décrit "si le trigger exact est déjà présent comme élément du prompt". Le comportement retenu par défaut pour cette rédaction, à confirmer avant implémentation :

- le prompt est découpé par `,` ;
- chaque élément est strippé de ses espaces ;
- la comparaison au `trigger_word` est **exacte et sensible à la casse** (pas une recherche de sous-chaîne n'importe où dans le prompt, pas de comparaison insensible à la casse).

Conséquence pratique : `"Dmlrwoman, portrait"` ne serait **pas** reconnu comme doublon de `dmlrwoman` (casse différente), et `"a dmlrwoman standing"` (sans virgule séparatrice) ne serait pas non plus reconnu comme doublon (le trigger n'est pas un élément séparé par `,`) — seule une réinsertion sur un prompt dont le trigger est déjà un élément `,`-séparé identique caractère pour caractère est bloquée. Si un comportement différent est souhaité (insensible à la casse, ou détection en sous-chaîne indépendamment des virgules), merci de le préciser avant implémentation — sinon la règle ci-dessus sera celle implémentée.
