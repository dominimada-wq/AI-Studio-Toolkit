# Mission 123 — Generation Provenance/Metadata Persistence

> **MISSION IMPLÉMENTÉE, VALIDÉE, COMMITÉE, TAGUÉE ET PUBLIÉE.** Implémentée exactement selon ce document (les 12 précisions demandées par l'architecte lors de la validation ont été intégrées avant implémentation — renommage d'attribut, cycle de vie de la metadata figé, documentation de `GenerationReference`, garde `field(default_factory=list)`, désérialisation défensive détaillée, renommage du paramètre `WorkspaceManager.add_images()`, preuve d'indépendance mémoire), validée par la suite complète (2483/2483) et par un smoke réel ComfyUI de bout en bout (anti-contamination, persistance vérifiée dans `project.json`, deux générations indépendantes, reload réel d'un Workspace). Commit fonctionnel `4745b1ba826b91421663e1b00d518f3fae7674c4` (`Add generation provenance metadata persistence`), tag `v0.2-mission123`, GitHub Release publiée manuellement.

## 1. Contexte

L'audit post-Mission 122 a établi que `src/domain/image.py::Image` ne porte que deux champs (`image_id`, `file_path`), alors qu'`InferencePage` construit déjà, à chaque clic Generate, un snapshot immuable complet de tout ce qui a réellement servi à produire le résultat : `_PendingGenerationRequest` (`src/ui/pages/inference_page.py:110-139`, introduit par la Mission 115 pour survivre à un démarrage asynchrone de ComfyUI Local). Au moment de l'acceptation (`_accept_pending_result()`, `inference_page.py:1401-1478`), seul le chemin de fichier traverse vers la persistance (`self._workspace_manager.add_images([self._pending_path])`, ligne 1465) — tout le reste du snapshot est perdu. Une fois l'image dans `Workspace.images`, il est impossible de savoir quel prompt, quelle seed, quel checkpoint ou quel LoRA l'a produite.

**Audit du cycle de vie réel du snapshot (préalable à toute décision architecturale) :**

- `_build_generation_request()` (`inference_page.py:973-1142`) lit les widgets une seule fois et retourne un `_PendingGenerationRequest` — jamais reconstruit ni relu depuis les widgets ensuite.
- `_start_generation()` (ligne 1144) appelle `_build_generation_request()` puis, soit lance immédiatement (`_launch_generation_worker(request)`), soit conserve `request` dans `self._pending_generation_request` en attendant le démarrage de ComfyUI Local (Mission 115) — cet attribut existant sert exclusivement cette attente pré-lancement, jamais la fenêtre "résultat en attente d'Accept/Reject" qui nous intéresse ici.
- `_launch_generation_worker(request)` (ligne 1292) construit le `GenerationWorker` en lui passant chaque champ du snapshot **individuellement** (`request.prompt_text`, `request.seed`, etc.) — l'objet `request` lui-même n'est aujourd'hui stocké nulle part au-delà de cet appel.
- `worker.finished` déclenche `_on_generation_finished(self, path)` (ligne 1356), qui ne reçoit que le chemin du fichier — **le snapshot n'est donc déjà plus accessible à ce point dans le code actuel**, sauf à l'y avoir explicitement conservé.
- `_set_pending(path)` (ligne 2134) enregistre `self._pending_path`/`self._pending_pixmap` — toujours aucune trace du snapshot.
- `_accept_pending_result()` (ligne 1401) n'a accès qu'à `self._pending_path` et `self._generation_workspace_root`.
- `_clear_pending(delete_file)` (ligne 2144) est le point de sortie unique partagé par Accept (succès), Reject, l'invalidation sur changement de Workspace (`reset_for_workspace_change()`) et `shutdown()` — il remet `_pending_path`/`_pending_pixmap`/`_generation_workspace_root` à `None`.

**Conclusion de l'audit** : le snapshot nécessaire à la provenance existe déjà, au bon endroit, au bon moment (`_build_generation_request()`), mais aucune référence n'est aujourd'hui conservée entre le lancement du worker et l'Accept. La mission doit ajouter cette rétention, sans toucher au principe "un seul pending à la fois" ni à aucun autre mécanisme de garde déjà en place (Missions 083-085/115-117).

**Audit du modèle de sérialisation Domain existant** : `Image.to_dict()`/`from_dict()`/`list_from_data()` suivent la convention standard du projet (garde `isinstance(entry, dict)`, tolérance des entrées `str` héritées). `WorkspaceManager.add_images()` (`src/managers/workspace_manager.py:432-551`) est l'unique point de construction des `Image` pour le pool `Workspace.images` ; il a exactement deux appelants réels : `ImagesPage.import_images()` (`images_page.py:148`, import manuel, sans aucune notion de génération) et `InferencePage._accept_pending_result()` (ligne 1465, le seul appelant concerné par cette mission). `DatasetManager.add_images()` (`dataset_manager.py:382`) est une méthode **distincte**, opérant sur `Dataset.images` (pool indépendant depuis la Mission 011, modèle d'ownership D) — hors périmètre, non touchée.

