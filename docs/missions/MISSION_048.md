# Mission 048 — Sort Images and Dataset Galleries by Filename

> **STATUT : IMPLÉMENTATION TERMINÉE ET VALIDÉE TECHNIQUEMENT — CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> 12/12 tests ciblés (`ImagesPageGallerySortTest` + `DatasetsPageGallerySortTest`), 823/823 tests automatisés verts, smoke test manuel réel du rendu Qt PASS. Aucun commit, tag ni Release n'existe encore pour cette mission (voir "Principe de non-auto-référence", `docs/PROJECT_CONTEXT.md`) — voir la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Le besoin "tri de la galerie Images" est documenté depuis Mission 023 (`docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés") et reste ouvert depuis : `ImagesPage.update_images()` et `DatasetsPage.update_datasets()` itèrent leurs images respectives dans l'ordre brut d'insertion (ordre de `Workspace.images`/`Dataset.images`), sans aucun tri. `Image` (`src/domain/image.py`) ne possède qu'`image_id`/`file_path` — aucun champ date, confirmé par audit.

Un mini-audit de vérification des tests existants a été effectué avant rédaction de cette spécification (`test_images_page.py`, `test_datasets_page.py`, `test_dataset_roundtrip.py`) : la quasi-totalité des tests multi-images sont agnostiques à l'ordre (comparaisons par `set`, ou noms de fixtures dont l'ordre alphabétique coïncide déjà avec l'ordre d'insertion). **Une exception réelle a été trouvée et validée par l'architecte** : `test_images_page.py::test_missing_file_item_still_created_with_fallback_icon_and_user_role` localise l'item ajouté via `list_widget.item(count() - 1)`, en supposant que le dernier ajouté (`"does_not_exist.png"`) reste en dernière position — hypothèse qui ne tient plus sous un tri alphabétique, `"does_not_exist.png"` (`d`) triant avant `"existing.png"` (`e`, ajouté par `setUp()`). Ce n'est pas un comportement contractuel produit, seulement une commodité d'écriture de test (localisation par position plutôt que par identité) — **la reformulation de ce test fait partie du périmètre de cette mission** (voir section 5).

## 2. Problème

Les galeries `ImagesPage` et `DatasetsPage` affichent les images dans l'ordre brut d'insertion, sans tri, rendant plus difficile la recherche d'une image précise à mesure que leur nombre grandit.

## 3. Objectif

Trier l'affichage des deux galeries par nom de fichier, insensible à la casse, de façon toujours active — sans aucun changement Domain/Manager/EventBus, sans aucun contrôle UI de tri.

## 4. Contrat fonctionnel validé

- Le tri est calculé à partir de `Path(file_path).name`, comparé insensible à la casse (`.lower()` sur la clé de tri uniquement — la casse d'affichage réelle du nom de fichier n'est jamais altérée).
- Le tri est **toujours actif**, sans contrôle UI (pas de combobox/bouton), sans ordre configurable, sans persistance de préférence.
- Le tri est **stable** : `sorted()` (Python, garanti stable) est utilisé directement — si deux fichiers produisent la même clé après normalisation de casse, leur ordre relatif d'origine (ordre de la liste Domain source) est conservé. Aucun second critère de tri n'est ajouté.
- Le tri est appliqué sur une **copie/itérable temporaire** construite juste avant la boucle de peuplement du `QListWidget` — `Workspace.images`/`Dataset.images` (et le payload `dict` reçu depuis `WORKSPACE_SAVED`/`DATASET_SELECTED`) ne sont jamais mutés ni réordonnés.
- S'applique identiquement à `ImagesPage` (galerie principale) et `DatasetsPage` (galerie du Dataset actif), pour la parité déjà établie entre les deux depuis Mission 042.
- Aucun champ date, aucun changement `Image`, aucune combobox/bouton de critère, aucun ordre ascendant/descendant configurable, aucune persistance — tous explicitement hors périmètre (section 6).

