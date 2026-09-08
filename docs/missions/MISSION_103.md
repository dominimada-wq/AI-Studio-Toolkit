# Mission 103 — Résultat Training → Central LoRA Library, sans manipulation de fichier

> **MISSION CLÔTURÉE — IMPORT TRAINING → CENTRAL LORA LIBRARY VALIDÉ DE BOUT EN BOUT, SMOKE RÉEL RÉUSSI.** Ce document a d'abord servi de contrat avant implémentation (sections 1-10, inchangées). Voir section 11 pour le résultat réel complet, incluant l'incident d'isolation découvert et corrigé en cours de route. Le commit/tag de clôture Git sera consigné dans la régularisation documentaire post-Release, suivant le précédent Mission 100 (non-auto-référence).

## 1. Contexte

L'audit post-Mission 102 (`docs/PROJECT_CONTEXT.md`) a identifié un unique blocage réel restant sur la chaîne `Images → Dataset/captions → OneTrainer → LoRA → Inference → Images` : un `TrainingJob` réussi produit un `.safetensors` réel (`final_output_path`, vérifié présent sur disque au moment du succès — `src/ui/training_job_runner.py:187-188`), mais rien ne relie ce résultat à la Bibliothèque LoRA centrale depuis l'interface. `TrainingPage` affiche le chemin une seule fois, dans une `QMessageBox.information()` transitoire (`training_page.py:648-653`), sans historique consultable ensuite. Le seul chemin actuel pour importer ce LoRA est l'import générique "depuis le disque" (Mission 092), qui exige de connaître et de retrouver manuellement le chemin interne du Job (`.../trainings/<id>/jobs/<id>/output/lora.safetensors`) — un ouverture manuelle de `project.json` ou une exploration à l'aveugle de l'arborescence du Workspace.

Le champ `TrainingJob.imported_lora_id` existe déjà dans le Domain depuis Mission 100, avec un commentaire explicite dans le code source : *"Reserved for Mission 101 (Central LoRA Library import) — never populated by Mission 100"* (`training_job.py:49-51`). Il n'a jamais été écrit par aucun code de production.

Un mini-audit ciblé, validé par l'architecte, a confirmé que l'architecture Domain/Manager existante (`Training.jobs`, `TrainingJob.final_output_path`/`imported_lora_id`, `LoRALibraryManager.import_lora()`, `LORA_LIBRARY_IMPORTED`) est **déjà entièrement suffisante** — aucune nouvelle collection d'historique, aucun nouveau mécanisme physique de stockage LoRA.

## 2. Objectif

Permettre à l'utilisateur de retrouver, depuis `TrainingPage`, le résultat de n'importe quel `TrainingJob` du `Training` sélectionné et de l'importer dans la Bibliothèque LoRA centrale en un geste — sans jamais passer par l'Explorateur Windows ni éditer `project.json` — puis de le voir immédiatement disponible dans le sélecteur d'Inference introduit par Mission 102, sans redémarrage.

## 3. Mini-audit — décisions retenues

### 3.1 Architecture réutilisée — aucun nouveau Domain

**Décision : réutilisation stricte de `Training.jobs`, `TrainingJob.final_output_path`/`imported_lora_id`, `LoRALibraryManager.import_lora()` et `LORA_LIBRARY_IMPORTED`. Aucune nouvelle collection, aucun nouveau champ Domain, aucun nouveau mécanisme physique de copie de fichier.**

`TrainingManager.active_training` (property, `training_manager.py:244-248`) expose déjà `.jobs` du `Training` sélectionné, dans l'ordre de création, persistés dans `project.json` exactement comme toute autre collection imbriquée (filtrage défensif `isinstance(j, dict)` déjà en place, `training.py:111-115`) — les Jobs survivent déjà à un redémarrage sans aucun changement de stockage. Une UI minimale se contente de lire cette liste ; aucune nouvelle méthode Manager de lecture n'est nécessaire.

`LoRALibraryManager.import_lora(name, file_paths, library_root, thumbnail_path=None, ...)` (`lora_library_manager.py:144-249`) est directement réutilisable : `library_root` est déjà résolu ailleurs via `application_settings_manager.settings.lora_library_path` (précédent `lora_page.py:1536`) ; aucun champ de scope/association n'existe sur `LoRA` (registre applicatif indépendant de tout Workspace/Character, confirmé à l'audit) ; `thumbnail_path` reste optionnel comme aujourd'hui. `TrainingPage` reçoit déjà `application_settings_manager` en dépendance — seul `lora_library_manager` manque, exactement comme `InferencePage` l'a gagné en Mission 102.

