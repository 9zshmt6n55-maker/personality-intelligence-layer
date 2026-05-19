# Release Checklist

Before publishing this repository:

1. Do not commit private runtime profiles:

```text
agents/*
state/*.json
public/pkm_visible.json
PIL_PERSONALITY_BACKUP.md
backups/
imports/feishu/
```

2. Keep only code, docs, and templates in Git.

3. Run:

```powershell
python -m py_compile .\pkm.py .\pkm_runtime.py .\pil_profiles.py .\desktop_orb.py .\pkm_signal.py
```

4. Create a test profile locally:

```powershell
python .\pil_profiles.py boot --profile test-agent --mode fresh --reset --no-open
python .\pil_profiles.py list
```

5. Restore a backup only into a profile:

```powershell
python .\pil_profiles.py restore-backup .\PIL_PERSONALITY_BACKUP.md --open
```

6. Never use the root legacy state as a long-term identity boundary. The open-source path is:

```text
agents\<profile>\state\agent.pkm.json
agents\<profile>\public\pkm_visible.json
agents\<profile>\state\orb_signal.json
```

7. If `git` is available, inspect before committing:

```powershell
git status --short
git check-ignore -v agents\example-agent\state\agent.pkm.json
git check-ignore -v PIL_PERSONALITY_BACKUP.md
```

The repository should not contain personal agent backups or private conversation-derived state.
