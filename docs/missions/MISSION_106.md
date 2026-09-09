# Mission 106 — Rejeter `base_model_source` uniquement quand OneTrainer ne peut certainement pas l'utiliser

> **MISSION CLÔTURÉE — LA VALIDATION EST EN PLACE AU POINT UNIQUE, AUCUNE FORME LÉGITIME BLOQUÉE, AUCUNE FENÊTRE NATIVE PENDANT LES TESTS.** Ce document a d'abord servi de contrat avant implémentation (sections 1-10, inchangées). Voir section 11 pour le résultat réel complet.

## 1. Contexte

L'audit post-Mission 105 (`docs/PROJECT_CONTEXT.md`) a réexaminé la dette IMPORTANTE identifiée avant Mission 105 : `Training.base_model_source` n'est validé nulle part avant qu'un Job réel ne soit créé. Aujourd'hui, un chemin vide, blanc, ou manifestement invalide n'échoue qu'après que `TrainingManager._materialize_concept()` a déjà copié le Dataset et qu'un vrai sous-processus OneTrainer a été lancé (chargement `torch`/venv réel), avec un message générique (`"OneTrainer process exited with code {exit_code}"`, `training_job_runner.py:184`) sans rapport avec la cause réelle — visible seulement en faisant défiler le journal brut stdout/stderr.

Un premier mini-audit a établi le principe directeur, validé par l'architecte : **Toolkit ne doit rejeter que les valeurs dont il peut déterminer avec certitude qu'elles ne peuvent être utilisées par aucune des formes acceptées par OneTrainer.**

Preuve directe, lue dans le code source réel de l'installation OneTrainer (`J:\Programmes\Onetrainer\modules\modelLoader\...`, jamais exécuté) :

- `Training.base_model_source` est déjà documenté dans le Domain (`training.py:23-28`) comme une chaîne opaque pouvant légitimement représenter trois formes : un fichier `.safetensors`/`.ckpt` local, un dossier Diffusers local, ou un identifiant Hugging Face.
- `StableDiffusionModelLoader.load()` (`stableDiffusion/StableDiffusionModelLoader.py:276-317`) — même structure pour Flux (`flux/FluxModelLoader.py:229-268`) et, par la même fabrique `make_fine_tune_model_loader`, pour SDXL — essaie dans l'ordre : format interne (`<base_model_name>/meta.json`), Diffusers (`CLIPTokenizer.from_pretrained(base_model_name, ...)`, qui accepte indifféremment un dossier local existant ou un identifiant Hugging Face Hub), fichier `.safetensors` unique, puis fallback `.ckpt`. Chaque échec est capturé, la stratégie suivante est tentée.
- `TrainConfig.py:968` : la valeur par défaut native de `base_model_name` dans OneTrainer lui-même est `"stable-diffusion-v1-5/stable-diffusion-v1-5"` — un identifiant Hugging Face, pas un chemin local. Ce n'est pas un cas marginal, c'est le comportement idiomatique par défaut d'OneTrainer.

Un `Path.is_file()` ou `Path.exists()` naïf rejetterait à tort un dossier Diffusers valide et l'identifiant Hugging Face par défaut d'OneTrainer — inacceptable au regard du principe directeur ci-dessus.

