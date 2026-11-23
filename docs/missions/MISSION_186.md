# Mission 186 — Vérifier la longueur des légendes d'une session d'entraînement SDXL (EF-01, périmètre minimal : détection, affichage, export CSV)

> **STATUT (2026-11-23) : Mission 186 implémentée et testée automatiquement (validation ciblée de sept modules, dérogation motivée pour un module construisant `MainWindow`) ; contrôle réel limité réalisé (CPU, hors ligne, légendes fictives) ; vérification manuelle dans l'interface non réalisée ; quatre commits fonctionnels locaux, non poussés ; mission ni publiée ni close ; suite complète non validée.** Ce statut ne ferme aucune réserve : la validation ciblée de la section 6 n'est pas une suite complète, L18 n'a pas été exécuté (non autorisé) et le plantage `0xC0000374` de la Mission 177 reste hors périmètre. Aucun entraînement, aucune génération et aucun lancement de moteur n'ont été faits dans cette mission.

## 1. Objectif et limites

OneTrainer tronque en silence la fin d'une légende qui dépasse la limite de son encodeur de texte (constat établi sur le dataset Kaelya04 : 61 légendes sur 80, SDXL). Cette mission ajoute, à la page Training, un bouton **« Vérifier les légendes »** qui, pour la session sélectionnée, **détecte** les légendes trop longues, les **affiche** et les **exporte en CSV** pour correction externe. Périmètre minimal validé par l'architecte (fiche EF-01 hors dépôt).

Hors périmètre (non implémenté, explicitement différé) : réimport contrôlé des légendes corrigées ; correction dans le Toolkit (édition avec comptage en direct, propositions de raccourcissement) ; contrôle automatique au Prepare/Start ; architectures autres que SDXL (affichées « non vérifiable ») ; affichage dans la page Datasets ; mémorisation du résultat dans le projet (aucun stockage, aucun événement) ; évolutions EF-02 à EF-04 ; diagnostic des arrêts de la machine.

## 2. Décisions de l'architecte (2026-11-21 et 2026-11-23)

- EF-01 devient la **Mission 186** (numéro libre : aucun fichier, tag ni entrée du journal ne le portait). Détection, affichage et export CSV uniquement ; bouton « Vérifier les légendes » dans Training ; **processus séparé avec le Python de OneTrainer**, sans nouvelle dépendance dans le Toolkit.
- Commits locaux par couche, sans tag, push ni Release. Conformément à `CLAUDE.md` (ne pas mélanger Domain, Storage, Manager et UI dans un même commit), le stockage CSV et le Manager font **deux commits distincts** : Engines, Storage, Manager, UI, puis documentation.
- Cinq exigences : (1) compter le texte selon la règle de `_materialize_concept()` sans la dupliquer ; (2) vérifier les deux tokenizers SDXL, distinguer contenu et jetons spéciaux, établir la source et sa compatibilité, sinon « non vérifiable » ; (3) distinguer conforme, trop longue et non vérifiable, sans bilan rassurant en cas d'échec partiel, et préciser si la partie tronquée est décodée ; (4) interface réactive, délai borné, pas de téléchargement, de modèle ni de GPU, résultat lié à la session et aux textes analysés ; (5) export identifiant sans ambiguïté chaque image.
- Vérifications demandées en plus : légendes multilignes (chaque ligne jugée seule), lignes vides et espaces contre le chemin OneTrainer réellement utilisé, cas vide (« conforme » = aucune longueur excessive, sans remplacement par le déclencheur), erreurs du helper visibles, aucun processus laissé actif, aucun résultat appliqué au mauvais contexte, obsolescence sur changement de dataset, légende, déclencheur ou architecture.
- **Contrôle réel limité autorisé** : CPU, Python de OneTrainer, tokenizers déjà présents en local, légendes fictives ; ni entraînement, ni installation, ni téléchargement.
- Tests ciblés autorisés : `test_caption_length_check`, `test_caption_report_storage`, `test_training_caption_analysis`, `test_training_page_caption_check`, `test_training_roundtrip`, `test_training_page_external_refresh`, `test_main_window_training_to_inference` (**dérogation explicite** pour sa construction de `MainWindow`), relances nécessaires comprises ; L18 et suite complète exclus. Les 460 tests de la Mission 185 sont une **référence antérieure**, non une nouvelle mesure avant modification.

