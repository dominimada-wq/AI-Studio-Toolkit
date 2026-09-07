# Mission 099 — Qt Test Harness Window/Widget Lifecycle Hardening

> **MISSION CLÔTURÉE COMME CARACTÉRISATION/DOCUMENTATION DE DETTE — AUCUN CORRECTIF RETENU. GITHUB RELEASE PUBLIÉE.** Un correctif de cleanup a été implémenté, validé sur cible (126/126, safety net 7/7), puis **rejeté** après avoir déclenché un incident natif `STATUS_HEAP_CORRUPTION` (`0xC0000374`) reproductible avec le runner canonique `python -m unittest discover` à l'échelle de la suite complète. Le code de test est revenu strictement à l'état d'avant Mission 099 (`git diff` vide sur les 9 fichiers concernés). Aucune modification de `src/`. Voir section 5 pour le récit complet et section 6 pour la dette finale documentée.

## 1. Contexte

L'audit post-Mission 098 a listé quatre candidats de prochaine mission. Après analyse conjointe avec l'architecte, le candidat A — la dette de harnais de test Qt documentée depuis Mission 097 (`docs/missions/MISSION_097.md` §12.5 : un drift de `QApplication.topLevelWidgets()` mesuré à **+16 net sur 126 tests réels construisant une `MainWindow`**, strictement identique en baseline et en M097 complet, deux tentatives de correction déjà explorées et rejetées après preuve empirique qu'elles n'amélioraient rien — voire aggravaient le drift) — est retenu comme Mission 099, avec un cadrage explicitement révisé par l'architecte : **ne pas présumer qu'il s'agit d'une « fuite Qt » au sens strict** avant d'en avoir établi la cause par la preuve.

L'architecte a explicitement demandé une démarche `audit ciblé → preuve de la cause → correctif minimal → validation`, sans présupposer ni la cause ni le correctif, avec des mesures reproductibles avant/après. **Cette démarche a été suivie intégralement ; elle a conduit à rejeter le correctif envisagé plutôt qu'à l'adopter** — voir section 5.

## 2. Objectif (intention initiale, révisée par les résultats)

Intention initiale : stabiliser le cycle de vie des fenêtres/widgets Qt dans le harnais de test monoprocessus, en s'appuyant sur des mesures reproductibles, sans modifier aucun comportement fonctionnel de l'application. **Résultat final** : la stabilisation par cleanup explicite s'est révélée elle-même déclencheuse d'un incident natif plus grave que la dette qu'elle corrigeait ; l'objectif réel de clôture devient la **caractérisation, le bornage et la documentation** de cette dette, sans correctif de code retenu — voir section 6.

## 3. Audit préalable — faits établis (présenté et validé par l'architecte avant implémentation)

Toutes les mesures ci-dessous ont été obtenues par exécution réelle (PySide6 6.11.1 réellement installé, `MainWindow` réelle) depuis des scripts jetables en scratchpad de session, **sans aucune modification du dépôt**.

### 3.1 Mesure sur le fichier réel `test_main_window_new_project.py` (42 tests)

Un `TestResult` instrumenté (aucune modification du fichier testé) a pris un instantané de `QApplication.topLevelWidgets()` — nombre **et répartition par type** — avant/après chaque test individuel :

- **42/42 tests montrent un delta strictement positif**, quasi tous **exactement `+15`**, de composition strictement identique à chaque fois : `{'MainWindow': 1, 'QFrame': 8, 'QMenu': 5, 'QMenuBar': 1}`.
- Net sur le fichier entier : `0 → 43`.
- Un seul test dérogeait (`QMenuBar: -12` compensé ailleurs) — cohérent avec un passage non déterministe du GC cyclique générationnel de Python pendant ce test précis, pas une anomalie propre au test.

### 3.2 Isolation de la cause — deux mécanismes indépendants, mesurés séparément

**Mécanisme n°1 — dominant (~14/15, ~93 % du drift mesuré) : rétention structurelle par `unittest.TestSuite`.**

