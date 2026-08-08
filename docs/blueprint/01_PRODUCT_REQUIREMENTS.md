# AI Studio Toolkit

**Document:** 01_PRODUCT_REQUIREMENTS.md

**Version:** 1.0

**Status:** Draft

**Related Documents**
- 00_VISION.md

---

# 1. Purpose

This document defines the functional requirements of AI Studio Toolkit.

It specifies what the application must do.

It does not describe how it should be implemented.

Implementation details belong to the Architecture documents.

---

# 2. Product Goal

AI Studio Toolkit is a desktop application allowing creators to manage the complete production lifecycle of AI-generated digital characters.

The software must provide a unified environment covering:

- project management
- character management
- datasets
- LoRA training
- model management
- image generation
- video generation
- workflow management
- AI engine orchestration
- publishing

---

# 3. Functional Domains

The application is divided into the following domains.

## Workspace

Responsible for:

- creating workspaces
- opening workspaces
- closing workspaces
- importing workspaces
- exporting workspaces
- backups
- archive management

Priority: P0

---

## Character Management

Responsible for:

- create character
- duplicate character
- archive character
- delete character
- rename character
- version character
- organize character folders

Each character owns independent resources.

Priority: P0

---

## Dataset Management

Responsible for:

- import datasets

- automatic validation

- duplicate detection

- image quality analysis

- caption generation

- automatic tagging

- dataset statistics

- dataset versions

Priority: P0

---

## Model Library

Responsible for:

- checkpoints

- VAE

- ControlNet

- Clip Vision

- IPAdapter

- Embeddings

- Upscalers

- Hypernetworks

- Custom Models

Models are shared between all Characters.

Priority: P0

---

## LoRA Library

Responsible for:

- Flux LoRA

- SDXL LoRA

- Pony LoRA

- Wan LoRA

- Hunyuan LoRA

Every LoRA stores:

- metadata

- trigger words

- version

- author

- engine compatibility

Priority: P0

---

## Prompt Library

Responsible for:

- positive prompts

- negative prompts

- templates

- variables

- tags

- categories

- favorites

- prompt history

Priority: P1

---

## Workflow Library

Responsible for:

- ComfyUI workflows

- Fooocus presets

- Forge presets

- reusable templates

- workflow categories

Priority: P1

---

## Training

Responsible for:

- OneTrainer

- Kohya_ss

- monitoring

- live logs

- pause

- resume

- cancel

Priority: P0

---

## Image Generation

Responsible for:

Local engines

Cloud engines

History

Queue

Metadata

Ratings

Favorites

Priority: P0

---

## Video Generation

Responsible for:

Kling

Seedance

Seedream

Higgsfield

Future providers

Priority: P1

---

## Automation

Responsible for:

batch generation

scheduled jobs

automatic exports

automatic captions

automatic training

automatic publishing

Priority: P2

---

# 4. Supported Engines

## Local

ComfyUI

AUTOMATIC1111

WebUI Forge

Fooocus

OneTrainer

Kohya_ss

---

## Cloud

GPT Image 2

fal.ai

Nano Banana

Kling

Seedance

Seedream

Higgsfield

---

# 5. Workspace Structure

Each Workspace contains

Characters

Datasets

Models

LoRAs

Outputs

Assets

Workflows

Logs

Configuration

Jobs

Cache

---

# 6. Character Structure

Each Character contains

Identity

Description

Reference Images

Reference Videos

Datasets

Captions

LoRAs

Favorite Models

Favorite Engines

Prompt Library

Generation History

Training History

Knowledge Base

Notes

---

# 7. Dashboard Requirements

The Dashboard must display

Current Workspace

Characters

Images

Datasets

Models

LoRAs

Jobs

Recent Activity

Storage Usage

Engine Status

GPU Information

Training Queue

Generation Queue

---

# 8. Settings

The Settings page must manage

Python

ComfyUI

Fooocus

Forge

AUTOMATIC1111

OneTrainer

Kohya_ss

GPT Image 2 API

fal.ai API

Kling API

Seedance API

Seedream API

Higgsfield API

Themes

Language

Updates

Logging

GPU Settings

---

# 9. Generation Requirements

Image generation must support

single image

batch

variations

seed locking

character locking

negative prompts

ControlNet

IPAdapter

LoRA selection

workflow selection

metadata recording

---

# 10. Training Requirements

Training must support

OneTrainer

Kohya

training queue

resume

cancel

monitoring

tensorboard

logs

automatic model registration

automatic versioning

---

# 11. Character Lock

Every Character must remain independent.

A Character stores

its own prompts

its own datasets

its own LoRAs

its own preferred models

its own generation history

its own workflows

No Character may modify another Character.

---

# 12. Queue System

Every long operation becomes a Job.

States

Waiting

Running

Paused

Completed

Cancelled

Failed

Jobs remain visible after completion.

---

# 13. Error Handling

Every operation must

return detailed errors

write logs

never silently fail

allow retry whenever possible

---

# 14. Acceptance Criteria

The software is considered functionally complete when a user can

Create a Workspace

↓

Create Characters

↓

Import datasets

↓

Train LoRA

↓

Generate images

↓

Generate videos

↓

Save the project

↓

Reopen the project

↓

Continue working

without using any external file manager.

---

# 15. Future Requirements

Future versions should support

multi-user collaboration

cloud synchronization

distributed rendering

REST API

plugin marketplace

AI assistants

mobile companion

---

# 16. Priorities

P0

Workspace

Characters

Datasets

Models

LoRAs

Training

Generation

Settings

Project persistence

P1

Prompt Library

Workflow Library

Video

Dashboard

Statistics

P2

Automation

Marketplace

Collaboration

Cloud Sync

---

# 17. Implementation Notes

This document intentionally avoids implementation details.

Implementation is defined by:

- 02_ARCHITECTURE.md
- 03_PROJECT_STRUCTURE.md
- 04_DATA_MODEL.md
- 05_CHARACTER_SYSTEM.md

The implementation must satisfy every functional requirement described here.

---

End of document.