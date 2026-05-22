# Design References

This project is not a clone of any existing memory framework, but the final profile logic follows several patterns that are already common in agent systems.

## Lessons Applied

### 1. Persist state explicitly

Agent identity must survive process restarts through explicit state save/load, not through hidden chat context.

Applied here:

```text
agents/<profile>/state/agent.pkm.json
agents/<profile>/public/pkm_visible.json
agents/<profile>/state/orb_signal.json
```

### 2. Keep profile scope isolated

One agent profile must not overwrite another agent's state or UI signal.

Applied here:

```text
--agent-id <profile>
--visible agents/<profile>/public/pkm_visible.json
--signal agents/<profile>/state/orb_signal.json
```

### 3. Treat root legacy state as migration-only

The root `state/agent.pkm.json` is ambiguous once old-agent backups are imported. Long-term identity belongs under `agents/<profile>/`.

Applied here:

- `default`, `legacy`, `main`, and `root` are reserved profile names.
- `OPEN_LEGACY_DEFAULT` refuses to open root state if it contains an imported PIL backup unless forced.

### 4. Make memory inspectable and portable

Backups should be file-based and inspectable. They should not rely on a hidden server context.

Applied here:

```text
PIL_PERSONALITY_BACKUP.md
PIL_OLD_AGENT_BACKUP_WORKSHEET.md
profile.json
```

### 5. Separate memory from formation

PDK should not treat old chat logs as the personality itself. Raw memory,
retrieval stores, and documents can support an agent, but the kernel should
store compressed disposition: boundaries, risk posture, action habits,
correction rules, and situation-response signatures.

Applied here:

```text
formation.initial_conditions
formation.long_term_environment
formation.feedback_history
formation.disposition_kernel
```

The design target is:

```text
initial conditions + long-term environment + feedback history -> behavioral disposition
```

### 6. Keep portable kernels smaller than private histories

Future interop should exchange a compact, auditable behavioral profile, not a
dump of raw transcripts. A profile can carry provenance, compressed signals,
and correction rules while keeping private source records outside the exchange
boundary.

Applied here:

```text
PDK_THEORY.md
growth_trace[].formation_delta
export_visible().model.formation
```

### 7. Do not publish private runtime data

Personal profiles are derived from private conversations and task history. They are ignored by Git by default.

Applied here:

```text
agents/*
state/*.json
public/pkm_visible.json
PIL_PERSONALITY_BACKUP.md
backups/
imports/feishu/
```

## External References

### Personality and Formation Theory

- CAPS / Cognitive-Affective Personality System: https://doi.org/10.1037/0033-295X.102.2.246
- HEXACO Personality Inventory: https://hexaco.org/
- Computational personality recognition from language: https://doi.org/10.1016/j.jrp.2006.10.003
- Digital records and private traits: https://www.pnas.org/doi/10.1073/pnas.1218772110

### Agent Memory and Persistence

- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- AutoGen AgentChat state save/load: https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/state.html
- Letta context hierarchy: https://docs.letta.com/guides/core-concepts/memory/context-hierarchy/
- Letta MemFS git-backed memory: https://docs.letta.com/letta-code/memfs/
- CrewAI memory: https://docs.crewai.com/en/concepts/memory
- Generative Agents: https://arxiv.org/abs/2304.03442
- MemGPT: https://arxiv.org/abs/2310.08560
- MemoryBank: https://arxiv.org/abs/2305.10250

### Interoperability and User-Controlled Data

- Model Context Protocol: https://modelcontextprotocol.io/docs
- Agent2Agent Protocol: https://github.com/a2aproject/A2A
- Solid Protocol: https://solidproject.org/TR/protocol
- W3C DID Core: https://www.w3.org/TR/did-1.0/
