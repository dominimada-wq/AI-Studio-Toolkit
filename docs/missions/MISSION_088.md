# Mission 088 — Add an Existing LoRA to the Central Library

> **MISSION IMPLÉMENTÉE, EN ATTENTE DE CLÔTURE GIT.** 16 tests ciblés nets nouveaux (14 `test_lora_roundtrip.py`, 2 `test_lora_library_roundtrip.py`), non-régression complète, suite complète **1646/1646, aucun crash**, smoke test Qt réel exécuté et **PASS** (25/25 assertions, stable sur 3 exécutions consécutives — voir section 5). Voir section 7 pour l'état de clôture Git.

## 1. Contexte

L'audit post-Mission 087 a confirmé que la fondation posée par cette dernière (`LoRALibraryManager`/`LoRALibraryStorage`, `ApplicationSettings.lora_library_path`) est fonctionnellement présente mais entièrement déconnectée : aucun appelant Presentation n'existe, la bibliothèque centrale reste vide et invisible en dehors de `SettingsPage` (qui n'affiche que le chemin). Trois candidats ont été comparés (action d'import depuis `LoRAPage` ; nettoyage de dettes cosmétiques déjà connues et inchangées — `setButtonText()` deprecated, isolation `EventBus` — ; reprise d'un besoin mûr distinct — Prompt Library/RAG, portabilité des chemins, Character Context avancé). L'action d'import a été retenue : c'est littéralement l'action nommée par la décision C de l'architecte lors du mini-audit LoRA (Mission 087, « future action explicite d'import/ajout pour transfert volontaire ») et l'item (1) de la feuille de route de `MISSION_087.md`, sans exiger aucune décision architecturale nouvelle.

Un mini-audit contractuel ciblé, mené à partir du code réel post-M087, a fermé les points suivants avant toute écriture de code :
- La signature réelle de `LoRALibraryManager.import_lora()` (`name`, `file_paths`, `library_root`, `thumbnail_path=None`) ne transmet aujourd'hui ni `engine`, ni `architecture`, ni `trigger_word`, ni `version` au `LoRA` central créé — une copie appauvrie serait produite sans extension de l'API. Confirmé et corrigé par le contrat ci-dessous (extension additive, jamais appliquée automatiquement sans validation).
- Le comportement tout-ou-rien de `import_lora()` face à une miniature déclarée mais dont le fichier a disparu (même chemin d'échec que pour les fichiers principaux, dans le même bloc `try`) a été confirmé et retenu tel quel — aucune pré-vérification UI destinée à l'ignorer silencieusement.
- `ApplicationSettingsManager.settings` est une propriété toujours vivante (réassignée à chaque `update()` réussi) — aucun risque de valeur périmée en la lisant au moment du clic.
- `LoRAManager.active_lora` (propriété) retourne un vrai `LoRA` Domain, source correcte pour l'import — pas `list_loras()` (`List[dict]`).
- `_confirm_discard_metadata_before_switch()` (`src/ui/pages/lora_page.py`) a été relu intégralement : il ne fait que construire/afficher le dialogue Save/Discard/Cancel et retourner le bouton cliqué, sans aucune hypothèse ni effet de bord propre au changement de sélection — réutilisable tel quel, sans extraction d'une primitive séparée.
- Wiring : `main_window.py` construit déjà `self.lora_library_manager` et `self.application_settings_manager` avant `self.lora_page = LoRAPage(...)` — aucun réordonnancement nécessaire. Seuls appelants réels de `LoRAPage(...)` : `main_window.py` (1 site) et `tests/integration/test_lora_roundtrip.py` (12 sites).

## 2. Objectif

Permettre, depuis `LoRAPage`, d'ajouter la LoRA Character-scoped actuellement active à la bibliothèque centrale posée par Mission 087 — une copie volontaire, explicite, sans association retour ni déduplication — afin que la bibliothèque cesse d'être vide et que les missions futures (référencement Character/Workspace, exposition moteur/provider) disposent d'un premier contenu réel à exploiter.

## 3. Contrat final validé

### 3.1 Extension de `LoRALibraryManager.import_lora()`

Quatre nouveaux paramètres optionnels, mots-clés uniquement, transmis tels quels au `LoRA` central construit :

```
import_lora(
    name: str,
    file_paths: list[str],
    library_root,
    thumbnail_path: Optional[str] = None,
    engine: str = "",
    architecture: str = "",
    trigger_word: str = "",
    version: str = "",
) -> LoRA
```

Purement additif — les 39 tests M087 existants n'appellent jamais ces paramètres ; leur comportement testé (défauts `""`) reste identique, byte-for-byte. Aucun autre changement au corps de la méthode (copie, transaction, rollback, exceptions) — ces 4 valeurs ne sont ni validées ni transformées, seulement transmises au constructeur `LoRA(...)`.

### 3.2 Comportement fichiers/thumbnail (contrat M087 inchangé, confirmé)

- `files=[]` : import autorisé, entrée créée sans fichier — aucune validation métier nouvelle.
- Fichier principal manquant/inaccessible : `WorkspaceStorageError` → `LoRALibraryError`, nettoyage best-effort, aucune entrée créée.
- `thumbnail == ""` : import autorisé sans miniature.
- Thumbnail déclarée et présente : copiée normalement.
- Thumbnail déclarée mais fichier absent/inaccessible : **échec total de l'import** (même bloc transactionnel que les fichiers principaux) — comportement conservé tel quel, aucune tolérance silencieuse ajoutée.
- Fichiers/thumbnail source (Character-scoped) : jamais modifiés, jamais supprimés, jamais déplacés — garanti par le contrat M087 déjà testé (lecture seule).

### 3.3 `LoRAPage`

**Constructeur** — deux nouveaux paramètres **requis**, non `Optional` :

```
LoRAPage(lora_manager, workspace_manager, lora_library_manager, application_settings_manager)
```

Cohérent avec `lora_manager`/`workspace_manager` déjà requis dans ce même constructeur — pas d'`Optional` introduit uniquement pour préserver les anciens tests. Les 12 sites de construction existants dans `tests/integration/test_lora_roundtrip.py` sont mis à jour mécaniquement (2 arguments ajoutés), sans changement de comportement testé.

**Nouveau bouton** `add_to_library_button` (« Ajouter à la bibliothèque centrale »), placé dans la rangée `lora_buttons` (aux côtés de « Nouvelle LoRA »/« Supprimer »). Activé/désactivé via `_update_metadata_buttons_state()` (même source que `choose_thumbnail_button`/`save_metadata_button`, `active_lora_id is not None`) — confirmé impossible de lancer l'action sans LoRA active.

**Handler `add_to_central_library()`** :
1. Retour anticipé si `active_lora_id is None` (garde défensive, cohérente avec `save_metadata()`/`choose_thumbnail()`).
2. Si `_metadata_dirty` : affiche `_confirm_discard_metadata_before_switch()` (réutilisé tel quel, voir §1) :
   - **Cancel** → l'action s'arrête immédiatement, aucun import, aucune mutation.
   - **Save** → `lora_manager.update(active_lora_id, engine=..., architecture=..., trigger_word=..., version=...)` avec les valeurs actuellement affichées. Échec (`WorkspaceManagerError`) → `QMessageBox.critical`, `_force_refresh_lora()` (resynchronise l'affichage sur l'état Domain déjà restauré par le rollback de `LoRAManager.update()`, Mission 070), **import annulé**, retour immédiat — mirroir exact du bloc Save de `confirm_context_change()`.
   - **Discard** → `_force_refresh_lora()` (restaure explicitement les champs depuis l'état Domain persisté — aucun changement de sélection ne suit pour déclencher ce rechargement automatiquement, contrairement à `on_lora_selection_changed()`), qui remet `_metadata_dirty` à `False` via `_load_metadata_fields()`.
   - Sur Save réussi, `_metadata_dirty = False` est positionné explicitement (les 4 champs affichent déjà exactement ce qui vient d'être persisté, aucun resync nécessaire — mirroir exact de `confirm_context_change()`).
3. Relit `lora = self.lora_manager.active_lora` (objet Domain synchronisé, que le brouillon ait été Save/Discard ou qu'il n'y ait jamais eu de brouillon).
4. Résout `library_root = self.application_settings_manager.settings.lora_library_path` (lecture au moment du clic, jamais mise en cache).
5. Appelle `self.lora_library_manager.import_lora(name=lora.name, file_paths=lora.files, library_root=library_root, thumbnail_path=lora.thumbnail, engine=lora.engine, architecture=lora.architecture, trigger_word=lora.trigger_word, version=lora.version)`.
6. `LoRALibraryError` → `QMessageBox.critical`, retour — aucune mutation résiduelle côté `LoRAPage`/`LoRAManager`.
7. Succès → `QMessageBox.information` nommant la LoRA importée (mirroir exact du pattern déjà établi par `import_files()`) — rend tout import, y compris un double-clic accidentel, visible et confirmé explicitement.

Aucune association retour n'est stockée sur la `LoRA` Character-scoped — une réimportation ultérieure de la même LoRA crée une entrée centrale supplémentaire indépendante, avec sa propre copie physique (contrat M087 inchangé, aucun hash, aucune déduplication).

### 3.4 `main_window.py`

```python
self.lora_page = LoRAPage(
    self.lora_manager,
    self.workspace_manager,
    self.lora_library_manager,
    self.application_settings_manager,
)
```

Aucun réordonnancement nécessaire — les deux dépendances existent déjà avant ce point.

### 3.5 Hors périmètre (confirmé, inchangé)

Références Character/Workspace → entrée centrale ; migration de `project.json` ; UI globale de bibliothèque ; suppression d'entrées centrales référencées depuis `LoRAPage` ; exposition aux moteurs locaux (ComfyUI/Fooocus/A1111/Forge) ; providers cloud Image/Video ; sélection de LoRA centrale dans Inference ; déduplication par hash.

## 4. Implémentation

- `src/managers/lora_library_manager.py` — `import_lora()` gagne 4 paramètres optionnels mots-clés (`engine=""`, `architecture=""`, `trigger_word=""`, `version=""`), transmis tels quels au `LoRA` central construit. Purement additif, conforme au §3.1.
- `src/ui/pages/lora_page.py` — nouveaux paramètres constructeur requis `lora_library_manager`/`application_settings_manager` (import `LoRALibraryError`) ; nouveau bouton `add_to_library_button` dans la rangée `lora_buttons`, activé/désactivé via `_update_metadata_buttons_state()` (même source que `choose_thumbnail_button`/`save_metadata_button`) ; nouvelle méthode `add_to_central_library()` implémentant exactement le contrat du §3.3 (résolution dirty-state Save/Discard/Cancel via `_confirm_discard_metadata_before_switch()` réutilisé tel quel, lecture de `lora_manager.active_lora` post-résolution, résolution du chemin via `application_settings_manager.settings.lora_library_path` au moment du clic, appel `import_lora()` avec fichiers+thumbnail+les 4 métadonnées, `QMessageBox.critical`/`QMessageBox.information`).
- `src/ui/main_window.py` — `LoRAPage(...)` reçoit désormais `self.lora_library_manager`/`self.application_settings_manager`, déjà construits avant ce point ; aucun réordonnancement nécessaire.
- `tests/integration/test_lora_roundtrip.py` — les 12 sites de construction `LoRAPage(...)` existants mis à jour mécaniquement (ajout de `lora_library_manager`/`application_settings_manager`, résolus via des répertoires temporaires dédiés sous `self.tmp_dir`, jamais `%LOCALAPPDATA%` réel) ; nouvelle classe `LoRAPageAddToCentralLibraryTest` (14 tests).
- `tests/integration/test_lora_library_roundtrip.py` — 2 tests ajoutés à `LoRALibraryManagerImportTest` couvrant la transmission des 4 métadonnées et la conservation du comportement pré-Mission-088 (défauts `""`) quand elles ne sont pas fournies.

**Hors périmètre, confirmé inchangé** : références Character/Workspace → entrée centrale, migration de `project.json`, UI globale de bibliothèque, suppression d'entrées centrales référencées depuis `LoRAPage`, exposition aux moteurs locaux, providers cloud Image/Video, sélection de LoRA centrale dans Inference, déduplication par hash.

## 5. Tests automatisés et smoke test

- **16 tests ciblés nets nouveaux** : `LoRAPageAddToCentralLibraryTest` (14, `test_lora_roundtrip.py`) — bouton désactivé sans LoRA active / activé après sélection ; import créant une entrée centrale avec fichiers+métadonnées+thumbnail corrects ; import multi-fichiers ; import sans thumbnail ; fichier principal manquant → erreur, aucune entrée ; thumbnail déclarée mais fichier disparu → échec total de l'import (contrat tout-ou-rien verrouillé) ; échec de persistence → erreur, aucune entrée ; import répété → deux entrées indépendantes avec deux copies physiques distinctes ; fichiers/thumbnail Character-scoped source strictement inchangés après import ; dirty-state Cancel (aucun import, brouillon conservé), Save (métadonnées persistées puis import synchronisé sur les nouvelles valeurs), Discard (champs restaurés à l'état persisté puis import sur cet état), échec de Save pendant la résolution (import annulé, aucun brouillon résiduel, mirroir du contrat `confirm_context_change()`). `LoRALibraryManagerImportTest` (2, `test_lora_library_roundtrip.py`) — les 4 métadonnées transmises fidèlement et persistées après rechargement du registre ; comportement pré-Mission-088 inchangé quand elles ne sont pas fournies.
- Non-régression complète : `test_lora_roundtrip.py` (173/173 avant ajout des 14 nouveaux, tous verts après la mise à jour mécanique des 12 sites de construction), `test_lora_library_roundtrip.py` (41/41 avec les 2 nouveaux), `test_application_settings_roundtrip.py` (17/17), `test_settings_page.py`/`test_settings_roundtrip.py` (90/90), suite `MainWindow` ciblée sur 9 fichiers (122/122, confirmant le nouveau wiring `main_window.py` sans régression).
- **1646/1646 tests verts au total** (1630 précédents + 16 nets nouveaux), une exécution complète `unittest discover`, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `LoRAPage`/`LoRAManager`/`LoRALibraryManager`/`ApplicationSettingsManager` réels, Workspace/Character/LoRA réels avec fichiers+thumbnail réels sur disque, bibliothèque centrale pointée vers un dossier temporaire réel, clic réel sur `add_to_library_button` — **PASS, 25/25 assertions** (stable sur 3 exécutions consécutives) : bouton activé, message de succès affiché, fichier `lora_library.json` réellement écrit avec 1 entrée, copie physique du fichier de poids présente sous `library_root/<lora_id>/` avec le contenu exact de la source, thumbnail centrale présente, les 4 métadonnées correctement transmises, **fichiers et thumbnail Character-scoped source strictement inchangés (mêmes chemins, même contenu, toujours présents sur disque)**, copie centrale physiquement distincte de la source, import répété créant une seconde entrée indépendante avec un `lora_id` distinct.

## 6. Conclusion

La bibliothèque LoRA centrale posée par Mission 087 cesse d'être vide et invisible : `LoRAPage` permet désormais d'y copier volontairement, explicitement, la LoRA Character-scoped active — fichiers, thumbnail et les 4 métadonnées (`engine`/`architecture`/`trigger_word`/`version`, désormais transmissibles à `import_lora()` sans régression pour les appelants existants) — sans jamais créer d'association retour ni de déduplication, conformément aux décisions déjà actées (grandfathering, transfert volontaire explicite). Le contrat transactionnel tout-ou-rien de M087 (y compris pour une thumbnail déclarée mais disparue) est conservé sans tolérance ajoutée. La résolution du dirty-state des 4 champs métadonnées avant import (Save/Discard/Cancel, réutilisant `_confirm_discard_metadata_before_switch()` sans modification) garantit que l'entrée centrale reflète toujours exactement ce qui est affiché/persisté, jamais une valeur ambiguë. La bibliothèque reste entièrement déconnectée de `Character.loras`/`project.json`/Inference/tout moteur — la fondation reste stable pour de futures missions (référencement Character/Workspace, exposition moteur/provider), aucune n'a été engagée prématurément.

## 7. État d'avancement et clôture Git

- Mini-audit contractuel : **terminé**, validé par l'architecte.
- Rédaction du contrat final : **terminée**.
- Implémentation : **réalisée**, strictement limitée au périmètre de la section 4.
- Tests automatisés : **exécutés, verts — 16/16 ciblés nets nouveaux, non-régression complète** (voir section 5).
- Suite complète : **1646/1646, aucun crash**, une exécution complète `unittest discover`.
- `git diff --check` : **propre** (uniquement des avertissements de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme** (3 fichiers de production modifiés, 2 fichiers de test modifiés, ce document de mission ; `Character.loras`, `project.json`, aucune UI globale, aucun moteur/provider confirmés non touchés).
- Smoke test Qt réel : **réalisé, PASS, 25/25 assertions, stable sur 3 exécutions consécutives**.
- Clôture Git (commit/tag/Release) : **en attente de validation de l'architecte.**
