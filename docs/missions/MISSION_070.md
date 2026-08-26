# Mission 070 — Rollback Scalar Domain-Only Mutations on Persistence Failure

> **MISSION ENTIÈREMENT CLOSE.** 56 tests ciblés nets nouveaux, suite complète 1235/1235, smoke test Qt réel exécuté et **PASS** (40/40 assertions, 7 scénarios réels : 6 renommages, 2 chemins de fichiers Model/Workflow, cas complet Prompt→Prompt). Commit fonctionnel `a9e162473379c8c54fa214fdcda423e1580a1c4d`, tag annoté `v0.2-mission070`, GitHub Release publiée. Voir section 11 pour l'état de clôture Git final.

## 1. Contexte

L'audit post-Mission 069 a démontré, par reproduction Python et Qt réelle, qu'un groupe homogène de 10 méthodes Domain-only mutent un scalaire **avant** `WorkspaceManager.save()`, sans aucun rollback en cas d'échec de persistence. Un mini-audit contractuel dédié a ensuite précisé ce groupe et démontré empiriquement deux conséquences concrètes : (1) une mutation « fantôme » reste résidente en mémoire après un échec, silencieusement persistable par un `save()` ultérieur sans rapport ; (2) le garde d'idempotence (`if old == new: return False`), légitime pour éviter un `save()` redondant, neutralise également tout retry identique après un premier échec — puisque la valeur en mémoire a déjà été mutée, un second appel avec la même valeur ne relève même plus l'exception, il retourne silencieusement `False` sans tenter `save()`.

Le mini-audit a également isolé un cas prioritaire : `PromptsPage.on_prompt_selection_changed()`, où un changement de Prompt avec un brouillon dirty et un choix « Enregistrer » qui échoue laisse Qt avec une sélection visuelle déjà avancée (`currentItem()` pointe le nouveau Prompt) alors que `active_prompt_id`/`_loaded_prompt_id` restent bloqués sur l'ancien — une divergence UI/Domain réelle, reproduite avec un `EventBus` réel.

## 2. Objectif

Éliminer, pour les 9 méthodes retenues (Option B du mini-audit), la mutation fantôme et ses deux conséquences : persistence silencieuse ultérieure, et retry identique neutralisé par le garde d'idempotence — sans jamais toucher au système dirty-state de Missions 038/069, ni introduire de framework transactionnel générique.

## 3. Périmètre exact

**Renommages** (6) : `DatasetManager.update_name()`, `LoRAManager.update_name()`, `ModelManager.update_name()`, `TrainingManager.update_name()`, `WorkflowManager.update_name()`, `PromptManager.update_name()`.

**Chemins de fichiers** (2) : `ModelManager.update_file_path()`, `WorkflowManager.update_file_path()`.

**Texte Prompt** (1) : `PromptManager.update_text()`, avec ses 3 call sites Presentation réels (`on_prompt_selection_changed()`, `confirm_context_change()` — déjà protégé depuis Mission 069, `save_text()`).

Handlers Presentation correspondants : `rename_dataset()`, `rename_lora()`, `rename_model()`, `rename_training()`, `rename_workflow()`, `rename_prompt()`, `choose_model_file()`, `choose_workflow_file()`, `on_prompt_selection_changed()`, `save_text()`.

## 4. Contrat Manager

Pour chacune des 9 méthodes :
```python
old = obj.field
if old == new:
    return False          # garde d'idempotence inchangé
obj.field = new
try:
    self._workspace_manager.save()
except WorkspaceManagerError:
    obj.field = old       # rollback exact, même objet, aucun autre champ touché
    raise                 # aucun événement de succès publié
return True
```
Aucun snapshot Workspace global, aucun mécanisme filesystem, aucune abstraction transactionnelle partagée — chaque Manager implémente son propre rollback local, comme pour M066/067/068.

## 5. Contrat Presentation

