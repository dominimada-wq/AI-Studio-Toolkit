# Mission 050 — Remove Individual Files from a LoRA

> **STATUT : IMPLÉMENTATION TERMINÉE ET VALIDÉE TECHNIQUEMENT — CLÔTURE GIT NON ENCORE EFFECTUÉE.**
> 19/19 tests ciblés nets nouveaux (nouvelle classe `LoRAManagerRemoveFilesTest` + extension `LoRARoundTripTest`), 859/859 tests automatisés verts, smoke test manuel réel du rendu Qt PASS. Aucun commit, tag ni Release n'existe encore pour cette mission (voir "Principe de non-auto-référence", `docs/PROJECT_CONTEXT.md`) — voir la section "État d'avancement" en fin de document pour le détail exact.

## 1. Contexte

Un audit read-only du dépôt après clôture de Mission 049 a confirmé que `LoRA.files` (`src/domain/lora.py`) est une `list[str]` de chemins de fichiers externes, alimentée exclusivement par `LoRAManager.add_files()` (ajout, déduplication par égalité de chaîne exacte). **Aucune méthode `remove_files()` n'existe** sur `LoRAManager`, et `LoRAPage.files_list` ([lora_page.py:64](src/ui/pages/lora_page.py:64)) est un simple `QListWidget` en lecture seule — aucune sélection étendue, aucun bouton de retrait, aucun moyen de corriger une erreur d'ajout individuelle sans supprimer la LoRA entière (`delete_lora()`) et la recréer.

Ce constat mirroir exactement la situation résolue pour `Dataset.images` par Mission 045 (`DatasetManager.remove_images()`, bouton « Retirer du dataset ») — avant cette mission, seule la suppression d'un Dataset entier existait. Le même défaut existe aujourd'hui pour `LoRA.files`, et sa correction est devenue **plus urgente depuis Mission 047** : `LoRA` porte désormais des métadonnées réellement éditables (`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`) — supprimer puis recréer une LoRA entière pour corriger un simple fichier mal importé ferait perdre l'intégralité de cette fiche, une conséquence bien plus coûteuse qu'avant Mission 047.

**Comparaison avec `Model`/`Workflow`** : ces deux classes n'ont pas ce défaut — `Model.file_path`/`Workflow.file_path` sont des scalaires uniques, et `ModelManager.update_file_path()`/`WorkflowManager.update_file_path()` permettent déjà de corriger un chemin sans recréer l'entité. `LoRA.files` est délibérément une liste (choix documenté dans `src/domain/lora.py` : "mirrors Dataset.images, avoiding a future migration once multiple files need to be associated with one LoRA") — c'est cette spécificité de collection qui crée le besoin d'un retrait individuel, absent des deux autres classes par construction.

## 2. Problème

Il n'existe aujourd'hui aucun moyen de retirer un fichier individuel d'une LoRA sans supprimer la LoRA entière — perdant au passage son nom et l'ensemble de sa fiche de métadonnées (Mission 047).

## 3. Objectif

Permettre de retirer un ou plusieurs fichiers sélectionnés de la LoRA active, sans jamais supprimer le fichier physique (les fichiers LoRA restent des chemins externes, jamais copiés — Mission 047 l'a confirmé et n'a pas changé cette politique), sans confirmation (cohérent avec le précédent non-destructif de Mission 045).

## 4. Contrat fonctionnel validé

- Nouvelle méthode `LoRAManager.remove_files(paths: List[str]) -> int`, symétrique à `add_files()` : comparaison par égalité de chaîne exacte (même convention que `add_files()` — jamais une résolution de chemin, `LoRA.files` n'étant jamais copié ni normalisé), retire chaque chemin présent dans `lora.files`, sauvegarde (`WorkspaceManager.save()`) uniquement si au moins une mutation réelle a eu lieu, retourne le nombre de fichiers effectivement retirés. Aucun événement dédié publié (mêmes conventions que `DatasetManager.remove_images()`).
- Ne supprime jamais le fichier physique — `LoRA.files` référence toujours des chemins externes, jamais copiés (confirmé inchangé depuis Mission 047).
- Aucune confirmation avant retrait — cohérent avec le précédent établi par Mission 045 (retrait de référence, non destructif).
- `LoRAPage.files_list` passe en `QListWidget.ExtendedSelection` (retrait multiple en une seule opération), nouveau bouton « Retirer les fichiers sélectionnés », activé/désactivé selon la présence d'une sélection (mirroir du mécanisme d'état déjà établi ailleurs dans le projet — `_update_enlarge_button_state()`/`_update_metadata_buttons_state()`).
- Retirer la dernière référence d'un fichier laisse simplement `files_list` vide — aucun traitement spécial.
- Rafraîchissement via le canal `WORKSPACE_SAVED` déjà existant (déjà abonné à `LoRAPage.update_loras()`) — aucun nouveau wiring EventBus.

