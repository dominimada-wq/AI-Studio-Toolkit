# Mission 136 — EventBus Fault-Isolation Policy

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture (commit/tag/Release) en attente de validation externe.** `EventBus.publish()` (`src/core/event_bus.py`) n'isolait auparavant aucun subscriber d'un autre : une exception levée par l'un interrompait immédiatement la livraison à tous les subscribers suivants pour ce même événement, et remontait telle quelle jusqu'à l'appelant (toujours une méthode Manager, toujours appelée après que la mutation Domain et l'écriture disque ont déjà réussi — vérifié directement dans `WorkspaceManager`/`CharacterManager`/`LoRALibraryManager`). Une première itération de cette mission avait recommandé une politique "continue-then-aggregate-raise" ; une investigation complémentaire, portant spécifiquement sur la classification réelle des subscribers et le comportement observable par les *callers*, a **infirmé ce choix**. Preuve concrète et décisive trouvée dans le code : `CharactersPage`'s bouton « Créer un personnage » (`characters_page.py:178-186`) affiche, sur erreur, le message *"Le personnage n'a pas été créé"* — or `CharacterManager.create()` ne fait un rollback (`workspace.characters.remove(character)`) que sur l'échec de sa propre persistance (`save()`), jamais sur un échec de la publication `CHARACTER_CREATED` qui suit, non protégée par aucun `try/except`. Toute politique qui relève une exception après un succès métier déjà acté crée un risque réel de **faux échec** et de **retry après persistance réussie** (ici : création d'un second personnage en double, `create()` n'ayant aucune déduplication). La politique implémentée est **B — continue + journalisation, sans jamais relever** : chaque subscriber d'un événement est toujours tenté, chaque échec est journalisé (traceback complet, jamais le payload) via l'infrastructure `logging` déjà existante, et `publish()` retourne toujours normalement — un succès métier réel ne peut plus jamais apparaître comme un échec au caller. `EventBusPublishError` n'a jamais été créée. `ImagesPage` et `_ensure_default_character()` n'ont pas été modifiés (faux positif infirmé / dette hors périmètre explicitement documentée). **+9 tests nets** (2746 → 2755). Full suite **2755/2755/0 échoué**, `git diff --check` clean, exactement les 3 fichiers autorisés. Aucun smoke requis.

## 1. Contexte

Fait suite à l'audit global post-Mission 135, qui avait réévalué `EventBus.publish()` sans présumer d'une direction et trouvé une preuve concrète (mais, comme le §6 ci-dessous le montre après investigation plus poussée, en réalité non atteignable telle quelle) suggérant que l'absence d'isolation de panne n'était plus purement préventive. Cette mission a pour seul objectif d'établir, **avant toute implémentation**, le contrat architectural exact que `EventBus.publish()` doit respecter quand un subscriber lève une exception — en le déduisant de l'architecture réelle, des call sites, des responsabilités des subscribers, des conventions d'erreur existantes, de l'UX Qt et des tests, jamais d'une préférence abstraite.

**Formulation correcte du problème (aucune sur-affirmation)** :
- `EventBus.publish()` n'isole actuellement pas les subscribers.
- Une exception déterministe d'un subscriber interrompt réellement le fan-out (démontré directement dans le code, §2 et §5).
- Un chemin de reproduction concret impliquant `ImagesPage.update_images()` avait été proposé par l'audit précédent ; l'investigation dédiée de cette mission (§6) montre qu'il **n'est pas atteignable** aujourd'hui via le chemin de chargement normal, un `project.json` corrompu ou un format hérité — un filtre de chargement (`Image.list_from_data()`) neutralise déjà ce cas précis avant qu'il n'atteigne l'UI.
- Aucune preuve n'établit qu'un utilisateur ait déjà rencontré une exception de subscriber en production.
- Le risque architectural reste néanmoins réel et structurel, indépendamment de la correction ou non d'un subscriber précis : l'absence de toute isolation signifie qu'**un** subscriber quelconque, aujourd'hui ou dans une future mission, peut silencieusement priver tous les subscribers suivants de leur exécution — une propriété qu'`EventBus` devrait garantir par construction, pas par la correction ponctuelle de chaque callback.

## 2. Investigation 1 — Cartographie EventBus

`EventBus.publish()` (`src/core/event_bus.py:44-48`) :
```python
def publish(self, event_name: str, payload=None) -> None:
    payload = self._freeze(payload)
    for callback in list(self._subscribers[event_name]):
        callback(payload)
```
`list(self._subscribers[event_name])` capture un instantané de la liste au moment de l'appel (une désinscription pendant l'itération ne perturbe pas la boucle courante — propriété à préserver). Aucun `try/except` : la première exception interrompt la boucle et se propage intégralement à l'appelant de `publish()`.

### WORKSPACE_CREATED / OPENED / SAVED / CLOSED / RENAMED

Constantes : `src/managers/workspace_manager.py:15-19`. Publisher unique : `WorkspaceManager._publish()` (`:727-738`), appelé en toute dernière instruction de `create()`/`open()`/`save()`/`rename()`/`close()`, toujours **après** que la mutation Domain et l'écriture disque (le cas échéant) aient déjà réussi (détail complet en §5).

Subscribers, dans l'ordre d'enregistrement réel (Managers construits avant les Pages dans `main_window.py`) :

