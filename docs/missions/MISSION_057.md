# Mission 057 — Remove Vestigial Workspace Fields and Dead Code

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat validé par l'architecte le 2026-08-24 avec précisions obligatoires (compatibilité des anciens `project.json` démontrée explicitement, pas seulement affirmée nulle ; retrait strictement borné aux trois champs confirmés morts ; tests de compatibilité ajoutés, non simplement retirés). Implémentation réalisée conformément au contrat corrigé, 11/11 tests ciblés nets nouveaux, 967/967 tests automatisés verts, `git diff --check` propre, cycle réel création/sauvegarde/fermeture/réouverture exécuté manuellement et JSON produit inspecté (rapporté en section 11). Commit, tag et GitHub Release réels — voir sections 12-15 ci-dessous.

## 1. Contexte

L'audit factuel de Mission 057 (voir rapport de présentation) a confirmé, code à l'appui, que trois éléments du dépôt sont du code/état mort :

- `Workspace.datasets`, `Workspace.loras`, `Workspace.training` (`src/domain/workspace.py`) — champs génériques non typés (`list`/`list`/`dict`), jamais lus par aucun Manager (`DatasetManager`/`LoRAManager`/`TrainingManager` lisent exclusivement `character_manager.principal_character.datasets`/`.loras`/`.trainings`, confirmé par grep sur tout `src/`), jamais écrits ailleurs que dans `Workspace.to_dict()`/`from_dict()` eux-mêmes. `Workspace.models`/`.workflows` sont en revanche réellement consommés par `ModelManager`/`WorkflowManager` et restent **strictement inchangés**.
- `Character.history` (`src/domain/character.py`) — champ `list[str]`, sérialisé dans `to_dict()` mais jamais peuplé ni lu ailleurs dans tout `src/` (confirmé par grep — seule occurrence : la ligne `to_dict()` elle-même).
- `src/ui/pages/base_page.py` (`BasePage(QWidget)`) — fichier de 19 lignes, aucune Page du projet n'en hérite (toutes héritent directement de `QWidget` et redéfinissent leur propre titre) — confirmé par grep, zéro référence hors sa propre définition.

Ces trois éléments constituent une violation du principe **Single Source of Truth** de `CLAUDE.md` (deux sources possibles pour les collections dataset/lora/training d'un Workspace, une seule réelle) et un risque latent (un futur code lisant par erreur `workspace.datasets` au lieu de `character.datasets` obtiendrait silencieusement une liste vide au lieu d'une erreur).

## 2. Mini-audit réalisé

**Confirmation d'absence d'usage réel** : grep sur `workspace\.datasets|workspace\.loras|workspace\.training|current_workspace\.datasets|current_workspace\.loras|current_workspace\.training|\.history\b` dans tout `src/` : seule occurrence, `character.py:52` (`"history": self.history` dans `to_dict()`). Aucune Page, aucun Manager, aucun test fonctionnel n'exploite ces champs comme source de données réelle.

**Impact tests identifié** : trois tests existants vérifient explicitement `workspace.datasets`/`.loras`/`.training` (non-mutation ou roundtrip) — `test_workflow_roundtrip.py::test_workflow_operations_do_not_mutate_other_workspace_collections` (2 assertions), `test_settings_roundtrip.py` (2 emplacements : un test de roundtrip comparant `restored.datasets`/`.loras`/`.training` à `original.*`, 3 assertions ; un test de non-mutation, 3 assertions) — 8 assertions au total à retirer. `workspace.models`/`.workflows`/`.characters`/`.images`, également vérifiés dans ces mêmes tests, restent inchangés et continuent d'être vérifiés.

**Aucune décision produit ou architecturale substantielle ne reste ouverte** : ces champs n'ont, d'après leurs propres commentaires historiques (« has never held real data »), jamais porté de donnée réelle à aucun stade du projet — leur suppression ne constitue donc ni une migration de données ni une perte fonctionnelle.

## 3. Objectif

Retirer les trois éléments de code/état mort identifiés ci-dessus, sans toucher à aucun comportement réellement observable de l'application.

## 4. Contrat fonctionnel — réellement implémenté

