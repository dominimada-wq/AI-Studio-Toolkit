# Mission 049 — Sort Images and Dataset Galleries by File Date

> **STATUT : IMPLÉMENTATION TERMINÉE ET VALIDÉE TECHNIQUEMENT — CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> 17/17 tests ciblés nets nouveaux (extension de `ImagesPageGallerySortTest`/`DatasetsPageGallerySortTest`, Mission 048), 128/128 de non-régression, 840/840 tests automatisés verts, smoke test manuel réel du rendu Qt PASS. Aucun commit, tag ni Release n'existe encore pour cette mission (voir "Principe de non-auto-référence", `docs/PROJECT_CONTEXT.md`) — voir la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Le besoin "tri de la galerie Images" (identifié Mission 023) a été partiellement résolu par Mission 048 (tri par nom de fichier). Le tri par date restait explicitement ouvert, avec une précision apportée par l'architecte après clôture de Mission 048 : permettre d'afficher notamment les images les plus récentes en premier.

Un audit dédié a établi les constats suivants avant toute décision :

- **Source de date retenue : `Path(file_path).stat().st_mtime`** (date de dernière modification du fichier sur disque) — **décision produit explicite de l'architecte**, préférée à un nouveau champ Domain persistant (`created_at`/`added_at`), pour ne modifier ni `Image.to_dict()`/`from_dict()`, ni provoquer de migration des anciens `project.json`, et pour rester une information immédiatement disponible aussi bien pour un fichier interne qu'externe.
- **Conséquence de `shutil.copy2()` — compromis explicitement accepté** : `WorkspaceStorage.copy_into_workspace()` (utilisée par `WorkspaceManager.add_images()`/`DatasetManager.add_images()`, Mission 028) appelle `shutil.copy2()`, qui préserve le `mtime` du fichier source. Une photo ancienne importée aujourd'hui conserve donc son ancien `mtime` après copie — le tri par date reflète la **date de dernière modification du fichier**, jamais la **date d'ajout au projet**. Ce comportement est le comportement **attendu et documenté** de cette mission, pas un défaut à corriger — Mission 049 n'introduit aucun mécanisme de date d'import.
- **Deux critères de tri désormais disponibles** (nom, date) justifient un contrôle UI explicite — absent de Mission 048, qui ne traitait qu'un seul critère implicite.
- **Fichier manquant** : `Path(file_path).stat()` lève `OSError` (`FileNotFoundError`) si le fichier n'existe pas — nécessite un repli explicite, sans jamais faire échouer le rafraîchissement de la galerie.
- **`Dataset.images`/`Workspace.images`** : `DatasetManager.add_images()` utilise la même primitive `copy_into_workspace()`/`shutil.copy2()` que `WorkspaceManager.add_images()` — le même compromis `mtime` s'applique identiquement aux deux galeries, aucune divergence de traitement nécessaire.

## 2. Problème

Il n'existe aujourd'hui aucun moyen d'afficher les images les plus récentes en premier dans `ImagesPage`/`DatasetsPage` — seul le tri par nom (Mission 048) est disponible.

## 3. Objectif

