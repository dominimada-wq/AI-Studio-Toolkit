# Mission 078 — Dirty-State Protection for CharactersPage / LoRAPage / SettingsPage

> **MISSION ENTIÈREMENT CLOSE.** 42 tests ciblés nets nouveaux, non-régression complète sur `test_character_roundtrip.py` (75/75), `test_lora_roundtrip.py` (160/160), `test_settings_roundtrip.py` (42/42), `test_settings_page.py` (48/48), `test_application_settings_roundtrip.py` (16/16), suite complète 1446/1446, smoke test Qt réel exécuté et **PASS** (20/20 assertions, 7 scénarios réels — voir section 8). Commit fonctionnel `0c7c30ec9698d6b876db57b0cd7a18e9b1b7a30a`, tag annoté `v0.2-mission078`, GitHub Release publiée. Voir section 10 pour l'état de clôture Git final.

## 1. Contexte

L'audit frais réalisé après la clôture de Mission 077 a confirmé que la série de sécurisation transactionnelle Domain → persistence (Missions 066–077) était close pour tous les chemins réellement accessibles depuis l'UI. En cherchant un bug réel et démontrable plutôt qu'un besoin produit futur, l'audit a découvert que `CharactersPage.update_characters()`, `LoRAPage.update_loras()` et `SettingsPage.update_settings()` réécrivaient **inconditionnellement** leurs champs texte à chaque événement `WORKSPACE_CREATED/OPENED/SAVED/CLOSED/RENAMED` (et `CHARACTER_*`/`LORA_*` selon la Page) — sans aucune garde de dirty-state. C'est exactement le bug déjà corrigé pour `PromptsPage` par la Mission 038, jamais généralisé à ces trois autres Pages, qui partagent le même patron (bouton « Enregistrer » explicite, pas de sauvegarde sur perte de focus comme `rename_dataset()`/`rename_lora()`/`rename_model()`/`rename_workflow()`/`rename_training()`).

Une reproduction empirique réelle (script scratchpad, 3 scénarios) a confirmé le bug avant toute implémentation :

```
Before unrelated save, bio_edit = 'DRAFT BIO NOT SAVED YET'
After unrelated LoRA creation, bio_edit = ''
Before unrelated save, engine_edit = 'DRAFT ENGINE NOT SAVED YET'
After unrelated character creation, engine_edit = ''
Before unrelated save, theme_edit = 'draft-theme-not-saved'
After unrelated LoRA creation, theme_edit = ''
ALL THREE SCENARIOS CONFIRMED: unsaved drafts are silently wiped by unrelated WORKSPACE_SAVED events.
```

## 2. Objectif

Généraliser à `CharactersPage`, `LoRAPage` et `SettingsPage` la protection dirty-state déjà établie et validée pour `PromptsPage` (Mission 038) : une sauvegarde ou mutation indépendante ailleurs dans l'application ne doit jamais effacer silencieusement une saisie locale non sauvegardée, sans jamais casser les contrats de resynchronisation après échec déjà établis par les Missions 073 (LoRA metadata), 074 (Character identity) et 077 (Settings).

## 3. Audit préalable — différences de cycle de vie entre les trois Pages

L'analogie avec `PromptsPage` a été vérifiée page par page, pas recopiée mécaniquement :

- **`CharactersPage`** : 7 champs (`name`/`bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token`), un seul « brouillon » possible à la fois — `principal_character_id` reste stable dans l'usage normal (« 1 Workspace = 1 personnage principal »). Aucune sélection réelle accessible depuis l'UI (liste cachée, Mission 026) : le seul « vrai changement de contexte » possible est un Workspace créé/ouvert/fermé. `CHARACTER_SELECTED`/`CHARACTER_DELETED` restent des événements internes/tests, jamais atteints par un vrai clic utilisateur, mais couverts pour la compatibilité historique.
- **`LoRAPage`** : 4 champs de métadonnées (`engine`/`architecture`/`trigger_word`/`version`) — `name_edit`/`files_list`/`thumbnail` n'ont aucun brouillon (renommage sur perte de focus, affichages en lecture seule) et continuent de se resynchroniser sans condition, exactement comme avant cette mission. Contrairement à `CharactersPage`, un vrai changement de sélection LoRA est directement accessible depuis l'UI (liste visible) : un brouillon de métadonnées peut donc légitimement appartenir à une LoRA qui n'est plus celle affichée après un clic sur une autre entrée de la liste.
- **`SettingsPage`** : 2 champs (`theme`/`language`), aucune dimension de sélection (un seul objet `Settings` par Workspace ouvert) — la distinction pertinente est uniquement « même Workspace ouvert, sauvegarde indépendante » vs. « Workspace différent/fermé ».

