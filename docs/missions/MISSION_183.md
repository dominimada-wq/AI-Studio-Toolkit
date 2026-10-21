# Mission 183 — Consolidation documentaire : état courant synthétique, archives exactes et index des missions

> **STATUT (date de préparation : 2026-10-21) : revue pré-commit acceptée ; commits locaux autorisés ; validation documentaire seulement ; publication non autorisée ; mission non close.** *(Statut antérieur, daté du 2026-10-21, avant l'acceptation de la revue pré-commit, conservé et dépassé : « mission documentaire en cours ; proposition acceptée pour application ; validation documentaire seulement ; revue pré-commit en préparation ; commit et publication non autorisés ; mission non close ».)* La date de préparation est conservée ; les dates de commit et de publication éventuelles seront distinctes et consignées à leur tour. Cette mission est documentaire uniquement ; la suite complète du logiciel n'est pas validée. La validation de cette mission est documentaire (conservation des contenus, exactitude des synthèses, liens et ancres, périmètre, blobs) ; elle **ne modifie aucune réserve de validation du logiciel** : aucun test applicatif n'a été lancé, aucune production ni aucun test n'a été modifié. Aucun identifiant de commit, de tag ou de Release n'est écrit dans ce document : Git fait autorité (voir « Principe de non-auto-référence » dans `docs/PROJECT_CONTEXT.md`).

## 1. Objectif et limites

Rendre les documents courants lisibles et fidèles à leur rôle. Avant cette mission, `docs/PROJECT_CONTEXT.md` (environ 1,06 Mo) et `CHANGELOG.md` (environ 1,15 Mo) empilaient les statuts datés successifs et les récits de toutes les missions, alors que `CLAUDE.md` et `AGENTS.md` décrivent le premier comme un « état consolidé » ; des lignes de plus de 100 000 caractères y existaient. Le `README.md`, arrêté à la Mission 010 pour son statut, ses fonctionnalités, ses tests, son arborescence et sa feuille de route, citait Kohya_ss comme moteur d'entraînement orchestré. **Hors périmètre** : `src/`, `tests/`, `docs/missions/` (hors l'ajout de ce document), `docs/blueprint/` (sa contradiction sur Kohya_ss est signalée, non corrigée), `graphify-out/`, les protections, les tags et les Releases ; L18 et le plantage de Mission 177.

## 2. Décisions de l'architecte

Candidat D de l'audit préparatoire post-Mission 182 retenu ; principe autorisé : les anciens statuts datés n'ont plus à être recopiés indéfiniment dans les documents courants, ils sont déplacés vers une archive référencée, avec conservation exacte et vérifiée ; les réserves encore ouvertes restent visibles dans l'état courant. Erratum sur le candidat E accepté (test émetteur du `Traceback` identifié par les preuves de M182 ; production non exonérée). Décisions de la version 2 :

1. Ce travail est la **Mission 183**, documentaire uniquement ; tag et Release pourront suivre le workflow habituel après acceptation et commit, et ne sont pas autorisés à ce stade.
2. Validation documentaire ; aucun test applicatif.
3. Synthèses corrigées : bilan de la Mission 181 (résultats répartis sur trois manifestes et deux états du code, L04 par réévaluation, pas une campagne intégralement réussie sur un état unique) ; « Environnement des exécutions consignées » ; fonctionnalités présentées comme synthèse issue des missions ; toute mention de vérification par exécution réelle cite sa preuve ou est reformulée en constat statique ; registre des réserves qui distingue réserves établies, limites de couverture et pistes non confirmées.
4. README : renvoi neutre vers l'historique des missions (l'existence d'un tag n'atteste ni la clôture ni la validation) ; correction du statut, des fonctionnalités, des tests et de l'arborescence à partir de sources, avec les limites de validation conservées.
5. `CLAUDE.md` et `AGENTS.md` amendés pour la nouvelle organisation, sans lecture systématique des archives.
6. Dix dernières missions en texte intégral dans le journal courant ; archives existantes immuables ; archivages ultérieurs dans de nouveaux fichiers.
7. Liens internes des documents proposés et liens entrants des autres fichiers du dépôt vérifiés séparément ; ancres nécessaires préservées ou corrections ciblées proposées, sans réécriture générale des documents historiques.

Précisions de l'architecte sur la version 2 (acceptée pour application et pour la préparation de la revue pré-commit ; le découpage en deux commits est accepté en principe, leur création n'est pas autorisée) :

