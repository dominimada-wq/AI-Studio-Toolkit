# Mission 010 — Application Settings Domain

Source : historique direct de la conversation de développement + `CHANGELOG.md` (section "Mission 010 — Application Settings Domain"), vérifié contre `git log`/`git tag`.

## Objectif

Introduire `ApplicationSettings`, objet Domain **Application-level** — niveau de configuration distinct de `Workspace.settings` (Mission 009), jamais persisté dans `project.json`. Domain minimal : `python_path`, `comfyui_path`, `onetrainer_path`. Candidat retenu à l'issue d'un audit architectural comparant trois options (`Job`, `Image` Domain, `Application Settings`) — `Application Settings` choisi car seul candidat ne déclenchant aucun anti-pattern identifié (scaffolding sans utilisateur réel, machine à états artificielle, migration lourde sans raison immédiate, nettoyage opportuniste).

## Modifications principales

- `ApplicationSettings` (dataclass, 3 champs).
- `ApplicationSettingsStorage` (`src/infrastructure/storage/`) — répertoire résolu en Python standard uniquement (`os`/`pathlib`, aucun `QStandardPaths`/dépendance nouvelle) : `%LOCALAPPDATA%\AIStudioToolkit\` sous Windows, repli déterministe `Path.home()/AppData/Local/AIStudioToolkit` si `LOCALAPPDATA` absent. Fichier `application_settings.json`. Lecture non bloquante (absent/vide/JSON invalide/racine non-dict/`OSError` → défauts + warning, jamais d'exception). Écriture atomique (fichier temporaire dans le même répertoire → `flush()` + `os.fsync()` → `os.replace()`) ; `ApplicationSettingsStorageError` levée sur échec, ancien fichier valide garanti intact, nettoyage best-effort du temporaire.
- `ApplicationSettingsManager(storage_directory=None, event_bus=None)` — **aucune dépendance à `WorkspaceManager`**. Stratégie **"candidate-first"** : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire — un échec de sauvegarde laisse la mémoire strictement inchangée (divergence assumée par rapport à `SettingsManager`, Mission 009, jugée supérieure mais non rétrofittée).
- Événement `application_settings.updated` — publié uniquement après sauvegarde réussie, aucune publication sur no-op ou échec.
- `SettingsPage` scindée en **deux sections strictement indépendantes** : Workspace Settings (inchangée) et Application Settings (disponible et activée en permanence, y compris sans Workspace ouvert), chacune avec son propre bouton "Enregistrer" et son propre canal de rafraîchissement. Étanchéité vérifiée dans les deux sens (un événement Workspace ne touche jamais la section Application, et réciproquement).

## Fichiers importants créés ou modifiés

Créés : `application_settings.py`, `application_settings_storage.py`, `application_settings_manager.py`, `test_application_settings_roundtrip.py`.
Modifiés : `settings_page.py`, `main_window.py`, `test_settings_roundtrip.py` (adaptation mineure de signature/`_wire()`).

## Décisions techniques

- Séparation stricte des scopes : `python_path`/`comfyui_path`/`onetrainer_path` jamais dans `project.json` ; `theme`/`language` jamais dans `application_settings.json`.
- Aucune migration automatique depuis `Workspace.settings` — les deux stockages n'ont jamais été liés.
- Aucun `settings_id` — singleton, même principe que `Settings`/`Workspace`.
- Hors périmètre explicite : validation d'existence des chemins, lancement réel de Python/ComfyUI/OneTrainer, clés API, secrets, chiffrement, `Job`, `Engine`, `Plugin`, `Service`, `AI Orchestrator`, `Image` Domain, support Linux/macOS validé.

## Tests et validations

`test_application_settings_roundtrip.py` (13 tests) : round-trip et défauts Domain, résolution `default_directory()` (LOCALAPPDATA simulé + repli), matrice de compatibilité `load()`, round-trip Unicode réel, écriture atomique + préservation du dernier fichier valide en cas d'échec, chargement/idempotence/atomicité du Manager, cohérence mémoire/disque après échec, persistance entre deux instances, indépendance totale vis-à-vis de `WorkspaceManager`, cycle de vie UI complet, étanchéité bidirectionnelle des deux sections, absence de duplication d'abonnements.

## Commit correspondant

6 commits, vérifiés par `git log --oneline --reverse` entre `v0.2-mission009` et `v0.2-mission010` :

```
791e1b6 Introduce ApplicationSettings domain object
10dd467 Add atomic ApplicationSettings storage
6cc47f2 Add ApplicationSettingsManager with persisted updates
0ac31c4 Integrate Application Settings into SettingsPage
46c1174 tests: add Application Settings storage and lifecycle coverage
089d8e3 docs: document Application Settings and close Mission 010
```

Correspond exactement aux "5 commits" du CHANGELOG (développement) + le 6ᵉ commit de clôture documentaire.

## Tag / release correspondant

`v0.2-mission010` — **annoté** (`git cat-file -t` = `tag`), cible `089d8e338b4649a8242ed094bab74f748f765187`, présent localement et sur `origin` (`git ls-remote --tags origin` confirmé). Titre et Release Notes GitHub rédigés dans la conversation. **GitHub Release publiée** — confirmé directement par l'architecte du projet (information fiable ; non re-vérifiable techniquement depuis cet environnement, `gh` CLI absent).

## État final

Mission terminée. `main` synchronisé avec `origin/main`, tag `v0.2-mission010` poussé. Deux niveaux de préférences strictement séparés (Workspace Settings / Application Settings), 80 tests d'intégration. Mission 011 non définie — nécessitera son propre audit architectural.
