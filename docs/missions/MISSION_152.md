# Mission 152 — Harden LoRA Exposure Root Inspection

> **MISSION IMPLÉMENTÉE ET TESTÉE — clôture Git en attente.** `LoRALibraryManager.has_any_exposure()` (Mission 149) garantit qu'un `expose_root` Forge/ComfyUI ne peut pas être remplacé tant qu'une exposition Central LoRA Library connue y existe encore — mais elle s'appuie sur des primitives `pathlib` (`Path.is_dir()`, `Path.glob()`) dont la sémantique confond volontairement, par construction, un root réellement absent et un root temporairement inaccessible (permission refusée, média non prêt, erreur réseau) : les deux cas produisent aujourd'hui silencieusement `False`. Un mini-audit READ-ONLY ciblé, vérifié par lecture directe du code source `pathlib.py` de la version Python réellement utilisée par ce projet et par expérimentation locale reproduisant chaque scénario (ACL Windows réelles, drive letter inexistante, suppression concurrente), a confirmé que ce faux négatif réouvre exactement la classe de bug orphelin que Mission 149 devait fermer. M152 introduit un contrat à trois états (absence prouvée / inspection normale / inspection non concluante) et une exception métier dédiée pour le troisième état, sans jamais retourner `False` silencieusement dans ce cas. Voir §5 pour le contrat exact et §16-18 pour la matrice de tests prévue.

## 1. Root cause

`LoRALibraryManager.has_any_exposure(expose_root)` (`src/managers/lora_library_manager.py:749-797`) délègue entièrement à `_find_existing_alias(expose_root, lora_id)` (`:852-877`), qui teste `subfolder.is_dir()` puis `subfolder.glob(f"*__{lora_id}.*")`. Ces deux primitives `pathlib` avalent silencieusement plusieurs classes d'erreurs filesystem distinctes en les réduisant toutes à `False`/liste vide :

- `Path.is_dir()`/`Path.exists()` catchent tout `OSError` dont l'`errno` est `ENOENT`/`ENOTDIR`/`EBADF`/`ELOOP`, ou dont le `winerror` est `21` (`NOT_READY` — « drive exists but is not accessible », commentaire du code source Python lui-même), `123` ou `1921`, et retournent `False` sans jamais lever ;
- `Path.glob()` (`_WildcardSelector._select_from()`) enveloppe l'intégralité de son `scandir()` interne d'un `except PermissionError: return` — un `PermissionError` levé pendant l'énumération du dossier est donc **avalé silencieusement**, produisant une liste vide exactement comme un dossier réellement vide.

Un `OSError` non-`PermissionError` levé pendant le `scandir()` (ex. une erreur réseau lors de la déconnexion d'un partage en cours d'énumération) n'est en revanche catché par aucune de ces deux primitives et peut se propager tel quel — un second sous-problème distinct, voir §5 (État 3) et §7.

## 2. Conséquence réelle confirmée (séquence complète)

