# Mission 067 — Rollback Additive Filesystem Mutations on Persistence Failure

> **STATUT : MISSION ENTIÈREMENT CLOSE.** 20 tests ciblés nets nouveaux, suite complète 1121/1121, smoke test Qt réel exécuté et **PASS** (29/29 assertions, 4 scénarios réels dont Inference Accept/Reject). Commit fonctionnel `9105c9214de478b30368c0d4bdcff167f6690432`, tag annoté `v0.2-mission067`, GitHub Release publiée. Voir section 12 pour l'état de clôture Git final.

## 1. Contexte

Le mini-audit transactionnel mené avant Mission 066 avait identifié un second défaut, structurellement distinct de celui résolu par cette mission : les mutations **additives** (`WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`) copiaient physiquement un fichier puis mutaient le Domain **avant** `save()`, sans aucun rollback en cas d'échec de persistence. Conséquences démontrées : copie physique orpheline, mutation Domain silencieusement persistable par un `save()` ultérieur sans rapport, et pour `InferencePage._on_accept_clicked()` (dont l'image pending est déjà interne au Workspace, sous `outputs/`) un cas aggravé — un second clic sur « Accepter » après un échec obtenait silencieusement `added=0` sans jamais retenter la persistence, et un « Rejeter » après un « Accepter » échoué pouvait supprimer physiquement le fichier pending tout en laissant une référence Domain fantôme, persistable plus tard sans le moindre avertissement.

## 2. Objectif

Compléter le contrat transactionnel introduit par Mission 066 pour le cas structurellement différent des mutations additives : `filesystem → Domain → persistence`. En cas d'échec de persistence, les éléments ajoutés pendant l'appel doivent être rollbackés et les copies physiques créées par cet appel compensées autant que possible — sans jamais toucher un fichier préexistant ou un passthrough déjà interne au Workspace.

## 3. Contrat implémenté

