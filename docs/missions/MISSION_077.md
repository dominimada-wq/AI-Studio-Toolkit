# Mission 077 — Rollback SettingsManager.update() on Persistence Failure

> **MISSION FONCTIONNELLEMENT VALIDÉE, IMPLÉMENTATION TERMINÉE.** 19 tests ciblés nets nouveaux, non-régression complète sur `test_settings_roundtrip.py` (28/28) et `test_settings_page.py` (48/48), suite complète 1404/1404, smoke test Qt réel exécuté et **PASS** (16/16 assertions — voir section 8). Voir section 9 pour l'état de clôture Git.

## 1. Contexte

L'audit exhaustif post-Mission 076 a relu systématiquement tous les appels `save()` des 8 Managers métier et confirmé qu'il ne restait que deux sites non protégés contre la mutation fantôme mémoire/disque sur échec de persistence : `CharacterManager.delete()` et `SettingsManager.update()`. Le premier a été reconfirmé réellement inaccessible depuis l'UI (`new_button`/`delete_button`/`list_widget` tous `setVisible(False)` de façon permanente dans `characters_page.py`, décision produit Mission 026 documentée : « 1 Workspace = 1 personnage principal »). Le second a été retenu comme périmètre de cette mission, avec une reproduction empirique confirmant le défaut avant tout code :

```
theme in memory immediately after failed save(): dark-rejected
theme on disk after failed save():               (inchangé, correct)
theme on disk after an UNRELATED successful save(): dark-rejected
CONFIRMED BUG: rejected theme value was silently persisted by an unrelated save().
```

## 2. Objectif

Appliquer à `SettingsManager.update()` un rollback local Domain-only exact, empêchant qu'une valeur `theme`/`language` rejetée par un échec de `save()` survive en mémoire jusqu'à être silencieusement persistée par une sauvegarde ultérieure totalement indépendante.

## 3. Audit préalable — constats structurants

- **Champs réellement mutés** : uniquement `settings.theme` et `settings.language` (dataclass `Settings`, 2 champs scalaires, aucune collection imbriquée).
- **Identité et propriété de `workspace.settings`** : `Workspace.settings` est un champ `Settings` unique (`field(default_factory=Settings)`), lu en direct par `SettingsManager.settings` (propriété, aucun cache) à chaque accès — aucune copie ni snapshot ailleurs.
- **Autres références vers cette même instance** : recherche exhaustive dans `src/` — seul `SettingsManager` lit `workspace.settings`, et seule `SettingsPage.update_settings()` lit `self.settings_manager.settings` (toujours en direct, jamais mise en cache entre deux appels). Aucun autre composant ne conserve de référence susceptible de devenir stale.
- **Événements publiés** : aucun. `SettingsManager` ne prend même pas d'`event_bus` en paramètre (conforme à CLAUDE.md : « Singleton Workspace-owned : pas d'event_bus »). `WORKSPACE_SAVED` reste l'unique canal de notification, publié par `WorkspaceManager.save()` lui-même, uniquement après un `WorkspaceStorage.save()` réussi — jamais atteint si celui-ci lève.
- **Autre état modifié** : aucun — pas d'`active_id`, pas de collection, pas de fichier physique.
- **Comportement de `WorkspaceManager.save()`** : lève `WorkspaceManagerError` sur `WorkspaceStorageError`, sans jamais publier `WORKSPACE_SAVED` dans ce cas — comportement déjà exhaustivement couvert par les tests existants de `WorkspaceManager`, non remis en cause ici.

## 4. Choix du contrat — rollback local, pas candidate-before-save

Deux stratégies étaient envisageables : candidate-before-save (comme `ApplicationSettingsManager.update()`) ou snapshot des anciennes valeurs + rollback sur la même instance. L'audit ci-dessus confirme que `workspace.settings` est l'objet Domain partagé et durable de la classe `Workspace` (mêmes conventions que `Character`/`Dataset`/`LoRA`/`Model`/`Workflow`/`Training`), et non un singleton privé au Manager comme `ApplicationSettings._settings`. Recopier mécaniquement le pattern candidate-before-save aurait exigé de réassigner `workspace.settings` à une nouvelle instance — une déviation par rapport à la convention dominante déjà établie pour toute mise à jour de champ scalaire sur une entité Domain partagée (`CharacterManager.update()`, `LoRAManager.update_name()`, `ModelManager.update_name()`/`update_file_path()`, `WorkflowManager.update_name()`/`update_file_path()`) — toutes utilisent un snapshot des anciennes valeurs et un rollback sur la même instance, jamais un remplacement d'objet.

**Stratégie retenue** : snapshot des anciennes valeurs de `theme`/`language`, application des nouvelles, tentative de `save()`, restauration exacte des deux anciennes valeurs sur la même instance `Settings` en cas d'échec, ré-élévation de l'exception.

## 5. Contrat transactionnel appliqué

1. Garde existante inchangée (`workspace is None` → `return False`), calcul `changed` inchangé.
2. Capture de `old_theme`/`old_language` par simple lecture des champs actuels.
3. Application des nouvelles valeurs sur `settings` (comportement inchangé).
4. `try: self._workspace_manager.save() except WorkspaceManagerError: settings.theme = old_theme; settings.language = old_language; raise`.
5. Sur succès : comportement inchangé (retourne `True`).

## 6. Primitives ajoutées

Aucune. Changement strictement local à `SettingsManager.update()` — pas de nouvel événement, pas de nouveau type de retour (`bool` conservé).

## 7. Contrat Presentation

