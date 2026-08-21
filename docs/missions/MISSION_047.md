# Mission 047 — LoRA Metadata Fiche

> **STATUT : IMPLÉMENTATION TERMINÉE ET VALIDÉE TECHNIQUEMENT — CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> 19/19 tests ciblés (`LoRAManagerMetadataTest` + extensions UI de `LoRARoundTripTest`), 811/811 tests automatisés verts, smoke test manuel réel du rendu Qt PASS. Aucun commit, tag ni Release n'existe encore pour cette mission (voir "Principe de non-auto-référence", `docs/PROJECT_CONTEXT.md`) — voir la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

`LoRA` (`src/domain/lora.py`) sérialise depuis toujours cinq champs de métadonnées — `engine`, `architecture`, `trigger_word`, `version`, `thumbnail` — mais un audit exhaustif (`grep` sur `src/`/`tests/`) confirme qu'aucun d'eux n'est exposé nulle part au-delà du Domain : `LoRAPage` n'affiche que `name` et le nombre de fichiers, `LoRAManager` ne possède aucune méthode `update()`, et `test_lora_roundtrip.py` ne les exerce jamais au-delà de leurs valeurs par défaut. Ces champs restent bloqués à `""` de façon permanente depuis leur introduction (Mission 006 pour `LoRA` elle-même).

Un mini-audit dédié a établi les constats suivants avant toute décision :

