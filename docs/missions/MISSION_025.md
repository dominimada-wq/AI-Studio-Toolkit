# Mission 025 — ComfyUI Checkpoint Discovery & Selection

Source : audit read-only préalable de priorisation (sept candidats comparés — A : multi-référence 1..N + rôles, B : sélection moteur/backend, C : exploitation de `comfyui_path` + sélection de checkpoint, D : refonte de Settings, E : tri de la galerie Images, F : internationalisation réelle, G : LoRA multi-engine), Candidat C recommandé puis validé par l'architecte. Spécification pré-implémentation — **aucun code applicatif ni aucun test n'a encore été modifié à ce stade**. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur ici ; les sections "Commit correspondant"/"Tag / release correspondant" seront complétées après implémentation et clôture Git réelles.

## 1. Contexte

`ApplicationSettings.comfyui_path` existe depuis Mission 018 mais n'est consommé nulle part dans le code — un champ purement déclaratif, jamais défini précisément quant à sa structure interne attendue. `ApplicationSettings.comfyui_checkpoint_name` (également Mission 018) est aujourd'hui saisi en texte libre dans `SettingsPage` (`comfyui_checkpoint_name_edit`, `QLineEdit`), sans aucune validation ni assistance — source d'erreur déjà observée empiriquement (écart entre le nom saisi et le nom réel du fichier checkpoint, cf. smoke test Mission 012). Ce besoin est enregistré dans `docs/PROJECT_CONTEXT.md` sous "`ComfyUI Installation Folder` — exploitation de `comfyui_path`", avec la sélection de checkpoint comme sous-capacité prioritaire identifiée lors de l'audit Mission 024.

**Correction apportée après audit read-only complémentaire (avant toute implémentation)** : l'hypothèse initiale d'un simple scan filesystem de `comfyui_path/models/checkpoints/` s'est révélée insuffisante pour notre installation réelle **ComfyUI Desktop pour Windows**. Lors du smoke test Mission 012, `GET /system_stats` avait déjà montré que ComfyUI Desktop démarre avec un argument `--extra-model-paths-config .../shared_models.yaml`, indiquant que les checkpoints réellement chargeables par le serveur peuvent provenir de chemins additionnels/partagés, résolus en interne par ComfyUI lui-même, et pas seulement d'un unique dossier `models/checkpoints/` relatif à `comfyui_path`. Voir section 5 pour la conclusion détaillée et le mécanisme de découverte corrigé qui en résulte.

## 2. Objectif

Permettre à l'utilisateur de découvrir automatiquement les checkpoints réellement exploitables par son instance ComfyUI (locale, Desktop, portable ou distante) et de faciliter leur sélection dans `SettingsPage` — **sans jamais retirer la possibilité de saisir manuellement un nom de checkpoint**, seule option valable quand la découverte automatique échoue ou n'est pas applicable (serveur non démarré, configuration distante/cloud). Cette mission n'est ni une refonte générale de `SettingsPage`, ni une abstraction multi-engine.

Le mécanisme de découverte a été corrigé suite à l'audit de la section 5 : il interroge désormais le serveur ComfyUI réellement en cours d'exécution (via `comfyui_url`, déjà exploité depuis Mission 018) plutôt que de scanner le filesystem via `comfyui_path`. `comfyui_path` reste, à l'issue de cette mission, un champ non consommé — ce point est documenté explicitement en section 5 et reporté dans `docs/PROJECT_CONTEXT.md`.

## 3. Architecture avant Mission 025

```
SettingsPage.__init__(settings_manager, application_settings_manager)
  comfyui_checkpoint_name_edit: QLineEdit (texte libre, aucune validation)
       │ save_application_settings()
       ▼
ApplicationSettingsManager.update(comfyui_checkpoint_name=<texte saisi>)
       │
       ▼
ApplicationSettingsStorage (fichier machine-local, hors project.json)

comfyui_path: str = ""  (ApplicationSettings) — existe, jamais lu par aucun code
```

