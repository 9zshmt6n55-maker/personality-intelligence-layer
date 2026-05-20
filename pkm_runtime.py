#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pkm
from pil_profiles import ensure_profile_dirs, launch_profile, profile_paths
from pkm_signal import write_signal


ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / "state" / "agent.pkm.json"
FRESH_STATE = ROOT / "state" / "fresh_test_agent.pkm.json"
RUNTIME_MODE = ROOT / "state" / "runtime_mode.json"
DEFAULT_VISIBLE = ROOT / "public" / "pkm_visible.json"
DEFAULT_SIGNAL = ROOT / "state" / "orb_signal.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def normalize_profile(profile: str) -> str:
    value = str(profile or "").strip()
    if value.lower() in {"default", "legacy", "legacy-default", "main", "root"}:
        return ""
    return value


def paths_for(profile: str, mode: str) -> tuple[Path, Path, Path, Path, Any]:
    profile = normalize_profile(profile)
    if profile:
        paths = profile_paths(profile)
        ensure_profile_dirs(paths)
        state = paths.fresh_state if mode == "fresh" else paths.state
        return state, paths.runtime_mode, paths.visible, paths.signal, paths
    state = FRESH_STATE if mode == "fresh" else DEFAULT_STATE
    return state, RUNTIME_MODE, DEFAULT_VISIBLE, DEFAULT_SIGNAL, None


def state_path_for_mode(mode: str, profile: str = "") -> Path:
    profile = normalize_profile(profile)
    if profile:
        return paths_for(profile, mode)[0]
    return FRESH_STATE if mode == "fresh" else DEFAULT_STATE


def write_mode(mode: str, profile: str = "") -> None:
    profile = normalize_profile(profile)
    _, runtime_mode, _, _, _ = paths_for(profile, mode)
    runtime_mode.parent.mkdir(parents=True, exist_ok=True)
    runtime_mode.write_text(json.dumps({"mode": mode}, ensure_ascii=False, indent=2), encoding="utf-8")


def read_mode(profile: str = "") -> str:
    profile = normalize_profile(profile)
    runtime_mode = profile_paths(profile).runtime_mode if profile else RUNTIME_MODE
    try:
        payload = json.loads(runtime_mode.read_text(encoding="utf-8"))
        mode = str(payload.get("mode", "continue"))
    except Exception:
        mode = "continue"
    return mode if mode in {"fresh", "continue"} else "continue"


def load_runtime_state(profile: str = "") -> tuple[str, Path, Path, Path, dict[str, Any]]:
    profile = normalize_profile(profile)
    mode = read_mode(profile)
    path, _, visible, signal, _ = paths_for(profile, mode)
    if mode == "fresh" and not path.exists():
        pkm.init_state(path, force=True)
    if not path.exists():
        pkm.init_state(path, force=True)
    return mode, path, visible, signal, pkm.load_state(path)


def run_boot(mode: str, reset: bool = False, profile: str = "", compact: bool = False) -> int:
    profile = normalize_profile(profile)
    path, _, visible, signal, profile_paths_obj = paths_for(profile, mode)
    if mode == "fresh" and reset:
        pkm.init_state(path, force=True)
    elif not path.exists():
        pkm.init_state(path, force=True)
    state = pkm.load_state(path)
    pkm.export_visible(state, visible)
    write_mode(mode, profile)
    if profile and profile_paths_obj is not None:
        launch_profile(profile_paths_obj, compact=compact)
    else:
        script = ROOT / "launch_personality_observatory.ps1"
        if not script.exists():
            script = ROOT / "launch_desktop_pet.ps1"
        args = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-AgentId",
            "default",
            "-Visible",
            str(visible),
            "-Signal",
            str(signal),
        ]
        if compact:
            args.append("-Compact")
        subprocess.run(args, cwd=str(ROOT), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    write_signal(False, signal)
    print_json({"ok": True, "profile": profile or "default", "mode": mode, "state": str(path), "visible": str(visible), "ball": "start_requested"})
    return 0


def run_decide(text: str, profile: str = "") -> int:
    profile = normalize_profile(profile)
    _, _, _, signal, _ = paths_for(profile, read_mode(profile))
    write_signal(True, signal)
    try:
        mode, path, visible, _, state = load_runtime_state(profile)
        result = pkm.decide(state, text)
        pkm.export_visible(state, visible, runtime=result.get("orb_runtime"))
        result["runtime"] = {"profile": profile or "default", "mode": mode, "state": str(path), "visible": str(visible)}
        print_json(result)
    finally:
        write_signal(False, signal)
    return 0


def run_teach(text: str, profile: str = "") -> int:
    profile = normalize_profile(profile)
    _, _, _, signal, _ = paths_for(profile, read_mode(profile))
    write_signal(True, signal)
    try:
        mode, path, visible, _, state = load_runtime_state(profile)
        result = pkm.teach(state, text)
        pkm.save_state(path, state)
        pkm.export_visible(state, visible)
        result["runtime"] = {"profile": profile or "default", "mode": mode, "state": str(path), "visible": str(visible)}
        print_json(result)
    finally:
        write_signal(False, signal)
    return 0


def run_settle(text: str, outcome: str, note: str, profile: str = "") -> int:
    profile = normalize_profile(profile)
    _, _, _, signal, _ = paths_for(profile, read_mode(profile))
    write_signal(True, signal)
    try:
        mode, path, visible, _, state = load_runtime_state(profile)
        result = pkm.settle(state, text, outcome, note)
        pkm.save_state(path, state)
        pkm.export_visible(state, visible)
        result["runtime"] = {"profile": profile or "default", "mode": mode, "state": str(path), "visible": str(visible)}
        print_json(result)
    finally:
        write_signal(False, signal)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast PKM runtime entrypoint for Codex tests")
    sub = parser.add_subparsers(dest="command", required=True)
    p_boot = sub.add_parser("boot")
    p_boot.add_argument("--mode", choices=["fresh", "continue"], default="continue")
    p_boot.add_argument("--reset", action="store_true", help="reset the selected state before booting")
    p_boot.add_argument("--profile", default="", help="agent profile slug under agents/<profile>")
    p_boot.add_argument("--compact", action="store_true", help="start as a small desktop ball")
    p_decide = sub.add_parser("decide")
    p_decide.add_argument("--profile", default="")
    p_decide.add_argument("text")
    p_teach = sub.add_parser("teach")
    p_teach.add_argument("--profile", default="")
    p_teach.add_argument("text")
    p_settle = sub.add_parser("settle")
    p_settle.add_argument("--profile", default="")
    p_settle.add_argument("text")
    p_settle.add_argument("--outcome", required=True, choices=["success", "failure", "mixed"])
    p_settle.add_argument("--note", default="")

    args = parser.parse_args()
    if args.command == "boot":
        return run_boot(args.mode, args.reset, args.profile, args.compact)
    if args.command == "decide":
        return run_decide(args.text, args.profile)
    if args.command == "teach":
        return run_teach(args.text, args.profile)
    if args.command == "settle":
        return run_settle(args.text, args.outcome, args.note, args.profile)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
