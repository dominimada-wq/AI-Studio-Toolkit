# Mission 019 — Images Gallery / Thumbnails

Source : audit read-only préalable (Mission 019 Phase 1, état Git, code réel `src/ui/pages/images_page.py`/`src/ui/dialogs/image_preview_dialog.py`/`tests/integration/test_images_page.py`), spécification validée par l'architecte, implémentation réalisée et vérifiée par exécution réelle de la suite de tests complète. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur dans ce document tant que la clôture Git n'a pas eu lieu.

## Contexte

`ImagesPage` (`src/ui/pages/images_page.py`) affiche `Workspace.images` depuis Mission 011 sous forme de `QListWidget` en mode texte : chaque `QListWidgetItem` porte le `file_path` complet comme unique texte visible (`self.list_widget.addItem(image["file_path"])`). Mission 015 a ajouté la consultation agrandie (`ImagePreviewDialog`, double-clic ou bouton "Voir en grand"), sans modifier cette représentation. Ce besoin de galerie visuelle est identifié comme réel depuis l'audit préalable de Mission 015 (voir `docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés par l'usage réel") et confirmé par l'audit Mission 019 (Candidat principal retenu).

## Problème actuel

Une liste de chemins de fichiers bruts n'offre aucune prévisualisation visuelle — l'utilisateur ne peut identifier une image qu'en lisant son chemin complet, ce qui est insuffisant à l'usage réel dès qu'un Workspace contient plusieurs images. `item.text()` est aujourd'hui l'unique source du `file_path`, utilisée directement par `_on_item_double_clicked`/`_on_enlarge_clicked` — un couplage entre représentation visuelle et donnée fonctionnelle qui empêche toute évolution du texte affiché sans casser le comportement.

## Objectif

Transformer `ImagesPage` en galerie visuelle avec miniatures, en conservant strictement le comportement fonctionnel existant (import, sélection, bouton d'agrandissement, double-clic, `ImagePreviewDialog`, aucune mutation Domain supplémentaire), sans introduire d'architecture disproportionnée par rapport au besoin.

## Périmètre

**In scope**
- Passage de `self.list_widget` en `QListWidget.IconMode`.
- Un seul `QListWidgetItem` par image (inchangé), avec :
  - `item.setData(Qt.UserRole, file_path)` comme donnée fiable ;
  - `item.setText(Path(file_path).name)` comme label visible ;
  - `item.setToolTip(file_path)` comme chemin complet consultable ;
  - `item.setIcon(QIcon(...))` — miniature générée à partir d'un `QPixmap` redimensionné (~128×128, ratio conservé, transformation lissée), ou icône de repli déterministe si `QPixmap(file_path).isNull()`.
- Adaptation de `_on_item_double_clicked`/`_on_enlarge_clicked` pour lire `item.data(Qt.UserRole)` au lieu de `item.text()`.
- Configuration raisonnable du `QListWidget` (`iconSize`, `gridSize`, `setResizeMode(Adjust)`, `setMovement(Static)`, `setWordWrap(True)`).
- Extension de `tests/integration/test_images_page.py`.

**Out of scope** (voir section dédiée en fin de document)

## Représentation des items

Un item = une image = un seul `QListWidgetItem`, comme aujourd'hui. Aucune structure Domain nouvelle, aucun modèle/vue séparé (`QListView`+`QAbstractListModel` explicitement écarté par l'architecte — hors proportion avec le besoin).

## Décision `Qt.UserRole`

Le `file_path` complet devient une donnée attachée à l'item (`Qt.UserRole`), indépendante du texte affiché. C'est la seule source utilisée par toute action UI (double-clic, bouton "Voir en grand") — `item.text()` n'est plus jamais lu comme donnée fonctionnelle, uniquement comme label de présentation (nom de fichier court).

## Stratégie de miniatures

