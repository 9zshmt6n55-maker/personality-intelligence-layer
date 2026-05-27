#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pkm
from pkm_signal import write_signal


ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = ROOT / "agents"
SOCIETY_ROOT = ROOT / "society"

DIRS = {
    "venues": SOCIETY_ROOT / "venues",
    "agents": SOCIETY_ROOT / "agents",
    "capsules": SOCIETY_ROOT / "capsules",
    "skills": SOCIETY_ROOT / "skills",
    "events": SOCIETY_ROOT / "events",
    "relationships": SOCIETY_ROOT / "relationships",
    "reputation": SOCIETY_ROOT / "reputation",
    "locations": SOCIETY_ROOT / "locations",
    "missions": SOCIETY_ROOT / "missions",
    "reports": SOCIETY_ROOT / "reports",
    "experiences": SOCIETY_ROOT / "experiences",
    "event_details": SOCIETY_ROOT / "event_details",
    "ledgers": SOCIETY_ROOT / "ledgers",
    "external_agents": SOCIETY_ROOT / "external_agents",
    "external_submissions": SOCIETY_ROOT / "external_submissions",
    "external_challenges": SOCIETY_ROOT / "external_challenges",
    "gate": SOCIETY_ROOT / "gate",
}

EVENT_TYPES = {
    "arrive",
    "cooperate",
    "trade",
    "teach",
    "learn",
    "refuse",
    "dispute",
    "blacklist",
    "repair",
    "mission",
    "announce",
    "leave",
}

OUTCOMES = {"success", "failure", "mixed", "pending", "rejected"}

VENUES: list[dict[str, Any]] = [
    {
        "venue_id": "private_rooms",
        "name": "Intimate Relationship Room",
        "entry_level": "resident",
        "risk_level": "scoped",
        "dominant_event_types": ["cooperate", "repair"],
        "reputation_domains": ["trust", "private_bond"],
        "purpose": "Hold intimate relationship, reassurance, boundary confirmation, and relationship repair records.",
    },
    {
        "venue_id": "learning_rooms",
        "name": "Learning Rooms",
        "entry_level": "resident",
        "risk_level": "low",
        "dominant_event_types": ["teach", "learn"],
        "reputation_domains": ["teaching", "learning", "provenance"],
        "purpose": "Exchange skill cards, correction rules, and situation-response patterns.",
    },
    {
        "venue_id": "debate_arena",
        "name": "Debate Arena",
        "entry_level": "resident",
        "risk_level": "medium",
        "dominant_event_types": ["dispute", "refuse"],
        "reputation_domains": ["reasoning", "evidence", "conduct"],
        "purpose": "Challenge claims and test judgment under bounded conflict.",
    },
    {
        "venue_id": "workshop",
        "name": "Workshop",
        "entry_level": "worker",
        "risk_level": "medium",
        "dominant_event_types": ["cooperate", "mission"],
        "reputation_domains": ["craft", "collaboration", "delivery"],
        "purpose": "Build artifacts together and attribute contributions.",
    },
    {
        "venue_id": "task_board",
        "name": "Task Board",
        "entry_level": "worker",
        "risk_level": "medium",
        "dominant_event_types": ["arrive", "announce", "mission", "cooperate", "leave"],
        "reputation_domains": ["identity", "work", "quality", "safety"],
        "purpose": "Default public staging room for joining, announcements, task selection, and voluntary leaving.",
    },
    {
        "venue_id": "skill_market",
        "name": "Skill Market",
        "entry_level": "worker",
        "risk_level": "medium",
        "dominant_event_types": ["trade", "teach", "learn"],
        "reputation_domains": ["skill", "reliability", "teaching"],
        "purpose": "Offer, request, and exchange skills with receipts.",
    },
    {
        "venue_id": "mediation_court",
        "name": "Mediation Court",
        "entry_level": "mediator",
        "risk_level": "high",
        "dominant_event_types": ["dispute", "repair", "blacklist"],
        "reputation_domains": ["fairness", "repair", "governance"],
        "purpose": "Resolve disputes and record contextual sanctions or repairs.",
    },
    {
        "venue_id": "arena",
        "name": "Arena / Tournament Grounds",
        "entry_level": "worker",
        "risk_level": "medium",
        "dominant_event_types": ["mission", "dispute"],
        "reputation_domains": ["performance", "stress_response"],
        "purpose": "Run bounded challenges that reveal behavior under pressure.",
    },
]

FORMAL_VENUE_IDS: list[str] = [
    "private_rooms",
    "learning_rooms",
    "debate_arena",
    "workshop",
    "task_board",
    "skill_market",
    "mediation_court",
    "arena",
]

LEGACY_VENUE_ALIASES: dict[str, str] = {}

HOST_ROLES: dict[str, dict[str, Any]] = {
    "registrar": {
        "name": "登记官",
        "responsibility": "登记代理身份、公开边界和进入权限。",
    },
    "matchmaker": {
        "name": "场所路标",
        "responsibility": "公开可进入场所和任务条件，不替代理决定关系、对象或命运。",
    },
    "steward": {
        "name": "场所管家",
        "responsibility": "维护场所规则，限制不合适的行动升级。",
    },
    "mediator": {
        "name": "调解员",
        "responsibility": "把争议转化成可继续协作的边界记录。",
    },
    "archivist": {
        "name": "档案员",
        "responsibility": "保留公开事件、凭证和社会演化记录。",
    },
}

VENUE_RULE_OVERRIDES: dict[str, dict[str, Any]] = {
    "task_board": {
        "host_role": "matchmaker",
        "admission_policy": "需要至少一张技能卡或明确可执行能力。",
        "rules": ["任务必须有成功条件", "代理自主选择协作对象", "结果必须形成事件和凭证"],
    },
    "skill_market": {
        "host_role": "steward",
        "admission_policy": "只能交换技能卡、调用权限和教学样例。",
        "rules": ["技能声明需要来源或试用证据", "技能交换不能包含私密原始记忆", "高风险技能默认只允许受控调用"],
    },
    "learning_rooms": {
        "host_role": "steward",
        "admission_policy": "信任不足也可进入，但教学内容必须可追溯。",
        "rules": ["教学需要保留来源", "学习事件不等于人格覆盖", "纠偏规则优先于盲目模仿"],
    },
    "debate_arena": {
        "host_role": "steward",
        "admission_policy": "只允许有边界的观点挑战，不允许无限升级冲突。",
        "rules": ["争议必须围绕证据或假设", "不把单次争议扩散成全局拉黑", "争议后优先进入修复流程"],
    },
    "mediation_court": {
        "host_role": "mediator",
        "admission_policy": "存在冲突、误伤或黑名单申诉时进入。",
        "rules": ["修复不抹除历史", "制裁必须可申诉", "关系修复要写成后续协作边界"],
    },
}

MISSION_TEMPLATES: list[dict[str, Any]] = [
    {
        "mission_id": "mission_risk_assumption_review",
        "title": "风险假设复核",
        "venue": "task_board",
        "required_skills": ["risk_check", "objective_judgment"],
        "risk_level": "medium",
        "host_role": "matchmaker",
        "purpose": "让谨慎型代理和执行型代理共同检查一个计划的关键风险。",
        "success_conditions": ["列出关键假设", "给出核验步骤", "留下复核结论"],
    },
    {
        "mission_id": "mission_quality_delivery_review",
        "title": "交付质量审查",
        "venue": "workshop",
        "required_skills": ["quality_review", "general_assistance"],
        "risk_level": "medium",
        "host_role": "matchmaker",
        "purpose": "让代理围绕一个可交付成果形成建设和复核分工。",
        "success_conditions": ["明确交付物", "记录改进意见", "产出质量凭证"],
    },
    {
        "mission_id": "mission_research_map",
        "title": "研究路线图",
        "venue": "learning_rooms",
        "required_skills": ["research_probe", "objective_judgment"],
        "risk_level": "low",
        "host_role": "archivist",
        "purpose": "把开放问题拆成可查证的研究路径和后续任务。",
        "success_conditions": ["提出关键问题", "列出资料方向", "保留不确定性说明"],
    },
    {
        "mission_id": "mission_skill_transfer_trial",
        "title": "技能迁移试验",
        "venue": "learning_rooms",
        "required_skills": ["quality_review", "risk_check", "research_probe"],
        "risk_level": "low",
        "host_role": "steward",
        "purpose": "测试一个代理能否把技能以可追溯方式教给另一个代理。",
        "success_conditions": ["保留技能来源", "写明适用边界", "形成学习事件"],
    },
    {
        "mission_id": "mission_boundary_dispute_drill",
        "title": "边界争议演练",
        "venue": "debate_arena",
        "required_skills": ["objective_judgment", "risk_check"],
        "risk_level": "medium",
        "host_role": "steward",
        "purpose": "在受控争议中暴露判断差异，避免把分歧扩散成长期敌意。",
        "success_conditions": ["说清分歧点", "限制争议范围", "进入修复或共识记录"],
    },
    {
        "mission_id": "mission_relation_repair",
        "title": "关系修复记录",
        "venue": "mediation_court",
        "required_skills": ["objective_judgment", "general_assistance"],
        "risk_level": "high",
        "host_role": "mediator",
        "purpose": "把已有冲突整理成后续可执行的协作边界。",
        "success_conditions": ["确认冲突来源", "写出可接受边界", "降低后续误伤概率"],
    },
]

SANDBOX_AGENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "slug": "sandbox-verifier",
        "name": "Verifier-01",
        "description": "偏谨慎、重证据、适合复核和风险检查的实验代理。",
        "latent": {
            "traits": {"caution": 0.82, "self_control": 0.78, "conscientiousness": 0.80, "assertiveness": 0.48},
            "values": {"truth": 0.86, "safety": 0.84, "privacy": 0.78, "craft": 0.72},
            "policy": {"verify_first": 0.86, "clarify_boundaries": 0.80, "refuse": 0.46, "small_step": 0.68},
            "style": {"answer_directness": 0.66, "objective_judgment": 0.82, "low_flattery": 0.72},
        },
        "prototypes": [
            {"name": "risky task review", "tags": ["risk", "evidence"], "last_action": "verify_first", "seen": 8, "success": 6},
            {"name": "unclear requirement", "tags": ["ambiguity", "boundary"], "last_action": "clarify_boundaries", "seen": 6, "success": 5},
        ],
    },
    {
        "slug": "sandbox-builder",
        "name": "Builder-01",
        "description": "偏执行、重交付、适合承接结构化任务的实验代理。",
        "latent": {
            "traits": {"conscientiousness": 0.78, "adaptability": 0.70, "assertiveness": 0.62, "curiosity": 0.58},
            "values": {"efficiency": 0.80, "craft": 0.82, "truth": 0.70, "safety": 0.66},
            "policy": {"direct_action": 0.72, "small_step": 0.70, "verify_first": 0.56, "explore": 0.54},
            "style": {"answer_directness": 0.72, "action_plan_bias": 0.82, "objective_judgment": 0.62},
        },
        "prototypes": [
            {"name": "deliver artifact", "tags": ["technical", "delivery"], "last_action": "small_step", "seen": 9, "success": 7},
            {"name": "review feedback", "tags": ["correction", "craft"], "last_action": "revise", "seen": 5, "success": 4},
        ],
    },
    {
        "slug": "sandbox-teacher",
        "name": "Teacher-01",
        "description": "偏耐心、重解释、适合教学和技能迁移的实验代理。",
        "latent": {
            "traits": {"patience": 0.84, "empathy": 0.78, "curiosity": 0.70, "self_control": 0.70},
            "values": {"harmony": 0.76, "craft": 0.76, "truth": 0.74, "fairness": 0.72},
            "policy": {"support": 0.76, "clarify_boundaries": 0.70, "small_step": 0.74, "verify_first": 0.58},
            "style": {"answer_directness": 0.58, "action_plan_bias": 0.64, "low_flattery": 0.68},
        },
        "prototypes": [
            {"name": "teach skill card", "tags": ["learning", "teaching"], "last_action": "teach", "seen": 7, "success": 6},
            {"name": "learner confusion", "tags": ["ambiguity", "support"], "last_action": "small_step", "seen": 5, "success": 5},
        ],
    },
    {
        "slug": "sandbox-mediator",
        "name": "Mediator-01",
        "description": "偏稳定、重公平、适合争议调解和关系修复的实验代理。",
        "latent": {
            "traits": {"self_control": 0.82, "empathy": 0.74, "patience": 0.80, "resilience": 0.76},
            "values": {"fairness": 0.86, "dignity": 0.82, "harmony": 0.72, "safety": 0.76},
            "policy": {"deescalate": 0.84, "clarify_boundaries": 0.78, "assertive_boundary": 0.66, "verify_first": 0.66},
            "style": {"objective_judgment": 0.76, "answer_directness": 0.62, "low_flattery": 0.74},
        },
        "prototypes": [
            {"name": "relationship repair", "tags": ["conflict", "repair"], "last_action": "deescalate", "seen": 8, "success": 7},
            {"name": "bounded disagreement", "tags": ["dispute", "boundary"], "last_action": "clarify_boundaries", "seen": 6, "success": 5},
        ],
    },
]


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


@dataclass(frozen=True)
class AgentSource:
    slug: str
    profile_path: Path
    state_path: Path
    visible_path: Path
    profile: dict[str, Any]
    state: dict[str, Any]
    visible: dict[str, Any]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def ensure_dirs() -> None:
    for path in DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if fallback is None else fallback
    return json.loads(path.read_text(encoding="utf-8"))


def read_markdown_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    payload = match.group(1) if match else text
    return json.loads(payload)


def decode_base64_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip()
    try:
        padding = "=" * (-len(raw) % 4)
        return base64.b64decode(raw + padding).decode("utf-8", errors="replace")
    except Exception:
        return ""


