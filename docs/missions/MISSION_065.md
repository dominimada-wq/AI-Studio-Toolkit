# Mission 065 — Block Prompt Assistant Close While Generation Is Running

> **STATUT : MISSION ENTIÈREMENT CLOSE.** 7 tests ciblés nets nouveaux (`tests/integration/test_prompt_assistant_dialog.py`), 38/38 sur le fichier complet du dialogue, suite complète 3/3 exécutions propres à 1096/1096, smoke test Qt réel exécuté et **PASS** (chemins succès et échec). Commit fonctionnel `17c44dceeecf0d277038edc0bea2118a740dd7ba`, tag annoté `v0.2-mission065`, GitHub Release publiée. Voir section 11 pour l'état de clôture Git final.

## 1. Contexte

L'audit post-Mission 064 avait identifié le candidat B2, laissé en suspens dans l'attente d'un arbitrage produit : pendant une génération de `PromptAssistantDialog`, le bouton Annuler est désactivé, mais `Escape` et la fermeture native de la fenêtre contournent ce garde-fou (`QDialog.reject()` n'est jamais surchargé), abandonnant le worker/`QThread` en arrière-plan et pouvant faire apparaître un `QMessageBox.critical()` tardif sur un dialogue que l'utilisateur croit fermé. L'architecte a tranché : **Option A — interdire la fermeture pendant une génération**.

## 2. Objectif

Rendre le comportement de fermeture cohérent avec l'état déjà exprimé par l'interface (bouton Annuler désactivé) : tant qu'une génération est en cours, `Escape`, la croix native et toute autre tentative de fermeture utilisateur doivent être ignorées silencieusement — sans nouvelle popup — le dialogue reste ouvert jusqu'à la fin réelle du traitement (succès ou échec), après quoi les mécanismes normaux de fermeture sont restaurés.

## 3. Contrat fonctionnel implémenté

**Vérification préalable des chemins Qt réels** (avant toute modification, script de sonde exécuté dans le scratchpad) : `dialog.close()` déclenche `closeEvent()` **et** `reject()` (Qt le confirme empiriquement — `QDialog` route la fermeture native via `reject()`) ; `Escape` appelle `reject()` directement, sans passer par `closeEvent()`. **`reject()` est donc l'unique point de passage commun** à Escape, à la fermeture native et au bouton Annuler (`cancel_button.clicked.connect(self.reject)`) — surcharger uniquement `reject()` couvre les trois chemins sans dupliquer la logique dans `closeEvent()`/`keyPressEvent()`.

**Implémentation** (`src/ui/dialogs/prompt_assistant_dialog.py`) — une seule méthode ajoutée :
```python
def reject(self):
    if not self.cancel_button.isEnabled():
        return
    super().reject()
```
**Source de vérité réutilisée, aucun nouvel état introduit** : `cancel_button.isEnabled()` est exactement l'état déjà piloté par `_set_controls_enabled()` (Mission 031) — désactivé au lancement d'une génération, réactivé de façon synchrone par `_on_assist_finished()` et `_on_assist_failed()`. Aucune dépendance à `self._thread`, dont la remise à `None` par `_cleanup_thread()` est asynchrone et retardée par rapport à la fin réelle du traitement côté UI — utiliser `_thread` aurait laissé une fenêtre où le bouton semble réactivé mais la fermeture resterait bloquée.

**UX** : aucune nouvelle popup — une tentative de fermeture pendant la génération est simplement ignorée, exactement comme demandé (le bouton Annuler désactivé reste la seule indication visuelle).

**Aucun mécanisme d'annulation du worker introduit** — le `QThread`/`PromptAssistantWorker` continuent leur cycle normal, inchangés ; seule la fermeture du dialogue est bloquée pendant ce temps.

**Fichier modifié** (Presentation uniquement) : `src/ui/dialogs/prompt_assistant_dialog.py`. Aucune modification de `InferencePage`, `PromptsPage`, `Domain`, `Managers`, `EventBus`, ou de tout autre dialogue.

## 4. Hors périmètre (explicitement différé)

- Tout mécanisme d'annulation réelle du worker/appel IA — non traité ici.
- Le segfault Qt/PySide6 (candidat C) — voir section 9, non traité, hypothèse de cleanup `QThread` déjà réfutée expérimentalement lors de l'audit post-Mission 064.
- Toute modification de la politique d'affichage des erreurs du dialogue en usage normal (hors busy) — strictement inchangée.

