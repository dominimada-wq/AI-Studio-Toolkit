# Mission 115 — ComfyUI Auto-Start from Inference with Pending Generation Handoff

> **CONTRAT PRÉ-IMPLÉMENTATION — NON ENCORE IMPLÉMENTÉE.** Ce document sert de périmètre fermé avant toute implémentation. Le code ne sera écrit qu'après validation explicite par l'architecte.

## 1. Contexte

Mission 114 a livré un lifecycle Start/Stop/ownership/readiness complet pour ComfyUI Local (`src/ui/comfyui_lifecycle_manager.py::ComfyUILifecycleManager`, six états `STOPPED`/`EXTERNAL_ACTIVE`/`STARTING`/`RUNNING_OWNED`/`STOPPING`/`START_FAILED`), mais strictement limité à `SettingsPage` — `InferencePage` n'a aujourd'hui aucune référence à ce composant (confirmé par audit : zéro occurrence de `ComfyUILifecycleManager`/`comfyui_lifecycle_manager` dans `src/ui/pages/inference_page.py`). Un clic sur Generate avec ComfyUI éteint traverse aujourd'hui `_start_generation()` → `GenerationWorker`/`QThread` → `GenerationManager.generate()` (`src/managers/generation_manager.py:127-145`) → `ComfyUIEngine.generate_image()`, échoue après le timeout socket, et affiche le message technique brut via `QMessageBox.critical` dans `_on_generation_failed()` — sans aucune tentative de démarrage automatique.

Deux micro-audits read-only préalables ont établi, par inspection directe du code réel (jamais par supposition) :

- **Audit d'intégration asynchrone** : `InferencePage._start_generation()` (`inference_page.py:887-1069`) capture déjà l'intégralité des paramètres de génération en variables locales avant toute construction d'objet asynchrone — le point d'insertion naturel pour un pré-vol lifecycle se situe juste après la résolution de `target_engine_key`/`target_engine` (lignes 934-935), avant la désactivation des contrôles et la construction du `GenerationWorker`. `ComfyUILifecycleManager` n'expose qu'un seul signal, `state_changed = Signal(str)` (`comfyui_lifecycle_manager.py:73`) — aucun signal dédié par état, `last_error_message` étant mis à jour de façon synchrone juste avant chaque émission. `is_generation_active()` (`inference_page.py:1756-1775`) ne teste aujourd'hui que `self._thread is not None and self._thread.isRunning()` — insuffisant pour couvrir une attente de Start pendant laquelle aucun thread n'existe encore, ce qui rendrait `confirm_no_active_generation()` (utilisé par les guards de fermeture/renommage dans `main_window.py:684-687,806-809`) inefficace sans extension explicite.
- **Audit de provenance de configuration** : `InferencePage` reçoit déjà `application_settings_manager` en position 7 de ses 9 paramètres constructeur (`inference_page.py:103-114`, stocké `self._application_settings_manager` ligne 134) — la **même instance unique** que celle injectée dans `SettingsPage` (`main_window.py:159-162,293,449`). Aucune modification n'est nécessaire pour qu'Inference lise la configuration persistée : `self._application_settings_manager.settings.comfyui_path/.comfyui_install_path/.comfyui_url`. Un texte tapé dans `comfyui_path_edit`/`comfyui_install_path_edit`/`comfyui_url_edit` sans cliquer sur « Enregistrer » n'atteint déjà, dans l'architecture actuelle, ni `application_settings_manager.settings` ni le fichier persisté (confirmé : ces trois widgets n'ont aucune connexion vers `application_settings_manager.update(...)`, seul `save_application_settings()` l'appelle). `SettingsPage.start_comfyui()` (`settings_page.py:667-671`) lit volontairement le texte live des widgets — un choix délibéré et distinct, non modifié par cette mission. `resolve_comfyui_launch()` produit déjà des messages d'erreur actionnables (`ComfyUILaunchError`), capturés par `ComfyUILifecycleManager.start()` et transformés en `START_FAILED` + `last_error_message` avant toute émission de signal — directement réutilisables sans nouveau texte.

Aucun obstacle architectural n'a été identifié par ces deux audits.

## 2. Objectif

