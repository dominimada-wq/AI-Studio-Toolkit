# AI Studio Toolkit

**Document:** 00_VISION.md

**Version:** 1.0

**Status:** Draft

**Last Update:** 2026-08-08

---

# 1. Vision

## Mission

AI Studio Toolkit is a professional desktop application designed to manage the complete lifecycle of AI-generated digital characters.

The application is not intended to replace existing AI engines.

Instead, it provides a unified workspace capable of orchestrating multiple local and cloud AI engines through a single, consistent user interface.

The objective is to eliminate the need to constantly switch between different applications during production.

---

# 2. Product Vision

AI Studio Toolkit aims to become the reference operating environment for AI creators.

The software must allow users to:

- create digital characters
- train character models
- manage datasets
- organize AI assets
- generate images
- generate videos
- manage prompts
- manage workflows
- manage AI models
- monitor production
- automate repetitive tasks

Everything must happen inside a single application.

---

# 3. Long-Term Goal

Within the next five years AI Studio Toolkit should become the equivalent of Visual Studio for Generative AI.

Instead of writing software, users build digital humans.

Instead of compiling code, users generate media.

Instead of debugging applications, users improve AI models.

The software should become the central workspace for every stage of AI content production.

---

# 4. Design Philosophy

The project follows several immutable principles.

## Simplicity

Complex workflows should appear simple.

The user should focus on creation rather than technical configuration.

---

## Modularity

Every subsystem must remain independent.

Features can be added or removed without affecting the rest of the application.

---

## Scalability

The software must support:

- one character
- ten characters
- hundreds of characters

without changing its architecture.

---

## Extensibility

New AI engines must be integrated through plugins.

The core application must never depend directly on a specific engine.

---

## Non-destructive workflow

User data should never be modified automatically.

Every important operation must be reversible whenever possible.

---

# 5. Product Scope

AI Studio Toolkit manages the production pipeline.

It does not replace specialized software.

Instead it coordinates them.

Examples:

ComfyUI remains responsible for node-based image generation.

OneTrainer remains responsible for model training.

Kohya_ss remains responsible for advanced LoRA training.

GPT Image 2 remains responsible for cloud image generation.

Kling remains responsible for AI video generation.

AI Studio Toolkit coordinates all these systems.

---

# 6. Target Users

Primary users

- AI artists

- AI photographers

- Virtual influencer creators

- Content creators

- Marketing agencies

- Independent studios

Secondary users

- Researchers

- Developers

- AI educators

---

# 7. Core Concepts

The application is built around four fundamental concepts.

## Workspace

A Workspace represents an entire production environment.

It contains all resources required for one or more AI productions.

---

## Character

A Character represents a digital human.

Characters own identity.

Characters evolve over time.

Characters contain their own datasets, prompts, LoRAs and history.

---

## Engine

An Engine represents any software capable of producing AI results.

Examples:

ComfyUI

Forge

Automatic1111

Fooocus

GPT Image 2

Kling

OneTrainer

Kohya_ss

fal.ai

Seedance

Seedream

Higgsfield

---

## Job

Every operation executed by the software becomes a Job.

Examples

Generate Image

Generate Video

Train LoRA

Import Dataset

Export Dataset

Generate Captions

Upscale

Publish

Jobs can be queued, paused, resumed and monitored.

---

# 8. Workspace Philosophy

A Workspace is the highest organizational level.

Everything belongs to a Workspace.

Workspace

├── Characters

├── Models

├── Datasets

├── Workflows

├── Assets

├── Jobs

├── Outputs

├── Settings

└── Logs

---

# 9. Character Philosophy

Characters are the heart of the application.

A Character is not merely a folder.

A Character is a structured digital entity.

Every Character owns

Identity

Reference Images

Reference Videos

Datasets

Prompts

Negative Prompts

LoRAs

Favorite Models

Favorite Engines

Generation History

Training History

Metadata

Knowledge Base

---

# 10. Supported Engines

## Local Engines

ComfyUI

WebUI Forge

AUTOMATIC1111

Fooocus

OneTrainer

Kohya_ss

---

## Cloud Engines

GPT Image 2

fal.ai

Nano Banana

Kling

Seedance

Seedream

Higgsfield

Future engines can be added through plugins.

---

# 11. AI Orchestrator

The application never communicates directly with AI engines.

Every request passes through the AI Orchestrator.

User Interface

↓

Managers

↓

Services

↓

AI Orchestrator

↓

Engine Manager

↓

Plugins

↓

AI Engine

This guarantees complete engine independence.

---

# 12. Shared Resources

The following resources belong to the Workspace.

Checkpoints

LoRAs

VAEs

ControlNet

Embeddings

IPAdapter

Clip Vision

Upscalers

Workflows

Templates

Assets

Characters simply reference these resources.

---

# 13. Character Knowledge Base

Every Character continuously records production knowledge.

Examples

Best prompts

Best checkpoints

Best LoRAs

Best engines

Best parameters

Best workflows

Highest rated generations

This transforms every Character into a continuously improving digital asset.

---

# 14. Automation

Every repetitive task should eventually become automatable.

Examples

Automatic imports

Automatic dataset preparation

Automatic caption generation

Automatic training

Automatic testing

Automatic generation

Automatic publication

---

# 15. Future AI

The software should be designed to integrate future AI technologies without requiring architectural changes.

This includes future image models, video models, language models and training systems.

---

# 16. What AI Studio Toolkit is NOT

AI Studio Toolkit is not

- an image generator

- a node editor

- a LoRA trainer

- a video generator

Instead it orchestrates all these tools.

---

# 17. Product Identity

AI Studio Toolkit is a production platform.

The application manages complete digital productions rather than isolated AI generations.

Its focus is organization, orchestration, automation and long-term management.

---

# 18. Success Criteria

The project will be considered successful when a creator can:

Create a new Character

↓

Prepare datasets

↓

Train LoRA

↓

Generate images

↓

Generate videos

↓

Manage versions

↓

Publish content

↓

Archive the complete production

without leaving AI Studio Toolkit.

---

# 19. Golden Rule

Every architectural decision must reinforce this vision.

Whenever a new feature conflicts with this document, the Vision must be updated before the code.

---

End of document.