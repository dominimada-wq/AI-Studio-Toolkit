# Mission 055 — Handle Settings Persistence Failures Gracefully

> **STATUT : IMPLÉMENTATION TERMINÉE, EN ATTENTE DE COMMIT.** Contrat validé par l'architecte, implémentation réalisée conformément au contrat, 5/5 tests ciblés nets nouveaux (`SettingsPageSaveErrorTest`), 950/950 tests automatisés verts, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS (échec réel du système de fichiers pour Application Settings, patch contrôlé pour Workspace Settings — la piste réelle envisagée pour ce second cas s'étant avérée peu fiable sous Windows, conformément à l'instruction explicite de l'architecte).
> Aucun commit, tag ou Release n'existe encore pour cette mission — conformément au principe de non-auto-référence, ce document ne contient aucune valeur Git réelle avant la clôture effective.

## 1. Contexte

Un audit factuel du dépôt post-Mission 054 (grep systématique de TODO/FIXME, code mort, champs Domain non consommés, asymétries de CRUD Manager, contrôles UI désactivés, exceptions définies mais jamais interceptées) a été mené pour déterminer le prochain incrément pertinent, sans présupposer aucun des besoins déjà documentés et explicitement écartés de la sélection automatique (primitive Inference multi-références, Dataset de références → Inference, multi-engine, `comfyui_path`, refonte Settings, i18n, Prompt Library/RAG, portabilité des chemins, publication sociale).

Cet audit a révélé une exception définie et effectivement levée, mais **jamais interceptée nulle part dans le code** : `ApplicationSettingsStorageError` (`src/infrastructure/storage/application_settings_storage.py:11`, levée ligne 82 si l'écriture du fichier `application_settings.json` échoue). Un commentaire explicite dans `ApplicationSettingsManager.update()` (`src/managers/application_settings_manager.py:91-94`) documente le choix — correct au niveau Manager — de laisser cette exception se propager sans la capturer : *« Storage.save() may raise ApplicationSettingsStorageError — left to propagate uncaught. »* Mais rien, au niveau UI, ne l'intercepte : `SettingsPage.save_application_settings()` (`src/ui/pages/settings_page.py:155-166`) appelle `application_settings_manager.update(...)` sans aucun `try/except`.

En creusant plus loin, le même défaut existe pour la sauvegarde des **Workspace Settings** (`theme`/`language`) : `SettingsPage.save_settings()` (`src/ui/pages/settings_page.py:148-153`) appelle `self.settings_manager.update(...)`, qui délègue à `WorkspaceManager.save()` — une méthode qui lève déjà `WorkspaceManagerError` en cas d'échec de `WorkspaceStorage.save()` (`src/managers/workspace_manager.py:164-177`, confirmé par lecture directe). Or `WorkspaceManagerError` est **déjà** un type intercepté et traité par un message utilisateur français à quatre endroits distincts dans `main_window.py` (`new_project()`, `open_project()`, `save_project()`, `rename_project()` — chacun via `except WorkspaceManagerError as exc: QMessageBox.critical(self, "Erreur", str(exc))`). `SettingsPage.save_settings()` est donc le seul chemin de sauvegarde du Workspace qui n'applique pas cette convention déjà établie et validée quatre fois ailleurs dans la base.

Les deux boutons « Enregistrer » de `SettingsPage` sont réellement atteignables depuis l'UI (non désactivés en permanence — `save_button`/`application_save_button` sont conditionnés à l'état `opened`/toujours actif, confirmé par lecture directe), donc ce n'est pas du code mort : un échec d'écriture réel (permissions, disque plein, chemin `%LOCALAPPDATA%` indisponible) provoquerait aujourd'hui une exception non gérée remontant jusqu'à la boucle Qt, au lieu du message français gracieux déjà offert pour toute autre opération de sauvegarde de l'application.

## 2. Mini-audit réalisé

**`ApplicationSettingsStorage.save()`** (`src/infrastructure/storage/application_settings_storage.py:53-84`) : écriture atomique (`tempfile.mkstemp()` + `os.replace()`), lève `ApplicationSettingsStorageError` sur tout `OSError` durant l'écriture — mécanisme inchangé, robuste, seul le traitement de l'exception fait défaut en amont.

**`ApplicationSettingsManager.update()`** (`src/managers/application_settings_manager.py:38-101`) : appelle `ApplicationSettingsStorage.save()` ligne 95 sans `try/except`, comportement déjà volontaire et documenté (commentaire lignes 91-94) — **aucun changement Manager nécessaire**, seule la couche UI doit réagir.

**`WorkspaceManager.save()`** (`src/managers/workspace_manager.py:164-177`) : capture déjà `WorkspaceStorageError` et relève `WorkspaceManagerError(str(exc))` — mécanisme et contrat inchangés, déjà utilisés ailleurs.

**`SettingsManager.update()`** (`src/managers/settings_manager.py:28-57`) : délègue simplement à `self._workspace_manager.save()` ligne 55, sans capture — **aucun changement Manager nécessaire**, `WorkspaceManagerError` doit simplement remonter jusqu'à l'UI, comme pour toute autre opération de sauvegarde du Workspace.

