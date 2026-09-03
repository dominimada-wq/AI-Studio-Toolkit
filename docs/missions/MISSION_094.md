# Mission 094 — Fix the Mission-084 Test-Cleanup Lifetime Gap (Pending Result Guard Tests)

> **MISSION IMPLÉMENTÉE ET VALIDÉE PAR L'ARCHITECTE, CLÔTURE GIT EFFECTUÉE.** Voir section 6 pour l'état final.

## 1. Contexte

L'audit post-Mission 093 a confirmé, avec preuve directe et reproductible (5 occurrences, 100 % reproductibles sur 3 exécutions instrumentées pendant M093), un défaut structurel de harness de test distinct de tout comportement applicatif : `MainWindowInferencePendingResultGuardTest` (`tests/integration/test_main_window_new_project.py`) et `MainWindowRenamePendingResultGuardTest` (`tests/integration/test_main_window_rename_project.py`) mockent `_confirm_pending_before_switch()` uniquement à l'intérieur d'un bloc `with patch.object(...)` scopé au corps du test. Pour les scénarios où `InferencePage._pending_path` reste intentionnellement non-`None` en fin de test (Cancel, échec de persistance), `self.addCleanup(self.window.close)` — enregistré en premier dans `setUp()` — s'exécute après la sortie de ce bloc et retombe sur un `MainWindow.closeEvent()` réel et entièrement démocké, qui construit et affiche la vraie `QMessageBox` « Génération en attente » (`InferencePage._confirm_pending_before_switch()`).

Ce défaut a produit un incident réel observé par l'architecte à deux reprises consécutives (Missions 092 et 093), nécessitant une intervention manuelle pour débloquer la suite. Le filet de sécurité de Mission 091 ne couvre pas ces deux classes — il n'est armé que sur les 4 classes de la famille Mission 085 (« génération active »).

## 2. Objectif

