# Mission 174 — Surface Raw Protocol Errors in Diagnostic Calls

> **MISSION 174 CLOSE AVEC RÉSERVE NON RÉSOLUE — commit fonctionnel et tag annoté publiés, GitHub Release publiée manuellement (section 11).** La réserve est la sortie anormale `0xC0000409` du lot ciblé de suites existantes (section 6.5) : elle n'est pas résolue, la suite complète réussie ne la lève pas, et cette clôture ne signifie pas que le lot ciblé s'est terminé proprement. *Historique du statut : ce document a d'abord été commité avec le statut « implémentation validée par revue architecte pour commit local — publication en attente ; mission non close » ; il est mis à jour après la publication de la Release.* Sur les appels de diagnostic synchrones (les tests de connexion et les boutons de découverte de `SettingsPage`, `GenerationManager.list_checkpoints/list_samplers/list_schedulers` et, par lui, le bouton « Rafraîchir » d'`InferencePage`), certaines erreurs de protocole sortent **brutes** des moteurs ComfyUI, Forge et Ollama : l'exception quitte le slot Qt, l'utilisateur ne voit aucun statut. Candidat C1 retenu par l'architecte après l'audit post-M173, verrouillé par une conception ciblée et six sondes hors dépôt. Corrigé **côté diagnostic**, par une liste fermée d'exceptions, sans modifier le comportement des moteurs sur lequel reposent la pré-vérification des lifecycle managers et les workers de disponibilité. **Provenance des résultats (section 6) : preuve avant/après sur une copie hors dépôt qui n'est pas `HEAD` pur ; nouveau fichier de tests réussi (61/61, code 0) ; suite complète réussie (3462 tests, code réel 0) ; mais le lot ciblé de suites existantes se termine par une sortie anormale `0xC0000409` après ses assertions, observée aussi sur une copie de `HEAD` sans C1 (section 6.5).**

## 1. Défaut confirmé

