# Mission 086 — Select an Inference Reference Image from the Workspace Gallery

> **MISSION IMPLÉMENTÉE, EN ATTENTE DE CLÔTURE GIT.** 15 tests ciblés nets nouveaux (3 sur `test_select_images_dialog.py`, 12 sur `test_inference_page.py`), non-régression complète, suite complète **1590/1590, aucun crash**, smoke test Qt réel exécuté et **PASS** (17/17 assertions — voir section 5). Commit fonctionnel `<à renseigner après commit>`, tag annoté `v0.2-mission086` à créer. Voir section 7 pour l'état de clôture Git.

## 1. Contexte

L'audit post-Mission 085 a identifié une friction utilisateur réelle et démontrable : `InferencePage._on_select_reference_clicked()` ne permettait de choisir une image de référence que via `QFileDialog` (parcours du disque), sans jamais pouvoir réutiliser une image déjà présente dans la galerie du Workspace (`Workspace.images`) — alors que `DatasetsPage` offre déjà ce choix pour l'ajout d'images à un Dataset depuis Mission 044 (`SelectImagesDialog`). Aucune décision produit n'expliquait cette asymétrie ; elle a été retenue comme direction candidate pour Mission 086, à l'exclusion du fix `CharacterManager.delete()` (dette de robustesse secondaire, sans impact car l'UI multi-Character reste volontairement inaccessible depuis Mission 026) et des autres besoins fonctionnels encore en catégorie B (LoRA centralisée, découverte ComfyUI, Prompt Library — tous nécessitant un pré-audit architectural plus lourd).

Un mini-audit contractuel préalable a établi trois faits déterminants avant toute implémentation :
- `self._reference_image_path` est un simple `Optional[str]`, jamais copié ni persisté, quelle que soit sa source — `GenerationManager.generate()`/`ComfyUIEngine.upload_image()` ne font que **lire** ce chemin (`Path(file_path).read_bytes()`) pour le POSTer vers ComfyUI, sans jamais écrire dans le Workspace. Une image de galerie utilisée comme référence n'est donc **jamais dupliquée physiquement**, exactement comme une image choisie sur le disque.
- Aucun pattern de menu-sur-bouton n'existe nulle part dans le codebase ; `DatasetsPage` résout la même dualité disque/galerie avec **deux boutons explicites côte à côte** (« Importer des images » / « Ajouter depuis Images… ») — pattern déjà en production, retenu pour Inference plutôt qu'une invention esthétique.
- `SelectImagesDialog` (Mission 044) était déjà une pure couche de présentation sans dépendance Dataset — sa généralisation par 3 paramètres constructeur optionnels (`selection_mode`, `title`, `info_text`), tous à valeur par défaut reproduisant le comportement Dataset actuel byte-for-byte, a été jugée petite, propre et sans risque de régression, écartant l'option d'un second dialogue quasi identique.

## 2. Objectif

Ajouter un second bouton explicite dans la zone de référence d'Inference, ouvrant une sélection en `SingleSelection` depuis la galerie du Workspace, alimentant exactement la primitive existante `self._reference_image_path`, sans que le reste du pipeline de génération n'ait à distinguer sa provenance. Mission strictement mono-référence (0..1) — le futur système multi-référence à rôles (`identity`, `clothing`, `pose`, `environment`, ...) reste explicitement hors périmètre, sans aucune préparation spéculative.

## 3. Mini-audit contractuel préalable

