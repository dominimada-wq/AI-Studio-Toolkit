# Mission 028 — Import Images into Workspace

Source : audit READ-ONLY de priorisation Mission 028 (candidats comparés — A : Import réel des images, B : Chemins relatifs/portabilité, C : Tri de la galerie Images, D : Suite Character Identity, E : Audit multi-référence, F : i18n, G : autre candidat découvert dans le code), Candidat A retenu et validé par l'architecte, avec l'ordre indicatif Mission 028 (copie réelle) → Mission 029 (chemins relatifs) → Mission 030 (à décider).

**Révision post-validation** : l'architecte a validé la spécification initiale sous réserve de verrouiller deux points avant implémentation — le contrat de retour de `add_images()` (nécessitant un audit exhaustif de ses appelants) et le comportement pour une source déjà interne au Workspace. Les sections 6 à 10 ci-dessous intègrent les résultats de cet audit et les décisions qui en découlent, y compris une découverte non anticipée par la spécification initiale (section 6.3 — `InferencePage`/Accept).

**État final (voir sections 22/23)** : implémentée, testée (510/510) et validée par un smoke test manuel réel — **PASS**, après un premier smoke test réel ayant révélé et fait corriger deux problèmes fonctionnels (gestion des collisions de nom, régression `DatasetManager`/Character principal). Clôture documentaire fonctionnelle effectuée ; clôture Git en attente d'autorisation explicite de l'architecte.

## 1. Contexte

Audit préalable confirmé par lecture directe du code réel (pas de supposition) :

