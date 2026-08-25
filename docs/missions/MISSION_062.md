# Mission 062 — Confirm Destructive Entity Deletion

> **STATUT : MISSION ENTIÈREMENT CLOSE.** 16 tests ciblés nets nouveaux (Cancel/Confirm par entité, plus la garde Dataset↔Training), 1041/1041 tests automatisés verts, smoke test Qt réel exécuté et **PASS** sur les 5 pages concernées (section 9). Commit fonctionnel `a630b4f6884b6bf204fdeb42cb7a94f39a639a4b`, tag annoté `v0.2-mission062`, GitHub Release publiée. Voir section 11 pour l'état de clôture Git et publication.

## 1. Contexte

L'audit consécutif à Mission 061 a identifié que 6 des 7 entités du projet (`Character`, `Dataset`, `LoRA`, `Model`, `Training`, `Workflow`) exposaient une méthode `delete_<entité>()` de Page appelant directement le Manager sans aucune confirmation utilisateur — un simple clic sur « Supprimer » suffisait à effacer irréversiblement l'enregistrement, contrairement à `ImagesPage.delete_selected_images()` (Mission 046) et, dans une moindre mesure, `PromptsPage.delete_prompt()` (Mission 038), qui confirment déjà avant de supprimer.

**Réexamen demandé par l'architecte avant validation** : un second mini-audit a établi que `CharactersPage.delete_button` est **volontairement caché** (`setVisible(False)`, Mission 026, verrouillé par un test de régression dédié — `test_character_roundtrip.py` vérifie `isHidden()`) — `CharactersPage.delete_character()` n'est donc accessible par **aucun** utilisateur réel, uniquement câblé pour compatibilité interne. `CharacterManager.delete()` reste légitime et nécessaire (appelé directement par onze tests dans `test_character_roundtrip.py`, et par un test dans chacune des suites `test_dataset_roundtrip.py`/`test_lora_roundtrip.py`/`test_model_roundtrip.py`/`test_prompt_roundtrip.py`/`test_training_roundtrip.py`/`test_workflow_roundtrip.py`, qui valident le comportement de réinitialisation `active_*_id`/cascade du pattern Character-owned). **Character est donc explicitement hors périmètre de cette mission** — ajouter une confirmation sur un chemin UI inaccessible n'aurait protégé personne.

Pour les 5 entités restantes, le second mini-audit a confirmé que chaque bouton « Supprimer » est réellement visible et câblé (aucun `setVisible(False)`), qu'aucune des 5 suppressions ne cascade vers d'autres entités ni ne supprime de fichier physique (métadonnées uniquement dans `project.json`), et qu'aucune n'était couverte par un test au niveau Page.

## 2. Objectif

Ajouter une confirmation explicite (`QMessageBox`, motif déjà établi par `ImagesPage`/`PromptsPage`) avant toute suppression de `Dataset`, `LoRA`, `Model`, `Training` ou `Workflow`, avec Annuler comme action sûre par défaut, sans modifier aucune autre règle métier existante.

## 3. Contrat fonctionnel implémenté

Pour chacun des 5 fichiers, le corps de `delete_<entité>()` a été étendu (aucun autre appel modifié) :

```python
box = QMessageBox(self)
box.setWindowTitle("Supprimer <l'entité> ?")
box.setText(f"Supprimer <l'entité> « {item.text()} » ? Cette action est irréversible.")
delete_button = box.addButton("Supprimer", QMessageBox.AcceptRole)
cancel_button = box.addButton("Annuler", QMessageBox.RejectRole)
box.setDefaultButton(cancel_button)
box.exec()

if box.clickedButton() is not delete_button:
    return

self.<entité>_manager.delete(...)
```

