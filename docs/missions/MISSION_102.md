# Mission 102 — Sélection dynamique d'un LoRA depuis Inference

> **MISSION CLÔTURÉE — SÉLECTION DYNAMIQUE DE LORA VALIDÉE DE BOUT EN BOUT, SMOKE COMFYUI RÉEL 3/3, GITHUB RELEASE PUBLIÉE.** Ce document a d'abord servi de contrat avant implémentation (sections 1-10, inchangées). Voir section 11 pour le résultat réel complet, incluant le smoke ComfyUI réel exécuté contre l'installation de l'architecte, et section 12 pour la clôture Git.

## 1. Contexte

L'audit post-Mission 101 (`docs/PROJECT_CONTEXT.md`) a identifié un unique blocage réel sur la chaîne `Images → Dataset/captions → OneTrainer → LoRA → Inference → Images` : `GenerationManager` lit `comfyui_lora_name`/`comfyui_lora_strength` une seule fois, à la construction de l'application (`src/ui/main_window.py:173-181`), un choix documenté et assumé ("no hot reload", Missions 018/059). Concrètement, changer de LoRA entre deux personnages impose aujourd'hui : Bibliothèque → exposer le LoRA à ComfyUI → Settings → sélectionner le nom exposé dans un unique combo global → sauvegarder → **redémarrer AI Studio Toolkit** → générer. Aucun sélecteur de LoRA n'existe sur `InferencePage`.

## 2. Objectif

Permettre à l'utilisateur de choisir, depuis `InferencePage` elle-même, un LoRA de la Bibliothèque LoRA centrale à appliquer à une génération réelle via ComfyUI — sans redémarrage de l'application, sans reconfigurer Settings, et sans construire une abstraction multi-LoRA prématurée.

## 3. Mini-audit — décisions retenues

### 3.1 Source de vérité du LoRA sélectionné

**Décision : état transitoire de `InferencePage`, aucun nouvel objet Domain, aucune persistance.**

Il n'existe aujourd'hui aucun objet Domain "Inference" ou "GenerationRequest" persisté (`src/domain/` ne contient aucun fichier de ce nom) — en créer un maintenant serait du scaffolding anticipé sans consommateur actuel, explicitement proscrit par les règles permanentes du projet. `InferencePage` gère déjà plusieurs choix de génération (image de référence, seed, dimensions) comme un état transitoire du widget, jamais persisté ni remonté au Domain (`src/ui/pages/inference_page.py`). La sélection de LoRA suit exactement le même pattern : un attribut transitoire de `InferencePage` représentant l'un des trois états de la section 3.2 (par défaut, l'état A — "aucun override", voir ci-dessous), jamais écrit dans `project.json`, jamais un champ de `Training`/`Character`/`Workspace`.

**Correction importante par rapport à une première rédaction de ce contrat** : le sélecteur ne peut pas avoir pour unique valeur par défaut "Aucun LoRA" (état B), car cela romprait la compatibilité historique exigée par la section 3.2/étape 9 — un utilisateur qui ne touche jamais au sélecteur doit continuer à bénéficier du LoRA global de Settings s'il en a configuré un. Le sélecteur expose donc **trois options toujours visibles**, jamais seulement deux avec un suivi implicite de "l'utilisateur a-t-il touché ce contrôle" :
1. **"Utiliser le réglage global (Settings)"** — option sélectionnée par défaut, correspond à l'état A (`lora_name=None`, fallback Settings).
2. **"Aucun LoRA"** — état B (`lora_name=""`, jamais de repli sur Settings).
3. **une entrée par `LoRA` réel de la Bibliothèque** — état C.

Cette représentation à trois options explicites est plus simple et plus sûre qu'un suivi d'état "touché/non touché" du widget, et rend les trois comportements immédiatement visibles et sélectionnables par l'utilisateur.

