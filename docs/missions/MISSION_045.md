# Mission 045 — Remove Images from a Dataset

> **STATUT : IMPLÉMENTATION RÉALISÉE, 39/39 TESTS CIBLÉS (10 `test_datasets_page.py` + 8 `DatasetManagerRemoveImagesTest` + 1 cycle complet `test_dataset_roundtrip.py`), 768/768 TESTS AUTOMATISÉS VERTS, SMOKE TEST MANUEL RÉEL DU RENDU QT PASS. CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> Voir "État d'avancement" en fin de document.

## 1. Contexte

Suite du candidat « suppression d'image » identifié à l'issue de Mission 044, dont le périmètre a été volontairement réduit pour séparer deux responsabilités distinctes : cette mission ne traite que le retrait d'une image **d'un Dataset**, jamais sa suppression depuis la galerie principale `ImagesPage`.

Principe fonctionnel validé par l'architecte : une image contenue dans un Dataset est une **référence** vers un fichier potentiellement partagé avec `Workspace.images` et/ou d'autres Datasets (rendu explicitement possible sans copie physique depuis Mission 044 — `WorkspaceStorage.copy_into_workspace()` réutilise une source déjà interne au Workspace telle quelle). Retirer une image d'un Dataset ne doit donc **jamais** : supprimer le fichier physique, retirer l'image de `Workspace.images`, ni modifier un autre Dataset référençant le même fichier.

