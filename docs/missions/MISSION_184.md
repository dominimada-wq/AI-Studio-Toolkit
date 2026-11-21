# Mission 184 — Allonger les délais de génération ComfyUI et Forge et distinguer un délai dépassé d'une connexion impossible

> **STATUT (2026-11-11) : Mission 184 implémentée et testée automatiquement ; validation manuelle (essais réels ComfyUI et Forge, après redémarrage du Toolkit) en attente ; deux commits fonctionnels locaux, non poussés ; mission ni publiée ni close ; suite complète non validée.** Ce statut ne ferme aucune réserve : la validation ciblée de la section 6 n'est pas une suite complète, L18 n'a pas été exécuté (non autorisé) et le plantage `0xC0000374` de la Mission 177 reste hors périmètre. Aucune génération réelle et aucun lancement de moteur n'ont été faits dans cette mission.

> **STATUT (2026-11-21) : validations manuelles ComfyUI et Forge réalisées le 2026-11-12 par l'architecte pour le scénario dépassant l'ancien délai de 120 s (résultats et limites : section 14 et R22) ; commits locaux non poussés ; mission ni publiée ni close ; suite complète non validée.** Le statut du 2026-11-11 ci-dessus est conservé comme statut daté ; les sections 1 à 8 ne sont pas modifiées.

## 1. Objectif et limites

Le Toolkit affichait une erreur de délai dépassé alors que le moteur de génération poursuivait son travail et produisait l'image. Cette mission allonge à **600 s** le délai des moteurs ComfyUI et Forge de la page Inference et fait **dire la vérité** au message de Forge : un délai dépassé n'est ni un serveur inaccessible ni la preuve que la génération s'est arrêtée côté moteur.

**Hors périmètre, par décision de l'architecte** : refonte du délai partagé entre requêtes, annulation d'une génération, garde de fermeture pendant une génération, message des délais HTTP de ComfyUI (réserve R20), relance automatique après expiration, délais réglables dans les Réglages, génération asynchrone de Forge.

## 2. Décisions de l'architecte (2026-11-11)

- Mission 184 (numéro vérifié libre : ni `MISSION_184.md`, ni tag), documentation habituelle.
- Les **deux moteurs** (ComfyUI et Forge), délai de **600 s**, **deux commits distincts** : ComfyUI, puis Forge.
- Message de Forge : distinguer un délai dépassé d'une impossibilité de connexion ; ne pas affirmer que le serveur est inaccessible ni que la génération côté moteur est arrêtée sans preuve.
- Ne pas relancer automatiquement une génération après expiration, pour éviter les doublons.
- Exécutions de tests **ciblées** : d'abord `test_main_window_comfyui_settings`, `test_main_window_forge_settings` et `test_main_window_ollama_settings` (avant et après modification, plus les relances nécessaires) ; puis, sur demande motivée de l'assistant, `test_forge_engine.py` et `test_settings_page.py`. Exclus : la suite complète, L18 et les onze autres modules construisant un `MainWindow`.
- Vérifications par tests simulés, sans génération réelle ni attente de plusieurs minutes : une génération de plus de 120 s peut aboutir avec le nouveau délai ; une expiration produit le bon message.
- Documenter le délai partagé, l'absence d'annulation et le blocage de fermeture ; ne pas élargir la mission.
- Aucun push à distance ; aucune génération ni moteur lancé par l'assistant ; l'architecte réalise lui-même les essais réels.
- La mission est présentée comme **implémentée et testée automatiquement, validation manuelle en attente**.

## 3. Constat initial (vérifié)

