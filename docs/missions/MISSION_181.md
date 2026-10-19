# Mission 181 — Restaurer une validation complète sûre : campagne partitionnée, un processus par module de tests

> **STATUT (mis à jour le 2026-10-19, après l'acceptation de la revue pré-commit) : campagne partitionnée examinée avec réserves ; périmètre canonique incomplet, L18 non exécuté ; suite complète partitionnée non validée ; correction du test L66 validée de façon ciblée ; revue pré-commit acceptée ; commit local autorisé avec réserves ; publication non autorisée ; mission non close.** *(Statut antérieur, daté du 2026-10-19, avant l'acceptation de la revue pré-commit, conservé et dépassé : « campagne partitionnée examinée avec réserves ; périmètre canonique incomplet, L18 non exécuté ; suite complète partitionnée non validée ; correction du test L66 validée de façon ciblée ; revue pré-commit en préparation ; commit non autorisé ; mission non close ».)* Ni cette mission ni ce document ne présentent la campagne comme une validation de la suite complète : 65 lots canoniques sur 66 ont été exécutés, soit **3 486 identifiants distincts sur 3 627** ; le lot L18 (141 tests, fixtures Forge) n'a jamais été exécuté et n'est pas autorisé. Aucun identifiant de commit, de tag ou de Release n'est anticipé dans ce document.

## 1. Objectif et limites

