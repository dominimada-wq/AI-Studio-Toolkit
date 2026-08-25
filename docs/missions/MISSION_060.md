# Mission 060 — Adaptive Initial Window Size

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat de tests renforcé validé (section 2), implémentation réalisée conforme à la solution retenue, 5/5 tests ciblés nets nouveaux, 75/75 de non-régression, **1016/1016 tests automatisés verts**, smoke test Qt réel exécuté et **PASS** (section 9) — validation technique accordée par l'architecte, puis clôture Git et publication de la GitHub Release entièrement effectuées. Voir section 11 pour l'état final réel.

## 1. Contexte

Un audit factuel du dépôt, réalisé après la clôture complète et la régularisation documentaire de Mission 059, a cherché en priorité une fonctionnalité utilisateur concrète ou une dette UX réellement visible, conformément à l'instruction explicite de privilégier ce type de candidat sur un nouveau tour de nettoyage de code mort pour cette itération.

**Constat vérifié** : `MainWindow.__init__()` fixe une taille de fenêtre en dur, sans aucune prise en compte de la taille d'écran réellement disponible.

```python
# src/ui/main_window.py:185
self.resize(1700, 950)
```

Aucun appel à `screen()`/`availableGeometry()` n'existe nulle part dans `main_window.py` (confirmé par recherche exhaustive). Sur un écran dont la résolution disponible est inférieure à 1700×950, la fenêtre s'ouvre visiblement plus grande que l'espace utilisable — anomalie réellement observée et documentée pendant le smoke test réel de Mission 059 (`docs/missions/MISSION_059.md`, section 15 ; `docs/PROJECT_CONTEXT.md`, section "Problèmes connus / dettes"). Cette anomalie est **authentiquement préexistante** (commit racine du fichier, 2026-08-08) et **indépendante** de la régression que Mission 059 avait elle-même introduite puis corrigée (`application_hint.setWordWrap(True)`) — les deux causes sont confirmées distinctes par mesure directe.

