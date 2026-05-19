# Personality Drive Kernel

**Personality Drive Kernel (PDK)** is a growable personality-driven kernel layer for AI agents.

It is built around a simple observation:

```text
Humans forget details, but they retain shaped behavior.
```

A person may forget many past events, yet still knows how to respond when a similar situation appears. The experience has not disappeared. It has been compressed into personality, judgment, boundaries, habits, and risk posture.

PDK applies the same idea to AI agents. Instead of relying on long context forever, it distills interaction history into a persistent layer that guides decisions, communication style, risk handling, behavioral consistency, and future growth.

中文说明见 [README.zh-CN.md](README.zh-CN.md).

> Note: some files still use the earlier `PIL_*` naming for compatibility. The public concept name is now **PDK: Personality Drive Kernel**.

## Why This Exists

Most AI agent systems depend on one of three mechanisms:

- long context windows
- memory files full of past facts
- static role prompts

Those mechanisms are useful, but they are not the same as a durable behavioral core.

Long context tries to keep the past alive by carrying more text. PDK takes another path: it treats past experience as material that should reshape the agent. After an interaction updates the kernel, the raw detail can often be forgotten.

The goal is not:

```text
Remember everything that happened.
```

The goal is:

```text
Become the kind of agent that knows how to act when something similar happens again.
```

## Theoretical Grounding

PDK is inspired by modern personality psychology and cognitive science, especially:

- **Big Five / Five-Factor Model**: personality can be described through broad trait dimensions such as openness, conscientiousness, extraversion, agreeableness, and neuroticism.
- **HEXACO**: adds honesty-humility and offers another trait structure for social behavior, restraint, and cooperation.
- **Temperament and character theories**: distinguish more stable response tendencies from learned values and self-regulation.
- **CAPS, the Cognitive-Affective Personality System**: behavior is shaped by situation-sensitive patterns, not only fixed traits.
- **Appraisal theories of emotion**: emotional response can be modeled as evaluations of novelty, risk, goal relevance, control, and social meaning.
- **Decision and control theory**: action can be viewed as the result of competing forces, constraints, priorities, and feedback.

PDK does not claim to perfectly reproduce human personality. It uses these theories as design scaffolding for an agent kernel: traits, drives, values, emotional baselines, risk sensitivity, boundaries, relationship models, situation prototypes, and correction rules.

## What Makes It Different

PDK is not a chatbot prompt. It is not a folder of memories. It is not a role-play card.

It is a profile system that separates raw experience from shaped behavioral state.

Core advantages:

- **Context-light continuity**: old conversations can be distilled into behavior-shaping state instead of being pasted back forever.
- **Personality-driven decisions**: the kernel participates in how the agent judges, speaks, refuses, verifies, takes risks, and acts.
- **Agent identity as a profile**: each agent lives in `agents/<profile>/`, so multiple agents can run side by side without overwriting each other.
- **Old-agent migration**: a mature agent can generate `PIL_PERSONALITY_BACKUP.md`, then a new session can restore that backup into a working profile.
- **Visible personality state**: the desktop orb and observatory show growth, domains, activity, and changes instead of hiding the model in a black box.
- **Behavior arbitration**: decisions are influenced by competing signals such as caution, directness, trust, autonomy, curiosity, boundaries, and risk sensitivity.
- **Forgetting is intentional**: PDK treats forgetting raw details as a feature. The state should preserve behavioral lessons, not hoard every transcript.
- **Protocol plus runtime**: if the local Python runtime is available, PDK can write state and show the orb. If not, the Markdown protocol still tells an agent how to restore, back up, and act.

## What This Repository Contains