## 5. Périmètre

Production (2) :
- `src/managers/lora_manager.py` (nouvelle méthode `remove_files()`)
- `src/ui/pages/lora_page.py` (`files_list` en `ExtendedSelection`, nouveau bouton « Retirer les fichiers sélectionnés », méthode `remove_selected_files()`, extension de l'état des boutons)

Tests (1, aucun nouveau fichier) :
- `tests/integration/test_lora_roundtrip.py` (convention déjà établie pour LoRA : tests Manager et tests Qt réels de `LoRAPage` cohabitent dans ce seul fichier depuis son origine)

## 6. Hors périmètre

- Toute modification de `Model`/`Workflow`/`ModelManager`/`WorkflowManager` (déjà couverts par `update_file_path()`, aucun défaut identifié).
- Tout changement de la politique de fichiers LoRA (toujours externes, jamais copiés — inchangé depuis Mission 047).
- Toute confirmation avant retrait (non destructif, cohérent avec Mission 045).
- Renommage de la LoRA, métadonnées (`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`) — hors périmètre, déjà traités par Mission 047, non concernés par cette mission.
- Toute modification Domain, EventBus.

## 7. Wiring de rafraîchissement — aucun ajout

```
LoRAPage.remove_selected_files()
  → LoRAManager.remove_files(paths)
  → WorkspaceManager.save() (uniquement si mutation réelle)
  → événement WORKSPACE_SAVED
  → LoRAPage.update_loras() (déjà abonné depuis MainWindow)
```

Aucune souscription EventBus nouvelle.

## 8. Stratégie d'implémentation — réellement mise en œuvre

**`LoRAManager.remove_files(paths)`** :
```python
def remove_files(self, paths: List[str]) -> int:
    lora = self.active_lora
    if lora is None:
        return 0
    targets = set(paths)
    before = len(lora.files)
    lora.files[:] = [f for f in lora.files if f not in targets]
    removed = before - len(lora.files)
    if removed:
        self._workspace_manager.save()
    return removed
```

**`LoRAPage`** : `self.files_list.setSelectionMode(QListWidget.ExtendedSelection)` ; nouveau `self.remove_files_button` (« Retirer les fichiers sélectionnés »), activé selon `bool(self.files_list.selectedItems())` (mirroir exact de `_update_metadata_buttons_state()`) ; `remove_selected_files()` : lit les chemins sélectionnés (`item.text()` — `files_list` utilise déjà le chemin complet comme texte, confirmé par `update_loras()` actuel, `self.files_list.addItem(file_path)`), appelle `lora_manager.remove_files(paths)`, aucun traitement du retour nécessaire (rafraîchissement délégué à `WORKSPACE_SAVED`).

Aucun changement `CharacterManager`, `WorkspaceManager`, Domain, EventBus.

## 9. Stratégie de tests — réellement mise en œuvre

Nouvelle classe `LoRAManagerRemoveFilesTest` dans `test_lora_roundtrip.py` (9 tests) : retrait d'un fichier, retrait de plusieurs fichiers en un seul appel, chemin inconnu → `0` et `save()` jamais appelé (`patch.object(..., wraps=...)`), sauvegarde déclenchée uniquement si mutation réelle, retrait de la dernière entrée laissant `files == []`, sans LoRA active → `0`, fichier physique confirmé toujours présent sur disque après retrait, `engine`/`architecture`/`trigger_word`/`version`/`thumbnail` confirmés inchangés après un retrait, persistance après fermeture/réouverture (fichiers restants et métadonnées).

Extension de `LoRARoundTripTest` (10 tests, widgets Qt réels) : `files_list` en `ExtendedSelection`, bouton désactivé sans sélection puis activé avec sélection simple/multiple, retrait réel d'un fichier et de plusieurs en une opération, no-op sans sélection, liste vide et bouton désactivé après retrait de la dernière entrée, changement de LoRA active reflétant correctement l'état de `files_list`/du bouton, retrait laissant la fiche Métadonnées et l'aperçu de miniature intacts (propriété clé de cette mission).

**19/19 tests ciblés nets nouveaux, tous verts** (9 `LoRAManagerRemoveFilesTest` + 10 extension `LoRARoundTripTest`, soit 48/48 sur `test_lora_roundtrip.py` au total, 29 précédents + 19 nouveaux). Aucune comparaison pixel par pixel. Aucun test Domain M047 dupliqué — les tests de métadonnées existants (`LoRAManagerMetadataTest`) restés inchangés et verts.

## 10. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels, Managers réels, vrais fichiers temporaires). Script et capture exclusivement dans le scratchpad de session.

Points observés réellement, tous conformes :
- Création Workspace → Character → LoRA avec 3 fichiers externes réels (`.safetensors`), fiche Métadonnées remplie (Engine/Architecture/Trigger word/Version, sauvegarde réelle) et miniature réelle choisie et copiée dans le Workspace.
- Sélection réelle de 2 des 3 fichiers, clic réel sur « Retirer les fichiers sélectionnés » → `files_list` et `LoRA.files` confirmés avec un seul fichier restant.
- **Les 3 fichiers physiques confirmés toujours présents sur disque** après le retrait (aucune suppression, aucun déplacement).
- **Métadonnées et miniature confirmées strictement intactes** après le retrait (`engine`/`architecture`/`trigger_word`/`version` et `thumbnail` tous inchangés, aperçu `QPixmap` toujours affiché) — capture `m050_01_after_partial_removal.png` confirmant visuellement la fiche complète avec 1 fichier restant.
- Retrait du dernier fichier restant → `files_list` vide, bouton désactivé, `LoRA.files == []`, **LoRA toujours existante** (nom `"StyleA"` confirmé), fichier physique toujours présent sur disque.
- Fermeture puis réouverture réelle du Workspace → fichiers restants (aucun) et métadonnées (`engine="ComfyUI"`, `thumbnail` non vide) confirmés persistants.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat de la section 4.

## 11. Risques / non-régressions

- **Risque architectural** : nul — aucun changement Domain/EventBus, `CharacterManager` non touché, confirmé par inspection du diff complet.
- **Risque de régression sur `add_files()`/`create_lora()`/`delete_lora()`/`choose_thumbnail()`/`save_metadata()`** : écarté — tous les tests existants de `test_lora_roundtrip.py` restés verts sans modification.
- **Risque de confusion entre le retrait de fichier (cette mission) et la suppression de la LoRA entière (`delete_lora()`, inchangé)** : écarté par des libellés de bouton explicitement distincts (« Retirer les fichiers sélectionnés » vs « Supprimer »).
- **Risque de perte accidentelle des métadonnées/miniature lors d'un retrait de fichier** : écarté par construction (`remove_files()` ne touche que `LoRA.files`) et confirmé par test dédié et par smoke test réel.

## 12. Critères d'acceptation — résultats

- Retrait d'un ou plusieurs fichiers de la LoRA active, sans confirmation — **conforme**, vérifié par test et smoke test réel.
- Fichier physique jamais supprimé/déplacé/copié — **conforme**.
- `engine`/`architecture`/`trigger_word`/`version`/`thumbnail` inchangés après un retrait — **conforme**, vérifié par test dédié et smoke test réel.
- `files_list` en `ExtendedSelection`, bouton correctement activé/désactivé selon la présence d'une LoRA active et d'une sélection — **conforme**.
- Retrait de la dernière entrée laisse la LoRA valide avec `files == []` — **conforme**.
- Rafraîchissement via le seul mécanisme `WORKSPACE_SAVED` existant — **conforme**.
- Aucun changement Domain/Manager (hors ajout additif)/EventBus — **conforme**, confirmé par inspection du diff complet.
- Suite ciblée : **19/19 OK** (48/48 sur `test_lora_roundtrip.py`).
- Suite complète : **859/859 OK** (840 précédents + 19 nets nouveaux).
- `git diff --check` : **propre**.
- **Smoke test manuel obligatoire (section 10) réalisé, résultat PASS.**

## État d'avancement

- Audit de sélection (candidat Mission 050), mini-audit ciblé et spécification : **validés par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 19/19 ciblés (48/48 sur `test_lora_roundtrip.py`), 859/859 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS**.
- Clôture Git : **non effectuée** — en attente de validation technique de l'architecte avant commit/tag/Release.