Pour ComfyUI Local uniquement : `Generate` avec ComfyUI arrêté doit devenir `Generate → détection backend absent → Start via le ComfyUILifecycleManager partagé → attente non bloquante de readiness → RUNNING_OWNED → lancement automatique de la génération originellement demandée`, sans que l'utilisateur n'ait à ouvrir ComfyUI Desktop, aller dans Settings, cliquer sur Démarrer, ou recliquer sur Generate après readiness.

## 3. Décision retenue — architecture

**Source canonique de configuration** : Inference utilise exclusivement `self._application_settings_manager.settings.comfyui_path`/`.comfyui_install_path`/`.comfyui_url`, snapshotées au clic Generate — jamais les `QLineEdit` de `SettingsPage`. Les modifications Settings non sauvegardées restent sans effet. Le comportement actuel de `SettingsPage.start_comfyui()` (valeurs live des widgets) reste inchangé — asymétrie assumée et documentée, pas une incohérence.

**Instance lifecycle unique** : `MainWindow` injecte la **même** instance `self.comfyui_lifecycle_manager` (déjà construite ligne 193) dans `SettingsPage` (déjà fait) et désormais aussi dans `InferencePage` — aucun second `ComfyUILifecycleManager` n'est créé pour Inference.

**Snapshot de génération** : au clic Generate, après la validation actuelle et la résolution de `target_engine_key`/`target_engine`, l'ensemble des paramètres déjà capturés aujourd'hui (prompt, workspace/output, références, dimensions, engine, sampler/scheduler, seed, LoRA) plus la configuration ComfyUI persistée nécessaire au Start sont regroupés dans une structure explicitement typée et privée à `inference_page.py` (ex. `NamedTuple`/`@dataclass` interne, jamais un objet `src/domain/` — état d'orchestration UI éphémère, pas une entité métier persistée). Cette structure est immuable : elle n'est jamais reconstruite ni relue depuis les widgets une fois créée.

**Un seul pending** : `self._pending_generation_request`, initialisé à `None`, un seul champ, jamais de file d'attente. Son identité (comparaison `is`) sert de garde contre tout signal `state_changed` tardif ou obsolète — même discipline que celle déjà appliquée par `_cleanup_thread()` pour `worker`/`thread` (capture par valeur, vérification d'identité avant tout effet).

## 4. Comportement contractuel

**États lifecycle au clic Generate** (moteur ComfyUI sélectionné uniquement) :

| État | Comportement |
|---|---|
| `RUNNING_OWNED` | Génération immédiate, aucun `start()`. |
| `EXTERNAL_ACTIVE` | Génération immédiate, aucun `start()`, aucun ownership pris. |
| `STOPPED` | Snapshot + pending, contrôles Generate désactivés, appel `manager.start(...)`. |
| `START_FAILED` | Même comportement que `STOPPED` — nouvelle tentative autorisée via `manager.start(...)`. |
| `STARTING` | Snapshot + pending, **aucun second Start** — rattachement au Start déjà en cours. |
| `STOPPING` | Refus immédiat, aucun pending créé, aucune mise en file d'attente jusqu'à `STOPPED` — message utilisateur clair demandant de réessayer après l'arrêt. |

**Readiness** : Inference se connecte au `state_changed` du lifecycle manager partagé — **aucun second polling HTTP**. Quand le pending courant reçoit `RUNNING_OWNED` **ou** `EXTERNAL_ACTIVE` (ce second cas couvrant la situation où `start()` détecte de façon synchrone, dès l'appel depuis `STOPPED`, qu'un backend externe répond déjà — cas du premier clic Generate d'une session où Settings n'a jamais été ouvert), la génération snapshotée est lancée automatiquement.

**`START_FAILED` pendant l'attente** : invalider le pending, réactiver l'UI, afficher exactement `last_error_message` (jamais un nouveau texte inventé côté Inference), ne jamais appeler `GenerationManager.generate()` — évite toute seconde erreur technique.

**Stop pendant l'attente** (`STARTING → STOPPING → STOPPED`, déclenché ailleurs, ex. Settings) : invalider le pending, réactiver l'UI, afficher un message d'annulation distinct de `START_FAILED`, ne jamais relancer automatiquement ComfyUI, ne jamais lancer la génération.

