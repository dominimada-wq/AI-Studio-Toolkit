# Mission 030 — Assistant IA / LLM Foundation + Ollama Minimal Integration

**État final (voir sections à venir)** : spécification uniquement — audit d'API Ollama effectué contre la documentation réelle, architecture figée, aucune implémentation réalisée à ce stade. En attente de validation de l'architecte avant tout code.

## 1. Contexte

L'audit de priorisation Mission 030 (voir échange précédent) a recommandé une fondation architecturale pour un futur assistant IA/LLM intégré à AI Studio Toolkit, avec Ollama comme premier backend concret — sans coupler l'UI directement à Ollama, exactement comme `ComfyUIEngine` a toujours été découplé de l'UI via `GenerationManager` (Missions 012/013/018/021/023/024/025). Le besoin futur correspondant ("Assistant IA / LLM intégré à AI Studio Toolkit") est déjà documenté dans `docs/PROJECT_CONTEXT.md` (modification non commitée, préservée pendant cette passe — voir section "Git / documentation" en fin de document).

Mission 030 pose uniquement la fondation : une abstraction minimale, un provider Ollama concret, sa configuration dans Settings, et sa découverte de modèles — **aucun usage utilisateur final** (génération de prompt, vision, contexte Character, historique) n'est câblé cette mission.

## 2. Objectif

1. Définir le plus petit contrat utile pour un futur "AI backend" (texte uniquement), sans framework générique disproportionné.
2. Implémenter `OllamaEngine`, un client HTTP minimal (stdlib) satisfaisant ce contrat, vérifié contre l'API Ollama réelle.
3. Exposer sa configuration dans `ApplicationSettings`/`SettingsPage`, selon le patron déjà établi par `comfyui_url`/`comfyui_path`/`comfyui_checkpoint_name` (Missions 010/018/025).
4. Ne rien câbler à `InferencePage`/`PromptsPage`/`CharactersPage` — fondation seule.

## 3. Audit de l'API Ollama réelle

Vérifié contre `github.com/ollama/ollama/blob/main/docs/api.md` (documentation officielle) :

### 3.1 Découverte des modèles

`GET /api/tags` — liste les modèles **localement présents** sur l'instance Ollama interrogée (jamais un scan de dossier local par AI Studio Toolkit lui-même — exactement le même principe déjà retenu pour `ComfyUIEngine.list_checkpoints()` en Mission 025 : interroger le serveur en cours d'exécution plutôt que réimplémenter une résolution de chemins qu'il fait déjà correctement).

Réponse :
```json
{
  "models": [
    {
      "name": "llama3.2:latest",
      "model": "llama3.2:latest",
      "modified_at": "...",
      "size": 2019393189,
      "digest": "...",
      "details": {"family": "llama", "parameter_size": "3.2B", "quantization_level": "Q4_K_M"}
    }
  ]
}
```

**Retenu pour Mission 030** : uniquement le champ `"name"` de chaque entrée. `"details"`/`"size"`/`"digest"` ignorés — aucun consommateur identifié aujourd'hui, cohérent avec `list_checkpoints()` qui ne retourne que des noms.

### 3.2 Génération de texte

Deux endpoints existent : `POST /api/generate` (complétion simple, `{"model": ..., "prompt": ...}`) et `POST /api/chat` (conversationnel, `{"model": ..., "messages": [...]}`).

**Retenu pour Mission 030 : `POST /api/generate`.** Un simple prompt texte → réponse texte est le besoin minimal de cette fondation (« envoyer un prompt texte, recevoir une réponse texte ») ; `/api/chat` introduirait une notion de tour de conversation/historique de messages qui n'a aucun consommateur avant une mission future (historique de prompts, contexte Character) — **explicitement hors périmètre ici**. Rien n'empêche un futur `OllamaEngine.chat()` additif le jour où ce besoin devient réel.

### 3.3 Streaming vs non-streaming