Pour les 6 renommages : `try/except WorkspaceManagerError` autour de l'appel `update_name()`, affichage `QMessageBox.critical()`, puis appel au `update_*()` de la Page déjà existant (jamais de restauration manuelle du widget) — le Domain étant rollBacké avant l'exception, ce refresh redessine automatiquement `name_edit` avec l'ancienne valeur.

Pour les 2 chemins de fichiers : le mini-audit a démontré empiriquement que `file_path_edit` n'est jamais pré-muté visuellement (il n'est peuplé que par le refresh d'événement, jamais directement par le picker) — `try/except` + `QMessageBox.critical()` suffit, sans besoin de rappel explicite à `update_*()` pour la cohérence visuelle (mais l'ajouter reste inoffensif et uniforme avec les autres handlers).

Pour `PromptsPage.on_prompt_selection_changed()` (cas prioritaire) : `try/except WorkspaceManagerError` autour de l'appel `update_text()` dans la branche Save, réutilisant **exactement** le mécanisme déjà existant pour Cancel (`blockSignals(True)` → `setCurrentItem(previous)` → `blockSignals(False)` → `delete_button.setEnabled(previous is not None)`), plus `QMessageBox.critical()`, puis `return` immédiat — `select()` n'est jamais atteint, donc `active_prompt_id`/`_loaded_prompt_id` n'ont besoin d'aucune restauration explicite (ils n'ont jamais changé).

Pour `PromptsPage.save_text()` : `try/except WorkspaceManagerError` + `QMessageBox.critical()` ; `_dirty` reste `True` (déjà le cas aujourd'hui puisque l'exception empêchait déjà d'atteindre `self._dirty = False`).

## 6. Hors périmètre (explicitement exclu)

`LoRAManager.update()` (4 métadonnées, cycle Presentation par bouton multi-champs — contrat distinct, reporté) ; créations Domain-only (candidat futur, non prédéterminé) ; `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `CharacterManager.update()` (UI cachée, inatteignable) ; miniature LoRA orpheline ; segfault Qt/PySide6 ; toute abstraction transactionnelle générique.

## 7. Risques

Faible — chaque méthode reçoit un rollback strictement local (capture d'une seule ancienne valeur, restauration identique), aucune modification de la logique de garde d'idempotence existante pour les cas légitimes (valeur déjà persistée), aucune modification du système dirty-state de `PromptsPage`.

## 8. Tests automatisés

Pour chacune des 9 méthodes Manager : succès inchangé, échec `save()` → ancienne valeur restaurée (même instance, `assertIs`), `project.json` inchangé, aucun événement de succès publié, retry avec la même valeur précédemment refusée constitue une tentative réelle après rollback. Pour les 6 renommages Presentation : erreur affichée, widget restauré à l'ancienne valeur via le refresh existant. Pour les 2 chemins de fichiers : erreur affichée, pas de divergence visuelle à corriger. Pour `on_prompt_selection_changed()` : scénario complet (brouillon dirty → sélection d'un autre Prompt → Save → échec → sélection visuelle restaurée → `active_prompt_id`/`_loaded_prompt_id` inchangés → texte utilisateur conservé → `_dirty=True` → `Prompt.text` rollbacké → `project.json` inchangé → retry ultérieur réussi). Pour `save_text()` : erreur affichée, aucune mutation fantôme.

## 9. Smoke test Qt réel — exécuté par Claude, écran non mocké

`DatasetsPage`/`LoRAPage`/`ModelsPage`/`WorkflowsPage`/`TrainingPage`/`PromptsPage` réels, Managers réels, Workspace temporaire réel sur disque, `project.json` réellement relu.

1. **Dataset rename** — échec de save() → erreur affichée, `Dataset.name` rollBacké, `name_edit` restauré, `project.json` inchangé ; retry réussi et persisté.
2. **LoRA rename** — mêmes garanties.
3. **Model rename + update_file_path()** — rename : mêmes garanties. File path : erreur affichée, `Model.file_path` rollBacké, `file_path_edit` n'a jamais montré la valeur rejetée (jamais pré-muté), retry réussi.
4. **Workflow rename + update_file_path()** — mêmes garanties que Model.
5. **Training rename** — mêmes garanties.
6. **Prompt rename** — mêmes garanties.
7. **Prompt → Prompt, brouillon dirty, Save en échec** — erreur affichée, sélection visuelle restaurée sur l'ancien Prompt (mécanisme identique à Cancel), `active_prompt_id`/`_loaded_prompt_id` inchangés, texte édité conservé, `_dirty=True`, `Prompt.text` rollBacké (aucune mutation fantôme), `project.json` inchangé ; retry ultérieur réussi (`select()` du nouveau Prompt, persistence réelle de l'ancien).

**Verdict : PASS**, 40/40 assertions vérifiées (`m070_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## 10. Vérifications finales — réellement exécutées

- **Tests ciblés** : **56/56 nets nouveaux PASS** (répartis sur les 6 fichiers de tests concernés).
- **Non-régression complète des fichiers touchés** : **457/457 PASS** (`test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_model_roundtrip.py` + `test_workflow_roundtrip.py` + `test_training_roundtrip.py` + `test_prompt_roundtrip.py` + `test_main_window_new_project.py` + `test_main_window_rename_project.py`).
- **Suite complète** : **1235/1235** (1179 précédents + 56 nets nouveaux), une exécution complète `unittest discover`, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet apportée.
- **`git diff --check`** : propre, aucun avertissement de contenu (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 19 fichiers — 6 Managers, 6 Pages, 6 fichiers de tests, 1 nouveau document de mission. Aucun autre fichier Domain/UI touché.

## État d'avancement

- Spécification : **validée par l'architecte** à l'issue du mini-audit contractuel dédié.
- Implémentation : **réalisée, conforme au contrat** — rollback local sur les 9 méthodes, traitement Presentation des 10 handlers concernés, réutilisation exacte du mécanisme Cancel pour le cas Prompt→Prompt.
- Tests automatisés : **exécutés, verts — 56/56 ciblés nets nouveaux, 457/457 non-régression complète**.
- Suite complète : **1235/1235, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (19 fichiers exactement)**.
- Smoke test Qt réel : **réalisé, PASS, 7 scénarios réels couverts, 40/40 assertions** (section 9).
- Clôture Git (commit/tag/Release) : **terminée** (section 11).

## 11. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `a9e162473379c8c54fa214fdcda423e1580a1c4d` (`feat: rollback scalar Domain-only mutations on persistence failure`), 19 fichiers modifiés (6 Managers, 6 Pages, 6 fichiers de tests, 1 nouveau `docs/missions/MISSION_070.md`), 1359 insertions(+), 27 suppressions(-). Poussé sur `origin/main` (`3903546..a9e1624`), divergence `0 0` vérifiée avant et après le push.
- **Tag annoté** : `v0.2-mission070` (message « Mission 070 - Rollback Scalar Domain-Only Mutations on Persistence Failure »), créé sur et poussé pour `a9e162473379c8c54fa214fdcda423e1580a1c4d`. Vérifié via `git ls-remote --tags origin v0.2-mission070 "v0.2-mission070^{}"` — objet tag `ea402833a01927a1f8b3fd90dd78f194e14c4a8b`, peeled sur `a9e162473379c8c54fa214fdcda423e1580a1c4d`, correspondance exacte confirmée localement et à distance.
- **GitHub Release** : `v0.2-mission070 — Rollback Scalar Domain-Only Mutations on Persistence Failure`, rédigée par Claude (Release Notes en anglais conformément à la convention permanente depuis Mission 024) et **publiée manuellement par l'architecte**.
- **État Git final vérifié lors de la régularisation post-Release** : working tree propre, `HEAD == origin/main == a9e162473379c8c54fa214fdcda423e1580a1c4d`, divergence `0 0`, tag `v0.2-mission070` intact et toujours attaché au commit fonctionnel (non déplacé par la régularisation documentaire qui suit dans un commit séparé).
