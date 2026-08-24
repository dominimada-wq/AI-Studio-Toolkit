# Mission 052 — Post-Creation Rename for Model, Workflow and LoRA

> **STATUT : IMPLÉMENTATION TERMINÉE, EN ATTENTE DE COMMIT.** Contrat validé par l'architecte, implémentation réalisée conformément au contrat, 28/28 tests ciblés nets nouveaux (7 dans `test_model_roundtrip.py` + 7 dans `test_workflow_roundtrip.py` + 14 dans `test_lora_roundtrip.py`), 913/913 tests automatisés verts, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS sur les trois Pages.
> Aucun commit, tag ou Release n'existe encore pour cette mission — conformément au principe de non-auto-référence, ce document ne contient aucune valeur Git réelle avant la clôture effective (commit, puis tag/Release lors d'une étape ultérieure explicitement autorisée).

## 1. Contexte

Un audit read-only du dépôt après clôture de Mission 051 a comparé les capacités d'édition post-création disponibles pour chaque type d'entité de l'application. `Character` dispose d'un renommage complet depuis longtemps : `CharacterManager.update(character_id, name=..., bio=..., ...)` ([character_manager.py:186](src/managers/character_manager.py:186)) traite explicitement `name` comme un champ scalaire ordinaire du même mécanisme idempotent que les autres champs d'identité — son propre docstring le formule ainsi : *"name included, so a rename and an identity edit share the exact same idempotent mechanism instead of a separate rename flow"*.

Aucune des six autres entités (`Model`, `Workflow`, `LoRA`, `Dataset`, `Training`, `Prompt`) ne dispose de cette capacité :

- `ModelManager` ([model_manager.py](src/managers/model_manager.py)) et `WorkflowManager` ([workflow_manager.py](src/managers/workflow_manager.py)) exposent chacun `update_file_path(file_path: str) -> bool` (édition d'un scalaire unique, idempotente), mais aucune méthode équivalente pour `name`.
- `LoRAManager.update()` ([lora_manager.py:198](src/managers/lora_manager.py:198)) édite `engine`/`architecture`/`trigger_word`/`version` mais exclut explicitement `name` par conception — son propre docstring l'indique : *"Never touches `name`/`files`/`thumbnail` — name has its own creation flow"*.
- `PromptManager.update_text()` ([prompt_manager.py:143](src/managers/prompt_manager.py:143)) n'édite que `text`.
- `DatasetManager` et `TrainingManager` n'exposent **aucune** méthode `update()` de quelque nature que ce soit — `create()`/`select()`/`delete()` (+ `add_images()`/`remove_images()` côté Dataset) sont les seules opérations disponibles.

Ce constat n'est mentionné nulle part dans les "besoins futurs identifiés" de `docs/PROJECT_CONTEXT.md" (qui ne recense que des besoins architecturaux plus larges — sélection multi-engine, refonte Settings, i18n, RAG/LLM, publication sociale, portabilité des chemins) : il s'agit d'un écart mécanique découvert par lecture directe du code, du même type que les écarts trouvés par Missions 048/051 (tri non étendu), pas d'un besoin déjà en attente d'arbitrage.

Mission 051 avait explicitement noté, dans sa propre section "Hors périmètre" : *"Renommage d'une entité après création (...) comportement uniforme constaté, non une incohérence, et hors périmètre de cette mission"* — cette observation portait sur l'uniformité **entre LoRA/Model/Workflow/Prompt/Training entre eux** (aucun n'était renommable), sans comparer à `Character`, qui lui l'est déjà. Le présent audit révèle donc une **asymétrie réelle** (`Character` face aux six autres), pas seulement une absence uniforme.

## 2. Problème

Un utilisateur qui se trompe en nommant un Model, un Workflow ou une LoRA (faute de frappe, nom provisoire, réorganisation) n'a aujourd'hui aucun moyen de corriger ce nom sans supprimer l'entité entière et la recréer — perdant au passage, pour une LoRA, sa fiche de métadonnées (`engine`/`architecture`/`trigger_word`/`version`, Mission 047) et ses fichiers associés (Mission 050), et pour un Model/Workflow, son `file_path`. `Character` ne souffre pas de cette limitation depuis longtemps.

