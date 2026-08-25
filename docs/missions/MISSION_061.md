# Mission 061 — Adaptive Dialog Sizing

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Implémentation conforme au contrat proposé (section 4), 10 tests ciblés nets nouveaux (5 par dialogue, un test préexistant remplacé), 49/49 tests ciblés PASS, 248/248 de non-régression, **1025/1025 tests automatisés verts**, smoke test Qt réel exécuté et **PASS** sur les deux dialogues (section 9). Commit fonctionnel, tag `v0.2-mission061` et GitHub Release publiés — voir section 11 pour l'état de clôture Git final.

## 1. Contexte

Mission 060 a corrigé une dette UX réelle et déjà documentée : `MainWindow.__init__()` fixait `self.resize(1700, 950)` inconditionnellement, sans jamais tenir compte de l'espace d'écran réellement disponible (`screen().availableGeometry()`). L'audit du dépôt effectué après la régularisation documentaire de Mission 060 a cherché à vérifier si cette même classe de dette existait ailleurs dans le code, avant d'évaluer les autres besoins déjà connus.

**Constat vérifié** : exactement deux autres fenêtres du projet présentent la même dette structurelle — un appel `.resize(largeur, hauteur)` fixe, jamais borné à l'écran réellement disponible, appelé dans `__init__()` avant tout affichage :

```python
# src/ui/dialogs/image_preview_dialog.py:27
self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)   # DEFAULT_WIDTH = 1000, DEFAULT_HEIGHT = 750

# src/ui/dialogs/prompt_assistant_dialog.py:41
self.resize(800, 700)
```

Recherche exhaustive de toute la hiérarchie `QDialog` du projet (`class .*\(QDialog\)`, 6 classes : `ImagePreviewDialog`, `ImportCollisionDialog`, `NewProjectDialog`, `SelectImagesDialog`, `RenameProjectDialog`, `PromptAssistantDialog`) — seules ces deux appellent `.resize()` avec des valeurs fixes ; les quatre autres n'appellent jamais `.resize()`/`.setFixedSize()`/`.setGeometry()` et se dimensionnent uniquement via le `sizeHint()` agrégé de leur contenu (donc déjà adaptatif par construction, aucune dette). Aucun `setFixedSize()` sur aucun de ces dialogues — tous restent librement redimensionnables après ouverture, exactement comme `MainWindow` avant Mission 060.

Sur un écran dont l'espace disponible est inférieur à `1000×750` (ou `800×700`), ces dialogues peuvent donc s'ouvrir visiblement plus grands que l'espace utilisable — la même anomalie que celle corrigée par Mission 060 pour `MainWindow`, jamais balayée sur le reste du code à l'époque (Mission 060 était strictement limitée à `MainWindow`, par contrat).

## 2. Mini-audit réalisé

**`ImagePreviewDialog`** (`src/ui/dialogs/image_preview_dialog.py`) : `self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)` = `self.resize(1000, 750)`, ligne 27, dans `__init__()`, avant toute construction de contenu. Dialogue non modal réutilisé par `ImagesPage` et `InferencePage` (aperçu d'image plein cadre). `self.image_label.setMinimumSize(1, 1)` est la seule contrainte de taille minimale du dialogue — négligeable, aucun risque de conflit avec un écran réaliste.

**`PromptAssistantDialog`** (`src/ui/dialogs/prompt_assistant_dialog.py`) : `self.resize(800, 700)`, ligne 41, dans `__init__()`. Un test existant (`tests/integration/test_prompt_assistant_dialog.py::test_initial_size_is_at_least_800_by_700`) verrouille aujourd'hui un plancher **inconditionnel** `width() >= 800` / `height() >= 700` — ce test encode précisément la dette à corriger (un écran réellement plus petit que `800×700` disponible devrait pouvoir borner la taille, exactement comme `MainWindow` le fait désormais) et devra être remplacé par un test conforme au nouveau contrat (borné à `availableGeometry()`, plancher `800×700` uniquement quand l'écran le permet — mêmes 4 cas que Mission 060, voir ci-dessous). Aucun autre test ne verrouille une valeur fixe pour `ImagePreviewDialog` au-delà de `assertGreater(dialog.width(), 500)` (`test_window_can_shrink_back_after_displaying_a_large_scaled_image`), qui reste compatible sans modification (tout écran raisonnable, y compris un netbook `1024×600`, dépasse `500` de large).

