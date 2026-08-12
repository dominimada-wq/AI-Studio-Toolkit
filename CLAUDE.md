# CLAUDE.md — Règles permanentes du projet AI Studio Toolkit

Ce fichier contient les règles et instructions qui doivent rester valables d'une mission à l'autre. Il ne doit **jamais** devenir un journal des missions — l'historique détaillé vit dans `docs/PROJECT_CONTEXT.md` et `docs/missions/`.

## Objectif général du projet

AI Studio Toolkit est une application desktop (PySide6) qui orchestre la production de personnages numériques générés par IA — gestion de workspace, personnages, datasets, LoRA, prompts, modèles, workflows, entraînement, génération d'images/vidéos. Le logiciel **ne remplace pas** les moteurs IA existants (ComfyUI, OneTrainer, Kohya_ss, moteurs cloud) — il les **orchestre**. Source de vérité produit/architecture : `docs/blueprint/` (5 fichiers : `00_VISION.md`, `01_PRODUCT_REQUIREMENTS.md`, `02_ARCHITECTURE.md`, `03_PROJECT_STRUCTURE.md`, `04_DOMAIN_MODEL.md`). Le Blueprint n'est **jamais modifié** sans décision architecte explicite et séparée.

## Architecture et principes fondamentaux

Couches strictement descendantes, définies dans `02_ARCHITECTURE.md` :

```
Presentation (src/ui/) → Managers (src/managers/) → Domain (src/domain/) → Infrastructure (src/infrastructure/) → Core/EventBus (src/core/)
```

- **Single Source of Truth** — un seul objet représente l'état réel à un instant donné ; jamais de duplication d'état entre l'UI et les Managers.
- **Dependency Rule** — les dépendances ne remontent jamais.
- **Event Driven UI** — les pages ne se rafraîchissent jamais par appel direct entre elles ; uniquement via l'`EventBus`.
- **Domain indépendant de Qt** — aucun objet `src/domain/` n'importe PySide6.
- **Infrastructure ignorant le Domain** — la couche de stockage échange des dictionnaires, jamais des objets métier.
- **Managers sans widgets Qt** — coordonnent l'état applicatif, ne créent/lisent/modifient jamais un widget directement.
- **EventBus générique** (`src/core/event_bus.py`) — ne contient **aucune** constante d'événement. Chaque constante (`"domain.verbe"`, ex. `"character.created"`) est définie localement dans son module Manager, jamais centralisée.

Deux patterns d'ownership établis pour les entités Domain, plus deux variantes singleton :
- **Character-owned** (`Dataset`, `LoRA`, `Prompt`, `Training`) : Manager `(character_manager, workspace_manager, event_bus=None)`, `active_*_id` réinitialisé sur `CHARACTER_SELECTED`/`DELETED` + `WORKSPACE_*`.
- **Workspace-owned** (`Model`, `Workflow`) : Manager `(workspace_manager, event_bus=None)`, `active_*_id` réinitialisé uniquement sur `WORKSPACE_*`.
- **Singleton Workspace-owned** (`Settings`) : pas de collection, pas d'`active_id`, pas d'`event_bus` (aucun événement propre) — mirroir `WorkspaceManager.save()` → `WORKSPACE_SAVED` comme seul canal de notification.
- **Singleton Application-level** (`ApplicationSettings`) : aucune dépendance à `WorkspaceManager`, stockage physique propre hors `project.json`, événement dédié publié uniquement après sauvegarde réussie.

**Persistance** : un seul fichier `project.json` par Workspace (`WorkspaceStorage`), sauf `ApplicationSettings` qui vit dans un fichier séparé hors de tout Workspace (`ApplicationSettingsStorage`, `%LOCALAPPDATA%\AIStudioToolkit\application_settings.json` sous Windows).

## Conventions de développement

- **Domain objects** : dataclasses minimales (`@dataclass`, champs `= ""`/`= []` par défaut), `to_dict()`/`from_dict()` symétriques. Scalaires : `data.get(key, default)`. Listes mutables : `(data.get(key) or [])`. Le Manager génère les ID (`uuid.uuid4()`), jamais le dataclass lui-même.
- **Aucun commentaire lié à un numéro de mission/commit dans le code Domain** — le Domain doit rester intemporel. Les décisions historiques vivent dans `CHANGELOG.md`/`docs/missions/`, pas dans le code.
- **Compatibilité défensive, jamais migration implicite** : filtrage `isinstance(x, dict)` sur toute liste d'objets imbriqués désérialisée, pour tolérer un `project.json` édité à la main — jamais présenté comme une migration de données réelles.
- **Garde de type explicite** (`isinstance(x, dict)`) plutôt que vérité simple (`x or default`) quand une valeur mal typée mais truthy (`42`, `"abc"`, `[...]`) doit aussi être rejetée.
- **Aucune validation de contenu métier dans les Managers** (noms vides, chemins, etc.) — c'est la responsabilité de l'UI si nécessaire. `create()` ne valide jamais le nom, ne sélectionne jamais automatiquement l'objet créé.
- **Idempotence stricte** pour toute méthode `update_*()`/`update()` : valeur identique → `False`, aucun `save()`, aucun événement. Chaîne vide (`""`) est une valeur légitime, distincte de "non fourni" (`None`).
- **Pattern UI de rafraîchissement** : `blockSignals(True)` → `clear()` → reconstruction → `setCurrentItem()` → `blockSignals(False)`, pour toute méthode `update_X()` de Page.
- **Sidebar/Stack** : alignement strictement positionnel (`sidebar.currentRowChanged.connect(stack.setCurrentIndex)`). Toute nouvelle page doit être ajoutée au même index relatif dans `sidebar.py` et `main_window.py::stack.addWidget()`, vérifié par exécution réelle, pas seulement par lecture.
- **Pas de scaffolding avant un besoin réel** — ne jamais introduire de Domain/Manager/UI pour une fonctionnalité future hypothétique sans consommateur actuel.
- **Ne jamais transposer automatiquement un pattern d'une mission précédente** — chaque nouvelle entité doit être auditée contre le Blueprint indépendamment (ownership, attributs, événements), pas copiée par analogie.

