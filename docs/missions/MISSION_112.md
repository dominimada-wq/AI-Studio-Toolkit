# Mission 112 — Explicit ComfyUI / Forge Connection Diagnostics in Settings

> **MISSION CLÔTURÉE — DIAGNOSTIC DE CONNEXION COMFYUI/FORGE DANS SETTINGS VALIDÉ, SUITE COMPLÈTE 2230/2230.** Commit fonctionnel `1c40fca14ef1e73e05deb792240388a3fd46131b` (`Add explicit ComfyUI/Forge connection diagnostics in Settings`), tag `v0.2-mission112`, GitHub Release publiée. Voir `CHANGELOG.md` (section « Mission 112 ») pour le résumé de clôture ; le contrat ci-dessous décrit fidèlement le périmètre réellement implémenté, sans écart.

## 1. Contexte

L'audit post-Mission 111 puis le micro-audit complémentaire ont établi par lecture directe du code que l'utilisateur ne découvre aujourd'hui qu'ComfyUI/Forge est indisponible qu'au moment d'une vraie action, et que cette découverte est structurellement inégale entre Settings et Inference, et entre ComfyUI et Forge :

- `InferencePage._on_refresh_sampler_scheduler_clicked()` (`inference_page.py:1368-1439`) couvre déjà les deux moteurs via `self._active_engine()` (`inference_page.py:638-648`, duck-typing, jamais d'`isinstance`) et `GenerationManager.list_checkpoints/list_samplers/list_schedulers(engine=...)` — un échec affiche un message générique mais réel (`"Découverte impossible : moteur injoignable..."`). Un clic sur « Générer » avec un backend éteint traverse `GenerationManager.generate()` (`generation_manager.py:312-313`, catch `ComfyUIEngineError, ForgeEngineError` → `GenerationError`) → `GenerationWorker.run()` (`generation_worker.py:132-133`, `failed.emit(str(error))`) → `InferencePage._on_generation_failed()` (`inference_page.py:1096-1107`, `QMessageBox.critical` avec le message brut de l'Engine, ex. `"ComfyUI server unreachable at http://127.0.0.1:8188: ..."` / `"Forge server unreachable at http://127.0.0.1:7860: ..."`). **Ce mécanisme Inference existe déjà et fonctionne pour les deux moteurs — il n'est pas modifié par cette mission.**
- `SettingsPage.refresh_checkpoints()`/`refresh_loras()` (`settings_page.py:365-433`) n'existent que pour **ComfyUI**, instancient un `ComfyUIEngine` frais directement dans la Page à partir du texte actuellement saisi dans `comfyui_url_edit` (`settings_page.py:369`, `settings_page.py:405` — contournement délibéré de `GenerationManager`, nécessaire pour tester une URL pas encore sauvegardée) et ne servent qu'indirectement de test de connexion : un succès signifie « des checkpoints ont été trouvés », jamais explicitement « le backend est joignable ».
- **Forge n'a strictement aucun mécanisme de ce type dans Settings** : `forge_url_edit` (`settings_page.py:182`) est un `QLineEdit` nu, sans combo, sans bouton, sans import de `ForgeEngine` dans `settings_page.py` (confirmé par grep).
- Les endpoints de découverte déjà exploités constituent déjà une validation applicative réelle, jamais un simple test de port : `ComfyUIEngine.list_checkpoints()` (`comfyui_engine.py:245-310`) appelle `GET /object_info/CheckpointLoaderSimple` et valide la forme exacte de la réponse (`node_info["input"]["required"]["ckpt_name"][0]` doit être une liste) ; `ForgeEngine.list_checkpoints()` (`forge_engine.py:118-139`) appelle `GET /sdapi/v1/sd-models` et valide que la réponse est une liste d'objets portant chacun une clé `"title"`. Dans les deux cas, une réponse structurellement valide mais vide (`[]`) ne lève aucune exception — `list_checkpoints()` retourne alors une liste vide sans erreur, ce qui satisfait déjà nativement la contrainte « zéro checkpoint ≠ backend injoignable ».
- `ComfyUIEngine._request_json()` (`comfyui_engine.py:574-594`) et `ForgeEngine._request_json()` (`forge_engine.py:389-418`) sont les points uniques de capture des erreurs de communication (`urllib.error.URLError`/`OSError` → `ComfyUIEngineError`/`ForgeEngineError` nommant l'URL) — aucune nouvelle route HTTP n'est nécessaire pour cette mission.
- `SettingsPage._on_settings_changed()`/`self._dirty` (`settings_page.py:64-72`) est un pattern déjà établi (Mission 078) de suivi de saisie utilisateur via `textChanged`, mais réservé à la section Workspace (thème/langue) et rendu sûr uniquement parce que `_load_settings_fields()` enveloppe ses `setText()` dans `blockSignals()`. `update_application_settings()` (`settings_page.py:580-597`), qui recharge `comfyui_url_edit`/`forge_url_edit` via `setText()` (lignes 587/596), **n'a pas** cet enveloppement — connecter un nouveau handler à `textChanged` sur ces deux champs déclencherait donc une invalidation à chaque rechargement de Settings, pas seulement à une vraie saisie utilisateur. Le signal Qt `textEdited` (émis uniquement par une interaction utilisateur réelle, jamais par un `setText()` programmatique) évite ce problème sans modifier `update_application_settings()`.

## 2. Objectif

Fermer la friction réelle identifiée : permettre à l'utilisateur de vérifier explicitement, depuis Settings, la disponibilité de ComfyUI et de Forge — y compris pour une URL tout juste modifiée et pas encore sauvegardée — sans attendre une vraie génération ni une découverte de checkpoints pour l'apprendre indirectement.

## 3. Décision retenue — mécanisme

**Sur les Engines** : une méthode `check_connection(timeout: Optional[float] = None) -> bool` sur `ComfyUIEngine` et `ForgeEngine`, implémentée comme un pur wrapper de la méthode `list_checkpoints()` déjà existante — aucune nouvelle requête HTTP, aucun nouvel endpoint, **aucune nouvelle exception, et aucune capture de l'exception existante** :

```python
def check_connection(self, timeout: Optional[float] = None) -> bool:
    self.list_checkpoints(timeout=timeout)
    return True
```

Sur succès (y compris une réponse structurellement valide mais vide), retourne `True`. Sur échec de communication ou de forme de réponse, `ComfyUIEngineError`/`ForgeEngineError` — la même exception que `list_checkpoints()` lève déjà — remonte **telle quelle**, jamais absorbée en `False` : c'est l'appelant (`SettingsPage`) qui décide comment transformer cette exception en feedback, conservant ainsi l'information diagnostique (URL, raison exacte) que l'exception porte déjà, plutôt que de la perdre dans un booléen. Ce contrat satisfait directement la contrainte « zéro checkpoint ne doit jamais être assimilé à une absence de connexion » : `list_checkpoints()` ne lève que sur un échec de communication ou une réponse structurellement invalide (voir §1) — une réponse valide avec une liste vide retourne `True`, exactement comme une réponse valide avec dix checkpoints.

**Sur `SettingsPage`** : deux nouveaux boutons « Tester la connexion » et deux nouveaux labels de statut, un par moteur, positionnés directement sous leur champ URL respectif dans la section Application (`comfyui_url_edit` ligne 102, `forge_url_edit` ligne 182). Chaque bouton instancie un engine transitoire depuis le texte actuellement saisi — exactement le pattern déjà établi par `refresh_checkpoints()`/`refresh_loras()` (`ComfyUIEngine(base_url=self.comfyui_url_edit.text(), timeout=CONNECTION_TEST_TIMEOUT)`) — appelle `check_connection()` dans un `try`/`except ComfyUIEngineError`/`ForgeEngineError`, et met à jour uniquement son propre label de statut (positif sur succès, message court construit à partir de `str(error)` — qui nomme déjà le moteur et l'URL, voir §1 — sur échec, jamais un traceback brut). Aucun des deux boutons ne touche à un combo checkpoint/LoRA, ne déclenche `save_application_settings()`, ni ne modifie l'état de l'autre moteur.

**Invalidation du statut** : `comfyui_url_edit.textEdited` et `forge_url_edit.textEdited` (signal Qt qui ne s'émet que sur une saisie utilisateur réelle, jamais sur un `setText()` programmatique — voir §1) sont chacun connectés à un handler qui réinitialise uniquement son propre label à un texte neutre (« Connexion non testée. »), indépendamment de l'autre moteur.

## 4. Comportement contractuel

1. `check_connection()` retourne `True` si et seulement si la requête applicative aboutit et que la réponse a la forme structurelle attendue — jamais en fonction du nombre d'éléments retournés.
2. `check_connection()` **propage telle quelle** `ComfyUIEngineError`/`ForgeEngineError` sur toute erreur de communication ou de forme de réponse déjà couverte par `list_checkpoints()` — jamais absorbée en un simple `False`, aucune nouvelle catégorie d'erreur n'est introduite.
3. Le test utilise la valeur actuellement affichée dans le champ URL, jamais nécessairement la valeur déjà sauvegardée.
4. Tester une URL ne modifie jamais `ApplicationSettings` — aucun appel à `save_application_settings()` depuis les nouveaux boutons.
5. Tester un moteur ne modifie jamais l'état affiché de l'autre moteur.
6. Une modification manuelle du champ URL après un test invalide immédiatement le statut affiché pour ce moteur uniquement, en le ramenant à un état neutre — jamais en essayant de deviner un nouveau résultat sans nouveau clic.
7. Aucun combo checkpoint/LoRA, aucune découverte de modèles, n'est affecté par ces nouveaux boutons.
8. Le bouton « Rafraîchir » existant d'`InferencePage`, `GenerationManager`, et `SettingsPage.refresh_checkpoints()`/`refresh_loras()` restent strictement inchangés.
9. `SettingsPage` intercepte l'exception propagée par `check_connection()` et affiche un message court et actionnable (moteur concerné, URL testée, raison résumée) — jamais un traceback brut ni la chaîne d'erreur système non résumée.

## 5. Périmètre exact — fichiers concernés

- `src/engines/comfyui_engine.py` (modifié) — ajout de `check_connection()`.
- `src/engines/forge_engine.py` (modifié) — ajout de `check_connection()`.
- `src/ui/pages/settings_page.py` (modifié) — deux boutons, deux labels, deux méthodes de test, deux handlers d'invalidation, une nouvelle constante `CONNECTION_TEST_TIMEOUT = 5.0` (même valeur que `CHECKPOINT_DISCOVERY_TIMEOUT`/`LORA_DISCOVERY_TIMEOUT`/`OLLAMA_DISCOVERY_TIMEOUT`, `settings_page.py:28-36`).
- `tests/integration/test_comfyui_engine.py` (modifié) — nouveaux tests de `check_connection()`.
- `tests/integration/test_forge_engine.py` (modifié) — nouveaux tests de `check_connection()`.
- `tests/integration/test_settings_page.py` (modifié) — nouveaux tests des deux boutons/labels.

**Aucun changement attendu** à `src/ui/pages/inference_page.py`, `src/managers/generation_manager.py`, `src/domain/application_settings.py`, `src/managers/application_settings_manager.py`, Domain, `MainWindow`, EventBus, OneTrainer (`src/engines/onetrainer_launch.py`, `src/ui/training_job_runner.py`) — si l'implémentation réelle révèle qu'un changement dans l'un de ces fichiers est nécessaire, arrêt et rapport avant tout élargissement.

## 6. Hors périmètre strict — ne pas ajouter à cette mission

- Démarrage automatique de ComfyUI ou de Forge, arrêt, redémarrage, ownership de process, `subprocess`/`QProcess`.
- Surveillance continue, polling périodique, reconnexion automatique.
- Exploitation de `comfyui_path` pour lancer ComfyUI.
- Ajout d'un champ de chemin d'installation Forge.
- Refresh des checkpoints/LoRA Forge dans Settings (combo, bouton dédié) — hors périmètre de cette mission, qui ne porte que sur la joignabilité.
- Modification d'`InferencePage` ou de `GenerationManager`.
- Modification de l'architecture OneTrainer.
- Refonte générale de `SettingsPage`.
- Fooocus, ou tout autre moteur.

## 7. Étape technique attendue

**`ComfyUIEngine`** (`comfyui_engine.py`, méthode ajoutée après `list_loras()` ou à proximité) :

```python
def check_connection(self, timeout: Optional[float] = None) -> bool:
    self.list_checkpoints(timeout=timeout)
    return True
```

**`ForgeEngine`** (`forge_engine.py`, même emplacement relatif) :

```python
def check_connection(self, timeout: Optional[float] = None) -> bool:
    self.list_checkpoints(timeout=timeout)
    return True
```

**`SettingsPage`** (`settings_page.py`) :

- Constante : `CONNECTION_TEST_TIMEOUT = 5.0` près des constantes de découverte existantes (ligne ~28-36).
- Widgets : `self.comfyui_test_connection_button` (`QPushButton("Tester la connexion")`) + `self.comfyui_connection_status_label` (`QLabel`) sous `comfyui_url_edit` ; `self.forge_test_connection_button` + `self.forge_connection_status_label` sous `forge_url_edit`.
- Méthodes `test_comfyui_connection()`/`test_forge_connection()`, symétriques à `refresh_checkpoints()` dans leur construction d'engine transitoire, appelant `check_connection()` dans un `try`/`except ComfyUIEngineError`/`ForgeEngineError` et n'écrivant que dans leur propre label (succès : message positif ; échec : message court dérivé de `str(error)`).
- Handlers `_on_comfyui_url_edited()`/`_on_forge_url_edited()` connectés respectivement à `comfyui_url_edit.textEdited`/`forge_url_edit.textEdited`, réinitialisant leur propre label à un texte neutre.

## 8. Tests attendus

**`tests/integration/test_comfyui_engine.py`** (nouvelle classe `ComfyUIEngineCheckConnectionTest`, même pattern `@patch("urllib.request.urlopen")`/`_FakeResponse` que les classes existantes) :

1. Réponse applicative structurellement valide (avec au moins un checkpoint) → `True`.
2. Réponse applicative valide mais `ckpt_name` vide (`[[]]`) → `True` (zéro checkpoint ≠ injoignable).
3. `urlopen` lève `URLError`/`OSError` (backend injoignable) → `ComfyUIEngineError` propagée (`assertRaises`), jamais absorbée en `False`.
4. Réponse structurellement invalide (forme inattendue) → `ComfyUIEngineError` propagée, même comportement que `list_checkpoints()` seul.

**`tests/integration/test_forge_engine.py`** (nouvelle classe `ForgeEngineCheckConnectionTest`, même pattern) : les 4 mêmes cas (3 et 4 avec `ForgeEngineError`), adaptés à la forme `/sdapi/v1/sd-models` (liste de `{"title": ...}`).

**`tests/integration/test_settings_page.py`** (nouvelle classe, ou extension de `SettingsPageCheckpointDiscoveryTest`/nouvelle classe dédiée `SettingsPageConnectionDiagnosticsTest`, `@patch("src.ui.pages.settings_page.ComfyUIEngine")`/`@patch("src.ui.pages.settings_page.ForgeEngine")`) :

5. Clic sur le bouton ComfyUI avec `check_connection()` mocké à `True` → label affiche un statut positif explicite.
6. Clic sur le bouton ComfyUI avec `check_connection()` mocké à `False` → label affiche un statut d'échec explicite.
7. Le test ComfyUI utilise bien l'URL actuellement tapée (non sauvegardée) — même vérification que `test_refresh_uses_the_currently_typed_url_not_necessarily_saved` déjà existant.
8. Les 3 mêmes tests (5-7) pour Forge.
9. Modifier `comfyui_url_edit` après un test réussi réinitialise son label à l'état neutre, sans toucher au label Forge.
10. Modifier `forge_url_edit` après un test réussi réinitialise son label à l'état neutre, sans toucher au label ComfyUI.
11. Tester un moteur ne modifie pas le label de l'autre.
12. Aucun des deux boutons n'appelle `save_application_settings()` (vérifié par assertion sur `application_settings_manager.settings` inchangé après clic).

## 9. Critères de clôture

1. `check_connection()` implémenté à l'identique sur les deux Engines, testé selon la section 8.
2. Les 8 points du contrat comportemental (section 4) vérifiés explicitement par au moins un test chacun.
3. Zéro modification d'`InferencePage`, `GenerationManager`, Domain, `ApplicationSettingsManager`, `MainWindow`, EventBus, OneTrainer — sauf anomalie réelle découverte et rapportée avant tout élargissement.
4. Suite complète verte au nombre exact, `git diff --check` propre.
5. Aucun élément de la section 6 n'a été ajouté.

## 10. Documentation

Cette mission ne referme aucun besoin futur déjà enregistré dans `docs/PROJECT_CONTEXT.md` autre que le sous-point explicitement non tranché « un diagnostic de joignabilité amélioré (message actionnable avant Generate, sans lancement) » des entrées ComfyUI/Forge — la gestion automatique complète (démarrage/arrêt/ownership) qu'elles décrivent par ailleurs reste, elle, entièrement ouverte et non affectée par cette mission. La régularisation documentaire post-clôture suivra le même processus que les missions précédentes, après commit/tag/Release.

## 11. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte.
