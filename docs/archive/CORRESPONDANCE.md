# Table de correspondance de la consolidation documentaire (Mission 183)

Cette table indique, pour chaque partie des documents d'origine (commit `cd86418dacf3cd6c332dc9259d8d0883c6365774`), si elle est **conservée** (à l'identique, au même endroit), **déplacée** (à l'identique, vers `docs/archive/`), **résumée** (une synthèse la remplace dans le document courant ; l'original est déplacé à l'identique), **corrigée** (texte modifié à partir de sources identifiées) ou **ajoutée**. La conservation exacte est affirmée **uniquement** pour les contenus dont elle est effectivement vérifiée par empreinte (régime A ci-dessous). Les autres textes remplacés (régime B) ne sont pas copiés dans `docs/archive/` : leur ancienne formulation reste dans l'historique Git (blob du commit de base et diff de la mission). Les synthèses et les corrections sont les seules parties qui ne sont pas des copies : ce sont celles que la revue doit lire.

## Régimes de conservation

| Régime | Contenus | Où se retrouve l'ancien texte | Vérification |
|---|---|---|---|
| **A. Archive documentaire exacte** | les onze tranches de l'ancien `PROJECT_CONTEXT.md` ; les 183 entrées et le Sommaire d'origine du journal ; les sections « Roadmap des prochaines missions » et « Structure du dépôt » du README | `docs/archive/` | reconstitution octet pour octet et empreintes SHA-256 (`MANIFEST.json`) |
| **B. Historique Git et diff de la mission** | parties réécrites du README (statut, fonctionnalités, tests, deux phrases sur Kohya_ss, titre et lien de la feuille de route, section Releases) ; anciennes formulations de `CLAUDE.md` et de `AGENTS.md` | historique Git (blob du commit de base, diff de la mission) ; **non archivé** dans `docs/archive/` | blobs du commit de base ; diff exact conservé |
| **C. Texte ajouté** | synthèses, registre des réserves, index, règles, `MISSION_183.md` | — | relecture (voir la revue pré-commit) |

## `docs/PROJECT_CONTEXT.md` (1 059 844 octets, blob LF → document courant synthétique)

| Lignes d'origine | Contenu | Octets | Traitement | Destination |
|---|---|---|---|---|
| 1–2 | Titre « État consolidé… » | 71 | corrigé (titre, rôle du document) | PROJECT_CONTEXT.md (en-tête) ; texte d'origine : docs/archive/project_context/PC_01 |
| 3–7 | Bandeaux de statut des Missions 182, 181 et 177 | 7814 | déplacé à l'identique ; remplacé par le statut courant | docs/archive/project_context/PC_01 ; PROJECT_CONTEXT.md (« Statut courant ») |
| 9–11 | « État actuel du projet » : ligne HEAD du repository | 215 | résumé (même règle : Git fait autorité) | PROJECT_CONTEXT.md (« HEAD du repository… ») ; docs/archive/project_context/PC_01 |
| 12–12 | Dernier commit de mission (chaîne d'environ 60 commits antérieurs, SHA et intitulés) | 8386 | résumé : SHA des Missions 182 et 181 conservés ; la chaîne complète est déplacée | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_01 (ligne 12) |
| 13–13 | Dernier tag de mission (SHA des objets de tags 163 à 182) | 6005 | résumé : tag de la Mission 182 conservé ; liste complète déplacée (récupérable par `git tag`) | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_01 (ligne 13) |
| 14–19 | Bullets de statut des Missions 177 à 182 (statuts datés empilés) | 25943 | déplacé à l'identique ; résumé dans « Dernière mission terminée » et dans le registre des réserves | docs/archive/project_context/PC_01 ; PROJECT_CONTEXT.md |
| 20–20 | « Suite de tests » : validation Missions 097 à 182 (44 Ko sur une ligne) | 44136 | déplacé à l'identique ; résumé dans « État actuel du projet » (validation, tests) | docs/archive/project_context/PC_01 ; PROJECT_CONTEXT.md |
| 21–25 | Bullets des Missions 078 à 081 et « Statut général » (92 Ko, Missions 013 à 081) | 99698 | déplacé à l'identique ; non repris (historique de missions) | docs/archive/project_context/PC_01 |
| 27–27 | Principe de non-auto-référence | 1082 | conservé à l'identique (aussi dans l'archive) | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_01 |
| 29–111 | « Architecture actuelle » (11 classes Domain, Managers, Infrastructure, Engines, UI, EventBus) | 35236 | déplacé à l'identique ; corrigé : inventaire relevé par lecture statique du dépôt (champs, Managers, événements, Engines, UI) | PROJECT_CONTEXT.md (« Architecture actuelle ») ; docs/archive/project_context/PC_02 |
| 112–115 | « Tests » : énumération historique par fichier (105 Ko, « non maintenue ») | 105569 | déplacé à l'identique ; non repris (66 modules, commande canonique et réserves résumés) | docs/archive/project_context/PC_03 ; PROJECT_CONTEXT.md (« État actuel ») |
| 116–151 | « Fonctionnalités terminées » (arrêtée à la Mission 033) | 37543 | déplacé à l'identique ; corrigé : synthèse par domaine jusqu'à la Mission 182 | PROJECT_CONTEXT.md (« Fonctionnalités terminées ») ; docs/archive/project_context/PC_04 |
| 152–188 | « Décisions techniques importantes à retenir » (décisions par mission, Missions 011 à 024) | 22921 | déplacé à l'identique ; résumé des décisions durables | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_05 |
| 189–209 | « Fichiers et répertoires structurants » (arbre périmé : 11 fichiers Domain, 23 fichiers de test) et « Dépendances importantes » | 1388 | déplacé à l'identique ; corrigé : répertoires et dépendances relevés sur le dépôt | PROJECT_CONTEXT.md (« État actuel ») ; docs/archive/project_context/PC_05 |
| 210–325 | « Problèmes connus / dettes » (dettes résolues des Missions 011 à 155, réserves ouvertes, traçabilités de suites) | 78218 | déplacé à l'identique ; résumé : registre unique des réserves ouvertes R1 à R17 | PROJECT_CONTEXT.md (registre) ; docs/archive/project_context/PC_06 |
| 326–489 | « Besoins futurs identifiés par l'usage réel » (45 besoins) | 147452 | déplacé à l'identique ; résumé : tableau des intitulés, statut non réévalué | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_07 |
| 490–518 | « Orientation architecturale validée » (1 Workspace = 1 personnage) | 6538 | déplacé à l'identique ; résumé | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_08 |
| 519–522 | « Travaux encore en attente » (34 Ko, « aucune direction arrêtée au-delà de Mission 058 ») | 34121 | déplacé à l'identique ; non repris (énoncé périmé) ; remplacé par « Prochaine étape » | docs/archive/project_context/PC_08 |
| 523–654 | « Dernière mission terminée » (indication courante Mission 182 et récits des missions récentes) | 207770 | déplacé à l'identique ; résumé de la Mission 182 et des cinq missions précédentes | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_09 |
| 655–666 | « HEAD du repository », « Dernier commit de mission », « Dernier tag de mission » | 13449 | déplacé à l'identique ; résumé | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_10 |
| 667–676 | « Prochaine mission prévue » (énoncés datés empilés, 170 Ko) | 176287 | déplacé à l'identique ; remplacé par « Prochaine mission prévue et prochaine étape » | PROJECT_CONTEXT.md ; docs/archive/project_context/PC_11 |

Ajouts qui n'existaient pas dans le document d'origine : « Lecture à la reprise », « Règles de maintenance de ce document », « Index des anciennes sections », le registre des réserves (R1 à R19, avec la colonne **Nature** : réserve établie, limite de couverture ou piste non confirmée, chacune avec sa source), le bilan de validation reformulé (Mission 181 : résultats répartis sur trois manifestes et deux états du code, L04 par réévaluation), « Environnement des exécutions consignées » (ancien « Environnement validé »), l'inventaire d'architecture relevé par analyse statique.

## `CHANGELOG.md` (1 153 617 octets, blob LF)

| Partie | Traitement | Destination | Contrôle |
|---|---|---|---|
| Titre et phrase d'introduction (lignes 1 à 4) | corrigé (introduction complétée par l'organisation en index, dix dernières missions et archives) | `CHANGELOG.md` | première ligne inchangée |
| Sommaire d'origine (817 lignes, 183 groupes) | déplacé à l'identique, réparti : groupes des entrées courantes dans `CHANGELOG.md`, autres en tête de chaque archive | `CHANGELOG.md` ; `docs/archive/changelog/*` | la concaténation redonne le Sommaire d'origine octet pour octet |
| Index des missions (185 lignes : 184 missions dont la Mission 138, qui a un document mais pas d'entrée de journal, plus 1 correctif sans numéro) | ajouté ; chaque ligne porte le titre du document de mission **et** le nom de la section d'origine, pour retrouver les références écrites avant la réorganisation | `CHANGELOG.md` | chaque lien résolu |
| Entrée de la Mission 183 et son groupe de Sommaire | ajouté | `CHANGELOG.md` | n'existe pas dans l'original ; exclue de la comparaison d'exactitude |
| Entrées Missions 174 à 182 (9 entrées) | conservé à l'identique | `CHANGELOG.md` | idem |
| Entrées Missions 149 à 173 (26 entrées ; dont le « Correctif de fixtures post-M173 ») | déplacé à l'identique | `docs/archive/changelog/CHANGELOG_M173-M149.md` | empreintes par entrée dans `MANIFEST.json` |
| Entrées Missions 124 à 148 (25 entrées ; dont « Correctifs pré-Mission 124 ») | déplacé à l'identique | `docs/archive/changelog/CHANGELOG_M148-M124.md` | empreintes par entrée dans `MANIFEST.json` |
| Entrées Missions 084 à 123 (40 entrées) | déplacé à l'identique | `docs/archive/changelog/CHANGELOG_M123-M084.md` | empreintes par entrée dans `MANIFEST.json` |
| Entrées Missions 042 à 083 (42 entrées) | déplacé à l'identique | `docs/archive/changelog/CHANGELOG_M083-M042.md` | empreintes par entrée dans `MANIFEST.json` |
| Entrées Missions 001 à 041 (41 entrées) | déplacé à l'identique | `docs/archive/changelog/CHANGELOG_M041-M001.md` | empreintes par entrée dans `MANIFEST.json` |

## `README.md` (33 191 octets, blob LF)

| Partie | Traitement | Source ou constat qui fonde le changement | Destination |
|---|---|---|---|
| Lignes 38 et 46 : « OneTrainer et Kohya_ss de l'entraînement » | corrigé : OneTrainer seul ; Kohya_ss mentionné comme backend potentiel futur non engagé | `CLAUDE.md` (politique Training) ; `docs/blueprint/01_PRODUCT_REQUIREMENTS.md` lignes 213 et 495 ; recherche textuelle de « kohya » dans `src/` : une docstring seulement (constat lexical, qui ne prouve pas l'absence d'intégration) | `README.md` |
| Ligne 12 : statut arrêté à la Mission 010 (« définition uniquement, sans exécution » pour Training) | corrigé : statut neutre renvoyant à `docs/PROJECT_CONTEXT.md`, avec le dernier état publié daté et ses réserves ; un tag n'atteste pas la clôture ni la validation | `docs/PROJECT_CONTEXT.md` ; `docs/missions/MISSION_182.md` | `README.md` ; ancien texte : régime B |
| Section « Fonctionnalités actuelles » (arrêtée à la Mission 010, 17 puces) | corrigé : synthèse par domaine issue des missions, avec renvois aux numéros de mission et une liste de limites ; présentée comme synthèse, pas comme nouvelle vérification | titres et récits de `docs/missions/` ; fichiers de `src/` | `README.md` ; ancien texte : régime B |
| Section « Tests » (dix modules listés) | corrigé : commande canonique, nombre de modules (66), limites de validation | `tests/integration/` ; `docs/missions/MISSION_177.md`, `MISSION_181.md` | `README.md` |
| Section « Structure du dépôt » (arborescence d'origine) | déplacé à l'identique (archive) ; remplacé par l'arborescence des fichiers suivis par Git | `git ls-files` au commit de base | `docs/archive/readme/` ; `README.md` |
| Section « Roadmap des prochaines missions » : lignes « Mission 011 — À définir » et « Missions suivantes — Planifiées » | déplacé à l'identique (archive) ; section renommée « Historique des missions » avec un renvoi neutre vers `CHANGELOG.md` et `docs/missions/`, sans « Missions 011 à 182 réalisées » | existence des tags (n'atteste ni clôture ni validation) ; `src/engines/` existe, `src/services/` ne contient que `__init__.py`, `src/plugins/` n'existe pas | `docs/archive/readme/` ; `README.md` |
| Tableau des Missions 001 à 010 | conservé à l'identique | — | `README.md` |
| Section « Architecture actuelle » (récit des Missions 001 à 010) | conservé ; une note la présente comme récit daté | — | `README.md` |
| Section « Releases » (Missions 001 à 010) | conservé ; ajout d'un renvoi neutre | — | `README.md` |
| Badge et prérequis « Python 3.10+ » | **conservés** (écart de couverture, pas une incompatibilité ni un changement de prérequis) ; le statut précise que Python 3.10 n'a pas été exécuté | erratum post-M181 | `README.md` |

## `CLAUDE.md` et `AGENTS.md`

| Partie | Traitement | Destination |
|---|---|---|
| `CLAUDE.md` ligne 3 (« l'historique détaillé vit dans `docs/PROJECT_CONTEXT.md` ») | corrigé : état courant dans `PROJECT_CONTEXT.md`, historique dans les missions, le journal et les archives | `CLAUDE.md` |
| `CLAUDE.md`, workflow de fin de mission | corrigé : état courant synthétique, entrée et index du journal, cohérence incluant `archive/` | `CLAUDE.md` |
| `CLAUDE.md`, section « Organisation de la documentation (règle permanente) » | ajouté | `CLAUDE.md` |
| `AGENTS.md`, description des documents, étape 2 de « Avant toute modification », workflow, règle de modification | corrigé / ajouté (pas de lecture systématique des archives) | `AGENTS.md` |

Toutes les anciennes formulations de `CLAUDE.md` et de `AGENTS.md` relèvent du **régime B** : elles ne sont pas dans `docs/archive/` (les règles permanentes ne s'archivent pas), mais dans l'historique Git.

**Non modifié** : `docs/blueprint/` (la contradiction de `00_VISION.md` sur Kohya_ss est signalée dans le registre, R14) ; `docs/missions/` (hors ajout de `MISSION_183.md`) ; `src/`, `tests/`, `graphify-out/`. `CLAUDE.md` reste muet sur la validation d'une mission documentaire : la règle « après chaque commit, relancer la suite complète » n'est pas modifiée ; l'exception documentaire est propre à la Mission 183 (voir son document).

## Ajouts

`docs/missions/MISSION_183.md` (document de mission), `docs/archive/README.md`, la présente table, `docs/archive/MANIFEST.json`.
