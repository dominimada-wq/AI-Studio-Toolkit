# Mission 014 — Validation post-génération avant enregistrement

Source : historique direct de la conversation de développement (audit architectural préalable, implémentation, revue technique finale ayant identifié et corrigé un défaut réel de liaison pending/Workspace, smoke test réel complet contre ComfyUI Desktop couvrant six scénarios), vérifié contre le code réel et la suite de tests.

## Objectif

Introduire une étape de validation explicite entre la génération et sa persistance dans `Workspace.images` :

```
Generate
  → résultat temporaire (pending)
  → Preview
  → Accept / Reject / Regenerate
```

Règle fondamentale : **seule l'action explicite Accept transforme un résultat temporaire en `Image` persistée dans `Workspace.images`.** Avant Mission 014, une génération réussie était automatiquement ajoutée à `Workspace.images` dès que `GenerationWorker` émettait `finished(path)` (Mission 013) — ce comportement disparaît.

## Architecture

- L'état `pending` (`_pending_path`, `_pending_pixmap`) appartient exclusivement à `InferencePage` — état UI transitoire, jamais persisté, jamais partagé avec un autre composant.
- Un second état transitoire, `_generation_workspace_root`, mémorise le Workspace actif au lancement du cycle de génération en cours (voir section dédiée "Protection changement de Workspace" ci-dessous).
- **Aucun nouveau Domain** : pas de classe `GenerationResult`/`PendingImage` — un scalaire (chemin) et une référence (racine Workspace) suffisent, portés par de simples attributs d'instance d'`InferencePage`.
- **Aucun nouveau Manager** : `GenerationManager` reste strictement inchangé (contrat `generate(prompt_text, output_directory) -> str` identique à Mission 013).
- **`GenerationWorker` inchangé** : signaux `finished(str)`/`failed(str)` identiques ; c'est uniquement ce qu'`InferencePage` fait de `path` dans son slot `_on_generation_finished` qui change.
- **`ComfyUIEngine` inchangé** : aucune modification, aucun nouveau paramètre.
- **Aucun nouveau canal EventBus** : `WORKSPACE_SAVED` continue de ne se déclencher que via `WorkspaceManager.save()`, désormais uniquement appelé après Accept (au lieu de systématiquement après chaque génération) — effet secondaire positif, pas un nouveau canal.
- **Aperçu** : `QLabel`/`QPixmap` (PySide6, déjà une dépendance du projet) — aucune dépendance nouvelle, pas de Pillow.
- **Mécanisme `QThread` de Mission 013 réutilisé tel quel** : `_start_generation()` (renommée depuis l'ancien `_on_generate_clicked` pour être appelée aussi bien par le clic Generate que par Regenerate) crée `QObject`/`QThread`, avec la capture par valeur de `worker`/`thread` dans le callback `thread.finished` et la remise à `None` conditionnée par identité (correctif de course Mission 013) — strictement inchangée dans son fonctionnement interne.
- **`main_window.py`** : seule modification de composition root — abonnement de `inference_page.reset_for_workspace_change` à `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED` (voir "Protection changement de Workspace"). `InferencePage` elle-même ne reçoit toujours pas l'`event_bus` en dépendance — conforme au pattern déjà établi où seul `MainWindow` connecte les Pages aux événements, les Pages n'exposant que de simples méthodes callback.

## State machine

| État | Generate | Accept | Reject | Regenerate | `_pending_path` | `_generation_workspace_root` | Thread/worker |
|---|---|---|---|---|---|---|---|
| INITIAL | actif | inactif | inactif | inactif | `None` | `None` | `None` |
| GENERATING | inactif | inactif | inactif | inactif | `None` | racine du Workspace au lancement | en cours |
| PENDING | inactif | actif | actif | actif | chemin du fichier téléchargé | racine mémorisée au lancement | `None` (ou transitoirement non-`None` jusqu'à `thread.finished`) |
| ACCEPT | → INITIAL | | | | `None` | `None` | `None` |
| REJECT | → INITIAL | | | | `None` | `None` | `None` |
| REGENERATE | → GENERATING immédiatement (ancien pending supprimé, prompt conservé) | | | | | | |
| ERROR | → INITIAL (aucun pending n'a jamais existé) | | | | `None` | `None` | `None` |
| WORKSPACE_CHANGED (depuis PENDING) | → INITIAL | | | | `None` | `None` | `None` |
| WORKSPACE_CHANGED (depuis GENERATING) | inchangé (reste inactif, aucune annulation) | | | | `None` | racine obsolète, sert uniquement à la détection au retour du worker | en cours, non annulé |
| SHUTDOWN | non pertinent (fermeture) | | | | `None` (nettoyé) | `None` | attendu puis nettoyé |

Aucun chemin ne permet : double Accept (garde `_pending_path is None` + désactivation bouton, vérifiés aux deux niveaux) ; Accept dans le mauvais Workspace (garde de correspondance + invalidation proactive) ; Generate et Regenerate actifs simultanément (jamais vrais ensemble par construction) ; persistance d'un résultat rejeté ; perte de références `QThread` ou cleanup d'un ancien cycle touchant un nouveau cycle (mécanisme Mission 013 intact).

## Ownership / persistance

- Une génération réussie **n'est plus jamais enregistrée automatiquement** dans `Workspace.images`.
- Avant Accept : aucune entrée `Workspace.images`, aucune écriture dans `project.json`.
- **Accept** → `WorkspaceManager.add_images([pending_path])` (déjà existant depuis Mission 006/011, appelé depuis le thread principal, inchangé) → `save()` → `WORKSPACE_SAVED`.
- **Reject** → aucune persistance, suppression du fichier temporaire.
- **Regenerate** → l'ancien résultat n'est jamais persisté, quelle que soit l'issue de sa suppression.
- **Changement de Workspace** (Nouveau projet / Ouvrir un projet) → le résultat de l'ancien Workspace est invalidé, jamais persisté dans le nouveau.
- **Shutdown avec résultat pending** → aucune persistance, nettoyage du fichier.
- `Dataset.images` n'est à aucun moment lu, modifié ou référencé par cette verticale — inchangé depuis Mission 013.

## Protection changement de Workspace

**Défaut identifié pendant la revue technique finale, avant toute correction** : ni le passage en pending (`_on_generation_finished`) ni Accept (`_on_accept_clicked`) ne vérifiaient que le Workspace actif au moment de l'action était le même que celui actif au lancement de la génération. `WorkspaceManager.create()`/`.open()` réassignent `current_workspace` à un nouvel objet sans jamais appeler `close()` — un résultat né dans le Workspace A aurait donc pu être silencieusement enregistré dans un Workspace B ouvert entre-temps.

Correction retenue :

- Le Workspace actif est mémorisé (`self._generation_workspace_root`) au moment exact où `_start_generation()` calcule `output_directory` — même source, même instant.
- **Vérification avant création du pending** : `_on_generation_finished(path)` compare le Workspace actif à ce moment à la racine mémorisée ; en cas de désaccord, le fichier est supprimé silencieusement et n'est jamais présenté comme pending (couvre le cas où le Workspace change *pendant* que le worker tourne encore).
- **Vérification à Accept** : `_on_accept_clicked()` revérifie la même correspondance juste avant `add_images()`, défense en profondeur si `reset_for_workspace_change` n'avait pas encore été délivré.
- **Invalidation proactive** : `InferencePage.reset_for_workspace_change()`, abonnée par `main_window.py` à `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED` (jamais `WORKSPACE_SAVED`, pour ne pas invalider un pending à cause d'une simple sauvegarde manuelle sans rapport), nettoie immédiatement un pending existant dès que le contexte change — sans attendre une tentative d'Accept.

Résultat : **une image du Workspace A ne peut structurellement jamais être enregistrée dans un Workspace B**, vérifié par test automatisé et par smoke test réel (scénario E).

## Gestion filesystem

- **Fichier pending absent à Accept** : `Path(pending_path).exists()` vérifié avant `add_images()` ; si absent, `QMessageBox.warning`, pending nettoyé sans persistance.
- **`FileNotFoundError` au nettoyage** (`_delete_pending_file`) : traitée comme un **succès** — l'état désiré ("plus de fichier") est déjà atteint, aucun avertissement affiché (éviter un faux positif confus pour l'utilisateur).
- **`OSError` réelle** (fichier toujours présent, ex. permission refusée) : `QMessageBox.warning` informe l'utilisateur ; pour Reject, l'état pending est tout de même libéré (aucune incohérence Domain possible, le fichier n'a jamais été référencé) ; pour Regenerate, une nouvelle génération démarre malgré tout, avec avertissement.
- **Possibilité résiduelle d'un fichier orphelin** : si `unlink()` échoue réellement (permission refusée, fichier verrouillé), le fichier peut rester sur disque — limite acceptée, non résolue davantage (pas de nouvelle tentative, pas de nettoyage différé).

## Aperçu

- `QLabel` + `QPixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)`, recalculé dans `resizeEvent` — ratio conservé, redimensionnement dynamique avec la fenêtre.
- Aucune nouvelle dépendance (`QPixmap`/`QLabel` déjà fournis par PySide6, déjà une dépendance du projet).
- **Si `QPixmap` ne peut pas charger le fichier** (`pixmap.isNull()`) : le pending reste valide, Accept reste possible. Le téléchargement via `ComfyUIEngine.download_output()` a réussi (octets réels reçus) — l'incapacité de Qt à décoder ces octets comme image affichable n'implique pas que le fichier soit corrompu ou invalide en tant qu'artefact généré ; construire une détection de corruption aurait été une validation de contenu hors périmètre. Décision explicitement réévaluée en revue technique finale et conservée telle quelle.

## Tests

**159/159 tests d'intégration verts** (nombre exact confirmé par exécution complète après revue technique finale et smoke test réel) — 138 précédents (base Mission 013) + 21 nets nouveaux dans `test_inference_page.py` (9 → 30 tests). `test_generation_manager.py` (10), `test_generation_worker.py` (4) et `test_comfyui_engine.py` (25) restent strictement inchangés.

`test_inference_page.py` (30 tests) couvre notamment :

- **Preview sans persistance** : `test_successful_generation_shows_pending_result_without_persisting`, `test_preview_shows_pixmap_for_a_valid_image_file`, `test_preview_is_cleared_for_an_unreadable_image_file`.
- **Accept exactement une fois** : `test_accept_persists_pending_image_exactly_once` (spy sur `add_images`, appel unique vérifié explicitement), `test_double_click_accept_does_not_persist_twice`, `test_direct_double_call_accept_does_not_persist_twice`, `test_accept_with_no_pending_result_is_a_no_op`.
- **Reject** : `test_reject_deletes_pending_file_without_persisting`, `test_reject_when_pending_file_already_missing_does_not_crash`.
- **Regenerate** : `test_regenerate_deletes_old_pending_keeps_prompt_and_starts_new_cycle`, `test_regenerate_with_no_pending_result_is_a_no_op`, `test_regenerate_deletion_error_still_starts_a_new_generation`.
- **Changement de Workspace pendant pending** : `test_workspace_switch_before_accept_never_persists_into_new_workspace`, `test_workspace_open_invalidates_pending_and_resets_ui`, `test_workspace_close_invalidates_pending`.
- **Changement de Workspace pendant génération** : `test_workspace_switch_during_in_flight_generation_is_never_persisted`.
- **Fichier disparu avant Accept** : `test_accept_with_pending_file_missing_persists_nothing`.
- **Cleanup filesystem (erreurs de suppression)** : `test_deletion_error_is_handled_without_crashing`, `test_regenerate_deletion_error_still_starts_a_new_generation`.
- **Shutdown avec pending** : `test_shutdown_with_pending_result_deletes_file_without_persisting`, `test_shutdown_without_pending_result_does_nothing_special`.
- **Races `QThread` Mission 013 toujours protégées** : `test_cleanup_of_an_old_cycle_never_touches_a_newer_cycles_references`, `test_cleanup_resets_references_only_when_they_still_belong_to_this_cycle`, `test_rapid_regenerate_after_success_is_safe` (variante Mission 014 du test de course, déclenchée via Regenerate puisque Generate reste désormais désactivé après succès), `test_rapid_second_click_after_error_is_safe` — aucune régression, tous verts avec de vrais `QThread` et capture `qInstallMessageHandler`.
- Cycle complet répété (`test_second_full_cycle_after_accept_runs_a_fresh_qthread_cycle`), non-blocage UI (`test_click_disables_button_immediately_and_ui_is_not_blocked`), génération normale après changement de Workspace (`test_generation_in_new_workspace_after_switch_works_normally`).

Suite entièrement mockée (`GenerationManager` mocké), aucun accès réseau réel, aucune instance ComfyUI, aucun GPU dans les tests automatisés.

## Smoke test réel

Réalisé depuis la vraie interface (`src/core/main.py`, wiring de production réel), backend ComfyUI Desktop `0.24.1` réellement détecté sur `http://127.0.0.1:8000` (port non supposé, vérifié via `/system_stats`), GPU Quadro P4000, checkpoint `v1-5-pruned-emaonly-fp16.safetensors` confirmé disponible. Deux Workspaces de test dédiés hors dépôt (`Mission014-SmokeTest-A`, `Mission014-SmokeTest-B`).

Six scénarios réellement exécutés et observés :

- **A — Generate → Preview → Accept** : génération réelle ("a red cube on a white background"), `Workspace.images` et `project.json` vérifiés vides avant Accept, aperçu réellement visible pendant que l'UI restait responsive (navigation vers `ImagesPage` pendant la génération), Accept → image ajoutée exactement une fois, `project.json` mis à jour, `ImagesPage` rafraîchie automatiquement sans action manuelle.
- **B — Generate → Preview → Reject** : deuxième génération réelle, fichier temporaire noté avant Reject, `project.json` vérifié inchangé avant et après Reject, fichier confirmé supprimé du disque.
- **C — Generate → Preview → Regenerate → Preview → Accept** : troisième génération réelle, premier pending noté, Regenerate → ancien fichier supprimé immédiatement, prompt conservé, nouveau cycle `QThread` réel avec boutons correctement verrouillés pendant la génération, nouvel aperçu visuellement distinct, `project.json` revérifié à 1 seule image juste avant l'Accept final (preuve que le résultat régénéré intermédiaire n'a jamais été persisté), Accept final → exactement 2 images dans `Workspace.images` (résultat A + résultat régénéré de C).
- **D — Persistance/reload** : Workspace A fermé puis rouvert via l'UI réelle (File → Ouvrir un projet) — exactement les 2 images acceptées retrouvées, `image_id` stables, aucune trace des résultats rejetés/régénérés intermédiaires, fichiers présents sur disque.
- **E — Changement de Workspace A → B avec pending** : génération réelle dans A laissée pending, création du Workspace B sans Accept ni Reject → immédiatement : pending de A disparu, aperçu vidé, boutons de validation désactivés, `Générer` disponible dans B, fichier temporaire de A supprimé du disque, `project.json` de A inchangé, `project.json` de B vide. Génération et Accept ensuite réalisés normalement dans B → image enregistrée uniquement dans B, A resté strictement inchangé.
- **F — Fermeture application avec pending terminé** : génération menée à son terme dans B (aucune fermeture pendant une génération en cours, conformément à la limite de shutdown de Mission 013), résultat pending noté, fermeture normale (File → Quitter) sans Accept ni Reject → processus terminé proprement (PID disparu), fichier pending supprimé du disque, `project.json` de B inchangé (toujours uniquement l'image acceptée précédente), aucun message Qt anormal observé (sortie process vide sur toute la session).

Contrôles finaux réellement effectués : fichiers de `J:\Programmes\ComfyUI\output` (répertoire propre à ComfyUI, jamais géré par AI Studio Toolkit) comparés aux copies téléchargées dans les dossiers `outputs/` de chaque Workspace — confirmé que l'historique interne de ComfyUI conserve tous les fichiers générés (y compris les rejetés/régénérés), tandis que seules les copies des résultats acceptés subsistent côté Workspace ; aucun message Qt anormal ; dépôt Git strictement inchangé (`git status --short`/`git diff --stat` identiques avant et après le smoke test).

Aucune divergence entre le comportement automatisé (tests) et le comportement réel observé.

## Limites

- **Shutdown pendant une génération en cours** : toujours sans annulation HTTP réelle (limite Mission 013, non révisée par Mission 014) — `thread.quit()+wait()` ne peut interrompre un appel `ComfyUIEngine` déjà en vol ; non testé empiriquement pendant ce smoke test (la fermeture n'a été testée qu'après génération terminée, conformément aux instructions).
- **Fichier orphelin résiduel possible** si `unlink()` échoue réellement lors d'un nettoyage (Reject/Regenerate/changement de Workspace/shutdown) — non résolu, limite acceptée.
- Toujours hors périmètre, non implémentés : galerie/miniatures `ImagesPage`, images de référence pour `InferencePage`, sélection multi-engine/backend, historique de générations (rejets/régénérations passées), sélection de checkpoint, annulation réelle d'une génération en cours.

## Fichiers modifiés

- `src/ui/pages/inference_page.py` (logique de validation post-génération, state machine complète)
- `src/ui/main_window.py` (abonnement `reset_for_workspace_change` à 3 des 4 événements Workspace)
- `tests/integration/test_inference_page.py` (9 → 30 tests)

Aucun fichier créé. Aucun fichier hors ce périmètre (pas de nouveau Domain, Manager, Job, Service, Plugin, AI Orchestrator ; `requirements.txt` inchangé). Liste vérifiée directement depuis `git status --short`/`git diff --stat`.

## Critères d'acceptation — état final

- Une génération réussie n'est plus jamais automatiquement persistée : ✅, vérifié par test automatisé et smoke test réel.
- Aperçu visible et de taille exploitable avant toute décision, ratio conservé : ✅.
- Accept persiste exactement comme le faisait Mission 013 (simplement différé) : ✅.
- Reject ne persiste rien et supprime le fichier temporaire : ✅.
- Regenerate conserve le prompt, supprime l'ancien résultat, ne le persiste jamais : ✅.
- Un résultat pending ne peut structurellement jamais être persisté dans un Workspace différent de celui où il a été généré : ✅, défaut réel trouvé en revue et corrigé avant clôture, vérifié par test automatisé et smoke test réel (scénario E).
- Fermeture avec résultat pending terminé : aucune persistance, nettoyage propre : ✅.
- Condition de course `QThread` Mission 013 non affaiblie : ✅, tests dédiés toujours verts.
- Aucun nouveau Domain/Manager/Job/Service/Plugin/AI Orchestrator/dépendance/événement EventBus : ✅.
- Suite de tests complète verte, nombre exact confirmé : ✅ (159/159).
- Smoke test réel complet, six scénarios validés : ✅.
- Documentation de fin de mission complète : ✅ (ce document + `docs/PROJECT_CONTEXT.md`).

## Dettes hors périmètre (volontairement non traitées par Mission 014)

- Limite shutdown sans annulation réelle pendant une génération active (Mission 013, non résolue).
- Possibilité résiduelle de fichier orphelin sur échec réel de suppression (voir "Gestion filesystem").
- Les besoins déjà identifiés en Mission 013 (galerie `ImagesPage`, images de référence, sélection multi-engine) — toujours non implémentés.
- Nouveau besoin identifié par l'usage réel de Mission 014 (aperçu agrandi/plein écran) — voir `docs/PROJECT_CONTEXT.md`, non implémenté.
- Toutes les dettes déjà connues avant Mission 014 (ambiguïté `Training`/`Training History`, `BasePage` mort, incohérences Blueprint `Job`, support Linux/macOS `ApplicationSettingsStorage`) — inchangées.

## Commit correspondant

Mission 014 sera clôturée en commit(s) après validation. Conformément au principe de non-auto-référence adopté après Mission 011, aucun hash ni message définitif n'est fixé en dur dans ce document avant la création du commit — vérifier avec `git rev-parse HEAD` ou en recherchant le message exact dans `git log` une fois la clôture Git effectuée.

## Tag / release correspondant

À créer après validation explicite, selon la convention établie (`v0.2-mission014`). Cible exacte non fixée en dur ici — vérifier avec `git rev-list -n 1 v0.2-mission014` une fois créé.

## État final

Mission terminée. `InferencePage` introduit une étape de validation explicite entre génération et persistance (`Generate → Preview → Accept/Reject/Regenerate`), avec protection structurelle contre tout enregistrement croisé entre Workspaces — défaut réel trouvé en revue technique finale et corrigé avant clôture. Validée par 159 tests automatisés entièrement mockés et par un smoke test réel complet (six scénarios, deux Workspaces, contre ComfyUI Desktop réel). Un nouveau besoin futur (aperçu agrandi/plein écran) a été identifié par l'usage réel, sans être architecturé ni implémenté. Mission 015 non définie ; nécessitera son propre audit architectural, qui devra notamment tenir compte des cinq besoins réels désormais identifiés (voir `docs/PROJECT_CONTEXT.md`).