- `WorkspaceManager.add_images()` (`src/managers/workspace_manager.py:296`) et `DatasetManager.add_images()` (`src/managers/dataset_manager.py:143`) stockent aujourd'hui le `file_path` choisi via `QFileDialog.getOpenFileNames()` **tel quel** — aucune copie physique n'a jamais lieu, la ressource reste indéfiniment dépendante de son emplacement d'origine hors du Workspace.
- Seule exception déjà interne par construction : les images générées par `Inference` et acceptées, physiquement écrites sous `<workspace>/outputs/` (mécanisme `GenerationManager`/`InferencePage`, sans rapport avec l'import) — **point qui redevient central en section 6.3**.
- `WorkspaceStorage.DIRECTORIES` (`src/infrastructure/storage/workspace_storage.py:36-49`) crée déjà, à la création de tout projet, les dossiers `images/`, `datasets/`, `datasets/train`, `datasets/validation`, `models/checkpoints`, `models/loras`, `outputs/`, etc. — **la destination physique pour les images existe donc déjà pour tout Workspace**, il n'y a aucune nouvelle arborescence à introduire pour le pool `Workspace.images`.
- **Constat sur `datasets/train`/`datasets/validation`** (vérifié par recherche exhaustive `grep -rn "datasets/train\|datasets/validation\|\"train\"\|\"validation\""` sur `src/`) : ces deux dossiers sont créés par `create_directories()` mais **ne sont référencés nulle part ailleurs dans le code**. `Dataset` (`src/domain/dataset.py`) est une dataclass plate avec un seul pool `images: list[Image]`, sans aucun champ de rôle. Conclusion validée par l'architecte (section 3 de sa validation) : Mission 028 **n'invente pas** cette distinction, `datasets/train`/`datasets/validation` restent tels quels, non pilotés par cette mission.

## 2. Objectif

Lorsqu'un utilisateur importe une ou plusieurs images (`ImagesPage`/`DatasetsPage`), AI Studio Toolkit doit :
- copier physiquement chaque fichier source **réellement externe** dans le Workspace ;
- conserver le fichier source intact, à son emplacement d'origine, sans jamais le déplacer ni le supprimer ;
- persister le chemin de la **copie interne** (ou du fichier déjà interne, section 6), jamais un chemin externe, comme `Image.file_path` ;
- rendre l'utilisateur indépendant du fichier source après l'import — un déplacement/suppression ultérieur du fichier d'origine ne doit plus casser la référence dans AI Studio Toolkit.

**Principe produit** : "Importer" change de sens à partir de cette mission — ce n'est plus "référencer un fichier existant ailleurs", c'est "faire entrer une copie du fichier dans le projet, ou reconnaître qu'il y est déjà".

## 3. Architecture retenue — emplacement de la primitive de copie

Respect strict des couches (`CLAUDE.md`) : aucune logique de copie dispersée dans les Pages, le Manager reste responsable de l'orchestration, l'UI reste responsable uniquement du choix des fichiers (`QFileDialog`, inchangé) et de l'affichage du résultat.

- **`src/infrastructure/storage/workspace_storage.py`** (Infrastructure — précédent direct : `rename_folder()`/`create_directories()`/`save()` durci en Mission 027) : deux nouvelles méthodes statiques, purement filesystem, sans connaissance du Domain :
  - `WorkspaceStorage.is_inside(path: Path, root: Path) -> bool` — prédicat pur, aucune I/O au-delà de `resolve()`.
  - `WorkspaceStorage.copy_into_workspace(source: Path, destination_folder: Path, workspace_root: Path) -> Path` — orchestration copie/réutilisation (section 6).
- **`src/managers/workspace_manager.py`** : `add_images()` étendu pour orchestrer la copie/réutilisation, nouveau type `ImportResult` (section 9), défini ici et importé par `dataset_manager.py` — cohérent avec le sens de dépendance déjà existant (`dataset_manager.py` importe déjà `WORKSPACE_CREATED`/`OPENED`/`CLOSED` depuis `workspace_manager.py`, `src/managers/dataset_manager.py:12-17`).
- **`src/managers/dataset_manager.py`** : `add_images()` étendu selon exactement le même principe, réutilisant `WorkspaceStorage.copy_into_workspace()`/`ImportResult` — aucune duplication de logique entre les deux Managers.
- **`src/ui/pages/images_page.py`** / **`src/ui/pages/datasets_page.py`** : `import_images()` adapté au nouveau contrat de retour (section 10).

## 4. Comportement exact de `WorkspaceStorage.copy_into_workspace()`

```python
@staticmethod
def copy_into_workspace(source: Path, destination_folder: Path, workspace_root: Path) -> Path:
```

1. **Court-circuit "déjà interne"** (section 6) : si `WorkspaceStorage.is_inside(source, workspace_root)` est vrai → retourne immédiatement `source.resolve()`, **aucun appel à `shutil.copy2()`**, aucune création de dossier. C'est cette étape qui empêche structurellement toute tentative de copie d'un fichier vers lui-même (section 6.1).
2. Sinon (source réellement externe au Workspace) : `destination_folder.mkdir(parents=True, exist_ok=True)` — création défensive, nécessaire pour le sous-dossier par Dataset qui n'existe pas encore physiquement avant le premier import de ce Dataset ; no-op pour `images/` qui existe déjà depuis `create_directories()`.
3. Résolution du **nom de fichier final**, non destructive, selon l'algorithme de collision de la section 7.
4. `shutil.copy2(source, destination_folder / final_name)` — préserve les métadonnées (date de modification).
5. En cas d'`OSError` (source introuvable, permission refusée, disque plein, destination inaccessible) : toute portion de fichier déjà écrite à `destination_folder / final_name` est supprimée en best-effort (`unlink()`, silencieux si absente), puis l'exception est enveloppée en `WorkspaceStorageError`, même contrat que `rename_folder()`/`save()` (Mission 027).
6. Retourne le `Path` absolu de la copie réussie (étape 2-5) ou du fichier déjà interne réutilisé (étape 1).

**Différence assumée avec l'écriture atomique de `project.json` (Mission 027)** : pas de fichier temporaire + `os.replace()` ici. Le nom de destination résolu à l'étape 3 est **garanti neuf** (jamais un fichier préexistant écrasé) — un échec ne peut laisser qu'un fichier orphelin sous un nom jusque-là inutilisé, nettoyé en best-effort, jamais une corruption d'un fichier déjà valide. Un mécanisme temp+rename ici serait une rigueur non justifiée par le risque réel.

## 5. Images vs Datasets — destinations

### 5.1 `ImagesPage` → `Workspace.images`

Destination : `<workspace_root>/images/`. Dossier déjà créé à la création du projet — aucune nouvelle arborescence.

### 5.2 `DatasetsPage` → `Character.datasets[*].images`

**Aucune distinction train/validation** (section 1, conclusion validée par l'architecte). Destination retenue : **sous-dossier par Dataset**, `<workspace_root>/datasets/<dataset_id>/`.

Justification `dataset_id` plutôt que `dataset.name` : identifiant stable déjà utilisé partout ailleurs dans ce Domain (`active_dataset_id`, résolution par `_find()`), garanti unique et filesystem-safe (UUID4), évite toute collision de noms de fichiers **entre deux Datasets distincts** en gardant un dossier dédié par Dataset. `dataset.name` reste une chaîne libre sans contrainte d'unicité ni de validité filesystem.

`datasets/train/`, `datasets/validation/` restent inutilisés par cette mission, non supprimés, non pilotés par elle (validé par l'architecte, section 3).

## 6. Source déjà interne au Workspace — comportement détaillé

### 6.1 Principe retenu — critère large : "déjà sous `Workspace.root`", pas seulement "déjà dans le dossier de destination exact"

Décision affinée par rapport à une lecture strictement littérale de la demande de l'architecte ("si le fichier source est déjà exactement dans le dossier interne approprié"). Le critère effectivement retenu est plus large : **une source est considérée "déjà interne" dès lors qu'elle se trouve n'importe où sous `Workspace.root`**, pas seulement dans le dossier de destination exact (`images/` ou `datasets/<dataset_id>/`) visé par cet import précis. Raison de cet élargissement, découverte pendant cet audit (section 6.3) : une lecture strictement littérale aurait silencieusement introduit une régression de duplication de stockage pour un flux existant et déjà validé.

Mécanisme : `WorkspaceStorage.is_inside(path, root)` réutilise **exactement la même technique** que `WorkspaceManager._remap_path()` (Mission 027, `src/managers/workspace_manager.py`) — comparaison composant par composant (`candidate.parts` vs `root.resolve().parts`), chaque composant normalisé via `os.path.normcase()` pour l'insensibilité à la casse Windows/NTFS, robuste même si le fichier n'existe plus (`resolve()` sans `strict=True`). **Aucune modification du code de Mission 027** — la technique est reproduite à l'identique dans une nouvelle méthode `WorkspaceStorage.is_inside()`, pas réutilisée par import direct (`_remap_path()` reste une méthode privée de `WorkspaceManager`, à une couche différente).

### 6.2 Ce que "déjà interne" implique concrètement

Quand `is_inside(source, workspace_root)` est vrai, `copy_into_workspace()` retourne `source.resolve()` sans aucune I/O de copie (section 4, étape 1). Le Manager appelant applique ensuite **une seule et même règle de déduplication**, qu'importe la provenance du chemin retourné :

- Si le chemin résolu correspond exactement à un `Image.file_path` **déjà enregistré** dans la collection cible (`Workspace.images` ou `Dataset.images` selon le cas), comparaison normcase — c'est un doublon déjà connu → **`skipped`** (section 8/9), aucune nouvelle `Image` créée.
- Sinon (fichier physiquement déjà dans le Workspace, mais jamais encore enregistré comme `Image` dans **cette** collection) → **`added`**, une nouvelle `Image(file_path=chemin_résolu)` est créée en utilisant ce chemin tel quel, sans aucune copie physique.

**Jamais de renommage artificiel (`photo_1.jpg`) pour ce cas** — la logique de collision (section 7) n'est jamais atteinte pour une source déjà interne, puisque `copy_into_workspace()` retourne avant même d'y arriver (étape 1 précède l'étape 3).

**Cohérence avec le modèle d'ownership existant (Mission 011, "Modèle D")** : rien n'empêche qu'un même fichier physique interne soit référencé à la fois par `Workspace.images` et par `Character.datasets[*].images` avec deux `Image` indépendantes (deux `image_id` distincts, comparaison déjà couverte par `test_workspace_and_dataset_pools_are_independent`, `tests/integration/test_image_roundtrip.py:214`) — un fichier déjà interne réutilisé pour un import Dataset ne "déplace" jamais ce fichier physique, il ajoute simplement une seconde référence, exactement comme deux imports externes indépendants du même chemin l'auraient déjà fait aujourd'hui pour les deux pools.

### 6.3 Découverte pendant l'audit — synergie avec `InferencePage`/Accept, comportement préservé sans modification

**Recherche exhaustive de tous les appelants de `add_images()`** (détail complet section 11) a révélé un appelant de production non anticipé par la première version de cette spécification : `src/ui/pages/inference_page.py:314`, dans le flux Accept :

```python
self._workspace_manager.add_images([self._pending_path])
```

`self._pending_path` est déjà, à ce stade, un chemin physiquement situé sous `<workspace_root>/outputs/` (écrit par `GenerationManager` avant Accept — mécanisme Mission 013/014, sans rapport avec l'import). **Sans le critère large retenu en section 6.1**, une lecture strictement littérale ("déjà exactement dans le dossier `images/`") aurait fait échouer ce court-circuit pour ce cas précis (`outputs/` ≠ `images/`), et `add_images()` aurait alors tenté de **copier** le fichier généré une seconde fois vers `images/` — dupliquant silencieusement chaque image générée et acceptée sur le disque, un effet de bord jamais discuté ni voulu par cette mission, découvert uniquement par cet audit exhaustif des appelants.

Avec le critère large (`is_inside(source, workspace_root)`, section 6.1) : `<workspace_root>/outputs/generated.png` est bien sous `workspace_root` → reconnu comme déjà interne → **comportement strictement inchangé pour Accept** : `file_path` reste le chemin `outputs/...` existant, aucune copie, aucune duplication de stockage, aucune régression sur ce flux déjà testé et validé (Missions 013/014/023/024). Ce point est vérifié explicitement par un test dédié (section 12) plutôt que simplement affirmé.

## 7. Stratégie de collision de noms — non destructive, jamais d'écrasement

Inchangé dans son principe, **atteint uniquement pour une source réellement externe** (section 6 la court-circuite pour toute source déjà interne) :

1. `stem, suffix = Path(source).stem, Path(source).suffix` (ex. `photo`, `.jpg`).
2. `candidate = destination_folder / f"{stem}{suffix}"`. Si `not candidate.exists()` → nom retenu.
3. Sinon, `n = 1, 2, 3, ...` jusqu'à trouver `f"{stem}_{n}{suffix}"` non existant → nom retenu (`photo.jpg` occupé → `photo_1.jpg` → `photo_2.jpg`...).
4. Aucune limite artificielle sur `n`.

**Aucun fichier existant n'est jamais écrasé** — garantie structurelle de l'algorithme, pas une convention documentée.

**Limite assumée** : vérification d'existence puis copie, sans verrou filesystem exclusif entre les deux étapes (TOCTOU théorique) — cohérent avec le niveau de rigueur déjà accepté ailleurs (`RenameProjectDialog` revalide de la même façon "au moment exact de l'acceptation").

## 8. Doublons — trois cas, sans hash, jamais présentés comme une erreur

Réponse à la demande explicite de l'architecte : un doublon volontairement ignoré n'est **jamais** classé comme un échec.

- **Fichiers différents, même nom** (deux photos sans rapport nommées `photo.jpg`) : traité par la collision de noms (section 7) — les deux copies coexistent sous des noms distincts, jamais d'écrasement. Ni l'un ni l'autre n'est un doublon — les deux comptent comme `added`.
- **Même chemin source apparaissant deux fois dans le même lot** (le même chemin sélectionné deux fois dans le même `QFileDialog.getOpenFileNames()`) : détecté **avant** tout appel à `copy_into_workspace()`, par comparaison exacte des chemins sources résolus déjà traités dans l'appel courant → **`skipped`**, jamais `failed`.
- **Fichier déjà interne, déjà enregistré comme `Image`** (section 6.2, premier tiret) : reconnu après retour de `copy_into_workspace()`, par comparaison du chemin résolu contre les `Image.file_path` déjà présents dans la collection cible → **`skipped`**, jamais `failed`.
- **Même fichier source importé lors de deux opérations d'import séparées, mais réellement externe** (ex. l'utilisateur clique "Importer" deux fois avec la même sélection externe) : **non détecté comme doublon** — chaque opération produit sa propre copie physique, avec un nom résolu par collision si nécessaire (comportement assumé, changement volontaire par rapport à l'existant, section 1 de la validation architecte : pas de hash de contenu, pas de table de correspondance source→copie). Après la première copie, une **réimportation ultérieure du fichier interne résultant** (et non plus du fichier externe d'origine) retomberait, elle, dans le cas "déjà interne, déjà enregistré" ci-dessus.

Aucun système de déduplication par hash de contenu — stratégie la plus simple et la plus prévisible, conformément à la demande explicite de l'architecte.

## 9. Contrat de retour de `add_images()` — `ImportResult(added, failed, skipped)`

### 9.1 Décision retenue

```python
# src/managers/workspace_manager.py
from typing import NamedTuple

class ImportResult(NamedTuple):
    added: int
    failed: list       # chemins source ayant échoué à la copie, dans l'ordre du lot
    skipped: list       # chemins source ignorés (doublon de lot ou déjà interne/déjà enregistré), dans l'ordre du lot
```

`WorkspaceManager.add_images(paths: list) -> ImportResult` et `DatasetManager.add_images(paths: list) -> ImportResult` (import de `ImportResult` depuis `workspace_manager.py`, cohérent avec le sens de dépendance déjà existant, section 3).

### 9.2 Justification — pourquoi ce changement de contrat est nécessaire, pas une sur-ingénierie

Le comportement best-effort demandé (section 10) exige de distinguer, pour un même appel, **trois issues distinctes par fichier** (succès, échec diagnosticable, doublon volontaire non fautif) — un simple retour `int` ne peut représenter cette information sans perte. Alternatives considérées et écartées :

- **Conserver `int` + état caché sur le Manager** (ex. un attribut `self.last_import_errors` rempli en effet de bord) : écarté — introduirait un état mutable implicite entre deux appels, contraire au style strictement fonctionnel déjà en place pour les méthodes de ce Manager (`create()`, `delete()`, `update()` retournent tous une valeur directement exploitable, jamais un effet de bord cascadé à lire séparément), et rendrait les tests plus fragiles (ordre d'appel implicite).
- **Lever une exception agrégée contenant le rapport partiel** : écarté — un import partiellement réussi n'est **pas** un cas exceptionnel au sens de ce codebase (`WorkspaceManagerError` reste réservée aux échecs qui invalident l'opération entière, ex. Mission 027) ; forcer un `try/except` dans l'UI pour un résultat par ailleurs normal et attendu casserait la cohérence des conventions déjà établies.
- **`ImportResult(added, failed)` sans champ `skipped` dédié** (version initiale de cette spécification) : rejetée sur demande explicite de l'architecte — sans champ dédié, un doublon ignoré n'est distinguable d'un succès que par soustraction (`len(paths) - added - len(failed)`), calcul implicite, sujet à erreur, et surtout **rien n'empêche visuellement de le confondre avec un échec** si un développeur futur lit `failed` sans lire aussi ce calcul. Le champ `skipped` explicite rend cette distinction structurellement impossible à rater.

`ImportResult` est donc la structure **minimale** nécessaire à ce que l'UX demandée (section 10) soit réalisable sans ambiguïté — pas un enrichissement spéculatif (pas de raison détaillée par fichier au-delà du message d'exception déjà porté par `WorkspaceStorageError`, pas de timestamp, pas de taille de fichier).

## 10. Gestion des erreurs — best-effort, UX des succès partiels

**Stratégie confirmée : best-effort, jamais fail-fast.** Continuité du comportement déjà implicite aujourd'hui (un doublon déjà présent n'empêche jamais les autres fichiers valides d'un même lot d'être importés) — étendue aux échecs de copie.

**Séquence par fichier source, dans l'ordre du lot** (orchestrée identiquement par `WorkspaceManager.add_images()`/`DatasetManager.add_images()`) :

1. Doublon exact déjà traité plus tôt dans ce même appel (section 8) → `skipped`, fichier suivant.
2. `effective_path = WorkspaceStorage.copy_into_workspace(Path(source), destination_folder, workspace_root)`. `WorkspaceStorageError` levée (source introuvable, permission refusée, disque plein, destination inaccessible) → `failed`, fichier suivant.
3. `effective_path` déjà enregistré comme `Image.file_path` existant dans la collection cible (section 6.2) → `skipped`, fichier suivant.
4. Sinon → `Image(image_id=str(uuid.uuid4()), file_path=str(effective_path))` ajoutée à une liste locale `to_add` (jamais persistée immédiatement).

**Garantie "jamais de `file_path` persisté pour une copie échouée"** : la collection Domain n'est étendue et `self._workspace_manager.save()` n'est appelé **qu'une seule fois, après la fin de la boucle**, uniquement si `to_add` est non vide — même principe "commit après succès" déjà établi par `WorkspaceManager.rename()` (Mission 027), appliqué ici à l'échelle de chaque fichier du lot plutôt qu'à l'opération globale.

### 10.1 UX — un seul rapport agrégé, jamais une série de boîtes de dialogue modales

`ImagesPage.import_images()`/`DatasetsPage.import_images()` affichent **une seule** `QMessageBox` en fin d'import, quel que soit le nombre de fichiers du lot — jamais une boîte par fichier échoué. Contenu déterminé par `ImportResult` :

- `added > 0`, `failed` vide → `QMessageBox.information` (comme aujourd'hui), ex. *"N image(s) importée(s)."*
- `added == 0`, `failed` vide, `skipped` non vide → `QMessageBox.information`, ex. *"Aucune nouvelle image importée (déjà présente(s) ou sélectionnée(s) en double)."* — reformulation du message existant, **jamais présenté comme un échec**.
- `failed` non vide (que `added`/`skipped` soient non nuls ou non) → `QMessageBox.warning` (pas `.critical` — cohérent avec le choix déjà établi en Mission 027 pour un problème actionnable/partiel plutôt qu'une erreur technique bloquante), listant : le nombre de succès, le nombre de doublons ignorés le cas échéant, et le **nom des fichiers en échec** (`Path(f).name` pour chacun, lisible sans ouvrir de dialogue supplémentaire) — un seul texte consolidé, une seule boîte, jamais une boucle de `QMessageBox` par fichier.

Le format exact du texte reste un détail d'implémentation (non figé rigidement ici), mais doit toujours permettre de distinguer visuellement les trois catégories et de nommer les fichiers en échec.

## 11. Audit exhaustif des appelants de `add_images()` — résultat

Recherche exhaustive (`grep -rn "\.add_images\("` sur tout le dépôt, hors `CHANGELOG.md`/`docs/`) exécutée avant toute décision sur le contrat de retour, conformément à la demande explicite de l'architecte.

### 11.1 Appelants de production (3, tous recensés)

| Appelant | Fichier:ligne | Utilise le retour ? | Impact |
|---|---|---|---|
| `ImagesPage.import_images()` | `src/ui/pages/images_page.py:85` | Oui — `duplicates = len(files) - added` | Adapté au nouveau contrat (section 10.1) |
| `DatasetsPage.import_images()` | `src/ui/pages/datasets_page.py:118` | Oui — même calcul | Adapté au nouveau contrat (section 10.1) |
| `InferencePage._on_accept_clicked()` (Accept) | `src/ui/pages/inference_page.py:314` | **Non** — appel pour effet de bord seul, retour jamais lu | Aucune adaptation de ce call site ; comportement fonctionnel préservé par le critère "déjà interne" (section 6.3) |

**Aucun autre appelant de production trouvé.** `GenerationManager`, `ComfyUIEngine`, `DashboardPage` (import déjà délégué à `ImagesPage.import_images()` depuis Mission 017) n'appellent jamais `add_images()` directement.

### 11.2 Appelants de test dépendant du retour `int` (audit exhaustif)

| Fichier | Nb. d'appels | Nature des chemins utilisés | Impact |
|---|---|---|---|
| `tests/integration/test_workspace_roundtrip.py` | 1 (ligne 84) | Fictifs, non existants (`"ref1.png"`, `"ref2.png"`) | Adapté — fichiers source réels requis (section 12.4) |
| `tests/integration/test_image_roundtrip.py` | 5 (lignes 182, 203, 206, 224-225) | Fictifs, non existants | Adapté — fichiers source réels requis (section 12.4) |
| `tests/integration/test_dataset_roundtrip.py` | 5 (lignes 94, 148, 156, 166, 243) | Fictifs, non existants | Adapté — fichiers source réels requis (section 12.4) |
| `tests/integration/test_images_page.py` | 9 (lignes 58, 125, 135, 145, 192, 204, 218, 228, 245) | Majoritairement réels (`Path(...).write_bytes(...)`/`_make_png()`), **3 exceptions** (lignes 204, 228, et le fichier corrompu de la ligne 218 est réel mais invalide en tant que PNG, pas manquant) | Voir section 11.3 |

### 11.3 Cas particulier — tests `test_images_page.py` simulant un fichier "manquant à l'import"

`test_missing_file_item_still_created_with_fallback_icon_and_user_role` (ligne 201) et `test_missing_file_gallery_item_still_opens_preview_and_supports_selection` (ligne 226) importent aujourd'hui un chemin qui **n'existe pas au moment de l'import** (`does_not_exist.png`, `gone.png`) et vérifient que `ImagesPage` affiche malgré tout une icône de repli. **Cette prémisse devient obsolète après Mission 028** : une source introuvable à l'import échoue désormais la copie (`failed`), aucune `Image` n'est créée — le scénario "élément de galerie pour un fichier jamais importable" ne peut structurellement plus se produire de cette façon.

**Le comportement réellement testé (icône de repli pour un fichier manquant) reste pertinent et doit être conservé**, mais reformulé selon un scénario déjà présent ailleurs dans ce même fichier : `test_missing_file_opens_dialog_without_mutating_domain` (ligne 100) importe un fichier **réel**, puis le supprime **après** import (`Path(self.image_path).unlink()`) — c'est le scénario correct pour "un fichier référencé devient manquant après coup", inchangé par cette mission (aucune re-vérification d'existence n'est faite après l'import). Les deux tests des lignes 201/226 seront réécrits selon ce même patron (import réel réussi, suppression du fichier **après**, assertions inchangées sur l'icône de repli) plutôt que supprimés — aucune perte de couverture.

`test_invalid_non_image_file_item_still_created_with_fallback_icon` (ligne 214) utilise un fichier réel mais au contenu invalide (pas un PNG valide) — la copie réussit normalement (la copie ne valide jamais le contenu, seulement l'existence/les droits), seul le rendu de la miniature échoue ensuite — **aucun changement nécessaire** pour ce test.

### 11.4 Conclusion de l'audit — propagation réelle mais bornée, pas disproportionnée architecturalement

**Aucune propagation architecturale** : aucune nouvelle abstraction, aucun nouveau Manager/Domain, aucun changement de couche — le changement reste strictement localisé aux deux méthodes `add_images()` et à leurs trois appelants de production directs.

**Propagation de fixtures de test réelle, mais bornée et mécanique** : 11 appels dans 3 fichiers de tests d'intégration (`test_workspace_roundtrip.py` ×1, `test_image_roundtrip.py` ×5, `test_dataset_roundtrip.py` ×5) utilisent aujourd'hui des chemins fictifs comme technique de fixture pour tester une logique orthogonale à la copie physique (dédoublonnage, ordre, indépendance des pools, stabilité des `image_id`) — ces tests doivent être adaptés pour utiliser des fichiers temporaires réels (section 12.4), sans changer l'intention de ce qu'ils vérifient. 2 tests supplémentaires dans `test_images_page.py` doivent être reformulés selon un patron déjà existant dans le même fichier (section 11.3), sans perte de couverture. **Confirmation demandée par l'architecte** : ce périmètre est jugé proportionné à ce que la fonctionnalité exige structurellement (on ne peut pas tester une copie réelle sans fichiers réels) — traité selon la même discipline "recherche préalable de mocks/fixtures obsolètes" déjà appliquée à chaque mission précédente, ici simplement plus étendue en surface.

**Tests explicitement non affectés** (vérifié, pas supposé) : les tests Domain purs de `test_image_roundtrip.py` qui construisent `Image`/`Workspace`/`Dataset` directement via leurs constructeurs/`from_dict()` sans jamais passer par `add_images()` (`test_image_domain_object_roundtrip_and_defaults`, `test_list_from_data_migrates_legacy_and_filters_invalid`, `test_list_from_data_filters_dicts_without_usable_file_path`, `test_workspace_migrates_legacy_images_without_loss`, `test_dataset_migrates_legacy_images_without_loss`, `test_workspace_and_dataset_roundtrip_preserves_image_id_new_format`) — strictement inchangés.

## 12. Périmètre IN

- `WorkspaceStorage.is_inside()` + `WorkspaceStorage.copy_into_workspace()` (nouvelles méthodes statiques) — court-circuit "déjà interne" (section 6), collision non destructive (section 7), nettoyage best-effort sur échec.
- `WorkspaceManager.add_images()` étendu : copie/réutilisation réelle vers `<workspace_root>/images/`, nouveau type `ImportResult(added, failed, skipped)` (section 9), best-effort (section 10), aucune persistance pour un fichier en échec.
- `DatasetManager.add_images()` étendu selon le même principe, vers `<workspace_root>/datasets/<dataset_id>/`.
- `ImagesPage.import_images()`/`DatasetsPage.import_images()` adaptés au nouveau contrat de retour, message unique agrégé (section 10.1).
- Rétrocompatibilité totale des références externes déjà persistées (section 13, inchangée depuis la version précédente).
- Vérification explicite, par test, de la compatibilité avec le remap de renommage Mission 027 (section 14, inchangée).
- Vérification explicite, par test, de la non-régression du flux Accept (`InferencePage`, section 6.3).
- Tests exhaustifs (section 17).
- Smoke test manuel réel (section 20).

## 13. Chemins — persistance inchangée pour cette mission

`Image.file_path` reste un simple `str`, persisté **absolu** — aucun changement de format de sérialisation (`Image.to_dict()`/`from_dict()` strictement inchangés). La conversion vers des chemins relatifs à `Workspace.root` appartient explicitement à la future Mission 029.

## 14. Rétrocompatibilité

Aucune migration rétroactive. Un `project.json` déjà existant, avec des `Image.file_path` pointant vers des emplacements externes, continue de se charger et de fonctionner exactement comme aujourd'hui — `Image.from_dict()`/`Image.list_from_data()` (`src/domain/image.py`) restent strictement inchangés.

## 15. Synergie Mission 027 — vérification du remap au renommage

Les nouvelles copies internes sont, par construction, des chemins sous `Workspace.root` — exactement la définition déjà utilisée par `WorkspaceManager.rename()` (Mission 027). **Aucune modification du code de `rename()`/`_build_renamed_payload()`/`_remap_path()` n'est nécessaire.** Un test dédié (section 17) le prouve plutôt que de le supposer.

## 16. Périmètre OUT (explicitement différé)

Models, Workflows, LoRA, checkpoints ; migration vers des chemins relatifs (Mission 029) ; déplacement d'un projet vers un autre disque ; migration rétroactive des anciennes références externes ; déduplication par hash de contenu (section 8) ; refonte générale de `WorkspaceStorage` ; synchronisation automatique avec le fichier source d'origine après import ; introduction d'un champ de rôle (`train`/`validation`) sur `Dataset` ou exploitation des dossiers `datasets/train`/`datasets/validation` (section 1) ; toute limite de taille/volume/format au-delà du filtre déjà existant du `QFileDialog` ; verrou filesystem exclusif pendant la résolution de collision (section 7) ; nettoyage/suppression des dossiers `datasets/train`/`datasets/validation` existants ; tout changement au flux Accept d'`InferencePage` au-delà de la préservation stricte de son comportement actuel (section 6.3).

## 17. Stratégie de tests

**Recherche préalable de mocks/fixtures à signature obsolète** avant tout lancement Qt — déjà exécutée pour l'essentiel par l'audit de la section 11, à revérifier au moment de l'implémentation.

### 17.1 Tests Infrastructure (`WorkspaceStorage`, nouveaux, dans `test_workspace_roundtrip.py`)

- `is_inside()` : chemin sous la racine (profondeur 1 et profondeur N) → `True` ; chemin hors racine → `False` ; la racine elle-même → `True` ; insensibilité à la casse Windows ; chemin inexistant (fichier supprimé entre-temps) → toujours résolu sans exception.
- `copy_into_workspace()` : résolution de collision (`photo.jpg` → `photo_1.jpg` → `photo_2.jpg`) ; création défensive du dossier de destination ; nettoyage best-effort d'un fichier partiel en cas d'échec simulé ; **source déjà sous `workspace_root` → retournée telle quelle, `shutil.copy2` jamais appelé** (vérifié par mock/spy sur `shutil.copy2`, pas seulement par le résultat) ; source déjà interne mais dans un sous-dossier différent de `destination_folder` (ex. `outputs/`) → toujours court-circuitée, jamais copiée vers `destination_folder`.

### 17.2 Tests `WorkspaceManager.add_images()` (`test_workspace_roundtrip.py`, nouvelle classe dédiée)

- Import d'une image externe → fichier physiquement copié sous `<root>/images/`, source intacte, `Image.file_path` = copie interne, `ImportResult.added == 1`.
- Collision de nom : deux fichiers externes de contenus différents, même nom → deux copies distinctes, aucun écrasement, `added == 2`.
- **Source déjà dans `<root>/images/`, jamais encore enregistrée** → aucune copie, `Image.file_path` = chemin déjà existant, `added == 1`, `shutil.copy2` jamais appelé.
- **Source déjà dans `<root>/images/`, déjà enregistrée comme `Image`** → `skipped == [chemin]`, aucune nouvelle `Image`, `added == 0`.
- **Source déjà interne mais ailleurs sous la racine** (ex. `<root>/outputs/generated.png`, jamais encore dans `Workspace.images`) → aucune copie, réutilisée telle quelle, `added == 1` (couvre le cas général au-delà d'Accept spécifiquement).
- Doublon exact dans le même lot (même chemin externe deux fois) → une seule copie, `skipped` contient l'occurrence ignorée, jamais `failed`.
- Deux fichiers distincts, même nom → `added == 2`, noms distincts sur disque (déjà couvert ci-dessus, reformulé pour clarté du contrat `ImportResult`).
- Import multiple avec échec partiel (un chemin source inexistant dans le lot) → `failed` contient ce chemin, `added` reflète uniquement les succès, aucune `Image` créée pour l'échec.
- Absence de persistance pour une copie échouée : `project.json` relu après un import contenant un échec ne contient que les entrées effectivement copiées/réutilisées avec succès.
- Erreur de copie simulée (`shutil.copy2` mocké pour lever `OSError`) → `failed`, fichier partiel nettoyé.
- Ancien projet avec un `Image.file_path` externe préexistant (fixture `project.json` écrite manuellement, format pré-Mission-028) → chargé sans exception, valeur strictement inchangée, aucune copie tentée à la lecture.
- **Renommage Mission 027 après import interne** : import externe → copie sous `<root>/images/` → `WorkspaceManager.rename()` → `Image.file_path` remappé sous le nouveau `root`, fichier physiquement présent au nouvel emplacement.
- **Fermeture/réouverture après import** : import → `save()` → `close()` → nouveau `WorkspaceManager` → `open()` → `Image.file_path` relu à l'identique, fichier physique présent.

### 17.3 Tests `DatasetManager.add_images()` (`test_dataset_roundtrip.py`, étendu)

Mêmes cas que 17.2, adaptés à `<root>/datasets/<dataset_id>/` :
- copie réelle, source intacte, collision de nom, doublon de lot, source déjà interne (déjà enregistrée / pas encore enregistrée), import multiple avec échec partiel, absence de persistance sur échec ;
- **deux Datasets distincts important chacun un fichier de même nom** → aucune collision croisée (dossiers séparés par `dataset_id`) ;
- ancien projet avec un `Dataset.images[].file_path` externe préexistant → chargé sans exception ;
- renommage Mission 027 après import interne dans un Dataset ;
- fermeture/réouverture après import dans un Dataset.

### 17.4 Test dédié — non-régression du flux Accept (`InferencePage`)

Nouveau test (`tests/integration/test_inference_page.py`, étendu) : simuler un Accept réel (chemin `pending_path` sous `<root>/outputs/`), vérifier après appel que `Workspace.images` contient une `Image` dont `file_path` est **exactement** le chemin `outputs/...` d'origine (aucune copie vers `images/`, `shutil.copy2` jamais appelé — vérifié par spy) — preuve directe de la non-régression identifiée en section 6.3, pas une simple absence d'erreur.

### 17.5 Adaptation des tests existants à fixtures fictives (section 11.2)

- `test_workspace_roundtrip.py` (`test_full_create_import_save_close_reopen_cycle`) : chemins `"ref1.png"`/`"ref2.png"` remplacés par deux fichiers temporaires réels créés dans `setUp`/le test ; assertions sur `file_path` mises à jour pour vérifier le chemin de la copie interne (`<folder>/images/ref1.png` etc.) plutôt que le nom fictif d'origine — la logique testée (persistance, cycle fermeture/réouverture, `ImagesPage` mise à jour) reste inchangée dans son intention.
- `test_image_roundtrip.py` (5 tests Manager listés section 11.2) : mêmes fichiers temporaires réels, assertions sur `file_path` mises à jour vers le chemin de destination attendu (déterministe, section 7) plutôt que le nom source fictif — les assertions de fond (stabilité des `image_id`, dédoublonnage, indépendance des pools) restent identiques dans leur intention et leur couverture.
- `test_dataset_roundtrip.py` (5 tests listés section 11.2) : même traitement.
- `test_images_page.py` : les deux tests "fichier manquant à l'import" reformulés selon le patron "supprimé après import" (section 11.3) ; les 9 autres appels déjà réels ou déjà conformes ne nécessitent qu'une vérification de non-régression, aucune réécriture de fond.

Nombre exact de tests final à confirmer après implémentation (452 + N).

## 18. Fichiers concernés (aucun modifié dans cette passe — liste prévisionnelle)

- `src/infrastructure/storage/workspace_storage.py` — `is_inside()`, `copy_into_workspace()` ajoutés.
- `src/managers/workspace_manager.py` — `ImportResult` (nouveau type), `add_images()` étendu.
- `src/managers/dataset_manager.py` — `add_images()` étendu, `ImportResult` importé.
- `src/ui/pages/images_page.py` — `import_images()` adapté au nouveau contrat de retour, message unique agrégé.
- `src/ui/pages/datasets_page.py` — `import_images()` adapté, même principe.
- `tests/integration/test_workspace_roundtrip.py` — nouvelle classe dédiée `WorkspaceAddImagesCopyTest` (ou équivalent) + tests unitaires `is_inside()`/`copy_into_workspace()` + adaptation de `test_full_create_import_save_close_reopen_cycle`.
- `tests/integration/test_dataset_roundtrip.py` — extension + adaptation des 5 tests recensés.
- `tests/integration/test_image_roundtrip.py` — adaptation des 5 tests recensés.
- `tests/integration/test_images_page.py` — reformulation ciblée de 2 tests (section 11.3), aucun changement pour les 7 autres appels.
- `tests/integration/test_inference_page.py` — nouveau test de non-régression Accept (section 17.4).
- `docs/missions/MISSION_028.md` — cette spécification, puis complétée avec les résultats réels à la clôture.
- `docs/PROJECT_CONTEXT.md` / `CHANGELOG.md` — **non modifiés dans cette passe**, mis à jour uniquement à la clôture réelle de la mission.

Aucun fichier Domain (`src/domain/*.py`) modifié.

## 19. Risques résiduels

- **Volume de copie pour un import multiple important** : opération séquentielle, synchrone — aucun mécanisme de progression/asynchronisme prévu, cohérent avec le caractère déjà synchrone d'`add_images()` aujourd'hui.
- **Espace disque doublé** pour les fichiers réellement externes copiés (le fichier source n'est jamais supprimé, par principe produit) — risque connu et accepté.
- **Dossier `images/`/`datasets/<dataset_id>/` verrouillé par un processus externe** (même famille de risque que Mission 027 section 17) : la copie échoue proprement (`failed`), sans corrompre l'état existant — pas de traitement UX dédié spécifique à ce cas précis dans cette mission.
- **`datasets/train`/`datasets/validation` restent du scaffolding mort** après cette mission — non aggravé ni résolu.
- **Critère "déjà interne" large (section 6.1)** : un fichier physiquement présent n'importe où sous `Workspace.root` (pas seulement dans le dossier de destination visé) est réutilisé sans copie, y compris depuis un sous-dossier "inattendu" pour ce type de ressource (ex. une image de `outputs/` réimportée volontairement dans un Dataset) — comportement jugé cohérent avec le modèle d'ownership déjà existant (Mission 011, pools indépendants sans exclusivité), accepté comme conséquence du critère large plutôt que traité comme une anomalie.
- **Propagation de fixtures de tests** (section 11.4) : 11 tests existants + 2 reformulations, bornée et mécanique, confirmée proportionnée par l'audit exhaustif — à exécuter avec soin pour ne perdre aucune assertion substantielle (même discipline que chaque mission précédente).

## 20. Critères d'acceptation

- Suite de tests complète verte, nombre exact confirmé, aucune régression sur les comportements non concernés par cette mission — **y compris le flux Accept d'`InferencePage`, vérifié par test dédié (section 17.4), pas seulement supposé inchangé.**
- `git diff --stat` confirmant exactement le périmètre de fichiers de la section 18.
- Une image importée depuis `ImagesPage` est physiquement copiée sous `<workspace_root>/images/`, le fichier source reste intact.
- Une image importée depuis `DatasetsPage` est physiquement copiée sous `<workspace_root>/datasets/<dataset_id>/`, même garantie sur la source.
- Aucune collision de nom ne provoque jamais un écrasement silencieux.
- **Une source déjà interne au Workspace n'est jamais recopiée, jamais renommée artificiellement (`photo_1.jpg`), et n'est jamais tentée en copie vers elle-même (`shutil.copy2` jamais appelé pour ce cas).**
- **Un doublon volontairement ignoré (lot ou déjà interne) apparaît toujours dans `skipped`, jamais dans `failed`.**
- Aucun `Image.file_path` n'est jamais persisté pour une copie ayant échoué.
- Un `project.json` pré-Mission-028 avec des références externes se charge et fonctionne sans exception.
- Un renommage de projet (Mission 027) après un import interne remappe correctement le nouveau chemin, fichier physique inclus.
- Smoke test manuel réel réalisé et documenté (section 21).

## 21. Protocole de smoke test manuel réel

**Révisé après le premier smoke test réel (section 22)** — intègre désormais la vérification du dialogue de collision et de la création de Dataset sans sélection manuelle de personnage. À exécuter par l'architecte, sur un projet temporaire réel (Windows), après implémentation et suite automatisée verte :

1. Préparer une image source **hors du projet** (ex. `Téléchargements`), noter son chemin exact.
2. Créer ou ouvrir un projet temporaire.
3. Dans `Images`, cliquer "Importer des images", sélectionner ce fichier.
4. Vérifier physiquement (Explorateur Windows) que le fichier a bien été copié sous `<workspace>\images\`.
5. **Déplacer ou supprimer le fichier source original** (hors d'AI Studio Toolkit).
6. Confirmer que l'image reste disponible et affichée normalement dans `ImagesPage`.
7. **Réimporter, via "Importer des images", ce même fichier directement depuis `<workspace>\images\`** (naviguer dedans dans la boîte de dialogue de sélection) — confirmer qu'aucun dialogue de collision ne s'affiche (ce n'est pas une collision de nom, section 22.1), qu'aucun nouveau fichier `photo_1.jpg` n'apparaît sur disque, et que le message affiché indique une image déjà présente (pas un échec).
8. **Préparer une seconde image externe portant le même nom que l'image déjà importée à l'étape 3** (contenu différent) et l'importer — confirmer qu'**un dialogue unique** apparaît, proposant un nom alternatif éditable (ex. `photo_1.jpg`) et une case "Ignorer" ; valider le renommage proposé sans le modifier — confirmer que le fichier est copié sous ce nom, sans écraser l'original.
9. Répéter avec un troisième fichier de même nom, mais cette fois cocher "Ignorer" — confirmer qu'aucun fichier supplémentaire n'est copié et que le message final indique une image ignorée, jamais un échec.
10. Importer en une seule fois deux fichiers externes différents partageant eux-mêmes un nom entre eux (aucun des deux déjà présent) — confirmer qu'un seul dialogue apparaît, listant bien les deux, plutôt qu'une suite de boîtes de dialogue.
11. Menu **Fichier → Renommer le projet…**, renommer le projet (fermer au préalable toute fenêtre de l'Explorateur Windows ouverte dans le dossier du projet ou ses sous-dossiers — comportement Mission 027 confirmé, section 22.3).
12. Confirmer que toutes les images importées restent accessibles et affichées après le renommage.
13. Fermer puis rouvrir le projet — confirmer que toutes les images restent présentes et affichées à l'identique.
14. **Aller directement dans `Datasets` sans être jamais passé par `Characters`** (aucune sélection manuelle de personnage) : cliquer "Nouveau dataset" — confirmer la création immédiate, sans message d'erreur.
15. Dans ce Dataset, "Importer des images" avec une image externe — confirmer la copie physique sous `<workspace>\datasets\<dataset_id>\`.
16. Fermer puis rouvrir à nouveau le projet — confirmer que le Dataset et son image restent présents, et que "Nouveau dataset" reste utilisable sans sélection manuelle.
17. **Lancer une génération réelle dans `Inference`, l'Accepter** — confirmer dans `Images` que l'image acceptée apparaît avec son chemin habituel sous `outputs\` (jamais dupliquée sous `images\`, jamais de dialogue de collision) — vérification directe de la non-régression du flux Accept (section 6.3).

## 22. Premier smoke test réel — FAIL, deux corrections apportées

**Résultat** : les imports simples fonctionnaient (copie physique réelle confirmée), mais deux comportements fonctionnels ont été jugés non conformes à l'UX/l'architecture attendues. Mission 028 est restée ouverte, aucune clôture documentaire n'a eu lieu avant cette révision.

### 22.1 Collision de nom — UX non souhaitée

**Constat** : le suffixage automatique et silencieux (`photo.jpg` → `photo_1.jpg`) fonctionnait comme prévu par la spécification initiale, mais l'architecte a jugé, à l'usage réel, que ce comportement ne devait pas rester **silencieux** — l'utilisateur doit être informé d'une collision et choisir explicitement de renommer ou d'ignorer.

**Décision retenue** : la primitive Infrastructure non destructive est **conservée intégralement** (`WorkspaceStorage.resolve_collision_free_name()`, ex-`_resolve_collision_free_name()`, désormais publique) — elle reste le filet de sécurité par défaut pour tout appelant qui ne passe pas par le nouveau flux UI (tests, usage programmatique). Seul le flux **piloté par l'UI** (`ImagesPage`/`DatasetsPage`) change :

1. **Prévisualisation, sans I/O** : nouvelle méthode `preview_collisions(paths) -> list[CollisionInfo]` (`WorkspaceManager`/`DatasetManager`), qui prédit, avant tout import réel, quels fichiers colliseraient avec un nom déjà présent dans le dossier de destination — y compris en tenant compte des autres fichiers du même lot pas encore physiquement copiés au moment de la prévisualisation (`also_avoid`, sans quoi deux fichiers neufs de même nom dans le même lot auraient tous deux semblé libres à la prévisualisation, avant que le second ne soit quand même auto-suffixé silencieusement à l'exécution réelle).
2. **Un seul dialogue, jamais une série** : si `preview_collisions()` retourne au moins une collision, `ImportCollisionDialog` (nouveau, `src/ui/dialogs/import_collision_dialog.py`) affiche **une seule fois** la liste complète des fichiers concernés, chacun avec un nom proposé (pré-rempli avec le même nom collision-safe que l'automatique aurait choisi, éditable) et une case à cocher "Ignorer cet import". Un seul bouton OK valide l'ensemble du lot en une fois.
3. **Application des décisions** : les fichiers cochés "Ignorer" sont retirés du lot avant l'appel à `add_images()` et comptés en `skipped` (jamais en `failed`) dans le message final. Les renommages choisis sont transmis via un nouveau paramètre `add_images(paths, renames: dict[str, str] = None)` — `WorkspaceStorage.copy_into_workspace()` reçoit alors un `target_name` explicite (revérifié pour l'existence juste avant la copie, jamais écrasé même dans ce cas) plutôt que de recalculer un nom automatiquement.
4. **Annulation du dialogue** : `Cancel` (ou fermeture) annule l'import dans son intégralité — aucun fichier, même non conflictuel, n'est importé. Choix le plus simple et le plus prévisible, cohérent avec le comportement `Cancel` déjà établi ailleurs dans ce projet (`RenameProjectDialog`, `NewProjectDialog`).

**Trois cas vérifiés distinctement, par test** (`preview_collisions()`) :
- **Même source externe réimportée** : reconnue comme une collision de nom réelle (aucun dédoublonnage par contenu, décision déjà actée section 8) → passe par le dialogue.
- **Source déjà exactement dans `Workspace/images/` (ou le dossier du Dataset)** : jamais une collision de nom — court-circuitée en amont par `WorkspaceStorage.is_inside()` (section 6), ne montre jamais le dialogue.
- **Deux fichiers différents, même nom** : collision réelle → passe par le dialogue, y compris lorsque les deux fichiers sont neufs et proviennent du même lot (`also_avoid`).

### 22.2 Dataset — régression liée au Character principal

**Cause exacte, confirmée par diagnostic read-only** : `DatasetManager` (`datasets` property, `create()`, `is_referenced_by_training()`, `delete()`) lisait `CharacterManager.active_character` — jamais `principal_character`. Or depuis Mission 026, `CharactersPage` ne rappelle plus jamais `CharacterManager.select()` : elle se contente de **lire** `principal_character`/`principal_character_id` pour peupler la fiche, sans jamais réaffecter `active_character_id`. Combiné au fait que `active_character_id` est explicitement réinitialisé à `None` sur `WORKSPACE_OPENED` (et non recréé automatiquement — la création automatique du personnage principal, `_ensure_default_character()`, ne se déclenche que sur `WORKSPACE_CREATED`, décision Mission 026 section 9.4), `active_character_id` reste `None` pendant toute la session dès qu'un Workspace **existant** est rouvert. Résultat : `DatasetManager.create()` retournait toujours `None` (« Aucun personnage actif »), sans qu'aucune action utilisateur ne puisse corriger cet état — la liste de sélection multi-personnage étant masquée depuis Mission 026.

`LoRAManager`/`PromptManager`/`TrainingManager` présentent exactement le même schéma (`self._character_manager.active_character`, jamais `principal_character`) — recherche exhaustive confirmée (`grep -rn "active_character\b" src/managers/`). **Ce n'est pas corrigé dans cette passe** : strictement hors périmètre de Mission 028 (Import Images), signalé ici pour mémoire et à traiter par une décision explicite séparée de l'architecte (correctif identique, un seul remplacement `active_character` → `principal_character` par fichier, sans risque de régression pour les mêmes raisons que ci-dessous).

**Solution retenue** : les quatre usages de `DatasetManager` remplacés par `CharacterManager.principal_character` — exactement le mécanisme déjà validé par Mission 026 pour `CharactersPage` (préfère `active_character` quand une sélection multi-personnage explicite est réellement en cours — préservé à l'identique pour tous les tests multi-personnage existants, qui appellent tous `select()` explicitement — sinon retombe sur le premier personnage du Workspace, toujours le personnage principal auto-créé). Aucune modification de `CharacterManager`, aucune réapparition de la liste multi-personnage, aucune contrainte de cardinalité ajoutée.

**Comportement cible obtenu** : dans un Workspace possédant son personnage principal (auto-créé ou existant), `Datasets → Nouveau dataset` fonctionne immédiatement, sans aucune sélection manuelle, y compris après un cycle fermeture/réouverture — vérifié par un test de régression dédié reproduisant exactement la séquence réelle rapportée (`DatasetCreationWithoutManualCharacterSelectionTest`, `test_dataset_roundtrip.py`) : création puis fermeture puis réouverture du Workspace (sans jamais appeler `select()`), création du Dataset, import d'images, persistance vérifiée après un second cycle fermeture/réouverture.

### 22.3 Renommage de projet pendant le smoke test — comportement Mission 027 confirmé, non rouvert

Le blocage occasionnel du renommage malgré l'absence apparente de fenêtre Explorateur visible reste cohérent avec le diagnostic Sysinternals déjà établi en Mission 027 (`explorer.exe` peut conserver des handles sur des sous-dossiers du Workspace au-delà de ce qui est visuellement évident) — le message UX Mission 027 fonctionne correctement. **Mission 027 n'est pas rouverte.** Pour le smoke test Mission 028, fermer complètement les fenêtres de l'Explorateur avant tout renommage reste la procédure acceptée.

### 22.4 Fichiers modifiés pour ces corrections

- `src/infrastructure/storage/workspace_storage.py` — `_resolve_collision_free_name()` renommée `resolve_collision_free_name()` (publique), paramètre `also_avoid` ajouté ; `copy_into_workspace()` gagne un paramètre `target_name` optionnel.
- `src/managers/workspace_manager.py` — nouveau type `CollisionInfo`, nouvelle méthode `preview_collisions()`, `add_images()` gagne un paramètre `renames`.
- `src/managers/dataset_manager.py` — même extension (`preview_collisions()`, `renames`) ; les quatre usages de `active_character` remplacés par `principal_character`.
- `src/ui/dialogs/import_collision_dialog.py` — nouveau fichier, `ImportCollisionDialog`.
- `src/ui/pages/images_page.py` / `src/ui/pages/datasets_page.py` — `import_images()` appelle désormais `preview_collisions()` puis, si nécessaire, `ImportCollisionDialog`, avant `add_images()` ; message de fin d'import mis à jour (message d'avertissement pour "Aucun personnage" reformulé dans `datasets_page.py`, la notion de "sélection" n'ayant plus de sens côté utilisateur).
- Tests : `tests/integration/test_workspace_roundtrip.py`, `tests/integration/test_dataset_roundtrip.py`, `tests/integration/test_images_page.py` étendus (voir section 22.5).

### 22.5 Tests ajoutés

- `preview_collisions()`/`renames` : source déjà internée (aucune collision), même source réimportée (collision réelle), deux fichiers différents même nom (collision réelle, y compris intra-lot via `also_avoid`), doublon exact intra-lot (ignoré, jamais une collision), renommage appliqué verbatim, nom demandé déjà pris entre-temps → `failed` (jamais un écrasement), comportement automatique silencieux toujours disponible hors flux UI — `WorkspaceManagerAddImagesCopyTest`/nouveaux tests dédiés (`test_workspace_roundtrip.py`), `DatasetManagerAddImagesCopyTest` (`test_dataset_roundtrip.py`).
- UI (`ImagesPageCollisionDialogTest`, `test_images_page.py` ; `DatasetsPageCollisionDialogTest`, `test_dataset_roundtrip.py`) : aucun dialogue si aucune collision ; un seul dialogue pour plusieurs collisions ; `Cancel` annule l'import entier ; décision "renommer" appliquée verbatim ; décision "ignorer" jamais comptée comme un échec.
- Régression Character/Dataset (`DatasetCreationWithoutManualCharacterSelectionTest`, `test_dataset_roundtrip.py`) : séquence exacte create → close → open (sans `select()`) → `Nouveau dataset` réussi → import réussi → persistance après un second cycle fermeture/réouverture.

### 22.6 Résultat

**510/510 tests verts** (487 précédents + 23 nets nouveaux). Aucune régression sur le comportement automatique par défaut (toujours utilisé par tout appelant hors UI, y compris tous les tests Infrastructure/Manager existants).

## 23. Deuxième smoke test réel — PASS

Exécuté par l'architecte après les deux corrections de la section 22, suite automatisée 510/510 confirmée avant le test. Résultat : **PASS**. Vérifications utilisateur confirmées, conformes au protocole révisé de la section 21 :

- les images externes sont réellement copiées dans le Workspace (`<workspace>\images\`) ;
- elles restent disponibles indépendamment de leur fichier source externe (déplacement/suppression de la source sans effet sur AI Studio Toolkit) ;
- la gestion des collisions fonctionne avec le nouveau dialogue (`ImportCollisionDialog`), affiché une seule fois même pour plusieurs collisions simultanées ;
- l'utilisateur peut renommer (nom proposé éditable) ou ignorer une collision, sans qu'un import ignoré ne soit jamais présenté comme un échec ;
- la création d'un Dataset fonctionne désormais sans sélection manuelle d'un Character (`DatasetManager` → `principal_character`) ;
- l'import d'images dans un Dataset fonctionne ;
- les images du Dataset sont physiquement stockées sous `datasets/<dataset_id>/` ;
- le comportement est cohérent avec le Character principal introduit par Mission 026 (aucune réapparition de la liste/sélection multi-personnage) ;
- les vérifications de renommage de projet et de persistance (fermeture/réouverture) prévues au protocole sont validées, y compris pour les images de Dataset ;
- le flux Inference/Accept ne provoque toujours aucune copie artificielle dans `images/` (confirmé visuellement en plus de la couverture automatisée dédiée, section 17.4/22.4).

Le blocage occasionnel de renommage rencontré pendant ce second smoke test reste cohérent avec le comportement Windows déjà diagnostiqué et traité par Mission 027 (`explorer.exe` retenant des handles sur des sous-dossiers du Workspace) — voir section 22.3, non rouvert.

## Commit correspondant

Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé ici — cette section sera complétée après la clôture Git réelle de la mission.

## État final

**Implémentation, suite automatisée (510/510) et smoke test manuel réel complet validés — PASS**, après un premier smoke test réel ayant révélé puis vu corriger deux problèmes fonctionnels (section 22) : gestion interactive des collisions de nom (`ImportCollisionDialog`, jamais de suffixage automatique silencieux côté UI) et correction de la régression `DatasetManager` → `CharacterManager.principal_character` (création de Dataset possible sans sélection manuelle de personnage, cohérente avec l'orientation Character principal de Mission 026). Deux besoins futurs distincts ont été identifiés et enregistrés dans `docs/PROJECT_CONTEXT.md` sans être implémentés : alimentation d'un Dataset depuis la galerie Images, et la dette de cohérence `active_character`/`principal_character` affectant encore `LoRAManager`/`PromptManager`/`TrainingManager`. **Clôture documentaire fonctionnelle effectuée** (`docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`, ce document). **Clôture Git non encore réalisée** — en attente d'autorisation explicite de l'architecte.
