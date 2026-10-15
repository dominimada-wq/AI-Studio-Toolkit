# Mission 178 — Refuse Unusable Storage Files Explicitly at Load Time

> **STATUT (2026-10-15) : validation ciblée examinée avec réserves ; suite complète non validée ; revue pré-commit acceptée ; commit local autorisé avec réserves ; publication non autorisée ; mission non close.** *(Statut antérieur, daté du 2026-10-15, avant l'acceptation de la revue pré-commit v2, conservé et dépassé : « validation ciblée examinée avec réserves ; suite complète non validée ; revue pré-commit en préparation ; commit non autorisé ; mission non close ».)* L'implémentation limitée (section 3) et les 38 tests (section 5) ont été examinés par **cinq lancements distincts (A à D)**, une exécution chacun, décrits séparément en section 10 : A, comparatif contre la copie exacte de la base (prévision confirmée), puis **quatre lancements sur la production corrigée** : B (38 méthodes et 56 sous-tests réussis), C1 (165 réussis), C2 (15 réussis) et D (157 réussis, `OK_NON_NET` pour inventaire incomplet seul). **Aucune suite complète n'a été lancée ni validée** ; la dérogation ponctuelle P1 (section 6) est limitée à Mission 178 ; le plantage `0xC0000374` de Mission 177 n'est pas résolu (K0 non rouvert) et les réserves Forge restent ouvertes (K1). Les trois fichiers de production sont **inchangés depuis les lancements** (empreintes avant et après épinglées, section 12) ; le fichier de tests ne diffère de la version exécutée que par une **correction rédactionnelle de sa docstring de module, postérieure aux exécutions et acceptée sans nouvelle exécution** (il n'est pas identique octet pour octet à la version exécutée, section 12) ; les changements documentaires de `MISSION_178.md`, de `CHANGELOG.md` et de `docs/PROJECT_CONTEXT.md` sont **postérieurs aux tests**. Base : `HEAD` `0ee3ba349db83bd18a43196ea98b46cf6f658f6a` (commit documentaire de Mission 177, poussé). Un commit local unique a été autorisé par l'architecte avec réserves (section 13) ; **il n'est pas annoncé ici comme créé et aucun identifiant n'est anticipé**.

## 1. Problème

Trois fichiers JSON sont lus par trois stockages : `project.json` (`WorkspaceStorage`), `application_settings.json` (`ApplicationSettingsStorage`) et `lora_library.json` (`LoRALibraryStorage`). Pour les catégories couvertes par cette mission (JSON invalide, racine non objet, octets non UTF-8, `OSError` levée à la lecture ou par `exists()`), un fichier présent mais inutilisable doit sortir de `load()` sous la forme de l'erreur dédiée du stockage (jamais une exception brute de ces catégories, jamais `None`, qui ne signifie que « le fichier n'existe pas »), et `load()` ne doit rien écrire, réparer, migrer, sauvegarder ni remplacer.

État avant la mission, établi par lecture (rapport d'impact, hors dépôt) :

| Cas | Workspace | Réglages | Registre LoRA |
|---|---|---|---|
| Racine non objet | valeur renvoyée sans contrôle ; `null` renvoyé comme `None` (confondu avec « absent ») | erreur dédiée (Mission 144) | erreur dédiée (Mission 144) |
| Octets non UTF-8 | `UnicodeDecodeError` brute | brute | brute |
| `Path.exists()` qui lève une `OSError` non masquée par `pathlib` | brute (appel hors du `try`) | brute | brute |

Conséquences **déduites** (non observées) : à l'ouverture d'un projet, une racine non objet ou un fichier non décodable ne produit aucun dialogue (exception dans un slot Qt) ; au démarrage, un fichier machine-local non décodable sort de `main()` en exception brute au lieu du message fatal prévu pour les deux erreurs dédiées. La fréquence de ces situations n'est pas mesurée (fichier édité hors application).

## 2. Décisions de l'architecte (rapport d'impact validé)

- **D1 — BOM : B3.** Le refus actuel du BOM et son erreur JSON sont conservés (le module `json` refuse un U+FEFF en tête par une `JSONDecodeError`, vérifié par lecture de la stdlib 3.11.9). Aucun mécanisme spécifique. Tolérer un BOM serait un élargissement de compatibilité, pas qualifié automatiquement de « réparation » ; aucun besoin établi ne le justifie ici. La politique n'est pas déduite des sidecars OneTrainer.
- **D2 — (a)** : seule la racine est contrôlée. **Le typage des collections, y compris imbriquées, reste hors périmètre ; le risque résiduel est explicite (section 7).**
- **D3** : `exists()` placé dans la frontière `try` des trois stockages, pour convertir les `OSError` effectivement propagées.
- **D4 — U1** : interface inchangée ; aucun changement de `main_window.py`. La conversion en exceptions dédiées emprunte les chemins de signalement existants.
- Exceptions existantes réutilisées, cause chaînée pour le décodage et l'accès. `RecursionError` et le `ValueError` du plafond de chiffres des entiers de `json` restent **hors de la liste fermée** ; aucun `except` large.
- **Politique de validation P1, pour Mission 178 seulement, avec dérogation ponctuelle à l'exigence de suite complète avant et après commit** (section 6). Cette dérogation n'est pas permanente, ne modifie pas `CLAUDE.md`, ne valide pas la suite et n'autorise, seule, aucun lancement ni aucun commit.

## 3. Contrat et périmètre de production (trois fichiers)

`WorkspaceStorage.load()` :
- absent → `None` (inchangé) ;
- JSON invalide (BOM compris) → `WorkspaceStorageError` « … is not valid JSON », cause `JSONDecodeError` (inchangé) ;
- **octets non UTF-8 → `WorkspaceStorageError` « … is not valid UTF-8 text », cause `UnicodeDecodeError`, une ligne `logger.error` (nouveau)** ;
- `OSError` à la lecture **ou levée par `exists()`** → `WorkspaceStorageError` « Could not read … », cause chaînée (la lecture : inchangé ; `exists()` : nouveau) ;
- **racine JSON qui n'est pas un objet (liste, chaîne, nombre, booléen, `null`) → `WorkspaceStorageError` « … does not contain a JSON object », une ligne `logger.error` (nouveau)** ; l'objet vide `{}` reste valide.

`ApplicationSettingsStorage.load()` et `LoRALibraryStorage.load()` : mêmes ajouts pour le décodage et `exists()` ; leurs contrôles de racine (et de `"loras"`) sont ceux de la Mission 144, inchangés. Les docstrings des trois erreurs sont complétées (texte non UTF-8 ; pour le projet, aussi la racine).

Non modifiés : `save()`, managers, Domain, `main.py`, interface (`main_window.py`), moteurs, dépendances, prérequis Python, `CLAUDE.md`, `graphify-out/`. Aucune écriture, réparation, migration, copie de sauvegarde ni remplacement du fichier invalide au chargement.

## 4. Limites

- Hors périmètre et non couverts par un test : `RecursionError` (JSON très profond), les autres `ValueError` (par exemple le plafond de chiffres d'un entier de `json`), les structures internes mal typées (voir la section 7), fichier modifié pendant la lecture. L'affirmation « jamais une exception brute » ne vaut que pour les catégories couvertes ci-dessus.
- Le double de `PermissionError` (levée par `open()` ou par `Path.exists()`) montre la conversion, **pas** qu'un refus d'accès réel produit cette exception ; aucun refus réel (ACL) n'est testé.
- Python 3.11.9 / Windows 10 seulement ; aucune exécution sous Python 3.10.
- Le message affiché à l'ouverture d'un projet reste le texte technique du stockage, en anglais, avec le chemin brut (U1) ; le cas « fichier absent » garde son message de barre d'état.
- Aucun effet dans l'application fenêtrée n'est observé : les chemins de signalement sont ceux de Mission 144 (démarrage) et de `open_project()` (`QMessageBox.critical` pour `WorkspaceManagerError`), non rejoués dans cette mission.

## 5. Tests (écrits avant les lancements, exécutés en section 10)

Nouveau fichier `tests/integration/test_storage_read_boundary.py` : **38 tests** (comptage statique par arbre syntaxique ; total à confirmer seulement par une découverte ultérieure autorisée). Fichiers temporaires réels, sans Qt, sans réseau, sans processus ; chaque cas d'échec vérifie l'erreur dédiée, une seule ligne d'erreur journalisée, le message, la cause chaînée, **l'identité octet pour octet du dossier** (mêmes fichiers, mêmes empreintes, rien de créé).

**Ce que chaque famille de tests vérifie (à ne pas généraliser)** : les tests d'échec des **stockages** (classes `*Storage*Test`, `*RootInvariantsTest`) vérifient l'erreur dédiée, **une seule ligne d'erreur journalisée, le message, la cause chaînée** et l'intégrité du dossier ; les tests des **managers** (`WorkspaceManagerOpenFailureTest`, `MachineLocalManagerUndecodableFileTest`) vérifient surtout **le type de l'exception, l'état** (projet précédent conservé, aucun événement publié) **et les fichiers** : ils ne vérifient ni le journal, ni le message, ni la cause. Les tests de succès (absent, valide, `{}`) ne vérifient pas le journal.

Classification (le nom de la classe indique la catégorie pour les classes de **stockage** ; **les classes de managers ne suivent pas toutes cette convention** : `WorkspaceManagerOpenFailureTest` mêle invariants et nouveau contrat, `MachineLocalManagerUndecodableFileTest` ne contient que du nouveau contrat) :

| Classe | Tests | Nature |
|---|---|---|
| `WorkspaceStorageInvariantsTest`, `ApplicationSettingsStorageInvariantsTest`, `LoRALibraryStorageInvariantsTest` | 7 + 7 + 7 | **Invariants** : absent, dossier absent non créé, UTF-8 valide avec accents, objet vide, JSON invalide, BOM suivi d'un objet valide **toujours refusé** (erreur JSON), `OSError` à la lecture (double) |
| `ApplicationSettingsRootInvariantsTest`, `LoRALibraryRootInvariantsTest` | 1 + 1 | **Invariants hérités de la Mission 144** : six racines non objets des stockages machine-locaux |
| `WorkspaceManagerOpenFailureTest` | 4 sur 6 | **Invariants** : fichier absent → `None`, JSON invalide → `WorkspaceManagerError`, échec sans projet ouvert, ouverture réussie qui publie toujours `WORKSPACE_OPENED` |
| `WorkspaceStorageNewContractTest` (+ deux classes sœurs) | 3 + 2 + 2 | **Nouveau contrat** : racine non objet du projet (sept cas dont `null` et `false`), octets non conformes à UTF-8 (cinq cas), `exists()` qui lève (double) |
| `WorkspaceManagerOpenFailureTest` | 2 sur 6 | **Nouveau contrat** : `WorkspaceManagerError` pour racines non objets et octets non UTF-8, projet précédemment ouvert conservé, aucun `WORKSPACE_OPENED`, fichier inchangé |
| `MachineLocalManagerUndecodableFileTest` | 2 | **Nouveau contrat** : les deux managers refusent à la construction un fichier non décodable, sans rien écrire |

Soit **27 invariants** et **11 tests du nouveau contrat** (38). Les cinq octets non UTF-8 : signature UTF-16 LE seule `b"\xff\xfe"` et objet encodé en UTF-16 LE (cas décrits comme **non conformes à l'encodage UTF-8 attendu**, et non comme une « absence de BOM valide »), octet de continuation invalide, lettre accentuée Latin-1, séquence multi-octets tronquée.

### Résultat prévu avant tout lancement, cas par cas, sur la production **avant** (copie exacte de la base) — confirmé par le lancement A

Prévision écrite avant tout lancement, **confirmée à l'identique par le lancement A (section 10)**. Une exception brute produit une **erreur** `unittest`, pas un échec d'assertion.

| Cas | Avant | Après |
|---|---|---|
| 27 invariants | réussissent | réussissent |
| Octets non UTF-8, trois stockages (3 tests × 5 sous-cas) | 15 **erreurs** (`UnicodeDecodeError` brute) | réussissent |
| `exists()` qui lève, trois stockages (3 tests) | 3 **erreurs** (`PermissionError` brute) | réussissent |
| Racines non objets du projet, stockage (1 test × 7 sous-cas, `null` compris) | 7 **échecs** (« not raised ») | réussissent |
| Racines non objets, `open()` du manager (1 test × 7 sous-cas) | 6 **erreurs** (`AttributeError` sur `get`) + 1 **échec** (`null` : `open()` renvoie `None`) | réussissent |
| Octets non UTF-8, `open()` du manager (1 test × 5 sous-cas) | 5 **erreurs** | réussissent |
| Octets non UTF-8, deux managers machine-locaux (2 tests × 5 sous-cas) | 10 **erreurs** | réussissent |

Bilan prévu (et observé en A) sur la base : `Ran 38 tests`, 27 réussis, 11 tests non réussis (10 en erreur, 1 en échec seul), soit au niveau des sous-cas **39 erreurs et 8 échecs**. Bilan sur l'état final : 38 réussis, observé en B. **Ces chiffres étaient une prévision ; les lancements A et B les ont observés exactement (section 10).**

Limites de la comparaison avant/après : elle porte sur ce fichier seul, par doubles pour deux familles de cas, sur une copie hors dépôt de `src/` identique octet pour octet à la base (95 fichiers, manifeste hors dépôt) ; elle ne prouve rien sur l'interface ; les 27 invariants ne prouvent la stabilité que des cas écrits.

## 6. Politique de validation P1 (Mission 178 seulement)

Lot **minimal** retenu par l'architecte, fondé sur l'analyse statique des imports et des appels (analyse statique préalable aux lancements ; le chargement ciblé des tests a eu lieu pendant les lancements A à D ; aucune découverte globale n'a été réalisée dans Mission 178) ; chaque lancement a été autorisé et exécuté une seule fois (section 10) :

| # | Module | Tests | Qt importé | Widgets créés | Socket | Processus | Modules Forge importés | Raison |
|---|---|---|---|---|---|---|---|---|
| 1 | `test_storage_read_boundary` (nouveau) | 38 | non | non | non | non | non | nouveau contrat |
| 2 | `test_lora_library_roundtrip` | 165 | non | non | non | non | non | registre et réglages réels, régression de `LoRALibraryStorage.load` |
| 3 | `test_image_roundtrip` | 15 | non | non | non | non | non | `WorkspaceManager.open()` sur fichiers valides, sans Qt |
| 4 | `test_workspace_roundtrip` | 157 | oui | oui (`DashboardPage`, `ImagesPage`) | non | non | non | module principal de `WorkspaceStorage`/`WorkspaceManager` ; Qt hors écran |

**Non retenu** (décision de l'architecte, le nouveau module couvrant directement le stockage et son manager) : `test_application_settings_roundtrip` limité à ses méthodes de stockage (`test_storage_load_compatibility_matrix`, `test_storage_load_malformed_json_preserves_original_cause`, `test_storage_load_failure_never_modifies_the_corrupt_file`, `test_storage_round_trip_with_unicode_paths`). Le module importe Qt, crée un `QApplication` à l'import, importe cinq modules Forge et contient des tests de `SettingsPage` qui appellent une inspection d'installation Forge sur le système de fichiers (sans processus ni socket) ; la sélection de méthodes n'empêche pas l'import de ces modules.

**Exclus et pourquoi** : `test_main_startup` (4 tests, `MainWindow` remplacé par un double ; n'exerce ni le code modifié ni `main.py` modifié) ; tout module construisant un vrai `MainWindow` (`test_main_window_new_project`, `test_main_toolbar`, `test_dashboard_page`, `test_dataset_roundtrip`, etc.) : l'interface n'est pas modifiée (U1), ils importent les modules Forge et n'exercent pas le code modifié de façon distincte (aucun lien n'est établi avec le plantage inexpliqué ; ce n'est pas le motif de l'exclusion) ; modules de pages redondants avec le n° 4 (`test_character_roundtrip`, `test_model_roundtrip`, …). **Exclure les modules dont le nom contient Forge ne garantit pas l'absence d'activité Forge dans les autres** : à la construction, `ForgeLifecycleManager` est à l'état arrêté sans processus ni fil (lecture de `__init__`) ; l'analyse statique ne détecte ni socket ni processus dans les quatre modules retenus, ce qui n'est pas une preuve d'absence d'activité à l'exécution.

Lancements autorisés et exécutés **une seule fois chacun**, dans l'ordre A, B, C1, C2, D, sans parallélisme ni relance automatique : (A) les 38 tests du nouveau module contre la copie exacte de la production de base ; (B) les mêmes 38 tests, **le même fichier** (même sha256 `32c2dc33…`), contre la production corrigée ; (C) `test_lora_library_roundtrip` (165) et `test_image_roundtrip` (15), chacun dans un processus distinct ; (D) `test_workspace_roundtrip` (157), interpréteur du venv, Qt hors écran, environnement privé, sous le superviseur existant. Les pièces de lancement (lanceurs, enfant, validateur, bornes, critères de poursuite) sont hors dépôt ; leurs empreintes sont consignées dans la note de reprise et le dossier de revue. Aucune suite complète, aucun processus Forge, aucune investigation du plantage, aucune relance. **Dérogation ponctuelle P1 : pour Mission 178 seulement, l'architecte a accepté de ne pas exiger la suite complète avant et après commit ; elle n'est pas permanente, ne modifie pas `CLAUDE.md`, ne valide pas la suite complète et ne vaut pas, seule, autorisation de commit.**

## 7. Risque résiduel explicite (D2)

La racine est contrôlée, **pas le typage des collections** : `images`, `models`, `workflows` et `characters` (et, imbriquées, `datasets`, `loras`, `prompts`, `trainings` de chaque personnage) sont lues par `Workspace.from_dict` et `Character.from_dict` sans contrôle de leur type. Par lecture : une valeur entière provoque un `TypeError` pendant la lecture ; une chaîne ou un objet non vide est parcouru sans erreur (caractères ou clés) et les éléments non objets sont filtrés, ce qui donne **une collection vide silencieuse** ; un `save()` ultérieur réécrirait alors le projet sans ces données. Déclencheur : édition manuelle d'un type précis ; non mesuré, non rejoué. Le filtrage des entrées mal typées des listes est un contrat existant (compatibilité défensive) qui n'est pas modifié.

## 8. Différences avec les contrats existants (toutes validées par l'architecte)

1. `WorkspaceStorage.load()` lève sur une racine non objet ou `null` (avant : valeur renvoyée / `None`).
2. Les trois stockages convertissent un texte non UTF-8 en erreur dédiée (avant : exception brute).
3. Les trois stockages convertissent en erreur dédiée une `OSError` levée par `exists()` (avant : brute).
4. Nouveaux textes d'erreur ; textes existants inchangés.

## 9. Fichiers du périmètre (sept)

1. `src/infrastructure/storage/workspace_storage.py` — production.
2. `src/infrastructure/storage/application_settings_storage.py` — production.
3. `src/infrastructure/storage/lora_library_storage.py` — production.
4. `tests/integration/test_storage_read_boundary.py` — nouveau.
5. `docs/missions/MISSION_178.md` — cette archive (nouveau).
6. `CHANGELOG.md` — documentation (nouvelle entrée de Mission 178, en cours).
7. `docs/PROJECT_CONTEXT.md` — documentation (état courant, prochaine mission) ; fins de ligne CRLF conservées dans l'arbre de travail, LF dans les blobs.

Un seul commit est envisagé pour cet objectif cohérent, sous le message « Normalize storage read errors and reject non-object workspaces » ; sa création locale a été autorisée par l'architecte avec réserves (section 13) ; elle n'est pas annoncée ici comme faite. Aucun identifiant de commit n'est anticipé ici. `CLAUDE.md`, le Blueprint, `main_window.py`, les managers, le Domain, `main.py` et `graphify-out/` ne sont pas modifiés.

## 10. Résultats observés (validation ciblée du 2026-10-15)

Un lancement par résultat, jamais de relance. Avant chaque lancement : empreintes des pièces et des fichiers épinglés, `HEAD`, index, stash, statut (cinq entrées M178 et huit entrées `graphify-out/`) vérifiés sans écart. Les nombres de **méthodes**, de **sous-tests** et les **compteurs `unittest`** (qui comptent les sous-tests défaillants un par un) sont distincts. Les modules applicatifs `src`/`tests` chargés ont été vérifiés comme provenant de la seule racine de chaque lancement.

### A — les 38 tests contre la copie exacte de la production de base : prévision confirmée
Racine : copie hors dépôt de `src/` (95 fichiers, manifeste inchangé), même fichier de tests que B. Code de l'enfant 1 (planifié), lanceur 0. **38 méthodes : 27 réussies, 10 en erreur, 1 en échec ; 56 sous-tests : 12 réussis, 36 en erreur, 8 en échec ; compteurs `unittest` : 39 erreurs et 8 échecs.** Traces lues en entier : 30 `UnicodeDecodeError`, 6 `AttributeError`, 3 `PermissionError`, 8 `AssertionError`, conformes cas par cas à la prévision de la section 5 (méthodes et sous-tests, un à un). Ces erreurs et échecs attendus ne sont pas des incidents du harnais. Verdict `PREVISION_CONFIRMEE`. Ce comparatif confirme les comportements couverts par le nouveau contrat et la conservation des 27 invariants écrits ; il ne dit rien des cas non écrits.

### B — les mêmes 38 tests contre la production corrigée
**38 méthodes réussies, 56 sous-tests réussis** (56 événements, 56 identifiants distincts, tous réussis, égaux aux identifiants attendus), 0 échec, 0 erreur, 0 ignoré, 0 échec attendu, 0 succès inattendu. Enfant 0. Verdict `CONFORME`.

### C1 — `test_lora_library_roundtrip` : 165 tests réussis
165 méthodes réussies (29 sous-tests réussis), 0 échec, erreur ou ignoré ; enfant 0 ; verdict `CONFORME`. `stderr` : lignes de journal d'erreurs volontairement provoquées par des tests existants, sans trace d'exception.

### C2 — `test_image_roundtrip` : 15 tests réussis
15 méthodes réussies, 0 échec, erreur ou ignoré ; enfant 0 ; verdict `CONFORME` ; `stderr` vide.

### D — `test_workspace_roundtrip` : 157 tests réussis, `OK_NON_NET`
157 tests réussis (`Ran 157 tests`, `OK` final), 0 échec, erreur, ignoré, échec attendu ou succès inattendu ; **code naturel 0 du processus testé observé avant toute intervention** ; **aucune intervention** ; **job vide confirmé** (5 processus comptés par le job, 0 actif à la fin ; compteur `TotalTerminatedProcesses` = 0) ; fermetures de handles réussies ; observation indépendante : les trois membres identifiés sont sortis avec le code 0 ; niveaux réseau tous à zéro (politique `none`) ; 38 modules `src`/`tests` chargés depuis le dépôt, PySide6 et shiboken6 6.11.1 du venv, Qt hors écran. **Superviseur : code 20 ; supervision incomplète pour inventaire seul (5 comptés, 3 identifiés, « 2 process(es) … never identified »)** ; les trois seules conditions fausses sont celles de propreté de supervision. Niveau `OK_NON_NET` : validation partielle recevable, **jamais convertie en résultat net**, ni en échec. Un code 20 n'est pas pris isolément : toutes les autres conditions ont été vérifiées une à une.

### Total et limites
**375 tests réussis (38 + 165 + 15 + 157)** en **quatre lancements ciblés distincts sur la production corrigée** (B, C1, C2, D). A n'y est pas ajouté (son rôle est le comparatif sur la base). Ce total n'est **pas une suite complète** : les **3 574 tests** (3 536 + 38) restent un **attendu statique** (comptage par arbre syntaxique, identique à la découverte de Mission 177 pour les 63 modules existants), sans découverte ni exécution globale dans Mission 178. Limites conservées : un lancement par résultat, **reproductibilité non établie** ; Python 3.11.9 et Windows 10 seulement, aucune exécution sous 3.10 ; le double de `PermissionError` (par `open()` et par `Path.exists()`) ne démontre pas un refus d'accès réel ; les compteurs réseau couvrent les points instrumentés, sans preuve générale sur du code natif ni sur le réseau natif de Qt ; la vérification de provenance concerne les modules applicatifs `src`/`tests`, pas tous les modules Python ; le nombre inchangé de dossiers `__pycache__` de `src/` et `tests/` (16 avant et après chaque lancement) ne prouve pas l'identité de leur contenu ; le validateur écrit `verdict.json` hors dépôt (opération non strictement en lecture seule) ; les tests de stockage vérifient journal, message et cause, ceux des managers surtout l'exception, l'état et les fichiers ; aucun effet n'a été observé dans l'application fenêtrée.

## 11. Statut, dérogation et réserves

Statut courant : **validation ciblée examinée avec réserves ; suite complète non validée ; revue pré-commit acceptée ; commit local autorisé avec réserves ; publication non autorisée ; mission non close.** Dérogation P1 limitée à Mission 178 (section 6). Réserves ouvertes, non résolues par Mission 178 : **reproductibilité non établie** ; limites des doubles et de l'observation réseau ; **structures internes mal typées de `project.json` hors périmètre** (section 7, risque résiduel D2) ; `RecursionError`, autres `ValueError` et fichier modifié pendant la lecture hors périmètre ; **suite complète non validée et plantage `0xC0000374` de Mission 177 non résolu** (K0 non rouvert) ; **réserves Forge ouvertes** (K1) ; réserves historiques des Missions 173 à 177 ; supervision incomplète dans les exécutions supervisées ; absence d'exécution sous Python 3.10.

## 12. Provenance et changements documentaires postérieurs aux tests

- **Provenance : trois notions à ne pas confondre.** (1) **Empreintes avant et après** : chaque lanceur a épinglé, puis comparé avant et après le lancement, le sha256 des fichiers contrôlés (production, fichier de tests, pièces, et fermeture applicative statique). Elles établissent la **stabilité** de ces fichiers pendant les lancements ; **elles ne prouvent ni un import ni une couverture**. Production : `workspace_storage.py` `79cf53b9…`, `application_settings_storage.py` `579e902c…`, `lora_library_storage.py` `31038770…`, inchangés ; fichier de tests de la version exécutée : `32c2dc33…`. (2) **Modules effectivement chargés** : leur provenance est consignée dans les résultats propres à chaque lancement (`results.json` de A, B, C1, C2 ; verdict de D) : A, 28 modules `src`/`tests` tous sous la copie de base ; B, 28 sous le dépôt ; C1, 14 ; C2, 25 ; D, 38 sous le dépôt. (3) **Tests effectivement exécutés** : le nouveau fichier en A (contre la production de base) et en B (contre la production corrigée) ; `test_lora_library_roundtrip` en C1, `test_image_roundtrip` en C2 et `test_workspace_roundtrip` en D, qui sont des modules voisins et n'exécutent pas le nouveau fichier.
- **Version actuelle du fichier de tests** : correction rédactionnelle de la docstring de module, **postérieure aux exécutions** (elle précise que les noms de classes distinguent les catégories pour les stockages mais pas pour toutes les classes de managers). Empreinte de la version exécutée `32c2dc33…`, empreinte actuelle `80427dbe…` : **le fichier actuel n'est pas identique octet pour octet à la version exécutée** ; l'arbre syntaxique est identique en excluant uniquement la docstring de module (vérifié sans importer ni exécuter) ; cette différence limitée est acceptée sans nouvelle exécution. Les épingles des lanceurs préparés ne correspondent donc plus au fichier actuel : ils ne sont ni régénérés ni relancés.
- **Postérieurs aux tests** : ce document (épinglé à `c41eca72…` pendant les lancements, sans effet sur eux : le lanceur ne l'exécute pas), `CHANGELOG.md` et `docs/PROJECT_CONTEXT.md`. Ils ne contiennent aucun code exécuté.
- **Pièces hors dépôt** (scratchpad de session, non versionnées ; empreintes tronquées) : lancement A `A_20261015_143853` (verdict `e44b4a0d08542ecc…`, résultats `ae11ab267596b1ce…`, sortie unittest `cab9c2125ec39ec2…`) ; B `B_20261015_144007` (`036c19e2722165b8…`, `081972a29f48b36c…`, `ec2f0335926d66a6…`) ; C1 `C1_20261015_144109` (`74b6c90d369db14e…`, `0077c05ec761c85a…`, `110061ff69b82ce0…`) ; C2 `C2_20261015_144152` (`62f077d2463fdf13…`, `db00786368a0709f…`, `5b4856f3b61a93cc…`) ; D `workspace_roundtrip_20261015_144309` (`verdict.json` `d7a9c44ac0d9a765…`, `supervised/supervision.json` `db8291b3bb85c611…`, `supervised/process_info.json` `02aa3fa9ef1d7349…`). Superviseur `job_supervisor_v2.py` `dbb13d19…`, enveloppe `run_qt_batch_with_info_v2.py` `4b7ec044…` (inchangés depuis Mission 177).

## 13. Décision de commit (2026-10-15)

L'architecte a **accepté la revue pré-commit v2** (sha256 `0612c9c6ee44603889d0423381ebb7d754f09c708374a9ea4f9824dc55fefd3e`) et **autorisé un unique commit local** de Mission 178, sous le message « Normalize storage read errors and reject non-object workspaces » (avec la ligne d'attribution `Co-Authored-By: Claude Sonnet 5.5`). Cette décision accepte les validations ciblées de la section 10 et leurs limites ; **elle ne valide pas la suite complète**. La dérogation ponctuelle P1 reste **limitée à Mission 178, avant et après ce commit** ; aucun test, aucune collecte ni aucune sonde n'est lancé après lui. La correction rédactionnelle de la docstring du test (section 12) est acceptée sans nouvelle exécution. Procédure autorisée : contrôles frais ; actualisation, avant l'indexation, des seuls statuts courants des trois documents (versions précédentes et diff exact conservés hors dépôt) ; indexation explicite des sept chemins du périmètre (section 9), sans `git add` global, sans `-a`, sans amend ; vérification du périmètre de l'index, de `git diff --cached --check` et des blobs (code et tests conformes à la revue v2 ; documents conformes aux versions revues plus le seul diff d'actualisation, avec la normalisation CRLF → LF de `docs/PROJECT_CONTEXT.md`). **Statut courant : validation ciblée examinée avec réserves ; suite complète non validée ; revue pré-commit acceptée ; commit local autorisé avec réserves ; publication non autorisée ; mission non close.** Ce paragraphe n'annonce pas le commit comme créé et n'anticipe aucun identifiant ; Git fait autorité. Push, tag et GitHub Release restent à autoriser séparément.
