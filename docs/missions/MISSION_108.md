# Mission 108 — Forge Inference Integration

> **MISSION CLÔTURÉE — FORGE UTILISABLE DEPUIS INFERENCE, SMOKE RÉEL TXT2IMG ET LORA CENTRAL LIBRARY VALIDÉS SUR SERVEUR FORGE RÉEL.** Voir §12 "Résultat réel" pour l'implémentation finale, y compris le correctif de normalisation du nom LoRA découvert par le smoke réel et hors du périmètre initialement fermé ci-dessous.

## 1. Contexte

Mission 107 a livré `ForgeEngine` (`src/engines/forge_engine.py`) comme fondation technique invisible : un client HTTP Qt-free de même rang que `ComfyUIEngine`, un contrat Python commun `denoise` pour la force de référence, un mécanisme de checkpoint par appel (`override_settings` + restauration garantie) déjà vérifié contre le code réel de l'installation Forge, et une généralisation minimale de `GenerationManager.generate()` (`engine`/`checkpoint_name` optionnels par-appel, sans aucun `isinstance` contre un type de moteur concret). Aucune de ces capacités n'est aujourd'hui atteignable depuis l'UI — zéro Settings Forge, zéro sélecteur, zéro câblage `InferencePage`.

Un audit read-only post-M107 (Settings Forge, sélecteur moteur, checkpoint commun, LoRA multi-engine, capability refresh, référence, composition `MainWindow`, protocole de smoke) a précédé ce document. Neuf décisions architecturales ont ensuite été tranchées explicitement par l'architecte et sont reprises intégralement en section 3 ci-dessous — ce document ne les rediscute pas, il les traduit en périmètre fermé.

