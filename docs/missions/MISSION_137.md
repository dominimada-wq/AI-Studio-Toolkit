# Mission 137 — Harden Workspace/Character Creation Invariant

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en attente de validation externe.** L'audit post-Mission 136 a confirmé deux problèmes réels dans le cycle de vie Workspace/Character. **Problème principal** : `CharacterManager._ensure_default_character()` garantit l'invariant produit « un Workspace créé a toujours un Character principal » (Mission 026/036) en tant que simple *subscriber* de `WORKSPACE_CREATED` — depuis M136, `EventBus.publish()` journalise puis absorbe toute exception de subscriber sans jamais la relever, donc un échec de cette auto-création est désormais **silencieusement avalé** : `WorkspaceManager.create()` retourne un succès à son appelant alors que le Workspace n'a en réalité aucun Character, sans aucun recours UI (`CharactersPage` a ses contrôles de création/liste masqués depuis Mission 026). **Problème secondaire** : `Workspace.from_dict()` ne filtre pas `characters` par `isinstance(c, dict)`, contrairement à `models`/`workflows`/`settings` dans le même fichier. **Architecture finale retenue** (résolvant explicitement le point resté ouvert lors de la première itération de ce document — le timing de `WORKSPACE_CREATED`) : `WorkspaceManager.create()` est scindée, sans duplication, en une primitive interne `create_without_publishing()` (matérialisation seule) et une méthode `publish_created()` (publication seule) — `create()` elle-même reste **strictement inchangée pour tous ses appelants actuels** (~390 sites de test, comportement/exceptions/timing d'événement identiques). Une nouvelle primitive d'orchestration, `create_workspace_with_default_character(workspace_manager, character_manager, folder)` (nouveau module `src/managers/workspace_lifecycle.py`, fonction libre, aucune dépendance circulaire), matérialise le Workspace, crée et sélectionne le Character principal, et **ne publie `WORKSPACE_CREATED` qu'une fois l'invariant complet satisfait** — en cas d'échec avant ce point : rollback complet (best-effort, idiome cleanup-then-raise déjà établi par `LoRALibraryManager.import_lora()`/Mission 134), aucun `WORKSPACE_CREATED` jamais publié, `WorkspaceManagerError` relevée au caller. `MainWindow.new_project()` devient l'unique appelant produit de cette nouvelle primitive ; tous les autres appelants existants de `WorkspaceManager.create()` restent inchangés. Ordre d'événements cible sur succès, vérifié subscriber par subscriber (aucun ne suppose `WORKSPACE_CREATED` déjà publié) : `WORKSPACE_SAVED → CHARACTER_CREATED → CHARACTER_SELECTED → WORKSPACE_CREATED`. Environ 9 à 11 tests existants (précisément identifiés en §5.1/§14) nécessitent une adaptation — un nombre borné et vérifié, pas les ~390 sites initialement redoutés. Cette version résout intégralement le point laissé ouvert par la première itération de ce document.

## 1. Contexte

Fait suite à l'audit global post-Mission 135 (Mission 136, EventBus Fault-Isolation Policy) puis à l'audit global post-M136, qui a confirmé et aggravé un constat déjà documenté par M136 sans être corrigé : `CharacterManager._ensure_default_character()` accomplit une étape métier déguisée en subscriber EventBus, dont l'échec est désormais silencieusement avalé plutôt que bruyamment (mais déjà mal) signalé comme avant M136.

Une première itération de ce document proposait une architecture (orchestrateur au-dessus des deux Managers, rollback complet) validée sur le principe par l'architecte et par ChatGPT, mais laissait explicitement ouverte la question du timing exact de `WORKSPACE_CREATED` (« Option 1 » vs « Option 2 »). **Cette question est désormais tranchée** (§6, §9) : l'architecture cible ne publie jamais `WORKSPACE_CREATED` avant que l'invariant Character soit satisfait, conformément à la décision explicite de l'architecte. Cette version du document intègre également une investigation approfondie, non faite lors de la première itération, sur l'ampleur réelle des tests affectés (§5.1), qui corrige une estimation initiale trop optimiste.

## 2. Investigation 1 — Contrat produit exact (inchangé depuis la première itération, revérifié)

**Le contrat produit est un fait établi, documenté à trois endroits indépendants, jamais ambigu :**

- `CharacterManager._ensure_default_character()`'s docstring ([character_manager.py:53-64](../../src/managers/character_manager.py)) : *« Mission 026: a freshly created Workspace should not force a "New character" click before its identity fiche is usable — exactly one principal Character is created and selected »*.
- `CharacterManager.principal_character`'s docstring ([character_manager.py:100-116](../../src/managers/character_manager.py)) : *« the auto-created principal is always created before any other Character can exist (Mission 026 decision 1) »*.
- `CharactersPage.reset_for_context_change()`'s docstring ([characters_page.py:406-409](../../src/ui/pages/characters_page.py)) qualifie un Workspace sans Character de *« a defensive edge case, never reachable through the real "1 Workspace = 1 principal Character" UI »*.

**Distinction contrat produit / tolérance technique du Domain, vérifiée directement** : `principal_character` retourne `None` proprement ([character_manager.py:118-123](../../src/managers/character_manager.py)) ; `DatasetManager`/`LoRAManager`/`PromptManager`/`TrainingManager` retournent tous `[]` si `principal_character is None` ; `CharactersPage._load_identity_fields(None)` vide simplement la fiche. Aucun crash nulle part — une tolérance défensive, jamais un état produit légitime.

**Précision nouvelle, trouvée lors de l'investigation complémentaire (§5.1)** : un Workspace à 0 Character **est** déjà, aujourd'hui, un état délibérément atteint et testé — pas seulement via un échec de création, mais via `CharacterManager.delete()` (qui n'a aucune garde contre la suppression du dernier Character). Au moins 7 tests existants (`test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py`, et 3 dans `test_character_roundtrip.py`) créent délibérément un Workspace, suppriment son Character auto-créé, puis vérifient qu'un avertissement UI cohérent apparaît (`DatasetsPage.create_dataset()` : *« Aucun personnage — Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un dataset. »*, message identique en substance pour LoRA/Prompt/Training). **Ce message renvoie vers une action ("créez-en un depuis Characters") impossible dans l'UI actuelle** (boutons masqués, §7) — une incohérence UX préexistante, orthogonale à M137, non corrigée ici (hors périmètre, réactivation de l'UI multi-Character explicitement exclue) mais qui renforce la justification du rollback (§6) : laisser un Workspace échoir dans cet état via un échec de création serait un second chemin vers le même dead-end UX déjà connu.

## 3. Investigation 2 — Cartographie de `WorkspaceManager.create()` (inchangée depuis la première itération)