**Principe commun aux trois Managers**, appliqué localement sans abstraction partagée (mirroir du principe déjà établi par Mission 063 : adaptations locales indépendantes plutôt qu'un framework) :

1. Le fichier est copié si nécessaire (`WorkspaceStorage.copy_into_workspace()`, inchangé).
2. Pour chaque nouvelle entrée, une comparaison entre `effective_path` (résolu) et la source (résolue) détermine si une vraie copie a été créée ou si c'est un passthrough (source déjà interne au Workspace, retournée telle quelle, sans I/O) — c'est cette même comparaison qui protège toujours la compensation de ne jamais supprimer un fichier préexistant.
3. Le Domain est muté (liste d'origine capturée avant mutation).
4. `save()` est tenté.
5. **Succès** : comportement normal existant, inchangé.
6. **Échec** : le Domain est restauré à sa liste d'origine exacte (mêmes objets, même ordre) ; chaque copie réellement créée par cet appel (jamais un passthrough) est supprimée en best-effort ; l'exception de persistence d'origine est relevée — enrichie d'une information sur un éventuel fichier orphelin non nettoyé si la compensation elle-même échoue, sans jamais masquer la cause première (mirroir exact du précédent déjà établi par `WorkspaceManager.rename()`, Mission 027).

**`WorkspaceManager.add_images()`** et **`DatasetManager.add_images()`** (`src/managers/workspace_manager.py`, `src/managers/dataset_manager.py`) : rollback de `Workspace.images`/`dataset.images` à leur état antérieur exact ; compensation des copies réellement créées (`created_copies`, liste locale construite pendant la boucle) ; le comportement de succès partiel des copies (`failed`/`skipped`) reste strictement inchangé.

**`LoRAManager.set_thumbnail()`** (`src/managers/lora_manager.py`) : `old_thumbnail` capturé avant mutation, restauré en cas d'échec ; la nouvelle copie n'est supprimée que si elle diffère réellement de la source (jamais un passthrough). La politique de conservation de l'ancienne miniature physique lors d'un remplacement **réussi** reste explicitement inchangée — dette distincte, non traitée ici.

**Presentation** (`ImagesPage.import_images()`, `DatasetsPage.import_images()`/`add_images_from_gallery()`, `LoRAPage.choose_thumbnail()`) : chaque handler intercepte désormais `WorkspaceManagerError` et affiche `QMessageBox.critical()` — l'action n'est jamais présentée comme réussie, l'état Domain est déjà cohérent grâce au rollback Manager, un nouvel essai est une tentative réellement neuve.

**`InferencePage._on_accept_clicked()`** — cas prioritaire : intercepte `WorkspaceManagerError`, affiche un message, et **ne nettoie pas** l'état pending (`_clear_pending()` non appelé, `generate_button`/contrôles de référence non réactivés) — la page reste exactement dans l'état pré-Accept (image toujours visible, Accepter/Rejeter/Régénérer toujours disponibles). Grâce au rollback du Manager, un second « Accepter » retente réellement la persistence (l'entrée n'existe plus en mémoire), et un « Rejeter » après un « Accepter » échoué ne laisse plus aucune référence fantôme.

## 4. Hors périmètre (explicitement confirmé, non traité)

- Les ~30 handlers Type 1 sans opération filesystem — reportés.
- `WorkspaceManager.remove_images()` — déjà traité par Mission 066.
- A-4 (libellés de liste obsolètes après renommage) — candidat de repli inchangé.
- Suppression/nettoyage de l'ancienne miniature LoRA après un remplacement **réussi** — dette distincte, non modifiée.
- Toute infrastructure transactionnelle générale ou modification de `WorkspaceStorage` non indispensable au contrat.

## 5. Risques

- **Risque de régression fonctionnelle** : faible — la logique de copie/déduplication existante (`existing`, `failed`, `skipped`) reste strictement inchangée ; seul l'ordre des opérations et la gestion d'erreur ont changé.
- **Risque de suppression d'un fichier préexistant lors de la compensation** : écarté par construction — la comparaison `effective_path` résolu vs source résolue garantit qu'un passthrough n'est jamais supprimé, vérifiée par des tests dédiés sur les trois Managers.

## 6. Pourquoi maintenant

Défaut transactionnel démontré empiriquement lors du mini-audit pré-Mission 066, avec un cas aggravé concret sur `InferencePage.accept()` (perte silencieuse d'une image acceptée, référence fantôme possible) — retenu comme candidat A prioritaire à l'issue de l'audit post-Mission 066, comparé explicitement à A-4 et écarté de ce dernier en raison d'un impact utilisateur plus sérieux.

## 7. Tests automatisés ajoutés

**20 tests nets nouveaux** :

- `tests/integration/test_workspace_roundtrip.py`, `WorkspaceManagerAddImagesCopyTest` (5) : échec `save()` + vraie copie (rollback + copie supprimée) ; échec `save()` + passthrough (jamais supprimé, reproduisant le cas `InferencePage`) ; retry après échec (tentative réellement neuve, aucun suffixe parasite) ; échec de compensation (erreur d'origine préservée, information orpheline jointe) ; lot multi-fichiers (préexistants jamais touchés, identité d'objet préservée).
- `tests/integration/test_dataset_roundtrip.py`, `DatasetManagerAddImagesCopyTest` (4) : rollback complet + nettoyage après plusieurs copies ; mélange copie réussie/échouée ; passthrough (image déjà dans la galerie Workspace) ; échec de compensation. `DatasetsPageImportPersistenceFailureTest` (2, nouvelle classe) : `import_images()` et `add_images_from_gallery()` affichent l'erreur et ne réintroduisent jamais l'image.
- `tests/integration/test_lora_roundtrip.py`, `LoRAManagerMetadataTest` (3) : restauration de `old_thumbnail` + nettoyage de la nouvelle copie ; passthrough jamais supprimé ; échec de compensation. Plus 1 test Presentation (`choose_thumbnail()` affiche l'erreur, ancienne miniature conservée).
- `tests/integration/test_images_page.py`, `ImagesPageImportPersistenceFailureTest` (2, nouvelle classe) : erreur affichée sans rien importer ; retry réellement fonctionnel.
- `tests/integration/test_inference_page.py`, `InferencePageTest` (3) : Accept échoué conserve l'état pending exact (contrôles cohérents, image toujours présente, aucune entrée Domain) ; retry Accept persiste réellement ; Rejeter après Accept échoué ne laisse aucune référence fantôme, vérifié y compris après un `save()` ultérieur sans rapport.

Comportement observable testé (fichiers réels sur disque, `project.json` réellement relu, widgets Qt réels, boutons réellement cliqués), jamais l'existence interne d'un mécanisme.

## 8. Vérifications finales — réellement exécutées

**Tests ciblés** — **20/20 nets nouveaux PASS**. Non-régression complète des fichiers touchés — **294/294 PASS** (`test_workspace_roundtrip.py` + `test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_images_page.py`), **81/81 PASS** (`test_inference_page.py`).

`git diff --check` : propre, aucun avertissement de contenu.

**Périmètre du diff** : exactement 12 fichiers — `src/managers/{workspace_manager,dataset_manager,lora_manager}.py`, `src/ui/pages/{images_page,datasets_page,lora_page,inference_page}.py` (production), et leurs 5 fichiers de tests correspondants. Aucun fichier Domain/EventBus/`WorkspaceManager.remove_images()`/A-4/autre Manager touché.

## 9. Suite complète

**1121/1121 tests verts** (1101 précédents + 20 nets nouveaux), une exécution complète `unittest discover`, aucun crash, aucun échec. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet apportée.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

Widgets réels (`ImagesPage`, `DatasetsPage`, `LoRAPage`, `InferencePage`), Managers réels, fichiers réels sur disque, `project.json` réellement relu à chaque étape, boutons réellement cliqués. `QMessageBox` mocké uniquement pour éviter un modal bloquant, `GenerationManager` mocké pour `InferencePage` (convention déjà établie).

1. **Import Images** : échec de persistence injecté → erreur affichée, Domain rollbacké, aucune copie orpheline, source intacte ; retry réel réussi, galerie mise à jour.
2. **Import Dataset** : même principe, Dataset réel — mêmes garanties.
3. **Miniature LoRA** : état initial connu → échec injecté → erreur affichée, ancienne miniature restaurée et toujours présente sur disque, nouvelle copie compensée (supprimée) ; retry réel réussi.
4. **Inference Accept** — scénario a : génération réelle → Accept avec `save()` en échec → message affiché, image toujours pending, absente de `workspace.images`, fichier toujours présent, Accepter/Rejeter toujours utilisables, `Generate` toujours désactivé → second Accept (persistence fonctionnelle) → succès réel, pending nettoyé normalement. Scénario b : Accept échoué → Rejeter → fichier supprimé, aucune entrée Domain, et **aucune référence fantôme dans `project.json` après un `save()` ultérieur sans rapport** — le critère essentiel de cette mission.

**Verdict : PASS**, 29/29 assertions vérifiées (`m067_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## 11. État d'avancement

- Décision de périmètre (rollback local par Manager, sans framework transactionnel) : **validée par l'architecte** à l'issue du mini-audit transactionnel.
- Implémentation : **réalisée, conforme au contrat** — rollback Domain + compensation filesystem local sur les trois Managers, traitement Presentation dédié pour les 4 handlers + le cas prioritaire `InferencePage`.
- Tests automatisés : **exécutés, verts — 20/20 ciblés nets nouveaux, 294/294 + 81/81 non-régression complète**.
- Suite complète : **1121/1121, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (12 fichiers exactement, aucun fichier hors périmètre touché)**.
- Smoke test Qt réel : **réalisé, PASS, 4 scénarios réels couverts** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (voir section 12).

## 12. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `9105c9214de478b30368c0d4bdcff167f6690432` (`feat: rollback additive filesystem mutations on persistence failure`), 13 fichiers modifiés/créés (7 fichiers de production, 5 fichiers de tests, `docs/missions/MISSION_067.md`), 718 insertions(+), 12 suppressions(-).
- **Push** : `0cb58fc..9105c92 main -> main`. Vérifié après coup : `HEAD == origin/main == 9105c9214de478b30368c0d4bdcff167f6690432`, divergence `0 0`.
- **Tag annoté** : `v0.2-mission067`, message « Mission 067 - Rollback Additive Filesystem Mutations on Persistence Failure », objet `de0bcf92f7d307d58b7145aed87576a1af9ec439`, peeled sur `9105c9214de478b30368c0d4bdcff167f6690432` — vérifié identique en local et à distance (`git ls-remote --tags`).
- **GitHub Release `v0.2-mission067`** : publiée manuellement par l'architecte.
- **Régularisation documentaire post-Release** (ce commit) : mise à jour du bandeau de statut de ce document, de `docs/PROJECT_CONTEXT.md` et de `CHANGELOG.md` (nouvelle section `## v0.2-mission067`) pour refléter l'état Git/Release réel désormais clos. Le tag `v0.2-mission067` reste sur le commit fonctionnel `9105c92` — non déplacé par ce commit de régularisation, purement documentaire.
- **Segfault Qt/PySide6** : ne s'est pas manifesté pendant la validation de cette mission (1121/1121 propre) — observation de stabilité, non une preuve de correction. Cause racine toujours non isolée ; l'hypothèse simple de cleanup `QThread` reste expérimentalement réfutée (audit post-Mission 064). Aucune modification visant ce sujet n'a été apportée dans Mission 067.
