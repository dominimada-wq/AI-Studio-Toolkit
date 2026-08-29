# Mission 089 — Central LoRA Library: Read-Only Consultation and Deletion

> **MISSION IMPLÉMENTÉE, EN ATTENTE DE CLÔTURE GIT.** 18 tests ciblés nets nouveaux (`test_lora_roundtrip.py`), non-régression complète, suite complète **1664/1664, aucun crash**, smoke test Qt réel exécuté et **PASS** (25/25 assertions, stable sur 3 exécutions consécutives — voir section 5). Voir section 7 pour l'état de clôture Git.

## 1. Contexte

L'audit post-Mission 088 a confirmé, par lecture directe du code, que la longue série de sécurisation transactionnelle (Missions 066–085) est close — aucun bug fonctionnel réel n'a été retrouvé dans le code actuel. Parmi les candidats comparés (bibliothèque centrale LoRA non consultable, `Dataset` de références → Inference, Prompt Library/tags, dette cosmétique `setButtonText()`, isolation EventBus, architecture Image+Video), le candidat retenu est la consultation/suppression de la bibliothèque centrale LoRA : `LoRALibraryManager.delete()` (Mission 087) est entièrement implémentée et testée mais n'a aucun appelant Presentation, et les événements `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_DELETED` (Mission 087) n'ont aucun abonné — depuis Mission 088, la bibliothèque peut être alimentée mais jamais consultée ni corrigée autrement qu'en éditant `lora_library.json` à la main.