- Déclencheur : un clic sur « Tester la connexion » (ComfyUI, Forge), sur « Rafraîchir les checkpoints / les LoRA / les modèles » (`SettingsPage`) ou sur « Rafraîchir » (`InferencePage`), lorsque le moteur ou le serveur répond de façon anormale ou que l'URL saisie est mal formée. La fréquence réelle de ces situations n'est pas mesurée.
- Les moteurs traduisent ce qu'ils connaissent (`URLError`, `OSError`, `HTTPError`, `JSONDecodeError`, `ValueError` d'URL) en `ComfyUIEngineError`, `ForgeEngineError` ou `AIBackendError`, mais laissent passer des erreurs de `http.client` et de forme. Les appelants de diagnostic ne traitent que les erreurs des moteurs (et `GenerationError` pour la page d'inférence) : l'exception sort donc du slot. PySide6 la route vers `sys.excepthook`, le processus continue, aucun statut n'est affiché.
- **Erreurs brutes observées** (sondes hors dépôt, une exécution chacune, Windows 10, CPython 3.11.9) :

| Classe brute | Origine observée | Appels concernés |
|---|---|---|
| `InvalidURL` | URL saisie : port non numérique, espace ou caractère de contrôle dans l'hôte ou dans le chemin ; **ou** redirection du serveur vers un port invalide | les 11 appels de moteur testés |
| `BadStatusLine` | ligne de statut absurde, code non numérique ou inférieur à 100, ligne vide | les 11 |
| `IncompleteRead` | corps tronqué, `chunked` invalide ou tronqué, **corps d'un `HTTPError`** (`error.read()`) | les 11 |
| `LineTooLong` | ligne de statut ou d'en-tête de plus de 64 Ko | les 11 |
| `UnknownProtocol` | `HTTP/2.0` | les 11 |
| `UnicodeDecodeError` | corps non décodable, **brute seulement côté Forge** ; ComfyUI et Ollama la traduisent (avec un message « base URL is invalid » trompeur) | 5 appels Forge |
| `AttributeError` | JSON valide dont la racine n'est pas un objet (`[]`, `"x"`, `1`, `null`, `true`) | 5 appels ComfyUI et `OllamaEngine.list_models` ; Forge lève déjà `ForgeEngineError` |

- Les structures JSON imbriquées incorrectes (28 formes par méthode ComfyUI, ainsi que les listes Forge et Ollama) sont **déjà** traduites par les moteurs : aucune exception brute imbriquée n'a été observée.
- **Distinction entre simulation et essai local.** Tous les essais ont eu lieu contre un serveur lancé par la sonde sur `127.0.0.1` (vraie mécanique `http.client`), sans DNS ni réseau externe (aucune tentative non loopback n'a été bloquée). Seule exception : le cas `http://localhost:99999` utilise un résolveur de remplacement qui substitue `localhost` par `127.0.0.1` (simulation de l'étape de résolution seulement). Aucun mandataire système n'était présent ; l'opener est neutralisé dans le processus de sonde seulement.
- **Hypothèse non reproduite** : `OverflowError` pour un port hors plage. Sur cette plateforme, un port hors plage ne lève rien (`:99999` donne un délai dépassé, `:65536` une `OSError` WinError 10049, compatibles avec une troncature modulo 65536 ; le port de destination n'a pas été observé directement). Le comportement d'autres plateformes n'est pas testé.

## 2. Contrat

- **Frontière côté diagnostic, liste fermée** : `DIAGNOSTIC_PROTOCOL_ERRORS = (InvalidURL, BadStatusLine, IncompleteRead, LineTooLong, UnknownProtocol, UnicodeDecodeError, ComfyUIUnexpectedResponseError)`, dans le nouveau module `src/engines/diagnostic_errors.py` (Infrastructure, sans Qt, sans import de l'UI, des Managers ni du Domain). Jamais `Exception`, `BaseException`, `AttributeError` ni la classe de base `http.client.HTTPException`.
- **Exclusions, qui ne sont pas une interdiction générale** : `HTTPException` nue (observée avec plus de 100 en-têtes), `RecursionError` (JSON imbriqué sur 100 000 niveaux, observé) et `OverflowError` (non reproduite) restent hors de la liste et continuent de se propager par ces appels. Cette exclusion est un choix de périmètre de cette mission ; elle ne se déduit pas d'une règle générale et ne constitue pas la preuve qu'une charge hostile est nécessaire pour les provoquer. `RemoteDisconnected` est une sous-classe de `BadStatusLine`, mais les moteurs la traduisent déjà (c'est une `OSError`) : elle n'atteint jamais un appelant de diagnostic à l'état brut.
- **Messages** :
  - tests de connexion : `ComfyUI : URL invalide ou réponse inattendue du serveur (<détail>).` / `Forge : …` ;
  - découvertes : `Découverte impossible : réponse inattendue du serveur ou URL invalide (<détail>). La saisie manuelle du checkpoint|du LoRA|du modèle reste disponible.` ;
  - `<détail>` est `describe_protocol_error(erreur)` : `TypeName: message`, tronqué à 300 caractères, ne lève jamais pour une exception ordinaire, ne masque jamais `KeyboardInterrupt` ni `SystemExit` (uniquement `except Exception`) ; même corps que les deux copies de `describe_unexpected_exception` des workers.
  - Sur les sites de découverte, `return` immédiat : combos, valeur saisie à la main, signaux et autres libellés sont intacts.
- **`GenerationManager`** : une clause `except DIAGNOSTIC_PROTOCOL_ERRORS` après la clause existante, dans `list_checkpoints`, `list_samplers` et `list_schedulers` : `GenerationError(describe_protocol_error(erreur)) from erreur`.
- **`InferencePage` inchangée** (décision D3) : son message générique de repli est conservé tel quel.
- **Aucune nouvelle journalisation avec trace** (décision D4).
- **Gardes de forme dans les moteurs** (décision D1) : `ComfyUIUnexpectedResponseError(Exception)`, volontairement **distincte** de `ComfyUIEngineError`, levée par `ComfyUIEngine.list_checkpoints()` (donc par `check_connection()`) lorsque la racine JSON n'est pas un objet. `list_loras()` et `_list_ksampler_combo_values()` lisent une racine non objet comme « pas d'info de nœud » et lèvent le `ComfyUIEngineError` existant ; `OllamaEngine.list_models()` lève l'`AIBackendError` existant.
- **Non modifiés** : `ComfyUILifecycleManager`, `ForgeLifecycleManager`, les deux workers de disponibilité, `ForgeEngine`, les trois `_request_json`, les deux `check_connection`, `InferencePage`, `ai_backend.py`.

## 3. Préservation des décisions M170

Les lifecycle managers et les workers classent eux-mêmes les erreurs que les moteurs laissent passer (`comfyui_lifecycle_manager.py` : `except ComfyUIEngineError: pass` puis `except Exception` qui donne `START_FAILED` sans lancement ; `comfyui_readiness_worker.py` : tolérance de `(ComfyUIEngineError, IncompleteRead, BadStatusLine)`, tout le reste donne `failed`). Une traduction en erreur d'engine, côté moteur, ferait basculer le cas de « ne rien lancer » vers « lancer » ; elle a donc été écartée, et la correction reste du côté diagnostic.

| Cas | Pré-vérification | Worker de disponibilité | Avant → après |
|---|---|---|---|
| `URLError`, `RemoteDisconnected`, `TimeoutError` (traduites) | lancement | continue de sonder | inchangé |
| `BadStatusLine`, `IncompleteRead` | `START_FAILED`, aucun lancement | tolérées jusqu'à la fin du budget | inchangé |
| `InvalidURL`, `LineTooLong`, `UnknownProtocol` | `START_FAILED`, aucun lancement | `failed` | inchangé |
| `HTTPException` nue, `CannotSendRequest`, `RuntimeError` | `START_FAILED`, aucun lancement | `failed` | inchangé |
| ComfyUI, racine non objet | `START_FAILED`, aucun lancement | `failed` | blocage et `failed` inchangés ; **seul le nom du type** dans le message ou le détail passe de `AttributeError` à `ComfyUIUnexpectedResponseError` |
| Forge, `UnicodeDecodeError` brute | `START_FAILED`, aucun lancement | `failed` | inchangé |
| Forge, racine non liste (`ForgeEngineError`) | lancement | continue de sonder | inchangé (caractérisation, pas une approbation) |

- **Correction d'une affirmation de conception** : `InvalidURL` n'est pas « inatteignable » dans la pré-vérification. L'URL de pré-vérification est fixe (`127.0.0.1` et un port validé), mais un service qui répond sur ce port peut rediriger vers une URL invalide : `InvalidURL` sort alors brute du moteur. Elle tombe dans `except Exception` (pas de lancement), comportement conservé parce que les moteurs ne sont pas modifiés ; un test le vérifie avec la vraie mécanique `http.client`.
- La nouvelle classe n'hérite pas de `ComfyUIEngineError` : c'est la condition pour que la pré-vérification continue de bloquer le lancement sur une racine non objet. Deux mutants (section 6.4) l'établissent.
- **Nature de la preuve** : lecture du code, tests avec les vrais objets moteur et un transport contrôlé (`urllib.request.urlopen` remplacé ; `QProcess` et thread de disponibilité remplacés pour les lifecycle managers), et six tests de bout en bout (un sans socket, pour un port non numérique, cinq contre un socket réel sur `127.0.0.1`). Aucun moteur réel n'est lancé ni contacté. La preuve ne couvre pas un vrai ComfyUI ou un vrai Forge.

## 4. Correction

- `src/engines/diagnostic_errors.py` (neuf) : la liste fermée et `describe_protocol_error`.
- `src/engines/comfyui_engine.py` : la classe `ComfyUIUnexpectedResponseError` ; garde de racine non objet dans `list_checkpoints()` ; lecture tolérante de la racine dans `list_loras()` et `_list_ksampler_combo_values()`.
- `src/engines/ollama_engine.py` : lecture tolérante de la racine dans `list_models()`.
- `src/managers/generation_manager.py` : une clause par méthode de découverte.
- `src/ui/pages/settings_page.py` : une clause dans chacune des cinq méthodes (tests de connexion ComfyUI et Forge, découverte de checkpoints, de LoRA et de modèles Ollama).

## 5. Tests

`tests/integration/test_diagnostic_protocol_errors.py` (neuf, 61 tests exécutés), regroupés dans un seul fichier pour cette revue ; aucun test existant n'est modifié. Vrais `ComfyUIEngine`, `ForgeEngine` et `OllamaEngine` partout. Les erreurs sont injectées là où elles naissent : dans `urlopen()`, dans `response.read()`, dans `HTTPError.read()` ou dans le corps de la réponse.

- **Contrat et portée** : liste exacte, absence de classes plus larges, nouvelle classe non héritée de `ComfyUIEngineError`, formateur (format, troncature, `str()` défaillant, `KeyboardInterrupt` et `SystemExit` non masqués, sortie identique aux formateurs existants), dépendances du module, modules non modifiés qui ignorent les nouveaux noms.
- **Moteurs inchangés** : les erreurs de la liste sortent brutes des 11 appels ; les erreurs traduites restent traduites ; les formes imbriquées gardent leur type historique ; les réponses valides fonctionnent.
- **Gardes de forme** : racine non objet (ComfyUI, Ollama, y compris un 404 à corps `[]`), racine non liste Forge inchangée.
- **Fronts de diagnostic** : `GenerationManager` (valeur du message, `__cause__`, invariants hors liste, `KeyboardInterrupt`), `SettingsPage` (vrais clics sur les cinq sites, rien ne remonte à `sys.excepthook`, combos et saisie intacts), `InferencePage` (vrai clic, message générique inchangé, deux moteurs).
- **Préservation M170 avec les vrais moteurs** : pré-vérification ComfyUI et Forge, workers ComfyUI et Forge.
- **Six tests de bout en bout** (mandataires désactivés pour le test) : port non numérique tapé dans Settings (sans socket), puis cinq contre un socket réel sur `127.0.0.1` : ligne de statut absurde (Settings ComfyUI), corps tronqué (Settings Forge), ligne de statut absurde (`GenerationManager`), redirection vers un port invalide (pré-vérification ComfyUI), tolérance du worker ComfyUI à une ligne absurde et à un corps tronqué.

## 6. Résultats, par nature (ne pas confondre)

### 6.1 Sondes hors dépôt (conception)

Six sondes, une exécution chacune, code 0 : U5 (mandataires), U1 (formes d'URL), U2 (pannes de serveur), U3 (racines et structures JSON), U4 (corps d'`HTTPError`), U6 (contrat du formateur, 12 vérifications). Voir section 1 pour les constats et la distinction entre simulation et essais locaux.

### 6.2 Nouveau fichier, dans le dépôt

61 tests réussis, code 0.

### 6.3 Preuve avant/après, classée

- **Ce que contient la copie « avant »** (hors dépôt) : `git archive HEAD src` ; plus le module final `diagnostic_errors.py` (même empreinte que le dépôt) ; plus, dans `comfyui_engine.py`, **une classe vide** `ComfyUIUnexpectedResponseError(Exception)` (docstring « Inert stage-1 addition only. ») insérée après `ComfyUIEngineError`, pour permettre les imports ; plus le fichier de tests final et deux `__init__.py` vides. Les autres fichiers de `src` sont ceux de `HEAD`. **Ce n'est donc pas `HEAD` pur.**
- Résultat : 61 tests exécutés, **132 sous-tests en échec = 91 échecs par assertion (`FAIL`) + 41 erreurs (`ERROR`, exception brute qui sort d'un appel testé)**, répartis sur **18 méthodes**. 43 tests réussissent avant et après.
- **Classification des 18 méthodes** (à partir de l'assertion exacte qui échoue dans la trace) :

| Groupe | Méthodes | Sous-tests | Nature |
|---|---|---|---|
| A. Régressions comportementales démontrées par la trace | 12 | 89 (41 `ERROR` + 48 `FAIL`) | l'ancien code laisse échapper l'exception brute : hors de `GenerationManager.list_*` (41 `ERROR`) ou hors du slot (assertion « rien ne remonte à `sys.excepthook` », 48 `FAIL`) |
| B. Assertions du nouveau contrat, qui échouent normalement sur l'ancien code | 6 | 43 (`FAIL`) | elles exigent un type d'erreur ou un nom qui n'existe pas comme comportement dans l'ancien code |
| C. Invariants réussis avant et après | 43 tests | — | 9 réussissent par construction (le module final est dans la copie « avant »), 34 sont de vrais invariants de comportement non modifié |

- **Groupe A, précisions** : (i) `GenerationManager` : 36 + 3 + 1 sous-tests, plus 1 essai sur socket réel ; (ii) `SettingsPage` : 30 sous-tests (5 sites × 6 erreurs), plus 1 (corps Forge non décodable), plus 1 (racine non objet côté LoRA) ; (iii) `InferencePage` : 12 + 1 ; (iv) 3 tests de bout en bout côté Settings (un sans socket, pour le port non numérique ; deux sur socket réel). **Limites de ce que la trace démontre** : dans un sous-test, seule la première assertion en échec est connue ; les suivantes (combos intacts…) n'y sont pas évaluées. Les tests à plusieurs étapes s'arrêtent à la première : le test « racine non objet LoRA et Ollama » échoue sur le clic LoRA (le clic Ollama n'est pas atteint) ; le test « racine non objet ComfyUI et corps Forge non décodable » d'`InferencePage` échoue sur le premier rafraîchissement ComfyUI (le cas Forge n'est pas atteint) ; le test « corps Forge non décodable » de Settings échoue sur le corps 200 (le corps d'`HTTPError` n'est pas atteint).
- **Groupe B, précisions** : (i) `EngineResponseShapeGuardTest`, 3 méthodes, 31 sous-tests : le moteur lève l'`AttributeError` brute au lieu du type attendu (`assertIsInstance(raised, ComfyUIUnexpectedResponseError)` pour `list_checkpoints`/`check_connection`, 10 sous-tests ; `assertIsInstance(raised, ComfyUIEngineError)` pour loras, samplers, schedulers, 15 ; `assertIsInstance(…, AIBackendError)` pour Ollama, 6) ; (ii) `SettingsPageDiagnosticFrontierTest.test_a_comfyui_non_object_root_gives_a_visible_status…` : 2 sous-tests qui échouent sur la **précondition** `assertIsInstance(error, ComfyUIUnexpectedResponseError)` ; la trace ne démontre donc pas, pour ce test, le comportement du slot ; (iii) deux tests de **préservation** ComfyUI, 10 sous-tests, voir ci-dessous.
- **Tests de préservation ComfyUI : ce qui échoue et ce qui est préservé.**
  - `ComfyUIPreStartCheckPreservationTest.test_a_non_object_root_is_not_an_engine_error_so_it_still_blocks_the_launch` : 5 sous-tests (une racine par sous-test). L'assertion qui échoue est `self.assertIn("ComfyUIUnexpectedResponseError", manager.last_error_message)`, la dernière du sous-test. Elle vient **après** `manager = self.assert_blocked(_body(raw))`, qui a réussi : sur l'ancien code, l'état est `START_FAILED`, la liste d'états est `[START_FAILED]`, `QProcess` n'est pas construit, le worker n'est pas démarré, et le message commence par `ComfyUI pre-start check failed unexpectedly (` (la trace montre `(AttributeError: 'list' object has no attribute 'get'…`). **Préservé : le blocage ; nouveau : le nom du type.**
  - `ComfyUIReadinessWorkerPreservationTest.test_a_non_object_root_still_ends_in_failed` : 5 sous-tests. L'assertion qui échoue est `self.assertTrue(events[0][1].startswith("ComfyUIUnexpectedResponseError:"))`, la quatrième du sous-test, après `assertEqual(len(events), 1)` et `assertEqual(events[0][0], "failed")`, qui ont réussi. **Préservé : l'émission d'un seul `failed` ; nouveau : le nom du type dans le détail.**
  - Ce que les traces permettent de conclure : le comportement de blocage et l'émission `failed` existaient avant ; elles ne permettent pas de conclure plus loin (elles ne distinguent pas ce qui se passerait avec un autre type d'exception).
- **Conclusion bornée** : ces 18 méthodes ne sont pas 18 régressions comportementales démontrées. La trace en démontre 12 (groupe A, avec les limites ci-dessus) ; les 6 autres sont des assertions du nouveau contrat, dont deux méthodes de préservation dont seul le nom du type diffère.
- Une première exécution « avant » dans le dépôt (état inerte) a donné les mêmes totaux mais avec un défaut de mon test (flux `HTTPError` à usage unique réutilisé) ; elle est remplacée par l'exécution de la copie ci-dessus.

### 6.4 Mutations (copies hors dépôt, un défaut chacune)

13 mutants sur 13 détectés par le nouveau fichier : type d'erreur hérité de `ComfyUIEngineError` (2 mutants, dont la garde qui lève une erreur d'engine), `UnicodeDecodeError` ou `LineTooLong` retiré de la liste, `HTTPException` ajoutée à la liste, clause absente dans `GenerationManager` ou dans Settings, traduction côté moteur d'une `HTTPException`, formateur qui attrape `BaseException`, garde Ollama retirée, tolérance du worker réduite, pré-vérification qui tolère une `HTTPException` brute, message Settings sans détail.

### 6.5 Lot ciblé de suites existantes et incident de sortie

- **Nouveau fichier** : 61 tests réussis, code 0.
- **Lot ciblé** (`test_comfyui_engine`, `test_forge_engine`, `test_ollama_engine`, `test_generation_manager`, `test_settings_page`, `test_inference_page`, les deux lifecycle managers, les deux workers de disponibilité, plus le nouveau fichier) : 908 tests `OK` côté `unittest`, puis sortie anormale du processus avec le code réel `0xC0000409`.
- **Deux diagnostics supplémentaires** : le même lot sans le nouveau fichier (847 tests) et le même lot sur une copie de `HEAD` (`git archive HEAD src tests`, 847 tests) : `OK` côté `unittest` puis le même code `0xC0000409`.
- **Qualification** : le lot ciblé termine ses assertions sans échec, puis le processus sort avec `0xC0000409`. Le même code est observé dans deux configurations supplémentaires, dont une copie de `HEAD` sans C1. C1 n'est donc pas nécessaire à cette reproduction ; le mécanisme et les éventuelles interactions restent non établis.
- **Conduite** : la condition « validations ciblées propres avant la suite complète » n'était pas satisfaite. J'ai poursuivi vers la suite complète sur ma propre interprétation du diagnostic, ce que l'autorisation ne prévoyait pas. Ces deux diagnostics supplémentaires n'étaient pas non plus prévus.

### 6.6 Suite complète unique, dans le dépôt, état final

3462 tests exécutés, 0 échec, 0 erreur, 0 ignoré, **code réel 0**, 436 s (3401 tests existants plus 61). Configuration : Python 3.11.9, Qt hors écran, `LOCALAPPDATA` temporaire, bytecode désactivé, `PYTHONFAULTHANDLER` et `PYTHONDEVMODE` absentes, aucune option `-X`, `faulthandler` non activé. Aucun résidu de processus constaté. Exécutée avant le commit fonctionnel. **Comparaison pré-commit, sur l'état préparé (le commit n'existait pas encore)** : la revue pré-commit (section 4) consigne les empreintes sha256 (16 premiers caractères) des six fichiers de code et de tests comme identiques à celles enregistrées pour la suite complète ; ces empreintes sont relevées inchangées avant et après `git add` ; le diff indexé des quatre fichiers de production modifiés et les blobs indexés de `src/engines/diagnostic_errors.py` et du fichier de tests sont identiques aux sections correspondantes de la revue. **Limite** : aucune comparaison du contenu du commit fonctionnel lui-même avec la revue ou avec ces empreintes n'est attestée dans les traces disponibles ; pour le commit, seules sont attestées la liste des sept fichiers et la numstat (1296 ajouts, 3 suppressions), identiques à celles de l'état préparé, et sa création depuis l'index (`git commit -F`, sans `-a`). Traces hors dépôt (non versionnées, `scratchpad/m174/c1impl/out/c1_full_suite.*`) : stdout sha256 `c1e445737e9584f6…`, stderr `bff868af9f7e27af…`, meta `188ee1405ea9e026…`. Aucune suite complète n'a été relancée depuis, ni pendant la publication ni pendant la régularisation documentaire. Ce succès valide cet état dans cette configuration ; il ne résout pas la sortie anormale du lot ciblé (section 6.5).

## 7. Incidents de parcours (sans effet sur le dépôt livré)

- Un `grep -c` sur les fins de ligne s'est révélé trompeur sous Git Bash ; `git ls-files --eol` et Python font foi.
- Défaut de mon test (flux `HTTPError` à usage unique réutilisé), corrigé avant la preuve retenue.
- Erreur de syntaxe dans un script d'application (détectée avant toute écriture), échappements incorrects dans deux scripts d'édition et un motif de mutant ambigu : aucun n'a modifié le dépôt.
- Le traceback `setText(MagicMock)` affiché sur la sortie d'erreur du lot ciblé provient de `inference_page.py` et existait déjà dans la suite complète validée précédemment.

## 8. Limites

- Plateforme unique : Windows 10, CPython 3.11.9 ; IPv6 loopback non testé.
- Aucun vrai ComfyUI, Forge ou Ollama contacté ; clics Qt hors écran, donc pas de contrôle visuel du rendu.
- Les tests reposent sur un `sys.excepthook` temporaire (restauré) et sur l'attribut privé `urllib.request._opener` pour restaurer l'opener des essais sur socket.
- `HTTPException` nue, `RecursionError` et `OverflowError` restent hors liste (voir la section 2) ; les tests documentent qu'elles se propagent encore.
- La sortie anormale `0xC0000409` du lot ciblé reste non expliquée (section 6.5).

## 9. Observations voisines (hors périmètre, aucune sélectionnée)

- Message « base URL is invalid » trompeur pour un corps non décodable (ComfyUI, Ollama) et pour une redirection vers une URL IPv6 invalide ; non verrouillé par un test.
- Forge renvoie sans erreur des éléments non `str` (`[{"title": null}]` donne `[None]`) ; l'effet sur les consommateurs n'est pas examiné.
- Forge, racine non liste : `ForgeEngineError`, donc le lancement reste autorisé (asymétrie avec le principe de M170).
- Repli silencieux des ports hors plage (voir la section 1).
- `ApplicationSettings.from_dict` sans garde `isinstance(str)` pour les URL ; les engines partagés de `main_window.py` sont construits hors `try` ; la couche de stockage n'a pas été examinée.
- `OllamaEngine` traite le corps d'une `HTTPError` comme des données.
- `OllamaEngine.generate_text` et les chemins de génération exposent les mêmes exceptions brutes.

## 10. Fichiers du périmètre (sept, avec le présent document)

| Fichier | numstat (ajouts/suppressions) | EOL |
|---|---|---|
| `src/engines/diagnostic_errors.py` (neuf) | 58 / 0 | LF |
| `src/engines/comfyui_engine.py` | 25 / 2 | CRLF préservé |
| `src/engines/ollama_engine.py` | 2 / 1 | LF préservé |
| `src/managers/generation_manager.py` | 10 / 0 | CRLF préservé |
| `src/ui/pages/settings_page.py` | 37 / 0 | LF préservé |
| `tests/integration/test_diagnostic_protocol_errors.py` (neuf) | 999 / 0 | LF |
| `docs/missions/MISSION_174.md` (neuf, le présent document) | — | LF |

`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md` et `graphify-out/` n'étaient pas touchés par le commit fonctionnel. `CHANGELOG.md`, `docs/PROJECT_CONTEXT.md` et le présent document sont mis à jour par le commit documentaire de régularisation post-Release (section 11) ; `graphify-out/` n'est touché par aucun des deux commits.

## 11. Références Git et publication

Les faits sont répartis selon leur provenance : (A) références relues pendant la régularisation documentaire (lecture actuelle, 2026-10-08) ; (B) opérations de publication antérieures, non rejouées ; (C) Release ; (D) autres éléments. Une lecture actuelle des références ne démontre pas à elle seule le déroulement des opérations antérieures. Les résultats de test et de diagnostic des sections 6 à 8 sont des résultats historiques repris tels quels, aucun n'a été réexécuté.

**A. Références relues pendant la régularisation (lecture actuelle)**

- **Commit fonctionnel** : `fc8fe7486bd85cc274b3797e237a99a02b579899` (`Surface protocol errors in diagnostic calls`), parent `de29e7f1e00875b91509bb214aa3c4cf63cd256d` (`Document post-M173 fixture fix and full-suite validation`) ; sept fichiers, 1296 ajouts, 3 suppressions (lus par `git show --numstat`). `src/` et `tests/` ne diffèrent pas de ce commit à la date de la régularisation.
- **Tag annoté** `v0.2-mission174` : type `tag`, objet `2525b2097878eca21d10835b991d64e1cf0d13de`, cible `fc8fe7486bd85cc274b3797e237a99a02b579899`, annotation « Mission 174: surface protocol errors in diagnostic calls », relus en local et par `git ls-remote` (objet et cible concordants). Les tags `v0.2-mission173` (objet `c3b9c1921ef2530ea06bdfbc9f481c8efa8ce7c8`, cible `b6c9688a409034df03aed37f00b96d0b988f7641`) et `v0.2-mission172` (objet `6e77cfe78ec7c871a94d42315c80c11334f3d5ff`, cible `43058a31b8b47b09076a50093d436646fe8d7005`) sont relus inchangés, en local et à distance.

**B. Opérations de publication antérieures (non rejouées lors de la régularisation)**

Source : sorties d'outils de la session de publication de Claude (journal de session Claude Code, hors dépôt et non versionné) et rapport de publication remis à l'utilisateur. Aucune pièce versionnée dans le dépôt n'atteste ce déroulement ; seule la lecture actuelle (A) montre l'état final concordant.

- **État avant le push** (après `git fetch origin`) : `origin/main` et `main` distant à `de29e7f1e00875b91509bb214aa3c4cf63cd256d`, divergence 0/1 avec pour seul commit local non publié `fc8fe74`, aucun commit distant absent en local, index vide, aucun stash, aucun tag `v0.2-mission174` local ou distant.
- **Publication de `main`** : `git push origin main` (sans force), sortie `de29e7f..fc8fe74  main -> main`, code 0 ; ensuite `HEAD` = `origin/main` = `main` distant = `fc8fe7486bd85cc274b3797e237a99a02b579899` (aussi après un nouveau `fetch`), divergence 0/0.
- **Tag** : `git tag -a v0.2-mission174 fc8fe7486bd85cc274b3797e237a99a02b579899 -m "Mission 174: surface protocol errors in diagnostic calls"`, puis `git push origin refs/tags/v0.2-mission174` (ce tag seul), sortie `* [new tag]`, codes 0 ; type, objet et cible vérifiés en local et à distance juste après, tags M173 et M172 inchangés.

**C. GitHub Release**

- Publiée **manuellement** : confirmation de l'utilisateur, non constatée par Claude à la publication. Constat direct lors de la régularisation, par une lecture non authentifiée de l'API publique GitHub (HTTP 200), sans aucune modification : titre observé « v0.2-Mission174 — Surface Protocol Errors in Diagnostic Calls », `tag_name` `v0.2-mission174`, `draft` `false`, `prerelease` `false`, `target_commitish` `main`, `created_at` `2026-10-08T08:53:15Z`, `published_at` `2026-10-08T08:55:03Z`, aucun asset, URL `https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission174`. L'API ne porte pas le SHA cible du tag : l'association au tag attendu repose sur `tag_name` et sur la résolution du tag lui-même, relue séparément (A).
- **Corps de la Release, relu en entier** : la réserve y figure et est exacte (lot ciblé de 908 tests `OK` côté `unittest` puis `0xC0000409` ; deux diagnostics de 847 tests dont une copie de `HEAD` sans C1 ; C1 non nécessaire à la reproduction, mécanisme et interactions inconnus, incident non résolu ; écart de protocole consigné ; preuve avant/après sur une copie qui n'est pas `HEAD` pur : 12 méthodes de régression comportementale, 6 du nouveau contrat ; aucune mention d'un lot propre ni d'une indépendance à C1). **Nuance relevée** : le corps dit que les ports hors plage sont « silently truncated », formulation plus affirmative que la section 1 de ce document (comportement compatible avec une troncature modulo 65536, port de destination non observé directement) ; le présent document prévaut et la Release n'est pas modifiée.

**D. Autres éléments**

- **Revue pré-commit hors dépôt** : `scratchpad/m174/c1impl/C1_revue_precommit_v2.txt`, sha256 `5cd5bbf4b500cb42f2caef2046b668d3d8304e9945bd43470245590487278317` (empreinte revérifiée lors de la régularisation, identique). Elle précède la finalisation du statut pour le commit : le document commité prévaut sur ses formulations. Cette pièce est hors dépôt et non versionnée.
- **Régularisation documentaire** : un premier commit documentaire distinct (`790a75a9a4167c2b78266509900bae7a317201ba`, après la Release : `CHANGELOG.md`, `docs/PROJECT_CONTEXT.md` et le présent document), puis un second commit documentaire, limité à `docs/PROJECT_CONTEXT.md` et au présent document, qui corrige un champ de gabarit non substitué et des formulations de provenance (sections 6.6 et 11). La référence de ce second commit n'est pas consignée ici (le document fait partie du commit ; Git fait autorité). Aucune modification de production ni de tests, aucun test ni diagnostic exécuté, aucun tag déplacé ou créé ; aucun commit documentaire n'est la cible d'un tag.
- **État de clôture** : Mission 174 close avec réserve non résolue sur la sortie anormale `0xC0000409` du lot ciblé (section 6.5). Cette clôture ne résout pas cet incident et ne résout aucun incident historique de la Mission 173 ou antérieur (sorties 127, `0xC0000374`, `taskkill`, Mission 164) ; aucune relation entre ces incidents n'est établie ni exclue. Aucune Mission 175 n'est sélectionnée : un nouvel audit global READ-ONLY post-Mission 174 devra précéder toute décision.