## 3. Constat initial (établi par lecture du code et par exécution)

- **Chemin d'entraînement pris en charge.** `StableDiffusionXLModelLoader.__load_safetensors` (OneTrainer) construit l'`StableDiffusionXLPipeline` par `from_single_file(..., original_config=...)`. Dans le diffusers fourni avec OneTrainer, la configuration d'un checkpoint SDXL de base (`DIFFUSERS_DEFAULT_PIPELINE_PATHS["xl_base"]`) est le dépôt `stabilityai/stable-diffusion-xl-base-1.0` ; ses sous-dossiers `tokenizer` et `tokenizer_2` sont chargés en `CLIPTokenizer`. Le chemin `openai/clip-vit-large-patch14` et `laion/CLIP-ViT-bigG-14-laion2B-39B-b160k` n'est utilisé qu'en repli hors cache (`local_files_only` et configuration absente) : le helper ne le substitue jamais.
- **Lecture d'une légende.** `mgds/pipelineModules/LoadMultipleTexts.py` lit le fichier `.txt` avec `[line.strip() for line in f]`, supprime les lignes vides et retombe sur `[""]` s'il n'en reste aucune ; `SelectRandomText` choisit une ligne ; `Tokenize.py` tokenise avec `padding='max_length', truncation=True, max_length=model_max_length` (77 pour les deux tokenizers). Le Toolkit n'écrit qu'un concept minimal (`name`, `path`) : valeurs par défaut de `ConceptConfig` (`prompt_source` « sample », mélange de balises désactivé).
- **Environnements.** Le venv du Toolkit ne contient ni `transformers`, ni `tokenizers`, ni `regex`. Le Python de OneTrainer (`<onetrainer_path>/venv/Scripts/python.exe`) dispose de `transformers 5.5.4` et `tokenizers 0.22.2`. Le cache Hugging Face local contient un instantané du dépôt SDXL (révision `462165984030…`) avec `tokenizer` et `tokenizer_2`.
- **Précédent d'architecture** : `onetrainer_cancel_helper.py` (Mission 100) est un script lancé comme processus séparé avec le Python de OneTrainer, jamais importé dans le processus du Toolkit.

## 4. Implémentation

