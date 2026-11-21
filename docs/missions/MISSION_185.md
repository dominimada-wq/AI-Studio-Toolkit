# Mission 185 — Reconstruire la liste Training à l'ouverture d'un projet et à chaque changement de contexte

> **STATUT (2026-11-21) : Mission 185 implémentée et testée automatiquement (validation ciblée de trois modules) ; vérification manuelle partielle dans l'interface (liste remplie dès l'ouverture, paramètres affichés à la sélection ; réouverture du même projet non vérifiée) ; un commit fonctionnel local, non poussé ; mission ni publiée ni close ; suite complète non validée.** Ce statut ne ferme aucune réserve : la validation ciblée de la section 6 n'est pas une suite complète, L18 n'a pas été exécuté (non autorisé) et le plantage `0xC0000374` de la Mission 177 reste hors périmètre. Aucune génération, aucun entraînement et aucun lancement de moteur n'ont été faits dans cette mission.

## 1. Objectif et limites

Corriger un défaut établi de la page Training : après l'ouverture d'un projet contenant des trainings, la liste des sessions restait vide (alors que le Dashboard les comptait) jusqu'à un événement de rafraîchissement, par exemple « Sauvegarder ». Correction minimale : `TrainingPage.reset_for_context_change()` reconstruit la liste en se terminant par `update_trainings()`.

Hors périmètre (non implémenté, explicitement différé) : sélection automatique d'un training, mémorisation du dernier training ouvert, menu « Fermer le projet » (évolution distincte, non retenue à ce stade), EF-01 à EF-04, diagnostic des arrêts de la machine, publication de la Mission 184.

## 2. Décisions de l'architecte (2026-11-21)

- Rapport d'impact validé pour la Mission 185, sous réserve de disponibilité du numéro (aucun fichier, tag ni entrée du journal ne portait ce numéro).
- **Option A retenue** : appeler `update_trainings()` à la fin de `reset_for_context_change()`, sans sélection automatique et sans modification des données ni de la persistance.
- Tests dans `tests/integration/test_training_roundtrip.py`, par un EventBus réel et un ordre d'abonnement représentatif de `MainWindow`, avec des **projets temporaires isolés et des données fictives** : le projet réel `Essai-Recette-2` n'est ni modifié ni dupliqué.
- Autorisation d'exécuter, avant et après la modification, `test_training_roundtrip`, `test_training_page_external_refresh` et `test_main_window_training_to_inference` (et les relances nécessaires pour résoudre un échec lié à la mission) ; L18 et la suite complète exclus.
- Si l'ordre des événements imposait une correction plus large que l'option A, l'écart devait être présenté avant implémentation : cela n'a pas été nécessaire.
- Un commit local de code avec ses tests, puis un commit documentaire séparé ; aucun tag, push ni Release.

## 3. Constat initial (établi)

- `TrainingPage.reset_for_context_change()` (abonné par `MainWindow` à `WORKSPACE_CREATED/OPENED/CLOSED` et `CHARACTER_SELECTED/DELETED`) vidait `training_list`, désactivait les boutons et réinitialisait les champs, **sans reconstruire la liste**. `update_trainings()` n'est abonné qu'à `WORKSPACE_SAVED/RENAMED`, `CHARACTER_CREATED` et `TRAINING_CREATED/SELECTED/DELETED`.
- `DatasetsPage.reset_for_context_change()` se termine par `update_datasets()` ; `LoRAPage` rafraîchit sa liste ; la page Training était la seule à ne pas repeupler.
- Diagnostic hors dépôt du 2026-11-05 (reproduction par les vraies pages Qt en mode hors écran, sur une copie du projet) : après l'ouverture, Dashboard = 3 sessions, liste Training = 0, `TrainingManager.list_trainings()` = 3 ; après un `WORKSPACE_SAVED`, la liste se remplissait. Données intactes. Le comportement date de l'introduction du découpage `update_trainings()` / `reset_for_context_change()` (Mission 105).
- Contournement avant correction : « Sauvegarder » (réécrit `project.json`), puis cliquer le training voulu.

## 4. Implémentation

`src/ui/pages/training_page.py` (10 lignes ajoutées ou modifiées) : `reset_for_context_change()` se termine désormais par `self.update_trainings()`, précédé d'un commentaire ; la docstring le mentionne. Après un changement de contexte, aucun training n'est actif : la liste est reconstruite depuis `TrainingManager`, triée par nom, aucun élément n'est sélectionné, les boutons liés à la session (Supprimer, Enregistrer les paramètres, Préparer la configuration) restent désactivés. `update_trainings()` n'écrit pas dans le Workspace. Domain, Managers, persistance, événements et `main_window.py` inchangés.

## 5. Tests ajoutés (+7)

