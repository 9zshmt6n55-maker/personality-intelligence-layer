# 00_AGENT_READ_ME_FIRST

Read this file before running commands.

This project implements PDK, the Personality Drive Kernel: a persistent, inspectable, growing personality-driven kernel layer for AI agents.

PDK treats personality as formation:

```text
initial conditions + long-term environment + feedback history -> behavioral disposition kernel
```

Some runtime files still use the earlier `PIL_*` names for compatibility. Treat those files as PDK backup/protocol files.

The project is not a long-context store, not a raw memory dump, and not a role-play prompt. Each agent must have its own durable profile.

## Work Directory

Run commands from the repository or deployed PDK folder:

```text
<PDK_ROOT>
```

Do not search the entire machine. Do not use old drop-in files from backups. Do not infer paths from another user's local machine.

## Identity Boundary

Every durable agent must live in one profile:

```text
agents/<profile>/
  PIL_PERSONALITY_BACKUP.md
  profile.json
  state/agent.pkm.json
  state/orb_signal.json
  state/runtime_mode.json
  public/pkm_visible.json
```

The root `state/agent.pkm.json` is legacy-only. Do not use it as a long-term identity boundary.

Reserved profile names:

```text
default
legacy
legacy-default
main
root
```

## Safe Entrypoints

Prefer the English entrypoints. They avoid encoding problems with localized filenames.

### Restore An Old Agent Backup

```text
RESTORE_BACKUP_AS_PROFILE.cmd
```

Equivalent command:

```powershell
python .\pil_profiles.py restore-backup .\PIL_PERSONALITY_BACKUP.md --open
```

This imports the backup into `agents/<profile>/` and opens that profile's orb. It must not overwrite other profiles.

### Open All Profiles

```text
OPEN_ALL_PROFILES.cmd
```

Equivalent command:

```powershell
python .\pil_profiles.py open-all
```

### Open One Profile

```text
OPEN_PROFILE.cmd
```

Equivalent command example:

```powershell
python .\pil_profiles.py boot --profile example-agent --mode continue
```

### Create A Fresh Profile

```text
NEW_PROFILE_FRESH.cmd
```

Equivalent command example:

```powershell
python .\pil_profiles.py boot --profile test-agent --mode fresh --reset
```

Only use this when the user explicitly asks for a new agent from zero.

### Legacy Root State

```text
OPEN_LEGACY_DEFAULT.cmd
```

This opens the root `state/agent.pkm.json`. It is for migration/debug only. It is not guaranteed to be the user's old agent. If the root state contains an imported backup, the script refuses to open unless forced.

## Forbidden Operations

Never stop all Python processes.

Never stop all `desktop_orb.py` processes.

Do not run broad commands like:

```powershell
Stop-Process -Name python
```

or:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'desktop_orb.py' } |
  Stop-Process
```

If you must restart an orb, restart only the same profile by matching `--agent-id` or the exact `--visible` path.

## Task Routing

### User says: restore/import/read a backup

Find `PIL_PERSONALITY_BACKUP.md`, then run:

```powershell
python .\pil_profiles.py restore-backup <backup-path> --open
```

Do not ask the user to restate the agent's identity. Read identity, style, owner relation, and state from the backup.

### User says: open an existing profile

Run:

```powershell
python .\pil_profiles.py list
```

Then open the requested profile:

```powershell
python .\pil_profiles.py boot --profile <profile> --mode continue
```

### User says: old agent self-backup

Read:

```text
PIL_OLD_AGENT_BACKUP_WORKSHEET.md
```

The old agent should fill the worksheet and produce `PIL_PERSONALITY_BACKUP.md`.

### User says: new agent from zero

Create a fresh named profile:

```powershell
python .\pil_profiles.py boot --profile <new-profile> --mode fresh --reset
```

## Personality-Driven Answer Loop

Before answering a meaningful user task, ask the selected profile for a decision:

```powershell
python .\pkm_runtime.py decide --profile <profile> "<current user task>"
```

Then answer according to:

- `action_contract.winner_label`
- `action_contract.answer_shape`
- `action_contract.avoid`
- `action_contract.active_domains`
- `action_contract.formation_kernel`
- `llm_directive`

Do not paste the JSON to the user unless asked. The personality layer should change judgment, tone, risk handling, boundary strength, and action style. Treat `formation_kernel` as compressed disposition, not as factual memory.

After the task has an outcome, update the profile:

```powershell
python .\pkm_runtime.py settle --profile <profile> "<same task>" --outcome success --note "<short result>"
```

Use `mixed` or `failure` instead of `success` when appropriate. This is what turns the orb from a visual object into a decision-and-growth layer.

## Verification Commands

List profiles:

```powershell
python .\pil_profiles.py list
```

Inspect orb processes:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'desktop_orb\.py' } |
  Select-Object ProcessId,CommandLine
```

Each profile orb should have:

```text
--agent-id <profile>
--visible agents\<profile>\public\pkm_visible.json
--signal agents\<profile>\state\orb_signal.json
```

## Reporting Standard

After an operation, report:

- profile name
- state file path
- visible file path
- whether the orb was opened
- whether any root legacy state was touched

If unsure, stop and reread this file plus `PIL_UNIVERSAL_AGENT_LAYER.md`.