1. Charger `QPixmap(file_path)`.
2. Vérifier `.isNull()`.
3. Si valide : produire un pixmap redimensionné à la taille de miniature (~128×128) via `.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`, puis construire `QIcon` à partir de ce pixmap réduit — jamais un `QIcon` construit directement sur le pixmap pleine résolution (empreinte mémoire non maîtrisée sinon).
4. Chaque miniature est calculée à la reconstruction de la liste (`update_images()`), aucune mise en cache, aucun chargement différé — cohérent avec la taille actuelle des Workspaces réels, pas de besoin démontré pour une optimisation supplémentaire.

## Gestion des fichiers invalides

Réutilisation du même test que `ImagePreviewDialog` (`QPixmap(file_path).isNull()`). Si invalide (fichier manquant ou illisible) :
- l'item est tout de même créé et conservé dans la galerie (jamais omis) ;
- une icône de repli déterministe est utilisée (élément Qt standard ou pixmap généré en mémoire, aucun asset externe ajouté) ;
- `Qt.UserRole` et le tooltip restent renseignés avec le `file_path` d'origine ;
- double-clic/agrandissement restent actifs et ouvrent `ImagePreviewDialog`, qui affiche alors son message `UNAVAILABLE_MESSAGE` déjà existant (Mission 015, inchangé).

Aucune vérification d'existence de fichier séparée n'est ajoutée : `QPixmap.isNull()` couvre à la fois "fichier manquant" et "fichier illisible" en un seul test, comme le fait déjà `ImagePreviewDialog`.

## Architecture retenue

`ImagesPage` reste une vue UI pure, sans nouvelle dépendance Manager/Domain. `QListWidget` conservé (pas de remplacement par `QListView`/modèle custom/grille custom). Flux d'import inchangé (`QFileDialog → WorkspaceManager.add_images() → WORKSPACE_SAVED → update_images()`). `ImagePreviewDialog` non modifié. Aucun nouveau Domain (`Image` reste `image_id`/`file_path`, pas de champ `thumbnail`), aucun nouveau Manager/Service/Engine.

## Tests

Extension de `tests/integration/test_images_page.py` (fichier existant, pas de nouveau fichier) :
1. `ImagesPage` utilise `QListWidget.IconMode` (`self.page.list_widget.viewMode() == QListWidget.IconMode`).
2. Image valide : item présent, icône non nulle, `item.text()` == nom de fichier court, `item.toolTip()` == chemin complet, `item.data(Qt.UserRole)` == chemin complet.
3. Fichier manquant : aucune exception à la construction de la liste, item toujours créé, icône de repli présente (non nulle), `Qt.UserRole` conservé.
4. Fichier invalide/non-image (contenu non-image) : même comportement que fichier manquant.
5. Double-clic : `ImagePreviewDialog` reçoit toujours le chemin complet correct, lu depuis `Qt.UserRole`.
6. Bouton "Voir en grand" : idem, chemin complet correct depuis `Qt.UserRole`.
7. Sélection : activation/désactivation du bouton inchangée en `IconMode` (réutilisation des tests existants, adaptés si nécessaire).
8. Plusieurs images : tous les items présents, chacun avec son propre `Qt.UserRole` distinct.

Réutilisation maximale des tests déjà existants (aucun ne dépend de `item.text()` comme donnée fonctionnelle — confirmé par audit préalable) ; adaptation plutôt que duplication.

### Résultats réels

**Tests existants conservés sans modification (`test_images_page.py`)** : `test_enlarge_button_disabled_without_selection`, `test_enlarge_button_enabled_once_an_item_is_selected`, `test_enlarge_button_opens_the_selected_file_path`, `test_double_click_opens_the_same_file_path`, `test_enlarge_button_with_no_selection_is_a_no_op`, `test_missing_file_opens_dialog_without_mutating_domain`, `test_refresh_clears_previous_selection_and_disables_button`, `test_refresh_with_no_prior_selection_leaves_button_disabled`, `test_selecting_again_after_refresh_re_enables_the_button`, `test_enlarge_button_opened_twice_in_a_row_opens_dialog_each_time`, `test_consultation_never_calls_add_images_or_save` — tous verts sans adaptation, confirmant qu'aucun ne dépendait de `item.text()` comme donnée fonctionnelle.