- **`engine`/`architecture`** — aucune taxonomie multi-engine n'existe dans le projet (ComfyUI reste le seul Engine implémenté) ; toute liste fermée serait prématurée. **Décision validée par l'architecte** : champs texte libres, sans validation spécifique à un moteur.
- **`trigger_word`/`version`** — champs texte simples, sans ambiguïté. `trigger_word` est une métadonnée propre à la LoRA (le mot-déclencheur associé au fichier LoRA lui-même), **distincte** de `Character.trigger_token` (Mission 026, propre à l'identité du personnage) — les deux ne doivent jamais être confondus ni fusionnés.
- **`thumbnail`** — audit approfondi :
  - Le Blueprint (`04_DOMAIN_MODEL.md` §12 "LoRA") ne liste pas `Thumbnail` parmi les attributs LoRA ; le champ a été nommé par emprunt au vocabulaire Blueprint de `Model`/`Workflow` (§10/§14), pas d'une convention propre à LoRA.
  - `03_PROJECT_STRUCTURE.md` §13 "Models" documente `models/` (incluant LoRA) comme des ressources **partagées entre Workspaces** — signal allant à l'encontre d'une copie de la ressource LoRA elle-même dans un Workspace particulier.
  - `LoRAManager.add_files()` ne copie jamais les fichiers LoRA sélectionnés (`WorkspaceStorage.copy_into_workspace()` jamais appelée) — chemins absolus externes, choix déjà documenté et assumé (`docs/PROJECT_CONTEXT.md`, besoin "Import d'images" : *"Models/Workflows/LoRA restent systématiquement des chemins absolus externes, jamais copiés — hors périmètre assumé de Mission 028"*).
  - `WorkspaceManager._remap_path()` (Mission 027) traite déjà `Character.loras[].thumbnail` exactement comme `.files` — remappé s'il se trouve être interne, laissé intact sinon (`test_model_workflow_lora_internal_paths_are_remapped`, `test_workspace_roundtrip.py`).
  - Précédent transversal confirmé : aucun Manager du projet ne nettoie jamais les fichiers physiques d'une entité supprimée (`DatasetManager.delete()` laisse orphelin le dossier `datasets/<dataset_id>/` créé par Mission 028) — un comportement établi et accepté, pas une régression à éviter.
  - `WorkspaceStorage.DIRECTORIES` scaffold déjà `models/loras` à la création de tout Workspace.

**Décision produit arbitrée par l'architecte** (après présentation des deux options) : une miniature choisie depuis le disque est copiée dans le Workspace (`WorkspaceStorage.copy_into_workspace()`, réutilisée telle quelle), **uniquement pour `thumbnail`** — `LoRA.files` reste inchangé, toujours externe/non copié. La distinction retenue : `thumbnail` est une image d'illustration/aperçu, pas "la ressource LoRA" elle-même que le Blueprint qualifie de partagée entre Workspaces.

## 2. Problème

Il n'existe aujourd'hui aucun moyen de consulter ou modifier `engine`, `architecture`, `trigger_word`, `version` ou `thumbnail` d'une LoRA depuis AI Studio Toolkit, alors que ces champs sont déjà prévus, sérialisés et persistés par le Domain depuis l'origine.

## 3. Objectif

Permettre de consulter et modifier les métadonnées d'une LoRA sélectionnée (`engine`, `architecture`, `trigger_word`, `version`, `thumbnail`), avec une miniature copiée dans le Workspace lors de sa sélection, sans introduire de sélection LoRA multi-engine ni de système de gestion d'assets général.

## 4. Contrat fonctionnel validé

### 4.1 `engine` / `architecture` / `trigger_word` / `version`

Quatre champs texte libres (`QLineEdit`), édités et persistés via une nouvelle méthode `LoRAManager.update()`, strictement idempotente (même contrat que `CharacterManager.update()`) :
- Une valeur `None` laisse le champ inchangé (non fourni).
- Une chaîne vide est une valeur explicite et légitime, distincte de "non fourni".
- Si aucune valeur fournie ne diffère de l'état actuel : aucune mutation, aucun `save()`, retour `False`.
- Si au moins une valeur diffère : mutation des champs concernés, un seul `save()`, retour `True`. Aucun événement publié (mêmes conventions que `CharacterManager.update()`).

Aucune liste fermée, aucune validation métier sur le contenu (conforme à CLAUDE.md : aucune validation de contenu dans les Managers).

### 4.2 `thumbnail`

Nouvelle méthode dédiée `LoRAManager.set_thumbnail(lora_id, source_path)`, distincte de `update()` car elle exécute une opération d'E/S (copie), pas une simple mutation de champ :
- Le fichier choisi est copié via `WorkspaceStorage.copy_into_workspace()` vers `<workspace_root>/models/loras/<lora_id>/` (sous-dossier par `lora_id`, filesystem-safe, jamais de collision entre LoRA — même convention que `datasets/<dataset_id>/`, Mission 028).
- Une source déjà interne au Workspace est reconnue et réutilisée telle quelle, sans nouvelle copie (comportement déjà garanti par `copy_into_workspace()`).
- `LoRA.thumbnail` est mis à jour avec le chemin résultant, `WorkspaceManager.save()` appelé une seule fois.
- Aucun nettoyage de l'ancienne miniature lors d'un remplacement (fichier orphelin laissé sur disque) — cohérent avec le comportement déjà établi ailleurs dans le projet (`DatasetManager.delete()`), assumé, non traité par cette mission.
- Échec de copie (`WorkspaceStorageError` — source introuvable, disque plein, etc.) : aucune mutation, `set_thumbnail()` retourne `None`, `LoRAPage` affiche un message d'erreur, sans jamais planter.

### 4.3 Aperçu de la miniature

`LoRAPage` affiche la miniature de la LoRA active dans un `QLabel` dédié, avec la même discipline de repli qu'`ImagePreviewDialog` (`isNull()` sur le `QPixmap` chargé, texte de repli plutôt qu'un crash) :
- `thumbnail == ""` (aucune miniature choisie) → texte "Aucune miniature."
- `thumbnail` non vide mais fichier manquant/invalide → texte "Image indisponible : fichier introuvable ou illisible." (réutilisation exacte du message déjà établi par `ImagePreviewDialog.UNAVAILABLE_MESSAGE`).
- `thumbnail` valide → `QPixmap` chargé et affiché, mis à l'échelle (`Qt.KeepAspectRatio`/`Qt.SmoothTransformation`), taille de repère 128×128 (cohérent avec les autres miniatures du projet).

### 4.4 Sauvegarde

Bouton explicite « Enregistrer les métadonnées », mirroir exact de `CharactersPage.save_identity_button`/`PromptsPage`'s « Enregistrer le texte » — **aucun auto-save au changement de champ**, cohérent avec la seule convention réellement établie dans l'application pour ce type de fiche. Le choix d'une nouvelle miniature (bouton « Choisir une miniature… ») est en revanche appliqué immédiatement au clic (comme `import_files()`/`add_files()` déjà existants dans `LoRAPage`, qui persistent dès la sélection de fichiers, sans bouton "Enregistrer" séparé) — cohérent avec le fait que la copie physique est un acte immédiat et non un simple brouillon de texte.

