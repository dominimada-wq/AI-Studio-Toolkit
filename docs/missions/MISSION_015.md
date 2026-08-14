# Mission 015 — Enlarged Image Preview

Source : historique direct de la conversation de développement (audit architectural préalable, spécification validée, implémentation, revue technique finale ayant identifié et corrigé un défaut réel de redimensionnement, smoke test réel complet couvrant les deux consommateurs), vérifié contre le code réel et la suite de tests.

## Objectif

Introduire un mécanisme Qt simple et réutilisable permettant d'afficher une image en grand, partagé par deux consommateurs réels :

1. `ImagesPage` (consultation d'une image de `Workspace.images`) ;
2. `InferencePage` (consultation du résultat pending introduit par Mission 014, avant toute décision Accept/Reject/Regenerate).

Besoin identifié par l'usage réel des Missions 013/014 (aperçu post-génération jugé trop petit pour une inspection détaillée, et absence totale de moyen de consulter une image en grand depuis `ImagesPage`). La galerie/miniatures `ImagesPage` reste explicitement différée à une mission ultérieure — Mission 015 ne transforme pas la liste texte actuelle en galerie visuelle.

## Architecture

### Composant partagé : `ImagePreviewDialog`

- Emplacement : `src/ui/dialogs/image_preview_dialog.py` (nouveau sous-package `src/ui/dialogs/`, avec `__init__.py`, cohérent avec la convention déjà en place sur tous les autres sous-packages `src/*`).
- Classe unique : `ImagePreviewDialog(QDialog)`, API publique minimale — `__init__(self, file_path: str, parent=None)`. Aucune autre méthode publique n'est nécessaire ; l'appelant instancie et appelle `.exec()`.
- **Strictement passif** : le constructeur ne reçoit qu'une `str` (`file_path`) — jamais une référence à un objet Domain, un Manager, ou une Page. Le dialogue n'a donc **aucun canal** pour modifier `Workspace.images`, `Dataset.images`, un état pending, ou déclencher `WORKSPACE_SAVED` ; cette garantie vient de la conception (absence de référence), pas d'un garde-fou ajouté après coup.
- **Aucune nouvelle dépendance** : uniquement `PySide6` (`QDialog`, `QLabel`, `QPushButton`, `QVBoxLayout`, `QPixmap`, `QShortcut`, `QKeySequence`), déjà une dépendance du projet. `Pillow`/`opencv-python` (présents dans `requirements.txt` mais jamais utilisés dans `src/ui/`) ne sont pas sollicités, cohérent avec le raisonnement déjà tenu en Mission 014 pour l'aperçu inline.
- **Aucun nouveau Domain, Manager, EventBus event** : `ImagePreviewDialog` est un composant de Presentation pur, sans dépendance descendante nouvelle.

### Chargement et affichage

- `QPixmap(file_path)` chargé **une seule fois** au constructeur (`self._source_pixmap`), jamais rechargé depuis le disque ensuite. Si `pixmap.isNull()` (fichier absent, illisible, ou non décodable), `self._source_pixmap` est mis à `None` — le dialogue affiche alors un message texte clair (`UNAVAILABLE_MESSAGE = "Image indisponible : fichier introuvable ou illisible."`) dans le `QLabel`, sans exception, sans accès au Domain.
- `QLabel` centré (`Qt.AlignCenter`), redimensionné dynamiquement dans `resizeEvent`/`showEvent` via `self._source_pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)` — chaque resize rescale l'unique pixmap déjà en mémoire, aucune copie pleine résolution supplémentaire n'est jamais créée, aucune relecture disque.
- Titre de fenêtre = `Path(file_path).name` (nom de fichier seul, ou le chemin complet en repli si le nom est vide).
- Taille initiale : 1000×750, nettement plus grande que l'aperçu inline `InferencePage` (`minimumHeight(240)`), fenêtre librement redimensionnable.

### Plein écran

- Bouton "Plein écran (F11)" et raccourci clavier `F11` (`QShortcut`) connectés **au même** callback `_toggle_fullscreen()` — un seul mécanisme, pas deux implémentations divergentes.
- `showFullScreen()`/`showNormal()` alternés selon `self.isFullScreen()` — aucun état métier supplémentaire, purement visuel.
- Fermeture directement depuis le plein écran fonctionne sans restauration préalable (`showNormal()` non requis avant `close()`).

## Correction découverte en revue technique finale — défaut réel de redimensionnement

**Défaut identifié avant toute correction, via investigation empirique (widgets Qt réels, pas seulement lecture de code)** : `QLabel.minimumSizeHint()` se cale automatiquement sur le dernier pixmap qui lui a été assigné via `setPixmap()`. Comme `_update_scaled_pixmap()` réassigne un nouveau pixmap redimensionné à chaque `resizeEvent`/`showEvent`, le plancher de taille minimale du `QLabel` — et donc de la fenêtre elle-même — remontait silencieusement à chaque agrandissement. Conséquence concrète reproduite par script de sondage : après un premier affichage à la taille par défaut (1000×750), un `resize(60, 60)` restait bloqué autour de 1000×541 au lieu de réellement rétrécir.

**Correction retenue** :

```python
self.image_label.setMinimumSize(1, 1)
```

Cette ligne découple explicitement la contrainte minimale de layout du `QLabel` du pixmap actuellement affiché — la fenêtre peut alors rétrécir librement, indépendamment de la plus grande taille de rendu déjà atteinte.

Le défaut a été :

- **reproduit empiriquement** (script de sondage utilisant les vraies API Qt/PySide6, mesures de géométrie avant/après) ;
- **corrigé** avant toute clôture de mission ;
- **couvert par un test de régression automatisé dédié** (`test_window_can_shrink_back_after_displaying_a_large_scaled_image`) ;
- **revalidé pendant le smoke test réel** par un cycle manuel complet agrandissement → fort rétrécissement (dans les deux dimensions) → réagrandissement, effectué depuis la vraie application via le mécanisme de redimensionnement système Windows (menu système + flèches clavier, le glisser-déposer synthétique de bordure s'étant révélé peu fiable — limitation de l'outil d'automatisation du smoke test, non représentative d'un défaut d'AI Studio Toolkit).

## Intégration `ImagesPage`

- **Double-clic** sur un item (`itemDoubleClicked`) et **bouton "Voir en grand"** (nouveau) convergent vers la même méthode interne `_open_preview(file_path)` — comportement strictement identique quel que soit le déclencheur.
- Bouton désactivé par défaut, activé/désactivé via `_update_enlarge_button_state()` connectée à `itemSelectionChanged` : désactivé sans sélection, activé dès qu'un item est sélectionné (`self.list_widget.currentItem() is not None`).
- `update_images()` (rafraîchissement sur `WORKSPACE_CREATED`/`OPENED`/`SAVED`/`CLOSED`) suit désormais le pattern `blockSignals(True)/clear()/reconstruction/blockSignals(False)` documenté dans `CLAUDE.md`, puis appelle explicitement `_update_enlarge_button_state()` après reconstruction — garantissant qu'un `WORKSPACE_SAVED` ne peut jamais laisser le bouton activé avec `currentItem() is None` : l'état du bouton est toujours relu depuis l'état réel de la sélection après le refresh, jamais mis en cache.
- **Galerie/miniatures non implémentées** : le `QListWidget` texte reste inchangé dans son mode d'affichage — Mission 015 ne transforme pas `ImagesPage` en galerie visuelle.
- Fichier référencé absent/illisible : le dialogue s'ouvre normalement avec le `file_path` de l'entrée `Image`, affiche son message d'indisponibilité — `Workspace.images` n'est jamais modifié ni nettoyé automatiquement par la simple consultation.

## Intégration `InferencePage`

- Nouveau bouton `preview_enlarge_button` ("Voir en grand"), ajouté à la ligne de boutons de validation existante, branché sur le point d'activation déjà en place `_set_validation_buttons_enabled()` — aucun nouvel état à introduire, le bouton suit exactement le même cycle de vie qu'Accept/Reject/Regenerate.
- `_on_enlarge_clicked()` : garde `if self._pending_path is None: return` (même style défensif que les autres handlers), puis `ImagePreviewDialog(self._pending_path, parent=self).exec()`.
- **Aucune ligne modifiée** dans `_on_generation_finished`, `_on_accept_clicked`, `_on_reject_clicked`, `_on_regenerate_clicked`, `reset_for_workspace_change`, `_clear_pending`, `_delete_pending_file` — la state machine Mission 014 reste strictement inchangée.
- Le dialogue étant **modal** (`exec()`), aucune autre action (Accept/Reject/Regenerate/Generate) n'est possible pendant la consultation — garantie supplémentaire, en plus de l'absence structurelle de référence, qu'aucune transition d'état ne peut survenir pendant l'ouverture.

### État du bouton "Voir en grand" selon la state machine Mission 014

| État | `preview_enlarge_button` |
|---|---|
| INITIAL | désactivé |
| GENERATING | désactivé |
| PENDING | activé |
| ACCEPT | désactivé |
| REJECT | désactivé |
| REGENERATE (nouvelle génération en cours) | désactivé |
| ERROR | désactivé |
| WORKSPACE_CHANGED | désactivé |
| SHUTDOWN | sans effet métier propre (`_clear_pending` le désactive déjà) |

Ouvrir/fermer `ImagePreviewDialog` depuis un résultat pending ne modifie jamais : `_pending_path`, `_pending_pixmap`, `_generation_workspace_root`, `Workspace.images`, `project.json`, l'état Accept/Reject/Regenerate, le `QThread`/`worker` en cours, ni ne déclenche `WORKSPACE_SAVED` — vérifié par test automatisé et par smoke test réel (génération ComfyUI réelle, deux ouvertures successives, Accept final).

## Tests

**190/190 tests d'intégration verts** — 159 précédents (base Mission 014) + 31 nets nouveaux (19 lors de l'implémentation initiale + 12 ajoutés lors de la revue technique finale).

Trois fichiers concernés :

- **`tests/integration/test_image_preview_dialog.py`** (nouveau, 13 tests) : composant testé en isolation avec de vrais widgets Qt (`show()`/`processEvents()`/`close()`, jamais `exec()` qui bloquerait le process de test) — image paysage valide, image portrait valide (ratio conservé dans les deux orientations), fichier absent, fichier invalide/non décodable, redimensionnement réel avec conservation du ratio, régression du bug de rétrécissement (agrandissement puis fort rétrécissement), fenêtre très petite (1×1) sans crash, ouvertures/fermetures multiples sans état résiduel, bascule plein écran par bouton, bascule F11 réelle (`QTest.keyClick`) deux fois de suite avec retour à l'état normal, bouton et F11 prouvés comme invoquant la même méthode (`patch.object` + comptage d'appels), fermeture directement depuis le plein écran.
- **`tests/integration/test_images_page.py`** (nouveau, 11 tests) : bouton désactivé sans sélection puis activé avec sélection, bouton et double-clic ouvrent le même `file_path` (`ImagePreviewDialog` patchée pour éviter tout `exec()` réel), ouverture répétée du même item, fichier absent ouvert sans mutation du Domain, consultation ne déclenchant jamais `add_images()`/`save()`, refresh (simulation de `WORKSPACE_SAVED` via un nouvel import) avec sélection active → bouton correctement réinitialisé, refresh sans sélection préalable, re-sélection après refresh réactivant le bouton.
- **`tests/integration/test_inference_page.py`** (étendu, 30 → 37 tests) : bouton "Voir en grand" désactivé hors PENDING, activé uniquement en PENDING, ouverture avec le bon `pending_path`, ouverture répétée sans effet sur l'état pending, état pending strictement identique avant/après ouverture-fermeture (chemin, pixmap, racine Workspace mémorisée, état de tous les boutons), aucune persistance/suppression/sauvegarde déclenchée par la simple consultation (spies sur `add_images`/`save`), assertions `preview_enlarge_button` ajoutées aux tests existants de changement de Workspace (WORKSPACE_CHANGED → désactivé). Tous les tests Accept/Reject/Regenerate/course `QThread` de Mission 014 restent verts, strictement inchangés dans leur logique.

