# World Model

The world model defines the persistent structures from which applications derive fictional state. It is intentionally small: the kernel should provide generic semantics for identity, state, relations, history, provenance, validation, and scope without hardcoding a universal fiction ontology.

## Minimal primitives

The core model centers on:

- `ObjectDefinition`
- `ObjectInstance`
- `Relation`
- `Event`
- `Source`
- `Schema` / type metadata

Other concepts such as `Memory`, `Belief`, `Secret`, `Character`, `Place`, `Message`, `Spell`, or `SocialPost` should normally be world-defined object types or compositions of these primitives unless repeated evidence shows that the engine needs additional built-in semantics.

## Definition and instance

A reusable definition and a living world instance are distinct concepts.

An `ObjectDefinition` is immutable, versioned construction input. It provides reusable baseline data, provenance, and type information from which an `ObjectInstance` may be created. It is not trans-world runtime identity and does not participate in live world state.

An `ObjectInstance` is an authoritative, world-local realization inside a specific world or scenario. It carries current mutable state, revision metadata, and links to the history that produced that state.

A definition may exist without any active instance. An instance may also be created without a reusable definition when the world creates something unique.

Instantiation materializes the selected definition version into instance state. Runtime reads should operate on materialized instance state rather than implicitly merging the current definition with instance overrides. Existing instances do not change when a definition is revised unless an explicit migration operation is performed.

This distinction supports:

- clean reuse across independent worlds;
- exporting baseline definitions separately from evolved state;
- reproducible instantiation from versioned sources;
- alternate scenarios without mutating unrelated worlds;
- multiple applications operating on the same world instance without cloning it.

Definitions should be versionable. Existing instances remain pinned to the definition version from which they were created unless an explicit migration policy is applied.

## Object definition

A minimal definition should support:

- stable definition ID;
- type/schema identifier;
- schema version;
- baseline structured data;
- provenance references;
- definition version;
- creation/update metadata.

Example shape:

```json
{
  "id": "definition:alice",
  "type": "Person",
  "schema": "fixture.Person@1",
  "version": 1,
  "data": {
    "name": "Alice"
  },
  "provenance": ["source:fixture"]
}
```

The engine must not assume that `Person` is universally special.

Definitions should not directly relate to mutable instances or mutable world state. If reusable relational templates are introduced later, their instantiation and materialization rules must be explicit rather than implied by graph traversal.

## Object instance

A minimal instance should support:

- stable instance ID;
- world/scope identifier;
- optional definition ID and definition version;
- type/schema identifier;
- current structured state;
- revision number or participation in an enclosing world revision;
- provenance for instance-local creation;
- creation/update metadata.

Example shape:

```json
{
  "id": "instance:world-1:alice",
  "world_id": "world:1",
  "definition_id": "definition:alice",
  "definition_version": 1,
  "schema": "fixture.Person@1",
  "revision": 7,
  "state": {
    "name": "Alice",
    "location": "instance:world-1:library"
  }
}
```

An instance's current state is the authoritative runtime representation for that instance within its scope.

## State scopes

Persistent world truth and temporary application state are not the same thing.

The architecture should support explicit scopes, even if an implementation supports only a subset. Typical scopes include:

- reusable definition scope;
- persistent world-instance scope;
- scenario or branch scope;
- application/session overlay scope;
- transient execution state.

A scope must have a clear parent or ownership relationship and a clear commit policy. Temporary overlays should not silently become authoritative world state.

Applications may share the same world instance while maintaining private draft or transient state of their own.

Most runtime context should bind the active world and scope outside individual model-generated tool arguments. Scope changes are explicit runtime operations, not incidental fields a model is expected to repeat correctly on every call.

## Relations

A relation connects runtime instances without requiring either endpoint to embed the other.

A mutable authoritative relation should have:

- stable relation ID;
- scope;
- subject instance ID;
- predicate/type;
- target instance ID;
- optional structured metadata;
- provenance;
- validity/lifecycle information where needed;
- revision/version metadata where mutation is allowed.

Definitions do not participate directly in mutable runtime relations. Reusable relational construction data, if supported, must be materialized into instance-local relations during an explicit instantiation or migration operation.

Relations may themselves become first-class objects when they carry substantial independent state, history, or identity. A marriage, treaty, debt, employment agreement, or rivalry may justify that treatment.

For any given invariant, the engine should designate one authoritative representation. The same fact should not be simultaneously authoritative in both embedded object state and relation state unless a rigorously specified consistency rule exists.

## Events and current state