## 4. Contrat dirty-state retenu

**Principe commun, décliné par Page — pas un framework transversal.** Chaque Page reçoit un flag `_dirty`/`_metadata_dirty` local, mis à `True` uniquement par un signal `textChanged` connecté aux champs concernés (jamais déclenché par une écriture programmatique, protégée par `blockSignals()` dans toute méthode de rechargement).

**Deux méthodes de refresh par Page, jamais une seule (mirroir exact de `PromptsPage`/Mission 038) :**

- `update_*()` — abonnée uniquement à `WORKSPACE_SAVED`/`WORKSPACE_RENAMED` (et aux événements propres à l'entité qui ne changent jamais l'identité affichée — `CHARACTER_CREATED` pour Characters/LoRA, `LORA_CREATED`/`LORA_SELECTED`/`LORA_DELETED` pour LoRA). Ne discute jamais qu'un simple retard.
- `reset_for_context_change()` — abonnée à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` (et `CHARACTER_SELECTED`/`CHARACTER_DELETED` pour Characters/LoRA). Toujours inconditionnelle : un changement réel de contexte ne doit jamais dépendre d'une comparaison d'identifiant qui pourrait lire `None == None` comme « rien n'a changé » (le même piège documenté par Mission 038 pour `PromptsPage` — vérifié applicable ici aussi, notamment pour Characters/LoRA en cas de Workspace vide de Character/LoRA des deux côtés du switch).

**Condition de préservation du brouillon, affinée par rapport à `PromptsPage` après une régression détectée en tests** : `update_*()` ne préserve les champs concernés que si **l'identité affichée est inchangée ET le champ est réellement dirty** — pas seulement « l'identité est inchangée » comme le fait `PromptsPage.update_prompts()`. Un premier passage utilisant uniquement la comparaison d'identifiant (sans le second facteur `_dirty`) a fait régresser 3 tests préexistants (`test_rename_preserves_files_metadata_and_thumbnail`, `test_selection_targets_correct_lora_and_preserves_files_metadata_thumbnail`, `test_remove_selected_files_leaves_metadata_and_thumbnail_intact`) qui appellent `LoRAManager.update()` directement (hors `save_metadata()`) et attendent que la fiche reflète ce changement externe. La garde `AND _dirty` corrige ce cas sans réintroduire le bug initial — un brouillon réellement en cours de saisie reste protégé, un rafraîchissement sans rien de non sauvegardé continue de refléter fidèlement le Domain.

**`LoRAPage` — changement réel de sélection.** `on_lora_selection_changed()` intercepte désormais un brouillon `_metadata_dirty` avant d'appeler `lora_manager.select()`, avec le même dialogue Enregistrer/Ignorer/Annuler que `PromptsPage.on_prompt_selection_changed()` (Mission 038) — Annuler restaure la sélection visuelle sans jamais appeler `select()`, Enregistrer tente `lora_manager.update()` sur la LoRA **précédente** avant de basculer. `delete_lora()` adapte le texte de son dialogue existant (jamais un second dialogue empilé) quand la LoRA supprimée porte un brouillon non enregistré.

**Changement réel de Workspace.** `confirm_context_change() -> bool` ajouté aux trois Pages, même rôle que `PromptsPage.confirm_context_change()` (Mission 069) : appelé par `MainWindow.new_project()`/`open_project()` avant que `reset_for_context_change()` ne discute silencieusement un brouillon lors du remplacement de `current_workspace`.

## 5. Interaction avec les Missions 073/074/077 — jamais cassée

Les trois Pages disposent chacune d'un helper de rechargement **inconditionnel**, distinct de la voie automatique protégée par le dirty-state, réutilisé par tout site d'échec déjà établi :

- `CharactersPage._load_identity_fields()` — utilisé par `save_identity()` (Mission 074) et par `confirm_context_change()` sur échec.
- `LoRAPage._load_metadata_fields()`/`_force_refresh_lora()` — utilisé par `save_metadata()` (Mission 073), `rename_lora()`/`import_files()`/`remove_selected_files()` (Missions 070/076, pour leurs propres besoins de resynchronisation `name_edit`/`files_list`, non liés au dirty-state metadata) et `confirm_context_change()` sur échec.
- `SettingsPage._load_settings_fields()` — utilisé par `save_settings()` (Mission 077) et `confirm_context_change()` sur échec.

Dans les trois cas, ce chemin **bypasse volontairement** la garde dirty-state : après un échec de persistence, la valeur rejetée ne doit jamais rester affichée, quel que soit l'état `_dirty` — exactement le contrat déjà validé par ces trois missions, désormais combiné avec la remise à `False` du nouveau flag (l'affichage restauré n'est plus considéré comme un brouillon).

## 6. Primitives ajoutées

Aucune nouvelle abstraction transversale de dirty-state. Changement strictement local à chaque Page : un flag booléen, un « identifiant chargé » (`_loaded_character_id`/`_loaded_lora_id`), les helpers de rechargement déjà décrits, et `confirm_context_change()`. `main_window.py` scinde les abonnements EventBus déjà existants entre les deux méthodes par Page et ajoute les trois appels `confirm_context_change()` dans `new_project()`/`open_project()`, au même endroit que celui déjà existant pour `PromptsPage`.

## 7. Bug corrigé en cours d'implémentation

Une première version de `CharactersPage.save_identity()`'s échec appelait `self._load_identity_fields(principal_id)` en passant l'**identifiant** au lieu du dictionnaire attendu — aurait levé une `TypeError` (« string indices must be integers ») à chaque échec réel de sauvegarde d'identité. Détecté et corrigé avant toute exécution de test, via un script de reproduction empirique dédié exerçant explicitement les 3 chemins d'échec (`save_identity()`/`save_metadata()`/`save_settings()`) avec un vrai `WorkspaceStorage.save()` patché.

## 8. Tests automatisés et smoke test Qt réel

**42 tests nets nouveaux** répartis en 3 classes (`CharactersPageDirtyStateTest` 13, `LoRAPageDirtyStateTest` 15, `SettingsPageDirtyStateTest` 14), couvrant pour chaque Page : brouillon préservé à travers un `WORKSPACE_SAVED` indépendant (reproduction permanente des 3 scénarios empiriques de l'audit — `bio_edit`/`engine_edit`/`theme_edit`) ; plusieurs champs dirty simultanément ; save réussi (dirty effacé, persistance réelle) ; save échoué (contrat Missions 073/074/077 préservé, dirty effacé par le resync forcé) ; absence de faux dirty lors d'un rafraîchissement programmatique ; un rafraîchissement non-dirty reflète correctement une mutation externe directe du Manager ; changement réel de contexte (fermeture Workspace) efface le brouillon ; `confirm_context_change()` (Enregistrer/Ignorer/Annuler/échec, avec retry réel) ; pour LoRA spécifiquement, changement réel de sélection (Enregistrer/Ignorer/Annuler avec restauration de sélection) et suppression d'une LoRA avec brouillon (dialogue adapté).

**Non-régression complète** des 5 fichiers de tests touchés/liés : `test_character_roundtrip.py` (75/75 = 62 précédents + 13 nets nouveaux), `test_lora_roundtrip.py` (160/160 = 145 + 15), `test_settings_roundtrip.py` (42/42 = 28 + 14), `test_settings_page.py` (48/48, wiring corrigé sans nouveau test), `test_application_settings_roundtrip.py` (16/16, wiring corrigé sans nouveau test). Trois fichiers cablant `CharactersPage`/`LoRAPage`/`SettingsPage` avec l'ancien schéma d'abonnement à tous les événements Workspace ont dû être corrigés pour refléter la scission `update_*()`/`reset_for_context_change()` (`test_settings_roundtrip.py`, `test_settings_page.py`, `test_application_settings_roundtrip.py`) — une régression réelle détectée par exécution (`SettingsPage.theme_edit.isEnabled()` restait `False` après ouverture de Workspace) et corrigée avant tout commit.

**Suite complète : 1446/1446** (1404 précédents + 42 nets nouveaux), une exécution complète `unittest discover`, 133.9s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.

**Smoke test Qt réel** — exécuté par Claude, `CharactersPage`/`LoRAPage`/`SettingsPage`/`CharacterManager`/`LoRAManager`/`SettingsManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, **PASS, 20/20 assertions**, 7 scénarios réels :
1. Saisie réelle dans les 3 widgets, puis mutation réelle indépendante (création d'un Character) — les 3 brouillons survivent.
2. Clic réel sur les 3 boutons Enregistrer — persistance réelle confirmée, dirty effacé.
3. Échec de persistence réel injecté sur les 3 Pages — resynchronisation aux valeurs restaurées, dirty effacé.
4. Sauvegarde ultérieure réelle indépendante — aucune valeur rejetée ne contamine `project.json`.
5. Changement réel de sélection LoRA avec brouillon, interception réelle du dialogue, choix Enregistrer — persistance sur l'ancienne LoRA confirmée, affichage correct de la nouvelle.
6. Fermeture réelle du Workspace — brouillons effacés, champs Settings désactivés.
7. Retry réel après échec — persistance de bout en bout confirmée sur un nouveau Workspace/LoRA.

## 9. Conclusion

Le bug de perte silencieuse de saisie non sauvegardée, démontré empiriquement sur les 3 Pages avant implémentation, est corrigé sans régression sur les contrats déjà établis par les Missions 038 (précédent direct), 069 (garde de changement de Workspace), 070/073/074/076/077 (contrats de resynchronisation après échec). Aucune nouvelle fonctionnalité métier, aucune abstraction transversale de dirty-state, `CharacterManager.delete()` non touché, périmètre strictement limité aux 3 Pages validées.

## État d'avancement

- Audit préalable : **terminé, cycles de vie des 3 Pages comparés individuellement, différences documentées**.
- Implémentation : **réalisée, un bug d'argument découvert et corrigé avant tout test, une régression de conception (garde `AND dirty`) détectée par tests et corrigée**.
- Tests automatisés : **exécutés, verts — 42/42 ciblés nets nouveaux, non-régression complète des 5 fichiers de tests concernés**.
- Suite complète : **1446/1446, aucun crash**.
- `git diff --check` : **propre** (seuls des avertissements de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme (4 fichiers de code + 5 fichiers de tests + ce document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 20/20 assertions, 7 scénarios réels**.
- Clôture Git (commit/tag/Release) : **entièrement effectuée** — commit fonctionnel `0c7c30ec9698d6b876db57b0cd7a18e9b1b7a30a` (`feat: dirty-state protection for CharactersPage/LoRAPage/SettingsPage`), poussé sur `origin/main` (divergence `0 0` vérifiée avant et après push), tag annoté `v0.2-mission078` créé et poussé sur ce même commit (vérifié via `git ls-remote --tags`, peelé exactement sur `0c7c30e`), GitHub Release `v0.2-mission078` **publiée** par l'architecte du projet.

## 10. Clôture Git et publication

- **Commit fonctionnel** : `0c7c30ec9698d6b876db57b0cd7a18e9b1b7a30a` — `feat: dirty-state protection for CharactersPage/LoRAPage/SettingsPage` (4 fichiers de code + 5 fichiers de tests + ce document de mission, 1469 insertions/44 suppressions).
- **Tag** : `v0.2-mission078` (annoté, message « Mission 078 - Dirty-State Protection for CharactersPage/LoRAPage/SettingsPage »), créé et poussé sur `0c7c30e`, vérifié par `git ls-remote --tags origin v0.2-mission078 "v0.2-mission078^{}"` (peelé exactement sur `0c7c30e`).
- **GitHub Release** : `v0.2-mission078` publiée par l'architecte du projet (Release Notes rédigées en anglais par Claude, conformément à la convention permanente depuis Mission 024).
- **État Git final vérifié** : `HEAD == origin/main == 0c7c30e`, divergence `0 0`, working tree propre.