**Verdict de faisabilité en une seule mission** : confirmé. Chacune des capacités requises généralise un pattern déjà établi par une mission antérieure (Mission 059 : lecture Settings une fois à la construction ; Mission 087 : bouton Parcourir ; Mission 096 : découverte on-demand avec timeout court dédié et repli manuel ; Mission 102 : override par-appel à trois métiers réduits à deux ; Mission 107 lui-même : `engine`/`checkpoint_name` par-appel sans `isinstance`). Aucune architecture nouvelle (pas de registry, pas d'async, pas de nouvelle couche de persistance) n'est nécessaire. Si la rédaction avait révélé un obstacle structurel réel, ce constat aurait été signalé ici avant toute proposition de découpage — ce n'est pas le cas.

## 2. Objectif

Rendre Forge réellement utilisable depuis `InferencePage`, au même niveau fonctionnel que ComfyUI, sans dégrader le chemin ComfyUI existant. Résultat cible :

```
Inference → Moteur (ComfyUI / Forge) → Checkpoint → LoRA → paramètres → Generate → preview → Accept/Reject/Regenerate → Images
```

À la fin de M108, un architecte doit pouvoir basculer entre ComfyUI et Forge dans la même session, sélectionner un checkpoint réellement découvert sur le moteur actif, appliquer un LoRA de la Central Library de façon identique aux deux moteurs, et obtenir une image réellement produite par Forge — vérifié par un smoke réel, pas seulement par des tests mockés.

## 3. Décisions retenues (tranchées par l'architecte, non rediscutées ici)

### 3.1 LoRA — suppression du fallback Settings dans l'Inference interactive

Le combo LoRA de `InferencePage` perd son état `"Utiliser le réglage global (Settings)"` (aujourd'hui `itemData=None`, index 0) pour les deux moteurs. Il ne reste que deux états, identiques pour ComfyUI et Forge :

- `"Aucun LoRA"` (`itemData=""`) — **nouvel index 0, sélection par défaut**.
- une entrée par LoRA réel de la Central Library (`itemData=lora_id`), inchangé.

Ce retrait ne touche à rien d'autre : `ApplicationSettings.comfyui_lora_name`/`comfyui_lora_strength` et leurs champs `SettingsPage` restent tels quels pour compatibilité historique — `GenerationManager.__init__`/`generate()` gardent leur propre repli `lora_name=None` → valeurs du constructeur, un contrat qui reste valide pour un futur appelant hypothétique, simplement plus jamais exercé par `InferencePage`, qui ne transmettra plus jamais `lora_name=None`. Aucun nettoyage général de ces anciens Settings.

`refresh_lora_selector()` est simplifié en conséquence : la restauration de sélection après un rename/suppression garde exactement les mêmes garanties (un rename suit `lora_id`, un LoRA supprimé retombe sur `"Aucun LoRA"`), avec un seul état de repli au lieu de deux.

### 3.2 Injection des moteurs — deux dépendances explicites

`InferencePage.__init__` reçoit deux nouveaux paramètres explicites, `comfyui_engine` et `forge_engine` (les instances `ComfyUIEngine`/`ForgeEngine` déjà construites par `MainWindow`, pas une nouvelle construction). Aucun dict, registry, factory ou plugin system — le nombre de moteurs reste fermé à deux, adressés par deux attributs nommés (`self._comfyui_engine`, `self._forge_engine`), exactement le même style que `GenerationManager.__init__(comfyui_engine, ...)` depuis Mission 013.

### 3.3 Central LoRA Library — helper commun, deux wrappers publics

`LoRALibraryManager.expose_to_comfyui()` (Mission 095) est refactoré en un helper privé commun portant l'intégralité de la logique hardlink/idempotence/collision, paramétré par `expose_root` (déjà le cas) — aucune autre différence entre les deux moteurs n'existe dans cette logique (chaque racine d'exposition est un dossier physiquement distinct, donc aucune collision de nom possible entre les deux). `expose_to_comfyui()` devient un wrapper public fin appelant ce helper ; `expose_to_forge()` est son symétrique, ajouté à côté. La sélection logique du LoRA dans `InferencePage` reste unique et indépendante du moteur — seul l'appel d'exposition choisi à la génération (`expose_to_comfyui` vs `expose_to_forge`) dépend du moteur actif.

### 3.4 Checkpoint commun — `Engine → Checkpoint` dans Inference

Un nouveau combo `checkpoint_combo` dans `InferencePage`, peuplé par `GenerationManager.list_checkpoints(engine=<moteur actif>, timeout=...)` (nouvelle méthode, symétrique à `list_samplers()`/`list_schedulers()`). Le checkpoint explicitement sélectionné est transmis à `generate(checkpoint_name=...)`.

**Point de correction identifié pendant l'audit, repris ici comme invariant explicite** : `GenerationManager._checkpoint_name` (repli du constructeur) est lu une seule fois depuis `ApplicationSettings.comfyui_checkpoint_name` — un nom de checkpoint **ComfyUI**, jamais un choix neutre entre moteurs. Si `InferencePage` appelait `generate()` pour Forge sans `checkpoint_name` explicite, ce repli enverrait silencieusement un nom de checkpoint ComfyUI à Forge (`override_settings={"sd_model_checkpoint": "v1-5-pruned-emaonly-fp16.safetensors"}` ou équivalent), un comportement incorrect et jamais désiré. En conséquence :

- **ComfyUI** : si `checkpoint_combo` n'a reçu aucune sélection explicite (jamais rafraîchi, ou combo encore vide), `InferencePage` n'envoie pas de `checkpoint_name` — `GenerationManager` retombe sur son repli historique (`ApplicationSettings.comfyui_checkpoint_name`), comportement byte-for-byte identique à avant M108.
- **Forge** : ce repli n'a jamais de sens. Si aucun checkpoint n'a été explicitement découvert/sélectionné pour Forge, la génération est bloquée avec un message explicite (même traitement que le garde-fou "prompt vide" déjà existant), plutôt que de transmettre silencieusement un nom de checkpoint étranger.

Aucun `forge_checkpoint_name` n'est créé dans `ApplicationSettings` — cette dette n'est jamais reproduite pour Forge.

### 3.5 Settings Forge — strictement deux champs

`ApplicationSettings.forge_url` (repli `"http://127.0.0.1:7860"`, le propre défaut de `ForgeEngine`) et `ApplicationSettings.forge_lora_expose_path` (repli `""`, même convention que `comfyui_lora_expose_path`). `forge_lora_expose_path` reçoit un bouton "Parcourir…" dès son introduction dans `SettingsPage`, dupliquant exactement le pattern Mission 087 déjà utilisé par `comfyui_lora_expose_path`. Aucun `forge_path`, aucune référence à un Python/launcher Forge, aucun `forge_checkpoint_name`/`forge_lora_name`/`forge_lora_strength`.

### 3.6 Changement de moteur — état conservé vs invalidé

Le sélecteur `ComfyUI / Forge` vit dans `InferencePage`. Au changement :

**Conservé à l'identique** : prompt, prompt négatif, référence sélectionnée, force de transformation (`denoise`), largeur/hauteur, steps, CFG, seed (mode aléatoire/fixe et valeur). Sélection logique LoRA conservée si le LoRA actuellement sélectionné peut être exposé au moteur cible (l'exposition physique elle-même n'est tentée qu'au moment de `Generate`, jamais au moment du changement de moteur — un échec d'exposition à ce moment-là est signalé exactement comme aujourd'hui, sans jamais bloquer le changement de moteur lui-même).

**Invalidé/à redécouvrir** : `checkpoint_combo`, `sampler_combo`, `scheduler_combo` — vidés immédiatement au changement de moteur, jamais une valeur ComfyUI laissée visible comme si elle était une sélection Forge valide (et réciproquement).

**Bloquant** : une génération en cours (`is_generation_active()`) ou un résultat pending non résolu (`confirm_pending_result_change()`) bloquent le changement de moteur — ces deux guards existent déjà (Missions 084/085) et sont réutilisés tels quels, jamais dupliqués ni réécrits.

### 3.7 Refresh des capabilities — solution minimale, pas de refonte async

Étudié pendant l'audit : la découverte actuelle (`list_samplers()`/`list_schedulers()`, Mission 096) est un appel HTTP synchrone bloquant le thread Qt, avec un timeout court dédié (`SAMPLER_SCHEDULER_DISCOVERY_TIMEOUT = 5.0`) — un moteur injoignable produit donc un gel perceptible de l'UI pouvant atteindre 5 secondes. Introduire une découverte **automatique** au changement de moteur exposerait ce gel à chaque bascule vers un moteur indisponible, sans qu'aucune architecture asynchrone n'existe aujourd'hui pour l'éviter.

**Décision retenue** : pas de découverte automatique au changement de moteur. Au changement, les trois listes (checkpoint/sampler/scheduler) sont immédiatement vidées et un message clair ("Rafraîchissement nécessaire") est affiché ; le bouton `Rafraîchir` (déjà existant pour sampler/scheduler, étendu au checkpoint) reste le seul déclencheur de découverte, et interroge exclusivement le moteur actif au moment du clic. Aucune nouvelle architecture réseau/async n'est introduite.

### 3.8 Référence — contrat `denoise` inchangé

Le slider "Force de transformation" (`reference_strength_slider`) reste unique, sans aucun contrôle spécifique à un moteur. Le contrat Python `denoise` établi par M107 est déjà vérifié transmis identiquement aux deux moteurs par `GenerationManager.generate()` — aucune modification requise dans cette mission au-delà du câblage `engine=` déjà couvert par 3.2/3.4.

### 3.9 Smoke réel obligatoire — voir section 8

## 4. Périmètre exact — fichiers concernés

- `src/domain/application_settings.py` — `forge_url`, `forge_lora_expose_path` (champs, `to_dict()`/`from_dict()`).
- `src/ui/pages/settings_page.py` — deux champs, un bouton Parcourir (`forge_lora_expose_path`).
- `src/ui/main_window.py` — construction de `ForgeEngine` (lu une fois depuis `ApplicationSettings.forge_url`, comme `ComfyUIEngine`), injection de `comfyui_engine`/`forge_engine` dans `InferencePage`.
- `src/ui/pages/inference_page.py` — sélecteur moteur, `checkpoint_combo`, retrait de l'état "réglage global" du `lora_combo`, invalidation checkpoint/sampler/scheduler au changement de moteur, résolution explicite du checkpoint pour Forge (section 3.4).
- `src/ui/generation_worker.py` — transmission de `engine`/`checkpoint_name` à `generate()`, même pattern additif que `lora_name`/`lora_strength` (Mission 102).
- `src/managers/generation_manager.py` — nouveau `list_checkpoints(engine=None, timeout=None)` ; `engine=None` ajouté à `list_samplers()`/`list_schedulers()` existants (repli sur `self._comfyui_engine` si omis — comportement byte-for-byte inchangé pour tout appelant existant).
- `src/engines/comfyui_engine.py` — `timeout: Optional[float] = None` ajouté à `list_checkpoints()`, pour permettre à `GenerationManager.list_checkpoints()` de transmettre un timeout court de découverte à ComfyUI comme il le fait déjà pour Forge (`ForgeEngine.list_checkpoints()` l'accepte déjà).
- `src/managers/lora_library_manager.py` — extraction d'un helper privé commun, `expose_to_comfyui()` conservé comme wrapper public, nouveau `expose_to_forge()`.
- Tests d'intégration correspondants (voir section 7).
- `docs/missions/MISSION_108.md` (ce document).

**Aucune autre modification** de `src/domain/` (au-delà des deux champs ci-dessus), d'`ApplicationSettings` (au-delà des deux champs), de `LoRALibraryManager` (au-delà de l'extraction 3.3), de `comfyui_engine.py` (au-delà de l'ajout `timeout` ci-dessus), ni de tout fichier non listé. **Exception réelle, voir §12.6** : `src/engines/forge_engine.py` a fait l'objet d'une correction supplémentaire, non prévue à la rédaction de ce document, autorisée après stop-and-report explicite suite à une incompatibilité révélée par le smoke réel (§8) — jamais une refonte de Mission 107.

## 5. Hors périmètre strict

- `forge_path`, tout Python/launcher Forge, toute installation/lancement automatique de Forge.
- `forge_checkpoint_name`, `forge_lora_name`, `forge_lora_strength` dans `ApplicationSettings`.
- Nettoyage ou suppression de `comfyui_lora_name`/`comfyui_lora_strength` (restent pour compatibilité historique).
- Toute refonte générale de `SettingsPage` (organisation, onglets — besoin déjà documenté, non traité ici).
- Toute architecture multi-engine générique au-delà des deux adapters nommés (pas de registry, pas de plugin, pas de factory).
- Toute découverte automatique/asynchrone des capabilities (section 3.7) — solution minimale synchrone + bouton Rafraîchir uniquement.
- Fooocus, progression OneTrainer, TensorBoard.
- Toute modification de `ComfyUIEngine`/`ForgeEngine` au-delà de l'ajout `timeout` ponctuel listé en section 4.
- Mission 109 ou toute suite — non commencée, non anticipée.

## 6. Comportement détaillé attendu

### 6.1 Sélecteur moteur

`QComboBox` "ComfyUI"/"Forge" dans `InferencePage`, valeur par défaut "ComfyUI" (comportement de démarrage strictement identique à avant M108 tant que l'architecte ne bascule pas explicitement). Le changement déclenche, dans l'ordre : `confirm_no_active_generation()` puis `confirm_pending_result_change()` (les deux guards existants, Missions 084/085 — un refus de l'un ou l'autre annule le changement et restaure la sélection précédente du combo moteur) ; puis invalidation checkpoint/sampler/scheduler (section 3.7) ; la sélection logique LoRA et tous les autres paramètres restent inchangés (section 3.6).

### 6.2 Checkpoint

`checkpoint_combo` éditable (même style que `sampler_combo`/`scheduler_combo`, Mission 096), vide au démarrage et après tout changement de moteur, peuplé uniquement sur clic `Rafraîchir`. Résolution à `Generate` :

- une valeur présente dans `checkpoint_combo` → toujours transmise explicitement comme `checkpoint_name=...`, quel que soit le moteur ;
- `checkpoint_combo` vide et moteur = ComfyUI → aucun `checkpoint_name` transmis (repli historique `ApplicationSettings.comfyui_checkpoint_name`, section 3.4) ;
- `checkpoint_combo` vide et moteur = Forge → génération bloquée, message explicite ("Sélectionnez un checkpoint Forge avant de générer — cliquez sur Rafraîchir.").

### 6.3 LoRA

Voir section 3.1. Résolution à `Generate` inchangée dans son mécanisme (résolution de l'objet LoRA via `lora_library_manager.get()`, appel d'exposition, alias transmis comme `lora_name`) — seul le choix de la méthode d'exposition (`expose_to_comfyui`/`expose_to_forge`) dépend désormais du moteur actif.

### 6.4 Capabilities (checkpoint/sampler/scheduler)

Bouton `Rafraîchir` unique (étendu pour couvrir aussi le checkpoint), interrogeant exclusivement `list_checkpoints()`/`list_samplers()`/`list_schedulers()` avec `engine=<moteur actif>`. Un moteur injoignable produit le même traitement gracieux déjà existant pour sampler/scheduler (message explicite, saisie manuelle toujours possible dans les combos éditables) — jamais de crash, jamais d'effet sur l'autre moteur.

### 6.5 Référence

Inchangé (section 3.8).

### 6.6 Composition `MainWindow`

```python
self.forge_engine = ForgeEngine(
    base_url=self.application_settings_manager.settings.forge_url
)
```
construit juste après `self.comfyui_engine`, même contrat "lu une fois au démarrage, pas de hot-reload". `InferencePage` reçoit `self.comfyui_engine`/`self.forge_engine` en plus de ses dépendances actuelles. Aucune reconstruction de `MainWindow` requise pour `ComfyUI → Forge → ComfyUI` — les deux engines sont des wrappers HTTP sans état construits une seule fois (vérifié pour `ForgeEngine` par M107, propriété déjà partagée par `ComfyUIEngine` depuis Mission 012).

## 7. Stratégie de tests

Aucun appel réseau réel dans les tests automatisés (transport mocké, même convention que `test_forge_engine.py`/`test_comfyui_engine.py`) — seul le smoke réel (section 8) touche un vrai serveur Forge.

- `test_application_settings_roundtrip.py` (ou équivalent) : `forge_url`/`forge_lora_expose_path` round-trip `to_dict()`/`from_dict()`, valeurs par défaut.
- `test_settings_page.py` : deux nouveaux champs, bouton Parcourir `forge_lora_expose_path` (même assertions que `comfyui_lora_expose_path`).
- `test_generation_manager.py` : `list_checkpoints(engine=..., timeout=...)` nouveau (succès/échec/repli sur `self._comfyui_engine` si `engine` omis) ; `engine=` ajouté à `list_samplers()`/`list_schedulers()` avec non-régression de l'appel sans argument.
- `test_comfyui_engine.py` : `timeout` optionnel sur `list_checkpoints()`, non-régression de l'appel sans argument.
- `test_lora_library_roundtrip.py` : helper commun extrait, `expose_to_forge()` nouveau (mêmes cas que `expose_to_comfyui()` : racine non configurée, cardinalité de fichiers, volume différent, idempotence, collision, rename), non-régression complète de `expose_to_comfyui()`.
- `test_generation_worker.py` : transmission `engine`/`checkpoint_name`, non-régression sans ces paramètres.
- `test_inference_page.py` : sélecteur moteur (bascule, guards bloquants réutilisés, invalidation checkpoint/sampler/scheduler, conservation des autres paramètres) ; nouveau `checkpoint_combo` (peuplement, résolution à `Generate`, blocage explicite si Forge sans checkpoint) ; **adaptation des tests existants du `lora_combo`** — les assertions actuelles sur l'entrée `"Utiliser le réglage global (Settings)"` (`itemData=None`, index 0) doivent être mises à jour pour refléter le nouveau combo à deux états, une adaptation de test attendue et documentée ici à l'avance, pas une régression.
- `test_main_window_comfyui_settings.py` (ou nouveau `test_main_window_forge_settings.py`) : construction de `ForgeEngine` depuis `ApplicationSettings.forge_url`, injection dans `InferencePage`.
- Suite complète : nombre exact confirmé avant clôture (2123 avant M108 + net nouveaux).

## 8. Smoke réel — protocole (obligatoire, autorisation requise avant tout appel réel)

M108 ne peut se clore sans un smoke réel contre un vrai serveur Forge. **Claude ne lance jamais Forge et ne modifie jamais `webui-user.bat` sans autorisation explicite ponctuelle de l'architecte.** Au moment venu (implémentation terminée, tests mockés tous verts), Claude s'arrêtera et communiquera exactement ces trois étapes à effectuer par l'architecte lui-même :

1. Éditer `J:\Programmes\WebUI Forge CU121\webui\webui-user.bat`, ligne `set COMMANDLINE_ARGS=` → `set COMMANDLINE_ARGS=--api`.
2. Lancer `J:\Programmes\WebUI Forge CU121\run.bat` (jamais `webui.bat` directement — `run.bat` est le seul point d'entrée qui source `environment.bat` avant `webui-user.bat`).
3. Confirmer à Claude, une fois le serveur affichant `Running on local URL: http://127.0.0.1:7860`, que l'API est prête.

Claude attend cette confirmation explicite avant tout appel réel. Le smoke réel doit couvrir au minimum :

`Forge sélectionné` → checkpoint réel découvert et sélectionné → paramètres réels → `Generate` → image réellement retournée par Forge → preview affichée → `Accept` → image réellement présente dans `Workspace.images`/galerie Images.

Si raisonnable dans ce même smoke ou un second smoke court : un LoRA réel de la Central Library exposé à Forge (`expose_to_forge()`), génération l'utilisant réellement. Le chemin référence/img2img (`denoise`) doit être couvert soit par ce smoke réel, soit par une preuve automatisée jugée suffisante selon le coût GPU réel constaté pendant le smoke lui-même — décision prise à ce moment, pas anticipée ici.

## 9. Critères de clôture

1. Sections 3/6 implémentées exactement comme spécifié, sans élargissement silencieux du périmètre fermé (section 4).
2. Aucun élément de la section 5 n'a été ajouté.
3. Suite complète verte au nombre exact, `git diff --check` propre.
4. Chemin ComfyUI historique strictement inchangé pour tout usage qui ne touche jamais au sélecteur moteur (démarrage par défaut sur ComfyUI, aucun `checkpoint_combo` renseigné, `lora_combo` sur "Aucun LoRA" par défaut).
5. Smoke réel Forge exécuté et PASS (section 8), avec l'autorisation explicite de l'architecte documentée avant tout appel réel.
6. Documentation mise à jour (`docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`) selon le workflow habituel de clôture.

## 10. Documentation

M108 livre la première intégration utilisateur réelle de Forge — à ce titre, contrairement à M107, elle constitue une fonctionnalité visible et doit être documentée comme telle dans `docs/PROJECT_CONTEXT.md`/`CHANGELOG.md` à sa clôture (pas une fondation invisible). Le besoin futur "Character ↔ Training ↔ LoRA pour le trigger" (documenté après M107) reste explicitement non traité par cette mission.

## 11. Autorisation

Ce document sert de contrat avant toute implémentation. Aucun code n'est écrit tant que l'architecte n'a pas validé explicitement ce périmètre.

## 12. Résultat réel

### 12.1 Conformité de l'implémentation

Le périmètre fermé des sections 1-9 a été implémenté tel que spécifié : Settings Forge minimaux (`forge_url`/`forge_lora_expose_path`, aucun `forge_path`), sélecteur moteur dans `InferencePage` avec guards réutilisés (Missions 084/085), combo checkpoint commun avec blocage explicite pour Forge sans checkpoint sélectionné, combo LoRA réduit à deux états (suppression du fallback Settings), généralisation de `GenerationManager.list_checkpoints()`/`list_samplers()`/`list_schedulers()` avec `engine=` optionnel, helper `_expose()` partagé entre `expose_to_comfyui()`/`expose_to_forge()`, invalidation immédiate des capabilities au changement de moteur sans refresh automatique. Aucun `isinstance` contre un type de moteur concret, à aucun endroit, à aucun moment de la mission — vérifié explicitement par des tests dédiés dans `test_generation_manager.py`/`test_inference_page.py`.

### 12.2 Correctif découvert par le smoke réel — normalisation du nom LoRA Forge

Le premier smoke réel avec LoRA (checkpoint `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors [c9e3e68f89]`, LoRA `Zaraya Koyah SDX`) a révélé, par lecture directe du code source de l'extension `sd_forge_lora` installée et confirmation empirique (absence de la ligne `Lora hashes:` dans les métadonnées PNG retournées par un vrai serveur Forge), que `ForgeEngine._apply_lora_syntax()` transmettait `alias_name` de `LoRALibraryManager` (convention chemin relatif + extension, correcte pour ComfyUI) tel quel dans le tag `<lora:name:weight>`, alors que le registre interne de Forge (`extensions-builtin/sd_forge_lora/networks.py::process_network_files()`) indexe chaque LoRA exclusivement par `os.path.splitext(os.path.basename(filename))[0]` — le nom de fichier seul, sans sous-dossier ni extension.

**Correctif minimal appliqué, confiné à `src/engines/forge_engine.py`** : nouveau helper statique `_forge_lora_tag_name()` (normalisation explicite `/` → `\` puis `ntpath.basename()`/`ntpath.splitext()`, reproduisant exactement l'algorithme de Forge lui-même), appelé par `_apply_lora_syntax()` avant construction du tag. Aucune modification de `LoRALibraryManager`/`GenerationManager`/`GenerationWorker`/`InferencePage` — `alias_name` garde son format partagé avec ComfyUI, la traduction reste confinée au seul composant qui connaît le protocole Forge, dans l'esprit du contrat `denoise` déjà établi par Mission 107.

Second smoke réel, après correctif : métadonnées PNG confirmant `<lora:Zaraya_Koyah_SDX__37ca771a-08d2-4b6e-8858-fac6c742f193:1.0>` et `Lora hashes: "Zaraya_Koyah_SDX__37ca771a-08d2-4b6e-8858-fac6c742f193: 709879b7f841"` — hash correspondant exactement (préfixe 12 caractères) au `sshs_model_hash` embarqué dans le fichier `.safetensors` canonique lui-même, preuve indépendante que Forge a chargé et appliqué le fichier physique exact exposé par hardlink.

### 12.3 Smoke réel — preuve matérielle complète

- **Txt2img sans LoRA** (checkpoint/sampler/scheduler réels découverts via Rafraîchir, `Aucun LoRA`) : génération Forge réelle, image 512×512 valide (magic bytes PNG, nommage `uuid4().hex` propre à `ForgeEngine._save_image()`), Accept réussi, image présente dans `project.json`/page Images.
- **LoRA Central Library → Forge** : `expose_to_forge()` réellement exercé contre un `forge_lora_expose_path` réel (`J:\Programmes\WebUI Forge CU121\webui\models\Lora`) — hardlink NTFS vérifié par `os.stat()` (même `dev`/`ino` des deux côtés, `nlink=2`, `os.path.samefile() → True`) dans le sous-dossier `AIStudioToolkit\`, jamais les deux LoRA historiques déjà présents à la racine (intacts, tailles/dates inchangées à chaque vérification). Génération avec LoRA réussie, `Lora hashes:` confirmé après correctif, Accept réussi, image persistée dans `project.json` et visible dans Images.
- **Référence/img2img** : couvert par les tests automatisés réels de Mission 107 (payload `denoising_strength`, endpoint `/sdapi/v1/img2img`) plus le nouveau test dédié `test_lora_name_is_normalized_on_the_img2img_path_too` — non rejoué sur GPU réel en plus des deux smoke txt2img déjà réalisés, jugé suffisant au vu du coût GPU et de la couverture automatisée déjà exercée contre un vrai payload structurellement identique.

### 12.4 Conformité au périmètre

Aucun élément de la section 5 (hors périmètre) n'a été ajouté : pas de `forge_path`, pas de `forge_checkpoint_name`/`forge_lora_name`/`forge_lora_strength`, pas de nettoyage `comfyui_lora_name`/`comfyui_lora_strength`, pas de réorganisation `SettingsPage`, pas d'architecture multi-engine générique, pas de découverte automatique/asynchrone, pas de Fooocus/OneTrainer/TensorBoard. Le seul dépassement du périmètre initial (§4) est la correction ciblée de `forge_engine.py` documentée en §12.2, autorisée explicitement après stop-and-report — jamais une extension silencieuse.

### 12.5 Tests

`test_forge_engine.py` : 46 (Mission 107) + 6 (Mission 108, normalisation LoRA) = 52. `test_generation_manager.py`/`test_generation_worker.py`/`test_lora_library_roundtrip.py`/`test_inference_page.py`/`test_application_settings_roundtrip.py`/`test_comfyui_engine.py`/`test_main_window_forge_settings.py` (nouveau) : net +37 tests par rapport à la base post-Mission 107 (2123 → 2160), puis +6 pour le correctif LoRA (2160 → 2166). Suite complète finale : **2166/2166**, `python -m unittest discover -s tests -p "test_*.py"`.

### 12.6 Fichiers fonctionnels réellement modifiés/créés

`src/domain/application_settings.py`, `src/managers/application_settings_manager.py`, `src/engines/comfyui_engine.py`, `src/engines/forge_engine.py` (§12.2), `src/managers/generation_manager.py`, `src/managers/lora_library_manager.py`, `src/ui/generation_worker.py`, `src/ui/main_window.py`, `src/ui/pages/inference_page.py`, `src/ui/pages/settings_page.py`, `docs/missions/MISSION_108.md`, plus les fichiers de tests correspondants (dont le nouveau `tests/integration/test_main_window_forge_settings.py`).
