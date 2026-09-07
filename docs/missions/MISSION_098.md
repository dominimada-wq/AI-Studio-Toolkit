# Mission 098 — Dataset Captions (per-image, per-Dataset)

> **MISSION CLÔTURÉE.** Commit fonctionnel `a56a46cd6dd9c4ae483f7915f163bb35cdd55f7f`, tag annoté `v0.2-mission098` sur ce même commit. Voir section 9 pour la validation finale complète (diff, smoke tests Qt/filesystem réels, deux suites complètes monoprocessus) et section 10 pour la clôture Git.

## 1. Contexte

L'audit post-Mission 097 a identifié un besoin réel, documenté au Blueprint depuis l'origine mais jamais implémenté : `docs/blueprint/04_DOMAIN_MODEL.md` §7 (Dataset) liste explicitement "Store captions", "Caption Count" et "Captions" comme enfant structurel du Dataset, au même rang qu'Images/Masks/Metadata — jamais concrétisé. `WorkspaceStorage.DIRECTORIES` réserve déjà un dossier top-level `captions/` dans chaque Workspace, non consommé par aucun code, exactement le schéma que `training/` présentait avant Mission 097.

Ce besoin est directement synergique avec ce que Mission 097 vient de livrer : `TrainingManager._materialize_concept()` écrit aujourd'hui le **même** `training.trigger_word` sur chaque image d'un concept OneTrainer matérialisé — explicitement documenté comme "minimum fonctionnel provisoire" (`training.py`, `training_manager.py`). Mission 098 remplace ce point faible par une vraie caption par image, sans jamais dépendre de l'exécution réelle d'un entraînement.

Orientation architecturale validée par l'architecte avant cette mission : une `Image` globale ne doit pas porter de caption d'entraînement unique (la même image peut appartenir à plusieurs Datasets avec des objectifs différents) — la caption appartient à l'association image↔Dataset, dans l'esprit d'une future structure `DatasetEntry`/`DatasetItem`. La caption stockée dans AI Studio Toolkit est la source canonique ; tout fichier sidecar `.txt` est une matérialisation/export propre à un moteur (OneTrainer aujourd'hui), jamais l'inverse.

