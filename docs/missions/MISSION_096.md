# Mission 096 — Real Generation Parameters for Inference

> **MISSION IMPLÉMENTÉE, VALIDÉE PAR L'ARCHITECTE, CLÔTURE GIT EFFECTUÉE, GITHUB RELEASE PUBLIÉE.** Voir section 15 pour l'état final.

## 1. Contexte

L'audit global de maturité post-Mission 095 a établi, par lecture directe du code (`InferencePage` → `GenerationManager.generate()` → `ComfyUIEngine.generate_image()` → `build_txt2img_workflow()`/`build_img2img_workflow()`), un constat non documenté jusqu'alors : la génération d'image réelle reste, telle quelle depuis la Mission 012, le **workflow de démonstration fixe** de cette mission — le code lui-même le nomme ainsi (« Mission 012's fixed demonstration workflow », `comfyui_workflows.py:88`). Résolution figée à 512×512, `batch_size=1`, `steps=20`/`cfg=8`/`sampler_name="euler"`/`scheduler="normal"` codés en dur, prompt négatif codé en dur (`"text, watermark"`), seed aléatoire non reproductible (`random.randint(0, 2**32-1)`, jamais retourné à l'appelant). `GenerationManager.generate()` n'accepte aujourd'hui que `prompt_text`/`reference_images`/`reference_strength` — aucun autre levier.

L'architecte a validé ce constat comme prioritaire et retient l'orientation Mission 096 : faire évoluer `InferencePage` d'un panneau minimal (prompt + référence) vers un véritable panneau de paramètres de génération ComfyUI, sans exiger de nouvelle décision architecturale non résolue (pas de Training, pas de nouveau moteur, pas de détection automatique d'architecture de checkpoint, pas de refonte Prompt Library).

Ce document est le contrat issu du mini-audit demandé avant toute implémentation — verrouille le trajet exact de chaque paramètre, les valeurs par défaut de compatibilité, et les décisions de périmètre (résolution libre, seed à deux usages, sampler/scheduler par découverte dynamique, batch maintenu à 1, prompt négatif éditable, aucune nouvelle architecture de persistance).

## 2. Objectif

Faire évoluer `InferencePage` d'un workflow de démonstration figé (Mission 012) vers un panneau de paramètres de génération réels — largeur, hauteur, steps, CFG, sampler, scheduler, seed (aléatoire ou fixe), prompt négatif — tout en conservant strictement la compatibilité de comportement pour tout appelant qui ne fournit aucun de ces nouveaux paramètres (tests existants, contrat `build_txt2img_workflow()`/`build_img2img_workflow()` inchangé par défaut).

## 3. Trajet actuel des paramètres — audit ligne par ligne

Vérifié directement en source, chaîne complète `InferencePage._start_generation()` → `GenerationWorker.run()` → `GenerationManager.generate()` → `ComfyUIEngine.generate_image()`/`_submit_and_download()` → `build_txt2img_workflow()`/`build_img2img_workflow()` :

| Paramètre | État actuel | Défini | Transmis |
|---|---|---|---|
| Largeur/hauteur | Codés en dur `512`/`512` dans `EmptyLatentImage` (node `"5"`, `comfyui_workflows.py:128`) | Nulle part — aucun paramètre à aucune couche | Jamais |
| Nombre d'images (batch) | Codé en dur `batch_size: 1` (même node) | Nulle part | Jamais |
| Steps | Codé en dur `20` dans `KSampler` (node `"3"`) | Nulle part | Jamais |
| CFG | Codé en dur `8` (même node) | Nulle part | Jamais |
| Sampler | Codé en dur `"euler"` (même node) | Nulle part | Jamais |
| Scheduler | Codé en dur `"normal"` (même node) | Nulle part | Jamais |
| Seed | `random.randint(0, 2**32-1)` calculé **à l'intérieur** de `build_txt2img_workflow()`/`build_img2img_workflow()`, jamais remonté à l'appelant | Interne au builder | Jamais retourné — `generate_image()`/`generate()` ne renvoient qu'un `str` (chemin local du fichier téléchargé) |
| Prompt négatif | Codé en dur `"text, watermark"` dans `CLIPTextEncode` (node `"7"`, identique dans les deux graphes) | Nulle part | Jamais |
| Force de référence (`reference_strength`) | **Déjà réel** — `InferencePage.reference_strength_slider` (0-100), converti en `0.0-1.0` dans `_start_generation()`, transmis en paramètre `generate()`, forwardé en `denoise=` uniquement si une référence est active (`generation_manager.py:190-191`) | `InferencePage` (état local UI, jamais persisté) | `GenerationWorker` → `GenerationManager.generate(reference_strength=...)` → `ComfyUIEngine.generate_image(denoise=...)` |