Confirmé : `"stream": false` dans le corps de la requête fait retourner un unique objet JSON complet plutôt qu'un flux de fragments. **Retenu pour Mission 030**, conformément à la préférence explicite de l'architecte — garde la fondation testable simplement (un seul `urlopen()`/`json.loads()`, exactement le patron déjà utilisé par `ComfyUIEngine._request_json()`), sans gestion de flux incrémental.

Réponse non-streaming de `/api/generate` :
```json
{
  "model": "llama3.2",
  "created_at": "...",
  "response": "The sky is blue because...",
  "done": true,
  "done_reason": "stop",
  "context": [1, 2, 3],
  "total_duration": 5043500667,
  ...
}
```

**Retenu pour Mission 030** : uniquement le champ `"response"` (`str`). Les métriques de performance/`context` (utilisé par Ollama pour enchaîner des tours de conversation sans `/api/chat`) sont ignorées — aucun consommateur aujourd'hui.

### 3.4 Distinction texte / vision — limite documentée, non résolue

Vérifié explicitement, comme demandé : le champ `"capabilities"` (ex. `["completion", "vision"]`) **n'est pas présent de façon fiable dans `GET /api/tags`** — il n'apparaît que dans la réponse de `GET /api/show` (documentation officielle), un endpoint distinct qui doit être appelé **individuellement pour chaque modèle**. Interroger `/api/show` pour chaque modèle détecté à chaque rafraîchissement de la liste multiplierait les appels réseau (N+1) pour une information non consommée par Mission 030 (le texte seul est implémenté).

**Décision** : `AIModelInfo` (voir section 4) ne porte donc **aucun champ de capacité** cette mission — ni `vision: bool` deviné, ni valeur par défaut trompeuse. C'est une limite documentée, pas une fonctionnalité partiellement implémentée. La structure reste néanmoins additive (NamedTuple, voir section 4) : un futur champ de capacité pourra être ajouté sans casser aucun consommateur existant, sans qu'aucune conception de ce mécanisme ne soit figée maintenant. Le format exact d'une future détection (appel `/api/show` à la demande, uniquement lorsqu'un usage vision réel l'exigera) reste un point ouvert pour une mission future.

### 3.5 Erreurs

La documentation ne détaille pas de schéma d'erreur explicite pour un modèle inconnu ou une requête malformée. Par prudence (comportement non vérifié empiriquement, à confirmer par le smoke test réel), `OllamaEngine` traite toute réponse HTTP d'erreur comme un corps potentiellement JSON contenant un champ `"error"` (`str`) — pattern déjà utilisé nulle part ailleurs dans ce projet mais raisonnable et sans risque : si le corps n'est pas un JSON exploitable ou ne porte pas ce champ, l'erreur générique de communication s'applique (voir section 4.3).

## 4. Architecture retenue

### 4.1 Principe

```
Fonctionnalité AI Studio Toolkit (future, hors périmètre Mission 030)
        ↓
Abstraction LLM/AI backend  (src/engines/ai_backend.py)
        ↓
Provider Ollama concret     (src/engines/ollama_engine.py)
```

Aucune fonctionnalité ne dépend de `OllamaEngine` directement — seulement de l'abstraction `AIBackend`. `SettingsPage` fait exception assumée (voir section 4.5), au même titre que `SettingsPage` importe déjà `ComfyUIEngine` directement pour `refresh_checkpoints()` : la page de configuration/test de connexion d'un provider connaît nécessairement ce provider, ce n'est pas la frontière que l'abstraction protège.

### 4.2 `src/engines/ai_backend.py` (nouveau) — le plus petit contrat utile

