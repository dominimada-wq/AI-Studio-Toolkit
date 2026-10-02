# Mission 165 — Protect Unsaved Dataset Name Edits in DatasetsPage

> **MISSION ENTIÈREMENT CLOSE — commit fonctionnel, tag et GitHub Release publiés.** `DatasetsPage.name_edit` est un champ en commit-on-blur (`editingFinished` uniquement, aucun bouton Save, aucun suivi de brouillon) : `update_datasets()` l'écrasait inconditionnellement à chaque `WORKSPACE_SAVED`/`WORKSPACE_RENAMED`/`CHARACTER_CREATED`/`DATASET_*`, effaçant silencieusement un renommage en cours de frappe dès qu'un événement sans rapport survenait ailleurs dans le même Workspace (ex. un Training terminant en arrière-plan, ou un clic sur « Sauvegarder »). Découvert par l'audit global post-Mission 164 (candidat G3), conçu READ-ONLY, puis implémenté strictement dans le périmètre validé : `DatasetsPage` uniquement. Commit fonctionnel `571f898efc2cf7f3c2b4e761974ec6a5f28af5fd`, tag annoté `v0.2-mission165` (objet `f5f5bf28db1bf4d3fc41c0c57cfc18a45b1b25cc`, cible `571f898efc2cf7f3c2b4e761974ec6a5f28af5fd`), GitHub Release publiée manuellement — références vérifiées en section 10.

## 1. Défaut initial

`src/ui/pages/datasets_page.py::update_datasets()` appelait `self.name_edit.setText(active_name)` sans condition. `QLineEdit.setText()` n'émettant jamais `editingFinished`, un nom tapé mais pas encore commité (Entrée ou perte de focus) était remplacé par le nom du Domain, sans avertissement ni récupération. `rename_dataset()` agissait sur `active_dataset_id` sans jamais vérifier à quel Dataset le texte de l'éditeur appartenait, et ne protégeait pas contre une seconde `editingFinished` pendant le dialogue d'erreur.

## 2. Preuve empirique (état antérieur à la correction)

Observations avec un `MainWindow()` réel (câblage réel, plateforme Windows native, focus réel, vraies frappes `QTest.keyClicks`) :

| Scénario | Résultat avant correction |
|---|---|
| Frappe, puis `WORKSPACE_SAVED` sans rapport | texte redevenu `'Portraits'`, `editingFinished` émis 0 fois |
| Frappe, puis `WORKSPACE_RENAMED` | brouillon perdu |
| Frappe, puis clic souris réel sur le bouton Sauvegarder de la barre d'outils | brouillon perdu ; le clic ne persiste pas le nom (`editingFinished` non émis, focus conservé dans le champ) |
| Échec de `save()` avec une seconde `editingFinished` pendant le dialogue | 2 dialogues d'erreur, 2 tentatives de persistance |
| Entrée puis perte de focus réelle | 1 seule persistance (inchangé : `update_name()` est idempotent) |
| Clic réel sur un autre Dataset avec un brouillon | l'ancien est commité par la perte de focus, le nouveau devient actif (inchangé) |

Ces observations sont limitées aux scénarios réellement exécutés ; aucune garantie universelle n'en est déduite.

## 3. Contrat

1. Un événement de rafraîchissement sans rapport (`WORKSPACE_SAVED/RENAMED`, `CHARACTER_CREATED`, `DATASET_CREATED`, changement de tri) ne remplace jamais un brouillon réel du nom pour le **même Dataset actif**.
2. Un brouillon n'existe que si l'objet actif existe, que son identité est celle chargée dans l'éditeur, et que le texte diffère de la valeur chargée — jamais déduit du focus.
3. Un éditeur propre reflète toujours le Domain.
4. Changement d'identité ou de contexte : l'éditeur est rechargé. Pour un clic réel, la perte de focus a déjà commité le brouillon sur le Dataset qui était actif.
5. `rename_dataset()` ne persiste jamais un texte chargé pour une autre identité ni sans objet actif (existence vérifiée sur l'objet, jamais déduite de l'id seul).
6. Après succès, no-op idempotent ou échec avec rollback : l'éditeur est réconcilié sur la valeur canonique, indépendamment du focus.
7. Garde de réentrance couvrant l'appel Manager, le dialogue et la réconciliation, toujours libérée.

