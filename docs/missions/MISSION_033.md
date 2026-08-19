# Mission 033 — Prompts → Envoyer vers Inference

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 619/619 tests automatisés verts, smoke test manuel réel PASS, clôture Git effectuée, GitHub Release `v0.2-mission033` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Mission 031 a livré le Prompt Assistant dans `InferencePage` uniquement (Option B tactique). Mission 032 en a fait un second consommateur réel dans `PromptsPage` (Option C confirmée comme architecture long terme), sans jamais câbler de sens `Prompts → Inference` — ce sens restait explicitement hors périmètre, confirmé absent par le smoke test réel de Mission 032. `PROJECT_CONTEXT.md` désigne ce besoin comme le candidat le plus mûr pour prolonger la boucle `Créer/sélectionner un Prompt → Assistant IA → édition → génération`.

## 2. Objectif

Permettre à l'utilisateur d'envoyer, depuis `PromptsPage`, le texte **actuellement visible** dans l'éditeur vers `InferencePage`, avec navigation automatique, sans jamais provoquer de sauvegarde implicite du Prompt ni de couplage direct entre les deux Pages.

## 3. Audit ciblé — constats vérifiés par lecture directe du code

- **`InferencePage.prompt`** ([inference_page.py:92](src/ui/pages/inference_page.py:92)) est un `QTextEdit` ordinaire, sans getter/setter public dédié aujourd'hui — tout accès externe devrait passer directement par le widget.
- **`InferencePage.save_prompt_button`** ([inference_page.py:111-117](src/ui/pages/inference_page.py:111)) suit déjà le pattern « activation dynamique selon le texte » via `_on_prompt_text_changed()` ([inference_page.py:216-217](src/ui/pages/inference_page.py:216)) — `setEnabled(bool(text.strip()))` — plutôt qu'un message au clic. C'est le seul précédent directement analogue (action optionnelle sur le texte actuellement dans un éditeur) dans toute la base.
- **`PromptsPage.save_text()`** ([prompts_page.py:137-147](src/ui/pages/prompts_page.py:137)) ne vérifie que `active_prompt_id is not None` — aucune garde sur le texte vide n'existe aujourd'hui côté `PromptsPage`.
- **Aucun `QMessageBox.question()` n'existe nulle part dans `src/`** (recherche exhaustive) — ce sera le premier usage d'une confirmation Oui/Non-like dans l'application. Tous les usages existants (`.warning`/`.critical`/`.information`) sont informatifs, jamais des confirmations d'action.
- **Précédent de communication inter-pages déjà existant** : `MainWindow` connecte directement `self.dashboard_page.importImagesButton.clicked` à `self.images_page.import_images` ([main_window.py:235-237](src/ui/main_window.py:235)) — un signal Qt d'une Page, câblé par `MainWindow`, vers une méthode publique d'une autre Page. Aucun `EventBus` impliqué. C'est un précédent architectural direct pour le flux demandé.
- **`Sidebar`** ([sidebar.py](src/ui/sidebar.py)) expose déjà `self.pages` (liste ordonnée `(titre, nom)`) et `page_name(index)` (index → nom), mais aucune méthode inverse (nom → sélection). `MainWindow.sidebar.currentRowChanged` pilote `stack.setCurrentIndex` — l'alignement positionnel `Sidebar.pages`/`stack.addWidget()` est la règle déjà documentée dans `CLAUDE.md`.
- **`EventBus`** ([event_bus.py](src/core/event_bus.py)) : chaque événement publié aujourd'hui correspond à une mutation Domain réelle effectuée par un Manager (`"prompt.created"`, `"workspace.saved"`, etc.) — jamais à une intention Presentation-layer pure. Aucun événement existant ne correspond à « l'utilisateur veut transférer du texte d'une Page à une autre » : ce ne serait pas une mutation Domain, seulement une chorégraphie UI.
- **Patron de test déjà établi pour `MainWindow`** (`test_main_window_new_project.py`) : construction d'un vrai `MainWindow()`, mock ciblé des seules frontières externes (dialogues, `QMessageBox`), assertions sur les appels — nouveau fichier de test dédié et étroit, pas de suite `MainWindow` généraliste.

