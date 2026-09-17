# Mission 133 — Harden the Qt Dialog-Guard Timing Assertion

> **MISSION CLÔTURÉE — commit, tag et Release publiés.** L'idiome dupliqué `assertLess(elapsed, 1.0)` (5 occurrences, 4 fichiers) est remplacé par un helper partagé unique (`assert_dialog_guard_intercepts_promptly()`) dans `tests/integration/_qt_dialog_safety_net.py`, avec un plafond de dysfonctionnement généreux et justifié (`_HANG_DETECTION_CEILING_SECONDS = 5.0`, contre 1.0 s), explicitement documenté comme **non garant d'une absence de hang total** — seulement d'une interception qui réussit mais devient anormalement lente. `_DialogGuard` reste strictement inchangé. **+2 tests nets** prouvant que ce plafond détecte réellement une dégradation bornée. Tests ciblés 342/342 verts (répartis sur les 4 fichiers concernés), répétitions ciblées 10/10 + 5/5 + 5/5 vertes, **deux suites complètes indépendantes à 2734/2734/0 échoué**, aucun des deux flakes historiques observé sur aucun des runs. Aucun fichier `src/` modifié. Aucun smoke requis. Commit fonctionnel `6694ab43ecee205a5c1dda36d33af8c17dd6e514`, tag `v0.2-mission133`, GitHub Release publiée manuellement (`gh` CLI indisponible).

## 1. Contexte

L'audit post-Mission 132 a identifié un flake reproductible et documenté sur cinq clôtures de mission consécutives (126→132, voir `docs/PROJECT_CONTEXT.md` section "Problèmes connus / dettes") : `AssertionError: 1.25 not less than 1.0`, toujours sur la même classe de test, jamais reproduit en isolation (1/1 ou 1/8 selon les runs), jamais attribué à une régression fonctionnelle réelle.

