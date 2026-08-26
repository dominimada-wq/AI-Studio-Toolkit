# Mission 072 — Rollback Domain-Only create() on Persistence Failure

> **MISSION FONCTIONNELLEMENT VALIDÉE, IMPLÉMENTATION TERMINÉE.** 66 tests ciblés nets nouveaux, suite complète 1311/1311, smoke test Qt réel exécuté et **PASS** (38/38 assertions, 7 scénarios réels couvrant les 7 entités concernées). Voir section "État d'avancement" pour l'état de clôture Git.

## 1. Contexte

L'audit post-Mission 071 a identifié que les 7 méthodes `create()` (`DatasetManager`, `CharacterManager`, `ModelManager`, `WorkflowManager`, `LoRAManager`, `TrainingManager`, `PromptManager`) sont **rigoureusement isomorphes** : construction de l'entité → `append()` dans la collection Domain parente → `WorkspaceManager.save()` **sans aucun `try/except`** → publication de l'événement de succès. Aucun des 9 sites d'appel Presentation (`DatasetsPage.create_dataset()`, `CharactersPage.create_character()`, `ModelsPage.create_model()`, `WorkflowsPage.create_workflow()`, `LoRAPage.create_lora()`, `TrainingPage.create_training()`, `PromptsPage.create_prompt()`, `PromptsPage.save_as_new_prompt()`, `InferencePage._on_save_prompt_clicked()`) n'interceptait quoi que ce soit autour de l'appel.

Une reproduction empirique réelle (script Python, scratchpad de session, `QApplication` réel + `DatasetsPage` réelle + `WorkspaceStorage.save` mocké + déclenchement via `button.clicked.emit()`, dispatch Qt réel) a confirmé :
- Le traceback Python brut remonte jusqu'à la boucle d'événements Qt et s'affiche sur stderr — aucun message utilisateur, aucun `QMessageBox`.
- Le processus **ne crashe pas** (PySide6 sans `excepthook` personnalisé imprime et continue) — hypothèse de crash infirmée pour ce chemin précis, sans rapport avec le segfault natif déjà documenté.
- **L'entité créée reste résidente en mémoire après l'échec** (`dataset_manager.datasets` contenait le Dataset fantôme) alors que `project.json` n'avait jamais été modifié — exactement le motif déjà corrigé par Missions 068/070/071 pour delete()/update(), jamais traité pour create().

C'est la dernière famille homogène et la plus largement utilisée (créer une entité est l'action la plus fréquente de toute l'application) du triptyque create/update/delete encore non sécurisée.

## 2. Objectif

Appliquer aux 7 méthodes `create()` le même contrat de rollback local déjà établi par Missions 068/070/071, sans nouvelle abstraction générique.

## 3. Mini-audit contractuel préalable

Relecture intégrale des 7 méthodes `create()` et de leurs 9 sites d'appel Presentation. Constats :
- Les 7 méthodes sont **parfaitement isomorphes** : aucune ne touche `active_*_id` ni aucun autre état au-delà de l'`append()` dans sa collection — le rollback est donc trivial (retirer la même instance) et identique pour les 7, sans exception ni cas particulier.
- `CharacterManager.create()`/`delete()`/`update()` n'importaient **jamais** `WorkspaceManagerError` (contrairement aux 6 autres Managers, déjà équipés depuis Missions 068/070) — un import réellement manquant, ajouté par cette mission, non une dette préexistante silencieusement contournée.
- `CharactersPage.py` n'importait pas non plus `WorkspaceManagerError` — même constat côté Presentation.
- Les 9 sites d'appel Presentation ont été vérifiés un par un (jamais supposés à partir d'un compte annoncé) : `datasets_page.py:141`, `characters_page.py:155`, `models_page.py:74`, `workflows_page.py:74`, `lora_page.py:136`, `training_page.py:117`, `prompts_page.py:147` (`create_prompt`), `prompts_page.py:449` (`save_as_new_prompt`, un second site distinct dans le même fichier), `inference_page.py:271` (`_on_save_prompt_clicked`). Aucun site supplémentaire trouvé ; aucun des 9 ne nécessitait d'être exclu.
- `TrainingManager.create()` conserve son garde métier existant (`dataset_id` doit appartenir au Character actif) — inchangé, évalué avant toute mutation, jamais concerné par le rollback.

**Conclusion du mini-audit** : port direct du contrat M068/070/071 sur les 7 méthodes, sans nouvelle décision produit ni architecturale — à l'exception des deux imports `WorkspaceManagerError` manquants, ajouts strictement nécessaires et sans alternative.

## 4. Périmètre exact

- 7 Managers : `src/managers/dataset_manager.py`, `character_manager.py`, `model_manager.py`, `workflow_manager.py`, `lora_manager.py`, `training_manager.py`, `prompt_manager.py`.
- 8 Pages : `src/ui/pages/datasets_page.py`, `characters_page.py`, `models_page.py`, `workflows_page.py`, `lora_page.py`, `training_page.py`, `prompts_page.py` (2 sites), `inference_page.py`.
- 8 fichiers de tests : `tests/integration/test_dataset_roundtrip.py`, `test_character_roundtrip.py`, `test_model_roundtrip.py`, `test_workflow_roundtrip.py`, `test_lora_roundtrip.py`, `test_training_roundtrip.py`, `test_prompt_roundtrip.py`, `test_inference_page.py`.
- `docs/missions/MISSION_072.md` — ce document.

