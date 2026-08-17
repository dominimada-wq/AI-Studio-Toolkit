# Mission 026 — Character Identity Foundation

Source : audit read-only préalable de priorisation (six candidats comparés — A : Character Identity, B : Multiple Reference Images 1..N, C : Engine/Backend Selection, D : Settings/External Applications, E : exploitation de `comfyui_path`, F : tri de la galerie Images), Candidat A recommandé puis validé par l'architecte, avec décisions architecturales complémentaires explicites (cardinalité, champs, périmètre différé, UI, persistance), puis **audit complémentaire élargi** sur l'organisation conceptuelle de la fiche Character (identité biographique, apparence, personnalité, goûts/centres d'intérêt, informations techniques IA — au-delà du seul usage visuel de génération).

**Révisions post-smoke-test (avant clôture)** : deux smoke tests réels successifs ont révélé des incohérences réelles, chacune auditée en read-only puis corrigée avant re-test :
1. Un Workspace nouvellement créé n'avait encore aucun Character, obligeant un clic "Nouveau personnage" avant de pouvoir remplir la fiche — contraire à l'orientation "1 Workspace = 1 personnage principal". Corrigé par la création/sélection automatique du personnage principal (section 9).
2. Une fois cette création automatique en place, la liste et les boutons multi-personnage ne correspondaient plus à l'UX cible (section 10.1), et un bug fonctionnel empêchait la sauvegarde de la fiche dans le flux le plus simple (section 10.2).

**Troisième smoke test réel : PASS**, voir section 16 pour le détail complet des résultats.

Spécification finale, implémentation terminée conformément aux décisions ci-dessous. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur ici ; les sections "Commit correspondant"/"Tag / release correspondant" seront complétées après la clôture Git réelle.

## 1. Contexte

L'architecte a validé une orientation fonctionnelle : **1 Project/Workspace = 1 personnage IA principal**. `Characters` doit évoluer progressivement vers la fiche d'identité du personnage du projet, plutôt que de rester un gestionnaire de N personnages indépendants. Cette orientation est documentée dans `docs/PROJECT_CONTEXT.md` depuis l'audit Mission 025.

L'audit technique préalable a établi un fait important : le CRUD multi-personnage actuel n'est **pas** un vestige théorique — c'est une fonctionnalité réelle, fonctionnelle et **couverte par 7 tests d'intégration actifs** (`tests/integration/test_character_roundtrip.py`), qui créent explicitement plusieurs personnages ("Aria", "Kai") dans le même Workspace. Toute réécriture de cardinalité non maîtrisée casserait cette suite réelle sans nécessité démontrée pour cette mission.

Un second audit, complémentaire, a élargi la portée conceptuelle de la fiche : le personnage IA n'est pas seulement une identité visuelle destinée à la génération d'images — à terme, il doit porter une identité personnelle et narrative persistante, exploitable pour la génération de prompts cohérents, de scénarios image/vidéo, de légendes/publications sociales, et pour maintenir une personnalité stable dans le temps. La section 3 ci-dessous traite cette organisation conceptuelle en détail — c'est le cœur de cette spécification.

## 2. Objectif

Poser une fondation Domain **propre, additive et durable** pour l'identité du personnage, organisée conceptuellement en plusieurs catégories cohérentes (identité, apparence, personnalité, goûts/centres d'intérêt, informations techniques IA), afin que les capacités futures explicitement identifiées (Character Lock → références d'identité → LoRA d'identité → multi-référence, génération de prompts/scénarios/légendes cohérents avec le personnage) puissent s'appuyer sur `Character` plutôt que de s'accumuler dans `InferencePage`. Cette mission **ne force aucune migration de cardinalité**, **ne retire aucune capacité existante**, et **n'introduit qu'un socle raisonnable** — pas une base de données sociale exhaustive.

## 3. Organisation conceptuelle de la fiche Character

### 3.1 Catégories conceptuelles retenues

Cinq catégories organisent la fiche, reprenant la structure proposée par l'architecte :

1. **Identité** — qui est ce personnage (nom, éléments biographiques).
2. **Apparence / identité visuelle** — à quoi il ressemble, ce qui doit rester visuellement cohérent.
3. **Personnalité** — caractère, tempérament, façon d'être.
4. **Goûts et centres d'intérêt** — ce qu'il aime, ce qui nourrit son contenu.
5. **Informations techniques IA** — ce que les mécanismes de génération/LoRA exploiteront directement.

Ces catégories sont **conceptuelles et documentaires** (organisation de la fiche, de l'audit, de l'UI) — elles ne se traduisent **pas** en cinq sous-dataclasses Domain séparées (voir 3.3).

### 3.2 Principe retenu pour éviter l'accumulation incontrôlée de propriétés

Question centrale posée par l'architecte : comment donner un socle utile aux cinq catégories sans transformer `Character` en accumulation de dizaines de champs "au cas où" ?

**Principe retenu : un champ texte libre consolidé par catégorie qui n'a pas encore de consommateur technique réel, plutôt que des champs scalaires individuels spéculatifs.** Concrètement :

- Une catégorie qui n'a **aucun mécanisme consommateur identifié aujourd'hui** (personnalité, goûts/intérêts, éléments biographiques secondaires) reçoit **un seul champ `str` texte libre**, où l'utilisateur écrit ce qu'il juge pertinent (prose ou liste), plutôt que d'être décomposée en sous-champs individuels (prénom, date de naissance, lieu de naissance, nationalité, caractère, tempérament, qualités, défauts, passions, loisirs, musique...). Ce sont exactement les "dizaines de champs simplement parce qu'ils pourraient servir un jour" que l'architecte a explicitement demandé d'éviter.
- Une catégorie qui a **déjà** un rôle technique identifié et nommé (Character Lock pour la cohérence visuelle en génération, trigger token pour les futurs LoRA) garde son **champ scalaire dédié**, car son nom et son usage sont déjà stables — pas une supposition.
- **Extraire un sous-champ structuré d'un champ texte libre reste toujours possible plus tard**, de façon strictement additive, le jour où un mécanisme réel en a besoin (ex. : si une future mission doit générer automatiquement une publication d'anniversaire, `date_naissance` pourra être extrait de `bio` à ce moment-là — exactement le même principe additif que `checkpoint_name` ajouté à `generate_image()` en Mission 013, ou `denoise` en Mission 024). L'inverse (défaire cinq champs scalaires devenus inutiles ou mal taillés) est toujours plus coûteux que d'étendre un champ texte existant — ce principe minimise donc le risque de mauvais découpage précoce.
- **Aucun mécanisme générique** n'est introduit pour anticiper une extensibilité future (pas de `dict` fourre-tout, pas de système de métadonnées/tags générique, pas de registre de "types de champs") — l'extension future se fait par ajout additif de champs nommés, mission par mission, comme partout ailleurs dans ce Domain.

