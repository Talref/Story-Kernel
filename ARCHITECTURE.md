# Architecture

Story Kernel is organized around four conceptual layers. These layers describe responsibility boundaries, not necessarily separate processes or services.

## A — World substrate

The world substrate is persistent fictional reality.

It contains typed, addressable state such as:

- objects;
- relations;
- events;
- sources and provenance;
- memories, beliefs, claims, secrets, or other world-authored structures;
- schema/type definitions;
- indexes derived from authoritative state.

A is authoritative for what exists and what has happened.

Natural-language transcripts are evidence and history, not the sole source of truth.

## B — Application contract

The application contract defines what a runtime is allowed and expected to do with A.

It may expose:

- tools and methods;
- input/output schemas;
- state projections;
- permissions;
- constraints;
- validation behavior;
- examples and usage documentation;
- retrieval policies;
- capability-specific prompts;
- deterministic procedures and model-assisted procedures.

B should be MCP-like from the model's point of view: explicit, documented, and narrow enough that a competent tool-using model can operate it reliably.

B may be generic or domain-specific. `inspect_object` may be generic; `send_owl` may belong to a particular world/application package.

## C — Live runtime

C is the experience presented to the user.

Examples include:

- prose roleplay;
- phone-like conversations;
- social feeds;
- newspapers;
- game interfaces;
- a book-writing workflow;
- a temporary scenario.

C should not require the user to understand A or B. C may present selected projections of A through B, but it should not own duplicate copies of persistent world truth.

Different applications should be able to operate the same world entity without creating mode-specific clones of that entity.

## D — Meta-runtime

D is persistent authoring and architectural intelligence.

Unlike a conventional compiler that runs once, D may remain active while the world is used. It can:

- inspect A and B;
- identify missing or inadequate capabilities;
- detect structural world gaps;
- propose new schemas, tools, methods, or skills;
- repair inconsistencies;
- run validation and tests;
- evolve B when a live interaction exceeds its current vocabulary;
- extend A when the world cannot represent a newly important concept.

D must operate under policy. Novelty does not automatically justify a permanent abstraction.

A useful escalation model is:

1. **generic execution** — existing primitives are enough;
2. **ad-hoc reasoning** — solve the current case without persisting a new abstraction;
3. **vocabulary extension** — create or revise a reusable capability because consistent mechanics/state justify it.

## Core invariants

### One world, many applications

A persistent entity should not be duplicated merely because it appears in multiple modes.

A person may participate in roleplay, correspondence, social simulation, games, and publications while remaining the same underlying world object.

### World state is not prompt state

The system may compile a minimal context packet for a writer model, but prompt construction is downstream of world computation.

The intended direction is:

`WORLD STATE -> queries/methods/computation -> relevant results -> minimal model context`

not:

`WORLD -> serialize everything -> prompt`

### Semantic retrieval is discovery, not authority

Embeddings and RAG are indexes. They may discover candidate objects or evidence, but authoritative structured state is resolved through object inspection, relations, events, sources, and validated methods.

### Models use APIs, not storage internals

Model-facing contracts must be independent from physical persistence. A future storage migration should not require the runtime model vocabulary to change.

### Composition over universal ontology

The engine should not impose a universal fiction ontology. Worlds define what dimensions they care about.

The core provides primitives for identity, state, relation, history, schema, querying, validation, and capability execution.

## Execution phases

The architecture should support work with different latency requirements:

- **before/blocking** — required before the current output can be produced;
- **parallel** — useful work that cannot affect the current output;
- **after** — consumes the completed output and may update state;
- **background** — eventually consistent enrichment, auditing, consolidation, or analysis.

The first prototype should keep the critical path minimal. Do not create a council of agents by default.

## Authoring boundary

Human-facing editing and AI-assisted editing should ultimately converge on the same validated mutation APIs.

A privileged authoring surface may expose broader operations than a live runtime, but it should not create an untraceable second source of truth.

## Compatibility

Story Kernel may import or export formats from existing roleplay ecosystems. Compatibility belongs at the edges.

The internal architecture must not be constrained to character cards, lorebook keyword triggers, prompt depth, or other legacy prompt-management abstractions.