### 3.2 UI Training — représentation minimale des Jobs, jamais un historique avancé

**Décision : une petite liste des Jobs du `Training` sélectionné, ajoutée sous les contrôles déjà présents (`job_state_label`/`job_log_view`), jamais un tableau riche, un log viewer ou un dashboard de monitoring.**

Pour chaque Job : date/heure (`created_at`), état (`state`), et une action contextuelle liée au résultat/import (section 3.3) — rien de plus. Le `job_log_view` existant reste l'unique surface de suivi temps réel d'un Job actif ; cette nouvelle liste ne duplique jamais ce rôle. Rafraîchie au même point d'entrée déjà existant que `_refresh_job_controls()` (appelé après `on_training_selection_changed`, `create_job`, `_on_job_started`, `_on_job_finished`) — aucun nouvel abonnement `EventBus` n'est nécessaire pour son propre rafraîchissement : ni `TRAINING_JOB_CREATED` ni `TRAINING_JOB_STATE_CHANGED` ne sont aujourd'hui consommés par aucune UI (vérifié à l'audit), cette page reste la seule consommatrice de ses propres Jobs.

### 3.3 États d'import — quatre cas distincts, jamais confondus

**Décision : distinction explicite au niveau UI entre quatre situations, calculée à chaque rafraîchissement à partir de `TrainingJob.state`/`final_output_path`/`imported_lora_id` et d'une relecture fraîche de `lora_library_manager.get(imported_lora_id)` — jamais un état mis en cache.**

| État | Condition | Affichage/action |
|---|---|---|
| **Jamais importé** | `state == "succeeded"` et `imported_lora_id == ""` | Action **"Importer dans la Bibliothèque"** |
| **Importé, entrée Library toujours présente** | `imported_lora_id != ""` et `lora_library_manager.get(imported_lora_id)` retourne une entrée réelle | Statut **"Importé"** (nom de l'entrée affiché) ; pas d'action d'import — un second import silencieux est impossible par construction (aucun bouton actionnable) |
| **Importé puis supprimé de la Library** | `imported_lora_id != ""` et `lora_library_manager.get(imported_lora_id)` retourne `None` | Statut explicite **"LoRA supprimé — Réimporter"** ; action de réimport réautorisée si `final_output_path` existe encore (jamais présenté comme "jamais importé") |
| **Output disparu** | `state == "succeeded"` et `Path(final_output_path).is_file()` faux au moment de l'affichage/du clic | Statut **"Fichier introuvable"**, aucune action d'import proposée, aucune tentative de copie |

Un Job `failed`/`cancelled`/`unknown` n'affiche jamais d'action d'import — seul `succeeded` avec un fichier réellement vérifié présent au moment du clic (revérification `is_file()` juste avant l'appel à `import_lora()`, jamais seulement une confiance en la valeur stockée) autorise l'import.

### 3.4 `imported_lora_id` — source de vérité unique

