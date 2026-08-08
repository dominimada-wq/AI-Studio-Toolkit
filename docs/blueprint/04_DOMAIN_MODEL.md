# AI Studio Toolkit

**Document:** 04_DOMAIN_MODEL.md

**Version:** 1.0

**Status:** Draft

**Related Documents**

- 00_VISION.md
- 01_PRODUCT_REQUIREMENTS.md
- 02_ARCHITECTURE.md
- 03_PROJECT_STRUCTURE.md

---

# 1. Purpose

This document defines the complete business domain of AI Studio Toolkit.

Unlike the Architecture document, this document focuses on the business objects manipulated by the application.

Every future implementation must respect this domain model.

The domain model is the single source of truth for every object manipulated by the application.

---

# 2. Domain Philosophy

The software is built around digital characters.

Everything else exists to create, improve, organize or publish these characters.

Characters are first-class citizens.

Images are not.

Videos are not.

LoRAs are not.

Characters own these resources.

---

# 3. Core Business Objects

The application is built around the following business objects.

Workspace

Character

Dataset

Image

Video

Model

Checkpoint

LoRA

Prompt

Workflow

Job

Generation

Training

Publication

Knowledge Base

Plugin

Engine

Settings

Cloud Account

Asset

History

Version

Every business feature must belong to one of these objects.

---

# 4. Entity Hierarchy

Workspace

└── Characters

    ├── Datasets

    ├── Images

    ├── Videos

    ├── LoRAs

    ├── Generations

    ├── Trainings

    ├── Prompt Library

    ├── Knowledge Base

    └── History

Workspace also owns shared resources.

Shared Models

Shared Workflows

Shared Prompts

Shared Assets

Shared Plugins

Shared Engine Configuration

---

# 5. Workspace

## Description

A Workspace represents an entire production environment.

Everything belongs to a Workspace.

Nothing exists outside a Workspace.

---

## Responsibilities

Store every project resource.

Manage shared resources.

Manage global settings.

Manage AI engines.

Manage plugins.

Manage cloud accounts.

Manage outputs.

Manage logs.

Manage backups.

---

## Attributes

Workspace ID

Workspace Name

Description

Author

Company

Version

Creation Date

Last Modified

Workspace Path

Workspace Icon

Default Language

Default Theme

Preferred AI Engine

Preferred Image Engine

Preferred Video Engine

Preferred Training Engine

Settings

Metadata

Tags

Notes

---

## Relationships

Workspace

↓

Characters

↓

Generations

↓

Outputs

Workspace

↓

Shared Models

↓

Characters

Workspace

↓

Plugins

↓

Engines

---

## Events

WorkspaceCreated

WorkspaceOpened

WorkspaceSaved

WorkspaceClosed

WorkspaceDeleted

WorkspaceArchived

WorkspaceRestored

WorkspaceExported

WorkspaceImported

---

# 6. Character

## Description

A Character represents a digital human.

The Character is the most important entity in the software.

Every image, dataset, LoRA, workflow or prompt ultimately belongs to a Character.

Characters evolve over time.

The application tracks this evolution.

---

## Responsibilities

Maintain identity.

Maintain visual consistency.

Manage datasets.

Manage prompts.

Manage LoRAs.

Manage history.

Manage versions.

Store metadata.

Store production knowledge.

---

## Identity

Character ID

Display Name

Internal Name

Description

Biography

Gender

Age

Nationality

Languages

Occupation

Personality

Voice Description

Social Media Identity

Brand

---

## Physical Appearance

Height

Weight

Body Type

Skin Tone

Face Shape

Hair Style

Hair Color

Eye Color

Eyebrows

Eyelashes

Lips

Teeth

Freckles

Scars

Birth Marks

Tattoos

Piercings

Body Proportions

Dominant Features

Distinctive Features

---

## Visual Identity

Master Prompt

Negative Prompt

Reference Images

Reference Videos

Identity Rules

Consistency Rules

Pose Library

Expression Library

Outfit Library

Accessory Library

Location Library

Lighting Library

Style Library

Color Palette

---

## AI Resources

Datasets

Training Sessions

LoRAs

Embeddings

Favorite Models

Favorite Engines

Favorite Workflows

Favorite Prompts

Generation Presets

Video Presets

---

## Production

Images

Videos

Generated Assets

Published Assets

Rejected Assets

Archived Assets

Exports

---

## Metadata

Author

Creation Date

Modification Date

Current Version

Previous Versions

Status

Favorite

Archived

Rating

Quality Score

Tags

Custom Properties

Notes

---

## Knowledge Base

Best Prompt

