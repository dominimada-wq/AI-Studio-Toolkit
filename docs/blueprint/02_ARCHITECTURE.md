# AI Studio Toolkit

**Document:** 02_ARCHITECTURE.md

**Version:** 1.0

**Status:** Draft

**Related Documents**
- 00_VISION.md
- 01_PRODUCT_REQUIREMENTS.md

---

# 1. Purpose

This document defines the software architecture of AI Studio Toolkit.

It specifies the organization of the application, the responsibilities of each layer, the dependencies allowed between modules and the architectural rules that every implementation must follow.

Every future development must remain compatible with this architecture.

---

# 2. Architectural Principles

The application follows five fundamental principles.

## Separation of Concerns

Each component has one responsibility.

User Interface never contains business logic.

Business logic never manipulates Qt widgets.

Storage never depends on the UI.

---

## Dependency Direction

Dependencies always flow downward.

UI

↓

Managers

↓

Services

↓

Domain

↓

Infrastructure

↓

External Engines

No lower layer may depend on an upper layer.

---

## Single Source of Truth

Every object exists only once.

There must never be two independent representations of the same Character, Workspace or Job.

---

## Extensibility

Every AI engine must be replaceable.

Adding a new engine must require only a new Plugin implementation.

---

## Testability

Every Manager and Service must be testable without starting the GUI.

---

# 3. High-Level Architecture

```text
Presentation Layer

↓

Application Layer

↓

Domain Layer

↓

Infrastructure Layer

↓

External Engines
```

---

# 4. Layer Responsibilities

## Presentation Layer

Contains:

- MainWindow
- Pages
- Dialogs
- Widgets
- Toolbars
- Menus

Responsibilities:

- Display information
- Collect user input
- Emit commands

Must never:

- Read files
- Launch training
- Generate images
- Call APIs directly

---

## Application Layer

Contains Managers.

Responsibilities:

- Coordinate workflows
- Manage state
- Dispatch commands
- Validate actions

Managers never access Qt widgets.

---

## Domain Layer

Contains business objects.

Examples:

Workspace

Character

Dataset

Model

LoRA

Prompt

Workflow

Job

History

KnowledgeBase

Settings

These classes contain business rules only.

---

## Infrastructure Layer

Responsible for:

Storage

Configuration

Logging

Cache

Serialization

Plugin loading

Subprocess execution

API communication

---

## Engine Layer

Represents external systems.

Examples

ComfyUI

Fooocus

Forge

AUTOMATIC1111

OneTrainer

Kohya_ss

GPT Image 2

fal.ai

Nano Banana

Kling

Seedance

Seedream

Higgsfield

---

# 5. Main Domains

Workspace

Character

Library

Training

Generation

Video

Jobs

Plugins

Infrastructure

Each domain owns its data and business rules.

---

# 6. Managers

The application layer contains the following managers.

WorkspaceManager

CharacterManager

DatasetManager

ModelManager

LoRAManager

PromptManager

WorkflowManager

TrainingManager

GenerationManager

VideoManager

JobManager

PluginManager

HistoryManager

SettingsManager

CloudManager

BackupManager

Managers coordinate services.

Managers never implement heavy processing.

---

# 7. Services

Services implement business operations.

Examples

ImportService

ExportService

GenerationService

TrainingService

CaptionService

PublishService

ValidationService

StorageService

UpdateService

BackupService

CacheService

Services are reusable.

Services never manipulate Qt widgets.

---

# 8. Plugin System

Every engine is a plugin.

Examples

ComfyUIPlugin

FooocusPlugin

ForgePlugin

Automatic1111Plugin

OneTrainerPlugin

KohyaPlugin

GPTImagePlugin

FalPlugin

NanoBananaPlugin

KlingPlugin

SeedancePlugin

SeedreamPlugin

HiggsfieldPlugin

Plugins expose a common interface.

The UI must never know which engine is used internally.

---

# 9. AI Orchestrator

Every generation request follows the same path.

User

↓

Page

↓

Manager

↓

Service

↓

AI Orchestrator

↓

Plugin

↓

Engine

↓

Result

The orchestrator selects the correct plugin.

---

# 10. Workspace Architecture

Workspace

├── Characters

├── Shared Models

├── Shared LoRAs

├── Shared Workflows

├── Shared Prompts

├── Assets

├── Outputs

├── Logs

├── Jobs

└── Settings

Everything belongs to one Workspace.

---

# 11. Character Architecture

Character

├── Identity

├── References

├── Datasets

├── LoRAs

├── Prompts

├── Workflows

├── Knowledge Base

├── Training History

├── Generation History

└── Metadata

Characters are completely independent.

---

# 12. Library System

Libraries are shared across the Workspace.

Checkpoint Library

LoRA Library

Workflow Library

Prompt Library

Embedding Library

ControlNet Library

IPAdapter Library

Upscaler Library

---

# 13. Job System

Every long operation becomes a Job.

Job States

Queued

Running

Paused

Completed

Cancelled

Failed

Jobs are persistent.

They survive application restart.

---

# 14. Event Bus

The application communicates through events.

Examples

WorkspaceOpened

WorkspaceClosed

CharacterCreated

CharacterDeleted

DatasetImported

TrainingStarted

TrainingFinished

GenerationStarted

GenerationFinished

VideoGenerated

SettingsChanged

Pages subscribe to events.

Pages do not communicate directly.

---

# 15. Persistence

All persistent data is stored in JSON files during the first versions.

Future versions may migrate to SQLite.

Storage implementation must remain abstract.

---

# 16. Configuration

Configuration is divided into:

Global Settings

Workspace Settings

Character Settings

Engine Settings

Plugin Settings

No configuration file should contain unrelated settings.

---

# 17. Logging

The application must provide centralized logging.

Levels

Debug

Info

Warning

Error

Critical

Logs are written to disk and displayed in the UI.

---

# 18. Error Handling

Errors must never crash the application silently.

Every exception must:

- be logged
- be reported to the user
- contain diagnostic information
- allow recovery when possible

---

# 19. Dependency Rules

Allowed

UI → Managers

Managers → Services

Services → Domain

Services → Infrastructure

Infrastructure → Plugins

Plugins → Engines

Forbidden

UI → Services

UI → Plugins

Managers → Qt Widgets

Plugins → UI

Domain → Qt

---

# 20. Future Architecture

The architecture must support future features without redesign.

Examples

Multi-user mode

Cloud synchronization

Plugin Marketplace

REST API

Headless mode

Remote rendering

Distributed training

AI Assistants

---

# 21. Architectural Decisions

Every important architectural modification must be documented through an ADR (Architecture Decision Record).

No structural modification should occur without updating both:

- 00_VISION.md
- 02_ARCHITECTURE.md

---

# 22. Golden Rule

The architecture exists to protect the project from uncontrolled growth.

Whenever implementation and architecture disagree, the architecture must be reviewed before modifying the code.

---

End of document.