## Contraintes techniques importantes

- Windows (`win32`), PowerShell principal, Bash (Git Bash) disponible et généralement préféré pour les commandes git/python dans ce projet (chemins Unix).
- `.venv/Scripts/python.exe` requis pour tout ce qui touche PySide6 (absent du Python système).
- Tests : stdlib `unittest` uniquement, aucune dépendance de test externe (pas de pytest).
  ```bash
  ./.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
  ```
- Aucune nouvelle dépendance ajoutée sans validation explicite de l'architecte — toujours vérifier si la stdlib ou une dépendance déjà installée suffit avant d'en proposer une nouvelle.
- Scripts de vérification temporaires : **toujours** dans le scratchpad de session, **jamais** dans le dépôt. Confirmer leur absence (`git status`, `git ls-files`) avant chaque commit.

## Conventions de nommage

- Fichiers Python : `snake_case.py`. Classes : `PascalCase`. Méthodes : `snake_case()`. Constantes : `UPPER_CASE`.
- Événements : `"domaine.verbe"` en minuscules (ex. `"training.created"`, `"application_settings.updated"`).
- Fichiers de test : `tests/integration/test_<domaine>_roundtrip.py`, classe `<Domaine>RoundTripTest(unittest.TestCase)`.

## Règles Git

- Branche principale : `main`.
- **Jamais** de `git push --force`, `rebase`, `merge`, `reset --hard`, `cherry-pick` sans autorisation explicite et ponctuelle.
- Avant tout push : `git fetch origin`, `git rev-list --left-right --count origin/main...main`, vérifier qu'aucun commit étranger n'est intercalé et qu'aucun commit distant n'est absent de `main`.
- Commits **atomiques**, un seul objectif chacun — ne jamais mélanger Domain/Storage/Manager/UI dans un même commit, même quand la mission introduit un nouveau type de stockage.
- Message de commit court et factuel, style impératif anglais (ex. `Add atomic ApplicationSettings storage`), aligné sur l'historique existant (`git log`).

## Commits, tags et releases

- **Aucun code n'est écrit sans rapport d'impact préalable, validé explicitement par l'architecte.** Un message qui se contente de reproduire le rapport précédent (sans "je valide" ou équivalent explicite) n'est **pas** une validation — redemander confirmation avant d'agir.
- Séquence stricte par commit : rapport d'impact → validation → implémentation → vérifications (manuelles + suite complète) → rapport d'exécution → validation → commit → rapport post-commit → rapport d'impact du commit suivant.
- Tags : **annotés** (`git tag -a vX.Y-missionNNN <commit> -m "..."`), convention `v0.2-missionNNN`. Deux exceptions historiques en lightweight (`v0.2-mission003`, `v0.2-mission006`) — ne pas reproduire ce type pour les futurs tags sans décision explicite.
- Le tag et le push de `main` ne sont créés qu'après validation explicite d'un audit pré-push complet (état Git, absence de divergence, absence de commit étranger).
- GitHub Release : Claude peut rédiger le titre et les Release Notes complètes en Markdown, mais **ne publie jamais lui-même** sans autorisation explicite finale.

## Procédures de validation

- Toute mission suit : **audit architectural préalable** (Blueprint + code existant) → **choix de mission validé par l'architecte** → **rapport d'impact par commit** → **implémentation** → **vérifications comportementales réelles** (widgets Qt réels quand UI concernée, pas seulement inspection de code) → **validation** → **commit** → répétition jusqu'à la documentation finale (README/CHANGELOG) → **tag** → **push** → **Release**.
- Toute fonctionnalité hors périmètre d'une mission doit être explicitement listée comme "non implémentée / différée" dans la documentation, jamais laissée ambiguë.
- Après chaque commit : relancer la suite complète de tests et confirmer le nombre exact attendu (ex. `80/80`), vérifier `git status --short`/`git diff --stat` pour confirmer que seuls les fichiers annoncés sont touchés.

### Workflow de fin de mission (règle permanente)

Chaque future mission doit se clore selon cette séquence exacte, dans l'ordre :

```
Mission terminée
→ tests et vérifications (suite complète, nombre exact confirmé)
→ mise à jour de docs/PROJECT_CONTEXT.md (état consolidé, pas de journal détaillé)
→ création ou mise à jour de docs/missions/MISSION_XXX.md (archive de la mission)
→ vérification de cohérence documentaire (CLAUDE.md / PROJECT_CONTEXT.md / missions/ / CHANGELOG.md / historique Git ne se contredisent pas)
→ commit
→ tag lorsque prévu
→ GitHub Release lorsque prévue
```

`CLAUDE.md` lui-même n'est modifié **que** lorsqu'une règle permanente, une convention ou un principe architectural change — jamais pour consigner un état de mission (qui appartient à `docs/PROJECT_CONTEXT.md`) ou un historique (qui appartient à `docs/missions/`).
