# Mission 056 — Typed Inference Reference Primitive

> **STATUT : MISSION ENTIÈREMENT CLOSE.** Contrat révisé validé par l'architecte, implémentation réalisée conformément au contrat, 6/6 tests ciblés nets nouveaux (`GenerationManagerTypedReferenceTest`), 956/956 tests automatisés verts, `git diff --check` propre, smoke test manuel réel du rendu Qt PASS (21/21 assertions) — y compris la preuve que le flux `pose_composition` reste strictement inchangé (un seul upload, résultat transmis tel quel) et que la distinction collection/capacité de génération est respectée (aucune génération simultanée multi-références tentée ni prétendue). Commit, tag et GitHub Release réels — voir sections 15-18 ci-dessous.

## 1. Contexte

Un audit dédié de l'architecture Inference a confirmé que la limitation à une seule référence est codée à **toutes** les couches : `InferencePage._reference_image_path` reste un scalaire (`inference_page.py:91`), `GenerationManager.generate()` rejette explicitement `len(reference_images) > 1` (`generation_manager.py:103-106`), `ComfyUIEngine.generate_image(reference_image: Optional[dict])` est structurellement singulier, et `build_img2img_workflow()` ne contient qu'un seul nœud `LoadImage`. L'architecture « 0..N références avec rôles » documentée dans `docs/PROJECT_CONTEXT.md` n'existe que dans des commentaires — zéro code.

L'architecte a validé l'orientation (Option B) — construire une **primitive typée**, sans intégrer aucun mécanisme moteur concret (IP-Adapter/ControlNet/InstantID/PuLID, chacun une mission future distincte) — avec une correction de positionnement obligatoire : cette mission établit une **représentation structurée et extensible**, migre le mécanisme mono-référence existant vers elle, mais **ne prétend jamais** livrer une génération simultanée multi-références. La capacité de génération réellement livrée reste strictement 0..1 référence actionnable.

## 2. Mini-audit / audit ciblé réalisé

**Placement de `Reference`** : ni `src/domain/` (jamais persistée, pas d'`id`, pas de `to_dict()`/`from_dict()`, aucune collection possédée par un Manager) ni un nouveau module. Précédent direct déjà établi dans ce dépôt : `CharacterContext` (`src/managers/prompt_assistant_manager.py:54-97`), `NamedTuple` transitoire colocalisé dans son unique Manager consommateur. `Reference` suit ce même précédent, dans `src/managers/generation_manager.py` — **validé par l'architecte**.

**Compatibilité de signature** : `test_reference_images_parameter_is_still_a_0_to_n_list_based_collection` (`test_generation_manager.py:220-227`) vérifie uniquement le nom du paramètre (`reference_images`) et son défaut (`None`) — jamais l'annotation de type. Le paramètre et son défaut restent donc **strictement inchangés** ; seule son annotation est élargie. Les appelants existants passant une chaîne continuent de fonctionner sans migration.

**Frontière ComfyUIEngine** : `ComfyUIEngine`/`comfyui_workflows.py` ne connaissent aujourd'hui aucune notion de rôle — ils reçoivent `reference_image: Optional[dict]` (singulier). Cette frontière reste strictement inchangée ; c'est `GenerationManager.generate()`, seul, qui interprète un rôle.

**Rôle unique réellement actionnable** : `build_img2img_workflow()` (LoadImage → VAEEncode → KSampler denoise<1) est le seul mécanisme réel existant. Il est retypé sous le rôle `pose_composition`, sans qu'aucun autre rôle ne soit codé en dur (ni constante, ni enum) tant qu'aucun mécanisme réel ne le consomme — évite une taxonomie morte, conformément à la correction de l'architecte.

**Aucune décision produit ou architecturale substantielle ne reste ouverte.**

## 3. Objectif

Établir la représentation structurée et extensible d'une référence d'Inference (`Reference(path, role)`) et migrer le mécanisme mono-référence existant vers cette représentation — **sans** livrer de génération simultanée multi-références, qui reste un besoin futur explicitement différé.

## 4. Distinction explicite — modèle de collection vs. capacité de génération livrée

- **Modèle de collection** : `reference_images` reste une collection ordonnée `List[Union[str, Reference]]`, conçue dès aujourd'hui pour pouvoir un jour recevoir 0..N références typées — aucune limite artificielle n'est imposée à la *forme* de la collection elle-même.
- **Capacité de génération réellement livrée en M056** : **0..1 référence actionnable**, uniquement avec le rôle `pose_composition`. Toute collection contenant plus d'un élément est rejetée explicitement — la représentation multi-références existe, la génération simultanée multi-références n'existe pas encore. Ce document ne présente à aucun endroit M056 comme permettant plusieurs références simultanées dans une génération réelle.

## 5. Structure `Reference`

```python
class Reference(NamedTuple):
    path: str
    role: str
```

Strictement minimale — **aucun** champ `strength` par rôle, poids, masque, modèle ControlNet, configuration IP-Adapter, provider, ou paramètre moteur n'est ajouté maintenant. Ces champs appartiendront aux futurs adaptateurs, uniquement si un besoin réel apparaît.

## 6. Rôles

**Une seule constante de rôle est créée** : `REFERENCE_ROLE_POSE_COMPOSITION = "pose_composition"` — le seul rôle réellement actionnable, représentant le comportement img2img/référence déjà existant.

Les concepts futurs (identité, tenue, décor/environnement, style, pose/composition plus spécialisée) sont **documentés en prose** (docstring de `Reference`/`generate()`) comme direction future — **aucune constante, aucun enum, aucune entrée de taxonomie n'est créée pour eux** tant qu'aucun mécanisme réel ne les consomme. Un rôle qui n'est pas `pose_composition` (y compris un futur rôle nommé qui n'existe pas encore comme constante) est rejeté par comparaison directe à `REFERENCE_ROLE_POSE_COMPOSITION`, pas par recherche dans un ensemble de rôles "supportés" — il n'y a qu'un seul rôle supporté, pas un ensemble.

