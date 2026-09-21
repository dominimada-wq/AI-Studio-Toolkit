# Mission 143 — Guard CharacterManager.delete() Against Save-Failure State Corruption

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente de validation externe.** Reconstruction exacte de `CharacterManager.delete()` et de son unique appelant production (`CharactersPage.delete_character()`), sans copie mécanique du pattern `TrainingManager.delete()`. Corrigé et vérifié — voir §10 pour les résultats réels.

## 1. Problème

`CharacterManager.delete()` (`src/managers/character_manager.py:191-212`) mute `workspace.characters` et `active_character_id` **avant** d'appeler `WorkspaceManager.save()`, sans aucun `try/except` :

```python
def delete(self, character_id: str) -> bool:
    workspace = self._workspace_manager.current_workspace
    if workspace is None:
        return False
    character = self._find(character_id)
    if character is None:
        return False
    workspace.characters.remove(character)
    if self.active_character_id == character_id:
        self.active_character_id = None
    self._workspace_manager.save()          # <-- aucune protection
    self._publish(CHARACTER_DELETED, character)
    return True
```

C'est le seul `delete()`/`update()` du dépôt sans rollback sur échec de `save()`. `CharacterManager.create()` (`:157-176`) et `CharacterManager.update()` (`:214-300`), dans le **même fichier**, encapsulent déjà tous deux `save()` dans `try/except WorkspaceManagerError` avec restauration complète avant de relever.

## 2. Preuve — état avant/après exact

**Avant mutation** (avant tout appel à `delete()`) :
- `workspace.characters` : liste ordonnée, le Character ciblé occupe un index précis (potentiellement premier, dernier ou intermédiaire — jamais supposé).
- `active_character_id` : valeur quelconque, **pas nécessairement égale à `character_id`** (peut être `None`, pointer sur un autre Character, ou sur le Character ciblé lui-même).
- Aucune hypothèse a priori : la valeur exacte doit être capturée dynamiquement avant la mutation, jamais recalculée après coup.

**Trace actuelle si `save()` échoue** (confirmée par lecture directe) :
1. `workspace.characters.remove(character)` — le Character est déjà retiré de la liste en mémoire.
2. Si `active_character_id == character_id` : remis à `None` immédiatement.
3. `self._workspace_manager.save()` lève `WorkspaceManagerError` (propagée telle quelle, `WorkspaceManager.save()` l'enveloppe déjà depuis `WorkspaceStorageError`).
4. **Aucun rollback** : l'exception remonte immédiatement à l'appelant, `workspace.characters` reste sans le Character, `active_character_id` reste à `None` si c'était le Character actif — **état Domain déjà corrompu**, bien que l'opération ait échoué extérieurement.
5. `CHARACTER_DELETED` n'est jamais publié dans ce cas précis (la ligne `self._publish(...)` n'est jamais atteinte) — ce point du contrat est donc déjà correct aujourd'hui, par accident de flux plutôt que par garde explicite.

**Confirmé par lecture de `project.json`** : `WorkspaceStorage.save()` échouant avant `os.replace()` (atomique), le fichier sur disque reste intact — seule la mémoire est corrompue. Une sauvegarde ultérieure et sans rapport (renommer un autre Character, éditer un Prompt) persisterait alors silencieusement cette suppression jamais confirmée.

## 3. Invariant cible

Si `CharacterManager.delete()` ne peut pas persister la suppression :
- `workspace.characters` après l'échec **doit être identique** à son état avant l'appel — même nombre d'éléments, mêmes objets, même ordre, Character replacé à son **index exact** d'origine.
- `active_character_id` après l'échec **doit être exactement égal** à sa valeur avant l'appel (peu importe si elle valait `character_id`, une autre valeur, ou `None`).
- Aucun `CHARACTER_DELETED` ne doit être publié (déjà vrai aujourd'hui, à préserver).
- L'exception `WorkspaceManagerError` doit continuer à remonter sans être enveloppée dans un nouveau type — même contrat que `create()`/`update()`.

## 4. Comparaison avec les autres Managers — pattern retenu

| Manager | Filesystem impliqué | Rollback sur échec de `save()` | Pattern |
|---|---|---|---|
| `TrainingManager.delete()` (`training_manager.py:1255-1294`, Mission 068) | Non (Domain-only) | Oui | `index = list.index(obj)` + `previous_active_id` capturés avant mutation → `try/except` → `list.insert(index, obj)` + restauration de l'id actif |
| `CharacterManager.create()`/`update()` (même fichier) | Non | Oui | Rollback local simple (retrait/restauration de champs) |
| `DatasetManager.delete()` / `LoRAManager.delete()` / `LoRALibraryManager.delete()` | Oui (trash-then-purge, Mission 075) | Oui, plus rollback du renommage de dossier | Pattern à 3 phases, plus complexe car un dossier physique existe |

**Pattern retenu : celui de `TrainingManager.delete()`** — c'est le sibling le plus proche structurellement : une liste Domain-only (`character.trainings` pour Training, `workspace.characters` pour Character) plus un `active_*_id` nullable au même niveau, sans aucune opération filesystem. `DatasetManager`/`LoRAManager`/`LoRALibraryManager` sont écartés comme modèle direct car leur rollback inclut une étape de dossier physique (trash/rename) totalement hors périmètre de cette mission — `CharacterManager.delete()` ne touche et ne touchera aucun fichier.

## 5. Rollback exact retenu

```python
index = workspace.characters.index(character)
previous_active_character_id = self.active_character_id

workspace.characters.remove(character)

if self.active_character_id == character_id:
    self.active_character_id = None

try:
    self._workspace_manager.save()
except WorkspaceManagerError:
    workspace.characters.insert(index, character)
    self.active_character_id = previous_active_character_id
    raise

self._publish(CHARACTER_DELETED, character)
return True
```

`index` et `previous_active_character_id` sont capturés **avant** toute mutation, jamais recalculés après coup — couvre nativement les 6 cas demandés (Character actif/non actif, position début/milieu/fin, plusieurs Characters présents), puisque `list.index()`/`list.insert()` sont indépendants de la position réelle.

## 6. EventBus semantics

Ordre confirmé, inchangé par cette mission : **mutation Domain → `save()` → `CHARACTER_DELETED`**. Sur échec, `CHARACTER_DELETED` n'est jamais publié (déjà vrai avant cette mission, par accident de flux — désormais garanti par construction puisque le `raise` du bloc `except` empêche d'atteindre `_publish()`). Aucune modification de la politique EventBus générale (Mission 136, continue + journalisation, non touchée).

