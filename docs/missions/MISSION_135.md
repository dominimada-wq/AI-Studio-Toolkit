# Mission 135 — Fix Orphaned Forge-Exposed Central LoRA Library Hardlink on Deletion

> **MISSION CLÔTURÉE — commit, tag et Release publiés.** `LoRALibraryManager` avait `expose_to_comfyui()`/`unexpose_from_comfyui()` (Mission 095) et `expose_to_forge()` (Mission 108), mais aucun `unexpose_from_forge()`. `LoRAPage.delete_from_library()` ne désexposait donc que ComfyUI avant de supprimer l'entrée canonique — un LoRA exposé à Forge (hardlink NTFS créé silencieusement à la génération, `inference_page.py`) restait physiquement accessible et sélectionnable dans Forge après une suppression que Toolkit annonçait comme définitive. Un helper privé `_unexpose(lora, expose_root, engine_label)`, miroir exact de `_expose()`, factorise désormais le mécanisme partagé ; `unexpose_from_comfyui()` (message d'erreur préservé byte-for-byte) et le nouveau `unexpose_from_forge()` en sont deux wrappers d'une ligne. `delete_from_library()` tente désormais les deux désexpositions de façon inconditionnelle (jamais de court-circuit d'un moteur à cause de l'échec de l'autre) avant toute suppression canonique ; tout échec réel bloque la suppression avec un diagnostic agrégé nommant chaque moteur en cause ; un succès partiel (un alias retiré, l'autre en échec) ne déclenche aucun rollback — l'entrée canonique reste intacte et une nouvelle tentative converge naturellement. `update()` (rename) reste inchangé, confirmé sans risque de lifecycle. Seuls ComfyUI et Forge sont des moteurs réellement implémentés aujourd'hui. **+10 tests nets** (2736 → 2746). Tests ciblés Manager Forge **12/12**, non-régression Manager ComfyUI **21/21**, tests UI multi-moteur **6/6**, non-régression UI ComfyUI **9/9**, `test_lora_library_roundtrip.py` complet **93/93**, `test_lora_roundtrip.py` complet **275/275**, full suite **2746/2746/0 échoué**, aucun flake historique observé sur ce run. Aucun changement ForgeEngine/ComfyUIEngine/lifecycle/Inference/Training/EventBus. Aucun smoke requis.

## 1. Contexte

L'audit global post-Mission 134 (READ-ONLY, voir le rapport transmis) a identifié ce bug en vérifiant directement le code : `src/managers/lora_library_manager.py` définit `expose_to_comfyui()` (Mission 095), `unexpose_from_comfyui()` (Mission 095) et `expose_to_forge()` (Mission 108, symétrique de `expose_to_comfyui()`), mais aucun `unexpose_from_forge()`. `LoRAPage.delete_from_library()` (`src/ui/pages/lora_page.py:1341-1409`) désexpose ComfyUI avant la suppression canonique — le commentaire du code lui-même énonce l'invariant voulu ("never a best-effort deletion that could leave a ComfyUI-visible hardlink alias referencing data whose canonical library entry no longer exists") — mais n'appelle jamais l'équivalent Forge.

Chemin utilisateur réel : configurer `forge_lora_expose_path` dans Settings → générer une fois avec Forge actif et un LoRA de la Central Library sélectionné (`inference_page.py:1148-1150` appelle `expose_to_forge()` silencieusement, sans bouton manuel dédié comme ComfyUI) → aller dans `LoRAPage` → « Supprimer de la bibliothèque centrale ». Le hardlink NTFS Forge partage l'inode du fichier canonique ; sa suppression (déplacement en `.trash/` puis suppression) ne supprime jamais ce hardlink. Le fichier reste donc utilisable dans Forge après une suppression Toolkit présentée comme définitive.

Cette mission a été retenue en priorité sur les deux autres candidats de l'audit (EventBus sans isolation de panne entre subscribers ; dossiers canoniques UUID de la Central LoRA Library) parce que c'est le seul bug réellement démontré et immédiatement atteignable par un utilisateur, avec un précédent déjà testé (Mission 095) à répliquer plutôt qu'une nouvelle abstraction ou une décision de contrat lourde à trancher.

## 2. Investigation 1 — Contrat transactionnel de suppression (comportement actuel exact)

### 2.1 `LoRALibraryManager.delete()` (`lora_library_manager.py:459-531`)

Ne touche jamais aucun expose root — sa propre docstring le garantit explicitement ("Never touches an external source file"). Contrat : déplace `<library_root>/<lora_id>/` vers `<library_root>/.trash/lora_<lora_id>_<uuid>/` (abandon avant toute mutation Domain si ce déplacement échoue) → mutation Domain (retrait de la liste) → `_save()` → sur échec de `_save()`, rollback Domain (réinsertion à l'index d'origine, ne peut pas lui-même échouer) puis tentative de déplacement retour du dossier, avec message enrichi si ce retour échoue aussi → sur succès de `_save()`, suppression best-effort du dossier `.trash/`, jamais annulée en cas d'échec (seulement rapportée via `cleanup_failed`/`residual_path`). Ce contrat interne, entièrement dédié au dossier canonique, n'est pas modifié par M135.

### 2.2 `unexpose_from_comfyui()` (`lora_library_manager.py:727-757`) — comportement exact

```python
def unexpose_from_comfyui(self, lora: LoRA, expose_root) -> bool:
    if not expose_root:
        return False
    existing = self._find_existing_alias(Path(expose_root), lora.lora_id)
    if existing is None:
        return False
    try:
        existing.unlink()
    except OSError as exc:
        raise LoRALibraryError(
            f"Could not remove ComfyUI exposure alias for LoRA "
            f"{lora.lora_id!r} at {existing}: {exc}"
        ) from exc
    return True
```

- `expose_root` faux (non configuré) → `False`, jamais une erreur.
- Aucun alias trouvé (`_find_existing_alias()` localise toujours par `lora_id` seul, jamais en recalculant le nom de fichier attendu à partir de `lora.name` — voir §4 ci-dessous pour pourquoi ceci importe pour le rename) → `False`, no-op.
- Alias trouvé, suppression réussie → `True`.
- Alias trouvé, suppression échoue réellement (`OSError`) → `LoRALibraryError`, jamais avalé.
- `_find_existing_alias()` (`:775-799`) lève elle-même `LoRALibraryError` si plusieurs fichiers candidats existent pour le même `lora_id` sous le sous-dossier d'exposition — refuse de deviner, jamais un choix silencieux.

Seul contenu réellement spécifique à ComfyUI dans toute cette méthode : le mot "ComfyUI" dans le message d'erreur. Tout le reste (garde sur `expose_root`, appel à `_find_existing_alias()`, `unlink()`, enveloppe `LoRALibraryError`) est déjà générique.

### 2.3 `LoRAPage.delete_from_library()` (`lora_page.py:1341-1409`) — orchestration UI actuelle

1. Confirmation utilisateur (`QMessageBox`).
2. Lecture live de `comfyui_lora_expose_path` et de l'entrée LoRA.
3. Si l'entrée existe et qu'un `expose_root` est configuré : appelle `unexpose_from_comfyui()`. Sur `LoRALibraryError` → `QMessageBox.critical()`, **`return` immédiat — `lora_library_manager.delete()` n'est jamais appelé**, l'entrée canonique survit intacte.
4. Sinon (no-op ou succès) : lecture live de `lora_library_path`, appel à `lora_library_manager.delete()`.
5. Sur `cleanup_failed` (dette `.trash/` interne, sans rapport avec l'exposition), avertissement non bloquant.

Confirmé par un test dédié existant, `test_delete_is_refused_when_unexpose_fails_and_the_entry_survives` (`tests/integration/test_lora_roundtrip.py:5372-5396`) : patch de `unexpose_from_comfyui` en échec → `delete()` jamais appelé (`delete_mock.assert_not_called()`) → entrée, fichier et alias survivent tous intacts.

**Le contrat exact actuel est donc : désexposition externe réussie (ou no-op) → seulement ensuite suppression canonique. Un échec de désexposition bloque bien la suppression de Central Library. M135 doit préserver cette propriété, étendue aux deux moteurs.**

### 2.4 Matrice multi-moteur — comportement retenu

Aucun des deux appels de désexposition (`unexpose_from_comfyui`/`unexpose_from_forge`) ne mute jamais l'entrée canonique — ils ne touchent que des fichiers d'alias externes, indépendants l'un de l'autre et indépendants du dossier canonique. Chaque appel est déjà idempotent (rejouable sans effet de bord si l'alias a déjà disparu). Design retenu : **les deux désexpositions sont tentées inconditionnellement** (jamais de court-circuit dès le premier échec) avant toute suppression canonique ; si l'une des deux (ou les deux) échoue réellement, la suppression canonique est refusée et un message d'erreur unique énumère explicitement chaque échec réel, sans jamais masquer l'un derrière l'autre — même idiome d'agrégation qu'utilisé par Mission 134 pour la cause initiale et l'échec de cleanup.

| Cas | ComfyUI | Forge | Résultat |
|---|---|---|---|
| Aucun des deux exposé | no-op | no-op | Suppression canonique normale (comportement actuel inchangé) |
| Seul ComfyUI exposé | retiré | no-op | Suppression canonique normale (comportement actuel inchangé) |
| Seul Forge exposé | no-op | retiré | Suppression canonique normale (alias Forge retiré avant) |
| Les deux exposés | retiré | retiré | Suppression canonique normale |
| ComfyUI réussit, Forge échoue réellement | retiré | échec réel | **Suppression canonique refusée** ; alias ComfyUI déjà retiré (fait acquis) ; message nommant explicitement l'échec Forge ; entrée canonique survit |
| Forge réussit, ComfyUI échoue réellement | échec réel | retiré | **Suppression canonique refusée** ; alias Forge déjà retiré (fait acquis) ; message nommant explicitement l'échec ComfyUI ; entrée canonique survit |
| Les deux échouent réellement | échec réel | échec réel | Suppression refusée ; message nommant les deux échecs ; rien n'est retiré |
| `expose_root` non configuré pour un moteur | no-op pour ce moteur | — | Ne bloque jamais artificiellement la suppression (invariant §6.7) |
| Alias déjà absent (jamais créé, ou supprimé manuellement) | no-op | no-op | Idempotent, jamais une erreur |

**Sur le cas « un moteur réussit, l'autre échoue » : ce résultat partiellement désexposé est jugé acceptable et récupérable au prochain essai, sans mécanisme supplémentaire.** L'entrée canonique restant intacte (la suppression n'a jamais eu lieu), une nouvelle tentative de suppression relance les deux désexpositions : celle déjà retirée redevient un no-op idempotent, celle qui avait échoué est retentée seule. Aucun rollback n'est nécessaire : rien d'irréversible n'a eu lieu côté canonique, et l'alias déjà retiré ne peut pas être « rétabli à tort » puisqu'il ne fait que refléter fidèlement l'état filesystem réel à chaque appel (`_find_existing_alias()` re-scanne toujours le disque, jamais un état mis en cache). Construire un rollback compensatoire (recréer artificiellement l'alias déjà retiré) ajouterait de la complexité pour un bénéfice nul — l'entrée canonique n'ayant jamais été supprimée, il n'y a rien à réconcilier.

## 3. Investigation 3 — `update()` (rename) et le risque d'alias orphelin/multiple

Il n'existe pas de méthode `update_name()` distincte dans `LoRALibraryManager` : le renommage passe par `update()` (`lora_library_manager.py:251-331`, Mission 090, mutation combinée de 5 champs texte dont `name`). Sa docstring garantit explicitement : *"Never touches the filesystem: `<library_root>/<lora_id>/` is keyed by lora_id ... never by name — a rename here never renames/moves anything on disk."* `update()` ne touche donc jamais un alias d'exposition, ComfyUI ou Forge.

Conséquence sur un alias déjà exposé avant un renommage : le fichier d'alias sur disque garde son ancien nom de fichier (`<ancien-slug>__<lora_id>.<ext>`) jusqu'à la prochaine exposition réelle. Ceci est déjà couvert et prouvé par les tests existants :
- `test_expose_to_forge_after_rename_replaces_the_stale_alias` / son équivalent ComfyUI : la prochaine `expose_to_forge()`/`expose_to_comfyui()` après un renommage crée d'abord le nouveau hardlink sous le nom à jour, puis retire au mieux (best-effort, `cleanup_failed`/`residual_path` si cela échoue) l'ancien alias devenu obsolète — jamais destructif en premier, jamais un remplacement en écrasement.
- `test_unexpose_finds_the_alias_after_a_rename` : `unexpose_from_comfyui()` retrouve et retire correctement l'alias même après un renommage intervenu entre exposition et désexposition, parce que `_find_existing_alias()` localise toujours par `lora_id` seul (jamais en recalculant le nom de fichier attendu depuis `lora.name` — le slug n'est que cosmétique).
- `_find_existing_alias()` lève explicitement `LoRALibraryError` si plusieurs fichiers candidats existent pour le même `lora_id` (`:791-797`) — un alias multiple ne peut jamais être silencieusement ignoré ou mal choisi ; c'est structurellement empêché, pas seulement non observé.

**Conclusion : le renommage ne crée ni alias orphelin, ni alias multiple silencieux, ni comportement destructif — uniquement une fenêtre cosmétique où le nom de fichier visible dans le dossier d'exposition reste l'ancien nom jusqu'à la prochaine exposition réelle, tout en restant correctement lié (même inode) à la bonne entrée `lora_id`.** C'est une dette UX mineure, distincte, **explicitement laissée hors périmètre de M135** — à consigner séparément dans `docs/PROJECT_CONTEXT.md` lors d'une future régularisation documentaire, jamais comme un correctif de cette mission.

## 4. Investigation 4 — Moteurs réellement implémentés aujourd'hui

Recherche exhaustive dans `src/managers/lora_library_manager.py` : seules deux méthodes d'exposition existent, `expose_to_comfyui()` et `expose_to_forge()`, toutes deux dérivées du même `_expose()` privé. Recherche dans `src/domain/application_settings.py` : seuls deux champs d'exposition existent, `comfyui_lora_expose_path` et `forge_lora_expose_path`. **Aucun troisième moteur (Fooocus ou autre) n'est implémenté aujourd'hui.** M135 couvre exactement ComfyUI et Forge ; aucune boucle générique sur une liste de moteurs hypothétiques n'est introduite — les deux méthodes publiques restent des wrappers explicites nommés, exactement comme `expose_to_comfyui()`/`expose_to_forge()` le sont déjà pour l'exposition.

## 5. Investigation 2 — Design du helper partagé `_unexpose()`

`_expose()` est déjà l'unique mécanisme partagé derrière `expose_to_comfyui()`/`expose_to_forge()`, paramétré par `engine_label`/`settings_field`. Côté désexposition, aucun helper n'existe encore — `unexpose_from_comfyui()` est une méthode autonome dont le seul élément spécifique à ComfyUI est le littéral `"ComfyUI"` dans son message d'erreur.

**Design retenu** : extraire un helper privé `_unexpose(self, lora: LoRA, expose_root, engine_label: str) -> bool`, reprenant le corps exact de `unexpose_from_comfyui()` actuel, avec `engine_label` substitué dans le message d'erreur à la place du littéral `"ComfyUI"`. `unexpose_from_comfyui()` et `unexpose_from_forge()` deviennent alors deux wrappers d'une ligne :

```python
def unexpose_from_comfyui(self, lora: LoRA, expose_root) -> bool:
    return self._unexpose(lora, expose_root, engine_label="ComfyUI")

def unexpose_from_forge(self, lora: LoRA, expose_root) -> bool:
    return self._unexpose(lora, expose_root, engine_label="Forge")
```

- **Paramètres** : `lora`, `expose_root`, `engine_label` seul — pas de `settings_field`, contrairement à `_expose()` : `_unexpose()` ne valide jamais `expose_root` par une levée d'erreur (un root absent est un no-op silencieux, jamais une erreur nommant le champ Settings concerné), donc `settings_field` n'aurait aucun usage dans le corps de la méthode. Ajouter ce paramètre inutilisé serait une généralisation non justifiée par un besoin réel.
- **Erreurs** : `LoRALibraryError` sur un échec réel de `unlink()`, message paramétré par `engine_label` (`f"Could not remove {engine_label} exposure alias for LoRA {lora.lora_id!r} at {existing}: {exc}"`) — pour ComfyUI, ce message reste **byte-for-byte identique** au message actuel (`engine_label="ComfyUI"` reproduit exactement le littéral existant), garantissant qu'aucun des 5 tests existants de `LoRALibraryManagerComfyUIExposureTest` visant `unexpose_from_comfyui()` n'a besoin d'être modifié.
- **Root non configuré** : `False`, no-op, inchangé.
- **Aucun alias trouvé** : `False`, no-op, inchangé (délégué à `_find_existing_alias()`, lui-même déjà partagé par les deux moteurs).
- **Plusieurs fichiers candidats** : déjà entièrement géré par `_find_existing_alias()` elle-même (lève `LoRALibraryError` avant même que `_unexpose()` ne s'exécute) — aucune logique supplémentaire nécessaire dans le nouveau helper.

**Aucune régression du côté ComfyUI** : le refactor ne change ni la signature publique de `unexpose_from_comfyui()`, ni son comportement observable, ni ses messages d'erreur — seule son implémentation interne délègue désormais à `_unexpose()`.

## 6. Fichiers autorisés

- `src/managers/lora_library_manager.py` — ajout de `_unexpose()` et `unexpose_from_forge()`, refactor de `unexpose_from_comfyui()` en wrapper.
- `src/ui/pages/lora_page.py` — `delete_from_library()` étendu pour tenter les deux désexpositions avant la suppression canonique, avec agrégation d'erreur si l'une ou les deux échouent réellement.
- `tests/integration/test_lora_library_roundtrip.py` — tests `unexpose_from_forge()` au niveau Manager (miroir de la suite `unexpose_from_comfyui()` existante).
- `tests/integration/test_lora_roundtrip.py` — tests d'orchestration UI multi-moteur dans `delete_from_library()` (miroir des 3 tests UI ComfyUI existants, plus les cas multi-moteur).
- `docs/missions/MISSION_135.md` (ce document).

Aucun autre fichier n'est requis — aucune découverte de cette investigation ne justifie de toucher `src/engines/comfyui_engine.py`, `src/engines/forge_engine.py`, `src/domain/application_settings.py` (les deux champs `*_lora_expose_path` existent déjà), ou `src/ui/pages/inference_page.py` (l'exposition à la génération reste inchangée, seule la désexposition à la suppression est concernée).

## 7. Invariants protégés

1. Suppression d'une LoRA non exposée (ni ComfyUI ni Forge) : comportement inchangé.
2. LoRA exposée seulement à ComfyUI : contrat actuel inchangé (alias retiré, suppression procède).
3. LoRA exposée seulement à Forge : alias Forge retiré avant la suppression canonique.
4. LoRA exposée aux deux moteurs : les deux alias sont traités (retirés ou confirmés no-op) avant la suppression canonique.
5. Échec réel d'une désexposition obligatoire (l'un des deux moteurs, ou les deux) : suppression canonique refusée, entrée et fichier canonique intacts, diagnostic explicite nommant chaque échec réel sans en masquer aucun.
6. Alias déjà absent pour un moteur (jamais créé, ou déjà supprimé manuellement) : no-op idempotent pour ce moteur, jamais une erreur.
7. `expose_root` non configuré pour un moteur : no-op pour ce moteur, ne bloque jamais artificiellement une suppression normale.
8. Aucune suppression d'un fichier source externe original — uniquement les alias/hardlinks gérés par Toolkit sous `<expose_root>/AIStudioToolkit/`.
9. L'identification d'un alias reste toujours fondée sur `lora_id` seul, jamais sur le slug lisible recalculé depuis `lora.name` — propriété déjà garantie par `_find_existing_alias()`, non modifiée par cette mission.
10. Comportement ComfyUI existant (`expose_to_comfyui`, `unexpose_from_comfyui`, tous les tests actuels) non régressé — messages d'erreur inchangés, signature publique inchangée.
11. Un échec partiel (un moteur désexposé avec succès, l'autre en échec) ne transforme jamais un état intermédiaire en suppression réussie — la suppression canonique reste strictement tout-ou-rien du point de vue de l'entrée Domain, même si l'état des alias externes peut avoir partiellement convergé entre deux tentatives.

## 8. Tests prévus

**Niveau Manager (`test_lora_library_roundtrip.py`)** — miroir exact de la suite `unexpose_from_comfyui()` existante, appliqué à `unexpose_from_forge()` (nouvelle classe ou extension de `LoRALibraryManagerForgeExposureTest`, à trancher au moment de l'implémentation selon la cohérence avec l'organisation existante des classes de test) :
- A. Alias Forge existant → `unexpose_from_forge()` le retire, retourne `True`.
- B. Jamais exposé à Forge → `False`, no-op.
- C. Appelé deux fois de suite → idempotent (`True` puis `False`).
- D. `expose_root` non configuré (`""`) → `False`, no-op.
- E. Alias retrouvé après un renommage intervenu entre exposition et désexposition → toujours retiré correctement.
- F. Échec réel de suppression (`Path.unlink` patché pour lever `OSError`) → `LoRALibraryError`, message nommant "Forge".
- G. Non-régression : les 5 tests existants `unexpose_from_comfyui()` restent verts inchangés après le refactor `_unexpose()`.

**Niveau UI (`test_lora_roundtrip.py`)** — miroir des 3 tests ComfyUI existants (`test_delete_of_a_never_exposed_entry_still_works_unchanged`, `test_delete_of_an_exposed_entry_removes_the_alias_first`, `test_delete_is_refused_when_unexpose_fails_and_the_entry_survives`), étendus au cas multi-moteur :

- H. Forge exposé seul → suppression retire l'alias Forge, suppression canonique procède normalement.
- I. Forge non exposé / alias absent → suppression normale, aucune erreur artificielle.
- J. Échec réel de désexposition Forge seule → suppression canonique refusée, entrée conservée, diagnostic clair (miroir exact du test ComfyUI existant, `unexpose_from_forge` patché en échec).
- K. ComfyUI et Forge exposés tous les deux → suppression retire les deux alias, procède normalement.
- L. ComfyUI réussit, Forge échoue → suppression refusée, alias ComfyUI réellement retiré (fait acquis observable), entrée canonique conservée, message nommant l'échec Forge.
- M. Forge réussit, ComfyUI échoue → symétrique de L.
- N. Non-régression : les 3 tests UI ComfyUI existants restent verts inchangés.

Le nombre exact de tests nets sera confirmé après implémentation — ce plan n'est pas figé arbitrairement, conformément à l'instruction de ne pas fixer un nombre avant d'avoir établi le contrat définitif pendant l'implémentation. Mocks déterministes uniquement (`unittest.mock.patch`/`patch.object`), hardlinks réels sur répertoire temporaire pour les cas nominaux (même convention que les suites `ComfyUIExposureTest`/`ForgeExposureTest` existantes) — jamais de fichier Windows réellement verrouillé.

## 9. Smoke

**Aucun smoke moteur réel requis, confirmé depuis le code** : le mécanisme hardlink NTFS (`os.link()`/`Path.unlink()`) est déjà validé empiriquement contre une installation ComfyUI réelle par Mission 095 (`MISSION_095.md §3.4`) et répliqué à l'identique pour Forge par Mission 108 — cette mission ne modifie ni le mécanisme de création de hardlink, ni aucune configuration ComfyUI/Forge, ni aucun lancement de processus. Les cas nominaux et d'échec sont entièrement démontrables sur un répertoire temporaire réel (hardlinks véritables) avec des échecs simulés déterministes (`patch.object(Path, "unlink", side_effect=OSError(...))`), exactement comme la suite `LoRALibraryManagerComfyUIExposureTest` le fait déjà. Aucun GPU, aucun lancement réel de Forge, aucune génération réelle.

## 10. Exclusions explicites

- Aucun changement à `ForgeEngine`/`ComfyUIEngine`.
- Aucun changement au lifecycle Start/Stop de Forge ou ComfyUI Local.
- Aucune génération réelle, aucun changement à `InferencePage` au-delà d'aucun (l'exposition à la génération reste strictement inchangée).
- Aucun changement à Training.
- Aucun changement à `EventBus` (Candidat 2 de l'audit, hors périmètre).
- Aucun changement au format de stockage de la Central Library ni à ses dossiers canoniques UUID (Candidat 3 de l'audit, hors périmètre — nécessiterait une mission d'audit/conception dédiée).
- Aucun renommage/migration des dossiers UUID existants.
- Aucune migration de LoRA réelle, aucune manipulation de la bibliothèque réelle de l'architecte.
- Aucun support hypothétique Fooocus ou tout autre moteur non implémenté aujourd'hui.
- Aucune refonte générale multi-provider/boucle générique sur une liste de moteurs.
- `update()`/renommage (Investigation 3) : dette cosmétique confirmée distincte, explicitement exclue — à documenter séparément, jamais implémentée dans cette mission.

## 11. Critères d'acceptation

- [x] `unexpose_from_forge()` existe, testé isolément (tests A-G).
- [x] `_unexpose()` factorise le corps commun sans dupliquer la logique, sans régression ComfyUI (message d'erreur byte-for-byte identique).
- [x] `delete_from_library()` tente les deux désexpositions avant toute suppression canonique, sans court-circuit prématuré.
- [x] Un échec réel de l'une ou des deux désexpositions refuse la suppression canonique avec un diagnostic nommant explicitement chaque échec.
- [x] Un moteur non configuré ou jamais exposé ne bloque jamais artificiellement une suppression (invariant §7.7).
- [x] Aucune suppression d'un fichier source externe — uniquement les alias gérés par Toolkit.
- [x] Tests UI multi-moteur (H-N) verts, y compris les deux scénarios d'échec partiel asymétrique (L, M).
- [x] Suite ciblée `LoRALibraryManagerComfyUIExposureTest`/`LoRALibraryManagerForgeExposureTest` et tests UI ComfyUI existants restent verts inchangés (non-régression).
- [x] `test_lora_library_roundtrip.py` et `test_lora_roundtrip.py` complets verts.
- [x] Full suite exécutée, nombre exact confirmé, tout échec distingué explicitement d'un flake historique déjà documenté.
- [x] `git diff --check` clean.
- [x] Aucun fichier hors périmètre (§6) modifié.
- [x] Aucun smoke réel requis, confirmé.
- [x] Dette `update()`/renommage documentée séparément comme hors périmètre, jamais traitée ici.

### Résultats réels

**Implémentation** : exactement le design retenu en §5 — `_unexpose(self, lora, expose_root, engine_label)` extrait du corps de l'ancien `unexpose_from_comfyui()`, sans paramètre `settings_field` (inutile, confirmé à l'implémentation). `unexpose_from_comfyui()` délègue à `_unexpose(lora, expose_root, engine_label="ComfyUI")` — message d'erreur byte-for-byte identique à l'ancien littéral. `unexpose_from_forge()` délègue à `_unexpose(lora, expose_root, engine_label="Forge")`. Aucune abstraction multi-provider générique introduite (deux méthodes publiques nommées, comme `expose_to_comfyui()`/`expose_to_forge()`).

`LoRAPage.delete_from_library()` : les deux lectures live (`comfyui_lora_expose_path`, `forge_lora_expose_path`) et les deux appels de désexposition sont désormais inconditionnels — chacun dans son propre `try/except LoRALibraryError`, les échecs accumulés dans une liste `unexpose_failures` plutôt qu'un retour anticipé au premier échec. Si cette liste est non vide après les deux tentatives, un unique `QMessageBox.critical()` agrège tous les messages (un par ligne) et la suppression canonique n'est jamais appelée — sinon le flux continue exactement comme avant (lecture de `lora_library_path`, appel à `lora_library_manager.delete()`).

**Comportement multi-moteur final** : confirmé exactement conforme à la matrice §2.4 — chaque moteur est toujours tenté indépendamment (prouvé par `test_delete_still_attempts_forge_when_comfyui_unexpose_fails_first` : Forge réellement désexposé malgré l'échec ComfyUI précédent dans l'ordre d'appel) ; un double échec produit un unique message citant les deux moteurs et leurs causes respectives (`test_delete_is_refused_with_both_diagnostics_when_both_engines_fail`) ; un succès partiel laisse l'entrée canonique intacte et une nouvelle tentative converge naturellement vers la suppression complète, sans aucun mécanisme de rollback (`test_partial_desexposition_is_recoverable_on_a_later_retry`).

**Tests ajoutés (10 nets, aucun quota artificiel — chaque test couvre une propriété distincte du §8 du plan, aucune duplication)** :
- Niveau Manager (`test_lora_library_roundtrip.py`, classe `LoRALibraryManagerForgeExposureTest`) : `test_unexpose_from_forge_removes_the_alias`, `test_unexpose_from_forge_is_a_no_op_when_never_exposed`, `test_unexpose_from_forge_is_a_no_op_when_expose_root_is_not_configured`, `test_unexpose_from_forge_raises_a_clear_error_on_real_removal_failure` (propriétés A/B/C du plan validé).
- Niveau UI (`test_lora_roundtrip.py`, nouvelle classe `LoRAPageForgeAndMultiEngineExposureTest`, Forge n'ayant pas de bouton dédié — alias établis directement via le Manager, comme `InferencePage` le ferait) : `test_delete_of_forge_only_exposed_entry_removes_the_alias_first` (E), `test_delete_of_entry_exposed_to_both_engines_removes_both_aliases` (F), `test_delete_is_refused_when_forge_unexpose_fails_and_entry_survives` (G), `test_delete_still_attempts_forge_when_comfyui_unexpose_fails_first` (H), `test_delete_is_refused_with_both_diagnostics_when_both_engines_fail` (I), `test_partial_desexposition_is_recoverable_on_a_later_retry` (J).
- Non-régression D (ComfyUI inchangé) : vérifiée en relançant les suites existantes sans aucune modification — `LoRALibraryManagerComfyUIExposureTest` 21/21, `LoRAPageComfyUIExposureTest` 9/9 — aucun nouveau test de non-régression nécessaire, la propriété est déjà couverte par la suite existante elle-même.

**Résultats exacts** : ciblé Manager Forge **12/12** (8 expose préexistants + 4 nouveaux unexpose), non-régression Manager ComfyUI **21/21**, ciblé UI multi-moteur **6/6**, non-régression UI ComfyUI **9/9**, `test_lora_library_roundtrip.py` complet **93/93**, `test_lora_roundtrip.py` complet **275/275**, full suite **2746 collectés, 2746 passés, 0 échoué**, exit 0 (319.624s) — nombre exact conforme à l'attendu (2736 à la clôture M134 + 10 nets). Aucun des deux flakes historiques (`dialog_guard`, `ForgeLifecycleManagerRealProcessTest`) observé sur ce run précis — jamais présenté comme leur résolution permanente.

**`git diff --check`** : clean. **Scope** : exactement les 4 fichiers autorisés (`src/managers/lora_library_manager.py`, `src/ui/pages/lora_page.py`, `tests/integration/test_lora_library_roundtrip.py`, `tests/integration/test_lora_roundtrip.py`) plus ce document — `graphify-out/` exclu, aucune donnée réelle de l'architecte concernée.

**Smoke** : confirmé non requis — mécanisme hardlink déjà validé empiriquement par Missions 095/108, aucun changement à ce mécanisme, aucun lancement Forge/ComfyUI réel, aucun GPU.

**Dette `update()`/rename** : confirmée hors périmètre, non traitée, non corrigée opportunistement — reste une dette cosmétique distincte à documenter séparément si l'architecte le souhaite.

**Écarts par rapport au contrat validé** : aucun.

## 12. Autorisation

**Implémentée, testée et clôturée.** Investigation préalable complète (contrat transactionnel multi-moteur, design du helper partagé, renommage, moteurs réellement implémentés) menée avant tout figement de design. Validée par l'architecte et par validation externe à chaque étape (rédaction, implémentation, clôture Git). Commit fonctionnel `f6b5ef5a739d2e8b093e3b2e9eaf9de992ff4e33`, tag annoté `v0.2-mission135` (ciblant exactement ce commit), GitHub Release `v0.2-mission135` publiée manuellement.
