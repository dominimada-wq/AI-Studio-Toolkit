# Mission 166 — Remap TrainingJob Paths When Renaming a Workspace

> **IMPLÉMENTATION VALIDÉE PAR REVUE ARCHITECTE — publication en attente.** `WorkspaceManager.rename()` déplaçait le dossier du Workspace et remappait les chemins internes de ses Images, Datasets, LoRA, Modèles et Workflows, mais pas les trois chemins absolus persistés de chaque `TrainingJob` (`config_snapshot_path`, `expected_output_path`, `final_output_path`). Après un renommage de projet, un Job réussi pointait toujours vers l'ancienne racine : sa ligne affichait « fichier introuvable » et le bouton d'import était désactivé, alors que le fichier existait bien sous la nouvelle racine. Découvert par l'audit global post-Mission 165 (candidat H), conçu READ-ONLY, puis implémenté strictement dans le périmètre validé : `_build_renamed_payload()` uniquement. Mission non close : push, tag et Release restent à venir.

## 1. Défaut initial

`src/managers/workspace_manager.py::_build_renamed_payload()` remappait `Workspace.images`, `Character.datasets[].images`, `Character.loras[].files/thumbnail`, `Workspace.models` et `Workspace.workflows`, mais ignorait `Character.trainings[].jobs[]`. Ces chemins sont absolus et persistés dans `project.json` ; le Domain reconstruit après renommage (`Workspace.from_dict`) et le `project.json` réécrit conservaient donc l'ancienne racine, y compris après fermeture et réouverture du projet.

## 2. Preuve empirique (état antérieur à la correction)

Sonde sur un `MainWindow` réel, plateforme Windows native. Ce qui est construit : un Dataset avec une image PNG, un fichier de sortie factice, un double de `RenameProjectDialog` et un `QMessageBox` simulé. Ce qui passe par la production : `TrainingManager.create/select/update/prepare_onetrainer_config/create_job/update_job_state`, l'action de menu `action_rename_project.trigger()`, `MainWindow.rename_project()`, `WorkspaceManager.rename()` et `TrainingPage`.

| Étape | Résultat |
|---|---|
| Avant renommage | les 3 chemins existent ; ligne du Job « succeeded — importable » ; bouton d'import activé |
| Après renommage (racine `OldProj` → `NewProj`) | les 3 chemins pointent encore sous `OldProj` et n'existent pas ; ligne « succeeded — fichier introuvable » ; bouton d'import désactivé ; le fichier existe sous `NewProj` |
| `project.json` | contient `OldProj` pour les 3 champs |
| Après réouverture | `final_output_path` toujours sous l'ancienne racine |

Aucun entraînement OneTrainer ni import réel n'a été exécuté : les objets, chemins et fichiers reproduisent le contrat de `create_job()` et d'`update_job_state()`.

## 3. Contrat des trois champs

- `config_snapshot_path` : non vide pour tout vrai Job, interne par construction (`training/<id>/jobs/<job>/onetrainer_config.json`) ; valeur historique, jamais relue depuis le Domain (le runner recalcule via `job_paths()`).
- `expected_output_path` : non vide pour tout vrai Job, interne par construction ; le fichier peut ne pas encore exister (Job actif, échoué, annulé, inconnu) ; valeur historique, recalculée par le runner.
- `final_output_path` : vide sauf Job réussi ; en production égal à `expected_output_path` quand il est renseigné ; **seul champ opérationnel** (affichage de la ligne, `_importable_job()`, revalidation et copie à l'import).
- Le schéma n'impose aucun type : `from_dict` fait `data.get(clé, "")` sans garde.

## 4. Correction

**Production (1 fichier)** : `src/managers/workspace_manager.py`. `_build_renamed_payload()` parcourt désormais, dans chaque Character sérialisé (`character["trainings"]`), chaque Training puis chaque Job (`training["jobs"]`) et applique à `config_snapshot_path`, `expected_output_path` et `final_output_path` le helper existant `_remap_path(valeur, old_root_resolved, new_root)`, avec exactement les arguments des autres chemins. Les docstrings de `rename()` et de `_build_renamed_payload()` sont mises à jour.

Comportement conservé du helper, vérifié par sonde avant l'implémentation : un chemin interne est remappé **même si le fichier n'existe pas** ; un chemin externe est inchangé ; `""` et `None` sont retournés tels quels ; la comparaison se fait composant par composant, donc `Old` n'est pas confondu avec `OldBackup` ; la casse Windows est traitée par `normcase`. Aucune dérivation de `final_output_path` à partir d'`expected_output_path`, aucune nouvelle normalisation ni validation.

Le payload est préparé **avant** toute mutation, puis écrit et appliqué par la transaction de renommage existante, inchangée : déplacement du dossier, écriture atomique de `project.json`, retour arrière du dossier en cas d'échec de sauvegarde, remplacement de l'état en mémoire seulement après réussite complète, puis `WORKSPACE_RENAMED`.

## 5. Fichiers modifiés

- `src/managers/workspace_manager.py` (production, 28 lignes touchées).
- `tests/integration/test_workspace_roundtrip.py` — classe `WorkspaceRenameTrainingJobPathsTest` (11 tests) ; imports `Training` et `TrainingJob`.
- `tests/integration/test_main_window_rename_project.py` — classe `MainWindowRenameTrainingJobPathsTest` (1 test) ; imports ajoutés.
- `docs/missions/MISSION_166.md` (ce document).

Aucun changement Domain, Storage, UI, runner ni garde M161.

## 6. Tests ajoutés (12)

**`WorkspaceRenameTrainingJobPathsTest`** (11, Manager-level) : état Domain construit directement, `WorkspaceManager.rename()` exercé réellement.
- les trois chemins internes remappés, fichiers physiquement accessibles après le déplacement (test principal) ;
- `expected_output_path` inexistant remappé ;
- valeurs `""` et `None` préservées ;
- chemins externes inchangés ;
- dossier voisin partageant seulement un préfixe textuel (`OldNameBackup`, et `OldNameX` inexistant) inchangé, tandis qu'un autre champ du même Job, réellement interne, est remappé ;
- plusieurs Characters (dont un non principal), plusieurs Trainings, six Jobs dans les états `starting`, `running`, `succeeded`, `failed`, `cancelled` et `unknown` : tous remappés, autres champs des Jobs et des Trainings strictement inchangés ;
- persistance vérifiée dans `project.json` puis après fermeture et réouverture ;
- deux renommages successifs ;
- échec du déplacement : chemins, mémoire et `project.json` octet pour octet inchangés ;
- échec de sauvegarde après le déplacement : dossier restauré, nouveau dossier absent, même objet `Workspace` avec chemins d'origine, fichier de sortie accessible, `project.json` identique octet pour octet, aucun `WORKSPACE_RENAMED` ;
- non-régression des champs déjà remappés (Images, Models, Workflows, LoRA, Dataset) avec un chemin de Job.

Les scénarios qui construisent des Jobs `starting`/`running` testent le remappage du Manager seul ; ils ne prétendent pas que l'UI autorise un renommage pendant un entraînement actif (`MainWindow.rename_project()` le refuse avant d'ouvrir le dialogue).

