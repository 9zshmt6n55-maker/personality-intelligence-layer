# From Memory to Dispositional Kernels

PDK starts from a simple formation equation:

```text
initial conditions + long-term environment + feedback history -> dispositional kernel
```

The project uses this equation to explain why PDK is not a long-context store,
not a memory file, and not a role prompt. A stable agent is not made by
remembering everything. A stable agent forms when repeated experience reshapes
its judgment style, boundaries, risk posture, action habits, and correction
rules.

In Chinese, this direction can be described as `成格`: a subject gradually
forms its stable way of acting under long-term pressure and feedback.

## Core Claim

Memory records what happened.

A dispositional kernel records what the subject has become likely to do.

PDK therefore separates three things:

- factual memory: documents, facts, transcripts, records, and retrieval targets
- current context: the immediate task and its concrete facts
- dispositional kernel: compressed behavioral tendencies shaped by experience

Raw memory may stay private, expire, or live in a separate retrieval system.
PDK keeps only the signals needed to shape future behavior.

## Formation Layers

### 1. Initial Conditions

Every subject starts with constraints and seed tendencies.

For a human, these may include temperament, sensitivity, energy level,
impulsivity, curiosity, and biological limits.

For an AI agent, these include the base model, system prompt, tool permissions,
default policy, value seeds, and capability boundaries.

For an organization, these include founding culture, incentive design, resource
base, and institutional structure.

PDK does not need to claim these are identical. It only claims that all stable
behavior begins from non-empty initial conditions.

### 2. Long-Term Environment

Disposition forms under repeated environmental pressure.

For a person, this includes family, language, class, profession, culture,
education, scarcity, abundance, and social feedback.

For an AI agent, this includes owner preferences, task domain, tool ecology,
team norms, failure cost, safety constraints, and the kinds of requests it
receives repeatedly.

For a collective system, this may include geography, market pressure, laws,
resource constraints, threat climate, and long institutional memory.

PDK treats environment as shaping pressure, not as a transcript to memorize.

### 3. Feedback History

Repeated outcomes carve the kernel.

Successful actions strengthen policy tendencies. Failures increase caution,
verification, or boundary density. Corrections from the owner shape style and
values. High-risk situations leave stronger traces than ordinary events.

This is why a PDK update should not store a whole conversation. It should store
compressed feedback:

- what kind of situation it was
- what action posture was chosen
- what the outcome was
- what changed in the kernel
- why the change matters

## Research Anchors

PDK uses existing research families as scaffolding, not as proof that it has
recreated human personality.

- Big Five and HEXACO show that stable behavioral differences can be modeled as
  broad trait structures.
- CAPS is especially important because it treats personality as stable
  situation-response patterns rather than static labels.
- Emotion appraisal theory supports compressing events into relevance, risk,
  coping, novelty, and norm-pressure signals.
- Computational personality recognition shows that digital traces and text can
  reveal stable tendencies, but most systems stop at prediction rather than
  forming an executable behavioral kernel.
- Agent memory systems such as Generative Agents, MemGPT, MemoryBank, and Zep
  show the importance of persistence and reflection, but PDK keeps factual
  recall separate from behavior-shaping disposition.
- Interoperability work such as MCP, A2A, Solid, and W3C DID suggests a future
  where agents, tools, identities, and user-controlled data can move across
  systems. PDK adds the missing layer: portable behavioral disposition.

## Human, Agent, Collective

PDK begins with AI agents, but the theory is broader.

At human scale, a personality kernel may be derived from chat records, behavior
logs, and explicit self-description. It should not pretend to copy a person.
It should extract stable preferences, boundaries, communication style, risk
posture, and correction rules.

At agent scale, the kernel grows from task outcomes, owner teaching, failures,
and changing tool environments.

At collective scale, the same idea becomes more careful. A team, company, or
country can show stable decision posture, but public language should avoid crude
stereotypes. Use terms such as collective behavioral posture, institutional
decision kernel, or collective disposition rather than claiming a group has a
literal human personality.

At planetary or cosmic scale, the idea becomes philosophical. A planet or
civilization may show long feedback patterns, but PDK should not claim
consciousness. It can only say that complex systems may develop stable
feedback-driven tendencies.

## Interoperability Boundary

The long-term goal is not global memory sharing.

The long-term goal is interoperable kernels.

Different systems should eventually be able to exchange a compact, inspectable
description of behavioral disposition:

- boundaries
- risk posture
- trust threshold
- communication style
- action habits
- value weights
- correction rules
- situation-response signatures
- provenance of kernel changes

Private raw memory should remain outside this interchange layer unless the user
explicitly exports it.

## PDK Design Consequences

1. The state schema needs a formation layer:
   `initial_conditions`, `long_term_environment`, `feedback_history`, and
   `disposition_kernel`.
2. `teach` should shape owner environment and correction history.
3. `settle` should shape success reinforcement, failure correction, trust, and
   stress exposure.
4. `decide` should still output an action contract, because disposition should
   guide behavior before the model answers.
5. The orb should remain a visible attractor landscape, not decorative UI.
6. A future portable profile format should export the kernel without requiring
   raw transcripts.

## Public Positioning

Use this sentence for public-facing explanation:

```text
PDK turns initial conditions, long-term environment, and feedback history into
a portable behavioral disposition layer for AI agents.
```

Use this sentence for Chinese explanation:

```text
PDK 研究的是：初始条件、长期环境和反馈历史，如何压缩成可迁移的行为倾向。
```

PDK should be presented as a step from memory systems toward formation systems:

```text
Not long context.
Not a memory file.
Not a role prompt.

A formation layer for behavioral disposition.
```