- **`SelectImagesDialog`** : contrat réel entièrement relu (réception d'une `list[str]` déjà résolue par l'appelant, `Qt.UserRole` porte le chemin brut, `ExtendedSelection` codé en dur, titre/textes codés en dur pour Dataset, `selected_paths()` retourne une liste possiblement vide, Ok toujours actif même sans sélection — défaut C préexistant, non traité, sans impact) et ses 7 tests de contrat (`test_select_images_dialog.py`) identifiés comme devant rester verts byte-for-byte.
- **Contrat de référence Inference** : `_on_select_reference_clicked()`/`_clear_reference_selection()`/`reset_for_workspace_change()` relus intégralement — remplacement et re-sélection déjà gérés sans code spécial (écrasement inconditionnel), reset sur changement de Workspace déjà inconditionnel et inchangé par nature (source non pertinente), contrôles de référence déjà désactivés pendant une génération active (`_set_reference_controls_enabled(False)`, aucune nouvelle interaction avec M085 nécessaire), fichier disparu déjà normalisé en `GenerationError` par le pipeline commun (`OSError`/`FileNotFoundError` → `GenerationManager.generate()`), identique quelle que soit la source.
- **UX minimale** : recherche exhaustive de `QMenu`/`setMenu` dans `src/ui/` — aucune occurrence. Le pattern « deux boutons explicites » de `DatasetsPage.import_images()`/`add_images_from_gallery()` est le seul déjà établi pour cette dualité — retenu.
- **Limite architecturale** : `GenerationManager.generate()` reste à 0..1 référence *actionable* (`len(reference_images) > 1` toujours rejeté, inchangé) ; `Reference(path, role)` et la réserve de capacité 0..N (Mission 056) restent intacts sans aucune modification — Mission 086 ne fait qu'ajouter une seconde façon de peupler l'élément unique actuel.
- **Aucune anomalie découverte pendant l'audit ne contredit le contrat validé** — implémentation autorisée sans recadrage.

## 4. Implémentation

**`SelectImagesDialog`** ([select_images_dialog.py](../../src/ui/dialogs/select_images_dialog.py)) : constructeur étendu par 3 paramètres optionnels — `selection_mode=QListWidget.ExtendedSelection`, `title="Ajouter depuis Images"`, `info_text="Sélectionnez une ou plusieurs images à ajouter au dataset actif :"` — valeurs par défaut identiques au comportement Dataset actuel, aucun appelant existant modifié.

**`InferencePage`** ([inference_page.py](../../src/ui/pages/inference_page.py)) :
- Nouveau bouton `select_reference_from_gallery_button` (« Choisir depuis Images… ») ajouté dans `reference_row`, à côté du bouton disque existant.
- `_on_select_reference_from_gallery_clicked()` : mirroring exact de `DatasetsPage.add_images_from_gallery()` — `workspace_manager.opened` (sinon `QMessageBox.warning`), galerie vide (sinon `QMessageBox.information`), ouverture de `SelectImagesDialog(image_paths, parent=self, selection_mode=QListWidget.SingleSelection, title="Choisir une image de référence", info_text="Sélectionnez une image de la galerie à utiliser comme référence :")`, Cancel/aucune sélection → aucune mutation.
- `_apply_selected_reference(file_path)` : petit helper privé extrait pour éviter la duplication des 4 lignes de mise à jour d'état (`_reference_image_path`, label, `remove_reference_button`, `reference_strength_slider`) entre les deux chemins de sélection — partagé par `_on_select_reference_clicked()` (disque) et `_on_select_reference_from_gallery_clicked()` (galerie), sans généralisation supplémentaire.
- `_set_reference_controls_enabled()` étendu pour inclure le nouveau bouton, désactivé/réactivé exactement comme les contrôles de référence existants.
- Aucun changement à `GenerationManager`, `ComfyUIEngine`, Domain, ou tout autre Manager.

## 5. Tests automatisés et smoke test Qt réel

