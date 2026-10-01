# Mission 164 — Tolerate Sidecar Inspection Failures During Dataset Import

> **IMPLÉMENTATION VALIDÉE PAR REVUE ARCHITECTE — publication en attente.** `DatasetManager.add_images()` copiait physiquement chaque image avant d'inspecter un éventuel sidecar `.txt` de caption (`detect_caption_sidecars=True`, seul `DatasetsPage.import_images()` l'active) — un `OSError` sur `sidecar.is_file()` (verrou antivirus, partage réseau déconnecté) n'était pas catché, interrompant tout le lot en cours et laissant chaque copie déjà réalisée, y compris celle de l'image en cours, orpheline sur disque, sans référence dans `dataset.images` ni dans `project.json`. Découvert par l'audit global post-Mission 163 (candidat G), conçu READ-ONLY, puis implémenté strictement dans le périmètre validé.

## 1. Défaut initial

`src/managers/dataset_manager.py::add_images()` copie chaque fichier source (`WorkspaceStorage.copy_into_workspace()`) et construit son `Image` **avant** d'inspecter un sidecar `.txt` optionnel. `sidecar.is_file()` n'était protégé par aucun `try/except`, contrairement à `sidecar.read_text()` juste en dessous, qui catche déjà `(OSError, UnicodeDecodeError)`. Un `OSError` sur cette seule inspection (vérifié empiriquement contre le `pathlib.py` réel du projet : `is_file()` ne catche qu'un jeu restreint d'errno et relève tout le reste) remontait brut hors de `add_images()`, jamais une `WorkspaceManagerError` — seule exception interceptée par l'unique appelant, `DatasetsPage.import_images()`.

## 2. Preuve empirique et chronologie exacte

Tracé sur un lot `[img1, img2, img3, img4]`, sidecar de `img3` provoquant l'`OSError` :

| Étape | img1/img2 | img3 | img4 |
|---|---|---|---|
| Copie physique (`copy_into_workspace()`) | déjà réalisée | **déjà réalisée, avant le crash** | jamais atteinte |
| `Image` construit, ajouté à `new_images` | déjà fait | **déjà fait avant le crash** | jamais construit |
| Inspection sidecar | OK | `is_file()` lève, non catché | jamais atteinte |
| `dataset.images` / `project.json` | — | jamais mutés (boucle interrompue avant le commit) | — |
| Nettoyage Mission 067 | — | jamais atteint (scope exclusif à un échec de `save()`) | — |

La copie de l'image **courante** (img3) est orpheline au même titre que les précédentes — la copie précède l'inspection dans la même itération. `img4` n'est simplement jamais traité. Aucune divergence `project.json`/Domain (rien n'est jamais persisté), aucune source utilisateur touchée (`copy_into_workspace()` ne fait que copier).

## 3. Contrat du sidecar clarifié

| Cas | Avant M164 | Après M164 |
|---|---|---|
| Absent | aucune entrée, image importée | inchangé |
| Lisible | entrée = texte | inchangé |
| Vide | entrée explicite `caption=""` | inchangé |
| `OSError`/`UnicodeDecodeError` sur `read_text()` | déjà toléré (inchangé par cette mission) | inchangé |
| **`OSError` sur `is_file()`** | **lot entier interrompu, orphelins** | **traité exactement comme « sidecar absent » : aucune entrée, image importée, lot poursuivi** |
| `detect_caption_sidecars=False` | bloc sauté | inchangé |

## 4. Correction minimale

`sidecar.is_file()` est désormais appelé dans son propre `try/except OSError`, convertissant une inspection inconcluante en `sidecar_is_file = False` — traitement identique à un sidecar absent. Le `try/except (OSError, UnicodeDecodeError)` déjà existant autour de `read_text()` reste intact et séparé, jamais fusionné. Aucun `except Exception`, aucune nouvelle suppression, aucune nouvelle stratégie de transaction/nettoyage introduite — puisque le lot ne s'interrompt plus jamais à ce point, il n'y a plus rien à nettoyer.

**Garantie exacte** : cette correction neutralise l'`OSError` d'inspection du sidecar optionnel. Elle ne garantit pas l'absence de toute exception possible dans `add_images()`.

## 5. Fichiers modifiés

**Production (1)** : `src/managers/dataset_manager.py` — bloc d'inspection du sidecar dans `add_images()` uniquement, plus une note de docstring. Le bloc de rollback Mission 067 (persistance finale, lignes suivantes) est resté caractère pour caractère inchangé.

**Tests (1)** : `tests/integration/test_dataset_roundtrip.py` — 4 tests nets ajoutés à `DatasetManagerCaptionTest`.

## 6. Tests ajoutés

