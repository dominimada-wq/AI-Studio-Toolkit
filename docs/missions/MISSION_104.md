# Mission 104 — Sécuriser l'import Training → Central LoRA Library contre un `lora_library_path` vide/blanc

> **MISSION CLÔTURÉE — LES QUATRE SITES D'IMPORT SONT PROTÉGÉS, SMOKE RÉEL ISOLÉ RÉUSSI.** Ce document a d'abord servi de contrat avant implémentation (sections 1-10, inchangées). Voir section 11 pour le résultat réel complet.

## 1. Contexte

L'audit post-Mission 103 (`docs/PROJECT_CONTEXT.md`) a confirmé que le workflow MVP `Images → Dataset/captions → OneTrainer → LoRA → Inference → Images` est fonctionnel de bout en bout sur le chemin heureux, sans blocage structurel. Il a cependant identifié un point IMPORTANT non bloquant : `LoRALibraryManager.import_lora()`/`set_thumbnail()` reçoivent `library_root` sans aucune validation en amont, à quatre sites d'appel UI distincts, répartis sur deux Pages.

Un mini-audit ciblé, validé par l'architecte, a établi précisément le comportement réel :

- `ApplicationSettings.lora_library_path` a un défaut réel non-vide (`Path.home() / "AI Studio Toolkit" / "LoRA Library"`, `application_settings.py:80`) et `from_dict()` corrige déjà un `""` lu sur disque (`application_settings.py:121`) — **mais** `SettingsPage.save_application_settings()` transmet `self.lora_library_path_edit.text()` telle quelle (`settings_page.py:288`), et `ApplicationSettingsManager.update()` accepte un `""` explicite tant que la bibliothèque ne contient encore aucune entrée (`LoRALibraryPathLockedError` ne protège que le cas où elle en contient déjà — `application_settings_manager.py:84-94`). Le champ peut donc rester `""` en mémoire pendant toute une session, en particulier au tout premier usage.
- Vérifié empiriquement (`./.venv/Scripts/python.exe`) : `Path("") / lora_id` résout vers un chemin **relatif**, résolu par rapport au `cwd` du process au moment de l'écriture — `workspace_storage.py:256`, `destination_folder.mkdir(parents=True, exist_ok=True)`, réussit silencieusement puisque le `cwd` est presque toujours inscriptible. Le résultat est un **faux succès complet** : copie réussie, `LoRA` créée, `LORA_LIBRARY_IMPORTED` publié, message de succès affiché — le fichier atterrit hors de tout emplacement voulu par l'utilisateur.
- Une valeur uniquement composée d'espaces (`"   "`) ne s'effondre pas vers le `cwd` lui-même mais crée un sous-dossier littéralement nommé `"   "` sous le `cwd` — tout aussi inattendu, et non couvert par une simple comparaison stricte à `""`.
- **Tous les autres cas limites testés lèvent déjà une erreur correcte**, sans faux succès : chemin inexistant sur un volume valide → auto-créé par `mkdir(parents=True)` (bootstrap volontaire, comportement à préserver) ; chemin pointant vers un fichier existant → `FileExistsError` capturée, `LoRALibraryError` levée (vérifié empiriquement) ; chemin non inscriptible → `PermissionError` capturée, `LoRALibraryError` levée ; échec de copie en cours de route → nettoyage best-effort déjà en place depuis Mission 087, aucune entrée orpheline. Le seul défaut réel est donc circonscrit à la valeur vide/blanche.
- **Quatre sites d'appel atteignent ce chemin sans aucune validation**, dans deux Pages différentes : `LoRAPage.add_to_central_library()` (`lora_page.py:742-754`), `LoRAPage.import_to_library_from_disk()` (`lora_page.py:1536-1543`), `LoRAPage.choose_library_thumbnail()` (`lora_page.py:1628-1631`), `TrainingPage.import_selected_job_to_library()` (`training_page.py:871-876`, Mission 103). Une correction locale à un seul site laisserait les trois autres exposés au même défaut.

