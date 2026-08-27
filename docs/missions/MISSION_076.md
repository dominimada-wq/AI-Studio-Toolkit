# Mission 076 — Rollback DatasetManager.remove_images() / LoRAManager.add_files() / remove_files() on Persistence Failure

> **MISSION ENTIÈREMENT CLOSE.** 30 tests ciblés nets nouveaux (10 Dataset, 20 LoRA), non-régression complète sur `test_dataset_roundtrip.py` (113/113) et `test_lora_roundtrip.py` (145/145), suite complète 1385/1385, smoke test Qt réel exécuté et **PASS** (24/24 assertions, 3 scénarios réels avec de vrais fichiers sur disque — voir section 9). Voir section 10 pour l'état de clôture Git et publication.

## 1. Contexte

L'audit post-Mission 075 a relu systématiquement tous les appels `_workspace_manager.save()` des 8 Managers pour confirmer que la liste de dettes connue restait exhaustive. Il ne restait que quatre sites non protégés : `DatasetManager.remove_images()`, `LoRAManager.add_files()`, `LoRAManager.remove_files()` (Candidat F) et `SettingsManager.update()` (Candidat I). Le Candidat F a été retenu en priorité : les trois méthodes sont réellement accessibles depuis l'UI (boutons jamais cachés, contrairement à `CharacterManager.delete()`) et présentent le même risque de mutation fantôme mémoire/disque déjà traité par les Missions 066/067/070/071/072/073/074/075 pour d'autres méthodes.

## 2. Objectif

Appliquer à `DatasetManager.remove_images()`, `LoRAManager.add_files()` et `LoRAManager.remove_files()` un rollback local Domain-only exact (même principe que Missions 067/070), sans introduire de mécanisme filesystem ni d'abstraction transactionnelle partagée.

## 3. Audit préalable — constats structurants

