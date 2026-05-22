#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pkm
from pkm_signal import write_signal


ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = ROOT / "agents"
DEFAULT_BACKUP_NAME = "PIL_PERSONALITY_BACKUP.md"
RESERVED_PROFILE_NAMES = {"default", "legacy", "legacy-default", "main", "root"}

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


@dataclass(frozen=True)
class ProfilePaths:
    slug: str
    root: Path
    state_dir: Path
    public_dir: Path
    backup: Path
    state: Path
    fresh_state: Path
    visible: Path
    signal: Path
    runtime_mode: Path
    meta: Path


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def clean_slug(value: str, fallback: str = "") -> str:
    raw = value.strip().lower()
    raw = re.sub(r"\([^)]*\)", " ", raw)
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if slug:
        return slug[:48]
    fallback = re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-")
    return fallback[:48] if fallback else "agent"


def profile_paths(slug: str) -> ProfilePaths:
    slug = clean_slug(slug)
    if slug in RESERVED_PROFILE_NAMES:
        raise ValueError(
            f"{slug!r} is reserved for the root legacy state. Use a real agent profile name, "
            "or run OPEN_LEGACY_DEFAULT only for the root state."
        )
    root = AGENTS_ROOT / slug
    state_dir = root / "state"
    public_dir = root / "public"
    return ProfilePaths(
        slug=slug,
        root=root,
        state_dir=state_dir,
        public_dir=public_dir,
        backup=root / DEFAULT_BACKUP_NAME,
        state=state_dir / "agent.pkm.json",
        fresh_state=state_dir / "fresh_test_agent.pkm.json",
        visible=public_dir / "pkm_visible.json",
        signal=state_dir / "orb_signal.json",
        runtime_mode=state_dir / "runtime_mode.json",
        meta=root / "profile.json",
    )