## 3. Objectif

Étendre à `Model`, `Workflow` et `LoRA` la capacité de renommage déjà disponible pour `Character`, en réutilisant le même contrat idempotent déjà établi par `CharacterManager.update()`/`ModelManager.update_file_path()`/`PromptManager.update_text()`/`LoRAManager.update()` — sans introduire de nouveau mécanisme, de confirmation, ou de validation de contenu.

**`Dataset`, `Training` et `Prompt` sont explicitement exclus de cette mission** (section 6) — chacun nécessite son propre audit dédié, pour des raisons distinctes détaillées ci-dessous, plutôt que d'être traité par analogie mécanique.

## 4. Contrat fonctionnel validé

- Chaque Manager concerné gagne une nouvelle méthode **`update_name(...) -> bool`**, sibling additif des méthodes `update_*()` existantes — **aucune méthode existante n'est renommée, fusionnée ou modifiée dans sa signature** :
  - `ModelManager.update_name(name: str) -> bool` — opère sur `self.active_model`, mirroir exact de `update_file_path()` (idempotent : renvoie `False` sans `save()` si aucun modèle actif ou si `name` est identique à la valeur stockée ; chaîne vide non rejetée par le Manager).
  - `WorkflowManager.update_name(name: str) -> bool` — mirroir exact, opère sur `self.active_workflow`.
  - `LoRAManager.update_name(lora_id: str, name: str) -> bool` — signature à `lora_id` explicite, mirroir du style déjà utilisé par `LoRAManager.update(lora_id, ...)` (LoRA est la seule des trois à identifier l'entité explicitement plutôt qu'implicitement via `active_*` — convention déjà existante dans ce Manager, conservée telle quelle plutôt qu'uniformisée artificiellement).
- Aucune de ces méthodes ne publie d'événement dédié — comportement identique à `update_file_path()`/`update_text()`/`LoRAManager.update()`/`CharacterManager.update()`, qui s'appuient tous exclusivement sur `WORKSPACE_SAVED` (émis par `WorkspaceManager.save()`) pour déclencher le rafraîchissement des Pages déjà abonnées. Aucun nouveau wiring EventBus.
- Idempotence stricte identique au reste du projet : valeur identique → `False`, aucun `save()`. Chaîne vide **non validée par le Manager** (cohérent avec `create()` qui ne valide jamais le nom) — c'est la Page qui, comme `create_model()`/`create_workflow()`/`create_lora()` le font déjà à la création, empêche l'envoi d'un nom vide côté UI (`.strip()`, retour silencieux si vide après trim).
- Côté UI, chaque Page (`ModelsPage`, `WorkflowsPage`, `LoRAPage`) gagne un nouveau `QLineEdit` **éditable** (`name_edit`), distinct des champs déjà read-only (`file_path_edit`) ou informatifs (`engine_edit` etc.), peuplé avec le nom de l'entité active et vidé quand aucune entité n'est active — même mécanisme de peuplement que `file_path_edit`/`engine_edit` déjà en place dans `update_models()`/`update_workflows()`/`update_loras()`.
- Le renommage se déclenche sur `name_edit.editingFinished` (perte de focus ou Entrée) — **pas de bouton "Renommer" séparé, pas de dialogue dédié** — cohérent avec le mécanisme déjà en place pour `browse_file()`/`LoRAPage`'s metadata fields (édition immédiate, sans étape de sauvegarde explicite distincte). Ce choix suit le précédent déjà établi dans le code (édition immédiate par scalaire) plutôt que le précédent alternatif `RenameProjectDialog` (Mission 027, dialogue dédié pour le renommage du Workspace) — les deux précédents coexistent dans le dépôt pour des objets de nature différente (un Workspace entier vs un champ scalaire d'une entité déjà éditée en place), le second est retenu ici car c'est celui déjà utilisé pour éditer les autres champs scalaires de ces mêmes Pages.
- Après renommage, le rafraîchissement déclenché par `WORKSPACE_SAVED` retrie automatiquement la liste (tri alphabétique déjà livré par Mission 048/051) — l'entité renommée peut donc changer de position visuelle ; la sélection doit continuer à cibler la bonne entité par identité (`model_id`/`workflow_id`/`lora_id`), exactement comme Mission 051 l'a déjà vérifié pour un rafraîchissement après création. Aucun mécanisme nouveau requis — c'est le même `setCurrentItem()` par correspondance d'ID déjà en place.
- Aucune validation d'unicité de nom — cohérent avec l'absence totale de contrainte d'unicité déjà existante pour la création (`create()` ne valide jamais le nom, deux entités peuvent déjà partager le même nom aujourd'hui).
- Aucune confirmation avant renommage — action non destructive, cohérent avec l'absence de confirmation déjà établie pour l'édition des métadonnées LoRA (Mission 047) et du `file_path` de Model/Workflow.