8. **Statut exact** de la mission (ci-dessus) à la place d'une formulation qui anticipait l'existence des commits ; la date réelle de préparation est conservée.
9. **Conservation** : l'affirmation d'une conservation exacte est limitée aux contenus dont elle est effectivement vérifiée (régime A de la table de correspondance) ; pour les règles permanentes et les parties réécrites du README, l'ancien texte se retrouve dans l'historique Git et dans le diff de la mission, non dans `docs/archive/` (régime B).
10. **Maintenance des archives** : les contenus archivés et leurs manifestes de référence sont immuables ; les index de navigation peuvent être actualisés pour référencer de nouvelles archives, sans modifier les archives précédentes.
11. L'absence de test applicatif reste **propre à la Mission 183** ; elle n'est pas transformée en règle permanente.
12. **Création des deux commits locaux autorisée** (2026-10-21), selon le découpage ci-dessous, avec indexation explicite, sans `-a` ni amend, et vérification de chaque commit ; publication (push, tag, Release) non autorisée. Les statuts courants ont été actualisés en conséquence, sans anticiper aucun identifiant de commit.

## 3. Nouvelle organisation (règle permanente, voir `CLAUDE.md`)

`docs/PROJECT_CONTEXT.md` : état courant synthétique (un seul statut courant, architecture relevée par lecture statique, comportement actuel issu des missions, registre unique des réserves ouvertes avec leur nature, dernière mission close, prochaine étape, règles de maintenance, index des anciennes sections). `docs/missions/MISSION_NNN.md` : détails. `CHANGELOG.md` : index de toutes les missions (titre, nom de la section d'origine, liens) et entrées des dix dernières missions. `docs/archive/` : copies exactes en ajout seulement, avec leur README, leur table de correspondance et un manifeste d'empreintes.

## 4. Périmètre et découpage en commits

**Fichiers modifiés (5)** : `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `AGENTS.md`. **Fichiers créés (21)** : `docs/missions/MISSION_183.md` et 20 fichiers sous `docs/archive/` (`README.md`, `CORRESPONDANCE.md`, `MANIFEST.json`, 11 tranches `project_context/PC_01…PC_11`, 5 blocs `changelog/`, 1 fichier `readme/`). **Total : 26 chemins.**

Découpage en **deux commits locaux** (création autorisée le 2026-10-21 ; publication non autorisée), chacun laissant les références cohérentes :

1. **Correction du README** — `README.md` et `docs/archive/readme/README_roadmap_avant_consolidation.md` (2 chemins). Le README ne renvoie qu'à des fichiers qui existent déjà (`CHANGELOG.md` sans nouvelle ancre, `docs/PROJECT_CONTEXT.md`, `docs/missions/`) et au fichier d'archive créé dans le même commit ; l'archive des extraits retirés du README ne renvoie à aucun fichier encore absent.
2. **Organisation en état courant, index et archives** — `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`, `docs/missions/MISSION_183.md` et les 19 autres fichiers de `docs/archive/` (24 chemins au total). La table de correspondance et le README de l'archive décrivent des modifications du README **déjà présentes** (commit 1) ; `PROJECT_CONTEXT.md`, `CLAUDE.md` et `AGENTS.md` renvoient à des archives créées dans ce même commit.

Le tag éventuel de la mission cible le dernier commit de contenu ; ce choix, la Release et la régularisation documentaire suivante sont des décisions ultérieures de l'architecte.

## 5. Contenus : conservés, déplacés, résumés, corrigés

Table complète : [`docs/archive/CORRESPONDANCE.md`](../archive/CORRESPONDANCE.md). Trois régimes de conservation sont distingués : **A** — archive documentaire exacte, vérifiée par empreinte (anciennes sections de `PROJECT_CONTEXT.md`, entrées et Sommaire du journal, deux sections retirées du README) ; **B** — historique Git et diff de la mission, **sans copie dans `docs/archive/`** (parties réécrites du README, anciennes formulations de `CLAUDE.md` et `AGENTS.md`) ; **C** — textes ajoutés (synthèses, registre, index, règles, ce document), qui ne sont pas des copies et que la revue doit lire. L'affirmation de conservation exacte ne vaut que pour le régime A.

| Document | Avant (octets, blob LF) | Après (octets, blob LF) |
|---|---:|---:|
| `docs/PROJECT_CONTEXT.md` | 1 059 844 | 51 820 |
| `CHANGELOG.md` | 1 153 617 | 149 168 |
| `README.md` | 33 191 | 35 223 |
| `CLAUDE.md` | 12 429 | 15 374 |
| `AGENTS.md` | 4 498 | 5 251 |
| `docs/archive/` (20 fichiers) | 0 | 2 222 494 |

Les tailles sont celles des **blobs Git (fins de ligne LF)**. Dans l'arbre de travail Windows (`core.autocrlf=true`), `docs/PROJECT_CONTEXT.md` et `CLAUDE.md` sont en CRLF et pèsent donc un octet de plus par ligne (soit 52 107 et 15 496 octets après application) ; les vérifications d'exactitude portent sur les blobs LF.

## 6. Vérifications documentaires (hors dépôt, aucune exécution applicative)

- **Exactitude des archives** : la concaténation des 11 tranches `PC_NN` redonne le blob d'origine de `PROJECT_CONTEXT.md` (SHA-256 `3f951f28a75e…`) octet pour octet ; les entrées du journal d'origine (183) mises bout à bout dans l'ordre (archives puis entrées courantes, hors entrée ajoutée de la Mission 183) redonnent la zone des entrées d'origine (blob `CHANGELOG.md`, SHA-256 `ac19b1f7aa9f…`) octet pour octet ; les groupes du Sommaire d'origine redonnent le Sommaire d'origine ; les empreintes par entrée du manifeste sont recalculées.
- **Liens internes des documents proposés** : toutes les ancres et tous les liens relatifs des documents modifiés ou créés se résolvent, **dans chaque commit pris isolément** (arbre du commit précédent plus fichiers du commit).
- **Liens entrants** : (a) aucun lien explicite vers une ancre de `CHANGELOG.md`, de `docs/PROJECT_CONTEXT.md` ou de `README.md` n'existe dans les autres fichiers suivis par Git ni dans le corps des Releases GitHub publiées (176 lues en lecture seule) ; (b) les références **textuelles** à des sections de `PROJECT_CONTEXT.md` (« Fonctionnalités terminées », « Problèmes connus / dettes », « Besoins futurs identifiés par l'usage réel », « Dernière mission terminée », « Prochaine mission prévue ») pointent toujours vers un titre de même nom ; (c) les références des documents de mission du type « `CHANGELOG.md` (section "Mission 001 — Blueprint Refactoring") » correspondent à la colonne « nom de la section d'origine » de l'index. Un nouvel index ne répare pas un lien direct vers une ancre supprimée : il n'y en a pas ici, et les documents historiques ne sont pas réécrits.
- **Fichiers appliqués** : les vérifications sont refaites sur les fichiers réellement écrits dans l'arbre de travail (fins de ligne normalisées comme Git le fera), pour chacun des deux états de commit proposés (état de base plus fichiers du commit 1 ; puis plus fichiers du commit 2).
- **Synthèses (contrôle mécanique)** : chaque numéro de mission cité dans les synthèses a un document de mission ; les noms de fichiers du README (arborescence) existent dans les fichiers suivis par Git ; chaque fichier de production de `src/` apparaît dans l'arborescence du README ; le nombre de modules de test cité (66) est celui de `tests/integration/test_*.py`.
- **Hygiène** : aucun chemin personnel, identifiant de session ou de tâche dans les textes nouveaux ; aucune mention d'un identifiant de commit ou de tag de cette mission.
- **Limites de ces vérifications** : elles prouvent la conservation des contenus du régime A, la cohérence des références et l'existence des sources citées ; **une référence à un document de mission prouve l'existence de ce document, pas à elle seule l'exactitude du résumé qui la cite**, et elles ne prouvent pas que chaque comportement résumé est correct à l'exécution. L'exactitude des synthèses (régime C) relève de la relecture ; un tableau des puces de synthèse avec les titres des missions citées est préparé pour cette relecture.

## 7. Réserves et limites de la mission

Les réserves techniques ouvertes sont celles du registre de `docs/PROJECT_CONTEXT.md` (R1 à R19) ; cette mission n'en ferme aucune. Les synthèses de fonctionnalités reprennent les missions sans rejouer leurs vérifications ; l'inventaire d'architecture est un constat statique. `CLAUDE.md` n'est pas modifié sur la règle « après chaque commit, relancer la suite complète » : l'exception documentaire est propre à cette mission et à la décision de l'architecte ci-dessus. La limite d'affichage d'éventuels très gros fichiers Markdown par GitHub n'a pas été vérifiée ; la réduction de taille est indépendante de ce point. Les entrées du journal archivées conservent leurs mots d'origine, y compris des statuts qui étaient courants à leur date.

## 8. Preuves hors dépôt (jamais versionnées)

Version 1 de la proposition (conservée), version 2, diffs, table de correspondance, manifeste d'empreintes, résultats des vérifications, scripts de génération et de vérification, analyse des liens entrants et lecture des Releases : conservés hors dépôt avec leurs empreintes SHA-256. Blobs de base : `docs/PROJECT_CONTEXT.md` `3f951f28a75e…`, `CHANGELOG.md` `ac19b1f7aa9f…`, `README.md` `d2bccb0fbb21…` (SHA-256 des blobs du commit `cd86418dacf3cd6c332dc9259d8d0883c6365774`).

## 9. Suite

Après autorisation, création et vérification des commits : tag et GitHub Release selon le workflow habituel (rédaction en anglais, publication manuelle par l'utilisateur), puis régularisation documentaire de cette mission dans un commit séparé. Aucun candidat de code n'est sélectionné ; l'audit préparatoire post-M182 (candidats B, C, E et étapes de validation) reste la base de la décision suivante. L18 reste non autorisé ; le plantage de Mission 177 reste hors périmètre.