- `ComfyUIEngine.__init__` fixe `timeout=120.0` (`src/engines/comfyui_engine.py` l.110) ; `ForgeEngine.__init__` fait de même (`src/engines/forge_engine.py` l.114). `MainWindow` les construisait sans délai explicite (`src/ui/main_window.py`, construction des deux moteurs).
- ComfyUI : ce délai est le plafond de `wait_for_result()` (« Timed out waiting for ComfyUI result for prompt … ») **et** le délai de chaque requête HTTP de l'instance sans délai explicite (soumission, interrogation de l'historique, téléchargement). L'image est écrite dans le dossier de sortie de ComfyUI mais n'est pas importée.
- Forge : la génération est **une requête unique bloquante** ; le délai joue comme plafond de durée totale. À l'expiration, le Toolkit ferme la connexion ; Forge, appelé par son API, n'enregistre pas l'image : elle est perdue. Le message était « Forge server unreachable at … : timed out », alors que le serveur était joignable (`_request_json` regroupait `URLError` et `OSError` dont les délais).
- Mesures de durée (machine d'essai : Quadro P4000 8 Go ; propres à cette machine) :

| Moteur | Réglages | Durée | Source |
|---|---|---|---|
| ComfyUI | txt2img 832×1216, 30 pas | ≈ 145 s ; 148,4 s et 156,8 s | historique ComfyUI et protocole A/B du 2026-10-30 |
| ComfyUI | img2img, référence 941×1672, sortie 936×1672, 30 pas, force 0,75 | **233 s** de charge GPU | enregistreur système, 2026-11-06 19:11:52 → 19:15:45 ; image écrite à 19:15:46 |
| Forge | img2img 832×1216, 30 pas, force 0,75 (23 pas effectifs) | 109 s de charge GPU, échec (modèle à charger) | enregistreur, 2026-11-09 11:03:40 → 11:05:29 |
| Forge | idem | 117 s de charge GPU ; image écrite 119 s après le début de la requête : **réussite à 1 s de marge** | enregistreur, 15:40:06 → 15:42:03 |
| Forge | idem | **124 s** de charge GPU ; échec « Forge server unreachable … timed out » | enregistreur, 15:52:11 → 15:54:15 ; message affiché relevé par l'utilisateur |

- Les durées de Forge varient de 109 à 124 s à réglages identiques : l'ancien délai ne tenait qu'environ une fois sur deux. La graine de l'essai de 15:52 n'a pas été enregistrée (image perdue).
- Contexte d'essai : la machine d'essai a connu des redémarrages brutaux non résolus (notes hors dépôt). Ils sont sans rapport avec ce correctif ; ils peuvent interrompre une génération pendant les essais manuels.

## 4. Implémentation

Commit 1 — `ef013788e18c1c67e1544f3b71abba7fda49ceca` (« Raise ComfyUI generation timeout for the inference page ») :

- `src/ui/main_window.py` : constante `COMFYUI_GENERATION_TIMEOUT = 600.0`, avec un commentaire qui décrit le délai partagé, l'absence d'annulation et le blocage de fermeture ; passée à `ComfyUIEngine(..., timeout=COMFYUI_GENERATION_TIMEOUT)`.
- `tests/integration/test_main_window_comfyui_settings.py` : 4 tests.

Commit 2 — `c452233ee401ba66126e1183fc92729cee4a5d3c` (« Raise Forge generation timeout and report timeouts distinctly ») :

- `src/ui/main_window.py` : constante `FORGE_GENERATION_TIMEOUT = 600.0` et son passage à `ForgeEngine`.
- `src/engines/forge_engine.py` : `_request_json` détecte un délai dépassé (`TimeoutError` levée à la lecture, ou `URLError` dont la cause est un `TimeoutError` à la connexion, par `_is_timeout()`) et lève `ForgeEngineError("Forge did not respond within N s for <chemin> (request timed out). The Toolkit abandoned this request; whether Forge is still processing it is unknown.")`. Les autres échecs de connexion gardent « Forge server unreachable at … ». `ForgeEngineError` reste la seule classe d'erreur.
- `tests/integration/test_main_window_forge_settings.py` : 6 tests.

Aucune relance automatique n'a été introduite. Domain, Managers, `ComfyUIEngine`, `ApplicationSettings`, Blueprint, `project.json` et `CLAUDE.md` sont inchangés.

## 5. Tests ajoutés (+10)

`test_main_window_comfyui_settings.py` (classe `MainWindowComfyUIGenerationTimeoutTest`, 2 → 6 tests) :

1. `test_main_window_comfyui_engine_uses_the_generation_timeout` : valeur 600,0 et délai transmis au moteur.
2. `test_a_generation_longer_than_the_former_120_seconds_succeeds` : horloge factice et faux serveur d'historique ; une génération simulée de 150 s aboutit ; toutes les requêtes portent le délai de 600 s.
3. `test_the_former_120_second_timeout_expires_on_the_same_generation` : garde de régression, la même génération expire avec 120 s.
4. `test_expiry_reports_the_timeout_message_and_never_submits_again` : message d'expiration du plafond et uniquement des requêtes d'historique (aucune soumission, donc aucun doublon).

`test_main_window_forge_settings.py` (classe `MainWindowForgeGenerationTimeoutTest`, 3 → 9 tests) :

1. `test_main_window_forge_engine_uses_the_generation_timeout`.
2. `test_a_generation_longer_than_the_former_120_seconds_succeeds` : faux serveur dont la requête dure 150 s simulées ; une seule requête, avec le délai de 600 s.
3. `test_the_former_120_second_timeout_expires_on_the_same_generation` : même génération, 120 s : « did not respond within 120 s ».
4. `test_expiry_reports_a_timeout_and_never_claims_more_than_it_knows` : message de délai, chemin de l'appel, « unknown » ; ni « unreachable » ni « stopped » ; un seul appel (pas de seconde tentative).
5. `test_a_timeout_wrapped_in_url_error_while_connecting_is_also_a_timeout`.
6. `test_a_refused_connection_is_still_reported_as_unreachable` : trois échecs de connexion (refus, message textuel, coupure) gardent « Forge server unreachable ».

## 6. Validation automatique ciblée : ce qui a été exécuté

Environnement : Windows 10, Python 3.11.9, PySide6 6.11.1, `QT_QPA_PLATFORM=offscreen`, `unittest` ; exécutions du 2026-11-11 sur autorisation de l'architecte.

| Module | Avant | Après |
|---|---|---|
| `test_main_window_comfyui_settings` | 2 OK | **6 OK** |
| `test_main_window_forge_settings` | 3 OK | **9 OK** |
| `test_main_window_ollama_settings` | 10 OK | **10 OK** |
| `test_forge_engine` (supplémentaire) | non exécuté avant | **58 OK** |
| `test_settings_page` (supplémentaire) | non exécuté avant | **97 OK** |

- **Contrôle d'efficacité** (modifications temporaires, fichiers restaurés à l'identique et vérifiés) : sans le délai du moteur ComfyUI, 3 nouveaux tests échouent ; sans le délai du moteur Forge, 4 échouent ; avec l'ancien message de Forge, 3 échouent.
- **Séparation des commits** : l'index du premier commit ne contenait que les lignes ComfyUI de `main_window.py` (module ComfyUI : 6/6 à cet état intermédiaire) ; l'état final contient les deux correctifs ; les quatre fichiers committés sont identiques à l'état testé.
- Lecture seule : aucune relance automatique dans `GenerationManager`, `GenerationWorker` ni `InferencePage` (recherche textuelle et lecture, non démontrée par exécution).

