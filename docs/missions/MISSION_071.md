# Mission 071 — Rollback PromptManager.delete() on Persistence Failure

> **MISSION ENTIÈREMENT CLOSE.** 10 tests ciblés nets nouveaux, suite complète 1245/1245, smoke test Qt réel exécuté et **PASS** (24/24 assertions, 3 scénarios réels : suppression normale, échec de persistence + retry, brouillon dirty préservé après échec). Commit fonctionnel `33101ef9bbe1628a6c6c0e48405d8787b330d31c`, tag annoté `v0.2-mission071`, GitHub Release publiée. Voir section 12 pour l'état de clôture Git final.

## 1. Contexte

L'audit post-Mission 070 a révélé que Mission 068 (« Rollback Domain-Only Deletions on Persistence Failure ») énonce explicitement son périmètre comme portant sur **cinq** Managers — `DatasetManager.delete()`, `LoRAManager.delete()`, `ModelManager.delete()`, `TrainingManager.delete()`, `WorkflowManager.delete()` — et ne mentionne `PromptManager.delete()` nulle part, y compris dans sa section « Hors périmètre », qui liste pourtant explicitement `CharacterManager.delete()` comme exclusion volontaire. `PromptManager.delete()` n'a donc jamais été analysé ni corrigé par Mission 068 : ce n'est pas une exclusion délibérée, c'est un oubli d'audit.

Une reproduction empirique réelle (script Python, scratchpad de session) a confirmé que `PromptManager.delete()` suit exactement le motif pré-Mission 068 : retrait de `character.prompts` en mémoire → `WorkspaceManager.save()` sans aucun `try/except`. Un échec de `save()` laisse la suppression appliquée en mémoire sans que `project.json` ne soit modifié et sans aucun message d'erreur (le handler Presentation `PromptsPage.delete_prompt()` n'intercepte rien) ; une sauvegarde ultérieure totalement indépendante (ex. créer un autre Prompt) persiste alors silencieusement la suppression jamais confirmée avec succès.

## 2. Objectif

Compléter la famille transactionnelle déjà établie par Mission 068 en y ajoutant son sixième membre manquant, `PromptManager.delete()`, avec le contrat de rollback **rigoureusement identique** — sans nouvelle abstraction, sans élargissement de périmètre.

## 3. Mini-audit contractuel préalable

Relecture intégrale de `PromptManager.delete()`, de `PromptsPage.delete_prompt()`, du cycle complet `delete_prompt() → PromptManager.delete() → WorkspaceManager.save() → PROMPT_DELETED → PromptsPage.update_prompts()`, et des tests Prompt existants issus de Missions 038/063/069/070. Constats :