**`SettingsPage`** (`src/ui/pages/settings_page.py`) : `QMessageBox` **n'est pas importé** dans ce fichier (confirmé par grep, aucune occurrence) — à ajouter. `save_settings()` (148-153) et `save_application_settings()` (155-166) n'ont aujourd'hui aucun `try/except`. Aucun label de statut dédié aux deux boutons « Enregistrer » (le seul label existant, `checkpoint_discovery_status_label`, est réservé à la découverte de checkpoints — Mission 025 — pas à la sauvegarde).

**Convention déjà établie à réutiliser telle quelle** : `main_window.py:402-403,420-421,440-441,481-482` — `except WorkspaceManagerError as exc: QMessageBox.critical(self, "Erreur", str(exc)); return`. Cette convention est reprise à l'identique pour les deux méthodes de `SettingsPage` — aucune nouvelle convention UI inventée, aucun nouveau texte de message à décider (le message est directement `str(exc)`, déjà porté par l'exception elle-même dans les deux cas).

**Persistance simulée dans les tests** : le dépôt utilise déjà `patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full"))` (`tests/integration/test_workspace_roundtrip.py:467,506,590`) — mécanisme directement transposable à `patch.object(ApplicationSettingsStorage, "save", side_effect=ApplicationSettingsStorageError("disk full"))` pour simuler un échec réel sans toucher au disque.

**Aucune décision produit ou architecturale substantielle ne reste ouverte** : le type d'exception à capturer dans chaque méthode est déterminé sans ambiguïté par ce que chaque Manager lève réellement (vérifié par lecture directe, pas supposé), et le mécanisme de restitution à l'utilisateur (`QMessageBox.critical`, message = `str(exc)`) est un remploi exact d'une convention déjà validée quatre fois dans `main_window.py` — aucune nouvelle convention à trancher.

## 3. Objectif

Étendre aux deux méthodes de sauvegarde de `SettingsPage` (`save_settings()` pour les Workspace Settings, `save_application_settings()` pour les Application Settings) la même convention de gestion d'erreur déjà utilisée quatre fois dans `main_window.py` pour toute autre opération de sauvegarde — un échec d'écriture réel affiche désormais un message français explicite (`QMessageBox.critical`) au lieu de laisser une exception non interceptée remonter jusqu'à la boucle Qt.

## 4. Contrat fonctionnel — réellement implémenté

- `SettingsPage.save_settings()` : le corps de la méthode est entouré d'un `try/except WorkspaceManagerError as exc: QMessageBox.critical(self, "Erreur", str(exc)); return`. Comportement de succès strictement inchangé (aucun test existant ne doit changer d'assertion).
- `SettingsPage.save_application_settings()` : même mécanisme, `except ApplicationSettingsStorageError as exc: QMessageBox.critical(self, "Erreur", str(exc)); return`.
- Nouveaux imports dans `settings_page.py` : `QMessageBox` (`PySide6.QtWidgets`), `WorkspaceManagerError` (`src.managers.workspace_manager`), `ApplicationSettingsStorageError` (`src.infrastructure.storage.application_settings_storage`).
- Aucun changement Domain, aucun changement Manager, aucun changement EventBus, aucun nouveau texte de message inventé (`str(exc)` reprend le message déjà porté par l'exception, comme dans `main_window.py`).

## 5. Périmètre — réellement modifié

Production (1) :
- `src/ui/pages/settings_page.py` (3 nouveaux imports — `QMessageBox`, `WorkspaceManagerError`, `ApplicationSettingsStorageError` — + `try/except` dans `save_settings()`/`save_application_settings()`)

Tests (1, aucun nouveau fichier) :
- `tests/integration/test_settings_page.py` (nouvelle classe `SettingsPageSaveErrorTest`, 5 tests — échec simulé de `WorkspaceManager.save()`/`ApplicationSettingsStorage.save()` pour les deux méthodes)

## 6. Hors périmètre

- Toute modification de `WorkspaceManager`/`SettingsManager`/`ApplicationSettingsManager`/`ApplicationSettingsStorage`/`WorkspaceStorage` — le comportement de propagation Manager reste strictement inchangé, déjà correct.
- Tout mécanisme de nouvelle tentative (retry) après échec.
- Toute autre Page ou tout autre bouton — périmètre strictement limité aux deux méthodes `save_settings()`/`save_application_settings()` de `SettingsPage`.
- Toute reformulation des messages d'erreur au-delà de la réutilisation directe de `str(exc)` — aucun nouveau texte français à rédiger.
- Le champ `ollama_path`/`comfyui_path` non consommé (besoin distinct, documenté séparément, non concerné par cette mission).
- La refonte Settings, l'application réelle de `theme`/`language` à l'UI (besoin distinct déjà documenté et explicitement hors périmètre).

## 7. Stratégie de tests — réellement mise en œuvre

`SettingsPageSaveErrorTest` (nouvelle classe, `test_settings_page.py`, 5 tests) :
- `test_application_settings_save_failure_shows_error_and_does_not_raise` : `patch.object(ApplicationSettingsStorage, "save", side_effect=ApplicationSettingsStorageError("disk full"))` + appel réel de `page.save_application_settings()` → aucune exception ne remonte, `QMessageBox.critical(page, "Erreur", "disk full")` invoqué (mock).
- `test_application_settings_save_failure_leaves_settings_unchanged` : `ApplicationSettings` en mémoire inchangés après l'échec (`ApplicationSettingsManager.update()` ne réassigne `self._settings` qu'après un `save()` réussi).
- `test_application_settings_page_reusable_for_real_save_after_failure` : après l'échec simulé, un vrai `save_application_settings()` (patch retiré) persiste réellement — preuve de réutilisabilité.
- `test_workspace_settings_save_failure_shows_error_and_does_not_raise` : même schéma avec `patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full"))` + `page.save_settings()`.
- `test_workspace_settings_page_reusable_for_real_save_after_failure` : `theme_edit`/`save_button` confirmés toujours activés après l'échec, puis un vrai `save_settings()` persiste réellement.