1. Un LoRA de la Central Library est exposé dans le root A (Forge ou ComfyUI).
2. Le root A devient temporairement inaccessible (média débranché, partage réseau hors ligne, ACL restreignant l'énumération).
3. L'utilisateur change la Setting du root correspondant de A vers B.
4. `has_any_exposure(A)` retourne `False` — faux négatif, alors qu'une exposition y existe réellement.
5. Le verrou Mission 149 ne se déclenche pas.
6. B est persisté normalement dans `ApplicationSettings` (aucune exception, chemin `changed`/`candidate`/`save()` complet).
7. Le même LoRA peut ensuite être exposé dans B — un nouveau hardlink y est créé.
8. Une suppression future de ce LoRA (`LoRAPage.delete_from_library()`) lit les chemins d'exposition **actuellement configurés** (B) et n'appelle `unexpose_from_forge()`/`unexpose_from_comfyui()` qu'avec B.
9. B est désexposé correctement.
10. L'ancien hardlink dans A n'est plus jamais mentionné ni retrouvé — aucune trace de A n'existe nulle part (ni Domain, ni Settings, ni log).
11. Le fichier canonique est supprimé de la Central Library — aucune exception, aucun `cleanup_failed` ne se déclenche (rien n'a « échoué » du point de vue du code).
12. Le hardlink dans A, partageant le même inode que le fichier canonique désormais supprimé, survit physiquement et reste utilisable par Forge/ComfyUI.

**Conclusion** : cette séquence réouvre exactement et intégralement la classe d'orphelin que Mission 149 avait pour objectif d'empêcher — la seule différence avec le bug pré-M149 est le déclencheur (inaccessibilité temporaire plutôt qu'un simple changement de Settings sans verrou).

## 3. Deux sous-problèmes distincts

**A. Faux négatif filesystem** — `has_any_exposure()` retourne `False` alors que l'état réel du root ne peut pas être établi avec confiance (root inaccessible, pas absent). **C'est le problème principal.** Classification : **CONFIRMED BUG**. Impact élevé relativement au périmètre M149 — l'invariant du verrou peut être contourné silencieusement, sans qu'aucune erreur n'apparaisse nulle part.

**B. Erreur filesystem explicite non traduite** — certains `OSError` (non-`PermissionError`, non catchés par `is_dir()`/`glob()`) peuvent aujourd'hui remonter bruts hors de `has_any_exposure()`, sans traduction métier ni gestion UI dédiée. Classification : **LATENT BUG**. Impact inférieur au faux négatif (pas de contournement silencieux du verrou — l'opération échoue au moins visiblement quelque part), mais même root cause conceptuelle : l'inspection du root n'a aujourd'hui aucun contrat explicite distinguant « absent » de « impossible à inspecter ». Un mini-audit dédié a par ailleurs vérifié empiriquement, avec le PySide6 réel de ce projet, qu'une exception non catchée dans un slot Qt n'aboutit **pas** à un crash du process (traceback stderr, exécution qui continue) — l'impact réel de B est donc une sauvegarde silencieusement sans effet plutôt qu'un crash.

M152 traite les deux sous-problèmes par un seul et même contrat (§5), puisqu'ils partagent la même racine : l'absence de distinction déterministe entre absence prouvée et inspection non concluante.

## 4. Non-régression impérative — ce qui doit rester autorisé

Les cas suivants doivent continuer à permettre le changement de root exactement comme aujourd'hui, sans jamais devenir un verrou :

- root non configuré (`""`/`None`) ;
- root réellement inexistant sur le disque (`ENOENT` — ex. un ancien chemin jamais recréé) ;
- sous-dossier `AIStudioToolkit/` réellement absent dans un root par ailleurs existant ;
- aucune exposition connue trouvée dans un root par ailleurs inspectable.

M152 ne doit jamais devenir un verrou empêchant un utilisateur de remplacer un ancien chemin qui n'existe véritablement plus (disque externe définitivement retiré, dossier réellement supprimé) — un tel verrou serait un regression de confort sans aucun bénéfice de sécurité, puisqu'un root prouvé absent ne peut par définition contenir aucune exposition.

## 5. Contrat à trois états (obligatoire)

**État 1 — root réellement absent.** Si l'absence est établie de manière fiable (équivalent de `ENOENT`) : conclusion `False`, comportement actuel préservé à l'identique, changement de root autorisé.

**État 2 — root inspectable.** Inspection normale et complète possible. Exposition connue trouvée → `True`, verrou Mission 149 inchangé, changement refusé. Aucune exposition connue trouvée → `False`, changement autorisé.

**État 3 — inspection non concluante.** Le système ne peut pas déterminer avec confiance si le root contient une exposition (permission refusée, média non prêt, erreur réseau, ou toute autre erreur d'inspection filesystem non assimilable à une absence certaine) : **ne jamais retourner `False` silencieusement**. L'opération doit échouer en mode fail-safe/fail-closed pour ce changement de Setting précis, en levant l'exception métier dédiée définie en §6.

Ce contrat sémantique est obligatoire ; l'implémentation exacte qui le réalise ne l'est pas (voir §10).

## 6. Exception métier dédiée — nom, emplacement et justification architecturale

**Nom retenu : `LoRAExposureRootInspectionError`**, cohérent avec la convention de nommage déjà en place (`LoRAExposureRootLockedError`, `LoRALibraryPathLockedError`) — le suffixe `InspectionError` la distingue sans ambiguïté de `LockedError` (qui signifie « une exposition connue a été effectivement trouvée »), alors que celle-ci signifie « l'état du root n'a pas pu être déterminé avec suffisamment de confiance ». Elle reste strictement distincte de `LoRAExposureRootLockedError`, `LoRALibraryPathLockedError`, `ApplicationSettingsStorageError`, et de toute exception `LoRALibraryError` générique d'expose/unexpose.

**Emplacement retenu : `src/managers/lora_library_manager.py`**, aux côtés de `LoRALibraryError` (`:33`) — **jamais** dans `src/managers/application_settings_manager.py`. Justification vérifiée par lecture directe des imports existants : `application_settings_manager.py` importe déjà `LoRALibraryManager` depuis `lora_library_manager.py` (`:9`). Si la nouvelle exception était définie dans `application_settings_manager.py`, la primitive d'inspection de `LoRALibraryManager` (qui doit la lever) devrait importer en retour depuis `application_settings_manager.py` — un import circulaire. La définir dans `lora_library_manager.py` évite structurellement ce problème et mirrore exactement le précédent déjà établi par Mission 149 elle-même : l'ambiguïté multi-alias de `_find_existing_alias()` lève déjà `LoRALibraryError` (défini dans ce même fichier) et la laisse remonter telle quelle à travers `has_any_exposure()` puis `ApplicationSettingsManager.update()`, qui ne la catche jamais (`MISSION_149.md` §4 : « `ApplicationSettingsManager.update()` ne catch pas cette exception non plus — elle remonte telle quelle »).

`application_settings_manager.py` importe `LoRAExposureRootInspectionError` en étendant sa ligne d'import existante (`from src.managers.lora_library_manager import LoRALibraryManager` devient `from src.managers.lora_library_manager import LoRALibraryManager, LoRAExposureRootInspectionError`), sans nouvelle dépendance de module.

## 7. Propagation exacte

```
inspection filesystem (LoRALibraryManager)
  → LoRAExposureRootInspectionError (levée, jamais avalée)
  → ApplicationSettingsManager.update() (ne catche pas, laisse propager — comme l'ambiguïté multi-alias déjà aujourd'hui)
  → SettingsPage.save_application_settings() (nouveau bloc/tuple except dédié)
  → QMessageBox.critical() avec un message métier propre, jamais une traceback ni un détail OS brut
  → self.update_application_settings() (resynchronisation UI, identique au pattern LoRAExposureRootLockedError existant)
```

Ne jamais transformer cette exception en `False`. Ne jamais persister la nouvelle Setting dans ce cas. Ne jamais modifier le Domain.

**Ambiguïté découverte pendant la vérification des imports (à traiter explicitement à l'implémentation)** : `SettingsPage.save_application_settings()` catche aujourd'hui exactement `(LoRALibraryPathLockedError, LoRAExposureRootLockedError)` et `ApplicationSettingsStorageError` (`settings_page.py:700-712`) — jamais `LoRALibraryError` brut. Aucun test existant (`test_settings_page.py`, `test_lora_library_roundtrip.py`) ne vérifie qu'un dialogue+resync se déclenche réellement pour `LoRAExposureRootLockedError` elle-même au niveau `SettingsPage` — seule la non-régression des 90 tests existants a été confirmée à l'implémentation de Mission 149 (`MISSION_149.md` §18), jamais un test dédié à ce comportement précis. Le test que M152 écrira pour `LoRAExposureRootInspectionError` (§18) sera donc le **premier** test de ce type dans le dépôt, pas le mirroir d'un test préexistant — à documenter comme tel dans le rapport d'implémentation, sans chercher à « retrouver » un test analogue qui n'existe pas.

## 8. Atomicité Settings

Doit rester strictement identique au contrat déjà vérifié pour `LoRAExposureRootLockedError` : les contrôles d'inspection doivent continuer à s'exécuter avant toute construction du `candidate` (`application_settings_manager.py:205`) et avant tout appel à `ApplicationSettingsStorage.save()`. En cas d'inspection non concluante : `self._settings` reste strictement inchangé, `ApplicationSettingsStorage.save()` n'est jamais appelé, aucun état Domain n'est partiellement muté, aucun changement de root n'a lieu, et l'UI est resynchronisée sur la valeur réellement persistée (jamais la valeur refusée laissée affichée).

## 9. Indépendance Forge / ComfyUI

Préservée exactement comme Mission 149 l'a établie : une inspection non concluante du root Forge ne doit affecter que le champ Forge (`forge_lora_expose_path`) ; une inspection non concluante du root ComfyUI ne doit affecter que le champ ComfyUI. Aucun verrou global commun aux deux providers. Un `update()` combiné modifiant les deux champs dans le même appel reste refusé dans son ensemble si l'un des deux lève `LoRAExposureRootInspectionError` (même règle « tout ou rien » déjà en vigueur pour `LoRAExposureRootLockedError`/`LoRALibraryPathLockedError`, héritée sans modification). Le même-valeur (no-op) reste toujours autorisé, quel que soit l'état d'inspection du root — la garde n'est évaluée que si le champ change réellement (`forge_lora_expose_path_changed`/`comfyui_lora_expose_path_changed`, calculés exactement comme aujourd'hui).

## 10. Portée de la correction dans `LoRALibraryManager` — implémentation non imposée

Le contrat obligatoire est purement sémantique (§5) : distinguer de manière déterministe une absence certaine d'une inspection non concluante. Le mini-audit préalable a identifié que `os.stat()`/`os.scandir()` avec inspection d'`errno`/`winerror` est probablement la voie la plus directe, mais **cette implémentation n'est pas imposée** — si une relecture du code à l'implémentation révèle une solution plus petite et tout aussi fiable, elle doit être préférée.

Contrainte de scope ferme : la correction doit rester centrée sur le besoin read-only de `has_any_exposure()`. **`_find_existing_alias()` ne doit pas être modifiée** si ce changement affecterait aussi `_expose()`/`_unexpose()`/`delete()` sans nécessité réelle — ces trois mécanismes restent hors périmètre de M152 (exactement comme ils l'étaient déjà hors périmètre de M149, `MISSION_149.md` §10/§14). La voie recommandée est une **primitive d'inspection dédiée**, utilisée exclusivement par `has_any_exposure()`, laissant `_find_existing_alias()` et son comportement `pathlib` actuel strictement inchangés pour tous ses autres appelants.

## 11. Portabilité errno/winerror

Toute utilisation d'`errno`/`winerror` doit rester portable autant que raisonnablement possible :
- ne jamais supposer que l'attribut `winerror` existe sur toutes les plateformes (il n'existe que sur Windows — sur une autre plateforme, `getattr(exc, "winerror", None)` retourne `None` sans lever) ;
- utiliser `errno` (`e.errno`) lorsqu'il suffit à distinguer les cas — `errno.ENOENT` est portable et suffit à lui seul pour l'État 1 ;
- ne consulter les informations `winerror` que lorsqu'elles existent réellement, jamais comme condition unique bloquant le fonctionnement sur une plateforme qui ne les fournit pas.

Rappel : ce projet est actuellement Windows-only par contrainte technique établie (`CLAUDE.md`), mais rien dans cette mission ne doit introduire une dépendance à `winerror` qui romprait silencieusement sur une autre plateforme si le projet venait à y être un jour exécuté.

## 12. Relation avec Mission 149 — M152 ne la remplace pas

M149 reste entièrement correcte et inchangée dans son contrat lorsque le filesystem est normalement inspectable (États 1 et 2 du §5) — c'est le cas immense majorité du temps. M152 renforce uniquement la frontière précise où M149 ne pouvait pas établir de manière fiable l'état réel du root (État 3) — elle ne redéfinit ni le verrou lui-même, ni son message, ni son exception (`LoRAExposureRootLockedError` reste inchangée), ni la logique d'indépendance Forge/ComfyUI déjà établie. Les 20 tests M149 existants doivent rester verts sans modification.

## 13. Relation avec Mission 135 — inchangée

M135 (`_expose()`/`_unexpose()`/`delete_from_library()`) n'est ni modifiée ni concernée par M152 — la suppression continue de désexposer les roots **actuellement configurés** avant la suppression canonique, exactement comme avant. M152 agit exclusivement en amont, au moment du changement de Settings, pour empêcher qu'un changement de root dont l'état réel n'a pas pu être établi avec confiance fasse perdre la capacité de retrouver un ancien alias — elle ne change rien à ce qui se passe une fois qu'un root a effectivement et sûrement été libéré.

## 14. Non-goals (exclusions confirmées)

Persistance des chemins d'exposition ; registre des anciens roots ; migration automatique ; récupération des hardlinks déjà orphelins avant cette mission ; scan des anciens roots ; suppression LoRA pendant une génération active ; refonte de la Central LoRA Library ; changement de schéma/Domain ; correction générique d'`ApplicationSettingsStorageError` (finding distinct, non fusionné — voir le mini-audit préalable §16) ; New/Open Project vs génération Inference active (Mission 085, NON-ISSUE reconfirmé) ; Character deletion ; OneTrainer (containment/reconciliation) ; Training cleanup ; Forge timeout ; toute nouvelle politique de retry filesystem.

## 15. Fichiers attendus (scope vérifié par lecture directe des imports/tests existants)

Production :
- `src/managers/lora_library_manager.py` — nouvelle exception `LoRAExposureRootInspectionError` (aux côtés de `LoRALibraryError`), nouvelle primitive d'inspection dédiée utilisée exclusivement par `has_any_exposure()`. `_find_existing_alias()`/`_expose()`/`_unexpose()`/`delete()` non modifiées sans nécessité démontrée.
- `src/managers/application_settings_manager.py` — extension de la ligne d'import existante (`from src.managers.lora_library_manager import LoRALibraryManager` → ajoute `LoRAExposureRootInspectionError`). Aucune nouvelle garde structurelle : la propagation reste implicite (non catchée), exactement comme l'ambiguïté multi-alias aujourd'hui.
- `src/ui/pages/settings_page.py` — nouvel import depuis `src.managers.lora_library_manager` (première importation depuis ce module dans ce fichier, confirmé par lecture directe — aujourd'hui `settings_page.py` n'importe que depuis `application_settings_manager.py`, `settings_page.py:46-49`), extension du tuple `except` existant (ou bloc dédié), même corps que le bloc `LoRAExposureRootLockedError` actuel.

Tests (emplacements vérifiés par lecture directe des imports existants) :
- `tests/integration/test_lora_library_roundtrip.py` — déjà le fichier hébergeant `LoRALibraryManagerHasAnyExposureTest` et `ApplicationSettingsExposureRootLockTest` (Mission 149, même raison structurelle que pour cette mission : `ApplicationSettingsManager` y est testé avec un vrai `LoRALibraryManager` injecté). Nouveaux tests de la primitive d'inspection et du verrou Forge/ComfyUI en État 3 à y ajouter, sur le modèle de ces deux classes existantes.
- `tests/integration/test_settings_page.py` — pour le test UI (dialogue + resync). **Vérifié par lecture directe : ce fichier ne contient aujourd'hui aucun test de `LoRAExposureRootLockedError`/`LoRALibraryPathLockedError` au niveau `SettingsPage`** (voir l'ambiguïté documentée en §7) — le nouveau test sera donc autonome, sans mirroir préexistant exact à reproduire, seulement le pattern général déjà utilisé par les autres blocs `except` de cette méthode.

Documentation :
- `docs/missions/MISSION_152.md` (ce document).

Si l'implémentation démontre qu'un autre fichier de production est réellement nécessaire, ce point doit être signalé et justifié avant toute modification — jamais ajouté silencieusement au périmètre.

## 16. Matrice de tests — `LoRALibraryManager` (déterministe, mocks/fakes uniquement)

1. Root réellement absent (équivalent `ENOENT` simulé) → `has_any_exposure()` retourne `False`, comportement M149 inchangé.
2. Exposition connue trouvée dans un root inspectable → `True`, comportement M149 inchangé.
3. Aucune exposition connue dans un root inspectable → `False`, comportement M149 inchangé.
4. `PermissionError` simulée pendant l'inspection → `LoRAExposureRootInspectionError` levée, jamais `False`.
5. `OSError` générique simulée pendant l'inspection → `LoRAExposureRootInspectionError` levée.
6. Média `NOT_READY`/équivalent simulé de façon portable et déterministe (mock d'un `OSError` avec l'attribut `winerror` correspondant, jamais une manipulation réelle de disque) → `LoRAExposureRootInspectionError` levée.
7. Ambiguïté multi-alias (comportement M149 existant) → inchangée, continue de lever `LoRALibraryError`, jamais convertie en `LoRAExposureRootInspectionError` ni en `True`/`False`.

Aucune manipulation réelle d'ACL Windows n'est requise — tous les cas ci-dessus sont simulables par `unittest.mock.patch` avec `side_effect` sur la primitive d'inspection retenue à l'implémentation.

## 17. Matrice de tests — `ApplicationSettingsManager`

Pour Forge et pour ComfyUI, indépendamment (mirroir de la structure `ApplicationSettingsExposureRootLockTest` déjà existante) :
8. Inspection non concluante lors d'un changement réel de root → `LoRAExposureRootInspectionError` propagée hors de `update()`.
9. `self._settings` inchangé après cette exception.
10. `ApplicationSettingsStorage.save()` jamais appelé dans ce cas (assertion `assert_not_called()` sur un mock/spy).
11. Même valeur resoumise (no-op) reste toujours acceptée, quel que soit l'état d'inspection simulé du root.
12. Une inspection non concluante sur Forge n'affecte jamais le champ ComfyUI, et réciproquement.
13. Un `update()` combiné (Forge + ComfyUI, ou Forge + un autre champ non lié) refusé sur une inspection non concluante ne persiste aucun des champs de l'appel, y compris ceux qui auraient été acceptés isolément.

Non-régression stricte à rejouer sans modification : les 11 tests existants de `ApplicationSettingsExposureRootLockTest` (lock si exposition connue, no-op, réouverture après unexpose, indépendance des deux providers, atomicité d'un update combiné refusé, absence de verrou sans `lora_library_manager` injecté).

## 18. Matrice de tests — `SettingsPage`

14. `LoRAExposureRootInspectionError` levée par `application_settings_manager.update()` → captée par `save_application_settings()`, jamais laissée s'échapper comme traceback Qt.
15. Un `QMessageBox.critical()` est affiché avec un message métier compréhensible, sans traceback ni détail OS brut (`str(exc)` ne doit jamais contenir de représentation de l'`OSError` original si celui-ci expose un chemin/errno technique — le message de `LoRAExposureRootInspectionError` doit être rédigé en français clair, sur le modèle des messages déjà rédigés pour `LoRAExposureRootLockedError`).
16. `self.update_application_settings()` est appelée (resynchronisation UI), identique au pattern déjà en place pour `LoRAExposureRootLockedError`.
17. Aucune persistance supplémentaire ne se produit (mock de `ApplicationSettingsManager.update()` levant l'exception ; `ApplicationSettingsStorage.save()` jamais atteint).

Comme noté en §7, ces 4 tests seront les premiers de ce type dans `test_settings_page.py` — aucun test existant à mirrorer exactement pour `LoRAExposureRootLockedError` elle-même.

## 19. Tests de non-régression requis

Les 20 tests M149 existants (`LoRALibraryManagerHasAnyExposureTest` + `ApplicationSettingsExposureRootLockTest`) doivent rester verts sans modification. Les tests M135 pertinents (`LoRALibraryManagerComfyUIExposureTest`, `LoRALibraryManagerForgeExposureTest`, tests de `delete_from_library()`) doivent rester verts sans modification — `_expose()`/`_unexpose()`/`delete()` ne sont pas touchées par cette mission. `test_settings_page.py` (90 tests existants) doit rester vert au complet. Suite complète : 2877 (baseline post-M151) + tests nets ajoutés par M152, à confirmer exactement à l'implémentation.

## 20. Critères de réussite

1. Un root réellement absent reste autorisé au changement.
2. Un root inspectable sans exposition connue reste autorisé au changement.
3. Une exposition connue reste verrouillée exactement comme Mission 149 l'établit déjà.
4. Une inspection non concluante ne produit jamais `False` silencieusement.
5. Une inspection non concluante lève `LoRAExposureRootInspectionError`.
6. Aucune nouvelle Setting n'est persistée dans ce cas.
7. Le Domain reste inchangé dans ce cas.
8. `SettingsPage` affiche une erreur métier propre, jamais une traceback.
9. L'UI est resynchronisée sur la valeur réellement persistée.
10. Forge et ComfyUI restent verrouillés indépendamment.
11. Mission 149 reste fonctionnellement intacte (20 tests existants verts, aucune modification de son contrat pour les États 1/2).
12. Mission 135 reste intacte (aucune modification de `_expose()`/`_unexpose()`/`delete()`).
13. Aucun mécanisme de persistance/migration/registre historique n'est ajouté.
14. Suite complète verte (baseline 2877 + tests nets ajoutés par M152).

## 21. Baseline et cadre de rédaction

Baseline avant M152 : **2877/2877** (aucune modification fonctionnelle depuis Mission 151 — le commit `199b62cd4996921e467e649275c02afd1b6d5d13` est purement documentaire, régularisant le contrat Mission 085 après le mini-audit New/Open Project). Cette mission a été rédigée après deux mini-audits READ-ONLY successifs, validés par l'architecte : le premier sur New/Open Project vs génération Inference active (reclassé NON-ISSUE), le second sur la robustesse filesystem du verrou d'exposition LoRA introduit par Mission 149 (candidat retenu, à l'origine de cette mission).

## 22. Vérifications de qualité (avant de considérer l'implémentation terminée)

- Confirmer que `_find_existing_alias()` n'a reçu aucune modification, sauf nécessité démontrée et signalée explicitement avant tout changement.
- Confirmer que `_expose()`/`_unexpose()`/`delete()`/`delete_from_library()` restent octet pour octet inchangées.
- Confirmer que les deux contrôles Forge/ComfyUI dans `ApplicationSettingsManager.update()` continuent de s'exécuter avant toute construction du `candidate` et tout appel à `ApplicationSettingsStorage.save()`.
- Confirmer qu'un `update()` combiné refusé sur une inspection non concluante ne persiste et ne mute strictement rien, y compris les champs non concernés par cette garde précise.
- Confirmer que `LoRAExposureRootInspectionError` est définie dans `src/managers/lora_library_manager.py`, jamais dans `application_settings_manager.py` (voir §6 pour la justification anti-import-circulaire).
- Confirmer qu'aucun usage de `winerror` ne suppose sa présence sur une plateforme où il n'existe pas.
- Confirmer qu'aucun fichier hors de la liste du §15 n'a été modifié.
- Confirmer que les 20 tests M149 et les tests M135 pertinents repassent sans aucune modification de leur code.

## 23. Résultats réels (implémentation)

**Implémentation retenue** : plus petite que la voie `errno`/`winerror` explicitement anticipée par le draft — repose exclusivement sur les sous-classes `OSError` déjà mappées portablement par CPython depuis Python 3.3 (PEP 3151) : `FileNotFoundError` et `NotADirectoryError` signifient une absence prouvée, tout autre `OSError` (dont `PermissionError`) signifie une inspection non concluante. Aucun code n'inspecte `errno`/`winerror` directement — la distinction se fait uniquement par type d'exception, ce qui est déjà portable par construction sans aucune table de correspondance à maintenir.

**`LoRAExposureRootInspectionError`** : définie dans `src/managers/lora_library_manager.py`, juste après `LoRALibraryError` — jamais dans `application_settings_manager.py`, conformément à la justification anti-import-circulaire du §6. `application_settings_manager.py` étend sa ligne d'import existante pour l'inclure, sans jamais la catcher (propagation implicite, comme l'ambiguïté multi-alias déjà existante).

**Comportement par cas, vérifié par expérimentation locale puis par test** :
- `ENOENT` (root/sous-dossier réellement absent, y compris drive letter inexistante ou parent manquant) → `FileNotFoundError` → traité comme absence, `has_any_exposure()` retourne `False`.
- `ENOTDIR` (un composant du chemin est un fichier, pas un dossier — ex. `AIStudioToolkit` existant comme fichier) → `NotADirectoryError` → également traité comme absence, `False` (comportement `pathlib` historique préservé à l'identique).
- `PermissionError` (ACL refusant l'énumération) → `LoRAExposureRootInspectionError` levée — jamais avalée silencieusement, contrairement à `Path.glob()`.
- `OSError` générique (ex. erreur réseau simulée) → `LoRAExposureRootInspectionError` levée.
- `NOT_READY`/équivalent Windows (simulé via un `OSError` portant l'attribut `winerror=21`, jamais un vrai volume déconnecté) → `LoRAExposureRootInspectionError` levée — non spécial-casé comme une absence, conformément au contrat.

**`has_any_exposure()`** : ne délègue plus à `_find_existing_alias()` — construit désormais son propre listing via la nouvelle primitive statique `_list_expose_subfolder(subfolder)` (un seul `os.scandir()` par appel), puis matche chaque `lora_id` connu avec `fnmatch.fnmatch(name, f"*__{lora_id}.*")`, reproduisant exactement la sémantique de motif de `Path.glob()`. Le court-circuit sur bibliothèque vide (`if not self._loras: return False`) évite tout accès filesystem quand il n'y a rien à chercher. L'ambiguïté multi-alias (plus d'un match pour un même `lora_id`) continue de lever `LoRALibraryError`, inchangée. `_find_existing_alias()`, `_expose()`, `_unexpose()`, `delete()` confirmés octet pour octet inchangés par lecture directe du diff (aucun hunk ne les touche).

**`ApplicationSettingsManager`** : aucun changement structurel dans `update()` — seule la ligne d'import est étendue. Les deux gardes Forge/ComfyUI continuent de s'exécuter avant toute construction du `candidate`/tout `save()` ; une `LoRAExposureRootInspectionError` s'y comporte exactement comme le faisait déjà l'ambiguïté `LoRALibraryError` : propagation immédiate, aucune mutation.

**`SettingsPage`** : nouvel import direct depuis `src.managers.lora_library_manager` (première importation depuis ce module dans ce fichier). Le tuple `except (LoRALibraryPathLockedError, LoRAExposureRootLockedError)` devient `except (LoRALibraryPathLockedError, LoRAExposureRootLockedError, LoRAExposureRootInspectionError)`, corps strictement inchangé (`QMessageBox.critical` + `self.update_application_settings()`). Le bloc `except ApplicationSettingsStorageError` n'a reçu aucune modification.

**Fichiers réellement modifiés** — strictement les 5 fichiers annoncés au §15, aucun autre :
- `src/managers/lora_library_manager.py` : +134/-8 en 4 hunks (import `fnmatch`, nouvelle exception, `has_any_exposure()` réécrite, nouvelle méthode statique `_list_expose_subfolder()`).
- `src/managers/application_settings_manager.py` : +4/-1 (extension de l'import en bloc parenthésé).
- `src/ui/pages/settings_page.py` : +12/-7 (nouvel import, tuple `except` étendu sur plusieurs lignes, commentaire mis à jour).
- `tests/integration/test_lora_library_roundtrip.py` : +171/-1 (import étendu, 6 nouveaux tests dans `LoRALibraryManagerHasAnyExposureTest`, 5 nouveaux tests dans `ApplicationSettingsExposureRootLockTest`).
- `tests/integration/test_settings_page.py` : +93/-1 (import ajouté, 4 nouveaux tests dans `SettingsPageSaveErrorTest`).

**Tests ajoutés — 14 tests nets** (2877 → 2891 tests collectés) :
- `LoRALibraryManagerHasAnyExposureTest` (+5) : bibliothèque vide ne touche jamais le filesystem, `PermissionError` lève l'exception, `OSError` générique lève l'exception, `NOT_READY` simulé lève l'exception, le message de l'exception ne contient aucune trace de traceback et cite le chemin concerné.
- `ApplicationSettingsExposureRootLockTest` (+5) : inspection non concluante Forge propagée sans mutation, inspection non concluante ComfyUI propagée sans mutation, une erreur d'inspection Forge n'affecte jamais ComfyUI, une resoumission de la même valeur reste un no-op même si l'inspection échouerait, un `update()` combiné refusé sur une inspection non concluante ne persiste aucun champ de l'appel.
- `SettingsPageSaveErrorTest` (+4) : l'exception est captée et affiche un `QMessageBox.critical` avec le message exact, le champ est resynchronisé sur la valeur réellement persistée, aucune persistance supplémentaire ne se produit, la page reste pleinement réutilisable pour une sauvegarde réelle après l'échec simulé.

**Résultats ciblés** :
- `LoRALibraryManagerHasAnyExposureTest` + `ApplicationSettingsExposureRootLockTest` : **30/30 passés** (0.718s) — 20 tests M149 préexistants + 10 nouveaux, tous verts.
- `tests/integration/test_lora_library_roundtrip.py` complet : **127/127 passés** (2.532s).
- `tests/integration/test_settings_page.py` complet : **94/94 passés** (2.255s) — 90 préexistants + 4 nouveaux.

**Résultats voisins (M135/M149, non-régression)** :
- `tests/integration/test_lora_roundtrip.py` (Workbench LoRA, non modifié) : **275/275 passés** (15.852s).
- `LoRALibraryManagerComfyUIExposureTest`/`LoRALibraryManagerForgeExposureTest`/tests de `delete_from_library()` (M135, dans `test_lora_library_roundtrip.py`) : rejoués tels quels dans le run complet du fichier ci-dessus, tous verts, aucune modification de leur code.

**20 tests Mission 149** : tous verts sans aucune modification de leur code (inclus dans les 30/30 ci-dessus).

**Résultat suite complète** : **2891/2891 collectés/passés, 0 échoué**, exit 0, 320.224s. Équation : 2877 (baseline post-M151) + 14 nets ajoutés par Mission 152 = **2891**, cohérent. Les lignes `Failed to copy .../disk full/...` et le traceback bénin `QLabel.setText(MagicMock)` interlignés dans la sortie sont des logs/anomalies attendus déjà documentés (tests d'échec simulé et non-régression Inference préexistante), sans aucun rapport avec le périmètre M152.

**`git diff --check`** : clean, exit 0 (avertissements `LF will be replaced by CRLF` uniquement, non bloquants).

**Écarts par rapport au draft** : un seul, explicitement anticipé par le draft lui-même (§10 : « cette implémentation n'est pas imposée ») — l'usage direct d'`errno`/`winerror` a été remplacé par une distinction fondée uniquement sur le type d'exception (`FileNotFoundError`/`NotADirectoryError` vs tout autre `OSError`), plus petite, plus lisible, et déjà portable par construction. Aucun autre écart de scope, de contrat ou de fichier.

**Dettes découvertes mais non corrigées (hors périmètre M152, documentées pour mémoire)** : aucune nouvelle dette découverte pendant cette implémentation — l'ambiguïté déjà documentée au §7 (absence de test préexistant pour `LoRAExposureRootLockedError` au niveau `SettingsPage`) a été traitée comme prévu, sans élargissement de scope. `ApplicationSettingsStorageError` et son absence de resynchronisation restent explicitement non touchées, conformément à l'instruction.

**Rappel explicite** : la clôture Git (commit/tag/Release) n'a pas été effectuée à ce stade — en attente de validation.
