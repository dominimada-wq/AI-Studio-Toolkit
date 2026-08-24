# Mission 058 — Dead Code and Stale Documentation Cleanup (Round 2)

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat validé par l'architecte le 2026-08-24, avec arbitrage explicite confirmant le retrait d'`EventBus.unsubscribe()`. Implémentation réalisée conformément au contrat, aucun élargissement de périmètre, 967/967 tests automatisés verts (décompte inchangé — aucun test ajouté ni retiré, conformément au contrat), `git diff --check` propre, cycle Qt réel `TrainingPage.create_training()` exécuté manuellement (rapporté en section 10). Validation technique accordée par l'architecte le 2026-08-24. Commit fonctionnel, tag et GitHub Release tous créés et publiés.

## 1. Contexte

Un audit factuel frais du dépôt, réalisé après la clôture complète de Mission 057, a identifié quatre éléments supplémentaires de code mort ou de documentation obsolète — distincts des trois éléments déjà traités par Mission 057 (`Workspace.datasets`/`.loras`/`.training`, `Character.history`, `BasePage`) :

1. **`EventBus.unsubscribe()`** (`src/core/event_bus.py:44-46`) — méthode publique définie mais **jamais appelée nulle part** dans `src/` ni `tests/` (confirmé par grep exhaustif sur tout le dépôt — seule occurrence : sa propre définition). Aucun test ne l'exerce non plus.
2. **Branche morte dans `TrainingPage.create_training()`** (`src/ui/pages/training_page.py:122-127`) — le bloc `if training is None: [...] if not self.workspace_manager.opened:` est **structurellement inatteignable** : une garde identique existe déjà en tête de la même méthode (`training_page.py:73-79`), qui retourne immédiatement si `workspace_manager.opened` est faux — donc au moment d'atteindre la ligne 116, `workspace_manager.opened` est nécessairement vrai, et la branche `if not self.workspace_manager.opened:` (ligne 122) ne peut jamais s'exécuter. Ce constat est déjà documenté dans `PROJECT_CONTEXT.md` (section "Décisions techniques importantes") depuis Mission 029, mais le code lui-même n'a jamais été retiré.
3. **Commentaire obsolète dans `Workspace.from_dict()`** (`src/domain/workspace.py:73-77`) — affirme que « `Workspace.models` has never held real data », ce qui est aujourd'hui **faux** : `ModelManager` (`src/managers/model_manager.py`) est un Manager CRUD pleinement câblé, consommé par `ModelsPage` et `MainWindow`, et `Workspace.models` contient réellement des données persistées. Même défaut de staleness que celui déjà corrigé pour `Character.datasets`/`.loras`/`.prompts` par Mission 057 (section 5, différé), mais sur un fichier distinct, non traité par cette mission-là.
4. **Deux références obsolètes à `BasePage` dans `docs/PROJECT_CONTEXT.md`** (lignes 91 et 203) — le décrivent encore comme « code mort, jamais importé, non traité », alors que Mission 057 l'a supprimé entièrement. Ces deux lignes appartiennent à des sections narratives (« Décisions techniques importantes », « Problèmes connus ») que la régularisation de Mission 057 n'a pas touchées — un résidu de cohérence documentaire, identifié en retour par cet audit.

**Aucune décision produit ou architecturale ne bloque le traitement de ces quatre éléments.** Le seul point nécessitant un jugement (et non une décision produit) concerne `EventBus.unsubscribe()` : contrairement aux trois autres, il ne s'agit pas d'un reliquat accidentel, mais d'une méthode symétrique de `subscribe()`, jamais consommée. Sa présence contredit néanmoins le principe explicitement documenté par `EventBus` lui-même (« avoids introducing an envelope type before any current subscriber needs one — no scaffolding ahead of need ») et le principe CLAUDE.md « Pas de scaffolding avant un besoin réel ». Retrait proposé par cohérence avec ce principe, mais signalé ici pour arbitrage si l'architecte préfère la conserver comme API délibérément complète.

## 2. Mini-audit réalisé

**Confirmation d'absence d'usage réel** :
- `grep -rn "unsubscribe" .` (hors `.venv`) : une seule occurrence, la définition elle-même.
- Lecture directe de `training_page.py:66-134` : la garde ligne 73 retourne avant tout appel à `training_manager.create()` si `workspace_manager.opened` est faux ; donc, au retour de `training_manager.create()` (ligne 114), `workspace_manager.opened` est garanti vrai — la branche ligne 122 est un vrai code mort, pas une supposition.
- Lecture directe de `workspace.py:73-77` et confirmation croisée que `ModelManager`/`ModelsPage` consomment réellement `Workspace.models` (même constat déjà utilisé pour justifier la conservation — jamais la suppression — de ce champ par Mission 057).
- Lecture directe de `PROJECT_CONTEXT.md:91` et `:203` : toutes deux décrivent encore `BasePage` comme présent dans le dépôt.