`unittest.TestLoader` construit tous les objets `TestCase` d'une suite avant qu'aucun test ne s'exécute, et le `TestSuite` les garde vivants jusqu'à la fin complète du run. Les 9 fichiers concernés (confirmés par recherche exhaustive du motif `= MainWindow(` dans `tests/integration/`) suivent tous le même patron : `self.window = MainWindow()` en `setUp()`, `self.addCleanup(self.window.close)` — **aucun des 9 ne vide jamais l'attribut `self.window` après usage** :

- `test_main_window_new_project.py`
- `test_main_window_rename_project.py`
- `test_main_window_close_event.py`
- `test_main_window_prompts_to_inference.py`
- `test_main_window_initial_size.py`
- `test_main_window_comfyui_settings.py`
- `test_main_window_ollama_settings.py`
- `test_dashboard_page.py`
- `test_main_toolbar.py`

Tant que le `TestCase` existe dans la suite, `self.window` maintient tout le graphe (`MainWindow` + ses `QFrame` internes + les 5 sous-menus `QMenu` + le `QMenuBar`) atteignable en Python, donc jamais détruit côté C++, jusqu'à la fin du run entier.

**Preuve isolée** (`FakeTestCase` reproduisant exactement `setUp()`/`addCleanup()`/`doCleanups()` — avec `pop()` sur `_cleanups`, comme le vrai `unittest.case.TestCase.doCleanups()` — retenue dans une liste jouant le rôle d'un `TestSuite`) :
- `self.window` jamais vidé après cleanups → **`+15` par cycle**, identique à la mesure réelle du fichier.
- `self.window` explicitement mis à `None` après cleanups (`tc.window = None`) → **`+1` par cycle**, soit une chute de **93 %** du drift.
- Aucune rétention de `TestCase` (pas de conteneur type `TestSuite`) → **`+1` par cycle** également, motif identique à la reproduction PySide6 nu ci-dessous.

**Mécanisme n°2 — résiduel (~1/15, ~7 % du drift) : particularité native PySide6/Qt sur `QMainWindow.setMenuBar()`.**

Reproduit à l'identique avec **zéro ligne de code du projet** (`QMainWindow()` + `setMenuBar(QMenuBar())` nus) :
- `MainWindow()` construite, `.close()`, `del`, **`gc.collect()` à chaque itération** (30 cycles) → **`+1` par cycle, sans exception** ; le `gc.collect()` répété ne change rien.
- `weakref` sur une `MainWindow` : `gc.get_referrers()` avant `del` → **0 référent** ; `ref()` déjà `None` juste après `del`, **avant tout `gc.collect()` manuel** → destruction déterministe par simple comptage de références, **aucun cycle Python détecté**.
- `menu.parentWidget()`/`isWindow()` interrogés en direct à chaque étape tant que les objets Python restent vivants → **parenté toujours correcte**, jamais top-level ; le problème n'apparaît **qu'après** la destruction du wrapper Python.
- Contrôles : `QMainWindow()` seule sans `setMenuBar()` ni `.menuBar()` → 0 croissance. `QMainWindow()` + `self.menuBar()` (création automatique paresseuse de Qt) → 0 croissance. Seul `setMenuBar(objet_externe)` déclenche l'effet.
- `deleteLater()` + purge de la boucle d'événements → **aggrave** (`+2` au lieu de `+1`), jamais de correction. Cohérent avec le rejet déjà documenté en Mission 097 (§12.5, tentative `close_and_delete_widget()` → `+254` au lieu de `+16`).

### 3.3 Élucidation complète des 8 `QFrame` (réalisée pendant l'implémentation, voir section 6)

Vérifié widget par widget (`id()`, `parentWidget()`, `isWindow()`, chaîne de parenté complète, `findChildren()`) : les 8 `QFrame` sont les conteneurs de popup internes de **8 `QComboBox` réels de l'application** (2×`InferencePage`, 3×`SettingsPage`, 1×`DatasetsPage`, 1×`ImagesPage`, 1×`TrainingPage`), chacun correctement parenté (`parentWidget()` renvoie la vraie page) mais `isWindow()==True` par construction Qt (même principe que `QMenu`, flag `Qt::Popup`). Confirmé également par contraste : les 3 fichiers à variable locale (`test_main_window_initial_size.py`, `test_main_window_comfyui_settings.py`, `test_main_window_ollama_settings.py`, où `window` n'est jamais stocké sur `self`) ne montrent **que** du `QMenuBar` dans leurs deltas cumulés — jamais de `QFrame`/`QMenu`/`MainWindow` — confirmant que ces derniers n'apparaissent que parce que tout le graphe `MainWindow` reste vivant via le Mécanisme n°1, pas à cause d'un défaut de parenté indépendant.

