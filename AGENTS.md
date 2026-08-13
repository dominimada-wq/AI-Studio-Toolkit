# AGENTS.md — Point d'entrée pour Codex et les autres agents de développement

Ce fichier est le point d'entrée des instructions pour Codex (et tout autre agent de développement automatisé) sur le projet AI Studio Toolkit. Il ne remplace ni ne duplique la mémoire du projet — il indique où la trouver et comment l'utiliser :

- `CLAUDE.md` (racine) : règles permanentes, architecture, conventions — actuellement rédigées pour Claude Code, mais valables pour tout agent.
- `docs/PROJECT_CONTEXT.md` : état consolidé actuel du projet — référence unique pour "où en est le projet aujourd'hui".
- `docs/missions/MISSION_XXX.md` : archives détaillées, une par mission — à consulter quand l'historique d'une mission précise est nécessaire.

`AGENTS.md` n'est ni un journal de missions ni une copie de `CLAUDE.md` : il ne doit être modifié que lorsque les instructions destinées aux agents changent.

## Avant toute modification

Codex doit, dans l'ordre :

1. lire `docs/PROJECT_CONTEXT.md` ;
2. consulter les fichiers pertinents de `docs/missions/` lorsque l'historique d'une mission est nécessaire ;
3. prendre connaissance des règles permanentes et conventions architecturales documentées dans `CLAUDE.md` ;
4. considérer `docs/PROJECT_CONTEXT.md` comme la référence pour l'état actuel du projet — jamais une supposition, jamais une extrapolation ;
5. ne jamais inventer une information historique absente ou incertaine ; si une information nécessaire n'est pas disponible ou reste incertaine dans la documentation existante, le signaler explicitement plutôt que de la déduire.

## Avant une nouvelle mission

Codex doit :

- identifier l'objectif et le périmètre de la mission ;
- analyser le code et l'architecture concernés ;
- déterminer les impacts éventuels sur Domain, Managers, Infrastructure, UI, EventBus, persistance et tests ;
- identifier les risques de compatibilité et les conflits architecturaux potentiels ;
- présenter l'analyse d'impact avant toute implémentation, lorsque le workflow du projet exige une validation (voir `CLAUDE.md`, section "Commits, tags et releases").

## Règles de développement

Codex doit :

- préserver l'architecture existante (couches Presentation → Managers → Domain → Infrastructure → Core/EventBus, voir `CLAUDE.md`) ;
- respecter les conventions du projet (nommage, patterns d'ownership, idempotence, etc. — voir `CLAUDE.md`) ;
- ne pas ajouter de dépendance sans validation explicite ;
- ne pas modifier de fichiers sans rapport avec la mission en cours ;
- privilégier les modifications minimales et ciblées ;
- signaler les ambiguïtés architecturales au lieu de les résoudre silencieusement ;
- ne jamais transformer une hypothèse en décision de projet établie.

## Validation

Après toute modification, Codex doit :

- exécuter les tests pertinents ;
- exécuter la suite complète lorsque les règles du projet l'exigent (voir `CLAUDE.md`, section "Contraintes techniques importantes") ;
- vérifier le diff ;
- vérifier qu'aucun fichier étranger à la mission n'a été modifié ;
- signaler explicitement tout test non exécuté, échec, avertissement ou limitation constatée.

## Sécurité Git

Sans autorisation explicite de l'architecte du projet, Codex ne doit jamais :

- effectuer de force-push ;
- rebaser l'historique publié ;
- effectuer de reset destructif ;
- réécrire des commits ou des tags existants ;
- créer un tag automatiquement ;
- publier une GitHub Release automatiquement ;
- inclure dans un commit des modifications étrangères à la tâche en cours.

## Workflow de fin de mission

Identique à la règle permanente de `CLAUDE.md` :

```
Mission terminée
→ tests et validations
→ mise à jour de docs/PROJECT_CONTEXT.md
→ création ou mise à jour de docs/missions/MISSION_XXX.md
→ vérification de cohérence documentaire
→ commit après validation
→ tag uniquement lorsque prévu et autorisé
→ GitHub Release uniquement lorsque prévue et autorisée
```

## Règles de modification de ce fichier

- `CLAUDE.md` n'est modifié que lorsqu'une règle permanente, une convention ou un principe architectural change.
- `AGENTS.md` n'est modifié que lorsque les instructions destinées aux agents (Codex ou autres) changent.
- Ni `CLAUDE.md` ni `AGENTS.md` ne doivent devenir des journaux de missions — l'historique détaillé vit exclusivement dans `docs/missions/`, l'état consolidé dans `docs/PROJECT_CONTEXT.md`.