Ce choix prépare raisonnablement un futur besoin multi-LoRA : parce que c'est un état de widget ordinaire (pas un schéma persisté à faire migrer), le faire évoluer vers une liste plus tard resterait un changement local à `InferencePage`, sans impact Domain/Storage.

**Identité conservée, pas seulement un nom affiché** : `InferencePage` conserve, comme état transitoire, le `lora_id` réel de l'entrée choisie (jamais seulement une chaîne `name` mise en cache) — voir section 3.3 pour la justification et la résolution au moment de la génération.

### 3.2 Interaction avec `GenerationManager` — trois états distincts, jamais confondus

**Décision : deux nouveaux paramètres optionnels par appel sur `generate()`, jamais une refonte du Manager. La distinction des trois comportements repose uniquement sur les valeurs déjà signifiantes à la couche engine — aucun nouveau type sentinel.**

`GenerationManager.generate()` (`src/managers/generation_manager.py:98-249`) accepte déjà, par appel, `width/height/steps/cfg/sampler_name/scheduler/seed/negative_prompt/reference_strength` — chacun optionnel, retombant sur un défaut du Manager ou de l'engine quand omis (Mission 096). Seuls `lora_name`/`lora_strength` restent fixés une fois pour toutes au constructeur (lignes 82-91). `ComfyUIEngine.generate_image()` (`src/engines/comfyui_engine.py:410-511`), lui, accepte déjà `lora_name`/`lora_strength` **par appel**, et son propre docstring établit déjà que `lora_name=""` signifie explicitement "aucun LoRA" (ligne 470 : *"lora_name="" (default) reproduces this method's pre-Mission-059 output byte-for-byte"*) — la couche engine n'a donc aucune modification à subir, et porte déjà la moitié de la sémantique dont cette mission a besoin.

`generate()` gagne deux paramètres optionnels `lora_name: Optional[str] = None`, `lora_strength: Optional[float] = None`, avec **trois états distincts et testés séparément** :

| État | Valeur transmise par l'appelant | Comportement de `GenerationManager` |
|---|---|---|
| **A. Aucun override (compatibilité historique)** | `lora_name=None` (paramètre omis) | Retombe sur `self._lora_name`/`self._lora_strength`, donc sur `comfyui_lora_name`/`comfyui_lora_strength` de Settings, exactement comme aujourd'hui — byte-for-byte. |
| **B. "Aucun LoRA" choisi explicitement dans Inference** | `lora_name=""` (chaîne vide, explicite) | Transmis tel quel à `ComfyUIEngine.generate_image()` — qui traite déjà `""` comme "aucun LoRA" (voir ci-dessus). Le LoRA global de Settings n'est **jamais** réintroduit silencieusement : `""` n'est pas `None`, donc le fallback de l'état A ne se déclenche pas. |
| **C. LoRA choisi explicitement dans Inference** | `lora_name="<alias exposé>"` (chaîne non vide) | Transmis tel quel, avec `lora_strength` fourni par l'appelant (contrôle Inference, section 3.5). |