## 5. Périmètre

Production (6) :
- `src/managers/model_manager.py` (nouvelle méthode `update_name()`)
- `src/managers/workflow_manager.py` (nouvelle méthode `update_name()`)
- `src/managers/lora_manager.py` (nouvelle méthode `update_name()` ; révision du docstring de `update()` existant, dont la mention "name has its own creation flow" devient trompeuse une fois `update_name()` ajoutée)
- `src/ui/pages/models_page.py` (`name_edit`, peuplement dans `update_models()`, nouveau handler `rename_model()`)
- `src/ui/pages/workflows_page.py` (mirroir exact pour `rename_workflow()`)
- `src/ui/pages/lora_page.py` (`name_edit` positionné avant le panneau `metadata_form` existant — le nom n'est pas une métadonnée LoRA au sens de Mission 047, il identifie l'entité elle-même — peuplement dans `update_loras()`, nouveau handler `rename_lora()`)

Tests (3, aucun nouveau fichier) :
- `tests/integration/test_model_roundtrip.py`
- `tests/integration/test_workflow_roundtrip.py`
- `tests/integration/test_lora_roundtrip.py`

## 6. Hors périmètre

- **`Prompt`** : structure de Page incompatible avec le mécanisme envisagé — `PromptsPage` n'a pas de panneau de détails scalaire comparable (seulement `prompt_list` + `text_edit`, avec un mécanisme de dirty-state dédié établi par Mission 038). Ajouter un renommage immédiat sur perte de focus interagirait avec ce dirty-state d'une façon non encore auditée (le renommage doit-il être bloqué/avertir si `self._dirty` est vrai ? doit-il partager le même bouton "Enregistrer le texte" ?) — nécessite son propre mini-audit dédié, pas un traitement par analogie mécanique.
- **`Dataset`** et **`Training`** : aucune méthode `update()` d'aucune sorte n'existe aujourd'hui pour ces deux Managers — ajouter `update_name()` introduirait la toute première capacité d'édition post-création pour ces entités, un précédent structurel plus significatif qu'une simple extension d'un mécanisme déjà existant. Candidat probable pour une mission future distincte, une fois auditée indépendamment.
- **`Character`** : dispose déjà de cette capacité depuis Mission 026 — aucun changement.
- Toute validation d'unicité de nom, toute confirmation avant renommage, tout dialogue dédié de type `RenameProjectDialog`.
- Toute modification de `Model`/`Workflow`/`LoRA` (Domain — le champ `name` existe déjà, aucun changement de schéma).
- Tout nouveau wiring EventBus, toute nouvelle constante d'événement.
- `LoRAManager.update()` existant : signature et comportement inchangés pour `engine`/`architecture`/`trigger_word`/`version` — seul son docstring est révisé pour rester exact.

## 7. Wiring de rafraîchissement — aucun ajout

```
WORKSPACE_SAVED / WORKSPACE_CREATED / WORKSPACE_OPENED / WORKSPACE_CLOSED / MODEL_*
  → ModelsPage.update_models()        (name_edit peuplé, tri déjà appliqué par Mission 051)

WORKSPACE_SAVED / ... / WORKFLOW_*
  → WorkflowsPage.update_workflows()  (idem)

WORKSPACE_SAVED / ... / LORA_*
  → LoRAPage.update_loras()           (idem, lora_list uniquement)
```