- Le texte affiché reprend `item.text()` (le libellé déjà visible dans la liste), identifiant sans ambiguïté l'élément concerné.
- Les textes sont factuellement exacts : aucune des 5 entités ne supprime de fichier physique — le texte Dataset précise explicitement que les images qu'il référence restent dans la galerie Images, pour éviter toute confusion.
- **Cas Dataset** : la garde préexistante `is_referenced_by_training()` reste la **première** vérification, avant toute construction de `QMessageBox` — un Dataset dont la suppression est refusée par cette garde n'affiche jamais de confirmation trompeuse ; seul le `QMessageBox.warning()` déjà existant s'affiche, et la méthode retourne immédiatement.
- `Annuler` (y compris la fermeture du dialogue via la croix ou Échap, qui laisse `clickedButton()` à `None`) : aucun appel au Manager, aucune mutation, aucune sauvegarde.
- `Supprimer` : exécute exactement l'appel au Manager déjà existant, sans changement de comportement.
- Aucune abstraction/helper partagé introduit — 5 adaptations locales indépendantes, comme demandé.

**Fichiers modifiés** :
- `src/ui/pages/datasets_page.py` — `delete_dataset()`
- `src/ui/pages/lora_page.py` — `delete_lora()`
- `src/ui/pages/models_page.py` — `delete_model()`
- `src/ui/pages/training_page.py` — `delete_training()`
- `src/ui/pages/workflows_page.py` — `delete_workflow()`

**Domain/Manager/Infrastructure/EventBus** : aucun changement — strictement Presentation.

## 4. Hors périmètre (explicitement différé)

