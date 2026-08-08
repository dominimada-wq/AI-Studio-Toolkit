# AI Studio Toolkit

**Document:** 03_PROJECT_STRUCTURE.md

**Version:** 1.0

**Status:** Draft

Related Documents

00_VISION.md

01_PRODUCT_REQUIREMENTS.md

02_ARCHITECTURE.md

---

# 1. Purpose

This document defines the official repository structure.

Every source file must belong to a defined location.

Developers must never create arbitrary folders.

The structure defined here is mandatory.

---

# 2. Repository Structure

AI-Studio-Toolkit/

├── docs/

├── src/

├── tests/

├── assets/

├── examples/

├── scripts/

├── config/

├── resources/

├── plugins/

├── models/

├── datasets/

├── outputs/

├── cache/

├── logs/

├── .github/

├── README.md

├── CHANGELOG.md

├── LICENSE

├── pyproject.toml

└── requirements.txt

---

# 3. Source Folder

The source folder contains application code only.

src/

├── core/

├── domain/

├── infrastructure/

├── managers/

├── services/

├── engines/

├── plugins/

├── ui/

├── resources/

└── utils/

---

# 4. Core

Contains application foundation.

Examples

Application

EventBus

Configuration

Dependency Injection

Command Dispatcher

Lifecycle

---

# 5. Domain

Contains business objects.

Workspace

Character

Dataset

Prompt

Model

LoRA

Job

History

KnowledgeBase

Asset

Workflow

Version

These classes must remain independent from Qt.

---

# 6. Managers

Managers coordinate application workflows.

WorkspaceManager

CharacterManager

DatasetManager

ModelManager

LoRAManager

WorkflowManager

PromptManager

GenerationManager

TrainingManager

VideoManager

SettingsManager

JobManager

HistoryManager

PluginManager

CloudManager

---

# 7. Services

Business operations.

Examples

ImportService

ExportService

GenerationService

TrainingService

CaptionService

ValidationService

StorageService

BackupService

CacheService

UpdateService

Services never know the UI.

---

# 8. Engines

Engine abstraction layer.

ComfyUI

Forge

Automatic1111

Fooocus

OneTrainer

Kohya

GPT Image

fal.ai

Nano Banana

Kling

Seedance

Seedream

Higgsfield

Each engine implements a common interface.

---

# 9. Plugins

Every engine plugin lives inside

src/plugins/

Each plugin contains

plugin.py

configuration.py

engine.py

metadata.py

icons/

templates/

---

# 10. UI

src/ui/

contains

Main Window

Pages

Widgets

Dialogs

Toolbars

Menus

Dock Widgets

Themes

Icons

No business logic belongs here.

---

# 11. Tests

tests/

├── unit/

├── integration/

├── ui/

├── engines/

└── performance/

Every new feature should include tests whenever practical.

---

# 12. Assets

assets/

contains

Icons

Fonts

Images

Themes

Translations

Templates

---

# 13. Models

models/

contains shared AI resources.

Checkpoints

LoRA

VAE

Embeddings

ControlNet

IPAdapter

Upscalers

Clip Vision

Resources remain shared between Workspaces.

---

# 14. Datasets

datasets/

contains imported datasets.

Future versions may allow shared datasets.

---

# 15. Outputs

outputs/

contains generated files.

Images

Videos

Exports

Reports

Archives

---

# 16. Configuration

config/

contains

Application settings

Engine settings

Plugin settings

Templates

Default values

---

# 17. Documentation

docs/

contains

Blueprint

API

Developer Guide

User Guide

Architecture Decision Records

RFC

Images

---

# 18. Scripts

scripts/

contains

Utilities

Migration tools

Packaging

Maintenance

Benchmark

Automation

---

# 19. GitHub

.github/

contains

CI

Issue templates

Pull Request templates

Actions

Release workflow

---

# 20. Naming Convention

Python files

snake_case.py

Classes

PascalCase

Methods

snake_case()

Constants

UPPER_CASE

Qt Signals

snake_case

---

# 21. Maximum File Size

Recommended limits

Manager

< 400 lines

Service

< 400 lines

Widget

< 300 lines

Plugin

< 500 lines

Split files when necessary.

---

# 22. Forbidden

Never create

misc/

temp/

new/

test2/

backup/

old/

random/

All folders must be documented.

---

# 23. Future Growth

The repository should remain organized even after

1000 Python files

100 plugins

100 Characters

Millions of generated assets

---

# 24. Golden Rule

Repository organization is part of the architecture.

Whenever a new folder becomes necessary, this document must be updated first.

---

End of document.