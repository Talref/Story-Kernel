# Story Kernel — Human Recap

This document is the human-facing map of the project.

It is intentionally simpler than the architecture documents. It is meant for someone who wants to understand what Story Kernel is, why it exists, what has been decided, and what is being tested without following every technical discussion or implementation detail.

It should be updated when the project changes direction, reaches a meaningful milestone, or makes an architectural decision that changes how the system should be understood. It should not be updated for every issue or code change.

The technical documents remain the source of truth for implementation details.

## What are we trying to build?

Story Kernel is an experiment in building a lower-level engine for persistent fictional worlds.

The project is not trying to build one specific roleplay application. A future system built on top of it could be:

- a traditional prose roleplay;
- a phone-like conversation system;
- a social network populated by fictional people;
- an in-world newspaper;
- a game;
- a book-writing environment;
- or something that has not been designed yet.

The central idea is that all of those experiences should be able to use the same underlying fictional reality instead of each keeping its own disconnected copy of characters, memories, locations, facts, and history.

## Why not just use a lorebook and a large prompt?

Most current roleplay systems treat text as the main representation of the world.

A character description, lorebook entries, summaries, retrieved memories, and recent messages are assembled into a prompt. The language model then has to reconstruct what is true from that text every time it responds.

Story Kernel is testing a different approach:

> Store the important parts of the fictional world as persistent, structured, addressable state, and let models interact with that state through explicit tools.

Text still matters. It is how people write, speak, narrate, and author content. But text should not have to be the only place where the engine remembers who owns an item, what happened yesterday, who knows a secret, or which version of an object belongs to the current world.

## The four parts of the system

The project currently uses four conceptual areas. They are easier to understand as responsibilities than as literal software layers.

### A — The world

This is the persistent fictional reality.

It contains things such as objects, relations, current state, events, sources, memories, beliefs, and other structures defined by a world.

The engine itself should not assume that every world has characters, spells, quests, combat, or any other fiction-specific concept. A farming world and a wizard school should be free to care about very different things.

A is authoritative about world state.

### B — The ways of interacting with the world

B is the documented vocabulary that an application or model can use to work with A.

Examples might include generic operations such as inspecting an object or following a relation, and world-specific operations such as sending a letter or playing a particular game.

The important point is that a runtime model should not have to understand the database or invent arbitrary JSON structures. It should be given clear, typed, documented capabilities, similar in spirit to an API, SDK, or MCP server.

B is authoritative about what operations are available and what policies govern them.

### C — The user experience

C is what the user actually sees and uses.

It might be prose, chat bubbles, a social feed, a newspaper layout, a game interface, or something else entirely.

C should use A through B. It should not become a second source of world truth.

For example, the same fictional person should be able to appear in a roleplay, receive a letter, and be quoted in a newspaper while remaining the same underlying world instance.

### D — The authoring and meta-runtime

D is privileged intelligence used to build, inspect, repair, and eventually extend A and B.

Unlike a normal compiler, it may remain useful after a world has started running. If the current vocabulary cannot represent an important new activity, D may eventually help decide whether the system should handle it once, improvise it, or add a reusable capability.

D is deliberately excluded from the first experiment. The project first needs to prove that A, B, and a simple runtime are useful before adding self-extension.

## Reusable objects and living objects

A useful distinction has been made between a reusable seed and an object that is already living inside a world.

A reusable definition or seed is construction input. It can be exported and used to create an object in a new world.

A world instance is the actual object inside one particular fictional world. Its state can change as events occur.

For example, a reusable character seed may describe a person's baseline identity. Two separate worlds may instantiate that seed and then develop differently.

Existing world instances do not silently change because the reusable seed is edited later.

This distinction is intended to support reuse, export, independent scenarios, and persistent evolution without mixing unrelated histories.

## Current state and history

For the first implementation, the intended simple model is:

- current state answers **what is true now**;
- committed history answers **how it became true**.

The first prototype does not need full event sourcing or a sophisticated branching system. It only needs deterministic current state, revision checks, and an auditable history of accepted changes.

## How models should interact with the world

A runtime model should not write SQL or edit arbitrary database records.

It should use documented operations.

Reading should support three basic paths:

1. exact lookup when the target is already known;
2. relation traversal for structured connections;
3. semantic search for discovering likely relevant objects or evidence.

Semantic search is treated as a way to find candidates, not as the final authority. After discovery, the engine should inspect structured state.

Writes should normally use semantic commands such as transferring an item rather than replacing arbitrary JSON fields. The runtime validates the command before committing it.

## Knowledge and perspective

One of the most important tests is whether the engine can distinguish objective world state from what individual people know, remember, believe, or misunderstand.

A statement being made is not the same thing as the statement being true. A person hearing something is not the same thing as believing it. A secret is not automatically known by every character simply because it exists in the database.

The first fixture world will include asymmetric knowledge and at least one false belief specifically to test this.

## What are we building first?

Not a roleplay frontend.

The first experiment should be deliberately small and somewhat boring. Its job is to test the architecture, not to entertain.

A small deterministic fictional world will be created with a handful of people, places, objects, events, secrets, and beliefs.

The same canonical facts will then be exposed to the same medium-capability model in three different ways:

1. a monolithic text prompt;
2. ordinary text RAG;
3. the Story Kernel object/tool runtime.

The experiment will test things such as:

- retrieving current state correctly;
- following relations;
- understanding chronology;
- avoiding knowledge leakage;
- finding semantically relevant old events;
- performing one safe state-changing operation;
- tool-call reliability;
- latency and context cost.

The comparison must be fair. All approaches should be generated from the same underlying fixture and use the same final validation rules where applicable.

## What would count as a useful result?

A positive result would show that structured world state and explicit tools let a competent non-frontier model behave more reliably than text RAG on the kinds of tasks where world structure should matter.

A negative result is also valuable.

If the object runtime performs no better than RAG, requires large bespoke APIs for every task, needs frontier-model rescue constantly, or simply turns structured objects back into giant lore paragraphs before generation, then the central idea needs to be reconsidered.

The project should publish and learn from that result rather than adding complexity until the original test becomes impossible to fail.

## What are we deliberately not building yet?

The first experiment does not need:

- a polished UI;
- image generation;
- a social network clone;
- a game mode;
- branching and merge systems;
- automatic gap repair;
- dynamic skill creation;
- D running inside ordinary turns;
- a marketplace;
- a universal fiction ontology;
- a large multi-agent council;
- production infrastructure.

Those ideas may matter later, but only after the lower-level hypothesis has evidence behind it.

## Current project status

The architecture documents have been written and reviewed several times. The major authority and persistence questions are considered settled enough for Experiment 0.1.

The architecture is now intentionally frozen for the first experiment unless implementation reveals a genuine contradiction or blocker.

The next meaningful work is implementation and measurement, not another round of broad architectural polishing.

## Where to look if you need more detail

- `ARCHITECTURE.md` explains the responsibility boundaries and core invariants.
- `WORLD_MODEL.md` defines the persistent structures and state semantics.
- `RUNTIME_PROTOCOL.md` defines how models and applications read and change world state.
- `EVALUATION.md` defines how the experiment should be tested and falsified.
- `ENGINESKILLS.md` describes the future concept of reusable skills.
- `AGENTS.md` contains instructions for coding agents working in the repository.

If these documents and this recap ever disagree, the technical documents should be treated as authoritative and this recap should be corrected.