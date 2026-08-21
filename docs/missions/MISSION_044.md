# Mission 044 — Feed a Dataset from the Images Gallery

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation terminée, 7/7 tests ciblés `test_select_images_dialog.py`, 20/20 `test_datasets_page.py`, 27/27 `test_dataset_roundtrip.py`, 23/23 `test_images_page.py` (non-régression), 749/749 tests automatisés verts, smoke test manuel réel du rendu Qt PASS, clôture Git effectuée, GitHub Release `v0.2-mission044` publiée.
> Voir "Commit correspondant"/"Tag / release correspondant" et la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Besoin enregistré comme dette UX ouverte depuis Mission 028 (voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés" — « Alimentation d'un Dataset depuis la galerie Images ») : le seul moyen d'ajouter des images à un Dataset est aujourd'hui de repasser par le sélecteur de fichiers Windows (`QFileDialog`), même lorsque l'image souhaitée est déjà présente dans la galerie `Images` du Workspace.

Un mini-audit ciblé en lecture seule a inspecté précisément `ImagesPage`, `DatasetsPage`, `DatasetManager`, `WorkspaceManager`/`WorkspaceStorage`, le Domain `Image`/`Dataset`, l'EventBus pertinent, les tests existants, ainsi que le mécanisme réel de `WorkspaceStorage.copy_into_workspace()`/`is_inside()`. Trois constats structurants en résultent :

1. **Aucune copie physique n'est nécessaire.** `WorkspaceStorage.copy_into_workspace()` (Mission 028) reconnaît déjà toute source résolvant à un emplacement sous `workspace_root` et la retourne telle quelle, sans I/O — c'est le mécanisme qui évite déjà la duplication du flux Accept (Inference → `outputs/`). Une image de `Workspace.images` ajoutée à un Dataset via `DatasetManager.add_images([file_path])` ne sera donc **jamais recopiée** : le nouvel `Image` du Dataset pointera vers exactement le même fichier physique.
2. **La déduplication existe déjà, entièrement déterministe.** `DatasetManager.add_images()` calcule déjà l'ensemble des chemins internes déjà présents dans le Dataset actif et classe tout doublon en `skipped`, jamais dupliqué — aucune nouvelle logique n'est nécessaire pour ce point.
3. **Aucun wiring EventBus supplémentaire n'est nécessaire.** `add_images()` réussi appelle déjà `WorkspaceManager.save()`, qui publie `WORKSPACE_SAVED` — événement auquel `DatasetsPage.update_datasets()` est déjà abonné (`main_window.py`). Exactement le même mécanisme vérifié pour Mission 043.

Une quatrième conclusion, plus architecturale, détermine le périmètre retenu : **l'action « Ajouter depuis Images » est placée dans `DatasetsPage`, pas dans `ImagesPage`.** `DatasetsPage` possède déjà à la fois `dataset_manager` et `workspace_manager` (donc un accès direct à `workspace_manager.current_workspace.images`) — aucune nouvelle dépendance de constructeur n'est nécessaire. L'alternative (un bouton dans `ImagesPage`) aurait exigé d'injecter `dataset_manager` dans `ImagesPage.__init__`, un constructeur actuellement instancié dans **11 fichiers de test** dont 6 n'ont aujourd'hui aucune raison de construire un `DatasetManager` (`test_lora_roundtrip.py`, `test_model_roundtrip.py`, `test_prompt_roundtrip.py`, `test_settings_roundtrip.py`, `test_workflow_roundtrip.py`, `test_inference_page.py`) — un élargissement mécanique disproportionné pour une fonctionnalité qui n'a besoin d'aucune de ces dépendances côté `ImagesPage`. Héberger l'action côté `DatasetsPage` élimine également toute question de « Dataset cible » : la cible est simplement le Dataset déjà actif dans la Page où l'action est déclenchée, réutilisant le garde-fou déjà existant (« Aucun dataset sélectionné »).

## 2. Problème

Un utilisateur souhaitant alimenter un Dataset avec une image déjà présente dans le Workspace doit aujourd'hui la réimporter depuis le disque via `QFileDialog`, alors qu'elle est déjà visible dans `ImagesPage`.

## 3. Objectif

Permettre d'ajouter au Dataset actuellement actif une ou plusieurs images déjà présentes dans la galerie `Images` du Workspace, sans passer par le sélecteur de fichiers Windows et sans jamais dupliquer physiquement le fichier sur disque.

## 4. Contrat fonctionnel validé

**Emplacement** : nouveau bouton « Ajouter depuis Images… » dans `DatasetsPage`, à côté du bouton « Importer des images » existant.

**Dataset cible** : toujours le Dataset actuellement actif (`dataset_manager.active_dataset_id`) — pas de sélecteur de Dataset. Sans Dataset actif, réutilisation à l'identique du garde-fou déjà existant (« Aucun dataset sélectionné » / « Sélectionnez un dataset avant d'importer des images. »).

