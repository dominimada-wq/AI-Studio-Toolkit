# Mission 011 — Image Domain

Source : historique direct de la conversation de développement (audit architectural préalable, spécification d'ownership validée, implémentation, revue technique finale), vérifié contre le code réel et la suite de tests.

## Objectif

Introduire une représentation Domain minimale et cohérente des images existantes — sans anticiper les fonctionnalités Generation — en remplacement des chaînes brutes (`list[str]`) actuellement dispersées et incohérentes entre `Workspace.images`, `Dataset.images` et un `Character.images` mort.

## Architecture retenue — Ownership `Image` (Modèle D, contextuel et structurel)

Un audit d'ownership dédié (préalable à toute implémentation) a comparé quatre modèles (Workspace-owned seul, Character-owned seul, Dataset-owned seul, hybride contextuel) contre le comportement réel du code — pas seulement contre le Blueprint. Conclusion retenue :

- `Workspace` possède son propre pool d'`Image` (`Workspace.images: list[Image]`).
- Chaque `Dataset` possède son propre pool d'`Image` (`Dataset.images: list[Image]`, Character-owned par transitivité, comme `Dataset` lui-même).
- **Pools strictement indépendants** : aucun registre global, aucune référence croisée. Une même valeur `file_path` présente dans les deux pools représente deux instances `Image` distinctes, avec deux `image_id` distincts.
- Ce modèle a été retenu car c'est le seul qui ne romptait aucun comportement fonctionnel déjà existant (le chemin d'import Dataset a toujours été volontairement indépendant du chemin d'import Workspace, documenté dès Mission 003) tout en éliminant la dette de représentation (`str` → `Image`).

## Image Domain

`src/domain/image.py`, structure exacte :

```python
@dataclass
class Image:
    image_id: str = ""
    file_path: str = ""
```

Aucun autre champ. Explicitement exclus (dépendent d'une `Generation` inexistante) : Generation ID, Seed, Sampler, Steps, CFG, Engine, Model, LoRA List, Workflow, Rating, Favorite, Archived, Tags, Notes, métadonnées de génération.

## `Character.images`

**Supprimé** (dataclass, `to_dict()`, `from_dict()`). Justification par le code réel, pas seulement le Blueprint : ce champ n'a jamais été lu ni écrit par aucun Manager (`character_manager.py` ne le référence nulle part) ni par aucune Page (`characters_page.py` ne le référence nulle part), et son caractère non fonctionnel était déjà documenté dans le code source dès son introduction (Mission 002/003 : *"Unlike Character.images in Mission 002, this field will actually be populated..."*, commentaire historique de `dataset.py`). Aucun test n'exerçait ce champ — suppression sans impact de couverture. La relation `Character → Image` reste strictement transitive via `Character → Dataset → Image`.

## Managers

- `WorkspaceManager.add_images()` et `DatasetManager.add_images()` adaptés pour construire des `Image` (`image_id=uuid4()`, `file_path=path`) au lieu de chaînes brutes. La déduplication prospective continue de fonctionner par `file_path`.
- **Aucun `ImageManager`** introduit, décision explicite et motivée : `Image` n'a pas de cycle de vie CRUD autonome (pas de sélection, pas d'`active_id`) contrairement à `Model`/`Workflow`/`Settings`/`ApplicationSettings`, qui justifiait chacun son propre Manager dédié. `Image` est un élément d'une collection déjà pilotée par un Manager existant.

## Migration

Ancien format : `"images": ["a.png", "b.png"]`
Nouveau format : `"images": [{"image_id": "...", "file_path": "..."}]`

Règles implémentées (`Image.list_from_data()`, partagé entre `Workspace.from_dict()` et `Dataset.from_dict()`) :
- Conversion à la lecture uniquement — aucune réécriture forcée du fichier utilisateur pendant le chargement ; le nouveau format n'est écrit qu'à la prochaine sauvegarde normale.
- Un `uuid4()` est généré pour chaque entrée `str` legacy convertie.
- Cet identifiant est stable dès la première sauvegarde au nouveau format ; avant cette sauvegarde, deux chargements successifs du même fichier legacy produisent des `image_id` différents pour la même entrée (aucun identifiant n'existait avant la migration — comportement attendu, vérifié explicitement).
- Une entrée `dict` n'est conservée que si `file_path` est un `str` non vide.
- Une entrée `str` legacy n'est conservée que si elle est non vide.
- Toute autre entrée (mauvais type, `file_path` vide/`None`/non-`str`) est filtrée silencieusement, sans exception.
- Les doublons de chemin historiques sont préservés comme instances `Image` distinctes (aucune fusion, aucune perte de données).
- La déduplication ne s'applique que **prospectivement**, lors des nouveaux imports via `add_images()` — jamais rétroactivement sur des données déjà migrées.
- `Workspace.images` et `Dataset.images` sont migrés indépendamment l'un de l'autre — aucune fusion entre les deux pools.

## UI

- `ImagesPage.update_images()` et `DatasetsPage.update_datasets()` adaptées pour afficher `image["file_path"]` (les Pages consomment le payload `to_dict()`, donc des dictionnaires) au lieu de traiter chaque entrée comme une chaîne directe.
- Aucun changement de comportement fonctionnel ou de présentation au-delà de cette migration.

## Tests

- Nouveau fichier `tests/integration/test_image_roundtrip.py` — **10 tests** : défauts/round-trip Domain, migration Workspace, migration Dataset, round-trip nouveau format avec conservation exacte des `image_id`, stabilité des identifiants après sauvegarde/réouverture réelle, déduplication prospective par `file_path`, indépendance prouvée des deux pools (même `file_path`, deux instances, deux `image_id`, `assertIsNot`), suppression de `Character.images`, et filtrage explicite des `dict` sans `file_path` exploitable (ajouté en revue finale, voir ci-dessous).
- **90/90 tests d'intégration verts** (80 précédents adaptés/inchangés + 10 nouveaux).
- Exécution réelle des widgets Qt (`QApplication`, pas seulement inspection de code) : `ImagesPage.list_widget`, `DatasetsPage.images_list`, y compris après fermeture/réouverture réelle du Workspace.
- Migration legacy testée explicitement (`list[str]` → `list[Image]`, préservation des chemins, génération d'identifiants, doublons, entrées invalides).
- Persistance/rechargement testés (`test_manager_add_images_ids_stable_across_save_and_reopen`).
- Indépendance des deux pools testée (`test_workspace_and_dataset_pools_are_independent`).

## Correction découverte en revue finale

Avant commit, une revue technique dédiée à `Image.list_from_data()` a révélé une divergence réelle par rapport à la spécification validée : la première implémentation acceptait silencieusement **tout** `dict`, sans vérifier la validité de `file_path`. Concrètement, `{}` aurait produit `Image(image_id="", file_path="")`, et `{"image_id": "abc"}` aurait produit `Image(image_id="abc", file_path="")` — exactement les deux cas que la spécification interdisait explicitement.

Corrigée avant tout commit :
- une entrée `dict` n'est désormais conservée que si `file_path` est un `str` non vide ;
- une entrée `str` legacy n'est désormais conservée que si elle est non vide ;
- `Image.from_dict()` reste inchangé, simple et défensif (la décision de validité reste entièrement dans `list_from_data()`) ;
- test de régression ajouté (`test_list_from_data_filters_dicts_without_usable_file_path`), couvrant explicitement `{}`, `{"image_id": "abc"}`, `{"file_path": ""}`, `{"file_path": None}`, `{"file_path": 42}`, entouré d'entrées valides pour prouver qu'elles survivent ;
- suite finale confirmée **90/90 verte** après correction.

Cette information fait partie de l'historique technique réel de la mission et est volontairement conservée, conformément à la règle du projet de ne jamais effacer une divergence corrigée en cours de mission.

## Fichiers créés

- `src/domain/image.py`
- `tests/integration/test_image_roundtrip.py`

## Fichiers modifiés

- `src/domain/workspace.py`
- `src/domain/dataset.py`
- `src/domain/character.py`
- `src/managers/workspace_manager.py`
- `src/managers/dataset_manager.py`
- `src/ui/pages/images_page.py`
- `src/ui/pages/datasets_page.py`
- `tests/integration/test_workspace_roundtrip.py`
- `tests/integration/test_dataset_roundtrip.py`
- `tests/integration/test_training_roundtrip.py` (retrait de 3 lignes exerçant l'ancien `Character.images`, couverture équivalente déjà assurée par la comparaison complète de `Character.datasets`)
- `docs/PROJECT_CONTEXT.md`

Liste vérifiée directement depuis `git status --short`/`git diff --stat` au moment de la clôture.

## Critères d'acceptation — état final

- Audit d'ownership tranché et documenté avant implémentation : ✅ (Modèle D).
- `Image` existe comme Domain minimal, aucun champ hors périmètre : ✅ (2 champs exacts).
- Images existantes migrées sans perte (`list[str]` → `list[Image]`) sur `Workspace.images` et `Dataset.images` : ✅, testé explicitement.
- Sort de `Character.images` explicitement tranché : ✅ (suppression justifiée).
- Suite de tests complète verte, nombre exact confirmé : ✅ (90/90).
- Aucun fichier hors périmètre modifié : ✅, vérifié par `git status`/`git diff --stat` à chaque étape.
- Documentation de fin de mission complète : ✅ (ce document + `docs/PROJECT_CONTEXT.md`).

## Dettes hors périmètre (volontairement non traitées par Mission 011)

- `BasePage` (code mort).
- Ambiguïté `Training` vs `Training History`.
- Incohérences documentaires `Job` dans le Blueprint.
- Support Linux/macOS non vérifié pour `ApplicationSettingsStorage`.
- `Generation`, exécution réelle de `Job`, `Service`, `Plugin`, `Engine`, `AI Orchestrator`.
- Suppression individuelle d'une `Image`.
- Tout traitement physique de fichier (copie, redimensionnement, thumbnailing).

## Commit correspondant

Mission 011 a été implémentée en une seule session continue, sans commits intermédiaires. À la demande explicite de l'architecte pour cette clôture, l'ensemble (Domain/Manager/UI/tests/documentation) est regroupé en **un commit unique** : `feat: introduce Image Domain` — dérogation ponctuelle à la granularité atomique habituelle du projet (une seule mission sur onze concernée à ce jour), non reconductible par défaut pour les missions futures sans nouvelle décision explicite de l'architecte.

Le hash exact de ce commit ne peut pas être connu au moment où ce document est rédigé (il fait lui-même partie du contenu de ce commit). Il est renseigné, avec le reste des références de HEAD, par le commit documentaire de synchronisation qui suit immédiatement — voir `docs/PROJECT_CONTEXT.md`, section "HEAD actuel de `main`".

## Tag / release correspondant

`v0.2-mission011` (annoté), prévu pour cibler le commit de clôture ci-dessus.

## État final

Mission terminée. `Image` devient la 11ᵉ entité Domain du projet, premier pattern d'ownership contextuel (deux pools indépendants d'un même type, sans registre partagé) après les patterns Character-owned/Workspace-owned/singleton déjà établis. Première migration du projet portant sur des données réellement présentes. 90 tests d'intégration. Mission 012 non définie ; le prérequis architectural le plus probable pour une future mission Generation reste la chaîne `Service → AI Orchestrator → Plugin → Engine`, entièrement absente du code à ce jour.
