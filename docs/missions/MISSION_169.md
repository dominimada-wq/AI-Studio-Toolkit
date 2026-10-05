# Mission 169 — Protect Gallery Images Still Used as LoRA Thumbnails

> **MISSION 169 CLOSE — implémentation validée par revue architecte, commit fonctionnel et tag publiés, GitHub Release publiée manuellement (références en section 13).** `WorkspaceManager.remove_images()` supprimait physiquement un fichier de la galerie même lorsqu'une LoRA l'utilisait encore comme miniature : `LoRAManager.set_thumbnail()` réutilise tel quel un fichier déjà situé dans le Workspace (« passthrough »), et seule la garde Dataset existait. La miniature restait alors un chemin mort, persisté dans `project.json`, et l'import de la LoRA en bibliothèque centrale échouait tant qu'une autre miniature n'était pas choisie. Découvert par l'audit global post-Mission 168 (candidat G), confirmé par une sonde dynamique de conception, puis corrigé dans le Manager (option A retenue par l'architecte : seuls les fichiers que l'appel supprimerait physiquement sont protégés), avec un traitement défensif de la page. Mission close : push, tag et Release sont effectués ; le commit documentaire de régularisation n'est ni tagué ni référencé en dur.

## 1. Défaut confirmé

- `LoRAManager.set_thumbnail()` copie la source dans `models/loras/<lora_id>/` **sauf** si elle est déjà dans la racine du Workspace (`WorkspaceStorage.copy_into_workspace()` : « passthrough », aucune copie). Une image de `images/` ou de `outputs/` devient donc directement la miniature, sans dossier privé de LoRA.
- `WorkspaceManager.remove_images()` ne connaissait que les références Dataset (`images_referenced_by_datasets()`). Un fichier dans la racine et présent était supprimé physiquement après sauvegarde.
- Conséquences observées : miniature de la LoRA morte (aperçu « indisponible »), chemin mort conservé dans `project.json`, aucun avertissement avant la suppression (la confirmation annonce seulement une suppression définitive des fichiers).
- Import en bibliothèque centrale : `LoRAPage.add_to_central_library()` échoue entièrement tant que la miniature manque (contrat Mission 088, test existant `test_import_missing_thumbnail_file_fails_entire_import`). **Choisir une autre miniature débloque l'import** (prouvé par la sonde). Frictions restantes, hors périmètre : aucun moyen de vider une miniature, et le message d'erreur d'import cite un chemin sans désigner la miniature comme cause.

## 2. Preuve empirique (sonde de conception, hors dépôt)

Projets temporaires construits par les vrais Managers ; bibliothèque centrale entièrement isolée dans le dossier temporaire (`LoRALibraryManager(storage_directory=<tmp>)`, `library_root` temporaire) ; Python 3.11.9 du venv, Qt hors écran, aucun clic, aucun moteur ; aucun accès en écriture à la bibliothèque réelle ; aucun fichier du dépôt modifié, aucun bytecode écrit. Scripts et résultats dans le scratchpad de la session.

| Scénario | Mesure |
|---|---|
| Image de galerie → `set_thumbnail` → `remove_images` direct | Passthrough confirmé (chemin résolu identique, chaîne identique, aucun dossier privé créé). Fichier supprimé, `Workspace.images=[]`, miniature morte, `project.json` conserve le chemin. |
| Import en bibliothèque avec miniature morte | Échec (« Could not import LoRA files: Could not copy … »), 0 entrée, aucun dossier résiduel dans la racine isolée. |
| Récupération | `set_thumbnail` avec un autre fichier (copié dans le dossier de la LoRA), puis import réussi. |
| Image sous `outputs/` | Passthrough, fichier et miniature supprimés. |
| Miniature externe, absente, différente | Entrée externe de même chemin : retrait par référence, fichier conservé et miniature valide. Fichier absent : `reference_only`, rien de détruit. Fichier différent : aucune correspondance. |
| Renommage préalable du Workspace | Chemins de galerie et de miniature remappés à l'identique ; un chemin périmé ne correspond à rien. |
| Sélection mixte | Les deux fichiers supprimés (aucune garde LoRA) ; avec un Dataset : blocage global, rien supprimé. |
| Page (dialogues simulés) | Aucun avertissement, confirmation affichée, fichier supprimé. |

Limites de la sonde : lecture statique pour l'atteignabilité (navigation dans un `QFileDialog` vers le dossier du projet), fréquence d'usage non mesurée, plateforme Windows native seulement.