Best Negative Prompt

Best LoRA

Best Engine

Best Parameters

Best Workflow

Best Model

Known Issues

Recommended Settings

Training Notes

Generation Notes

Video Notes

---

## Relationships

Character

↓

Dataset

↓

Training

↓

LoRA

↓

Generation

↓

Publication

Character

↓

Prompt Library

Character

↓

History

Character

↓

Knowledge Base

---

## Events

CharacterCreated

CharacterUpdated

CharacterDeleted

CharacterArchived

CharacterRestored

CharacterDuplicated

CharacterVersionCreated

CharacterVersionRestored

CharacterPublished

---

## Business Rules

A Character belongs to exactly one Workspace.

A Character owns multiple Datasets.

A Character owns multiple LoRAs.

A Character owns multiple Images.

A Character owns multiple Videos.

A Character may use shared Models.

A Character may use shared Workflows.

Characters must never share identity.
---

# 7. Dataset

## Description

A Dataset is a structured collection of reference images used for training AI models.

Datasets belong to one Character.

Datasets may evolve over time.

Previous versions remain available.

---

## Responsibilities

Store reference images.

Store captions.

Measure dataset quality.

Prepare training.

Export training packages.

Maintain statistics.

Track dataset history.

---

## Attributes

Dataset ID

Name

Description

Character ID

Version

Author

Creation Date

Modification Date

Status

Training Engine

Compatible Models

Image Count

Caption Count

Resolution Statistics

Quality Score

Duplicate Count

Blur Score

Metadata

Notes

Tags

---

## Dataset Structure

Dataset

├── Images

├── Captions

├── Masks

├── Metadata

├── Statistics

├── Reports

└── History

---

## Relationships

Character

↓

Datasets

↓

Images

↓

Captions

---

## Events

DatasetCreated

DatasetImported

DatasetValidated

DatasetUpdated

DatasetDeleted

DatasetExported

DatasetArchived

---

## Business Rules

Every Dataset belongs to one Character.

Datasets are immutable after publication.

Images cannot belong to multiple Datasets.

---

# 8. Image

## Description

Represents a single image.

Images may be:

Reference Images

Generated Images

Training Images

Output Images

Published Images

---

## Attributes

Image ID

Character ID

Dataset ID

Generation ID

Width

Height

Aspect Ratio

File Format

Bit Depth

Creation Date

Camera Metadata

Prompt

Negative Prompt

Seed

Sampler

Steps

CFG

Engine

Model

LoRA List

Workflow

Rating

Favorite

Archived

Tags

Notes

---

## Relationships

Character

↓

Image

↓

Generation

---

## Events

ImageImported

ImageGenerated

ImageDeleted

ImageArchived

ImageRated

ImagePublished

---

# 9. Video

## Description

Represents a generated or imported video.

---

## Supported Providers

Kling

Seedance

Seedream

Higgsfield

Future Providers

---

## Attributes

Video ID

Character

Provider

Duration

Resolution

FPS

Codec

Prompt

Image Source

Workflow

Status

Generation Date

Rating

Favorite

Tags

Metadata

Notes

---

## Events

VideoCreated

VideoGenerated

VideoImported

VideoDeleted

VideoPublished

---

# 10. Model

## Description

Represents any reusable AI model.

---

## Types

Checkpoint

LoRA

Embedding

VAE

ControlNet

IPAdapter

Upscaler

Clip Vision

Future Types

---

## Attributes

Model ID

Name

Display Name

Version

Provider

Author

Engine

Architecture

Compatibility

License

File Size

Hash

Thumbnail

Description

Tags

Installation Path

---

## Relationships

Workspace

↓

Models

↓

Characters

---

## Events

ModelImported

ModelUpdated

ModelDeleted

ModelIndexed

---

# 11. Checkpoint

Checkpoint is a specialization of Model.

Additional Attributes

Base Model

Training Dataset

Resolution

Recommended Sampler

Recommended CFG

Recommended Scheduler

Recommended LoRA Weight

Compatible Engines

---

# 12. LoRA

## Description

Represents a trainable AI adaptation.

---

## Attributes

LoRA ID

Name

Version

Engine

Architecture

Trigger Word

Activation Weight

Training Engine

Training Date

Training Duration

Epochs

Optimizer

Learning Rate

Batch Size

Compatible Models

Compatible Engines

Recommended Weight

Metadata

Evaluation Score

Quality Notes

---

## Relationships

Character

↓

LoRA

↓

Training Session

---

## Events

LoRACreated

LoRAImported

LoRATrained

LoRAUpdated

LoRAArchived

LoRADeleted

---