Concrètement, `GenerationManager.generate()` distingue uniquement `is None` (état A → fallback constructeur) de "fourni, y compris chaîne vide" (états B/C → valeur transmise telle quelle) — une seule condition `if lora_name is not None:`, sans branche spéciale pour la chaîne vide, puisque c'est déjà la sémantique portée par l'engine. `GenerationWorker` (`src/ui/generation_worker.py`) suit le même ajout que ses paramètres `width`/`height`/etc. déjà présents (capture au constructeur, transmission conditionnelle via `kwargs` uniquement si non `None` — une chaîne vide `""` est bien "non `None`" et est donc transmise normalement, exactement comme le ferait déjà ce même pattern `is not None` pour n'importe quel autre paramètre).

Aucune autre méthode de `GenerationManager` n'est touchée.

### 3.3 Bibliothèque LoRA centrale — pas de nouveau stockage

**Décision : réutilisation stricte de `LoRALibraryManager.list_loras()` et de l'entité `LoRA` existante.**

`LoRA` (`src/domain/lora.py`) expose déjà `lora_id` (identifiant stable, jamais affiché) et `name` (libellé lisible) — l'identification UI utilise `name` comme libellé principal ; en cas de doublon de nom, `lora_id` (ou un suffixe court dérivé) doit permettre de désambiguïser sans ambiguïté dans le picker, sans introduire de nouveau champ. `LoRALibraryManager` (`src/managers/lora_library_manager.py`) est déjà un registre applicatif indépendant de tout Workspace/Character (ligne 95-105), déjà utilisé par `lora_page.py`. `InferencePage` reçoit `lora_library_manager` comme nouvelle dépendance constructeur (elle ne le reçoit pas aujourd'hui — vérifié dans `src/ui/main_window.py:411-417`), au même titre que ses dépendances actuelles (`workspace_manager`, `character_manager`, etc.).

Le sélecteur propose les trois options de la section 3.1 : "Utiliser le réglage global (Settings)" (par défaut) et "Aucun LoRA" en premier (données associées `None`/état A et `""`/état B respectivement — voir résolution exacte en 3.2), suivies d'une entrée par `LoRA` réel retourné par `list_loras()`. Chaque entrée réelle du `QComboBox` porte le `lora_id` en donnée associée (`Qt.UserRole`), `LoRA.name` servant uniquement de libellé affiché — jamais l'inverse. Au moment de générer, l'identité fonctionnelle suit toujours le chemin :

```
lora_id sélectionné → relecture de l'entité LoRA réelle via lora_library_manager.list_loras() → expose_to_comfyui() → alias_name (nom/chemin réellement attendu par ComfyUIEngine)
```

La `LoRA` est **toujours relue par id** au moment de générer (jamais un objet `LoRA` mis en cache depuis la sélection) — ceci couvre nativement un renommage survenu entre la sélection et la génération, sans code de synchronisation supplémentaire.

