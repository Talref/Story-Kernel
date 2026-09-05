# Engine Skills

A skill is a reusable, bounded execution procedure that reduces repeated general reasoning while preserving explicit state behavior.

This file defines what Story Kernel means by a skill. World-specific skill catalogs may evolve later, but this doctrine should remain engine-owned and comparatively stable.

## A skill is

A skill should have:

- a clear reusable purpose;
- typed inputs and outputs;
- declared tools/capabilities it may call;
- explicit reads and writes where relevant;
- failure behavior;
- validation rules;
- an execution strategy;
- a cost/latency profile where useful;
- enough evidence that formalizing the procedure is preferable to solving each case ad hoc.

A skill may be implemented by:

- deterministic code;
- retrieval/query logic;
- a small or medium model;
- a reasoning model;
- a hybrid of deterministic and model-assisted steps.

A skill is not necessarily a prompt.

## A skill is not

Do not create skills merely because an action has a name.

Examples that usually should not become skills by themselves:

- smiling;
- opening an ordinary door;
- looking out a window;
- drinking tea;
- one-off descriptive gestures.

A skill is also not:

- a hidden chain-of-thought recipe;
- a vague persona prompt;
- a raw lore blob;
- a duplicate of an already adequate generic capability;
- a domain abstraction added only because a model once mentioned it.

## When a capability gap appears

Novel interactions should be handled at the lowest adequate level:

1. **Generic execution** — existing primitives/capabilities are sufficient.
2. **Ad-hoc reasoning** — solve the current instance without creating a permanent skill.
3. **Skill/capability extension** — formalize a reusable procedure because repeated or mechanically meaningful behavior benefits from consistency.

Examples likely to justify formalization include poker, chess, a recurring combat ruleset, a stock market simulation, farming mechanics, or a court procedure.

## Evidence for skill creation

The future Skill Manager must not rely on intuition alone or hidden model reasoning.

The runtime should first produce an immutable factual execution ledger containing things such as:

- components invoked;
- tools called;
- arguments;
- objects read/written;
- results;
- failures/retries;
- latency and token usage.

A Skill Manager may analyze windows of this ledger and propose candidates.

A proposal should cite supporting executions and, where possible:

- recurring operation sequence;
- common inputs/outputs;
- meaningful variations;
- near-misses/counterexamples;
- expected benefit from formalization;
- whether deterministic implementation can replace model reasoning.

Human review should remain available because models can over-detect patterns.

## Desired lifecycle

Skills should allow intelligence to be compiled out of routine runtime work over time.

A procedure may evolve from:

`strong model + broad tools`

into:

`medium model + narrow tools`

and eventually, where appropriate:

`deterministic mechanics + model only for subjective decisions/rendering`

Mature worlds should therefore have the possibility of becoming cheaper, faster, and more consistent as their vocabulary stabilizes.

## Permissions

Skills must declare capabilities rather than receiving unrestricted access by default.

Potential permission families may include:

- world read;
- world write proposal;
- world write commit;
- schema read/write;
- source access;
- model invocation;
- network access;
- filesystem/process access.

The exact permission system is not fixed by this document, but privilege should be explicit and reviewable.

## Dynamic meta-runtime

Layer D may create or revise skills at runtime under world/author policy.

Possible policies include:

- automatic creation for safe/local skills;
- proposal + review;
- ad-hoc resolution only;
- ignore unsupported mechanics;
- forbid unsupported mechanics.

Dynamic creation must not imply uncontrolled ontology or skill growth. Reusability and consistency benefit are central criteria.

## Prototype scope

Do not implement a full Skill Manager in the first world-core experiment.

The first prototype should produce the execution ledger and keep the runtime/tool boundaries compatible with future skill analysis. Dynamic skill creation becomes a later experiment after persistent world access and mutation have been validated.