## 3. Chaîne causale

1. `set_thumbnail()` → `copy_into_workspace()` renvoie le fichier interne tel quel (`workspace_storage.py`, `is_inside` puis `return source.resolve()`).
2. La LoRA stocke ce chemin dans `thumbnail` (identique à une entrée de `Workspace.images`).
3. `ImagesPage.delete_selected_images()` ne contrôlait que les Datasets ; `remove_images()` ne contrôlait que les Datasets, alors que sa docstring le désigne comme seule autorité.
4. Après `save()`, `Path.unlink()` supprime le fichier : la miniature pointe vers un fichier absent.

## 4. Contrat de suppression (relu avant correction)

- Blocage **global** : une seule protection établie rend l'appel entier sans effet (ni `save`, ni `unlink`) ; aucune suppression partielle.
- Retrait de la galerie et suppression physique : `remove_images()` retire toujours les entrées correspondantes de `Workspace.images` ; le fichier n'est supprimé que s'il est dans la racine et présent ; sinon `reference_only` (externe ou absent), sans `unlink`.
- Chemins externes ou absents retirés par référence ; un chemin absent de `Workspace.images` est ignoré (aucun `save`).
- Ordre : classification pure, remplacement de `Workspace.images`, `save()` (restauration de la liste d'origine et relance en cas d'échec), puis `unlink` fichier par fichier (`deletion_failed`, sans rollback).
- Comparaison des chemins : `normcase(str(Path(p).resolve()))` des deux côtés. Limites : sémantique Windows seulement, `resolve` non strict, ni normalisation Unicode ni noms courts 8.3 (mêmes limites que Mission 168).
- Portée : la protection Dataset parcourt tous les Characters ; la protection LoRA aussi (jamais seulement le Character principal : `LoRAManager.loras` ne lit que celui-ci).
- Consommateurs : `RemovalResult` n'est construit que dans `workspace_manager.py` ; `remove_images` n'est appelé que par `ImagesPage` et par les tests.

## 5. Correction

**`src/managers/workspace_manager.py`**
- `LoRAThumbnailReference(NamedTuple)` : `character_id`, `character_name`, `lora_id`, `lora_name`, `thumbnail`. Identité = `(character_id, lora_id)`, jamais un nom ; `thumbnail` = valeur stockée telle quelle. Une référence par LoRA, dans l'ordre du Workspace, sans déduplication ni fusion par nom.
- `RemovalResult` : champ final `blocked_by_loras: Tuple[LoRAThumbnailReference, ...] = ()` (défaut immuable) et propriété `blocked` (`blocked_by` ou `blocked_by_loras` non vide).
- `RemovalInspectionError(WorkspaceManagerError)` : l'inspection LoRA n'a pas pu aboutir ; levée avant toute mutation.
- `_classify_image_removal(paths)` : la boucle de classification de `remove_images()` extraite à l'identique (mêmes appels, même ordre, même frontière d'erreur, aucun enveloppement).
- `_lora_thumbnail_refs(files)` : une référence par LoRA de tous les Characters dont la miniature non vide se résout vers l'un des fichiers ; `files` vide → `[]` sans aucun appel filesystem ; échec (`OSError`, `ValueError`, `TypeError`) → `RemovalInspectionError` ; aucun `try/except` par LoRA.
- `lora_thumbnails_blocking_removal(paths)` : lecture seule, avec la même règle (option A) ; un échec de la classification est retypé en `RemovalInspectionError`.
- `remove_images()` : voir l'ordre des contrôles ci-dessous. Suite (remplacement, `save`, rollback, `unlink`, `deletion_failed`) strictement inchangée.

**Option A (architecte).** Seuls les fichiers que l'appel supprimerait physiquement (entrées de `Workspace.images` correspondantes, dans la racine et présentes) sont protégés. Une référence externe ou absente est retirée sans blocage (son fichier n'est pas détruit) ; un fichier différent ou un chemin absent de `Workspace.images` ne bloque jamais.

