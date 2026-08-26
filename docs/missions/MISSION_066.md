# Mission 066 — Safe Image Deletion Persistence

> **STATUT : MISSION ENTIÈREMENT CLOSE.** 5 tests ciblés nets nouveaux, 17/17 sur `WorkspaceManagerRemoveImagesTest`, 92/92 sur le fichier complet `test_workspace_roundtrip.py`, 49/49 sur `test_images_page.py`, suite complète 1101/1101, smoke test Qt réel exécuté et **PASS** (18/18 assertions, 3 scénarios réels). Commit fonctionnel `c06fe82569cef35ea29fc7c5ce47da6a7f921f33`, tag annoté `v0.2-mission066`, GitHub Release publiée. Voir section 12 pour l'état de clôture Git final.

## 1. Contexte

Le mini-audit transactionnel post-Mission 065 a démontré, par expérimentation réelle (scripts jetables, jamais commités), que `WorkspaceManager.remove_images()` supprimait physiquement chaque fichier (`Path.unlink()`) **avant** toute mutation du Domain et tout appel à `save()`. Deux scénarios dangereux ont été reproduits empiriquement :

- **`save()` échoue après que tous les `unlink()` ont réussi** : les fichiers sont définitivement détruits, mais `project.json` continue de les référencer — confirmé après réouverture du Workspace, qui prétend toujours que les fichiers existent alors qu'ils ont disparu du disque. Perte de données réelle et silencieuse.
- **Un `unlink()` échoue au milieu d'un lot** : l'exception levée est un `PermissionError` brut, jamais convertie en `WorkspaceManagerError` — un guard Presentation générique ne l'aurait pas interceptée. Le Domain restait par ailleurs totalement désynchronisé du filesystem dès la première suppression physique.

## 2. Objectif

Garantir qu'**un échec de persistence ne provoque jamais la destruction d'une image encore référencée par le Workspace persistant**, en adoptant l'ordre *persistence-first* : Domain muté → `save()` → suppression physique seulement après succès de `save()`.

## 3. Contrat implémenté

**`WorkspaceManager.remove_images()`** (`src/managers/workspace_manager.py`) réordonné :

1. Classification pure (sans aucune I/O de suppression) des chemins demandés en `to_delete` (interne + présent sur disque) et `reference_only` (externe et/ou déjà absent) — logique de classification strictement inchangée.
2. `Workspace.images` muté en mémoire (liste sans les entrées retirées).
3. `self.save()` appelé.
4. **Si `save()` échoue** : la liste `Workspace.images` d'origine est restaurée verbatim (mêmes objets `Image`, même ordre) et l'exception `WorkspaceManagerError` est relevée — **aucun `Path.unlink()` n'a jamais été tenté**. Le rollback Domain s'est révélé simple et sûr (une seule ré-affectation de liste, aucun snapshot du Workspace entier nécessaire) — le contrat transactionnel le plus propre a donc pu être adopté : échec de persistence = aucune conséquence observable durable.
5. **Si `save()` réussit** : la suppression logique est déjà durable, quel que soit le sort des suppressions physiques. Chaque fichier de `to_delete` est alors traité indépendamment dans son propre `try/except OSError` — un échec n'interrompt jamais le traitement des fichiers suivants du lot. Les échecs sont collectés dans `RemovalResult.deletion_failed` (nouveau champ), jamais rollbackés (rollbacker le Domain à ce stade ressusciterait une suppression déjà persistée avec succès — l'inverse de ce qu'un échec purement filesystem doit produire).

**`RemovalResult`** étendu d'un quatrième champ `deletion_failed: List[str]` — réutilisation du type existant, aucune nouvelle infrastructure introduite.

**`ImagesPage.delete_selected_images()`** (`src/ui/pages/images_page.py`) adapté au strict nécessaire :
- Un `WorkspaceManagerError` levé par `remove_images()` (persistence échouée avant toute suppression physique) affiche `QMessageBox.critical()` — aucun fichier n'a été détruit, l'action n'est jamais présentée comme réussie.
- Un `result.deletion_failed` non vide (persistence réussie mais un ou plusieurs `unlink()` en échec) affiche `QMessageBox.warning()` reflétant la réalité exacte : les images ont bien été retirées du projet, certains fichiers n'ont simplement pas pu être supprimés du disque. Les images ne sont jamais réintroduites dans le Workspace ; aucun refresh manuel supplémentaire n'est ajouté — la galerie se met déjà à jour via le câblage `WORKSPACE_SAVED` préexistant, puisque `save()` a réussi.