Le commit-on-blur, les règles de nom existantes (aucun strip, `""` légitime) et les messages d'erreur sont inchangés.

## 4. Correction

**Production (1 fichier)** : `src/ui/pages/datasets_page.py` — trois attributs `_name_editor_owner_id`, `_name_editor_loaded_value`, `_renaming_in_progress`, indépendants de tout état `_caption_*` ; `rename_dataset()` (garde de réentrance, vérification d'identité avant écriture, `finally` imbriqué qui réconcilie puis libère la garde) ; `_reload_name_editor()` ; `_has_unsaved_name_draft()` ; le `setText` de `update_datasets()` devient conditionnel ; `reset_for_context_change()` force `_reload_name_editor()` après `update_datasets()`. Le `self.update_datasets()` du `except` de `rename_dataset()` est remplacé par la réconciliation du `finally` (il ne restaurerait plus le nom une fois la garde de brouillon en place). Aucune modification de Manager, de `MainWindow`, de la logique de caption, ni des trois Pages voisines ; aucune factorisation.

**Précision A — reset de contexte.** Le `_reload_name_editor()` forcé ne rend pas le code indépendant de l'ordre des abonnés : il relit lui aussi le Manager. L'ordre réel a donc été vérifié et testé : `DatasetManager` est construit avant la page (dans `MainWindow` comme dans le harnais) et s'abonne le premier aux événements de contexte ; au moment où le handler de reset de la page s'exécute, `active_dataset_id` vaut `None`. Constaté sur les 4 contextes testés (`WORKSPACE_CLOSED`, `WORKSPACE_CREATED`, `WORKSPACE_OPENED` y compris une réouverture du même dossier — mêmes `dataset_id` —, `CHARACTER_SELECTED`), avec le câblage de harnais et avec le `MainWindow` réel. Constat complémentaire (observé avec `create_workspace_with_default_character()`) : la création d'un Workspace publie `WORKSPACE_SAVED`, `CHARACTER_CREATED` et `CHARACTER_SELECTED` **avant** `WORKSPACE_CREATED` ; les rafraîchissements intermédiaires voient encore l'ancien id actif, mais celui-ci ne correspond à aucun objet du nouveau Workspace et ne compte donc jamais comme brouillon. Le reset forcé n'est utilisé ni pour `WORKSPACE_SAVED`, ni pour `WORKSPACE_RENAMED` (vérifié par le câblage et par un test).

**Précision B — annulation avec caption modifiée.** Un clic réel sur un autre Dataset déplace d'abord le focus : `editingFinished` peut commiter le nom **avant** que le dialogue de caption n'apparaisse. Le contrat testé est donc : aucune perte du texte du nom (brouillon ou déjà persisté), caption modifiée conservée, sélection et contexte restaurés par les gardes existantes, aucune écriture sur le mauvais Dataset — et non « le nom reste non enregistré ».

## 5. Fichiers modifiés

- `src/ui/pages/datasets_page.py` (production).
- `tests/integration/test_dataset_roundtrip.py` — 2 classes ajoutées (26 tests) ; 3 imports ajoutés.
- `tests/integration/test_datasets_page.py` — 1 classe ajoutée (6 tests) ; imports ajoutés.
- `docs/missions/MISSION_165.md` (ce document).

## 6. Tests ajoutés (32)

**`DatasetsPageNameDraftProtectionTest`** (23, `test_dataset_roundtrip.py`) — `_wire()` reproduit les abonnements réels de `main_window.py` pour `DatasetsPage` (dont `WORKSPACE_RENAMED`, `CHARACTER_CREATED`, et les 5 événements de reset routés vers `reset_for_context_change()`), le Manager étant construit avant la page :
- `WORKSPACE_SAVED` sans rapport : aucun renommage, aucune sauvegarde supplémentaire causée par le rafraîchissement (la sauvegarde explicite du test est comptée : exactement 1), aucun rechargement ; brouillon conservé ;
- événements répétés et `WORKSPACE_RENAMED` (callback effectivement atteint, vérifié en substituant l'entrée dans la liste d'abonnés de l'`EventBus`) ;
- `CHARACTER_CREATED`, `DATASET_CREATED` et changement de tri ;
- éditeur propre reflétant une mise à jour Domain, avec focus ; retour au nom initial (aucune persistance) ;
- succès avec callback synchrone (callback atteint pendant que la garde est tenue ; 1 `update_name`, 1 `save`) ; Entrée puis perte de focus réelle (1 seule persistance) ;
- échec avec rollback, avec et sans focus, puis nouvel essai qui persiste ;
- discordance d'identité construite **sans refresh intermédiaire** (état vérifié avant l'appel direct à `rename_dataset()`) ; aucun objet actif ; id actif sans objet ; `DATASET_SELECTED` programmatique ; `DATASET_DELETED` ; clic réel sur un autre Dataset ;
- réentrance pendant le dialogue : `update_name()`, tentatives de persistance (WorkspaceManager et Storage) et dialogues comptés séparément (1 chacun) ; garde libérée même si la réconciliation lève (cas nominal et cas après échec de sauvegarde) ;
- resets forcés : fermeture, création, réouverture du même Workspace (mêmes ids), `CHARACTER_SELECTED` — le contexte Domain est capturé au moment exact où le handler de reset s'exécute ; reset forcé non câblé sur `WORKSPACE_SAVED/RENAMED`.

**`DatasetsPageNameDraftMainWindowTest`** (3, `test_dataset_roundtrip.py`, `MainWindow()` réel) : clic souris réel sur le bouton Sauvegarder de la barre d'outils — le brouillon reste affiché ; le nom est persisté **si et seulement si** `editingFinished` a été émis pendant le clic (le clic ne persiste jamais le nom par lui-même ; ce que la plateforme émet n'est volontairement pas affirmé) ; le commit reste déclenché par `editingFinished` ; ordre réel des abonnés pour `WORKSPACE_CLOSED` et pour une réouverture du même dossier.