**Problème de départ.** Depuis Mission 177, la suite complète n'est plus validée : la seule tentative d'exécution de la suite monoprocessus via `unittest discover` a été interrompue par un arrêt anormal du processus testé (`0xC0000374`) après 104 résultats `ok` (de tests exécutés, pas d'une découverte seule), cause inconnue, non résolue (réserve de Mission 177, conservée telle quelle). Mission 181 est une **phase 1 de validation et de diagnostic, sans modification de production** : elle cherche un moyen de revalider la suite en toute sécurité, en la partitionnant en **un processus neuf par module de tests**, chacun sous le superviseur Job Object de Mission 176.

**Ce que la campagne partitionnée est.** 66 lots canoniques (un par module de tests de la découverte, 3 627 identifiants au total, hash de l'ordre de découverte consigné) plus un fichier isolé hors découverte (I1, `isolated_test_onetrainer_cancel_helper`, 4 tests, **hors des 3 627**). Chaque lot est exécuté une fois par tentative dans son propre processus (`unittest discover -s tests -p <fichier> -v`), avec environnement privé (répertoires temporaires, profil et données locales privés), Qt hors écran, politique réseau `none` (`own_loopback_listeners` pour L13), un enregistreur de résultats par identifiant, et un contrôle strict de la supervision.

**Ce qu'elle n'est pas.** Elle ne peut pas être appelée « équivalente » à une exécution monoprocessus : les interactions possibles entre modules dans un même processus (état global partagé, ordre, fuites de ressources) ne sont pas exercées, et le plantage de Mission 177 n'a pas été reproduit **ni expliqué** par cette campagne (réserve distincte, non rouverte). Une réussite de tous les lots n'aurait donc ni démontré l'équivalence monoprocessus ni résolu Mission 177. La reproductibilité n'est pas établie : un lot, un résultat, par état du code.

**Hors périmètre, différé** : dérives documentaires déjà identifiées (README, introduction de `docs/PROJECT_CONTEXT.md`, commentaire de `Workspace.root`), audit de dépendances, et les candidates B, C, D, E de l'inventaire (ordre des gardes de fermeture, ordre de `SelectImagesDialog`, `masklabel`/`condlabel`, cache de vignettes) : inventoriées, **non commencées**. Aucune réintroduction du correctif de nettoyage de Mission 099.

## 2. Décisions de l'architecte (résumé)

Candidate A retenue, première phase limitée à la validation et au diagnostic ; qualification « suite complète partitionnée » possible **seulement** si la couverture et les résultats sont démontrés, jamais « équivalente » à la suite monoprocessus ; le plantage de Mission 177 reste une réserve distincte ; la reproductibilité n'est pas établie après une seule passe ; les qualifications `OK_NON_NET` sont conservées ; poursuite après un échec de test ordinaire seulement si l'exécution est complète, les identifiants conformes, le code naturel 1, la supervision conforme et sans intervention (jamais après une erreur de fixture, d'import ou d'outillage) ; I1 en dernier et rapporté séparément ; plafonds de processus acceptés comme seuils d'arrêt prudents, non comme preuve ; **option B pour le lot Forge L18** (séquence `--forge skip` d'abord, décision séparée pour L18 ensuite) : **L18 n'est pas autorisé** ; budget global de lancement de 120 minutes (budget de **lancement**, non garantie de durée totale).

## 3. Méthode et niveaux de résultat

Chaîne par lot : pilote de séquence (journal, barrières, verrou) → lanceur → pilote de lot → superviseur Job Object (processus suspendu à la création, `KILL_ON_JOB_CLOSE`, comptage des membres) → enveloppe d'exécution (enregistreur `RecordingResult` de chaque identifiant, résultat et phase) → `unittest`. **Barrières** à l'entrée et à la sortie de chaque lot (état Git, `__pycache__` détaillé, emplacements réels surveillés du profil, recensement de processus par identité pid + date de création), seconde lecture des preuves par un code distinct du pilote (même preuve, pas une seconde observation), arrêt conservateur sur tout survivant, ambigu ou suspect.

Niveaux : `NET` (tous contrôles vrais) ; `OK_NON_NET` (succès, seuls les contrôles de code de sortie, de complétude et d'inventaire sont faux, code superviseur exactement 20, motifs exclusivement « N process(es) … never identified » avec N = comptés − identifiés) ; `ECHEC_DE_TEST_PROPRE` (échec d'assertion ordinaire, dans le corps du test seulement) ; `ECHEC_OU_NON_CONCLUSIF` (arrêt). **Qt (règle révision 3)** : attendu par lot (statique, fermeture des imports de niveau module) et recoupé à l'exécution — « chargé conforme », « non applicable, non chargé » (absence cohérente), jamais une dispense automatique ; les états bloquants restent bloquants.

**Classes de processus** (matrice par lot, plafonds jamais une preuve) : P0 (≤ 3 processus), P1 (L07, L26, L60 : vrais enfants `QProcess` factices ; plafonds 153, 15, 87), P2 (L18 : Forge, 600), P3 (L03, ≤ 6), P4 (I1, ≤ 15). Les réserves Forge F1 à F5 (vrai `taskkill /PID /T /F`, fenêtres de réutilisation de PID, faiblesses de `_LifecycleCase`) ne sont **pas** acceptées par héritage : L18 exige une décision séparée.

## 4. Trois tentatives, trois révisions d'outillage, trois manifestes, deux états du code

Quatre notions distinctes, jamais confondues :

| Tentative | Périmètre | Révision d'outillage | Manifeste (`sha256`) | État du code |
|---|---|---|---|---|
| 1 | L01 à L04 (arrêt en L04) | rév. 2 | `2b394f28…` | état 1 |
| 2 (`--forge skip`, départ L05) | L05 à L66 hors L18, puis I1 | rév. 3 | `07282a6c…` | état 1 |
| 3 (`3_L66`) | L66 seul | rév. 4 | `c14aa8cf…` | état 2 |

- **État 1** : `HEAD` à `661da483…`, arbre de travail propre hors `graphify-out/`, fichiers `src/` et `tests/` à l'empreinte du manifeste (arbre `c4f81185…`). Les tentatives 1 et 2 portent sur **le même code** : les deux manifestes ont le même arbre.
- **État 2** : même `HEAD`, un seul fichier modifié et non commité, `tests/integration/test_workspace_roundtrip.py` (section 7) ; arbre `c9c88aba…`.
- **Le changement de manifeste entre les tentatives 1 et 2 n'est pas une modification du code du projet** : il ne porte que sur les attentes Qt par lot (champs `qt_expectation`, `qt_justification`, `qt_static`, listes `qt_module_level_importers` et `qt_expectation_summary`, révision d'outillage) ; l'arbre `src/`/`tests/`, les identifiants attendus de chaque lot et l'empreinte de découverte sont identiques (vérifié en lecture seule sur les manifestes archivés).
- **Le passage à la tentative 3 est un changement de code** (un fichier de test) et un changement d'outillage (rév. 4 : copies dérivées des pièces de la rév. 3, qui exigeaient un arbre propre, c'est-à-dire aucune entrée de statut Git hors `graphify-out/` ; les pièces rév. 4 **n'exigent plus l'arbre propre** et autorisent désormais **exactement** une seule modification, ` M tests/integration/test_workspace_roundtrip.py`, dont l'empreinte est épinglée dans le manifeste ; toute autre entrée de statut les ferait refuser ; `--only L66` est obligatoire avec `--forge skip`).
- Les pièces des révisions précédentes sont conservées intactes ; chaque tentative est un journal distinct (« une tentative ne contient ni ne remplace aucune autre »).