### 3.3 Domain : structure plate, organisation seulement documentaire/UI

`Character` reste une **dataclass plate** — pas de sous-dataclasses `CharacterIdentity`/`CharacterAppearance`/etc. Justification : les entités imbriquées existantes de `Character` (`Dataset`, `LoRA`, `Prompt`, `Training`) sont des objets avec leur propre identité/cycle de vie/Manager (pattern Character-owned, CLAUDE.md) — les champs d'identité proposés ici sont de simples scalaires, sans identité propre ni CRUD indépendant, exactement comme `ApplicationSettings` regroupe des champs conceptuellement différents (chemins d'installation vs configuration ComfyUI) dans une seule dataclass plate. Introduire des sous-objets uniquement pour un regroupement visuel serait une sur-conception non justifiée par un besoin réel (CLAUDE.md : pas de scaffolding avant besoin réel). Le regroupement en catégories reste visible dans la documentation, les tests, et surtout dans `CharactersPage` (section 8) — la structure de données elle-même n'a pas besoin de le refléter.

### 3.4 Champs proposés — décision IN/OUT par catégorie

| Catégorie | Champ | Statut Mission 026 | Type | Justification |
|---|---|---|---|---|
| Identité | `name` | **IN** (existant, inchangé) | `str` | Déjà présent, flux de création inchangé. |
| Identité | `bio` | **IN (nouveau)** | `str`, défaut `""` | Champ texte libre consolidant prénom/pseudonyme, date/lieu de naissance, ville/pays de résidence, nationalité et autres éléments biographiques — aucun de ces sous-éléments n'a de consommateur technique identifié aujourd'hui ; un seul champ évite cinq scalaires spéculatifs. |
| Apparence / identité visuelle | `description` | **IN** (déjà décidé, section précédente) | `str`, défaut `""` | Description physique. |
| Apparence / identité visuelle | `character_lock` | **IN** (déjà décidé) | `str`, défaut `""` | Cohérence visuelle pour de futures générations — classé ici pour son *contenu* (description de cohérence physique), référencé aussi depuis "Informations techniques IA" (même champ, pas de duplication — voir 3.5). |
| Apparence / identité visuelle | Planche de référence principale, références visage/corps | **OUT (différé)** | — | Dépend du mécanisme multi-référence non choisi (besoin déjà documenté comme non tranché). |
| Personnalité | `personality` | **IN (nouveau)** | `str`, défaut `""` | Champ texte libre consolidant caractère, tempérament, qualités, défauts, style de communication — aucun mécanisme (génération de dialogue, ton de légende) ne consomme individuellement ces sous-éléments aujourd'hui. |
| Goûts et centres d'intérêt | `interests` | **IN (nouveau)** | `str`, défaut `""` | Champ texte libre consolidant passions, loisirs, sport, musique, mode, voyages, nourriture, autres préférences — aucun mécanisme de recherche/filtrage/tags ne justifie une structuration aujourd'hui. |
| Informations techniques IA | `trigger_token` | **IN** (déjà décidé) | `str`, défaut `""` | Nom et usage déjà stables (futurs LoRA d'identité). |
| Informations techniques IA | LoRA d'identité (sélection/association) | **OUT (différé)** | — | Dépend du besoin "sélection de LoRA multi-engine", non résolu. |

**Total des nouveaux champs Domain pour Mission 026 : 5** (`bio`, `description`, `character_lock`, `personality`, `interests`, `trigger_token` — soit exactement 6 en comptant tous les champs listés IN-nouveau/déjà-décidé ci-dessus ; `name` reste inchangé). Volontairement **aucune** décomposition en champs typés (date, liste fermée de nationalités, énumération de traits de personnalité, tags de centres d'intérêt) — tout reste `str` texte libre, cohérent avec `Prompt.text`/`LoRA` `description`-like fields déjà présents dans ce Domain sous cette forme.

### 3.5 Convention de langue — noms Domain (anglais) vs libellés UI (français)

Distinction stricte, appliquée dans cette mission et à conserver pour toute future mission touchant `Character` :

- **Noms internes** (propriétés Domain, sérialisation `project.json`, code Python) : **anglais**, invariants — `name`, `bio`, `description`, `character_lock`, `personality`, `interests`, `trigger_token`. Jamais traduits, ni dans le code ni dans le fichier persisté.
- **Libellés visibles dans `CharactersPage`** : **français**, cohérents avec le reste de l'interface déjà existante (`SettingsPage`, `PromptsPage`, etc., toutes en français à ce jour). Correspondance retenue pour cette mission :

  | Champ Domain | Libellé UI (français) |
  |---|---|
  | `name` | "Nom" |
  | `bio` | "Biographie" |
  | `description` | "Description physique" |
  | `character_lock` | "Character Lock" |
  | `personality` | "Personnalité" |
  | `interests` | "Goûts et centres d'intérêt" |
  | `trigger_token` | "Trigger token" |
  | (bouton) | "Enregistrer l'identité" |

  Titres des 5 sections également en français : "Identité", "Apparence / identité visuelle", "Personnalité", "Goûts et centres d'intérêt", "Informations techniques IA".

- **Aucun système d'internationalisation (i18n) n'est mis en place dans Mission 026** — le besoin futur est déjà documenté dans `docs/PROJECT_CONTEXT.md` (internationalisation/localisation de l'interface, champ `Settings.language` actuellement inerte). Cette séparation stricte noms-Domain/libellés-UI est déterminante pour ce futur besoin : le jour où l'i18n sera implémentée, seules les chaînes françaises codées en dur dans `CharactersPage` (comme dans toute autre Page) devront migrer vers le mécanisme de traduction — **aucune migration du Domain `Character` ni de `project.json` ne sera nécessaire**, les noms de propriétés restant en anglais et invariants depuis cette mission.

### 3.6 Character Lock — classement retenu

Character Lock est **conceptuellement double** (contenu visuel, usage technique IA). Une seule source de vérité : le champ Domain `character_lock`. Documentairement, il est présenté dans la catégorie "Apparence / identité visuelle" (c'est un texte de cohérence physique) et **référencé** (pas dupliqué) dans "Informations techniques IA" comme l'un des leviers que la génération pourra exploiter plus tard. Aucune duplication de stockage.

## 4. État actuel exact du Domain `Character`

```python
@dataclass
class Character:
    character_id: str = ""
    name: str = ""
    datasets: list[Dataset] = field(default_factory=list)
    loras: list[LoRA] = field(default_factory=list)
    prompts: list[Prompt] = field(default_factory=list)
    trainings: list[Training] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
```

`Workspace.characters: list[Character]` (`src/domain/workspace.py`) — une collection réelle, sans limite de cardinalité imposée nulle part dans le code.

`CharacterManager` (`src/managers/character_manager.py`) expose aujourd'hui : `create(name) -> Character`, `select(character_id) -> Character`, `delete(character_id) -> bool`, `characters`/`list_characters()`, `active_character`/`active_character_id` (runtime, jamais persisté, réinitialisé sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED`). Événements publiés : `CHARACTER_CREATED`, `CHARACTER_SELECTED`, `CHARACTER_DELETED`.

`CharactersPage` (`src/ui/pages/characters_page.py`) : `QListWidget` (liste des personnages), boutons "Nouveau personnage"/"Supprimer", sélection déclenchant `character_manager.select()`. Aucun champ d'identité, aucune notion de "fiche".

Cette structure est identique, dans son pattern, à `PromptManager`/`PromptsPage` (Character-owned, `active_prompt_id` runtime) : `PromptManager.update_text(text) -> bool` est déjà le précédent exact d'une méthode d'édition scalaire idempotente **sans événement publié** — modèle direct pour le futur `CharacterManager.update()` de cette mission (section 8).

## 5. Stratégie de compatibilité avec `Workspace.characters`

**Décision retenue : aucune modification de cardinalité dans cette mission.** `Workspace.characters` reste une `list[Character]`, sans changement de format de persistance, sans migration, sans limite imposée par le code. Le CRUD multi-personnage existant (`create`/`select`/`delete`, `CharactersPage`) **reste fonctionnel à l'identique** — les 7 tests de `test_character_roundtrip.py` ne sont ni modifiés ni cassés par cette mission.

L'orientation "1 personnage principal" est traitée comme une **direction produit progressive**, pas comme une contrainte technique à appliquer immédiatement : Mission 026 pose les champs d'identité qu'un futur personnage "principal" utilisera, sans décider aujourd'hui comment/si la cardinalité sera un jour techniquement contrainte. Cette question reste **explicitement ouverte pour un futur audit dédié**.

**Aucun système de migration n'est introduit.** Les nouveaux champs sont additifs et rétrocompatibles (section 7) — un `project.json` existant, avec ou sans plusieurs personnages, se charge sans erreur, chaque personnage recevant simplement les valeurs par défaut (`""`) pour les nouveaux champs.

## 6. Propriétés Domain proposées et valeurs par défaut

| Propriété | Type | Défaut | Catégorie | Rôle |
|---|---|---|---|---|
| `bio` | `str` | `""` | Identité | Éléments biographiques libres (prénom/pseudonyme, naissance, résidence, nationalité...). |
| `description` | `str` | `""` | Apparence | Description / identité physique du personnage. |
| `character_lock` | `str` | `""` | Apparence + Informations techniques IA | Texte de cohérence physique, destiné aux futures générations (non consommé par la génération dans Mission 026). |
| `personality` | `str` | `""` | Personnalité | Caractère, tempérament, qualités, défauts, style de communication. |
| `interests` | `str` | `""` | Goûts et centres d'intérêt | Passions, loisirs, musique, mode, voyages, nourriture, autres préférences. |
| `trigger_token` | `str` | `""` | Informations techniques IA | Token destiné aux futurs LoRA d'identité (non consommé dans Mission 026). |

`name` (déjà existant) reste géré par `CharacterManager.create(name)` à la création (inchangé), **mais devient également éditable après création, via la fiche d'identité** (décision finale de l'architecte) — plutôt que d'introduire un système de renommage séparé, `CharacterManager.update()` (section 8) gagne un paramètre `name` optionnel, cohérent avec le style additif déjà utilisé par `ApplicationSettingsManager.update()`.

Tous les champs (`name` inclus) sont `str`, tous libres (aucune validation de contenu, aucune liste fermée, aucun format imposé), cohérents avec le principe "Aucune validation de contenu métier dans les Managers" (CLAUDE.md). Aucun de ces champs n'est interprété, validé ou consommé par un mécanisme de génération dans cette mission — ce sont des champs de stockage pur, strictement analogues à `Prompt.text` avant qu'un mécanisme ne vienne l'exploiter.

## 7. Sérialisation/désérialisation et rétrocompatibilité

`Character.to_dict()` : ajout additif des six clés.

```python
def to_dict(self) -> dict:
    return {
        "character_id": self.character_id,
        "name": self.name,
        "bio": self.bio,
        "description": self.description,
        "character_lock": self.character_lock,
        "personality": self.personality,
        "interests": self.interests,
        "trigger_token": self.trigger_token,
        "datasets": [...],
        "loras": [...],
        "prompts": [...],
        "trainings": [...],
        "history": self.history,
    }
```

`Character.from_dict()` : lecture défensive standard pour un scalaire (CLAUDE.md — `data.get(key, default)`), aucune garde `isinstance` nécessaire (pas de structure imbriquée) :

```python
bio=data.get("bio", ""),
description=data.get("description", ""),
character_lock=data.get("character_lock", ""),
personality=data.get("personality", ""),
interests=data.get("interests", ""),
trigger_token=data.get("trigger_token", ""),
```

**Rétrocompatibilité** : un `project.json` écrit avant cette mission ne contient aucune de ces six clés — `from_dict()` les initialise alors à `""`, exactement comme le fait déjà `history=data.get("history", [])` pour un champ historique absent. Un test de compatibilité legacy dédié sera ajouté (section 12), symétrique à celui déjà existant pour `ApplicationSettings`.

Pas de commentaire de numéro de mission dans le code Domain lui-même (`character.py`), conformément à la règle permanente CLAUDE.md — la justification vit dans ce document et dans `CHANGELOG.md`.

## 8. Comportement de `CharacterManager`

Nouvelle méthode additive, idempotente, suivant exactement le contrat déjà établi par `PromptManager.update_text()`/`ApplicationSettingsManager.update()` :

```python
def update(
    self,
    character_id: str,
    name: Optional[str] = None,
    bio: Optional[str] = None,
    description: Optional[str] = None,
    character_lock: Optional[str] = None,
    personality: Optional[str] = None,
    interests: Optional[str] = None,
    trigger_token: Optional[str] = None,
) -> bool:
```

- Retourne `False` sans `save()` ni effet si `character_id` est introuvable, ou si tous les champs fournis sont déjà identiques à la valeur actuelle (idempotence stricte — chaîne vide `""` est une valeur légitime, distincte de `None`/non fourni).
- Modifie l'objet `Character` trouvé en place, appelle `self._workspace_manager.save()` si un changement réel a eu lieu.
- **Aucun événement publié** — même choix que `PromptManager.update_text()`/`DatasetManager.add_images()` : une mutation de contenu scalaire n'a historiquement jamais publié d'événement dans ce projet. `CharactersPage` étant la seule et unique consommatrice de ces champs dans cette mission, aucun rafraîchissement inter-Page n'est nécessaire.
- `name` est désormais un paramètre de cette méthode (décision finale de l'architecte) — un seul mécanisme de mise à jour gère à la fois le renommage et les champs d'identité, évitant un système de renommage séparé. `list_widget`/`CharactersPage.update_characters()` doivent refléter un nom modifié après sauvegarde de la fiche, exactement comme pour tout autre champ.

`create()`/`select()`/`delete()` restent strictement inchangés.

## 9. Comportement — nouveau Workspace sans Character (révisé après smoke test)

### 9.1 Constat du smoke test

Le premier smoke test a montré qu'un Workspace nouvellement créé n'avait aucun Character — l'utilisateur devait cliquer "Nouveau personnage" avant de pouvoir remplir la fiche d'identité, ce qui ne correspond pas à l'esprit de "1 Workspace = 1 personnage principal". Comportement cible : créer un projet → ouvrir Characters → la fiche existe déjà → `Nom` déjà renseigné avec le nom du projet.

### 9.2 Source vérifiée du nom du projet

Vérification du modèle réel plutôt que supposition : **`Workspace.name`** (champ Domain déjà existant et déjà persisté) est la bonne source — `WorkspaceManager.create(folder)` fait déjà `Workspace(name=folder.name, root=folder)`, et `NewProjectDialog` (Mission 016) construit le dossier créé exactement à partir du nom saisi par l'utilisateur (`target_path = parent / name`). `workspace.name` est donc déjà, de façon fiable, "le nom du projet" — pas une redérivation supplémentaire depuis `root`/le chemin (`root` est d'ailleurs runtime-only, jamais persisté, donc moins fiable que `name`).

### 9.3 Stratégies comparées

- **Option 1 — création dans `WorkspaceManager.create()`.** Rejetée : `WorkspaceManager` n'a et ne doit pas avoir de dépendance vers `Character`/`CharacterManager` — l'inverse existe déjà (`CharacterManager` dépend de `WorkspaceManager`) ; introduire le sens contraire violerait le Dependency Rule sans précédent dans ce projet.
- **Option 2 — lazy creation à l'ouverture de `CharactersPage`.** Rejetée : introduirait un nouveau pattern (écriture disque déclenchée par la simple ouverture d'une Page) jamais utilisé ailleurs, et la garantie "il existe toujours un personnage" deviendrait conditionnelle à la navigation UI.
- **Option 3 — `CharacterManager` réagit à `WORKSPACE_CREATED` (retenue).** `CharacterManager` s'abonne déjà à `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED` pour réinitialiser `active_character_id`. Un second handler dédié, abonné uniquement à `WORKSPACE_CREATED`, vérifie `workspace.characters` vide puis appelle `self.create(workspace.name)` (méthode déjà existante, aucune duplication) suivi de `self.select(...)`. Aucune nouvelle dépendance : `CharacterManager` lit déjà `self._workspace_manager.current_workspace` directement. `EventBus.publish()` est synchrone (vérifié dans `src/core/event_bus.py`) — au retour de `WorkspaceManager.create()`, le personnage principal existe déjà, est sélectionné et sauvegardé.

### 9.4 Décisions validées par l'architecte

1. **Création automatique sur `WORKSPACE_CREATED`** : si `workspace.characters` est vide au moment de l'événement, `CharacterManager` crée un Character via `create(workspace.name)` puis le sélectionne automatiquement (`select(...)`), afin que `CharactersPage` affiche immédiatement sa fiche. Le nom du Character reste ensuite librement modifiable depuis la fiche (section 8) — un renommage ne modifie jamais `Workspace.name` ni le dossier du projet (aucun couplage entre les deux ; `CharacterManager.update()` ne touche jamais `Workspace`).
2. **Aucune création automatique sur `WORKSPACE_OPENED`.** Impossible aujourd'hui de distinguer proprement un Workspace legacy qui n'a jamais eu de Character d'un Workspace où l'utilisateur a volontairement supprimé tous ses personnages via le CRUD encore disponible — auto-créer sur ouverture annulerait silencieusement ce second cas. Point réévalué lorsque la cardinalité produit deviendra réellement contraignante et que le devenir de "Nouveau personnage"/"Supprimer"/liste multi-personnage sera tranché.
3. **Aucune contrainte de cardinalité `max=1`.** La création automatique est une valeur par défaut de confort, pas une limite Domain — le CRUD multi-personnage reste pleinement fonctionnel, aucune migration introduite.
4. **Impact sur les tests existants explicitement accepté.** L'hypothèse "nouveau Workspace → zéro Character", vraie avant cette révision, devient volontairement fausse — un changement de contrat produit assumé. Périmètre réel identifié avant modification (pas une simple correction mécanique) : les 7 tests pré-existants de `test_character_roundtrip.py`, plusieurs des tests ajoutés dans la première passe de cette mission, **et** un motif identique (`character_manager_2.characters[0]` supposé être l'unique personnage manuellement créé après réouverture) trouvé dans `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py`. Règle d'adaptation : jamais de correction par simple décalage d'index — recherche explicite par `character_id` ou par nom lorsque c'est l'intention fonctionnelle réelle du test ; aucune assertion supprimée uniquement pour faire passer la suite ; les états "aucun Character sélectionné" nécessaires à certains tests sont reconstruits via un cycle de vie réel (fermeture/réouverture — la sélection ne survit jamais à un redémarrage), jamais supposés acquis juste après `create()`.

### 9.5 Règle produit — `Workspace.name` vs `Character.name` (divergence acceptée, confirmée par le smoke test)

Le smoke test final a explicitement observé et validé le comportement suivant, désormais documenté comme règle produit permanente pour ce périmètre :

- `Workspace.name` = nom du projet/conteneur (le dossier physique du Workspace).
- `Character.name` = identité du personnage.
- À la création d'un nouveau projet, `Character.name` (du personnage principal auto-créé) est **initialisé** depuis `Workspace.name` — c'est la seule synchronisation qui existe (section 9.4, décision 1).
- **Au-delà de cette initialisation, les deux valeurs peuvent librement diverger.** Renommer le Character via la fiche d'identité (`CharacterManager.update(name=...)`) ne modifie jamais `Workspace.name`, ni le dossier du projet sur disque — aucun couplage, aucune synchronisation ultérieure dans un sens ou dans l'autre. Vérifié explicitement par `test_renaming_via_update_never_changes_workspace_name` et confirmé en conditions réelles par le smoke test (renommage du personnage persistant, nom du projet/dossier inchangé).
- Ce comportement est **intentionnel, pas une limitation** : un personnage peut légitimement porter un nom différent du projet qui l'héberge (ex. surnom, nom de scène) sans jamais renommer le projet lui-même — renommer un dossier de projet reste une opération distincte, hors périmètre de cette mission et de `CharacterManager`.

## 10. Évolution minimale de `CharactersPage` — une vraie fiche en sections

Aucun retrait de la liste/CRUD existante — `list_widget`, `new_button`, `delete_button` restent identiques (les 7 tests existants continuent de passer sans modification de leurs assertions sur ces éléments).

**Organisation retenue pour la fiche** : réutilisation du pattern de sectionnement **déjà existant dans `SettingsPage`** (titre de section en `QLabel` gras + `QFormLayout` par section, empilés verticalement) — cohérent avec le style déjà établi dans ce projet, plutôt que d'introduire un nouveau paradigme UI (ex. `QTabWidget`, jamais utilisé ailleurs dans le codebase actuel). Quatre sections visuellement séparées sous la liste de personnages (Character Lock et trigger token regroupés dans leurs catégories respectives, sans duplication) :

- **Identité** : `name_edit` (`QLineEdit`, renommage), `bio_edit` (`QTextEdit`).
- **Apparence** : `description_edit` (`QTextEdit`), `character_lock_edit` (`QTextEdit`).
- **Personnalité** : `personality_edit` (`QTextEdit`).
- **Goûts et centres d'intérêt** : `interests_edit` (`QTextEdit`).
- **Informations techniques IA** : `trigger_token_edit` (`QLineEdit`, token court, une ligne).

Un unique bouton `save_identity_button` (`QPushButton("Enregistrer l'identité")`) pour l'ensemble de la fiche, `name` inclus — cohérent avec le pattern déjà utilisé (`PromptsPage`/`SettingsPage` : un bouton par groupe logique de champs, pas un bouton par champ). Connecté à `save_identity()` :
  - Si `character_manager.active_character_id is None` → `QMessageBox.warning` ("Aucun personnage sélectionné" / "Sélectionnez un personnage avant d'enregistrer son identité."), même convention que `PromptsPage.save_text()`.
  - Sinon, appelle `character_manager.update(active_character_id, name=..., bio=..., description=..., character_lock=..., personality=..., interests=..., trigger_token=...)`.

`update_characters()` (déjà existante) est étendue : en plus de repeupler `list_widget`, elle peuple aussi `name_edit` et les six champs d'identité à partir du personnage actif retrouvé dans `list_characters()`, et les vide si aucun personnage n'est actif — même principe que `text_edit.setPlainText(active_text)` dans `PromptsPage.update_prompts()`. Un renommage sauvegardé via la fiche doit se refléter dans `list_widget` (le libellé de l'item correspondant), exactement comme le nom l'est déjà à la création.

`QInputDialog` reste le point d'entrée pour la **création** d'un personnage (nom initial) — inchangé. Le renommage passe désormais exclusivement par la fiche/`update()`, aucun mécanisme de renommage séparé n'est ajouté. Aucune amélioration du reste du CRUD multi-personnage (pas de réorganisation de la liste, pas de tri).

### 10.1 Révision UX (après confirmation de la cible produit) — masquage des contrôles multi-personnage

Avec la création/sélection automatique du personnage principal (section 9), la liste et les boutons "Nouveau personnage"/"Supprimer" ne correspondent plus à l'UX cible ("Characters = fiche d'identité du personnage du projet", jamais une liste à gérer). Décision retenue : **masquage (`setVisible(False)`), jamais retrait** de `list_widget`/`new_button`/`delete_button` — ils restent instanciés, câblés et pleinement fonctionnels par programme (`addItem`, `currentItem`, `.click()` continueraient de fonctionner), seule leur présentation à l'utilisateur disparaît. C'est le choix le plus sûr : `CharacterManager.create()`/`delete()`, `Workspace.characters: list[Character]` et la sérialisation multi-Character restent des mécanismes internes transitoires intacts, et les 7 tests historiques multi-personnage (`CharacterRoundTripTest`) continuent de prouver cette compatibilité **sans aucune modification**, puisqu'un widget masqué reste entièrement opérationnel côté test (`isHidden()` reflète l'appel explicite à `setVisible(False)`, indépendamment du fait que la fenêtre de plus haut niveau soit affichée ou non dans les tests headless).

Comportement UX résultant : à l'ouverture de `CharactersPage` sur un Workspace nouvellement créé, seule la fiche du personnage principal (déjà auto-créé et auto-sélectionné, section 9) est visible — aucune liste, aucun bouton de création/suppression.

### 10.2 Correction post-smoke-test — `save_identity()` ne doit plus dépendre de `active_character_id`

**Symptôme rapporté** : fiche correctement peuplée (`Nom` renseigné) à l'ouverture d'un nouveau projet, mais clic sur "Enregistrer l'identité" → `QMessageBox` "Aucun personnage sélectionné".

**Diagnostic (read-only, avant toute correction)** : l'ordre synchrone réel de `WORKSPACE_CREATED` a été vérifié précisément (abonnements de `CharacterManager` dans l'ordre d'enregistrement : `_on_workspace_changed` puis `_ensure_default_character`, ce dernier appelant `create()` → `save()` → `WORKSPACE_SAVED` imbriqué → `select()` → `CHARACTER_SELECTED`) — reproduit à l'identique via trois niveaux de simulation (wiring minimal, `MainWindow` réel construit directement, `MainWindow` réel avec boucle d'événements Qt complète + navigation sidebar + clic réel sur le bouton) : dans les trois cas, `active_character_id` est correctement positionné et `save_identity()` réussit. **La séquence de création elle-même n'a pas pu être mise en défaut par simulation automatisée.** En revanche, forcer explicitement `character_manager.active_character_id = None` alors qu'un unique Character existe toujours reproduit exactement le message rapporté — confirmant que le mécanisme de la panne (retour à `None` de `active_character_id` pendant que le Character persiste) est réel et suffisant pour expliquer le symptôme, quel qu'en soit le déclencheur exact dans la session réelle de l'architecte.

**Cause architecturale** : `save_identity()` dépendait strictement de `active_character_id` — un mécanisme conçu pour la sélection dans une liste multi-personnage aujourd'hui masquée. Aucun événement ni aucune interaction ne peut plus faire remonter une nouvelle valeur à `active_character_id` une fois que la liste n'est plus utilisable par l'utilisateur ; toute remise à `None` (fragilité d'ordonnancement non identifiée avec certitude, ou future régression) devient alors irréversible du point de vue de l'utilisateur.

**Correction retenue** : nouvelle propriété `CharacterManager.principal_character` (+ `principal_character_id`, variante id pour la couche Presentation) — retourne `active_character` s'il est valide, sinon se rabat sur `characters[0]` (le personnage principal est toujours créé en premier, décision 9.4). `CharactersPage.save_identity()` et `update_characters()` (partie peuplement de la fiche uniquement — le surlignage de `list_widget` continue d'utiliser `active_character_id` pour ne rien changer au mécanisme historique) utilisent désormais `principal_character_id`. Le message d'avertissement ne peut plus apparaître que si le Workspace n'a réellement **aucun** Character (ex. après suppression volontaire du seul personnage via le CRUD interne encore disponible) — jamais simplement parce que la sélection interne a été perdue.

**Compatibilité préservée** : `active_character_id`/`select()`/`active_character` strictement inchangés — tous les tests multi-personnage historiques, qui appellent explicitement `select()` avant toute vérification, restent prioritaires sur le repli et ne sont pas affectés.

## 11. Périmètre IN

- `Character.bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token` (`str`, défaut `""`), `to_dict()`/`from_dict()` additifs.
- `CharacterManager.update(character_id, name=None, bio=None, description=None, character_lock=None, personality=None, interests=None, trigger_token=None) -> bool`, idempotent, sans événement — gère aussi bien le renommage que les champs d'identité.
- `CharactersPage` : fiche en 5 sections visuellement séparées (Identité — nom inclus, Apparence, Personnalité, Goûts et centres d'intérêt, Informations techniques IA), un bouton "Enregistrer l'identité", peuplée/vidée par `update_characters()` selon le personnage actif.
- Persistance réelle via `WorkspaceManager.save()` déjà existant — round-trip fermeture/réouverture prouvé par test, `name` modifié inclus.
- Rétrocompatibilité avec un `project.json` sans ces champs.
- **Création et sélection automatiques du Character principal sur `WORKSPACE_CREATED` si `workspace.characters` est vide**, nommé depuis `workspace.name` (section 9).
- Adaptation précise (recherche explicite par `character_id`/nom, jamais par index) des tests existants impactés par ce nouveau contrat (section 13).
- Tests Domain/Manager/UI/persistance (section 13).
- Smoke test manuel réel (section 16).

## 12. Périmètre OUT (explicitement différé, à documenter dans `docs/PROJECT_CONTEXT.md` à la clôture)

Sélection/association de LoRA d'identité ; planche de référence principale ; références visage/corps ; références vêtement/décor/pose ; multi-référence 1..N ; IP-Adapter/ControlNet ; sélection moteur/backend ; modification des workflows ComfyUI (`comfyui_workflows.py`) ; refonte générale de Settings ; toute contrainte de cardinalité `max=1` sur `Workspace.characters` ; **création automatique sur `WORKSPACE_OPENED`** (uniquement sur `WORKSPACE_CREATED`, décision explicite section 9.4) ; réorganisation/tri de la liste de personnages ; toute consommation réelle de `character_lock`/`trigger_token`/`bio`/`personality`/`interests` par un mécanisme de génération, de prompt, de scénario ou de légende sociale (tous ces champs restent du stockage pur dans cette mission) ; décomposition de `bio`/`personality`/`interests` en sous-champs structurés/typés (date de naissance typée, listes fermées, tags) — à réévaluer uniquement si un futur mécanisme réel en a besoin individuellement ; toute fonctionnalité conversationnelle ou d'assistance à la création de contenu.

## 13. Stratégie de tests

**Recherche préalable de mocks à signature obsolète** : `Character.__init__`/`to_dict()`/`from_dict()` gagnent des champs additionnels à défaut non-`None` — tout mock/fixture construisant un `Character`/dict de test avec des assertions exhaustives sur l'ensemble des clés devra être recherché et adapté avant exécution, même procédure que Missions 022/023/024/025.

- `tests/integration/test_character_roundtrip.py` (existant, étendu, jamais cassé) :
  - nouveaux champs présents avec leur défaut `""` à la création (`create()` n'est pas modifié) ;
  - `update()` : idempotence (valeurs identiques → `False`, aucun `save()`) ; changement réel sur un ou plusieurs champs → `True`, `save()` appelé ; `character_id` introuvable → `False` ; chaîne vide traitée comme valeur légitime ; un sous-ensemble de champs fournis ne touche pas les autres ;
  - round-trip réel fermeture/réouverture : les six champs sont bien persistés et restaurés à l'identique ;
  - **rétrocompatibilité legacy** : un fichier `project.json` écrit sans ces six clés (format pré-Mission-026) se charge sans exception, avec `""` pour chacun des champs — nouveau test dédié, symétrique à `test_manager_loads_legacy_settings_file_without_comfyui_url_or_checkpoint_fields` (`test_application_settings_roundtrip.py`) ;
  - `CharactersPage` réelle : les 5 sections existent et sont vides/désactivées sans personnage actif ; peuplées correctement à la sélection ; "Enregistrer l'identité" sans personnage sélectionné → `QMessageBox.warning`, aucun appel à `update()` ; saisie dans plusieurs sections puis "Enregistrer" → `CharacterManager.update()` reçoit exactement les valeurs saisies ; changement de personnage sélectionné → toutes les sections reflètent le nouveau personnage (pas de fuite de valeurs entre deux personnages) ;
  - confirmation explicite que les 7 tests existants (multi-personnage : création, sélection, suppression, cascade Dataset/Training, événements, non-duplication d'abonnements) restent verts **sans modification de leurs assertions**.
- Test architectural anti-couplage : aucune référence à `bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token` dans `generation_manager.py`/`comfyui_engine.py`/`inference_page.py`/`comfyui_workflows.py` — sur le modèle du test anti-`"denoise"` de Mission 024.

Nombre exact de tests final à confirmer après implémentation (370 + N nouveaux), comme pour chaque mission précédente.

### Résultats réels

Recherche préalable exécutée avant chaque lancement Qt : aucun mock/fixture à signature exhaustive cassée trouvé hors `test_character_roundtrip.py` lui-même (7 tests pré-existants adaptés pour intégrer le personnage principal auto-créé, jamais par décalage d'index — recherche explicite par `character_id`/nom) ; motif identique trouvé et corrigé de la même façon dans `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py` (2 occurrences chacun) ; découverte complémentaire du même compteur d'abonnés `WORKSPACE_CREATED` obsolète (+1, nouvel abonnement `CharacterManager._ensure_default_character`) dans `test_model_roundtrip.py`/`test_workflow_roundtrip.py`, hors périmètre initialement balisé mais signalé et corrigé par transparence. **24 tests adaptés au total**, aucune assertion supprimée — chaque adaptation étend, remplace un accès fragile par une recherche explicite, ou reconstruit honnêtement un état réel (fermeture/réouverture) plutôt que de l'affaiblir.

**32 tests nets nouveaux, répartis sur les quatre passes de cette mission** :
- Passe 1 (fondation d'identité) — **21** : 4 Domain (`CharacterIdentityDomainTest`) + 9 Manager (`CharacterManagerUpdateTest`) + 7 UI (`CharactersPageIdentityFicheTest`) + 1 architectural.
- Passe 2 (révision auto-création) — **8** : 7 Manager (`CharacterManagerAutoCreateDefaultTest`) + 1 UI (fiche immédiatement peuplée sans clic).
- Passe 3 (révision UX, masquage des contrôles) — **1** : `test_multi_character_controls_are_hidden_from_ui`.
- Passe 4 (correction `principal_character_id` post-smoke-test) — **2** : `test_save_identity_succeeds_on_fresh_workspace_without_any_manual_selection`, `test_save_identity_succeeds_even_if_active_character_id_was_lost` (ce dernier confirmé **FAIL avant correction**, **PASS après**). Deux tests supplémentaires ont été **renommés** dans cette même passe pour refléter le nouveau contrat (`test_identity_panel_cleared_when_no_character_exists_at_all`, `test_save_identity_without_any_character_shows_warning`) — sans effet sur le compte net.

21 + 8 + 1 + 2 = **32**.

**Suite complète, exécution unique : 402/402** (370 précédents + 32 nets nouveaux).

## 14. Risques de régression

- **Dérive de signature de mock/fixture** (voir section 13) — recherche préalable obligatoire avant tout lancement Qt.
- **Confusion cardinalité** : risque qu'une future mission interprète à tort cette fondation comme une contrainte technique déjà appliquée — atténué en documentant explicitement, dans `docs/PROJECT_CONTEXT.md` à la clôture, que la cardinalité N reste techniquement inchangée.
- **Sur-interprétation des champs texte libres** : risque qu'une future mission tente de "parser" `bio`/`personality`/`interests` par heuristique plutôt que d'attendre un vrai besoin structuré — à rappeler explicitement dans la documentation de clôture (section 3.2 de ce document fait référence).
- **Couplage accidentel** : veiller à ce qu'aucun code de génération ne lise ces nouveaux champs dans cette mission — couvert par le test architectural dédié (section 13).
- **Perte de valeurs lors d'un changement de personnage sélectionné dans l'UI** si `update_characters()` ne repeuple pas correctement les cinq sections — couvert explicitement par test dédié (section 13).
- **UI dense** : 6 champs texte répartis en 5 sections dans une seule Page peut devenir visuellement chargé — risque UX mineur, atténué par le sectionnement (QLabel gras + QFormLayout par section, cohérent avec `SettingsPage`), à valider concrètement lors du smoke test.

## 15. Critères d'acceptation

- Suite de tests complète verte, nombre exact confirmé.
- `git diff --stat` confirmant exactement le périmètre de fichiers de cette section (à lister précisément dans le rapport d'implémentation).
- Les 7 tests existants de `test_character_roundtrip.py` passent sans modification de leurs assertions substantielles.
- Un `project.json` pré-Mission-026 se charge sans exception, avec les six nouveaux champs à `""`.
- `CharacterManager.update()` strictement idempotent, jamais d'événement publié.
- Aucune référence à `bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token` dans le code de génération.
- Les 5 sections de la fiche sont visuellement distinctes dans `CharactersPage` (vérifié par test Qt réel, pas seulement par lecture de code).
- Smoke test manuel réel réalisé et documenté (section 16).

### Résultats réels

Tous les critères ci-dessus sont satisfaits : 402/402 tests verts ; les 7 tests historiques `test_character_roundtrip.py` passent sans modification de leurs assertions substantielles (adaptations de comptage/liste uniquement, jamais de suppression) ; `project.json` pré-Mission-026 chargé sans exception (test dédié + confirmé par la rétrocompatibilité générale) ; `CharacterManager.update()` idempotent, jamais d'événement publié (test dédié) ; aucune référence aux nouveaux champs dans le code de génération (test architectural) ; 5 sections visuellement distinctes confirmées par test Qt réel **et** par le smoke test manuel (section 16). Critère supplémentaire ajouté après le second smoke test et satisfait : `save_identity()` ne dépend plus de `active_character_id` pour fonctionner dans le flux nominal (section 10.2).

## 16. Plan du smoke test manuel réel

**Plan initial (obsolète)** : le plan d'origine ci-dessous supposait une sélection manuelle du personnage dans une liste visible ("Sélectionner le personnage..."). Devenu obsolète après les révisions des sections 9 et 10 (personnage principal auto-créé/sélectionné, liste masquée) — conservé uniquement pour mémoire de l'historique de cette spécification, remplacé par le plan final ci-dessous, réellement exécuté par l'architecte.

*Plan initial, non exécuté tel quel :* ouvrir/créer un Workspace, créer un personnage ; sélectionner le personnage, remplir les 5 sections, "Enregistrer l'identité" ; vérifier le sectionnement visuel ; changer de sélection et vérifier l'absence de fuite ; resélectionner le premier personnage ; fermer/rouvrir et vérifier la persistance ; test de rétrocompatibilité.

**Plan final réellement exécuté** (trois passes de smoke test réel, la dernière concluante) :

1. Créer un nouveau projet (ex. `Lauraya`).
2. Ouvrir Characters — vérifier que la fiche du personnage principal est **déjà** active, sans aucun clic ni sélection manuelle, et qu'aucune liste ni bouton "Nouveau personnage"/"Supprimer" n'est visible.
3. Vérifier `Nom = <nom du projet>` dès l'ouverture.
4. Remplir les 5 sections (Biographie, Description physique, Character Lock, Personnalité, Goûts et centres d'intérêt, Trigger token) et éventuellement renommer le personnage.
5. Cliquer sur "Enregistrer l'identité" — vérifier l'absence de toute `QMessageBox` d'erreur.
6. Répéter une sauvegarde dans la même session (modifier un champ, enregistrer à nouveau).
7. Fermer puis rouvrir le projet — vérifier que toute la fiche (nom renommé inclus) est restaurée à l'identique.
8. Vérifier que le nom du projet/dossier n'a pas changé malgré le renommage du personnage (section 9.5).

### Résultats réels

**Trois smoke tests réels successifs**, chacun ayant révélé une incohérence corrigée avant le suivant (voir sections 9/10.1/10.2 pour le détail de chaque révision) :
- 1er smoke test : **FAIL** — aucun personnage à la création, clic "Nouveau personnage" requis (incohérence UX à l'origine de la révision auto-création, section 9).
- 2e smoke test : **FAIL** — fiche correctement peuplée mais sauvegarde impossible (`QMessageBox` "Aucun personnage sélectionné"), à l'origine de la correction `principal_character_id` (section 10.2).
- 3e smoke test (plan final ci-dessus) : **PASS**, réalisé par l'architecte. Résultats observés : nouveau projet créé ; Character principal auto-créé ; `Nom` initial = nom du projet ; aucune liste multi-personnage visible ; aucun bouton "Nouveau personnage"/"Supprimer" visible ; fiche directement utilisable ; sauvegarde réussie ; sauvegardes répétées dans la même session réussies ; fermeture/réouverture avec données restaurées ; renommage du Character persistant ; aucune `QMessageBox` d'erreur ; nom du Workspace/projet inchangé malgré le renommage du personnage (section 9.5) ; suite automatisée 402/402.

## 17. Confirmation — aucune fonctionnalité hors périmètre

Aucune sélection de LoRA, aucune planche de référence, aucune référence visage/corps/vêtement/décor/pose, aucun multi-référence, aucun IP-Adapter/ControlNet, aucune sélection moteur/backend, aucune modification des workflows ComfyUI, aucune refonte de Settings, aucune contrainte de cardinalité **`max=1`** sur `Workspace.characters` (le CRUD interne multi-personnage reste pleinement fonctionnel, seulement masqué de l'UI), aucun renommage automatique du Workspace/dossier lorsque le Character est renommé (section 9.5), aucune consommation réelle de `bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token` par la génération, les prompts, les scénarios ou les publications sociales, aucune décomposition structurée des champs texte libres, aucune fonctionnalité conversationnelle. **Correction apportée en cours de mission, hors périmètre initial mais explicitement validée par l'architecte** : création/sélection automatique du personnage principal sur `WORKSPACE_CREATED` (section 9) et masquage des contrôles multi-personnage dans `CharactersPage` (section 10.1) — nécessaires pour que la fondation d'identité posée soit réellement utilisable selon l'orientation produit "1 Workspace = 1 personnage principal".

## Commit correspondant

`4430465a843fad609d924adf4c8f22f77caf1304` — `feat: add character identity profile`.

## Tag / release correspondant

Tag en cours de création (`v0.2-mission026`) — voir régularisation documentaire ultérieure pour confirmation de la cible exacte. GitHub Release non encore publiée.

## État final

**Implémentation, tests automatisés (402/402) et smoke test manuel réel validés — PASS.** `CharactersPage` représente désormais directement la fiche d'identité du personnage principal du Workspace : personnage créé et sélectionné automatiquement à la création d'un projet (nommé depuis `Workspace.name`), fiche en 5 sections immédiatement utilisable sans aucun clic préalable, liste et boutons multi-personnage masqués de l'UI (compatibilité interne `CharacterManager.create()`/`delete()`/`Workspace.characters: list[Character]` intégralement préservée, provisoire, en attente d'une future décision de cardinalité), sauvegarde robuste (`principal_character_id`) indépendante du mécanisme historique de sélection. `Workspace.name` et `Character.name` peuvent diverger après l'initialisation, sans aucun couplage automatique dans un sens ou dans l'autre — confirmé par test et par le smoke test réel. **Commit fonctionnel effectué** (`4430465a843fad609d924adf4c8f22f77caf1304`) ; tag et push en cours de clôture Git contrôlée.
