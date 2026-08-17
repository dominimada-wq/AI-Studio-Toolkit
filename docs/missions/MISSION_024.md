# Mission 024 — Réglage utilisateur de la force img2img

Source : audit read-only préalable (reconstruction de l'architecture réelle après Mission 023 depuis le code, comparaison de sept candidats — A: réglage denoise, B: multi-reference avec rôles, C: IP-Adapter, D: ControlNet, E: exploitation de `comfyui_path`, F: tri de la galerie Images, G: autre), Candidat A recommandé puis validé par l'architecte. Spécification pré-implémentation — **aucun code applicatif ni aucun test n'a encore été modifié à ce stade**. Conformément au principe de non-auto-référence déjà établi (`docs/PROJECT_CONTEXT.md`), aucun hash de commit/tag n'est fixé en dur ici ; les sections "Commit correspondant"/"Tag / release correspondant" seront complétées après implémentation et clôture Git réelles.

## 1. Contexte

Mission 023 a livré la première consommation réelle d'une image de référence via un workflow img2img natif ComfyUI, avec une valeur `denoise` fixe (`DEFAULT_IMG2IMG_DENOISE = 0.75`, définie dans `src/engines/workflows/comfyui_workflows.py`). Le smoke test manuel réel de Mission 023 a démontré empiriquement que l'équilibre entre fidélité à la référence et liberté du prompt dépend du couple référence/prompt/checkpoint, sans qu'une valeur unique convienne à tous les cas — besoin enregistré comme "Réglage utilisateur de la force img2img / `denoise`" dans `docs/PROJECT_CONTEXT.md`. `build_img2img_workflow()` accepte déjà un paramètre `denoise: float = DEFAULT_IMG2IMG_DENOISE` (aucune modification requise à ce niveau) — seule la chaîne d'appel au-dessus (`ComfyUIEngine.generate_image()` → `GenerationManager.generate()` → `GenerationWorker` → `InferencePage`) ne le transmet pas.

## 2. Objectif

Rendre ce paramètre réellement contrôlable par l'utilisateur depuis `InferencePage`, via un curseur (slider) accompagné d'une valeur numérique visible, en suivant le patron de câblage bout-en-bout déjà validé par les Missions 022/023 (transport à travers les mêmes couches, sans nouvelle abstraction Domain/Manager).

## 3. Architecture avant Mission 024

```
InferencePage
  _reference_image_path: Optional[str]
       │ _start_generation()
       ▼
GenerationWorker(generation_manager, prompt_text, output_directory, reference_images)
       │ run()
       ▼
GenerationManager.generate(prompt_text, output_directory, reference_images=None)
  - upload_image() si 1 référence
  - ComfyUIEngine.generate_image(checkpoint_name=..., reference_image=<dict ou None>)
       ▼
ComfyUIEngine.generate_image(..., reference_image=None)
  - reference_image is None → build_txt2img_workflow(...)
  - sinon → build_img2img_workflow(..., denoise=DEFAULT_IMG2IMG_DENOISE)  ← valeur fixe, non paramétrée par l'appelant
```

`denoise` n'existe aujourd'hui nulle part au-dessus de `build_img2img_workflow()` — ni dans la signature de `ComfyUIEngine.generate_image()`, ni dans `GenerationManager.generate()`, ni dans `GenerationWorker`, ni dans `InferencePage`.

## 4. Nom du paramètre par couche (frontière générique / ComfyUI)

Décision : le concept doit rester générique jusqu'à `ComfyUIEngine` inclus dans son rôle d'appelant, et ne devenir `denoise` qu'à l'unique point où le vocabulaire ComfyUI natif du workflow est effectivement utilisé.

| Couche | Nom du paramètre | Type | Vocabulaire |
|---|---|---|---|
| `InferencePage` (UI) | `reference_strength_slider` / libellé "Force de transformation" | `int` (0–100, widget Qt) converti en `float` (0.0–1.0) à l'appel | générique |
| `GenerationWorker` | `reference_strength` | `Optional[float]` | générique |
| `GenerationManager.generate()` | `reference_strength` | `Optional[float]` | générique |
| `ComfyUIEngine.generate_image()` | `denoise` | `float`, défaut `DEFAULT_IMG2IMG_DENOISE` | natif ComfyUI (cette classe parle déjà ce vocabulaire pour `checkpoint_name`) |
| `build_img2img_workflow()` | `denoise` | `float` | natif ComfyUI (inchangé depuis Mission 023) |

La traduction `reference_strength` → `denoise` se fait exactement à l'appel `GenerationManager` → `ComfyUIEngine.generate_image(..., denoise=reference_strength)` : `GenerationManager` ne fait que transmettre un `float` sous le nom de paramètre attendu par la méthode appelée, sans jamais interpréter de structure JSON ComfyUI (contrairement au `dict reference_image`, qui reste strictement opaque). Ce choix évite d'importer `DEFAULT_IMG2IMG_DENOISE` dans `generation_manager.py` : quand `reference_strength` vaut `None` (valeur non fournie, rétrocompatibilité), `denoise` n'est simplement pas transmis, et `ComfyUIEngine.generate_image()`/`build_img2img_workflow()` retombent naturellement sur leur défaut existant `0.75` — garantie structurelle, pas conventionnelle, que la valeur historique par défaut n'est jamais modifiée.

Un futur moteur (Fooocus/Automatic1111/Forge/cloud) pourrait exposer un concept équivalent sous un nom différent sans toucher `InferencePage`/`GenerationWorker`/`GenerationManager` — seule la traduction finale, interne à l'Engine concerné, changerait. Aucun système d'abstraction multi-engine n'est créé pour cela : ce découplage est un effet de bord du nommage, pas une nouvelle capacité.

## 5. Comportement précis du slider

- Widget : `QSlider(Qt.Horizontal)`, plage entière `0`–`100` (Qt ne supporte pas nativement les valeurs flottantes sur `QSlider` — conversion `value / 100.0` à la lecture, `int(round(0.75 * 100))` = `75` à l'initialisation).
- `QLabel` de légende statique : "Force de transformation :".
- `QLabel` de valeur dynamique, affichant la valeur convertie avec deux décimales (ex. `"0.75"`), mis à jour à chaque `valueChanged` du slider.
- Placement : nouvelle ligne (`QHBoxLayout`) juste après `reference_row` (sélection de référence) et avant `preview_label`, cohérent avec le regroupement fonctionnel existant (contrôles liés à la référence groupés ensemble).
- État initial (aucune référence sélectionnée) : slider **visible mais désactivé**, valeur `75` (0.75), label de valeur affichant `"0.75"`.
- Activation : dès qu'une référence est sélectionnée (`_on_select_reference_clicked`), le slider devient actif — même mécanisme que `remove_reference_button`, ajouté à `_set_reference_controls_enabled()`.
- Désactivation + reset : le retrait de la référence (`_on_remove_reference_clicked`) et le changement de workspace (`reset_for_workspace_change` → `_clear_reference_selection()`) désactivent le slider et **remettent sa valeur à `75` (0.75)** — choix motivé par le fait que `_clear_reference_selection()` est déjà le point de reset unique partagé par ces deux appelants (Mission 022) ; ajouter le reset du slider ici plutôt que dupliquer la logique dans deux endroits suit ce même principe. Aucune persistance entre sessions ni dans `project.json`.
- Pendant une génération en cours (`_set_reference_controls_enabled(False)`), le slider est désactivé comme `remove_reference_button` ; à la fin, il redevient actif uniquement si une référence est toujours sélectionnée (même logique conditionnelle que `remove_reference_button` aujourd'hui).

## 6. Transmission de la valeur

`_start_generation()` lit `self.reference_strength_slider.value() / 100.0` à chaque appel (pas de mise en cache) et le transmet systématiquement à `GenerationWorker(..., reference_strength=...)`, que `reference_images` soit vide ou non — `GenerationManager.generate()` reste seul responsable de ne l'utiliser que si `reference_images` est non vide (cohérent avec la manière dont `reference_images` lui-même est déjà toujours construit comme une liste, potentiellement vide, plutôt que conditionnellement omis).

## 7. Périmètre IN

- `QSlider` + `QLabel` de valeur dans `InferencePage`, activé/désactivé selon la présence d'une référence, réinitialisé au retrait de la référence ou au changement de workspace.
- Transmission bout-en-bout `InferencePage` → `GenerationWorker` → `GenerationManager.generate(reference_strength=...)` → `ComfyUIEngine.generate_image(denoise=...)` → `build_img2img_workflow(denoise=...)` (déjà prêt, inchangé).
- Tests Qt réels sur le nouveau contrôle (existence, état initial, activation/désactivation, reset, valeur affichée) + tests de câblage sur chaque couche traversée.
- Smoke test manuel réel démontrant l'effet visuel d'une valeur différente de `0.75`.

## 8. Périmètre OUT (explicitement différé, listé dans `docs/PROJECT_CONTEXT.md`)

Multi-référence ; rôles de références ; IP-Adapter ; ControlNet ; sélection de LoRA ; sélection automatique de checkpoint ; exploitation de `comfyui_path` ; tri de la galerie Images ; persistance du réglage (session ou `project.json`) ; nouveau système d'abstraction multi-engine ; modification de la valeur par défaut historique `0.75` ; modification de `build_img2img_workflow()`/`build_txt2img_workflow()`/`comfyui_workflows.py`.

## 9. Fichiers réellement concernés

- `src/ui/pages/inference_page.py` — nouveau slider + label, wiring, reset, activation/désactivation.
- `src/ui/generation_worker.py` — nouveau paramètre `reference_strength: Optional[float] = None`, forwardé à `generate()`.
- `src/managers/generation_manager.py` — nouveau paramètre `reference_strength: Optional[float] = None`, forwardé comme `denoise=` à `ComfyUIEngine.generate_image()` uniquement quand une référence est présente et que la valeur est fournie.
- `src/engines/comfyui_engine.py` — `generate_image()` gagne un paramètre `denoise: float = DEFAULT_IMG2IMG_DENOISE`, forwardé à `build_img2img_workflow(denoise=denoise)`.
- `tests/integration/test_inference_page.py`, `tests/integration/test_generation_worker.py`, `tests/integration/test_generation_manager.py`, `tests/integration/test_comfyui_engine.py` — tests adaptés/ajoutés (voir section 10).
- **Aucune modification attendue** de `src/engines/workflows/comfyui_workflows.py` (déjà prêt depuis Mission 023), ni de `src/domain/`, ni de `WorkspaceStorage`/`project.json`.

## 10. Stratégie de tests

**Recherche préalable obligatoire avant toute exécution de la suite Qt** (procédure établie Mission 022, reconduite Mission 023) : `GenerationWorker.run()` appellera désormais `generation_manager.generate(..., reference_strength=...)` — tout mock/fake local reproduisant l'ancienne signature de `GenerationManager.generate()` dans `tests/integration/test_generation_worker.py` doit être recherché et adapté **avant** exécution, pour éviter la répétition exacte du mode d'échec Mission 022 (`TypeError` → `GenerationWorker.failed` → `QMessageBox.critical` réel non mocké → blocage indéfini). Même vigilance pour tout fake de `ComfyUIEngine.generate_image()` dans `tests/integration/test_generation_manager.py`/`test_comfyui_engine.py`.

- `test_inference_page.py` (nouveaux) : slider présent et désactivé à l'état initial avec valeur `0.75` affichée ; activé après sélection d'une référence ; désactivé et remis à `0.75` après retrait de la référence ; désactivé et remis à `0.75` après changement de workspace ; label de valeur mis à jour en déplaçant le slider ; désactivé pendant une génération en cours puis réactivé seulement si une référence reste sélectionnée ; valeur du slider correctement transmise à la construction de `GenerationWorker`.
- `test_generation_worker.py` (adaptés + nouveaux) : `reference_strength` stocké et transmis à `generate()` ; comportement par défaut (`None`) inchangé pour les tests existants.
- `test_generation_manager.py` (adaptés + nouveaux) : `reference_strength` transmis comme `denoise=` uniquement quand une référence est présente ; `reference_strength=None` → `generate_image()` appelé sans `denoise=` (défaut `ComfyUIEngine` préservé) ; `reference_strength` fourni sans référence → ignoré, non transmis.
- `test_comfyui_engine.py` (adaptés + nouveaux) : `generate_image(denoise=X)` transmet bien `X` à `build_img2img_workflow` ; comportement par défaut inchangé si omis ; test architectural existant (agnosticisme du contenu du graphe) toujours vert sans modification.
- `test_comfyui_workflows.py` : aucune modification attendue (couverture déjà complète depuis Mission 023).

Nombre exact de tests final à confirmer après implémentation (321 + N nouveaux), comme pour chaque mission précédente.

### Résultats réels

Recherche préalable exécutée avant tout lancement Qt : 8 mocks/fakes locaux à ancienne signature trouvés et adaptés (`test_generation_worker.py` : `fake_generate` ×1 ; `test_inference_page.py` : `generate_side_effect` ×4, `slow_generate` ×4), tous complétés avec `reference_strength=None`. 5 assertions `assert_called_once_with`/`assert_called_with` sur `.generate()` complétées avec `reference_strength=0.75` (`test_inference_page.py`). Aucun code de production modifié pour contourner un mock. Aucune `QMessageBox` réelle non mockée rencontrée, aucun blocage.

Suites ciblées, dans l'ordre : `test_comfyui_engine.py` → **48/48** (+2) ; `test_generation_manager.py` → **27/27** (+4) ; `test_generation_worker.py` → **10/10** (+3) ; `test_inference_page.py` → **59/59** (+11), aucun blocage. `test_comfyui_workflows.py` → **27/27**, inchangé, non modifié.

**Suite complète : 341/341** (321 précédents + 20 nets nouveaux).

## 11. Risques de régression

- **Dérive de signature de mock** (voir section 10) — risque déjà rencontré Mission 022, procédure de recherche préalable obligatoire reconduite.
- **Ordre de câblage Qt** : le slot de mise à jour du label de valeur doit être connecté seulement après la construction des deux widgets, pour éviter une exception lors de l'initialisation du slider.
- **Valeur par défaut historique** : garantie structurellement par le choix de ne transmettre `denoise=` que si `reference_strength` n'est pas `None` (section 4) — pas une simple discipline de test.
- **Fuite de vocabulaire ComfyUI vers l'UI** : à vérifier explicitement en revue de code — aucun `"denoise"` ne doit apparaître dans `inference_page.py`.
- **Régression txt2img/img2img** : couverte par les tests existants Missions 013/023, non modifiés.

## 12. Critères d'acceptation

- Suite de tests complète verte, nombre exact confirmé.
- `git diff --stat` confirmant exactement le périmètre de fichiers de la section 9.
- Comportement par défaut (utilisateur ne touchant pas au slider) strictement identique au comportement Mission 023.
- Comportement txt2img strictement inchangé.
- Slider visible mais désactivé sans référence ; actif avec référence ; réinitialisé (valeur + état) au retrait de la référence et au changement de workspace.
- Aucun terme `"denoise"` visible dans `InferencePage` (libellé UI générique "Force de transformation").
- Smoke test manuel réel réalisé et documenté (section 13).

### Résultats réels

Tous les critères ci-dessus sont satisfaits : 341/341 tests verts ; `git diff --stat` limité aux 8 fichiers de la section 9 (4 code + 4 tests), `comfyui_workflows.py` confirmé absent du diff ; comportement par défaut et txt2img strictement inchangés (voir section 10, tests dédiés) ; aucun `"denoise"` dans `inference_page.py` (confirmé par recherche textuelle et par test architectural dédié) ; smoke test manuel réel réalisé et PASS (voir ci-dessous).

## 13. Plan du smoke test manuel réel

Réalisé par l'architecte, guidé pas à pas, contre l'instance ComfyUI Desktop déjà validée (Missions 012/023).

1. **Test C — régression valeur par défaut** : reprise du couple référence/prompt cohérent de Mission 023 sans toucher au slider (`0.75`) → résultat attendu cohérent avec Mission 023 (référence et prompt tous deux observables).
2. **Test D — force basse** (slider ≈ `0.15`–`0.20`) : même couple → résultat attendu visuellement proche de la référence, peu influencé par le prompt.
3. **Test E — force haute** (slider ≈ `0.90`–`0.95`) : même couple → résultat attendu où le prompt domine nettement plus que dans le Test C.
4. **Test F — retrait puis reprise sans référence** : retirer la référence, lancer une génération → comportement txt2img strictement inchangé, slider désactivé et non pris en compte.
5. **Test G — reset UI** : sélectionner une référence, déplacer le slider, la retirer, la resélectionner → slider revenu à `0.75` par défaut (pas de persistance de la valeur précédente).

Direction attendue (`denoise` bas = proche de la référence, `denoise` haut = prompt plus libre) cohérente avec le docstring déjà existant de `DEFAULT_IMG2IMG_DENOISE` — à confirmer empiriquement, pas présentée comme garantie absolue avant le test réel.

### Résultats réels

Réalisé par l'architecte contre l'instance ComfyUI Desktop déjà validée (Missions 012/023), avec la même image de référence (voiture) et le même prompt que Mission 023 (`a futuristic sports car at night in a neon-lit city, cinematic realistic photography`), en ne faisant varier que le slider « Force de transformation » :

| Force | Fichier | Observation |
|---|---|---|
| `0.20` | `AIStudioToolkit_00018_.png` | Résultat très proche de la référence : cadrage frontal et géométrie générale fortement conservés, environnement encore proche de la référence, influence du prompt relativement faible. |
| `0.75` (défaut) | `AIStudioToolkit_00019_.png` | Transformation intermédiaire : voiture et composition frontale toujours clairement conservées, design et éclairage davantage réinterprétés, influence du prompt plus perceptible qu'à `0.20`. |
| `0.95` | `AIStudioToolkit_00020_.png` | Transformation très forte : changement important de composition (notamment vue latérale), environnement futuriste/lumineux beaucoup plus présent, le prompt devient nettement dominant par rapport à la référence. |

**Conclusion** : la progression `0.20 → 0.75 → 0.95` est clairement perceptible et cohérente avec la direction attendue (force basse = proche de la référence, force haute = prompt dominant). Le résultat à `0.75` reste cohérent avec le comportement observé en Mission 023 (régression confirmée). **Smoke test fonctionnel : PASS**, déclaré par l'architecte.

## 14. Confirmation — aucune fonctionnalité hors périmètre

Aucune modification de `comfyui_workflows.py` (le paramètre `denoise` y existe déjà, inchangé) ; aucune persistance ; aucun multi-référence, rôle, IP-Adapter, ControlNet, LoRA, sélection de checkpoint, exploitation de `comfyui_path`, tri de galerie, ni système multi-engine. Seul le câblage bout-en-bout d'une valeur déjà supportée par la couche la plus basse est ajouté.

### Résultats réels

Revue finale du diff confirmée : `git diff --stat` limité aux 8 fichiers de la section 9 (4 fichiers de code, 4 fichiers de test), `src/engines/workflows/` absent du diff, aucun terme hors périmètre (`comfyui_path`, `lora`, `ip-adapter`, `controlnet`, tri, persistance, `application_settings`, multi-engine, plugin) trouvé dans le diff de production au-delà d'un commentaire confirmant explicitement l'absence de persistance dans `project.json`. Aucune fonctionnalité hors périmètre introduite.

## Commit correspondant

À compléter après clôture Git réelle (non encore effectuée à ce stade — implémentation et smoke test validés, en attente de validation explicite de l'architecte avant commit).

## Tag / release correspondant

À compléter après clôture Git réelle (non encore effectuée à ce stade).

## État final

**Implémentation, tests automatisés (341/341) et smoke test manuel réel validés — PASS.** Le slider « Force de transformation » de `InferencePage` permet désormais à l'utilisateur de contrôler réellement l'équilibre référence/prompt du workflow img2img livré par Mission 023, confirmé par un smoke test réel démontrant une progression cohérente (`0.20` proche de la référence → `0.75` intermédiaire, cohérent avec Mission 023 → `0.95` prompt dominant). Comportement par défaut et txt2img strictement inchangés. Aucun terme ComfyUI natif (`denoise`) n'a fui vers `InferencePage`. **Clôture Git de Mission 024 non encore effectuée** — en attente de validation explicite de l'architecte avant commit.
