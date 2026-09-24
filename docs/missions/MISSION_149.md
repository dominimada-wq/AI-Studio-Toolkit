# Mission 149 — Guard LoRA Exposure Root Changes While Exposed

> **MISSION CLÔTURÉE — commit, tag et GitHub Release publiés.** La Central LoRA Library expose des LoRA vers Forge/ComfyUI par hardlink NTFS, retrouvé uniquement par un scan live de `lora_id` dans le `expose_root` **passé en argument à l'appel** — aucune trace de l'exposition n'est jamais persistée. Rien n'empêchait jusqu'ici de changer librement `forge_lora_expose_path`/`comfyui_lora_expose_path` dans Settings pendant qu'une exposition existe encore dans l'ancien root : cette exposition devenait alors invisible à toute opération future, y compris à la suppression M135, qui ne désexpose que depuis le root **courant** — le hardlink de l'ancien root survivait alors physiquement à une suppression que le Toolkit annonçait pourtant comme réussie. M149 corrige ceci **prospectivement**, sans persistance nouvelle : un `expose_root` ne peut désormais plus être remplacé tant qu'au moins une exposition Toolkit identifiable y existe encore (`LoRALibraryManager.has_any_exposure()` + `LoRAExposureRootLockedError` dans `ApplicationSettingsManager.update()`). Voir §12 pour la portée exacte (aucune récupération des orphelins déjà créés avant cette mission), §18 pour le détail complet des résultats réels et §19 pour la clôture Git.

## 1. Root cause

`LoRALibraryManager._expose()`/`_unexpose()` (`src/managers/lora_library_manager.py:569-786`) localisent une exposition exclusivement via `_find_existing_alias(expose_root, lora_id)` (`:802-827`), un glob `<expose_root>/AIStudioToolkit/*__<lora_id>.*` — calculé à chaque appel à partir du seul `expose_root` fourni par l'appelant, jamais d'une valeur persistée. Aucun champ lié à l'exposition n'existe sur le Domain `LoRA` (`src/domain/lora.py`) ni dans `LoRALibraryStorage` (`{"loras": [...]}` uniquement, confirmé par lecture directe). `ApplicationSettingsManager.update()` (`src/managers/application_settings_manager.py`) ne verrouille aujourd'hui que `lora_library_path` (`LoRALibraryPathLockedError`, tant que le registre contient au moins une entrée) — `forge_lora_expose_path`/`comfyui_lora_expose_path` sont librement modifiables à tout moment, sans validation, sans verrou, avec hot-reload immédiat (confirmé par le commentaire de test existant, `tests/integration/test_application_settings_roundtrip.py:685-689` : « No lock of any kind (unlike `lora_library_path`) — this field is freely changeable at any time »).

Séquence exacte du bug (établie par le mini-audit architectural précédent, validée par ChatGPT — non redémontrée ici) :

1. LoRA central exposé vers Forge (ou ComfyUI) dans `expose_root = A` → hardlink créé dans `A/AIStudioToolkit/`.
2. L'utilisateur change le chemin d'exposition correspondant vers `B` dans Settings — aucune validation, effet immédiat.
3. Le même LoRA est éventuellement ré-exposé vers le même moteur : `_find_existing_alias(B, lora_id)` ne cherche que dans `B`, ne trouve rien, crée un **nouveau** hardlink dans `B` — l'ancien hardlink de `A` n'est ni détecté, ni touché, ni supprimé.
4. L'utilisateur supprime le LoRA depuis la Central Library : `lora_page.py::delete_from_library()` lit `forge_lora_expose_path`/`comfyui_lora_expose_path` **en direct depuis Settings au moment du clic** (valeur = `B`) et n'appelle `unexpose_from_forge()`/`unexpose_from_comfyui()` qu'avec `B`.
5. `_unexpose(lora, B)` retire le hardlink de `B` — le hardlink de `A` n'est jamais mentionné.
6. La suppression canonique procède normalement (aucune exception levée — un `_unexpose` qui ne trouve rien retourne silencieusement `False`, jamais une erreur).
7. Le canonical LoRA est supprimé — mais un hardlink partage l'inode avec le fichier canonique : le hardlink de `A` conserve physiquement les données et reste utilisable par Forge/ComfyUI.
8. Le Toolkit annonce pourtant la suppression comme réussie (aucun `cleanup_failed`/`unexpose_failures` ne se déclenche pour ce cas, puisque rien n'a échoué du point de vue du code — l'ancien root est simplement invisible).

## 2. Décision architecturale retenue (Option C)

