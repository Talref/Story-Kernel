# Runtime Protocol

The runtime protocol defines how models and applications interact with the world substrate without depending on physical storage internals.

The prototype should use typed JSON-compatible contracts. JSON is a transport format, not the conceptual architecture.

## Execution context

Every stateful read or write runs inside an explicit execution context bound by the runtime.

A context may identify:

- world or scenario ID;
- state scope;
- application/capability version;
- observer or actor identity;
- authorization context;
- current world/scope revision.

Most of this context should not be repeated in model-generated tool arguments. The runtime should bind it when an execution begins so models cannot accidentally change world, scope, observer, or contract version simply by emitting different arguments.

Object IDs, command-specific arguments, and explicit preconditions remain part of individual calls.

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
  "object_id": "instance:world-1:alice",
  "projection": "default"
}
```

```json
{
  "op": "get_relations",
  "subject_id": "instance:world-1:alice",
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

Queries should distinguish reusable definitions from mutable instances when that distinction matters. A request for baseline construction data is not equivalent to a request for current world state.

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

The engine should prefer returning only the state relevant to the operation instead of serializing complete objects by default.

Perspective-sensitive projections are essential for preventing omniscience leakage.

Externally visible errors must also respect authorization and epistemic policy. A model-facing error should not unintentionally reveal whether a forbidden or epistemically hidden object exists.

Conceptually:

```json
{
  "object_id": "instance:world-1:alice",
  "visible": {
    "public_name": "Alice",
    "known_claims": ["claim:17"]
  }
}
```

The execution context supplies the observer, application, scope, and permissions under which this projection was computed.

## Commands and proposals

Runtime models should express semantic intent rather than directly mutating arbitrary object fields when a suitable command exists.

Prefer:

```json
{
  "op": "transfer_object",
  "command_id": "cmd:7f2c",
  "item_id": "instance:world-1:key",
  "from_id": "instance:world-1:alice",
  "to_id": "instance:world-1:ben",
  "expected_world_revision": 12
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

A persistent mutation command should include an idempotency identifier such as `command_id`. Retrying the same accepted command must return the prior committed result rather than applying the mutation again.

Commands should also state the concurrency assumptions they require. A simple implementation may use a monotonic `expected_world_revision`; more granular systems may use object/relation revisions or explicit precondition sets. The chosen semantics must be unambiguous to both validator and caller.

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
- provenance/evidence requirements;
- duplicate command detection.

Where practical, a command's related mutations should be atomic.

Committed results should make clear:

- command ID;
- whether the result is newly committed or replayed from idempotency history;
- resulting authoritative state revision;
- history/event records corresponding to the transition.

## Creation and instantiation

Creation is a normal write operation, but the protocol should distinguish reusable definition creation from world-instance creation.

A model may propose creation only through a documented capability or privileged authoring path.

A definition proposal should identify:

- target schema/type;
- baseline structured properties;
- provenance/source;
- versioning intent.

An instance proposal should identify:

- optional source definition and definition version;
- materialized instance-local state;
- instance-local relations;
- reason for creation;
- provenance/source.

The active world/scope comes from execution context unless an explicitly privileged operation is changing scope.

The engine validates the proposal before committing it.

## Scope and overlays

Writes operate inside the scope bound to execution context.

Examples of possible scopes include:

- persistent world state;
- scenario or branch state;
- application-private draft state;
- transient execution state.

Changing scope is an explicit runtime or privileged authoring operation. A model should not be able to redirect an ordinary command to a different scope by supplying an arbitrary scope identifier.

A temporary overlay must not silently mutate its parent scope. Promotion, merge, discard, or commit of overlay state should be explicit operations with validation and provenance.

An implementation may support only a subset of these scopes until experiments require more.

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
- allowed writes;
- preconditions;
- failure modes;
- examples when ambiguity warrants them.

The runtime model should not be expected to infer these contracts from database contents.

An execution remains pinned to the contract version under which it began unless an explicit migration or retry policy says otherwise.

Whether capability specification, execution, and registration are separate internal abstractions is an implementation choice; the model-facing contract should remain stable regardless.

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
- bound world/scenario/scope ID;
- application/capability version;
- observer/actor identity when applicable;
- component/role;
- model/provider identifier;
- tool calls and arguments;
- object IDs and revisions read/written;
- command/idempotency IDs;
- validation outcome;
- committed operations/events;
- resulting revisions;
- latency;
- token usage when available;
- errors/retries.

This ledger is factual runtime telemetry. Future skill discovery should analyze this ledger rather than hidden model chain-of-thought.