- **`DatasetManager.remove_images()`** : retire de `dataset.images` (liste propre à chaque Dataset, Mission 011) toute entrée dont le `file_path` résolu correspond à un des chemins fournis. Ne touche jamais le filesystem, `Workspace.images`, ni un autre Dataset. Comparaison par chemin résolu (comme `add_images()`) — un chemin absent est un no-op, `save()` n'est appelé que si `removed > 0`. Aucun événement dédié publié. `active_dataset_id` jamais lu ni écrit par cette méthode.
- **`LoRAManager.add_files()`** : ajoute à `lora.files` les chemins non déjà présents (dédoublonnage contre le contenu existant **avant** l'appel, jamais contre une copie physique — `LoRA.files` ne contient que des références externes, jamais copiées, seul `set_thumbnail()` écrit physiquement dans le dossier privé de la LoRA). Ordre d'arrivée préservé pour les nouvelles entrées. `save()` appelé uniquement si au moins un chemin a été réellement ajouté. Aucun événement dédié, aucun autre état touché.
- **`LoRAManager.remove_files()`** : symétrique — égalité de chaîne exacte (jamais de résolution de chemin, puisque rien n'est copié), retire toutes les entrées correspondantes. Mêmes garanties qu'`add_files()`.
- **Aucune des trois méthodes ne touche un fichier physique** — confirmé par lecture directe : ni `Path.unlink()`, ni `shutil`, ni `WorkspaceStorage.copy_into_workspace()`/`delete_folder()` dans aucun des trois corps de méthode. Le rollback reste donc strictement Domain-only, sans aucune opération filesystem à compenser.
- **Doublons** : la sémantique actuelle n'empêche pas qu'un `project.json` édité à la main contienne des doublons (même `file_path`/même chemin répété) — `remove_images()`/`remove_files()` retirent alors **toutes** les occurrences correspondantes en une seule fois ; le rollback doit les restaurer toutes, sans en perdre ni en dupliquer.

## 4. Stratégie retenue — snapshot par réassignation (convention Mission 067)

Plutôt qu'une reconstruction élément par élément après échec, chaque méthode capture l'ancien objet-liste (`original_images`/`original_files`) par simple référence, puis **réassigne** l'attribut à une nouvelle liste (`dataset.images = [...]`, `lora.files = original_files + new_paths`, jamais de mutation en place `[:]`/`.extend()`) — exactement la convention déjà établie par `DatasetManager.add_images()` (Mission 067). Comme l'ancienne liste n'est jamais mutée, la restaurer sur échec (`dataset.images = original_images`) est exacte par construction : même ordre, mêmes doublons éventuels, même identité d'objet — pas une reconstruction approximative.

Aucun autre état n'est capturé ni restauré : l'audit (section 3) confirme qu'aucune des trois méthodes ne touche `active_dataset_id`/`active_lora_id` ni ne publie d'événement.

## 5. Contrat transactionnel appliqué

Pour les trois méthodes, identique :
1. Gardes existantes inchangées (`active_dataset`/`active_lora is None` → `return 0`).
2. Capture de l'ancienne liste par référence, calcul de la nouvelle liste, réassignation de l'attribut.
3. Si le nombre d'éléments réellement affectés est non nul : `try: self._workspace_manager.save() except WorkspaceManagerError: <attribut> = <ancienne liste>; raise`.
4. Sur succès : comportement inchangé (valeur de retour identique à avant Mission 076).

## 6. Primitives ajoutées

Aucune. Changement strictement local aux trois méthodes existantes — pas de nouvelle primitive `WorkspaceStorage`, pas de nouvel événement, pas de nouveau type de retour (contrairement à Mission 075 : ces trois méthodes n'ont aucune étape physique best-effort à signaler séparément).

## 7. Contrat Presentation

Les trois call sites réels interceptent désormais `WorkspaceManagerError` :
- `DatasetsPage.remove_selected_images_from_dataset()` : `QMessageBox.critical()`, puis `update_datasets()` explicite (aucun rafraîchissement automatique possible : `WORKSPACE_SAVED` n'est publié que sur un `save()` réussi).
- `LoRAPage.import_files()` : `QMessageBox.critical()` puis `return` avant les messages de succès existants (jamais un faux "import terminé"), et `update_loras()` explicite.
- `LoRAPage.remove_selected_files()` : `QMessageBox.critical()` puis `update_loras()` explicite.

Audit du refresh : aucune des trois listes (`images_list`/`files_list`) n'est mutée de façon spéculative par la Page avant l'appel au Manager — contrairement à `rename_dataset()`/`save_metadata()` où un widget de saisie affiche déjà la nouvelle valeur avant persistence. Le state affiché reste donc déjà cohérent avec le Domain restauré même sans resynchronisation ; l'appel explicite à `update_datasets()`/`update_loras()` est néanmoins ajouté systématiquement, par symétrie avec le contrat déjà établi (Missions 070/073/074/075) et pour rester robuste à toute évolution future de ces Pages, plutôt que de supposer qu'aucun résidu visuel ne peut jamais apparaître.

## 8. Hors périmètre (confirmé)

`SettingsManager.update()` ; `CharacterManager.delete()` (UI cachée) ; gestion/cleanup général de `.trash/` ; segfault Qt/PySide6 ; refonte du stockage ; future bibliothèque LoRA centralisée. Aucun fichier physique n'est jamais supprimé par ces méthodes, avant comme après cette mission.

## 9. Tests automatisés et smoke test Qt réel

**Niveau Manager** (`DatasetManagerRemoveImagesRollbackTest`, 7 tests ; `LoRAManagerAddFilesRollbackTest`, 7 tests ; `LoRAManagerRemoveFilesRollbackTest`, 7 tests) : succès normal inchangé ; échec `save()` restaurant la liste exacte avec plusieurs éléments retirés/ajoutés en une seule opération ; `project.json` inchangé après échec ; aucun événement `WORKSPACE_SAVED` publié sur échec ; une autre entité sans rapport non affectée (`assertIs`/comparaison directe) ; préservation de doublons préexistants (entrée manuellement dupliquée, simulant un `project.json` édité à la main) ; pour `add_files()`, un échec ne retire que ce que la tentative venait d'ajouter ; retry réel après rollback, y compris vérification du contenu exact persisté sur disque.

**Niveau Presentation** (`DatasetsPageRemoveImagesPersistenceFailureTest`, 3 tests ; `LoRAPageFilesPersistenceFailureTest`, 6 tests) : erreur affichée ; aucune mutation réelle sur échec ; `project.json` inchangé ; retry réel effectif depuis la Page, avec vérification du contenu final sur disque.

**Non-régression** : `test_dataset_roundtrip.py` (113/113 = 103 précédents + 10 nets nouveaux), `test_lora_roundtrip.py` (145/145 = 125 précédents + 20 nets nouveaux).

**Suite complète** : **1385/1385** (1355 précédents + 30 nets nouveaux), une exécution complète `unittest discover`, 131.3s, aucun crash.

**Smoke test Qt réel** — exécuté par Claude, `DatasetsPage`/`LoRAPage`/`DatasetManager`/`LoRAManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, sélection réelle dans les widgets (`setSelected(True)`), fichiers réels écrits/lus à chaque étape :
1. Dataset — `remove_selected_images_from_dataset()` : 2 images réelles importées, sélection réelle d'une image, échec de persistence injecté, rollback vérifié (Domain **et** `images_list` resynchronisée, `project.json` byte-identique), retry réel effectif.
2. LoRA — `import_files()` : référence existante réelle, tentative d'ajout avec échec de persistence, rollback vérifié (Domain **et** `files_list`, `project.json` inchangé), retry réel effectif.
3. LoRA — `remove_selected_files()` : sélection réelle, échec de persistence injecté, rollback vérifié (ordre exact restauré), retry réel effectif.
4. Vérification finale : les fichiers physiques réels (`photo1.png`/`photo2.png`) ne sont jamais touchés par aucune de ces opérations.

**24/24 assertions PASS.**

## Vérifications finales — réellement exécutées

- **Tests ciblés** : **30/30 nets nouveaux PASS**.
- **Non-régression complète** : `test_dataset_roundtrip.py` **113/113**, `test_lora_roundtrip.py` **145/145**.
- **Suite complète** : **1385/1385**, 131.3s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.
- **`git diff --check`** : propre (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 4 fichiers de production (`src/managers/dataset_manager.py`, `src/managers/lora_manager.py`, `src/ui/pages/datasets_page.py`, `src/ui/pages/lora_page.py`) + 2 fichiers de tests (`tests/integration/test_dataset_roundtrip.py`, `tests/integration/test_lora_roundtrip.py`) + ce document de mission.

## État d'avancement

- Audit préalable : **terminé, périmètre confirmé, aucune opération filesystem trouvée dans les trois méthodes**.
- Implémentation : **réalisée, conforme au contrat validé (snapshot par réassignation, convention Mission 067)**.
- Tests automatisés : **exécutés, verts — 30/30 ciblés nets nouveaux, non-régression complète des 2 fichiers de tests concernés**.
- Suite complète : **1385/1385, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (4 fichiers de code + 2 fichiers de tests + 1 document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 3 scénarios réels avec de vrais fichiers sur disque, 24/24 assertions** (section 9).
- Clôture Git (commit/tag/Release) : **terminée (section 10)**.

## 10. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `a0207d6` (`feat: rollback DatasetManager.remove_images() and LoRAManager.add_files()/remove_files() on persistence failure`), 7 fichiers modifiés (`src/managers/dataset_manager.py`, `src/managers/lora_manager.py`, `src/ui/pages/datasets_page.py`, `src/ui/pages/lora_page.py`, `tests/integration/test_dataset_roundtrip.py`, `tests/integration/test_lora_roundtrip.py`, `docs/missions/MISSION_076.md`), 750 insertions(+), 15 suppressions(-). Poussé (`d0a06c0..a0207d6`), divergence `0 0` vérifiée avant et après le push.
- **Tag annoté** : `v0.2-mission076` (message "Mission 076 - Rollback DatasetManager.remove_images() / LoRAManager.add_files() / remove_files() on Persistence Failure"), créé sur et poussé pour `a0207d6c951160836cdc3ea43495c13e7c87969c`. Vérifié via `git ls-remote --tags` — objet tag `963f831906011e23497244b715273d487e1919ca`, peelé sur `a0207d6c951160836cdc3ea43495c13e7c87969c`.
- **GitHub Release** : "v0.2-mission076 — Rollback DatasetManager.remove_images() / LoRAManager.add_files() / remove_files() on Persistence Failure" publiée manuellement par l'architecte.
- **État Git final vérifié post-régularisation** : working tree propre, `HEAD == origin/main == a0207d6c951160836cdc3ea43495c13e7c87969c` (avant le commit de régularisation documentaire qui suit), divergence `0 0`, tag intact et non déplacé.