Classe `TrainingListRepopulationOnContextChangeTest` dans `tests/integration/test_training_roundtrip.py` (430 → 437 tests ; aucun test existant modifié). EventBus, Managers et pages réels (`DashboardPage`, `CharactersPage`, `ImagesPage`, `TrainingPage`), abonnés dans l'ordre relatif de `MainWindow` (Managers d'abord, rafraîchissements généraux, puis remises à zéro de contexte avec `CharactersPage` avant `TrainingPage`) ; `DatasetsPage`, `LoRAPage` et `SettingsPage` ne sont pas construites. Projets temporaires isolés, données fictives.

1. `test_opening_a_project_with_trainings_populates_the_sorted_list_without_selection` : liste remplie et triée sans tenir compte de la casse, aucun training sélectionné ni actif, trois boutons désactivés.
2. `test_switching_from_project_a_to_project_b_leaves_no_entry_of_a` : ouverture directe du projet B alors que A est ouvert avec un training sélectionné ; aucune entrée ni identifiant de A ne subsiste.
3. `test_character_switch_rebuilds_the_list_for_the_new_principal_character` : à `CHARACTER_SELECTED`, la liste suit le personnage principal (vide pour un second personnage sans training, de nouveau remplie au retour) ; aucun training actif. Ce chemin n'est pas atteignable depuis l'interface visible (la liste des personnages est masquée depuis la Mission 026) : il est exercé via le Manager.
4. `test_opening_an_empty_project_shows_an_empty_list`.
5. `test_closing_the_project_empties_the_list` (fermeture interne par `WorkspaceManager.close()`).
6. `test_closing_then_reopening_the_same_project_repopulates_the_list` (fermeture interne puis réouverture, au niveau Manager).
7. `test_unsaved_drafts_are_abandoned_on_project_switch_without_writing_to_any_project` : un brouillon de nom et un brouillon de paramètre (epochs) non enregistrés sont abandonnés au changement de projet ; **contrôle automatisé de non-écriture** : aucun appel à `WorkspaceStorage.save` pendant l'ouverture du projet B, et les `project.json` des deux projets temporaires sont identiques octet pour octet avant et après.

## 6. Validation automatique ciblée : ce qui a été exécuté

Environnement : Windows 10, Python 3.11.9, PySide6 6.11.1, `QT_QPA_PLATFORM=offscreen`, `unittest` ; exécutions du 2026-11-21 sur autorisation de l'architecte.

| Module | Avant la modification | Après |
|---|---|---|
| `test_training_page_external_refresh` | 18 | 18 |
| `test_main_window_training_to_inference` | 5 | 5 |
| `test_training_roundtrip` | 430 | 437 (+7) |
| **Total** | **453, tous réussis** | **460, tous réussis** |

**Défaut reproduit avant correction** : les 7 nouveaux tests, exécutés seuls avant la modification du code, donnent 5 échecs (liste vide au lieu des trainings) ; les deux autres (projet vide, fermeture interne) passent et servent de non-régression. Après la correction : 7 sur 7.

## 7. Propriétés vérifiées et non vérifiées