**Disponibilité de l'action — décision confirmée en implémentation** : `DatasetsPage` ne désactive aujourd'hui aucun bouton selon l'état du Dataset actif (`new_button`/`delete_button`/`import_images_button` restent toujours cliquables ; c'est la méthode appelée qui vérifie l'état et affiche un avertissement le cas échéant). Introduire un `setEnabled()` piloté par `active_dataset_id` pour ce seul nouveau bouton aurait créé une seconde source de vérité pour un état déjà géré autrement dans cette Page. Le bouton « Ajouter depuis Images… » suit donc exactement le même mécanisme que « Importer des images » : toujours cliquable, garde-fou réutilisé à l'identique à l'intérieur du gestionnaire.

**Sélection** : multi-sélection, dans un nouveau dialogue dédié (`SelectImagesDialog`, `src/ui/dialogs/`) listant `workspace_manager.current_workspace.images` en galerie de miniatures (`QListWidget.IconMode`, réutilisant `load_thumbnail_icon()`), sélection étendue (`QListWidget.ExtendedSelection`). Aucune modification de `ImagesPage` — sa propre galerie reste en sélection simple, inchangée.

**Galerie Images vide** : message informatif (« Aucune image dans la galerie Images. »), le dialogue n'est pas ouvert.

**Ajout** : `dataset_manager.add_images([chemins sélectionnés])`, appelé tel quel — aucune nouvelle méthode Manager. Résultat affiché via `_show_import_result()` déjà existant dans `DatasetsPage` (même message qu'un import classique).

**Doublons** : délégués entièrement à `add_images()` existant — une image déjà présente dans le Dataset actif est comptée `skipped`, jamais dupliquée ; une sélection mixte (images nouvelles + déjà présentes) ajoute les nouvelles et ignore silencieusement les autres, exactement comme un import classique avec doublons.

**Absence de copie physique** : confirmée par le mécanisme déjà existant de `WorkspaceStorage.copy_into_workspace()` — le nouvel `Image` du Dataset partage le même `file_path` que l'`Image` de la galerie Workspace, jamais un nouveau fichier sous `datasets/<dataset_id>/`.

**Rafraîchissement** : aucun wiring EventBus nouveau — chemin déjà existant et suffisant, voir section 7.

**Suppression future (constatée, non traitée)** : `ImagesPage` ne propose aujourd'hui aucune suppression d'image (confirmé par lecture directe, aucune méthode de ce type n'existe) — le scénario « image supprimée de la galerie Images alors que référencée par un Dataset » n'est donc pas atteignable aujourd'hui. Documenté pour mémoire uniquement : le jour où une suppression sera introduite dans `ImagesPage`, la galerie `DatasetsPage` tolère déjà un fichier manquant sans crash (icône de repli native, Mission 042) — aucun risque de plantage, seulement une miniature de repli.

## 5. Périmètre

Production (2) :
- `src/ui/dialogs/select_images_dialog.py` (nouveau)
- `src/ui/pages/datasets_page.py` (nouveau bouton + méthode)

Tests (3) :
- `tests/integration/test_select_images_dialog.py` (nouveau)
- `tests/integration/test_datasets_page.py` (extension)
- `tests/integration/test_dataset_roundtrip.py` (extension, cycle complet + non-duplication physique)

## 6. Hors périmètre

- Toute modification d'`ImagesPage` (bouton, sélection, constructeur).
- Toute modification Domain (`Image`, `Dataset`, `Workspace`).
- Toute nouvelle méthode `DatasetManager`/`WorkspaceManager` — `add_images()` existant est suffisant.
- Toute suppression d'image dans `ImagesPage` ou `DatasetsPage`.
- Tri de la galerie Images.
- Portabilité des chemins.
- Refonte EventBus.
- Sélection multi-engine, Prompt Library/RAG, ou toute autre dette indépendante.

## 7. Wiring de rafraîchissement — aucun ajout

Chemin déjà existant et suffisant, vérifié par le mini-audit :

```
DatasetsPage.add_images_from_gallery()
  → DatasetManager.add_images(paths)
  → WorkspaceManager.save()
  → événement WORKSPACE_SAVED
  → DatasetsPage.update_datasets() (déjà abonné depuis MainWindow)
```

Aucune souscription EventBus nouvelle. `DatasetsPage` ne reçoit aucune nouvelle dépendance de constructeur — `dataset_manager`/`workspace_manager` sont déjà ses deux dépendances actuelles.

## 8. Stratégie d'implémentation — réellement mise en œuvre

- `src/ui/dialogs/select_images_dialog.py` (nouveau) : `SelectImagesDialog(QDialog)`, reçoit une liste de chemins (`list[str]`, déjà résolus par l'appelant) et un `parent`. Galerie `QListWidget.IconMode`/`ExtendedSelection`, miniatures via `load_thumbnail_icon()` (Mission 042, réutilisé tel quel), boutons OK/Annuler (`QDialogButtonBox`). Accesseur `selected_paths()` après `exec()`, motif identique à `ImportCollisionDialog.decisions()`/`NewProjectDialog.target_path`. Ne réalise lui-même aucune mutation de Dataset ni copie de fichier.
- `DatasetsPage` : nouveau bouton `self.add_from_gallery_button` (« Ajouter depuis Images… »), placé dans une `QHBoxLayout` avec `import_images_button` existant. Nouvelle méthode `add_images_from_gallery()` — garde « aucun dataset actif » réutilisée à l'identique (même message que `import_images()`), lecture de `workspace_manager.current_workspace.images`, garde « galerie vide » (message informatif), ouverture de `SelectImagesDialog`, puis `dataset_manager.add_images(dialog.selected_paths())` et `_show_import_result()` déjà existant — aucune nouvelle logique de déduplication ou de copie en Presentation.
- Aucun changement de `ImagesPage`, `DatasetManager`, `WorkspaceManager`, `WorkspaceStorage`, Domain, EventBus — confirmé par inspection du diff complet.

## 9. Stratégie de tests — réellement mise en œuvre

- `test_select_images_dialog.py` (nouveau, 7 tests) : mode galerie, sélection multiple activée, icône/texte/tooltip/`Qt.UserRole` par image, aucune sélection → liste vide, sélection d'une puis de plusieurs images → chemins exacts retournés, liste de chemins vide → galerie vide.
- `test_datasets_page.py` (extension, 8 tests nets nouveaux) : garde « aucun dataset actif » (nouvelle instance sans Dataset, message réutilisé, dialogue jamais construit), garde « galerie Images vide » (message informatif, dialogue jamais construit), dialogue peuplé exactement des images réelles du Workspace, annulation du dialogue → rien ajouté, ajout d'une image unique sans nouveau fichier sur disque, ajout de plusieurs images en une seule opération, doublon (image déjà dans le dataset actif) correctement ignoré sans duplication, rafraîchissement de `images_list` vérifié via le seul mécanisme `WORKSPACE_SAVED` existant (aucun appel manuel à `update_datasets()`).
- `test_dataset_roundtrip.py` (extension, 1 test net nouveau) : cycle complet réel — image importée dans la galerie Images, ajoutée au Dataset actif via `add_images_from_gallery()`, sauvegarde, fermeture, réouverture avec instances fraîches — persistance confirmée et **absence de copie physique** vérifiée explicitement (le dossier `datasets/<dataset_id>/` n'est jamais créé, le `file_path` du Dataset reste identique à celui de la galerie Workspace).
- `test_images_page.py` : exécuté intégralement, **aucune modification** — 23/23 OK, confirmant qu'`ImagesPage` n'a subi aucune régression (fichier non touché).

Aucune comparaison pixel par pixel dans les tests automatisés. Aucune nouvelle vérification approfondie des responsabilités internes de `DatasetManager.add_images()` déjà couvertes par `DatasetManagerAddImagesCopyTest` — les nouveaux tests vérifient l'intégration de la nouvelle voie d'entrée, pas la logique déjà testée du Manager.

## 10. Critères d'acceptation — résultats

- Bouton « Ajouter depuis Images… » présent dans `DatasetsPage`, à côté de « Importer des images » — **conforme**.
- Sans Dataset actif : message « Aucun dataset sélectionné » réutilisé, dialogue non ouvert — **conforme**.
- Galerie Images vide : message informatif, dialogue non ouvert — **conforme**.
- Sélection multiple d'images de la galerie Images → toutes ajoutées au Dataset actif, sans copie physique — **conforme**, vérifié par test et par smoke test réel (aucun fichier sous `datasets/<dataset_id>/`).
- Image déjà présente dans le Dataset actif → ignorée (`skipped`), jamais dupliquée — **conforme**.
- Sélection mixte (nouvelles + déjà présentes) → seules les nouvelles ajoutées — **conforme** (délégué à `add_images()` existant).
- Persistance confirmée après fermeture/réouverture du Workspace, sans nouveau fichier créé sur disque — **conforme**, vérifié par test et par smoke test réel.
- Rafraîchissement de `DatasetsPage.images_list` sans wiring EventBus supplémentaire — **conforme**, confirmé par smoke test réel (aucun appel manuel).
- Aucune modification d'`ImagesPage` — **conforme**, `test_images_page.py` 23/23 OK sans modification.
- Suite `test_select_images_dialog.py` : **7/7 OK**. Suite `test_datasets_page.py` : **20/20 OK** (12 précédents + 8 nets nouveaux). Suite `test_dataset_roundtrip.py` : **27/27 OK** (26 précédents + 1 net nouveau).
- Suite complète du projet : **749/749 OK** (733 précédents + 16 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 11) réalisé, résultat PASS.**

## 11. Smoke test manuel — réalisé, PASS

Réalisé moi-même (rendu de vrais widgets Qt — `DatasetsPage`, `SelectImagesDialog`, `EventBus`, Managers réels — aucune dépendance externe). Sélection et validation du dialogue effectuées par de vrais événements Qt (`QTest.mouseClick`, y compris un clic Ctrl pour la multi-sélection, et un vrai clic sur le bouton OK réel — jamais un appel direct à `accept()`). Script et captures exclusivement dans le scratchpad de session, jamais dans le dépôt.

Points observés réellement, tous conformes :
- Workspace réel, 2 images importées dans la galerie Images, Dataset créé et sélectionné comme actif.
- Clic réel sur « Ajouter depuis Images… » → `SelectImagesDialog` s'ouvre réellement, affiche les 2 images de la galerie Workspace.
- Sélection réelle des 2 images (clic + Ctrl-clic), clic réel sur OK → `selected_paths()` retourne exactement les 2 chemins internes.
- `DatasetsPage.images_list` affiche immédiatement les 2 images, **sans aucun appel manuel à `update_datasets()`** — uniquement via le mécanisme `WORKSPACE_SAVED` déjà existant.
- Aucun dossier `datasets/<dataset_id>/` créé sur le système de fichiers réel, à aucun moment.
- Nouvelle tentative avec les mêmes 2 images → correctement ignorée, toujours 2 items dans la galerie, toujours aucun dossier créé.
- Fermeture puis réouverture réelle du Workspace (instances fraîches) → les 2 images restent présentes dans la galerie Dataset, chemins identiques, toujours aucun dossier `datasets/<dataset_id>/`.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4. Aucune vérification manuelle utilisateur n'a été nécessaire.

## 12. Risques / non-régressions

- **Risque architectural** : nul — aucun changement Domain/Manager, `add_images()` déjà existant et déjà testé pour la réutilisation sans copie et la déduplication. Confirmé par inspection du diff complet.
- **Risque sur `ImagesPage`** : nul — fichier non touché, aucun changement de constructeur, aucune régression sur les 11 sites d'instanciation existants (`main_window.py` + 10 fichiers de test), confirmé par 23/23 `test_images_page.py` sans modification.
- **Risque de rafraîchissement manqué** : écarté par le mini-audit puis confirmé par le smoke test réel — même chemin `WORKSPACE_SAVED` déjà prouvé suffisant pour Mission 043.
- **Risque de duplication physique** : écarté par construction et confirmé par test et smoke test réel — `WorkspaceStorage.copy_into_workspace()` reconnaît déjà toute source interne au Workspace et ne la copie jamais.
- **Risque de seconde source de vérité pour l'état du Dataset actif** : écarté — le nouveau bouton suit le même mécanisme de garde interne (pas de `setEnabled()`) que les boutons `DatasetsPage` existants dépendant du Dataset actif.

## État d'avancement

- Audit de sélection (candidats Mission 044), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 7/7 (`test_select_images_dialog.py`), 20/20 (`test_datasets_page.py`), 27/27 (`test_dataset_roundtrip.py`), 23/23 (`test_images_page.py`, non modifié), 749/749 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **effectuée** — commit fonctionnel `542e0fef67a426f800220a2a5e43f25ecce57e5b`, tag `v0.2-mission044`.
- GitHub Release : **publiée**.

## Fichiers concernés

Production (2) : `src/ui/dialogs/select_images_dialog.py` (nouveau), `src/ui/pages/datasets_page.py`.
Tests (3) : `tests/integration/test_select_images_dialog.py` (nouveau), `tests/integration/test_datasets_page.py`, `tests/integration/test_dataset_roundtrip.py`.

Aucun autre fichier — `ImagesPage`, Domain, Managers, EventBus, persistance strictement inchangés.

## Commit correspondant

`542e0fef67a426f800220a2a5e43f25ecce57e5b` — `feat: add feeding a Dataset from the Images gallery`. Inclut la spécification (`docs/missions/MISSION_044.md`, version pré-implémentation), l'implémentation fonctionnelle et les tests de Mission 044.

## Tag / release correspondant

`v0.2-mission044` (annoté, message `Mission 044 - Feed a Dataset from the Images Gallery`), ciblant exactement `542e0fef67a426f800220a2a5e43f25ecce57e5b`. GitHub Release `v0.2-mission044` **publiée**.

## État final

Mission 044 — Feed a Dataset from the Images Gallery — est **entièrement close** : implémentation, 749/749 tests automatisés (7/7 `test_select_images_dialog.py`, 20/20 `test_datasets_page.py`, 27/27 `test_dataset_roundtrip.py`, 23/23 `test_images_page.py` non modifié), smoke test manuel réel du rendu Qt PASS, clôture Git et publication GitHub Release toutes effectuées. La dette UX documentée depuis Mission 028 (alimentation d'un Dataset depuis la galerie Images) est résolue par un nouveau bouton « Ajouter depuis Images… » dans `DatasetsPage`, un dialogue dédié `SelectImagesDialog` (galerie de miniatures multi-sélectionnable) ciblant le Dataset actif, sans copie physique (réutilisation confirmée du mécanisme `WorkspaceStorage.copy_into_workspace()`) et sans nouvelle logique de déduplication (`DatasetManager.add_images()` réutilisé tel quel). Aucun wiring EventBus supplémentaire, `ImagesPage` strictement inchangée. Aucune nouvelle dette n'a été identifiée en retour par cette mission.
