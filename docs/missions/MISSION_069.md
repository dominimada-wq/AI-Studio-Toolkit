# Mission 069 — Protect PromptsPage Draft Before New/Open Project

> **STATUT : MISSION FONCTIONNELLEMENT VALIDÉE PAR L'ARCHITECTE, IMPLÉMENTATION TERMINÉE.** 17 tests ciblés nets nouveaux, suite complète 1179/1179, smoke test Qt réel exécuté et **PASS** (24/24 assertions, 8 scénarios réels dont New/Open × Save/Discard/Cancel, échec de persistence, et annulation du picker). Voir section 11 pour l'état de clôture Git.

## 1. Contexte

L'audit mené après Mission 068 a démontré empiriquement (reproduction Python réelle) qu'un brouillon `PromptsPage` non sauvegardé était silencieusement perdu lors d'un `MainWindow.new_project()`/`open_project()` : `WorkspaceManager.create()`/`.open()` remplacent `current_workspace` **avant** de publier `WORKSPACE_CREATED`/`WORKSPACE_OPENED`, événements auxquels `PromptsPage.reset_for_context_change()` est abonné — au moment où ce handler s'exécute, le contexte a déjà changé, rendant un Save ou un Cancel structurellement impossibles à ce stade. Mission 038 protège déjà la navigation prompt-à-prompt et la suppression via un dialogue Save/Discard/Cancel (`_confirm_discard_before_switch()`), mais jamais les deux seuls chemins réellement atteignables par un utilisateur qui détruisent le contexte Workspace : `new_project()` et `open_project()`.

## 2. Objectif

Garantir qu'un brouillon `PromptsPage` non sauvegardé ne soit plus jamais perdu silencieusement lors d'un `New Project`/`Open Project` — en réutilisant, sans le dupliquer, le pattern Save/Discard/Cancel déjà établi par Mission 038.

## 3. Contrat implémenté

**`PromptsPage.confirm_context_change() -> bool`** (nouvelle méthode publique, seule addition à l'API de la Page) :
- Pas de brouillon dirty → retourne `True` immédiatement, **aucun dialogue** — New/Open se comporte exactement comme avant.
- Dirty → affiche le dialogue **existant** `_confirm_discard_before_switch()` (réutilisé verbatim, aucune logique dupliquée) :
  - **Cancel** → retourne `False`. Aucune mutation locale : Workspace, Prompt actif, texte de l'éditeur et `_dirty` restent strictement inchangés.
  - **Discard** → retourne `True` sans persister. Le nettoyage (`text_edit` vidé, `_dirty=False`, liste reconstruite) reste entièrement assuré par `reset_for_context_change()`, déjà déclenché normalement une fois le nouveau Workspace chargé — aucune duplication de ce nettoyage dans le nouveau hook.
  - **Save** → `prompt_manager.update_text()` est appelé pendant que l'**ancien** Workspace est encore actif (persistance réelle dans l'ancien projet) ; en cas de succès, `_dirty=False` et retourne `True` ; en cas d'échec (`WorkspaceManagerError`), affiche `QMessageBox.critical()`, retourne `False`, **`_dirty` reste `True`** — l'échec de persistence ne permet jamais au changement de Workspace de continuer.

**`MainWindow.new_project()`/`open_project()`** : un appel d'une ligne à `self.prompts_page.confirm_context_change()` inséré **après** l'acceptation du sélecteur (`NewProjectDialog`/`QFileDialog.getExistingDirectory`) et **avant** tout appel à `workspace_manager.create()`/`.open()`. Si le sélecteur est annulé par l'utilisateur, le guard n'est **jamais** appelé — aucun dialogue dirty-state superflu. Les deux chemins réutilisent le même appel, sans abstraction supplémentaire.

## 4. Hors périmètre (explicitement confirmé, non traité)

- Le défaut préexistant de `on_prompt_selection_changed()` : un `update_text()` en échec pendant un changement prompt→prompt n'est pas intercepté (`_dirty` reste bloqué à `True` sans message, exception silencieusement absorbée par Qt) — candidat futur distinct, non traité ici.
- Le cas `_dirty=True` sans Prompt actif (texte généré par le Prompt Assistant, jamais rattaché) : `update_text()` y est un no-op silencieux, comportement hérité de Mission 038, non aggravé ni corrigé par M069.
- `WorkspaceManager.close()` (jamais appelé depuis `src/ui/`), changements de Character masqués (`CharactersPage` UI cachée), fermeture générale de l'application (`closeEvent()`) — tous vérifiés inatteignables par un utilisateur réel aujourd'hui, donc sans impact sur la complétude du correctif.
- Créations Domain-only sans rollback — candidat A distinct, conservé pour un audit futur.
- Aucun framework générique de dirty-state/veto introduit — `PromptsPage` reste la seule Page concernée aujourd'hui.

## 5. Détail technique vérifié pendant l'implémentation

`PromptManager.update_text()` mute `prompt.text` en mémoire **avant** `save()`, sans rollback en cas d'échec — dette Domain-only déjà identifiée par l'audit post-Mission 068 (candidat B1, hors périmètre M069). Un test rédigé pendant cette mission a d'abord supposé à tort que `prompt.text` serait restauré après un échec de Save ; corrigé pour vérifier uniquement ce que M069 garantit réellement : `project.json` (l'état persisté réel) reste inchangé, `_dirty` reste `True`, et le changement de Workspace n'a jamais lieu — le contrat de M069 porte sur le **guard du changement de contexte**, pas sur le rollback interne de `update_text()`.