Aucun code du dépôt ne lit `comfyui_path` aujourd'hui (confirmé par recherche textuelle) — et Mission 025, après correction (section 5), ne change pas ce fait. `comfyui_checkpoint_name` est lu uniquement par `MainWindow`/`GenerationManager` (Mission 018), sans changement prévu ici. `comfyui_url` est déjà exploité depuis Mission 018 pour la connexion réelle (`ComfyUIEngine._base_url`) — Mission 025 lui ajoute un second usage, ponctuel et local à `SettingsPage` : interroger le serveur pour découvrir ses checkpoints.

## 4. Point d'audit UI — solution retenue

Trois options ont été comparées :

- **A. Ajouter une liste déroulante séparée à côté du champ texte existant.** Rejeté : duplique la représentation d'une seule et même valeur (`comfyui_checkpoint_name`) dans deux widgets, avec un risque de désynchronisation (lequel des deux est lu à l'enregistrement ?) et une UI plus complexe sans bénéfice.
- **B. `QComboBox` non éditable, avec un bouton "Saisie manuelle" basculant vers un `QLineEdit` séparé.** Rejeté : deux widgets, un état de bascule supplémentaire à gérer, pour un gain ergonomique marginal par rapport à l'option C.
- **C. `QComboBox` avec `setEditable(True)`.** **Retenue.** Un seul widget, un seul champ persisté. `setEditable(True)` conserve un `QLineEdit` interne (accessible via `.lineEdit()`) : `currentText()` retourne indifféremment l'élément sélectionné dans la liste ou le texte librement saisi, et `setCurrentText(...)` accepte une valeur absente de la liste sans erreur (contrairement à un `QComboBox` non éditable). Cela couvre nativement les deux situations demandées :
  - **ComfyUI joignable (local, Desktop ou distant) au moment du clic sur "Rafraîchir"** → la liste déroulante propose les checkpoints réellement exposés par le serveur ; sélectionner un élément suffit.
  - **ComfyUI non démarré/injoignable, ou découverte non tentée** → la liste est vide ; l'utilisateur tape directement le nom, exactement comme aujourd'hui avec le `QLineEdit`.

  Vérifié comme réellement disponible dans PySide6 (`QComboBox.setEditable`, `QComboBox.currentText`, `QComboBox.setCurrentText`) — aucune dépendance nouvelle, aucun composant custom.

`comfyui_checkpoint_name_edit` change donc de type (`QLineEdit` → `QComboBox` éditable) mais conserve son nom d'attribut, pour limiter la surface de changement à ce qui est réellement nécessaire.

## 5. Audit ComfyUI Desktop et règles de découverte retenues

### Conclusion de l'audit read-only