**`src/domain/workspace.py`** :
- Champs `datasets: list`, `loras: list`, `training: dict` retirés de la dataclass `Workspace`.
- Clés `"datasets"`, `"loras"`, `"training"` retirées de `Workspace.to_dict()`.
- Paramètres `datasets=`, `loras=`, `training=` retirés de `Workspace.from_dict()`.
- `Workspace.models`/`.workflows`/`.images`/`.characters`/`.settings`/`.name`/`.version`/`.root` : **strictement inchangés**.
- Compatibilité défensive démontrée (pas seulement affirmée) par tests réels (section 10) : un `project.json` écrit avant cette mission et contenant encore ces trois clés (même peuplées de données non vides) se charge toujours sans erreur ; ces clés ne sont plus jamais réémises dans le fichier une fois le Workspace sauvegardé avec cette version — nettoyage d'un schéma mort, jamais présenté comme une migration de données fonctionnelles puisque ces champs n'ont jamais porté de donnée réelle.

**`src/domain/character.py`** :
- Champ `history: list[str]` retiré.
- Clé `"history"` retirée de `Character.to_dict()`.
- Paramètre `history=` retiré de `Character.from_dict()`.
- `Character.datasets`/`.loras`/`.prompts`/`.trainings` et tous les autres champs : **strictement inchangés** — ce sont les collections réellement possédées et consommées par `DatasetManager`/`LoRAManager`/`PromptManager`/`TrainingManager`. Même garantie de compatibilité défensive : un `history` legacy est ignoré, jamais réémis après re-sauvegarde.

**`src/ui/pages/base_page.py`** :
- Fichier supprimé entièrement. Confirmé, après suppression, qu'aucune Page ni aucun `__init__.py` ne le référence plus nulle part (grep exhaustif sur `src/` et `tests/`, plus test architectural dédié — section 10).

**Domain/Manager/EventBus/persistance** : aucun autre changement. `ComfyUIEngine`/`GenerationManager`/Inference : aucun changement.

## 5. Comportement explicitement différé (hors périmètre)

- Les commentaires de `Character.from_dict()` faisant référence à « Commit 3's impact report » pour `datasets`/`loras`/`prompts` sont aujourd'hui obsolètes (ces champs sont réellement consommés depuis les Missions 026-029) — leur correction n'est **pas** traitée par cette mission pour éviter tout élargissement de périmètre ; observation consignée dans `PROJECT_CONTEXT.md`.
- La présence généralisée de références à des numéros de Mission/Commit dans les commentaires du Domain (violation documentée de la règle CLAUDE.md « Domain intemporel »), bien plus large que les seuls champs retirés ici, n'est **pas** traitée par cette mission — nécessiterait un audit dédié séparé de tout `src/domain/`.
- Aucun changement de format `project.json` au-delà de la suppression de 4 clés qui n'ont jamais porté de donnée réelle.

## 6. Fichiers concernés — réellement modifiés

Production (3) :
- `src/domain/workspace.py` (retrait de 3 champs + entrées `to_dict()`/`from_dict()`, 20 lignes de diff)
- `src/domain/character.py` (retrait de 1 champ + entrées `to_dict()`/`from_dict()`, 8 lignes de diff)
- `src/ui/pages/base_page.py` (fichier supprimé, 19 lignes)

Tests (4, aucun nouveau fichier) :
- `tests/integration/test_workflow_roundtrip.py` (retrait de 2 assertions obsolètes dans `test_workflow_operations_do_not_mutate_other_workspace_collections`)
- `tests/integration/test_settings_roundtrip.py` (retrait de 6 assertions obsolètes réparties sur 2 tests)
- `tests/integration/test_workspace_roundtrip.py` (nouvelle classe `WorkspaceVestigialFieldsRemovalTest`, 9 tests nets nouveaux)
- `tests/integration/test_character_roundtrip.py` (nouvelle classe `CharacterHistoryFieldRemovalTest`, 2 tests nets nouveaux)

## 7. Stratégie de tests — réellement mise en œuvre