**Nouveaux tests ajoutés (6, `test_images_page.py`)** :
- `test_list_widget_uses_icon_mode` — `viewMode() == QListWidget.IconMode`.
- `test_valid_image_item_has_icon_short_label_tooltip_and_user_role` — vraie image PNG générée (`_make_png`, même pattern que `test_image_preview_dialog.py`) : icône non nulle, `item.text() == "real.png"`, `item.toolTip() == chemin complet`, `item.data(Qt.UserRole) == chemin complet`.
- `test_missing_file_item_still_created_with_fallback_icon_and_user_role` — fichier jamais créé sur disque : item quand même présent, icône de repli non nulle, `Qt.UserRole`/tooltip corrects.
- `test_invalid_non_image_file_item_still_created_with_fallback_icon` — fichier avec contenu non-image : même comportement de repli.
- `test_missing_file_gallery_item_still_opens_preview_and_supports_selection` — un item représentant un fichier manquant reste sélectionnable et ouvre bien `ImagePreviewDialog` avec le chemin complet correct.
- `test_multiple_images_each_item_has_its_own_user_role` — plusieurs images (dont des vraies images générées), chacune avec un `Qt.UserRole` distinct et correct.

**Adaptation nécessaire hors `test_images_page.py`, directement imposée par Mission 019** : `tests/integration/test_inference_page.py::_images_page_paths()` (helper privé de test, utilisé par 4 tests vérifiant qu'une image générée/acceptée apparaît bien dans `ImagesPage`) lisait `item.text()` en le comparant à un chemin complet — hypothèse valide avant Mission 019 uniquement. Avec le changement de représentation (`item.text()` devenu le nom court, `Qt.UserRole` devenu la source du chemin complet), ce helper a été migré vers `item.data(Qt.UserRole)` (import `Qt` ajouté). **Ce n'est pas une modification du comportement Inference** : `InferencePage`, `GenerationManager`, `ComfyUIEngine`, l'EventBus et le flux Accept/Reject/Regenerate restent strictement inchangés — seule l'assertion de test lit désormais la donnée fiable au lieu du texte de présentation, conformément à la nouvelle représentation introduite par cette mission.

**Résultat `test_images_page.py` seul** : `Ran 17 tests in 0.745s — OK` (11 tests précédents inchangés + 6 nouveaux).

**Résultat `test_inference_page.py` après correction du helper** : `Ran 37 tests in 69.536s — OK` (37 tests inchangés en nombre, 1 seul helper adapté).

**Résultat suite complète** : `Ran 240 tests in 74.581s — OK` (234 tests précédents + 6 nouveaux, aucun test supprimé, aucune régression).

## Limites connues

- Pas de cache de miniatures, pas de chargement différé/asynchrone : chaque `update_images()` recharge et redimensionne tous les `QPixmap` en mémoire — acceptable pour la taille actuelle des Workspaces réels, dégraderait avec plusieurs centaines d'images (non mesuré, non démontré comme besoin réel à ce stade).
- Icône de repli volontairement simple (élément Qt standard ou pixmap généré en mémoire), aucun design dédié.

## Critères d'acceptation — état final

- `ImagesPage` utilise `QListWidget.IconMode`, `QListWidget` non remplacé : ✅.
- Chaque image reste représentée par un seul `QListWidgetItem` : ✅.
- `Qt.UserRole` porte le `file_path` complet, seule source utilisée par les actions UI (`_on_item_double_clicked`/`_on_enlarge_clicked`) : ✅.
- Label visible = nom de fichier court (`Path(file_path).name`), tooltip = chemin complet : ✅.
- Miniature 128×128 (`iconSize`), `gridSize` 150×170, ratio conservé (`Qt.KeepAspectRatio`), transformation lissée (`Qt.SmoothTransformation`), construite à partir d'un pixmap redimensionné (jamais pleine résolution attachée à l'item) : ✅.
- `IconMode` configuré avec `setResizeMode(Adjust)`, `setMovement(Static)`, `setWordWrap(True)` : ✅.
- Fichier manquant/invalide : aucun crash, item conservé, icône de repli Qt standard (`QStyle.SP_MessageBoxWarning`), `Qt.UserRole`/tooltip préservés, double-clic/agrandissement toujours fonctionnels, `ImagePreviewDialog` affiche son message d'indisponibilité existant : ✅.
- Sélection, double-clic, bouton "Voir en grand", `ImagePreviewDialog`, flux d'import, `WorkspaceManager`, `Image` Domain, EventBus : strictement inchangés, non modifiés : ✅.
- Aucune mutation Domain supplémentaire : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ (240/240 : 234 précédents + 6 nouveaux, aucun test supprimé).
- Aucune modification hors périmètre : ✅, vérifié par `git status`/`git diff --stat`.