**Vérifié automatiquement** (par exécution) : liste remplie à l'ouverture d'un projet ; passage direct d'un projet à un autre sans entrée résiduelle ; changement de personnage selon la règle du personnage principal ; projet vide ; fermeture interne ; réouverture au niveau Manager ; abandon des brouillons de nom et de paramètre selon la protection existante ; absence de sélection active et boutons désactivés ; absence d'écriture (compteur d'appels et octets identiques, section 5, test 7) ; ordre d'abonnement du Manager avant la page suffisant pour que la liste soit juste.

**Non vérifié** : `MainWindow` complet (aucun des trois modules ne l'exerce pour ce comportement) ; interaction réelle à l'écran autre que la vérification manuelle de la section 9 ; suite complète ; L18.

## 8. Limites connues et réserves

1. Suite complète non validée (réserves R1 à R3 du registre), L18 non autorisé ; validation ciblée de trois modules seulement.
2. Les tests de contexte ne construisent pas `DatasetsPage`, `LoRAPage` ni `SettingsPage`, abonnées par `MainWindow` entre les deux pages concernées.
3. Aucun menu « Fermer le projet » n'existe dans l'interface (constat de l'architecte, confirmé par la barre de menus : Nouveau projet, Ouvrir un projet, Sauvegarder, Renommer le projet…, Quitter) : la fermeture est couverte automatiquement seulement. L'ajout éventuel de ce menu est une évolution distincte.
4. Le passage entre deux projets n'a pas été essayé à la main : l'architecte ne possède qu'un seul projet réel contenant des trainings.
5. Cette mission n'ouvre ni ne ferme aucune réserve du registre de `docs/PROJECT_CONTEXT.md` ; aucune réserve nouvelle n'y est inscrite (décision éventuelle à prendre séparément).

## 9. Vérifications manuelles dans l'interface (architecte, 2026-11-21)

Distinction entre ce qui a été **vérifié dans l'interface**, ce qui est **couvert automatiquement** et ce qui n'a **pas** été vérifié manuellement.

**Procédure (corrigée : aucun menu de fermeture n'existe)** : (1) relancer le Toolkit, l'instance déjà ouverte ne contenant pas la correction ; (2) ouvrir `Essai-Recette-2` par « Ouvrir un projet », sans « Sauvegarder » ; (3) page Training : les sessions doivent apparaître immédiatement, aucune sélectionnée, boutons liés à la session grisés ; (4) cliquer une session : ses paramètres s'affichent et les boutons s'activent ; (5) facultatif : rouvrir le même projet par « Ouvrir un projet », la liste doit rester remplie et la sélection disparaître.

**Vérifié dans l'interface** (captures d'écran de l'architecte, projet `Essai-Recette-2`) :
- après l'ouverture, sans « Sauvegarder » : les quatre sessions `training 01` à `training 04` sont dans la liste, aucune n'est sélectionnée, les boutons Supprimer, Enregistrer les paramètres, Préparer la configuration et Démarrer sont désactivés ;
- après un clic sur `training 04` : ses paramètres s'affichent (architecture SDXL, résolution 1024, 15 epochs, trigger word « Kaëlya woman »…), les boutons s'activent et les résultats d'entraînement sont affichés.

**Couvert automatiquement, non reproduit à la main** : passage d'un projet A à un projet B ; fermeture interne ; abandon des brouillons ; absence de sélection et boutons désactivés ; absence d'écriture (contrôle automatisé de la section 5, test 7).

**Non vérifié manuellement** : réouverture du même projet par « Ouvrir un projet » (étape 5 de la procédure : non effectuée à ce jour) ; absence d'écriture dans `project.json` pendant l'essai manuel. La date de modification de `project.json` n'est pas retenue comme preuve de non-écriture : seul le contrôle automatisé de la section 5 l'établit, sur les projets temporaires.

## 10. Preuves hors dépôt (jamais versionnées)

Diagnostic `DIAGNOSTIC_LISTE_TRAINING_VIDE_20261105.md` et script de reproduction du dossier de notes ; captures d'écran de l'architecte du 2026-11-21 ; sorties des exécutions de tests (espace temporaire de la session). Ces fichiers ne sont pas dans le dépôt.

## 11. Fichiers du périmètre et statut

Code et tests (commit `c2afe5abd5c9d377769eed2fae2f6b268e06c4e1`) : `src/ui/pages/training_page.py`, `tests/integration/test_training_roundtrip.py`.

Documentation (commit suivant, dont l'identifiant n'est pas cité ici : Git fait autorité) : `docs/missions/MISSION_185.md` (ce fichier), `docs/PROJECT_CONTEXT.md`, `CHANGELOG.md`, `docs/archive/README.md` (section d'archivage complémentaire), `docs/archive/changelog/CHANGELOG_M175-M175.md` et `docs/archive/MANIFEST_M175.json` (nouveaux).

## 12. Archivage documentaire

L'ajout de l'entrée de la Mission 185 portait à onze les entrées intégrales du journal ; l'entrée de la Mission 175 (lignes 407 à 421 du `CHANGELOG.md` de base, 10460 octets, SHA-256 `f39f102bff1d492d6bbcc3734b5fe1e7ff8e869a8e252785431947c40d3c9842`) a été déplacée à l'identique dans `docs/archive/changelog/CHANGELOG_M175-M175.md` (11819 octets, SHA-256 `d75e0fb834183d42c2d16276752e51230733eac2cb03ccbd5d89161633914b34`), avec un manifeste propre, `docs/archive/MANIFEST_M175.json`. Aucune archive existante, ni `MANIFEST.json`, ni `MANIFEST_M174.json`, ni `CORRESPONDANCE.md` n'est modifiée. Vérification de l'exactitude par empreinte contre le blob Git du commit de base `c2afe5abd5c9d377769eed2fae2f6b268e06c4e1` : voir `docs/archive/README.md`. Les dix entrées intégrales restantes de `CHANGELOG.md` sont celles des Missions 176 à 185.

## 13. Suite

- Vérification manuelle complémentaire facultative : réouverture du même projet (section 9, étape 5).
- Décision de publication (tag, push, Release) de la Mission 184 et de la Mission 185 : **non décidée**, aucun push n'a été fait.
- Travail suivant retenu par l'architecte : **EF-01** (détection des légendes trop longues dans le Toolkit) ; rapport d'impact hors dépôt à produire avant tout code. EF-02, EF-03 et EF-04 restent enregistrées hors dépôt pour plus tard ; l'ajout éventuel d'un menu « Fermer le projet » est une évolution distincte.