## 5. Périmètre

Production (2) :
- `src/ui/pages/images_page.py` (`update_images()` — tri de la liste `workspace.get("images", [])` avant la boucle de peuplement)
- `src/ui/pages/datasets_page.py` (`update_datasets()` — tri de `active_images` avant la boucle de peuplement de `images_list`)

Tests (2, aucun nouveau fichier) :
- `tests/integration/test_images_page.py` — extension + reformulation ciblée de `test_missing_file_item_still_created_with_fallback_icon_and_user_role` (localisation par `Qt.UserRole` plutôt que par position, mirroir du pattern déjà utilisé par `test_delete_confirmed_for_external_image_removes_reference_but_keeps_file` dans le même fichier — aucun changement de comportement testé)
- `tests/integration/test_datasets_page.py` — extension

## 6. Hors périmètre

- Tri par date, tout nouveau champ `Image` (ex. `created_at`).
- Toute combobox/bouton de sélection du critère de tri.
- Ordre ascendant/descendant configurable.
- Persistance d'une préférence de tri (session ou `project.json`).
- Toute modification de `Image`, `WorkspaceManager`, `DatasetManager`, Domain, EventBus.
- Tout autre fichier au-delà des deux Pages et de leurs tests.

## 7. Wiring de rafraîchissement — aucun ajout

```
WORKSPACE_SAVED / WORKSPACE_CREATED / WORKSPACE_OPENED / WORKSPACE_CLOSED
  → ImagesPage.update_images(workspace)   (tri appliqué localement avant peuplement)

WORKSPACE_SAVED / DATASET_SELECTED
  → DatasetsPage.update_datasets()        (tri appliqué localement avant peuplement)
```

Aucune souscription EventBus nouvelle, aucun changement de canal.

## 8. Stratégie d'implémentation — réellement mise en œuvre

**`ImagesPage.update_images()`** : remplacer l'itération directe de `workspace.get("images", [])` par une itération sur `sorted(workspace.get("images", []), key=lambda image: Path(image["file_path"]).name.lower())` — `workspace` reste le `dict` reçu en paramètre (jamais muté par cette méthode de toute façon, `sorted()` retourne toujours une nouvelle liste).

**`DatasetsPage.update_datasets()`** : même traitement sur `active_images` (`dataset["images"]` du Dataset actif) juste avant la boucle `for image in active_images: self.images_list.addItem(...)`.