## 7. Exception semantics

`WorkspaceManagerError` continue de remonter telle quelle, sans enveloppement — même contrat que `create()`/`update()`. Aucun nouveau type d'exception introduit.

## 8. Audit CharactersPage — comportement UI réel

`CharactersPage.delete_character()` (`src/ui/pages/characters_page.py:197-204`) :
```python
def delete_character(self):
    item = self.list_widget.currentItem()
    if item is None:
        return
    self.character_manager.delete(item.data(Qt.UserRole))
```
Aucun `try/except`, contrairement à `create_character()` (`:179-188`) et `save_identity()` (`:244-267`) dans la **même Page**, qui catchent tous deux `WorkspaceManagerError` avec `QMessageBox.critical`. `DatasetsPage.delete_dataset()` (`:279-287`) et `TrainingPage.delete_training()` (`:1090-1098`) suivent aussi ce même motif de protection systématiquement. Aucun `sys.excepthook` global ni wrapper d'erreur commun n'existe nulle part dans le dépôt (`src/core/main.py` : `QApplication([])` puis `window.show()` puis `app.exec()`, sans aucune capture) — une `WorkspaceManagerError` levée ici remonterait donc non interceptée à travers le slot Qt `delete_button.clicked`.

**Décision — CharactersPage non modifiée dans cette mission.** Fait déterminant, confirmé par lecture directe de `characters_page.py:59-67` : depuis la révision UX de la Mission 026, `self.new_button`/`self.delete_button` (et le `list_widget` associé) sont explicitement `setVisible(False)` — le produit cible est « 1 Workspace = 1 Character principal », créé et sélectionné automatiquement, sans jamais exposer ce bouton à un utilisateur réel. `delete_character()` reste câblé et pleinement fonctionnel (compatibilité interne/tests uniquement, selon le commentaire du fichier lui-même), mais n'est **atteignable par aucun utilisateur réel de l'application livrée aujourd'hui** — confirmé par une recherche exhaustive de tout appelant production de `CharacterManager.delete()` (`grep` : un seul résultat, cette ligne). Contrairement à `DatasetsPage`/`TrainingPage`, où le bouton de suppression est visible et réellement utilisé, il n'existe donc aujourd'hui aucun « faux contrat utilisateur » réel à corriger côté `CharactersPage` — ajouter la même protection y serait une amélioration cosmétique sans bénéfice utilisateur actuel, et une extension de périmètre non nécessaire à l'invariant cible (qui porte uniquement sur l'état Domain). **Non modifiée dans cette mission**, conformément à l'instruction de ne l'inclure que si nécessaire.

## 9. Tests

**Fichier concerné** : `tests/integration/test_character_roundtrip.py` uniquement.

Nouvelle classe `CharacterManagerDeleteRollbackTest`, mirroir direct de `TrainingManagerDeleteRollbackTest` (`test_training_roundtrip.py:1874-1976`, Mission 068) adapté au niveau Workspace/Character plutôt que Character/Training : 3 Characters créés (`Aria`/`Kai`/`Nova`), `Kai` (position intermédiaire) sélectionné puis ciblé par la suppression — couvre nativement position et Character actif/non actif sans multiplier les tests, `list.index()`/`list.insert()` étant indépendants de la position réelle testée.

- `test_delete_succeeds_normally_when_save_works` — non-régression du chemin succès.
- `test_delete_save_failure_restores_object_at_original_index` — le Character est réinséré au même index exact, aucun `CHARACTER_DELETED` publié.
- `test_delete_save_failure_restores_active_character_id` — `active_character_id` restauré exactement quand le Character supprimé était actif.
- `test_delete_save_failure_never_touches_an_unrelated_active_id` — un `active_character_id` pointant sur un **autre** Character n'est jamais altéré par l'échec (cas B — Character non actif supprimé).
- `test_delete_save_failure_leaves_project_json_unchanged` — le fichier réel sur disque reste intact.
- `test_retry_after_save_failure_is_a_genuine_new_attempt` — une nouvelle tentative après un échec réussit normalement.

## 10. Résultats réels après implémentation

**Fichiers modifiés** :
- `src/managers/character_manager.py` — 20 lignes ajoutées, 1 supprimée (encapsulation de `save()` dans `try/except WorkspaceManagerError` avec capture de `index`/`previous_active_character_id` avant mutation et rollback exact sur échec, plus un docstring), aucun changement de signature ni de type de retour.
- `tests/integration/test_character_roundtrip.py` — **+6 tests nets**, nouvelle classe `CharacterManagerDeleteRollbackTest` : `test_delete_succeeds_normally_when_save_works`, `test_delete_save_failure_restores_object_at_original_index`, `test_delete_save_failure_restores_active_character_id`, `test_delete_save_failure_never_touches_an_unrelated_active_id`, `test_delete_save_failure_leaves_project_json_unchanged`, `test_retry_after_save_failure_is_a_genuine_new_attempt`.

**Résultats** :
- `CharacterManagerDeleteRollbackTest` seule : **6/6**.
- `test_character_roundtrip.py` complet : **81/81**, aucune régression.
- Suite ciblée voisine (`test_dataset_roundtrip.py`, `test_datasets_page.py`, `test_event_bus.py`, `test_image_roundtrip.py`, `test_images_page.py`, `test_lora_library_roundtrip.py`, `test_lora_roundtrip.py`, `test_model_roundtrip.py`, `test_prompt_assistant_dialog.py`, `test_prompt_roundtrip.py`, `test_settings_roundtrip.py`, `test_training_roundtrip.py`, `test_workflow_roundtrip.py`, `test_workspace_lifecycle.py`, `test_workspace_roundtrip.py` — tous les fichiers référençant `CharacterManager`) : **1457/1457**, aucune régression (les lignes « Failed to copy »/« disk full »/« Access is denied » visibles dans le log sont des injections d'erreurs simulées volontaires de tests préexistants, pas des échecs réels).
- **Suite complète** : **2798 tests collectés, 2798 passés, 0 échoué, exit 0 (446.400s)**. Équation : 2792 (clôture Mission 142) + 6 nets ajoutés par Mission 143 = **2798**, cohérent. Aucun flake sur ce run (un traceback bénin et déjà pré-existant, `inference_page.py:789`/`:865`, `QLabel.setText(MagicMock)`, sans rapport avec ce diff, imprimé pendant le run sans provoquer d'échec — non-régression confirmée, identique à ce qui était déjà observé lors de Mission 142). `git diff --check` : propre (seuls des avertissements LF→CRLF inoffensifs).

**Smoke** : non effectué, justifié — mécanisme entièrement synchrone, Qt-free, déterministe ; `CharactersPage` n'a pas été modifiée (voir §8), donc aucun test Qt supplémentaire n'était nécessaire au-delà de la suite automatisée déjà exécutée.

**Écarts par rapport au design demandé** : aucun. L'implémentation suit exactement le rollback retenu au §5, sans modification de `CharactersPage`, sans aucun nettoyage filesystem, sans changement du contrat d'exception ni de la sémantique EventBus.

## 11. Exclusions confirmées

Aucun nettoyage filesystem (`datasets/<id>/`, `training/<id>/`, `models/loras/<id>/`, Central LoRA Library ou tout autre subtree physique appartenant au Character) — dette distincte, documentée séparément, à comparer lors d'un futur audit. `CharactersPage` non modifiée (voir §8). `TrainingManager.delete()` filesystem, `create_job()` cleanup, rolling backup OneTrainer, Training Resume, caption sidecar, Forge, ComfyUI, Settings, Training EventBus, backup/versioning de `project.json`, toute refonte générique des méthodes `delete()` au-delà de `CharacterManager` : tous hors périmètre.

**Correction roadmap OneTrainer** (demandée explicitement, sans lien avec le code de cette mission) : l'audit précédent affirmant que « `rolling_backup_count = 3` est confirmé/recommandé par les presets officiels OneTrainer » est **infirmé** — vérification directe des 51 presets officiels installés (`J:\Programmes\Onetrainer\training_presets\*.json`) : aucun ne configure `rolling_backup` ni `rolling_backup_count`. La valeur `3` est uniquement le défaut de classe `TrainConfig`, inerte tant que `rolling_backup=False` (jamais activé nulle part). Cette correction ne modifie aucun document M138 existant dans le cadre de cette mission — aucune contradiction documentaire n'exige une correction immédiate de `MISSION_138.md`, qui présente déjà `3` comme « défaut OneTrainer conservé », pas comme une recommandation de preset.