## 6. Risques

- **Risque de régression fonctionnelle** : très faible — insertion d'un unique early-return avant toute mutation, aucune modification de `reset_for_context_change()`, `PromptManager`, ou de toute autre Page. Le test existant `test_reset_for_context_change_clears_dirty_draft_on_workspace_close` (qui appelle `workspace_manager.close()` directement, hors `MainWindow`) reste inchangé et vert, confirmant que M069 est strictement additif à la couche réactive déjà existante.

## 7. Pourquoi maintenant

Défaut de perte de travail utilisateur réellement démontré (reproduction Python + test Qt réel), périmètre extrêmement borné (2 méthodes `MainWindow` + 1 méthode `PromptsPage`), décision UX déjà fixée par un précédent interne direct (Mission 038) — retenu comme candidat A prioritaire à l'issue de l'audit post-Mission 068.

## 8. Tests automatisés ajoutés

**17 tests nets nouveaux** :

- `tests/integration/test_prompt_roundtrip.py`, `PromptsPageConfirmContextChangeTest` (5) : pas de dirty → `True` sans dialogue ; Save réussi → texte persisté dans l'ancien Workspace, `True`, `_dirty=False` ; Discard → `True`, rien persisté ; Cancel → `False`, tout inchangé (Workspace, Prompt actif, texte éditeur, `_dirty`) ; Save en échec → `QMessageBox.critical` affiché, `False`, `_dirty` toujours `True`, `project.json` inchangé.
- `tests/integration/test_main_window_new_project.py`, `MainWindowConfirmContextChangeTest` (12, réel `MainWindow` avec deux dossiers de projet réels) : `new_project()`/`open_project()` × Save/Discard/Cancel (persistance/absence de persistance dans l'ancien `project.json` vérifiée réellement, Workspace effectivement switché ou non) ; guard retournant `False` → `create()`/`open()` jamais appelé ; picker annulé → guard jamais appelé ; ordre d'exécution guard-avant-`create()`/`open()` vérifié explicitement via une liste d'ordre partagée.

Comportement observable testé (fichiers réels sur disque, `project.json` réellement relu, widgets Qt réels), jamais l'existence interne d'un mécanisme.

## 9. Vérifications finales — réellement exécutées

**Tests ciblés** — **17/17 nets nouveaux PASS**. Non-régression complète des fichiers touchés — **112/112 PASS** (`test_prompt_roundtrip.py` + `test_main_window_new_project.py` + `test_main_window_rename_project.py`).

`git diff --check` : propre, aucun avertissement de contenu.

**Périmètre du diff** : exactement 4 fichiers — `src/ui/pages/prompts_page.py`, `src/ui/main_window.py` (production), et leurs 2 fichiers de tests correspondants. Aucun autre fichier Domain/Manager/Page touché.

## 10. Suite complète

**1179/1179 tests verts** (1162 précédents + 17 nets nouveaux), une exécution complète `unittest discover`, aucun crash, aucun échec. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet apportée.

## 11. Smoke test Qt réel — exécuté par Claude, écran non mocké

`MainWindow` réel, `PromptsPage` réelle, Managers réels, fichiers réels sur disque, `project.json` réellement relu à chaque étape. Seuls les dialogues modaux (`NewProjectDialog`, `QFileDialog.getExistingDirectory`, le `QMessageBox` interne Save/Discard/Cancel de `PromptsPage`) sont mockés pour éviter un blocage.

1. **New Project — Save** : brouillon réellement persisté dans l'ancien `project.json`, Workspace effectivement switché.
2. **New Project — Discard** : Workspace switché, ancien `project.json` inchangé.
3. **New Project — Cancel** : Workspace inchangé, dossier cible jamais créé, brouillon toujours dirty et visible, Prompt actif préservé.
4. **New Project — échec de Save injecté** : message d'erreur affiché, Workspace inchangé, dossier cible jamais créé, brouillon toujours dirty.
5. **New Project — picker annulé** : guard jamais invoqué, brouillon intact.
6. **Open Project — Save/Discard/Cancel** : mêmes garanties que New Project, vérifiées sur les trois choix avec un second projet réel pré-créé indépendamment.

**Verdict : PASS**, 24/24 assertions vérifiées (`m069_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## État d'avancement

- Décision de périmètre (hook minimal Prompt-specific, aucun framework générique) : **validée par l'architecte** à l'issue du mini-audit contractuel dédié.
- Implémentation : **réalisée, conforme au contrat** — `confirm_context_change()` sur `PromptsPage`, câblage `MainWindow.new_project()`/`open_project()`.
- Tests automatisés : **exécutés, verts — 17/17 ciblés nets nouveaux, 112/112 non-régression complète**.
- Suite complète : **1179/1179, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (4 fichiers exactement, aucun fichier hors périmètre touché)**.
- Smoke test Qt réel : **réalisé, PASS, 8 scénarios réels couverts** (section 11).
- Clôture Git (commit/tag/Release) : **en cours**.
