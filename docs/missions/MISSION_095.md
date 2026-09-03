# Mission 095 — Central LoRA Library: ComfyUI Exposure via NTFS Hardlink

> **MISSION IMPLÉMENTÉE ET VALIDÉE PAR L'ARCHITECTE, CLÔTURE GIT EFFECTUÉE.** Voir section 9 pour l'état final.

## 1. Contexte

L'audit post-Mission 094 a établi, par preuve directe (code + `/system_stats` réel + tests empiriques sur l'installation ComfyUI réelle de l'architecte), que la bibliothèque LoRA centrale (Missions 087–093) est complète et mature côté stockage/CRUD, mais **totalement déconnectée** de la sélection LoRA réellement utilisée en génération : `SettingsPage.comfyui_lora_name_edit` est peuplé exclusivement par `ComfyUIEngine.list_loras()` (découverte serveur, Mission 059), sans aucune référence à `LoRALibraryManager`. Une LoRA importée dans la bibliothèque centrale n'est donc, aujourd'hui, jamais utilisable en génération réelle sans copie manuelle hors du Toolkit.

Un mini-audit empirique a ensuite été conduit contre l'installation ComfyUI Desktop réelle de l'architecte (`http://127.0.0.1:8000`, ComfyUI Desktop v0.9.4, base `J:\Programmes\ComfyUI`), avec autorisation explicite de démarrer/interroger le serveur. Cet audit a produit deux catégories de résultats :

- **Un incident externe, documenté séparément et sans rapport avec le périmètre fonctionnel de cette mission** : deux lancements de `ComfyUI.exe` par l'agent ont déclenché la routine de synchronisation de paquets intégrée à ComfyUI Desktop, provoquant un downgrade non désiré de `comfyui-workflow-templates`/`comfyui-embedded-docs`/`comfy-aimdo`/`comfyui-manager`, ainsi que le téléchargement (et probablement l'installation silencieuse au quit) d'une mise à jour Comfy Desktop 1.0.46. Cet incident est **externe à AI Studio Toolkit**, n'a entraîné aucune modification de code ni de configuration du Toolkit, et n'est pas traité par cette mission.
- **Les résultats empiriques exploitables pour cette mission**, détaillés en section 3, obtenus exclusivement contre l'instance ComfyUI démarrée manuellement par l'architecte — jamais par un lancement, redémarrage ou modification de configuration effectué par l'agent après cet incident.