## 7. Propriétés vérifiées et non vérifiées

**Vérifiées (tests simulés)** : valeur transmise à chaque moteur ; aboutissement d'une génération de 150 s avec le nouveau délai et expiration avec l'ancien ; message d'expiration de Forge sans affirmation de serveur inaccessible ni de génération arrêtée ; refus et coupures de connexion inchangés ; aucune seconde requête ni nouvelle soumission à l'expiration (niveau des moteurs).

**Non vérifiées** : comportement avec un vrai ComfyUI ou un vrai Forge ; délais réseau réels du système ; thread de génération Qt et boîte de dialogue qui affiche le message ; effet à l'écran ; les onze autres modules construisant un `MainWindow` (R8) ; L18 (R2) ; la suite complète (R1).

## 8. Limites connues et réserves

Limites de conception, **documentées et non traitées** (par décision) :

1. **Délai partagé** : la valeur de 600 s vaut pour toutes les requêtes de l'instance sans délai explicite (ComfyUI : soumission, historique, téléchargement ; Forge : chaque requête sans délai propre) et, pour ComfyUI, pour le plafond d'attente du résultat. Les découvertes (checkpoints, samplers, schedulers) et les contrôles de connexion passent leurs propres délais courts explicites et ne sont pas touchés.
2. **Aucune annulation** pendant une génération.
3. **Fermeture bloquée** : `closeEvent` refuse de fermer l'application tant qu'une génération est en cours ; un blocage réel peut donc durer jusqu'à 10 minutes.
4. **Message de délai de Forge pour toutes les requêtes** : le nouveau message s'applique aussi aux requêtes de découverte (par exemple « did not respond within 5 s ») ; aucun test existant n'en dépend (test_forge_engine et test_settings_page exécutés).

