# Mission 079 — Protect Dirty Drafts on Application Close (MainWindow.closeEvent())

> **MISSION ENTIÈREMENT CLOSE.** 12 tests ciblés nets nouveaux, non-régression complète sur `test_main_window_new_project.py` (17/17), `test_main_window_prompts_to_inference.py` (7/7) et les 6 autres fichiers `MainWindow()` non concernés (32/32), suite complète 1458/1458, smoke test Qt réel exécuté et **PASS** (17/17 assertions, 5 scénarios réels — voir section 6). Commit fonctionnel `<à renseigner après commit>`, tag annoté `v0.2-mission079`, GitHub Release en attente de publication manuelle. Voir section 8 pour l'état de clôture Git.

## 1. Contexte

L'audit réalisé après la clôture de Mission 078 a réévalué directement les interactions avec ce que cette mission venait de livrer (les quatre `confirm_context_change()` sur `PromptsPage`/`CharactersPage`/`LoRAPage`/`SettingsPage`, jusque-là uniquement branchés dans `MainWindow.new_project()`/`open_project()`). Il a trouvé que `MainWindow.closeEvent()` ne consultait aucun des quatre guards et acceptait la fermeture inconditionnellement (`self.inference_page.shutdown(); super().closeEvent(event)`), même en présence d'un brouillon non sauvegardé sur l'une de ces quatre Pages.

Une reproduction empirique réelle (script scratchpad, `MainWindow` réel, Workspace temporaire réel sur disque) a confirmé le bug avant toute implémentation :

```
dirty before close: True
QMessageBox invoked during closeEvent? False
event.isAccepted(): True
theme persisted on disk after close:   (vide — brouillon perdu)
```

Fermer l'application (bouton X, Alt+F4, fermeture OS — aucune action « Quitter » distincte n'existe dans le menu, vérifié) effaçait donc silencieusement tout brouillon non sauvegardé sur `PromptsPage` (Missions 038/069), `CharactersPage`/`LoRAPage`/`SettingsPage` (Mission 078), alors que le même scénario lors d'un changement de Workspace était déjà correctement protégé.

## 2. Objectif

Étendre à `MainWindow.closeEvent()` le même guard `confirm_context_change()` déjà branché dans `new_project()`/`open_project()`, avec exactement le même contrat et le même ordre, sans introduire de transaction globale entre Pages ni de nouveau système de dirty-state.

## 3. Mini-audit contractuel préalable