Suite entièrement mockée (`GenerationManager` mocké dans `test_inference_page.py`), aucun accès réseau réel, aucune instance ComfyUI, aucun GPU dans les tests automatisés.

## Smoke test réel

Réalisé depuis la vraie interface (`src/core/main.py`, wiring de production réel), backend ComfyUI Desktop déjà actif et détecté sur `http://127.0.0.1:8000`, Workspace de test réel hors dépôt (`Mission015Project`), nettoyé après le test.

### `ImagesPage`

Trois images réelles importées (`landscape_red.png` 640×360, `portrait_blue.png` 360×640, `third_green.png` 300×300, ajoutée en cours de test) : bouton "Voir en grand" désactivé sans sélection, activé dès sélection ; ouverture correcte via le bouton et via le double-clic (bon `file_path` à chaque fois, comportement identique) ; ratio conservé pour les trois images (paysage, portrait, carrée) ; redimensionnement réel de la fenêtre — agrandissement, **fort rétrécissement réel dans les deux dimensions**, puis réagrandissement — sans blocage sur une ancienne taille de pixmap (bug corrigé confirmé absent en conditions réelles), sans déformation ; plein écran par bouton et par `F11` tous deux vérifiés (bascule réelle, retour normal, même dialogue conservé) ; ouvertures successives (même image deux fois, puis image différente) sans fenêtre résiduelle ; fermeture directement depuis le plein écran (Alt+F4) propre ; refresh réel déclenché par un nouvel import (`WORKSPACE_SAVED`) — sélection précédente correctement réinitialisée (`currentItem()` absent, bouton désactivé), réactivation confirmée après nouvelle sélection.

