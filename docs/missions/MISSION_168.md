# Mission 168 — Prevent Caption Sidecar Collisions When Materializing Training Images

> **MISSION 168 CLOSE — implémentation validée par revue architecte, commit fonctionnel et tag publiés, GitHub Release publiée manuellement (références en section 11).** `TrainingManager._materialize_concept()` copiait chaque image du Dataset dans le dossier concept sous un nom choisi uniquement d'après son **nom complet**, puis écrivait un sidecar `.txt` dérivé de son **radical**. Deux images de même radical et d'extensions différentes (`a.png` et `a.jpg`) partageaient donc le même `a.txt` : la dernière écrite l'emportait, l'autre image héritait de son texte (ou perdait sa caption, vide ou non). Découvert par l'audit global post-Mission 167 (candidat H), confirmé par une sonde dynamique de conception, puis corrigé localement par un allocateur de noms à deux passes, sans toucher au helper partagé. Mission close : push, tag et Release sont effectués ; le commit documentaire de régularisation n'est ni tagué ni référencé en dur.

## 1. Défaut confirmé

`src/managers/training_manager.py::_materialize_concept()` :
- choisissait le nom de l'image par `WorkspaceStorage.resolve_collision_free_name(source, concept_folder)`, qui ne teste que le nom complet (existence sur disque) ;
- écrivait le sidecar par `target.with_suffix(".txt")`, soit un fichier par radical ;
- écrivait toujours un sidecar, pour chaque image : caption du Dataset (y compris `""`) si une entrée existe, sinon `trigger_word`.

OneTrainer (sources installées, lues sans être importées ni lancées) dérive le sidecar par `os.path.splitext(image_path)[0] + ".txt"` (mgds `ModifyPath`), seule la dernière extension étant retirée. Un sidecar absent ou vide donne la liste de textes `[""]` dans le chemin lu (`LoadMultipleTexts`), sans repli sur le trigger word ; aucune conclusion n'est tirée ici sur l'effet de ce prompt vide sur l'entraînement.

## 2. Preuve empirique (sonde de conception, hors dépôt)

Projets temporaires construits par les vrais Managers, avec de vraies images valides (couleurs distinctes), le vrai `prepare_onetrainer_config()` et, pour un scénario, le vrai `create_job()` sans runner. L'association image → sidecar → texte est recalculée selon les quatre modules OneTrainer cités. 15 scénarios, aucune exception.

| Scénario | Constat avec le code antérieur |
|---|---|
| `a.png`, `a.jpg`, captions distinctes (deux ordres) | un seul `a.txt` ; la dernière image écrite impose son texte à l'autre |
| captionnée + sans entrée (deux ordres) | l'image sans entrée hérite du texte de l'autre, ou le remplace par le trigger word |
| caption vide + texte (deux ordres) | le vide explicite peut disparaître ; le dernier écrit gagne |
| deux images sans aucune entrée | un seul sidecar partagé ; textes identiques (le trigger word), donc associations « correctes » par coïncidence |
| trois images de même radical | seule la dernière écrite est correcte |
| `a.png`, `a.jpg`, `a_1.png` | `a.png`/`a.jpg` partagent `a.txt` ; `a_1.png` correct |
| `my.photo.png`, `my.photo.jpg` | `my.photo.txt` partagé (seule la dernière extension compte) |
| `A.png`, `a.jpg` | un seul `A.txt` (NTFS insensible à la casse) |
| snapshot de job (`create_job`) | le partage est figé dans la copie du job |
| `001.png` en galerie + `001.png` importé ; `my.photo.png` + `my.png` | corrects (invariants) |