## 7. Contrat fonctionnel — réellement implémenté

**`src/managers/generation_manager.py`** (additif) :
- `REFERENCE_ROLE_POSE_COMPOSITION = "pose_composition"` — constante unique.
- `class Reference(NamedTuple): path: str; role: str`.
- `generate()` : signature inchangée (`reference_images: Optional[List[str]] = None` → annotation élargie `Optional[List[Union[str, Reference]]] = None`, nom et défaut identiques).
- **Règle de génération, stricte et explicite** :
  - Aucune référence → chemin `txt2img` actuel, strictement inchangé.
  - Une référence, rôle `pose_composition` (chaîne legacy normalisée en interne vers `Reference(path, role="pose_composition")`, ou `Reference` explicite avec ce rôle) → chemin `img2img` actuel, comportement strictement inchangé — un seul appel `upload_image()`, résultat transmis à `generate_image()` exactement comme aujourd'hui.
  - Une référence, rôle différent de `pose_composition` → `GenerationError` explicite nommant le rôle reçu, **aucun** upload tenté.
  - Plusieurs références (quel que soit leur rôle) → `GenerationError` explicite indiquant que la représentation multi-références existe mais que la génération simultanée multi-références n'est pas encore supportée — **aucun** upload tenté, **aucun** mélange arbitraire, **aucun** choix implicite de « la première » référence.
  - Aucun fallback silencieux à aucune étape.

**`src/ui/pages/inference_page.py`** (minimal) :
- `_start_generation()` (ligne 301) construit désormais explicitement `[Reference(self._reference_image_path, REFERENCE_ROLE_POSE_COMPOSITION)] if self._reference_image_path else []` — la primitive typée est réellement utilisée en production dès cette mission, pas seulement acceptée en façade.
- Affichage du rôle dans `reference_label` : discret, formulation naturelle (ex. `"<fichier> — Pose / composition"`), jamais le terme technique brut `pose_composition` exposé à l'utilisateur. Si cet affichage n'apporte pas assez de valeur au moment de l'implémentation, l'UI actuelle (nom de fichier seul) peut être conservée sans changement — l'observabilité principale de cette mission est de toute façon démontrée par les tests et le smoke test, pas uniquement par ce libellé.