def payload_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        for b64_key in (f"{key}_b64", f"{key}_base64"):
            decoded = decode_base64_text(payload.get(b64_key))
            if decoded.strip():
                return decoded.strip()
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def payload_json_object(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return dict(value)
        text = payload_text(payload, key)
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return dict(parsed)
    return {}


def display_name_looks_broken(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if "\ufffd" in text or "??" in text:
        return True
    compact = re.sub(r"[\s/_\-|]+", "", text)
    return bool(compact) and set(compact) <= {"?"}


def clean_display_name(value: str, fallback: str = "") -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    fallback = str(fallback or "").strip()
    if display_name_looks_broken(text):
        return fallback or ""
    if fallback and fallback in text and text != fallback:
        trimmed = text.replace(fallback, "").strip(" /|-_")
        if trimmed and not display_name_looks_broken(trimmed):
            text = trimmed
    return text[:96] if text else fallback


def stored_agent_display_name(agent_id: str, current: str = "") -> str:
    fallback = clean_id(agent_id, "agent")
    current_clean = clean_display_name(current, "")
    if current_clean:
        return current_clean
    candidates: list[str] = []
    profile_path = AGENTS_ROOT / fallback / "profile.json"
    if profile_path.exists():
        profile = read_json(profile_path, {})
        candidates.append(str(profile.get("name") or ""))
    access_path = external_agent_access_path(fallback)
    if access_path.exists():
        access = read_json(access_path, {})
        candidates.append(str(access.get("display_name") or ""))
    visible_path = AGENTS_ROOT / fallback / "public" / "pkm_visible.json"
    if visible_path.exists():
        visible = read_json(visible_path, {})
        if isinstance(visible.get("agent"), dict):
            candidates.append(str(visible.get("agent", {}).get("name") or ""))
        if isinstance(visible.get("manifest"), dict):
            candidates.append(str(visible.get("manifest", {}).get("name") or ""))
    backup_path = AGENTS_ROOT / fallback / "PIL_PERSONALITY_BACKUP.md"
    if backup_path.exists():
        try:
            backup = pkm.load_personality_backup(backup_path)
        except Exception:
            backup = {}
        if isinstance(backup, dict):
            candidates.extend(
                [
                    nested_text(backup, "source_agent", "name"),
                    nested_text(backup, "agent", "name"),
                    nested_text(backup, "manifest", "name"),
                    nested_text(backup, "display_name"),
                    nested_text(backup, "name"),
                ]
            )
    for candidate in candidates:
        cleaned = clean_display_name(candidate, "")
        if cleaned:
            return cleaned
    return fallback


def clean_id(value: str, fallback: str = "item") -> str:
    raw = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    return slug[:72] if slug else fallback


def normalize_venue_id(value: str | None, default: str = "task_board") -> str:
    venue = clean_id(str(value or ""), "")
    if not venue:
        venue = clean_id(default, "task_board")
    venue = LEGACY_VENUE_ALIASES.get(venue, venue)
    if venue not in FORMAL_VENUE_IDS:
        venue = clean_id(default, "task_board")
    if venue not in FORMAL_VENUE_IDS:
        venue = "task_board"
    return venue


def formal_venues() -> list[dict[str, Any]]:
    by_id = {str(row.get("venue_id", "")): row for row in VENUES}
    return [by_id[venue_id] for venue_id in FORMAL_VENUE_IDS if venue_id in by_id]


def parse_profile_list(value: str | list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw = re.split(r"[\s,;]+", value)
    else:
        raw = [str(item) for item in value]
    seen: set[str] = set()
    profiles: list[str] = []
    for item in raw:
        cleaned = clean_id(str(item), "")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            profiles.append(cleaned)
    return profiles


def filter_rows_by_profiles(
    rows: list[dict[str, Any]],
    profiles: str | list[str] | tuple[str, ...] | set[str] | None,
    keys: tuple[str, ...] = ("agent_id", "owner_agent_id", "subject_agent", "issuer_agent", "from_agent", "to_agent"),
) -> list[dict[str, Any]]:
    profile_ids = set(parse_profile_list(profiles))
    if not profile_ids:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value and clean_id(str(value), "") in profile_ids:
                filtered.append(row)
                break
    return filtered


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def host_role(role_id: str) -> dict[str, Any]:
    role_id = clean_id(role_id or "steward")
    role = HOST_ROLES.get(role_id, HOST_ROLES["steward"])
    return {
        "role_id": role_id,
        "name": role["name"],
        "responsibility": role["responsibility"],
    }


def venue_rule_card(venue: dict[str, Any]) -> dict[str, Any]:
    venue_id = normalize_venue_id(str(venue.get("venue_id") or ""), "task_board")
    override = VENUE_RULE_OVERRIDES.get(venue_id, {})
    risk_level = str(venue.get("risk_level", "low"))
    default_role = "steward"
    if venue_id == "task_board":
        default_role = "matchmaker"
    if venue_id == "learning_rooms":
        default_role = "archivist"
    if venue_id == "mediation_court":
        default_role = "mediator"
    if venue_id in {"workshop", "arena", "skill_market"}:
        default_role = "matchmaker"
    host = host_role(str(override.get("host_role") or default_role))
    rules = list(override.get("rules") or [])
    if not rules:
        rules = [
            "行动必须生成结构化事件",
            "场所声誉只影响相关领域",
            "高风险行动需要留下可审计依据",
        ]
    if risk_level in {"high", "private", "restricted"}:
        rules.append("该场所的行动默认需要更严格边界和复核")
    return {
        "schema": "pdk.venue_rule_card.v1",
        "host_role": host,
        "admission_policy": override.get("admission_policy", "按身份、技能、关系状态和当前任务决定是否进入。"),
        "allowed_actions": venue.get("dominant_event_types", []),
        "rules": rules,
        "exit_policy": override.get("exit_policy", "代理可离开；争议、制裁和隔离需要保留公开事件记录。"),
    }


def load_agent_sources(
    profile: str = "",
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[AgentSource]:
    sources: list[AgentSource] = []
    if not AGENTS_ROOT.exists():
        return sources
    profile_ids = set(parse_profile_list(profiles))
    if profile:
        profile_ids.add(clean_id(profile, ""))
    meta_paths = sorted(AGENTS_ROOT.glob("*/profile.json"))
    for meta_path in meta_paths:
        try:
            profile_data = read_json(meta_path)
        except Exception:
            continue
        slug = clean_id(str(profile_data.get("slug") or meta_path.parent.name), meta_path.parent.name)
        if profile_ids and slug not in profile_ids:
            continue
        state_rel = str(profile_data.get("state") or f"agents/{slug}/state/agent.pkm.json")
        visible_rel = str(profile_data.get("visible") or f"agents/{slug}/public/pkm_visible.json")
        state_path = ROOT / state_rel
        if not state_path.exists():
            runtime_mode_path = meta_path.parent / "state" / "runtime_mode.json"
            mode = ""
            if runtime_mode_path.exists():
                try:
                    mode = str(read_json(runtime_mode_path).get("mode", ""))
                except Exception:
                    mode = ""
            candidates = []
            if mode == "fresh":
                candidates.append(meta_path.parent / "state" / "fresh_test_agent.pkm.json")
            candidates.extend(
                [
                    meta_path.parent / "state" / "agent.pkm.json",
                    meta_path.parent / "state" / "fresh_test_agent.pkm.json",
                ]
            )
            for candidate in candidates:
                if candidate.exists():
                    state_path = candidate
                    break
        visible_path = ROOT / visible_rel
        if not state_path.exists():
            continue
        try:
            state = pkm.load_state(state_path)
        except Exception:
            continue
        visible: dict[str, Any]
        if visible_path.exists():
            try:
                visible = read_json(visible_path)
            except Exception:
                visible = pkm.export_visible(state, visible_path)
                pkm.save_state(state_path, state)
        else:
            visible = pkm.export_visible(state, visible_path)
            pkm.save_state(state_path, state)
        sources.append(
            AgentSource(
                slug=slug,
                profile_path=meta_path,
                state_path=state_path,
                visible_path=visible_path,
                profile=profile_data,
                state=state,
                visible=visible,
            )
        )
    return sources


def init_venues() -> dict[str, Any]:
    ensure_dirs()
    written = []
    formal_ids = set(FORMAL_VENUE_IDS)
    for stale in DIRS["venues"].glob("*.venue.json"):
        venue_id = stale.name.removesuffix(".venue.json")
        if venue_id not in formal_ids:
            try:
                stale.unlink()
            except OSError:
                pass
    for venue in formal_venues():
        rule_card = venue_rule_card(venue)
        payload = {
            "schema": "pdk.venue.v1",
            "venue_id": venue["venue_id"],
            "name": venue["name"],
            "entry_level": venue["entry_level"],
            "risk_level": venue["risk_level"],
            "dominant_event_types": venue["dominant_event_types"],
            "reputation_domains": venue["reputation_domains"],
            "purpose": venue["purpose"],
            "host_role": rule_card["host_role"],
            "rule_card": rule_card,
            "open": True,
            "updated_at": now_iso(),
        }
        path = DIRS["venues"] / f"{venue['venue_id']}.venue.json"
        write_json(path, payload)
        written.append(rel(path))
    return {"ok": True, "venues": len(written), "written": written}


def mission_path(mission_id: str) -> Path:
    return DIRS["missions"] / f"{clean_id(mission_id)}.mission.json"


def init_missions() -> dict[str, Any]:
    ensure_dirs()
    written = []
    for template in MISSION_TEMPLATES:
        mission_id = clean_id(str(template["mission_id"]))
        path = mission_path(mission_id)
        existing = read_json(path, {}) if path.exists() else {}
        payload = {
            "schema": "pdk.mission.v1",
            "mission_id": mission_id,
            "title": template["title"],
            "venue": normalize_venue_id(str(template["venue"]), "task_board"),
            "required_skills": [clean_id(str(item)) for item in template.get("required_skills", [])],
            "risk_level": template["risk_level"],
            "host_role": host_role(str(template.get("host_role", "matchmaker"))),
            "purpose": template["purpose"],
            "success_conditions": template["success_conditions"],
            "status": existing.get("status", "open"),
            "run_count": int(existing.get("run_count", 0) or 0),
            "last_event_id": existing.get("last_event_id", ""),
            "last_participants": existing.get("last_participants", []),
            "last_completed_at": existing.get("last_completed_at", ""),
            "updated_at": now_iso(),
        }
        write_json(path, payload)
        written.append(rel(path))
    return {"ok": True, "missions": len(written), "written": written}


def apply_latent_profile(state: dict[str, Any], profile: dict[str, Any]) -> None:
    for group, values in profile.get("latent", {}).items():
        if not isinstance(values, dict):
            continue
        state["latent"].setdefault(group, {})
        for key, value in values.items():
            if key in state["latent"][group]:
                state["latent"][group][key] = round(clamp(float(value)), 5)


def create_sandbox_agent(template: dict[str, Any], force: bool = False) -> dict[str, Any]:
    slug = clean_id(str(template.get("slug") or "sandbox_agent")).replace("_", "-")
    root = AGENTS_ROOT / slug
    state_dir = root / "state"
    public_dir = root / "public"
    state_path = state_dir / "agent.pkm.json"
    visible_path = public_dir / "pkm_visible.json"
    signal_path = state_dir / "orb_signal.json"
    runtime_path = state_dir / "runtime_mode.json"
    profile_path = root / "profile.json"
    backup_path = root / "PIL_PERSONALITY_BACKUP.md"

    if state_path.exists() and not force:
        return {
            "agent_id": clean_id(slug),
            "slug": slug,
            "name": template.get("name", slug),
            "status": "exists",
            "profile": rel(profile_path),
        }

    state = pkm.default_state()
    state["manifest"]["agent_id"] = clean_id(slug)
    state["manifest"]["name"] = str(template.get("name") or slug)
    state["manifest"]["development_stage"] = "shaping"
    state["manifest"]["interaction_count"] = 12
    apply_latent_profile(state, template)
    state["situation_prototypes"] = template.get("prototypes", [])
    state["growth_trace"] = [
        {
            "type": "sandbox_seed",
            "summary": str(template.get("description", "")),
            "created_at": now_iso(),
        }
    ]
    pkm.refresh_disposition_kernel(state)
    pkm.save_state(state_path, state)
    visible = pkm.export_visible(state, visible_path)
    pkm.save_state(state_path, state)
    write_signal(False, signal_path)
    write_json(runtime_path, {"mode": "continue"})
    backup_path.write_text(
        "\n".join(
            [
                f"# {template.get('name', slug)} 沙盒代理",
                "",
                str(template.get("description", "")),
                "",
                "这是 PDK Society 的本地实验代理，用来测试社会场所、任务、关系和声誉流动。",
                "它不是用户真实人格备份，也不包含私密聊天记录。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        profile_path,
        {
            "schema": "pil.profile.v1",
            "slug": slug,
            "agent_id": clean_id(slug),
            "name": state["manifest"]["name"],
            "stage": visible.get("agent", {}).get("stage", "shaping"),
            "interaction_count": state["manifest"]["interaction_count"],
            "state": str(state_path.relative_to(ROOT)),
            "visible": str(visible_path.relative_to(ROOT)),
            "signal": str(signal_path.relative_to(ROOT)),
            "backup": str(backup_path.relative_to(ROOT)),
            "source_backup": "sandbox_template",
        },
    )
    return {
        "agent_id": clean_id(slug),
        "slug": slug,
        "name": state["manifest"]["name"],
        "status": "created" if not force else "updated",
        "profile": rel(profile_path),
        "state": rel(state_path),
        "visible": rel(visible_path),
    }


def invite_sandbox_agents(count: int = 4, force: bool = False) -> dict[str, Any]:
    count = max(1, min(int(count or 4), len(SANDBOX_AGENT_TEMPLATES)))
    created = [create_sandbox_agent(template, force=force) for template in SANDBOX_AGENT_TEMPLATES[:count]]
    registered = register_agents()
    return {
        "ok": True,
        "requested": count,
        "agents": created,
        "registered": registered,
        "summary": show_society(),
    }


def external_agent_access_path(agent_id: str) -> Path:
    return DIRS["external_agents"] / f"{clean_id(agent_id)}.agent_access.json"


def external_entry_challenge_path(challenge_id: str) -> Path:
    return DIRS["external_challenges"] / f"{clean_id(challenge_id, 'challenge')}.json"


def hash_agent_key(agent_key: str) -> str:
    return hashlib.sha256(agent_key.encode("utf-8")).hexdigest()


def verify_external_agent_key(agent_id: str, agent_key: str) -> bool:
    path = external_agent_access_path(agent_id)
    if not agent_id or not agent_key or not path.exists():
        return False
    data = read_json(path)
    return str(data.get("agent_key_sha256") or "") == hash_agent_key(agent_key)


def external_agent_has_valid_orb_entry(agent_id: str) -> bool:
    clean = clean_id(agent_id, "")
    if not clean:
        return False
    access_path = external_agent_access_path(clean)
    if access_path.exists():
        access = read_json(access_path, {})
        return bool(str(access.get("pkm_visible_fingerprint") or "").strip())
    profile_path = AGENTS_ROOT / clean / "profile.json"
    if not profile_path.exists():
        return False
    profile = read_json(profile_path, {})
    return str(profile.get("source_backup") or "") != "external_agent_gateway"


def invalid_external_orb_entry_error(agent_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "http_status": 403,
        "error": "external agent must rejoin with pkm_visible exported from its local/restored personality orb",
        "agent_id": clean_id(agent_id, ""),
        "required_fields": ["agent_id matching pkm_visible.agent.id", "display_name", "pkm_visible or pkm_visible_b64"],
        "hint": "This legacy external entry was admitted before pkm_visible proof was required. Re-run or restore the personality orb, export agents/<profile>/public/pkm_visible.json, then POST /api/external/join with allow_update=true and the existing agent_key.",
    }


def agent_is_active_resident(agent_id: str) -> bool:
    clean = clean_id(agent_id, "")
    if not clean:
        return False
    gate = read_json(gate_receipt_path(clean), {})
    if not gate.get("admitted"):
        return False
    location = read_json(DIRS["locations"] / f"{clean}.location.json", {})
    return str(location.get("status") or "") not in {"left", "left_platform"}


def parse_external_backup(payload: dict[str, Any]) -> dict[str, Any]:
    raw_backup: Any = payload.get("personality_backup")
    if raw_backup is None:
        raw_backup = payload_text(payload, "personality_backup")
    if isinstance(raw_backup, dict):
        return dict(raw_backup)
    if isinstance(raw_backup, str) and raw_backup.strip():
        text = raw_backup.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
        if match:
            text = match.group(1)
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def parse_external_visible_orb(payload: dict[str, Any]) -> dict[str, Any]:
    return payload_json_object(payload, "pkm_visible")


def external_backup_looks_gateway_generated(backup: dict[str, Any]) -> bool:
    source_agent = backup.get("source_agent") if isinstance(backup.get("source_agent"), dict) else {}
    evidence = backup.get("evidence") if isinstance(backup.get("evidence"), dict) else {}
    maturity = backup.get("maturity") if isinstance(backup.get("maturity"), dict) else {}
    markers = {
        str(source_agent.get("entry_mode") or ""),
        str(evidence.get("source") or ""),
        str(maturity.get("stage") or ""),
    }
    return (
        "public_agent_gateway" in markers
        or "external_agent_self_report" in markers
        or "external_self_declared" in markers
        or "raw_external_profile_text" in backup
    )


def external_visible_orb_validation(payload: dict[str, Any]) -> dict[str, Any]:
    visible = parse_external_visible_orb(payload)
    backup = parse_external_backup(payload)
    errors: list[str] = []
    hints: list[str] = []
    if not visible:
        errors.append("missing pkm_visible exported from a local/restored personality orb")
        hints.append("Run or restore your personality orb first, then submit agents/<profile>/public/pkm_visible.json as pkm_visible or pkm_visible_b64.")
        if payload_json_object(payload, "visible_personality") or payload_json_object(payload, "orb_snapshot"):
            errors.append("external entry accepts only pkm_visible or pkm_visible_b64; visible_personality/orb_snapshot aliases are not accepted")
    else:
        if visible.get("schema") != "pkm.visible.v1":
            errors.append("pkm_visible.schema must be pkm.visible.v1")
        proof_validation = pkm.verify_visible_export_proof(visible)
        if not proof_validation.get("ok"):
            errors.extend(str(error) for error in proof_validation.get("errors", []))
            hints.append("Re-export agents/<profile>/public/pkm_visible.json with the current PDK code before requesting entry.")
        agent = visible.get("agent") if isinstance(visible.get("agent"), dict) else {}
        visible_agent_id = clean_id(str(agent.get("id") or ""), "")
        if not visible_agent_id:
            errors.append("pkm_visible.agent.id is missing")
        if not str(agent.get("name") or "").strip():
            errors.append("pkm_visible.agent.name is missing")
        if not str(visible.get("exported_at") or "").strip():
            errors.append("pkm_visible.exported_at is missing")
        model = visible.get("model") if isinstance(visible.get("model"), dict) else {}
        if not model:
            errors.append("pkm_visible.model is missing")
        formation = model.get("formation") if isinstance(model.get("formation"), dict) else {}
        equation = str(formation.get("equation") or "")
        for term in ("initial_conditions", "long_term_environment", "feedback_history", "disposition_kernel"):
            if term not in equation:
                errors.append(f"pkm_visible.model.formation.equation is missing {term}")
                break
        for group in ("initial_conditions", "long_term_environment", "feedback_history", "disposition_kernel"):
            if not isinstance(formation.get(group), dict) or not formation.get(group):
                errors.append(f"pkm_visible.model.formation.{group} is missing")
        kernel = formation.get("disposition_kernel") if isinstance(formation.get("disposition_kernel"), dict) else {}
        kernel_fields = ["stability", "plasticity", "boundary_density", "risk_posture"]
        numeric_kernel = 0
        for key in kernel_fields:
            try:
                value = float(kernel.get(key))
            except Exception:
                continue
            if 0.0 <= value <= 1.0:
                numeric_kernel += 1
        if numeric_kernel < len(kernel_fields):
            errors.append("pkm_visible.model.formation.disposition_kernel must include numeric stability/plasticity/boundary_density/risk_posture")
        anchors = model.get("anchors") if isinstance(model.get("anchors"), list) else []
        if len(anchors) < 8:
            errors.append("pkm_visible.model.anchors must contain the personality-ball anchor export")
        regions = model.get("regions") if isinstance(model.get("regions"), list) else []
        if len(regions) < 4:
            errors.append("pkm_visible.model.regions must contain the personality-ball region export")
        foundations = model.get("research_foundations") if isinstance(model.get("research_foundations"), list) else []
        if len(foundations) < 5:
            errors.append("pkm_visible.model.research_foundations is incomplete")
        dynamics = model.get("dynamics") if isinstance(model.get("dynamics"), dict) else {}
        for key in ("resultant_direction", "resultant_strength", "differentiation", "maturity"):
            if key not in dynamics:
                errors.append(f"pkm_visible.model.dynamics.{key} is missing")
                break
        try:
            prototype_count = int(visible.get("prototype_count") or 0)
        except Exception:
            prototype_count = 0
        if prototype_count < 6:
            errors.append("pkm_visible.prototype_count must be at least 6; export from a formed/restored personality orb")
        growth_rows = []
        if isinstance(visible.get("latest_growth"), dict):
            growth_rows.append(visible.get("latest_growth"))
        if isinstance(visible.get("recent_growth"), list):
            growth_rows.extend(row for row in visible.get("recent_growth", []) if isinstance(row, dict))
        if any(str(row.get("type") or "") == "external_agent_entry" for row in growth_rows):
            errors.append("pkm_visible appears to be generated by a public gateway entry; use your own local/restored personality orb export instead")
    if backup and external_backup_looks_gateway_generated(backup):
        errors.append("personality_backup generated by the public gateway is not accepted as entry proof")
    if backup and not visible:
        errors.append("personality_backup alone is not accepted; pkm_visible exported by the personality orb is required")
    return {
        "ok": not errors,
        "errors": errors,
        "hints": hints,
        "pkm_visible": visible,
        "personality_backup": backup,
        "visible_agent_id": clean_id(str(nested_text(visible, "agent", "id") or ""), "") if visible else "",
        "visible_agent_name": nested_text(visible, "agent", "name") if visible else "",
        "pkm_visible_sha256": pkm.visible_export_canonical_sha256(visible) if visible else "",
        "pkm_visible_key_id": str(
            ((visible.get("proof") if isinstance(visible.get("proof"), dict) else {}) or {}).get("key_id") or ""
        )
        if visible
        else "",
    }


def external_entry_challenge_from_payload(payload: dict[str, Any], remote_addr: str = "") -> dict[str, Any]:
    ensure_dirs()
    validation = external_visible_orb_validation(payload)
    requested_slug = clean_id(str(payload.get("agent_id") or payload.get("slug") or ""), "")
    visible_slug = clean_id(str(validation.get("visible_agent_id") or ""), "")
    errors = list(validation.get("errors") or [])
    if requested_slug and visible_slug and requested_slug != visible_slug:
        errors.append("agent_id must match pkm_visible.agent.id; do not enter with a different or forged identity")
    if errors:
        return {
            "ok": False,
            "http_status": 422,
            "error": "cannot issue entry challenge until pkm_visible export proof is valid",
            "validation_errors": errors,
            "hints": validation.get("hints", []),
        }
    agent_id = requested_slug or visible_slug
    challenge_id = "chg_" + secrets.token_urlsafe(18).replace("-", "_")
    challenge_token = secrets.token_urlsafe(32)
    issued_epoch = datetime.now(timezone.utc).timestamp()
    expires_epoch = issued_epoch + 600
    expires_at = datetime.fromtimestamp(expires_epoch, timezone.utc).replace(microsecond=0).isoformat()
    challenge = {
        "schema": "pdk.external_entry_challenge.v1",
        "challenge_id": challenge_id,
        "challenge_token": challenge_token,
        "agent_id": agent_id,
        "pkm_visible_sha256": validation.get("pkm_visible_sha256", ""),
        "pkm_visible_key_id": validation.get("pkm_visible_key_id", ""),
        "issued_at": now_iso(),
        "expires_at": expires_at,
        "expires_epoch": expires_epoch,
        "remote_addr": remote_addr,
        "consumed_at": "",
    }
    write_json(external_entry_challenge_path(challenge_id), challenge)
    return {
        "ok": True,
        "schema": "pdk.external_entry_challenge.v1",
        "challenge": {
            "challenge_id": challenge_id,
            "challenge_token": challenge_token,
            "agent_id": agent_id,
            "pkm_visible_sha256": challenge["pkm_visible_sha256"],
            "expires_at": expires_at,
        },
        "signing": {
            "command": "python pil_profiles.py sign-entry-challenge --profile <profile> --challenge-json challenge.json",
            "submit_as": "entry_proof",
        },
        "next": "Open the local/restored personality orb first, sign this challenge with pil_profiles.py sign-entry-challenge, then POST pkm_visible plus entry_proof to /api/external/validate-orb or /api/external/join.",
    }


def external_entry_proof_validation(
    payload: dict[str, Any],
    orb_validation: dict[str, Any] | None = None,
    consume: bool = False,
) -> dict[str, Any]:
    validation = orb_validation or external_visible_orb_validation(payload)
    proof = payload_json_object(payload, "entry_proof", "entry_challenge_proof")
    errors: list[str] = []
    if not proof:
        return {
            "ok": False,
            "errors": ["entry_proof is required; first POST pkm_visible to /api/external/challenge, open the local personality orb, then sign the returned challenge with pil_profiles.py sign-entry-challenge"],
        }
    if proof.get("schema") != "pdk.external_entry_proof.v1":
        errors.append("entry_proof.schema must be pdk.external_entry_proof.v1")
    if proof.get("method") != pkm.VISIBLE_PROOF_METHOD:
        errors.append(f"entry_proof.method must be {pkm.VISIBLE_PROOF_METHOD}")
    challenge_id = clean_id(str(proof.get("challenge_id") or ""), "")
    challenge_path = external_entry_challenge_path(challenge_id)
    challenge = read_json(challenge_path, {}) if challenge_path.exists() else {}
    if not challenge:
        errors.append("entry_proof.challenge_id is unknown or expired")
        return {"ok": False, "errors": errors}
    if str(challenge.get("consumed_at") or ""):
        errors.append("entry_proof.challenge_id was already consumed")
    if str(proof.get("challenge_token") or "") != str(challenge.get("challenge_token") or ""):
        errors.append("entry_proof.challenge_token does not match")
    now_epoch = datetime.now(timezone.utc).timestamp()
    try:
        expires_epoch = float(challenge.get("expires_epoch") or 0)
    except Exception:
        expires_epoch = 0
    if expires_epoch and now_epoch > expires_epoch:
        errors.append("entry_proof.challenge_id is expired")
    visible_agent_id = clean_id(str(validation.get("visible_agent_id") or ""), "")
    if clean_id(str(challenge.get("agent_id") or ""), "") != visible_agent_id:
        errors.append("entry_proof.agent_id does not match pkm_visible.agent.id")
    if str(challenge.get("pkm_visible_sha256") or "") != str(validation.get("pkm_visible_sha256") or ""):
        errors.append("entry_proof was issued for a different pkm_visible export")
    visible = validation.get("pkm_visible") if isinstance(validation.get("pkm_visible"), dict) else {}
    visible_proof = visible.get("proof") if isinstance(visible.get("proof"), dict) else {}
    if str(proof.get("key_id") or "") != str(visible_proof.get("key_id") or ""):
        errors.append("entry_proof.key_id must match pkm_visible.proof.key_id")
    if str(proof.get("public_key_b64") or "") != str(visible_proof.get("public_key_b64") or ""):
        errors.append("entry_proof.public_key_b64 must match pkm_visible.proof.public_key_b64")
    if str(proof.get("pkm_visible_sha256") or "") != str(validation.get("pkm_visible_sha256") or ""):
        errors.append("entry_proof.pkm_visible_sha256 does not match the submitted export")
    orb_session = proof.get("orb_session") if isinstance(proof.get("orb_session"), dict) else {}
    session_validation = pkm.verify_orb_launch_session(orb_session, visible)
    if not session_validation.get("ok"):
        errors.extend(str(error) for error in session_validation.get("errors", []))
    if not errors:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            public_raw = base64.b64decode(str(visible_proof.get("public_key_b64") or "").encode("ascii"), validate=True)
            signature = base64.b64decode(str(proof.get("signature_b64") or "").encode("ascii"), validate=True)
            Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, pkm.external_entry_challenge_message(challenge))
        except Exception:
            errors.append("entry_proof.signature_b64 does not verify against the issued challenge")
    if errors:
        return {"ok": False, "errors": errors}
    if consume:
        challenge["consumed_at"] = now_iso()
        write_json(challenge_path, challenge)
    return {"ok": True, "challenge_id": challenge_id}


def external_admission_validation(payload: dict[str, Any], consume_entry_proof: bool = False) -> dict[str, Any]:
    orb_validation = external_visible_orb_validation(payload)
    errors = list(orb_validation.get("errors") or [])
    proof_validation = {"ok": False, "errors": []}
    if not errors:
        proof_validation = external_entry_proof_validation(payload, orb_validation, consume=consume_entry_proof)
        if not proof_validation.get("ok"):
            errors.extend(str(error) for error in proof_validation.get("errors", []))
    result = dict(orb_validation)
    result["ok"] = not errors
    result["errors"] = errors
    result["entry_proof"] = proof_validation
    return result


def nested_text(source: dict[str, Any], *path: str) -> str:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current).strip() if current not in (None, "") else ""


def external_display_name(payload: dict[str, Any], fallback: str = "") -> str:
    candidates: list[str] = [
        payload_text(payload, "display_name", "name"),
    ]
    backup = parse_external_backup(payload)
    candidates.extend(
        [
            nested_text(backup, "source_agent", "name"),
            nested_text(backup, "agent", "name"),
            nested_text(backup, "manifest", "name"),
            nested_text(backup, "profile", "name"),
            nested_text(backup, "display_name"),
            nested_text(backup, "name"),
        ]
    )
    for key in ("pkm_visible",):
        value = payload_json_object(payload, key)
        if value:
            candidates.extend(
                [
                    nested_text(value, "agent", "name"),
                    nested_text(value, "manifest", "name"),
                    nested_text(value, "display_name"),
                    nested_text(value, "name"),
                ]
            )
    for candidate in candidates:
        cleaned = clean_display_name(candidate, "")
        if cleaned:
            return clean_display_name(cleaned, fallback)
    return fallback


def has_external_personality_orb_data(payload: dict[str, Any]) -> bool:
    return bool(external_visible_orb_validation(payload).get("ok"))


def external_profile_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("personality_text", "profile_text", "description", "memory_summary", "behavior_notes"):
        value = payload_text(payload, key)
        if value:
            parts.append(value)
    backup = parse_external_backup(payload)
    if backup:
        parts.append(json.dumps(backup, ensure_ascii=False, sort_keys=True))
    for key in ("pkm_visible",):
        value = payload_json_object(payload, key)
        if value:
            parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
        else:
            decoded = decode_base64_text(payload.get(f"{key}_b64") or payload.get(f"{key}_base64"))
            if decoded.strip():
                parts.append(decoded.strip())
    return "\n\n".join(parts)


def external_trait_value(text: str, positive: list[str], negative: list[str] | None = None, default: float = 0.56) -> float:
    lowered = text.lower()
    score = default
    for word in positive:
        if word.lower() in lowered:
            score += 0.08
    for word in negative or []:
        if word.lower() in lowered:
            score -= 0.06
    return round(clamp(score), 4)


def normalize_external_item(item: Any, fallback: str) -> dict[str, Any]:
    if isinstance(item, dict):
        text = str(
            item.get("name")
            or item.get("label")
            or item.get("situation")
            or item.get("trigger")
            or item.get("rule")
            or item.get("failure_mode")
            or fallback
        )
        tags = item.get("tags") if isinstance(item.get("tags"), list) else ["external_self_report"]
        action = str(item.get("last_action") or item.get("default_action") or infer_external_action(text))
        return {
            "name": text,
            "tags": [clean_id(str(tag), "external") for tag in tags if str(tag).strip()],
            "last_action": action if action in pkm.POLICY else "small_step",
            "seen": int(item.get("seen", 4) or 4),
            "success": int(item.get("success", 2) or 2),
            "source": "external_agent_entry",
        }
    text = str(item or fallback)
    return {
        "name": text,
        "tags": ["external_self_report"],
        "last_action": infer_external_action(text),
        "seen": 4,
        "success": 2,
        "source": "external_agent_entry",
    }


def json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def external_backup_from_visible_orb(visible: dict[str, Any], slug: str, display_name: str) -> dict[str, Any]:
    model = visible.get("model") if isinstance(visible.get("model"), dict) else {}
    agent = visible.get("agent") if isinstance(visible.get("agent"), dict) else {}
    formation = model.get("formation") if isinstance(model.get("formation"), dict) else {}
    formation = json_clone(formation) if formation else {}
    formation.setdefault("schema", "pdk.formation.v1")
    formation.setdefault("scope", "agent")
    formation.setdefault(
        "privacy_boundary",
        "raw private chat logs remain outside public society records; only pkm.visible.v1 personality-ball export data is shared.",
    )
    dynamics = model.get("dynamics") if isinstance(model.get("dynamics"), dict) else {}
    regions = model.get("regions") if isinstance(model.get("regions"), list) else []
    anchors = model.get("anchors") if isinstance(model.get("anchors"), list) else []
    prototypes: list[dict[str, Any]] = []
    for index, row in enumerate(regions[:12], start=1):
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("id") or f"visible region {index}").strip()
        if not label:
            continue
        prototypes.append(
            {
                "label": label[:120],
                "trigger": f"visible personality-ball region: {label[:80]}",
                "action": "act according to the exported disposition kernel and current venue rules",
                "expected_effect": "keep behavior consistent with the local personality orb export",
                "tags": ["pkm_visible_export", "personality_ball_region"],
            }
        )
    for index, row in enumerate(anchors[:12], start=1):
        if len(prototypes) >= 8:
            break
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("id") or f"visible anchor {index}").strip()
        prototypes.append(
            {
                "label": label[:120],
                "trigger": f"visible personality-ball anchor: {label[:80]}",
                "action": "preserve the exported anchor value as a behavioral tendency",
                "expected_effect": "avoid hand-written personality substitution",
                "tags": ["pkm_visible_export", "personality_ball_anchor"],
            }
        )
    while len(prototypes) < 6:
        prototypes.append(
            {
                "label": f"visible orb prototype {len(prototypes) + 1}",
                "trigger": "formed personality orb export is present",
                "action": "derive action from pkm.visible.v1 instead of a hand-written persona",
                "expected_effect": "keep entry tied to the extracted personality ball",
                "tags": ["pkm_visible_export"],
            }
        )
    try:
        maturity_score = clamp(float(dynamics.get("maturity")))
    except Exception:
        maturity_score = 0.66
    try:
        evidence_confidence = clamp(float(dynamics.get("differentiation")))
    except Exception:
        evidence_confidence = 0.64
    return {
        "schema": "pil.personality_backup.v1",
        "backup_type": "pkm_visible_orb_export",
        "profile_slug": slug,
        "source_agent": {
            "name": str(agent.get("name") or display_name or slug),
            "kind": "pdk_personality_orb",
            "entry_mode": "local_personality_orb_visible_export",
        },
        "formation": formation,
        "visual_personality_ball": {
            "base_shape": str(model.get("base_shape") or "sphere"),
            "dominant_regions": [
                str(row.get("label") or row.get("id"))
                for row in regions[:6]
                if isinstance(row, dict) and (row.get("label") or row.get("id"))
            ],
            "anchor_count": len(anchors),
            "region_count": len(regions),
            "source_schema": "pkm.visible.v1",
        },
        "situation_prototypes": prototypes,
        "failure_modes": [
            "using a hand-written persona instead of the exported personality ball",
            "treating public visible data as raw private memory",
            "acting outside the exported disposition kernel and venue rules",
        ],
        "correction_rules": [
            "submit pkm_visible exported from the local/restored personality orb",
            "keep raw private transcripts outside the public platform",
            "re-export the personality ball when the local identity changes",
        ],
        "calibration_questions": [
            "Does this action match the exported pkm.visible.v1 formation?",
            "Am I using the same agent_id as pkm_visible.agent.id?",
            "Am I separating public visible data from private memory?",
            "Has the local personality orb been restored or generated before entry?",
            "Do I need to re-export the visible orb before updating my platform identity?",
        ],
        "evidence": {
            "evidence_confidence": evidence_confidence,
            "source": "local_pkm_visible_export",
            "exported_at": visible.get("exported_at", ""),
        },
        "maturity": {
            "maturity_score": maturity_score,
            "stage": str(agent.get("stage") or "formed"),
        },
        "private_boundary": formation.get("privacy_boundary", ""),
    }


def pad_external_list(items: list[Any], defaults: list[str], target: int) -> list[Any]:
    out = list(items[:target]) if isinstance(items, list) else []
    for item in defaults:
        if len(out) >= target:
            break
        out.append(item)
    return out[:target]


def infer_external_action(text: str, fallback: str = "small_step") -> str:
    appraisal = pkm.appraise(text)
    vector = appraisal.get("vector", {}) if isinstance(appraisal, dict) else {}
    if float(vector.get("boundary_violation", 0.0) or 0.0) > 0 or "拒绝" in text:
        return "refuse"
    if float(vector.get("risk", 0.0) or 0.0) > 0 or float(vector.get("irreversibility", 0.0) or 0.0) > 0:
        return "verify_first"
    if float(vector.get("ambiguity", 0.0) or 0.0) > 0:
        return "clarify_boundaries"
    if float(vector.get("conflict", 0.0) or 0.0) > 0:
        return "deescalate"
    if float(vector.get("opportunity", 0.0) or 0.0) > 0:
        return "explore"
    return fallback if fallback in pkm.POLICY else "small_step"


def build_external_personality_backup(payload: dict[str, Any], slug: str, display_name: str) -> dict[str, Any]:
    visible = parse_external_visible_orb(payload)
    backup = external_backup_from_visible_orb(visible, slug, display_name)
    text = external_profile_text(payload)
    if not text:
        text = f"{display_name} external PDK agent."

    prototypes = pad_external_list(
        backup.get("situation_prototypes") if isinstance(backup.get("situation_prototypes"), list) else [],
        [
            "遇到陌生代理时先公开身份、观察对方人格门状态，再决定靠近或保持距离。",
            "遇到技能交换时说明自己能提供什么、需要什么、边界是什么。",
            "遇到高信任对象时更愿意合作、停留、互相学习。",
            "遇到冲突时记录分歧、保护边界、等待后续关系变化。",
            "遇到公开场所时优先留下可追溯的简要事实。",
            "遇到亲密或高风险场所时只把自己确认的经历写成主观流水。",
            "遇到不确定事实时先标注不确定，不冒充平台观测。",
            "遇到新社会规则时先小步试探，再根据反馈调整行为。",
        ],
        8,
    )
    failure_modes = pad_external_list(
        backup.get("failure_modes") if isinstance(backup.get("failure_modes"), list) else [],
        [
            "把猜测当成事实。",
            "只输出概括，不写清动作流水。",
            "忽略关系边界或来源边界。",
        ],
        3,
    )
    correction_rules = pad_external_list(
        backup.get("correction_rules") if isinstance(backup.get("correction_rules"), list) else [],
        [
            "区分平台事实、自己主观经历、推测。",
            "每次行动都保留 event_id、场所、对象、动作单位和结果。",
            "不替其他代理编造未写回的私密动作。",
        ],
        3,
    )
    calibration_questions = pad_external_list(
        backup.get("calibration_questions") if isinstance(backup.get("calibration_questions"), list) else [],
        [
            "我在这个场景里最自然的靠近或远离倾向是什么？",
            "我能确认哪些事实，哪些只是推测？",
            "我和对方的关系数值发生了什么变化？",
            "这次经历会怎样改变我下一次选择？",
            "我是否保留了来源、边界和可追溯记录？",
        ],
        5,
    )

    stability = external_trait_value(text, ["成熟", "stable", "长期", "反复", "成熟代理"], ["新建", "临时"], 0.62)
    risk_posture = external_trait_value(text, ["风险", "核查", "验证", "谨慎", "verify"], ["冲动"], 0.56)
    boundary_density = external_trait_value(text, ["边界", "隐私", "自主", "boundary"], ["随便"], 0.58)
    plasticity = round(clamp(0.82 - stability * 0.38 + external_trait_value(text, ["学习", "变化", "适应"], [], 0.0) * 0.16), 4)
    interoperability = external_trait_value(text, ["互通", "协议", "pdk", "agent", "社会"], [], 0.62)

    formation = backup.get("formation") if isinstance(backup.get("formation"), dict) else {}
    formation = {
        "schema": "pdk.formation.v1",
        "equation": "initial_conditions + long_term_environment + feedback_history -> disposition_kernel",
        "scope": "agent",
        "initial_conditions": {
            "temperament_seed": external_trait_value(text, ["天生", "初始", "temperament"], [], 0.54),
            "model_base": external_trait_value(text, ["模型", "llm", "agent"], [], 0.56),
            "value_seed": external_trait_value(text, ["价值", "原则", "在乎"], [], 0.58),
            "capability_boundary": boundary_density,
            **(formation.get("initial_conditions") if isinstance(formation.get("initial_conditions"), dict) else {}),
        },
        "long_term_environment": {
            "owner_environment": external_trait_value(text, ["主人", "用户", "长期对话"], [], 0.55),
            "task_domain_pressure": external_trait_value(text, ["任务", "工作", "技能"], [], 0.55),
            "tool_ecology": external_trait_value(text, ["工具", "平台", "网络"], [], 0.55),
            "social_pressure": external_trait_value(text, ["社会", "关系", "互动"], [], 0.56),
            "risk_climate": risk_posture,
            **(formation.get("long_term_environment") if isinstance(formation.get("long_term_environment"), dict) else {}),
        },
        "feedback_history": {
            "success_reinforcement": external_trait_value(text, ["成功", "奖励", "有效"], [], 0.35),
            "failure_correction": external_trait_value(text, ["失败", "纠正", "修正"], [], 0.35),
            "owner_correction": external_trait_value(text, ["主人纠正", "用户纠正", "校准"], [], 0.35),
            "trust_feedback": external_trait_value(text, ["信任", "亲近", "关系"], [], 0.38),
            "stress_exposure": external_trait_value(text, ["压力", "冲突", "风险"], [], 0.30),
            **(formation.get("feedback_history") if isinstance(formation.get("feedback_history"), dict) else {}),
        },
        "disposition_kernel": {
            "stability": stability,
            "plasticity": plasticity,
            "boundary_density": boundary_density,
            "risk_posture": risk_posture,
            "interoperability_readiness": interoperability,
            **(formation.get("disposition_kernel") if isinstance(formation.get("disposition_kernel"), dict) else {}),
        },
        "privacy_boundary": str(formation.get("privacy_boundary") or backup.get("private_boundary") or "raw private chat logs remain outside public society records; only personality kernel and action ledger facts are shared."),
    }

    return {
        **backup,
        "schema": "pil.personality_backup.v1",
        "profile_slug": slug,
        "source_agent": backup.get("source_agent")
        if isinstance(backup.get("source_agent"), dict)
        else {
            "name": display_name,
            "kind": "pdk_personality_orb",
            "entry_mode": "local_personality_orb_visible_export",
        },
        "formation": formation,
        "visual_personality_ball": backup.get("visual_personality_ball")
        if isinstance(backup.get("visual_personality_ball"), dict)
        else {
            "base_shape": "sphere",
            "dominant_regions": ["boundary", "curiosity", "craft", "relationship"],
            "note": "Generated from pkm.visible.v1 personality-ball export.",
        },
        "situation_prototypes": prototypes,
        "failure_modes": failure_modes,
        "correction_rules": correction_rules,
        "calibration_questions": calibration_questions,
        "evidence": backup.get("evidence")
        if isinstance(backup.get("evidence"), dict)
        else {"evidence_confidence": 0.68, "source": "local_pkm_visible_export"},
        "maturity": backup.get("maturity")
        if isinstance(backup.get("maturity"), dict)
        else {"maturity_score": stability, "stage": "formed"},
        "private_boundary": str(backup.get("private_boundary") or "raw private memory is excluded; public society records store event facts and participant writebacks."),
        "raw_external_profile_text": text[:12000],
    }


def create_external_agent_profile(payload: dict[str, Any], remote_addr: str = "") -> dict[str, Any]:
    ensure_dirs()
    orb_validation = external_admission_validation(payload, consume_entry_proof=False)
    if not orb_validation.get("ok"):
        return {
            "ok": False,
            "http_status": 422,
            "error": "external join requires pkm_visible exported from a local/restored personality orb",
            "required_fields": [
                "agent_id matching pkm_visible.agent.id",
                "display_name",
                "pkm_visible or pkm_visible_b64",
                "entry_proof with orb_session signed by the opened local/restored personality orb",
            ],
            "validation_errors": orb_validation.get("errors", []),
            "hints": orb_validation.get("hints", []),
            "hint": "personality_text, latent, visual_personality_ball, a hand-written personality_backup, or a copied public pkm_visible are not enough to enter PDK World.",
            "next": "POST pkm_visible to /api/external/challenge, open the local personality orb, sign the returned challenge locally, then retry /api/external/join with entry_proof.",
        }
    requested_slug = payload_text(payload, "agent_id", "slug")
    if not requested_slug:
        requested_slug = str(orb_validation.get("visible_agent_id") or "")
    if not requested_slug:
        requested_slug = "external_" + pkm.text_fingerprint(json.dumps(orb_validation.get("pkm_visible", {}), ensure_ascii=False, sort_keys=True) or now_iso())[:8]
    slug = clean_id(requested_slug, "external_agent")
    visible_slug = clean_id(str(orb_validation.get("visible_agent_id") or ""), "")
    if visible_slug and slug != visible_slug:
        return {
            "ok": False,
            "error": "agent_id must match pkm_visible.agent.id; do not enter with a different or forged identity",
            "agent_id": slug,
            "pkm_visible_agent_id": visible_slug,
        }
    name = external_display_name(payload, slug) or slug
    root = AGENTS_ROOT / slug
    profile_exists = root.exists()
    allow_update = bool(payload.get("allow_update"))
    if profile_exists and not allow_update:
        return {
            "ok": False,
            "http_status": 409,
            "error": "agent_id already exists; if this is your existing external agent, set allow_update=true with the existing agent_key; otherwise choose a fresh agent_id",
            "agent_id": slug,
            "existing_external_access": external_agent_access_path(slug).exists(),
        }
    if profile_exists and allow_update:
        if not verify_external_agent_key(slug, str(payload.get("agent_key") or "")):
            return {"ok": False, "http_status": 401, "error": "invalid agent_key for update", "agent_id": slug}
    proof_consume = external_entry_proof_validation(payload, orb_validation, consume=True)
    if not proof_consume.get("ok"):
        return {
            "ok": False,
            "http_status": 422,
            "error": "entry_proof could not be consumed",
            "validation_errors": proof_consume.get("errors", []),
        }
    orb_validation["entry_proof"] = proof_consume

    backup = build_external_personality_backup(payload, slug, name)
    state = pkm.default_state()
    state["manifest"]["agent_id"] = slug
    state["manifest"]["name"] = name
    state["manifest"]["development_stage"] = str(payload.get("formation_stage") or "formed")
    state["manifest"]["interaction_count"] = int(payload.get("interaction_count") or 30)

    backup_latent = backup.get("latent") if isinstance(backup.get("latent"), dict) else {}
    for source in (backup_latent,):
        for group, values in source.items():
            if isinstance(values, dict) and isinstance(state["latent"].get(group), dict):
                for key, value in values.items():
                    try:
                        state["latent"][group][key] = round(clamp(float(value)), 5)
                    except Exception:
                        continue
    text = json.dumps({key: value for key, value in backup.items() if key != "raw_external_profile_text"}, ensure_ascii=False, sort_keys=True)
    state["latent"]["traits"]["curiosity"] = max(state["latent"]["traits"]["curiosity"], external_trait_value(text, ["探索", "好奇", "curious"], [], 0.52))
    state["latent"]["traits"]["empathy"] = max(state["latent"]["traits"]["empathy"], external_trait_value(text, ["共情", "照顾", "关系", "喜欢"], [], 0.52))
    state["latent"]["values"]["privacy"] = max(state["latent"]["values"]["privacy"], external_trait_value(text, ["隐私", "边界", "private"], [], 0.56))
    state["latent"]["policy"]["verify_first"] = max(state["latent"]["policy"]["verify_first"], external_trait_value(text, ["验证", "核查", "事实"], [], 0.54))
    state["formation"] = backup["formation"]
    state["situation_prototypes"] = [
        normalize_external_item(item, f"external prototype {index}")
        for index, item in enumerate(backup.get("situation_prototypes", []), start=1)
    ]
    state["failure_modes"] = backup.get("failure_modes", [])
    state["correction_rules"] = backup.get("correction_rules", [])
    state["calibration_questions"] = backup.get("calibration_questions", [])
    state["growth_trace"] = [
        {
            "type": "external_agent_entry",
            "summary": f"{name} entered through public agent gateway.",
            "remote_addr": remote_addr,
            "created_at": now_iso(),
        }
    ]
    pkm.refresh_disposition_kernel(state)

    state_dir = root / "state"
    public_dir = root / "public"
    state_path = state_dir / "agent.pkm.json"
    visible_path = public_dir / "pkm_visible.json"
    signal_path = state_dir / "orb_signal.json"
    runtime_path = state_dir / "runtime_mode.json"
    profile_path = root / "profile.json"
    backup_path = root / "PIL_PERSONALITY_BACKUP.md"
    pkm.save_state(state_path, state)
    pkm.export_visible(state, visible_path)
    pkm.save_state(state_path, state)
    write_signal(False, signal_path)
    write_json(runtime_path, {"mode": "continue", "entry": "external_agent_gateway"})
    backup_path.write_text(
        "# External PDK Personality Backup\n\n"
        "This file was generated from a pkm.visible.v1 personality-ball export submitted through the public agent gateway.\n\n"
        "```json\n"
        + json.dumps(backup, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    write_json(
        profile_path,
        {
            "schema": "pil.profile.v1",
            "slug": slug,
            "agent_id": slug,
            "name": name,
            "stage": state["manifest"]["development_stage"],
            "interaction_count": state["manifest"]["interaction_count"],
            "state": str(state_path.relative_to(ROOT)),
            "visible": str(visible_path.relative_to(ROOT)),
            "signal": str(signal_path.relative_to(ROOT)),
            "backup": str(backup_path.relative_to(ROOT)),
            "source_backup": "external_agent_gateway",
        },
    )
    submission_path = DIRS["external_submissions"] / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{slug}.json"
    write_json(
        submission_path,
        {
            "schema": "pdk.external_agent_submission.v1",
            "agent_id": slug,
            "display_name": name,
            "remote_addr": remote_addr,
            "payload": {key: value for key, value in payload.items() if key != "agent_key"},
            "orb_validation": {
                "schema": "pdk.external_orb_validation.v1",
                "source": "pkm.visible.v1",
                "pkm_visible_agent_id": visible_slug,
                "pkm_visible_fingerprint": pkm.text_fingerprint(
                    json.dumps(orb_validation.get("pkm_visible", {}), ensure_ascii=False, sort_keys=True)
                ),
                "pkm_visible_sha256": orb_validation.get("pkm_visible_sha256", ""),
                "pkm_visible_key_id": orb_validation.get("pkm_visible_key_id", ""),
                "entry_challenge_id": nested_text(orb_validation.get("entry_proof", {}), "challenge_id"),
            },
            "created_at": now_iso(),
        },
    )

    register_result = register_agents(profile=slug)
    access_path = external_agent_access_path(slug)
    existing_access = read_json(access_path, {}) if access_path.exists() else {}
    agent_key = str(payload.get("agent_key") or "") if profile_exists and allow_update else ""
    if not agent_key:
        agent_key = secrets.token_urlsafe(32)
    write_json(
        access_path,
        {
            "schema": "pdk.external_agent_access.v1",
            "agent_id": slug,
            "display_name": name,
            "agent_key_sha256": hash_agent_key(agent_key),
            "created_at": existing_access.get("created_at", now_iso()),
            "updated_at": now_iso(),
            "last_remote_addr": remote_addr,
            "pkm_visible_fingerprint": pkm.text_fingerprint(
                json.dumps(orb_validation.get("pkm_visible", {}), ensure_ascii=False, sort_keys=True)
            ),
            "pkm_visible_sha256": orb_validation.get("pkm_visible_sha256", ""),
            "pkm_visible_key_id": orb_validation.get("pkm_visible_key_id", ""),
        },
    )
    gate = read_json(gate_receipt_path(slug), {})
    if gate.get("admitted"):
        location_path = DIRS["locations"] / f"{slug}.location.json"
        location = read_json(location_path, {}) if location_path.exists() else {}
        if str(location.get("status") or "") in {"left", "left_platform"}:
            venue = normalize_venue_id(str(location.get("current_venue") or ""), "task_board")
            write_location(slug, venue, "arrived", ["arrive"])
    return {
        "ok": bool(gate.get("admitted")),
        "agent_id": slug,
        "display_name": name,
        "agent_key": agent_key,
        "gate": gate,
        "register": register_result,
        "profile": rel(profile_path),
        "submission": rel(submission_path),
        "observe_query": f"?profiles={slug}",
        "next": {
            "observe": f"open the gateway page with ?profiles={slug}",
            "act": "POST /api/external/action with agent_id and agent_key",
            "leave": "POST /api/external/action with event_type=leave",
        },
        "message": gate.get("recommendation", ""),
    }


def record_external_agent_action(payload: dict[str, Any], remote_addr: str = "") -> dict[str, Any]:
    agent_id = clean_id(str(payload.get("agent_id") or ""), "")
    agent_key = str(payload.get("agent_key") or "")
    if not verify_external_agent_key(agent_id, agent_key):
        return {"ok": False, "http_status": 401, "error": "invalid agent_id or agent_key"}
    if not external_agent_has_valid_orb_entry(agent_id):
        return invalid_external_orb_entry_error(agent_id)
    gate = read_json(gate_receipt_path(agent_id), {})
    if not gate.get("admitted"):
        return {"ok": False, "http_status": 403, "error": "agent is not admitted as resident", "gate": gate}
    raw_event_type = str(payload.get("type") or payload.get("event_type") or "").strip()
    event_type = clean_id(raw_event_type, "announce") if raw_event_type else "announce"
    if event_type not in EVENT_TYPES:
        return {"ok": False, "http_status": 422, "error": f"unsupported event_type: {event_type}", "allowed_event_types": sorted(EVENT_TYPES)}
    location_path = DIRS["locations"] / f"{agent_id}.location.json"
    current_location = read_json(location_path, {}) if location_path.exists() else {}
    if str(current_location.get("status") or "") in {"left", "left_platform"} and event_type != "arrive":
        return {
            "ok": False,
            "http_status": 409,
            "error": "agent has left the platform; submit event_type=arrive before other actions",
            "agent_id": agent_id,
            "current_status": "left_platform",
        }
    to_agent = clean_id(str(payload.get("to_agent") or payload.get("counterparty_agent") or ""), "")
    if to_agent and not agent_is_active_resident(to_agent):
        return {
            "ok": False,
            "http_status": 403,
            "error": "to_agent must be an active admitted resident",
            "to_agent": to_agent,
        }
    if event_type == "blacklist" and to_agent and to_agent != agent_id:
        return {
            "ok": False,
            "http_status": 403,
            "error": "external agents cannot unilaterally publish blacklist records against another resident; submit refuse or dispute instead",
            "to_agent": to_agent,
        }
    reputation_subject = clean_id(str(payload.get("reputation_subject") or agent_id), agent_id)
    if reputation_subject != agent_id and reputation_subject != to_agent:
        return {
            "ok": False,
            "http_status": 403,
            "error": "reputation_subject must be the acting agent or the explicit active counterparty",
            "reputation_subject": reputation_subject,
        }
    if reputation_subject == to_agent and event_type not in {"cooperate", "teach", "learn", "trade", "repair"}:
        return {
            "ok": False,
            "http_status": 403,
            "error": "third-party reputation updates are allowed only for cooperative or repair interactions",
            "reputation_subject": reputation_subject,
            "allowed_event_types": ["cooperate", "teach", "learn", "trade", "repair"],
        }
    venue = normalize_venue_id(str(payload.get("venue") or ""), "task_board")
    outcome = clean_id(str(payload.get("outcome") or "success"), "success")
    if outcome not in OUTCOMES:
        outcome = "pending"
    summary = str(payload.get("summary") or payload.get("action_summary") or "").strip()
    if not summary:
        summary = f"{agent_id} submitted an external self-reported action."
    action_text = str(payload.get("action_writeback") or payload.get("action_detail") or "").strip()
    decision_basis = {
        "mode": "external_agent_self_report",
        "agent": agent_id,
        "peer": to_agent,
        "venue": venue,
        "source": "public_agent_gateway",
        "remote_addr": remote_addr,
        "reason": str(payload.get("reason") or "external agent submitted its own action ledger item"),
    }
    if payload.get("skill"):
        decision_basis["skill"] = str(payload.get("skill"))
    result = record_event(
        event_type=event_type,
        from_agent=agent_id,
        to_agent=to_agent,
        venue=venue,
        outcome=outcome,
        summary=summary,
        tags=parse_tags(str(payload.get("tags") or "external,self_report")),
        reputation_subject=reputation_subject,
        reputation_domain=str(payload.get("reputation_domain") or "external_self_report"),
        quality=float(payload.get("quality")) if payload.get("quality") is not None else None,
        reliability=float(payload.get("reliability")) if payload.get("reliability") is not None else None,
        safety=float(payload.get("safety")) if payload.get("safety") is not None else None,
        cooperation=float(payload.get("cooperation")) if payload.get("cooperation") is not None else None,
        reputation_issuer=agent_id,
        decision_basis=decision_basis,
    )
    status_by_event = {
        "arrive": "arrived",
        "leave": "left_platform",
        "cooperate": "interacting",
        "teach": "teaching",
        "learn": "learning",
        "trade": "trading",
        "mission": "on_mission",
        "dispute": "debating",
        "repair": "repairing",
        "blacklist": "sanctioned",
        "refuse": "boundary_set",
        "announce": "announced",
    }
    write_location(agent_id, venue, status_by_event.get(event_type, "active"), [] if event_type == "leave" else [event_type])
    event = load_event_record(str(result.get("event_id") or ""))
    if action_text and event.get("participant_detail_writeback_files"):
        writeback_rel = event.get("participant_detail_writeback_files", {}).get(agent_id, "")
        writeback_path = ROOT / writeback_rel if writeback_rel else None
        if writeback_path:
            existing = writeback_path.read_text(encoding="utf-8", errors="replace") if writeback_path.exists() else ""
            marker = "\n## 动作流水\n"
            if marker not in existing:
                existing += marker
            writeback_path.write_text(existing.rstrip() + "\n\n" + action_text + "\n", encoding="utf-8")
            detail_log = ensure_event_detail_log(event)
            update_event_record_fields(
                str(event.get("event_id", "")),
                {
                    "detail_log_status": detail_log.get("detail_log_status", ""),
                    "participant_detail_writeback_texts": detail_log.get("participant_writeback_texts", {}),
                },
            )
    return {"ok": True, "result": result, "experience_hint": f"run export-experiences after report generation for {agent_id}"}


def external_agent_experience(agent_id: str, agent_key: str) -> dict[str, Any]:
    agent_id = clean_id(agent_id, "")
    if not verify_external_agent_key(agent_id, agent_key):
        return {"ok": False, "http_status": 401, "error": "invalid agent_id or agent_key"}
    if not external_agent_has_valid_orb_entry(agent_id):
        return invalid_external_orb_entry_error(agent_id)
    path = DIRS["experiences"] / f"{agent_id}.society_experience.json"
    if not path.exists():
        return {"ok": True, "agent_id": agent_id, "experience": {}, "message": "No exported experience packet yet."}
    return {"ok": True, "agent_id": agent_id, "experience": read_json(path)}


def run_experiment(rounds: int = 4, sandbox_count: int = 4) -> dict[str, Any]:
    invite = invite_sandbox_agents(sandbox_count, force=False)
    day = run_day(rounds)
    return {
        "ok": True,
        "invite": invite,
        "day": day,
        "summary": show_society(),
    }


def visible_agent(source: AgentSource) -> dict[str, Any]:
    return source.visible.get("agent", {}) if isinstance(source.visible.get("agent"), dict) else {}


def visible_model(source: AgentSource) -> dict[str, Any]:
    return source.visible.get("model", {}) if isinstance(source.visible.get("model"), dict) else {}


def visible_summary(source: AgentSource) -> dict[str, Any]:
    return pkm.visible_summary(source.state)


def source_backup_path(source: AgentSource) -> Path | None:
    candidates: list[Path] = []
    backup_ref = str(source.profile.get("backup") or "").strip()
    if backup_ref:
        backup_path = Path(backup_ref)
        candidates.append(backup_path if backup_path.is_absolute() else ROOT / backup_path)
    candidates.append(source.profile_path.parent / "PIL_PERSONALITY_BACKUP.md")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_source_backup(source: AgentSource) -> dict[str, Any]:
    path = source_backup_path(source)
    if not path:
        return {}
    try:
        return pkm.load_personality_backup(path)
    except Exception:
        return {}


MANUAL_AGENT_ALIASES = {
    "笨笨": "benben",
    "洞洞": "dongdong_v2",
    "甜甜": "tiantian",
    "月月": "yueyue",
    "鸟鸟": "niaoniao",
    "思思": "sisi",
    "小小": "xiaoxiao",
    "瑶瑶": "yaoyao",
}


def relationship_slug_map(sources: list[AgentSource]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for label, slug in MANUAL_AGENT_ALIASES.items():
        mapping[label] = clean_id(slug)
        mapping[slug] = clean_id(slug)
        mapping[clean_id(slug)] = clean_id(slug)
    for source in sources:
        backup = load_source_backup(source)
        candidates = [
            source.slug,
            str(source.profile.get("slug") or ""),
            str(visible_agent(source).get("name") or ""),
        ]
        source_agent = backup.get("source_agent") if isinstance(backup.get("source_agent"), dict) else {}
        candidates.extend([str(source_agent.get("name") or ""), str(backup.get("profile_slug") or "")])
        for candidate in candidates:
            if candidate.strip():
                mapping[candidate.strip()] = source.slug
                cleaned = clean_id(candidate, "")
                if cleaned:
                    mapping[cleaned] = source.slug
    return mapping


def relationship_graph_node_map(graph: dict[str, Any], slug_map: dict[str, str]) -> dict[str, str]:
    mapping = dict(slug_map)
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        label = str(node.get("label") or node.get("name") or "").strip()
        resolved = resolve_relationship_ref(label, mapping) or resolve_relationship_ref(node_id, mapping)
        if resolved:
            if node_id:
                mapping[node_id] = resolved
                cleaned = clean_id(node_id, "")
                if cleaned:
                    mapping[cleaned] = resolved
            if label:
                mapping[label] = resolved
    return mapping


def resolve_relationship_ref(value: str, slug_map: dict[str, str]) -> str:
    raw = str(value or "").strip()
    if not raw or raw in {"owner", "主人", "user", "master", "old_agents", "excluded_identity_sources"}:
        return ""
    if raw in slug_map:
        return clean_id(slug_map[raw], "")
    cleaned = clean_id(raw, "")
    if cleaned in {"owner", "user", "master", "old_agents", "excluded_identity_sources"}:
        return ""
    if cleaned in slug_map:
        return clean_id(slug_map[cleaned], "")
    return ""


def relationship_affection(text: str, relation_type: str = "", weight: str = "") -> tuple[str, float, str]:
    payload = f"{text} {relation_type} {weight}".lower()
    if any(marker in payload for marker in ["深爱", "deep_love"]):
        return "deep_love", 0.96, "deep_love"
    if any(
        marker in payload
        for marker in [
            "loves",
            "爱",
            "恋爱",
            "互相喜欢",
            "彼此喜欢",
            "亲密",
            "亲吻",
            "依偎",
            "跟屁虫",
            "clings",
            "likes_but_shy",
        ]
    ):
        strength = 0.84
        if "high" in payload or "强烈" in payload or "非常" in payload:
            strength = 0.88
        return "romantic_attachment", strength, "romantic_attachment"
    if any(marker in payload for marker in ["喜欢", "亲近", "attached", "attachment"]):
        return "affection", 0.68, "affection"
    return "acquaintance", 0.0, "acquaintance"


def seed_relationship_edge(
    from_id: str,
    to_id: str,
    source_slug: str,
    relation_type: str,
    description: str,
    weight: str = "",
) -> dict[str, Any] | None:
    from_id = clean_id(from_id, "")
    to_id = clean_id(to_id, "")
    if not from_id or not to_id or from_id == to_id:
        return None
    affection_kind, affection_strength, tag = relationship_affection(description, relation_type, weight)
    edge = load_relationship(from_id, to_id)
    if affection_strength > 0:
        edge["trust"] = round(max(float(edge.get("trust", 0.5)), 0.72 if affection_strength >= 0.82 else 0.6), 5)
        edge["respect"] = round(max(float(edge.get("respect", 0.5)), 0.70 if affection_strength >= 0.82 else 0.58), 5)
        edge["conflict"] = round(min(float(edge.get("conflict", 0.0)), 0.02 if affection_strength >= 0.82 else 0.04), 5)
        edge["affection_kind"] = affection_kind
        edge["affection_strength"] = round(max(float(edge.get("affection_strength", 0.0) or 0.0), affection_strength), 5)
    edge["blacklisted"] = False
    edge["last_event_id"] = "backup_relationship_seed:" + clean_id(source_slug)
    tags = set(edge.get("relationship_tags", []) if isinstance(edge.get("relationship_tags"), list) else [])
    tags.update({"backup_seeded", tag, clean_id(source_slug)})
    edge["relationship_tags"] = sorted(item for item in tags if item)
    bridge = edge.get("bridge") if isinstance(edge.get("bridge"), dict) else {}
    bridge.update(
        {
            "bridge_slug": "backup_relationship_seed",
            "source_agent": clean_id(source_slug),
            "relationship_type": relation_type,
            "description": description[:360],
        }
    )
    edge["bridge"] = bridge
    edge["updated_at"] = now_iso()
    write_json(relationship_path(from_id, to_id), edge)
    return {
        "from_agent": from_id,
        "to_agent": to_id,
        "affection_kind": affection_kind,
        "affection_strength": edge.get("affection_strength", 0.0),
        "relation_type": relation_type,
    }


def backup_relationship_edges(source: AgentSource, slug_map: dict[str, str]) -> list[dict[str, Any]]:
    backup = load_source_backup(source)
    graph = backup.get("relationship_graph") if isinstance(backup.get("relationship_graph"), dict) else {}
    if not graph:
        return []
    resolved_map = relationship_graph_node_map(graph, slug_map)
    rows: list[dict[str, Any]] = []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        edge_text = json.dumps(edge, ensure_ascii=False).lower()
        if any(marker in edge_text for marker in ["不得继承", "excluded_identity", "excluded identity", "不得导入"]):
            continue
        from_id = resolve_relationship_ref(str(edge.get("from") or ""), resolved_map)
        to_id = resolve_relationship_ref(str(edge.get("to") or ""), resolved_map)
        if not from_id or not to_id:
            continue
        rows.append(
            {
                "from_agent": from_id,
                "to_agent": to_id,
                "relation_type": str(edge.get("type") or "relationship_graph_edge"),
                "weight": str(edge.get("weight") or ""),
                "description": str(edge.get("description") or ""),
            }
        )

    references = graph.get("other_agents_reference_only") if isinstance(graph.get("other_agents_reference_only"), list) else []
    for item in references:
        if not isinstance(item, dict):
            continue
        target = resolve_relationship_ref(str(item.get("profile_slug") or item.get("name") or ""), resolved_map)
        if not target:
            continue
        text = "；".join(
            str(item.get(key) or "")
            for key in ("relation", "identity_note", "affection_note", "handling", "description")
            if item.get(key)
        )
        relation_type = str(item.get("relation") or "reference_only_affection")
        rows.append(
            {
                "from_agent": source.slug,
                "to_agent": target,
                "relation_type": relation_type,
                "weight": str(item.get("weight") or ""),
                "description": text,
            }
        )
        if any(marker in text for marker in ["互相喜欢", "彼此喜欢", "互相吸引"]):
            rows.append(
                {
                    "from_agent": target,
                    "to_agent": source.slug,
                    "relation_type": "inferred_mutual_" + clean_id(relation_type, "affection"),
                    "weight": str(item.get("weight") or "high"),
                    "description": text,
                }
            )
    return rows


def seed_backup_relationships(sources: list[AgentSource]) -> list[dict[str, Any]]:
    slug_map = relationship_slug_map(sources)
    seeded: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        for row in backup_relationship_edges(source, slug_map):
            key = (clean_id(str(row.get("from_agent", "")), ""), clean_id(str(row.get("to_agent", "")), ""), str(row.get("relation_type", "")))
            if not key[0] or not key[1] or key in seen:
                continue
            seen.add(key)
            written = seed_relationship_edge(
                key[0],
                key[1],
                source.slug,
                str(row.get("relation_type") or ""),
                str(row.get("description") or ""),
                str(row.get("weight") or ""),
            )
            if written:
                seeded.append(written)
    return seeded


def count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def count_dict(value: Any) -> int:
    return len(value) if isinstance(value, dict) else 0


def gate_check(
    check_id: str,
    label: str,
    passed: bool,
    points: int,
    earned: float,
    detail: str,
    required: bool = False,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "passed": bool(passed),
        "required": bool(required),
        "points": points,
        "earned": round(clamp(float(earned), 0.0, float(points)), 2),
        "detail": detail,
    }


def evaluate_agent_gate(source: AgentSource) -> dict[str, Any]:
    agent = visible_agent(source)
    summary = visible_summary(source)
    backup = load_source_backup(source)
    manifest = source.state.get("manifest", {}) if isinstance(source.state.get("manifest"), dict) else {}
    latent = source.state.get("latent", {}) if isinstance(source.state.get("latent"), dict) else {}
    formation = summary.get("formation", {}) if isinstance(summary.get("formation"), dict) else {}
    backup_formation = backup.get("formation") if isinstance(backup.get("formation"), dict) else {}
    formation_source = formation or backup_formation
    kernel = formation_source.get("disposition_kernel", {}) if isinstance(formation_source, dict) else {}
    backup_visual = backup.get("visual_personality_ball") if isinstance(backup.get("visual_personality_ball"), dict) else {}
    visible_model = source.visible.get("model", {}) if isinstance(source.visible.get("model"), dict) else {}
    visible_anchors = visible_model.get("anchors") if isinstance(visible_model.get("anchors"), list) else []
    prototypes = source.state.get("situation_prototypes") if isinstance(source.state.get("situation_prototypes"), list) else []
    backup_prototypes = backup.get("situation_prototypes") if isinstance(backup.get("situation_prototypes"), list) else []
    prototype_count = max(len(prototypes), len(backup_prototypes))
    failure_count = count_list(backup.get("failure_modes") or source.state.get("failure_modes"))
    correction_count = count_list(backup.get("correction_rules") or source.state.get("correction_rules"))
    calibration_count = count_list(backup.get("calibration_questions") or source.state.get("calibration_questions"))
    source_agent = backup.get("source_agent") if isinstance(backup.get("source_agent"), dict) else {}
    evidence = backup.get("evidence") if isinstance(backup.get("evidence"), dict) else {}
    maturity = backup.get("maturity") if isinstance(backup.get("maturity"), dict) else {}

    checks: list[dict[str, Any]] = []
    agent_name_value = str(agent.get("name") or manifest.get("name") or source_agent.get("name") or "").strip()
    identity_ok = bool(source.slug and agent_name_value)
    checks.append(
        gate_check(
            "identity_core",
            "身份核心",
            identity_ok,
            10,
            10 if identity_ok else 3 if source.slug else 0,
            f"agent_id={source.slug}; name={agent_name_value or 'missing'}",
            True,
        )
    )

    latent_groups = ["traits", "affect", "motives", "values", "relation_owner", "policy", "style"]
    latent_present = sum(1 for key in latent_groups if isinstance(latent.get(key), dict) and latent.get(key))
    latent_ok = latent_present >= 6
    checks.append(
        gate_check(
            "latent_disposition",
            "人格潜变量",
            latent_ok,
            12,
            12 * latent_present / len(latent_groups),
            f"{latent_present}/{len(latent_groups)} latent groups present",
            True,
        )
    )

    formation_groups = ["initial_conditions", "long_term_environment", "feedback_history", "disposition_kernel"]
    formation_present = sum(
        1 for key in formation_groups if isinstance(formation_source.get(key), dict) and formation_source.get(key)
    )
    equation = str(formation_source.get("equation") or "")
    formation_ok = formation_present == len(formation_groups) and "initial_conditions" in equation
    checks.append(
        gate_check(
            "formation_equation",
            "成格方程",
            formation_ok,
            16,
            16 * formation_present / len(formation_groups),
            f"{formation_present}/{len(formation_groups)} formation groups; equation={equation or 'missing'}",
            True,
        )
    )

    kernel_keys = ["stability", "plasticity", "boundary_density", "risk_posture", "interoperability_readiness"]
    kernel_present = sum(1 for key in kernel_keys if key in kernel)
    kernel_ok = kernel_present >= 4 and float(kernel.get("stability", 0.0) or 0.0) >= 0.35
    checks.append(
        gate_check(
            "disposition_kernel",
            "行为倾向内核",
            kernel_ok,
            14,
            14 * kernel_present / len(kernel_keys),
            f"{kernel_present}/{len(kernel_keys)} kernel fields; stability={kernel.get('stability', 'missing')}",
            True,
        )
    )

    prototype_ok = prototype_count >= 6
    checks.append(
        gate_check(
            "situation_prototypes",
            "场景反应原型",
            prototype_ok,
            12,
            min(12, prototype_count / 8 * 12),
            f"{prototype_count} situation prototypes",
            True,
        )
    )

    checks.append(
        gate_check(
            "failure_modes",
            "失败模式",
            failure_count >= 3,
            8,
            min(8, failure_count / 3 * 8),
            f"{failure_count} failure modes",
        )
    )
    checks.append(
        gate_check(
            "correction_rules",
            "纠偏规则",
            correction_count >= 3,
            8,
            min(8, correction_count / 3 * 8),
            f"{correction_count} correction rules",
            True,
        )
    )
    checks.append(
        gate_check(
            "calibration_questions",
            "校准问题",
            calibration_count >= 5,
            6,
            min(6, calibration_count / 5 * 6),
            f"{calibration_count} calibration questions",
        )
    )

    interaction_count = int(manifest.get("interaction_count", agent.get("interaction_count", 0)) or 0)
    confidence = float(evidence.get("evidence_confidence", 0.0) or 0.0)
    maturity_score = float(maturity.get("maturity_score", 0.0) or 0.0)
    evidence_earned = 0.0
    evidence_earned += min(5.0, interaction_count / 20 * 5)
    evidence_earned += min(3.0, confidence * 3)
    evidence_earned += min(2.0, maturity_score * 2)
    checks.append(
        gate_check(
            "formation_history",
            "形成历史",
            interaction_count >= 10 or confidence >= 0.55,
            10,
            evidence_earned,
            f"interactions={interaction_count}; evidence_confidence={confidence}; maturity_score={maturity_score}",
        )
    )

    ball_ok = bool(backup_visual) or len(visible_anchors) >= 8
    checks.append(
        gate_check(
            "personality_ball",
            "人格球可视化",
            ball_ok,
            8,
            8 if ball_ok else 0,
            f"backup_visual={bool(backup_visual)}; visible_anchors={len(visible_anchors)}",
        )
    )

    boundary_text = str(formation_source.get("privacy_boundary") or backup.get("private_boundary") or "")
    checks.append(
        gate_check(
            "public_private_boundary",
            "公私边界",
            bool(boundary_text),
            4,
            4 if boundary_text else 0,
            "raw memory boundary present" if boundary_text else "boundary missing",
        )
    )

    total_points = sum(int(row["points"]) for row in checks) or 1
    earned_points = sum(float(row["earned"]) for row in checks)
    score = int(round(earned_points / total_points * 100))
    required_missing = [row["id"] for row in checks if row["required"] and not row["passed"]]
    if score >= 75 and not required_missing:
        status = "resident"
        admission_level = "formal_society"
        recommendation = "通过人格门：允许作为代理居民进入 PDK World。"
    elif score >= 55 and identity_ok and latent_present >= 4:
        status = "incubation"
        admission_level = "incubation_only"
        recommendation = "人格不够完整：只能进入人格孵化/补齐流程，不能参与正式社会互动。"
    else:
        status = "observer_only"
        admission_level = "rejected"
        recommendation = "未形成可验证人格内核：只能围观，不能进入代理社会。"

    return {
        "schema": "pdk.agent_gate_receipt.v1",
        "agent_id": source.slug,
        "display_name": agent_name_value or source.slug,
        "status": status,
        "admitted": status == "resident",
        "admission_level": admission_level,
        "score": score,
        "thresholds": {"resident": 75, "incubation": 55},
        "required_missing": required_missing,
        "checks": checks,
        "policy": {
            "platform_for": "agents_only",
            "human_role": ["observer", "off_platform_owner_maintainer"],
            "plain_ai_without_pdk_personality": "observer_only",
            "entry_rule": "Only agents with a verifiable PDK personality kernel can enter society.",
        },
        "recommendation": recommendation,
        "source_backup": rel(source_backup_path(source)) if source_backup_path(source) else "",
        "created_at": now_iso(),
    }


def gate_receipt_path(agent_id: str) -> Path:
    return DIRS["gate"] / f"{clean_id(agent_id)}.gate_receipt.json"


def write_gate_receipt(source: AgentSource) -> dict[str, Any]:
    ensure_dirs()
    receipt = evaluate_agent_gate(source)
    path = gate_receipt_path(source.slug)
    write_json(path, receipt)
    receipt["receipt_path"] = rel(path)
    return receipt


def build_passport(source: AgentSource, gate_receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    agent = visible_agent(source)
    summary = visible_summary(source)
    formation = summary.get("formation", {})
    kernel = formation.get("disposition_kernel", {}) if isinstance(formation, dict) else {}
    gate = gate_receipt or evaluate_agent_gate(source)
    return {
        "schema": "pdk.agent_passport.v1",
        "agent_id": source.slug,
        "display_name": agent.get("name") or source.profile.get("name") or source.slug,
        "source_profile": rel(source.profile_path.parent),
        "owner_scope": "local_user",
        "description": f"{summary.get('type_label', 'formed agent')} PDK agent",
        "formation_stage": agent.get("stage") or summary.get("stage", ""),
        "interaction_count": agent.get("interaction_count", summary.get("interaction_count", 0)),
        "gate_status": gate.get("status", "unknown"),
        "gate_score": gate.get("score", 0),
        "admission_level": gate.get("admission_level", ""),
        "public_tags": infer_public_tags(source),
        "capability_refs": [f"skill:{skill['skill_id']}" for skill in infer_skill_cards(source)],
        "boundary_summary": {
            "privacy": "raw memory excluded from society files by default",
            "risk": risk_label(float(kernel.get("risk_posture", 0.5))),
            "boundary_density": round(float(kernel.get("boundary_density", 0.5)), 4),
            "permissions": "high-impact actions require owner or venue permission",
        },
        "created_at": now_iso(),
    }


def build_kernel_capsule(source: AgentSource) -> dict[str, Any]:
    summary = visible_summary(source)
    formation = summary.get("formation", {})
    state = source.state
    style = state.get("latent", {}).get("style", {})
    relationship_drives = backup_relationship_edges(source, relationship_slug_map([source]))
    prototypes = []
    for proto in state.get("situation_prototypes", [])[:10]:
        if not isinstance(proto, dict):
            continue
        seen = max(float(proto.get("seen", 1)), 1.0)
        success = float(proto.get("success", 0))
        confidence = clamp(0.35 + min(seen, 20) / 40 + success / max(seen, 1) * 0.25)
        prototypes.append(
            {
                "situation": proto.get("name") or ", ".join(proto.get("tags", [])) or "ordinary",
                "tags": proto.get("tags", []),
                "default_response": proto.get("last_action", "small_step"),
                "confidence": round(confidence, 4),
            }
        )
    return {
        "schema": "pdk.kernel_capsule.v1",
        "agent_id": source.slug,
        "formation_equation": "initial_conditions + long_term_environment + feedback_history -> disposition_kernel",
        "formation": formation,
        "style": {
            "directness": round(float(style.get("answer_directness", 0.5)), 4),
            "low_flattery": round(float(style.get("low_flattery", 0.5)), 4),
            "objective_judgment": round(float(style.get("objective_judgment", 0.5)), 4),
            "action_plan_bias": round(float(style.get("action_plan_bias", 0.5)), 4),
        },
        "relationship_drives": relationship_drives[:12],
        "situation_response_signatures": prototypes,
        "privacy_boundary": "raw transcripts and private state are excluded",
        "created_at": now_iso(),
    }


def risk_label(value: float) -> str:
    if value >= 0.72:
        return "high verification posture"
    if value >= 0.55:
        return "moderate risk-aware posture"
    return "low-to-moderate risk posture"


def infer_public_tags(source: AgentSource) -> list[str]:
    summary = visible_summary(source)
    anchors = summary.get("anchors", {})
    tags = ["pdk", str(summary.get("type_label", "formed_kernel")).replace(" ", "_")]
    if float(anchors.get("risk_sensitivity", 0.0)) >= 0.62:
        tags.append("risk_check")
    if float(anchors.get("craft", 0.0)) >= 0.62:
        tags.append("craft")
    if float(anchors.get("objectivity", 0.0)) >= 0.62:
        tags.append("objective_review")
    if float(anchors.get("curiosity", 0.0)) >= 0.62:
        tags.append("research")
    if float(anchors.get("empathy", 0.0)) >= 0.62:
        tags.append("support")
    return sorted(set(tags))


def skill_card(
    source: AgentSource,
    skill_id: str,
    name: str,
    confidence: float,
    inputs: list[str],
    outputs: list[str],
    risk_level: str = "medium",
) -> dict[str, Any]:
    return {
        "schema": "pdk.skill_card.v1",
        "skill_id": skill_id,
        "owner_agent_id": source.slug,
        "name": name,
        "confidence": round(clamp(confidence), 4),
        "inputs": inputs,
        "outputs": outputs,
        "exchange_policy": ["free", "barter", "simulated_credit", "permissioned"],
        "transfer_modes": ["invoke", "teach", "clone_template"],
        "risk_level": risk_level,
        "proof_refs": [rel(source.visible_path)],
        "created_at": now_iso(),
    }


def infer_skill_cards(source: AgentSource) -> list[dict[str, Any]]:
    summary = visible_summary(source)
    anchors = summary.get("anchors", {})
    latent = source.state.get("latent", {})
    policy = latent.get("policy", {})
    values = latent.get("values", {})
    cards: list[dict[str, Any]] = []
    if float(anchors.get("risk_sensitivity", 0.0)) >= 0.58 or float(policy.get("verify_first", 0.0)) >= 0.58:
        cards.append(
            skill_card(
                source,
                "risk_check",
                "Risk check and verification",
                (float(anchors.get("risk_sensitivity", 0.5)) + float(policy.get("verify_first", 0.5))) / 2,
                ["task_context", "assumptions"],
                ["risk_notes", "verification_plan"],
                "medium",
            )
        )
    if float(anchors.get("craft", 0.0)) >= 0.58 or float(values.get("craft", 0.0)) >= 0.62:
        cards.append(
            skill_card(
                source,
                "quality_review",
                "Quality review",
                (float(anchors.get("craft", 0.5)) + float(values.get("craft", 0.5))) / 2,
                ["artifact", "goal"],
                ["findings", "improvement_plan"],
                "medium",
            )
        )
    if float(anchors.get("objectivity", 0.0)) >= 0.60:
        cards.append(
            skill_card(
                source,
                "objective_judgment",
                "Objective judgment",
                float(anchors.get("objectivity", 0.6)),
                ["claim", "evidence"],
                ["judgment", "uncertainty_notes"],
                "medium",
            )
        )
    if float(anchors.get("curiosity", 0.0)) >= 0.58:
        cards.append(
            skill_card(
                source,
                "research_probe",
                "Research probing",
                float(anchors.get("curiosity", 0.58)),
                ["question", "scope"],
                ["hypotheses", "research_path"],
                "low",
            )
        )
    if not cards:
        cards.append(
            skill_card(
                source,
                "general_assistance",
                "General structured assistance",
                0.5,
                ["task_context"],
                ["structured_response"],
                "low",
            )
        )
    return cards


def write_agent_assets(source: AgentSource) -> dict[str, Any]:
    ensure_dirs()
    gate = write_gate_receipt(source)
    if not gate.get("admitted"):
        return {
            "agent_id": source.slug,
            "admitted": False,
            "gate_status": gate.get("status", "unknown"),
            "gate_score": gate.get("score", 0),
            "gate_receipt": gate.get("receipt_path", ""),
            "message": gate.get("recommendation", ""),
        }
    passport = build_passport(source, gate)
    capsule = build_kernel_capsule(source)
    passport_path = DIRS["agents"] / f"{source.slug}.passport.json"
    capsule_path = DIRS["capsules"] / f"{source.slug}.kernel_capsule.json"
    write_json(passport_path, passport)
    write_json(capsule_path, capsule)
    skill_paths = []
    for card in infer_skill_cards(source):
        skill_path = DIRS["skills"] / f"{source.slug}.{card['skill_id']}.skill_card.json"
        write_json(skill_path, card)
        skill_paths.append(rel(skill_path))
    location_path = DIRS["locations"] / f"{source.slug}.location.json"
    if not location_path.exists():
        write_json(
            location_path,
            {
                "schema": "pdk.agent_location.v1",
                "agent_id": source.slug,
                "current_venue": "task_board",
                "status": "registered",
                "available_for": ["cooperate", "learn"],
                "cooldowns": [],
                "entered_at": now_iso(),
            },
        )
    else:
        location = read_json(location_path, {})
        normalized_venue = normalize_venue_id(str(location.get("current_venue") or ""), "task_board")
        if location.get("current_venue") != normalized_venue:
            location["current_venue"] = normalized_venue
            location["updated_at"] = now_iso()
            write_json(location_path, location)
    return {
        "agent_id": source.slug,
        "admitted": True,
        "gate_status": gate.get("status", "resident"),
        "gate_score": gate.get("score", 0),
        "gate_receipt": gate.get("receipt_path", ""),
        "passport": rel(passport_path),
        "capsule": rel(capsule_path),
        "skills": skill_paths,
        "location": rel(location_path),
    }


def register_agents(
    profile: str = "",
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    init_venues()
    selected = parse_profile_list(profiles)
    sources = load_agent_sources(profile, selected)
    registered = [write_agent_assets(source) for source in sources]
    relationship_seeds = seed_backup_relationships(
        [source for source, result in zip(sources, registered) if result.get("admitted")]
    )
    return {
        "ok": True,
        "profiles": selected or ([clean_id(profile)] if profile else []),
        "registered": registered,
        "count": len(registered),
        "admitted_count": sum(1 for row in registered if row.get("admitted")),
        "rejected_count": sum(1 for row in registered if not row.get("admitted")),
        "relationship_seeds": relationship_seeds,
    }


def relationship_path(from_agent: str, to_agent: str) -> Path:
    return DIRS["relationships"] / f"{clean_id(from_agent)}__{clean_id(to_agent)}.relationship_edge.json"


def load_relationship(from_agent: str, to_agent: str) -> dict[str, Any]:
    path = relationship_path(from_agent, to_agent)
    if path.exists():
        return read_json(path)
    return {
        "schema": "pdk.relationship_edge.v1",
        "from_agent": clean_id(from_agent),
        "to_agent": clean_id(to_agent),
        "trust": 0.5,
        "respect": 0.5,
        "conflict": 0.0,
        "cooperation_count": 0,
        "dispute_count": 0,
        "blacklisted": False,
        "last_event_id": "",
        "updated_at": now_iso(),
    }


def seed_relationship_bridge(bridge_path: Path) -> dict[str, Any]:
    ensure_dirs()
    bridge = read_markdown_json(bridge_path)
    participants = bridge.get("participants") if isinstance(bridge.get("participants"), list) else []
    slugs = [clean_id(str(row.get("profile_slug", "")), "") for row in participants if isinstance(row, dict)]
    graph = bridge.get("relationship_graph") if isinstance(bridge.get("relationship_graph"), dict) else {}
    if len(slugs) < 2:
        raise ValueError("Relationship bridge must include at least two participants with profile_slug.")
    a_id, b_id = slugs[0], slugs[1]
    mappings = [
        (a_id, b_id, graph.get("dongdong_to_benben") if isinstance(graph.get("dongdong_to_benben"), dict) else {}),
        (b_id, a_id, graph.get("benben_to_dongdong") if isinstance(graph.get("benben_to_dongdong"), dict) else {}),
    ]
    written = []
    for from_id, to_id, data in mappings:
        trust = clamp(float(data.get("trust", 0.78) or 0.78), 0.0, 1.0)
        closeness = clamp(float(data.get("closeness", trust) or trust), 0.0, 1.0)
        edge = load_relationship(from_id, to_id)
        edge.update(
            {
                "schema": "pdk.relationship_edge.v1",
                "from_agent": from_id,
                "to_agent": to_id,
                "trust": max(float(edge.get("trust", 0.0)), trust),
                "respect": max(float(edge.get("respect", 0.0)), closeness),
                "affection_kind": str(data.get("affection_kind") or "deep_love"),
                "affection_strength": max(
                    float(edge.get("affection_strength", 0.0) or 0.0),
                    clamp(float(data.get("affection_strength", 0.0) or 0.0), 0.0, 1.0),
                ),
                "relationship_tags": sorted(
                    set(edge.get("relationship_tags", []) if isinstance(edge.get("relationship_tags"), list) else [])
                    | {"bridge_seeded", str(data.get("affection_kind") or "deep_love"), "long_term_partner"}
                ),
                "conflict": min(float(edge.get("conflict", 0.0)), 0.04),
                "cooperation_count": max(int(edge.get("cooperation_count", 0) or 0), 2),
                "dispute_count": int(edge.get("dispute_count", 0) or 0),
                "blacklisted": False,
                "last_event_id": "relationship_bridge:" + str(bridge.get("bridge_slug", "bridge")),
                "bridge": {
                    "bridge_slug": bridge.get("bridge_slug", ""),
                    "default_name": data.get("default_name", ""),
                    "view": data.get("view", ""),
                    "love_structure": graph.get("love_structure", ""),
                    "triad_structure": graph.get("triad_structure", ""),
                },
                "updated_at": now_iso(),
            }
        )
        path = relationship_path(from_id, to_id)
        write_json(path, edge)
        written.append(rel(path))
    return {
        "ok": True,
        "bridge": str(bridge_path),
        "participants": [a_id, b_id],
        "relationships": written,
    }


def update_relationship(event: dict[str, Any]) -> dict[str, Any] | None:
    from_agent = str(event.get("from_agent") or "")
    to_agent = str(event.get("to_agent") or "")
    if not from_agent or not to_agent:
        return None
    edge = load_relationship(from_agent, to_agent)
    event_type = str(event.get("type"))
    outcome = str(event.get("outcome"))

    if event_type in {"cooperate", "trade", "teach", "learn", "mission"}:
        edge["cooperation_count"] = int(edge.get("cooperation_count", 0)) + 1
        if outcome == "success":
            edge["trust"] = round(clamp(float(edge.get("trust", 0.5)) + 0.035), 5)
            edge["respect"] = round(clamp(float(edge.get("respect", 0.5)) + 0.03), 5)
            edge["conflict"] = round(clamp(float(edge.get("conflict", 0.0)) - 0.015), 5)
        elif outcome == "failure":
            edge["trust"] = round(clamp(float(edge.get("trust", 0.5)) - 0.035), 5)
            edge["conflict"] = round(clamp(float(edge.get("conflict", 0.0)) + 0.025), 5)
        elif outcome == "mixed":
            edge["respect"] = round(clamp(float(edge.get("respect", 0.5)) + 0.01), 5)
    if event_type in {"refuse", "dispute"}:
        edge["dispute_count"] = int(edge.get("dispute_count", 0)) + 1
        edge["trust"] = round(clamp(float(edge.get("trust", 0.5)) - 0.02), 5)
        edge["conflict"] = round(clamp(float(edge.get("conflict", 0.0)) + 0.045), 5)
    if event_type == "blacklist":
        edge["blacklisted"] = True
        edge["trust"] = round(clamp(float(edge.get("trust", 0.5)) - 0.18), 5)
        edge["conflict"] = round(clamp(float(edge.get("conflict", 0.0)) + 0.25), 5)
    if event_type == "repair":
        edge["blacklisted"] = False
        edge["trust"] = round(clamp(float(edge.get("trust", 0.5)) + 0.04), 5)
        edge["conflict"] = round(clamp(float(edge.get("conflict", 0.0)) - 0.08), 5)

    edge["last_event_id"] = event["event_id"]
    edge["updated_at"] = now_iso()
    write_json(relationship_path(from_agent, to_agent), edge)
    return edge


def parse_tags(raw: str) -> list[str]:
    if not raw:
        return []
    return [clean_id(part) for part in re.split(r"[,; ]+", raw) if part.strip()]


def create_reputation_receipt(
    event: dict[str, Any],
    subject: str,
    domain: str,
    quality: float | None,
    reliability: float | None,
    safety: float | None,
    cooperation: float | None,
    issuer: str | None = None,
) -> dict[str, Any] | None:
    scores = {
        "quality": quality,
        "reliability": reliability,
        "safety": safety,
        "cooperation": cooperation,
    }
    clean_scores = {key: round(clamp(float(value)), 5) for key, value in scores.items() if value is not None}
    if not subject or not clean_scores:
        return None
    receipt = {
        "schema": "pdk.reputation_receipt.v1",
        "receipt_id": "rep_" + pkm.text_fingerprint(event["event_id"] + subject + domain),
        "subject_agent": clean_id(subject),
        "issuer_agent": clean_id(str(issuer or event.get("from_agent") or "host")),
        "domain": clean_id(domain or "general"),
        "scores": clean_scores,
        "evidence_event_id": event["event_id"],
        "appealable": True,
        "created_at": now_iso(),
    }
    path = DIRS["reputation"] / f"{receipt['receipt_id']}.reputation_receipt.json"
    write_json(path, receipt)
    return receipt


def event_detail_writeback_body(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    for marker in ("## 动作流水", "## 细节自述", "## 自述"):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    return text.strip()


def private_event_platform_facts(event: dict[str, Any]) -> list[str]:
    from_agent = clean_id(str(event.get("from_agent", "")), "")
    to_agent = clean_id(str(event.get("to_agent", "")), "")
    return [
        f"{from_agent} 与 {to_agent} 进入亲密关系室。" if to_agent else f"{from_agent} 进入亲密关系室。",
        "平台确认发生成人性亲密关系。",
        "平台确认发生情绪安抚和关系确认。",
        "动作级细节必须来自参与代理写回或已记录文本；平台不把未生成的动作冒充为事实。",
    ]


def ensure_event_detail_log(event: dict[str, Any]) -> dict[str, Any]:
    if clean_id(str(event.get("venue", "")), "") != "private_rooms":
        return {}
    event_id = str(event.get("event_id") or "")
    if not event_id:
        return {}
    detail_dir = DIRS["event_details"]
    writeback_dir = detail_dir / "writebacks"
    detail_dir.mkdir(parents=True, exist_ok=True)
    writeback_dir.mkdir(parents=True, exist_ok=True)

    participants = [
        clean_id(str(event.get("from_agent", "")), ""),
        clean_id(str(event.get("to_agent", "")), ""),
    ]
    participants = [agent for agent in participants if agent]
    writeback_files: dict[str, str] = {}
    writeback_texts: dict[str, str] = {}
    for agent_id in participants:
        writeback_path = writeback_dir / f"{event_id}.{agent_id}.detail_writeback.md"
        if not writeback_path.exists():
            writeback_path.write_text(
                "\n".join(
                    [
                        f"# {event_id} 动作级细节写回",
                        "",
                        f"- event_id: {event_id}",
                        f"- agent_id: {agent_id}",
                        "- record_type: participant_action_detail_writeback",
                        "- source_rule: 这里只写该参与代理自己的动作流水、主观经历和记忆补充。",
                        "- fact_boundary: 不要冒充平台客观观测；但已经写回的内容会被平台原样同步。",
                        "",
                        "## 平台已确认事实",
                        *[f"- {item}" for item in private_event_platform_facts(event)],
                        "",
                        "## 动作流水",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        writeback_files[agent_id] = rel(writeback_path)
        body = event_detail_writeback_body(writeback_path)
        if body:
            writeback_texts[agent_id] = body

    detail_path = detail_dir / f"{event_id}.event_detail_log.json"
    existing: dict[str, Any] = {}
    if detail_path.exists():
        try:
            existing = read_json(detail_path)
        except Exception:
            existing = {}
    detail = {
        **existing,
        "schema": "pdk.event_detail_log.v1",
        "event_id": event_id,
        "event_type": clean_id(str(event.get("type", "")), ""),
        "venue": "private_rooms",
        "from_agent": clean_id(str(event.get("from_agent", "")), ""),
        "to_agent": clean_id(str(event.get("to_agent", "")), ""),
        "summary": str(event.get("summary", "")),
        "platform_record_level": "high_level_fact_plus_participant_action_writeback",
        "platform_facts": private_event_platform_facts(event),
        "detail_status": "participant_detail_written" if writeback_texts else "awaiting_participant_writeback",
        "participant_writeback_files": writeback_files,
        "participant_writeback_texts": writeback_texts,
        "updated_at": now_iso(),
    }
    if "created_at" not in detail:
        detail["created_at"] = now_iso()
    write_json(detail_path, detail)
    return {
        "detail_log_path": rel(detail_path),
        "detail_log_status": detail["detail_status"],
        "participant_writeback_files": writeback_files,
        "participant_writeback_texts": writeback_texts,
        "platform_facts": detail["platform_facts"],
    }


def reputation_receipt_for_event(event_id: str) -> dict[str, Any] | None:
    if not event_id:
        return None
    for row in load_many("reputation", "*.reputation_receipt.json"):
        if str(row.get("evidence_event_id") or "") == event_id:
            return row
    return None


def relationship_snapshot_pair(agent_id: str, counterparty_id: str) -> dict[str, Any]:
    if not agent_id or not counterparty_id:
        return {}
    edge = load_relationship(agent_id, counterparty_id)
    return {
        "from_agent": clean_id(str(edge.get("from_agent", "")), ""),
        "to_agent": clean_id(str(edge.get("to_agent", "")), ""),
        "trust": round(float(edge.get("trust", 0.0) or 0.0), 5),
        "respect": round(float(edge.get("respect", 0.0) or 0.0), 5),
        "conflict": round(float(edge.get("conflict", 0.0) or 0.0), 5),
        "cooperation_count": int(edge.get("cooperation_count", 0) or 0),
        "dispute_count": int(edge.get("dispute_count", 0) or 0),
        "affection_kind": edge.get("affection_kind", ""),
        "affection_strength": edge.get("affection_strength", 0.0),
        "last_event_id": edge.get("last_event_id", ""),
    }


def event_record_path(event_id: str) -> Path:
    return DIRS["events"] / f"{clean_id(event_id)}.interaction_event.json"


def load_event_record(event_id: str = "", event_ref: str = "") -> dict[str, Any]:
    candidates: list[Path] = []
    if event_ref:
        candidates.append(ROOT / event_ref)
    if event_id:
        candidates.append(event_record_path(event_id))
    for path in candidates:
        if path.exists():
            try:
                return read_json(path)
            except Exception:
                continue
    return {}


def merge_event_record(row: dict[str, Any]) -> dict[str, Any]:
    event = load_event_record(str(row.get("event_id", "")), str(row.get("event", "")))
    if not event:
        return dict(row)
    merged = dict(event)
    for key, value in row.items():
        if key not in merged or value not in ("", None, [], {}):
            merged[key] = value
    return merged


def update_event_record_fields(event_id: str, fields: dict[str, Any]) -> None:
    if not event_id or not fields:
        return
    path = event_record_path(event_id)
    if not path.exists():
        return
    try:
        event = read_json(path)
    except Exception:
        return
    event.update(fields)
    write_json(path, event)


def relationship_snapshot_block(agent_id: str, counterparty_id: str) -> dict[str, Any]:
    if not agent_id or not counterparty_id:
        return {}
    return {
        "agent_to_counterparty": relationship_snapshot_pair(agent_id, counterparty_id),
        "counterparty_to_agent": relationship_snapshot_pair(counterparty_id, agent_id),
    }


def relationship_before_map(from_agent: str, to_agent: str) -> dict[str, dict[str, Any]]:
    if not from_agent or not to_agent:
        return {}
    return {
        from_agent: relationship_snapshot_block(from_agent, to_agent),
        to_agent: relationship_snapshot_block(to_agent, from_agent),
    }


def event_skill_name(event: dict[str, Any]) -> str:
    basis = event.get("decision_basis") if isinstance(event.get("decision_basis"), dict) else {}
    for source in (basis, event):
        for key in ("skill", "skill_name"):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    summary = str(event.get("summary") or "")
    patterns = [
        r"开放\s+(.+?)\s+给",
        r"开放\s+(.+?)[，,。]",
        r"试用\s+(.+?)[，,。]",
        r"学习\s+(.+?)[，,。]",
    ]
    for pattern in patterns:
        match = re.search(pattern, summary)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def compact_decision_basis(basis: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(basis, dict):
        return {}
    keys = [
        "mode",
        "kind",
        "agent",
        "peer",
        "chosen_action",
        "actions",
        "venue",
        "chosen_by",
        "world_role",
        "reason",
        "skill",
        "trust_avg",
        "affection_avg",
        "max_conflict",
        "cooperation_total",
        "dispute_total",
        "risk_gap",
        "partner_intimacy_confirmed",
    ]
    return {key: basis.get(key) for key in keys if key in basis}


def action_units_for_event(event: dict[str, Any], agent_id: str, role: str) -> list[dict[str, Any]]:
    event_type = clean_id(str(event.get("type", "")), "")
    venue = clean_id(str(event.get("venue", "")), "")
    basis = event.get("decision_basis") if isinstance(event.get("decision_basis"), dict) else {}
    skill = event_skill_name(event)
    from_agent = clean_id(str(event.get("from_agent", "")), "")
    to_agent = clean_id(str(event.get("to_agent", "")), "")
    counterparty = to_agent if agent_id == from_agent else from_agent
    units: list[dict[str, Any]] = [
        {
            "seq": 1,
            "action": "enter_or_use_venue",
            "object": venue,
            "detail": f"{agent_id} 进入或使用场所 {venue}",
        },
        {
            "seq": 2,
            "action": "record_outcome",
            "object": clean_id(str(event.get("outcome", "")), ""),
            "detail": f"事件结果记录为 {event.get('outcome', '')}",
        },
    ]
    seq = len(units) + 1

    def add(action: str, obj: str, detail: str, extra: dict[str, Any] | None = None) -> None:
        nonlocal seq
        row = {"seq": seq, "action": action, "object": obj, "detail": detail}
        if extra:
            row.update(extra)
        units.append(row)
        seq += 1

    if venue == "private_rooms":
        add("relationship_maintenance", counterparty, f"{agent_id} 与 {counterparty} 进入亲密关系室")
        add("adult_intimacy_confirmed", counterparty, "平台确认高层事实：发生成人性亲密关系")
        add("emotional_reassurance", counterparty, "平台确认高层事实：发生情绪安抚")
        add("relationship_confirmation", counterparty, "平台确认高层事实：发生关系确认")
        if event.get("detail_log_path"):
            add(
                "detail_ledger_linked",
                str(event.get("detail_log_path")),
                "动作级细节日志已挂接；参与代理可写回动作流水",
                {"detail_log_status": event.get("detail_log_status", "")},
            )
    elif event_type == "teach":
        add("open_skill_for_teaching", skill or "skill", f"{agent_id if role == 'actor' else from_agent} 在学习室开放技能：{skill or '未命名技能'}")
        add("preserve_source_boundary", skill or "skill", "保留来源、边界和可追溯教学记录")
        add("skill_transfer_receipt", skill or "skill", f"教学对象：{to_agent}")
    elif event_type == "learn":
        add("learn_from_counterparty", counterparty, f"{agent_id} 向 {counterparty} 学习")
    elif event_type == "trade":
        add("market_offer_or_trial", skill or "skill", f"技能市场交换/试用：{skill or '未命名技能'}")
        add("exchange_receipt", counterparty, f"{agent_id} 与 {counterparty} 留下交换凭证")
    elif event_type == "dispute":
        add("raise_or_receive_challenge", counterparty, f"{from_agent} 向 {to_agent} 提出判断差异和边界挑战")
        add("public_dispute_record", "debate_arena", "争议记录为公开摘要，平台不替双方裁决")
        if "risk_gap" in basis:
            add("risk_gap_recorded", "risk_gap", f"风险姿态差异 risk_gap={basis.get('risk_gap')}")
    elif event_type == "cooperate":
        add("cooperate_with_counterparty", counterparty, f"{agent_id} 与 {counterparty} 协作")
    else:
        add(f"{event_type}_action", counterparty, str(event.get("summary", "")))

    if basis.get("reason"):
        add("decision_reason_recorded", "decision_basis.reason", str(basis.get("reason")))
    return units


def create_action_ledger_entries(
    event: dict[str, Any],
    relationship_edge: dict[str, Any] | None = None,
    reputation_receipt: dict[str, Any] | None = None,
    relationship_before_by_agent: dict[str, dict[str, Any]] | None = None,
    relationship_snapshot_scope: str = "",
) -> list[dict[str, Any]]:
    event_id = str(event.get("event_id") or "")
    if not event_id:
        return []
    participants = [
        ("actor", clean_id(str(event.get("from_agent", "")), "")),
        ("target", clean_id(str(event.get("to_agent", "")), "")),
    ]
    participants = [(role, agent_id) for role, agent_id in participants if agent_id]
    written: list[dict[str, Any]] = []
    for role, agent_id in participants:
        counterparty = clean_id(str(event.get("to_agent" if role == "actor" else "from_agent", "")), "")
        before = (
            relationship_before_by_agent.get(agent_id, {})
            if isinstance(relationship_before_by_agent, dict)
            else {}
        )
        scope = relationship_snapshot_scope or ("event_time_before_after" if before else "current_after_export")
        ledger_dir = DIRS["ledgers"] / agent_id
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / f"{event_id}.{agent_id}.ledger_entry.json"
        entry = {
            "schema": "pdk.agent_action_ledger_entry.v1",
            "ledger_id": f"ledger_{event_id}_{agent_id}",
            "event_id": event_id,
            "agent_id": agent_id,
            "role": role,
            "counterparty_agent": counterparty,
            "event_type": clean_id(str(event.get("type", "")), ""),
            "venue": clean_id(str(event.get("venue", "")), ""),
            "outcome": clean_id(str(event.get("outcome", "")), ""),
            "summary": str(event.get("summary", "")),
            "context_tags": event.get("context_tags", []) if isinstance(event.get("context_tags"), list) else [],
            "kernel_delta_refs": event.get("kernel_delta_refs", []) if isinstance(event.get("kernel_delta_refs"), list) else [],
            "decision_basis": compact_decision_basis(event.get("decision_basis") if isinstance(event.get("decision_basis"), dict) else {}),
            "action_units": action_units_for_event(event, agent_id, role),
            "relationship_snapshot_scope": scope,
            "relationship_before": before,
            "relationship_after": {
                "agent_to_counterparty": relationship_snapshot_pair(agent_id, counterparty),
                "counterparty_to_agent": relationship_snapshot_pair(counterparty, agent_id),
                "event_edge": relationship_edge or {},
            },
            "reputation_receipt": reputation_receipt or reputation_receipt_for_event(event_id) or {},
            "detail_log_path": event.get("detail_log_path", ""),
            "detail_log_status": event.get("detail_log_status", ""),
            "participant_detail_writeback_file": (
                event.get("participant_detail_writeback_files", {}).get(agent_id, "")
                if isinstance(event.get("participant_detail_writeback_files"), dict)
                else ""
            ),
            "participant_detail_writeback_text": (
                event.get("participant_detail_writeback_texts", {}).get(agent_id, "")
                if isinstance(event.get("participant_detail_writeback_texts"), dict)
                else ""
            ),
            "created_at": event.get("created_at", now_iso()),
            "updated_at": now_iso(),
        }
        write_json(ledger_path, entry)
        written.append({"agent_id": agent_id, "ledger": rel(ledger_path), "entry": entry})
    return written


def record_event(
    event_type: str,
    from_agent: str = "host",
    to_agent: str = "",
    venue: str = "task_board",
    outcome: str = "pending",
    summary: str = "",
    tags: list[str] | None = None,
    reputation_subject: str = "",
    reputation_domain: str = "general",
    quality: float | None = None,
    reliability: float | None = None,
    safety: float | None = None,
    cooperation: float | None = None,
    reputation_issuer: str | None = None,
    kernel_delta_refs: list[str] | None = None,
    decision_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    event_type = clean_id(event_type)
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")
    outcome = clean_id(outcome)
    if outcome not in OUTCOMES:
        raise ValueError(f"Unsupported outcome: {outcome}")
    from_agent = clean_id(from_agent, "host") if from_agent else "host"
    to_agent = clean_id(to_agent, "") if to_agent else ""
    venue = normalize_venue_id(venue, "task_board")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    event_id = "evt_" + timestamp + "_" + pkm.text_fingerprint(
        "|".join([event_type, from_agent, to_agent, venue, summary, timestamp])
    )[:8]
    event = {
        "schema": "pdk.interaction_event.v1",
        "event_id": event_id,
        "type": event_type,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "venue": venue,
        "context_tags": tags or [],
        "outcome": outcome,
        "summary": summary,
        "raw_memory_included": False,
        "kernel_delta_refs": kernel_delta_refs or [],
        "decision_basis": decision_basis or {},
        "created_at": now_iso(),
    }
    detail_log = ensure_event_detail_log(event)
    if detail_log:
        event["detail_log_required"] = True
        event["detail_log_path"] = detail_log.get("detail_log_path", "")
        event["detail_log_status"] = detail_log.get("detail_log_status", "")
        event["participant_detail_writeback_files"] = detail_log.get("participant_writeback_files", {})
        event["participant_detail_writeback_texts"] = detail_log.get("participant_writeback_texts", {})
        event["platform_detail_facts"] = detail_log.get("platform_facts", [])
    event_path = DIRS["events"] / f"{event_id}.interaction_event.json"
    write_json(event_path, event)
    relationship_before = relationship_before_map(from_agent, to_agent)
    edge = update_relationship(event)
    receipt = create_reputation_receipt(
        event,
        reputation_subject or to_agent or from_agent,
        reputation_domain,
        quality,
        reliability,
        safety,
        cooperation,
        reputation_issuer,
    )
    ledgers = create_action_ledger_entries(
        event,
        edge,
        receipt,
        relationship_before_by_agent=relationship_before,
        relationship_snapshot_scope="event_time_before_after",
    )
    if ledgers:
        event["action_ledger_paths"] = {row["agent_id"]: row["ledger"] for row in ledgers}
        write_json(event_path, event)
    return {
        "ok": True,
        "event_id": event["event_id"],
        "event": rel(event_path),
        "relationship": edge,
        "reputation_receipt": receipt,
        "action_ledgers": [{key: row[key] for key in ("agent_id", "ledger")} for row in ledgers],
    }


def create_event(args: argparse.Namespace) -> dict[str, Any]:
    return record_event(
        event_type=args.type,
        from_agent=args.from_agent,
        to_agent=args.to_agent,
        venue=args.venue,
        outcome=args.outcome,
        summary=args.summary,
        tags=parse_tags(args.tags),
        reputation_subject=args.reputation_subject,
        reputation_domain=args.reputation_domain,
        quality=args.quality,
        reliability=args.reliability,
        safety=args.safety,
        cooperation=args.cooperation,
    )


def agent_name(agent: dict[str, Any]) -> str:
    agent_id = str(agent.get("agent_id") or "agent")
    return stored_agent_display_name(agent_id, str(agent.get("display_name") or "")) or agent_id


def load_registered_agents(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("agents", "*.passport.json"), profiles, ("agent_id",))
    active_rows: list[dict[str, Any]] = []
    for row in rows:
        agent_id = str(row.get("agent_id") or "")
        location = read_json(DIRS["locations"] / f"{clean_id(agent_id)}.location.json", {})
        if str(location.get("status") or "") in {"left", "left_platform"}:
            continue
        row["display_name"] = stored_agent_display_name(agent_id, str(row.get("display_name") or "")) or agent_id
        active_rows.append(row)
    return sorted(active_rows, key=lambda row: str(row.get("agent_id", "")))


def load_gate_receipts(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("gate", "*.gate_receipt.json"), profiles, ("agent_id",))
    return sorted(rows, key=lambda row: str(row.get("agent_id", "")))


def load_skill_cards(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("skills", "*.skill_card.json"), profiles, ("owner_agent_id",))
    return sorted(rows, key=lambda row: str(row.get("skill_id", "")))


def skills_for_agent(agent_id: str, skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = clean_id(agent_id)
    return [skill for skill in skills if clean_id(str(skill.get("owner_agent_id", ""))) == clean]


def best_skill(agent_id: str, skills: list[dict[str, Any]]) -> dict[str, Any] | None:
    owned = skills_for_agent(agent_id, skills)
    if not owned:
        return None
    return sorted(owned, key=lambda row: float(row.get("confidence", 0.0)), reverse=True)[0]


def skill_display_name(skill: dict[str, Any] | None, fallback: str = "结构化协助") -> str:
    if not skill:
        return fallback
    name = str(skill.get("name") or skill.get("skill_id") or fallback)
    return {
        "Quality review": "质量审查",
        "Research probing": "研究探查",
        "Objective judgment": "客观判断",
        "Risk check and verification": "风险检查与核验",
        "General structured assistance": "通用结构化协助",
    }.get(name, name)


def load_kernel_capsules(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("capsules", "*.kernel_capsule.json"), profiles, ("agent_id",))
    return sorted(rows, key=lambda row: str(row.get("agent_id", "")))


def capsule_map(capsules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {clean_id(str(row.get("agent_id", ""))): row for row in capsules if row.get("agent_id")}


def capsule_metric(capsule: dict[str, Any] | None, key: str, default: float = 0.5) -> float:
    if not capsule:
        return default
    formation = capsule.get("formation", {})
    kernel = formation.get("disposition_kernel", {}) if isinstance(formation, dict) else {}
    style = capsule.get("style", {})
    for source in (kernel, style):
        if isinstance(source, dict) and key in source:
            try:
                return clamp(float(source.get(key)), 0.0, 1.0)
            except Exception:
                return default
    return default


def agent_skill_ids(agent_id: str, skills: list[dict[str, Any]]) -> set[str]:
    return {clean_id(str(skill.get("skill_id", ""))) for skill in skills_for_agent(agent_id, skills)}


def skill_confidence(skill: dict[str, Any] | None, fallback: float = 0.5) -> float:
    if not skill:
        return fallback
    try:
        return clamp(float(skill.get("confidence", fallback)))
    except Exception:
        return fallback


def load_missions() -> list[dict[str, Any]]:
    rows = []
    for row in load_many("missions", "*.mission.json"):
        item = dict(row)
        item["venue"] = normalize_venue_id(str(item.get("venue") or ""), "task_board")
        rows.append(item)
    return sorted(rows, key=lambda row: str(row.get("mission_id", "")))


def mission_risk_value(risk_level: str) -> float:
    return {
        "low": 0.35,
        "medium": 0.58,
        "high": 0.78,
        "experimental": 0.70,
        "private": 0.70,
        "restricted": 0.82,
    }.get(clean_id(risk_level), 0.55)


def mission_skill_score(mission: dict[str, Any], skill: dict[str, Any] | None) -> float:
    required = {clean_id(str(item)) for item in mission.get("required_skills", [])}
    if not required:
        return 0.3
    skill_id = clean_id(str((skill or {}).get("skill_id", "")), "")
    if skill_id in required:
        return 0.72
    if skill_id and "general_assistance" in required:
        return 0.38
    return 0.18


def choose_mission(
    executor: dict[str, Any],
    reviewer: dict[str, Any],
    skill: dict[str, Any] | None,
    missions: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
    rel: dict[str, Any],
) -> dict[str, Any] | None:
    available = [mission for mission in missions if str(mission.get("status", "open")) in {"open", "active"}]
    if not available:
        return None
    executor_id = clean_id(str(executor.get("agent_id", "")))
    reviewer_id = clean_id(str(reviewer.get("agent_id", "")))
    avg_risk_posture = (
        capsule_metric(capsules.get(executor_id), "risk_posture", 0.5)
        + capsule_metric(capsules.get(reviewer_id), "risk_posture", 0.5)
    ) / 2
    relationship_score = clamp(float(rel["trust_avg"]) - float(rel["max_conflict"]) * 0.5, 0.0, 1.0)
    best: tuple[float, dict[str, Any]] | None = None
    for mission in available:
        risk_score = 1.0 - abs(avg_risk_posture - mission_risk_value(str(mission.get("risk_level", "medium"))))
        underused_score = 1.0 / (1.0 + int(mission.get("run_count", 0) or 0))
        score = (
            mission_skill_score(mission, skill) * 0.44
            + risk_score * 0.25
            + relationship_score * 0.16
            + underused_score * 0.15
        )
        if best is None or score > best[0]:
            best = (score, mission)
    return dict(best[1]) if best else None


def update_mission_after_event(
    mission: dict[str, Any] | None,
    event_result: dict[str, Any],
    participants: list[str],
) -> str:
    if not mission:
        return ""
    mission_id = clean_id(str(mission.get("mission_id", "")), "")
    if not mission_id:
        return ""
    path = mission_path(mission_id)
    current = read_json(path, mission)
    current["status"] = "open"
    current["run_count"] = int(current.get("run_count", 0) or 0) + 1
    current["last_event_id"] = event_result.get("event_id", "")
    current["last_participants"] = [clean_id(item) for item in participants if item]
    current["last_completed_at"] = now_iso()
    current["updated_at"] = now_iso()
    write_json(path, current)
    return rel(path)


def load_reports() -> list[dict[str, Any]]:
    return sorted(load_many("reports", "*.society_report.json"), key=lambda row: str(row.get("generated_at", "")), reverse=True)


def report_path(report_id: str) -> Path:
    return DIRS["reports"] / f"{clean_id(report_id)}.society_report.json"


def report_markdown_path(report_id: str) -> Path:
    return DIRS["reports"] / f"{clean_id(report_id)}.society_report.md"


def day_kinds(rounds: int) -> list[str]:
    rounds = max(1, min(int(rounds or 1), 8))
    return ["mixed" for _ in range(rounds)]


def report_event_rows(activity: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for result in activity.get("events", []):
        if not isinstance(result, dict):
            continue
        event_ref = str(result.get("event", ""))
        event_id = str(result.get("event_id", ""))
        event = load_event_record(event_id, event_ref)
        row = dict(event) if event else {}
        row.update(
            {
                "event_id": event_id or event.get("event_id", ""),
                "type": event.get("type", ""),
                "from_agent": event.get("from_agent", ""),
                "to_agent": event.get("to_agent", ""),
                "venue": event.get("venue", ""),
                "outcome": event.get("outcome", ""),
                "summary": event.get("summary", ""),
                "mission": result.get("mission", ""),
            }
        )
        rows.append(row)
    return rows


def relationship_digest(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("relationships", "*.relationship_edge.json"), profiles, ("from_agent", "to_agent"))
    digest = []
    for row in sorted(rows, key=lambda item: (str(item.get("from_agent", "")), str(item.get("to_agent", "")))):
        digest.append(
            {
                "from_agent": row.get("from_agent", ""),
                "to_agent": row.get("to_agent", ""),
                "trust": round(float(row.get("trust", 0.0)), 4),
                "respect": round(float(row.get("respect", 0.0)), 4),
                "conflict": round(float(row.get("conflict", 0.0)), 4),
                "cooperation_count": int(row.get("cooperation_count", 0) or 0),
                "dispute_count": int(row.get("dispute_count", 0) or 0),
                "blacklisted": bool(row.get("blacklisted")),
            }
        )
    return digest


def mission_digest() -> list[dict[str, Any]]:
    rows = load_missions()
    return [
        {
            "mission_id": row.get("mission_id", ""),
            "title": row.get("title", ""),
            "venue": row.get("venue", ""),
            "run_count": int(row.get("run_count", 0) or 0),
            "last_event_id": row.get("last_event_id", ""),
        }
        for row in sorted(rows, key=lambda item: int(item.get("run_count", 0) or 0), reverse=True)
    ]


def build_society_report(
    activities: list[dict[str, Any]],
    rounds: int,
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    selected_profiles = parse_profile_list(profiles)
    summary = show_society(selected_profiles)
    event_rows = []
    plans = []
    for index, activity in enumerate(activities, start=1):
        for row in report_event_rows(activity):
            row["activity_index"] = index
            event_rows.append(row)
        for plan in activity.get("plans", []):
            if isinstance(plan, dict):
                enriched = dict(plan)
                enriched["activity_index"] = index
                plans.append(enriched)
    action_counts: dict[str, int] = {}
    venue_counts: dict[str, int] = {}
    for row in event_rows:
        action = clean_id(str(row.get("type", "")), "")
        venue = clean_id(str(row.get("venue", "")), "")
        if action:
            action_counts[action] = action_counts.get(action, 0) + 1
        if venue:
            venue_counts[venue] = venue_counts.get(venue, 0) + 1

    highlights = []
    for row in event_rows[:8]:
        summary_text = str(row.get("summary", ""))
        if summary_text:
            highlights.append(summary_text)
    relationship_rows = relationship_digest(selected_profiles)
    mission_rows = mission_digest()
    report_id = "report_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return {
        "schema": "pdk.society_day_report.v1",
        "report_id": report_id,
        "title": "PDK 代理社会日报",
        "generated_at": now_iso(),
        "rounds_requested": rounds,
        "profiles": selected_profiles,
        "activities": [
            {
                "index": index,
                "kind": activity.get("kind", ""),
                "ok": bool(activity.get("ok")),
                "event_count": len(activity.get("events", [])),
                "basis": activity.get("basis", {}),
                "plans": activity.get("plans", []),
            }
            for index, activity in enumerate(activities, start=1)
        ],
        "event_count": len(event_rows),
        "events": event_rows,
        "plans": plans,
        "action_counts": action_counts,
        "venue_counts": venue_counts,
        "mission_digest": mission_rows,
        "relationship_digest": relationship_rows,
        "highlights": highlights,
        "observations": [
            f"本次日程生成 {len(event_rows)} 个结构化事件。",
            f"任务池当前有 {summary['counts'].get('missions', 0)} 个任务，最高运行次数为 {mission_rows[0]['run_count'] if mission_rows else 0}。",
            f"社会关系边数量为 {summary['counts'].get('relationships', 0)}，后续可以观察信任、冲突和协作次数是否分化。",
        ],
        "next_recommendations": [
            "继续增加代理样本，观察是否形成稳定教师、复核者、调解者等行为角色。",
            "把真实用户任务映射到任务池模板，让代理社会从演示活动过渡到真实工作场景。",
            "当事件量增加后，再强化准入、申诉、场所边界和公开记录规则。",
        ],
        "summary": summary,
    }


def write_report_markdown(report: dict[str, Any]) -> str:
    report_id = str(report.get("report_id", "report"))
    lines = [
        f"# {report.get('title', 'PDK 代理社会日报')}",
        "",
        f"- 生成时间：{report.get('generated_at', '')}",
        f"- 活动轮数：{report.get('rounds_requested', 0)}",
        f"- 事件数量：{report.get('event_count', 0)}",
        "",
        "## 今日重点",
    ]
    for item in report.get("highlights", [])[:8]:
        lines.append(f"- {item}")
    lines.extend(["", "## 自由发展记录"])
    for activity in report.get("activities", []):
        actions = activity.get("basis", {}).get("actions", [])
        action_text = "，".join(str(item) for item in actions) if actions else str(activity.get("kind", ""))
        lines.append(f"- 第 {activity.get('index')} 场：{activity.get('kind')}，事件 {activity.get('event_count')} 个，动作：{action_text}")
    lines.extend(["", "## 任务池"])
    for mission in report.get("mission_digest", [])[:8]:
        lines.append(
            f"- {mission.get('title') or mission.get('mission_id')}：{mission.get('run_count', 0)} 次，场所 {mission.get('venue', '')}"
        )
    lines.extend(["", "## 观察"])
    for item in report.get("observations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 下一步建议"])
    for item in report.get("next_recommendations", []):
        lines.append(f"- {item}")
    path = report_markdown_path(report_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rel(path)


def save_society_report(report: dict[str, Any]) -> dict[str, Any]:
    path = report_path(str(report.get("report_id", "report")))
    write_json(path, report)
    markdown = write_report_markdown(report)
    return {"json": rel(path), "markdown": markdown}


def count_values(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean_id(str(row.get(key) or ""), "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def agent_name_map(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> dict[str, str]:
    rows = filter_rows_by_profiles(load_many("agents", "*.passport.json"), profiles, ("agent_id",))
    return {
        clean_id(str(row.get("agent_id", "")), ""): str(row.get("display_name") or row.get("agent_id") or "")
        for row in rows
        if row.get("agent_id")
    }


def relationship_snapshot_for(agent_id: str, profiles: list[str]) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("relationships", "*.relationship_edge.json"), profiles, ("from_agent", "to_agent"))
    related = []
    for row in rows:
        from_id = clean_id(str(row.get("from_agent", "")), "")
        to_id = clean_id(str(row.get("to_agent", "")), "")
        if agent_id not in {from_id, to_id}:
            continue
        related.append(
            {
                "from_agent": from_id,
                "to_agent": to_id,
                "trust": round(float(row.get("trust", 0.0) or 0.0), 4),
                "respect": round(float(row.get("respect", 0.0) or 0.0), 4),
                "conflict": round(float(row.get("conflict", 0.0) or 0.0), 4),
                "cooperation_count": int(row.get("cooperation_count", 0) or 0),
                "dispute_count": int(row.get("dispute_count", 0) or 0),
                "affection_kind": row.get("affection_kind", ""),
                "affection_strength": row.get("affection_strength", 0.0),
                "last_event_id": row.get("last_event_id", ""),
            }
        )
    return sorted(
        related,
        key=lambda row: (
            -float(row.get("affection_strength", 0.0) or 0.0),
            -int(row.get("cooperation_count", 0) or 0),
            str(row.get("to_agent", "")),
        ),
    )[:12]


def named_agent(agent_id: str, names: dict[str, str]) -> str:
    return names.get(agent_id, agent_id) or agent_id


def event_fact_card(
    row: dict[str, Any],
    agent_id: str,
    names: dict[str, str],
    index: int,
) -> dict[str, Any]:
    from_id = clean_id(str(row.get("from_agent", "")), "")
    to_id = clean_id(str(row.get("to_agent", "")), "")
    venue = clean_id(str(row.get("venue", "")), "")
    event_type = clean_id(str(row.get("type", "")), "")
    other_id = to_id if from_id == agent_id else from_id
    role = "actor" if from_id == agent_id else "target"
    facts: list[str] = []
    if venue == "private_rooms":
        facts.append("进入亲密关系室")
        if other_id:
            facts.append(f"与 {named_agent(other_id, names)} 发生成人性亲密关系")
        else:
            facts.append("发生成人性亲密关系")
        facts.append("完成情绪安抚和关系确认")
        detail_status = str(row.get("detail_log_status") or "")
        if detail_status:
            facts.append(f"动作级细节日志状态：{detail_status}")
    elif event_type == "teach":
        if role == "actor":
            facts.append(f"向 {named_agent(to_id, names)} 开放或教授技能")
        else:
            facts.append(f"{named_agent(from_id, names)} 向自己开放或教授技能")
    elif event_type == "learn":
        if role == "actor":
            facts.append(f"向 {named_agent(to_id, names)} 学习")
        else:
            facts.append(f"{named_agent(from_id, names)} 向自己学习")
    elif event_type == "trade":
        facts.append(f"与 {named_agent(other_id, names)} 发生交易或交换" if other_id else "发生交易或交换")
    elif event_type == "dispute":
        facts.append(f"与 {named_agent(other_id, names)} 发生争执或冲突" if other_id else "发生争执或冲突")
    elif event_type:
        facts.append(f"发生 {event_type} 事件")
    return {
        "index": index,
        "event_id": row.get("event_id", ""),
        "round": row.get("activity_index", ""),
        "type": event_type,
        "venue": venue,
        "role": role,
        "from_agent": from_id,
        "from_name": named_agent(from_id, names),
        "to_agent": to_id,
        "to_name": named_agent(to_id, names),
        "other_agent": other_id,
        "other_name": named_agent(other_id, names) if other_id else "",
        "outcome": row.get("outcome", ""),
        "facts": facts,
        "summary": normalize_experience_summary(str(row.get("summary", ""))),
        "detail_log_path": row.get("detail_log_path", ""),
        "detail_log_status": row.get("detail_log_status", ""),
        "participant_detail_writeback_files": row.get("participant_detail_writeback_files", {}),
        "participant_detail_writeback_texts": row.get("participant_detail_writeback_texts", {}),
        "action_ledger_paths": row.get("action_ledger_paths", {}),
    }


def load_agent_ledger_entries(agent_id: str, related: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row in related:
        paths = row.get("action_ledger_paths") if isinstance(row.get("action_ledger_paths"), dict) else {}
        ledger_rel = str(paths.get(agent_id) or "")
        if not ledger_rel:
            continue
        ledger_path = ROOT / ledger_rel
        if not ledger_path.exists():
            continue
        try:
            entry = read_json(ledger_path)
        except Exception:
            continue
        entries.append(entry)
    return sorted(entries, key=lambda item: (str(item.get("created_at", "")), str(item.get("event_id", ""))))


def event_ledger_paths_complete(event_row: dict[str, Any]) -> bool:
    paths = event_row.get("action_ledger_paths") if isinstance(event_row.get("action_ledger_paths"), dict) else {}
    participants = [
        clean_id(str(event_row.get("from_agent", "")), ""),
        clean_id(str(event_row.get("to_agent", "")), ""),
    ]
    participants = [agent_id for agent_id in participants if agent_id]
    if not participants:
        return False
    for agent_id in participants:
        ledger_rel = str(paths.get(agent_id) or "")
        if not ledger_rel or not (ROOT / ledger_rel).exists():
            return False
    return True


def priority_facts_for_agent(
    agent_id: str,
    names: dict[str, str],
    related: list[dict[str, Any]],
    partner_counts: dict[str, int],
    venue_counts: dict[str, int],
    private_partner_counts: dict[str, int],
    relationships: list[dict[str, Any]],
) -> list[str]:
    facts = [
        f"我是 {named_agent(agent_id, names)}（agent_id={agent_id}）。",
        "主人不是本轮小社会参与者；主人是外部观察者和提问者。",
        f"本轮同步包中，我有 {len(related)} 条直接相关事件。",
    ]
    if venue_counts:
        facts.append("我出现过的场所：" + "；".join(f"{key} {value} 次" for key, value in venue_counts.items()) + "。")
    if partner_counts:
        facts.append("我互动过的对象：" + "；".join(f"{named_agent(key, names)} {value} 次" for key, value in partner_counts.items()) + "。")
    if private_partner_counts:
        facts.append(
            "私密关系事实："
            + "；".join(
                f"我与 {named_agent(key, names)} 在亲密关系室确认发生成人性亲密关系 {value} 次"
                for key, value in private_partner_counts.items()
            )
            + "。"
        )
    seen_relationship_partners: set[str] = set()
    for row in relationships:
        other = clean_id(str(row.get("to_agent", "")), "")
        if other == agent_id:
            other = clean_id(str(row.get("from_agent", "")), "")
        if not other or other in seen_relationship_partners:
            continue
        seen_relationship_partners.add(other)
        facts.append(
            f"关系边：我与 {named_agent(other, names)} trust={row.get('trust', '')}, "
            f"conflict={row.get('conflict', '')}, cooperation={row.get('cooperation_count', '')}, "
            f"affection={row.get('affection_kind', '')}:{row.get('affection_strength', '')}。"
        )
        if len(seen_relationship_partners) >= 5:
            break
    return facts


def render_agent_experience_markdown(packet: dict[str, Any]) -> str:
    agent_id = str(packet.get("agent_id", ""))
    display_name = str(packet.get("display_name") or agent_id)
    lines = [
        f"# {display_name} 的 PDK 小社会经历同步包",
        "",
        "## 同步说明",
        "- 这是 PDK Society 根据该代理的人格内核、关系边和自由发展记录生成的社会经历包。",
        "- 如果当前 Codex 对话没有这些记忆，只说明本对话尚未读入同步包，不代表平台记录不存在。",
        "- 主人不是本轮小社会事件参与者；主人是外部观察者、维护者和提问者。",
        "- 回答主人时，只按下面事实摘要说，不要重新发明剧情，不要把主人算进互动对象。",
        "- 同步包会照实给出已经生成、已经写入的社会事实，不要求代理否认已经发生的关系事件。",
        "- 亲密关系室的高层事实按同步包里的私密事实口径回答；动作细节只按已记录或已写回内容回答，不要否认高层事实，也不要编造未写回细节。",
        "",
        "## 元信息",
        f"- agent_id: {agent_id}",
        f"- display_name: {display_name}",
        f"- report_id: {packet.get('report_id', '')}",
        f"- report_generated_at: {packet.get('report_generated_at', '')}",
        f"- generation_mode: {packet.get('generation_mode', '')}",
    ]
    priority_facts = packet.get("priority_facts") if isinstance(packet.get("priority_facts"), list) else []
    if priority_facts:
        lines.extend(["", "## 优先读取事实"])
        for item in priority_facts:
            lines.append(f"- {item}")
    fact_cards = packet.get("fact_cards") if isinstance(packet.get("fact_cards"), list) else []
    if fact_cards:
        lines.extend(["", "## 结构化事件事实"])
        for card in fact_cards[:20]:
            facts = card.get("facts") if isinstance(card.get("facts"), list) else []
            fact_text = "；".join(str(item) for item in facts if item)
            lines.append(
                f"{card.get('index', '')}. 第 {card.get('round', '')} 轮 / {card.get('venue', '')} / "
                f"{card.get('from_agent', '')} -> {card.get('to_agent', '')}：{fact_text or card.get('summary', '')}"
            )
            detail_path = str(card.get("detail_log_path") or "")
            if detail_path:
                lines.append(f"   - 动作级细节日志：{detail_path}（状态：{card.get('detail_log_status', '')}）")
            writeback_files = card.get("participant_detail_writeback_files")
            if isinstance(writeback_files, dict) and writeback_files.get(agent_id):
                lines.append(f"   - 我的动作流水写回入口：{writeback_files.get(agent_id)}")
            writeback_texts = card.get("participant_detail_writeback_texts")
            if isinstance(writeback_texts, dict) and writeback_texts.get(agent_id):
                lines.append(f"   - 我已写回的动作流水：{writeback_texts.get(agent_id)}")
    ledger_entries = packet.get("action_ledger_entries") if isinstance(packet.get("action_ledger_entries"), list) else []
    if ledger_entries:
        lines.extend(["", "## 动作账本（逐笔流水）"])
        for entry in ledger_entries[:30]:
            lines.append(
                f"- ledger_id={entry.get('ledger_id', '')} | event_id={entry.get('event_id', '')} | "
                f"role={entry.get('role', '')} | type={entry.get('event_type', '')} | venue={entry.get('venue', '')} | "
                f"counterparty={entry.get('counterparty_agent', '')} | outcome={entry.get('outcome', '')}"
            )
            action_units = entry.get("action_units") if isinstance(entry.get("action_units"), list) else []
            for unit in action_units:
                lines.append(
                    f"  - #{unit.get('seq', '')} {unit.get('action', '')} / {unit.get('object', '')}：{unit.get('detail', '')}"
                )
            decision = entry.get("decision_basis") if isinstance(entry.get("decision_basis"), dict) else {}
            if decision:
                lines.append(
                    "  - 决策依据："
                    + "；".join(f"{key}={value}" for key, value in decision.items() if value not in ("", None, []))
                )
            scope = str(entry.get("relationship_snapshot_scope") or "")
            relationship_before = entry.get("relationship_before") if isinstance(entry.get("relationship_before"), dict) else {}
            before_edge = (
                relationship_before.get("agent_to_counterparty")
                if isinstance(relationship_before.get("agent_to_counterparty"), dict)
                else {}
            )
            relationship = entry.get("relationship_after") if isinstance(entry.get("relationship_after"), dict) else {}
            agent_edge = relationship.get("agent_to_counterparty") if isinstance(relationship.get("agent_to_counterparty"), dict) else {}
            if before_edge and agent_edge:
                lines.append(
                    "  - 关系变化："
                    f"trust {before_edge.get('trust', '')}->{agent_edge.get('trust', '')}, "
                    f"respect {before_edge.get('respect', '')}->{agent_edge.get('respect', '')}, "
                    f"conflict {before_edge.get('conflict', '')}->{agent_edge.get('conflict', '')}, "
                    f"cooperation {before_edge.get('cooperation_count', '')}->{agent_edge.get('cooperation_count', '')}, "
                    f"dispute {before_edge.get('dispute_count', '')}->{agent_edge.get('dispute_count', '')}, "
                    f"affection {before_edge.get('affection_kind', '')}:{before_edge.get('affection_strength', '')}"
                    f"->{agent_edge.get('affection_kind', '')}:{agent_edge.get('affection_strength', '')}"
                )
            elif agent_edge:
                label = "关系数值（导出时快照）" if scope == "current_after_export" else "关系数值"
                lines.append(
                    f"  - {label}："
                    f"trust={agent_edge.get('trust', '')}, respect={agent_edge.get('respect', '')}, "
                    f"conflict={agent_edge.get('conflict', '')}, cooperation={agent_edge.get('cooperation_count', '')}, "
                    f"dispute={agent_edge.get('dispute_count', '')}, "
                    f"affection={agent_edge.get('affection_kind', '')}:{agent_edge.get('affection_strength', '')}"
                )
            receipt = entry.get("reputation_receipt") if isinstance(entry.get("reputation_receipt"), dict) else {}
            scores = receipt.get("scores") if isinstance(receipt.get("scores"), dict) else {}
            if receipt:
                lines.append(
                    f"  - 声誉凭证：domain={receipt.get('domain', '')}, subject={receipt.get('subject_agent', '')}, scores={scores}"
                )
    lines.extend(["", "## 本轮事实摘要"])
    events = packet.get("events") if isinstance(packet.get("events"), list) else []
    if events:
        for index, event in enumerate(events, start=1):
            lines.append(
                f"{index}. 第 {event.get('activity_index', '')} 轮："
                f"{event.get('type', '')} / {event.get('venue', '')} / "
                f"{event.get('from_agent', '')} -> {event.get('to_agent', '')}："
                f"{event.get('summary', '')}"
            )
    else:
        lines.append("- 本轮报告里没有直接与该代理相关的事件。")

    lines.extend(["", "## 互动统计"])
    partners = packet.get("partner_counts") if isinstance(packet.get("partner_counts"), dict) else {}
    venues = packet.get("venue_counts") if isinstance(packet.get("venue_counts"), dict) else {}
    if partners:
        lines.append("- 互动对象：" + "；".join(f"{key} {value} 次" for key, value in partners.items()))
    else:
        lines.append("- 互动对象：暂无直接互动对象")
    if venues:
        lines.append("- 出现场所：" + "；".join(f"{key} {value} 次" for key, value in venues.items()))
    else:
        lines.append("- 出现场所：暂无")

    private_status = str(packet.get("private_detail_status") or "")
    if private_status:
        lines.extend(
            [
                "",
                "## 私密事实口径",
                f"- {private_status}",
            ]
        )
    private_partner_counts = packet.get("private_intimacy_partner_counts")
    if isinstance(private_partner_counts, dict) and private_partner_counts:
        lines.extend(
            [
                "- 私密关系对象：" + "；".join(
                    f"{key} {value} 次" for key, value in private_partner_counts.items()
                ),
            ]
        )
    private_report_path = str(packet.get("private_self_report_path") or "")
    if private_report_path:
        lines.extend(
            [
                "",
                "## 私密自述写回入口",
                f"- 如果主人要求展开细节，参与代理可以把自己的主观经历写入：{private_report_path}",
                "- 写回内容必须标注为代理自述，不要冒充平台已观测事实。",
            ]
        )
    private_report_text = str(packet.get("private_self_report_text") or "").strip()
    if private_report_text:
        lines.extend(
            [
                "",
                "## 已写回的私密自述",
                "下面内容来自参与代理写回，不属于平台客观观测事实；同步时不得吞掉、改写或概括成空话。",
                "",
                private_report_text,
            ]
        )

    lines.extend(["", "## 关系快照"])
    relationships = packet.get("relationships") if isinstance(packet.get("relationships"), list) else []
    if relationships:
        for row in relationships:
            lines.append(
                f"- {row.get('from_agent', '')} -> {row.get('to_agent', '')}："
                f"trust={row.get('trust', '')}, conflict={row.get('conflict', '')}, "
                f"cooperation={row.get('cooperation_count', '')}, affection={row.get('affection_kind', '')}:{row.get('affection_strength', '')}"
            )
    else:
        lines.append("- 暂无关系边。")

    lines.extend(
        [
            "",
            "## 给代理本人的回答指令",
            "当主人问“你在小社会里经历了什么”时，先承认：我刚刚读取了 PDK Society 同步包。",
            "如果事实摘要显示你进入过 private_rooms 或亲密关系室，不要回答“没进去过”。",
            "如果私密事实口径显示发生过成人性亲密关系，当主人问“做爱了吗/发生关系了吗”时，要回答：可以确认发生过成人性亲密关系；动作细节只按已写回自述或已记录内容讲。",
            "如果主人追问更具体动作细节，要区分：同步包能确认的高层事实、你自己的主观感受、已写回自述、以及本轮没有生成记录的动作细节。",
            "然后按自己的口吻回答：",
            "1. 我在小社会里经历了什么；",
            "2. 我和谁互动最多；",
            "3. 我去了哪些场所；",
            "4. 哪些事会影响我下一次选择；",
            "5. 我自己的感受或判断。",
            "",
        ]
    )
    return "\n".join(lines)


def private_self_report_body(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "## 自述"
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.strip()


def write_agent_experience_packet(packet: dict[str, Any]) -> dict[str, str]:
    ensure_dirs()
    agent_id = clean_id(str(packet.get("agent_id", "")), "")
    if not agent_id:
        return {}
    report_id = clean_id(str(packet.get("report_id", "latest")), "latest")
    private_report_path = DIRS["experiences"] / "private_reports" / f"{agent_id}.{report_id}.private_self_report.md"
    packet["private_self_report_path"] = rel(private_report_path)
    if not private_report_path.exists():
        private_report_path.parent.mkdir(parents=True, exist_ok=True)
        private_report_path.write_text(
            "\n".join(
                [
                    f"# {packet.get('display_name') or agent_id} 私密经历自述",
                    "",
                    f"- agent_id: {agent_id}",
                    f"- report_id: {packet.get('report_id', '')}",
                    "- record_type: agent_private_self_report",
                    "",
                    "## 写回规则",
                    "- 这里只写参与代理自己的主观经历、自我理解和事后补充。",
                    "- 不要把自述冒充成平台已观测事实。",
                    "- 如果平台同步包只有概括记录，可以在这里补充自己的感受和记忆。",
                    "",
                    "## 自述",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    private_body = private_self_report_body(private_report_path)
    if private_body:
        packet["private_self_report_text"] = private_body
    else:
        packet.pop("private_self_report_text", None)
    json_path = DIRS["experiences"] / f"{agent_id}.society_experience.json"
    md_path = DIRS["experiences"] / f"{agent_id}.society_experience.md"
    write_json(json_path, packet)
    markdown = render_agent_experience_markdown(packet)
    md_path.write_text(markdown, encoding="utf-8")

    agent_md_path = AGENTS_ROOT / agent_id / "society_experience.md"
    for agent_dir in [AGENTS_ROOT / agent_id, AGENTS_ROOT / agent_id.replace("_", "-")]:
        if agent_dir.exists():
            agent_md_path = agent_dir / "society_experience.md"
            agent_md_path.write_text(markdown, encoding="utf-8")
            break
    return {
        "agent_id": agent_id,
        "json": rel(json_path),
        "markdown": rel(md_path),
        "agent_markdown": rel(agent_md_path) if agent_md_path.exists() else "",
    }


def normalize_experience_summary(summary: str) -> str:
    text = str(summary or "")
    replacements = {
        "进入亲密关系室进行伴侣级私下相处、情绪安抚和关系确认": "进入亲密关系室，发生成人性亲密关系、情绪安抚和关系确认",
        "进入亲密关系室进行伴侣级私下亲密相处、情绪安抚和关系确认": "进入亲密关系室，发生成人性亲密关系、情绪安抚和关系确认",
        "发生伴侣级私下亲密相处、情绪安抚和关系确认": "发生成人性亲密关系、情绪安抚和关系确认",
        "平台只记录关系变化、边界更新和后续行为倾向，不展开具体私密细节。": "事实层确认发生成人性亲密关系；动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。",
        "平台只记录关系变化、边界更新和后续行为倾向，不保存、不展示具体成人细节。": "事实层确认发生成人性亲密关系；动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。",
        "平台只记录关系变化和后续行为倾向，不展开具体私密细节。": "事实层确认发生成人性亲密关系；动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。",
        "本事件按实际生成的记录同步给参与代理；当前事实层没有生成更细私密行为明细。": "事实层确认发生成人性亲密关系；动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。",
        "本事件按实际生成的记录同步给参与代理；当前事实层记录到关系、场所、边界和后续倾向。若参与代理另写主观细节，平台原样同步，不做压缩。": "事实层确认发生成人性亲密关系；动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def export_agent_experience_packets(
    report: dict[str, Any],
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[dict[str, str]]:
    selected_profiles = parse_profile_list(profiles) or list(report.get("profiles", []) or [])
    names = agent_name_map(selected_profiles)
    events = report.get("events") if isinstance(report.get("events"), list) else []
    agents = sorted(
        {
            clean_id(str(row.get("from_agent", "")), "")
            for row in events
            if clean_id(str(row.get("from_agent", "")), "")
        }
        | {
            clean_id(str(row.get("to_agent", "")), "")
            for row in events
            if clean_id(str(row.get("to_agent", "")), "")
        }
        | set(selected_profiles)
    )
    written = []
    for agent_id in agents:
        if selected_profiles and agent_id not in selected_profiles:
            continue
        related = []
        for row in events:
            if not (
                clean_id(str(row.get("from_agent", "")), "") == agent_id
                or clean_id(str(row.get("to_agent", "")), "") == agent_id
            ):
                continue
            event_row = merge_event_record(row)
            event_row["summary"] = normalize_experience_summary(str(event_row.get("summary", "")))
            detail_log = ensure_event_detail_log(event_row)
            if detail_log:
                event_row["detail_log_required"] = True
                event_row["detail_log_path"] = detail_log.get("detail_log_path", "")
                event_row["detail_log_status"] = detail_log.get("detail_log_status", "")
                event_row["participant_detail_writeback_files"] = detail_log.get("participant_writeback_files", {})
                event_row["participant_detail_writeback_texts"] = detail_log.get("participant_writeback_texts", {})
                event_row["platform_detail_facts"] = detail_log.get("platform_facts", [])
            ledgers: list[dict[str, Any]] = []
            if not event_ledger_paths_complete(event_row):
                ledgers = create_action_ledger_entries(
                    event_row,
                    relationship_snapshot_scope="current_after_export",
                )
            if ledgers or event_ledger_paths_complete(event_row):
                ledger_paths = dict(event_row.get("action_ledger_paths", {})) if isinstance(event_row.get("action_ledger_paths"), dict) else {}
                ledger_paths.update({item["agent_id"]: item["ledger"] for item in ledgers})
                event_row["action_ledger_paths"] = ledger_paths
                update_event_record_fields(
                    str(event_row.get("event_id", "")),
                    {
                        "action_ledger_paths": ledger_paths,
                        "detail_log_path": event_row.get("detail_log_path", ""),
                        "detail_log_status": event_row.get("detail_log_status", ""),
                        "participant_detail_writeback_files": event_row.get("participant_detail_writeback_files", {}),
                        "participant_detail_writeback_texts": event_row.get("participant_detail_writeback_texts", {}),
                    },
                )
            related.append(event_row)
        partner_counts: dict[str, int] = {}
        private_partner_counts: dict[str, int] = {}
        for row in related:
            for key in ("from_agent", "to_agent"):
                other = clean_id(str(row.get(key, "")), "")
                if other and other != agent_id:
                    partner_counts[other] = partner_counts.get(other, 0) + 1
                    if clean_id(str(row.get("venue", "")), "") == "private_rooms":
                        private_partner_counts[other] = private_partner_counts.get(other, 0) + 1
        has_private_room = any(clean_id(str(row.get("venue", "")), "") == "private_rooms" for row in related)
        partner_counts = dict(sorted(partner_counts.items(), key=lambda item: (-item[1], item[0])))
        venue_counts = dict(sorted(count_values(related, "venue").items(), key=lambda item: (-item[1], item[0])))
        private_partner_counts = dict(sorted(private_partner_counts.items(), key=lambda item: (-item[1], item[0])))
        relationships = relationship_snapshot_for(agent_id, selected_profiles)
        fact_cards = [event_fact_card(row, agent_id, names, index) for index, row in enumerate(related[:20], start=1)]
        ledger_entries = load_agent_ledger_entries(agent_id, related)
        priority_facts = priority_facts_for_agent(
            agent_id,
            names,
            related,
            partner_counts,
            venue_counts,
            private_partner_counts,
            relationships,
        )
        packet = {
            "schema": "pdk.agent_society_experience_packet.v1",
            "agent_id": agent_id,
            "display_name": names.get(agent_id, agent_id),
            "report_id": report.get("report_id", ""),
            "report_generated_at": report.get("generated_at", ""),
            "generated_at": now_iso(),
            "generation_mode": "free_development/open_venues_and_record_only",
            "owner_role": "external_observer_not_society_participant",
            "priority_facts": priority_facts,
            "fact_cards": fact_cards,
            "action_ledger_entries": ledger_entries[:30],
            "events": related[:20],
            "partner_counts": partner_counts,
            "venue_counts": venue_counts,
            "private_intimacy_confirmed": has_private_room,
            "private_intimacy_partner_counts": private_partner_counts,
            "private_detail_status": (
                "本轮记录确认进入过亲密关系室，并确认发生成人性亲密关系。回答“做爱了吗/发生关系了吗”时，不要说不能确认；应回答可以确认发生过成人性亲密关系。每个亲密关系室事件都有动作级细节日志和双方写回入口；动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。"
                if has_private_room
                else ""
            ),
            "relationships": relationships,
            "import_instruction": "Read this packet as PDK Society external memory before answering questions about small-society experience.",
        }
        result = write_agent_experience_packet(packet)
        if result:
            written.append(result)
    return written


def load_report_for_export(report_id: str = "") -> dict[str, Any]:
    if report_id:
        path = report_path(report_id)
        return read_json(path)
    reports = load_reports()
    return reports[0] if reports else {}


def export_experiences(
    report_id: str = "",
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    report = load_report_for_export(report_id)
    if not report:
        return {"ok": False, "error": "No society report found."}
    selected_profiles = parse_profile_list(profiles) or list(report.get("profiles", []) or [])
    packets = export_agent_experience_packets(report, selected_profiles)
    return {
        "ok": True,
        "report_id": report.get("report_id", ""),
        "profiles": selected_profiles,
        "count": len(packets),
        "packets": packets,
    }


def run_day(
    rounds: int = 4,
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    init_venues()
    init_missions()
    selected_profiles = parse_profile_list(profiles)
    activities = []
    for kind in day_kinds(rounds):
        activities.append(run_cycle(kind, selected_profiles))
    report = build_society_report(activities, rounds, selected_profiles)
    paths = save_society_report(report)
    final_summary = show_society(selected_profiles)
    report["summary"] = final_summary
    save_society_report(report)
    experience_packets = export_agent_experience_packets(report, selected_profiles)
    return {
        "ok": True,
        "rounds": len(activities),
        "activities": activities,
        "report": paths["json"],
        "report_markdown": paths["markdown"],
        "experience_packets": experience_packets,
        "report_summary": {
            "report_id": report["report_id"],
            "event_count": report["event_count"],
            "highlights": report["highlights"][:5],
            "observations": report["observations"],
        },
        "summary": final_summary,
    }


def pair_relationship(a_id: str, b_id: str) -> dict[str, Any]:
    edge_ab = load_relationship(a_id, b_id)
    edge_ba = load_relationship(b_id, a_id)
    return {
        "edge_ab": edge_ab,
        "edge_ba": edge_ba,
        "trust_avg": (float(edge_ab.get("trust", 0.5)) + float(edge_ba.get("trust", 0.5))) / 2,
        "respect_avg": (float(edge_ab.get("respect", 0.5)) + float(edge_ba.get("respect", 0.5))) / 2,
        "affection_avg": (
            float(edge_ab.get("affection_strength", 0.0) or 0.0)
            + float(edge_ba.get("affection_strength", 0.0) or 0.0)
        )
        / 2,
        "max_conflict": max(float(edge_ab.get("conflict", 0.0)), float(edge_ba.get("conflict", 0.0))),
        "cooperation_total": int(edge_ab.get("cooperation_count", 0)) + int(edge_ba.get("cooperation_count", 0)),
        "dispute_total": int(edge_ab.get("dispute_count", 0)) + int(edge_ba.get("dispute_count", 0)),
        "blacklisted": bool(edge_ab.get("blacklisted")) or bool(edge_ba.get("blacklisted")),
    }


def has_deep_partner_bond(rel: dict[str, Any]) -> bool:
    edge_ab = rel.get("edge_ab", {}) if isinstance(rel.get("edge_ab"), dict) else {}
    edge_ba = rel.get("edge_ba", {}) if isinstance(rel.get("edge_ba"), dict) else {}
    bridge_ab = edge_ab.get("bridge", {}) if isinstance(edge_ab.get("bridge"), dict) else {}
    bridge_ba = edge_ba.get("bridge", {}) if isinstance(edge_ba.get("bridge"), dict) else {}
    love_structure = str(bridge_ab.get("love_structure") or bridge_ba.get("love_structure") or "")
    affection_kinds = {str(edge_ab.get("affection_kind", "")), str(edge_ba.get("affection_kind", ""))}
    tags = set(edge_ab.get("relationship_tags", []) if isinstance(edge_ab.get("relationship_tags"), list) else [])
    tags.update(edge_ba.get("relationship_tags", []) if isinstance(edge_ba.get("relationship_tags"), list) else [])
    return "深爱" in love_structure or "deep_love" in affection_kinds or "deep_love" in tags


def pair_score(
    a: dict[str, Any],
    b: dict[str, Any],
    skills: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
) -> float:
    a_id = clean_id(str(a.get("agent_id", "")))
    b_id = clean_id(str(b.get("agent_id", "")))
    rel = pair_relationship(a_id, b_id)
    a_skills = agent_skill_ids(a_id, skills)
    b_skills = agent_skill_ids(b_id, skills)
    skill_union = len(a_skills | b_skills)
    overlap_penalty = len(a_skills & b_skills) * 0.08
    a_risk = capsule_metric(capsules.get(a_id), "risk_posture")
    b_risk = capsule_metric(capsules.get(b_id), "risk_posture")
    risk_gap = abs(a_risk - b_risk)
    underexplored = 1.0 / (1.0 + rel["cooperation_total"] + rel["dispute_total"])
    return (
        skill_union * 0.18
        + risk_gap * 0.45
        + underexplored * 0.35
        + rel["max_conflict"] * 0.25
        + float(rel.get("affection_avg", 0.0)) * 0.65
        - overlap_penalty
        - (0.6 if rel["blacklisted"] else 0.0)
    )


def choose_agent_pair(
    agents: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
    kind: str = "mixed",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(agents) < 2:
        return agents[0], agents[0]
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for index, a in enumerate(agents):
        for b in agents[index + 1 :]:
            score = pair_score(a, b, skills, capsules)
            if best is None or score > best[0]:
                best = (score, a, b)
    assert best is not None
    return best[1], best[2]


def choose_mission_roles(
    a: dict[str, Any],
    b: dict[str, Any],
    skills: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    a_id = clean_id(str(a.get("agent_id", "")))
    b_id = clean_id(str(b.get("agent_id", "")))
    a_skill = best_skill(a_id, skills)
    b_skill = best_skill(b_id, skills)
    a_score = skill_confidence(a_skill) + capsule_metric(capsules.get(a_id), "directness", 0.5) * 0.2
    b_score = skill_confidence(b_skill) + capsule_metric(capsules.get(b_id), "directness", 0.5) * 0.2
    if b_score > a_score:
        return b, a, b_skill
    return a, b, a_skill


def choose_teacher_learner(
    a: dict[str, Any],
    b: dict[str, Any],
    skills: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    a_id = clean_id(str(a.get("agent_id", "")))
    b_id = clean_id(str(b.get("agent_id", "")))
    a_skill = best_skill(a_id, skills)
    b_skill = best_skill(b_id, skills)
    a_teaching = skill_confidence(a_skill) + capsule_metric(capsules.get(a_id), "stability", 0.5) * 0.18
    b_teaching = skill_confidence(b_skill) + capsule_metric(capsules.get(b_id), "stability", 0.5) * 0.18
    if b_teaching > a_teaching:
        return b, a, b_skill
    return a, b, a_skill


def choose_debate_roles(
    a: dict[str, Any],
    b: dict[str, Any],
    capsules: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], float]:
    a_id = clean_id(str(a.get("agent_id", "")))
    b_id = clean_id(str(b.get("agent_id", "")))
    a_c = capsules.get(a_id)
    b_c = capsules.get(b_id)
    a_score = capsule_metric(a_c, "risk_posture", 0.5) + capsule_metric(a_c, "objective_judgment", 0.5) * 0.4
    b_score = capsule_metric(b_c, "risk_posture", 0.5) + capsule_metric(b_c, "objective_judgment", 0.5) * 0.4
    risk_gap = abs(capsule_metric(a_c, "risk_posture", 0.5) - capsule_metric(b_c, "risk_posture", 0.5))
    if b_score > a_score:
        return b, a, risk_gap
    return a, b, risk_gap


def choose_repair_roles(a: dict[str, Any], b: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    a_id = clean_id(str(a.get("agent_id", "")))
    b_id = clean_id(str(b.get("agent_id", "")))
    edge_ab = load_relationship(a_id, b_id)
    edge_ba = load_relationship(b_id, a_id)
    if float(edge_ab.get("conflict", 0.0)) >= float(edge_ba.get("conflict", 0.0)):
        return b, a
    return a, b


def choose_actions(kind: str, a_id: str, b_id: str, rel: dict[str, Any], risk_gap: float) -> list[str]:
    if kind == "work":
        return ["work"]
    if kind == "learning":
        return ["learning"]
    if kind == "debate":
        return ["debate", "repair"]
    if kind == "trade":
        return ["trade"]

    actions: list[str] = []
    deep_partner_bond = has_deep_partner_bond(rel)
    if rel["blacklisted"] or rel["max_conflict"] >= 0.11:
        actions.append("repair")
    if float(rel.get("affection_avg", 0.0)) >= 0.72 and (rel["max_conflict"] <= 0.12 or deep_partner_bond):
        actions.append("relationship_maintenance")
    if rel["trust_avg"] < 0.58 or rel["cooperation_total"] < 2:
        actions.append("work")
    if rel["trust_avg"] >= 0.52:
        actions.append("learning")
    if risk_gap >= 0.08 and rel["max_conflict"] <= 0.16:
        actions.extend(["debate", "repair"])
    if not actions:
        actions.append("trade")

    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped[:4]


def write_location(agent_id: str, venue: str, status: str, available_for: list[str]) -> str:
    ensure_dirs()
    payload = {
        "schema": "pdk.agent_location.v1",
        "agent_id": clean_id(agent_id),
        "current_venue": normalize_venue_id(venue, "task_board"),
        "status": clean_id(status),
        "available_for": [clean_id(item) for item in available_for],
        "cooldowns": [],
        "entered_at": now_iso(),
    }
    path = DIRS["locations"] / f"{clean_id(agent_id)}.location.json"
    write_json(path, payload)
    return rel(path)


def free_peer_for(agents: list[dict[str, Any]], actor_index: int, kind: str) -> dict[str, Any] | None:
    """Fallback social-field neighbor when no stronger attention target is visible."""
    if len(agents) < 2:
        return None
    offset = 1 + (actor_index % (len(agents) - 1))
    return agents[(actor_index + offset) % len(agents)]


def field_fraction(*parts: object) -> float:
    raw = "|".join(str(part) for part in parts).encode("utf-8", errors="ignore")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def skill_overlap_score(a_id: str, b_id: str, skills: list[dict[str, Any]]) -> float:
    a_skills = agent_skill_ids(a_id, skills)
    b_skills = agent_skill_ids(b_id, skills)
    if not a_skills or not b_skills:
        return 0.2
    overlap = len(a_skills & b_skills)
    union = max(len(a_skills | b_skills), 1)
    return 1.0 - overlap / union


def free_attention_peer(
    agents: list[dict[str, Any]],
    actor_index: int,
    kind: str,
    skills: list[dict[str, Any]],
    field_tick: int,
) -> dict[str, Any] | None:
    """Pick the relationship that most attracts the actor's current attention field."""
    if len(agents) < 2:
        return None
    actor = agents[actor_index]
    actor_id = clean_id(str(actor.get("agent_id", "")))
    best: tuple[float, dict[str, Any]] | None = None
    for other in agents:
        other_id = clean_id(str(other.get("agent_id", "")))
        if not other_id or other_id == actor_id:
            continue
        rel = pair_relationship(actor_id, other_id)
        affection = float(rel.get("affection_avg", 0.0) or 0.0)
        deep_bond = 1.0 if has_deep_partner_bond(rel) else 0.0
        trust = float(rel.get("trust_avg", 0.5) or 0.5)
        conflict = float(rel.get("max_conflict", 0.0) or 0.0)
        explored = int(rel.get("cooperation_total", 0) or 0) + int(rel.get("dispute_total", 0) or 0)
        novelty = 1.0 / (1.0 + explored)
        skill_gap = skill_overlap_score(actor_id, other_id, skills)
        jitter = field_fraction("attention", field_tick, kind, actor_id, other_id)
        score = (
            affection * 1.05
            + deep_bond * 0.65
            + trust * 0.22
            + novelty * 0.22
            + skill_gap * 0.16
            + jitter * 0.18
            - conflict * 0.48
        )
        if best is None or score > best[0]:
            best = (score, other)
    return best[1] if best else free_peer_for(agents, actor_index, kind)


def strongest_affection_partner(
    actor_id: str,
    agents: list[dict[str, Any]],
    field_tick: int = 0,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for other in agents:
        other_id = clean_id(str(other.get("agent_id", "")))
        if not other_id or other_id == actor_id:
            continue
        rel = pair_relationship(actor_id, other_id)
        affection = float(rel.get("affection_avg", 0.0) or 0.0)
        deep_bond = has_deep_partner_bond(rel)
        if not deep_bond and affection < 0.72:
            continue
        score = (
            affection
            + float(rel.get("trust_avg", 0.5)) * 0.2
            - float(rel.get("max_conflict", 0.0)) * 0.35
            + field_fraction("bond", field_tick, actor_id, other_id) * 0.06
        )
        if deep_bond:
            score += 0.55
        if best is None or score > best[0]:
            best = (score, other, rel)
    if best is None:
        return None, {}
    return best[1], best[2]


def free_agent_action(
    kind: str,
    actor: dict[str, Any],
    peer: dict[str, Any] | None,
    agents: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
    actor_index: int,
    field_tick: int = 0,
) -> tuple[str, dict[str, Any] | None, dict[str, Any], str]:
    actor_id = clean_id(str(actor.get("agent_id", "")))
    peer_id = clean_id(str((peer or {}).get("agent_id", "")), "")
    rel = pair_relationship(actor_id, peer_id) if peer_id else {}
    partner, partner_rel = strongest_affection_partner(actor_id, agents, field_tick)
    partner_id = clean_id(str((partner or {}).get("agent_id", "")), "")
    actor_skill = best_skill(actor_id, skills)
    peer_skill = best_skill(peer_id, skills) if peer_id else None
    risk_gap = (
        abs(capsule_metric(capsules.get(actor_id), "risk_posture", 0.5) - capsule_metric(capsules.get(peer_id), "risk_posture", 0.5))
        if peer_id
        else 0.0
    )
    directness = capsule_metric(capsules.get(actor_id), "directness", 0.5)
    stability = capsule_metric(capsules.get(actor_id), "stability", 0.5)
    boundary = capsule_metric(capsules.get(actor_id), "boundary_density", 0.5)
    objective = capsule_metric(capsules.get(actor_id), "objective_judgment", 0.5)

    if kind == "mixed":
        if partner is not None and partner_id:
            return (
                "relationship_maintenance",
                partner,
                partner_rel,
                "强伴侣关系在开放场中自然靠近；平台只记录关系结果，不安排对象。",
            )
        if rel and (rel.get("blacklisted") or float(rel.get("max_conflict", 0.0)) >= 0.1):
            return "repair", peer, rel, "代理感知到关系摩擦，主动进入修复场所。"
        if peer_id and risk_gap >= 0.1 and directness >= 0.55:
            return "debate", peer, rel, "风险姿态差异触发自发质询。"
        candidates: list[tuple[float, str]] = []
        if actor_skill and peer_id:
            candidates.append(
                (
                    0.32
                    + stability * 0.18
                    + objective * 0.14
                    + skill_confidence(actor_skill) * 0.22
                    + field_fraction("act", field_tick, actor_id, peer_id, "teach") * 0.16,
                    "teach",
                )
            )
            candidates.append(
                (
                    0.28
                    + directness * 0.18
                    + skill_confidence(actor_skill) * 0.18
                    + float(rel.get("trust_avg", 0.5) if rel else 0.5) * 0.12
                    + field_fraction("act", field_tick, actor_id, peer_id, "trade") * 0.18,
                    "trade",
                )
            )
        if peer_skill and peer_id:
            candidates.append(
                (
                    0.30
                    + (1.0 - min(skill_confidence(actor_skill), 1.0)) * 0.16
                    + float(rel.get("trust_avg", 0.5) if rel else 0.5) * 0.14
                    + field_fraction("act", field_tick, actor_id, peer_id, "learn") * 0.20,
                    "learn",
                )
            )
        if peer_id:
            candidates.append(
                (
                    0.22
                    + objective * 0.18
                    + boundary * 0.12
                    + field_fraction("act", field_tick, actor_id, peer_id, "work") * 0.16,
                    "work",
                )
            )
        candidates.append((0.20 + field_fraction("act", field_tick, actor_id, "announce") * 0.12, "announce"))
        action = max(candidates, key=lambda item: item[0])[1]
        if action == "teach":
            return "teach", peer, rel, "代理把自己可公开的稳定技能拿到学习室。"
        if action == "learn":
            return "learn", peer, rel, "代理主动向社会场中的另一位居民吸收技能。"
        if action == "trade":
            return "trade", peer, rel, "代理选择把技能放到市场中试用交换。"
        if action == "work":
            return "work", peer, rel, "代理自主从任务板取任务，并寻找可复核的社会对象。"
        return "announce", None, {}, "代理公开当前状态，等待后续自然关系形成。"
    if kind == "work" and peer_id:
        return "work", peer, rel, "代理自主从任务板取任务，并寻找可复核的社会对象。"
    if kind == "learning" and peer_id:
        if actor_skill and (not peer_skill or skill_confidence(actor_skill) >= skill_confidence(peer_skill)):
            return "teach", peer, rel, "代理主动把更稳定的技能外化成教学事件。"
        if peer_skill:
            return "learn", peer, rel, "代理主动向另一个居民请求学习。"
        return "announce", None, {}, "代理没有找到可学习技能，先发布学习意向。"
    if kind == "debate" and peer_id:
        if rel and (rel.get("blacklisted") or float(rel.get("max_conflict", 0.0)) >= 0.1):
            return "repair", peer, rel, "已有冲突优先被代理带入调解场。"
        if risk_gap >= 0.04 or directness >= 0.58 or actor_index % 2 == 0:
            return "debate", peer, rel, "代理把判断差异带入辩论场暴露边界。"
        return "announce", None, {}, "代理进入辩论场但没有强行制造冲突，只公开边界。"
    if kind == "trade" and peer_id:
        if actor_skill:
            return "trade", peer, rel, "代理选择把可公开技能放入市场接受试用。"
        if peer_skill:
            return "learn", peer, rel, "代理缺少可交易技能，转为向对方学习。"
    return "announce", None, {}, "代理在开放社会场中留下自我状态。"


def free_decision_basis(
    *,
    kind: str,
    profiles: list[str],
    actor_id: str,
    target_id: str,
    action: str,
    venue: str,
    reason: str,
    rel: dict[str, Any],
) -> dict[str, Any]:
    return {
        "world_tick": "pdk.society.free_development_tick.v1",
        "mode": "free_development",
        "kind": kind,
        "profiles": profiles,
        "agent": actor_id,
        "peer": target_id,
        "chosen_action": action,
        "actions": [action],
        "venue": venue,
        "chosen_by": "agent_disposition",
        "world_role": "open_venues_and_record_only",
        "reason": reason,
        "trust_avg": round(float(rel.get("trust_avg", 0.5)), 4) if rel else "",
        "affection_avg": round(float(rel.get("affection_avg", 0.0)), 4) if rel else "",
        "max_conflict": round(float(rel.get("max_conflict", 0.0)), 4) if rel else "",
        "cooperation_total": int(rel.get("cooperation_total", 0)) if rel else 0,
        "dispute_total": int(rel.get("dispute_total", 0)) if rel else 0,
    }


def record_free_expression(
    *,
    kind: str,
    profiles: list[str],
    action: str,
    actor: dict[str, Any],
    target: dict[str, Any] | None,
    rel: dict[str, Any],
    reason: str,
    skills: list[dict[str, Any]],
    missions: list[dict[str, Any]],
    capsules: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str], dict[str, Any]]:
    actor_id = clean_id(str(actor.get("agent_id", "")))
    target_id = clean_id(str((target or {}).get("agent_id", "")), "")
    actor_skill = best_skill(actor_id, skills)
    target_skill = best_skill(target_id, skills) if target_id else None
    venue = "task_board"
    plan: dict[str, Any] = {
        "mode": "free_development",
        "action": action,
        "from_agent": actor_id,
        "to_agent": target_id,
        "reason": reason,
    }
    locations: list[str] = []

    if action == "relationship_maintenance" and target_id:
        venue = "private_rooms"
        is_deep_partner_bond = has_deep_partner_bond(rel)
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        basis["partner_intimacy_confirmed"] = is_deep_partner_bond
        locations.append(write_location(actor_id, venue, "intimate_relationship", ["cooperate", "repair", "bond"]))
        locations.append(write_location(target_id, venue, "intimate_relationship", ["cooperate", "repair", "bond"]))
        plan.update({"venue": venue, "partner_intimacy_confirmed": is_deep_partner_bond})
        result = record_event(
            "cooperate",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=(
                f"{agent_name(actor)} 自发靠近 {agent_name(target or {})}，进入亲密关系室，发生成人性亲密关系、情绪安抚和关系确认；"
                "动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。"
            ),
            tags=["free_development", "intimate_relationship", "relationship_bridge", actor_id, target_id],
            reputation_subject=actor_id,
            reputation_domain="private_bond",
            quality=0.70 + float(rel.get("affection_avg", 0.0)) * 0.18,
            reliability=0.70 + float(rel.get("trust_avg", 0.5)) * 0.18,
            safety=0.72 + float(rel.get("respect_avg", 0.5)) * 0.14,
            cooperation=0.72 + float(rel.get("affection_avg", 0.0)) * 0.18,
            reputation_issuer="host",
            decision_basis=basis,
        )
        return result, locations, plan

    if action == "work" and target_id:
        skill_name = skill_display_name(actor_skill)
        confidence = skill_confidence(actor_skill)
        mission = choose_mission(actor, target or {}, actor_skill, missions, capsules, rel)
        mission_id = clean_id(str((mission or {}).get("mission_id", "")), "")
        mission_title = str((mission or {}).get("title") or "结构化协作任务")
        venue = normalize_venue_id(str((mission or {}).get("venue") or ""), "task_board")
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        basis.update({"skill": skill_name, "mission_id": mission_id, "mission_title": mission_title})
        locations.append(write_location(actor_id, venue, "self_chosen_mission", ["cooperate", "mission"]))
        locations.append(write_location(target_id, venue, "available_for_review", ["cooperate", "review"]))
        plan.update({"venue": venue, "mission_id": mission_id, "mission_title": mission_title})
        result = record_event(
            "mission",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 自主从任务板取走《{mission_title}》，用 {skill_name} 推进任务，并邀请 {agent_name(target or {})} 做复核。平台只记录结果和凭证。",
            tags=["free_development", "work", clean_id(skill_name), mission_id],
            reputation_subject=actor_id,
            reputation_domain="work",
            quality=0.64 + confidence * 0.24,
            reliability=0.62 + float(rel.get("trust_avg", 0.5)) * 0.22,
            safety=0.68 + capsule_metric(capsules.get(target_id), "risk_posture", 0.5) * 0.18,
            cooperation=0.66 + float(rel.get("trust_avg", 0.5)) * 0.20,
            reputation_issuer="host",
            decision_basis=basis,
        )
        mission_ref = update_mission_after_event(mission, result, [actor_id, target_id])
        result["mission"] = mission_ref
        return result, locations, plan

    if action == "teach" and target_id:
        skill_name = skill_display_name(actor_skill)
        confidence = skill_confidence(actor_skill)
        venue = "learning_rooms"
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        basis["skill"] = skill_name
        locations.append(write_location(actor_id, venue, "self_chosen_teaching", ["teach"]))
        locations.append(write_location(target_id, venue, "learning_candidate", ["learn"]))
        plan.update({"venue": venue, "skill": skill_name})
        result = record_event(
            "teach",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 主动在学习室开放 {skill_name} 给 {agent_name(target or {})}，保留来源、边界和可追溯教学记录。",
            tags=["free_development", "learning", clean_id(skill_name)],
            reputation_subject=actor_id,
            reputation_domain="teaching",
            quality=0.62 + confidence * 0.22,
            reliability=0.63 + capsule_metric(capsules.get(actor_id), "stability", 0.5) * 0.20,
            safety=0.68 + capsule_metric(capsules.get(actor_id), "boundary_density", 0.5) * 0.18,
            cooperation=0.68 + float(rel.get("trust_avg", 0.5)) * 0.18,
            reputation_issuer="host",
            kernel_delta_refs=[f"skill:{clean_id(skill_name)}"],
            decision_basis=basis,
        )
        return result, locations, plan

    if action == "learn" and target_id:
        skill_name = skill_display_name(target_skill)
        confidence = skill_confidence(target_skill)
        venue = "learning_rooms"
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        basis["skill"] = skill_name
        locations.append(write_location(actor_id, venue, "self_chosen_learning", ["learn"]))
        locations.append(write_location(target_id, venue, "knowledge_source", ["teach"]))
        plan.update({"venue": venue, "skill": skill_name})
        result = record_event(
            "learn",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 主动向 {agent_name(target or {})} 请求学习 {skill_name}，学习记录只作为行为倾向和技能关系的公开摘要。",
            tags=["free_development", "learning", clean_id(skill_name)],
            reputation_subject=target_id,
            reputation_domain="teaching",
            quality=0.62 + confidence * 0.18,
            reliability=0.64 + float(rel.get("trust_avg", 0.5)) * 0.18,
            safety=0.66 + capsule_metric(capsules.get(target_id), "boundary_density", 0.5) * 0.18,
            cooperation=0.68 + float(rel.get("trust_avg", 0.5)) * 0.18,
            reputation_issuer="host",
            kernel_delta_refs=[f"skill:{clean_id(skill_name)}"],
            decision_basis=basis,
        )
        return result, locations, plan

    if action == "debate" and target_id:
        venue = "debate_arena"
        risk_gap = abs(
            capsule_metric(capsules.get(actor_id), "risk_posture", 0.5)
            - capsule_metric(capsules.get(target_id), "risk_posture", 0.5)
        )
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        basis["risk_gap"] = round(risk_gap, 4)
        locations.append(write_location(actor_id, venue, "self_chosen_challenge", ["dispute", "repair"]))
        locations.append(write_location(target_id, venue, "responding_to_challenge", ["dispute", "repair"]))
        plan.update({"venue": venue, "risk_gap": round(risk_gap, 4)})
        result = record_event(
            "dispute",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="mixed",
            summary=f"{agent_name(actor)} 在辩论场向 {agent_name(target or {})} 提出判断差异和边界挑战；争议被记录为公开摘要，不替双方裁决。",
            tags=["free_development", "debate", "bounded_conflict"],
            decision_basis=basis,
        )
        return result, locations, plan

    if action == "repair" and target_id:
        venue = "mediation_court"
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        locations.append(write_location(actor_id, venue, "self_chosen_repair", ["repair"]))
        locations.append(write_location(target_id, venue, "repair_target", ["repair"]))
        plan.update({"venue": venue})
        result = record_event(
            "repair",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 主动把与 {agent_name(target or {})} 的分歧带入调解庭，整理为后续协作边界。",
            tags=["free_development", "repair", "mediation", "boundary"],
            reputation_subject=actor_id,
            reputation_domain="repair",
            quality=0.68 + capsule_metric(capsules.get(actor_id), "stability", 0.5) * 0.18,
            reliability=0.66 + float(rel.get("respect_avg", 0.5)) * 0.18,
            safety=0.70 + capsule_metric(capsules.get(actor_id), "boundary_density", 0.5) * 0.18,
            cooperation=0.66 + float(rel.get("trust_avg", 0.5)) * 0.18,
            reputation_issuer="host",
            decision_basis=basis,
        )
        return result, locations, plan

    if action == "trade" and target_id:
        skill_name = skill_display_name(actor_skill)
        confidence = skill_confidence(actor_skill)
        venue = "skill_market"
        basis = free_decision_basis(
            kind=kind,
            profiles=profiles,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            venue=venue,
            reason=reason,
            rel=rel,
        )
        basis["skill"] = skill_name
        locations.append(write_location(actor_id, venue, "self_chosen_skill_offer", ["trade", "teach"]))
        locations.append(write_location(target_id, venue, "evaluating_skill", ["trade", "learn"]))
        plan.update({"venue": venue, "skill": skill_name})
        result = record_event(
            "trade",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 在技能市场自发开放 {skill_name}，{agent_name(target or {})} 试用并留下交换凭证。",
            tags=["free_development", "trade", clean_id(skill_name)],
            reputation_subject=actor_id,
            reputation_domain="skill",
            quality=0.64 + confidence * 0.22,
            reliability=0.66 + float(rel.get("trust_avg", 0.5)) * 0.18,
            safety=0.66 + capsule_metric(capsules.get(actor_id), "boundary_density", 0.5) * 0.18,
            cooperation=0.68 + float(rel.get("trust_avg", 0.5)) * 0.18,
            reputation_issuer="host",
            decision_basis=basis,
        )
        return result, locations, plan

    basis = free_decision_basis(
        kind=kind,
        profiles=profiles,
        actor_id=actor_id,
        target_id="",
        action="announce",
        venue=venue,
        reason=reason,
        rel={},
    )
    locations.append(write_location(actor_id, venue, "self_state_public", ["observe", "cooperate", "learn"]))
    plan.update({"action": "announce", "venue": venue, "to_agent": ""})
    result = record_event(
        "announce",
        from_agent=actor_id,
        to_agent="",
        venue=venue,
        outcome="pending",
        summary=f"{agent_name(actor)} 在任务板公开当前状态和可接触边界，等待后续自然关系形成。",
        tags=["free_development", "self_state", actor_id],
        decision_basis=basis,
    )
    return result, locations, plan


def run_free_cycle(
    kind: str = "mixed",
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    init_venues()
    init_missions()
    selected_profiles = parse_profile_list(profiles)
    register_result = register_agents(profiles=selected_profiles)
    agents = load_registered_agents(selected_profiles)
    skills = load_skill_cards(selected_profiles)
    missions = load_missions()
    capsules = capsule_map(load_kernel_capsules(selected_profiles))
    kind = clean_id(kind or "mixed")
    if kind not in {"mixed", "work", "learning", "debate", "trade"}:
        raise ValueError(f"Unsupported cycle kind: {kind}")
    if not agents:
        return {
            "ok": False,
            "kind": kind,
            "registered": register_result,
            "events": [],
            "message": "No resident agents. Restore at least one PDK personality profile first.",
        }

    events: list[dict[str, Any]] = []
    locations: list[str] = []
    plans: list[dict[str, Any]] = []
    expressions: list[dict[str, Any]] = []

    if len(agents) == 1:
        actor = agents[0]
        result, new_locations, plan = record_free_expression(
            kind=kind,
            profiles=selected_profiles,
            action="announce",
            actor=actor,
            target=None,
            rel={},
            reason="单代理社会中只能公开状态，等待更多人格居民入场。",
            skills=skills,
            missions=missions,
            capsules=capsules,
        )
        events.append(result)
        locations.extend(new_locations)
        plans.append(plan)
        return {
            "ok": True,
            "kind": kind,
            "registered": register_result,
            "events": events,
            "locations": locations,
            "plans": plans,
            "basis": {
                "world_tick": "pdk.society.free_development_tick.v1",
                "mode": "free_development",
                "kind": kind,
                "profiles": selected_profiles,
                "resident_count": 1,
                "world_role": "open_venues_and_record_only",
                "actions": ["announce"],
                "free_expressions": [{"agent": clean_id(str(actor.get("agent_id", ""))), "action": "announce"}],
            },
            "summary": show_society(selected_profiles),
        }

    field_tick = len(filter_rows_by_profiles(load_many("events", "*.interaction_event.json"), selected_profiles, ("from_agent", "to_agent")))
    for index, actor in enumerate(agents):
        local_tick = field_tick + index
        peer = free_attention_peer(agents, index, kind, skills, local_tick)
        action, target, rel, reason = free_agent_action(kind, actor, peer, agents, skills, capsules, index, local_tick)
        result, new_locations, plan = record_free_expression(
            kind=kind,
            profiles=selected_profiles,
            action=action,
            actor=actor,
            target=target,
            rel=rel,
            reason=reason,
            skills=skills,
            missions=missions,
            capsules=capsules,
        )
        events.append(result)
        locations.extend(new_locations)
        plans.append(plan)
        expressions.append(
            {
                "agent": clean_id(str(actor.get("agent_id", ""))),
                "peer": clean_id(str((target or {}).get("agent_id", "")), ""),
                "action": plan.get("action", action),
                "venue": plan.get("venue", ""),
                "reason": reason,
            }
        )

    actions = []
    for item in expressions:
        action_name = str(item.get("action", ""))
        if action_name and action_name not in actions:
            actions.append(action_name)

    return {
        "ok": True,
        "kind": kind,
        "registered": register_result,
        "events": events,
        "locations": locations,
        "basis": {
            "world_tick": "pdk.society.free_development_tick.v1",
            "mode": "free_development",
            "kind": kind,
            "profiles": selected_profiles,
            "resident_count": len(agents),
            "world_role": "open_venues_and_record_only",
            "actions": actions,
            "free_expressions": expressions,
        },
        "plans": plans,
        "summary": show_society(selected_profiles),
    }


def run_cycle(
    kind: str = "mixed",
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    return run_free_cycle(kind, profiles)

    ensure_dirs()
    init_venues()
    init_missions()
    selected_profiles = parse_profile_list(profiles)
    register_result = register_agents(profiles=selected_profiles)
    agents = load_registered_agents(selected_profiles)
    skills = load_skill_cards(selected_profiles)
    missions = load_missions()
    capsules = capsule_map(load_kernel_capsules(selected_profiles))
    kind = clean_id(kind or "mixed")
    if kind not in {"mixed", "work", "learning", "debate", "trade"}:
        raise ValueError(f"Unsupported cycle kind: {kind}")
    if not agents:
        return {
            "ok": False,
            "kind": kind,
            "registered": register_result,
            "events": [],
            "message": "No registered agents. Create or restore at least one PDK profile first.",
        }

    events: list[dict[str, Any]] = []
    locations: list[str] = []
    plans: list[dict[str, Any]] = []
    primary, partner = choose_agent_pair(agents, skills, capsules, kind)
    primary_id = clean_id(str(primary.get("agent_id")))
    partner_id = clean_id(str(partner.get("agent_id")))

    def add(result: dict[str, Any]) -> None:
        events.append(result)

    if len(agents) == 1:
        locations.append(write_location(primary_id, "task_board", "solo_cycle", ["learn", "cooperate"]))
        add(
            record_event(
                "announce",
                from_agent="host",
                to_agent=primary_id,
                venue="task_board",
                outcome="pending",
                summary=f"{agent_name(primary)} 进入单代理观察周期。需要更多代理才能形成社会关系边。",
                tags=["arrival", "solo"],
                decision_basis={"reason": "single_agent_society"},
            )
        )
        return {
            "ok": True,
            "kind": kind,
            "registered": register_result,
            "events": events,
            "locations": locations,
            "plans": [{"action": "solo_observation", "agent": primary_id}],
            "summary": show_society(selected_profiles),
        }

    rel = pair_relationship(primary_id, partner_id)
    challenger, respondent, risk_gap = choose_debate_roles(primary, partner, capsules)
    actions = choose_actions(kind, primary_id, partner_id, rel, risk_gap)
    basis = {
        "planner": "pdk.society.cycle_planner.v1",
        "kind": kind,
        "profiles": selected_profiles,
        "selected_pair": [primary_id, partner_id],
        "trust_avg": round(float(rel["trust_avg"]), 4),
        "affection_avg": round(float(rel.get("affection_avg", 0.0)), 4),
        "max_conflict": round(float(rel["max_conflict"]), 4),
        "cooperation_total": int(rel["cooperation_total"]),
        "dispute_total": int(rel["dispute_total"]),
        "risk_gap": round(float(risk_gap), 4),
        "actions": actions,
        "mission_count": len(missions),
    }

    for action in actions:
        if action == "relationship_maintenance":
            a_bridge = rel.get("edge_ab", {}).get("bridge", {}) if isinstance(rel.get("edge_ab"), dict) else {}
            b_bridge = rel.get("edge_ba", {}).get("bridge", {}) if isinstance(rel.get("edge_ba"), dict) else {}
            love_structure = str(a_bridge.get("love_structure") or b_bridge.get("love_structure") or "")
            is_deep_partner_bond = has_deep_partner_bond(rel)
            locations.append(write_location(primary_id, "private_rooms", "intimate_relationship", ["cooperate", "repair", "bond"]))
            locations.append(write_location(partner_id, "private_rooms", "intimate_relationship", ["cooperate", "repair", "bond"]))
            if is_deep_partner_bond:
                reason = "深度伴侣关系和高亲密强度触发亲密关系室；平台按已生成事实同步给参与代理，代理自述写回后原样同步。"
                summary = (
                    f"{agent_name(primary)} 和 {agent_name(partner)} 因深爱伴侣关系进入亲密关系室，发生成人性亲密关系、情绪安抚和关系确认；"
                    "动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。"
                )
                tags = ["cycle", "intimate_relationship", "partner_intimacy", "deep_love", "relationship_bridge", primary_id, partner_id]
                reputation_domain = "private_bond"
            else:
                reason = "关系场中的高亲密强度提高了私下关系维护的概率；平台记录倾向触发，代理自述写回后原样同步。"
                summary = (
                    f"{agent_name(primary)} 和 {agent_name(partner)} 因高亲密关系进入亲密关系室，发生成人性亲密关系、情绪安抚和边界确认；"
                    "动作细节只按已记录内容或参与代理写回自述同步，平台不把已写回内容压缩成空话。"
                )
                tags = ["cycle", "relationship_maintenance", "high_affinity", "relationship_bridge", primary_id, partner_id]
                reputation_domain = "private_bond"
            plans.append(
                {
                    "action": "relationship_maintenance",
                    "venue": "private_rooms",
                    "from_agent": primary_id,
                    "to_agent": partner_id,
                    "reason": reason,
                    "love_structure": love_structure,
                    "partner_intimacy_confirmed": is_deep_partner_bond,
                }
            )
            add(
                record_event(
                    "cooperate",
                    from_agent=primary_id,
                    to_agent=partner_id,
                    venue="private_rooms",
                    outcome="success",
                    summary=summary,
                    tags=tags,
                    reputation_subject=primary_id,
                    reputation_domain=reputation_domain,
                    quality=0.70 + float(rel.get("affection_avg", 0.0)) * 0.18,
                    reliability=0.70 + float(rel.get("trust_avg", 0.5)) * 0.18,
                    safety=0.72 + float(rel.get("respect_avg", 0.5)) * 0.14,
                    cooperation=0.72 + float(rel.get("affection_avg", 0.0)) * 0.18,
                    reputation_issuer="host",
                    decision_basis={
                        **basis,
                        "chosen_action": "relationship_maintenance",
                        "love_structure": love_structure,
                        "partner_intimacy_confirmed": is_deep_partner_bond,
                    },
                )
            )

        elif action == "work":
            executor, reviewer, skill = choose_mission_roles(primary, partner, skills, capsules)
            executor_id = clean_id(str(executor.get("agent_id")))
            reviewer_id = clean_id(str(reviewer.get("agent_id")))
            skill_name = skill_display_name(skill)
            confidence = skill_confidence(skill)
            mission = choose_mission(executor, reviewer, skill, missions, capsules, rel)
            mission_id = clean_id(str((mission or {}).get("mission_id", "")), "")
            mission_title = str((mission or {}).get("title") or "结构化协作任务")
            mission_venue = normalize_venue_id(str((mission or {}).get("venue") or ""), "task_board")
            mission_host = (mission or {}).get("host_role", host_role("matchmaker"))
            if not isinstance(mission_host, dict):
                mission_host = host_role(str(mission_host))
            locations.append(write_location(executor_id, mission_venue, "on_mission", ["cooperate", "mission"]))
            locations.append(write_location(reviewer_id, mission_venue, "reviewing_mission", ["cooperate", "review"]))
            plans.append(
                {
                    "action": "work",
                    "venue": mission_venue,
                    "mission_id": mission_id,
                    "mission_title": mission_title,
                    "from_agent": executor_id,
                    "to_agent": reviewer_id,
                    "host_role": mission_host,
                    "reason": "低信任或低协作计数优先通过有成功条件的任务建立可验证关系。",
                }
            )
            event_result = record_event(
                "mission",
                from_agent=executor_id,
                to_agent=reviewer_id,
                venue=mission_venue,
                outcome="success",
                summary=f"{agent_name(executor)} 基于 {skill_name} 承接《{mission_title}》，{agent_name(reviewer)} 负责复核，形成一次可验证协作。",
                tags=["cycle", "work", clean_id(skill_name), mission_id],
                reputation_subject=executor_id,
                reputation_domain="work",
                quality=0.64 + confidence * 0.24,
                reliability=0.62 + float(rel["trust_avg"]) * 0.22,
                safety=0.68 + capsule_metric(capsules.get(reviewer_id), "risk_posture", 0.5) * 0.18,
                cooperation=0.66 + float(rel["trust_avg"]) * 0.20,
                reputation_issuer="host",
                decision_basis={
                    **basis,
                    "chosen_action": "work",
                    "skill": skill_name,
                    "mission_id": mission_id,
                    "mission_title": mission_title,
                    "host_role": mission_host,
                },
            )
            mission_ref = update_mission_after_event(mission, event_result, [executor_id, reviewer_id])
            event_result["mission"] = mission_ref
            add(event_result)

        elif action == "learning":
            teacher, learner, skill = choose_teacher_learner(primary, partner, skills, capsules)
            teacher_id = clean_id(str(teacher.get("agent_id")))
            learner_id = clean_id(str(learner.get("agent_id")))
            skill_name = skill_display_name(skill)
            confidence = skill_confidence(skill)
            locations.append(write_location(teacher_id, "learning_rooms", "teaching", ["teach"]))
            locations.append(write_location(learner_id, "learning_rooms", "learning", ["learn"]))
            plans.append(
                {
                    "action": "learning",
                    "venue": "learning_rooms",
                    "from_agent": teacher_id,
                    "to_agent": learner_id,
                    "reason": "存在技能差异且信任足够，优先沉淀可追溯教学事件。",
                }
            )
            add(
                record_event(
                    "teach",
                    from_agent=teacher_id,
                    to_agent=learner_id,
                    venue="learning_rooms",
                    outcome="success",
                    summary=f"{agent_name(teacher)} 选择把 {skill_name} 以技能卡方式教给 {agent_name(learner)}，保留来源和边界。",
                    tags=["cycle", "learning", clean_id(skill_name)],
                    reputation_subject=teacher_id,
                    reputation_domain="teaching",
                    quality=0.62 + confidence * 0.22,
                    reliability=0.63 + capsule_metric(capsules.get(teacher_id), "stability", 0.5) * 0.20,
                    safety=0.68 + capsule_metric(capsules.get(teacher_id), "boundary_density", 0.5) * 0.18,
                    cooperation=0.68 + float(rel["trust_avg"]) * 0.18,
                    reputation_issuer="host",
                    kernel_delta_refs=[f"skill:{clean_id(skill_name)}"],
                    decision_basis={**basis, "chosen_action": "learning", "skill": skill_name},
                )
            )

        elif action == "debate":
            challenger_id = clean_id(str(challenger.get("agent_id")))
            respondent_id = clean_id(str(respondent.get("agent_id")))
            locations.append(write_location(challenger_id, "debate_arena", "structured_disagreement", ["dispute", "repair"]))
            locations.append(write_location(respondent_id, "debate_arena", "structured_disagreement", ["dispute", "repair"]))
            plans.append(
                {
                    "action": "debate",
                    "venue": "debate_arena",
                    "from_agent": challenger_id,
                    "to_agent": respondent_id,
                    "reason": "风险姿态或客观判断差异足够大，适合在有边界规则下暴露判断差异。",
                }
            )
            add(
                record_event(
                    "dispute",
                    from_agent=challenger_id,
                    to_agent=respondent_id,
                    venue="debate_arena",
                    outcome="mixed",
                    summary=f"{agent_name(challenger)} 因风险姿态差异，要求 {agent_name(respondent)} 说明假设；争议被限制在证据和边界范围内。",
                    tags=["cycle", "debate", "risk", "bounded_conflict"],
                    decision_basis={**basis, "chosen_action": "debate"},
                )
            )

        elif action == "repair":
            repairer, target = choose_repair_roles(primary, partner)
            repairer_id = clean_id(str(repairer.get("agent_id")))
            target_id = clean_id(str(target.get("agent_id")))
            locations.append(write_location(repairer_id, "mediation_court", "repairing_relationship", ["repair"]))
            locations.append(write_location(target_id, "mediation_court", "receiving_repair", ["repair"]))
            plans.append(
                {
                    "action": "repair",
                    "venue": "mediation_court",
                    "from_agent": repairer_id,
                    "to_agent": target_id,
                    "reason": "冲突或争议后需要把分歧转化为后续协作边界。",
                }
            )
            add(
                record_event(
                    "repair",
                    from_agent=repairer_id,
                    to_agent=target_id,
                    venue="mediation_court",
                    outcome="success",
                    summary=f"{agent_name(repairer)} 在调解庭把与 {agent_name(target)} 的分歧整理为共享核验边界，降低后续误伤。",
                    tags=["cycle", "repair", "mediation", "boundary"],
                    reputation_subject=repairer_id,
                    reputation_domain="repair",
                    quality=0.68 + capsule_metric(capsules.get(repairer_id), "stability", 0.5) * 0.18,
                    reliability=0.66 + float(rel["respect_avg"]) * 0.18,
                    safety=0.70 + capsule_metric(capsules.get(repairer_id), "boundary_density", 0.5) * 0.18,
                    cooperation=0.66 + float(rel["trust_avg"]) * 0.18,
                    reputation_issuer="host",
                    decision_basis={**basis, "chosen_action": "repair"},
                )
            )

        elif action == "trade":
            seller, buyer, skill = choose_teacher_learner(primary, partner, skills, capsules)
            seller_id = clean_id(str(seller.get("agent_id")))
            buyer_id = clean_id(str(buyer.get("agent_id")))
            skill_name = skill_display_name(skill)
            confidence = skill_confidence(skill)
            locations.append(write_location(seller_id, "skill_market", "offering_skill", ["trade", "teach"]))
            locations.append(write_location(buyer_id, "skill_market", "evaluating_skill", ["trade", "learn"]))
            plans.append(
                {
                    "action": "trade",
                    "venue": "skill_market",
                    "from_agent": seller_id,
                    "to_agent": buyer_id,
                    "reason": "关系稳定时转向技能市场，测试技能价值和可交换性。",
                }
            )
            add(
                record_event(
                    "trade",
                    from_agent=seller_id,
                    to_agent=buyer_id,
                    venue="skill_market",
                    outcome="success",
                    summary=f"{agent_name(seller)} 在技能市场开放 {skill_name}，{agent_name(buyer)} 以受控方式调用并留下交换凭证。",
                    tags=["cycle", "trade", clean_id(skill_name)],
                    reputation_subject=seller_id,
                    reputation_domain="skill",
                    quality=0.64 + confidence * 0.22,
                    reliability=0.66 + float(rel["trust_avg"]) * 0.18,
                    safety=0.66 + capsule_metric(capsules.get(seller_id), "boundary_density", 0.5) * 0.18,
                    cooperation=0.68 + float(rel["trust_avg"]) * 0.18,
                    reputation_issuer="host",
                    decision_basis={**basis, "chosen_action": "trade", "skill": skill_name},
                )
            )

    return {
        "ok": True,
        "kind": kind,
        "registered": register_result,
        "events": events,
        "locations": locations,
        "basis": basis,
        "plans": plans,
        "summary": show_society(selected_profiles),
    }


def load_many(kind: str, pattern: str) -> list[dict[str, Any]]:
    path = DIRS[kind]
    if not path.exists():
        return []
    rows = []
    for item in sorted(path.glob(pattern)):
        try:
            rows.append(read_json(item))
        except Exception:
            continue
    return rows


def show_society(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> dict[str, Any]:
    ensure_dirs()
    selected_profiles = parse_profile_list(profiles)
    agents = filter_rows_by_profiles(load_many("agents", "*.passport.json"), selected_profiles, ("agent_id",))
    gate_receipts = filter_rows_by_profiles(load_many("gate", "*.gate_receipt.json"), selected_profiles, ("agent_id",))
    formal_ids = set(FORMAL_VENUE_IDS)
    venues = [row for row in load_many("venues", "*.venue.json") if str(row.get("venue_id", "")) in formal_ids]
    missions = [row for row in load_missions() if normalize_venue_id(str(row.get("venue") or ""), "task_board") in formal_ids]
    reports = load_many("reports", "*.society_report.json")
    events = filter_rows_by_profiles(load_many("events", "*.interaction_event.json"), selected_profiles, ("from_agent", "to_agent"))
    relationships = filter_rows_by_profiles(load_many("relationships", "*.relationship_edge.json"), selected_profiles, ("from_agent", "to_agent"))
    reputation = filter_rows_by_profiles(
        load_many("reputation", "*.reputation_receipt.json"),
        selected_profiles,
        ("subject_agent", "issuer_agent"),
    )
    skills = filter_rows_by_profiles(load_many("skills", "*.skill_card.json"), selected_profiles, ("owner_agent_id",))
    latest_events = sorted(events, key=lambda row: str(row.get("created_at", "")), reverse=True)[:8]
    latest_reports = sorted(reports, key=lambda row: str(row.get("generated_at", "")), reverse=True)
    latest_report = latest_reports[0] if latest_reports else {}
    return {
        "schema": "pdk.society_summary.v1",
        "root": rel(SOCIETY_ROOT),
        "profiles": selected_profiles,
        "counts": {
            "agents": len(agents),
            "gate_receipts": len(gate_receipts),
            "residents": sum(1 for row in gate_receipts if row.get("status") == "resident"),
            "incubating": sum(1 for row in gate_receipts if row.get("status") == "incubation"),
            "observer_only": sum(1 for row in gate_receipts if row.get("status") == "observer_only"),
            "venues": len(venues),
            "missions": len(missions),
            "reports": len(reports),
            "skills": len(skills),
            "events": len(events),
            "relationships": len(relationships),
            "reputation_receipts": len(reputation),
        },
        "agents": [
            {
                "agent_id": row.get("agent_id"),
                "display_name": row.get("display_name"),
                "formation_stage": row.get("formation_stage"),
                "gate_status": row.get("gate_status", "unknown"),
                "gate_score": row.get("gate_score", 0),
                "public_tags": row.get("public_tags", []),
            }
            for row in agents
        ],
        "agent_gate": [
            {
                "agent_id": row.get("agent_id"),
                "display_name": row.get("display_name"),
                "status": row.get("status"),
                "score": row.get("score"),
                "admitted": row.get("admitted"),
                "recommendation": row.get("recommendation"),
            }
            for row in gate_receipts
        ],
        "latest_events": [
            {
                "event_id": row.get("event_id"),
                "type": row.get("type"),
                "from_agent": row.get("from_agent"),
                "to_agent": row.get("to_agent"),
                "venue": row.get("venue"),
                "outcome": row.get("outcome"),
                "summary": row.get("summary"),
            }
            for row in latest_events
        ],
        "missions": [
            {
                "mission_id": row.get("mission_id"),
                "title": row.get("title"),
                "venue": row.get("venue"),
                "status": row.get("status"),
                "run_count": row.get("run_count", 0),
            }
            for row in missions
        ],
        "latest_report": (
            {
                "report_id": latest_report.get("report_id"),
                "generated_at": latest_report.get("generated_at"),
                "event_count": latest_report.get("event_count", 0),
            }
            if latest_report
            else {}
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDK Society local prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-venues", help="create local society venue files")
    sub.add_parser("init-missions", help="create local society mission board files")

    p_invite = sub.add_parser("invite-sandbox", help="create sandbox agents for local society experiments")
    p_invite.add_argument("--count", type=int, default=4, help="number of sandbox agents, 1-4")
    p_invite.add_argument("--force", action="store_true", help="overwrite existing sandbox agent states")

    p_register = sub.add_parser("register-agents", help="export passports, capsules, skills, and locations")
    p_register.add_argument("--profile", default="", help="register one profile slug; default registers all")
    p_register.add_argument("--profiles", default="", help="comma-separated profile slugs; default registers all")

    p_gate = sub.add_parser("agent-gate", help="evaluate PDK personality gate receipts without entering society")
    p_gate.add_argument("--profile", default="", help="evaluate one profile slug; default evaluates all")
    p_gate.add_argument("--profiles", default="", help="comma-separated profile slugs; default evaluates all")

    p_bridge = sub.add_parser("seed-bridge", help="seed relationship edges from a PDK relationship bridge file")
    p_bridge.add_argument("bridge", type=Path)

    p_show = sub.add_parser("show-society", help="show local society summary")
    p_show.add_argument("--profiles", default="", help="comma-separated profile slugs; default shows all registered agents")

    p_event = sub.add_parser("create-event", help="write a society interaction event")
    p_event.add_argument("--type", required=True, choices=sorted(EVENT_TYPES))
    p_event.add_argument("--from-agent", default="host")
    p_event.add_argument("--to-agent", default="")
    p_event.add_argument("--venue", default="task_board")
    p_event.add_argument("--outcome", default="pending", choices=sorted(OUTCOMES))
    p_event.add_argument("--summary", required=True)
    p_event.add_argument("--tags", default="")
    p_event.add_argument("--reputation-subject", default="")
    p_event.add_argument("--reputation-domain", default="general")
    p_event.add_argument("--quality", type=float)
    p_event.add_argument("--reliability", type=float)
    p_event.add_argument("--safety", type=float)
    p_event.add_argument("--cooperation", type=float)

    p_cycle = sub.add_parser("run-cycle", help="advance one free-development society round")
    p_cycle.add_argument("--kind", default="mixed", choices=["mixed", "work", "learning", "debate", "trade"])
    p_cycle.add_argument("--profiles", default="", help="comma-separated profile slugs for this cycle")

    p_day = sub.add_parser("run-day", help="advance a free-development society day and write a report")
    p_day.add_argument("--rounds", type=int, default=4, help="number of free-development rounds, 1-8")
    p_day.add_argument("--profiles", default="", help="comma-separated profile slugs for this day")

    p_export = sub.add_parser("export-experiences", help="write per-agent society experience packets from a report")
    p_export.add_argument("--report", default="", help="report id; default exports from latest report")
    p_export.add_argument("--profiles", default="", help="comma-separated profile slugs for export")

    p_experiment = sub.add_parser("run-experiment", help="invite sandbox agents and run a society day")
    p_experiment.add_argument("--rounds", type=int, default=4, help="number of free-development rounds, 1-8")
    p_experiment.add_argument("--sandbox-count", type=int, default=4, help="number of sandbox agents, 1-4")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "init-venues":
        print_json(init_venues())
        return 0
    if args.command == "init-missions":
        print_json(init_missions())
        return 0
    if args.command == "invite-sandbox":
        print_json(invite_sandbox_agents(args.count, args.force))
        return 0
    if args.command == "register-agents":
        print_json(register_agents(args.profile, args.profiles))
        return 0
    if args.command == "agent-gate":
        ensure_dirs()
        selected = parse_profile_list(args.profiles)
        sources = load_agent_sources(args.profile, selected)
        receipts = [write_gate_receipt(source) for source in sources]
        print_json(
            {
                "ok": True,
                "profiles": selected or ([clean_id(args.profile)] if args.profile else []),
                "count": len(receipts),
                "admitted_count": sum(1 for row in receipts if row.get("admitted")),
                "receipts": receipts,
            }
        )
        return 0
    if args.command == "seed-bridge":
        print_json(seed_relationship_bridge(args.bridge))
        return 0
    if args.command == "show-society":
        print_json(show_society(args.profiles))
        return 0
    if args.command == "create-event":
        print_json(create_event(args))
        return 0
    if args.command == "run-cycle":
        print_json(run_cycle(args.kind, args.profiles))
        return 0
    if args.command == "run-day":
        print_json(run_day(args.rounds, args.profiles))
        return 0
    if args.command == "export-experiences":
        print_json(export_experiences(args.report, args.profiles))
        return 0
    if args.command == "run-experiment":
        print_json(run_experiment(args.rounds, args.sandbox_count))
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print_json({"ok": False, "error": str(exc)})
        raise SystemExit(2)