**Conclusion** : `QMenu`/`QFrame` visibles dans `topLevelWidgets()` ne constituent **pas en eux-mêmes une preuve de fuite de production** — ce sont des popups Qt normaux, correctement parentés, qui satisfont `isWindow()==True` par conception. Aucun défaut de parenté de production n'a été démontré. Voir section 6 pour la formulation finale de la dette.

## 4. Frontière stricte — test-only (respectée intégralement)

- **Aucune modification de `src/`** à aucun moment de la mission, y compris pendant l'implémentation du correctif puis son rollback.
- Aucun changement fonctionnel de l'application à aucun moment.
- Le seul signal ayant nécessité un arrêt et un rapport (incident natif `STATUS_HEAP_CORRUPTION`, section 5) a été traité exactement selon la procédure prévue : arrêt immédiat, diagnostic, rapport à l'architecte, décision collégiale — jamais de contournement silencieux.

## 5. Tentative de correctif — implémentation, incident natif, rollback

### 5.1 Correctif implémenté

Après validation du contrat par l'architecte, un correctif minimal a été appliqué aux 9 fichiers du Mécanisme n°1 (6 fichiers réellement modifiés, les 3 fichiers à variable locale n'ayant pas besoin de correctif — voir §3.3) : libération explicite de `self.window` après les cleanups Qt existants, ordre LIFO vérifié rigoureusement (la libération s'exécute toujours après `self.window.close()`, jamais avant), aucun helper partagé introduit (9 occurrences quasi identiques d'une seule ligne, jugées préférables à une abstraction). 13 lignes ajoutées au total, 0 supprimée, `src/` intact.

### 5.2 Validation initiale — verte

- 126 tests ciblés (`python -m unittest` sur les 9 fichiers) : **126/126 OK**.
- Safety net Qt (`test_qt_dialog_safety_net.py`) : **7/7 OK**, contrat inchangé.

### 5.3 Incident lors de la mesure avant/après — diagnostic différentiel

La mesure de confirmation (même instrumentation que §3.1, avant/après le correctif) a produit une terminaison native silencieuse, sans traceback Python, dans un harnais de diagnostic manuel (`TestLoader`/`TestSuite`/`TextTestRunner` construits à la main, hors `python -m unittest`). Une matrice différentielle rigoureuse a établi, par la preuve :

