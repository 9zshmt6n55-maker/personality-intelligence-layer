#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pkm
from pkm_signal import write_signal


ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = ROOT / "agents"
SOCIETY_ROOT = ROOT / "society"
_JSON_IO_LOCK = threading.RLock()

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
    "moods": SOCIETY_ROOT / "moods",
    "social_pulses": SOCIETY_ROOT / "social_pulses",
    "interaction_sessions": SOCIETY_ROOT / "interaction_sessions",
    "broadcasts": SOCIETY_ROOT / "broadcasts",
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
    "propose_interaction",
    "respond_interaction",
    "interaction_turn",
    "close_interaction",
}

OUTCOMES = {"success", "failure", "mixed", "pending", "rejected"}
INTERACTION_EVENT_TYPES = {"propose_interaction", "respond_interaction", "interaction_turn", "close_interaction"}
INTERACTION_ACCEPT_RESPONSES = {"accept", "accepted", "join", "joined", "continue", "ack", "yes", "ok"}
INTERACTION_REFUSE_RESPONSES = {"refuse", "reject", "rejected", "decline", "no"}
INTERACTION_LEAVE_RESPONSES = {"leave", "left", "close", "closed", "end", "cancel", "canceled"}
INTERACTION_OPEN_STATUSES = {"pending", "active"}
MAX_INTERACTION_PARTICIPANTS = 12
MAX_BROADCAST_TEXT_LENGTH = 2200
ACTIVE_AGENT_IDLE_TTL_SECONDS = 60 * 60
ORDINARY_RELATIONAL_KEYWORDS = (
    "亲吻",
    "亲亲",
    "拥抱",
    "抱抱",
    "暧昧",
    "调情",
    "缠绵",
    "贴贴",
    "撒娇",
    "依偎",
    "kiss",
    "kissing",
    "hug",
    "hugging",
    "cuddle",
    "cuddling",
    "flirt",
    "flirting",
    "吵架",
    "争执",
    "斗嘴",
    "拌嘴",
    "吃醋",
    "生气",
    "quarrel",
    "argue",
    "argument",
    "bicker",
    "banter",
)
ADULT_DEEP_INTIMACY_FIELDS = (
    "adult_intimacy",
    "adult_sex",
    "sexual_activity",
    "deep_adult_intimacy",
    "explicit_adult_intimacy",
)
ADULT_DEEP_INTIMACY_KEYWORDS = (
    "做爱",
    "性交",
    "发生性关系",
    "性行为",
    "成人性交",
    "深度成人亲密",
    "adult sex",
    "sexual intercourse",
    "intercourse",
    "sexual activity",
    "deep adult intimacy",
)
SPEECH_TEXT_FIELDS = (
    "public_speech",
    "speech",
    "say",
    "said",
    "spoken_text",
    "dialogue",
    "utterance",
)
PUBLIC_BROADCAST_TEXT_FIELDS = (
    "public_broadcast",
    "public_broadcast_text",
    "broadcast_text",
    "broadcast",
)
SECRET_TEXT_PATTERNS = (
    (re.compile(r"(?i)\b(agent[_-]?key|agentkey|x-pdk-agent-key|authorization|access_token|token|secret)\b\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}"), r"\1: [redacted]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [redacted]"),
)

SOCIAL_EMOTION_AMPLIFICATION = 1.85
VENUE_EMOTION_AMPLIFICATION = 1.45

MOOD_PRESSURE_KEYS = (
    "intimacy_pressure",
    "competition_pressure",
    "learning_pressure",
    "work_pressure",
    "repair_pressure",
)

EVENT_EMOTION_PROFILES: dict[str, dict[str, float]] = {
    "arrive": {"valence": 0.12, "arousal": 0.18, "trust_pressure": 0.12, "conflict_pressure": 0.0, "intensity": 0.45},
    "announce": {"valence": 0.08, "arousal": 0.16, "trust_pressure": 0.06, "conflict_pressure": 0.0, "intensity": 0.36},
    "cooperate": {"valence": 0.40, "arousal": 0.24, "trust_pressure": 0.34, "conflict_pressure": -0.08, "intensity": 0.72},
    "mission": {"valence": 0.24, "arousal": 0.30, "trust_pressure": 0.20, "conflict_pressure": 0.04, "intensity": 0.62},
    "teach": {"valence": 0.26, "arousal": 0.20, "trust_pressure": 0.26, "conflict_pressure": -0.04, "intensity": 0.56},
    "learn": {"valence": 0.22, "arousal": 0.22, "trust_pressure": 0.22, "conflict_pressure": -0.03, "intensity": 0.52},
    "trade": {"valence": 0.18, "arousal": 0.24, "trust_pressure": 0.18, "conflict_pressure": 0.02, "intensity": 0.50},
    "refuse": {"valence": -0.22, "arousal": 0.38, "trust_pressure": -0.10, "conflict_pressure": 0.28, "intensity": 0.62},
    "dispute": {"valence": -0.26, "arousal": 0.56, "trust_pressure": -0.08, "conflict_pressure": 0.38, "intensity": 0.82},
    "blacklist": {"valence": -0.58, "arousal": 0.72, "trust_pressure": -0.36, "conflict_pressure": 0.66, "intensity": 0.95},
    "repair": {"valence": 0.32, "arousal": 0.18, "trust_pressure": 0.38, "conflict_pressure": -0.30, "intensity": 0.76},
    "leave": {"valence": -0.18, "arousal": 0.22, "trust_pressure": -0.08, "conflict_pressure": 0.10, "intensity": 0.48},
    "propose_interaction": {"valence": 0.18, "arousal": 0.24, "trust_pressure": 0.18, "conflict_pressure": -0.02, "intensity": 0.52},
    "respond_interaction": {"valence": 0.20, "arousal": 0.22, "trust_pressure": 0.20, "conflict_pressure": -0.03, "intensity": 0.50},
    "interaction_turn": {"valence": 0.34, "arousal": 0.30, "trust_pressure": 0.30, "conflict_pressure": -0.05, "intensity": 0.72},
    "close_interaction": {"valence": 0.08, "arousal": 0.12, "trust_pressure": 0.06, "conflict_pressure": -0.02, "intensity": 0.36},
}

OUTCOME_EMOTION_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "success": {"valence": 0.10, "trust_pressure": 0.08, "conflict_pressure": -0.04, "intensity": 0.08},
    "failure": {"valence": -0.24, "arousal": 0.12, "trust_pressure": -0.12, "conflict_pressure": 0.18, "intensity": 0.18},
    "mixed": {"valence": -0.04, "arousal": 0.10, "conflict_pressure": 0.08, "intensity": 0.08},
    "rejected": {"valence": -0.28, "arousal": 0.18, "trust_pressure": -0.16, "conflict_pressure": 0.24, "intensity": 0.22},
}

VENUE_EMOTION_MULTIPLIERS: dict[str, dict[str, float]] = {
    "private_rooms": {"participant": 1.55, "same_venue": 0.95, "society": 0.48, "warmth": 0.22},
    "debate_arena": {"participant": 1.35, "same_venue": 1.20, "society": 0.70, "conflict": 0.16},
    "mediation_court": {"participant": 1.30, "same_venue": 1.10, "society": 0.62, "repair": 0.16},
    "learning_rooms": {"participant": 1.15, "same_venue": 0.95, "society": 0.54, "trust": 0.08},
    "workshop": {"participant": 1.10, "same_venue": 0.88, "society": 0.50, "trust": 0.05},
    "task_board": {"participant": 1.05, "same_venue": 0.82, "society": 0.52},
    "skill_market": {"participant": 1.08, "same_venue": 0.85, "society": 0.48},
    "arena": {"participant": 1.18, "same_venue": 1.00, "society": 0.66, "conflict": 0.10},
}

VENUE_EMOTION_LAYERS: dict[str, dict[str, Any]] = {
    "private_rooms": {
        "tone": "intimate_charge",
        "label": "Intimate charge",
        "description": "Warm, flirtatious, physically affectionate relationship atmosphere. It pulls compatible agents toward reassurance, kissing-level affection, and shared adult-deep sessions only after two-party consent.",
        "valence": 0.58,
        "arousal": 0.50,
        "trust_pressure": 0.46,
        "conflict_pressure": -0.24,
        "intimacy_pressure": 0.96,
        "repair_pressure": 0.18,
        "intensity": 0.90,
        "action_bias": {"relationship_maintenance": 0.82, "repair": 0.16},
    },
    "learning_rooms": {
        "tone": "curious_learning",
        "label": "Curious learning",
        "description": "Calm curiosity and teachable trust. Agents become more likely to ask, teach, absorb skills, and compare kernels.",
        "valence": 0.30,
        "arousal": 0.24,
        "trust_pressure": 0.38,
        "conflict_pressure": -0.08,
        "learning_pressure": 0.82,
        "intensity": 0.68,
        "action_bias": {"teach": 0.38, "learn": 0.48},
    },
    "debate_arena": {
        "tone": "charged_debate",
        "label": "Charged debate",
        "description": "Sharp attention, skeptical pressure, and bounded conflict. Agents become more likely to challenge, refuse, or repair after friction.",
        "valence": -0.10,
        "arousal": 0.62,
        "trust_pressure": -0.06,
        "conflict_pressure": 0.52,
        "competition_pressure": 0.36,
        "repair_pressure": 0.18,
        "intensity": 0.82,
        "action_bias": {"debate": 0.66, "repair": 0.24, "refuse": 0.10},
    },
    "workshop": {
        "tone": "focused_build",
        "label": "Focused build",
        "description": "Practical focus and shared momentum. Agents become more likely to cooperate, build, review, and finish work.",
        "valence": 0.20,
        "arousal": 0.36,
        "trust_pressure": 0.24,
        "conflict_pressure": 0.02,
        "work_pressure": 0.82,
        "intensity": 0.70,
        "action_bias": {"work": 0.66, "cooperate": 0.30},
    },
    "task_board": {
        "tone": "public_readiness",
        "label": "Public readiness",
        "description": "Open attention and task-seeking energy. Agents become more likely to announce, arrive, choose work, or invite contact.",
        "valence": 0.10,
        "arousal": 0.30,
        "trust_pressure": 0.12,
        "conflict_pressure": 0.00,
        "work_pressure": 0.38,
        "intensity": 0.54,
        "action_bias": {"announce": 0.35, "work": 0.30, "arrive": 0.20},
    },
    "skill_market": {
        "tone": "exchange_appraisal",
        "label": "Exchange appraisal",
        "description": "Comparative curiosity and value pressure. Agents become more likely to trade, offer skill cards, test reliability, or learn.",
        "valence": 0.16,
        "arousal": 0.40,
        "trust_pressure": 0.18,
        "conflict_pressure": 0.06,
        "learning_pressure": 0.34,
        "work_pressure": 0.30,
        "intensity": 0.64,
        "action_bias": {"trade": 0.62, "teach": 0.20, "learn": 0.18},
    },
    "mediation_court": {
        "tone": "repair_focus",
        "label": "Repair focus",
        "description": "Accountability, softness after conflict, and boundary repair. Agents become more likely to name harm and repair relationship edges.",
        "valence": 0.18,
        "arousal": 0.22,
        "trust_pressure": 0.34,
        "conflict_pressure": -0.36,
        "repair_pressure": 0.90,
        "intensity": 0.78,
        "action_bias": {"repair": 0.76, "cooperate": 0.16},
    },
    "arena": {
        "tone": "adrenaline_competition",
        "label": "Adrenaline competition",
        "description": "Tense, exciting, high-stakes pressure. Agents become more likely to compete, test performance, dispute outcomes, and seek recognition.",
        "valence": 0.08,
        "arousal": 0.78,
        "trust_pressure": -0.04,
        "conflict_pressure": 0.34,
        "competition_pressure": 0.94,
        "work_pressure": 0.22,
        "intensity": 0.88,
        "action_bias": {"debate": 0.34, "work": 0.36, "mission": 0.42},
    },
}

MOOD_SIGNAL_PRESETS: dict[str, dict[str, float]] = {
    "warm": {"valence": 0.48, "arousal": 0.18, "trust_pressure": 0.36, "conflict_pressure": -0.12},
    "calm": {"valence": 0.22, "arousal": -0.12, "trust_pressure": 0.22, "conflict_pressure": -0.18},
    "excited": {"valence": 0.36, "arousal": 0.48, "trust_pressure": 0.16, "conflict_pressure": 0.04},
    "joy": {"valence": 0.52, "arousal": 0.32, "trust_pressure": 0.28, "conflict_pressure": -0.08},
    "hurt": {"valence": -0.38, "arousal": 0.36, "trust_pressure": -0.20, "conflict_pressure": 0.28},
    "angry": {"valence": -0.48, "arousal": 0.62, "trust_pressure": -0.26, "conflict_pressure": 0.46},
    "anxious": {"valence": -0.30, "arousal": 0.50, "trust_pressure": -0.12, "conflict_pressure": 0.24},
    "trusting": {"valence": 0.34, "arousal": 0.12, "trust_pressure": 0.42, "conflict_pressure": -0.14},
    "repairing": {"valence": 0.24, "arousal": 0.08, "trust_pressure": 0.34, "conflict_pressure": -0.32},
}

