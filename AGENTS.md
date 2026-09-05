# AGENTS.md

This repository is an architecture experiment. Coding agents must optimize for learning and falsifiability, not feature count.

## Required reading order

Before implementation work, read:

1. `ARCHITECTURE.md`
2. `WORLD_MODEL.md`
3. `RUNTIME_PROTOCOL.md`
4. `EVALUATION.md`
5. `ENGINESKILLS.md` when skills or meta-runtime behavior are involved
6. the active GitHub issue

Treat these documents as design constraints. If an issue conflicts with them, surface the conflict explicitly instead of silently changing the architecture.

## Core engineering rules

- Do not introduce domain concepts such as `Character`, `Combat`, `Quest`, `Twitter`, `Poker`, or `Scene` into the engine core unless an issue explicitly justifies them as generic primitives.
- Do not make raw prompt assembly the authoritative world model.
- Runtime models must not write SQL or mutate persistence directly.
- Prefer typed contracts and validated operations over free-form model output.
- Keep storage implementation separate from the model-facing protocol.
- Prefer deterministic code for exact lookup, validation, state transitions, indexing, budgeting, and bookkeeping.
- Use model reasoning only where ambiguity actually requires it.
- Do not add infrastructure such as Redis, Celery, Kafka, Neo4j, LangChain, LangGraph, or Kubernetes without evidence from a failing experiment that it is needed.
- Avoid deep classical-inheritance designs. Favor composition, explicit schemas, relations, and capabilities.
- Preserve provenance and execution traces for every experiment-relevant mutation or model/tool action.

## Prototype discipline

The repository is not an MVP product. UI polish and breadth are secondary.

Each implementation issue should answer a concrete architectural question. Prefer issues such as:

> Implement object-linked knowledge projections and test whether they prevent observer knowledge leakage.

over:

> Add memory system.

Whenever practical, add deterministic tests or fixtures that demonstrate the behavior under study.

## Model-facing design

A runtime language model should receive a narrow documented interface, not an implicit database schema. Tool and capability descriptions should be sufficiently explicit that a competent medium model can use them without reverse-engineering storage internals.

If a weaker model repeatedly fails, first inspect whether the interface can be made less ambiguous before assuming that a stronger model is required.

## Writes and mutations

Model-originated world changes should be represented as typed proposals/commands, validated by the runtime, and committed through a controlled mutation path. Direct arbitrary object replacement is acceptable only for explicitly privileged authoring/admin operations.

## Pull requests

PRs should:

- reference the motivating issue;
- state which hypothesis or behavior they implement;
- identify any architecture-doc conflict or required amendment;
- include tests where meaningful;
- avoid unrelated refactors;
- keep new abstractions as narrow as possible.

Do not update architecture documents merely to describe implementation details. Update them only when the intended architecture itself has changed.