- **Ordre exact New/Open** (identique dans les deux) : `prompts_page` → `characters_page` → `lora_page` → `settings_page`, `return` immédiat dès le premier `False` ([main_window.py](../../src/ui/main_window.py) — anciennement lignes 456-466/490-500, avant l'ajout de `closeEvent()`).
- **Contrat des quatre `confirm_context_change()`**, vérifié identique par lecture directe du code des 4 Pages : non dirty → `True` immédiat sans dialogue ; Cancel → `False` ; Save réussi → `_dirty = False`, `True` ; Save échoué (`WorkspaceManagerError`) → `QMessageBox.critical()`, resynchronisation via le helper de rechargement inconditionnel propre à chacune (`_load_identity_fields()`/`_force_refresh_lora()`/`_load_settings_fields()`), `False`. Aucune divergence trouvée entre les quatre contrats.
- **Cinquième Page ?** Non. La section « Application » de `SettingsPage` (`python_path_edit`/`comfyui_url_edit`/etc., `ApplicationSettingsManager`) n'a aucun `_dirty` ni `confirm_context_change()` — vérifié volontairement absent, pas un oubli : `ApplicationSettingsManager.update()` n'a qu'un seul appelant dans tout `src/` (cette même section, sur son propre bouton Enregistrer), donc aucune mutation indépendante ne peut jamais écraser ce brouillon — le bug de classe Mission 038/078 ne s'applique structurellement pas ici. Rester hors périmètre, non traité.
- **Cas multi-dirty séquentiel** : confirmé par lecture directe que New/Open n'effectue aucun rollback global — le premier `False` interrompt la chaîne sans jamais annuler un Save déjà effectué sur une Page précédente. Mission 079 reproduit exactement cette sémantique.
- **Position de `inference_page.shutdown()`** : confirmé appelé inconditionnellement en premier, avant tout ce qui deviendrait les 4 guards — devait être déplacé après eux.

Aucune anomalie sur ces quatre points. Une anomalie distincte a en revanche été détectée et rapportée avant implémentation (voir section 4).

## 4. Anomalie détectée et actée avant implémentation : effet de bord sur les tests préexistants

Le pattern `MainWindow()` + `self.addCleanup(self.window.close)` est utilisé dans 8 fichiers de tests. Avant cette mission, `window.close()` en fin de test était inoffensif (`closeEvent()` ne consultait rien). Une fois les 4 guards ajoutés, tout test laissant une Page dirty à la fin déclencherait un vrai `QMessageBox.exec()` bloquant pendant le teardown implicite — un risque de blocage du process de test, aucun utilisateur n'étant présent pour cliquer.

Vérification exhaustive des 8 fichiers concernés :

- [test_main_window_new_project.py](../../tests/integration/test_main_window_new_project.py) : 2 tests laissent délibérément `prompts_page._dirty = True` en fin de test (`test_new_project_dirty_cancel_abandons_new_project_entirely`, `test_open_project_dirty_cancel_abandons_open_project_entirely` — le scénario Cancel est le point même du test).
- [test_main_window_prompts_to_inference.py](../../tests/integration/test_main_window_prompts_to_inference.py) : les 7 tests appellent `prompts_page.text_edit.setPlainText(...)` sans jamais sauvegarder ni ouvrir de Workspace — aucun n'exerce le dirty-state lui-même, mais tous laissent `_dirty = True` comme effet de bord.
- Les 6 autres fichiers `MainWindow()` (`comfyui_settings`, `ollama_settings`, `rename_project`, `initial_size`, `dashboard_page`, `main_toolbar`) ne touchent à aucun champ dirty-trackable — aucun risque, confirmé par grep ciblé et par exécution réelle après implémentation.

Validé explicitement par l'architecte comme faisant partie du périmètre de Mission 079 (adaptation de non-régression nécessaire au nouveau contrat de `closeEvent()`, pas un élargissement fonctionnel).

## 5. Implémentation

**`MainWindow.closeEvent()`** ([main_window.py](../../src/ui/main_window.py)) : les quatre guards sont désormais interrogés dans le même ordre que New/Open, avant tout code de fermeture. Dès qu'un guard retourne `False` : `event.ignore()` puis `return` immédiat — les guards suivants ne sont jamais appelés, et `inference_page.shutdown()` n'est jamais atteint. Si les quatre retournent `True`, le comportement de fermeture reste exactement celui d'avant cette mission (`shutdown()` puis `super().closeEvent(event)`).

Les docstrings des quatre `confirm_context_change()` (`PromptsPage`, `CharactersPage`, `LoRAPage`, `SettingsPage`) ont été complétées d'une phrase mentionnant ce nouvel appelant, sans aucun changement de comportement.

**Adaptation des 9 tests préexistants concernés** (section 4) :
- Les 2 tests Cancel de `test_main_window_new_project.py` conservent intégralement leurs assertions existantes (`_dirty == True` après l'abandon reste vérifié) ; un `self.addCleanup(setattr, self.window.prompts_page, "_dirty", False)` est ajouté juste après ces assertions — enregistré après celui de `setUp()`, il s'exécute donc en premier (LIFO), neutralisant uniquement le `window.close()` de fin de test sans jamais toucher à l'état vérifié par le test lui-même.
- Les 7 tests de `test_main_window_prompts_to_inference.py`, qui ne testent pas le dirty-state, reçoivent la même neutralisation directement dans `setUp()` (un seul ajout, pour toute la classe) — aucune assertion fonctionnelle modifiée.

Aucun changement de code de production pour « détecter » les tests ; `closeEvent()` reste un chemin utilisateur réel, non contourné.

## 6. Tests automatisés et smoke test Qt réel

**12 tests ciblés nets nouveaux** (`tests/integration/test_main_window_close_event.py`), en deux classes :

- `MainWindowCloseEventOrchestrationTest` (7 tests, guards mockés) : tous les guards `True` → fermeture acceptée et `inference_page.shutdown()` appelé ; chacun des quatre guards retournant `False` individuellement → fermeture refusée, `event.ignore()`, les guards suivants et `shutdown()` jamais appelés ; ordre des quatre guards identique à New/Open ; `shutdown()` n'intervient qu'après résolution des quatre guards.
- `MainWindowCloseEventRealStateTest` (5 tests, état réel — Workspace/Manager réels sur disque, seuls les `QMessageBox` mockés) : aucune Page dirty → fermeture immédiate sans aucun dialogue ; brouillon Settings réel + Cancel → fermeture refusée, brouillon intact ; brouillon Settings réel + Save → fermeture acceptée, valeur réellement persistée dans `project.json` ; échec réel de `SettingsManager.update()` + Save → fermeture refusée, champ resynchronisé à la valeur restaurée (contrat Mission 077 inchangé) ; deux Pages dirty simultanément (Prompts Save réussi, puis Characters Cancel) → fermeture refusée, mais la sauvegarde déjà effectuée sur Prompts n'est jamais annulée (sémantique séquentielle, pas de transaction globale).

**Non-régression complète** : `test_main_window_new_project.py` (17/17 — 15 précédents + 2 adaptés sans changement d'assertion), `test_main_window_prompts_to_inference.py` (7/7, `setUp()` adapté sans changement d'assertion), et les 6 autres fichiers `MainWindow()` non concernés (`test_main_window_initial_size.py`, `test_main_window_comfyui_settings.py`, `test_main_window_ollama_settings.py`, `test_dashboard_page.py`, `test_main_window_rename_project.py`, `test_main_toolbar.py` — 32/32 au total), tous exécutés réellement pour confirmer l'absence de tout blocage.

**Suite complète : 1458/1458** (1446 précédents + 12 nets nouveaux), une exécution complète `unittest discover`, 141.5s, aucun crash, aucun blocage. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.

**Smoke test Qt réel** — exécuté par Claude, `MainWindow`/`SettingsPage`/`CharactersPage`/`PromptsPage`/Managers réels contre des Workspaces temporaires réels sur disque, **PASS, 17/17 assertions**, 5 scénarios réels :
1. Brouillon réel (saisie effective dans `theme_edit`) → Cancel → fermeture refusée, fenêtre reste ouverte, brouillon intact et toujours dirty.
2. Brouillon réel → Save → fermeture acceptée, valeur réellement écrite dans `project.json`.
3. Brouillon réel → Discard → fermeture acceptée, brouillon jamais persisté.
4. Échec réel de persistence injecté + Save → fermeture refusée, champ resynchronisé à la valeur restaurée, dirty effacé par le resync forcé (contrat Mission 077).
5. Deux Pages dirty simultanément (Prompts + Characters) → Prompts sauvegardé avec succès, puis Characters annule → fermeture refusée, mais le prompt déjà sauvegardé reste réellement persisté sur disque, et le brouillon Characters reste intact.

## 7. Conclusion

Le brouillon non sauvegardé sur `PromptsPage`/`CharactersPage`/`LoRAPage`/`SettingsPage` est désormais protégé de la même façon lors d'un changement de Workspace (Missions 069/078) et lors de la fermeture complète de l'application. Aucune transaction globale introduite, aucun nouveau système de dirty-state, aucune nouvelle action « Quitter »/« Fermer le projet », aucun changement Domain/Manager. Périmètre strictement limité à `MainWindow.closeEvent()` et à l'adaptation de non-régression des 9 tests préexistants directement affectés par ce nouveau contrat.

## 8. État d'avancement et clôture Git

- Mini-audit contractuel préalable : **terminé, aucune anomalie sur les 4 points demandés**.
- Anomalie de non-régression sur les tests préexistants : **détectée avant implémentation, rapportée, validée par l'architecte comme incluse dans le périmètre**.
- Implémentation : **réalisée**, strictement limitée à `closeEvent()` et aux docstrings des 4 `confirm_context_change()`.
- Tests automatisés : **exécutés, verts — 12/12 ciblés nets nouveaux, non-régression complète des fichiers concernés**.
- Suite complète : **1458/1458, aucun crash, aucun blocage**.
- `git diff --check` : **propre** (seuls des avertissements de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme** (2 fichiers de production + 4 docstrings + 2 fichiers de tests adaptés + 1 nouveau fichier de tests + ce document de mission).
- Smoke test Qt réel : **réalisé, PASS, 17/17 assertions, 5 scénarios réels**.
- Clôture Git (commit/tag/Release) : **en cours**.