**Aucun événement nouveau introduit.** `WORKSPACE_SAVED` continue de n'être publié qu'en cas de succès de `save()`, exactement comme avant — l'ordre persistence-first fait que ce même événement, déjà câblé, suffit à refléter l'état persisté dans la galerie, même quand une suppression physique échoue ensuite.

**Cas du fichier déjà absent** (§7 du mandat) : comportement préexistant strictement conservé — un chemin déjà manquant sur disque reste classé `reference_only` avant même d'atteindre la logique de suppression physique, jamais transformé en échec.

## 4. Hors périmètre (explicitement confirmé, non traité)

- `WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()` — mutations additives filesystem, candidat distinct conservé pour un futur audit (voir section 9).
- `InferencePage._on_accept_clicked()` — sa cause racine (rollback de `WorkspaceManager.add_images()`) appartient au même candidat futur, non traitée ici.
- Les ~30 handlers Type 1 de l'audit A-3 (aucune opération filesystem) — reportés sur instruction explicite de l'architecte.
- A-4 (libellés de liste obsolètes après renommage) — candidat de repli inchangé.
- Toute architecture transactionnelle générale des Managers — aucune généralisation introduite, correctif strictement local à `remove_images()`.

## 5. Risques

- **Risque de régression fonctionnelle** : faible — la logique de classification (interne/présent → suppression réelle ; externe/absent → retrait de référence seul) est strictement inchangée, seul l'ordre des opérations et la granularité de gestion d'erreur ont changé.
- **Risque de perte de données résiduelle** : éliminé pour le scénario audité (`save()` en échec) — démontré par expérimentation réelle avant et après le correctif.

## 6. Pourquoi maintenant

Risque de perte de données réelle et démontrée par expérimentation directe (mini-audit transactionnel post-Mission 065) — priorité explicitement confirmée par l'architecte comme la plus élevée parmi les candidats identifiés.

## 7. Tests automatisés ajoutés

**5 tests nets nouveaux** :

- `tests/integration/test_workspace_roundtrip.py`, classe `WorkspaceManagerRemoveImagesTest` (3 nouveaux, 2 tests existants étendus avec une assertion explicite `deletion_failed == []`) :
  - `test_remove_images_when_save_fails_deletes_no_file_and_restores_domain` — le test de sécurité principal : `save()` mocké en échec, aucun `unlink()` exécuté, tous les fichiers existent toujours, `project.json` conserve son état précédent, Domain restauré exactement (mêmes objets), exception `WorkspaceManagerError` propagée.
  - `test_remove_images_batch_survives_one_unlink_failure_and_reports_it` — lot A/B/C, `unlink()` de B échoue : A et C supprimés, B reste physiquement présent, aucun des trois n'est plus dans le Domain ni dans `project.json`, `result.deletion_failed == [B]`.
  - `test_remove_images_collects_every_unlink_failure_not_only_the_first` — lot de 4, deux échecs (B et D) : les deux sont collectés, A et C bien supprimés, le traitement n'est jamais interrompu par le premier échec.