**`src/ui/pages/images_page.py`**
- Pré-contrôle (consultatif) : `images_referenced_by_datasets()` d'abord (inchangé), puis `lora_thumbnails_blocking_removal()` ; un échec d'inspection ne remplace jamais un refus Dataset déjà connu.
- Après la confirmation : `remove_images()` recalcule tout ; la page traite `RemovalInspectionError` (avant le gestionnaire générique) puis `result.blocked` (avertissement final).
- Messages : texte Dataset seul inchangé octet pour octet ; blocage combiné = **un seul** avertissement (paragraphe Dataset, ligne vide, paragraphe LoRA) ; le paragraphe LoRA indique « (N au total) », une ligne par référence (« • « LoRA » (personnage « Character ») »), l'identifiant abrégé `[id xxxxxxxx]` seulement quand deux libellés sont identiques, et se tronque à cinq lignes avec « • … et N autre(s) LoRA ». L'identifiant abrégé est une aide de lecture, pas une garantie d'unicité : les références internes restent identifiées par `(character_id, lora_id)`. Un échec d'inspection a son propre message (« Impossible de vérifier les miniatures LoRA avant la suppression… Aucune image n'a été supprimée. »), distinct d'un échec d'enregistrement.

## 6. Ordre des contrôles et erreurs

Chaque étape précède toute mutation :
1. **Garde Dataset**, en premier, inchangée (mêmes appels, mêmes erreurs). Si elle refuse, le refus demeure quoi qu'il arrive ensuite : l'enrichissement LoRA est facultatif et une `RemovalInspectionError` y est avalée (le résultat contient alors `blocked_by` seul).
2. **Classification** : mêmes appels, même frontière d'erreur historique (une `OSError` brute reste brute).
3. **Garde LoRA** : atteinte seulement sans refus Dataset ; un échec lève `RemovalInspectionError` et interrompt la suppression : une référence qui n'a pas pu être examinée ne laisse jamais passer une suppression.

Aucun appel filesystem n'est ajouté avant le refus Dataset. L'inspection LoRA n'a lieu que si un fichier serait réellement supprimé. Aucun durcissement filesystem général n'est ajouté.

**Erreurs préexistantes laissées hors périmètre :** `OSError` brute de la garde Dataset (`resolve()`), classification brute dans le chemin principal, doublons d'une même image dans `Workspace.images` (`project.json` édité à la main : la seconde suppression échoue et alimente `deletion_failed`), fusion sous une même clé des Datasets de même nom dans `blocked_by`.

## 7. Compatibilité

- **Conservé :** construction de `RemovalResult` à quatre arguments (positionnels ou nommés) et lecture par attribut des quatre champs historiques.
- **Modifié :** la longueur du tuple passe de 4 à 5 ; la déstructuration en quatre éléments échoue (`ValueError`) ; une égalité avec un tuple de quatre éléments devient fausse.
- **Vérifié :** aucun consommateur interne ne déstructure ni n'indexe le résultat (recherche textuelle sur `src/` et `tests/`) ; `RemovalResult` n'est construit que dans `workspace_manager.py`.
- **Non revendiqué :** aucune compatibilité pour du code extérieur au dépôt, non vérifié.
- Le Manager recalcule la protection à chaque appel de `remove_images()` ; il n'accepte aucun résultat de pré-contrôle (celui de la page n'est que consultatif), notamment pendant la boucle d'événements du dialogue de confirmation.

## 8. Fichiers modifiés

- `src/managers/workspace_manager.py` (+224, −37) ;
- `src/ui/pages/images_page.py` (+90, −6) ;
- `tests/integration/test_workspace_roundtrip.py` (+755, −0) : un fixture (mixin) et 3 classes ajoutés avant `WorkspaceVestigialFieldsRemovalTest`, imports `contextlib` et `LoRAManager` ;
- `tests/integration/test_images_page.py` (+539, −0) : 4 éléments ajoutés avant le bloc d'entrée (un fixture et 3 classes), imports `contextlib`, `LoRAManager`, `create_workspace_with_default_character` et le filet anti-dialogue ;
- `docs/missions/MISSION_169.md` (ce document).

Fins de ligne : LF conservées partout. Aucun changement de `LoRAManager`, `LoRALibraryManager`, du Domain, du contrat de copie, de `CHANGELOG.md` ni de `PROJECT_CONTEXT.md` dans le commit fonctionnel (ces deux documents sont mis à jour par la régularisation documentaire post-Release, voir section 13).

## 9. Tests

**59 nouveaux tests** (`test_workspace_roundtrip.py` 118 → 157, `test_images_page.py` 57 → 77), en trois familles séparées.

