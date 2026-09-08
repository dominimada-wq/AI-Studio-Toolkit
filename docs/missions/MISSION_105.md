# Mission 105 — Protection dirty-state du formulaire `TrainingPage`

> **MISSION CLÔTURÉE — LES 8 PARAMÈTRES SONT PROTÉGÉS, L'INVARIANT PREPARE/START EST GARANTI, SMOKE RÉEL ISOLÉ RÉUSSI.** Ce document a d'abord servi de contrat avant implémentation (sections 1-10, inchangées). Voir section 11 pour le résultat réel complet.

## 1. Contexte

L'audit post-Mission 104 a identifié le point le plus gênant pour un usage réel du produit : `TrainingPage` n'a **aucune protection dirty-state** sur son formulaire de 8 paramètres (`base_model_source`, `architecture`, `resolution`, `epochs`, `learning_rate`, `lora_rank`, `lora_alpha`, `trigger_word`), contrairement à `CharactersPage`/`LoRAPage`/`SettingsPage` (Mission 078) et `PromptsPage` (Mission 038). Une saisie non enregistrée est aujourd'hui écrasée silencieusement dès qu'un autre Training est sélectionné, qu'un autre Character devient actif, ou qu'un Workspace est fermé/ouvert — juste avant une opération GPU réelle et coûteuse.

Un mini-audit ciblé a confirmé que le pattern canonique (Missions 038/078/079) est directement réutilisable, avec un point contractuel supplémentaire propre à Training : `TrainingManager.prepare_onetrainer_config()` écrit un fichier de configuration OneTrainer (`onetrainer_config.json`) totalement déconnecté des widgets — ni `prepare_onetrainer_config()` ni `create_job()`/`start_training()` ne relisent jamais les champs affichés. Un second mini-audit (ci-dessous, section 3.5) a établi le mécanisme garantissant que Start utilise réellement les valeurs affichées.

## 2. Objectif

Garantir qu'aucune modification du formulaire Training ne peut être perdue silencieusement, et que Prepare/Start utilisent toujours, de façon fiable, les valeurs actuellement affichées — sans dialogue supplémentaire pour l'utilisateur au-delà de ce qui existe déjà ailleurs dans l'application.

## 3. Mini-audit — décisions retenues

### 3.1 Détection du dirty-state

Un unique flag `self._dirty`, couvrant les 8 champs ensemble — même contrat que `CharactersPage._dirty`/`LoRAPage._metadata_dirty` (un seul flag pour tout un formulaire, jamais un par champ). Connecté aux signaux natifs de chaque widget :

| Champ | Signal |
|---|---|
| `base_model_edit` | `textChanged` |
| `architecture_combo` | `currentTextChanged` (étend `on_architecture_changed()` existant — pas de seconde connexion) |
| `resolution_spinbox` | `valueChanged` |
| `epochs_spinbox` | `valueChanged` |
| `learning_rate_spinbox` | `valueChanged` |
| `lora_rank_spinbox` | `valueChanged` |
| `lora_alpha_spinbox` | `valueChanged` |
| `trigger_word_edit` | `textChanged` |

Un seul handler partagé `_on_training_parameters_changed()` met `_dirty = True` (mirroir exact de `LoRAPage._on_metadata_changed()`).

`update_trainings()` doit envelopper **les 7 champs actuellement non protégés** (`base_model_edit`, `resolution_spinbox`, `epochs_spinbox`, `learning_rate_spinbox`, `lora_rank_spinbox`, `lora_alpha_spinbox`, `trigger_word_edit`) dans `blockSignals(True)`/`blockSignals(False)` au moment du rechargement — seul `architecture_combo` l'est aujourd'hui (Mission 097). Sans cette extension, un simple refresh se marquerait dirty lui-même.

### 3.2 `update_trainings()` / `reset_for_context_change()` — séparation canonique

