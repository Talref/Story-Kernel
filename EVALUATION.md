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

## Baselines

At minimum compare:

1. **Monolithic prompt** — relevant world material supplied as one text context.
2. **Text RAG** — chunked prose/lore retrieved semantically and injected.
3. **Object runtime** — typed world state navigated through exact, relational, and semantic tools.

Later experiments may add variants such as graph-enhanced memory, gap resolution, or dynamic capabilities.

## Runtime model matrix

Do not validate the architecture only with frontier models.

Use at least:

- a weaker/cheap model where practical;
- a competent medium tool-using model as the primary target;
- a frontier model as a ceiling/reference.

Keep the model fixed when comparing successive engine versions whenever possible. Improvement under a fixed model is stronger evidence that the architecture is helping.

## Deterministic metrics

Prefer deterministic assertions whenever the expected answer is structured.

Measure examples such as:

- correct object/entity resolution;
- correct current state;
- observer knowledge leakage;
- chronology errors;
- invalid mutations;
- schema violations;
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

The first suite should include scenarios such as:

- exact state lookup;
- relation-dependent query;
- old-memory callback;
- secret/knowledge asymmetry;
- incorrect belief vs objective truth;
- semantically discoverable event;
- new object/state mutation;
- missing structural fact;
- irrelevant-lore resistance.

Different "modes" can initially be simulated as different requesting applications/observers without building real UIs.

## Falsification criteria

The architecture should be reconsidered if, after reasonable interface tuning:

- object/tool retrieval is not materially more accurate than text RAG;
- medium models cannot navigate the interface without frequent frontier-model rescue;
- structured state creates more continuity errors than it prevents;
- the context compiler still needs to dump large portions of the world into prompts;
- model-originated mutations remain too unreliable to validate safely;
- the generic object model requires pervasive domain-specific exceptions;
- latency/cost increases substantially without corresponding consistency gains.

Failure is a useful result. Do not hide negative experimental outcomes by adding complexity until the original hypothesis becomes untestable.

## Evidence discipline

Every experiment should record:

- engine commit/version;
- fixture version;
- model/provider and relevant settings;
- execution trace;
- produced context packet;
- output;
- deterministic results;
- evaluator result where used;
- human notes where relevant.

A GitHub issue should state what question an experiment is intended to answer before implementation begins.
