# Mission 074 — Rollback CharacterManager.update() Identity on Persistence Failure

> **MISSION ENTIÈREMENT CLOSE.** 11 tests ciblés nets nouveaux, non-régression complète 62/62 (`test_character_roundtrip.py`), suite complète 1333/1333, smoke test Qt réel exécuté et **PASS** (9/9 assertions, 3 scénarios réels : update normal, échec de persistence avec rollback mémoire/disque/widgets, retry réel). Commit `ec15312`, tag `v0.2-mission074`, GitHub Release publiée. Voir section 12 pour l'état de clôture Git final.

## 1. Contexte

L'audit post-Mission 073 a réévalué la dette regroupée depuis plusieurs missions sous l'intitulé unique « `CharacterManager.delete()`/`update()` — UI cachée, inatteignable ». Une vérification directe du code a confirmé que cette caractérisation reste exacte pour `delete()` (`CharactersPage.delete_button`/`.list_widget`/`.new_button` sont bien `setVisible(False)`, jamais réaffichés) mais **inexacte pour `update()`** : `CharactersPage.save_identity()`, branché sur `self.save_identity_button` — un bouton jamais caché, « Enregistrer l'identité » — appelle `CharacterManager.update()` sans aucune protection, ni au niveau Manager (aucun `try/except` autour de `self._workspace_manager.save()`) ni au niveau Presentation (aucune interception de `WorkspaceManagerError`). C'est le chemin d'édition principal et le plus utilisé de toute l'entité Character.

**Correction d'audit à documenter explicitement** : `CharacterManager.delete()` reste inaccessible depuis l'UI réelle (confirmé) ; `CharacterManager.update()`, à l'inverse, est actif et accessible via le bouton « Enregistrer l'identité » — les deux méthodes ne doivent plus être regroupées sous une même dette « UI cachée » dans les audits futurs.

## 2. Objectif

Appliquer à `CharacterManager.update()` un rollback local des 7 champs simultanément mutés, et protéger `CharactersPage.save_identity()` par le contrat Presentation déjà établi par Missions 070/073.

## 3. Mini-audit contractuel préalable

Relecture intégrale de `CharacterManager.update()` et de `CharactersPage.save_identity()`/`update_characters()`. Constats :

- `update()` mute exactement 7 champs (`name`/`bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token`) — confirmé par lecture complète du corps de la méthode, aucun autre champ, jamais `active_character_id`.
- `update()` **ne publie aucun événement**, avant comme après cette mission — aucun appel à `self._publish()` dans son corps, contrairement à `create()`/`delete()`/`select()` du même Manager. La clause standard « ne publier aucun événement de succès sur échec » est donc vérifiée comme un invariant déjà respecté, pas un comportement nouvellement introduit — confirmé par un test dédié plutôt que supposé.
- Contrairement aux Missions 072/073, `update()` n'avait **aucune** protection préalable : pas même un `try` nu autour de `self._workspace_manager.save()` — un cran plus bas que `LoRAManager.update()` avant Mission 073, qui avait au moins la mutation immédiate mais toujours aucune gestion d'erreur.
- Découverte architecturale clé : `WorkspaceManager.save()` publie `WORKSPACE_SAVED` uniquement **après** une écriture réussie ([workspace_manager.py:174-187](../../src/managers/workspace_manager.py)) — jamais en cas d'échec, l'exception étant levée avant. En production (`main_window.py`), **tous** les `update_X()` de Page (dont `CharactersPage.update_characters()`) sont abonnés à `WORKSPACE_SAVED` : c'est ce mécanisme, et non un événement propre à Character, qui resynchronise déjà silencieusement la fiche d'identité (et le libellé de `list_widget`) après un `save_identity()` réussi. Un échec de `save()` ne publie jamais `WORKSPACE_SAVED`, donc aucun rafraîchissement automatique n'a lieu — exactement la même mécanique déjà identifiée par Missions 070/073, appliquée ici en connaissance de cause plutôt que par simple analogie.
- Décision UX : `save_identity()` doit donc appeler explicitement `self.update_characters()` dans son bloc `except`, pour obtenir le même effet que celui que `WORKSPACE_SAVED` aurait produit sur succès — resynchronisant les 7 widgets sur les valeurs Domain restaurées. Choix directement dérivé du précédent déjà établi par `DatasetsPage.rename_dataset()` (Mission 070) et `LoRAPage.save_metadata()` (Mission 073), et justifié ici par la lecture directe du wiring réel de `main_window.py`, pas seulement par analogie avec les missions précédentes.