- `PromptManager.delete()` ne porte **aucun guard métier** supplémentaire (contrairement à `DatasetManager.delete()` et sa garde `is_referenced_by_training()`) — le port du contrat M068 est donc plus simple que le cas général, jamais plus complexe.
- `PromptsPage.delete_prompt()` affiche un dialogue Discard/Cancel (Mission 038) **uniquement** si `self._dirty` est vrai, **avant** tout appel à `prompt_manager.delete()` — une pré-condition entièrement indépendante du chemin de persistence, jamais modifiée par cette mission.
- Le retrait visuel de la ligne dans `prompt_list` ne se produit **que** réactivement, via l'abonnement de `PromptsPage.update_prompts()` à `PROMPT_DELETED` (câblé dans `MainWindow`, seul abonné à cet événement dans tout le projet). Cet événement n'est jamais publié en cas d'échec — donc le Prompt reste présent et sélectionnable dans la liste sans qu'aucun code Presentation supplémentaire ne soit nécessaire (contrairement aux renommages Mission 070, où `name_edit` était déjà pré-muté par la frappe de l'utilisateur et nécessitait un rafraîchissement explicite).
- Aucune interférence possible avec `on_prompt_selection_changed()` (Mission 070) ni `confirm_context_change()` (Mission 069) : ces deux mécanismes portent exclusivement sur `update_text()`, un chemin de code entièrement distinct de `delete()`.
- Le test existant `PromptsPageDeleteButtonStateTest.test_disabled_after_deleting_the_selected_prompt` couvre uniquement le chemin de succès (aucun mock de `save()`) — reste vert sans modification.
- `PromptManager.delete(prompt_id)` accepte un identifiant explicite (comme les 5 autres `delete()`), et non uniquement le Prompt actif — un appel Manager direct sur un Prompt non-actif est donc un scénario réel et testable, distinct du seul chemin Presentation (qui ne supprime jamais que la sélection courante).

**Conclusion du mini-audit** : le contrat Mission 068 se porte sur Prompt sans aucune adaptation, sans nouvelle décision produit ni architecturale. Implémentation autorisée à procéder directement.

## 4. Périmètre exact

- `src/managers/prompt_manager.py` — `PromptManager.delete()`.
- `src/ui/pages/prompts_page.py` — `PromptsPage.delete_prompt()`.
- `tests/integration/test_prompt_roundtrip.py` — tests Manager + Presentation.
- `docs/missions/MISSION_071.md` — ce document.

Aucun autre fichier touché. Explicitement hors périmètre (confirmé par l'architecte) : `create()` Domain-only, `LoRAManager.update()`, `SettingsManager.update()`, fichiers/dossiers orphelins Dataset/LoRA, segfault Qt/PySide6, `CharacterManager.delete()`, toute abstraction transactionnelle générique.

## 5. Contrat Manager

```python
def delete(self, prompt_id: str) -> bool:

    character = self._character_manager.principal_character

    if character is None:
        return False

    prompt = self._find(prompt_id)

    if prompt is None:
        return False

    index = character.prompts.index(prompt)
    previous_active_prompt_id = self.active_prompt_id

    character.prompts.remove(prompt)

    if self.active_prompt_id == prompt_id:
        self.active_prompt_id = None

    try:
        self._workspace_manager.save()
    except WorkspaceManagerError:
        character.prompts.insert(index, prompt)
        self.active_prompt_id = previous_active_prompt_id
        raise

    self._publish(PROMPT_DELETED, prompt)

    return True
```

Rollback purement local (même objet Python réinséré à son index exact, `active_prompt_id` restauré), aucun snapshot du Workspace, aucune opération filesystem — rigoureusement identique aux 5 Managers déjà corrigés par Mission 068.

## 6. Contrat Presentation

`PromptsPage.delete_prompt()` intercepte `WorkspaceManagerError` autour de l'appel `prompt_manager.delete()` et affiche `QMessageBox.critical()` — aucun appel supplémentaire à `update_prompts()` n'est nécessaire (voir section 3 : la ligne n'a jamais été retirée visuellement puisque `PROMPT_DELETED` n'a jamais été publié), mirroir exact du traitement déjà appliqué par Mission 068 à `DatasetsPage.delete_dataset()`/`LoRAPage.delete_lora()`/`ModelsPage.delete_model()`/`TrainingPage.delete_training()`/`WorkflowsPage.delete_workflow()`.

## 7. Hors périmètre (explicitement confirmé, non traité)

`create()` Domain-only (6 entités) ; `LoRAManager.update()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA après suppression ; segfault Qt/PySide6 ; `CharacterManager.delete()` (UI cachée, inatteignable) ; toute abstraction transactionnelle générique ; toute autre dette découverte pendant l'implémentation.

## 8. Risques

Minimal — mécanique déjà validée cinq fois à l'identique par Mission 068, aucune modification des 5 Managers déjà corrigés, aucun guard métier à préserver pour Prompt.

## 9. Tests automatisés

**Niveau Manager** (`PromptManagerDeleteRollbackTest`, nouveau, mirroir de `DatasetManagerDeleteRollbackTest` adapté — sans le test de guard métier, Prompt n'en ayant aucun) :
- Suppression réussie normale.
- Échec de `save()` → objet restauré au même index exact (`assertIs`, même instance).
- Échec de `save()` → `active_prompt_id` restauré à sa valeur exacte.
- Échec de `save()` sur un Prompt **non actif** → `active_prompt_id` (pointant vers un autre Prompt) reste totalement inchangé.
- Échec de `save()` → `project.json` inchangé octet pour octet.
- Aucun événement `PROMPT_DELETED` publié sur échec.
- Retry après échec → tentative réellement neuve, suppression effective et persistée.

**Niveau Presentation** (nouvelle classe `PromptsPageDeletePersistenceFailureTest`, mirroir structurel de `PromptsPageSaveTextPersistenceFailureTest` (Mission 070) et `PromptsPageRenameTest`'s tests d'échec) :
- Échec affiché via `QMessageBox.critical()`.
- Le Prompt reste présent et sélectionnable dans `prompt_list` après l'échec (aucune ligne retirée).
- `active_prompt_id` reste pointé sur le Prompt dont la suppression a échoué.
- Retry réel après échec → suppression effective, ligne retirée de la liste, bouton Supprimer désactivé.

**Non-régression explicite vérifiée** : `PromptsPageDeleteButtonStateTest.test_disabled_after_deleting_the_selected_prompt` (chemin de succès, M063) et l'ensemble des suites M038/M069/M070 (`PromptRoundTripTest`, `PromptsPageConfirmContextChangeTest`, `PromptManagerScalarRollbackTest`, `PromptsPageRenameTest`, `PromptsPageSaveTextPersistenceFailureTest`) restent vertes sans modification.

## 10. Smoke test Qt réel

Exécuté par Claude, `PromptsPage` réelle, `PromptManager`/`WorkspaceManager`/`CharacterManager` réels, Workspace temporaire réel sur disque, `project.json` réellement relu :
1. Suppression normale (succès) — mêmes garanties qu'avant M071, non-régression.
2. Échec de persistence injecté sur un Prompt actif — erreur affichée, Prompt toujours présent et sélectionné dans la liste, `active_prompt_id` inchangé, `project.json` inchangé ; retry réussi et persisté.
3. Échec de persistence injecté sur un Prompt actif **avec brouillon dirty non sauvegardé** — dialogue Discard/Cancel toujours affiché en amont ; après Discard puis échec de la suppression elle-même, le texte édité non sauvegardé reste visible et `_dirty` reste `True` (aucune perte supplémentaire).

## 11. Vérifications finales — réellement exécutées

- **Tests ciblés** : **10/10 nets nouveaux PASS** (`PromptManagerDeleteRollbackTest`, 6 ; `PromptsPageDeletePersistenceFailureTest`, 4).
- **Non-régression complète de `test_prompt_roundtrip.py`** : **109/109 PASS** (99 précédents + 10 nets nouveaux), 3.6s.
- **Suite complète** : **1245/1245** (1235 précédents + 10 nets nouveaux), une exécution complète `unittest discover`, 126.6s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet apportée.
- **`git diff --check`** : propre (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 3 fichiers de production/tests — `src/managers/prompt_manager.py`, `src/ui/pages/prompts_page.py`, `tests/integration/test_prompt_roundtrip.py` — plus ce document de mission.

### Incident de test détecté et corrigé pendant l'implémentation

Une première version du test `test_delete_failure_with_unsaved_draft_preserves_dirty_state_and_draft` mockait `PromptsPage._confirm_discard_before_switch()` par erreur — une méthode que `delete_prompt()` n'appelle en réalité jamais (celui-ci construit son propre `QMessageBox` Discard/Cancel en ligne, distinct du dialogue Save/Discard/Cancel partagé utilisé par `on_prompt_selection_changed()`/`confirm_context_change()`). Ce mock sans effet a laissé s'exécuter un **vrai** `QMessageBox.exec()` non mocké pendant la suite de tests, provoquant un blocage d'environ 32 minutes (`Ran 109 tests in 1954.623s`) au lieu de quelques secondes — la suite a fini par retourner "OK" car le bouton par défaut du dialogue réel (`Cancel`) a produit un comportement qui satisfaisait accidentellement les assertions (rien ne s'était produit, ce que le test vérifiait par ailleurs). Corrigé en adoptant l'idiome déjà établi ailleurs dans ce fichier (`patch("src.ui.pages.prompts_page.QMessageBox")` en bloc, avec `mock_message_box.return_value.exec.return_value = mock_message_box.Discard`) — la suite retourne désormais en 3.6s, confirmé par une ré-exécution complète.

## État d'avancement

- Mini-audit contractuel : **terminé, périmètre confirmé sans adaptation**.
- Implémentation : **réalisée, conforme au contrat M068 porté verbatim**.
- Tests automatisés : **exécutés, verts — 10/10 ciblés nets nouveaux, 109/109 non-régression complète du fichier**.
- Suite complète : **1245/1245, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (3 fichiers de code + 1 document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 3 scénarios réels couverts, 24/24 assertions** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (section 12).

## 12. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `33101ef9bbe1628a6c6c0e48405d8787b330d31c` (`feat: rollback PromptManager.delete() on persistence failure`), 4 fichiers modifiés (`src/managers/prompt_manager.py`, `src/ui/pages/prompts_page.py`, `tests/integration/test_prompt_roundtrip.py`, nouveau `docs/missions/MISSION_071.md`), 404 insertions(+), 2 suppressions(-). Poussé sur `origin/main` (`1c3a1b2..33101ef`), divergence `0 1` avant push puis `0 0` après.
- **Tag annoté** : `v0.2-mission071` (message « Mission 071 - Rollback PromptManager.delete() on Persistence Failure »), créé sur et poussé pour `33101ef9bbe1628a6c6c0e48405d8787b330d31c`. Vérifié via `git ls-remote --tags origin v0.2-mission071 "v0.2-mission071^{}"` — objet tag `00f185b0aa52b14efc85d0aa70651d871e6e9cb5`, peeled sur `33101ef9bbe1628a6c6c0e48405d8787b330d31c`, correspondance exacte confirmée localement et à distance.
- **GitHub Release** : `v0.2-mission071 — Rollback PromptManager.delete() on Persistence Failure`, rédigée par Claude (Release Notes en anglais conformément à la convention permanente depuis Mission 024) et **publiée manuellement par l'architecte**.
- **État Git final vérifié lors de la régularisation post-Release** : working tree propre, `HEAD == origin/main == 33101ef9bbe1628a6c6c0e48405d8787b330d31c`, divergence `0 0`, tag `v0.2-mission071` intact et toujours attaché au commit fonctionnel (non déplacé par la régularisation documentaire qui suit dans un commit séparé).