# 13. Prompt

## Description

Represents reusable prompt definitions.

---

## Types

Master Prompt

Negative Prompt

Generation Prompt

Training Prompt

Video Prompt

Template Prompt

Dynamic Prompt

---

## Attributes

Prompt ID

Title

Category

Text

Variables

Tags

Favorite

Rating

Version

Author

Creation Date

Last Modified

---

## Relationships

Character

↓

Prompt Library

↓

Generation

---

## Events

PromptCreated

PromptEdited

PromptDeleted

PromptApplied

---

# 14. Workflow

## Description

Represents reusable production pipelines.

---

## Supported Types

ComfyUI Workflow

Forge Preset

Fooocus Preset

Training Pipeline

Publishing Pipeline

Video Pipeline

---

## Attributes

Workflow ID

Name

Description

Compatible Engine

Inputs

Outputs

Parameters

Version

Category

Author

Thumbnail

Tags

Metadata

---

## Relationships

Workspace

↓

Workflow Library

↓

Characters

---

## Events

WorkflowCreated

WorkflowImported

WorkflowUpdated

WorkflowDeleted

WorkflowExecuted

---

# 15. Generation

## Description

Represents one image generation task.

---

## Attributes

Generation ID

Character

Engine

Model

LoRAs

Prompt

Negative Prompt

Seed

Width

Height

Sampler

Scheduler

CFG

Steps

Generation Time

GPU Used

Status

Result Images

Logs

---

## Events

GenerationStarted

GenerationFinished

GenerationCancelled

GenerationFailed

---

# 16. Training

## Description

Represents a LoRA training session.

---

## Supported Engines

OneTrainer

Kohya_ss

Future Trainers

---

## Attributes

Training ID

Character

Dataset

Output LoRA

Engine

Base Model

Epochs

Learning Rate

Optimizer

Batch Size

Resolution

Start Time

End Time

Duration

Loss

GPU

VRAM

Logs

Artifacts

---

## Events

TrainingStarted

TrainingPaused

TrainingResumed

TrainingFinished

TrainingCancelled

TrainingFailed

---

End of Part 2.
---

# 17. Job

## Description

A Job represents any long-running operation executed by AI Studio Toolkit.

Jobs are managed by the Job Manager.

Every operation requiring more than a few seconds should be executed as a Job.

Jobs survive application restart whenever technically possible.

---

## Job Types

Image Generation

Video Generation

LoRA Training

Dataset Import

Dataset Export

Caption Generation

Model Scan

Workspace Backup

Workspace Restore

Publication

Plugin Installation

Update Check

Custom Job

---

## Attributes

Job ID

Job Name

Job Type

Priority

Status

Progress

Owner

Character

Workspace

Engine

Plugin

Created At

Started At

Finished At

Duration

Cancellation Allowed

Retry Count

Logs

Result

Error Message

Metadata

---

## Status

Queued

Waiting

Running

Paused

Completed

Cancelled

Failed

---

## Events

JobQueued

JobStarted

JobPaused

JobResumed

JobCompleted

JobCancelled

JobFailed

JobRemoved

---

## Business Rules

Jobs are immutable after completion.

Completed Jobs remain visible in History.

Jobs may produce Assets.

Jobs belong to one Workspace.

---

# 18. Engine

## Description

An Engine represents any AI backend capable of executing AI tasks.

The application communicates only with the Engine abstraction.

Never with the engine directly.

---

## Engine Categories

Image Engine

Video Engine

Training Engine

Caption Engine

Publishing Engine

Cloud Engine

---

## Supported Engines

ComfyUI

AUTOMATIC1111

WebUI Forge

Fooocus

OneTrainer

Kohya_ss

GPT Image 2

fal.ai

Nano Banana

Kling

Seedance

Seedream

Higgsfield

Future Engines

---

## Attributes

Engine ID

Name

Version

Category

Provider

Local / Cloud

Status

Capabilities

Configuration

Installed

Enabled

Default

Executable Path

API Endpoint

Authentication

Metadata

---

## Capabilities

Generate Images

Generate Videos

Train LoRA

Upscale

Caption

ControlNet

IPAdapter

Batch Processing

Streaming

Cloud Execution

---

## Events

EngineInstalled

EngineRemoved

EngineStarted

EngineStopped

EngineUpdated

EngineUnavailable

---

# 19. Plugin

## Description

Plugins extend AI Studio Toolkit.

Every Engine is delivered through a Plugin.

Future features should also be implemented as Plugins whenever appropriate.

---

## Attributes

Plugin ID

Plugin Name

Version

Author

Description

Category

Compatible Application Version

