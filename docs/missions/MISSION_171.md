# Mission 171 — Protect Unsaved Renames on PromptsPage, LoRAPage and TrainingPage

> **MISSION 171 CLOSE — implémentation validée par revue architecte, commit fonctionnel et tag publiés, GitHub Release publiée manuellement (références en section 12).** `PromptsPage`, `LoRAPage` et `TrainingPage` écrasaient sans message un nom en cours de saisie (champ `name_edit`, validé seulement à la perte de focus) lors de tout rafraîchissement général : `WORKSPACE_SAVED`, `WORKSPACE_RENAMED`, événements de job d'entraînement, clic sur « Save » de la barre d'outils. Découvert par l'audit global post-Mission 170 (candidat A), reproduit par des sondes à vraie saisie Qt, puis corrigé en reprenant le contrat des Missions 163 et 165 (identité propriétaire, valeur chargée, brouillon dérivé, protection contre la réentrance). Le candidat B (brouillon de métadonnées LoRA) reste hors périmètre. Ce document est rédigé après les validations, sans changement de code depuis.

## 1. Défaut confirmé

- Les trois pages réécrivaient `name_edit` à chaque rafraîchissement général, sans état de brouillon (contrairement à `ModelsPage`/`WorkflowsPage`, Mission 163, et `DatasetsPage`, Mission 165). Le nom saisi mais pas encore validé était remplacé par la valeur persistée, sans message.
- Déclencheurs établis par des sondes (vrais événements clavier, vrai focus, câblage réel de `MainWindow`) sur l'état de `HEAD` avant correction :
  - `WORKSPACE_SAVED` (`editingFinished` = 0, `update_name` = 0, une persistance, texte remplacé) ;
  - événements de job : `TrainingManager.update_job_state()` appelle `WorkspaceManager.save()` (démarrage, fin), la navigation étant libre pendant un job ;
  - `WORKSPACE_RENAMED` (l'objet `Workspace` est remplacé, les ids et les entités actives sont conservés) ;
  - clic sur le bouton Save de la barre d'outils (`MainWindow.save_project()` → `save()`).
- Réentrance : une seconde validation survenant pendant le dialogue d'erreur donnait 2 appels `update_name`, 2 tentatives de persistance et 2 dialogues sur les trois pages.
- Aucune donnée persistée n'était perdue : seul le texte saisi non validé l'était.

## 2. Observations de focus (bornées à l'environnement testé)

Environnement : Qt, plugin hors écran, événements synthétisés par `QTest`.
- Le `QToolButton` de la barre d'outils y est en `focusPolicy=NoFocus` : le clic réel n'a pas déplacé le focus, `editingFinished` n'est pas parti avant la sauvegarde. C'est une propriété observée, **pas** une preuve de l'ordre des événements sur toutes les plateformes ; le scénario asynchrone (événements de job) suffit à établir le défaut.
- L'ouverture du popup du menu File a retiré le focus du champ et déclenché la validation avant l'action (observé dans cet environnement) : le brouillon n'y était pas perdu.
- Un clic réel sur une autre entrée de la liste valide d'abord le nom (le focus change avant la sélection).
- Le comportement des menus natifs de Windows n'a pas été vérifié.

## 3. Contrat (identique sur les trois pages, hors différences listées en 4)

- Trois attributs d'instance par page, initialisés dans `__init__` : `_name_editor_owner_id`, `_name_editor_loaded_value`, `_renaming_in_progress`. États de nom strictement distincts de `_loaded_*_id` (texte Prompts), `_metadata_dirty` (LoRA) et `_dirty` (paramètres Training).
- Un brouillon existe seulement si l'objet actif existe réellement, que son id est celui du propriétaire et que le texte diffère de la valeur chargée (`_has_unsaved_name_draft`).
- Rafraîchissements généraux (`update_*`) : l'éditeur n'est resynchronisé que sans brouillon ; un champ focalisé non modifié, ou revenu à son texte initial, suit donc les changements externes.
- Changements de contexte (`reset_for_context_change`) : resynchronisation forcée, jamais de transfert de brouillon.
- Validation (`rename_*`) : sortie immédiate si une validation est en cours ; objet actif absent ou id différent du propriétaire → rechargement de l'éditeur, aucun appel Manager ; sinon drapeau levé, appel Manager, dialogue d'échec et réconciliation (`_reload_name_editor()`) dans des `try/finally` imbriqués, drapeau libéré même si la réconciliation lève. Commit au blur et no-op idempotent conservés.

## 4. Correction et différences entre pages

Aucun changement de Manager, de `MainWindow`, de Domain, d'`EventBus` ni de moteur ; aucune factorisation entre pages.
- **PromptsPage** : l'écriture du nom se trouvait dans `_refresh_prompt_list` (partagé par `update_prompts` et `reset_for_context_change`) ; elle en est retirée. La synchronisation est placée dans `update_prompts` avant le retour anticipé (`active == _loaded_prompt_id`), qui l'aurait sauté. L'échec n'appelle plus `update_prompts()` : la réconciliation suffit.
- **TrainingPage** : écriture en ligne dans `update_trainings` et littéral dans `reset_for_context_change` ; `update_trainings()` n'est plus appelé sur échec ; `dataset_label` reste resynchronisé sans condition.
- **LoRAPage** : l'écriture se trouvait dans `_load_non_metadata_details`, partagé avec `_force_refresh_lora` ; le nom en est extrait. `update_loras` synchronise sous condition ; `_force_refresh_lora` (et donc `reset_for_context_change`) recharge de façon forcée. Le Manager prend un id explicite : la page lui transmet l'id propriétaire vérifié.
- **LoRA, séquence sur échec** : drapeau levé, appel Manager qui échoue, dialogue, `_force_refresh_lora()` (appel conservé, drapeau toujours levé), puis réconciliation finale et libération du drapeau ; si `_force_refresh_lora()` lève, le `finally` tente quand même la réconciliation et libère le drapeau.

## 5. Limites acceptées

- **Changement d'identité programmatique avec un brouillon** : le brouillon de l'ancienne entité est abandonné sans transfert ni écriture (le focus valide normalement d'abord ; un clic réel sur une autre entrée a été vérifié). Même limite que Missions 163 et 165.
- **Modification externe du même nom pendant un brouillon** : le brouillon est conservé ; la validation suivante écrase la modification externe. Même comportement que Missions 163 et 165.
- Focus des menus natifs Windows non vérifié ; conclusions de focus limitées à l'environnement testé (voir 2).

## 6. Candidat B (LoRA) — hors périmètre, explicitement non traité

- Établi par sondes sur l'état de `HEAD` : l'échec de l'enregistrement d'un renommage ou d'un import de fichiers appelle `_force_refresh_lora()`, qui recharge aussi les champs de métadonnées et efface silencieusement le brouillon de métadonnées (seul le dialogue d'erreur de l'opération échouée est affiché).
- Cette mission conserve l'appel `_force_refresh_lora()` sur l'échec du renommage, textuellement inchangé : le brouillon de métadonnées y reste effacé, comme avant. Aucun test ne fixe ce comportement dans un sens ou dans l'autre ; le candidat B reste ouvert. Un nom en brouillon est lui aussi remis à zéro par les chemins forcés (même fonction).

## 7. Fichiers modifiés

- `src/ui/pages/prompts_page.py` (+57, −22), `src/ui/pages/lora_page.py` (+54, −17), `src/ui/pages/training_page.py` (+52, −22) — fins de ligne CRLF conservées.
- `tests/integration/test_prompt_roundtrip.py` (+411, −1, LF), `tests/integration/test_lora_roundtrip.py` (+453, −1, LF), `tests/integration/test_training_roundtrip.py` (+438, −1, CRLF) — la seule suppression de chaque fichier est la ligne d'import `PySide6.QtCore` étendue ; toutes les classes sont ajoutées avant le bloc `unittest.main()` final.
- `tests/integration/test_main_window_name_drafts.py` (nouveau, 235 lignes, LF) ; `docs/missions/MISSION_171.md` (ce document).

## 8. Tests

**60 nouveaux tests** : Prompts 17 (4 + 8 + 5), LoRA 19 (4 + 8 + 7), Training 18 (5 + 8 + 5), MainWindow 6 (3 + 3). Trois familles séparées par classe :
- **Régressions comportementales** (16) : échouent sur la production précédente, sans lire d'attribut privé : brouillon survivant à des `WORKSPACE_SAVED` répétés puis validé une fois à la perte de focus réelle ; survie à `WORKSPACE_RENAMED` et validation sur la même entité ; réentrance forcée (compteurs distincts `update_name` / persistance / dialogue = 1 / 1 / 1) ; coexistence avec le texte Prompts, les paramètres Training et les métadonnées LoRA ; Training : événements de job ; MainWindow : clic réel sur Save de la barre d'outils.
- **Invariants** (27) : déjà vrais avant (champ focalisé non modifié qui suit un renommage externe, brouillon revenu au texte initial, changement d'identité sans transfert, clic réel qui valide d'abord, fermeture/réouverture sans résurrection, suppression de l'entité active, succès avec rafraîchissement synchrone, échec avec restauration, Entrée puis perte de focus = une persistance, File > Sauvegarder).
- **Tests du nouveau contrat** (17) : lisent l'état privé ; non exécutables avant correction (un `AttributeError` n'est pas une preuve du défaut) : id propriétaire différent de l'objet actif, valeur chargée rebasée, drapeau tenu pendant le dialogue et libéré, échec de réconciliation, reset forcé ; LoRA : id propriétaire transmis au Manager, `_force_refresh_lora()` appelé une fois après le dialogue sous le drapeau, jamais sur le succès.
- Fixtures : fenêtres/pages fermées et libérées (`close`, `deleteLater`, traitement des destructions différées), mocks de dialogue installés avant et levés après la libération, `LOCALAPPDATA` redirigé pour `MainWindow`, aucun GC modifié, aucune classe exécutée dans un processus séparé pour masquer un arrêt.

## 9. Résultats, par nature (ne pas confondre)

**9.1 Sondes sur le dépôt avant correction** (hors dépôt, vrais événements Qt) : défaut reproduit sur les trois pages (§1) ; clic réel sur une autre entrée : validation d'abord ; `select(B)` programmatique : brouillon remplacé sans écriture sur B ; fermeture/réouverture : éditeur vidé ; réentrance 2 / 2 / 2 ; Entrée puis perte de focus : 2 `update_name`, 1 persistance effective.

**9.2 Résultats du prototype** (sous-classes dynamiques, hors dépôt — mécanisme de sonde, pas le code livré) : matrice M1 à M11 (vrai `MainWindow`) 100/100 ; scénarios propres à chaque page 4/4, 3/3, 2/2. Même matrice sur une copie de `HEAD` : 60/94, soit 34 échecs (22 comportementaux observables, 12 assertions d'état privé) et 3 scénarios non exécutables avant correction.
- **Arrêts du prototype, cause inconnue.** Exécuté sur les tests `LoRAPage` existants dans l'environnement du harnais de sonde, le prototype a fait sortir le processus en code 127 avec `STATUS_HEAP_CORRUPTION` (`0xc0000374`) détecté dans un constructeur `QWidget` du `setUp` de `LoRAPageComfyUIExposureTest` (installation d'un filtre d'événements applicatif juste avant) : plus d'une quinzaine d'arrêts sur des variantes diverses, sur le dépôt comme sur une copie avec caches `.pyc`. Contrôles sans arrêt : dépôt (au moins 4/4), sous-classe nulle (3/3), copie identique par `exec` (2/2), ajouts inertes (2/2), prototype avec GC désactivé (2/2) ou sous contrainte (1/1), prototype sur copie sans `.pyc` (6/6). **Cause inconnue** : ni l'implication de la logique, ni celle du mécanisme dynamique, ni celle du GC n'est démontrée ; une signature proche de Missions 097/164 ne démontre pas une cause commune.

**9.3 Intégration isolée** (hors dépôt ; copie A = `HEAD` octet pour octet avec le working tree, copie B = A + le changement intégré directement aux classes ; seuls les trois fichiers de pages diffèrent ; sources réellement chargées vérifiées) : l'intégration directe n'a **pas reproduit** l'arrêt dans les 21 exécutions réalisées (groupe minimal de 3 classes, groupe des 13 classes `LoRAPage*`, fichier LoRA entier ; avec et sans `.pyc`, deux harnais), A (HEAD) dans 18 exécutions. Cette observation n'explique pas l'arrêt du prototype et ne démontre pas qu'aucun arrêt ne peut survenir dans un contexte non testé.
- **Série de six exécutions mal dirigées, écartée comme invalide** : un paramètre de chemin du harnais n'avait pas été pris en compte (commande `sed` sans effet) ; ces six exécutions ont tourné sur le dépôt et non sur les copies. Elles sont conservées à part et ne servent à aucune conclusion.

**9.4 Validations fraîches du dépôt, état final** (code intégré, GC normal, une exécution à la fois, limites externes, codes de sortie réels) :
1. Nouvelles classes ciblées : Prompts 17/17, LoRA 19/19, Training 18/18, MainWindow 6/6 — exit 0.
2. Fichiers complets : `test_prompt_roundtrip.py` 137 (120 avant), `test_lora_roundtrip.py` 294 (275), `test_training_roundtrip.py` 430 (412), `test_main_window_name_drafts.py` 6 — tous OK, exit 0.
3. Fichier LoRA complet : trois exécutions (294 tests), toutes OK, exit 0, aucun arrêt natif.
4. Exécution directe des quatre fichiers (`PYTHONPATH` = racine) : 4/4 exit 0.
5. **Suite complète : 3264 tests, OK, exit 0** (383 s, sortie non tamponnée, une seule exécution) ; 3264 = 3114 (référence M169) + 90 (M170) + 60 (M171). Les lignes « Failed to copy… », « Access denied while renaming workspace folder… » et le message `QLabel.setText(MagicMock)` d'`inference_page.py` sont de la journalisation de tests existants ; ce dernier se reproduit à l'identique sur la copie de `HEAD` (`test_inference_page.py` 230/230).

**9.5 Preuve avant/après** (copie isolée de `HEAD`, tests nouveaux compatibles avec l'ancienne production ; pilote hors dépôt ; sources chargées vérifiées par empreinte) : sur la production précédente, **16 méthodes de régression échouent par assertion** (Prompts 4, LoRA 4, Training 5, MainWindow 3 ; 0 erreur ; chaque méthode s'arrête à sa première assertion échouée) et **27 invariants passent** ; sur l'état final, les 43 méthodes passent. Le pilote s'est terminé normalement (exit 0) dans les deux cas : cela ne constitue pas, en soi, un verdict de validation. Les 17 tests du nouveau contrat ne font pas partie de cette preuve.

## 10. Incidents et inconnues

- Arrêt natif du prototype (9.2) : cause inconnue, non reproduit avec le code intégré dans les exécutions réalisées.
- Une première application scriptée de la modification a échoué sur une ancre non unique avant toute écriture ; une copie par `git archive` convertissait les fins de ligne et a été remplacée par une copie du working tree. Aucun fichier du dépôt n'a été touché par ces incidents.
- Un remplacement de `QMessageBox.exec` mal formé dans le harnais de sonde avait provoqué un arrêt (code 139) : défaut de sonde, corrigé.
- Message `QLabel.setText(MagicMock)` : préexistant (9.4).

## 11. Hors périmètre et pistes ouvertes (liste non ordonnée, aucune sélectionnée)

Candidat B (métadonnées LoRA) ; exceptions brutes des moteurs dans les diagnostics de connexion (SettingsPage / Inference) ; primitives de copie et d'import hors frontière d'erreur (`copy_into_workspace`, `preview_collisions`, `add_images`) ; `LoRALibraryManager._expose()` ; faux négatif possible de `taskkill` au Stop Forge (hypothèse) ; sortie 127 des fichiers de tests de lifecycle ; suffixes réservés OneTrainer `-masklabel`/`-condlabel` ; BOM UTF-8 des sidecars ; liste de jobs de `TrainingPage` périmée après modification de la bibliothèque LoRA ; suppression de Dataset/Training vis-à-vis des références ; perte de sélection au renommage du Workspace ; dérives documentaires (README, « 12 Managers ») ; incidents natifs de la Mission 164.

## 12. Références Git et publication (régularisation documentaire post-Release)

Section ajoutée par la régularisation documentaire, après la publication de la Release ; elle ne modifie ni les sections 1 à 10 ni les résultats qu'elles rapportent. La bannière de statut de ce document et la dernière phrase de la section 11, telles qu'elles figurent dans le commit fonctionnel, indiquaient « publication en attente » / « Mission non close » ; elles sont mises à jour par cette régularisation (la phrase de la section 11 est supprimée).

- **Commit fonctionnel** : `da928221b97f2d63a741ce96516825412c7cd570` — « Protect unsaved prompt, LoRA and training renames » ; parent `5e645498d85c5e4d4b2b6d24c3300eca98eeee92` (« Document Mission 170 completion ») ; 8 fichiers (`src/ui/pages/prompts_page.py`, `src/ui/pages/lora_page.py`, `src/ui/pages/training_page.py`, `tests/integration/test_prompt_roundtrip.py`, `tests/integration/test_lora_roundtrip.py`, `tests/integration/test_training_roundtrip.py`, `tests/integration/test_main_window_name_drafts.py`, `docs/missions/MISSION_171.md`) ; 1793 insertions, 64 suppressions (mesurées par `git show --numstat`, et non par une somme de lignes modifiées).
- **Tag annoté** `v0.2-mission171` : objet `7f1acf132b8d8ebe3abd03a77a4c631d123bcd5d`, cible `da928221b97f2d63a741ce96516825412c7cd570` (message « Mission 171: protect unsaved prompt, LoRA and training renames »). Commit et tag ont été publiés par un push normal de `main` sans force (`5e64549..da92822`), puis par le push du seul tag ; type, objet et cible déréférencée identiques en local et à distance.
- **Tags antérieurs inchangés** : `v0.2-mission170` (objet `5b66682320e4f7f5d2c4f3380fb241bdd0fcf328`, cible `86090cb4d6de2befbe8701e7c9cf4ebae3e36366`, local et distant) ; `v0.2-mission169` (objet `e915973db3820557cd11a5078dd43a14b1090990`, cible `12cfa60a33dc1a0c2223657f976b8887e0a5c030`).
- **GitHub Release** : publiée manuellement par l'architecte (confirmation), puis constatée lors de la régularisation par une lecture non authentifiée de l'API publique GitHub (HTTP 200) : titre « v0.2-Mission171 — Protect Unsaved Prompt, LoRA and Training Renames » (le titre proposé « Mission 171 — Protect Unsaved Prompt, LoRA and Training Renames » diffère par le préfixe `v0.2-Mission171`, le titre réel fait foi ; l'origine de ce préfixe n'est pas établie ici), `tag_name` `v0.2-mission171`, `draft` `false`, `prerelease` `false`, `published_at` `2026-10-06T07:01:01Z` (création `2026-10-06T06:59:32Z`, `target_commitish` `main`, aucun asset), URL https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission171. Le corps (4316 caractères, fins de ligne CRLF) a été relu intégralement : il reprend, à la lecture, le texte proposé et les faits consignés dans ce document. Cette vérification technique est distincte de la confirmation de publication donnée par l'architecte ; elle n'a pas échoué.
- **Formulation de la Release à signaler** : la section « Problem » présente le clic sur le bouton Save de la barre d'outils parmi les déclencheurs reproduits sans en borner l'énoncé à l'environnement ; ce document (section 2) limite cette observation au plugin Qt hors écran avec événements synthétisés, et la section « Known limitations » de la Release énonce cette borne. Les deux textes ne se contredisent pas, mais la Release est plus affirmative dans sa première section ; elle n'est pas modifiée par cette étape.
- **Chronologie des résultats** : sondes sur le dépôt avant correction (9.1), prototype (9.2), intégration isolée sur copies (9.3), validations fraîches du dépôt (9.4) et preuve avant/après (9.5) sont des résultats de nature différente et ne se substituent pas. La dernière suite complète réussie est **3264 tests, code 0**, sur l'état final de Mission 171 ; 3264 = 3114 + 90 + 60, le total de 3204 attendu à la clôture de Mission 170 n'ayant jamais été exécuté seul. Aucun test n'a été relancé par la régularisation.
- **Incidents et limites conservés** : arrêts natifs du prototype de cause inconnue, non reproduits dans les validations du code intégré, sans être déclarés résolus ; six exécutions mal dirigées écartées comme invalides ; commit-on-blur conservé ; pas de transfert de brouillon lors d'un changement d'identité ; une validation peut remplacer une modification externe du même nom ; candidat B LoRA toujours ouvert (le rafraîchissement forcé sur échec peut effacer un brouillon de métadonnées) ; conclusions de focus bornées à l'environnement Qt testé.
- **Statut** : Mission 171 entièrement close. Aucune Mission 172 n'est sélectionnée ; un nouvel audit global READ-ONLY post-Mission 171 devra précéder toute décision. Les pistes ouvertes (section 11) restent non classées et non sélectionnées.