### 4.5 Repeuplement / vidage de la fiche

La fiche de métadonnées suit la LoRA active (`on_lora_selection_changed()`/`update_loras()` déjà existants) :
- Changement de LoRA active → les 4 champs texte et l'aperçu miniature sont repeuplés depuis la nouvelle LoRA active.
- Aucune LoRA active (aucune sélection, ou liste vide) → les 4 champs sont vidés, l'aperçu affiche "Aucune miniature.", le bouton « Choisir une miniature… » et le bouton « Enregistrer les métadonnées » sont désactivés (mirroir du mécanisme d'état déjà en place pour `enlarge_button`/`delete_button` dans `ImagesPage`/`DatasetsPage`).

## 5. Périmètre

Production (2) :
- `src/managers/lora_manager.py` (nouvelles méthodes `update()`, `set_thumbnail()`)
- `src/ui/pages/lora_page.py` (nouvelle section fiche : 4 champs texte, aperçu miniature, bouton de sélection, bouton d'enregistrement, extension du repeuplement/vidage)

Tests (1) :
- `tests/integration/test_lora_roundtrip.py` (extension — ce fichier contient déjà à la fois les tests Manager et les tests Qt réels de `LoRAPage`, convention propre à LoRA depuis son origine ; aucun nouveau fichier créé)

## 6. Hors périmètre

- Sélection de LoRA multi-engine/multi-moteur (besoin distinct, non refermé par cette mission — voir `docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés").
- Toute liste fermée ou validation métier pour `engine`/`architecture`.
- Renommage de la LoRA (`name`) — reste géré exclusivement par la création (`create_lora()`), non touché par cette mission.
- Nettoyage rétroactif ou système de gestion d'assets général (pas de suivi de miniatures orphelines, pas de suppression de fichier lors du remplacement ou de la suppression d'une LoRA).
- Toute modification de `Character`, `CharacterManager`, `Dataset`, `DatasetManager`, `Workspace`, ou de tout autre Domain/Manager.
- Tout nouveau wiring EventBus au-delà de `WORKSPACE_SAVED` déjà existant.

## 7. Wiring de rafraîchissement — aucun ajout

```
LoRAPage.save_metadata()
  → LoRAManager.update(lora_id, engine=..., architecture=..., trigger_word=..., version=...)
  → WorkspaceManager.save() (uniquement si mutation réelle)
  → événement WORKSPACE_SAVED
  → LoRAPage.update_loras() (déjà abonné depuis MainWindow)

LoRAPage.choose_thumbnail()
  → LoRAManager.set_thumbnail(lora_id, source_path)
  → WorkspaceStorage.copy_into_workspace() (E/S)
  → WorkspaceManager.save()
  → événement WORKSPACE_SAVED
  → LoRAPage.update_loras()
```

Aucune souscription EventBus nouvelle.

## 8. Stratégie d'implémentation — réellement mise en œuvre

**`LoRAManager`** :
- `update(lora_id, engine=None, architecture=None, trigger_word=None, version=None) -> bool` — mirroir exact de `CharacterManager.update()` (idempotence, `None` = non fourni, chaîne vide légitime, aucun événement publié).
- `set_thumbnail(lora_id, source_path) -> Optional[str]` — `destination_folder = workspace.root / "models" / "loras" / lora.lora_id`, appelle `WorkspaceStorage.copy_into_workspace(Path(source_path), destination_folder, workspace.root)` (aucun `target_name`, comportement automatique de `resolve_collision_free_name()` conservé, comme tout appelant programmatique existant), capture `WorkspaceStorageError` → retourne `None` sans muter ni sauvegarder ; en cas de succès, `lora.thumbnail = str(effective_path)`, `save()`, retourne le chemin.

**`LoRAPage`** : nouvelle section sous les fichiers de la LoRA — `QFormLayout` avec `engine_edit`/`architecture_edit`/`trigger_word_edit`/`version_edit` (`QLineEdit`) ; `thumbnail_label` (`QLabel`, taille de repère 128×128) avec `choose_thumbnail_button` (« Choisir une miniature… », `QFileDialog.getOpenFileName`, filtre `"Images (*.png *.jpg *.jpeg *.webp *.bmp)"`, mirroir exact du filtre déjà utilisé par `ImagesPage.import_images()`) ; `save_metadata_button` (« Enregistrer les métadonnées »). `update_loras()` étendu pour peupler/vider ces widgets selon `lora_manager.active_lora` (même mécanisme que `active_files` déjà présent dans cette méthode) et pour activer/désactiver `choose_thumbnail_button`/`save_metadata_button` selon la présence d'une LoRA active.

Aucun changement `CharacterManager`, `DatasetManager`, `Domain`, `EventBus`. La couche Presentation n'exécute elle-même aucune copie de fichier — `set_thumbnail()` reste seule responsable de l'E/S, comme `add_images()`/`add_files()` déjà existants.

## 9. Stratégie de tests — réellement mise en œuvre

`test_lora_roundtrip.py` (extension, aucun nouveau fichier) :
- Nouvelle classe `LoRAManagerMetadataTest` (13 tests) : `update()` — mutation réelle de 4 champs et persistance (reopen), idempotence (valeur identique → `False`), `None` laisse un champ inchangé pendant qu'un autre est modifié, chaîne vide acceptée comme valeur légitime, LoRA inconnue → `False` ; `set_thumbnail()` — copie réelle d'un fichier externe sous `models/loras/<lora_id>/` (source intacte), source déjà interne réutilisée sans nouvelle copie, `LoRA.files` jamais touché par un appel à `set_thumbnail()`, échec de copie (`WorkspaceStorageError` simulée) → `None` et valeur précédente strictement conservée, LoRA inconnue → `None`, persistance après fermeture/réouverture (fichier physique confirmé sur disque après reopen), remplacement d'une miniature existante → nouvelle copie distincte, ancien fichier toujours présent (comportement assumé, non nettoyé).
- `LoRARoundTripTest` (+6 tests, widgets Qt réels) : fiche vidée et boutons désactivés sans LoRA active, fiche peuplée à la sélection puis correctement remplacée au changement de LoRA (values distinctes vérifiées), sauvegarde réelle des 4 champs via `save_metadata()`, sélection réelle d'un fichier de miniature (`QFileDialog.getOpenFileName` patché) copiant le fichier et affichant un `QPixmap` réel non nul, aperçu affichant le texte de repli exact (`UNAVAILABLE_MESSAGE`) pour un `thumbnail` pointant vers un fichier manquant, échec de copie de miniature → avertissement affiché et valeur précédente conservée.
- Non-régression : `create_lora()`/`delete_lora()`/`on_lora_selection_changed()`/`import_files()`/`add_files()` exercés sans modification par les 10 tests historiques, tous restés verts.

Aucune comparaison pixel par pixel dans les tests automatisés. **19/19 tests ciblés nets nouveaux, tous verts** (10 tests historiques + 19 nouveaux = 29/29 sur `test_lora_roundtrip.py`).

## 10. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels, vrais fichiers temporaires, clics réels via `QTest.mouseClick`/`QTest.keyClicks`). Script et capture exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Création Workspace → Character → LoRA (avec un vrai fichier `.safetensors` associé via `add_files()`) → fiche activée (`choose_thumbnail_button`/`save_metadata_button` tous deux `enabled`).
- Saisie réelle (`QTest.keyClicks`) des 4 champs Engine/Architecture/Trigger word/Version, clic réel sur « Enregistrer les métadonnées » → les 4 valeurs confirmées sur l'objet `LoRA` réel.
- Clic réel sur « Choisir une miniature… » (`QFileDialog.getOpenFileName` monkeypatché pour retourner un vrai fichier PNG externe, restauré ensuite) → fichier réellement copié sous `<workspace_root>/models/loras/<lora_id>/thumb.png`, source externe toujours intacte, `thumbnail_label` affichant un `QPixmap` réel non nul — capture `m047_01_thumbnail_set.png` confirmant visuellement la fiche complète.
- **Vérification explicite que le fichier LoRA lui-même n'a pas été touché** : `lora.files` inchangé, contenu binaire du fichier `.safetensors` identique avant/après, `models/loras/` ne contenant que le sous-dossier `<lora_id>/` créé pour la miniature.
- Changement vers une seconde LoRA sans métadonnées → fiche correctement vidée (`""`, "Aucune miniature.") ; re-sélection de la première → valeurs et miniature réelle restaurées.
- Suppression de la LoRA active → fiche correctement vidée et boutons désactivés.
- Fermeture puis réouverture réelle du Workspace (nouvelle instance de Managers/`LoRAPage`, simulant un redémarrage) → métadonnées et fichier de miniature physique tous deux confirmés restaurés à l'identique.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 11. Risques / non-régressions

- **Risque d'asymétrie `thumbnail`/`files`** : assumé et documenté (section 1) — décision explicite de l'architecte après présentation des deux options ; confirmé par test et smoke test réel que `LoRA.files` reste rigoureusement inchangé par `set_thumbnail()`.
- **Risque de confusion `trigger_word`/`trigger_token`** : écarté par nommage distinct déjà existant dans le Domain, aucun champ partagé, aucune conversion entre les deux.
- **Risque de fichier orphelin lors d'un remplacement de miniature** : assumé, cohérent avec le comportement déjà établi (`DatasetManager.delete()`), confirmé par test dédié (l'ancien fichier reste présent après un remplacement), non traité comme une régression à corriger dans cette mission.
- **Risque architectural** : nul — aucun changement Domain/EventBus, `CharacterManager`/`DatasetManager` non touchés, confirmé par inspection du diff complet.
- **Risque de régression sur `LoRAPage` existante** : écarté — les 10 tests historiques de `test_lora_roundtrip.py` restent verts sans modification.
- **Risque de perte silencieuse de la miniature existante en cas d'échec de copie** : écarté par construction (`set_thumbnail()` ne mute `lora.thumbnail`/n'appelle `save()` qu'après le succès de `copy_into_workspace()`) et confirmé par test dédié (`WorkspaceStorageError` simulée → valeur précédente strictement inchangée).

## 12. Critères d'acceptation — résultats

- Consultation/modification de `engine`/`architecture`/`trigger_word`/`version` d'une LoRA active, persistée — **conforme**, vérifié par test et smoke test réel.
- Idempotence stricte de `update()` (valeur identique → aucune mutation) — **conforme**.
- Miniature choisie copiée dans `<workspace_root>/models/loras/<lora_id>/`, `LoRA.thumbnail` pointant vers la copie interne — **conforme**, vérifié par test et smoke test réel (fichier physique confirmé sur disque).
- `LoRA.files` strictement inchangé par cette mission — **conforme**, vérifié par test dédié et par smoke test réel (contenu binaire identique avant/après).
- Échec de copie de miniature → `LoRA.thumbnail` inchangé, aucune sauvegarde partielle, échec signalé (`None` + avertissement UI) — **conforme**.
- Aperçu avec repli propre pour miniature absente ("Aucune miniature.") et invalide/manquante (message `ImagePreviewDialog.UNAVAILABLE_MESSAGE` réutilisé) — **conforme**.
- Fiche correctement vidée/désactivée sans LoRA active, y compris après suppression de la LoRA active — **conforme**.
- Fiche correctement repeuplée au changement de LoRA — **conforme**.
- Sauvegarde explicite par bouton, aucun auto-save au changement de champ — **conforme**.
- Persistance des métadonnées et du fichier de miniature après fermeture/réouverture — **conforme**.
- Aucun changement Domain/EventBus/`CharacterManager`/`DatasetManager` — **conforme**, confirmé par inspection du diff complet.
- Suite ciblée `test_lora_roundtrip.py` : **29/29 OK** (10 précédents + 19 nets nouveaux).
- Suite complète du projet : **811/811 OK** (792 précédents + 19 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 10) réalisé, résultat PASS.**

## État d'avancement

- Audit de sélection (candidat Mission 047), mini-audit ciblé (thumbnail, arbitrage architectural) et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 29/29 (`test_lora_roundtrip.py`, 10 précédents + 19 nouveaux), 811/811 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée** — en attente de validation technique de l'architecte avant commit/tag/Release.