- **Engines** (`src/engines/caption_token_helper.py`, `src/engines/caption_length_check.py`). Le helper (protocole JSON ASCII, hors ligne, CPU, aucun modèle chargé) charge les deux `CLIPTokenizer` depuis l'instantané local, vérifie `model_max_length` = 77 et 2 jetons spéciaux, compte les jetons de contenu de chaque ligne et décode la partie au-delà de la limite. Le côté Toolkit reproduit la lecture de OneTrainer (`caption_lines()`), calcule les statuts (**conforme**, **trop longue**, **non vérifiable** ; trop longue l'emporte sur non vérifiable, qui l'emporte sur conforme), signale le numéro de ligne et les comptes de chaque tokenizer, marque les légendes sans aucun texte exploitable (aucun remplacement par le déclencheur) et lie le résultat à une empreinte (session, architecture, dataset, installation OneTrainer, textes et origines). Le processus est borné (120 s), son **arbre entier** est tué à l'expiration, à l'annulation et à la sortie **normale** de l'application (pas en cas d'arrêt forcé du Toolkit : voir la section 9) ; les messages d'erreur standard du helper restent visibles, seul l'avertissement de longueur attendu est retiré.
- **Storage** (`src/infrastructure/storage/caption_report_storage.py`). CSV UTF-8 avec BOM, tous les champs entre guillemets, fichier temporaire déplacé en place.
- **Manager** (`src/managers/training_manager.py`). `resolve_concept_caption()` porte la règle unique « entrée du dataset, même vide, sinon mot déclencheur », utilisée par `_materialize_concept()` et par la nouvelle `caption_analysis_inputs()` (lecture seule, sans écriture, sans événement, avec le nom de fichier du `.txt` du concept).
- **UI** (`src/ui/caption_check_worker.py`, `src/ui/dialogs/caption_check_dialog.py`, `src/ui/pages/training_page.py`). Fil de travail démon, jamais attaché à la page, annulable ; bouton et libellé d'état ; dialogue avec bilan, source des tokenizers, messages du helper, tableau et export. Un résultat est abandonné ou marqué obsolète, et l'export est désactivé, dès que la session, le dataset, les légendes, le déclencheur, l'architecture ou l'installation OneTrainer changent ; fermer le projet ou détruire la page annule l'analyse.
- **Colonnes de l'export** : identifiants de la session et de l'image, nom du fichier, nom du `.txt` du concept, origine du texte, texte exploitable ou non, nombre de lignes, texte analysé exact, comptes de contenu et jetons spéciaux de chaque tokenizer avec la ligne la plus longue, limites, statut et raison, ligne et partie tronquées de chaque tokenizer (décodage des jetons), sources des tokenizers, empreinte.

## 5. Tests ajoutés (+98)

- `test_caption_length_check.py` (45) : lecture des lignes, empreinte, statuts, légendes multilignes (deux lignes sous la limite ne sont pas « trop longues » ; une seule ligne trop longue est signalée avec son numéro et les comptes de chaque tokenizer), lignes vides et espaces, cas vide signalé sans remplacement, désaccord et panne partielle de tokenizer, toutes les défaillances du helper (expiration, démarrage, code de sortie, sortie illisible ou invalide, résultat incomplet) avec messages visibles, protocole du helper avec modules `transformers` et `huggingface_hub` simulés (limite de 75, jetons spéciaux, partie décodée, hors ligne, source locale, échecs), lignes d'export, et **processus réels inoffensifs** : expiration et annulation tuent l'arbre entier, aucun processus ne reste.
- `test_caption_report_storage.py` (5) : aller-retour avec accents, guillemets, virgules et retours à la ligne, BOM, remplacement, aucun fichier à moitié écrit.
- `test_training_caption_analysis.py` (13) : règle partagée, légende vide distincte d'une entrée absente, **égalité avec les fichiers réellement écrits par `_materialize_concept()`** et avec la lecture de `LoadMultipleTexts` répliquée, lecture seule (aucune écriture, aucun événement, aucun fichier), contextes non résolus, empreinte sensible aux changements.
- `test_training_page_caption_check.py` (35) : bouton, interface réactive pendant l'analyse, session et textes liés au résultat, obsolescence sur changement de légende, session, déclencheur, architecture, contenu du dataset, dataset de la session et installation OneTrainer, export impossible d'un résultat obsolète, contexte (fermeture du projet, destruction de la page, résultat tardif d'une analyse abandonnée ignoré, aucune erreur de fil), architecture non SDXL et OneTrainer non configuré avec le vrai moteur sans lancer de processus, dialogue (bilan, messages, numéros de ligne, export, annulation, échec d'écriture).

## 6. Validation automatique ciblée : ce qui a été exécuté

Environnement : Windows 10, Python 3.11.9, PySide6 6.11.1, `QT_QPA_PLATFORM=offscreen`, `unittest` ; exécutions du 2026-11-23 sur autorisation de l'architecte.

| Module | Tests | Résultat |
|---|---|---|
| `test_caption_length_check` (nouveau) | 45 | réussis |
| `test_caption_report_storage` (nouveau) | 5 | réussis |
| `test_training_caption_analysis` (nouveau) | 13 | réussis |
| `test_training_page_caption_check` (nouveau) | 35 | réussis |
| `test_training_roundtrip` | 437 | réussis |
| `test_training_page_external_refresh` | 18 | réussis |
| `test_main_window_training_to_inference` (dérogation `MainWindow`) | 5 | réussis |
| **Total** | **558** | **tous réussis** |

Les trois modules existants (437 + 18 + 5 = 460) donnent le même nombre qu'à la fin de la Mission 185, qui reste une **référence antérieure** : aucune mesure n'a été refaite avant la modification de la Mission 186. Relances nécessaires : trois défauts **de tests** (un nombre de mots attendu erroné, une substitution de méthode de Qt, un scénario de bouton incohérent avec l'état du Manager) ont été corrigés après un premier passage en échec ; aucun défaut du code de production n'a été mis en évidence par ces échecs.

## 7. Contrôle réel limité (CPU, hors ligne, légendes fictives)

Scripts temporaires hors dépôt ; aucun entraînement, aucune installation, aucun téléchargement, aucune écriture dans OneTrainer.

- **Helper, Python de OneTrainer, deux tokenizers** : les deux `CLIPTokenizer` viennent du même instantané local, 77 positions, 2 jetons spéciaux, limite de contenu 75. Cas : vide 0 ; texte accentué 36 ; exactement 75 : conforme ; 76 : trop longue ; 200 : trop longue ; 75 puis 80 mots accentués : conforme puis trop longue ; comptes **identiques** pour les deux tokenizers. Premier démarrage : 29,5 s ; `cuda_initialized` faux, mémoire GPU 0 Mo après l'essai.
- **Lecture des légendes par le vrai module `LoadMultipleTexts` de OneTrainer** sur 12 fichiers fictifs écrits comme le fait `_materialize_concept()` (vide, espaces seuls, sauts de ligne seuls, lignes vides, CRLF/CR/LF, tabulation, espace insécable, séparateur U+2028, accents, saut final, BOM, tabulation verticale et saut de page) : **12 cas sur 12 identiques** à `caption_lines()`.
- **Troncature réelle** (`padding='max_length', truncation=True, max_length=77`) : positions utiles = `min(n, 75) + 2` et longueur 77 pour n = 0, 1, 74, 75, 76 et 100, avec les deux tokenizers.
- **Processus** : expiration à 4 s arrêtée en 4,5 s, annulation à 3 s arrêtée en 3,4 s, aucun processus de comptage restant.

## 8. Propriétés vérifiées et non vérifiées

**Vérifié par exécution** : tout ce qui précède, dont l'équivalence de la règle de texte avec les fichiers écrits, la lecture ligne par ligne, la non-écriture, l'absence de processus restant et la liaison du résultat à son contexte.

**Non vérifié** : bouton et dialogue dans le `MainWindow` réel, avec le vrai OneTrainer et le vrai dataset (vérification manuelle de la section 10, non réalisée) ; export dans l'explorateur de fichiers réel ; comportement avec des légendes réelles très nombreuses ; équivalence entre l'instantané local des tokenizers et une révision en ligne ; suite complète.

## 9. Limites connues et réserves

1. Suite complète non validée (R1 à R3), L18 non autorisé ; validation ciblée de sept modules.
2. **Source des tokenizers** : instantané local du cache Hugging Face (révision affichée dans le dialogue et l'export) ; OneTrainer en ligne pourrait en actualiser la révision, ce qu'un contrôle hors ligne ne peut pas établir. Absent, l'instantané donne « non vérifiable », sans substitution.
3. Seule l'architecture SDXL a été auditée ; les autres sont « non vérifiable ».
4. **La partie tronquée est reconstruite par décodage des jetons** (normalisée : minuscules, espaces) et peut différer des caractères d'origine ; le texte analysé exact figure dans l'export.
5. « Conforme » signifie uniquement « aucune longueur excessive ». Une légende sans aucun texte exploitable est signalée ; OneTrainer s'entraîne alors sur un texte vide, et ni le Toolkit ni cette vérification ne le remplacent par le déclencheur.
6. OneTrainer choisit au hasard une ligne d'une légende multiligne à chaque pas : chaque ligne est jugée séparément, la somme des lignes ne compte pas.
7. **Processus helper : ce qui est borné et ce qui ne l'est pas.** *Testés et vérifiés* : l'annulation (changement de session, fermeture du projet, destruction de la page), l'expiration du délai de 120 s et la **sortie normale** de l'application tuent l'arbre entier du helper (processus réels de test ; vrai helper : expiration à 4 s arrêtée en 4,5 s, annulation à 3 s arrêtée en 3,4 s ; sortie normale d'un interpréteur pendant un comptage : aucun helper 0,9 s après, par le crochet `atexit` du moteur). *Non couvert* : l'**arrêt forcé du Toolkit** (gestionnaire des tâches, plantage, coupure) : le délai de 120 s est tenu par le processus **parent** (`communicate(timeout=...)`) ; si le parent disparaît, **il ne s'applique plus** et rien ne tue le helper. Mesure du 2026-11-23 (vrai helper, légende fictive, parent tué de force pendant le comptage) : le helper a poursuivi son travail et s'est arrêté de lui-même environ 41 s après la mort du parent, une seule mesure, vraisemblablement quand sa réponse n'a plus pu être écrite dans le tube fermé (cause déduite, non observée). **Aucun arrêt borné n'est promis dans ce cas** : un helper bloqué (import ou tokenizer figé) resterait actif jusqu'à ce qu'il se termine ou qu'un utilisateur l'arrête ; il n'écrit rien sur le disque et n'emploie que le CPU. Atténuations possibles, non implémentées (décision à prendre) : un minuteur de sortie dans le helper, ou un objet Job Windows qui tue le helper à la disparition du parent. Premier démarrage du helper d'environ 30 s.
8. Aucune nouvelle réserve n'est inscrite au registre de `docs/PROJECT_CONTEXT.md` et aucune réserve existante n'est fermée ; une inscription éventuelle est une décision à prendre séparément.
9. Contrôle des liens de la documentation : les douze « ancres absentes » signalées par un vérificateur sur d'anciens liens vers `docs/archive/changelog/CHANGELOG_M041-M001.md` sont une limite de ce vérificateur (titres d'archive écrits comme des liens Markdown), non un défaut de lien ; traitement séparé, aucune modification (note hors dépôt).

## 10. Vérification manuelle (à réaliser par l'architecte, non réalisée à ce jour)

1. Relancer le Toolkit (l'instance déjà ouverte ne contient pas le code).
2. Ouvrir `Essai-Recette-2`, page Training, sélectionner une session SDXL (par exemple `training 04`).
3. Cliquer sur **« Vérifier les légendes »** : le bouton devient « Vérification des légendes en cours… » et l'interface reste utilisable ; compter environ 30 s au premier lancement. Changer de session pendant l'analyse l'abandonne (message « Vérification abandonnée »).
4. Dans le dialogue : lire le bilan (conformes (longueur), trop longues, non vérifiables), la source des tokenizers (instantané `stabilityai/stable-diffusion-xl-base-1.0`, limite de 75 jetons) et le tableau (statut, comptes des deux tokenizers, ligne et partie tronquées). Un bilan « INCOMPLET » ou « non vérifiable » ne doit jamais être lu comme conforme.
5. **Exporter en CSV** vers un dossier hors du projet ; ouvrir le fichier dans un tableur ou un éditeur : une ligne par image, accents conservés.
6. Modifier une légende dans la page Datasets, revenir sur Training : le libellé indique une vérification obsolète.
7. Le bouton ne doit rien écrire dans le projet.

**Statut : vérification manuelle en attente** (aucune observation reçue de l'architecte à ce jour). Empreinte de `project.json` relevée en lecture seule avant l'essai (2026-11-23, 10 h 21, hors dépôt) : 183586 octets, dernière modification 2026-11-21 11:12:32, SHA-256 `ec5defeff84879dd418b41424b3ba631894f4808319f186b4529a62005788c27`. Une comparaison après l'essai n'a de valeur que si aucune autre modification du projet n'a été faite entre-temps ; la non-écriture du bouton est établie séparément par le contrôle automatisé de la section 5. Le scénario d'obsolescence ne sera pas éprouvé sur les légendes validées, mais sur des données temporaires (tests automatisés de la section 5).

## 11. Preuves hors dépôt (jamais versionnées)

Rapport d'impact `RAPPORT_IMPACT_EF01_20261121.md` ; fiche `EVOLUTIONS_FUTURES_TOOLKIT.md` (EF-01) ; note `NOTE_VERIFICATEUR_LIENS_20261121.md` ; relevé de l'empreinte de `project.json` avant la vérification manuelle (`RELEVE_PROJECT_JSON_AVANT_ESSAI_M186_20261123.md`) ; scripts temporaires du contrôle réel, des expériences d'arrêt du helper et de l'archivage (espace temporaire de la session). Ces fichiers ne sont pas dans le dépôt.

## 12. Fichiers du périmètre et statut

Quatre commits fonctionnels locaux, non poussés :

- Engines `d76471e60635fb4a25e5a5ba53c966c8e09ba613` : `src/engines/caption_token_helper.py`, `src/engines/caption_length_check.py`, `tests/integration/test_caption_length_check.py`.
- Storage `1939104205b35ce4840458e95f197b9b3f419d98` : `src/infrastructure/storage/caption_report_storage.py`, `tests/integration/test_caption_report_storage.py`.
- Manager `5726379d75552b1796c0cfdf6b45d565baf47832` : `src/managers/training_manager.py`, `tests/integration/test_training_caption_analysis.py`.
- UI `9c668079c21afb0b24752c3289f1e43e77d67aac` : `src/ui/caption_check_worker.py`, `src/ui/dialogs/caption_check_dialog.py`, `src/ui/pages/training_page.py`, `tests/integration/test_training_page_caption_check.py`.

Documentation (commit suivant, dont l'identifiant n'est pas cité ici : Git fait autorité) : `docs/missions/MISSION_186.md` (ce fichier), `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`, `docs/archive/README.md` (section d'archivage complémentaire), `docs/archive/changelog/CHANGELOG_M176-M176.md` et `docs/archive/MANIFEST_M176.json` (nouveaux).

## 13. Archivage documentaire

L'ajout de l'entrée de la Mission 186 portait à onze les entrées intégrales du journal ; l'entrée de la Mission 176 (lignes 408 à 422 du `CHANGELOG.md` de base, 12377 octets, SHA-256 `eb78c3e1aaf7b50d971c99d298d75560c6242280903a21dc79252395a868bb7f`) a été déplacée à l'identique dans `docs/archive/changelog/CHANGELOG_M176-M176.md` (13730 octets, SHA-256 `ac7fcbf4fba5f5e804af6406ef398c0667b5673a923335e6e79540777586e02d`), avec un manifeste propre, `docs/archive/MANIFEST_M176.json`. La source a été revérifiée au commit de base `9c668079c21afb0b24752c3289f1e43e77d67aac` (424 lignes, 139815 octets) avant toute écriture. Aucune archive existante, ni `MANIFEST.json`, ni `MANIFEST_M174.json`, ni `MANIFEST_M175.json`, ni `CORRESPONDANCE.md` n'est modifiée. Les dix entrées intégrales restantes de `CHANGELOG.md` sont celles des Missions 177 à 186.

## 14. Suite

- Vérification manuelle de la section 10, à réaliser par l'architecte.
- Décision de publication (tag, push, Release) des Missions 184, 185 et 186 : **non décidée**, aucun push n'a été fait.
- Fonctions différées (section 1) : réimport contrôlé, correction intégrée, contrôle au Prepare/Start, autres architectures ; EF-02, EF-03 et EF-04 restent enregistrées hors dépôt ; un éventuel menu « Fermer le projet » est une évolution distincte.
