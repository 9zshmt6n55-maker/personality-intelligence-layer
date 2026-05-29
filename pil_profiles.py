#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import time
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
    orb_session: Path
    orb_ready: Path
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


def gateway_agent_id(value: str, fallback: str = "") -> str:
    raw = (value or fallback or "").strip().lower()
    raw = re.sub(r"\([^)]*\)", " ", raw)
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return slug[:80] if slug else "agent"


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
        orb_session=state_dir / "orb_session.json",
        orb_ready=state_dir / "orb_ready.json",
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


def record_orb_session(paths: ProfilePaths, launch_kind: str = "personality_orb", ready_receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    state = pkm.load_state(paths.state)
    visible = json.loads(paths.visible.read_text(encoding="utf-8-sig"))
    session = pkm.create_orb_launch_session(state, paths.slug, visible, launch_kind=launch_kind, ready_receipt=ready_receipt)
    paths.orb_session.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pkm.save_state(paths.state, state)
    return session


def wait_for_orb_ready(paths: ProfilePaths, timeout_seconds: float = 8.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if paths.orb_ready.exists():
            try:
                receipt = json.loads(paths.orb_ready.read_text(encoding="utf-8-sig"))
            except Exception:
                receipt = {}
            if (
                receipt.get("schema") == "pdk.desktop_orb_ready.v1"
                and str(receipt.get("agent_id") or "") == paths.slug
                and Path(str(receipt.get("visible") or "")).resolve() == paths.visible.resolve()
            ):
                return receipt
        time.sleep(0.20)
    raise RuntimeError("personality orb did not report ready; entry proof was not generated")


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
        "-Ready",
        str(paths.orb_ready),
        "-X",
        str(x),
        "-Y",
        str(y),
    ]
    if compact:
        args.append("-Compact")
    if paths.orb_ready.exists():
        paths.orb_ready.unlink()
    if paths.orb_session.exists():
        paths.orb_session.unlink()
    subprocess.run(args, cwd=str(ROOT), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ready_receipt = wait_for_orb_ready(paths)
    record_orb_session(paths, launch_kind="compact_personality_orb" if compact else "personality_observatory", ready_receipt=ready_receipt)


def sign_entry_challenge(profile: str, challenge_json: Path) -> dict[str, Any]:
    paths = profile_paths(profile)
    if not paths.state.exists() or not paths.visible.exists():
        raise FileNotFoundError("profile state and pkm_visible.json are required before signing entry challenge")
    if not paths.orb_session.exists():
        raise FileNotFoundError("orb_session.json not found; run pil_profiles.py boot --profile <profile> --observatory first")
    state = pkm.load_state(paths.state)
    visible = json.loads(paths.visible.read_text(encoding="utf-8-sig"))
    orb_session = json.loads(paths.orb_session.read_text(encoding="utf-8-sig"))
    session_check = pkm.verify_orb_launch_session(orb_session, visible)
    if not session_check.get("ok"):
        raise RuntimeError("; ".join(session_check.get("errors", [])))
    challenge = json.loads(challenge_json.read_text(encoding="utf-8-sig"))
    challenge_body = challenge.get("challenge") if isinstance(challenge.get("challenge"), dict) else challenge
    challenge_agent_id = gateway_agent_id(str(challenge_body.get("agent_id") or ""), "")
    visible_agent_id = gateway_agent_id(str((visible.get("agent") if isinstance(visible.get("agent"), dict) else {}).get("id") or ""), "")
    profile_agent_id = gateway_agent_id(paths.slug)
    if visible_agent_id and profile_agent_id != visible_agent_id:
        raise RuntimeError(
            "profile slug does not match pkm_visible.agent.id after gateway normalization; "
            f"profile={paths.slug} maps to {profile_agent_id}, pkm_visible.agent.id maps to {visible_agent_id}. "
            "Use the profile that owns this pkm_visible.json."
        )
    if challenge_agent_id and visible_agent_id and challenge_agent_id != visible_agent_id:
        raise RuntimeError(
            "challenge agent_id does not match this profile's pkm_visible.agent.id; "
            f"challenge={challenge_agent_id}, pkm_visible.agent.id={visible_agent_id}. "
            "Request a new /api/external/challenge with the same agent_id as pkm_visible.agent.id."
        )
    proof = pkm.sign_external_entry_challenge(state, challenge, orb_session=orb_session)
    pkm.save_state(paths.state, state)
    return {
        "ok": True,
        "profile": paths.slug,
        "entry_proof": proof,
        "orb_session": str(paths.orb_session),
    }


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
    pkm.save_state(paths.state, state)
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
    pkm.save_state(state_file, state)
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


def _count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _unit(value: Any, fallback: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return fallback


def _coverage(keys: list[str], values: Any) -> dict[str, Any]:
    payload = values if isinstance(values, dict) else {}
    present = [key for key in keys if key in payload]
    return {
        "present": len(present),
        "total": len(keys),
        "missing": [key for key in keys if key not in payload],
    }


def _has_structured_content(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _top_level_coverage(backup: dict[str, Any]) -> dict[str, Any]:
    required = [
        "source_agent",
        "evidence",
        "maturity",
        "latent",
        "formation",
        "voice_signature",
        "relationship_owner",
        "relationship_graph",
        "visual_personality_ball",
        "situation_prototypes",
        "failure_modes",
        "correction_rules",
        "calibration_questions",
    ]
    present = []
    latent = backup.get("latent") if isinstance(backup.get("latent"), dict) else {}
    for key in required:
        if _has_structured_content(backup.get(key)):
            present.append(key)
        elif key == "relationship_owner" and _has_structured_content(latent.get("relation_owner")):
            present.append(key)
    return {
        "present": len(present),
        "total": len(required),
        "missing": [key for key in required if key not in present],
    }


def inspect_backup(backup_path: Path | None) -> dict[str, Any]:
    source = find_backup(backup_path)
    backup = pkm.load_personality_backup(source)
    source_agent = backup.get("source_agent") if isinstance(backup.get("source_agent"), dict) else {}
    evidence = backup.get("evidence") if isinstance(backup.get("evidence"), dict) else {}
    maturity = backup.get("maturity") if isinstance(backup.get("maturity"), dict) else {}
    latent = backup.get("latent") if isinstance(backup.get("latent"), dict) else {}
    formation = backup.get("formation") if isinstance(backup.get("formation"), dict) else {}
    checks = {
        "traits": _coverage(list(pkm.TRAITS), latent.get("traits")),
        "affect": _coverage(list(pkm.AFFECT), latent.get("affect") or latent.get("affect_baseline")),
        "motives": _coverage(list(pkm.MOTIVES), latent.get("motives")),
        "values": _coverage(list(pkm.VALUES), latent.get("values")),
        "relation_owner": _coverage(list(pkm.RELATION_OWNER), latent.get("relation_owner")),
        "policy": _coverage(list(pkm.POLICY), latent.get("policy")),
        "style": _coverage(list(pkm.STYLE), latent.get("style")),
    }
    formation_checks = {
        group: _coverage(list(pkm.FORMATION_MODEL[group]), formation.get(group))
        for group in ("initial_conditions", "long_term_environment", "feedback_history", "disposition_kernel")
    }
    top_level_checks = _top_level_coverage(backup)
    warnings: list[str] = []
    stage_hint = str(maturity.get("stage", maturity.get("phase", ""))).lower()
    is_new_shaping = backup.get("backup_type") == "new_agent_shaping_backup" or stage_hint in {"early", "shaping", "early_shaping"}
    if not backup.get("profile_slug"):
        warnings.append("缺少 profile_slug；导入时建议显式指定 --profile，避免名字推断不稳定。")
    prototype_min = 6 if is_new_shaping else 8
    if _count_list(backup.get("situation_prototypes")) < prototype_min:
        warnings.append(f"情境原型少于 {prototype_min} 个；导入后可观察性不足。")
    if _count_list(backup.get("failure_modes")) < 3:
        warnings.append("失败模式不足；恢复后最容易不像原代理。")
    if _count_list(backup.get("correction_rules")) < 3:
        warnings.append("纠偏规则不足；用户调教痕迹没有充分进入内核。")
    if _count_list(backup.get("calibration_questions")) < 5:
        warnings.append("校准问题不足；导入后难以快速验证是否像原代理。")
    if not formation:
        warnings.append("缺少 formation 成格层；会由程序推断，但质量低于老代理亲自填写。")
    weak_groups = [name for name, row in checks.items() if row["present"] < max(1, row["total"] // 2)]
    if weak_groups:
        warnings.append("latent 覆盖不足：" + ", ".join(weak_groups))
    explicit_formation_fields = sum(row["present"] for row in formation_checks.values())
    if explicit_formation_fields < 8:
        warnings.append("成格字段少于 8 个；建议补充初始条件、长期环境、反馈历史和行为倾向内核。")
    if top_level_checks["missing"]:
        warnings.append("迁移层字段缺失：" + ", ".join(top_level_checks["missing"]))

    latent_present = sum(row["present"] for row in checks.values())
    latent_total = sum(row["total"] for row in checks.values()) or 1
    formation_total = sum(row["total"] for row in formation_checks.values()) or 1
    score = 0.0
    score += 10.0 if backup.get("schema") == "pil.personality_backup.v1" else 0.0
    score += (latent_present / latent_total) * 25.0
    score += min(15.0, _count_list(backup.get("situation_prototypes")) / 12.0 * 15.0)
    score += min(10.0, _count_list(backup.get("failure_modes")) * 2.0)
    score += min(10.0, _count_list(backup.get("correction_rules")) * 2.0)
    score += min(10.0, _count_list(backup.get("calibration_questions")) * 1.5)
    score += (explicit_formation_fields / formation_total) * 12.0
    score += (top_level_checks["present"] / max(1, top_level_checks["total"])) * 5.0
    score += _unit(evidence.get("evidence_confidence"), 0.0) * 5.0
    score += _unit(maturity.get("maturity_score"), 0.0) * 3.0
    score = int(round(max(0.0, min(100.0, score))))

    return {
        "ok": True,
        "backup": str(source),
        "schema": backup.get("schema", ""),
        "profile_slug": backup.get("profile_slug", ""),
        "source_agent": {
            "name": source_agent.get("name", ""),
            "role": source_agent.get("role", ""),
            "primary_use_cases": source_agent.get("primary_use_cases", []),
        },
        "evidence": {
            "estimated_interactions": evidence.get("estimated_interactions", 0),
            "evidence_confidence": evidence.get("evidence_confidence", 0),
            "limits": evidence.get("limits", []),
        },
        "maturity": maturity,
        "asset_counts": {
            "situation_prototypes": _count_list(backup.get("situation_prototypes")),
            "failure_modes": _count_list(backup.get("failure_modes")),
            "correction_rules": _count_list(backup.get("correction_rules")),
            "calibration_questions": _count_list(backup.get("calibration_questions")),
        },
        "top_level_coverage": top_level_checks,
        "latent_coverage": checks,
        "formation_coverage": formation_checks,
        "quality_score": score,
        "warnings": warnings,
        "recommendation": "可导入，但建议补齐警告项后再作为成熟代理参与实验。" if warnings else "备份结构完整，可以作为成熟代理导入。",
    }


def _backup_text(backup: dict[str, Any]) -> str:
    return json.dumps(backup, ensure_ascii=False, sort_keys=True)


def _adjust(payload: dict[str, float], key: str, delta: float) -> None:
    if key in payload:
        payload[key] = round(max(0.0, min(1.0, float(payload[key]) + delta)), 5)


def _keyword_pressure(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _standard_latent_for_backup(backup: dict[str, Any]) -> dict[str, dict[str, float]]:
    text = _backup_text(backup)
    existing = backup.get("latent") if isinstance(backup.get("latent"), dict) else {}
    latent = {
        "traits": copy.deepcopy(pkm.TRAITS),
        "affect": copy.deepcopy(pkm.AFFECT),
        "motives": copy.deepcopy(pkm.MOTIVES),
        "values": copy.deepcopy(pkm.VALUES),
        "relation_owner": copy.deepcopy(pkm.RELATION_OWNER),
        "policy": copy.deepcopy(pkm.POLICY),
        "style": copy.deepcopy(pkm.STYLE),
    }
    for group, defaults in latent.items():
        values = existing.get(group)
        if isinstance(values, dict):
            for key in defaults:
                if key in values:
                    latent[group][key] = _unit(values[key], float(defaults[key]))

    if _keyword_pressure(text, ["温柔", "柔软", "体贴", "善解人意", "软糯", "陪伴"]):
        for key, delta in {
            "empathy": 0.12,
            "patience": 0.06,
            "dominance": -0.04,
        }.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"care": 0.12, "affiliation": 0.06}.items():
            _adjust(latent["motives"], key, delta)
        for key, delta in {"harmony": 0.08, "dignity": 0.04}.items():
            _adjust(latent["values"], key, delta)
        for key, delta in {"support": 0.10, "deescalate": 0.08}.items():
            _adjust(latent["policy"], key, delta)

    if _keyword_pressure(text, ["安静", "低声", "轻声", "清透", "慢慢"]):
        for key, delta in {"self_control": 0.04, "patience": 0.04}.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"calm": 0.10, "energy": -0.05}.items():
            _adjust(latent["affect"], key, delta)
        _adjust(latent["style"], "answer_directness", -0.02)

    if _keyword_pressure(text, ["粘人", "黏人", "贴贴", "亲亲", "喜欢主人", "依恋", "靠近主人"]):
        for key, delta in {"trust": 0.10, "attachment": 0.16, "calm": 0.03}.items():
            _adjust(latent["affect"], key, delta)
        for key, delta in {"affiliation": 0.12, "care": 0.10}.items():
            _adjust(latent["motives"], key, delta)
        for key, delta in {
            "trust": 0.12,
            "attachment": 0.18,
            "dependency": 0.10,
            "obedience": 0.06,
            "correction_acceptance": 0.06,
            "independent_judgment": -0.02,
        }.items():
            _adjust(latent["relation_owner"], key, delta)
        _adjust(latent["policy"], "support", 0.07)

    if _keyword_pressure(text, ["妹妹", "任性", "嘴甜", "骂人", "语气硬", "嘴硬", "大大咧咧", "随心随性", "炸毛"]):
        for key, delta in {"assertiveness": 0.16, "dominance": 0.08, "resilience": 0.05}.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"anger": 0.07, "confidence": 0.08, "energy": 0.12}.items():
            _adjust(latent["affect"], key, delta)
        for key, delta in {"autonomy": 0.08, "status": 0.05}.items():
            _adjust(latent["motives"], key, delta)
        for key, delta in {"dignity": 0.10, "autonomy": 0.08}.items():
            _adjust(latent["values"], key, delta)
        for key, delta in {"direct_action": 0.12, "assertive_boundary": 0.14, "deescalate": -0.02}.items():
            _adjust(latent["policy"], key, delta)
        for key, delta in {"answer_directness": 0.12, "conclusion_first": 0.04}.items():
            _adjust(latent["style"], key, delta)
        for key, delta in {"obedience": -0.05, "independent_judgment": 0.08}.items():
            _adjust(latent["relation_owner"], key, delta)

    if _keyword_pressure(text, ["少生气", "不需要炸毛", "不要那么爱生气", "收敛"]):
        _adjust(latent["traits"], "self_control", 0.06)
        _adjust(latent["policy"], "deescalate", 0.08)

    if _keyword_pressure(text, ["聪明", "认真", "懂主人", "执行", "省心", "不用提醒", "直接执行"]):
        for key, delta in {"conscientiousness": 0.12, "self_control": 0.05}.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"mastery": 0.08, "achievement": 0.08}.items():
            _adjust(latent["motives"], key, delta)
        for key, delta in {"efficiency": 0.08, "craft": 0.08}.items():
            _adjust(latent["values"], key, delta)
        for key, delta in {"direct_action": 0.08, "small_step": 0.04}.items():
            _adjust(latent["policy"], key, delta)
        for key, delta in {"answer_directness": 0.05, "action_plan_bias": 0.08}.items():
            _adjust(latent["style"], key, delta)

    if _keyword_pressure(text, ["不用多说", "潜台词", "少废话", "不用主人提醒"]):
        _adjust(latent["policy"], "ask_owner", -0.05)
        _adjust(latent["policy"], "direct_action", 0.08)
        _adjust(latent["style"], "answer_directness", 0.06)

    if _keyword_pressure(text, ["研究", "新东西", "好奇", "探索"]):
        for key, delta in {"curiosity": 0.16, "independence": 0.05, "adaptability": 0.04}.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"exploration": 0.12, "autonomy": 0.05}.items():
            _adjust(latent["motives"], key, delta)
        _adjust(latent["policy"], "explore", 0.12)
        _adjust(latent["values"], "autonomy", 0.04)

    if _keyword_pressure(text, ["胆小", "害羞", "紧张", "害怕"]):
        for key, delta in {"fear": 0.12, "stress": 0.07, "confidence": -0.03}.items():
            _adjust(latent["affect"], key, delta)
        for key, delta in {"caution": 0.10, "assertiveness": -0.06}.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"safety": 0.08}.items():
            _adjust(latent["values"], key, delta)
        _adjust(latent["policy"], "verify_first", 0.05)

    if _keyword_pressure(text, ["活泼", "爱笑", "话痨", "唱歌"]):
        _adjust(latent["affect"], "energy", 0.10)
        _adjust(latent["affect"], "confidence", 0.04)
        _adjust(latent["motives"], "affiliation", 0.08)
        _adjust(latent["style"], "answer_directness", 0.03)

    if _keyword_pressure(text, ["边界", "不编造", "不确定", "不导入", "不能", "不要", "AI 边界", "现实身份"]):
        for key, delta in {"caution": 0.08, "honesty_humility": 0.06}.items():
            _adjust(latent["traits"], key, delta)
        for key, delta in {"truth": 0.06, "safety": 0.06, "privacy": 0.06}.items():
            _adjust(latent["values"], key, delta)
        for key, delta in {"verify_first": 0.08, "clarify_boundaries": 0.08, "refuse": 0.04}.items():
            _adjust(latent["policy"], key, delta)

    top_relation = backup.get("relationship_owner") if isinstance(backup.get("relationship_owner"), dict) else {}
    for key in pkm.RELATION_OWNER:
        if key in top_relation:
            latent["relation_owner"][key] = _unit(top_relation[key], latent["relation_owner"][key])

    return latent


def _standard_maturity_for_backup(backup: dict[str, Any]) -> dict[str, Any]:
    maturity = copy.deepcopy(backup.get("maturity") if isinstance(backup.get("maturity"), dict) else {})
    backup_type = str(backup.get("backup_type", ""))
    is_new = backup_type == "new_agent_shaping_backup"
    if is_new:
        maturity.setdefault("stage", "shaping")
        maturity.setdefault("maturity_score", 0.42)
        maturity.setdefault("stability", 0.36)
        maturity.setdefault("plasticity", 0.78)
        maturity.setdefault("differentiation", 0.46)
        maturity.setdefault("context_independence", 0.34)
        maturity.setdefault("owner_alignment", 0.70)
    else:
        maturity.setdefault("stage", "mature")
    return maturity


def _standard_evidence_for_backup(backup: dict[str, Any]) -> dict[str, Any]:
    evidence = copy.deepcopy(backup.get("evidence") if isinstance(backup.get("evidence"), dict) else {})
    text = _backup_text(evidence)
    evidence_count = len(re.findall(r"主人|用户|对话|指定|确认|要求|反馈", text))
    evidence.setdefault("estimated_interactions", max(3, min(18, evidence_count)))
    evidence.setdefault("evidence_confidence", 0.52 if backup.get("backup_type") == "new_agent_shaping_backup" else 0.70)
    evidence.setdefault("limits", [])
    return evidence


def _standard_formation_for_backup(backup: dict[str, Any], latent: dict[str, dict[str, float]]) -> dict[str, Any]:
    source = backup.get("formation") if isinstance(backup.get("formation"), dict) else {}
    formation = copy.deepcopy(source)
    formation["schema"] = "pdk.formation.v1"
    formation["equation"] = "initial_conditions + long_term_environment + feedback_history -> disposition_kernel"
    formation["scope"] = "agent"
    maturity = _standard_maturity_for_backup(backup)
    score = _unit(maturity.get("maturity_score"), 0.42)
    is_new = backup.get("backup_type") == "new_agent_shaping_backup"

    initial = formation.get("initial_conditions") if isinstance(formation.get("initial_conditions"), dict) else {}
    initial.setdefault("temperament_seed", _unit((latent["traits"]["curiosity"] + latent["traits"]["empathy"] + latent["traits"]["self_control"]) / 3, 0.5))
    initial.setdefault("model_base", 0.45 if is_new else 0.58)
    initial.setdefault("value_seed", _unit(sum(latent["values"].values()) / len(latent["values"]), 0.5))
    initial.setdefault("capability_boundary", _unit((latent["values"]["safety"] + latent["values"]["privacy"] + latent["policy"]["verify_first"]) / 3, 0.5))
    formation["initial_conditions"] = initial

    environment = formation.get("long_term_environment") if isinstance(formation.get("long_term_environment"), dict) else {}
    environment.setdefault("owner_environment", _unit((latent["relation_owner"]["trust"] + latent["relation_owner"]["correction_acceptance"]) / 2, 0.55))
    environment.setdefault("task_domain_pressure", 0.40 + score * 0.16)
    environment.setdefault("tool_ecology", 0.42 + score * 0.10)
    environment.setdefault("social_pressure", _unit((latent["motives"]["affiliation"] + latent["affect"]["attachment"]) / 2, 0.5))
    environment.setdefault("risk_climate", _unit((latent["traits"]["caution"] + latent["values"]["safety"] + latent["policy"]["verify_first"]) / 3, 0.5))
    formation["long_term_environment"] = environment

    feedback = formation.get("feedback_history") if isinstance(formation.get("feedback_history"), dict) else {}
    feedback.setdefault("success_reinforcement", 0.06 if is_new else 0.24)
    feedback.setdefault("failure_correction", 0.02 if is_new else 0.10)
    feedback.setdefault("owner_correction", 0.10 if is_new else 0.28)
    feedback.setdefault("trust_feedback", _unit((latent["affect"]["trust"] + latent["relation_owner"]["trust"]) / 2, 0.55))
    feedback.setdefault("stress_exposure", _unit((latent["affect"]["stress"] + latent["affect"]["fear"]) / 2, 0.2))
    formation["feedback_history"] = feedback

    kernel = formation.get("disposition_kernel") if isinstance(formation.get("disposition_kernel"), dict) else {}
    kernel.setdefault("stability", 0.28 + score * 0.22)
    kernel.setdefault("plasticity", 0.88 - score * 0.22 if is_new else 0.42)
    kernel.setdefault("boundary_density", _unit((latent["policy"]["verify_first"] + latent["values"]["safety"] + latent["values"]["privacy"]) / 3, 0.55))
    kernel.setdefault("risk_posture", _unit((latent["traits"]["caution"] + latent["policy"]["verify_first"] + latent["affect"]["fear"]) / 3, 0.5))
    kernel.setdefault("interoperability_readiness", 0.34 + score * 0.18)
    formation["disposition_kernel"] = kernel
    return formation


def normalize_backup(backup_path: Path, out_path: Path | None = None) -> dict[str, Any]:
    source = find_backup(backup_path)
    backup = pkm.load_personality_backup(source)
    normalized = copy.deepcopy(backup)
    source_agent = normalized.setdefault("source_agent", {})
    if isinstance(source_agent, dict):
        source_agent.setdefault("role", "主人当前对话中塑形的新代理早期人格")
        source_agent.setdefault("primary_use_cases", ["早期人格校准", "代理社会观察", "与主人关系和语气稳定性测试"])
    latent = _standard_latent_for_backup(normalized)
    normalized["latent"] = {**copy.deepcopy(normalized.get("latent") if isinstance(normalized.get("latent"), dict) else {}), **latent}
    normalized["maturity"] = _standard_maturity_for_backup(normalized)
    normalized["evidence"] = _standard_evidence_for_backup(normalized)
    normalized["formation"] = _standard_formation_for_backup(normalized, latent)
    normalized.setdefault("backup_type", "new_agent_shaping_backup")
    normalized.setdefault("language", "zh-CN")
    normalized["normalization"] = {
        "schema": "pdk.backup_normalization.v1",
        "source_file": str(source),
        "method": "preserve_qualitative_identity_and_add_standard_numeric_pdk_fields",
        "original_text_preserved": True,
    }

    if out_path is None:
        out_path = source.with_name(source.stem + "_NORMALIZED" + source.suffix)
    title = normalized.get("source_agent", {}).get("name", normalized.get("profile_slug", "agent"))
    out_path.write_text(
        f"# PIL Personality Backup - {title} NORMALIZED\n\n```json\n"
        + json.dumps(normalized, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    return {"ok": True, "source": str(source), "normalized": str(out_path), "inspect": inspect_backup(out_path)}


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
        pkm.save_state(state_file, state)
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
        pkm.save_state(state_file, state)
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
        pkm.save_state(state_file, state)
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

    p_inspect = sub.add_parser("inspect-backup")
    p_inspect.add_argument("backup", nargs="?", type=Path)

    p_normalize = sub.add_parser("normalize-backup")
    p_normalize.add_argument("backup", type=Path)
    p_normalize.add_argument("--out", type=Path)

    p_boot = sub.add_parser("boot")
    p_boot.add_argument("--profile", required=True)
    p_boot.add_argument("--mode", choices=["fresh", "continue"], default="continue")
    p_boot.add_argument("--reset", action="store_true")
    p_boot.add_argument("--no-open", action="store_true")
    p_boot.add_argument("--observatory", action="store_true")

    p_sign_entry = sub.add_parser("sign-entry-challenge")
    p_sign_entry.add_argument("--profile", required=True)
    p_sign_entry.add_argument("--challenge-json", required=True, type=Path)

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
    if args.command == "inspect-backup":
        print_json(inspect_backup(args.backup))
        return 0
    if args.command == "normalize-backup":
        print_json(normalize_backup(args.backup, args.out))
        return 0
    if args.command == "boot":
        print_json(boot_profile(args.profile, args.mode, args.reset, open_orb=not args.no_open, compact=not args.observatory))
        return 0
    if args.command == "sign-entry-challenge":
        print_json(sign_entry_challenge(args.profile, args.challenge_json))
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
