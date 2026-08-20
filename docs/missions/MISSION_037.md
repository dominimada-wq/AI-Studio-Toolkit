# Mission 037 — Distinguish no open project from no dataset in TrainingPage

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 680/680 tests automatisés verts, smoke test manuel réel PASS, clôture Git effectuée, GitHub Release `v0.2-mission037` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

L'audit et le smoke test manuel réel de Mission 036 ont confirmé et volontairement laissé ouverte une ambiguïté distincte des 7 emplacements corrigés par cette mission : `TrainingPage.create_training()` pouvait afficher « Aucun dataset disponible » avant même d'atteindre la branche « Aucun personnage » lorsqu'aucun Workspace n'était ouvert — enregistrée comme besoin futur dans `docs/PROJECT_CONTEXT.md`, sans décision architecturale de correction (voir `docs/missions/MISSION_036.md`, section 12).

## 2. Objectif

Corriger cette ambiguïté restante : lorsqu'aucun Workspace n'est ouvert, l'utilisateur doit recevoir « Aucun projet ouvert » plutôt que « Aucun dataset disponible », sans modifier le comportement des deux autres états (Workspace ouvert sans Dataset ; Workspace ouvert avec Dataset).

## 3. Audit ciblé — constats vérifiés par lecture directe du code

- `TrainingPage.create_training()` ([training_page.py:57](src/ui/pages/training_page.py:57), avant correction) appelait `dataset_manager.list_datasets()` en tout premier, avant toute consultation de `workspace_manager.opened` — pourtant déjà injecté dans `TrainingPage` depuis Mission 036.
- `DatasetManager.datasets` ([dataset_manager.py:69](src/managers/dataset_manager.py:69)) retourne `[]` aussi bien lorsqu'aucun Workspace n'est ouvert que lorsqu'un Workspace existe sans personnage principal — même cause racine que l'ambiguïté déjà résolue par Mission 036 aux 7 autres emplacements, mais interceptée ici une étape plus tôt, avant même que `training_manager.create()` (et le bloc défensif Mission 036 qui en dépend) ne soit atteint.
- Le bloc introduit par Mission 036 après `training_manager.create()` ([training_page.py:107-121](src/ui/pages/training_page.py:107)) était déjà correct pour son propre cas (« Aucun personnage » vs « Aucun projet ouvert », selon `workspace_manager.opened`), mais n'intervenait jamais à temps pour empêcher le message « Aucun dataset disponible » de s'afficher en premier.

## 4. Décision technique

Ajout d'une seule garde `workspace_manager.opened` en tête de `create_training()`, avant tout appel à `dataset_manager.list_datasets()`. `WorkspaceManager.opened` reste la seule source d'autorité, cohérente avec Mission 036. Aucune nouvelle dépendance : `TrainingPage` possédait déjà `workspace_manager` en constructeur depuis Mission 036, donc aucun changement de constructeur, aucun site d'instanciation (production ou test) à modifier au-delà du fichier de test dédié. Le bloc défensif Mission 036 après `training_manager.create()` reste strictement inchangé — hors périmètre de cette mission.

## 5. Périmètre IN

- Ajout d'une garde `workspace_manager.opened` en tête de `TrainingPage.create_training()`, avec retour immédiat et message « Aucun projet ouvert » / « Ouvrez ou créez un projet avant de créer une session d'entraînement. » (texte identique à celui déjà utilisé par le bloc Mission 036).
- Renforcement d'un test existant, ajout de deux tests nets nouveaux dans `tests/integration/test_training_roundtrip.py`.

## 6. Périmètre OUT (strict, explicitement différé)

Les 7 messages déjà corrigés par Mission 036 ; tout autre message contextuel non identifié ; dirty-state de `PromptsPage` ; Prompt Assistant ; Prompt Library ; tags ; RAG ; vision/multimodal ; Character Context avancé ; Settings ; i18n ; refonte de `TrainingPage`, des Managers ou de la gestion des erreurs ; toute modification de `WorkspaceManager`, `DatasetManager` ou `TrainingManager`.

## 7. Fichiers concernés

Production (1) : `src/ui/main_window.py` **non concerné** (aucun changement de constructeur) ; `src/ui/pages/training_page.py`.
Tests (1) : `tests/integration/test_training_roundtrip.py`.

