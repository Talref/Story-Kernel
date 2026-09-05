# Runtime Protocol

The runtime protocol defines how models and applications interact with the world substrate without depending on physical storage internals.

The prototype should use typed JSON-compatible contracts. JSON is a transport format, not the conceptual architecture.

## Addressing context

Every stateful read or write should be resolvable against an explicit execution context.

A context may identify:

- world or scenario ID;
- state scope;
- application/capability version;
- observer or actor identity;
- expected object revision where mutation safety requires it.

A model should not need to know database table names or persistence keys in order to address world state.

## Message classes

The protocol should distinguish at least four classes of interaction:

1. **Query** — ask the world for information.
2. **Projection** — return a bounded, policy-aware view of world state.
3. **Command / Proposal** — request a world change.
4. **Event / Result** — record what the engine actually accepted and executed.

## Queries

Queries should be narrow and explicit.

Examples:

```json
{
  "op": "inspect_object",
  "world_id": "world:1",
  "object_id": "instance:world-1:alice",
  "projection": "default"
}
```

```json
{
  "op": "get_relations",
  "world_id": "world:1",
  "subject_id": "instance:world-1:alice",
  "predicate": "member_of"
}
```

```json
{
  "op": "semantic_search",
  "world_id": "world:1",
  "query": "the incident where Alice admitted stealing the key",
  "limit": 8
}
```

The model should not generate SQL, storage keys, or table-specific operations.

Queries should distinguish reusable definitions from mutable instances when that distinction matters. A request for baseline definition data is not equivalent to a request for current world state.

## Projections

A projection is a bounded representation of an object or set of objects for a specific purpose.

Projection should be treated as an ordered policy pipeline rather than one undifferentiated filter.

At minimum:

1. resolve the target world/scope and authoritative revision;
2. apply authorization/access policy;
3. apply epistemic/observer visibility;
4. apply capability/application-specific shaping;
5. apply size or token-budget truncation.

Authorization and epistemic visibility must be resolved before budget reduction. A budget may shorten an allowed projection; it must never make a forbidden or unknown fact become visible.

A projection may depend on:

- requesting application;
- observer/actor;
- permissions;
- requested capability;
- target scope;
- token/context budget.

The engine should prefer returning only the state relevant to the operation instead of serializing complete objects by default.

Perspective-sensitive projections are essential for preventing omniscience leakage.

Conceptually:

```json
{
  "object_id": "instance:world-1:alice",
  "observer_id": "instance:world-1:ben",
  "application": "conversation",
  "world_id": "world:1",
  "visible": {
    "public_name": "Alice",
    "known_claims": ["claim:17"]
  }
}
```

## Commands and proposals

Runtime models should express semantic intent rather than directly mutating arbitrary object fields when a suitable command exists.

Prefer:

```json
{
  "op": "transfer_object",
  "world_id": "world:1",
  "item_id": "instance:world-1:key",
  "from_id": "instance:world-1:alice",
  "to_id": "instance:world-1:ben",
  "expected_revision": 12
}
```

instead of:

```json
{
  "op": "replace_json",
  "path": "person:ben.inventory",
  "value": ["item:key"]
}
```

Commands should declare their input schema, permitted reads/writes, target scope, validation behavior, and result type.

A command that mutates persistent state should identify the revision or preconditions it was evaluated against when stale-write protection is relevant.

## Validation and commit

The runtime owns persistence and invariants.

A model-originated change should follow a controlled path:

`proposal -> validation -> execution -> committed event/result`

Validation may include:

- schema conformance;
- object existence;
- scope compatibility;
- permissions;
- preconditions;
- expected revision/current-state consistency;
- application rules;
- provenance/evidence requirements.

Where practical, a turn's related mutations should be atomic.

Committed results should make clear which authoritative state revision was produced and which history/event records correspond to that transition.

## Creation and instantiation

Creation is a normal write operation, but the protocol should distinguish reusable definition creation from world-instance creation.

A model may propose creation only through a documented capability or privileged authoring path.

A definition proposal should identify:

- target schema/type;
- baseline structured properties;
- provenance/source;
- versioning intent.

An instance proposal should identify:

- target world/scope;
- optional source definition and definition version;
- instance-local state;
- relations;
- reason for creation;
- provenance/source.

The engine validates the proposal before committing it.

## Scope and overlays

Writes must target an explicit scope.

Examples include:

- persistent world state;
- scenario or branch state;
- application-private draft state;
- transient execution state.

A temporary overlay must not silently mutate its parent scope. Promotion, merge, discard, or commit of overlay state should be explicit operations with validation and provenance.

The first implementation may support only a subset of these scopes, but the protocol should not conflate them.

## Structural gaps

Missing information should not always be represented as null or failure.

When a required fact is absent, the applicable schema or capability should determine the allowed policy. Policies may include:

- fail because the field is required and closed-world;
- return unknown;
- infer for the current operation without persisting;
- propose authorial invention;
- persist derived state;
- require approval.

Gap resolution should be explicit and traceable rather than hidden inside prose generation.

A resolver may:

- inspect related world objects;
- search sources;
- use stronger models;
- propose new objects or relations;
- validate consistency;
- persist the resolved result when policy permits.

Provenance and confidence describe origin and uncertainty; they do not automatically authorize invention as world truth.

## Application contracts

Layer B should expose a model-facing interface analogous to an SDK or MCP server.

A capability definition should ideally include:

- stable name and version;
- purpose;
- when to use and when not to use it;
- typed inputs;
- typed output/result;
- allowed reads;
- allowed writes and target scopes;
- preconditions;
- failure modes;
- examples when ambiguity warrants them.

The runtime model should not be expected to infer these contracts from database contents.

An execution should remain pinned to the contract version under which it began unless an explicit migration or retry policy says otherwise.

## Authoring operations

Privileged authoring may expose lower-level mutation tools such as:

- create or revise definition;
- instantiate object;
- patch instance;
- add/remove relation;
- record/correct event;
- migrate schema;
- retcon or supersede data;
- fork or merge scoped state.

These operations must still be logged and validated. Human and AI-assisted authoring should converge on the same underlying mutation APIs.

Definition edits, instance edits, migrations, retcons, and branch operations are distinct semantic operations even if they share lower-level storage machinery.

## Context compilation

If a writer model is used, the planner/runtime may compile a minimal context packet from resolved world state.

The packet should contain results, not a raw database dump.

The writer's job is primarily rendering and generation. It should not be required to reconstruct authoritative world truth from large lore blobs.

## Execution ledger

Every model/tool turn relevant to an experiment should be observable.

Record at least:

- turn/execution ID;
- world/scenario/scope ID;
- application/capability version;
- component/role;
- model/provider identifier;
- tool calls and arguments;
- object IDs and revisions read/written;
- validation outcome;
- committed operations/events;
- resulting revisions;
- latency;
- token usage when available;
- errors/retries.

This ledger is factual runtime telemetry. Future skill discovery should analyze this ledger rather than hidden model chain-of-thought.