Une première version de ce contrat a été révisée après relecture critique de l'architecte, qui a identifié deux angles morts : (a) une contradiction interne entre « dossier d'exposition dédié », « alias plat sans préfixe » et « aucune modification de configuration ComfyUI », ces trois propriétés ne pouvant pas coexister ; (b) l'absence d'un contrat explicite de cycle de vie des hardlinks (un hardlink n'est pas supprimé automatiquement avec la source — un nettoyage incomplet laisse des données physiquement présentes et toujours visibles par ComfyUI). Les deux points sont tranchés ci-dessous.

## 2. Objectif

Combler le fossé identifié : rendre une entrée de la bibliothèque LoRA centrale physiquement visible et sélectionnable par ComfyUI, sans dupliquer le fichier physique, sans modifier automatiquement la configuration ComfyUI, sans exiger de privilège élevé, et avec un cycle de vie de hardlink entièrement défini avant implémentation — via un mécanisme d'exposition prouvé empiriquement sur l'installation réelle de l'architecte.

## 3. Mini-audit — conclusions verrouillées

### 3.1 Installation réelle identifiée

ComfyUI Desktop (`C:\Users\dlero\AppData\Local\Programs\ComfyUI\ComfyUI.exe`), backend `J:\Programmes\ComfyUI\.venv\Scripts\python.exe`, exposé sur `http://127.0.0.1:8000` — confirmé par l'`argv` réel retourné par `GET /system_stats` de l'instance démarrée manuellement par l'architecte. `ApplicationSettings.comfyui_path` reste vide et non consommé par `comfyui_engine.py` ; il n'est pas nécessaire à cette mission.

Cette instance déclare, via `C:\Users\dlero\AppData\Roaming\Comfy Desktop\instance-model-paths\inst-1780747414105.yaml` (mécanisme par-instance de Comfy Desktop, propre à cette machine), une racine `loras` sous `C:\Users\dlero\ComfyUI-Shared\models`, en plus de la racine implicite toujours active `<base-directory>/models/loras`. Cette mission ne dépend d'aucune de ces deux valeurs précises (propres à cette machine) — elle nécessite seulement qu'une racine `loras` **quelconque** soit déjà déclarée à ComfyUI par l'architecte, et que son chemin soit renseigné dans les Réglages du Toolkit (§4, point 6).

### 3.2 Mécanisme de découverte — confirmé en source et empiriquement

Lecture directe de `folder_paths.py` (ComfyUI installé, `recursive_search()` + `filter_files_extensions()`) : la découverte est un `os.walk()` récursif suivi d'un filtre sur extension uniquement — **aucun chargement ni validation du contenu du fichier**.

Confirmé empiriquement contre l'instance réelle (fichiers de test créés puis entièrement supprimés après vérification) :
- un fichier ajouté dans une racine déjà déclarée est détecté par `GET /object_info/LoraLoader` **immédiatement, sans redémarrage** du serveur, y compris sa suppression ;
- un fichier placé dans un sous-dossier est présenté sous `<sous-dossier>\<fichier>` (séparateur Windows littéral) — préfixe qui fait **partie intégrante** du nom que ComfyUI attend en retour pour ce fichier (exactement le même mécanisme qu'un utilisateur rangeant ses LoRA dans des sous-dossiers par personnage, nativement supporté par ComfyUI) ;
- un fichier placé à la racine plate du dossier déclaré est présenté sous son nom exact, sans aucun préfixe.

**Non testé empiriquement** (nécessiterait de modifier un fichier de configuration ComfyUI, explicitement interdit) : le besoin de redémarrage pour l'ajout d'une **nouvelle racine**. Confirmé uniquement en lecture de code (`folder_names_and_paths` construit une seule fois au chargement du module). Cette mission en tient compte : elle ne déclare jamais de nouvelle racine — voir §3.3.

### 3.3 Emplacement d'exposition — décision tranchée (point 1 de la relecture)

Trois options étaient en tension :
- **(a) Hardlinks directement à la racine plate d'une racine loras déjà déclarée** — pas de préfixe, mais mélange les alias gérés par le Toolkit avec les vrais fichiers de génération de l'architecte dans la même racine (ex. `J:\Programmes\ComfyUI\models\loras`, qui contient aujourd'hui 7 fichiers réels), sans séparation visuelle ni organisationnelle.
- **(b) Sous-dossier dédié à l'intérieur d'une racine déjà déclarée, préfixe assumé dans le nom envoyé à `LoraLoader`** — c'est exactement le cas déjà testé empiriquement en §3.2 (le tout premier hardlink de test a été créé dans un sous-dossier et est apparu sous `<sous-dossier>\<fichier>`, fonctionnellement correct). Aucune modification de configuration ComfyUI requise : le sous-dossier vit à l'intérieur d'une racine que l'architecte a déjà déclarée.
- **(c) Nouvelle racine dédiée** — nécessiterait une modification de configuration ComfyUI, explicitement hors périmètre de cette mission.

**Décision retenue : (b).** `ApplicationSettings.comfyui_lora_expose_path` désigne désormais précisément **une racine `loras` déjà déclarée à ComfyUI** (peu importe laquelle, propre à l'installation de l'architecte) — jamais un dossier à déclarer. Le Toolkit y crée et gère exclusivement un sous-dossier fixe, non configurable, nommé `AIStudioToolkit/` (créé s'il n'existe pas, jamais à la racine du chemin configuré). Le nom ComfyUI-facing d'une entrée exposée est donc systématiquement de la forme :
```
AIStudioToolkit\<slug>__<lora_id>.<ext>
```
Ce préfixe n'est **jamais présenté comme absent** ni comme un défaut à corriger — c'est un choix délibéré qui isole proprement les alias gérés par le Toolkit des fichiers gérés manuellement par l'architecte dans la même racine, sans jamais nécessiter de nouvelle déclaration de racine.

### 3.4 Mécanisme d'exposition — hardlink NTFS validé empiriquement

Test réalisé contre le dossier `C:\Users\dlero\ComfyUI-Shared\models\loras\` (racine déjà déclarée, sans rapport avec les fichiers réels de génération situés dans `J:\Programmes\ComfyUI\models\loras`) : `mklink /H` (hardlink de fichier) — création réussie, code de sortie 0, **sans invite d'élévation ni exigence de mode développeur**, aussi bien en sous-dossier qu'à la racine plate. Nettoyage complet effectué et revérifié à chaque fois (fichiers et dossiers de test supprimés, `/object_info/LoraLoader` revenu exactement à son état initial, backend toujours sain après chaque test).

Un hardlink NTFS ne duplique jamais la donnée physique (même fichier sur disque, plusieurs entrées de répertoire indépendantes) mais **exige que la source et la destination soient sur le même volume** — limitation structurelle du mécanisme NTFS. Conséquence directe soulevée par l'architecte : **la donnée physique survit tant qu'une seule entrée de répertoire la référence encore** — supprimer l'entrée canonique de la bibliothèque centrale sans avoir retiré un alias ComfyUI existant laisse le fichier physiquement présent et toujours visible/sélectionnable par ComfyUI, en dehors de tout contrôle du Toolkit. Le contrat de cycle de vie (§5) existe spécifiquement pour empêcher cet état.

### 3.5 `LoRA.files: list[str]` — cardinalité auditée, non modifiée

`LoRAManager.add_files()`/`remove_files()` (`lora_manager.py:251-320`, Missions 050/076) confirment, par leur propre docstring, que cette cardinalité imite le patron `Dataset.images` plutôt que de répondre à un besoin métier LoRA démontré séparément. Aucun chemin de génération, ni Character-owned ni bibliothèque centrale, ne consomme `LoRA.files` aujourd'hui.

**Décision retenue, précisée après relecture** : l'exposition ComfyUI exige qu'une entrée possède **exactement un fichier** dans `LoRA.files`. Ce n'est **pas** un choix arbitraire de `files[0]` — c'est un refus explicite et propre dès que `len(lora.files) != 1`, quelle que soit la position d'un éventuel fichier unique dans la liste. Aucune notion de « fichier principal » n'est introduite dans le domaine : la contrainte vit uniquement dans la méthode d'exposition, pas dans `LoRA`.

### 3.6 Séparation source de vérité — confirmée utile, pas de fusion

`ComfyUIEngine.list_loras()` reste un moyen fiable de vérifier ce que le moteur voit réellement, sans risque de désynchronisation (détection immédiate, §3.2). `LoRALibraryManager` devient la source de vérité pour ce que le Toolkit gère. **Conséquence directe pour le périmètre** : une fois une entrée exposée, elle apparaît automatiquement dans `SettingsPage.comfyui_lora_name_edit` via `refresh_loras()`/`list_loras()` **déjà existants, non modifiés** — cette mission n'a pas besoin de toucher `SettingsPage` ni `GenerationManager` pour qu'une LoRA exposée devienne réellement sélectionnable et utilisable en génération.

## 4. Flux complet retenu

```
Central entry (LoRALibraryManager, <library_root>/<lora_id>/, exactement 1 fichier modèle)
  │
  ├─ expose_to_comfyui(lora, expose_root)
  │     → vérifie : expose_root configuré, même volume, exactement 1 fichier, fichier source existe
  │     → crée <expose_root>/AIStudioToolkit/ si absent
  │     → hardlink déterministe : AIStudioToolkit\<slug(name)>__<lora_id>.<ext>
  │     → idempotent (voir §5)
  │
  ├─ ComfyUI visible : GET /object_info/LoraLoader expose ce nom immédiatement, sans redémarrage
  │     (racine déjà déclarée par l'architecte — jamais par le Toolkit)
  │
  ├─ Sélection : SettingsPage.refresh_loras() (inchangé) affiche ce nom dans le combo existant ;
  │     ComfyUIEngine.list_loras() reste l'observation, jamais la source de sélection
  │
  ├─ Renommage de LoRA.name → alias existant non renommé automatiquement ; un nouvel appel
  │     explicite à expose_to_comfyui() ré-expose sous le nouveau slug et retire l'ancien (§5)
  │
  ├─ unexpose_from_comfyui(lora, expose_root) → retire l'alias, jamais le fichier canonique
  │
  └─ Suppression d'une entrée déjà exposée → unexpose_from_comfyui() appelée et son succès
        vérifié AVANT LoRALibraryManager.delete() (§5) — jamais en best-effort silencieux
```

## 5. Contrat de cycle de vie des hardlinks — invariants verrouillés (point 2 de la relecture)

### 5.1 Nommage — UUID complet, pas de troncature

Le schéma initialement proposé (`<slug>__<lora_id[:8]>`) est remplacé par **`<slug>__<lora_id>`** (UUID4 complet, jamais tronqué) : rien ne justifie de recréer artificiellement un risque de collision alors que l'identifiant complet, déjà garanti unique ailleurs dans l'application, est disponible sans coût. `slug` = `lora.name` assaini (caractères alphanumériques/`.`/`_`/`-` uniquement, tronqué à 80 caractères, `"lora"` si vide après assainissement) — purement cosmétique, jamais utilisé pour l'identification ou la recherche d'un alias existant.

### 5.2 Recherche d'un alias existant — toujours par `lora_id`, jamais par nom recalculé

Primitive interne : recherche par motif `AIStudioToolkit/*__<lora_id>.*` (le nom complet ne contenant aucun `.`, ce motif est sans ambiguïté). **Jamais** de recalcul du nom attendu à partir de `lora.name` courant pour retrouver un alias existant — un renommage de l'entrée changerait ce nom recalculé et rendrait un alias existant introuvable par erreur. Cette recherche est donc robuste à un renommage intervenu depuis la dernière exposition. Si le motif retourne plus d'une correspondance (anomalie ne pouvant résulter d'aucun chemin de code du Toolkit, seulement d'une intervention externe) : erreur explicite, aucune tentative de deviner laquelle est correcte.

### 5.3 `expose_to_comfyui(lora, expose_root)` — table de décision complète

Signature réellement implémentée : **sans** paramètre `library_root`, contrairement à `import_lora()`/`delete()`/`set_thumbnail()`. `LoRA.files` contient déjà des chemins absolus (retournés par `WorkspaceStorage.copy_into_workspace()` lors de l'import) — `library_root` y aurait été un paramètre mort, jamais lu, ce qui aurait contredit le principe « pas de scaffolding non nécessaire ». Écart accepté par l'architecte après implémentation.

1. Validation préalable, dans cet ordre, chaque échec produisant une erreur explicite typée distincte : `expose_root` non vide → `len(lora.files) == 1` → le fichier unique existe réellement sur disque (`os.path.isfile`) → `expose_root` existe déjà en tant que dossier → même volume que le fichier source (`os.stat(...).st_dev` comparé **avant** toute opération sur les fichiers, jamais une simple propagation de l'erreur système brute).
2. Recherche d'un alias existant pour `lora_id` (§5.2).
3. **Alias absent** → créer `AIStudioToolkit/` si nécessaire, créer le hardlink (`os.link()`) vers le nom déterministe courant (slug actuel + `lora_id`). Retourne le nom relatif ComfyUI-facing.
4. **Alias trouvé, nom identique au nom attendu courant** (aucun renommage depuis la dernière exposition) → vérifier `os.path.samefile(alias_trouvé, fichier_canonique)`.
   - Si vrai → **no-op idempotent**, retourne le même nom, aucune opération disque.
   - Si faux (même nom déterministe, mais ne pointe pas vers le fichier canonique actuel — anomalie externe) → **erreur explicite**, jamais d'écrasement.
5. **Alias trouvé, nom différent du nom attendu courant** (renommage de `LoRA.name` intervenu depuis la dernière exposition) → vérifier `os.path.samefile(alias_trouvé, fichier_canonique)` d'abord.
   - Si vrai → **ré-exposition attendue** : supprimer l'ancien alias, créer le nouveau au nom courant, retourner le nouveau nom. C'est le seul mécanisme de mise à jour après renommage — jamais automatique, seulement au prochain appel explicite à `expose_to_comfyui()`.
   - Si faux (anomalie) → **erreur explicite**, jamais d'écrasement.

### 5.4 `unexpose_from_comfyui(lora, expose_root)` — table de décision complète

1. Recherche d'un alias existant pour `lora_id` (§5.2), indépendamment du nom courant de `LoRA.name`.
2. **Alias absent** → no-op, retourne `False` (idempotent — retirer une exposition déjà retirée, ou jamais créée, n'est jamais une erreur).
3. **Alias trouvé** → supprime uniquement ce fichier alias. Ne touche jamais au fichier canonique dans `library_root`, quel que soit son état.

### 5.5 Suppression d'une entrée déjà exposée

L'orchestration vit dans `LoRAPage` (UI), jamais dans `LoRALibraryManager.delete()` lui-même (signature/comportement testé inchangés) :
1. Appelle `unexpose_from_comfyui(lora, expose_root)`.
2. **Si cet appel échoue** (erreur I/O réelle — permission, fichier verrouillé par un autre processus) → **la suppression de l'entrée centrale est annulée**, l'erreur est affichée à l'architecte. Jamais de suppression best-effort qui laisserait un alias orphelin référencer encore les données physiques après disparition de l'entrée canonique — c'est exactement le risque soulevé par l'architecte en §3.4.
3. Si `expose_root` n'est pas configuré, ou si l'entrée n'a jamais été exposée (§5.4, no-op) → la suppression procède normalement, sans blocage.

### 5.6 Récapitulatif des invariants demandés explicitement

| Situation | Comportement |
|---|---|
| Exposition initiale | Création du hardlink, `AIStudioToolkit/` créé si absent |
| Exposition répétée, rien n'a changé | No-op idempotent (vérifié par `samefile`) |
| Retrait d'exposition (`unexpose`) | Suppression de l'alias uniquement ; no-op si déjà absent |
| Suppression d'une entrée déjà exposée | `unexpose` d'abord ; échec de `unexpose` **bloque** la suppression |
| Renommage de `LoRA.name` après exposition | Alias existant conservé tel quel jusqu'au prochain `expose_to_comfyui()` explicite, qui le remplace proprement (retrouvé via `lora_id`, jamais via le nom) |
| Alias au nom déterministe déjà occupé par un fichier différent | Erreur explicite, jamais d'écrasement |
| Alias existant et pointant bien vers le fichier canonique actuel | Traité comme already-exposed (no-op ou ré-exposition selon que le nom a changé, jamais recréé inutilement) |

## 6. Contrat définitif

1. **`src/domain/application_settings.py`** : ajouter `comfyui_lora_expose_path: str = ""` — désigne une racine `loras` **déjà déclarée** à ComfyUI par l'architecte (voir §3.3). Aucune valeur par défaut générée. Chaîne vide = exposition impossible, erreur explicite si tentée.
2. **`src/ui/pages/settings_page.py`** : champ de chemin + bouton de sélection pour `comfyui_lora_expose_path`, même patron que les champs de chemin existants. Aucun changement à `comfyui_lora_name_edit`/`refresh_loras()`.
3. **`src/managers/lora_library_manager.py`** — deux méthodes d'instance symétriques, aucun état de chemin propre au manager (patron déjà établi par `import_lora()`/`delete()`) :
   - `expose_to_comfyui(self, lora: LoRA, expose_root) -> LoRAComfyUIExposureResult` — implémente exactement §5.3. **Sans `library_root`** (voir §5.3 pour la justification) — écart accepté par l'architecte par rapport à la première version de ce contrat. Retourne un `NamedTuple` (`alias_name`, `cleanup_failed`, `residual_path`) — même patron que `LoRALibraryDeletionResult`/`LoRALibraryThumbnailResult` déjà existants, pas un simple `str` — pour reporter séparément un éventuel échec best-effort du nettoyage de l'ancien alias après un renommage (§5.3, cas 5).
   - `unexpose_from_comfyui(self, lora: LoRA, expose_root) -> bool` — implémente exactement §5.4.
   - Sous-dossier `AIStudioToolkit` : constante interne au module, non configurable.
4. **`src/ui/pages/lora_page.py`**, onglet bibliothèque centrale : action « Exposer à ComfyUI » appelant `expose_to_comfyui()` ; le flux de suppression existant implémente exactement §5.5 (bloquant, jamais best-effort).
5. **Aucun changement à `SettingsPage.comfyui_lora_name_edit`, `refresh_loras()`, `GenerationManager`, ni au modèle `LoRA.files`.**
6. **Aucune automatisation de la déclaration de la racine d'exposition à ComfyUI** : l'architecte reste seul responsable de déclarer, une fois, une racine `loras` existante correspondant à `comfyui_lora_expose_path` — le Toolkit ne lit, n'écrit et ne valide jamais un fichier de configuration ComfyUI.
7. **Tests** (`tests/integration/test_lora_library_roundtrip.py` et suites `SettingsPage`/`LoRAPage`) couvrant explicitement chaque ligne du tableau §5.6 : exposition initiale (hardlink réel sur disque, dossier temporaire NTFS), idempotence stricte (deuxième appel ne modifie rien), ré-exposition après renommage (ancien alias supprimé, nouveau créé, retrouvé par `lora_id`), `unexpose` idempotent, collision par anomalie externe (erreur explicite, jamais écrasement), refus explicite (`expose_root` vide, fichier absent, `len(files) != 1`, volumes différents — simulé selon ce que permet réellement l'environnement de test), suppression bloquée par un échec d'`unexpose` simulé.

## 7. Hors périmètre explicite de cette mission

- Modèle de scopes Character/Workspace/Global-Shared persistant (Option 2 — bibliothèque provisoirement globale — reste l'état de fait).
- Remplacement ou enrichissement de `SettingsPage.comfyui_lora_name_edit` par les entrées de la bibliothèque centrale (§3.6).
- Support d'un moteur autre que ComfyUI.
- Repli automatique par copie ou par symlink si le hardlink échoue (volumes différents) — un échec propre et explicite est la seule réponse ; aucun fallback introduit sans décision préalable séparée.
- Mise à jour automatique d'un alias existant lors d'un renommage (seulement au prochain appel explicite, §5.3).
- Toute modification de fichier de configuration ComfyUI, tout lancement/fermeture/mise à jour/réparation de ComfyUI Desktop par le Toolkit ou par l'agent pendant l'implémentation — l'instance démarrée manuellement par l'architecte reste la seule autorisée pour d'éventuels smoke tests live.
- Migration ou lien entre une LoRA Character-owned historique et une entrée de bibliothèque centrale (aucune donnée réelle concernée à ce jour).

## 8. Critères de clôture définitive

- Chaque ligne du tableau §5.6 couverte par un test dédié et réellement vérifiée (hardlink effectif sur disque pour le cas nominal, pas mocké).
- Nouveau champ `comfyui_lora_expose_path` persistant correctement (round-trip `ApplicationSettingsStorage`), UI Settings testée.
- Action « Exposer à ComfyUI » et orchestration suppression→`unexpose` (bloquante en cas d'échec) testées dans `LoRAPage`.
- Aucun changement à `SettingsPage.comfyui_lora_name_edit`/`refresh_loras()`/`GenerationManager`/`LoRA.files`.
- Suite complète verte, nombre exact confirmé.
- Tout smoke test live nécessaire à la clôture : uniquement contre une instance démarrée manuellement par l'architecte, jamais lancée/redémarrée/fermée par l'agent.

## 9. État d'avancement

- Mini-audit + smoke tests empiriques : **terminés**.
- Contrat : **validé par l'architecte**, avec un écart de signature accepté après implémentation (`expose_to_comfyui(self, lora, expose_root)`/`unexpose_from_comfyui(self, lora, expose_root)`, sans `library_root` — voir §5.3) et un type de retour `LoRAComfyUIExposureResult` (`NamedTuple`) plutôt qu'un `str` brut.
- Implémentation : **terminée**, strictement conforme au contrat corrigé.
  - `src/domain/application_settings.py` : champ `comfyui_lora_expose_path` ajouté (`""` par défaut, aucune valeur générée).
  - `src/managers/application_settings_manager.py` : `update()` étendu symétriquement, sans verrou (contrairement à `lora_library_path`).
  - `src/managers/lora_library_manager.py` : `expose_to_comfyui()`/`unexpose_from_comfyui()` implémentées exactement selon §5.3/§5.4 ; `LoRAComfyUIExposureResult` ajouté.
  - `src/ui/pages/settings_page.py` : champ + bouton « Parcourir… » pour `comfyui_lora_expose_path`.
  - `src/ui/pages/lora_page.py` : action « Exposer à ComfyUI » ; suppression orchestrée avec `unexpose_from_comfyui()` bloquant en cas d'échec (§5.5).
- **Audit des appelants de `LoRALibraryManager.delete()`** : confirmé, par recherche exhaustive dans `src/` (hors tests), que `LoRAPage.delete_from_library()` est l'**unique** chemin applicatif de production appelant cette méthode — `main_window.py` ne fait que construire/câbler `LoRALibraryManager`, `application_settings_manager.py` n'appelle que `list_loras()` (verrou de chemin), `settings_page.py` ne le référence que dans un commentaire. L'invariant « aucune suppression canonique ne peut laisser un alias hardlink orphelin » est donc garanti par construction — aucun refactor nécessaire.
- **Incident de harnais de test** : un premier passage de la nouvelle classe `LoRAPageComfyUIExposureTest` a bloqué sur une vraie `QMessageBox` (3 appels à `expose_selected_to_comfyui()` non mockés, filet Mission 091 non armé dans cette nouvelle classe) — corrigé par mock explicite des 3 appels, armement du filet en `setUp()`/`tearDown()` de toute la classe, et ajout d'une preuve dédiée (`test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure`). Comportement de production (`QMessageBox.information()` sur succès) inchangé.
- **Tests ciblés (non-régression)** : `test_lora_library_roundtrip.py` 81/81, `test_lora_roundtrip.py` 263/263, `test_application_settings_roundtrip.py` 17/17, `test_settings_page.py`+`test_settings_roundtrip.py`+`test_main_window_comfyui_settings.py`+`test_main_window_ollama_settings.py` 95/95 — **456/456 OK**.
- **Smoke test réel** contre l'instance ComfyUI démarrée manuellement par l'architecte (`127.0.0.1:8000`, jamais lancée/redémarrée/fermée par l'agent) : entrée centrale de test isolée → `expose_to_comfyui()` → alias confirmé via `ComfyUIEngine.list_loras()` sous `AIStudioToolkit\<alias>` → `unexpose_from_comfyui()` → disparition confirmée sans redémarrage → racine ComfyUI réelle strictement restaurée à son état initial → serveur toujours sain. **PASS**.
- **Deux full suites consécutives, sans instrumentation temporaire** : **1771/1771 OK** (162.6s) puis **1771/1771 OK** (162.4s) — 0 boîte de dialogue visible, 0 intervention humaine, aucun processus de test résiduel.
- `git diff --check` : propre.
- Aucun fichier Graphify modifié. Aucune configuration/package ComfyUI modifié pendant l'implémentation.
- Commit de mission : `50eea64019624848c536b4a73d2c590531a81944` — "Add ComfyUI exposure for the central LoRA library via NTFS hardlink", poussé sur `main`.
- Tag annoté : `v0.2-mission095`, ciblant exactement le commit de mission ci-dessus, poussé.