Un premier mini-audit avait initialement envisagé trois emplacements UI (nouvelle Page Sidebar, section `SettingsPage`, deux onglets dans `LoRAPage`) sans trancher. L'architecte a ensuite orienté explicitement vers la solution à deux onglets et demandé sa vérification contre le code réel avant validation finale. Cette vérification a confirmé :
- `LoRAPage` (`src/ui/pages/lora_page.py`) est un unique `QVBoxLayout` linéaire — aucun `QTabWidget` n'existe encore dans le projet, mais le wrapping du contenu existant dans un premier onglet ne change que le parent Qt de chaque widget, jamais son nom d'attribut Python (confirmé par relecture : aucun test de `test_lora_roundtrip.py` n'inspecte `layout()`/`findChildren()`, tous référencent les widgets par attribut).
- `LoRALibraryManager.list_loras()` retourne des objets `LoRA` (accès par attribut), contrairement à `LoRAManager.list_loras()` qui retourne des `dict` — point d'implémentation à ne pas confondre par analogie.
- Le helper `_load_thumbnail_preview()` existant n'était **pas** directement réutilisable tel quel : il mutait un unique `QLabel` codé en dur (`self.thumbnail_label`), sans paramètre pour cibler un autre label. Vérifié avant réutilisation (conformément à l'instruction de l'architecte), puis extrait en une primitive paramétrée `_render_thumbnail_preview(label, thumbnail_path)`, dont `_load_thumbnail_preview()` devient un mince wrapper — comportement de l'onglet Personnage strictement inchangé, primitive désormais réutilisable pour l'onglet Bibliothèque centrale.
- Les événements `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_DELETED` transportent un payload à une seule entrée, mais la convention déjà établie dans ce fichier (`main_window.py`) est de toujours relire la liste complète depuis le Manager plutôt que de faire confiance au payload — appliquée à l'identique pour le nouvel onglet.

Comparée aux deux alternatives, la solution à deux onglets l'emporte sur la cohérence UX (un seul endroit pour un même concept LoRA à deux portées) et l'évolution future (place naturelle pour un futur modèle de références Character↔Library), au prix d'un coût de code légèrement supérieur (premier `QTabWidget` du projet) — jugé acceptable et sans risque de régression démontré.

## 2. Objectif

Permettre, depuis `LoRAPage`, de consulter la bibliothèque centrale LoRA (Mission 087) — nom, nombre de fichiers, les 4 métadonnées, miniature — et d'en supprimer une entrée avec confirmation explicite, sans introduire d'édition, d'import direct depuis cet onglet, ni d'association avec `Character.loras`/`Workspace`.

## 3. Contrat final validé

### 3.1 Structure de `LoRAPage`

Un titre partagé « LoRA » reste au-dessus d'un nouveau `QTabWidget` à deux onglets :
- **« Personnage »** : contenu strictement inchangé de l'ancien `LoRAPage`, déplacé tel quel dans `character_tab` — aucune logique métier modifiée, tous les attributs publics (`lora_list`, `engine_edit`, `add_to_library_button`, etc.) conservent leur nom.
- **« Bibliothèque centrale »** : nouvelle vue Application-level, exclusivement `LoRALibraryManager` — jamais `LoRAManager`, jamais fusionnée avec la collection Character-scoped malgré le dataclass `LoRA` partagé.

### 3.2 Onglet Bibliothèque centrale

`library_list` (tri alphabétique insensible à la casse, `f"{lora.name} ({len(lora.files)} fichier(s))"`), panneau détail en lecture seule (`QLabel` — jamais de `QLineEdit` désactivé — pour `engine`/`architecture`/`trigger_word`/`version`), aperçu miniature via `_render_thumbnail_preview()` (extraction paramétrée de l'ancien `_load_thumbnail_preview()`), bouton `delete_from_library_button` désactivé sans sélection.

Comportement miniature : présente et valide → affichée ; `thumbnail == ""` → « Aucune miniature. » ; fichier disparu → message dégradé (« Aperçu non disponible ») sans crash — aucun scanner ni réparation automatique.

Suppression : confirmation `QMessageBox` (Supprimer/Annuler, Annuler par défaut), `LoRALibraryManager.delete(lora_id, library_root)` avec `library_root` lu en direct depuis `application_settings_manager.settings.lora_library_path` (jamais mis en cache), `QMessageBox.critical` sur `LoRALibraryError`, `QMessageBox.warning` non bloquant sur `cleanup_failed` — aucun rafraîchissement manuel après un succès : l'événement `LORA_LIBRARY_DELETED` déjà publié par le Manager déclenche `update_central_library()` via l'EventBus, exactement le principe Event-Driven UI déjà appliqué par `delete_lora()`.

### 3.3 Événements

`update_central_library()` est abonnée uniquement à `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_DELETED` (`main_window.py`) — jamais à un événement Workspace/Character. Relit systématiquement `list_loras()` en entier, ignore le payload. Appelée une première fois à la construction de `LoRAPage` pour peupler l'onglet dès le lancement. Aucune sélection n'est restaurée après un rafraîchissement (liste/détail/bouton toujours réinitialisés) — pas de risque de transfert de sélection entre deux entités, contrairement aux galeries `ExtendedSelection` protégées par Mission 082.

### 3.4 Hors périmètre (confirmé, inchangé)

Édition des entrées centrales, import depuis l'onglet central, association Character/Workspace, modèle de scopes, migration `project.json`, sélection dans Inference, exposition moteur/provider, déduplication, scanner/réparateur, suppression tenant compte de références futures.

## 4. Implémentation

- `src/ui/pages/lora_page.py` — `__init__()` restructuré autour d'un `QTabWidget` (`self.tab_widget`) à deux onglets ; contenu Personnage déplacé tel quel dans `character_tab` ; nouvel onglet `library_tab` avec `library_list`, `library_engine_label`/`library_architecture_label`/`library_trigger_word_label`/`library_version_label`, `library_thumbnail_label`, `delete_from_library_button` ; nouvelles méthodes `on_library_selection_changed()`, `_load_library_details()`, `update_central_library()`, `delete_from_library()` ; `_load_thumbnail_preview()` devient un mince wrapper de la nouvelle primitive paramétrée `_render_thumbnail_preview(label, thumbnail_path)`.
- `src/ui/main_window.py` — import de `LORA_LIBRARY_IMPORTED`/`LORA_LIBRARY_DELETED` ; deux nouveaux abonnements dédiés vers `lora_page.update_central_library`, strictement séparés des abonnements Workspace/Character existants.
- `tests/integration/test_lora_roundtrip.py` — nouvelle classe `LoRAPageCentralLibraryTabTest` (18 tests).

## 5. Tests automatisés

- **18 tests ciblés nets nouveaux** (`LoRAPageCentralLibraryTabTest`) : structure des deux onglets et ordre ; non-régression des widgets de l'onglet Personnage (toujours présents, toujours parentés) ; bibliothèque vide ; une entrée (nom + nombre de fichiers) ; plusieurs entrées triées ; les 4 métadonnées affichées à la sélection ; miniature présente ; aucune miniature ; miniature physiquement disparue sans crash ; sélection → bouton activé ; désélection → bouton désactivé et panneau vidé ; Cancel → aucune mutation ; suppression confirmée réelle (registre + disque + UI réinitialisée) ; erreur Manager → message + entrée conservée ; `cleanup_failed` → suppression logique maintenue + avertissement ; import M088 → apparition automatique via EventBus ; suppression → mise à jour automatique via EventBus ; New/Rename/Close de Workspace + création de Character → bibliothèque centrale strictement inchangée.
- Non-régression complète : `test_lora_roundtrip.py` (187 pré-existants + 18 nets nouveaux = 205/205), `test_lora_library_roundtrip.py` (41/41), `test_application_settings_roundtrip.py` (17/17).
- **1664/1664 tests verts au total** (1646 précédents + 18 nets nouveaux), une exécution complète `unittest discover`, aucun crash.
- Smoke test Qt réel, exécuté par Claude, `LoRAPage`/`LoRAManager`/`LoRALibraryManager`/`ApplicationSettingsManager` réels, Workspace/Character/LoRA réels avec fichiers+thumbnail réels sur disque, bibliothèque centrale pointée vers un dossier temporaire réel — **PASS, 25/25 assertions** (stable sur 3 exécutions consécutives) : clic réel sur « Ajouter à la bibliothèque centrale » (Mission 088) suivi d'une mise à jour automatique de l'onglet Bibliothèque centrale via l'EventBus (sans appel manuel) ; bascule réelle d'onglet ; sélection réelle affichant les 4 métadonnées et une miniature réelle non nulle ; `lora_library.json` et le dossier physique de l'entrée vérifiés directement sur disque avant suppression ; clic réel sur « Supprimer » (confirmation acceptée) suivi d'une mise à jour automatique de la liste/du panneau/du bouton via l'EventBus ; `lora_library.json` et le dossier physique confirmés vidés/supprimés après la suppression ; **fichiers et thumbnail de la LoRA Character-scoped source confirmés strictement inchangés (mêmes chemins, même contenu) après l'ensemble du cycle import → consultation → suppression**.

## 6. Conclusion

La bibliothèque centrale LoRA posée par Mission 087 et alimentée depuis l'UI par Mission 088 devient enfin consultable et corrigible directement depuis l'application : `LoRAPage` présente désormais deux onglets clairement séparés — « Personnage » (comportement Character-scoped strictement inchangé) et « Bibliothèque centrale » (consultation en lecture seule + suppression, exclusivement `LoRALibraryManager`, jamais fusionnée avec `LoRAManager`). Le rafraîchissement est entièrement piloté par l'EventBus (`LORA_LIBRARY_IMPORTED`/`DELETED`), sans jamais réagir à un événement Workspace/Character — la bibliothèque centrale reste Application-level. Aucune association Character/Workspace, aucune édition, aucun import direct, aucune exposition moteur/provider n'a été engagée — la fondation reste ouverte pour de futures missions dédiées.

## 7. État d'avancement et clôture Git

- Mini-audit contractuel (orientation deux onglets) : **terminé**, validé par l'architecte.
- Implémentation : **réalisée**, strictement limitée au périmètre de la section 4.
- Tests ciblés : **18/18 verts**, non-régression `test_lora_roundtrip.py`/`test_lora_library_roundtrip.py`/`test_application_settings_roundtrip.py` **verte** (voir section 5).
- Suite complète : **1664/1664, aucun crash**, une exécution complète `unittest discover`.
- `git diff --check` : **propre** (uniquement un avertissement de normalisation de fin de ligne LF/CRLF).
- Contrôle de périmètre du diff : **conforme** (2 fichiers de production modifiés, 1 fichier de test modifié, ce document de mission ; `Character.loras`, `project.json`, aucune association, aucun moteur/provider confirmés non touchés).
- Smoke test Qt réel : **réalisé, PASS, 25/25 assertions, stable sur 3 exécutions consécutives**.
- Clôture Git (commit/tag/Release) : autorisée par l'architecte, exécutée selon la procédure habituelle — voir le commit/tag réels une fois créés (non fixés en dur ici avant leur existence, par principe de non-auto-référence).