**Impact tests identifié** : aucun test n'exerce `EventBus.unsubscribe()` (rien à retirer). Aucun test n'exerce spécifiquement la branche morte de `training_page.py` ligne 122-127 (elle est, par construction, inatteignable — impossible à couvrir). Aucun impact sur les suites `test_training_roundtrip.py` existantes, qui exercent uniquement les chemins réellement atteignables.

**Aucune décision produit ou architecturale substantielle ne reste ouverte.**

## 3. Objectif

Retirer les quatre éléments de code mort/documentation obsolète identifiés ci-dessus, sans toucher à aucun comportement réellement observable de l'application.

## 4. Contrat fonctionnel — réellement implémenté

**`src/core/event_bus.py`** :
- Méthode `unsubscribe()` retirée, après vérification finale exhaustive confirmant l'absence de tout appel direct, usage dynamique (`getattr`), export (`__all__`/`__init__.py`) ou test en dépendant.
- `subscribe()`/`publish()`/`_freeze()`/structure interne des abonnements : **strictement inchangés**.

**`src/ui/pages/training_page.py`** :
- Bloc `if not self.workspace_manager.opened: [...] else:` (lignes 122-133 avant modification) retiré, ne conservant que le message "Aucun personnage" — confirmé, par analyse de flot, comme le seul cas réellement atteignable quand `training is None` : `TrainingManager.create()` (`training_manager.py:82-93`) ne retourne `None` que si `principal_character is None` ou si `dataset_id` n'appartient pas à ce Character, jamais en fermant le Workspace ; le seul abonné à `TRAINING_CREATED` est `TrainingPage.update_trainings` (rafraîchissement UI pur) ; la garde ligne 73 garantit déjà `workspace_manager.opened` vrai à ce point de la méthode.
- Reste de `create_training()` : strictement inchangé.

**`src/domain/workspace.py`** :
- Commentaire de `from_dict()` sur `models` corrigé : ne prétend plus que `Workspace.models` « n'a jamais tenu de vraie donnée », reflète désormais qu'il s'agit d'une collection réelle et activement consommée par `ModelManager`/`ModelsPage`. Aucun changement de code.

**`docs/PROJECT_CONTEXT.md`** :
- Ligne 91 (inventaire de composants, décrivait encore `BasePage` comme présent) : retirée — plus rien à inventorier, le fichier n'existe plus.
- Bullet de la section « Problèmes connus / dettes (non résolues...) » décrivant `BasePage` comme dette non résolue : retirée — la section liste explicitement des dettes *non résolues*, or celle-ci l'est depuis Mission 057.
- Aucune autre section touchée.

**Domain/Manager/EventBus (comportement)/Persistance/Inference** : aucun changement de comportement. Seul le retrait de code mort et la correction de texte.

## 5. Comportement explicitement différé (hors périmètre)

