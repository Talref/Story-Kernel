# Decision 0001 — Interactive Kernel Slice

## Status

Accepted for Experiment 0.1a.

## Purpose

Experiment 0.1a is a vertical slice used to test Story Kernel's core interaction loop:

`human -> C -> B -> A`

This is not a production architecture commitment. The stack and UI are laboratory tooling chosen to make the smallest useful interactive experiment easy to build, inspect, reset, and change.

## Scope

The slice must support:

- a minimal persistent world substrate (A);
- a primitive model-facing capability layer (B);
- a sterile chat and inspection interface (C);
- persistent world reads and writes through B;
- conversation reset without world reset;
- world reset independent from conversation reset;
- visible execution/tool traces;
- raw and human-readable world inspection;
- import/export of the experiment's modular artifacts.

D is excluded.

## Implementation stack

Use:

- Python 3.12+
- `uv`
- Pydantic
- SQLAlchemy
- SQLite
- Typer
- Gradio
- pytest

Provide one unified launcher for the local experiment harness.

Do not add PostgreSQL, pgvector, FastAPI, React, Redis, Celery, Kafka, Neo4j, LangChain/LangGraph, Docker as a requirement, or production deployment infrastructure unless a later experiment demonstrates a need.

## Minimal A surface

Keep A deliberately small. It should persist only enough structure to test model-mediated retrieval and mutation.

Initial concepts:

- object;
- relation;
- revision/current state;
- provenance/source reference where practical;
- committed transaction/event history;
- conversation-independent persistence.

Do not introduce built-in domain concepts such as Character, Scene, Memory, Quest, Combat, or similar fiction ontology.

## Primitive B surface

B is the main subject of this experiment.

Initial capabilities should stay generic and narrow, for example:

- `create_object`
- `inspect_object`
- `search_objects`
- `set_attribute`
- `add_relation`
- `list_relations`
- `remove_relation` or an equivalent superseding operation

All state changes must pass through typed, validated operations. Runtime models must not patch storage directly.

B includes an editable application/system prompt used to define the model's operating policy. Prompt state must be stored separately from world state and conversation state.

## C — experiment interface

Use Gradio as an inspection surface, not as a product UI.

The interface should expose at minimum:

- chat;
- current model selection;
- editable B/application prompt;
- human-readable world view;
- raw structured world view;
- tool/execution trace;
- new-conversation action;
- reset-world action;
- import/export controls.

`New conversation` must clear model conversation context while preserving A.

`Reset world` must clear or reload A independently of conversation state.

The defining manual test is that after a conversation reset, the model can recover only information that was persisted in A and can update that information only through B.

## Model adapter

The runtime must keep model-provider integration behind a small adapter boundary.

Experiment 0.1a should initially support NanoGPT using an API key from `.env`.

Requirements:

- fetch the available subscription model list dynamically;
- expose it as a searchable/selectable model list in Gradio;
- pin the selected model to each conversation/run;
- record the actual model identifier in traces;
- do not store API keys in UI state, exports, or logs.

Model switching exists for later robustness testing, but development of the first slice should use a mostly fixed model for consistency.

## Exportable modules

Keep these concepts separately serializable from the beginning:

- world data;
- B capability/prompt configuration;
- model/agent configuration without secrets;
- conversation/session transcript;
- execution trace.

A temporary JSON/YAML representation is sufficient. Do not design a final package format yet.

## Execution records

Record enough information to reconstruct and inspect each turn:

- conversation/session ID;
- user message;
- active B prompt/version;
- selected model;
- model messages/input where available;
- available tool/capability schemas;
- tool calls and arguments;
- tool results;
- world reads and writes;
- revision before/after;
- committed transaction/event references;
- assistant response;
- errors/retries;
- latency and token usage when available.

Conversation history is telemetry/evidence, not authoritative world state.

## Explicit non-goals

Experiment 0.1a does not implement:

- D/meta-runtime;
- dynamic skill creation;
- roleplay behavior;
- semantic/vector RAG unless later needed to test retrieval scale;
- branching/scenarios;
- rich epistemic models;
- multi-agent orchestration;
- production authentication, networking, deployment, or scaling;
- polished product UI.

## Exit condition

The slice is useful when a human can:

1. start with an empty or minimal world;
2. tell the model persistent facts;
3. inspect what was committed;
4. ask the model to retrieve those facts;
5. correct facts and inspect the resulting update/history;
6. start a new conversation with no previous model context;
7. retrieve the persisted facts again through B;
8. compare the model's statements, tool activity, and A's actual state.

Once this loop is reliable and understandable, Experiment 0.1b can freeze fixtures and benchmark Story Kernel against prompt and RAG baselines.