- **`update_trainings()`** reste abonnée uniquement à ses événements « refresh » actuels côté Character (`CHARACTER_CREATED`) et Workspace (`WORKSPACE_SAVED`/`RENAMED`), plus ses propres événements Manager (`TRAINING_CREATED`/`SELECTED`/`DELETED`). Compare `active_training_id` à un nouveau `self._loaded_training_id` : si inchangé et `_dirty` vrai → ne touche ni les 8 champs ni `_dirty`/`_config_stale` (refresh non destructeur). Sinon → recharge les 8 champs (sous `blockSignals`), `_dirty = False`, `_config_stale = False`, `_loaded_training_id = active_training_id`.
- **Nouvelle `reset_for_context_change()`** : méthode séparée, inconditionnelle, abonnée exclusivement à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` et `CHARACTER_SELECTED`/`DELETED` — retirés de la liste d'abonnements de `update_trainings()` dans `main_window.py`. Vide `training_list`, les 8 champs, `_dirty = False`, `_config_stale = False`, `_loaded_training_id = None`. Jamais superposée à `update_trainings()`.

### 3.3 Transitions destructrices — comportement cible

| Transition | Comportement |
|---|---|
| Sélection d'un autre Training | Si `_dirty` : dialogue Save/Discard/Cancel (mirroir `LoRAPage.on_lora_selection_changed()`) ; `Cancel` restaure la sélection Qt précédente (`blockSignals`), `training_manager.select()` jamais appelé |
| Création d'un Training | Non destructeur par construction (`TrainingManager.create()` ne sélectionne jamais) — aucune garde nécessaire au-delà de la comparaison d'id déjà en place |
| Suppression du Training affiché | Dialogue de confirmation existant enrichi d'une mention si `_dirty and item.data(...) == self._loaded_training_id` (mirroir `LoRAPage.delete_lora()`) — pas de second dialogue |
| Changement de Character (`CHARACTER_SELECTED`/`DELETED`) | Routé vers `reset_for_context_change()`, jamais `update_trainings()` |
| New Project / Open Project | Nouvelle `TrainingPage.confirm_context_change()` insérée dans `main_window.py::new_project()`/`open_project()`, avant `confirm_no_active_training()` (dernier de la série dirty, même ordre que les 5 gardes existantes) |
| Fermeture de l'application | Même `confirm_context_change()` insérée dans `closeEvent()`, dans le groupe des gardes dirty (après les gardes d'opération active `confirm_no_active_generation()`/`confirm_no_active_training()`, qui restent en premier) |
| Sélection/rafraîchissement de Job, import M103 | **Aucun effet** sur `_dirty`/`_config_stale` — confirmé : `_on_job_selection_changed()`, `_on_job_started()`, `_on_job_finished()`, `import_selected_job_to_library()` n'appellent jamais `update_trainings()`, seulement `_refresh_job_controls()`/`_refresh_jobs_list()` |

### 3.4 `confirm_context_change() -> bool`

Mirroir exact de `LoRAPage.confirm_context_change()` : retourne `True` immédiatement si `not self._dirty` ; sinon dialogue Save/Discard/Cancel ; `Cancel` → `False` ; `Save` → `save_training_parameters()`, `False` si échec (avec le message d'erreur déjà existant) ; sinon `_dirty = False`, `True`.

### 3.5 Invariant Prepare/Start — mécanisme retenu

**Constat vérifié** : `TrainingManager.create_job()` ne relit jamais le formulaire ni même l'objet `Training` — il relit exclusivement le fichier `onetrainer_config.json` déjà écrit par le dernier `prepare_onetrainer_config()` réussi. Un simple `save_training_parameters()` avant Start ne suffit donc pas : il met à jour `Training` mais ne régénère jamais ce fichier. Sans mécanisme supplémentaire, un Save manuel suivi d'un Start sans repasser par Préparer utiliserait une configuration obsolète.

**Solution retenue — nouveau flag `_config_stale` (Presentation uniquement, aucun champ Domain/Manager)** :
- mis à `True` uniquement quand `TrainingManager.update()` retourne réellement `True` (changement réellement persisté) — capturé dans `save_training_parameters()` ;
- remis à `False` uniquement par un `TrainingManager.prepare_onetrainer_config()` réussi (bouton Préparer **ou** appel automatique depuis Start) ;
- réinitialisé à `False` sur tout changement réel de Training actif, même frontière que `_loaded_training_id`.

**Rejeté** : Prepare automatique inconditionnel avant chaque Start (romprait « si propre : comportement historique » — `_materialize_concept()` recopie physiquement chaque image du Dataset à chaque Prepare, un coût réel) ; toute régénération « ciblée » alternative de la configuration (créerait une seconde implémentation, explicitement exclue) ; aucun mécanisme existant ne permet de détecter la fraîcheur autrement (`Training` ne porte aucune empreinte/horodatage de préparation).

**Contrat final `prepare_onetrainer_config()` (bouton Préparer)** :
1. si `_dirty` : `save_training_parameters()` ; échec → arrêt, aucun appel à `prepare_onetrainer_config()` côté Manager.
2. appel `TrainingManager.prepare_onetrainer_config()` inchangé.
3. succès → `_config_stale = False`, en plus du dialogue de succès existant.

**Contrat final `start_training()`** :
1. si `_dirty` : `save_training_parameters()` ; si `_dirty` reste vrai (échec, message déjà affiché) → **aucun Job créé**, retour immédiat.
2. si `_config_stale` : `TrainingManager.prepare_onetrainer_config()` (même gestion d'erreur que le bouton Préparer) ; échec → **aucun Job créé**, retour immédiat ; succès → `_config_stale = False`.
3. si ni dirty ni stale : comportement historique exact, aucun appel supplémentaire.
4. `create_job()` inchangé ensuite.

**Aucun nouveau dialogue** dans ce chemin — uniquement les `QMessageBox.critical` déjà existants (échec de sauvegarde/préparation/création de Job), jamais pour le simple fait d'être dirty.

**Vérifié — second invariant (état post-sauvegarde automatique)** : `_dirty == False` garanti (seul chemin de succès de `save_training_parameters()`) ; formulaire affiché inchangé (aucun `select()` dans ce chemin) ; le refresh réentrant déclenché par `WORKSPACE_SAVED` (`TrainingManager.update()` → `WorkspaceManager.save()`, précédent déjà établi pour `LoRAPage.save_metadata()`/`PromptsPage.save_text()`) recharge les 8 champs depuis des valeurs identiques à ce qui vient d'être persisté — sans effet visible ; aucun événement Job ne touche `_dirty`/`_config_stale` (confirmé section 3.3).

## 4. Périmètre exact — fichiers concernés

- `src/ui/pages/training_page.py` — `_dirty`, `_config_stale`, `_loaded_training_id`, connexions de signaux, `blockSignals()` étendu, `on_training_selection_changed()`, `delete_training()`, `save_training_parameters()` (capture du retour de `update()`), `prepare_onetrainer_config()`, `start_training()`, nouvelles `confirm_context_change()`/`reset_for_context_change()`.
- `src/ui/main_window.py` — retirer `training_page.update_trainings` des abonnements `WORKSPACE_CREATED/OPENED/CLOSED` et `CHARACTER_SELECTED/DELETED` (s'ils y figurent) au profit de `training_page.reset_for_context_change` ; insérer `training_page.confirm_context_change()` dans `new_project()`/`open_project()` (avant `confirm_no_active_training()`) et dans `closeEvent()` (après les gardes d'opération active, avec les autres gardes dirty).
- `tests/integration/test_training_roundtrip.py` — nouveaux tests.

**Aucun changement** `src/domain/`, `src/managers/training_manager.py`, `src/managers/*` (aucune nouvelle constante d'événement), `src/engines/onetrainer_config.py`.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

Validation de `base_model_source`, traduction générale des messages d'erreur, nouveaux paramètres OneTrainer, presets, refonte de `TrainingPage`, historique Jobs avancé, restructuration Settings, démarrage automatique de ComfyUI, Fooocus/Forge.

## 6. Étapes techniques attendues

1. `_dirty`, `_config_stale`, `_loaded_training_id` initialisés dans `__init__`.
2. Connexion des 7 signaux manquants + extension de `on_architecture_changed()`.
3. `blockSignals()` étendu aux 7 champs dans `update_trainings()`.
4. Séparation `update_trainings()`/`reset_for_context_change()`, wiring `main_window.py`.
5. `on_training_selection_changed()` : garde Save/Discard/Cancel.
6. `delete_training()` : dialogue enrichi si dirty sur l'item ciblé.
7. `confirm_context_change()` : nouvelle méthode, wiring `new_project()`/`open_project()`/`closeEvent()`.
8. `save_training_parameters()` : capture du retour de `TrainingManager.update()`, met `_config_stale = True` si `True`.
9. `prepare_onetrainer_config()` : préfixe save-si-dirty, `_config_stale = False` sur succès.
10. `start_training()` : préfixe save-si-dirty puis prepare-si-stale, chacun avec arrêt sur échec, avant `create_job()`.

## 7. Tests attendus

- Modification d'un des 8 champs → `_dirty` devient vrai (un test par type de widget suffit à couvrir le handler partagé, pas 8 tests redondants).
- Refresh programmatique (`WORKSPACE_SAVED` sans changement de Training, `CHARACTER_CREATED`, `TRAINING_CREATED` sans changement d'id actif) → `_dirty`/`_config_stale` inchangés, champs inchangés.
- Sélection d'un autre Training : Save réussi (persistance confirmée, sélection avancée) / Discard (sélection avancée, brouillon perdu) / Cancel (sélection restaurée, Manager jamais appelé) / échec de Save (sélection restaurée, message d'erreur).
- Suppression : dialogue standard si non dirty, dialogue enrichi si dirty sur l'item ciblé.
- Changement de Character/Workspace, New/Open/Close : `reset_for_context_change()` vide tout sans dialogue ; `confirm_context_change()` bloque/sauvegarde/ignore selon le choix, mêmes trois issues que la sélection.
- Prepare : propre → comportement historique (un seul appel Manager) ; dirty → save puis prepare (deux appels, dans l'ordre) ; échec de save → prepare jamais appelé.
- Start : propre et non stale → comportement historique (aucun appel Manager supplémentaire avant `create_job()`) ; dirty → save puis prepare puis create_job (trois appels, dans l'ordre, `_dirty`/`_config_stale` faux ensuite) ; échec de save → ni prepare ni create_job ; échec de prepare → create_job jamais appelé ; propre mais stale (édition sauvegardée manuellement sans repasser par Préparer) → prepare automatique avant create_job.
- Événements Job/M103 (démarrage, log, fin, import Bibliothèque) → aucun effet sur `_dirty`/`_config_stale`.
- Non-régression des gardes `MainWindow` existantes (Prompts/Characters/LoRA/Settings/Inference/`confirm_no_active_training`) — suite complète verte, aucun changement d'ordre pour les gardes déjà en place.

Tests `QMessageBox` interceptés exclusivement via les deux techniques déjà établies dans ce dépôt (`patch.object` sur la méthode de dialogue de la Page, ou `patch(".../QMessageBox")` avec `exec.return_value` réglé sur `.Save`/`.Discard`/`.Cancel`) — jamais de boîte modale réelle laissée bloquer un test.

## 8. Smoke réel — politique

Un smoke Qt réel est prévu et sera exécuté par Claude une fois ce contrat validé et l'implémentation terminée, avant tout commit — même esprit que les smokes Missions 078/079 : édition réelle des 8 champs, changement de sélection réel avec les trois issues, Prepare/Start réels (sans OneTrainer/GPU réel — seule la préparation de configuration est exercée, comme les smokes Mission 097/100 existants) confirmant l'ordre save→prepare→create_job et l'absence de Job créé sur échec simulé.

## 9. Critères de clôture

Suite complète verte (nombre exact confirmé), tests ciblés listés en section 7 tous PASS, smoke réel PASS, `git diff --stat` limité au périmètre de la section 4, aucune régression des gardes `MainWindow` existantes.

## 10. Autorisation

Ce document a servi de contrat avant toute implémentation. Le code n'a été écrit qu'après validation explicite de ce périmètre par l'architecte — voir section 11 pour le résultat réel complet.

## 11. Résultat réel

### 11.1 Implémentation — conforme au périmètre exact

`git diff --stat` confirmé limité au périmètre annoncé (section 4) : `src/ui/pages/training_page.py` (+366 lignes), `src/ui/main_window.py` (+33/-6 lignes), `tests/integration/test_training_roundtrip.py` (+628 lignes) — aucune modification `src/domain/`, `TrainingManager`, `src/engines/`, `SettingsPage`, `InferencePage`.

`_dirty`/`_config_stale`/`_loaded_training_id` implémentés exactement selon le contrat (section 3.1/3.5) : flag unique pour les 8 paramètres, `_config_stale` strictement Presentation/session (aucun hash, aucun horodatage, aucune validation persistante de `onetrainer_config.json` — limite volontaire respectée). `update_trainings()`/`reset_for_context_change()` séparées selon le pattern canonique, `blockSignals()` étendu aux 7 champs qui n'en bénéficiaient pas encore. Save/Discard/Cancel implémentés sur la sélection et sur `confirm_context_change()`, avec restauration réelle de la sélection Qt sur Cancel. Suppression enrichie sans second dialogue. Intégration `MainWindow` en 7ᵉ garde dans `new_project()`/`open_project()`/`closeEvent()`, ordre vérifié par rapport à `confirm_no_active_training()`.

**Ajustement interne découvert et corrigé pendant l'implémentation** (validé fonctionnellement par l'architecte) : `save_training_parameters()` suit le contrat déjà établi par Mission 097/LoRAPage.save_metadata() — un échec de sauvegarde resynchronise les champs vers l'état Domain restauré et remet `_dirty` à `False`, rendant impossible de distinguer succès et échec en relisant `_dirty` après l'appel. `save_training_parameters()` retourne désormais un booléen explicite (`True` uniquement sur succès réel), vérifié par tous ses appelants (`on_training_selection_changed()`, `confirm_context_change()`, `prepare_onetrainer_config()`, `start_training()`) — le comportement observable respecte intégralement le contrat validé, seul le mécanisme de détection interne diffère de ce qui était implicite en section 3.5.

### 11.2 Tests

**26 tests ciblés nets nouveaux** (2021 → 2047) : 24 dans la nouvelle `TrainingPageDirtyStateTest` (les 8 types de widgets, refresh non-destructif via `CHARACTER_CREATED`, Save/Discard/Cancel avec restauration réelle de sélection, suppression enrichie, reset Character/Workspace sans dialogue, `confirm_context_change()` isolée avec ses trois issues, invariant Prepare/Start complet — dirty, stale, échecs de sauvegarde/préparation, cas propre-et-non-stale sans Prepare superflu), 2 dans `TrainingPageJobImportTest` (sélection/import de Job et callbacks de cycle de vie M100/M103 sans faux `_dirty`/`_config_stale`). Suite complète : **2047/2047**, exit 0, aucune régression — y compris les 168/168 de `test_training_roundtrip.py` et les 74/74 gardes `MainWindow` existantes (`test_main_window_close_event.py`/`test_main_window_new_project.py`), non modifiées et non régressées.

### 11.3 Smoke réel — isolé, aucun subprocess/GPU réel

Script autonome exécuté par Claude (scratchpad, jamais commité), isolé (Workspace/registre temporaires dédiés). Seul `TrainingJobRunner` est remplacé (jamais de subprocess/GPU réel) — `WorkspaceManager`/`CharacterManager`/`DatasetManager`/`TrainingManager`/`TrainingPage` et ses widgets Qt sont tous réels et non mockés. Parcours réel confirmé : édition réelle d'un champ → `_dirty` → Start → sauvegarde réelle → préparation réelle avec la nouvelle valeur → Job créé dont le snapshot de configuration contient la nouvelle valeur ; callbacks de cycle de vie du Job sans effet sur `_dirty`/`_config_stale` ; cycle complet Save/Discard/Cancel sur un vrai changement de sélection (Cancel restaure la sélection Qt réelle et préserve le brouillon, Discard bascule et vide les champs, Save persiste réellement puis bascule) ; Start propre et non stale ne redéclenche aucune préparation superflue. **26/26 vérifications réussies**, exit 0. cwd réel confirmé inchangé après nettoyage.
