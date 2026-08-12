# Mission 003 — Dataset Domain

Source : `CHANGELOG.md` (section "Mission 003 — Dataset Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `Dataset`, positionnée dans la hiérarchie `Character → Datasets` (`04_DOMAIN_MODEL.md` §7). Contrairement à `Character.images` (Mission 002), `Dataset.images` devait être fonctionnel dès cette mission.

## Modifications principales

- `Dataset` (dataclass, 3 champs : `dataset_id`, `name`, `images`).
- `Character.datasets` : `list[str]` → `list[Dataset]` ; migration prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle sous l'ancien format).
- `DatasetManager` — CRUD, sélection, `add_images()` fonctionnel (déduplication, ordre préservé) ; `active_dataset_id` runtime-only.
- `DatasetsPage` — remplace le placeholder ; CRUD + import d'images à deux niveaux.
- `WorkspaceManagerError` — nouvelle exception publique, remplace l'import direct `WorkspaceStorageError` (Infrastructure) dans `MainWindow` — dette corrigée en ouverture de mission.

## Fichiers importants créés ou modifiés

Créés : `dataset.py`, `dataset_manager.py`, `test_dataset_roundtrip.py`.
Modifiés : `character.py`, `main_window.py`, `datasets_page.py` (placeholder → réelle), `workspace_manager.py`.

## Décisions techniques

- `Dataset.images` fonctionnel dès cette mission (contrairement à `Character.images`).
- Ownership implicite (pas de `character_id` stocké sur `Dataset`).
- `add_images(paths)` opère sur le dataset actif implicitement.
- Filtrage défensif `isinstance` dans `Character.from_dict()` sur `datasets`.

## Tests et validations

`test_dataset_roundtrip.py` (7 tests) : cycle complet, ordre/déduplication images, réinitialisation sélection à la suppression, reset de contexte, reconstruction `DatasetsPage`, absence de duplication d'abonnements, non-impact Dashboard/Images.

## Commit correspondant

`git log --oneline --reverse` entre `v0.2-mission002` et `v0.2-mission003` (7 commits — correspond exactement au chiffre du CHANGELOG) :

```
20e1564 Introduce WorkspaceManagerError, remove UI -> Infrastructure import
2602992 Introduce Dataset domain object
51fcfec Character.datasets: list[str] -> list[Dataset], with safe deserialization
f0c0a5b Introduce DatasetManager (CRUD, selection, add_images())
386650d Wire DatasetManager and a real DatasetsPage into MainWindow
67d80a6 Add Dataset lifecycle integration test suite
c811274 docs: document Mission 003 (Dataset domain) in README and CHANGELOG
```

## Tag / release correspondant

`v0.2-mission003` — **lightweight** (`git cat-file -t` = `commit`, pas `tag`), cible `c81127407ce2e3679a3b8810202f1236cc7d9e14`. Confirmé : l'une des deux exceptions historiques au type "annoté" du projet.

## État final

Mission terminée. `Character`/`Dataset` pleinement fonctionnels, 15 tests d'intégration, dette technique (`WorkspaceManagerError`) corrigée.
