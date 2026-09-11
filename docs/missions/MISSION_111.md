# Mission 111 — Character.trigger_token → Training.trigger_word Default Prefill

> **MISSION CLÔTURÉE — PRÉREMPLISSAGE CHARACTER.TRIGGER_TOKEN → TRAINING.TRIGGER_WORD VALIDÉ, SUITE COMPLÈTE 2203/2203.** Commit fonctionnel `ba66caa68df7f7eda80950dd134769321f18cd7c` (`Prefill Training.trigger_word from Character.trigger_token at creation`), tag `v0.2-mission111`, GitHub Release publiée. Ce document sert de périmètre fermé avant implémentation (sections 1-11, inchangées) ; la simplification architecturale proposée en §3 (mécanisme entièrement interne à `TrainingManager.create()`, aucune modification de `TrainingPage`) a été confirmée telle quelle par l'architecte avant implémentation, et implémentée exactement en l'état. Voir `CHANGELOG.md` (`v0.2-mission111`) pour le résumé du résultat réel.

## 1. Contexte

L'audit post-Mission 110 a confirmé par lecture directe du code que le premier maillon de la chaîne de provenance du trigger — déjà documentée dans `docs/PROJECT_CONTEXT.md` depuis Mission 108 — reste manquant : `Character.trigger_token` (`character.py:26`, éditable via `CharactersPage.trigger_token_edit`, `characters_page.py:148`) et `Training.trigger_word` (`training.py:64`, éditable via `TrainingPage.trigger_word_edit`, `training_page.py:207`) existent tous deux mais ne sont reliés par aucun code. Or Mission 110 vient de garantir que `Training.trigger_word`, une fois renseigné, se propage fidèlement jusqu'à `LoRA.trigger_word` puis jusqu'au prompt d'Inference — ce qui rend la ressaisie manuelle de ce même mot à chaque nouveau `Training` d'un Character qui en possède déjà un une friction réelle et désormais évitable, pas seulement une continuité de série.

Vérification directe du code réel :

