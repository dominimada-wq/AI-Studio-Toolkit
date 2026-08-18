# Mission 029 — Principal Character Consistency (LoRA / Prompts / Training)

**État final (voir sections 14/15)** : implémentée, testée (513/513) et validée par un smoke test manuel réel — **PASS**. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte (voir "Commit correspondant"/"Tag" ci-dessous).

## 1. Contexte

Mission 028 (voir `docs/missions/MISSION_028.md`, section 22.2) a révélé, lors de son premier smoke test réel, une régression bloquante dans `DatasetManager` : la propriété `datasets`, `create()`, `is_referenced_by_training()` et `delete()` dépendaient de `CharacterManager.active_character`, jamais réaffecté depuis que `CharactersPage` (Mission 026) a cessé d'appeler `CharacterManager.select()` — elle ne fait plus que *lire* `principal_character` pour peupler la fiche d'identité. Conséquence concrète : dans tout Workspace **existant rouvert** (`WORKSPACE_OPENED`, jamais suivi d'une re-sélection automatique), `active_character_id` reste `None` pour toute la session, et toute action dépendant de `active_character` échoue silencieusement — sans qu'aucune action utilisateur ne puisse corriger la situation, la liste multi-personnage étant masquée de l'UI depuis Mission 026.

Mission 028 a corrigé ce défaut uniquement dans `DatasetManager` (strictement dans son périmètre — Import Images), en basculant sur `CharacterManager.principal_character` — exactement le mécanisme déjà validé par Mission 026 pour `CharactersPage`. Elle a explicitement identifié, sans les corriger, que `LoRAManager`, `PromptManager` et `TrainingManager` partagent le même défaut structurel (`docs/PROJECT_CONTEXT.md`, besoin futur "Dette de cohérence Character").

Mission 029 ferme ce besoin : elle applique le même correctif, déjà éprouvé deux fois (`CharactersPage` Mission 026, `DatasetManager` Mission 028), aux trois Managers restants.

## 2. Objectif

Faire en sorte que `LoRAManager`, `PromptManager` et `TrainingManager` restent pleinement utilisables (lecture, création, suppression) après une séquence **création de projet → fermeture → réouverture**, sans qu'aucune sélection manuelle de Character n'ait jamais eu lieu — cohérent avec l'UX cible "1 Workspace = 1 personnage principal" issue de Mission 026, dans laquelle l'utilisateur n'a de toute façon plus aucun moyen de sélectionner manuellement un Character.

Référence architecturale stricte : le mécanisme `CharacterManager.principal_character`/`principal_character_id` existe déjà (`src/managers/character_manager.py`), inchangé depuis Mission 026 — Mission 029 ne crée **aucun nouveau mécanisme**, elle propage un mécanisme existant à trois consommateurs qui ne l'utilisent pas encore.

## 3. Audit exhaustif — méthode

Recherche exhaustive effectuée sur l'intégralité du dépôt (`src/` et `tests/`), au-delà des neuf occurrences déjà repérées lors de l'audit de priorisation :

- `grep -rn "active_character\b" src/ tests/`
- `grep -rn "active_character_id\b" src/ tests/`
- `grep -rn "\.select\(" src/`
- Lecture complète de `character_manager.py`, `lora_manager.py`, `prompt_manager.py`, `training_manager.py`, `dataset_manager.py` (référence déjà corrigée), `characters_page.py`, `lora_page.py`, `prompts_page.py`, `training_page.py`, `models_page.py`, `workflows_page.py`, `datasets_page.py`.
- Lecture complète de `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py`, `test_dataset_roundtrip.py` (section régression Mission 028), `test_character_roundtrip.py`, `test_workflow_roundtrip.py`, `test_model_roundtrip.py`.

Aucun remplacement mécanique n'a été effectué avant cette classification.

## 4. Classification exhaustive des occurrences

### Catégorie 1 — doit utiliser le Character principal (à corriger par Mission 029)

**Code (9 occurrences, confirmant exactement le nombre initialement repéré) :**

| Fichier | Ligne | Méthode | Usage actuel |
|---|---|---|---|
| `src/managers/lora_manager.py` | 60 | `loras` (property) | `character = self._character_manager.active_character` |
| `src/managers/lora_manager.py` | 76 | `create()` | idem |
| `src/managers/lora_manager.py` | 106 | `delete()` | idem |
| `src/managers/prompt_manager.py` | 60 | `prompts` (property) | idem |
| `src/managers/prompt_manager.py` | 76 | `create()` | idem |
| `src/managers/prompt_manager.py` | 106 | `delete()` | idem |
| `src/managers/training_manager.py` | 62 | `trainings` (property) | idem |
| `src/managers/training_manager.py` | 78 | `create()` | idem |
| `src/managers/training_manager.py` | 116 | `delete()` | idem |

Chaque occurrence sera remplacée par `self._character_manager.principal_character` — remplacement à l'identique de celui déjà appliqué à `DatasetManager` en Mission 028, aucune autre ligne de ces méthodes ne change.

**Docstrings de classe (3 occurrences, précision documentaire, même esprit que la mise à jour du docstring de `DatasetManager` en Mission 028) :**

| Fichier | Ligne | Contenu actuel |
|---|---|---|
| `src/managers/lora_manager.py` | 27 | "Operates exclusively on `character_manager.active_character.loras`" |
| `src/managers/prompt_manager.py` | 27 | "Operates exclusively on `character_manager.active_character.prompts`" |
| `src/managers/training_manager.py` | 27 | "Operates exclusively on `character_manager.active_character.trainings`" |

À reformuler en `character_manager.principal_character.*`, sur le modèle du docstring déjà mis à jour de `DatasetManager` ("Coordinates ... within the Workspace's principal Character (Mission 026/028)").

**Messages UI (3 occurrences) — texte devenu trompeur après correction :**

| Fichier | Méthode | Titre actuel | Texte actuel |
|---|---|---|---|
| `src/ui/pages/lora_page.py:66-70` | `create_lora()` | "Aucun personnage actif" | "Sélectionnez un personnage avant de créer une LoRA." |
| `src/ui/pages/prompts_page.py:67-71` | `create_prompt()` | "Aucun personnage actif" | "Sélectionnez un personnage avant de créer un prompt." |
| `src/ui/pages/training_page.py:89-93` | `create_training()` | "Aucun personnage actif" | "Sélectionnez un personnage avant de créer une session d'entraînement." |

Une fois la correction appliquée, `create()` ne peut plus renvoyer `None` que dans le cas réel résiduel (aucun Character du tout dans le Workspace — Character supprimé via le CRUD interne encore fonctionnel) — exactement le cas déjà traité par `DatasetsPage.create_dataset()` depuis Mission 028. Les trois messages seront reformulés sur son modèle exact :

> Titre : **"Aucun personnage"**
> Texte : **"Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un(e) [LoRA / prompt / session d'entraînement]."**

### Catégorie 2 — doit conserver `active_character`/`active_character_id` (compatibilité multi-Character interne, à ne pas toucher)

| Emplacement | Rôle |
|---|---|
| `CharacterManager.active_character` / `active_character_id` (définition, `character_manager.py`) | Mécanisme lui-même — protégé explicitement par la consigne de l'architecte, jamais modifié. |
| `CharacterManager._ensure_default_character()` → `self.select(...)` (`character_manager.py:71-72`) | Sélectionne réellement le Character principal auto-créé à `WORKSPACE_CREATED` — c'est ce qui permet à `principal_character` de résoudre correctement dès la création, sans jamais passer par son repli. Ne concerne aucun des trois Managers ciblés. |
| `CharactersPage.on_selection_changed()` → `character_manager.select(...)` (`characters_page.py:173`) | Mécanisme de sélection de la liste masquée (`setVisible(False)`), conservé pour compatibilité interne/tests multi-personnage, explicitement protégé par la consigne "ne pas réintroduire la liste multi-Character dans l'UI". |
| `CharactersPage.update_characters()` → `active_character_id` (`characters_page.py:214`) | Pilote uniquement l'item mis en surbrillance dans la liste masquée — sans lien avec la fiche affichée (`principal_character_id`, déjà correct depuis Mission 026). |
| `lora_manager.select()` / `active_lora_id`, `prompt_manager.select()` / `active_prompt_id`, `training_manager.select()` / `active_training_id`, `dataset_manager.select()` / `active_dataset_id` | Sélection de l'entité **elle-même** (une LoRA, un Prompt, une Session, un Dataset) au sein du Character principal — concept indépendant de la sélection de Character, jamais concerné par ce correctif. |
| `models_page.py:89` (`model_manager.select(...)`), `workflows_page.py:89` (`workflow_manager.select(...)`) | `Model`/`Workflow` sont Workspace-owned (voir `02_ARCHITECTURE.md`/`PROJECT_CONTEXT.md`) — aucune dépendance à `CharacterManager`, confirmé par lecture des deux Managers. Hors sujet. |
| Tests historiques multi-Character de `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py` (voir section 5) | Appellent `character_manager.select()` explicitement pour prouver la compatibilité multi-Character interne — comportement à préserver à l'identique, ces tests ne doivent nécessiter **aucune modification**. |
| `test_workflow_roundtrip.py:305`, `test_model_roundtrip.py:288` | Simples commentaires mentionnant `active_character_id` dans un docstring de test générique (mécanisme de reset sur changement de contexte) — aucun code réel, aucun rapport avec `LoRA`/`Prompt`/`Training`. |

### Catégorie 3 — hors périmètre

- `DatasetManager` (déjà corrigé Mission 028) — aucune régression liée découverte pendant cet audit ; conformément à la consigne, non retouché.
- `test_character_roundtrip.py`, `test_workspace_roundtrip.py` — exercent `CharacterManager` lui-même (non modifié par cette mission).
- Toute la chaîne `active_dataset_id`/`active_lora_id`/`active_prompt_id`/`active_training_id` (sélection de l'entité, pas du Character) — inchangée.

## 5. Constat clé de l'audit — les fixtures existantes masquent le bug réel

Confirmation exhaustive, comme demandé : **la totalité** des tests existants de `test_lora_roundtrip.py` (6 méthodes), `test_prompt_roundtrip.py` (6 méthodes) et `test_training_roundtrip.py` (9 méthodes) appellent `character_manager.select(...)` explicitement avant d'exercer le Manager concerné. Aucun test existant ne reproduit la séquence réelle "réouverture sans sélection manuelle" — exactement le point que l'architecte demandait de vérifier. C'est structurellement la même situation que celle qui a permis à la régression `DatasetManager` de passer inaperçue jusqu'au smoke test réel de Mission 028 : les tests prouvent la compatibilité multi-Character (catégorie 2, à préserver), mais aucun ne couvre le chemin mono-Character réel après réouverture.

`test_dataset_roundtrip.py` contient déjà, depuis Mission 028, le test de référence exact à répliquer : `DatasetCreationWithoutManualCharacterSelectionTest.test_create_dataset_and_import_images_without_ever_selecting_a_character` (lignes 636-710) — crée un Workspace, le ferme, le rouvre sans jamais appeler `select()`, puis vérifie que l'action métier réussit.

## 6. Scénario de régression central — à reproduire pour les trois Managers

Pour chacun de `LoRAManager`, `PromptManager`, `TrainingManager`, un nouveau test doit reproduire exactement :

```
création du Workspace (auto-crée/sélectionne le Character principal, Mission 026)
→ fermeture du Workspace
→ réouverture du Workspace (WORKSPACE_OPENED — active_character_id redevient None)
→ aucune visite de CharactersPage, aucun appel à select()
→ action métier : lecture de la liste (doit refléter les données existantes, pas une liste vide)
→ création d'une nouvelle entité (doit réussir)
→ (Training uniquement) l'entité créée doit référencer un Dataset existant du Character principal
→ suppression de l'entité (doit réussir)
```

Avant correction, ce scénario échoue de façon identique aux trois Managers (liste vide au lieu des données réelles, `create()`/`delete()` retournent silencieusement `None`/`False`) — vérifié par lecture directe du code (section 4), pas seulement supposé.

## 7. Architecture retenue

Aucune architecture nouvelle. Remplacement textuel `active_character` → `principal_character` aux 9 emplacements de catégorie 1, plus mise à jour des 3 docstrings et des 3 messages UI. Aucune modification de :

- `CharacterManager` (aucune méthode, aucune propriété, aucun événement) ;
- la sérialisation de `Workspace.characters` ;
- la cardinalité (`list[Character]` reste 0..N, aucune contrainte `max=1`) ;
- `DatasetManager` (sauf découverte contraire, non confirmée par cet audit) ;
- `LoRAManager.add_files()`/`PromptManager.update_text()`/`*.select()`/`active_lora_id`/`active_prompt_id`/`active_training_id` (sélection de l'entité elle-même, catégorie 2/3, non concernée).

Aucun nouvel événement EventBus, aucune nouvelle méthode publique.

## 8. Périmètre IN

- `src/managers/lora_manager.py` : 3 occurrences `active_character` → `principal_character` + docstring de classe.
- `src/managers/prompt_manager.py` : idem.
- `src/managers/training_manager.py` : idem.
- `src/ui/pages/lora_page.py` : message d'avertissement de `create_lora()`.
- `src/ui/pages/prompts_page.py` : message d'avertissement de `create_prompt()`.
- `src/ui/pages/training_page.py` : message d'avertissement de `create_training()`.
- Nouveaux tests de régression (un par Manager, voir section 9).

## 9. Périmètre OUT (explicitement différé)

- Chemins internes relatifs / portabilité — candidat probable Mission 030, non abordé ici.
- Alimentation d'un Dataset depuis la galerie Images — non abordé.
- Miniatures `DatasetsPage` — non abordé.
- Tri de la galerie `ImagesPage` — non abordé.
- Images de référence multi-usage (1..N, rôles, IP-Adapter/ControlNet) — non abordé.
- Toute contrainte de cardinalité `Workspace.characters` (`max=1`) — non abordé, orientation Project/Character non retranchée davantage que Mission 026.
- Réintroduction de la liste multi-Character dans l'UI — explicitement exclue.
- Refonte générale des Managers, de `CharacterManager`, ou de tout mécanisme au-delà du remplacement ciblé décrit ci-dessus.
- `DatasetManager` — non modifié sauf découverte d'une régression directement liée (aucune trouvée pendant cet audit).

## 10. Stratégie de tests

### 10.1 Tests existants concernés (aucune modification attendue)

Tous les tests de `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py` appellent déjà `character_manager.select()` avant d'exercer le Manager (voir section 5) : ils exercent le chemin `principal_character → active_character` (catégorie 2, préféré quand actif), qui reste inchangé par ce correctif. Ces tests doivent continuer à passer **sans modification** — c'est en soi une vérification de non-régression multi-Character, à confirmer par exécution réelle après correction, pas seulement par lecture.

### 10.2 Fixtures pouvant masquer le bug (identifiées, à ne pas dupliquer par erreur)

Toute fixture appelant `character_manager.select(...)` avant l'action testée valide le chemin multi-Character explicite, jamais le chemin réel "réouverture sans sélection" — c'est précisément pour cela que trois nouvelles classes de test dédiées (section 10.3) sont nécessaires plutôt que d'étendre les fixtures existantes.

### 10.3 Nouveaux tests de régression requis (un par Manager, sur le modèle de `DatasetCreationWithoutManualCharacterSelectionTest`)

- **`LoRACreationWithoutManualCharacterSelectionTest`** (`test_lora_roundtrip.py`) : création Workspace → fermeture → réouverture → aucun `select()` → `lora_manager.loras` reflète les LoRA existantes → `create()` réussit → `delete()` réussit.
- **`PromptCreationWithoutManualCharacterSelectionTest`** (`test_prompt_roundtrip.py`) : même séquence, avec en plus la vérification que `update_text()` fonctionne toujours via `active_prompt`/`select()` local (entité, catégorie 2, doit rester intact) après réouverture.
- **`TrainingCreationWithoutManualCharacterSelectionTest`** (`test_training_roundtrip.py`) : même séquence, avec un Dataset pré-existant du Character principal (créé avant fermeture) référencé par `create(name, dataset_id)` après réouverture — vérifie à la fois la correction et que le contrôle "dataset appartient au Character principal" (`training_manager.py:86`) continue de fonctionner correctement une fois `character` résolu via `principal_character`.

Chacun de ces trois tests doit vérifier explicitement `character_manager.active_character_id is None` juste avant l'action testée (comme le fait déjà le test `DatasetManager` équivalent), pour garantir que le test reproduit réellement le cas qui déclenchait le bug — pas seulement un cas où le correctif serait accidentellement inutile.

### 10.4 Tests UI nécessaires

Les pages (`LoRAPage`, `PromptsPage`, `TrainingPage`) délèguent entièrement à leurs Managers respectifs sans logique de sélection de Character propre — la correction Manager suffit à corriger leur comportement. Deux ajustements ciblés :

- Un test par page vérifiant que le nouveau message ("Aucun personnage" / texte révisé, section 4) s'affiche bien dans le cas résiduel réel (Character explicitement supprimé), remplaçant l'assertion sur l'ancien texte partout où elle existe actuellement (recherche à effectuer avant implémentation : aucun test actuel de `test_lora_roundtrip.py`/`test_prompt_roundtrip.py`/`test_training_roundtrip.py` ne semble asserter sur ce texte précis d'après l'audit — à confirmer lors de l'implémentation).
- Pas de nouveau test `update_*()` dédié nécessaire au-delà des trois tests de régression Manager (section 10.3) : `LoRAPage.update_loras()`/`PromptsPage.update_prompts()`/`TrainingPage.update_trainings()` lisent déjà directement `list_loras()`/`list_prompts()`/`list_trainings()`, eux-mêmes corrigés par la modification du Manager — aucune logique UI supplémentaire ne dépend d'`active_character`.

### 10.5 Ordre d'exécution prévu

Recherche préalable des mocks/signatures obsolètes (habitude établie), puis suite complète :

```
./.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
```

Nombre exact confirmé après implémentation : **513/513** (510 précédents + 3 nouveaux tests de régression, un par Manager — voir section 14).

## 11. Protocole de smoke test manuel réel

1. Créer un nouveau projet ("Nouveau projet"). Le personnage principal est auto-créé/sélectionné (Mission 026).
2. Aller dans LoRA → créer une LoRA "Style A" → Prompts → créer un prompt "Portrait" avec un texte → Datasets → créer un dataset "Base" → Training → créer une session référençant "Base".
3. Fermer le projet (Fichier → Fermer, ou équivalent).
4. Rouvrir le même projet depuis "Ouvrir un projet" — **ne jamais visiter Characters, ne jamais faire de sélection manuelle.**
5. Aller directement dans LoRA : "Style A" doit être visible dans la liste (pas une liste vide).
6. Créer une seconde LoRA "Style B" : doit réussir sans message d'erreur.
7. Aller dans Prompts : "Portrait" doit être visible avec son texte. Créer un second prompt : doit réussir.
8. Aller dans Training : la session doit être visible. Créer une seconde session référençant "Base" : doit réussir.
9. Supprimer une LoRA, un prompt et une session : chaque suppression doit réussir.
10. Fermer et rouvrir une seconde fois : les créations/suppressions de l'étape précédente doivent avoir persisté.

PASS attendu sur l'ensemble des 10 étapes, sans qu'aucune ne nécessite un passage par Characters.

## 12. Documentation — condition de clôture du besoin futur

Le besoin futur documenté dans `docs/PROJECT_CONTEXT.md` ("Dette de cohérence Character — `active_character` vs `principal_character` dans `LoRAManager`/`PromptManager`/`TrainingManager`") ne sera retiré/reclassé en "Fonctionnalités terminées" **qu'après** confirmation du smoke test manuel réel PASS (section 11) — pas à la seule confirmation des tests automatisés, conformément à la procédure de validation standard du projet (`CLAUDE.md`).

## 13. Risques résiduels / décisions en attente

- **Aucun risque architectural identifié** — remplacement mécanique et déjà éprouvé deux fois à l'identique, sur un périmètre entièrement audité.
- Seul point à trancher pendant l'implémentation (mineur) : la formulation exacte des trois nouveaux messages UI (section 4) est proposée mais pas encore figée mot pour mot — sur le modèle direct de `DatasetsPage`, simple adaptation du nom de l'entité (LoRA / prompt / session d'entraînement).
- Aucune interaction négative identifiée avec `DatasetManager` (déjà corrigé) ni avec le mécanisme de renommage de projet (Mission 027) — ce correctif ne touche à aucun chemin de fichier.
- Aucune interaction négative identifiée avec la primitive d'import (Mission 028) — `LoRAManager.add_files()` reste inchangé (opère sur `active_lora`, catégorie 2/3).

## 14. Implémentation réalisée — résultat

Conforme au périmètre spécifié (sections 4/8), aucun remplacement hors des occurrences classifiées catégorie 1 :

- **9 usages Manager corrigés** : `LoRAManager.loras`/`create()`/`delete()`, `PromptManager.prompts`/`create()`/`delete()`, `TrainingManager.trainings`/`create()`/`delete()` — `active_character` → `principal_character`, remplacement à l'identique de celui déjà appliqué à `DatasetManager` en Mission 028.
- **3 docstrings de classe** mis à jour (`LoRAManager`, `PromptManager`, `TrainingManager`) pour refléter `principal_character` (Mission 026/028/029).
- **3 messages UI ajustés** (`LoRAPage.create_lora()`, `PromptsPage.create_prompt()`, `TrainingPage.create_training()`) : titre "Aucun personnage" + texte "Ce projet ne possède aucun personnage — créez-en un depuis Characters avant de créer un(e) [LoRA/prompt/session d'entraînement]." — sur le modèle exact du message déjà corrigé de `DatasetsPage` en Mission 028. Aucun test existant n'assertait sur l'ancien texte ; aucune adaptation nécessaire de ce fait.
- **Aucun changement de `CharacterManager`** : `active_character`, `active_character_id`, `select()`, `_ensure_default_character()` strictement inchangés.
- **Aucun changement de `DatasetManager`** : aucune régression liée découverte pendant l'implémentation.
- **Aucun remplacement hors périmètre** : `models_page.py`/`workflows_page.py` (`Model`/`Workflow` Workspace-owned), `.select()`/`active_lora_id`/`active_prompt_id`/`active_training_id`/`active_dataset_id` (sélection d'entité, catégorie 2/3) tous laissés strictement intacts.

**3 nouveaux tests de régression ajoutés**, un par Manager, calqués sur `DatasetCreationWithoutManualCharacterSelectionTest` (Mission 028) :

- `LoRACreationWithoutManualCharacterSelectionTest` (`test_lora_roundtrip.py`).
- `PromptCreationWithoutManualCharacterSelectionTest` (`test_prompt_roundtrip.py`) — vérifie en plus que `update_text()`/`select()` (entité, catégorie 2) continuent de fonctionner à l'identique après réouverture.
- `TrainingCreationWithoutManualCharacterSelectionTest` (`test_training_roundtrip.py`) — vérifie en plus que le contrôle d'appartenance du Dataset référencé continue de fonctionner correctement une fois résolu via `principal_character`.

Chacun vérifie explicitement `active_character_id is None` juste avant l'action testée, compare l'identité du `principal_character` avant/après réouverture, et vérifie que la nouvelle entité créée est bien rattachée à ce même Character (`assertIn(...)`) — pas seulement un retour non-`None` — conformément à la section 10.3.

**Aucun test existant adapté** : les 21 méthodes historiques de `test_lora_roundtrip.py`/`test_prompt_roundtrip.py`/`test_training_roundtrip.py` appelant `character_manager.select()` explicitement restent intactes, comme prévu (section 5) — elles continuent de prouver la compatibilité multi-Character interne.

**Résultats de test** :

- Suites ciblées (`test_lora_roundtrip.py` + `test_prompt_roundtrip.py` + `test_training_roundtrip.py`) : **28/28 OK**.
- Suite complète : **513/513 OK** (510 précédents + 3 nouveaux), aucune régression Dataset/Character détectée.
- `git diff --check` : uniquement des avertissements CRLF bénins (`autocrlf`), aucune erreur réelle.

## 15. Smoke test manuel réel — PASS

Résultat confirmé par l'architecte, conforme au protocole de la section 11 :

- Après fermeture/réouverture du Workspace, **sans jamais passer par Characters** : les LoRA existantes restent visibles, les Prompts existants restent visibles, les Trainings existants restent visibles (pas de liste vide).
- Création de nouvelles entrées après réouverture : OK pour les trois domaines.
- Suppression : OK.
- Persistance confirmée après un second cycle fermeture/réouverture.
- Aucune sélection manuelle de Character nécessaire à aucune étape.

**Point observé, non-échec Mission 029** : le Dashboard affiche `Training: Idle`. Il a été confirmé qu'`Idle` représente l'état d'exécution du moteur Training (aucun moteur d'entraînement réel n'existe, voir Mission 017), pas le nombre de sessions Training enregistrées — l'indicateur ne reflète donc correctement ni une régression ni un succès du comptage, il s'agit d'une ambiguïté de présentation préexistante, sans lien avec la correction `active_character`/`principal_character` de cette mission. Enregistré comme nouveau besoin futur dans `docs/PROJECT_CONTEXT.md` ("Dashboard — clarification de l'indicateur Training"), non implémenté dans cette mission.

## Commit correspondant

Non applicable à ce stade — clôture Git non encore effectuée, en attente de l'autorisation explicite de l'architecte.

## Tag / release correspondant

Non applicable à ce stade — clôture Git non encore effectuée.

## État final

**Implémentation, suite automatisée complète (513/513) et smoke test manuel réel complet validés — PASS.** Correction strictement conforme au périmètre spécifié (9 usages Manager, 3 docstrings, 3 messages UI, 3 nouveaux tests de régression), sans aucun remplacement hors des occurrences classifiées, sans modification de `CharacterManager` ni de `DatasetManager`. Un nouveau besoin futur a été identifié pendant le smoke test et enregistré dans `docs/PROJECT_CONTEXT.md` sans être implémenté : clarification de l'indicateur `Training: Idle` du Dashboard (distinction nombre de sessions enregistrées / état d'exécution du moteur). Le besoin futur "dette de cohérence Character — `active_character` vs `principal_character`" est désormais **résolu** pour les trois Managers concernés — voir `docs/PROJECT_CONTEXT.md`, section "Fonctionnalités terminées". **Clôture Git en attente de l'autorisation explicite de l'architecte.**
