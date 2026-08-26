# Mission 068 — Rollback Domain-Only Deletions on Persistence Failure

> **STATUT : MISSION ENTIÈREMENT CLOSE.** 41 tests ciblés nets nouveaux, suite complète 1162/1162, smoke test Qt réel exécuté et **PASS** (24/24 assertions, 5 scénarios réels dont la garde Training du Dataset). Commit fonctionnel `969d70c4c0133e95045b0bfeda8822dbc148e3f1`, tag annoté `v0.2-mission068`, GitHub Release publiée. Voir section 14 pour l'état de clôture Git final.

## 1. Contexte

L'audit mené après Mission 067 a démontré empiriquement que les suppressions Domain-only (`DatasetManager.delete()`, `LoRAManager.delete()`, `ModelManager.delete()`, `TrainingManager.delete()`, `WorkflowManager.delete()`) suivent toutes le même ordre non transactionnel : retrait de l'objet de la collection en mémoire → `save()`, sans aucun rollback en cas d'échec de persistence. Conséquence démontrée par lecture directe du code (motif rigoureusement identique dans les cinq Managers) : un échec de `save()` laisse la suppression appliquée en mémoire — l'objet a disparu de `character.datasets`/`character.loras`/`character.trainings`/`workspace.models`/`workspace.workflows` — sans que `project.json` ne soit modifié et sans qu'aucun événement de succès ne soit publié. L'utilisateur ne voit rien se passer (aucun message, aucun refresh de liste), mais l'entité est réellement absente du Domain ; une sauvegarde ultérieure sans rapport la persisterait alors silencieusement, sans nouvelle confirmation.

## 2. Objectif

Garantir que si la persistence d'une suppression Domain-only échoue, l'état Domain est restauré exactement comme avant l'action — même objet, même position, mêmes IDs actifs — et que l'utilisateur en est informé.

## 3. Audit local préalable

Les cinq `delete()` ont été relus intégralement avant toute modification. Constat : structure identique dans les cinq cas, aucune divergence — guard(s) métier → `_find()` → retrait de la collection (`character.X.remove()` ou `workspace.X.remove()`) → ajustement conditionnel de `active_*_id` → `save()` → publication de l'événement `*_DELETED` → `return True`. Aucun champ secondaire, aucune référence croisée, aucune opération filesystem. Seul `DatasetManager.delete()` porte un guard métier supplémentaire (`is_referenced_by_training()`), placé avant toute mutation — donc naturellement hors du nouveau chemin transactionnel puisqu'il retourne `False` avant que quoi que ce soit ne soit modifié.

## 4. Contrat implémenté

Pour chacun des cinq Managers, appliqué localement et indépendamment (aucune abstraction commune, mirroir du principe déjà établi par Missions 063/066/067) :

1. Position de l'objet capturée (`collection.index(obj)`) et valeur courante de `active_*_id` capturée, avant toute mutation.
2. Retrait de la collection (logique métier existante strictement inchangée, guards compris).
3. `active_*_id` mis à `None` si c'était l'objet supprimé (logique existante inchangée).
4. `save()` tenté.
5. **Succès** : comportement existant inchangé — événement `*_DELETED` publié, `return True`.
6. **Échec (`WorkspaceManagerError`)** : l'objet est réinséré à son index exact (même instance Python, jamais recréée) ; `active_*_id` est restauré à sa valeur d'avant l'appel ; aucun événement n'est publié ; l'exception est relevée telle quelle (aucun message composite nécessaire — contrairement à Mission 067, il n'y a ici aucune compensation filesystem qui pourrait elle-même échouer).

Aucun snapshot général du Workspace n'a été nécessaire : chaque Manager dispose déjà, localement, de toute l'information utile à un rollback exact (l'objet lui-même, son index, l'ancien `active_*_id`).

**Presentation** (`DatasetsPage.delete_dataset()`, `LoRAPage.delete_lora()`, `ModelsPage.delete_model()`, `TrainingPage.delete_training()`, `WorkflowsPage.delete_workflow()`) : chaque handler intercepte désormais `WorkspaceManagerError` autour de l'appel `*_manager.delete()` et affiche `QMessageBox.critical()` — l'action n'est jamais présentée comme réussie. Aucun refresh supplémentaire n'a été nécessaire : la confirmation M062 et le retrait effectif de `dataset_list`/`lora_list`/etc. ne se produisent que via l'événement `*_DELETED` (jamais publié en cas d'échec) — l'entité n'a donc jamais été retirée visuellement de la liste, aucun état à reconstruire après l'erreur.