- `TrainingManager.create(name, dataset_id)` (`training_manager.py:251-278`) construit toujours `Training(training_id=..., name=name, dataset_id=dataset_id)` — `trigger_word` reste donc à sa valeur par défaut du dataclass (`""`, `training.py:64`) à chaque création, quel que soit le `trigger_token` du Character. `character = self._character_manager.principal_character` (`training_manager.py:253`) est déjà résolu à cet instant précis, avant la construction de l'objet `Training`.
- `TrainingManager` expose déjà un pattern établi de lecture dérivée de `principal_character` sans jamais exposer `CharacterManager` lui-même à l'appelant : la property `trainings` (`training_manager.py:229-240`) lit `self._character_manager.principal_character` et retourne `[]`/`character.trainings` selon le cas — aucune fuite de `Character` ou de `CharacterManager` vers `TrainingPage`.
- `TrainingPage.__init__` (`training_page.py:64-71`) ne reçoit **pas** `character_manager` — seuls `training_manager`, `dataset_manager`, `workspace_manager`, `application_settings_manager`, `lora_library_manager` lui sont injectés. `TrainingPage.create_training()` (`training_page.py:300-370`) appelle `self.training_manager.create(name.strip(), dataset_id)` puis retourne — la Training fraîchement créée est affichée uniquement via l'événement `TRAINING_CREATED`, reçu par `TrainingPage.update_trainings()` (`training_page.py:548-617`).
- **Point architectural déterminant** : `update_trainings()` est le **même** gestionnaire, abonné à la fois à `TRAINING_CREATED`, `TRAINING_SELECTED`, `TRAINING_DELETED`, `WORKSPACE_SAVED`/`RENAMED` et `CHARACTER_CREATED` (commentaire `training_page.py:548-556`). Il appelle `_load_training_parameters(active_training)` (`training_page.py:619` et suivants) chaque fois que `active_training_id != self._loaded_training_id or not self._dirty` (`training_page.py:600`) — ce qui couvre indifféremment une création réelle, une sélection d'un Training existant, **et** un rafraîchissement non destructif déclenché par un événement Workspace sans rapport. Il n'existe **aucun signal, à ce point du code, distinguant « ce Training vient d'être créé » de « ce Training existant vient d'être chargé/rafraîchi »** — appliquer le préremplissage dans `_load_training_parameters()` ou dans `update_trainings()` violerait directement la règle 8 (aucun préremplissage tardif au chargement d'un Training existant, même vide).
- `CharacterManager.create(name)` ne renseigne jamais `trigger_token` (défaut dataclass `""`) — confirmé par les fixtures de test existantes (`test_training_roundtrip.py:816`, `character_manager.create("Aria")` sans trigger_token), qui créent ensuite des `Training` via `training_manager.create(...)` : le comportement de ces ~15 sites d'appel existants reste strictement inchangé par cette mission, puisque leur Character de test n'a jamais de `trigger_token`.

## 2. Objectif

Fermer le premier maillon de la chaîne de provenance du trigger : à la création d'un nouveau `Training`, son `trigger_word` doit démarrer avec la valeur de `Character.trigger_token` du principal Character si celui-ci en possède un — un préremplissage strict, jamais un lien permanent, jamais une contrainte.

## 3. Décision retenue — mécanisme (affine le périmètre pré-validé par l'architecte)

Le périmètre pré-validé proposait une exposition en lecture seule du `trigger_token` via une nouvelle méthode/property publique de `TrainingManager`, consommée par `TrainingPage` au moment de la création. **L'audit du point 1 ci-dessus établit qu'un mécanisme strictement plus simple et plus sûr existe, entièrement interne à `TrainingManager.create()`** :

`TrainingManager.create()` a déjà résolu `character = self._character_manager.principal_character` (`training_manager.py:253`) avant de construire l'objet `Training` (`training_manager.py:264-266`). Il suffit de construire cet objet avec `trigger_word=character.trigger_token` au lieu de laisser le défaut implicite du dataclass.

Conséquence directe, vérifiée point par point contre le contrat de la section 4 :

1. Valeur par défaut uniquement — un simple champ initial du nouvel objet, jamais un lien conservé. ✅
2. Le préremplissage n'a lieu que dans `create()`, jamais ailleurs. ✅
3. Le nouveau `Training` n'a jamais de `trigger_word` préexistant à ce stade — condition triviale. ✅
4. Valeur = `trigger_token` du principal Character, exactement celui déjà résolu à la ligne 253. ✅
5. Character sans `trigger_token` → `character.trigger_token == ""` → comportement byte-for-byte inchangé (défaut actuel). ✅
6. Une fois l'objet `Training` construit, `trigger_word` est un champ ordinaire — aucune référence conservée vers `Character`. ✅
7. Un changement ultérieur de `Character.trigger_token` ne relit jamais aucun `Training` existant — `create()` n'est appelé qu'une fois, à la création. ✅
8. Charger/sélectionner un Training existant ne passe jamais par `create()` — `update_trainings()`/`_load_training_parameters()` restent **entièrement inchangés**, éliminant tout risque lié au point architectural du §1. ✅
9. Aucune écrasement possible : le champ n'existe pas avant la construction. ✅
10. `trigger_word_edit` reste un champ Qt ordinaire, non touché par cette mission — édition/sauvegarde via `save_training_parameters()` inchangées. ✅

**Aucune nouvelle méthode publique sur `TrainingManager` n'est donc nécessaire, et `TrainingPage` n'a besoin d'aucune modification** — elle affiche déjà `active_training["trigger_word"]` tel quel (`training_page.py:659`), qui contiendra désormais parfois une valeur non vide dès la création plutôt que systématiquement `""`. Ce point doit être confirmé par l'architecte avant implémentation (voir §7) : il s'écarte du périmètre de fichiers pré-validé (qui prévoyait une modification de `training_page.py`) en le réduisant, jamais en l'élargissant.

## 4. Comportement contractuel (rappel exact, validé par l'architecte, non renégocié ici)

1. `Character.trigger_token` sert uniquement de valeur par défaut pour le `trigger_word` d'un nouveau Training.
2. Le préremplissage n'a lieu qu'à la création/initialisation d'un nouveau Training.
3. Il ne s'applique que si le `trigger_word` du nouveau Training est vide.
4. La valeur utilisée est le `trigger_token` du principal Character courant.
5. Si ce Character ne possède aucun `trigger_token`, le champ Training reste vide.
6. Dès que le Training existe, `Character.trigger_token` et `Training.trigger_word` deviennent indépendants.
7. Une modification ultérieure de `Character.trigger_token` ne doit jamais modifier un Training existant.
8. Charger/sélectionner un Training existant ne doit jamais déclencher de préremplissage tardif, même si son `trigger_word` est vide.
9. Une valeur déjà présente dans `Training.trigger_word` ne doit jamais être écrasée.
10. Le champ reste entièrement éditable par l'utilisateur — aucun verrou, aucune synchronisation permanente, aucune contrainte.

## 5. Périmètre exact — fichiers concernés

- `src/managers/training_manager.py` (modifié) — un seul changement, dans `create()` : `trigger_word=character.trigger_token` passé à la construction de `Training(...)`.
- `tests/integration/test_training_roundtrip.py` (modifié) — nouveaux tests de préremplissage (section 7).

**Aucun changement attendu** à `src/ui/pages/training_page.py`, `src/domain/training.py`, `src/domain/character.py`, `src/managers/character_manager.py`, `MainWindow`, tout Engine ou l'EventBus — si l'implémentation réelle révèle qu'un changement dans l'un de ces fichiers est nécessaire, arrêt et rapport avant tout élargissement.

## 6. Hors périmètre strict — ne pas ajouter à cette mission

- Champ ou liaison `character_id` dans `LoRA`.
- Association `LoRA ↔ Character`.
- Toute synchronisation permanente Character ↔ Training au-delà de l'instant de création.
- Mise à jour rétroactive des Trainings déjà existants.
- Génération automatique d'un trigger.
- Toute modification du comportement Mission 110 dans `InferencePage` (affichage/insertion du trigger).
- Correctif de détection des sidecars `.txt` depuis la galerie.
- Gestion Start/Stop/Recheck des backends.
- Refonte de `TrainingPage` ou de `SettingsPage`.
- Tout autre besoin futur déjà documenté dans `docs/PROJECT_CONTEXT.md`.

## 7. Étape technique attendue

Dans `TrainingManager.create()` (`training_manager.py:251-278`), remplacer :

```python
training = Training(
    training_id=str(uuid.uuid4()), name=name, dataset_id=dataset_id
)
```

par :

```python
training = Training(
    training_id=str(uuid.uuid4()), name=name, dataset_id=dataset_id,
    trigger_word=character.trigger_token,
)
```

`character` est déjà en scope local (ligne 253), déjà garanti non-`None` par le guard des lignes 255-256. Aucun autre changement dans cette méthode ni ailleurs dans `TrainingManager`.

## 8. Tests attendus

`tests/integration/test_training_roundtrip.py` (extension, nouvelle classe dédiée) :

1. Character avec `trigger_token` non vide → `training_manager.create(...)` produit un `Training.trigger_word` égal à ce `trigger_token`.
2. Character sans `trigger_token` (défaut `""`) → `Training.trigger_word` reste `""`, comportement inchangé.
3. Un Training déjà existant avec un `trigger_word` non vide, rechargé (`select()` puis relecture, ou via `update_trainings()`/`_load_training_parameters()` côté `TrainingPage`) → sa valeur reste strictement inchangée.
4. Un Training déjà existant avec un `trigger_word` vide, rechargé → reste vide, aucun préremplissage tardif déclenché par le rechargement.
5. Modification manuelle du `trigger_word` d'un Training existant (`update()`/`save_training_parameters()`) → la valeur utilisateur est conservée telle quelle, jamais réécrasée par `Character.trigger_token`.
6. `Character.trigger_token` modifié après la création d'un Training → le `trigger_word` de ce Training déjà existant reste inchangé.
7. Non-régression Mission 110 : un `Training.trigger_word` préremplid par cette mission est transmis tel quel à `LoRALibraryManager.import_lora()` lors de l'import (`TrainingPage.import_selected_job_to_library()`, `training_page.py:1283`), exactement comme un `trigger_word` saisi manuellement.

Aucun widget Qt réel n'est strictement nécessaire pour couvrir cette mission (toute la logique est contenue dans `TrainingManager`) — un smoke réel reste possible si l'architecte le souhaite, mais n'est pas requis par le périmètre retenu à la section 3.

## 9. Critères de clôture

1. `TrainingManager.create()` implémenté exactement selon la section 7, testé selon la section 8.
2. Les 10 points du contrat comportemental (section 4) vérifiés explicitement par au moins un test chacun.
3. Aucun des ~15 sites d'appel de test existants de `training_manager.create(...)` n'est modifié ni ne change de comportement (Character de test sans `trigger_token` dans tous les cas déjà présents).
4. Zéro modification de `TrainingPage`, Domain, `CharacterManager`, `MainWindow`, Engines, EventBus — sauf anomalie réelle découverte et rapportée avant tout élargissement.
5. Suite complète verte au nombre exact, `git diff --check` propre.
6. Aucun élément de la section 6 n'a été ajouté.

## 10. Documentation

- Cette mission ne modifie ni ne referme aucun autre besoin futur déjà enregistré dans `docs/PROJECT_CONTEXT.md` (association `LoRA ↔ Character`, réorganisation `SettingsPage`, gestion des backends, sidecars galerie, captioning IA, etc.) — tous restent explicitement ouverts et non tranchés.
- La régularisation documentaire post-clôture (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`, notamment la mise à jour de l'entrée « Liaison Character ↔ Training ↔ LoRA pour le trigger » déjà partiellement close par Mission 110) suivra le même processus que les missions précédentes, après commit/tag/Release.

## 11. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte — en particulier de la simplification proposée à la section 3 (mécanisme entièrement interne à `TrainingManager.create()`, aucune modification de `TrainingPage`).