Le même idiome — chronométrer un round-trip complet « `QMessageBox` réel affiché → intercepté → `UnexpectedDialogError` levée » et exiger `elapsed < 1.0` seconde — est dupliqué **exactement 5 fois dans 4 fichiers**, vérifiés un par un à la ligne près pendant cette investigation (aucun n'est supposé) :

| # | Fichier | Ligne(s) | Test | Contexte du parent |
|---|---|---|---|---|
| 1 | [`test_qt_dialog_safety_net.py:35-49`](../../tests/integration/test_qt_dialog_safety_net.py#L35) | `test_unexpected_warning_dialog_is_caught_not_blocked` | `assertLess(elapsed, 1.0, "...")` (avec message) | `guard_against_unexpected_dialogs()` context manager, `QApplication` nue sans `MainWindow` |
| 2 | [`test_qt_dialog_safety_net.py:51-61`](../../tests/integration/test_qt_dialog_safety_net.py#L51) | `test_unexpected_critical_dialog_is_caught_not_blocked` | `assertLess(elapsed, 1.0)` (sans message) | idem, variante `.critical()` |
| 3 | [`test_main_window_new_project.py:961-983`](../../tests/integration/test_main_window_new_project.py#L961) | `test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure` | `assertLess(elapsed, 1.0)` | `start_dialog_guard()`/`stop_dialog_guard()` sur une vraie `MainWindow()` (poids Qt réel — fuite de widgets M097/M099 documentée) |
| 4 | [`test_main_window_rename_project.py:439-460`](../../tests/integration/test_main_window_rename_project.py#L439) | même nom de test | `assertLess(elapsed, 1.0)` | idem, contexte Rename |
| 5 | [`test_lora_roundtrip.py:5398-5423`](../../tests/integration/test_lora_roundtrip.py#L5398) | même nom de test | `assertLess(elapsed, 1.0)` | idem, sur `LoRAPage` réelle |

**Le flake documenté touche précisément l'occurrence #3.** Les occurrences #4 et #5 partagent l'exact même idiome fragile et le même contexte à charge Qt (vraie fenêtre) sans avoir (encore) été observées en échec — traitées ici par prévention, pas par preuve d'échec propre.

**Deux fichiers utilisent le guard sans porter cet idiome** — confirmés hors périmètre par lecture directe : [`test_inference_page.py:63`](../../tests/integration/test_inference_page.py#L63) et [`test_main_window_close_event.py:27`](../../tests/integration/test_main_window_close_event.py#L27) importent `start_dialog_guard`/`stop_dialog_guard` mais ne contiennent aucun `assertLess` sur un `elapsed` — non concernés par cette mission.

## 2. Fonctionnement exact du mécanisme (base de l'investigation)

Lu intégralement dans [`_qt_dialog_safety_net.py`](../../tests/integration/_qt_dialog_safety_net.py) :

1. `_DialogGuard.eventFilter()` intercepte tout `QEvent.Type.Show` sur une instance de `QMessageBox`, pour n'importe quel appelant (y compris les fonctions statiques natives `QMessageBox.warning()/.critical()`, qui ne passent jamais par un attribut Python patchable — c'est la raison d'être documentée de ce mécanisme depuis Mission 091).
2. La fermeture n'est **jamais synchrone** dans ce handler : elle est différée via `QTimer.singleShot(0, ...)`, car `QDialog.exec()` appelle `show()` **avant** de créer sa propre `QEventLoop` interne — fermer de façon synchrone dans l'`eventFilter` masquerait la boîte pendant que sa boucle d'événements (pas encore armée) démarre juste après, provoquant un hang invisible pire que le bug d'origine.
3. Ce `singleShot(0, ...)` n'est traité que lorsque la boucle d'événements interne de `exec()` tourne réellement — c'est-à-dire seulement une fois que l'appel bloquant `QMessageBox.warning(...)` a lui-même démarré sa boucle. Le round-trip complet (Show → filtre → planification → tick suivant → `_close_if_visible()` → `box.done()`/`hide()` → retour d'`exec()`) se déroule donc **entièrement à l'intérieur** de l'appel bloquant `QMessageBox.warning(...)`, dans le même thread, sans jamais rendre la main à l'appelant avant que la fermeture ait eu lieu.
4. `_DialogGuard.stop()` (appelé par `guard_against_unexpected_dialogs.__exit__()` ou directement par `stop_dialog_guard()`) lève `UnexpectedDialogError` seulement si `self.captured` est non vide — c'est-à-dire seulement après que la fermeture ci-dessus a effectivement eu lieu.

**Conséquence structurelle centrale, qui gouverne tout le design de cette mission** : parce que `QMessageBox.warning(...)` est un appel **bloquant** dans le thread du test, si le mécanisme d'interception (`eventFilter` + `singleShot`) échouait totalement (jamais appelé, jamais traité), l'appel ne rendrait **jamais** la main — le test resterait bloqué au niveau natif Qt/C++, avant même d'atteindre la ligne `elapsed = time.monotonic() - started`. **Aucune assertion Python placée après cet appel ne peut donc jamais détecter un échec total du mécanisme** — un tel échec se manifesterait uniquement comme un processus de test qui ne se termine jamais (visible en externe : timeout CI, terminal figé), exactement comme avant cette mission. Ce n'est pas une lacune introduite ici ; c'est une propriété déjà vraie de l'architecture actuelle, qu'aucun changement de seuil ne peut changer, et qu'il serait malhonnête de prétendre corriger.

Ce que l'assertion chronométrée peut réellement détecter, en revanche, c'est une **dégradation partielle** : le mécanisme fonctionne (la boîte finit par se fermer, `UnexpectedDialogError` finit par être levée) mais le round-trip est anormalement lent — un signal de dysfonctionnement réel, distinct d'un hang total.

## 3. Design retenu — trois niveaux distincts, jamais confondus

| Niveau | Ce qu'il garantit | Mécanisme | Où il vit |
|---|---|---|---|
| **Propriété fonctionnelle testée** | Un `QMessageBox` réel/non mocké est intercepté ; `UnexpectedDialogError` est produite, avec le bon titre/texte | `self.assertRaises(UnexpectedDialogError)` + `assertIn(titre, str(exception))` | Inchangé dans les 5 tests — déjà correct, jamais remis en cause par cette mission |
| **Mécanisme anti-hang** | Le round-trip ne bloque jamais indéfiniment dans l'écrasante majorité des cas réels | `QEvent.Show` `eventFilter` + `QTimer.singleShot(0, ...)` fermant sur le tick suivant de la boucle `exec()` déjà démarrée | `_DialogGuard` — code déjà existant, **non modifié** par cette mission (voir §2) |
| **Timeout de dernier recours (nouveau)** | Une dégradation partielle réelle (round-trip anormalement lent malgré une interception qui a fini par réussir) reste détectable, sans faire échouer le test à cause de la seule lenteur ponctuelle d'une machine/suite chargée | Un unique plafond généreux, documenté, partagé (`_HANG_DETECTION_CEILING_SECONDS = 5.0`), utilisé par un helper unique | Nouveau : `tests/integration/_qt_dialog_safety_net.py` |

**Pourquoi 5.0 secondes, pas un autre chiffre arbitraire :**

- La seule valeur observée en échec réel et documentée est `1.25 s` (Mission 127, jamais reproduite en isolation). Un plafond de `5.0 s` donne une marge de **4×** au-dessus de ce seul point de données réel — largement suffisant pour absorber la latence de planification/GC d'une suite complète chargée (2732 tests, fuite de widgets connue et acceptée M097/M099), sans viser un chiffre inventé.
- `5.0 s` reste **deux ordres de grandeur** en dessous de toute durée plausible où un humain remarquerait et cliquerait réellement une boîte de dialogue laissée ouverte (réalistement plusieurs secondes à plusieurs minutes en environnement CI sans surveillance) — le plafond conserve donc son pouvoir discriminant réel : distinguer « fermeture automatique en un tick » de « serait resté ouvert en attente d'un humain », qui est la propriété métier réellement visée par le message d'erreur historique (« it may have actually rendered/blocked instead of being intercepted »).
- `5.0 s` n'est **pas** un objectif de performance : le nom de la constante (`_HANG_DETECTION_CEILING_SECONDS`) et son message d'assertion l'explicitent — dépasser ce plafond n'est jamais présenté comme "trop lent", mais comme "signal de dysfonctionnement du filet de sécurité lui-même".
- Une seule constante partagée pour les 5 occurrences (pas de réglage par fichier) : aucune preuve ne justifie un plafond différent selon le contexte (QApplication nue vs vraie `MainWindow`/`LoRAPage`), et une valeur unique évite tout ajustement au cas par cas non justifié.

## 4. Helper partagé — élimine la duplication

Nouvelle fonction ajoutée à `_qt_dialog_safety_net.py`, aux côtés de `UnexpectedDialogError`/`guard_against_unexpected_dialogs`/`start_dialog_guard`/`stop_dialog_guard` déjà exportés :

```python
_HANG_DETECTION_CEILING_SECONDS = 5.0
# Last-resort dysfunction ceiling, not a performance budget — see
# module docstring section "Mission 133" for the full reasoning. The
# only documented real-world failure was 1.25s (Mission 127); this
# gives 4x margin over that single data point while staying two
# orders of magnitude below any duration a human would need to notice
# and click a dialog left open. Exceeding it signals a genuine
# degradation of the interception mechanism itself, never ordinary
# full-suite scheduling jitter.


def assert_dialog_guard_intercepts_promptly(testcase, trigger):
    """
    Runs `trigger()` (expected to cause a real QMessageBox to appear
    and the guard to raise UnexpectedDialogError, synchronously or via
    a subsequent stop_dialog_guard() call inside `trigger` itself) and
    asserts it completes within the last-resort dysfunction ceiling.

    Does NOT assert anti-hang itself — see module docstring: a total
    mechanism failure would block inside `trigger()` at the native Qt
    level, before this function's own timing code ever runs. This
    assertion only catches a partial degradation (interception
    eventually succeeds, but pathologically slowly).

    Returns the caught exception so the caller can assert on its
    message (title/text), keeping this helper single-purpose.
    """
    started = time.monotonic()
    with testcase.assertRaises(UnexpectedDialogError) as ctx:
        trigger()
    elapsed = time.monotonic() - started
    testcase.assertLess(
        elapsed,
        _HANG_DETECTION_CEILING_SECONDS,
        f"the guarded dialog round-trip took {elapsed:.3f}s, over the "
        f"{_HANG_DETECTION_CEILING_SECONDS}s last-resort dysfunction "
        "ceiling. This is not a performance budget — see "
        "_HANG_DETECTION_CEILING_SECONDS — it exists only to catch a "
        "genuinely degraded anti-hang mechanism; ordinary full-suite "
        "scheduling jitter should never reach it.",
    )
    return ctx.exception
```

`time` devient un import nouveau de `_qt_dialog_safety_net.py` (déjà présent dans les 5 fichiers appelants, aucun changement d'import côté appelants pour `time` lui-même).

**Portée volontairement étroite** : ce helper ne fait qu'une chose (chronométrer + `assertRaises` + plafond nommé) ; il ne devient pas un utilitaire Qt générique, ne touche pas à `_DialogGuard`, n'introduit aucune nouvelle capacité d'attente/poll. Conforme à la contrainte explicite de ne pas produire d'abstraction Qt générale inutile.

### Utilisation dans les 5 sites

**Occurrence #1** (`test_qt_dialog_safety_net.py`, contexte manager) :
```python
def test_unexpected_warning_dialog_is_caught_not_blocked(self):
    def trigger():
        with guard_against_unexpected_dialogs():
            QMessageBox.warning(None, "Test Title", "Test Text")

    ctx_exception = assert_dialog_guard_intercepts_promptly(self, trigger)
    self.assertIn("Test Title", str(ctx_exception))
    self.assertIn("Test Text", str(ctx_exception))
```

**Occurrences #2-5** (guard déjà armé en `setUp()`, `stop_dialog_guard()` explicite) — mirroir exact du pattern existant, `trigger` encapsule l'appel bloquant *et* l'arrêt du guard (reproduit fidèlement ce que mesurait déjà `elapsed` avant cette mission — aucun changement de ce qui est chronométré, seulement de la façon dont c'est vérifié) :
```python
def test_dialog_guard_converts_a_genuinely_unexpected_dialog_into_a_clean_failure(self):
    def trigger():
        QMessageBox.warning(self.window, "Mission 094 Test Title", "Mission 094 Test Text")
        stop_dialog_guard(self.dialog_guard)

    ctx_exception = assert_dialog_guard_intercepts_promptly(self, trigger)
    self.assertIn("Mission 094 Test Title", str(ctx_exception))
```
(`self.window` devient `self.lora_page` dans `test_lora_roundtrip.py`, message adapté "Mission 095" — aucun autre changement de contrat.)

## 5. Nouveau test — preuve positive que le plafond détecte réellement une dégradation

Répond explicitement au point 5 exigé par l'architecte : « un vrai dysfonctionnement du filet de sécurité reste détectable ». Ajouté dans `test_qt_dialog_safety_net.py` (fichier déjà dédié à la preuve du contrat du guard) :

- **Test positif de non-régression du plafond** : monkeypatch de `QTimer.singleShot` (ou du point d'entrée équivalent le plus proche dans `_DialogGuard`) pour introduire un délai **déterministe et borné** légèrement supérieur au plafond (ex. `_HANG_DETECTION_CEILING_SECONDS + 0.5`) avant de fermer la boîte, puis vérifie que `assert_dialog_guard_intercepts_promptly` échoue bien avec l'`AssertionError` attendue — preuve que le plafond n'est pas devenu vide de sens (« si tout est toujours vert quel que soit le délai, le plafond ne teste plus rien »).
- Ce délai simulé reste **fini et borné** (jamais un vrai hang infini) : aucun risque de bloquer réellement la suite, contrairement à une tentative de casser le mécanisme d'interception lui-même (hors périmètre, voir §7).
- Un second test, symétrique, confirme qu'un délai simulé **sous** le plafond (ex. `_HANG_DETECTION_CEILING_SECONDS - 4.5`, soit 0.5 s) continue de passer — non-régression du chemin nominal.

Ces deux tests valident le helper lui-même, indépendamment des 5 sites d'usage — ils ne remplacent aucun test existant.

## 6. Fichiers autorisés (vérifiés à l'exécution, chemins exacts confirmés)

- `tests/integration/_qt_dialog_safety_net.py` — nouvelle constante + nouveau helper, export ajouté ; aucune modification de `_DialogGuard`.
- `tests/integration/test_qt_dialog_safety_net.py` — 2 tests migrés vers le helper, 2 nouveaux tests (§5).
- `tests/integration/test_main_window_new_project.py` — 1 test migré.
- `tests/integration/test_main_window_rename_project.py` — 1 test migré.
- `tests/integration/test_lora_roundtrip.py` — 1 test migré.
- `docs/missions/MISSION_133.md` (ce document, mis à jour avec les résultats réels après implémentation).

**Aucun fichier `src/` n'est modifié.** `test_inference_page.py` et `test_main_window_close_event.py` ne sont pas concernés (§1).

## 7. Exclusions explicites

- **Dette historique de fuite de widgets Qt (M097/M099)** — non rouverte, aucune tentative de correction, aucune nouvelle mesure/instrumentation ajoutée. C'est une cause plausible de la lenteur ponctuelle observée, jamais un problème que cette mission cherche à résoudre — le fix ici absorbe la marge, il ne traite pas la cause.
- **`ForgeLifecycleManagerRealProcessTest`** — flake distinct, cause différente (subprocess réel), jamais fusionné avec celui-ci.
- **Lifecycle Forge** — hors périmètre.
- **Code de production des dialogs** (`src/ui/*.py` appelant `QMessageBox.critical/warning/...`) — inchangé.
- **Training/OneTrainer, Central LoRA Library** — sans lien, non touchés.
- **`_DialogGuard` lui-même** (`eventFilter`, `_close_if_visible`, `start`/`stop`) — mécanisme anti-hang déjà correct par construction (§2), non modifié. Le monkeypatch du §5 agit uniquement depuis les tests, jamais sur le fichier de production du guard.
- **Aucune tentative de provoquer un vrai hang infini** pour "prouver" l'anti-hang — voir §2 : structurellement indétectable par une assertion post-hoc, et dangereux à simuler dans une suite automatisée.
- **Aucune nouvelle abstraction Qt générale** — le helper reste strictement scopé à cette seule responsabilité (chronométrage + assertRaises + plafond nommé), pas un framework de test Qt.

## 8. Tests prévus

1. **Non-régression fonctionnelle des 5 sites migrés** : chacun continue de lever `UnexpectedDialogError` avec le bon titre/texte (`assertIn` inchangé).
2. **Le helper échoue correctement en cas de dégradation simulée bornée** (§5, nouveau test positif du plafond).
3. **Le helper n'échoue pas sur un délai simulé sous le plafond** (§5, non-régression du chemin nominal).
4. **Suppression effective de la duplication** : vérifier par lecture (`grep assertLess`) qu'aucune occurrence brute de `assertLess(elapsed, 1.0)` ne subsiste dans les 4 fichiers de tests concernés.
5. **Suite complète** (`tests/integration/test_qt_dialog_safety_net.py`, `test_main_window_new_project.py`, `test_main_window_rename_project.py`, `test_lora_roundtrip.py`) verte.
6. **Full suite** : nombre exact de tests confirmé (baseline 2732 + 2 nouveaux tests de §5 = 2734 attendus), aucune régression.

## 9. Stratégie de répétition du flake — preuve supérieure à un seul passage vert

Le défaut étant intermittent (jamais reproduit en isolation dans l'historique des missions 127-132), un seul passage vert après migration ne suffit pas à démontrer la robustesse du nouveau plafond. Stratégie retenue, **volontairement bornée pour ne pas devenir un benchmark de performance ni une boucle de stress excessive** :

- **Répétitions ciblées, en isolation** : ré-exécuter `test_main_window_new_project.py` (le seul fichier avec un échec réellement documenté) **10 fois consécutives** en isolation pendant l'implémentation, comme preuve empirique ponctuelle — pas ajoutée en dur dans la suite automatisée. Même chose pour `test_main_window_rename_project.py` et `test_lora_roundtrip.py` (5 fois chacun, prévention, pas de preuve d'échec antérieur).
- **Inclusion dans au moins 2 exécutions complètes de la suite** (2734 tests), le contexte réel où le flake a toujours été observé — pas seulement en isolation.
- **Aucune répétition n'est ajoutée de façon permanente à l'intérieur des tests eux-mêmes** (pas de `for _ in range(N)` dans le corps d'un test de la suite) : cela ralentirait chaque exécution future de la suite complète pour un bénéfice ponctuel de validation, contraire à l'esprit de la demande.
- Le rapport d'implémentation doit indiquer le nombre exact de répétitions réellement effectuées et leur résultat (vert/rouge à chaque itération), pas une formulation vague.

## 10. Smoke

**Aucun smoke utilisateur ou moteur requis ni prévu.** Mission strictement confinée à l'infrastructure de tests Qt (`tests/integration/`) ; aucun comportement applicatif (`src/`) n'est modifié.

## 11. Baseline

2732 tests collectés à la clôture de Mission 132 (359/359 ciblés M132 verts, full suite unique 2732/2732/0). Cette mission ajoute exactement 2 tests nouveaux (§5) sans en retirer aucun — 2734 attendus après implémentation. Formulation stricte à conserver (jamais "X/X" sans le nombre exact, jamais "flake résolu" sans nuance — voir §12).

## 12. Critères d'acceptation

- [x] Les 5 occurrences de `assertLess(elapsed, 1.0)` sont remplacées par un appel au helper partagé `assert_dialog_guard_intercepts_promptly()`.
- [x] Le helper et la constante `_HANG_DETECTION_CEILING_SECONDS` vivent exclusivement dans `tests/integration/_qt_dialog_safety_net.py`.
- [x] `_DialogGuard` (eventFilter/singleShot/start/stop) reste strictement inchangé.
- [x] Les assertions fonctionnelles existantes (`assertRaises(UnexpectedDialogError)`, `assertIn(titre, ...)`) sont préservées à l'identique dans les 5 sites migrés.
- [x] Un nouveau test prouve que le plafond échoue bien sur une dégradation simulée bornée (§5).
- [x] Un nouveau test prouve que le plafond n'échoue pas sur un délai simulé sous le seuil (§5, non-régression).
- [x] Aucun fichier `src/` modifié.
- [x] Stratégie de répétition (§9) exécutée et documentée avec des nombres exacts, pas une formulation vague.
- [x] Full suite : nombre exact confirmé (2734 attendus), formulation stricte sur tout flake historique observé ou non sur le run de clôture.
- [x] Aucun smoke requis, confirmé explicitement dans le rapport d'implémentation.

### Résultats réels

**Fichiers modifiés** : exactement les 5 fichiers de tests prévus (`_qt_dialog_safety_net.py`, `test_qt_dialog_safety_net.py`, `test_main_window_new_project.py`, `test_main_window_rename_project.py`, `test_lora_roundtrip.py`) plus ce document — confirmé par `git status --short`/`git diff --stat -- src` (vide). `import time` devenu mort dans `test_lora_roundtrip.py` après migration, retiré par la même occasion (conséquence directe de la migration, pas un ajout hors périmètre).

**Implémentation** : conforme section par section à ce document. `_HANG_DETECTION_CEILING_SECONDS = 5.0` et `assert_dialog_guard_intercepts_promptly()` ajoutés à `_qt_dialog_safety_net.py` (§4), `_DialogGuard` non touché. Les 5 occurrences de `assertLess(elapsed, 1.0)` remplacées par le helper, `assertIn(...)` sur le titre/texte conservés à l'identique. `grep -rn "assertLess(elapsed" tests/` confirme **zéro occurrence restante**.

**Sémantique du plafond préservée dans le code** : le commentaire au-dessus de `_HANG_DETECTION_CEILING_SECONDS`, la docstring de `assert_dialog_guard_intercepts_promptly()` et le message de l'assertion elle-même énoncent tous explicitement que ce plafond ne garantit pas l'absence d'un hang total (structurellement indétectable par une assertion post-hoc, voir §2) — il détecte uniquement une interception qui réussit mais devient anormalement lente. Aucune terminologie sur-promettant cette garantie n'a été introduite.

**Tests ajoutés (§5)** : `test_ceiling_rejects_a_bounded_round_trip_slower_than_the_ceiling` (délai simulé et borné de `_HANG_DETECTION_CEILING_SECONDS + 0.5s` via patch de `_DialogGuard._close_if_visible`, confirme que l'assertion échoue avec le message attendu) et `test_ceiling_accepts_a_bounded_round_trip_faster_than_the_ceiling` (délai borné de 0.5s, confirme la non-régression du chemin nominal). Aucun hang réel jamais simulé.

**Tests ciblés** : `test_qt_dialog_safety_net.py` 9/9, `test_main_window_new_project.py` 42/42, `test_main_window_rename_project.py` 22/22, `test_lora_roundtrip.py` 269/269 — **342/342 au total**.

**Répétitions (§9)** : `test_main_window_new_project.py` **10/10 exécutions isolées vertes** (42/42 à chaque fois) ; `test_main_window_rename_project.py` **5/5 exécutions isolées vertes** (22/22) ; `test_lora_roundtrip.py` **5/5 exécutions isolées vertes** (269/269). Aucune reproduction du flake en isolation, cohérent avec l'historique (jamais reproduit hors pression de suite complète).

**Full suite #1** : 2734 collectés, 2734 passés, 0 échoué, exit 0 (301.739s). **Full suite #2** (exécution indépendante) : 2734 collectés, 2734 passés, 0 échoué, exit 0 (301.432s) — nombre de tests identique entre les deux runs, aucune différence. Ni le flake `DialogGuard` (`assertLess`/timing) ni le flake distinct `ForgeLifecycleManagerRealProcessTest` ne se sont manifestés sur aucun des deux runs. Cette absence ne doit jamais être lue comme une disparition permanente du flake (jamais reproductible à volonté, seulement observé de façon intermittente sur certaines clôtures passées) — voir §2 et §7 : la fuite de widgets Qt M097/M099, cause plausible sous-jacente, reste une dette distincte, non traitée par cette mission.

**`git diff --check`** : clean (uniquement les avertissements normaux de conversion LF→CRLF).

**Smoke** : confirmé non requis — mission strictement confinée à `tests/integration/`, aucun fichier `src/` modifié.

**Écarts par rapport au contrat** : aucun.

## 13. Hors périmètre strict

`_DialogGuard`, fuite de widgets Qt M097/M099, `ForgeLifecycleManagerRealProcessTest`, lifecycle Forge, tout code `src/`, Training/OneTrainer, Central LoRA Library, toute nouvelle abstraction Qt générale, toute tentative de provoquer/résoudre un hang réellement infini.

## 14. Autorisation

**Implémentée, testée et clôturée.** Validée par l'architecte et par validation externe à chaque étape (rédaction, implémentation, clôture). Commit fonctionnel `6694ab43ecee205a5c1dda36d33af8c17dd6e514`, tag annoté `v0.2-mission133` (ciblant exactement ce commit), GitHub Release `v0.2-mission133` publiée manuellement (`gh` CLI confirmé indisponible, comme pour toutes les missions précédentes).