```python
from typing import NamedTuple, Protocol, runtime_checkable


class AIModelInfo(NamedTuple):
    """
    Deliberately minimal (Mission 030) — only what every backend can
    report today. Additive by construction (NamedTuple, same pattern
    as ImportResult/CollisionInfo in workspace_manager.py): a future
    capability field (e.g. vision support) can be appended without
    breaking any existing attribute-based consumer. No such field
    exists yet because Ollama's /api/tags does not reliably expose it
    (see MISSION_030.md section 3.4) — this is a documented limitation,
    not an oversight.
    """
    name: str


class AIBackendError(Exception):
    """
    Common error type raised by every AIBackend implementation for any
    communication/protocol failure — a future consumer catches this
    single type regardless of which provider is configured, the same
    way GenerationManager normalizes ComfyUIEngineError/OSError into
    its own GenerationError today.
    """


@runtime_checkable
class AIBackend(Protocol):
    """
    Structural contract (typing.Protocol — no inheritance required,
    same zero-ceremony spirit as ComfyUIEngine having no base class).
    Text-only for Mission 030 by deliberate choice — no chat/message
    history, no vision, no streaming. A provider satisfies this
    Protocol simply by implementing both methods with this exact
    signature; nothing needs to import or subclass AIBackend to work.
    """

    def list_models(self) -> list[AIModelInfo]:
        """Returns the models currently available on this backend."""

    def generate_text(self, prompt: str, model: str) -> str:
        """Sends a single text prompt, returns the backend's full text response."""
```

Aucune connaissance HTTP/JSON dans ce module — pur contrat, comme `src/engines/workflows/comfyui_workflows.py` est pure construction de graphe sans connaissance transport.

### 4.3 `src/engines/ollama_engine.py` (nouveau) — provider concret

```python
class OllamaEngine:  # satisfies AIBackend structurally, no inheritance
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 30.0): ...
    def list_models(self) -> list[AIModelInfo]: ...       # GET /api/tags
    def generate_text(self, prompt: str, model: str) -> str: ...  # POST /api/generate, stream=false
```

Implémentation mirroir de `ComfyUIEngine` (stdlib `urllib`/`json` uniquement, aucune nouvelle dépendance) :
- `_request_json()` privé, même discipline exacte que `ComfyUIEngine._request_json()` : `HTTPError` → tente quand même de décoder le corps en JSON (pour extraire un éventuel `"error"`) ; `URLError`/`OSError` → `AIBackendError` ("serveur injoignable") ; `json.JSONDecodeError` → `AIBackendError` ("réponse invalide").
- `list_models()` : erreur dure (`AIBackendError`) si `"models"` absent ou n'est pas une liste ; chaque entrée est filtrée défensivement (`isinstance(entry, dict)` et `name` non vide) plutôt que de lever pour une seule entrée malformée — même discipline que `list_checkpoints()`.
- `generate_text()` : erreur dure si `"response"` absent/non-`str` — message d'erreur Ollama (`data.get("error")`) inclus dans l'exception si présent (section 3.5).
- Port par défaut Ollama `11434` (défaut officiel documenté), reflété dans le défaut littéral d'`ApplicationSettings.ollama_url` (voir 4.4) exactement comme `comfyui_url` reflète le défaut ComfyUI historique.

### 4.4 `ApplicationSettings` — champs ajoutés (plat, patron `comfyui_*` inchangé)

| Champ | Défaut | Consommé par du code cette mission ? |
|---|---|---|
| `ollama_url: str` | `"http://127.0.0.1:11434"` | Oui — `OllamaEngine(base_url=...)` |
| `ollama_path: str` | `""` | **Non** — dossier d'installation local optionnel, réservé à un usage futur (détection, ouverture, diagnostic, démarrage/arrêt, exploration locale), miroir exact de `comfyui_path` depuis Mission 010 |
| `ollama_model_name: str` | `""` | Oui — modèle par défaut sélectionné/affiché dans Settings |

**Nom retenu : `ollama_model_name`** (et non `ollama_default_model`) — cohérence avec `comfyui_checkpoint_name` (`<provider>_<concept>_name`), conformément à la préférence de l'architecte pour la cohérence avec ce champ précis. Pas de valeur par défaut littérale non vide pour `ollama_model_name` (contrairement à `comfyui_checkpoint_name`) : il n'existe aucun comportement historique à préserver ici — Ollama est une intégration entièrement nouvelle, `""` signifie honnêtement "non configuré", exactement comme `python_path`/`onetrainer_path`.