def ensure_profile_dirs(paths: ProfilePaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    paths.public_dir.mkdir(parents=True, exist_ok=True)


def find_backup(explicit: Path | None = None) -> Path:
    if explicit:
        if explicit.exists():
            return explicit.resolve()
        raise FileNotFoundError(f"backup not found: {explicit}")
    desktop = Path.home() / "Desktop"
    candidates = [
        ROOT / DEFAULT_BACKUP_NAME,
        desktop / DEFAULT_BACKUP_NAME,
        ROOT / "imports" / DEFAULT_BACKUP_NAME,
    ]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise FileNotFoundError("PIL_PERSONALITY_BACKUP.md not found")
    return max(existing, key=lambda path: path.stat().st_mtime).resolve()


def slug_from_backup(backup: dict[str, Any], backup_text: str, override: str = "") -> str:
    if override:
        return clean_slug(override)
    explicit_slug = str(backup.get("profile_slug") or "").strip()
    if explicit_slug:
        return clean_slug(explicit_slug, "pil-" + pkm.text_fingerprint(backup_text)[:8])
    source = backup.get("source_agent") if isinstance(backup.get("source_agent"), dict) else {}
    name = str(source.get("name") or "").strip()
    if name:
        return clean_slug(name, "pil-" + pkm.text_fingerprint(backup_text)[:8])
    return "pil-" + pkm.text_fingerprint(backup_text)[:8]


def write_profile_meta(paths: ProfilePaths, state: dict[str, Any], source_backup: Path | None = None) -> None:
    manifest = state.get("manifest", {})
    previous_source = ""
    if source_backup is None and paths.meta.exists():
        try:
            previous_source = str(json.loads(paths.meta.read_text(encoding="utf-8")).get("source_backup", ""))
        except Exception:
            previous_source = ""
    payload = {
        "schema": "pil.profile.v1",
        "slug": paths.slug,
        "agent_id": manifest.get("agent_id", paths.slug),
        "name": manifest.get("name", paths.slug),
        "stage": manifest.get("development_stage", ""),
        "interaction_count": manifest.get("interaction_count", 0),
        "state": str(paths.state.relative_to(ROOT)),
        "visible": str(paths.visible.relative_to(ROOT)),
        "signal": str(paths.signal.relative_to(ROOT)),
        "backup": str(paths.backup.relative_to(ROOT)),
        "source_backup": str(source_backup) if source_backup else previous_source,
    }
    paths.meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def deterministic_position(slug: str) -> tuple[int, int]:
    seed = int(pkm.text_fingerprint(slug), 16)
    return 80 + seed % 420, 80 + (seed // 17) % 280


def launch_profile(paths: ProfilePaths, compact: bool = True, x: int | None = None, y: int | None = None) -> None:
    script = ROOT / "launch_personality_observatory.ps1"
    if x is None or y is None:
        x0, y0 = deterministic_position(paths.slug)
        x = x if x is not None else x0
        y = y if y is not None else y0
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-AgentId",
        paths.slug,
        "-Visible",
        str(paths.visible),
        "-Signal",
        str(paths.signal),
        "-X",
        str(x),
        "-Y",
        str(y),
    ]
    if compact:
        args.append("-Compact")
    subprocess.run(args, cwd=str(ROOT), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restore_backup(backup_path: Path | None, profile: str = "", open_orb: bool = False, compact: bool = True) -> dict[str, Any]:
    source = find_backup(backup_path)
    backup_text = source.read_text(encoding="utf-8-sig")
    backup = pkm.load_personality_backup(source)
    slug = slug_from_backup(backup, backup_text, profile)
    paths = profile_paths(slug)
    ensure_profile_dirs(paths)
    paths.backup.write_text(backup_text, encoding="utf-8")
    state = pkm.default_state()
    pkm.apply_personality_backup(state, backup, merge=False)
    pkm.save_state(paths.state, state)
    visible = pkm.export_visible(state, paths.visible)
    paths.runtime_mode.write_text(json.dumps({"mode": "continue"}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_signal(False, paths.signal)
    write_profile_meta(paths, state, source)
    if open_orb:
        launch_profile(paths, compact=compact)
    return {
        "ok": True,
        "profile": paths.slug,
        "name": state["manifest"].get("name"),
        "state": str(paths.state),
        "visible": str(paths.visible),
        "signal": str(paths.signal),
        "stage": visible.get("agent", {}).get("stage"),
        "formation_kernel": visible.get("model", {}).get("formation", {}).get("disposition_kernel", {}),
        "opened": bool(open_orb),
    }


def state_path(paths: ProfilePaths, mode: str) -> Path:
    return paths.fresh_state if mode == "fresh" else paths.state


def boot_profile(profile: str, mode: str = "continue", reset: bool = False, open_orb: bool = True, compact: bool = True) -> dict[str, Any]:
    paths = profile_paths(profile)
    ensure_profile_dirs(paths)
    state_file = state_path(paths, mode)
    if reset or not state_file.exists():
        pkm.init_state(state_file, force=True)
    state = pkm.load_state(state_file)
    pkm.export_visible(state, paths.visible)
    paths.runtime_mode.write_text(json.dumps({"mode": mode}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_signal(False, paths.signal)
    write_profile_meta(paths, state)
    if open_orb:
        launch_profile(paths, compact=compact)
    return {
        "ok": True,
        "profile": paths.slug,
        "mode": mode,
        "state": str(state_file),
        "visible": str(paths.visible),
        "opened": bool(open_orb),
    }


def list_profiles() -> list[dict[str, Any]]:
    if not AGENTS_ROOT.exists():
        return []
    rows: list[dict[str, Any]] = []
    for meta_path in sorted(AGENTS_ROOT.glob("*/profile.json")):
        try:
            rows.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except Exception:
            rows.append({"slug": meta_path.parent.name, "error": "profile.json unreadable"})
    return rows


def profile_runtime(profile: str, mode: str | None = None) -> tuple[ProfilePaths, str, Path, dict[str, Any]]:
    paths = profile_paths(profile)
    ensure_profile_dirs(paths)
    if mode is None:
        try:
            payload = json.loads(paths.runtime_mode.read_text(encoding="utf-8"))
            mode = str(payload.get("mode", "continue"))
        except Exception:
            mode = "continue"
    if mode not in {"fresh", "continue"}:
        mode = "continue"
    state_file = state_path(paths, mode)
    if not state_file.exists():
        pkm.init_state(state_file, force=True)
    return paths, mode, state_file, pkm.load_state(state_file)


def decide(profile: str, text: str) -> dict[str, Any]:
    paths, mode, state_file, state = profile_runtime(profile)
    write_signal(True, paths.signal)
    try:
        result = pkm.decide(state, text)
        pkm.export_visible(state, paths.visible, runtime=result.get("orb_runtime"))
        result["runtime"] = {"profile": paths.slug, "mode": mode, "state": str(state_file), "visible": str(paths.visible)}
        return result
    finally:
        write_signal(False, paths.signal)


def teach(profile: str, text: str) -> dict[str, Any]:
    paths, mode, state_file, state = profile_runtime(profile)
    write_signal(True, paths.signal)
    try:
        result = pkm.teach(state, text)
        pkm.save_state(state_file, state)
        pkm.export_visible(state, paths.visible)
        write_profile_meta(paths, state)
        result["runtime"] = {"profile": paths.slug, "mode": mode, "state": str(state_file)}
        return result
    finally:
        write_signal(False, paths.signal)


def settle(profile: str, text: str, outcome: str, note: str) -> dict[str, Any]:
    paths, mode, state_file, state = profile_runtime(profile)
    write_signal(True, paths.signal)
    try:
        result = pkm.settle(state, text, outcome, note)
        pkm.save_state(state_file, state)
        pkm.export_visible(state, paths.visible)
        write_profile_meta(paths, state)
        result["runtime"] = {"profile": paths.slug, "mode": mode, "state": str(state_file)}
        return result
    finally:
        write_signal(False, paths.signal)


def main() -> int:
    parser = argparse.ArgumentParser(description="PIL multi-agent profile manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_restore = sub.add_parser("restore-backup")
    p_restore.add_argument("backup", nargs="?", type=Path)
    p_restore.add_argument("--profile", default="")
    p_restore.add_argument("--open", action="store_true")
    p_restore.add_argument("--observatory", action="store_true", help="start opened in the large observatory")

    p_boot = sub.add_parser("boot")
    p_boot.add_argument("--profile", required=True)
    p_boot.add_argument("--mode", choices=["fresh", "continue"], default="continue")
    p_boot.add_argument("--reset", action="store_true")
    p_boot.add_argument("--no-open", action="store_true")
    p_boot.add_argument("--observatory", action="store_true")

    sub.add_parser("list")

    p_open_all = sub.add_parser("open-all")
    p_open_all.add_argument("--observatory", action="store_true")

    p_decide = sub.add_parser("decide")
    p_decide.add_argument("--profile", required=True)
    p_decide.add_argument("text")

    p_teach = sub.add_parser("teach")
    p_teach.add_argument("--profile", required=True)
    p_teach.add_argument("text")

    p_settle = sub.add_parser("settle")
    p_settle.add_argument("--profile", required=True)
    p_settle.add_argument("text")
    p_settle.add_argument("--outcome", required=True, choices=["success", "failure", "mixed"])
    p_settle.add_argument("--note", default="")

    args = parser.parse_args()
    if args.command == "restore-backup":
        print_json(restore_backup(args.backup, args.profile, args.open, compact=not args.observatory))
        return 0
    if args.command == "boot":
        print_json(boot_profile(args.profile, args.mode, args.reset, open_orb=not args.no_open, compact=not args.observatory))
        return 0
    if args.command == "list":
        print_json({"profiles": list_profiles()})
        return 0
    if args.command == "open-all":
        profiles = list_profiles()
        for row in profiles:
            slug = str(row.get("slug", "")).strip()
            if slug:
                boot_profile(slug, mode="continue", reset=False, open_orb=True, compact=not args.observatory)
        print_json({"opened": [row.get("slug") for row in profiles]})
        return 0
    if args.command == "decide":
        print_json(decide(args.profile, args.text))
        return 0
    if args.command == "teach":
        print_json(teach(args.profile, args.text))
        return 0
    if args.command == "settle":
        print_json(settle(args.profile, args.text, args.outcome, args.note))
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print_json({"ok": False, "error": str(exc)})
        raise SystemExit(2)