Code exact ([workspace_manager.py:136-152](../../src/managers/workspace_manager.py)) :
```python
def create(self, folder) -> Workspace:
    folder = Path(folder)
    workspace = Workspace(name=folder.name, root=folder)
    try:
        WorkspaceStorage.create_directories(folder)
        WorkspaceStorage.save(folder, workspace.to_dict())
    except WorkspaceStorageError as exc:
        raise WorkspaceManagerError(str(exc)) from exc
    self.current_workspace = workspace
    self._publish(WORKSPACE_CREATED)
    return workspace
```
Séquence : (1) aucune validation ; (2) `Workspace(...)` en mémoire, `characters=[]` ; (3) `WorkspaceStorage.create_directories(folder)` ; (4) `WorkspaceStorage.save(folder, workspace.to_dict())`, premier `save()`, `characters: []` ; (5) `self.current_workspace = workspace`, **avant** publication ; (6) `self._publish(WORKSPACE_CREATED)` — déclenche aujourd'hui, de façon imbriquée, toute la création du Character ; (7) `return workspace`, valeur **jamais utilisée** par le seul appelant réel.

**Artefacts filesystem créés par cette méthode** : l'arborescence de dossiers (`WorkspaceStorage.DIRECTORIES`, vérifiée dans `create_directories()`, [workspace_storage.py:54-70](../../src/infrastructure/storage/workspace_storage.py)) et `project.json`. Aucun fichier physique dédié au Character n'est jamais créé nulle part (seule une entrée dans `project.json`) — **une suppression récursive du dossier racine du Workspace efface donc, en une seule opération, tout ce que cette séquence peut avoir produit, sans qu'aucun artefact ne puisse jamais exister en dehors de ce dossier**. Ce fait est décisif pour le rollback (§6).

## 4. Investigation 3 — Cartographie de la création du Character (inchangée depuis la première itération)

### 4.1 `CharacterManager.create()` ([character_manager.py:134-153](../../src/managers/character_manager.py))
```python
def create(self, name: str) -> Optional[Character]:
    workspace = self._workspace_manager.current_workspace
    if workspace is None:
        return None
    character = Character(character_id=str(uuid.uuid4()), name=name)
    workspace.characters.append(character)          # mutation Domain, AVANT le save()
    try:
        self._workspace_manager.save()                 # second save() -> publish(WORKSPACE_SAVED)
    except WorkspaceManagerError:
        workspace.characters.remove(character)          # rollback Domain — seulement ici
        raise
    self._publish(CHARACTER_CREATED, character)          # aucun try/except autour de ceci
    return character
```
**Point décisif pour l'ordre des événements (§6)** : `workspace.characters.append(character)` a lieu **avant** l'appel `save()` qui publie `WORKSPACE_SAVED` — donc au moment où `WORKSPACE_SAVED` est publié, `workspace.characters` contient **déjà** le nouveau Character. Aucun subscriber de `WORKSPACE_SAVED` ne peut donc observer un état à moitié construit.

### 4.2 `_ensure_default_character()` ([character_manager.py:52-74](../../src/managers/character_manager.py))
```python
def _ensure_default_character(self, payload) -> None:
    workspace = self._workspace_manager.current_workspace
    if workspace is None or workspace.characters:
        return
    character = self.create(workspace.name)
    self.select(character.character_id)
```
- **Rollback existant** : uniquement le `workspace.characters.remove(character)` de `create()` lui-même, sur son propre échec de `save()` — jamais sur un échec de `publish()` qui suit (preuve déjà établie par M136 §4.2 du caractère post-commit d'EventBus).
- **Comportement de `select()` si `create()` réussit** : `select()` ([character_manager.py:155-166](../../src/managers/character_manager.py)) n'a **structurellement aucun chemin d'échec réel** — recherche par ID (garanti trouvé, l'ID vient d'être créé), assignation mémoire, `_publish(CHARACTER_SELECTED, character)`. Le seul risque théorique résiduel (exception de subscriber sur `CHARACTER_SELECTED`) est déjà absorbé par `publish()` depuis M136 et ne remonte jamais. **`select()` n'est donc pas une source de rollback réaliste aujourd'hui** — confirmé, pas supposé.

## 5. Investigation 4 — Dépendances Managers : circularité confirmée, ampleur réelle des tests affectés

**Constructeurs vérifiés** : `WorkspaceManager.__init__(self, event_bus=None)` ne référence aucun autre Manager ; `CharacterManager.__init__(self, workspace_manager, event_bus=None)` dépend de `WorkspaceManager`. **Import module-level** : `character_manager.py` importe `workspace_manager.py` — l'inverse créerait un import circulaire Python bloquant si `WorkspaceManager` devait publier des constantes définies dans `character_manager.py`.

**Réponse confirmée** : un appel direct `WorkspaceManager.create() → CharacterManager.create()` exigerait d'injecter `CharacterManager` dans `WorkspaceManager`, alors que `CharacterManager` exige déjà un `WorkspaceManager` construit — **dépendance circulaire d'instanciation réelle, confirmée par le code**.

### 5.1 Callers réels de `WorkspaceManager.create()` — classification complète et ampleur précise des tests affectés

**Production** : un seul caller, `MainWindow.new_project()` ([main_window.py:614](../../src/ui/main_window.py)), confirmé par recherche exhaustive dans `src/`.

**Migration/outillage** : aucun trouvé (pas de script CLI/migration appelant `WorkspaceManager.create()`).

**Tests** : `WorkspaceManager(` est instancié dans **17 fichiers** de test. Parmi eux, **12 construisent également un `CharacterManager`** dans le même wiring — et parce que `CharacterManager.__init__()` souscrit `_ensure_default_character` à `WORKSPACE_CREATED` **en interne, à la construction, sans qu'aucun code de test ne le demande explicitement** ([character_manager.py:44-47](../../src/managers/character_manager.py)), tout appel à `workspace_manager.create()` dans ces 12 fichiers déclenche déjà, aujourd'hui, la création automatique — sans que le test lui-même en ait conscience.

**Investigation approfondie de l'impact réel (correction d'une sous-estimation initiale)** : un premier passage avait compté ~390 sites d'appel `workspace_manager.create()` dans ces 12 fichiers et redouté une migration massive. **Vérification directe de leur contenu réel** infirme ce risque pour l'écrasante majorité :

- La grande majorité des tests (ex. `test_dataset_roundtrip.py:189-191` : `workspace_manager.create(self.folder); aria = character_manager.create("Aria"); character_manager.select(aria.character_id)`) **créent et sélectionnent explicitement leur propre Character** immédiatement après `workspace_manager.create()`, **sans jamais référencer le Character auto-créé** — leur comportement est **strictement identique**, que l'auto-création ait eu lieu ou non (elle produirait aujourd'hui un second Character auto-créé, silencieusement ignoré, jamais sélectionné). **Aucune adaptation requise pour ces sites.**
- **Exactement 4 tests** (`test_workspace_created_with_empty_characters_creates_exactly_one`, `test_auto_created_character_name_matches_workspace_name`, `test_auto_created_character_is_automatically_selected`, `test_auto_created_character_is_persisted_in_project_json`, tous dans `test_character_roundtrip.py:776-799`) **testent directement l'auto-création elle-même**, en appelant `workspace_manager.create()` seul et en vérifiant l'état de `character_manager` ensuite. **Ces 4 tests doivent être adaptés pour appeler la nouvelle primitive d'orchestration** (§9) à la place de `workspace_manager.create()` seul.
- **7 tests supplémentaires, trouvés par cette investigation, suivant un patron distinct** (`test_character_roundtrip.py` ×3 : lignes 829, 1144, 1189 ; `test_dataset_roundtrip.py:1649` ; `test_lora_roundtrip.py:2088` ; `test_prompt_roundtrip.py:1644` ; `test_training_roundtrip.py:1016`) : chacun appelle `workspace_manager.create(self.folder)`, récupère `character_manager.characters[0]` (le Character auto-créé), **le supprime délibérément** (`character_manager.delete(principal.character_id)`), puis vérifie le comportement d'un Workspace à 0 Character (avertissement UI, §2). **Ces 7 tests reposent sur l'auto-création pour obtenir un Character à supprimer** — avec la nouvelle architecture, `workspace_manager.create()` seul ne produira plus aucun Character : ces 7 tests peuvent être **simplifiés** (suppression des deux lignes `principal = ...`/`character_manager.delete(...)`, `workspace_manager.create()` seul suffit désormais à produire directement l'état à 0 Character qu'ils testent) plutôt que migrés vers l'orchestrateur.
- Aucune autre occurrence de dépendance à l'auto-création trouvée par cette investigation dans les 12 fichiers.