Dans tous les scénarios, captions du Domain, sources et noms du Dataset restent inchangés. Limites de la sonde : OneTrainer non exécuté (association réimplémentée d'après les sources lues), casse observée sur NTFS seulement, images de 16×16 pixels, une exécution par scénario.

## 3. Chaîne causale

1. `resolve_collision_free_name()` ne réserve que le nom complet : `a.png` et `a.jpg` coexistent.
2. Le sidecar est dérivé du radical : les deux images pointent sur `a.txt`.
3. Chaque image réécrit ce fichier : le dernier écrit gagne.
4. `create_job()` copie le dossier concept tel quel : le partage est figé dans chaque job créé ensuite.

## 4. Correction

**Production (1 fichier)** : `src/managers/training_manager.py`.
- `import os` ajouté (absent jusque-là).
- Deux fonctions privées, pures, sans I/O, au niveau module avant `class TrainingManager` :
  - `_concept_stem_key(name)` = `os.path.normcase(os.path.splitext(name)[0])` ;
  - `_allocate_concept_file_names(sources)` : une liste de noms, même longueur et même ordre que `sources`.
- `_materialize_concept()` calcule les noms une fois, dans le `try` existant, puis copie chaque image sous son nom alloué (`zip(..., strict=True)`). Inchangés : suppression/reconstruction du dossier, nettoyage des erreurs (Mission 134), `shutil.copy2`, règle caption/`trigger_word`, sidecar toujours écrit.
- Le helper partagé `resolve_collision_free_name()`, les imports Dataset et Images, les sources, le Domain, les noms persistés et les jobs existants ne sont pas modifiés.
- `zip(strict=True)` ne sert qu'à vérifier les longueurs : la cohérence des longueurs relève du contrat interne de l'allocateur. Une `ValueError` éventuelle ne serait pas interceptée par l'`except (WorkspaceStorageError, OSError)` existant ; aucun élargissement des exceptions n'a été fait.

**Règle à deux passes (ordre du Dataset).**
1. Le premier représentant de chaque radical garde son nom d'origine. Tous les radicaux d'origine sont réservés avant toute attribution, y compris ceux d'images situées après un doublon : une image sans collision de radical (`a_1.png`) n'est jamais renommée.
2. Chaque doublon reçoit `<radical>_<n><extension>` avec le plus petit `n ≥ 1` dont la clé n'est ni un radical d'origine réservé ni un radical déjà attribué. Les candidats de `n` différents ont des clés distinctes et l'ensemble réservé est fini : la boucle se termine, au plus `len(sources)+1` essais par doublon.

Exemples exacts, dans l'ordre des entrées :

| Entrée | Sortie |
|---|---|
| `[a.png, a.jpg]` | `[a.png, a_1.jpg]` |
| `[a.png, a.jpg, a_1.png]` | `[a.png, a_2.jpg, a_1.png]` |
| `[a_1.png, a.jpg, a.png]` | `[a_1.png, a.jpg, a_2.png]` |
| `[001.png, 001.png, 001_1.png]` | `[001.png, 001_2.png, 001_1.png]` |
| `[x.png, x.png, x.png, x_1.jpg, x_2.png]` | `[x.png, x_3.png, x_4.png, x_1.jpg, x_2.png]` |

**Compromis de compatibilité (accepté).** Les noms de fichiers du concept sont dérivés et reconstruits à chaque préparation ; ils ne sont jamais persistés dans le Dataset.
- Pour des noms complets déjà distincts sans radical partagé, l'allocation est identique à l'ancienne. Il en va de même pour des doublons de nom complet sans nom pré-suffixé coexistant (`[001.png, 001.png]`, `[x.png, x.png, x.png]`).
- Réserver les radicaux d'origine peut changer un nom dérivé qui était valide : `[001.png, 001.png, 001_1.png]` donne maintenant `[001.png, 001_2.png, 001_1.png]`, alors que l'ancien code produisait `[001.png, 001_1.png, 001_1_1.png]` avec des sidecars distincts. Les appariements de cet exemple étaient corrects avant : ce n'est **pas** présenté comme la correction d'une corruption antérieure, mais comme la conséquence assumée de la règle « un nom d'origine sans collision n'est jamais renommé ». Le changement n'a lieu que dans les concepts reconstruits et les snapshots de jobs créés ensuite.
- Les seuls cas où l'ancienne allocation était fausse sont ceux où elle produisait un sidecar partagé.

## 5. Comparaison des noms : radical OneTrainer et normalisation choisie

- Le radical utilisé par OneTrainer est `os.path.splitext(image_path)[0]` (une chaîne ; le fichier est ensuite résolu selon les règles du système de fichiers).
- La clé de collision choisie ici, `os.path.normcase(...)`, est une **approximation** de « deux radicaux désignent le même sidecar », retenue pour la plateforme validée (Windows/NTFS). Observé : `A.png` et `a.jpg` ont produit un seul `A.txt`.
- Limites non revendiquées : `normcase` n'est pas la table de casse de NTFS (caractères non ASCII, ligatures, cas particuliers) ; pas de pliage de la normalisation Unicode (NFC/NFD), ni des noms courts 8.3, ni des points ou espaces finaux propres à Windows ; aucune garantie multiplateforme (sous POSIX `normcase` est l'identité, correct pour un système de fichiers sensible à la casse ; un système insensible à la casse hors Windows n'a pas été vérifié).
- Les tests de casse sont donc des garanties de la plateforme Windows validée (marqués `skipUnless(os.name == "nt")`), pas une équivalence universelle.

## 6. Fichiers modifiés

- `src/managers/training_manager.py` (production, CRLF conservé, 83 ajouts, 3 suppressions) ;
- `tests/integration/test_training_roundtrip.py` (CRLF conservé, 444 ajouts, 0 suppression) : deux classes ajoutées après les tests de préparation M097 ; le bloc `if __name__ == "__main__"` reste la dernière chose du fichier ;
- `docs/missions/MISSION_168.md` (ce document).

Aucun changement du helper partagé, de `DatasetManager`, de `WorkspaceManager`, des pages, du Domain, de `CHANGELOG.md` ni de `PROJECT_CONTEXT.md` dans le commit fonctionnel (ces deux documents sont mis à jour par la régularisation documentaire post-Release, voir section 11).

## 7. Tests

**`TrainingManagerConceptSidecarPairingTest` (15, API publique existante uniquement)** : `prepare_onetrainer_config()` et `create_job()` sans runner. Les images sont distinguées par des contenus binaires distincts ; chaque assertion identifie quelle image reçoit quel texte (association recalculée à la manière de OneTrainer) et vérifie l'unicité des sidecars et l'absence de fichier étranger.

*Régressions comportementales (11, échouent sur la production antérieure)* :
- même radical et extensions différentes, captions distinctes, deux ordres ;
- caption présente et absente (repli `trigger_word`), deux ordres ;
- caption vide explicite et texte, deux ordres ;
- deux images sans aucune entrée (unicité des sidecars) ;
- trois images de même radical ;
- noms pré-suffixés (`a.png a.jpg a_1.png` et `a_1.png a.png a.jpg`), `a_1.png` conservant son nom ;
- noms à plusieurs points de même radical ;
- variantes de casse `A.png`/`a.jpg` (Windows/NTFS seulement) ;
- préparations répétées avec radical partagé, puis rétrécissement du Dataset sans fichier périmé ;
- snapshot de `create_job()` (pairings conservés, sans runner) ;
- flux complet `DatasetManager.add_images()` + `set_caption()` + `prepare`, `project.json` et chemins du Dataset inchangés.

*Invariants déjà vrais avant la correction (4)* : noms complets identiques depuis deux dossiers (`001.png`, `001_1.png`, Mission 097) ; noms à plusieurs points de radicaux distincts ; aucune mutation des sources, des captions du Domain, des chemins du Dataset ni de `project.json` ; nettoyage du dossier concept après un échec de copie malgré un radical partagé (complète les tests de nettoyage M134 existants, conservés).

**`ConceptFileNameAllocatorContractTest` (9, contrat du nouvel allocateur)** : testés séparément, l'allocateur étant importé paresseusement pour que le module de tests s'importe quel que soit l'état de la production. Ces tests valident le contrat ; ils ne constituent pas la preuve du défaut (la fonction n'existe pas sur l'ancienne production). Ils couvrent les cinq exemples exacts du tableau ci-dessus, l'absence de collision (noms d'origine conservés), les doublons de nom complet, les noms à plusieurs points, l'ordre et la longueur quels que soient les dossiers, l'unicité des clés et le déterminisme, la terminaison sur une longue chaîne de noms pré-suffixés (`a_51.jpg`), la clé indépendante de l'extension et déléguée à `normcase`, et (Windows seulement) l'équivalence de casse ASCII.

## 8. Résultats (effectivement obtenus)

**Preuve avant/après, exclusivement par les API publiques existantes** (seul le fichier de production remplacé par sa version `HEAD`, sans `git stash` : sauvegarde octet-exacte avec empreinte SHA-256, version `HEAD` convertie en CRLF, convention de ce fichier, puis restauration vérifiée par `cmp` et par empreinte) :
- production antérieure, classe `TrainingManagerConceptSidecarPairingTest` seule (15 tests) : **15 échecs d'assertion** (11 méthodes ; les sous-cas de trois d'entre elles comptent chacun) sur les associations image/caption et l'unicité des sidecars, aucune erreur d'import ni d'exécution ; les 4 invariants réussissent ;
- production corrigée : **24/24** (15 + 9), code 0 ;
- empreinte SHA-256 de la production corrigée `58c95aa537043e2ee8547c49751dcd3e46d9310f5c42a2e49c505e76bd161b59`, identique avant et après la preuve ; CRLF 1486/1486 ; aucun stash.

**Validation sur l'état final** (premier plan, sortie non tamponnée, vrai code de sortie) :
- classes existantes `TrainingManagerPrepareOnetrainerConfigTest` et `TrainingManagerCreateJobTest` : 57/57, code 0 (identique avant la mission) ;
- `test_training_roundtrip.py` complet : **412/412** (388 avant, +24), code 0, par la commande habituelle (`python -m unittest tests.integration.test_training_roundtrip`) **et** par exécution directe du fichier (avec la racine du dépôt dans `PYTHONPATH`, comme pour tout test du projet) ; le bloc `unittest.main()` est après toutes les classes ;
- **suite complète** : **3055 tests, OK, code de sortie 0**, 376,049 s d'exécution (382 s mesurées autour du processus), aucun autre processus Python au lancement, aucune ligne `FAIL`/`ERROR` ; 3031 (référence M167) + 24 = 3055 ;
- `git diff --check` propre ; seuls les fichiers de production et de tests ci-dessus sont modifiés, plus ce document.

## 9. Incidents de validation (conservés pour traçabilité, aucun n'est un défaut produit)

- **`import os` absent** : la première exécution du prototype de test a échoué (45 erreurs `NameError`) parce que `training_manager.py` n'importait pas `os`. Constat intégré à la conception ; l'import a été ajouté en production.
- **Libellé d'un sous-cas** : après la première preuve avant/après, le libellé des sous-cas du test « caption vide et texte » a été précisé (captions incluses). Modification d'affichage uniquement ; la preuve avant/après a été **rejouée** sur le texte final des tests (résultats ci-dessus).
- **Exécution directe du fichier** : sans `PYTHONPATH` le fichier échoue à l'import de `src` (comportement antérieur à la mission, indépendant d'elle) ; avec la racine du dépôt dans `PYTHONPATH`, 412/412.
- Les incidents d'exécution natifs/blocage de la Mission 164 restent de cause inconnue ; aucune exécution de cette mission ne les a reproduits ni résolus.

