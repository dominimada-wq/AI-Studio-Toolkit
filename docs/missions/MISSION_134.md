# Mission 134 — Harden Training Concept-Folder Materialization Against Silent Partial-Wipe Contamination

> **MISSION CLÔTURÉE — commit, tag et Release publiés.** `TrainingManager._materialize_concept()` supprimait le dossier concept via `shutil.rmtree(concept_folder, ignore_errors=True)`, **hors de tout `try/except`** : un échec réel ou partiel de cette suppression était silencieusement avalé, et la boucle de copie qui suivait pouvait alors ajouter les nouvelles images à côté de fichiers résiduels d'une matérialisation précédente (jamais en écrasement, `resolve_collision_free_name()` garantit qu'aucun fichier n'est jamais écrasé) — le dossier concept cessait de refléter exactement le Dataset/Training courant, sans qu'aucune erreur ne remonte. L'investigation a également mis en évidence un second risque directement lié, dans la même méthode : si le wipe réussit mais qu'une copie échoue en cours de boucle, le dossier concept restait partiellement reconstruit sur disque, et — comme `onetrainer_config.json` n'est réécrit qu'après une matérialisation *réussie* — un `config.json` d'un `Prepare` antérieur valide restait lisible par `create_job()` (Mission 100) sans aucune revalidation, et pointerait alors vers ce dossier partiel. Le `shutil.rmtree()` brut est remplacé par la primitive Infrastructure déjà existante et déjà testée `WorkspaceStorage.delete_folder()`, avec un nettoyage best-effort en cas d'échec de matérialisation. **Le contrat exact reste non-transactionnel et explicitement documenté comme tel** : aucun échec de wipe n'est plus silencieusement accepté, aucun échec de matérialisation n'est transformé en succès, un nettoyage de récupération est tenté — et **s'il échoue lui-même, ce second échec est explicitement signalé sans jamais masquer la cause initiale, sans jamais prétendre que le dossier est garanti absent**. **+2 tests nets.** Tests ciblés **38/38** verts, `test_training_roundtrip.py` complet **361/361** vert, full suite **2736/2736/0 échoué**, aucun flake historique observé sur ce run. Aucun changement UI/Domain/translator/runtime OneTrainer. Aucun smoke requis.

## 1. Contexte