**`src/engines/comfyui_engine.py`** : **aucun changement**.
**`src/engines/workflows/comfyui_workflows.py`** : **aucun changement** (aucune modification n'est strictement indispensable — le rôle `pose_composition` retype un mécanisme déjà entièrement fonctionnel, sans toucher au graphe lui-même).
**Domain/EventBus/persistance** : **aucun changement**.
**Aucune dépendance nouvelle** (IP-Adapter/ControlNet/InstantID/PuLID ou autre).

## 8. Comportement explicitement différé (hors périmètre)

- **Génération simultanée de plusieurs références** — la collection peut structurellement contenir N éléments, mais `generate()` la rejette dès que sa longueur dépasse 1, avec un message explicite indiquant que ce n'est pas encore supporté (pas une simple limite technique déguisée).
- Toute intégration IP-Adapter/ControlNet/InstantID/PuLID — missions futures distinctes, une par mécanisme.
- Toute constante/enum pour les rôles futurs (identité, tenue, décor/environnement, style) — documentés en prose uniquement, aucun code créé pour eux.
- Tout nouveau widget de sélection multi-références dans `InferencePage` — la sélection reste 0..1 via le bouton existant.
- Tout champ `strength` par rôle, poids, masque, configuration moteur sur `Reference` — appartiendra aux futurs adaptateurs si un besoin réel apparaît.
- **« Dataset de références → Inference »** — reste non résolu après M056. Cette mission prépare une fondation nécessaire mais ne permet pas d'envoyer plusieurs images d'un Dataset vers une génération. Les étapes suivantes (premier adaptateur moteur supportant réellement un rôle supplémentaire ; vraie consommation simultanée de plusieurs références ; puis seulement l'intégration pratique Dataset → Inference) devront chacune faire l'objet d'un audit séparé.
- Toute modification de `ComfyUIEngine`/`comfyui_workflows.py` au-delà de zéro changement.

## 9. Fichiers — réellement modifiés

Production (2) :
- `src/managers/generation_manager.py` (constante `REFERENCE_ROLE_POSE_COMPOSITION`, `Reference(NamedTuple)`, `generate()` étendu — 98 lignes de diff)
- `src/ui/pages/inference_page.py` (construction explicite d'un `Reference` en `_start_generation()`, libellé `reference_label` naturel — 15 lignes de diff)

Tests (2, aucun nouveau fichier) :
- `tests/integration/test_generation_manager.py` (nouvelle classe `GenerationManagerTypedReferenceTest`, 6 tests — 86 lignes de diff)
- `tests/integration/test_inference_page.py` (4 assertions `reference_images=[...]` migrées vers `Reference(...)`, 2 assertions de libellé mises à jour — 18 lignes de diff)

## 10. Stratégie de tests — réellement mise en œuvre

`GenerationManagerTypedReferenceTest` (nouvelle classe, `test_generation_manager.py`, 6 tests) :
- `test_explicit_pose_composition_reference_matches_legacy_string_behavior` — `Reference(path, "pose_composition")` explicite produit exactement les mêmes appels `upload_image()`/`generate_image()` qu'une chaîne legacy.
- `test_unsupported_role_raises_before_any_upload` — rôle ≠ `pose_composition` → `GenerationError`, `upload_image()` jamais appelé.
- `test_unsupported_role_does_not_set_busy` — même scénario, `busy` reste `False` après le rejet.
- `test_two_typed_references_raise_before_any_upload_regardless_of_role` — deux `Reference` (rôles mêlés) → rejet avant tout upload, message distinct du cas "rôle non supporté".
- `test_reference_role_constant_value` — sanity check `REFERENCE_ROLE_POSE_COMPOSITION == "pose_composition"`.
- `test_reference_is_a_minimal_namedtuple_of_path_and_role` — `Reference._fields == ("path", "role")`, aucun champ supplémentaire.

`test_inference_page.py` (mise à jour de 4 assertions existantes + 2 assertions de libellé, aucun nouveau test) :
- `test_generate_with_reference_sends_it_as_a_single_element_list`, `test_changing_selection_after_launch_does_not_affect_the_in_flight_snapshot`, `test_generate_with_default_strength_forwards_0_75`, `test_generate_with_custom_strength_forwards_converted_value` : `reference_images=[reference_path]` → `reference_images=[Reference(reference_path, REFERENCE_ROLE_POSE_COMPOSITION)]` — preuve directe qu'`InferencePage` construit désormais réellement un `Reference`.
- `test_selecting_a_reference_updates_state_label_and_remove_button`/`test_selecting_a_new_reference_replaces_the_previous_one` : libellé mis à jour (`"portrait.png — Pose / composition"`).

**Non-régression explicite confirmée** : tous les tests `txt2img`/`img2img` existants restent verts — seule la forme des 4 assertions `reference_images` et des 2 assertions de libellé a été mise à jour, jamais leur résultat fonctionnel. Signature publique `reference_images` et son défaut `None` conservés — `test_reference_images_parameter_is_still_a_0_to_n_list_based_collection` reste vert **sans aucune modification**.

**33/33** sur `test_generation_manager.py` (27 précédents + 6 nets nouveaux). **78/78** sur `test_inference_page.py`. **956/956 tests verts au total** (950 précédents + 6 nets nouveaux).

## 11. Smoke test manuel — réalisé, PASS

Réalisé moi-même (widgets Qt réels — `InferencePage` réel, `GenerationManager` réel, `ComfyUIEngine` mocké ; mission structurelle, aucun changement de ce qui est réellement envoyé à ComfyUI pour le cas `pose_composition`), script exclusivement dans le scratchpad de session, confirmé absent du dépôt (`git status --porcelain --ignored`).

Points observés réellement, tous conformes (21/21 assertions) :
- Génération réelle sans référence → `generate_image()` appelé avec `reference_image=None`, `upload_image()` jamais appelé → Accept réel persiste l'image dans `Workspace.images`.
- Sélection réelle d'une référence via le vrai `QFileDialog` → `reference_label` affiche `"portrait.png — Pose / composition"` (formulation naturelle, jamais le terme technique `pose_composition` brut).
- Génération réelle avec la référence sélectionnée → `upload_image()` appelé **exactement une fois** avec le chemin sélectionné, `generate_image()` reçoit le résultat d'upload **inchangé** (`reference_image=upload_result`) plus `denoise=0.75` — comportement `img2img` byte-for-byte identique à avant cette mission.
- Regenerate réel : ancien fichier pending supprimé, nouveau cycle réel démarré, référence réuploadée une seule fois.
- Reject réel : fichier pending supprimé, aucune persistance, aucune régression du cycle Preview/Accept/Reject/Regenerate.
- Appel contrôlé avec un rôle non supporté (`Reference(path, "identity")`) → `GenerationError("Reference role 'identity' has no generation mechanism yet (only 'pose_composition' is supported)")`, **aucun** `upload_image()` ni `generate_image()` appelé.
- **Aucun smoke test multi-références simultané tenté** — conforme à l'instruction explicite de ne pas faire croire à une capacité que M056 ne livre pas.

**Verdict : PASS.** Aucun écart constaté par rapport au contrat des sections 4 et 7.

## 12. Risques

- **Risque de sur-promesse** : écarté par construction — le contrat distingue explicitement (section 4) le modèle de collection de la capacité de génération réellement livrée, et le message d'erreur multi-références le rappelle explicitement à l'exécution.
- **Risque de taxonomie morte** : écarté — une seule constante de rôle créée, les rôles futurs restent en prose, aucun code mort.
- **Risque de sur-portée** : écarté — `ComfyUIEngine`/`comfyui_workflows.py`/Domain/EventBus non touchés.
- **Risque de casser `InferencePage`/`GenerationManager` existants** : le comportement de génération pour les cas 0 et 1 référence `pose_composition` reste strictement identique ; seules les assertions de test comparant la forme exacte de `reference_images` nécessitent une mise à jour littérale.

## 13. Pourquoi maintenant

Cette mission referme l'écart entre l'architecture documentée et le code réel pour la seule partie qui peut l'être sans engager l'application dans une dépendance à des nœuds ComfyUI personnalisés (IP-Adapter/ControlNet) — un choix qui reste à arbitrer mission par mission. Elle a un bénéfice architectural direct et immédiat pour toute future mission d'adaptateur moteur, qui n'aura plus qu'à ajouter son propre rôle et son propre branchement dans `comfyui_workflows.py`, sans retoucher `InferencePage`/`GenerationWorker`/la forme de `reference_images`.

## État d'avancement

- Audit du dépôt (candidats Mission 056) : **réalisé**.
- Orientation architecturale (Option B, périmètre restreint) : **validée par l'architecte**.
- Audit ciblé de faisabilité : **réalisé**.
- Correction de positionnement (0..1 actionnable, pas de taxonomie morte, distinction collection/capacité) : **intégrée**.
- Spécification (contrat révisé) : **validée par l'architecte**.
- Implémentation : **réalisée**, conforme à la spécification validée, aucune divergence de périmètre.
- Tests automatisés : **exécutés, verts** — 6/6 ciblés (`GenerationManagerTypedReferenceTest`), 956/956 (suite complète).
- `git diff --check` : **propre**.
- Smoke test manuel réel obligatoire : **réalisé, PASS** (21/21 assertions).
- Clôture Git (commit/tag/Release) : **entièrement effectuée**.

## 15. Fichiers concernés

Production (2) : `src/managers/generation_manager.py`, `src/ui/pages/inference_page.py`.
Tests (2, aucun nouveau fichier) : `tests/integration/test_generation_manager.py`, `tests/integration/test_inference_page.py`.
Documentation (1, nouveau fichier) : `docs/missions/MISSION_056.md`.

## 16. Commit correspondant

`f095b74c07b63ba5d5293cef8684e4acb0400f9c` — `feat: introduce typed Inference reference primitive`.

## 17. Tag-release correspondant

`v0.2-mission056` (annoté, message `Mission 056 - Typed Inference Reference Primitive`), ciblant exactement `f095b74c07b63ba5d5293cef8684e4acb0400f9c`.

## 18. État final

GitHub Release `v0.2-mission056` publiée. Mission entièrement close.