**`DatasetsPageNameAndCaptionDraftTest`** (6, `test_datasets_page.py`) : brouillons nom et caption conservés ensemble sur `WORKSPACE_SAVED` ; caption conservée après un renommage réussi puis après un échec de renommage (nom restauré) ; sauvegarde de la caption sans commit ni perte du brouillon de nom ; annulation du changement de Dataset avec caption modifiée (précision B) ; choix « Ignorer » : le nom est commité sur le bon Dataset uniquement.

**Dispositif** : les trois classes arment le filet de sécurité du projet (`tests/integration/_qt_dialog_safety_net.py`, Mission 091) en premier — arrêté en dernier — de sorte qu'un `QMessageBox` réel inattendu est fermé au tick suivant et transformé en `UnexpectedDialogError`, jamais en attente d'un clic humain.

## 7. Résultats

**Preuve avant/après** (fichier de production seul mis de côté par `git stash push -- <fichier>`, puis restauré — diff de production vérifié identique après restauration, aucun stash restant) :
- Sonde comportementale sans aucune référence à un attribut M165 : avant → `P1` `'Portraits'` (brouillon perdu), `P2` perdu, `P3` perdu après clic réel sur Sauvegarder, `P4` 2 dialogues et 2 tentatives de persistance ; après → `P1`–`P3` `'Portraits EDIT'` conservé, `P4` 1 dialogue et 1 tentative.
- Les 32 nouveaux tests contre la production antérieure : **12 échecs et 14 erreurs** (les erreurs étant des `AttributeError` sur les nouveaux attributs, les échecs des assertions comportementales dont `'Alpha' != 'Alpha EDIT'` ; dans le test de réentrance, dont le faux dialogue ré-entre à chaque appel, 163 appels `update_name` récursifs contre 1 attendu — un cas de contrainte, pas un scénario utilisateur) ; contre la production corrigée : **32/32 OK**. Ces deux exécutions ont été refaites avec le dispositif corrigé (§8), entièrement automatisées (10 s et 11 s). **Lecture de ces résultats** : seule la sonde comportementale, qui ne référence aucun attribut M165, constitue une preuve indépendante du défaut initial. Les 14 erreurs `AttributeError` de la suite « avant » viennent d'attributs absents de l'ancien code et ne prouvent pas, individuellement, le défaut ; les échecs d'assertion comportementale le montrent, hors cas de contrainte du test de réentrance.

