# Mission 073 — Rollback LoRAManager.update() Metadata on Persistence Failure

> **MISSION ENTIÈREMENT CLOSE.** 11 tests ciblés nets nouveaux, suite complète 1322/1322, smoke test Qt réel exécuté et **PASS** (10/10 assertions, 3 scénarios réels : update normal, échec de persistence avec rollback mémoire/disque, retry réel). Commit fonctionnel `add35c1`, tag annoté `v0.2-mission073`, GitHub Release publiée. Voir section 12 pour l'état de clôture Git final.

## 1. Contexte

L'audit post-Mission 072 a confirmé que `LoRAManager.update()` (les 4 métadonnées texte `engine`/`architecture`/`trigger_word`/`version`) mutait ces champs en mémoire puis appelait `WorkspaceManager.save()` **sans aucun `try/except`**. `LoRAPage.save_metadata()`, son unique site d'appel Presentation, n'interceptait rien non plus. Un échec de `save()` laissait les 4 champs mutés en mémoire sans persistance ni message d'erreur — le même motif déjà corrigé pour `create()`/`delete()`/les mutations scalaires par Missions 068/070/071/072, jamais traité pour cette méthode multi-champs.

## 2. Objectif

Appliquer à `LoRAManager.update()` un rollback local des 4 champs simultanément mutés, et protéger `LoRAPage.save_metadata()` par le contrat Presentation déjà établi.

## 3. Mini-audit contractuel préalable

Relecture intégrale de `LoRAManager.update()` et de `LoRAPage.save_metadata()`/`update_loras()`. Constats :

