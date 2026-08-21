# Mission 043 — Dashboard Training Indicator

> **STATUT : IMPLÉMENTATION RÉALISÉE, 18/18 TESTS CIBLÉS `test_training_roundtrip.py`, 733/733 TESTS AUTOMATISÉS VERTS, SMOKE TEST MANUEL RÉEL DU RENDU QT PASS. CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> Voir "État d'avancement" en fin de document.

## 1. Contexte

Besoin enregistré comme dette UX ouverte depuis Mission 029 (voir `docs/PROJECT_CONTEXT.md`, section "Besoins futurs identifiés" — « Dashboard — clarification de l'indicateur Training ») : `DashboardPage.trainingCard` affiche aujourd'hui la valeur figée `"Idle"`, jamais mise à jour par `update_project()`, alors que toutes les autres cartes de la grille (`imagesCard`/`datasetsCard`/`modelsCard`/`lorasCard`) affichent un compteur réel des données du Workspace.

Un mini-audit ciblé en lecture seule a ensuite vérifié précisément : la structure de `DashboardPage`/`update_project()`, le calcul actuel des compteurs `datasetsCard`/`lorasCard`, la structure réelle de `Character.trainings`, le cycle création/persistance/rechargement des sessions Training (`TrainingManager.create()`/`delete()`), le mécanisme de rafraîchissement du Dashboard (`WorkspaceManager.save()` → `WORKSPACE_SAVED` → `DashboardPage.update_project()`), les tests existants de `DashboardPage`/Training, et la question centrale : le Dashboard peut-il être rafraîchi après création/suppression d'une session Training sans wiring EventBus supplémentaire. Conclusion vérifiée (pas supposée) : `TrainingManager.create()`/`delete()` appellent déjà `workspace_manager.save()` avant de publier leur propre événement — `DashboardPage.update_project()`, déjà abonné à `WORKSPACE_SAVED` depuis `MainWindow`, est donc **déjà rappelé automatiquement** à chaque création/suppression de session Training, exactement comme pour `datasetsCard`/`lorasCard` aujourd'hui. Aucun wiring supplémentaire n'est nécessaire.

## 2. Problème

`trainingCard` est la seule carte du Dashboard qui ne reflète aucune donnée réelle du Workspace : elle affiche en permanence `"Idle"`, y compris lorsque des sessions Training existent, et n'est même jamais réinitialisée à la fermeture d'un projet — contrairement aux quatre autres cartes.

## 3. Objectif

Faire de `trainingCard` un compteur réel du nombre de sessions Training enregistrées dans le Workspace, strictement cohérent avec le traitement déjà appliqué à `datasetsCard`/`lorasCard`, sans introduire ni simuler un quelconque état d'exécution d'un moteur d'entraînement (aucun moteur réel n'existe à ce jour).

## 4. Contrat fonctionnel validé

| Situation | Valeur affichée par `trainingCard` |
|---|---|
| Aucun Workspace ouvert / état initial d'un `DashboardPage` fraîchement construit | `"0"` |
| Workspace ouvert sans aucune session Training | `"0"` |
| Création d'une session Training | compteur incrémenté en conséquence |
| Plusieurs sessions Training | compteur correspondant exact |
| Suppression d'une session Training | compteur décrémenté en conséquence |
| Fermeture du Workspace | retour à `"0"` |
| Réouverture d'un Workspace persistant des sessions Training | compteur restauré depuis les données rechargées |

Aucun texte `"Idle"`/`"Running"`/`"Failed"` ou équivalent n'est affiché à aucun moment. `trainingButton` reste strictement inchangé (visible, désactivé, tooltip existant).

## 5. Périmètre

Production (1) :
- `src/ui/pages/dashboard_page.py`

Modifications attendues, exactement au nombre de trois :
1. Constructeur : `DashboardCard("Training", "Idle")` → `DashboardCard("Training", "0")`.
2. `update_project()`, branche `project is None` : ajout explicite de `self.trainingCard.value.setText("0")`, au même titre que les quatre autres cartes déjà réinitialisées dans cette branche.
3. `update_project()`, branche normale : ajout d'une agrégation `trainingCard.value.setText(str(sum(len(character.get("trainings") or []) for character in (project.get("characters") or []))))`, calquée à l'identique sur le pattern déjà utilisé pour `datasetsCard`/`lorasCard`.