Explicitement écarté par la décision de l'architecte/ChatGPT :
- persistance des chemins d'exposition exacts (Option A) ;
- registre d'exposition séparé (Option B) ;
- migration automatique lors d'un changement de Settings (Option D) ;
- toute modification du Domain `LoRA` ou de `LoRALibraryStorage`.

**Contrat retenu :** un `expose_root` (Forge ou ComfyUI, indépendamment) ne peut pas être remplacé par une valeur réellement différente tant qu'au moins une exposition Toolkit appartenant à la Central Library existe encore, de manière identifiable, dans le root **actuellement configuré** pour ce provider. Le changement redevient autorisé dès que ces expositions ont été retirées (bouton d'exposition existant en re-cliquant sur « Exposer » ne les retire jamais — retrait via suppression du LoRA, ou tout futur mécanisme de désexposition manuelle, hors périmètre ici). Aucune migration, aucun déplacement automatique, aucune tentative de reconstruction des expositions passées.

## 3. Indépendance Forge / ComfyUI

Les deux providers sont verrouillés **indépendamment**, exactement comme deux champs distincts le seraient — pas de verrou global partagé :
- Forge exposé en `A`, ComfyUI exposé en `C` → tentative `Forge A → Forge B` refusée (verrou Forge uniquement) ; le Setting ComfyUI (`C`) n'est ni lu, ni modifié, ni affecté par ce refus.
- Symétriquement, `ComfyUI C → ComfyUI D` alors que Forge est exposé en `A` reste refusée uniquement si **ComfyUI** a lui-même une exposition active en `C` — la présence d'une exposition Forge n'a strictement aucune influence sur le verrou ComfyUI, et réciproquement.
- Un changement des deux champs dans le même appel `update()` (cas réel : `SettingsPage.save_application_settings()` transmet tous les champs en un seul appel) est évalué champ par champ : si Forge est verrouillé mais pas ComfyUI, l'appel entier est refusé (comportement déjà établi par `lora_library_path` — un seul champ verrouillé bloque l'ensemble de l'appel groupé, aucune mutation partielle n'est jamais persistée) et **aucun** des deux champs n'est modifié, y compris celui qui aurait pu être accepté isolément. Ce comportement "tout ou rien" par appel groupé est celui déjà en vigueur pour tous les champs de `update()` (une seule levée d'exception avant toute construction du candidat) — M149 ne l'introduit pas, il en hérite.

## 4. `has_any_exposure()` — contrat exact

Nouvelle méthode publique sur `LoRALibraryManager` :

```python
def has_any_exposure(self, expose_root) -> bool:
```