- `update()` ne touche **aucun autre état** que les 4 champs texte — jamais `active_lora_id`, jamais `name`/`files`/`thumbnail` (chacun ayant sa propre méthode dédiée, non concernée par cette mission). Confirmé par lecture complète du corps de la méthode.
- `update()` **ne publie aucun événement**, avant comme après cette mission — même contrat que `CharacterManager.update()`. La clause standard « ne publier aucun événement de succès sur échec » est donc vérifiée comme un invariant déjà respecté (aucun événement n'existe à annuler), pas un comportement nouvellement introduit — un test dédié le confirme explicitement plutôt que de le supposer.
- `LoRAPage.save_metadata()` ne rafraîchissait rien après un appel réussi ou échoué — les 4 `QLineEdit` (`engine_edit`/`architecture_edit`/`trigger_word_edit`/`version_edit`) sont des champs de saisie directe, jamais pré-remplis par un événement au moment de l'appel. Après un succès, ils affichent déjà exactement ce que l'utilisateur a tapé, qui correspond à l'état persisté — aucun rafraîchissement nécessaire.
- Après un **échec**, sans rafraîchissement explicite, les 4 champs continueraient d'afficher les valeurs rejetées alors que le Domain aurait été restauré aux anciennes valeurs — une divergence UI/Domain réelle. Le précédent déjà établi par `DatasetsPage.rename_dataset()` (Mission 070, vérifié par lecture directe de son bloc `except`) résout exactement ce cas en appelant `self.update_datasets()` pour reconstruire le widget depuis le Domain restauré. Le même choix est retenu ici : `save_metadata()` appelle `self.update_loras()` dans son bloc `except`, resynchronisant les 4 champs (et le reste de la Page) sur les valeurs restaurées — jamais laissés sur la saisie rejetée.

**Conclusion du mini-audit** : contrat de rollback local trivial (aucun état additionnel), contrat Presentation nécessitant un rafraîchissement explicite (contrairement à Mission 071/072 où aucun n'était nécessaire) — décision UX directement dérivée d'un précédent déjà existant, pas une nouvelle décision produit.

## 4. Périmètre exact

- `src/managers/lora_manager.py` — `LoRAManager.update()`.
- `src/ui/pages/lora_page.py` — `LoRAPage.save_metadata()`.
- `tests/integration/test_lora_roundtrip.py` — tests Manager + Presentation.
- `docs/missions/MISSION_073.md` — ce document.

Explicitement hors périmètre (confirmé par l'architecte) : candidat F (`DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()`), candidat I (`SettingsManager.update()`), fichiers physiques orphelins Dataset/LoRA, `CharacterManager.delete()`/`update()`, segfault Qt/PySide6.

## 5. Contrat Manager

```python
def update(self, lora_id, engine=None, architecture=None, trigger_word=None, version=None) -> bool:

    lora = self._find(lora_id)
    if lora is None:
        return False

    changed = (...)
    if not changed:
        return False

    previous_engine = lora.engine
    previous_architecture = lora.architecture
    previous_trigger_word = lora.trigger_word
    previous_version = lora.version

    if engine is not None:
        lora.engine = engine
    if architecture is not None:
        lora.architecture = architecture
    if trigger_word is not None:
        lora.trigger_word = trigger_word
    if version is not None:
        lora.version = version

    try:
        self._workspace_manager.save()
    except WorkspaceManagerError:
        lora.engine = previous_engine
        lora.architecture = previous_architecture
        lora.trigger_word = previous_trigger_word
        lora.version = previous_version
        raise

    return True
```

Rollback purement local (même objet `LoRA`, 4 champs restaurés simultanément), aucun snapshot Workspace, aucune opération filesystem, aucun événement à annuler.

## 6. Contrat Presentation

`LoRAPage.save_metadata()` intercepte `WorkspaceManagerError` autour de l'appel `lora_manager.update()`, affiche `QMessageBox.critical()`, puis appelle `self.update_loras()` pour resynchroniser les 4 champs de métadonnées (et le reste de la Page) sur les valeurs Domain restaurées — décision justifiée dans la section 3, mirroir du précédent `DatasetsPage.rename_dataset()` (Mission 070).

## 7. Hors périmètre (explicitement confirmé, non traité)

`DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA après suppression ; `CharacterManager.delete()`/`update()` (UI cachée) ; segfault Qt/PySide6 ; toute abstraction transactionnelle générique.

## 8. Risques

Minimal — mécanique déjà validée à l'identique par Missions 068/070/071/072, aucun état additionnel à restaurer, décision UX directement dérivée d'un précédent déjà établi.

## 9. Tests automatisés

**Niveau Manager** (`LoRAManagerMetadataRollbackTest`, 7 tests) : succès normal (4 champs) ; échec `save()` restaurant les 4 champs simultanément sur le même objet ; échec `save()` restaurant un seul champ modifié isolément (pour ne jamais prouver le rollback uniquement sur le cas multi-champs) ; aucun événement publié sur échec (vérifié comme invariant, `update()` n'en ayant jamais eu) ; `project.json` inchangé après échec ; une LoRA préexistante sans rapport reste inchangée ; retry réel après rollback persistant effectivement.

**Niveau Presentation** (`LoRAPageMetadataPersistenceFailureTest`, 4 tests) : erreur affichée et la LoRA reste visible/sélectionnée dans la liste ; Domain restauré **et** widgets resynchronisés sur les valeurs restaurées (jamais laissés sur la saisie rejetée) ; `project.json` inchangé ; retry réel effectif depuis la Page.

**Non-régression explicite vérifiée** : `LoRAManagerMetadataTest` (succès, idempotence, champ `None` préservé, persistance après fermeture/réouverture) reste vert sans modification ; l'ensemble de `test_lora_roundtrip.py` (114/114) confirmé.

## 10. Smoke test Qt réel

Exécuté par Claude, `LoRAPage`/`LoRAManager`/`WorkspaceManager`/`CharacterManager` réels, Workspace temporaire réel sur disque, `project.json` réellement relu à chaque étape :
1. Update normal des 4 champs (succès) — persisté et reflété sur disque.
2. Échec de persistence injecté — erreur affichée, Domain restauré en mémoire aux 4 anciennes valeurs, widgets resynchronisés sur ces mêmes valeurs restaurées, LoRA toujours visible/sélectionnée, `project.json` inchangé.
3. Retry réel après rollback — nouvelle tentative réussie et persistée sur disque.

**10/10 assertions PASS.**

## 11. Vérifications finales — réellement exécutées

- **Tests ciblés** : **11/11 nets nouveaux PASS** (`LoRAManagerMetadataRollbackTest`, 7 ; `LoRAPageMetadataPersistenceFailureTest`, 4).
- **Non-régression complète de `test_lora_roundtrip.py`** : **114/114 PASS** (103 précédents + 11 nets nouveaux), 3.9s.
- **Suite complète** : **1322/1322** (1311 précédents + 11 nets nouveaux), une exécution complète `unittest discover`, 128.4s, aucun crash. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté.
- **`git diff --check`** : propre (seul un avertissement de normalisation de fin de ligne LF/CRLF, sans rapport).
- **Contrôle de périmètre** : exactement 3 fichiers de production/tests — `src/managers/lora_manager.py`, `src/ui/pages/lora_page.py`, `tests/integration/test_lora_roundtrip.py` — plus ce document de mission.

## État d'avancement

- Mini-audit contractuel : **terminé, périmètre confirmé, une décision UX dérivée d'un précédent existant (rafraîchissement des widgets sur échec)**.
- Implémentation : **réalisée, conforme au contrat M068/070/071/072 porté sur les 4 champs simultanés**.
- Tests automatisés : **exécutés, verts — 11/11 ciblés nets nouveaux, 114/114 non-régression complète du fichier**.
- Suite complète : **1322/1322, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (3 fichiers de code + 1 document de mission)**.
- Smoke test Qt réel : **réalisé, PASS, 3 scénarios réels couverts, 10/10 assertions** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (section 12).

## 12. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `add35c1` (`feat: rollback LoRAManager.update() metadata on persistence failure`), 4 fichiers modifiés (`src/managers/lora_manager.py`, `src/ui/pages/lora_page.py`, `tests/integration/test_lora_roundtrip.py`, nouveau `docs/missions/MISSION_073.md`), 459 insertions(+), 8 suppressions(-). Poussé (`4576009..add35c1`), divergence `0 0` vérifiée avant et après le push.
- **Tag annoté** : `v0.2-mission073` (message « Mission 073 - Rollback LoRAManager.update() Metadata on Persistence Failure »), créé sur et poussé pour `add35c18c088266371fdfd1559a5b8065239b6ed`. Vérifié via `git ls-remote --tags origin v0.2-mission073` — objet tag `12a0d2783471748e1c1bf60d95b58bfd7cbc709d`, peeled sur `add35c18c088266371fdfd1559a5b8065239b6ed`, correspondance exacte confirmée localement et à distance.
- **GitHub Release** : `v0.2-mission073 — Rollback LoRAManager.update() Metadata on Persistence Failure`, rédigée par Claude (Release Notes en anglais conformément à la convention permanente depuis Mission 024) et **publiée manuellement par l'architecte**.
- **État Git final vérifié lors de la régularisation post-Release** : working tree propre, `HEAD == origin/main == add35c18c088266371fdfd1559a5b8065239b6ed`, divergence `0 0`, tag `v0.2-mission073` intact et toujours attaché au commit `add35c1` (non déplacé par la régularisation documentaire qui suit dans un commit séparé).