Corriger la cause du lifetime gap (état de fixture incohérent au moment où `window.close()` réel s'exécute), pas seulement neutraliser son symptôme, puis évaluer si le filet de sécurité Mission 091 doit être armé sur ces deux classes en défense en profondeur — sans jamais élargir le périmètre au-delà des tests concernés.

## 3. Mini-audit — conclusions verrouillées

### 3.1 Mécanisme exact confirmé en source

`InferencePage.confirm_pending_result_change()` (`src/ui/pages/inference_page.py:834`) vérifie `self._pending_path is None` comme **toute première instruction** (ligne 851-852) et retourne `True` immédiatement, sans construire aucun dialogue, si c'est le cas. `_pending_path = None` est donc **strictement nécessaire et suffisant** pour rendre le guard entièrement no-op — aucun autre attribut associé (`_pending_pixmap`, état des boutons Accept/Reject, `_generation_workspace_root`) n'est lu par ce guard, et aucun n'a besoin d'être remis à zéro pour la correction elle-même. Le seul rôle de ces autres attributs est cosmétique (aperçu affiché) sur une fenêtre de toute façon détruite juste après par `window.close()` ; chaque test reconstruit un `MainWindow()` neuf dans `setUp()`, donc aucune fuite inter-tests n'est possible même sans les réinitialiser.

`MainWindow.closeEvent()` (`src/ui/main_window.py:696`) appelle `inference_page.confirm_pending_result_change()` en dernière position (ligne 757), après `confirm_no_active_generation()` (Mission 085) puis les 5 guards `confirm_context_change()`. `rename_project()` (ligne 593) l'appelle en ligne 626 comme guard unique (après le seul guard `confirm_no_active_generation()`, ligne 604) — cohérent avec le docstring de la méthode : un renommage ne détruit aucun brouillon texte, seulement un résultat pending.

### 3.2 Ordre LIFO de `addCleanup()` — vérifié

`unittest.TestCase.doCleanups()` exécute les fonctions enregistrées via `addCleanup()` en ordre **LIFO** (dernier enregistré, premier exécuté) — comportement stdlib garanti. `setUp()` enregistre `self.addCleanup(self.window.close)` **avant** l'exécution du corps du test. Si le corps du test enregistre lui-même `self.addCleanup(setattr, self.window.inference_page, "_pending_path", None)` **après** l'assertion confirmant que `_pending_path` reste positionné, ce second cleanup — enregistré plus tard — s'exécute **avant** `window.close()` lors du `doCleanups()` réel. C'est exactement ce mécanisme qui rend le patron ci-dessous sûr.

### 3.3 Le correctif primaire existe déjà, éprouvé, dans le même fichier

`MainWindowInferencePromptGuardTest` (guard Mission 083, `_dirty`, même fichier `test_main_window_new_project.py`, classe immédiatement précédente) rencontre exactement le même risque structurel pour `self.inference_page._dirty` et s'en protège déjà, aux lignes 476 et 586 :
```python
self.addCleanup(setattr, self.window.inference_page, "_dirty", False)
```
enregistré juste après l'assertion `self.assertTrue(self.window.inference_page._dirty)` qui vérifie le comportement réel du guard (Cancel préserve le brouillon). Le même patron protège `prompts_page._dirty` dans `MainWindowConfirmContextChangeTest` (lignes 227, 336). **Ce patron n'a simplement jamais été répliqué pour `_pending_path`** dans les deux classes sœurs traitant le guard Mission 084 — un oubli localisé, pas un mécanisme à concevoir.

Un second patron équivalent, plus direct, existe indépendamment dans `MainWindowCloseEventRealStateTest` (`test_main_window_close_event.py:402`, classe déjà armée du filet Mission 091) : une réaffectation immédiate en ligne, `self.window.inference_page._pending_path = None`, exécutée juste après l'assertion, à 6 endroits (lignes 679, 729, 743, 794, 810, 858) — cette classe manipule un vrai `QThread`, donc une réinitialisation immédiate en ligne (plutôt que différée via `addCleanup`) y est plus naturelle. C'est cette classe déjà auto-protégée qui explique pourquoi elle n'a jamais figuré parmi les 5 occurrences.

**Décision retenue** : pour les deux classes concernées par cette mission, réutiliser le patron `addCleanup(setattr, ...)` — cohérent avec la classe sœur immédiatement adjacente dans le même fichier (`MainWindowInferencePromptGuardTest`), plutôt que le patron de réaffectation en ligne de `MainWindowCloseEventRealStateTest`, structurellement moins adapté ici (ces deux classes ne manipulent aucun thread réel, le style `with patch(...): ... action()` sans variable intermédiaire rend une réaffectation en ligne moins lisible qu'un `addCleanup` placé juste après l'assertion).

### 3.4 Aucun risque de masquer une assertion existante

Le cleanup enregistré via `addCleanup()` ne s'exécute qu'après le retour complet du corps du test (`doCleanups()`, phase de teardown) — jamais avant. Chaque assertion vérifiant que `_pending_path` reste positionné (`self.assertEqual(self.window.inference_page._pending_path, str(generated_path))`) s'exécute et est évaluée **avant** que le cleanup ne soit même atteint. Ajouter ce cleanup ne peut donc jamais masquer ni affaiblir une assertion existante — il agit strictement après que le comportement testé a déjà été vérifié.

### 3.5 Portée : par test concerné, jamais par classe entière

Le correctif est appliqué **uniquement aux tests qui laissent volontairement `_pending_path` non-`None` en fin de scénario fonctionnel** — jamais via un reset inconditionnel en `tearDown()`. Un reset inconditionnel masquerait silencieusement une régression future où un scénario Accept/Reject qui *devrait* normalement vider `_pending_path` échouerait à le faire — exactement le même principe de portée déjà respecté par le patron `_dirty` existant (appliqué uniquement à `test_..._cancel_abandons_..._entirely`, jamais aux tests Save/Discard où le guard réel vide déjà `_dirty` lui-même).

### 3.6 Périmètre exact — recherche exhaustive effectuée

Recherche de `_pending_path`, `confirm_pending_result_change`, `_confirm_pending_before_switch` et `addCleanup(self.window.close)`/`MainWindow()` dans tout `tests/` (4 fichiers au total) :

- **`test_main_window_new_project.py` :: `MainWindowInferencePendingResultGuardTest`** — 12 tests. Exactement 3 laissent `_pending_path` non-`None` en fin de scénario :
  1. `test_new_project_pending_cancel_abandons_new_project_entirely` (assertion ligne 684)
  2. `test_new_project_pending_accept_persistence_failure_refuses_transition` (assertion ligne 709)
  3. `test_open_project_pending_cancel_abandons_open_project_entirely` (assertion ligne 878)

  Les 9 autres tests de cette classe se terminent soit avec `_pending_path` déjà `None` (Accept/Reject réussis, échecs de contexte périmé/fichier disparu qui autorisent déjà la transition), soit ne créent jamais de résultat pending réel (guard directement mocké) — aucun risque, non modifiés.

- **`test_main_window_rename_project.py` :: `MainWindowRenamePendingResultGuardTest`** — 5 tests. Exactement 2 laissent `_pending_path` non-`None` :
  1. `test_pending_cancel_refuses_rename_entirely` (assertion ligne 288)
  2. `test_pending_accept_persistence_failure_refuses_rename_and_keeps_file` (assertion ligne 326)

  Les 3 autres (`test_no_pending_result_never_shows_a_dialog`, `test_pending_reject_deletes_then_renames`, `test_pending_accept_then_real_rename_remaps_path_and_moves_file_physically`) se terminent avec `_pending_path` déjà `None` — non modifiés.

- **`test_main_window_close_event.py` :: `MainWindowCloseEventOrchestrationTest`** — les 4 tests référençant `confirm_pending_result_change` (lignes 179, 202, 245, 289) mockent la méthode guard **elle-même**, jamais `_confirm_pending_before_switch`, et n'appellent jamais `_set_pending()`/`_make_pending_result()` — `_pending_path` reste `None` tout du long, y compris lors du `closeEvent()` réel déclenché plus tard par `addCleanup(self.window.close)`. Structurellement sûrs, non concernés.
- **`test_main_window_close_event.py` :: `MainWindowCloseEventRealStateTest`** — déjà auto-protégée (réaffectation en ligne, §3.3) et déjà armée du filet Mission 091 ; jamais identifiée parmi les 5 occurrences ; non concernée.
- **`test_inference_page.py`** — construit `InferencePage` directement, jamais `MainWindow()` ; aucun `addCleanup(self.window.close)` n'existe dans ce fichier ; le lifetime gap (spécifique à `MainWindow.closeEvent()`) ne peut structurellement pas s'y produire. Non concerné.

**Conclusion** : les 5 occurrences diagnostiquées pendant M093 constituent l'intégralité du défaut structurel — aucune occurrence supplémentaire non détectée n'existe ailleurs dans la suite.

### 3.7 Filet de sécurité Mission 091 — option retenue

Comparaison des 3 options :
- **A (cleanup seul)** : corrige la cause connue avec un risque résiduel non nul — une future régression (nouveau test laissant `_pending_path` non-`None` sans répliquer le cleanup) redeviendrait un blocage silencieux nécessitant une intervention humaine, sans aucun signal automatisé.
- **B (filet seul)** : n'est pas un correctif — le filet Mission 091 (`_DialogGuard.stop()`) lève `UnexpectedDialogError` pour **toute** boîte capturée, connue ou non, sans distinction (contrairement à l'instrumentation diagnostique temporaire de M093, qui distinguait explicitement les deux). Armer le filet sans corriger la cause transformerait donc les 5 tests concernés en échecs **permanents** dès le premier passage, jamais en succès — confirmé par lecture directe de `_DialogGuard.stop()` (`tests/integration/_qt_dialog_safety_net.py:92-105`).
- **C (cleanup + filet)** : le cleanup rend les 5 tests correctement verts (le guard réel devient no-op avant que `window.close()` ne s'exécute) ; le filet, une fois armé, ne capture donc plus rien aujourd'hui — son rôle devient une pure défense en profondeur, gratuite dans l'état actuel, contre toute régression future (nouveau test omettant le cleanup, ou tout autre dialogue réellement inattendu atteignable depuis ces deux classes).

**Stabilité du filet vérifiée** : l'usage par classe (`start_dialog_guard()`/`stop_dialog_guard()` dans `setUp()`/`tearDown()` ou `addCleanup`) est le patron **validé** — déjà utilisé sans incident sur 4 classes existantes (`MainWindowNewOpenGenerationActiveNonRegressionTest`, `MainWindowRenameGenerationActiveGuardTest`, `MainWindowCloseEventRealStateTest`, et les tests dédiés de `test_qt_dialog_safety_net.py`), à travers de multiples exécutions de suite complète depuis Mission 091. Le crash natif observé pendant le diagnostic M093 concernait exclusivement un armement **global, suite-wide**, un usage jamais validé auparavant et catégoriquement différent — non pertinent ici.

**Décision retenue : Option C**, avec responsabilités strictement séparées :
- **Cleanup** (`addCleanup(setattr, self.window.inference_page, "_pending_path", None)`, ajouté aux 5 tests identifiés en §3.6) = ramène la fixture dans un état cohérent *avant* que `window.close()` ne s'exécute — le correctif primaire, celui qui fait rester ces 5 tests verts.
- **Filet Mission 091** (armé sur les deux classes entières via `start_dialog_guard()`/`stop_dialog_guard()`, patron déjà établi) = fait échouer proprement, avec preuve (stack + titre du dialogue), tout futur test de ces deux classes qui laisserait échapper une vraie `QMessageBox` — connue ou non — plutôt que de bloquer silencieusement un écran en attendant un humain.

## 4. Contrat définitif

1. **`tests/integration/test_main_window_new_project.py`, classe `MainWindowInferencePendingResultGuardTest`** : ajouter `self.addCleanup(setattr, self.window.inference_page, "_pending_path", None)` immédiatement après l'assertion confirmant `_pending_path` positionné, dans les 3 tests identifiés en §3.6. Armer `start_dialog_guard()`/`stop_dialog_guard()` sur la classe entière (patron `MainWindowNewOpenGenerationActiveNonRegressionTest`, déjà dans le même fichier).
2. **`tests/integration/test_main_window_rename_project.py`, classe `MainWindowRenamePendingResultGuardTest`** : même correctif sur les 2 tests identifiés, même armement du filet sur la classe entière (patron `MainWindowRenameGenerationActiveGuardTest`, déjà dans le même fichier).
3. **Aucun autre fichier, aucune autre classe, aucun changement à `src/`.**
4. **Preuve de non-régression dédiée** (nouvelle, au moins 1 par classe corrigée) : un test qui (a) laisse volontairement `_pending_path` non-`None` en sortie de scénario fonctionnel comme aujourd'hui, (b) sort explicitement du scope du mock, (c) exécute le cleanup réel (`self.doCleanups()` ou équivalent contrôlé), (d) démontre — via un espion/patch sur `QMessageBox`/`_confirm_pending_before_switch` — qu'aucune construction de dialogue réel n'est atteinte. Les 5 tests corrigés eux-mêmes ne suffisent pas comme preuve : leur succès pourrait aussi bien résulter d'un effet de bord non intentionnel qu'du mécanisme réellement corrigé — la preuve dédiée isole explicitement le mécanisme.
5. **Preuve positive du filet** (si l'armement est confirmé à l'implémentation) : au moins 1 test par classe démontrant qu'un vrai dialogue délibérément déclenché est capturé et transformé en `UnexpectedDialogError` propre par `stop_dialog_guard()` — mirroir du patron déjà établi dans `test_qt_dialog_safety_net.py::QtDialogSafetyNetTest`.
6. **Validation finale** : suite complète exécutée **sans aucune instrumentation diagnostique temporaire** (contrairement à M093) — attendu : suite verte, 0 tentative de dialogue « Génération en attente » provenant des 5 chemins connus, 0 dialogue inattendu, 0 intervention humaine, aucun processus/thread Qt résiduel. Deux exécutions consécutives si possible, comme précédent Mission 091, pour vérifier la stabilité.
7. **Périmètre strict** : `tests/integration/test_main_window_new_project.py` et `tests/integration/test_main_window_rename_project.py` uniquement. Aucun changement `src/`, aucune modification du comportement de production du guard Mission 084, aucun travail LoRA/scopes/moteurs/multi-référence, aucun armement global du filet, aucune refonte générale des fixtures Qt.

## 5. Critères de clôture définitive de cette famille de blocages

- Les 5 tests identifiés restent verts avec le cleanup appliqué.
- La preuve de non-régression dédiée démontre explicitement l'absence de construction de dialogue réel après cleanup.
- Le filet armé sur les deux classes capture 0 dialogue en fonctionnement normal (preuve indirecte que le cleanup couvre bien tous les cas), et la preuve positive confirme qu'il resterait opérant si une régression future en introduisait un.
- Suite complète verte sans instrumentation temporaire, deux exécutions consécutives.
- Aucun changement `src/`.

## 6. État d'avancement

- Mini-audit ciblé : **terminé**, contrat verrouillé ci-dessus.
- Implémentation : **terminée**, strictement conforme au contrat — aucun écart. Cleanup `addCleanup(setattr, self.window.inference_page, "_pending_path", None)` ajouté aux 5 tests identifiés (§3.6), filet de sécurité Mission 091 armé dans `setUp()` des deux classes (`start_dialog_guard()`/`stop_dialog_guard()`), 2 tests de preuve dédiés par classe (lifetime gap + filet).
- **Tests ciblés des deux classes** : `MainWindowInferencePendingResultGuardTest` **14/14 OK** (12 préexistants + 2 nets nouveaux), `MainWindowRenamePendingResultGuardTest` **7/7 OK** (5 préexistants + 2 nets nouveaux).
- **Preuve dédiée du lifetime gap** (`test_pending_cleanup_prevents_real_dialog_reaching_close`, une par classe) : reproduit la séquence défaillante exacte (Cancel → sortie du scope du mock → `self.doCleanups()` réel) avec `QMessageBox` patché au niveau module — `mock_box.assert_not_called()` **passe**, prouvant que `_confirm_pending_before_switch()` n'est jamais atteinte.
- **Preuve dédiée du filet** (`test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure`, une par classe) : un `QMessageBox.warning()` volontaire dans le contexte protégé produit `UnexpectedDialogError` en moins d'une seconde — jamais un blocage.
- **Non-régression ciblée** (`test_main_window_new_project.py` + `test_main_window_rename_project.py` + `test_main_window_close_event.py` + `test_inference_page.py` + `test_qt_dialog_safety_net.py`) : **229/229 OK**.
- **Deux full suites consécutives, sans aucune instrumentation diagnostique temporaire** (contrairement à M093) : **1741/1741 OK** (166.3s) puis **1741/1741 OK** (164.0s) — 1737 préexistants + 4 tests de preuve nets nouveaux. **0 tentative réelle de « Génération en attente » provenant des 5 chemins connus, 0 dialogue inattendu, 0 intervention humaine sur les deux runs**, aucun processus Python résiduel confirmé par `tasklist` après chaque run.
- Aucun écart au contrat verrouillé en section 4.
- `git diff --check` : propre.
- Périmètre respecté à la lettre : uniquement `tests/integration/test_main_window_new_project.py`, `tests/integration/test_main_window_rename_project.py`, ce document — **aucun changement `src/`**.
- Commit de mission : `6f173aebe8789857ed44a4c01a3d5e8ed6303a5f` — "Fix Mission-084 test-cleanup lifetime gap in pending-result guard tests", poussé sur `main`.
- Tag annoté : `v0.2-mission094`, ciblant exactement le commit de mission ci-dessus, poussé.
- GitHub Release `v0.2-mission094` : **publiée manuellement par l'architecte** (`gh` indisponible dans cet environnement) — vérifiée indépendamment via l'API GitHub (`published`, `tag_name: v0.2-mission094`, `target_commitish: main`).
