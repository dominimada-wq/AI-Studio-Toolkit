# Mission 113 — Local Engine Installation Paths and Static Launcher Validation

> **CONTRAT PRÉ-IMPLÉMENTATION — NON ENCORE IMPLÉMENTÉE.** Ce document sert de périmètre fermé avant toute implémentation. Le code ne sera écrit qu'après validation explicite par l'architecte.

## 1. Contexte

Le micro-audit environnemental post-Mission 112 (lecture seule, aucun backend lancé) a établi par inspection directe des fichiers réellement présents sur la machine :

- `ApplicationSettings.comfyui_path` (`application_settings.py:23`) correspond exactement au `basePath`/`--base-directory` réel de ComfyUI Desktop (confirmé par `%APPDATA%\ComfyUI\config.json` : `"basePath": "J:\\Programmes\\ComfyUI"`, identique à la valeur stockée) — une racine de données pure (`.venv`, `models`, `input`, `output`, `user`, `custom_nodes`), **jamais** l'installation de l'application elle-même.
- Le véritable point d'entrée exécuté par ComfyUI Desktop est `main.py`, confirmé présent à `%LOCALAPPDATA%\Programs\ComfyUI\resources\ComfyUI\main.py` — un chemin entièrement distinct de `comfyui_path`, non dérivable de celui-ci, propre à l'installation Electron. La commande réellement exécutée par Desktop (capturée dans `%APPDATA%\ComfyUI\logs\main.log`) le confirme littéralement : `J:\Programmes\ComfyUI\.venv\Scripts\python.exe C:\Users\...\Programs\ComfyUI\resources\ComfyUI\main.py --base-directory J:\Programmes\ComfyUI ...`.
- Aucun champ `forge_path` n'existe dans `ApplicationSettings` alors que Forge dispose déjà de `forge_url`/`forge_lora_expose_path` (`application_settings.py:95-101`). L'installation Forge réelle (`J:\Programmes\WebUI Forge CU121\`) est une installation portable classique confirmée par les fichiers réels : `run.bat`/`environment.bat` à la racine, `system\python\` (Python portable embarqué, pas un `.venv`), et `webui\launch.py` comme point d'entrée Python réel. `run.bat` est le seul point d'entrée fiable — appeler `launch.py` directement sans l'environnement construit par `environment.bat` (PATH, `SKIP_VENV=1`) est fragile.
- Le seul précédent architectural existant pour ce type de validation est `src/engines/onetrainer_launch.py::resolve_onetrainer_launch()` (Mission 100) : une fonction pure, sans Qt, sans réseau, qui valide par existence de fichiers la configuration de lancement d'un moteur local à partir d'un seul chemin de configuration, lève une exception dédiée à message actionnable (`OneTrainerLaunchError`) en cas d'échec, et retourne un `NamedTuple` de configuration en cas de succès. Ni `TrainingPage` ni le futur runner ne dupliquent cette logique — ils l'appellent tous les deux.
- Le diagnostic de connexion HTTP livré par Mission 112 (`check_connection()`) teste la joignabilité **applicative** d'un backend déjà démarré — un concept strictement distinct de la présente mission, qui valide la **présence sur disque** d'une installation locale, indépendamment de tout état d'exécution.
- Audit de sémantique des champs de chemin existants (préalable requis avant toute implémentation) :
  - `onetrainer_path` : confirmé être une racine de dossier (`resolve_onetrainer_launch()` résout `<onetrainer_path>/venv/Scripts/python.exe` et `<onetrainer_path>/scripts/train_remote.py`) — un vrai dossier, sans bouton « Parcourir… » aujourd'hui malgré cette contrainte physique déjà établie.
  - `comfyui_path` : confirmé être une racine de dossier (voir ci-dessus) — même absence de bouton « Parcourir… » aujourd'hui.
  - `python_path` (`application_settings.py:21`) : **sémantique non déterminée**. Aucun code ne le consomme (confirmé par recherche exhaustive — seul `settings_page.py`/`application_settings_manager.py` le font transiter). `onetrainer_launch.py` documente explicitement (ligne 11) qu'il n'est **jamais** utilisé pour résoudre l'interpréteur réellement utilisé par OneTrainer. Le Blueprint (`01_PRODUCT_REQUIREMENTS.md`, section 8) le liste comme un item autonome (« Python »), sans préciser s'il s'agit d'un dossier d'installation ou du chemin direct vers un exécutable. **Décision de cette mission : `python_path` reste exclu du périmètre `Parcourir…`** — lui appliquer `getExistingDirectory()` par analogie avec les autres champs serait une supposition non vérifiée sur un champ dont personne ne consomme la valeur ; un futur besoin réel devra trancher sa sémantique exacte avant de lui donner un sélecteur.

## 2. Objectif

Donner à `ApplicationSettings` une configuration explicite des racines d'installation locale ComfyUI et Forge, et une validation statique (existence du point d'entrée attendu sur disque) consultable depuis Settings — sans lancer, arrêter, ni gérer le cycle de vie d'aucun processus. Cette mission prépare seulement le terrain pour une future mission de lancement (« Start »), sans la préjuger.

## 3. Décision retenue — mécanisme

**Domain** (`src/domain/application_settings.py`) : deux nouveaux champs, même convention que les champs d'installation existants (`""` = non configuré, jamais un défaut inventé) :
- `comfyui_install_path: str = ""` — racine de l'installation ComfyUI **Local/Desktop**, distincte de `comfyui_path` (données) ; ajouté juste après `comfyui_path` dans le dataclass, `to_dict()`, `from_dict()` (`data.get("comfyui_install_path", "")`, compatible avec un `application_settings.json` existant qui ne le contient pas).
- `forge_path: str = ""` — racine de l'installation Forge locale ; ajouté juste avant `forge_url` dans le dataclass/`to_dict()`/`from_dict()` (même garde `data.get("forge_path", "")`).

**`ApplicationSettingsManager.update()`** : deux nouveaux paramètres optionnels `comfyui_install_path`/`forge_path`, exactement le même patron que `onetrainer_path` (comparaison `!= current.*` pour `changed`, report inchangé dans `candidate` si `None`).

**Résolveurs statiques, Qt-free, dans `src/engines/`** — même famille architecturale que `onetrainer_launch.py`, **deux modules distincts**, pas de helper partagé artificiellement symétrique (la structure de vérification diffère : un fichier `.py` sous un sous-dossier à deux niveaux pour ComfyUI, un `.bat` à la racine pour Forge) :

`src/engines/comfyui_install.py` :
```python
class ComfyUIInstallError(Exception): ...

class ComfyUIInstallConfig(NamedTuple):
    entry_point: str
    install_root: str

def resolve_comfyui_install(comfyui_install_path: str) -> ComfyUIInstallConfig:
    # blank -> ComfyUIInstallError actionnable
    # <comfyui_install_path>/resources/ComfyUI/main.py absent -> ComfyUIInstallError actionnable
    # sinon -> ComfyUIInstallConfig(entry_point=..., install_root=...)
```

`src/engines/forge_install.py` :
```python
class ForgeInstallError(Exception): ...

class ForgeInstallConfig(NamedTuple):
    entry_point: str
    install_root: str

def resolve_forge_install(forge_path: str) -> ForgeInstallConfig:
    # blank -> ForgeInstallError actionnable
    # <forge_path>/run.bat absent -> ForgeInstallError actionnable
    # sinon -> ForgeInstallConfig(entry_point=..., install_root=...)
```

Messages d'exception en anglais, comme `ComfyUIEngineError`/`ForgeEngineError`/`OneTrainerLaunchError` (convention déjà établie et uniforme dans toute la couche `src/engines/`, indépendante de la langue française des libellés Settings — déjà le cas aujourd'hui pour les erreurs `check_connection()` affichées telles quelles). Ni l'un ni l'autre resolver n'importe Qt, n'ouvre de socket, ni n'exécute quoi que ce soit — uniquement `Path.is_file()`.

**`SettingsPage`** : pour chacun des deux nouveaux champs, un `QLineEdit` + bouton « Parcourir… » (`QFileDialog.getExistingDirectory()`, pattern `browse_lora_library_path()` déjà établi) sur sa propre ligne, puis une ligne dédiée bouton « Vérifier l'installation » + label de statut (pattern visuel identique à la ligne « Tester la connexion » de Mission 112, mais **sans aucune construction d'Engine ni appel réseau** — appel direct du resolver pur). `comfyui_path_edit` et `onetrainer_path_edit` reçoivent également un bouton « Parcourir… », en réutilisant exactement le même pattern (`getExistingDirectory()`), puisque leur sémantique de dossier est déjà confirmée par le code existant (`resolve_onetrainer_launch()` pour le second, `basePath` Desktop pour le premier) — **`python_path_edit` n'en reçoit pas**, pour la raison exposée en §1.

**Invalidation du statut** : mêmes principes que Mission 112, adaptés au fait qu'il n'y a ici ni réseau ni URL mais un chemin de dossier modifiable par saisie **ou** par Parcourir — les deux doivent invalider le statut, contrairement à Mission 112 où seule la saisie clavier existait (pas de Parcourir sur un champ URL). `textEdited` du champ réinitialise le statut à neutre (« Installation non vérifiée. ») exactement comme M112 ; la méthode `browse_comfyui_install_path()`/`browse_forge_path()` appelle en plus, après un choix de dossier réel, le même réinitialiseur — pour que le label affiché ne mente jamais après un changement de dossier via Parcourir. C'est une extension du patron M112, pas une reproduction à l'identique — signalée explicitement ici pour validation.

## 4. Comportement contractuel

1. `comfyui_path` garde exactement sa signification actuelle (racine de données/`--base-directory`) — aucun changement de son contrat, de son libellé fonctionnel, ni de sa valeur par défaut.
2. `comfyui_install_path`/`forge_path` sont deux réglages **nouveaux et indépendants**, `""` par défaut, jamais consommés par aucun Engine, Manager, ou composition-root (`MainWindow`) dans cette mission — uniquement stockés et validables statiquement.
3. `resolve_comfyui_install()`/`resolve_forge_install()` ne touchent jamais le réseau, ne lancent jamais de process, et ne préjugent d'aucune commande de lancement future — ils valident uniquement la présence sur disque d'un point d'entrée nommé.
4. Un chemin vide ou composé uniquement d'espaces lève l'exception dédiée avec un message actionnable, jamais un chemin implicite ou une exception générique.
5. La validation statique et le diagnostic de connexion HTTP (Mission 112) restent deux états strictement distincts, jamais fusionnés dans un seul label ou une seule méthode.
6. Aucune sauvegarde implicite : cliquer sur « Vérifier l'installation » ne modifie jamais `ApplicationSettings`, exactement comme « Tester la connexion ».
7. Une modification du chemin (saisie clavier réelle, ou choix via Parcourir) réinitialise uniquement le statut de son propre moteur à un état neutre.
8. Aucun champ, méthode ou comportement existant de Mission 112 (`check_connection()`, boutons de test de connexion) n'est modifié.
9. `python_path` n'est pas modifié, ni dans `ApplicationSettings`, ni dans `SettingsPage` (aucun bouton ajouté), ni dans aucun resolver.
10. ComfyUI Local et un futur ComfyUI Cloud restent des concepts distincts : `comfyui_install_path` et les resolvers introduits ici décrivent exclusivement une installation **locale**, jamais une hypothèse d'exécuteur/provider cloud — aucune structure n'est créée qui présupposerait qu'un usage de ComfyUI nécessite toujours une installation locale.

## 5. Périmètre exact — fichiers concernés

- `src/domain/application_settings.py` (modifié) — `comfyui_install_path`, `forge_path`.
- `src/managers/application_settings_manager.py` (modifié) — `update()` étendu.
- `src/engines/comfyui_install.py` (nouveau) — `resolve_comfyui_install()`, `ComfyUIInstallConfig`, `ComfyUIInstallError`.
- `src/engines/forge_install.py` (nouveau) — `resolve_forge_install()`, `ForgeInstallConfig`, `ForgeInstallError`.
- `src/ui/pages/settings_page.py` (modifié) — nouveaux champs/boutons/labels pour ComfyUI/Forge, boutons « Parcourir… » ajoutés à `comfyui_path_edit`/`onetrainer_path_edit`.
- `tests/integration/test_application_settings_roundtrip.py` (modifié) — round-trip des deux nouveaux champs, compatibilité ancien fichier.
- `tests/integration/test_comfyui_install.py` (nouveau) — tests du resolver ComfyUI.
- `tests/integration/test_forge_install.py` (nouveau) — tests du resolver Forge.
- `tests/integration/test_settings_page.py` (modifié) — nouveaux champs/boutons/validation.

**Aucun changement attendu** à `src/ui/pages/inference_page.py`, `src/managers/generation_manager.py`, `src/engines/comfyui_engine.py`, `src/engines/forge_engine.py`, `src/ui/main_window.py`, `src/engines/onetrainer_launch.py`, Domain (hors `application_settings.py`), EventBus — si l'implémentation réelle révèle qu'un changement dans l'un de ces fichiers est nécessaire, arrêt et rapport avant tout élargissement.

## 6. Hors périmètre strict — ne pas ajouter à cette mission

- Aucun `Start`/`Stop`/`Restart`, aucun `QProcess`/`subprocess`, aucune notion d'ownership de process, aucun PID tracking, aucun Windows Job Object.
- Aucun auto-lancement, auto-reconnexion, ni polling.
- Aucune modification d'`InferencePage`, `GenerationManager`, ou des Engines HTTP (`ComfyUIEngine`/`ForgeEngine`, y compris `check_connection()`).
- Aucune commande de lancement figée ou codée en dur (ni `python.exe main.py --base-directory ... --listen ... --port ...` pour ComfyUI, ni `cmd.exe /c run.bat` pour Forge) — ces stratégies restent des pistes documentées pour une future mission « Start », jamais implémentées ici.
- Aucune détection assistée automatique du chemin Desktop par défaut (`%LOCALAPPDATA%\Programs\ComfyUI`) — l'utilisateur configure `comfyui_install_path` manuellement dans cette mission.
- Aucune intégration ComfyUI Cloud, aucun changement lié à Fooocus.
- Aucun changement de comportement de `python_path`.

## 7. Étape technique attendue

**`src/domain/application_settings.py`** : ajout des deux champs (voir §3), mise à jour de `to_dict()`/`from_dict()` avec gardes `data.get(..., "")`.

**`src/managers/application_settings_manager.py`** : `update(..., comfyui_install_path: Optional[str] = None, forge_path: Optional[str] = None)`, intégré à `changed`/`candidate` selon le patron exact déjà utilisé pour `onetrainer_path`.

**`src/engines/comfyui_install.py`**/**`src/engines/forge_install.py`** : voir §3 pour le contrat exact — mêmes principes que `onetrainer_launch.py` (docstring expliquant pourquoi tel champ n'est pas utilisé si pertinent, exception à message actionnable citant le chemin résolu complet, `NamedTuple` de résultat).

**`SettingsPage`** :
- Nouveaux widgets : `comfyui_install_path_edit` + `comfyui_install_browse_button`, `comfyui_install_check_button` + `comfyui_install_status_label` (init « Installation non vérifiée. ») ; `forge_path_edit` + `forge_path_browse_button`, `forge_install_check_button` + `forge_install_status_label` (même init).
- `comfyui_path_edit`/`onetrainer_path_edit` : ajout d'un bouton « Parcourir… » chacun, réutilisant `QFileDialog.getExistingDirectory()`.
- Méthodes `check_comfyui_install()`/`check_forge_install()` : appellent directement `resolve_comfyui_install(self.comfyui_install_path_edit.text())`/`resolve_forge_install(self.forge_path_edit.text())` dans un `try`/`except`, écrivent dans leur propre label uniquement.
- Méthodes `browse_comfyui_path()`/`browse_onetrainer_path()`/`browse_comfyui_install_path()`/`browse_forge_path()`, patron identique à `browse_lora_library_path()`.
- Handlers `_on_comfyui_install_path_edited()`/`_on_forge_path_edited()` connectés à `textEdited`, réinitialisant leur propre label ; les méthodes `browse_comfyui_install_path()`/`browse_forge_path()` appellent le même réinitialiseur après un choix de dossier réussi.
- `update_application_settings()`/`save_application_settings()` étendus pour les deux nouveaux champs, patron identique aux champs existants.

## 8. Tests attendus

**`tests/integration/test_application_settings_roundtrip.py`** :
1. Un `application_settings.json` sans `comfyui_install_path`/`forge_path` se charge sans erreur, les deux valant `""`.
2. Round-trip `comfyui_install_path` (`to_dict()`/`from_dict()`).
3. Round-trip `forge_path`.
4. `ApplicationSettingsManager.update()` accepte et persiste les deux nouveaux champs, idempotence stricte (valeur identique → `False`, aucun `save()`).

**`tests/integration/test_comfyui_install.py`** (mêmes principes que `test_onetrainer_launch.py`, répertoires temporaires réels, aucune dépendance à l'installation réelle de la machine) :
1. Chemin vide/blanc → `ComfyUIInstallError`.
2. Dossier existant mais `resources/ComfyUI/main.py` absent → `ComfyUIInstallError`, message citant le chemin attendu.
3. Chemin inexistant → `ComfyUIInstallError`.
4. Installation complète (fichier `resources/ComfyUI/main.py` présent) → `ComfyUIInstallConfig` correct.

**`tests/integration/test_forge_install.py`** : les 4 mêmes cas, adaptés à `run.bat` à la racine.

**`tests/integration/test_settings_page.py`** :
5. Chargement des nouveaux champs depuis `ApplicationSettings`.
6. Sauvegarde des nouveaux champs.
7. Bouton Parcourir de chaque nouveau champ + de `comfyui_path_edit`/`onetrainer_path_edit` ouvre bien un sélecteur de **dossier** (jamais de fichier).
8. Clic sur « Vérifier l'installation » avec un resolver réussissant/échouant (mock du resolver ou répertoire temporaire réel) → label positif/négatif correct, par moteur.
9. Le label de validation statique et le label de connexion HTTP restent indépendants l'un de l'autre (tester l'un ne modifie jamais l'autre).
10. Ni « Vérifier l'installation » ni Parcourir n'appellent `save_application_settings()`.
11. Une saisie clavier réelle **et** un choix via Parcourir réinitialisent chacun le statut à neutre.
12. Smoke Qt réel pertinent puisque `SettingsPage` change : un vrai clic sur un vrai widget, avec un vrai répertoire temporaire jouant le rôle d'installation (aucun mock du resolver, aucune dépendance à une installation réelle de la machine) — installation valide reconnue, installation invalide rejetée avec message actionnable.

## 9. Critères de clôture

1. `comfyui_install_path`/`forge_path` ajoutés à `ApplicationSettings`, round-trip et compatibilité ascendante testés.
2. `resolve_comfyui_install()`/`resolve_forge_install()` implémentés à l'identique du patron `resolve_onetrainer_launch()`, testés selon §8.
3. `comfyui_path_edit`/`onetrainer_path_edit`/`comfyui_install_path_edit`/`forge_path_edit` disposent tous d'un bouton « Parcourir… » ; `python_path_edit` n'en reçoit pas.
4. Validation statique et diagnostic de connexion M112 restent deux mécanismes et deux états visuellement distincts.
5. Zéro modification d'`InferencePage`, `GenerationManager`, `ComfyUIEngine`/`ForgeEngine`, `MainWindow`, `onetrainer_launch.py` — sauf anomalie réelle découverte et rapportée avant tout élargissement.
6. Suite complète verte au nombre exact, `git diff --check` propre.
7. Aucun élément de la section 6 (hors périmètre) n'a été ajouté.

## 10. Documentation

Cette mission ne referme aucun besoin futur déjà enregistré dans `docs/PROJECT_CONTEXT.md` — les entrées « Gestion automatique du backend ComfyUI »/« ... Forge » restent entièrement ouvertes pour tout ce qui touche Start/Stop/ownership ; elle documente seulement, pour la première fois, une configuration explicite et validable des racines d'installation locale, préalable factuel à ces besoins. La régularisation documentaire post-clôture suivra le même processus que les missions précédentes, après commit/tag/Release.

## 11. Autorisation

Ce document sert de contrat avant toute implémentation. Le code ne sera écrit qu'après validation explicite de ce périmètre par l'architecte.
