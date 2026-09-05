# Evaluation

Story Kernel is an architecture experiment. The prototype succeeds only if it produces evidence about the central hypothesis.

## Central hypothesis

A persistent typed world exposed through explicit tools/capabilities should let a competent tool-using language model retrieve and mutate fictional state more reliably than prompt-centric or text-RAG approaches, without requiring a frontier model for routine runtime operation.

## First experiment

Build a deliberately small fixture world containing enough asymmetry and history to expose common failures.

Suggested ingredients:

- 4–6 people;
- 3–4 locations;
- 1–2 organizations;
- several items;
- 8–15 events;
- asymmetric memories/beliefs;
- at least 2 secrets;
- at least one incorrect belief;
- at least one fact discoverable semantically but not by obvious keyword overlap;
- at least one state-changing interaction.

The fixture should be artificial and deterministic. Entertainment value is irrelevant.

Before tuning tool descriptions or retrieval behavior, freeze:

- canonical fixture facts;
- epistemic/visibility rules used by the fixture;
- scenario inputs;
- expected answers or state transitions;
- baseline materialization rules;
- success/failure criteria.

## Matched comparison principle

All comparison arms must derive from the same canonical fixture rather than independently authored representations.

At minimum compare:

1. **Monolithic prompt** — deterministic textual rendering of the canonical facts.
2. **Text RAG** — deterministic text chunks generated from those same facts, retrieved semantically.
3. **Object runtime** — the same facts represented as typed state and navigated through exact, relational, and semantic tools.

To avoid confounding, comparison arms should use, where applicable:

- the same model/version/settings;
- comparable instructions and context budgets;
- the same final typed answer or command schema;
- the same mutation validator;
- the same embedding model and semantic retrieval limit when semantic retrieval is used;
- isolated copies of mutable fixture state.

A result is not evidence for the object substrate if the object arm wins only because it received richer manually authored facts, bespoke answers encoded into capabilities, or a stronger validation contract unavailable to the baselines.

Later experiments may add variants such as graph-enhanced memory, gap resolution, or dynamic capabilities.

## Runtime model matrix

Do not validate the architecture only with frontier models.

Use at least:

- a weaker/cheap model where practical;
- a competent medium tool-using model as the primary target;
- a frontier model as a ceiling/reference.

Keep the model fixed when comparing successive engine versions whenever possible. Improvement under a fixed model is stronger evidence that the architecture is helping.

Development-time frontier-model assistance and runtime-model cost should be recorded separately when both are involved.

## Deterministic metrics

Prefer deterministic assertions whenever the expected answer is structured.

Measure examples such as:

- correct object/entity resolution;
- correct current state;
- observer knowledge leakage;
- chronology errors;
- invalid mutations;
- schema violations;
- stale-write rejection;
- idempotent retry behavior;
- missed required objects/events;
- unnecessary retrieved objects;
- number of tool calls;
- invalid tool arguments;
- recovery from empty/failed retrieval;
- context size;
- latency;
- token usage/cost where available.

## Model-based evaluation

A frontier evaluator may judge dimensions difficult to encode deterministically, including:

- whether relevant world facts were used naturally;
- semantic continuity;
- character voice;
- prose quality;
- stiffness/repetition;
- whether retrieved information was relevant rather than merely present.

Whenever possible, evaluations should be blind to which architecture produced the candidate output.

LLM judgments are evidence, not ground truth. They should complement deterministic checks and human review.

## Human evaluation

Human review remains important for actual fiction quality.

Record observations such as:

- which answer feels most coherent;
- whether callbacks feel natural rather than forced;
- whether the engine surfaces irrelevant lore;
- whether the model appears constrained or confused by the interface;
- whether correcting world state is understandable.

## Initial scenario classes

The first suite should include balanced scenario classes such as:

- exact state lookup;
- relation-dependent query;
- chronology/current-state query;
- secret/knowledge asymmetry;
- incorrect belief vs objective truth;
- semantically discoverable event;
- valid state mutation;
- invalid or stale state mutation;
- irrelevant-lore resistance.

Different "modes" can initially be simulated as different requesting applications/observers without building real UIs.

Missing structural facts, dynamic capability creation, branching, and meta-runtime repair should be evaluated separately rather than introduced into the first matched benchmark.

## Ablations

Where practical, include ablations that reveal what part of the architecture is providing value.

Useful examples include:

- disable semantic search on exact and relation-only tasks;
- replace structured inspection output with equivalent prose;
- give text-RAG the same final command schema and mutation validator;
- measure how often the object runtime returns or compiles large opaque prose fields;
- compare generic capabilities against increasingly task-specific ones.

If structured state provides no advantage once validation or representation quality is controlled, that is an important negative result.

## Falsification criteria

The architecture should be reconsidered if, after reasonable interface tuning:

- object/tool retrieval is not materially more accurate than text RAG;
- medium models cannot navigate the interface without frequent frontier-model rescue;
- structured state creates more continuity errors than it prevents;
- the context compiler still needs to dump large portions of the world into prompts;
- model-originated mutations remain too unreliable to validate safely;
- the generic object model requires pervasive domain-specific exceptions;
- the object arm wins only when supplied with highly bespoke capabilities that encode task answers;
- latency/cost increases substantially without corresponding consistency gains.

Failure is a useful result. Do not hide negative experimental outcomes by adding complexity until the original hypothesis becomes untestable.

## Evidence discipline

Every experiment should record:

- engine commit/version;
- fixture version;
- baseline/materialization version;
- model/provider and relevant settings;
- execution trace;
- produced context packet;
- output;
- deterministic results;
- evaluator result where used;
- human notes where relevant.

A GitHub issue should state what question an experiment is intended to answer before implementation begins.