- `pkm.py` - personality kernel model, appraisal, policy arbitration, growth updates, visible export.
- `pil_profiles.py` - multi-agent profile manager. Each agent has isolated state, visible output, signal file, and metadata.
- `pkm_runtime.py` - runtime entrypoint for boot, decide, teach, and settle operations.
- `desktop_orb.py` - transparent desktop personality orb and observatory UI.
- `PIL_UNIVERSAL_AGENT_LAYER.md` - drop-in protocol for new agents, old-agent self-backup, and backup restore.
- `PIL_OLD_AGENT_BACKUP_WORKSHEET.md` - detailed worksheet for generating higher-quality old-agent backups.
- `00_AGENT_READ_ME_FIRST.md` - mandatory operating rules for agents before they run commands.
- `给代理看的使用说明.md` - short Chinese usage guide for agents.

## First-Time Use

Run commands from the project folder:

```powershell
cd <PDK_ROOT>
```

Install Python 3 if needed, then create a new profile:

```powershell
python .\pil_profiles.py boot --profile test-agent --mode fresh --reset
```

Open that profile later without resetting it:

```powershell
python .\pil_profiles.py boot --profile test-agent --mode continue
```

Teach the profile from a correction or preference:

```powershell
python .\pkm_runtime.py teach --profile test-agent "When risk is high, verify first and avoid overpromising."
```

Ask the profile for a behavioral decision:

```powershell
python .\pkm_runtime.py decide --profile test-agent "The user asks for a fast but risky shortcut."
```

List all profiles:

```powershell
python .\pil_profiles.py list
```

Open all saved profile orbs:

```powershell
python .\pil_profiles.py open-all
```

## Restoring An Old Agent

Old agents should not write a short self-description. That is too weak to restore behavior.

They should produce a structured backup:

```text
PIL_PERSONALITY_BACKUP.md
```

Use this worksheet:

```text
PIL_OLD_AGENT_BACKUP_WORKSHEET.md
```

Then restore it:

```powershell
python .\pil_profiles.py restore-backup .\PIL_PERSONALITY_BACKUP.md --open
```

The restore command creates an isolated profile under `agents/<profile>/`. It should not overwrite another agent.

## Profile Model

Every durable agent must live in its own profile:

```text
agents/<profile>/
  PIL_PERSONALITY_BACKUP.md
  profile.json
  state/agent.pkm.json
  state/orb_signal.json
  state/runtime_mode.json
  public/pkm_visible.json
```

The root `state/agent.pkm.json` is legacy-only. Do not use it as the normal identity boundary.

## Desktop Orb Controls

- Middle click: expand or collapse observatory mode.
- Hover in observatory mode: inspect domains.
- Drag the sphere in observatory mode: rotate the model.
- Mouse wheel: resize.
- Right click: settings menu.

The orb is a visible model of the profile state. A fresh agent starts close to an even sphere. As the profile grows, domain weights, colors, texture, activity, and prominence can change.

## Recommended Agent Workflow

When another AI agent receives this repository, it should first read:

```text
00_AGENT_READ_ME_FIRST.md
```

Then choose one path:

```text
New agent from zero       -> create a fresh named profile
Old agent self-backup     -> fill PIL_OLD_AGENT_BACKUP_WORKSHEET.md
Restore existing backup   -> restore PIL_PERSONALITY_BACKUP.md into a profile
Open existing profile     -> list profiles, then boot the selected profile in continue mode
```

Do not run `fresh --reset` unless the user explicitly asks for a new agent from zero.

## Git Safety

Runtime profiles and backups are private by default. They are ignored by `.gitignore`:

```text
agents/*
state/*.json
public/pkm_visible.json
PIL_PERSONALITY_BACKUP.md
backups/
imports/feishu/
```

Before publishing, read:

```text
RELEASE_CHECKLIST.md
```

## Current Scope

This version uses deterministic heuristics for appraisal and policy arbitration. That is intentional. The first target is the architecture:

- personality as adaptive state
- behavior as policy arbitration
- growth as visible deformation
- raw detail as discardable after update
- each agent profile as an isolated identity boundary

Future versions can replace or extend the appraisal layer with an LLM, classifier, embedding model, trained encoder, or larger simulation model.

## Design References

For related work and design references around agent state, persistence, and memory systems, see:

```text
DESIGN_REFERENCES.md
```
