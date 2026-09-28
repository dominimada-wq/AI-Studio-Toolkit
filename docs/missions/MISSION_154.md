# Mission 154 — Resync Application Settings UI After Storage Failure

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** `SettingsPage.save_application_settings()` (`src/ui/pages/settings_page.py`) resynchronisait déjà ses 16 champs sur l'état réel du Manager après les trois exceptions `LoRALibraryPathLockedError`/`LoRAExposureRootLockedError`/`LoRAExposureRootInspectionError` (Missions 087/149/152), mais pas après `ApplicationSettingsStorageError` — un échec disque transitoire (disque plein, dossier `%LOCALAPPDATA%` inaccessible) laissait les champs afficher indéfiniment la saisie rejetée et jamais persistée, sans aucun indicateur permettant de la distinguer d'une valeur réellement enregistrée. Un audit/conception ciblé READ-ONLY préalable, validé par l'architecte, a confirmé que ce comportement est un oubli d'audit et non une conservation intentionnelle du brouillon (aucun test/doc/historique de mission ne l'établit comme tel) et que le contrat déjà appliqué au précédent le plus proche (`save_settings()`, même fichier, même classe, Mission 077, même nature d'erreur disque) est un resync inconditionnel. Corrigé en ajoutant le même appel `self.update_application_settings()` à la quatrième branche — aucune nouvelle abstraction, aucun changement du Manager, aucun mécanisme de dirty-state introduit.

## 1. Origine du bug