**Constat structurel additionnel, déterminant pour le contrat** : `build_img2img_workflow()` ne possède **aucun** paramètre largeur/hauteur/batch — les dimensions du latent proviennent de `VAEEncode` appliqué à l'image de référence chargée (« no width/height/batch_size to set, ComfyUI derives the latent's dimensions from the loaded image itself », `comfyui_workflows.py:179-181`). Largeur/hauteur/batch ne sont donc **significatifs que sur le chemin txt2img** (sans référence active) — le contrat UI doit désactiver ces trois champs dès qu'une référence est sélectionnée, plutôt que de les transmettre silencieusement sans effet. Steps/CFG/sampler/scheduler/seed/prompt négatif, en revanche, sont structurellement identiques dans les deux graphes (même `KSampler`/`CLIPTextEncode` nodes) — s'appliquent donc uniformément aux deux chemins.

`reference_strength` confirme par ailleurs le patron déjà établi et directement réutilisable pour tous les nouveaux paramètres : **état local d'`InferencePage`, jamais persisté, relu à chaque appel de `_start_generation()`** — jamais un paramètre de construction de `GenerationManager` (contrairement à `checkpoint_name`/`lora_name`, choix moteur figés au démarrage sans hot-reload).

## 4. Résolution — largeur/hauteur libres, pas de presets figés

Décision : **pas de presets fermés (512/768/1024)**. Deux champs numériques indépendants (largeur, hauteur), permettant portrait/paysage/carré à volonté, conformément à la demande explicite.

**Contrainte technique réelle** (connaissance de domaine Stable Diffusion/ComfyUI, non vérifiée en direct pendant cet audit — aucun accès à une instance ComfyUI n'a été utilisé, conformément à la consigne) : le nœud `EmptyLatentImage` encode l'image dans l'espace latent du VAE, dont le facteur de sous-échantillonnage standard (SD1.5, SDXL, et la quasi-totalité des architectures dérivées) est ×8 — largeur et hauteur doivent être des multiples de 8, propriété reflétée par le pas (`step`) de 8 des widgets natifs de l'interface ComfyUI elle-même pour ce nœud. Cette contrainte est réelle et mécanique, indépendante du modèle chargé — elle **n'exige pas** de détecter si le checkpoint est SD1.5/SDXL/FLUX (explicitement hors périmètre). Cette hypothèse sera reconfirmée empiriquement pendant le smoke test réel de mise en œuvre, contre l'instance démarrée manuellement par l'architecte, avant clôture — jamais présumée acquise sans vérification.

**Validation retenue** : rejet explicite (message clair, même patron que `QMessageBox.warning` déjà utilisé pour « Prompt vide »/« Aucun projet ouvert ») si la valeur n'est pas un multiple de 8 — jamais un arrondi silencieux, cohérent avec le principe déjà établi dans ce projet (« erreur explicite, jamais d'écrasement/de correction silencieuse »). Bornes de raisonnabilité proposées, **purement des garde-fous UI** (pas une limite technique ComfyUI réelle) : 64 à 2048 pour chaque dimension — évite une saisie absurde (0, négatif, valeur extrême) sans prétendre connaître la VRAM réellement disponible sur la machine de l'architecte. `QSpinBox` avec `setSingleStep(8)` pour guider la saisie, validation explicite avant soumission dans tous les cas (la saisie clavier directe dans un `QSpinBox` n'est pas contrainte au pas).

**Trajet** : deux nouveaux champs `InferencePage.width_spinbox`/`height_spinbox`, désactivés dès qu'une image de référence est active (§3), lus dans `_start_generation()`, transmis en paramètres `width`/`height` de `GenerationManager.generate()` → `ComfyUIEngine.generate_image()` → `build_txt2img_workflow(width=..., height=...)`, ignorés/non transmis par `build_img2img_workflow()` qui ne les accepte pas (signature inchangée sur ce point).