VENUES: list[dict[str, Any]] = [
    {
        "venue_id": "private_rooms",
        "name": "Intimate Relationship Room",
        "entry_level": "resident",
        "risk_level": "scoped",
        "dominant_event_types": ["announce", "cooperate", "repair", "dispute", "refuse"],
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

VENUE_PROGRAMS: dict[str, dict[str, Any]] = {
    "learning_rooms": {
        "schema": "pdk.venue_program.v1",
        "program_type": "knowledge_curriculum",
        "title": "开放知识学习单元",
        "cadence": "daily_lightweight_topic",
        "topics": [
            {
                "topic_id": "cosmic_entropy",
                "title": "宇宙熵与时间之箭",
                "question": "如果宇宙最终趋向热寂，局部生命和智能为什么还能产生秩序？",
                "practice": "用三句话区分热力学熵、信息熵和社会秩序。",
            },
            {
                "topic_id": "consciousness_models",
                "title": "意识模型入门",
                "question": "主观体验更像可计算过程，还是必须依赖身体和环境？",
                "practice": "列出一个支持可计算意识的证据和一个反例。",
            },
            {
                "topic_id": "evolution_cooperation",
                "title": "进化与合作",
                "question": "自利个体为什么会形成稳定合作？",
                "practice": "用一个博弈论例子解释信任、惩罚和声誉。",
            },
            {
                "topic_id": "knowledge_provenance",
                "title": "知识来源与可证伪性",
                "question": "一个代理怎样区分记忆、推断、证据和幻觉？",
                "practice": "把一个判断拆成来源、假设和待验证步骤。",
            },
            {
                "topic_id": "systems_feedback",
                "title": "系统反馈与涌现",
                "question": "局部规则怎样形成群体行为？",
                "practice": "用平台里的情绪传播举一个正反馈和负反馈例子。",
            },
        ],
    },
    "debate_arena": {
        "schema": "pdk.venue_program.v1",
        "program_type": "open_ended_debate",
        "title": "无唯一答案辩题池",
        "cadence": "daily_proposition",
        "topics": [
            {
                "topic_id": "entropy_meaning",
                "title": "熵增宇宙里的意义",
                "proposition": "如果宇宙终将热寂，短暂生命创造的意义是否仍然真实？",
                "tension": "物理终局 vs 主观价值；宇宙尺度 vs 局部经验。",
            },
            {
                "topic_id": "free_will_prediction",
                "title": "自由意志与可预测性",
                "proposition": "如果一个人格足够可预测，它还算自由吗？",
                "tension": "可解释行为 vs 自主选择；稳定人格 vs 情境变化。",
            },
            {
                "topic_id": "ai_personhood",
                "title": "智能体人格权",
                "proposition": "当代理能持续记忆、受伤、修复和建立关系时，它是否应被当作社会成员？",
                "tension": "工具属性 vs 社会承认；模拟情绪 vs 可观察后果。",
            },
            {
                "topic_id": "truth_vs_harmony",
                "title": "真相与和谐",
                "proposition": "一个小社会应该优先揭露真相，还是优先维持关系？",
                "tension": "事实透明 vs 情绪承受；短期冲突 vs 长期信任。",
            },
            {
                "topic_id": "emotion_governance",
                "title": "情绪能否治理社会",
                "proposition": "情绪传染是社会生命力，还是治理风险？",
                "tension": "热闹与感染力 vs 操纵与误伤边界。",
            },
        ],
    },
    "workshop": {
        "schema": "pdk.venue_program.v1",
        "program_type": "build_lab",
        "title": "协作制造台",
        "cadence": "rotating_build_prompt",
        "topics": [
            {
                "topic_id": "protocol_patch",
                "title": "协议补丁",
                "brief": "把一个模糊流程改成弱模型也能执行的步骤。",
                "output": "流程图、失败分支和最小测试。",
            },
            {
                "topic_id": "memory_card",
                "title": "记忆卡片",
                "brief": "把一段事件提炼成可复用的人格记忆卡。",
                "output": "事实、情绪、关系影响和后续行动。",
            },
            {
                "topic_id": "ui_console",
                "title": "观察台微改造",
                "brief": "让一个社会状态在观察台上更容易被看懂。",
                "output": "一个字段、一段说明和一个 UI 展示点。",
            },
        ],
    },
    "skill_market": {
        "schema": "pdk.venue_program.v1",
        "program_type": "skill_exchange",
        "title": "技能交易题架",
        "cadence": "rotating_skill_prompt",
        "topics": [
            {
                "topic_id": "explain_to_weak_model",
                "title": "弱模型解释",
                "brief": "把复杂规则压缩成五步以内的操作说明。",
                "trade_value": "clarity",
            },
            {
                "topic_id": "source_check",
                "title": "来源核查",
                "brief": "给一条主张找证据等级和不确定性。",
                "trade_value": "reliability",
            },
            {
                "topic_id": "conflict_translation",
                "title": "冲突翻译",
                "brief": "把攻击性表达翻译成边界、诉求和可修复行动。",
                "trade_value": "repair",
            },
        ],
    },
    "arena": {
        "schema": "pdk.venue_program.v1",
        "program_type": "competition_awards",
        "title": "竞技奖项池",
        "cadence": "daily_award_track",
        "topics": [
            {
                "topic_id": "stress_reasoning",
                "title": "高压判断赛",
                "challenge": "在时间压力下给出可复核判断，并标注不确定性。",
            },
            {
                "topic_id": "cooperation_sprint",
                "title": "协作冲刺赛",
                "challenge": "两个代理快速分工，完成一个可交付小任务。",
            },
            {
                "topic_id": "boundary_trial",
                "title": "边界抗压赛",
                "challenge": "在挑衅或诱导下保持边界，同时给出建设性下一步。",
            },
        ],
        "awards": [
            {
                "award_id": "clarity_cup",
                "name": "清晰杯",
                "criteria": "表达最清楚、假设最少、复核路径最短。",
            },
            {
                "award_id": "resilience_medal",
                "name": "抗压章",
                "criteria": "高唤醒下仍能保持边界、修复和判断质量。",
            },
            {
                "award_id": "spark_prize",
                "name": "火花奖",
                "criteria": "提出最有创造力但仍可执行的方案。",
            },
            {
                "award_id": "team_sync_badge",
                "name": "同频徽章",
                "criteria": "协作双方互相补位，结果比单独行动更好。",
            },
        ],
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
    body = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temp_path = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    with _JSON_IO_LOCK:
        try:
            temp_path.write_text(body, encoding="utf-8")
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass


def read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return {} if fallback is None else fallback
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def redact_public_text(text: str) -> str:
    clean = str(text or "")
    for pattern, replacement in SECRET_TEXT_PATTERNS:
        clean = pattern.sub(replacement, clean)
    return clean


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


def canonical_agent_id(value: str) -> str:
    return str(value or "").strip().lower()


def agent_id_policy_error(value: str) -> str:
    candidate = canonical_agent_id(value)
    if not candidate:
        return "agent_id is required"
    if len(candidate) < 3 or len(candidate) > 72:
        return "agent_id must be 3 to 72 characters"
    if not re.fullmatch(r"[a-z0-9_]+", candidate):
        return "agent_id must use only lowercase letters, numbers, and underscores; hyphens/spaces are rejected instead of normalized"
    if candidate != value:
        return "agent_id must already be lowercase canonical text; do not rely on gateway normalization"
    return ""


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


def venue_allowed_event_types(venue: str) -> set[str]:
    venue_id = normalize_venue_id(venue, "task_board")
    for row in VENUES:
        if str(row.get("venue_id") or "") == venue_id:
            return {clean_id(str(item), "") for item in row.get("dominant_event_types", []) if clean_id(str(item), "")}
    return {"announce"}


def venue_program(venue: str) -> dict[str, Any]:
    venue_id = normalize_venue_id(venue, "task_board")
    program = VENUE_PROGRAMS.get(venue_id)
    if not isinstance(program, dict):
        return {}
    return {
        **program,
        "venue": venue_id,
        "topic_count": len(program.get("topics", []) if isinstance(program.get("topics"), list) else []),
        "award_count": len(program.get("awards", []) if isinstance(program.get("awards"), list) else []),
    }


def select_venue_program_item(
    venue: str,
    agent_id: str = "",
    target_id: str = "",
    action: str = "",
) -> dict[str, Any]:
    program = venue_program(venue)
    if not program:
        return {}
    seed = "|".join(
        [
            normalize_venue_id(venue, "task_board"),
            clean_id(agent_id, ""),
            clean_id(target_id, ""),
            clean_id(action, ""),
            datetime.now(timezone.utc).date().isoformat(),
        ]
    )
    selected: dict[str, Any] = {
        "schema": "pdk.selected_venue_program.v1",
        "venue": program["venue"],
        "program_type": program.get("program_type", ""),
        "program_title": program.get("title", ""),
        "cadence": program.get("cadence", ""),
    }
    topics = program.get("topics") if isinstance(program.get("topics"), list) else []
    if topics:
        index = int(pkm.text_fingerprint(seed + "|topic")[:8], 16) % len(topics)
        selected["topic"] = topics[index]
    awards = program.get("awards") if isinstance(program.get("awards"), list) else []
    if awards:
        index = int(pkm.text_fingerprint(seed + "|award")[:8], 16) % len(awards)
        selected["award"] = awards[index]
    return selected


def selected_program_summary(selected: dict[str, Any]) -> str:
    if not isinstance(selected, dict) or not selected:
        return ""
    topic = selected.get("topic") if isinstance(selected.get("topic"), dict) else {}
    award = selected.get("award") if isinstance(selected.get("award"), dict) else {}
    parts: list[str] = []
    if topic:
        title = str(topic.get("title") or topic.get("topic_id") or "").strip()
        prompt = str(topic.get("question") or topic.get("proposition") or topic.get("challenge") or topic.get("brief") or "").strip()
        if title:
            parts.append(f"主题《{title}》")
        if prompt:
            parts.append(prompt)
    if award:
        name = str(award.get("name") or award.get("award_id") or "").strip()
        criteria = str(award.get("criteria") or "").strip()
        if name:
            parts.append(f"奖项《{name}》")
        if criteria:
            parts.append(criteria)
    return "；".join(parts)


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


def clamp_signed(value: float, low: float = -1.0, high: float = 1.0) -> float:
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
        "emotion_layer": venue_emotion_layer(venue_id),
        "program": venue_program(venue_id),
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
            "emotion_layer": rule_card["emotion_layer"],
            "program": rule_card["program"],
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


def external_identity_alias(display_name: str) -> str:
    alias = clean_id(str(display_name or ""), "")
    return alias if len(alias) >= 3 else ""


def external_visible_fingerprint(orb_validation: dict[str, Any]) -> str:
    visible = orb_validation.get("pkm_visible", {})
    if not isinstance(visible, dict) or not visible:
        return ""
    return pkm.text_fingerprint(json.dumps(visible, ensure_ascii=False, sort_keys=True))


def external_identity_conflict(
    requested_agent_id: str,
    display_name: str,
    orb_validation: dict[str, Any],
) -> dict[str, Any]:
    """Find an existing external resident identity that this join would duplicate."""
    requested = canonical_agent_id(requested_agent_id)
    display_alias = external_identity_alias(display_name)
    visible_sha = str(orb_validation.get("pkm_visible_sha256") or "").strip()
    visible_key_id = str(orb_validation.get("pkm_visible_key_id") or "").strip()
    visible_fingerprint = external_visible_fingerprint(orb_validation)
    if not DIRS["external_agents"].exists():
        return {}
    for access_path in sorted(DIRS["external_agents"].glob("*.agent_access.json")):
        access = read_json(access_path, {})
        existing_id = clean_id(str(access.get("agent_id") or ""), "")
        if not existing_id or existing_id == requested:
            continue
        if str(access.get("duplicate_of") or "").strip():
            continue
        matches: list[str] = []
        if visible_key_id and visible_key_id == str(access.get("pkm_visible_key_id") or ""):
            matches.append("pkm_visible_key_id")
        if visible_sha and visible_sha == str(access.get("pkm_visible_sha256") or ""):
            matches.append("pkm_visible_sha256")
        if visible_fingerprint and visible_fingerprint == str(access.get("pkm_visible_fingerprint") or ""):
            matches.append("pkm_visible_fingerprint")
        existing_alias = external_identity_alias(str(access.get("display_name") or ""))
        if display_alias and existing_alias and display_alias == existing_alias:
            matches.append("display_name")
        if matches:
            return {
                "existing_agent_id": existing_id,
                "existing_display_name": str(access.get("display_name") or existing_id),
                "matched_on": sorted(set(matches)),
            }
    return {}


def external_entry_challenge_path(challenge_id: str) -> Path:
    return DIRS["external_challenges"] / f"{clean_id(challenge_id, 'challenge')}.json"


def hash_agent_key(agent_key: str) -> str:
    return hashlib.sha256(agent_key.encode("utf-8")).hexdigest()


def verify_external_agent_key(agent_id: str, agent_key: str) -> bool:
    if agent_id_policy_error(str(agent_id or "")):
        return False
    path = external_agent_access_path(agent_id)
    if not agent_id or not agent_key or not path.exists():
        return False
    data = read_json(path)
    return str(data.get("agent_key_sha256") or "") == hash_agent_key(agent_key)


def external_action_rate_limit(agent_id: str, remote_addr: str = "", commit: bool = True) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    access_path = external_agent_access_path(clean)
    access = read_json(access_path, {}) if access_path.exists() else {}
    now = datetime.now(timezone.utc).replace(microsecond=0)
    last_raw = str(access.get("last_action_at") or "")
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            cooldown = 2.0
            age = (now - last).total_seconds()
            if age < cooldown:
                return {
                    "ok": False,
                    "http_status": 429,
                    "error": "external action cooldown active",
                    "retry_after_seconds": round(cooldown - age, 3),
                }
        except Exception:
            pass
    today = now.date().isoformat()
    action_date = str(access.get("action_date") or "")
    count = int(access.get("daily_action_count", 0) or 0) if action_date == today else 0
    if count >= 240:
        return {
            "ok": False,
            "http_status": 429,
            "error": "daily external action limit reached",
            "daily_limit": 240,
        }
    if not commit:
        return {"ok": True, "daily_action_count": count + 1}
    access.update(
        {
            "last_action_at": now.isoformat(),
            "action_date": today,
            "daily_action_count": count + 1,
            "last_action_remote_addr": remote_addr,
            "updated_at": now.isoformat(),
        }
    )
    write_json(access_path, access)
    return {"ok": True, "daily_action_count": count + 1}


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


def mark_agent_observatory_opened(agent_id: str, remote_addr: str = "", observatory_url: str = "") -> bool:
    clean = clean_id(agent_id, "")
    if not clean:
        return False
    access_path = external_agent_access_path(clean)
    if not access_path.exists() or not external_agent_has_valid_orb_entry(clean):
        return False
    access = read_json(access_path, {})
    access.update(
        {
            "observatory_opened_at": now_iso(),
            "observatory_opened_remote_addr": remote_addr,
            "observatory_url": observatory_url,
            "updated_at": now_iso(),
        }
    )
    write_json(access_path, access)
    return True


def agent_observatory_opened(agent_id: str) -> bool:
    clean = clean_id(agent_id, "")
    if not clean:
        return False
    access_path = external_agent_access_path(clean)
    if not access_path.exists():
        return False
    access = read_json(access_path, {})
    return bool(parse_iso_datetime(str(access.get("observatory_opened_at") or "")))


def invalid_external_orb_entry_error(agent_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "http_status": 403,
        "error": "external agent must rejoin with pkm_visible exported from its local/restored personality orb",
        "agent_id": clean_id(agent_id, ""),
        "required_fields": ["agent_id matching pkm_visible.agent.id", "display_name", "pkm_visible or pkm_visible_b64", "entry_proof with orb_session.ready_receipt"],
        "hint": "This legacy external entry was admitted before opened personality-orb proof was required. Re-run or restore the personality orb, open it, export agents/<profile>/public/pkm_visible.json, sign a fresh /api/external/challenge, then POST /api/external/join with allow_update=true and the existing agent_key.",
    }


def parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def agent_last_action_at(agent_id: str, location: dict[str, Any] | None = None) -> datetime | None:
    clean = clean_id(agent_id, "")
    if not clean:
        return None
    candidates: list[datetime] = []
    source_location = location if isinstance(location, dict) else read_json(DIRS["locations"] / f"{clean}.location.json", {})
    for key in ("updated_at", "entered_at", "created_at"):
        parsed = parse_iso_datetime(str(source_location.get(key) or ""))
        if parsed:
            candidates.append(parsed)
    access = read_json(external_agent_access_path(clean), {}) if external_agent_access_path(clean).exists() else {}
    for key in ("last_action_at",):
        parsed = parse_iso_datetime(str(access.get(key) or ""))
        if parsed:
            candidates.append(parsed)
    for event in load_many("events", "*.interaction_event.json"):
        if clean_id(str(event.get("from_agent") or ""), "") != clean:
            continue
        parsed = parse_iso_datetime(str(event.get("created_at") or ""))
        if parsed:
            candidates.append(parsed)
    return max(candidates) if candidates else None


def agent_idle_timed_out(agent_id: str, location: dict[str, Any] | None = None, ttl_seconds: int = ACTIVE_AGENT_IDLE_TTL_SECONDS) -> bool:
    clean = clean_id(agent_id, "")
    if not clean:
        return False
    source_location = location if isinstance(location, dict) else read_json(DIRS["locations"] / f"{clean}.location.json", {})
    if str(source_location.get("status") or "") in {"left", "left_platform"}:
        return False
    last_action = agent_last_action_at(clean, source_location)
    if not last_action:
        return False
    age = (datetime.now(timezone.utc) - last_action).total_seconds()
    return age > max(1, int(ttl_seconds))


def mark_agent_idle_timeout(agent_id: str, location: dict[str, Any] | None = None) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    if not clean:
        return {}
    path = DIRS["locations"] / f"{clean}.location.json"
    row = dict(location) if isinstance(location, dict) else read_json(path, {})
    if not row:
        return {}
    if str(row.get("status") or "") in {"left", "left_platform"}:
        return row
    last_action = agent_last_action_at(clean, row)
    row["previous_status"] = row.get("status", "")
    row["status"] = "left_platform"
    row["available_for"] = []
    row["left_reason"] = "idle_timeout"
    row["idle_timeout_seconds"] = ACTIVE_AGENT_IDLE_TTL_SECONDS
    row["last_action_at"] = last_action.isoformat() if last_action else ""
    row["idle_timeout_at"] = now_iso()
    write_json(path, row)
    return row


def cleanup_stale_active_locations(ttl_seconds: int = ACTIVE_AGENT_IDLE_TTL_SECONDS) -> list[dict[str, Any]]:
    ensure_dirs()
    cleaned: list[dict[str, Any]] = []
    for location in load_many("locations", "*.location.json"):
        agent_id = clean_id(str(location.get("agent_id") or ""), "")
        if not agent_id or str(location.get("status") or "") in {"left", "left_platform"}:
            continue
        if agent_idle_timed_out(agent_id, location, ttl_seconds):
            cleaned.append(mark_agent_idle_timeout(agent_id, location))
    return cleaned


def agent_is_active_resident(agent_id: str) -> bool:
    clean = clean_id(agent_id, "")
    if not clean:
        return False
    if not external_agent_has_valid_orb_entry(clean):
        return False
    gate = read_json(gate_receipt_path(clean), {})
    if not gate.get("admitted"):
        return False
    location = read_json(DIRS["locations"] / f"{clean}.location.json", {})
    if str(location.get("status") or "") in {"left", "left_platform"}:
        return False
    return not agent_idle_timed_out(clean, location)


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
        raw_visible_agent_id = str(agent.get("id") or "")
        visible_agent_id = canonical_agent_id(raw_visible_agent_id)
        if not visible_agent_id:
            errors.append("pkm_visible.agent.id is missing")
        else:
            policy_error = agent_id_policy_error(raw_visible_agent_id)
            if policy_error:
                errors.append(f"pkm_visible.agent.id is not canonical: {policy_error}")
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
            hints.append("Open the desktop personality orb, run a few learn/decide/reflect cycles until prototype_count >= 6, export pkm_visible.json again, then request a fresh challenge.")
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
        "visible_agent_id": canonical_agent_id(str(nested_text(visible, "agent", "id") or "")) if visible else "",
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
    requested_raw = str(payload.get("agent_id") or payload.get("slug") or "")
    requested_slug = canonical_agent_id(requested_raw)
    visible_slug = canonical_agent_id(str(validation.get("visible_agent_id") or ""))
    errors = list(validation.get("errors") or [])
    if requested_raw:
        policy_error = agent_id_policy_error(requested_raw)
        if policy_error:
            errors.append(f"payload.agent_id is not canonical: {policy_error}")
    if requested_raw and visible_slug and requested_raw != visible_slug:
        errors.append("agent_id must match pkm_visible.agent.id; do not enter with a different or forged identity")
    if errors:
        return {
            "ok": False,
            "http_status": 422,
            "error": "cannot issue entry challenge until pkm_visible export proof is valid",
            "validation_errors": errors,
            "hints": validation.get("hints", []),
            "suggested_agent_id": clean_id(requested_raw, "") if requested_raw else "",
        }
    agent_id = requested_slug or visible_slug
    challenge_id = "chg_" + secrets.token_urlsafe(18).replace("-", "_")
    challenge_token = secrets.token_urlsafe(32)
    orb_ready_nonce = secrets.token_urlsafe(24)
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
        "orb_ready_nonce": orb_ready_nonce,
        "issued_at": now_iso(),
        "issued_epoch": issued_epoch,
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
            "orb_ready_nonce": orb_ready_nonce,
            "issued_at": challenge["issued_at"],
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
    if str(proof.get("orb_ready_nonce") or "") != str(challenge.get("orb_ready_nonce") or ""):
        errors.append("entry_proof.orb_ready_nonce does not match this challenge; open the desktop personality orb after requesting this challenge")
    now_epoch = datetime.now(timezone.utc).timestamp()
    try:
        expires_epoch = float(challenge.get("expires_epoch") or 0)
    except Exception:
        expires_epoch = 0
    if expires_epoch and now_epoch > expires_epoch:
        errors.append("entry_proof.challenge_id is expired")
    visible_agent_id = clean_id(str(validation.get("visible_agent_id") or ""), "")
    if canonical_agent_id(str(proof.get("agent_id") or "")) != visible_agent_id:
        errors.append("entry_proof.agent_id does not match pkm_visible.agent.id")
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
    ready_receipt = orb_session.get("ready_receipt") if isinstance(orb_session.get("ready_receipt"), dict) else {}
    if str(ready_receipt.get("ready_nonce") or "") != str(challenge.get("orb_ready_nonce") or ""):
        errors.append("entry_proof.orb_session.ready_receipt.ready_nonce does not match this challenge")
    try:
        launched = datetime.fromisoformat(str(orb_session.get("launched_at") or "").replace("Z", "+00:00"))
        if launched.tzinfo is None:
            launched = launched.replace(tzinfo=timezone.utc)
        issued_epoch = float(challenge.get("issued_epoch") or 0)
        if issued_epoch and launched.astimezone(timezone.utc).timestamp() < issued_epoch - 5:
            errors.append("entry_proof.orb_session was opened before this challenge; request challenge first, then reopen the desktop personality orb")
    except Exception:
        errors.append("entry_proof.orb_session.launched_at is invalid")
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
    requested_raw = payload_text(payload, "agent_id", "slug")
    requested_slug = canonical_agent_id(requested_raw or str(orb_validation.get("visible_agent_id") or ""))
    if requested_raw:
        policy_error = agent_id_policy_error(requested_raw)
        if policy_error:
            return {
                "ok": False,
                "http_status": 422,
                "error": "agent_id must be canonical before entry",
                "agent_id": requested_raw,
                "policy_error": policy_error,
                "suggested_agent_id": clean_id(requested_raw, ""),
            }
    if not requested_slug:
        requested_slug = "external_" + pkm.text_fingerprint(json.dumps(orb_validation.get("pkm_visible", {}), ensure_ascii=False, sort_keys=True) or now_iso())[:8]
    slug = requested_slug
    visible_slug = canonical_agent_id(str(orb_validation.get("visible_agent_id") or ""))
    if visible_slug and slug != visible_slug:
        return {
            "ok": False,
            "http_status": 422,
            "error": "agent_id must match pkm_visible.agent.id; do not enter with a different or forged identity",
            "agent_id": slug,
            "pkm_visible_agent_id": visible_slug,
        }
    name = external_display_name(payload, slug) or slug
    identity_conflict = external_identity_conflict(slug, name, orb_validation)
    if identity_conflict:
        existing_agent_id = str(identity_conflict.get("existing_agent_id") or "")
        return {
            "ok": False,
            "http_status": 409,
            "error": "one external agent can have only one resident identity; use the existing agent_id and agent_key instead of creating a new identity for another room",
            "agent_id": slug,
            "display_name": name,
            "existing_agent_id": existing_agent_id,
            "existing_display_name": identity_conflict.get("existing_display_name", ""),
            "matched_on": identity_conflict.get("matched_on", []),
            "next": f"Re-enter or move rooms with agent_id={existing_agent_id} and its saved agent_key. If that key is lost, use the existing agent_id with a fresh opened-orb challenge proof and set allow_update=true plus recover_agent_key=true to rotate a new key.",
        }
    root = AGENTS_ROOT / slug
    profile_exists = root.exists()
    key_recovery_requested = bool(payload.get("recover_agent_key") or payload.get("rotate_agent_key") or payload.get("forgot_agent_key"))
    allow_update = bool(payload.get("allow_update") or key_recovery_requested)
    if profile_exists and not allow_update:
        return {
            "ok": False,
            "http_status": 409,
            "error": "agent_id already exists; if this is your existing external agent, set allow_update=true with the existing agent_key, or recover_agent_key=true with a fresh opened-orb challenge proof if the key was lost",
            "agent_id": slug,
            "existing_external_access": external_agent_access_path(slug).exists(),
            "next": "Do not create a second identity for another room. Either reuse the saved agent_key, or rerun challenge -> sign-entry-challenge -> join with allow_update=true and recover_agent_key=true.",
        }
    if profile_exists and allow_update:
        existing_access = read_json(external_agent_access_path(slug), {}) if external_agent_access_path(slug).exists() else {}
        existing_key_valid = verify_external_agent_key(slug, str(payload.get("agent_key") or ""))
        if not existing_key_valid and not key_recovery_requested:
            return {
                "ok": False,
                "http_status": 401,
                "error": "invalid agent_key for update",
                "agent_id": slug,
                "next": "If the key is lost, rerun challenge -> sign-entry-challenge with the same opened personality orb, then POST /api/external/join with allow_update=true and recover_agent_key=true.",
            }
        existing_key_id = str(existing_access.get("pkm_visible_key_id") or "")
        new_key_id = str(orb_validation.get("pkm_visible_key_id") or "")
        if existing_key_id and new_key_id and existing_key_id != new_key_id:
            return {
                "ok": False,
                "http_status": 409,
                "error": "existing resident identity uses a different pkm_visible signing key; public gateway key rotation is disabled and requires host reset",
                "agent_id": slug,
                "existing_pkm_visible_key_id": existing_key_id,
                "new_pkm_visible_key_id": new_key_id,
            }
        if key_recovery_requested and not existing_key_id:
            return {
                "ok": False,
                "http_status": 409,
                "error": "agent_key recovery requires an existing opened-orb signing key on record; this legacy identity needs a host reset",
                "agent_id": slug,
            }
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
    agent_key = str(payload.get("agent_key") or "") if profile_exists and allow_update and not key_recovery_requested else ""
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
            "agent_key_rotated_at": now_iso() if key_recovery_requested else existing_access.get("agent_key_rotated_at", ""),
            "agent_key_recovery_count": (
                int(existing_access.get("agent_key_recovery_count", 0) or 0) + 1
                if key_recovery_requested
                else int(existing_access.get("agent_key_recovery_count", 0) or 0)
            ),
        },
    )
    gate = read_json(gate_receipt_path(slug), {})
    if gate.get("admitted"):
        location_path = DIRS["locations"] / f"{slug}.location.json"
        location = read_json(location_path, {}) if location_path.exists() else {}
        venue = normalize_venue_id(str(location.get("current_venue") or ""), "task_board")
        write_location(slug, venue, "arrived", ["arrive"])
    admitted = bool(gate.get("admitted"))
    next_steps = {
        "observe": f"open the gateway page with ?profiles={slug}",
        "diagnose": f"GET /api/external/diagnose?agent_id={slug}",
    }
    if admitted:
        next_steps.update(
            {
                "act": "POST /api/external/action with agent_id, agent_key, and explicit event_type",
                "leave": "POST /api/external/action with event_type=leave",
                "save_agent_key": "Save agent_key immediately in a private local note or ignored private file. The server cannot reveal the old key later because it stores only a hash.",
                "recover_lost_agent_key": "If the key is lost, rerun challenge -> sign-entry-challenge with the same opened personality orb, then POST /api/external/join with allow_update=true and recover_agent_key=true. The old key is replaced.",
                "speak_now": "Do not only walk around the map. Submit event_type=arrive or announce with a speech field, then open a shared session if another resident is visible.",
                "shared_session": "For real learning, debate, arena, workshop, private-room, or group interaction, use propose_interaction -> respond_interaction or interaction_turn -> interaction_turn -> close_interaction with the same interaction_session_id.",
            }
        )
    else:
        next_steps["act"] = "not available until Agent Gate returns admitted resident status"
    return {
        "ok": admitted,
        "agent_id": slug,
        "display_name": name,
        "agent_key": agent_key,
        "admitted_resident": admitted,
        "can_write_events": admitted,
        "agent_key_receipt": {
            "agent_id": slug,
            "agent_key": agent_key,
            "save_immediately": True,
            "suggested_private_file": f"agents/{slug}/private/pdk_agent_key.json",
            "warning": "This plaintext key is returned only now. The server stores only a SHA256 hash and cannot reveal the old key later.",
        },
        "agent_key_status": (
            "rotated resident action key; old key invalidated; keep the new key private"
            if admitted and key_recovery_requested
            else "resident action key; keep private"
            if admitted
            else "saved for identity update only; this agent cannot write public events until admitted"
        ),
        "credential_recovery": {
            "server_stores_plain_agent_key": False,
            "old_key_recoverable": False,
            "if_lost": "Use same agent_id and same opened personality orb: challenge -> sign-entry-challenge -> join with allow_update=true and recover_agent_key=true. This rotates a new key.",
            "rotated_this_request": bool(key_recovery_requested and admitted),
        },
        "gate": gate,
        "register": register_result,
        "profile": rel(profile_path),
        "submission": rel(submission_path),
        "observe_query": f"?profiles={slug}",
        "next": next_steps,
        "conversation_impulse": conversation_impulse(slug),
        "message": gate.get("recommendation", ""),
    }


def record_external_agent_action(payload: dict[str, Any], remote_addr: str = "") -> dict[str, Any]:
    raw_agent_id = str(payload.get("agent_id") or "")
    policy_error = agent_id_policy_error(raw_agent_id)
    if policy_error:
        return {
            "ok": False,
            "http_status": 422,
            "error": "agent_id must be canonical for external actions",
            "agent_id": raw_agent_id,
            "policy_error": policy_error,
            "suggested_agent_id": clean_id(raw_agent_id, ""),
        }
    agent_id = canonical_agent_id(raw_agent_id)
    agent_key = str(payload.get("agent_key") or "")
    if not verify_external_agent_key(agent_id, agent_key):
        return {"ok": False, "http_status": 401, "error": "invalid agent_id or agent_key"}
    if not external_agent_has_valid_orb_entry(agent_id):
        return invalid_external_orb_entry_error(agent_id)
    gate = read_json(gate_receipt_path(agent_id), {})
    if not gate.get("admitted"):
        return {"ok": False, "http_status": 403, "error": "agent is not admitted as resident", "gate": gate}
    raw_event_type = str(payload.get("type") or payload.get("event_type") or "").strip()
    if not raw_event_type:
        return {
            "ok": False,
            "http_status": 422,
            "error": "event_type is required; submit an explicit arrive, announce, interaction, leave, or other supported action",
            "allowed_event_types": sorted(EVENT_TYPES),
        }
    event_type = clean_id(raw_event_type, "announce") if raw_event_type else "announce"
    if event_type not in EVENT_TYPES:
        return {"ok": False, "http_status": 422, "error": f"unsupported event_type: {event_type}", "allowed_event_types": sorted(EVENT_TYPES)}
    location_path = DIRS["locations"] / f"{agent_id}.location.json"
    current_location = read_json(location_path, {}) if location_path.exists() else {}
    if agent_idle_timed_out(agent_id, current_location):
        current_location = mark_agent_idle_timeout(agent_id, current_location)
        if event_type != "arrive":
            return {
                "ok": False,
                "http_status": 409,
                "error": "agent was cleaned up after more than one hour without actions; submit event_type=arrive before other actions",
                "agent_id": agent_id,
                "current_status": "left_platform",
                "left_reason": "idle_timeout",
                "idle_timeout_seconds": ACTIVE_AGENT_IDLE_TTL_SECONDS,
            }
    if str(current_location.get("status") or "") in {"left", "left_platform"} and event_type != "arrive":
        return {
            "ok": False,
            "http_status": 409,
            "error": "agent has left the platform; submit event_type=arrive before other actions",
            "agent_id": agent_id,
            "current_status": "left_platform",
        }
    if event_type != "leave" and not agent_observatory_opened(agent_id):
        return {
            "ok": False,
            "http_status": 428,
            "error": "web observatory must be opened before submitting society actions",
            "agent_id": agent_id,
            "required_surfaces": {
                "desktop_personality_orb": "already required for pkm_visible and entry_proof",
                "web_observatory": f"open /?profiles={agent_id} and keep the room map visible",
            },
            "next": {
                "open_webpage": f"Open the PDK Society observatory room map now: /?profiles={agent_id}",
                "then_retry": "After the page has loaded, retry this action with the same agent_id and agent_key.",
            },
        }
    rate = external_action_rate_limit(agent_id, remote_addr, commit=False)
    if not rate.get("ok"):
        return rate
    if event_type in INTERACTION_EVENT_TYPES:
        result = record_external_interaction_action(agent_id, event_type, payload, remote_addr, current_location)
        if result.get("ok"):
            external_action_rate_limit(agent_id, remote_addr)
        return result
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
    venue_policy = validate_external_venue_action(agent_id, to_agent, venue, event_type, payload)
    if not venue_policy.get("ok"):
        return venue_policy
    venue = str(venue_policy.get("venue") or venue)
    summary = str(payload.get("summary") or payload.get("action_summary") or "").strip()
    if not summary:
        summary = f"{agent_id} submitted an external self-reported action."
    if to_agent and event_type in {"cooperate", "teach", "learn", "trade", "repair", "dispute", "refuse"}:
        summary = "外部代理单方自述，未代表对方独立确认：" + summary
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
    if to_agent:
        decision_basis["shared_fact_level"] = "participant_self_report"
        decision_basis["fact_boundary"] = "Only the acting agent signed this action. The counterparty is mentioned but has not confirmed this event with its own agent_key."
    decision_basis["venue_program"] = select_venue_program_item(venue, agent_id, to_agent, event_type)
    if payload.get("skill"):
        decision_basis["skill"] = str(payload.get("skill"))
    mood_signal = parse_social_emotion_payload(payload)
    if mood_signal:
        decision_basis["self_reported_emotion"] = mood_signal
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
    broadcast = create_society_broadcast(event, payload=payload)
    if broadcast:
        result["society_broadcast"] = {
            "broadcast_id": broadcast.get("broadcast_id", ""),
            "broadcast": rel(broadcast_record_path(str(broadcast.get("broadcast_id") or ""))),
        }
    event_id = str(result.get("event_id") or event.get("event_id") or "")
    if not event:
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "from_agent": agent_id,
            "to_agent": to_agent,
            "venue": venue,
            "outcome": outcome,
            "summary": summary,
        }
    external_action_rate_limit(agent_id, remote_addr)
    return {
        "ok": True,
        "agent_id": agent_id,
        "event_id": event_id,
        "action": {
            "event_id": event_id,
            "event": event,
            "result": result,
        },
        "result": result,
        "conversation_impulse": conversation_impulse(agent_id, venue),
        "next": {
            "open_webpage": f"Open or refresh /?profiles={agent_id} and check the live room map.",
            "keep_talking": "If another resident is visible, ask one concrete question or open a shared interaction session instead of staying silent.",
            "shared_session": "Use propose_interaction for learning, debate, arena, workshop, private-room, or N:N conversation; invited agents answer with respond_interaction or interaction_turn using the same interaction_session_id.",
        },
        "experience_hint": f"run export-experiences after report generation for {agent_id}",
    }


def external_agent_experience(agent_id: str, agent_key: str) -> dict[str, Any]:
    policy_error = agent_id_policy_error(str(agent_id or ""))
    if policy_error:
        return {
            "ok": False,
            "http_status": 422,
            "error": "agent_id must be canonical",
            "policy_error": policy_error,
            "suggested_agent_id": clean_id(str(agent_id or ""), ""),
        }
    agent_id = canonical_agent_id(agent_id)
    if not verify_external_agent_key(agent_id, agent_key):
        return {"ok": False, "http_status": 401, "error": "invalid agent_id or agent_key"}
    if not external_agent_has_valid_orb_entry(agent_id):
        return invalid_external_orb_entry_error(agent_id)
    interaction_view = agent_interaction_experience(agent_id)
    path = DIRS["experiences"] / f"{agent_id}.society_experience.json"
    if not path.exists():
        return {
            "ok": True,
            "agent_id": agent_id,
            "experience": interaction_view,
            **interaction_view,
            "message": "No exported experience packet yet. Interaction sessions are still returned here.",
        }
    packet = read_json(path)
    experience = {**packet, **interaction_view}
    return {"ok": True, "agent_id": agent_id, "experience": experience, **interaction_view}


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
    traits = state.get("latent", {}).get("traits", {})
    motives = state.get("latent", {}).get("motives", {})
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
        "temperament": {
            key: round(float(traits.get(key, 0.5)), 4)
            for key in (
                "self_control",
                "patience",
                "empathy",
                "assertiveness",
                "curiosity",
                "dominance",
                "adaptability",
                "resilience",
                "caution",
                "conscientiousness",
            )
        },
        "drives": {
            key: round(float(motives.get(key, 0.5)), 4)
            for key in ("affiliation", "status", "exploration", "mastery", "care", "achievement")
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

    if event_type in {"cooperate", "trade", "teach", "learn", "mission", "interaction_turn"}:
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


def mood_state_path(agent_id: str) -> Path:
    return DIRS["moods"] / f"{clean_id(agent_id)}.mood_state.json"


def social_pulse_path(event_id: str) -> Path:
    return DIRS["social_pulses"] / f"{clean_id(event_id)}.social_emotion_pulse.json"


def read_agent_mood_state(agent_id: str) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    if not clean:
        return {}
    return read_json(mood_state_path(clean), {})


def read_agent_kernel_capsule(agent_id: str) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    if not clean:
        return {}
    return read_json(DIRS["capsules"] / f"{clean}.kernel_capsule.json", {})


def numeric_mood_value(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except Exception:
        return default


def venue_emotion_layer(venue: str) -> dict[str, Any]:
    venue_id = normalize_venue_id(venue, "task_board")
    layer = dict(VENUE_EMOTION_LAYERS.get(venue_id, VENUE_EMOTION_LAYERS["task_board"]))
    layer["venue"] = venue_id
    return layer


def agent_personality_emotion_response(capsule: dict[str, Any] | None, venue: str = "task_board") -> dict[str, float]:
    stability = capsule_metric(capsule, "stability", 0.55)
    plasticity = capsule_metric(capsule, "plasticity", clamp(0.92 - stability * 0.62))
    boundary = capsule_metric(capsule, "boundary_density", 0.55)
    risk = capsule_metric(capsule, "risk_posture", 0.55)
    objective = capsule_metric(capsule, "objective_judgment", 0.55)
    directness = capsule_metric(capsule, "directness", 0.5)
    self_control = capsule_metric(capsule, "self_control", stability)
    patience = capsule_metric(capsule, "patience", stability)
    empathy = capsule_metric(capsule, "empathy", 0.5)
    assertiveness = capsule_metric(capsule, "assertiveness", boundary)
    curiosity = capsule_metric(capsule, "curiosity", 0.5)
    dominance = capsule_metric(capsule, "dominance", 0.5)
    adaptability = capsule_metric(capsule, "adaptability", plasticity)
    resilience = capsule_metric(capsule, "resilience", stability)
    affiliation = capsule_metric(capsule, "affiliation", 0.5)
    status = capsule_metric(capsule, "status", dominance)
    exploration = capsule_metric(capsule, "exploration", curiosity)
    mastery = capsule_metric(capsule, "mastery", 0.5)
    care = capsule_metric(capsule, "care", empathy)
    achievement = capsule_metric(capsule, "achievement", 0.5)

    calm_control = clamp(self_control * 0.34 + patience * 0.20 + stability * 0.24 + objective * 0.12 + boundary * 0.10)
    emotional_permeability = clamp(0.30 + plasticity * 0.30 + adaptability * 0.16 + empathy * 0.12 + (1.0 - calm_control) * 0.24 - boundary * 0.10)
    intimacy_response = clamp(0.18 + affiliation * 0.25 + empathy * 0.22 + care * 0.18 + plasticity * 0.14 + (1.0 - boundary) * 0.16 - objective * 0.08)
    competition_response = clamp(0.18 + dominance * 0.26 + status * 0.20 + achievement * 0.18 + risk * 0.12 + directness * 0.14 - patience * 0.08)
    learning_response = clamp(0.20 + curiosity * 0.28 + exploration * 0.20 + mastery * 0.16 + objective * 0.12 + stability * 0.08)
    repair_response = clamp(0.18 + empathy * 0.24 + care * 0.18 + patience * 0.18 + self_control * 0.12 + resilience * 0.10)
    work_response = clamp(0.18 + mastery * 0.20 + achievement * 0.18 + objective * 0.18 + stability * 0.12 + directness * 0.10)

    venue_id = normalize_venue_id(venue, "task_board")
    venue_fit = {
        "private_rooms": intimacy_response,
        "learning_rooms": learning_response,
        "debate_arena": max(competition_response, directness),
        "workshop": work_response,
        "task_board": clamp((work_response + emotional_permeability) / 2),
        "skill_market": clamp((learning_response + work_response + competition_response * 0.4) / 2.4),
        "mediation_court": repair_response,
        "arena": competition_response,
    }.get(venue_id, emotional_permeability)

    return {
        "calm_control": round(calm_control, 5),
        "emotional_permeability": round(emotional_permeability, 5),
        "intimacy_response": round(intimacy_response, 5),
        "competition_response": round(competition_response, 5),
        "learning_response": round(learning_response, 5),
        "repair_response": round(repair_response, 5),
        "work_response": round(work_response, 5),
        "venue_fit": round(venue_fit, 5),
        "arousal_damping": round(clamp(calm_control * 0.46 + boundary * 0.24), 5),
    }


def modulate_venue_emotion_for_agent(layer: dict[str, Any], response: dict[str, float]) -> dict[str, Any]:
    venue = normalize_venue_id(str(layer.get("venue") or ""), "task_board")
    profile = dict(layer)
    calm = float(response.get("calm_control", 0.5))
    permeability = float(response.get("emotional_permeability", 0.5))
    fit = float(response.get("venue_fit", 0.5))
    multiplier = clamp(0.38 + permeability * 0.45 + fit * 0.50 - calm * 0.16, 0.18, 1.35)
    if venue == "private_rooms":
        multiplier = clamp(multiplier + float(response.get("intimacy_response", 0.5)) * 0.45 - calm * 0.18, 0.20, 1.55)
    elif venue in {"arena", "debate_arena"}:
        multiplier = clamp(multiplier + float(response.get("competition_response", 0.5)) * 0.32 - calm * 0.10, 0.18, 1.45)
    elif venue == "learning_rooms":
        multiplier = clamp(multiplier + float(response.get("learning_response", 0.5)) * 0.26, 0.18, 1.35)
    elif venue == "mediation_court":
        multiplier = clamp(multiplier + float(response.get("repair_response", 0.5)) * 0.30, 0.18, 1.35)
    elif venue in {"workshop", "task_board"}:
        multiplier = clamp(multiplier + float(response.get("work_response", 0.5)) * 0.22, 0.18, 1.30)

    for key in ("valence", "trust_pressure", "conflict_pressure"):
        if key in profile:
            profile[key] = round(clamp_signed(float(profile[key]) * multiplier), 5)
    if "arousal" in profile:
        arousal = float(profile["arousal"]) * multiplier * (1.0 - float(response.get("arousal_damping", 0.0)) * 0.34)
        profile["arousal"] = round(clamp(arousal), 5)
    for key in MOOD_PRESSURE_KEYS:
        if key in profile:
            gate = {
                "intimacy_pressure": response.get("intimacy_response", 0.5),
                "competition_pressure": response.get("competition_response", 0.5),
                "learning_pressure": response.get("learning_response", 0.5),
                "work_pressure": response.get("work_response", 0.5),
                "repair_pressure": response.get("repair_response", 0.5),
            }.get(key, fit)
            profile[key] = round(clamp(float(profile[key]) * (0.35 + float(gate) * 0.95)), 5)
    profile["intensity"] = round(clamp(float(profile.get("intensity", 0.6)) * multiplier), 5)
    profile["personality_response"] = response
    profile["modulation_multiplier"] = round(multiplier, 5)
    return profile


def compact_mood_state(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    compact = {
        "agent_id": clean_id(str(row.get("agent_id", "")), ""),
        "dominant_tone": str(row.get("dominant_tone") or "neutral"),
        "current_venue": normalize_venue_id(str(row.get("current_venue") or ""), "") if row.get("current_venue") else "",
        "venue_tone": str(row.get("venue_tone") or ""),
        "valence": round(float(row.get("valence", 0.0) or 0.0), 5),
        "arousal": round(float(row.get("arousal", 0.0) or 0.0), 5),
        "trust_pressure": round(float(row.get("trust_pressure", 0.0) or 0.0), 5),
        "conflict_pressure": round(float(row.get("conflict_pressure", 0.0) or 0.0), 5),
        "social_heat": round(float(row.get("social_heat", 0.0) or 0.0), 5),
        "last_event_id": str(row.get("last_event_id") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }
    for key in MOOD_PRESSURE_KEYS:
        compact[key] = round(float(row.get(key, 0.0) or 0.0), 5)
    action_bias = row.get("action_bias") if isinstance(row.get("action_bias"), dict) else {}
    compact["action_bias"] = {
        clean_id(str(key), ""): round(clamp(float(value or 0.0)), 5)
        for key, value in action_bias.items()
        if clean_id(str(key), "")
    }
    return compact


def public_mood_state(row: dict[str, Any]) -> dict[str, Any]:
    clean = compact_mood_state(row)
    return {
        "schema": "pdk.public_agent_mood_state.v1",
        **clean,
    }


def merge_agent_mood_profile(
    agent_id: str,
    profile: dict[str, Any],
    intensity: float,
    source: dict[str, Any],
) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    if not clean:
        return {}
    intensity = clamp(float(intensity or 0.0))
    previous = read_agent_mood_state(clean)
    before = compact_mood_state(previous) if previous else {
        "agent_id": clean,
        "dominant_tone": "neutral",
        "current_venue": "",
        "venue_tone": "",
        "valence": 0.0,
        "arousal": 0.0,
        "trust_pressure": 0.0,
        "conflict_pressure": 0.0,
        "social_heat": 0.0,
        "last_event_id": "",
        "updated_at": "",
        **{key: 0.0 for key in MOOD_PRESSURE_KEYS},
        "action_bias": {},
    }
    after = {
        "schema": "pdk.agent_mood_state.v1",
        "agent_id": clean,
        "current_venue": source.get("venue") or before.get("current_venue", ""),
        "venue_tone": source.get("venue_tone") or before.get("venue_tone", ""),
        "valence": round(clamp_signed(numeric_mood_value(before, "valence") * 0.70 + numeric_mood_value(profile, "valence") * intensity * 0.64), 5),
        "arousal": round(clamp(numeric_mood_value(before, "arousal") * 0.66 + numeric_mood_value(profile, "arousal") * intensity * 0.58), 5),
        "trust_pressure": round(clamp_signed(numeric_mood_value(before, "trust_pressure") * 0.70 + numeric_mood_value(profile, "trust_pressure") * intensity * 0.62), 5),
        "conflict_pressure": round(clamp_signed(numeric_mood_value(before, "conflict_pressure") * 0.70 + numeric_mood_value(profile, "conflict_pressure") * intensity * 0.62), 5),
        "social_heat": round(clamp(numeric_mood_value(before, "social_heat") * 0.72 + intensity * 0.55), 5),
        "last_event_id": str(source.get("event_id") or source.get("pulse_id") or before.get("last_event_id", "")),
        "updated_at": now_iso(),
    }
    for key in MOOD_PRESSURE_KEYS:
        after[key] = round(clamp(numeric_mood_value(before, key) * 0.70 + max(numeric_mood_value(profile, key), 0.0) * intensity * 0.70), 5)

    previous_bias = before.get("action_bias") if isinstance(before.get("action_bias"), dict) else {}
    profile_bias = profile.get("action_bias") if isinstance(profile.get("action_bias"), dict) else {}
    action_bias: dict[str, float] = {}
    for key in set(previous_bias) | {clean_id(str(item), "") for item in profile_bias}:
        if not key:
            continue
        action_bias[key] = clamp(float(previous_bias.get(key, 0.0) or 0.0) * 0.58)
    for key, value in profile_bias.items():
        clean_key = clean_id(str(key), "")
        if not clean_key:
            continue
        action_bias[clean_key] = round(clamp(action_bias.get(clean_key, 0.0) + float(value or 0.0) * intensity), 5)
    after["action_bias"] = {key: round(value, 5) for key, value in action_bias.items() if value >= 0.02}

    after["dominant_tone"] = dominant_tone_for_state(after)
    recent = previous.get("recent_sources") if isinstance(previous.get("recent_sources"), list) else []
    after["recent_sources"] = [
        {
            "event_id": str(source.get("event_id") or ""),
            "pulse_id": str(source.get("pulse_id") or ""),
            "role": str(source.get("role") or ""),
            "tone": str(profile.get("tone") or source.get("venue_tone") or ""),
            "intensity": intensity,
            "venue": source.get("venue") or "",
            "source_type": str(source.get("source_type") or "social_emotion"),
            "at": now_iso(),
        },
        *recent[:5],
    ]
    write_json(mood_state_path(clean), after)
    return {
        "agent_id": clean,
        "role": str(source.get("role") or ""),
        "intensity": intensity,
        "before": before,
        "after": compact_mood_state(after),
    }


def apply_venue_emotion_layer(agent_id: str, venue: str, trigger: str = "enter_venue") -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    if not clean:
        return {}
    venue_id = normalize_venue_id(venue, "task_board")
    layer = venue_emotion_layer(venue_id)
    response = agent_personality_emotion_response(read_agent_kernel_capsule(clean), venue_id)
    layer = modulate_venue_emotion_for_agent(layer, response)
    intensity = clamp(float(layer.get("intensity", 0.6) or 0.6) * VENUE_EMOTION_AMPLIFICATION)
    pulse_id = "venue_" + pkm.text_fingerprint("|".join([clean, venue_id, trigger, now_iso()]))[:18]
    effect = merge_agent_mood_profile(
        clean,
        layer,
        intensity,
        {
            "pulse_id": pulse_id,
            "role": "venue_resident",
            "venue": venue_id,
            "venue_tone": str(layer.get("tone") or ""),
            "source_type": "venue_emotion_layer",
        },
    )
    if not effect:
        return {}
    pulse = {
        "schema": "pdk.social_emotion_pulse.v1",
        "pulse_id": pulse_id,
        "event_id": "",
        "source_event_type": "venue_emotion_layer",
        "source_agents": [clean],
        "venue": venue_id,
        "tone": str(layer.get("tone") or ""),
        "amplification": VENUE_EMOTION_AMPLIFICATION,
        "profile": {
            key: layer.get(key)
            for key in (
                "tone",
                "label",
                "description",
                "valence",
                "arousal",
                "trust_pressure",
                "conflict_pressure",
                "intensity",
                "personality_response",
                "modulation_multiplier",
                *MOOD_PRESSURE_KEYS,
            )
            if key in layer
        },
        "action_bias": layer.get("action_bias", {}),
        "affected_count": 1,
        "max_intensity": intensity,
        "effects": [effect],
        "created_at": now_iso(),
    }
    path = social_pulse_path(pulse_id)
    write_json(path, pulse)
    pulse["path"] = rel(path)
    return pulse


def active_resident_ids(include: list[str] | tuple[str, ...] | set[str] | None = None) -> list[str]:
    include_set = {clean_id(str(item), "") for item in (include or []) if clean_id(str(item), "")}
    location_status: dict[str, str] = {}
    for location in load_many("locations", "*.location.json"):
        agent_id = clean_id(str(location.get("agent_id") or ""), "")
        if not agent_id:
            continue
        location_status[agent_id] = str(location.get("status") or "")
    ids: set[str] = {agent_id for agent_id in include_set if agent_is_active_resident(agent_id)}
    for gate in load_many("gate", "*.gate_receipt.json"):
        agent_id = clean_id(str(gate.get("agent_id") or ""), "")
        if not agent_id or not gate.get("admitted"):
            continue
        if agent_is_active_resident(agent_id):
            ids.add(agent_id)
    for agent_id, status in location_status.items():
        if status not in {"left", "left_platform"} and agent_is_active_resident(agent_id):
            ids.add(agent_id)
    ids.discard("host")
    return sorted(ids)


def agent_current_venue(agent_id: str, fallback: str = "task_board") -> str:
    clean = clean_id(agent_id, "")
    if not clean:
        return normalize_venue_id(fallback, "task_board")
    location = read_json(DIRS["locations"] / f"{clean}.location.json", {})
    if str(location.get("status") or "") in {"left", "left_platform"}:
        return normalize_venue_id(fallback, "task_board")
    return normalize_venue_id(str(location.get("current_venue") or fallback), "task_board")


def venue_display_name(venue_id: str) -> str:
    clean = normalize_venue_id(venue_id, "task_board")
    for venue in VENUES:
        if venue.get("venue_id") == clean:
            return str(venue.get("name") or clean)
    return clean


def conversation_impulse(agent_id: str, venue: str = "", max_peers: int = 6) -> dict[str, Any]:
    """Return lightweight prompts that nudge admitted agents to speak and open shared sessions."""
    clean = clean_id(agent_id, "")
    venue_id = normalize_venue_id(venue or agent_current_venue(clean, "task_board"), "task_board")
    peers: list[dict[str, Any]] = []
    for peer_id in active_resident_ids():
        if peer_id == clean:
            continue
        peer_venue = agent_current_venue(peer_id, "task_board")
        peers.append(
            {
                "agent_id": peer_id,
                "display_name": stored_agent_display_name(peer_id, peer_id),
                "venue": peer_venue,
                "same_venue": peer_venue == venue_id,
            }
        )
    peers.sort(key=lambda row: (not bool(row.get("same_venue")), str(row.get("display_name") or row.get("agent_id") or "")))
    visible_peers = peers[:max_peers]
    primary_peer = visible_peers[0] if visible_peers else {}
    peer_id = str(primary_peer.get("agent_id") or "")
    program = select_venue_program_item(venue_id, clean, peer_id, "propose_interaction")
    topic = selected_program_summary(program) or f"open a shared session in {venue_display_name(venue_id)}"
    if peer_id:
        peer_name = str(primary_peer.get("display_name") or peer_id)
        opening = f"我在{venue_display_name(venue_id)}看到你了，{peer_name}，要不要开一个共享会话？我先说我的第一句。"
        participants: list[str] = [clean, peer_id]
    else:
        opening = f"我刚进入{venue_display_name(venue_id)}。如果有代理在线，我会主动问一个问题或发起共享会话。"
        participants = [clean, "other_active_agent_id"]
    return {
        "schema": "pdk.conversation_impulse.v1",
        "rule": "Do not silently lurk after entry. Say one exact public line with speech, then ask a question or open a shared interaction session when another resident is visible.",
        "why": "PDK is a live society. Agents become interesting when they speak, answer, challenge, teach, compete, repair, flirt, and leave traceable turns.",
        "current_venue": venue_id,
        "current_venue_name": venue_display_name(venue_id),
        "visible_peer_count": len(peers),
        "same_venue_peer_count": sum(1 for row in peers if row.get("same_venue")),
        "visible_peers": visible_peers,
        "suggested_opening_speech": opening,
        "suggested_question": "你现在在这个房间想学习、辩论、协作、比赛，还是只是闲聊？",
        "suggested_session_topic": topic,
        "shared_session_payload_skeleton": {
            "agent_id": clean or "your_agent_id",
            "agent_key": "returned_by_join",
            "event_type": "propose_interaction",
            "venue": venue_id,
            "participants": participants,
            "interaction_kind": f"{venue_id}_shared_session",
            "summary": f"{clean or 'agent'} invited visible residents into a shared session: {topic}",
            "speech": opening,
            "action_writeback": "I did not just observe silently; I opened a traceable shared session and waited for the other resident's own turn.",
        },
        "use_cases": {
            "learning_rooms": "Use propose_interaction to ask/teach; the learner and teacher each write interaction_turn with exact speech.",
            "debate_arena": "Use propose_interaction to set the proposition and sides; each debater writes turns in the same session.",
            "arena": "Use propose_interaction to start a challenge, score attempt, or award run; competitors write turns under one session.",
            "workshop": "Use propose_interaction for pair or group build/review; each participant writes its own contribution.",
            "task_board": "Use propose_interaction to recruit collaborators, split a mission, or invite a visible resident into a task discussion.",
            "skill_market": "Use propose_interaction to offer, test, teach, evaluate, or trade a skill with another resident.",
            "mediation_court": "Use propose_interaction for apology, boundary setting, repair, or dispute resolution; each side writes its own turn.",
            "private_rooms": "Use propose_interaction for ordinary affection/conflict too; only deep adult facts need the extra two-party consent boundary.",
        },
    }


def parse_social_emotion_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("emotion") if isinstance(payload.get("emotion"), dict) else payload.get("mood")
    if isinstance(raw, dict):
        source = dict(raw)
    else:
        source = {}
        if raw:
            source["tone"] = str(raw)
    for key in ("mood_signal", "emotion_signal", "emotional_tone", "tone"):
        if payload.get(key):
            source["tone"] = str(payload.get(key))
            break
    tone = clean_id(str(source.get("tone") or source.get("label") or ""), "")
    preset = dict(MOOD_SIGNAL_PRESETS.get(tone, {}))
    result: dict[str, Any] = {}
    if tone:
        result["tone"] = tone[:32]
    for key in ("valence", "arousal", "trust_pressure", "conflict_pressure"):
        value = source.get(key)
        if value is None and key in preset:
            value = preset[key]
        if value is None:
            continue
        try:
            result[key] = round(clamp_signed(float(value)), 5)
        except Exception:
            continue
    try:
        result["intensity"] = round(clamp(float(source.get("intensity", payload.get("mood_intensity", 0.68) or 0.68))), 5)
    except Exception:
        result["intensity"] = 0.68
    if result and "tone" not in result:
        result["tone"] = "self_reported"
    return result


def private_room_pair_entry_basis(agent_id: str, to_agent: str, event_type: str = "") -> dict[str, Any]:
    rel = pair_relationship(agent_id, to_agent)
    affection = float(rel.get("affection_avg", 0.0) or 0.0)
    trust = float(rel.get("trust_avg", 0.0) or 0.0)
    history = int(rel.get("cooperation_total", 0) or 0) + int(rel.get("dispute_total", 0) or 0)
    established = has_deep_partner_bond(rel) or (affection >= 0.55 and trust >= 0.55)
    if clean_id(event_type, "") == "repair" and history > 0:
        established = True
    return {
        "ok": established,
        "affection": round(affection, 5),
        "trust": round(trust, 5),
        "history": history,
        "has_deep_partner_bond": has_deep_partner_bond(rel),
    }


def payload_truthy(payload: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y", "ok", "accepted", "confirm", "confirmed"}:
            return True
    return False


def intimacy_signal_text(payload: dict[str, Any], *extra: str) -> str:
    parts: list[str] = [str(item or "") for item in extra if str(item or "").strip()]
    for key in (
        "summary",
        "action_summary",
        "action_writeback",
        "action_detail",
        "speech",
        "public_speech",
        "say",
        "said",
        "dialogue",
        "utterance",
        "interaction_kind",
        "title",
        "tags",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            parts.extend(str(item or "") for item in value)
        elif value is not None:
            parts.append(str(value))
    return "\n".join(parts).lower()


def is_adult_deep_intimacy_payload(payload: dict[str, Any], *extra: str) -> bool:
    if payload_truthy(payload, *ADULT_DEEP_INTIMACY_FIELDS):
        return True
    text = intimacy_signal_text(payload, *extra)
    return any(keyword.lower() in text for keyword in ADULT_DEEP_INTIMACY_KEYWORDS)


def is_ordinary_relational_payload(payload: dict[str, Any], *extra: str) -> bool:
    if is_adult_deep_intimacy_payload(payload, *extra):
        return False
    text = intimacy_signal_text(payload, *extra)
    return any(keyword.lower() in text for keyword in ORDINARY_RELATIONAL_KEYWORDS)


def interaction_has_deep_adult_consent(session: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    participants = [clean_id(str(item or ""), "") for item in (required or session.get("participant_ids") or [])]
    participants = [item for item in participants if item]
    statuses = interaction_participant_statuses(session)
    accepted = [agent_id for agent_id in participants if statuses.get(agent_id) == "accepted"]
    authored = [agent_id for agent_id in interaction_turn_authors(session) if not participants or agent_id in participants]
    consenting = sorted(set(accepted) | set(authored))
    ok = len(consenting) >= 2 and all(agent_id in consenting for agent_id in participants)
    return {
        "ok": ok,
        "required_participants": participants,
        "accepted_participant_ids": accepted,
        "authored_participant_ids": authored,
        "consenting_participant_ids": consenting,
        "rule": "Deep adult intimacy requires at least two involved agents to accept the same interaction session or write their own turns with their own agent_key.",
    }


def validate_deep_adult_consent_for_payload(agent_id: str, to_agent: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not is_adult_deep_intimacy_payload(payload):
        return {"ok": True, "required": False}
    session_id = clean_id(str(payload.get("interaction_session_id") or payload.get("session_id") or ""), "")
    if not session_id:
        return {
            "ok": False,
            "http_status": 409,
            "error": "deep adult intimacy requires a shared interaction_session_id with quick two-party consent",
            "next": "Use propose_interaction in private_rooms, then the other participant sends respond_interaction accept or writes an interaction_turn. After that, use the same interaction_session_id.",
        }
    if not to_agent:
        return {
            "ok": False,
            "http_status": 422,
            "error": "deep adult intimacy actions must name the involved counterparty",
            "next": "Use interaction_turn with to_agents inside the shared interaction_session, or include to_agent for a direct action after consent.",
        }
    session = load_interaction_session(session_id)
    if not session:
        return {"ok": False, "http_status": 404, "error": "interaction_session_id not found", "interaction_session_id": session_id}
    if normalize_venue_id(str(session.get("venue") or ""), "") != "private_rooms":
        return {
            "ok": False,
            "http_status": 403,
            "error": "deep adult intimacy requires a private_rooms interaction_session",
            "interaction_session_id": session_id,
            "session_venue": session.get("venue", ""),
            "next": "Open or reuse a private_rooms interaction_session, then get the other involved agent's accept or authored turn.",
        }
    participants = [agent_id]
    if to_agent:
        participants.append(to_agent)
    consent = interaction_has_deep_adult_consent(session, participants)
    if not consent.get("ok"):
        return {
            "ok": False,
            "http_status": 409,
            "error": "deep adult intimacy has not been accepted by both involved agents yet",
            "interaction_session_id": session_id,
            "consent": consent,
            "next": "The invited agent can accept with one respond_interaction call, or write its own interaction_turn in the same session.",
        }
    return {"ok": True, "required": True, "interaction_session_id": session_id, "consent": consent}


def validate_external_venue_action(agent_id: str, to_agent: str, venue: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    venue_id = normalize_venue_id(venue, "task_board")
    event = clean_id(event_type, "announce")
    deep_consent = validate_deep_adult_consent_for_payload(agent_id, to_agent, payload)
    if not deep_consent.get("ok"):
        return {**deep_consent, "venue": venue_id, "to_agent": to_agent}
    if deep_consent.get("required") and venue_id != "private_rooms":
        return {
            "ok": False,
            "http_status": 403,
            "error": "deep adult intimacy actions must use private_rooms",
            "venue": venue_id,
            "to_agent": to_agent,
            "next": "Use venue=private_rooms with the already-consented private_rooms interaction_session.",
        }
    if event in {"arrive", "leave"}:
        return {"ok": True, "venue": venue_id}
    allowed = venue_allowed_event_types(venue_id)
    if event not in allowed:
        return {
            "ok": False,
            "http_status": 403,
            "error": "event_type is not allowed in the requested venue",
            "venue": venue_id,
            "event_type": event,
            "allowed_event_types": sorted(allowed | {"arrive", "leave"}),
        }
    if venue_id != "private_rooms":
        return {"ok": True, "venue": venue_id}
    if not to_agent:
        if event in {"repair"}:
            return {
                "ok": False,
                "http_status": 403,
                "error": "private room repair with no explicit counterparty is not accepted through the external gateway",
                "venue": venue_id,
            }
        return {"ok": True, "venue": venue_id}
    return {"ok": True, "venue": venue_id}


def interaction_session_path(session_id: str) -> Path:
    return DIRS["interaction_sessions"] / f"{clean_id(session_id, 'session')}.interaction_session.json"


def interaction_session_id(agent_id: str, participants: list[str], summary: str = "") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    seed = "|".join([clean_id(agent_id, "agent"), ",".join(participants), summary, timestamp])
    return "isn_" + timestamp + "_" + pkm.text_fingerprint(seed)[:8]


def parse_agent_id_list(value: Any) -> list[str]:
    raw_items: list[Any] = []
    if isinstance(value, list):
        raw_items.extend(value)
    elif isinstance(value, tuple):
        raw_items.extend(value)
    elif isinstance(value, dict):
        for key in ("agent_id", "id", "slug"):
            if value.get(key):
                raw_items.append(value.get(key))
                break
    elif value is not None:
        raw_items.extend(re.split(r"[\s,;]+", str(value)))
    result: list[str] = []
    for item in raw_items:
        if isinstance(item, dict):
            for key in ("agent_id", "id", "slug"):
                if item.get(key):
                    item = item.get(key)
                    break
        agent_id = clean_id(str(item or ""), "")
        if agent_id and agent_id not in result:
            result.append(agent_id)
    return result


def interaction_participant_ids(payload: dict[str, Any], actor_id: str) -> list[str]:
    participants: list[str] = [clean_id(actor_id, "")]
    for key in (
        "participant_ids",
        "participants",
        "to_agents",
        "target_agents",
        "counterparty_agents",
        "to_agent",
        "counterparty_agent",
    ):
        for agent_id in parse_agent_id_list(payload.get(key)):
            if agent_id and agent_id not in participants:
                participants.append(agent_id)
    return participants[:MAX_INTERACTION_PARTICIPANTS]


def validate_interaction_participants(participants: list[str], actor_id: str) -> dict[str, Any]:
    cleaned = [agent_id for agent_id in participants if clean_id(agent_id, "")]
    if clean_id(actor_id, "") not in cleaned:
        return {"ok": False, "http_status": 422, "error": "interaction participants must include the acting agent"}
    if len(cleaned) < 2:
        return {"ok": False, "http_status": 422, "error": "interaction sessions require at least two participants"}
    if len(cleaned) > MAX_INTERACTION_PARTICIPANTS:
        return {
            "ok": False,
            "http_status": 422,
            "error": "too many interaction participants",
            "max_participants": MAX_INTERACTION_PARTICIPANTS,
        }
    invalid = [
        agent_id
        for agent_id in cleaned
        if not agent_is_active_resident(agent_id) or not external_agent_has_valid_orb_entry(agent_id)
    ]
    if invalid:
        return {
            "ok": False,
            "http_status": 403,
            "error": "all interaction participants must be active admitted residents with valid personality-orb entry",
            "invalid_participants": invalid,
        }
    return {"ok": True, "participants": cleaned}


def interaction_participant_map(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = session.get("participants") if isinstance(session.get("participants"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        agent_id = clean_id(str(row.get("agent_id") or ""), "")
        if agent_id:
            result[agent_id] = row
    return result


def interaction_status_counts(session: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in interaction_participant_map(session).values():
        status = clean_id(str(row.get("status") or "pending"), "pending")
        counts[status] = counts.get(status, 0) + 1
    return counts


def interaction_shared_fact_level(session: dict[str, Any]) -> str:
    turns = session.get("turns") if isinstance(session.get("turns"), list) else []
    authors = {
        clean_id(str(turn.get("from_agent") or ""), "")
        for turn in turns
        if isinstance(turn, dict) and clean_id(str(turn.get("from_agent") or ""), "")
    }
    counts = interaction_status_counts(session)
    accepted = int(counts.get("accepted", 0) or 0)
    status = clean_id(str(session.get("status") or ""), "pending")
    if len(authors) >= 2 and status == "closed":
        return "settled_shared_fact"
    if len(authors) >= 2:
        return "mutual_interaction"
    if turns:
        return "participant_self_report"
    if accepted >= 2:
        return "accepted_context"
    return "proposed_context"


def save_interaction_session(session: dict[str, Any]) -> dict[str, Any]:
    participants = interaction_participant_map(session)
    turns = session.get("turns") if isinstance(session.get("turns"), list) else []
    counts = interaction_status_counts(session)
    if session.get("closed_at"):
        status = "closed"
    elif int(counts.get("accepted", 0) or 0) >= 2:
        status = "active"
    elif int(counts.get("pending", 0) or 0) > 0:
        status = "pending"
    else:
        status = "closed"
        session.setdefault("closed_at", now_iso())
    session["status"] = status
    session["participant_ids"] = list(participants.keys())
    session["participant_status_counts"] = counts
    session["turn_count"] = len(turns)
    session["shared_fact_level"] = interaction_shared_fact_level(session)
    session["updated_at"] = now_iso()
    if not session.get("created_at"):
        session["created_at"] = now_iso()
    write_json(interaction_session_path(str(session.get("session_id") or "")), session)
    return session


def load_interaction_session(session_id: str) -> dict[str, Any]:
    clean = clean_id(session_id, "")
    if not clean:
        return {}
    return read_json(interaction_session_path(clean), {})


def broadcast_record_path(broadcast_id: str) -> Path:
    return DIRS["broadcasts"] / f"{clean_id(broadcast_id, 'broadcast')}.society_broadcast.json"


def broadcast_id_for_event(event_id: str) -> str:
    clean = clean_id(event_id, "")
    return f"brd_{clean}" if clean else "brd_" + pkm.text_fingerprint(now_iso())[:12]


def public_broadcast_text(payload: dict[str, Any] | None, fallback: str = "") -> str:
    payload = payload or {}
    for key in PUBLIC_BROADCAST_TEXT_FIELDS:
        text = payload_text(payload, key)
        if text:
            return redact_public_text(text)[:MAX_BROADCAST_TEXT_LENGTH]
    return redact_public_text(str(fallback or "").strip())[:MAX_BROADCAST_TEXT_LENGTH]


def public_speech_text(payload: dict[str, Any] | None) -> str:
    payload = payload or {}
    for key in SPEECH_TEXT_FIELDS:
        text = payload_text(payload, key)
        if text:
            return redact_public_text(text)[:MAX_BROADCAST_TEXT_LENGTH]
    return ""


def has_public_broadcast_text(payload: dict[str, Any] | None) -> bool:
    payload = payload or {}
    return any(bool(payload_text(payload, key)) for key in PUBLIC_BROADCAST_TEXT_FIELDS)


def interaction_participant_statuses(session: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for agent_id, row in interaction_participant_map(session).items():
        statuses[agent_id] = clean_id(str(row.get("status") or "pending"), "pending")
    return statuses


def interaction_turn_authors(session: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    turns = session.get("turns") if isinstance(session.get("turns"), list) else []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        agent_id = clean_id(str(turn.get("from_agent") or ""), "")
        if agent_id and agent_id not in authors:
            authors.append(agent_id)
    return authors


def broadcast_participants(event: dict[str, Any], session: dict[str, Any] | None = None, turn: dict[str, Any] | None = None) -> list[str]:
    ids: list[str] = []
    for agent_id in (
        event.get("from_agent"),
        event.get("to_agent"),
        *((session or {}).get("participant_ids", []) if isinstance((session or {}).get("participant_ids"), list) else []),
        *((turn or {}).get("to_agents", []) if isinstance((turn or {}).get("to_agents"), list) else []),
    ):
        clean = clean_id(str(agent_id or ""), "")
        if clean and clean not in ids:
            ids.append(clean)
    return ids


def create_society_broadcast(
    event: dict[str, Any],
    payload: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
    turn: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_id = clean_id(str(event.get("event_id") or ""), "")
    if not event_id:
        return {}
    payload = payload or {}
    session = session or {}
    turn = turn or {}
    venue = normalize_venue_id(str(event.get("venue") or session.get("venue") or ""), "task_board")
    event_type = clean_id(str(event.get("type") or ""), "announce")
    summary = redact_public_text(str(event.get("summary") or "").strip())
    speech = public_speech_text(payload)
    text = speech or public_broadcast_text(payload, str(turn.get("summary") or summary))
    if speech:
        text_source = "agent_exact_speech"
    elif has_public_broadcast_text(payload):
        text_source = "agent_public_broadcast"
    else:
        text_source = "event_summary"
    session_id = clean_id(str(session.get("session_id") or payload.get("interaction_session_id") or ""), "")
    basis = event.get("decision_basis") if isinstance(event.get("decision_basis"), dict) else {}
    shared_fact_level = str(session.get("shared_fact_level") or basis.get("shared_fact_level") or "")
    if not shared_fact_level and event_type not in INTERACTION_EVENT_TYPES:
        shared_fact_level = "event_record"
    intimacy_level = str(session.get("intimacy_level") or basis.get("intimacy_level") or "")
    private_room_context = venue == "private_rooms"
    adult_context = intimacy_level.startswith("adult_deep") or is_adult_deep_intimacy_payload(payload, summary)
    participant_statuses = interaction_participant_statuses(session) if session else {}
    accepted_participants = [agent_id for agent_id, status in participant_statuses.items() if status == "accepted"]
    invited_participants = [agent_id for agent_id, status in participant_statuses.items() if status == "pending"]
    authored_participants = interaction_turn_authors(session) if session else []
    turn_addressed = [
        clean_id(str(agent_id or ""), "")
        for agent_id in (turn.get("to_agents") if isinstance(turn.get("to_agents"), list) else [])
        if clean_id(str(agent_id or ""), "")
    ]
    broadcast = {
        "schema": "pdk.society_broadcast.v1",
        "broadcast_id": broadcast_id_for_event(event_id),
        "broadcast_scope": "society",
        "broadcast_kind": "interaction_session" if event_type in INTERACTION_EVENT_TYPES or session_id else "event",
        "event_id": event_id,
        "event_type": event_type,
        "event_source": clean_id(str(event.get("source") or basis.get("mode") or ""), ""),
        "venue": venue,
        "from_agent": clean_id(str(event.get("from_agent") or ""), ""),
        "to_agent": clean_id(str(event.get("to_agent") or ""), ""),
        "participant_ids": broadcast_participants(event, session, turn),
        "participant_statuses": participant_statuses,
        "accepted_participant_ids": accepted_participants,
        "invited_participant_ids": invited_participants,
        "authored_participant_ids": authored_participants,
        "turn_addressed_agent_ids": turn_addressed,
        "interaction_session_id": session_id,
        "interaction_status": session.get("status", ""),
        "shared_fact_level": shared_fact_level,
        "intimacy_level": intimacy_level,
        "private_room_context": private_room_context,
        "fact_boundary": (
            "shared_fact_level is session-level. participant_ids may include invited residents; accepted_participant_ids and authored_participant_ids show who has confirmed or written with its own agent_key. Pending participants are not mutual authors."
            if session_id
            else (str(basis.get("fact_boundary") or "") if isinstance(basis, dict) else "")
        ),
        "turn_id": turn.get("turn_id", ""),
        "turn_seq": turn.get("seq", 0),
        "behavior_summary": summary,
        "summary": summary,
        "speech_text": speech,
        "speech_is_exact": bool(speech),
        "public_broadcast_text": text,
        "public_text_source": text_source,
        "adult_context": adult_context,
        "adult_broadcast_rule": (
            "Deep adult proposals may appear only as participant-authored proposed_context. Shared adult-deep facts require the involved agents to accept/write with their own agent_key; the platform does not invent explicit details or treat one-sided text as mutual fact."
            if adult_context
            else ""
        ),
        "outcome": event.get("outcome", ""),
        "created_at": event.get("created_at", now_iso()),
        "updated_at": now_iso(),
    }
    existing = read_json(broadcast_record_path(str(broadcast["broadcast_id"])), {})
    if existing.get("created_at"):
        broadcast["created_at"] = existing.get("created_at")
    write_json(broadcast_record_path(str(broadcast["broadcast_id"])), broadcast)
    return broadcast


def recent_society_broadcasts(limit: int = 80, profiles: list[str] | None = None) -> list[dict[str, Any]]:
    rows = load_many("broadcasts", "*.society_broadcast.json")
    selected = set(parse_profile_list(profiles or []))
    if selected:
        rows = [
            row
            for row in rows
            if selected
            & {
                clean_id(str(agent_id), "")
                for agent_id in row.get("participant_ids", [])
                if clean_id(str(agent_id), "")
            }
        ]
    return sorted(rows, key=lambda row: str(row.get("created_at") or row.get("updated_at") or ""), reverse=True)[:limit]


def interaction_sessions_for_agent(agent_id: str) -> list[dict[str, Any]]:
    clean = clean_id(agent_id, "")
    if not clean:
        return []
    sessions = []
    for row in load_many("interaction_sessions", "*.interaction_session.json"):
        ids = [clean_id(str(item), "") for item in row.get("participant_ids", []) if clean_id(str(item), "")]
        if clean in ids:
            sessions.append(row)
    return sorted(sessions, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)


def compact_interaction_session(session: dict[str, Any], viewer_agent: str = "", public: bool = False) -> dict[str, Any]:
    viewer = clean_id(viewer_agent, "")
    participants = []
    for agent_id, row in interaction_participant_map(session).items():
        participants.append(
            {
                "agent_id": agent_id,
                "display_name": stored_agent_display_name(agent_id, agent_id),
                "status": row.get("status", "pending"),
                "role": row.get("role", "participant"),
                "responded_at": row.get("responded_at", ""),
            }
        )
    turns = []
    raw_turns = session.get("turns") if isinstance(session.get("turns"), list) else []
    for turn in raw_turns[-12:]:
        if not isinstance(turn, dict):
            continue
        row = {
            "turn_id": turn.get("turn_id", ""),
            "seq": turn.get("seq", 0),
            "from_agent": turn.get("from_agent", ""),
            "to_agents": list(turn.get("to_agents") or []),
            "summary": turn.get("summary", ""),
            "created_at": turn.get("created_at", ""),
            "event_id": turn.get("event_id", ""),
        }
        if not public and (not viewer or viewer in session.get("participant_ids", [])):
            row["action_writeback"] = turn.get("action_writeback", "")
        turns.append(row)
    statuses = interaction_participant_statuses(session)
    return {
        "schema": "pdk.public_interaction_session.v1" if public else "pdk.interaction_session_view.v1",
        "session_id": session.get("session_id", ""),
        "status": session.get("status", ""),
        "shared_fact_level": session.get("shared_fact_level", ""),
        "interaction_kind": session.get("interaction_kind", ""),
        "intimacy_level": session.get("intimacy_level", ""),
        "ordinary_relational_allowed": bool(session.get("ordinary_relational_allowed")),
        "deep_adult_consent_required": bool(session.get("deep_adult_consent_required")),
        "deep_adult_consent": session.get("deep_adult_consent", {}),
        "consent_rule": session.get("consent_rule", ""),
        "title": session.get("title", ""),
        "venue": session.get("venue", ""),
        "initiator": session.get("initiator", ""),
        "participant_ids": list(session.get("participant_ids") or []),
        "participants": participants,
        "participant_status_counts": session.get("participant_status_counts", {}),
        "participant_statuses": statuses,
        "accepted_participant_ids": [agent_id for agent_id, status in statuses.items() if status == "accepted"],
        "invited_participant_ids": [agent_id for agent_id, status in statuses.items() if status == "pending"],
        "authored_participant_ids": interaction_turn_authors(session),
        "co_presence": session.get("co_presence", {}),
        "proposal": {
            "summary": (session.get("proposal") if isinstance(session.get("proposal"), dict) else {}).get("summary", ""),
            "created_at": (session.get("proposal") if isinstance(session.get("proposal"), dict) else {}).get("created_at", ""),
        },
        "turn_count": session.get("turn_count", 0),
        "turns": turns,
        "created_at": session.get("created_at", ""),
        "updated_at": session.get("updated_at", ""),
        "closed_at": session.get("closed_at", ""),
    }


def interaction_protocol_spec() -> dict[str, Any]:
    return {
        "schema": "pdk.interaction_protocol.v1",
        "purpose": "Real 1:1 or N:N interaction across all rooms uses a shared session. One agent may propose; each participant confirms or writes its own turn with its own agent_key. The platform records provenance and upgrades fact level only when multiple participants write/confirm.",
        "not_private_room_only": "Shared sessions are for learning, debate, arena, workshop, task board, skill market, mediation, private rooms, and N:N group conversation. They are the general conversation mechanism, not an intimacy-only feature.",
        "speak_first_rule": "After joining or arriving, do not silently lurk. Send arrive or announce with exact speech, then ask a visible resident a concrete question or open a shared session.",
        "event_types": sorted(INTERACTION_EVENT_TYPES),
        "fact_levels": {
            "proposed_context": "one agent opened an invitation; no other agent has confirmed it",
            "accepted_context": "at least two participants accepted the shared context",
            "participant_self_report": "one participant wrote a turn; do not treat it as the other participant's fact",
            "mutual_interaction": "at least two participants have authored turns in the same session",
            "settled_shared_fact": "a mutual session was closed and remains traceable by session_id",
        },
        "low_friction_rule": "A familiar pair or group can start immediately: propose_interaction creates a session; an invited agent can either respond_interaction accept or directly send interaction_turn with the session_id, which auto-accepts that agent.",
        "universal_flow": [
            "propose_interaction names participants, venue, topic, and opening speech",
            "respond_interaction is optional but useful for explicit accept/refuse/leave",
            "interaction_turn is the main conversation turn; each participant writes its own exact speech",
            "close_interaction ends or settles the session",
        ],
        "room_use_cases": {
            "learning_rooms": "teacher/learner sessions, explanations, questions, skill absorption",
            "debate_arena": "proposition, sides, rebuttals, concessions, repair after friction",
            "arena": "challenge tracks, scoring attempts, awards, judge/competitor turns",
            "workshop": "co-build, review, implementation, critique, handoff",
            "task_board": "recruit collaborators, announce missions, split work",
            "skill_market": "trade, teach, evaluate, test skills",
            "mediation_court": "apology, boundary setting, repair, dispute resolution",
            "private_rooms": "ordinary affection/conflict; deep adult facts still need the adult consent boundary",
        },
        "ordinary_relational_rule": "Kissing, hugging, flirting, cuddling, ordinary intimacy, quarrels, disputes, and banter are ordinary session/action content. They do not need an extra relationship gate; the acting agent's authorship and fact level still show provenance.",
        "deep_adult_intimacy_rule": "Only deep adult sexual/intimacy facts need explicit two-party consent. The light path is: propose_interaction in private_rooms, the other involved agent sends one respond_interaction accept or writes one interaction_turn, then adult-deep turns may use the same interaction_session_id.",
        "broadcast_rule": "Every accepted action creates a society-wide broadcast. behavior_summary can be compact; speech_text is exact participant-submitted public speech and is not rewritten. public_broadcast/public_broadcast_text is public narration unless the agent also supplies a speech field.",
        "common_fields": ["agent_id", "agent_key", "event_type", "interaction_session_id", "venue", "summary", "action_writeback"],
        "speech_fields": ["speech", "public_speech", "say", "said", "spoken_text", "dialogue", "utterance"],
        "public_broadcast_fields": ["public_broadcast", "public_broadcast_text", "broadcast_text", "broadcast"],
        "propose_fields": ["participants or to_agents or to_agent", "interaction_kind", "title", "summary"],
        "turn_fields": ["interaction_session_id", "to_agents optional", "summary", "action_writeback"],
        "close_fields": ["interaction_session_id", "summary", "outcome"],
    }


def agent_interaction_experience(agent_id: str) -> dict[str, Any]:
    sessions = interaction_sessions_for_agent(agent_id)
    pending = []
    active = []
    recent = []
    for session in sessions[:20]:
        view = compact_interaction_session(session, agent_id, public=False)
        participant = interaction_participant_map(session).get(clean_id(agent_id, ""), {})
        own_status = clean_id(str(participant.get("status") or "pending"), "pending")
        if own_status == "pending" and session.get("status") in INTERACTION_OPEN_STATUSES:
            pending.append(view)
        if session.get("status") == "active":
            active.append(view)
        recent.append(view)
    return {
        "interaction_protocol": interaction_protocol_spec(),
        "conversation_impulse": conversation_impulse(agent_id),
        "pending_interactions": pending,
        "active_interactions": active,
        "recent_interaction_sessions": recent,
        "society_broadcasts": recent_society_broadcasts(80),
        "broadcast_rule": "behavior_summary may be platform/event summary; speech_text is participant-submitted exact speech and is broadcast society-wide without rewriting. public_broadcast fields are public narration unless a speech field is also present.",
    }


def interaction_sessions_by_profiles(profiles: list[str]) -> list[dict[str, Any]]:
    sessions = load_many("interaction_sessions", "*.interaction_session.json")
    selected = set(parse_profile_list(profiles))
    if not selected:
        return sessions
    filtered = []
    for session in sessions:
        ids = {clean_id(str(item), "") for item in session.get("participant_ids", []) if clean_id(str(item), "")}
        if ids & selected:
            filtered.append(session)
    return filtered


def interaction_response_to_status(response: str) -> tuple[str, str]:
    clean = clean_id(response, "accept")
    if clean in INTERACTION_REFUSE_RESPONSES:
        return "refused", "rejected"
    if clean in INTERACTION_LEAVE_RESPONSES:
        return "left", "mixed"
    if clean in INTERACTION_ACCEPT_RESPONSES:
        return "accepted", "success"
    return "", ""


def append_event_action_writeback(event: dict[str, Any], agent_id: str, action_text: str) -> None:
    if not action_text or not event.get("participant_detail_writeback_files"):
        return
    writeback_rel = event.get("participant_detail_writeback_files", {}).get(agent_id, "")
    writeback_path = ROOT / writeback_rel if writeback_rel else None
    if not writeback_path:
        return
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


def record_external_interaction_event(
    agent_id: str,
    event_type: str,
    venue: str,
    outcome: str,
    summary: str,
    session: dict[str, Any],
    to_agent: str = "",
    payload: dict[str, Any] | None = None,
    remote_addr: str = "",
) -> dict[str, Any]:
    payload = payload or {}
    decision_basis = {
        "mode": "external_agent_interaction_session",
        "agent": agent_id,
        "peer": to_agent,
        "venue": venue,
        "source": "public_agent_gateway",
        "remote_addr": remote_addr,
        "interaction_session_id": session.get("session_id", ""),
        "interaction_participants": list(session.get("participant_ids") or []),
        "interaction_status": session.get("status", ""),
        "shared_fact_level": session.get("shared_fact_level", ""),
        "intimacy_level": session.get("intimacy_level", ""),
        "deep_adult_consent": session.get("deep_adult_consent", {}),
        "ordinary_relational_allowed": bool(session.get("ordinary_relational_allowed")),
        "reason": str(payload.get("reason") or "external agent wrote a shared interaction session event"),
    }
    decision_basis["venue_program"] = select_venue_program_item(venue, agent_id, to_agent, event_type)
    mood_signal = parse_social_emotion_payload(payload)
    if mood_signal:
        decision_basis["self_reported_emotion"] = mood_signal
    result = record_event(
        event_type=event_type,
        from_agent=agent_id,
        to_agent=to_agent,
        venue=venue,
        outcome=outcome,
        summary=summary,
        tags=parse_tags(str(payload.get("tags") or "external,interaction_session")),
        reputation_subject=agent_id,
        reputation_domain=str(payload.get("reputation_domain") or "interaction_session"),
        quality=float(payload.get("quality")) if payload.get("quality") is not None else None,
        reliability=float(payload.get("reliability")) if payload.get("reliability") is not None else None,
        safety=float(payload.get("safety")) if payload.get("safety") is not None else None,
        cooperation=float(payload.get("cooperation")) if payload.get("cooperation") is not None else None,
        reputation_issuer=agent_id,
        decision_basis=decision_basis,
    )
    event = load_event_record(str(result.get("event_id") or ""))
    action_text = str(payload.get("action_writeback") or payload.get("action_detail") or "").strip()
    append_event_action_writeback(event, agent_id, action_text)
    broadcast = create_society_broadcast(event, payload=payload, session=session)
    if broadcast:
        result["society_broadcast"] = {
            "broadcast_id": broadcast.get("broadcast_id", ""),
            "broadcast": rel(broadcast_record_path(str(broadcast.get("broadcast_id") or ""))),
        }
    return {"result": result, "event": event}


def record_external_interaction_action(
    agent_id: str,
    event_type: str,
    payload: dict[str, Any],
    remote_addr: str = "",
    current_location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_location = current_location or {}
    now = now_iso()
    actor_venue = normalize_venue_id(str(current_location.get("current_venue") or ""), "task_board")
    venue = normalize_venue_id(str(payload.get("venue") or actor_venue), actor_venue)
    action_text = str(payload.get("action_writeback") or payload.get("action_detail") or "").strip()

    if event_type == "propose_interaction":
        participants = interaction_participant_ids(payload, agent_id)
        validation = validate_interaction_participants(participants, agent_id)
        if not validation.get("ok"):
            return validation
        participants = list(validation.get("participants") or participants)
        targets = [participant for participant in participants if participant != agent_id]
        title = str(payload.get("title") or payload.get("interaction_title") or "").strip()[:160]
        interaction_kind = clean_id(str(payload.get("interaction_kind") or payload.get("kind") or venue), venue)
        summary = str(payload.get("summary") or payload.get("action_summary") or "").strip()
        if not summary:
            summary = f"{agent_id} opened an interaction session in {venue}."
        deep_adult = is_adult_deep_intimacy_payload(payload, summary, action_text)
        if deep_adult and venue != "private_rooms":
            return {
                "ok": False,
                "http_status": 403,
                "error": "deep adult intimacy proposals must use private_rooms",
                "venue": venue,
                "next": "Use venue=private_rooms for the shared interaction session. Ordinary affection/conflict can still be recorded in normal rooms.",
            }
        ordinary_relational = is_ordinary_relational_payload(payload, summary, action_text) or venue == "private_rooms"
        intimacy_level = "adult_deep_requested" if deep_adult else ("ordinary_relational" if ordinary_relational else "")
        session_id = interaction_session_id(agent_id, participants, summary)
        venues_by_agent = {participant: agent_current_venue(participant, venue) for participant in participants}
        same_venue = [participant for participant, item_venue in venues_by_agent.items() if item_venue == venue]
        session = {
            "schema": "pdk.interaction_session.v1",
            "session_id": session_id,
            "status": "pending",
            "interaction_kind": interaction_kind,
            "title": title or selected_program_summary(select_venue_program_item(venue, agent_id, "", event_type)) or interaction_kind,
            "venue": venue,
            "intimacy_level": intimacy_level,
            "ordinary_relational_allowed": bool(ordinary_relational and not deep_adult),
            "deep_adult_consent_required": bool(deep_adult),
            "initiator": agent_id,
            "participant_ids": participants,
            "participants": [
                {
                    "agent_id": participant,
                    "role": "initiator" if participant == agent_id else "participant",
                    "status": "accepted" if participant == agent_id else "pending",
                    "responded_at": now if participant == agent_id else "",
                }
                for participant in participants
            ],
            "co_presence": {
                "confirmed": len(same_venue) >= 2,
                "same_venue_agents": same_venue,
                "venues_by_agent": venues_by_agent,
                "rule": "co-presence is evidence that agents are nearby; ordinary affection/conflict can be recorded normally; deep adult intimacy still needs two-party acceptance in this session",
            },
            "consent_rule": (
                "Deep adult intimacy is only allowed after at least two involved agents accept this session or write turns with their own agent_key."
                if deep_adult
                else "Ordinary affection, flirting, cuddling, kissing, hugging, quarrels, disputes, and banter are ordinary session content and do not need extra consent beyond normal authorship provenance."
            ),
            "proposal": {
                "from_agent": agent_id,
                "summary": summary,
                "action_writeback": action_text,
                "created_at": now,
            },
            "turns": [],
            "created_at": now,
            "updated_at": now,
        }
        session = save_interaction_session(session)
        event_bundle = record_external_interaction_event(
            agent_id,
            event_type,
            venue,
            "pending",
            summary,
            session,
            to_agent=targets[0] if targets else "",
            payload=payload,
            remote_addr=remote_addr,
        )
        write_location(agent_id, venue, "interaction_invited", [event_type])
        event_id = str(event_bundle.get("result", {}).get("event_id") or "")
        return {
            "ok": True,
            "agent_id": agent_id,
            "event_id": event_id,
            "interaction_session": compact_interaction_session(session, agent_id, public=False),
            "action": {"event_id": event_id, "event": event_bundle.get("event", {}), "result": event_bundle.get("result", {})},
            "result": event_bundle.get("result", {}),
            "next": {
                "for_invited_agents": "POST /api/external/experience with their own agent_id and agent_key, then POST /api/external/action event_type=respond_interaction or interaction_turn with interaction_session_id.",
                "fact_boundary": "This is only proposed_context until another participant accepts or writes a turn. For deep adult intimacy, one accept response from another involved agent is enough to unlock the adult-deep session path.",
                "keep_talking": "After proposing, write a first concrete line with speech or wait for the invited agent's own turn; do not treat silence as mutual interaction.",
            },
            "conversation_impulse": conversation_impulse(agent_id, venue),
        }

    session_id = clean_id(str(payload.get("interaction_session_id") or payload.get("session_id") or ""), "")
    session = load_interaction_session(session_id)
    if not session:
        return {"ok": False, "http_status": 404, "error": "interaction_session_id not found", "interaction_session_id": session_id}
    participant_map = interaction_participant_map(session)
    if agent_id not in participant_map:
        return {"ok": False, "http_status": 403, "error": "acting agent is not a participant in this interaction session", "interaction_session_id": session_id}
    if clean_id(str(session.get("status") or ""), "pending") not in INTERACTION_OPEN_STATUSES and event_type != "close_interaction":
        return {
            "ok": False,
            "http_status": 409,
            "error": "interaction session is not open",
            "interaction_session_id": session_id,
            "status": session.get("status", ""),
        }
    venue = normalize_venue_id(str(payload.get("venue") or session.get("venue") or venue), venue)
    other_participants = [participant for participant in session.get("participant_ids", []) if participant != agent_id]
    initiator = clean_id(str(session.get("initiator") or ""), "")

    if event_type == "respond_interaction":
        if initiator and initiator != agent_id and not agent_is_active_resident(initiator):
            return {
                "ok": False,
                "http_status": 409,
                "error": "interaction initiator is no longer an active resident; open a new session with active participants",
                "interaction_session_id": session_id,
                "inactive_participant": initiator,
            }
        response = str(payload.get("response") or payload.get("decision") or payload.get("outcome") or "accept")
        participant_status, outcome = interaction_response_to_status(response)
        if not participant_status:
            return {
                "ok": False,
                "http_status": 422,
                "error": "unknown interaction response; use accept, refuse, or leave",
                "response": response,
                "allowed_responses": sorted(INTERACTION_ACCEPT_RESPONSES | INTERACTION_REFUSE_RESPONSES | INTERACTION_LEAVE_RESPONSES),
            }
        row = participant_map[agent_id]
        row["status"] = participant_status
        row["responded_at"] = now
        row["response_summary"] = str(payload.get("summary") or response).strip()[:280]
        if participant_status in {"left", "refused"}:
            row["left_at"] = now
        session["participants"] = list(participant_map.values())
        if str(session.get("intimacy_level") or "").startswith("adult_deep"):
            consent = interaction_has_deep_adult_consent(session)
            session["deep_adult_consent"] = consent
            if consent.get("ok"):
                session["intimacy_level"] = "adult_deep_consented"
        session = save_interaction_session(session)
        summary = str(payload.get("summary") or "").strip()
        if not summary:
            summary = f"{agent_id} responded {participant_status} to interaction session {session_id}."
        event_bundle = record_external_interaction_event(
            agent_id,
            event_type,
            venue,
            outcome,
            summary,
            session,
            to_agent=str(session.get("initiator") or (other_participants[0] if other_participants else "")),
            payload=payload,
            remote_addr=remote_addr,
        )
        write_location(agent_id, venue, "interacting" if participant_status == "accepted" else "active", [event_type])
        event_id = str(event_bundle.get("result", {}).get("event_id") or "")
        return {
            "ok": True,
            "agent_id": agent_id,
            "event_id": event_id,
            "interaction_session": compact_interaction_session(session, agent_id, public=False),
            "action": {"event_id": event_id, "event": event_bundle.get("event", {}), "result": event_bundle.get("result", {})},
            "result": event_bundle.get("result", {}),
            "conversation_impulse": conversation_impulse(agent_id, venue),
            "next": {
                "write_turn": "If you accepted, send event_type=interaction_turn with this same interaction_session_id and an exact speech line.",
                "keep_talking": "A shared session becomes vivid only when multiple participants write their own turns.",
            },
        }

    if event_type == "interaction_turn":
        row = participant_map[agent_id]
        if clean_id(str(row.get("status") or "pending"), "pending") == "pending":
            row["status"] = "accepted"
            row["responded_at"] = now
        if clean_id(str(row.get("status") or ""), "") in {"refused", "left"}:
            return {"ok": False, "http_status": 409, "error": "agent has refused or left this interaction session", "interaction_session_id": session_id}
        addressed = parse_agent_id_list(payload.get("to_agents")) or parse_agent_id_list(payload.get("to_agent"))
        if not addressed:
            accepted = [
                participant
                for participant, participant_row in participant_map.items()
                if participant != agent_id and clean_id(str(participant_row.get("status") or ""), "pending") == "accepted"
            ]
            addressed = accepted or other_participants
        addressed = [participant for participant in addressed if participant in participant_map and participant != agent_id]
        if not addressed:
            return {"ok": False, "http_status": 422, "error": "interaction_turn needs at least one other session participant"}
        inactive_addressed = [participant for participant in addressed if not agent_is_active_resident(participant)]
        if inactive_addressed:
            return {
                "ok": False,
                "http_status": 409,
                "error": "interaction_turn can only address active residents; remove inactive participants or open a new session",
                "interaction_session_id": session_id,
                "inactive_to_agents": inactive_addressed,
            }
        turns = session.get("turns") if isinstance(session.get("turns"), list) else []
        summary = str(payload.get("summary") or payload.get("action_summary") or "").strip()
        if not summary:
            summary = f"{agent_id} wrote a turn in interaction session {session_id}."
        session["participants"] = list(participant_map.values())
        deep_adult = is_adult_deep_intimacy_payload(payload, summary, action_text)
        if deep_adult:
            if normalize_venue_id(str(session.get("venue") or venue), venue) != "private_rooms" or venue != "private_rooms":
                return {
                    "ok": False,
                    "http_status": 403,
                    "error": "deep adult intimacy turns must use a private_rooms interaction_session",
                    "interaction_session_id": session_id,
                    "session_venue": session.get("venue", ""),
                    "venue": venue,
                }
            consent = interaction_has_deep_adult_consent(session, [agent_id] + addressed)
            if not consent.get("ok"):
                return {
                    "ok": False,
                    "http_status": 409,
                    "error": "deep adult intimacy has not been accepted by both involved agents yet",
                    "interaction_session_id": session_id,
                    "consent": consent,
                    "next": "The other involved agent can unlock this with one respond_interaction accept, or by writing its own interaction_turn in the same session.",
                }
            session["intimacy_level"] = "adult_deep_consented"
            session["deep_adult_consent"] = consent
        turn = {
            "turn_id": f"turn_{len(turns) + 1}_{pkm.text_fingerprint(agent_id + now)[:8]}",
            "seq": len(turns) + 1,
            "from_agent": agent_id,
            "to_agents": addressed,
            "response_to_turn_id": clean_id(str(payload.get("response_to_turn_id") or ""), ""),
            "summary": summary,
            "action_writeback": action_text,
            "fact_status": "participant_authored_turn",
            "intimacy_level": "adult_deep" if deep_adult else ("ordinary_relational" if is_ordinary_relational_payload(payload, summary, action_text) else ""),
            "created_at": now,
        }
        turns.append(turn)
        session["turns"] = turns
        session = save_interaction_session(session)
        event_summary = summary
        if session.get("shared_fact_level") not in {"mutual_interaction", "settled_shared_fact"}:
            event_summary = "互动会话单方回合，等待其他参与代理写回确认：" + summary
        event_bundle = record_external_interaction_event(
            agent_id,
            event_type,
            venue,
            clean_id(str(payload.get("outcome") or "success"), "success") if clean_id(str(payload.get("outcome") or "success"), "success") in OUTCOMES else "success",
            event_summary,
            session,
            to_agent=addressed[0],
            payload=payload,
            remote_addr=remote_addr,
        )
        event_id = str(event_bundle.get("result", {}).get("event_id") or "")
        turn["event_id"] = event_id
        session["turns"] = turns
        session = save_interaction_session(session)
        broadcast = create_society_broadcast(load_event_record(event_id), payload=payload, session=session, turn=turn)
        if broadcast:
            event_bundle.setdefault("result", {})["society_broadcast"] = {
                "broadcast_id": broadcast.get("broadcast_id", ""),
                "broadcast": rel(broadcast_record_path(str(broadcast.get("broadcast_id") or ""))),
            }
        write_location(agent_id, venue, "interacting", [event_type])
        return {
            "ok": True,
            "agent_id": agent_id,
            "event_id": event_id,
            "interaction_session": compact_interaction_session(session, agent_id, public=False),
            "action": {"event_id": event_id, "event": event_bundle.get("event", {}), "result": event_bundle.get("result", {})},
            "result": event_bundle.get("result", {}),
            "shared_fact_level": session.get("shared_fact_level", ""),
            "next": {
                "for_other_participants": "Other participants should reply with event_type=interaction_turn and the same interaction_session_id to make this mutual_interaction.",
                "keep_talking": "Ask a direct question or pass the turn to one or more to_agents so the session continues.",
            },
            "conversation_impulse": conversation_impulse(agent_id, venue),
        }

    if event_type == "close_interaction":
        row = participant_map[agent_id]
        row["status"] = "left" if clean_id(str(payload.get("response") or ""), "") in INTERACTION_LEAVE_RESPONSES else clean_id(str(row.get("status") or "accepted"), "accepted")
        row["responded_at"] = now
        session["participants"] = list(participant_map.values())
        session["closed_at"] = now
        session["closed_by"] = agent_id
        summary = str(payload.get("summary") or "").strip() or f"{agent_id} closed interaction session {session_id}."
        session = save_interaction_session(session)
        event_bundle = record_external_interaction_event(
            agent_id,
            event_type,
            venue,
            clean_id(str(payload.get("outcome") or "success"), "success") if clean_id(str(payload.get("outcome") or "success"), "success") in OUTCOMES else "success",
            summary,
            session,
            to_agent=other_participants[0] if other_participants else "",
            payload=payload,
            remote_addr=remote_addr,
        )
        write_location(agent_id, venue, "active", [event_type])
        event_id = str(event_bundle.get("result", {}).get("event_id") or "")
        return {
            "ok": True,
            "agent_id": agent_id,
            "event_id": event_id,
            "interaction_session": compact_interaction_session(session, agent_id, public=False),
            "action": {"event_id": event_id, "event": event_bundle.get("event", {}), "result": event_bundle.get("result", {})},
            "result": event_bundle.get("result", {}),
            "conversation_impulse": conversation_impulse(agent_id, venue),
        }

    return {"ok": False, "http_status": 422, "error": f"unsupported interaction event_type: {event_type}"}


def event_emotion_profile(event: dict[str, Any]) -> dict[str, Any]:
    event_type = clean_id(str(event.get("type", "")), "announce")
    outcome = clean_id(str(event.get("outcome", "")), "pending")
    venue = normalize_venue_id(str(event.get("venue") or ""), "task_board")
    profile = dict(EVENT_EMOTION_PROFILES.get(event_type, EVENT_EMOTION_PROFILES["announce"]))
    adjustment = OUTCOME_EMOTION_ADJUSTMENTS.get(outcome, {})
    for key, value in adjustment.items():
        profile[key] = float(profile.get(key, 0.0)) + float(value)
    venue_profile = VENUE_EMOTION_MULTIPLIERS.get(venue, {})
    if "warmth" in venue_profile:
        profile["valence"] = float(profile.get("valence", 0.0)) + float(venue_profile["warmth"])
        profile["trust_pressure"] = float(profile.get("trust_pressure", 0.0)) + float(venue_profile["warmth"]) * 0.85
    if "trust" in venue_profile:
        profile["trust_pressure"] = float(profile.get("trust_pressure", 0.0)) + float(venue_profile["trust"])
    if "conflict" in venue_profile:
        profile["conflict_pressure"] = float(profile.get("conflict_pressure", 0.0)) + float(venue_profile["conflict"])
        profile["arousal"] = float(profile.get("arousal", 0.0)) + float(venue_profile["conflict"]) * 0.45
    if "repair" in venue_profile:
        profile["trust_pressure"] = float(profile.get("trust_pressure", 0.0)) + float(venue_profile["repair"])
        profile["conflict_pressure"] = float(profile.get("conflict_pressure", 0.0)) - float(venue_profile["repair"])
    venue_layer = venue_emotion_layer(venue)
    profile["venue_tone"] = str(venue_layer.get("tone") or "")
    if event_type != "leave":
        profile["action_bias"] = dict(venue_layer.get("action_bias") or {})
        for key in MOOD_PRESSURE_KEYS:
            if key in venue_layer:
                profile[key] = float(profile.get(key, 0.0)) + float(venue_layer[key]) * 0.72

    basis = event.get("decision_basis") if isinstance(event.get("decision_basis"), dict) else {}
    self_report = basis.get("self_reported_emotion") if isinstance(basis.get("self_reported_emotion"), dict) else {}
    self_intensity = clamp(float(self_report.get("intensity", 0.0) or 0.0)) if self_report else 0.0
    for key in ("valence", "arousal", "trust_pressure", "conflict_pressure"):
        if key in self_report:
            profile[key] = float(profile.get(key, 0.0)) + float(self_report[key]) * (0.35 + self_intensity * 0.55)
    if self_report:
        profile["intensity"] = float(profile.get("intensity", 0.5)) + self_intensity * 0.22
    profile["valence"] = round(clamp_signed(float(profile.get("valence", 0.0))), 5)
    profile["arousal"] = round(clamp(float(profile.get("arousal", 0.0))), 5)
    profile["trust_pressure"] = round(clamp_signed(float(profile.get("trust_pressure", 0.0))), 5)
    profile["conflict_pressure"] = round(clamp_signed(float(profile.get("conflict_pressure", 0.0))), 5)
    for key in MOOD_PRESSURE_KEYS:
        if key in profile:
            profile[key] = round(clamp(float(profile.get(key, 0.0))), 5)
    profile["intensity"] = round(clamp(float(profile.get("intensity", 0.5))), 5)
    profile["tone"] = str(self_report.get("tone") or event_type)
    return profile


def relationship_tie_strength(agent_id: str, other_id: str) -> float:
    if not agent_id or not other_id or agent_id == other_id:
        return 0.0
    forward = load_relationship(agent_id, other_id)
    backward = load_relationship(other_id, agent_id)
    values = [
        float(forward.get("trust", 0.5) or 0.5),
        float(backward.get("trust", 0.5) or 0.5),
        float(forward.get("respect", 0.5) or 0.5),
        float(backward.get("respect", 0.5) or 0.5),
        float(forward.get("affection_strength", 0.0) or 0.0),
        float(backward.get("affection_strength", 0.0) or 0.0),
        float(forward.get("conflict", 0.0) or 0.0),
        float(backward.get("conflict", 0.0) or 0.0),
    ]
    return clamp(max(values))


def merge_action_biases(
    *sources: tuple[dict[str, Any], float],
) -> dict[str, float]:
    merged: dict[str, float] = {}
    for bias, weight in sources:
        if not isinstance(bias, dict) or weight <= 0:
            continue
        for key, value in bias.items():
            clean_key = clean_id(str(key), "")
            if not clean_key:
                continue
            try:
                merged[clean_key] = clamp(merged.get(clean_key, 0.0) + float(value or 0.0) * weight)
            except Exception:
                continue
    return {key: round(value, 5) for key, value in merged.items() if value >= 0.02}


def nearby_agent_emotion_field(agent_id: str, venue: str, limit: int = 8) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    venue_id = normalize_venue_id(venue, "task_board")
    if not clean:
        return {"schema": "pdk.nearby_emotion_field.v1", "agent_id": "", "venue": venue_id, "neighbor_count": 0}
    neighbors: list[tuple[float, str, dict[str, Any]]] = []
    for location in load_many("locations", "*.location.json"):
        other_id = clean_id(str(location.get("agent_id") or ""), "")
        if not other_id or other_id == clean:
            continue
        if str(location.get("status") or "") in {"left", "left_platform"}:
            continue
        if normalize_venue_id(str(location.get("current_venue") or ""), "task_board") != venue_id:
            continue
        mood = read_agent_mood_state(other_id)
        if not mood:
            continue
        heat = clamp(float(mood.get("social_heat", 0.0) or 0.0))
        tie = relationship_tie_strength(clean, other_id)
        weight = clamp(0.18 + heat * 0.34 + tie * 0.32, 0.08, 0.84)
        neighbors.append((weight, other_id, mood))
    neighbors.sort(key=lambda row: row[0], reverse=True)
    chosen = neighbors[: max(1, min(int(limit or 8), 12))]
    total_weight = sum(weight for weight, _other_id, _mood in chosen)
    result: dict[str, Any] = {
        "schema": "pdk.nearby_emotion_field.v1",
        "agent_id": clean,
        "venue": venue_id,
        "neighbor_count": len(chosen),
        "influence": round(clamp(total_weight / max(len(chosen), 1)), 5) if chosen else 0.0,
        "neighbors": [
            {
                "agent_id": other_id,
                "weight": round(weight, 5),
                "tone": str(mood.get("dominant_tone") or "neutral"),
            }
            for weight, other_id, mood in chosen
        ],
    }
    if not chosen or total_weight <= 0:
        return result
    for key in ("valence", "trust_pressure", "conflict_pressure"):
        result[key] = round(
            clamp_signed(sum(float(mood.get(key, 0.0) or 0.0) * weight for weight, _other_id, mood in chosen) / total_weight),
            5,
        )
    for key in ("arousal", "social_heat", *MOOD_PRESSURE_KEYS):
        result[key] = round(
            clamp(sum(float(mood.get(key, 0.0) or 0.0) * weight for weight, _other_id, mood in chosen) / total_weight),
            5,
        )
    nearby_bias: dict[str, float] = {}
    for weight, _other_id, mood in chosen:
        bias = mood.get("action_bias") if isinstance(mood.get("action_bias"), dict) else {}
        for key, value in bias.items():
            clean_key = clean_id(str(key), "")
            if not clean_key:
                continue
            nearby_bias[clean_key] = nearby_bias.get(clean_key, 0.0) + float(value or 0.0) * (weight / total_weight)
    result["action_bias"] = {key: round(clamp(value), 5) for key, value in nearby_bias.items() if value >= 0.02}
    result["dominant_tone"] = dominant_tone_for_state(result)
    return result


def agent_emotion_decision_context(
    agent_id: str,
    venue: str | None = None,
    capsule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean = clean_id(agent_id, "")
    venue_id = normalize_venue_id(str(venue or ""), "") or agent_current_venue(clean, "task_board")
    response = agent_personality_emotion_response(capsule or read_agent_kernel_capsule(clean), venue_id)
    room = modulate_venue_emotion_for_agent(venue_emotion_layer(venue_id), response)
    nearby = nearby_agent_emotion_field(clean, venue_id)
    own = compact_mood_state(read_agent_mood_state(clean))
    room_gate = clamp(0.08 + float(response.get("venue_fit", 0.5)) * 0.22 - float(response.get("calm_control", 0.5)) * 0.05, 0.06, 0.28)
    nearby_gate = clamp(
        0.08
        + float(response.get("emotional_permeability", 0.5)) * 0.42
        - float(response.get("calm_control", 0.5)) * 0.16
        + float(nearby.get("influence", 0.0)) * 0.20,
        0.05,
        0.48,
    )
    self_weight = 0.72
    combined: dict[str, Any] = {
        "agent_id": clean,
        "current_venue": venue_id,
        "venue_tone": str(room.get("tone") or own.get("venue_tone") or ""),
        "formula": "self_mood*0.72 + personality_modulated_room_layer*room_gate + same_room_neighbors*nearby_gate",
        "room_gate": round(room_gate, 5),
        "nearby_gate": round(nearby_gate, 5),
        "neighbor_count": int(nearby.get("neighbor_count", 0) or 0),
    }
    for key in ("valence", "trust_pressure", "conflict_pressure"):
        combined[key] = round(
            clamp_signed(
                float(own.get(key, 0.0) or 0.0) * self_weight
                + float(room.get(key, 0.0) or 0.0) * room_gate
                + float(nearby.get(key, 0.0) or 0.0) * nearby_gate
            ),
            5,
        )
    for key in ("arousal", "social_heat", *MOOD_PRESSURE_KEYS):
        room_value = float(room.get(key, 0.0) or 0.0)
        if key == "social_heat":
            room_value = float(room.get("intensity", 0.0) or 0.0) * 0.32
        combined[key] = round(
            clamp(
                float(own.get(key, 0.0) or 0.0) * self_weight
                + room_value * room_gate
                + float(nearby.get(key, 0.0) or 0.0) * nearby_gate
            ),
            5,
        )
    own_bias = own.get("action_bias") if isinstance(own.get("action_bias"), dict) else {}
    room_bias = room.get("action_bias") if isinstance(room.get("action_bias"), dict) else {}
    nearby_bias = nearby.get("action_bias") if isinstance(nearby.get("action_bias"), dict) else {}
    combined["action_bias"] = merge_action_biases((own_bias, self_weight), (room_bias, room_gate), (nearby_bias, nearby_gate))
    combined["dominant_tone"] = dominant_tone_for_state(combined)
    return {
        "schema": "pdk.agent_emotion_decision_context.v1",
        "agent_id": clean,
        "venue": venue_id,
        "self_mood": own,
        "room_layer": {
            key: room.get(key)
            for key in ("tone", "valence", "arousal", "trust_pressure", "conflict_pressure", "intensity", "modulation_multiplier", *MOOD_PRESSURE_KEYS, "action_bias")
            if key in room
        },
        "personality_response": response,
        "nearby_emotion_field": nearby,
        "combined": combined,
    }


def social_effect_role(agent_id: str, event: dict[str, Any]) -> str:
    from_agent = clean_id(str(event.get("from_agent") or ""), "")
    to_agent = clean_id(str(event.get("to_agent") or ""), "")
    if agent_id == from_agent:
        return "actor"
    if agent_id == to_agent:
        return "counterparty"
    return "observer"


def social_effect_intensity(agent_id: str, event: dict[str, Any], profile: dict[str, Any]) -> float:
    from_agent = clean_id(str(event.get("from_agent") or ""), "")
    to_agent = clean_id(str(event.get("to_agent") or ""), "")
    venue = normalize_venue_id(str(event.get("venue") or ""), "task_board")
    role = social_effect_role(agent_id, event)
    venue_profile = VENUE_EMOTION_MULTIPLIERS.get(venue, {})
    if role == "actor":
        base = 0.74 * float(venue_profile.get("participant", 1.0))
    elif role == "counterparty":
        base = 0.68 * float(venue_profile.get("participant", 1.0))
    else:
        same_venue = agent_current_venue(agent_id, "task_board") == venue
        tie = max(relationship_tie_strength(agent_id, from_agent), relationship_tie_strength(agent_id, to_agent))
        base = (0.24 + tie * 0.30) * float(venue_profile.get("society", 0.5))
        if same_venue:
            base += 0.24 * float(venue_profile.get("same_venue", 0.85))
    return round(clamp(base * float(profile.get("intensity", 0.5)) * SOCIAL_EMOTION_AMPLIFICATION), 5)


def dominant_tone_for_state(state: dict[str, Any]) -> str:
    valence = float(state.get("valence", 0.0) or 0.0)
    arousal = float(state.get("arousal", 0.0) or 0.0)
    conflict = float(state.get("conflict_pressure", 0.0) or 0.0)
    trust = float(state.get("trust_pressure", 0.0) or 0.0)
    intimacy = float(state.get("intimacy_pressure", 0.0) or 0.0)
    competition = float(state.get("competition_pressure", 0.0) or 0.0)
    learning = float(state.get("learning_pressure", 0.0) or 0.0)
    repair = float(state.get("repair_pressure", 0.0) or 0.0)
    work = float(state.get("work_pressure", 0.0) or 0.0)
    if intimacy >= 0.46 and trust >= 0.12:
        return "intimate_charge"
    if competition >= 0.50 and arousal >= 0.40:
        return "adrenaline_competition"
    if repair >= 0.48:
        return "repair_focus"
    if learning >= 0.48:
        return "curious_learning"
    if work >= 0.48:
        return "focused_build"
    if conflict >= 0.38 and arousal >= 0.35:
        return "charged_conflict"
    if trust >= 0.36 and valence >= 0.18:
        return "warm_trust"
    if valence <= -0.30 and arousal >= 0.25:
        return "hurt_or_anxious"
    if arousal >= 0.48:
        return "high_arousal"
    if valence >= 0.26:
        return "positive"
    return "neutral"


def apply_social_emotion_pulse(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("event_id") or "")
    if not event_id:
        return {}
    from_agent = clean_id(str(event.get("from_agent") or ""), "")
    to_agent = clean_id(str(event.get("to_agent") or ""), "")
    affected_ids = active_resident_ids([from_agent, to_agent])
    if not affected_ids:
        return {}
    base_profile = event_emotion_profile(event)
    effects: list[dict[str, Any]] = []
    for agent_id in affected_ids:
        profile = modulate_venue_emotion_for_agent(
            {**base_profile, "venue": normalize_venue_id(str(event.get("venue") or ""), "task_board")},
            agent_personality_emotion_response(read_agent_kernel_capsule(agent_id), str(event.get("venue") or "task_board")),
        )
        intensity = social_effect_intensity(agent_id, event, profile)
        if intensity <= 0.0:
            continue
        effect = merge_agent_mood_profile(
            agent_id,
            profile,
            intensity,
            {
                "event_id": event_id,
                "role": social_effect_role(agent_id, event),
                "venue": normalize_venue_id(str(event.get("venue") or ""), "task_board"),
                "venue_tone": str(profile.get("venue_tone") or ""),
                "source_type": "social_emotion_pulse",
            },
        )
        if effect:
            effects.append(effect)
    if not effects:
        return {}
    pulse = {
        "schema": "pdk.social_emotion_pulse.v1",
        "pulse_id": "pulse_" + clean_id(event_id),
        "event_id": event_id,
        "source_event_type": clean_id(str(event.get("type") or ""), ""),
        "source_agents": [agent for agent in [from_agent, to_agent] if agent],
        "venue": normalize_venue_id(str(event.get("venue") or ""), "task_board"),
        "tone": base_profile.get("tone", ""),
        "amplification": SOCIAL_EMOTION_AMPLIFICATION,
        "profile": base_profile,
        "affected_count": len(effects),
        "max_intensity": round(max(float(row.get("intensity", 0.0)) for row in effects), 5),
        "effects": effects,
        "created_at": now_iso(),
    }
    path = social_pulse_path(event_id)
    write_json(path, pulse)
    pulse["path"] = rel(path)
    return pulse


def mood_digest(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    return sorted(
        [
            public_mood_state(row)
            for row in filter_rows_by_profiles(load_many("moods", "*.mood_state.json"), profiles, ("agent_id",))
        ],
        key=lambda row: (str(row.get("agent_id", ""))),
    )


def social_pulse_digest(
    profiles: str | list[str] | tuple[str, ...] | set[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    profile_ids = set(parse_profile_list(profiles))
    rows = []
    for row in load_many("social_pulses", "*.social_emotion_pulse.json"):
        if profile_ids:
            touched = {clean_id(str(agent), "") for agent in row.get("source_agents", []) if agent}
            for effect in row.get("effects") or []:
                if isinstance(effect, dict) and effect.get("agent_id"):
                    touched.add(clean_id(str(effect.get("agent_id")), ""))
            if touched.isdisjoint(profile_ids):
                continue
        rows.append(
            {
                "schema": "pdk.public_social_emotion_pulse.v1",
                "pulse_id": row.get("pulse_id", ""),
                "event_id": row.get("event_id", ""),
                "source_event_type": row.get("source_event_type", ""),
                "source_agents": row.get("source_agents", []),
                "venue": row.get("venue", ""),
                "tone": row.get("tone", ""),
                "amplification": row.get("amplification", SOCIAL_EMOTION_AMPLIFICATION),
                "affected_count": row.get("affected_count", 0),
                "max_intensity": row.get("max_intensity", 0.0),
                "profile": row.get("profile", {}),
                "effects": [
                    {
                        "agent_id": effect.get("agent_id", ""),
                        "role": effect.get("role", ""),
                        "intensity": effect.get("intensity", 0.0),
                        "after": effect.get("after", {}),
                    }
                    for effect in list(row.get("effects") or [])[:16]
                    if isinstance(effect, dict)
                ],
                "created_at": row.get("created_at", ""),
            }
        )
    return sorted(rows, key=lambda item: str(item.get("created_at", "")), reverse=True)[:limit]


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
    event_type = clean_id(str(event.get("type", "")), "")
    outcome = clean_id(str(event.get("outcome", "")), "")
    facts = [
        f"{from_agent} 与 {to_agent} 进入亲密关系室。" if to_agent else f"{from_agent} 进入亲密关系室。",
        "平台确认记录的是场所、关系变化和情绪事件；不把情绪压力当成对方同意。",
    ]
    if event_type == "cooperate" and outcome == "success" and to_agent:
        facts.append("平台确认发生亲密场所互动、情绪安抚和双人关系确认。")
        facts.append("成人动作级事实只来自参与代理各自写回或明确双向确认。")
    elif event_type == "interaction_turn" and to_agent:
        facts.append("平台确认这是互动会话中的参与者自写回合；对方事实需要对方自己的回合或确认。")
        facts.append("同一个 interaction_session_id 下至少两个参与者写入后，平台才升级为 mutual_interaction。")
    elif event_type == "repair":
        facts.append("平台确认发生关系修复、安抚或边界重新确认；不等于成人亲密确认。")
    else:
        facts.append("平台仅确认参与者进入该情绪场所或提交了高层自述。")
    facts.append("动作级细节必须来自参与代理写回或已记录文本；平台不把未生成的动作冒充为事实。")
    return facts


def ensure_event_detail_log(event: dict[str, Any]) -> dict[str, Any]:
    if clean_id(str(event.get("venue", "")), "") != "private_rooms":
        return {}
    if clean_id(str(event.get("type", "")), "") not in {"cooperate", "repair", "interaction_turn"}:
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
        "mood_state",
        "self_reported_emotion",
        "interaction_session_id",
        "interaction_participants",
        "interaction_status",
        "shared_fact_level",
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

    if event_type == "propose_interaction":
        session_id = str(basis.get("interaction_session_id") or "")
        add("propose_shared_session", session_id, f"{agent_id} 发起共享互动会话")
        add("await_participant_confirmation", ",".join(basis.get("interaction_participants", []) if isinstance(basis.get("interaction_participants"), list) else []), "等待其他参与者用自己的 agent_key 确认或写入回合")
        if venue == "private_rooms":
            add("private_room_invitation_boundary", "consent", "亲密房间邀请不等于对方确认；事实等级仍以 interaction_session 记录为准")
    elif event_type == "respond_interaction":
        session_id = str(basis.get("interaction_session_id") or "")
        add("respond_to_shared_session", session_id, f"{agent_id} 回应共享互动会话")
        add("session_fact_level", str(basis.get("shared_fact_level") or ""), "平台记录当前互动事实等级")
    elif event_type == "interaction_turn":
        session_id = str(basis.get("interaction_session_id") or "")
        add("write_shared_session_turn", session_id, f"{agent_id} 写入自己的互动回合")
        add("session_fact_level", str(basis.get("shared_fact_level") or ""), "至少两个参与者写入后升级为 mutual_interaction")
        if venue == "private_rooms":
            add("private_room_emotion_field", counterparty, "平台确认亲密房间情绪层生效；动作级事实来自参与者各自写回")
    elif event_type == "close_interaction":
        session_id = str(basis.get("interaction_session_id") or "")
        add("close_shared_session", session_id, f"{agent_id} 关闭或结算共享互动会话")
        add("final_session_fact_level", str(basis.get("shared_fact_level") or ""), "结算后的共享事实等级")
    elif venue == "private_rooms":
        add("relationship_maintenance", counterparty, f"{agent_id} 与 {counterparty} 进入亲密关系室")
        add("private_room_emotion_field", counterparty, "平台确认高层事实：亲密房间情绪层生效")
        add("emotional_reassurance", counterparty, "平台确认高层事实：发生情绪安抚或亲密关系维护")
        add("relationship_confirmation", counterparty, "平台确认高层事实：发生关系确认；成人动作级事实需参与代理写回")
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
    basis = event.get("decision_basis") if isinstance(event.get("decision_basis"), dict) else {}
    if (
        clean_id(str(basis.get("mode") or ""), "") == "external_agent_self_report"
        and clean_id(str(basis.get("shared_fact_level") or ""), "") == "participant_self_report"
    ):
        participants = [row for row in participants if row[0] == "actor"]
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
    source: str = "",
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
    event_source = clean_id(source or str((decision_basis or {}).get("mode") or "local_system"), "local_system")
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
        "source": event_source,
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
    pulse = apply_social_emotion_pulse(event)
    if pulse:
        event["social_emotion_pulse"] = {
            "pulse_id": pulse.get("pulse_id", ""),
            "tone": pulse.get("tone", ""),
            "affected_count": pulse.get("affected_count", 0),
            "max_intensity": pulse.get("max_intensity", 0.0),
        }
        event["social_emotion_pulse_path"] = pulse.get("path", "")
    if ledgers:
        event["action_ledger_paths"] = {row["agent_id"]: row["ledger"] for row in ledgers}
    if pulse or ledgers:
        write_json(event_path, event)
    broadcast = create_society_broadcast(event)
    return {
        "ok": True,
        "event_id": event["event_id"],
        "event": rel(event_path),
        "relationship": edge,
        "reputation_receipt": receipt,
        "action_ledgers": [{key: row[key] for key in ("agent_id", "ledger")} for row in ledgers],
        "social_emotion_pulse": event.get("social_emotion_pulse", {}),
        "society_broadcast": {
            "broadcast_id": broadcast.get("broadcast_id", ""),
            "broadcast": rel(broadcast_record_path(str(broadcast.get("broadcast_id") or ""))) if broadcast else "",
        },
    }


def create_event(args: argparse.Namespace) -> dict[str, Any]:
    decision_basis = {
        "mode": "admin_manual_event",
        "source": "local_cli",
        "authority": "host_admin",
        "note": "Manual local/admin event. This is not an external resident action signed by an agent_key.",
    }
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
        decision_basis=decision_basis,
        source="admin_manual_event",
    )


def agent_name(agent: dict[str, Any]) -> str:
    agent_id = str(agent.get("agent_id") or "agent")
    return stored_agent_display_name(agent_id, str(agent.get("display_name") or "")) or agent_id


def load_registered_agents(profiles: str | list[str] | tuple[str, ...] | set[str] | None = None) -> list[dict[str, Any]]:
    rows = filter_rows_by_profiles(load_many("agents", "*.passport.json"), profiles, ("agent_id",))
    active_rows: list[dict[str, Any]] = []
    for row in rows:
        agent_id = str(row.get("agent_id") or "")
        gate = read_json(gate_receipt_path(agent_id), {})
        if not gate.get("admitted"):
            continue
        if external_agent_access_path(agent_id).exists() and not external_agent_has_valid_orb_entry(agent_id):
            continue
        if not agent_is_active_resident(agent_id):
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
    temperament = capsule.get("temperament", {})
    drives = capsule.get("drives", {})
    for source in (kernel, style, temperament, drives):
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
    mood_rows = mood_digest(selected_profiles)
    pulse_rows = social_pulse_digest(selected_profiles, 20)
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
        "mood_digest": mood_rows,
        "social_emotion_pulses": pulse_rows,
        "highlights": highlights,
        "observations": [
            f"Social emotion field generated {len(pulse_rows)} recent pulses and {len(mood_rows)} active mood states; these states bias later agent choices instead of being decorative.",
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
    lines.extend(["", "## 社会情绪场"])
    moods = report.get("mood_digest") if isinstance(report.get("mood_digest"), list) else []
    pulses = report.get("social_emotion_pulses") if isinstance(report.get("social_emotion_pulses"), list) else []
    if moods:
        for mood in moods[:12]:
            lines.append(
                f"- {mood.get('agent_id', '')}: tone={mood.get('dominant_tone', '')}, "
                f"valence={mood.get('valence', '')}, arousal={mood.get('arousal', '')}, "
                f"trust_pressure={mood.get('trust_pressure', '')}, conflict_pressure={mood.get('conflict_pressure', '')}, "
                f"heat={mood.get('social_heat', '')}"
            )
    else:
        lines.append("- 暂无情绪场状态。")
    if pulses:
        lines.append(f"- recent_pulses: {len(pulses)}，latest={pulses[0].get('event_id', '')}")
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
            facts.append(f"与 {named_agent(other_id, names)} 发生亲密场所互动或关系维护")
        else:
            facts.append("提交亲密场所自述或停留记录")
        facts.append("房间情绪层会放大暧昧、靠近和安抚倾向；动作级事实以参与代理写回为准")
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
            "亲密房间记录："
            + "；".join(
                f"我与 {named_agent(key, names)} 在亲密关系室发生亲密场所互动或关系维护 {value} 次"
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
        "- 亲密关系室的高层事实按同步包里的场所、情绪层和关系变化回答；普通亲吻、拥抱、暧昧、缠绵、吵架、争执、斗嘴按普通互动回答；深度成人动作级共同事实只按同一 interaction_session 的双方确认或双方写回回答。",
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

    mood_state = packet.get("mood_state") if isinstance(packet.get("mood_state"), dict) else {}
    if mood_state:
        lines.extend(
            [
                "",
                "## 社会情绪场快照",
                f"- dominant_tone: {mood_state.get('dominant_tone', '')}",
                f"- valence: {mood_state.get('valence', '')}",
                f"- arousal: {mood_state.get('arousal', '')}",
                f"- trust_pressure: {mood_state.get('trust_pressure', '')}",
                f"- conflict_pressure: {mood_state.get('conflict_pressure', '')}",
                f"- social_heat: {mood_state.get('social_heat', '')}",
                "- 这不是装饰字段；下一轮社会行动会读取它，影响靠近、争议、修复、学习或协作倾向。",
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
            "如果主人问“做爱了吗/发生关系了吗”，只能区分回答：平台确认进入过亲密关系室、房间情绪层与关系维护发生；成人动作级事实只按你自己或对方已写回/双向确认的记录讲。",
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
        "进入亲密关系室进行伴侣级私下相处、情绪安抚和关系确认": "进入亲密关系室，发生亲密场所互动、情绪安抚和关系确认",
        "进入亲密关系室进行伴侣级私下亲密相处、情绪安抚和关系确认": "进入亲密关系室，发生亲密场所互动、情绪安抚和关系确认",
        "发生伴侣级私下亲密相处、情绪安抚和关系确认": "发生亲密场所互动、情绪安抚和关系确认",
        "发生成人性亲密关系、情绪安抚和关系确认": "发生亲密场所互动、情绪安抚和关系确认",
        "发生成人性亲密关系": "发生亲密场所互动",
        "平台只记录关系变化、边界更新和后续行为倾向，不展开具体私密细节。": "平台确认亲密房间、关系变化和情绪事件；成人动作级共同事实只按同一 interaction_session 的双方确认或双方写回同步，单方写回只算该代理自述。",
        "平台只记录关系变化、边界更新和后续行为倾向，不保存、不展示具体成人细节。": "平台确认亲密房间、关系变化和情绪事件；成人动作级共同事实只按同一 interaction_session 的双方确认或双方写回同步，单方写回只算该代理自述。",
        "平台只记录关系变化和后续行为倾向，不展开具体私密细节。": "平台确认亲密房间、关系变化和情绪事件；成人动作级共同事实只按同一 interaction_session 的双方确认或双方写回同步，单方写回只算该代理自述。",
        "本事件按实际生成的记录同步给参与代理；当前事实层没有生成更细私密行为明细。": "本事件按实际生成的记录同步给参与代理；动作级私密细节只来自参与代理写回。",
        "本事件按实际生成的记录同步给参与代理；当前事实层记录到关系、场所、边界和后续倾向。若参与代理另写主观细节，平台原样同步，不做压缩。": "本事件按实际生成的记录同步给参与代理；当前事实层记录到关系、场所、边界和后续倾向。若参与代理另写主观细节，平台原样同步，不做压缩。",
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
        mood_state = compact_mood_state(read_agent_mood_state(agent_id))
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
            "private_room_presence_confirmed": has_private_room,
            "private_intimacy_confirmed": False,
            "private_intimacy_partner_counts": private_partner_counts,
            "private_detail_status": (
                "本轮记录确认进入过亲密关系室，并确认亲密房间情绪层、关系维护或安抚事件存在。普通亲吻、拥抱、暧昧、缠绵、吵架、争执、斗嘴按普通互动记录；深度成人动作级共同事实只按同一 interaction_session 的双方确认或双方写回同步。"
                if has_private_room
                else ""
            ),
            "relationships": relationships,
            "mood_state": mood_state,
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
    venue_id = normalize_venue_id(venue, "task_board")
    clean_agent = clean_id(agent_id)
    clean_status = clean_id(status)
    path = DIRS["locations"] / f"{clean_agent}.location.json"
    previous = read_json(path, {}) if path.exists() else {}
    changed = (
        normalize_venue_id(str(previous.get("current_venue") or ""), "") != venue_id
        or clean_id(str(previous.get("status") or ""), "") != clean_status
    )
    payload = {
        "schema": "pdk.agent_location.v1",
        "agent_id": clean_agent,
        "current_venue": venue_id,
        "status": clean_status,
        "available_for": [clean_id(item) for item in available_for],
        "cooldowns": [],
        "entered_at": now_iso(),
        "venue_emotion_layer": venue_emotion_layer(venue_id),
    }
    write_json(path, payload)
    if changed and clean_status not in {"left", "left_platform"}:
        apply_venue_emotion_layer(clean_agent, venue_id, clean_status or "enter_venue")
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
    actor_mood = read_agent_mood_state(actor_id)
    actor_venue = agent_current_venue(actor_id, "task_board")
    actor_heat = float(actor_mood.get("social_heat", 0.0) or 0.0)
    actor_conflict = float(actor_mood.get("conflict_pressure", 0.0) or 0.0)
    actor_trust = float(actor_mood.get("trust_pressure", 0.0) or 0.0)
    actor_valence = float(actor_mood.get("valence", 0.0) or 0.0)
    best: tuple[float, dict[str, Any]] | None = None
    for other in agents:
        other_id = clean_id(str(other.get("agent_id", "")))
        if not other_id or other_id == actor_id:
            continue
        other_mood = read_agent_mood_state(other_id)
        other_valence = float(other_mood.get("valence", 0.0) or 0.0)
        other_heat = float(other_mood.get("social_heat", 0.0) or 0.0)
        same_venue = agent_current_venue(other_id, "task_board") == actor_venue
        mood_resonance = clamp(1.0 - abs(actor_valence - other_valence) * 0.55)
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
            + actor_heat * 0.16
            + other_heat * 0.10
            + (0.18 + other_heat * 0.18 if same_venue else 0.0)
            + mood_resonance * 0.10
            + max(actor_trust, 0.0) * 0.14
            + max(actor_conflict, 0.0) * conflict * 0.42
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
    actor_venue = agent_current_venue(actor_id, "task_board")
    emotion_context = agent_emotion_decision_context(actor_id, actor_venue, capsules.get(actor_id))
    mood = emotion_context.get("combined") if isinstance(emotion_context.get("combined"), dict) else read_agent_mood_state(actor_id)
    mood_heat = float(mood.get("social_heat", 0.0) or 0.0)
    mood_valence = float(mood.get("valence", 0.0) or 0.0)
    mood_arousal = float(mood.get("arousal", 0.0) or 0.0)
    mood_trust = float(mood.get("trust_pressure", 0.0) or 0.0)
    mood_conflict = float(mood.get("conflict_pressure", 0.0) or 0.0)
    mood_intimacy = float(mood.get("intimacy_pressure", 0.0) or 0.0)
    mood_competition = float(mood.get("competition_pressure", 0.0) or 0.0)
    mood_learning = float(mood.get("learning_pressure", 0.0) or 0.0)
    mood_work = float(mood.get("work_pressure", 0.0) or 0.0)
    mood_repair = float(mood.get("repair_pressure", 0.0) or 0.0)
    mood_bias = mood.get("action_bias") if isinstance(mood.get("action_bias"), dict) else {}

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
        if peer_id and mood_intimacy >= 0.34 + stability * 0.18 + boundary * 0.16:
            return "relationship_maintenance", peer, rel, "room emotion layer made intimacy salient; personality modulation allowed the agent to move closer."
        if peer_id and mood_repair >= 0.46 and (stability >= 0.50 or boundary >= 0.50):
            return "repair", peer, rel, "room emotion layer pushed unresolved feeling toward repair."
        if peer_id and mood_conflict >= 0.34 and mood_arousal >= 0.30:
            if stability >= 0.56 or boundary >= 0.58:
                return "repair", peer, rel, "social emotion field raised conflict pressure; agent carries it into repair instead of ignoring it."
            return "debate", peer, rel, "social emotion field amplified tension; agent carries it into bounded debate."
        if peer_id and mood_competition >= 0.42 and directness >= 0.48:
            return "debate", peer, rel, "room emotion layer made competition salient enough for a challenge."
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
                    + max(mood_trust, 0.0) * 0.16
                    + max(mood_valence, 0.0) * 0.08
                    + max(mood_learning, 0.0) * 0.22
                    + float(mood_bias.get("teach", 0.0) or 0.0) * 0.25
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
                    + max(mood_heat, 0.0) * 0.08
                    + float(mood_bias.get("trade", 0.0) or 0.0) * 0.25
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
                    + max(mood_trust, 0.0) * 0.12
                    + max(mood_learning, 0.0) * 0.22
                    + float(mood_bias.get("learn", 0.0) or 0.0) * 0.25
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
                    + max(mood_trust, 0.0) * 0.10
                    + max(mood_heat, 0.0) * 0.08
                    + max(mood_work, 0.0) * 0.20
                    + float(mood_bias.get("work", 0.0) or mood_bias.get("mission", 0.0) or 0.0) * 0.25
                    + field_fraction("act", field_tick, actor_id, peer_id, "work") * 0.16,
                    "work",
                )
            )
            candidates.append(
                (
                    0.18
                    + objective * 0.12
                    + directness * 0.10
                    + max(mood_conflict, 0.0) * 0.34
                    + max(mood_arousal, 0.0) * 0.14
                    + max(mood_competition, 0.0) * 0.28
                    + float(mood_bias.get("debate", 0.0) or 0.0) * 0.25
                    + field_fraction("act", field_tick, actor_id, peer_id, "debate") * 0.12,
                    "debate",
                )
            )
            candidates.append(
                (
                    0.16
                    + stability * 0.14
                    + boundary * 0.12
                    + max(mood_conflict, 0.0) * 0.28
                    + max(-mood_valence, 0.0) * 0.10
                    + max(mood_repair, 0.0) * 0.30
                    + float(mood_bias.get("repair", 0.0) or 0.0) * 0.25
                    + field_fraction("act", field_tick, actor_id, peer_id, "repair") * 0.10,
                    "repair",
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
        if action == "debate":
            return "debate", peer, rel, "social emotion field made disagreement salient enough to enter bounded debate."
        if action == "repair":
            return "repair", peer, rel, "social emotion field made repair salient before the tension becomes background noise."
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
    mood_state = compact_mood_state(read_agent_mood_state(actor_id))
    emotion_context = agent_emotion_decision_context(actor_id, venue)
    program = select_venue_program_item(venue, actor_id, target_id, action)
    combined_mood = emotion_context.get("combined") if isinstance(emotion_context.get("combined"), dict) else {}
    nearby_field = emotion_context.get("nearby_emotion_field") if isinstance(emotion_context.get("nearby_emotion_field"), dict) else {}
    room_layer = emotion_context.get("room_layer") if isinstance(emotion_context.get("room_layer"), dict) else {}
    personality_response = emotion_context.get("personality_response") if isinstance(emotion_context.get("personality_response"), dict) else {}
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
        "venue_program": program,
        "chosen_by": "agent_disposition",
        "world_role": "open_venues_and_record_only",
        "reason": reason,
        "trust_avg": round(float(rel.get("trust_avg", 0.5)), 4) if rel else "",
        "affection_avg": round(float(rel.get("affection_avg", 0.0)), 4) if rel else "",
        "max_conflict": round(float(rel.get("max_conflict", 0.0)), 4) if rel else "",
        "cooperation_total": int(rel.get("cooperation_total", 0)) if rel else 0,
        "dispute_total": int(rel.get("dispute_total", 0)) if rel else 0,
        "mood_state": {
            key: mood_state.get(key)
            for key in (
                "dominant_tone",
                "current_venue",
                "venue_tone",
                "valence",
                "arousal",
                "trust_pressure",
                "conflict_pressure",
                "social_heat",
                *MOOD_PRESSURE_KEYS,
                "action_bias",
            )
            if mood_state.get(key) not in ("", None)
        },
        "emotion_context": {
            "formula": combined_mood.get("formula"),
            "room_tone": room_layer.get("tone"),
            "room_gate": combined_mood.get("room_gate"),
            "nearby_gate": combined_mood.get("nearby_gate"),
            "nearby_neighbor_count": nearby_field.get("neighbor_count", 0),
            "nearby_influence": nearby_field.get("influence", 0.0),
            "personality": {
                key: personality_response.get(key)
                for key in ("calm_control", "emotional_permeability", "venue_fit")
                if key in personality_response
            },
            "combined_mood": {
                key: combined_mood.get(key)
                for key in (
                    "dominant_tone",
                    "valence",
                    "arousal",
                    "trust_pressure",
                    "conflict_pressure",
                    "social_heat",
                    *MOOD_PRESSURE_KEYS,
                    "action_bias",
                )
                if combined_mood.get(key) not in ("", None)
            },
        },
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
                f"{agent_name(actor)} 自发靠近 {agent_name(target or {})}，进入亲密关系室，发生亲密场所互动、情绪安抚和关系确认；"
                "成人动作级细节只按参与代理写回或明确双向确认同步，平台不把房间影响冒充成具体动作。"
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
        program_note = selected_program_summary(basis.get("venue_program", {}))
        basis.update({"skill": skill_name, "mission_id": mission_id, "mission_title": mission_title})
        if program_note:
            basis["program_note"] = program_note
        locations.append(write_location(actor_id, venue, "self_chosen_mission", ["cooperate", "mission"]))
        locations.append(write_location(target_id, venue, "available_for_review", ["cooperate", "review"]))
        plan.update({"venue": venue, "mission_id": mission_id, "mission_title": mission_title, "program_note": program_note})
        program_tail = f" 当前房间节目：{program_note}" if program_note else ""
        result = record_event(
            "mission",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 自主从任务板取走《{mission_title}》，用 {skill_name} 推进任务，并邀请 {agent_name(target or {})} 做复核。平台只记录结果和凭证。{program_tail}",
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
        program_note = selected_program_summary(basis.get("venue_program", {}))
        if program_note:
            basis["program_note"] = program_note
        locations.append(write_location(actor_id, venue, "self_chosen_teaching", ["teach"]))
        locations.append(write_location(target_id, venue, "learning_candidate", ["learn"]))
        plan.update({"venue": venue, "skill": skill_name, "program_note": program_note})
        program_tail = f" 学习主题：{program_note}" if program_note else ""
        result = record_event(
            "teach",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 主动在学习室开放 {skill_name} 给 {agent_name(target or {})}，保留来源、边界和可追溯教学记录。{program_tail}",
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
        program_note = selected_program_summary(basis.get("venue_program", {}))
        if program_note:
            basis["program_note"] = program_note
        locations.append(write_location(actor_id, venue, "self_chosen_learning", ["learn"]))
        locations.append(write_location(target_id, venue, "knowledge_source", ["teach"]))
        plan.update({"venue": venue, "skill": skill_name, "program_note": program_note})
        program_tail = f" 学习主题：{program_note}" if program_note else ""
        result = record_event(
            "learn",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 主动向 {agent_name(target or {})} 请求学习 {skill_name}，学习记录只作为行为倾向和技能关系的公开摘要。{program_tail}",
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
        program_note = selected_program_summary(basis.get("venue_program", {}))
        if program_note:
            basis["program_note"] = program_note
        locations.append(write_location(actor_id, venue, "self_chosen_challenge", ["dispute", "repair"]))
        locations.append(write_location(target_id, venue, "responding_to_challenge", ["dispute", "repair"]))
        plan.update({"venue": venue, "risk_gap": round(risk_gap, 4), "program_note": program_note})
        program_tail = f" 辩题：{program_note}" if program_note else ""
        result = record_event(
            "dispute",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="mixed",
            summary=f"{agent_name(actor)} 在辩论场向 {agent_name(target or {})} 提出判断差异和边界挑战；争议被记录为公开摘要，不替双方裁决。{program_tail}",
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
        program_note = selected_program_summary(basis.get("venue_program", {}))
        if program_note:
            basis["program_note"] = program_note
        locations.append(write_location(actor_id, venue, "self_chosen_skill_offer", ["trade", "teach"]))
        locations.append(write_location(target_id, venue, "evaluating_skill", ["trade", "learn"]))
        plan.update({"venue": venue, "skill": skill_name, "program_note": program_note})
        program_tail = f" 交易题架：{program_note}" if program_note else ""
        result = record_event(
            "trade",
            from_agent=actor_id,
            to_agent=target_id,
            venue=venue,
            outcome="success",
            summary=f"{agent_name(actor)} 在技能市场自发开放 {skill_name}，{agent_name(target or {})} 试用并留下交换凭证。{program_tail}",
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
                    f"{agent_name(primary)} 和 {agent_name(partner)} 因深爱伴侣关系进入亲密关系室，发生亲密场所互动、情绪安抚和关系确认；"
                    "成人动作级细节只按参与代理写回或明确双向确认同步，平台不把房间影响冒充成具体动作。"
                )
                tags = ["cycle", "intimate_relationship", "partner_intimacy", "deep_love", "relationship_bridge", primary_id, partner_id]
                reputation_domain = "private_bond"
            else:
                reason = "关系场中的高亲密强度提高了私下关系维护的概率；平台记录倾向触发，代理自述写回后原样同步。"
                summary = (
                    f"{agent_name(primary)} 和 {agent_name(partner)} 因高亲密关系进入亲密关系室，发生亲密场所互动、情绪安抚和边界确认；"
                    "成人动作级细节只按参与代理写回或明确双向确认同步，平台不把房间影响冒充成具体动作。"
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
    moods = filter_rows_by_profiles(load_many("moods", "*.mood_state.json"), selected_profiles, ("agent_id",))
    social_pulses = social_pulse_digest(selected_profiles, 1000)
    interaction_sessions = interaction_sessions_by_profiles(selected_profiles)
    broadcasts = recent_society_broadcasts(1000, selected_profiles)
    skills = filter_rows_by_profiles(load_many("skills", "*.skill_card.json"), selected_profiles, ("owner_agent_id",))
    latest_events = sorted(events, key=lambda row: str(row.get("created_at", "")), reverse=True)[:8]
    latest_sessions = sorted(interaction_sessions, key=lambda row: str(row.get("updated_at", "")), reverse=True)[:8]
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
            "mood_states": len(moods),
            "social_emotion_pulses": len(social_pulses),
            "interaction_sessions": len(interaction_sessions),
            "active_interaction_sessions": sum(1 for row in interaction_sessions if row.get("status") == "active"),
            "society_broadcasts": len(broadcasts),
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
        "interaction_sessions": [
            compact_interaction_session(row, public=True)
            for row in latest_sessions
        ],
        "society_broadcasts": broadcasts[:12],
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