**Conclusion du mini-audit** : contrat de rollback local trivial (7 champs, aucun état additionnel), contrat Presentation nécessitant un rafraîchissement explicite (comme Mission 073, pas comme Mission 072) — décision UX confirmée par lecture du wiring réel de production, pas seulement par précédent.

## 4. Périmètre exact

- `src/managers/character_manager.py` — `CharacterManager.update()`.
- `src/ui/pages/characters_page.py` — `CharactersPage.save_identity()`.
- `tests/integration/test_character_roundtrip.py` — tests Manager + Presentation.
- `docs/missions/MISSION_074.md` — ce document.

Explicitement hors périmètre (confirmé par l'architecte) : `CharacterManager.delete()` (UI réellement cachée, confirmé par cette mission) ; `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; nettoyage des fichiers physiques orphelins ; segfault Qt/PySide6 (aucune nouvelle preuve).

## 5. Contrat Manager

```python
def update(self, character_id, name=None, bio=None, description=None,
           character_lock=None, personality=None, interests=None,
           trigger_token=None) -> bool:

    character = self._find(character_id)
    if character is None:
        return False

    changed = (...)
    if not changed:
        return False

    previous_name = character.name
    previous_bio = character.bio
    previous_description = character.description
    previous_character_lock = character.character_lock
    previous_personality = character.personality
    previous_interests = character.interests
    previous_trigger_token = character.trigger_token

    if name is not None:
        character.name = name
    if bio is not None:
        character.bio = bio
    if description is not None:
        character.description = description
    if character_lock is not None:
        character.character_lock = character_lock
    if personality is not None:
        character.personality = personality
    if interests is not None:
        character.interests = interests
    if trigger_token is not None:
        character.trigger_token = trigger_token

    try:
        self._workspace_manager.save()
    except WorkspaceManagerError:
        character.name = previous_name
        character.bio = previous_bio
        character.description = previous_description
        character.character_lock = previous_character_lock
        character.personality = previous_personality
        character.interests = previous_interests
        character.trigger_token = previous_trigger_token
        raise

    return True
```

Rollback purement local (même objet `Character`, 7 champs restaurés simultanément), aucun snapshot Workspace, aucune opération filesystem, aucun événement à annuler.

## 6. Contrat Presentation

`CharactersPage.save_identity()` intercepte `WorkspaceManagerError` autour de l'appel `character_manager.update()`, affiche `QMessageBox.critical()`, puis appelle `self.update_characters()` pour resynchroniser les 7 widgets de la fiche d'identité (et le libellé de `list_widget`) sur les valeurs Domain restaurées — décision justifiée dans la section 3, mirroir des précédents `DatasetsPage.rename_dataset()` (Mission 070) et `LoRAPage.save_metadata()` (Mission 073), confirmée ici par lecture directe du wiring `WORKSPACE_SAVED` de production.

## 7. Hors périmètre (explicitement confirmé, non traité)

`CharacterManager.delete()` (UI réellement cachée) ; `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; nettoyage des fichiers physiques orphelins Dataset/LoRA ; segfault Qt/PySide6 ; toute abstraction transactionnelle générique.

## 8. Risques

Minimal — mécanique déjà validée à l'identique par Missions 068/070/071/072/073, aucun état additionnel à restaurer, décision UX confirmée par lecture directe du wiring réel plutôt que par simple analogie.

## 9. Tests automatisés

**Niveau Manager** (`CharacterManagerUpdateRollbackTest`, 7 tests) : succès normal (7 champs simultanés) ; échec `save()` restaurant les 7 champs simultanément sur le même objet ; échec `save()` restaurant un seul champ modifié isolément (pour ne jamais prouver le rollback uniquement sur le cas à 7 champs) ; aucun événement publié sur échec (vérifié comme invariant, `update()` n'en ayant jamais eu) ; `project.json` inchangé après échec ; un autre Character préexistant sans rapport reste inchangé (`assertIs`) ; retry réel après rollback persistant effectivement.

**Niveau Presentation** (`CharactersPageIdentityPersistenceFailureTest`, 4 tests) : erreur affichée et le Character reste présent/visible ; Domain restauré **et** les 7 widgets resynchronisés sur les valeurs restaurées (jamais laissés sur la saisie rejetée) ; `project.json` inchangé ; retry réel effectif depuis `CharactersPage`.

**Non-régression explicite vérifiée** : `CharacterManagerUpdateTest` (idempotence, champs partiels, valeur vide légitime, persistance après fermeture/réouverture, aucun événement) reste vert sans modification ; `CharactersPageIdentityFicheTest` (fiche immédiatement peuplée, aucune fuite entre personnages, boutons multi-personnages cachés) reste vert sans modification ; l'ensemble de `test_character_roundtrip.py` (62/62) confirmé.

## 10. Smoke test Qt réel

Exécuté par Claude, `CharactersPage`/`CharacterManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, `project.json` réellement relu à chaque étape :
1. Update normal des 7 champs (succès) — persisté et reflété sur disque.
2. Échec de persistence injecté — erreur affichée, Domain restauré en mémoire aux 7 anciennes valeurs, les 7 widgets resynchronisés sur ces mêmes valeurs restaurées, Character toujours présent, `project.json` inchangé.
3. Retry réel après rollback — nouvelle tentative réussie et persistée sur disque.

**9/9 assertions PASS.**

## 11. Vérifications finales — réellement exécutées

- **Tests ciblés** : **11/11 nets nouveaux PASS** (`CharacterManagerUpdateRollbackTest`, 7 ; `CharactersPageIdentityPersistenceFailureTest`, 4).
- **Non-régression complète de `test_character_roundtrip.py`** : **62/62 PASS** (51 précédents + 11 nets nouveaux).
- **Suite complète** : **1333/1333** (1322 précédents + 11 nets nouveaux), une exécution complète `unittest discover`, 132.5s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.
- **`git diff --check`** : propre (seuls des avertissements de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 3 fichiers de production/tests — `src/managers/character_manager.py`, `src/ui/pages/characters_page.py`, `tests/integration/test_character_roundtrip.py` — plus ce document de mission.

## État d'avancement

- Mini-audit contractuel : **terminé, périmètre confirmé, correction d'audit documentée (`delete()` reste caché, `update()` était actif et non protégé)**.
- Implémentation : **réalisée, conforme au contrat M068/070/071/072/073 porté sur les 7 champs simultanés**.
- Tests automatisés : **exécutés, verts — 11/11 ciblés nets nouveaux, 62/62 non-régression complète du fichier**.
- Suite complète : **1333/1333, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (3 fichiers de code + 1 document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 3 scénarios réels couverts, 9/9 assertions** (section 10).
- Clôture Git (commit/tag/Release) : **terminée (section 12)**.

## 12. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `ec15312` (`feat: rollback CharacterManager.update() identity on persistence failure`), 4 fichiers modifiés (`src/managers/character_manager.py`, `src/ui/pages/characters_page.py`, `tests/integration/test_character_roundtrip.py`, `docs/missions/MISSION_074.md`), 459 insertions(+), 11 suppressions(-). Poussé (`7e2e4f9..ec15312`), divergence `0 0` vérifiée avant et après le push.
- **Tag annoté** : `v0.2-mission074` (message "Mission 074 - Rollback CharacterManager.update() Identity on Persistence Failure"), créé sur et poussé pour `ec1531273b63cebc5487d1b123f648961d980114`. Vérifié via `git ls-remote --tags` — objet tag `fee53d13a4fc01c9299c1bd4a4c0866cbfab1ef0`, peelé sur `ec1531273b63cebc5487d1b123f648961d980114`.
- **GitHub Release** : "v0.2-mission074 — Rollback CharacterManager.update() Identity on Persistence Failure" publiée manuellement par l'architecte.
- **État Git final vérifié post-régularisation** : working tree propre, `HEAD == origin/main == ec1531273b63cebc5487d1b123f648961d980114` (avant le commit de régularisation documentaire qui suit), divergence `0 0`, tag intact et non déplacé.