Events represent changes or occurrences over time.

A minimal event should support:

- stable ID;
- scope/world ID;
- event type;
- time or ordering metadata;
- participants;
- affected objects;
- structured payload;
- source/provenance;
- transaction or command reference;
- links to the revisions or state changes it produced.

The kernel must distinguish two questions:

- **What is true now?** — answered from authoritative current state.
- **How did it become true?** — answered from committed history.

The persistence strategy may use snapshots plus an append-only transaction/event log, full event sourcing, or another rigorously specified model. Whichever strategy is chosen must define a single authoritative rule for resolving current truth and must not permit silent disagreement between state and history.

A deployment should also define the concurrency revision unit used for stale-write detection. This may be a monotonic world/scope revision, object/relation revisions, or explicit precondition sets, but command semantics must make the choice unambiguous.

The initial implementation should favor the simplest strategy that preserves deterministic current-state reads, revision checks, and auditable history.

## Source and provenance

The engine should preserve where information came from.

Sources may include:

- authored world data;
- imported lore;
- conversation turns;
- generated content;
- inferred/derived facts;
- external documents;
- author corrections.

Derived state should be distinguishable from explicitly authored state where practical.

Provenance is evidence about origin, not proof of truth. Assertion status, confidence, and derivation policy should be modeled separately when a world needs them.

## Schemas and extensibility

Worlds define their own types.

The prototype may use JSON Schema, Pydantic models, or an equivalent machine-readable representation. A dedicated language/DSL should not be designed until real usage demonstrates what syntax and semantics are needed.

Schemas should be strict enough to validate state while allowing worlds to define arbitrary domain concepts.

The kernel should own non-domain invariants such as:

- stable identity;
- schema/version validation;
- referential integrity;
- transaction atomicity;
- revision/concurrency rules;
- event/state consistency;
- provenance integrity;
- scope isolation;
- deterministic validation of permitted transitions.

Avoid deep inheritance trees. Composition and capabilities are preferred.

## Knowledge and perspective

Objective event truth, observation, memory, belief, rumor, claim, and secrecy are not equivalent.

For example, if Alice tells Ben "I stole the key":

- an `Event` may represent that Alice made the statement;
- a `Claim` object may represent the content of the statement;
- Ben may acquire a `Memory` or `Observation` linked to the claim;
- Ben may have a separate `Belief` with confidence and source;
- the actual theft may or may not be true.

The kernel should not silently collapse these categories into a single `known_by` flag. Worlds may define richer epistemic structures, but projections and capabilities must have deterministic rules for which structured facts they expose.

Secrecy should normally be represented through distribution, visibility, policy, or knowledge state rather than assuming that `Secret` is always an intrinsic engine primitive.

## Missing and derived information

Absence of a value must have explicit semantics where it matters.

A schema, field, or capability may define policies such as:

- closed-world absence / invalid;
- unknown;
- infer for the current operation only;
- propose an authored invention;
- persist derived state;
- require approval.

Generated provenance or confidence does not by itself make invented information authoritative.

## Retrieval surfaces

The world model must support at least three distinct discovery paths:

1. **exact addressing** — retrieve a known object, instance, relation, or field;
2. **relation traversal** — follow structured graph connections;
3. **semantic discovery** — find candidate objects/evidence by meaning.

Semantic discovery should normally return identifiers that can then be inspected through authoritative structured interfaces.

Semantic indexes are derived access paths, not primary world truth.

## State changes

Runtime models should not replace arbitrary object JSON directly.

World-changing interactions should normally become typed commands/proposals that the runtime validates and applies against the active execution context and declared preconditions.

Low-level patches may exist for privileged authoring/admin workflows.

A valid state transition should identify what it changes, which prior state it assumes, and with what provenance or triggering command.

## Branching and alternate scenarios

The architecture should support independent world instances and leave room for branching, retcons, overlays, and temporary scenarios.

A branch or scenario should derive from an explicit source state or revision and maintain its own subsequent state/history until a deliberate merge, promotion, or discard operation occurs.

An implementation does not need a sophisticated branch system until experiments require it, but object identity and scope rules should not make later isolation impossible.

## Initial storage guidance

The physical database is not the conceptual model.

A prototype relational schema may use flexible tables such as:

- `definitions`
- `instances`
- `relations`
- `events`
- `sources`
- `embeddings`
- `executions`

with JSON/JSONB payloads where useful.

A simpler implementation may combine some of these physically as long as their conceptual distinctions remain explicit.

Do not create one SQL table per fictional type in the first experiment.