- Toute autre référence à un numéro de Mission/Commit dans les commentaires du Domain (violation généralisée, documentée mais non traitée depuis Mission 057) — nécessiterait un audit dédié séparé de tout `src/domain/`.
- Ajout de tests UI dédiés pour `MainWindow.open_project()`/`save_project()` (actuellement non couverts au niveau UI bien que déjà correctement gérés avec `QMessageBox.critical`, voir l'audit) — hors périmètre, sujet distinct sans code mort ni bug associé.
- Toute décision sur la conservation/suppression future d'autres méthodes d'API "complète mais non consommée" au-delà d'`EventBus.unsubscribe()`.

## 6. Fichiers concernés — réellement modifiés

Production (3) :
- `src/core/event_bus.py` (retrait de `unsubscribe()`, 4 lignes de diff)
- `src/ui/pages/training_page.py` (retrait de la branche morte, 28 lignes de diff)
- `src/domain/workspace.py` (correction de commentaire, aucun changement de code, 8 lignes de diff)

Documentation (1) :
- `docs/PROJECT_CONTEXT.md` (retrait de 2 références obsolètes à `BasePage` — inventaire de composants et bullet de dette résolue, 3 lignes de diff)

Tests : **aucun nouveau test, aucun test retiré** — conforme au contrat (aucun comportement observable ne change, `EventBus.unsubscribe()` n'avait aucun test le couvrant, la branche morte de `training_page.py` était par construction non testable, et le seul cas réel restant — « Aucun personnage » — était déjà couvert par `test_training_roundtrip.py:664` avant cette mission).

## 7. Stratégie de tests — réellement mise en œuvre

- Suite ciblée : `test_training_roundtrip.py` — **34/34 verts**, aucune régression sur `create_training()`. Aucune suite `test_event_bus.py` dédiée n'existe dans le dépôt ; aucun test (dans aucune suite) ne référence `unsubscribe`.
- Suite complète : **967/967 tests verts** — décompte strictement identique à l'état pré-mission (aucun test ajouté ni retiré).
- `git diff --check` propre, diff limité aux 4 fichiers du périmètre.
- Aucun smoke test Qt formel requis — un cycle réel `TrainingPage.create_training()` a néanmoins été exécuté manuellement (script scratchpad, jamais committé) en non-régression, voir section 10.

## 8. Risques

- **Risque de régression fonctionnelle** : nul, confirmé — `unsubscribe()` n'avait aucun appelant (vérification finale exhaustive : aucun appel direct, aucun `getattr` dynamique, aucun export, aucun test), la branche morte de `training_page.py` était structurellement inatteignable (analyse de flot confirmée par lecture directe de `TrainingManager.create()` et des abonnés à `TRAINING_CREATED`), et les corrections de commentaires ne touchent aucun code.
- **Risque de désaccord sur `EventBus.unsubscribe()`** : **résolu** — arbitrage explicite de l'architecte confirmant le retrait.

## 9. Pourquoi maintenant

Prolonge directement le nettoyage entamé par Mission 057, avec des éléments frais identifiés par un audit dédié post-clôture — dont un résidu de cohérence documentaire (`BasePage` encore référencé dans `PROJECT_CONTEXT.md`) directement issu de la régularisation de Mission 057 elle-même. Petit périmètre, risque nul, aucune dépendance externe, aucun choix d'architecture ouvert.

## 10. Vérification manuelle réelle — cycle Qt Training

Exécuté moi-même en dehors de la suite `unittest` (script scratchpad, jamais committé), avec les Managers et widgets réels (`TrainingPage`, `TrainingManager`, `DatasetManager`, `CharacterManager`, `WorkspaceManager`, `DashboardPage`) — pas de mock, sauf `QMessageBox.warning` (patché pour capturer l'appel sans bloquer sur une boîte de dialogue réelle) :

1. Aucun Workspace ouvert → `page.create_training()` affiche exactement le même avertissement « Aucun projet ouvert » qu'avant cette mission.
2. Workspace ouvert, aucun Dataset → même avertissement « Aucun dataset disponible » qu'avant cette mission. `DashboardPage.trainingCard` affiche bien `"0"`.
3. Dataset réel créé, sélection via les vrais `QInputDialog.getItem()`/`getText()` patchés pour simuler une saisie utilisateur → `Training` réellement créé (`len(trainings) == 1`), `training_list` rafraîchie via le vrai `EventBus` (`TRAINING_CREATED`), libellé affiché correct.
4. Confirmation que le Workspace reste ouvert après suppression du Character (la garde ligne 73 ne peut jamais redevenir vraie dans ce flux).

Le cas « Aucun personnage » (seule branche réellement atteignable de l'ancien bloc `if training is None:`) n'a pas été re-testé manuellement ici — il est déjà couvert par `test_training_roundtrip.py:664`, vert dans la suite ciblée ci-dessus, et son message n'a pas changé.

**Verdict : PASS, sans écart.** Comportement utilisateur de `TrainingPage.create_training()` strictement identique à avant cette mission, sur les quatre scénarios réellement atteignables.

## État d'avancement

- Audit du dépôt (candidats Mission 058) : **réalisé**.
- Choix de mission : **validé par l'architecte** (2026-08-24), avec arbitrage explicite sur `EventBus.unsubscribe()`.
- Spécification (ce document) : **rédigée**, conforme à l'implémentation réalisée.
- Implémentation : **réalisée**, conforme au contrat, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — `test_training_roundtrip.py` 34/34, suite complète 967/967 (décompte inchangé).
- `git diff --check` : **propre**.
- Vérification manuelle réelle (cycle Qt Training) : **réalisée, PASS** (section 10).
- Clôture Git (commit/tag/Release) : **effectuée** — voir section 11 ci-dessous.

## 11. Clôture

**Fichiers concernés (4)** :
- `src/core/event_bus.py` — retrait de `unsubscribe()`.
- `src/ui/pages/training_page.py` — retrait de la branche structurellement inatteignable de `create_training()`.
- `src/domain/workspace.py` — correction du commentaire obsolète de `from_dict()` sur `Workspace.models` (aucun changement de code).
- `docs/PROJECT_CONTEXT.md` — retrait de deux références obsolètes à `BasePage` (inventaire de composants, bullet de dette déjà résolue par Mission 057).

**Commit fonctionnel** : `9e35c4497fe880123f46a6edd6b10603727d123c` (`chore: remove dead code and stale documentation (round 2)`), 4 fichiers, 15 insertions/28 suppressions.

**Tag** : `v0.2-mission058` (annoté, message `Mission 058 - Dead Code and Stale Documentation Cleanup`), ciblant exactement le commit fonctionnel ci-dessus — vérifié localement (`git rev-list -n1`) et à distance (`git ls-remote --tags origin v0.2-mission058 "v0.2-mission058^{}"`).

**GitHub Release** : `v0.2-mission058` — **publiée**, confirmée par l'architecte du projet.

**Résultats réels** : 967/967 tests automatisés verts (décompte strictement inchangé par rapport à l'état pré-mission, conformément au contrat — aucun test ajouté ni retiré) ; `git diff --check` propre ; cycle Qt réel `TrainingPage.create_training()` exécuté manuellement, PASS sur les quatre scénarios réellement atteignables (voir section 10).

**État final** : mission entièrement close — implémentation, tests, vérification manuelle réelle, commit, tag et Release tous complets. Régularisation documentaire (`MISSION_058.md`, `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`) effectuée après publication de la Release, conformément à la procédure standard de fin de mission.