Une seconde vérification ciblée, read-only, exécutée avec `./.venv/Scripts/python.exe` (l'interpréteur réel de ce projet, Python 3.11 sous Windows), confirme qu'un discriminant simple et non ambigu existe :

| Valeur | `os.path.isabs()` | Comportement attendu |
|---|---|---|
| `C:\models\missing.safetensors` | `True` | Absolu Windows (lettre de lecteur + backslash) |
| `C:/models/missing.safetensors` | `True` | Absolu Windows (lettre de lecteur + slash — `ntpath` normalise les deux séparateurs) |
| `\\server\share\missing.safetensors` | `True` | Absolu Windows (UNC) |
| `stable-diffusion-v1-5/stable-diffusion-v1-5` | `False` | Ne contient ni lettre de lecteur ni préfixe UNC — jamais un chemin absolu Windows |
| `models/model.safetensors` | `False` | Relatif |
| `model.safetensors` | `False` | Relatif |

`os.path.isabs()` (identique à `ntpath.isabs()` et à `pathlib.PureWindowsPath.is_absolute()` sur cette machine — les trois ont été comparés et concordent exactement sur les six valeurs ci-dessus) est **déterministe, sans heuristique de contenu, et ne dépend d'aucune structure interne d'OneTrainer ou de ComfyUI**. Un identifiant Hugging Face ne contient jamais de lettre de lecteur ni de préfixe UNC — aucune ambiguïté possible avec un chemin absolu Windows.

## 2. Objectif

Rejeter, avant toute matérialisation du Dataset ou tout lancement de sous-processus, uniquement les valeurs de `base_model_source` dont Toolkit peut être certain qu'aucune des formes acceptées par OneTrainer ne peut leur correspondre : chaîne vide, chaîne blanche, ou chemin absolu Windows local qui n'existe ni comme fichier ni comme dossier. Ne jamais bloquer un fichier existant, un dossier existant, une chaîne relative, ou un identifiant Hugging Face.

## 3. Mini-audit — décisions retenues

### 3.1 Emplacement du helper partagé

**Décision : `src/utils/base_model_source.py`, même famille que `src/utils/lora_library_path.py` (Mission 104).**

Même raisonnement que Mission 104 (`MISSION_104.md` section 3.1) : une fonction Qt-free, sans état, sans rapport avec un moteur backend particulier — une vérification de forme sur un champ `Training`, pas une résolution de lancement de moteur (`src/engines/` resterait injustifié, comme pour `lora_library_path.py`). `src/utils/` reste l'emplacement neutre sans contrainte de dépendance Blueprint, déjà utilisé pour un besoin structurellement identique.

### 3.2 Contrat du helper

**Décision : une fonction pure, `validate_base_model_source(base_model_source: str) -> None`, et une exception dédiée `InvalidBaseModelSourceError`.**

```
def validate_base_model_source(base_model_source: str) -> None:
    ...
```

- Lève `InvalidBaseModelSourceError` (message français actionnable) si `base_model_source.strip()` est vide.
- Lève `InvalidBaseModelSourceError` si `os.path.isabs(base_model_source.strip())` est vrai **et** que le chemin n'existe ni comme fichier ni comme dossier (`Path(...).is_file()` / `Path(...).is_dir()`).
- Ne lève rien dans tous les autres cas — en particulier une chaîne relative ou un identifiant Hugging Face passent sans aucune vérification d'existence, de réseau, ou de structure.
- Ne touche jamais au disque au-delà d'une vérification d'existence (`is_file()`/`is_dir()`, jamais de lecture de contenu, jamais de création), ne connaît ni Qt ni aucun Manager — testable en isolation complète, même contrat de testabilité que `resolve_lora_library_root()`/`resolve_onetrainer_launch()`.
- Ne retourne pas de valeur normalisée (contrairement à `resolve_lora_library_root() -> Path`) : `base_model_source` n'a besoin d'aucune transformation avant d'être transmis tel quel à `build_training_config()`, seule sa validité est en question.

### 3.3 Site d'intégration — unique

**Décision : appel à `validate_base_model_source()` en tout premier dans `TrainingManager.prepare_onetrainer_config()`, avant même la résolution du Character/Dataset actuellement en tête de méthode.**

Prepare (bouton direct de `TrainingPage`) et Start (auto-Prepare si `_config_stale`, Mission 105) convergent tous deux vers `TrainingManager.prepare_onetrainer_config()` — c'est le seul point où valider sans créer une deuxième voie. `TrainingPage` catche déjà `TrainingPreparationError` aux deux endroits (`prepare_onetrainer_config()` et `start_training()`) depuis Mission 097/105 — réutiliser cette même exception pour le nouvel échec de validation n'exige aucun nouveau branchement UI.

Placer la validation avant la résolution du Dataset (plutôt que seulement avant `_materialize_concept()`) est délibéré : c'est la vérification la moins coûteuse de toute la méthode, elle doit s'exécuter avant tout le reste.

### 3.4 Interaction avec l'invariant Prepare/Start de Mission 105

Aucun changement du contrat `_dirty`/`_config_stale`. Un échec de validation lève `TrainingPreparationError`, capturé exactement comme tout échec existant de `prepare_onetrainer_config()` — `_config_stale` reste inchangé (puisque la préparation n'a pas eu lieu), un nouveau Start retentera logiquement la même préparation tant que `base_model_source` n'a pas été corrigé. Le flux `Start → si dirty, save → si stale, Prepare` (Mission 105) exécute la nouvelle validation exactement une fois, au même endroit que Prepare seul.

## 4. Périmètre exact — fichiers concernés

- `src/utils/base_model_source.py` (nouveau) — `validate_base_model_source()`, `InvalidBaseModelSourceError`.
- `src/managers/training_manager.py` — un seul site d'intégration (section 3.3), aucune autre modification.
- `tests/integration/test_training_roundtrip.py` — tests listés en section 7.
- `docs/missions/MISSION_106.md` (ce document).
- Documentation de clôture (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`) uniquement au moment approprié, jamais mélangée au commit fonctionnel.

**Aucune modification** de `src/ui/pages/training_page.py`, `src/domain/`, `src/engines/onetrainer_config.py`, tout autre fichier `src/engines/`, ni `src/ui/pages/settings_page.py`/Settings. Si l'implémentation démontre qu'un autre fichier fonctionnel est nécessaire, arrêt et rapport avant tout élargissement.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Validation de la compatibilité architecture ↔ checkpoint (nécessiterait de charger le modèle).
- Validation du contenu d'un fichier `.safetensors`/`.ckpt`, ou de la structure d'un dossier Diffusers.
- Toute vérification réseau de l'existence d'un identifiant/repo Hugging Face.
- Ajout ou modification d'un bouton Browse (le Browse actuel — `QFileDialog.getOpenFileName`, fichier unique seulement — ne couvre déjà pas le cas dossier Diffusers ; ce n'est pas résolu par cette mission, voir observation dédiée ci-dessous).
- Toute modification de `TrainingPage`, `onetrainer_config.py`, `TrainingJobRunner`, ou de tout Domain/Engine.
- Gestion automatique ou pré-vérification du backend ComfyUI (sujet distinct, documenté comme besoin futur dans `docs/PROJECT_CONTEXT.md`, non rattaché à cette mission).
- Validation de tout autre champ `Training` (`architecture` est déjà validé par `build_training_config()`, `resolution`/`epochs`/etc. restent hors périmètre).

## 6. Étapes techniques attendues

1. Créer `src/utils/base_model_source.py` : `InvalidBaseModelSourceError(Exception)`, `validate_base_model_source(base_model_source: str) -> None` — lève l'exception si `.strip()` est vide, ou si `os.path.isabs(.strip())` est vrai et que ni `Path(...).is_file()` ni `Path(...).is_dir()` n'est vrai ; ne lève rien et ne fait rien d'autre sinon.
2. `TrainingManager.prepare_onetrainer_config()` : appel à `validate_base_model_source(training.base_model_source)` en tout premier, immédiatement après la résolution de `training = self._find(training_id)` et la vérification `training is None`, avant toute résolution de Character/Dataset. `InvalidBaseModelSourceError` propagée telle quelle (ou reconvertie en `TrainingPreparationError` avec le même message — à trancher au moment de l'implémentation selon ce qui reste le plus simple ; dans les deux cas, `TrainingPage` doit pouvoir la capturer sans aucun changement de son propre code, donc si `InvalidBaseModelSourceError` n'hérite pas déjà de `TrainingPreparationError`, la conversion doit se faire côté `TrainingManager`).
3. Pour une valeur invalide : aucun appel à `_materialize_concept()`, aucune résolution de Character/Dataset, aucune écriture de fichier de configuration, aucun `TrainingJob` créé, aucun sous-processus lancé.

## 7. Tests attendus

`tests/integration/test_training_roundtrip.py` — nouvelle classe ou extension ciblée, sans mock du filesystem réel (fichiers/dossiers temporaires réels comme le reste de la suite) :

1. `""` → `TrainingPreparationError` (ou équivalent), message actionnable français.
2. `"   "` (espaces uniquement) → idem.
3. Chemin absolu Windows local inexistant (`C:\models\missing.safetensors` ou équivalent temporaire réel inexistant) → idem.
4. Fichier absolu local existant (fichier temporaire réel) → accepté, comportement inchangé.
5. Dossier absolu local existant (dossier temporaire réel) → accepté, comportement inchangé — cas de non-régression explicite du dossier Diffusers, celui qu'un `Path.is_file()` naïf aurait cassé.
6. Identifiant Hugging Face (`"stable-diffusion-v1-5/stable-diffusion-v1-5"`) → accepté sans aucun appel réseau, jamais bloqué.
7. Chaîne relative (`"models/model.safetensors"`, `"model.safetensors"`) → jamais rejetée par cette validation, quel que soit son existence réelle sur disque.
8. Pour chaque cas de rejet (1-3) : vérifier qu'aucun dossier concept n'est créé (`_materialize_concept()` jamais atteint), qu'aucun fichier de configuration OneTrainer n'est écrit, qu'aucun `TrainingJob` n'est ajouté à `training.jobs`, qu'aucun `TrainingJobRunner`/sous-processus n'est sollicité.
9. Interaction Mission 105 : formulaire dirty avec `base_model_source` invalide, clic Start → la sauvegarde réussit réellement (`_dirty` devient `False`), puis la validation bloque avant tout Prepare/Job — `_config_stale` reste cohérent avec l'état pré-existant (inchangé par cet échec), formulaire affichant les valeurs bien enregistrées.
10. Non-régression : la suite `test_training_roundtrip.py` existante (dont les 26 tests Mission 105) reste verte sans modification de son propre comportement testé.
11. Suite complète : nombre exact confirmé (2047 + tests nets nouveaux de cette mission), exit 0.

Aucun OneTrainer ni GPU réel dans aucun de ces tests.

## 8. Smoke réel — politique

Aucun besoin de GPU ni de OneTrainer réel pour cette mission — la validation elle-même ne touche à aucun moteur. Un smoke Qt réel isolé (même politique que Missions 101/103/104/105 : Workspace/Character/Dataset/Training temporaires dédiés, jamais l'état réel de la machine) confirmera, avec `TrainingJobRunner` seul remplacé (comme Mission 105) :

1. `base_model_source=""` puis un chemin absolu inexistant → Prepare et Start bloquent tous deux avant tout `_materialize_concept()`/Job, message actionnable affiché, formulaire cohérent.
2. `base_model_source` pointant vers un fichier réel temporaire → Prepare/Start fonctionnent normalement, comportement identique à avant cette mission.
3. `base_model_source` pointant vers un dossier réel temporaire (simulateur de dossier Diffusers) → Prepare/Start fonctionnent normalement — cas qui aurait été cassé par une validation naïve.
4. `base_model_source` avec une valeur non-path type identifiant Hugging Face → Prepare/Start ne sont jamais bloqués par cette validation (l'échec éventuel plus loin dans un vrai OneTrainer reste hors de portée de ce smoke, qui ne lance aucun sous-processus réel).

## 9. Critères de clôture

1. Les étapes de la section 6 sont observées réellement (smoke réel selon la politique de la section 8).
2. Tous les tests de la section 7 passent, suite complète confirmée au nombre exact.
3. Une valeur vide, blanche, ou un chemin absolu Windows local inexistant ne produit, dans aucun cas, de matérialisation de Dataset, d'écriture de configuration, de `TrainingJob`, ni de sous-processus.
4. Un fichier existant, un dossier existant, une chaîne relative, ou un identifiant Hugging Face continuent de se comporter exactement comme avant cette mission — aucune régression.
5. Aucun élément de la section 5 n'a été ajouté.
6. Aucune modification de `src/ui/pages/training_page.py`, `src/domain/`, `src/engines/`, ni `src/ui/pages/settings_page.py`.

## 10. Autorisation

Ce document a servi de contrat avant toute implémentation. Le code n'a été écrit qu'après validation explicite de ce périmètre par l'architecte — voir section 11 pour le résultat réel complet.

## 11. Résultat réel

### 11.1 Implémentation — conforme au périmètre exact

`src/utils/base_model_source.py` créé exactement selon le contrat (section 3.2) : `validate_base_model_source()`/`InvalidBaseModelSourceError`, rejette `.strip()`-vide et tout chemin absolu Windows (`os.path.isabs()`) qui n'existe ni comme fichier ni comme dossier, sans jamais toucher au réseau ni au contenu. `TrainingManager.prepare_onetrainer_config()` appelle ce helper en tout premier, avant toute résolution Character/Dataset, convertissant `InvalidBaseModelSourceError` en `TrainingPreparationError` — `TrainingPage` capture cette exception sans aucune modification de son propre code. `git diff --numstat` confirme : `src/utils/base_model_source.py` (nouveau), `src/managers/training_manager.py` (+13/-1), `tests/integration/test_training_roundtrip.py` (+218/-35) — aucune modification de `src/ui/pages/training_page.py`, `src/domain/`, `src/engines/`, ni `src/ui/pages/settings_page.py`.

**Ajustement découvert et corrigé pendant l'implémentation, hors du helper lui-même** : `Path.is_file()`/`is_dir()` lèvent une `OSError` (`WinError 64`, nom réseau indisponible) pour un hôte UNC inaccessible au lieu de retourner silencieusement `False`, contrairement à un simple fichier local manquant. Corrigé par un `try/except OSError` traitant l'inaccessibilité comme équivalente à l'inexistence — un chemin absolu inatteignable est tout aussi inutilisable par OneTrainer qu'un chemin manquant. Le message d'erreur a été formulé « introuvable ou inaccessible » (et non uniquement « introuvable ») pour rester sémantiquement exact dans les deux cas.

### 11.2 Effet de bord réel sur les fixtures existantes — découvert et corrigé

`os.path.isabs()` traite un chemin de la forme `/models/...` (utilisé comme valeur `base_model_source` factice dans une trentaine de fixtures pré-existantes, dans huit classes de tests distinctes) comme **absolu** sous Windows, même sans lettre de lecteur — confirmé empiriquement, contrairement à l'hypothèse initiale du mini-audit qui n'avait envisagé que les formes `C:\`/`C:/`/UNC comme réellement absolues. Toutes ces fixtures cassaient donc dès l'introduction de la validation, avec 75 erreurs et 1 échec sur la première exécution ciblée. Corrigé uniformément par un remplacement mécanique `"/models/` → `"models/"` dans tout le fichier de test (rendant ces valeurs relatives, catégorie jamais validée par contrat), plus l'ajout explicite d'un `base_model_source` valide au seul test qui ne le fixait jamais (`test_prepare_config_success_shows_the_three_paths_and_starts_no_training`, auparavant appuyé implicitement sur la valeur par défaut `""` du Domain). Aucun changement de comportement de production, aucune intention de test modifiée — uniquement des valeurs de fixture rendues à nouveau valides.

### 11.3 Deux interceptions `QMessageBox.information` latentes depuis Mission 105 — découvertes et corrigées

Deux tests pré-existants de `TrainingPageDirtyStateTest` (`test_prepare_dirty_saves_then_prepares`, `test_prepare_success_clears_config_stale`) appelaient `TrainingPage.prepare_onetrainer_config()` sans jamais mocker `QMessageBox.information` — un gap latent depuis Mission 105 lui-même, jamais manifesté avant que Mission 106 ne s'y attarde. Deux vraies fenêtres natives sont apparues pendant l'exécution automatisée et ont dû être fermées manuellement par l'architecte avant que la cause ne soit identifiée et corrigée. Corrigé strictement côté test (`patch("src.ui.pages.training_page.QMessageBox.information")`, convention M091 déjà utilisée par les tests voisins), sans aucune modification de production. Un balayage exhaustif de tous les appels à `TrainingPage.prepare_onetrainer_config()`/`start_training()` dans le fichier a confirmé l'absence de tout autre site à risque (`start_training()` n'appelle jamais la méthode UI de Prepare, seulement `TrainingManager.prepare_onetrainer_config()` directement — jamais de dialogue de succès sur ce chemin).

### 11.4 Tests

**16 tests ciblés nets nouveaux** (2047 → 2063) : 9 dans `ValidateBaseModelSourceTest` (Qt-free — vide, whitespace, `C:\`/`C:/`/UNC manquants, fichier/dossier existants, chaîne relative, identifiant Hugging Face, aucun accès réseau), 5 dans `TrainingManagerPrepareOnetrainerConfigTest` (rejet avant `_materialize_concept()`, aucun dossier concept créé, aucune configuration écrite, rejet même sans Dataset résolvable, message actionnable), 2 dans `TrainingPageDirtyStateTest` (interaction réelle M105 dirty → Save → validation → arrêt avant tout Job/`TrainingJobRunner`, `_dirty`/`_config_stale` cohérents, configuration existante jamais écrasée par la tentative échouée). `test_training_roundtrip.py` complet **184/184**, suite complète **2063/2063**, `git diff --check` clean — sans aucune fenêtre native, sans aucun OneTrainer/subprocess/GPU réel.

### 11.5 Smoke réel — non nécessaire, conformément à la politique de la section 8

Aucun besoin de GPU ni de OneTrainer réel pour cette mission — confirmé a posteriori : la validation elle-même ne touche à aucun moteur, et les tests automatisés (section 11.4) couvrent déjà chaque forme auditée avec des fichiers/dossiers temporaires réels. Aucun smoke Qt isolé supplémentaire n'a été jugé nécessaire par l'architecte au-delà des tests d'intégration déjà réels (widgets Qt réels, `TrainingManager`/`TrainingPage` réels, seul `TrainingJobRunner` mocké dans les scénarios Start).