**Audit des références** : `Reference` (`reference_images: List[Reference]` du snapshot) est un `NamedTuple(path: str, role: str)` défini dans `src/managers/generation_manager.py` — **une classe de Manager, jamais de Domain**. L'importer directement dans `src/domain/` violerait la Dependency Rule (`CLAUDE.md` : "les dépendances ne remontent jamais" — Domain ne doit rien connaître de la couche Managers). Chaque `Reference` ne porte déjà qu'un `path` (chaîne) et un `role` (chaîne) — aucun objet Qt, aucune référence mémoire, aucun ID de Dataset/Image à résoudre. La solution retenue (section 3.1) est une structure Domain minimale et propre, `GenerationReference`, qui reprend exactement cette forme sans dépendre du fichier Manager.

**Audit UI (`ImagesPage`)** : `src/ui/pages/images_page.py` ne contient aujourd'hui qu'une grille de miniatures (`list_widget`) et deux boutons (`enlarge_button`/`delete_button`) — aucun panneau de détails n'existe. L'agrandissement (bouton ou double-clic) ouvre `ImagePreviewDialog` (`src/ui/dialogs/image_preview_dialog.py`), qui porte une contrainte architecturale explicite et documentée depuis la Mission 015 : *« strictement un visualiseur passif, partagé entre `ImagesPage` et l'aperçu pending d'`InferencePage` — reçoit uniquement un `file_path`, **jamais un objet Domain, un Manager ou une référence de Page** »*. Lui faire porter un affichage de métadonnées introduirait soit une violation directe de ce principe documenté, soit une divergence de contrat entre son usage `ImagesPage` (image déjà acceptée, un `Image` Domain existe) et son usage `InferencePage` (résultat encore pending, aucun `Image` Domain n'existe avant Accept). Décision actée en section 6.

## 2. Objectif de M123

Lorsqu'une génération réalisée depuis `InferencePage` est acceptée, conserver avec l'`Image` créée les paramètres réellement utilisés pour produire ce résultat précis — capturés une seule fois, au moment du clic Generate, jamais relus depuis l'état courant des widgets au moment de l'Accept. Une image importée manuellement (`ImagesPage`) doit rester strictement valide sans aucune provenance de génération, comme aujourd'hui. Un `project.json` antérieur ne portant aucune métadonnée de génération doit continuer à se charger sans erreur ni migration.

**M123 crée la donnée durable — elle ne construit ni Generation History, ni Queue, ni Replay/Regenerate, ni extraction EXIF/métadonnées moteur.** Ces capacités futures deviendront possibles une fois cette donnée disponible, mais aucune n'est livrée par cette mission.

## 3. Décision architecturale

### 3.1 Nouvelle structure Domain — `GenerationMetadata` / `GenerationReference`

Nouveau fichier `src/domain/generation_metadata.py`, Qt-free, deux dataclasses minimales suivant exactement la convention déjà établie (`to_dict()`/`from_dict()` symétriques, désérialisation défensive `isinstance(x, dict)`) :

```
GenerationReference
├── path: str = ""
└── role: str = ""

GenerationMetadata
├── engine: str = ""                                   (target_engine_key réel : "comfyui" | "forge")
├── prompt: str = ""
├── negative_prompt: str = ""
├── seed: int = -1                                      (sentinelle hors plage réelle [0, 2**32-1] — voir 3.2)
├── width: int = 0
├── height: int = 0
├── steps: int = 0
├── cfg: float = 0.0
├── sampler_name: str = ""
├── scheduler: str = ""
├── checkpoint_name: Optional[str] = None               (None reste légitime — voir 3.2)
├── lora_name: str = ""                                 ("" = pas de LoRA, sentinelle déjà en usage dans ce fichier)
├── lora_strength: Optional[float] = None
├── references: list[GenerationReference] = field(default_factory=list)
└── reference_strength: float = 0.0
```

`GenerationReference` reprend exactement et uniquement la forme de `Reference` (Manager) — sans jamais l'importer — pour rester strictement Domain-pure.

**Précision demandée par l'architecte — `GenerationReference.path` est une provenance historique, jamais une promesse de disponibilité** : `path` documente quel fichier a été utilisé comme référence *au moment de la génération*. Il n'est ni revalidé, ni résolu à un `image_id`/`Dataset` stable (le snapshot réel ne fournit aujourd'hui aucun identifiant logique fiable pour une référence — seulement un chemin et un rôle, voir Mission 056), et rien ne garantit que le fichier existe encore à cette adresse plus tard (déplacement, suppression, renommage externe). M123 ne rend donc **pas** la metadata directement rejouable : aucune régénération, aucun « Use these settings again », aucune résolution portable de référence ne sont livrés par cette mission (confirmé hors périmètre, section 5). Le docstring de `GenerationReference` dans `src/domain/generation_metadata.py` portera cette même précision.

**Garde contre tout état mutable partagé (dataclasses)** : `references` utilise `field(default_factory=list)`, jamais `= []` littéral (qui partagerait la même liste entre toutes les instances n'en fournissant pas explicitement une — piège classique des dataclasses). `GenerationMetadata.from_dict()` construit une **nouvelle** liste de **nouvelles** instances `GenerationReference` à chaque appel (jamais une réutilisation directe des dicts/listes issus du JSON chargé) — aucune structure mutable n'est donc jamais partagée entre deux `GenerationMetadata`, ni entre un `GenerationMetadata` chargé et le dict qui a servi à le construire.

`Image` gagne :

```
Image
├── image_id: str = ""                (inchangé)
├── file_path: str = ""               (inchangé)
└── generation_metadata: Optional[GenerationMetadata] = None   (nouveau — None = aucune provenance)
```

`generation_metadata=None` est la sentinelle : toute image (importée manuellement, ou générée avant cette mission) sans donnée de génération reste strictement valide. Aucun champ de provenance n'est jamais inventé pour une image qui n'a pas réellement été produite par `InferencePage`.

`Image.to_dict()` n'inclut la clé `"generation_metadata"` que lorsqu'elle n'est pas `None` (cohérent avec le principe déjà appliqué par `build_training_config()` en Mission 120-122 : une absence de valeur ne doit jamais gonfler `project.json` pour le cas — trèsmajoritaire — d'une image sans provenance). `Image.from_dict()` lit `data.get("generation_metadata")` : si ce n'est pas un `dict`, `generation_metadata=None` sans erreur ni migration — un `project.json` antérieur (`image_id`/`file_path` seuls) se charge donc à l'identique d'aujourd'hui.

### 3.2 Table de correspondance — `_PendingGenerationRequest` → `GenerationMetadata`

Construite strictement à partir des champs réels du dataclass (`inference_page.py:122-139`), sans aucun champ anticipé pour un besoin futur :

| Champ `_PendingGenerationRequest` | Champ persistant | Type | Raison de le conserver |
|---|---|---|---|
| `target_engine_key` | `engine` | `str` | Identifie quel moteur (`comfyui`/`forge`) a réellement produit l'image — nécessaire pour interpréter tous les autres champs (ex. un `sampler_name` ComfyUI n'a pas le même vocabulaire qu'un Forge). |
| `prompt_text` | `prompt` | `str` | Le prompt positif réellement envoyé au moteur. |
| `negative_prompt` | `negative_prompt` | `str` | Le prompt négatif réellement envoyé. |
| `seed` | `seed` | `int` | La seed réellement résolue (`_resolve_seed()`) et utilisée — c'est la donnée de provenance la plus critique pour comprendre pourquoi deux générations diffèrent. |
| `width` | `width` | `int` | Résolution réellement demandée. |
| `height` | `height` | `int` | Résolution réellement demandée. |
| `steps` | `steps` | `int` | Nombre de steps réellement utilisé. |
| `cfg` | `cfg` | `float` | CFG scale réellement utilisé. |
| `sampler_name` | `sampler_name` | `str` | Sampler réellement utilisé (déjà résolu avec repli ComfyUI, ou chaîne vide Forge — voir `_build_generation_request()` ligne 1045-1050). |
| `scheduler` | `scheduler` | `str` | Scheduler réellement utilisé, même logique de résolution. |
| `checkpoint_name` | `checkpoint_name` | `Optional[str]` | Checkpoint réellement utilisé — `None` reste possible (ComfyUI avec combo vide, seul cas où c'est atteignable d'après le code), jamais transformé en chaîne vide artificielle. |
| `lora_name` | `lora_name` | `str` | Nom d'alias LoRA réellement exposé au moteur pour cette génération (`""` = pas de LoRA, sentinelle déjà en vigueur dans ce fichier — voir note ci-dessous). |
| `lora_strength` | `lora_strength` | `Optional[float]` | Force réellement utilisée, `None` uniquement quand `lora_name == ""`. |
| `reference_images` | `references` | `list[GenerationReference]` | La ou les références réellement utilisées (0..N), forme déjà minimale et sérialisable (`path`/`role`) — aucune conversion nécessaire au-delà du renommage de type. |
| `reference_strength` | `reference_strength` | `float` | Force de référence réellement utilisée (lue systématiquement, même sans référence — voir commentaire ligne 1008-1012 : sans effet si `references` est vide, conservée telle quelle). |

**Champs explicitement exclus, avec justification** :

| Champ `_PendingGenerationRequest` | Exclu — raison |
|---|---|
| `output_directory` | Chemin d'exécution transitoire, strictement dérivé de `workspace_root`, redondant avec `Image.file_path` lui-même — aucune valeur de provenance propre. |
| `workspace_root` | Valeur de contexte runtime (sert uniquement à `_workspace_context_matches()`), pas une donnée de génération ; la conserver introduirait un chemin absolu figé dans `project.json`, contraire aux préoccupations de portabilité déjà documentées ailleurs dans ce projet — et de toute façon redondante puisque l'image vit déjà dans ce Workspace par construction. |
| `target_engine` | Objet moteur (`ComfyUIEngine`/`ForgeEngine`), non sérialisable — `target_engine_key` (déjà une chaîne) porte toute l'information de provenance utile. |

**Note sur `lora_name`** : la valeur capturée est l'alias exposé au moteur (`exposure.alias_name`, ligne 1120 de `inference_page.py`), pas l'identifiant stable `lora_id` de la Bibliothèque LoRA — `_PendingGenerationRequest` ne porte pas ce second identifiant aujourd'hui, et cette mission n'en introduit pas un nouveau qui n'existerait pas déjà dans le snapshot réel (consigne explicite : ne pas créer de champ "pour plus tard"). Toute résolution future vers un `lora_id` stable de Bibliothèque reste hors périmètre, à documenter comme limitation connue si elle s'avère utile plus tard (ex. pour un futur "Use these settings again", explicitement hors périmètre de M123).

**Note sur `seed`** : sentinelle `-1`, choisie car `MIN_SEED = 0` / `MAX_SEED = 2**32 - 1` (`inference_page.py:101-102`) couvrent déjà tout l'intervalle légitime — `-1` reste donc sans ambiguïté possible avec une vraie seed. En pratique, `GenerationMetadata` n'est jamais construit avec cette sentinelle par le flux réel (une génération terminée a toujours une seed réelle résolue) ; elle ne sert qu'à la valeur par défaut du dataclass lui-même.

### 3.3 Cycle de vie de la metadata — figé explicitement, sans dérive vers une queue

**Renommage demandé par l'architecte** : le nouvel attribut n'est pas nommé `_pending_generation_snapshot`, pour éviter toute confusion avec `self._pending_generation_request` déjà existant (qui représente un stade **antérieur** et sans rapport — l'attente d'un démarrage de ComfyUI Local, avant même que le worker ne soit lancé). Le nouvel attribut représente la catégorie suivante et distincte : *un résultat de génération réellement terminé, attendant Accept/Reject*. Nom retenu : **`InferencePage._pending_result_metadata: Optional[GenerationMetadata]`**.

**Décision de construction anticipée** : contrairement à l'esquisse initiale (construire `GenerationMetadata` seulement à l'Accept), la metadata est désormais **construite dans `_launch_generation_worker(request)` lui-même**, juste après résolution complète des paramètres réellement utilisés (c'est le point de passage unique déjà emprunté par les deux chemins de lancement — immédiat, ou différé après démarrage ComfyUI, voir son propre docstring ligne 1302-1307) :

```python
self._pending_result_metadata = _build_generation_metadata(request)
```

`_build_generation_metadata()` (fonction privée du module, pure, sans effet de bord) traduit `_PendingGenerationRequest` → `GenerationMetadata`/`GenerationReference` selon la table de la section 3.2. Elle réussit toujours pour un `request` réel (aucune branche d'échec) — `self._pending_result_metadata` est donc systématiquement une vraie instance dès qu'un worker est effectivement lancé, jamais `None` à ce stade.

**Cycle de vie complet, chemin par chemin :**

| Événement | Effet sur `_pending_result_metadata` |
|---|---|
| `_launch_generation_worker(request)` | Construite et assignée — première écriture du cycle. |
| Génération réussie (`_on_generation_finished`, contexte Workspace valide) | Conservée telle quelle, associée au résultat pending jusqu'à décision Accept/Reject. |
| **Accept réussi** (`_accept_pending_result()`, `add_images()` n'a pas levé) | Transmise à `WorkspaceManager.add_images()` (section 3.4) **avant** tout nettoyage, puis nettoyée par `_clear_pending()`. |
| **Accept échoué** (`WorkspaceManagerError`, retry possible — Mission 067) | **Conservée** : le résultat reste pending, un second Accept doit pouvoir réutiliser la même metadata sans la reconstruire (aucun changement à ce chemin de retry déjà établi). |
| **Reject** (`_reject_pending_result()`) | Nettoyée via `_clear_pending()`, sans jamais avoir atteint `add_images()`. |
| **Échec de génération** (`_on_generation_failed()`) | Nettoyée explicitement (nouvelle ligne `self._pending_result_metadata = None` dans ce handler — aucun résultat pending n'est jamais créé pour ce cycle, mais la metadata avait déjà été construite à l'étape de lancement). |
| **Changement de Workspace pendant que le résultat vient d'arriver** (`_on_generation_finished()`, branche de rejet silencieux, ligne 1358-1371, où `_set_pending()` n'est jamais atteint) | Nettoyée explicitement, par symétrie avec la remise à `None` de `self._generation_workspace_root` déjà présente dans cette branche. |
| Invalidation Workspace en cours de pending (`reset_for_workspace_change()`), `shutdown()` | Nettoyée via `_clear_pending(delete_file=True)`, déjà le point de sortie unique de ces deux chemins. |
| Nouvelle génération (Regenerate ou nouveau clic Generate) | Un seul cycle en vol à la fois (`generate_button` désactivé pendant tout run, Regenerate impossible tant que le pending précédent n'est pas tranché) — la prochaine `_launch_generation_worker()` réassigne intégralement l'attribut ; aucun résidu de l'ancien cycle ne peut donc jamais contaminer le suivant. |

`_clear_pending(delete_file)` reste le point de sortie unique partagé par Accept-succès, Reject, invalidation Workspace et `shutdown()` — il remet `_pending_result_metadata = None` exactement au même endroit que `_pending_path`/`_pending_pixmap`/`_generation_workspace_root`.

**Preuve explicite du scénario anti-contamination (précision architecte n°2)** : Generate avec paramètres A → `_pending_result_metadata` construit depuis A → résultat pending → l'utilisateur modifie les widgets vers B (jamais relus) → Accept. L'image acceptée porte les paramètres A, jamais B — garanti par construction, couvert par un test dédié (section 7, point 7).

**Tests de chemins d'erreur/nettoyage ajoutés suite à cette précision** (section 7, points 10bis/15) : échec de génération → metadata nettoyée ; Accept échoué (retry) → metadata conservée à l'identique pour le retry ; changement de Workspace pendant l'arrivée du résultat → metadata nettoyée.

### 3.4 Extension de `WorkspaceManager.add_images()` — analyse de risque et compatibilité

**Risque audité** : `add_images()` a deux appelants réels (section 1). Toute modification de sa signature ou de son comportement par défaut affecterait `ImagesPage.import_images()`, qui n'a et ne doit jamais avoir de notion de génération.

**Décision** : ajout d'un unique paramètre optionnel, par défaut `None`, sans toucher à aucune ligne de logique existante (dédoublonnage, renommage, rollback Mission 067). **Nom renommé suite à la précision de l'architecte** (`generation_metadata` seul jugé ambigu) : **`generation_metadata_by_path`**, qui exprime explicitement qu'il s'agit d'une correspondance keyée par chemin, symétrique de `renames` :

```python
def add_images(
    self,
    paths: list,
    renames: Optional[dict] = None,
    generation_metadata_by_path: Optional[dict] = None,
) -> ImportResult:
```

`generation_metadata_by_path` est une correspondance `{chemin_source_original: GenerationMetadata}`. **Vérification explicite de l'espace de clés** (demandée par l'architecte, à confirmer sur le diff réel à l'implémentation) : dans la boucle actuelle (ligne 502 `for path in paths:` … ligne 513 `renames.get(path)` … ligne 529 `Image(...)`), la variable `path` est à chaque itération le chemin source **original**, tel que fourni dans `paths`, **avant** toute résolution via `WorkspaceStorage.copy_into_workspace()` — very exactement le même chemin que celui déjà utilisé pour interroger `renames.get(path)` une vingtaine de lignes plus haut dans la même itération. `generation_metadata_by_path.get(path)` doit donc être appelé avec cette même variable `path`, jamais avec `effective_path` (le chemin final, potentiellement copié/renommé) — ce qui exclut toute collision avec le chemin final réécrit, et fonctionne identiquement que l'appelant passe 1 ou N chemins dans le même appel (chaque itération résout sa propre entrée de la map indépendamment). Au point de construction de chaque `Image` (ligne 529 actuelle), le seul changement est :

```python
Image(
    image_id=str(uuid.uuid4()),
    file_path=str(effective_path),
    generation_metadata=(generation_metadata_by_path or {}).get(path),
)
```

`ImagesPage.import_images()` (appel existant, ligne 148 : `add_images(files, renames=renames)`) ne passe jamais ce paramètre — `(generation_metadata_by_path or {}).get(path)` retourne alors toujours `None`, comportement rigoureusement identique à aujourd'hui, y compris pour un import multi-fichiers. `DatasetManager.add_images()` reste une méthode entièrement distincte, **non modifiée** (confirmé, précision architecte point 6). Le contrat de rollback Mission 067 (échec de `save()` restaure `Workspace.images` et nettoie les copies orphelines) reste inchangé — `generation_metadata_by_path` ne fait que voyager avec l'`Image` déjà construite, sans toucher au chemin d'erreur.

`InferencePage._accept_pending_result()` devient le seul appelant réel à fournir ce paramètre — en réutilisant directement `self._pending_result_metadata` déjà construit à l'étape de lancement (section 3.3), **sans jamais le reconstruire ni relire les widgets à l'Accept** :

```python
self._workspace_manager.add_images(
    [self._pending_path],
    generation_metadata_by_path=(
        {self._pending_path: self._pending_result_metadata}
        if self._pending_result_metadata is not None
        else None
    ),
)
```

Le garde `if self._pending_result_metadata is not None` reste un filet défensif pour un état qui ne devrait structurellement jamais se produire dans le flux normal (la metadata est toujours construite avant qu'un résultat ne devienne pending — section 3.3) — jamais une provenance inventée en son absence.

**Preuve d'indépendance mémoire (précision architecte n°7)** : `_build_generation_metadata()` construit toujours une **nouvelle** instance `GenerationMetadata` (et une nouvelle liste de nouvelles instances `GenerationReference`, jamais une réutilisation de `request.reference_images`) à chaque appel — aucun état n'est partagé entre deux cycles de génération, ni entre le `_PendingGenerationRequest` source et l'objet persisté. Une mutation ultérieure du snapshot Inference, de sa liste de références, ou des paramètres d'une génération suivante ne peut donc jamais modifier une `Image.generation_metadata` déjà transmise à `add_images()` — prouvé par un test dédié (section 7, point 11) plutôt que par un mécanisme `deepcopy` général, inutile ici puisque la construction ne réutilise jamais une référence mutable partagée.

### 3.5 Images importées et rétrocompatibilité — comportement strictement inchangé

- Une image ajoutée via `ImagesPage` continue de n'avoir jamais de `generation_metadata` — `None`, jamais une valeur reconstituée ou devinée.
- Un `project.json` antérieur à cette mission (`image_id`/`file_path` seuls) se charge sans erreur ni migration : `Image.from_dict()` ne trouvant pas la clé `"generation_metadata"` produit `generation_metadata=None`, identique au comportement par défaut du dataclass.
- Une image déjà acceptée avant cette mission, présente dans un Workspace rouvert après mise à jour du Toolkit, garde `generation_metadata=None` pour toujours — aucune reconstruction rétroactive n'est tentée (impossible de toute façon, la donnée n'a jamais existé).

## 4. Fichiers concernés

- `src/domain/generation_metadata.py` (nouveau) — `GenerationReference`, `GenerationMetadata` (dataclasses Qt-free, `to_dict()`/`from_dict()` défensifs).
- `src/domain/image.py` (modifié) — nouveau champ `generation_metadata: Optional[GenerationMetadata] = None`, `to_dict()`/`from_dict()` étendus (clé omise si `None`, garde `isinstance(..., dict)` à la désérialisation).
- `src/managers/workspace_manager.py` (modifié) — `add_images()` gagne le paramètre optionnel `generation_metadata_by_path: Optional[dict] = None`, sans changement de comportement par défaut.
- `src/ui/pages/inference_page.py` (modifié) — nouvel attribut `_pending_result_metadata: Optional[GenerationMetadata]`, construit dans `_launch_generation_worker()` via une nouvelle fonction privée du module `_build_generation_metadata(request)`, consommé tel quel dans `_accept_pending_result()`, nettoyé dans `_clear_pending()`, dans `_on_generation_failed()`, et dans la branche de rejet pour changement de Workspace de `_on_generation_finished()`.
- `tests/integration/test_image_roundtrip.py` (modifié) — round-trip `Image.generation_metadata`, image sans metadata, désérialisation défensive, indépendance des instances `GenerationReference` désérialisées.
- `tests/integration/test_workspace_roundtrip.py` (modifié) — `WorkspaceManagerAddImagesCopyTest` étendu : `add_images(generation_metadata_by_path=...)` (une et plusieurs images dans le même appel), non-régression de l'appel sans ce paramètre.
- `tests/integration/test_inference_page.py` (modifié) — construction/rétention/consommation/nettoyage de `_pending_result_metadata` sur chacun des chemins de la table du cycle de vie (section 3.3), non-contamination par une modification UI post-Generate, Reject ne persiste rien, deux générations successives gardent des métadonnées indépendantes, échec de génération nettoie la metadata, Accept échoué la conserve pour le retry.

**Aucun changement** à `DatasetManager`/`Dataset.images`, `ImagesPage` (voir section 6), `ImagePreviewDialog`, `GenerationManager`/`GenerationWorker`/`ComfyUIEngine`/`ForgeEngine`, à l'EventBus, ni à aucun mécanisme de garde Mission 083-085/108/115-117 au-delà de l'ajout ponctuel décrit en section 3.3.

## 5. Hors périmètre strict

- Page **Generation History** (liste/navigation des générations passées).
- **Queue** de génération (plusieurs résultats en attente simultanément).
- **Ratings**/**Favorites**.
- **Versioning** complet (liens explicites entre générations apparentées).
- **Comparaison d'images**.
- **Régénération automatique depuis metadata** / **« Use these settings again »**.
- **Dashboard Recent Activity**.
- **Migration** des images déjà présentes dans un Workspace existant (elles restent `generation_metadata=None` pour toujours).
- **Extraction EXIF/PNG metadata** depuis les moteurs (ComfyUI/Forge écrivent potentiellement déjà des métadonnées dans le PNG lui-même — non lues, non consommées ; M123 persiste uniquement ce que `_PendingGenerationRequest` a capturé côté Toolkit).
- Résolution du `lora_name` exposé vers un `lora_id` stable de Bibliothèque LoRA (voir note section 3.2).
- **Résolution portable de `GenerationReference.path`** — aucune revalidation, aucune tentative de retrouver un `image_id`/`Dataset` d'origine, aucune garantie que le fichier existe encore à cette adresse (voir section 3.1) ; c'est une provenance historique, jamais un lien fonctionnel maintenu.
- Tout affichage UI au-delà de ce que la section 6 tranche.
- Tout système général de validation/migration de `project.json` au-delà de la désérialisation défensive minimale déjà pratiquée partout ailleurs dans ce projet (`isinstance(x, dict)`).

## 6. UI — audit et décision de report

`ImagesPage` ne porte aujourd'hui aucune zone de détails/panneau — uniquement une grille de miniatures et deux boutons (`enlarge_button`/`delete_button`). Le seul mécanisme d'agrandissement existant, `ImagePreviewDialog`, porte une contrainte architecturale explicite et documentée depuis la Mission 015 (*« reçoit uniquement un `file_path` — jamais un objet Domain, un Manager, ou une référence de Page »*), et ce même composant est **partagé** avec l'aperçu du résultat encore pending d'`InferencePage` — un contexte où aucun `Image` Domain n'existe avant Accept.

Lui faire porter un affichage de métadonnées introduirait soit une violation de ce principe déjà acté, soit une incohérence de contrat entre ses deux usages. Aucune zone d'affichage minimal ne peut donc être ajoutée proprement sans élargir la mission au-delà de la persistance de la provenance.

**Décision** : M123 persiste strictement la provenance (Domain + Manager + capture InferencePage) et **reporte tout affichage UI détaillé à une mission ultérieure**, qui pourra alors décider consciemment soit d'assouplir la contrainte Mission 015 d'`ImagePreviewDialog`, soit d'introduire un panneau de détails dédié dans `ImagesPage` — les deux options restant ouvertes et non tranchées ici.

## 7. Tests

Les 15 scénarios validés par l'architecte sont conservés ; les assertions supplémentaires demandées lors de la validation (chemins d'erreur/nettoyage, indépendance mémoire, désérialisation défensive détaillée, cohérence du keying `WorkspaceManager.add_images()`) sont **fusionnées dans ces mêmes scénarios** plutôt que multipliées en tests séparés, conformément à la consigne de ne pas augmenter artificiellement le nombre de tests.

1. Round-trip `GenerationMetadata`/`GenerationReference` : tous les champs survivent à `to_dict()`/`from_dict()` à l'identique.
2. `Image` sans `generation_metadata` (sentinelle `None`) : round-trip inchangé, clé absente de `to_dict()`.
3. `Image.from_dict()` sur un `project.json` antérieur (`image_id`/`file_path` seuls, sans la clé `generation_metadata`) : charge avec `generation_metadata=None`, sans erreur. *Fusionné* : `generation_metadata` absent du dict → `None`.
4. `Image.from_dict()` sur une valeur `generation_metadata` mal typée (pas un dict) : repli défensif sur `None`, jamais d'exception. *Fusionné* : `references` absent/non-`list` dans le sous-dict → liste vide ; un élément de `references` qui n'est pas un dict est ignoré (même convention défensive que `Image.list_from_data()` — filtrage silencieux, jamais de crash) ; les champs optionnels (`checkpoint_name`, `lora_strength`) restent correctement `None` quand absents ou explicitement `null`.
5. Image importée via `ImagesPage`/`WorkspaceManager.add_images()` sans `generation_metadata_by_path` : `Image.generation_metadata is None`, comportement strictement inchangé par rapport à avant cette mission. *Fusionné* : plusieurs images importées dans le **même appel** (`paths` à 2+ entrées) restent toutes sans metadata, sans effet de bord entre elles.
6. Accept d'une génération réelle (via `InferencePage`) : l'`Image` ajoutée à `Workspace.images` porte un `generation_metadata` non `None`, dont chaque champ correspond exactement au snapshot capturé au clic Generate (table section 3.2). *Fusionné* : `_pending_result_metadata` est bien construit dès `_launch_generation_worker()` (vérifiable avant même que `_on_generation_finished` ne soit signalé).
7. **Non-contamination** : Generate avec des paramètres A, puis modification des widgets vers B avant Accept — la métadonnée persistée reste strictement celle de A.
8. Reload du Workspace après Accept : `Image.generation_metadata` relu est identique à celui persisté (round-trip complet via `project.json`).
9. Deux générations acceptées successivement avec des paramètres différents conservent chacune leur propre `generation_metadata`, sans contamination croisée.
10. Reject d'un résultat pending : rien n'est ajouté à `Workspace.images`, `_pending_result_metadata` est nettoyé (`None` après `_clear_pending()`). *Fusionné* : un échec de génération (`_on_generation_failed()`) nettoie également `_pending_result_metadata`, alors qu'aucun résultat pending n'a jamais existé pour ce cycle.
11. Une nouvelle génération lancée après une précédente Accept ne modifie jamais le `generation_metadata` de l'image déjà persistée. *Fusionné* : preuve d'indépendance mémoire explicite — muter la liste `reference_images` du `_PendingGenerationRequest` source (ou construire une deuxième génération) après un Accept réussi ne modifie ni les valeurs, ni la liste `references`, de l'`Image.generation_metadata` déjà transmise à `add_images()`.
12. Références sérialisées correctement quand `reference_images` du snapshot est non vide (0, 1 référence — la seule cardinalité réellement atteignable aujourd'hui, Mission 056), et absentes/liste vide quand aucune référence n'était utilisée.
13. Aucun objet Qt ni référence non sérialisable dans `project.json` après un Accept réel (vérifié par relecture directe du fichier écrit sur disque).
14. `WorkspaceManager.add_images()` appelé sans `generation_metadata_by_path` (comme le fait `ImagesPage`) : comportement byte-à-byte identique à avant cette mission — non-régression explicite. *Fusionné* : le keying de `generation_metadata_by_path` utilise bien le chemin **source original** (celui de `paths`), jamais `effective_path` (le chemin final après copie/renommage) — vérifié avec un cas où une collision de nom force un renommage automatique, la metadata restant correctement associée à la bonne image malgré le renommage.
15. Changement de Workspace pendant qu'une génération est en vol (résultat jeté silencieusement, section 3.3) : `_pending_result_metadata` est bien remis à `None`, ne survit pas pour contaminer un cycle suivant. *Fusionné* : un Accept qui échoue (`WorkspaceManagerError`) conserve `_pending_result_metadata` à l'identique — le retry suivant (nouvel Accept sur le même pending) réutilise la même metadata, jamais reconstruite ni perdue.

## 8. Smoke réel (prévu, non exécuté avant validation)

Contre une installation ComfyUI (ou Forge, selon le chemin le plus fiable au moment de l'exécution) réelle, réutilisant le Workspace/scénario déjà validé par les smokes précédents :

1. Ouvrir un Workspace réel.
2. Lancer une génération avec des paramètres distinctifs (prompt/seed/checkpoint/LoRA choisis pour être reconnaissables sans ambiguïté).
3. Attendre le résultat pending.
4. Modifier un ou deux widgets (ex. prompt, seed) **sans** relancer de génération.
5. Cliquer Accepter.
6. Lire directement `project.json` sur disque et vérifier que la métadonnée persistée correspond aux paramètres de l'étape 2, jamais à ceux de l'étape 4.
7. Fermer puis rouvrir le Workspace ; vérifier que l'`Image` rechargée porte un `generation_metadata` identique.
8. Effectuer une deuxième génération avec des paramètres différents, l'accepter.
9. Vérifier que les deux images du Workspace conservent chacune leur propre métadonnée, sans contamination.

Le smoke doit prouver la persistance réelle (lecture directe de `project.json` + rechargement), pas seulement la présence en mémoire immédiatement après Accept.

## 9. Critères de clôture

1. `GenerationMetadata`/`GenerationReference` round-trip exact ; `Image.generation_metadata` reste `None` pour toute image sans provenance, sans jamais de champ inventé.
2. Rétrocompatibilité totale avec tout `project.json` antérieur (avec ou sans la clé `generation_metadata`), sans migration.
3. `WorkspaceManager.add_images()` reste byte-à-byte inchangé pour tout appelant qui ne fournit pas `generation_metadata` (`ImagesPage`, `DatasetManager.add_images()` non concerné car méthode distincte).
4. La métadonnée persistée pour une génération acceptée correspond exactement au snapshot capturé au clic Generate, jamais à l'état des widgets au moment de l'Accept — prouvé par test explicite (section 7, point 7) et par le smoke réel.
5. Reject ne persiste jamais rien ; deux générations successives restent indépendantes.
6. Suite complète verte au nombre exact, aucune régression sur les tests hérités de Mission 122.
7. Smoke réel de bout en bout validé, preuve par lecture directe de `project.json` et rechargement du Workspace.
8. Documentation explicite que M123 ne livre ni Generation History, ni Queue, ni Replay/Regenerate, ni extraction EXIF moteur, ni affichage UI détaillé (reporté, section 6).

## 10. Autorisation

Mission autorisée par l'architecte après audit post-Mission 122 ayant identifié la perte de provenance de génération comme le gap le plus fortement justifié par le Blueprint (P0 « Metadata »/« History » sous Image Generation, critère de succès « Manage versions ») et le moins risqué architecturalement (le snapshot nécessaire existe déjà en mémoire au bon endroit — Mission 115 — il ne reste qu'à le retenir jusqu'à Accept et à le persister). Décisions actées explicitement : (1) `GenerationMetadata`/`GenerationReference` sont des structures Domain dédiées et typées, jamais un dict non typé, définies indépendamment de `Reference` (Manager) pour respecter la Dependency Rule, avec `field(default_factory=list)` pour `references` (jamais d'état mutable partagé) ; (2) `Image.generation_metadata: Optional[GenerationMetadata] = None` est un ajout strictement additif, sans migration, sans impact sur une image importée manuellement ; (3) `WorkspaceManager.add_images()` gagne un unique paramètre optionnel renommé `generation_metadata_by_path`, sans changement de comportement pour son autre appelant réel (`ImagesPage`), `DatasetManager.add_images()` non touché ; (4) la metadata est construite une seule fois, dans `_launch_generation_worker()`, immédiatement après résolution des paramètres réellement utilisés, conservée sous `_pending_result_metadata` (nom distinct de `_pending_generation_request` déjà existant) jusqu'à Accept/Reject, jamais reconstruite ni relue depuis les widgets au moment de l'Accept, avec un cycle de nettoyage figé pour chacun des chemins réels (succès, échec, Reject, Accept-échoué-retry, invalidation Workspace, shutdown) ; (5) `GenerationReference.path` est documenté comme provenance historique, jamais une promesse de disponibilité ni une base de Replay ; (6) l'affichage UI détaillé est explicitement reporté à une mission ultérieure, `ImagePreviewDialog` ne devant pas voir sa contrainte Mission 015 assouplie sans décision consciente et séparée.

**Précisions de l'architecte intégrées au présent document, implémentation autorisée à partir d'ici.**