`ApplicationSettingsManager.update()` gagne 3 paramètres optionnels nommés (`ollama_url`, `ollama_path`, `ollama_model_name`), même contrat idempotent exact que les 5 existants (valeur identique → `False`, pas de `save()`, pas d'événement).

**Note architecturale explicitement demandée, à documenter sans agir dessus** : `update()` passe de 5 à 8 paramètres explicites avec cet ajout. Ce n'est plus seulement une anticipation abstraite mais un signal concret que le besoin futur déjà documenté ("Refonte et organisation future de la page Settings", `docs/PROJECT_CONTEXT.md`) devient réellement pressant à mesure que les providers s'accumulent — **aucune refonte n'est entreprise dans Mission 030**, ce constat est réservé à la clôture documentaire.

### 4.5 `SettingsPage` — UI minimale, patron `comfyui_checkpoint_name_edit` reproduit à l'identique

Trois nouveaux champs dans la section "Application" existante (pas de nouvelle section/onglet — cohérent avec "ne pas refactoriser Settings maintenant") :

| Widget | Label | Type |
|---|---|---|
| `ollama_url_edit` | "Ollama URL :" | `QLineEdit` |
| `ollama_path_edit` | "Ollama :" | `QLineEdit` (miroir exact de `"ComfyUI :"` pour `comfyui_path_edit`) |
| `ollama_model_name_edit` | "Ollama Model :" | `QComboBox` éditable (miroir exact de `comfyui_checkpoint_name_edit`) |

Plus `refresh_ollama_models_button` ("Rafraîchir les modèles") + `ollama_discovery_status_label`, câblés à `refresh_ollama_models()` — **reproduit exactement `refresh_checkpoints()`** : construit un `OllamaEngine(base_url=self.ollama_url_edit.text(), timeout=OLLAMA_DISCOVERY_TIMEOUT)` à la volée (URL actuellement tapée, pas nécessairement enregistrée), peuple le `QComboBox` (`blockSignals` → `clear()` → `addItems([m.name for m in models])` → `setCurrentText()` préservé → `blockSignals(False)`), message de repli identique en cas d'échec ("Découverte impossible : Ollama injoignable ou configuration invalide. La saisie manuelle du modèle reste disponible."), jamais de plantage. `OLLAMA_DISCOVERY_TIMEOUT = 5.0` — même valeur courte dédiée que `CHECKPOINT_DISCOVERY_TIMEOUT`, distincte de tout futur timeout de génération.

`SettingsPage` importe `OllamaEngine` **directement** (pas `AIBackend`) — exception assumée et documentée en 4.1 : c'est la même exception déjà en vigueur pour `ComfyUIEngine`.

Message d'aide de la section Application étendu pour mentionner qu'un changement Ollama prend effet au redémarrage, comme pour ComfyUI.

### 4.6 Ce qui reste strictement spécifique à Ollama

Tout le contenu de `ollama_engine.py` (endpoints, forme JSON, `stream: false`, extraction de `"name"`/`"response"`, gestion de `"error"`) — rien de tout cela ne fuit dans `ai_backend.py`, `SettingsPage` (au-delà de la construction de l'objet et de la lecture de `.name`), ou `ApplicationSettings`.

## 5. Périmètre IN

- `src/engines/ai_backend.py` : `AIBackend` (Protocol), `AIModelInfo` (NamedTuple), `AIBackendError`.
- `src/engines/ollama_engine.py` : `OllamaEngine.list_models()`/`generate_text()`.
- Connexion HTTP stdlib (`urllib`) — confirmé suffisant, aucune nouvelle dépendance.
- `ApplicationSettings`/`ApplicationSettingsManager` : `ollama_url`/`ollama_path`/`ollama_model_name`.
- `SettingsPage` : 3 champs + bouton de rafraîchissement + label de statut, patron `comfyui_checkpoint_name_edit` reproduit.
- Gestion d'erreurs : serveur injoignable, URL invalide, réponse HTTP d'erreur, JSON invalide, réponse structurellement inattendue — toutes normalisées en `AIBackendError`.
- Tests (voir section 7).

## 6. Périmètre OUT (strict, explicitement différé)

Aucun bouton IA dans `InferencePage` ; aucun usage dans `PromptsPage` ; aucun contexte Character ; aucun historique de prompts ; aucune vision/analyse d'image ; aucun upload d'image vers Ollama ; aucun RAG/base vectorielle ; aucun agent ; aucun provider cloud ; aucune UI de streaming ; aucun démarrage/arrêt d'Ollama ; **aucune lecture de `ollama_path`** par aucun code (champ stocké, jamais consommé, exactement comme `comfyui_path`) ; aucune refonte globale de Settings ; `/api/chat`, historique de conversation/`context` non utilisés.

## 7. Stratégie de tests

### 7.1 `tests/integration/test_ollama_engine.py` (nouveau, entièrement mocké — aucune requête réseau réelle)

Mirroir de `test_comfyui_engine.py` :
- `list_models()` : plusieurs/un seul/zéro modèle retourné, entrée malformée filtrée sans lever (nom absent/vide/non-`str`), `"models"` absent/non-liste → `AIBackendError`, requête GET vers le bon endpoint (`/api/tags`) vérifiée.
- `generate_text()` : réponse réussie retournée telle quelle, corps de requête exact vérifié (`model`, `prompt`, `stream: false`), `"response"` absent/non-`str` → `AIBackendError`, `"error"` Ollama présent → message repris dans l'exception.
- Communication : serveur injoignable, JSON invalide, erreur HTTP à corps vide, URL structurellement invalide.
- Deux appels indépendants (`list_models()` puis `generate_text()`, ou deux `generate_text()` successifs) sans état partagé.
- **Test architectural dédié** : `isinstance(OllamaEngine(...), AIBackend)` — confirme la conformité structurelle au Protocol sans héritage, exactement l'esprit des tests architecturaux déjà présents ailleurs dans ce projet (anti-couplage `GenerationManager`, anti-`"denoise"` dans `inference_page.py`).

### 7.2 `tests/integration/test_application_settings_roundtrip.py` (étendu)

Round-trip Domain (`to_dict()`/`from_dict()`) pour les 3 nouveaux champs, défauts corrects ; fichier legacy sans ces clés charge les défauts littéraux (pas de chaîne vide pour `ollama_url`, comportement identique au précédent déjà établi pour `comfyui_url`/`comfyui_checkpoint_name` en Mission 018) ; `ApplicationSettingsManager.update()` idempotent pour chacun des 3 champs individuellement et combinés.

### 7.3 `tests/integration/test_settings_page.py` (étendu)

Champs présents et éditables ; `refresh_ollama_models()` peuple le `QComboBox` depuis un `OllamaEngine.list_models()` mocké ; valeur actuellement affichée conservée même absente de la liste découverte ; échec de découverte (`AIBackendError`) sans plantage, message de repli affiché, `SettingsPage` toujours utilisable ; zéro modèle découvert sans erreur ; sauvegarde/rechargement restaure les 3 champs ; découverte utilisant l'URL actuellement tapée (pas nécessairement enregistrée) ; aucune interférence avec les champs ComfyUI/autres existants ; aucune découverte automatique au chargement.

### 7.4 Ordre d'exécution

Recherche préalable des mocks/signatures obsolètes (habitude établie), puis suite complète :
```bash
./.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
```
Nombre exact attendu à confirmer depuis le dépôt au moment de l'implémentation (base actuelle : 513/513 + nouveaux tests `test_ollama_engine.py` + extensions `test_application_settings_roundtrip.py`/`test_settings_page.py`).

## 8. Fichiers concernés (aucun modifié dans cette passe — liste prévisionnelle)

**Nouveaux** : `src/engines/ai_backend.py`, `src/engines/ollama_engine.py`, `tests/integration/test_ollama_engine.py`.

**Modifiés** : `src/domain/application_settings.py`, `src/managers/application_settings_manager.py`, `src/ui/pages/settings_page.py`, `tests/integration/test_application_settings_roundtrip.py`, `tests/integration/test_settings_page.py`.

**Non modifiés** : `src/ui/pages/inference_page.py`, `src/ui/pages/prompts_page.py`, `src/ui/pages/characters_page.py`, `src/managers/character_manager.py`, `src/managers/prompt_manager.py`, `src/engines/comfyui_engine.py`, tout module Domain/Manager hors `ApplicationSettings`.

## 9. Risques résiduels / décisions en attente

- **Comportement d'erreur Ollama non vérifié empiriquement** (section 3.5) — la documentation officielle ne détaille pas le schéma exact d'une erreur `/api/generate` (modèle inconnu, requête malformée) ; le smoke test réel devra confirmer que le traitement retenu (tentative de lecture d'un champ `"error"` JSON) correspond au comportement réel.
- **Dérive de version Ollama** : la forme exacte de `/api/tags` (champs `"name"` vs `"model"`, présence de `"details"`) peut évoluer entre versions — mitigé par le filtrage défensif déjà retenu (`isinstance` sur chaque entrée), même discipline que `list_checkpoints()`.
- **Limite de capacité vision documentée, non résolue** (section 3.4) — assumé explicitement, pas un report accidentel.
- **Croissance d'`ApplicationSettingsManager.update()`** (5 → 8 paramètres) — signal réel à l'appui du besoin futur déjà documenté de refonte Settings, non traité cette mission.
- Aucun risque identifié sur `InferencePage`/`PromptsPage`/`CharacterManager`/`DatasetManager` — aucun de ces fichiers n'est touché.

## 10. Critères d'acceptation

- `OllamaEngine` fonctionnel contre une instance Ollama locale réelle (voir smoke test, section 11).
- `AIBackend`/`AIModelInfo`/`AIBackendError` définis, `OllamaEngine` structurellement conforme (`isinstance` positif).
- `ApplicationSettings`/`SettingsPage` : configuration Ollama persistée, restaurée après redémarrage, découverte de modèles fonctionnelle avec repli sur saisie manuelle.
- Suite complète verte, aucune régression sur les 513 tests existants.
- `ollama_path` stocké et restauré, jamais lu par aucun autre code — vérifiable par relecture (`grep -rn "ollama_path" src/` ne doit apparaître que dans `application_settings.py`/`application_settings_manager.py`/`settings_page.py`).

## 11. Protocole de smoke test manuel réel

1. Lancer Ollama localement (`ollama serve`, ou déjà démarré par l'installation Windows), avec au moins un modèle déjà tiré (`ollama pull <modèle>`).
2. Ouvrir AI Studio Toolkit → Settings → confirmer `Ollama URL :` = `http://127.0.0.1:11434` par défaut (ou l'ajuster si Ollama écoute ailleurs).
3. Cliquer "Rafraîchir les modèles" → confirmer que la liste réellement installée localement s'affiche (comparer avec `ollama list`).
4. Sélectionner un modèle dans la liste.
5. "Enregistrer" → fermer et rouvrir AI Studio Toolkit (changement Application Settings, effectif au redémarrage comme pour ComfyUI) → confirmer que l'URL/le chemin/le modèle sont restaurés à l'identique.
6. Exécuter un appel texte minimal via la couche backend, **sans l'exposer comme fonctionnalité IA utilisateur finale** (appel direct `OllamaEngine(...).generate_text("...", model="...")`, par exemple depuis une console Python ou un script temporaire de vérification — jamais depuis un bouton UI, puisque `InferencePage`/`PromptsPage` restent hors périmètre) → confirmer qu'une réponse texte réelle est reçue.
7. Cas d'erreur à confirmer sans plantage : Ollama arrêté (`Ctrl+C` sur `ollama serve`) → message de repli affiché ; URL invalide (`http://127.0.0.1:1`) → même message ; aucun modèle installé sur l'instance testée → liste vide gérée proprement ("Aucun modèle détecté"), pas d'erreur.

PASS attendu sur les 7 étapes.

## Commit correspondant

Non applicable — spécification uniquement, aucune implémentation à ce stade.

## Tag / release correspondant

Non applicable — spécification uniquement.

## État final

**Spécification complète, API Ollama vérifiée contre la documentation officielle, architecture figée (abstraction + provider), en attente de validation explicite de l'architecte avant toute implémentation.**
