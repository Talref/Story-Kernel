# World Model

The initial world model is intentionally small. The prototype should test whether a compact set of generic primitives can support many fictional domains without hardcoding those domains into the engine.

## Minimal primitives

The first implementation should center on:

- `Object`
- `Relation`
- `Event`
- `Source`
- `Schema` / type metadata

Other concepts such as `Memory`, `Belief`, `Secret`, `Character`, `Place`, `Message`, `Spell`, or `SocialPost` should initially be world-defined object types or compositions of these primitives unless an experiment demonstrates that the engine needs a dedicated primitive.

## Object

An object is an addressable unit of fictional state.

A minimal object should have:

- stable ID;
- type/schema identifier;
- schema version;
- structured data payload;
- lifecycle/status metadata where needed;
- provenance references;
- creation/update metadata.

Example shape:

```json
{
  "id": "person:alice",
  "type": "Person",
  "schema": "fixture.Person@1",
  "data": {
    "name": "Alice"
  },
  "provenance": ["source:fixture"]
}
```

The engine must not assume that `Person` is universally special.

## Relation

A relation connects objects without requiring either object to embed the other.

A minimal relation should have:

- stable ID where useful;
- subject object ID;
- predicate/type;
- object/target ID;
- optional structured metadata;
- provenance;
- validity/lifecycle information where needed.

Relations may themselves become first-class objects when they carry substantial independent state, history, or identity. A marriage, treaty, debt, employment agreement, or rivalry may eventually justify that treatment.

## Event

Events represent changes or occurrences over time.

A minimal event should support:

- stable ID;
- event type;
- time or ordering metadata;
- participants;
- affected objects;
- structured payload;
- source/provenance;
- links to resulting state changes where applicable.

Events should make it possible to answer not only "what is true now?" but also "how did it become true?"

The prototype should prefer append-oriented event history over silently overwriting all evidence of prior state.

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

## Schemas and extensibility

Worlds define their own types.

The prototype may use JSON Schema, Pydantic models, or an equivalent machine-readable representation. A dedicated language/DSL should not be designed until real usage demonstrates what syntax and semantics are needed.

Schemas should be strict enough to validate state while allowing worlds to define arbitrary domain concepts.

Avoid deep inheritance trees. Composition and capabilities are preferred.

## Knowledge and perspective

Objective event truth, observation, memory, belief, rumor, and claim are not equivalent.

For example, if Alice tells Ben "I stole the key":

- an `Event` may represent that Alice made the statement;
- a `Claim` object may represent the content of the statement;
- Ben may acquire a `Memory` or `Observation` linked to the claim;
- Ben may have a separate `Belief` with confidence and source;
- the actual theft may or may not be true.

The first fixture world should include asymmetric knowledge so that the runtime can be tested for omniscience leakage.

## Retrieval surfaces

The world model must support at least three distinct discovery paths:

1. **exact addressing** — retrieve a known object or field;
2. **relation traversal** — follow structured graph connections;
3. **semantic discovery** — find candidate objects/evidence by meaning.

Semantic discovery should normally return object/evidence identifiers that can then be inspected through authoritative structured interfaces.

## State changes

Runtime models should not replace arbitrary object JSON directly.

World-changing interactions should normally become typed commands/proposals that the runtime validates and applies.

Low-level patches may exist for privileged authoring/admin workflows.

## Branching and alternate scenarios

The architecture should not prevent future branching, retcons, or temporary scenarios. The first implementation does not need a sophisticated branch system, but choices that make historical provenance impossible should be avoided.

## Initial storage guidance

The physical database is not the conceptual model.

A prototype relational schema may use flexible tables such as:

- `objects`
- `relations`
- `events`
- `sources`
- `embeddings`
- `executions`

with JSON/JSONB payloads where useful.

Do not create one SQL table per fictional type in the first experiment.