`update_name()` ne publie aucun événement propre — le rafraîchissement passe exclusivement par `WORKSPACE_SAVED`, déjà souscrit par chaque Page concernée.

## 8. Stratégie d'implémentation — réellement mise en œuvre

`ModelManager.update_name()` ([model_manager.py](src/managers/model_manager.py)) — mirroir exact d'`update_file_path()` :
```python
def update_name(self, name: str) -> bool:
    model = self.active_model
    if model is None:
        return False
    if model.name == name:
        return False
    model.name = name
    self._workspace_manager.save()
    return True
```
Même traitement pour `WorkflowManager.update_name()`. `LoRAManager.update_name(lora_id, name)` mirroir de `update()` avec `lora_id` explicite (convention déjà utilisée par ce Manager). Le docstring de `LoRAManager.update()` a été révisé (`"name has its own creation flow"` → `"name has its own sibling method (update_name(), Mission 052)"`).

Côté UI, chaque Page gagne un `name_edit` éditable, positionné juste après la liste (`ModelsPage`/`WorkflowsPage`) ou juste après `lora_list` (`LoRAPage`, avant le panneau Metadata Mission 047), câblé sur `editingFinished` vers un nouveau handler (`rename_model()`/`rename_workflow()`/`rename_lora()`) appelant directement `Manager.update_name(...)` avec `self.name_edit.text()` **sans `.strip()`**, conformément à la politique constatée (section "Validation du nom du contrat" ci-dessus, confirmée identique à `CharactersPage.save_identity()`). Peuplement dans `update_models()`/`update_workflows()`/`update_loras()`, exactement comme `file_path_edit`/`engine_edit` déjà en place.

**Politique de validation du nom réellement constatée avant implémentation** : `CharactersPage.save_identity()` appelle `self.character_manager.update(principal_id, name=self.name_edit.text(), ...)` **sans `.strip()` et sans garde anti-vide** — contrairement aux flux de création (`create_character()`/`create_model()`/`create_workflow()`/`create_lora()`, qui font tous `.strip()` + rejettent le vide via `QInputDialog`). Aucune contradiction entre les trois entités : les trois flux de création partagent exactement la même politique (strip + rejet du vide), et le seul précédent de renommage existant (Character) ne strip ni ne rejette rien. Mission 052 suit ce seul précédent de renommage sans en inventer un nouveau — aucun arrêt nécessaire.

## 9. Stratégie de tests — réellement mise en œuvre

Trois nouvelles classes de tests Manager + trois nouvelles classes de tests Page (aucun nouveau fichier) :
- `test_model_roundtrip.py` : `test_update_name_is_idempotent`/`test_rename_persists_after_close_reopen` (dans `ModelRoundTripTest`) + `ModelsPageRenameTest` (5 tests) = 7 tests nets nouveaux.
- `test_workflow_roundtrip.py` : mirroir exact = 7 tests nets nouveaux.
- `test_lora_roundtrip.py` : `LoRAManagerRenameTest` (7 tests) + `LoRAPageRenameTest` (7 tests) = 14 tests nets nouveaux.

Chaque classe Manager couvre : renommage réel, idempotence (`save()` non appelé si valeur identique, vérifié par `patch.object`), `save()` appelé une seule fois lors d'une mutation réelle, préservation de l'ID et des autres champs (`file_path` pour Model/Workflow ; `files`/`engine`/`architecture`/`trigger_word`/`version` pour LoRA), chaîne vide légitime, entité/`lora_id` inconnu → `False`, persistance après fermeture/réouverture.

Chaque classe Page couvre : renommage via le vrai widget (`name_edit.setText()` + `editingFinished.emit()`), déplacement vers le début de liste avec sélection conservée par ID, déplacement vers la fin de liste avec sélection conservée par ID, no-op sans entité active, persistance via l'UI après fermeture/réouverture. `LoRAPageRenameTest` ajoute explicitement : préservation de `files_list`/Metadata/thumbnail après renommage, et non-régression de `add_files()`/`remove_files()`/`save_metadata()`/`set_thumbnail()` appelés après un renommage.

