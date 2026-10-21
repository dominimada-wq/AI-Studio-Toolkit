# docs/archive — archives exactes de la documentation courante

Ce dossier conserve, **sans modification**, des contenus historiques retirés de `docs/PROJECT_CONTEXT.md`, de `CHANGELOG.md` et de `README.md` par la consolidation documentaire (Mission 183), lorsque leur conservation exacte est vérifiée par empreinte.

Ces archives ne décrivent pas l'état courant : elles décrivent l'état **à leur date** (commit de base de la consolidation : `cd86418dacf3cd6c332dc9259d8d0883c6365774`). La [table de correspondance](CORRESPONDANCE.md) indique, partie par partie, ce qui est conservé, déplacé, résumé ou corrigé. L'état courant est dans [`docs/PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) ; l'historique par mission est dans [`docs/missions/`](../missions/) et dans l'index de [`CHANGELOG.md`](../../CHANGELOG.md#index-des-missions).

## Maintenance : ce qui est immuable, ce qui s'actualise

- **Immuables** : les **contenus archivés** (`project_context/`, `changelog/`, `readme/`) et leurs **manifestes de référence** (`MANIFEST.json`, `CORRESPONDANCE.md`). On n'y modifie jamais un fichier existant.
- **Un archivage ultérieur** crée de **nouveaux** fichiers d'archive avec **leur propre manifeste** (par exemple pour les entrées du journal qui sortent des dix dernières missions) ; il ne touche pas aux archives précédentes.
- **Actualisables** : les **index de navigation** — ce `README.md` (pour référencer de nouvelles archives, sans changer les lignes existantes), l'[index des missions](../../CHANGELOG.md#index-des-missions) du journal courant et l'index des anciennes sections de [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) — peuvent être mis à jour pour pointer vers de nouvelles archives.
- **Hors archive** : les règles permanentes (`CLAUDE.md`, `AGENTS.md`) et les parties du `README.md` réécrites (statut, fonctionnalités, tests, mentions de Kohya_ss) **ne sont pas archivées ici** : leurs anciennes formulations se retrouvent dans l'historique Git (commit de base ci-dessus et diff de la mission), pas dans ce dossier.

## Définition de l'exactitude et vérification