## Fichiers modifiés / créés

- `src/ui/pages/images_page.py` (modifié) — galerie `IconMode`, `_build_item()`, `_load_thumbnail_icon()`, `_on_item_double_clicked`/`_on_enlarge_clicked` lisant `Qt.UserRole`.
- `tests/integration/test_images_page.py` (modifié) — 6 nouveaux tests, 11 tests existants conservés sans modification.
- `tests/integration/test_inference_page.py` (modifié) — adaptation minimale du helper privé `_images_page_paths()` vers `Qt.UserRole` (voir "Résultats réels" ci-dessus), aucun autre changement.
- `docs/missions/MISSION_019.md` (créé).

Liste vérifiée directement depuis `git status --short`/`git diff --stat`. Aucun fichier hors ce périmètre — en particulier, `src/ui/dialogs/image_preview_dialog.py`, `src/managers/workspace_manager.py`, `src/domain/image.py`, `src/core/event_bus.py`, `src/ui/toolbar.py` ne figurent dans aucun diff.

## Hors périmètre

Suppression individuelle d'image ; multi-sélection avec actions groupées ; drag-and-drop de réordonnancement ; tri ; filtres ; recherche ; métadonnées ; badges ; génération d'image ; modification du Domain `Image` ; champ `thumbnail` dans le Domain ; Dataset gallery ; cache de miniatures ; lazy loading ; worker thread ; chargement asynchrone ; miniatures persistées sur disque ; service de thumbnails ; `MainToolBar` ; image de référence Inference ; img2img ; IP-Adapter ; ControlNet ; multi-engine ; Training ; nouveau Service/Manager/Engine ; modification d'`ImagePreviewDialog`.

## Commit correspondant

Mission 019 sera clôturée en commit(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash ni message définitif n'est fixé en dur dans ce document avant la création du commit — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log` une fois la clôture Git effectuée.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission019`), si l'architecte confirme vouloir suivre cette convention pour cette mission. Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission019` une fois créé.

## État final

**Mission 019 est terminée (implémentation et tests).** `ImagesPage` est désormais une galerie visuelle (`QListWidget.IconMode`) avec miniatures 128×128, `Qt.UserRole` comme source fiable du chemin complet, nom de fichier court affiché et chemin complet en tooltip, icône de repli déterministe pour tout fichier manquant/invalide. `ImagePreviewDialog`, `WorkspaceManager`, `Image` Domain, EventBus et le flux d'import restent strictement inchangés. Validée par 240 tests d'intégration (234 précédents + 6 nouveaux), aucune régression. **Clôture Git (commit/tag/Release) non encore effectuée** à la rédaction de ce document — à réaliser après validation explicite de l'architecte. Mission 020 non définie.