Aucun changement à `_build_item()`/`_build_image_item()` (déjà basés sur `Path(file_path).name` pour l'affichage), aucun changement de signature, aucun nouvel import au-delà de `pathlib.Path` (déjà importé dans les deux fichiers).

## 9. Stratégie de tests — réellement mise en œuvre

`test_images_page.py` : reformulation de `test_missing_file_item_still_created_with_fallback_icon_and_user_role` (localisation par `Qt.UserRole == internal_path` plutôt que par `count() - 1`, aucun changement de comportement testé) ; nouvelle classe `ImagesPageGallerySortTest` (6 tests) — tri alphabétique sur noms volontairement désordonnés, tri insensible à la casse, stabilité pour deux fichiers de même nom affiché (dossiers source distincts, même nom exact), `Workspace.images` (Domain) confirmé dans son ordre d'insertion d'origine après tri d'affichage, re-tri confirmé après un second `WORKSPACE_SAVED` (pas seulement un ajout en fin de liste), sélection/aperçu (`enlarge_button`) confirmés fonctionnels sur un item dont la position d'affichage diffère de sa position d'insertion.

`test_datasets_page.py` : nouvelle classe `DatasetsPageGallerySortTest` (6 tests), mirroir exact de `ImagesPageGallerySortTest` appliqué à `images_list`/`Dataset.images`.

**12/12 tests ciblés nets nouveaux, tous verts.** Aucune comparaison pixel par pixel. Aucun test Domain/Manager dupliqué — `test_dataset_roundtrip.py` et les autres suites non concernées par ce changement purement Presentation, exécutées intégralement pour confirmer l'absence de régression (111/111 OK sur `test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py`).

## 10. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels, vrais fichiers temporaires). Script et capture exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Import de 5 fichiers à noms volontairement désordonnés et de casse mixte (`zebra.png`, `Mango.png`, `apple.png`, `banana.PNG`, `Cherry.png`) dans `ImagesPage` → ordre réel affiché : `apple.png`, `banana.PNG`, `Cherry.png`, `Mango.png`, `zebra.png` — capture `m048_01_images_page_sorted.png` confirmant visuellement le tri.
- Mêmes noms importés dans `DatasetsPage` (Dataset actif) → même ordre alphabétique réel confirmé.
- `Workspace.images`/`Dataset.images` (Domain, inspection directe des objets) confirmés dans leur ordre d'insertion d'origine (`zebra.png`, `Mango.png`, `apple.png`, `banana.PNG`, `Cherry.png`) — non trié, seul l'affichage l'est.
- Stabilité réelle vérifiée : deux fichiers nommés `shot.png` (dossiers source distincts) ajoutés l'un après l'autre → le premier ajouté reste avant le second dans l'affichage trié.
- Sélection réelle de l'item en position d'affichage 0 (`apple.png`) confirmée pointer vers le bon fichier interne malgré une position d'insertion différente.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 11. Risques / non-régressions

- **Risque de régression sur un test existant supposant l'ordre d'insertion** : identifié précisément (`test_missing_file_item_still_created_with_fallback_icon_and_user_role`), reformulé, vert — tous les autres tests multi-images confirmés agnostiques à l'ordre ou coïncidentiellement compatibles, 111/111 OK sur les trois suites concernées.
- **Risque de mutation accidentelle de l'ordre Domain** : écarté par construction et confirmé par test et smoke test réel — `sorted()` retourne toujours une nouvelle liste, jamais un tri en place (`list.sort()` non utilisé), `Workspace.images`/`Dataset.images` inspectés directement et confirmés dans leur ordre d'insertion.
- **Risque architectural** : nul — aucun changement Domain/Manager/EventBus, modification strictement confinée aux deux méthodes de peuplement UI, confirmé par inspection du diff complet.
- **Risque de régression sur la sélection/le rafraîchissement** : écarté — `_update_enlarge_button_state()`/`blockSignals()` et le mécanisme de rafraîchissement EventBus restent strictement inchangés, seul l'ordre d'itération change, confirmé par test et smoke test réel.

## 12. Critères d'acceptation — résultats

- Tri alphabétique, insensible à la casse, toujours actif, sans contrôle UI — **conforme**, vérifié par test et smoke test réel.
- Tri stable pour des clés identiques après normalisation — **conforme**.
- `Workspace.images`/`Dataset.images` jamais mutés/réordonnés — **conforme**, vérifié par test et smoke test réel (inspection directe des objets Domain).
- Application cohérente à `ImagesPage` et `DatasetsPage` — **conforme**.
- Sélection/aperçu fonctionnels après tri — **conforme**.
- Rafraîchissement correct après `WORKSPACE_SAVED` — **conforme**.
- Test existant supposant l'ordre d'insertion identifié et reformulé sans changement de comportement testé — **conforme**.
- Suite ciblée : **12/12 OK** (6 `ImagesPageGallerySortTest` + 6 `DatasetsPageGallerySortTest`), non-régression **111/111 OK** (`test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py`).
- Suite complète : **823/823 OK** (811 précédents + 12 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 10) réalisé, résultat PASS.**

## État d'avancement

- Audit de sélection (candidat Mission 048), vérification ciblée des tests existants (une contradiction trouvée et validée par l'architecte) et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 12/12 ciblés, 111/111 de non-régression, 823/823 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée** — en attente de validation technique de l'architecte avant commit/tag/Release.