Redimensionnement manuel possible ensuite (la fenêtre n'est jamais figée en taille), mais la première impression au lancement reste dégradée sur tout écran plus petit que 1700×950 — un cas d'usage réel, pas seulement théorique, déjà rencontré par l'architecte.

## 2. Mini-audit réalisé

**Comportement actuel** : `self.resize(1700, 950)` appliqué inconditionnellement, quelle que soit la résolution/l'espace disponible de l'écran cible. Aucun test automatisé ne verrouille cette valeur (recherche exhaustive dans `tests/integration/` : aucun fichier ne référence `resize`/`screen()`/`availableGeometry` pour `MainWindow` — seuls `test_settings_page.py`/`test_prompt_assistant_dialog.py`/`test_image_preview_dialog.py` référencent `sizeHint`/`minimumSize`, tous sans rapport avec `MainWindow.resize()`). Depuis la correction de Mission 059 (`application_hint.setWordWrap(True)`), `MainWindow.minimumSizeHint()` est mesuré à `(865, 769)` dans l'environnement de test — largement sous toute résolution d'écran réelle, donc aucun risque que le contenu ne puisse physiquement pas tenir.

**Vérification de l'API réellement disponible**, exécutée avec des widgets Qt réels dans cet environnement :
```
QMainWindow().screen()                       -> QScreen(name="\\.\DISPLAY1")   # jamais None ici, avant tout show()
QMainWindow().screen().availableGeometry()   -> QRect(0, 0, 1920, 1040)
QApplication.primaryScreen().availableGeometry() -> QRect(0, 0, 1920, 1040)
```
`QWidget.screen()` retourne un écran valide même avant `.show()` — utilisable directement dans `__init__()`, aucun besoin d'attendre l'affichage.

**Comportement cible** : la taille initiale ne doit jamais dépasser l'espace disponible de l'écran cible, tout en conservant `1700×950` comme taille par défaut préférée lorsque l'écran le permet. La fenêtre reste librement redimensionnable ensuite (déjà le cas, aucun `setFixedSize()` nulle part). Aucune tentative de centrage explicite (le placement par défaut du gestionnaire de fenêtres du système d'exploitation n'est pas modifié — hors périmètre, non demandé). Aucune persistance/restauration de géométrie entre sessions — **explicitement laissé ouvert par l'architecte** ("ne préjuge pas encore de cette politique"), non traité par ce candidat.

**Fichiers concernés** :
- `src/ui/main_window.py` — `MainWindow.__init__()`, remplacement de la ligne `self.resize(1700, 950)` par un calcul borné à `screen().availableGeometry()`.

**Domain/Manager/UI/Infrastructure** : UI uniquement (`MainWindow`). Aucun changement Domain/Manager/Infrastructure/EventBus.

**Persistance** : aucune — comportement purement à l'exécution, recalculé à chaque lancement.

**Tests existants à vérifier (non-régression)** : `tests/integration/test_settings_page.py::SettingsPageSizeHintRegressionTest` (Mission 059) — indépendant, mesure `SettingsPage.sizeHint()` isolément, non affecté par ce candidat.

**Nouveaux tests à écrire — contrat renforcé, validé par l'architecte** : nouveau fichier `tests/integration/test_main_window_initial_size.py`, `screen()`/`QApplication.primaryScreen()` mockés (`unittest.mock.patch.object`, vérifié fonctionnel avec de vrais widgets Qt dans cet environnement avant écriture des tests), couvrant explicitement quatre cas, chacun avec un mock distinguant volontairement `geometry()` de `availableGeometry()` (valeurs différentes) pour prouver que le calcul utilise bien la seconde — la zone réellement utilisable après barre des tâches et zones réservées — jamais la première :
1. **Écran disponible plus petit que 1700×950** (ex. `availableGeometry` `1280×720`, `geometry` volontairement différent, ex. `1280×800`) → `window.width() == 1280` et `window.height() == 720`, strictement bornés à `availableGeometry()`, jamais à `geometry()`.
2. **Écran disponible plus grand que 1700×950** (ex. `availableGeometry` `1920×1080`, `geometry` différent) → taille historique `1700×950` conservée à l'identique.
3. **`self.screen()` retourne `None`, `QApplication.primaryScreen()` disponible** (ex. `availableGeometry` `1366×768`) → fallback vers `primaryScreen()` effectivement emprunté, taille bornée en conséquence.
4. **`self.screen()` et `QApplication.primaryScreen()` retournent tous deux `None`** → fallback historique `1700×950`, construction de `MainWindow` sans lever d'exception.

Chaque test vérifie en plus que la fenêtre reste redimensionnable après construction (`resize()` manuel accepté, aucun `setFixedSize()`/taille maximale introduite).

**Smoke test Qt réel — exécuté par Claude, pas seulement décrit** : construction réelle de `MainWindow` dans cet environnement, rapport factuel de `screen.geometry()`, `screen.availableGeometry()` (mesurées, jamais supposées égales à `1920×1040`), taille initiale réellement obtenue, confirmation `window.width() <= available.width()` et `window.height() <= available.height()`, confirmation que la fenêtre reste manuellement/programmatiquement redimensionnable après son initialisation.

**Attention `minimumSizeHint()` — limite documentée, non contournée** : `self.resize(1700, 950)` (devenu le calcul ci-dessus) s'exécute avant la construction du `QStackedWidget`/des pages (ligne 185, avant la boucle de construction des pages à partir de la ligne ~216) — `MainWindow.minimumSizeHint()` mesuré à `865×769` par Mission 059 reflète l'état une fois toutes les pages construites, pas l'état au moment exact de l'appel `resize()`. Si un écran disponible était exceptionnellement plus petit que le minimum imposé une fois le layout complet construit, Qt agrandirait la fenêtre au-delà de la borne calculée ici pour respecter ce minimum — comportement Qt standard, non contourné, non corrigé, documenté ici pour mémoire ; aucun écran réaliste observé ou attendu ne déclenche ce cas (865×769 est un minimum très bas), donc non traité comme un problème réel nécessitant une décision séparée.

**Aucune décision produit ou architecturale substantielle ne reste ouverte.**

## 3. Objectif

Éliminer la dette UX documentée (`docs/PROJECT_CONTEXT.md`, "Problèmes connus / dettes") : la fenêtre principale ne doit plus jamais s'ouvrir plus grande que l'espace d'écran réellement disponible, tout en conservant la taille par défaut actuelle lorsque l'écran le permet.

## 4. Contrat fonctionnel proposé

- `MainWindow.__init__()` : remplace `self.resize(1700, 950)` par un calcul qui borne la largeur/hauteur par défaut (`1700`/`950`) à `self.screen().availableGeometry()` (repli sur `QApplication.primaryScreen()` si `self.screen()` renvoie `None` — cas défensif, non observé dans cet environnement mais raisonnable avant tout `show()`) :
  ```python
  screen = self.screen() or QApplication.primaryScreen()
  if screen is not None:
      available = screen.availableGeometry()
      width = min(1700, available.width())
      height = min(950, available.height())
  else:
      width, height = 1700, 950
  self.resize(width, height)
  ```
- Aucun autre appel (`setWindowTitle`, construction des pages, etc.) modifié.
- La fenêtre reste redimensionnable exactement comme aujourd'hui — aucun `setFixedSize()`/`setMaximumSize()` introduit.

## 5. Hors périmètre (explicitement différé)

- Persistance/restauration de la géométrie utilisateur entre sessions (déplacement, redimensionnement manuel mémorisés) — besoin futur distinct, politique non tranchée, explicitement laissée ouverte par l'architecte.
- Centrage explicite de la fenêtre ou toute autre logique de placement — le comportement par défaut du système d'exploitation n'est pas modifié.
- Gestion multi-écrans avancée (choix explicite de l'écran cible, comportement au changement d'écran en cours de session) — seul l'écran retourné par `screen()`/`primaryScreen()` au lancement est utilisé, comportement Qt standard.
- Toute autre dette UX ou besoin identifié par ailleurs (mapping LoRA Workspace↔moteur, `comfyui_path`, FLUX, second rôle Reference, portabilité des chemins, Training réel, Prompt Library/RAG) — non concernés par ce candidat, voir section 7 pour le statut de chacun.

## 6. Risques

- **Risque de régression fonctionnelle** : très faible — un seul appel modifié, aucun autre comportement touché, `MainWindow.minimumSizeHint()` (`865×769`, confirmé par Mission 059) reste largement sous la borne calculée dans tous les cas réalistes.
- **Risque de désaccord sur la politique** : faible — le contrat (borner au maximum disponible, sans jamais dépasser, taille par défaut conservée si l'écran le permet) est la lecture la plus directe du besoin déjà documenté par l'architecte lui-même dans la dette UX.
- **Risque de test fragile** : le nouveau test doit mocker `screen()` plutôt que dépendre de la résolution réelle de la machine d'exécution (CI/environnement de développement), pour rester déterministe.

## 7. Pourquoi maintenant

Le besoin est réellement observé (pas une anticipation) : signalé concrètement par l'architecte pendant le smoke test réel de Mission 059, cause déjà établie avec certitude par mesure directe, correctif déjà écarté du périmètre M059 pour rester strictement dans le contrat validé. Aucun prérequis manquant, aucune dépendance externe, aucune décision produit substantielle restant à trancher — contrairement à la plupart des autres candidats identifiés (voir section 8).

## 8. Autres candidats évalués et écartés pour cette mission

- **Mapping LoRA Workspace ↔ moteur (`LoRA.files` → `lora_name` ComfyUI)** : besoin réel confirmé et documenté par Mission 059 (`docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés" ; `docs/missions/MISSION_059.md`, section 2 bis). **Décision produit substantielle non tranchée** : stratégie de mapping (copie/installation physique vers le dossier du moteur — impliquerait de consommer `ApplicationSettings.comfyui_path`, toujours inexploité, et de décider si AI Studio Toolkit doit écrire dans le dossier d'une application tierce — vs. enregistrement/déclaration auprès du moteur si un mécanisme existe vs. autre mécanisme fiable). Nécessite un arbitrage architecte avant tout audit d'implémentation.
- **Exploitation de `comfyui_path`** : champ existant, jamais consommé (confirmé à nouveau par cet audit — aucune référence dans `src/` hors `SettingsPage`/`ApplicationSettings`/`ApplicationSettingsManager`). Besoin flou au-delà d'un usage diagnostic/détection ; recouperait directement le mapping LoRA ci-dessus si celui-ci est un jour tranché en faveur d'une copie physique — prématuré de le traiter isolément.
- **Compatibilité architecture checkpoint/LoRA (SD1.5/SDXL/FLUX)** : déjà traitée par Mission 059 (Option A — le serveur ComfyUI reste seul juge, échec explicite, jamais de substitution silencieuse). Rien de nouveau à livrer sans rouvrir la question du support FLUX lui-même (voir ci-dessous).
- **Support FLUX comme pipeline distinct** : nécessiterait un nouveau workflow ComfyUI complet (`UNETLoader`/`DualCLIPLoader`/VAE séparé, `LoraLoaderModelOnly`), de nouveaux `ApplicationSettings` moteur, et une décision architecturale sur la cohabitation avec le pipeline `CheckpointLoaderSimple` existant (nouveau mode/Engine distinct, ou branchement conditionnel dans les builders actuels ?) — taille et risque significativement plus grands que ce que peut couvrir un vertical slice, nécessite son propre audit dédié.
- **Second rôle Reference (IP-Adapter/ControlNet/InstantID/PuLID)** et **vrai multi-références** : toujours bloqués sur un mécanisme moteur réel dont la disponibilité sur l'installation ComfyUI réelle de l'architecte n'est pas vérifiable dans cet environnement — statut inchangé depuis Mission 056/057/058/059.
- **« Dataset de références → Inference »** : bloqué sur le point précédent, statut inchangé, reconfirmé par la régularisation de Mission 059.
- **Portabilité des chemins internes** (`Workspace.root`, `Image.file_path`, `LoRA.thumbnail`) : besoin réel documenté depuis Mission 029, mais le périmètre exact (quels champs précisément) n'a toujours jamais été tranché — nécessiterait son propre audit de scoping avant toute implémentation.
- **Training réel (OneTrainer/Kohya)** : exclu, multi-engine, aucune décision moteur tranchée, périmètre large.
- **Prompt Library structurée / RAG local** : modèle de données non défini, décision produit ouverte, périmètre large.
- **Model/Workflow → Inference** (identifié pendant l'audit de Mission 059, `Workspace.models`/`ModelManager` toujours entièrement déconnectés de `ApplicationSettings.comfyui_checkpoint_name` — reconfirmé par cet audit, aucune référence à `Workspace.models` dans `generation_manager.py`) : implique une décision produit non triviale (le concept "Model" du Workspace doit-il fusionner avec la notion de "checkpoint" Settings-level, ou rester délibérément distinct ?) non tranchée ici.
- **Settings/multi-engine, i18n** : périmètres larges, aucune décision d'architecture tranchée.

## 9. Vérifications finales — réellement exécutées

**Implémentation** : `src/ui/main_window.py`, un seul point de code — `self.resize(1700, 950)` remplacé par le calcul validé (`screen = self.screen() or QApplication.primaryScreen()`, borné à `screen.availableGeometry()`, repli sur `1700×950` si aucun écran). Import `QApplication` ajouté. Aucun autre fichier de production modifié.

**Tests ciblés** (`tests/integration/test_main_window_initial_size.py`, nouveau fichier, 5 tests) — **5/5 PASS** :
1. Écran disponible plus petit que `1700×950` (`availableGeometry` `1280×720`, `geometry` volontairement différent `1280×800`) → `window.size() == (1280, 720)`, prouvant l'usage d'`availableGeometry()` et non de `geometry()`.
2. Écran disponible plus grand (`1920×1080` vs `geometry` `1920×1200`) → taille historique `1700×950` conservée à l'identique.
3. `screen()` → `None`, `primaryScreen()` → écran `1366×768` → fallback effectif, `window.size() == (1366, 768)`.
4. `screen()` et `primaryScreen()` tous deux `None` → aucune exception, `window.size() == (1700, 950)`.
5. Redimensionnement manuel après construction (`resize(640, 480)`) → accepté sans contrainte, fenêtre toujours librement redimensionnable.

**Non-régression ciblée** : `test_settings_page.py` (`SettingsPageSizeHintRegressionTest`, Mission 059, non affecté), `test_main_window_comfyui_settings.py`/`_new_project.py`/`_rename_project.py`/`_ollama_settings.py`/`_prompts_to_inference.py` — **75/75 verts**.

**Suite complète** : **1016/1016 tests automatisés verts** (1011 précédents + 5 nets nouveaux).

`git diff --check` : propre. Périmètre exactement conforme au contrat : `src/ui/main_window.py` (production), `tests/integration/test_main_window_initial_size.py` (nouveau test), ce document — aucun résidu scratch/smoke dans le dépôt.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

Construction réelle de `MainWindow` dans cet environnement, écran réel (non patché) :
```
screen.geometry()          = QRect(0, 0, 1920, 1080)
screen.availableGeometry() = QRect(0, 0, 1920, 1040)   # mesuré, jamais supposé — 40px de barre des tâches
```
```
window.size() après construction = QSize(1700, 950)
window.width() <= available.width()   : True (1700 <= 1920)
window.height() <= available.height() : True (950 <= 1040)
```
```
resize(800, 600) manuel -> QSize(800, 600) -- redimensionnement confirmé
```
L'écran disponible étant plus grand que `1700×950`, la taille historique est conservée à l'identique — cohérent avec le test ciblé n°2. **Verdict : PASS.**

**Validation technique finale accordée par l'architecte.**

## 11. Clôture Git et publication — état final réel

**Commit fonctionnel** : `bee1ec46db9a54b08f7e165fa4aba66bfe00b8e5` ("feat: bound initial window size to available screen geometry"), 3 fichiers (`src/ui/main_window.py`, `tests/integration/test_main_window_initial_size.py`, `docs/missions/MISSION_060.md`), 292 insertions/1 suppression.

**Push** : `7c3983d..bee1ec4 main -> main`. Vérifié : `HEAD == origin/main`, divergence `0 0`, working tree propre.

**Tag** : `v0.2-mission060` (annoté, message "Mission 060 - Adaptive Initial Window Size"), objet tag `c8f68d8df297b868d2f2be28cde7bb1a5f9f01c3`, ciblant exactement le commit fonctionnel `bee1ec46db9a54b08f7e165fa4aba66bfe00b8e5` — confirmé localement (`git rev-list -n1`) et à distance (`git ls-remote --tags origin`), identiques.

**GitHub Release** : `v0.2-mission060` publiée manuellement par l'architecte (Release Notes en anglais, rédigées par Claude, publication effectuée par l'architecte conformément à la convention).

**Régularisation post-Release** : effectuée dans ce même document (section 11) ainsi que dans `docs/PROJECT_CONTEXT.md` et `CHANGELOG.md`, en commit documentaire séparé du commit fonctionnel — pas de déplacement du tag `v0.2-mission060`, toujours attaché au commit fonctionnel.

## État d'avancement

- Audit du dépôt (candidats Mission 060) : **réalisé**.
- Choix de mission : **validé par l'architecte**.
- Mini-audit : **réalisé** (section 2), aucune décision substantielle ouverte identifiée.
- Contrat de tests : **renforcé et validé par l'architecte** (4 cas explicites + preuve d'usage d'`availableGeometry()` + limite `minimumSizeHint()` documentée).
- Spécification (ce document) : **rédigée, conforme au contrat renforcé**.
- Implémentation : **réalisée, conforme au contrat**.
- Tests automatisés : **exécutés, verts — 1016/1016** (5 nets nouveaux).
- `git diff --check` : **propre**.
- Smoke test Qt réel : **réalisé, PASS** (section 10).
- **Validation technique finale : accordée par l'architecte.**
- Clôture Git (commit/tag/Release) : **entièrement effectuée** (section 11).
- Régularisation documentaire post-Release : **effectuée**.

**Mission 060 : ENTIÈREMENT CLOSE.**