### `InferencePage`

Génération réelle lancée avec le prompt `"a green sphere on a white background"` contre ComfyUI Desktop réel (~15 s) — résultat pending réel obtenu (fichier `outputs/AIStudioToolkit_00011_.png`, 310 Ko), `Workspace.images` resté inchangé (non persisté) avant Accept. Aperçu agrandi ouvert depuis le résultat pending : image nettement plus grande que l'aperçu inline, plein écran par bouton et par `F11` tous deux vérifiés, deuxième ouverture du même pending sans anomalie. État pending strictement préservé avant/après chaque ouverture-fermeture (chemin, aperçu inline, état des quatre boutons de validation) ; aucune persistance pendant la consultation (`project.json` relu à l'identique après chaque ouverture). Accept final : image ajoutée **exactement une fois** à `Workspace.images`, `ImagesPage` rafraîchie automatiquement sans action manuelle.

### Fichier absent

Fichier `landscape_red.png` supprimé du disque en dehors de l'application (Workspace de test jetable) : entrée conservée dans `Workspace.images`/`project.json` (aucune suppression automatique), `ImagePreviewDialog` affiche le message d'indisponibilité prévu, aucun crash.

### Fermeture

Application fermée proprement via File → Quitter, exit code `0`, log de sortie vide, aucun message Qt anormal observé sur toute la session.