Mission 097 a introduit `_materialize_concept()` avec un commentaire explicite : le dossier concept est "wiped (best-effort) and rebuilt from scratch on every call" ([`training_manager.py:706-707`](../../src/managers/training_manager.py#L706)), pour garantir qu'une matérialisation périmée ne survit jamais à un changement de Dataset/`trigger_word`. L'implémentation de ce "best-effort" est cependant plus dangereuse que voulu :

```python
concept_folder = self._training_folder(training.training_id) / _CONCEPT_SUBFOLDER_NAME

shutil.rmtree(concept_folder, ignore_errors=True)

try:
    concept_folder.mkdir(parents=True, exist_ok=True)
    for image in dataset.images:
        ...
except OSError as exc:
    raise TrainingPreparationError(...) from exc
```
([`training_manager.py:742-759`](../../src/managers/training_manager.py#L742))

`ignore_errors=True` ne distingue jamais "dossier absent" (cas normal, à tolérer) d'un **échec réel** de suppression (fichier verrouillé par un processus externe — exactement la classe de problème `WinError 5` déjà rencontrée et documentée pour le renommage de Workspace, Mission 027) : dans les deux cas, l'exécution continue silencieusement.

## 2. Comportement exact actuel — investigation

**Création du chemin concept** : chemin déterministe, `self._training_folder(training.training_id) / "concept"` — jamais dérivé du Dataset ni du contenu, toujours le même pour un `training_id` donné.

**Suppression préalable** : `shutil.rmtree(concept_folder, ignore_errors=True)`, hors try/except, avant toute autre opération. Aucune distinction dossier-absent / échec-réel.

**Dossier absent** : `shutil.rmtree(..., ignore_errors=True)` sur un chemin inexistant ne fait rien et ne lève rien — comportement actuel déjà correct pour ce cas précis, implicitement exercé par chaque test existant (chaque test démarre d'un `tempfile.mkdtemp()` neuf, donc le concept folder n'existe jamais avant le premier appel).

**Échec de `shutil.rmtree()`** : actuellement totalement invisible — `ignore_errors=True` avale l'exception, quelle qu'en soit la cause (verrou, permission, etc.).

**`try/except` actuellement présent** : couvre uniquement `mkdir()` et la boucle de copie/écriture caption (`except OSError as exc: raise TrainingPreparationError(...)`, [`training_manager.py:756-759`](../../src/managers/training_manager.py#L756)) — **le `rmtree` lui-même n'est couvert par rien**, ce qui est la cause directe du bug.

**Type et message de `TrainingPreparationError`** : exception simple ([`training_manager.py:160-167`](../../src/managers/training_manager.py#L160)), déjà documentée comme "Raised by `prepare_onetrainer_config()` on any real failure — an unknown dataset, an empty dataset, or a filesystem failure during materialization." Le message actuel du bloc `except` existant : `f"Could not materialize the dataset concept folder for training {training.training_id!r}: {exc}"`.

**Nettoyage après une copie partiellement échouée** : **aucun**. Si l'image N sur M échoue à se copier (`shutil.copy2` ou `write_text` lève `OSError`), le bloc `except` lève `TrainingPreparationError` mais **ne touche jamais** aux N-1 fichiers déjà physiquement copiés — ils restent sur disque, formant un dossier concept partiel qui n'est ni l'ancien état ni le nouveau.

**Reconstructions successives** : le test existant `test_rerunning_rebuilds_the_concept_from_the_current_dataset_state` ([`test_training_roundtrip.py:5648`](../../tests/integration/test_training_roundtrip.py#L5648)) prouve que le chemin nominal (wipe réussi, reconstruction complète réussie) fonctionne déjà correctement — non-régression à préserver strictement.

**Tests existants autour de `_materialize_concept()`** : tous dans `TrainingManagerPrepareOnetrainerConfigTest` ([`test_training_roundtrip.py:5290`](../../tests/integration/test_training_roundtrip.py#L5290)) — matérialisation nominale avec captions (`:5334`), collision de noms entre deux sources homonymes (`:5617`), reconstruction après changement de Dataset (`:5648`), non-modification des sources (`:5638`), chemins déterministes (`:5598`). **Aucun test n'exerce un échec de suppression ni un échec de copie partielle** — confirmé par lecture exhaustive de la classe.

## 3. Point important — second risque investigué (atomicité / échec partiel de copie)

Investigation demandée : que se passe-t-il si le wipe réussit mais qu'une copie échoue en cours de boucle ?

**Constat** : le dossier concept reste partiellement reconstruit sur disque (N-1 fichiers déjà copiés, ni l'ancien état ni le nouveau), et `TrainingPreparationError` est levée — mais rien n'efface ce résidu.

**Ce second risque est directement lié au même défaut racine et n'est pas séparable proprement** — mais il **est** résoluble dans le même périmètre étroit (une seule méthode, un seul fichier), pour la raison suivante, vérifiée par lecture de `create_job()` ([`training_manager.py:950-1000`](../../src/managers/training_manager.py#L950)) :

- `create_job()` ne rappelle **jamais** `prepare_onetrainer_config()` — il lit directement `onetrainer_config.json` du disque, en faisant confiance à sa docstring : "written by the last successful Prepare" ([`training_manager.py:955-956`](../../src/managers/training_manager.py#L955)). **Aucune revalidation** de la cohérence entre ce fichier et l'état réel du dossier concept.
- `onetrainer_config.json` n'est réécrit qu'**après** une matérialisation réussie ([`training_manager.py:914-920`](../../src/managers/training_manager.py#L914)) — donc si un second `Prepare` échoue (wipe ou copie), l'ancien `config.json` (d'un premier `Prepare` réussi) **reste en place, inchangé**, tout en pointant vers un dossier concept **désormais différent** (partiellement wipé et/ou partiellement recopié par la tentative échouée).
- **Scénario concret** : Prepare #1 réussit (concept = {A, B}, config.json écrit). L'utilisateur modifie le Dataset (retire B, ajoute C), relance Prepare #2 : le wipe réussit, A est recopié, la copie de C échoue (disque plein, source disparue). Le dossier concept contient alors seulement {A} — ni l'état de Prepare #1 ({A, B}) ni celui voulu par Prepare #2 ({A, C}). `TrainingPreparationError` est bien levée par Prepare #2, **mais** l'ancien `config.json` de Prepare #1 reste lisible et syntaxiquement valide. Si `create_job()` est appelé sans qu'un nouveau `Prepare` réussi n'ait eu lieu entre-temps, il lira ce `config.json` périmé et lancerait potentiellement OneTrainer sur un dossier concept **silencieusement tronqué** ({A} seul), sans qu'aucune erreur ne le signale nulle part.

**Design qui neutralise ce second risque sans élargir le périmètre** : garantir qu'**en cas d'échec de la matérialisation, quel qu'en soit le point (wipe ou copie), une tentative de nettoyage "best-effort" du dossier concept est faite avant de signaler l'échec**. Ceci n'est **pas** une garantie transactionnelle : si ce nettoyage de récupération réussit, le scénario ci-dessus se termine avec un dossier concept absent — si `create_job()` est ensuite appelé sur la base du `config.json` périmé, OneTrainer échouerait de façon immédiatement visible (dossier introuvable), au lieu de s'entraîner silencieusement sur des données tronquées. Mais si ce nettoyage de récupération échoue à son tour (même cause racine, ex. le même verrou), des fichiers peuvent physiquement subsister — ce second échec est alors explicitement signalé dans le message d'erreur, jamais masqué, jamais présenté comme un succès. Ce mécanisme unique couvre donc le bug original (échec du wipe) et ce second risque (échec de copie), **sans toucher à `create_job()`, à `EventBus`, ni à aucun autre fichier** — conformément à la contrainte de ne pas transformer M134 en refonte transactionnelle générale.

Pas de STOP nécessaire : ce second risque est directement résolu par la même primitive, dans le même fichier, sans élargissement de périmètre au-delà de `_materialize_concept()`.

## 4. Design retenu

Remplacer le `shutil.rmtree(concept_folder, ignore_errors=True)` brut, non gardé, par la primitive Infrastructure **déjà existante et déjà testée** `WorkspaceStorage.delete_folder()` ([`workspace_storage.py:333-360`](../../src/infrastructure/storage/workspace_storage.py#L333)), dont le contrat est **exactement** celui recherché :
- chemin absent → aucune opération, aucune erreur (`if not path.exists(): return`) ;
- suppression réussie → dossier supprimé ;
- échec réel (`OSError` interne à `shutil.rmtree`) → lève `WorkspaceStorageError`, jamais silencieux.

Cette primitive est déjà utilisée pour la suppression transactionnelle de LoRA (Mission 075) et déjà réutilisée par `LoRALibraryManager` avec le même idiome de nettoyage best-effort en cas d'échec partiel de copie ([`lora_library_manager.py:214-221`](../../src/managers/lora_library_manager.py#L214) : `if not self._best_effort_delete_folder(destination_folder): raise ...Additionally, the partially copied files could not be cleaned up and remain orphaned...`). M134 applique le **même idiome déjà établi**, une troisième fois, dans la seule méthode qui en était encore dépourvue — pas une nouvelle abstraction.

```python
def _materialize_concept(self, training: Training, dataset) -> Path:
    concept_folder = self._training_folder(training.training_id) / _CONCEPT_SUBFOLDER_NAME

    try:
        WorkspaceStorage.delete_folder(concept_folder)
        concept_folder.mkdir(parents=True, exist_ok=True)

        for image in dataset.images:
            source = Path(image.file_path)
            target = WorkspaceStorage.resolve_collision_free_name(source, concept_folder)
            shutil.copy2(source, target)
            metadata = dataset.entries.get(image.image_id)
            caption = metadata.caption if metadata is not None else training.trigger_word
            target.with_suffix(".txt").write_text(caption, encoding="utf-8")
    except (WorkspaceStorageError, OSError) as exc:
        try:
            WorkspaceStorage.delete_folder(concept_folder)
        except WorkspaceStorageError:
            raise TrainingPreparationError(
                f"Could not materialize the dataset concept folder for training "
                f"{training.training_id!r}: {exc} Additionally, the partially "
                f"materialized concept folder could not be cleaned up and remains "
                f"on disk at {concept_folder} — do not start a training job for "
                f"this Training without a successful re-run of Prepare."
            ) from exc
        raise TrainingPreparationError(
            f"Could not materialize the dataset concept folder for training {training.training_id!r}: {exc}"
        ) from exc

    return concept_folder
```

**Pourquoi ce design et pas un autre plus simple** :
- Un simple `ignore_errors=False` sur le `rmtree` initial (sans le déplacer dans le `try`) aurait laissé l'exception `OSError` du wipe non convertie en `TrainingPreparationError` (incohérence de type d'exception pour l'appelant) et n'aurait rien résolu pour le second risque (échec de copie).
- Réutiliser `WorkspaceStorage.delete_folder()` plutôt que garder `shutil.rmtree()` brut aligne cette méthode sur la primitive Infrastructure déjà standard du dépôt pour ce besoin exact, au lieu de dupliquer sa logique.
- Le nettoyage best-effort en cas d'échec (qu'il survienne au wipe ou en cours de copie) est ce qui neutralise le second risque dans le cas nominal : après un `Prepare` en échec, le dossier concept est soit complet (succès), soit absent (échec avec nettoyage de récupération réussi). Ce n'est **pas** une garantie transactionnelle du filesystem : si le nettoyage de récupération échoue lui-même (même cause racine que l'échec initial), des fichiers peuvent physiquement subsister — ce cas n'est jamais masqué, voir le message enrichi ci-dessous.
- Le message d'erreur enrichi en cas de double échec (wipe/cleanup impossible) suit le **même gabarit exact** que celui déjà utilisé par `LoRALibraryManager.import_lora()` — cohérence de convention, pas une formulation nouvelle inventée pour M134.

**Import à ajouter** : `WorkspaceStorageError` doit être ajouté à l'import déjà présent de `WorkspaceStorage` ([`training_manager.py:12`](../../src/managers/training_manager.py#L12)), à la manière de `dataset_manager.py`/`lora_manager.py`/`lora_library_manager.py`/`workspace_manager.py`, qui importent déjà les deux symboles ensemble depuis le même module.

**Docstring à mettre à jour** : la phrase "the concept folder is wiped (best-effort) and rebuilt from scratch on every call" ([`training_manager.py:706-707`](../../src/managers/training_manager.py#L706)) doit être reformulée pour refléter le nouveau contrat exact (best-effort seulement au sens "dossier absent toléré", jamais au sens "échec réel ignoré").

## 5. Fichiers autorisés (vérifiés)

- `src/managers/training_manager.py` — `_materialize_concept()` (import `WorkspaceStorageError` ajouté, docstring mise à jour, logique décrite en §4).
- `tests/integration/test_training_roundtrip.py` — nouveaux tests dans `TrainingManagerPrepareOnetrainerConfigTest` (déjà présente, ligne 5290).
- `docs/missions/MISSION_134.md` (ce document, mis à jour avec les résultats réels après implémentation).

**Aucun autre fichier.** Ni `create_job()`, ni `EventBus`, ni Domain, ni translator/`OneTrainerConfig`, ni UI, ni Central LoRA Library, ni Forge ne sont modifiés — le design du §4 résout le second risque sans y toucher (voir §3).

## 6. Invariants protégés

- Une matérialisation réussie reflète exactement le Dataset/Training courant (déjà vrai, non modifié).
- Dossier absent au premier appel = cas normal, toléré silencieusement (déjà vrai, préservé par `WorkspaceStorage.delete_folder()`).
- Échec réel de suppression = `TrainingPreparationError`, plus jamais silencieux.
- **Aucun fichier d'une matérialisation précédente ne peut être silencieusement conservé après un échec de wipe** — soit le wipe réussit et la reconstruction se poursuit normalement, soit il échoue et `TrainingPreparationError` est levée avant tout `mkdir`/toute copie (aucun mélange possible).
- **Après une erreur de préparation (wipe ou copie), un dossier concept partiel ne peut jamais être interprété ultérieurement comme une matérialisation valide** : un nettoyage best-effort est toujours tenté, et lorsqu'il réussit, le dossier finit soit complet (succès), soit absent (échec) — neutralisant le second risque identifié en §3 sur `create_job()`. **Ceci n'est pas une garantie transactionnelle** : si le nettoyage de récupération échoue lui-même, des fichiers peuvent physiquement subsister sur disque — jamais silencieusement, ce second échec est toujours explicitement signalé dans le message d'erreur (voir §4), sans jamais masquer la cause initiale ni transformer l'échec en succès.
- Aucune configuration OneTrainer ne doit être considérée préparée à partir d'un dossier concept dont le nettoyage préalable a échoué — `onetrainer_config.json` n'est de toute façon jamais réécrit avant la fin réussie de `_materialize_concept()` (comportement déjà existant, non modifié, revérifié en §3).
- Reconstructions successives normales restent fonctionnelles (`test_rerunning_rebuilds_the_concept_from_the_current_dataset_state` doit continuer à passer sans modification).
- Captions/sidecars et `trigger_word` conservent leur comportement actuel à l'identique (aucune ligne de la boucle de copie/caption n'est modifiée).

## 7. Tests prévus

1. **Dossier absent** — déjà couvert implicitement par tous les tests existants (chaque test démarre d'un répertoire temporaire neuf) ; non-régression à confirmer, aucun nouveau test requis pour ce seul cas.
2. **Dossier existant, reconstruction complète réussie** — déjà couvert par `test_rerunning_rebuilds_the_concept_from_the_current_dataset_state` (`:5648`) ; non-régression stricte, doit continuer à passer sans modification.
3. **Nouveau test — échec de suppression simulé et déterministe** : pré-remplir le dossier concept avec un fichier "résiduel" d'une matérialisation antérieure, patcher `WorkspaceStorage.delete_folder` (`unittest.mock.patch.object`, `side_effect=WorkspaceStorageError("locked")`) pour tout l'appel, tenter une nouvelle préparation avec un Dataset différent → `TrainingPreparationError` obligatoire ; le résidu ne doit jamais se retrouver mélangé avec un contenu nouvellement copié (la boucle de copie ne doit jamais être atteinte) ; le message doit signaler l'échec du nettoyage best-effort (gabarit "orphaned"/"remain on disk", identique à l'idiome déjà utilisé par `LoRALibraryManager`).
4. **Nouveau test — échec de copie partielle après wipe réussi** (réponse directe au §3) : Dataset avec au moins deux images, simuler un échec déterministe sur la copie de la seconde (`unittest.mock.patch` ciblé, jamais un vrai fichier verrouillé) → `TrainingPreparationError` obligatoire, et le dossier concept doit être vidé (best-effort) plutôt que laissé avec la première image seule — preuve directe que le second risque est neutralisé.
5. **Reconstructions successives** — non-régression déjà couverte par le test existant (#2 ci-dessus) ; pas de test supplémentaire distinct nécessaire.
6. **Full suite** : nombre exact de tests confirmé après ajout des 2 nouveaux tests (#3, #4) — baseline 2734 (clôture M133) + 2 = 2736 attendus, aucune régression.

Tous les nouveaux tests utilisent des mocks/patches déterministes (`unittest.mock.patch`/`patch.object`), jamais un vrai fichier Windows verrouillé, conformément à l'instruction explicite.

## 8. Smoke

**Aucun smoke réel requis.** Confirmé depuis le code : `_materialize_concept()` et `prepare_onetrainer_config()` ne lancent jamais OneTrainer, n'importent aucun code OneTrainer, ne touchent ni au réseau ni au GPU — frontière déjà documentée et jamais franchie depuis Mission 097 (`MISSION_097.md` sections 7/8, revérifiée ici, non remise en cause par ce changement purement filesystem). `create_job()` (qui, lui, prépare un lancement réel) n'est pas modifié par cette mission.

## 9. Exclusions explicites

Aucun changement UI ; aucun changement Domain ; aucun changement translator/`OneTrainerConfig` ; aucun changement runtime OneTrainer ; aucun changement de paramètres Training ; aucun changement Central LoRA Library ; aucun changement `EventBus` ; aucun changement Forge ; aucun refactor général du filesystem au-delà de `_materialize_concept()` ; aucune migration de données existantes ; `create_job()` non modifié (le design du §4 neutralise le second risque sans y toucher — voir §3).

## 10. Critères d'acceptation

- [x] `shutil.rmtree(concept_folder, ignore_errors=True)` non gardé est remplacé par `WorkspaceStorage.delete_folder()` à l'intérieur du `try` existant.
- [x] Un échec réel de suppression lève `TrainingPreparationError`, jamais silencieux.
- [x] Un dossier absent au premier appel continue de fonctionner sans erreur (non-régression).
- [x] Un échec de copie partielle après un wipe réussi entraîne un nettoyage best-effort du dossier concept (jamais laissé partiel silencieusement — voir la nuance non-transactionnelle du §3/§4) — second risque §3 neutralisé dans le cas nominal.
- [x] Un double échec (wipe/cleanup) produit un message d'erreur explicite, sur le même gabarit que `LoRALibraryManager`, sans jamais masquer la cause initiale.
- [x] Aucun autre fichier que les 3 listés en §5 n'est modifié.
- [x] `test_rerunning_rebuilds_the_concept_from_the_current_dataset_state` et tous les tests existants de `TrainingManagerPrepareOnetrainerConfigTest` continuent de passer sans modification.
- [x] 2 nouveaux tests ajoutés (§7 points 3 et 4), tous deux verts, mocks déterministes uniquement.
- [x] Full suite : nombre exact confirmé (2736 attendus), formulation stricte sur tout flake historique observé ou non.
- [x] Aucun smoke requis, confirmé explicitement dans le rapport d'implémentation.

### Résultats réels

**Implémentation** : conforme section par section à ce document. Dans `_materialize_concept()`, `WorkspaceStorage.delete_folder(concept_folder)` déplacé à l'intérieur du `try` existant, `except (WorkspaceStorageError, OSError) as exc` (au lieu de `except OSError` seul), avec une tentative de nettoyage best-effort (`WorkspaceStorage.delete_folder(concept_folder)`) avant de lever `TrainingPreparationError` — message enrichi si ce nettoyage échoue à son tour, sans jamais remplacer la cause initiale `exc` (toujours citée dans le message, toujours chaînée via `from exc`). Import `WorkspaceStorageError` ajouté à l'import existant de `WorkspaceStorage` ([`training_manager.py:12`](../../src/managers/training_manager.py#L12)). Docstring mise à jour pour refléter le contrat exact non-transactionnel.

**Invariant final, formulé sans sur-promesse** : une matérialisation se termine soit complète et cohérente avec le Dataset/Training courant, soit avec le dossier concept absent **lorsque le nettoyage de récupération réussit**. Aucun échec de wipe n'est silencieusement accepté ; aucun échec de matérialisation n'est transformé en succès ; un nettoyage de récupération est toujours tenté après tout échec ; **si ce nettoyage échoue lui-même, des fichiers peuvent physiquement subsister sur disque, et ce second échec est explicitement signalé dans le message d'erreur, jamais masqué**. Le filesystem n'est à aucun moment présenté comme transactionnel.

**Tests ajoutés (2, conformes au §7)** : `test_wipe_failure_raises_and_never_silently_mixes_stale_files_with_new_ones` (patch global de `WorkspaceStorage.delete_folder` pour toute la durée du bloc — exerce naturellement le double échec wipe+cleanup, réaliste puisque le même verrou persisterait ; vérifie que le message contient à la fois la cause initiale et le signal du cleanup échoué, et que seuls les fichiers résiduels préexistants subsistent, jamais mélangés à un fichier fraîchement copié) et `test_copy_failure_after_successful_wipe_cleans_up_the_partial_concept_folder` (premier `shutil.copy2` réel, second patché pour échouer ; vérifie `TrainingPreparationError` et que le dossier concept est entièrement absent après coup, cleanup de récupération réussi dans ce cas). Les deux branches de l'`except` (cleanup réussi / cleanup échoué) sont ainsi couvertes sans troisième test.

**Tests ciblés** : `TrainingManagerPrepareOnetrainerConfigTest` **38/38** verts (36 existants + 2 nouveaux).

**`test_training_roundtrip.py` complet** : **361/361** verts (359 + 2 nets).

**Full suite** : **2736 collectés, 2736 passés, 0 échoué**, exit 0 (353.850s) — nombre exact conforme à l'attendu (2734 à la clôture M133 + 2 nets). Aucun des deux flakes historiques (`dialog_guard`, `ForgeLifecycleManagerRealProcessTest`) observé sur ce run précis — jamais présenté comme leur résolution permanente.

**`git diff --check`** : clean.

**Smoke** : confirmé non requis — `_materialize_concept()`/`prepare_onetrainer_config()` ne lancent jamais OneTrainer ni ne touchent au GPU, frontière non remise en cause par ce changement purement filesystem.

**Écarts par rapport au contrat** : aucun.

## 11. Autorisation

**MISSION CLÔTURÉE.** Implémentée, testée, validée par l'architecte et par validation externe à chaque étape (rédaction, implémentation, clôture). Commit fonctionnel `96be669ddfb158a31024bb944d237b07cff43736` (`Harden training concept-folder materialization against partial wipe/copy failures`), tag annoté `v0.2-mission134` ciblant exactement ce commit, GitHub Release `v0.2-mission134` publiée manuellement.
