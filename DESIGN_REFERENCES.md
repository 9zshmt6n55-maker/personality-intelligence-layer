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

### 5. Do not publish private runtime data

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

- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- AutoGen AgentChat state save/load: https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/state.html
- Letta context hierarchy: https://docs.letta.com/guides/core-concepts/memory/context-hierarchy/
- Letta MemFS git-backed memory: https://docs.letta.com/letta-code/memfs/
- CrewAI memory: https://docs.crewai.com/en/concepts/memory
