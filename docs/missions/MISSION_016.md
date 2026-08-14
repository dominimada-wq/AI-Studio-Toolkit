# Mission 016 — Direct Project Folder Creation

Source : historique direct de la conversation de développement (audit architectural préalable comparant quatre besoins futurs, spécification validée, implémentation, revue technique finale, smoke test manuel réel repris intégralement après un incident externe), vérifié contre le code réel et la suite de tests.

## Objectif

Permettre à l'utilisateur de créer directement un nouveau dossier de projet depuis le flux "Nouveau projet" d'AI Studio Toolkit — choix d'un dossier parent existant, saisie du nom du projet, création automatique du dossier et de la structure Workspace, ouverture immédiate — sans devoir créer ce dossier au préalable dans l'Explorateur Windows.

## Problème UX initial

Le flux "Nouveau projet" reposait uniquement sur `QFileDialog.getExistingDirectory()`, qui force structurellement le choix d'un dossier **déjà existant**. Aucun chemin de code ne permettait de créer un nouveau dossier directement depuis l'application : l'utilisateur devait créer le dossier cible dans l'Explorateur Windows, revenir dans AI Studio Toolkit, puis le sélectionner. Ce besoin avait été identifié par l'usage réel pendant le smoke test de Mission 015 (voir `docs/missions/MISSION_015.md`, section "Dettes hors périmètre").

Un audit architectural préalable a comparé ce besoin à trois autres besoins futurs identifiés (galerie/miniatures `ImagesPage`, images de référence `InferencePage`, sélection multi-engine/backend). Ce dernier a été jugé le plus atomique et le moins risqué : `WorkspaceManager.create()`/`WorkspaceStorage.create_directories()` géraient déjà, avant toute modification, la création d'un dossier inexistant (`Path.mkdir(parents=True, exist_ok=True)`) — seule l'UI empêchait d'exploiter cette capacité déjà présente.

## Périmètre

**IN** : nouveau dialogue dédié (`NewProjectDialog`), choix du dossier parent, saisie et validation du nom de projet, construction et validation du chemin cible, câblage dans `MainWindow.new_project()`.

**OUT** : `Workspace` Domain, `WorkspaceManager`, `WorkspaceStorage`, `EventBus`, `open_project()`, `save_project()`, galerie/miniatures `ImagesPage`, images de référence, sélection multi-engine, projets récents, templates de projet, renommage/suppression de projet.

## Comportement implémenté

- **`NewProjectDialog`** (`src/ui/dialogs/new_project_dialog.py`) : champ dossier parent (lecture seule) + bouton "Parcourir..." (limité au choix du parent, via le `QFileDialog.getExistingDirectory()` existant), champ nom de projet, label d'aperçu affichant en permanence soit le chemin final calculé, soit le message d'erreur exact expliquant pourquoi "Créer" reste désactivé.
- **Construction du chemin** : `Path(parent_directory) / name`, exactement — aucun `strip()` silencieux, aucune extension ajoutée, aucune normalisation destructive, aucune création anticipée sur le disque. Le dialogue ne crée jamais rien lui-même ; il ne fait que construire et valider un `target_path`.
- **Validation du nom** (couche Presentation uniquement, `validate_project_name()`) : chaîne vide ou uniquement composée d'espaces, `"."`/`".."`, séparateurs `/`et `\`, caractères Windows interdits (`< > : " | ? *`), nom se terminant par un espace ou un point, noms réservés Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`, y compris avec extension) — tous refusés avec un message distinct. Les noms proches mais valides (`CONSOLE`, `COM10`, `LPT10`, `AUXILIARY`) et les noms avec espaces internes normaux (`"My Project"`) restent acceptés.
- **Gestion des collisions** : si le chemin cible (dossier **ou** fichier) existe déjà, "Créer" reste désactivé et un message explicite est affiché — jamais de réutilisation silencieuse, jamais d'écrasement de `project.json` existant. La collision est **revérifiée à l'instant exact du clic sur "Créer"** (`_on_accept_clicked()`), pas seulement lors de la dernière frappe : si la cible apparaît sur le disque entre la dernière validation visuelle et le clic, le dialogue reste ouvert, "Créer" se désactive, le message de collision s'affiche, et `WorkspaceManager.create()` n'est jamais appelé.
- **Annulation / fermeture par X** : les deux comportent identiquement — aucun dossier créé, aucun Workspace créé, `target_path` reste `None`, `MainWindow` reste dans son état précédent.
- **Câblage `MainWindow.new_project()`** : `NewProjectDialog(self).exec()` ; si `Rejected`, retour immédiat sans appel ; si `Accepted`, `WorkspaceManager.create(dialog.target_path)` appelé exactement comme l'ancien flux (même gestion `WorkspaceManagerError`/`QMessageBox.critical`), `WORKSPACE_CREATED` continue d'assurer le rafraîchissement normal, le nouveau Workspace est ouvert immédiatement.
- **Aucune modification** de `Workspace` Domain, `WorkspaceManager`, `WorkspaceStorage`, `EventBus`, `open_project()`, `save_project()` — `WorkspaceManager.create()` était déjà capable, avant cette mission, de créer un dossier inexistant et sa structure complète.