**Vérification de l'API réellement disponible** : déjà prouvée fonctionnelle par Mission 060 pour `QMainWindow` (`self.screen()`/`QApplication.primaryScreen()`/`availableGeometry()`, mockage `patch.object` confirmé fonctionnel via le MRO). `QDialog` hérite de `QWidget` exactement comme `QMainWindow` — le même mécanisme s'applique sans changement d'API ; aucune nouvelle vérification d'API n'est nécessaire, seule la réexécution du smoke test réel avec ces deux dialogues concrets reste utile pour confirmer le comportement en conditions réelles.

**Comportement cible** : pour chacun des deux dialogues, la taille initiale ne doit jamais dépasser l'espace disponible de l'écran cible (`screen().availableGeometry()`, repli `QApplication.primaryScreen()`, repli final sur la valeur historique si aucun écran n'est disponible), tout en conservant la taille par défaut actuelle (`1000×750`/`800×700`) lorsque l'écran le permet — **exactement le même contrat que Mission 060**, appliqué à deux points de code supplémentaires plutôt qu'un nouveau principe.

**Fichiers concernés** :
- `src/ui/dialogs/image_preview_dialog.py` — `ImagePreviewDialog.__init__()`.
- `src/ui/dialogs/prompt_assistant_dialog.py` — `PromptAssistantDialog.__init__()`.

**Domain/Manager/UI/Infrastructure** : UI uniquement. Aucun changement Domain/Manager/Infrastructure/EventBus.

**Persistance** : aucune — comportement purement à l'exécution, recalculé à chaque ouverture, comme Mission 060.

**Tests existants à ajuster (non-régression assumée)** : `tests/integration/test_prompt_assistant_dialog.py::test_initial_size_is_at_least_800_by_700` — son plancher inconditionnel doit être remplacé par un test borné à `availableGeometry()` (mêmes 4 cas que Mission 060). `tests/integration/test_image_preview_dialog.py` — aucun ajustement requis, ses assertions existantes (`>500`, comportement de rétrécissement manuel) restent valides telles quelles.

**Nouveaux tests à écrire — même contrat renforcé que Mission 060, appliqué aux deux dialogues** : pour `ImagePreviewDialog` et `PromptAssistantDialog`, chacun avec un mock distinguant volontairement `geometry()` de `availableGeometry()` (valeurs différentes), couvrant les 4 mêmes cas que `test_main_window_initial_size.py` (écran disponible plus petit → bornage réel ; écran disponible plus grand → taille historique conservée ; repli `primaryScreen()` ; repli historique sans écran du tout, sans exception) plus la confirmation que chaque dialogue reste librement redimensionnable après construction.

**Smoke test Qt réel — à exécuter par Claude, pas seulement décrit** : ouverture réelle des deux dialogues dans cet environnement (écran non mocké), rapport factuel de la taille initiale obtenue pour chacun, confirmation que ni l'un ni l'autre ne dépasse `availableGeometry()`, confirmation du redimensionnement manuel après ouverture.

**Aucune décision produit ou architecturale substantielle ne reste ouverte.**

## 3. Objectif

Achever, sur les deux derniers points de code concernés, le balayage de la classe de dette UX identifiée et corrigée par Mission 060 (fenêtre/dialogue s'ouvrant plus grand que l'espace d'écran réellement disponible) — cohérence complète de comportement entre `MainWindow` et les dialogues du projet qui fixent une taille initiale en dur.

## 4. Contrat fonctionnel proposé

Pour chacun des deux fichiers, remplacer l'appel `.resize()` fixe par le même calcul que Mission 060 (`src/ui/main_window.py`), avec les valeurs par défaut propres à chaque dialogue :

```python
# image_preview_dialog.py — remplace self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)
screen = self.screen() or QApplication.primaryScreen()
if screen is not None:
    available = screen.availableGeometry()
    width = min(DEFAULT_WIDTH, available.width())
    height = min(DEFAULT_HEIGHT, available.height())
else:
    width, height = DEFAULT_WIDTH, DEFAULT_HEIGHT
self.resize(width, height)
```

```python
# prompt_assistant_dialog.py — remplace self.resize(800, 700)
screen = self.screen() or QApplication.primaryScreen()
if screen is not None:
    available = screen.availableGeometry()
    width = min(800, available.width())
    height = min(700, available.height())
else:
    width, height = 800, 700
self.resize(width, height)
```

- Aucun autre appel modifié dans l'un ou l'autre fichier.
- Les deux dialogues restent redimensionnables exactement comme aujourd'hui — aucun `setFixedSize()`/`setMaximumSize()` introduit.
- `tests/integration/test_prompt_assistant_dialog.py::test_initial_size_is_at_least_800_by_700` est remplacé par un test conforme au nouveau contrat (plancher `800×700` uniquement quand l'écran le permet).

## 5. Hors périmètre (explicitement différé)

- Toute autre dette UX ou besoin identifié par ailleurs (mapping LoRA Workspace↔moteur, bibliothèque LoRA centralisée, `comfyui_path`, FLUX, second rôle Reference, Dataset de références → Inference, portabilité des chemins, Model/Workflow → Inference, Training réel, Prompt Library/RAG, Settings/multi-engine, i18n, publication réseaux sociaux) — non concernés par ce candidat, voir section 8 pour le statut de chacun.
- Persistance/restauration de géométrie entre sessions pour l'un ou l'autre dialogue — même position que Mission 060, non tranchée.
- Centrage explicite ou toute logique de placement — comportement par défaut de Qt/du système d'exploitation inchangé.
- Toute modification du contenu, du comportement fonctionnel ou de la logique métier des deux dialogues au-delà du seul calcul de taille initiale.
- Tout autre dialogue du projet (`ImportCollisionDialog`, `NewProjectDialog`, `SelectImagesDialog`, `RenameProjectDialog`) — confirmés sans dette de ce type par cet audit (aucun `.resize()` fixe, dimensionnement déjà adaptatif via `sizeHint()`), donc non concernés.

## 6. Risques

- **Risque de régression fonctionnelle** : très faible — deux points de code modifiés, technique déjà validée par Mission 060 dans ce même environnement (widgets Qt réels, mockage `screen()`/`primaryScreen()` confirmé fonctionnel via le MRO pour un `QDialog` comme pour un `QMainWindow`, tous deux `QWidget`).
- **Risque de désaccord sur la politique** : très faible — strict prolongement du contrat déjà validé par l'architecte pour Mission 060, appliqué à l'identique.
- **Risque de test fragile** : identique à Mission 060 — mocker `screen()` plutôt que dépendre de la résolution réelle de la machine d'exécution.
- **Test existant à modifier** : `test_initial_size_is_at_least_800_by_700` doit être remplacé, pas seulement étendu — son intention actuelle (plancher inconditionnel) contredit directement le nouveau contrat. Signalé explicitement ici pour éviter toute ambiguïté au moment de l'implémentation.

## 7. Pourquoi maintenant

Le besoin est directement dérivé d'un principe déjà validé et implémenté par l'architecte lui-même (Mission 060), sur un périmètre que Mission 060 avait explicitement limité à `MainWindow` par contrat — cet audit confirme qu'il reste exactement deux occurrences de la même dette ailleurs dans le code, ni plus ni moins. Aucun prérequis manquant, aucune dépendance externe, aucune décision produit substantielle restant à trancher — contrairement à la quasi-totalité des autres candidats identifiés (voir section 8), qui restent bloqués soit sur une décision architecturale non tranchée, soit sur une vérification externe impossible dans cet environnement.

## 8. Autres candidats évalués et écartés pour cette mission

- **Bibliothèque LoRA centralisée multi-engine / mapping LoRA Workspace ↔ moteur** : décision de principe désormais retenue par l'architecte (voir `docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés"), mais **explicitement non destinée à devenir automatiquement une mission** — le modèle de données et l'intégration moteur par moteur restent à auditer, sur instruction explicite de l'architecte de ne pas transformer cette décision en Mission 061.
- **Exploitation de `comfyui_path`** : toujours inexploité au-delà de `SettingsPage`/`ApplicationSettings` (reconfirmé par cet audit) ; recoupe directement la décision LoRA ci-dessus, prématuré de le traiter isolément avant que cette décision soit auditée plus en détail.
- **Support FLUX comme pipeline distinct** : inchangé depuis Mission 060 — nécessiterait un nouveau workflow ComfyUI complet et une décision architecturale sur la cohabitation avec le pipeline existant ; taille et risque significativement plus grands qu'un vertical slice.
- **Second rôle Reference (IP-Adapter/ControlNet/InstantID/PuLID)** et **« Dataset de références → Inference »** : toujours bloqués sur un mécanisme moteur réel dont la disponibilité sur l'installation ComfyUI réelle de l'architecte n'est pas vérifiable dans cet environnement — statut inchangé depuis Mission 056.
- **Portabilité des chemins internes** (`Workspace.root`, `Image.file_path`, `LoRA.thumbnail`) : le périmètre exact (quels champs précisément, quelle stratégie de sérialisation) reste lui-même une décision non tranchée — nécessiterait un arbitrage architecte avant tout audit d'implémentation, pas seulement un audit de scoping que Claude pourrait clore seul.
- **Model/Workflow → Inference** (`Workspace.models`/`ModelManager` toujours entièrement déconnectés de `ApplicationSettings.comfyui_checkpoint_name`, reconfirmé par cet audit) : implique une décision produit non triviale (fusionner ou non le concept "Model" du Workspace avec la notion de "checkpoint" Settings-level) non tranchée.
- **Training réel (OneTrainer/Kohya)**, **Prompt Library structurée/RAG local**, **Settings/multi-engine**, **i18n**, **publication sur réseaux sociaux** : périmètres larges, décisions produit/architecture non tranchées, statuts inchangés depuis les audits précédents.
- **Dead code (round 3)** : recherche `TODO`/`FIXME`/`XXX`/`HACK` dans `src/` exécutée pendant cet audit — aucune occurrence. Aucun candidat de nettoyage identifié cette fois-ci.
- **`MainToolBar.action_run`** (désactivé depuis Mission 020, tooltip explicite) : toujours sans cible fonctionnelle légitime clairement définie — activer ce bouton nécessiterait de décider ce que "Run" doit exécuter (dernière configuration Inference ? autre ?), décision produit non tranchée, non traité ici.

## 9. Vérifications finales — réellement exécutées

**Implémentation** : conforme au contrat de la section 4, aucune divergence fonctionnelle.
- `src/ui/dialogs/image_preview_dialog.py` : `self.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)` remplacé par le calcul validé (`screen = self.screen() or QApplication.primaryScreen()`, borné à `screen.availableGeometry()`, repli sur `1000×750` si aucun écran). Import `QApplication` ajouté.
- `src/ui/dialogs/prompt_assistant_dialog.py` : `self.resize(800, 700)` remplacé par le même calcul, repli sur `800×700`. Import `QApplication` ajouté.
- Aucune abstraction/helper partagé introduit — deux adaptations locales indépendantes, comme prévu. Aucun autre fichier de production modifié ; les quatre autres `QDialog` du projet inchangés.

**Tests ciblés** — **49/49 PASS** :
- `tests/integration/test_image_preview_dialog.py` : nouvelle classe `ImagePreviewDialogInitialSizeTest` (5 tests) — écran disponible plus petit (`640×480` vs `geometry` `640×600`) borné à `availableGeometry()` ; écran disponible plus grand (`1920×1080` vs `geometry` `1920×1200`) conserve `1000×750` ; repli `primaryScreen()` (`1366×768`) ; repli historique sans écran (`1000×750`, aucune exception) ; redimensionnement manuel après construction. Tous les tests existants du fichier restent inchangés et verts.
- `tests/integration/test_prompt_assistant_dialog.py` : `test_initial_size_is_at_least_800_by_700` (plancher inconditionnel, contredisait le nouveau contrat) **remplacé** par la nouvelle classe `PromptAssistantDialogInitialSizeTest`, 5 tests strictement symétriques aux précédents, adaptés à `800×700`. `test_dialog_is_resizable` et tous les autres tests existants du fichier conservés inchangés.

**Non-régression ciblée** : `test_inference_page.py`, `test_images_page.py`, `test_datasets_page.py`, `test_prompt_roundtrip.py` (consommateurs des deux dialogues), `test_main_window_initial_size.py` (Mission 060, non affecté) — **248/248 verts**.

**Suite complète** : **1025/1025 tests automatisés verts** (1016 précédents + 9 nets nouveaux : 5+5 nouveaux tests − 1 test remplacé).

`git diff --check` : propre. Périmètre exactement conforme au contrat : `src/ui/dialogs/image_preview_dialog.py`, `src/ui/dialogs/prompt_assistant_dialog.py` (production), `tests/integration/test_image_preview_dialog.py`, `tests/integration/test_prompt_assistant_dialog.py` (tests), ce document — aucun résidu scratch dans le dépôt.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

Construction réelle des deux dialogues dans cet environnement, écran réel (non patché) :
```
screen.geometry()          = QRect(0, 0, 1920, 1080)
screen.availableGeometry() = QRect(0, 0, 1920, 1040)
```
```
ImagePreviewDialog    : size après construction = QSize(1000, 750)
  width() <= available.width()  : True (1000 <= 1920)
  height() <= available.height(): True (750 <= 1040)
  resize(400, 300) manuel -> QSize(400, 300) -- redimensionnement confirmé

PromptAssistantDialog : size après construction = QSize(800, 700)
  width() <= available.width()  : True (800 <= 1920)
  height() <= available.height(): True (700 <= 1040)
  resize(500, 400) manuel -> QSize(500, 400) -- redimensionnement confirmé
```
L'écran disponible étant plus grand que les deux défauts respectifs, les tailles historiques sont conservées à l'identique pour les deux dialogues — cohérent avec le comportement attendu. **Verdict : PASS.**

**Validation technique finale accordée par l'architecte.**

## 11. Clôture Git et publication — état final réel

**Commit fonctionnel** : `e2466292fd25d457eb2261414646597686c5240d` — « feat: bound ImagePreviewDialog and PromptAssistantDialog to available screen geometry ». 5 fichiers modifiés (`src/ui/dialogs/image_preview_dialog.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `tests/integration/test_image_preview_dialog.py`, `tests/integration/test_prompt_assistant_dialog.py`, `docs/missions/MISSION_061.md`), 364 insertions / 14 suppressions.

**Push** : `68572a3..e246629 main -> main`. Vérifié après coup : `HEAD == origin/main == e2466292fd25d457eb2261414646597686c5240d`, divergence `0 0`, working tree propre.

**Tag** : `v0.2-mission061` (annoté, message « Mission 061 - Adaptive Dialog Sizing »), objet `717a896a02a43a7a249bb473a66bd73bac14bc08`, peeled sur le commit fonctionnel `e2466292fd25d457eb2261414646597686c5240d` — vérifié identique en local (`git rev-list -n1`) et à distance (`git ls-remote --tags`). Le tag n'a jamais été déplacé.

**GitHub Release** : « Mission 061 - Adaptive Dialog Sizing », Release Notes rédigées en anglais par Claude, **publiée manuellement par l'architecte**.

## État d'avancement

- Audit du dépôt (candidats Mission 061) : **réalisé**.
- Choix de mission : **validé par l'architecte**.
- Mini-audit : **réalisé** (section 2), aucune décision substantielle ouverte identifiée.
- Spécification (ce document) : **rédigée, conforme au contrat**.
- Implémentation : **réalisée, conforme au contrat**.
- Tests automatisés : **exécutés, verts — 1025/1025** (9 nets nouveaux, 1 test remplacé).
- `git diff --check` : **propre**.
- Smoke test Qt réel : **réalisé, PASS sur les deux dialogues** (section 10).
- **Validation technique finale : accordée par l'architecte.**
- Clôture Git (commit/tag) : **réalisée** (section 11).
- GitHub Release : **publiée par l'architecte**.
- **Mission entièrement close.**