Aucun autre fichier — `DatasetManager`, `TrainingManager`, `WorkspaceManager`, `src/domain/`, `src/core/event_bus.py` strictement inchangés.

## 8. Fonctionnalités livrées (implémentation réelle)

`TrainingPage.create_training()` vérifie désormais `self.workspace_manager.opened` en tout premier :
- **Aucun Workspace ouvert** : avertissement « Aucun projet ouvert » / « Ouvrez ou créez un projet avant de créer une session d'entraînement. », retour immédiat — aucun appel à `dataset_manager.list_datasets()`, aucun dialogue de sélection de Dataset, aucun dialogue de saisie du nom.
- **Workspace ouvert sans Dataset** : comportement existant strictement inchangé — « Aucun dataset disponible » / « Créez un dataset avant de créer une session d'entraînement. ».
- **Workspace ouvert avec Dataset disponible** : flux normal strictement inchangé (sélection dataset, saisie du nom, `training_manager.create()`).

Le bloc défensif introduit par Mission 036 après `training_manager.create()` reste inchangé — sa branche « Aucun projet ouvert » devient en pratique inatteignable après la nouvelle garde, mais n'a pas été retirée (hors périmètre).

## 9. Tests ajoutés/modifiés (2 nets nouveaux)

- `test_create_training_without_open_workspace_shows_no_project_warning` (renforcé, `TrainingCreationWithoutManualCharacterSelectionTest`) : ajout de `dataset_manager.list_datasets.assert_not_called()` et de l'absence d'appel aux deux `QInputDialog`, prouvant que la nouvelle garde intercepte le cas avant toute autre opération.
- `test_create_training_with_open_workspace_and_no_dataset_shows_dataset_warning` (nouveau) : Workspace réel ouvert, `DatasetManager` réel non mocké, zéro Dataset → message « Aucun dataset disponible » inchangé, aucune Training créée.
- `test_create_training_with_open_workspace_and_dataset_succeeds` (nouveau) : Workspace + Dataset réels, flux nominal via `QInputDialog` contrôlé → aucun avertissement, Training effectivement créée.
- `test_create_training_with_open_workspace_and_no_character_shows_personnage_warning` (bloc Mission 036) : inchangé, toujours vert.

## 10. Résultats de tests (automatisés)

- Suite ciblée (`test_training_roundtrip.py`) : **16/16 OK**.
- Suite complète (`python -m unittest discover -s tests -p "test_*.py"`) : **680/680 OK** (678 précédents + 2 nets nouveaux), une seule exécution après implémentation.

## 11. Smoke test manuel réel — résultat

**Résultat global : PASS.** Confirmé par l'architecte du projet — aucune anomalie relevée.

## Commit correspondant

`27ce1d1d3f3679722c3d78ba529d2d55b4843bd0` — `feat: distinguish no open project from no dataset in TrainingPage`. Inclut l'implémentation fonctionnelle (code + tests) de Mission 037.

## Tag / release correspondant

`v0.2-mission037` (annoté, message `Mission 037 - Distinguish no open project from no dataset in TrainingPage`), ciblant exactement `27ce1d1d3f3679722c3d78ba529d2d55b4843bd0`. GitHub Release `v0.2-mission037` **publiée**.

## État d'avancement

- Audit et spécification : **validés**.
- Implémentation : **réalisée**, conforme à la spécification validée.
- Tests automatisés ciblés (16/16) et suite complète (680/680) : **exécutés, verts**.
- Smoke test manuel réel : **PASS**.
- Clôture Git : **effectuée** — commit fonctionnel `27ce1d1d3f3679722c3d78ba529d2d55b4843bd0`, tag `v0.2-mission037`.
- GitHub Release : **publiée**.

## État final

Mission 037 — Distinguish no open project from no dataset in TrainingPage — est **entièrement close** : implémentation, 680/680 tests automatisés, smoke test manuel réel PASS, clôture Git et publication GitHub Release toutes effectuées. La dette distincte enregistrée pendant Mission 036 (`TrainingPage → « Aucun dataset disponible »` lorsqu'aucun Workspace n'est ouvert) est résolue.