Le flux M062/M063 (confirmation avant suppression, bouton synchronisé avec la sélection) reste strictement inchangé — la garde Dataset↔Training continue de s'exécuter avant toute confirmation, jamais court-circuitée par le nouveau chemin transactionnel.

## 5. Hors périmètre (explicitement confirmé, non traité)

- `CharacterManager.delete()` / `CharactersPage.delete_character()` — suppression volontairement inaccessible dans l'UX actuelle (boutons `setVisible(False)`).
- Créations, renommages, modifications scalaires, associations/désassociations Domain-only.
- Mutations filesystem (`WorkspaceManager.remove_images()` — Mission 066 ; mutations additives — Mission 067).
- `PromptsPage` dirty-state, ancien thumbnail LoRA orphelin.
- Toute infrastructure transactionnelle générique.

## 6. Distinction avec Missions 066/067

- **Mission 066** : suppressions physiques de fichiers — persistence-first (Domain → `save()` → suppression physique uniquement après succès), car une suppression physique est irréversible.
- **Mission 067** : mutations additives filesystem — rollback Domain + compensation best-effort des copies physiques réellement créées, car une copie physique peut être annulée sans jamais toucher un fichier préexistant.
- **Mission 068** : suppressions Domain-only, aucune opération filesystem — rollback Domain local pur (réinsertion à l'index d'origine), sans aucune compensation filesystem puisqu'aucun fichier n'est jamais en jeu.

## 7. Risques

- **Risque de régression fonctionnelle** : très faible — la logique métier existante (guards, ajustement `active_*_id`, événements) reste strictement inchangée ; seule la gestion de l'échec de `save()` est ajoutée.
- **Risque d'incohérence d'ordre après rollback** : écarté par construction — l'index est capturé avant le retrait et la réinsertion cible ce même index, vérifié par des tests dédiés sur les cinq Managers (identité d'objet + position).

## 8. Pourquoi maintenant

Défaut transactionnel démontré par l'audit post-Mission 067, retenu comme candidat A prioritaire (meilleur rapport impact réel/certitude/périmètre borné/absence de décision produit ouverte) — motif rigoureusement identique aux cinq Managers, réutilisant directement le précédent de rollback local déjà établi par Mission 067 sans qu'aucune compensation filesystem ne soit nécessaire ici.

## 9. Tests automatisés ajoutés

**41 tests nets nouveaux**, répartis à l'identique sur les cinq entités (motif de test uniforme, reflet du motif de code uniforme) :