`ApplicationSettingsManager.update()` (`src/managers/application_settings_manager.py:259-267`) construit un `candidate` puis appelle `ApplicationSettingsStorage.save()` **avant** toute réaffectation de `self._settings` — un échec laisse donc le Manager strictement inchangé (déjà vrai depuis l'introduction de cette méthode, comportement volontaire et documenté en ligne). `SettingsPage.save_application_settings()` (`src/ui/pages/settings_page.py:680-717`), introduite par Mission 055, capturait déjà `ApplicationSettingsStorageError` pour éviter toute exception non gérée, mais son bloc `except` se limitait à `QMessageBox.critical(...); return` — repris tel quel de la convention générique de `main_window.py` (New/Open/Rename/Save Project), qui ne comporte aucun champ persistant à resynchroniser puisqu'il s'agit de dialogues ponctuels, pas d'un formulaire toujours visible. La question du resync des champs n'a donc jamais été tranchée par Mission 055 elle-même — elle n'existait pas encore à cette date.

## 2. Divergence UI ↔ Manager

Après l'exception : `application_settings_manager.settings` contient la valeur réellement persistée (inchangée), tandis que les widgets affichent la saisie de l'utilisateur, rejetée et jamais écrite sur disque. Rien dans l'UI ne signale cette divergence — un second regard sur la page ne permet pas de savoir si ce qui est affiché a été sauvegardé ou non.

## 3. Atomicité de `ApplicationSettingsManager.update()` — correcte, non modifiée

Confirmé par lecture directe (voir §1) : le pattern « candidate construit et validé avant tout `save()`, `self._settings` réaffecté seulement après succès » est déjà correct et suffisant. Cette mission ne touche à aucune ligne de `application_settings_manager.py`.

## 4. Absence de fondement historique pour un contrat de conservation du brouillon

L'audit/conception préalable a vérifié :
- Le seul test existant relatif à la réutilisabilité de la page après cet échec (`test_application_settings_page_reusable_for_real_save_after_failure`) **retape** une nouvelle valeur avant de relancer Save — il ne prouve à aucun moment qu'un second clic sans retaper persisterait la saisie rejetée conservée à l'écran. Aucune preuve que la préservation du champ soit un comportement voulu.
- Aucun dirty-state n'existe pour la section Application Settings (le seul `_dirty` du fichier couvre exclusivement la section Workspace `theme`/`language`, Mission 078) — une conservation délibérée du brouillon resterait de toute façon invisible/ambiguë pour l'utilisateur sans un tel indicateur, qui n'a jamais été construit ici.
- Les trois exceptions sœurs (Missions 087/149/152) rejettent déjà atomiquement les 16 champs du même clic en cas d'échec — le coût de retype du Contrat A est donc déjà pleinement accepté aujourd'hui pour 3 des 4 causes d'échec possibles de ce même bouton Save.

## 5. Précédent Mission 077 pertinent

`SettingsManager.update()` (Workspace `theme`/`language`) lève `WorkspaceManagerError` sur un échec de `WorkspaceManager.save()` — un échec disque transitoire de même nature que `ApplicationSettingsStorageError`, pas un refus métier. Mission 077 a doté `SettingsPage.save_settings()` (méthode sœur immédiate, même fichier, même classe) d'un resync inconditionnel via `_load_settings_fields()`, avec ce commentaire explicite conservé dans le code : « the just-rejected input must always be replaced by the restored Domain value here... exactly like Missions 073/074's own failure contract ». C'est le précédent le plus directement comparable de tout le dépôt pour cette question précise — plus proche que les trois exceptions sœurs elles-mêmes, dont la sémantique (refus métier actif) diffère de celle d'un simple échec d'écriture.

## 6. Contrat retenu — Contrat A (rollback visuel)

`ApplicationSettingsStorageError` → le Manager reste sur les valeurs réellement persistées (déjà garanti, §3) → l'UI est immédiatement resynchronisée sur ces valeurs, exactement comme les trois branches sœurs et comme `save_settings()` pour son échec de nature équivalente.

## 7. Correction appliquée

Dans `src/ui/pages/settings_page.py`, `save_application_settings()` :

```python
except ApplicationSettingsStorageError as exc:
    QMessageBox.critical(self, "Erreur", str(exc))
    self.update_application_settings()
    return
```

Un seul appel ajouté, réutilisant `update_application_settings()` — le même mécanisme canonique déjà utilisé par la branche sœur juste au-dessus, confirmé toujours correct par relecture directe avant modification (reconstruit les 16 champs depuis `application_settings_manager.settings`, sans distinction par champ). Les trois autres branches `except` ne sont pas modifiées — déjà correctes.

## 8. Tests ajoutés

**+1 test net**, ajouté à `SettingsPageSaveErrorTest` (`tests/integration/test_settings_page.py`), entre `test_application_settings_save_failure_leaves_settings_unchanged` (qui ne vérifie que le Manager) et `test_application_settings_page_reusable_for_real_save_after_failure` :

- `test_application_settings_widgets_resync_to_manager_after_storage_failure` : (1) une vraie valeur (`"C:/RealComfyUI"`) est d'abord réellement persistée par un save réussi — reverting vers `""` serait indiscernable d'un widget jamais touché ; (2) une valeur différente (`"C:/Rejected"`) est saisie ; (3) `ApplicationSettingsStorageError` est provoquée sur le save suivant ; (4) le dialogue `QMessageBox.critical` est vérifié appelé une fois avec le message exact ; (5) le Manager reste sur la valeur réellement persistée ; (6) le widget est désormais resynchronisé sur cette même valeur, jamais sur la saisie rejetée.

Aucun test existant modifié — `test_application_settings_save_failure_shows_error_and_does_not_raise`, `test_application_settings_save_failure_leaves_settings_unchanged` et `test_application_settings_page_reusable_for_real_save_after_failure` continuent de vérifier chacun leur propre invariant, inchangé.

## 9. Résultats réels

- `SettingsPageSaveErrorTest` : **10/10 passés** (9 préexistants + 1 nouveau, 1.501s).
- `tests/integration/test_settings_page.py` complet : **95/95 passés** (94 préexistants + 1 nouveau, 2.105s).
- Non-régression ciblée : `test_application_settings_roundtrip.py` + `test_lora_library_roundtrip.py` : **148/148 passés** (3.308s).
- **Suite complète : 2895 collectés/2895 passés, 0 échoué** (329.667s). Équation : 2894 (clôture Mission 153) + 1 net ajouté par Mission 154 = **2895**, cohérent.
- `git diff --check` : clean (avertissements `LF will be replaced by CRLF` uniquement, non bloquants).

## 10. Hors périmètre (non-goals confirmés)

- Aucun dirty-state ajouté à la section Application Settings.
- Aucun mécanisme de conservation/retry du brouillon.
- Aucune modification de `ApplicationSettingsManager`.
- Aucun refactor de `save_application_settings()` au-delà de la ligne ajoutée.
- Aucune modification des trois autres branches `except`, déjà correctes.
- Aucun des autres constats de l'audit global post-Mission 153 (D2 Training `unknown`, D3 race Forge `_stop_unconfirmed`, D4 `_find_existing_alias()` OSError, D5 `_same_volume()`, D6 path-traversal IDs, D7 suppression LoRA pendant génération active) n'est traité par cette mission.
- Aucun nettoyage documentaire sans rapport avec ce bug précis.

## 11. Clôture Git

Commit fonctionnel : `4f5aa1807f0a01958ce57c44c636355ae67d1e2c` (« Resync application settings after save failure », 3 fichiers : `src/ui/pages/settings_page.py`, `tests/integration/test_settings_page.py`, `docs/missions/MISSION_154.md`). Poussé sur `origin/main` sans commit étranger intercalé, `HEAD == origin/main`, divergence `0 0`. Tag annoté `v0.2-mission154` (objet `a9dfb5afe0c73cc86c3142660e98de41a658ceef`, cible `4f5aa1807f0a01958ce57c44c636355ae67d1e2c`), poussé et confirmé identique local/distant. GitHub Release `v0.2-mission154 — Resync Application Settings UI After Storage Failure` **publiée manuellement** par l'architecte. Suite complète au moment de la clôture : **2895/2895, 0 échoué** (329.667s). Le tag `v0.2-mission153` (`8913f15214d06f51962dde664d9d4c43fd3b2cc0` → objet `b5a4600c33965f7da2c9f44804ef74d6204292d6`) reste inchangé.