Réserves inscrites au registre de `docs/PROJECT_CONTEXT.md` : **R20** (message encore trompeur pour certains délais HTTP de ComfyUI), **R21** (limites de conception ci-dessus), **R22** (validation manuelle en attente et couverture simulée). Cette mission n'en ferme aucune.

## 9. Validation manuelle en attente (réalisée par l'architecte)

Après **redémarrage du Toolkit** (les moteurs sont construits au démarrage), moteurs lancés par l'architecte. Pour chaque essai, noter : (a) la **durée entre le clic sur « Générer » et l'affichage du résultat** ; (b) la **présence ou l'absence d'erreur** ; (c) la **réception de l'image dans le Toolkit et son enregistrement après « Accepter »**. Une génération reçue après plus de 120 s valide le scénario qui échouait ; si Forge termine avant 120 s, cela confirme son fonctionnement courant sans prouver le franchissement de l'ancien délai : un essai supplémentaire serait alors à décider.

Paramètres communs : prompt `Kaëlya woman, close-up portrait, front-facing, looking at camera, neutral expression, slightly parted lips, long voluminous wavy hair, deep espresso brown with subtle mahogany-burgundy and copper highlights, deep side part, swept over one shoulder, beige sleeveless ribbed top, gold hoop earrings, gold necklace, gray studio background, soft studio lighting` (357 caractères) ; prompt négatif `text, watermark` ; référence `Kaëlya Dia Identité (4).png` (941×1672), rôle « Pose / composition », force de transformation 0,75 ; checkpoint Juggernaut-XL v9 RunDiffusionPhoto v2 ; LoRA « training 04 » (`training_04__b79fead2-0acf-40e2-8e9f-5b2e0beb26bc`), force 1,00 ; 30 pas ; CFG 5,00 ; scheduler `karras` ; « Seed aléatoire » décochée, seed fixe 887855730.

| | Essai ComfyUI | Essai Forge |
|---|---|---|
| Sampler | `dpmpp_2m` | `DPM++ 2M` |
| Taille de sortie | **936×1672** (taille de la référence arrondie à un multiple de 8 ; largeur et hauteur grisées) | **832×1216** (champs du Toolkit) |
| Durée connue | **233 s** (image 00043 du 2026-11-06, charge GPU relevée par l'enregistreur) | 109 à 124 s selon l'essai ; l'essai de 124 s (2026-11-09, 15:52) a échoué avec l'ancien délai ; celui de 15:40 a abouti en 119 s |
| Résultat attendu | image reçue après environ 4 minutes, sans erreur | image reçue sans erreur, y compris au-delà de 120 s |
| Particularités | prompt, LoRA et référence tels que l'image 00043 (métadonnées du PNG) | entrée de checkpoint avec l'empreinte `c9e3e68f89` ; module VAE `sdxl_vae` et version Forge f2.0.1v1.10.1 actifs côté Forge, non pilotés par le Toolkit ; graine de l'essai de 15:52 non enregistrée (graine de l'image acceptée reprise) |

Aucune génération n'est lancée automatiquement. Les résultats de ces essais seront consignés dans une mise à jour de ce document, sans modifier les sections 1 à 8.

## 10. Preuves hors dépôt (jamais versionnées)

Rapports d'impact `RAPPORT_IMPACT_DELAI_GENERATION_COMFYUI.md` (30 octobre, remplacé) et `RAPPORT_IMPACT_DELAIS_GENERATION_COMFYUI_FORGE.md` (9 novembre, révisé le 11) ; enregistrements système et capteurs des 6 et 9 novembre (dossier `mesures/` des notes) ; métadonnées des images de ComfyUI et de Forge ; scripts temporaires de l'archivage et de la mise à jour du journal, dans l'espace temporaire de la session. Ces fichiers ne sont pas dans le dépôt.