**Validation après correction** :
- 3 classes nouvelles : 32/32 OK.
- `test_dataset_roundtrip.py` complet : **167/167** OK (141 avant la mission).
- `test_datasets_page.py` complet : **94/94** OK (88 avant la mission).
- Non-régression ciblée (`DatasetsPageRenameTest`, `DatasetsPageCaptionPanelTest`, `DatasetsPageConfirmContextChangeTest`, `DatasetsPageImagesSelectionPreservationTest`) : 50/50 OK.
- **Suite complète** (premier plan, `-u -v`, une seule exécution à la fois) : **3002 tests, OK, exit 0, 351,229 s** ; 2970 (référence M164) + 32 nets = 3002, cohérent. Aucune ligne `FAIL`/`ERROR` dans la sortie.
- `git diff --check` : clean. Exactement 1 fichier de production et 2 fichiers de test modifiés, plus ce document.

## 8. Incident d'exécution pendant la validation (conservé pour traçabilité)

Pendant une exécution de la preuve « avant » (production antérieure remise temporairement en place), un vrai dialogue a été affiché sur la fenêtre Datasets d'un `MainWindowNameDraftProject` : « Impossible d'enregistrer le renommage dans le projet : Could not write project.json… Le nom précédent a été restauré. » L'utilisateur a dû cliquer manuellement sur OK ; **cette exécution (320 s) n'est donc pas présentée comme entièrement automatisée** et son résultat n'a pas été retenu — elle a été refaite.