Rafraîchi via les événements déjà existants et déjà publiés par ce Manager : `LORA_LIBRARY_IMPORTED`, `LORA_LIBRARY_DELETED`, `LORA_LIBRARY_UPDATED` (`lora_library_manager.py:18-20`) — aucun nouvel événement à créer. **Comportement si le LoRA sélectionné disparaît** (suppression, ou tout événement après lequel son `lora_id` n'est plus dans `list_loras()`) : le sélecteur revient explicitement et proprement à "Aucun LoRA" — jamais de référence morte conservée, jamais de génération silencieusement lancée avec un `lora_id` qui n'existe plus. Un renommage (`LORA_LIBRARY_UPDATED` sur le même `lora_id`, toujours présent) met seulement à jour le libellé affiché ; la sélection elle-même (l'id) est conservée.

### 3.4 Exposition à ComfyUI

**Décision : Option B — exposition à la demande via la primitive existante, jamais une nouvelle mécanique physique.**

`ComfyUIEngine.list_loras()` (`comfyui_engine.py:304-346`) interroge ComfyUI lui-même (`object_info/LoraLoader`) : seuls les fichiers physiquement visibles dans le dossier LoRA de ComfyUI peuvent être utilisés comme `lora_name`. Un LoRA de la Bibliothèque non exposé n'est donc **pas directement utilisable** par ComfyUI (Option A — n'autoriser que les LoRA déjà exposés — obligerait l'utilisateur à un aller-retour manuel préalable par la page Bibliothèque, ce qui reproduirait exactement la friction actuelle).

`LoRALibraryManager.expose_to_comfyui(lora, expose_root)` (`lora_library_manager.py:533`) existe déjà, est **idempotent** par construction (un appel répété sur le même LoRA déjà exposé à l'identique est un no-op vérifié par `os.path.samefile`, sans aucune écriture disque), gère déjà la ré-exposition après renommage, et retourne `LoRAComfyUIExposureResult.alias_name` — exactement le nom de fichier à transmettre comme `lora_name` à `generate()`. `InferencePage` utilise `ApplicationSettings.comfyui_lora_expose_path` déjà configuré (`settings_page.py:165-188`, déjà lu par `main_window.py`) comme `expose_root` — `InferencePage` reçoit donc aussi une lecture de ce chemin (via `application_settings_manager`, à ajouter à ses dépendances comme `lora_library_manager` ci-dessus).

**Moment de l'appel — au déclenchement de la génération, jamais seulement à la sélection.** `expose_to_comfyui()` est appelé juste avant de construire le `GenerationWorker`, à chaque génération où un LoRA réel (état C) est sélectionné — jamais uniquement au moment du choix dans le `QComboBox`. Grâce à l'idempotence déjà garantie par la primitive, répéter l'appel à chaque génération est sans coût (no-op si rien n'a changé) et donne la garantie demandée : **le `lora_name` envoyé à ComfyUI correspond toujours à une exposition qui vient de réussir pour cette génération précise**, jamais à un état exposé potentiellement périmé (config modifiée entretemps, fichier déplacé, etc.).

**Comportement d'échec explicite** : `expose_to_comfyui()` lève déjà `LoRALibraryError` avec un message précis et distinct pour chaque cause réelle (chemin d'exposition non configuré, fichier absent, volumes différents, alias en conflit, etc. — voir docstring complète de la méthode). Cette exception est interceptée par `InferencePage` **avant** toute construction de `GenerationWorker` : le message est affiché à l'utilisateur **tel quel** (`QMessageBox`, jamais reformulé ni générique), et **aucune génération n'est lancée** — ni avec le LoRA demandé, ni en repli silencieux vers "Aucun LoRA". Pour l'état B ("Aucun LoRA" choisi explicitement), `expose_to_comfyui()` n'est jamais appelé — rien à exposer.

### 3.5 Strength

**Décision : incluse — un seul contrôle simple à côté du sélecteur, jamais un panneau avancé.**

`ApplicationSettings.comfyui_lora_strength: float = 1.0` existe déjà comme réglage global ; l'appliquer sans contrôle de force reviendrait à toujours forcer 1.0, ce qui n'est pas raisonnablement utilisable pour un LoRA de personnage réel. L'ajout est trivial et cohérent avec le sélecteur : un unique contrôle numérique (ex. `QDoubleSpinBox`, mêmes bornes que le champ Settings existant), actif seulement quand un LoRA réel est sélectionné (état C — désactivé/non pertinent pour "Aucun LoRA"), initialisé à la même valeur par défaut que `ApplicationSettings.comfyui_lora_strength` (`1.0`) pour rester cohérent avec le comportement déjà connu, transmis comme nouveau paramètre `lora_strength` de `generate()` (section 3.2). Aucun autre réglage LoRA (clip strength séparé, plusieurs LoRA, etc.) n'est ajouté.

### 3.6 Compatibilité avec Settings — aucune suppression

**Décision : `comfyui_lora_name`/`comfyui_lora_strength` restent dans `ApplicationSettings`/`SettingsPage` inchangés, comme valeurs par défaut/fallback.**

Ces deux champs continuent d'alimenter `GenerationManager` exactement comme aujourd'hui, au démarrage de l'application (`main_window.py:173-181`, inchangé). Ils deviennent le **fallback** utilisé chaque fois que le sélecteur d'Inference ne fournit rien (`lora_name`/`lora_strength` = `None` côté `generate()`, section 3.2) — c'est-à-dire tant que l'utilisateur n'a jamais touché le nouveau sélecteur, ou explicitement choisi "Aucun". Le comportement actuel (byte-for-byte, sans toucher au sélecteur) reste garanti. Aucune dépréciation, aucune migration : ces champs restent des réglages de démarrage légitimes, pas une redondance à supprimer.

## 4. Périmètre exact — fichiers concernés

- `src/managers/generation_manager.py` — deux paramètres optionnels ajoutés à `generate()`.
- `src/ui/generation_worker.py` — deux paramètres optionnels ajoutés, transmis en `kwargs` seulement si non `None` (même pattern que `width`/`height`/etc. déjà présents).
- `src/ui/pages/inference_page.py` — nouvelles dépendances constructeur (`lora_library_manager`, accès à `comfyui_lora_expose_path`), nouveau sélecteur + contrôle de force, appel à `expose_to_comfyui()` à la demande, gestion d'erreur explicite, abonnement aux 3 événements `LORA_LIBRARY_*` existants.
- `src/ui/main_window.py` — passage de la nouvelle dépendance à `InferencePage(...)`.
- Fichiers de tests listés en section 7.

**Aucune modification** de `src/domain/`, de `src/managers/training_manager.py`, de `src/managers/lora_library_manager.py` (réutilisé tel quel), de `src/engines/comfyui_engine.py` (déjà suffisant), ni de `src/ui/pages/settings_page.py`.

## 5. Hors périmètre strict — ne pas ajouter à cette mission

- Import automatique du LoRA produit par un `TrainingJob` réussi vers la Bibliothèque (`imported_lora_id` reste non peuplé — dette déjà documentée séparément).
- Historique des `TrainingJob` dans `TrainingPage`.
- Réorganisation de `SettingsPage` (voir section dédiée du rapport d'audit — direction retenue mais non planifiée ici).
- Fooocus, Stable Diffusion WebUI Forge, abstraction multi-engine.
- Sélection/pondération de **plusieurs** LoRA simultanés (stacking).
- Réglages OneTrainer avancés, diagnostic GPU/PyTorch.
- Toute modification de `GenerationManager` au-delà des deux paramètres décrits en 3.2 (pas de refonte générale).
- Amélioration de la qualité des LoRA produits.

## 6. Étapes techniques attendues

1. `GenerationManager.generate()` accepte `lora_name`/`lora_strength` optionnels par appel (section 3.2), avec les trois états A/B/C distincts (`None` → fallback Settings ; `""` → aucun LoRA explicite ; valeur → LoRA choisi).
2. `GenerationWorker` transmet ces deux paramètres selon le même pattern `is not None` que les paramètres Mission 096 existants.
3. `InferencePage` reçoit `lora_library_manager` (et l'accès à `comfyui_lora_expose_path`) en dépendance.
4. Un sélecteur réel (ex. `QComboBox`) liste "Aucun LoRA" (sélectionné par défaut) + les entrées réelles de `lora_library_manager.list_loras()`, portant le `lora_id` réel en donnée associée. Rafraîchi sur `LORA_LIBRARY_IMPORTED`/`_DELETED`/`_UPDATED` ; retour propre à "Aucun LoRA" si l'entrée sélectionnée disparaît.
5. Un contrôle de force (actif seulement en état C) accompagne le sélecteur, initialisé à `1.0`.
6. Juste avant chaque génération où un LoRA réel est sélectionné (état C), `InferencePage` relit l'entité `LoRA` par `lora_id`, appelle `expose_to_comfyui()` et récupère `alias_name` (section 3.4) — jamais seulement au moment de la sélection.
7. Toute `LoRALibraryError` levée par l'exposition est affichée telle quelle à l'utilisateur ; **aucune génération n'est lancée** dans ce cas (ni avec le LoRA demandé, ni en repli vers "Aucun LoRA").
8. Une génération lancée avec "Aucun LoRA" choisi explicitement (état B, `lora_name=""`) n'applique jamais le LoRA global de Settings, même s'il est configuré.
9. Une génération lancée sans jamais toucher au sélecteur (état A) reproduit le comportement actuel (fallback Settings) sans aucune régression.
10. Changer de sélection entre deux générations successives (y compris vers "Aucun LoRA") ne nécessite aucun redémarrage de l'application.

## 7. Tests attendus

- `tests/integration/test_generation_manager.py` :
  1. aucun override fourni (`lora_name`/`lora_strength` omis) → `ComfyUIEngine.generate_image()` reçoit les valeurs de construction (état A, non-régression Mission 059) ;
  2. `lora_name=""` fourni explicitement → transmis tel quel, **jamais** remplacé par la valeur de construction même si celle-ci est non vide (état B — le fallback de l'état A ne doit pas se déclencher) ;
  3. `lora_name="<valeur>"` non vide fourni → transmis tel quel avec le `lora_strength` fourni (état C) ;
  4. `lora_strength` transmis correctement par appel, indépendamment de `lora_name`.
- `tests/integration/test_generation_worker.py` : les deux nouveaux paramètres optionnels sont transmis selon le même pattern `is not None` que les paramètres existants (`None` → absent des `kwargs` ; `""` → présent dans les `kwargs`, distinct de `None`).
- `tests/integration/test_inference_page.py` :
  1. le sélecteur liste "Aucun LoRA" + les entrées réelles de la Bibliothèque ;
  2. sélection d'un LoRA A → génération réelle transmettant l'`alias_name` exposé de A ;
  3. changement vers un LoRA B sans redémarrage → génération suivante transmettant B, jamais A ;
  4. changement vers "Aucun LoRA" → génération suivante avec `lora_name=""`, jamais de réintroduction du LoRA global de Settings ;
  5. la `strength` choisie est bien celle transmise à la génération ;
  6. un échec de `expose_to_comfyui()` (mocké) empêche proprement la génération (aucun `GenerationWorker` construit, aucun appel à `generate()`) et affiche le message d'erreur réel ;
  7. suppression/renommage/import dans la Bibliothèque (simulant `LORA_LIBRARY_DELETED`/`_UPDATED`/`_IMPORTED`) rafraîchit le sélecteur sans référence invalide, avec retour à "Aucun LoRA" si l'entrée sélectionnée a disparu ;
  8. une génération sans jamais toucher au sélecteur reste fonctionnelle et identique au comportement actuel.
- Suite complète existante (1972+ tests) : aucune régression, nombre exact reconfirmé après implémentation.

## 8. Smoke réel — politique

Si ComfyUI est déjà joignable à l'URL configurée (`ApplicationSettings.comfyui_url`) au moment de la vérification, Claude exécute lui-même un smoke réel minimal (une génération avec "Aucun LoRA", puis une génération avec un vrai LoRA de la Bibliothèque réellement exposé, puis un changement de sélection suivi d'une seconde génération réelle — sans redémarrage), conformément à la pratique déjà établie sur les missions ComfyUI réelles de ce projet. Si ComfyUI n'est pas démarré, Claude ne le démarre pas lui-même (action externe) et demande à l'architecte de le lancer avant de procéder au smoke — jamais de contournement, jamais de simulation présentée comme un test réel.

## 9. Critères de clôture

1. Les 10 étapes de la section 6 sont observées réellement (smoke réel si ComfyUI disponible, sinon rapporté explicitement comme non exécuté et pourquoi).
2. Tous les tests de la section 7 passent, suite complète confirmée au nombre exact.
3. `comfyui_lora_name`/`comfyui_lora_strength` restent inchangés dans Settings et continuent de fonctionner comme fallback (vérifié par un test explicite, pas seulement par lecture de code).
4. Aucun élément de la section 5 n'a été ajouté.
5. Aucune modification de `src/domain/` ni de `LoRALibraryManager`/`ComfyUIEngine`.

## 10. Autorisation

Ce document a servi de contrat avant toute implémentation. Le code n'a été écrit qu'après validation explicite de ce périmètre par l'architecte — voir section 11 pour le résultat réel complet.

## 11. Résultat réel

### 11.1 Implémentation — conforme au périmètre exact

Les 4 fichiers `src/` et 3 fichiers `tests/` de la section 4 ont été modifiés, strictement dans ce périmètre — confirmé par `git diff --stat` au moment de la clôture : `src/managers/generation_manager.py`, `src/ui/generation_worker.py`, `src/ui/pages/inference_page.py`, `src/ui/main_window.py`, `tests/integration/test_generation_manager.py`, `tests/integration/test_generation_worker.py`, `tests/integration/test_inference_page.py`. Aucune modification de `src/domain/`, `src/managers/lora_library_manager.py`, `src/engines/comfyui_engine.py`, ni `src/ui/pages/settings_page.py` — conforme aux critères 4/5 de la section 9.

Les trois états A/B/C de la section 3.2 sont implémentés exactement comme spécifiés : `GenerationManager.generate()` distingue `lora_name is None` (état A, fallback construction) de toute valeur fournie, y compris `""` (états B/C, jamais de repli silencieux vers le LoRA global). Le sélecteur à trois options de la section 3.1 ("Utiliser le réglage global (Settings)", "Aucun LoRA", puis les entrées réelles de la Bibliothèque) est implémenté dans `InferencePage`, avec relecture par `lora_id` à chaque génération (jamais un objet `LoRA` mis en cache) et retour propre à "Aucun LoRA" si l'entrée sélectionnée disparaît.

### 11.2 Tests

Suite complète : **1991/1991 tests verts** (1972 avant Mission 102 + 19 tests ajoutés : 4 dans `GenerationManagerLoraOverrideTest`, 4 dans `GenerationWorkerLoraTest`, 11 dans `InferencePageLoraSelectorTest`), aucune régression. Les 8 points de tests exigés en section 7 sont couverts.

### 11.3 Smoke réel ComfyUI — 3/3, exécuté deux fois (v1 diagnostiqué, v2 réussi)

**Première tentative (script de vérification, jamais le code de production) : blocage identifié et corrigé.** Le script de smoke plaçait sa Bibliothèque LoRA temporaire sur le volume `C:` alors que `comfyui_lora_expose_path` réel de l'architecte est sur `J:` — `LoRALibraryManager.expose_to_comfyui()` a **correctement** refusé le hardlink inter-volumes (comportement documenté et déjà testé), levant `LoRALibraryError` ; `InferencePage` a correctement affiché l'erreur via une vraie `QMessageBox.critical()` modale — mais celle-ci, dans un script non interactif sans utilisateur pour cliquer "OK", est restée ouverte indéfiniment (~50 minutes), simulant un blocage qui n'en était pas un côté Mission 102. Diagnostic confirmé par preuve directe (`os.stat().st_dev` différent entre les deux chemins, `/queue`/`/history` de ComfyUI vides pour cette étape). Aucune modification de code de production nécessaire — uniquement correction du script de test (Bibliothèque temporaire déplacée sur `J:`, garde anti-dialogue `tests/integration/_qt_dialog_safety_net.py` ajoutée pour la robustesse du script).

**Seconde tentative — succès complet, contre l'installation réelle de l'architecte (`J:\Programmes\ComfyUI`, lancée via ComfyUI Desktop, API réelle sur `http://127.0.0.1:8000`)** :

| Étape | `lora_name` réellement transmis à `ComfyUIEngine.generate_image()` | `lora_strength` | Résultat réel |
|---|---|---|---|
| 1. Sans LoRA | `""` | `1.0` (non pertinent) | ✅ image réelle produite (363 750 octets) |
| 2. Avec un LoRA réel de la Bibliothèque, exposition réelle | `AIStudioToolkit\Mission102SmokeLoRA__<id>.safetensors` (alias réellement créé par `expose_to_comfyui()`, `cleanup_failed=False`) | `0.65` | ✅ image réelle produite (310 226 octets) |
| 3. Retour à « Aucun LoRA », **sans redémarrage** d'AI Studio Toolkit | `""` — jamais le LoRA global de Settings (`Zarayah-lora-Replicate (02).safetensors`, resté inutilisé tout le smoke) | `1.0` (non pertinent) | ✅ image réelle produite (311 976 octets) |

Aucun dialogue inattendu (garde anti-dialogue : liste vide en fin de run). Le LoRA de test exposé (hardlink réel dans `J:\Programmes\ComfyUI\models\loras\AIStudioToolkit\`) et la Bibliothèque/le Workspace temporaires du smoke ont été supprimés après vérification — l'installation ComfyUI réelle de l'architecte a été confirmée restaurée à son état exact d'origine (mêmes 7 fichiers qu'avant le smoke).

### 11.4 Découverte annexe, sans lien avec le code de Mission 102

Le diagnostic du premier blocage a mis en évidence que le backend ComfyUI (process Python `main.py`, distinct de la coquille Electron ComfyUI Desktop) n'avait pas été relancé depuis plusieurs jours malgré l'application ouverte — preuve par logs historiques (`Comfy Desktop\logs\app.log*`, `installations.json.lastLaunchedAt`). Sans rapport avec Mission 102 ; mentionné ici uniquement pour mémoire du contexte de ce smoke.

### 11.5 Besoins futurs identifiés pendant cette mission — non intégrés à son périmètre

Quatre besoins ont été observés pendant l'audit/le smoke de Mission 102, explicitement **non traités ici** et à considérer séparément par un futur audit (voir aussi `docs/PROJECT_CONTEXT.md`) :
- lancement automatique du backend ComfyUI par AI Studio Toolkit (aujourd'hui, l'architecte doit le démarrer lui-même côté ComfyUI Desktop) ;
- sélection graphique (parcourir un dossier) pour `ApplicationSettings.comfyui_path`/`comfyui_lora_expose_path`, aujourd'hui de simples champs texte ;
- réorganisation de `SettingsPage` (dette déjà caractérisée par l'audit post-Mission 101, direction à navigation hiérarchisée envisagée mais non implémentée) ;
- amélioration UX de l'import automatique des sidecars `.txt` de caption (`DatasetManager.add_images(detect_caption_sidecars=True)`), observé comme fonctionnel mais perfectible pendant cette mission.

## 12. Clôture Git

- Commit fonctionnel : `bbe6991df6c0f6d5cc29992ad272168c4b63f760` — *Add dynamic LoRA selection to Inference from the Central LoRA Library* (`src/managers/generation_manager.py`, `src/ui/generation_worker.py`, `src/ui/pages/inference_page.py`, `src/ui/main_window.py`, `tests/integration/test_generation_manager.py`, `tests/integration/test_generation_worker.py`, `tests/integration/test_inference_page.py`, `docs/missions/MISSION_102.md`, `docs/PROJECT_CONTEXT.md`).
- Tag annoté : `v0.2-mission102`, sur ce même commit exact (vérifié via `git rev-list -n 1 v0.2-mission102`).
- `main` et le tag poussés vers `origin` sans divergence ni commit étranger intercalé (`HEAD == origin/main == bbe6991df6c0f6d5cc29992ad272168c4b63f760`, `git rev-list --left-right --count origin/main...main` → `0 0`).
- GitHub Release `v0.2-mission102` **publiée** — confirmée par l'architecte du projet.
- Validation finale à la clôture : suite complète **1991/1991**, exit 0 ; smoke réel ComfyUI **3/3** contre l'installation réelle de l'architecte (voir section 11.3).
- Régularisation documentaire post-Release effectuée dans un commit distinct (`CHANGELOG.md`, `docs/PROJECT_CONTEXT.md`, ce document) — ne déplace pas le tag `v0.2-mission102`, qui continue de cibler exclusivement le commit fonctionnel ci-dessus.