- **Read-only filesystem, sans mutation, sans création de dossier, déterministe** — ne crée jamais `<expose_root>/AIStudioToolkit/`, ne modifie jamais la registry, ne modifie jamais le filesystem.
- Réutilise exactement la convention d'identification déjà en place — `_find_existing_alias(expose_root, lora_id)` (`:802-827`), jamais un second format. Implémentation : itère sur `self._loras` (les LoRA **actuellement connus** de la Central Library) et retourne `True` dès que `_find_existing_alias(expose_root, lora.lora_id)` renvoie un match non-`None` pour l'un d'eux (court-circuit dès le premier trouvé, pas besoin de tout scanner) ; `False` si aucun des LoRA connus n'a d'alias dans ce root.
- **Un fichier étranger** dans `AIStudioToolkit/` (résidu historique, fichier non rattachable à un `lora_id` connu) **ne bloque jamais** — `_find_existing_alias` ne matche que le motif exact `*__<lora_id>.*` pour un `lora_id` réellement présent dans `self._loras` ; tout le reste est ignoré par construction, sans logique d'exclusion supplémentaire à écrire.
- **Un alias correspondant à un `lora_id` inconnu de la bibliothèque courante** (LoRA déjà supprimé depuis, ou alias d'une autre installation) **ne bloque jamais**, pour la même raison : la boucle ne teste que les `lora_id` réellement présents dans `self._loras` au moment de l'appel.
- **Root vide/non configuré** (`not expose_root`), **root inexistant** (`expose_root.is_dir()` faux), **dossier `AIStudioToolkit/` absent**, ou **bibliothèque vide** (`self._loras == []`) → `False` dans tous les cas, sans lever d'exception et sans créer quoi que ce soit — `_find_existing_alias()` retourne déjà `None` de façon sûre pour un `subfolder` inexistant (`:814-815`, `if not subfolder.is_dir(): return None`), donc `has_any_exposure()` hérite de cette sûreté sans code supplémentaire pour ces cas.
- **Cas d'ambiguïté** (plusieurs alias trouvés pour un même `lora_id`, situation déjà détectée et levée en `LoRALibraryError` par `_find_existing_alias()` elle-même, `:819-825`) : `has_any_exposure()` **laisse remonter** cette exception plutôt que de l'avaler silencieusement — un état de corruption déjà détecté par le mécanisme existant ne doit jamais être masqué au moment précis où l'utilisateur tente d'agir sur les Settings. `ApplicationSettingsManager.update()` ne catch pas cette exception non plus — elle remonte telle quelle à l'appelant UI, qui devra la traiter comme toute autre erreur de sauvegarde (voir §8).

## 5. Verrou Settings — contrat exact

Dans `ApplicationSettingsManager.update()` (`src/managers/application_settings_manager.py`), à l'image exacte du calcul déjà existant pour `lora_library_path_changed` (`:84-86`) :

```python
forge_lora_expose_path_changed = (
    forge_lora_expose_path is not None
    and forge_lora_expose_path != current.forge_lora_expose_path
)
comfyui_lora_expose_path_changed = (
    comfyui_lora_expose_path is not None
    and comfyui_lora_expose_path != current.comfyui_lora_expose_path
)
```

Puis, avant la construction du `candidate` (même position relative que le contrôle `lora_library_path` existant, avant le bloc `changed` global) :

```python
if (
    forge_lora_expose_path_changed
    and self._lora_library_manager is not None
    and self._lora_library_manager.has_any_exposure(current.forge_lora_expose_path)
):
    raise <ExceptionRetenue>(...)  # voir §9

if (
    comfyui_lora_expose_path_changed
    and self._lora_library_manager is not None
    and self._lora_library_manager.has_any_exposure(current.comfyui_lora_expose_path)
):
    raise <ExceptionRetenue>(...)  # voir §9
```

- Le contrôle porte sur `current.forge_lora_expose_path`/`current.comfyui_lora_expose_path` — le root **actuellement configuré, avant le changement demandé** — jamais la nouvelle valeur proposée (qui n'a par définition aucune exposition connue tant qu'elle n'a pas encore été utilisée).
- `self._lora_library_manager is None` (dépendance optionnelle non injectée) → le verrou ne peut structurellement jamais se déclencher, exactement comme pour `lora_library_path` (`test_manager_without_lora_library_manager_never_locks`, comportement hérité tel quel).
- Aucune mutation, aucun `ApplicationSettingsStorage.save()`, aucune reconstruction du `candidate` n'a lieu avant ces deux contrôles — un refus laisse `self._settings` strictement intact, identique au contrat déjà établi pour `lora_library_path`.

## 6. Comportement même-valeur (no-op)

Resoumettre exactement la valeur déjà configurée pour `forge_lora_expose_path` ou `comfyui_lora_expose_path` ne déclenche jamais le verrou, même si des LoRA y sont exposés — parce que `forge_lora_expose_path_changed`/`comfyui_lora_expose_path_changed` est `False` dans ce cas (identique à `current.*`), et le contrôle `has_any_exposure()` n'est évalué que si `*_changed` est vrai. Ce comportement est strictement identique au contrat déjà en vigueur pour `lora_library_path` (`test_same_path_as_current_is_a_no_op_even_with_non_empty_registry`).

## 7. Root vide / non configuré — comportement explicite

Couvert nativement par `has_any_exposure()` (§4) : root vide, inexistant, dossier `AIStudioToolkit/` absent, bibliothèque vide, ou aucun alias correspondant à un `lora_id` connu → `has_any_exposure(...) == False` dans tous les cas, jamais de verrou levé pour ces situations, jamais de création de dossier pendant le contrôle.

## 8. UI Settings

Réutilisation intégrale du pattern déjà existant dans `SettingsPage.save_application_settings()` (`src/ui/pages/settings_page.py:676-708`) — aucun nouveau widget, aucune nouvelle disposition :
- Un changement refusé est intercepté par un `except` calqué mot pour mot sur le bloc `except LoRALibraryPathLockedError` existant (`:697-705`) : `QMessageBox.critical(self, "Erreur", str(exc))`, puis `self.update_application_settings()` pour resynchroniser **tous** les champs Application (y compris ceux d'un autre champ édité dans le même clic, exactement comme aujourd'hui pour `lora_library_path`) avec l'état réellement persisté — jamais de valeur rejetée laissée affichée.
- Le message d'erreur doit indiquer explicitement que les LoRA exposés au provider concerné (Forge ou ComfyUI, nommément) doivent être désexposés avant de pouvoir modifier son chemin d'exposition — texte à finaliser lors de l'implémentation, sur le modèle du message déjà existant pour `lora_library_path` (« Supprimez toutes les entrées de la bibliothèque avant de changer ce chemin, ou conservez le chemin actuel »).
- Aucun workflow de migration, de déblocage automatique, ou de nettoyage n'est ajouté à l'UI.

## 9. Exception métier retenue

**Décision : une nouvelle exception dédiée, `LoRAExposureRootLockedError`, partagée par les deux providers (Forge et ComfyUI), plutôt qu'une réutilisation du nom `LoRALibraryPathLockedError`.**

Justification : `LoRALibraryPathLockedError` porte un nom sémantiquement spécifique au verrou de `lora_library_path` (le chemin de la bibliothèque elle-même, une notion distincte d'un chemin d'exposition Forge/ComfyUI) — le réutiliser tel quel pour un concept différent romprait la lisibilité de son nom sans bénéfice réel, et cette classe est déjà directement importée et testée par son nom exact dans plusieurs fichiers de tests existants (`test_lora_library_roundtrip.py`, `test_application_settings_roundtrip.py`) — la renommer romprait ces tests sans justification. À l'inverse, créer **deux** exceptions séparées (une par provider) constituerait la « multiplication inutile de types d'exceptions » explicitement à éviter, alors que le message d'erreur suffit déjà à distinguer Forge de ComfyUI (paramètre du message, comme `_expose()`/`_unexpose()` le font déjà avec `engine_label`). **Une seule nouvelle exception, générique aux deux providers**, est donc le compromis le plus cohérent avec l'architecture actuelle : elle suit exactement la même convention (une exception Manager-level dédiée à un verrou de changement de Settings, catchable dans un `except` dédié de `SettingsPage`) sans dupliquer ni renommer l'existant.

```python
class LoRAExposureRootLockedError(Exception):
    """
    Raised by ApplicationSettingsManager.update() when forge_lora_expose_path
    or comfyui_lora_expose_path is given a genuinely different value while
    the Central LoRA Library still has at least one identifiable exposure
    in the currently configured root for that provider. Mirrors
    LoRALibraryPathLockedError's contract exactly (same-value resubmission
    is never blocked, no automatic migration/cleanup is attempted), for a
    conceptually distinct root — kept as a separate type since the two
    locks protect different Settings fields with different remediation
    steps (delete every library entry vs. unexpose from one provider).
    """
```

`SettingsPage.save_application_settings()` gagne un second bloc `except LoRAExposureRootLockedError as exc:` (même corps que le bloc `LoRALibraryPathLockedError` existant : `QMessageBox.critical` + `self.update_application_settings()`), ou une fusion `except (LoRALibraryPathLockedError, LoRAExposureRootLockedError) as exc:` si l'implémentation juge le corps strictement identique suffisamment proche pour le factoriser sans perte de clarté — décision laissée à l'implémentation, sans impact sur le contrat observable.

## 10. Invariant M135 — préservé sans modification

M149 ne modifie ni ne touche :
- `_expose()` / `expose_to_forge()` / `expose_to_comfyui()` ;
- `_unexpose()` / `unexpose_from_forge()` / `unexpose_from_comfyui()` ;
- `LoRALibraryManager.delete()` ;
- `LoRAPage.delete_from_library()` et sa logique d'agrégation M135 (tentative des deux `unexpose`, agrégation des erreurs réelles, refus du `delete()` canonique si l'un des deux lève une exception, retry idempotent possible sur succès partiel).

M149 agit exclusivement **en amont**, au moment du changement de Settings — jamais au moment de la suppression. Le chemin `UI → Manager → unexpose Forge → unexpose ComfyUI → canonical delete` reste identique ligne pour ligne. M149 ne fait qu'empêcher qu'un root soit changé pendant qu'une exposition y existe encore — il ne change rien à ce qui se passe une fois qu'un root a effectivement été libéré.

## 11. Stratégie hardlink — inchangée

Le mécanisme reste exclusivement `os.link()` (`lora_library_manager.py:678, 705`), sans fallback copy/symlink/junction, sans distinction Forge/ComfyUI au niveau du mécanisme. M149 ne modifie aucune ligne de `_expose()`/`_unexpose()` et ne change donc rien à cette stratégie.

## 12. Orphelins historiques — explicitement hors périmètre

Un hardlink créé **avant** M149 dans un ancien `expose_root` que les Settings ne référencent plus ne peut pas être retrouvé de manière fiable — aucune trace de cet ancien chemin n'existe nulle part (ni Domain, ni Settings, ni log). M149 est un correctif **prospectif uniquement** : il empêche la création de *futurs* orphelins par changement de root, il ne répare rien de préexistant. Aucun scan disque arbitraire, aucune tentative de reconstruction par identité d'inode hors des roots actuellement connus par Settings.

## 13. Fichiers attendus

Production :
- `src/managers/lora_library_manager.py` — ajout de `has_any_exposure()` uniquement, aucune modification de `_expose()`/`_unexpose()`/`delete()`.
- `src/managers/application_settings_manager.py` — ajout de la nouvelle exception `LoRAExposureRootLockedError`, des deux booléens `*_changed`, et des deux contrôles de verrou dans `update()`.
- `src/ui/pages/settings_page.py` — ajout d'un bloc `except` dédié (ou fusionné, voir §9) dans `save_application_settings()`.

Tests :
- `tests/integration/test_lora_library_roundtrip.py` — nouveaux tests de `has_any_exposure()`.
- `tests/integration/test_application_settings_roundtrip.py` — fichier réel confirmé par lecture directe (`ApplicationSettingsRoundTripTest`), contient déjà le commentaire à corriger « No lock of any kind (unlike lora_library_path) — this field is freely changeable at any time » (`:685-689`), devenu obsolète par cette mission ; nouveaux tests du verrou Forge/ComfyUI à y ajouter, sur le modèle exact de `ApplicationSettingsLoraLibraryLockTest` (`test_lora_library_roundtrip.py:956-1053`) — classe(s) de test à nommer lors de l'implémentation, en cohérence avec les conventions existantes.

Documentation :
- `docs/missions/MISSION_149.md` (ce document).

Si l'implémentation démontre qu'un autre fichier de production est réellement nécessaire, ce point doit être signalé et justifié avant toute modification — jamais ajouté silencieusement au périmètre.

## 14. Non-goals (exclusions confirmées)

Persistance des chemins d'exposition ; nouveau registre d'exposition ; modification du Domain `LoRA` ; modification de `LoRALibraryStorage` ; toute migration de schéma ; migration automatique A→B ; récupération des hardlinks historiques déjà orphelins ; scan global du disque ; modification de `_expose()`/`_unexpose()`/`delete()`/de la logique M135 ; changement de stratégie hardlink (copy/symlink/junction) ; `ComfyUIEngine.wait_for_result()` (Candidate 2) ; rollback de création Workspace (Candidate 3) ; cascade de suppression Character ; validation path-traversal Training (`_training_folder()`) ; `rolling_backup` OneTrainer ; caption sidecars ; Training Resume ; nettoyage `create_job()` ; lifecycle/flakiness Forge ; Mission 148 elle-même.

## 15. Matrice de tests requise

**`LoRALibraryManager.has_any_exposure()`** (nouveaux, `test_lora_library_roundtrip.py`) :
1. Bibliothèque vide → `False`.
2. Root vide/non configuré (`""`/`None`) → `False`.
3. Root inexistant sur disque → `False`.
4. Root existant mais `AIStudioToolkit/` absent → `False`.
5. LoRA connu exposé dans ce root → `True`.
6. Après `unexpose` de ce LoRA → `False`.
7. Fichier étranger présent dans `AIStudioToolkit/` (non rattachable à un `lora_id` connu) → ne bloque pas, `False` si aucun LoRA connu n'y est par ailleurs exposé.
8. Alias sur disque correspondant à un `lora_id` qui n'est plus/pas dans la bibliothèque courante → ne bloque pas, `False`.

**`ApplicationSettingsManager.update()` — verrou Forge** (nouveaux, `test_application_settings_roundtrip.py`) :
9. Exposition Forge active en `A` → tentative `A→B` refusée (`LoRAExposureRootLockedError`, aucune mutation, `self._settings` inchangé).
10. Exposition Forge active en `A` → `A→A` (même valeur) acceptée en no-op, jamais refusée.
11. Après désexposition (LoRA supprimé ou désexposé) → `A→B` de nouveau acceptée.

**Verrou ComfyUI** (nouveaux) :
12. Matrice identique aux points 9-11, appliquée à `comfyui_lora_expose_path`.

**Indépendance des deux providers** (nouveaux) :
13. Forge exposé, ComfyUI non exposé → changement Forge refusé, changement ComfyUI (isolé) autorisé.
14. ComfyUI exposé, Forge non exposé → inverse.
15. Forge **et** ComfyUI exposés simultanément (scénario déjà couvert structurellement par `test_lora_library_roundtrip.py:1416-1423` pour l'exposition elle-même, à réutiliser comme fixture) → chaque root verrouillé indépendamment ; un appel `update()` combiné modifiant les deux champs à la fois est refusé dans son ensemble si l'un des deux est verrouillé (voir §3), sans mutation partielle.

**Non-régression M135** (aucune duplication artificielle) :
16. Rejouer intégralement la suite existante de suppression/unexpose (`LoRALibraryManagerComfyUIExposureTest`, `LoRALibraryManagerForgeExposureTest`, et les tests UI de `delete_from_library()` s'ils existent) sans aucune modification de ces tests — sert de preuve que `_expose()`/`_unexpose()`/`delete()` restent identiques.

Aucune duplication artificielle : si un invariant listé ci-dessus s'avère déjà couvert par un test existant lors de l'implémentation, il doit être documenté comme réutilisé, jamais dupliqué.

## 16. Cross-session — invariant à documenter dans le code

Aucune nouvelle persistance n'étant introduite, M149 ne nécessite ni migration ni test de sérialisation. Le verrou fonctionne correctement après redémarrage du Toolkit par construction : `has_any_exposure()` s'appuie uniquement sur (a) la Central Library réellement persistée (`lora_library.json`, déjà rechargée à chaque démarrage), (b) le Setting courant réellement persisté (`application_settings.json`, déjà rechargé à chaque démarrage), et (c) un scan filesystem live du root courant au moment de l'appel — trois sources déjà correctement rechargées avant toute mission, sans état intermédiaire en mémoire à revalider. Ce point doit être mentionné explicitement dans le docstring de `has_any_exposure()` lors de l'implémentation.

## 17. Vérifications de qualité (avant de considérer l'implémentation terminée)

- Confirmer que `has_any_exposure()` ne modifie strictement rien (ni `self._loras`, ni le filesystem, ni la registry).
- Confirmer que `_find_existing_alias()` n'a reçu aucune modification.
- Confirmer que les deux nouveaux contrôles dans `update()` s'exécutent avant toute construction du `candidate` et tout appel à `ApplicationSettingsStorage.save()`.
- Confirmer qu'un appel `update()` combiné (Forge + ComfyUI + autres champs dans le même appel) refusé ne persiste et ne mute strictement rien, y compris les champs qui n'étaient pas eux-mêmes verrouillés.
- Confirmer que le commentaire obsolète de `test_application_settings_roundtrip.py:685-689` est corrigé pour refléter le nouveau comportement.
- Confirmer qu'aucun fichier hors de la liste §13 n'a été modifié.

## 18. Résultats réels (implémentation)

**Fichiers effectivement modifiés** — strictement les 5 fichiers annoncés au §13, aucun autre :
- `src/managers/lora_library_manager.py` : +50/-0, ajout unique de `has_any_exposure()` entre `unexpose_from_forge()` et `_unexpose()`. Un seul hunk de diff dans tout le fichier — `_expose()`, `_unexpose()`, `expose_to_comfyui()`, `expose_to_forge()`, `unexpose_from_comfyui()`, `unexpose_from_forge()`, `delete()`, `import_lora()`, `update()`, `set_thumbnail()`, `_find_existing_alias()` tous confirmés octet pour octet inchangés.
- `src/managers/application_settings_manager.py` : +62/-0 en deux hunks additifs — la classe `LoRAExposureRootLockedError` (après `LoRALibraryPathLockedError`, non modifiée) et les deux blocs de garde (`forge_lora_expose_path_changed`/`comfyui_lora_expose_path_changed` + les deux `raise`), insérés avant le calcul de `changed` et donc avant toute construction de `candidate`/tout appel à `ApplicationSettingsStorage.save()` — atomicité vérifiée directement dans le diff (aucune ligne entre la construction du candidat et la sauvegarde n'a été touchée).
- `src/ui/pages/settings_page.py` : +18/-10 — import étendu (`LoRAExposureRootLockedError` ajouté), et le bloc `except LoRALibraryPathLockedError` devient `except (LoRALibraryPathLockedError, LoRAExposureRootLockedError)`, corps strictement inchangé (même `QMessageBox.critical` + même `self.update_application_settings()` de resynchronisation). Aucun nouveau widget, aucune nouvelle disposition.
- `tests/integration/test_lora_library_roundtrip.py` : +296/-0 — import étendu (`LoRAExposureRootLockedError`), nouvelle classe `LoRALibraryManagerHasAnyExposureTest` (9 tests) et nouvelle classe `ApplicationSettingsExposureRootLockTest` (11 tests, positionnée juste après `ApplicationSettingsLoraLibraryLockTest`, son analogue exact pour `lora_library_path`).
- `tests/integration/test_application_settings_roundtrip.py` : +12/-4 — uniquement la correction du commentaire obsolète (§11 de ce document) ; aucune assertion de test existante modifiée.

**Écart mineur par rapport au draft (§13)** : le draft suggérait d'ajouter les tests du verrou Forge/ComfyUI dans `test_application_settings_roundtrip.py`. À l'implémentation, ce fichier s'est avéré ne jamais importer `LoRALibraryManager` et ses fixtures `ApplicationSettingsManager` n'y injectent jamais de `lora_library_manager` réel — exactement la même situation déjà documentée pour le verrou `lora_library_path` existant, dont le test vit pour cette raison dans `test_lora_library_roundtrip.py` (`ApplicationSettingsLoraLibraryLockTest`). Les nouveaux tests Forge/ComfyUI ont donc été placés au même endroit que leur analogue exact, en réutilisant sa fixture réelle (LoRA importée + hardlink réellement exposé), plutôt que de recréer cette infrastructure dans `test_application_settings_roundtrip.py`. `test_application_settings_roundtrip.py` n'a été touché que pour la correction du commentaire obsolète (§11), conformément à l'instruction « pas de cleanup opportuniste ». Aucun autre écart de scope, de contrat ou de fichier.

**Exception ajoutée** : `LoRAExposureRootLockedError` (`src/managers/application_settings_manager.py`), une seule exception partagée par Forge et ComfyUI — jamais deux, le provider concerné est nommé explicitement dans le message d'erreur, jamais dans le type. `LoRALibraryPathLockedError` n'a reçu aucune modification.

**`has_any_exposure(expose_root) -> bool`** (`LoRALibraryManager`) : itère `self._loras`, retourne `True` dès que `_find_existing_alias(expose_root, lora.lora_id)` trouve un alias pour l'un d'eux (court-circuit), `False` sinon. Garde explicite `if not expose_root: return False` (miroir exact de `_unexpose()`) avant toute construction de `Path`. Aucune création de dossier, aucune mutation, aucun `_save()`. Une ambiguïté multi-alias détectée par `_find_existing_alias()` (`LoRALibraryError`) n'est jamais avalée — elle remonte telle quelle.

**Guard Forge / ComfyUI** : dans `ApplicationSettingsManager.update()`, `forge_lora_expose_path_changed`/`comfyui_lora_expose_path_changed` calculés à l'identique du `lora_library_path_changed` déjà existant ; chaque garde lève `LoRAExposureRootLockedError` si le champ change réellement **et** `has_any_exposure(current.<champ>)` est vrai — testé indépendamment (`test_forge_lock_does_not_affect_comfyui`/`test_comfyui_lock_does_not_affect_forge`/`test_both_providers_exposed_are_locked_independently`).

**Atomicité Settings** : confirmée à la fois par lecture du diff (les deux gardes précèdent toute mutation) et par test dédié (`test_refused_exposure_change_does_not_persist_other_fields_in_the_same_call` — un `update()` combiné Forge+`ollama_url` refusé sur le verrou Forge ne persiste ni le nouveau root Forge ni le nouveau `ollama_url`, `ApplicationSettingsStorage.save` jamais appelé).

**Handling UI** : bloc `except` étendu en tuple, message `QMessageBox.critical` distinct par provider (texte nommant Forge ou ComfyUI selon le champ refusé), resynchronisation via `update_application_settings()` identique au comportement `lora_library_path` existant. Aucun nouveau widget.

**Comportement fichiers étrangers/inconnus** : confirmé par test — un fichier sans rapport dans `AIStudioToolkit/` (`test_unrelated_foreign_file_never_locks`) et un alias portant un `lora_id` absent de la bibliothèque courante (`test_alias_belonging_to_an_unknown_lora_id_never_locks`) ne déclenchent jamais le verrou.

**Comportement ambiguïté multi-alias** : confirmé par test (`test_ambiguous_multiple_aliases_still_raises_instead_of_silently_reporting_true`) — `has_any_exposure()` laisse remonter `LoRALibraryError` sans jamais la convertir en `True`/`False`.

**Tests ajoutés** : **20 tests nets** (2842 → 2862 tests collectés). `LoRALibraryManagerHasAnyExposureTest` (9) : bibliothèque vide, root non configuré, root inexistant, dossier `AIStudioToolkit` absent, exposition connue détectée, disparue après unexpose, fichier étranger sans effet, alias `lora_id` inconnu sans effet, ambiguïté multi-alias préservée. `ApplicationSettingsExposureRootLockTest` (11) : Forge refusé/no-op/rouvert après unexpose (3), même matrice ComfyUI (3), indépendance dans les deux sens + double exposition simultanée verrouillée indépendamment (3), atomicité d'un update combiné refusé (1), manager sans `lora_library_manager` injecté ne verrouille jamais (1). Aucun test dupliqué : la matrice §15 des points déjà couverts par la structure de fixture existante (double exposition Forge+ComfyUI simultanée sur racines indépendantes) n'a pas été redémontrée séparément, seulement réutilisée comme prérequis du test d'indépendance.

**Résultats ciblés** :
- `tests.integration.test_lora_library_roundtrip` (fichier complet) : **117/117 passés** (2.264s), dont 9 + 11 = 20 nouveaux.
- `tests.integration.test_application_settings_roundtrip` (fichier complet) : **21/21 passés** (0.961s) — non-régression totale, y compris le test contenant le commentaire corrigé.
- `tests.integration.test_settings_page` (fichier complet, UI) : **90/90 passés** (2.364s) — non-régression totale du handling `except` étendu.

**Résultats voisins / non-régression M135** :
- `tests.integration.test_lora_roundtrip` (Workbench LoRA, non modifié) : **275/275 passés** (16.482s).
- `tests.integration.test_training_roundtrip` (non modifié, aucune interaction attendue) : **384/384 passés** (27.380s).
- Les classes `LoRALibraryManagerComfyUIExposureTest`/`LoRALibraryManagerForgeExposureTest`/`LoRALibraryManagerDeleteTest` (mécanisme M135) ont été rejouées telles quelles dans la suite ciblée ci-dessus, sans aucune modification de leur code — toutes vertes.

**Résultat suite complète** : **2862/2862 collectés/passés, 0 échoué**, exit 0, 314.581s. Équation : 2842 (clôture Mission 148) + 20 nets ajoutés par Mission 149 = **2862**, cohérent. Un traceback bénin préexistant (`inference_page.py`, `QLabel.setText(MagicMock)`) a été observé sur ce run, déjà documenté et reconfirmé non lié aux Missions 142/143/145/148 — sans rapport avec le périmètre M149 (LoRA Library/Settings), non bloquant (suite toujours `OK`). Les lignes `Failed to copy .../disk full/...` interlignées sont des logs attendus de tests d'échec simulé déjà existants ailleurs dans la suite (LoRA Library, Workspace, Dataset), non liées à Mission 149.

**`git diff --check`** : clean, exit 0 (avertissements `LF will be replaced by CRLF` uniquement — normalisation de fin de ligne, non bloquants).

**`git status --short`** : exactement les 5 fichiers M149 modifiés + `docs/missions/MISSION_149.md` — aucun fichier hors scope, `graphify-out/` inchangé par cette session.

**Findings inattendus** : aucun. Aucune découverte nécessitant un élargissement de scope ; `_expose()`/`_unexpose()`/`delete_from_library()`/Domain `LoRA`/`LoRALibraryStorage`/stratégie hardlink tous confirmés inchangés par lecture directe du diff.

## 19. Clôture Git

Commit fonctionnel `98d9c3c5057edfd67757ac4d0011fb550d66ed72` (« Guard LoRA exposure root changes while exposed », 6 fichiers : `src/managers/lora_library_manager.py`, `src/managers/application_settings_manager.py`, `src/ui/pages/settings_page.py`, `tests/integration/test_lora_library_roundtrip.py`, `tests/integration/test_application_settings_roundtrip.py`, `docs/missions/MISSION_149.md`), poussé sur `main` (`141e92a..98d9c3c`). Tag annoté `v0.2-mission149` créé exactement sur ce commit (objet tag local et distant `303ca39d79fe7c7cfe4f1243be73d61155b07d71`, peeled target local et distant tous deux `98d9c3c5057edfd67757ac4d0011fb550d66ed72`, vérifiés identiques), poussé et confirmé sur `origin`. `v0.2-mission148` (peeled `dffe92c09dbcd55e5c950d8c065708682034e0fe`), `v0.2-mission147` (peeled `3f9d9e7a8e02b05a72f24bfae2e233e4b62ca06a`), `v0.2-mission146` (peeled `24613861960e3f4e6c87c9a80c8f111f00f74b7a`) et `v0.2-mission145` (peeled `3dcc625f02bca4e9398c1db8c933550058513582`) reconfirmés inchangés. GitHub Release `v0.2-mission149` publiée manuellement (titre « v0.2-mission149 — Guard LoRA Exposure Root Changes While Exposed »). Le présent commit documentaire de régularisation post-Release (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`, `docs/missions/MISSION_149.md`) n'appartient pas au tag `v0.2-mission149` — celui-ci reste durablement sur le commit fonctionnel ci-dessus, jamais déplacé. Aucun élargissement de scope, aucune fonctionnalité ajoutée après validation ; les hardlinks historiques déjà orphelins avant cette mission restent explicitement hors périmètre (§12).