Un mini-audit ciblé en lecture seule a confirmé : `DatasetManager` ne possède aujourd'hui **aucune primitive de retrait** (`create`/`select`/`is_referenced_by_training`/`delete`/`preview_collisions`/`add_images` sont les seules méthodes de mutation) ; chaque Dataset a son propre pool `Image` totalement indépendant (Mission 011 — deux Datasets référençant la même source possèdent chacun leur propre objet `Image`, avec son propre `image_id`, simplement le même `file_path`) — retirer d'un Dataset ne peut donc, par construction, jamais affecter un autre Dataset ; `add_images()` ne publie aucun événement dédié, seulement `WorkspaceManager.save()` (→ `WORKSPACE_SAVED`, déjà suffisant pour rafraîchir `DatasetsPage.update_datasets()`) ; `delete_dataset()` (suppression d'un Dataset entier, action plus destructive que celle de cette mission) ne montre aujourd'hui **aucune confirmation** avant suppression.

## 2. Problème

Il n'existe aujourd'hui aucun moyen de corriger une erreur d'ajout à un Dataset (import classique ou « Ajouter depuis Images… », Mission 044) autrement qu'en supprimant le Dataset entier.

## 3. Objectif

Permettre de retirer une ou plusieurs images sélectionnées du Dataset actuellement actif, en ne mutant que la référence de ce Dataset — jamais le fichier physique, jamais `Workspace.images`, jamais un autre Dataset.

## 4. Contrat fonctionnel validé

**Action** : nouveau bouton « Retirer du dataset » dans `DatasetsPage`, à côté de `enlarge_button`.

**Sélection** : multiple — `images_list` passe en `QListWidget.ExtendedSelection` (actuellement sélection simple par défaut, sans risque de régression confirmé par le mini-audit : aucun test existant ne dépend de l'exclusivité de la sélection simple).

**Disponibilité de l'action** : réutilisation stricte du mécanisme déjà existant (`_update_enlarge_button_state()`, qui gère déjà `enlarge_button` selon la présence d'une sélection) — étendu pour piloter également ce nouveau bouton. Aucune seconde source de vérité introduite. Sans Dataset actif, `images_list` est naturellement vide (aucune sélection possible) — aucun garde-fou/message dédié nécessaire.

**Confirmation** : **aucune** — cohérent avec `delete_dataset()` (suppression d'un Dataset entier), qui n'en affiche déjà aucune ; une confirmation ici serait plus alarmiste que l'action la plus destructive déjà existante dans cette Page.

**Effet** : retire uniquement les `Image` correspondantes de `active_dataset.images` (comparaison par chemin résolu, même convention que `add_images()`/`preview_collisions()`). Ne touche jamais `Workspace.images`, ni aucun autre Dataset, ni le fichier physique sur disque.

**Retrait de la dernière image** : comportement naturel, aucune règle spéciale — `images_list` devient simplement vide, `enlarge_button`/« Retirer du dataset » redeviennent désactivés (même mécanisme que le rafraîchissement déjà existant).

**Sélection après rafraîchissement** : réinitialisée — comportement déjà garanti par `update_datasets()` (reconstruction complète de `images_list`), identique au comportement déjà observé pour `add_images_from_gallery()` (Mission 044).

## 5. Périmètre

Production (2) :
- `src/managers/dataset_manager.py` (nouvelle méthode `remove_images()`)
- `src/ui/pages/datasets_page.py` (nouveau bouton + méthode + sélection multiple)

Tests (2) :
- `tests/integration/test_datasets_page.py` (extension)
- `tests/integration/test_dataset_roundtrip.py` (extension — persistance et référence partagée entre deux Datasets)

## 6. Hors périmètre

- Suppression depuis `ImagesPage`.
- Suppression physique d'un fichier.
- Toute cascade entre Datasets.
- Toute gestion générale des références/nettoyage de fichiers orphelins.
- Tri de galerie, portabilité des chemins, refonte Domain, refonte EventBus.

## 7. Wiring de rafraîchissement — aucun ajout

```
DatasetsPage.remove_selected_images_from_dataset()
  → DatasetManager.remove_images(paths)
  → WorkspaceManager.save() (uniquement si au moins une image a été réellement retirée)
  → événement WORKSPACE_SAVED
  → DatasetsPage.update_datasets() (déjà abonné depuis MainWindow)
```

Aucune souscription EventBus nouvelle, aucun nouvel événement `DatasetManager` publié — symétrie stricte avec `add_images()`, qui ne publie déjà aucun événement dédié.

## 8. Stratégie d'implémentation — réellement mise en œuvre

- `DatasetManager.remove_images(paths: List[str]) -> int` : retourne `0` sans mutation si aucun Dataset actif ; construit l'ensemble des chemins résolus à retirer (`os.path.normcase(str(Path(p).resolve()))`, même convention que le reste du Manager) ; filtre `dataset.images` en excluant toute `Image` dont le chemin résolu correspond ; appelle `WorkspaceManager.save()` uniquement si au moins une image a effectivement été retirée ; retourne le nombre réellement retiré. Aucun événement dédié publié, symétrique à `add_images()`.
- `DatasetsPage` : `images_list.setSelectionMode(QListWidget.ExtendedSelection)` dans le constructeur ; nouveau bouton `self.remove_from_dataset_button` (« Retirer du dataset »), placé à côté de `enlarge_button` dans une `QHBoxLayout` partagée, initialement désactivé ; `_update_enlarge_button_state()` étendue pour piloter aussi ce bouton selon `bool(images_list.selectedItems())` — aucune seconde source de vérité ; nouvelle méthode `remove_selected_images_from_dataset()` — lit les chemins des items sélectionnés (`Qt.UserRole`), no-op si aucune sélection, sinon appelle `dataset_manager.remove_images(paths)`. Aucune confirmation, cohérent avec `delete_dataset()`.
- `enlarge_button`/double-clic continuent d'agir sur `images_list.currentItem()` seul, comportement inchangé et déterministe même avec plusieurs items sélectionnés — confirmé par test dédié et par le smoke test réel.
- Aucun changement `ImagesPage`, Domain, EventBus, persistance au-delà de l'appel déjà existant à `WorkspaceManager.save()`.

## 9. Stratégie de tests — réellement mise en œuvre

`test_datasets_page.py` (10 tests nets nouveaux) : `images_list` en `ExtendedSelection` ; bouton désactivé sans sélection, activé avec sélection simple ou multiple ; retrait d'une image sélectionnée ; retrait de plusieurs images en une opération ; clic sans sélection → no-op ; retrait de la dernière image → galerie vide, les deux boutons redésactivés ; rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` (aucun appel manuel) ; « Voir en grand » confirmé fonctionnel avec une sélection multiple active (`currentItem()` déterministe).

`DatasetManagerRemoveImagesTest` (nouvelle classe, `test_dataset_roundtrip.py`, 8 tests) : retrait d'une entrée, retrait multiple en un appel, chemin inconnu → no-op (`0`, aucune mutation), sans Dataset actif → `0`, fichier physique jamais touché, `Workspace.images` jamais touché, sauvegarde déclenchée uniquement en cas de mutation réelle (`patch.object(..., wraps=...)` sur `WorkspaceManager.save`), et la **propriété déterminante** : une image de `Workspace.images` ajoutée à deux Datasets distincts, retrait dans l'un, conservation confirmée dans l'autre + dans `Workspace.images` + sur disque.

`DatasetRoundTripTest` (1 test net nouveau) : cycle complet réel — Dataset A et B partageant la même image via « Ajouter depuis Images… », retrait côté A, sauvegarde, fermeture, réouverture avec instances fraîches — propriété de référence partagée confirmée survivre au redémarrage.

`test_images_page.py` : exécuté intégralement, **aucune modification** — 23/23 OK.

Aucune comparaison pixel par pixel. Aucune nouvelle vérification approfondie des responsabilités déjà couvertes ailleurs.

## 10. Critères d'acceptation — résultats

- Retrait d'une image sélectionnée → retirée du Dataset actif uniquement — **conforme**.
- Retrait multiple en une opération → toutes les images sélectionnées retirées — **conforme**.
- Fichier physique jamais supprimé, à aucune étape — **conforme**, vérifié par test et smoke test réel.
- `Workspace.images` jamais modifié par cette mission — **conforme**.
- Un autre Dataset référençant la même image reste intact après retrait dans le premier — **conforme**, propriété déterminante validée par test dédié et smoke test réel.
- Sans sélection → bouton désactivé, clic impossible — **conforme**.
- Persistance confirmée après fermeture/réouverture du Workspace — **conforme**.
- Rafraîchissement de `DatasetsPage.images_list` sans wiring EventBus supplémentaire — **conforme**.
- Non-régression de `add_images_from_gallery()`/import externe/`test_images_page.py` (23/23 OK, non modifié) — **conforme**.
- Suite `test_datasets_page.py` : **30/30 OK** (20 précédents + 10 nets nouveaux). Suite `test_dataset_roundtrip.py` : **36/36 OK** (27 précédents + 9 nets nouveaux).
- Suite complète du projet : **768/768 OK** (749 précédents + 19 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 11) réalisé, résultat PASS.**

## 11. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels, sélection et clics par vrais événements Qt — `QTest.mouseClick`, y compris Ctrl-clic pour la multi-sélection). Script et captures exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Dataset A et Dataset B référençant tous deux la même image (via « Ajouter depuis Images… ») — sélection réelle d'un item dans la galerie du Dataset A, bouton « Retirer du dataset » activé.
- Clic réel sur le bouton → image retirée de la galerie du Dataset A (`images_list` vide immédiatement, sans appel manuel), boutons redésactivés.
- Bascule vers Dataset B → image toujours présente, chemin identique.
- `Workspace.images` inchangé, fichier physique confirmé toujours présent sur disque.
- Retrait multiple réel (clic + Ctrl-clic sur 2 items) → les deux retirées en une seule opération.
- Fermeture puis réouverture réelle du Workspace (instances fraîches) → Dataset A restauré vide, Dataset B restauré avec l'image, `Workspace.images` inchangé, fichier physique toujours présent.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4. Aucune vérification manuelle utilisateur n'a été nécessaire.

## 12. Risques / non-régressions

- **Risque architectural** : nul — aucun changement Domain, aucun nouvel événement, `WorkspaceManager.save()` déjà existant réutilisé tel quel. Confirmé par inspection du diff complet.
- **Risque de suppression physique accidentelle** : écarté par construction et confirmé par test et smoke test réel — `remove_images()` ne contient aucun appel filesystem.
- **Risque de cascade vers un autre Dataset** : écarté par construction et confirmé par test et smoke test réel — chaque Dataset possède son propre pool `Image` indépendant (Mission 011).
- **Risque de régression sur la sélection simple d'`images_list`** : écarté — 30/30 `test_datasets_page.py` OK, y compris tous les tests hérités de Missions 042/044.
- **Risque de rafraîchissement manqué** : écarté par le mini-audit puis confirmé par le smoke test réel — même chemin `WORKSPACE_SAVED` déjà prouvé suffisant pour Missions 043/044.

## État d'avancement

- Audit de sélection (candidats Mission 045), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 30/30 (`test_datasets_page.py`), 36/36 (`test_dataset_roundtrip.py`), 23/23 (`test_images_page.py`, non modifié), 768/768 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée**.
- GitHub Release : **non préparée**.