**1. Preuves comportementales exécutables sur l'ancienne production** (API existantes seulement : fichier, galerie, `project.json` relu par un `WorkspaceManager` neuf, espions `save`/`unlink`/événements, `QMessageBox.warning`) :
- *Régressions* (11) : `WorkspaceManagerRemoveImagesLoRAThumbnailBehaviorTest` (7 : image interne, `outputs/`, sélection mixte, plusieurs Characters et noms identiques, chaque fichier protégé par sa LoRA, renommage préalable avec objets relus, sortie du Dataset sans libération de la miniature) et `ImagesPageLoRAThumbnailBehaviorTest` (4 : refus sans confirmation, sélection mixte, référence LoRA ajoutée pendant le dialogue, référence Dataset ajoutée pendant le dialogue). Le blocage LoRA « aucun `save` » est une régression, pas un invariant.
- *Invariants* (18) : `WorkspaceManagerRemoveImagesLoRAThumbnailInvariantTest` (13 : refus Dataset sans `save`/`unlink`, Dataset et LoRA ensemble, image non référencée supprimée, référence externe de même chemin, fichier absent, fichier différent, LoRA sans miniature, chemin d'avant renommage, rollback d'un échec de `save`, échec d'`unlink`, construction à quatre arguments, erreur brute de classification, aucune inspection si rien n'est détruit) et `ImagesPageLoRAThumbnailInvariantTest` (5 : texte Dataset seul inchangé, image non référencée, référence externe, confirmation annulée, message d'échec d'enregistrement).

**2. Nouveau contrat de résultat et erreurs d'inspection** : `WorkspaceManagerRemoveImagesLoRAThumbnailContractTest` (19). Ces tests lisent `blocked_by_loras`, `blocked`, `LoRAThumbnailReference`, `RemovalInspectionError` ou `lora_thumbnails_blocking_removal()` (imports paresseux : le module s'importe aussi sur l'ancienne production). Ils valident le contrat, ils ne prouvent pas le défaut. Erreurs injectées : `Path.resolve()` ne lève que pour un suffixe de chemin précis, tous les autres appels étant réels ; échec de l'inspection avec et sans refus Dataset ; échec de la classification pendant l'enrichissement du refus Dataset (le refus est conservé) ; miniature non chaîne ; référence non examinée jamais ignorée quel que soit l'ordre.

**3. Page, messages, réévaluation après confirmation** : `ImagesPageLoRAThumbnailMessageTest` (11) : décompte exact, noms et Characters, libellés identiques avec identifiants de lecture, même nom dans deux Characters, troncature à cinq lignes, noms vides, avertissement unique du blocage combiné, échec d'inspection avant la confirmation et pendant l'appel (message distinct d'un échec d'enregistrement), refus Dataset conservé malgré un échec d'inspection, avertissement final après ajout réel d'une référence pendant le dialogue simulé.

Hygiène Qt : filet anti-dialogue armé avant les widgets et arrêté en dernier ; page fermée, fermeture vérifiée, avant la suppression du projet temporaire, y compris après une assertion échouée.

## 10. Résultats (effectivement obtenus)

**Preuve avant/après** (les deux fichiers de production remis **ensemble** à leur version `HEAD`, vérifiés par empreinte SHA-256 contre les blobs Git, `git diff` de `src/` vide, sans `git stash` ; tests finals inchangés ; puis restauration octet pour octet vérifiée par empreinte). Seules les API existantes sont sollicitées par ces deux familles.

| | Avant (production `HEAD`) | Après |
|---|---|---|
| Manager : régressions (7) | **7 échecs d'assertion** | 7/7 |
| Manager : invariants (13) | 13/13 | 13/13 |
| Page : régressions (4) | **4 échecs d'assertion** | 4/4 |
| Page : invariants (5) | 5/5 | 5/5 |
| Nouveau contrat + messages (30) | 9 échecs et 21 erreurs, **non interprétés** (le contrat n'existe pas sur l'ancienne production) | 30/30 |

Soit **11 régressions échouant avant** et **18 invariants réussis avant**, puis 59/59 après.