- **`comfyui_path/models/checkpoints/` ne suffit pas comme unique source de vérité.** Aucun code ni aucune documentation du dépôt ne définit précisément ce que `comfyui_path` est censé contenir (Mission 018 le décrit uniquement comme "le chemin d'installation local de ComfyUI", jamais davantage précisé) — et rien dans le dépôt ne documente la structure réelle de l'installation ComfyUI Desktop de l'architecte (aucun chemin filesystem concret n'a jamais été consigné dans `docs/`, y compris lors du smoke test Mission 012).
- **Comportement réel de ComfyUI Desktop (Windows)** : le smoke test Mission 012 avait déjà établi, via `GET /system_stats`, que le processus est lancé avec `--extra-model-paths-config .../shared_models.yaml`. C'est un mécanisme ComfyUI natif et documenté (`extra_model_paths.yaml`) permettant de déclarer des dossiers de modèles supplémentaires/partagés, résolus par ComfyUI lui-même en interne, potentiellement situés en dehors du dossier d'installation de l'application Desktop. Un scan filesystem de `comfyui_path/models/checkpoints/` peut donc légitimement manquer des checkpoints réellement visibles et utilisables par le serveur.
- **`shared_models.yaml`/`extra_model_paths`** : format YAML propre à ComfyUI, listant un ou plusieurs `base_path` et leurs sous-dossiers de modèles (`checkpoints`, `loras`, `vae`, etc.). Aucun exemplaire réel de ce fichier n'a été inspecté durant cet audit (hors périmètre read-only du dépôt) — seuls son existence et son rôle général sont confirmés par l'argument de lancement déjà observé.
- **Décision** : ne pas écrire de parser (même minimal) pour `shared_models.yaml`/`extra_model_paths` — un tel parser devrait, pour rester correct, réimplémenter une partie non triviale de la résolution de chemins déjà faite par ComfyUI lui-même (fusion de plusieurs `base_path`, gestion des chemins relatifs/absolus, priorité entre sources) : c'est exactement le genre de complexité générique que l'architecte a demandé d'éviter. **La source de vérité la plus simple, la plus robuste, et déjà éprouvée par le projet (smoke test Mission 012) est de demander directement au serveur ComfyUI en cours d'exécution quels checkpoints il expose**, via l'endpoint déjà utilisé avec succès en Mission 012 : `GET /object_info/CheckpointLoaderSimple`. ComfyUI y résout lui-même l'intégralité de sa configuration de chemins (locale, partagée, `extra_model_paths` incluse) — AI Studio Toolkit n'a plus besoin d'en connaître la structure.

### Mécanisme de découverte retenu (correction de spécification)

Le scan filesystem de `comfyui_path` est **abandonné** au profit d'une requête `GET {comfyui_url}/object_info/CheckpointLoaderSimple` contre le serveur ComfyUI réellement configuré (`comfyui_url`, déjà exploité depuis Mission 018) — exactement le mécanisme déjà validé manuellement en Mission 012 pour obtenir la liste réelle des checkpoints.

| Cas | Comportement |
|---|---|
| `comfyui_url` valide, serveur ComfyUI démarré et joignable | Liste réelle des checkpoints telle que résolue par ComfyUI lui-même (chemins locaux et partagés/`extra_model_paths` confondus — jamais interprétés directement par Toolkit). |
| `comfyui_url` vide ou syntaxiquement invalide | Échec de la requête → traité comme découverte indisponible, liste vide, repli sur la saisie manuelle. |
| Serveur injoignable (non démarré, mauvaise adresse, pare-feu) | Échec réseau (timeout court ou connexion refusée) → même traitement : liste vide, repli sur la saisie manuelle. |
| Réponse reçue mais structurellement inattendue (nœud `CheckpointLoaderSimple` absent, forme JSON différente de celle documentée par ComfyUI) | Traité comme une erreur de communication, jamais comme une liste partielle devinée. |
| Aucun checkpoint installé côté serveur | Liste vide légitime (pas une erreur) — combo box vide, saisie manuelle toujours possible. |
| Ordre de présentation | Ordre retourné tel quel par ComfyUI — aucun retri côté Toolkit, pour ne pas prétendre à un ordre "plus correct" que celui du serveur qui utilisera réellement ce nom. |
| Doublons | Non dédupliqués côté Toolkit — reflet fidèle, non réinterprété, de ce que le serveur retourne. |

Ce mécanisme fonctionne à l'identique pour une installation locale, portable, Desktop (avec ou sans `extra_model_paths`) ou distante/cloud : dans tous les cas, c'est le serveur qui répond, jamais Toolkit qui devine une structure de dossiers.

**Conséquence assumée** : `comfyui_path` reste, à l'issue de cette mission, un champ non consommé par aucun code — le besoin "exploitation de `comfyui_path`" documenté dans `docs/PROJECT_CONTEXT.md` n'est donc **pas** résolu par Mission 025 ; seule sa sous-capacité "sélection de checkpoint" l'est, par un mécanisme différent de celui envisagé à l'audit Mission 024. Cette nuance sera reportée dans `docs/PROJECT_CONTEXT.md` lors de la clôture documentaire de la mission (comme pour chaque mission précédente) — non modifiée dans cette passe read-only, qui ne touche `docs/PROJECT_CONTEXT.md` que pour l'orientation Project/Character demandée séparément.

## 6. Emplacement architectural du mécanisme de découverte

Pas de nouveau module : `GET /object_info/CheckpointLoaderSimple` est une opération protocolaire ComfyUI comme `submit()`/`wait_for_result()`/`upload_image()` déjà présentes dans `ComfyUIEngine` — elle y trouve donc naturellement sa place, en cohérence avec le rôle déjà documenté de cette classe ("Minimal HTTP client for a ComfyUI instance's own API").

Nouvelle méthode publique, additive, sur `ComfyUIEngine` (`src/engines/comfyui_engine.py`) :

```python
def list_checkpoints(self) -> list[str]:
    ...
```

Réutilise `_request_json()` (déjà existant, déjà utilisé par `submit()`/`wait_for_result()`) — une seule requête `GET`, aucun polling. Suit le même contrat d'erreur que les méthodes existantes de cette classe : lève `ComfyUIEngineError` sur tout échec de communication ou réponse structurellement inattendue, ne retourne jamais une liste partielle/devinée. C'est l'appelant (`SettingsPage`) qui décide de traiter cette exception comme "découverte indisponible → liste vide, repli sur saisie manuelle" — même partage des responsabilités que pour toute autre erreur `ComfyUIEngineError` déjà gérée ailleurs dans le projet (`GenerationWorker`).

Aucun nouveau module, aucune nouvelle classe, aucun registre — la plus petite extension additive possible à une primitive déjà existante.

## 7. Stratégie de rafraîchissement

- **Découverte uniquement sur action explicite** : nouveau bouton "Rafraîchir les checkpoints" à côté du champ checkpoint, construisant un `ComfyUIEngine` transitoire avec l'URL **actuellement affichée** dans `comfyui_url_edit` (pas nécessairement déjà enregistrée — permet de tester une adresse avant de la sauvegarder) et appelant `list_checkpoints()`.
- **Explicitement exclu : aucune découverte automatique au chargement de `SettingsPage`.** Contrairement au plan filesystem initial, cette découverte est désormais un appel réseau bloquant sur le thread UI — la déclencher silencieusement à chaque ouverture de Settings (y compris quand ComfyUI n'est pas démarré) introduirait une latence/un blocage non sollicité par l'utilisateur. Au chargement, seule la valeur déjà persistée est affichée (`setCurrentText`), sans tentative de découverte.
- **Timeout court dédié** : l'instance `ComfyUIEngine` construite pour la découverte utilise un `timeout` court (quelques secondes, à fixer précisément en implémentation — paramètre déjà existant sur `ComfyUIEngine.__init__`, aucun nouveau paramètre nécessaire), distinct du timeout long utilisé pour la génération d'image réelle (`GenerationManager`, 120s par défaut) — une adresse erronée ou un serveur éteint ne doit pas geler l'UI pendant deux minutes pour un simple clic sur "Rafraîchir".
- **Explicitement exclu** : tout mécanisme de thread dédié (`QThread`) pour cet appel — jugé disproportionné pour une action manuelle, ponctuelle, à timeout court, contrairement à la génération d'image (potentiellement longue, déjà threadée depuis Mission 013). Simplification assumée, pas un oubli.
- Aucune surveillance filesystem ou réseau permanente.

## 8. Comportement précis de l'UI

- `comfyui_checkpoint_name_edit` : `QComboBox`, `setEditable(True)`, remplace le `QLineEdit` actuel (même nom d'attribut).
- Peuplé via `list_checkpoints()` uniquement sur clic du bouton "Rafraîchir les checkpoints" (section 7) — jamais automatiquement.
- Valeur affichée au chargement de `SettingsPage` : la valeur actuellement persistée (`ApplicationSettings.comfyui_checkpoint_name`) restaurée via `setCurrentText(...)`, liste déroulante vide tant qu'aucun rafraîchissement n'a été demandé — l'édition libre permet malgré tout d'afficher/modifier cette valeur immédiatement.
- Après un rafraîchissement réussi, `setCurrentText(...)` est réappliqué après repeuplement pour ne pas perdre la valeur actuellement affichée (sélectionnée dans la liste si elle y figure, conservée telle quelle sinon).
- Aucun élément vide/placeholder ajouté à la liste déroulante — une chaîne vide n'a jamais été une valeur de checkpoint légitime (le défaut `Domain` est déjà non-vide depuis Mission 018).
- En cas d'échec de découverte (`ComfyUIEngineError` capturée), la liste reste vide (ou inchangée si un rafraîchissement précédent avait réussi) et un signal visuel minimal (ex. texte du bouton temporairement changé, ou `QMessageBox`/statut — choix précis laissé à l'implémentation) informe l'utilisateur sans bloquer la saisie manuelle.
- `save_application_settings()` : lit `.currentText()` au lieu de `.text()` — **seule ligne modifiée** dans cette méthode. Aucun changement de signature de `ApplicationSettingsManager.update()` (toujours un `str` pour `comfyui_checkpoint_name`).

## 9. Persistance

Aucun nouveau champ, aucun nouveau format de configuration. `ApplicationSettings.comfyui_checkpoint_name` (existant depuis Mission 018) reste l'unique source de vérité persistée, via le même `ApplicationSettingsManager.update(...)` et la même `ApplicationSettingsStorage`. La découverte ne persiste jamais rien elle-même — appel réseau en lecture seule, aucun effet de bord en écriture, ni sur `ApplicationSettings` ni côté serveur ComfyUI.

## 10. Périmètre IN

- `ComfyUIEngine.list_checkpoints()` (nouvelle méthode additive dans `src/engines/comfyui_engine.py`).
- `comfyui_checkpoint_name_edit` : `QLineEdit` → `QComboBox` éditable dans `SettingsPage`.
- Nouveau bouton "Rafraîchir les checkpoints", découverte sur clic uniquement (timeout court dédié).
- Lecture de la valeur enregistrée via `.currentText()`.
- Tests automatisés de `list_checkpoints()` (mocké, comme toutes les méthodes réseau existantes de `ComfyUIEngine`) et du widget `SettingsPage` (Qt réel).
- Smoke test manuel réel contre l'installation ComfyUI Desktop Windows déjà validée, avec vérification explicite que les checkpoints réellement exposés par cette instance (y compris via `extra_model_paths`/`shared_models.yaml`) apparaissent.

## 11. Périmètre OUT (explicitement différé, déjà listé dans `docs/PROJECT_CONTEXT.md`)

LoRA discovery/sélection ; ControlNet ; IP-Adapter ; custom nodes ; téléchargement de checkpoints ; installation/suppression/déplacement de modèles ; démarrage/arrêt de ComfyUI ; refonte générale de `SettingsPage` ; sélection moteur/backend ; multi-référence ; modification des workflows de génération (`comfyui_workflows.py`) ; modification du paramètre `reference_strength`/`denoise` livré par Mission 024 ; **parsing direct de `shared_models.yaml`/`extra_model_paths`** (ComfyUI résout déjà cette configuration lui-même — Toolkit ne la réinterprète jamais) ; **scan filesystem de `comfyui_path`** (mécanisme initial abandonné, section 5) ; découverte automatique au chargement de Settings (uniquement sur clic explicite) ; thread dédié pour la découverte (timeout court synchrone jugé suffisant) ; persistance de la liste des checkpoints découverts (toujours recalculée, jamais stockée).

## 12. Fichiers réellement concernés

- **Modifié** : `src/engines/comfyui_engine.py` — nouvelle méthode additive `list_checkpoints()`, aucune méthode existante modifiée.
- **Modifié** : `src/ui/pages/settings_page.py` — `QComboBox` éditable, bouton de rafraîchissement, méthodes `save_application_settings()`/`update_application_settings()` adaptées.
- **Modifié** : `tests/integration/test_comfyui_engine.py` — nouveaux tests pour `list_checkpoints()` (mêmes conventions de mock réseau que les tests existants).
- **Nouveau test** : `tests/integration/test_settings_page.py` — première couverture Qt réelle dédiée à `SettingsPage` (n'existait pas avant cette mission).
- **Aucune modification attendue** : `src/domain/application_settings.py`, `src/managers/application_settings_manager.py`, `src/infrastructure/storage/application_settings_storage.py`, `src/engines/workflows/comfyui_workflows.py`, `src/managers/generation_manager.py`, `src/ui/pages/inference_page.py`, `src/ui/generation_worker.py`, ni aucun fichier touché par Mission 024. `comfyui_path_edit` dans `settings_page.py` reste également inchangé (champ toujours non consommé).

## 13. Stratégie de tests

- `test_comfyui_engine.py` (nouveaux tests pour `list_checkpoints()`, mêmes conventions que les tests existants — réponses HTTP simulées déterministes, aucune requête réseau réelle) :
  - réponse structurellement valide avec plusieurs checkpoints → liste correctement extraite ;
  - réponse valide avec un seul checkpoint → liste à un élément ;
  - réponse valide sans aucun checkpoint (liste vide côté serveur) → liste vide, pas d'exception ;
  - réponse HTTP d'erreur / serveur injoignable → `ComfyUIEngineError` levée (même contrat que `submit()`/`upload_image()`) ;
  - réponse reçue mais structurellement inattendue (`CheckpointLoaderSimple` absent, forme JSON différente) → `ComfyUIEngineError` levée, pas de liste partielle devinée ;
  - test architectural existant (agnosticisme du contenu du graphe) toujours vert sans modification.
- `test_settings_page.py` (nouveau, `SettingsPage` réelle, Qt réel) :
  - au chargement, combo box vide (aucune découverte automatique), valeur persistée affichée via `setCurrentText` ;
  - clic sur "Rafraîchir les checkpoints" avec `list_checkpoints()` mocké en succès → combo box peuplé, valeur actuellement affichée conservée ;
  - clic sur "Rafraîchir les checkpoints" avec `list_checkpoints()` mocké en échec (`ComfyUIEngineError`) → liste vide/inchangée, aucune exception ne remonte à l'UI, saisie manuelle toujours possible ;
  - saisie manuelle d'un nom non présent dans la liste, puis sauvegarde → `ApplicationSettingsManager.update()` reçoit exactement le texte saisi ;
  - sélection d'un élément détecté, puis sauvegarde → `ApplicationSettingsManager.update()` reçoit exactement cet élément ;
  - rafraîchissement utilise l'URL **actuellement affichée** dans `comfyui_url_edit`, pas nécessairement déjà enregistrée ;
  - valeur déjà persistée restaurée correctement après rechargement (`update_application_settings()`), y compris quand elle n'est plus présente dans la liste redécouverte.

**Recherche préalable de mocks à signature obsolète** : cette mission n'ajoute ni ne modifie aucun paramètre de `GenerationManager`/`GenerationWorker` ni d'aucune méthode existante de `ComfyUIEngine` (`list_checkpoints()` est purement additive) — la procédure de recherche systématique de mocks (établie Mission 022) reste appliquée par précaution avant l'exécution de la suite complète, mais aucun mock existant ne devrait être concerné.

Nombre exact de tests final à confirmer après implémentation (341 + N nouveaux), comme pour chaque mission précédente.

### Résultats réels

Recherche préalable exécutée avant tout lancement Qt : le changement de type de `comfyui_checkpoint_name_edit` (`QLineEdit` → `QComboBox`) a bien cassé un test existant non anticipé en section 12 initiale — `tests/integration/test_application_settings_roundtrip.py::test_settings_page_application_section_lifecycle` utilisait `.text()`/`.setText()` sur ce widget. Corrigé (2 lignes, `.currentText()`/`.setCurrentText()`), sans changement de logique de test. Aucun autre mock/signature obsolète trouvé (aucun paramètre de méthode existante modifié). Aucune `QMessageBox` réelle rencontrée, aucun blocage.

Suites exécutées dans l'ordre prescrit : 15 tests ciblés `list_checkpoints()` → **15/15** ; `test_comfyui_engine.py` complet → **63/63** (48 + 15) ; `test_settings_page.py` (nouveau) → **14/14** ; `test_application_settings_roundtrip.py` → **14/14** ; `test_main_window_comfyui_settings.py` → **2/2** ; `test_settings_roundtrip.py` → **11/11**.

**Suite complète, une seule exécution : 370/370** (341 précédents + 29 nets nouveaux : 15 `ComfyUIEngineListCheckpointsTest` + 14 `SettingsPageCheckpointDiscoveryTest`).

## 14. Risques de régression

- **Changement de type de widget** (`QLineEdit` → `QComboBox`) : `comfyui_checkpoint_name_edit` est déjà lu/écrit uniquement dans `settings_page.py` (confirmé par recherche textuelle) — aucun autre fichier n'accède directement à ce widget, limitant le risque à ce seul fichier.
- **Comportement de `QComboBox.currentText()` avec `setEditable(True)`** : à vérifier explicitement par test Qt réel (pas seulement supposé) — la valeur doit être identique qu'elle provienne d'une sélection ou d'une saisie libre.
- **Appel réseau bloquant le thread UI sur clic "Rafraîchir"** : risque explicitement assumé et atténué par un timeout court dédié (section 7) — à confirmer empiriquement lors du smoke test que ce délai reste imperceptible/acceptable en usage réel, y compris quand ComfyUI est éteint (cas où le timeout est effectivement atteint).
- **Format de réponse `/object_info/CheckpointLoaderSimple`** : la structure exacte (`data["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]`) est basée sur la spécification ComfyUI publique et sur l'usage déjà fait manuellement en Mission 012, mais n'a pas été re-vérifiée dans le code du dépôt (aucun test automatisé actuel n'appelle cet endpoint) — à confirmer explicitement lors du smoke test réel avant de considérer `list_checkpoints()` fiable.
- **Régression Mission 018** (`MainWindow`/`GenerationManager` lisant `comfyui_checkpoint_name`) : aucun changement de `ApplicationSettings`/`ApplicationSettingsManager` prévu — couverte par les tests existants (`test_main_window_comfyui_settings.py`, `test_application_settings_roundtrip.py`), non modifiés.
- **Couverture partielle en environnement multi-serveur ou multi-`base_path` exotique** : si le smoke test révèle que `/object_info/CheckpointLoaderSimple` ne reflète pas la totalité des checkpoints attendus (scénario non anticipé par cet audit read-only), la saisie manuelle reste le filet de sécurité — pas un échec bloquant de la mission, mais à documenter comme limite connue si observé.

## 15. Critères d'acceptation

- Suite de tests complète verte, nombre exact confirmé.
- `git diff --stat` confirmant exactement le périmètre de fichiers de la section 12.
- `list_checkpoints()` ne propage jamais d'exception non contrôlée à l'UI — `SettingsPage` capture systématiquement `ComfyUIEngineError` autour de l'appel (section 5/8).
- Saisie manuelle d'un checkpoint toujours possible, y compris quand ComfyUI est injoignable ou que la découverte échoue.
- Valeur persistée toujours restaurée correctement au rechargement, présente ou non dans la liste redécouverte.
- Aucune modification de comportement pour `MainWindow`/`GenerationManager` (Mission 018) ni pour le slider de force img2img (Mission 024).
- **Smoke test réel démontrant que les checkpoints réellement exposés par l'instance ComfyUI Desktop de l'architecte (y compris via `extra_model_paths`/`shared_models.yaml`) apparaissent bien dans la liste découverte** — condition de réussite explicitement posée par l'architecte pour cette mission (section 16).

### Résultats réels

Tous les critères ci-dessus sont satisfaits : 370/370 tests verts ; `git diff --stat` conforme au périmètre réel (voir section 12, avec la correction ponctuelle de `test_application_settings_roundtrip.py` documentée en section 13) ; `list_checkpoints()` ne propage jamais d'exception non contrôlée (confirmé par tests automatisés et par le smoke test réel, capture du message "Découverte impossible..." à l'appui) ; saisie manuelle toujours disponible (confirmé réellement) ; valeur persistée restaurée correctement (confirmé réellement) ; `MainWindow`/`GenerationManager`/slider Mission 024 non affectés (suites dédiées toujours vertes, inchangées) ; smoke test réel PASS complet, checkpoints réellement exposés par ComfyUI Desktop bien présents dans la liste découverte.

## 16. Plan du smoke test manuel réel

Réalisé par l'architecte, guidé pas à pas, contre l'installation ComfyUI Desktop Windows déjà validée (Missions 012/023/024).

1. S'assurer que ComfyUI Desktop est démarré (URL déjà connue et fonctionnelle depuis Missions 012/018/023/024 : `http://127.0.0.1:8000`).
2. Cliquer sur "Rafraîchir les checkpoints" dans Settings et vérifier que le combo box se peuple avec le(s) checkpoint(s) réellement exposés par cette instance — **y compris, si applicable, ceux provenant de chemins partagés/`extra_model_paths` référencés par `shared_models.yaml`** (comparaison avec la liste déjà connue depuis Mission 012 : `Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors`, `juggernautXL_v8Rundiffusion.safetensors`, `v1-5-pruned-emaonly-fp16.safetensors`, à confirmer toujours cohérente ou à jour).
3. Sélectionner un checkpoint dans la liste (différent de la valeur par défaut actuelle si possible).
4. Cliquer sur "Enregistrer" (section Application).
5. Redémarrer AI Studio Toolkit.
6. Revenir sur Settings, cliquer sur "Rafraîchir les checkpoints", et vérifier que le checkpoint précédemment sélectionné est bien restauré/affiché dans le combo box.
7. Effectuer une génération txt2img simple depuis `InferencePage` et confirmer, par le résultat produit, que le checkpoint sélectionné est réellement celui utilisé par ComfyUI (comportement cohérent avec `GenerationManager._checkpoint_name`, Mission 018).
8. Test complémentaire de robustesse : arrêter temporairement ComfyUI Desktop (ou pointer `comfyui_url_edit` vers une adresse invalide), cliquer sur "Rafraîchir les checkpoints", vérifier que l'échec est géré sans exception ni blocage prolongé de l'UI (timeout court), et que la saisie manuelle reste possible et enregistrable.

### Résultats réels

Réalisé par l'architecte contre l'installation ComfyUI Desktop Windows réelle déjà validée (Missions 012/023/024, `http://127.0.0.1:8000`). Tous les points **PASS** : découverte des checkpoints via ComfyUI ; liste déroulante `ComfyUI Checkpoint` fonctionnelle ; checkpoints réellement exposés par ComfyUI Desktop (y compris via `extra_model_paths`/`shared_models.yaml` le cas échéant) bien présents dans la liste ; sélection d'un checkpoint ; sauvegarde ; restauration de la sélection après redémarrage ; génération réelle avec la configuration sélectionnée ; fallback lorsque ComfyUI est injoignable/configuration invalide ; aucun plantage de `SettingsPage` ; message d'indisponibilité correctement affiché (capture confirmant exactement le texte `"Découverte impossible : ComfyUI injoignable ou configuration invalide. La saisie manuelle du checkpoint reste disponible."`) ; saisie manuelle du checkpoint toujours disponible. **Smoke test fonctionnel : PASS**, déclaré par l'architecte.

## 17. Confirmation — aucune fonctionnalité hors périmètre

Aucune LoRA discovery, aucun ControlNet/IP-Adapter, aucun custom node, aucun téléchargement/installation/suppression de modèle, aucun démarrage/arrêt de ComfyUI, aucune refonte générale de `SettingsPage`, aucune sélection moteur/backend, aucun multi-référence, aucune modification de `comfyui_workflows.py` ni du paramètre `reference_strength`/`denoise` de Mission 024, aucun parsing de `shared_models.yaml`/`extra_model_paths`. Seule une nouvelle méthode additive de `ComfyUIEngine` (`list_checkpoints()`, réutilisant l'infrastructure HTTP déjà existante) et l'UI de sélection de checkpoint dans `SettingsPage` sont ajoutées.

### Résultats réels

Revue finale du diff confirmée : `git diff --stat` limité à `src/engines/comfyui_engine.py`, `src/ui/pages/settings_page.py`, `tests/integration/test_comfyui_engine.py`, `tests/integration/test_settings_page.py` (nouveau), et à la correction ponctuelle de 2 lignes dans `tests/integration/test_application_settings_roundtrip.py` (signature obsolète, section 13) — `comfyui_workflows.py`, `generation_manager.py`, `generation_worker.py`, `inference_page.py` absents du diff. Aucun terme hors périmètre (`lora`, `controlnet`, `ip-adapter`, `plugin`, multi-engine) trouvé dans le diff de production au-delà des mentions explicites de périmètre différé dans les commentaires/docstrings. Aucune fonctionnalité hors périmètre introduite.

## Commit correspondant

Non applicable à ce stade — implémentation et validation (automatisée + smoke test réel) terminées, clôture Git non encore effectuée (en attente d'autorisation explicite de l'architecte).

## Tag / release correspondant

Non applicable à ce stade — clôture Git non encore effectuée.

## État final

**Implémentation, tests automatisés (370/370) et smoke test manuel réel validés — PASS.** `SettingsPage` permet désormais de découvrir et sélectionner un checkpoint réellement exposé par le serveur ComfyUI en cours d'exécution (`GET /object_info/CheckpointLoaderSimple`, via `comfyui_url`), avec repli systématique sur la saisie manuelle en cas d'indisponibilité — confirmé par un smoke test réel complet contre ComfyUI Desktop Windows, incluant le cas de fallback. `comfyui_path` reste non consommé (voir `docs/PROJECT_CONTEXT.md`). **Clôture Git non encore effectuée** — en attente d'autorisation explicite de l'architecte pour le commit, le tag et le push.