**Conclusion révisée, décisive** : **11 tests précisément identifiés** nécessitent une modification (4 adaptations vers l'orchestrateur + 7 simplifications), sur les ~390 sites initialement redoutés — un périmètre de test borné, vérifié fichier par fichier, pas une estimation. **Un test Qt réel supplémentaire** (`tests/integration/test_main_window_new_project.py`, `MainWindowNewProjectTest`, `MainWindow()` réel non mocké) doit également être adapté : `test_accept_calls_create_exactly_once_with_dialog_target_path` et `test_workspace_manager_error_is_shown_via_message_box` patchent aujourd'hui directement `self.window.workspace_manager.create` et vérifient qu'il est appelé avec `dialog.target_path` — une fois le call site de `MainWindow.new_project()` changé pour appeler la nouvelle primitive d'orchestration, ces deux tests doivent patcher/asserter contre celle-ci à la place ([test_main_window_new_project.py:89-112](../../tests/integration/test_main_window_new_project.py)).

### 5.2 Options d'architecture (rappel, tranché en §9)

- **A — MainWindow uniquement** : insuffisant seul (§5.1 : casserait les 4+7 tests `_wire()`-style qui n'utilisent jamais `MainWindow`).
- **B — Primitive dédiée au-dessus des deux Managers** : **retenue** (§9) — aucune dépendance circulaire, migration bornée à 11+1 tests précisément identifiés (§5.1), aucun changement pour les ~380 autres sites d'appel.
- **C — Création directe dans `WorkspaceManager`** : écartée (import circulaire pour publier `CHARACTER_CREATED`/`CHARACTER_SELECTED`, ou duplication de constantes en violation de CLAUDE.md ; casse `test_auto_created_character_is_automatically_selected`, `active_character_id` ne serait jamais assigné).

## 6. Investigation 5 — Transaction / Rollback et timing des événements : décision finale

### 6.1 Décision architecturale sur le timing de `WORKSPACE_CREATED`

**L'Option consistant à publier `WORKSPACE_CREATED` avant que l'invariant Character soit satisfait est rejetée**, conformément à la décision explicite de l'architecte : `WORKSPACE_CREATED` ne doit jamais annoncer publiquement comme créé un objet qui pourrait ensuite être rollbacké.

**Séquence cible retenue** :
```
matérialisation/persistance interne du Workspace (sans publication)
→ création/persistance du Character principal
→ sélection du Character
→ SEULEMENT ALORS : publication de WORKSPACE_CREATED
→ observers
→ retour succès au caller
```

**Modification minimale identifiée pour la rendre possible, sans dupliquer la logique de `WorkspaceManager.create()`** (option 1 de la liste proposée par l'architecte — méthode interne matérialisant sans publier, combinée à l'option 3 — primitive dédiée de finalisation) :

```python
# src/managers/workspace_manager.py

def create_without_publishing(self, folder) -> Workspace:
    folder = Path(folder)
    workspace = Workspace(name=folder.name, root=folder)
    try:
        WorkspaceStorage.create_directories(folder)
        WorkspaceStorage.save(folder, workspace.to_dict())
    except WorkspaceStorageError as exc:
        raise WorkspaceManagerError(str(exc)) from exc
    self.current_workspace = workspace
    return workspace

def publish_created(self) -> None:
    self._publish(WORKSPACE_CREATED)

def create(self, folder) -> Workspace:
    workspace = self.create_without_publishing(folder)
    self.publish_created()
    return workspace
```

**`create()` reste, pour tout appelant existant, strictement et intégralement identique** : même signature, mêmes exceptions, même valeur de retour, et — vu depuis l'extérieur de la méthode — exactement le même instant relatif de publication de `WORKSPACE_CREATED` par rapport à son propre appel. **Aucun des ~380 sites d'appel non concernés par §5.1 n'a besoin d'être modifié.** La logique de matérialisation n'existe qu'à un seul endroit (`create_without_publishing()`), jamais dupliquée — `create()` n'en est plus qu'une composition triviale.

### 6.2 Réponse à la question WORKSPACE_SAVED

**Est-il cohérent de publier `WORKSPACE_SAVED` pour un Workspace qui n'a pas encore été annoncé via `WORKSPACE_CREATED` ? Oui, vérifié subscriber par subscriber, pas supposé :**

Les 10 subscribers de `WORKSPACE_SAVED` ([main_window.py:332-364](../../src/ui/main_window.py), vérifiés un par un) sont **exclusivement** des méthodes `update_*` de Page (`dashboard_page.update_project`, `images_page.update_images`, `datasets_page.update_datasets`, `models_page.update_models`, `workflows_page.update_workflows`, `characters_page.update_characters`, `lora_page.update_loras`, `settings_page.update_settings`, `training_page.update_trainings`, `prompts_page.update_prompts`) — **jamais** un `_on_context_changed`/`reset_for_context_change` (ces derniers ne sont abonnés qu'à `WORKSPACE_CREATED/OPENED/CLOSED`, pas à `SAVED`, par choix délibéré de Mission 078/105 déjà en place). Chaque méthode `update_*` relit l'état **courant** (`workspace_manager.current_workspace`/`character_manager.characters`, déjà entièrement posés à ce stade — §4.1 : `workspace.characters.append()` précède toujours le `save()` qui publie `WORKSPACE_SAVED`) — aucune ne conserve ni ne consulte un indicateur « `WORKSPACE_CREATED` a-t-il déjà eu lieu ». **Aucune de ces 10 méthodes ne peut donc observer un état incohérent ou halfway-built.**

**Ce n'est pas une situation nouvelle** : aujourd'hui déjà, ce même `WORKSPACE_SAVED` (et `CHARACTER_CREATED`/`CHARACTER_SELECTED`) est publié de façon imbriquée **pendant** le fan-out de `WORKSPACE_CREATED` lui-même (avant que les subscribers restants de `WORKSPACE_CREATED` n'aient été atteints) — le changement introduit par cette mission ne fait que déplacer ce même schéma d'imbrication **avant le début** du fan-out de `WORKSPACE_CREATED`, plutôt qu'en plein milieu. Aucune nouvelle catégorie d'incohérence n'est introduite.

### 6.3 Ordre événementiel cible complet, vérifié pour chaque événement

| Événement | Moment actuel | Moment cible | Subscribers | Doit-il être différé ? |
|---|---|---|---|---|
| `WORKSPACE_SAVED` (2e save, imbriqué) | Pendant le fan-out de `WORKSPACE_CREATED` | **Avant** `WORKSPACE_CREATED` | 10 Pages, `update_*` uniquement | Non — vérifié §6.2, aucun état incohérent observable |
| `CHARACTER_CREATED` | Pendant le fan-out de `WORKSPACE_CREATED` | **Avant** `WORKSPACE_CREATED` | 5 Pages, `update_*` uniquement (`characters_page`/`datasets_page`/`lora_page`/`training_page`/`prompts_page`) | Non — mêmes méthodes `update_*`, même raisonnement §6.2 |
| `CHARACTER_SELECTED` | Pendant le fan-out de `WORKSPACE_CREATED` | **Avant** `WORKSPACE_CREATED` | `characters_page.reset_for_context_change`, `datasets_page.update_datasets`, `lora_page.reset_for_context_change`, `training_page.reset_for_context_change` ([main_window.py:398-406](../../src/ui/main_window.py)) — vérifiés un par un, tous relisent l'état courant, aucun ne suppose `WORKSPACE_CREATED` déjà publié | Non |
| `WORKSPACE_CREATED` | Dernière instruction de `WorkspaceManager.create()`, avant même la création du Character | **Après** que le Character soit créé ET sélectionné | ~15-17 subscribers (cartographie MISSION_136.md §2, inchangée) : tous, sans exception, observent désormais un Workspace **et** un Character déjà pleinement en place — propriété plus forte qu'aujourd'hui, où seuls les subscribers enregistrés après `_ensure_default_character` (position 2) en bénéficient | — (c'est la publication qui est déplacée, pas différée : elle a désormais lieu au bon moment dès le départ) |

**Ordre final sur succès, exact** : `WORKSPACE_SAVED → CHARACTER_CREATED → CHARACTER_SELECTED → WORKSPACE_CREATED`. **Justifié depuis les callbacks réels**, pas repris sans vérification : chacune des 19 méthodes subscriber concernées (10 + 5 + 4, avec chevauchement) a été relue individuellement ; aucune ne conditionne son comportement à un événement antérieur précis, chacune relit l'état Domain/Manager courant. **Aucun refactor disproportionné n'a été nécessaire** pour atteindre cet ordre sans fuite d'état intermédiaire incohérent.

### 6.4 Rollback — spécification exacte

**État à capturer avant création** : `previous_workspace = workspace_manager.current_workspace` (seule référence Manager pertinente — `CharacterManager.active_character_id` n'a pas besoin d'être capturé séparément : il est réinitialisé à `None` par le mécanisme déjà existant `_on_workspace_changed` sur `WORKSPACE_CREATED`, et puisque `WORKSPACE_CREATED` n'est jamais publié en cas d'échec, `active_character_id` reste simplement à sa valeur d'avant l'opération — aucune action supplémentaire requise).

**Après échec de la création du Character** (`character_manager.ensure_default_character()` lève `WorkspaceManagerError`, §9) :

- **Filesystem** : `WorkspaceStorage.delete_folder(folder)` — supprime le dossier complet, `project.json` inclus. **Aucun fichier Character séparé n'existe jamais** (§3) — cette seule suppression couvre tout, sans qu'aucun artefact distinct n'ait besoin d'être traqué individuellement.
- **Domain** : le Character lui-même est déjà retiré de `workspace.characters` par le rollback propre de `CharacterManager.create()` (`workspace.characters.remove(character)`, [character_manager.py:148](../../src/managers/character_manager.py)) avant même que l'orchestrateur n'intervienne — rien à refaire à ce niveau.
- **Manager state** : `workspace_manager.current_workspace = previous_workspace`, **exécuté inconditionnellement, que la suppression du dossier réussisse ou non** — même idiome que `DatasetManager.delete()` (« the Domain rollback must always run, regardless of whether the filesystem rollback below succeeds »).
- **Events** : aucun `WORKSPACE_CREATED`/`CHARACTER_CREATED`/`CHARACTER_SELECTED` n'est jamais publié pour un Workspace qui échoue avant que l'invariant soit satisfait, **par construction** (§6.1 : la publication de `WORKSPACE_CREATED` est la toute dernière étape de l'orchestrateur, atteinte uniquement si tout ce qui précède a réussi). **`WORKSPACE_SAVED` (imbriqué dans `character_manager.create()`) peut avoir été publié avant que l'échec ne survienne** (ex. si c'est `select()` qui échouait, hypothèse non réaliste aujourd'hui — §4.2) — dans un tel cas hypothétique, ce `WORKSPACE_SAVED` aurait déjà annoncé un état qui sera ensuite rollbacké. **Ce résidu théorique n'est pas traité par cette mission** : `select()` n'a aucun chemin d'échec réel aujourd'hui (§4.2), donc ce scénario est **structurellement inatteignable**, pas activement empêché — à documenter comme limite connue plutôt que faussement présenté comme couvert.
- **Caller** : reçoit `WorkspaceManagerError`, cohérent avec le type déjà catché par `MainWindow.new_project()` — aucune nouvelle exception introduite.

### 6.5 Échec du cleanup (rollback filesystem lui-même en échec)

Réutilise exactement le pattern déjà établi par Mission 134 (`TrainingManager._materialize_concept()`) et `LoRALibraryManager.import_lora()` : **l'erreur primaire n'est jamais remplacée**, l'échec de cleanup est **ajouté** au message, jamais substitué :

```python
except WorkspaceManagerError as exc:
    workspace_manager.current_workspace = previous_workspace   # toujours exécuté
    try:
        WorkspaceStorage.delete_folder(folder)
    except WorkspaceStorageError:
        raise WorkspaceManagerError(
            f"{exc} Additionally, the incomplete project folder could not be "
            f"cleaned up and remains on disk at {folder}. Manual recovery "
            f"required: delete {folder} yourself once the underlying issue is "
            f"resolved."
        ) from exc
    raise WorkspaceManagerError(str(exc)) from exc
```
**Type final et propriétaire** : `WorkspaceManagerError` dans les deux branches — aucune nouvelle classe d'exception. `from exc` dans les deux cas (jamais `from` l'exception de cleanup elle-même) : la cause chaînée (`__cause__`) reste toujours l'échec **primaire** (création du Character), exactement l'idiome de Mission 134 où l'exception de cleanup elle-même n'est jamais nommée dans le message (seule sa survenue est signalée), pour ne jamais laisser croire que le nettoyage a remplacé la vraie cause.

### 6.6 `WorkspaceStorage.delete_folder()` — contrat clarifié avant réutilisation

Vérifié directement ([workspace_storage.py:333-361](../../src/infrastructure/storage/workspace_storage.py)) :
- **Accepte-t-il le dossier racine du Workspace ?** Oui, techniquement — c'est une suppression récursive générique (`shutil.rmtree`), sans distinction entre un sous-dossier et une racine.
- **Vérifie-t-il des limites de sécurité ?** **Non** — aucune vérification de périmètre/sandboxing. **Risque réel à documenter** : l'orchestrateur doit passer exactement et uniquement le `folder` reçu en paramètre (jamais une valeur relue depuis un état Manager potentiellement muté entre-temps), pour exclure toute confusion de chemin. Ses 6 usages existants dans le dépôt ciblent tous des sous-dossiers étroits (dossier de corbeille, dossier de concept, dossier d'entrée LoRA) — **c'est la première fois que cette primitive serait appliquée à une racine de Workspace entière**, un fait à assumer explicitement, pas à masquer.
- **Que fait-il si le dossier est absent ?** No-op (`if not path.exists(): return`) — traité comme déjà supprimé, jamais une erreur.
- **Que fait-il sur suppression partielle ?** `shutil.rmtree()` peut échouer en cours de route (fichier verrouillé, permission) ; ceci surface comme une unique `WorkspaceStorageError`, sans bookkeeping partiel — cohérent avec un usage best-effort.
- **Quelles exceptions ?** `WorkspaceStorageError` sur tout `OSError`.
- **Existe-t-il une meilleure primitive déjà utilisée pour supprimer un Workspace entier ?** **Non** — recherche exhaustive de `delete_folder(` dans `src/` : tous les appels existants ciblent des sous-dossiers, aucun ne supprime jamais une racine de Workspace. Il n'existe aucune primitive dédiée à cet usage précis dans le dépôt aujourd'hui.
- **Conformité à la contrainte « pas de `shutil.rmtree(ignore_errors=True)` »** : déjà satisfaite — `delete_folder()` ne masque jamais un `OSError` réel (contrairement à `ignore_errors=True`), il le propage systématiquement en `WorkspaceStorageError`. Le seul comportement « silencieux » qu'elle a est sur un dossier **déjà absent**, ce qui est un no-op légitime, pas une erreur masquée.

**Décision** : réutiliser `WorkspaceStorage.delete_folder()` telle quelle, sans nouvelle primitive, en documentant explicitement (commentaire dans l'orchestrateur) qu'il s'agit d'un usage élargi par rapport à son historique de sous-dossiers, et en garantissant que seul le `folder` exact reçu en paramètre lui est transmis.

## 7. Investigation 6 — UI (inchangée depuis la première itération, revérifiée)

`CharactersPage` a ses trois contrôles (`new_button`/`delete_button`/`list_widget`) explicitement masqués (`setVisible(False)`) depuis Mission 026 — aucun chemin UI réel ne permet de créer ou supprimer un Character. `_load_identity_fields(None)` vide la fiche sans crash. Le seul appelant réel de `WorkspaceManager.create()` (`MainWindow.new_project()`, [main_window.py:614-619](../../src/ui/main_window.py)) catche déjà `WorkspaceManagerError` avec `QMessageBox.critical(self, "Erreur", str(exc))` et ignore déjà la valeur de retour — **la nouvelle primitive d'orchestration, levant ce même type d'exception, s'intègre sans aucune modification de ce bloc `except`, seul le call site change**. Aucune nouvelle UX nécessaire, confirmé.

## 8. Investigation 7 — `Workspace.from_dict()` (inchangée depuis la première itération, revérifiée)

Comparaison complète : `models`/`workflows` ont `if isinstance(x, dict)`, `settings` a son propre garde équivalent, **`characters` n'en a aucun** — oubli manifeste, confirmé. **Contrat exact à implémenter** :
```python
characters = [None, "x", 42, valid_dict]
```
→ `None`, `"x"` (itéré caractère par caractère si la clé elle-même n'était pas une liste — non applicable ici puisque c'est un élément de liste, pas la liste elle-même), `42` : tous rejetés par `isinstance(c, dict)` ; `valid_dict` : chargé normalement via `Character.from_dict(valid_dict)`. **Résultat attendu : exactement 1 Character chargé, aucune exception.** Le même angle mort que `models`/`workflows` sur la collection elle-même non-liste (`(data.get("characters") or [])` ne protège que contre les valeurs *falsy*) est **déjà accepté uniformément** pour ces deux collections voisines — la garder ainsi pour `characters`, sans aller plus loin, évite une dérive vers une migration générale non demandée. Aucun changement nécessaire dans `Character.from_dict()` (déjà défensif sur ses propres sous-collections) ni dans `principal_character`/les index.

## 9. Architecture cible — décision finale, unique

**Propriétaire réel de l'invariant** : une primitive d'orchestration dédiée, au-dessus des deux Managers, ni l'un ni l'autre ne dépendant de l'autre au-delà de l'existant.

### 9.1 API cible

**`WorkspaceManager` (modifié)** — trois méthodes publiques au lieu d'une, aucune duplication de logique :
```python
class WorkspaceManager:
    def create_without_publishing(self, folder) -> Workspace: ...   # nouveau — matérialisation seule
    def publish_created(self) -> None: ...                            # nouveau — publication seule
    def create(self, folder) -> Workspace: ...                        # inchangé pour tout appelant existant
```
`create()` reste l'API **historique**, pour tout code qui n'a jamais eu et n'a toujours pas besoin de la garantie Character (les ~380 sites de test non concernés par §5.1, et tout futur usage Workspace-only). Elle n'est ni dépréciée ni rendue privée — la rendre privée casserait ces mêmes ~380 sites sans aucun bénéfice.

**`CharacterManager` (modifié)** — `_ensure_default_character` perd son statut privé et son abonnement EventBus, devient un point d'entrée explicite :
```python
class CharacterManager:
    def __init__(self, workspace_manager, event_bus=None):
        ...
        if self._event_bus is not None:
            self._event_bus.subscribe(WORKSPACE_CREATED, self._on_workspace_changed)
            self._event_bus.subscribe(WORKSPACE_OPENED, self._on_workspace_changed)
            self._event_bus.subscribe(WORKSPACE_CLOSED, self._on_workspace_changed)
            # ligne retirée : subscribe(WORKSPACE_CREATED, self._ensure_default_character)

    def ensure_default_character(self) -> None:   # renommée, publique, appelée explicitement
        workspace = self._workspace_manager.current_workspace
        if workspace is None or workspace.characters:
            return
        character = self.create(workspace.name)
        self.select(character.character_id)
```
**Aucun mécanisme concurrent ne subsiste** : c'est la même méthode, avec la même garde interne, simplement invoquée explicitement par l'orchestrateur plutôt qu'implicitement par EventBus — pas de duplication de la logique de garde dans l'orchestrateur.

### 9.2 Orchestrateur exact

- **Nom** : `create_workspace_with_default_character`.
- **Module** : nouveau fichier `src/managers/workspace_lifecycle.py` — une fonction libre, pas une classe : aucun état n'est conservé entre deux appels, et une fonction signale sans ambiguïté qu'il s'agit d'une opération précise, pas d'un troisième Manager générique.
- **Dépendances injectées** : `workspace_manager: WorkspaceManager`, `character_manager: CharacterManager`, `folder` — paramètres de la fonction, aucun état stocké, aucun constructeur.
- **Type de retour** : `Workspace` — identique au contrat historique de `WorkspaceManager.create()`.
- **Type(s) d'erreur** : `WorkspaceManagerError` exclusivement — aucune nouvelle classe.
- **Propriétaire du rollback** : l'orchestrateur lui-même (il observe l'état des deux Managers et décide).
- **Propriétaire de la publication finale** : `WorkspaceManager`, via sa propre méthode `publish_created()` — l'orchestrateur décide **quand**, jamais **quoi** ni **par qui** ; la règle « chaque Manager publie ses propres événements » reste intacte.

```python
# src/managers/workspace_lifecycle.py

def create_workspace_with_default_character(workspace_manager, character_manager, folder) -> Workspace:
    previous_workspace = workspace_manager.current_workspace

    workspace = workspace_manager.create_without_publishing(folder)

    try:
        character_manager.ensure_default_character()
    except WorkspaceManagerError as exc:
        workspace_manager.current_workspace = previous_workspace
        try:
            WorkspaceStorage.delete_folder(folder)
        except WorkspaceStorageError:
            raise WorkspaceManagerError(
                f"{exc} Additionally, the incomplete project folder could not be "
                f"cleaned up and remains on disk at {folder}. Manual recovery "
                f"required: delete {folder} yourself once the underlying issue is "
                f"resolved."
            ) from exc
        raise WorkspaceManagerError(str(exc)) from exc

    workspace_manager.publish_created()
    return workspace
```

### 9.3 Wiring et usage par MainWindow

**Aucun changement de wiring dans `MainWindow.__init__`** : les deux Managers sont déjà construits et déjà reliés au même `EventBus` pour d'autres raisons. Le seul changement de wiring est la suppression de la ligne d'abonnement interne à `CharacterManager.__init__()` (§9.1) — invisible depuis `MainWindow`.

**`MainWindow.new_project()`** ([main_window.py:614](../../src/ui/main_window.py)) :
```python
try:
    create_workspace_with_default_character(self.workspace_manager, self.character_manager, dialog.target_path)
except WorkspaceManagerError as exc:
    QMessageBox.critical(self, "Erreur", str(exc))
    return
self.statusBar().showMessage("Projet créé")
```
Seul le call site change ; le bloc `except` reste identique. `MainWindow` importe la fonction directement (`from src.managers.workspace_lifecycle import create_workspace_with_default_character`).

## 10. Séquences d'échec — exhaustives

| # | Scénario | État disque | État Domain | État Managers | Événements déjà publiés | Exception caller |
|---|---|---|---|---|---|---|
| 1 | Échec du 1er save Workspace (`create_without_publishing()`) | Dossier potentiellement créé par `create_directories()`, `project.json` absent — **comportement pré-existant, non traité par M137** (hors périmètre : hardening de l'atomicité interne de `create_without_publishing()` elle-même) | `workspace` jamais assigné à `current_workspace` | Inchangé (jamais écrasé, l'assignation a lieu après le bloc try/except) | Aucun | `WorkspaceManagerError` (comportement déjà actuel, inchangé) |
| 2/3 | Échec de création du Character (le « second save » **est** l'appel `WorkspaceManager.save()` fait par `CharacterManager.create()` — même événement, pas deux scénarios distincts) | Dossier + `project.json` (`characters: []`) existent avant rollback ; supprimés entièrement après rollback réussi | `workspace.characters` déjà remis à `[]` par `CharacterManager.create()` lui-même, avant même l'action de l'orchestrateur | `current_workspace` restauré à `previous_workspace` par l'orchestrateur | Aucun (`WORKSPACE_SAVED`/`CHARACTER_CREATED` n'ont jamais été publiés puisque c'est justement ce `save()` qui échoue avant de publier quoi que ce soit) | `WorkspaceManagerError` (celle de `character_manager.create()`, propagée par l'orchestrateur) |
| 4 | Échec de `select()` | **Structurellement inatteignable aujourd'hui** (§4.2) — aucun chemin d'échec réel identifié. Si un futur changement le rendait possible : le Character existerait déjà en Domain et sur disque (`WORKSPACE_SAVED`/`CHARACTER_CREATED` déjà publiés) ; le même rollback (suppression totale du dossier) resterait correct et suffisant puisqu'aucun artefact n'existe hors du dossier Workspace (§3) — mais ce cas laisserait, de façon théorique, `WORKSPACE_SAVED`/`CHARACTER_CREATED` avoir été publiés pour un Workspace ensuite rollbacké (limite documentée §6.4, non activement empêchée) | — | — | — | — |
| 5 | Échec du rollback filesystem (`WorkspaceStorage.delete_folder()` échoue à son tour) | Dossier orphelin résiduel, documenté explicitement dans le message d'erreur | `workspace.characters` déjà `[]` (rollback Domain déjà fait, indépendant du filesystem) | `current_workspace` **quand même restauré** — le rollback mémoire ne dépend jamais du succès du rollback filesystem | Aucun | `WorkspaceManagerError`, message augmenté (§6.5), `from exc` (cause = l'échec **primaire**, jamais remplacée) |

## 11. Plan de tests futur

Doit couvrir, sans nombre fixé artificiellement :

1. Création normale via l'orchestrateur : invariant satisfait, `character_manager.characters` contient exactement 1 Character, sélectionné, nommé d'après le Workspace.
2. **Ordre exact des événements sur succès** : `WORKSPACE_SAVED → CHARACTER_CREATED → CHARACTER_SELECTED → WORKSPACE_CREATED` — test dédié capturant l'ordre réel de réception via des subscribers instrumentés, pas seulement l'état final.
3. Échec contrôlé de `character_manager.ensure_default_character()` (mock de `WorkspaceManager.save()` échouant spécifiquement sur le second appel) → `WorkspaceManagerError` visible au caller.
4. **Absence d'événements de succès prématurés** : sur l'échec du point 3, vérifier explicitement que `WORKSPACE_CREATED` n'a **jamais** été publié (assertion sur l'absence, pas seulement sur l'état final) — verrou explicite contre une future régression qui publierait trop tôt.
5. État Domain après échec : `workspace.characters == []`.
6. État filesystem après échec : dossier absent (rollback réussi).
7. État Manager après échec : `current_workspace` restauré à sa valeur précédente (tester à la fois le cas « aucun Workspace n'était ouvert avant » et « un autre Workspace était déjà ouvert avant »).
8. Absence de Workspace zombie : vérification directe du filesystem après l'exception.
9. Échec du rollback filesystem lui-même : message d'erreur mentionne à la fois la cause primaire et l'échec de cleanup, `current_workspace` tout de même restauré, `__cause__` pointe vers l'exception primaire (pas celle du cleanup).
10. Compatibilité avec M136 : la garantie ne dépend d'aucune exception `EventBus` — test explicite prouvant qu'elle fonctionne même si un `EventBus` swallow toute exception de subscriber (cohérent avec la politique déjà en place, jamais contourné).
11. `Workspace.from_dict()` avec `characters = [None, "x", 42, valid_dict]` → exactement 1 Character chargé, aucune exception (§8).
12. Non-régression des `project.json` valides existants.
13. Non-régression de `WorkspaceManager.create()` elle-même (les ~380 sites non concernés) : un test minimal confirmant que `create()` seule, sans orchestrateur, ne crée toujours aucun Character et publie toujours `WORKSPACE_CREATED` immédiatement — verrouille explicitement que son contrat historique n'a pas changé.
14. Les 4 tests d'auto-création de `test_character_roundtrip.py` (§5.1) adaptés pour appeler l'orchestrateur.
15. Les 7 tests « no character » (§5.1) simplifiés (suppression du couple create-puis-delete, devenu inutile).
16. `MainWindowNewProjectTest` (§5.1) adapté pour patcher/asserter contre l'orchestrateur plutôt que `workspace_manager.create` directement — conserve les mêmes garanties (annulation du dialogue → orchestrateur jamais appelé ; acceptation → orchestrateur appelé avec `dialog.target_path` ; erreur → `QMessageBox.critical` affichée).

## 12. Smoke

**Non nécessaire, décidé sur preuve, pas par défaut** : `tests/integration/test_main_window_new_project.py::MainWindowNewProjectTest` utilise un **`MainWindow()` réel** (non mocké), avec uniquement le dialogue modal `NewProjectDialog` patché — ce test couvre déjà exactement le chemin `MainWindow → orchestration → Workspace/Character → état visible` demandé. **À condition que ce fichier soit effectivement adapté** (§5.1, §11 point 16) pour continuer à exercer le nouveau call site, aucun smoke manuel n'est nécessaire. Si l'implémentation révèle une conséquence Qt non couverte par ce test réel (ex. un rendu visuel du rollback non observable automatiquement), cela devra être signalé avant clôture plutôt que supposé couvert.

## 13. Risques résiduels

- Le scénario théorique d'un échec de `select()` (§4.2, §10 ligne 4) laisserait `WORKSPACE_SAVED`/`CHARACTER_CREATED` publiés pour un Workspace ensuite rollbacké — documenté comme limite connue, non activement empêché, car structurellement inatteignable avec le code actuel.
- `WorkspaceStorage.delete_folder()` appliquée pour la première fois à une racine de Workspace entière plutôt qu'à un sous-dossier (§6.6) — aucune vérification de périmètre dans cette primitive ; l'orchestrateur doit strictement passer le `folder` reçu en paramètre, jamais une valeur relue d'un état potentiellement muté.
- 11 tests + 1 fichier de test Qt réel à adapter (§5.1) — périmètre borné et vérifié, mais toute omission romprait silencieusement la couverture de l'invariant ou casserait un test existant.
- Aucune garde ne protège aujourd'hui `CharacterManager.delete()` contre la suppression du dernier Character (§2) — confirmé comme déjà le cas, **non corrigé par M137** (hors périmètre : ce n'est pas un chemin de création, c'est un chemin de suppression, dont le comportement à 0-Character est déjà testé et volontaire, cf. §2).

## 14. Dettes restantes, non traitées par cette mission

- `TrainingManager._recover_stale_jobs` (même famille que `_ensure_default_character`, impact moindre) — non touché.
- Le message d'avertissement de `DatasetsPage`/`LoRAPage`/`PromptsPage`/`TrainingPage` sur un Workspace à 0 Character renvoie vers une action UI aujourd'hui impossible (« créez-en un depuis Characters », bouton masqué, §2/§7) — incohérence préexistante, non introduite ni corrigée par M137, hors périmètre (réactivation de l'UI multi-Character explicitement exclue).
- Absence de garde sur `CharacterManager.delete()` contre la suppression du dernier Character — confirmé, non corrigé (§13).
- Backup/reprise OneTrainer, Models/Workflows découplés d'Inference — candidats distincts, hors périmètre.

## 15. Exclusions explicites

- EventBus M136 (contrat déjà validé, non rouvert — aucune transaction, buffering, queue ou suspension globale introduite dans `EventBus` lui-même ; toute la logique de séquencement reste locale à `workspace_lifecycle.py`).
- Training resume, Models/Workflows, Central LoRA Library, Forge, ComfyUI.
- Réactivation de l'UI multi-Character (boutons/liste restent masqués).
- Nouveau système transactionnel générique (réutilisation de l'idiome cleanup-then-raise existant uniquement, local à cette seule orchestration).
- Migration massive de `project.json`.
- Refonte de `Character`, support multi-Character produit.
- Nouvelle UX complexe (l'infrastructure d'erreur existante de `MainWindow.new_project()` suffit).
- Correction de l'absence de garde sur `CharacterManager.delete()` (§13/§14).

## 17. Résultats réels

**Architecture implémentée** : exactement celle décrite en §6/§9, sans écart. `WorkspaceManager.create_without_publishing()`/`publish_created()` ajoutées, `create()` réécrite comme composition triviale des deux — strictement inchangée pour tout appelant existant. `CharacterManager._ensure_default_character()` renommée `ensure_default_character()` (publique, plus de paramètre `payload`), son abonnement à `WORKSPACE_CREATED` retiré. Nouveau module `src/managers/workspace_lifecycle.py` avec `create_workspace_with_default_character()`, conforme au design (rollback best-effort, `previous_workspace` restauré inconditionnellement, idiome cleanup-then-raise, `WorkspaceManagerError` uniquement). `MainWindow.new_project()` appelle exclusivement cette primitive.

**Correction découverte pendant l'implémentation, non anticipée par le design** : retirer `WORKSPACE_CREATED` de l'abonnement de `CharacterManager._on_workspace_changed` (qui remettait `active_character_id` à `None`) s'est révélé nécessaire — dans la séquence cible, ce reset se serait exécuté *après* la sélection du Character par `ensure_default_character()`, l'annulant silencieusement. La ligne d'abonnement à `WORKSPACE_CREATED` a donc été retirée de `_on_workspace_changed` (conservée pour `WORKSPACE_OPENED`/`WORKSPACE_CLOSED`, où ce reset reste correct et nécessaire) — documenté explicitement dans `character_manager.py`. Aucun autre écart architectural découvert.

**Ampleur réelle des tests — classification finale après migration complète** (corrige l'estimation initiale de §5.1, elle-même déjà une révision de l'estimation ~281 initiale) :

- **Catégorie A (contrat produit complet, migrés vers l'orchestrateur)** : 47 sites, répartis sur `test_character_roundtrip.py` (10), `test_dataset_roundtrip.py` (1), `test_lora_roundtrip.py` (1), `test_prompt_roundtrip.py` (1 + 27 dans `PromptsPageSortTest`), `test_training_roundtrip.py` (6), `test_workspace_roundtrip.py` (2), `test_datasets_page.py` (4), `test_dashboard_page.py` (1), `test_main_window_close_event.py` (1), `test_main_window_new_project.py` (1 call site + 3 tests de patch/ordre adaptés).
- **Catégorie B (0-Character volontaire, simplifiés — suppression du couple create-puis-delete)** : 4 sites (`test_character_roundtrip.py` ×2, `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py` — un par fichier « no_character »).
- **Catégorie C1/C2 (Character explicite déjà présent, non touchés ou simplifiés pour retirer une dépendance inutile à l'auto-création)** : ~4 sites simplifiés (`CharacterManagerUpdateRollbackTest`, `CharacterManagerCreateRollbackTest`, `test_renaming_via_update_never_changes_workspace_name`, `CharactersPageIdentityPersistenceFailureTest._prepare()`) — remplacent une dépendance implicite à l'auto-création par une création explicite, sans changer le comportement testé.
- **Non concernés, vérifiés puis laissés inchangés** : la quasi-totalité des ~281 sites restants dans les 5 fichiers initialement redoutés, plus `test_image_roundtrip.py`, `test_images_page.py`, `test_inference_page.py` (CharacterManager mocké ou Character créé explicitement partout) — confirmé fichier par fichier, jamais supposé.
- **2 fichiers supplémentaires découverts en cours d'implémentation, non anticipés par §5.1** : `test_datasets_page.py` (4 classes entières, `dataset_manager.create()` dépendant implicitement de l'auto-création sans jamais mentionner littéralement `principal_character`) et `test_dashboard_page.py` (1 test patchant directement `workspace_manager.create` sur un vrai `MainWindow`, même patron que `test_main_window_new_project.py`) — trouvés uniquement parce que la suite complète a été exécutée avant clôture, confirmant la valeur de cette étape.

**Helpers de test ajoutés** : un seul, `LoRAPageDeleteButtonStateTest._wire()` (test_lora_roundtrip.py) élargi pour retourner aussi `character_manager` (absent du tuple avant cette mission, nécessaire pour appeler l'orchestrateur dans les tests de ce groupe). Aucun helper générique/framework de test introduit.

**Justification des assertions adaptées** : chaque assertion modifiée correspond à un changement de contrat explicitement voulu par M137, jamais à une correction pour faire passer un test — en particulier : les comptages de subscribers `WORKSPACE_CREATED` (7→5, 8→6 selon les fichiers) reflètent le retrait réel d'une subscription (`ensure_default_character` n'est plus jamais souscrite à cet événement) ; les assertions de patch (`workspace_manager.create` → `create_workspace_with_default_character`) reflètent le changement réel du call site de `MainWindow.new_project()`.

**Nouveaux tests ajoutés** : **+17 tests nets** (2755 → 2772). `tests/integration/test_workspace_lifecycle.py` (nouveau fichier, 14 tests) : succès (Workspace + Character créés/sélectionnés, ordre exact des événements, subscribers de `WORKSPACE_CREATED` voient déjà l'invariant satisfait, `WorkspaceManager.create()` historique toujours fonctionnel sans CharacterManager) et échec (erreur `WorkspaceManagerError`, `WORKSPACE_CREATED` jamais publié, filesystem nettoyé, Domain sans Character résiduel, `current_workspace` restauré — cas `None` et cas Workspace précédent réel testés séparément —, absence de zombie, cause primaire préservée en cas d'échec du cleanup, garantie indépendante de toute exception EventBus). `tests/integration/test_workspace_roundtrip.py` (+3 tests, nouvelle classe `WorkspaceFromDictCharactersDefensiveParsingTest`) : `characters = [None, "x", 42, valid_dict]` → 1 Character chargé sans exception, clé `characters` absente → liste vide, non-régression d'un `project.json` valide.

**Résultats exacts** :
- Fichier ciblé `test_workspace_lifecycle.py` : **14/14**.
- Tests ciblés Workspace/Character/lifecycle/MainWindow/Domain parsing, exécutés ensemble (`test_character_roundtrip.py`, `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py`, `test_workspace_roundtrip.py`, `test_workspace_lifecycle.py`, `test_main_window_new_project.py`, `test_main_window_close_event.py`, `test_model_roundtrip.py`, `test_workflow_roundtrip.py`, `test_settings_roundtrip.py`) : **1331/1331**.
- `test_datasets_page.py` + `test_dashboard_page.py` (découverts via la suite complète) : **75/75**.
- Une première exécution de la suite complète a révélé les 2 fichiers non anticipés ci-dessus (67 erreurs + 1 échec, tous dans ces 2 fichiers, tous corrigés) — rapportée ici sans la masquer, conformément à la discipline de transparence du projet.
- Une seconde exécution complète, après correction, a obtenu **2772 collectés, 2772 passés, 0 échoué, exit 0 (309.470s)**. Aucun flake historique (`ForgeLifecycleManagerRealProcessTest`) ne s'est manifesté sur ce run.
- `git diff --check` : clean (avertissements CRLF/LF bénins uniquement).
- Fichiers réellement modifiés : exactement les 5 fichiers de production autorisés (`src/managers/workspace_manager.py`, `src/managers/character_manager.py`, `src/managers/workspace_lifecycle.py` nouveau, `src/domain/workspace.py`, `src/ui/main_window.py`) + 13 fichiers de tests existants adaptés + 1 nouveau fichier de test + `docs/missions/MISSION_137.md`.

**Smoke** : non nécessaire, confirmé — `test_main_window_new_project.py::MainWindowNewProjectTest` utilise un `MainWindow()` réel (non mocké, seul `NewProjectDialog` patché) et couvre effectivement `MainWindow.new_project() → create_workspace_with_default_character() → Workspace + Character → état visible`, avec ses assertions de call site et d'erreur adaptées et vertes.

**Dettes découvertes, non traitées, documentées séparément** : aucune nouvelle depuis §13/§14 — le scénario théorique d'échec de `select()` et l'usage inédit de `WorkspaceStorage.delete_folder()` sur une racine restent tels que documentés, aucun problème supplémentaire rencontré à l'implémentation.

**Écarts par rapport au design validé** : un seul, documenté ci-dessus (retrait de `WORKSPACE_CREATED` de `_on_workspace_changed`) — conséquence directe et nécessaire de la séquence déjà validée, pas un changement d'architecture.

## 16. Autorisation

**Implémentée et testée.** Le point resté ouvert lors de la première itération (timing de `WORKSPACE_CREATED`) est résolu explicitement (§6, §9) : `WorkspaceManager.create()` scindée sans duplication (`create_without_publishing()` + `publish_created()`, `create()` inchangée pour tout appelant existant), orchestrateur `create_workspace_with_default_character()` publiant `WORKSPACE_CREATED` uniquement après satisfaction complète de l'invariant, ordre événementiel cible vérifié callback par callback (§6.3) et confirmé par test (§17), rollback spécifié exactement (§6.4-§6.6) et implémenté à l'identique, ampleur réelle des tests affectés entièrement migrée et vérifiée (§17, deux fichiers non anticipés découverts et corrigés via la suite complète). Full suite **2772/2772/0 échoué**. Validée par l'architecte et par validation externe à chaque étape (rédaction initiale, complément d'investigation, écart de périmètre, implémentation). Clôture Git (commit/tag/Release) en attente de validation externe finale avant de procéder.