`WorkspaceVestigialFieldsRemovalTest` (nouvelle classe, `test_workspace_roundtrip.py`, 9 tests) :
- `test_legacy_workspace_json_with_removed_keys_still_loads` — un `project.json` écrit à la main avec `datasets`/`loras`/`training` peuplés de données non vides se charge sans erreur.
- `test_legacy_character_json_with_history_key_still_loads` — même preuve pour un `Character` legacy avec `history` peuplé.
- `test_real_character_collections_survive_the_legacy_load` — `Character.datasets`/`.loras`/`.prompts`/`.trainings` restent intacts et exploitables après le chargement de ce JSON legacy.
- `test_real_workspace_collections_survive_the_legacy_load` — `Workspace.models`/`.workflows` restent intacts.
- `test_resave_no_longer_emits_the_removed_keys` — après réouverture puis `save()`, les clés `datasets`/`loras`/`training`/`history` sont absentes du nouveau `project.json`.
- `test_resave_still_preserves_real_data` — dans ce même fichier re-sauvegardé, les vraies collections (`Character.datasets`/`.loras`/`.prompts`/`.trainings`, `Workspace.models`/`.workflows`) sont toujours présentes et complètes.
- `test_workspace_to_dict_never_emits_the_removed_keys_for_a_fresh_workspace` — un Workspace flambant neuf (jamais issu d'un ancien fichier) n'écrit jamais ces clés, y compris pour son Character principal auto-créé (Mission 026).
- `test_create_close_reopen_cycle_has_no_regression` — cycle création/fermeture/réouverture standard, aucune régression.
- `test_base_page_file_and_all_references_are_gone` — `src/ui/pages/base_page.py` n'existe plus, et aucun fichier de `src/ui/pages/*.py` ne référence plus `BasePage`/`base_page`.

`CharacterHistoryFieldRemovalTest` (nouvelle classe, `test_character_roundtrip.py`, 2 tests) :
- `test_legacy_history_key_is_ignored_without_error` — `Character.from_dict()` isolé, preuve Domain-level indépendante du cycle Workspace complet.
- `test_to_dict_never_emits_a_history_key` — un `Character` neuf n'écrit jamais cette clé.

**Non-régression explicite confirmée** : `test_workspace_roundtrip.py` (89/89), `test_character_roundtrip.py` (42/42), `test_workflow_roundtrip.py` (21/21), `test_settings_roundtrip.py` (9/9), `test_dataset_roundtrip.py` (49/49), `test_lora_roundtrip.py` (67/67), `test_training_roundtrip.py` (34/34) — tous verts, aucune régression sur les cycles Dataset/LoRA/Training/Character/Workspace.

**11/11 tests ciblés nets nouveaux. 967/967 tests automatisés verts au total** (956 précédents + 11 nets nouveaux).

`git diff --check` propre. Cycle réel création → sauvegarde → fermeture → réouverture exécuté manuellement (le contrat ne change aucun comportement UI observable — pas de smoke test Qt requis), JSON produit inspecté directement — voir section 11 pour la preuve complète.

## 8. Risques

- **Risque de régression fonctionnelle** : nul par construction — les champs retirés ne sont lus par aucun code applicatif (confirmé par grep exhaustif) — et démontré, pas seulement affirmé, par les 9+2 tests de compatibilité ci-dessus.
- **Risque de casser un test existant** : identifié et scopé précisément (section 6) — 8 assertions obsolètes dans 2 fichiers de test retirées, aucune logique de test par ailleurs modifiée.
- **Risque de perte de compatibilité avec un `project.json` ancien** : faible, jamais présenté comme nul — les clés retirées n'étaient jamais nécessaires à une relecture réussie, mais le contrat exige une preuve directe (pas une simple assertion) que le chargement réussit et que les vraies données survivent ; cette preuve est apportée par `test_legacy_workspace_json_with_removed_keys_still_loads` et les tests voisins, plus le cycle réel de la section 11.

## 9. Pourquoi maintenant

Ce nettoyage referme une incohérence architecturale documentée depuis les Missions 026-029 (migration de la propriété de `Dataset`/`LoRA`/`Training` de `Workspace` vers `Character`, jamais suivie du retrait des champs `Workspace` devenus obsolètes) et une dette mineure plus ancienne (`Character.history`, jamais consommé depuis son introduction ; `BasePage`, jamais adopté). Petit périmètre, risque nul, aucune décision produit à trancher — candidat directement actionnable sans bloquer sur une dépendance externe ou un choix d'architecture encore ouvert (contrairement aux autres candidats identifiés par l'audit, voir rapport de présentation).

