# Mission 167 — Preserve the Caption Draft Across a Workspace Rename

> **IMPLÉMENTATION VALIDÉE PAR REVUE ARCHITECTE — publication en attente.** Un renommage de Workspace remappe tous les chemins d'images internes ; `DatasetsPage.update_datasets()` capturait et restaurait la sélection de `images_list` par `file_path`, qui ne retrouvait donc plus rien après le renommage : la sélection (simple ou multiple) était perdue et, avec elle, le brouillon de caption attaché à l'image sélectionnée (éditeur vidé et désactivé, état dirty remis à `False`, sans aucune confirmation). Découvert par l'audit global post-Mission 166 (candidat B), conçu READ-ONLY avec une sonde dynamique, puis implémenté strictement dans le périmètre validé : la clé d'identité de la capture et de la restauration de la sélection, dans `DatasetsPage` uniquement. Mission non close : push, tag et Release restent à venir.

## 1. Défaut initial

`src/ui/pages/datasets_page.py::update_datasets()` capturait, avant la reconstruction de `images_list`, la sélection et l'élément courant par `file_path` (`Qt.UserRole`), puis les restaurait par la même clé (Mission 082). `WorkspaceManager.rename()` remappe tous les `file_path` internes et reconstruit le Workspace : après `WORKSPACE_RENAMED`, aucun élément ne correspondait plus aux anciens chemins. L'élément courant devenait `None`, et `_refresh_caption_panel_for_current_selection()` appelait `_load_caption_into_editor(None)`, qui vide et désactive l'éditeur et force `_caption_dirty = False`.

La logique de caption (identité `_caption_loaded_image_id`, gardes M098/M158/M159/M160) était correcte : la perte du brouillon n'était que la conséquence de la perte de sélection. Le défaut touchait donc aussi l'utilisateur **sans brouillon** (sélection perdue, caption affichée vidée).

## 2. Preuve empirique (sonde de conception)

Sonde exécutée hors dépôt (`MainWindow` réel sur un projet temporaire, 3 images, captions distinctes sur `b` et `c`) : sélection par vrais clics de souris, brouillon par vraies frappes, renommage par `rename_project()` avec seul le dialogue de saisie simulé, aucun rafraîchissement manuel. Deux phases : le code actuel, puis un prototype en mémoire (même fonction, clé remplacée par `image_id`), jamais écrit dans le dépôt. 21 scénarios (11 + 10), aucune exception, aucun dialogue réel.

| Scénario | Code antérieur | Restauration par `image_id` |
|---|---|---|
| brouillon sur `b`, renommage | sélection `[]`, courant `None`, dirty `False`, éditeur vide et désactivé | sélection `[b]`, courant `b`, dirty `True`, texte conservé |
| enregistrement ensuite | `save_caption()` retourne `True` sans rien enregistrer (identité chargée `None`) | `b` enregistrée sur le disque sous la nouvelle racine ; `c` inchangée |
| deux renommages successifs | brouillon perdu dès le premier | conservé après chacun ; enregistrement final correct |
| sans brouillon, `b` sélectionnée | sélection perdue, éditeur vidé | sélection et texte conservés |
| multi-sélection `{a,b,c}` + brouillon | sélection perdue | conservée ; seule l'image du brouillon est modifiée à l'enregistrement |
| tri par date | ordre conservé, sélection et brouillon perdus | tout conservé |
| image à chemin externe (état construit) | brouillon **conservé** (chemin non remappé) | identique |
| renommage annulé ou en échec | état antérieur conservé | identique |
| `close()` puis `open()` après renommage | aucun brouillon, aucune sélection | identique : aucun transfert |

Observations : (1) l'image à chemin externe garde son brouillon, ce qui isole le remappage de chemin comme déclencheur ; (2) l'ordre réel des abonnés de `WORKSPACE_RENAMED` est, pour `DatasetsPage.update_datasets`, le 6ᵉ sur 11 et correspond à la liste statique ; aucun Manager ne s'y abonne ; le Workspace est déjà reconstruit au moment du callback ; (3) les 120 tests ciblés existants (`test_datasets_page.py` en entier et deux classes de `test_dataset_roundtrip.py`) passent à l'identique avec et sans le prototype.

Limites de la sonde : plateforme Windows native, une exécution par scénario ; dialogue de saisie simulé ; échec de renommage simulé par une levée de `WorkspaceManager.rename` ; image externe construite (non atteignable par un import normal, qui copie toujours dans le projet) ; `close()`/`open()` directs qui contournent volontairement les gardes de `MainWindow` pour n'observer que le reset ; le prototype est un remplacement textuel de la fonction, pas le code final.

## 3. Chaîne causale