- **Test concerné** : `DatasetsPageNameDraftMainWindowTest.test_real_wiring_reopening_the_same_workspace_never_carries_the_draft` (reproduit, avec l'ancien ordre de nettoyage et la production antérieure, par `UnexpectedDialogError` capturant ce dialogue exact).
- **Cause (établie par reproduction)** : une erreur de nettoyage dans le dispositif de test, pas une erreur injectée ni un défaut de production. `setUp` enregistrait `window.close` avant `rmtree` ; les nettoyages s'exécutant en ordre inverse, le dossier du Workspace était supprimé **avant** la fermeture de la fenêtre. Sur la production antérieure, une assertion échoue en cours de test (`AttributeError` sur un attribut M165) en laissant un brouillon dans `name_edit` ; la fermeture de la fenêtre déclenche alors `editingFinished`, donc un vrai renommage vers un `project.json` disparu (`save()` échoue sur le fichier temporaire manquant), donc un vrai `QMessageBox.critical` bloquant. Contrôle : avec la production corrigée et le même ancien ordre, 0 échec, 0 dialogue.
- **Résultat après fermeture du dialogue** : message du dialogue conforme (« Le nom précédent a été restauré ») ; aucune écriture hors du dossier temporaire du test ; le test en échec attendu restait en échec pour sa cause propre.
- **Correction (dispositif de test uniquement, aucun changement de production)** : (1) filet de sécurité du projet armé en premier, arrêté en dernier, dans les trois classes ; (2) dans la classe `MainWindow`, dossier temporaire enregistré avant la fenêtre, donc fenêtre fermée avant la suppression du dossier. Aucune erreur masquée : un dialogue réel inattendu fait échouer le test avec son texte exact.
- **Relances** : les 3 tests concernés 3/3 OK, puis les 32 tests avant/après, puis la suite complète, aucune exécution concurrente.

## 9. Limites, écarts constatés et hors périmètre

- **Pistes voisines non traitées** : `TrainingPage`, `LoRAPage` et `PromptsPage` perdent le même nom en commit-on-blur (observé par exécution, chacune avec une structure de rafraîchissement propre) — candidats distincts pour des missions ultérieures.
- **Écart préexistant, distinct, non corrigé** : un `WORKSPACE_RENAMED` (renommage de projet) remappe tous les chemins d'images internes ; la restauration de sélection d'`update_datasets()` étant indexée par `file_path` (Mission 082), une caption modifiée est perdue dans ce scénario, et `MainWindow.rename_project()` n'exécute délibérément aucune garde de brouillon. Constaté en écrivant `test_unrelated_events_preserve_both_the_name_draft_and_the_caption_draft`, dont l'assertion sur la caption est volontairement limitée à `WORKSPACE_SAVED`. Non traité (les gardes M098/M158/M159/M160 ne sont pas modifiées).
- **Nouveau délai visible** : un clic sur Sauvegarder laisse désormais le brouillon affiché sans le persister (avant : retour silencieux à l'ancien nom). Il reste commité par `editingFinished` ; la fermeture réelle de la fenêtre l'a commité dans l'expérience réalisée, sans garantie universelle.
- **Non testé** : l'action de menu « Sauvegarder » (focus de type popup possible) ; le comportement hors plateforme Windows native de cette session ; un vrai transfert de focus vers un `QMessageBox` pendant l'échec (la seconde `editingFinished` est simulée par appel direct) ; une modification externe du Domain sous un brouillon (le commit écrase alors, par action explicite de l'utilisateur).
- Les gardes globales New/Open/Close restent hors périmètre : un brouillon de nom n'est pas protégé lors d'un changement de Workspace (inchangé).

## 10. Références Git (vérifiées lors de la clôture documentaire)

- **Commit fonctionnel** : `571f898efc2cf7f3c2b4e761974ec6a5f28af5fd` (`Protect unsaved dataset renames`), parent `de2554f93bb69343d6a36aba15505221a352fe56` — exactement 4 fichiers (`docs/missions/MISSION_165.md`, `src/ui/pages/datasets_page.py`, `tests/integration/test_dataset_roundtrip.py`, `tests/integration/test_datasets_page.py`), 1253 insertions, 19 suppressions.
- **Tag annoté** : `v0.2-mission165`, objet `f5f5bf28db1bf4d3fc41c0c57cfc18a45b1b25cc`, cible déréférencée `571f898efc2cf7f3c2b4e761974ec6a5f28af5fd` — vérifié identique en local et sur le remote ; le tag cible le commit fonctionnel, jamais un commit documentaire.
- **GitHub Release** : publiée manuellement par l'architecte, rattachée au tag `v0.2-mission165` ; titre constaté sur GitHub : « v0.2-Mission165 — Protect Unsaved Dataset Renames ». Publication confirmée par l'architecte **et** constatée lors de cette clôture par une lecture non authentifiée de l'API publique GitHub (`tag_name` = `v0.2-mission165`, `draft` = `false`, `prerelease` = `false`, publiée le 2026-10-02, URL https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission165) ; cette lecture n'a vérifié que la présence d'un corps non vide et de quelques termes clés (tests, limites), pas le contenu intégral de la Release.
- **Tag précédent** : `v0.2-mission164` confirmé inchangé — objet `cc3a875bb7d347445bfb58a00fe39b4f0f43a55d`, cible `22f6ec6a9220600c7b60f71c9962f87ae23dc312`.
- Résultats de validation : voir sections 7 et 8 — non modifiés par cette clôture, aucun test relancé pour la seule régularisation documentaire.
- Voir `CHANGELOG.md` (section Mission 165) et `docs/PROJECT_CONTEXT.md` (« Dernière mission terminée ») pour la régularisation documentaire complète.