Dependencies

License

Website

Documentation

Enabled

Installed

Configuration

Metadata

---

## Plugin Categories

Engine Plugin

UI Plugin

Import Plugin

Export Plugin

Workflow Plugin

Cloud Plugin

Training Plugin

Automation Plugin

Future Plugin

---

## Events

PluginInstalled

PluginUpdated

PluginEnabled

PluginDisabled

PluginRemoved

---

# 20. Knowledge Base

## Description

Each Character owns a Knowledge Base.

The Knowledge Base records everything learned during production.

It continuously improves recommendations.

---

## Content

Best Prompts

Best Negative Prompts

Best Models

Best LoRAs

Best Engines

Best Parameters

Best Workflows

Known Problems

Recommended Fixes

Successful Experiments

Failed Experiments

Preferred Styles

Preferred Lighting

Preferred Camera Angles

Preferred Clothing

Preferred Expressions

---

## Events

KnowledgeUpdated

RecommendationAdded

RecommendationRemoved

---

# 21. History

## Description

History stores every important action.

Nothing important should disappear.

History enables traceability.

---

## Recorded Events

Workspace

Character

Dataset

Training

Generation

Video

Publication

Plugin

Settings

Engine

Import

Export

Backup

Restore

---

## Attributes

History ID

Timestamp

User

Action

Target

Category

Description

Metadata

---

# 22. Publication

## Description

Represents publication of generated media.

Publication targets may evolve over time.

---

## Supported Targets

Instagram

TikTok

Facebook

X

YouTube

Future Platforms

---

## Attributes

Publication ID

Target Platform

Character

Media

Caption

Hashtags

Publication Date

Status

URL

Statistics

---

## Events

PublicationCreated

PublicationPublished

PublicationFailed

PublicationRemoved

---

# 23. Asset

## Description

Assets represent reusable production resources.

---

## Asset Types

Image

Video

Audio

PSD

Prompt

Workflow

Template

Thumbnail

Document

Archive

---

## Attributes

Asset ID

Name

Category

Location

Checksum

Preview

Metadata

Tags

Version

---

# 24. Version

## Description

Version represents a snapshot of a business object.

Characters

Datasets

LoRAs

Workflows

Projects

may all be versioned.

---

## Attributes

Version ID

Object ID

Object Type

Version Number

Created At

Author

Description

Parent Version

---

## Events

VersionCreated

VersionRestored

VersionDeleted

---

# 25. Settings

## Description

Represents configuration data.

Settings exist at several levels.

---

## Levels

Application

Workspace

Character

Engine

Plugin

User Interface

Training

Generation

Video

Cloud

---

## Attributes

Setting ID

Category

Key

Value

Default Value

Type

Validation Rules

Visibility

---

## Events

SettingChanged

SettingReset

SettingImported

SettingExported

---

# 26. Cloud Account

## Description

Represents an authenticated cloud service.

---

## Supported Providers

OpenAI

fal.ai

Kling

Higgsfield

Seedance

Seedream

Future Providers

---

## Attributes

Account ID

Provider

Display Name

API Key Reference

Endpoint

Quota

Usage

Status

Last Validation

Metadata

---

## Events

CloudAccountAdded

CloudAccountValidated

CloudAccountUpdated

CloudAccountRemoved

---

# 27. Domain Relationships

Workspace

↓

Characters

↓

Datasets

↓

Training

↓

LoRAs

↓

Generation

↓

Images

↓

Videos

↓

Publication

Workspace

↓

Shared Libraries

↓

Models

↓

Workflows

↓

Prompts

↓

Plugins

↓

Engines

---

# 28. Domain Invariants

A Character belongs to exactly one Workspace.

A Dataset belongs to exactly one Character.

A Job belongs to exactly one Workspace.

A LoRA belongs to exactly one Character.

Models belong to the Workspace Library.

Plugins are global.

Engines are accessed only through Plugins.

Business objects never depend on Qt.

---

# 29. Domain Events

The Domain Layer communicates using events.

Business objects never communicate directly.

All notifications pass through the Event Bus.

---

# 30. Claude Implementation Notes

Each business object should be implemented as an independent Python class.

Recommended package:

src/domain/

Each class should:

- expose a clean public API
- avoid Qt dependencies
- support serialization
- support validation
- emit domain events through services
- remain unit-testable

Future persistence may migrate from JSON to SQLite without modifying the domain objects.

---

# 31. Golden Rule

The Domain Model is the foundation of AI Studio Toolkit.

No feature may introduce a new business object without updating this document first.

Every implementation must remain compatible with this Domain Model.

---

End of document.