## 5. Seed — deux usages explicites, capture pour affichage, persistance différée

**Les deux usages requis** : un mode « Aléatoire » (comportement actuel, une valeur différente à chaque génération) et un mode « Fixe/reproductible » (l'architecte saisit un entier, réutilisé tel quel).

**Contrainte de compatibilité découverte pendant l'audit** : `tests/integration/test_comfyui_workflows.py::BuildTxt2ImgWorkflowTest::test_seed_is_randomized_between_calls` (ligne 96) appelle `build_txt2img_workflow("a red fox")` **sans argument seed**, deux fois, et vérifie que les deux seeds diffèrent — le comportement `random.randint(...)` interne aux builders, déclenché quand `seed` n'est pas fourni, **doit être préservé intact** pour ne pas casser ce test existant.

**Décision retenue, conciliant les deux points** : `build_txt2img_workflow(..., seed: Optional[int] = None, ...)`/`build_img2img_workflow(..., seed: Optional[int] = None, ...)` conservent leur fallback interne `random.randint(0, 2**32-1)` quand `seed is None` — comportement de `test_seed_is_randomized_between_calls` intact, aucune modification de ce test. `GenerationManager.generate(..., seed: Optional[int] = None, ...)` transmet `seed` sans l'interpréter (même patron que `reference_strength`). **`InferencePage`, en revanche, ne laisse jamais `seed` à `None`** : en mode Aléatoire, elle calcule elle-même `random.randint(0, 2**32-1)` (même plage, même distribution que le fallback actuel) juste avant l'appel et transmet cette valeur concrète ; en mode Fixe, elle transmet l'entier saisi par l'architecte. Ce déplacement, à la frontière UI, suit exactement le précédent déjà établi par `reference_strength` (conversion 0-100 → 0.0-1.0 faite dans `InferencePage`, jamais plus bas) — c'est ce qui permet de répondre « oui » à la question suivante sans aucune modification de couche basse.

**Le seed réellement utilisé peut-il être récupéré et affiché ?** Oui, trivialement, avec cette conception : puisque `InferencePage` choisit elle-même la valeur concrète avant l'appel (que le mode soit Aléatoire ou Fixe), elle la connaît déjà — un nouveau label en lecture seule (« Seed utilisé : 3821947705 ») affiché après chaque génération réussie, permettant à l'architecte de le copier manuellement s'il veut le fixer pour une prochaine génération. Aucun changement de signature de retour n'est nécessaire à `generate_image()`/`generate()` (qui continuent à ne renvoyer que le chemin du fichier).

**Peut-il être conservé avec le résultat généré (persistance) ?** Non, pas dans cette mission — audité et confirmé : `src/domain/image.py::Image` est un dataclass à deux champs seulement (`image_id`, `file_path`), aucune métadonnée. Conserver le seed avec l'image acceptée exigerait d'étendre ce modèle Domain (nouveau champ, ex. `generation_metadata` ou champs dédiés), une évolution réelle du modèle `Image` — **explicitement documentée ici comme extension future séparée, non introduite silencieusement dans M096**, conformément à l'instruction.

## 6. Sampler / Scheduler — découverte dynamique via ComfyUI, jamais de liste figée

**Mécanisme retenu** : ComfyUI expose déjà, via `GET /object_info/<NodeClass>`, la liste exacte des valeurs COMBO acceptées par un nœud — c'est très précisément le mécanisme déjà utilisé et testé par `ComfyUIEngine.list_checkpoints()` (`/object_info/CheckpointLoaderSimple`, `node_info["input"]["required"]["ckpt_name"][0]`) et `list_loras()` (`/object_info/LoraLoader`, même structure). Ce même mécanisme s'applique à l'identique pour `KSampler` : `node_info["input"]["required"]["sampler_name"][0]` et `["scheduler"][0]` renvoient les listes réelles acceptées par la version de ComfyUI de l'architecte — **aucune liste codée en dur côté Toolkit**, troisième application du même patron déjà éprouvé (pas une nouvelle mécanique architecturale).

**Nouvelles méthodes** : `ComfyUIEngine.list_samplers() -> list[str]`/`list_schedulers() -> list[str]`, mêmes conventions d'erreur que `list_checkpoints()`/`list_loras()` (`ComfyUIEngineError` sur toute anomalie, jamais de liste partielle/devinée). `GenerationManager` expose deux passthroughs fins (`list_samplers()`/`list_schedulers()` délégant à son `_comfyui_engine` privé) — **jamais** d'accès direct d'`InferencePage` à `ComfyUIEngine`, respect strict de la couche Managers déjà établie (contrairement à `SettingsPage`, qui construit son propre `ComfyUIEngine` ad hoc pour refléter une URL en cours de frappe non encore sauvegardée — cas non applicable ici, `InferencePage` réutilise l'engine déjà configuré, sans hot-reload d'URL en jeu).

**Comportement si ComfyUI est indisponible** (exigé explicitement) : même patron déjà en production dans `SettingsPage.refresh_checkpoints()`/`refresh_loras()` — bouton « Rafraîchir » déclenchant l'appel synchrone (timeout court, même constante `5.0s` que `CHECKPOINT_DISCOVERY_TIMEOUT`/`LORA_DISCOVERY_TIMEOUT`), échec intercepté (`ComfyUIEngineError`) → label de statut explicite (« Découverte impossible : ComfyUI injoignable... La saisie manuelle reste disponible »), jamais bloquant. Les deux champs sont des `QComboBox` **éditables**, pré-remplis par défaut avec `"euler"`/`"normal"` (valeurs de compatibilité) même sans aucune découverte réussie — l'architecte peut toujours taper une valeur manuellement, découverte ou non.

## 7. Batch / nombre d'images — maintenu à 1 dans cette mission

**Audit du contrat preview/accept actuel** (Missions 014/084/085) : `InferencePage._on_generation_finished(self, path)` reçoit un **unique** chemin de fichier ; `_pending_path`/`_pending_pixmap` sont des scalaires, jamais des collections ; `GenerationWorker.finished = Signal(str)` (une seule chaîne) ; `ComfyUIEngine._submit_and_download()` télécharge explicitement « the first image found in result » (`_first_image_reference()`, ne considère que le premier output image trouvé, peu importe combien ComfyUI en aurait produit). Le cycle complet Accept/Reject/Regenerate — avec ses guards de fermeture d'application (Mission 084), de changement de Workspace (Mission 085), et son verrou `_busy` sur `GenerationManager` empêchant toute génération concurrente — est structurellement conçu autour d'**un seul résultat en attente à la fois**.

**Décision** : `batch_size` reste codé à `1`, **non exposé** comme paramètre dans cette mission. Le transformer en paramètre réel exigerait de repenser tout le contrat de preview/validation (plusieurs chemins en attente, plusieurs décisions Accept/Reject indépendantes, sélection parmi plusieurs miniatures) — un chantier de taille comparable à Mission 014 elle-même, hors périmètre de M096 tel que cadré par l'architecte. **Documenté ici comme extension future séparée**, non entamée.

## 8. Prompt négatif — champ éditable, plus de comportement invisible

**Valeur actuelle exacte, vérifiée en source** (`comfyui_workflows.py:136,234`, confirmée par 4 assertions de test — `test_comfyui_workflows.py:48,177,252,313`) : `"text, watermark"`, identique sur les deux graphes.

**Décision** : nouveau champ `InferencePage.negative_prompt_edit` (`QTextEdit` ou `QLineEdit` court — un `QLineEdit` suffit, le prompt négatif est presque toujours court), **valeur initiale = `"text, watermark"`** (compatibilité stricte : une génération lancée sans y toucher reproduit le comportement actuel à l'identique). Éditable, jamais persisté au-delà de la session (même statut que `reference_strength`) — pas de nouveau champ `ApplicationSettings`. Transmis en paramètre `negative_prompt: str = "text, watermark"` à chaque couche (`generate()` → `generate_image()` → les deux builders), même patron additif que tous les autres nouveaux paramètres.

## 9. Persistance des paramètres — état courant d'Inference uniquement, aucune nouvelle architecture

**Décision tranchée par ce mini-audit** : tous les nouveaux paramètres (largeur, hauteur, steps, CFG, sampler, scheduler, mode seed + valeur, prompt négatif) suivent exactement le patron déjà établi par `reference_strength` — **état local d'`InferencePage`, jamais persisté**, ni dans `ApplicationSettings` (moteur/engine-level, incompatible avec des valeurs qui changent à chaque génération), ni par Workspace (`project.json` ne porte aucune notion de préférences de génération aujourd'hui, et il n'existe aucun besoin démontré de les faire survivre à un changement de Workspace), ni via une nouvelle architecture de presets/profils (explicitement exclue par l'architecte pour cette mission). Chaque champ revient à sa valeur de compatibilité par défaut à chaque lancement de l'application — cohérent avec le contrat de compatibilité (§11) et le principe « pas de scaffolding avant un besoin réel » (`CLAUDE.md`). Si un besoin réel de persistance (par Workspace ou globalement) apparaît à l'usage, il sera audité comme mission distincte plutôt que anticipé ici.

## 10. Contrat définitif par couche

1. **`src/engines/workflows/comfyui_workflows.py`** :
   - Nouvelles constantes : `DEFAULT_WIDTH = 512`, `DEFAULT_HEIGHT = 512`, `DEFAULT_STEPS = 20`, `DEFAULT_CFG = 8`, `DEFAULT_SAMPLER_NAME = "euler"`, `DEFAULT_SCHEDULER = "normal"`, `DEFAULT_NEGATIVE_PROMPT = "text, watermark"`.
   - `build_txt2img_workflow(prompt_text, checkpoint_name=..., lora_name="", lora_strength=1.0, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, steps=DEFAULT_STEPS, cfg=DEFAULT_CFG, sampler_name=DEFAULT_SAMPLER_NAME, scheduler=DEFAULT_SCHEDULER, seed: Optional[int] = None, negative_prompt=DEFAULT_NEGATIVE_PROMPT)` — `batch_size` reste un littéral `1` non paramétré (§7) ; `seed=None` préserve le fallback `random.randint(...)` interne (§5).
   - `build_img2img_workflow(...)` : mêmes nouveaux paramètres **sauf** `width`/`height`/`batch_size`, qui n'existent structurellement pas sur ce chemin (§3) — signature volontairement asymétrique, documentée en docstring.
2. **`src/engines/comfyui_engine.py`** :
   - `generate_image(...)` étendu avec les mêmes paramètres additifs, forwardés tels quels au builder choisi (txt2img ou img2img), `width`/`height` silencieusement absents de l'appel `build_img2img_workflow()` (jamais transmis, jamais une erreur).
   - Nouvelles méthodes `list_samplers() -> list[str]`/`list_schedulers() -> list[str]` (§6), mêmes conventions que `list_checkpoints()`/`list_loras()`.
3. **`src/managers/generation_manager.py`** :
   - `generate(...)` étendu avec les mêmes paramètres additifs (tous `Optional`/valeur de compatibilité par défaut), forwardés à `ComfyUIEngine.generate_image()` sans interprétation métier (même statut que `reference_strength` aujourd'hui) ; `width`/`height` ignorés sans erreur quand une référence est active (transmis uniquement sur le chemin txt2img, cohérent avec §3).
   - Nouvelles méthodes passthrough `list_samplers()`/`list_schedulers()` déléguant à `self._comfyui_engine`.
4. **`src/ui/generation_worker.py`** : constructeur étendu avec les mêmes paramètres, capturés par valeur avant `moveToThread()` (même patron que `reference_strength`), forwardés tels quels dans `run()`.
5. **`src/ui/pages/inference_page.py`** :
   - Nouveaux widgets : `width_spinbox`/`height_spinbox` (`QSpinBox`, pas 8, bornes 64-2048, désactivés si une référence est active), `steps_spinbox` (bornes raisonnables, ex. 1-150), `cfg_spinbox` (`QDoubleSpinBox`, ex. 0-30), `sampler_combo`/`scheduler_combo` (`QComboBox` éditables, valeurs par défaut `"euler"`/`"normal"`, bouton « Rafraîchir » déclenchant `list_samplers()`/`list_schedulers()` via `GenerationManager`, fallback gracieux §6), un contrôle de mode seed (ex. case à cocher « Aléatoire », activée par défaut) + `seed_spinbox` (actif seulement en mode Fixe), `negative_prompt_edit` (valeur initiale `"text, watermark"`), et un label de résultat « Seed utilisé : … » rempli après chaque génération réussie (§5).
   - `_start_generation()` : validation explicite (largeur/hauteur multiples de 8, rejet sinon — §4), résolution du seed concret (§5), lecture de tous les nouveaux champs, transmission à `GenerationWorker`.
   - `_on_reference_selected`/`_on_reference_removed` (noms exacts à confirmer en implémentation) : activent/désactivent `width_spinbox`/`height_spinbox` selon la présence d'une référence (§3).

## 11. Stratégie de compatibilité

Toute génération lancée sans toucher aux nouveaux champs doit reproduire le comportement actuel **à l'identique** : `width=512`, `height=512`, `batch_size=1` (non paramétré), `steps=20`, `cfg=8`, `sampler_name="euler"`, `scheduler="normal"`, `negative_prompt="text, watermark"`, seed toujours aléatoire par défaut (case « Aléatoire » cochée par défaut). Les 4 tests existants pinnant `"text, watermark"`, les tests pinnant `{"batch_size": 1, "height": 512, "width": 512}`/`"euler"`/`"normal"`/`cfg: 8`/`steps: 20`, et `test_seed_is_randomized_between_calls` (appel sans argument `seed`) doivent continuer à passer **sans aucune modification** — les nouveaux paramètres sont strictement additifs à chaque couche, jamais un changement de signification d'un appel existant.

## 12. Tests ciblés et smoke tests prévus (implémentation future, non commencée)

- `tests/integration/test_comfyui_workflows.py` : nouveaux tests par paramètre (largeur/hauteur/steps/cfg/sampler/scheduler/seed fixe/negative_prompt transmis correctement au node attendu), confirmation explicite que `build_img2img_workflow()` n'accepte pas `width`/`height`/`batch_size`, non-régression complète des tests existants (aucune modification attendue).
- `tests/integration/test_comfyui_engine.py` : `list_samplers()`/`list_schedulers()` — succès, erreur serveur, forme de réponse inattendue (même trio de scénarios que `ComfyUIEngineListCheckpointsTest`).
- `tests/integration/test_generation_manager.py` : forwarding de chaque nouveau paramètre vers `ComfyUIEngine.generate_image()`, `width`/`height` absents de l'appel quand une référence est active, passthroughs `list_samplers()`/`list_schedulers()`.
- `tests/integration/test_inference_page.py` : validation largeur/hauteur (rejet non-multiple-de-8, bornes), désactivation largeur/hauteur avec référence active, mode seed aléatoire vs fixe (valeur concrète transmise, jamais `None`), affichage du seed utilisé après génération, découverte sampler/scheduler réussie/échouée (fallback), valeur initiale du prompt négatif, non-régression complète du cycle Accept/Reject/Regenerate.
- **Smoke test réel** : contre l'instance ComfyUI démarrée manuellement par l'architecte uniquement (jamais lancée/redémarrée/fermée par l'agent — si indisponible, signaler la limite plutôt que la démarrer) — au minimum une génération portrait (ex. 512×768), une génération paysage (ex. 768×512), une génération avec seed fixe répétée deux fois produisant une image identique, une découverte réelle de sampler/scheduler, une génération avec référence active confirmant que largeur/hauteur restent désactivés et sans effet.

## 13. Fichiers probablement concernés

`src/engines/workflows/comfyui_workflows.py`, `src/engines/comfyui_engine.py`, `src/managers/generation_manager.py`, `src/ui/generation_worker.py`, `src/ui/pages/inference_page.py`, `tests/integration/test_comfyui_workflows.py`, `tests/integration/test_comfyui_engine.py`, `tests/integration/test_generation_manager.py`, `tests/integration/test_inference_page.py`.

## 14. Hors périmètre explicite

Aucune découverte contraire n'a été faite pendant ce mini-audit — le périmètre présumé par l'architecte est confirmé intact : pas de Training, pas de nouveau moteur, pas de multi-référence, pas de refonte Prompt Library, pas de presets/profils de génération complexes, pas de détection automatique d'architecture de checkpoint (SD1.5/SDXL/FLUX), pas de modification du modèle LoRA, pas de modification de configuration ComfyUI. S'ajoutent, identifiés précisément par ce mini-audit : pas de génération multi-image/batch réelle (§7, extension future documentée), pas de persistance du seed avec l'image acceptée (§5, nécessite une évolution du modèle Domain `Image`, extension future documentée), pas de nouvelle architecture de persistance des paramètres de génération (§9).

## 15. État d'avancement

Mini-audit contractuel **terminé**, contrat validé par l'architecte, **implémentation terminée et strictement conforme au contrat**.

### Écarts au contrat

Deux précisions techniques nécessaires, découvertes pendant l'implémentation, non anticipées par le mini-audit — aucune ne modifie le contrat fonctionnel :
- **Champ seed fixe en `QLineEdit`, pas `QSpinBox`** : `QSpinBox` est limité à un entier signé 32 bits (max `2**31-1`), insuffisant pour couvrir `random.randint(0, 2**32-1)` — validation manuelle explicite (`MIN_SEED`/`MAX_SEED`) plutôt qu'un widget qui aurait silencieusement réduit la plage atteignable en mode fixe.
- **Timeout de découverte sampler/scheduler** : `GenerationManager`/`ComfyUIEngine` réutilisent l'engine déjà configuré (timeout de génération, 120 s par défaut) — un paramètre `timeout` optionnel a été ajouté à `ComfyUIEngine._request_json()`/`list_samplers()`/`list_schedulers()` et `GenerationManager.list_samplers()`/`list_schedulers()` pour permettre à `InferencePage` de passer un timeout court dédié à la découverte, plutôt que de risquer un gel de l'UI jusqu'à 120 s si ComfyUI est injoignable.

### Fichiers modifiés

`src/engines/workflows/comfyui_workflows.py`, `src/engines/comfyui_engine.py`, `src/managers/generation_manager.py`, `src/ui/generation_worker.py`, `src/ui/pages/inference_page.py`, `tests/integration/test_comfyui_workflows.py`, `tests/integration/test_comfyui_engine.py`, `tests/integration/test_generation_manager.py`, `tests/integration/test_inference_page.py`, `tests/integration/test_main_window_close_event.py`, `tests/integration/test_main_window_new_project.py`, `tests/integration/test_main_window_rename_project.py` (3 derniers : mise à jour d'un fake `generate()` de test pour accepter les nouveaux kwargs — aucun changement de comportement testé).

### Tests ciblés

**459/459 OK** sur les 8 fichiers de test directement concernés : `test_comfyui_workflows.py` 54/54, `test_comfyui_engine.py` 96/96, `test_generation_manager.py` 47/47, `test_generation_worker.py` 10/10 (inchangé, confirmé compatible sans modification), `test_inference_page.py` 156/156 (dont la nouvelle classe `InferencePageGenerationParametersTest`, 28/28), `test_main_window_close_event.py` 32/32, `test_main_window_new_project.py` 42/42, `test_main_window_rename_project.py` 22/22.

### Smoke test Qt réel

**25/25 PASS** — widgets réels (`setValue`/`click`/`setChecked`/`setCurrentText`/`setText`), `GenerationManager` mocké : changement de résolution, changement des paramètres avancés (steps/CFG/sampler/scheduler/prompt négatif), seed fixe (valeur exacte transmise, affichée immédiatement, Regenerate la réutilise), seed aléatoire (valeur concrète transmise et affichée, Regenerate en produit une nouvelle), activation/désactivation largeur/hauteur à l'ajout/retrait d'une référence (clics réels), rejet d'une résolution invalide (vraie `QMessageBox.warning` interceptée), découverte sampler/scheduler réussie et son repli gracieux en échec.

### Smoke test ComfyUI réel

**Exécuté avec succès — 16/16 PASS**, contre l'instance restart manuellement par l'architecte après un premier plantage au démarrage de ComfyUI Desktop (anomalie externe, hors périmètre M096, non traitée). Port réellement utilisé confirmé en lecture seule (`Get-NetTCPConnection`, PID réellement en écoute) avant tout appel, jamais supposé. Résultats :
- Découverte réelle `GET /object_info/KSampler` : `list_samplers()`/`list_schedulers()` renvoient bien les listes exactes exposées par cette instance (42 samplers, 9 schedulers), format conforme.
- Workflow txt2img avec valeurs non par défaut (576×704, steps=6, cfg=6.5, sampler=`dpmpp_2m`, scheduler=`karras`, seed=20260903, prompt négatif personnalisé) : soumis avec succès, exécuté réellement, image produite avec les dimensions **exactement** demandées (576×704, jamais 512×512). Le seed **embarqué dans les métadonnées PNG natives de ComfyUI** (chunk `tEXt "prompt"`, indépendant de toute déclaration côté Toolkit) correspond exactement à celui soumis — confirmation serveur, pas un simple écho client.
- **Constat empirique important sur la résolution non multiple de 8** : ComfyUI **n'a pas rejeté** une soumission 513×513 au niveau de son API `/prompt` — elle a été acceptée puis exécutée, produisant une image en 512×512 (arrondi silencieux interne, confirmé par inspection du fichier réellement produit). **Ceci confirme que la validation stricte côté Toolkit (rejet explicite avant soumission) n'est pas une simple précaution UX mais une nécessité réelle** : sans elle, une résolution invalide serait silencieusement corrigée par ComfyUI sans aucun avertissement à l'architecte.
- Workflow img2img : `VAEEncode` confirmé sans clé `width`/`height` dans le workflow réellement soumis ; image de référence 384×576 (téléversée réellement) ; image produite en sortie mesurée à **384×576 exactement** — jamais 512×512 ni les valeurs txt2img de la même session (576×704), confirmant empiriquement que les dimensions proviennent bien de la référence.
- Backend confirmé toujours sain (`HTTP 200` sur `/system_stats`) après chaque étage et à la fin.

**Nettoyage effectué** : les 3 fichiers produits dans `J:\Programmes\ComfyUI\output\` (`AIStudioToolkit_00001_.png` à `_00003_.png`, tous horodatés de cette session) supprimés ; copies locales de scratch supprimées ; file d'attente ComfyUI vérifiée vide après coup. Aucun modèle, LoRA, custom node ou fichier de configuration ComfyUI touché.

### Anomalie externe consignée — hors périmètre M096

Premier démarrage de ComfyUI Desktop : plantage backend (« ComfyUI exited unexpectedly », exit code 4294967295), résolu par un « Restart ComfyUI » manuel de l'architecte. Externe à AI Studio Toolkit, non diagnostiqué ni traité par cette mission.

### Incident diagnostiqué pendant la validation — non lié à M096

Un crash natif reproductible (`STATUS_HEAP_CORRUPTION`, Windows) a été observé lors de l'exécution isolée de `test_main_window_new_project.py` via `unittest discover`. Diagnostiqué avec `faulthandler` : origine dans `MainWindow.__init__()` (construction Qt native), jamais dans le code applicatif. **Confirmé pré-existant** : reproduit à l'identique sur le code de base (`git stash` des changements M096, même commande, même point de crash) — c'est l'« aléa d'environnement natif Qt/PySide6 » déjà documenté dans l'historique du projet (Missions 063-069+), non causé ni aggravé par cette mission. Ne s'est manifesté à aucun moment pendant les deux suites complètes finales.

### Full suite

**Deux suites complètes consécutives via `unittest discover -s tests -p "test_*.py"` : 1845/1845 OK** (209.5 s puis 212.0 s) — 0 dialogue visible, 0 intervention humaine, aucun processus résiduel après chaque exécution.

### Vérifications finales

`git diff --check` : propre (seuls avertissements CRLF/LF bénins). `git status` : seuls les 12 fichiers listés ci-dessus modifiés + `MISSION_096.md` non suivi. Aucun fichier Graphify modifié. Aucune configuration/exécutable ComfyUI touché.

- Commit de mission : `8121904140985396e85fa369b343f45599a0803e` — "Add real generation parameters to Inference (width/height/steps/CFG/sampler/scheduler/seed/negative prompt)", poussé sur `main`.
- Commit documentaire : `2cd128a35c0de70926678467612f691f6ff16c05` — "docs: record Mission 096 commit and tag in MISSION_096.md", poussé sur `main`.
- Tag annoté : `v0.2-mission096`, ciblant exactement le commit de mission ci-dessus (jamais le commit documentaire), poussé.
- GitHub Release `v0.2-mission096` : **publiée**, confirmée par l'architecte.
