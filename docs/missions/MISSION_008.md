# Mission 008 — Training Domain

Source : `CHANGELOG.md` (section "Mission 008 — Training Domain") + historique direct de la conversation de développement, vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `Training`, nouvelle entité Domain **Character-owned**, avec un niveau de preuve Blueprint plus nuancé que `Model`/`Workflow` : `04_DOMAIN_MODEL.md` §4 place explicitement `Trainings` sous `Characters` dans la hiérarchie d'entités, mais les arbres structurels de `00_VISION.md`, `01_PRODUCT_REQUIREMENTS.md` et `02_ARCHITECTURE.md` ne nomment à cet emplacement que `Training History` — divergence documentaire signalée, non résolue.

## Modifications principales

- `Training` (dataclass, 3 champs : `training_id`, `name`, `dataset_id`) — **aucun `character_id`** stocké, ownership implicite via `Character.trainings`.
- `Character.trainings: list[Training]` — nouveau champ, filtrage défensif `isinstance`.
- `TrainingManager` — `create(name, dataset_id)`, `select`, `delete`, `list_trainings()`. Validation de `dataset_id` strictement limitée à `active_character.datasets` (un Dataset d'un autre Character est refusé, indiscernable d'un ID inconnu). Aucune méthode `update_*()`.
- **Première intégrité référentielle inter-entités du projet** : `DatasetManager.is_referenced_by_training()` + garde dans `DatasetManager.delete()` — un Dataset référencé par ≥1 Training ne peut pas être supprimé, sans cascade. Défense en profondeur (préflight UI + garde Manager indépendante).
- `TrainingPage` — première Page du projet dépendante de deux Managers (`training_manager` + `dataset_manager` en lecture seule). Sélection de Dataset via `QInputDialog`, désambiguïsation des noms dupliqués par fragment de `dataset_id`. Référence historique invalide affichée `"Dataset introuvable [dataset_id]"`, sans exception. **Aucun bouton de lancement, aucune console** — retirés du prototype initial.

## Fichiers importants créés ou modifiés

Créés : `training.py`, `training_manager.py`, `training_page.py`, `test_training_roundtrip.py`.
Modifiés : `character.py`, `dataset_manager.py`, `datasets_page.py`, `main_window.py`.

## Décisions techniques

- Ownership Character-owned documenté comme non-certitude absolue, contrairement à `Model`/`Workflow`.
- Aucune suppression en cascade — le refus est la seule réponse à une suppression bloquée.
- Événements réellement publiés : `training.created`, `training.selected`, `training.deleted` — aucun autre.
- Hors périmètre explicite : `Training Engine`, `Job`, lancement réel, pause/reprise/annulation, progression, loss, logs, `Output LoRA`, `Base Model`, epochs, learning rate, optimizer, batch size, résolution, événements `TrainingStarted`/`Paused`/`Resumed`/`Finished`/`Cancelled`/`Failed`.

## Tests et validations

`test_training_roundtrip.py` (11 tests) : round-trip Domain, compatibilité `Character.trainings`, création + persistance, refus `dataset_id` vide/inexistant/d'un autre Character (atomicité complète prouvée), reset de contexte, suppression active/non-active/invalide, cycle complet d'intégrité référentielle (blocage/absence de cascade/déblocage), isolation des autres collections, reconstruction `TrainingPage`, absence de duplication d'abonnements, non-impact Dashboard/Images.

## Commit correspondant

6 commits fonctionnels + 1 commit de documentation/clôture, vérifiés par `git log --oneline --reverse` entre `v0.2-mission007` et `v0.2-mission008` :

```
3cba90f Introduce Training domain object (training_id, name, dataset_id)
08553e5 Add Training collection to Character persistence
7bd1ced Add TrainingManager with Dataset reference validation
fcf97b9 Prevent deletion of Datasets referenced by Training
e2ce108 Add functional TrainingPage with Dataset selection
36aa431 tests: add Training lifecycle and referential integrity coverage
af7645c docs: document Mission 008 Training domain
```

Correspond exactement aux 6 commits fonctionnels indiqués par le CHANGELOG + le 7ᵉ commit de clôture documentaire.

## Tag / release correspondant

`v0.2-mission008` — **annoté**, cible `af7645cdf9c4c04cdaee3256696d91ca9e94321f`. GitHub Release publiée par l'utilisateur (confirmé dans l'historique de conversation).

## État final

Mission terminée. `Training` rejoint `Dataset`/`LoRA`/`Prompt` comme entités Character-owned, première intégrité référentielle inter-entités (Dataset → Training), 57 tests d'intégration.
