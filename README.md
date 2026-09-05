# Story Kernel

Story Kernel is an experimental runtime for persistent fictional worlds.

The project is not an RP frontend, game engine, chatbot shell, or social simulator. It is a lower-level architecture experiment intended to answer a narrower question:

> Can a persistent typed world, exposed through explicit machine-readable capabilities, let ordinary tool-using language models interact with fictional state more reliably than prompt/lorebook-centric systems?

The prototype is deliberately implementation-first and product-agnostic. A finished system might later power prose roleplay, messaging, social simulation, games, newspapers, books, or interfaces we have not anticipated. The core must not depend on any one of those presentations.

## Core model

Story Kernel currently uses four conceptual layers:

- **A — World substrate:** persistent fictional reality: typed objects, relations, events, sources, state, memories, beliefs, and other world-authored structures.
- **B — Application contract:** documented capabilities, tools, projections, constraints, and methods through which a runtime may interact with the world.
- **C — Live runtime:** the user-facing experience: prose, chat, game, social feed, or any other interface.
- **D — Meta-runtime:** persistent authoring intelligence that can inspect, repair, extend, and evolve A and B when the current vocabulary is insufficient.

A and B are authoritative. C should not require direct knowledge of their internal representation. D may evolve them under explicit policy.

## Prototype goal

The first prototype does not attempt to build a polished roleplay application. It should establish whether the underlying world runtime is viable.

Initial work should focus on:

1. persistent typed world state;
2. exact, relational, and semantic discovery;
3. documented model-facing tools and projections;
4. validated creation and mutation of world state;
5. execution traces and deterministic evaluation;
6. comparison against monolithic prompt and text-RAG baselines.

## Non-goals for the first prototype

Do not prioritize:

- polished UX;
- character-card compatibility beyond what an experiment needs;
- game mechanics;
- social-network UI;
- image generation;
- production scaling;
- marketplace/package ecosystems;
- elaborate multi-agent councils;
- domain-specific ontology in the engine core.

## Design documents

- [`AGENTS.md`](AGENTS.md) — repository instructions for coding agents.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — architectural boundaries and A/B/C/D model.
- [`WORLD_MODEL.md`](WORLD_MODEL.md) — persistent world representation.
- [`RUNTIME_PROTOCOL.md`](RUNTIME_PROTOCOL.md) — model/runtime interaction contracts.
- [`EVALUATION.md`](EVALUATION.md) — experiments, metrics, and falsification criteria.
- [`ENGINESKILLS.md`](ENGINESKILLS.md) — definition and lifecycle of reusable skills.

## Working principle

Compatibility may exist at the edges, but the core should not reproduce the SillyTavern pattern of treating text assembly as the world model.

Natural language is primarily an input/output representation. Persistent world state should be addressable, inspectable, testable, and mutable without requiring the transcript to remain the authoritative database.
