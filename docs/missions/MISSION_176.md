# Mission 176 — Give Downloaded ComfyUI Outputs a Local Name of Their Own

> **STATUT : Mission close avec réserves non résolues ; commit fonctionnel, tag annoté et GitHub Release publiés.** Cette clôture est une décision distincte de l'architecte, **non un résultat des exécutions ci-dessous**. Elle ne résout aucune réserve technique ni historique, ne change pas les limites de la section 9 et ne transforme ni la supervision incomplète en résultat net ni le module 4 non net en résultat net : la suite complète reste classée `OK_NON_NET`. Les exécutions de la section 7 (nouveau fichier de tests, comparatif limité sur l'ancienne production, module du moteur, modules voisins, module 4 et suite complète) sont des **pièces de validation de l'état local, avec leurs limites**. Chronologie : cette archive a été rédigée avant les exécutions, finalisée le 2026-10-12 **après** elles (section 12), commitée avec le commit fonctionnel, puis complétée après la publication (sections 9, 11, 12 et 13) ; la version présente lors des exécutions n'est pas celle-ci et aucun test ne lit ce fichier (section 7.9). Aucun identifiant du commit documentaire de cette régularisation n'est inscrit ici ; Git fait autorité.

## 1. Défaut confirmé

- **Déclencheur** : `ComfyUIEngine.download_output()` utilisait le `filename` fourni par le serveur comme nom local (`Path(output_directory) / filename`) et ouvrait en `"wb"`. Deux téléchargements portant le même nom distant écrivaient donc dans le même fichier local ; un nom distant contenant `..` ou un chemin absolu désignait une destination hors du dossier de sortie. **La fréquence du déclencheur n'a pas été mesurée** ; le compteur de nom de sortie de ComfyUI, qui rend un même nom possible d'une génération à l'autre, reste une **hypothèse amont non vérifiée** (code de l'installation Desktop non relu).
- **Constats observés** (sondes hors dépôt, section 8) : la sonde 1 (cas C01–C08 seulement, voir limites) a observé l'écrasement d'un même nom, l'écrasement de sentinelles par des noms `..\`, `../`, `..\..\` et un chemin absolu, et l'écriture d'un flux alternatif `:hidden` après création d'un fichier de base vide ; `subfolder` et `type` sont envoyés au serveur mais non utilisés localement. La sonde 2b (montage isolé, substitutions déclarées) a observé, avec le vrai `InferencePage` et les vrais managers : le fichier d'une image **acceptée** voit son contenu remplacé par la génération suivante de même nom distant, puis disparaît au rejet de cette seconde génération, l'entrée de galerie, `Workspace.images` et `project.json` restant en place. Le nettoyage n'a été constaté que sur cette exécution réussie.
- **Déduit par lecture, non observé** : une seconde acceptation sur le même chemin est classée « ignorée » par `add_images()` (`workspace_manager.py:642-646`).
- Les chemins de sortie et les scénarios dangereux n'ont été exercés que dans des arborescences temporaires privées ; aucun périphérique, aucun partage réseau, aucune destination extérieure.

## 2. Contrat (décisions de l'architecte)

1. **Requête inchangée** : `filename`, `subfolder` et `type` sont envoyés tels quels à `/view` ; le nom local n'en dépend pas.
2. **Nom local** : `<uuid4().hex>.<extension>`, sans préfixe. Les paramètres distants de nom et de chemin (`filename`, `subfolder`, `type`) ne sont jamais repris localement ; **seule l'extension dépend de ce que le serveur a envoyé** (signature des octets).
3. **Extension** : uniquement par signature des octets — PNG, JPEG (`jpg`), WebP — avec repli `png` ; les règles sont celles déjà utilisées par `ForgeEngine`. Les octets sont écrits **inchangés** ; la détection n'est pas une validation d'image.
4. **Aide privée dans `ComfyUIEngine`** ; aucun module partagé ; `ForgeEngine` **inchangé**.
5. **Création exclusive** `"xb"`, **huit noms au plus**. **Seul `FileExistsError`** à la création autorise un nouveau nom ; toute autre erreur locale se propage telle quelle, sans nouvelle tentative. À épuisement : `FileExistsError(errno.EEXIST, …)` chaînée à la dernière collision.
6. **Aucun nettoyage après un échec d'ouverture** (rien n'a été créé). Après une création réussie, si l'écriture ou la fermeture échoue : suppression au mieux **du seul fichier de cette tentative**. Pour les **erreurs ordinaires** couvertes, l'erreur initiale est celle qui est levée (une erreur de fermeture après un échec d'écriture, ou d'effacement, est consignée en note). **Cette priorité n'est pas revendiquée face à une interruption** (`KeyboardInterrupt`, `SystemExit`…) : une interruption qui survient pendant le traitement d'une erreur se propage telle quelle, l'effacement du fichier étant malgré tout tenté.
7. **Notes conditionnelles** (décision sur Python) : `Exception.add_note()` n'existe qu'à partir de Python 3.11 alors que le README annonce « 3.10+ recommandé » ; **le prérequis n'est pas relevé**. L'ajout d'une note passe par `_attach_note()` (`comfyui_engine.py:65`) : la recherche de l'attribut et l'appel sont tous deux protégés contre les exceptions ordinaires ; si `add_note` est absent ou échoue, la note est abandonnée, sans remplacer l'erreur initiale ni empêcher le nettoyage. Les interruptions ne sont pas interceptées. La note est un enrichissement facultatif ; la conservation de l'erreur initiale (erreurs ordinaires) et le nettoyage sont obligatoires.
8. **Pas de garantie absolue** contre le remplacement concurrent du dossier ou de l'entrée créée (notamment entre la fermeture et l'effacement) ; dossier de sortie lui-même lien ou jonction, droits restrictifs, antivirus, système de fichiers sans création exclusive, partages réseau : non couverts.
9. Erreurs réseau (`ComfyUIEngineError`) et locales (`OSError`, normalisées en `GenerationError` par `GenerationManager`) : inchangées dans leur nature.

## 3. Correction

`src/engines/comfyui_engine.py` (production, seul fichier de production modifié) :

