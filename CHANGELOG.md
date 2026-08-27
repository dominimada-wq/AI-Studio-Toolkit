# Changelog

Toutes les évolutions notables du projet **AI Studio Toolkit** sont documentées dans ce fichier.

## Sommaire

- **Mission 075 — Transactional Physical Cleanup of Dataset/LoRA Folders on Deletion**
  - [Résumé (Mission 075)](#résumé-mission-075)
  - [Tests ajoutés (Mission 075)](#tests-ajoutés-mission-075)
  - [État du projet (Mission 075)](#état-du-projet-mission-075)
- **Mission 074 — Rollback CharacterManager.update() Identity on Persistence Failure**
  - [Résumé (Mission 074)](#résumé-mission-074)
  - [Tests ajoutés (Mission 074)](#tests-ajoutés-mission-074)
  - [État du projet (Mission 074)](#état-du-projet-mission-074)
- **Mission 073 — Rollback LoRAManager.update() Metadata on Persistence Failure**
  - [Résumé (Mission 073)](#résumé-mission-073)
  - [Tests ajoutés (Mission 073)](#tests-ajoutés-mission-073)
  - [État du projet (Mission 073)](#état-du-projet-mission-073)
- **Mission 072 — Rollback Domain-Only create() on Persistence Failure**
  - [Résumé (Mission 072)](#résumé-mission-072)
  - [Tests ajoutés (Mission 072)](#tests-ajoutés-mission-072)
  - [État du projet (Mission 072)](#état-du-projet-mission-072)
- **Mission 071 — Rollback PromptManager.delete() on Persistence Failure**
  - [Résumé (Mission 071)](#résumé-mission-071)
  - [Tests ajoutés (Mission 071)](#tests-ajoutés-mission-071)
  - [État du projet (Mission 071)](#état-du-projet-mission-071)
- **Mission 070 — Rollback Scalar Domain-Only Mutations on Persistence Failure**
  - [Résumé (Mission 070)](#résumé-mission-070)
  - [Tests ajoutés (Mission 070)](#tests-ajoutés-mission-070)
  - [État du projet (Mission 070)](#état-du-projet-mission-070)
- **Mission 069 — Protect PromptsPage Draft Before New/Open Project**
  - [Résumé (Mission 069)](#résumé-mission-069)
  - [Tests ajoutés (Mission 069)](#tests-ajoutés-mission-069)
  - [État du projet (Mission 069)](#état-du-projet-mission-069)
- **Mission 068 — Rollback Domain-Only Deletions on Persistence Failure**
  - [Résumé (Mission 068)](#résumé-mission-068)
  - [Tests ajoutés (Mission 068)](#tests-ajoutés-mission-068)
  - [État du projet (Mission 068)](#état-du-projet-mission-068)
- **Mission 067 — Rollback Additive Filesystem Mutations on Persistence Failure**
  - [Résumé (Mission 067)](#résumé-mission-067)
  - [Tests ajoutés (Mission 067)](#tests-ajoutés-mission-067)
  - [État du projet (Mission 067)](#état-du-projet-mission-067)
- **Mission 066 — Safe Image Deletion Persistence**
  - [Résumé (Mission 066)](#résumé-mission-066)
  - [Tests ajoutés (Mission 066)](#tests-ajoutés-mission-066)
  - [État du projet (Mission 066)](#état-du-projet-mission-066)
- **Mission 065 — Block Prompt Assistant Close While Generation Is Running**
  - [Résumé (Mission 065)](#résumé-mission-065)
  - [Tests ajoutés (Mission 065)](#tests-ajoutés-mission-065)
  - [État du projet (Mission 065)](#état-du-projet-mission-065)
- **Mission 064 — Thumbnail Cache**
  - [Résumé (Mission 064)](#résumé-mission-064)
  - [Tests ajoutés (Mission 064)](#tests-ajoutés-mission-064)
  - [État du projet (Mission 064)](#état-du-projet-mission-064)
- **Mission 063 — Synchronize Delete Action with Selection**
  - [Résumé (Mission 063)](#résumé-mission-063)
  - [Tests ajoutés (Mission 063)](#tests-ajoutés-mission-063)
  - [État du projet (Mission 063)](#état-du-projet-mission-063)
- **Mission 062 — Confirm Destructive Entity Deletion**
  - [Résumé (Mission 062)](#résumé-mission-062)
  - [Tests ajoutés (Mission 062)](#tests-ajoutés-mission-062)
  - [État du projet (Mission 062)](#état-du-projet-mission-062)
- **Mission 061 — Adaptive Dialog Sizing**
  - [Résumé (Mission 061)](#résumé-mission-061)
  - [Tests ajoutés (Mission 061)](#tests-ajoutés-mission-061)
  - [État du projet (Mission 061)](#état-du-projet-mission-061)
- **Mission 060 — Adaptive Initial Window Size**
  - [Résumé (Mission 060)](#résumé-mission-060)
  - [Tests ajoutés (Mission 060)](#tests-ajoutés-mission-060)
  - [État du projet (Mission 060)](#état-du-projet-mission-060)
- **Mission 059 — ComfyUI LoRA Selection for Generation**
  - [Résumé (Mission 059)](#résumé-mission-059)
  - [Tests ajoutés (Mission 059)](#tests-ajoutés-mission-059)
  - [État du projet (Mission 059)](#état-du-projet-mission-059)
- **Mission 058 — Dead Code and Stale Documentation Cleanup (Round 2)**
  - [Résumé (Mission 058)](#résumé-mission-058)
  - [Tests ajoutés (Mission 058)](#tests-ajoutés-mission-058)
  - [État du projet (Mission 058)](#état-du-projet-mission-058)
- **Mission 057 — Remove Vestigial Workspace Fields and Dead Code**
  - [Résumé (Mission 057)](#résumé-mission-057)
  - [Tests ajoutés (Mission 057)](#tests-ajoutés-mission-057)
  - [État du projet (Mission 057)](#état-du-projet-mission-057)
- **Mission 056 — Typed Inference Reference Primitive**
  - [Résumé (Mission 056)](#résumé-mission-056)
  - [Tests ajoutés (Mission 056)](#tests-ajoutés-mission-056)
  - [État du projet (Mission 056)](#état-du-projet-mission-056)
- **Mission 055 — Graceful Settings Save Errors**
  - [Résumé (Mission 055)](#résumé-mission-055)
  - [Tests ajoutés (Mission 055)](#tests-ajoutés-mission-055)
  - [État du projet (Mission 055)](#état-du-projet-mission-055)
- **Mission 054 — Rename Dataset and Training after Creation**
  - [Résumé (Mission 054)](#résumé-mission-054)
  - [Tests ajoutés (Mission 054)](#tests-ajoutés-mission-054)
  - [État du projet (Mission 054)](#état-du-projet-mission-054)
- **Mission 053 — Rename Prompt after Creation**
  - [Résumé (Mission 053)](#résumé-mission-053)
  - [Tests ajoutés (Mission 053)](#tests-ajoutés-mission-053)
  - [État du projet (Mission 053)](#état-du-projet-mission-053)
- **Mission 052 — Rename Model, Workflow and LoRA after Creation**
  - [Résumé (Mission 052)](#résumé-mission-052)
  - [Tests ajoutés (Mission 052)](#tests-ajoutés-mission-052)
  - [État du projet (Mission 052)](#état-du-projet-mission-052)
- **Mission 051 — Sort Remaining Entity Lists by Name**
  - [Résumé (Mission 051)](#résumé-mission-051)
  - [Tests ajoutés (Mission 051)](#tests-ajoutés-mission-051)
  - [État du projet (Mission 051)](#état-du-projet-mission-051)
- **Mission 050 — Remove Individual Files from a LoRA**
  - [Résumé (Mission 050)](#résumé-mission-050)
  - [Tests ajoutés (Mission 050)](#tests-ajoutés-mission-050)
  - [État du projet (Mission 050)](#état-du-projet-mission-050)
- **Mission 049 — Sort Images and Dataset Galleries by File Date**
  - [Résumé (Mission 049)](#résumé-mission-049)
  - [Tests ajoutés (Mission 049)](#tests-ajoutés-mission-049)
  - [État du projet (Mission 049)](#état-du-projet-mission-049)
- **Mission 048 — Sort Images and Dataset Galleries by Filename**
  - [Résumé (Mission 048)](#résumé-mission-048)
  - [Tests ajoutés (Mission 048)](#tests-ajoutés-mission-048)
  - [État du projet (Mission 048)](#état-du-projet-mission-048)
- **Mission 047 — LoRA Metadata Fiche**
  - [Résumé (Mission 047)](#résumé-mission-047)
  - [Tests ajoutés (Mission 047)](#tests-ajoutés-mission-047)
  - [État du projet (Mission 047)](#état-du-projet-mission-047)
- **Mission 046 — Remove Images from the Workspace Gallery**
  - [Résumé (Mission 046)](#résumé-mission-046)
  - [Tests ajoutés (Mission 046)](#tests-ajoutés-mission-046)
  - [État du projet (Mission 046)](#état-du-projet-mission-046)
- **Mission 045 — Remove Images from a Dataset**
  - [Résumé (Mission 045)](#résumé-mission-045)
  - [Tests ajoutés (Mission 045)](#tests-ajoutés-mission-045)
  - [État du projet (Mission 045)](#état-du-projet-mission-045)
- **Mission 044 — Feed a Dataset from the Images Gallery**
  - [Résumé (Mission 044)](#résumé-mission-044)
  - [Tests ajoutés (Mission 044)](#tests-ajoutés-mission-044)
  - [État du projet (Mission 044)](#état-du-projet-mission-044)
- **Mission 043 — Dashboard Training Indicator**
  - [Résumé (Mission 043)](#résumé-mission-043)
  - [Tests ajoutés (Mission 043)](#tests-ajoutés-mission-043)
  - [État du projet (Mission 043)](#état-du-projet-mission-043)
- **Mission 042 — Dataset Thumbnail Gallery**
  - [Résumé (Mission 042)](#résumé-mission-042)
  - [Tests ajoutés (Mission 042)](#tests-ajoutés-mission-042)
  - [État du projet (Mission 042)](#état-du-projet-mission-042)
- **Mission 041 — Explicit Prompt Assistant Mode Selection**
  - [Résumé (Mission 041)](#résumé-mission-041)
  - [Tests ajoutés (Mission 041)](#tests-ajoutés-mission-041)
  - [État du projet (Mission 041)](#état-du-projet-mission-041)
- **Mission 040 — Restore Prompt Assistant Result Action**
  - [Résumé (Mission 040)](#résumé-mission-040)
  - [Tests ajoutés (Mission 040)](#tests-ajoutés-mission-040)
  - [État du projet (Mission 040)](#état-du-projet-mission-040)
- **Mission 039 — Enforce a clean output contract for the Prompt Assistant**
  - [Résumé (Mission 039)](#résumé-mission-039)
  - [Tests ajoutés (Mission 039)](#tests-ajoutés-mission-039)
  - [État du projet (Mission 039)](#état-du-projet-mission-039)
- **Mission 038 — Protect unsaved prompt drafts in PromptsPage**
  - [Résumé (Mission 038)](#résumé-mission-038)
  - [Tests ajoutés (Mission 038)](#tests-ajoutés-mission-038)
  - [État du projet (Mission 038)](#état-du-projet-mission-038)
- **Mission 037 — Distinguish no open project from no dataset in TrainingPage**
  - [Résumé (Mission 037)](#résumé-mission-037)
  - [Tests ajoutés (Mission 037)](#tests-ajoutés-mission-037)
  - [État du projet (Mission 037)](#état-du-projet-mission-037)
- **Mission 036 — Distinguish no open project from no principal character in warnings**
  - [Résumé (Mission 036)](#résumé-mission-036)
  - [Tests ajoutés (Mission 036)](#tests-ajoutés-mission-036)
  - [État du projet (Mission 036)](#état-du-projet-mission-036)
- **Mission 035 — Enregistrer comme nouveau Prompt… depuis un brouillon libre**
  - [Résumé (Mission 035)](#résumé-mission-035)
  - [Tests ajoutés (Mission 035)](#tests-ajoutés-mission-035)
  - [État du projet (Mission 035)](#état-du-projet-mission-035)
- **Mission 034 — Character Context minimal pour le Prompt Assistant**
  - [Résumé (Mission 034)](#résumé-mission-034)
  - [Tests ajoutés (Mission 034)](#tests-ajoutés-mission-034)
  - [État du projet (Mission 034)](#état-du-projet-mission-034)
- **Mission 033 — Prompts → Envoyer vers Inference**
  - [Résumé (Mission 033)](#résumé-mission-033)
  - [Tests ajoutés (Mission 033)](#tests-ajoutés-mission-033)
  - [État du projet (Mission 033)](#état-du-projet-mission-033)
- **Mission 032 — Prompt Assistant dans PromptsPage**
  - [Résumé (Mission 032)](#résumé-mission-032)
  - [Tests ajoutés (Mission 032)](#tests-ajoutés-mission-032)
  - [État du projet (Mission 032)](#état-du-projet-mission-032)
- **Mission 031 — Prompt Assistant Minimal (Inference)**
  - [Résumé (Mission 031)](#résumé-mission-031)
  - [Tests ajoutés (Mission 031)](#tests-ajoutés-mission-031)
  - [État du projet (Mission 031)](#état-du-projet-mission-031)
- **Mission 030 — Ollama Local AI Backend**
  - [Résumé (Mission 030)](#résumé-mission-030)
  - [Tests ajoutés (Mission 030)](#tests-ajoutés-mission-030)
  - [État du projet (Mission 030)](#état-du-projet-mission-030)
- **Mission 029 — Principal Character Consistency (LoRA / Prompts / Training)**
  - [Résumé (Mission 029)](#résumé-mission-029)
  - [Tests ajoutés (Mission 029)](#tests-ajoutés-mission-029)
  - [État du projet (Mission 029)](#état-du-projet-mission-029)
- **Mission 028 — Import Images into Workspace**
  - [Résumé (Mission 028)](#résumé-mission-028)
  - [Tests ajoutés (Mission 028)](#tests-ajoutés-mission-028)
  - [État du projet (Mission 028)](#état-du-projet-mission-028)
- **Mission 027 — Project Rename**
  - [Résumé (Mission 027)](#résumé-mission-027)
  - [Tests ajoutés (Mission 027)](#tests-ajoutés-mission-027)
  - [État du projet (Mission 027)](#état-du-projet-mission-027)
- **Mission 026 — Character Identity Foundation**
  - [Résumé (Mission 026)](#résumé-mission-026)
  - [Tests ajoutés (Mission 026)](#tests-ajoutés-mission-026)
  - [État du projet (Mission 026)](#état-du-projet-mission-026)
- **Mission 025 — ComfyUI Checkpoint Discovery & Selection**
  - [Résumé (Mission 025)](#résumé-mission-025)
  - [Tests ajoutés (Mission 025)](#tests-ajoutés-mission-025)
  - [État du projet (Mission 025)](#état-du-projet-mission-025)
- **Mission 024 — Réglage utilisateur de la force img2img**
  - [Résumé (Mission 024)](#résumé-mission-024)
  - [Tests ajoutés (Mission 024)](#tests-ajoutés-mission-024)
  - [État du projet (Mission 024)](#état-du-projet-mission-024)
- **Mission 023 — ComfyUI Img2Img Reference Workflow**
  - [Résumé (Mission 023)](#résumé-mission-023)
  - [Tests ajoutés (Mission 023)](#tests-ajoutés-mission-023)
  - [État du projet (Mission 023)](#état-du-projet-mission-023)
- **Mission 022 — Reference Image Transport Wiring**
  - [Résumé (Mission 022)](#résumé-mission-022)
  - [Tests ajoutés (Mission 022)](#tests-ajoutés-mission-022)
  - [État du projet (Mission 022)](#état-du-projet-mission-022)
- **Mission 021 — ComfyUI Image Upload**
  - [Résumé (Mission 021)](#résumé-mission-021)
  - [Tests ajoutés (Mission 021)](#tests-ajoutés-mission-021)
  - [État du projet (Mission 021)](#état-du-projet-mission-021)
- **Mission 020 — MainToolBar Actions Wiring**
  - [Résumé (Mission 020)](#résumé-mission-020)
  - [Tests ajoutés (Mission 020)](#tests-ajoutés-mission-020)
  - [État du projet (Mission 020)](#état-du-projet-mission-020)
- **Mission 019 — Images Gallery / Thumbnails**
  - [Résumé (Mission 019)](#résumé-mission-019)
  - [Tests ajoutés (Mission 019)](#tests-ajoutés-mission-019)
  - [État du projet (Mission 019)](#état-du-projet-mission-019)
- **Mission 018 — ComfyUI Application Settings**
  - [Résumé (Mission 018)](#résumé-mission-018)
  - [Tests ajoutés (Mission 018)](#tests-ajoutés-mission-018)
  - [État du projet (Mission 018)](#état-du-projet-mission-018)
- **Mission 017 — Dashboard Actions Wiring**
  - [Résumé (Mission 017)](#résumé-mission-017)
  - [Tests ajoutés (Mission 017)](#tests-ajoutés-mission-017)
  - [État du projet (Mission 017)](#état-du-projet-mission-017)
- **Mission 016 — Direct Project Folder Creation**
  - [Résumé (Mission 016)](#résumé-mission-016)
  - [Tests ajoutés (Mission 016)](#tests-ajoutés-mission-016)
  - [État du projet (Mission 016)](#état-du-projet-mission-016)
- **Mission 015 — Enlarged Image Preview**
  - [Résumé (Mission 015)](#résumé-mission-015)
  - [Statistiques (Mission 015)](#statistiques-mission-015)
  - [Évolutions architecturales (Mission 015)](#évolutions-architecturales-mission-015)
  - [Décisions de conception (Mission 015)](#décisions-de-conception-mission-015)
  - [Correction en revue finale (Mission 015)](#correction-en-revue-finale-mission-015)
  - [Hors périmètre (Mission 015)](#hors-périmètre-mission-015)
  - [Tests ajoutés (Mission 015)](#tests-ajoutés-mission-015)
  - [Prochaines étapes (Mission 015)](#prochaines-étapes-mission-015)
  - [État du projet (Mission 015)](#état-du-projet-mission-015)
- **Mission 014 — Validation post-génération avant enregistrement**
  - [Résumé (Mission 014)](#résumé-mission-014)
  - [Statistiques (Mission 014)](#statistiques-mission-014)
  - [Évolutions architecturales (Mission 014)](#évolutions-architecturales-mission-014)
  - [Décisions de conception (Mission 014)](#décisions-de-conception-mission-014)
  - [Correction en revue finale (Mission 014)](#correction-en-revue-finale-mission-014)
  - [Hors périmètre (Mission 014)](#hors-périmètre-mission-014)
  - [Tests ajoutés (Mission 014)](#tests-ajoutés-mission-014)
  - [Prochaines étapes (Mission 014)](#prochaines-étapes-mission-014)
  - [État du projet (Mission 014)](#état-du-projet-mission-014)
- **Mission 013 — Verticale minimale Inference**
  - [Résumé (Mission 013)](#résumé-mission-013)
  - [Statistiques (Mission 013)](#statistiques-mission-013)
  - [Évolutions architecturales (Mission 013)](#évolutions-architecturales-mission-013)
  - [Décisions de conception (Mission 013)](#décisions-de-conception-mission-013)
  - [Correction en revue finale (Mission 013)](#correction-en-revue-finale-mission-013)
  - [Hors périmètre (Mission 013)](#hors-périmètre-mission-013)
  - [Tests ajoutés (Mission 013)](#tests-ajoutés-mission-013)
  - [Prochaines étapes (Mission 013)](#prochaines-étapes-mission-013)
  - [État du projet (Mission 013)](#état-du-projet-mission-013)
- **Mission 012 — ComfyUI Engine minimal**
  - [Résumé (Mission 012)](#résumé-mission-012)
  - [Statistiques (Mission 012)](#statistiques-mission-012)
  - [Évolutions architecturales (Mission 012)](#évolutions-architecturales-mission-012)
  - [Décisions de conception (Mission 012)](#décisions-de-conception-mission-012)
  - [Correction en revue finale (Mission 012)](#correction-en-revue-finale-mission-012)
  - [Hors périmètre (Mission 012)](#hors-périmètre-mission-012)
  - [Tests ajoutés (Mission 012)](#tests-ajoutés-mission-012)
  - [Prochaines étapes (Mission 012)](#prochaines-étapes-mission-012)
  - [État du projet (Mission 012)](#état-du-projet-mission-012)
- **Mission 011 — Image Domain**
  - [Résumé (Mission 011)](#résumé-mission-011)
  - [Statistiques (Mission 011)](#statistiques-mission-011)
  - [Évolutions architecturales (Mission 011)](#évolutions-architecturales-mission-011)
  - [Décisions de conception (Mission 011)](#décisions-de-conception-mission-011)
  - [Correction en revue finale (Mission 011)](#correction-en-revue-finale-mission-011)
  - [Hors périmètre (Mission 011)](#hors-périmètre-mission-011)
  - [Tests ajoutés (Mission 011)](#tests-ajoutés-mission-011)
  - [Prochaines étapes (Mission 011)](#prochaines-étapes-mission-011)
  - [État du projet (Mission 011)](#état-du-projet-mission-011)
- **Mission 010 — Application Settings Domain**
  - [Résumé (Mission 010)](#résumé-mission-010)
  - [Statistiques (Mission 010)](#statistiques-mission-010)
  - [Évolutions architecturales (Mission 010)](#évolutions-architecturales-mission-010)
  - [Décisions de conception (Mission 010)](#décisions-de-conception-mission-010)
  - [Hors périmètre (Mission 010)](#hors-périmètre-mission-010)
  - [Tests ajoutés (Mission 010)](#tests-ajoutés-mission-010)
  - [Prochaines étapes (Mission 010)](#prochaines-étapes-mission-010)
  - [État du projet (Mission 010)](#état-du-projet-mission-010)
- **Mission 009 — Settings Domain (Workspace)**
  - [Résumé (Mission 009)](#résumé-mission-009)
  - [Statistiques (Mission 009)](#statistiques-mission-009)
  - [Évolutions architecturales (Mission 009)](#évolutions-architecturales-mission-009)
  - [Décisions de conception (Mission 009)](#décisions-de-conception-mission-009)
  - [Hors périmètre (Mission 009)](#hors-périmètre-mission-009)
  - [Tests ajoutés (Mission 009)](#tests-ajoutés-mission-009)
  - [Prochaines étapes (Mission 009)](#prochaines-étapes-mission-009)
  - [État du projet (Mission 009)](#état-du-projet-mission-009)
- **Mission 008 — Training Domain**
  - [Résumé (Mission 008)](#résumé-mission-008)
  - [Statistiques (Mission 008)](#statistiques-mission-008)
  - [Évolutions architecturales (Mission 008)](#évolutions-architecturales-mission-008)
  - [Décisions de conception (Mission 008)](#décisions-de-conception-mission-008)
  - [Hors périmètre (Mission 008)](#hors-périmètre-mission-008)
  - [Tests ajoutés (Mission 008)](#tests-ajoutés-mission-008)
  - [Prochaines étapes (Mission 008)](#prochaines-étapes-mission-008)
  - [État du projet (Mission 008)](#état-du-projet-mission-008)
- **Mission 007 — Workflow Domain**
  - [Résumé (Mission 007)](#résumé-mission-007)
  - [Statistiques (Mission 007)](#statistiques-mission-007)
  - [Évolutions architecturales (Mission 007)](#évolutions-architecturales-mission-007)
  - [Décisions de conception (Mission 007)](#décisions-de-conception-mission-007)
  - [Tests ajoutés (Mission 007)](#tests-ajoutés-mission-007)
  - [Prochaines étapes (Mission 007)](#prochaines-étapes-mission-007)
  - [État du projet (Mission 007)](#état-du-projet-mission-007)
- **Mission 006 — Model Domain**
  - [Résumé (Mission 006)](#résumé-mission-006)
  - [Statistiques (Mission 006)](#statistiques-mission-006)
  - [Évolutions architecturales (Mission 006)](#évolutions-architecturales-mission-006)
  - [Décisions de conception (Mission 006)](#décisions-de-conception-mission-006)
  - [Tests ajoutés (Mission 006)](#tests-ajoutés-mission-006)
  - [Prochaines étapes (Mission 006)](#prochaines-étapes-mission-006)
  - [État du projet (Mission 006)](#état-du-projet-mission-006)
- **Mission 005 — Prompt Domain**
  - [Résumé (Mission 005)](#résumé-mission-005)
  - [Statistiques (Mission 005)](#statistiques-mission-005)
  - [Évolutions architecturales (Mission 005)](#évolutions-architecturales-mission-005)
  - [Décisions de conception (Mission 005)](#décisions-de-conception-mission-005)
  - [Tests ajoutés (Mission 005)](#tests-ajoutés-mission-005)
  - [Prochaines étapes (Mission 005)](#prochaines-étapes-mission-005)
  - [État du projet (Mission 005)](#état-du-projet-mission-005)
- **Mission 004 — LoRA Domain**
  - [Résumé (Mission 004)](#résumé-mission-004)
  - [Statistiques (Mission 004)](#statistiques-mission-004)
  - [Évolutions architecturales (Mission 004)](#évolutions-architecturales-mission-004)
  - [Décisions de conception (Mission 004)](#décisions-de-conception-mission-004)
  - [Tests ajoutés (Mission 004)](#tests-ajoutés-mission-004)
  - [Prochaines étapes (Mission 004)](#prochaines-étapes-mission-004)
  - [État du projet (Mission 004)](#état-du-projet-mission-004)
- **Mission 003 — Dataset Domain**
  - [Résumé (Mission 003)](#résumé-mission-003)
  - [Statistiques (Mission 003)](#statistiques-mission-003)
  - [Évolutions architecturales (Mission 003)](#évolutions-architecturales-mission-003)
  - [Décisions de conception (Mission 003)](#décisions-de-conception-mission-003)
  - [Tests ajoutés (Mission 003)](#tests-ajoutés-mission-003)
  - [Prochaines étapes (Mission 003)](#prochaines-étapes-mission-003)
  - [État du projet (Mission 003)](#état-du-projet-mission-003)
- **Mission 002 — Character Domain**
  - [Résumé (Mission 002)](#résumé-mission-002)
  - [Statistiques (Mission 002)](#statistiques-mission-002)
  - [Évolutions architecturales (Mission 002)](#évolutions-architecturales-mission-002)
  - [Décisions de conception (Mission 002)](#décisions-de-conception-mission-002)
  - [Tests ajoutés (Mission 002)](#tests-ajoutés-mission-002)
  - [Prochaines étapes](#prochaines-étapes)
  - [État du projet (Mission 002)](#état-du-projet-mission-002)
- **Mission 001 — Blueprint Refactoring**
  - [Résumé de la mission](#résumé-de-la-mission)
  - [Statistiques de la mission](#statistiques-de-la-mission)
  - [Évolutions architecturales principales](#évolutions-architecturales-principales)
  - [Bugs corrigés](#bugs-corrigés)
  - [Tests ajoutés](#tests-ajoutés)
  - [Prochaines étapes (Mission 002)](#prochaines-étapes-mission-002)
  - [Améliorations UX futures](#améliorations-ux-futures)
  - [État du projet](#état-du-projet)

---

## v0.2-mission075 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 075 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 075)

L'audit mené après Mission 074 a révélé, par reproduction empirique directe (création, peuplement puis suppression réelles d'un Dataset/LoRA), que `DatasetManager.delete()`/`LoRAManager.delete()` — déjà protégés au niveau Domain-only depuis Mission 068 — ne supprimaient jamais le dossier physique privé de l'entité (`datasets/<id>/`, `models/loras/<id>/`) : une fuite se produisant sur le chemin **normal** de toute suppression, pas seulement en cas d'échec de persistence rare.

Contrairement aux Missions 068–074, cette mission introduit une suppression physique potentiellement irréversible et a donc suivi une phase de conception séparée, auditée puis explicitement validée par l'architecte avant tout code — audit portant sur la structure physique réelle de Dataset/LoRA, les primitives `WorkspaceStorage` existantes, et les précédents Missions 027/046/066/068.

**Stratégie retenue (Option C)** : déplacement atomique préalable du dossier vers une zone `.trash/` interne du Workspace (réutilisant `WorkspaceStorage.rename_folder()` de Mission 027 telle quelle) → mutation Domain selon le contrat Mission 068 → `WorkspaceManager.save()`. En cas d'échec de persistence, le rollback Domain s'exécute **toujours** en premier — instructions séquentielles qui ne peuvent elles-mêmes échouer — suivi d'une tentative indépendante de restauration filesystem ; si celle-ci échoue également (**double échec**), une `WorkspaceManagerError` enrichie est levée précisant que le Domain est sûr et où se trouve réellement le dossier dans `.trash/`, sur le modèle du précédent de `WorkspaceManager.rename()` (Mission 027). En cas de succès de persistence, le résidu dans `.trash/` est définitivement supprimé en best-effort via la nouvelle primitive `WorkspaceStorage.delete_folder()`, sans jamais rollbacker le Domain déjà persisté si ce nettoyage échoue.

L'audit a confirmé qu'un Dataset entièrement peuplé depuis la galerie Images n'a structurellement aucun dossier physique (cas normal, pas une corruption), et qu'un dossier LoRA supprimable ne peut jamais contenir un fichier partagé ni un fichier de la future bibliothèque LoRA centralisée : `LoRA.files` n'est jamais copié physiquement dans ce dossier (uniquement des références externes), `set_thumbnail()` étant l'unique site d'écriture de tout le projet.

`delete()` retourne désormais un `NamedTuple` par entité (`DatasetDeletionResult`/`LoRADeletionResult` — `deleted`/`cleanup_failed`/`residual_path`) au lieu d'un `bool` nu, même principe que `RemovalResult` de Mission 066 pour un problème structurellement identique. Le texte de confirmation de `DatasetsPage.delete_dataset()` a été mis à jour pour distinguer explicitement les images de galerie (qui survivent) des copies privées importées directement (supprimées avec le dataset).

Restent explicitement hors périmètre, non traités par cette mission : `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; `CharacterManager.delete()` (UI réellement cachée) ; le segfault Qt/PySide6 déjà documenté ; la future bibliothèque LoRA centralisée (seulement vérifiée pour compatibilité, non implémentée).

Changement limité à 5 fichiers de production (`src/infrastructure/storage/workspace_storage.py`, `src/managers/dataset_manager.py`, `src/managers/lora_manager.py`, `src/ui/pages/datasets_page.py`, `src/ui/pages/lora_page.py`), 3 fichiers de tests, plus le document de mission.

### Tests ajoutés (Mission 075)

- **22 tests nets nouveaux** : 9 au niveau `DatasetManagerPhysicalDeletionTest` et 10 au niveau `LoRAManagerPhysicalDeletionTest` (suppression normale avec dossier réel ; absence de dossier, cas normal ; échec du déplacement initial, abandon avant toute mutation ; échec `save()` restaurant le dossier à son emplacement d'origine avec son contenu exact ; **double échec** — `save()` et le renommage inverse échouent tous deux — Domain néanmoins restauré au même index avec `active_*_id`, dossier laissé dans `.trash/`, aucune autre entité touchée, erreur contenant l'information de récupération manuelle ; échec du nettoyage définitif après persistence réussie, jamais de rollback Domain ; retry réel ; non-impact sur une entité voisine ; collision de noms de transit) ; 3 au niveau Presentation (texte de confirmation Dataset mis à jour, warning affiché sur `cleanup_failed` pour Dataset et LoRA).
- **1355/1355 tests verts au total** (1333 précédents + 22 nets nouveaux) : non-régression complète sur `test_dataset_roundtrip.py` (103/103), `test_lora_roundtrip.py` (125/125), `test_training_roundtrip.py` (67/67, 3 assertions adaptées mécaniquement au nouveau type de retour) et `test_workspace_roundtrip.py` (97/97). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`DatasetManager`/`LoRAManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque, fichiers réels écrits/lus à chaque étape — **PASS, 19/19 assertions** sur 5 scénarios réels (suppression normale et rollback sur échec de persistence pour Dataset et LoRA, plus un flux Presentation réel).

### État du projet (Mission 075)

1355/1355 tests automatisés verts. Commit fonctionnel `3742d38` (`feat: transactional physical cleanup of Dataset/LoRA folders on deletion`), tag `v0.2-mission075`, GitHub Release publiée. Voir `docs/missions/MISSION_075.md` pour le détail complet.

---

## v0.2-mission074 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 074 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 074)

L'audit mené après Mission 073 a réévalué la dette regroupée depuis plusieurs missions sous l'intitulé unique « `CharacterManager.delete()`/`update()` — UI cachée, inatteignable ». Une vérification directe du code a confirmé que cette caractérisation reste exacte pour `delete()` (`CharactersPage.new_button`/`.delete_button`/`.list_widget` sont bien `setVisible(False)`, jamais réaffichés) mais **inexacte pour `update()`** : `CharactersPage.save_identity()`, branché sur `self.save_identity_button` — un bouton jamais caché, « Enregistrer l'identité » — appelait `CharacterManager.update()` sans aucune protection, ni au niveau Manager (pas même un `try` nu autour de `self._workspace_manager.save()`) ni au niveau Presentation. C'est le chemin d'édition principal et le plus utilisé de toute l'entité Character.

**Correction d'audit documentée** : `CharacterManager.delete()` reste inaccessible depuis l'UI réelle (confirmé) ; `CharacterManager.update()`, à l'inverse, est actif et accessible via le bouton « Enregistrer l'identité » — les deux méthodes ne doivent plus être regroupées sous une même dette « UI cachée » dans les audits futurs.

Un mini-audit contractuel dédié a confirmé que `update()` mute exactement 7 champs (`name`/`bio`/`description`/`character_lock`/`personality`/`interests`/`trigger_token`), ne touche aucun autre état (jamais `active_character_id`) et ne publie aucun événement, avant comme après cette mission — invariant vérifié par test plutôt que supposé. `CharacterManager.update()` reçoit désormais un rollback local exact : capture des 7 valeurs précédentes avant mutation, et en cas de `WorkspaceManagerError`, restauration simultanée des 7 champs sur le même objet `Character` avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée.

`CharactersPage.save_identity()` intercepte désormais `WorkspaceManagerError` et affiche `QMessageBox.critical()`. Une découverte architecturale a directement justifié le choix UX : `WorkspaceManager.save()` ne publie `WORKSPACE_SAVED` qu'après une écriture réussie, et en production tous les `update_X()` de Page — dont `CharactersPage.update_characters()` — y sont abonnés, ce qui resynchronise déjà silencieusement la fiche après un succès. Un échec ne publie jamais cet événement, donc `save_identity()` appelle désormais explicitement `update_characters()` dans son bloc `except`, resynchronisant les 7 widgets sur les valeurs restaurées — décision confirmée par lecture directe du wiring réel de `main_window.py`, pas seulement par analogie avec les précédents `DatasetsPage.rename_dataset()` (Mission 070) et `LoRAPage.save_metadata()` (Mission 073).

Restent explicitement hors périmètre, non traités par cette mission : `CharacterManager.delete()` (UI réellement cachée) ; `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA après suppression ; le segfault Qt/PySide6 déjà documenté.

Changement strictement limité à 2 fichiers de code (`src/managers/character_manager.py`, `src/ui/pages/characters_page.py`) et 1 fichier de tests, plus le document de mission.

### Tests ajoutés (Mission 074)

- **11 tests nets nouveaux** : 7 au niveau Manager (`CharacterManagerUpdateRollbackTest` — succès normal des 7 champs, échec `save()` restaurant les 7 champs simultanément sur le même objet, échec restaurant un seul champ modifié isolément afin de ne pas prouver le rollback uniquement sur le cas à 7 champs, aucun événement publié sur échec — invariant vérifié, `project.json` inchangé, un autre Character préexistant non concerné inchangé via `assertIs`, retry réellement neuf après rollback persistant effectivement) ; 4 au niveau Presentation (`CharactersPageIdentityPersistenceFailureTest` — erreur affichée et Character restant présent/visible, Domain restauré **et** les 7 widgets resynchronisés sur les valeurs restaurées via `update_characters()`, `project.json` inchangé, retry réel effectif depuis la Page).
- **1333/1333 tests verts au total** (1322 précédents + 11 nets nouveaux) : non-régression complète sur `test_character_roundtrip.py` (62/62). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `CharactersPage`/`CharacterManager`/`WorkspaceManager` réels contre un Workspace temporaire réel sur disque — **PASS, 9/9 assertions** sur 3 scénarios réels (update normal, échec de persistence avec rollback mémoire/disque/widgets vérifié, retry réel).

### État du projet (Mission 074)

1333/1333 tests automatisés verts. Commit fonctionnel `ec15312` (`feat: rollback CharacterManager.update() identity on persistence failure`), tag `v0.2-mission074`, GitHub Release publiée. Voir `docs/missions/MISSION_074.md` pour le détail complet.

---

## v0.2-mission073 — 2026-08-27

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 073 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 073)

L'audit mené après Mission 072 a confirmé que `LoRAManager.update()` (les 4 métadonnées texte `engine`/`architecture`/`trigger_word`/`version`, mutées simultanément) mutait ces champs en mémoire puis appelait `WorkspaceManager.save()` **sans aucun `try/except`**. `LoRAPage.save_metadata()`, son unique site d'appel Presentation, n'interceptait rien non plus. Un échec de `save()` laissait les 4 champs mutés en mémoire sans persistance ni message d'erreur — le même motif déjà corrigé pour `create()`/`delete()`/les mutations scalaires par Missions 068/070/071/072, jamais traité pour cette méthode multi-champs (explicitement exclue du périmètre de Mission 070 du fait de son contrat à 4 champs simultanés).

Un mini-audit contractuel dédié a confirmé que `update()` ne touche aucun autre état que les 4 champs (jamais `active_lora_id`, jamais `name`/`files`/`thumbnail`) et ne publie aucun événement, avant comme après cette mission — même contrat que `CharacterManager.update()`, vérifié par test plutôt que supposé. `LoRAManager.update()` reçoit désormais un rollback local exact : capture des 4 valeurs précédentes avant mutation, et en cas de `WorkspaceManagerError`, restauration simultanée des 4 champs sur le même objet `LoRA` avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée.

`LoRAPage.save_metadata()` intercepte désormais `WorkspaceManagerError` et affiche `QMessageBox.critical()`. Contrairement aux missions create()/delete(), cette mission nécessitait une décision UX explicite : les 4 `QLineEdit` de métadonnées sont des champs de saisie directe qui, sans rafraîchissement, continueraient d'afficher les valeurs rejetées après un échec alors que le Domain aurait été restauré. `save_metadata()` appelle désormais `update_loras()` dans son bloc `except`, resynchronisant les 4 widgets sur les valeurs restaurées — décision directement dérivée du précédent déjà établi par `DatasetsPage.rename_dataset()` (Mission 070), pas une nouvelle décision produit.

Restent explicitement hors périmètre, non traités par cette mission : `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA après suppression ; `CharacterManager.delete()`/`update()` (UI cachée, inatteignable) ; le segfault Qt/PySide6 déjà documenté.

Changement strictement limité à 2 fichiers de code (`src/managers/lora_manager.py`, `src/ui/pages/lora_page.py`) et 1 fichier de tests, plus le document de mission.

### Tests ajoutés (Mission 073)

- **11 tests nets nouveaux** : 7 au niveau Manager (`LoRAManagerMetadataRollbackTest` — succès normal des 4 champs, échec `save()` restaurant les 4 champs simultanément sur le même objet, échec restaurant un seul champ modifié isolément afin de ne pas prouver le rollback uniquement sur le cas multi-champs, aucun événement publié sur échec — invariant vérifié, `project.json` inchangé, une LoRA préexistante non concernée inchangée via `assertIs`, retry réellement neuf après rollback persistant effectivement) ; 4 au niveau Presentation (`LoRAPageMetadataPersistenceFailureTest` — erreur affichée et LoRA restant visible/sélectionnée, Domain restauré **et** widgets resynchronisés sur les valeurs restaurées via `update_loras()`, `project.json` inchangé, retry réel effectif depuis la Page).
- **1322/1322 tests verts au total** (1311 précédents + 11 nets nouveaux) : non-régression complète sur `test_lora_roundtrip.py` (114/114). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `LoRAPage`/`LoRAManager`/`WorkspaceManager`/`CharacterManager` réels contre un Workspace temporaire réel sur disque — **PASS, 10/10 assertions** sur 3 scénarios réels (update normal, échec de persistence avec rollback mémoire/disque vérifié, retry réel).

### État du projet (Mission 073)

1322/1322 tests automatisés verts. Commit fonctionnel `add35c1` (`feat: rollback LoRAManager.update() metadata on persistence failure`), tag `v0.2-mission073`, GitHub Release publiée. Voir `docs/missions/MISSION_073.md` pour le détail complet.

---

## v0.2-mission072 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 072 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 072)

L'audit mené après Mission 071 a révélé que les 7 méthodes `create()` (`DatasetManager`, `CharacterManager`, `ModelManager`, `WorkflowManager`, `LoRAManager`, `TrainingManager`, `PromptManager`) sont rigoureusement isomorphes : construction de l'entité → `append()` dans la collection Domain parente → `WorkspaceManager.save()` **sans aucun `try/except`** → publication de l'événement de succès. Aucun des 9 sites d'appel Presentation n'interceptait quoi que ce soit autour de l'appel. Une reproduction empirique réelle (`QApplication` réel, `DatasetsPage` réelle, `WorkspaceStorage.save` mocké, déclenchement via `button.clicked.emit()`) a confirmé qu'un échec laisse l'entité créée résidente en mémoire alors que `project.json` n'a jamais été modifié, sans aucun message d'erreur — le processus ne crashe pas (PySide6 sans `excepthook` personnalisé imprime et continue), mais une sauvegarde ultérieure totalement indépendante persiste alors silencieusement cette création jamais confirmée. C'était la dernière famille homogène et la plus largement utilisée du triptyque create/update/delete encore non sécurisée.

Chacune des 7 méthodes reçoit désormais le même contrat de rollback local déjà établi par Missions 068/070/071 : en cas de `WorkspaceManagerError`, la même instance tout juste ajoutée est retirée de sa collection avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée. Les 9 handlers Presentation correspondants interceptent `WorkspaceManagerError` et affichent `QMessageBox.critical()` ; aucun rafraîchissement de liste n'est nécessaire, l'entité n'ayant jamais été ajoutée visuellement.

Une découverte pendant l'implémentation : `character_manager.py` et `characters_page.py` n'importaient jamais `WorkspaceManagerError` — le seul Manager/Page du projet dans ce cas, ajout strictement nécessaire au périmètre, détecté immédiatement par un `NameError` lors des tests et corrigé avant toute autre action.

Restent explicitement hors périmètre, non traités par cette mission : `LoRAManager.update()` (4 métadonnées) ; `DatasetManager.remove_images()`/`LoRAManager.add_files()`/`remove_files()` ; `SettingsManager.update()` ; `CharacterManager.delete()`/`update()` (UI cachée, inatteignable) ; le segfault Qt/PySide6 déjà documenté.

Changement strictement limité à 7 Managers, 8 Pages et leurs fichiers de tests correspondants (24 fichiers au total, incluant le nouveau document de mission).

### Tests ajoutés (Mission 072)

- **66 tests nets nouveaux** : 42 au niveau Manager (6 par entité × 7 — succès normal, échec `save()` retirant l'entité fantôme au même objet, aucun événement de succès publié, `project.json` inchangé, retry réellement neuf après rollback persistant effectivement, entité préexistante non concernée inchangée via `assertIs`) ; 24 au niveau Presentation (3 par site × 8, `PromptsPage` comptant pour 5 du fait de ses 2 sites — erreur affichée et liste UI vide/inchangée, `project.json` inchangé, retry réel effectif) ; 1 test `InferencePage` (style mock existant, vérifiant que `select()`/`update_text()` ne sont jamais appelés sur l'échec).
- **1311/1311 tests verts au total** (1245 précédents + 66 nets nouveaux) : non-régression complète sur les 8 fichiers de tests concernés (`test_dataset_roundtrip.py` + `test_character_roundtrip.py` + `test_model_roundtrip.py` + `test_workflow_roundtrip.py` + `test_lora_roundtrip.py` + `test_training_roundtrip.py` + `test_prompt_roundtrip.py` + `test_inference_page.py`). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`CharactersPage`/`ModelsPage`/`WorkflowsPage`/`LoRAPage`/`TrainingPage`/`PromptsPage` réelles contre des Workspaces temporaires réels sur disque — **PASS, 38/38 assertions** sur 7 scénarios réels (une création normale, un échec de persistence avec rollback mémoire/disque vérifié, un retry réel — pour chacune des 7 entités).

### État du projet (Mission 072)

1311/1311 tests automatisés verts. Commit fonctionnel `2319b0b` (`feat: rollback Domain-only create() on persistence failure`, suivi du correctif documentaire `e93af7c`), tag `v0.2-mission072`, GitHub Release publiée. Voir `docs/missions/MISSION_072.md` pour le détail complet.

---

## v0.2-mission071 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 071 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 071)

L'audit mené après Mission 070 a révélé que Mission 068 (« Rollback Domain-Only Deletions on Persistence Failure ») énonce explicitement son périmètre comme portant sur **cinq** Managers — `DatasetManager.delete()`, `LoRAManager.delete()`, `ModelManager.delete()`, `TrainingManager.delete()`, `WorkflowManager.delete()` — et ne mentionne `PromptManager.delete()` nulle part, y compris dans sa section « Hors périmètre », qui liste pourtant explicitement `CharacterManager.delete()` comme exclusion volontaire. `PromptManager.delete()` n'avait donc jamais été analysé ni corrigé par Mission 068 : un oubli d'audit, non une exclusion délibérée. Une reproduction empirique a confirmé qu'il suivait exactement le motif pré-Mission 068 : retrait de `character.prompts` en mémoire → `WorkspaceManager.save()` sans aucun `try/except`, laissant une suppression fantôme en mémoire silencieusement persistable par une sauvegarde ultérieure totalement indépendante en cas d'échec.

`PromptManager.delete()` reçoit désormais le contrat de rollback **rigoureusement identique** aux cinq Managers déjà corrigés par Mission 068 : capture de l'index d'origine et de l'ancien `active_prompt_id`, retrait, `save()`, et en cas de `WorkspaceManagerError`, réinsertion du même objet Prompt à son index exact et restauration de `active_prompt_id`, avant de relever l'exception — aucun snapshot Workspace, aucune opération filesystem, aucune abstraction transactionnelle partagée. `PromptsPage.delete_prompt()` intercepte `WorkspaceManagerError` et affiche `QMessageBox.critical()` ; aucun rafraîchissement manuel de `prompt_list` n'est nécessaire, la ligne n'étant retirée que réactivement via `PROMPT_DELETED`, jamais publié en cas d'échec.

Restent explicitement hors périmètre, non traités par cette mission : `create()` Domain-only (6 entités) ; `LoRAManager.update()` ; `SettingsManager.update()` ; fichiers/dossiers physiques orphelins Dataset/LoRA ; segfault Qt/PySide6 ; `CharacterManager.delete()` ; toute abstraction transactionnelle générique.

Changement strictement limité à `PromptManager.delete()`, `PromptsPage.delete_prompt()` et leurs fichiers de tests correspondants (4 fichiers au total, incluant le nouveau document de mission).

### Tests ajoutés (Mission 071)

- **10 tests nets nouveaux** : au niveau Manager (`PromptManagerDeleteRollbackTest`, 6 tests) — succès normal ; échec `save()` restaurant le même objet à l'index exact (`assertIs`) ; `active_prompt_id` restauré ; un `active_prompt_id` pointant vers un autre Prompt reste inchangé ; `project.json` inchangé octet pour octet après échec ; retry après échec constituant une tentative réellement neuve. Au niveau Presentation (`PromptsPageDeletePersistenceFailureTest`, 4 tests) — erreur affichée et Prompt toujours présent/sélectionné ; `project.json` inchangé ; retry réel effectif ; suppression tentée avec un brouillon dirty (Discard puis échec) préservant le texte édité et l'état dirty.
- **1245/1245 tests verts au total** (1235 précédents + 10 nets nouveaux) : 109/109 non-régression complète sur `test_prompt_roundtrip.py`, 3.6s. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction.
- Smoke test Qt réel, exécuté par Claude, `PromptsPage`/`PromptManager`/`WorkspaceManager`/`CharacterManager` réels contre un Workspace temporaire réel sur disque — **PASS, 24/24 assertions** sur trois scénarios réels : suppression normale, échec de persistence + retry, brouillon dirty préservé après échec de suppression.
- Un incident de test auto-détecté et corrigé pendant l'implémentation est documenté dans `docs/missions/MISSION_071.md` (section 11) : un mock initial sans effet sur une méthode jamais appelée par le code réel a laissé s'exécuter un vrai dialogue Qt non mocké pendant ~32 minutes ; corrigé par adoption de l'idiome de mock déjà établi ailleurs dans le même fichier de tests.

### État du projet (Mission 071)

1245/1245 tests automatisés verts. Commit fonctionnel `33101ef9bbe1628a6c6c0e48405d8787b330d31c` (`feat: rollback PromptManager.delete() on persistence failure`), tag `v0.2-mission071`, GitHub Release publiée. Voir `docs/missions/MISSION_071.md` pour le détail complet.

---

## v0.2-mission070 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 070 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 070)

L'audit mené après Mission 069, puis un mini-audit contractuel dédié, ont démontré empiriquement qu'un groupe homogène de 9 méthodes Domain-only (`DatasetManager.update_name()`, `LoRAManager.update_name()`, `ModelManager.update_name()`/`update_file_path()`, `TrainingManager.update_name()`, `WorkflowManager.update_name()`/`update_file_path()`, `PromptManager.update_name()`/`update_text()`) mutent un scalaire **avant** `WorkspaceManager.save()`, sans aucun rollback en cas d'échec de persistence. Deux conséquences concrètes ont été reproduites : une mutation « fantôme » reste résidente en mémoire après un échec, silencieusement persistable par un `save()` ultérieur sans rapport ; et le garde d'idempotence préexistant (`if old == new: return False`), légitime pour éviter un `save()` redondant sur une valeur déjà persistée, neutralisait également tout retry identique après un premier échec — la valeur en mémoire ayant déjà été mutée, un second appel avec la même valeur ne relevait même plus l'exception, il retournait silencieusement `False` sans jamais retenter `save()`.

Un cas prioritaire distinct a également été isolé et corrigé : `PromptsPage.on_prompt_selection_changed()`, où un changement de Prompt avec un brouillon dirty et un choix « Enregistrer » qui échoue laissait Qt avec une sélection visuelle déjà avancée alors que `active_prompt_id`/`_loaded_prompt_id` restaient bloqués sur l'ancien Prompt — une divergence UI/Domain réelle. Le correctif réutilise **exactement** le mécanisme de restauration visuelle déjà existant pour le choix Cancel (`blockSignals(True)` → `setCurrentItem(previous)` → `blockSignals(False)` → synchronisation du bouton Supprimer), sans réécrire le système dirty-state de Missions 038/069.

Chacune des 9 méthodes reçoit désormais le même contrat de rollback local : capture de l'ancienne valeur, mutation, `save()`, et en cas de `WorkspaceManagerError`, restauration exacte de l'ancienne valeur sur le même objet avant de relever l'exception — aucun snapshot Workspace global, aucun mécanisme filesystem, aucune abstraction transactionnelle partagée, chaque Manager implémentant son propre rollback local comme pour Missions 066/067/068. Les 10 handlers Presentation correspondants interceptent `WorkspaceManagerError` et affichent `QMessageBox.critical()` : pour les 6 renommages, le refresh `update_*()` déjà existant de la Page redessine automatiquement le widget avec l'ancienne valeur (aucune restauration manuelle) ; pour les 2 chemins de fichiers (Model/Workflow), le widget concerné n'est jamais pré-muté visuellement (peuplé uniquement par le refresh d'événement, jamais directement par le picker), un simple `try/except` suffit.

Restent explicitement hors périmètre, non traités par cette mission : `LoRAManager.update()` et ses 4 métadonnées (cycle Presentation par bouton multi-champs, contrat structurellement distinct des 9 autres méthodes) ; les créations Domain-only (candidat futur important, non prédéterminé) ; `DatasetManager.remove_images()` ; `LoRAManager.add_files()`/`remove_files()` ; `CharacterManager.update()` (UI cachée, inatteignable) ; la miniature LoRA physique potentiellement orpheline après remplacement ; le segfault Qt/PySide6 déjà documenté ; toute abstraction transactionnelle générique.

Changement strictement limité à 6 Managers, 6 Pages et leurs fichiers de tests correspondants (19 fichiers au total, incluant le nouveau document de mission).

### Tests ajoutés (Mission 070)

- **56 tests nets nouveaux**, répartis sur les 6 entités concernées : pour chacune des 9 méthodes Manager — succès normal ; échec `save()` restaurant l'ancienne valeur exacte sur le même objet (identité vérifiée par `assertIs`) ; `project.json` inchangé octet pour octet après échec ; aucun événement de succès publié ; retry avec la même valeur précédemment refusée constituant une tentative réelle après rollback (garde d'idempotence toujours valide sur une valeur réellement persistée). Pour les 6 renommages Presentation : erreur affichée, widget restauré à l'ancienne valeur via le refresh existant, retry ultérieur réellement persisté. Pour les 2 chemins de fichiers : erreur affichée, aucune divergence visuelle à corriger. Pour `PromptsPage.on_prompt_selection_changed()` : scénario complet (brouillon dirty → sélection d'un autre Prompt → Save → échec → sélection visuelle restaurée → `active_prompt_id`/`_loaded_prompt_id` inchangés → texte utilisateur conservé → `_dirty=True` → `Prompt.text` rollbacké → `project.json` inchangé → retry ultérieur réussi). Pour `PromptsPage.save_text()` (troisième site d'appel réel de `update_text()`) : erreur affichée, aucune mutation fantôme.
- **1235/1235 tests verts au total** (1179 précédents + 56 nets nouveaux) : 457/457 non-régression sur les 8 fichiers de tests concernés (`test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_model_roundtrip.py` + `test_workflow_roundtrip.py` + `test_training_roundtrip.py` + `test_prompt_roundtrip.py` + `test_main_window_new_project.py` + `test_main_window_rename_project.py`). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`ModelsPage`/`WorkflowsPage`/`TrainingPage`/`PromptsPage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 40/40 assertions** sur sept scénarios réels : les 6 renommages, les 2 chemins de fichiers Model/Workflow, et le cas complet Prompt → Prompt (brouillon dirty, Save en échec, sélection visuelle restaurée, retry ultérieur réussi).

### État du projet (Mission 070)

1235/1235 tests automatisés verts. Commit fonctionnel `a9e162473379c8c54fa214fdcda423e1580a1c4d` (`feat: rollback scalar Domain-only mutations on persistence failure`), tag `v0.2-mission070`, GitHub Release publiée. Voir `docs/missions/MISSION_070.md` pour le détail complet.

---

## v0.2-mission069 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 069 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 069)

L'audit mené après Mission 068 avait révélé, par reproduction Python réelle, qu'un brouillon `PromptsPage` non sauvegardé était silencieusement perdu lors d'un `MainWindow.new_project()`/`open_project()` : `WorkspaceManager.create()`/`.open()` remplacent `current_workspace` **avant** de publier `WORKSPACE_CREATED`/`WORKSPACE_OPENED`, événements auxquels `PromptsPage.reset_for_context_change()` est abonné — au moment où ce handler s'exécute, le contexte a déjà changé, rendant tout Save ou Cancel structurellement impossibles à ce stade. Mission 038 protégeait déjà la navigation prompt-à-prompt et la suppression via un dialogue Save/Discard/Cancel (`_confirm_discard_before_switch()`), mais jamais les deux seuls chemins réellement atteignables par un utilisateur qui détruisent le contexte Workspace lui-même.

Mission 069 introduit `PromptsPage.confirm_context_change() -> bool`, seule addition à l'API de la Page, réutilisant verbatim le dialogue existant de Mission 038 sans dupliquer sa logique. Sans brouillon dirty, la méthode retourne `True` immédiatement, sans aucun dialogue — New/Open se comporte exactement comme avant. Avec un brouillon dirty : **Cancel** retourne `False` sans la moindre mutation (Workspace, Prompt actif, texte de l'éditeur et `_dirty` restent strictement inchangés, le changement de projet est entièrement abandonné) ; **Discard** retourne `True` sans persister, laissant `reset_for_context_change()` assurer seul le nettoyage une fois le nouveau Workspace chargé ; **Save** appelle `prompt_manager.update_text()` pendant que l'**ancien** Workspace est encore actif — en cas de succès, persistance réelle dans l'ancien projet puis `True` ; en cas d'échec (`WorkspaceManagerError`), `QMessageBox.critical()` est affiché, `_dirty` reste `True`, et la méthode retourne `False` — un échec de persistence ne permet jamais au changement de Workspace de continuer.

`MainWindow.new_project()`/`open_project()` reçoivent chacun un unique appel à `self.prompts_page.confirm_context_change()`, inséré après l'acceptation du sélecteur (`NewProjectDialog`/`QFileDialog.getExistingDirectory`) et avant tout appel à `workspace_manager.create()`/`.open()`. Si le sélecteur est annulé par l'utilisateur, le guard n'est jamais invoqué — aucun dialogue dirty-state superflu dans ce cas. Aucun framework générique de dirty-state/veto n'a été introduit : `PromptsPage` reste aujourd'hui la seule Page concernée par ce mécanisme.

Restent explicitement hors périmètre, non traités par cette mission : le défaut préexistant de `on_prompt_selection_changed()` (un `update_text()` en échec pendant un changement prompt→prompt n'est pas intercepté, `_dirty` reste bloqué à `True` sans message, avec un risque de divergence entre la sélection visuelle Qt et la sélection Domain) ; le cas `_dirty=True` sans Prompt actif (texte du Prompt Assistant jamais rattaché, `update_text()` y est un no-op silencieux hérité de Mission 038) ; toute protection lors de la fermeture générale de l'application (`closeEvent()` ne touche aujourd'hui ni `workspace_manager` ni `PromptsPage`) ; et les créations Domain-only sans rollback, candidat A distinct conservé pour un audit futur.

Changement strictement limité à `src/ui/pages/prompts_page.py` et `src/ui/main_window.py`.

### Tests ajoutés (Mission 069)

- **17 tests nets nouveaux** : `PromptsPageConfirmContextChangeTest` (5, dans `test_prompt_roundtrip.py`) — pas de dirty → `True` sans dialogue ; Save réussi → texte persisté dans l'ancien Workspace, `True`, `_dirty=False` ; Discard → `True`, rien persisté ; Cancel → `False`, tout inchangé (Workspace, Prompt actif, texte éditeur, `_dirty`) ; Save en échec → `QMessageBox.critical` affiché, `False`, `_dirty` toujours `True`, `project.json` inchangé. `MainWindowConfirmContextChangeTest` (12, dans `test_main_window_new_project.py`, réel `MainWindow` avec deux dossiers de projet réels) — `new_project()`/`open_project()` × Save/Discard/Cancel avec persistance/absence de persistance vérifiée réellement dans l'ancien `project.json` ; guard retournant `False` → `create()`/`open()` jamais appelé ; picker annulé → guard jamais appelé ; ordre d'exécution guard-avant-`create()`/`open()` vérifié explicitement.
- **1179/1179 tests verts au total** (1162 précédents + 17 nets nouveaux) : 112/112 non-régression sur `test_prompt_roundtrip.py` + `test_main_window_new_project.py` + `test_main_window_rename_project.py`. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `MainWindow`/`PromptsPage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 24/24 assertions** sur huit scénarios réels : New Project × Save/Discard/Cancel/échec de Save injecté/picker annulé, Open Project × Save/Discard/Cancel (avec un second projet réel indépendamment pré-créé).

### État du projet (Mission 069)

1179/1179 tests automatisés verts. Commit fonctionnel `896fb51c8af3024096984fa4075df008d696ea94` (`feat: protect PromptsPage draft before New/Open Project`), tag `v0.2-mission069`, GitHub Release publiée. Voir `docs/missions/MISSION_069.md` pour le détail complet.

---

## v0.2-mission068 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 068 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 068)

L'audit mené après Mission 067 a démontré empiriquement que les suppressions Domain-only (`DatasetManager.delete()`, `LoRAManager.delete()`, `ModelManager.delete()`, `TrainingManager.delete()`, `WorkflowManager.delete()`) suivent toutes le même ordre non transactionnel : retrait de l'objet de la collection en mémoire → `save()`, sans aucun rollback en cas d'échec de persistence. Motif rigoureusement identique dans les cinq Managers, confirmé par lecture directe du code. Conséquence : un échec de `save()` laisse la suppression appliquée en mémoire — l'objet a disparu de `character.datasets`/`character.loras`/`character.trainings`/`workspace.models`/`workspace.workflows` — sans que `project.json` ne soit modifié et sans qu'aucun événement de succès ne soit publié. L'utilisateur ne voit rien se passer (aucun message, aucun refresh de liste), mais l'entité est réellement absente du Domain ; une sauvegarde ultérieure sans rapport la persisterait alors silencieusement, sans nouvelle confirmation.

Mission 068 capture, pour chacun des cinq Managers, l'index exact de l'objet dans sa collection et la valeur courante de `active_*_id` avant toute mutation. Si `save()` échoue après le retrait, le même objet Python (jamais recréé) est réinséré à son index exact et `active_*_id` est restauré avant que l'exception `WorkspaceManagerError` ne soit relevée — un rollback purement local, Domain-only, sans aucune opération filesystem ni snapshot du Workspace entier, puisqu'aucun fichier n'est jamais en jeu dans ces cinq suppressions. La garde préexistante « Dataset référencé par une Training → suppression refusée » (Mission 062) continue de s'exécuter avant toute mutation et reste donc entièrement en dehors du nouveau chemin transactionnel — un Dataset dont la suppression est refusée par cette garde n'entre jamais dans le rollback.

Les cinq handlers Presentation correspondants (`DatasetsPage.delete_dataset()`, `LoRAPage.delete_lora()`, `ModelsPage.delete_model()`, `TrainingPage.delete_training()`, `WorkflowsPage.delete_workflow()`) interceptent désormais `WorkspaceManagerError` et affichent `QMessageBox.critical()` — la suppression n'est jamais présentée comme réussie. Aucun refresh UI supplémentaire n'a été nécessaire : la confirmation (Mission 062) et le retrait effectif de la liste ne se produisent que via l'événement `*_DELETED`, jamais publié en cas d'échec — l'entité n'a donc jamais été retirée visuellement, aucun état à reconstruire après l'erreur.

Cette mission complète la trilogie transactionnelle établie par Missions 066/067/068, chacune répondant à un profil de risque structurellement différent :
- **Mission 066** — suppression physique de fichiers : persistence-first (Domain → `save()` → suppression physique uniquement après succès), car une suppression physique est irréversible.
- **Mission 067** — mutation additive filesystem : rollback Domain + compensation best-effort des copies physiques réellement créées, car une copie physique peut être annulée sans jamais toucher un fichier préexistant.
- **Mission 068** — suppression Domain-only : rollback Domain local pur (réinsertion à l'index d'origine), sans aucune compensation filesystem puisqu'aucun fichier n'est jamais en jeu.

Changement strictement limité à `src/managers/{dataset_manager,lora_manager,model_manager,training_manager,workflow_manager}.py` et `src/ui/pages/{datasets_page,lora_page,models_page,training_page,workflows_page}.py`. `CharacterManager.delete()`/`CharactersPage.delete_character()` restent hors périmètre (suppression volontairement inaccessible dans l'UX actuelle) ; créations, renommages, modifications scalaires et associations/désassociations Domain-only restent également hors périmètre — candidats distincts, non traités ici.

### Tests ajoutés (Mission 068)

- **41 tests nets nouveaux**, répartis à l'identique sur les cinq entités : `DatasetManagerDeleteRollbackTest` (7, avec un test dédié vérifiant que la garde Training bloque toujours la suppression avant même que `save()` ne soit tenté) + `DatasetsPageDeleteConfirmationTest` (+2) dans `test_dataset_roundtrip.py` ; `LoRAManagerDeleteRollbackTest` (6) + `LoRAPageDeleteConfirmationTest` (+2) dans `test_lora_roundtrip.py` ; `ModelManagerDeleteRollbackTest` (6) + `ModelsPageDeleteConfirmationTest` (+2) dans `test_model_roundtrip.py` ; `TrainingManagerDeleteRollbackTest` (6, avec vérification explicite que `dataset_id` reste intact après rollback) + `TrainingPageDeleteConfirmationTest` (+2) dans `test_training_roundtrip.py` ; `WorkflowManagerDeleteRollbackTest` (6) + `WorkflowsPageDeleteConfirmationTest` (+2) dans `test_workflow_roundtrip.py`. Chaque suite Manager couvre : succès normal ; échec `save()` restaurant l'objet à son index exact (identité vérifiée par `assertIs`) sans publier d'événement de succès ; `active_*_id` restauré ; `active_*_id` non lié jamais touché ; `project.json` inchangé octet pour octet après échec ; retry réellement neuf après un premier échec.
- **1162/1162 tests verts au total** (1121 précédents + 41 nets nouveaux) : 289/289 sur les cinq fichiers de tests concernés, y compris l'intégralité des suites de non-régression Mission 062 (confirmation avant suppression) et Mission 063 (bouton synchronisé avec la sélection) déjà existantes. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `DatasetsPage`/`LoRAPage`/`ModelsPage`/`TrainingPage`/`WorkflowsPage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 24/24 assertions** sur cinq scénarios : Dataset (échec de persistence injecté → erreur affichée, dataset toujours présent avec la même instance, `active_dataset_id` restauré, `project.json` inchangé ; garde Training vérifiée toujours active sur ce même dataset ; retry réel réussi après retrait de la Training bloquante), LoRA/Model/Workflow/Training (même principe).

### État du projet (Mission 068)

1162/1162 tests automatisés verts. Commit fonctionnel `969d70c4c0133e95045b0bfeda8822dbc148e3f1` (`feat: rollback Domain-only deletions on persistence failure`), tag `v0.2-mission068`, GitHub Release publiée. Voir `docs/missions/MISSION_068.md` pour le détail complet.

---

## v0.2-mission067 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 067 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 067)

Le mini-audit transactionnel mené avant Mission 066 avait identifié un second défaut, structurellement distinct de celui résolu par cette mission : les mutations **additives** (`WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`) copiaient physiquement un fichier puis mutaient le Domain **avant** `save()`, sans aucun rollback en cas d'échec de persistence. Conséquences démontrées : copie physique orpheline, mutation Domain silencieusement persistable par un `save()` ultérieur sans rapport, et pour `InferencePage._on_accept_clicked()` (dont l'image pending est déjà interne au Workspace, sous `outputs/`) un cas aggravé — un second clic sur « Accepter » après un échec obtenait silencieusement `added=0` sans jamais retenter la persistence, et un « Rejeter » après un « Accepter » échoué pouvait supprimer physiquement le fichier pending tout en laissant une référence Domain fantôme, persistable plus tard sans le moindre avertissement.

Mission 067 complète le contrat transactionnel introduit par Mission 066 pour ce cas structurellement différent : `filesystem → Domain → persistence`. Pour chaque nouvelle entrée, une comparaison entre le chemin effectif résolu et la source résolue détermine si une vraie copie physique a été créée ou s'il s'agit d'un passthrough (source déjà interne au Workspace, retournée telle quelle) — cette même comparaison protège la compensation de ne jamais supprimer un fichier préexistant. En cas d'échec de `save()`, le Domain est restauré à son état antérieur exact (mêmes objets, même ordre) et chaque copie réellement créée par cet appel est supprimée en best-effort, jamais un passthrough ; l'exception de persistence d'origine reste la cause première même si le nettoyage échoue à son tour (mirroir exact du précédent déjà établi par `WorkspaceManager.rename()`, Mission 027). Rollback implémenté localement et indépendamment dans chacun des trois Managers, sans framework transactionnel partagé (mirroir du principe déjà établi par Mission 063).

Les 5 handlers Presentation concernés (`ImagesPage.import_images()`, `DatasetsPage.import_images()`/`add_images_from_gallery()`, `LoRAPage.choose_thumbnail()`) interceptent désormais `WorkspaceManagerError` et affichent `QMessageBox.critical()` — l'action n'est jamais présentée comme réussie. Cas prioritaire `InferencePage._on_accept_clicked()` : un Accept échoué n'appelle plus `_clear_pending()` ni ne réactive `generate_button`/les contrôles de référence — la page reste exactement dans l'état pré-Accept (image toujours visible, Accepter/Rejeter/Régénérer toujours disponibles). Grâce au rollback du Manager, un second « Accepter » retente réellement la persistence (l'entrée n'existe plus en mémoire, corrigeant le faux `added=0` silencieux précédent), et un « Rejeter » après un « Accepter » échoué ne laisse plus aucune référence fantôme — vérifié y compris après un `save()` ultérieur sans rapport, le critère essentiel de cette mission.

Changement strictement limité à `src/managers/{workspace_manager,dataset_manager,lora_manager}.py` et `src/ui/pages/{images_page,datasets_page,lora_page,inference_page}.py`. Explicitement hors périmètre, non modifié : les ~30 handlers Type 1 sans opération filesystem, `WorkspaceManager.remove_images()` (déjà traité par Mission 066), A-4 (libellés de liste obsolètes après renommage), et la politique préexistante laissant l'ancienne miniature LoRA physique sur disque après un remplacement **réussi** — dette distincte, non traitée ici.

### Tests ajoutés (Mission 067)

- **20 tests nets nouveaux** : `WorkspaceManagerAddImagesCopyTest` (5) — échec `save()` + vraie copie (rollback + copie supprimée) ; échec `save()` + passthrough (jamais supprimé, reproduisant le cas `InferencePage`) ; retry après échec (tentative réellement neuve, aucun suffixe parasite) ; échec de compensation (erreur d'origine préservée, information orpheline jointe) ; lot multi-fichiers (préexistants jamais touchés, identité d'objet préservée). `DatasetManagerAddImagesCopyTest` (4) + `DatasetsPageImportPersistenceFailureTest` (2, nouvelle classe) — mêmes garanties côté Dataset, passthrough via image déjà présente dans la galerie Workspace, Presentation n'important jamais l'image en cas d'échec. `LoRAManagerMetadataTest` (3) + 1 test Presentation — restauration de `old_thumbnail`, passthrough jamais supprimé, échec de compensation, `choose_thumbnail()` affichant l'erreur avec l'ancienne miniature conservée. `ImagesPageImportPersistenceFailureTest` (2, nouvelle classe) — erreur affichée sans rien importer, retry réellement fonctionnel. `InferencePageTest` (3) — Accept échoué conserve l'état pending exact (contrôles cohérents, image toujours présente, aucune entrée Domain) ; retry Accept persiste réellement ; Rejeter après Accept échoué ne laisse aucune référence fantôme, vérifié y compris après un `save()` ultérieur sans rapport.
- **1121/1121 tests verts au total** (1101 précédents + 20 nets nouveaux) : 294/294 sur `test_workspace_roundtrip.py` + `test_dataset_roundtrip.py` + `test_lora_roundtrip.py` + `test_images_page.py`, 81/81 sur `test_inference_page.py`. Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage`/`DatasetsPage`/`LoRAPage`/`InferencePage` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 29/29 assertions** sur quatre scénarios : import Images (échec de persistence injecté, rollback, aucune copie orpheline, source intacte, retry réel réussi), import Dataset (même principe), miniature LoRA (ancienne miniature restaurée et toujours présente, nouvelle copie compensée, retry réel réussi), Inference Accept (échec injecté → message affiché, image toujours pending, absente de `workspace.images`, fichier toujours présent → second Accept avec persistence fonctionnelle → succès réel ; puis, dans un second scénario, Accept échoué → Rejeter → fichier supprimé, aucune entrée Domain, et aucune référence fantôme dans `project.json` après un `save()` ultérieur sans rapport).

### État du projet (Mission 067)

1121/1121 tests automatisés verts. Commit fonctionnel `9105c9214de478b30368c0d4bdcff167f6690432` (`feat: rollback additive filesystem mutations on persistence failure`), tag `v0.2-mission067`, GitHub Release publiée. Voir `docs/missions/MISSION_067.md` pour le détail complet.

---

## v0.2-mission066 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 066 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 066)

Un mini-audit transactionnel dédié, mené après Mission 065, a reproduit empiriquement un scénario de perte de données réelle dans `WorkspaceManager.remove_images()` : l'ordre précédent (`Path.unlink()` physique → mutation `Workspace.images` → `save()`) pouvait détruire définitivement un fichier alors qu'un échec du `save()` qui suit laissait `project.json` continuer à le référencer — confirmé y compris après fermeture/réouverture du projet. Un échec d'`unlink()` au milieu d'un lot levait par ailleurs un `PermissionError` brut, jamais converti en `WorkspaceManagerError`, avec le Domain déjà désynchronisé du filesystem avant même toute tentative de `save()`.

Mission 066 réordonne `remove_images()` en **persistence-first** : détermination des images à retirer → mutation du Domain → `save()` → suppressions physiques uniquement après succès de la persistence. Si `save()` échoue, `Workspace.images` est restauré verbatim (mêmes objets, même ordre) et l'exception `WorkspaceManagerError` remonte — aucun fichier n'est jamais touché, un rollback local simple et sûr sans snapshot du Workspace entier. Si `save()` réussit, la suppression logique est déjà durable ; chaque suppression physique est ensuite tentée indépendamment (un échec n'interrompt jamais le traitement des fichiers suivants), les échecs étant collectés dans un nouveau champ `RemovalResult.deletion_failed` plutôt que rollbackés — la politique de risque retenue devient : fichier orphelin récupérable plutôt qu'un fichier détruit encore référencé par le projet. `ImagesPage.delete_selected_images()` distingue désormais un échec de persistence (`QMessageBox.critical`, rien n'a été supprimé) d'un échec filesystem après persistence réussie (`QMessageBox.warning`, la suppression est déjà persistée) — aucune nouvelle logique de rafraîchissement n'a été nécessaire, le câblage `WORKSPACE_SAVED` déjà existant suffisant à refléter l'état persisté.

Changement strictement limité à `src/managers/workspace_manager.py` (`remove_images()`/`RemovalResult`) et `src/ui/pages/images_page.py`. Aucune modification de `WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`, `InferencePage`, ou de tout autre Manager — ces mutations additives filesystem partagent un problème transactionnel distinct, explicitement laissé ouvert pour un futur audit dédié.

### Tests ajoutés (Mission 066)

- **5 tests nets nouveaux** : 3 dans `WorkspaceManagerRemoveImagesTest` (`test_remove_images_when_save_fails_deletes_no_file_and_restores_domain` — le test de sécurité principal, `save()` en échec, aucun `unlink()` exécuté, fichiers intacts, `project.json` inchangé, Domain restauré exactement ; `test_remove_images_batch_survives_one_unlink_failure_and_reports_it` — lot A/B/C, l'échec de B n'empêche pas la suppression de C ; `test_remove_images_collects_every_unlink_failure_not_only_the_first` — plusieurs échecs tous collectés) et 2 dans `ImagesPageTest` (persistence échouée → `QMessageBox.critical`, aucun fichier détruit ; échec filesystem post-`save()` → `QMessageBox.warning`, suppression déjà persistée, galerie cohérente).
- **1101/1101 tests verts au total** (1096 précédents + 5 nets nouveaux) : 17/17 sur `WorkspaceManagerRemoveImagesTest`, 92/92 sur `test_workspace_roundtrip.py`, 49/49 sur `test_images_page.py`, 132/132 de non-régression croisée (`test_datasets_page.py`/`test_inference_page.py`/`test_thumbnails.py`). Le segfault Qt/PySide6 déjà documenté ne s'est pas manifesté pendant cette validation — observation de stabilité, non une preuve de correction, aucune modification visant ce sujet n'a été apportée.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage`/`WorkspaceManager` réels contre des fichiers réels sur l'écran non mocké de l'environnement de développement — **PASS, 18/18 assertions** sur trois scénarios : suppression normale (fichier détruit, projet mis à jour), échec de persistence injecté (aucun fichier détruit, Domain/`project.json` restaurés, message d'erreur), échec filesystem intermédiaire après persistence réussie sur un lot de trois (deux fichiers supprimés, un orphelin conservé, avertissement affiché, galerie cohérente avec l'état persisté).

### État du projet (Mission 066)

1101/1101 tests automatisés verts. Commit fonctionnel `c06fe82569cef35ea29fc7c5ce47da6a7f921f33` (`feat: make WorkspaceManager.remove_images() persistence-first`), tag `v0.2-mission066`, GitHub Release publiée. Voir `docs/missions/MISSION_066.md` pour le détail complet.

**Candidat futur explicitement conservé** : les mutations filesystem additives (`WorkspaceManager.add_images()`, `DatasetManager.add_images()`, `LoRAManager.set_thumbnail()`) et le scénario `InferencePage.accept()` qui en dépend partagent un problème transactionnel distinct de celui résolu ici — démontré par le même mini-audit, non traité par Mission 066, à réévaluer par un futur audit dédié plutôt qu'automatiquement promu.

---

## v0.2-mission065 — 2026-08-26

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 065 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 065)

L'audit consécutif à Mission 064 avait laissé en suspens le candidat B2, identifié dès l'audit post-Mission 063 : pendant une génération de `PromptAssistantDialog` (Mission 031), le bouton Annuler est désactivé, mais `Escape` et la fermeture native de la fenêtre contournaient ce garde-fou (`QDialog.reject()` n'était jamais surchargé), abandonnant le worker/`QThread` en arrière-plan et pouvant faire apparaître un `QMessageBox.critical()` tardif sur un dialogue que l'utilisateur croyait déjà fermé. L'architecte a tranché l'arbitrage produit resté ouvert : **Option A — interdire la fermeture pendant une génération**, plutôt que l'alternative (fermeture autorisée avec annulation/discard propre du résultat).

Une vérification empirique préalable (script de sonde exécuté dans le scratchpad, sans modification) a établi que `dialog.close()` déclenche à la fois `closeEvent()` et `reject()`, tandis que `Escape` appelle `reject()` directement sans passer par `closeEvent()` — `reject()` est donc l'unique point de passage commun à `Escape`, à la fermeture native et au bouton Annuler (`cancel_button.clicked.connect(self.reject)`). Mission 065 surcharge uniquement `reject()` dans `src/ui/dialogs/prompt_assistant_dialog.py` : si `cancel_button.isEnabled()` est faux (état busy déjà piloté par `_set_controls_enabled()` depuis Mission 031), la tentative de fermeture est silencieusement ignorée, sans nouvelle popup ; sinon `super().reject()` s'exécute normalement. Aucun nouvel état n'est introduit — `cancel_button.isEnabled()` est réutilisé tel quel comme source de vérité busy/idle, délibérément préféré à `self._thread is not None` (dont la remise à `None` par `_cleanup_thread()` est asynchrone et retardée, ce qui aurait ouvert une fenêtre où le bouton semble réactivé alors que la fermeture resterait bloquée). Aucun mécanisme d'annulation du worker/`QThread` n'a été introduit : le cycle continue à s'exécuter normalement jusqu'à son terme (succès ou échec), après quoi la fermeture normale est restaurée.

Changement strictement limité à `src/ui/dialogs/prompt_assistant_dialog.py` (une seule méthode ajoutée, +15 lignes). Aucun changement `InferencePage`, `PromptsPage`, Domain/Manager/Infrastructure/EventBus, ou tout autre dialogue.

### Tests ajoutés (Mission 065)

- Nouvelle classe `PromptAssistantDialogCloseGuardTest` (5 tests, sans `QThread` réel — `cancel_button.setEnabled(False)` simule directement l'état busy, avec de vrais événements Qt pour Escape/fermeture) : Escape/fermeture ferment normalement à l'état idle, sont tous deux ignorés à l'état busy, fermeture de nouveau possible une fois l'état busy terminé.
- 2 tests ajoutés à la classe préexistante `PromptAssistantDialogGenerateTest` (cycle `QThread` réel réutilisé, pas une nouvelle classe threadée) : Escape et fermeture native tentés pendant une génération réelle restent sans effet, le worker termine normalement, le résultat atterrit correctement, et la fermeture redevient possible ensuite — vérifié à la fois sur le chemin de succès et sur le chemin d'échec (`QMessageBox.critical` mocké).
- **7 tests nets nouveaux**. Comportement observable testé (`isVisible()` via de vrais `dialog.show()`/`QTest.keyClick`/`dialog.close()`), jamais l'existence de l'override ou d'un booléen interne.
- **7/7 tests ciblés PASS. 38/38 sur la suite complète du fichier du dialogue. 159/159 en non-régression** (`test_inference_page.py` + `test_prompt_roundtrip.py`).
- **Suite complète : 3 exécutions consécutives `unittest discover` propres à 1096/1096** (1089 précédents + 7 nets nouveaux), aucun échec imputable à Mission 065 dans aucune des trois exécutions.
- Smoke test Qt réel, exécuté par Claude, dialogue et `QThread`/`PromptAssistantWorker` réels contre un écran non mocké — **PASS, 14/14 assertions** : idle (Escape/fermeture ferment normalement), busy (les deux tentatives sont ignorées, bouton Annuler désactivé), fin de génération réussie (fermeture de nouveau possible, résultat correct), et chemin d'échec (`QMessageBox.critical` réellement déclenché, fermeture de nouveau possible après l'erreur).

### État du projet (Mission 065)

1096/1096 tests automatisés verts sur 3 exécutions consécutives. Commit fonctionnel `17c44dceeecf0d277038edc0bea2118a740dd7ba` (`feat: block PromptAssistantDialog close while a generation is running`), tag `v0.2-mission065`, GitHub Release publiée. Voir `docs/missions/MISSION_065.md` pour le détail complet.

**Segfault Qt/PySide6** : l'aléa natif déjà documenté après Mission 063/064 **ne s'est pas manifesté pendant les 3 exécutions complètes de validation de Mission 065**. Cette absence d'observation est une **observation de stabilité sur ces 3 runs, pas une preuve de correction** : la cause racine reste non isolée, aucune modification visant ce sujet n'a été apportée dans Mission 065, et l'hypothèse simple « tests terminés avant la fin du cleanup du `QThread` » reste **expérimentalement réfutée** (deux expériences dédiées après Mission 064, toutes deux sans effet sur le crash à l'époque — voir `docs/missions/MISSION_064.md`).

---

## v0.2-mission064 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 064 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 064)

L'audit consécutif à Mission 063 a confirmé que `load_thumbnail_icon()` (`src/ui/thumbnails.py`) décodait intégralement chaque image en pleine résolution puis la redimensionnait, de façon synchrone sur le thread UI, **sans aucun cache** — à chaque appel, quel qu'en soit le déclencheur. Un mini-audit technique ciblé a établi que le déclencheur dominant n'est pas seulement le tri explicite mais `WORKSPACE_SAVED` : `ImagesPage.update_images()` et `DatasetsPage.update_datasets()` y sont tous deux abonnés, un événement publié après quasiment toute mutation de l'application — chaque déclenchement reconstruit intégralement la liste et redécode toutes les vignettes affichées, y compris celles totalement inchangées.

Mission 064 introduit un cache LRU partagé et borné, strictement localisé à `src/ui/thumbnails.py`, sans toucher à l'API publique `load_thumbnail_icon(file_path, size, style)` ni aux trois consommateurs (`ImagesPage`, `DatasetsPage`, `SelectImagesDialog`). La fonction publique lit d'abord `Path(file_path).stat()` — avant toute possibilité d'accès au cache, pour qu'un fichier absent/modifié/remplacé ne puisse jamais être satisfait par une entrée obsolète — puis délègue à une fonction interne `_decode_and_scale(file_path, mtime_ns, file_size, width, height)` décorée `functools.lru_cache(maxsize=256)`. Le décodage `QPixmap()` pleine résolution n'a lieu que lors d'un cache miss ; seul le `QIcon` construit à partir du résultat déjà redimensionné est retourné/conservé — le pixmap pleine résolution reste local et sort de portée aussitôt après. Un fichier modifié ou remplacé au même chemin change sa signature (`mtime_ns`/`file_size`), provoquant un nouveau décodage automatique ; un fichier supprimé échoue au `stat()` préalable et retombe directement sur l'icône de fallback, sans jamais interroger le cache.

Aucune normalisation de chemin supplémentaire n'a été ajoutée : les chemins de ce flux sont déjà construits de façon canonique par `WorkspaceStorage.copy_into_workspace()`, sans preuve concrète justifiant d'y déroger. La borne `maxsize=256` (≈16 Mo pour des vignettes 128×128 RGBA) est un choix d'ingénierie proportionné, pas un arbitrage produit.

### Tests ajoutés (Mission 064)

- Nouveau fichier `tests/integration/test_thumbnails.py`, classe `ThumbnailCacheTest` (**9 tests nets nouveaux**) : premier appel/cache miss, appel suivant sur fichier inchangé/cache hit, fichier modifié (réécriture réelle du contenu, pas un simple `os.utime()`) ou remplacé au même chemin/nouveau miss, dimensions différentes/entrées distinctes, fichier inexistant/fallback sans jamais toucher le cache, fichier supprimé après un chargement réussi/fallback sans réutiliser l'ancienne vignette, borne du cache conforme à la constante documentée. Comptage fiable des décodages via `_decode_and_scale.cache_info()` (`hits`/`misses`, mécanisme stdlib, aucune dépendance à un détail Qt fragile) ; `cache_clear()` systématique pour l'isolation entre tests (cache process-wide).
- Non-régression des trois consommateurs couverte par les suites existantes : **99/99 PASS** (`test_images_page.py` + `test_datasets_page.py` + `test_select_images_dialog.py`), aucun test supplémentaire redondant ajouté.
- **1089/1089 tests verts au total, démontrés par décomposition** (1080 précédents + 9 nets nouveaux) : l'aléa d'environnement natif Qt/PySide6 déjà documenté après Mission 063 est devenu **reproductible à 5/5 exécutions complètes `unittest discover`** pendant cette mission, systématiquement localisé dans `PromptAssistantDialogGenerateTest` (`tests/integration/test_prompt_assistant_dialog.py`, un test préexistant utilisant un vrai `QThread`, sans rapport avec ce diff). Non attribué à Mission 064 : la suite complète à l'exclusion des deux seuls modules `QThread` réels (`test_prompt_assistant_dialog.py`, `test_inference_page.py`) tourne à **980/980**, ces deux modules exécutés ensemble isolément à **109/109** — soit 980+109 = 1089, le total exact attendu.
- Smoke test Qt réel, exécuté par Claude, `ImagesPage` et `SelectImagesDialog` réels contre un Workspace réel sur l'écran non mocké de l'environnement de développement — **PASS** : aucun redécodage sur reconstruction déclenchée par une mutation sans rapport avec les images (`workspace_manager.save()`), exactement un nouveau décodage pour un fichier réellement modifié, partage de cache démontré entre `ImagesPage` et `SelectImagesDialog` (mêmes chemins internes exacts, sans copie).

### État du projet (Mission 064)

1089/1089 tests automatisés verts (démontrés par décomposition, voir ci-dessus). Commit fonctionnel `90689d0beb0e126700872310813e9e18e2c26edd` (`feat: add a bounded, mtime/size-keyed thumbnail cache`), tag `v0.2-mission064`, GitHub Release publiée. Voir `docs/missions/MISSION_064.md` pour le détail complet. L'aléa Qt/PySide6, désormais reproductible à 5/5, est élevé au rang de priorité d'investigation pour Mission 065.

---

## v0.2-mission063 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 063 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 063)

L'audit consécutif à Mission 062 a identifié que 6 des 7 pages CRUD du projet — `Dataset`, `LoRA`, `Model`, `Training`, `Workflow`, `Prompts` — laissaient leur bouton « Supprimer » **toujours activé**, indépendamment de toute sélection réelle dans la liste, contrairement à `ImagesPage.delete_button` (Mission 046), seule page correcte. Chaque `delete_<entité>()` de Page garde bien `if item is None: return`, donc aucun crash n'était possible — mais un clic sur « Supprimer » sans sélection produisait un **no-op silencieux, sans aucun retour visuel**, en particulier sur une liste vide ou juste après un changement de Workspace/Character. `Character` reste hors périmètre : `CharactersPage.delete_button` est volontairement caché depuis Mission 026, inaccessible depuis l'application réelle.

Mission 063 étend à chacune des 6 pages le motif déjà établi par `ImagesPage` : `delete_button.setEnabled(False)` à la construction, état recalculé au tout début du handler de sélection (`on_<entité>_selection_changed`) et à la fin de chaque reconstruction de liste (`update_<entité>s()`), puisque `blockSignals(True)` pendant une reconstruction supprime le signal `currentItemChanged` que le handler écoute normalement. `PromptsPage` diffère des 5 autres pages : sa sélection peut être annulée et revenir en arrière par la garde de brouillon non enregistré de Mission 038 (`on_prompt_selection_changed` → `_confirm_discard_before_switch()` → Annuler → `setCurrentItem(previous)`) — le bouton suit alors la sélection **réellement en vigueur après ce retour en arrière**, pas la tentative de bascule annulée. Pour `Dataset`, la garde préexistante `is_referenced_by_training()` (Mission 062) n'est **pas** répercutée sur l'état du bouton : un Dataset sélectionné, même référencé par un Training, active « Supprimer » selon la règle générale ; la garde continue d'intervenir uniquement au clic, dans `delete_dataset()`, strictement inchangée. Aucune abstraction partagée introduite — 6 adaptations locales indépendantes.

Changement strictement limité aux 6 fichiers `src/ui/pages/{datasets,lora,models,training,workflows,prompts}_page.py`. Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : `Character`, mécanisme de confirmation de Mission 062 (wording/comportement strictement inchangés), toute désactivation dynamique de « Supprimer » selon `is_referenced_by_training()` (évolution UX distincte, non traitée ici), candidats A-2 (cache des vignettes) et B2 (fermeture de `PromptAssistantDialog` pendant une génération), tous deux réservés à une future mission.

### Tests ajoutés (Mission 063)

- Pour chacune des 6 pages, une nouvelle classe `*PageDeleteButtonStateTest` dans le fichier `test_<entité>_roundtrip.py` existant, couvrant a minima : désactivé avant tout Workspace ; désactivé sans sélection puis activé après sélection réelle ; désactivé après désélection réelle ; état cohérent après reconstruction de liste ; désactivé après fermeture du Workspace ; désactivé après suppression de l'élément sélectionné.
- Pour Dataset spécifiquement, un test additionnel `test_selecting_a_dataset_referenced_by_training_still_enables_button` — preuve explicite que la garde Training n'intervient pas sur l'état du bouton.
- Pour Prompts spécifiquement, deux tests additionnels couvrant la bascule annulée par la garde dirty-state de Mission 038, avec et sans sélection préalable.
- **39 tests nets nouveaux** au total (6+7+6+6+6+8). **1080/1080 tests verts au total** (1041 précédents + 39 nets nouveaux) — un run complet propre confirmé ; un aléa d'environnement natif Qt/PySide6 (segfault intermittent) a été observé sur plusieurs runs complets, reproduit indépendamment de ce diff sur le baseline (`git stash`), jamais reproduit dans les runs ciblés/groupés des modules modifiés — voir `docs/missions/MISSION_063.md` section 9.
- Smoke test Qt réel, exécuté par Claude, les 6 pages construites contre un Workspace réel sur l'écran non mocké de l'environnement de développement — **PASS** : désactivé/activé/désactivé conformes à la sélection réelle, cohérence après reconstruction de liste, et cycle de confirmation Mission 062 intact rejoué de bout en bout (vrai `QMessageBox`, suppression réelle, bouton redevient désactivé) sur les 5 pages concernées.

### État du projet (Mission 063)

1080/1080 tests automatisés verts. Commit fonctionnel `538c943b7eb9f35e84634fce6e13785fcfbda365` (`feat: disable Supprimer when no CRUD entity is selected`), tag `v0.2-mission063`, GitHub Release publiée. Voir `docs/missions/MISSION_063.md` pour le détail complet.

---

## v0.2-mission062 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 062 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 062)

L'audit consécutif à Mission 061 (deux passes exploratoires successives, la seconde corrigée après réexamen de l'architecte) a identifié que 5 des 6 entités du projet — `Dataset`, `LoRA`, `Model`, `Training`, `Workflow` — exposaient une méthode `delete_<entité>()` de Page appelant directement le Manager sans aucune confirmation utilisateur : un simple clic sur « Supprimer » suffisait à effacer irréversiblement l'enregistrement, contrairement à `ImagesPage.delete_selected_images()` (Mission 046) et `PromptsPage.delete_prompt()` (Mission 038), qui confirment déjà.

La 6ᵉ entité initialement suspectée, `Character`, a été explicitement exclue après audit approfondi : `CharactersPage.delete_button` est volontairement caché (`setVisible(False)`) depuis Mission 026 (orientation produit « 1 Workspace = 1 personnage principal »), verrouillé par un test de régression dédié (`test_character_roundtrip.py`, `isHidden()`) — `CharactersPage.delete_character()` est donc inaccessible depuis l'application réelle. `CharacterManager.delete()` reste légitime et nécessaire, appelé par de nombreux tests de régression validant le pattern Character-owned (cascade `Dataset`/`LoRA`/`Prompt`/`Training`) — ajouter une confirmation sur un chemin UI inaccessible n'aurait protégé personne.

Mission 062 ajoute à chacune des 5 pages restantes un `QMessageBox` de confirmation avant suppression, reprenant exactement le motif déjà établi par `ImagesPage`/`PromptsPage` (`addButton`/`AcceptRole`/`RejectRole`, `setDefaultButton(cancel_button)`, `Annuler` par défaut) : Annuler (y compris fermeture via la croix ou Échap) n'appelle jamais le Manager et ne mute aucun état ; Supprimer exécute exactement l'appel au Manager déjà existant, sans autre changement de comportement. Pour `Dataset`, la garde préexistante `is_referenced_by_training()` reste la **première** vérification, avant toute construction de `QMessageBox` — un Dataset dont la suppression est refusée par cette garde n'affiche jamais de confirmation trompeuse. Aucune abstraction/helper partagé introduit — 5 adaptations locales indépendantes.

Changement strictement limité aux 5 fichiers `src/ui/pages/{datasets,lora,models,training,workflows}_page.py`. Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : `Character` (voir ci-dessus), cache des vignettes (candidat A-2 identifié pendant le même audit, réservé à une future mission).

### Tests ajoutés (Mission 062)

- Pour chacune des 5 entités, une nouvelle classe `*PageDeleteConfirmationTest` dans le fichier `test_<entité>_roundtrip.py` existant : `test_delete_with_no_selection_is_a_no_op`, `test_delete_confirmed_removes_<entité>`, `test_delete_cancelled_calls_neither_manager_nor_mutates_state` (mockage `QMessageBox` au niveau classe, technique déjà éprouvée par `test_images_page.py`, `patch.object(manager, "delete")` prouvant l'absence d'appel).
- Pour Dataset spécifiquement, une 4ᵉ méthode `test_delete_blocked_by_training_reference_never_shows_confirmation` : garde Training toujours active, `QMessageBox.warning()` appelé, `QMessageBox().exec()` jamais appelé, dataset toujours présent.
- **16 tests nets nouveaux** au total. **1041/1041 tests verts au total** (1025 précédents + 16 nets nouveaux), 16/16 de tests ciblés.
- Smoke test Qt réel, exécuté par Claude, les 5 pages construites contre un Workspace réel sur l'écran non mocké de l'environnement de développement — **PASS** : dialogue construit avec le bon titre/texte/boutons (`["Annuler", "Supprimer"]`), `defaultButton()` confirmé « Annuler », Annuler → entité conservée et sélection inchangée, Confirmer → entité effectivement supprimée ; cas Dataset référencé par un Training : `QMessageBox.exec()` jamais appelé (0 mesuré), seule la garde préexistante s'est déclenchée.

### État du projet (Mission 062)

1041/1041 tests automatisés verts. Commit fonctionnel `a630b4f6884b6bf204fdeb42cb7a94f39a639a4b` (`feat: confirm before deleting Dataset, LoRA, Model, Training and Workflow`), tag `v0.2-mission062`, GitHub Release publiée. Voir `docs/missions/MISSION_062.md` pour le détail complet.

---

## v0.2-mission061 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 061 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 061)

L'audit consécutif à Mission 060 a cherché à vérifier si la même classe de dette UX (taille initiale fixée en dur, jamais bornée à l'écran réellement disponible) existait ailleurs dans le code. Recherche exhaustive des 6 sous-classes `QDialog` du projet : exactement deux appellent `.resize()` avec des valeurs fixes — `ImagePreviewDialog` (`self.resize(1000, 750)`) et `PromptAssistantDialog` (`self.resize(800, 700)`) ; les quatre autres (`ImportCollisionDialog`, `NewProjectDialog`, `SelectImagesDialog`, `RenameProjectDialog`) se dimensionnent déjà de façon adaptative via le `sizeHint()` agrégé de leur contenu et n'étaient pas concernées.

Mission 061 applique aux deux dialogues exactement le même calcul que Mission 060 : `self.screen()` borné à `screen().availableGeometry()`, repli sur `QApplication.primaryScreen()` si `None`, repli final sur la taille historique de chacun (`1000×750`/`800×700`) si aucun écran n'est disponible du tout. La taille par défaut préférée reste conservée à l'identique dès que l'écran dispose de la place nécessaire ; elle n'est réduite que sur un écran dont l'espace disponible est effectivement inférieur. Les deux dialogues restent librement redimensionnables ensuite, exactement comme avant cette mission.

Changement strictement limité à deux points de code (`src/ui/dialogs/image_preview_dialog.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, import `QApplication` ajouté dans chacun). Aucune abstraction/helper partagé introduit — deux adaptations locales indépendantes. Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : persistance/restauration de géométrie entre sessions, centrage explicite, gestion multi-écrans avancée, tout autre dialogue du projet.

### Tests ajoutés (Mission 061)

- `tests/integration/test_image_preview_dialog.py` : nouvelle classe `ImagePreviewDialogInitialSizeTest` (5 tests) — écran disponible plus petit (borné à `availableGeometry()`, prouvé distinct de `geometry()`) ; écran disponible plus grand (`1000×750` conservé) ; repli `QApplication.primaryScreen()` ; repli historique sans écran, sans exception ; redimensionnement manuel toujours accepté après construction.
- `tests/integration/test_prompt_assistant_dialog.py` : le test préexistant `test_initial_size_is_at_least_800_by_700`, qui imposait un plancher **inconditionnel** contredisant directement le nouveau contrat, est **remplacé** (non étendu) par la nouvelle classe `PromptAssistantDialogInitialSizeTest`, 5 tests strictement symétriques, adaptés à `800×700`.
- **1025/1025 tests verts au total** (1016 précédents + 9 nets nouveaux : 5+5 ajoutés, 1 remplacé), 49/49 de tests ciblés, 248/248 de non-régression.
- Smoke test Qt réel, exécuté par Claude, les deux dialogues construits sur l'écran non mocké de l'environnement de développement — **PASS** : `ImagePreviewDialog` `QSize(1000, 750)`, `PromptAssistantDialog` `QSize(800, 700)`, tous deux dans les bornes de `availableGeometry() = QRect(0, 0, 1920, 1040)`, redimensionnement manuel confirmé pour chacun.

### État du projet (Mission 061)

1025/1025 tests automatisés verts. Commit fonctionnel `e2466292fd25d457eb2261414646597686c5240d` (`feat: bound ImagePreviewDialog and PromptAssistantDialog to available screen geometry`), tag `v0.2-mission061`, GitHub Release publiée. Voir `docs/missions/MISSION_061.md` pour le détail complet.

---

## v0.2-mission060 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 060 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 060)

`MainWindow.__init__()` fixait `self.resize(1700, 950)` inconditionnellement depuis le commit racine du fichier (2026-08-08), sans aucune prise en compte de l'espace d'écran réellement disponible — dette UX signalée pendant le smoke test réel de Mission 059, alors documentée séparément faute d'entrer dans le périmètre validé de cette mission-là.

Mission 060 remplace ce `resize()` fixe par un calcul borné à `screen().availableGeometry()` — la zone réellement utilisable de l'écran, à l'exclusion de la barre des tâches et des autres zones réservées, mesurée dans cet environnement à `1920×1040` contre `1920×1080` pour `geometry()` (40px de différence, une barre des tâches réelle). `self.screen()` se replie sur `QApplication.primaryScreen()` s'il retourne `None`, puis sur le défaut historique `1700×950` si aucun écran n'est disponible du tout — la construction de `MainWindow` ne peut jamais échouer pour cette raison. La taille par défaut préférée `1700×950` reste conservée à l'identique dès que l'écran dispose de la place nécessaire (le cas courant, confirmé par le smoke test réel de cet environnement) ; elle n'est réduite que sur un écran dont l'espace disponible est effectivement inférieur. La fenêtre reste librement redimensionnable ensuite, exactement comme avant cette mission.

Changement strictement limité à un seul point de code dans `src/ui/main_window.py` (import `QApplication` ajouté). Aucun changement Domain/Manager/Infrastructure/EventBus. Hors périmètre explicitement confirmé : persistance/restauration de géométrie entre sessions, centrage explicite, gestion multi-écrans avancée, modification des tailles minimales (`MainWindow.minimumSizeHint()` reste `865×769`, mesuré par Mission 059).

### Tests ajoutés (Mission 060)

- Nouveau fichier `tests/integration/test_main_window_initial_size.py` (`MainWindowInitialSizeTest`, 5 tests) : écran disponible plus petit que `1700×950` (borné à `availableGeometry()`, prouvé distinct de `geometry()` par des valeurs volontairement différentes dans chaque mock) ; écran disponible plus grand (taille historique `1700×950` conservée) ; repli sur `QApplication.primaryScreen()` quand `self.screen()` retourne `None` ; repli final sur `1700×950` quand aucun écran n'est disponible, sans exception ; redimensionnement manuel toujours accepté après construction.
- **1016/1016 tests verts au total** (1011 précédents + 5 nets nouveaux), 75/75 de non-régression ciblée.
- Smoke test Qt réel, exécuté par Claude (pas seulement décrit), `MainWindow` réelle construite sur l'écran non mocké de l'environnement de développement — **PASS** : `screen.geometry() = QRect(0, 0, 1920, 1080)`, `screen.availableGeometry() = QRect(0, 0, 1920, 1040)` (mesurés, jamais supposés), taille initiale obtenue `QSize(1700, 950)` dans les bornes, redimensionnement manuel (`resize(800, 600)`) confirmé après construction.

### État du projet (Mission 060)

1016/1016 tests automatisés verts. Commit fonctionnel `bee1ec46db9a54b08f7e165fa4aba66bfe00b8e5` (`feat: bound initial window size to available screen geometry`), tag `v0.2-mission060`, GitHub Release publiée. Voir `docs/missions/MISSION_060.md` pour le détail complet.

---

## v0.2-mission059 — 2026-08-25

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 059 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 059)

`LoRAManager`/`LoRAPage` géraient déjà intégralement la fiche technique d'une LoRA côté Workspace (fichiers, miniature, `engine`/`architecture`/`trigger_word`/`version`) depuis Mission 047/050, mais aucune LoRA n'était jamais appliquée lors d'une génération, quel que soit le moteur. Mission 059 livre la première application réelle d'une LoRA pendant une génération ComfyUI.

`ComfyUIEngine.list_loras()` (nouvelle méthode) interroge `GET /object_info/LoraLoader` sur le serveur ComfyUI réellement actif — mirroir exact du mécanisme de découverte du checkpoint (Mission 025) — et échoue explicitement (`ComfyUIEngineError`) sur toute réponse inattendue, jamais de liste partielle ou devinée. `SettingsPage` gagne un `QComboBox` LoRA éditable et un bouton de rafraîchissement dédiés, ainsi qu'un contrôle de force unique (`QDoubleSpinBox`, défaut `1.0`), persistés dans `ApplicationSettings` (`comfyui_lora_name`, `comfyui_lora_strength`) — sélection Settings-level/globale, comme le checkpoint, lue une seule fois au démarrage par `MainWindow` (contrat "pas de hot reload" déjà établi).

`build_txt2img_workflow()`/`build_img2img_workflow()` (`comfyui_workflows.py`) gagnent une nouvelle fonction interne `_apply_lora()` : quand aucune LoRA n'est configurée, le graphe retourné reste structurellement identique à avant cette mission (égalité de dict Python, seed aléatoire neutralisé pour la comparaison) ; quand une LoRA est configurée, un nœud natif `LoraLoader` est inséré entre `CheckpointLoaderSimple` et tout consommateur de `model`/`clip` (`KSampler`, les deux `CLIPTextEncode`), la même force alimentant à la fois `strength_model` et `strength_clip` — `vae` reste toujours issu directement du checkpoint, `LoraLoader` ne le touchant jamais. Le mécanisme `Reference(path, pose_composition)` de Mission 056 reste totalement inchangé et cohabite sans interaction avec le nouveau nœud LoRA, confirmé aussi bien en test automatisé qu'en génération réelle.

**Compatibilité architecture (SD1.5/SDXL/FLUX)** : le pipeline actuel (`CheckpointLoaderSimple` + nœuds génériques) couvre SD1.5 et SDXL — confirmé par preuve historique réelle (le smoke test de Mission 012 avait détecté des checkpoints SDXL via ce même mécanisme). **FLUX est explicitement hors périmètre** : son workflow natif ComfyUI (`UNETLoader`/`DualCLIPLoader`/VAE séparé) est structurellement différent et n'existe nulle part dans ce dépôt — limitation pré-existante depuis Mission 012/013, non introduite par cette mission. `/object_info/LoraLoader` n'expose aucune métadonnée d'architecture par fichier ; aucune détection ou filtrage automatique n'est donc implémenté, et aucune heuristique par nom de fichier n'est introduite. Une LoRA d'une architecture incompatible avec le checkpoint actif échoue explicitement côté serveur ComfyUI — jamais de substitution silencieuse.

**Hors périmètre explicite** : aucun mapping entre une entité `LoRA` du Workspace (`LoRA.files`) et un `lora_name` ComfyUI — `LoRA.files` contient des chemins externes bruts jamais copiés dans le Workspace (à la différence de `LoRA.thumbnail`), et aucun mécanisme fiable de correspondance n'existe aujourd'hui ; ce candidat sélectionne uniquement parmi les LoRA déjà connues du serveur ComfyUI actif. Aucune sélection par génération (`InferencePage`) ni par `Character`, aucune LoRA simultanée, aucun autre moteur.

**Régression de taille de fenêtre détectée et corrigée** : pendant l'audit de compatibilité architecture de cette même mission, l'allongement du texte d'un hint `SettingsPage` (`application_hint`, dépourvu de `setWordWrap()`) a fait presque doubler sa largeur naturelle, ce qui — via l'agrégation par `QStackedWidget` du `sizeHint()` maximal de toutes ses pages, y compris non affichées — a fait exploser la taille minimale de `MainWindow` bien au-delà des résolutions d'écran courantes, visible dès le Dashboard au lancement. Cause établie avec certitude par mesure directe de `sizeHint()`/`minimumSizeHint()` avec des widgets Qt réels, y compris une comparaison A/B contrôlée entre la version `settings_page.py` committée avant cette mission et la version actuelle. Corrigée par un seul appel `application_hint.setWordWrap(True)`, sans toucher au `self.resize(1700, 950)` fixe et non adaptatif à l'écran de `MainWindow` — celui-ci est authentiquement préexistant (commit racine du fichier) et n'est pas la cause de la régression ; il reste une dette UX distincte, non résolue par cette mission.

Aucun changement Domain au-delà de deux champs additifs `ApplicationSettings` (`comfyui_lora_name`, `comfyui_lora_strength`), aucun changement EventBus, aucune nouvelle dépendance.

### Tests ajoutés (Mission 059)

- 6 fichiers de test existants étendus, aucun nouveau fichier créé : `test_comfyui_workflows.py` (+`NoLoraProducesTheExactPreMission059WorkflowTest`, +`LoraInsertedWhenConfiguredTest`), `test_comfyui_engine.py` (+`ComfyUIEngineListLorasTest`, +`ComfyUIEngineGenerateImageLoraTest`), `test_generation_manager.py` (+`GenerationManagerLoraTest`, assertions existantes étendues), `test_application_settings_roundtrip.py` (nouveau test de compatibilité legacy sans champs LoRA, littéraux existants étendus), `test_settings_page.py` (+`SettingsPageLoraDiscoveryTest`, +`SettingsPageSizeHintRegressionTest`), `test_main_window_comfyui_settings.py` (assertions existantes étendues).
- Le test "sans LoRA" prouve une égalité structurelle complète du workflow Python (comparaison de dict via `assertEqual`, seed aléatoire du graphe neutralisé par un `random.randint` patché) — pas une comparaison JSON octet par octet.
- `SettingsPageSizeHintRegressionTest` verrouille `SettingsPage.sizeHint()`/`.minimumSizeHint()` sous 900px de large, en garde contre une régression future de même nature.
- **1011/1011 tests verts au total** (967 précédents + 44 nets nouveaux : 43 fonctionnels + 1 non-régression de taille de fenêtre).
- Vérification manuelle réelle en deux temps : smoke test **mocké** (objets Qt/Manager réels — `SettingsPage`, `ApplicationSettingsManager`, `ComfyUIEngine`, `GenerationManager` — mais réseau simulé, aucun serveur ComfyUI accessible dans l'environnement de développement) **PASS** (19/19) ; puis smoke test **réel**, exécuté par l'architecte sur son installation ComfyUI réelle **PASS** — découverte de 5 LoRA réels, génération txt2img réelle avec LoRA, génération img2img réelle avec `Reference(pose_composition)` + LoRA simultanément.

### État du projet (Mission 059)

1011\1011 tests automatisés verts. Commit fonctionnel `c96b984606bbac83d6276d7dca54b9efe4307c53` (`feat: add ComfyUI LoRA selection for generation`), tag `v0.2-mission059`, GitHub Release publiée. Voir `docs/missions/MISSION_059.md` pour le détail complet.

---

## v0.2-mission058 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 058 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 058)

Un audit factuel du dépôt, réalisé après la clôture complète de Mission 057, a identifié quatre éléments frais de code mort/documentation obsolète, distincts de ceux déjà traités par Mission 057 : `EventBus.unsubscribe()` (méthode publique jamais appelée nulle part, aucun test ne l'exerçant) ; une branche structurellement inatteignable dans `TrainingPage.create_training()` (une garde identique existe déjà en tête de la même méthode, rendant la seconde impossible à atteindre — confirmé par analyse de flot de `TrainingManager.create()` et de son seul abonné `TRAINING_CREATED`, une pure UI refresh) ; un commentaire obsolète de `Workspace.from_dict()` affirmant que `Workspace.models` « n'a jamais tenu de vraie donnée », alors que `ModelManager`/`ModelsPage` le consomment activement ; deux références obsolètes à `BasePage` dans `docs/PROJECT_CONTEXT.md`, encore décrit comme présent bien que Mission 057 l'ait déjà supprimé.

Les quatre éléments sont retirés/corrigés. `EventBus.subscribe()`/`publish()`/`_freeze()` et le reste de `create_training()` restent strictement inchangés. Aucun comportement utilisateur observable ne change — confirmé par un cycle Qt réel exécuté manuellement sur les quatre scénarios de `create_training()` (aucun Workspace ouvert, Workspace sans Dataset, création réelle d'une Training, suppression du Character).

Aucun changement Domain (au-delà du seul commentaire corrigé)/Manager/Inference/Settings/portabilité des chemins.

### Tests ajoutés (Mission 058)

- **Aucun test ajouté ni retiré** — décision explicite du contrat : `EventBus.unsubscribe()` n'avait aucun test le couvrant, la branche morte de `training_page.py` était par construction non testable (inatteignable), et le seul cas réel restant (« Aucun personnage ») était déjà couvert par `test_training_roundtrip.py` avant cette mission.
- **967/967 tests verts** au total — décompte strictement identique à l'état pré-mission. Non-régression confirmée sur `test_training_roundtrip.py` (34/34).
- Vérification manuelle réelle (hors suite `unittest`) : cycle Qt complet de `TrainingPage.create_training()`, PASS sur les quatre scénarios réellement atteignables.

### État du projet (Mission 058)

967/967 tests automatisés verts. Commit fonctionnel `9e35c4497fe880123f46a6edd6b10603727d123c` (`chore: remove dead code and stale documentation (round 2)`), tag `v0.2-mission058`, GitHub Release publiée. Voir `docs/missions/MISSION_058.md` pour le détail complet.

---

## v0.2-mission057 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 057 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 057)

**Mission 057 — Remove Vestigial Workspace Fields and Dead Code.** Un audit factuel du dépôt post-Mission 056 a confirmé, code à l'appui, que trois éléments étaient du code/état mort : `Workspace.datasets`/`.loras`/`.training` (champs génériques non typés, jamais lus par aucun Manager — `DatasetManager`/`LoRAManager`/`TrainingManager` lisent exclusivement `Character.datasets`/`.loras`/`.trainings`, une violation du principe Single Source of Truth de `CLAUDE.md`), `Character.history` (sérialisé depuis son introduction mais jamais peuplé ni lu nulle part), et `src/ui/pages/base_page.py` (`BasePage`, jamais hérité par aucune des 11 Pages du projet).

Les trois éléments sont retirés. `Workspace.models`/`.workflows`/`.images`/`.characters`/`.settings`/`.root` et `Character.datasets`/`.loras`/`.prompts`/`.trainings` — les collections réellement possédées et consommées — restent strictement inchangés.

**Compatibilité défensive démontrée par tests, pas seulement affirmée** (précision explicitement exigée par l'architecte avant implémentation) : un `project.json` écrit avant cette mission et contenant encore ces clés, même peuplées de données non vides, continue de se charger sans erreur ; ces clés ne sont plus jamais réémises une fois le Workspace sauvegardé avec cette version — un nettoyage d'un schéma mort, jamais présenté comme une migration de données fonctionnelles, ces champs n'ayant jamais porté de donnée réelle à aucun stade du projet.

Aucun changement Inference/Settings/portabilité des chemins/Domain (au-delà des retraits ci-dessus)/EventBus.

### Tests ajoutés (Mission 057)

- 9 tests nets nouveaux dans `test_workspace_roundtrip.py` (aucun nouveau fichier) : nouvelle classe `WorkspaceVestigialFieldsRemovalTest` — chargement réussi d'un `project.json` legacy avec `datasets`/`loras`/`training`/`history` peuplés ; collections réelles (`Character.datasets`/`.loras`/`.prompts`/`.trainings`, `Workspace.models`/`.workflows`) intactes après ce chargement ; clés absentes après re-sauvegarde ; Workspace neuf n'émettant jamais ces clés ; cycle création/fermeture/réouverture sans régression ; absence totale de référence à `BasePage`/`base_page` dans `src/ui/pages/*.py`.
- 2 tests nets nouveaux dans `test_character_roundtrip.py` : nouvelle classe `CharacterHistoryFieldRemovalTest` — preuve Domain-level isolée, indépendante du cycle Workspace complet.
- 8 assertions obsolètes retirées (comparaisons portant sur les champs supprimés) dans `test_workflow_roundtrip.py` (2) et `test_settings_roundtrip.py` (6, répartis sur 2 tests) — aucune autre logique de test modifiée.
- **967/967 tests verts** au total (956 précédents + 11 nets nouveaux). Non-régression confirmée sur `test_workspace_roundtrip.py` (89/89), `test_character_roundtrip.py` (42/42), `test_workflow_roundtrip.py` (21/21), `test_settings_roundtrip.py` (9/9), `test_dataset_roundtrip.py` (49/49), `test_lora_roundtrip.py` (67/67), `test_training_roundtrip.py` (34/34).
- **Cycle réel création → sauvegarde → fermeture → réouverture, exécuté manuellement en dehors de `unittest`, JSON produit inspecté directement : PASS** — un `project.json` legacy écrit à la main (clés retirées peuplées de données non vides, aux côtés d'un Dataset/LoRA/Prompt/Training réels) se charge sans erreur ; après réouverture avec une pile entièrement neuve puis sauvegarde, le fichier réécrit ne contient plus les clés retirées, et les données fonctionnelles (Dataset/LoRA/Prompt/Training/Model/Workflow) sont toutes préservées intactes. Aucun smoke test Qt requis — aucun comportement UI observable n'est modifié par cette mission.

### État du projet (Mission 057)

Le dépôt referme une incohérence architecturale documentée depuis les Missions 026-029 (migration de la propriété de `Dataset`/`LoRA`/`Training` de `Workspace` vers `Character`, jamais suivie du retrait des champs `Workspace` devenus obsolètes) et une dette mineure plus ancienne (`Character.history`, `BasePage`). Validée par la suite automatisée complète et par un cycle réel d'utilisation avec inspection directe du fichier produit. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `c7eb1fe0c32f677226f5b14c93dbbf82832e3bef` — `refactor: remove vestigial Workspace fields and dead code`, tag `v0.2-mission057`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et non résolu — Mission 057 n'y touche strictement pas (nettoyage Domain/dead-code uniquement, aucun changement Inference) ; la primitive typée `Reference(path, role)` introduite par Mission 056 reste la seule brique posée, avec `pose_composition` comme seul rôle réellement actionnable.

---

## v0.2-mission056 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 056 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 056)

**Mission 056 — Typed Inference Reference Primitive.** Un audit dédié de l'architecture Inference a confirmé que la limitation à une seule référence était codée à toutes les couches (`InferencePage._reference_image_path` scalaire, `GenerationManager.generate()` rejetant `len(reference_images) > 1`, `ComfyUIEngine.generate_image(reference_image: Optional[dict])` structurellement singulier), alors que l'architecture « 0..N références avec rôles » documentée dans `PROJECT_CONTEXT.md` n'existait que dans des commentaires — zéro code. L'architecte a validé une orientation (Option B) restreinte à une primitive typée générique, sans intégrer aucun mécanisme moteur concret (IP-Adapter/ControlNet/InstantID/PuLID, chacun réservé à une mission future distincte).

Nouvelle primitive transitoire `Reference(path, role)` (`NamedTuple`, colocalisée dans `GenerationManager` — même précédent architectural que `CharacterContext` dans `PromptAssistantManager`) et constante unique `REFERENCE_ROLE_POSE_COMPOSITION` — le seul rôle réellement actionnable, retypant sans le modifier le mécanisme img2img mono-référence déjà existant. `InferencePage._start_generation()` construit désormais réellement un `Reference` pour son flux de production, au lieu de transmettre un chemin brut. Compatibilité legacy intégrale : un appelant passant une simple chaîne continue de fonctionner sans migration, normalisé en interne vers `role=pose_composition`.

**Distinction stricte entre modèle de collection et capacité de génération réellement livrée** : `reference_images` reste une collection `List[Union[str, Reference]]` conçue pour recevoir un jour 0..N références typées, mais la capacité de génération réellement livrée par cette mission reste strictement **0..1 référence actionnable**. Aucune référence → `txt2img` inchangé. Une référence de rôle `pose_composition` → `img2img` inchangé, un seul appel `upload_image()`, résultat transmis à `generate_image()` sans modification. Une référence de tout autre rôle → `GenerationError` explicite avant tout upload. Plusieurs références (quel que soit leur rôle) → `GenerationError` explicite indiquant que la représentation multi-références existe mais que la génération simultanée n'est pas encore supportée — aucun upload tenté, aucun fallback silencieux, aucun choix implicite de « la première » référence.

Aucun changement `ComfyUIEngine`/`comfyui_workflows.py`/Domain/EventBus. Aucune constante ou enum créée pour les rôles futurs (identité, tenue, décor/environnement, style) — documentés en prose uniquement dans les docstrings, pour éviter toute taxonomie morte. Ne livre ni intégration IP-Adapter/ControlNet/InstantID/PuLID, ni génération simultanée multi-références, ni « Dataset de références → Inference ».

### Tests ajoutés (Mission 056)

- 6 tests nets nouveaux dans `test_generation_manager.py` (aucun nouveau fichier) : nouvelle classe `GenerationManagerTypedReferenceTest` — `Reference(path, "pose_composition")` explicite reproduit exactement le comportement legacy ; rôle non supporté lève `GenerationError` avant tout upload et sans passer `busy` à `True` ; deux références (rôles mêlés) lèvent une erreur distincte avant tout upload ; valeur de la constante `REFERENCE_ROLE_POSE_COMPOSITION` ; `Reference` strictement minimal (`path`, `role`, aucun champ supplémentaire).
- `test_inference_page.py` : 4 assertions `reference_images=[...]` migrées de chaînes brutes vers `Reference(...)`, 2 assertions de libellé mises à jour (`"<fichier> — Pose / composition"`), aucun nouveau test — preuve directe qu'`InferencePage` construit désormais réellement un `Reference`.
- **956/956 tests verts** au total (950 précédents + 6 nets nouveaux) : `test_generation_manager.py` 33/33, `test_inference_page.py` 78/78.
- **Smoke test manuel réel du rendu Qt, PASS** (21/21 assertions) — génération réelle sans référence (`reference_image=None`, aucun upload), sélection réelle via le vrai `QFileDialog` (libellé naturel affiché, jamais le terme technique brut), génération réelle avec la référence (`upload_image()` appelé exactement une fois, résultat transmis inchangé à `generate_image()` avec `denoise=0.75`), Regenerate/Reject réels sans régression, appel contrôlé avec un rôle non supporté prouvant zéro upload et zéro génération.

### État du projet (Mission 056)

`InferencePage`/`GenerationManager` disposent désormais d'une fondation structurelle réelle pour les références typées, immédiatement utilisée par le flux mono-référence de production — pas une abstraction vide « pour plus tard ». Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `f095b74c07b63ba5d5293cef8684e4acb0400f9c` — `feat: introduce typed Inference reference primitive`, tag `v0.2-mission056`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et **non résolu** : la primitive typée nécessaire existe désormais, mais l'intégration pratique reste bloquée sur un premier mécanisme moteur réel pour un second rôle, puis sur la consommation simultanée de plusieurs références — chacun nécessitant son propre audit dédié.

---

## v0.2-mission055 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 055 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 055)

**Mission 055 — Graceful Settings Save Errors.** Un audit factuel du dépôt post-Mission 054 a révélé une exception définie et réellement levée, mais jamais interceptée nulle part : `ApplicationSettingsStorageError`, levée par `ApplicationSettingsStorage.save()` en cas d'échec d'écriture, dont la propagation non capturée était documentée et volontaire au niveau `ApplicationSettingsManager`, mais jamais traitée en amont côté UI. Le même défaut existait pour les Workspace Settings : `SettingsPage.save_settings()` ne capturait pas `WorkspaceManagerError`, alors que ce type est déjà intercepté quatre fois ailleurs dans `main_window.py` pour toute autre opération de sauvegarde du Workspace.

`SettingsPage.save_settings()`/`save_application_settings()` interceptent désormais respectivement `WorkspaceManagerError`/`ApplicationSettingsStorageError` et affichent `QMessageBox.critical(self, "Erreur", str(exc))` — remploi exact de la convention déjà validée quatre fois dans `main_window.py`, aucun nouveau texte métier inventé. Le chemin de succès reste strictement inchangé, l'UI reste pleinement utilisable après une erreur (champs/boutons toujours activés), et un second enregistrement réel réussit une fois la cause corrigée.

Aucun changement Domain/Manager/Storage/EventBus — mission strictement additive côté UI. Ne résout ni la refonte Settings, ni l'exploitation de `comfyui_path`, ni l'organisation multi-engine.

### Tests ajoutés (Mission 055)

- 5 tests nets nouveaux dans `test_settings_page.py` (aucun nouveau fichier) : nouvelle classe `SettingsPageSaveErrorTest` — échec `ApplicationSettingsStorageError` intercepté sans lever, `ApplicationSettings` inchangés en mémoire après l'échec, page réutilisable pour un vrai enregistrement ensuite ; échec `WorkspaceManagerError` intercepté sans lever, champs/bouton toujours activés, page réutilisable pour un vrai enregistrement ensuite.
- **950/950 tests verts** au total (945 précédents + 5 nets nouveaux) : `test_settings_page.py` 33/33, non-régression Settings (`test_settings_roundtrip.py`/`test_application_settings_roundtrip.py`/`test_main_window_comfyui_settings.py`/`test_main_window_ollama_settings.py`) 29/29.
- **Smoke test manuel réel du rendu Qt, PASS** — échec réel du système de fichiers pour Application Settings (aucun mock sur le chemin d'échec lui-même : cible occupée par un vrai sous-dossier, `OSError` réelle enveloppée en `ApplicationSettingsStorageError` réelle), patch contrôlé pour Workspace Settings (rendre un dossier réellement inaccessible en écriture s'étant avéré peu fiable sous Windows dans cet environnement) — dans les deux cas, `QMessageBox.critical` confirmé invoqué, aucun crash, UI confirmée réutilisable, second enregistrement réel confirmé fonctionnel après correction de la cause.

### État du projet (Mission 055)

Les deux boutons « Enregistrer » de `SettingsPage` (Workspace Settings et Application Settings) traitent désormais gracieusement un échec d'écriture réel, au même titre que toute autre opération de sauvegarde de l'application. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `6469193f0e189a85525c3d3168851c54f69455b9` — `fix: handle Settings save errors gracefully`, tag `v0.2-mission055`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et non résolu, dépendant toujours de l'introduction d'une primitive Inference 0..N références avec rôles qui n'existe pas encore.

---

## v0.2-mission054 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 054 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 054)

**Mission 054 — Rename Dataset and Training after Creation.** Étend à `Dataset` et `Training` le renommage post-création déjà livré pour `Character`/`Model`/`Workflow`/`LoRA`/`Prompt` — refermant la dernière asymétrie de renommage de l'application. `Dataset` et `Training` ne possédaient encore, avant cette mission, **aucune** méthode `update()` d'aucune sorte ; `update_name()` en est la toute première pour chacun des deux Managers, mais le contrat, entièrement dicté par les cinq précédents directs, ne comportait aucune décision produit ou architecturale substantielle restant ouverte.

`DatasetManager.update_name(name)` et `TrainingManager.update_name(name)` opèrent implicitement sur `self.active_dataset`/`self.active_training` (mirroir de `ModelManager.update_name()`/`PromptManager.update_name()`, pas du style `lora_id` explicite de `LoRAManager.update_name()`) : `False`/aucun `save()` si aucune entité active ou si le nom est identique à la valeur stockée, aucun événement dédié publié, chaîne vide légitime et non validée.

Côté UI, `DatasetsPage` et `TrainingPage` gagnent chacune un champ `name_edit` éditable, renommé sur `editingFinished`, sans bouton ni dialogue dédié. `dataset_id`/`training_id`, `Dataset.images` et `Training.dataset_id` restent strictement inchangés par un renommage — une Training référençant un Dataset renommé continue de pointer vers le même `dataset_id`, et `TrainingPage.dataset_label` reflète le nouveau nom du Dataset sans aucun nouveau wiring EventBus, via le seul canal `WORKSPACE_SAVED` déjà souscrit.

Comportement de tri confirmé et **délibérément asymétrique** entre les deux entités : `training_list` (triée depuis Mission 051) se retrie automatiquement après un renommage, sélection conservée par `training_id`. `dataset_list` n'a jamais été triée (hors périmètre de Mission 051, vérifié par relecture directe du code) et Mission 054 n'y introduit aucun tri nouveau — le Dataset renommé garde simplement sa position d'insertion, sélectionné par `dataset_id`.

Aucun changement Domain/EventBus.

### Tests ajoutés (Mission 054)

- 24 tests nets nouveaux, aucun nouveau fichier : 8 `DatasetManagerRenameTest` + 5 `DatasetsPageRenameTest` (`test_dataset_roundtrip.py`), 6 `TrainingManagerRenameTest` + 5 `TrainingPageRenameTest` (`test_training_roundtrip.py`).
- Couverture : renommage réel via le vrai widget, idempotence, `dataset_id`/`training_id`/`images`/`dataset_id` de Training préservés, référence Training→Dataset conservée par ID après renommage du Dataset, `dataset_list` confirmée en ordre d'insertion après renommage, `training_list` confirmée retriée dans les deux sens avec sélection par ID, `TrainingPage.dataset_label` confirmée rafraîchie, aucune entité active → no-op, persistance après fermeture/réouverture.
- **945/945 tests verts** au total (921 précédents + 24 nets nouveaux), suite ciblée : `test_dataset_roundtrip.py` 49/49, `test_datasets_page.py` 45/45, `test_training_roundtrip.py` 34/34.
- **Smoke test manuel réel du rendu Qt, PASS** — Dataset avec image physique réelle référencé par une Training réelle : renommage réel des deux entités, IDs et relation préservés, `dataset_label` rafraîchi, `is_referenced_by_training()` toujours vrai, non-régression de `add_images()`/`remove_images()`, persistance confirmée après fermeture/réouverture réelle du Workspace.

### État du projet (Mission 054)

Toutes les entités possédant un champ `name` (`Character`, `Model`, `Workflow`, `LoRA`, `Prompt`, `Dataset`, `Training`) sont désormais renommables après leur création — dernière asymétrie de renommage de l'application résolue. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `a892f57b3f6fabffcc84203b0417a622fb80974d` — `feat: rename Dataset and Training after creation`, tag `v0.2-mission054`, GitHub Release publiée). Le besoin futur « Dataset de références → Inference » reste documenté et non résolu, dépendant toujours de l'introduction d'une primitive Inference 0..N références avec rôles qui n'existe pas encore.

---

## v0.2-mission053 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 053 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 053)

**Mission 053 — Rename Prompt after Creation.** Étend à `Prompt` le renommage post-création déjà livré pour `Model`, `Workflow` et `LoRA` par Mission 052 — la seule exclusion de Mission 052, dont le mini-audit dédié a confirmé qu'elle ne comportait en réalité aucune incompatibilité avec le dirty-state introduit par Mission 038.

`PromptManager` gagne une nouvelle méthode sibling additive **`update_name(name)`**, mirroir exact du contrat idempotent déjà établi par `update_text()` : opère implicitement sur `self.active_prompt`, `False`/aucun `save()` si aucun prompt actif ou si `name` est identique à la valeur stockée, aucun événement dédié publié, `text` jamais touché.

Côté UI, `PromptsPage` gagne un champ `name_edit` éditable, peuplé à l'intérieur de `_refresh_prompt_list()` et renommé sur `editingFinished`, sans bouton ni dialogue dédié. `name_edit` est entièrement indépendant du mécanisme de dirty-state de Mission 038 : `_dirty`/`_loaded_prompt_id` restent pilotés exclusivement par `text_edit.textChanged`, jamais par le renommage. Un brouillon non sauvegardé survit intact à un renommage — texte affiché inchangé, `_dirty` toujours `True` — et `save_text()` reste pleinement fonctionnel ensuite.

`prompt_id` et le texte persisté restent strictement inchangés par un renommage. Le renommage interagit correctement avec le tri alphabétique de Mission 051 : la liste se retrie automatiquement, dans les deux sens, tandis que la sélection reste sur l'entité renommée par **ID**, jamais par position d'affichage. Politique de validation du nom identique au précédent de Mission 052 : aucune (pas de `.strip()`, pas de rejet du vide, pas de contrainte d'unicité).

Aucun changement Domain/EventBus. `Dataset` et `Training` restent explicitement hors périmètre — aucune méthode `update()` d'aucune sorte n'existe encore pour ces deux entités.

### Tests ajoutés (Mission 053)

- 8 tests nets nouveaux dans `test_prompt_roundtrip.py` (aucun nouveau fichier) : 2 dans `PromptRoundTripTest` (`test_update_name_is_idempotent`, `test_rename_persists_after_close_reopen`) et 6 dans la nouvelle classe `PromptsPageRenameTest`.
- Couverture : renommage réel via le vrai widget, idempotence, `prompt_id`/texte préservés, retri correct dans les deux sens avec sélection conservée par ID, aucun prompt actif → no-op, persistance après fermeture/réouverture. Le test `test_rename_with_unsaved_text_preserves_dirty_state_and_draft` couvre le scénario critique explicitement requis : texte non sauvegardé → renommage → retri → dirty-state et brouillon intacts → `save_text()` toujours fonctionnel ensuite.
- **921/921 tests verts** au total (913 précédents + 8 nets nouveaux), suite ciblée : `test_prompt_roundtrip.py` 73/73 OK, confirmant l'absence de régression sur le Prompt Assistant, « Envoyer vers Inference » et « Enregistrer comme nouveau Prompt… ».
- **Smoke test manuel réel du rendu Qt, PASS** — renommage réel via `name_edit`, retri confirmé, sélection conservée par ID, texte sauvegardé jamais touché, brouillon non sauvegardé confirmé intact après renommage, `save_text()` confirmé fonctionnel ensuite, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 053)

L'asymétrie de renommage entre `Character`/`Model`/`Workflow`/`LoRA` (renommables) et `Prompt` (jusque-là non renommable) est désormais résolue. Seuls `Dataset`/`Training` restent explicitement non renommables — candidats probables pour une mission future distincte, chacun nécessitant l'introduction de sa toute première méthode `update()`. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `97384521ee1b487280707593c009305359893891` — `feat: rename Prompt after creation`, tag `v0.2-mission053`, GitHub Release publiée).

---

## v0.2-mission052 — 2026-08-24

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 052 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 052)

**Mission 052 — Rename Model, Workflow and LoRA after Creation.** Étend à `Model`, `Workflow` et `LoRA` la capacité de renommage post-création déjà disponible pour `Character` (`CharacterManager.update(name=...)`) — un écart mécanique découvert par audit direct du code, pas un besoin déjà documenté.

Chaque Manager gagne une nouvelle méthode sibling additive **`update_name(...)`**, suivant le même contrat idempotent déjà établi par `update_file_path()`/`update_text()`/`update()` : `ModelManager.update_name(name)` et `WorkflowManager.update_name(name)` opèrent sur l'entité active (mirroir de `update_file_path()`), `LoRAManager.update_name(lora_id, name)` cible par `lora_id` explicite (mirroir de `update()`). Aucune méthode existante n'est renommée ou fusionnée ; aucun événement dédié n'est publié — `WORKSPACE_SAVED` suffit déjà à déclencher le rafraîchissement des Pages déjà abonnées.

Côté UI, `ModelsPage`/`WorkflowsPage`/`LoRAPage` gagnent un champ `name_edit` éditable, renommage déclenché sur `editingFinished` (perte de focus/Entrée), sans bouton ni dialogue dédié — cohérent avec le mécanisme d'édition immédiate déjà en place pour `file_path_edit`/les champs Metadata LoRA. Pour LoRA, `name_edit` reste explicitement hors du panneau Metadata (Mission 047), n'interfère pas avec le bouton « Enregistrer les métadonnées ». Politique de validation du nom : aucune (pas de `.strip()`, pas de rejet du vide, pas de contrainte d'unicité) — mirroir exact du seul précédent de renommage existant, `CharactersPage.save_identity()`.

`model_id`/`workflow_id`/`lora_id` et toute autre propriété (`file_path` ; `LoRA.files`/`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`) restent strictement inchangés par un renommage. Le renommage interagit correctement avec le tri alphabétique de Mission 051 : la liste se retrie automatiquement après un renommage, dans les deux sens (déplacement vers le début ou la fin de liste), tandis que la sélection reste sur l'entité renommée par **ID**, jamais par position d'affichage.

Aucun changement Domain/EventBus. `Prompt`, `Dataset`, `Training` et `Character` sont explicitement hors périmètre — `Prompt` a une structure de Page incompatible (dirty-state), `Dataset`/`Training` n'ont aujourd'hui aucune méthode `update()` d'aucune sorte, `Character` dispose déjà de cette capacité.

### Tests ajoutés (Mission 052)

- 28 tests nets nouveaux, répartis sur trois suites existantes (aucun nouveau fichier) : `test_model_roundtrip.py` (+7, dont `ModelsPageRenameTest`), `test_workflow_roundtrip.py` (+7, mirroir exact), `test_lora_roundtrip.py` (+14 — `LoRAManagerRenameTest` 7 + `LoRAPageRenameTest` 7).
- Chaque suite couvre : renommage réel, idempotence (aucun `save()` si valeur inchangée), `save()` appelé une seule fois lors d'une mutation réelle, préservation de l'ID et des autres propriétés, chaîne vide légitime, entité/`lora_id` inconnu → `False`, persistance après fermeture/réouverture, renommage via le vrai widget Qt, retri correct dans les deux sens avec sélection conservée par ID. `LoRAPageRenameTest` ajoute la non-régression explicite de `add_files()`/`remove_files()`/`save_metadata()`/`set_thumbnail()` après un renommage.
- **913/913 tests verts** au total (885 précédents + 28 nets nouveaux), suite ciblée : 28/28 OK (`test_model_roundtrip.py` 20/20, `test_workflow_roundtrip.py` 21/21, `test_lora_roundtrip.py` 67/67).
- **Smoke test manuel réel du rendu Qt, PASS** — renommage réel via `name_edit` sur les trois Pages, retri confirmé dans les deux sens, sélection conservée par ID, `file_path`/`LoRA.files`/Metadata/thumbnail confirmés intacts, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 052)

L'asymétrie de renommage entre `Character` (déjà renommable) et `Model`/`Workflow`/`LoRA` (jusque-là non renommables) est désormais résolue. `Prompt`/`Dataset`/`Training` restent explicitement non renommables — candidats probables pour une mission future distincte, chacun nécessitant son propre audit (structure de Page différente pour `Prompt`, absence totale d'`update()` pour `Dataset`/`Training`). Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `a0e792e9cc6f321c29af673a4755ca4abeb77ed6` — `feat: rename Model, Workflow and LoRA after creation`, tag `v0.2-mission052`, GitHub Release publiée).

---

## v0.2-mission051 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 051 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 051)

**Mission 051 — Sort Remaining Entity Lists by Name.** Étend aux cinq dernières listes d'entités de l'application (`ModelsPage.model_list`, `WorkflowsPage.workflow_list`, `TrainingPage.training_list`, `PromptsPage.prompt_list`, `LoRAPage.lora_list`) le tri par nom déjà livré pour les galeries `ImagesPage`/`DatasetsPage` par Mission 048 — la dernière dette de tri d'affichage encore ouverte dans l'application.

Chaque Page trie désormais sa liste par `name`, **alphabétique (A → Z), insensible à la casse, toujours actif, sans aucun contrôle UI** (pas de combobox/bouton — un seul critère de tri existant pour ces cinq entités, contrairement aux galeries Images/Datasets où Mission 049 a dû introduire un sélecteur Nom/Date). Le tri (`sorted()`, garanti stable par Python) est appliqué sur une **copie temporaire** construite juste avant la boucle de peuplement de chaque `QListWidget` — `Workspace.models`/`.workflows` et `Character.loras`/`.prompts`/`.trainings` (Domain) ne sont **jamais mutés ni réordonnés**.

Changement strictement Presentation : aucune modification de `Model`/`Workflow`/`Prompt`/`Training`/`LoRA` (Domain), d'aucun Manager, ni d'aucun wiring EventBus. `PromptsPage._refresh_prompt_list()` reçoit le tri sans toucher au dirty-state, à l'éditeur, au Prompt Assistant, à « Send to Inference » ni à « Save as New Prompt ». `LoRAPage.update_loras()` ne trie que `lora_list` — la boucle `files_list` introduite par Mission 050 reste intacte, ainsi que `LoRA.files`/Metadata/thumbnail.

### Tests ajoutés (Mission 051)

- 26 tests nets nouveaux, répartis sur les cinq suites existantes (aucun nouveau fichier) : `ModelsPageSortTest` (5), `WorkflowsPageSortTest` (5), `TrainingPageSortTest` (5), `PromptsPageSortTest` (6 — un test dédié à la non-régression du dirty-state/`save_text()`), `LoRAPageSortTest` (5 — un test dédié confirmant `LoRA.files`/Metadata/thumbnail intacts après sélection sur liste triée).
- Chaque classe couvre : affichage alphabétique insensible à la casse, préservation de l'ordre d'insertion de la collection Domain source, stabilité du tri à noms identiques, sélection/édition ciblant correctement la bonne entité malgré un déplacement d'affichage, retri correct après un second rafraîchissement.
- **885/885 tests verts** au total (859 précédents + 26 nets nouveaux), suite ciblée : 26/26 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — cinq scénarios réels (un par Page), tri visuel confirmé, sélection après tri confirmée cibler la bonne entité, collections Domain confirmées non réordonnées par inspection directe, dirty-state/éditeur `PromptsPage` et `LoRA.files`/Metadata/thumbnail confirmés intacts.

### État du projet (Mission 051)

La dette de tri d'affichage, résolue pour les galeries Images/Datasets par Mission 048/049, est désormais résolue pour l'ensemble des listes d'entités de l'application. Aucun nouveau besoin distinct identifié en retour par cette mission — changement purement Presentation, sans impact Domain/Manager/EventBus. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `0d6a2c54a79dc42701c1c250e8f63167857e948c` — `feat: sort Models, Workflows, Trainings, Prompts and LoRAs lists by name`, tag `v0.2-mission051`, GitHub Release publiée).

---

## v0.2-mission050 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 050 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 050)

**Mission 050 — Remove Individual Files from a LoRA.** Referme un manque symétrique à `add_files()` : `LoRAManager` ne proposait aucune méthode pour retirer un fichier individuel d'une LoRA, seule la suppression de la LoRA entière (`delete_lora()`) existait — une conséquence devenue plus coûteuse depuis Mission 047, qui a rendu la fiche LoRA (`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`) réellement éditable et donc perdable en cas de suppression complète pour corriger un simple fichier mal importé.

`LoRAManager.remove_files(paths: List[str]) -> int` retire les chemins correspondants de `LoRA.files` par **égalité de chaîne exacte** (même convention que `add_files()` — jamais une résolution/normalisation de chemin, puisque `LoRA.files` référence toujours des fichiers externes jamais copiés physiquement), sauvegarde uniquement si une mutation réelle a eu lieu, ne touche jamais le fichier physique ni `name`/`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`.

`LoRAPage.files_list` passe en `QListWidget.ExtendedSelection` (retrait multiple en une seule opération), nouveau bouton « Retirer les fichiers sélectionnés » activé uniquement si une LoRA active existe et qu'au moins un fichier est sélectionné (mirroir de `_update_metadata_buttons_state()`). Aucune confirmation avant retrait — cohérent avec le précédent non destructif établi par Mission 045. Retirer la dernière référence laisse simplement `LoRA.files == []`, la LoRA restant pleinement valide avec sa fiche de métadonnées intacte.

**Distinction explicite** : cette mission ne retire qu'une **référence** dans `LoRA.files` — à aucun moment un fichier n'est supprimé, déplacé ou copié sur disque, à la différence de `ImagesPage.delete_selected_images()` (Mission 046) qui peut supprimer physiquement un fichier interne au Workspace. Aucun changement Domain/EventBus ; rafraîchissement via le seul canal `WORKSPACE_SAVED` déjà existant.

**Ne résout ni la sélection de LoRA multi-engine ni une gestion générale des assets** — ces besoins restent entièrement ouverts.

### Tests ajoutés (Mission 050)

- 19 tests nets nouveaux : nouvelle classe `LoRAManagerRemoveFilesTest` (9 tests — retrait simple/multiple, chemin inconnu sans sauvegarde, sauvegarde uniquement si mutation réelle, retrait de la dernière entrée, sans LoRA active, fichier physique confirmé intact, métadonnées/miniature confirmées inchangées, persistance après fermeture/réouverture) et extension de `LoRARoundTripTest` (10 tests, widgets Qt réels — `ExtendedSelection`, activation/désactivation du bouton, retrait simple/multiple réel, no-op sans sélection, liste vide après dernier retrait, changement de LoRA active, Métadonnées/miniature intactes après retrait).
- **859/859 tests verts** au total (840 précédents + 19 nets nouveaux), suite ciblée : 19/19 OK (48/48 sur `test_lora_roundtrip.py` au total).
- **Smoke test manuel réel du rendu Qt, PASS** — 3 fichiers externes réels importés, fiche Métadonnées et miniature réellement remplies, retrait réel de 2 fichiers sur 3 confirmé (fichiers physiques toujours présents, Métadonnées/miniature strictement intactes), retrait du dernier fichier confirmé (`files == []`, LoRA toujours valide), persistance confirmée après fermeture/réouverture réelle du Workspace.

### État du projet (Mission 050)

Le retrait de fichier individuel d'une LoRA, absent depuis l'origine et devenu plus coûteux depuis Mission 047, est désormais **résolu**. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission — la sélection de LoRA multi-engine et la gestion générale des assets restent explicitement hors périmètre. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `14ffc9c25367707a52ef7ae8f87e105f19016603` — `feat: add removing individual files from a LoRA`, tag `v0.2-mission050`, GitHub Release publiée).

---

## v0.2-mission049 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 049 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 049)

**Mission 049 — Sort Images and Dataset Galleries by File Date.** Referme le tri par date resté ouvert depuis Mission 048 : `ImagesPage` et `DatasetsPage` gagnent un contrôle explicite « Trier par : » à deux critères fixes — **Nom (A → Z)** (inchangé depuis Mission 048) et **Date du fichier (plus récent d'abord)**.

Le tri par date est fondé sur `Path(file_path).stat().st_mtime`, ordre décroissant, tri stable, via un petit helper Presentation partagé (`file_mtime_sort_key()`, `src/ui/thumbnails.py`) — aucun nouveau champ Domain, aucune modification de `Image.to_dict()`/`from_dict()`, aucune migration des anciens `project.json`.

**Compromis explicitement accepté** : `WorkspaceStorage.copy_into_workspace()` utilise `shutil.copy2()`, qui préserve le `mtime` du fichier source lors d'un import. Une photo ancienne importée aujourd'hui conserve donc son ancien `mtime` — le tri reflète la **date de dernière modification du fichier sur disque**, jamais sa **date d'ajout au Workspace/Dataset**. Ce comportement est volontaire pour cette mission, aucun mécanisme de date d'import n'est introduit.

Un fichier dont `stat()` échoue (supprimé, inaccessible, ...) retombe sur une clé `float("-inf")` — la plus petite valeur possible — le plaçant systématiquement en toute dernière position sous un tri décroissant, jamais accidentellement en tête. Plusieurs fichiers manquants conservent leur ordre relatif d'origine (tri stable). Le critère sélectionné est un état de session propre à chaque Page : il survit aux rafraîchissements `WORKSPACE_SAVED` et aux changements de Dataset actif sans être réinitialisé, mais n'est pas persisté au-delà de la session. Aucun changement Manager ou EventBus — `Workspace.images`/`Dataset.images` conservent toujours leur ordre stocké d'origine, le tri ne s'appliquant que sur une copie temporaire, exactement comme Mission 048.

### Tests ajoutés (Mission 049)

- 17 tests nets nouveaux, étendant `ImagesPageGallerySortTest`/`DatasetsPageGallerySortTest` (Mission 048, aucun nouveau fichier) : tri par date décroissant sur `mtime` réels échelonnés (`os.utime()`), fichier interne et externe, fichier manquant en fin de liste, plusieurs fichiers manquants et `mtime` identiques tous deux stables, bascule réelle Nom↔Date via le `QComboBox`, critère conservé après un `WORKSPACE_SAVED` réel et après un changement de Dataset actif, ordre `Workspace.images`/`Dataset.images` confirmé inchangé.
- **840/840 tests verts** au total (823 précédents + 17 nets nouveaux), suite ciblée : 17/17 OK, non-régression `test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py` : 128/128 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — fichiers à noms désordonnés/casse mixte et `mtime` explicitement échelonnés importés dans les deux galeries ; bascule réelle du contrôle confirmée décroissante dans `ImagesPage` et `DatasetsPage` ; fichier manquant confirmé en fin de liste sans exception ; critère confirmé conservé après un rafraîchissement `WORKSPACE_SAVED` réel ; `Workspace.images`/`Dataset.images` confirmés inchangés par inspection directe.

### État du projet (Mission 049)

Le besoin "tri de la galerie Images" (identifié Mission 023) est désormais **entièrement résolu** — tri par nom (Mission 048) et tri par date (Mission 049) tous deux livrés. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `8deae97e9c15b7bb27b57c8df3b4a2101468a4d9` — `feat: add sorting Images and Dataset galleries by file date`, tag `v0.2-mission049`, GitHub Release publiée).

---

## v0.2-mission048 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 048 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 048)

**Mission 048 — Sort Images and Dataset Galleries by Filename.** Les galeries `ImagesPage` et `DatasetsPage` sont désormais triées, toujours actif, facilitant la recherche d'une image précise à mesure que la collection d'un projet grandit.

Le tri est calculé sur `Path(file_path).name`, **insensible à la casse**, via le `sorted()` stable de Python — deux éléments partageant la même clé après normalisation de casse conservent leur ordre relatif d'origine. Appliqué de façon cohérente à **`ImagesPage`** (galerie principale du Workspace) et **`DatasetsPage`** (galerie du Dataset actif). Le tri est purement un ordre d'affichage : calculé sur une copie temporaire juste avant peuplement de la galerie — **aucune mutation de `Workspace.images` ni de `Dataset.images`**, qui conservent tous deux leur ordre d'insertion d'origine dans les données du projet. Aucun contrôle UI n'est introduit : pas de combobox/bouton de critère, pas d'ordre ascendant/descendant configurable, pas de préférence persistée — la galerie est simplement toujours affichée triée par nom.

Un test existant qui localisait un item par sa position d'insertion (`test_missing_file_item_still_created_with_fallback_icon_and_user_role`) a été rendu indépendant de cet ordre — il localise désormais l'item par identité (`Qt.UserRole`), comme son voisin déjà existant. Aucun changement de ce que le test vérifie réellement. Aucun changement Domain, Manager, ou EventBus — modification strictement confinée à la couche Presentation.

### Tests ajoutés (Mission 048)

- Nouvelles classes `ImagesPageGallerySortTest` et `DatasetsPageGallerySortTest` (6 tests chacune, 12 au total) — tri alphabétique sur noms volontairement désordonnés et de casse mixte, stabilité pour deux fichiers de même nom affiché, `Workspace.images`/`Dataset.images` confirmés dans leur ordre d'insertion d'origine, re-tri confirmé après un second `WORKSPACE_SAVED`, sélection/aperçu confirmés fonctionnels après réordonnancement de l'affichage.
- **823/823 tests verts** au total (811 précédents + 12 nets nouveaux), suite ciblée : 12/12 OK, non-régression `test_images_page.py`/`test_datasets_page.py`/`test_dataset_roundtrip.py` : 111/111 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — noms désordonnés et casse mixte importés dans les deux galeries, ordre affiché confirmé sorté alphabétiquement ; stabilité confirmée ; sélection et aperçu confirmés fonctionnels après réordonnancement ; `Workspace.images`/`Dataset.images` confirmés inchangés dans leur ordre d'insertion d'origine par inspection directe.

### État du projet (Mission 048)

Le besoin "tri de la galerie Images" (identifié Mission 023) est **partiellement résolu** — le tri par nom est désormais livré. **Le tri par date reste explicitement ouvert et non traité par cette mission** — besoin précisé par l'architecte : permettre d'afficher notamment les images les plus récentes en premier. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `714b40e41dc5f72245a3a5d524f716eee2519c1c` — `feat: sort Images and Dataset galleries by filename`, tag `v0.2-mission048`, GitHub Release publiée).

---

## v0.2-mission047 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 047 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 047)

**Mission 047 — LoRA Metadata Fiche.** Rend enfin éditables et persistantes les métadonnées LoRA prévues par le Domain depuis l'origine (Mission 006), jamais exposées jusqu'ici : un audit exhaustif avait confirmé que `LoRA.engine`/`.architecture`/`.trigger_word`/`.version`/`.thumbnail` restaient bloqués à `""` de façon permanente, aucun Manager ni aucune Page ne les exposant.

`LoRAPage` gagne une section « Métadonnées » pour la LoRA active — 4 champs texte libres (Engine/Architecture/Trigger word/Version, aucune liste fermée, aucune taxonomie multi-engine prématurée) sauvegardés uniquement via le bouton explicite « Enregistrer les métadonnées » (aucun auto-save), et un aperçu de miniature avec bouton « Choisir une miniature… ». Nouvelle `LoRAManager.update(lora_id, engine=None, architecture=None, trigger_word=None, version=None)`, strictement idempotente (mirroir exact de `CharacterManager.update()`).

Nouvelle `LoRAManager.set_thumbnail(lora_id, source_path)`, distincte car elle exécute une opération d'E/S réelle : un mini-audit dédié a révélé une tension architecturale réelle entre le Blueprint (LoRA documentée comme ressource partagée entre Workspaces) et le précédent `LoRAManager.add_files()` (jamais copié) d'une part, et l'ergonomie voulue pour l'aperçu d'autre part — tranchée explicitement par l'architecte après présentation de deux options : la miniature choisie est copiée via `WorkspaceStorage.copy_into_workspace()` vers `<workspace_root>/models/loras/<lora_id>/`, **tandis que `LoRA.files` reste strictement inchangé, toujours externe**. Échec de copie : `LoRA.thumbnail` reste strictement inchangé, aucune sauvegarde partielle, échec signalé (`None` + avertissement UI) — jamais de perte silencieuse de la miniature existante. Aucune migration implicite d'une ancienne valeur `thumbnail` déjà persistée. Aucun changement Domain/EventBus, aucun nouveau wiring (`WORKSPACE_SAVED`/`LORA_DELETED` existants suffisent).

### Tests ajoutés (Mission 047)

- Nouvelle classe `LoRAManagerMetadataTest` dans `test_lora_roundtrip.py` (13 tests) — `update()` : mutation réelle et persistance, idempotence (valeur identique → `False`), `None` laisse un champ inchangé, chaîne vide acceptée comme valeur légitime, LoRA inconnue → `False` ; `set_thumbnail()` : copie réelle sous `models/loras/<lora_id>/` (source externe intacte), source déjà interne réutilisée sans nouvelle copie, `LoRA.files` jamais touché, échec de copie (`WorkspaceStorageError` simulée) → `None` et valeur précédente strictement conservée, LoRA inconnue → `None`, persistance après fermeture/réouverture, remplacement d'une miniature existante → nouvelle copie distincte, ancien fichier laissé intact.
- `LoRARoundTripTest` (6 tests nets nouveaux, widgets Qt réels) — fiche vidée/désactivée sans LoRA active, repeuplée à la sélection puis correctement remplacée au changement de LoRA, sauvegarde réelle des 4 champs via le bouton dédié, sélection réelle d'un fichier de miniature copiant le fichier et affichant un `QPixmap` réel, repli exact (`UNAVAILABLE_MESSAGE`) pour un `thumbnail` manquant, échec de copie → avertissement affiché et valeur précédente conservée.
- **811/811 tests verts** au total (792 précédents + 19 nets nouveaux), suite ciblée `test_lora_roundtrip.py` : 29/29 OK (10 précédents + 19 nouveaux).
- **Smoke test manuel réel du rendu Qt, PASS** — édition réelle des 4 champs et sauvegarde confirmées, sélection réelle d'une miniature externe copiée sous le Workspace avec aperçu réel affiché, fichier LoRA lui-même confirmé binaire-identique avant/après, changement/suppression de LoRA correctement reflétés, persistance des métadonnées et du fichier de miniature confirmée après fermeture/réouverture réelle.

### État du projet (Mission 047)

Les métadonnées LoRA (`engine`/`architecture`/`trigger_word`/`version`/`thumbnail`), sérialisées depuis l'origine mais jamais exposées, sont désormais **résolues**. La sélection de LoRA multi-engine/multi-moteur, toute taxonomie fermée pour `engine`/`architecture`, le renommage de la LoRA et tout système de gestion d'assets général restent explicitement hors périmètre et non traités — besoins distincts, non refermés par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `9afc3a2f32be3aaeef9d64448f8720b6bc23b58e` — `feat: add editable LoRA metadata fiche with Workspace-owned thumbnail`, tag `v0.2-mission047`, GitHub Release publiée).

---

## v0.2-mission046 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 046 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 046)

**Mission 046 — Remove Images from the Workspace Gallery.** Referme la dette distincte laissée ouverte par Mission 045 : `ImagesPage`/`Workspace.images` — la galerie principale du Workspace — ne proposait aucune suppression d'image, à la différence de `DatasetsPage` qui sait déjà retirer une référence (Mission 045) ou supprimer un Dataset entier.

Un mini-audit dédié a établi qu'un `Image.file_path` de `Workspace.images` n'est **pas** garanti physiquement interne au Workspace (chemins externes/hérités déjà tolérés et testés avant cette mission) — la politique produit retenue est donc : suppression physique réelle (`Path.unlink()`) uniquement pour un fichier à la fois interne (`WorkspaceStorage.is_inside()`) et présent sur disque ; tout fichier externe ou manquant voit seulement sa référence retirée de `Workspace.images`, sans jamais exposer cette distinction technique à l'utilisateur. Toute image encore référencée par un Dataset bloque atomiquement la suppression de l'ensemble de la sélection — `WorkspaceManager` re-vérifie lui-même la référence, jamais une simple confiance envers un pré-contrôle UI (même schéma d'autorité que `DatasetManager.delete()`).

`ImagesPage` gagne un bouton « Supprimer », `list_widget` passant en sélection étendue (`ExtendedSelection`) pour un retrait multiple en une opération. Une confirmation explicite est désormais obligatoire avant toute mutation, avec trois libellés dédiés selon la composition de la sélection (tout supprimable, tout retrait de référence seul, mixte avec comptage). Nouvelles primitives `WorkspaceManager.images_referenced_by_datasets(paths)`, `preview_image_removal(paths) -> RemovalPreview` et `remove_images(paths) -> RemovalResult` (`NamedTuple`, même convention qu'`ImportResult`/`CollisionInfo`). Le retrait de référence Dataset (Mission 045) et la suppression réelle Workspace (Mission 046) restent deux mécanismes fonctionnellement distincts et non confondus. Aucun changement Domain/EventBus, `DatasetsPage`/`DatasetManager` strictement inchangés.

### Tests ajoutés (Mission 046)

- Nouvelle classe `WorkspaceManagerRemoveImagesTest` dans `test_workspace_roundtrip.py` (14 tests) — `images_referenced_by_datasets()`/`preview_image_removal()`/`remove_images()` : suppression physique réelle d'un fichier interne et présent, fichier externe jamais supprimé physiquement, fichier manquant retiré sans erreur, blocage atomique si au moins une image reste référencée par un Dataset, retrait de référence Dataset (Mission 045) débloquant ensuite la suppression réelle, sauvegarde déclenchée uniquement si mutation réelle, persistance après un cycle fermeture/réouverture.
- `test_images_page.py` (10 tests nets nouveaux) — sélection étendue, état du bouton « Supprimer » (sans/avec sélection simple/multiple), les trois libellés exacts de confirmation, annulation = aucune mutation, blocage Dataset affiché sans confirmation préalable, rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` existant, non-régression de « Voir en grand » avec une sélection multiple active.
- `test_datasets_page.py`/`test_dataset_roundtrip.py` : exécutés intégralement — **strictement inchangés**, aucune régression détectée.
- **792/792 tests verts** au total (768 précédents + 24 nets nouveaux), suite ciblée `WorkspaceManagerRemoveImagesTest` : 14/14 OK, `test_images_page.py` : 33/33 OK, non-régression Workspace/Dataset/DatasetsPage : 146/146 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — suppression réelle d'un fichier interne confirmée disparue du disque avec le libellé exact « Supprimer », retrait d'un fichier externe confirmé conservé sur disque avec le libellé exact « Retirer », blocage réel observé pour une image référencée par un Dataset puis suppression réussie après retrait de la référence, sélection mixte (1 interne + 1 externe) confirmée avec le libellé « Continuer » et le comptage exact, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 046)

La dette distincte laissée ouverte par Mission 045 (suppression d'une image depuis `ImagesPage`) est désormais **résolue**. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `40feee77150d5f52af00c6011db8630a449fe730` — `feat: add deleting images from the Workspace gallery`, tag `v0.2-mission046`, GitHub Release publiée).

---

## v0.2-mission045 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 045 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 045)

**Mission 045 — Remove Images from a Dataset.** Referme la dette identifiée en retour par Mission 044 : seule la suppression d'un Dataset entier existait (`delete_dataset()`), sans moyen de corriger une erreur d'ajout individuelle — devenu plus visible depuis Mission 044, qui permet à un Dataset de référencer directement une image du Workspace sans copie physique.

`DatasetsPage` gagne un bouton « Retirer du dataset », à côté de « Voir en grand », `images_list` passant en sélection étendue (`ExtendedSelection`) pour permettre un retrait multiple en une seule opération. Nouvelle primitive `DatasetManager.remove_images(paths)`, symétrique à `add_images()` (même convention de comparaison de chemins résolus, sauvegarde uniquement si une mutation réelle a eu lieu, aucun événement dédié publié).

Le retrait ne mute **que** la référence du Dataset actif : le fichier physique n'est jamais supprimé, `Workspace.images` reste inchangé, et tout autre Dataset référençant le même fichier (chaque Dataset possédant son propre pool `Image` indépendant, Mission 011) reste intact. Aucun nouveau wiring EventBus : le chemin `WORKSPACE_SAVED` déjà existant suffit. `ImagesPage` et le Domain restent strictement inchangés. La suppression d'une image depuis `ImagesPage` (retrait de `Workspace.images` et/ou suppression physique) reste une dette **distincte, entièrement ouverte**, non traitée par cette mission.

### Tests ajoutés (Mission 045)

- `test_datasets_page.py` (10 tests nets nouveaux) — sélection étendue, état du bouton « Retirer du dataset » (sans/avec sélection simple/multiple), retrait d'une image et de plusieurs en une opération, no-op sans sélection, retrait de la dernière image, rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` existant, non-régression de « Voir en grand » avec une sélection multiple active.
- Nouvelle classe `DatasetManagerRemoveImagesTest` dans `test_dataset_roundtrip.py` (8 tests) — retrait simple/multiple, chemin inconnu, sans Dataset actif, fichier physique jamais touché, `Workspace.images` jamais touché, sauvegarde déclenchée uniquement si mutation réelle, et la **propriété déterminante de référence partagée entre deux Datasets**.
- `test_dataset_roundtrip.py` (1 test net nouveau) — cycle complet réel confirmant que cette propriété de référence partagée survit à une fermeture/réouverture réelle du Workspace.
- `test_images_page.py` : exécuté intégralement — **strictement inchangé**, aucune régression détectée.
- **768/768 tests verts** au total (749 précédents + 19 nets nouveaux), suite ciblée `test_datasets_page.py` : 30/30 OK, `test_dataset_roundtrip.py` : 36/36 OK, `test_images_page.py` : 23/23 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — deux Datasets partageant la même image, sélection réelle et clic réel sur « Retirer du dataset », retrait observé uniquement dans le Dataset visé, second Dataset et `Workspace.images` intacts, fichier physique intact, retrait multiple réel confirmé, persistance de la propriété confirmée après fermeture/réouverture réelle.

### État du projet (Mission 045)

La dette identifiée en retour par Mission 044 (retrait d'une image d'un Dataset) est désormais **résolue**. La suppression d'une image depuis `ImagesPage` (retrait de `Workspace.images` et/ou suppression physique du fichier) reste explicitement hors périmètre et non traitée — dette distincte nécessitant son propre audit dédié. Aucun autre nouveau besoin n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `b83c4eb0ac1e582718afd73915b519e131c7dffe` — `feat: add removing images from a Dataset`, tag `v0.2-mission045`, GitHub Release publiée).

---

## v0.2-mission044 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 044 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 044)

**Mission 044 — Feed a Dataset from the Images Gallery.** Referme la dette UX documentée depuis Mission 028 : le seul moyen d'alimenter un Dataset était de réimporter une image depuis le disque via `QFileDialog`, même lorsqu'elle était déjà présente dans la galerie `Images` du Workspace.

`DatasetsPage` gagne un nouveau bouton « Ajouter depuis Images… », à côté de « Importer des images » existant, ouvrant un nouveau dialogue dédié `SelectImagesDialog` (galerie de miniatures multi-sélectionnable des images de `Workspace.images`, réutilisant le helper `load_thumbnail_icon()` introduit par Mission 042). La sélection est ajoutée au Dataset **actuellement actif** via `DatasetManager.add_images()`, strictement inchangé — aucune nouvelle logique de déduplication ni de copie n'a été ajoutée en Presentation.

Une image déjà interne au Workspace n'est **jamais physiquement dupliquée** : `WorkspaceStorage.copy_into_workspace()` (Mission 028) reconnaissait déjà ce cas et réutilise le fichier tel quel. Une image déjà présente dans le Dataset actif est silencieusement ignorée par le même mécanisme de déduplication déjà existant. Aucun nouveau wiring EventBus n'a été nécessaire : le chemin `WORKSPACE_SAVED` déjà utilisé pour rafraîchir `DatasetsPage` s'est révélé suffisant. `ImagesPage`, le Domain, `DatasetManager`, `WorkspaceManager` et l'EventBus restent tous strictement inchangés — l'action est intégralement hébergée dans `DatasetsPage`, qui possédait déjà les deux dépendances nécessaires.

### Tests ajoutés (Mission 044)

- Nouveau fichier `tests/integration/test_select_images_dialog.py` (7 tests) — mode galerie, sélection multiple activée, métadonnées par image (icône/texte/tooltip/`Qt.UserRole`), sélection vide/simple/multiple, galerie vide.
- `test_datasets_page.py` (8 tests nets nouveaux) — garde « aucun dataset actif », garde « galerie Images vide », dialogue peuplé des images réelles du Workspace, annulation, ajout d'une image et de plusieurs images sans nouveau fichier sur disque, doublon ignoré sans duplication, rafraîchissement vérifié via le seul mécanisme `WORKSPACE_SAVED` existant.
- `test_dataset_roundtrip.py` (1 test net nouveau) — cycle complet réel : ajout depuis la galerie, sauvegarde, fermeture, réouverture — persistance confirmée et absence de copie physique vérifiée explicitement.
- `test_images_page.py` : exécuté intégralement — **strictement inchangé**, aucune régression détectée.
- **749/749 tests verts** au total (733 précédents + 16 nets nouveaux), suite ciblée `test_select_images_dialog.py` : 7/7 OK, `test_datasets_page.py` : 20/20 OK, `test_dataset_roundtrip.py` : 27/27 OK, `test_images_page.py` : 23/23 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — sélection réelle (clic + Ctrl-clic) et clic réel sur le bouton OK du dialogue, ajout de 2 images observé, galerie Dataset rafraîchie sans appel manuel, aucun dossier `datasets/<dataset_id>/` créé à aucune étape, doublon correctement ignoré, persistance confirmée après fermeture/réouverture réelle.

### État du projet (Mission 044)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'alimentation d'un Dataset depuis la galerie Images est désormais **résolue**. La suppression avancée d'images, le tri de la galerie Images et la portabilité des chemins restent explicitement hors périmètre et non traités. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `542e0fef67a426f800220a2a5e43f25ecce57e5b` — `feat: add feeding a Dataset from the Images gallery`, tag `v0.2-mission044`, GitHub Release publiée).

---

## v0.2-mission043 — 2026-08-21

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 043 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 043)

**Mission 043 — Dashboard Training Indicator.** Referme la dette UX documentée depuis Mission 029 : `DashboardPage.trainingCard` affichait en permanence le texte figé `"Idle"`, jamais mis à jour par `update_project()` et jamais réinitialisé à la fermeture d'un projet — la seule carte du Dashboard qui ne reflétait aucune donnée réelle du Workspace, contrairement à `imagesCard`/`datasetsCard`/`modelsCard`/`lorasCard`.

`trainingCard` affiche désormais le nombre réel de sessions Training enregistrées dans le Workspace, via `sum(len(character.get("trainings") or []) for character in (project.get("characters") or []))` — exactement le même principe d'agrégation déjà utilisé pour `datasetsCard`/`lorasCard` — et se remet explicitement à `"0"` lorsqu'aucun Workspace n'est ouvert. Aucun état d'exécution (`Idle`/`Running`/`Failed`) n'est introduit ni simulé : ce choix est délibéré, aucun moteur d'entraînement réel n'existant à ce jour dans AI Studio Toolkit ; `trainingButton` reste inchangé, visible et désactivé.

Un mini-audit ciblé a confirmé qu'aucun nouveau wiring EventBus n'était nécessaire : `TrainingManager.create()`/`delete()` appellent déjà `WorkspaceManager.save()`, qui publie `WORKSPACE_SAVED`, événement auquel `DashboardPage.update_project()` est déjà abonné — exactement le mécanisme qui fait déjà fonctionner `datasetsCard`/`lorasCard`. Modification strictement confinée à `src/ui/pages/dashboard_page.py` : aucun changement Domain, Manager, EventBus ou persistance.

### Tests ajoutés (Mission 043)

- `test_training_roundtrip.py::test_full_create_select_save_close_reopen_cycle` (existant, étendu) : assertions ajoutées sur `dashboard.trainingCard.value.text()` — `"0"` avant création, `"1"` après création, `"0"` après fermeture du Workspace, `"1"` restauré après réouverture.
- `test_dashboard_training_card_default_value_without_any_workspace` (nouveau) : un `DashboardPage()` fraîchement construit, sans aucun Workspace, affiche `"0"`.
- `test_dashboard_training_card_reflects_multiple_sessions_and_deletion` (nouveau) : création de 2 sessions Training (`"1"` puis `"2"`), suppression des 2 (`"1"` puis `"0"`).
- `test_dashboard_and_images_unaffected_by_training_events` : confirmé non modifié — ses assertions ne portent jamais sur `trainingCard`.
- **733/733 tests verts** au total (731 précédents + 2 nets nouveaux), suite ciblée `test_training_roundtrip.py` : 18/18 OK, non-régression croisée (`test_dashboard_page.py`/`test_workspace_roundtrip.py`/`test_dataset_roundtrip.py`/`test_lora_roundtrip.py`) : 108/108 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — compteur observé à `"0"` (avant Workspace, puis Workspace sans Training), `"1"`/`"2"` (création de sessions), `"1"` (suppression), `"0"` (fermeture), `"1"` restauré (réouverture), non-régression des autres cartes et de `trainingButton` confirmée.

### État du projet (Mission 043)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'indicateur Training figé du Dashboard est désormais **résolue**. La notion d'état d'exécution (`Idle`/`Running`/`Failed`) est explicitement abandonnée tant qu'aucun moteur d'entraînement réel n'existe, plutôt que reportée. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `9eec7c5754faaf8bd077969c4d9580df4d3484b1` — `fix: reflect real Training session count on Dashboard`, tag `v0.2-mission043`, GitHub Release publiée).

---

## v0.2-mission042 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 042 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 042)

**Mission 042 — Dataset Thumbnail Gallery.** Referme la dette UX documentée depuis Mission 028 : `DatasetsPage` affichait le contenu d'un Dataset comme une simple liste de chemins texte, sans aucun aperçu visuel — à la différence d'`ImagesPage`, passée en galerie de miniatures dès Mission 019.

`DatasetsPage.images_list` devient une galerie de miniatures en parité stricte avec `ImagesPage` (`IconMode`, miniatures 128×128, grille 150×170) : chaque image affiche son nom de fichier, conserve son chemin complet en tooltip et dans `Qt.UserRole`, et bénéficie d'un repli robuste vers une icône native d'avertissement pour tout fichier absent, invalide ou non décodable — sans jamais faire planter la galerie. Un aperçu agrandi est désormais disponible via double-clic ou le nouveau bouton « Voir en grand », réutilisant `ImagePreviewDialog` **sans aucune modification**.

La logique de chargement de miniature, jusqu'ici privée à `ImagesPage`, a été extraite dans un helper UI partagé minimal (`src/ui/thumbnails.py`, une seule fonction, aucune classe, aucun nouveau package) — `ImagesPage` migrée vers ce helper sans aucun changement de comportement observable. Aucun changement Domain, Manager ou persistance : cette mission est strictement confinée à la couche Presentation.

### Tests ajoutés (Mission 042)

- Nouveau fichier `tests/integration/test_datasets_page.py` (12 tests, `DatasetsPageGalleryTest`) — mode galerie, image valide (icône/texte/tooltip/`Qt.UserRole`), fichier absent et fichier invalide (tous deux avec repli robuste), plusieurs images avec `Qt.UserRole` distincts, activation/désactivation de « Voir en grand » selon la sélection, ouverture de `ImagePreviewDialog` par bouton et par double-clic, réinitialisation de la sélection au changement/rafraîchissement de Dataset.
- `test_dataset_roundtrip.py` : deux assertions existantes adaptées au nouveau contrat de présentation (`item.text()` = nom de fichier, `Qt.UserRole` = chemin complet), aucun autre changement.
- `test_images_page.py` : exécuté intégralement après la migration vers le helper partagé — **strictement inchangé**, aucune régression détectée.
- **731/731 tests verts** au total (719 précédents + 12 nets nouveaux), aucune régression détectée, suite ciblée `test_datasets_page.py` : 12/12 OK, `test_images_page.py` : 23/23 OK.
- **Smoke test manuel réel du rendu Qt, PASS** — miniature valide et icône de repli natif observées dans la même galerie, nom de fichier lisible, sélection activant correctement « Voir en grand », aperçu ouvert avec succès par le bouton et par le double-clic, réinitialisation confirmée au changement de Dataset.

### État du projet (Mission 042)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'absence de miniatures pour les images d'un Dataset est désormais **résolue**. L'alimentation d'un Dataset depuis la galerie Images, la suppression/gestion avancée des images du Dataset, le tri et le workflow Training restent explicitement hors périmètre et non traités. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `5c13619bcf236fbf8366c74af74ddc207daaeb06` — `feat: add thumbnail gallery to Datasets page`, tag `v0.2-mission042`, GitHub Release publiée).

---

## v0.2-mission041 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 041 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 041)

**Mission 041 — Explicit Prompt Assistant Mode Selection.** Referme la dette UX documentée depuis Mission 032 : dans `PromptAssistantDialog`, les boutons « Créer un nouveau prompt » et « Améliorer le prompt actuel » ressemblaient à deux boutons d'action indépendants alors qu'ils fonctionnent comme un sélecteur de mode mutuellement exclusif — le mode actif n'était identifiable que par un texte, sans distinction visuelle des boutons eux-mêmes.

`create_mode_button`/`improve_mode_button` deviennent des `QPushButton` checkables, regroupés dans un `QButtonGroup` exclusif. `_set_mode()` devient le point unique synchronisant explicitement le mode logique (`self._mode`) et l'état `checked` des deux boutons, sans jamais s'appuyer sur la seule exclusivité du groupe.

Un smoke test manuel réel obligatoire — mené en rendant le widget réel via le mécanisme Qt natif (`QWidget.grab()`) et un échantillonnage objectif de pixels — a révélé que `create_mode_button` (premier `QPushButton` du dialogue) recevait automatiquement de Qt le statut de « bouton par défaut » du dialogue, produisant un rendu bleu natif indépendant de `:checked` qui brouillait la distinction avec le mode réellement actif. Corrigé par `setAutoDefault(False)` sur les deux boutons de mode — le statut de bouton par défaut se reporte sans conséquence sur `generate_button`, cohérent avec son rôle d'action principale du dialogue. Une première série de captures prises trop tôt après chaque changement d'état avait par ailleurs saisi une animation de transition du style Windows Vista natif en plein fondu — un artefact de la méthode de capture, non une régression de l'application — le contraste natif `:checked`/non-coché s'étant confirmé net et symétrique une fois le rendu stabilisé.

**Aucun style `:checked` personnalisé n'a été ajouté** : le rendu natif Qt, une fois décorrélé du bouton par défaut, s'est avéré suffisamment clair. `_set_mode()`, `assist()`, `PromptAssistantManager`, `AIBackend`/`OllamaEngine` restent strictement inchangés.

### Tests ajoutés (Mission 041)

- `test_initial_state_create_checked_improve_unchecked`, `test_switching_to_improve_checks_improve_and_unchecks_create`, `test_switching_back_to_create_checks_create_and_unchecks_improve` (`PromptAssistantDialogModeTest`, nouveaux) — état `isChecked()` correct à l'ouverture et à chaque bascule.
- `test_clicking_the_already_active_mode_keeps_exactly_one_checked` (nouveau) — reclic sur le mode déjà actif : exactement un bouton reste `checked`, jamais les deux `False` simultanément, `_mode` cohérent.
- `test_mode_buttons_are_not_the_dialog_default_button` (nouveau, ajouté pendant le smoke test) — `autoDefault() == False` sur les deux boutons de mode.
- Les 3 tests existants de `PromptAssistantDialogModeTest` restent inchangés et verts.
- **719/719 tests verts** au total (714 précédents + 5 nets nouveaux), aucune régression détectée, suite ciblée (`test_prompt_assistant_dialog.py`) : 27/27 OK.
- **Smoke test manuel réel du rendu natif Qt, PASS** — contraste actif/inactif confirmé net et symétrique à l'ouverture, lors des bascules Create ↔ Improve et lors du reclic sur le mode déjà actif, une fois le rendu Qt stabilisé.

### État du projet (Mission 041)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant la clarté visuelle du sélecteur de mode Créer/Améliorer est désormais **résolue**. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète et par un smoke test manuel réel du rendu natif Qt. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `355acfcafcfecf5a5e59bac687beeefd43a20ebe` — `fix: make Prompt Assistant mode selection explicit`, tag `v0.2-mission041`, GitHub Release publiée).

---

## v0.2-mission040 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 040 — commit, tag et Release sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 040)

**Mission 040 — Restore Prompt Assistant Result Action.** Corrige la dette UX distincte identifiée en retour par le smoke test de Mission 039 : dans `PromptAssistantDialog`, un résultat précédemment généré avec succès restait affiché après l'échec d'une génération suivante, mais devenait inutilisable via « Utiliser ce texte ».

Après réévaluation explicite du contrat par l'architecte, la conservation du dernier résultat valide dans `result_edit` après un échec est confirmée comme le comportement **voulu** — elle n'a jamais été le défaut et n'est **pas** modifiée par cette mission. Le défaut réel, plus étroit, était que `use_result_button` restait désactivé après un échec même lorsque ce résultat précédent demeurait valide et affiché.

`_on_assist_failed()` fait désormais dépendre l'état de `use_result_button` du contenu réel de `result_edit` (`bool(self.result_edit.toPlainText().strip())`), sans nouvel attribut d'état interne : le bouton redevient disponible après un échec si un résultat valide reste affiché, et reste correctement désactivé si aucun résultat valide n'a jamais été produit. `_on_generate_clicked()`/`_on_assist_finished()`, `AIBackend`/`OllamaEngine`, `PromptAssistantManager`, Domain, Managers, EventBus et persistance restent strictement inchangés.

### Tests ajoutés (Mission 040)

- `test_use_result_button_stays_enabled_after_a_failed_follow_up_generation` (`PromptAssistantDialogGenerateTest`, nouveau) : génération A réussie puis génération B échouée — `result_edit` contient toujours exactement le résultat A, `use_result_button` est de nouveau activé.
- Le test existant `test_prompt_assistant_error_does_not_crash_and_re_enables_controls` (aucun résultat préalable → échec → `result_edit` vide, bouton désactivé) est conservé sans modification, confirmant l'absence de régression sur ce cas.
- **714/714 tests verts** au total (713 précédents + 1 net nouveau), aucune régression détectée, suite ciblée (`test_prompt_assistant_dialog.py`) : 22/22 OK. Aucun smoke test manuel requis — `AIBackend`/`OllamaEngine` strictement hors périmètre et inchangés.

### État du projet (Mission 040)

La dette UX documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'incohérence entre `result_edit` et `use_result_button` dans `PromptAssistantDialog` est désormais **résolue**. Aucun nouveau besoin distinct n'a été identifié en retour par cette mission. Validée par la suite automatisée complète. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `0d87aa8154afb67f102512fd7306466e5a210a78` — `fix: restore Prompt Assistant result action after failed retry`, tag `v0.2-mission040`, GitHub Release publiée).

---

## v0.2-mission039 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 039 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 039)

**Mission 039 — Enforce a clean output contract for the Prompt Assistant.** Referme l'observation documentée depuis le smoke test réel de Mission 031 : le Prompt Assistant retournait directement la réponse brute du LLM à l'utilisateur, pouvant contenir un préambule, des explications, une analyse ou du Markdown autour du prompt final — l'action « Utiliser ce texte » pouvait donc récupérer autre chose que le seul prompt exploitable.

`PromptAssistantManager` demande désormais explicitement au modèle de retourner uniquement le prompt final, sans explication/analyse/préambule/commentaire ni bloc Markdown englobant, encadré par des marqueurs dédiés `@@AISTUDIO_PROMPT_START@@`/`@@AISTUDIO_PROMPT_END@@`. Le bloc d'instructions est construit à partir des mêmes constantes que le parser, ajouté une seule fois en fin de texte combiné, identiquement pour les modes Créer et Améliorer, avec ou sans `CharacterContext` (Mission 034 inchangée).

`assist()` applique un nouveau post-traitement déterministe (`_extract_final_prompt()`) : l'extraction n'a lieu que si `START` et `END` apparaissent chacun exactement une fois, `START` précède `END`, et le contenu interne après `.strip()` n'est pas vide — dans ce cas, seul ce contenu est retourné, sans nettoyage heuristique supplémentaire (Markdown et texte multilignes légitimes préservés tels quels). Dans tous les autres cas (délimiteurs absents, incomplets, inversés, multiples, ou contenu vide), le comportement est strictement non destructeur — `response.strip()` — sans jamais tenter de deviner quelle portion de la réponse constitue le prompt.

`AIBackend`/`OllamaEngine` restent strictement inchangés — aucun JSON mode générique, aucun protocole de sortie structurée universel introduit. Le contrat de délimitation appartient pour l'instant exclusivement à `PromptAssistantManager`, sans préjuger d'une future évolution pour Prompt Library, tags, RAG ou vision/multimodal.

### Tests ajoutés (Mission 039)

- 6 tests existants adaptés au nouveau texte littéral envoyé au backend (bloc de contrat de sortie désormais présent), sans changement de portée.
- `PromptAssistantManagerOutputContractInstructionTest` (+4) : bloc de contrat présent en Créer/Améliorer, présent une seule fois avec `CharacterContext`, ordre identité → demande actuelle → instructions de sortie.
- `PromptAssistantManagerExtractFinalPromptTest` (+9) : paire valide, espaces périphériques, sans délimiteur, START seul, END seul, paires multiples, ordre inversé, contenu multilignes préservé, Markdown interne préservé, contenu vide/whitespace-only entre délimiteurs valides → fallback.
- `PromptAssistantManagerAssistExtractionIntegrationTest` (+3) : `assist()` bout-en-bout — contrat respecté, contrat ignoré, erreur backend n'atteignant jamais l'extraction.
- **713/713 tests verts** au total (696 précédents + 17 nets nouveaux), aucune régression détectée, suite ciblée (`test_prompt_assistant_manager.py`) : 44/44 OK.
- **Smoke test manuel réel complet, PASS** — deux chemins clés vérifiés contre une instance Ollama réelle : contrat respecté (seul le prompt final visible, aucun marqueur), contrat incomplet avec `llama3.2:3b` (`START` sans `END` → réponse brute intégralement préservée). Un timeout Ollama occasionnel observé pendant l'essai a été diagnostiqué comme le comportement de cold start déjà documenté depuis Mission 030, sans lien causal avec Mission 039 — voir `docs/missions/MISSION_039.md` pour le détail complet.

### État du projet (Mission 039)

L'observation documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant la propreté de la sortie du Prompt Assistant est désormais **résolue**. Mission 039 a en retour identifié une nouvelle dette UX distincte, non corrigée par cette mission : dans `PromptAssistantDialog`, le contenu précédent de « Résultat proposé » reste affiché après l'échec d'une génération suivante — enregistrée comme besoin futur, aucune décision UX prise. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `d379f92db6d2a6d3554eb40e6edb5d353f51ca53` — `feat: enforce a clean output contract for the Prompt Assistant`, tag `v0.2-mission039`, GitHub Release publiée).

---

## v0.2-mission038 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 038 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 038)

**Mission 038 — Protect unsaved prompt drafts in PromptsPage.** Referme la dette documentée depuis l'audit pré-implémentation de Mission 032 : `PromptsPage.update_prompts()` réécrivait inconditionnellement `text_edit` à chaque événement EventBus pertinent, pouvant écraser silencieusement un brouillon non sauvegardé même lorsque le Prompt réellement édité n'avait pas changé — notamment `WORKSPACE_SAVED` (déclenché par « Enregistrer dans Prompts » depuis `InferencePage`), `WORKSPACE_RENAMED`, `CHARACTER_CREATED`, ou `PROMPT_CREATED` sans changement de Prompt actif.

Un mini-audit UX dédié a distingué les causes de rafraîchissement plutôt que d'ajouter une confirmation générique devant tout appel à `update_prompts()`. Solution retenue : un dirty-state local (`_dirty`/`_loaded_prompt_id`), purement Presentation — aucun changement Domain, `PromptManager`, format Workspace ou persistance. `update_prompts()` ne recharge `text_edit` que lorsque `PromptManager.active_prompt_id` a réellement changé depuis le dernier chargement, préservant le brouillon pour les refresh non destructeurs.

Changer volontairement de Prompt alors que le brouillon est dirty propose désormais Enregistrer/Ignorer les modifications/Annuler avant tout appel à `PromptManager.select()` — Annuler restaure réellement la sélection visuelle précédente sans jamais muter l'état du Manager. Supprimer le Prompt actuellement affiché est protégé de façon équivalente avant `PromptManager.delete()`. Le résultat du Prompt Assistant (« Utiliser ce texte ») marque correctement le brouillon dirty ; une sauvegarde explicite (y compris idempotente) le remet à `False` ; « Enregistrer comme nouveau Prompt… » (Mission 035) et « Nouveau prompt » conservent leur comportement, sans confirmation parasite.

Après un réexamen architectural explicite, une séparation EventBus stricte a été retenue plutôt qu'une double souscription ordonnée : `update_prompts()` gère exclusivement `WORKSPACE_SAVED`/`RENAMED`, `CHARACTER_CREATED`, `PROMPT_CREATED`/`SELECTED`/`DELETED` ; une nouvelle `reset_for_context_change()` gère exclusivement `WORKSPACE_CREATED`/`OPENED`/`CLOSED` et `CHARACTER_SELECTED`/`DELETED` — des événements déjà transitionnés côté Manager lorsque `PromptsPage` en est informée, acceptés sans tentative de veto tardif. Aucune double souscription, aucune dépendance à l'ordre des abonnés.

### Tests ajoutés (Mission 038)

- `PromptRoundTripTest` (+14) : refresh non destructeur préservant un brouillon dirty (`WORKSPACE_SAVED`/`WORKSPACE_RENAMED`/`PROMPT_CREATED` sans sélection) ; changement de Prompt dirty (Enregistrer/Ignorer/Annuler avec restauration réelle de la sélection) et sans dirty (régression) ; suppression dirty (Annuler/Confirmer) et non dirty (régression) ; `create_prompt()` préservant le brouillon ; `reset_for_context_change()` sur fermeture de Workspace, sur changement de Character, et sur le cas limite `_loaded_prompt_id`/`active_prompt_id` tous deux `None` ; vérification programmatique du routage EventBus déterministe.
- `PromptsPagePromptAssistantTest` (+3) : résultat de l'Assistant IA marquant dirty ; `save_text()` remettant `dirty=False` (cas normal et idempotent).
- **696/696 tests verts** au total (680 précédents + 16 nets nouveaux), aucune régression détectée, suite ciblée (`test_prompt_roundtrip.py`) : 59/59 OK ; suites dépendantes (`test_main_window_prompts_to_inference.py`/`test_inference_page.py`) : 86/86 OK.
- **Smoke test manuel réel complet, PASS** — voir `docs/missions/MISSION_038.md` pour le détail complet.

### État du projet (Mission 038)

`update_prompts()`/`reset_for_context_change()` forment désormais une séparation déterministe : un événement, un seul chemin Presentation dans `PromptsPage`. La dette documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant la perte silencieuse d'un texte non sauvegardé dans `PromptsPage` est désormais **résolue**, sans qu'aucun nouveau besoin distinct n'ait été identifié en retour — seule une limitation architecturale volontaire (changements Workspace/Character non annulables depuis `PromptsPage`) a été documentée, non transformée en dette active. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `f705377111cefe31c7a8be3bb0581c93cbedbef9` — `feat: protect unsaved prompt drafts in PromptsPage`, tag `v0.2-mission038`, GitHub Release publiée).

---

## v0.2-mission037 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 037 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 037)

**Mission 037 — Distinguish no open project from no dataset in TrainingPage.** Referme l'ambiguïté distincte confirmée pendant le smoke test manuel réel de Mission 036 : `TrainingPage.create_training()` interrogeait `dataset_manager.list_datasets()` avant toute vérification de `workspace_manager.opened` (déjà injecté depuis Mission 036), si bien qu'aucun Workspace ouvert produisait le message « Aucun dataset disponible » plutôt que le vrai problème, « Aucun projet ouvert ».

Une seule garde `workspace_manager.opened` a été ajoutée en tête de `create_training()`, avant tout appel à `dataset_manager.list_datasets()`. Aucun Workspace ouvert affiche désormais immédiatement « Aucun projet ouvert » — demandant d'ouvrir ou créer un projet avant de créer une session d'entraînement — sans consulter les Datasets ni ouvrir aucun dialogue. Workspace ouvert sans Dataset conserve le message existant « Aucun dataset disponible », inchangé. Workspace ouvert avec Dataset disponible conserve le flux normal, strictement inchangé.

`WorkspaceManager.opened` reste la seule source d'autorité, cohérente avec Mission 036. Aucune nouvelle dépendance : `TrainingPage` possédait déjà `WorkspaceManager` en constructeur depuis Mission 036. `DatasetManager` et `TrainingManager` sont strictement inchangés, y compris leurs contrats publics. Le bloc défensif introduit par Mission 036 après `training_manager.create()` reste lui aussi inchangé.

### Tests ajoutés (Mission 037)

- `test_create_training_without_open_workspace_shows_no_project_warning` (renforcé) : ajout de `dataset_manager.list_datasets.assert_not_called()` et de l'absence d'appel aux deux `QInputDialog`, prouvant que la nouvelle garde intercepte le cas avant toute autre opération.
- `test_create_training_with_open_workspace_and_no_dataset_shows_dataset_warning` (nouveau) : Workspace réel ouvert, `DatasetManager` réel non mocké, zéro Dataset → message « Aucun dataset disponible » inchangé, aucune Training créée.
- `test_create_training_with_open_workspace_and_dataset_succeeds` (nouveau) : Workspace + Dataset réels, flux nominal via `QInputDialog` contrôlé → aucun avertissement, Training effectivement créée.
- **680/680 tests verts** au total (678 précédents + 2 nets nouveaux), aucune régression détectée, suite ciblée (`test_training_roundtrip.py`) : 16/16 OK.
- **Smoke test manuel réel complet, PASS** — voir `docs/missions/MISSION_037.md` pour le détail complet.

### État du projet (Mission 037)

`WorkspaceManager.opened` reste la seule source d'autorité pour l'état du Workspace. La dette distincte documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'ambiguïté « Aucun dataset disponible » de `TrainingPage.create_training()` est désormais **résolue**, sans qu'aucun nouveau besoin distinct n'ait été identifié en retour. L'invariant « Workspace ouvert ⇒ Character principal » documenté par Mission 036 n'est pas rouvert. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `27ce1d1d3f3679722c3d78ba529d2d55b4843bd0` — `feat: distinguish no open project from no dataset in TrainingPage`, tag `v0.2-mission037`, GitHub Release publiée).

---

## v0.2-mission036 — 2026-08-20

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 036 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 036)

**Mission 036 — Distinguish no open project from no principal character in warnings.** Referme la dette UX transversale enregistrée pendant le smoke test manuel réel de Mission 035 : plusieurs messages affichaient « Aucun personnage » aussi bien lorsqu'aucun projet n'était ouvert que lorsqu'un Workspace existait sans personnage principal.

Sept emplacements (`CharactersPage.save_identity()`, `PromptsPage.create_prompt()`/`save_as_new_prompt()`, `DatasetsPage.create_dataset()`, `LoRAPage.create_lora()`, `TrainingPage.create_training()`, `InferencePage._on_save_prompt_clicked()`) distinguent désormais correctement les deux causes : « Aucun projet ouvert » (nouveau message, demandant d'ouvrir ou créer un projet) lorsqu'aucun Workspace n'est ouvert, contre le message « Aucun personnage »/« Aucun personnage sélectionné » existant — texte inchangé — lorsqu'un Workspace est réellement ouvert sans personnage principal.

Après un réexamen architectural explicite comparant deux options, `WorkspaceManager` est **injecté directement** dans les constructeurs de `CharactersPage`, `DatasetsPage`, `LoRAPage`, `PromptsPage` et `TrainingPage` (Option A) plutôt que d'ajouter une propriété `workspace_opened` dupliquée sur les cinq Managers métier concernés (Option C, explicitement écartée pour préserver `WorkspaceManager.opened` comme source d'autorité unique). `InferencePage` réutilise sa dépendance `WorkspaceManager` déjà existante depuis Mission 013, sans aucun changement de constructeur. **Aucun contrat Manager modifié** — `create()`/`update()`/`principal_character`/EventBus/Domain/persistance strictement inchangés. `CharactersPage.create_character()` reste inchangé, déjà correct.

Le smoke test manuel réel a également clarifié un invariant déjà réel de l'application : un Workspace ouvert possède toujours un Character principal auto-créé (Mission 026) — l'état « Workspace ouvert sans personnage principal » reste donc un cas technique/défensif couvert par les tests automatisés, pas un scénario utilisateur normalement atteignable. Une ambiguïté distincte a été confirmée et volontairement laissée hors périmètre : `TrainingPage.create_training()` peut afficher « Aucun dataset disponible » avant même d'atteindre la branche « Aucun personnage » lorsqu'aucun Workspace n'est ouvert.

### Tests ajoutés (Mission 036)

- `test_character_roundtrip.py` (+1) : `test_save_identity_without_open_workspace_shows_no_project_warning`, plus un test existant renforcé d'une assertion exacte de message.
- `test_dataset_roundtrip.py`/`test_lora_roundtrip.py` (+2 chacun) : un test par cause (aucun Workspace ouvert / Workspace ouvert sans personnage), assertions exactes de titre et de texte.
- `test_prompt_roundtrip.py` (+3) : couverture de `create_prompt()` et `save_as_new_prompt()`.
- `test_training_roundtrip.py` (+2) : `dataset_manager` mocké pour isoler la branche « Aucun personnage » de `create_training()`, normalement non atteignable en usage réel.
- `test_inference_page.py` (+1 nouveau, +1 existant renforcé).
- **678/678 tests verts** au total (667 précédents + 11 nets nouveaux), aucune régression détectée, suite ciblée (8 fichiers concernés) : 228/228 OK.
- **Smoke test manuel réel complet, PASS** — voir `docs/missions/MISSION_036.md` pour le détail complet.

### État du projet (Mission 036)

`WorkspaceManager.opened` reste la seule source d'autorité pour l'état du Workspace. Aucun Manager métier n'expose de propriété `workspace_opened`. La dette UX transversale documentée dans `docs/PROJECT_CONTEXT.md` ("Besoins futurs identifiés") concernant l'ambiguïté « Aucun personnage » est désormais **résolue**. Une nouvelle dette distincte (`TrainingPage → « Aucun dataset disponible »`) a été enregistrée, non traitée. L'invariant « Workspace ouvert ⇒ Character principal » a été explicitement documenté dans `docs/PROJECT_CONTEXT.md`, section "Orientation architecturale validée", sans aucune modification du Domain. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `ebd49d5f451448802e2732de9e4da718cd735506` — `feat: distinguish no open project from no principal character in warnings`, tag `v0.2-mission036`, GitHub Release publiée).

---

## v0.2-mission035 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 035 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 035)

**Mission 035 — Enregistrer comme nouveau Prompt… depuis un brouillon libre.** Referme l'observation UX enregistrée pendant le smoke test manuel réel de Mission 034 : dans `PromptsPage`, sans Prompt sélectionné, l'Assistant IA restait utilisable en mode Créer et « Utiliser ce texte » plaçait correctement le résultat dans l'éditeur — mais aucun chemin clair n'existait ensuite pour l'enregistrer comme nouveau `Prompt`.

Nouveau bouton « Enregistrer comme nouveau Prompt… » dans `PromptsPage`, disponible avec ou sans Prompt actuellement actif. Réutilise intégralement `PromptManager.create(name, text="")`, introduit en Mission 031, **sans aucune modification de son contrat**. Avec un Prompt actif, celui-ci reste strictement intact (jamais lu ni modifié) et un second Prompt distinct est créé à partir du texte actuellement visible. Dans les deux cas, `PromptsPage` appelle explicitement `prompt_manager.select(prompt.prompt_id)` juste après la création — décision locale à cette Page, délibérément différente de la garantie testée de Mission 031 pour `InferencePage` (qui, elle, ne doit jamais sélectionner, pour ne pas perturber la sélection de `PromptsPage` depuis une autre Page) — afin que le rafraîchissement synchrone déclenché par `PROMPT_CREATED` n'efface pas visuellement l'éditeur alors que le texte vient d'être persisté avec succès.

Aucune sauvegarde implicite : ouvrir ou utiliser l'Assistant IA ne crée jamais de Prompt par lui-même — seul ce nouveau bouton, actionné explicitement, le fait. Aucune modification d'`InferencePage`, du Domain `Prompt`, ni d'aucune partie du Prompt Assistant (`PromptAssistantManager`/`PromptAssistantDialog`/`PromptAssistantWorker`).

**Explicitement hors périmètre** : dirty-state général de `PromptsPage`, propreté de la sortie du Prompt Assistant, sélecteur visuel Créer/Améliorer, Prompt Library, tags, RAG, vision, Character Context avancé, toute extension du Domain `Prompt`.

Une dette UX transversale préexistante et sans lien avec cette mission a été constatée pendant le smoke test manuel réel : plusieurs Pages (`Characters`, `Prompts`, `Datasets`, `LoRA`, `Training`, `Inference`) affichent un message ambigu « Aucun personnage » aussi bien lorsqu'aucun projet n'est ouvert que lorsqu'un Workspace existe sans personnage principal — enregistrée comme besoin futur, aucune décision architecturale de correction prise.

### Tests ajoutés (Mission 035)

- `tests/integration/test_prompt_roundtrip.py`, classe `PromptRoundTripTest` (+2, Managers/EventBus réels) : `test_save_as_new_prompt_without_active_prompt_creates_and_selects_it` (création + sélection explicite, éditeur affichant le même texte après le rafraîchissement synchrone) ; `test_save_as_new_prompt_with_active_prompt_leaves_original_untouched` (Prompt d'origine strictement intact, second Prompt distinct créé et sélectionné).
- Nouvelle classe `PromptsPageSaveAsNewPromptTest` (+10, Managers mockés, mirroir de `PromptsPageSendToInferenceTest`) — présence/activation du bouton, création avec `select()` sur l'id exact, `update_text()` jamais appelé avec un Prompt actif, annulation/nom vide → aucune création, aucun personnage principal → avertissement affiché et `select()` jamais appelé.
- **667/667 tests verts** au total (655 précédents + 12 nets nouveaux), aucune régression détectée, suite ciblée (`test_prompt_roundtrip.py`) : 40/40 OK.
- **Smoke test manuel réel complet, PASS** — voir `docs/missions/MISSION_035.md` pour le détail complet.

### État du projet (Mission 035)

`PromptManager.create(name, text="")` reste strictement inchangé, réutilisé sans extension. `src/domain/prompt.py` strictement inchangé. La dette UX documentée de `PromptsPage` (voir `docs/PROJECT_CONTEXT.md`, "Besoins futurs identifiés") concernant l'absence de chemin clair pour transformer un texte libre en nouveau Prompt est désormais **résolue**. Une nouvelle dette UX transversale (ambiguïté « aucun projet ouvert » / « aucun personnage ») a été enregistrée, non traitée. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `a2766b6063859db85ec87e49b9a372d51d6c1c6f` — `feat: add save-as-new-prompt action to PromptsPage`, tag `v0.2-mission035`, GitHub Release publiée).

---

## v0.2-mission034 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 034 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 034)

**Mission 034 — Character Context minimal pour le Prompt Assistant.** Livre une première matérialisation concrète et explicite de la hiérarchie d'autorité « Identité canonique > demande actuelle > mémoire/anciens prompts/RAG », en exploitant les champs d'identité `Character` déjà existants depuis Mission 026, restés jusqu'ici totalement inertes côté Prompt Assistant.

Nouveau DTO minimal et provider-neutral `CharacterContext` (`character_lock`/`trigger_token`/`description`/`personality` — `bio`/`interests` volontairement exclus), converti depuis `Character` par un unique point `CharacterContext.from_character()`, colocalisé avec `PromptAssistantManager` dans `prompt_assistant_manager.py` : `PromptAssistantManager` (la classe) ne référence jamais `Character`, seule cette classmethod le fait. `assist(request_text, existing_prompt="", character_context=None)` reste une extension strictement additive — sans contexte, le texte envoyé au backend reste byte-for-byte identique à avant cette mission. Avec un contexte, `_build_combined_text()` préfixe un bloc `[IDENTITÉ CANONIQUE DU PERSONNAGE — priorité absolue, ne jamais contredire]` (Character Lock et Trigger token en tête, Description/Personnalité conditionnels, aucune ligne de champ vide) avant le bloc `[DEMANDE ACTUELLE]` déjà existant.

`PromptAssistantDialog` reçoit un `CharacterContext | None` déjà résolu par l'appelant — il ne connaît ni `Character` ni `CharacterManager` — et propose une `QCheckBox` « Utiliser l'identité du personnage », créée uniquement si un contexte utilisable existe, toujours décochée par défaut (aucune injection automatique). L'identité est capturée en snapshot avant le lancement de l'appel asynchrone : `PromptAssistantWorker` ne reçoit jamais `Character`/`CharacterManager`, aucune résolution dynamique pendant l'exécution. `PromptsPage` et `InferencePage` gagnent chacune `character_manager` en dépendance constructeur et résolvent identiquement `CharacterContext.from_character(character_manager.principal_character)` au moment d'ouvrir le dialogue — fonctionnalité strictement identique depuis les deux Pages, aucune logique dupliquée.

**Explicitement hors périmètre** : `bio`/`interests` dans le contexte IA, nouveaux champs Character, références d'identité 1..N, planche d'identité, Identity LoRA, tags, Prompt Library, inspiration depuis anciens prompts, RAG, embeddings, vision/multimodal, image → analyse → prompt, Qwen3-VL, auto-tagging, correction générale de la sortie Markdown du LLM, injection automatique de l'identité.

### Tests ajoutés (Mission 034)

- `tests/integration/test_prompt_assistant_manager.py` (+20) — `CharacterContextFromCharacterTest` (Character complet/partiel/quatre champs vides/blancs uniquement espaces/`bio` et `interests` jamais lus/`None`→`None`), `PromptAssistantManagerNoContextRegressionTest` (texte backend strictement identique à avant Mission 034 sans contexte), `PromptAssistantManagerWithContextTest` (ordre identité puis demande, Character Lock/Trigger token en tête, champs conditionnels, aucune ligne vide), `PromptAssistantManagerCharacterDependencyArchitectureTest` (aucune annotation `Character` sur `assist()`/`_build_combined_text()`, aucun import Qt).
- `tests/integration/test_prompt_assistant_worker.py` (+2) — snapshot `character_context` transmis tel quel, défaut `None`.
- `tests/integration/test_prompt_assistant_dialog.py` (+8, nouvelle classe `PromptAssistantDialogIdentityCheckboxTest`) — case absente/présente selon le contexte, décochée par défaut, décochée → `None` transmis, cochée → contexte transmis, non-régression Créer/Améliorer, erreur backend toujours gérée sans boîte modale réelle.
- `tests/integration/test_prompt_roundtrip.py` (+3) et `tests/integration/test_inference_page.py` (+3) — résolution `CharacterContext.from_character(character_manager.principal_character)` identique dans les deux Pages (aucun Character → `None` ; identité présente → contexte résolu ; identité vide → `None`).
- **655/655 tests verts** au total (619 précédents + 36 nets nouveaux), aucune régression détectée, dernière exécution complète unique (suite ciblée des 5 fichiers concernés : 160/160 OK).
- **Smoke test manuel réel complet, PASS** — case présente/absente selon l'identité disponible, décochée par défaut, génération avec et sans identité fonctionnelle depuis `PromptsPage` et `InferencePage`, non-régression Créer/Améliorer et `Prompts → Envoyer vers Inference` — voir `docs/missions/MISSION_034.md` pour le détail complet.

### État du projet (Mission 034)

`src/domain/character.py` strictement inchangé (aucun nouveau champ). Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) voit son besoin Character Context recevoir une première brique minimale — reste ouvert (Character Context avancé, Prompt Library, RAG, vision, propreté de la sortie LLM). Une observation UX non bloquante a été enregistrée pendant le smoke test réel (absence de chemin clair pour transformer un texte libre en nouveau Prompt depuis `PromptsPage` sans Prompt actif — comportement préexistant, non introduit par cette mission), rattachée à la dette UX déjà documentée de `PromptsPage`. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `d10afb47ac88a94944ea8eb86bbbfc94c9332ba5` — `feat: add Character Context to Prompt Assistant`, tag `v0.2-mission034`, GitHub Release publiée).

---

## v0.2-mission033 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 033 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 033)

**Mission 033 — Prompts → Envoyer vers Inference.** Livre le sens `Prompts → Envoyer vers Inference`, resté explicitement hors périmètre de Mission 032, fermant la boucle utilisateur `Créer/sélectionner un Prompt → Assistant IA → édition → Envoyer vers Inference → génération`. `PromptsPage` gagne un bouton « Envoyer vers Inference », activé/désactivé dynamiquement selon le texte actuellement visible dans l'éditeur (indépendamment de tout Prompt sélectionné), émettant un signal Qt local `send_to_inference_requested` capté uniquement par `MainWindow`.

Architecture Option A (signal Qt + `MainWindow` médiateur) retenue plutôt qu'un événement `EventBus` : aucune mutation Domain n'a lieu dans ce flux, seulement une intention Presentation-layer, hors du contrat `"domaine.verbe"` déjà établi par l'`EventBus`. `PromptsPage` ne référence jamais `InferencePage`. Deux nouvelles méthodes publiques minimales sur `InferencePage` (`prompt_text()`/`set_prompt_text()`) évitent tout accès direct au `QTextEdit` interne depuis `MainWindow` ; nouvelle `Sidebar.select_page(name)` (recherche dans `self.pages` déjà existant) évite tout index numérique codé en dur pour la navigation.

Le texte transféré est exactement le texte actuellement visible dans l'éditeur, y compris une modification locale non sauvegardée, jamais relu depuis le Domain `Prompt`. Gestion de collision par **comparaison exacte de chaînes** (aucune normalisation d'espaces/casse) : Inference vide ou identique → transfert et navigation immédiats, sans confirmation ; texte différent → `QMessageBox` à boutons personnalisés `Remplacer`/`Annuler` (premier usage d'une confirmation dans la base, aucun précédent réutilisable identifié), bouton par défaut `Annuler`. Annulation : aucune modification d'aucune des deux pages, aucune navigation. Aucune sauvegarde implicite à aucun moment (`PromptManager.update_text()`/`create()`, `WorkspaceManager.save()` jamais appelés par ce flux) — « Envoyer vers Inference » reste une opération d'usage du texte, jamais une sauvegarde du Prompt.

**Explicitement hors périmètre** : Prompt Library, tags, inspiration depuis anciens prompts, Character Context/« Utiliser l'identité », RAG, vision/multimodal, dirty-state général de `PromptsPage`, retour automatique Inference → Prompts.

### Tests ajoutés (Mission 033)

- `tests/integration/test_prompt_roundtrip.py` (+8, nouvelle classe standalone `PromptsPageSendToInferenceTest`) — bouton présent, désactivé si éditeur vide/espaces uniquement, activé dès qu'un texte est présent y compris sans Prompt actif, désactivé de nouveau après effacement, signal émis avec le texte exact actuellement visible (y compris non sauvegardé), aucun appel `update_text()`/`create()`.
- `tests/integration/test_inference_page.py` (+3, `InferencePagePromptAssistantTest`) — `prompt_text()`/`set_prompt_text()` corrects, aucun effet de bord `PromptManager`.
- `tests/integration/test_sidebar.py` (3, nouveau fichier) — `select_page()` positionne la ligne correcte (dérivée de `self.pages`, jamais un littéral codé en dur), fonctionne pour la première page, nom inconnu → `False` sans déplacement.
- `tests/integration/test_main_window_prompts_to_inference.py` (8, nouveau fichier, même patron que `test_main_window_new_project.py`) — Inference vide/espaces → transfert immédiat sans confirmation ; texte identique (comparaison stricte) → aucune confirmation ; texte différent → confirmation affichée ; confirmation acceptée → remplacement + navigation ; confirmation annulée → aucun changement ni navigation ; aucun appel `PromptManager.update_text()`/`create()` ; aucun appel `WorkspaceManager.save()`. `QMessageBox` toujours entièrement mocké, aucune boîte modale réelle.
- **619/619 tests verts** au total (597 précédents + 22 nets nouveaux), aucune régression détectée, dernière exécution complète unique.
- **Smoke test manuel réel complet, PASS** — bouton correctement activé/désactivé, transfert fonctionnel avec et sans Prompt actif, texte non sauvegardé transféré tel quel, les trois cas de collision confirmés, `Annuler`/`Remplacer` tous deux confirmés, aucune sauvegarde implicite constatée, aucune régression du Prompt Assistant ni de la navigation/édition des prompts — voir `docs/missions/MISSION_033.md` pour le détail complet.

### État du projet (Mission 033)

`src/domain/prompt.py`, `src/managers/prompt_manager.py`, `src/managers/prompt_assistant_manager.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `src/core/event_bus.py` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) voit son sens `Prompts → Envoyer vers Inference` désormais livré — reste ouvert (Character Context, Prompt Library, RAG, vision, propreté de la sortie LLM). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `2ee53f71780bb638b5ec9bd5af0603fb8d8241a2` — `feat: add Prompts to Inference transfer`, tag `v0.2-mission033`, GitHub Release publiée).

---

## v0.2-mission032 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 032 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 032)

**Mission 032 — Prompt Assistant dans PromptsPage.** Second usage utilisateur réel du service `PromptAssistantManager` (Mission 031, Option C long terme confirmée), désormais partagé entre `InferencePage` et `PromptsPage` — même instance construite une seule fois au composition root, aucun second Manager/Worker/dialogue créé. `PromptsPage` gagne un bouton « Assistant IA » (toujours activé) ouvrant `PromptAssistantDialog` réutilisé **sans aucune modification**.

Aucun Prompt sélectionné → `existing_prompt=""` transmis au dialogue quel que soit le contenu de l'éditeur (un texte libre non sauvegardé sans sélection est explicitement ignoré) — seul le mode **Créer** est proposé. Prompt sélectionné → `existing_prompt` = texte **actuellement visible** dans `text_edit` au moment de l'ouverture, jamais rechargé depuis le Domain `Prompt` persisté — un texte modifié manuellement mais non sauvegardé sert donc de base au mode **Améliorer**, vérifié par audit pré-implémentation dédié (un gating naïf sur la simple présence de texte, calque direct d'`InferencePage`, aurait permis à tort le mode Améliorer sans aucune sélection).

« Utiliser ce texte » remplace uniquement le contenu de l'éditeur — aucun appel `PromptManager.update_text()`/sauvegarde automatique, la persistance restant exclusivement gouvernée par le bouton existant « Enregistrer le texte », strictement inchangé. `Prompts → Envoyer vers Inference` reste explicitement hors périmètre.

Deux besoins futurs enregistrés pendant le smoke test manuel réel : confirmation que la dette UX préexistante de `PromptsPage` (perte silencieuse d'un texte non sauvegardé sur certains événements EventBus déclenchés ailleurs dans l'application) n'est pas une régression de cette mission ; observation UX non bloquante sur la clarté visuelle du sélecteur de mode Créer/Améliorer (`PromptAssistantDialog`, partagé par les deux Pages) — deux boutons ordinaires visuellement indiscernables de boutons d'action alors qu'ils fonctionnent comme un sélecteur de mode, non implémentée cette mission.

### Tests ajoutés (Mission 032)

- `tests/integration/test_prompt_roundtrip.py` (+8, aucun nouveau fichier) :
  - `PromptRoundTripTest` (+1) — `test_assistant_result_does_not_persist_until_explicit_save` : test de bout en bout avec `WorkspaceManager`/`CharacterManager`/`PromptManager` réels (`PromptAssistantDialog` mocké), confirmant qu'un texte édité manuellement mais non sauvegardé est bien transmis comme `existing_prompt` et que le résultat de l'Assistant ne modifie jamais le `Prompt` Domain avant sauvegarde explicite.
  - `PromptsPagePromptAssistantTest` (7, nouvelle classe standalone, calque d'`InferencePagePromptAssistantTest`) — bouton toujours présent/activé ; aucun Prompt actif → `existing_prompt=""` même avec du texte libre non sauvegardé ; Prompt actif → `existing_prompt` = texte actuellement affiché, jamais relu depuis `PromptManager.active_prompt` ; « Utiliser ce texte » sans sauvegarde automatique ; annulation sans modification ; non-régression de « Enregistrer le texte ».
- `tests/integration/test_inference_page.py` : commentaire du test architectural existant mis à jour pour refléter `PromptsPage` comme second consommateur réel, comportement du test inchangé.
- **597/597 tests verts** au total (589 précédents + 8 nets nouveaux), aucune régression détectée, dernière exécution complète unique, ~104 s.
- **Smoke test manuel réel complet, PASS** — ouverture de l'Assistant depuis `PromptsPage`, mode Créer avec génération réelle via Ollama, mode Améliorer utilisant correctement le texte actuellement visible dans l'éditeur (y compris une modification manuelle non sauvegardée) comme base, « Utiliser ce texte », sauvegarde explicite via « Enregistrer le texte » et persistance confirmée après rechargement, annulation du dialogue sans modification, gestion propre d'un backend Ollama inaccessible sans crash ni gel, absence confirmée du bouton `Prompts → Envoyer vers Inference` — voir `docs/missions/MISSION_032.md` pour le détail complet.

### État du projet (Mission 032)

`src/managers/prompt_assistant_manager.py`, `src/ui/prompt_assistant_worker.py`, `src/ui/dialogs/prompt_assistant_dialog.py`, `src/managers/prompt_manager.py`, `src/domain/prompt.py`, `src/engines/ai_backend.py`, `src/engines/ollama_engine.py` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) reçoit son second usage utilisateur réel, dans `PromptsPage` — reste ouvert (`Prompts → Envoyer vers Inference`, Character Context, Prompt Library, RAG, vision, propreté de la sortie LLM). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `e21447786795abe6cd9e0af5ef9f3cb6b9d2d94e` — `feat: add Prompt Assistant to PromptsPage`, tag `v0.2-mission032`, GitHub Release publiée).

---

## v0.2-mission031 — 2026-08-19

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 031 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction.

### Résumé (Mission 031)

**Mission 031 — Prompt Assistant Minimal (Inference).** Premier usage utilisateur réel du backend IA posé par Mission 030. `InferencePage` gagne une action « Assistant IA » ouvrant `PromptAssistantDialog` (nouveau, redimensionnable, 800×700 px par défaut, zones de texte extensibles priorisant le résultat proposé), présentant deux intentions explicites : **Créer** (à partir d'une demande utilisateur) et **Améliorer** (le prompt actuellement présent dans Inference affiché en lecture seule comme base avant tout envoi, jamais transmis silencieusement au backend). L'appel est exécuté hors du thread Qt principal via un nouveau `PromptAssistantWorker`/`QThread`, calque structurel exact de `GenerationWorker` (Mission 013) : interface réactive pendant l'appel, appel concurrent refusé, succès et erreur rétablissent tous deux correctement l'état de l'interface.

Nouveau `PromptAssistantManager` (Qt-free, même forme que `GenerationManager`) coordonne l'appel via l'abstraction `AIBackend` (Mission 030) — jamais `OllamaEngine` directement depuis l'UI, vérifié par test architectural couvrant `InferencePage` **et** `PromptsPage`. Construit une seule fois au composition root (`MainWindow`) depuis `ApplicationSettings.ollama_url`/`ollama_model_name`, sans aucun rechargement à chaud (même contrat que ComfyUI, confirmé par audit pré-implémentation dédié). Architecture long terme confirmée comme un service `PromptAssistantManager` partagé (Option C) — Mission 031 n'intègre volontairement que ce premier consommateur, `InferencePage` (Option B tactique), l'intégration `PromptsPage` restant une mission future.

« Utiliser ce texte » transfère le résultat proposé dans le prompt d'Inference ; bouton indépendant « Enregistrer dans Prompts » (nom obligatoire, doublons toujours autorisés) crée un `Prompt` persistant via une extension additive et rétrocompatible `PromptManager.create(name, text="")`, **sans jamais appeler `select()`** — le Prompt déjà actif dans `PromptsPage` n'est jamais modifié silencieusement (audit pré-implémentation dédié + test dédié).

Ajustement UX pendant le smoke test : dialogue agrandi (800×700, redimensionnable, zones extensibles), et correction d'un défaut de harness de tests (deux `QMessageBox` réelles bloquaient l'exécution automatisée — corrigé en les mockant, comportement applicatif inchangé). **Observation future enregistrée, non implémentée** : Ollama peut retourner du Markdown/une analyse autour du prompt proposé plutôt que le seul texte exploitable — besoin futur d'un contrat LLM plus strict, non traité cette mission.

### Tests ajoutés (Mission 031)

- `tests/integration/test_prompt_assistant_manager.py` (7, **nouveau fichier**) — intentions Créer/Améliorer, construction déterministe et testée du texte combiné envoyé au backend, `model_name` jamais codé en dur, normalisation `AIBackendError`/appel concurrent en une unique `PromptAssistantError`.
- `tests/integration/test_prompt_assistant_worker.py` (5, **nouveau fichier**) — calque exact de `test_generation_worker.py`, `QThread` réel, exécution hors thread principal prouvée.
- `tests/integration/test_prompt_assistant_dialog.py` (13, **nouveau fichier**) — modes Créer/Améliorer, aperçu du prompt existant affiché uniquement en mode Améliorer, appel non bloquant, boutons désactivés pendant l'appel, erreur gérée, handoff du résultat, taille initiale ≥800×700, redimensionnement réellement effectif, part d'étirement du résultat supérieure à celle de la demande ; `QMessageBox.warning`/`.critical` mockées dans les deux scénarios d'erreur (correction de harness post-smoke-test).
- `tests/integration/test_main_window_ollama_settings.py` (3, **nouveau fichier**) — calque exact de `test_main_window_comfyui_settings.py`, confirme explicitement l'absence de rechargement à chaud.
- `tests/integration/test_inference_page.py` (+11 nets) — boutons « Assistant IA »/« Enregistrer dans Prompts », garde de nom identique à `PromptsPage.create_prompt()`, absence de `select()`/`update_text()` depuis Inference, avertissement si aucun personnage principal, test architectural étendu anti-`OllamaEngine`/`urllib`.
- `tests/integration/test_prompt_roundtrip.py` (+1) — `create(name, text=...)` au niveau Manager réel confirmé sans effet sur `active_prompt_id` ni sur la sélection déjà affichée dans `PromptsPage`.
- **589/589 tests verts** au total (549 précédents + 40 nets nouveaux), aucune régression, dernière exécution complète unique sans intervention humaine ni boîte modale réelle (~104 s).
- **Smoke test manuel réel complet contre une instance Ollama réelle, PASS** — ouverture de l'Assistant, modes Créer/Améliorer, prompt actuel affiché comme base, génération réelle, récupération du résultat, « Utiliser ce texte », « Enregistrer dans Prompts » avec nom choisi par l'utilisateur, prompt visible dans `PromptsPage`, gestion propre d'un backend Ollama inaccessible sans crash, UI réutilisable après erreur, taille du dialogue validée visuellement — voir `docs/missions/MISSION_031.md` pour le détail complet.

### État du projet (Mission 031)

`src/domain/prompt.py`, `PromptsPage`, `src/engines/ai_backend.py`, `src/engines/ollama_engine.py` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) reçoit son premier usage utilisateur réel, dans `InferencePage` uniquement — reste ouvert (intégration `PromptsPage`, Character Context, Prompt Library, RAG, vision, propreté de la sortie LLM). La question architecturale d'articulation `PromptsPage`↔`InferencePage` est partiellement tranchée (Option B tactique, Option C confirmée long terme). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `1226342d808936f98673804eb654f6cc048103da` — `feat: add minimal AI Prompt Assistant for Inference`, tag `v0.2-mission031`, GitHub Release publiée).

---

## v0.2-mission030 — 2026-08-18

*Note de régularisation* : cette entrée est rédigée pendant la régularisation documentaire post-publication de Mission 030 — commit, tag, Release et smoke test manuel réel sont déjà tous réels au moment de la rédaction (contrairement au précédent "clôture Git en attente" de Missions 017/027/028/029, ici la clôture Git et la publication étaient déjà effectives avant que cette entrée CHANGELOG ne soit rédigée, un oubli comblé lors de cette régularisation ; le smoke test réel, initialement non confirmé lors d'une première passe de régularisation, a depuis été exécuté et son résultat est intégré ci-dessous).

### Résumé (Mission 030)

**Mission 030 — Ollama Local AI Backend.** Première fondation d'un assistant IA/LLM intégré à AI Studio Toolkit, avec Ollama comme premier backend concret. Nouvelle abstraction structurelle `AIBackend` (`src/engines/ai_backend.py`, `typing.Protocol` `@runtime_checkable`, deux méthodes — `list_models()`/`generate_text()` — plus `AIModelInfo`/`AIBackendError`), pour qu'aucune future fonctionnalité IA ne dépende directement d'un provider particulier — même séparation que `GenerationManager` maintient déjà vis-à-vis de `ComfyUIEngine`. `OllamaEngine` (`src/engines/ollama_engine.py`, nouveau, stdlib `urllib` uniquement, aucune nouvelle dépendance) implémente ce contrat sans en hériter, vérifié contre l'API Ollama réelle documentée : `GET /api/tags` pour la découverte des modèles (seul le nom de chaque modèle est retenu ; la capacité vision n'est pas exposée de façon fiable par cet endpoint — limite documentée, non résolue, `AIModelInfo` reste additif pour l'accueillir plus tard), `POST /api/generate` en mode non-streaming (`"stream": false`) pour la génération de texte — `POST /api/chat`, l'historique de conversation et tout usage vision restent explicitement hors périmètre.

`ApplicationSettings`/`ApplicationSettingsManager`/`SettingsPage` gagnent trois champs (`ollama_url`, `ollama_path`, `ollama_model_name`) suivant exactement le patron déjà établi par `comfyui_url`/`comfyui_path`/`comfyui_checkpoint_name` (Missions 010/018/025), y compris le bouton "Rafraîchir les modèles" et le repli systématique sur la saisie manuelle en cas d'échec — `ollama_path` stocké mais **non consommé par aucun code**, exactement comme `comfyui_path` depuis Mission 010. `ApplicationSettingsManager.update()` passe de 5 à 8 paramètres explicites, un signal concret renforçant le besoin déjà documenté de refonte Settings par provider, non traité cette mission.

**Aucun câblage vers `InferencePage`/`PromptsPage`/`CharactersPage`** — fondation seule, aucune fonctionnalité IA utilisateur finale, aucun contexte Character, aucun historique de prompts, aucune vision, aucun RAG, aucun provider cloud.

### Tests ajoutés (Mission 030)

- `tests/integration/test_ollama_engine.py` (19, **nouveau fichier**) — entièrement mocké, aucune requête réseau réelle : `list_models()` (plusieurs/un seul/zéro modèle, entrées malformées filtrées défensivement, `"models"` absent/non-liste → `AIBackendError`, endpoint `GET /api/tags` vérifié), `generate_text()` (réponse retournée telle quelle, corps de requête exact `model`/`prompt`/`stream: false`, `"response"` absent/non-`str` → `AIBackendError`, message d'erreur Ollama repris dans l'exception, deux appels indépendants sans état partagé), communication (serveur injoignable, JSON invalide, erreur HTTP), et un test architectural dédié confirmant que `OllamaEngine` satisfait structurellement `AIBackend` sans en hériter.
- `tests/integration/test_application_settings_roundtrip.py` (+1 net nouveau) — round-trip/défauts/idempotence `update()`/persistance étendus aux 3 nouveaux champs, nouveau test dédié `test_manager_loads_legacy_settings_file_without_ollama_fields` (un fichier antérieur à Mission 030 charge les défauts littéraux Ollama, pas des chaînes vides).
- `tests/integration/test_settings_page.py` (+14 nets nouveaux) — `SettingsPageOllamaDiscoveryTest`, miroir exact de la couverture ComfyUI existante appliquée au champ modèle Ollama et au bouton de rafraîchissement.
- **549/549 tests verts** au total (513 précédents + 36 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet contre une instance Ollama réelle, PASS** — machine NVIDIA Quadro P4000 (8 Go VRAM), 48 Go RAM, Intel Core i7-7920HQ, Ollama `0.32.14`, modèle `llama3.2:3b` (~2,0 Go) : installation, découverte depuis `SettingsPage` (`1 modèle(s) détecté(s).`), sélection, sauvegarde puis restauration fidèle après redémarrage complet, appel réel `OllamaEngine.generate_text()` hors UI (réponse texte réelle reçue), cas d'erreur URL invalide confirmé sans plantage (message de repli, saisie manuelle toujours disponible). Cas "zéro modèle détecté" non reproduit manuellement (pour ne pas supprimer le modèle installé) — reste couvert par la suite automatisée mockée. **Limite empirique découverte et documentée, non corrigée cette mission** : le tout premier appel `generate_text()` a expiré au bout du timeout par défaut d'`OllamaEngine` (30 s) — Ollama charge le modèle en mémoire/VRAM à la demande lors de sa première utilisation ("cold start"), une opération ayant dépassé 30 s sur cette machine avec ce modèle ; un appel identique suivant, modèle déjà chargé, a réussi immédiatement. Comportement propre à Ollama, pas un défaut du backend — voir `docs/missions/MISSION_030.md` section 13 pour le détail complet.

### État du projet (Mission 030)

Aucun fichier Domain hors `ApplicationSettings` modifié — `InferencePage`, `PromptsPage`, `CharactersPage`, `CharacterManager`, `PromptManager`, `DatasetManager`, `ComfyUIEngine` strictement inchangés. Le besoin futur "Assistant IA / LLM intégré à AI Studio Toolkit" (`docs/PROJECT_CONTEXT.md`) reçoit une première fondation partielle mais reste ouvert — aucun usage utilisateur final (Prompt Assistant, analyse vision, Character Context, Prompt Library, mémoire sémantique) n'est câblé. Validée par la suite automatisée complète **et par un smoke test manuel réel complet, PASS**. **Clôture Git et publication GitHub Release entièrement effectuées** (commit fonctionnel `3a37817b96400d7bd2e6fe7e82f12e230cc6c530` — `feat: add Ollama local AI backend`, tag `v0.2-mission030`, GitHub Release publiée).

---

## v0.2-mission029 — 2026-08-18

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 029 — commit, tag et Release non encore créés à la rédaction (même précédent que Missions 017/027/028). Clôture fonctionnelle uniquement : implémentation, tests et smoke test manuel réel tous validés.

### Résumé (Mission 029)

**Mission 029 — Principal Character Consistency (LoRA / Prompts / Training).** Mission 028 avait identifié, pendant le diagnostic de sa propre régression `DatasetManager`, que `LoRAManager`, `PromptManager` et `TrainingManager` partageaient le même défaut structurel : dépendre de `CharacterManager.active_character` plutôt que de `principal_character`, jamais réaffecté depuis que `CharactersPage` (Mission 026) ne fait plus que lire `principal_character` sans jamais rappeler `select()`. Conséquence réelle, confirmée par lecture directe du code avant toute correction : dans tout Workspace existant rouvert, les trois pages affichaient une liste vide (au lieu des LoRA/Prompts/Trainings réellement enregistrés) et toute création était silencieusement ignorée, sans qu'aucune action utilisateur ne puisse le corriger — la liste multi-personnage étant masquée de l'UI depuis Mission 026.

Un audit exhaustif préalable (`grep -rn "active_character\b"`/`"active_character_id\b"`/`"\.select\("` sur l'intégralité de `src/` et `tests/`, au-delà des neuf occurrences déjà repérées) a classifié chaque occurrence trouvée contre trois catégories — à corriger, à préserver pour la compatibilité multi-Character interne, ou hors périmètre — avant tout remplacement. Il a notamment confirmé que **la totalité** des tests existants de `test_lora_roundtrip.py`/`test_prompt_roundtrip.py`/`test_training_roundtrip.py` appellent `character_manager.select()` explicitement, masquant structurellement le bug réel — exactement la situation qui avait permis à la régression `DatasetManager` de passer inaperçue jusqu'au smoke test réel de Mission 028.

Corrigé par le remplacement à l'identique déjà validé deux fois (`CharactersPage` Mission 026, `DatasetManager` Mission 028) : `active_character` → `principal_character` sur 9 usages Manager (property de collection + `create()` + `delete()`, ×3 Managers), plus mise à jour de 3 docstrings de classe et reformulation de 3 messages UI (`LoRAPage`/`PromptsPage`/`TrainingPage`) devenus trompeurs, sur le modèle exact du message déjà corrigé de `DatasetsPage` en Mission 028. **Aucune modification de `CharacterManager`** (`active_character`, `active_character_id`, `select()`, `_ensure_default_character()` strictement inchangés) **ni de `DatasetManager`** (aucune régression liée découverte). La compatibilité multi-Character interne reste intégralement préservée — confirmée par les 21 tests historiques appelant `select()` explicitement, tous verts sans aucune modification.

### Tests ajoutés (Mission 029)

- `tests/integration/test_lora_roundtrip.py` (+1) — `LoRACreationWithoutManualCharacterSelectionTest` : séquence exacte création Workspace → attache une LoRA → fermeture → réouverture (sans jamais appeler `CharacterManager.select()`) → LoRA existante toujours visible (pas de liste vide) → création d'une seconde LoRA réussie et rattachée au même Character principal (`assertIn`, pas seulement un retour non-`None`) → suppression réussie → persistance confirmée après un second cycle fermeture/réouverture. Vérifie explicitement `active_character_id is None` juste avant l'action testée.
- `tests/integration/test_prompt_roundtrip.py` (+1) — `PromptCreationWithoutManualCharacterSelectionTest` : même séquence, avec en plus la vérification que `update_text()`/`select()` (sélection de l'entité elle-même, mécanisme entièrement indépendant de `CharacterManager.active_character`, non concerné par la correction) continuent de fonctionner à l'identique après réouverture.
- `tests/integration/test_training_roundtrip.py` (+1) — `TrainingCreationWithoutManualCharacterSelectionTest` : même séquence avec un Dataset pré-existant du Character principal, vérifiant que le contrôle d'appartenance du Dataset référencé par `create()` continue de fonctionner correctement une fois `character` résolu via `principal_character`.
- **513/513 tests verts** au total (510 précédents + 3 nets nouveaux), aucune régression Dataset/Character détectée — les 21 tests historiques multi-Character des trois fichiers concernés restent inchangés et verts.
- **Smoke test manuel réel complet, PASS** : après fermeture/réouverture du Workspace, sans jamais visiter Characters ni faire de sélection manuelle, les LoRA/Prompts/Trainings existants sont restés visibles, la création de nouvelles entrées a réussi dans les trois domaines, la suppression a réussi, la persistance a été confirmée après un second cycle fermeture/réouverture. Un point observé (`Training: Idle` affiché par le Dashboard, sans lien avec cette correction — `Idle` reflète l'état d'exécution du moteur Training, pas le nombre de sessions enregistrées) a été enregistré comme nouveau besoin futur distinct, non implémenté cette mission.

### État du projet (Mission 029)

Aucun fichier Domain (`src/domain/*.py`) modifié. Le besoin futur "dette de cohérence Character — `active_character` vs `principal_character` dans `LoRAManager`/`PromptManager`/`TrainingManager`", identifié pendant Mission 028, est désormais **résolu** — retiré de la liste des besoins ouverts dans `docs/PROJECT_CONTEXT.md`. Un nouveau besoin futur a été identifié et consigné, non implémenté cette mission : clarification de l'indicateur `Training: Idle` du Dashboard (distinction nombre de sessions enregistrées / état d'exécution du moteur). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte.

---

## v0.2-mission028 — 2026-08-18

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 028 — commit, tag et Release non encore créés à la rédaction (même précédent que Missions 017/027). Clôture fonctionnelle uniquement : implémentation, tests et smoke test manuel réel tous validés.

### Résumé (Mission 028)

**Mission 028 — Import Images into Workspace.** "Importer des images" ne se contente plus de référencer le chemin externe choisi via `QFileDialog` — AI Studio Toolkit copie désormais physiquement chaque source externe dans le Workspace, le fichier source restant toujours intact à son emplacement d'origine. Nouvelle primitive Infrastructure `WorkspaceStorage.copy_into_workspace()` (+ `is_inside()`, `resolve_collision_free_name()`), appelée par `WorkspaceManager.add_images()` (destination `<workspace_root>/images/`) et `DatasetManager.add_images()` (destination `<workspace_root>/datasets/<dataset_id>/`, un sous-dossier par Dataset identifié par `dataset_id` plutôt que par son nom, pour rester filesystem-safe et sans collision entre Datasets). Une source déjà interne au Workspace — n'importe où sous `Workspace.root`, notamment une image déjà générée sous `outputs/` par le flux Accept d'Inference (Mission 013/014) — est reconnue et réutilisée telle quelle, sans copie ni renommage : découverte pendant l'audit exhaustif des appelants d'`add_images()`, cette règle large (et non limitée au seul dossier de destination exact) est ce qui évite qu'Accept ne duplique silencieusement chaque image générée vers `images/` — vérifié par test dédié, comportement Accept strictement inchangé.

`add_images()` retourne désormais `ImportResult(added, failed, skipped)` plutôt qu'un simple entier : traitement best-effort d'un import multiple (un échec de copie n'empêche jamais les autres fichiers du lot), aucune persistance pour une copie échouée, un doublon (de lot ou source déjà enregistrée) toujours classé `skipped`, jamais confondu avec un `failed`.

**Révisée après un premier smoke test réel (FAIL) ayant révélé deux problèmes fonctionnels**, non corrigés avant un second smoke test réel :

1. **Collision de nom silencieuse, jugée non conforme à l'UX attendue.** Le suffixage automatique (`photo.jpg` → `photo_1.jpg`) fonctionnait mais restait silencieux. Remplacé, côté UI uniquement, par un dialogue unique (`ImportCollisionDialog`, jamais une série d'un dialogue par fichier) : nouvelle méthode `preview_collisions()` (Manager) détecte à l'avance les collisions — y compris entre fichiers du même lot pas encore physiquement copiés — et l'utilisateur choisit, pour chacune, de renommer (nom proposé éditable, pré-rempli avec le même nom collision-safe que l'automatique aurait choisi) ou d'ignorer (`skipped`, jamais `failed`). La primitive Infrastructure non destructive reste inchangée et sert toujours de filet de sécurité par défaut pour tout appelant hors UI (tests, usage programmatique).
2. **Régression bloquante : création de Dataset impossible dans un Workspace existant rouvert.** `DatasetManager` (`datasets`, `create()`, `is_referenced_by_training()`, `delete()`) dépendait encore de `CharacterManager.active_character`, jamais réaffecté depuis que `CharactersPage` (Mission 026) ne fait plus que lire `principal_character` sans jamais rappeler `select()` — un Workspace existant rouvert (`WORKSPACE_OPENED`, sans re-sélection automatique) laissait donc `active_character_id` à `None` pendant toute la session, bloquant "Nouveau dataset" sans qu'aucune action utilisateur ne puisse le corriger (liste multi-personnage masquée). Corrigé en basculant `DatasetManager` sur `CharacterManager.principal_character` — exactement le mécanisme déjà validé par Mission 026 pour `CharactersPage`. Le même défaut, identifié mais **non corrigé** dans cette mission (hors périmètre), affecte aussi `LoRAManager`/`PromptManager`/`TrainingManager` — enregistré comme besoin/audit futur distinct.

Aucune migration rétroactive des références externes déjà persistées ; aucun changement de format de sérialisation (`Image.file_path` reste un `str` absolu — la conversion vers des chemins relatifs appartient à la future Mission 029) ; remap correct par `WorkspaceManager.rename()` (Mission 027) vérifié par test dédié pour toute nouvelle copie interne.

### Tests ajoutés (Mission 028)

- `tests/integration/test_workspace_roundtrip.py` (35 nets nouveaux) — `WorkspaceStorageCopyIntoWorkspaceTest` (14) : `is_inside()` (enfant direct/imbriqué/racine/casse Windows/chemin disparu), `copy_into_workspace()` (copie + source intacte, création défensive du dossier, collision par suffixe numérique enchaîné, source introuvable, nettoyage best-effort d'un fichier partiel, source déjà interne réutilisée sans copie même depuis un sous-dossier différent). `WorkspaceManagerAddImagesCopyTest` (20, dont 9 pour `preview_collisions()`/`renames`) : copie réelle et chemin persisté, source intacte, deux sources différentes même nom jamais écrasées, doublon de lot `skipped`, échec partiel n'empêche pas le reste du lot, aucune persistance pour une copie échouée, source déjà interne réutilisée, persistance après fermeture/réouverture, ancien `project.json` externe inchangé, prévisualisation des collisions (vide/réelle/intra-lot/déjà interne), renommage appliqué verbatim, nom déjà pris → `failed`, comportement automatique silencieux toujours disponible hors UI. 1 test de synergie ajouté à `WorkspaceRenameTest` (import puis renommage → remap correct).
- `tests/integration/test_dataset_roundtrip.py` (17 nets nouveaux) — `DatasetManagerAddImagesCopyTest` (10, dont 3 pour `preview_collisions()`/`renames`) : copie sous `datasets/<dataset_id>/`, source intacte, deux Datasets sans collision croisée, échec partiel, aucune persistance sur échec, source déjà interne réutilisée, ancien `project.json` externe inchangé, persistance après fermeture/réouverture, remap après renommage. `DatasetsPageCollisionDialogTest` (4) : aucun dialogue sans collision, renommer/ignorer appliqués, `Cancel` annule tout l'import. `DatasetCreationWithoutManualCharacterSelectionTest` (1, régression) : séquence exacte create → close → open (sans `select()`) → "Nouveau dataset" réussi → import réussi → persistance après un second cycle fermeture/réouverture.
- `tests/integration/test_images_page.py` (6 nets nouveaux, 17 adaptés) — `ImagesPageCollisionDialogTest` : aucun dialogue sans collision, un seul dialogue pour plusieurs collisions, `Cancel` annule l'import entier, renommer/ignorer appliqués correctement. Les 17 tests existants adaptés distinguent désormais la source externe de la copie interne (assertions basées sur le chemin persisté, plus le nom fictif d'origine) ; les scénarios de fichier "manquant à l'import" reformulés en fichier réel au contenu non chargeable, une source inexistante ne pouvant plus devenir une `Image`.
- `tests/integration/test_image_roundtrip.py`, `test_dataset_roundtrip.py` (tests Manager historiques), `test_dashboard_page.py`, `test_inference_page.py` : fixtures adaptées (fichiers temporaires réels remplaçant les noms fictifs), `test_accept_persists_pending_image_exactly_once` enrichi d'une vérification directe (`shutil.copy2` jamais appelé, `images/` reste vide) prouvant la non-régression du flux Accept.
- **510/510 tests verts** au total (452 précédents + 58 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet, PASS après correction** (un premier smoke test avait révélé les deux problèmes ci-dessus, corrigés puis revalidés) : copie physique confirmée dans `Workspace/images/`, disponibilité indépendante du fichier source externe, dialogue de collision fonctionnel (renommer/ignorer), aucune série de dialogues pour plusieurs collisions, création de Dataset et import d'images fonctionnels sans aucune sélection manuelle de personnage, images de Dataset confirmées sous `datasets/<dataset_id>/`, persistance après renommage de projet et après fermeture/réouverture, flux Inference/Accept confirmé sans copie artificielle vers `images/`.

### État du projet (Mission 028)

Aucun fichier Domain (`src/domain/*.py`) modifié — `Image.file_path` reste un `str` absolu, seule sa provenance change (copie interne plutôt que chemin externe), jamais sa forme ni son type. Deux besoins futurs identifiés et consignés dans `docs/PROJECT_CONTEXT.md`, non implémentés cette mission : alimentation d'un Dataset depuis la galerie Images (sélection multiple dans `ImagesPage`, ajout à un Dataset sans repasser par le sélecteur de fichiers) ; dette de cohérence `active_character`/`principal_character` affectant encore `LoRAManager`/`PromptManager`/`TrainingManager` (`DatasetManager` seul corrigé, strictement dans le périmètre de cette mission). Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte.

---

## v0.2-mission027 — 2026-08-18

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 027 — commit, tag et Release non encore créés à la rédaction (même précédent que Mission 017). Clôture fonctionnelle uniquement : implémentation, tests et smoke test manuel réel tous validés.

### Résumé (Mission 027)

**Mission 027 — Project Rename.** AI Studio Toolkit permet désormais de renommer proprement un projet depuis l'application (menu **Fichier → Renommer le projet…**, `RenameProjectDialog`), plutôt que de dépendre d'un renommage manuel du dossier dans l'Explorateur Windows. Un audit read-only préalable a établi qu'un tel renommage manuel est SAFE SOUS CONDITIONS uniquement lorsque le projet est fermé, et casse au minimum les chemins absolus internes réellement situés sous l'ancien dossier — en particulier les images générées via `Inference` et acceptées, physiquement stockées sous `<workspace>/outputs/` mais dont le chemin absolu est enregistré tel quel dans `Workspace.images[]`.

`WorkspaceManager.rename(new_name) -> bool` orchestre l'opération : renommage physique du dossier (`WorkspaceStorage.rename_folder()`), mise à jour de `Workspace.root`/`Workspace.name`, et remappage des 6 champs de chemins internes identifiés par l'audit (`Workspace.images[].file_path`, `Character.datasets[].images[].file_path`, `Workspace.models[].file_path`, `Workspace.workflows[].file_path`, `Character.loras[].files[]`/`.thumbnail`) — toujours par comparaison composant par composant du chemin (`Path.parts`, normalisée pour l'insensibilité à la casse Windows/NTFS), jamais par substitution de préfixe de chaîne brute. Tout chemin situé hors de l'ancien dossier, et `Character.name`, restent strictement inchangés — aucun couplage introduit entre le nom du projet et celui du personnage (règle déjà actée en Mission 026).

Ordonnancement transactionnel délibéré ("commit en dernier") : `Workspace.rename()` calcule d'abord, sans aucune mutation, le nouveau contenu complet à écrire ; `self.current_workspace` n'est remplacé qu'une fois le renommage physique **et** la sauvegarde de `project.json` tous deux réussis. Si la sauvegarde échoue après un renommage physique réussi, un rollback filesystem best-effort est tenté (renommage en sens inverse) ; son éventuel échec est toujours signalé par une erreur explicite et actionnable, jamais masqué. Cette stratégie s'appuie sur un durcissement nécessaire de `WorkspaceStorage.save()` en écriture atomique (fichier temporaire + `os.replace()`), bénéfique à tous les appelants existants sans changer leur contrat observable.

Un premier smoke test réel a révélé un bug reproductible : un second renommage du même projet, dans la même session ou après fermeture/réouverture, pouvait échouer avec `WinError 5 — Accès refusé`. Un diagnostic exhaustif a d'abord infirmé toute cause interne à l'application (verrou Qt/`QPixmap`, écriture atomique, handle applicatif non libéré — chacune testée activement, jamais reproduite), puis un diagnostic réel avec *Process Explorer* (Sysinternals) a confirmé la cause exacte : `explorer.exe` détient des handles ouverts sur les sous-dossiers du projet (`images`, `outputs`, `models`...) lorsqu'une fenêtre de l'Explorateur Windows y navigue, bloquant le renommage du dossier racine — un verrouillage Windows externe et légitime, jamais une corruption du Workspace ni un défaut de libération de handle applicatif. Traité par un type d'exception dédié (`WorkspaceRenamePermissionError`, à deux niveaux Infrastructure/Manager) et un message utilisateur français actionnable (`QMessageBox.warning`, « Renommage impossible » — dossier/sous-dossier probablement utilisé par une autre application, fermer les fenêtres de l'Explorateur Windows concernées puis réessayer) — **sans jamais tenter de fermer un handle ou un processus externe**, et sans masquer aucune autre erreur sous ce message.

### Tests ajoutés (Mission 027)

- `tests/integration/test_workspace_roundtrip.py` (29 nets nouveaux) — `WorkspaceRenameTest` (23) : renommage simple, idempotence, réparation d'un `Workspace.name` désynchronisé sans renommage physique, `Character.name` jamais touché, remap des 6 champs de chemins internes et préservation stricte des chemins externes et des valeurs vides légitimes, persistance après fermeture/réouverture, `active_*_id` préservés (aucun reset sur `WORKSPACE_RENAMED`), dossier cible déjà existant, échec du rename filesystem initial → Domain strictement inchangé, échec de sauvegarde après renommage réussi → rollback filesystem + Domain jamais muté, échec du rollback lui-même → erreur explicite jamais un `False` silencieux, aucun `WORKSPACE_RENAMED` sur tout chemin d'échec, événement publié exactement une fois au succès, deux renommages consécutifs dans la même session et après un cycle fermeture/réouverture (régression du bug `WinError 5`), `PermissionError` levée comme type dédié et jamais publié d'événement, autres erreurs jamais reclassées comme permission-denied. `WorkspaceStorageAtomicSaveTest` (3) : échec avant `os.replace()` laisse `project.json` intact sans fichier temporaire résiduel. `WorkspaceStorageRenameFolderErrorTest` (3) : `PermissionError` distinguée de tout autre `OSError`.
- `tests/integration/test_rename_project_dialog.py` (10, nouveau fichier) — pré-remplissage depuis le nom réel du dossier, bouton désactivé sur nom vide/invalide/identique/collision, réutilisation de `validate_project_name()` sans duplication, collision de dernière seconde revérifiée à l'instant de l'acceptation, aucune écriture disque.
- `tests/integration/test_main_window_rename_project.py` (10, nouveau fichier) — câblage du menu vers `RenameProjectDialog`/`WorkspaceManager.rename()`, `WorkspaceRenamePermissionError` affichée via `QMessageBox.warning` dédié avec le texte français attendu (jamais `.critical`), toute autre erreur restant sur `.critical` (jamais `.warning`), `open_project()`/`save_project()`/`new_project()` non affectés, résultat de génération pending invalidé après un renommage réussi.
- `tests/integration/test_inference_page.py` (1 nouveau) — `WORKSPACE_RENAMED` ajouté à l'abonnement `reset_for_workspace_change`, invalidant un résultat pending exactement comme `CREATED`/`OPENED`/`CLOSED`.
- **452/452 tests verts** au total (402 précédents + 50 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet, PASS après correction** (un premier smoke test avait révélé le bug `WinError 5` ci-dessus, corrigé puis revalidé) : chaîne `ProjetA → ProjetB → ProjetC` sans redémarrage, cycle fermeture/réouverture puis renommage vers `ProjetD`, image réelle sous `outputs/` correctement remappée, ressource externe strictement inchangée, `Character.name` inchangé, blocage propre et message français actionnable confirmés avec une fenêtre de l'Explorateur Windows ouverte dans un sous-dossier du projet, résolution immédiate après fermeture de cette fenêtre.

### État du projet (Mission 027)

Aucun fichier Domain (`src/domain/*.py`) modifié. Nouvel événement `WORKSPACE_RENAMED`, ajouté aux abonnements de rafraîchissement des Pages et à celui d'invalidation du résultat pending d'`InferencePage` — jamais aux resets internes `active_*_id` des autres Managers (un renommage ne change l'identité d'aucune entité). Besoin architectural identifié mais non implémenté cette mission, consigné dans `docs/PROJECT_CONTEXT.md` : les ressources internes au Workspace devraient-elles être persistées relativement à `Workspace.root` plutôt qu'en chemins absolus (pertinent aussi pour la portabilité/déplacement d'un projet) ; et, distinctement, les images importées devraient-elles être copiées dans le dossier `images` du projet plutôt que simplement référencées par leur emplacement externe, pour l'autonomie du projet. Validée par la suite automatisée complète et par un smoke test manuel réel. **Clôture Git non encore effectuée** — en attente de l'autorisation explicite de l'architecte.

---

## v0.2-mission026 — 2026-08-17

### Résumé (Mission 026)

**Mission 026 — Character Identity Foundation.** `Character` gagne six champs additifs et rétrocompatibles — `bio`, `description`, `character_lock`, `personality`, `interests`, `trigger_token` (tous `str`, défaut `""`) — organisés conceptuellement en 5 catégories (Identité, Apparence/identité visuelle, Personnalité, Goûts et centres d'intérêt, Informations techniques IA) mais stockés en dataclass plate, sans sur-conception en sous-objets : une catégorie sans consommateur technique identifié reçoit un seul champ texte libre consolidé plutôt que des scalaires spéculatifs individuels ; `character_lock`/`trigger_token` gardent leur champ dédié, leur usage technique futur étant déjà nommé. `CharacterManager.update()` (idempotent, jamais d'événement publié, même contrat que `PromptManager.update_text()`) gère aussi bien ces champs que le renommage du personnage.

**Révisée deux fois après smoke test réel**, chacune corrigeant une incohérence constatée en conditions réelles :
1. Un Workspace nouvellement créé n'avait initialement aucun Character, obligeant un clic "Nouveau personnage" avant de pouvoir remplir la fiche — contraire à l'orientation produit "1 Workspace = 1 personnage principal". Corrigé : `CharacterManager` crée et sélectionne désormais automatiquement un personnage principal (nommé depuis `Workspace.name`) dès qu'un Workspace vide de personnages reçoit `WORKSPACE_CREATED` — jamais sur `WORKSPACE_OPENED`, pour ne jamais annuler silencieusement une suppression volontaire de l'utilisateur.
2. Une fois cette création automatique en place, la liste et les boutons "Nouveau personnage"/"Supprimer" ne correspondaient plus à l'UX cible, et un bug empêchait la sauvegarde de la fiche dans le flux le plus simple (`QMessageBox` "Aucun personnage sélectionné" malgré une fiche correctement affichée). Corrigé : `CharactersPage` masque désormais (`setVisible(False)`, jamais retiré) la liste et les boutons multi-personnage — `Characters` représente directement la fiche du personnage principal — et `save_identity()` utilise `CharacterManager.principal_character_id` (repli sur le premier personnage si aucune sélection active) plutôt que de dépendre du mécanisme historique de sélection.

`Workspace.characters: list[Character]` et le CRUD multi-personnage (`create()`/`delete()`, sérialisation) restent des **mécanismes internes transitoires intacts** — aucune migration, aucune contrainte de cardinalité `max=1` introduite ; les 7 tests historiques multi-personnage passent sans modification de leurs assertions substantielles. `Workspace.name` et `Character.name` peuvent diverger librement après l'initialisation : renommer le Character ne modifie jamais le Workspace/dossier du projet, et réciproquement.

### Tests ajoutés (Mission 026)

- `tests/integration/test_character_roundtrip.py` (39 — 7 précédents adaptés + 32 nets nouveaux) : défauts/`to_dict()`/`from_dict()`/rétrocompatibilité legacy des six champs d'identité ; `CharacterManager.update()` idempotent (renommage inclus, jamais d'événement) ; création/sélection automatique du personnage principal sur `WORKSPACE_CREATED` (nom = `workspace.name`, persistée, aucun double si republié, jamais sur `WORKSPACE_OPENED`) ; fiche `CharactersPage` en 5 sections peuplée/vidée sans fuite entre personnages, immédiatement active sans aucun clic ; contrôles multi-personnage masqués (`isHidden()`) ; `principal_character_id` avec repli sur le premier personnage y compris quand `active_character_id` a été perdu (test de régression, confirmé FAIL avant correction, PASS après) ; test architectural confirmant l'absence de toute référence aux nouveaux champs dans le code de génération.
- `tests/integration/test_dataset_roundtrip.py`, `test_lora_roundtrip.py`, `test_prompt_roundtrip.py`, `test_training_roundtrip.py` (0 nouveau test chacun, assertions adaptées) : recherche explicite du Character par nom (jamais par index de liste) après réouverture, compteur d'abonnés `WORKSPACE_CREATED` mis à jour.
- `tests/integration/test_model_roundtrip.py`, `test_workflow_roundtrip.py` (0 nouveau test chacun) : compteur d'abonnés `WORKSPACE_CREATED` mis à jour (découverte complémentaire, hors périmètre initialement balisé, signalée par transparence).
- **402/402 tests verts** au total (370 précédents + 32 nets nouveaux), aucune régression détectée, aucune assertion supprimée pour faire passer la suite.
- **Smoke test manuel réel complet, troisième tentative concluante** (les deux premières ayant chacune révélé une incohérence corrigée avant re-test) : personnage principal auto-créé et immédiatement utilisable dès la création d'un projet, `Nom` initial = nom du projet, aucune liste ni bouton multi-personnage visible, sauvegarde réussie y compris répétée dans la même session, fermeture/réouverture avec restauration fidèle de toute la fiche (renommage inclus), aucune `QMessageBox` d'erreur, nom du Workspace/projet inchangé malgré le renommage du personnage. PASS.

### État du projet (Mission 026)

Aucun nouvel événement EventBus publié par les nouveaux champs/méthodes d'identité. `Workspace.characters` reste `list[Character]`, sans migration ni contrainte de cardinalité — compatibilité interne multi-Character conservée temporairement, en attente d'une future décision architecturale sur la cardinalité produit "1 Workspace = 1 personnage principal". Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission025 — 2026-08-17

### Résumé (Mission 025)

**Mission 025 — ComfyUI Checkpoint Discovery & Selection.** `SettingsPage` expose désormais `ComfyUI Checkpoint` comme un `QComboBox` éditable (`comfyui_checkpoint_name_edit`, attribut conservé) plutôt qu'un `QLineEdit` en texte libre, accompagné d'un nouveau bouton "Rafraîchir les checkpoints". La découverte des checkpoints est réalisée par une nouvelle méthode additive `ComfyUIEngine.list_checkpoints()` (`GET /object_info/CheckpointLoaderSimple`, réutilisant `_request_json()` déjà existant, timeout court dédié distinct du timeout de génération) — **délibérément pas** par un scan du champ `comfyui_path` déjà existant, contrairement à l'hypothèse initiale de la spécification. Un audit read-only complémentaire, mené avant toute implémentation, a établi que l'installation réelle de l'architecte (ComfyUI Desktop pour Windows) démarre avec `--extra-model-paths-config .../shared_models.yaml` : les checkpoints réellement exposés peuvent provenir de chemins additionnels/partagés que ComfyUI résout déjà correctement en interne. Interroger directement le serveur en cours d'exécution via `comfyui_url` (déjà exploité depuis Mission 018) évite toute réimplémentation de cette résolution de chemins, et fonctionne identiquement pour une installation locale, portable, Desktop ou distante. La découverte n'est déclenchée que sur clic explicite du bouton (jamais au chargement de Settings, aucune surveillance filesystem/réseau permanente), avec un repli systématique et permanent sur la saisie manuelle en cas d'échec (serveur injoignable, URL invalide, réponse inattendue) — `ComfyUIEngineError` toujours capturée par `SettingsPage`, qui ne plante jamais. `comfyui_path` reste, à l'issue de cette mission, un champ existant mais **non consommé par aucun code** — son besoin d'exploitation future reste entièrement ouvert, désormais documenté indépendamment de la sélection de checkpoint (voir `docs/PROJECT_CONTEXT.md`).

### Tests ajoutés (Mission 025)

- `tests/integration/test_comfyui_engine.py` (15 nouveaux tests) — `list_checkpoints()` : extraction correcte de plusieurs/un seul/zéro checkpoint, requête `GET` vers le bon endpoint, retour strictement `list[str]` sans fuite de la structure brute `object_info`, entrées non-`str` filtrées défensivement, `ComfyUIEngineError` sur `CheckpointLoaderSimple` absent/forme inattendue/`ckpt_name` non-liste/JSON invalide/erreur HTTP/serveur injoignable/timeout socket/URL structurellement invalide, timeout effectivement transmis à `urlopen()`.
- `tests/integration/test_settings_page.py` (14 nouveaux tests, **nouveau fichier** — première couverture Qt dédiée à `SettingsPage`) — champ checkpoint est un `QComboBox` éditable, valeur persistée restaurée au chargement, rafraîchissement peuplant la liste, valeur actuellement affichée toujours conservée même absente de la liste découverte, sélection puis sauvegarde, saisie manuelle puis sauvegarde, rechargement restaurant la valeur, URL actuellement tapée utilisée (pas nécessairement enregistrée), timeout court dédié confirmé, échec de découverte sans plantage et `SettingsPage` toujours utilisable, zéro checkpoint découvert sans erreur, bouton présent, aucune interférence avec les autres champs Application, aucune découverte automatique au chargement.
- `tests/integration/test_application_settings_roundtrip.py` (0 nouveau test, 2 lignes corrigées) — `test_settings_page_application_section_lifecycle` adapté au changement de type `QLineEdit` → `QComboBox` (`.text()`/`.setText()` → `.currentText()`/`.setCurrentText()`), trouvé par la recherche préalable systématique de mocks/signatures obsolètes (procédure établie Mission 022).
- **370/370 tests verts** au total (341 précédents + 29 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet** contre ComfyUI Desktop (`http://127.0.0.1:8000`) : découverte réelle des checkpoints exposés, liste déroulante fonctionnelle, sélection, sauvegarde, restauration après redémarrage de l'application, génération txt2img réelle confirmant le checkpoint effectivement utilisé, et validation explicite du cas de fallback (ComfyUI arrêté/URL invalide) — aucun plantage, message d'indisponibilité affiché, saisie manuelle toujours disponible. PASS.

### État du projet (Mission 025)

Aucun nouveau Domain/Manager/Service/EventBus event. `comfyui_workflows.py`, `generation_manager.py`, `generation_worker.py`, `inference_page.py` strictement inchangés (aucun paramètre Mission 024 affecté). `comfyui_path` reste non consommé. Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission024 — 2026-08-17

### Résumé (Mission 024)

**Mission 024 — Réglage utilisateur de la force img2img.** `DEFAULT_IMG2IMG_DENOISE` (Mission 023, fixé à `0.75`) devient ajustable par l'utilisateur : `InferencePage` gagne un `QSlider` (plage `0`–`100`, valeur par défaut `75`) libellé « Force de transformation », accompagné d'un label numérique synchronisé (`"0.75"`, deux décimales) — visible mais désactivé sans référence, activé dès qu'une référence est sélectionnée, réinitialisé (valeur et état) au retrait de la référence et au changement de Workspace, sans aucune persistance (ni session, ni `project.json`). Le concept reste générique (`reference_strength: float`, `0.0`–`1.0`) à travers `InferencePage`/`GenerationWorker`/`GenerationManager.generate()` ; la traduction vers le vocabulaire natif ComfyUI (`denoise`) n'a lieu qu'à l'unique appel `GenerationManager` → `ComfyUIEngine.generate_image(denoise=...)`, et uniquement lorsqu'une référence est présente et qu'une valeur est fournie — sinon `ComfyUIEngine`/`build_img2img_workflow()` retombent sur leur défaut existant, garantissant structurellement (pas par convention) que le comportement historique `0.75` reste inchangé pour un utilisateur qui ne touche jamais au slider. `build_img2img_workflow()`/`comfyui_workflows.py` strictement inchangés (le paramètre `denoise` y existait déjà depuis Mission 023). Sans référence, le chemin txt2img reste strictement inchangé. Aucun terme `"denoise"` n'apparaît dans `inference_page.py`, vérifié par test architectural dédié.

### Tests ajoutés (Mission 024)

- `tests/integration/test_comfyui_engine.py` (2 nouveaux tests) — `generate_image(denoise=X)` transmet bien `X` au graphe img2img soumis ; comportement par défaut préservé si omis.
- `tests/integration/test_generation_manager.py` (4 nouveaux tests) — `reference_strength` transmis comme `denoise=` uniquement quand une référence est présente et une valeur fournie ; ignoré dans tous les autres cas ; signature générique confirmée.
- `tests/integration/test_generation_worker.py` (3 nouveaux tests) — `reference_strength` capturé immédiatement à la construction (valeur immuable) et transmis à `generate()` ; défaut `None` inchangé.
- `tests/integration/test_inference_page.py` (11 nouveaux tests) — libellé, état initial du slider, activation/désactivation selon la présence d'une référence, synchronisation du label numérique, conversion `75 → 0.75`, transmission de la valeur par défaut et d'une valeur personnalisée, reset au retrait de la référence et au changement de Workspace, désactivation pendant une génération avec réactivation conditionnelle, test architectural anti-`"denoise"`.
- **341/341 tests verts** au total (321 précédents + 20 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet** contre ComfyUI Desktop (`http://127.0.0.1:8000`), même référence et même prompt que Mission 023, trois forces testées : `0.20` (résultat très proche de la référence), `0.75` par défaut (transformation intermédiaire, cohérente avec la régression Mission 023), `0.95` (transformation forte, prompt nettement dominant) — progression jugée clairement perceptible et cohérente avec le comportement attendu. PASS.

### État du projet (Mission 024)

Aucun nouveau Domain/Manager/Service/EventBus event. `comfyui_workflows.py` strictement inchangé. Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission023 — 2026-08-17

### Résumé (Mission 023)

**Mission 023 — ComfyUI Img2Img Reference Workflow.** La référence sélectionnée dans `InferencePage` (Mission 022) influence désormais réellement le résultat généré, pour la première fois, via un workflow img2img natif ComfyUI. Nouveau module `src/engines/workflows/comfyui_workflows.py` séparant la construction des graphes ComfyUI du transport HTTP — `build_demo_workflow()` déplacée à l'identique et renommée `build_txt2img_workflow()` (mêmes node IDs, mêmes `class_type`, mêmes valeurs, aucun changement de comportement), et nouveau `build_img2img_workflow()` : `LoadImage → VAEEncode → KSampler(denoise=0.75) → VAEDecode → SaveImage`, nodes core ComfyUI uniquement, aucun custom node, aucun IP-Adapter, aucun ControlNet. `ComfyUIEngine.generate_image()` choisit le graphe selon la présence d'un `reference_image` (le `dict` structuré retourné par `upload_image()`, Mission 021) ; une nouvelle méthode privée `_submit_and_download()` factorise la séquence `submit → wait_for_result → download_output`, partagée sans duplication entre les deux graphes. `GenerationManager.generate()` uploade au plus une référence et transmet le résultat d'upload de façon strictement opaque à `generate_image()` — sans jamais interpréter de structure JSON/node ComfyUI. Plus d'une référence est explicitement rejetée (`GenerationError`, avant tout upload) : une limite propre à ce workflow, pas un retrait de l'architecture `reference_images: list[str]` (0..N) déjà établie en Mission 022. Sans référence, le chemin txt2img reste strictement inchangé. `InferencePage`/`GenerationWorker` non modifiés. Validée par la suite automatisée complète **et par un smoke test manuel réel** contre ComfyUI Desktop : régression txt2img confirmée, img2img confirmé (référence et prompt tous deux observés comme influençant réellement le résultat), avec l'observation que l'équilibre entre les deux dépend de la proximité sémantique référence/prompt et du checkpoint utilisé — enregistré comme besoin futur (réglage utilisateur de la force img2img), non implémenté cette mission.

### Tests ajoutés (Mission 023)

- `tests/integration/test_comfyui_workflows.py` (27 nouveaux tests, nouveau fichier) — `build_txt2img_workflow()` équivalente en tous points à l'ancienne `build_demo_workflow()`, `build_img2img_workflow()` : présence `LoadImage`/`VAEEncode`, absence d'`EmptyLatentImage`, `denoise` par défaut `0.75` et surchargeable, traduction correcte de `name`/`subfolder` en input `LoadImage`.
- `tests/integration/test_comfyui_engine.py` (3 nouveaux tests) — `generate_image()` sans/avec `reference_image` soumet respectivement le graphe txt2img/img2img ; tests architecturaux renommés et étendus (`build_txt2img_workflow`/`build_img2img_workflow`, `_submit_and_download()` toujours agnostique de tout graphe).
- `tests/integration/test_generation_manager.py` (6 nets nouveaux tests — 2 tests Mission 022 sur l'upload de plusieurs références supprimés et remplacés, changement de contrat assumé) — plus d'une référence rejetée avant tout upload, transmission opaque du résultat d'upload prouvée explicitement, test architectural confirmant l'absence de toute connaissance JSON/node ComfyUI dans `GenerationManager`.
- **321/321 tests verts** au total (287 précédents + 34 nets nouveaux), aucune régression détectée.
- **Smoke test manuel réel complet** contre ComfyUI Desktop (`http://127.0.0.1:8000`, checkpoint `v1-5-pruned-emaonly-fp16.safetensors`) : régression txt2img PASS, img2img avec prompt cohérent PASS, diagnostic de câblage sans anomalie détectée, img2img avec prompt volontairement contradictoire PASS.

### État du projet (Mission 023)

Aucun nouveau Domain/Manager/Service/EventBus event. `submit()`/`wait_for_result()`/`download_output()`/`upload_image()` strictement inchangées. `InferencePage`/`GenerationWorker` non modifiés. Validée par la suite automatisée complète et par un smoke test manuel réel.

---

## v0.2-mission022 — 2026-08-15

### Résumé (Mission 022)

**Mission 022 — Reference Image Transport Wiring.** La primitive `ComfyUIEngine.upload_image()` (Mission 021), jusque-là non appelée nulle part dans le code applicatif, est désormais réellement câblée à la verticale Inference. `InferencePage` gagne une sélection 0/1 d'image de référence locale, réutilisant le pattern `QFileDialog` déjà employé par `ImagesPage`/`DatasetsPage` : bouton de sélection, label affichant le nom du fichier, bouton de retrait — état transitoire, jamais persisté dans `project.json`, réinitialisé sur changement de Workspace. À la frontière `InferencePage → GenerationWorker`, la sélection devient une collection `reference_images: list[str]` — jamais un singleton — capturée dans un snapshot défensif avant le démarrage du thread, immunisé contre tout changement de sélection UI pendant que la génération tourne. `GenerationManager.generate(prompt_text, output_directory, reference_images=None)` uploade chaque référence via `upload_image()`, dans l'ordre, avant `generate_image()`, avec un comportement fail-fast : le premier échec d'upload interrompt immédiatement la génération (normalisée en `GenerationError`, comme toute autre erreur de cette méthode), sans jamais atteindre `generate_image()`. Sans référence, le comportement reste strictement identique à avant cette mission — aucun appel à `upload_image()`. Cette mission reste volontairement une fondation de transport : la référence uploadée n'est utilisée dans aucun workflow, aucun node `LoadImage`, aucun img2img, aucune notion de rôle — `generate_image()`, `build_demo_workflow()` et `upload_image()` elle-même restent strictement inchangés, et le résultat généré n'est visuellement affecté en rien par la présence d'une référence.

### Tests ajoutés (Mission 022)

- `tests/integration/test_generation_manager.py` (9 nouveaux tests) — `reference_images` `None`/vide sans appel `upload_image`, une puis plusieurs références uploadées dans l'ordre, fail-fast au premier échec d'upload, normalisation `GenerationError` cohérente.
- `tests/integration/test_generation_worker.py` (3 nouveaux tests) — propagation de `reference_images` au constructeur, défaut `[]`, snapshot défensif prouvé indépendant de toute mutation ultérieure de la liste de l'appelant.
- `tests/integration/test_inference_page.py` (11 nouveaux tests) — sélection/annulation/remplacement/retrait de référence, propagation `[]`/`[chemin]` vers `GenerationManager`, non-interférence d'un changement de sélection après lancement, réinitialisation sur changement de Workspace, non-persistance dans `Workspace.images`. Correction, sans changement de comportement applicatif, de 6 fonctions locales préexistantes (`generate_side_effect`/`slow_generate`) dont l'ancienne signature à 2 paramètres était devenue incompatible avec l'appel `generate()` désormais toujours muni de `reference_images=`.
- **287/287 tests verts** au total (264 précédents + 23 nouveaux), aucune régression détectée.

### État du projet (Mission 022)

Aucun nouveau Domain/Manager/Service/EventBus event. `ComfyUIEngine.upload_image()`/`generate_image()`/`build_demo_workflow()` inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission021 — 2026-08-15

### Résumé (Mission 021)

**Mission 021 — ComfyUI Image Upload.** `ComfyUIEngine` gagne une quatrième primitive générique, `upload_image(file_path, subfolder="", overwrite=False)`, qui envoie un fichier image local vers l'instance ComfyUI (`POST /upload/image`) — le premier sens de transport `AI Studio Toolkit → ComfyUI`, les trois primitives existantes (`submit`/`wait_for_result`/`download_output`) ne couvrant jusqu'ici que le sens inverse. Le corps `multipart/form-data` est construit manuellement avec la seule bibliothèque standard (`uuid` pour la frontière, `mimetypes` pour deviner le `Content-Type`, repli `application/octet-stream`) — aucune nouvelle dépendance. Le champ `type` est envoyé en dur à `"input"` (seule valeur utile à un futur node `LoadImage`, non exposée en paramètre) ; `subfolder` est transmis tel quel ; `overwrite` n'est envoyé que lorsqu'il vaut `True`, conformément au contrat réel de ComfyUI (vérifié directement contre le code source `server.py`). La méthode retourne un `dict` structuré `{"name", "subfolder", "type"}` reflétant fidèlement la réponse ComfyUI — jamais réduit à un simple nom de fichier — et valide les trois champs (chaînes non vides pour `name`/`type`, chaîne pour `subfolder`) avant de le retourner, sinon lève `ComfyUIEngineError`. Les erreurs locales (fichier introuvable ou illisible) restent des exceptions natives (`FileNotFoundError`/`OSError`) non enveloppées, cohérent avec la convention déjà établie par `download_output()`. `ComfyUIEngine` ne conserve aucun état lié aux uploads : chaque appel est strictement indépendant, appelable autant de fois que nécessaire pour des images distinctes — propriété vérifiée par un test dédié. Cette mission reste volontairement une primitive de transport pure : aucune sélection d'image dans `InferencePage`, aucune modification de `GenerationManager`, `generate_image()` ou `build_demo_workflow()`, aucune orchestration de rôle (identité, vêtement, décor, pose...), aucun mécanisme moteur (img2img, IP-Adapter, ControlNet) — cette primitive prépare seulement, sans l'implémenter, un futur besoin d'images de référence multiples.

### Tests ajoutés (Mission 021)

- `tests/integration/test_comfyui_engine.py` (18 nouveaux tests, classe `ComfyUIEngineUploadImageTest`, 25 tests existants conservés sans modification) — upload réussi et retour structuré, requête multipart réelle (endpoint, boundary, filename et octets exacts, champ `type="input"`), `subfolder` transmis et restitué, `overwrite` présent uniquement si demandé, validation structurelle de la réponse (`name`/`subfolder`/`type` manquant, mal typé ou vide → `ComfyUIEngineError`), JSON invalide, erreur HTTP à corps vide, serveur injoignable, fichier local inexistant (`FileNotFoundError` non enveloppée), deux appels indépendants pour deux images distinctes sans état partagé.
- **264/264 tests verts** au total (246 précédents + 18 nouveaux), aucune régression détectée.

### État du projet (Mission 021)

Aucun nouveau Domain/Manager/Service/EventBus event. `GenerationManager`, `InferencePage`, `generate_image()`, `build_demo_workflow()` strictement inchangés. Aucune orchestration Reference Image introduite. Validée par la suite automatisée complète.

---

## v0.2-mission020 — 2026-08-15

### Résumé (Mission 020)

**Mission 020 — MainToolBar Actions Wiring.** Les trois `QAction` de `MainToolBar` ("Open", "Save", "Run"), jusque-là anonymes et strictement inertes (aucun `.triggered.connect()` nulle part, la barre d'outils elle-même n'étant pas conservée comme attribut de `MainWindow`), sont désormais stockées comme attributs explicites (`action_open`, `action_save`, `action_run`). Open et Save sont câblées directement dans `MainWindow` vers `open_project()`/`save_project()` déjà existants — réutilisation stricte, aucune méthode intermédiaire, aucun comportement modifié (sélection de dossier, annulation, feedback status bar, gestion d'erreur, y compris le cas "aucun Workspace ouvert" pour Save, qui continue d'afficher `"Aucun projet ouvert"` sans appeler `WorkspaceManager.save()`). Run reste visible mais explicitement désactivé (`setEnabled(False)`), avec un tooltip expliquant que l'exécution depuis la barre d'outils n'est pas encore disponible — aucune sémantique inventée, même traitement que le bouton "Lancer un entraînement" du Dashboard (Mission 017), faute de toute cible fonctionnelle générique légitime dans le projet. `MainToolBar` reste un composant Presentation pur, sans logique métier, Workspace ou Manager.

### Tests ajoutés (Mission 020)

- `tests/integration/test_main_toolbar.py` (nouveau, 6 tests) — comportement observable via de vrais widgets Qt et une vraie `MainWindow` : Open avec dossier sélectionné/annulé, Save avec/sans Workspace ouvert (y compris le message de status bar existant), Run désactivé avec son tooltip d'indisponibilité.
- **246/246 tests verts** au total (240 précédents + 6 nouveaux), aucune régression détectée.

### État du projet (Mission 020)

Aucun nouveau Domain/Manager/Service/Engine. `open_project()`/`save_project()` inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission019 — 2026-08-15

### Résumé (Mission 019)

**Mission 019 — Images Gallery / Thumbnails.** `ImagesPage` passe d'une liste texte de chemins de fichiers bruts à une galerie visuelle avec miniatures : `QListWidget` conservé (pas de `QListView`/modèle custom), passé en `QListWidget.IconMode`. Chaque image reste représentée par un seul `QListWidgetItem` : une miniature (`QPixmap` redimensionné, ratio conservé via `Qt.KeepAspectRatio`, transformation lissée via `Qt.SmoothTransformation`, construite avant le `QIcon` — jamais un icône sur pixmap pleine résolution), un label court (`Path(file_path).name`) et un tooltip affichant le chemin complet. Le chemin complet est désormais stocké dans `Qt.UserRole`, devenu la seule source utilisée par le double-clic et le bouton "Voir en grand" (`item.text()` n'est plus qu'un label de présentation). Pour tout fichier manquant ou illisible, une icône de repli Qt standard est utilisée — l'item reste conservé dans la galerie, `Qt.UserRole`/tooltip restent renseignés, et `ImagePreviewDialog` (non modifié) continue d'afficher son message d'indisponibilité existant. Sélection, import, `WorkspaceManager`, `Image` Domain et EventBus restent strictement inchangés. Aucun cache de miniatures, aucun lazy loading, aucun worker thread introduit.

### Tests ajoutés (Mission 019)

- `tests/integration/test_images_page.py` (6 nouveaux tests, 11 existants conservés sans modification) — `IconMode` actif, image valide (icône non nulle, label court, tooltip et `Qt.UserRole` corrects), fichier manquant et fichier invalide (icône de repli, item conservé, `Qt.UserRole` préservé, sélection/preview toujours fonctionnels), plusieurs images avec `Qt.UserRole` distincts.
- `tests/integration/test_inference_page.py` — adaptation minimale d'un helper de test interne (`_images_page_paths()`) vers `item.data(Qt.UserRole)`, imposée par le changement de représentation des items ; aucune modification du comportement Inference.
- **240/240 tests verts** au total (234 précédents + 6 nouveaux), aucune régression détectée.

### État du projet (Mission 019)

Aucun nouveau Domain/Manager/Service/Engine. `ImagePreviewDialog`/`WorkspaceManager`/`Image` Domain/EventBus inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission018 — 2026-08-14

### Résumé (Mission 018)

**Mission 018 — ComfyUI Application Settings.** L'URL du serveur ComfyUI et le nom du checkpoint utilisé par défaut, jusqu'ici codés en dur dans `main_window.py` (`COMFYUI_BASE_URL`/`COMFYUI_CHECKPOINT_NAME`, désormais supprimées), sont devenus deux champs (`comfyui_url`, `comfyui_checkpoint_name`) d'`ApplicationSettings`, qui en est la source de vérité unique — pas de second niveau de configuration ni de repli ailleurs dans le code. Leurs valeurs par défaut sont identiques au comportement précédemment codé en dur (`http://127.0.0.1:8000`, `v1-5-pruned-emaonly-fp16.safetensors`), y compris pour un fichier `application_settings.json` antérieur à cette mission et dépourvu de ces deux clés — comportement ComfyUI strictement inchangé pour toute installation existante. Les deux valeurs sont consultables et modifiables depuis la section Application de `SettingsPage`, persistées via `ApplicationSettingsManager.update()` déjà existant (aucun nouveau Manager, Service ni abstraction). Un changement sauvegardé ne prend effet qu'au prochain démarrage de l'application — aucune reconfiguration à chaud, un rappel textuel en informe l'utilisateur dans `SettingsPage`. `ComfyUIEngine` et `GenerationManager` restent strictement inchangés.

### Tests ajoutés (Mission 018)

- `tests/integration/test_application_settings_roundtrip.py` (4 tests étendus, 1 nouveau) et `tests/integration/test_main_window_comfyui_settings.py` (nouveau, 2 tests) — **3 nouveaux tests**, comportement observable (défauts réels, round-trip, compatibilité avec un fichier de settings antérieur à cette mission, affichage/sauvegarde depuis `SettingsPage`, `MainWindow` réel utilisant effectivement la configuration ComfyUI issue d'`ApplicationSettings`).
- **234/234 tests verts** au total (231 précédents + 3 nouveaux), aucune régression détectée.

### État du projet (Mission 018)

Aucun nouveau Domain/Manager/Service/Engine. `ComfyUIEngine`/`GenerationManager` inchangés. Validée par la suite automatisée complète.

---

## v0.2-mission017 — 2026-08-14

### Résumé (Mission 017)

**Mission 017 — Dashboard Actions Wiring.** Les quatre boutons d'action du Dashboard (`newProjectButton`, `openProjectButton`, `importImagesButton`, `trainingButton`), visibles mais strictement inertes jusqu'à cette mission (aucun `.clicked.connect()` nulle part dans le code, confirmé par audit), sont désormais fonctionnels pour les trois premiers : câblés directement depuis `MainWindow` vers les comportements déjà existants — `MainWindow.new_project()` (flux `NewProjectDialog` → `WorkspaceManager.create()`, Mission 016, strictement inchangé), `MainWindow.open_project()`, et `ImagesPage.import_images()` (méthode publique déjà utilisée par le bouton d'import natif d'`ImagesPage`). Aucune logique de création, d'ouverture ou d'import n'est dupliquée dans `DashboardPage`, qui reste une vue UI pure sans référence Manager. Le bouton "Lancer un entraînement" reste visible mais devient explicitement désactivé, avec un tooltip indiquant que le lancement réel de l'entraînement n'est pas disponible dans cette version — aucun faux handler, aucun stub de Training Service, aucun nouveau Domain/Manager/Engine/Job/Plugin.

*Note de clôture Git* : cette entrée est rédigée avant la clôture Git de Mission 017 — tag et Release non encore créés à la rédaction. Voir `docs/missions/MISSION_017.md` pour l'état exact.

### Tests ajoutés (Mission 017)

- `tests/integration/test_dashboard_page.py` (nouveau, 6 tests) — widgets Qt réels, clic effectif sur les boutons via une `MainWindow` réelle, comportement observable exercé de bout en bout (seules les E/S externes sont patchées) : création de projet acceptée/annulée, ouverture de projet, import réel d'une image dans `Workspace.images`, désactivation et tooltip du bouton Training.
- **231/231 tests verts** au total (225 précédents + 6 nouveaux), aucune régression détectée.

### État du projet (Mission 017)

Aucun nouveau Domain/Manager/Service/Engine/Job/Plugin. `DashboardPage` reste une vue UI pure. Validée par la suite automatisée complète.

---

## [v0.2-mission016](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission016) — 2026-08-14

### Résumé (Mission 016)

**Mission 016 — Direct Project Folder Creation.** Le flux "Nouveau projet" repose désormais sur un dialogue dédié (`NewProjectDialog`) permettant de créer directement le dossier du nouveau projet depuis AI Studio Toolkit, sans devoir le créer au préalable dans l'Explorateur Windows : choix d'un dossier parent existant, saisie du nom, aperçu du chemin final, création automatique du dossier et de la structure Workspace standard (`project.json` + sous-répertoires), ouverture immédiate. Validation du nom (chaîne vide, caractères Windows interdits, noms réservés, espace/point final) et refus explicite d'une collision avec un dossier ou fichier déjà existant — jamais d'écrasement silencieux, revérifié à l'instant exact de la validation pour couvrir le cas d'une cible apparue entretemps sur le disque. Les flux "Ouvrir un projet" et "Sauvegarder" restent strictement inchangés.

### Tests ajoutés (Mission 016)

- `tests/integration/test_new_project_dialog.py` (31 tests) et `tests/integration/test_main_window_new_project.py` (4 tests) — **35 nouveaux tests**.
- **225/225 tests verts** au total (190 précédents + 35 nouveaux), aucune régression détectée.

### État du projet (Mission 016)

`WorkspaceManager`/`WorkspaceStorage` inchangés — ils étaient déjà capables de créer un dossier inexistant ; seule l'interface en était incapable. Validée par la suite automatisée complète et par un smoke test manuel réel dans l'application.

---

## v0.2-mission015 — 2026-08-14

### Résumé (Mission 015)

**Mission 015 — Enlarged Image Preview.** Introduction d'un composant Qt partagé, `ImagePreviewDialog` (`src/ui/dialogs/`), permettant de consulter une image en grand depuis deux consommateurs réels : `ImagesPage` (double-clic ou bouton "Voir en grand" sur une image de `Workspace.images`) et `InferencePage` (bouton "Voir en grand" sur le résultat pending introduit par Mission 014, avant toute décision Accept/Reject/Regenerate). Le dialogue est strictement passif : son constructeur ne reçoit qu'un `file_path` (`str`), jamais de référence Domain/Manager/Page, ce qui garantit structurellement qu'il ne peut jamais modifier `Workspace.images`, un état pending, ni déclencher `WORKSPACE_SAVED`. Redimensionnement dynamique avec conservation du ratio (`QPixmap.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`), plein écran par bouton et raccourci `F11` (même callback). Aucune nouvelle dépendance, aucun nouveau Domain/Manager/événement EventBus. La galerie/miniatures `ImagesPage` reste explicitement différée.

### Statistiques (Mission 015)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`52c1005`) |
| Nouveaux fichiers | `dialogs/__init__.py`, `image_preview_dialog.py`, `test_image_preview_dialog.py`, `test_images_page.py` |
| Fichiers modifiés | `images_page.py`, `inference_page.py`, `test_inference_page.py` |
| Tests ajoutés | 31 (13 + 11 + 7) |
| Total tests du projet | 190/190 verts (159 précédents + 31 nouveaux) |

### Évolutions architecturales (Mission 015)

- **`ImagePreviewDialog`** (`src/ui/dialogs/image_preview_dialog.py`, nouveau sous-package `src/ui/dialogs/`) — `QPixmap` chargé une seule fois au constructeur, jamais rechargé depuis le disque ; fichier absent/illisible géré par un message texte explicite, sans exception.
- **`ImagesPage`** — double-clic et bouton "Voir en grand" convergent vers la même méthode interne `_open_preview(file_path)` ; bouton activé/désactivé selon la sélection courante ; `update_images()` mis en conformité avec le pattern `blockSignals(True)/clear()/reconstruction/blockSignals(False)`.
- **`InferencePage`** — bouton "Voir en grand" branché sur le point d'activation déjà existant `_set_validation_buttons_enabled()`, actif uniquement en état PENDING (state machine Mission 014 strictement inchangée).
- Dialogue modal (`exec()`) : aucune action Accept/Reject/Regenerate/Generate n'est possible pendant la consultation.

### Décisions de conception (Mission 015)

- Composant strictement passif (aucune référence Domain/Manager/Page) — la garantie de non-mutation vient de la conception, pas d'un garde-fou ajouté après coup.
- Aucune nouvelle dépendance (`Pillow`/`opencv-python`, présents dans `requirements.txt` mais jamais utilisés dans `src/ui/`, ne sont pas sollicités).
- Galerie/miniatures `ImagesPage` et visualiseur système Windows délibérément non traités par cette mission.

### Correction en revue finale (Mission 015)

Une revue technique dédiée, effectuée avant clôture et fondée sur une investigation empirique (widgets Qt réels), a identifié que `QLabel.minimumSizeHint()` se calait automatiquement sur le dernier pixmap affiché : `_update_scaled_pixmap()` réassignant un pixmap redimensionné à chaque `resizeEvent`/`showEvent`, la taille minimale de la fenêtre remontait silencieusement à chaque agrandissement, empêchant tout rétrécissement ultérieur. Corrigée avant clôture par `self.image_label.setMinimumSize(1, 1)`, qui découple la contrainte de layout du pixmap courant. Un test de régression dédié a été ajouté (`test_window_can_shrink_back_after_displaying_a_large_scaled_image`), revalidé pendant le smoke test réel par un cycle manuel agrandissement → fort rétrécissement → réagrandissement.

### Hors périmètre (Mission 015)

Galerie/miniatures `ImagesPage`, visualiseur système Windows, multi-sélection `ImagesPage`, images de référence `InferencePage`, sélection multi-engine/backend, suppression/édition/renommage d'image, métadonnées d'image, annulation d'une génération en cours, historique de générations. Nouveau besoin identifié par l'usage réel de cette mission : absence de création directe de dossier lors de "Nouveau projet" (résolu depuis par Mission 016).

### Tests ajoutés (Mission 015)

`tests/integration/test_image_preview_dialog.py` (13 tests, nouveau) : image paysage/portrait valides, fichier absent, fichier invalide, redimensionnement réel avec ratio conservé, régression du bug de rétrécissement, fenêtre très petite, ouvertures/fermetures multiples, plein écran par bouton et par `F11`, fermeture directement depuis le plein écran. `tests/integration/test_images_page.py` (11 tests, nouveau) : bouton désactivé/activé selon sélection, bouton et double-clic ouvrent le même fichier, fichier absent sans mutation du Domain, consultation sans `add_images()`/`save()`, refresh réinitialisant correctement la sélection et le bouton. `tests/integration/test_inference_page.py` (30 → 37, 7 nouveaux) : bouton "Voir en grand" suivant strictement la state machine Mission 014, aucune persistance déclenchée par la simple consultation. Suite entièrement mockée, aucun accès réseau réel, aucune instance ComfyUI, aucun GPU.

Smoke test réel complet réalisé depuis l'application réelle (`src/core/main.py`), couvrant les deux consommateurs (trois images réelles dans `ImagesPage`, une génération ComfyUI réelle dans `InferencePage`), le cas du fichier absent, et une fermeture propre — aucune divergence relevée entre comportement automatisé et comportement réel observé.

### Prochaines étapes (Mission 015)

Sans engagement définitif — Mission 016 à définir selon son propre audit architectural. Nouveau besoin identifié par l'usage réel : création directe de dossier lors de "Nouveau projet" (traité depuis par Mission 016). Dettes déjà connues avant cette mission inchangées (voir Mission 014 et précédentes).

### État du projet (Mission 015)

**Mission 015 est terminée.** `ImagePreviewDialog` introduit un visualiseur d'image agrandi partagé, strictement passif, entre `ImagesPage` et `InferencePage`. 190 tests d'intégration, smoke test réel complet validé.

---

## v0.2-mission014 — 2026-08-13

### Résumé (Mission 014)

**Mission 014 — Validation post-génération avant enregistrement.** Introduction d'une étape de validation explicite entre génération et persistance dans `InferencePage` : `Generate → résultat temporaire (pending) → Preview → Accept/Reject/Regenerate`. Avant cette mission, une génération réussie était automatiquement ajoutée à `Workspace.images` dès que `GenerationWorker` émettait `finished(path)` (Mission 013) ; désormais, seule l'action explicite Accept transforme un résultat temporaire en `Image` persistée. État pending (`_pending_path`, `_pending_pixmap`) porté exclusivement par `InferencePage`, jamais partagé. Aucun nouveau Domain/Manager, `GenerationManager`/`GenerationWorker`/`ComfyUIEngine` strictement inchangés.

### Statistiques (Mission 014)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`5828c35`) |
| Nouveaux fichiers | aucun |
| Fichiers modifiés | `inference_page.py` (state machine complète), `main_window.py` (abonnement `reset_for_workspace_change`) |
| Tests ajoutés | 21 (`test_inference_page.py` : 9 → 30) |
| Total tests du projet | 159/159 verts (138 précédents + 21 nouveaux) |

### Évolutions architecturales (Mission 014)

- **State machine `InferencePage`** : INITIAL → GENERATING → PENDING → ACCEPT/REJECT/REGENERATE/ERROR, avec états dédiés pour un changement de Workspace pendant PENDING ou GENERATING, et pour le shutdown.
- **`_generation_workspace_root`** — nouvel état transitoire mémorisant le Workspace actif au lancement du cycle de génération, utilisé pour la protection contre l'enregistrement croisé entre Workspaces (voir "Correction en revue finale").
- **Aperçu** : `QLabel`/`QPixmap.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`, recalculé dans `resizeEvent`, aucune nouvelle dépendance.
- **`InferencePage.reset_for_workspace_change()`** — abonnée par `main_window.py` à `WORKSPACE_CREATED`/`WORKSPACE_OPENED`/`WORKSPACE_CLOSED` (jamais `WORKSPACE_SAVED`), invalide immédiatement un pending existant dès que le contexte change.

### Décisions de conception (Mission 014)

- Aucun nouveau Domain (`GenerationResult`/`PendingImage`) — un scalaire (chemin) et une référence (racine Workspace) suffisent, portés par de simples attributs d'instance.
- `FileNotFoundError` au nettoyage du fichier pending traitée comme un succès (l'état désiré est déjà atteint) ; `OSError` réelle affiche un avertissement, avec possibilité résiduelle de fichier orphelin non résolue davantage.
- `QPixmap` non chargeable pour l'aperçu n'invalide pas le pending — l'incapacité de Qt à décoder les octets ne prouve pas que le fichier généré soit invalide ; considérée hors périmètre une validation de contenu plus poussée.

### Correction en revue finale (Mission 014)

Une revue technique dédiée, effectuée avant clôture, a identifié que ni le passage en pending ni Accept ne vérifiaient que le Workspace actif correspondait à celui actif au lancement de la génération — `WorkspaceManager.create()`/`.open()` remplaçant `current_workspace` sans jamais appeler `close()`, un résultat né dans un Workspace A aurait pu être silencieusement enregistré dans un Workspace B ouvert entre-temps. Corrigée avant clôture par la mémorisation de la racine du Workspace au lancement (`_generation_workspace_root`), une vérification à l'arrivée du résultat et à Accept, et une invalidation proactive via `reset_for_workspace_change()`. Vérifiée par tests automatisés dédiés et par le scénario E du smoke test réel.

### Hors périmètre (Mission 014)

Limite shutdown sans annulation réelle pendant une génération active (déjà connue depuis Mission 013, non résolue). Possibilité résiduelle de fichier orphelin sur échec réel de suppression. Galerie `ImagesPage`, images de référence, sélection multi-engine (déjà identifiés en Mission 013, toujours non implémentés). Nouveau besoin identifié par l'usage réel de cette mission : aperçu agrandi/plein écran (résolu depuis par Mission 015).

### Tests ajoutés (Mission 014)

`tests/integration/test_inference_page.py` étendu (9 → 30 tests, 21 nouveaux) : preview sans persistance, Accept exactement une fois (spy sur `add_images`), Reject, Regenerate, changement de Workspace pendant pending et pendant génération en cours, fichier pending disparu avant Accept, erreurs de suppression filesystem, shutdown avec pending, races `QThread` de Mission 013 toujours protégées. Suite entièrement mockée. Smoke test réel complet réalisé depuis l'application réelle, six scénarios (A à F : Accept, Reject, Regenerate, persistance/reload, changement de Workspace A→B avec pending, fermeture avec pending terminé), deux Workspaces de test dédiés, aucune divergence relevée.

### Prochaines étapes (Mission 014)

Sans engagement définitif — Mission 015 à définir selon son propre audit architectural, devant tenir compte du nouveau besoin d'aperçu agrandi/plein écran identifié par l'usage réel de cette mission (traité depuis par Mission 015).

### État du projet (Mission 014)

**Mission 014 est terminée.** `InferencePage` introduit une étape de validation explicite entre génération et persistance, avec protection structurelle contre tout enregistrement croisé entre Workspaces — défaut réel trouvé en revue technique finale et corrigé avant clôture. 159 tests d'intégration, smoke test réel complet validé (six scénarios).

---

## v0.2-mission013 — 2026-08-13

### Résumé (Mission 013)

**Mission 013 — Verticale minimale Inference.** Livraison de la première verticale fonctionnelle réelle d'AI Studio Toolkit : un utilisateur saisit un prompt dans `InferencePage`, clique sur "Générer", obtient une image réelle sans bloquer l'interface, et la retrouve dans `Workspace.images`/`ImagesPage`. Premier consommateur réel de `ComfyUIEngine` (Mission 012), via `GenerationManager` (Qt-free) et `GenerationWorker` (`QObject` déplacé dans un `QThread`, premier threading Qt du projet).

### Statistiques (Mission 013)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`78c6937`) |
| Nouveaux fichiers | `generation_manager.py`, `generation_worker.py`, `test_generation_manager.py`, `test_generation_worker.py`, `test_inference_page.py` |
| Fichiers modifiés | `comfyui_engine.py` (paramètre additif `checkpoint_name`), `main_window.py` (composition root), `inference_page.py`, `test_comfyui_engine.py` |
| Tests ajoutés | 25 (10 + 4 + 9 nouveaux fichiers + 2 adaptations `test_comfyui_engine.py`) |
| Total tests du projet | 138/138 verts (113 précédents + 25 nouveaux) |

### Évolutions architecturales (Mission 013)

- **`GenerationManager`** (`src/managers/generation_manager.py`) — Manager minimal sans collection Domain ni `active_id`, un unique flag transitoire `_busy` ; strictement Qt-free (vérifié par test) ; normalise `ComfyUIEngineError`/`OSError` en `GenerationError`.
- **`GenerationWorker`** (`src/ui/generation_worker.py`) — unique classe connaissant à la fois Qt et `GenerationManager`, idiome "Worker Object" standard (`moveToThread()`), signaux `finished(str)`/`failed(str)`.
- **`InferencePage`** devient fonctionnelle : validation minimale, bouton désactivé pendant la génération, `output_directory` recalculé depuis `workspace.root / "outputs"`. `WorkspaceManager.add_images()` appelé depuis le thread principal uniquement.
- **`main_window.py`** — composition root instanciant `ComfyUIEngine`/`GenerationManager`, avec deux constantes explicitement documentées comme propres à la machine de développement (`COMFYUI_BASE_URL`, `COMFYUI_CHECKPOINT_NAME`).
- **`ComfyUIEngine`** étendu de façon additive : `generate_image()` gagne un paramètre optionnel `checkpoint_name` — les trois primitives génériques restent strictement inchangées.

### Décisions de conception (Mission 013)

- Ownership de l'image générée : `Workspace.images`, via `WorkspaceManager.add_images()` déjà existant — aucune ligne de persistance nouvelle, modèle d'ownership Mission 011 non modifié.
- `Workspace`/`WorkspaceManager` jugés non thread-safe : toute mutation reste exécutée depuis le thread principal, jamais depuis le worker.
- Limite acceptée : shutdown sans annulation réelle (`thread.quit()+wait()` ne peut interrompre un appel réseau déjà en cours).

### Correction en revue finale (Mission 013)

Une revue technique dédiée a identifié une condition de course réelle : `worker.finished`/`worker.failed` réactivaient le bouton avant que `thread.finished → _cleanup_thread()` ne s'exécute, et `_cleanup_thread()` relisait `self._worker`/`self._thread` au moment de son exécution différée — un ancien cleanup pouvait détruire les références d'un nouveau cycle relancé entretemps. Corrigée avant clôture : `worker`/`thread` capturés par valeur dans le callback `thread.finished`, remise à `None` conditionnée à l'identité du cycle. 4 tests ajoutés, dont deux avec de vrais `QThread` et reclic immédiat, capturant tout message Qt anormal.

### Hors périmètre (Mission 013)

Limite shutdown sans annulation réelle. `ApplicationSettings.comfyui_url` toujours différé. Historique de générations, annulation, générations simultanées, sélection Dataset comme pool alternatif — non traités. Trois besoins futurs identifiés par l'usage réel : galerie/miniatures `ImagesPage`, images de référence `InferencePage`, sélection multi-engine/backend — explicitement non implémentés, non architecturés.

### Tests ajoutés (Mission 013)

`test_generation_manager.py` (10, pur Python, `ComfyUIEngine` mocké), `test_generation_worker.py` (4, `QThread` réel, `GenerationManager` mocké), `test_inference_page.py` (9, widgets Qt réels, `GenerationManager` mocké), `test_comfyui_engine.py` étendu (23 → 25) pour la nouvelle paramétrisation `checkpoint_name`. Suite entièrement mockée, aucun accès réseau réel.

Smoke test réel complet réalisé depuis l'application réelle (`src/core/main.py`), backend ComfyUI Desktop réel (`http://127.0.0.1:8000`), deux générations GPU réelles successives validées, UI responsive pendant la génération, persistance/reload vérifiée, aucune divergence relevée.

### Prochaines étapes (Mission 013)

Sans engagement définitif — Mission 014 à définir selon son propre audit architectural, devant tenir compte des trois besoins réels identifiés (galerie Images, images de référence Inference, sélection multi-engine).

### État du projet (Mission 013)

**Mission 013 est terminée.** Première verticale fonctionnelle réelle du projet : `InferencePage → GenerationManager → GenerationWorker/QThread → ComfyUIEngine → Workspace.images → ImagesPage`, validée par 138 tests automatisés et par un smoke test réel complet (deux générations GPU réussies). Une condition de course réelle a été trouvée et corrigée avant clôture.

---

## [v0.2-mission012](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission012) — 2026-08-13

### Résumé (Mission 012)

**Mission 012 — ComfyUI Engine minimal.** Introduction de la première infrastructure IA réelle du projet : `ComfyUIEngine` (`src/engines/comfyui_engine.py`), établissant un contrat technique validé entre AI Studio Toolkit et une instance serveur ComfyUI, sans introduire `Plugin`, `Service`, `AI Orchestrator`, `Job` ni UI d'exécution. Frontière retenue : `AI Studio Toolkit → ComfyUI`, jamais `→ un modèle/provider particulier` — le protocole HTTP de ComfyUI (`/prompt`, `/history`, `/view`) étant générique par construction. Trois primitives génériques (`submit`, `wait_for_result`, `download_output`) constituent le contrat réel ; `generate_image()` est une convenience method de démonstration composée strictement de ces primitives.

### Statistiques (Mission 012)

| Indicateur | Valeur |
|---|---|
| Commit | unique, regroupant code, tests et documentation (`1388f9d`) |
| Nouveaux fichiers | `engines/__init__.py`, `engines/comfyui_engine.py`, `test_comfyui_engine.py` |
| Fichiers modifiés | `docs/PROJECT_CONTEXT.md` |
| Tests ajoutés | 23 |
| Total tests du projet | 113/113 verts (90 précédents + 23 nouveaux) |

### Évolutions architecturales (Mission 012)

- **`ComfyUIEngine`** (couche Infrastructure) — `submit(workflow, client_id) -> prompt_id`, `wait_for_result(prompt_id, poll_interval) -> outputs`, `download_output(filename, subfolder, type_, output_directory) -> chemin local`. Aucune des trois ne connaît le contenu du workflow (checkpoint, LoRA, modèle, provider).
- **`generate_image()`** — convenience method de démonstration, composée strictement des trois primitives + `build_demo_workflow()` (fonction libre, hors classe).
- `ComfyUIEngine` n'importe rien de `src/domain/`, ne retourne que des `str`/`dict` — aucune image générée n'est ajoutée automatiquement à `Workspace.images`/`Dataset.images`.
- Protocole : `POST /prompt` → `GET /history/{prompt_id}` (polling, pas de WebSocket) → `GET /view`.

### Décisions de conception (Mission 012)

- ComfyUI local retenu comme premier moteur concret, décision explicite de l'architecte motivée par le besoin de sortir des abstractions hypothétiques (`Service`/`AI Orchestrator`/`Plugin`/`Engine`/`Job` génériques).
- Support architectural actuel limité à une instance serveur ComfyUI (locale ou distante) parlant le protocole `/prompt`/`/history`/`/view` — explicitement pas un client direct vers une éventuelle API Comfy Cloud hébergée (endpoints/authentification propres, non implémentés).
- `checkpoint_name` isolé dans `build_demo_workflow()`, jamais une propriété de `ComfyUIEngine`.

### Correction en revue finale (Mission 012)

Une revue technique dédiée a identifié deux divergences réelles : `wait_for_result()` considérait comme terminé tout `outputs` non vide, sans vérifier qu'une image exploitable y figurait ; `_first_image_reference()` acceptait une référence sans `filename`. Corrigées avant clôture : le polling continue jusqu'à l'apparition d'une référence image structurellement exploitable ou l'expiration du timeout ; une référence sans `filename` non vide n'est plus retournée. 7 tests ajoutés pour couvrir précisément ces cas.

### Hors périmètre (Mission 012)

Câblage UI (`InferencePage`) et le problème de threading associé — différé (traité par Mission 013). `comfyui_url`/configurabilité de l'adresse serveur dans `ApplicationSettings` — non ajouté. Client direct vers une éventuelle API Comfy Cloud hébergée, credentials cloud, gestionnaire de providers, moteurs concurrents (`GPTImageEngine`, `NanoBananaEngine`, `FluxEngine`, `SDXLEngine`) — non implémentés.

### Tests ajoutés (Mission 012)

`tests/integration/test_comfyui_engine.py` (23 tests, entièrement mockés via `unittest.mock.patch` sur `urllib.request.urlopen`) : contrat `submit()`, `wait_for_result()`, `download_output()`, `generate_image()`, et 4 tests architecturaux dédiés (absence d'import Domain, absence de connaissance provider, isolation de `checkpoint_name`, séparation primitives/démonstration). Aucun accès réseau réel, aucune instance ComfyUI, aucun GPU dans la suite automatisée.

**Validation empirique post-clôture** : après le tag `v0.2-mission012` et la **publication de la GitHub Release**, un smoke test manuel a été réalisé contre une instance ComfyUI Desktop réellement démarrée (`http://127.0.0.1:8000`, GPU NVIDIA Quadro P4000) — séquence complète `submit()`/`wait_for_result()`/`download_output()` validée sans aucun mock, image PNG valide obtenue. Ce smoke test est resté manuel et ponctuel, hors dépôt, sans modification du code versionné.

### Prochaines étapes (Mission 012)

Sans engagement définitif — Mission 013 à définir selon son propre audit architectural, le point logique le plus probable étant le choix du premier consommateur du moteur (Manager et/ou UI).

### État du projet (Mission 012)

**Mission 012 est terminée.** Première infrastructure IA réelle du projet (`src/engines/`, `ComfyUIEngine`) introduite, sans Plugin/Service/AI Orchestrator/Job/UI d'exécution. 113 tests d'intégration, tous mockés pour cette nouvelle suite. Une génération ComfyUI réelle a depuis été validée empiriquement par un smoke test manuel post-clôture, hors dépôt.

---

## v0.2-mission011 — 2026-08-13

### Résumé (Mission 011)

**Mission 011 — Image Domain.** Introduction d'une représentation Domain minimale et cohérente des images existantes (`Image`, 2 champs : `image_id`, `file_path`), en remplacement des chaînes brutes (`list[str]`) dispersées entre `Workspace.images`, `Dataset.images` et un `Character.images` mort (supprimé par cette mission — jamais lu ni écrit par aucun Manager ni aucune Page depuis son introduction). Ownership retenu (Modèle D, contextuel et structurel) : `Workspace` et chaque `Dataset` possèdent chacun leur propre pool `list[Image]`, strictement indépendants, sans registre global ni référence croisée. Première migration du projet portant sur des données réellement présentes (`list[str]` → `list[Image]`), rétrocompatible, sans réécriture forcée au chargement.

*Note de clôture Git* : le tag `v0.2-mission011` ne cible pas directement le commit fonctionnel (`242453e`) mais le commit documentaire final de clôture (`c23283c`) — trois commits complémentaires (`26606e3`, `2634518`, `c23283c`) ont été nécessaires après le commit fonctionnel pour stabiliser les références documentaires, un piège d'auto-référence (documenter un hash pas encore créé) rencontré et résolu à cette occasion, à l'origine du principe de non-auto-référence désormais appliqué (`docs/PROJECT_CONTEXT.md`).

### Statistiques (Mission 011)

| Indicateur | Valeur |
|---|---|
| Commits | commit fonctionnel unique (`242453e`) + 3 commits documentaires de clôture (`26606e3`, `2634518`, `c23283c` — ce dernier ciblé par le tag) |
| Nouveaux fichiers | `domain/image.py`, `test_image_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `dataset.py`, `character.py`, `workspace_manager.py`, `dataset_manager.py`, `images_page.py`, `datasets_page.py`, `test_dataset_roundtrip.py`, `test_training_roundtrip.py` |
| Tests ajoutés | 10 |
| Total tests du projet | 90/90 verts (80 précédents + 10 nouveaux) |

### Évolutions architecturales (Mission 011)

- **`Image`** (`src/domain/image.py`) — dataclass Qt-indépendante, 2 champs (`image_id`, `file_path`), domaine passif.
- **`Character.images`** supprimé — relation `Character → Image` restant strictement transitive via `Character → Dataset → Image`.
- **`WorkspaceManager.add_images()`/`DatasetManager.add_images()`** adaptés pour construire des `Image` au lieu de chaînes brutes ; déduplication prospective continue de fonctionner par `file_path`.
- **Aucun `ImageManager`** introduit — `Image` n'a pas de cycle de vie CRUD autonome (pas de sélection, pas d'`active_id`), contrairement à `Model`/`Workflow`/`Settings`/`ApplicationSettings`.
- **`Image.list_from_data()`**, partagée entre `Workspace.from_dict()` et `Dataset.from_dict()`, gère la conversion `list[str]` legacy → `list[Image]` à la lecture uniquement.

### Décisions de conception (Mission 011)

- Modèle d'ownership retenu après audit dédié comparant quatre modèles (Workspace-owned seul, Character-owned seul, Dataset-owned seul, hybride contextuel) contre le comportement réel du code, pas seulement le Blueprint — seul modèle ne rompant aucun comportement fonctionnel déjà existant.
- Un `uuid4()` est généré pour chaque entrée `str` legacy convertie ; identifiant stable dès la première sauvegarde au nouveau format, non stable avant (comportement attendu, vérifié explicitement).
- Déduplication strictement prospective (nouveaux imports via `add_images()`), jamais rétroactive sur des données déjà migrées ; doublons historiques préservés comme instances `Image` distinctes.

### Correction en revue finale (Mission 011)

Une revue technique dédiée à `Image.list_from_data()`, effectuée avant commit, a révélé que la première implémentation acceptait silencieusement tout `dict`, sans vérifier la validité de `file_path` — `{}` aurait produit une `Image` avec `file_path=""`. Corrigée avant tout commit : une entrée `dict` n'est conservée que si `file_path` est un `str` non vide ; une entrée `str` legacy n'est conservée que si elle est non vide. Test de régression ajouté (`test_list_from_data_filters_dicts_without_usable_file_path`).

### Hors périmètre (Mission 011)

`BasePage` (code mort). Ambiguïté `Training` vs `Training History`. Incohérences documentaires `Job` dans le Blueprint. Support Linux/macOS non vérifié pour `ApplicationSettingsStorage`. `Generation`, exécution réelle de `Job`, `Service`, `Plugin`, `Engine`, `AI Orchestrator`. Suppression individuelle d'une `Image`. Tout traitement physique de fichier (copie, redimensionnement, thumbnailing).

### Tests ajoutés (Mission 011)

`tests/integration/test_image_roundtrip.py` (10 tests) : défauts/round-trip Domain, migration Workspace et Dataset, round-trip nouveau format avec conservation exacte des `image_id`, stabilité des identifiants après sauvegarde/réouverture réelle, déduplication prospective par `file_path`, indépendance prouvée des deux pools (même `file_path`, deux instances, deux `image_id`), suppression de `Character.images`, filtrage explicite des `dict` sans `file_path` exploitable.

### Prochaines étapes (Mission 011)

Sans engagement définitif — Mission 012 à définir selon la roadmap/Blueprint ; le prérequis architectural le plus probable pour une future mission Generation reste la chaîne `Service → AI Orchestrator → Plugin → Engine`, entièrement absente du code à ce jour.

### État du projet (Mission 011)

**Mission 011 est terminée.** `Image` devient la 11ᵉ entité Domain du projet, premier pattern d'ownership contextuel (deux pools indépendants d'un même type, sans registre partagé). Première migration du projet portant sur des données réellement présentes. 90 tests d'intégration.

---

## [v0.2-mission010](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission010) — 2026-08-12

### Résumé (Mission 010)

**Mission 010 — Application Settings Domain.** Introduction d'`ApplicationSettings`, objet Domain **Application-level** — un niveau de configuration distinct de `Workspace.settings` (Mission 009), jamais persisté dans `project.json`. Domain minimal : `python_path`, `comfyui_path`, `onetrainer_path`. Stockage dédié dans un fichier séparé, hors de tout Workspace :

```
Workspace                          Application
└── Settings                       └── ApplicationSettings
    ├── theme                          ├── python_path
    └── language                       ├── comfyui_path
         ↓                             └── onetrainer_path
     project.json                           ↓
                                     application_settings.json
```

Ces deux périmètres restent strictement indépendants : Managers, cycles de vie, persistances et canaux de rafraîchissement distincts, sans aucun couplage.

### Statistiques (Mission 010)

| Indicateur | Valeur |
|---|---|
| Commits | 5 |
| Nouveaux fichiers | `application_settings.py`, `application_settings_storage.py`, `application_settings_manager.py`, `test_application_settings_roundtrip.py` |
| Fichiers modifiés | `settings_page.py`, `main_window.py`, `test_settings_roundtrip.py` |
| Tests ajoutés | 13 |
| Total tests du projet | 80/80 verts (67 existants + 13 nouveaux) |

### Évolutions architecturales (Mission 010)

- **`ApplicationSettings`** (`src/domain/application_settings.py`) — dataclass Qt-indépendante, 3 champs, domaine passif.
- **`ApplicationSettingsStorage`** (`src/infrastructure/storage/application_settings_storage.py`) — répertoire résolu via `%LOCALAPPDATA%\AIStudioToolkit\` sous Windows (comportement Windows spécifiquement ; repli déterministe `Path.home()/AppData/Local/AIStudioToolkit` si `LOCALAPPDATA` est absent), fichier `application_settings.json`. Lecture non bloquante : fichier absent, vide, JSON invalide, racine non-`dict` ou erreur `OSError` → valeurs par défaut, jamais d'exception au démarrage. Écriture atomique (fichier temporaire dans le même répertoire, `flush()` + `os.fsync()`, puis `os.replace()`) : le dernier fichier valide est garanti intact si une sauvegarde échoue ; `ApplicationSettingsStorageError` levée dans ce cas.
- **`ApplicationSettingsManager`** (`src/managers/application_settings_manager.py`) — `settings` (lecture) et `update(python_path=None, comfyui_path=None, onetrainer_path=None)` (écriture idempotente, multi-champs en une seule sauvegarde). Stratégie "candidat d'abord" : le nouvel état est construit et persisté avec succès *avant* tout remplacement de l'état mémoire — un échec de sauvegarde laisse donc la mémoire strictement inchangée. Aucune dépendance à `WorkspaceManager`.
- **`SettingsPage`** — deux sections indépendantes (Workspace / Application), chacune avec son propre bouton "Enregistrer". La section Application reste disponible et activée en permanence, y compris sans aucun Workspace ouvert.
- **Événement `application_settings.updated`** — publié uniquement après une sauvegarde réussie ; aucun événement sur mise à jour idempotente ou échec.

### Décisions de conception (Mission 010)

- Séparation stricte des scopes : `python_path`/`comfyui_path`/`onetrainer_path` ne sont jamais écrits dans `project.json` ; `theme`/`language` ne sont jamais écrits dans `application_settings.json`.
- Aucune migration automatique depuis `Workspace.settings` — les deux stockages n'ont jamais été liés, aucune donnée à transférer.
- Résolution du répertoire de configuration en Python standard uniquement (`os`/`pathlib`) — aucune dépendance nouvelle, aucun import Qt dans Infrastructure/Managers.
- Aucun `settings_id` — singleton, même principe que `Settings`/`Workspace`.
- Un événement Workspace ne rafraîchit jamais la section Application, et réciproquement — vérifié dans les deux sens.

### Hors périmètre (Mission 010)

Non implémentés : validation d'existence des chemins, lancement réel de Python/ComfyUI/OneTrainer, clés API, secrets, chiffrement, `Job`, `Engine`, `Plugin`, `Service`, `AI Orchestrator`, `Image` Domain.

### Tests ajoutés (Mission 010)

`tests/integration/test_application_settings_roundtrip.py` (13 tests) : round-trip et défauts du Domain, résolution de `default_directory()` (`LOCALAPPDATA` simulé + repli), matrice de compatibilité de `load()`, round-trip Unicode réel, écriture atomique et préservation du dernier fichier valide en cas d'échec, chargement/idempotence/atomicité de `ApplicationSettingsManager`, cohérence mémoire/disque après échec de sauvegarde, persistance entre deux instances, indépendance totale vis-à-vis de `WorkspaceManager`, cycle de vie complet de la section Application dans `SettingsPage`, étanchéité bidirectionnelle entre les deux sections, absence de duplication d'abonnements. `tests/integration/test_settings_roundtrip.py` adapté à la marge (signature de `SettingsPage`, aucune nouvelle assertion).

### Prochaines étapes (Mission 010)

Sans engagement définitif — Mission 011 à définir selon la roadmap/Blueprint. Dettes restant indépendantes : `Job`/`Engine`/`Plugin`/`Service`/`AI Orchestrator`, migration `Image`, ambiguïté `Training`/`Training History`, références mortes `04_DATA_MODEL.md`/`05_CHARACTER_SYSTEM.md`, nettoyage de `BasePage`.

### État du projet (Mission 010)

**Mission 010 est terminée.** L'application dispose désormais de deux niveaux de préférences strictement séparés — Workspace Settings (`project.json`) et Application Settings (stockage local dédié) — et de 80 tests d'intégration.

---

## [v0.2-mission009](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission009) — 2026-08-12

### Résumé (Mission 009)

**Mission 009 — Settings Domain (Workspace).** Introduction de `Settings`, entité Domain Workspace-owned prenant la forme d'un **singleton** (`Workspace.settings: Settings`) plutôt que d'une collection — aucun identifiant, aucune sélection, aucun événement dédié. Domain minimal : `theme`, `language`. `Workspace.settings` (`dict` non typé depuis Mission 001) est converti vers ce type avec une compatibilité défensive stricte par garde de type, et `SettingsPage` devient une page réelle, remplaçant les trois champs de configuration machine-locale (`python_path`, `comfyui_path`, `onetrainer_path`) — actés comme relevant d'un futur niveau Application Settings, distinct du Workspace.

Le travail a été mené en 6 commits atomiques. Le premier comble une dette de couverture de tests identifiée lors de l'audit d'ouverture de mission (suppression d'un Character possédant Dataset et Training associés) — le comportement existant s'est révélé correct, aucun changement de `CharacterManager` n'a été nécessaire.

### Statistiques (Mission 009)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `settings.py`, `settings_manager.py`, `test_settings_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `settings_page.py`, `main_window.py`, `test_character_roundtrip.py` |
| Tests ajoutés | 10 (1 régression Character/Dataset/Training + 9 Settings) |
| Total tests du projet | 67/67 verts (57 existants + 10 nouveaux) |

### Évolutions architecturales (Mission 009)

- **`Settings`** (`src/domain/settings.py`) — dataclass Qt-indépendante, 2 champs (`theme`, `language`), domaine passif.
- **`Workspace.settings: Settings`** — remplace le `dict` non typé. Désérialisation par garde de type explicite (`isinstance(..., dict)`) plutôt que par simple vérité (`or {}`), afin de rejeter aussi les valeurs truthy mal typées (`42`, `"abc"`, `[...]`), pas seulement les valeurs falsy.
- **`SettingsManager`** (`src/managers/settings_manager.py`) — `settings` (lecture) et `update(theme=None, language=None)` (écriture idempotente, multi-champs en une seule sauvegarde). Aucune dépendance à `EventBus` : ce Manager ne publie ni ne s'abonne à rien.
- **`SettingsPage`** — page réelle : `theme`/`language`, bouton "Enregistrer" explicite, désactivée sans Workspace, texte explicatif indiquant que ces préférences ne sont pas encore appliquées à l'interface.

### Décisions de conception (Mission 009)

- Ownership Workspace-owned, singleton — pas de `settings_id` (même principe que `Workspace` lui-même, qui n'a pas de `workspace_id`).
- `python_path`/`comfyui_path`/`onetrainer_path` jugés Application-level (chemins propres à la machine), jamais Workspace-level — retirés de `SettingsPage`, non migrés, aucun fichier Application Settings créé.
- Clés inconnues sous `settings` (y compris les trois anciennes clés machine-locale) silencieusement ignorées, jamais conservées — décision consciente du passage à un schéma typé, pas un bug de sérialisation.
- Aucun événement Settings dédié : `SettingsManager.update()` → `WorkspaceManager.save()` → `WORKSPACE_SAVED`, seul canal de notification de `SettingsPage`.
- Sauvegarde exclusivement par bouton explicite ; une saisie non enregistrée est silencieusement abandonnée au changement de Workspace, sans dialogue de confirmation.

### Hors périmètre (Mission 009)

Non implémentés, différés : Application Settings, Character/Engine/Plugin/Cloud Settings, application réelle du thème à Qt, localisation réelle de l'interface, événements `SettingChanged`/`SettingReset`/`SettingImported`/`SettingExported`.

### Tests ajoutés (Mission 009)

`tests/integration/test_character_roundtrip.py` (+1) : suppression d'un Character avec Dataset référencé par un Training — aucune donnée orpheline, aucune exception. `tests/integration/test_settings_roundtrip.py` (9) : round-trip et défauts du Domain `Settings`, compatibilité historique complète de `Workspace.settings` (absent/`{}`/`null`/mauvais type/clés inconnues), idempotence et atomicité multi-champs de `SettingsManager.update()`, persistance réelle fermeture/réouverture, isolation stricte entre deux Workspaces, non-mutation des autres collections, cycle de vie complet de `SettingsPage`, absence de duplication d'abonnements.

### Prochaines étapes (Mission 009)

Sans engagement définitif — Mission 010 à définir selon la roadmap/Blueprint. Dettes restant indépendantes, non transformées en feuille de route : migration `Image` vers un vrai Domain object, ambiguïté `Training`/`Training History`, références mortes `04_DATA_MODEL.md`/`05_CHARACTER_SYSTEM.md`, nettoyage de `BasePage`.

### État du projet (Mission 009)

**Mission 009 est terminée.** L'application dispose désormais de `Settings`, entité Domain Workspace-owned sous forme de singleton, avec persistance et restauration réelles des préférences de Workspace, et 67 tests d'intégration.

---

## [v0.2-mission008](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission008) — 2026-08-11

### Résumé (Mission 008)

**Mission 008 — Training Domain.** La Mission 008 introduit `Training` comme nouvelle entité Domain Character-owned. Elle rejoint `Dataset`, `LoRA` et `Prompt` parmi les entités possédées par `Character` (`Character.trainings: list[Training]`). L'ownership retenu s'appuie sur `04_DOMAIN_MODEL.md` §4, qui place explicitement `Trainings` sous `Characters` dans la hiérarchie d'entités ; les arbres structurels de `00_VISION.md`, `01_PRODUCT_REQUIREMENTS.md` et `02_ARCHITECTURE.md` ne nomment à cet emplacement que `Training History` — un concept distinct, non implémenté par cette mission — jamais `Training` elle-même. Cette divergence documentaire est signalée, non résolue.

`Training` introduit également le premier mécanisme d'intégrité référentielle inter-entités du projet : un Dataset du personnage actif référencé par au moins un Training ne peut pas être supprimé tant que cette référence existe.

Le travail a été mené en 6 commits fonctionnels atomiques, chacun avec rapport d'impact validé avant exécution.

### Statistiques (Mission 008)

| Indicateur | Valeur |
|---|---|
| Commits fonctionnels | 6 |
| Nouveaux fichiers | `training.py`, `training_manager.py`, `training_page.py`, `test_training_roundtrip.py` |
| Fichiers modifiés | `character.py`, `dataset_manager.py`, `datasets_page.py`, `main_window.py` |
| Tests Training ajoutés | 11 (`test_training_roundtrip.py`) |
| Total tests du projet | 57/57 verts (46 existants + 11 nouveaux) |

### Évolutions architecturales (Mission 008)

- **`Training`** (`src/domain/training.py`) — dataclass Qt-indépendante, 3 champs (`training_id`, `name`, `dataset_id`), domaine passif. Aucun `character_id` stocké — l'appartenance est implicite via `Character.trainings`, même principe que `Dataset`/`LoRA`/`Prompt`. `dataset_id` est en revanche une vraie référence inter-entités, matérialisée en champ.
- **`Character.trainings`** — nouveau champ `list[Training]`, filtrage défensif `isinstance(t, dict)` à la désérialisation (compatibilité, pas migration — le champ n'a jamais existé sous aucune forme antérieure).
- **`TrainingManager`** (`src/managers/training_manager.py`) — `create(name, dataset_id)`, `select(training_id)`, `delete(training_id)`, `list_trainings()`, `active_training_id` (runtime-only, non persisté, réinitialisé sur changement de personnage et de workspace — pattern Character-owned identique à `Dataset`/`Prompt`). La validation de `dataset_id` est strictement limitée à `active_character.datasets` : un Dataset existant mais appartenant à un autre personnage est refusé. Aucune méthode `update_*()` — Training n'a pas de champ éditable en place.
- **Événements réellement publiés** : `training.created`, `training.selected`, `training.deleted`. Aucun autre événement Training n'existe dans le code.
- **Intégrité référentielle Dataset → Training** (`DatasetManager.is_referenced_by_training()` + garde dans `DatasetManager.delete()`) — un Dataset du personnage actif référencé par au moins un Training ne peut pas être supprimé tant que cette référence existe : pas de cascade, aucun Training supprimé automatiquement, aucun `dataset_id` réécrit. Le Dataset redevient supprimable une fois tous les Trainings qui le référencent supprimés. `DatasetsPage.delete_dataset()` effectue un contrôle préalable pour afficher un message explicite ; `DatasetManager.delete()` réapplique la même règle indépendamment de l'UI (défense en profondeur).
- **`TrainingPage`** — interface CRUD de définition de sessions d'entraînement : lister, créer (avec sélection du Dataset source via `QInputDialog`, noms de Dataset dupliqués désambiguïsés par un fragment de `dataset_id`), sélectionner, supprimer, afficher le Dataset associé. Une référence historique vers un Dataset supprimé s'affiche comme `"Dataset introuvable [dataset_id]"`, sans lever d'exception. Aucun bouton de lancement, aucune console — ce n'est pas un moteur d'entraînement.

### Décisions de conception (Mission 008)

- Ownership Character-owned retenu avec un niveau de preuve Blueprint plus nuancé que pour `Model`/`Workflow` (voir Résumé) — décision documentée, pas présentée comme une certitude absolue.
- Aucun `character_id` sur `Training` — ownership implicite par containment, cohérent avec `Dataset`/`LoRA`/`Prompt`.
- Aucune suppression en cascade lorsqu'un Dataset référencé est visé par une suppression — le refus est la seule réponse, jamais une correction automatique des données.
- `TrainingPage` est la première Page du projet dépendante de deux Managers en lecture (`training_manager` pour les mutations, `dataset_manager` en lecture seule pour peupler le sélecteur) — orchestration au niveau Presentation, aucune dépendance Manager-à-Manager introduite.
- Suppression volontaire du bouton "Lancer l'entraînement" et de la console placeholder hérités du prototype initial, pour que l'interface ne suggère aucune capacité d'exécution non implémentée.

### Hors périmètre (Mission 008)

Non implémentés, différés : `Training Engine`, `Job`, lancement réel d'un entraînement, pause/reprise/annulation, progression, loss, logs d'exécution, `Output LoRA`, `Base Model`, epochs, learning rate, optimizer, batch size, résolution, événements `TrainingStarted`/`TrainingPaused`/`TrainingResumed`/`TrainingFinished`/`TrainingCancelled`/`TrainingFailed`. Aucun de ces éléments n'existe dans le code livré par cette mission.

### Tests ajoutés (Mission 008)

`tests/integration/test_training_roundtrip.py` (11 tests) : round-trip et valeurs par défaut du Domain `Training`, compatibilité de `Character.trainings` (clé absente/`[]`/`None`/liste mixte), création valide et persistance réelle, refus d'un `dataset_id` vide ou inexistant et d'un Dataset appartenant à un autre personnage (atomicité complète : aucune mutation, aucun `save()`, aucun événement), réinitialisation du contexte au changement de personnage/workspace, suppression active/non-active/invalide avec persistance, cycle complet d'intégrité référentielle Dataset → Training (blocage, absence de cascade, déblocage), isolation des autres collections (y compris du Dataset référencé lui-même), reconstruction de `TrainingPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact Dashboard/Images.

### Prochaines étapes (Mission 008)

Sans engagement définitif :

- Mission 009 — à définir selon la roadmap/Blueprint.
- *(Dette documentaire Blueprint constatée pendant l'audit d'ouverture de mission, indépendante du Domain Training : `01_PRODUCT_REQUIREMENTS.md` référence `04_DATA_MODEL.md` et `05_CHARACTER_SYSTEM.md`, deux fichiers absents de `docs/blueprint/`. Correction laissée à une décision documentaire séparée.)*

### État du projet (Mission 008)

**Mission 008 est terminée.** L'application dispose désormais de `Training` comme nouvelle entité Domain Character-owned, aux côtés de `Dataset`, `LoRA` et `Prompt`, avec une première intégrité référentielle inter-entités (Dataset → Training), et 57 tests d'intégration.

---

## [v0.2-mission007](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission007) — 2026-08-11

### Résumé (Mission 007)

**Mission 007 — Workflow Domain.** Introduction de l'entité `Workflow`, sixième objet du Domain Model et deuxième ressource explicitement Workspace-owned après `Model` (`Workspace.workflows`), conformément à l'architecture "Workflow Library" retenue pour cette mission (`04_DOMAIN_MODEL.md` §14, `02_ARCHITECTURE.md` §6/§10/§12). Domain minimal : `workflow_id`, `name`, `file_path`. `file_path` est un choix d'implémentation propre à cette mission — le Blueprint ne nomme aucun attribut de type chemin pour `Workflow` (contrairement à `Model`, dont `file_path` traduit directement l'attribut "Installation Path") ; il permet uniquement de référencer un fichier externe, sans parsing, validation, détection d'origine ni exécution de son contenu.

Le travail a été mené en 5 commits atomiques, chacun avec rapport d'impact validé avant exécution. *(Le commit `cb60856`, situé chronologiquement entre la clôture de la Mission 006 et l'ouverture de cette mission, est une correction documentaire post-publication relative à la Mission 006 — il n'appartient pas à la Mission 007.)*

### Statistiques (Mission 007)

| Indicateur | Valeur |
|---|---|
| Commits | 5 |
| Nouveaux fichiers | `workflow.py`, `workflow_manager.py`, `workflows_page.py`, `test_workflow_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 9 (8 habituels + 1 dédié à l'isolation des collections Workspace) |
| Total tests du projet | 46/46 verts (37 existants + 9 nouveaux) |

### Évolutions architecturales (Mission 007)

- **`Workflow`** (`src/domain/workflow.py`) — dataclass Qt-indépendant, 3 champs (`workflow_id`, `name`, `file_path`), domaine passif.
- **`Workspace.workflows`** — nouveau champ `list[Workflow]` ; aucune conversion de type (contrairement à `models`/`datasets`/`loras`/`prompts`), le champ n'ayant jamais existé sous aucune forme auparavant. Sérialisation en liste de dictionnaires (`to_dict()`), désérialisation avec filtrage défensif `isinstance(w, dict)` (compatibilité, pas migration). Un `project.json` antérieur à cette mission, sans clé `"workflows"`, se charge normalement et produit `workflows == []`.
- **`WorkflowManager`** (`src/managers/workflow_manager.py`) — CRUD (`create`, `select`, `delete`), sélection via `active_workflow_id` (runtime-only), `update_file_path()` strictement idempotent (chaîne vide acceptée comme valeur légitime). Persistance déléguée à `WorkspaceManager.save()`. **Aucune dépendance à `CharacterManager`**, deuxième Manager du projet dans ce cas après `ModelManager`.
- **Événements réellement publiés** : `workflow.created`, `workflow.selected`, `workflow.deleted`. `update_file_path()` ne publie aucun événement dédié — la mutation est suivie de `WorkspaceManager.save()`, qui émet `workspace.saved` (seul mécanisme notifiant l'UI de ce changement). Ni `workflow.updated`, ni `workflow.imported`, ni `workflow.executed` (évoqués par le Blueprint §14) ne sont implémentés.
- **`WorkflowsPage`** — nouvelle page (`workflows_page.py`), création/sélection/suppression, association d'un fichier via `QFileDialog` (filtre `Workflows (*.json)`), affichage en lecture seule de `file_path`. Fonctionne indépendamment de l'existence ou de la sélection d'un `Character` — vérifié par exécution.
- **Intégration Sidebar/MainWindow** — nouvelle entrée "Workflows" insérée immédiatement après "Models" (regroupement des deux ressources Workspace-owned), alignement Sidebar/`QStackedWidget` vérifié sur les 11 entrées.
- **Isolation Character** — vérifiée par preuve inversée par exécution : la création, sélection ou suppression d'un `Character` n'a strictement aucun effet sur `active_workflow_id`, `WorkflowsPage`, ni sur les collections `workspace.models`/`.datasets`/`.loras`/`.characters`.

### Décisions de conception (Mission 007)

- `file_path` : choix d'implémentation minimal de Mission 007 permettant l'association à un fichier externe. Non implémenté dans Mission 007 / différé pour toute notion de parsing, validation ou exécution du contenu référencé. Ce n'est pas la traduction d'un attribut Blueprint nommé.
- Les formats `ComfyUI Workflow`, `Forge Preset`, `Fooocus Preset` (`01_PRODUCT_REQUIREMENTS.md`, "Workflow Library", priorité P1) sont les cas d'usage ayant motivé le filtre `*.json` du sélecteur de fichier — cela ne constitue **pas** une prise en charge fonctionnelle de ces formats : le fichier n'est ni ouvert, ni analysé, ni exécuté.
- **Ownership des workflows** — Mission 007 implémente `Workflow` comme ressource appartenant au `Workspace` (`Workspace.workflows`), conformément à l'architecture de Workflow Library retenue pour cette mission. Une formulation de `01_PRODUCT_REQUIREMENTS.md` §11 indique qu'un Character stocke ses propres workflows ; cette divergence documentaire est identifiée et laissée à une clarification architecturale ultérieure. Aucun couplage `WorkflowManager` ↔ `CharacterManager` n'est introduit dans Mission 007.
- `create()` reste un miroir strict de `ModelManager`/`DatasetManager`/`LoRAManager`/`PromptManager` : aucune validation de nom côté Manager, aucune sélection automatique après création.
- Attributs Blueprint `Description`, `Compatible Engine`, `Inputs`, `Outputs`, `Parameters`, `Version`, `Category`, `Author`, `Thumbnail`, `Tags`, `Metadata` : non implémentés dans Mission 007 / différés — aucun engagement n'est pris sur leur forme future.

### Tests ajoutés (Mission 007)

`tests/integration/test_workflow_roundtrip.py` (9 tests) : round-trip et valeurs par défaut du Domain `Workflow` (y compris compatibilité historique explicite d'un `project.json` sans clé `"workflows"`), cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture avec persistance disque réelle, idempotence complète d'`update_file_path()`, suppression avec persistance, preuve inversée d'isolation Character, reconstruction de `WorkflowsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact Dashboard/Images, et un test dédié vérifiant qu'aucune opération `WorkflowManager` ne mute `workspace.models`/`.datasets`/`.loras`/`.characters`.

### Prochaines étapes (Mission 007)

Sans engagement définitif :

- Clarification future de la tension documentaire Workspace-owned / Character-owned identifiée dans `01_PRODUCT_REQUIREMENTS.md` §11.
- Mission 008 — à définir selon la roadmap/Blueprint.

### État du projet (Mission 007)

**Mission 007 est terminée.** L'application dispose désormais de six entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`, `Model`, `Workflow`), 46 tests d'intégration, et deux ressources Workspace-owned cohérentes (`Model`, `Workflow`).

---

## [v0.2-mission006](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission006) — 2026-08-11

### Résumé (Mission 006)

**Mission 006 — Model Domain.** Introduction de l'entité `Model`, cinquième objet du Domain Model après `Character`, `Dataset`, `LoRA` et `Prompt` — et la première rattachée exclusivement au `Workspace`, pas au `Character`. Cette conclusion a été démontrée par huit citations Blueprint indépendantes (`04_DOMAIN_MODEL.md` §4/§5/§10/§27/§28, `02_ARCHITECTURE.md` §10/§11/§12), toutes convergentes : *"Models belong to the Workspace Library."* Le Domain reste volontairement minimal (`model_id`, `name`, `file_path`), dans la continuité directe de `Dataset`/`Prompt`.

Conséquence architecturale majeure : `ModelManager` est le **premier Manager du projet sans dépendance à `CharacterManager`**. `active_model_id` ne se réinitialise que sur les événements de cycle de vie du workspace, jamais sur un changement de personnage — l'inverse exact de ce qui avait été vérifié pour `LoRAManager`/`PromptManager`, et démontré ici par une preuve comportementale par exécution dédiée.

Le travail a été mené en 6 commits atomiques, chacun avec rapport d'impact validé avant exécution.

### Statistiques (Mission 006)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `model.py`, `model_manager.py`, `test_model_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `models_page.py` (placeholder statique → page réelle), `main_window.py` |
| Tests d'intégration ajoutés | 8 (7 habituels + 1 dédié au round-trip et aux valeurs par défaut du Domain `Model`) |
| Total tests du projet | 37/37 verts (29 existants + 8 nouveaux) |

### Évolutions architecturales (Mission 006)

- **`Model`** (`src/domain/model.py`) — dataclass Qt-indépendant, 3 champs (`model_id`, `name`, `file_path`), domaine passif.
- **`Workspace.models`** — `list` (non typé, jamais peuplé) → `list[Model]` ; aucune preuve historique de migration nécessaire au sens strict (le champ n'avait jamais été typé, contrairement aux conversions `list[str]` précédentes), même principe de compatibilité défensive (`isinstance(m, dict)`).
- **`ModelManager`** (`src/managers/model_manager.py`) — CRUD, sélection, `update_file_path()` (miroir du contrat d'idempotence de `update_text()`) ; **aucune dépendance à `CharacterManager`**, `active_model_id` réinitialisé uniquement sur `WORKSPACE_CREATED`/`OPENED`/`CLOSED`.
- **`ModelsPage`** — remplace le placeholder à liste statique (`"Flux"`, `"SDXL"`...) ; sélection de fichier via `QFileDialog.getOpenFileName` (singulier) plutôt que le pattern d'import multi-fichiers ; fonctionne sans qu'aucun personnage n'existe.

### Décisions de conception (Mission 006)

- `Model` rattaché exclusivement au `Workspace`, jamais au `Character` — démontré par le Blueprint, pas supposé.
- `file_path` scalaire, pas une liste — nommage aligné sur la convention déjà en place dans le projet (`LoRA.files`, `lora_page.py`) pour désigner un chemin de fichier individuel.
- `create()` reste un miroir strict des trois Managers précédents : **aucune validation de nom** côté Manager, cette responsabilité reste exclusivement dans la Page — décision explicite pour ne pas introduire de divergence où `Model` deviendrait plus robuste que `Dataset`/`LoRA`/`Prompt`.
- Pas de sélection automatique après `create()` — comportement déjà existant pour les trois domaines précédents, reproduit à l'identique plutôt que "corrigé" à l'occasion de cette mission.
- Chaîne vide (`""`) traitée comme valeur légitime de `file_path` ("aucun fichier associé"), pas une erreur à valider.
- Hors périmètre, différé et non abandonné : scan automatique de fichiers, métadonnées du Domain (`provider`, `hash`, `architecture`, `thumbnail`...), `Character.favorite_models`.

### Tests ajoutés (Mission 006)

`tests/integration/test_model_roundtrip.py` (8 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_file_path()` (y compris la chaîne vide comme changement réel), suppression avec persistance, **preuve inversée** qu'un changement de personnage ne réinitialise jamais `active_model_id`, reconstruction de `ModelsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images, et un test dédié au round-trip `to_dict()`/`from_dict()` du Domain `Model` (valeurs par défaut, clé absente, filtrage défensif sur liste mixte).

### Prochaines étapes (Mission 006)

Sans engagement définitif :

- *(Correction post-publication, audit Mission 007 : la carte Dashboard "Models" ne nécessitait en réalité aucun correctif — sa lecture de `Workspace.models` était déjà correcte depuis la Mission 001 ; seule la donnée était vide avant cette mission. L'affirmation initiale ci-dessus était erronée.)*
- Poursuite du Domain Model : `Job`, `Engine`, `Plugin`, couche Services — périmètre exact à préciser dans son propre rapport d'impact.

### État du projet (Mission 006)

**Mission 006 est terminée.** L'application dispose désormais de cinq entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`, `Model`), 37 tests d'intégration, et un premier pattern architectural "ressource partagée au niveau Workspace" validé et documenté.

---

## [v0.2-mission005](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission005) — 2026-08-11

### Résumé (Mission 005)

**Mission 005 — Prompt Domain.** Introduction de l'entité `Prompt`, quatrième objet du Domain Model après `Character`, `Dataset` et `LoRA`, positionnée dans la hiérarchie `Character → Prompt Library` (`docs/blueprint/04_DOMAIN_MODEL.md` §13). Contrairement à l'extension volontaire de `LoRA` en Mission 004, le Domain `Prompt` revient à un périmètre strictement minimal (`prompt_id`, `name`, `text`), cohérent avec la discipline appliquée à `Character`/`Dataset`. Les catégories de prompts prévues par le Blueprint (`Master Prompt`, `Negative Prompt`, `Generation Prompt`, `Training Prompt`, `Template Prompt`, `Dynamic Prompt`...) sont **explicitement différées, non abandonnées** — décision d'architecture documentée directement dans le code (`src/domain/prompt.py`) : leur ajout n'aura de sens que le jour où un consommateur réel existera (pipeline de génération, entraînement, bibliothèque de prompts filtrable), et ne nécessitera aucune migration puisqu'il s'agirait d'un simple ajout de champ scalaire avec valeur par défaut.

Le travail a été mené en 7 commits atomiques, chacun avec rapport d'impact validé avant exécution. Comme pour les Missions 003/004, deux points sensibles ont fait l'objet d'une preuve comportementale par exécution plutôt que par seule lecture de code : l'indépendance de deux instances de `PromptManager` vis-à-vis de l'`EventBus`, et l'idempotence stricte du contrat `update_text()` (aucune sauvegarde ni événement publié lorsque le texte est inchangé).

### Statistiques (Mission 005)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `prompt.py`, `prompt_manager.py`, `prompts_page.py`, `test_prompt_roundtrip.py` |
| Fichiers modifiés | `dashboard_page.py`, `character.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 7 |
| Bug corrigé | Carte Dashboard "LoRA" lisait le champ vestigial `Workspace.loras` au lieu d'agréger `Character.loras` (même bug que "Datasets" en Mission 004, corrigé en ouverture de mission) |
| Total tests du projet | 29/29 verts (22 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 005)

- **`Prompt`** (`src/domain/prompt.py`) — dataclass Qt-indépendant, 3 champs (`prompt_id`, `name`, `text`), domaine passif.
- **`Character.prompts`** — `list[str]` → `list[Prompt]` ; migration prouvée inutile par recherche exhaustive de l'historique Git, même méthodologie que `Character.datasets`/`Character.loras`.
- **`PromptManager`** (`src/managers/prompt_manager.py`) — CRUD, sélection, `update_text()` en remplacement du pattern `add_images()`/`add_files()` (texte scalaire édité en place plutôt que liste accumulée), strictement idempotent.
- **`PromptsPage`** — nouvelle page (aucun placeholder à remplacer, contrairement à `Dataset`/`LoRA`) ; nouvelle entrée `sidebar.py` entre "LoRA" et "Training" ; lit exclusivement des dicts via `PromptManager.list_prompts()`.
- **`DashboardPage.lorasCard`** — corrigé en ouverture de mission : agrège désormais les `Character.loras` réels au lieu du champ vestigial `Workspace.loras`.

### Décisions de conception (Mission 005)

- Domain `Prompt` volontairement minimal — retour à la discipline `Dataset`/`Character` après l'exception justifiée de `LoRA`.
- Catégories/types de prompts (Blueprint §13) explicitement différées, pas abandonnées : documentées en commentaire dans `prompt.py`, seront réintroduites dès qu'un consommateur réel existera, sans rupture de compatibilité. Lors de cette réintroduction future, elles devront être implémentées comme une extension naturelle du Domain `Prompt` existant, sans remettre en cause le modèle minimal ni casser la compatibilité des données déjà persistées.
- `update_text()` remplace `add_images()`/`add_files()` : un texte s'édite en place, il ne s'accumule pas — aucune logique de déduplication n'a de sens ici.
- Filtrage défensif `isinstance(p, dict)` dans `Character.from_dict()` explicitement qualifié de **compatibilité défensive**, jamais de migration implicite — principe désormais posé comme référence pour toute future conversion `list[str] → list[Objet]` du projet.
- Correctif `lorasCard` traité en ouverture de mission, même pattern que `datasetsCard` en Mission 004.

### Tests ajoutés (Mission 005)

`tests/integration/test_prompt_roundtrip.py` (7 tests) : cycle complet création/sélection/édition/sauvegarde/fermeture/réouverture, idempotence d'`update_text()` (no-op sans sauvegarde ni événement, vérifié par espionnage direct de `WorkspaceManager.save()`), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `PromptsPage` sur les événements pertinents, absence de duplication d'abonnements, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 005)

Sans engagement définitif :

- Poursuite du Domain Model : `Model` — ressource partagée au niveau Workspace (`Workspace → Models → Characters`), un pattern architectural encore jamais implémenté dans ce projet, nécessitant sa propre conception avant toute implémentation.
- Réintroduction des catégories/types de `Prompt` dès qu'une fonctionnalité réelle le justifiera.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 005)

**Mission 005 est terminée.** L'application dispose désormais de quatre entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`, `Prompt`), 29 tests d'intégration.

---

## [v0.2-mission004](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission004) — 2026-08-10

### Résumé (Mission 004)

**Mission 004 — LoRA Domain.** Introduction de l'entité `LoRA`, troisième objet du Domain Model après `Character` et `Dataset`, positionnée dans la hiérarchie `Character → LoRAs` (`docs/blueprint/04_DOMAIN_MODEL.md`). Contrairement au minimalisme strict appliqué à `Dataset`, le Domain `LoRA` a été volontairement étendu dès sa conception (8 champs : `lora_id`, `name`, `files`, `thumbnail`, `engine`, `architecture`, `trigger_word`, `version`) — décision explicite pour éviter une migration future, compte tenu de la richesse intrinsèque d'un LoRA par rapport à un simple regroupement d'images. Comme `Dataset.images` en Mission 003, `LoRA.files` est fonctionnel dès son introduction.

Le travail a été mené en 7 commits atomiques, chacun avec rapport d'impact validé avant exécution. Deux points sensibles ont fait l'objet d'une preuve comportementale par exécution plutôt que par seule lecture de code : l'indépendance de deux instances de `LoRAManager` vis-à-vis de l'`EventBus`, et l'équivalence stricte du contrat `add_files()`/`DatasetManager.add_images()`.

### Statistiques (Mission 004)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `lora.py`, `lora_manager.py`, `test_lora_roundtrip.py` |
| Fichiers modifiés | `dashboard_page.py`, `character.py`, `main_window.py`, `lora_page.py` (placeholder → page réelle) |
| Tests d'intégration ajoutés | 7 |
| Bug corrigé | Carte Dashboard "Datasets" lisait le champ vestigial `Workspace.datasets` au lieu d'agréger `Character.datasets` (corrigé en ouverture de mission) |
| Total tests du projet | 22/22 verts (15 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 004)

- **`LoRA`** (`src/domain/lora.py`) — dataclass Qt-indépendant, 8 champs, domaine passif (aucune génération d'ID).
- **`Character.loras`** — `list[str]` → `list[LoRA]` (dépendance Domain→Domain, autorisée) ; migration de données prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle n'a jamais existé sous l'ancien format), même méthodologie que `Character.datasets` en Mission 003.
- **`LoRAManager`** (`src/managers/lora_manager.py`) — CRUD, sélection, `add_files()` avec déduplication et préservation de l'ordre ; `active_lora_id` runtime-only, réinitialisé au changement de personnage actif ou de workspace ; miroir exact de `DatasetManager`.
- **`LoRAPage`** — remplace le placeholder existant (qui incluait un bouton "Entraîner" hors périmètre, retiré) ; miroir strict de `DatasetsPage` ; lit exclusivement des dicts via `LoRAManager.list_loras()`.
- **`DashboardPage.datasetsCard`** — corrigé en ouverture de mission : agrège désormais les `Character.datasets` réels au lieu du champ vestigial `Workspace.datasets`.

### Décisions de conception (Mission 004)

- Domain `LoRA` volontairement plus riche que `Dataset` dès sa création — exception bornée et justifiée au minimalisme strict appliqué à `Character`/`Dataset`.
- `thumbnail` distinct de `files` : un aperçu n'est pas un fichier constitutif du LoRA — distinction reprise de CivitAI/ComfyUI/A1111/Forge, vocabulaire aligné sur celui du Blueprint pour `Model`/`Workflow`.
- `add_files()` reste générique vis-à-vis des types de fichiers (le Manager ne connaît aucune extension), à l'image d'`add_images()`.
- Correctif de la carte Dashboard "LoRA" (même bug que "Datasets", non encore corrigé) explicitement différé hors du Commit 5, pour préserver le découpage atomique de la mission — sera traité séparément si décidé.

### Tests ajoutés (Mission 004)

`tests/integration/test_lora_roundtrip.py` (7 tests) : cycle complet création/sélection/import/sauvegarde/fermeture/réouverture, préservation de l'ordre et déduplication des fichiers, réinitialisation de la sélection à la suppression de la LoRA active (avec persistance vérifiée), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `LoRAPage` sur les événements pertinents, absence de duplication d'abonnements entre deux instanciations, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 004)

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Poursuite du Domain Model : `Prompt` (déjà anticipé par `Character.prompts`, actuellement vide), ou `Model`.
- Correctif différé de la carte Dashboard "LoRA" (même nature que le correctif "Datasets" traité en Mission 004).
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, toujours différée.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 004)

**Mission 004 est terminée.** L'application dispose désormais de trois entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`, `LoRA`), 22 tests d'intégration, et une dette identifiée lors de l'audit de démarrage corrigée.

---

## [v0.2-mission003](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission003) — 2026-08-10

### Résumé (Mission 003)

**Mission 003 — Dataset Domain.** Introduction de l'entité `Dataset`, deuxième objet du Domain Model après `Character`, positionnée dans la hiérarchie `Character → Datasets` (`docs/blueprint/04_DOMAIN_MODEL.md` §7). Contrairement à `Character.images` en Mission 002, `Dataset.images` est fonctionnel dès cette mission : import d'images propre à chaque dataset, avec déduplication et préservation de l'ordre — un chemin d'import indépendant de `Workspace.images`/`ImagesPage`, sans migration requise.

Le travail a été mené en 7 commits atomiques, chacun accompagné d'un rapport d'impact validé avant exécution, avec un niveau de preuve comportementale renforcé par rapport aux missions précédentes (espionnage d'appels, vérification directe des abonnements `EventBus`, tests sur widgets Qt réels plutôt que sur les managers isolés).

### Statistiques (Mission 003)

| Indicateur | Valeur |
|---|---|
| Commits | 7 |
| Nouveaux fichiers | `dataset.py`, `dataset_manager.py`, `test_dataset_roundtrip.py` |
| Fichiers modifiés | `character.py`, `main_window.py`, `datasets_page.py` (placeholder → page réelle), `workspace_manager.py` |
| Tests d'intégration ajoutés | 7 |
| Dette technique corrigée | Import direct Presentation → Infrastructure (`WorkspaceStorageError` dans `MainWindow`) remplacé par `WorkspaceManagerError` |
| Total tests du projet | 15/15 verts (8 existants + 7 nouveaux) |

### Évolutions architecturales (Mission 003)

- **`Dataset`** (`src/domain/dataset.py`) — dataclass Qt-indépendant, 3 champs (`dataset_id`, `name`, `images`), domaine passif (aucune génération d'ID).
- **`Character.datasets`** — `list[str]` → `list[Dataset]` (dépendance Domain→Domain, autorisée) ; migration de données prouvée inutile par recherche exhaustive de l'historique Git (aucune donnée réelle n'a jamais existé sous l'ancien format).
- **`DatasetManager`** (`src/managers/dataset_manager.py`) — CRUD, sélection, `add_images()` fonctionnel avec déduplication et préservation de l'ordre ; `active_dataset_id` runtime-only, réinitialisé au changement de personnage actif ou de workspace.
- **`DatasetsPage`** — remplace le placeholder existant ; CRUD + import d'images à deux niveaux (liste des datasets avec compteur d'images, liste des images du dataset sélectionné) ; lit exclusivement des dicts via `DatasetManager.list_datasets()`, jamais des objets `Dataset` directement.
- **`WorkspaceManagerError`** — nouvelle exception publique portée par `WorkspaceManager`, remplace l'import direct de `WorkspaceStorageError` (Infrastructure) dans `MainWindow`, corrigeant une dette identifiée lors de l'audit de démarrage de mission.

### Décisions de conception (Mission 003)

- `Dataset.images` fonctionnel dès cette mission, contrairement à `Character.images` en Mission 002 — import propre à chaque dataset, sans dépendre d'une migration de `Workspace.images`.
- Ownership de `Dataset` implicite (pas de `character_id` stocké), même principe que `Character` vis-à-vis de `Workspace`.
- `add_images(paths)` opère sur le dataset actif implicitement, sans paramètre d'identifiant — même logique que `WorkspaceManager.add_images()`.
- Robustesse de désérialisation : `Character.from_dict()` filtre explicitement les entrées non-`dict` dans `datasets` plutôt que de laisser fuiter une `AttributeError`.
- Correctif de dette technique (`WorkspaceManagerError`) traité en ouverture de mission plutôt qu'en fin, pour établir le bon pattern avant que `DatasetManager` n'en ait besoin à son tour.

### Tests ajoutés (Mission 003)

`tests/integration/test_dataset_roundtrip.py` (7 tests) : cycle complet création/sélection/import/sauvegarde/fermeture/réouverture, préservation de l'ordre et déduplication des images, réinitialisation de la sélection à la suppression du dataset actif (avec persistance vérifiée), réinitialisation du contexte au changement de personnage et de workspace, reconstruction de `DatasetsPage` sur les événements pertinents (y compris `workspace.saved` après un import), absence de duplication d'abonnements entre deux instanciations, non-impact sur Dashboard/Images.

### Prochaines étapes (Mission 003)

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Poursuite du Domain Model : `LoRA`/`Prompt` (déjà anticipés par `Character.loras`/`Character.prompts`, actuellement vides), ou `Model`.
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, toujours différée.
- Reste : `Job`, `Engine`, `Plugin`, couche Services.

### État du projet (Mission 003)

**Mission 003 est terminée.** L'application dispose désormais de deux entités du Domain Model pleinement fonctionnelles (`Character`, `Dataset`), 15 tests d'intégration, et une dette technique identifiée lors de l'audit post-Mission-002 corrigée.

---

## [v0.2-mission002](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission002) — 2026-08-10

### Résumé (Mission 002)

**Mission 002 — Character Domain.** Introduction de l'entité `Character`, présentée par le Blueprint comme l'entité centrale du logiciel (`docs/blueprint/04_DOMAIN_MODEL.md` §6). Périmètre volontairement minimal : identité + listes de référence vides (`images`, `datasets`, `loras`, `prompts`, `history`), CRUD complet (créer/sélectionner/supprimer), persistance dans `project.json` via le mécanisme `WorkspaceManager` déjà existant — aucune nouvelle infrastructure de stockage. La migration des images de `Workspace` vers `Character` est explicitement différée à une mission future.

Le travail a été mené en 6 commits atomiques, chacun accompagné d'un rapport d'impact validé avant exécution — même discipline que la Mission 001.

### Statistiques (Mission 002)

| Indicateur | Valeur |
|---|---|
| Commits | 6 |
| Nouveaux fichiers | `character.py`, `character_manager.py`, `characters_page.py`, `test_character_roundtrip.py` |
| Fichiers modifiés | `workspace.py`, `sidebar.py`, `main_window.py` |
| Tests d'intégration ajoutés | 6 |
| Bugs applicatifs introduits | 0 (une erreur de comptage dans un test a été trouvée et corrigée **dans le test**, pas dans le code applicatif) |
| Nouvelle page Sidebar | Characters (9ᵉ page, positionnée juste après Dashboard) |

### Évolutions architecturales (Mission 002)

- **`Character`** (`src/domain/character.py`) — dataclass Qt-indépendant, 7 champs (`character_id`, `name`, `images`, `datasets`, `loras`, `prompts`, `history`), domaine passif (aucune génération d'ID).
- **`Workspace.characters`** — extension rétrocompatible, liste de vrais objets `Character` (dépendance Domain→Domain, autorisée), robuste à `"characters": null`.
- **`CharacterManager`** (`src/managers/character_manager.py`) — CRUD/sélection, persistance déléguée à `WorkspaceManager.save()`, publication d'événements (`character.created`/`selected`/`deleted`), abonnement à `WORKSPACE_CREATED`/`OPENED`/`CLOSED` pour réinitialiser `active_character_id` (runtime-only, jamais persisté) à chaque changement de workspace.
- **`CharactersPage`** — lit exclusivement des dicts via `CharacterManager.list_characters()`, jamais des objets `Character` (Presentation reste indépendante du Domain) ; protection `blockSignals()` contre les boucles d'événements Qt.
- **Dashboard/Images inchangés** — aucune carte "Characters" ajoutée, aucune migration de `ImagesPage` vers `Character.images` — choix explicites, différés à une mission future.

### Décisions de conception (Mission 002)

- Pas de migration d'images cette mission (`Workspace.images` reste la source utilisée par `ImagesPage`).
- `active_character_id` runtime-only, non persisté — même principe que `Workspace.root`.
- `favorite_models` retiré du périmètre — uniquement les 7 champs réellement nécessaires.
- `datasets`/`loras`/`prompts` sont des listes d'identifiants destinés à des objets futurs, pas des chemins de fichiers.
- Aucune carte Dashboard ajoutée.
- Génération de `character_id` dans `CharacterManager.create()`, jamais dans le dataclass `Character` — le Domain reste passif.
- Entrée Sidebar "Characters" positionnée juste après Dashboard, pas en fin de liste.

### Tests ajoutés (Mission 002)

`tests/integration/test_character_roundtrip.py` (6 tests) : cycle complet créer/sélectionner/sauvegarder/fermer/rouvrir, persistance de la suppression, non-réinitialisation d'`active_character_id` sur ouverture échouée, non-impact sur Dashboard/Images, reconstruction correcte de `CharactersPage` sur les événements Workspace, absence de duplication d'abonnements entre deux instanciations.

### Prochaines étapes

Sans engagement définitif — le périmètre exact de chaque mission future sera précisé dans son propre rapport d'impact avant toute implémentation :

- Piste envisagée pour la prochaine mission : le domaine `Dataset`, entité suivante de la hiérarchie `Character → Datasets` déjà anticipée par `Character.datasets` (liste vide, prête à recevoir des identifiants).
- Migration de `ImagesPage`/`Workspace.images` vers `Character.images`, différée depuis cette mission.
- Reste du Domain Model : `Model`, `LoRA`, `Job`, `Engine`, `Plugin`.

### État du projet (Mission 002)

**Mission 002 est terminée.** L'application dispose désormais d'une entité `Character` complète en CRUD, intégrée dans la navigation et couverte par des tests d'intégration.

---

## [v0.2-mission001](https://github.com/dominimada-wq/AI-Studio-Toolkit/releases/tag/v0.2-mission001) — 2026-08-10

### Résumé de la mission

**Mission 001 — Blueprint Refactoring.** Cette mission correspond au **Blueprint 02 (`docs/blueprint/02_ARCHITECTURE.md`)** : le prototype initial (gestion de "Project" ad hoc, logique métier dispersée dans l'UI, managers non utilisés) a été refactoré pour se conformer à l'architecture qui y est décrite, en cohérence avec les autres documents du Blueprint (`00_VISION.md` → `04_DOMAIN_MODEL.md`).

Cette mission n'a **ajouté aucune fonctionnalité nouvelle** : son unique objectif était de mettre le code existant en conformité avec les couches, les responsabilités et le sens de dépendance définis par le Blueprint (`Presentation → Managers → Services → Domain → Infrastructure → Engines`), tout en préservant le comportement observable de l'application.

Le travail a été mené en 9 commits atomiques, chacun revu, testé manuellement et validé avant exécution.

### Statistiques de la mission

| Indicateur | Valeur |
|---|---|
| Commits | 9 |
| Bugs corrigés | 3 |
| Tests d'intégration ajoutés | 2 |
| Packages morts supprimés | `src/config/`, `src/models/`, `src/widgets/`, `src/project/` |
| Architecture | Refactorisée (Presentation / Managers / Domain / Infrastructure / Core) |

### Évolutions architecturales principales

- **Introduction du Domain Layer** — `src/domain/workspace.py::Workspace`, un dataclass Qt-indépendant remplaçant l'ancienne dataclass `Project` (jamais utilisée) et reflétant fidèlement le schéma JSON réel. Le champ `root` (chemin du dossier) est explicitement runtime-only, jamais sérialisé, pour garder `project.json` portable.
- **Introduction de l'Infrastructure Layer** — `src/infrastructure/storage/workspace_storage.py::WorkspaceStorage`, portage durci de l'ancien `ProjectIO` : gestion d'erreurs typée (`WorkspaceStorageError`), journalisation, API dict-only (aucune dépendance vers le Domain, conformément au sens de dépendance du Blueprint).
- **Introduction de l'Application Layer** — `src/managers/workspace_manager.py::WorkspaceManager`, source unique de vérité pour le workspace courant, remplaçant l'ancien `ProjectManager` (jamais réellement instancié) et l'état dupliqué de `MainWindow`.
- **Introduction du Core / EventBus** — `src/core/event_bus.py::EventBus`, pub/sub minimal, Qt-indépendant, avec payloads réellement immuables (copie profonde + vue en lecture seule), permettant à la Presentation de réagir aux événements du workspace sans que les Managers ne dépendent de Qt.
- **`MainWindow` délègue entièrement à `WorkspaceManager`** — suppression de l'accès direct à l'Infrastructure (`ProjectIO`) et de l'état dupliqué (`current_project`/`project_folder`) ; `DashboardPage` et `ImagesPage` s'abonnent désormais aux événements du workspace plutôt que d'être mises à jour manuellement.
- **Extraction de la logique métier hors des widgets** — `ImagesPage` ne détient plus d'état privé ; l'import d'images passe par `WorkspaceManager.add_images()`, avec déduplication, et persiste réellement dans `project.json`.
- **Réorganisation de la structure de fichiers** — `src/pages/` déplacé sous `src/ui/pages/` ; suppression des packages vides non conformes (`src/config/`, `src/models/`, `src/widgets/`) ; suppression finale de `src/project/`, devenu totalement orphelin.

### Bugs corrigés

- **Dashboard non rafraîchi après création/ouverture d'un projet** — corrigé structurellement par le câblage événementiel (`WorkspaceManager` → `EventBus` → `DashboardPage.update_project`), plutôt que par un correctif ponctuel.
- **Une tentative d'ouverture d'un dossier invalide fermait silencieusement le workspace déjà ouvert** — `WorkspaceManager.open()` réinitialisait `current_workspace` à `None` même en cas d'échec, faisant perdre le projet en cours sans avertissement visible. Corrigé : un échec d'ouverture laisse désormais l'état courant inchangé. Cette règle métier est maintenant protégée par un test de non-régression permanent.
- **`WorkspaceManager.close()` ne publiait plus l'événement `workspace.closed`** — régression introduite lors de l'ajout d'`add_images()` (ligne de publication déplacée par erreur après un `return`, dans la mauvaise méthode). Détectée par le test d'intégration écrit pour cette même mission, corrigée dans la foulée.

### Tests ajoutés

- `tests/integration/test_workspace_roundtrip.py` (stdlib `unittest`, aucune nouvelle dépendance) :
  - `test_full_create_import_save_close_reopen_cycle` — cycle complet création → import d'images → sauvegarde → fermeture → réouverture (avec instances fraîches, simulant un vrai redémarrage), vérifiant la persistance des images et la mise à jour correcte du Dashboard et de la page Images.
  - `test_failed_open_does_not_close_current_workspace` — garde de non-régression permanente pour la règle métier « une ouverture échouée ne doit jamais fermer le workspace courant ».

### Prochaines étapes (Mission 002)

Hors périmètre de la Mission 001, à traiter dans des missions dédiées ultérieures :

- Introduction du domaine **Character** (entité centrale du Blueprint, actuellement absente) et de la propriété des ressources (Datasets, LoRAs, Prompts, Historique) qui lui revient.
- Introduction progressive des autres objets du Domain Model (`Dataset`, `Model`, `LoRA`, `Job`, `Engine`, `Plugin`) — un par mission, sans scaffolding anticipé.
- Introduction de la couche **Services** dès qu'une logique métier réelle la justifiera.
- Introduction de `src/engines/` et `src/plugins/` lors de la première intégration réelle avec un moteur externe (ComfyUI, OneTrainer, etc.).

### Améliorations UX futures

- Création automatique du dossier cible directement depuis le dialogue "Nouveau projet", sans devoir le créer manuellement au préalable dans l'explorateur Windows.

### État du projet

**Mission 001 est terminée.** L'application dispose désormais d'une architecture conforme au Blueprint 02, d'une suite de tests d'intégration et d'une documentation à jour (`README.md`, ce `CHANGELOG.md`).

**Mission 002** introduira le domaine **Character**, entité centrale du Blueprint (`docs/blueprint/04_DOMAIN_MODEL.md`), actuellement absente du code.

---

*Généré à l'issue de la Mission 001 — Blueprint Refactoring.*