## 2. Objectif

Empêcher toute écriture Library relative au `cwd` (ou vers tout emplacement non voulu par l'utilisateur) lorsque `lora_library_path` est vide ou blanc, à tous les points d'entrée UI existants, sans introduire de nouvelle politique de validation pour un chemin non vide et sans modifier `LoRALibraryManager`.

## 3. Mini-audit — décisions retenues

### 3.1 Emplacement du helper partagé

**Décision : `src/utils/lora_library_path.py`, jamais `src/engines/`.**

Le précédent `resolve_onetrainer_launch()` (`src/engines/onetrainer_launch.py`) valide le *pattern* — une fonction Qt-free, sans état, partagée entre plusieurs appelants UI, levant une erreur dédiée avec message actionnable — mais son emplacement dans `src/engines/` est justifié par son propre contenu : il résout la configuration de lancement d'un moteur externe réel (interpréteur venv OneTrainer, script `train_remote.py`). La validation demandée ici ne concerne aucun moteur : c'est une vérification de forme sur un champ `ApplicationSettings` (`lora_library_path`), sans rapport avec un backend d'IA. La reproduire dans `src/engines/` uniquement par analogie serait transposer un pattern sans en vérifier le fondement — explicitement proscrit par les règles permanentes du projet ("ne jamais transposer automatiquement un pattern d'une mission précédente").

Le Blueprint (`docs/blueprint/02_ARCHITECTURE.md:621-645`) définit une règle de dépendance stricte `UI → Managers` uniquement, avec `UI → Services` explicitement **interdit** (`Services` n'est accessible qu'aux `Managers`). `src/services/` (qui liste pourtant `ValidationService` en exemple, `02_ARCHITECTURE.md:332`) est donc structurellement fermé à un appel direct depuis `LoRAPage`/`TrainingPage` sans détour par un Manager — un tel détour introduirait une nouvelle méthode Manager rien que pour relayer un appel Qt-free, complexité non justifiée par la taille réelle du correctif. `src/services/` reste par ailleurs un dossier vide (seul `__init__.py`) dans le dépôt réel, jamais encore utilisé par aucune mission.

`src/utils/` existe déjà dans le dépôt (`src/utils/__init__.py`, vide), déclaré dans la structure officielle (`03_PROJECT_STRUCTURE.md:101`) sans qu'aucune règle de dépendance ni contrainte "jamais connu de l'UI" ne lui soit attachée nulle part dans le Blueprint — contrairement à `Services`. C'est l'emplacement le plus cohérent pour une fonction générique, sans dépendance à aucun Domain/Manager/Qt, directement appelable depuis n'importe quelle UI : exactement le rôle neutre qu'un dossier `utils/` est censé jouer, et le seul des trois candidats sans contrainte architecturale qui l'interdise.

### 3.2 Contrat du helper

**Décision : une fonction pure, `resolve_lora_library_root(lora_library_path: str) -> Path`, et une exception dédiée `LoRALibraryPathError`.**

```
def resolve_lora_library_root(lora_library_path: str) -> Path:
    ...
```

- Rejette `""` et toute valeur dont `.strip()` est vide (couvre à la fois le cas vide et le cas blanc identifiés en section 1) en levant `LoRALibraryPathError` avec un message actionnable, en français (cohérent avec tous les autres messages `QMessageBox` déjà présents dans `LoRAPage`/`TrainingPage`), renvoyant explicitement vers Réglages.
- Pour toute valeur non vide/non blanche : retourne `Path(lora_library_path)` tel quel — **aucune vérification d'existence, de type (fichier/dossier), de permission, ni aucune création de dossier**. Ces responsabilités restent exactement où elles sont déjà correctement assurées aujourd'hui (`WorkspaceStorage.copy_into_workspace()` via `LoRALibraryManager.import_lora()`/`set_thumbnail()`, section 1) — le helper ne fait qu'écarter la seule valeur qui échappe aujourd'hui à tout contrôle.
- Ne touche jamais au disque, ne connaît ni Qt ni aucun Manager — testable en isolation complète, même contrat de testabilité que `resolve_onetrainer_launch()`.

### 3.3 Sites d'intégration — quatre, sans exception

**Décision : appel à `resolve_lora_library_root()` inséré immédiatement avant l'appel `LoRALibraryManager` existant, à chacun des quatre sites, capturant `LoRALibraryPathError` en `QMessageBox.critical` puis `return` — sans réordonner le reste du flux existant (dialogues de sélection de fichier/nom déjà présents restent à leur place actuelle).**

| Site | Fichier:ligne actuelle | Appel Library concerné |
|---|---|---|
| `LoRAPage.add_to_central_library()` | `lora_page.py:742-754` | `import_lora()` |
| `LoRAPage.import_to_library_from_disk()` | `lora_page.py:1536-1543` | `import_lora()` |
| `LoRAPage.choose_library_thumbnail()` | `lora_page.py:1628-1631` | `set_thumbnail()` |
| `TrainingPage.import_selected_job_to_library()` | `training_page.py:871-876` | `import_lora()` |

La ligne `library_root = self.application_settings_manager.settings.lora_library_path` est remplacée, à chacun des quatre sites, par un appel à `resolve_lora_library_root(...)` dans un bloc `try`/`except LoRALibraryPathError`. Toute logique déjà exécutée avant ce point à chacun de ces sites (dialogue de sélection de fichier, `QInputDialog.getText()` pour le nom, sauvegarde d'un brouillon de métadonnées dirty dans `add_to_central_library()`) reste strictement inchangée — le nouveau garde-fou ne bloque que l'appel Library lui-même, jamais une opération qui lui est indépendante.

### 3.4 Comportement pour un chemin non vide — aucun changement de politique

**Décision : `resolve_lora_library_root()` ne remplace ni ne double aucune validation filesystem existante.**

Un chemin inexistant-mais-créable continue d'être silencieusement créé par `mkdir(parents=True, exist_ok=True)` dans `WorkspaceStorage.copy_into_workspace()`, comme aujourd'hui (bootstrap volontaire, section 1). Un chemin pointant vers un fichier, non inscriptible, ou pour lequel la copie échoue en cours de route continue de lever `LoRALibraryError` exactement comme aujourd'hui, sans changement de message ni de comportement. Cette mission n'introduit aucune nouvelle règle de validation au-delà du seul cas vide/blanc.

## 4. Périmètre exact — fichiers concernés

- `src/utils/lora_library_path.py` (nouveau) — `resolve_lora_library_root()`, `LoRALibraryPathError`.
- `src/ui/pages/lora_page.py` — trois sites d'intégration (section 3.3), aucune autre modification.
- `src/ui/pages/training_page.py` — un site d'intégration (section 3.3), aucune autre modification.
- Fichiers de tests listés en section 7.

**Aucune modification** de `src/domain/`, `src/managers/lora_library_manager.py`, `src/managers/application_settings_manager.py`, `src/ui/pages/inference_page.py`, `src/ui/pages/settings_page.py`, ni d'aucun fichier hors de cette liste.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Validation générale de tout autre champ `ApplicationSettings` (`comfyui_path`, `onetrainer_path`, `comfyui_lora_expose_path`, etc.).
- Folder picker, ou toute modification de `SettingsPage` au-delà de ce qui est strictement nécessaire (aucune modification n'est en réalité prévue de ce fichier).
- Verrouillage supplémentaire de `ApplicationSettingsManager` (le verrou `LoRALibraryPathLockedError` existant reste inchangé).
- Dirty-state du formulaire de paramètres Training.
- Validation `base_model_source`/`architecture` avant lancement d'un entraînement.
- Lancement automatique du backend ComfyUI.
- Fooocus, Stable Diffusion WebUI Forge.
- Toute modification de `LoRALibraryManager` ou de tout fichier `src/domain/`.
- Tout nouvel entraînement OneTrainer, toute interaction GPU/ComfyUI réelle pour le smoke.

## 6. Étapes techniques attendues

1. Créer `src/utils/lora_library_path.py` : `LoRALibraryPathError(Exception)`, `resolve_lora_library_root(lora_library_path: str) -> Path` — rejette `""` et toute valeur dont `.strip()` est vide, retourne `Path(lora_library_path)` sinon, aucune autre vérification, aucune création de dossier.
2. `LoRAPage.add_to_central_library()` : appel à `resolve_lora_library_root()` avant `import_lora()`, `LoRALibraryPathError` → `QMessageBox.critical` → `return`, sans effet sur la persistance de métadonnées déjà exécutée plus haut dans la méthode.
3. `LoRAPage.import_to_library_from_disk()` : même intégration avant `import_lora()`.
4. `LoRAPage.choose_library_thumbnail()` : même intégration avant `set_thumbnail()`.
5. `TrainingPage.import_selected_job_to_library()` : même intégration avant `import_lora()`, sans modification de la séquence non compensatoire de Mission 103 (section 3.5 de `MISSION_103.md`) qui reste inchangée pour tout ce qui suit un `library_root` valide.
6. Pour un chemin vide/blanc, à chacun des quatre sites : aucun dossier/fichier créé, aucun appel `import_lora()`/`set_thumbnail()`, aucun événement `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_UPDATED` publié, aucun message de succès affiché — uniquement le message d'erreur actionnable renvoyant vers Réglages.

## 7. Tests attendus

- `tests/integration/test_lora_library_path.py` (nouveau fichier, même convention que `tests/integration/test_onetrainer_launch.py`) — test direct du helper Qt-free, sans UI :
  1. `""` → lève `LoRALibraryPathError`.
  2. `"   "` (espaces uniquement) → lève `LoRALibraryPathError`.
  3. valeur valide non vide → retourne un `Path` exploitable, égal à `Path(lora_library_path)`.
  4. chemin syntaxiquement valide mais inexistant sur disque → accepté (retourne un `Path`, ne lève rien) — non-régression explicite du bootstrap volontaire.
  5. le helper ne crée aucun fichier ni dossier sur disque, dans aucun des cas ci-dessus.
- `tests/integration/test_lora_roundtrip.py` — extension de `LoRAPageAddToCentralLibraryTest` et de `LoRAPageCentralLibraryTabTest` (ou nouvelle classe dédiée si plus clair à l'implémentation) :
  1. `lora_library_path=""` sur `add_to_central_library()` → aucun appel à `import_lora()`, aucune entrée créée dans la Bibliothèque, message d'erreur affiché, aucun `QMessageBox.information` de succès.
  2. Même scénario pour `import_to_library_from_disk()`.
  3. Même scénario pour `choose_library_thumbnail()` (aucun appel à `set_thumbnail()`).
  4. `lora_library_path` valide (répertoire temporaire isolé) → non-régression complète des trois flux existants, import réel toujours fonctionnel.
  5. Vérification explicite qu'aucun fichier n'apparaît sous le `cwd` du process de test après une tentative avec `lora_library_path=""`.
- `tests/integration/test_training_roundtrip.py` — extension de `TrainingPageJobImportTest` :
  1. `lora_library_path=""` sur `import_selected_job_to_library()` → aucun appel à `import_lora()`, `Job.imported_lora_id` reste vide, message d'erreur affiché, aucun succès annoncé.
  2. Non-régression du parcours complet M103 avec un `lora_library_path` valide (les 11 tests existants de `TrainingPageJobImportTest` restent verts sans modification).
- Non-régression explicite des cas d'erreur filesystem déjà couverts (`LoRALibraryManagerImportTest`, `LoRALibraryManagerSetThumbnailTest` dans `tests/integration/test_lora_library_roundtrip.py`) — chemin non-répertoire, permission refusée, échec de copie : comportement et messages inchangés.
- Suite complète : nombre exact confirmé (2008 + tests nets nouveaux de cette mission), exit 0.

## 8. Smoke réel — politique

Aucun besoin de ComfyUI, GPU, ni OneTrainer. Smoke Qt réel, entièrement isolé (Workspace/Bibliothèque/registre temporaires dédiés, jamais le registre ni la Bibliothèque réels de la machine — cf. l'incident d'isolation de Mission 103, `MISSION_103.md` section 11.3, à ne pas reproduire) :

1. Configurer temporairement `lora_library_path=""`, déclencher au moins un chemin `LoRAPage` (ex. `import_to_library_from_disk()`) et le chemin `TrainingPage.import_selected_job_to_library()` (réutilisation du même montage que le smoke de Mission 103 — Job réussi avec un `.safetensors` réel copié) → confirmer qu'aucune écriture n'apparaît ni sous le `cwd` réel du process ni ailleurs, et que le message d'erreur attendu s'affiche.
2. Répéter avec `lora_library_path="   "` (espaces) → même résultat.
3. Reconfigurer un `lora_library_path` temporaire valide (répertoire isolé) → confirmer qu'un import réel fonctionne toujours de bout en bout (au moins un des quatre sites), sans régression du comportement établi par Mission 103.

Tous les artefacts temporaires supprimés après vérification.

## 9. Critères de clôture

1. Les six étapes de la section 6 sont observées réellement (smoke réel selon la politique de la section 8).
2. Tous les tests de la section 7 passent, suite complète confirmée au nombre exact.
3. Un chemin vide ou blanc ne produit, à aucun des quatre sites, ni écriture disque, ni appel `import_lora()`/`set_thumbnail()`, ni événement `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_UPDATED`, ni message de succès.
4. Un chemin non vide continue de se comporter exactement comme avant cette mission (aucune nouvelle politique de validation filesystem).
5. Aucun élément de la section 5 n'a été ajouté.
6. Aucune modification de `src/domain/`, de `LoRALibraryManager`, de `ApplicationSettingsManager`, ni de `InferencePage`/`SettingsPage`.

## 10. Autorisation

Ce document a servi de contrat avant toute implémentation. Le code n'a été écrit qu'après validation explicite de ce périmètre par l'architecte — voir section 11 pour le résultat réel complet.

## 11. Résultat réel

### 11.1 Implémentation — conforme au périmètre exact

`src/utils/lora_library_path.py` créé avec `LoRALibraryPathError` et `resolve_lora_library_root()` exactement selon le contrat (sections 3.1/3.2) : Qt-free, sans effet de bord, ne crée jamais de dossier, rejette `""` et toute valeur `.strip()`-vide, retourne `Path(lora_library_path)` inchangé sinon. Les quatre sites identifiés (section 3.3) appellent tous le helper immédiatement avant leur appel `LoRALibraryManager` existant, capturant `LoRALibraryPathError` en `QMessageBox.critical` puis `return`, sans réordonner aucune autre logique déjà présente à ces sites. Confirmé par `git diff --stat` : `src/utils/lora_library_path.py` (nouveau), `src/ui/pages/lora_page.py` (+25/-4), `src/ui/pages/training_page.py` (+9/-1) — aucune modification de `src/domain/`, `LoRALibraryManager`, `ApplicationSettingsManager`, `SettingsPage`, ni `InferencePage`.

### 11.2 Tests

**13 tests ciblés nets nouveaux** (2008 → 2021) : 5 dans `tests/integration/test_lora_library_path.py` (test direct du helper Qt-free — `""`, `"   "`, valeur valide, chemin inexistant-mais-créable toujours accepté, aucune écriture disque par le helper lui-même), 6 dans `tests/integration/test_lora_roundtrip.py` (deux tests par site, `LoRAPage.add_to_central_library()`/`import_to_library_from_disk()`/`choose_library_thumbnail()` — le cas de ce dernier site exercé via un `ApplicationSettingsManager` délibérément construit sans le verrou de Mission 087, puisque ce verrou empêche structurellement d'atteindre un `lora_library_path` vide avec une entrée Library déjà existante dans le câblage réel de `main_window.py`), 2 dans `tests/integration/test_training_roundtrip.py` (`TrainingPageJobImportTest`, site M103). Chaque test vérifie : aucun appel `import_lora()`/`set_thumbnail()`, aucun événement `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_UPDATED`, aucun message de succès, message d'erreur contenant "pas configurée", registre Library inchangé, et absence de toute écriture parasite sous le `cwd` du process de test. Non-régression confirmée : `LoRALibraryManagerImportTest`/`LoRALibraryManagerSetThumbnailTest` (erreurs filesystem existantes) **81/81**, suite complète **2021/2021**, exit 0.

### 11.3 Smoke réel — isolé, aucun ComfyUI/GPU/OneTrainer

Script autonome exécuté par Claude (scratchpad, jamais commité), depuis un répertoire de travail sandbox dédié (jamais le dépôt) par précaution supplémentaire sur la vérification "aucune écriture relative au `cwd`". Isolation complète : Workspace/Bibliothèque/registre applicatif temporaires dédiés, jamais le registre ni la Bibliothèque LoRA réels de la machine. Phases `lora_library_path=""` puis `"   "` : aux deux sites vérifiés (`LoRAPage.add_to_central_library()`, `TrainingPage.import_selected_job_to_library()`) — `import_lora()` jamais appelé, aucun événement `LORA_LIBRARY_IMPORTED` publié, aucun message de succès, message d'erreur actionnable affiché, registre Library resté vide, listing du `cwd` réel strictement identique avant/après. Phase racine temporaire valide : `import_to_library_from_disk()` et `import_selected_job_to_library()` créent chacun une entrée réelle et distincte, fichiers physiquement présents sous la racine temporaire, `TrainingJob.imported_lora_id` réellement persisté — comportement historique intégralement préservé. **24/24 vérifications réussies**, exit 0. Tous les artefacts temporaires supprimés après vérification.

## 12. Clôture Git

- Commit fonctionnel : `e01aa81145656a4d670bf5ac4f11a85a9ddbda4e` — *Guard Training/LoRA library imports against a blank lora_library_path* (`src/utils/lora_library_path.py`, `src/ui/pages/lora_page.py`, `src/ui/pages/training_page.py`, `tests/integration/test_lora_library_path.py`, `tests/integration/test_lora_roundtrip.py`, `tests/integration/test_training_roundtrip.py`, `docs/missions/MISSION_104.md`, `docs/PROJECT_CONTEXT.md`).
- Tag annoté : `v0.2-mission104`, sur ce même commit exact (vérifié via `git rev-list -n 1 v0.2-mission104`).
- `main` et le tag poussés vers `origin` sans divergence ni commit étranger intercalé (`HEAD == origin/main == e01aa81145656a4d670bf5ac4f11a85a9ddbda4e`, `git rev-list --left-right --count origin/main...main` → `0 0`).
- GitHub Release `v0.2-mission104` **publiée** — confirmée par l'architecte du projet.
- Validation finale à la clôture : suite complète **2021/2021**, exit 0 ; non-régression filesystem **81/81** ; smoke réel isolé réussi de bout en bout (voir section 11.3).
- Régularisation documentaire post-Release effectuée dans un commit distinct (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`, ce document) — ne déplace pas le tag `v0.2-mission104`, qui continue de cibler exclusivement le commit fonctionnel ci-dessus.