## 11. Fichiers du périmètre et statut

Code et tests (commits `ef013788…` et `c452233e…`) : `src/ui/main_window.py`, `src/engines/forge_engine.py`, `tests/integration/test_main_window_comfyui_settings.py`, `tests/integration/test_main_window_forge_settings.py`.

Documentation (troisième commit, dont l'identifiant n'est pas cité ici : Git fait autorité) : `docs/missions/MISSION_184.md` (ce fichier), `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`, `docs/archive/README.md` (section d'archivage complémentaire), `docs/archive/changelog/CHANGELOG_M174-M174.md` et `docs/archive/MANIFEST_M174.json` (nouveaux).

Un commit documentaire ultérieur consigne les résultats de la validation manuelle (section 14 de ce fichier, `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`) ; son identifiant n'est pas cité ici : Git fait autorité.

## 12. Archivage documentaire

L'ajout de l'entrée de la Mission 184 portait à onze les entrées intégrales du journal ; l'entrée de la Mission 174 (lignes 406 à 422 du `CHANGELOG.md` de base, 10110 octets, SHA-256 `f8547d093b4a8fe7137983cfbafa67e6bf47cf9669c267665f10dc0d1ba222c3`) a été déplacée à l'identique dans `docs/archive/changelog/CHANGELOG_M174-M174.md`, avec un manifeste propre, `docs/archive/MANIFEST_M174.json`. Aucune archive existante, ni `MANIFEST.json`, ni `CORRESPONDANCE.md` n'est modifiée. Vérification de l'exactitude par empreinte contre le blob Git du commit de base `c452233ee401ba66126e1183fc92729cee4a5d3c` : voir `docs/archive/README.md`.

## 13. Suite

- Essais manuels de la section 9 : **réalisés le 2026-11-12**, résultats en section 14 (limites restantes : R22). Décision de publication (tag, push, Release) : **non décidée**, aucun push n'a été fait.
- Travaux suivants retenus par l'architecte, dans cet ordre : correction de la **liste Training vide** après ouverture d'un projet (contournée par « Fichier > Enregistrer ») ; puis **EF-01** (détecter et traiter les légendes trop longues dans le Toolkit).

## 14. Résultats de la validation manuelle (2026-11-12)

Cette section répond à la section 9, rédigée lorsque les essais étaient en attente ; les sections 1 à 8 ne sont pas modifiées. Les essais ont été réalisés par l'architecte (moteurs et générations lancés par lui) ; l'assistant n'a lancé aucune génération et a relevé les traces en lecture seule (journal de ComfyUI, fichiers horodatés, `project.json`, métadonnées des images). Les relevés détaillés sont hors dépôt (`SUIVI_ESSAIS_M184_20261111.md` du dossier de notes).

### 14.1 Images reçues et enregistrées normalement

Générations reçues dans le Toolkit puis enregistrées après « Accepter » (nouvelle entrée de `project.json` avec `generation_metadata`). Graine 887855730 et référence `Kaëlya Dia Identité (4).png` pour tous les essais.

| Essai | Moteur | Réglages enregistrés | Durée (source) | Résultat |
|---|---|---|---|---|
| ComfyUI n°2 (11:03) | ComfyUI | 30 pas, `dpmpp_2m`, `karras`, CFG 5,0, LoRA 1,0, référence 0,75, 936×1672 | 248,83 s (journal du moteur, `Prompt executed in`) | reçue et enregistrée |
| ComfyUI n°3 (11:17) | ComfyUI | 45 pas, `dpmpp_2m`, `karras`, CFG 5,0, LoRA 0,75, référence 0,75, 936×1672 | 344,63 s (journal du moteur) | reçue et enregistrée |
| ComfyUI n°4 (11:29) | ComfyUI | 45 pas, `dpmpp_2m`, `karras`, CFG 5,0, LoRA 1,0, référence 0,75, 936×1672 | 351,84 s (journal du moteur) | reçue et enregistrée |
| Forge n°1 (15:46) | Forge | 45 pas, DPM++ 2M SDE, `karras`, CFG 5,0, LoRA 1,0, avec référence (denoising 0,75), 512×512 | ≈ 62 à 73 s (estimation entre `params.txt` / `job_timestamp` et le fichier reçu ; moins de 120 s) | reçue et enregistrée |
| Forge n°2 (15:53) | Forge | 45 pas, DPM++ 2M SDE, `karras`, CFG 5,0, LoRA 1,0, sans référence, 832×1216 | ≈ 214 s (estimation entre `params.txt` et le fichier reçu ; plus de 120 s) | reçue et enregistrée |

Les durées ComfyUI sont celles du journal du moteur ; Forge ne tient aucun journal de durée exploitable : les durées Forge sont des **estimations** à partir d'horodatages de fichiers. Aucune durée n'est issue d'un chronométrage de l'architecte (non fourni).

### 14.2 Essais interrompus et image récupérée

- **Essai ComfyUI du 2026-11-11** : interrompu par un arrêt brutal de la machine (démarrage consigné à 12:26:26) ; aucune image reçue ni enregistrée ; essai non concluant, refait le 2026-11-12.
- **Essai ComfyUI n°5 du 2026-11-12** (45 pas, `dpmpp_2m_sde`, `karras`, LoRA 1,0, 936×1672, 338,15 s au journal du moteur, fin à 12:00:28.783) : le Toolkit a reçu l'image à 12:00:29.95, puis la machine s'est arrêtée brutalement (horodatage du bouton d'alimentation 12:00:30.372) avant « Accepter ». La copie du Toolkit dans `outputs\` a la bonne taille en octets mais ne contient que des octets nuls (inutilisable) et n'est pas enregistrée dans `project.json`. L'image a été **récupérée à partir du fichier de ComfyUI** (`output\AIStudioToolkit_00047_.png`, intact : signature et blocs PNG valides, 936×1672) et **importée manuellement** dans le projet, sans `generation_metadata`. Cette image **ne compte pas comme une réception et un enregistrement normaux** et n'entre pas dans la validation du scénario.

### 14.3 Écarts avec le protocole de la section 9

- Étapes : 45 au lieu de 30 pour plusieurs essais ; force du LoRA 0,75 pour un essai ; sampler `dpmpp_2m_sde` (ComfyUI n°5, Forge n°1 et n°2) au lieu de `dpmpp_2m` / `DPM++ 2M`.
- Forge n°1 : 512×512 (valeur par défaut des champs de taille, grisés quand une référence est active) au lieu de 832×1216 ; Forge n°2 : sans image de référence.
- Chronométrage clic → affichage non fourni ; l'effet à l'écran n'est connu que par les déclarations de l'architecte ci-dessous.
- Constat non traité : `generation_metadata` enregistre une largeur et une hauteur de 512×512 pour des générations ComfyUI avec référence, alors que la taille réelle (936×1672) vient de la référence.

### 14.4 Confirmations de l'architecte (formulations conservées)

- Forge : « aucune erreur forge affichée ».
- ComfyUI : « comfyUI a déjà été testé avec la rallonge des délais » (formulation indirecte, sans texte d'erreur ni chronométrage ; retenue telle quelle).

### 14.5 Verdict et limites

- **Scénario qui échouait (génération de plus de 120 s)** : ComfyUI (248,83 à 351,84 s) et Forge (≈ 214 s) ont reçu et enregistré une image, sans erreur déclarée par l'architecte. La partie « validation manuelle en attente » de R22 est levée pour ce scénario.
- **Limites restantes (R22 reformulée)** : durées issues des traces et non d'un chronométrage ; écarts au protocole initial (14.3) ; **expiration réelle à 600 s non testée** (le message « Forge did not respond within 600 s » n'a pas été observé) ; couverture automatique toujours simulée (voir section 7).
- R20 et R21 sont inchangées ; aucune réserve n'est fermée. La décision de publication (tag, push, Release) reste non prise ; aucun push n'a été fait.