1. `rename()` remappe les `file_path` internes et reconstruit le Workspace (les `image_id` sérialisés sont conservés).
2. `update_datasets()` capture la sélection avec les anciens chemins : aucune correspondance après reconstruction.
3. L'élément courant devient `None` ; le panneau de caption est rechargé à vide ; le brouillon est détruit sans confirmation.

Avec une clé `image_id`, l'élément courant retrouvé a l'identité déjà chargée : `_refresh_caption_panel_for_current_selection()` retourne immédiatement sans toucher texte, dirty ni bouton ; l'enregistrement s'appuie sur `_caption_loaded_image_id` (jamais un chemin) et relit le Dataset actif dans le Workspace reconstruit.

Portée et stabilité de l'identité : `image_id` est un `uuid4` attribué par le Manager, sérialisé dans `images[].image_id` et dans les clés de `entries`, conservé par le remappage ; unique dans le pool d'`Image` d'un Dataset (deux Datasets partageant un fichier ont des `image_id` distincts, M011). Entre Workspaces, deux projets dupliqués peuvent partager des identifiants sérialisés, mais la garde `same_dataset` (inchangée) interdit toute restauration après un vrai changement de contexte : `DatasetManager` remet `active_dataset_id` à `None` sur `WORKSPACE_CREATED/OPENED/CLOSED` et `CHARACTER_SELECTED/DELETED`.

## 4. Correction

**Production (1 fichier)** : `src/ui/pages/datasets_page.py`, `update_datasets()` uniquement.
- la sélection et l'élément courant sont capturés puis restaurés par `image_id` (`Qt.UserRole + 1`), au lieu de `file_path` (`Qt.UserRole`) ;
- variables renommées (`previously_selected_image_ids`, `previously_current_image_id`, `image_id`) et commentaire de la Mission 167 ajouté à celui de la Mission 082 ;
- conservés sans modification : la garde `same_dataset`, le blocage des signaux, `QItemSelectionModel.NoUpdate`, la logique du panneau de caption, le dispositif de nom (M165) ;
- aucun repli par chemin, aucun nouvel attribut de dirty-state, aucun dialogue, aucune sauvegarde automatique ; aucun changement de `MainWindow`, de Manager ni de Domain.

Le commentaire de `MainWindow.rename_project()` (« un renommage ne détruit aucun brouillon », Mission 084) n'est volontairement **pas** modifié : cette affirmation générale ne peut pas être déclarée exacte à l'issue de cette mission, d'autres pistes (noms Training/LoRA/Prompts, métadonnées LoRA) restant ouvertes.

## 5. Fichiers modifiés