Ajouter un contrôle de tri explicite à deux critères fixes — Nom (A → Z) et Date du fichier (plus récent d'abord) — sur `ImagesPage` et `DatasetsPage`, sans aucun changement Domain, en utilisant `mtime` comme seule source de date.

## 4. Contrat fonctionnel validé

### 4.1 Contrôle UI

Un `QComboBox` à exactement deux entrées fixes, sur chacune des deux Pages :
- `"Nom (A → Z)"` — comportement strictement identique à Mission 048 (`Path(file_path).name.lower()`, ascendant).
- `"Date du fichier (plus récent d'abord)"` — `mtime` décroissant.

Aucune option ascendant/descendant configurable, aucun troisième critère, aucune persistance de la sélection (session ou `project.json`) — le critère actif ne survit pas à la fermeture de la Page/du Workspace, retombe sur "Nom" par défaut à chaque (re)création de la Page (comportement identique à tout autre widget non persistant de ce type dans le projet).

### 4.2 Tri par date

- Clé de tri : `mtime` du fichier réellement présent sur disque, ordre **décroissant** (plus récent en premier).
- **Fichier manquant** : ne fait jamais échouer le rafraîchissement de la galerie. Traité avec la valeur sentinelle `float("-inf")` — la plus petite valeur possible, qui place systématiquement le fichier manquant en toute dernière position sous un tri décroissant (`reverse=True`), sans jamais risquer de le faire remonter en tête (aucune sentinelle positive/`+inf` utilisée).
- **Plusieurs fichiers manquants** : partagent tous la clé `float("-inf")` — le tri stable de Python (`sorted(..., reverse=True)`, qui préserve explicitement l'ordre relatif des clés égales même avec `reverse=True`, propriété documentée du langage) conserve leur ordre relatif d'origine entre eux.
- **`mtime` identiques** (résolution filesystem, copies rapprochées) : même garantie de stabilité, aucun second critère arbitraire ajouté.
- **Fichier externe** : `stat()` fonctionne identiquement, qu'il soit interne ou externe au Workspace — aucune distinction de traitement nécessaire.

### 4.3 Tri par nom — non régressé

Comportement strictement inchangé depuis Mission 048 — critère par défaut, ascendant, insensible à la casse.

### 4.4 Domain — aucun changement

Aucune modification de `Image`, `Workspace`, `Dataset`, de leur sérialisation, ni d'aucun `project.json`. `Workspace.images`/`Dataset.images` conservent strictement leur ordre stocké d'origine — le tri (nom ou date) ne s'applique que sur une copie temporaire, exactement comme Mission 048.

## 5. Périmètre

Production (3) :
- `src/ui/thumbnails.py` (nouveau helper `file_mtime_sort_key(file_path)` — primitive Presentation simple : `stat().st_mtime` ou `float("-inf")` sur `OSError`, aucune abstraction de tri générique)
- `src/ui/pages/images_page.py` (`QComboBox` de critère, `update_images()` étendu pour appliquer le critère actif, méthode de rebascule)
- `src/ui/pages/datasets_page.py` (même extension, mirroir exact)

Tests (2, aucun nouveau fichier) :
- `tests/integration/test_images_page.py` (extension de `ImagesPageGallerySortTest`, déjà existante depuis Mission 048)
- `tests/integration/test_datasets_page.py` (extension de `DatasetsPageGallerySortTest`, déjà existante depuis Mission 048)

## 6. Hors périmètre

- Tout nouveau champ Domain (`created_at`/`added_at` ou équivalent).
- Toute option ascendant/descendant configurable par critère.
- Toute persistance de la préférence de tri (session ou `project.json`).
- Tout mécanisme de date d'import distinct de `mtime` (le compromis `shutil.copy2` est accepté tel quel, jamais contourné).
- Troisième critère de tri (type de média, dimensions, etc.).
- Toute modification de `WorkspaceManager`, `DatasetManager`, EventBus.

## 7. Wiring de rafraîchissement — aucun ajout

```
WORKSPACE_SAVED / WORKSPACE_CREATED / WORKSPACE_OPENED / WORKSPACE_CLOSED
  → ImagesPage.update_images(workspace)   (critère actif du QComboBox appliqué)

WORKSPACE_SAVED / DATASET_SELECTED
  → DatasetsPage.update_datasets()        (critère actif du QComboBox appliqué)

QComboBox.currentIndexChanged (nouveau signal local, jamais EventBus)
  → ImagesPage: update_images(workspace_manager.current_workspace.to_dict() si ouvert, sinon None)
  → DatasetsPage: update_datasets()  (lit déjà son état directement depuis dataset_manager)
```

Aucune souscription EventBus nouvelle — le changement de critère est un événement Qt local, jamais publié sur l'EventBus (aucune mutation Domain).

## 8. Stratégie d'implémentation — réellement mise en œuvre

**`src/ui/thumbnails.py`** :
```python
def file_mtime_sort_key(file_path):
    try:
        return Path(file_path).stat().st_mtime
    except OSError:
        return float("-inf")
```

**`ImagesPage`** : nouveau `self.sort_combo` (`QComboBox`, `addItem("Nom (A → Z)", "name")` / `addItem("Date du fichier (plus récent d'abord)", "date")`), connecté à une méthode qui relit `self.workspace_manager.current_workspace` et rappelle `self.update_images(...)` avec le `dict` courant (ou `None` si aucun Workspace ouvert) — aucun état de critère dupliqué, `self.sort_combo.currentData()` lu directement dans `update_images()` au moment de trier. `update_images()` étend son tri existant : `key=lambda image: Path(image["file_path"]).name.lower()` si critère `"name"`, sinon `key=lambda image: file_mtime_sort_key(image["file_path"]), reverse=True`.

**`DatasetsPage`** : mirroir exact — `self.sort_combo` connecté à une méthode qui rappelle directement `self.update_datasets()` (qui lit déjà son état depuis `dataset_manager`, aucun paramètre à reconstruire).

Aucun changement à `_build_item()`/`_build_image_item()`, aucun nouvel import au-delà de `file_mtime_sort_key` (déjà `Path` importé dans les deux fichiers).

## 9. Stratégie de tests — réellement mise en œuvre

Extension de `ImagesPageGallerySortTest`/`DatasetsPageGallerySortTest` (Mission 048, aucun nouveau fichier) — 8 tests nets nouveaux dans chacune (17 au total, une classe en compte un de plus : "changement de Dataset actif") :
- Tri par date : `mtime` réels échelonnés (`os.utime()`) → ordre décroissant confirmé.
- Tri par date pour un fichier externe (`Image` ajoutée directement, hors `add_images()`, même technique que les tests M046 existants).
- Fichier manquant en tri par date → placé en dernière position, rafraîchissement non interrompu (aucune exception levée).
- Plusieurs fichiers manquants → ordre relatif d'origine conservé entre eux (stabilité).
- Deux fichiers de `mtime` strictement identique → ordre relatif d'origine conservé.
- Bascule réelle Nom → Date puis Date → Nom via `QComboBox.setCurrentIndex()` (signal Qt réel `currentIndexChanged`, jamais simulé autrement) → réordonnancement immédiat confirmé dans les deux sens.
- Rafraîchissement `WORKSPACE_SAVED` réel (ajout d'une nouvelle image) → critère "date" toujours actif après coup, jamais réinitialisé à "nom" (`sort_combo.currentData()` vérifié explicitement).
- `DatasetsPage` uniquement : changement de Dataset actif (création + sélection d'un second Dataset) → le critère "date" reste actif sur la Page, comportement déterministe indépendant du Dataset affiché.
- `Workspace.images`/`Dataset.images` confirmés dans leur ordre d'insertion d'origine, quel que soit le critère actif.

**17/17 tests ciblés nets nouveaux, tous verts** (14/14 `ImagesPageGallerySortTest` + 15/15 `DatasetsPageGallerySortTest`, dont 6+6 déjà existants Mission 048). Aucune comparaison pixel par pixel. Non-régression `test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py` : 128/128 OK.

## 10. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels, vrais fichiers temporaires, `os.utime()` pour fixer des `mtime` explicites). Script et captures exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Import de 3 fichiers à noms désordonnés/casse mixte (`Zebra.png`/`apple.png`/`Mango.png`) et `mtime` explicitement échelonnés dans `ImagesPage` → mode "Nom" par défaut confirmé (`apple.png`, `Mango.png`, `Zebra.png`) — capture `m049_01_images_name_mode.png`.
- Bascule réelle du `QComboBox` vers "Date du fichier (plus récent d'abord)" → ordre réel décroissant confirmé (`apple.png`, `Zebra.png`, `Mango.png`) — capture `m049_02_images_date_mode.png` confirmant visuellement le contrôle et l'ordre.
- Même séquence répétée dans `DatasetsPage` (Dataset actif) → mêmes résultats confirmés — capture `m049_03_datasets_date_mode.png`.
- Fichier manquant ajouté proprement (`Image` référençant un chemin inexistant) → confirmé en toute dernière position en mode Date, aucune exception levée par le rafraîchissement.
- `Workspace.images`/`Dataset.images` (Domain, inspection directe des objets) confirmés dans leur ordre d'insertion d'origine, indépendamment du critère actif à l'écran.
- Ajout d'une nouvelle image (déclenchant un `WORKSPACE_SAVED` réel) pendant que le critère "Date" est actif → critère resté "Date" après rafraîchissement, nouvelle image correctement positionnée en tête (plus récente), fichier manquant toujours en fin de liste.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 11. Risques / non-régressions

- **Risque sémantique du compromis `mtime`/`shutil.copy2`** : explicitement accepté et documenté par l'architecte (section 1) — non traité comme un défaut de cette mission.
- **Risque de fichier manquant remontant accidentellement en tête** : écarté par construction et confirmé par test et smoke test réel — `float("-inf")` est la plus petite valeur possible, ne peut jamais dominer un `mtime` réel sous tri décroissant.
- **Risque de régression sur le tri par nom (Mission 048)** : écarté — comportement strictement inchangé, critère par défaut, couvert par les tests Mission 048 déjà existants, tous restés verts sans modification.
- **Risque architectural** : nul — aucun changement Domain/Manager/EventBus, modification strictement confinée aux deux Pages et au helper Presentation partagé, confirmé par inspection du diff complet.
- **Risque de double source de vérité pour le critère actif** : écarté — `self.sort_combo.currentData()` lu directement au moment du tri, aucun attribut d'état dupliqué.
- **Risque de réinitialisation arbitraire du critère au rafraîchissement/changement de Dataset** : écarté par construction et confirmé par test et smoke test réel — le critère reste un état du `QComboBox` de la Page, jamais réinitialisé par `update_images()`/`update_datasets()`.

## 12. Critères d'acceptation — résultats

- Tri par nom strictement inchangé depuis Mission 048 — **conforme**.
- Tri par date décroissant (`mtime`) — **conforme**, vérifié par test et smoke test réel.
- Fichier manquant toujours en fin de liste, jamais d'exception — **conforme**.
- Plusieurs fichiers manquants et `mtime` égaux : stabilité — **conforme**.
- Contrôle `QComboBox` à deux entrées fixes, identique dans `ImagesPage`/`DatasetsPage` — **conforme**.
- Bascule immédiate du réordonnancement à l'affichage, sans mutation Domain — **conforme**.
- Critère conservé après `WORKSPACE_SAVED` et après changement de Dataset actif — **conforme**.
- `Workspace.images`/`Dataset.images` jamais mutés — **conforme**, vérifié par test et smoke test réel.
- Aucun changement Domain/Manager/EventBus — **conforme**, confirmé par inspection du diff complet.
- Suite ciblée : **17/17 OK**, non-régression **128/128 OK**.
- Suite complète : **840/840 OK** (823 précédents + 17 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 10) réalisé, résultat PASS.**

## État d'avancement

- Audit de sélection (candidat Mission 049), audit dédié du compromis `mtime`/`shutil.copy2` et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 17/17 ciblés, 128/128 de non-régression, 840/840 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée** — en attente de validation technique de l'architecte avant commit/tag/Release.