- **Code de sortie réel obtenu via PowerShell** (pas Git Bash) : `-1073740940` décimal = **`0xC0000374` = `STATUS_HEAP_CORRUPTION`**, confirmé au bit près.
- **Réfuté** : la corrélation avec `QApplication.topLevelWidgets()` — un script contenant cet appel *après* le point de crash (jamais atteint) plante à l'identique ; un script sans aucun appel à `topLevelWidgets()` plante aussi, dès que le harnais manuel charge le fichier entier sans `resultclass` personnalisé.
- **Non reproduit hors `unittest`** : 152 cycles cumulés `MainWindow() → close() → libération de la référence` en script nu, sans `TestCase`/`TestSuite`, tous propres (10, 42, 100 cycles, répétés).
- **Non reproduit avec un sous-ensemble réduit** : le test cible seul, +1/2/3 tests précédents, ou la classe entière (12 tests) isolée via `loadTestsFromTestCase` — tous propres. Le crash n'apparaît qu'en chargeant le fichier entier (42 tests, 5 classes) via `loadTestsFromModule`.
- **Non reproduit avec le runner canonique du projet** sur le périmètre ciblé : `python -m unittest` sur le fichier seul (13 exécutions fraîches) et sur les 9 fichiers combinés (5 exécutions fraîches) — 18/18 propres.
- Signal non totalement expliqué : sensibilité déterministe à des variations Python non fonctionnelles (présence ou non d'une sous-classe locale de `TextTestResult`), compatible avec une corruption mémoire native sensible à la disposition du tas plutôt qu'avec un défaut sémantique.

### 5.4 Le signal s'est confirmé avec le runner canonique à l'échelle de la suite complète

Sur instruction de l'architecte, le correctif a malgré tout été validé avec le runner canonique réel : `python -m unittest discover -s tests -p "test_*.py"`, avec le correctif de cleanup en place. **Résultat : terminaison abrupte (exit 127 sous Git Bash), aucun résumé `Ran X tests`/`OK`, log tronqué sans retour à la ligne final** — signature identique à celle du harnais manuel, mais cette fois avec la méthode d'invocation officielle du projet, sur la suite complète (jamais observé sur le sous-ensemble ciblé de 126 tests).

### 5.5 Rollback et preuve comparative

Le correctif (13 lignes) a été intégralement retiré via `git restore` sur les 6 fichiers modifiés — `git diff` confirmé strictement vide sur ces 6 fichiers, retour exact à l'état d'avant Mission 099. Avec le code revenu à cette baseline :

| Validation | Avec le correctif de cleanup | Après rollback (baseline) |
|---|---|---|
| 126 tests ciblés | 126/126 OK | 126/126 OK |
| Safety net Qt (7 tests) | 7/7 OK | 7/7 OK |
| Suite complète canonique (`python -m unittest discover`) | **Crash natif** (`STATUS_HEAP_CORRUPTION`, aucun résumé produit) | **`Ran 1930 tests in 215.755s` — `OK`, exit 0**, 0 `STATUS_HEAP_CORRUPTION`, 0 dialogue bloquant, 0 intervention humaine |

Cette comparaison directe, à code de test strictement identique en dehors du correctif retiré, constitue une preuve forte : **le retrait explicite de `self.window` (donc la destruction réelle et répétée de `MainWindow` qu'il entraîne) est l'élément déclencheur/amplificateur du `STATUS_HEAP_CORRUPTION` observé à l'échelle de la suite complète.**

### 5.6 Décision

**Le correctif de cleanup explicite est rejeté.** La rétention actuelle (Mécanisme n°1) est acceptée comme dette de harnais mieux maîtrisée — connue, bornée, sans impact fonctionnel démontré — que le crash natif qu'engendrerait sa suppression naïve. Aucune des 13 lignes n'est réintroduite. Aucun autre mécanisme de nettoyage (`deleteLater()`, `QApplication` modifié, GC forcé, changement de runner) n'a été tenté après ce constat, conformément à l'instruction explicite de l'architecte.

## 6. Dette Qt du harnais — caractérisation finale acceptée

Cette section constitue la conclusion définitive de Mission 099 :

1. **Le drift de `QApplication.topLevelWidgets()` observé depuis Mission 097 provient majoritairement (~93 %) de la rétention des instances `TestCase` par `unittest.TestSuite`**, via l'attribut `self.window` jamais libéré dans les 9 fichiers concernés (§3.2, §5.1).
2. **Les 8 `QFrame` sont identifiés avec certitude comme les popups internes de 8 `QComboBox` réels de l'application**, correctement parentés (§3.3) — aucun défaut de parenté de production.
3. **Les `QMenu`/`QFrame` visibles dans `topLevelWidgets()` ne constituent pas en eux-mêmes une preuve de fuite** : ce sont des popups Qt normaux (`Qt::Popup`), qui satisfont `isWindow()==True` par conception indépendamment de leur parenté correcte.
4. **Le résidu `QMenuBar` (~7 % du drift) est reproductible avec PySide6 nu** autour de `QMainWindow.setMenuBar(QMenuBar externe)` — particularité native, non causée par le code du projet, non corrigible par `deleteLater()`/purge d'événements (aggrave au contraire, §3.2).
5. **Le cleanup explicite de `self.window` réduit fortement le drift mesuré (~93 %) mais déclenche/amplifie un incident natif `0xC0000374`/`STATUS_HEAP_CORRUPTION` reproductible avec le runner canonique à l'échelle de la suite complète** (§5.3–5.4).
6. **Le rollback exact de ce cleanup restaure une suite complète stable, `1930/1930`, exit 0** (§5.5).
7. **En conséquence, ce cleanup est rejeté** ; la rétention actuelle du Mécanisme n°1 est acceptée comme dette de harnais — documentée, bornée, sans preuve d'impact fonctionnel — plutôt que remplacée par un correctif dont le risque démontré (corruption mémoire native sur la suite complète) est strictement supérieur au problème qu'il résout (accumulation d'objets inertes, jamais montrée comme cause d'un échec de test ou d'un comportement applicatif incorrect).
8. **Aucune tentative future de `self.window = None`, `deleteLater()`, ou nettoyage agressif équivalent ne doit être retentée sans élément technique nouveau** (nouvelle version de PySide6/Qt, nouvelle preuve isolant précisément le mécanisme de la corruption mémoire, ou autre piste non encore explorée) — cette mission a démontré, par la preuve et non par supposition, que la tentative la plus directe et la mieux intentionnée aggrave le risque réel plutôt que de le réduire.

## 7. Ce que cette mission ne fait pas (rappel)

- Aucun lancement réel d'OneTrainer ni d'aucun entraînement — aucune future mission OneTrainer ne redémarre/lance OneTrainer sans autorisation explicite de l'architecte.
- Aucune UI de suivi/progression Training.
- Aucune génération de caption assistée par IA.
- Aucune fondation de Prompt Library.
- Aucun autre besoin futur déjà documenté dans `docs/PROJECT_CONTEXT.md` (§ "Besoins futurs identifiés par l'usage réel").
- Aucun refactoring préventif du harnais de test au-delà de la tentative documentée en section 5.

## 8. Critères de clôture (révisés — reflètent le résultat réel)

1. ~~Disparition de la rétention dominante~~ — **non retenue** : la rétention est documentée et acceptée comme dette (section 6), pas supprimée.
2. Absence de croissance inexpliquée des `QFrame`/autres widgets — **satisfait** : entièrement élucidée (§3.3), aucune inconnue restante.
3. Résidu natif (Mécanisme n°2) clairement isolé, reproductible et borné — **satisfait**, avec sa valeur exacte mesurée (§3.2).
4. Tests ciblés des 9 fichiers concernés : **verts** (126/126, code de test revenu à la baseline, §5.5).
5. Tests du safety net Qt : **verts** (7/7, contrat inchangé).
6. Suite complète monoprocessus : **1930/1930, exit 0, 0 `STATUS_HEAP_CORRUPTION`, 0 dialogue bloquant, 0 intervention humaine**, obtenue sur le code de test revenu à la baseline (une seule suite complète nécessaire ici, la comparaison avec/sans correctif faisant elle-même office de preuve — voir §5.5).
7. `git diff --check` propre, aucun artefact de diagnostic dans le dépôt — confirmé (section 9 du rapport final).
8. Tous les scripts/instrumentations temporaires sont restés hors du dépôt (scratchpad de session) — confirmé, aucun n'a été ajouté au dépôt ni conservé de façon permanente.
9. **Aucune modification de `src/`** — respecté intégralement, à aucun moment de la mission.
10. **Aucune modification de test au final** — le correctif implémenté a été intégralement retiré ; le dépôt est revenu à l'état exact d'avant Mission 099 sur les 9 fichiers concernés.
11. Dette Qt caractérisée et documentée — section 6 ci-dessus, plus régularisation prévue dans `docs/PROJECT_CONTEXT.md`.
12. Tentative de correctif rejetée avec preuve — section 5 ci-dessus.
13. Baseline fonctionnelle conservée — 1930/1930, code de test identique à `HEAD`.

## 10. Clôture Git

- Commit documentaire substantiel : `199e7b8d72a40bb0dedb711aeefd418843d51118` — *docs: characterize Qt test harness lifecycle debt* (`docs/missions/MISSION_099.md`, `docs/PROJECT_CONTEXT.md`).
- Tag annoté : `v0.2-mission099`, sur ce même commit exact (vérifié via `git rev-parse v0.2-mission099^{commit}`).
- `main` et le tag poussés vers `origin` sans divergence ni commit étranger intercalé.
- Aucune modification de `src/` ou `tests/` dans ce commit — mission close sans changement de code, conformément à la décision de l'architecte (section 5.6).
- GitHub Release `v0.2-mission099` **publiée** — confirmée par l'architecte du projet.