**Vérification préalable confirmée** : aucun accès positionnel `model_list.item(`/`workflow_list.item(`/`lora_list.item(` ne contractualisait l'ordre d'insertion (déjà confirmé par l'audit de Mission 051) — aucune reformulation de test existant n'a été nécessaire.

**28/28 tests ciblés nets nouveaux, tous verts** (7+7+14). **913/913 tests automatisés verts** au total (885 précédents + 28 nets nouveaux) — suites `test_model_roundtrip.py` (20/20), `test_workflow_roundtrip.py` (21/21), `test_lora_roundtrip.py` (67/67) intégralement vertes.

## 10. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels), script exclusivement dans le scratchpad de session, 3 scénarios réels (un par Page).

Points observés réellement, tous conformes :
- **ModelsPage** : "Mango Model"/"Zebra Model" créés, "Zebra Model" sélectionné avec `file_path` réel associé ; renommage réel vers "Apple Model" (déplacement vers le début) → liste retriée `["Apple Model", "Mango Model"]`, sélection toujours sur l'entité renommée par `model_id`, `file_path_edit` toujours "C:/models/zebra.safetensors", `model_id` inchangé ; persistance confirmée après fermeture/réouverture réelle du Workspace.
- **WorkflowsPage** : "Apple Flow" sélectionné avec `file_path` réel, renommage réel vers "Zzz Flow" (déplacement vers la fin) → liste retriée `["Mango Flow", "Zzz Flow"]`, sélection conservée par `workflow_id`, `file_path_edit` préservé, persistance confirmée.
- **LoRAPage** : "Zebra Style" sélectionné avec fichier réel importé + Metadata réelle (`engine`/`trigger_word`) ; renommage réel vers "Apple Style" (déplacement vers le début) → liste retriée `["Apple Style", "Mango Style"]`, sélection conservée par `lora_id`, `files_list`/`engine_edit`/`trigger_word_edit` tous préservés ; `add_files()`/`remove_files()` réels confirmés fonctionner normalement après le renommage ; persistance confirmée (nom, fichiers et métadonnées) après fermeture/réouverture réelle.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 11. Risques / non-régressions

- **Risque d'interaction avec le tri Mission 051** : écarté — vérifié par test et smoke test réel, la sélection continue de reposer sur l'ID (jamais la position) dans les deux sens de déplacement (vers le début et vers la fin de liste).
- **Risque de confusion avec les métadonnées LoRA (Mission 047)/les fichiers LoRA (Mission 050)** : écarté — `name_edit` reste hors du panneau `metadata_form`, `files_list`/`LoRA.files`/`thumbnail` confirmés intacts par test dédié et smoke test réel, non-régression explicite de `add_files()`/`remove_files()`/`save_metadata()`/`set_thumbnail()` vérifiée après renommage.
- **Risque de docstring obsolète** : résolu — le docstring de `LoRAManager.update()` a été mis à jour pour référencer `update_name()`.
- **Risque de sur-portée** : écarté — `Dataset`/`Training`/`Prompt`/`Character` non touchés, confirmé par `git diff --stat` (section suivante).

## 11. Pourquoi maintenant plutôt que différée

Ce candidat est retenu plutôt que les autres pistes identifiées lors de l'audit (exploitation de `comfyui_path`, copie interne des fichiers Model/Workflow/LoRA, portabilité des chemins, multi-engine, refonte Settings, i18n, RAG/LLM) parce qu'il ne nécessite, pour les trois entités retenues, aucun arbitrage architectural : le contrat idempotent, la convention de nommage de méthode, le mécanisme d'édition immédiate et l'absence de validation/confirmation sont tous déjà entièrement déterminés par des précédents directs et sans ambiguïté déjà présents dans le code (`CharacterManager.update()`, `ModelManager.update_file_path()`, `PromptManager.update_text()`, `LoRAManager.update()`). Les autres candidats nécessitent chacun une décision produit ou architecturale explicite (taille/volume de copie de fichiers, choix d'un Engine abstrait, organisation de Settings, portée de l'i18n) et restent donc différés.

## État d'avancement

- Audit de sélection (candidat Mission 052), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 28/28 ciblés (7+7+14), 913/913 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git (commit/tag/Release) : **non encore effectuée** — en attente d'autorisation explicite de commit.