**`MainWindowRenameTrainingJobPathsTest`** (1, `MainWindow()` réel) :
- Job créé par `create_job()`, sortie factice, Job `SUCCEEDED` via `update_job_state()` ;
- avant renommage : ligne « importable » et bouton d'import activé ;
- le callback réel `WORKSPACE_RENAMED → TrainingPage.update_trainings` est enveloppé dans la liste des abonnés de l'`EventBus` (appelé exactement une fois) ;
- `rename_project()` avec le dialogue simulé ; aucun appel manuel à `update_trainings()` ensuite ;
- le Job est relu depuis le Workspace courant reconstruit, jamais depuis une ancienne référence Python ;
- trois chemins sous la nouvelle racine, fichiers de configuration et de sortie existants (contenu vérifié), ligne « importable » (sans « fichier introuvable »), bouton d'import activé, `_importable_job()` retourne ce Job.

**Limite** : ce test ne réalise ni entraînement OneTrainer ni import réel vers la bibliothèque ; il vérifie l'état « importable », le bouton, les chemins et les fichiers. Dispositif : filet anti-dialogue du projet armé en premier et arrêté en dernier ; dossier temporaire enregistré avant la fenêtre, donc fenêtre fermée avant la suppression du dossier.

## 7. Résultats

**Preuve avant/après** (seul le fichier de production mis de côté par `git stash push -- src/managers/workspace_manager.py`, puis restauré ; diff de production vérifié identique après restauration, aucun stash restant) :
- contre la production antérieure : 12 tests exécutés, **9 échecs d'assertion** (aucune erreur), 3 réussites — les trois réussites sont les invariants déjà vrais avant la correction (chemins externes inchangés, échec du déplacement, échec de sauvegarde avec retour arrière) ;
- les 9 échecs sont des assertions de valeur (`...\OldName\...` != `...\NewName\...`), dont le test principal, le test de réouverture, le test des états, le test du préfixe, le test d'`expected_output_path` inexistant, le test des valeurs vides/None, les renommages successifs, la non-régression combinée et le test d'intégration `MainWindow` ;
- contre la production corrigée : **12/12 OK**.

**Validation après correction** (premier plan, sortie non tamponnée `-u`, aucune exécution concurrente, vrai code de sortie du processus) :
- tests ciblés : 12/12, code de sortie 0 ;
- `test_workspace_roundtrip.py` : 118/118 (107 avant la mission), code 0 ;
- `test_main_window_rename_project.py` : 23/23 (22 avant), code 0 ;
- non-régression Training (`test_training_roundtrip.py` + `test_training_job_runner.py`) : 405/405, code 0 ;
- **suite complète** : **3014 tests, OK, code de sortie 0, 345,295 s** (17:30:55 → 17:36:44) ; 3002 (référence M165) + 12 nets = 3014 ; aucune ligne `FAIL`/`ERROR` dans la sortie ; aucun incident d'exécution des tests (voir l'incident de fins de ligne ci-dessous) ;
- `git diff --check` : propre. 1 fichier de production et 2 fichiers de test modifiés, plus ce document.