`SettingsPage.save_settings()` possédait déjà, depuis Mission 055, l'interception de `WorkspaceManagerError` avec `QMessageBox.critical()` — conservée sans modification.

**Nécessité de resynchronisation démontrée** : `theme_edit`/`language_edit` sont des `QLineEdit` affichant en permanence ce que l'utilisateur a tapé — après un rollback, ils continuaient donc d'afficher la valeur rejetée (`"dark-rejected"`) alors que le Domain (et le disque) étaient revenus à l'ancienne valeur (`"dark"`) : une incohérence UX réelle, de la même nature exacte que celle déjà traitée pour `DatasetsPage.rename_dataset()` (Mission 070, même type de widget lié à un champ scalaire). Un appel explicite à `self.update_settings(payload=True)` a donc été ajouté dans le bloc `except`, avec un commentaire expliquant pourquoi un payload sentinelle suffit (`update_settings()` ne lit jamais le contenu du payload, seulement `payload is not None`, et un workspace est nécessairement encore ouvert à ce point puisque `update()` n'aurait pas pu muter/lever au-delà de sa propre garde `workspace is None`). Couvert par 2 tests dédiés (resync des champs, champs restés activables pour un retry réel).

## 8. Tests automatisés et smoke test Qt réel

**Niveau Manager** (`SettingsManagerUpdateRollbackTest`, 14 tests) : succès normal inchangé ; `theme` seul, `language` seul, et les deux simultanément sur succès ; échec `save()` levant `WorkspaceManagerError` ; restauration exacte des deux valeurs (cas combiné, puis chacun isolément) ; même instance `Settings` conservée (`assertIs`) ; `project.json` inchangé après échec ; aucun événement publié sur échec (spy sur `EventBus.publish`) ; aucun autre état Workspace modifié (personnages/images) ; retry réel après rollback avec vérification du contenu exact persisté sur disque ; **test de non-régression permanent reproduisant le scénario empirique de l'audit** (`test_unrelated_later_save_no_longer_persists_previously_rejected_values`) — une sauvegarde ultérieure totalement indépendante ne persiste plus la valeur rejetée.

**Niveau Presentation** (`SettingsPagePersistenceFailureTest`, 5 tests) : erreur critique affichée ; `theme_edit`/`language_edit` resynchronisés à l'état Domain restauré après échec ; champs et bouton restés activables ; `project.json` inchangé ; retry réel effectif depuis la Page.

**Non-régression** : `test_settings_roundtrip.py` (28/28 = 9 précédents + 19 nets nouveaux), `test_settings_page.py` (48/48, aucune régression sur la couverture Mission 055 existante).

**Suite complète** : **1404/1404** (1385 précédents + 19 nets nouveaux), une exécution complète `unittest discover`, 132.4s, aucun crash.

**Smoke test Qt réel** — exécuté par Claude, `SettingsPage`/`SettingsManager`/`CharacterManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque :
1. Mise à jour normale de `theme`/`language`, vérifiée en mémoire et sur disque.
2. Échec de persistence injecté : erreur critique affichée, `theme`/`language` restaurés en mémoire **et** dans `theme_edit`/`language_edit`, champs restés activables, `project.json` byte-identique à avant l'échec.
3. Sauvegarde ultérieure totalement indépendante (création d'un personnage) : les valeurs rejetées ne contaminent plus `project.json`.
4. Retry réel : la nouvelle valeur est effectivement persistée en mémoire et sur disque.

**16/16 assertions PASS.**

## Vérifications finales — réellement exécutées

- **Tests ciblés** : **19/19 nets nouveaux PASS**.
- **Non-régression complète** : `test_settings_roundtrip.py` **28/28**, `test_settings_page.py` **48/48**.
- **Suite complète** : **1404/1404**, 132.4s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.
- **`git diff --check`** : propre (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 2 fichiers de production (`src/managers/settings_manager.py`, `src/ui/pages/settings_page.py`) + 1 fichier de tests (`tests/integration/test_settings_roundtrip.py`) + ce document de mission.

## 9. Conclusion transactionnelle

**Question posée** : existe-t-il encore un chemin Domain → `WorkspaceManager.save()` réellement accessible depuis l'UI qui puisse laisser une mutation fantôme après un échec de persistence ?

**Réponse : non.** Le balayage exhaustif des 8 Managers métier (répété identiquement avant Mission 076 et avant Mission 077) ne laisse plus qu'un seul site technique non protégé, `CharacterManager.delete()` — et celui-ci reste, comme confirmé indépendamment à deux reprises consécutives, structurellement inaccessible depuis l'UI par une décision produit délibérée et documentée (Mission 026), pas un oubli. **Mission 077 clôt donc la série de sécurisation transactionnelle des chemins Domain → persistence réellement actifs depuis l'UI**, ouverte à la Mission 066. `CharacterManager.delete()` reste sciemment non corrigé dans cette mission, conformément au périmètre validé — une éventuelle mission future ne serait justifiée que par un changement de décision produit rendant ce chemin de nouveau accessible.

## État d'avancement

- Audit préalable : **terminé, périmètre confirmé, stratégie de rollback local justifiée par opposition à candidate-before-save**.
- Implémentation : **réalisée, conforme au contrat validé (snapshot + rollback sur la même instance)**.
- Tests automatisés : **exécutés, verts — 19/19 ciblés nets nouveaux, non-régression complète des 2 fichiers de tests concernés**.
- Suite complète : **1404/1404, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (2 fichiers de code + 1 fichier de tests + 1 document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 16/16 assertions**.
- Clôture Git (commit/tag/Release) : **en cours**.