**Protection anti-double-clic** : `generate_button` désactivé dès que validation + snapshot sont acceptés, avant toute attente de Start. `is_generation_active()` doit retourner vrai si le thread de génération est actif **ou** si `self._pending_generation_request is not None`. `confirm_no_active_generation()` conserve son nom et sa signature, mais couvre désormais aussi cette phase pending — les guards existants (`main_window.py:684-687,806-809`) en bénéficient sans modification de leur propre code.

**Changement de contexte** : tant que la génération HTTP n'est pas réellement partie (pending encore en attente d'un état lifecycle), un changement de Workspace, une fermeture/reset de contexte ou un `shutdown()` pertinent doivent invalider le pending — un signal lifecycle tardif après cette invalidation est ignoré grâce à la garde d'identité. Une génération déjà réellement partie (thread HTTP en vol) conserve exactement son comportement actuel, non affecté par cette mission.

**Forge strictement inchangé** : ce flux ne s'applique que si `target_engine_key == "comfyui"` (résolu au même point que le code existant, `inference_page.py:934-935`). Pour Forge : code actuel inchangé à l'identique, aucun auto-start, aucun lifecycle, aucun pending, aucune modification de `forge_engine.py`.

## 5. Périmètre exact — fichiers concernés

- `src/ui/pages/inference_page.py` (modifié) — constructeur (nouveau paramètre `comfyui_lifecycle_manager`), scission de `_start_generation()` en phase de snapshot/validation et phase de lancement effectif, nouveau champ `_pending_generation_request` et sa structure dédiée, nouveau handler `state_changed`, extension de `is_generation_active()`, extension des handlers de changement de contexte (`reset_for_workspace_change`/`reset_for_context_change`) et de `shutdown()`.
- `src/ui/main_window.py` (modifié) — passage de `self.comfyui_lifecycle_manager` à la construction d'`InferencePage` (actuellement 9 arguments positionnels, `main_window.py:442-452`).
- `tests/integration/test_inference_page.py` (modifié) — nouveaux tests, extension des classes existantes `InferencePageGenerationActiveGuardTest`/`InferencePageEngineSelectorTest`.
- Éventuellement un petit type/structure privé pour `PendingGenerationRequest` si jugé plus clair qu'un simple regroupement de variables — décision d'implémentation, pas un nouveau fichier `src/domain/`.
- Point de vérification non fonctionnel identifié par audit, à valider en implémentation : `tests/integration/test_training_roundtrip.py:3541-3544` construit déjà `InferencePage(...)` avec 9 arguments positionnels (`MagicMock()`) — l'ajout d'un 10e paramètre (avec valeur par défaut) doit être vérifié à cet endroit avant clôture.

**Aucun changement attendu** à `src/managers/generation_manager.py`, `src/ui/generation_worker.py`, `src/engines/comfyui_engine.py`, `src/ui/comfyui_lifecycle_manager.py`, `src/ui/pages/settings_page.py`, `src/engines/forge_engine.py` — si l'implémentation réelle révèle qu'un changement dans l'un de ces fichiers est nécessaire, arrêt et rapport avant tout élargissement.

## 6. Hors périmètre strict

- Lifecycle Forge (Start/Stop/ownership) — inchangé.
- Refonte de `SettingsPage`.
- ComfyUI Cloud (aucune abstraction Provider/Executor).
- Captioning assisté par IA.
- Toute forme de queue multi-générations (un seul pending, jamais plusieurs).
- Toute modification de `GenerationManager`.
- Toute modification environnementale (installation, venv, base de données ComfyUI).

## 7. Étape technique attendue