- `tests/integration/test_dataset_roundtrip.py` — `DatasetManagerDeleteRollbackTest` (7) : succès normal ; échec `save()` restaure l'objet à son index exact (identité vérifiée) et ne publie aucun événement ; `active_dataset_id` restauré ; `active_dataset_id` non lié jamais touché ; `project.json` inchangé après échec ; retry après échec est une tentative réellement neuve ; la garde Training bloque toujours la suppression avant même que `save()` ne soit tenté. `DatasetsPageDeleteConfirmationTest` (+2) : échec de persistence affiche l'erreur et conserve le dataset (même instance) ; retry après échec supprime réellement.
- `tests/integration/test_lora_roundtrip.py` — `LoRAManagerDeleteRollbackTest` (6, sans le test de garde métier — LoRA n'en a pas) + `LoRAPageDeleteConfirmationTest` (+2).
- `tests/integration/test_model_roundtrip.py` — `ModelManagerDeleteRollbackTest` (6) + `ModelsPageDeleteConfirmationTest` (+2).
- `tests/integration/test_training_roundtrip.py` — `TrainingManagerDeleteRollbackTest` (6, avec vérification explicite que `dataset_id` reste intact après rollback) + `TrainingPageDeleteConfirmationTest` (+2).
- `tests/integration/test_workflow_roundtrip.py` — `WorkflowManagerDeleteRollbackTest` (6) + `WorkflowsPageDeleteConfirmationTest` (+2).

Comportement observable testé (fichiers réels sur disque, `project.json` réellement relu, widgets Qt réels, boutons réellement cliqués, identité d'objet vérifiée par `assertIs`), jamais l'existence interne d'un mécanisme.

## 10. Vérifications finales — réellement exécutées

**Tests ciblés** — **41/41 nets nouveaux PASS**. Non-régression complète des cinq fichiers touchés — **289/289 PASS** (`test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_model_roundtrip.py` + `test_training_roundtrip.py` + `test_workflow_roundtrip.py`, y compris l'ensemble des suites M062/M063 — `*DeleteButtonStateTest`, `*DeleteConfirmationTest` — toutes vertes).

`git diff --check` : propre, aucun avertissement de contenu.

**Périmètre du diff** : exactement 15 fichiers — `src/managers/{dataset_manager,lora_manager,model_manager,training_manager,workflow_manager}.py`, `src/ui/pages/{datasets_page,lora_page,models_page,training_page,workflows_page}.py` (production), et leurs 5 fichiers de tests correspondants. Aucun fichier Domain/EventBus/Character/mutation filesystem touché.

## 11. Suite complète

**1162/1162 tests verts** (1121 précédents + 41 nets nouveaux), une exécution complète `unittest discover`, aucun crash, aucun échec. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet apportée.

## 12. Smoke test Qt réel — exécuté par Claude, écran non mocké

Widgets réels (`DatasetsPage`, `LoRAPage`, `ModelsPage`, `TrainingPage`, `WorkflowsPage`), Managers réels, fichiers réels sur disque, `project.json` réellement relu, boutons réellement cliqués. `QMessageBox` mocké uniquement pour éviter un modal bloquant (convention déjà établie).

1. **Dataset** : suppression confirmée → échec de persistence injecté → erreur affichée, dataset toujours présent (même instance), `active_dataset_id` restauré, `project.json` inchangé ; garde Training vérifiée toujours active sur ce même dataset (avertissement affiché, aucune tentative de `save()`) ; retry réel réussi après retrait de la Training bloquante.
2. **LoRA** : même principe — erreur affichée, LoRA toujours présente, `active_lora_id` restauré, retry réel réussi.
3. **Model** : même principe.
4. **Workflow** : même principe.
5. **Training** : même principe, `dataset_id` de la Training vérifié intact après rollback.

**Verdict : PASS**, 24/24 assertions vérifiées (`m068_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## 13. État d'avancement

- Audit local préalable des cinq `delete()` : **réalisé, motif confirmé identique**.
- Décision de périmètre (rollback local par Manager, sans framework transactionnel) : **validée par l'architecte**.
- Implémentation : **réalisée, conforme au contrat** — rollback Domain local sur les cinq Managers, traitement Presentation dédié pour les 5 handlers, garde Training M062 préservée.
- Tests automatisés : **exécutés, verts — 41/41 ciblés nets nouveaux, 289/289 non-régression complète**.
- Suite complète : **1162/1162, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (15 fichiers exactement, aucun fichier hors périmètre touché)**.
- Smoke test Qt réel : **réalisé, PASS, 5 scénarios réels couverts** (section 12).
- Clôture Git (commit/tag/Release) : **terminée** (voir section 14).

## 14. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `969d70c4c0133e95045b0bfeda8822dbc148e3f1` (`feat: rollback Domain-only deletions on persistence failure`), 16 fichiers modifiés/créés (5 Managers, 5 Pages, 5 fichiers de tests, `docs/missions/MISSION_068.md`), 1010 insertions(+), 10 suppressions(-).
- **Push** : `04f104b..969d70c main -> main`. Vérifié après coup : `HEAD == origin/main == 969d70c4c0133e95045b0bfeda8822dbc148e3f1`, divergence `0 0`.
- **Tag annoté** : `v0.2-mission068`, message « Mission 068 - Rollback Domain-Only Deletions on Persistence Failure », objet `20a2aa9098cd9be4d618eec228179586537d45d6`, peeled sur `969d70c4c0133e95045b0bfeda8822dbc148e3f1` — vérifié identique en local et à distance (`git ls-remote --tags`).
- **GitHub Release `v0.2-mission068`** : publiée manuellement par l'architecte.
- **Régularisation documentaire post-Release** (ce commit) : mise à jour du bandeau de statut de ce document, de `docs/PROJECT_CONTEXT.md` et de `CHANGELOG.md` (nouvelle section `## v0.2-mission068`) pour refléter l'état Git/Release réel désormais clos. Le tag `v0.2-mission068` reste sur le commit fonctionnel `969d70c` — non déplacé par ce commit de régularisation, purement documentaire.
- **Segfault Qt/PySide6** : ne s'est pas manifesté pendant la validation de cette mission (1162/1162 propre) — observation de stabilité, non une preuve de correction. Cause racine toujours non isolée ; l'hypothèse simple de cleanup `QThread` reste expérimentalement réfutée (audit post-Mission 064). Aucune modification visant ce sujet n'a été apportée dans Mission 068.
