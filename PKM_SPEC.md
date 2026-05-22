# PKM v1 Specification

PKM means **Personality Kernel Model**.

The goal is not to store long context. The goal is to turn experience into
behavioral disposition.

```text
Memory remembers what happened.
PKM changes what the agent becomes.
```

## Model Boundary

PKM is responsible for:

- stable traits
- current affective state
- values
- motives
- owner relationship model
- behavior policy weights
- formation state
- situation prototypes
- growth traces
- visible personality morphology

PKM is not responsible for:

- exact facts
- document retrieval
- codebase context
- legal records
- full chat history

Those belong to task context, databases, files, or audit systems.

## Runtime Flow

```text
event
-> appraisal vector
-> latent personality state
-> policy arbitration
-> behavior posture for the LLM/tool layer
-> outcome feedback
-> latent update
-> formation update
-> visible morphology update
-> raw detail may be forgotten
```

## Latent State

The latent state is a high-dimensional adaptive state. The current prototype
stores it as JSON for inspectability, but the design is compatible with binary
vectors or tensors later.

Groups:

- `traits`: long-term personality tendencies
- `affect`: short-term emotional state
- `motives`: approach/avoidance and drive system
- `values`: value priorities
- `relation_owner`: how the agent relates to its owner
- `policy`: action-selection biases

## Formation Layer

PDK adds a formation layer above ordinary latent weights:

```text
initial_conditions + long_term_environment + feedback_history -> disposition_kernel
```

This layer exists because stable behavior is not only a trait snapshot. It is
the result of seed constraints, repeated environment, and outcome feedback.

Top-level state group:

- `formation.initial_conditions`: base model, temperament seed, value seed, and capability boundary
- `formation.long_term_environment`: owner environment, task pressure, tool ecology, social pressure, and risk climate
- `formation.feedback_history`: success reinforcement, failure correction, owner correction, trust feedback, and stress exposure
- `formation.disposition_kernel`: stability, plasticity, boundary density, risk posture, and interoperability readiness

`teach` primarily shapes owner environment and correction history. `settle`
primarily shapes success, failure, trust, and stress traces. The raw transcript
does not enter the formation layer. Only compressed appraisal and outcome
signals enter it.

## Appraisal Vector

Each event is compressed into an appraisal vector:

- risk
- urgency
- ambiguity
- conflict
- insult
- overpromise
- opportunity
- technical
- boundary_violation
- irreversibility
- social_cost
- owner_instruction
- correction
- praise
- trust_signal

This is intentionally not a memory entry. It is a low-dimensional signal used
to update the personality kernel.

## Policy Arbitration

The kernel does not output text directly. It outputs a behavior posture:

- verify before acting
- clarify boundaries
- act directly
- set a firm boundary
- de-escalate
- refuse unsafe request
- ask owner
- take reversible small step
- explore/probe
- support and stabilize

The LLM receives the posture and current task facts, then expresses and acts.

Before posture selection, PKM derives a small dynamics vector from the appraisal:

- familiarity: whether this resembles prior compressed prototypes
- novelty: how much untrained territory the event activates
- arousal: urgency, threat, conflict, and stress pressure
- valence: positive or negative motivational tone
- coping: current ability to handle the situation
- norm pressure: safety, privacy, dignity, and boundary pressure
- prediction error: mismatch between known patterns and current event
- inhibitory gate: restraint applied to direct or exploratory action

Policy arbitration then combines baseline policy, current appraisal, prototype
feedback, and this dynamics vector. This makes the action posture closer to a
resultant force than a fixed rules table.

## Visible Morphology

The visible model starts as a sphere. As the agent is taught and tested, the
sphere deforms.

Visual mapping:

- region area: behavioral weight / attractor territory
- region height: activation strength
- region curvature: tension, ambiguity, and inner conflict
- region boundary: stability and conflict separation
- region force: current influence on the next behavior posture
- region facets: fine-grained sub-dispositions inside one broad trait
- expansion: strengthened behavioral disposition
- contraction: weakened disposition
- outer shell: boundaries and public behavior
- middle layer: policy and habits
- affect layer: emotional state
- core: stable values
- anchor points: visible personality directions
- latent potential field: low-activity personality seeds before training
- growth path: latest update through the model

The visible body is therefore not a decorative sphere. It is a spherical
attractor landscape. When an event arrives, its appraisal vector activates
regions on this landscape. Behavior is selected by the competition between:

- region area
- region height
- region force
- fine-grained facets
- current affective tension
- owner training
- policy weight
- outcome history

## Region Facets

Broad labels are not enough. Each behavior region is decomposed into smaller
facets. For example, verification can split into fact checking, cost checking,
and rollback checking. Boundary can split into dignity, permission, and tone
control. Exploration can split into hypothesis probing, creative probing, and
technical search.

These facets do not create more on-screen text by default. They appear as
surface detail and are revealed when the user hovers or selects a region.

## New-Agent Shape

A new agent is not a blank sphere. It is a low-differentiation personality body:
all major behavior seeds exist at low contrast, borders are soft, and no region
dominates yet. Empty-looking space should be rendered as latent potential, not
as absence.

As interactions accumulate, entropy decreases, differentiation rises, and
stable regions become larger, higher, and sharper.

## Research Foundation

PKM uses research families as engineering constraints:

- Big Five / Big Five aspects: broad traits are hierarchical, not flat labels.
- HEXACO: integrity and manipulation resistance deserve a separate axis.
- CAPS: personality is a stable set of situation-response signatures, not only global trait labels.
- Circumplex affect: emotion is encoded through valence and arousal.
- Component appraisal: events become relevance, implication, coping, and norm signals.
- Reinforcement learning: outcomes update policy bias over time.
- Predictive regulation / active inference: novelty and uncertainty create pressure.
- Computational personality recognition: digital traces can expose stable tendencies, but PDK turns them into executable disposition rather than only a score.
- Agent memory systems: reflection and retrieval remain separate from the behavior-shaping kernel.
- Interoperability protocols: portable agent identity needs a disposition format, not only tool calls and raw data exchange.

## Multi-Form Traits

PKM must not reduce human-like traits to one scalar. A trait such as
confidence can appear in different forms:

- calibrated confidence: broad, stable, low-roughness, evidence-aligned
- execution confidence: forward and action-biased
- exploratory confidence: tied to curiosity and reversible probing
- social confidence: tied to trust, support, and relationship stability
- boundary confidence: firm but controlled
- defensive confidence: narrow, high, rough, stress-colored

The visible body encodes these forms separately:

- area: how much territory this form occupies
- height: current activation strength
- roughness: instability or defensive distortion
- color: value/emotion tone
- stability: whether the form is mature or brittle

This makes the agent's development visible without exposing long chat history.

## Forgetting Rule

Raw events can be discarded after they update the kernel.

PKM keeps:

- event fingerprint
- compressed appraisal tags
- chosen behavior posture
- outcome
- latent deltas
- formation deltas
- visible deltas
- short growth reason

PKM does not need:

- full conversation transcript
- full event text
- every intermediate thought

## Open Source Positioning

PKM should be presented as:

> A visible adaptive personality layer for AI agents. It turns experience into
> behavioral disposition instead of storing endless context.