- `tests/integration/test_images_page.py`, classe `ImagesPageTest` (2 nouveaux) :
  - `test_delete_confirmed_but_save_fails_shows_error_and_deletes_nothing` — `QMessageBox.critical` appelé, aucun fichier détruit, galerie inchangée (aucun refresh, cohérent avec l'absence de `WORKSPACE_SAVED`).
  - `test_delete_confirmed_but_unlink_fails_shows_warning_and_still_persists_removal` — `QMessageBox.warning` appelé (jamais `critical`), fichier orphelin toujours présent sur disque, mais Domain et galerie reflètent bien la suppression persistée.

Comportement observable testé (fichiers réels sur disque, `project.json` réellement relu, widgets Qt réels), jamais l'existence interne d'un mécanisme. Le test préexistant `test_delete_blocked_when_image_is_referenced_by_a_dataset` (garde Mission 062) reste intact et vert, non modifié.

## 8. Vérifications finales — réellement exécutées

**Tests ciblés** — **5/5 nets nouveaux PASS**. `WorkspaceManagerRemoveImagesTest` complet — **17/17 PASS**. `test_workspace_roundtrip.py` complet — **92/92 PASS**. `test_images_page.py` complet — **49/49 PASS**. Non-régression croisée (`DatasetsPage`, `InferencePage`, cache des vignettes) — **132/132 PASS** (`test_datasets_page.py` + `test_inference_page.py` + `test_thumbnails.py`).

`git diff --check` : propre, aucun avertissement de contenu (seuls des avertissements de normalisation LF/CRLF, déjà présents avant cette mission).

**Périmètre du diff** : exactement 4 fichiers — `src/managers/workspace_manager.py` (production, réordonnancement de `remove_images()` + extension de `RemovalResult`), `src/ui/pages/images_page.py` (production, gestion Presentation de `WorkspaceManagerError`/`deletion_failed`), `tests/integration/test_workspace_roundtrip.py`, `tests/integration/test_images_page.py`. Aucun fichier Domain/EventBus/`add_images()`/`set_thumbnail()`/`InferencePage`/autre Manager touché.

## 9. Suite complète

**1101/1101 tests verts** (1096 précédents + 5 nets nouveaux), une exécution complète `unittest discover`, aucun crash, aucun échec.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

`ImagesPage`/`WorkspaceManager` réels, fichiers réels sur disque, `project.json` réellement relu à chaque étape, `QMessageBox` mocké uniquement pour éviter un modal bloquant (convention déjà établie).

1. **Scénario normal** : suppression d'une image réelle confirmée → galerie vide, `Workspace.images` vide, fichier physiquement supprimé, `project.json` ne le référence plus.
2. **Échec de persistence injecté** : `WorkspaceStorage.save()` mocké en échec → `QMessageBox.critical` affiché (jamais `warning`), fichier toujours présent sur disque, `Workspace.images` et `project.json` conservent la référence (Domain restauré), galerie inchangée (aucun refresh, cohérent avec l'absence de `WORKSPACE_SAVED`).
3. **Échec filesystem post-`save()` sur un lot de 3** : un `unlink()` intermédiaire échoue → `QMessageBox.warning` affiché (jamais `critical`), les deux autres fichiers réellement supprimés, le fichier problématique conservé (orphelin), `Workspace.images`/`project.json` ne référencent plus aucun des trois, galerie cohérente avec l'état persisté.

**Verdict : PASS**, 18/18 assertions vérifiées (`m066_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## État d'avancement

- Décision de périmètre (persistence-first, sans corbeille temporaire) : **validée par l'architecte** à l'issue du mini-audit transactionnel.
- Implémentation : **réalisée, conforme au contrat** — réordonnancement de `remove_images()`, rollback Domain simple et local en cas d'échec de `save()`, gestion indépendante par fichier des échecs `unlink()` post-`save()`.
- Tests automatisés : **exécutés, verts — 5/5 ciblés nets nouveaux, 17/17 classe dédiée, 92/92 fichier complet Workspace, 49/49 fichier complet ImagesPage, 132/132 non-régression croisée**.
- Suite complète : **1101/1101, aucun crash**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (4 fichiers exactement, aucun fichier hors périmètre touché)**.
- Smoke test Qt réel : **réalisé, PASS, 3 scénarios couverts** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (voir section 12).

## 12. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `c06fe82569cef35ea29fc7c5ce47da6a7f921f33` (`feat: make WorkspaceManager.remove_images() persistence-first`), 5 fichiers modifiés/créés (`src/managers/workspace_manager.py`, `src/ui/pages/images_page.py`, `tests/integration/test_workspace_roundtrip.py`, `tests/integration/test_images_page.py`, `docs/missions/MISSION_066.md`), 317 insertions(+), 22 suppressions(-).
- **Push** : `53c496d..c06fe82 main -> main`. Vérifié après coup : `HEAD == origin/main == c06fe82569cef35ea29fc7c5ce47da6a7f921f33`, divergence `0 0`.
- **Tag annoté** : `v0.2-mission066`, message « Mission 066 - Safe Image Deletion Persistence », objet `a8d33cb335fd015653c8dc7315976fb1d26d5fb7`, peeled sur `c06fe82569cef35ea29fc7c5ce47da6a7f921f33` — vérifié identique en local et à distance (`git ls-remote --tags`).
- **GitHub Release `v0.2-mission066`** : publiée manuellement par l'architecte.
- **Régularisation documentaire post-Release** (ce commit) : mise à jour du bandeau de statut de ce document, de `docs/PROJECT_CONTEXT.md` et de `CHANGELOG.md` (nouvelle section `## v0.2-mission066`) pour refléter l'état Git/Release réel désormais clos. Le tag `v0.2-mission066` reste sur le commit fonctionnel `c06fe82` — non déplacé par ce commit de régularisation, purement documentaire.
- **Segfault Qt/PySide6** : ne s'est pas manifesté pendant la validation de cette mission (1101/1101 propre) — observation de stabilité, non une preuve de correction. Cause racine toujours non isolée ; l'hypothèse simple de cleanup `QThread` reste expérimentalement réfutée (audit post-Mission 064). Aucune modification visant ce sujet n'a été apportée dans Mission 066.