## 5. Résultats historiques par tentative

### Tentative 1 (rév. 2, état 1) — arrêt en L04
L01, L02, L03 : `NET` (23, 81 et 32 tests). **L04** (`test_comfyui_engine`, 117 tests) : **117 réussites sur 117, mais niveau historique `ECHEC_OU_NON_CONCLUSIF`** — un seul critère faux, la provenance de PySide6, que la révision 2 exigeait inconditionnellement alors que ce module n'importe pas Qt : **défaut d'outillage, pas résultat de test**. Arrêt de la séquence ; I1 non exécuté ; 253 tests exécutés (tous réussis). Ce verdict n'est **jamais réécrit**.

### Tentative 2 (rév. 3, état 1) — fin normale, 672,4 s
62 exécutions : 61 lots canoniques (L05 à L66 hors L18) plus I1. **57 `NET`, 4 `OK_NON_NET` (L07, L26, L60 et I1), 1 `ECHEC_DE_TEST_PROPRE` (L66).** 3 233 tests canoniques exécutés sur 3 233 attendus ; I1 4 sur 4. Aucun arrêt, aucune intervention, aucun survivant, ambigu ou suspect ; barrières égales à la ligne de base à chaque lot.
- `OK_NON_NET` : inventaire de processus incomplet **exclusivement** (code superviseur 20, `clean_exit`, aucune intervention) — L07 52 comptés / 46 identifiés (plafond 153), L26 7 / 3 (15), L60 34 / 22 (87), I1 11 / 8 (15). Les membres non identifiés restent d'identité inconnue ; un inventaire incomplet ne montre ni survivant ni défaut du code testé.
- **L66** : 157 tests exécutés, 156 `ok` et **1 échec** (`WorkspaceRoundTripTest.test_full_create_import_save_close_reopen_cycle`, première attente d'affichage de la méthode). Les assertions situées après ce point **n'étaient pas évaluées** par cette exécution. Verdict historique **conservé** (section 7).

### Tentative 3 (rév. 4, état 2) — L66 seul, fin normale, 13,7 s
**L66 `NET`** : 157 tests attendus et exécutés, chacun une fois, 157 `ok`, aucune erreur, aucun échec, aucun ignoré, code naturel 0, superviseur 0, `clean_exit`, aucune intervention, inventaire complet (3 comptés, 3 identifiés), aucun `Popen`, aucun survivant ; barrières égales à la ligne de base. Le cycle corrigé va **jusqu'au bout** : les assertions situées après l'ancien point d'échec (Domain, `project.json`, identité, fermeture, réouverture avec gestionnaire et pages neufs, affichage de la page rouverte) ont été évaluées et ont réussi dans cette campagne, contrairement à la tentative 2, où la méthode s'arrêtait avant ; aucune affirmation n'est faite sur l'histoire antérieure du test.

## 6. Réévaluation distincte de L04 (lecture seule)

La règle Qt corrigée (révision 3) a été appliquée **en lecture seule** aux preuves de L04 (métadonnées de la révision 2) : attente « non requis », absence cohérente et aucun importateur connu chargé → état « non applicable, non chargé », critère satisfait ; aucun autre critère faux dans le verdict historique. C'est une **réévaluation documentaire du seul critère Qt**, pas une nouvelle exécution : L04 n'est **jamais** présenté comme un résultat `NET` ni comme exécuté par la révision 3. Trois éléments restent distincts : le verdict historique `ECHEC_OU_NON_CONCLUSIF`, les 117 réussites avec une supervision complète, et la réévaluation du critère. L'architecte l'a acceptée comme élément de validation de ses 117 tests exécutés (lecture B ci-dessous). L01 à L04 n'ont pas été relancés.

## 7. Correction du test de L66

**Qualification.** L'échec de la tentative 2 est l'**adaptation oubliée d'une attente d'affichage au contrat de Mission 180** : le test construit `ImagesPage` sans choisir un autre tri, attendait l'affichage `ref1, ref2`, alors que le contrat de Mission 180 prévoit désormais, par défaut, la liste enregistrée inversée (`ref2, ref1`). Les attentes sur l'ordre du Domain et du fichier enregistré (`ref1, ref2`) restent exactes. **Aucune régression fonctionnelle du tri n'est démontrée** ; le test n'avait pas été adapté par Mission 180 (il ne figurait pas dans ses quatre fichiers de tests adaptés) et sa validation ciblée ne l'exécutait pas.

**Correction minimale, un seul fichier de test, aucune modification de production.** Dans `WorkspaceRoundTripTest.test_full_create_import_save_close_reopen_cycle` : les deux attentes d'affichage (après l'ajout des deux images, puis sur la page rouverte `images_2`, page neuve donc au critère par défaut) deviennent `["ref2.png", "ref1.png"]` ; une assertion explicite `sort_combo.currentData() == "added"` précède chacune ; commentaires explicatifs. **Le tri « Nom » n'est pas forcé** pour faire passer le scénario, et **toutes les assertions de persistance et d'identité sont conservées** (liste du Domain, contenu de `project.json`, identifiants d'images, existence des sources, fermeture, réouverture). Delta : 10 lignes ajoutées, 2 supprimées (les deux attentes).

**Validation ciblée.** L66 complet (157 tests) en tentative 3, sur l'état 2, résultat `NET` (section 5). C'est une validation **ciblée, sur un seul lot, une seule exécution** : elle ne démontre ni la reproductibilité ni l'exécution de toute la campagne sur un manifeste unique.

**Le verdict historique de la tentative 2 est conservé.** Les deux exécutions de L66 ne sont pas cumulées comme des tests distincts : les 157 identifiants de L66 sont comptés **une fois** dans la couverture consolidée ; les 156 réussites de la tentative 2 restent des observations valides de l'état 1.

## 8. Couverture et résultats retenus (lecture B acceptée)

**Couverture exécutée** : **65 lots canoniques sur 66, soit 3 486 identifiants distincts sur 3 627** (les 141 tests de L18 manquent). Sur ces 3 486 identifiants distincts, 3 485 n'ont que des exécutions `ok` ; un seul — `test_full_create_import_save_close_reopen_cycle` — a une exécution en échec (état 1) puis une exécution `ok` (état 2). Par exécution (non additionnées pour le lot rejoué) : tentative 1 = 253 `ok` ; tentative 2 = 3 232 `ok` et 1 échec ; tentative 3 = 157 `ok`. I1 : voir section 9.

**Résultats retenus, lecture B** (acceptée : verdicts historiques `NET` / `OK_NON_NET`, plus la réévaluation de L04), chaque identifiant compté une fois, avec sa qualification individuelle :

| Qualification | Lots | Identifiants | État du code |
|---|---|---|---|
| `NET` | 61 (dont L01 à L03 de la tentative 1, 57 de la tentative 2 et L66 de la tentative 3) | 3 061 | 60 lots / 2 904 en état 1, L66 / 157 en état 2 |
| `OK_NON_NET` (inventaire incomplet exclusivement) | 3 (L07, L26, L60) | 308 | état 1 |
| Réévaluation en lecture seule du critère Qt (L04), historique `ECHEC_OU_NON_CONCLUSIF` | 1 | 117 | état 1 |
| **Total retenu** | **65** | **3 486** | état 1 : 64 lots / 3 329 ; état 2 : 1 lot / 157 |

Lecture A (verdicts historiques seuls, sans réévaluation de L04) : 64 lots, 3 369 identifiants. Dans les deux lectures, **la validation retenue ne repose pas sur un manifeste ni un état du code uniques**. La somme n'est pas une suite complète et n'est pas présentée comme telle.

## 9. I1 (fichier isolé, séparé)

I1 (4 tests, hors des 3 627) : **4 réussites sur 4**, exécuté en tentative 2, niveau `OK_NON_NET` (inventaire 11 comptés / 8 identifiés, 4 `subprocess.Popen` audités, tous conformes). Compté **séparément**, jamais ajouté aux 3 486.

## 10. L18 (non exécuté)

**141 tests non exécutés** (`test_forge_lifecycle_manager` : vraies arborescences `QProcess` `cmd.exe` → `python`, vrai `taskkill /PID /T /F`, inspection d'identité PowerShell/CIM, un leurre `Popen`). Pas d'autorisation ; les réserves Forge F1 à F5 restent ouvertes. **Le périmètre canonique est donc incomplet** et la suite complète partitionnée n'est pas validée, quel que soit l'état des 65 autres lots.

## 11. Observations non attribuées (consignées, aucune cause affirmée)

- **L26** (tentative 2) : un `Traceback` imprimé (`TypeError`, `QLabel.setText` appelé avec un `MagicMock`), test rapporté `ok` — correspond à la description de l'observation de Mission 175 ; **L29** : trois `DeprecationWarning` (`QMessageBox.setButtonText` avec des entiers), même correspondance de description. Aucune comparaison n'a établi l'identité de ces observations avec les réserves citées.
- Messages de journal **attendus** de tests d'erreur provoquée (échecs de copie ou d'écriture simulés, accès refusé simulé) dans plusieurs lots, chemins dans le répertoire temporaire privé ; lignes de nettoyage de fixtures. Aucun `taskkill`, aucun message Qt de plateforme, aucun code `0xC0000374` ni `0xC0000409` dans les 67 exécutions.
- **Recensement de processus** : les « 59 nouveaux venus » de la tentative 2 sont **59 observations d'un seul processus** (même PID et même date de création, absent de la ligne de base, d'identité non établie), pas 59 processus ; il a été vu vivant pendant la séquence et n'était plus en cours au contrôle final (deux instants distincts). Des processus **présents avant un lot et absents après** (hors membres du job) sont comptés à titre informatif — 168 cumulés en tentative 2, 9 en tentative 3 : ce sont des **disparitions observées, de cause non établie** ; le recensement seul ne permet pas de les qualifier de sorties naturelles. Aucune enquête supplémentaire.

