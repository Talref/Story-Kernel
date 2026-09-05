# Architecture

Story Kernel is organized around three runtime responsibility layers and one privileged control plane. These boundaries describe ownership and authority, not necessarily separate processes or services.

## A — World substrate

The world substrate is persistent fictional reality.

It contains typed, addressable state such as:

- reusable object definitions;
- world-scoped object instances;
- relations;
- events and committed history;
- sources and provenance;
- memories, beliefs, claims, secrets, or other world-authored structures;
- schema/type definitions;
- indexes derived from authoritative state.

A is authoritative for persisted world state and for the committed history that explains state changes.

Current truth and historical provenance must have an explicit consistency rule. Natural-language transcripts are evidence and history inputs, not the sole source of truth.

A should distinguish reusable definitions from mutable instances. Independent worlds, scenarios, or branches may instantiate the same definition without sharing mutable state.

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

B is authoritative for the versioned operational vocabulary presented to clients and models: permitted operations, view policies, and their contracts. It is not authoritative for world truth itself.

B should be MCP-like from the model's point of view: explicit, documented, and narrow enough that a competent tool-using model can operate it reliably.

B may be generic or domain-specific. `inspect_object` may be generic; `send_owl` may belong to a particular world/application package.

## C — Live runtime

C is the experience and orchestration surface through which a user or automated client invokes B against A.

Examples include:

- prose roleplay;
- phone-like conversations;
- social feeds;
- newspapers;
- game interfaces;
- a book-writing workflow;
- a temporary scenario.

C may coordinate model calls, invoke capabilities, render results, and manage transient user-facing state. It should not own duplicate copies of authoritative world truth.

Different applications should be able to operate the same world instance without creating mode-specific clones of that entity.

Application-private drafts, simulations, or temporary overlays must remain explicitly scoped rather than silently becoming shared world truth.

## D — Meta-runtime control plane

D is persistent authoring and architectural intelligence with privileged access across A and B.

D is not an ordinary runtime layer and should not be an implicit fallback inside every live turn. It may be invoked continuously, periodically, or only under explicit policy.

It can:

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

Changes produced by D should be versioned, testable, and reproducible. A running execution must have a defined contract/schema version rather than silently switching semantics mid-operation.

## Core invariants

### One definition, many instances; one instance, many applications

A reusable definition may seed multiple independent worlds or scenarios.

A persistent instance should not be duplicated merely because it appears in multiple applications.

A person may participate in roleplay, correspondence, social simulation, games, and publications while remaining the same underlying world instance. A separate instance is created only when isolation of mutable state is intentional, such as a different world, scenario, or branch.

### Scoped state is explicit

Persistent world state, scenario state, application-private state, and transient execution state are different scopes.

Writes must target an explicit scope. Temporary state must not become authoritative merely because an application produced it.

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

The core provides primitives and invariants for identity, state, relation, history, schema, scope, querying, validation, and capability execution.

## Projection order

Projection concerns should remain separable.

At minimum:

1. resolve target world/scope and object revision;
2. apply authorization and access policy;
3. apply epistemic/observer visibility;
4. apply capability/application shaping;
5. apply size or token-budget reduction.

Budgeting may shorten an already-permitted view. It must not determine whether information is knowable or authorized.

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

Definition edits, instance edits, migrations, and retcons are distinct operations and should not be conflated.

## Compatibility

Story Kernel may import or export formats from existing roleplay ecosystems. Compatibility belongs at the edges.

Exports should be able to distinguish reusable definitions from world-specific instance state and history when the target format permits it.

The internal architecture must not be constrained to character cards, lorebook keyword triggers, prompt depth, or other legacy prompt-management abstractions.
