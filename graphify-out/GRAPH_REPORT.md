# Graph Report - AI-Studio-Toolkit  (2026-09-02)

## Corpus Check
- 233 files · ~479,947 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3631 nodes · 9083 edges · 207 communities (102 shown, 84 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 1159 edges (avg confidence: 0.94)
- Token cost: 1,299,936 input · 0 output

## Community Hubs (Navigation)
- EventBus & Core Managers CRUD
- Domain Model & Manager/Storage Modules
- LoRA/Model Rollback Test Suites
- Dataset Gallery Sort & Import Tests
- SelectImagesDialog & Sidebar/Thumbnails
- Prompt Assistant Dialog UI Tests
- Characters/Dashboard/Images Pages
- Domain Serialization & Deletion Results
- LoRA/Prompt/Character Mission Timeline
- Settings Discovery Tests
- InferencePage Generation & Reference Tests
- MainWindow Dirty-State Guard Tests
- InferencePage Pending Result Protection
- WorkspaceStorage Copy/Collision Primitives
- OllamaEngine HTTP Client & Tests
- AIBackend Protocol & PromptAssistantManager
- TrainingManager/TrainingPage CRUD
- ComfyUIEngine HTTP Client & Tests
- InferencePage Pending Result Guard Tests
- PromptManager Round-Trip Tests
- ApplicationSettings Domain & Round-Trip
- Central LoRA Library Manager
- LoRAPage Dirty-State & Persistence Tests
- LoRAPage Central Library Tab Tests
- ComfyUIEngine Checkpoint/LoRA Discovery
- Inference Vertical Slice Mission Timeline
- MainWindow Entry Point & Settings Tests
- NewProjectDialog Validation Tests
- PromptsPage Persistence Failure Tests
- DatasetManager/DatasetsPage Round-Trip
- LoRAPage Widget & Central Import
- LoRAManager Thumbnail Tests
- Settings Domain & SettingsPage Tests
- SettingsPage Save/Confirm Tests
- MainWindow CloseEvent Real-State Tests
- LoRA Round-Trip Tests
- App/LoRA Library Storage Tests
- WorkspaceStorage Copy/IsInside Tests
- ImagePreviewDialog Fullscreen Tests
- LoRALibraryManager Delete/Update Tests
- WorkspaceManager add_images Copy Tests
- PromptsPage Widget & Context Change
- TrainingPage Delete & Round-Trip Tests
- Model Domain & ModelManager
- ImagesPage Delete Tests
- Qt Dialog Safety Net
- ComfyUIEngine Protocol Primitives
- MainWindow Rename Pending Guard Tests
- CharacterContext & Output Contract Tests
- ComfyUIEngine upload_image Tests
- WorkflowsPage/WorkflowManager Round-Trip
- WorkspaceManager.rename() Tests
- Workflow Domain & WorkflowManager
- Create/Delete Rollback Family Overview
- GenerationWorker Reference Tests
- ModelsPage Widget & Persistence Tests
- MainWindow Rename Generation Guard Tests
- CharactersPage Dirty-State Tests
- ModelManager/ModelsPage Round-Trip
- WorkspaceManager remove_images Tests
- Prompt Domain & PromptManager
- DatasetsPage Collision & Persistence
- TrainingPage Rename & Sort Tests
- Graphify Skill Reference Documents
- build_img2img_workflow Tests
- InferencePage Prompt Dirty-State Tests
- LoRALibraryManager Import Tests
- NewProject/RenameProject Dialog Widgets
- DatasetManager add_images Copy Tests
- ImagesPage Gallery Sort Tests
- MainWindow CloseEvent Orchestration Tests
- SettingsPage Dirty-State Tests
- build_txt2img_workflow Tests
- DatasetsPage Widget (Gallery/CRUD)
- SettingsManager Update Rollback Tests
- Rename/Rollback Methods Overview
- PromptAssistantDialog Generation Tests
- WorkflowsPage Widget & Persistence
- Transactional Safety Pattern Timeline
- Character Identity & History Tests
- PromptAssistantWorker Thread Tests
- CharactersPage Identity Fiche Tests
- LoRAPage Add-to-Central-Library Tests
- Prompt Assistant Output Extraction Tests
- DatasetsPage Delete Confirmation Tests
- ImagesPage Import Persistence Tests
- PromptsPage Save-As-New Tests
- Mid-Project Mission Timeline (062-067)
- LoRA Library Path Lock Tests
- CharacterContext.from_character Tests
- LoRAPage Central Library Handlers
- InferencePage Generation Race Tests
- LoRAManager Physical Deletion Tests
- LoRAManager remove_files Tests
- Root Documentation Files
- Typed Reference Primitive Tests
- CharacterManager Update Tests
- DatasetManager Physical Deletion Tests
- GenerationManager ComfyUI-Agnosticism
- GenerationManager Core Tests
- InferencePage Generation-Active Guard
- LoRAPage Rename Tests
- MainWindow Prompts-to-Inference Tests
- Central LoRA Library Mission Timeline
- GenerationManager LoRA Forwarding Tests
- NewProjectDialog Widget
- DashboardPage Widget Tests
- DatasetManager remove_images Tests
- DatasetManager Rename Tests
- GenerationManager Reference Images Tests
- ImagesPage Selection Preservation Tests
- LoRAManager Rename Tests
- LoRAPage Delete Confirmation Tests
- ModelsPage Rename Tests
- PromptsPage Delete Button State Tests
- PromptsPage Rename Tests
- PromptsPage Send-to-Inference Tests
- RenameProjectDialog Widget Tests
- Project Rules & Doc Conventions
- Domain Entities & Ownership Patterns
- Early Foundation Missions (001-003)
- Training Domain & TrainingManager
- GenerationManager/Worker Modules
- CharacterManager Auto-Create Tests
- ImagePreviewDialog Initial Size Tests
- LoRAPage Files Selection Tests
- MainToolBar Widget Tests
- New/Open Project Generation Guard
- ModelsPage Delete Confirmation Tests
- TrainingPage Delete Confirmation Tests
- WorkflowsPage Delete Confirmation Tests
- WorkflowsPage Rename Tests
- Layered Architecture Principles
- ImportCollisionDialog Widget
- CharacterManager Update Rollback Tests
- DatasetManager Delete Rollback Tests
- DatasetManager remove_images Rollback
- ImagesPage Collision Dialog Tests
- LoRAManager add_files Rollback Tests
- LoRAManager remove_files Rollback Tests
- LoRAPage Delete Button State Tests
- ModelsPage Sort Tests
- PromptsPage Confirm Context Change
- PromptsPage Sort Tests
- WorkflowsPage Sort Tests
- WorkflowManager Scalar Rollback Tests
- Blueprint Vision & Requirements Docs
- LoRA Library Save-Failure Tests
- WorkspaceStorage rename_folder Errors
- CharacterManager Create Rollback Tests
- CharactersPage Identity Persistence
- ComfyUIEngine Architectural Tests
- ComfyUIEngine LoRA Workflow Tests
- DatasetManager Create Rollback Tests
- DatasetManager Rename Rollback Tests
- LoRAManager Delete Rollback Tests
- LoRAPage Sort Tests
- ModelManager Create Rollback Tests
- PromptManager Delete Rollback Tests
- SettingsPage Persistence Failure Tests
- TrainingManager Delete Rollback Tests
- WorkflowManager Create Rollback Tests
- LoRA-Loader-Inserted Workflow Tests
- Pre-Mission-059 Workflow Compatibility
- GenerationManager Multi-Reference Guard
- TrainingManager Rename Rollback Tests
- ComfyUI LoRA Selection Mission
- requirements.txt Dependencies
- OllamaEngine HTTP Primitives
- comfyui_workflows Module & Tests
- Confirm-Context-Change Shared Contract
- DatasetManager Character-Independence
- LoRALibraryManager List/Get Tests
- WorkflowsPage File-Path Persistence
- LoRAPage Create Persistence Tests
- DashboardCard Widget
- MainMenuBar Widget
- MainStatusBar Widget
- MainToolBar Widget
- Generation-Active Guard Primitives
- Character Identity Constraint Test
- ComfyUIEngine.generate_image Dispatch
- CharactersPage Workspace-Event Guard
- Dashboard Isolation from Characters
- WorkspaceManager Failed-Open Guard
- EventBus Subscription Independence

## God Nodes (most connected - your core abstractions)
1. `WorkspaceStorageError` - 397 edges
2. `WorkspaceManager` - 342 edges
3. `EventBus` - 326 edges
4. `CharacterManager` - 229 edges
5. `DatasetManager` - 120 edges
6. `WorkspaceStorage` - 116 edges
7. `WorkspaceManagerError` - 107 edges
8. `MainWindow` - 106 edges
9. `InferencePageTest` - 92 edges
10. `LoRAManager` - 85 edges

## Surprising Connections (you probably didn't know these)
- `CharacterManager.update()` --semantically_similar_to--> `ApplicationSettingsManager`  [INFERRED] [semantically similar]
  docs/missions/MISSION_026.md → src/managers/application_settings_manager.py
- `CharacterManager.update()` --semantically_similar_to--> `PromptManager`  [INFERRED] [semantically similar]
  docs/missions/MISSION_026.md → src/managers/prompt_manager.py
- `_DialogGuard (Qt dialog safety net)` --shares_data_with--> `GenerationWorker`  [INFERRED]
  docs/missions/MISSION_091.md → src/ui/generation_worker.py
- `PySide6 dependency` --conceptually_related_to--> `MainWindow`  [INFERRED]
  requirements.txt → src/ui/main_window.py
- `ComfyUIEngine.list_checkpoints()` --shares_data_with--> `ApplicationSettings`  [INFERRED]
  docs/missions/MISSION_025.md → src/domain/application_settings.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **AI Studio Toolkit layered architecture (Presentation/Managers/Domain/Infrastructure/Core)** — concept_layered_architecture, concept_managers_layer, concept_eventbus_core, concept_dependency_rule, concept_single_source_of_truth [EXTRACTED 1.00]
- **Blueprint document set (source of truth for product/architecture)** — docs_blueprint_00_vision, docs_blueprint_01_product_requirements, docs_blueprint_02_architecture, docs_blueprint_03_project_structure, docs_blueprint_04_domain_model [EXTRACTED 1.00]
- **End-of-mission documentation set (CLAUDE.md/PROJECT_CONTEXT/missions/CHANGELOG)** — claude, docs_project_context, docs_missions_mission_001, changelog, concept_end_of_mission_workflow [EXTRACTED 1.00]
- **Early foundational missions establishing Domain entities (001-003)** — docs_missions_mission_001, docs_missions_mission_002, docs_missions_mission_003, docs_missions_mission_001_domain_workspace, docs_missions_mission_002_character_domain, docs_missions_mission_003_dataset_domain [EXTRACTED 1.00]
- **graphify Step 3 structural + semantic extraction merge** — concept_graphify_ast_extraction, concept_graphify_semantic_extraction, concept_graphify_pipeline, _claude_skills_graphify_references_extraction_spec [EXTRACTED 1.00]
- **Character-owned Domain Entities Pattern** — src_domain_lora_lora, src_domain_prompt_prompt, src_domain_training_training, src_domain_dataset_dataset [INFERRED 0.85]
- **Workspace-owned Domain Entities Pattern** — src_domain_model_model, src_domain_workflow_workflow [EXTRACTED 1.00]
- **ComfyUI Inference Generation Pipeline** — src_ui_pages_inference_page_inferencepage, src_ui_generation_worker_generationworker, src_managers_generation_manager_generationmanager, src_engines_comfyui_engine_comfyuiengine [EXTRACTED 1.00]
- **Prompt Assistant feature evolution (Missions 030-041)** — docs_missions_mission_030_mission_030, docs_missions_mission_031_mission_031, docs_missions_mission_032_mission_032, docs_missions_mission_033_mission_033, docs_missions_mission_034_mission_034, docs_missions_mission_038_mission_038, docs_missions_mission_039_mission_039, docs_missions_mission_040_mission_040, docs_missions_mission_041_mission_041, concept_prompt_assistant_manager, concept_prompt_assistant_dialog [EXTRACTED 1.00]
- **Dataset/Images gallery management suite (Missions 042-049)** — docs_missions_mission_042_mission_042, docs_missions_mission_044_mission_044, docs_missions_mission_045_mission_045, docs_missions_mission_046_mission_046, docs_missions_mission_048_mission_048, docs_missions_mission_049_mission_049, concept_load_thumbnail_icon [EXTRACTED 1.00]
- **Principal Character / open-project consistency fixes** — docs_missions_mission_028_mission_028, docs_missions_mission_029_mission_029, docs_missions_mission_036_mission_036, docs_missions_mission_037_mission_037, concept_principal_character, concept_no_project_vs_no_character [EXTRACTED 1.00]
- **Transactional rollback safety family (create/update/delete persistence-failure handling)** — docs_missions_mission_066_safe_image_deletion_persistence, docs_missions_mission_067_rollback_additive_filesystem_mutations, docs_missions_mission_068_rollback_domain_only_deletions, docs_missions_mission_070_rollback_scalar_domain_mutations, docs_missions_mission_071_rollback_promptmanager_delete, docs_missions_mission_072_rollback_domain_only_create [EXTRACTED 0.90]
- **Post-creation rename family (Model/Workflow/LoRA, Prompt, Dataset/Training)** — docs_missions_mission_052_rename_model_workflow_lora, docs_missions_mission_053_rename_prompt, docs_missions_mission_054_rename_dataset_training [EXTRACTED 0.85]
- **Delete UX-safety family (confirmation, selection-sync, safe persistence)** — docs_missions_mission_062_confirm_destructive_deletion, docs_missions_mission_063_sync_delete_with_selection, docs_missions_mission_066_safe_image_deletion_persistence [INFERRED 0.75]
- **Domain-to-persistence rollback security series (Missions 073-077)** — docs_missions_mission_073_mission073, docs_missions_mission_074_mission074, docs_missions_mission_075_mission075, docs_missions_mission_076_mission076, docs_missions_mission_077_mission077, concept_rollback_on_persistence_failure [EXTRACTED 1.00]
- **Dirty-state draft protection generalization across Pages** — docs_missions_mission_078_mission078, docs_missions_mission_079_mission079, docs_missions_mission_083_mission083, docs_missions_mission_090_mission090, concept_dirty_state_protection [INFERRED 0.85]
- **Central LoRA library foundation-to-editing build-out (Missions 087-092)** — docs_missions_mission_087_mission087, docs_missions_mission_088_mission088, docs_missions_mission_089_mission089, docs_missions_mission_090_mission090, docs_missions_mission_092_mission092, concept_central_lora_library [EXTRACTED 1.00]

## Communities (207 total, 84 thin omitted)

### Community 0 - "EventBus & Core Managers CRUD"
Cohesion: 0.04
Nodes (21): EventBus, Lightweight, Qt-free publish/subscribe event bus. Domain and Application-layer…, CharacterManager, Coordinates Character CRUD and selection within the current workspace. Operates…, DatasetManager, Rename the active dataset. Mirrors PromptManager.update_name()'s exact…, Removes from the active Dataset's own Image pool every entry whose file_path…, Coordinates Dataset CRUD, selection and image import within the Workspace's… (+13 more)

### Community 1 - "Domain Model & Manager/Storage Modules"
Cohesion: 0.10
Nodes (29): Events are identified by plain string names (e.g. "workspace.created"), not by…, _default_lora_library_path(), Image, Raised specifically by rename_folder() when the OS reports access denied…, WorkspaceRenamePermissionError, WorkspaceStorage, Exception, Raised by WorkspaceManager when a workspace operation fails. Wraps… (+21 more)

### Community 2 - "LoRA/Model Rollback Test Suites"
Cohesion: 0.04
Nodes (21): Exception, Raised when a workspace cannot be read from or written to disk., WorkspaceStorageError, LoRAManagerCreateRollbackTest, LoRAManagerMetadataRollbackTest, LoRAManagerRenameRollbackTest, Mission 073: LoRAManager.update() rolls back all four text-metadata fields…, Mission 072: LoRAManager.create() rolls back the in-memory append (the same… (+13 more)

### Community 3 - "Dataset Gallery Sort & Import Tests"
Cohesion: 0.06
Nodes (7): DatasetsPageGallerySortTest, DatasetsPageGalleryTest, DatasetsPageImagesSelectionPreservationTest, _make_png(), patch, Mission 048: images_list is now sorted by Path(file_path).name, case-…, Mission 082: images_list.selectedItems()/currentItem() must survive a same-…

### Community 4 - "SelectImagesDialog & Sidebar/Thumbnails"
Cohesion: 0.05
Nodes (16): QListWidget, QDialog, Mission 044: lets the user pick one or more images already present in the…, Returns the full internal file path of every image the user selected. Only…, SelectImagesDialog, Sidebar, _decode_and_scale(), load_thumbnail_icon() (+8 more)

### Community 5 - "Prompt Assistant Dialog UI Tests"
Cohesion: 0.06
Nodes (17): PromptAssistantDialog, QDialog, PromptAssistantDialog — Mission 031's UI entry point for…, _fake_screen(), PromptAssistantDialogCloseGuardTest, PromptAssistantDialogIdentityCheckboxTest, PromptAssistantDialogInitialSizeTest, PromptAssistantDialogLayoutTest (+9 more)

### Community 6 - "Characters/Dashboard/Images Pages"
Cohesion: 0.06
Nodes (14): CharactersPage, QWidget, Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED and…, Mission 078: same role as PromptsPage.confirm_context_change() (Mission 069) —…, DashboardPage, QWidget, ImagesPage, QWidget (+6 more)

### Community 7 - "Domain Serialization & Deletion Results"
Cohesion: 0.06
Nodes (16): Mission 057 - Remove Vestigial Workspace Fields and Dead Code, Mission 058 - Dead Code and Stale Documentation Cleanup (Round 2), Character, Dataset, Shared by Workspace.from_dict() and Dataset.from_dict(), the two independent…, Path, Workspace, Mission 026 (post-smoke-test revision): the Character CharactersPage's identity… (+8 more)

### Community 8 - "LoRA/Prompt/Character Mission Timeline"
Cohesion: 0.06
Nodes (51): AIBackend Protocol / AIModelInfo / AIBackendError, CharacterContext DTO / from_character(), DashboardPage.trainingCard real session counter, DatasetManager.remove_images(), Dataset thumbnail gallery (DatasetsPage.images_list IconMode), Gallery sort by file mtime (file_mtime_sort_key), Gallery sort by filename (Images/Dataset galleries), ImportCollisionDialog (+43 more)

### Community 9 - "Settings Discovery Tests"
Cohesion: 0.06
Nodes (9): AIModelInfo, NamedTuple, Deliberately minimal — only what every backend can report today. Additive by…, patch, Mission 059: same discovery/selection pattern as…, Mission 030: same discovery/selection pattern as…, SettingsPageCheckpointDiscoveryTest, SettingsPageLoraDiscoveryTest (+1 more)

### Community 11 - "MainWindow Dirty-State Guard Tests"
Cohesion: 0.08
Nodes (6): MainWindowConfirmContextChangeTest, MainWindowInferencePendingResultGuardTest, MainWindowInferencePromptGuardTest, Mission 069: the PromptsPage.confirm_context_change() guard wired into…, Mission 083: InferencePage.confirm_context_change(), the 5th guard, appended…, Mission 084: InferencePage.confirm_pending_result_change(), the 6th and last…

### Community 12 - "InferencePage Pending Result Protection"
Cohesion: 0.07
Nodes (14): Pending Generation Result Protection, Mission 084 - Protect Pending Generation Result Against Silent Loss, Mission 085 - Refuse Close/Rename While Generation Is Active, Mission 086 - Select Inference Reference Image from Workspace Gallery, InferencePage, QWidget, Runs once this specific cycle's thread has fully stopped (thread.finished).…, Called from MainWindow.closeEvent() so a generation in progress never leaves a… (+6 more)

### Community 13 - "WorkspaceStorage Copy/Collision Primitives"
Cohesion: 0.05
Nodes (26): Path, Returns a Path inside destination_folder guaranteed not to already exist on…, Permanently deletes `path` and everything inside it (Mission 075) — the final,…, Writes project.json atomically: the content is fully written to a temporary…, Read-only prediction (Mission 028 second smoke test) of every source in `paths`…, Copies each path in `paths` into <workspace_root>/datasets/<dataset_id>/…, CollisionInfo, ImportResult (+18 more)

### Community 14 - "OllamaEngine HTTP Client & Tests"
Cohesion: 0.09
Nodes (12): OllamaEngine, Minimal HTTP client for a local or remote Ollama instance's own API (GET…, Generic Ollama protocol client (Infrastructure layer), structurally satisfying…, _FakeResponse, _http_error(), OllamaEngineArchitecturalConstraintsTest, OllamaEngineGenerateTextTest, OllamaEngineListModelsTest (+4 more)

### Community 15 - "AIBackend Protocol & PromptAssistantManager"
Cohesion: 0.08
Nodes (23): Protocol, AIBackend, AIBackendError, Exception, Minimal structural contract for a future "AI Studio Toolkit -> AI backend"…, Common error type every AIBackend implementation raises for any…, Structural contract (typing.Protocol — no inheritance required, same zero-…, Returns the models currently available on this backend. (+15 more)

### Community 16 - "TrainingManager/TrainingPage CRUD"
Cohesion: 0.06
Nodes (12): Dataset-Training Referential Integrity, Rename the active training. Mirrors PromptManager.update_name()'s exact…, Coordinates Training CRUD and selection within the Workspace's principal…, TrainingManager, QWidget, TrainingPage, Mission 029 regression: same defect as LoRAManager/PromptManager (see…, Mission 054: TrainingManager.update_name() — mirrors… (+4 more)

### Community 17 - "ComfyUIEngine HTTP Client & Tests"
Cohesion: 0.08
Nodes (10): ComfyUIEngine, Minimal HTTP client for a ComfyUI instance's own API (POST /prompt, GET…, Generic ComfyUI protocol client (Infrastructure layer). Imports nothing from…, ComfyUIEngineDownloadOutputTest, ComfyUIEngineGenerateImageTest, ComfyUIEngineSubmitTest, ComfyUIEngineWaitForResultTest, _FakeResponse (+2 more)

### Community 18 - "InferencePage Pending Result Guard Tests"
Cohesion: 0.06
Nodes (5): InferencePagePendingResultGuardTest, InferencePagePromptAssistantTest, patch, Mission 031: "Assistant IA" and "Enregistrer dans Prompts". A lightweight setUp…, Mission 084: InferencePage.confirm_pending_result_change() — the 6th MainWindow…

### Community 19 - "PromptManager Round-Trip Tests"
Cohesion: 0.09
Nodes (9): PromptRoundTripTest, Mission 031 (InferencePage's "Enregistrer dans Prompts", pre-implementation…, Mission 035: with no Prompt active (e.g. a fresh Assistant IA draft),…, Mission 035: with a Prompt already active, "Enregistrer comme nouveau…, Mission 032: "Utiliser ce texte" must never call…, Mission 038, Category A: WORKSPACE_SAVED, WORKSPACE_RENAMED and PROMPT_CREATED…, Mission 038: Annuler must never call PromptManager.select() at all — the…, Mission 070: a Save choice whose update_text() raises WorkspaceManagerError… (+1 more)

### Community 20 - "ApplicationSettings Domain & Round-Trip"
Cohesion: 0.10
Nodes (9): Mission 010 - Application Settings Domain, ApplicationSettings, Path, ApplicationSettingsManager, Path, Coordinates read/write access to ApplicationSettings — a singleton entirely…, ApplicationSettingsRoundTripTest, LoRACreationWithoutManualCharacterSelectionTest (+1 more)

### Community 21 - "Central LoRA Library Manager"
Cohesion: 0.10
Nodes (14): LoRA, LoRALibraryError, LoRALibraryManager, Exception, Path, engine/architecture/trigger_word/version (Mission 088) are transmitted as-is to…, Mission 090: a single combined mutation for name + the 4 text metadata fields —…, Raised on any real failure of a LoRALibraryManager mutation — a partial/failed… (+6 more)

### Community 22 - "LoRAPage Dirty-State & Persistence Tests"
Cohesion: 0.09
Nodes (7): LoRAPageDirtyStateTest, LoRAPageFilesPersistenceFailureTest, LoRAPageMetadataPersistenceFailureTest, Mission 073: LoRAPage.save_metadata() catches WorkspaceManagerError around…, Mission 076: LoRAPage.import_files()/remove_selected_files() catch…, Mission 078: LoRAPage.update_loras() used to unconditionally overwrite the 4…, Mission 078's core non-regression test: reproduces, as a permanent automated…

### Community 24 - "ComfyUIEngine Checkpoint/LoRA Discovery"
Cohesion: 0.11
Nodes (6): ComfyUIEngineListCheckpointsTest, ComfyUIEngineListLorasTest, _http_error(), patch, Mission 025: list_checkpoints() asks the running ComfyUI server which…, Mission 059: list_loras() asks the running ComfyUI server which LoRA it…

### Community 25 - "Inference Vertical Slice Mission Timeline"
Cohesion: 0.10
Nodes (35): Image Ownership Model D (Dual Pool), Mission 011 - Image Domain, Non-Self-Reference Documentation Principle, AI Studio Toolkit -> ComfyUI Protocol Boundary, Mission 012 - ComfyUI Engine Minimal, Mission 013 - Inference Vertical Slice, QThread Race Condition Fix, Generate/Preview/Accept/Reject/Regenerate State Machine (+27 more)

### Community 26 - "MainWindow Entry Point & Settings Tests"
Cohesion: 0.09
Nodes (11): QMainWindow, main(), AI Studio Toolkit Main entry point, MainWindow, text is exactly what PromptsPage.text_edit currently shows — never re-read from…, MainWindowComfyUISettingsTest, _fake_screen(), MainWindowInitialSizeTest (+3 more)

### Community 28 - "PromptsPage Persistence Failure Tests"
Cohesion: 0.09
Nodes (7): PromptsPageCreatePersistenceFailureTest, PromptsPageDeletePersistenceFailureTest, PromptsPagePromptAssistantTest, patch, Mission 072: PromptsPage.create_prompt()/save_as_new_prompt() both catch…, Mission 032: "Assistant IA" in PromptsPage, reusing Mission 031's…, Mission 071: PromptsPage.delete_prompt() -> PromptManager.delete(). A save()…

### Community 29 - "DatasetManager/DatasetsPage Round-Trip"
Cohesion: 0.10
Nodes (6): DatasetRoundTripTest, DatasetsPageDeleteButtonStateTest, DatasetsPageRenameTest, Mission 054: DatasetsPage.name_edit — real-widget rename, mirroring…, Mission 045: the core property survives a real close/reopen — an image shared…, Mission 063: "Supprimer" must always reflect whether there is currently a valid…

### Community 30 - "LoRAPage Widget & Central Import"
Cohesion: 0.12
Nodes (7): Dashboard Datasets Card Bug Fix, Mission 004 - LoRA Domain, LoRAPage, QWidget, Mission 078: same role as PromptsPage.confirm_context_change() (Mission 069) —…, Mission 088: copies the currently active Character-scoped LoRA into the…, Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED and…

### Community 31 - "LoRAManager Thumbnail Tests"
Cohesion: 0.14
Nodes (6): LoRAManagerMetadataTest, LoRAManagerThumbnailCleanupTest, _make_png(), Mission 047: LoRAManager.update() (text metadata, idempotent, same contract as…, Mission 080: replacing an owned thumbnail (one actually copied into this LoRA's…, Mission 080: once a new thumbnail has been durably persisted by…

### Community 32 - "Settings Domain & SettingsPage Tests"
Cohesion: 0.10
Nodes (9): Mission 008 - Training Domain, Mission 009 - Settings Domain (Workspace), Settings, Mission 077: if save() fails, settings.theme/settings.language are restored to…, Coordinates read/write access to the current Workspace's Settings. Unlike every…, SettingsManager, Mission 059: SettingsPage.sizeHint() must never balloon past a normal desktop…, SettingsPageSizeHintRegressionTest (+1 more)

### Community 33 - "SettingsPage Save/Confirm Tests"
Cohesion: 0.09
Nodes (10): object, ApplicationSettingsStorageError, Exception, Raised when the application settings file cannot be written to disk., QWidget, Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED — never to…, Mission 078: same role as PromptsPage.confirm_context_change() (Mission 069) —…, SettingsPage (+2 more)

### Community 34 - "MainWindow CloseEvent Real-State Tests"
Cohesion: 0.11
Nodes (6): _controlled_generate(), MainWindowCloseEventRealStateTest, Mission 079: MainWindow.closeEvent() gains the same dirty-draft guard already…, Real Workspace/Character/LoRA/Settings state on the real window — only the…, Mission 085: a GenerationManager.generate() replacement whose start and…, _wait_until()

### Community 36 - "App/LoRA Library Storage Tests"
Cohesion: 0.12
Nodes (9): ApplicationSettingsStorage, LoRALibraryStorage, Path, Mission 087: persists the central LoRA registry — deliberately a separate file…, LoRALibraryStorageTest, Integration coverage for Mission 087 — the central LoRA library foundation.…, Narrow coverage for Mission 018 — MainWindow reads ComfyUI's base_url/…, Mission 060 — MainWindow.__init__() no longer hard-codes resize(1700, 950)… (+1 more)

### Community 37 - "WorkspaceStorage Copy/IsInside Tests"
Cohesion: 0.11
Nodes (10): True if `path` resolves to a location under `root` (root itself included),…, Returns a Path usable as an Image's internal file_path for `source` (Mission…, LoRADeletionResult, LoRAThumbnailResult, NamedTuple, Mission 075: delete()'s return type — see DatasetDeletionResult…, Copies source_path into <workspace_root>/models/loras/<lora_id>/…, Mission 080: set_thumbnail()'s return type on success — same principle as… (+2 more)

### Community 38 - "ImagePreviewDialog Fullscreen Tests"
Cohesion: 0.19
Nodes (7): Mission 060 - Adaptive Initial Window Size, Mission 061 - Adaptive Dialog Sizing, ImagePreviewDialog, QDialog, Mission 015: strictly passive image viewer, shared between ImagesPage and…, ImagePreviewDialogTest, _make_png()

### Community 39 - "LoRALibraryManager Delete/Update Tests"
Cohesion: 0.09
Nodes (6): LoRALibraryDeletionResult, NamedTuple, delete()'s return type — same shape and rationale as…, LoRALibraryManagerDeleteTest, LoRALibraryManagerUpdateTest, Mission 090: LoRALibraryManager.update() — a single combined mutation for…

### Community 41 - "PromptsPage Widget & Context Change"
Cohesion: 0.11
Nodes (6): PromptsPage, QWidget, Mission 069: called by MainWindow before a Workspace switch…, Subscribed by MainWindow to WORKSPACE_CREATED/OPENED/CLOSED and…, PromptCreationWithoutManualCharacterSelectionTest, Mission 029 regression: same defect as LoRAManager (see…

### Community 42 - "TrainingPage Delete & Round-Trip Tests"
Cohesion: 0.13
Nodes (3): Mission 063: "Supprimer" must always reflect whether there is currently a valid…, TrainingPageDeleteButtonStateTest, TrainingRoundTripTest

### Community 43 - "Model Domain & ModelManager"
Cohesion: 0.14
Nodes (8): Mission 006 - Model Domain, Workspace-owned Ownership Pattern, Model, ModelManager, Mission 068: if save() fails after the Model has already been removed from…, Replace the active model's file_path. Mirrors PromptManager.update_text()'s…, Rename the active model. Mirrors update_file_path()'s exact contract: a single…, Coordinates Model CRUD, selection and file path editing within the current…

### Community 44 - "ImagesPage Delete Tests"
Cohesion: 0.12
Nodes (3): ImagesPageTest, _make_png(), Patches QMessageBox so that delete_selected_images()'s confirmation dialog is…

### Community 45 - "Qt Dialog Safety Net"
Cohesion: 0.14
Nodes (10): AssertionError, _describe(), _DialogGuard, guard_against_unexpected_dialogs(), QObject, Mission 091: shared safety net against unexpected, unmocked real QMessageBox…, A real QMessageBox appeared during a test and was never mocked., UnexpectedDialogError (+2 more)

### Community 46 - "ComfyUIEngine Protocol Primitives"
Cohesion: 0.12
Nodes (12): ComfyUIEngineError, Exception, Request, GET /view?filename=&subfolder=&type= — the exact query parameters ComfyUI's…, POST /upload/image — uploads a local file to the ComfyUI instance so it becomes…, GET /object_info/CheckpointLoaderSimple (Mission 025) — asks the running…, GET /object_info/LoraLoader (Mission 059) — same mechanism as…, Shared submit -> wait -> download sequence, extracted in Mission 023 so both… (+4 more)

### Community 47 - "MainWindow Rename Pending Guard Tests"
Cohesion: 0.15
Nodes (3): MainWindowRenamePendingResultGuardTest, MainWindowRenameProjectTest, Mission 084: InferencePage.confirm_pending_result_change() as the SOLE guard…

### Community 48 - "CharacterContext & Output Contract Tests"
Cohesion: 0.19
Nodes (8): CharacterContext, NamedTuple, existing_prompt="" -> "Create" intent: request_text alone is turned into a…, Mission 034: the minimal, explicit subset of Character's identity fields the…, PromptAssistantManagerOutputContractInstructionTest, PromptAssistantManagerWithContextTest, Mission 034: character_context prepends an explicit identity block., Mission 039: the output-contract block is appended exactly once, identically…

### Community 50 - "WorkflowsPage/WorkflowManager Round-Trip"
Cohesion: 0.16
Nodes (3): Mission 063: "Supprimer" must always reflect whether there is currently a valid…, WorkflowRoundTripTest, WorkflowsPageDeleteButtonStateTest

### Community 52 - "Workflow Domain & WorkflowManager"
Cohesion: 0.16
Nodes (7): Mission 007 - Workflow Domain, Workflow, Mission 068: if save() fails after the Workflow has already been removed from…, Replace the active workflow's file_path. Mirrors…, Rename the active workflow. Mirrors update_file_path()'s exact contract: a…, Coordinates Workflow CRUD, selection and file path editing within the current…, WorkflowManager

### Community 53 - "Create/Delete Rollback Family Overview"
Cohesion: 0.10
Nodes (8): Mission 055 - Handle Settings Persistence Failures Gracefully, Mission 068 - Rollback Domain-Only Deletions on Persistence Failure, Mission 069 - Protect PromptsPage Draft Before New/Open Project, Mission 071 - Rollback PromptManager.delete() on Persistence Failure, Mission 072 - Rollback Domain-Only create() on Persistence Failure, PromptsPage dirty-state Save/Discard/Cancel pattern, ApplicationSettingsManager.update(), WorkspaceManager.save()

### Community 54 - "GenerationWorker Reference Tests"
Cohesion: 0.14
Nodes (9): GenerationWorker, QObject, GenerationWorkerReferenceImagesTest, GenerationWorkerReferenceStrengthTest, GenerationWorkerTest, Mission 022: reference_images propagation and the snapshot guarantee — a…, Mission 024: reference_strength propagation, and the same construction-time…, Test-only harness. In the real application, MainWindow's QThread is… (+1 more)

### Community 55 - "ModelsPage Widget & Persistence Tests"
Cohesion: 0.11
Nodes (6): ModelsPage, QWidget, ModelsPageCreatePersistenceFailureTest, ModelsPageFilePathPersistenceFailureTest, Mission 070: browse_file() -> update_file_path(). Unlike name_edit,…, Mission 072: ModelsPage.create_model() catches WorkspaceManagerError around…

### Community 56 - "MainWindow Rename Generation Guard Tests"
Cohesion: 0.15
Nodes (8): start_dialog_guard(), stop_dialog_guard(), _controlled_generate(), MainWindowRenameGenerationActiveGuardTest, Narrow coverage for MainWindow.rename_project()'s wiring to…, Mission 085: InferencePage.confirm_no_active_generation() as the FIRST check in…, Mission 085: a GenerationManager.generate() replacement whose start and…, _wait_until()

### Community 57 - "CharactersPage Dirty-State Tests"
Cohesion: 0.16
Nodes (4): CharactersPageDirtyStateTest, Mission 078: CharactersPage.update_characters() used to unconditionally…, Mission 078's core non-regression test: reproduces, as a permanent automated…, A clean fiche (nothing typed) must still reflect a mutation applied directly…

### Community 58 - "ModelManager/ModelsPage Round-Trip"
Cohesion: 0.16
Nodes (3): ModelRoundTripTest, ModelsPageDeleteButtonStateTest, Mission 063: "Supprimer" must always reflect whether there is currently a valid…

### Community 60 - "Prompt Domain & PromptManager"
Cohesion: 0.17
Nodes (8): Mission 005 - Prompt Domain, Prompt, PromptManager, Mission 071: if save() fails after the Prompt has already been removed from…, Replace the active prompt's text. Unlike DatasetManager.add_images()/…, Rename the active prompt. Mirrors update_text()'s exact contract: a single…, Coordinates Prompt CRUD, selection and text editing within the Workspace's…, text defaults to "" — existing callers (PromptsPage.create_prompt()) are…

### Community 61 - "DatasetsPage Collision & Persistence"
Cohesion: 0.16
Nodes (7): DatasetsPageCollisionDialogTest, DatasetsPageCreatePersistenceFailureTest, DatasetsPageRemoveImagesPersistenceFailureTest, patch, Mission 076: DatasetsPage.remove_selected_images_from_dataset() catches…, Mission 028 second smoke test: DatasetsPage.import_images() — same collision UX…, Mission 072: DatasetsPage.create_dataset() catches WorkspaceManagerError around…

### Community 62 - "TrainingPage Rename & Sort Tests"
Cohesion: 0.16
Nodes (4): Mission 051: TrainingPage.training_list is now sorted by name, case-…, Mission 054: TrainingPage.name_edit — real-widget rename, mirroring…, TrainingPageRenameTest, TrainingPageSortTest

### Community 63 - "Graphify Skill Reference Documents"
Cohesion: 0.13
Nodes (19): Root .claude/CLAUDE.md, graphify add-watch reference, graphify exports reference, graphify extraction-spec reference, graphify github-and-merge reference, graphify hooks reference, graphify query reference, graphify transcribe reference (+11 more)

### Community 64 - "build_img2img_workflow Tests"
Cohesion: 0.18
Nodes (4): build_img2img_workflow(), Mission 023's first non-txt2img graph — native ComfyUI core nodes only, no…, BuildImg2ImgWorkflowTest, Mission 023: build_img2img_workflow() — the first non-txt2img graph, native…

### Community 67 - "NewProject/RenameProject Dialog Widgets"
Cohesion: 0.15
Nodes (8): Presentation-layer-only validation (no Domain/Manager rule). Returns None if…, validate_project_name(), QDialog, Mission 027: renames the current project's folder from within the application…, Returns (new_name, error_message). new_name is a ready-to-use string only when…, RenameProjectDialog, Real-widget coverage for NewProjectDialog (Mission 016): validates that the…, Real-widget coverage for RenameProjectDialog (Mission 027). Only the dialog's…

### Community 71 - "SettingsPage Dirty-State Tests"
Cohesion: 0.11
Nodes (4): Mission 078: SettingsPage.update_settings() used to unconditionally overwrite…, Mission 078's core non-regression test: reproduces, as a permanent automated…, Mission 078 + Mission 077 combined non-regression: a rejected theme must never…, SettingsPageDirtyStateTest

### Community 72 - "build_txt2img_workflow Tests"
Cohesion: 0.21
Nodes (4): build_txt2img_workflow(), Mission 012's fixed demonstration workflow (ComfyUI API format) — a minimal,…, BuildTxt2ImgWorkflowTest, Mission 023: build_txt2img_workflow() replaces Mission 012's…

### Community 74 - "SettingsManager Update Rollback Tests"
Cohesion: 0.12
Nodes (3): Mission 077: SettingsManager.update() rolls back settings.theme/…, Mission 077's core non-regression test: reproduces, as a permanent automated…, SettingsManagerUpdateRollbackTest

### Community 75 - "Rename/Rollback Methods Overview"
Cohesion: 0.17
Nodes (12): Mission 050 - Remove Individual Files from a LoRA, Mission 051 - Sort Remaining Entity Lists by Name, Mission 052 - Rename Model, Workflow and LoRA after Creation, Mission 053 - Rename Prompt after Creation, Mission 054 - Rename Dataset and Training after Creation, Mission 070 - Rollback Scalar Domain-Only Mutations on Persistence Failure, DatasetManager.update_name(), LoRAManager.update_name() (+4 more)

### Community 76 - "PromptAssistantDialog Generation Tests"
Cohesion: 0.24
Nodes (7): PromptAssistantError, Exception, Normalizes AIBackendError and "a request is already in progress" into a single…, PromptAssistantDialogGenerateTest, patch, Mission 040: a successful result already displayed must remain usable after a…, _wait_until()

### Community 77 - "WorkflowsPage Widget & Persistence"
Cohesion: 0.14
Nodes (4): QWidget, WorkflowsPage, Mission 072: WorkflowsPage.create_workflow() catches WorkspaceManagerError…, WorkflowsPageCreatePersistenceFailureTest

### Community 78 - "Transactional Safety Pattern Timeline"
Cohesion: 0.21
Nodes (15): Dirty-State Draft Protection Pattern, Multi-Selection Preservation Across UI Rebuilds, Rollback-on-Persistence-Failure Pattern, Transactional Physical Cleanup via .trash/, Mission 073 - Rollback LoRAManager.update() Metadata, Mission 074 - Rollback CharacterManager.update() Identity, Mission 075 - Transactional Physical Cleanup of Dataset/LoRA Folders, Mission 076 - Rollback remove_images()/add_files()/remove_files() (+7 more)

### Community 79 - "Character Identity & History Tests"
Cohesion: 0.15
Nodes (4): CharacterHistoryFieldRemovalTest, CharacterIdentityDomainTest, Mission 026: Character gains six additive identity fields…, Mission 057: Character.history removed — never populated nor read anywhere in…

### Community 80 - "PromptAssistantWorker Thread Tests"
Cohesion: 0.22
Nodes (5): PromptAssistantWorker, QObject, PromptAssistantWorkerTest, Coverage for src/ui/prompt_assistant_worker.py — PromptAssistantWorker actually…, _run_worker()

### Community 83 - "Prompt Assistant Output Extraction Tests"
Cohesion: 0.24
Nodes (3): Mission 039: deterministic extraction only — never a guess at which part of the…, PromptAssistantManagerExtractFinalPromptTest, Mission 039: deterministic extraction/fallback contract of…

### Community 84 - "DatasetsPage Delete Confirmation Tests"
Cohesion: 0.23
Nodes (4): DatasetsPageDeleteConfirmationTest, Mission 062: DatasetsPage.delete_dataset() now confirms before deleting,…, Mission 068: DatasetManager.delete() rolls back the Domain removal (and…, Mission 075: delete_dataset() now physically removes the Dataset's private…

### Community 85 - "ImagesPage Import Persistence Tests"
Cohesion: 0.16
Nodes (3): ImagesPageImportPersistenceFailureTest, patch, Mission 067: add_images() now rollbacks Workspace.images and compensates any…

### Community 87 - "Mid-Project Mission Timeline (062-067)"
Cohesion: 0.21
Nodes (8): Mission 062 - Confirm Destructive Entity Deletion, Mission 063 - Synchronize Delete Action with Selection, Mission 064 - Thumbnail Cache, Mission 065 - Block Prompt Assistant Close While Generation Is Running, Mission 066 - Safe Image Deletion Persistence, Mission 067 - Rollback Additive Filesystem Mutations on Persistence Failure, ImagesPage/PromptsPage delete-confirmation pattern (Cancel-default QMessageBox), Qt/PySide6 intermittent native segfault (test suite)

### Community 88 - "LoRA Library Path Lock Tests"
Cohesion: 0.21
Nodes (5): LoRALibraryPathLockedError, Exception, Mission 087: raised by update() when lora_library_path is given a genuinely…, ApplicationSettingsLoraLibraryLockTest, The path-change lock contract (decision validated by the architect): registre…

### Community 89 - "CharacterContext.from_character Tests"
Cohesion: 0.23
Nodes (3): The single Character -> CharacterContext conversion point in the whole codebase…, CharacterContextFromCharacterTest, Mission 034: the single Character -> CharacterContext conversion point.

### Community 90 - "LoRAPage Central Library Handlers"
Cohesion: 0.19
Nodes (3): Mission 090: mirrors LoRAPage.confirm_context_change() (Mission 078), but is…, Mission 089: subscribed (see main_window.py) only to…, Mission 092: second, independent entry point into…

### Community 91 - "InferencePage Generation Race Tests"
Cohesion: 0.17
Nodes (3): _pump(), Test-only: pumps the main thread's event loop so queued worker->InferencePage…, _wait_until()

### Community 94 - "Root Documentation Files"
Cohesion: 0.36
Nodes (10): CHANGELOG.md mission-by-mission log (through Mission 092), Character (Domain entity), Character-owned entity ownership pattern, Dataset (Domain entity), Knowledge Base (per-Character), LoRA (Domain entity), Training (Domain entity), Workspace domain object (Mission 001) (+2 more)

### Community 95 - "Typed Reference Primitive Tests"
Cohesion: 0.24
Nodes (5): NamedTuple, A single typed reference image for a generation request (Mission 056) —…, Reference, GenerationManagerTypedReferenceTest, Mission 056: reference_images now accepts either a plain str (legacy local file…

### Community 98 - "GenerationManager ComfyUI-Agnosticism"
Cohesion: 0.17
Nodes (5): GenerationManagerComfyUIAgnosticismTest, GenerationManagerReferenceStrengthTest, Coverage for src/managers/generation_manager.py — GenerationManager's…, Mission 024: reference_strength is a generic 0.0-1.0 concept at this boundary —…, Mission 023: GenerationManager must never learn ComfyUI's JSON graph vocabulary…

### Community 100 - "InferencePage Generation-Active Guard"
Cohesion: 0.23
Nodes (4): _controlled_generate(), InferencePageGenerationActiveGuardTest, Mission 085: InferencePage.is_generation_active()/…, Mission 085: a GenerationManager.generate() replacement whose start and…

### Community 104 - "Central LoRA Library Mission Timeline"
Cohesion: 0.40
Nodes (11): Central LoRA Library (Application-level Registry), confirm_context_change() Guard Pattern, Generation-Active Guard (isRunning() check), Qt Dialog Safety Net (Test Harness Reliability), Mission 087 - Central LoRA Library Foundation, Mission 088 - Add an Existing LoRA to the Central Library, Mission 089 - Central LoRA Library Read-Only Consultation and Deletion, Mission 090 - Central LoRA Library Entry Editing (+3 more)

### Community 105 - "GenerationManager LoRA Forwarding Tests"
Cohesion: 0.24
Nodes (4): GenerationManager, Blocking call — delegates to ComfyUIEngine.generate_image(). Returns the…, GenerationManagerLoraTest, Mission 059: lora_name/lora_strength are set once at construction, like…

### Community 106 - "NewProjectDialog Widget"
Cohesion: 0.25
Nodes (4): NewProjectDialog, QDialog, Returns (target_path, error_message). target_path is a ready- to-create Path…, Mission 016: builds and validates a target_path (parent directory + project…

### Community 113 - "LoRAPage Delete Confirmation Tests"
Cohesion: 0.29
Nodes (3): LoRAPageDeleteConfirmationTest, Mission 062: LoRAPage.delete_lora() now confirms before deleting, mirroring…, Mission 068: LoRAManager.delete() rolls back the Domain removal (and…

### Community 119 - "Project Rules & Doc Conventions"
Cohesion: 0.29
Nodes (8): Root CLAUDE.md (project rules), ApplicationSettings (Application-level singleton), Impact report → validation → implementation → verification sequence, Defensive compatibility, never implicit migration, End-of-mission documentation workflow (permanent rule), Git rules (no force-push/rebase/reset without explicit authorization), Strict idempotence for update_*() methods, Singleton Application-level pattern (ApplicationSettings)

### Community 120 - "Domain Entities & Ownership Patterns"
Cohesion: 0.31
Nodes (9): Engine (Domain entity/abstraction), Job (Domain entity), Model (Domain entity), Plugin (Domain entity), Settings (Domain entity), Singleton Workspace-owned pattern (Settings), Workflow (Domain entity), Workspace (Domain entity) (+1 more)

### Community 121 - "Early Foundation Missions (001-003)"
Cohesion: 0.33
Nodes (10): MISSION_001.md — Blueprint Refactoring, EventBus introduced (Mission 001), WorkspaceManager application layer, WorkspaceStorage infrastructure, MISSION_002.md — Character Domain, CharacterManager, CharactersPage UI, MISSION_003.md — Dataset Domain (+2 more)

### Community 123 - "GenerationManager/Worker Modules"
Cohesion: 0.29
Nodes (6): GenerationError, Exception, GenerationManager coordinates a single image generation request against…, Raised by GenerationManager on any failure to fulfil a generation request — an…, GenerationWorker runs GenerationManager.generate() off the Qt main thread. It…, Coverage for src/ui/generation_worker.py — GenerationWorker actually runs off…

### Community 125 - "ImagePreviewDialog Initial Size Tests"
Cohesion: 0.29
Nodes (4): _fake_screen(), ImagePreviewDialogInitialSizeTest, Real-widget coverage for Mission 015's ImagePreviewDialog: a strictly passive…, Mission 061: same availableGeometry()-bounded contract as MainWindow (Mission…

### Community 128 - "New/Open Project Generation Guard"
Cohesion: 0.36
Nodes (5): _controlled_generate(), MainWindowNewOpenGenerationActiveNonRegressionTest, Mission 085: a GenerationManager.generate() replacement whose start and…, Mission 085: New Project and Open Project deliberately gain NO new guard for a…, _wait_until()

### Community 129 - "ModelsPage Delete Confirmation Tests"
Cohesion: 0.31
Nodes (3): ModelsPageDeleteConfirmationTest, Mission 062: ModelsPage.delete_model() now confirms before deleting, mirroring…, Mission 068: ModelManager.delete() rolls back the Domain removal (and…

### Community 130 - "TrainingPage Delete Confirmation Tests"
Cohesion: 0.31
Nodes (3): Mission 062: TrainingPage.delete_training() now confirms before deleting,…, Mission 068: TrainingManager.delete() rolls back the Domain removal (and…, TrainingPageDeleteConfirmationTest

### Community 131 - "WorkflowsPage Delete Confirmation Tests"
Cohesion: 0.31
Nodes (3): Mission 062: WorkflowsPage.delete_workflow() now confirms before deleting,…, Mission 068: WorkflowManager.delete() rolls back the Domain removal (and…, WorkflowsPageDeleteConfirmationTest

### Community 133 - "Layered Architecture Principles"
Cohesion: 0.22
Nodes (9): Dependency Rule (dependencies never flow upward), Domain independent of Qt, Event Driven UI (EventBus-only page refresh), EventBus has no centralized event constants, Infrastructure ignorant of Domain (dict-only exchange), AI Studio Toolkit layered architecture (Presentation→Managers→Domain→Infrastructure→Core/EventBus), Managers never touch Qt widgets, PROJECT_CONTEXT.md consolidated project state (as of Mission 092) (+1 more)

### Community 134 - "ImportCollisionDialog Widget"
Cohesion: 0.25
Nodes (4): ImportCollisionDialog, QDialog, Mission 028 (second smoke test): shown once per import operation, never once…, Returns {source_path: chosen_name} for every collision the user chose to…

### Community 148 - "Blueprint Vision & Requirements Docs"
Cohesion: 0.32
Nodes (4): AI Orchestrator (never talks to engines directly), EventBus (src/core/event_bus.py), Managers layer (src/managers/), Forbidden folder names (misc/, temp/, new/, ...)

### Community 149 - "LoRA Library Save-Failure Tests"
Cohesion: 0.25
Nodes (3): LoRALibraryStorageError, Exception, Raised when the central LoRA library registry cannot be written to disk.

### Community 150 - "WorkspaceStorage rename_folder Errors"
Cohesion: 0.32
Nodes (3): Renames the workspace's root folder on disk — the one genuinely non-local…, Mission 027 real smoke test follow-up: WorkspaceStorage.rename_folder() must…, WorkspaceStorageRenameFolderErrorTest

### Community 166 - "Pre-Mission-059 Workflow Compatibility"
Cohesion: 0.43
Nodes (3): NoLoraProducesTheExactPreMission059WorkflowTest, patch, Mission 059's own compatibility proof: with lora_name unset (or explicitly ""),…

### Community 169 - "ComfyUI LoRA Selection Mission"
Cohesion: 0.40
Nodes (6): ComfyUI server-side discovery pattern (list_checkpoints/list_loras), Mission 056 - Typed Inference Reference Primitive, Mission 059 - ComfyUI LoRA Selection for Generation, _apply_lora(), Mission 059: inserts a native LoraLoader node ("11") between…, GenerationManager.generate()

### Community 170 - "requirements.txt Dependencies"
Cohesion: 0.33
Nodes (6): numpy dependency, opencv-python dependency, pillow dependency, pydantic dependency, PySide6 dependency, requirements.txt manifest

### Community 171 - "OllamaEngine HTTP Primitives"
Cohesion: 0.33
Nodes (3): Request, GET /api/tags — the models currently present on this Ollama instance (never a…, POST /api/generate with {"model": model, "prompt": prompt, "stream": false} — a…

### Community 172 - "comfyui_workflows Module & Tests"
Cohesion: 0.33
Nodes (4): _load_image_input(), Mission 023: pure ComfyUI workflow (API-format graph) construction — plain…, Translates the dict ComfyUIEngine.upload_image() (Mission 021) returns —…, Coverage for src/engines/workflows/comfyui_workflows.py — Mission 023's pure…

## Ambiguous Edges - Review These
- `docs/PROJECT_CONTEXT.md` → `MISSION_003.md — Dataset Domain`  [AMBIGUOUS]
  docs/PROJECT_CONTEXT.md · relation: references
- `Mission 092 - Direct Import to Central LoRA Library from Disk` → `Generation-Active Guard (isRunning() check)`  [AMBIGUOUS]
  docs/missions/MISSION_092.md · relation: conceptually_related_to

## Knowledge Gaps
- **17 isolated node(s):** `Root .claude/CLAUDE.md`, `graphify add-watch reference`, `graphify exports reference`, `Structural AST extraction (Part A)`, `graphify query BFS/DFS traversal with vocab expansion` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 972 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **84 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `docs/PROJECT_CONTEXT.md` and `MISSION_003.md — Dataset Domain`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Mission 092 - Direct Import to Central LoRA Library from Disk` and `Generation-Active Guard (isRunning() check)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `WorkspaceManager` connect `EventBus & Core Managers CRUD` to `Domain Model & Manager/Storage Modules`, `LoRA/Model Rollback Test Suites`, `Dataset Gallery Sort & Import Tests`, `Characters/Dashboard/Images Pages`, `Domain Serialization & Deletion Results`, `Settings Discovery Tests`, `InferencePage Generation & Reference Tests`, `MainWindow Dirty-State Guard Tests`, `WorkspaceStorage Copy/Collision Primitives`, `TrainingManager/TrainingPage CRUD`, `InferencePage Pending Result Guard Tests`, `PromptManager Round-Trip Tests`, `ApplicationSettings Domain & Round-Trip`, `LoRAPage Dirty-State & Persistence Tests`, `LoRAPage Central Library Tab Tests`, `MainWindow Entry Point & Settings Tests`, `PromptsPage Persistence Failure Tests`, `DatasetManager/DatasetsPage Round-Trip`, `LoRAManager Thumbnail Tests`, `Settings Domain & SettingsPage Tests`, `SettingsPage Save/Confirm Tests`, `LoRA Round-Trip Tests`, `WorkspaceManager add_images Copy Tests`, `PromptsPage Widget & Context Change`, `TrainingPage Delete & Round-Trip Tests`, `Model Domain & ModelManager`, `ImagesPage Delete Tests`, `WorkflowsPage/WorkflowManager Round-Trip`, `WorkspaceManager.rename() Tests`, `Workflow Domain & WorkflowManager`, `ModelsPage Widget & Persistence Tests`, `MainWindow Rename Generation Guard Tests`, `CharactersPage Dirty-State Tests`, `ModelManager/ModelsPage Round-Trip`, `WorkspaceManager remove_images Tests`, `Prompt Domain & PromptManager`, `DatasetsPage Collision & Persistence`, `TrainingPage Rename & Sort Tests`, `DatasetManager add_images Copy Tests`, `ImagesPage Gallery Sort Tests`, `SettingsPage Dirty-State Tests`, `SettingsManager Update Rollback Tests`, `WorkflowsPage Widget & Persistence`, `CharactersPage Identity Fiche Tests`, `LoRAPage Add-to-Central-Library Tests`, `DatasetsPage Delete Confirmation Tests`, `ImagesPage Import Persistence Tests`, `LoRAManager Physical Deletion Tests`, `LoRAManager remove_files Tests`, `CharacterManager Update Tests`, `DatasetManager Physical Deletion Tests`, `InferencePage Generation-Active Guard`, `LoRAPage Rename Tests`, `NewProjectDialog Widget`, `DatasetManager remove_images Tests`, `DatasetManager Rename Tests`, `ImagesPage Selection Preservation Tests`, `LoRAManager Rename Tests`, `LoRAPage Delete Confirmation Tests`, `ModelsPage Rename Tests`, `PromptsPage Delete Button State Tests`, `PromptsPage Rename Tests`, `CharacterManager Auto-Create Tests`, `LoRAPage Files Selection Tests`, `New/Open Project Generation Guard`, `ModelsPage Delete Confirmation Tests`, `TrainingPage Delete Confirmation Tests`, `WorkflowsPage Delete Confirmation Tests`, `WorkflowsPage Rename Tests`, `CharacterManager Update Rollback Tests`, `DatasetManager Delete Rollback Tests`, `DatasetManager remove_images Rollback`, `ImagesPage Collision Dialog Tests`, `LoRAManager add_files Rollback Tests`, `LoRAManager remove_files Rollback Tests`, `LoRAPage Delete Button State Tests`, `ModelsPage Sort Tests`, `PromptsPage Confirm Context Change`, `PromptsPage Sort Tests`, `WorkflowsPage Sort Tests`, `WorkflowManager Scalar Rollback Tests`, `CharacterManager Create Rollback Tests`, `CharactersPage Identity Persistence`, `DatasetManager Create Rollback Tests`, `DatasetManager Rename Rollback Tests`, `LoRAManager Delete Rollback Tests`, `LoRAPage Sort Tests`, `ModelManager Create Rollback Tests`, `PromptManager Delete Rollback Tests`, `SettingsPage Persistence Failure Tests`, `TrainingManager Delete Rollback Tests`, `WorkflowManager Create Rollback Tests`, `TrainingManager Rename Rollback Tests`, `DatasetManager Character-Independence`, `WorkflowsPage File-Path Persistence`, `LoRAPage Create Persistence Tests`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Why does `WorkspaceStorageError` connect `LoRA/Model Rollback Test Suites` to `EventBus & Core Managers CRUD`, `Domain Model & Manager/Storage Modules`, `ModelsPage Delete Confirmation Tests`, `TrainingPage Delete Confirmation Tests`, `WorkflowsPage Delete Confirmation Tests`, `WorkflowsPage Rename Tests`, `Characters/Dashboard/Images Pages`, `Domain Serialization & Deletion Results`, `CharacterManager Update Rollback Tests`, `DatasetManager Delete Rollback Tests`, `DatasetManager remove_images Rollback`, `InferencePage Generation & Reference Tests`, `LoRAManager add_files Rollback Tests`, `WorkspaceStorage Copy/Collision Primitives`, `LoRAManager remove_files Rollback Tests`, `MainWindow Dirty-State Guard Tests`, `PromptsPage Confirm Context Change`, `PromptsPage Persistence Failure Tests`, `InferencePage Pending Result Guard Tests`, `PromptManager Round-Trip Tests`, `TrainingManager/TrainingPage CRUD`, `Central LoRA Library Manager`, `WorkspaceStorage rename_folder Errors`, `CharacterManager Create Rollback Tests`, `CharactersPage Identity Persistence`, `LoRAPage Central Library Tab Tests`, `LoRAPage Dirty-State & Persistence Tests`, `DatasetManager Create Rollback Tests`, `DatasetManager Rename Rollback Tests`, `DatasetManager/DatasetsPage Round-Trip`, `LoRAManager Delete Rollback Tests`, `LoRAManager Thumbnail Tests`, `Central Library Delete Confirmation`, `ModelManager Create Rollback Tests`, `MainWindow CloseEvent Real-State Tests`, `LoRA Round-Trip Tests`, `App/LoRA Library Storage Tests`, `WorkspaceStorage Copy/IsInside Tests`, `PromptManager Delete Rollback Tests`, `LoRALibraryManager Delete/Update Tests`, `SettingsPage Save/Confirm Tests`, `SettingsPage Persistence Failure Tests`, `TrainingManager Delete Rollback Tests`, `TrainingManager Rename Rollback Tests`, `ImagesPage Delete Tests`, `WorkflowManager Create Rollback Tests`, `WorkspaceManager add_images Copy Tests`, `MainWindow Rename Pending Guard Tests`, `WorkflowsPage File-Path Persistence`, `LoRAPage Create Persistence Tests`, `WorkspaceManager.rename() Tests`, `ModelsPage Widget & Persistence Tests`, `MainWindow Rename Generation Guard Tests`, `CharactersPage Dirty-State Tests`, `WorkspaceManager remove_images Tests`, `DatasetsPage Collision & Persistence`, `TrainingPage Rename & Sort Tests`, `LoRALibraryManager Import Tests`, `DatasetManager add_images Copy Tests`, `SettingsPage Dirty-State Tests`, `SettingsManager Update Rollback Tests`, `WorkflowsPage Widget & Persistence`, `LoRAPage Add-to-Central-Library Tests`, `DatasetsPage Delete Confirmation Tests`, `ImagesPage Import Persistence Tests`, `LoRAManager Physical Deletion Tests`, `DatasetManager Physical Deletion Tests`, `WorkflowManager Scalar Rollback Tests`, `LoRAPage Rename Tests`, `LoRAPage Delete Confirmation Tests`, `ModelsPage Rename Tests`, `PromptsPage Rename Tests`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow Entry Point & Settings Tests` to `EventBus & Core Managers CRUD`, `Domain Model & Manager/Storage Modules`, `New/Open Project Generation Guard`, `SelectImagesDialog & Sidebar/Thumbnails`, `Characters/Dashboard/Images Pages`, `MainWindow Dirty-State Guard Tests`, `InferencePage Pending Result Protection`, `OllamaEngine HTTP Client & Tests`, `AIBackend Protocol & PromptAssistantManager`, `TrainingManager/TrainingPage CRUD`, `ComfyUIEngine HTTP Client & Tests`, `ApplicationSettings Domain & Round-Trip`, `Central LoRA Library Manager`, `LoRAPage Widget & Central Import`, `Settings Domain & SettingsPage Tests`, `SettingsPage Save/Confirm Tests`, `MainWindow CloseEvent Real-State Tests`, `App/LoRA Library Storage Tests`, `ImagePreviewDialog Fullscreen Tests`, `ComfyUI LoRA Selection Mission`, `requirements.txt Dependencies`, `Model Domain & ModelManager`, `PromptsPage Widget & Context Change`, `MainWindow Rename Pending Guard Tests`, `MainMenuBar Widget`, `Workflow Domain & WorkflowManager`, `Create/Delete Rollback Family Overview`, `MainStatusBar Widget`, `ModelsPage Widget & Persistence Tests`, `MainToolBar Widget`, `MainWindow Rename Generation Guard Tests`, `Prompt Domain & PromptManager`, `NewProject/RenameProject Dialog Widgets`, `MainWindow CloseEvent Orchestration Tests`, `DatasetsPage Widget (Gallery/CRUD)`, `WorkflowsPage Widget & Persistence`, `Transactional Safety Pattern Timeline`, `MainWindow Prompts-to-Inference Tests`, `Central LoRA Library Mission Timeline`, `GenerationManager LoRA Forwarding Tests`, `NewProjectDialog Widget`, `DashboardPage Widget Tests`, `MainToolBar Widget Tests`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Are the 85 inferred relationships involving `WorkspaceStorageError` (e.g. with `DatasetManager` and `LoRALibraryManager`) actually correct?**
  _`WorkspaceStorageError` has 85 INFERRED edges - model-reasoned connections that need verification._
- **Are the 138 inferred relationships involving `WorkspaceManager` (e.g. with `CharacterManager` and `DatasetManager`) actually correct?**
  _`WorkspaceManager` has 138 INFERRED edges - model-reasoned connections that need verification._