- `src/ui/pages/datasets_page.py` (production, 27 lignes touchées : 19 ajouts, 8 suppressions, commentaire compris) ;
- `tests/integration/test_datasets_page.py` — classe `DatasetsPageRenameCaptionDraftTest` (13 tests) ; test existant `test_unrelated_events_preserve_both_the_name_draft_and_the_caption_draft` complété (il excluait volontairement l'assertion de caption sur `WORKSPACE_RENAMED`) ; import `json` ajouté ;
- `tests/integration/test_main_window_rename_project.py` — classe `MainWindowRenameDatasetCaptionDraftTest` (4 tests) ; imports `json` et `QTest` ajoutés ;
- `docs/missions/MISSION_167.md` (ce document).

Aucun changement de `MainWindow`, de Manager, de Domain, de `CHANGELOG.md` ni de `PROJECT_CONTEXT.md`.

## 6. Tests ajoutés (17) et modifié (1)

**Niveau Page — `DatasetsPageRenameCaptionDraftTest` (13)** : vrai `WorkspaceManager.rename()` donc vrai `WORKSPACE_RENAMED` vers l'abonnement réel de la page (observé en place, restauré ensuite), aucun rafraîchissement manuel, objets relus depuis le Workspace reconstruit (`assertIsNot`).
- preuve principale : sélection, élément courant, identité chargée, texte, dirty et boutons conservés ; aucun `set_caption`, aucun `QMessageBox`, une seule sauvegarde (celle du renommage) ; Domain et `project.json` toujours sur les captions persistées ; puis enregistrement explicite : bonne image, autres captions inchangées, Domain courant et `project.json` sous la nouvelle racine ;
- sans brouillon : sélection et caption affichée conservées ; rien de sélectionné : reste vide ;
- deux renommages successifs puis enregistrement sous la dernière racine ;
- multi-sélection avec captions distinctes (brouillon sur l'image courante uniquement) ;
- tri par date (mtimes déterministes) ; image à chemin externe (état construit, signalé comme tel) avec sélection interne conservée ;
- image disparue après le renommage (appel direct au Manager, qui contourne le dialogue de la page) : éditeur réinitialisé, aucun brouillon résiduel ;
- échec de sauvegarde avec rollback : même Workspace, aucun événement, brouillon et sélection conservés, enregistrement toujours possible sous l'ancienne racine ;
- changement de Dataset par l'UI réelle (clic de souris, garde « Ignorer » répondue) après renommage : aucun transfert ; sélection directe par le Manager (chemin de reset, garde contournée) : aucun transfert, ni au retour ;
- ouverture d'un autre Workspace portant les mêmes identifiants sérialisés (copie octet pour octet), avec **et sans** renommage préalable : le reset empêche toute réutilisation du brouillon ; la même image sélectionnée charge sa propre caption persistée.

**Niveau intégration — `MainWindowRenameDatasetCaptionDraftTest` (4)** : `MainWindow()` réel, vrais clics de souris et vraies frappes, seul `RenameProjectDialog` simulé, abonnement réel observé en place.
- brouillon + `rename_project()` + enregistrement par le vrai bouton : nouvelle racine, bonne image, aucune sauvegarde automatique ;
- sans brouillon : multi-sélection (Ctrl+clic) et caption affichée conservées ;
- dialogue annulé puis renommage en échec : état antérieur conservé ;
- deux renommages successifs, enregistrement, `close()`/`open()` du projet renommé : caption persistée relue.

**Distinction reset direct / gardes UI.** Les tests qui appellent directement les Managers (`select`, `open`, `remove_images`) n'observent que le chemin de reset de la Présentation ; ils ne prouvent pas que les dialogues New/Open/Close fonctionnent. Cette couverture est conservée, inchangée, dans `DatasetsPageConfirmContextChangeTest`, `test_main_window_new_project.py` et `test_main_window_close_event.py`, et a été rejouée (section 7).

**Hygiène Qt.** Filet anti-dialogue armé avant la fenêtre et arrêté en dernier ; dossier temporaire enregistré avant la fenêtre (donc supprimé après sa fermeture) ; fermeture effective de la fenêtre ou de la page **vérifiée** avant la suppression du projet ; le brouillon n'est neutralisé que dans le nettoyage, après les assertions, jamais par un enregistrement exécuté en fin de chemin heureux.

## 7. Résultats (effectivement obtenus)

**Preuve avant/après** (seul le fichier de production remplacé par sa version `HEAD`, sans `git stash` : sauvegarde octet-exacte avec empreinte SHA-256, version `HEAD` convertie en CRLF, convention de ce fichier, puis restauration vérifiée par `cmp` et par empreinte, diff identique à celui revu, aucun stash, fins de ligne CRLF 986/986 conservées) :
- production antérieure : 23 tests exécutés dans les 3 classes ciblées, **14 échecs d'assertion de comportement, 0 erreur**, 9 réussites ;
- production corrigée : **23/23 OK**.

*Assertions de régression (échouent avant, réussissent après, 14)* : 10 tests de la classe Page (preuve principale, sans brouillon, successifs, multi-sélection, tri, externe/interne, image disparue, deux tests de changement de Dataset, ouverture d'un autre Workspace après renommage), le test existant complété, et 3 tests d'intégration (brouillon, sans brouillon, successifs).
*Invariants déjà vrais avant la correction (9)* : 5 tests existants de `DatasetsPageNameAndCaptionDraftTest` non modifiés ; rien de sélectionné ; échec de sauvegarde avec rollback ; renommage annulé/en échec (intégration) ; ouverture d'un autre Workspace aux mêmes identifiants **sans** renommage préalable. Dans les tests de reset combinés au renommage, la précondition « brouillon conservé après renommage » échoue avant la correction : leurs assertions de reset ne sont donc pas, seules, une preuve indépendante d'invariance — celle-ci est apportée par la variante sans renommage, par la couverture existante des gardes (M158) et par la sonde (scénarios `close`/`open`, identiques avant et avec prototype).

**Validation après correction** (premier plan, sortie non tamponnée, vrai code de sortie du processus) :
- `test_datasets_page.py` : 107/107 (94 avant la mission, +13), code 0 ;
- `test_main_window_rename_project.py` : 27/27 (23 avant, +4), code 0 — **rejoué après l'ajustement de revue** (section 8) : 27/27 par la commande habituelle (`python -m unittest tests.integration.test_main_window_rename_project`) **et** 27/27 par exécution directe du fichier, code 0 dans les deux cas ;
- couverture existante pertinente : `test_dataset_roundtrip.py` 167/167 (noms et gardes de nom), `test_main_window_new_project.py` 47/47 et `test_main_window_close_event.py` 47/47 (gardes de contexte), `test_workspace_roundtrip.py` 118/118, `test_images_page.py` 57/57, tous code 0 ;
- **suite complète** : **3031 tests, OK, code de sortie 0, 356,043 s** (11:11:48 → 11:17:50), aucun autre processus Python concurrent au lancement ; 3014 (référence M166) + 17 nets = 3031 ; aucune ligne `FAIL`/`ERROR` dans la sortie ; les 17 nouveaux tests y figurent. **Ce résultat date d'avant l'ajustement de revue de la section 8** (déplacement du bloc d'entrée de `test_main_window_rename_project.py`) : la suite complète n'a **pas** été relancée depuis ; seul le fichier concerné a été rejoué (27/27, ci-dessus). La production et le contenu des tests étant inchangés par cet ajustement, ce chiffre est reporté tel qu'obtenu, non présenté comme réexécuté ;
- `git diff --check` propre ; 3 fichiers de code modifiés plus ce document.

## 8. Incidents de validation (conservés pour traçabilité, aucun n'est un défaut produit)

- **Nettoyage de la sonde (corrigé, rejoué).** Dans la première exécution de la sonde, 4 scénarios s'achevant avec un brouillon encore actif ont fait demander la garde de fermeture réelle de `MainWindow` pendant le `window.close()` du nettoyage ; le filet anti-dialogue l'a annulée, la fenêtre est restée ouverte et le dossier temporaire a été supprimé fenêtre ouverte, contrairement à la consigne. Cause : dispositif de la sonde, pas le produit (la garde de fermeture fait exactement ce qu'elle doit). Corrigé en neutralisant le brouillon uniquement dans le nettoyage, en vérifiant la fermeture effective de la fenêtre avant la suppression, puis **toutes les sondes ont été rejouées** : 21 scénarios, aucune exception, aucun dialogue, fenêtre fermée à chaque fois. Les résultats retenus sont ceux de la seconde exécution.
- **Helper de sélection des tests (corrigé avant toute validation).** Le premier helper `_select` du niveau Page fixait l'élément courant en dernier avec `NoUpdate` : `itemSelectionChanged` n'étant plus émis après ce changement, `enlarge_button` restait désactivé dès l'état initial, avant tout renommage. Artefact du helper (5 échecs sur la production corrigée), pas de la production : l'ordre a été aligné sur un vrai clic (élément courant d'abord, autres éléments ajoutés ensuite), puis tout a été rejoué.
- **Écriture transitoire.** Une écriture de `test_datasets_page.py` a échoué une fois avec `OSError: [Errno 22]` avant toute troncature (fichier vérifié intact, 2221 lignes) ; elle a été réappliquée avec succès. Aucune incidence sur le contenu.
- **Bloc d'entrée du fichier de test (relevé en revue, corrigé).** Dans `test_main_window_rename_project.py`, la classe `MainWindowRenameDatasetCaptionDraftTest` avait été ajoutée **après** le bloc `if __name__ == "__main__": unittest.main()` situé en fin du fichier d'origine. La découverte unittest et la commande habituelle incluaient bien les nouveaux tests (la suite complète les avait exécutés), mais une exécution directe du fichier atteignait `unittest.main()` avant leur définition et les omettait. Ajustement : ce seul bloc a été déplacé à la toute fin du fichier, après toutes les classes ; fins de ligne CRLF préservées (1070/1070), production et contenu des tests inchangés (diff de production identique, empreinte SHA-256 inchangée). Vérifié : 27 méthodes de test dans le fichier, bloc d'entrée unique et postérieur à la dernière classe ; 27/27 par la commande habituelle et 27/27 par exécution directe. Cause : ordre d'insertion lors de l'ajout des tests, pas un défaut produit. La suite complète n'a pas été relancée après ce déplacement.
- Les incidents d'exécution natifs/blocage de la Mission 164 restent de cause inconnue ; aucune exécution de cette mission ne les a reproduits ni résolus.

## 9. Limites et hors périmètre

- **Identifiants invalides ou dupliqués** (un `project.json` édité à la main : `image_id` vide ou répété) : non gérés et aucune validation ajoutée. Un identifiant répété sélectionnerait plusieurs éléments à la restauration.
- La même clé `file_path` fait aussi perdre la sélection au renommage sur `ImagesPage` et `LoRAPage.files_list` (sans brouillon concerné, donc sans perte de données) : non traité.
- Le commentaire de `MainWindow.rename_project()` (M084) reste inchangé (voir section 4).
- Les pistes ouvertes restent ouvertes, sans classement : noms en commit-on-blur sur Training/LoRA/Prompts, brouillon de métadonnées LoRA après échec, frontières filesystem des imports et de l'exposition, readiness ComfyUI face à une racine JSON non objet, BOM des sidecars, dérive documentaire d'architecture, références LoRA lors de la suppression physique d'une image de galerie ; incidents natifs M164.
- Les gardes de dialogue New/Open/Close sont couvertes par les tests existants, non modifiés ; les nouveaux tests de reset appellent directement les Managers.
- Plateforme : seule la plateforme Windows native de cette session a été exercée ; une exécution par scénario.