- imports `errno` et `os` ; constante privée `_OUTPUT_NAME_ATTEMPTS = 8` (ligne 62) ; fonction privée `_attach_note()` (ligne 65) ;
- `download_output()` (ligne 263) : requête et traitement des erreurs réseau inchangés, docstring mise à jour, puis `return self._write_new_output_file(image_bytes, output_directory)` ; `filename` ne sert plus qu'à la requête et au message d'erreur HTTP ;
- `_guess_image_extension()` (ligne 303) : signatures PNG, JPEG, WebP, repli `png` ;
- `_write_new_output_file()` (ligne 318) : boucle de huit noms, `open(destination, "xb")`, `except FileExistsError` seul, écriture puis fermeture sans bloc `with` (pour qu'une erreur de fermeture ne remplace pas l'erreur d'écriture), nettoyage `os.unlink` du fichier de la tentative sur toute exception, relevée telle quelle.

Aucun paramètre public n'a été ajouté (ni pour les tests). Les numéros de ligne ci-dessus ont été relus sur le fichier au sha256 testé (section 8). Fins de ligne : le fichier de production a conservé les fins de ligne CRLF de l'arbre de travail (`git ls-files --eol` : `i/lf w/crlf`, `core.autocrlf=true`) ; **mesure du 2026-10-12 : 919 CRLF, 919 LF, aucun CR isolé** (voir la correction de l'ancien relevé « 912 » en section 12).

## 4. Interactions étudiées (lecture)

- **Tri et libellés de galerie** : le tri par défaut se fait sur le nom de fichier (`images_page.py:228-231`, libellés `:256` ; `datasets_page.py:653-655`, `:698` ; `select_images_dialog.py:67`). Avec des noms UUID, l'ordre n'a plus de rapport avec l'ordre de création et les libellés montrent un identifiant hexadécimal. **Impact visible, documenté et hors périmètre : aucun changement de galerie, de tri ou de libellé n'est fait ici** ; il fait l'objet d'une décision distincte.
- **Images déjà écrasées** : non réparées ; aucun correctif rétroactif.
- **Flux Accepter/Rejeter** : inchangé. Le fichier accepté reste dans l'espace de travail (`outputs/`), le rejet supprime le fichier en attente.
- **Préfixe de sortie** `AIStudioToolkit` côté ComfyUI : inchangé.
- **Forge** : `ForgeEngine._save_image` utilisait déjà des noms UUID ; inchangé.

## 5. Tests

**Tests existants adaptés** (`tests/integration/test_comfyui_engine.py`, trois attentes de nom devenues incompatibles ; assertions de requête et de contenu conservées) :

- `test_download_output_writes_file_and_returns_path` : chemin parent et nom local `[0-9a-f]{32}.png` au lieu de `img.png` ;
- `test_download_output_url_encodes_special_characters` : idem au lieu de `my image (1).png` ; les assertions sur la requête encodée sont inchangées ;
- `ComfyUIEngineGenerateImageTest` (attente sur `result.png`) : idem.

Ajout d'un `import re` et d'une constante d'expression régulière. Les tests de texte source (termes interdits dans `download_output()`/`_submit_and_download()`, absence d'import du domaine) ne sont pas modifiés ; le texte du nouveau code a été contrôlé statiquement contre la liste des termes (section 6), puis ces tests ont tourné (section 7.3).

**Nouveau fichier** `tests/integration/test_comfyui_download_local_name.py` (32 méthodes de test, plus des sous-cas), organisé **par nature de résultat** pour qu'une même exécution sur l'ancienne et la nouvelle production reste lisible (une erreur de montage n'est jamais une preuve avant/après) :

- *Invariants* (`DownloadInvariantsTest`, 7 tests ; doivent tenir avant **et** après) : la requête transporte `filename`, `subfolder` et `type` inchangés ; octets écrits inchangés et chemin renvoyé = fichier écrit ; erreurs réseau et HTTP → `ComfyUIEngineError` sans fichier créé ; dossier absent → `FileNotFoundError` ; autres erreurs à la création propagées inchangées, une seule tentative, aucun effacement ; erreur d'écriture levée telle quelle et descripteur libéré.
- *Scénarios révélant le défaut* (`DownloadDefectScenariosTest`, 3 tests, plus `AcceptedImageSurvivesRejectedRegenerationTest`, 1 test ; attendus en **échec avant**, succès après ; ils vérifient des **résultats**, jamais le nouveau format de nom) : deux téléchargements du même nom distant conservent chacun leur contenu ; des noms distants hostiles (`..\`, `../`, chemin absolu **interne**, `subfolder` hostile) ne modifient l'arborescence privée que par **un seul nouveau fichier dans `outputs/`** (sentinelles intactes) ; **flux alternatifs NTFS** (Windows) : `nom.png:hidden`, avec et sans fichier de base préexistant, ne crée ni fichier de base sous ce nom ni flux (ouverture du flux vérifiée explicitement, un simple parcours `os.walk` ne recensant pas les flux) ; première image acceptée conservée après une seconde génération rejetée.
- *Contrat nouveau* (`DownloadNewContractTest`, 11 tests, et `DownloadNewContractFailureTest`, 10 tests, soit **21 tests** ; échec **attendu** avant, par construction, sans valeur de preuve sur l'ancien comportement) : nom UUID4 hexadécimal sans préfixe ; format du nom pour tous les noms hostiles ; extension selon la signature et octets inchangés (PNG, JPEG, WebP, vide, `RIFF` seul, `RIFF…WAVE`, un octet, GIF, 256 octets) ; mode `"xb"` ; collisions de fichiers et de lien dur sans écrasement ; huit collisions → `FileExistsError` après exactement huit tentatives, neuvième nom jamais essayé ; identifiant toujours identique → huit tentatives ; autres erreurs non retentées ; collisions avec un dossier et une jonction (Windows, jonction ignorée si non créable) ; échecs injectés d'écriture, de fermeture, d'effacement, double et triple échec avec l'erreur d'écriture conservée, notes lorsque `add_note` existe, chemin d'erreur sans `add_note` (tests exécutés sous CPython 3.11.x, qui simulent l'absence sur l'objet d'erreur : **pas une exécution sous Python 3.10**) ; seul le fichier de la tentative en échec est effacé.
- *Conséquence utilisateur* : vrai `InferencePage`, `GenerationManager`, `GenerationWorker` sur vrai `QThread`, `ComfyUIEngine`, `WorkspaceManager` sur arborescence privée, `EventBus`, `ImagesPage` et **deux images PNG réellement décodables** ; **substitutions déclarées** : `urllib.request.urlopen` remplacé par un faux serveur en mémoire (aucun socket ; actif de avant la construction des widgets à après leur destruction), gestionnaires de prompts, d'assistant, de personnages, de paramètres et moteur Forge remplacés par un collaborateur dont **tout accès est refusé et enregistré** (aucun `MagicMock` ne fabrique de valeur consommée comme texte, chemin ou configuration), bibliothèque LoRA vide explicite, gestionnaire de cycle de vie factice en état `RUNNING_OWNED` (aucun processus), filet de sécurité des boîtes de dialogue, **enregistrement des exceptions qui s'échappent d'un slot Qt** (`sys.excepthook`) : toute exception échappée fait échouer le test ; les messages de log Qt ne sont pas captés. Pas de `MainWindow`, pas de vrai ComfyUI.
- *Nettoyage* : chaque ressource enregistre son nettoyage dès son acquisition (une construction partielle libère ce qui existe) ; le worker est arrêté par attente bornée de 20 s (un `QThread` encore actif n'est jamais détruit) ; les widgets sont détruits puis leur destruction est vérifiée ; la substitution réseau, le filet de dialogues, l'enregistreur d'exceptions et l'arborescence privée ne sont retirés qu'ensuite ; l'arborescence est supprimée **sans `ignore_errors`** ; tout nettoyage incomplet, toute poignée laissée ouverte par le code testé est signalé comme erreur, jamais masqué. Le faux fichier à échecs injectés respecte le protocole de gestionnaire de contexte d'un vrai fichier (son `__exit__` ferme et peut donc remplacer une erreur en cours, comme pour un vrai fichier), ce qui rend le montage applicable aux deux implémentations ; les poignées réelles sont libérées en fin d'exécution même après assertion échouée.

Aucun résultat n'est repris du prototype `probe3b` : ses 33 vérifications portaient sur une fonction jetable, pas sur `ComfyUIEngine`.

## 6. Vérifications statiques (avant les exécutions)

Contrôles **statiques**, attribués séparément :
- `ast.parse` sur les trois fichiers Python : établit **la validité syntaxique et rien d'autre** ;
- un script d'analyse des noms (heuristique maison, ni `pyflakes` ni exécution) : aucun nom importé n'est absent des références `Name` du fichier ; ce contrôle est approximatif et ne vaut pas analyse statique complète ;
- comptage des fins de ligne ; recherche textuelle des termes interdits par les tests structurels dans `download_output()` et `_submit_and_download()`, et des lignes d'import du domaine : aucun.

Le nombre de tests de la suite complète (3 512 = 3 480 + 32) et de modules (62) a aussi été établi par lecture `ast` avant son exécution (sans import ni collecte).

## 7. Exécutions et résultats (chronologie, résultats séparés)

Toutes les exécutions ont eu lieu sur la même machine (Windows 10), avec un environnement privé (`LOCALAPPDATA`, `USERPROFILE`, `HOME`, `TEMP`, `TMP` dans le dossier d'exécution, `QT_QPA_PLATFORM=offscreen`, sans `PYTHONFAULTHANDLER`, `PYTHONDEVMODE`, `-X`). Une exécution par état, sans relance. Les heures sont locales. **Ce qui a réellement été exécuté diffère selon les cas, qu'il ne faut pas confondre :**

- **Exécutions sur la production corrigée** (7.1, 7.3, 7.4, 7.6, 7.8) : le code exécuté est celui des fichiers du dépôt aux empreintes de la section 8 (l'archive `MISSION_176.md` y figurant avec son état de rédaction d'alors). Les relevés avant/après du lanceur prouvent la **stabilité des fichiers du dépôt** pendant ces exécutions ; la **provenance des modules effectivement chargés** n'est consignée par le processus testé que pour 7.3, 7.4, 7.6 et 7.8 (modules `src`/`tests` lus dans le dépôt). CPython 3.11.9 est consigné dans le processus testé pour 7.3, 7.4, 7.6 et 7.8.
- **Premier lancement** (7.1, `-m unittest` depuis la racine du dépôt) : **n'a consigné ni la version exacte de Python, ni les modules effectivement chargés** ; il a utilisé l'interpréteur du venv dont l'empreinte est celle des lancements suivants, ce qui n'en consigne pas la version.
- **Comparatif sur l'ancienne production** (7.2) : le code exécuté est une **copie de l'ancienne production** hors dépôt (moteur extrait du blob de `eff51b1`, sha256 `b51962f7…b1af`, plus le seul nouveau fichier de tests aux mêmes empreintes). Les empreintes du dépôt réel que le lanceur a relevées avant et après **ne décrivent pas le code exécuté** : elles montrent seulement que le dépôt n'a pas bougé. Les modules effectivement chargés (depuis la copie), CPython 3.11.9 et PySide6 6.11.1 sont consignés par le processus de ce comparatif.
- **Validation du superviseur** (7.5) : scripts inoffensifs hors dépôt, sans rapport avec les quatre fichiers.

### 7.1 Nouveau fichier sur la production corrigée — 2026-10-09 16:09:35
`python -B -u -m unittest -v -f tests.integration.test_comfyui_download_local_name` : **32 tests exécutés sur 32 attendus, 32 réussis**, 0 échec, 0 erreur, 0 ignoré (y compris les tests conditionnels : lien dur, jonction, dossier, flux alternatifs, deux tests de notes), code réel du processus **0**, 0,930 s (rapport unittest). `stdout` vide ; `stderr` : 32 lignes `… ok` et le pied du rapport, aucun avertissement ni message Qt ; dossiers privés vides ensuite. **Cela ne démontre pas** qu'un test réussi est capable d'échouer (traité en 7.2) ; la version de Python n'avait pas été consignée par ce lancement.

### 7.2 Comparatif limité sur l'ancienne production — 2026-10-10 10:45:03
Arbre « ancienne production » : 162 fichiers de `eff51b1` identiques octet à octet à leurs blobs (première extraction écartée : `git archive` avec `core.autocrlf=true` avait livré des fins de ligne CRLF, observation limitée à cette machine et à cette invocation), plus le seul nouveau fichier de tests (même empreinte que celui qui a réussi). Portée : les 7 invariants et les 4 scénarios de défaut ; **les 21 tests du nouveau contrat n'ont pas été exécutés sur l'ancienne production** et n'ont donc pas été comparés. Code réel **1**, convention du runner (échecs uniquement, tous conformes à la prévision, exécution complète).
- **Méthodes** : 11 exécutées sur 11 ; **7 invariants réussis** ; **4 scénarios de défaut en échec d'assertion** aux assertions prévues ; 0 erreur, 0 ignoré. **Sous-tests** : 24 rapportés, 19 réussis, 5 en échec d'assertion, 0 erreur.
- **Ce que chaque échec démontre, et ce qu'il ne démontre pas** (chaque test s'arrête à sa première assertion en échec ; lignes du fichier de tests) :
  - deux téléchargements du même nom distant (l. 452, `assertNotEqual(first, second)`) : les deux chemins renvoyés sont identiques. Le contenu écrasé (assertions des l. 453-455) **n'est pas atteint** : l'écrasement reste établi par la sonde 1 ;
  - noms distants hostiles (l. 466) : pour `..\`, `../` et chemin absolu interne, un fichier sentinelle existant hors de `outputs/` (dans l'arborescence privée) est modifié ; `subfolder` hostile et un nom bénin réussissent. Les assertions suivantes ne sont pas atteintes ;
  - flux alternatifs (l. 487, Windows) : `stream_only.png:hidden` crée l'entrée de fichier de base `stream_only.png` ; avec un fichier de base existant, aucune nouvelle entrée de répertoire. Les assertions des l. 488-500, **dont l'ouverture directe du flux, ne sont pas atteintes** : la présence du flux reste établie par la sonde 1 seulement ;
  - image acceptée puis génération rejetée (l. 1077, `assertNotEqual(second_path, first_path)`) : le chemin en attente de la seconde génération est celui de l'image acceptée. **Ni le remplacement du contenu ni la suppression du fichier accepté au rejet ne sont atteints** : cela reste issu de la sonde 2b.
- Établit : les 7 invariants tiennent sur l'ancienne production avec ce montage ; les quatre scénarios sont **capables d'échouer** et distinguent les deux implémentations sur les points listés. N'établit pas : la valeur des 21 assertions du nouveau contrat, l'écrasement du contenu ni la présence du flux (assertions non atteintes), la stabilité, le comportement sous Python 3.10.

### 7.3 Module du moteur — 2026-10-10 11:06:17
`tests.integration.test_comfyui_engine` (via une enveloppe équivalente à `-v -f`, équivalence avec `python -m unittest` non démontrée) : **117 tests sur 117 attendus, `OK`**, 0 échec, 0 erreur, 0 ignoré, code réel **0**, 0,926 s. Les trois attentes de nom adaptées et les six tests structurels réussissent. Aucun avertissement ni trace ; `TEMP` privé vide ensuite. Fichier mocké de bout en bout : rien sur un ComfyUI réel.

### 7.4 Modules voisins — 2026-10-10 (résultats séparés, un processus chacun)
| Module | Début | Tests | Résultat | Code réel |
|---|---|---|---|---|
| `test_generation_manager` | 11:12:36 | 74 / 74 | `OK`, 0 ignoré | 0 |
| `test_generation_worker` (`QThread` réel) | 11:29:55 | 17 / 17 | `OK`, 0 ignoré | 0 |
| `test_diagnostic_protocol_errors` (six tests avec serveur TCP d'écoute sur `127.0.0.1`, port éphémère) | 11:36:07 | 61 / 61 | `OK`, 0 ignoré | 0 |

Aucune trace ni avertissement dans ces trois modules ; dossiers privés vides ensuite ; aucune capture réseau (les ports éphémères n'ont pas été enregistrés). Ces exécutions séparées ne démontrent pas l'absence d'interactions en suite commune.

### 7.5 Supervision par Job Object (validation du dispositif, hors dépôt) — 2026-10-10
Un superviseur hors dépôt (processus créé suspendu, assigné à un job `KILL_ON_JOB_CLOSE`, inventaire par échantillonnage toutes les 0,25 s) a été validé séparément avant d'être utilisé : scénario 1 **partiel** (deux tentatives distinctes, la seconde sans prévision satisfaite), scénarios 2 et 3 **établis dans des limites**, scénario 4 **observation limitée** (terminaison observée après l'arrêt du superviseur, compatible avec `KILL_ON_JOB_CLOSE`, sans attribution directe). Le job ne limite pas la portée d'un `taskkill`. L'inventaire par échantillonnage peut être incomplet ; l'équivalence des lancements supervisés avec un lancement direct n'est pas démontrée.

### 7.6 Module 4 `tests.integration.test_inference_page` sous superviseur — 2026-10-11 12:07:32 à 12:10:55
**Tentative après restauration** (voir 7.7), à ne pas présenter comme la première exécution certaine. Résultat **non net** : **234 tests sur 234 attendus, tous réussis** (0 échec, 0 erreur, 0 ignoré) ; code naturel du processus testé **0**, observé avant toute intervention ; **superviseur code 20** (supervision incomplète : 9 processus comptés par le job, **4 identifiés**, 5 jamais identifiés, raison uniquement d'inventaire) ; aucune intervention ; **état final du job vide confirmé** ; pilote code 4 (`OK_NON_NET`). `stderr` : **trace Qt** `TypeError … QLabel.setText(MagicMock)` (`inference_page.py:789` → `:865`) pendant `test_switching_engine_preserves_a_real_lora_selection` (rapporté réussi) — réserve de M175 de nouveau observée, non corrigée, sans attribution à M176. Bornes 300/360/420 s ; durée unittest 199,718 s.

### 7.7 Lancement du 2026-10-10 et incident de protection
Un premier lancement du module 4, le 2026-10-10 à 19:31:58, a été interrompu côté outil (« session ended before this call's result was recorded ») : **son issue est inconnue** (aucun dossier de résultat à la reprise, ce qui ne prouve pas l'absence de démarrage). À la reprise, le lanceur et le pilote avaient disparu de leur dossier. L'utilisateur a observé dans Bitdefender une entrée de quarantaine `run_module4_once…` (détection `Atc4.Detection`, 2026-10-10 19:32) et des blocages d'applications (Advanced Threat Defense). **Établi** : une intervention de Bitdefender sur cette session, en forte corrélation temporelle avec l'appel interrompu. **Non établi** : le stade atteint par le lancement, la cause de chaque disparition ou refus d'écriture, le caractère de faux positif, l'étendue de l'exclusion annoncée. **Claude n'a effectué aucune modification de protection** (ni exclusion, ni restauration de quarantaine, ni réglage). **L'utilisateur** a restauré manuellement le lanceur (empreinte exacte) ; l'interface de Bitdefender annonçait alors une exclusion automatique, dont **l'état effectif et le périmètre restent inconnus**. Le pilote a été reconstruit à l'identique par Claude (empreinte exacte). Une intervention analogue lors d'un lancement ultérieur n'est pas évaluée.

### 7.8 Suite complète sous superviseur — 2026-10-12 09:53:23 à 10:00:32
`discover -s tests -p "test_*.py" -v` (sans `-f`), une seule tentative, en arrière-plan. Niveau **`OK_NON_NET`**.
- **unittest** : **3 512 tests exécutés (attendu 3 512), 62 modules découverts (attendu 62), tous réussis** ; 0 échec, 0 erreur, **0 ignoré** (y compris les dix tests conditionnels), 0 échec attendu, 0 succès inattendu ; `Ran 3512 tests in 423.702s`, `OK`. 156 modules `src`/`tests` chargés, tous depuis le dépôt.
- **Codes, séparés** : processus testé **0** (naturel, avant toute intervention) ; superviseur **20** ; aucune intervention ; pilote **4** ; lanceur **1** (convention : tout niveau autre que net).
- **Job et inventaire** : état final **vide confirmé** (`ActiveProcesses` 0) ; inventaire **incomplet : 270 processus comptés, 236 identifiés, 34 jamais identifiés** (raison unique, d'inventaire) ; 236 membres sortis avant toute intervention ; aucun membre listé encore vivant à l'observation indépendante ; toutes les fermetures de handles ont réussi. L'inventaire incomplet ne signifie ni survivant observé ni défaut du code testé.
- **Lecture de `stderr`** : **3 659 lignes**, dont **3 481 terminées par `... ok` et 178 autres** (73 en-têtes de tests à docstring, 31 en-têtes suivis d'une sortie, 31 `ok` isolés, 19 `DISPOSAL`, 24 lignes de continuation ou de pied de rapport). 3 481 + 31 = 3 512 verdicts `ok`, 3 512 en-têtes distincts, aucun `FAIL`/`ERROR`/`skipped`. Les 3 408 lignes `nom (id) ... ok` ont la forme exacte attendue ; les 73 autres lignes `... ok` sont des docstrings suivant chacune un en-tête seul, **sans que le texte de chacune de ces 73 docstrings ait été relu ligne à ligne** (limite). Les 3 481 lignes `... ok` ont été classées par programme, non affichées une à une.
- **Constats sans attribution supplémentaire** : (1) la **trace Qt** `setText(MagicMock)` de M175 (voir 7.6) ; (2) **trois `DeprecationWarning`** `QMessageBox.setButtonText` (`lora_page.py:467-469`) ; (3) **quatre messages `taskkill`** sur `stdout` (« Opération réussie : le processus de PID … a été arrêté »), d'origine non établie ; leurs PID (34876, 44240, 47732, 49004) figurent parmi les membres du job ; (4) des messages journaux de tests d'erreur simulée (copies, écritures, fichiers corrompus) et 18 lignes `DISPOSAL`, tous rapportés réussis.
- **Deux sorties `0xC0000409`** : deux membres du job (PID 25916, redirecteur du venv, et PID 19980, interpréteur système, vus à 385,687 s) sont sortis avec le code `3221226505` (`0xC0000409`) avant toute intervention. **Ce sont des membres du job distincts du processus testé (code naturel 0). Attribution non établie.** Le test `test_crash_reports_failed_with_native_detail` active `FAKE_CRASH="1"` et le faux OneTrainer appelle réellement `os.abort()` : c'est un **constat de lecture** ; **aucun rattachement de ces deux PID à ce test n'est démontré** (le superviseur ne conserve ni parenté ni ligne de commande des membres, et les sorties du faux processus ne figurent pas dans les traces). Un test voisin, `test_cancel_with_crash_exit_still_reports_cancelled`, appelle `_on_process_finished(…, CrashExit)` sans lancer lui-même un processus qui plante. **Ce n'est pas une reproduction établie de l'incident M174 ;** l'égalité du code ne suffit pas. Les autres codes de sortie des membres (141 à 0, 72 à 1, 19 à 62097, 1 à 2, 1 à 128) sont descriptifs et non interprétés.
- **Différences de lancement avec la suite de M175** (3 480 tests, 452,048 s, `python -B -u -m unittest discover -s tests -p "test_*.py" -v` direct, sans job) : enveloppe en processus au lieu de `-m` (équivalence non démontrée ; le dossier du script reste dans `sys.path`) ; liste blanche d'environnement (`APPDATA` absent) ; processus créé par un superviseur, sorties dans des fichiers, appartenance à un job (tous les descendants, dont `taskkill.exe`, `cmd.exe`, `conhost.exe`). Les durées ne sont pas comparables au sens strict et aucun jugement de performance n'est porté.
- Un lancement unique : reproductibilité non démontrée.

### 7.9 Empreintes et documentation finalisée après les exécutions
- **Relevés du lanceur de la suite** (`meta.json`, empreintes complètes avant et après) : les quatre fichiers M176, les trois fixtures du module 4, le venv, le superviseur, l'enveloppe et le pilote identiques avant et après, et conformes aux valeurs autorisées ; manifeste de 163 fichiers `.py` de `src/` et `tests/` identique avant et après ; `HEAD`, index et stash inchangés. Relevés équivalents des lanceurs précédents dans leurs propres traces.
- **Recalculs ultérieurs (lectures de contrôle)** : après la suite, comparaison complète des valeurs `sha256_before`/`sha256_after` du lanceur aux empreintes autorisées, et recalcul complet des quatre fichiers (2026-10-12, complément de lecture) ; recalcul complet à nouveau avant la présente finalisation. Un premier contrôle fait immédiatement après la suite ne portait que sur les 16 premiers caractères, d'où le complément. Ces recalculs ne sont pas des relevés du lanceur.
- **Documentation après les exécutions** : `MISSION_176.md` a été réécrit le 2026-10-12 après toutes les exécutions ; l'empreinte du fichier testé (`b2af06f1…`) n'est plus celle du fichier actuel (section 8). Aucun test ne lit ce fichier (recherche textuelle dans `tests/` : seulement des commentaires qui citent des archives de missions). La production et les tests n'ont pas été modifiés depuis les exécutions (empreintes identiques).

## 8. Provenance des preuves (hors dépôt)

Les preuves sont dans le dossier de travail de la session (hors dépôt, non versionné) ; la racine est `C:\Users\dlero\AppData\Local\Temp\claude\J--Projets-AI-Studio-Toolkit\243eda7b-1928-4f3d-92ae-9bf391064a58\scratchpad\`. Empreintes complètes des quatre fichiers du périmètre **à l'état testé** :

| Fichier | sha256 |
|---|---|
| `src/engines/comfyui_engine.py` | `05f8414c6897c244f063d30c77adf855750adff9d0111f03e6077769f08fdd47` |
| `tests/integration/test_comfyui_engine.py` | `5189ab3c8a485cf1a84d7a5b547fd2a0a83d8b99988b30daf0a2b513e3587c8b` |
| `tests/integration/test_comfyui_download_local_name.py` | `4ae27e76577d88bfcf3d65a3c5b7b4a64fb2fcbe5d571a069fbfb484bf947efc` |
| `docs/missions/MISSION_176.md` (état de rédaction avant les exécutions) | `b2af06f18e1956593a1747fc0ce21a1769b4eb9e66602fea19b14e8b212a8e06` |

Pièces principales (chemins relatifs à la racine ci-dessus) :

| Pièce | sha256 |
|---|---|
| `m176audit\CONCEPTION_D1_NOM_LOCAL_v3.md` (conception validée) | `10cbca000754d0b5fa8119a1485f0ce14e521d2a8f8eafe73d9e65c03ad432f3` |
| `m176run\runs\first_run_new_production_20261009_160934\stderr.txt` (7.1) | `8580628c6de6965bab8522206872bfd8884a90cb6705db7804ae6f157e76ef67` |
| `m176old\runs\old_production_limited_20261010_104503\stderr.txt` (7.2) | `4f577f928e3c91a217e0a160db47f4c1a776a01a91a37ae2eee99e5bac691710` |
| `m176old\runs\old_production_limited_20261010_104503\outcomes.json` | `289dfc18d3bef3360aa1a0e76b10ada87aa568f1c4a106741fc1e253b9e698e2` |
| `m176eng\runs\engine_module_corrected_20261010_110615\stderr.txt` (7.3) | `78c778409c757ba977a3bcdfcfe7de6ca3560f12a925354e4fef7b6723c6002c` |
| `m176batch\runs\batch01_test_generation_manager_20261010_111236\stderr.txt` (7.4) | `8ba109e391ca5c15fbdbf868fb806252eb1790400c91382721e280ad389dd646` |
| `m176batch\runs\batch02_test_generation_worker_20261010_112954\stderr.txt` | `72bbf0c4a9712acbbcd7cd224b8df73141d31e2874f80522c1b1b3025afb8315` |
| `m176batch\runs\batch03_test_diagnostic_protocol_errors_20261010_113606\stderr.txt` | `073814ed95252048350a47a6931e038cf434877c0d12b1cc302114f30722927e` |
| `m176sup\job_supervisor_v2.py` (superviseur, inchangé) | `dbb13d1909131c2e8dcc6b8bea7388f21f5a799eec6a5c88f92f4fc4bb644ee0` |
| `m176sup\RAPPORT_SUPERVISEUR_JOB_OBJECT_M176.md` (7.5) | `734c624a099ea856e1db34d5dbbdddea4fb6021e1b12546ecb9e8424a50882ad` |
| `m176sup\RAPPORT_MODULE4_TENTATIVE_POST_RESTAURATION_M176.md` (7.6) | `24b179513ba14e9e5c0c3a6e829cb101f41595457a3fe87a1d27a4da33e28e52` |
| `m176sup\INCIDENT_MODULE4_PIECES_ABSENTES_M176.md` (7.7) | `21c7358054ad78cea23f44f5a4bfdb54d8f26ac0517da36368c793855bf2af0e` |
| `m176sup\COMPTE_RENDU_VERIFICATION_ANTIVIRUS_M176.md` | `3274c0a8db14083e4d63a80cfe9ba77cc5c336ee9c2e28d7326e457cf0866ba2` |
| `m176sup\suite\run_suite_with_info.py` / `val_run_suite_v1.py` / `run_suite_once.py` (7.8) | `87fb8145db5ce3ce3316a1f7a6034e4118945c4210f8199bcf997f5aac4da3a3` / `8dd5fbd2bec024cc65b6418d67e222d0a764f3c50fa31c92477e517838e13c64` / `3c1592be1bc9fc1eb96587531002d48cffa9415eff6296ac757473ee043ddede` |
| `m176sup\suite_runs\suite_20261012_095323\verdict.json` | `43c6b2725e36f2096a4994efecef8ed811ac07b6804a147bdad745dc46b5b165` |
| `m176sup\suite_runs\suite_20261012_095323\supervised\stderr.txt` | `06a22f1e002d32190e164120f036cd9a1ef21ba94d331b3092d95e0a4737a002` |
| `m176sup\suite_runs\suite_20261012_095323\supervised\supervision.json` | `dc863bb97d98aea3bf08f8b0d1041689fc6888f334b1c82e2f6fd59f68ba4992` |
| `m176sup\scenario_launch_logs\suite_20261012_095323\meta.json` | `3732efac1fc94116e2fa9e328191a822d6966749d626dc2842cb05011c599c18` |
| `m176sup\RAPPORT_SUITE_COMPLETE_M176.md` (rapport historique, voir section 12) | `63ed18a43c7b6cf298fb4f2d50dab1c9aeecb6404f1db7ec73f88850078c733b` |

Sondes antérieures : sonde 1 (code réel 2, incident de montage : garde-fou refusant le cas C09 ; C01–C08 acceptés comme résultats partiels, C09–C18 non exécutés) ; sonde 2b (code réel 0, observations acceptées dans les limites du montage) ; premier prototype `probe3` (exécution non validée) ; prototype corrigé `probe3b` (code réel 0, 33 vérifications vraies, validé **dans son périmètre**, qui exclut l'intégration dans `ComfyUIEngine`, le cas de lien symbolique T11 non exercé, et dont les échecs sont injectés). Note de reprise hors dépôt : `m176audit\NOTE_REPRISE_M176.md`.

## 9. Limites

- **Validation locale partielle** : les résultats sont des pièces examinées pour l'état local, avec réserves ; ils ne valent pas, à eux seuls, décision de commit, de publication ou de clôture (décisions de l'architecte, section 13). La suite complète est `OK_NON_NET` et le module 4 non net, parce que la supervision est incomplète (inventaire 236/270 et 4/9 identifiés) ; un lancement chacun, stabilité non démontrée.
- Plateforme des observations : Windows 10, NTFS local, CPython 3.11.9 (consigné dans les processus de 7.2, 7.3, 7.4, 7.6 et 7.8 ; non consigné au premier lancement 7.1, voir l'introduction de la section 7). **Aucune exécution sous Python 3.10 n'a eu lieu.** Les tests simulant l'absence d'`add_note` **ont été exécutés** (sous CPython 3.11.x) : ils retirent la méthode de l'objet d'erreur, et **ne constituent pas** une exécution sous Python 3.10 ; la compatibilité 3.10 reste non vérifiée.
- Lien symbolique de fichier : non créable sans privilège, non exercé (aucune élévation). Périphériques, UNC, destinations extérieures : non testés.
- Échecs d'écriture, de fermeture et d'effacement : **injectés**, pas réels.
- Concurrence (remplacement du dossier ou de l'entrée entre la fermeture et l'effacement) : non garantie, non testée.
- Fréquence du déclencheur non mesurée ; compteur de ComfyUI = hypothèse amont.
- Le test de conséquence utilisateur n'est pas un test de bout en bout avec un vrai ComfyUI.
- Interruptions (`KeyboardInterrupt`, `SystemExit`…) : la conservation de l'erreur initiale ne concerne que les erreurs ordinaires couvertes ; aucun test n'injecte d'interruption.
- Flux alternatifs NTFS et collisions dossier/jonction : Windows seulement ; messages de log Qt non captés dans le test de conséquence utilisateur ; la protection contre une exception échappée d'un slot repose sur `sys.excepthook`.
- Comparaison avec l'ancienne production : limitée à 11 méthodes ; assertions non atteintes listées en 7.2 ; 21 tests du nouveau contrat non comparés.
- Supervision : un lancement par scénario ; échantillonnage (inventaire incomplet) ; équivalence des lancements supervisés (enveloppe, liste blanche d'environnement, job) avec un lancement direct non démontrée ; `threading.enumerate()` ne montre pas les threads natifs de Qt.
- Incident de protection du 2026-10-10 : cause non établie, issue du lancement du 2026-10-10 **inconnue**, étendue de l'exclusion inconnue (7.7).

## 10. Observations voisines et réserves historiques (hors périmètre, aucune sélectionnée)

E-1 (délai Ollama de 30 s), C-B (lecture des stockages), C-C (`-masklabel`/`-condlabel`), F-1, G-1, H-1 et les dérives documentaires de l'audit post-M175 restent **non sélectionnés et inchangés**. Les réserves historiques (M174 `0xC0000409` et écart au protocole ; incidents de M173 et antérieurs ; observations non résolues de M175 : exception Qt `setText(MagicMock)` — de nouveau observée aux exécutions 7.6 et 7.8 —, trois `DeprecationWarning` de `lora_page.py` — de nouveau observés —, quatre messages `taskkill` — de nombre identique observés en 7.8 —, différences de lanceur) **restent ouvertes** ; aucune n'est résolue par les résultats de cette mission. Les deux sorties `0xC0000409` de 7.8 ne sont pas rattachées à la réserve M174.

## 11. Fichiers du périmètre (quatre)

1. `src/engines/comfyui_engine.py` — production.
2. `tests/integration/test_comfyui_engine.py` — trois attentes de nom adaptées.
3. `tests/integration/test_comfyui_download_local_name.py` — nouveau.
4. `docs/missions/MISSION_176.md` — cette archive.

Forge, managers, interface, galerie, tri, dépendances et prérequis Python : **non modifiés** par cette mission. `CHANGELOG.md` et `docs/PROJECT_CONTEXT.md` n'étaient pas dans le périmètre du commit fonctionnel ; ils sont mis à jour, avec cette archive, par le commit documentaire distinct de régularisation post-publication (section 13).

## 12. Corrections d'archive et finalisation documentaire

- **Finalisation** : réécriture du 2026-10-12, après les exécutions, de l'archive rédigée avant elles. Les formulations devenues obsolètes (« non testées », « aucun test exécuté », « aucun test n'a tourné », « Tests préparés (non exécutés) ») ont été remplacées par les résultats de la section 7 avec leur provenance. Les sections 1, 2 et 4 sont reprises sans changement de fond.
- **Fins de ligne de la production** : l'ancienne version de ce document indiquait « 912 CRLF, 912 LF, aucun CR isolé » ; la mesure du 2026-10-12 sur le fichier à l'empreinte testée donne **919 CRLF, 919 LF, aucun CR isolé** (`i/lf w/crlf`). L'origine de l'écart n'est pas établie ; l'empreinte du fichier n'a pas changé depuis les exécutions.
- **Rapport historique erroné** : `RAPPORT_SUITE_COMPLETE_M176.md` (sha256 `63ed18a4…733b`) annonce « 3 659 lignes » mais décrit « 179 lignes qui ne se terminent pas par `... ok` » et « 25 lignes de continuation » : ce décompte comptait l'élément vide produit par la coupure après le dernier CRLF. **Correction (complément de lecture du 2026-10-12, fourni dans la session, sans fichier distinct, non reporté dans le rapport)** : 3 659 lignes réelles = 3 481 terminées par `... ok` + **178** autres, dont **24** lignes de continuation ou de pied de rapport. Le rapport n'a pas été modifié. Ce même complément a établi que le rattachement des PID 25916 et 19980 au test provoquant `os.abort()` n'est pas démontré (7.8) et a comparé les empreintes complètes (7.9).
- **Corrections de provenance (revue de l'architecte, 2026-10-12)** : (1) l'introduction de la section 7 affirmait que toutes les exécutions portaient sur les quatre fichiers aux empreintes indiquées et que CPython 3.11.9 était consigné partout ; elle distingue désormais les exécutions sur la production corrigée, le premier lancement (version de Python non consignée) et le comparatif sur la copie de l'ancienne production (dont les empreintes du dépôt réel ne décrivent pas le code exécuté) ; (2) la section 7.7 attribue désormais l'absence de modification de protection à Claude et la restauration du lanceur à l'utilisateur, l'état effectif de l'exclusion annoncée restant inconnu ; (3) la distinction entre tests simulant l'absence d'`add_note` (exécutés sous CPython 3.11.x) et exécution sous Python 3.10 (aucune) est reprise en 5 et 9. Le statut de la mission n'était pas modifié par cette correction.
- **Actualisation de statut (décision de l'architecte, 2026-10-12)** : les mentions de statut (bandeau, section 13) consignent « Revue pré-commit acceptée ; commit local autorisé avec réserves ; publication non autorisée ; mission non close ». Cette actualisation ne modifie ni les résultats, ni les réserves, ni les limites.
- **À la date de la finalisation et du commit fonctionnel**, rien d'autre n'avait été modifié dans le dépôt : production, tests, `CHANGELOG.md`, `docs/PROJECT_CONTEXT.md` et `graphify-out/` étaient inchangés.
- **Régularisation post-publication (2026-10-12, décision de l'architecte)** : après la publication manuelle de la Release par l'utilisateur et sa vérification directe, le bandeau et les sections 9, 11, 12 et 13 sont mis à jour pour consigner la publication du commit, du tag et de la Release et la clôture avec réserves ; `CHANGELOG.md` et `docs/PROJECT_CONTEXT.md` sont mis à jour dans le même commit documentaire. Les sections 1 à 8 (contrat, résultats, empreintes, provenance des preuves) et 10 sont reprises sans changement de fond. Production, tests, archives des autres missions et `graphify-out/` ne sont pas touchés ; aucun test n'est rejoué ; aucune réserve n'est résolue.
- **Références de tags relues (provenance)** : une affirmation d'un rapport de session selon laquelle les références du tag M173 ne figureraient pas dans `docs/missions/MISSION_174.md` était inexacte (cause probable, non vérifiée : la ligne 170 est très longue et l'outil de recherche en omet l'affichage ; conclusion tirée de cette sortie sans relecture de la ligne). Elles y figurent (section 11.A, ligne 170) et dans `docs/missions/MISSION_173.md` (lignes 94-95), avec des valeurs concordantes avec les audits de la section 13. Correction consignée hors dépôt (section 13.D) ; aucune archive M173 ou M174 n'est modifiée.

## 13. Références Git et publication

**Clôture** : Mission 176 **close avec réserves non résolues** (décision de l'architecte). Cette clôture ne résout aucune réserve technique ni historique, ne transforme pas `OK_NON_NET` en résultat net et ne modifie ni les limites de la section 9 ni les réserves de la section 10. Mission 177 non démarrée ; aucun candidat n'est sélectionné. Aucun identifiant du commit documentaire de régularisation n'est inscrit dans ce document ; Git fait autorité.

Les faits sont répartis selon leur provenance : (A) références relues pendant la régularisation, (B) opérations de publication rapportées et non rejouées, (C) Release, (D) pièces conservées hors dépôt. **Une référence relue aujourd'hui établit l'état actuel ; elle ne prouve pas le déroulement historique du push** (B).

**A. Références relues le 2026-10-12 (lecture actuelle, après `git fetch origin`, code 0)**

- **Commit fonctionnel** : `d97b03e8b12e073210be578d9d74c93c50c62a67` (`Give ComfyUI downloads independent local names`, trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`), parent `eff51b131202fbcf9bf132e83fde59dfc2044ae7` (`Document Mission 175 completion`), horodaté 2026-10-12 10:34:28 +03:00 (auteur et committer). Quatre fichiers, 1 457 ajouts et 15 suppressions (lus par `git show --numstat`) : `src/engines/comfyui_engine.py` +133/−9 ; `tests/integration/test_comfyui_engine.py` +16/−6 ; `tests/integration/test_comfyui_download_local_name.py` (neuf) +1101/−0 ; `docs/missions/MISSION_176.md` (neuf) +207/−0. Production et tests de l'arbre actuel sont ceux de ce commit.
- **Branche** : `HEAD`, `main`, `origin/main` et le `main` distant (`git ls-remote`) à `d97b03e8b12e073210be578d9d74c93c50c62a67` ; divergence `origin/main...main` 0/0 ; une seule branche distante ; index et stash vides ; arbre de travail propre hors les huit entrées historiques de `graphify-out/` (avant la présente régularisation).
- **Tag annoté** `v0.2-mission176` : type `tag`, objet `c936f44784ce93e5b961b28991196c488d7eadb1`, cible (commit) `d97b03e8b12e073210be578d9d74c93c50c62a67`, annotation « Mission 176: give ComfyUI downloads independent local names », horodaté 2026-10-12 10:41:47 +03:00 ; objet et cible identiques en local et par `git ls-remote origin` (référence et référence déréférencée `^{}`). Il est le seul tag qui désigne ce commit.
- **Tags historiques inchangés** (objet → cible, local = distant) : `v0.2-mission175` `60aef07a2d85719b57a3695511413d240c5069a7` → `fdf8f04810ae2701222f4d318691fc6a5a0cb226` ; `v0.2-mission174` `2525b2097878eca21d10835b991d64e1cf0d13de` → `fc8fe7486bd85cc274b3797e237a99a02b579899` ; `v0.2-mission173` `c3b9c1921ef2530ea06bdfbc9f481c8efa8ce7c8` → `b6c9688a409034df03aed37f00b96d0b988f7641`. Ces valeurs concordent avec celles consignées dans `docs/missions/MISSION_174.md` (section 11.A, ligne 170, pour M174 et M173) et `docs/missions/MISSION_173.md` (lignes 94-95).

**B. Opérations de publication rapportées (non rejouées par la régularisation)**

Source : sorties d'outils de la session de publication de Claude (journal de session) et pièces hors dépôt (D) ; elles ne sont pas reproduites aujourd'hui.

- **Audits avant publication** : un audit pré-push initial (`AUDIT_PREPUSH_M176.txt`) puis, après l'autorisation, un audit frais après `git fetch origin` (`AUDIT_PREPUBLICATION_M176.txt`, aucun écart) : `origin/main` et `main` distant à `eff51b131202fbcf9bf132e83fde59dfc2044ae7`, divergence 0/1, aucun commit distant absent de `main`, quatre blobs et statistiques conformes, index et stash vides, absence de `v0.2-mission176` et `v0.2-Mission176` en local et à distance, tags M173 à M175 inchangés.
- **Publication de `main`** : push normal, sans force, sortie `eff51b1..d97b03e  main -> main`, code 0 ; `git ls-remote` du `main` distant ensuite : `d97b03e8b12e073210be578d9d74c93c50c62a67`.
- **Tag** : création de `v0.2-mission176` (annoté) explicitement sur `d97b03e8b12e073210be578d9d74c93c50c62a67` avec l'annotation ci-dessus, type, objet et cible vérifiés ; push du seul `refs/tags/v0.2-mission176`, sortie `* [new tag]`, code 0.
- **Vérification finale** (`POSTPUBLICATION_M176.txt`, 2026-10-12 10:42:09) : références locales et distantes concordantes, divergence 0/0, tags M173 à M175 inchangés, index et stash vides, `v0.2-mission176` seul tag sur `HEAD`.
- Aucun `git push --force`, aucun déplacement ni aucune recréation de tag, aucune Release créée ni modifiée par Claude.

**C. GitHub Release**

- **Publication** : faite **manuellement par l'utilisateur** (confirmation de l'utilisateur relayée par l'architecte dans la session, après le rapport de publication). C'est la source de l'acte de publication ; ce qui suit est le constat direct de Claude.
- **Constat direct de Claude, 2026-10-12**, par lecture non authentifiée de l'API publique GitHub (`releases/tags/v0.2-mission176`, HTTP 200), sans modification : titre « v0.2-Mission176 — Give ComfyUI Downloads Independent Local Names » (identique au titre accepté), `tag_name` `v0.2-mission176`, `draft` `false`, `prerelease` `false`, `target_commitish` `main`, `created_at` `2026-10-12T07:41:47Z`, `published_at` `2026-10-12T07:43:49Z`, auteur `dominimada-wq`, aucun asset, identifiant 410329488, URL `https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission176`.
- **Corps** comparé au brouillon accepté (`release_m176_body.md`, 7 913 octets, sha256 `a6640a21455a82235247d9f6ebc81eed591c4831ec25f27f406e3e428ffc2c40`) : le corps publié fait 7 964 octets (sha256 `05d7f12fa53b0ffc9e832ca19c91ea81166b63a9011065c8143d8b35e242e558`) ; il est **identique octet pour octet après conversion CRLF→LF et ajout d'un unique retour à la ligne final** que le corps publié n'a pas. Écart de transport uniquement, aucune différence de contenu ; la Release n'est pas modifiée. Cette lecture est un constat daté : elle ne dit rien des états antérieurs de la Release ni de ses modifications ultérieures éventuelles.

**D. Pièces conservées hors dépôt** (non versionnées ; racine du dossier de travail de la session, section 8)

| Pièce | sha256 |
|---|---|
| `m176release\release_m176_title.txt` | `dad04b094dcecf874718c4ea508f346e528cad0a76e42330a0285641e96ee211` |
| `m176release\release_m176_body.md` | `a6640a21455a82235247d9f6ebc81eed591c4831ec25f27f406e3e428ffc2c40` |
| `m176release\AUDIT_PREPUSH_M176.txt` (audit initial) | `ccfd9df0a45ee2c377f03c1111ecd14bafe8fed22960dd1dbb8d1c58b34d6bc5` |
| `m176release\AUDIT_PREPUBLICATION_M176.txt` | `d7a0a094c0e61c87f20db8f5b926e46fb7f394d2ef7bfc790990604257b26591` |
| `m176release\POSTPUBLICATION_M176.txt` | `bc61569b08c5f73aefdc69f0e96eeaa817116aa150a27e9e258268dea2575fc0` |
| `m176release\COMPLEMENT_AUDIT_TAGS_M173_M174.txt` (conservé inchangé) | `5f3fecd38e595d42dbba769ba2f92ddb3f8ff6e3d7e082fd7a32a564cb192964` |
| `m176post\CORRECTION_COMPLEMENT_TAGS_M173_M174.txt` (correction du complément précédent) | `96d10e3114ac9ce0dc050cdbfa0ab1077d99e9aa3fd354db7423458b9027e230` |
| `m176post\RELEASE_VERIF_M176.txt` (constat direct de la Release) | `69286a29e5e058ad29a0a6c36a5e51a4bf1fcf295d89b1a7bfc12ef5bd130c1e` |
| `m176post\release_api.json` (réponse brute de l'API) | `ad3a6466652e407f03c9b078f98c123f99f9fc6d90674fbaaf1ee55f329d586a` |

Le complément d'audit des tags avait indiqué que les références du tag M173 ne figuraient pas dans `docs/missions/MISSION_174.md` ; la relecture de la section 11.A (ligne 170) a montré le contraire (section 12) ; le complément est conservé tel quel et corrigé par la pièce séparée ci-dessus.
