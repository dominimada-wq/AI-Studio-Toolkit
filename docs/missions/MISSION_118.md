# Mission 118 — SettingsPage Navigation Reorganization

> **MISSION IMPLÉMENTÉE — CLÔTURE EN COURS.** Implémentée, validée par la suite complète, commit fonctionnel en préparation.

## 1. Contexte

`SettingsPage` avait accumulé, mission après mission (M025 à M117), un unique `QFormLayout` linéaire couvrant Workspace, Python/ComfyUI/OneTrainer/Ollama/Forge/LoRA — un mini-correctif (Mission 115) avait déjà dû l'envelopper dans un `QScrollArea` pour que `application_save_button` reste atteignable. La priorité de cette réorganisation avait été explicitement réévaluée à la hausse depuis cet incident réel, et le fil ComfyUI Local (auto-start visible puis annulable, Missions 116/117) étant refermé, elle devenait la dette la plus significative encore ouverte.

## 2. Objectif

Réorganiser `SettingsPage` autour d'une navigation par catégories, préparant explicitement la séparation entre moteurs/services **locaux** et **cloud**, et les futurs domaines **Video Generation**/**Audio Generation**, sans aucune régression sur les champs, comportements ou noms d'attributs existants.

## 3. Décision retenue

Architecture cible fournie par l'architecte (corrigée après un premier retour) :

- **General** — Workspace (thème/langue) + Bibliothèque LoRA centrale
- **Training** → OneTrainer
- **Local Image Generation** → ComfyUI Local, Stable Diffusion Forge
- **Cloud Image Generation** — non peuplée (aucun provider implémenté)
- **Video Generation** / **Audio Generation** — non peuplées (aucune fonctionnalité)
- **AI Assistants** — Ollama
- **Online Services** — omise : aucun champ ne reste orphelin une fois les catégories ci-dessus attribuées

Implémentation : un `QListWidget` (`settings_nav_list`) pilote un `QStackedWidget` (`settings_stack`) — réutilisation exacte de l'idiome Sidebar/stack déjà établi et documenté comme convention permanente dans `CLAUDE.md` pour la navigation de `MainWindow`, appliqué ici une seconde fois, imbriqué dans `SettingsPage`, plutôt que d'introduire un nouveau type de widget (`QTreeWidget`). Les lignes d'en-tête (`Training`, `Local Image Generation`) sont de simples lignes visuelles non sélectionnables/non activées (`Qt.ItemIsEnabled`/`Qt.ItemIsSelectable` retirés), permettant un regroupement visuel à deux niveaux sans second widget. `_settings_nav_stack_index` associe chaque ligne sélectionnable à la page `settings_stack` correspondante ; les lignes d'en-tête en sont simplement absentes.

Les deux boutons de sauvegarde existants (`save_button`, `application_save_button`) restent globaux, positionnés hors du `QStackedWidget`, toujours visibles quelle que soit la catégorie affichée — `application_save_button` persistait déjà tous les champs Application en un seul appel avant cette mission ; le figer dans une seule catégorie aurait laissé croire, à tort, qu'il ne concerne que celle-ci.

## 4. Comportement implémenté

| Élément | Comportement |
|---|---|
| Ouverture de `SettingsPage` | Catégorie « General » sélectionnée par défaut |
| Clic sur une catégorie sélectionnable | `settings_stack` affiche la page correspondante ; toute valeur déjà saisie ailleurs reste intacte (les widgets ne sont ni détruits ni réinitialisés, seulement masqués) |
| Clic sur une ligne d'en-tête (Training / Local Image Generation) | Aucun effet — ligne non sélectionnable, `settings_stack` inchangé |
| Enregistrer (Workspace) / Enregistrer (Application) | Comportement strictement inchangé — lit les widgets par attribut, indépendamment de la catégorie actuellement affichée |
| Tout champ/bouton existant (`comfyui_url_edit`, `forge_path_edit`, `ollama_model_name_edit`, `refresh_checkpoints_button`, etc.) | Même attribut, même signal, même méthode — seule sa position dans l'arborescence de widgets a changé |

## 5. Périmètre exact — fichiers concernés

- `src/ui/pages/settings_page.py` (modifié) — construction de `settings_nav_list`/`settings_stack`, 5 pages feuilles, nouveau handler `_on_settings_nav_row_changed()`. Aucun attribut public renommé, aucune méthode supprimée ou modifiée.
- `tests/integration/test_settings_page.py` (modifié) — nouvelle classe `SettingsPageNavigationTest` (9 tests : sélection par défaut, contenu par catégorie pour les 4 pages peuplées, lignes d'en-tête non sélectionnables, stack inchangé sur clic d'en-tête, boutons Save hors stack, préservation d'une saisie non sauvegardée lors d'un changement de catégorie). Les 74 tests préexistants n'ont nécessité **aucune** modification.

**Aucun changement** à `src/domain/`, `src/managers/`, `src/infrastructure/`, `src/core/event_bus.py`, `ComfyUIEngine`, `ForgeEngine`, `OllamaEngine`, `ComfyUILifecycleManager` — confirmé par audit avant implémentation (chaque champ tracé jusqu'à son consommateur réel), aucun écart architectural rencontré.

## 6. Hors périmètre strict

- Toute page/catégorie pour Fooocus, fal.ai, Higgsfield, ComfyUI Cloud, Video Generation, Audio Generation — aucun champ/consommateur n'existe encore pour eux ; seule la structure déclarative (`add_settings_header()`/`add_settings_page()`) est pensée pour accueillir un futur ajout sans restructuration.
- Toute catégorie « Online Services » — non nécessaire, aucun champ orphelin.
- Toute séparation Save par catégorie — les deux boutons Save existants restent globaux, comportement inchangé.

## 7. Tests

`SettingsPageNavigationTest` : 9/9. `test_settings_page.py` complet : **83/83** (74 préexistants inchangés + 9 nets nouveaux). Suites dépendantes (`test_main_window_close_event`, `test_main_window_ollama_settings`, `test_application_settings_roundtrip`, `test_training_roundtrip`, `test_settings_roundtrip`) : **304/304**. Suite complète : **2327/2327** (2318 avant Mission 118 + 9 nets nouveaux). `git diff --check` propre.

## 8. Critères de clôture

1. Navigation par catégories fonctionnelle, catégorie « General » sélectionnée par défaut.
2. Aucun widget/attribut/méthode publique renommé ou supprimé.
3. Aucune catégorie vide créée pour un domaine non encore implémenté.
4. Boutons Save globaux, comportement de sauvegarde strictement inchangé.
5. Aucune modification Domain/Manager/Storage/EventBus/providers existants.
6. Suite complète verte au nombre exact, `git diff --check` propre, seuls `settings_page.py`/`test_settings_page.py` modifiés.

## 9. Documentation

Cette mission ferme la dette de réorganisation de `SettingsPage` identifiée dès l'incident réel de Mission 115 (QScrollArea) et réévaluée à la hausse une fois le fil ComfyUI Local (Missions 116/117) refermé. La régularisation documentaire post-clôture suit le même processus que les missions précédentes.

## 10. Autorisation

Mission autorisée par l'architecte avec architecture cible fournie explicitement (corrigée une première fois pour distinguer Local/Cloud Image Generation et anticiper Video/Audio Generation) ; audit préalable confirmant l'absence d'écart architectural, implémentation directe conformément à l'autorisation donnée.