**Décision : nouvelle méthode `TrainingManager.set_job_imported_lora_id(job_id, lora_id)`, dédiée, suivant exactement le même contrat idempotent/rollback que `update_job_state()` — jamais une deuxième propriété de suivi, jamais un paramètre supplémentaire ajouté à `update_job_state()` lui-même (concern distinct : liaison Library, pas cycle de vie d'exécution).**

Appelée **uniquement** après le retour réussi de `import_lora()` — jamais avant, jamais en cas d'exception. Persiste `job.imported_lora_id = lora_id` via `self._workspace_manager.save()`, avec rollback en mémoire si `save()` échoue (identique à `update_job_state()`), idempotence stricte (même valeur → `False`, aucun `save()`, aucun événement).

**Pas de nouvel événement `EventBus`.** `LORA_LIBRARY_IMPORTED` (déjà publié par `import_lora()` lui-même) couvre déjà la seule information qu'un autre composant a réellement besoin de connaître — la création réelle du LoRA — et déclenche déjà le rafraîchissement d'Inference (section 3.7). L'association Job → `lora_id`, elle, n'intéresse que `TrainingPage`, qui appelle `set_job_imported_lora_id()` elle-même et peut donc rafraîchir sa propre liste de Jobs par un simple appel direct juste après (même convention que `create_job()`/`update_job_state()`, déjà suivies d'un rafraîchissement local explicite dans cette même page, jamais d'un aller-retour par l'EventBus vers soi-même). Aucun consommateur concret n'a été identifié pour un événement dédié — en ajouter un serait du scaffolding anticipé sans consommateur actuel, explicitement proscrit par les règles permanentes du projet.

Ce champ n'est **jamais** effacé automatiquement (y compris quand l'entrée Library associée est supprimée, section 3.3) — il reste une trace historique jusqu'à ce qu'un nouvel import réussi le remplace explicitement.

### 3.5 Cas d'échec contractuel — `import_lora()` réussit, persistance de `imported_lora_id` échoue

**Décision : aucune nouvelle infrastructure transactionnelle. Séquence stricte à deux étapes, chacune avec sa propre gestion d'erreur, et un message UI qui ne présente jamais un succès complet en cas d'échec de la seconde étape.**

`LoRALibraryManager` et `WorkspaceManager` (`project.json`) sont deux backends de persistance indépendants ; aucun mécanisme transactionnel commun n'existe et n'en sera créé pour cette mission. Séquence retenue dans `TrainingPage` :

1. Appel à `lora_library_manager.import_lora(...)`. Si `LoRALibraryError` est levée, rien n'a changé côté Job — comportement déjà établi, message d'erreur affiché tel quel, aucun appel à l'étape 2.
2. Si `import_lora()` réussit, l'entrée Library est **réellement créée** — `LORA_LIBRARY_IMPORTED` est déjà publié à ce stade par `LoRALibraryManager` lui-même, donc le LoRA est immédiatement réel et utilisable (visible dans le sélecteur Inference dès cet instant, indépendamment de la suite — un LoRA correctement importé ne doit jamais être caché à l'utilisateur à cause d'un problème de bookkeeping séparé).
3. Appel à `training_manager.set_job_imported_lora_id(job.job_id, lora.lora_id)`. Si `WorkspaceManagerError` est levée (rollback interne déjà appliqué par la méthode, section 3.4), **l'UI n'affiche jamais le message de succès normal**. Un message distinct (`QMessageBox.warning`, jamais `.information`) informe explicitement : le LoRA a été importé avec succès dans la Bibliothèque sous tel nom, mais l'association avec ce Job n'a pas pu être enregistrée dans le projet (message d'erreur réel affiché tel quel) ; **le Job réaffichera "Jamais importé" au prochain rafraîchissement**, et une nouvelle tentative d'import créera une **entrée Library distincte** (`import_lora()` ne déduplique jamais par hash, comportement déjà documenté et assumé depuis Mission 087) — l'utilisateur est explicitement prévenu de ce risque de doublon dans ce même message, avant de décider de retenter ou non.

Ce comportement satisfait la contrainte posée : jamais de succès silencieux annoncé à tort, jamais de doublon créé sans avertissement explicite — sans construire de compensation automatique (pas de suppression automatique de l'entrée Library fraîchement créée, qui introduirait elle-même un nouveau risque d'échec en cascade).

### 3.6 Nom du LoRA importé

**Décision : réutilisation stricte du `QInputDialog.getText()` déjà utilisé par `LoRAPage.import_to_library_from_disk()` (Mission 092, `lora_page.py:1531`), pré-rempli avec `training.name`, toujours éditable.**

Aucune nouvelle convention de nommage globale. Comme pour l'import depuis le disque, aucune métadonnée (engine/architecture/trigger_word/version) n'est demandée à l'import — complétable ensuite via le formulaire d'édition déjà existant de `LoRAPage` (Mission 090). Thumbnail facultative comme aujourd'hui (`thumbnail_path=None`).

### 3.7 Inference — zéro nouveau code

**Décision : aucune modification de `src/ui/pages/inference_page.py` ni de son abonnement `EventBus` dans `main_window.py`.**

`InferencePage.refresh_lora_selector` est déjà abonné à `LORA_LIBRARY_IMPORTED` depuis Mission 102. Un import réussi depuis `TrainingPage` publie ce même événement via le même `LoRALibraryManager` partagé — le nouveau LoRA apparaît donc déjà, automatiquement, dans le sélecteur d'Inference, sans redémarrage. Vérifié par test et par smoke réel (sections 7 et 8), jamais supposé.

## 4. Périmètre exact — fichiers concernés

- `src/managers/training_manager.py` — nouvelle méthode `set_job_imported_lora_id(job_id, lora_id)` (contrat idempotent/rollback identique à `update_job_state()`), aucun nouvel événement.
- `src/ui/pages/training_page.py` — nouvelle dépendance constructeur `lora_library_manager` ; petite liste des Jobs du Training sélectionné avec les quatre états de la section 3.3 ; action d'import appelant `import_lora()` puis `set_job_imported_lora_id()` selon la séquence de la section 3.5 ; réutilisation de `QInputDialog.getText()` pour le nom.
- `src/ui/main_window.py` — passage de la nouvelle dépendance à `TrainingPage(...)`.
- Fichiers de tests listés en section 7.

**Aucune modification** de `src/domain/` (tous les champs nécessaires existent déjà), de `src/managers/lora_library_manager.py` (réutilisé tel quel), de `src/ui/pages/inference_page.py`, ni de `src/ui/main_window.py` au-delà du passage de dépendance ci-dessus.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Historique Training avancé (filtres, recherche, pagination).
- Consultation détaillée des logs d'anciens Jobs (le `job_log_view` existant reste réservé au Job actif).
- Relance/retry d'un Job depuis l'historique.
- Suppression de Jobs.
- Import automatique sans action utilisateur explicite.
- Tout nouvel entraînement OneTrainer réel pour cette mission, y compris pour le smoke.
- Réglages OneTrainer avancés, exposition Basic/Advanced/Presets.
- Lancement automatique du backend ComfyUI.
- Réorganisation de `SettingsPage`, folder pickers.
- Amélioration UX de l'import des sidecars `.txt` de caption.
- Fooocus, Stable Diffusion WebUI Forge, abstraction multi-engine.
- Sélection/pondération de plusieurs LoRA simultanés (stacking).
- Toute modification du code livré par Mission 102.

## 6. Étapes techniques attendues

1. `TrainingManager.set_job_imported_lora_id(job_id, lora_id)` : idempotent, rollback sur échec de `save()`, aucun événement publié.
2. `TrainingPage` reçoit `lora_library_manager` en dépendance constructeur.
3. Une liste des Jobs du Training sélectionné est construite/rafraîchie au même point d'entrée que `_refresh_job_controls()` — date/heure, état, action contextuelle selon les quatre états de la section 3.3.
4. L'action d'import revérifie `Path(final_output_path).is_file()` juste avant d'appeler `import_lora()` — jamais une confiance aveugle en la valeur stockée.
5. Le nom est demandé via `QInputDialog.getText()`, pré-rempli avec `training.name`, éditable ; annulation possible sans effet.
6. Séquence stricte : `import_lora()` puis, seulement si elle réussit, `set_job_imported_lora_id()` — comportement d'échec de chaque étape conforme à la section 3.5.
7. Un Job déjà importé avec une entrée Library toujours existante n'affiche plus d'action d'import (pas de double import silencieux possible).
8. Un Job dont l'entrée Library importée a été supprimée affiche "LoRA supprimé — Réimporter" et autorise un nouvel import si le fichier source existe encore.
9. Un import réussi rend le LoRA immédiatement sélectionnable dans `InferencePage`, sans redémarrage, sans aucune modification de son code.

## 7. Tests attendus

- `tests/integration/test_training_roundtrip.py` (nouvelle classe, ex. `TrainingManagerImportJobToLibraryTest`, même convention que `TrainingManagerCreateJobTest`/`TrainingManagerUpdateJobStateTest`) :
  1. `set_job_imported_lora_id()` persiste réellement `imported_lora_id`, idempotent (même valeur → `False`, aucun `save()`, aucun événement) ;
  2. rollback en mémoire si `save()` échoue ;
  3. round-trip après rechargement du projet (`from_dict`/`to_dict` déjà couverts, vérifier l'intégration bout en bout via `WorkspaceStorage`).
- `tests/integration/test_training_page.py` (ou fichier équivalent découvert à l'implémentation) :
  1. affichage de plusieurs Jobs persistés d'un même Training, dans l'ordre attendu ;
  2. un Job `succeeded` avec `final_output_path` valide affiche l'action d'import ; `failed`/`cancelled`/`unknown` ne l'affichent jamais ;
  3. `final_output_path` pointant vers un fichier disparu → état "Fichier introuvable", aucune tentative de copie ;
  4. import réel via `lora_library_manager.import_lora()` (mocké ou réel selon le fixture retenu à l'implémentation) → entrée Library créée, `imported_lora_id` persisté ;
  5. double import empêché tant que l'entrée Library existe ;
  6. entrée Library supprimée puis rafraîchissement → état "LoRA supprimé — Réimporter", réimport réel possible ;
  7. échec de `import_lora()` (mocké `LoRALibraryError`) → Job strictement inchangé, aucun appel à `set_job_imported_lora_id()` ;
  8. échec de `set_job_imported_lora_id()` après succès de `import_lora()` (mocké `WorkspaceManagerError`) → message distinct de la section 3.5, Job réaffiche "Jamais importé" au rafraîchissement suivant, entrée Library réellement présente et non supprimée automatiquement ;
  9. après un import réussi, la liste des Jobs reflète immédiatement le nouveau statut "Importé" par le rafraîchissement local déjà appelé après `set_job_imported_lora_id()` — aucun abonnement `EventBus` supplémentaire n'est nécessaire pour ce cas (`TrainingPage` connaît déjà le résultat de son propre appel).
- Non-régression : suite complète existante (1991+ tests), aucune modification de comportement de `TrainingPage`/`LoRAPage`/`InferencePage` en dehors du périmètre décrit.
- Disponibilité dans Inference après import : test d'intégration bout en bout (import réel déclenché → `InferencePage.lora_combo` contient la nouvelle entrée sans appel direct entre pages, uniquement via l'événement déjà existant).

## 8. Smoke réel — politique

Aucun nouvel entraînement OneTrainer. Le smoke doit démontrer le parcours utilisateur réel : `Training sélectionné` → `Job succeeded avec un .safetensors réel` (réutilisation d'un fichier réel existant, par exemple une copie du `.safetensors` produit par le smoke réel de Mission 101, associée à un vrai `TrainingJob` construit via le vrai `TrainingManager` — jamais via le runner `QProcess` ni un nouvel entraînement GPU) → action UI d'import réelle → vraie entrée dans la Central LoRA Library → Job marqué importé et persistant après rechargement du projet → LoRA réellement visible/sélectionnable dans `InferencePage`, sans redémarrage. Tous les artefacts du smoke (Workspace/Library temporaires, entrée Library créée) sont supprimés après vérification, comme pour le smoke de Mission 102.

## 9. Critères de clôture

1. Les 9 étapes de la section 6 sont observées réellement (smoke réel selon la politique de la section 8).
2. Tous les tests de la section 7 passent, suite complète confirmée au nombre exact.
3. Le cas d'échec de la section 3.5 est couvert par un test explicite démontrant l'absence de faux succès annoncé et l'absence de doublon silencieux.
4. Aucun élément de la section 5 n'a été ajouté.
5. Aucune modification de `src/domain/`, de `LoRALibraryManager`, ni de `InferencePage`.

## 10. Autorisation

Ce document a servi de contrat avant toute implémentation. Le code n'a été écrit qu'après validation explicite de ce périmètre par l'architecte — voir section 11 pour le résultat réel complet.

## 11. Résultat réel

### 11.1 `TRAINING_JOB_IMPORTED` retiré du contrat avant implémentation

Avant de commencer, l'architecte a demandé de réévaluer l'événement `TRAINING_JOB_IMPORTED` prévu en section 3.4/4/6. Aucun consommateur concret n'a été identifié : `LORA_LIBRARY_IMPORTED` (déjà publié par `import_lora()`) couvre déjà le seul besoin réel — annoncer la création du LoRA et rafraîchir Inference — et `TrainingPage` peut rafraîchir sa propre liste de Jobs par un simple appel direct après son propre appel à `set_job_imported_lora_id()`. L'événement a été retiré du contrat avant tout code, conformément à la règle "pas de scaffolding avant un besoin réel".

### 11.2 Implémentation — conforme au périmètre exact

`TrainingManager.set_job_imported_lora_id(job_id, lora_id)` ajouté avec le contrat idempotent/rollback identique à `update_job_state()`, aucun événement publié. `TrainingPage` gagne `lora_library_manager` en dépendance, une liste minimale des Jobs du Training sélectionné (`jobs_list`) avec un bouton d'action unique (`import_lora_button`), les quatre états d'import de la section 3.3 recalculés à chaque rafraîchissement à partir de `Training.jobs` et d'une relecture fraîche de `lora_library_manager.get(imported_lora_id)`. La séquence `import_lora()` puis `set_job_imported_lora_id()` suit exactement la stratégie non compensatoire de la section 3.5. Confirmé par `git diff --stat` : `src/managers/training_manager.py`, `src/ui/pages/training_page.py`, `src/ui/main_window.py` (passage de dépendance uniquement) — aucune modification de `src/domain/`, `LoRALibraryManager`, ni `InferencePage`.

### 11.3 Incident d'isolation découvert et corrigé pendant l'implémentation

La première version des nouveaux tests construisait `LoRALibraryManager` sans `storage_directory`, ce qui pointe par défaut vers le registre réel de la machine (`%LOCALAPPDATA%\AIStudioToolkit\lora_library.json`) — le même défaut d'isolation que le script de smoke v1 de Mission 102. Cinq entrées de test factices ("Imported LoRA") y ont été écrites avant d'être détectées (un test comptait 4 entrées Library au lieu de 1 attendue). Corrigé par un `storage_directory` temporaire dédié dans le test (même convention que `test_lora_library_roundtrip.py`), puis le registre réel a été nettoyé : les 5 entrées de test et une entrée orpheline `Mission102SmokeLoRA` restée du smoke Mission 102 (fichier source déjà supprimé, aucune donnée physique associée) ont été retirées. Vérifié après coup : registre réel vide, aucun dossier résiduel sous `%LOCALAPPDATA%\AIStudioToolkit\`, aucune donnée légitime pré-existante affectée.

### 11.4 Tests

**17 tests ciblés nets nouveaux** (1991 → 2008) : 6 dans `TrainingManagerImportJobToLibraryTest` (persistance, idempotence, rollback sur échec de `save()`, non-interférence avec `state`/`final_output_path`, survie à une fermeture/réouverture du projet), 11 dans `TrainingPageJobImportTest` (jobs multiples listés, éligibilité `succeeded`/`final_output_path` valide uniquement, fichier de sortie disparu, import réel créant une vraie entrée Library et persistant `imported_lora_id`, double import empêché tant que l'entrée existe, entrée supprimée → état "réimport possible" + réimport réel fonctionnel, échec `import_lora()` → Job inchangé, échec de persistance de `imported_lora_id` → avertissement explicite sans faux succès et sans suppression compensatoire, disponibilité immédiate et réelle dans `InferencePage.lora_combo` sans redémarrage). Suite complète : **2008/2008**, aucune régression.

### 11.5 Smoke réel — aucun nouvel entraînement OneTrainer, aucune interaction ComfyUI

Script autonome exécuté par Claude (scratchpad, jamais commité), isolé (Workspace/Library/registre temporaires dédiés). Réutilisation d'un `.safetensors` réel déjà présent sur disque (`Zaraya_Koyah_SDXL_last.safetensors`, 85 425 204 octets) **copié, jamais déplacé ni modifié** (hash MD5 vérifié identique avant/après), comme sortie d'un vrai `TrainingJob` marqué `succeeded` via le vrai `TrainingManager`. Parcours réel confirmé de bout en bout : ligne de Job affichée (`succeeded — importable`) → import réel via `TrainingPage.import_selected_job_to_library()` → vraie entrée créée dans la Bibliothèque (85 425 204 octets, copie identique) → `TrainingJob.imported_lora_id` réellement persisté et relu → LoRA immédiatement présent dans `InferencePage.lora_combo` **sans redémarrage**, via `LORA_LIBRARY_IMPORTED` déjà existant, aucun nouveau code Inference → rafraîchissement suivant : ligne affiche `importé : Mission103SmokeLoRA`, bouton désactivé, double import silencieux impossible. Tous les artefacts temporaires supprimés après vérification ; le fichier source réel sous `J:\Programmes\ComfyUI\models\loras\` et le registre réel de la machine confirmés inchangés après le smoke.
