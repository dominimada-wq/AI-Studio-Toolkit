# Mission 006 — Model Domain

Source : `CHANGELOG.md` (section "Mission 006 — Model Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire l'entité `Model`, **première entité rattachée exclusivement au `Workspace`, pas au `Character`** — démontré par huit citations Blueprint indépendantes (`04_DOMAIN_MODEL.md` §4/§5/§10/§27/§28, `02_ARCHITECTURE.md` §10/§11/§12) convergeant vers *"Models belong to the Workspace Library."*

## Modifications principales

- `Model` (dataclass, 3 champs : `model_id`, `name`, `file_path`).
- `Workspace.models` : `list` non typé → `list[Model]`.
- `ModelManager` — **premier Manager du projet sans dépendance à `CharacterManager`** ; `active_model_id` réinitialisé uniquement sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED` — prouvé par preuve inversée par exécution (un changement de personnage n'affecte jamais `active_model_id`).
- `ModelsPage` — remplace le placeholder à liste statique ; sélection de fichier via `QFileDialog.getOpenFileName` (singulier).

## Fichiers importants créés ou modifiés

Créés : `model.py`, `model_manager.py`, `test_model_roundtrip.py`.
Modifiés : `workspace.py`, `models_page.py` (placeholder → réelle), `main_window.py`.

## Décisions techniques

- `Model` rattaché exclusivement au `Workspace` — démontré par le Blueprint, pas supposé.
- `file_path` scalaire (pas une liste), aligné sur la convention `LoRA.files`/`lora_page.py`.
- `create()` sans validation de nom côté Manager (cohérent avec les 3 Managers précédents).
- Chaîne vide légitime pour `file_path` ("aucun fichier associé").
- Différé : scan automatique de fichiers, métadonnées descriptives, `Character.favorite_models`.

## Tests et validations

`test_model_roundtrip.py` (8 tests) : cycle complet, idempotence `update_file_path()` (chaîne vide incluse), suppression + persistance, **preuve inversée** (changement de personnage n'affecte jamais `active_model_id`), reconstruction `ModelsPage`, absence de duplication d'abonnements, non-impact Dashboard/Images, round-trip Domain.

## Commit correspondant

`git log --oneline --reverse` entre `v0.2-mission005` et `v0.2-mission006` (6 commits — correspond exactement au chiffre du CHANGELOG) :

```
41e0289 Introduce Model domain object (model_id, name, file_path)
84a2e5d Convert Workspace.models from list to list[Model]
8a46f58 Introduce ModelManager (CRUD, selection, update_file_path())
e6d97ea Wire ModelManager and a real ModelsPage into MainWindow
70befda Add Model lifecycle integration test suite
25ace27 docs: document Mission 006 (Model domain) in README and CHANGELOG
```

## Tag / release correspondant

`v0.2-mission006` — **lightweight** (`git cat-file -t` = `commit`, pas `tag`), cible `25ace27c5a303d4d4e731530a9549762fc576153`. Deuxième et dernière exception historique au type "annoté".

**Note post-publication** : le commit `cb60856` (`docs: correct Mission 006 modelsCard claim after Mission 007 audit`), situé chronologiquement entre ce tag et le début de Mission 007, corrige une affirmation erronée de la clôture Mission 006 (la carte Dashboard "Models" n'avait en réalité besoin d'aucun correctif). Ce commit n'appartient officiellement ni à Mission 006 ni à Mission 007 selon le CHANGELOG.

## État final

Mission terminée. Cinq entités Domain fonctionnelles, 37 tests d'intégration, premier pattern "ressource partagée au niveau Workspace" validé.