`InferencePage._start_generation()` est scindée en deux temps : une phase de validation/snapshot (code actuel jusqu'à la résolution de `target_engine_key`/`target_engine`, inchangée dans sa logique), produisant une structure de requête immuable ; puis soit un lancement immédiat du worker existant (code actuel inchangé, extrait dans une méthode privée prenant la requête en paramètre) si l'état lifecycle le permet, soit la mise en pending et l'attente du signal `state_changed`. Le handler `state_changed` compare l'état reçu aux constantes de module déjà exposées par `comfyui_lifecycle_manager.py` (mêmes constantes que celles importées par `SettingsPage`), vérifie l'identité du pending courant avant tout effet, et route vers : lancement de la génération (`RUNNING_OWNED`/`EXTERNAL_ACTIVE`), abandon avec `last_error_message` (`START_FAILED`), ou abandon avec message d'annulation (`STOPPED` atteint depuis `STOPPING` alors qu'un pending existait).

## 8. Tests attendus

- `RUNNING_OWNED` au clic → génération immédiate, `start()` jamais appelé.
- `EXTERNAL_ACTIVE` au clic → génération immédiate, aucun ownership pris.
- `STOPPED → STARTING → RUNNING_OWNED → Generate` : cycle complet (réutilisation du harnais de process factice déjà présent dans `tests/integration/test_comfyui_lifecycle_manager.py` — script factice, constantes de timing patchées), vérifiant que la génération lancée correspond exactement aux paramètres snapshotés au clic.
- `STARTING` déjà en cours au clic → rattachement, aucun second `start()` appelé (assertion sur le nombre d'appels).
- `START_FAILED` pendant l'attente → pending abandonné, UI réactivée, un seul message affichant `last_error_message`, `GenerationManager.generate()` jamais appelé.
- Stop déclenché ailleurs pendant l'attente (`STARTING → STOPPING → STOPPED`) → pending abandonné, message d'annulation distinct, aucun redémarrage automatique.
- Doubles clics Generate pendant l'attente → un seul pending, un seul appel `start()`.
- `is_generation_active()`/`confirm_no_active_generation()` retournent vrai/refusent correctement pendant un pending (extension de `InferencePageGenerationActiveGuardTest`).
- Changement de Workspace/contexte pendant l'attente → pending invalidé, un signal lifecycle tardif après ce changement n'a aucun effet.
- Valeurs Settings non sauvegardées → ignorées, seules les valeurs persistées de `application_settings_manager.settings` sont utilisées.
- Configuration ComfyUI vide/invalide → `START_FAILED` réel atteint via `resolve_comfyui_launch()`, `last_error_message` affiché tel quel.
- Forge sélectionné → comportement strictement inchangé, `comfyui_lifecycle_manager`/`start()` jamais sollicités.
- Instance lifecycle partagée : un seul `ComfyUILifecycleManager` piloté depuis `MainWindow`, observé de façon cohérente par `SettingsPage` et `InferencePage`.

## 9. Smoke réel prévu (non exécuté sans autorisation explicite)

**Scénario principal** : ComfyUI réellement fermé → prompt réel dans Inference → un seul clic Generate → Toolkit démarre réellement le process ComfyUI → attente readiness observée → la génération originellement demandée part automatiquement, sans second clic → image réellement produite. Vérifications complémentaires : PID/process réel, port réellement ouvert, état lifecycle observé à chaque transition, absence de process orphelin si un Stop est également exercé pendant ce smoke.

**Scénario secondaire léger** : ComfyUI externe déjà actif → Generate → génération immédiate, aucun nouveau process créé.

## 10. Critères de clôture

1. Les six états lifecycle couverts par test selon le tableau du §4, aucune régression sur le comportement Forge.
2. `is_generation_active()`/`confirm_no_active_generation()` couvrent la phase pending sans changer de signature.
3. Une seule instance `ComfyUILifecycleManager` observée par `MainWindow`/`SettingsPage`/`InferencePage`, démontré par test.
4. Aucune lecture des widgets `SettingsPage` depuis `InferencePage`, démontré par test (valeurs non sauvegardées sans effet).
5. Zéro modification de `GenerationManager`, `GenerationWorker`, `ComfyUIEngine`, `ComfyUILifecycleManager`, `SettingsPage`, `ForgeEngine` — sauf anomalie réelle découverte et rapportée avant tout élargissement.
6. Suite complète verte au nombre exact, `git diff --check` propre.
7. Aucun élément de la section 6 (hors périmètre) n'a été ajouté.
8. Smoke réel exécuté uniquement après autorisation explicite, les deux scénarios du §9 validés.

## 11. Documentation

Cette mission ferme, pour ComfyUI Local uniquement, le sous-point « auto-start déclenché depuis Inference » explicitement laissé hors périmètre par Mission 114 (`docs/missions/MISSION_114.md` §6). Forge et ComfyUI Cloud restent des sous-points ouverts, non affectés. La régularisation documentaire post-clôture suivra le même processus que les missions précédentes, après commit/tag/Release.

## 12. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte.

## 13. Correctif préalable découvert pendant la préparation du smoke réel — QScrollArea sur SettingsPage (hors périmètre fonctionnel de Mission 115)

Pendant la préparation du smoke réel Scénario A, un défaut fonctionnel réel et pré-existant a bloqué la persistance de `comfyui_install_path` (nécessaire pour tout `manager.start()` réel) : **`SettingsPage` était un unique `QVBoxLayout` sans aucun `QScrollArea`**. Le bouton `application_save_button` (« Enregistrer » de la section Application), ajouté après « Rafraîchir les modèles », se trouvait physiquement inatteignable dès que le contenu réel de la page — accumulé sur de nombreuses missions (M087/M108/M112/M113/M114) — dépassait la hauteur d'une fenêtre normale, sans aucune barre de défilement pour l'atteindre. Conséquence directe : `comfyui_install_path` n'avait jamais pu être sauvegardé depuis l'UI sur la machine de référence, ce qui aurait fait échouer systématiquement le smoke réel M115 (`STOPPED → START_FAILED` immédiat, configuration incomplète) sans rapport avec le code de cette mission.

**Ce correctif ne fait pas partie du périmètre fonctionnel de Mission 115** — il s'agit d'un défaut UI pré-existant, découvert par nécessité, documenté et corrigé séparément (commit distinct, hors tag `v0.2-mission115`) : encapsulation du contenu déjà existant de `SettingsPage` dans un `QScrollArea` (`setWidgetResizable(True)`), sans aucun changement de la logique de sauvegarde (`save_application_settings()` inchangée), sans réorganisation des sections, sans onglets. La réorganisation complète de `SettingsPage` (dette déjà documentée dans `docs/PROJECT_CONTEXT.md` depuis Mission 101/102) reste un chantier distinct, non traité ici.

**Validation** : 3 tests dédiés ajoutés (`SettingsPageScrollableContentTest` — présence d'un `QScrollArea` unique redimensionnable, `application_save_button` réellement descendant du contenu défilé, sauvegarde réelle toujours fonctionnelle à travers la zone de défilement) ; `tests/integration/test_settings_page.py` : **74/74** ; `tests/integration/test_main_window_initial_size.py` : **5/5** (aucune régression sur l'agrégation de taille du `QStackedWidget`) ; suite complète : **2309/2309**. Confirmé manuellement par l'architecte : redémarrage réel d'AI Studio Toolkit, page désormais défilable, `comfyui_install_path = C:\Users\dlero\AppData\Local\Programs\ComfyUI` réellement sauvegardé et confirmé présent dans `application_settings.json`.

## 14. Smoke réel — résultats

Les deux scénarios prévus au §9 ont été exécutés réellement (ComfyUI fermé au départ, jamais lancé manuellement par l'architecte pour le Scénario A) et ont tous deux **PASS** :

- **Scénario A — `STOPPED → STARTING → RUNNING_OWNED → génération réelle`** : clic Generate unique depuis Inference avec ComfyUI réellement fermé → pending créé → `manager.start(...)` → process réel lancé (PID confirmé) → `RUNNING_OWNED` atteint 45,3s après le clic → pending automatiquement consommé (aucun second clic) → génération réelle soumise à ComfyUI → image réellement produite et confirmée sur disque (45,7s). Aucune boîte de dialogue, aucun traceback. Observation complémentaire (sans rapport avec le code M115) : le process ComfyUI possédé s'est arrêté avec l'interpréteur Python du script de smoke lui-même (destructeur `QProcess` de Qt), sans jamais laisser de processus orphelin.
- **Scénario B — `EXTERNAL_ACTIVE → génération immédiate sans ownership`** : ComfyUI démarré hors du lifecycle Toolkit (process lancé directement, jamais via `ComfyUILifecycleManager`/`QProcess`, avec la commande réelle exacte que `resolve_comfyui_launch()` calcule) → clic Generate → transition immédiate et directe vers `EXTERNAL_ACTIVE` (aucun état `STARTING` intermédiaire) → aucun pending créé → `manager.start()` interne jamais engagé au-delà du check de disponibilité → aucun ownership pris (`_process is None`) → génération réelle aboutie (42,55s côté ComfyUI) → backend externe confirmé toujours actif et joignable après la génération, puis après la destruction de la fenêtre Toolkit elle-même — jamais arrêté par Toolkit.

Les deux branches principales du contrat (§4) sont ainsi validées en conditions réelles, sans mock, sans second clic utilisateur, sans anomalie.