**+4 tests nets** :
- `test_sidecar_inspection_oserror_is_tolerated_like_absent_sidecar_and_batch_continues` — test principal : lot de 4 images, `Path.is_file` patché pour ne lever que sur le sidecar exact de la 3ᵉ image (délégation à l'implémentation réelle pour tout le reste, chemins inspectés tracés), vérifie les 4 images importées/référencées, les 4 copies présentes sans orphelin supplémentaire, l'absence d'entrée pour la 3ᵉ image, les captions valides conservées pour les 3 autres, les sources originales inchangées, et l'état persisté via une réouverture réelle du Workspace (pas seulement l'objet Domain en mémoire). **Vérifié échouer sur le code pré-correctif** (`OSError: simulated antivirus lock` remontant depuis `add_images()`, via `git stash` temporaire du seul fichier de production, restauré aussitôt après) puis **passer après correction**.
- `test_sidecar_read_oserror_is_tolerated_and_image_still_imported` — couverture explicite, absente jusqu'ici, du cas `OSError` déjà toléré sur `read_text()` (comportement de production inchangé par cette mission). Corrigé après revue : preuve non ambiguë qu'une image est réellement importée (identifiants avant/après, `result.added == 1`, nouvel identifiant distinct des existants) plutôt qu'un simple `dataset.images[-1]` ; injection ciblée sur le seul chemin du sidecar fautif (délégation à `Path.read_text` réelle pour tout autre chemin), tentative de lecture fautive tracée et affirmée.
- `test_sidecar_read_unicode_decode_error_is_tolerated_and_image_still_imported` — couverture explicite, absente jusqu'ici, du cas `UnicodeDecodeError` déjà toléré (sidecar réel non-UTF-8, aucun mock). Corrigé après revue : même preuve non ambiguë d'import réel qu'au point précédent.
- `test_sidecar_inspection_oserror_tolerated_then_save_failure_rolls_back_via_m067` — scénario combiné : l'`OSError` d'inspection est toléré pendant le lot, puis la sauvegarde finale échoue — vérifie que le rollback Mission 067 reste intégralement correct (Domain restauré, les deux copies nettoyées, aucun fichier préexistant touché, sources préservées).

## 7. Résultats

- Test principal : **vérifié échouer avant correction, passer après** (voir section 6).
- `DatasetManagerCaptionTest` ciblée, résultats ciblés fraîchement réexécutés après la correction des deux tests de lecture (section 6, aucun changement de production) : **19/19**.
- `test_dataset_roundtrip.py` complet, résultats ciblés fraîchement réexécutés après cette même correction : **141/141**.
- `git diff --check` : clean.
- Exactement 1 fichier de production modifié (`src/managers/dataset_manager.py`), aucun deuxième — confirmé inchangé depuis la revue pré-commit.

**Suite complète — trois tentatives, les deux incidents conservés dans la traçabilité et jamais effacés par la réussite ultérieure** :
1. Première tentative (arrière-plan) : blocage sans sortie, interrompue après diagnostic. Origine exacte non établie — le lanceur de tâche de l'outil (hors dépôt) est suspecté sur la base d'un CPU quasi nul et de l'absence de tout processus enfant, mais ceci n'établit pas avec certitude qu'aucun test n'a été atteint. **Non comptée comme résultat.**
2. Deuxième tentative (arrière-plan, `-v` ajouté) : progression réelle confirmée (centaines de noms de tests réels avec résultats), puis **crash natif, code de sortie 139**, pendant `test_forge_lifecycle_manager.py::ForgeLifecycleManagerReadinessTimeoutCleanupConfirmationTest.test_readiness_timeout_with_taskkill_success_confirms_cleanup` (dernier test commencé, identifié avec certitude, jamais terminé). Un précédent d'instabilité native de ce même fichier est documenté par les missions antérieures (97/99/100/133) d'après les éléments consultés, mais la cause exacte de **ce** crash précis et son indépendance causale vis-à-vis du diff de cette mission ne sont pas démontrées ici — aucun diagnostic élargi Forge/Qt n'a été mené, hors périmètre de Mission 164. **Non comptée comme résultat.**
3. Troisième tentative (premier plan) : **2970 collectés/2970 passés, 0 échoué, exit 0 (357.558s)**. Équation : 2966 (clôture Mission 163) + 4 nets ajoutés par Mission 164 = **2970**, cohérent. Aucune occurrence `FAIL`/`ERROR` dans la sortie complète. **Seule exécution complète réussie obtenue** — elle ne constitue pas une preuve d'absence de cause réelle aux deux incidents précédents, simplement conservés ci-dessus pour mémoire. Cette exécution est **antérieure** à la correction des deux tests de lecture (section 6) ; elle n'a pas été rejouée depuis, ce qui n'était pas requis pour cette seule correction de tests sans changement de production — les résultats ciblés fraîchement réexécutés après cette correction (19/19, 141/141, ci-dessus) couvrent le code réellement modifié depuis.

## 8. Limitations et hors périmètre, non traitées par cette mission

- `LoRALibraryManager._expose()` (candidat A de l'audit post-M163) reste ouvert — la question des effets partiels possibles de `mkdir()` (sous-dossier `AIStudioToolkit` créé puis `os.link()` échouant ensuite) n'est pas tranchée ni traitée ici, hors périmètre strict de cette mission.
- `TrainingManager.create_job()` : `training_config_path.is_file()` non protégé (piste distincte, non fusionnée avec la dette de structure `config["concepts"][0]`) reste ouvert, non traité.
- Aucun autre candidat de l'audit post-M163 n'est traité par cette mission.