Non-régression du chemin de succès : `test_settings_page.py` (33/33), `test_settings_roundtrip.py`/`test_application_settings_roundtrip.py`/`test_main_window_comfyui_settings.py`/`test_main_window_ollama_settings.py` (29/29) tous verts sans modification d'assertion. **950/950 tests automatisés verts** au total (945 précédents + 5 nets nouveaux).

## 8. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels), script exclusivement dans le scratchpad de session, confirmé absent du dépôt (`git status --porcelain --ignored`).

**Application Settings — échec réel du système de fichiers, aucun mock sur le chemin d'échec** : `storage_directory` pointé vers un dossier réel et inscriptible dont le nom de fichier cible (`application_settings.json`) est occupé par un vrai sous-dossier — `os.replace(tmp_path, file)` lève alors une vraie `OSError` (remplacement d'un fichier par un dossier refusé sous Windows), capturée par le `except OSError` déjà existant de `ApplicationSettingsStorage.save()` et enveloppée en une vraie `ApplicationSettingsStorageError`. Clic réel sur « Enregistrer » → `QMessageBox.critical(page, "Erreur", ...)` confirmé invoqué (seule `QMessageBox` elle-même est mockée, pour rester non interactif — jamais le chemin d'échec), aucun crash, champ `comfyui_path_edit` conserve la valeur saisie, boutons/champs toujours activés. Cause réelle supprimée → nouveau clic réel sur « Enregistrer » → sauvegarde réelle confirmée sur disque.

**Workspace Settings — patch contrôlé, comme demandé** : rendre un dossier Workspace réellement inaccessible en écriture s'étant avéré peu fiable de façon déterministe sous Windows dans cet environnement, la défaillance est provoquée par `patch.object(WorkspaceStorage, "save", side_effect=WorkspaceStorageError("disk full"))` — chaque autre couche reste réelle (`WorkspaceManager`/`SettingsManager`/`SettingsPage` réels, clic réel sur « Enregistrer »). `QMessageBox.critical(page2, "Erreur", "disk full")` confirmé invoqué, aucun crash, `theme_edit`/`save_button` toujours activés. Patch retiré → nouveau clic réel → sauvegarde réelle confirmée (`settings_manager.settings.theme == "light"`).

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 9. Risques / non-régressions

- **Risque de capture trop large** : écarté — chaque `except` cible précisément le type d'exception réellement levé par le Manager concerné (`WorkspaceManagerError`/`ApplicationSettingsStorageError`), jamais un `except Exception` générique — vérifié par lecture du code final.
- **Risque de masquer une régression silencieuse** : écarté — le chemin de succès (aucune exception) confirmé identique au code précédent par la suite de tests existante, inchangée et toujours verte.
- **Risque de sur-portée** : écarté — `git diff --stat` limité à `src/ui/pages/settings_page.py` (production) et `tests/integration/test_settings_page.py` (tests), aucun Manager/Storage modifié.

## 10. Pourquoi maintenant

Ce candidat était le seul identifié par l'audit ne comportant aucune décision produit ou architecturale substantielle restant ouverte : le type d'exception à intercepter dans chaque cas était déterminé par lecture directe du code (pas supposé), et le mécanisme de restitution utilisateur est un remploi exact d'une convention déjà validée quatre fois ailleurs dans la base — aucune nouvelle convention inventée ni arbitrée. Il corrige un défaut réel et vérifié (deux chemins de sauvegarde réellement atteignables depuis l'UI, sans aucune gestion d'erreur, contrairement à toute autre opération de sauvegarde de l'application), pour un risque et une taille minimaux.

## État d'avancement

- Audit du dépôt (candidats Mission 055) : **réalisé**.
- Mini-audit ciblé du candidat recommandé : **réalisé**.
- Spécification : **validée par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 5/5 ciblés (`SettingsPageSaveErrorTest`), 950/950 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git (commit/tag/Release) : **non encore effectuée** — en attente d'autorisation explicite de commit.
