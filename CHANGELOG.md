# Changelog

Toutes les évolutions notables du projet **AI Studio Toolkit** sont documentées dans ce fichier.

## Sommaire

- [Résumé de la mission](#résumé-de-la-mission)
- [Statistiques de la mission](#statistiques-de-la-mission)
- [Évolutions architecturales principales](#évolutions-architecturales-principales)
- [Bugs corrigés](#bugs-corrigés)
- [Tests ajoutés](#tests-ajoutés)
- [Prochaines étapes (Mission 002)](#prochaines-étapes-mission-002)
- [Améliorations UX futures](#améliorations-ux-futures)
- [État du projet](#état-du-projet)

---

## [v0.2-mission001](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission001) — 2026-08-10

### Résumé de la mission

**Mission 001 — Blueprint Refactoring.** Cette mission correspond au **Blueprint 02 (`docs/blueprint/02_ARCHITECTURE.md`)** : le prototype initial (gestion de "Project" ad hoc, logique métier dispersée dans l'UI, managers non utilisés) a été refactoré pour se conformer à l'architecture qui y est décrite, en cohérence avec les autres documents du Blueprint (`00_VISION.md` → `04_DOMAIN_MODEL.md`).

Cette mission n'a **ajouté aucune fonctionnalité nouvelle** : son unique objectif était de mettre le code existant en conformité avec les couches, les responsabilités et le sens de dépendance définis par le Blueprint (`Presentation → Managers → Services → Domain → Infrastructure → Engines`), tout en préservant le comportement observable de l'application.

Le travail a été mené en 9 commits atomiques, chacun revu, testé manuellement et validé avant exécution.

### Statistiques de la mission

| Indicateur | Valeur |
|---|---|
| Commits | 9 |
| Bugs corrigés | 3 |
| Tests d'intégration ajoutés | 2 |
| Packages morts supprimés | `src/config/`, `src/models/`, `src/widgets/`, `src/project/` |
| Architecture | Refactorisée (Presentation / Managers / Domain / Infrastructure / Core) |

### Évolutions architecturales principales

- **Introduction du Domain Layer** — `src/domain/workspace.py::Workspace`, un dataclass Qt-indépendant remplaçant l'ancienne dataclass `Project` (jamais utilisée) et reflétant fidèlement le schéma JSON réel. Le champ `root` (chemin du dossier) est explicitement runtime-only, jamais sérialisé, pour garder `project.json` portable.
- **Introduction de l'Infrastructure Layer** — `src/infrastructure/storage/workspace_storage.py::WorkspaceStorage`, portage durci de l'ancien `ProjectIO` : gestion d'erreurs typée (`WorkspaceStorageError`), journalisation, API dict-only (aucune dépendance vers le Domain, conformément au sens de dépendance du Blueprint).
- **Introduction de l'Application Layer** — `src/managers/workspace_manager.py::WorkspaceManager`, source unique de vérité pour le workspace courant, remplaçant l'ancien `ProjectManager` (jamais réellement instancié) et l'état dupliqué de `MainWindow`.
- **Introduction du Core / EventBus** — `src/core/event_bus.py::EventBus`, pub/sub minimal, Qt-indépendant, avec payloads réellement immuables (copie profonde + vue en lecture seule), permettant à la Presentation de réagir aux événements du workspace sans que les Managers ne dépendent de Qt.
- **`MainWindow` délègue entièrement à `WorkspaceManager`** — suppression de l'accès direct à l'Infrastructure (`ProjectIO`) et de l'état dupliqué (`current_project`/`project_folder`) ; `DashboardPage` et `ImagesPage` s'abonnent désormais aux événements du workspace plutôt que d'être mises à jour manuellement.
- **Extraction de la logique métier hors des widgets** — `ImagesPage` ne détient plus d'état privé ; l'import d'images passe par `WorkspaceManager.add_images()`, avec déduplication, et persiste réellement dans `project.json`.
- **Réorganisation de la structure de fichiers** — `src/pages/` déplacé sous `src/ui/pages/` ; suppression des packages vides non conformes (`src/config/`, `src/models/`, `src/widgets/`) ; suppression finale de `src/project/`, devenu totalement orphelin.

### Bugs corrigés

- **Dashboard non rafraîchi après création/ouverture d'un projet** — corrigé structurellement par le câblage événementiel (`WorkspaceManager` → `EventBus` → `DashboardPage.update_project`), plutôt que par un correctif ponctuel.
- **Une tentative d'ouverture d'un dossier invalide fermait silencieusement le workspace déjà ouvert** — `WorkspaceManager.open()` réinitialisait `current_workspace` à `None` même en cas d'échec, faisant perdre le projet en cours sans avertissement visible. Corrigé : un échec d'ouverture laisse désormais l'état courant inchangé. Cette règle métier est maintenant protégée par un test de non-régression permanent.
- **`WorkspaceManager.close()` ne publiait plus l'événement `workspace.closed`** — régression introduite lors de l'ajout d'`add_images()` (ligne de publication déplacée par erreur après un `return`, dans la mauvaise méthode). Détectée par le test d'intégration écrit pour cette même mission, corrigée dans la foulée.

### Tests ajoutés

- `tests/integration/test_workspace_roundtrip.py` (stdlib `unittest`, aucune nouvelle dépendance) :
  - `test_full_create_import_save_close_reopen_cycle` — cycle complet création → import d'images → sauvegarde → fermeture → réouverture (avec instances fraîches, simulant un vrai redémarrage), vérifiant la persistance des images et la mise à jour correcte du Dashboard et de la page Images.
  - `test_failed_open_does_not_close_current_workspace` — garde de non-régression permanente pour la règle métier « une ouverture échouée ne doit jamais fermer le workspace courant ».

### Prochaines étapes (Mission 002)

Hors périmètre de la Mission 001, à traiter dans des missions dédiées ultérieures :

- Introduction du domaine **Character** (entité centrale du Blueprint, actuellement absente) et de la propriété des ressources (Datasets, LoRAs, Prompts, Historique) qui lui revient.
- Introduction progressive des autres objets du Domain Model (`Dataset`, `Model`, `LoRA`, `Job`, `Engine`, `Plugin`) — un par mission, sans scaffolding anticipé.
- Introduction de la couche **Services** dès qu'une logique métier réelle la justifiera.
- Introduction de `src/engines/` et `src/plugins/` lors de la première intégration réelle avec un moteur externe (ComfyUI, OneTrainer, etc.).

### Améliorations UX futures

- Création automatique du dossier cible directement depuis le dialogue "Nouveau projet", sans devoir le créer manuellement au préalable dans l'explorateur Windows.

### État du projet

**Mission 001 est terminée.** L'application dispose désormais d'une architecture conforme au Blueprint 02, d'une suite de tests d'intégration et d'une documentation à jour (`README.md`, ce `CHANGELOG.md`).

**Mission 002** introduira le domaine **Character**, entité centrale du Blueprint (`docs/blueprint/04_DOMAIN_MODEL.md`), actuellement absente du code.

---

*Généré à l'issue de la Mission 001 — Blueprint Refactoring.*
