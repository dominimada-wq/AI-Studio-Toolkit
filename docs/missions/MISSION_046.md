# Mission 046 — Delete Images from the Images Gallery

> **STATUT : IMPLÉMENTATION RÉALISÉE, 38/38 TESTS CIBLÉS (14 `WorkspaceManagerRemoveImagesTest` + 10 `ImagesPageTest` nets nouveaux + non-régressions), 792/792 TESTS AUTOMATISÉS VERTS, SMOKE TEST MANUEL RÉEL DU RENDU QT PASS. CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> Voir "État d'avancement" en fin de document.

## 1. Contexte

Dette distincte identifiée en retour par Mission 045 (voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés") : `ImagesPage`/`Workspace.images` — la galerie principale du Workspace — ne propose aujourd'hui aucune suppression d'image, à la différence de `DatasetsPage` qui sait désormais retirer une référence (Mission 045) ou supprimer un Dataset entier.

Un mini-audit ciblé en lecture seule, approfondi sur plusieurs passes suite à des points d'arrêt explicitement demandés par l'architecte, a établi les constats structurants suivants :

**Propriété physique de `Workspace.images` — constat déterminant.** Un `Image.file_path` présent dans `Workspace.images` n'est **pas** une garantie que le fichier se trouve physiquement sous `workspace_root`. Ce n'est pas une hypothèse : `tests/integration/test_workspace_roundtrip.py::test_external_paths_are_strictly_unchanged` construit déjà explicitement une `Image` avec un `file_path` externe insérée directement dans `workspace.images`, et `test_legacy_project_json_with_external_reference_still_loads_unchanged` confirme qu'un `project.json` édité à la main avec un chemin externe se recharge tel quel — les deux tests sont **déjà verts aujourd'hui**. Cause racine : `Image.list_from_data()` (Domain, indépendant de Qt/Infrastructure) ne valide que la forme des entrées, jamais leur localisation physique — il ne le peut structurellement pas, `workspace_root` n'étant pas connu du Domain. Seule voie garantissant un chemin interne : `WorkspaceManager.add_images()` (import `ImagesPage`, Accept Inference), qui passe systématiquement par `WorkspaceStorage.copy_into_workspace()`.

**Référencement par un Dataset.** La cardinalité `Workspace.characters` reste techniquement non contrainte (0..N réel, CRUD interne masqué mais fonctionnel — Missions 026/036). Une détection de référence limitée à `principal_character.datasets` manquerait donc tout Dataset appartenant à un Character non principal. La vérification doit parcourir `workspace.characters[*].datasets[*].images[*]` dans leur ensemble — traversée Domain pure, réalisable comme méthode de lecture sur `WorkspaceManager` (qui possède déjà `current_workspace`), sans dépendance circulaire vers `DatasetManager`/`CharacterManager`.

**Décision produit arbitrée par l'architecte** : la politique validée est la suivante — suppression physique bloquée, atomiquement, si au moins une image sélectionnée est encore référencée par un Dataset ; sinon, une confirmation explicite et transparente est **toujours** requise avant toute suppression/retrait, expliquant concrètement à l'utilisateur — sans jamais lui exposer la notion technique de chemin « interne/externe » — ce qui sera réellement supprimé du disque et ce qui sera seulement retiré de la galerie.

## 2. Problème

Il n'existe aujourd'hui aucun moyen de supprimer une image de la galerie principale du Workspace, ni de corriger une erreur d'import, sans passer en dehors de l'application (Explorateur Windows).

## 3. Objectif

Permettre de supprimer une ou plusieurs images sélectionnées de `Workspace.images`/`ImagesPage`, avec suppression physique réelle du fichier lorsque celui-ci appartient sûrement au Workspace, blocage atomique si une image sélectionnée est encore référencée par un Dataset, et une confirmation explicite qui explique fidèlement à l'utilisateur les conséquences réelles de l'opération.

## 4. Contrat fonctionnel validé

### 4.1 Vérification des références Dataset (avant toute confirmation)

Avant tout dialogue de confirmation, l'ensemble de la sélection est vérifié : si **au moins une** image sélectionnée est encore référencée par au moins un Dataset (tous Characters confondus), l'opération entière est bloquée — **atomiquement, aucune exception** :
- Aucune confirmation de suppression n'est affichée.
- Aucune mutation, aucune suppression physique.
- Un message de blocage (`QMessageBox.warning`) explique que la ou les images concernées doivent d'abord être retirées du/des Dataset(s), en mentionnant les noms des Datasets concernés lorsque cela reste raisonnable (peu de Datasets distincts).

### 4.2 Confirmation explicite (toujours requise, jamais de suppression silencieuse)

Une fois la vérification de la section 4.1 passée (aucun blocage), chaque image sélectionnée est classée dans l'une de deux catégories, sans jamais exposer ce vocabulaire technique à l'utilisateur :
- **« à supprimer »** : chemin résolu à l'intérieur de `workspace_root` **et** fichier physiquement présent sur disque.
- **« à retirer seulement »** : tout le reste — chemin externe au Workspace, **ou** fichier déjà absent du disque (les deux cas sont délibérément fusionnés dans cette même catégorie, pour ne pas complexifier inutilement le dialogue : dans les deux cas, aucun fichier n'est réellement supprimé).

Trois formulations de confirmation, calquées sur le pattern `QMessageBox` déjà établi (`main_window.py::_on_send_to_inference`, boutons `addButton(label, role)` avec un libellé explicite plutôt que Oui/Non génériques) :

**Sélection entièrement « à supprimer »** :
- Titre : « Supprimer les images sélectionnées ? »
- Texte : « Les images seront retirées de la galerie et les fichiers correspondants seront supprimés définitivement du projet. Cette action est irréversible. »
- Boutons : « Supprimer » (rôle Accept) / « Annuler » (rôle Reject, bouton par défaut).

**Sélection entièrement « à retirer seulement »** :
- Titre : « Retirer les images sélectionnées ? »
- Texte : « Ces images seront retirées de la galerie du projet. Aucun fichier ne sera supprimé du disque. »
- Boutons : « Retirer » (rôle Accept) / « Annuler » (rôle Reject, bouton par défaut).

**Sélection mixte** :
- Titre : « Supprimer les images sélectionnées ? »
- Texte : « {N} image(s) seront retirées de la galerie et leur(s) fichier(s) seront supprimé(s) définitivement du projet. {M} image(s) seront retirées de la galerie sans suppression de fichier. »
- Boutons : « Continuer » (rôle Accept) / « Annuler » (rôle Reject, bouton par défaut).

Les nombres `{N}`/`{M}` reflètent exactement la sélection réelle, calculés via la classification de la section 4.2.

### 4.3 Effet réel après confirmation

- Chaque image classée « à supprimer » : fichier physique réellement supprimé (`unlink()`), puis retirée de `Workspace.images`.
- Chaque image classée « à retirer seulement » : retirée de `Workspace.images`, **aucun** appel filesystem.
- `WorkspaceManager.save()` appelé une seule fois, uniquement si au moins une mutation a réellement eu lieu.
- Annulation à n'importe quelle étape (blocage, ou clic « Annuler ») : aucune mutation, aucune suppression, aucun appel `save()`.

### 4.4 Garde de sécurité absolue

Aucun `unlink()` n'est jamais exécuté sur un chemin ne résolvant pas explicitement à l'intérieur de `workspace_root` (`WorkspaceStorage.is_inside()`, déjà existant, réutilisé tel quel comme garde immédiatement avant toute suppression physique) — y compris si un bug de classification venait à se produire, cette garde reste la dernière ligne de défense.

## 5. Périmètre

Production (2) :
- `src/managers/workspace_manager.py` (nouvelles méthodes `images_referenced_by_datasets()`, `preview_image_removal()`, `remove_images()`)
- `src/ui/pages/images_page.py` (sélection multiple, nouveau bouton, orchestration des confirmations)

Tests (2) :
- `tests/integration/test_workspace_roundtrip.py` (extension — nouvelles méthodes Manager)
- `tests/integration/test_images_page.py` (extension — UI, confirmations, blocage)

## 6. Hors périmètre

- Toute modification de `DatasetsPage`/`DatasetManager` au-delà d'une éventuelle lecture (aucune mutation Dataset par cette mission).
- Toute modification Domain.
- Tout nouveau wiring EventBus au-delà de `WORKSPACE_SAVED` déjà existant.
- Nettoyage rétroactif des Datasets déjà orphelins (fichier déjà manquant avant cette mission).
- Tri de la galerie Images.
- Portabilité générale des chemins.
- Toute politique de suppression pour des références potentielles autres que Dataset (aucune n'existe à ce jour dans le Domain — confirmé par le mini-audit).

## 7. Wiring de rafraîchissement — aucun ajout

```
ImagesPage.delete_selected_images()
  → WorkspaceManager.remove_images(paths)
  → WorkspaceManager.save() (uniquement si mutation réelle)
  → événement WORKSPACE_SAVED
  → ImagesPage.update_images() (déjà abonné depuis MainWindow)
```

Aucune souscription EventBus nouvelle.

## 8. Stratégie d'implémentation — réellement mise en œuvre

**`WorkspaceManager`** — trois méthodes nouvelles, toutes opérant sur `os.path.normcase(str(Path(p).resolve()))`, même convention que `add_images()`/`DatasetManager` :

- `images_referenced_by_datasets(paths) -> dict[str, list[str]]` (lecture seule) : parcourt `current_workspace.characters[*].datasets[*].images[*]`, retourne `{nom_dataset: [chemins concernés]}` pour toute correspondance — dict vide si aucune référence.
- `preview_image_removal(paths) -> RemovalPreview` (`NamedTuple`, même convention qu'`ImportResult`/`CollisionInfo`, lecture seule) : `deletable: list[str]` (interne + présent) / `reference_only: list[str]` (externe et/ou absent). Ne suppose jamais qu'un chemin appartient au Workspace sans vérifier `WorkspaceStorage.is_inside()` explicitement.
- `remove_images(paths) -> RemovalResult` (`NamedTuple` : `deleted`, `reference_only`, `blocked_by`) : re-vérifie atomiquement les références Dataset (le Manager reste seule autorité, même principe que `DatasetManager.delete()`/`is_referenced_by_training()`) — si `blocked_by` non vide, **aucune mutation**, retour immédiat. Sinon, supprime physiquement (`Path.unlink()`, gardé par `is_inside()` réévalué immédiatement avant l'appel) chaque chemin `deletable`, retire toutes les entrées correspondantes de `Workspace.images`, appelle `save()` une seule fois si au moins une mutation a eu lieu.

**`ImagesPage`** : `list_widget.setSelectionMode(QListWidget.ExtendedSelection)` ; nouveau bouton `self.delete_button` (« Supprimer »), activé selon le même mécanisme d'état déjà existant pour `enlarge_button` (`_update_enlarge_button_state()` étendue, aucune seconde source de vérité) ; nouvelle méthode `delete_selected_images()` orchestrant exactement l'ordre validé : lecture des chemins sélectionnés → `workspace_manager.images_referenced_by_datasets(paths)` → si non vide, `QMessageBox.warning` de blocage (noms de Datasets inclus) et retour, sans jamais appeler `preview_image_removal()`/`remove_images()` ; sinon → `workspace_manager.preview_image_removal(paths)` → construction du bon texte de confirmation (section 4.2, texte neutre ne présumant jamais qu'un fichier manquant est « extérieur ») → `QMessageBox` avec boutons libellés (motif `main_window.py::_on_send_to_inference`) → si annulé, retour sans mutation ; si confirmé → `workspace_manager.remove_images(paths)`.

Aucun changement `DatasetManager`, `CharacterManager`, Domain, EventBus. La couche Presentation n'exécute elle-même aucun `unlink()`.

## 9. Stratégie de tests — réellement mise en œuvre

`test_workspace_roundtrip.py` (nouvelle classe `WorkspaceManagerRemoveImagesTest`, 14 tests) : `images_referenced_by_datasets()` — aucune référence → dict vide, une référence → dataset correctement identifié, plusieurs Datasets référençant le même chemin, référence portée par un Character non principal (cardinalité non contrainte, Missions 026/036) ; `preview_image_removal()` — chemin interne et présent → `deletable`, chemin externe (construit directement comme `test_external_paths_are_strictly_unchanged`) → `reference_only`, chemin interne mais fichier physiquement absent → `reference_only` ; `remove_images()` — suppression réelle d'un fichier interne présent, retrait de référence seul pour un externe et pour un absent, sélection mixte traitée en un seul appel, blocage atomique si au moins une entrée référencée par un Dataset (aucune mutation, aucun fichier supprimé, `Workspace.images` inchangé, vérifié précisément), sauvegarde déclenchée uniquement si mutation réelle (`patch.object(..., wraps=...)`), persistance après fermeture/réouverture.

`test_images_page.py` (10 tests nets nouveaux) : sélection étendue activée ; bouton « Supprimer » désactivé sans sélection, activé avec sélection simple/multiple ; no-op sans sélection ; suppression confirmée d'une image interne (fichier réellement absent, référence retirée, galerie rafraîchie sans appel manuel) ; confirmation annulée (aucune mutation) ; suppression confirmée d'une image externe (référence retirée, fichier intact) ; sélection mixte (interne supprimé, externe conservé, en un seul appel) ; blocage si référencée par un Dataset (aucune confirmation affichée, `Dataset` et fichier intacts).

`test_datasets_page.py`/`test_dataset_roundtrip.py` : exécutés intégralement pour non-régression M044/M045 — **aucune modification**.

Aucune comparaison pixel par pixel dans les tests automatisés.

## 10. Critères d'acceptation — résultats

- Suppression d'une image interne non référencée → fichier réellement supprimé du disque, retirée de `Workspace.images` — **conforme**, vérifié par test et smoke test réel.
- Suppression multiple en une opération, y compris sélection mixte (interne+externe) — **conforme**.
- Blocage atomique et total si au moins une image sélectionnée est référencée par un Dataset — **conforme**, aucune confirmation affichée, aucune mutation, aucun fichier supprimé.
- Confirmation systématique avec texte fidèle aux conséquences réelles, jamais de présomption d'origine pour un fichier manquant — **conforme**, textes exacts vérifiés par smoke test réel.
- Annulation à toute étape → aucune mutation — **conforme**.
- Aucun fichier externe au Workspace jamais supprimé physiquement — **conforme**, vérifié par test et smoke test réel.
- Persistance confirmée après fermeture/réouverture du Workspace — **conforme**.
- Rafraîchissement de `ImagesPage` sans wiring EventBus supplémentaire — **conforme**.
- Non-régression de `DatasetsPage`/Mission 044/Mission 045 — **conforme**, 146/146 OK sur les trois fichiers concernés, sans modification.
- Suite `test_workspace_roundtrip.py` : inchangée hors extension, verte. Suite `test_images_page.py` : **33/33 OK** (23 précédents + 10 nets nouveaux).
- Suite complète du projet : **792/792 OK** (768 précédents + 24 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 11) réalisé, résultat PASS.**

## 11. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels, vrais fichiers temporaires, clics réels via `QTest.mouseClick` sur les boutons réels des dialogues réels). Script et captures exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Image interne libre → dialogue réel « Supprimer les images sélectionnées ? » (texte et boutons vérifiés mot pour mot) → clic réel sur « Supprimer » → fichier réellement absent du disque, galerie rafraîchie sans appel manuel.
- Image externe → dialogue réel « Retirer les images sélectionnées ? » (texte adapté vérifié) → clic réel sur « Retirer » → fichier externe toujours présent, référence retirée.
- Image référencée par un Dataset → tentative bloquée réellement, message réel mentionnant le nom du Dataset (« Portraits »), aucune confirmation affichée, fichier et référence intacts.
- Retrait de la référence via `DatasetManager.remove_images()` (Mission 045) → nouvelle tentative depuis `ImagesPage` → désormais autorisée, confirmée réellement, fichier réellement supprimé.
- Sélection mixte réelle (1 interne + 1 externe, via clic + Ctrl-clic) → dialogue « Continuer » avec texte exact (« 1 image(s) ... 1 image(s) ... ») → après confirmation, l'interne est réellement supprimé, l'externe reste intact.
- Fermeture puis réouverture réelle du Workspace → état persistant confirmé (`Workspace.images` vide, cohérent avec les suppressions/retraits effectués).

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4. Aucune vérification manuelle utilisateur n'a été nécessaire.

## 12. Risques / non-régressions

- **Risque de suppression d'un fichier hors Workspace** : écarté par construction et confirmé par test et smoke test réel — `WorkspaceStorage.is_inside()` comme garde immédiatement avant tout `unlink()`, jamais contournée.
- **Risque de suppression partielle non désirée** : écarté par la politique atomique de blocage (section 4.1), appliquée à la fois côté UI et re-vérifiée côté Manager (seule autorité), confirmé par test dédié.
- **Risque de confusion utilisateur** : écarté par la confirmation systématique à trois variantes explicites (section 4.2), textes vérifiés mot pour mot par smoke test réel, jamais de suppression silencieuse.
- **Risque architectural** : nul — aucun changement Domain, `DatasetManager`/`CharacterManager` lus mais jamais mutés par cette mission, confirmé par inspection du diff complet et par 146/146 tests de non-régression M044/M045.
- **Risque de régression sur la sélection simple d'`ImagesPage`** : écarté — 33/33 `test_images_page.py` OK, y compris tous les tests hérités.
- **Risque de rafraîchissement manqué** : écarté par le mini-audit puis confirmé par le smoke test réel — même chemin `WORKSPACE_SAVED` déjà prouvé suffisant pour Missions 043/044/045.

## État d'avancement

- Audit de sélection (candidats Mission 046), mini-audit ciblé (en plusieurs passes, incluant un arrêt explicite sur la propriété physique de `Workspace.images` et un complément d'arbitrage sur l'UX de confirmation) et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 14/14 (`WorkspaceManagerRemoveImagesTest`), 33/33 (`test_images_page.py`, 23 précédents + 10 nouveaux), 146/146 (non-régression `test_workspace_roundtrip.py`/`test_dataset_roundtrip.py`/`test_datasets_page.py`), 792/792 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée**.
- GitHub Release : **non préparée**.