| # | Subscriber | Événements | Nature | Classe (§4) |
|---|---|---|---|---|
| 1 | `CharacterManager._on_workspace_changed` | CREATED/OPENED/CLOSED | Reset d'état interne (`active_character_id = None`), assignation mémoire pure | B |
| 2 | `CharacterManager._ensure_default_character` | CREATED seul | **Cross-Manager avec publication imbriquée** — voir §3 et §4.5 | A' (cas particulier, voir §4.5) |
| 3 | `DatasetManager`/`LoRAManager`/`PromptManager`/`ModelManager`/`WorkflowManager` `_on_context_changed` (nom exact par module) | CREATED/OPENED/CLOSED | Reset d'état interne (`active_*_id = None`), même patron, assignation mémoire pure — vérifié directement dans chaque module | B |
| 4 | `TrainingManager._on_context_changed` | CREATED/OPENED/CLOSED | Reset d'état interne, assignation mémoire pure | B |
| 5 | `TrainingManager._recover_stale_jobs` | OPENED seul | Nettoyage best-effort de jobs orphelins (Mission 100 §12), appelle `update_job_state()` (persistance possible) — vérifié directement : purement corrective, la Workspace est déjà ouverte avec succès avant ce callback, aucune donnée n'est perdue si ce nettoyage échoue (juste différé au prochain open réussi) | D |
| 6 | `dashboard_page.update_project`, `images_page.update_images`, `datasets_page.update_datasets`, `models_page.update_models`, `workflows_page.update_workflows` | les 5 événements | Rafraîchissement Qt (`blockSignals`/`clear`/reconstruction) | C |
| 7 | `characters_page.update_characters`, `lora_page.update_loras`, `settings_page.update_settings`, `training_page.update_trainings` | SAVED/RENAMED seuls | Rafraîchissement Qt, préservant un brouillon dirty (`if dirty: return`) | C |
| 8 | mêmes 4 pages, `reset_for_context_change` | CREATED/OPENED/CLOSED seuls | Rafraîchissement Qt, abandon inconditionnel d'un brouillon | C |
| 9 | `inference_page.reset_for_workspace_change` | CREATED/OPENED/CLOSED/RENAMED | Invalide un résultat de génération pendante lié à l'ancien Workspace | C |
| 10 | `inference_page.reset_for_context_change`, `prompts_page.reset_for_context_change` | CREATED/OPENED/CLOSED | Rafraîchissement Qt | C |

Jusqu'à **~15-17 subscribers** pour un seul `publish(WORKSPACE_CREATED, ...)`.

### CHARACTER_CREATED / SELECTED / DELETED

Constantes : `src/managers/character_manager.py:14-16`. Publisher : `CharacterManager._publish()` (`:285-290`), appelé après `save()`/mutation en mémoire réussis. Subscribers CREATED : 5 pages (`characters_page`/`datasets_page`/`lora_page`/`training_page`/`prompts_page`, toutes en `update_*`). Subscribers SELECTED+DELETED : mêmes 5 pages en `reset_for_context_change`/`update_datasets`. Toutes de nature rafraîchissement Qt avec garde dirty-state où applicable.

### LORA_LIBRARY_IMPORTED / DELETED / UPDATED

Constantes : `src/managers/lora_library_manager.py:18-20`. Publisher : `LoRALibraryManager._publish()` (`:855`), après `_save()` réussi. **2 subscribers** : `lora_page.update_central_library` puis `inference_page.refresh_lora_selector` — seul autre fan-out réel à 2+ subscribers hors WORKSPACE_*/CHARACTER_*.

### Événements à subscriber unique (pas de risque de fan-out)

`DATASET_*`/`LORA_*`/`PROMPT_*`/`MODEL_*`/`WORKFLOW_*`/`TRAINING_*` (CREATED/SELECTED/DELETED, un seul subscriber chacun : la Page correspondante), `APPLICATION_SETTINGS_UPDATED` (un seul subscriber, `settings_page.update_application_settings`). `TRAINING_JOB_CREATED`/`TRAINING_JOB_STATE_CHANGED` : publisher confirmé (`TrainingManager._publish_job()`, `:1190`), **aucun subscriber trouvé** par recherche exhaustive dans `main_window.py` — probablement 0 subscriber actuellement (non vérifié davantage, hors impact fault-isolation puisqu'il n'y a rien à isoler).

### Confirmation absence de test

`tests/` ne contient qu'un seul sous-dossier, `tests/integration/` (pas de `tests/unit/`). Aucun fichier `test_event_bus*.py` n'existe. Les 16 fichiers instanciant `EventBus(...)` le font uniquement pour câbler un Manager/Page sous test (patron `_wire()`), jamais pour tester le contrat propre de `publish()`/`subscribe()`.

## 3. Investigation 2 — Ordre des subscribers : dépendance réelle découverte

L'ordre Managers → Pages n'est **pas** qu'un artefact accidentel de l'ordre de construction : une dépendance fonctionnelle réelle existe, **découverte et vérifiée directement dans le code** :

```python
# character_manager.py:52-74
def _ensure_default_character(self, payload) -> None:
    workspace = self._workspace_manager.current_workspace
    if workspace is None or workspace.characters:
        return
    character = self.create(workspace.name)   # publie WORKSPACE_SAVED puis CHARACTER_CREATED, IMBRIQUÉ
    self.select(character.character_id)        # publie CHARACTER_SELECTED, IMBRIQUÉ
```
Ce subscriber de `WORKSPACE_CREATED` (enregistré en position 2, juste après `_on_workspace_changed`) déclenche, **de façon synchrone et imbriquée dans la boucle `publish(WORKSPACE_CREATED, ...)` elle-même**, deux publications supplémentaires (`WORKSPACE_SAVED` puis `CHARACTER_CREATED`, puis `CHARACTER_SELECTED`) — le tout avant qu'aucune Page n'ait réagi à `WORKSPACE_CREATED`. Les Pages qui s'abonnent à `WORKSPACE_CREATED` (position 6+) s'exécutent donc en supposant implicitement qu'un Character principal existe déjà et est sélectionné — une garantie qui tient aujourd'hui uniquement parce que l'ordre d'enregistrement place ce subscriber Manager avant les Pages.