**Incident de fins de ligne (corrigé, conservé pour traçabilité)** : le `git stash pop` de la preuve avant/après a réécrit `src/managers/workspace_manager.py` en CRLF (`core.autocrlf=true`), alors que ce fichier est en LF dans la copie de travail. Constaté lors de la vérification des fins de ligne du fichier de revue, avant toute transmission ; fichier ramené en LF (contenu inchangé, `git diff --numstat` identique : 26 ajouts, 2 suppressions). Les tests ciblés, les deux fichiers, la non-régression Training et la suite complète ont ensuite été **réexécutés sur l'état final** ; les résultats ci-dessus sont ceux de cette réexécution (une première suite complète, avant la correction des fins de ligne, avait donné 3014 tests OK, code 0, 351,548 s).

## 8. Job différé M161 : chemin examiné

Un Job « différé » (processus terminé, état terminal non persisté) reste marqué actif tout en permettant un renommage, car `is_training_active()` l'exempte. Examiné lors de la conception, limité aux parcours UI étudiés :
- après le report, `_on_job_finished` ne conserve aucun chemin : `kwargs` est une variable locale, `_active_runner` et `_active_job_id` sont remis à `None`, le runner n'est plus vivant ; seul `_deferred_job_id` (un identifiant) subsiste ;
- `update_job_state` n'a que trois appelants de production (`_on_job_started` sans chemin, `_recover_stale_jobs` sans chemin, `_on_job_finished` pendant la boucle) ; après report et renommage, `_on_job_started`, `cancel_training` et `start_training` n'écrivent rien ; à la réouverture le Job devient `unknown` avec `final_output_path` vide ;
- le Job différé garde `final_output_path` vide ; ses `config_snapshot_path` et `expected_output_path` sont remappés comme les autres ;
- **la non-réinjection d'un chemin capturé sous l'ancienne racine repose sur la modalité de la boîte « Réessayer » (application-modale, vérifiée) et sur le fait que `rename_project()` (action de menu) est l'unique appelant de production de `WorkspaceManager.rename()` — pas sur les données.** Un contrefactuel (renommage forcé pendant la boîte ouverte, modalité contournée) réinjecte bien l'ancien chemin ; ce scénario n'est pas atteignable par l'UI examinée. Un `QAction.trigger()` programmatique n'est pas bloqué par la modalité ; aucun clic réel de souris n'a été testé pendant la boîte ouverte.

Le résultat d'un Job différé n'est jamais enregistré comme réussi (comportement M161 inchangé) : il n'est donc pas importable, même si le fichier existe.

## 9. Limites et hors périmètre

- **Aucune réparation rétroactive** : les projets déjà renommés avant cette mission gardent leurs chemins périmés (ni migration, ni recherche heuristique) ; un nouveau renommage ne les corrige pas, ces chemins étant externes à la racine courante. Récupération actuelle : import manuel depuis le disque du fichier présent sous `training/<id>/jobs/<job>/output/`.
- **Contenu des configurations non réécrit** : les `onetrainer_config.json` sur disque (snapshot figé du Job, copie de niveau Training) conservent des chemins absolus de l'ancienne racine dans leur contenu. Le snapshot d'un Job terminé n'est relu nulle part ; la copie de niveau Training est régénérée à chaque Start. Une éventuelle future reprise d'entraînement devrait traiter ce point.
- **Nouveaux points d'échec possibles** : le helper `_remap_path` est appliqué aux trois nouveaux champs et leur ajoute les mêmes comportements que pour les autres chemins : `resolve()` peut lever une `OSError` sur un chemin pathologique, et une valeur truthy non chaîne (par exemple un entier édité à la main) lève `TypeError`. Ces erreurs surviennent pendant la préparation du payload, **avant toute mutation**, mais `rename_project()` n'attrape que `WorkspaceRenamePermissionError` et `WorkspaceManagerError`. Aucun durcissement dans M166 : l'existence de risques analogues ailleurs ne les rend pas inexistants.
- **Garde multi-Character inchangée** : `is_training_active()` ne parcourt que le Character principal ; piste distincte, non promue en défaut atteignable par l'UI.
- **Liens et jonctions** : un chemin qui traverse un lien résolu hors de la racine est traité comme externe, comme les champs existants ; non sondé spécifiquement.
- **Hors périmètre, non traités** : caption perdue sur `WORKSPACE_RENAMED` ; noms non protégés sur Training, LoRA et Prompts ; brouillon de métadonnées LoRA perdu après un échec de renommage ; readiness ComfyUI sans signal terminal sur une racine JSON non objet (comportement du worker démontré, verrouillage complet du lifecycle non reproduit au niveau intégration) ; frontières filesystem (`exists()` hors frontière d'erreur, `_expose()`) ; BOM UTF-8 dans les sidecars ; incidents natifs M164, cause inconnue.
- Plateforme : seule la plateforme Windows native de cette session a été exercée.