## 12. Rapprochement des identifiants

Pour **chaque** exécution (67 au total : 4 + 62 + 1), l'ensemble des identifiants exécutés a été recalculé à partir de l'enregistrement et comparé aux identifiants attendus du manifeste de la tentative, puis au journal : **chaque identifiant attendu exactement une fois, aucun manquant, aucun inattendu, aucun doublon dans une exécution, accord avec le journal dans les 67 cas** (hash de l'ordre exécuté égal au hash attendu quand l'ordre est celui de la découverte ; I1 : même ensemble, ordre alphabétique d'exécution contre ordre de définition de la liste attendue, sans conséquence). Les 3 627 identifiants canoniques sont deux à deux distincts. **Les répétitions entre tentatives sont distinguées des doublons dans une exécution** : les seuls identifiants présents dans des exécutions de deux tentatives sont les 157 de L66 (répétition légitime d'un lot rejoué sur un autre état du code), comptés une fois dans la couverture consolidée avec leurs deux exécutions conservées ; il n'y a **aucun doublon à l'intérieur d'une exécution**. Ce rapprochement ne se limite pas à la présence d'un résultat récent.

## 13. Ce que la campagne ne démontre pas — réserves ouvertes

Suite complète partitionnée **non validée** (L18 non exécuté, 141 tests ; périmètre canonique incomplet) ; équivalence avec une exécution monoprocessus **non démontrée** ; plantage `0xC0000374` de Mission 177 **non résolu**, non reproduit ni expliqué ; réserves Forge F1 à F5 ouvertes ; reproductibilité non établie (une exécution par lot et par état) ; validation retenue répartie sur **trois manifestes et deux états du code** ; trois lots et I1 en `OK_NON_NET` pour inventaire incomplet (processus non identifiés dont l'identité reste inconnue) ; L04 retenu par réévaluation de critère et non par exécution `NET` ; le contrôle des processus se limite aux arbres testés (le Job Object ne couvre ni le pilote ni le superviseur) ; les minuteries imbriquées ne tuent que le processus enfant direct ; le plafond de processus de chaque lot est un seuil d'arrêt prudent, pas une preuve ; recensement de processus limité aux identités lisibles ; Python 3.11.9 et Windows 10 seulement ; Qt hors écran ; réserves historiques des Missions 173 à 180 ouvertes ; les anomalies de la section 11 non attribuées.

## 14. Preuves hors dépôt et outillage

Les pièces, journaux, verdicts, enregistrements, sorties, réévaluation et bilans sont conservés **hors dépôt** (jamais versionnés ; aucun script de vérification temporaire n'est dans le dépôt). Empreintes principales : tentative 1 — pilote de séquence `855ea067…`, pièces `5bdbdd13…`, manifeste `2b394f28…` ; tentative 2 — pilote de séquence `c4be345b8095b92a7276e0b94b9349c20295f794143d814db28e90b0ea5c2198`, pièces `c48dce5cee08eab6…`, manifeste `07282a6c21552c32…` ; tentative 3 — pilote de séquence `67b9274b46095ba749e3aac757e4c915ee15da54b21082b90d42c924ffaad1cd`, pièces `9163bb851543e519c41ec275ec220cbba2e1599a3af925a4f3daf84ce49f5b90`, manifeste `c14aa8cf29e198650a37095648626468077871cd1356599049983381ad3522da`, test corrigé `d19092b307ae044ad7aa69a64582c564ae2d405e01cd4ce9219bf8246f135b28` (blob `bebfaac6bfab90ab73922fa483d18e207d5903e8`) ; version précédente du test `ef38dbab6e74261492e22117611eb716946207a3f66f447ecb68cc74317ff7e6` (blob `3567ad232bad1ffb40ceee0c905582982fbb7a62`). Bilan consolidé v3 (lecture seule, trois axes distincts, rapprochement exact par exécution, couverture consolidée à identifiant compté une fois) ; versions précédentes du bilan conservées. Le drapeau de réconciliation de la version 2 de l'outil de bilan a été corrigé en cours de campagne (il testait à tort une exécution unique par lot, sans effet sur les chiffres de couverture) ; le diff de cette correction est **reconstitué** à partir du script final, la version antérieure exacte n'ayant pas été conservée : ce n'est pas un diff vérifié entre deux originaux archivés. La vérification du bilan actuel sur les preuves existantes (rapprochement exact de chaque exécution, répétitions entre tentatives distinguées des doublons internes) est distincte et repose sur les enregistrements des exécutions.

## 15. Fichiers du périmètre et statut

Périmètre du dépôt, destiné à un unique commit local autorisé avec réserves (publication non autorisée) : `tests/integration/test_workspace_roundtrip.py` (correction ciblée, section 7), ce document, `CHANGELOG.md` et `docs/PROJECT_CONTEXT.md`. **Production, autres tests, `CLAUDE.md`, Blueprint, `graphify-out/` et documents des autres missions : inchangés.** Aucun test n'a été lancé pour cette consolidation documentaire ; les seuls lancements de la mission sont les trois tentatives ci-dessus.

Statut courant : **campagne partitionnée examinée avec réserves ; périmètre canonique incomplet, L18 non exécuté ; suite complète partitionnée non validée ; correction du test L66 validée de façon ciblée ; revue pré-commit acceptée ; commit local autorisé avec réserves ; publication non autorisée ; mission non close.** *(Énoncé antérieur, daté du 2026-10-19, conservé et dépassé : « revue pré-commit en préparation ; commit non autorisé ; mission non close ».)* Ni tag ni Release ne sont décidés ; push, tag et Release restent à autoriser séparément. Aucun SHA de commit ne figure ici : Git fait autorité (voir « Principe de non-auto-référence » dans `docs/PROJECT_CONTEXT.md`).