## 10. Limites et hors périmètre

- **Anciens snapshots non réparés.** Les jobs créés avant cette mission conservent leur copie du dossier concept, avec les sidecars partagés éventuels : aucune réparation rétroactive. Une nouvelle préparation suivie d'un nouveau job utilise l'allocation corrigée.
- Les noms du concept ne sont jamais écrits dans le Dataset ; les noms d'origine sont conservés quand aucun radical n'est partagé.
- Limites de `normcase` et de la plateforme validée : voir section 5.
- OneTrainer n'a pas été lancé : l'association image → sidecar est celle des sources lues, pas une exécution.
- Hors périmètre, laissés ouverts : BOM UTF-8 des sidecars (effet sur l'entraînement non établi) ; images dont le radical finit par `-masklabel` ou `-condlabel`, exclues par `CollectPaths` (statique, non sondé) ; noms en commit-on-blur sur Training/LoRA/Prompts (candidat A, déclencheur par clic « Save » non démontré) ; suppression d'une image de galerie encore utilisée comme miniature LoRA ; brouillon de métadonnées LoRA après un échec d'une autre opération ; erreurs filesystem brutes de l'exposition LoRA et des imports ; readiness ComfyUI face à une exception hors `ComfyUIEngineError` ; perte de sélection sur `ImagesPage` ; dérives de description d'architecture dans `docs/PROJECT_CONTEXT.md` ; incidents natifs M164.
- Le commentaire de `MainWindow.rename_project()` (Mission 084) n'est pas déclaré sûr pour les noms : l'hypothèse de focus du menu reste non démontrée et hors de cette mission.

## 11. Références Git et publication (régularisation documentaire post-Release)

Section ajoutée par la régularisation documentaire, après la publication de la Release ; elle ne modifie ni les sections 1 à 10 ni les résultats qu'elles rapportent. La bannière de statut de ce document, telle qu'elle figure dans le commit fonctionnel, indiquait « publication en attente » ; elle est mise à jour par cette régularisation.

- **Commit fonctionnel** : `0fde27e0ce925bfdb1b6cc94314bade40c4c1d76` — « Prevent caption sidecar collisions when materializing training images » ; parent `22549a8b3bad3f32508f6f0861a58af947d82620` (« Document Mission 167 completion ») ; 3 fichiers (`src/managers/training_manager.py`, `tests/integration/test_training_roundtrip.py`, `docs/missions/MISSION_168.md`) ; 660 insertions, 3 suppressions.
- **Tag annoté** `v0.2-mission168` : objet `897f44b2e9ef6a2a177a8292e241cf74836ac34e`, cible `0fde27e0ce925bfdb1b6cc94314bade40c4c1d76` (message « Mission 168: prevent caption sidecar collisions when materializing training images »). Commit et tag ont été publiés par un push normal de `main` sans force, puis par le push du seul tag.
- **Tag `v0.2-mission167` inchangé** : objet `8d6030a4b1422a286c9860a99dc1f2206c20c24a`, cible `b1d1dc8c47078faff49700d6f53b36f7d225529e`.
- **GitHub Release** : publiée manuellement par l'architecte (confirmation), puis constatée lors de la régularisation par une lecture non authentifiée de l'API publique GitHub : titre « v0.2-Mission168 — Prevent Caption Sidecar Collisions When Materializing Training Images » (le titre proposé « Mission 168 — Prevent Caption Sidecar Collisions When Materializing Training Images » diffère par le préfixe `v0.2-Mission168`, le titre réel fait foi), `tag_name` `v0.2-mission168`, `draft` `false`, `prerelease` `false`, `published_at` `2026-10-03T10:31:29Z` (création `2026-10-03T10:30:09Z`, `target_commitish` `main`, aucun asset), URL https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission168. Corps relu intégralement : 41 lignes, retours à la ligne CRLF tels que stockés par GitHub, identique au texte préparé (comparaison ligne à ligne, fins de ligne normalisées) ; rendu HTML de GitHub conforme (15 paragraphes dont les cinq titres de section en texte simple, deux listes de 4 et 6 éléments) ; ses chiffres (24 nouveaux tests dont 15 + 9, 15 échecs d'assertion sur 11 méthodes régressives avec 4 invariants, 24/24, 57/57, 412/412, 3055) et ses limites concordent avec les sections 7 à 10.
- **Chronologie des résultats** : la dernière suite complète réussie est 3055/3055, exit 0, obtenue sur l'état final de la production et des tests pendant la mission ; seule la bannière de statut de ce document a été finalisée ensuite. Aucun test n'a été relancé pendant la régularisation documentaire.
- **Statut** : Mission 168 entièrement close. Aucune Mission 169 n'est sélectionnée ; un nouvel audit global READ-ONLY devra précéder toute décision. Les pistes ouvertes (section 10) et les incidents natifs de Mission 164 (causes inconnues) restent ouverts.