- Les sources sont les **blobs Git du commit de base** (fins de ligne LF). `MANIFEST.json` consigne, pour chaque fichier d'archive, ses octets et son empreinte SHA-256, et, pour chaque entrée du journal, sa plage de lignes d'origine et son empreinte.
- **Journal du projet (`project_context/`).** Les fichiers `PC_01` à `PC_11` sont des **tranches contiguës** de l'ancien `docs/PROJECT_CONTEXT.md` : leur concaténation, dans l'ordre des numéros, redonne le document d'origine octet pour octet (les lignes vides de frontière entre deux tranches sont portées en tête du fichier suivant, afin qu'aucun fichier d'archive ne se termine par une ligne vide ; les plages de lignes du tableau ci-dessous sont celles des sections d'origine). Vérification : `cat docs/archive/project_context/PC_*.md | sha256sum` doit donner `3f951f28a75ee97c5b2f1b7e6aa63c795e045b8f51af53252a38a4b9adcc41c6` (empreinte du blob d'origine, `git show cd86418dacf3cd6c332dc9259d8d0883c6365774:docs/PROJECT_CONTEXT.md | sha256sum`).
- **Journal des versions (`changelog/`).** Chaque fichier commence par une introduction ajoutée et par le **Sommaire d'origine**, repris mot pour mot pour ses entrées (ses ancres restent valides dans le fichier), puis contient les entrées **à l'identique**. Les entrées du `CHANGELOG.md` courant (hors l'entrée de la Mission 183, ajoutée par la consolidation) et celles des archives, mises bout à bout dans l'ordre d'origine, redonnent la zone des entrées du journal d'origine octet pour octet ; les Sommaires, mis bout à bout, redonnent le Sommaire d'origine. Les empreintes par entrée sont dans `MANIFEST.json`.
- **README (`readme/`).** Les sections « Roadmap des prochaines missions » et « Structure du dépôt » du `README.md` d'origine, retirées et reproduites à l'identique dans des blocs de code (liens inactifs), précédées d'une courte introduction ajoutée.

## Fichiers

### `project_context/` (source : `docs/PROJECT_CONTEXT.md`, 1059844 octets, SHA-256 `3f951f28a75e…`)

| Fichier | Lignes d'origine | Octets | SHA-256 | Contenu |
|---|---|---|---|---|
| `PC_01_en-tete_et_etat_actuel.md` | 1–28 | 193352 | `217b9290503a…` | En-tête, bandeaux de statut et « État actuel du projet » |
| `PC_02_architecture_actuelle.md` | 29–111 | 35236 | `ca70daf4cfa3…` | « Architecture actuelle » (Domain, Managers, Infrastructure, Engines, UI, EventBus) |
| `PC_03_tests_enumeration_historique.md` | 112–115 | 105569 | `ad74f74c3d0f…` | « Tests » (énumération historique par fichier) |
| `PC_04_fonctionnalites_terminees.md` | 116–151 | 37543 | `6fc46a51e0b4…` | « Fonctionnalités terminées » |
| `PC_05_decisions_fichiers_dependances.md` | 152–209 | 24309 | `38fed199c670…` | « Décisions techniques importantes à retenir », « Fichiers et répertoires structurants », « Dépendances importantes » |
| `PC_06_problemes_connus_dettes.md` | 210–325 | 78218 | `9c7b3cdb881a…` | « Problèmes connus / dettes » |
| `PC_07_besoins_futurs.md` | 326–489 | 147452 | `2327d0121da5…` | « Besoins futurs identifiés par l'usage réel » |
| `PC_08_orientation_et_travaux_en_attente.md` | 490–522 | 40659 | `d2fd388974f2…` | « Orientation architecturale validée » et « Travaux encore en attente » |
| `PC_09_derniere_mission_terminee.md` | 523–654 | 207770 | `aac02945532a…` | « Dernière mission terminée » |
| `PC_10_head_commit_tag.md` | 655–666 | 13449 | `7b9bc1e63277…` | « HEAD du repository », « Dernier commit de mission », « Dernier tag de mission » |
| `PC_11_prochaine_mission_prevue.md` | 667–676 | 176287 | `789a8b44796d…` | « Prochaine mission prévue » |

### `changelog/` (source : `CHANGELOG.md`, 1153617 octets, SHA-256 `ac19b1f7aa9f…`)

| Fichier | Contenu | Octets | SHA-256 |
|---|---|---|---|
| `CHANGELOG_M173-M149.md` | Missions 149 à 173 (26 entrées) | 230829 | `ff8f720c23d2…` |
| `CHANGELOG_M148-M124.md` | Missions 124 à 148 (25 entrées) | 156727 | `fa698a52eed7…` |
| `CHANGELOG_M123-M084.md` | Missions 084 à 123 (40 entrées) | 237784 | `761839c6c567…` |
| `CHANGELOG_M083-M042.md` | Missions 042 à 083 (42 entrées) | 220146 | `473fda75393e…` |
| `CHANGELOG_M041-M001.md` | Missions 001 à 041 (41 entrées) | 221273 | `225c63918e88…` |

Les dix dernières missions (Missions 174 à 183) restent en texte intégral dans [`CHANGELOG.md`](../../CHANGELOG.md). Lorsque de nouvelles missions les en feront sortir, leurs entrées seront archivées dans de **nouveaux** fichiers de ce dossier (par exemple `CHANGELOG_M182-M174.md`), sans modifier les fichiers existants, et l'index de `CHANGELOG.md` sera mis à jour.

### `readme/`

- `README_roadmap_avant_consolidation.md` : sections « Roadmap des prochaines missions » et « Structure du dépôt » du README d'origine.