## Fichiers source concernés

- **Créé** : `src/ui/dialogs/new_project_dialog.py` (`NewProjectDialog`, `validate_project_name()`).
- **Modifié** : `src/ui/main_window.py` — import de `QDialog` et `NewProjectDialog`, corps de `new_project()` remplacé (remplacement de l'appel direct à `QFileDialog.getExistingDirectory()` par l'ouverture du nouveau dialogue). Aucune autre méthode de `MainWindow` modifiée.

## Stratégie de validation

Trois niveaux, comme pour les missions précédentes :

1. **Tests automatisés** (widgets Qt réels, `NewProjectDialog` jamais appelée via un `.exec()` réel dans les tests de câblage `MainWindow` — même précédent que Mission 014/015 pour éviter tout modal bloquant le process de test).
2. **Revue technique finale ciblée** sur les invariants d'état de `target_path` (jamais d'ancienne valeur exposée après un état devenu invalide), la revalidation de collision à l'instant de l'Accept, et les cas limites du dossier parent (inexistant, fichier, Browse annulé) — aucune divergence réelle trouvée, uniquement des tests supplémentaires ajoutés pour le prouver explicitement.
3. **Smoke test manuel réel**, repris intégralement depuis zéro après un incident d'affichage/connexion externe survenu pendant une première tentative (voir note ci-dessous) — aucune étape de la première tentative n'a été considérée comme acquise.

## Tests automatisés ajoutés

- **`tests/integration/test_new_project_dialog.py`** (31 tests) : état initial, parent seul, nom seul, combinaison valide, tous les cas de validation du nom (vide, espaces, `.`/`..`, caractères interdits, séparateurs, noms réservés avec/sans extension, espace/point final, noms proches valides, espaces internes), dossier parent inexistant/supprimé après sélection, parent pointant vers un fichier, Browse annulé (avec et sans parent déjà sélectionné), collision dossier et collision fichier, cible redevenant valide après changement de nom ou après suppression externe + nouvelle interaction, construction exacte du chemin, Cancel, fermeture via X, Accept, preuve qu'aucune création disque n'a lieu, collision de dernière seconde (apparue après la dernière revalidation mais avant le clic), idempotence d'un double appel à l'acceptation.
- **`tests/integration/test_main_window_new_project.py`** (4 tests) : annulation = aucun `create()` appelé, acceptation = `create()` appelé exactement une fois avec le `target_path` du dialogue, `WorkspaceManagerError` toujours affichée via `QMessageBox.critical`, `open_project()`/`save_project()` non affectés par le nouveau câblage.

Premier fichier de test touchant `MainWindow` directement — délibérément scopé au seul câblage de `new_project()`, sans constituer une suite de test `MainWindow` générale.

## Résultat des tests

- **Tests spécifiques Mission 016** : **35/35 verts**.
- **Suite complète du projet** : **225/225 verts** (190 hérités + 35 nouveaux), aucune régression détectée.

## Smoke test manuel réel

Repris intégralement depuis zéro (aucune étape de la tentative précédente considérée comme acquise), dans la vraie application (`src/core/main.py`), dossier parent de test dédié hors dépôt (`C:\Mission016-SmokeTest`, supprimé après le test).