- `Character` — voir section 1 ; `CharactersPage.delete_button` reste caché, `delete_character()`/`CharacterManager.delete()` non modifiés.
- A-2 (cache des vignettes / redécodages complets inutiles, candidat identifié pendant l'audit de Mission 062) — reste un candidat futur, non implémenté ici.
- Toute autre règle métier des 5 Managers concernés (garde Dataset↔Training, réinitialisation `active_*_id`, publication des événements `*_DELETED`) — strictement inchangée.

## 5. Risques

- **Risque de régression fonctionnelle** : très faible — motif déjà validé deux fois dans le dépôt (`ImagesPage`, `PromptsPage`), 5 adaptations mécaniques, aucun changement de signature Manager.
- **Risque d'UX trompeuse pour Dataset** : explicitement neutralisé — l'ordre des vérifications place la garde Training avant toute confirmation (voir section 3), vérifié par un test dédié et par le smoke test réel.
- **Risque de test fragile** : mockage de `QMessageBox` au niveau classe (`patch("src.ui.pages.<module>.QMessageBox")`), technique déjà éprouvée par `test_images_page.py` — aucune dépendance à la résolution d'écran ou à un événement Qt réel.

## 6. Pourquoi maintenant

Débattu et validé lors de deux audits successifs (voir historique de la conversation) : c'est le candidat autonome restant le plus mûr — périmètre borné, motif déjà établi, zéro décision architecturale ouverte, contrairement à la quasi-totalité des autres besoins enregistrés dans `docs/PROJECT_CONTEXT.md`.

## 7. Autres candidats évalués et écartés pour cette mission

- **A-2 — cache des vignettes / suppression des redécodages complets inutiles** (`src/ui/thumbnails.py::load_thumbnail_icon()`, consommé par `ImagesPage`/`DatasetsPage`/`SelectImagesDialog`) : dette réelle et démontrée (aucun cache, redécodage complet de chaque fichier à chaque tri/sauvegarde/changement de contexte), mais nécessite un micro-choix d'implémentation (borne du cache) — retenu comme candidat futur, explicitement non implémenté ici sur instruction de l'architecte.
- **Character** — voir section 1 : chemin UI inaccessible, ajouter une confirmation n'aurait protégé personne ; explicitement exclu du périmètre.

## 8. Tests automatisés ajoutés

Pour chacune des 5 entités, une nouvelle classe `*PageDeleteConfirmationTest` (mêmes fichiers `test_<entité>_roundtrip.py` que les classes `*PageRenameTest`/`*PageSortTest` déjà existantes) :

- `test_delete_with_no_selection_is_a_no_op` — aucune sélection → `QMessageBox` jamais construit (`mock_cls.assert_not_called()`).
- `test_delete_confirmed_removes_<entité>` — Confirm → Manager appelé, entité effectivement supprimée.
- `test_delete_cancelled_calls_neither_manager_nor_mutates_state` — Cancel → `Manager.delete` jamais appelé (`patch.object(..., "delete")` + `assert_not_called()`), sélection et compte inchangés.

Pour Dataset spécifiquement, une 4ᵉ méthode :
- `test_delete_blocked_by_training_reference_never_shows_confirmation` — garde Training toujours active, `QMessageBox.warning()` appelé, **`QMessageBox().exec()` jamais appelé** (`mock_cls.return_value.exec.assert_not_called()`), dataset toujours présent.

**16 tests nets nouveaux** au total (3 × 4 entités sans garde + 4 pour Dataset). Aucun test préexistant modifié ou supprimé — tous les tests `*RenameTest`/`*SortTest`/roundtrip restent inchangés et verts.

## 9. Vérifications finales — réellement exécutées

**Tests ciblés** — **16/16 PASS** (les 5 nouvelles classes de test, exécutées ensemble).

**Suite complète** : **1041/1041 tests automatisés verts** (1025 précédents + 16 nets nouveaux).

`git diff --check` : propre (seuls des avertissements de fin de ligne LF/CRLF liés à la configuration Git de l'environnement, aucune erreur réelle).

**Périmètre du diff** : exactement 10 fichiers — `src/ui/pages/{datasets,lora,models,training,workflows}_page.py` (production) et `tests/integration/test_{dataset,lora,model,training,workflow}_roundtrip.py` (tests), plus ce document. Aucun fichier Domain/Manager/Infrastructure/EventBus touché. Aucun résidu scratch dans le dépôt.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

Construction réelle des 5 Pages contre un Workspace réel (dossiers temporaires), clic réel sur le bouton « Supprimer », `QMessageBox` réel construit (non mocké) — seul `QMessageBox.exec()` est patché pour cliquer programmatiquement sur le vrai bouton voulu plutôt que de bloquer sur une boucle modale réelle, exactement comme `ImagePreviewDialog`/`PromptAssistantDialog` avaient été smoke-testés via `show()`/`processEvents()` plutôt que `exec()` bloquant.

Pour chacune des 5 entités (Dataset, LoRA, Model, Training, Workflow) :
- Dialogue construit avec le bon titre, le bon texte (nom réel de l'entité inclus), les deux boutons `["Annuler", "Supprimer"]`, **`defaultButton()` confirmé être « Annuler »**.
- **Annuler** → l'entité reste présente (`count == 1`), la sélection active reste inchangée.
- **Supprimer** → l'entité est effectivement supprimée (`count == 0`).

Cas Dataset référencé par un Training : `QMessageBox.exec()` **jamais appelé** (0 appel mesuré) — seule la garde `warning()` préexistante s'est déclenchée, le dataset reste présent. Confirme que l'ordre garde→confirmation est respecté en conditions réelles.

**Verdict : PASS sur les 5 pages.**

## 11. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `a630b4f6884b6bf204fdeb42cb7a94f39a639a4b` — « feat: confirm before deleting Dataset, LoRA, Model, Training and Workflow » (11 fichiers, 652 insertions : 5 fichiers de production, 5 fichiers de test, ce document).
- **Push** : `1309bed..a630b4f main -> main`, `HEAD == origin/main`, divergence `0 0`, arbre de travail propre.
- **Tag annoté** : `v0.2-mission062` (message « Mission 062 - Confirm Destructive Entity Deletion »), pointant sur `a630b4f6884b6bf204fdeb42cb7a94f39a639a4b` — vérifié identique en local (`git rev-list -n1`) et à distance (`git ls-remote --tags origin`, commit peelé `^{}` correspondant exactement).
- **GitHub Release** `v0.2-mission062` — **publiée** par l'architecte, Release Notes en anglais.

## État d'avancement

- Audit du dépôt (candidats Mission 062, deux passes successives) : **réalisé**.
- Choix de mission (A-1 corrigé, 5 entités, Character exclu) : **validé par l'architecte**.
- Implémentation : **réalisée, conforme au contrat**.
- Tests automatisés : **exécutés, verts — 1041/1041** (16 nets nouveaux).
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (10 fichiers exactement)**.
- Smoke test Qt réel : **réalisé, PASS sur les 5 pages** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (section 11).