**Validation sur l'état final** (premier plan, sortie non tamponnée, vrai code de sortie) :
- `test_workspace_roundtrip.py` complet : **157/157** (118 avant, +39), par `unittest` **et** par exécution directe du fichier avec la racine du dépôt dans `PYTHONPATH` ;
- `test_images_page.py` complet : **77/77** (57 avant, +20), par `unittest` **et** par exécution directe (même condition) ;
- couverture LoRA pertinente `test_lora_roundtrip.py` + `test_lora_library_roundtrip.py` : **407/407** ;
- **suite complète** : **3114 tests, OK, code de sortie 0**, 340,538 s d'exécution (344 s mesurées autour du processus), aucun autre processus Python au lancement, aucune ligne `FAIL`/`ERROR` ; 3055 (référence M168) + 59 = 3114. La ligne « Access denied while renaming workspace folder » du journal est la sortie de journalisation d'un test de renommage existant, pas un échec.
- `git diff --check` propre ; seuls les fichiers du périmètre sont modifiés ; aucun stash.

**Chronologie des résultats.** Les résultats ci-dessus (preuve avant/après, 59/59, **3114 tests**, **157/157**, **77/77** et **407/407**) ont été obtenus **avant** les dernières retouches documentaires, qui n'ont modifié aucun code exécutable (AST de `workspace_manager.py` hors docstrings identique à la version validée) ni aucun test, et ils n'ont **pas été réexécutés depuis**. Ces retouches sont : la docstring de `RemovalResult` (champs vides lors d'un blocage, `blocked_by` et `blocked_by_loras` renseignables ensemble, paragraphe Mission 066 limité aux chemins effectivement retirés — `deleted`, `reference_only` et `deletion_failed`, ces derniers ayant seulement vu leur `unlink` échouer —, résultat bloqué ne retirant rien), la formulation de la piste A (déclencheurs asynchrones établis, déclencheur synchrone par clic sur « Save » non démontré), la bannière et les statistiques de ce document.

Empreintes SHA-256 (16 premiers caractères) des fichiers lors de la validation, avant ces retouches : `workspace_manager.py` `3c67878865bbd522`, `images_page.py` `6f9b913f6feef0a5`, `test_workspace_roundtrip.py` `ef38dbab6e742614`, `test_images_page.py` `7fdc102512cee896`. Depuis, seul `workspace_manager.py` a changé (docstring uniquement, empreinte actuelle `b9db3ae4c0cf949c`) ; `images_page.py` et les deux fichiers de tests sont identiques octet pour octet.

## 11. Incidents de validation (conservés pour traçabilité, aucun n'est un défaut produit)

- **Première preuve avant/après invalide.** La première tentative de remise à `HEAD` par `cp` a échoué (`Permission denied`, verrou Windows transitoire) : les « avant » ont alors tourné sur la nouvelle production. L'écart a été relevé par la comparaison d'empreintes affichée par la commande ; ces résultats ont été écartés, la production n'avait pas été modifiée (empreintes vérifiées). La preuve a été refaite avec une écriture par Python, avec nouvelles tentatives et vérification d'empreinte obligatoire avant toute exécution (échec bloquant), puis rejouée une seconde fois sur le texte final des tests. Des écritures transitoires `[Errno 22]` rattrapées par les nouvelles tentatives ont été constatées lors de cet échange.
- **Test mal classé.** Un test d'abord rangé dans la famille « nouveau contrat » (aucune inspection LoRA quand rien ne serait détruit) ne lisait aucun nouvel attribut et réussissait sur l'ancienne production : c'est un invariant, déplacé dans la classe des invariants (13 au lieu de 12) ; la famille « contrat » compte 19 tests, tous échouant avant.
- Les incidents natifs/blocage de la Mission 164 restent de cause inconnue ; aucune exécution de cette mission ne les a reproduits ni résolus.

## 12. Limites et hors périmètre

- **Comparaison de chemins** : `normcase(resolve())`, validée sous Windows/NTFS ; ni normalisation Unicode, ni noms courts 8.3, ni garantie multiplateforme. Une fenêtre existe entre le recalcul de la protection et l'`unlink` (un fichier ne peut pas être protégé s'il devient miniature entre les deux).
- **Fichiers non protégés** : seules les miniatures des LoRA du Workspace sont protégées ; ni `LoRA.files`, ni les sorties de jobs d'entraînement, ni la bibliothèque centrale (ses miniatures sont des copies possédées).
- **Suppression de Dataset ou de Training** : `DatasetManager.delete()` et `TrainingManager.delete()` déplacent puis suppriment le dossier `datasets/<id>/` ou `training/<id>/` sans consulter les miniatures ni `Workspace.images` ; des entrées ou miniatures pointant par passthrough dans ces dossiers resteraient mortes. Piste distincte, déduite et non démontrée, non traitée ici.
- **Autres pistes distinctes, non traitées** : noms non enregistrés écrasés (`TrainingPage`, `LoRAPage`, `PromptsPage` : les déclencheurs asynchrones sont établis — toute sauvegarde du Workspace, par exemple celle d'un job d'entraînement, publie `WORKSPACE_SAVED` vers les autres pages abonnées, la navigation étant libre pendant un job — alors que le déclencheur synchrone par clic sur « Save » reste non démontré), autres brouillons, suffixes réservés OneTrainer `-masklabel`/`-condlabel` (parcours d'import de fichiers nommés par l'utilisateur à examiner), BOM UTF-8 des sidecars, impossibilité de vider une miniature, message d'import n'indiquant pas la miniature, durcissement des inspections filesystem préexistantes.