## 11. Vérification manuelle réelle — cycle création/sauvegarde/fermeture/réouverture

Exécuté moi-même en dehors de la suite `unittest` (script scratchpad, jamais committé), avec les Managers réels (`WorkspaceManager`, `CharacterManager`, `DatasetManager`, `LoRAManager`, `TrainingManager`, `PromptManager`, `ModelManager`, `WorkflowManager`) — pas de mock :

1. Un `project.json` pré-Mission-057 est écrit à la main (`datasets`/`loras`/`training` peuplés de valeurs non vides au niveau Workspace, `history` peuplé au niveau Character, aux côtés de vraies collections Character : 1 Dataset, 1 LoRA, 1 Prompt, 1 Training).
2. `WorkspaceManager.open()` réel charge ce fichier sans erreur. Confirmé : `hasattr(workspace, "datasets")` → `False`, `hasattr(workspace, "loras")` → `False`, `hasattr(workspace, "training")` → `False`, `hasattr(character, "history")` → `False` — les champs n'existent plus sur les objets Domain reconstruits. Les vraies collections sont intactes : `character.datasets` → `["Portraits"]`, `character.loras` → `["L1"]`, `character.prompts` → `["hello"]`, `character.trainings` → `["T1"]`.
3. `WorkspaceManager.close()` réel, puis réouverture avec une pile entièrement neuve (nouveau `WorkspaceManager`, nouveau `EventBus`) et `save()` réel.
4. Le `project.json` réécrit sur disque est inspecté directement : `datasets`/`loras`/`training` absents au niveau racine, `history` absent de l'entrée Character — et les vraies données toujours présentes en intégralité (`datasets`: 1, `loras`: 1, `prompts`: 1, `trainings`: 1, `models`/`workflows` présents).

**Verdict : PASS, sans écart.** Preuve directe, sur un cycle réel (pas seulement via `unittest`), que la compatibilité defensive fonctionne et que le nettoyage ne perd aucune donnée fonctionnelle.

## État d'avancement

- Audit du dépôt (candidats Mission 057) : **réalisé**.
- Choix de mission : **validé par l'architecte** (2026-08-24), avec précisions de contrat intégrées.
- Spécification (ce document) : **rédigée et corrigée** conformément aux précisions de l'architecte.
- Implémentation : **réalisée**, conforme au contrat corrigé, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 11/11 ciblés nets nouveaux, 967/967 (suite complète).
- `git diff --check` : **propre**.
- Vérification manuelle réelle (cycle création/sauvegarde/fermeture/réouverture + inspection du JSON) : **réalisée, PASS** (section 11). Aucun smoke test Qt requis — aucun comportement UI observable n'est modifié par cette mission.
- Clôture Git (commit/tag/Release) : **entièrement effectuée**.

## 12. Fichiers concernés

Production (3) : `src/domain/workspace.py`, `src/domain/character.py`, `src/ui/pages/base_page.py` (supprimé).
Tests (4, aucun nouveau fichier) : `tests/integration/test_workspace_roundtrip.py`, `tests/integration/test_character_roundtrip.py`, `tests/integration/test_workflow_roundtrip.py`, `tests/integration/test_settings_roundtrip.py`.
Documentation (1, nouveau fichier) : `docs/missions/MISSION_057.md`.

## 13. Commit correspondant

`c7eb1fe0c32f677226f5b14c93dbbf82832e3bef` — `refactor: remove vestigial Workspace fields and dead code`.

## 14. Tag-release correspondant

`v0.2-mission057` (annoté, message `Mission 057 - Remove Vestigial Workspace Fields and Dead Code`), ciblant exactement `c7eb1fe0c32f677226f5b14c93dbbf82832e3bef`.

## 15. État final

GitHub Release `v0.2-mission057` publiée. Mission entièrement close.