**15 tests ciblés nets nouveaux** :
- `test_select_images_dialog.py` (3) — titre/texte par défaut inchangés, `selection_mode`/`title`/`info_text` configurables, `SingleSelection` empêche réellement plus d'un item sélectionné simultanément (vérifié empiriquement : `QListWidget` applique déjà cette contrainte même via `item.setSelected(True)` direct).
- `test_inference_page.py` (12, dans `InferencePageTest`) — aucun Workspace ouvert → warning contrôlé, aucun dialogue construit ; galerie vide → information contrôlée, aucun dialogue construit ; dialogue peuplé avec les images réelles du Workspace en mode `SingleSelection` ; Cancel → aucune mutation ; aucune sélection → aucune mutation ; sélection réelle → `_reference_image_path`/label/boutons mis à jour exactement comme le picker disque ; remplacement disque → galerie ; remplacement galerie → disque ; re-sélection de la même image galerie → inoffensif ; aucune duplication physique sous `images/` ; bouton galerie désactivé pendant une génération active et toujours désactivé pendant un pending, réactivé après Reject ; reset complet sur un changement de Workspace réel.
- Le cas « fichier de galerie disparu physiquement » n'a délibérément **pas** reçu de nouveau test dédié : aucun nouveau code de production M086 n'intervient dans ce traitement (`GenerationManager.generate()`/`ComfyUIEngine.upload_image()` inchangés), et la couverture générique existante de `GenerationError` (plusieurs tests préexistants injectant `generation_manager.generate.side_effect = GenerationError(...)`, indépendants de la provenance de la référence) couvre déjà ce cas — conformément à l'instruction de ne pas créer artificiellement une nouvelle logique de test pour un comportement déjà intégralement couvert par le pipeline commun.
- Non-régression complète : `test_select_images_dialog.py` (10/10), `test_inference_page.py` (128/128), `test_datasets_page.py` (non modifié, vert) — 138/138 sur l'ensemble ciblé.
- **1590/1590 tests verts au total** (1575 précédents + 15 nets nouveaux), une exécution complète `unittest discover`, 188,6 s, aucun crash. Une défaillance isolée observée lors d'une exécution intermédiaire combinée à forte charge système (`InferencePageGenerationActiveGuardTest.test_confirm_does_not_touch_thread_or_pending_when_refusing`, un test hérité de Mission 085 sans rapport avec M086) a été reproduite en isolation et confirmée verte en 4,9 s — anomalie de contention ponctuelle déjà documentée comme catégorie connue depuis Mission 085, non un défaut introduit par cette mission.

**Smoke test Qt réel**, exécuté par Claude, `InferencePage`/`WorkspaceManager` réels, vraies images PNG écrites sur disque, vrai `SelectImagesDialog` construit (non mocké, seuls `exec()`/`selected_paths()` sont patchés pour simuler le clic utilisateur) — **PASS, 17/17 assertions** (exécuté 3 fois consécutivement, stable) : galerie réelle à 2 images, bouton galerie actif, dialogue réel construit en `SingleSelection` avec le titre Inference, référence correctement chargée (path/label/boutons), **aucun nouveau fichier écrit sous `images/`** après sélection, remplacement par une seconde image de galerie, reset complet après un changement de Workspace réel (`WorkspaceManager.create()`), avertissement contrôlé et aucun dialogue construit quand aucun Workspace n'est ouvert.

## 6. Conclusion

Inference dispose désormais de deux sources indépendantes pour la même primitive `self._reference_image_path` — le reste du pipeline de génération (`GenerationManager`, `ComfyUIEngine`, `Reference`) reste structurellement ignorant de la provenance, exactement comme demandé. `SelectImagesDialog` reste un dialogue unique généralisé par 3 paramètres optionnels à défauts inchangés, sans nouvelle abstraction. Aucune duplication physique n'est jamais produite, quelle que soit la source. Le périmètre mono-référence (0..1) est resté strictement respecté ; aucune préparation du futur système multi-référence à rôles n'a été introduite. Aucun changement Domain/Manager/EventBus/Engine.

## 7. État d'avancement et clôture Git

- Mini-audit contractuel préalable : **terminé**, validé par l'architecte, contrat définitif reçu.
- Implémentation : **réalisée**, strictement limitée à `src/ui/dialogs/select_images_dialog.py` et `src/ui/pages/inference_page.py`.
- Tests automatisés : **exécutés, verts — 15/15 ciblés nets nouveaux, non-régression complète (138/138 sur les fichiers ciblés)**.
- Suite complète : **1590/1590, aucun crash**, une exécution complète `unittest discover`, 188,6 s.
- `git diff --check` : **propre** (uniquement des avertissements de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme** (2 fichiers de production + 2 fichiers de tests + ce document de mission ; `test_datasets_page.py` non modifié).
- Smoke test Qt réel : **réalisé, PASS, 17/17 assertions, stable sur 3 exécutions consécutives**.
- Clôture Git (commit/tag/Release) : **en cours**.
