# Runtime Protocol

The runtime protocol defines how models and applications interact with the world substrate without depending on physical storage internals.

The prototype should use typed JSON-compatible contracts. JSON is a transport format, not the conceptual architecture.

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
  "object_id": "person:alice",
  "projection": "default"
}
```

```json
{
  "op": "get_relations",
  "subject_id": "person:alice",
  "predicate": "member_of"
}
```

```json
{
  "op": "semantic_search",
  "query": "the incident where Alice admitted stealing the key",
  "limit": 8
}
```

The model should not generate SQL, storage keys, or table-specific operations.

## Projections

A projection is a bounded representation of an object or set of objects for a specific purpose.

A projection may depend on:

- requesting application;
- observer/actor;
- permissions;
- requested capability;
- token/context budget.

The engine should prefer returning only the state relevant to the operation instead of serializing complete objects by default.

Perspective-sensitive projections are essential for preventing omniscience leakage.

Conceptually:

```json
{
  "object_id": "person:alice",
  "observer_id": "person:ben",
  "application": "conversation",
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
  "item_id": "item:key",
  "from_id": "person:alice",
  "to_id": "person:ben"
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

Commands should declare their input schema, permitted reads/writes, validation behavior, and result type.

## Validation and commit

The runtime owns persistence and invariants.

A model-originated change should follow a controlled path:

`proposal -> validation -> execution -> committed event/result`

Validation may include:

- schema conformance;
- object existence;
- permissions;
- preconditions;
- current-state consistency;
- application rules;
- provenance/evidence requirements.

Where practical, a turn's related mutations should be atomic.

## Creation

Creation is a normal write operation.

A model may propose creation of a world object only through a documented capability or privileged authoring path.

The proposal should identify:

- target schema/type;
- structured properties;
- relations;
- reason for creation;
- provenance/source;
- confidence or derivation status where relevant.

The engine validates the proposal before committing it.

## Structural gaps

Missing information should not always be represented as null or failure.

When a required fact is absent, the runtime may escalate to a gap-resolution capability. Gap resolution should be explicit and traceable rather than hidden inside prose generation.

A resolver may:

- inspect related world objects;
- search sources;
- use stronger models;
- propose new objects or relations;
- validate consistency;
- persist the resolved result.

Cosmetic gaps and structural gaps may use different policies.

## Application contracts

Layer B should expose a model-facing interface analogous to an SDK or MCP server.

A capability definition should ideally include:

- stable name;
- purpose;
- when to use and when not to use it;
- typed inputs;
- typed output/result;
- allowed reads;
- allowed writes;
- preconditions;
- failure modes;
- examples when ambiguity warrants them.

The runtime model should not be expected to infer these contracts from database contents.

## Authoring operations

Privileged authoring may expose lower-level mutation tools such as:

- create object;
- patch object;
- add/remove relation;
- record/correct event;
- migrate schema;
- retcon or supersede data.

These operations must still be logged and validated. Human and AI-assisted authoring should converge on the same underlying mutation APIs.

## Context compilation

If a writer model is used, the planner/runtime may compile a minimal context packet from resolved world state.

The packet should contain results, not a raw database dump.

The writer's job is primarily rendering and generation. It should not be required to reconstruct authoritative world truth from large lore blobs.

## Execution ledger

Every model/tool turn relevant to an experiment should be observable.

Record at least:

- turn/execution ID;
- component/role;
- model/provider identifier;
- tool calls and arguments;
- object IDs read/written;
- validation outcome;
- committed operations/events;
- latency;
- token usage when available;
- errors/retries.

This ledger is factual runtime telemetry. Future skill discovery should analyze this ledger rather than hidden model chain-of-thought.