Tests (1, extension d'un fichier existant) :
- `tests/integration/test_training_roundtrip.py`

## 6. Hors périmètre

- Tout moteur d'entraînement réel.
- Tout état d'exécution (`Idle`, `Running`, `Failed`, etc.) — la notion d'état d'exécution est explicitement abandonnée par cette mission, pas seulement reportée.
- Toute modification de `TrainingManager`.
- Toute modification Domain (`Training`, `Character`).
- Toute modification de la persistance (`WorkspaceStorage`/`WorkspaceManager.save()`).
- Tout nouveau mécanisme ou souscription EventBus (voir section 7).
- Toute activation de `trainingButton`.
- Toute refonte générale du Dashboard (disposition, autres cartes, styles).
- Toute autre dette UX documentée dans `docs/PROJECT_CONTEXT.md`.

## 7. Wiring de rafraîchissement — aucun ajout

Chemin déjà existant et suffisant, vérifié par le mini-audit :

```
TrainingManager.create() / delete()
  → WorkspaceManager.save()
  → événement WORKSPACE_SAVED
  → DashboardPage.update_project() (déjà abonné depuis MainWindow)
```

Aucune souscription directe de `DashboardPage` à `TRAINING_CREATED`/`TRAINING_DELETED` n'est ajoutée. `DashboardPage` reste sans dépendance à aucun Manager (constructeur `DashboardPage()` inchangé, toujours sans argument).

## 8. Stratégie d'implémentation — réellement mise en œuvre

Les trois modifications de la section 5 ont été réalisées à l'identique, sans aucune divergence par rapport au contrat :

- `DashboardCard("Training", "Idle")` → `DashboardCard("Training", "0")`.
- Branche `project is None` de `update_project()` : ajout de `self.trainingCard.value.setText("0")`, au même titre que les quatre autres cartes déjà réinitialisées.
- Branche normale : ajout de `total_trainings = sum(len(character.get("trainings") or []) for character in (project.get("characters") or []))` puis `self.trainingCard.value.setText(str(total_trainings))` — pattern strictement identique à celui déjà utilisé pour `datasetsCard`/`lorasCard`.

Aucune autre ligne de `dashboard_page.py` modifiée : disposition de la grille, autres cartes, `trainingButton`, signature de `update_project(self, project)` tous strictement inchangés. Aucune nouvelle dépendance, aucun nouveau constructeur.

## 9. Stratégie de tests — réellement mise en œuvre

Extension de `tests/integration/test_training_roundtrip.py`, réutilisant intégralement l'infrastructure `_wire()` déjà existante (qui instancie déjà un vrai `DashboardPage` abonné aux `WORKSPACE_EVENTS`, exactement comme pour `imagesCard` dans `test_workspace_roundtrip.py`) — aucune nouvelle fixture créée :

- `test_full_create_select_save_close_reopen_cycle` (existant, étendu) : assertions ajoutées sur `dashboard.trainingCard.value.text()` aux points déjà présents dans le cycle — `"0"` avant création, `"1"` après création de la session, `"0"` après `workspace_manager.close()`, `"1"` restauré après réouverture (`dashboard_2`, instances fraîches).
- `test_dashboard_training_card_default_value_without_any_workspace` (nouveau) : un `DashboardPage()` fraîchement construit, sans aucun Workspace, affiche `"0"`.
- `test_dashboard_training_card_reflects_multiple_sessions_and_deletion` (nouveau) : création de 2 sessions (`"1"` puis `"2"`), suppression des 2 (`"1"` puis `"0"`).

`test_dashboard_page.py` non modifié (couverture des boutons, hors périmètre). `test_dashboard_and_images_unaffected_by_training_events` non modifié — confirmé après implémentation que ses assertions (`projectCard`/`images.list_widget.count()`) ne portent jamais sur `trainingCard` et restent exactes telles quelles.

Aucune comparaison pixel par pixel dans les tests automatisés.

## 10. Critères d'acceptation — résultats

- `DashboardPage()` fraîchement construit, sans Workspace : `trainingCard.value.text() == "0"` — **conforme**.
- Workspace ouvert sans session Training : `"0"` — **conforme**.
- Après création d'une session Training : compteur incrémenté correctement (`"1"`) — **conforme**.
- Après création de plusieurs sessions : compteur exact (`"2"`) — **conforme**.
- Après suppression d'une session : compteur décrémenté correctement (`"2"` → `"1"` → `"0"`) — **conforme**.
- Après fermeture du Workspace : retour à `"0"` — **conforme**.
- Après réouverture d'un Workspace persistant des sessions Training : compteur restauré fidèlement (`"1"`) — **conforme**.
- Aucune régression des autres cartes (`projectCard`/`imagesCard`/`datasetsCard`/`modelsCard`/`lorasCard`) ni de `trainingButton` (toujours désactivé, tooltip inchangé) — **confirmé**, y compris par le smoke test réel.
- Suite `test_training_roundtrip.py` : **18/18 OK** (16 précédents + 2 nets nouveaux).
- Non-régression croisée (`test_dashboard_page.py`, `test_workspace_roundtrip.py`, `test_dataset_roundtrip.py`, `test_lora_roundtrip.py`) : **108/108 OK**.
- Suite complète du projet : **733/733 OK** (731 précédents + 2 nets nouveaux).
- `git diff --check` : **propre** (seul avertissement bénin de conversion LF/CRLF, aucune erreur d'espace).
- **Smoke test manuel obligatoire (section 11) réalisé, résultat PASS.**
- Aucun changement hors périmètre introduit (voir section 6) — confirmé par inspection du diff complet, limité à `dashboard_page.py` et `test_training_roundtrip.py`.

## 11. Smoke test manuel — réalisé, PASS

Réalisé moi-même (rendu de vrais widgets Qt — `DashboardPage`, `EventBus`, Managers réels — aucune dépendance externe type Ollama/ComfyUI requise). Script et captures exclusivement dans le scratchpad de session, jamais dans le dépôt.

Points observés réellement, tous conformes :
- `DashboardPage()` fraîchement construit, avant tout Workspace : `trainingCard` = `"0"`.
- Workspace créé, aucune session Training : `trainingCard` = `"0"`.
- Création de 2 sessions Training réelles via `TrainingManager.create()` : `trainingCard` observé successivement à `"1"` puis `"2"`.
- Suppression d'une session via `TrainingManager.delete()` : `trainingCard` = `"1"`.
- Fermeture du Workspace : `trainingCard` = `"0"`.
- Réouverture du Workspace (instances `EventBus`/`DashboardPage` fraîches, simulant un redémarrage réel) : `trainingCard` = `"1"`, restauré depuis les données persistées, observable dès `WORKSPACE_OPENED` sans sélection manuelle de Character/Training.
- Non-régression confirmée : `datasetsCard` = `"1"` (cohérent), `trainingButton.isEnabled()` = `False`.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4. Aucune vérification manuelle utilisateur n'a été nécessaire — tous les points prévus étaient observables de manière fiable depuis cet environnement.

## 12. Risques / non-régressions

- **Risque architectural** : nul — aucun changement Domain/Manager/EventBus/persistance, modification strictement confinée à `dashboard_page.py`. Confirmé par inspection du diff complet.
- **Risque de régression des autres cartes** : mitigé — les trois modifications sont additives et localisées ; `imagesCard`/`datasetsCard`/`modelsCard`/`lorasCard` restent des lignes de code inchangées, confirmé par 108/108 tests de non-régression croisée et par le smoke test réel.
- **Risque de rafraîchissement manqué** : écarté par le mini-audit puis confirmé par le smoke test réel — le chemin `WORKSPACE_SAVED` existant, déjà prouvé suffisant pour `datasetsCard`/`lorasCard`, s'est avéré également suffisant pour `trainingCard` (`TrainingManager.create()`/`delete()` suivent exactement le même appel à `workspace_manager.save()`), sans qu'aucun wiring supplémentaire n'ait été nécessaire.
- **Test existant `test_dashboard_and_images_unaffected_by_training_events`** : resté inchangé, comme prévu — ses assertions ne portent jamais sur `trainingCard`, seulement sur `projectCard` et le nombre d'images, qui ne sont effectivement pas affectés par un événement Training.
- **Aucune divergence de périmètre** : les trois fichiers modifiés (`dashboard_page.py`, `test_training_roundtrip.py`, ce document) correspondent exactement à ceux annoncés en section 5 — aucun fichier Domain/Manager/EventBus/persistance touché, aucune activation de `trainingButton`, aucun état d'exécution introduit.

## État d'avancement

- Audit de sélection (candidats Mission 043), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 18/18 (`test_training_roundtrip.py`), 108/108 (non-régression croisée), 733/733 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée**.
- GitHub Release : **non préparée**.