**Conclusion** : cette dépendance d'ordre est réelle et doit être **préservée**, pas supprimée ni transformée en contrat public générique. La politique recommandée (§7) ne modifie jamais l'ordre d'enregistrement ni d'invocation — elle change uniquement le comportement en cas d'exception, ce qui laisse cette dépendance intacte par construction. Aucune autre dépendance d'ordre équivalente n'a été identifiée ailleurs dans la cartographie du §2.

## 4. Investigation complémentaire — Classification des subscribers, caractère transactionnel, choix final

Cette section remplace intégralement l'analyse A/B/C de la première itération de cette mission, jugée insuffisante par la validation externe : elle ne classait pas réellement les subscribers par comportement, et son choix (« continue-then-aggregate-raise ») n'avait pas été confronté sérieusement à l'hypothèse log-and-continue.

### 4.1 Classification réelle des subscribers (comportement inspecté, pas seulement le nom)

Voir la colonne « Classe » du tableau §2. Quatre classes trouvées :

- **B — Synchronisation d'état Manager/Domain** (`_on_workspace_changed`/`_on_context_changed`, 7 occurrences vérifiées directement dans `character_manager.py`/`dataset_manager.py`/`lora_manager.py`/`prompt_manager.py`/`model_manager.py`/`workflow_manager.py`/`training_manager.py`) : chacune est une **simple assignation mémoire** (`self.active_*_id = None`), sans aucun accès disque, Domain ou Qt — ne peut réalistement jamais lever.
- **C — Rafraîchissement UI dérivé** (toutes les méthodes `update_*`/`reset_for_context_change`/`reset_for_workspace_change`/`refresh_lora_selector` des Pages) : reconstructions de widgets Qt, jamais nécessaires à la validité de l'opération métier qui a déclenché l'événement — une Page qui échoue à se rafraîchir laisse simplement son affichage obsolète jusqu'au prochain événement, sans aucune conséquence sur les données.
- **D — Effet secondaire secondaire/non critique** (`TrainingManager._recover_stale_jobs`) : nettoyage best-effort de jobs orphelins, vérifié directement — la Workspace est déjà ouverte avec succès avant ce callback ; un échec ne perd aucune donnée, seulement reporté au prochain open réussi (idempotent).
- **A' — Cas particulier `CharacterManager._ensure_default_character`** : seul subscriber de toute la cartographie qui accomplit une étape produit *voulue* par une mission (Mission 026 : un Workspace fraîchement créé doit toujours avoir un Character principal utilisable, invariant explicitement documenté depuis Mission 036 — voir §4.5). Analysé séparément ci-dessous car c'est le seul candidat plausible à la catégorie A (« nécessaire à la cohérence métier »).

**Aucun subscriber trouvé qui soit réellement de catégorie A pure** (un échec dont la seule réponse cohérente serait d'annuler l'opération métier déjà validée) — `_ensure_default_character` est le seul cas à examiner en détail, et sa conclusion (§4.5) n'aboutit pas à ce classement.

### 4.2 EventBus : mécanisme transactionnel ou d'observation post-commit ? — Réponse explicite

**EventBus est un mécanisme d'observation post-commit, pas une partie de la transaction métier.** Ceci est établi directement par le code, pas par convention :

- `publish()`/`_publish()` est vérifié comme étant la **toute dernière instruction** de chaque méthode auditée (`WorkspaceManager.create/open/save/rename/close`, `CharacterManager.create/delete`, `LoRALibraryManager.import_lora/update/set_thumbnail/delete`), toujours après que la mutation Domain et l'écriture disque ont déjà réussi.
- **Preuve directe et décisive** : `CharacterManager.create()` (`character_manager.py:134-153`) :
  ```python
  workspace.characters.append(character)
  try:
      self._workspace_manager.save()
  except WorkspaceManagerError:
      workspace.characters.remove(character)   # rollback — mais seulement ici
      raise
  self._publish(CHARACTER_CREATED, character)  # AUCUN try/except autour de ceci
  return character
  ```
  Le rollback existe **uniquement** pour l'échec de la persistance elle-même. Aucun rollback n'existe, n'a jamais existé, et n'est appelé nulle part pour un échec de la publication qui suit — la transaction (mutation + persistance) est déjà considérée close et irréversible au moment où `publish()` s'exécute. C'est la preuve que le code lui-même traite déjà la notification comme hors de la transaction.
- Aucun Manager ne compense, ne rejoue, ni n'annule quoi que ce soit en réaction à un échec de subscriber — il n'existe et n'a jamais existé de mécanisme de ce type dans le dépôt.

### 4.3 Analyse des callers — risque de « false failure » et de « retry après persistance réussie » (démontré, pas hypothétique)

Recherche des callers de `WorkspaceManager.create/open/save/rename`, `CharacterManager.create/update/delete/select`, `LoRALibraryManager` : tous suivent le même patron — un `try/except <ManagerError typé>` autour de l'appel Manager, avec un `QMessageBox.critical`/`statusBar().showMessage` selon le résultat. Aucun ne fait de retry automatique. Exemples vérifiés directement :

- `main_window.py:614-619` (`new_project`), `:667-670` (`open_project`), `:686-692` (`save_project`) : `except WorkspaceManagerError as exc: QMessageBox.critical(...)`, sinon `self.statusBar().showMessage("Projet créé"/"sauvegardé")`.
- **`characters_page.py:178-186`** (bouton « Créer un personnage »), preuve concrète et décisive :
  ```python
  try:
      character = self.character_manager.create(name.strip())
  except WorkspaceManagerError as exc:
      QMessageBox.critical(
          self, "Erreur",
          f"Impossible d'enregistrer le nouveau personnage dans le projet : {exc}\n"
          "Le personnage n'a pas été créé."
      )
  ```

