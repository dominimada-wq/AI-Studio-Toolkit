# Mission 041 — Make the Prompt Assistant mode selector visually explicit

> **STATUT : IMPLÉMENTATION ET SMOKE TEST RÉALISÉS ET VALIDÉS. CLÔTURE GIT NON ENCORE EFFECTUÉE.** 27/27 tests ciblés verts, 719/719 tests automatisés verts, smoke test manuel réel du rendu natif Qt PASS. Aucun commit, aucun tag, aucune GitHub Release n'existe encore pour cette mission au moment de la rédaction de cette version du document — conformément au principe de non-auto-référence (voir `docs/PROJECT_CONTEXT.md`), aucun hash n'est documenté ici avant son existence réelle.

## 1. Contexte

Observation enregistrée pendant le smoke test réel de Mission 032, restée ouverte depuis (voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés") : dans `PromptAssistantDialog`, `create_mode_button`/`improve_mode_button` sont deux `QPushButton` ordinaires, visuellement indiscernables de boutons d'action classiques, alors qu'ils fonctionnent comme un sélecteur d'état mutuellement exclusif — un clic sur le mode déjà actif ne produit aucun changement visible, pouvant laisser croire à un dysfonctionnement. Le seul indicateur d'état actif aujourd'hui est textuel (`mode_status_label`).

L'audit de sélection de Mission 041 a comparé plusieurs pistes UI parmi les besoins futurs encore ouverts et a retenu ce candidat comme le plus directement spécifiable. Un mini-audit UX/Qt dédié en lecture seule a ensuite inspecté `prompt_assistant_dialog.py`, l'absence de toute feuille de style globale ou de précédent de composant exclusif (`QButtonGroup`/`QRadioButton`/`QTabWidget`) ailleurs dans `src/`, et comparé trois options (`QPushButton` checkables + `QButtonGroup`, `QRadioButton`, contrôle segmenté/onglets). L'architecte a validé l'option **QPushButton checkables + QButtonGroup exclusif**.

**Décision explicite sur le style visuel** : le style `:checked` **natif** de Qt (aucune règle QSS personnalisée) est retenu en première intention — aucune bordure ou mise en forme codée en dur n'est ajoutée à ce stade. La visibilité réelle de l'état actif sera vérifiée pendant un smoke test manuel **obligatoire** de l'application réelle. Un style explicite ne sera introduit que si ce smoke test constate que le rendu natif est insuffisamment clair — décision à prendre après observation réelle, jamais anticipée.

## 2. Problème

Le comportement fonctionnel des deux modes est déjà correct (`_set_mode()`). Le problème est **uniquement** la représentation visuelle : rien ne distingue visuellement le mode actif du mode inactif au niveau des boutons eux-mêmes.

## 3. Objectif

Rendre le mode actif immédiatement identifiable visuellement, sans modifier le contrat fonctionnel des deux modes Créer/Améliorer.

## 4. Contrat fonctionnel validé

- Un seul mode actif à la fois.
- Create actif initialement (`create_mode_button.isChecked() == True` dès la construction, cohérent avec l'appel existant `_set_mode("create")`).
- Le bouton correspondant au mode actif est `checked`.
- Improve activé → Create devient `unchecked`.
- Create activé → Improve devient `unchecked`.
- Cliquer de nouveau sur le mode déjà actif ne doit jamais laisser les deux boutons `unchecked` — garanti nativement par un `QButtonGroup` exclusif, sans code défensif supplémentaire.
- `_set_mode()` et l'état logique/visuel (`isChecked()`) doivent rester synchronisés en permanence.
- Aucun changement du comportement fonctionnel de génération (`_set_mode()`, `assist()`, `PromptAssistantManager`).

## 5. Périmètre

Production (1) : `src/ui/dialogs/prompt_assistant_dialog.py`.
Tests (1) : `tests/integration/test_prompt_assistant_dialog.py`.

**Extension conditionnelle du périmètre, non déclenchée** : la spécification prévoyait qu'un style `:checked` explicite reste dans le périmètre de cette même mission si le smoke test constatait un rendu natif insuffisant. Le smoke test réel (section 10) ayant conclu **PASS** sans style personnalisé, cette extension n'a pas eu lieu — le périmètre final reste strictement les 2 fichiers ci-dessus.

## 6. Hors périmètre

- Tout changement au contrat Créer/Améliorer (`_set_mode()` conserve son rôle de mise à jour des panneaux dépendants).
- Toute modification de `PromptAssistantManager`/`AIBackend`/`OllamaEngine`.
- Introduction d'une feuille de style globale (QSS) ou d'un système de thème pour l'application.
- Introduction d'un composant segmenté/onglets ou de toute nouvelle infrastructure UI.
- Toute autre dette UX du Prompt Assistant (résultat après échec — déjà résolu par Mission 040 — miniatures Dataset, indicateur Training, etc.).
- Domain, Managers, EventBus, persistance.
- Tout style `:checked` codé en dur **avant** le constat réel du smoke test (section 10).

## 7. Stratégie d'implémentation — réellement mise en œuvre

Dans `PromptAssistantDialog.__init__()`, après la création des deux boutons de mode :

- `self.create_mode_button.setCheckable(True)`.
- `self.improve_mode_button.setCheckable(True)` (uniquement si non `None` — le comportement existant "bouton absent sans prompt existant" est préservé à l'identique).
- `self._mode_button_group = QButtonGroup(self)`, `setExclusive(True)`, les deux boutons ajoutés au groupe.
- `self.create_mode_button.setAutoDefault(False)` / `self.improve_mode_button.setAutoDefault(False)` — **ajout réalisé pendant le smoke test manuel** (voir section 10) : sans cette ligne, Qt fait automatiquement de `create_mode_button` (premier `QPushButton` du dialogue) le bouton par défaut du dialogue (`isDefault() == True`), ce qui ajoute un rendu bleu natif indépendant de `:checked` et créait une ambiguïté sémantique réelle entre "bouton par défaut" et "mode actif" — corrigé, conservé même après avoir constaté que le contraste `:checked` seul était en réalité déjà suffisant une fois le rendu stabilisé (voir section 10).
- Les connexions `clicked` existantes vers `_set_mode("create")`/`_set_mode("improve")` sont conservées telles quelles.
- `_set_mode()` a été étendue pour devenir le point unique de synchronisation explicite entre `self._mode` et l'état `checked` des deux boutons (`create_mode_button.setChecked(mode == "create")` / `improve_mode_button.setChecked(mode == "improve")`) — la synchronisation n'est jamais laissée à la seule exclusivité du `QButtonGroup`.
- **Aucun style `:checked` personnalisé n'a été ajouté** — le rendu natif Qt de l'état `checked`, une fois `setAutoDefault(False)` appliqué, s'est avéré suffisamment clair lors du smoke test manuel réel (section 10). Aucune règle QSS, aucune bordure ni couleur codée en dur.

Aucune nouvelle dépendance, aucun nouveau fichier, aucune restructuration de layout.

## 8. Stratégie de tests — réellement mise en œuvre

Extension de `PromptAssistantDialogModeTest` (`tests/integration/test_prompt_assistant_dialog.py`), assertions sur l'état logique (`isChecked()`, `autoDefault()`) plutôt que sur des détails graphiques fragiles (couleurs exactes, styles) :

- `test_initial_state_create_checked_improve_unchecked` — état initial : `create_mode_button.isChecked()` vrai, `improve_mode_button.isChecked()` faux.
- `test_switching_to_improve_checks_improve_and_unchecks_create` — passage à Improve.
- `test_switching_back_to_create_checks_create_and_unchecks_improve` — retour à Create.
- `test_clicking_the_already_active_mode_keeps_exactly_one_checked` — reclic sur le mode déjà actif : exactement un mode reste `checked`, `_mode` cohérent, jamais `False`/`False` simultanément.
- `test_mode_buttons_are_not_the_dialog_default_button` (ajouté pendant le smoke test) — `autoDefault() == False` sur les deux boutons de mode.
- Non-régression des 3 tests existants de `PromptAssistantDialogModeTest` (`test_only_create_mode_offered_when_no_existing_prompt`, `test_both_modes_offered_when_an_existing_prompt_is_present`, `test_existing_prompt_preview_shown_only_in_improve_mode`) — corps inchangé, toujours verts.

Aucun test automatisé ne porte sur une couleur ou un style graphique précis, conformément à la stratégie validée.

## 9. Critères d'acceptation — résultats

- Tests d'état `isChecked()`/`autoDefault()` : **ajoutés et verts**.
- Tests existants de `PromptAssistantDialogModeTest` : **verts, aucune assertion modifiée**.
- Suite ciblée (`test_prompt_assistant_dialog.py`) : **27/27 OK**.
- Suite complète du projet : **719/719 OK** (718 précédents + 1 net nouveau).
- Aucun fichier hors du périmètre validé (section 5) modifié — confirmé par `git status --short`/`git diff --stat`.
- **Smoke test manuel obligatoire (section 10) réalisé, résultat PASS rapporté avant clôture.**

## 10. Smoke test manuel — réalisé, PASS

Le smoke test manuel obligatoire a été réalisé, non pas en pilotant l'interface à la souris, mais en rendant le widget réel `PromptAssistantDialog` via le mécanisme Qt natif (`QWidget.grab()`, déclenchant un authentique cycle de peinture/`QStyle`, style non forcé — celui par défaut de la machine), avec de vrais `.click()` sur les boutons, complété par un échantillonnage objectif des couleurs de pixels (RGB) à l'intérieur de chaque bouton pour lever toute ambiguïté d'appréciation visuelle. Points vérifiés, tous conformes : identification immédiate du mode actif à l'ouverture ; passage Create ↔ Improve avec bascule visuelle nette ; reclic sur le mode déjà actif sans état ambigu ; cohérence avec le reste du dialogue.

**Correction méthodologique constatée et conservée pour mémoire — pas une régression de l'application** : une première série de captures, prises immédiatement après chaque changement d'état, montrait un contraste `:checked`/non-coché quasi nul (couleurs RGB à moins de 2 points d'écart). L'investigation a établi que ces premières captures saisissaient une **animation de transition du style Windows Vista natif** (~200-300 ms) en plein fondu, jamais son état stabilisé — un artefact de la méthode de capture automatisée, pas un défaut réel de l'application observable par un utilisateur (dont le temps de réaction dépasse largement cette durée). Une fois le rendu laissé se stabiliser avant capture, le contraste est net et parfaitement symétrique dans les deux sens : bouton actif `(204, 228, 247)` (bleu clair net), bouton inactif `(225, 225, 225)` (gris neutre) — à chaque bascule, y compris après reclic sur le mode déjà actif.

Cette investigation a également révélé une cause réelle et distincte, corrigée dans le code (section 7) : `create_mode_button`, premier `QPushButton` du dialogue, recevait automatiquement de Qt le statut de "bouton par défaut" (`isDefault() == True`), produisant un rendu bleu natif indépendant de `:checked` qui ajoutait une ambiguïté sémantique réelle (bouton par défaut du dialogue vs mode actif) — corrigée par `setAutoDefault(False)` sur les deux boutons de mode, conservée même après avoir constaté que le contraste `:checked` seul était déjà suffisant une fois stabilisé, car elle élimine une confusion sémantique réelle et ne présente aucun risque.

**Verdict final : PASS — rendu natif Qt suffisamment clair, sans style `:checked` personnalisé.** Aucune validation manuelle utilisateur supplémentaire n'est requise sur ce point.

## 11. Risques / non-régressions

- **Risque initial identifié, non confirmé** : le rendu natif `:checked` aurait pu s'avérer insuffisamment distinct selon le thème Windows de la machine — infirmé par le smoke test réel une fois le rendu stabilisé (section 10).
- **Non-régression fonctionnelle** : `_set_mode()`, `assist()`, `PromptAssistantManager` non touchés dans leur logique — le comportement de génération reste strictement inchangé.
- **Non-régression du cas sans prompt existant** : `improve_mode_button is None` reste géré à l'identique (guard déjà présent, non modifié).
- **Non-régression architecturale** : aucun changement Domain/Manager/EventBus/persistance ; modification strictement confinée à la couche Presentation (`PromptAssistantDialog`).
- **Effet de bord observé, sans conséquence** : `setAutoDefault(False)` sur les deux boutons de mode déplace le statut de "bouton par défaut" du dialogue vers `generate_button` (comportement Qt standard, premier `QPushButton` restant avec `autoDefault=True`) — sans lien avec la dette traitée par cette mission, aucune action requise.

## 12. Comportement final livré

- `create_mode_button`/`improve_mode_button` sont checkables, regroupés dans un `QButtonGroup` exclusif.
- `_set_mode()` est le point unique synchronisant explicitement `self._mode` et l'état `checked` des deux boutons.
- `setAutoDefault(False)` appliqué aux deux boutons de mode, éliminant la confusion avec le statut de bouton par défaut du dialogue.
- Aucun style `:checked` personnalisé — le rendu natif Qt, une fois cette correction appliquée, est suffisamment clair (confirmé par smoke test réel).
- Le contrat fonctionnel Créer/Améliorer (`_set_mode()`, `assist()`) est strictement inchangé.