### Réserve d'outillage (non représentative d'un défaut applicatif)

Le glisser-déposer synthétique de bordure de fenêtre (outil d'automatisation du smoke test) s'est révélé peu fiable pour déclencher un rétrécissement — un seul essai a partiellement fonctionné, les suivants n'ont produit aucun changement observable. Contourné avec succès via le mécanisme de redimensionnement système Windows natif (menu système de la fenêtre → "Taille" → flèches clavier), qui a permis de vérifier rigoureusement et de façon déterministe le comportement réel de la fenêtre, y compris le rétrécissement fort dans les deux dimensions. Cette réserve concerne exclusivement l'outil de contrôle du poste de travail utilisé pour le test, jamais `ImagePreviewDialog` ni AI Studio Toolkit eux-mêmes.

Aucune divergence entre le comportement automatisé (tests) et le comportement réel observé.

## Limites

- **Galerie/miniatures `ImagesPage`** : toujours non implémentées — la liste reste un `QListWidget` texte, volontairement hors périmètre de Mission 015.
- **Visualiseur système Windows** : non implémenté — étudié dans l'audit préalable mais jugé non prioritaire et potentiellement Windows-only, resté hors périmètre.
- **Multi-sélection `ImagesPage`** : non implémentée — un seul item consultable à la fois.
- Toujours hors périmètre, non implémentés : images de référence pour `InferencePage`, sélection multi-engine/backend, suppression/édition/renommage d'image, métadonnées d'image, annulation d'une génération en cours, historique de générations.

## Fichiers créés

- `src/ui/dialogs/__init__.py`
- `src/ui/dialogs/image_preview_dialog.py`
- `tests/integration/test_image_preview_dialog.py`
- `tests/integration/test_images_page.py`

## Fichiers modifiés

- `src/ui/pages/images_page.py` (double-clic, bouton "Voir en grand", pattern `blockSignals` sur `update_images()`)
- `src/ui/pages/inference_page.py` (bouton "Voir en grand" pending, aucune modification de la state machine)
- `tests/integration/test_inference_page.py` (30 → 37 tests)

Aucun autre fichier modifié. Aucune modification de `main_window.py` (pas de nouveau câblage EventBus — le dialogue est purement local à chaque handler de clic), du Domain, des Managers, de `GenerationManager`, `GenerationWorker`, `ComfyUIEngine`, de l'EventBus, ou de `requirements.txt`. Liste vérifiée directement depuis `git status --short`/`git diff --stat`.

## Critères d'acceptation — état final

- Composant `ImagePreviewDialog` créé, strictement passif, sans dépendance Domain/Manager/Page : ✅.
- `QPixmap` chargé une seule fois, ratio conservé (`KeepAspectRatio`), lissage (`SmoothTransformation`) : ✅.
- Redimensionnement dynamique réel, y compris rétrécissement après agrandissement : ✅, défaut réel trouvé en revue et corrigé avant clôture, vérifié par test automatisé et smoke test réel.
- Fichier absent/invalide géré sans crash, sans mutation du Domain : ✅.
- Plein écran par bouton et par `F11`, même mécanisme, aucun état métier supplémentaire : ✅.
- `ImagesPage` : double-clic et bouton ouvrent la même image, sélection correctement gérée, refresh sans sélection fantôme : ✅.
- `InferencePage` : bouton suit exactement la state machine Mission 014, aucune modification de `_pending_path`/Accept/Reject/Regenerate/`Workspace.images`/`WORKSPACE_SAVED` par la simple consultation : ✅.
- Aucun nouveau Domain/Manager/EventBus event/dépendance : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ (190/190).
- Smoke test réel complet, deux consommateurs validés : ✅.
- Documentation de fin de mission complète : ✅ (ce document + `docs/PROJECT_CONTEXT.md`).

## Dettes hors périmètre (volontairement non traitées par Mission 015)

- Galerie/miniatures `ImagesPage` (besoin déjà identifié en Mission 013/014, toujours non implémenté).
- Images de référence pour `InferencePage` (déjà identifié, toujours non implémenté).
- Sélection multi-engine/backend (déjà identifié, toujours non implémenté).
- Visualiseur système Windows pour l'aperçu agrandi (étudié, non implémenté).
- Nouveau besoin identifié par l'usage réel de Mission 015 : absence de création directe de dossier lors de "Nouveau projet" — voir `docs/PROJECT_CONTEXT.md`, non implémenté.
- Limite shutdown sans annulation réelle pendant une génération active (Mission 013, non résolue).
- Toutes les dettes déjà connues avant Mission 015 (ambiguïté `Training`/`Training History`, `BasePage` mort, incohérences Blueprint `Job`, support Linux/macOS `ApplicationSettingsStorage`) — inchangées.

## Commit correspondant

Mission 015 sera clôturée en commit(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash ni message définitif n'est fixé en dur dans ce document avant la création du commit — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log` une fois la clôture Git effectuée.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission015`), si l'architecte confirme vouloir suivre cette convention pour cette mission. Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission015` une fois créé.

## État final

Mission terminée. `ImagePreviewDialog` introduit un visualiseur d'image partagé, strictement passif, entre `ImagesPage` et le résultat pending de `InferencePage` — un défaut réel de redimensionnement trouvé en revue technique finale et corrigé avant clôture. Validée par 190 tests automatisés entièrement mockés et par un smoke test réel complet couvrant les deux consommateurs, une génération ComfyUI réelle, et le cas du fichier absent. Un nouveau besoin futur (création directe de dossier lors de "Nouveau projet") a été identifié par l'usage réel, sans être architecturé ni implémenté. Mission 016 non définie ; nécessitera son propre audit architectural.