## 4. Décisions d'architecture proposées

### 4.1 Communication inter-pages : Option A retenue (signal Qt + MainWindow médiateur)

**Option A — signal Qt + MainWindow médiateur** : `PromptsPage` émet un signal Qt propre (`send_to_inference_requested`, `str`) ; `MainWindow` le connecte à une méthode privée qui orchestre la logique de collision puis appelle une méthode publique d'`InferencePage`.

**Option B — EventBus** : publier un événement type `"prompt.send_to_inference_requested"`.

**Recommandation : Option A.** Justification à partir de l'audit ci-dessus, pas d'une préférence a priori :
- La règle permanente `CLAUDE.md` (« Event Driven UI — les pages ne se rafraîchissent jamais par appel direct entre elles ; uniquement via l'EventBus ») encadre le **rafraîchissement des Pages en réaction à une mutation Domain publiée par un Manager** — chaque événement existant est nommé `"domaine.verbe"` et défini dans un module Manager. Il n'existe ici **aucune mutation Domain** : aucun Manager n'est impliqué, aucun `Prompt`/`Character`/`Workspace` ne change d'état. Créer un événement `EventBus` pour ce cas inventerait un pseudo-événement Domain pour une pure intention Presentation-layer — un détournement du contrat existant, pas une réutilisation légitime.
- Le précédent déjà réel et fonctionnel (`Dashboard.importImagesButton` → `MainWindow` → `ImagesPage.import_images`) est exactement de cette nature : signal Qt d'une Page, câblé exclusivement par `MainWindow`, vers une autre Page. Mission 033 reproduit ce patron existant plutôt que d'en introduire un nouveau.
- `PromptsPage` ne connaît toujours pas `InferencePage` : elle émet un signal sur elle-même, sans jamais importer ni référencer `InferencePage`. Seul `MainWindow` (déjà le point unique connaissant toutes les Pages) relie les deux.

### 4.2 Méthodes publiques d'`InferencePage`

Deux méthodes minimales, un-liners, ajoutées à `InferencePage` :

```python
def prompt_text(self) -> str:
    return self.prompt.toPlainText()

def set_prompt_text(self, text: str) -> None:
    self.prompt.setPlainText(text)
```

**Justification** : sans elles, `MainWindow` devrait lire/écrire directement `self.inference_page.prompt` (un `QTextEdit` interne). Ces deux méthodes ne créent aucune abstraction nouvelle — elles rendent explicite une frontière déjà implicite (comme `reset_for_workspace_change()`, déjà une méthode publique intentionnelle d'`InferencePage` appelée depuis `MainWindow`), et permettent de tester `InferencePage` indépendamment de la structure interne de son widget. Alternative rejetée : accès direct à `self.inference_page.prompt.toPlainText()`/`.setPlainText()` depuis `MainWindow` — fonctionnellement suffisant mais expose un détail d'implémentation (le widget `QTextEdit` précis) au-delà de la frontière de la Page, contrairement au reste de la base où chaque Page n'expose que des méthodes/signaux nommés à ses appelants externes.

### 4.3 Navigation : `Sidebar.select_page(name)`

Nouvelle méthode additive sur `Sidebar` :

```python
def select_page(self, name: str) -> bool:
    for index, (_, page_name) in enumerate(self.pages):
        if page_name == name:
            self.setCurrentRow(index)
            return True
    return False
```

**Justification** : évite de coder en dur un index numérique (`9`) dans `MainWindow`, conformément à la consigne. `Sidebar` possède déjà `self.pages` (source de vérité de l'alignement positionnel) et `page_name(index)` (sens index→nom) — `select_page(name)` ajoute simplement le sens inverse, dans la classe qui porte déjà cette responsabilité, sans toucher `page_name()` ni `self.pages` existants. `MainWindow` appelle `self.sidebar.select_page("inference")`, qui déclenche `currentRowChanged` → `stack.setCurrentIndex` (mécanisme déjà existant, inchangé).

### 4.4 Bouton « Envoyer vers Inference » dans `PromptsPage` — texte vide

**Pattern retenu : désactivation dynamique**, reproduisant exactement `InferencePage.save_prompt_button`/`_on_prompt_text_changed` (seul précédent directement analogue — une action optionnelle sur le texte actuellement dans l'éditeur). `PromptsPage.text_edit.textChanged` pilote `send_to_inference_button.setEnabled(bool(text.strip()))`. Rejeté : un message d'avertissement au clic (pattern de `InferencePage.generate_button`), car ce pattern est réservé aux actions qui déclenchent un traitement lourd/bloquant (une génération) — pas à un simple transfert de texte, où l'analogie « Enregistrer dans Prompts » est plus proche.

### 4.5 Aucun Prompt actif, texte libre présent

Conforme à l'audit de `PromptsPage.text_edit` (jamais désactivé, jamais lié à `active_prompt_id` pour la lecture) : le bouton « Envoyer vers Inference » lit toujours `self.text_edit.toPlainText()` directement, **jamais** `self.prompt_manager.active_prompt_id`/le Domain `Prompt`. Aucun conflit avec l'architecture actuelle — c'est exactement le même principe que Mission 032 pour `existing_prompt` de l'Assistant (texte de l'éditeur, jamais relu depuis le Manager), simplement appliqué à un nouveau bouton.

### 4.6 Collision avec Inference

```python
def _on_prompts_send_to_inference(self, text):
    current = self.inference_page.prompt_text()

    if current.strip() and current != text:
        box = QMessageBox(self)
        box.setWindowTitle("Remplacer le prompt ?")
        box.setText(
            "Un prompt différent est déjà présent dans Inference. "
            "Voulez-vous le remplacer ?"
        )
        replace_button = box.addButton("Remplacer", QMessageBox.AcceptRole)
        cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
        box.setDefaultButton(cancel_button)
        box.exec()

        if box.clickedButton() is not replace_button:
            return

    self.inference_page.set_prompt_text(text)
    self.sidebar.select_page("inference")
```

- **Inference vide ou uniquement composé d'espaces** (`not current.strip()`) : transfert + navigation immédiats, aucune confirmation.
- **Inference contient exactement le même texte** (`current == text`, **comparaison exacte de chaînes** — aucune normalisation d'espaces/retours à la ligne/casse/ponctuation) : aucune confirmation ; `set_prompt_text` réappliqué (idempotent, sans effet visible) puis navigation.
- **Inference contient un texte différent** : `QMessageBox` à boutons personnalisés `Remplacer`/`Annuler` (français, cohérent avec `Accepter`/`Rejeter`/`Régénérer`/`Ignorer cet import` déjà dans l'app) — **premier usage d'une confirmation dans la base**, choix validé en l'absence de précédent réutilisable. Texte validé : *« Un prompt différent est déjà présent dans Inference. Voulez-vous le remplacer ? »*. Bouton par défaut : `Annuler` (choix prudent, non destructif).
- **Annulation** : aucun appel à `set_prompt_text`, aucun appel à `select_page`, aucune sauvegarde, l'utilisateur reste dans `PromptsPage` — `return` immédiat, exactement la garantie demandée.

## 5. Périmètre IN

- Nouveau bouton `send_to_inference_button` (« Envoyer vers Inference ») dans `PromptsPage`, désactivé dynamiquement si `text_edit` vide/espaces.
- Nouveau signal Qt `PromptsPage.send_to_inference_requested(str)`, émis avec le texte actuellement visible dans l'éditeur.
- `MainWindow` connecte ce signal à une nouvelle méthode privée orchestrant la logique de collision (section 4.6).
- Deux nouvelles méthodes publiques sur `InferencePage` : `prompt_text()`, `set_prompt_text(text)`.
- Nouvelle méthode publique `Sidebar.select_page(name)`.
- Navigation automatique vers `InferencePage` après transfert réussi (immédiat ou après confirmation acceptée).
- `QMessageBox` de confirmation (Remplacer/Annuler) uniquement en cas de texte différent déjà présent dans Inference.

## 6. Périmètre OUT (strict, explicitement différé)

- Character Context, « Utiliser l'identité ».
- Inspiration depuis anciens prompts, Prompt Library structurée, tags, RAG, embeddings.
- Vision/multimodal, image → analyse → prompt, Qwen3-VL, références d'identité.
- LoRA, modification d'`AIBackend`.
- Correction générale de la dette UX `PromptsPage` (perte de texte non sauvegardé sur événement `WORKSPACE_*`/`CHARACTER_*`/`PROMPT_*`) — non traitée, non aggravée.
- Refonte du Prompt Assistant (`PromptAssistantDialog`/`Manager`/`Worker` restent strictement inchangés).
- Tout retour automatique `Inference → Prompts`.
- Toute persistance/historique/provenance du transfert (`PromptManager.update_text()`, `save()`, ou toute modification du Domain `Prompt` restent explicitement exclus de ce flux).

## 7. Stratégie de tests prévue

Aucun test ne dépend d'Ollama/ComfyUI (mocks systématiques, comme Missions 031/032). Fichiers concernés :

**`tests/integration/test_prompt_roundtrip.py`** (extension de la classe `PromptsPagePromptAssistantTest` existante ou nouvelle classe voisine) :
- bouton présent, désactivé si `text_edit` vide/espaces, activé sinon (dynamique, comme `InferencePage.save_prompt_button`) ;
- clic émet `send_to_inference_requested` avec le texte actuellement visible (y compris un texte modifié non sauvegardé, aucun Prompt actif) ;
- aucune régression sur l'Assistant IA existant (le bouton `assistant_button` reste fonctionnel après ajout du nouveau bouton).

**Nouveau fichier `tests/integration/test_main_window_prompts_to_inference.py`** (même patron que `test_main_window_new_project.py` — vrai `MainWindow()`, mocks ciblés) :
- Inference vide → transfert immédiat, aucune `QMessageBox` affichée, `stack.currentWidget() is inference_page` ;
- Inference contient le même texte → aucune `QMessageBox`, navigation effectuée ;
- Inference contient un texte différent → `QMessageBox` affichée (patch de `src.ui.main_window.QMessageBox`) ;
- confirmation « Remplacer » → texte remplacé, navigation effectuée ;
- confirmation « Annuler » → `InferencePage.prompt` inchangé, `PromptsPage.text_edit` inchangé, pas de navigation (sidebar reste sur son `currentRow` précédent) ;
- aucun appel à `PromptManager.update_text()`/`create()` dans tout le flux (mock/spy) ;
- Domain `Prompt` (`character.prompts[i].text`) inchangé après un transfert, y compris après confirmation ;
- aucune vraie `QMessageBox` bloquante (classe entièrement patchée, jamais un `.exec()` réel).

**`tests/integration/test_inference_page.py`** (extension ciblée) :
- `prompt_text()`/`set_prompt_text()` fonctionnent indépendamment (lecture/écriture correctes du widget).

**`tests/integration/test_sidebar.py`** (nouveau fichier étroit, ou extension si un fichier existe déjà) :
- `select_page("inference")` positionne `currentRow` sur l'index réel d'Inference (dérivé de `self.pages`, jamais un littéral codé en dur dans le test) ;
- `select_page("nom_inexistant")` retourne `False`, ne modifie pas `currentRow`.

## 8. Fichiers qui seraient modifiés lors d'une implémentation

- `src/ui/pages/prompts_page.py` (signal, bouton, handler)
- `src/ui/pages/inference_page.py` (deux méthodes publiques)
- `src/ui/sidebar.py` (une méthode publique)
- `src/ui/main_window.py` (câblage du signal, méthode d'orchestration privée)
- `tests/integration/test_prompt_roundtrip.py`
- `tests/integration/test_main_window_prompts_to_inference.py` (nouveau)
- `tests/integration/test_inference_page.py`
- `tests/integration/test_sidebar.py` (nouveau ou étendu, selon existant)

Aucun Domain, aucun Manager, aucun Storage, aucun `AIBackend`/`PromptAssistantManager`/`PromptAssistantDialog` touché.

## 9. Critères d'acceptation proposés (pour une future implémentation validée)

- Bouton visible dans `PromptsPage`, désactivé si texte vide/espaces uniquement.
- Texte transféré = texte visible dans l'éditeur au moment du clic, jamais relu depuis le Domain `Prompt`.
- Fonctionne sans Prompt actif si du texte libre est présent.
- Inference vide/identique → aucune confirmation. Inference différent → confirmation Remplacer/Annuler.
- Annulation → aucun changement, aucune navigation.
- Transfert réussi → navigation automatique et exclusive vers `InferencePage`.
- Aucun `PromptManager.update_text()`/`create()`/`save()` déclenché par ce flux.
- Aucune régression sur l'Assistant IA (`InferencePage`/`PromptsPage`), aucune régression sur la suite existante.
- `PromptsPage` ne référence jamais `InferencePage` directement (aucun import croisé entre les deux modules Page).

## 10. Décisions finales validées par l'architecte

1. Texte de confirmation validé : *« Un prompt différent est déjà présent dans Inference. Voulez-vous le remplacer ? »*, boutons `Remplacer`/`Annuler`.
2. Emplacement du bouton dans `PromptsPage` : à proximité des actions d'utilisation/édition du prompt, après `save_button`, sans refonte du layout existant.
3. Nom de méthode retenu sur `Sidebar` : `select_page(name)`.
4. Aucune garde `workspace_manager.opened` ajoutée — confirmé non nécessaire, ce flux ne fait que transférer du texte entre deux widgets, sans déclencher de génération.
5. Comparaison Inference identique/différent : comparaison exacte de chaînes, aucune normalisation.

## 11. Fonctionnalités livrées (implémentation réelle)

- `PromptsPage` : nouveau bouton `send_to_inference_button` (« Envoyer vers Inference »), désactivé/activé dynamiquement selon `text_edit.toPlainText().strip()` (via `_on_text_changed()`, câblé sur `text_edit.textChanged`) ; nouveau signal `send_to_inference_requested(str)`, émis avec le texte exact de `text_edit` au moment du clic — jamais relu depuis `PromptManager`.
- `InferencePage` : deux nouvelles méthodes publiques minimales, `prompt_text() -> str` et `set_prompt_text(text: str) -> None`, simples délégations vers `self.prompt` (`QTextEdit`).
- `Sidebar` : nouvelle méthode publique `select_page(name) -> bool`, recherche dans `self.pages` déjà existant (aucun index codé en dur).
- `MainWindow` : connecte `prompts_page.send_to_inference_requested` à une nouvelle méthode privée `_on_prompts_send_to_inference(text)` qui applique exactement les règles de collision de la section 4.6 (comparaison de chaînes exacte, `QMessageBox` à boutons `Remplacer`/`Annuler` personnalisés uniquement si Inference contient un texte différent non vide), puis `inference_page.set_prompt_text(text)` + `sidebar.select_page("inference")`.
- Aucun appel à `PromptManager.update_text()`/`create()` ni à `WorkspaceManager.save()` dans tout le flux — vérifié par tests dédiés.

## 12. Tests ajoutés

- `tests/integration/test_prompt_roundtrip.py` — nouvelle classe `PromptsPageSendToInferenceTest` (8 tests) : bouton présent/désactivé à vide/espaces, activé avec texte (y compris sans Prompt actif), désactivé de nouveau après effacement, signal émis avec le texte exact (y compris texte non sauvegardé), aucun appel `update_text()`/`create()`.
- `tests/integration/test_inference_page.py` — 3 tests ajoutés à `InferencePagePromptAssistantTest` : `prompt_text()`/`set_prompt_text()` corrects, aucun effet de bord `PromptManager`.
- `tests/integration/test_sidebar.py` (nouveau fichier, 3 tests) : `select_page()` positionne la bonne ligne (dérivée de `self.pages`, jamais un littéral), fonctionne pour la première page, nom inconnu → `False` sans déplacement.
- `tests/integration/test_main_window_prompts_to_inference.py` (nouveau fichier, 8 tests) : Inference vide/espaces → transfert immédiat sans confirmation ; texte identique → aucune confirmation ; texte différent par un espace seul → confirmation quand même affichée (comparaison stricte, aucune normalisation) ; confirmation acceptée → remplacement + navigation ; confirmation annulée → aucun changement, aucune navigation ; aucun appel `PromptManager.update_text()`/`create()` ; aucun appel `WorkspaceManager.save()`. `QMessageBox` toujours entièrement mocké (`patch("src.ui.main_window.QMessageBox")`), aucune boîte modale réelle.

## 13. Résultats de tests

- Suite ciblée (4 fichiers concernés) : **110/110 OK**.
- Suite complète : **619/619 OK** (597 précédents + 22 nets nouveaux), une seule exécution après implémentation.
- Aucune dépendance Ollama/ComfyUI réelle dans les nouveaux tests.

## 14. Smoke test manuel réel — résultat

**Résultat global : PASS.** Aucune anomalie fonctionnelle constatée.

| Cas testé | Résultat |
|---|---|
| Texte vide dans `PromptsPage` → bouton désactivé | PASS |
| Texte présent → bouton activé, transfert possible depuis le texte visible | PASS |
| Transfert vers Inference (texte + navigation) | PASS |
| Texte visible/modifications locales non sauvegardées transférées telles quelles, sans sauvegarde préalable obligatoire | PASS |
| Collision — Inference vide → transfert direct | PASS |
| Collision — texte identique → navigation sans confirmation inutile | PASS |
| Collision — texte différent → confirmation affichée | PASS |
| Collision — Annuler → aucun remplacement | PASS |
| Collision — Remplacer → remplacement puis navigation | PASS |
| Absence de sauvegarde implicite du Domain `Prompt` | PASS |
| Non-régression Prompt Assistant (`PromptsPage`/`InferencePage`), navigation, édition des prompts | PASS |

## Commit correspondant

`2ee53f71780bb638b5ec9bd5af0603fb8d8241a2` — `feat: add Prompts to Inference transfer`. Inclut à la fois l'implémentation fonctionnelle (code + tests) et la documentation de clôture pré-publication de Mission 033 (commit unique, conforme au principe "un seul objectif" — la mission dans son ensemble).

## Tag / release correspondant

`v0.2-mission033` (annoté, message `Mission 033 - Prompts to Inference Transfer`), ciblant exactement `2ee53f71780bb638b5ec9bd5af0603fb8d8241a2`. GitHub Release `v0.2-mission033` **publiée**.

## État d'avancement

- Spécification : **validée**.
- Implémentation : **réalisée**, conforme à la spécification section 4 et aux décisions finales section 10.
- Tests automatisés ciblés (110/110) et suite complète (619/619) : **exécutés, verts**.
- Smoke test manuel réel : **PASS** (voir section 14).
- Clôture Git : **effectuée** — commit fonctionnel `2ee53f71780bb638b5ec9bd5af0603fb8d8241a2`, tag `v0.2-mission033`.
- GitHub Release : **publiée**.

## État final

Mission 033 — Prompts → Envoyer vers Inference — est **entièrement close** : implémentation, 619/619 tests automatisés, smoke test manuel réel complet PASS, clôture Git et publication GitHub Release toutes effectuées.