Aujourd'hui, une exception de subscriber (non typée `WorkspaceManagerError`) **n'est pas capturée par ce bloc** — elle se propage plus loin, non interceptée (aucun `sys.excepthook` personnalisé n'existe dans le dépôt, confirmé). Le caller ne voit ni ce message d'erreur précis, ni le message de succès (`return character`/`statusBar().showMessage` jamais atteint) : c'est un **« faux silence »**, pas un faux message, dans l'état actuel du code.

**Le risque concret que révèle cette investigation n'est pas dans le comportement actuel isolé, mais dans toute politique qui ferait remonter une exception de subscriber comme si elle appartenait au même type d'échec que `WorkspaceManagerError`.** Si ce bloc `except` était un jour élargi (dérive de maintenance plausible : un futur développeur, face à un rapport de plantage sur cette ligne, élargit naturellement `except WorkspaceManagerError` en `except Exception` pour « couvrir le cas ») — sous une politique **continue-then-aggregate-raise**, ce message afficherait alors **« Le personnage n'a pas été créé »** alors que le personnage a réellement été créé et persisté avec succès juste avant. L'utilisateur, voyant ce message, cliquerait vraisemblablement à nouveau sur « Créer un personnage » — et `CharacterManager.create()` n'a **aucune déduplication par nom** (conforme à `CLAUDE.md` : « `create()` ne valide jamais le nom ») : un second personnage seraît créé, avec le même nom, en double. **C'est un risque de retry-after-successful-persistence démontré par la structure réelle du code, pas une spéculation.**

Sous une politique **log-and-continue (sans jamais relever)**, ce risque disparaît structurellement : `character_manager.create()` ne peut plus jamais lever à cause d'un subscriber, donc ce message d'erreur reste **toujours vrai** quelle que soit l'évolution future de ce bloc `except`, et le message de succès (`return character`, `statusBar().showMessage`) est **toujours atteint** quand l'opération a réellement réussi — ce qui n'est garanti par aucune des deux autres options.

### 4.4 Option B (continue + log, sans re-raise) réexaminée sérieusement

Contrat :
```python
for callback in list(self._subscribers[event_name]):
    try:
        callback(payload)
    except Exception:
        logger.exception("Subscriber %s raised while handling event %r", ..., event_name)
# publish() retourne normalement, toujours, après avoir tenté tous les subscribers
```

Le risque théorique associé (« certaines erreurs Manager-subscriber importantes pourraient être masquées ») **ne se vérifie pas** une fois la classification du §4.1 appliquée : aucun subscriber de catégorie B/C/D ne peut, par construction, laisser le système dans un état pire que « pas rafraîchi » ou « pas nettoyé, retenté plus tard » — jamais une perte ou une corruption de donnée persistée. Seul `_ensure_default_character` (A') mérite un examen séparé (§4.5).

### 4.5 `CharacterManager._ensure_default_character()` — analyse détaillée

```python
def _ensure_default_character(self, payload) -> None:
    workspace = self._workspace_manager.current_workspace
    if workspace is None or workspace.characters:
        return
    character = self.create(workspace.name)   # publie WORKSPACE_SAVED + CHARACTER_CREATED, imbriqué
    self.select(character.character_id)        # publie CHARACTER_SELECTED, imbriqué
```

**Invariant en jeu** : `docs/PROJECT_CONTEXT.md` documente explicitement depuis Mission 036 qu'« un Workspace ouvert possède toujours un Character principal ». Un échec ici pourrait donc laisser un Workspace fraîchement créé sans Character — une violation réelle de cet invariant énoncé.

**Mais la question posée (A vs B) appelle une réponse plus fine que « bloquant » ou « pas bloquant »** :
- **Aucune politique de `publish()` ne peut compenser cet échec** : que `WorkspaceManager.create()` (l'appelant du `publish(WORKSPACE_CREATED, ...)` externe) reçoive une exception ou non, il ne peut de toute façon **rien annuler** — le dossier Workspace et son `project.json` existent déjà sur disque, un rollback filesystem n'est jamais tenté nulle part dans ce dépôt pour ce type d'opération (cohérent avec la politique déjà établie ailleurs, ex. Mission 134, où l'absence de garantie transactionnelle du filesystem est explicitement assumée). Faire lever `publish()` ne fait donc que transformer un « Workspace créé, sans Character, sans signal » en « Workspace créé, sans Character, avec une exception non exploitée par personne » (aucun code n'agit sur cette exception aujourd'hui pour la corriger).
- **La conséquence utilisateur d'un Workspace sans Character n'est pas une corruption silencieuse de données** : `CharactersPage` affichera simplement une liste vide, avec le bouton « Créer un personnage » toujours disponible — l'utilisateur peut recréer manuellement un Character en un clic. C'est une dégradation UX visible et auto-réparable, pas un état incohérent invisible.
- **Sous log-and-continue, cet échec reste visible** : `_logger.error(...)` capture l'événement, le callback fautif et le traceback complet — une trace au moins aussi exploitable pour le diagnostic qu'une exception aujourd'hui non interceptée et potentiellement invisible (pas de console attachée dans un build packagé).

**Conclusion** : `_ensure_default_character()` **ne justifie pas** de faire lever `publish()` au niveau global — aucune politique de `publish()` ne peut de toute façon réparer cet échec, et le coût (risque de faux échec démontré en §4.3, sur TOUS les événements et TOUS les callers, pour le bénéfice de UN SEUL subscriber dont l'échec est de toute façon irrécupérable par ce canal) est disproportionné.

**Recommandation distincte, hors périmètre d'implémentation de M136 (aucun refactor fait maintenant, conformément à l'instruction)** : ce subscriber accomplit en réalité une étape métier de `WorkspaceManager.create()` (garantir l'invariant Mission 036), pas une simple notification — il serait architecturalement plus sain que `WorkspaceManager.create()` (ou un appel Manager-à-Manager explicite) invoque directement cette logique, avec sa propre décision de gestion d'erreur choisie consciemment, plutôt que de la faire dépendre du contrat générique d'`EventBus`. Signalé ici comme observation pour une mission future, jamais implémenté dans M136.

### 4.6 Comparaison finale et politique retenue

| | A — fail-fast (statu quo) | B — continue + log, sans relever | C — continue + agréger + relever |
|---|---|---|---|
| Tous les subscribers exécutés | Non | **Oui** | Oui |
| Risque de faux échec pour un succès métier réel | Oui (déjà aujourd'hui, non documenté) | **Non, structurellement impossible** | Oui, si un `except` est un jour élargi (§4.3) |
| Risque de retry → mutation dupliquée | Oui (latent) | **Non** | Oui (latent, même mécanisme) |
| Diagnostic des échecs de subscriber | Aucun | **Oui (log complet)** | Oui (log + exception) |
| Compatible avec `_ensure_default_character` (§4.5) | Oui, mais sans bénéfice réel | **Oui** | Oui, mais sans bénéfice réel |
| Complexité ajoutée | Aucune (mais bug non corrigé) | **Minimale** | Nouvelle classe d'exception, nouveau contrat pour les callers |

**Politique finale recommandée : B — continue + log, sans jamais relever.** `EventBusPublishError` est **retirée** — elle n'apporte aucun bénéfice pour `_ensure_default_character` (le seul cas qui aurait pu la justifier), et introduit un risque démontré de faux échec/retry dupliqué pour tous les autres callers.

## 5. Investigation 4 — Frontière Manager/UI (vérifiée directement dans le code)

Pour chaque méthode auditée, `publish()`/`_publish()` est la toute dernière instruction, appelée strictement après succès de la mutation Domain et de la persistance — détail complet en §4.2/§4.3 ci-dessus (`WorkspaceManager.create/open/save/rename/close`, `CharacterManager.create/delete/select`, `LoRALibraryManager.import_lora/update/set_thumbnail/delete`).

**EventBus est entièrement synchrone** : aucun `QThread`/`Signal`/`QTimer.singleShot`/`threading` dans `event_bus.py` ou ses usages. `publish()` s'exécute toujours sur le même thread (le thread GUI Qt) que son appelant, dans le même call stack qu'un gestionnaire de clic de bouton.

## 6. Investigation 5 — ImagesPage : chemin de reproduction proposé, infirmé après investigation

`ImagesPage.update_images()` (`src/ui/pages/images_page.py:219,225,228`) indexe `image["file_path"]` sans `.get()`. L'audit précédent avait présenté ceci comme un chemin concret d'exception via un `project.json` corrompu ou hérité. **Investigation approfondie infirme ce chemin précis** :

- `Image.to_dict()` (`src/domain/image.py:20-27`) garantit toujours la clé `file_path` pour toute image créée normalement par l'application ; aucune méthode Manager (`WorkspaceManager.add_images()`) ne peut produire une entrée sans `file_path`.
- Un `project.json` corrompu ou au format hérité (Mission 011 : ancien format `list[str]` avant la migration vers `[{"image_id","file_path"}]`) est déjà filtré **au chargement**, dans `Image.list_from_data()` (`src/domain/image.py:42-67`) : une entrée n'est conservée que si `isinstance(image.file_path, str) and image.file_path` (dict) ou `isinstance(entry, str) and entry` (legacy str) — toute autre forme est silencieusement écartée, par conception documentée explicitement dans le docstring de cette méthode ("this is where validity is decided").
- Conséquence : au moment où `workspace.to_dict()` atteint `ImagesPage.update_images()`, chaque entrée possède déjà garantie un `file_path` non vide. **Le `KeyError` n'est pas atteignable par ce chemin aujourd'hui.**
- De plus, l'indexation directe (`image["file_path"]`, `model["file_path"]`, `workflow["file_path"]`) est la convention **dominante** dans `DatasetsPage`/`ModelsPage`/`WorkflowsPage` également (recherche `.get("file_path"` dans `src/ui/pages/*.py` : zéro résultat) — ce n'est pas une violation isolée d'`ImagesPage`, mais un choix cohérent avec l'architecture réelle : le filtrage défensif a lieu une fois, au chargement (couche Domain), pas redondamment à chaque point de contact UI.

**Décision** : `ImagesPage` **n'entre pas dans le périmètre de l'implémentation de M136**. Il n'y a rien de démontré à corriger dans ce fichier précis aujourd'hui ; y toucher serait une modification spéculative sans défaut constaté, contraire à la discipline de périmètre du projet. Le risque architectural qui motive M136 reste néanmoins entier et indépendant de ce cas précis : la garantie qu'un subscriber quelconque ne puisse pas priver silencieusement les suivants de leur exécution est une propriété qu'`EventBus` doit fournir par construction, pas une conséquence de la correction (bug par bug, mission par mission) de chaque callback existant.

## 7. Investigation 6 — Distinction de types de subscribers

La politique finale (§4.6) ne nécessite **aucune** distinction Manager-critique / UI-best-effort au niveau d'`EventBus` lui-même : tous les subscribers d'un événement sont toujours tentés intégralement, tous les échecs sont journalisés de façon identique, sans priorité ni catégorie. La seule distinction réelle trouvée (`_ensure_default_character`, catégorie A', §4.5) n'est pas traitée en généralisant une infrastructure de priorités dans `EventBus` — elle est traitée en observant que ce cas particulier appartient conceptuellement à la responsabilité du Manager, pas à celle du bus d'événements (§4.5, recommandation hors périmètre). Ceci satisfait la préférence explicite pour la solution la plus simple qui respecte le contrat — aucune metadata, aucun nouveau type d'événement, aucune infrastructure de priorité n'est introduite dans `EventBus`.

## 8. Investigation 7 — Threading / Qt

`EventBus` reste et doit rester purement synchrone. La politique finale ne change ni le thread d'exécution ni le caractère synchrone de la boucle : chaque callback continue de s'exécuter immédiatement, sur le thread appelant, dans l'ordre d'enregistrement inchangé — seule la réaction à une exception change (capturée et journalisée, boucle continue, `publish()` retourne normalement). Aucun dispatcher asynchrone, aucune queue, aucun `QTimer`.

## 9. Investigation 8 — Tests prévus (aucun test EventBus existant, confirmé)

Confirmé au moment de l'investigation : aucun `tests/**/test_event_bus*.py` n'existait. Emplacement retenu, réalisé (§15) : `tests/integration/test_event_bus.py` (seul sous-dossier de tests existant dans le dépôt ; nommage sans suffixe `_roundtrip` car ce n'est pas un test de roundtrip Domain, à l'image de `test_main_window_close_event.py`/`test_settings_page.py`).

Propriétés minimales à démontrer (mocks déterministes uniquement, callbacks factices — jamais un subscriber réel du projet comme véhicule de reproduction, cohérent avec le §6) :
1. Fan-out normal : N subscribers enregistrés, tous invoqués, dans l'ordre d'enregistrement, avec le même payload gelé.
2. Un subscriber intermédiaire lève une exception déterministe (`side_effect`) → les subscribers suivants sont **quand même invoqués** (propriété centrale que corrige cette mission, contrairement au comportement actuel).
3. **Test verrouillant la décision architecturale (§4.3), pas seulement le comportement interne de la boucle** : simuler le patron réel d'un Manager (mutation + persistance mockée réussies, puis `event_bus.publish(...)` en toute dernière instruction, comme `CharacterManager.create()`), avec un subscriber déterministe qui lève. Assertions : `publish()` ne lève **rien** ; le code immédiatement après l'appel `publish()` dans la méthode "Manager" s'exécute normalement ; sa valeur de retour est bien délivrée au caller — reproduisant explicitement la garantie qui protège `characters_page.py:178-186` d'un faux « Le personnage n'a pas été créé » (§4.3).
4. Deux subscribers échouent sur le même `publish()` → les deux échecs sont journalisés distinctement (via `self.assertLogs(level="ERROR")`), sans que l'un ne masque l'autre — `publish()` retourne toujours normalement.
5. `list(self._subscribers[event_name])` : la désinscription d'un subscriber pendant l'itération ne doit pas perturber le fan-out en cours (comportement déjà présent, non régressé).
6. `_freeze()` : le payload reste immuable (`MappingProxyType`) même avec le nouveau comportement — non régressé.
7. Cas de la réentrance (§3) : un test dédié reproduisant le patron `_ensure_default_character` (un subscriber qui publie lui-même un autre événement pendant son exécution) doit continuer à fonctionner sans changement d'ordre observable, y compris quand ce subscriber imbriqué lève (son échec ne doit pas empêcher les subscribers de l'événement externe de s'exécuter).
8. Le log ne contient jamais le payload complet : test dédié avec un payload contenant une valeur sentinelle, assertant son absence du message de log capturé.

## 10. Investigation 9 — Logging existant

Un système minimal existe déjà, **jamais utilisé hors Infrastructure** : `src/infrastructure/storage/workspace_storage.py`, `lora_library_storage.py`, `application_settings_storage.py` utilisent chacun `logging.getLogger(__name__)` (stdlib pur, aucune configuration centrale — pas de `basicConfig`/`addHandler`/`setLevel` nulle part dans `src/`, les loggers propagent vers le handler de secours par défaut de Python, stderr, niveau WARNING+). `src/core/logger.py` existe mais est un fichier **vide** depuis le commit initial — un stub mort, non concerné par cette mission.

**Recommandation inchangée** : réutiliser exactement le même idiome (`logging.getLogger(__name__)` directement dans `src/core/event_bus.py`, pas de nouveau système) — ce serait son premier usage en dehors de la couche Infrastructure, mais le même mécanisme stdlib, cohérent avec l'existant. `logger.exception(...)` (ou `logger.error(..., exc_info=True)`) niveau `ERROR`, appelé **à l'intérieur du bloc `except`** pour capturer le traceback complet automatiquement. Contenu du message : nom de l'événement, identifiant du callback fautif (`getattr(callback, "__qualname__", repr(callback))`) — jamais le payload complet (évite d'exposer des données de projet potentiellement sensibles sans nécessité).

## 11. Choix architectural final — Politique retenue

**Réponse explicite à la question centrale** : EventBus est un **mécanisme d'observation post-commit**, pas un mécanisme transactionnel — établi directement par le code (§4.2) : `publish()` est systématiquement la dernière instruction de chaque Manager audité, appelée après succès de la mutation et de la persistance, et aucun rollback n'existe ni n'a jamais existé pour un échec de subscriber (`CharacterManager.create()` ne fait de rollback que sur l'échec de sa propre `save()`, jamais sur l'échec de `_publish()` qui suit, non protégé).

**Politique recommandée : B — continue + log, sans jamais relever.**

```python
import logging

_logger = logging.getLogger(__name__)


def publish(self, event_name: str, payload=None) -> None:
    payload = self._freeze(payload)

    for callback in list(self._subscribers[event_name]):
        try:
            callback(payload)
        except Exception:
            _logger.exception(
                "Subscriber %s raised while handling event %r",
                getattr(callback, "__qualname__", repr(callback)),
                event_name,
            )
    # Aucune exception n'est jamais relevée ici : chaque subscriber a été
    # tenté, chaque échec a été journalisé, et l'appelant — dont la
    # mutation/persistance a nécessairement déjà réussi avant cet appel,
    # EventBus étant un mécanisme d'observation post-commit et non
    # transactionnel — ne doit jamais voir son opération métier réussie
    # se transformer en échec apparent à cause d'un observateur.
```

`EventBusPublishError` **n'existe plus** dans ce design : elle n'apportait aucun bénéfice pour le seul cas qui aurait pu la justifier (`_ensure_default_character`, §4.5 — aucune politique de `publish()` ne peut de toute façon compenser son échec), et introduisait un risque démontré de faux échec/retry dupliqué pour tous les autres callers (§4.3).

**Justification** (déduite de l'investigation, pas d'une préférence abstraite) :
- Corrige le défaut concret et vérifié : plus aucun subscriber n'est privé de son exécution à cause d'un échec antérieur pour le même événement (§2).
- **Élimine** (et non pas seulement « ne dégrade pas ») le risque de faux échec pour une opération métier réellement réussie — propriété plus forte que celle offerte par une politique qui relève, démontrée concrètement sur `characters_page.py` (§4.3).
- Préserve exactement l'ordre d'enregistrement/invocation actuel, donc la dépendance réelle découverte au §3 (réentrance `_ensure_default_character`) continue de fonctionner sans changement de comportement observable.
- Réutilise l'infrastructure `logging` déjà présente dans le dépôt, sans introduire de second système (§10).
- Reste strictement synchrone, sans threading ni dispatcher asynchrone (§8).
- Ne nécessite aucune distinction de types de subscribers, aucune priorité, aucune metadata dans `EventBus` (§7).
- Le seul subscriber pour lequel un signal plus fort que le log pourrait sembler désirable (`_ensure_default_character`, §4.5) ne peut de toute façon pas être réparé par un mécanisme générique de `publish()` — sa solution, si elle est un jour jugée nécessaire, est un changement de responsabilité (Manager-à-Manager explicite), pas un contrat `EventBus` plus strict pour tous les autres subscribers.

Cette recommandation est soumise à validation externe **avant toute implémentation**.

## 12. Périmètre de l'implémentation (réalisé, voir §15 pour les résultats réels)

- `src/core/event_bus.py` — `publish()` modifié (try/except par subscriber, `logging.getLogger(__name__)` ajouté). **Aucune nouvelle classe d'exception.**
- `tests/integration/test_event_bus.py` (nouveau fichier).
- Éventuellement `docs/PROJECT_CONTEXT.md`/mission doc de clôture (régularisation standard).

**`src/ui/pages/images_page.py` est explicitement exclu** (§6 : aucun défaut démontré à corriger). **`character_manager.py`/`workspace_manager.py` (déplacement éventuel de `_ensure_default_character`, §4.5) sont explicitement exclus de cette implémentation** — signalés comme observation pour une mission future, jamais traités ici. Aucun autre fichier Manager/UI n'est concerné — la politique se limite au mécanisme central `EventBus`, sans modifier aucun publisher ni aucun subscriber existant.

## 13. Exclusions explicites

- Pas d'EventBus asynchrone, pas de queue d'événements, pas de replay/historique.
- Pas de priorités complexes, pas de typed event framework, pas de changement du format de payload.
- Pas de refonte de `subscribe()`/`unsubscribe()`.
- Pas de refonte des Managers ni de `MainWindow` — en particulier, **aucun déplacement de `_ensure_default_character()` n'est fait dans cette mission** (§4.5 : observation pour une mission future uniquement).
- Pas d'EventBus inter-processus, pas de système de télémétrie.
- Pas de modification d'`ImagesPage` (§6 : rien à corriger, non démontré).
- Training resume, Model/Workflow integration, Central LoRA Library, Forge/ComfyUI : hors sujet, non concernés par cette mission.
- Aucun changement de l'ordre d'enregistrement/invocation actuel des subscribers.
- Aucune exception publique nouvelle (`EventBusPublishError` retirée du design).

## 15. Résultats réels

**Implémentation** : exactement le design retenu en §11 — `publish()` capture désormais `Exception` (jamais `BaseException`) individuellement autour de chaque appel `callback(payload)`, journalise via `_logger.exception(...)` (nouveau `_logger = logging.getLogger(__name__)`, même idiome stdlib déjà utilisé en Infrastructure), puis continue la boucle sans jamais relever — `publish()` retourne toujours normalement (`None` implicite), aucune exception ne remonte jamais au caller. `_freeze(payload)`, le snapshot `list(self._subscribers[event_name])` et l'ordre d'enregistrement/invocation sont strictement inchangés (aucune ligne touchée en dehors du corps de `publish()` et de l'ajout du logger/helper). Identification du callback via une fonction privée `_describe_callback()` : `getattr(callback, "__qualname__", None) or repr(callback)`, elle-même protégée par un `try/except Exception` interne (retour `"<unrepresentable callback>"`) — une construction de message de log ne peut donc jamais elle-même faire échouer le dispatcher. `EventBusPublishError` n'a jamais été créée. Aucun fichier autre que `src/core/event_bus.py` n'a été modifié : `ImagesPage`, `CharacterManager`, `WorkspaceManager`, `MainWindow`, `_ensure_default_character()` sont tous strictement inchangés.

**Comportement vérifié par les tests** (`tests/integration/test_event_bus.py`, 9 tests, classe `EventBusFaultIsolationTest`, isolée — aucun Qt/Manager instancié, un `EventBus()` nu suffit à prouver le contrat) :
- Fan-out normal : tous les subscribers appelés une fois, dans l'ordre d'enregistrement (`test_all_subscribers_are_called_once_in_registration_order`).
- Échec intermédiaire : les subscribers suivants sont bien invoqués malgré l'échec du précédent, `publish()` retourne `None` normalement (`test_a_failing_intermediate_subscriber_does_not_block_the_others`).
- Journalisation : `event_name` et l'identité du callback fautif présents dans le message, `exc_info`/type d'exception conservé, le payload n'apparaît jamais dans la sortie journalisée (`test_failure_is_logged_with_event_name_callback_and_traceback_but_not_the_payload`).
- Échecs multiples : 2 échecs sur 4 subscribers → les 4 sont tentés, les 2 échecs sont journalisés distinctement (types d'exception différenciés), aucun re-raise (`test_multiple_failures_are_all_logged_and_all_subscribers_are_attempted`).
- Snapshot : un subscriber qui s'abonne lui-même à un nouvel événement pendant le fan-out courant ne voit ce nouvel abonné invoqué qu'au *prochain* `publish()`, jamais dans le fan-out en cours (`test_subscribing_during_fan_out_does_not_affect_the_current_publish`) — non-régression du `list(...)` existant.
- `_freeze()` : immuabilité du dict de premier niveau (`TypeError` sur assignation) et isolation de la liste imbriquée (deep copy) toutes deux non régressées (`test_freeze_still_makes_dict_payloads_read_only_and_isolated`).
- Réentrance : un `publish()` imbriqué déclenché par un subscriber (reproduisant le patron `_ensure_default_character` — `WORKSPACE_CREATED` → nested `WORKSPACE_SAVED`/`CHARACTER_CREATED` → retour → suite des subscribers `WORKSPACE_CREATED`) se termine correctement, dans l'ordre exact attendu, même quand le subscriber imbriqué échoue (`test_nested_publish_during_a_subscriber_completes_and_outer_fan_out_continues`).
- **Sémantique caller/post-commit verrouillée** : un harnais minimal reproduisant la forme réelle de tout publisher du dépôt (mutation + persistance simulées réussies, `publish()` en toute dernière instruction, puis retour du succès) prouve que ce succès est toujours délivré au caller même quand un subscriber échoue — verrou explicite contre une future réintroduction d'aggregate+raise (`test_a_successful_operation_is_never_reported_as_failed_because_a_subscriber_raised`).
- Robustesse de l'identification : un callback sans `__qualname__` (objet callable) retombe sur `repr()` sans jamais faire échouer le dispatcher (`test_describing_a_callback_without_a_qualname_falls_back_to_repr_without_crashing`).

**Résultats exacts** : fichier ciblé `test_event_bus.py` **9/9**. Suites indirectement critiques (`test_workspace_roundtrip.py`, `test_character_roundtrip.py`, `test_main_window_new_project.py`, `test_main_window_close_event.py`, `test_main_window_rename_project.py`, `test_main_window_prompts_to_inference.py`, `test_main_window_training_to_inference.py`) **299/299**, aucune régression. Full suite : première exécution **2755 collectés, 2754 passés, 1 échoué** (`ForgeLifecycleManagerRealProcessTest.test_stop_is_idempotent_on_running_owned` — flake historique déjà documenté, processus réel/timing, aucun rapport avec `EventBus`), reconfirmé **3/3 vert en isolation** ; seconde exécution complète indépendante **2755 collectés, 2755 passés, 0 échoué**, exit 0 (320.407s) — nombre exact conforme à l'attendu (2746 à la clôture M135 + 9 nets). `git diff --check` : clean. Scope : exactement les 3 fichiers autorisés (`src/core/event_bus.py`, `tests/integration/test_event_bus.py`, `docs/missions/MISSION_136.md`).

**Smoke** : confirmé non requis — mécanisme purement synchrone, Qt-free, comportement entièrement déterministe et couvert par tests automatisés ; aucune conséquence Qt non testable automatiquement n'a été révélée par l'implémentation.

**Dettes découvertes, non traitées, documentées séparément** : `_ensure_default_character()` (`CharacterManager`) accomplit en réalité une étape métier (garantir l'invariant Mission 036 : un Workspace créé possède toujours un Character principal) déguisée en simple subscriber `EventBus` — non corrigée dans cette mission, recommandation explicite pour une mission future de la faire porter par un appel Manager-à-Manager direct plutôt que par le contrat générique d'`EventBus` (§4.5, §6/§7 exclusions). `ImagesPage.update_images()`'s indexation directe (`image["file_path"]`) reste inchangée — confirmée non défectueuse (§6), aucune dette réelle associée.

**Écarts par rapport au contrat validé** : aucun.

## 14. Autorisation

**Implémentée et testée.** Cartographie complète établie et classée par comportement réel (§2, §4.1), caractère post-commit d'EventBus établi explicitement et par preuve directe dans le code (§4.2), risque de faux échec/retry dupliqué démontré concrètement sur un caller réel (§4.3, `characters_page.py`), l'option log-and-continue réexaminée sérieusement et retenue (§4.4, §4.6), le cas `_ensure_default_character` analysé en détail sans conclure à la nécessité de faire lever `publish()` (§4.5), chemin de reproduction ImagesPage initialement proposé **infirmé** après investigation approfondie (§6), design implémenté sans `EventBusPublishError` (§11), résultats réels conformes en tout point au contrat validé (§15). Validée par l'architecte et par validation externe à chaque étape (rédaction initiale, investigation complémentaire, implémentation). Clôture Git (commit/tag/Release) en attente de validation externe finale avant de procéder.