| # | Contrôle | Résultat |
|---|---|---|
| 1 | Lancement de l'application, interface utilisable | PASS |
| 2 | Ouverture du dialogue "Nouveau projet" | PASS |
| 3 | Création nominale (`Project-A`) — dossier, `project.json`, structure Workspace, ouverture immédiate | PASS |
| 4 | Persistance — fermeture, relance, réouverture via "Ouvrir un projet" | PASS |
| 5 | Nom invalide (`Project:Invalid`) — création refusée, aucun crash | PASS |
| 6 | Nom vide / espaces uniquement — création refusée | PASS |
| 7 | Collision avec un dossier existant — refusée, aucun écrasement | PASS |
| 8 | Annulation — aucun effet de bord | PASS |
| 9 | Dossier parent inexistant/invalide | **NOT APPLICABLE** |
| 10 | Régression "Ouvrir un projet" | PASS |
| 11 | Régression "Sauvegarder" | PASS |
| 12 | Fermeture finale — aucun traceback, aucun processus résiduel | PASS |

**Point NOT APPLICABLE (contrôle 9)** : le sélecteur système (`QFileDialog.getExistingDirectory()`) utilisé pour choisir le dossier parent ne permet de sélectionner qu'un dossier **réellement existant** — il est structurellement impossible de produire un "dossier parent inexistant" via l'interface normale, sans contourner l'UI. Ce cas n'a donc pas pu être testé manuellement ; il n'existe pas de chemin de code réel qui l'exposerait.

Synthèse : 11 contrôles PASS, 1 NOT APPLICABLE (justifié structurellement), 0 FAIL. Aucune divergence entre le comportement automatisé (tests) et le comportement réel observé.

## Critères d'acceptation — état final

- `NewProjectDialog` créé, ne crée jamais rien lui-même sur le disque, uniquement `target_path` construit et validé : ✅.
- Choix du dossier parent, saisie du nom, aperçu du chemin final exact : ✅.
- Validation du nom (vide, espaces, caractères interdits, séparateurs, noms réservés Windows, espace/point final) sans excès sur les noms proches valides : ✅.
- Collision refusée, y compris revérifiée à l'instant exact de l'Accept (course filesystem) : ✅.
- Annulation et fermeture par X sans aucun effet de bord : ✅.
- Création physique exclusivement via `WorkspaceManager.create()` → `WorkspaceStorage.create_directories()`, inchangés : ✅.
- `open_project()`/`save_project()` non affectés : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ (225/225).
- Smoke test manuel réel complet, repris depuis zéro : ✅ (11 PASS, 1 NOT APPLICABLE justifié, 0 FAIL).
- Documentation de fin de mission complète : ✅ (ce document + `docs/PROJECT_CONTEXT.md` + `CHANGELOG.md`).

## Dettes hors périmètre (volontairement non traitées par Mission 016)

- Galerie/miniatures `ImagesPage` (identifié en Mission 013/014/015, toujours non implémenté).
- Images de référence pour `InferencePage` (identifié, toujours non implémenté).
- Sélection multi-engine/backend (identifié, toujours non implémenté).
- Projets récents, templates de projet, renommage/suppression de projet — non demandés, non implémentés.
- Toutes les dettes déjà connues avant Mission 016 (ambiguïté `Training`/`Training History`, `BasePage` mort, incohérences Blueprint `Job`, support Linux/macOS non vérifié, limite shutdown sans annulation réelle) — inchangées.

## Commit correspondant

Commit : `566babf727c38b8a0875a4f0cf7fd16d1b29b912`. Message : `feat: add direct project folder creation`.

## Tag / release correspondant

Tag annoté `v0.2-mission016`, message `Mission 016 - Direct Project Folder Creation`, ciblant exactement `566babf727c38b8a0875a4f0cf7fd16d1b29b912`. GitHub Release `v0.2-mission016` publiée — confirmé directement par l'architecte du projet.

## État final

Mission terminée. `NewProjectDialog` permet désormais de créer un nouveau projet directement depuis AI Studio Toolkit — choix d'un dossier parent existant, saisie et validation du nom, création automatique du dossier et de la structure Workspace standard, ouverture immédiate — sans jamais devoir créer le dossier au préalable dans l'Explorateur Windows. Aucune modification de `WorkspaceManager`/`WorkspaceStorage`/`EventBus`, qui géraient déjà cette capacité. Validée par 225 tests automatisés (35 nouveaux) et par un smoke test manuel réel complet (11 PASS, 1 NOT APPLICABLE structurellement justifié, 0 FAIL), repris intégralement depuis zéro après un incident d'affichage/connexion diagnostiqué comme externe à AI Studio Toolkit et n'ayant entraîné aucune correction applicative.