## 13. Références Git et publication (régularisation documentaire post-Release)

Section ajoutée par la régularisation documentaire, après la publication de la Release ; elle ne modifie ni les sections 1 à 12 ni les résultats qu'elles rapportent. La bannière de statut de ce document, telle qu'elle figure dans le commit fonctionnel, indiquait « publication en attente » ; elle est mise à jour par cette régularisation.

- **Commit fonctionnel** : `12cfa60a33dc1a0c2223657f976b8887e0a5c030` — « Protect gallery images still used as LoRA thumbnails » ; parent `e5e4f6bbd9a3f161177eaab889391f3cbadf755d` (« Document Mission 168 completion ») ; 5 fichiers (`src/managers/workspace_manager.py`, `src/ui/pages/images_page.py`, `tests/integration/test_workspace_roundtrip.py`, `tests/integration/test_images_page.py`, `docs/missions/MISSION_169.md`) ; 1751 insertions, 43 suppressions.
- **Tag annoté** `v0.2-mission169` : objet `e915973db3820557cd11a5078dd43a14b1090990`, cible `12cfa60a33dc1a0c2223657f976b8887e0a5c030` (message « Mission 169: protect gallery images still used as LoRA thumbnails »). Commit et tag ont été publiés par un push normal de `main` sans force, puis par le push du seul tag.
- **Tag `v0.2-mission168` inchangé** : objet `897f44b2e9ef6a2a177a8292e241cf74836ac34e`, cible `0fde27e0ce925bfdb1b6cc94314bade40c4c1d76`.
- **GitHub Release** : publiée manuellement par l'architecte (confirmation), puis constatée lors de la régularisation par une lecture non authentifiée de l'API publique GitHub : titre « v0.2-Mission169 — Protect Gallery Images Still Used as LoRA Thumbnails » (le titre proposé « Mission 169 — Protect Gallery Images Still Used as LoRA Thumbnails » diffère par le préfixe `v0.2-Mission169`, le titre réel fait foi), `tag_name` `v0.2-mission169`, `draft` `false`, `prerelease` `false`, `published_at` `2026-10-05T08:25:56Z` (création `2026-10-05T08:21:45Z`, `target_commitish` `main`, aucun asset), URL https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission169. Corps relu intégralement : 46 lignes, retours à la ligne CRLF tels que stockés par GitHub, sans saut de ligne final, identique au texte préparé (comparaison ligne à ligne, fins de ligne normalisées ; seul le saut de ligne final du texte préparé n'est pas stocké) ; rendu HTML de GitHub conforme (cinq titres de section `##` rendus en titres de niveau 2, 11 paragraphes, deux listes de 6 et 7 éléments) ; ses chiffres (59 nouveaux tests dont 11 régressions, 18 invariants et 30 tests du nouveau contrat et des messages, 157/157, 77/77, 407/407, 3114) et ses limites concordent avec les sections 9 à 12, y compris la première preuve avant/après invalide ; la mention que les références de miniature déjà mortes ne sont pas réparées figure dans le corps de la Release et est consignée ici comme limite supplémentaire.
- **Chronologie des résultats** : la dernière suite complète réussie est 3114/3114, exit 0, obtenue avant les dernières retouches documentaires et de docstrings ; le code exécutable et les tests ont été vérifiés inchangés après ces retouches (section 10) et aucun test n'a été réexécuté depuis, y compris pendant la régularisation documentaire.
- **Statut** : Mission 169 entièrement close. Aucune Mission 170 n'est sélectionnée ; un nouvel audit global READ-ONLY devra précéder toute décision. Les pistes ouvertes (section 12) et les incidents natifs de Mission 164 (causes inconnues) restent ouverts.