23 fichiers au total. Explicitement hors périmètre (confirmé par l'architecte) : `LoRAManager.update()` (candidat B), `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` (candidat F), `SettingsManager.update()` (candidat I), `CharacterManager.delete()`/`update()` (UI cachée), segfault Qt/PySide6.

## 5. Contrat Manager

```python
def create(self, name: str) -> Optional[X]:

    parent = ...
    if parent is None:
        return None

    entity = X(x_id=str(uuid.uuid4()), name=name)

    parent.xs.append(entity)

    try:
        self._workspace_manager.save()
    except WorkspaceManagerError:
        parent.xs.remove(entity)
        raise

    self._publish(X_CREATED, entity)

    return entity
```

Appliqué à l'identique sur les 7 Managers (adapté au nom du champ/collection/événement de chacun). Rollback purement local (même objet Python retiré), aucun snapshot du Workspace, aucune opération filesystem — aucun état additionnel à restaurer, confirmé par le mini-audit.

## 6. Contrat Presentation

Chacun des 9 handlers intercepte désormais `WorkspaceManagerError` autour de l'appel `manager.create()` et affiche `QMessageBox.critical()` avant de `return` — la logique préexistante de gestion du `None` (cas "aucun projet ouvert"/"aucun personnage") reste intacte et inchangée, désormais atteinte uniquement après un `create()` qui n'a pas levé d'exception. Aucun rafraîchissement manuel de liste n'est nécessaire : l'entité n'a jamais été ajoutée visuellement puisque l'événement de création n'est publié qu'après succès.

## 7. Hors périmètre (explicitement confirmé, non traité)

`LoRAManager.update()` ; `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; `CharacterManager.delete()`/`update()` (UI cachée, inatteignable) ; segfault Qt/PySide6 ; toute abstraction transactionnelle générique ; toute autre dette découverte pendant l'implémentation (aucune ne s'est présentée au-delà des deux imports manquants, strictement nécessaires au périmètre).

## 8. Risques

Minimal — mécanique déjà validée à l'identique par Missions 068/070/071, isomorphisme confirmé empiriquement sur les 7 méthodes avant implémentation, aucun état additionnel à restaurer pour aucune des 7.

## 9. Tests automatisés

**66 tests nets nouveaux**, répartis par entité :

- **Niveau Manager** (`<Entité>ManagerCreateRollbackTest`, 6 tests × 7 entités = 42) : succès normal ; échec `save()` retirant l'entité fantôme (même instance, jamais recréée) ; aucun événement de succès publié ; `project.json` inchangé ; retry réel après rollback persistant effectivement ; une entité préexistante non concernée reste inchangée (`assertIs`).
- **Niveau Presentation** (`<Entité>sPageCreatePersistenceFailureTest`/équivalent, 3 tests × 8 sites = 24, `PromptsPage` comptant pour 5 du fait de ses 2 sites) : erreur affichée et liste UI vide/inchangée ; `project.json` inchangé ; retry réel effectif.
- **`InferencePage`** (1 test, style mock existant du fichier) : `WorkspaceManagerError` intercepté, `QMessageBox.critical()` affiché, `select()`/`update_text()` jamais appelés.

**Non-régression** : 92/92 (`test_dataset_roundtrip.py`), 51/51 (`test_character_roundtrip.py`), 57/57 (`test_model_roundtrip.py`), 58/58 (`test_workflow_roundtrip.py`), 103/103 (`test_lora_roundtrip.py`), 67/67 (`test_training_roundtrip.py`), 120/120 (`test_prompt_roundtrip.py`), 82/82 (`test_inference_page.py`).

## 10. Smoke test Qt réel

Exécuté par Claude, 7 Pages réelles (`DatasetsPage`/`CharactersPage`/`ModelsPage`/`WorkflowsPage`/`LoRAPage`/`TrainingPage`/`PromptsPage`) contre des Workspaces temporaires réels sur disque, `project.json` réellement relu à chaque étape :
1. Création normale (succès) pour chacune des 7 entités.
2. Échec de persistence injecté — erreur affichée, entité fantôme retirée de la mémoire, liste UI inchangée, `project.json` inchangé.
3. Retry réel après échec — création effective et persistée.

**38/38 assertions PASS.**

## 11. Vérifications finales — réellement exécutées

- **Tests ciblés** : **66/66 nets nouveaux PASS**.
- **Non-régression** : 8/8 fichiers de tests concernés, tous verts (détail section 9).
- **Suite complète** : **1311/1311** (1245 précédents + 66 nets nouveaux), une exécution complète `unittest discover`, 129.0s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.
- **`git diff --check`** : propre (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 23 fichiers — 7 Managers, 8 Pages, 8 fichiers de tests, 1 document de mission.

### Découverte pendant l'implémentation : deux imports `WorkspaceManagerError` manquants

`character_manager.py` et `characters_page.py` n'importaient jamais `WorkspaceManagerError` — seul Manager/Page du projet dans ce cas, les 6 autres l'important déjà depuis leurs rollbacks Mission 068/070. Ajout strictement nécessaire au périmètre (aucun `except WorkspaceManagerError` n'est possible sans lui) — détecté immédiatement par l'exécution des tests (`NameError`), corrigé avant toute autre action, jamais une dette de mission antérieure laissée non résolue puisque `CharacterManager.delete()`/`update()` restent hors périmètre et n'en dépendent pas.

## État d'avancement

- Mini-audit contractuel : **terminé, périmètre confirmé sans adaptation majeure**.
- Implémentation : **réalisée, conforme au contrat M068/070/071 porté verbatim sur les 7 Managers**.
- Tests automatisés : **exécutés, verts — 66/66 ciblés nets nouveaux, non-régression complète des 8 fichiers concernés**.
- Suite complète : **1311/1311, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (23 fichiers exactement)**.
- Smoke test Qt réel : **réalisé, PASS, 7 scénarios réels couverts, 38/38 assertions** (section 10).
- Clôture Git (commit/tag/Release) : **en cours**.