## 5. Risques

- **Risque de régression fonctionnelle** : très faible — un seul point de garde ajouté, réutilisant un état déjà existant et déjà testé ; comportement hors génération strictement inchangé (vérifié par tests dédiés).
- **Risque d'incohérence état busy/UI** : écarté par le choix de `cancel_button.isEnabled()` plutôt que `self._thread` comme source de vérité — les deux mécanismes (désactivation des contrôles et garde de fermeture) restent synchrones par construction, pilotés par le même appel `_set_controls_enabled()`.

## 6. Pourquoi maintenant

Décision produit tranchée par l'architecte (Option A) à l'issue de l'audit post-Mission 064 — seul point qui bloquait la spécification de ce candidat, identifié dès l'audit post-Mission 063.

## 7. Tests automatisés ajoutés

**7 tests nets nouveaux**, `tests/integration/test_prompt_assistant_dialog.py` :

- Nouvelle classe `PromptAssistantDialogCloseGuardTest` (5 tests, sans `QThread` réel — `cancel_button.setEnabled(False)` simule directement l'état busy, la même source de vérité que lit `reject()`, avec de vrais événements Qt pour Escape/fermeture) : `test_escape_closes_dialog_when_idle`, `test_native_close_closes_dialog_when_idle`, `test_escape_does_not_close_dialog_while_busy`, `test_native_close_does_not_close_dialog_while_busy`, `test_dialog_becomes_closable_again_once_busy_state_ends`.
- 2 tests ajoutés à `PromptAssistantDialogGenerateTest` (cycle `QThread` réel réutilisé, pas une nouvelle classe threadée) : `test_escape_and_close_are_ignored_during_a_real_generation_and_the_worker_completes_normally` (Escape + close tentés pendant une génération réelle, dialogue reste ouvert, le worker termine normalement, le résultat atterrit correctement, Escape referme ensuite) et `test_dialog_becomes_closable_again_after_a_real_generation_fails` (même garde côté échec, `QMessageBox.critical` mocké, fermeture de nouveau possible après l'erreur).

Comportement observable testé (`isVisible()` via de vrais `dialog.show()`/`QTest.keyClick`/`dialog.close()`), jamais l'existence de l'override ou d'un booléen interne. Le test préexistant `test_result_text_stays_none_if_dialog_is_cancelled` couvre déjà le comportement normal du bouton Annuler hors génération — non dupliqué.

## 8. Vérifications finales — réellement exécutées

**Tests ciblés** — **7/7 PASS**. **Fichier complet du dialogue** — **38/38 PASS** (31 préexistants + 7 nouveaux). Non-régression des consommateurs (`InferencePage`, `PromptsPage`) — **159/159 PASS** (`test_inference_page.py` + `test_prompt_roundtrip.py`).

`git diff --check` : propre, aucun avertissement.

**Périmètre du diff** : exactement 2 fichiers — `src/ui/dialogs/prompt_assistant_dialog.py` (production, +15 lignes, une seule méthode ajoutée) et `tests/integration/test_prompt_assistant_dialog.py` (tests, +119 lignes). Aucun fichier Domain/Manager/Infrastructure/EventBus/`InferencePage`/autre dialogue touché.

## 9. Suite complète — segfault Qt/PySide6, résultat de cette mission

**Total attendu : 1096 tests** (1089 après Mission 064 + 7 nets nouveaux). **3 exécutions complètes consécutives `unittest discover`, toutes propres à 1096/1096, aucun crash.** Ce résultat n'est **pas** attribué à un correctif du segfault — aucune modification liée aux `QThread`/tests n'a été apportée dans cette mission, conformément à l'instruction explicite de ne pas réintroduire l'hypothèse déjà réfutée lors de l'audit post-Mission 064 (attente explicite de fin de thread + reproduction du mécanisme `quit()+wait()` d'`InferencePage.shutdown()`, toutes deux sans effet sur le crash à l'époque). Ce résultat est cohérent avec la nature déjà documentée de l'aléa (intermittent, sensibilisé par le volume cumulé de la suite, non isolé à une cause précise) — 3 runs propres ne prouvent ni sa disparition ni sa correction, seulement qu'il ne s'est pas manifesté pendant ces vérifications. Aucun échec fonctionnel imputable à Mission 065 n'a été observé, dans aucune des trois exécutions.

## 10. Smoke test Qt réel — exécuté par Claude, écran non mocké

Dialogue réel, `QThread`/`PromptAssistantWorker` réels (`PromptAssistantManager` mocké — aucune instance Ollama réelle nécessaire, convention déjà établie par tous les tests automatisés de ce dialogue), vrais événements Qt (`QTest.keyClick(Key_Escape)`, `dialog.close()`) — jamais un appel direct à `.reject()`.

1. **Hors génération** : `Escape` ferme le dialogue ; fermeture native (`close()`) ferme le dialogue.
2. **Pendant une génération réelle** : bouton Annuler désactivé ; `Escape` tenté → dialogue toujours ouvert ; fermeture native tentée → dialogue toujours ouvert.
3. **Fin de génération (succès)** : `use_result_button` réactivé, résultat correctement affiché, bouton Annuler réactivé ; `Escape` referme de nouveau le dialogue normalement.
4. **Chemin d'échec** (vérifié également, sans modification hors périmètre — `PromptAssistantManager.assist()` lève `PromptAssistantError`, `QMessageBox.critical` mocké) : bouton Annuler désactivé pendant le traitement, `Escape` ignoré pendant ce temps, `QMessageBox.critical` déclenché normalement à l'échec, bouton Annuler réactivé, `Escape` referme de nouveau le dialogue.

**Verdict : PASS**, 14/14 assertions vérifiées (voir sortie complète de `m065_smoke.py`, script de vérification exécuté depuis le scratchpad de session, jamais commité).

## État d'avancement

- Décision produit (Option A) : **tranchée par l'architecte**.
- Vérification préalable des chemins Qt réels (sonde dédiée, sans modification) : **réalisée**.
- Implémentation : **réalisée, conforme au contrat, un seul point de garde dans `reject()`**.
- Tests automatisés : **exécutés, verts — 7/7 ciblés, 38/38 fichier complet, 159/159 non-régression consommateurs**.
- Suite complète : **3/3 exécutions propres à 1096/1096, aucun échec imputable à Mission 065**.
- `git diff --check` : **propre**.
- Contrôle de périmètre du diff : **conforme (2 fichiers exactement)**.
- Smoke test Qt réel : **réalisé, PASS, succès et échec couverts** (section 10).
- Clôture Git (commit/tag/Release) : **terminée** (voir section 11).

## 11. Clôture Git et publication — état final réel

- **Commit fonctionnel** : `17c44dceeecf0d277038edc0bea2118a740dd7ba` (`feat: block PromptAssistantDialog close while a generation is running`), 3 fichiers modifiés (`src/ui/dialogs/prompt_assistant_dialog.py`, `tests/integration/test_prompt_assistant_dialog.py`, `docs/missions/MISSION_065.md`), 222 insertions(+), 1 suppression(-).
- **Push** : `80888a4..17c44dc main -> main`. Vérifié après coup : `HEAD == origin/main == 17c44dceeecf0d277038edc0bea2118a740dd7ba`, divergence `0 0`.
- **Tag annoté** : `v0.2-mission065`, message « Mission 065 - Block Prompt Assistant Close While Generation Is Running », objet `30acd91c43bf9a18aa40b524b89479e03257890f`, peeled sur `17c44dceeecf0d277038edc0bea2118a740dd7ba` — vérifié identique en local et à distance (`git ls-remote --tags`).
- **GitHub Release `v0.2-mission065`** : publiée manuellement par l'architecte.
- **Régularisation documentaire post-Release** (ce commit) : mise à jour du bandeau de statut de ce document, de `docs/PROJECT_CONTEXT.md` et de `CHANGELOG.md` (nouvelle section `## v0.2-mission065`) pour refléter l'état Git/Release réel désormais clos. Le tag `v0.2-mission065` reste sur le commit fonctionnel `17c44dc` — non déplacé par ce commit de régularisation, purement documentaire.
- **Segfault Qt/PySide6** : ne s'est pas manifesté pendant les 3 exécutions complètes de validation de cette mission — observation de stabilité sur ces runs, non une preuve de correction. Cause racine toujours non isolée ; l'hypothèse simple de cleanup `QThread` reste expérimentalement réfutée (audit post-Mission 064). Aucune modification visant ce sujet n'a été apportée dans Mission 065.