Un mini-audit contractuel dédié (voir rapport présenté à l'architecte, non reproduit ici in extenso) a vérifié en source — jamais supposé — l'étendue réelle de `Dataset.images` dans le code et les tests, le comportement de déduplication existant, la stabilité de `Image.image_id` face à un renommage de projet, et un cas de test existant démontrant que deux `Image` peuvent légitimement partager un même `file_path` dans un `project.json` édité à la main. Ce mini-audit a confirmé qu'aucune décision structurante ne reste ouverte.

## 2. Objectif

Permettre d'associer une caption optionnelle à chaque image d'un Dataset, éditable depuis `DatasetsPage`, important automatiquement un sidecar `.txt` déjà présent à côté d'une image importée **depuis le disque**, et faisant remplacer par `TrainingManager._materialize_concept()` le `trigger_word` unique de Mission 097 par cette caption réelle quand elle est explicitement définie — sans jamais toucher à l'exécution d'OneTrainer, à son format de configuration, ni au modèle d'exécution futur de Training.

## 3. Décisions verrouillées (issues du mini-audit, validées par l'architecte — Option 2 retenue)

- **`Dataset.images: list[Image]` reste strictement inchangé** — aucun renommage, aucune restructuration, zéro impact sur les ~155 usages existants (production et tests). Trois options architecturales ont été comparées pour l'association Dataset↔Image (`entries` canonique avec `images` dérivé via une propriété réconciliante ; `images` canonique + `entries` additif dédié aux métadonnées ; dette transitoire non typée) — l'architecte a tranché pour la deuxième : `images` reste la seule collection d'images, `entries` est une collection additive **séparée**, dédiée exclusivement aux métadonnées de l'association.
- **Nouveau champ `Dataset.entries: dict[str, DatasetEntryMetadata]`** — clé = `image_id`. `default_factory=dict`, absent d'un `project.json` existant → `{}` sans migration, garde `isinstance` classique sur toute entrée désérialisée (même discipline que `Image.list_from_data()`).
- **`DatasetEntryMetadata`** — petite dataclass extensible, contenant pour M098 uniquement `caption: str = ""`. **Règle permanente verrouillée par cette mission** : `DatasetEntryMetadata` est désormais l'unique emplacement prévu pour toute future métadonnée propre à une association Dataset↔Image (source de caption, statut de validation, information de captioning IA, autre métadonnée d'entraînement propre à cette association…) — un besoin futur y ajoute un **champ**, jamais un nouveau dictionnaire parallèle du type `Dataset.caption_sources`. Cette règle est documentée ici pour qu'elle survive à cette mission.
- **Pas de nouvel identifiant `dataset_entry_id`** — `image_id` (déjà unique par construction, `uuid.uuid4()` frais à chaque `add_images()`) suffit comme clé de `entries`, y compris dans le cas vérifié où deux `Image` partagent un même `file_path` après édition manuelle du `project.json` (`test_remove_images_save_failure_preserves_preexisting_duplicate_entries`, `test_dataset_roundtrip.py`). `image_id` n'est jamais remappé par `WorkspaceManager.rename()` (seul `file_path` l'est) — une entrée `entries` clée par `image_id` survit donc à un renommage de projet sans aucun nouveau code de remap.
- **Sémantique de présence, verrouillée** : `image_id` absent de `entries` → aucune caption explicitement définie (fallback M097 vers `training.trigger_word`) ; `entries[image_id]` existant avec `caption == ""` → caption **explicitement vide**, jamais remplacée par le trigger word ; `entries[image_id]` existant avec un texte → caption explicite utilisée telle quelle. La distinction absence/vide est fonctionnellement significative et ne doit jamais être aplatie par un `or`/une vérité simple.
- **`DatasetEntryMetadata`/`Dataset.entries` ne sont pas la forme finale de `DatasetEntry`** — c'est la première matérialisation typée et extensible de l'association Dataset↔Image, sans casser le contrat historique `Dataset.images`. Une vraie entité `DatasetEntry(image + metadata)` (fusionnant la référence à l'image elle-même, pas seulement son `image_id`) ne sera introduite que lorsqu'un besoin supplémentaire réel le justifiera — pas par cette mission.
- **Edge case documenté, non traité** : un `project.json` antérieur à Mission 011 jamais resauvegardé depuis régénère un `image_id` éphémère à chaque chargement (`Image.list_from_data()`) — une entrée `entries` ainsi clée serait alors orpheline jusqu'à la prochaine sauvegarde. Dégradation silencieuse (caption non trouvée, fallback trigger_word), jamais une erreur ; cas jugé trop marginal (~90 missions plus tard) pour justifier un traitement dédié.

## 4. Contrat par couche

1. **`src/domain/dataset.py`** :
   - Nouvelle petite dataclass `DatasetEntryMetadata` : `caption: str = ""`, `to_dict()`/`from_dict()` symétriques.
   - `Dataset` gagne `entries: dict[str, DatasetEntryMetadata] = field(default_factory=dict)`. `to_dict()` sérialise `{"entries": {image_id: metadata.to_dict(), ...}}` ; `from_dict()` lit `data.get("entries")`, filtrant toute entrée dont la clé n'est pas un `str` ou la valeur pas un `dict` (compatibilité défensive, jamais une migration) — absent → `{}`, aucun `project.json` existant affecté.
   - `Dataset.images: list[Image]` **n'est touché à aucun endroit de ce fichier**.
2. **`src/managers/dataset_manager.py`** :
   - `set_caption(image_id: str, caption: str) -> bool` — mirroir exact du contrat idempotent de `LoRAManager.update()` (Mission 047/073) : valeur identique → `False`, aucun `save()`. Une caption explicitement vide (`""`) est une valeur légitime et **crée ou conserve une entrée** dans `entries` (jamais supprimée automatiquement au seul motif que `caption == ""` — seule une image réellement retirée du Dataset entraîne la suppression de son entrée, voir ci-dessous) ; rollback exact de `dataset.entries` sur échec de `save()`.
   - `remove_images()` étendu pour retirer, pour chaque image effectivement supprimée, l'entrée `entries[image_id]` correspondante si elle existe — c'est la **seule** condition de suppression d'une entrée ; retirer une entrée simplement parce qu'une caption a été vidée par l'utilisateur serait incorrect (voir sémantique de présence, §3).
   - `add_images()` gagne un paramètre `detect_caption_sidecars: bool = False` (désactivé par défaut, pour qu'un futur appelant ne déclenche jamais implicitement cette détection sans le décider explicitement). Quand `True` : pour chaque chemin source accepté, si `Path(source).with_suffix(".txt")` existe **à côté de la source d'origine** (jamais la destination copiée), son contenu devient `entries[nouvel image_id] = DatasetEntryMetadata(caption=...)` — le fichier `.txt` lui-même n'est jamais copié ni référencé comme image/fichier du Dataset. Aucune entrée n'est créée si le sidecar est absent (l'absence d'entrée reste significative, §3) ; si le contenu du sidecar est une chaîne vide, l'entrée est tout de même créée avec `caption=""` (caption explicitement vide, distincte de l'absence).
   - `DatasetsPage.import_images()` (import disque) appelle `add_images(..., detect_caption_sidecars=True)`. `DatasetsPage.add_images_from_gallery()` ("Add from Images", galerie Workspace) n'active pas ce paramètre — une image ajoutée depuis la galerie ne reçoit aucune détection automatique de caption, faute d'un contrat de sidecar Workspace établi pour ce flux.
3. **`src/managers/training_manager.py`** : seul `_materialize_concept()` change. Pour chaque image :
   ```python
   metadata = dataset.entries.get(image.image_id)
   caption = metadata.caption if metadata is not None else training.trigger_word
   ```
   **Jamais** `caption or training.trigger_word` — cette forme aplatirait une caption explicitement vide vers le trigger word, ce qui est exactement le bug que cette révision corrige. Un `.txt` est **toujours** écrit pour chaque image, y compris quand `caption == ""` — invariant structurel préservé de Mission 097 (jamais de branche conditionnelle "pas de fichier"), justifié par une vérification directe dans le code réel de la dépendance qu'utilise OneTrainer pour charger ce sidecar (`mgds/pipelineModules/LoadMultipleTexts.py`, installation locale) : un `.txt` absent et un `.txt` présent mais vide produisent tous deux `texts = [""]` — strictement équivalents pour le moteur, donc le choix d'implémentation (toujours écrire le fichier) n'a aucune conséquence sur l'entraînement réel, seulement sur la simplicité du code. Rétrocompatible par construction : tant qu'aucune entrée `entries` n'existe, le comportement Mission 097 exact (trigger_word partout) est reproduit à l'identique. `src/engines/onetrainer_config.py` (format, `__version`, mapping architecture) **n'est pas touché**.
4. **`src/ui/pages/datasets_page.py`** : un panneau caption (un `QTextEdit`) réagissant à la sélection courante de `images_list`, mirroir du patron déjà établi par `LoRAPage` (Mission 047/090) — flag `_caption_dirty` local, bouton "Enregistrer la caption" activé seulement si dirty, confirmation Sauvegarder/Ignorer/Annuler avant de changer d'image sélectionnée si dirty. Indicateur visuel de présence/absence d'une entrée `entries` sur chaque miniature de `images_list` (détail de rendu tranché en implémentation, pas une nouvelle mécanique de sélection) — une entrée avec `caption == ""` compte comme "présente" (caption explicitement vide), distincte de l'absence totale d'entrée. **Aucune nouvelle page** — la gestion reste intégrée à `DatasetsPage`.

## 5. Hors périmètre explicite

Génération de caption par IA/multimodal (dépend d'un futur modèle multimodal/Prompt Assistant, non engagé ici). Toute vraie entité `DatasetEntry(image + metadata)` fusionnant la référence à l'image elle-même — `DatasetEntryMetadata` reste clée par `image_id` à côté de `Dataset.images`, jamais fusionnée avec lui, pour cette mission. Détection de sidecar `.txt` pour le flux "Add from Images" (galerie Workspace) — explicitement exclue, voir §3/§4. Tout système d'export générique multi-moteur — seule la matérialisation OneTrainer déjà existante (Mission 097) est adaptée. Tout changement au modèle d'exécution Training, tout lancement réel d'OneTrainer, tout sous-processus d'entraînement. Toute nouvelle page top-level. Tout second champ de métadonnée par image au-delà de `caption` — `DatasetEntryMetadata` est conçue pour les recevoir plus tard, mais aucun n'est ajouté par cette mission.

## 6. Tests et smoke tests prévus

- **`DatasetManager`** : `set_caption()` idempotence/rollback (mirroir des tests `LoRAManager.update()`), y compris le cas "caption explicitement vide" (entrée conservée, jamais supprimée) ; suppression de l'entrée `entries` sur `remove_images()` (et seulement à ce moment) ; détection du sidecar `.txt` avec `detect_caption_sidecars=True` (présent avec texte / présent mais vide → entrée créée avec `caption=""` / absent → aucune entrée créée) ; confirmation que `add_images_from_gallery()` ne déclenche jamais cette détection ; compatibilité de lecture d'un `project.json` sans clé `entries` (ancien format) → `{}`.
- **`TrainingManager`** : matérialisation avec caption explicite (non vide) sur tout ou partie des images d'un Dataset, avec caption explicitement vide (`.txt` vide généré, jamais remplacé par le trigger word), avec absence totale d'entrée (fallback trigger_word, comportement Mission 097 exact), et un mélange des trois cas dans un même Dataset — confirmation que `onetrainer_config.py`/le format de configuration restent inchangés.
- **`DatasetsPage`** : affichage/édition de la caption de l'image sélectionnée, dirty-state, confirmation de changement de sélection avec caption non sauvegardée, indicateur visuel présence/absence d'entrée (une caption vide comptant comme "présente").
- **Aucun smoke test OneTrainer réel requis** — le format de configuration n'est pas modifié, seule la matérialisation du concept change ; la preuve d'équivalence absent/vide a déjà été établie par lecture directe du code réel de `mgds` (voir §4.3), pas besoin de la revalider par exécution.
- Suite complète (partitionnée + deux suites monoprocessus consécutives, selon la stratégie déjà établie par Mission 097 face à la dette Qt documentée) revalidée, nombre exact confirmé avant clôture.

## 7. Critères de clôture

- `Dataset.entries`/`DatasetEntryMetadata` ajoutés, compatibilité stricte des `project.json` existants démontrée par test (absence de la clé `entries` → `{}`), `Dataset.images` strictement inchangé (aucun test existant modifié pour cette raison).
- `DatasetManager.set_caption()` (avec conservation de l'entrée si caption vide)/suppression d'entrée sur `remove_images()` uniquement/détection sidecar `.txt` scopée à l'import disque implémentés et testés.
- `TrainingManager._materialize_concept()` distingue explicitement absence d'entrée (fallback `trigger_word`) et entrée avec caption vide (`.txt` vide, jamais remplacé) — testé pour les trois cas (absente/vide/explicite) et leur mélange.
- `DatasetsPage` permet de consulter/éditer la caption de chaque image du Dataset actif, avec indicateur visuel et dirty-state cohérents avec les conventions déjà établies (`LoRAPage`).
- Aucun changement à `src/engines/onetrainer_config.py`, aucun lancement d'OneTrainer, aucune nouvelle page, aucun second dictionnaire parallèle de métadonnées par image.
- Suite complète verte, nombre exact confirmé.

## 8. Besoin futur enregistré pendant cet audit, hors périmètre de M098

L'architecte a validé, indépendamment de ce périmètre, le besoin d'associer une **miniature/image d'aperçu à chaque Prompt** (identifier visuellement le contenu/résultat attendu d'un prompt sans l'ouvrir ni lire son texte complet ; idéalement une image générée à partir du prompt utilisable comme miniature). Ce besoin sera enregistré dans `docs/PROJECT_CONTEXT.md` lors de la prochaine régularisation documentaire appropriée — le mécanisme exact reste à auditer plus tard, avec le chantier Prompt Library. **Non implémenté par Mission 098.**

## 9. Validation finale

### 9.1 Relecture du diff complet — conformité au contrat

Le diff intégral des 4 fichiers de production (`src/domain/dataset.py`, `src/managers/dataset_manager.py`, `src/managers/training_manager.py`, `src/ui/pages/datasets_page.py`) a été relu ligne par ligne contre chacun des points verrouillés en section 3/4 :

- `Dataset.images` : **aucune ligne du diff ne le touche** — seul un nouveau champ `entries` est ajouté à côté, `to_dict()`/`from_dict()` étendus additivement.
- `Dataset.entries: dict[str, DatasetEntryMetadata]` est l'unique structure de métadonnées introduite — confirmé qu'aucun `Dataset.captions`, `Dataset.caption_sources` ou tout autre dictionnaire parallèle n'existe où que ce soit dans le diff.
- Fallback caption absente : `metadata = dataset.entries.get(image.image_id); caption = metadata.caption if metadata is not None else training.trigger_word` — jamais un `or`, confirmé dans `training_manager.py`.
- Caption explicitement vide : le même ternaire ci-dessus retourne `""` telle quelle quand `metadata is not None` et `metadata.caption == ""` — jamais retombée sur `trigger_word`.
- Suppression d'image → suppression de l'entrée : `remove_images()` calcule `removed_image_ids` (les images réellement filtrées hors de `dataset.images`) et reconstruit `dataset.entries` en excluant uniquement ces clés — `set_caption()` ne supprime jamais d'entrée, quelle que soit la valeur de caption.
- Sidecar `.txt` : `detect_caption_sidecars` par défaut `False` sur `add_images()` ; seul `DatasetsPage.import_images()` (import disque) passe `True` ; `add_images_from_gallery()` ne le passe jamais (confirmé par lecture directe des deux sites d'appel).

Aucun écart contractuel trouvé.

### 9.2 Smoke test Qt réel (widgets réels, non mockés hors `QMessageBox.exec`)

Script temporaire exécuté dans le scratchpad de session (jamais dans le dépôt), nettoyé après exécution. Widgets réels (`QTextEdit`, `QListWidget`, `QPushButton`) exercés directement ; seul `QMessageBox.exec` est monkeypatché pour répondre déterministiquement (un vrai `.exec()` modal bloquerait indéfiniment en exécution non supervisée) — aucun autre mocking.

**18/18 PASS** : sélection d'une image (panneau activé, caption vide) ; affichage d'une caption existante après sélection ; modification réelle du texte → dirty + bouton activé ; sauvegarde réelle → dirty effacé, caption persistée en Domain ; indicateur présent/absent correct sur les miniatures ; changement d'image avec brouillon non sauvegardé — **Cancel** (brouillon et sélection conservés), **Discard** (brouillon abandonné, nouvelle image chargée, aucune caption fantôme persistée), **Save** (persistance avant changement, puis chargement correct de la nouvelle image) ; caption explicitement vidée puis sauvegardée — entrée conservée (jamais supprimée), caption réellement vide après une resélection ultérieure (pas de résidu de l'ancienne valeur). Aucun crash, aucun hang.

### 9.3 Smoke test filesystem réel (disque temporaire, jamais mocké)

Script temporaire, disque réel, nettoyé après exécution (`shutil.rmtree` en `finally`). **9/9 PASS** : image + sidecar `.txt` importés depuis disque (`detect_caption_sidecars=True`) → caption récupérée verbatim ; image sans sidecar → aucune entrée créée (absence reste significative) ; confirmation que le `.txt` source n'est jamais copié dans le dossier du Dataset et qu'aucune `Image` Domain ne pointe vers un `.txt` ; matérialisation Training sur un Dataset mixte (caption explicite / absente / explicitement vide) → `.txt` respectivement égal à la caption, au `trigger_word`, et vide (jamais le `trigger_word`) ; confirmation qu'aucun module OneTrainer n'a été importé ou appelé.

### 9.4 Deux suites complètes monoprocessus consécutives

Exécutées via `unittest discover -s tests -p "test_*.py"`, aucune instrumentation, aucune intervention humaine :

- Run 1 : **1930/1930, 209.9s, OK**.
- Run 2 : **1930/1930, 212.7s, OK**.

Aucun `STATUS_HEAP_CORRUPTION`, aucune exception Windows fatale, aucune ligne `FAIL:`/`ERROR:`/`FAILED (...)` dans l'un ou l'autre run (vérifié explicitement par grep dédié sur les deux logs complets — les lignes `Failed to copy .../disk full/Access denied` visibles en sortie sont le bruit stderr attendu des tests de chemins d'erreur déjà documentés depuis les missions précédentes, jamais des échecs réels).

### 9.5 Hygiène du dépôt

- `git diff --check` : exit 0 (seuls les avertissements CRLF/LF bénins habituels sur ce dépôt Windows).
- `git status --short` : exactement les 7 fichiers modifiés + `MISSION_098.md` non suivi, rien d'autre.
- `git worktree list` : uniquement le dépôt principal — aucun worktree diagnostique parasite.
- Aucun artefact Graphify (les entrées `graphify-out/` sont des artefacts de build pré-existants, déjà ignorés par Git, sans rapport avec M098) ni OneTrainer dans l'arbre de travail.
- Tous les scripts de smoke test temporaires ont été créés et supprimés du scratchpad de session — aucun n'est jamais entré dans le dépôt.

### 9.6 Fichiers modifiés — liste exacte confirmée

```
src/domain/dataset.py
src/managers/dataset_manager.py
src/managers/training_manager.py
src/ui/pages/datasets_page.py
tests/integration/test_dataset_roundtrip.py
tests/integration/test_datasets_page.py
tests/integration/test_training_roundtrip.py
docs/missions/MISSION_098.md (nouveau)
```

**Aucun entraînement OneTrainer réel n'a été lancé à aucun moment de cette validation.** Critère de validation finale de l'architecte satisfait — prêt pour clôture Git (commit/tag/push) sur validation explicite.

## 10. Clôture Git

- Commit fonctionnel : `a56a46cd6dd9c4ae483f7915f163bb35cdd55f7f` — *Add per-image, per-Dataset captions (DatasetEntryMetadata)*.
- Fichiers commités : `src/domain/dataset.py`, `src/managers/dataset_manager.py`, `src/managers/training_manager.py`, `src/ui/pages/datasets_page.py`, `tests/integration/test_dataset_roundtrip.py`, `tests/integration/test_datasets_page.py`, `tests/integration/test_training_roundtrip.py`, `docs/missions/MISSION_098.md` (nouveau).
- Tag annoté : `v0.2-mission098`, sur ce même commit exact (vérifié via `git rev-parse v0.2-mission098^{commit}`).
- `main` et le tag poussés vers `origin` sans divergence ni commit étranger intercalé.
